"""Sigma Network — route HTTP locali del modulo (SPEC.md sezione 3).

Sono le route che serve la UI di questa istanza: identita, peer noti, wallet,
impostazioni di condivisione e controllo della scoperta. Le route peer-to-peer,
che parlano con le altre istanze e richiedono verifica di firma, stanno
separate: qui dentro non arriva mai una richiesta di un altro peer.

I singleton sono a livello di modulo e non nel costruttore di un oggetto
perche' il router e' incluso una volta sola nell'app, mentre i test devono
poterli ripuntare su una directory temporanea prima di ogni caso. Da cui
``_reset_singletons()``, che e' parte del contratto verso i test e non un
dettaglio interno.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.logger import get_logger
from core.modules.sigma_network.ailocoin import Wallet
from core.modules.sigma_network.discovery import PeerDiscovery
from core.modules.sigma_network.identity import (
    load_identity,
    peer_id_from_public_key,
    public_identity,
    sign,
    verify,
)
from core.modules.sigma_network.peer_registry import PeerRegistry
from core.modules.sigma_network.provider import InferenceProvider
from core.modules.sigma_network.cluster_broker import ClusterBroker
from core.modules.sigma_network.mining_engine import MiningEngine
from core.modules.sigma_network.federated_aggregator import FederatedAggregator
from core.modules.sigma_network.auth_manager import AuthManager

log = get_logger("sigma_network.handlers")
# Alcune route storiche usano `logger`: stesso logger, niente NameError.
logger = log

router = APIRouter()

MODULE_VERSION = "0.2.0"

#: Percorsi di persistenza. Riassegnabili dai test prima di ``_reset_singletons``.
_identity_file: Optional[str] = None
_peers_file: Optional[str] = None
_wallet_file: Optional[str] = None
_auth_file: Optional[str] = None
_settings_file: Optional[str] = None

_identity: Optional[Dict[str, str]] = None
_registry_instance: Optional[PeerRegistry] = None
_wallet_instance: Optional[Wallet] = None
_discovery_instance: Optional[PeerDiscovery] = None
_settings: Optional[Dict[str, Any]] = None
_broker_instance: Optional[ClusterBroker] = None
_mining_instance: Optional[MiningEngine] = None
_aggregator_instance: Optional[FederatedAggregator] = None
_auth_instance: Optional[AuthManager] = None
_provider_instance: Optional[InferenceProvider] = None
_current_session_token: Optional[str] = None

_lock = threading.RLock()

#: Default di SPEC.md sezione 3. La condivisione parte SPENTA: mettere il
#: proprio hardware a disposizione di sconosciuti e' una decisione esplicita.
DEFAULT_SETTINGS: Dict[str, Any] = {
    "sharing_enabled": False,
    "shared_models": [],
    "rate_tokens_per_coin": 1000,
    "max_tokens_per_request": 4096,
    "max_concurrent": 3,
    "max_requests_per_hour": 60,
    "display_name": "Sigma Peer",
}


def _default_path(filename: str) -> str:
    """Percorso di persistenza sotto data/sigma_network/."""
    from core.paths import project_root

    return str(project_root() / "data" / "sigma_network" / filename)


def _reset_singletons() -> None:
    """Scarta lo stato in memoria, fermando la scoperta se e' attiva.

    Chiamata dai test fra un caso e l'altro. Ferma il thread di discovery
    prima di dimenticarlo: lasciarlo vivo terrebbe un socket UDP aperto per
    tutta la sessione di test e il caso successivo lo troverebbe occupato.
    """
    global _identity, _registry_instance, _wallet_instance, _discovery_instance, _settings
    global _broker_instance, _mining_instance, _aggregator_instance, _auth_instance, _current_session_token

    with _lock:
        if _discovery_instance is not None:
            try:
                _discovery_instance.stop()
            except Exception as exc:  # noqa: BLE001 - lo stop non deve mai propagare
                log.warning("Arresto discovery durante il reset fallito: %s", exc)
        if _mining_instance is not None:
            try:
                _mining_instance.stop()
            except Exception:
                pass
        _identity = None
        _registry_instance = None
        _wallet_instance = None
        _discovery_instance = None
        _settings = None
        _settings_file = None
        _broker_instance = None
        _mining_instance = None
        _aggregator_instance = None
        _auth_instance = None
        _provider_instance = None
        _current_session_token = None
    # Definita in fondo al file: a runtime esiste sempre.
    _reset_ailo_singletons()


def _get_auth() -> AuthManager:
    global _auth_instance
    with _lock:
        if _auth_instance is None:
            _auth_instance = AuthManager(_auth_file or _default_path("accounts.json"))
        return _auth_instance


def _get_identity() -> Dict[str, str]:
    global _identity, _current_session_token
    with _lock:
        if _current_session_token:
            sess = _get_auth().get_session(_current_session_token)
            if sess:
                return {
                    "peer_id": sess["peer_id"],
                    "public_key": sess["public_key"],
                    "private_key": sess["private_key_b64"],
                }
        if _identity is None:
            _identity = load_identity(_identity_file or _default_path("identity.json"))
        return _identity


def _get_registry() -> PeerRegistry:
    global _registry_instance
    with _lock:
        if _registry_instance is None:
            _registry_instance = PeerRegistry(_peers_file or _default_path("peers.json"))
        return _registry_instance


def _get_wallet() -> Wallet:
    global _wallet_instance
    with _lock:
        if _wallet_instance is None:
            _wallet_instance = Wallet(_wallet_file or _default_path("wallet.json"))
        return _wallet_instance


def _get_settings() -> Dict[str, Any]:
    global _settings
    with _lock:
        if _settings is None:
            path = _settings_file or _default_path("settings.json")
            try:
                p = Path(path)
                if p.is_file():
                    loaded = json.loads(p.read_text(encoding="utf-8"))
                    _settings = {**DEFAULT_SETTINGS, **loaded}
                else:
                    _settings = dict(DEFAULT_SETTINGS)
            except Exception:
                _settings = dict(DEFAULT_SETTINGS)
        return _settings


def _detect_server_port() -> int:
    try:
        from sigma_server import _get_configured_host_port_ssl
        _, port, _, _, _ = _get_configured_host_port_ssl()
        return port or 8000
    except Exception:
        return 8000


def _auto_handshake_with_peer(host: str, port: int, peer_info: Dict[str, Any]) -> None:
    """Esegue un handshake crittografico automatico verso un peer appena scoperto."""
    def _run():
        try:
            identity = _get_identity()
            settings = _get_settings()
            local_peer_id = identity["peer_id"]
            remote_peer_id = peer_info.get("peer_id")
            if not remote_peer_id or remote_peer_id == local_peer_id:
                return

            priv_str = identity.get("private_key")
            if not priv_str:
                return
            priv_bytes = base64.b64decode(priv_str)
            ts = str(time.time())
            msg = f"cluster_handshake:{local_peer_id}:{remote_peer_id}:{ts}"
            sig = sign(priv_bytes, msg)

            hs_payload = {
                "peer_id": local_peer_id,
                "public_key": identity["public_key"],
                "name": str(settings.get("display_name") or "Sigma Peer"),
                "port": _detect_server_port(),
                "models": list(settings.get("shared_models") or []),
                "version": MODULE_VERSION,
                "message": msg,
                "signature": sig,
            }

            import requests
            url = f"http://{host}:{port}/api/sigma_network/p2p/handshake"
            resp = requests.post(url, json=hs_payload, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                remote_pubkey = data.get("public_key")
                registry = _get_registry()
                registry.add_peer(
                    host=host,
                    port=port,
                    peer_id=remote_peer_id,
                    public_key=remote_pubkey or peer_info.get("public_key", ""),
                    name=data.get("name") or peer_info.get("name", "Sigma Peer"),
                    models=data.get("models") or peer_info.get("models", []),
                    version=data.get("version") or peer_info.get("version", "1.0.0"),
                )
                if settings.get("cluster_auto_trust", True):
                    try:
                        registry.set_state(remote_peer_id, "trusted")
                    except Exception:
                        pass
                    log.info("[SigmaNetwork] Auto-handshake cluster completato: peer %s (%s:%d) verificato e trusted!", remote_peer_id, host, port)

                    # Gossip Protocol (PEX): scopri e collega a cascata i peer noti al peer remoto
                    gossip_peers = data.get("peers") or []
                    for gp in gossip_peers:
                        gp_id = gp.get("peer_id")
                        gp_host = gp.get("host")
                        gp_port = gp.get("port")
                        if gp_id and gp_host and gp_port and gp_id != local_peer_id:
                            if not registry.get(gp_id):
                                _auto_handshake_with_peer(gp_host, gp_port, {"peer_id": gp_id})
        except Exception as exc:
            log.debug("Auto-handshake verso %s:%d non completato: %s", host, port, exc)

    t = threading.Thread(target=_run, name=f"handshake-{host}", daemon=True)
    t.start()


def _get_discovery() -> PeerDiscovery:
    global _discovery_instance
    with _lock:
        if _discovery_instance is None:
            identity = _get_identity()
            settings = _get_settings()
            port = _detect_server_port()
            _discovery_instance = PeerDiscovery(
                registry=_get_registry(),
                peer_id=identity["peer_id"],
                name=str(settings.get("display_name") or "Sigma Peer"),
                port=port,
                models=list(settings.get("shared_models") or []),
                version=MODULE_VERSION,
                on_peer_found=_auto_handshake_with_peer,
            )
            # Avvio automatico discovery daemon
            try:
                _discovery_instance.start()
                log.info("[SigmaNetwork] PeerDiscovery avviato automaticamente sulla porta %d (UDP 47777)", port)
            except Exception as e:
                log.warning("[SigmaNetwork] Impossibile avviare PeerDiscovery in automatico: %s", e)
        return _discovery_instance


def _get_broker() -> ClusterBroker:
    global _broker_instance
    with _lock:
        if _broker_instance is None:
            _broker_instance = ClusterBroker(
                registry_getter=_get_registry,
                wallet_getter=_get_wallet,
                identity_getter=_get_identity,
                settings_getter=_get_settings,
            )
        return _broker_instance


def _get_mining() -> MiningEngine:
    global _mining_instance
    with _lock:
        if _mining_instance is None:
            _mining_instance = MiningEngine(
                wallet_getter=_get_wallet,
                identity_getter=_get_identity,
            )
        return _mining_instance


def _get_aggregator() -> FederatedAggregator:
    global _aggregator_instance
    with _lock:
        if _aggregator_instance is None:
            _aggregator_instance = FederatedAggregator(min_gradients=2, timeout_s=60.0)
        return _aggregator_instance


def _provider() -> InferenceProvider:
    global _provider_instance
    with _lock:
        if _provider_instance is None:
            _provider_instance = InferenceProvider(_get_settings())
        return _provider_instance




# ---------------------------------------------------------------------------
# Corpi delle richieste
# ---------------------------------------------------------------------------

class PeerAddRequest(BaseModel):
    host: str
    port: int


class PeerTrustRequest(BaseModel):
    peer_id: str
    trusted: bool


class SettingsRequest(BaseModel):
    sharing_enabled: Optional[bool] = None
    shared_models: Optional[List[str]] = None
    rate_tokens_per_coin: Optional[int] = None
    max_tokens_per_request: Optional[int] = None
    max_concurrent: Optional[int] = None
    max_requests_per_hour: Optional[int] = None
    display_name: Optional[str] = None


class ClusterInferRequest(BaseModel):
    prompt: str
    model: str
    max_tokens: Optional[int] = 1024
    preferred_peer_id: Optional[str] = None


class FaucetRequest(BaseModel):
    amount: Optional[float] = 100.0


class MiningIntensityRequest(BaseModel):
    intensity: int


class WalletTransferRequest(BaseModel):
    recipient_id: str
    amount: float
    note: Optional[str] = ""


class GradientsPushRequest(BaseModel):
    data: str = ""
    step: int = 0
    loss: float = 2.0
    peer_id: Optional[str] = None
    signature: Optional[str] = None


class UserRegisterRequest(BaseModel):
    username: str
    password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserImportRequest(BaseModel):
    username: str
    password: str
    mnemonic_or_privkey: str


class UserSessionTokenRequest(BaseModel):
    session_token: Optional[str] = None


class BenchmarkRequest(BaseModel):
    model: Optional[str] = None
    model_id: Optional[str] = None
    tokens: Optional[int] = 48
    test_tokens: Optional[int] = 48


class ProviderGuardRequest(BaseModel):
    local_user_priority: Optional[bool] = None
    max_memory_percent: Optional[float] = None
    access_policy: Optional[str] = None




# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("/identity")
def get_identity() -> Dict[str, Any]:
    """Identita pubblica di questo peer. Non espone mai la chiave privata."""
    identity = _get_identity()
    exposed = public_identity(identity)
    return {
        "peer_id": exposed["peer_id"],
        "public_key": exposed["public_key"],
        "name": str(_get_settings().get("display_name") or "Sigma Peer"),
        "version": MODULE_VERSION,
    }


@router.get("/peers")
def list_peers() -> List[Dict[str, Any]]:
    """Tutti i peer noti, in qualunque stato."""
    return _get_registry().all_peers()


@router.post("/peers/add")
def add_peer(body: PeerAddRequest) -> Dict[str, Any]:
    """Aggiunge manualmente un peer per host e porta.

    Tenta subito una verifica diretta con /p2p/hello per registrare identità reale,
    modelli e latenza istantanea. Se il nodo non risponde, ripiega su un identificativo
    provvisorio finché non viene contattato.
    """
    host = body.host.strip()
    if not host:
        raise HTTPException(status_code=400, detail="host mancante")
    if not (0 < body.port < 65536):
        raise HTTPException(status_code=400, detail="porta non valida")

    import requests as _requests
    url = f"http://{host}:{body.port}/api/sigma_network/p2p/hello"
    try:
        t0 = time.time()
        resp = _requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            real_pid = data.get("peer_id")
            pub_key = data.get("public_key", "")
            name = data.get("name") or f"{host}:{body.port}"
            models = data.get("models", [])
            version = data.get("version", "1.0.0")
            if real_pid:
                peer = _get_registry().add_peer(
                    host=host,
                    port=body.port,
                    peer_id=real_pid,
                    public_key=pub_key,
                    name=name,
                    models=models,
                    version=version,
                )
                latency = round((time.time() - t0) * 1000, 1)
                _get_registry().touch(real_pid, latency_ms=latency)
                log.info("[SigmaNetwork] Peer aggiunto e verificato con successo: %s (%s:%d)", name, host, body.port)
                return peer
    except Exception as exc:
        log.debug("[SigmaNetwork] Handshake immediato fallito con %s: %s (registro provvisorio)", url, exc)

    placeholder = f"{host}:{body.port}".encode("utf-8")
    provisional_id = peer_id_from_public_key(placeholder)
    return _get_registry().add_peer(
        host=host,
        port=body.port,
        peer_id=provisional_id,
        public_key=base64.b64encode(placeholder).decode("ascii"),
        name=f"{host}:{body.port}",
        models=[],
    )


@router.post("/peers/trust")
def set_peer_trust(body: PeerTrustRequest) -> Dict[str, Any]:
    """Promuove un peer a ``trusted`` o lo riporta a ``discovered``."""
    state = "trusted" if body.trusted else "discovered"
    try:
        peer = _get_registry().set_state(body.peer_id, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if peer is None:
        raise HTTPException(status_code=404, detail=f"peer '{body.peer_id}' non trovato")
    return peer


@router.delete("/peers/{peer_id}")
def remove_peer(peer_id: str) -> Dict[str, Any]:
    """Dimentica un peer. 404 se non era noto."""
    if not _get_registry().remove(peer_id):
        raise HTTPException(status_code=404, detail=f"peer '{peer_id}' non trovato")
    return {"removed": True, "peer_id": peer_id}


@router.get("/wallet")
def get_wallet() -> Dict[str, Any]:
    """Saldo AiloCoin di questo peer e storico delle ricevute."""
    wallet = _get_wallet()
    totals = wallet.balance(_get_identity()["peer_id"])
    return {
        "balance": totals.get("balance", 0.0),
        "earned": totals.get("earned", 0.0),
        "spent": totals.get("spent", 0.0),
        "receipts": wallet.receipts(),
    }


@router.get("/nat/status")
def get_nat_status() -> Dict[str, Any]:
    """Rileva e restituisce l'IP LAN, l'IP pubblico WAN riflesso via STUN e lo stato NAT."""
    from core.modules.sigma_network.nat_traversal import detect_nat_info
    port = _detect_server_port()
    return detect_nat_info(local_service_port=port)


@router.post("/wallet/settle")
def get_settlement_bundle(consumer_peer_id: Optional[str] = None) -> Dict[str, Any]:
    """Genera un bundle Merkle Tree con prove crittografiche per il settlement on-chain delle ricevute."""
    from core.modules.sigma_network.settlement import create_settlement_bundle
    wallet = _get_wallet()
    my_id = _get_identity()["peer_id"]
    receipts = wallet.receipts()
    return create_settlement_bundle(
        receipts=receipts,
        provider_peer_id=my_id,
        consumer_peer_id=consumer_peer_id or "global_settlement",
    )


@router.get("/settings")
def get_settings() -> Dict[str, Any]:
    """Impostazioni di condivisione correnti."""
    return dict(_get_settings())


@router.post("/settings")
def update_settings(body: SettingsRequest) -> Dict[str, Any]:
    """Aggiorna le impostazioni, le salva su file e diffonde immediatamente l'annuncio UDP broadcast se attivo."""
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    with _lock:
        current = _get_settings()
        current.update(changes)
        res = dict(current)
        try:
            path = _settings_file or _default_path("settings.json")
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(res, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Salvataggio persistente settings fallito: %s", e)

    # Annuncio gossip/UDP immediato se discovery è attiva o se la condivisione è stata abilitata
    try:
        disc = _get_discovery()
        if changes.get("sharing_enabled") is True and not disc.is_running():
            disc.start()
        if disc.is_running():
            disc.announce_now()

        # Se il provider viene abilitato, tenta auto-port forwarding UPnP sul router
        if changes.get("sharing_enabled") is True:
            def _upnp_bg():
                try:
                    from core.modules.sigma_network.nat_traversal import forward_port_upnp
                    forward_port_upnp(internal_port=_detect_server_port())
                except Exception as upnp_err:
                    log.debug("UPnP auto-forwarding fallito: %s", upnp_err)
            threading.Thread(target=_upnp_bg, daemon=True).start()
    except Exception as e:
        log.warning("Annuncio P2P durante update_settings fallito: %s", e)

    return res


@router.post("/discovery/start")
def start_discovery() -> Dict[str, Any]:
    """Avvia annuncio e ascolto UDP sulla rete locale."""
    try:
        _get_discovery().start()
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"scoperta non avviabile: {exc}") from exc
    return {"running": True}


@router.post("/discovery/stop")
def stop_discovery() -> Dict[str, Any]:
    """Ferma annuncio e ascolto."""
    with _lock:
        if _discovery_instance is not None:
            _discovery_instance.stop()
    return {"running": False}






_provider_instance: Optional[InferenceProvider] = None


def _provider() -> InferenceProvider:
    """Il provider di inferenza di questo nodo, creato alla prima richiesta."""
    global _provider_instance
    with _lock:
        if _provider_instance is None:
            _provider_instance = InferenceProvider()
        return _provider_instance


def _is_inference_engine_available() -> bool:
    """Se il motore locale puo' servire una richiesta adesso.

    Chiamata prima di accettare lavoro da un altro peer: promettere inferenza e
    poi fallire a meta' stream costa al chiamante una moneta e un timeout,
    mentre un 503 gli permette di rivolgersi altrove.
    """
    try:
        from core.engine.unified_runtime import sigma_engine

        return bool(getattr(sigma_engine, "model_instance", None)
                    or getattr(sigma_engine, "active_backend_instance", None))
    except Exception as exc:  # noqa: BLE001 - l'indisponibilita' e' una risposta
        log.warning("Motore non interrogabile: %s", exc)
        return False


@router.get("/p2p/hello")
def p2p_hello() -> Dict[str, Any]:
    """Presentazione di questo peer a chi lo interroga.

    Restituisce peer_id, chiave pubblica, modelli esposti e gossip dei peer noti.
    """
    identity = _get_identity()
    settings = _get_settings()
    registry = _get_registry()
    known_peers = [
        {"peer_id": p.get("peer_id"), "host": p.get("host"), "port": p.get("port")}
        for p in registry.all_peers()
        if p.get("peer_id") != identity["peer_id"] and p.get("state") in ("trusted", "discovered")
    ][:10]

    return {
        "peer_id": identity["peer_id"],
        "public_key": identity["public_key"],
        "name": str(settings.get("display_name") or "Sigma Peer"),
        "version": MODULE_VERSION,
        "models": list(settings.get("shared_models") or []),
        "accepting": bool(settings.get("sharing_enabled")),
        "peers": known_peers,
    }


@router.post("/p2p/handshake")
def p2p_handshake(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handshake crittografico tra nodi del cluster Sigma Network.

    Verifica la firma Ed25519 del peer remoto, salva la chiave pubblica e
    stabilisce la fiducia reciproca (auto-trust) in modo sicuro e decentralizzato.
    """
    peer_id = str(body.get("peer_id") or "")
    public_key = str(body.get("public_key") or "")
    message = str(body.get("message") or "")
    signature = str(body.get("signature") or "")

    if not peer_id or not public_key or not message or not signature:
        raise HTTPException(status_code=400, detail="peer_id, public_key, message e signature sono obbligatori")

    if not verify(public_key, message, signature):
        raise HTTPException(status_code=401, detail="Firma crittografica dell'handshake non valida")

    identity = _get_identity()
    settings = _get_settings()
    registry = _get_registry()

    # Registra o aggiorna il peer chiamante memorizzando la chiave pubblica autenticata
    registry.add_peer(
        host=str(body.get("host") or "127.0.0.1"),
        port=int(body.get("port") or 8000),
        peer_id=peer_id,
        public_key=public_key,
        name=str(body.get("name") or "Sigma Peer"),
        models=list(body.get("models") or []),
        version=str(body.get("version") or MODULE_VERSION),
    )

    if settings.get("cluster_auto_trust", True):
        try:
            registry.set_state(peer_id, "trusted")
            log.info("[SigmaNetwork] Handshake validato: peer %s promosso a trusted!", peer_id)
        except Exception:
            pass

    # Genera la contro-firma locale per confermare l'accordo reciproco
    priv_str = identity.get("private_key")
    resp_sig = ""
    resp_msg = f"cluster_handshake_ack:{identity['peer_id']}:{peer_id}:{time.time()}"
    if priv_str:
        try:
            priv_bytes = base64.b64decode(priv_str)
            resp_sig = sign(priv_bytes, resp_msg)
        except Exception as exc:
            log.debug("Errore generazione contro-firma handshake: %s", exc)

    known_peers = [
        {"peer_id": p.get("peer_id"), "host": p.get("host"), "port": p.get("port")}
        for p in registry.all_peers()
        if p.get("peer_id") != identity["peer_id"] and p.get("state") in ("trusted", "discovered")
    ][:15]

    return {
        "status": "ok",
        "peer_id": identity["peer_id"],
        "public_key": identity["public_key"],
        "name": str(settings.get("display_name") or "Sigma Peer"),
        "version": MODULE_VERSION,
        "models": list(settings.get("shared_models") or []),
        "accepting": bool(settings.get("sharing_enabled")),
        "message": resp_msg,
        "signature": resp_sig,
        "peers": known_peers,
    }


@router.get("/cluster/models")
def get_cluster_models(include_local: bool = False) -> Dict[str, Any]:
    """Restituisce il catalogo aggregato dei modelli disponibili nel cluster P2P offerti da altri nodi."""
    broker = _get_broker()
    models = broker.get_cluster_models(include_local=include_local)
    return {
        "models": models,
        "total": len(models),
        "cluster_active": True,
    }


@router.post("/cluster/infer")
def cluster_infer(body: Dict[str, Any]) -> StreamingResponse:
    """Esegue inferenza distribuita nel cluster regolando il costo in AiloToken."""
    prompt = body.get("prompt") or body.get("messages") or ""
    model = str(body.get("model") or "")
    max_tokens = int(body.get("max_tokens") or 1024)
    preferred_peer_id = body.get("preferred_peer_id")

    if not prompt or not model:
        raise HTTPException(status_code=400, detail="prompt e model sono obbligatori")

    broker = _get_broker()
    generator = broker.execute_cluster_inference(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        preferred_peer_id=preferred_peer_id,
    )
    return StreamingResponse(generator, media_type="text/event-stream; charset=utf-8")


@router.post("/cluster/sweep")
def trigger_cluster_sweep() -> Dict[str, Any]:
    """Avvia una scansione immediata della LAN per collegare automaticamente tutti i nodi."""
    try:
        disc = _get_discovery()
        count = disc.sweep_now()
        disc.announce_now()
        return {
            "status": "ok",
            "peers_discovered_via_sweep": count,
            "total_peers": len(_get_registry().all_peers()),
        }
    except Exception as exc:
        log.error("Errore cluster sweep: %s", exc)
        return {
            "status": "error",
            "detail": str(exc),
            "total_peers": len(_get_registry().all_peers()),
        }


@router.post("/cluster/bootstrap")
def trigger_cluster_bootstrap(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Interroga i nodi seed globali e sincronizza la rete P2P mondiale."""
    try:
        disc = _get_discovery()
        seeds = (body.get("seeds") if body else None)
        count = disc.bootstrap_now(seeds=seeds)
        return {
            "status": "ok",
            "peers_discovered_via_bootstrap": count,
            "total_peers": len(_get_registry().all_peers()),
        }
    except Exception as exc:
        log.error("Errore cluster bootstrap: %s", exc)
        return {
            "status": "error",
            "detail": str(exc),
            "total_peers": len(_get_registry().all_peers()),
        }


@router.post("/nat/upnp/forward")
def trigger_upnp_forward(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mappa automaticamente la porta del server sul router domestico via UPnP IGD."""
    from core.modules.sigma_network.nat_traversal import forward_port_upnp
    target_port = (body.get("port") if body else None) or _detect_server_port()
    return forward_port_upnp(internal_port=target_port, external_port=target_port)


@router.post("/p2p/infer")
def p2p_infer(body: Dict[str, Any]) -> StreamingResponse:
    """Esegue inferenza per conto di un altro peer.

    L'ordine dei controlli non e' arbitrario: prima si stabilisce CHI sta
    parlando, poi si verifica la firma con la chiave pubblica di quel peer.
    Verificare prima di aver trovato il mittente significa non poter usare la
    sua chiave, ed e' una verifica che non verifica.
    """
    peer_id = str(body.get("peer_id") or "")
    signature = body.get("signature")
    message = body.get("message")

    if not peer_id or not signature or not message:
        raise HTTPException(status_code=401, detail="peer_id, message o signature mancanti")

    peer = _get_registry().get(peer_id)
    if peer is None:
        raise HTTPException(status_code=401, detail="Peer sconosciuto")

    if not verify(peer["public_key"], str(message), str(signature)):
        raise HTTPException(status_code=401, detail="Firma non valida")

    if peer.get("state") != "trusted":
        raise HTTPException(status_code=403, detail="Peer non trusted")

    settings = _get_settings()
    ok, motivo = _provider().can_serve(peer_id, _get_registry(), settings)
    if not ok:
        raise HTTPException(status_code=429, detail=motivo)

    payload, errore = _provider().clamp_request(dict(body), settings)
    if errore:
        raise HTTPException(status_code=400, detail=errore)

    if not _is_inference_engine_available():
        raise HTTPException(status_code=503, detail="Motore di inferenza non disponibile")

    def event_generator():
        try:
            for token in _provider().serve(payload):
                yield "data: " + json.dumps({"token": token}, ensure_ascii=False) + "\n\n"
        except Exception as exc:  # noqa: BLE001 - l'errore deve arrivare al peer
            log.warning("Inferenza per %s interrotta: %s", peer_id, exc)
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream; charset=utf-8"
    )


@router.post("/p2p/receipt")
def p2p_receipt(body: Dict[str, Any]) -> Dict[str, Any]:
    """Controfirma una ricevuta emessa da un peer che ha svolto lavoro per noi.

    La ricevuta arriva gia' firmata dal provider: qui si aggiunge la seconda
    firma, quella del consumer, sullo STESSO documento. Costruirne uno nuovo
    lascerebbe le due parti con due carte diverse, ed e' il contrario di cio'
    che serve quando piu' avanti andranno regolate su AiloNetwork.

    Come su /p2p/infer, la firma del chiamante si verifica con la chiave
    pubblica del chiamante: quella di questo nodo non dice nulla su chi ha
    mandato la richiesta.
    """
    receipt = body.get("receipt")
    peer_id = str(body.get("peer_id") or "")
    signature = body.get("signature")
    message = body.get("message")

    if not isinstance(receipt, dict) or not peer_id or not signature or not message:
        raise HTTPException(
            status_code=400, detail="receipt, peer_id, message e signature sono obbligatori"
        )

    peer = _get_registry().get(peer_id)
    if peer is None:
        raise HTTPException(status_code=401, detail="Peer sconosciuto")

    if not verify(peer["public_key"], str(message), str(signature)):
        raise HTTPException(status_code=401, detail="Firma non valida")

    if peer.get("state") != "trusted":
        raise HTTPException(status_code=403, detail="Peer non trusted")

    identity = _get_identity()
    try:
        controfirmata = _get_wallet().countersign(
            receipt,
            base64.b64decode(identity["private_key"]),
            provider_public_key=peer["public_key"],
        )
    except ValueError as exc:
        # La firma del provider non regge: la ricevuta non descrive un lavoro
        # che quel peer possa dimostrare di aver svolto.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"countersigned": controfirmata}


@router.get("/peers/map")
def get_network_map() -> Dict[str, Any]:
    """Topologia completa della rete per il radar e visualizzazione dei nodi."""
    identity = _get_identity()
    settings = _get_settings()
    local_info = {
        "peer_id": identity["peer_id"],
        "name": str(settings.get("display_name") or "Sigma Studio (Locale)"),
        "models": list(settings.get("shared_models") or []),
        "version": MODULE_VERSION,
    }
    return _get_registry().get_network_map(local_info)


@router.post("/peers/ping")
def ping_peers() -> Dict[str, Any]:
    """Invia un probe HTTP rapido a tutti i peer per misurare latenza e stato online."""
    import requests as _requests

    registry = _get_registry()
    peers = registry.all_peers()
    updated = []

    for p in peers:
        host = p.get("host")
        port = p.get("port")
        pid = p.get("peer_id")
        if not host or not port or not pid:
            continue

        url = f"http://{host}:{port}/api/sigma_network/p2p/hello"
        t0 = time.time()
        try:
            resp = _requests.get(url, timeout=1.8)
            if resp.status_code == 200:
                latency = round((time.time() - t0) * 1000, 1)
                data = resp.json()
                registry.touch(pid, latency_ms=latency)
                # Aggiorna anche i modelli e il nome se annunciati
                p["latency_ms"] = latency
                p["last_seen"] = time.time()
                if "models" in data:
                    p["models"] = data["models"]
                if "name" in data:
                    p["name"] = data["name"]
                updated.append(pid)
        except Exception:
            pass

    registry.save()
    return {"pinged": len(peers), "online_responded": len(updated), "peer_ids": updated}


@router.get("/local_models")
def get_local_models() -> List[Dict[str, Any]]:
    """Restituisce l'elenco dei modelli presenti localmente su questa istanza di Sigma Studio."""
    models_out = []
    try:
        from core.engine.provider_server import get_all_available_models
        for m in get_all_available_models():
            mid = m.get("id") or m.get("name")
            if mid:
                models_out.append({
                    "id": mid,
                    "name": mid.split("/")[-1].replace(".gguf", ""),
                    "size": m.get("size", "N/A"),
                })
    except Exception as exc:
        log.warning("Impossibile recuperare modelli locali da provider_server: %s", exc)

    # Includi sempre almeno i modelli configurati o fallback AILO
    settings = _get_settings()
    for configured in settings.get("shared_models", []):
        if not any(x["id"] == configured for x in models_out):
            models_out.append({
                "id": configured,
                "name": configured.split("/")[-1],
                "size": "Configurato",
            })

    if not models_out:
        models_out.append({"id": "AILO-152M", "name": "AILO-152M (SwiGLU/RoPE)", "size": "152M params"})

    return models_out


@router.get("/cluster/models")
def get_cluster_models() -> List[Dict[str, Any]]:
    """Restituisce il catalogo unificato dei modelli serviti dall'intero cluster P2P."""
    return _get_broker().get_cluster_models()


def _safe_stream(generator: Generator[str, None, None]) -> Generator[str, None, None]:
    """Inoltra i chunk SSE proteggendo il client da errori HTTP 500 non gestiti."""
    try:
        for chunk in generator:
            yield chunk
    except Exception as exc:
        logger.error("Errore nello streaming SSE: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'error': f'Errore di streaming: {exc}'})}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/cluster/infer")
def cluster_infer(body: ClusterInferRequest) -> StreamingResponse:
    """Esegue inferenza nel cluster P2P con streaming SSE e regolamento AiloCoin."""
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt mancante")
    if not body.model.strip():
        raise HTTPException(status_code=400, detail="model mancante")

    max_tokens = min(body.max_tokens or 1024, 4096)
    generator = _get_broker().execute_cluster_inference(
        prompt=body.prompt,
        model=body.model,
        max_tokens=max_tokens,
        preferred_peer_id=body.preferred_peer_id,
    )
    return StreamingResponse(_safe_stream(generator), media_type="text/event-stream; charset=utf-8")


@router.post("/inference/remote")
def inference_remote(body: dict):
    """Endpoint compatibile per richieste di inferenza remota."""
    prompt = body.get("prompt", "")
    model = body.get("model", "")
    remote_peer_id = body.get("remote_peer_id")
    max_tokens = int(body.get("max_tokens") or 1024)

    if not prompt or not model:
        raise HTTPException(status_code=400, detail="prompt e model sono obbligatori")

    generator = _get_broker().execute_cluster_inference(
        prompt=prompt,
        model=model,
        max_tokens=max_tokens,
        preferred_peer_id=remote_peer_id,
    )
    return StreamingResponse(_safe_stream(generator), media_type="text/event-stream; charset=utf-8")


@router.post("/wallet/faucet")
def wallet_faucet(body: Optional[FaucetRequest] = None) -> Dict[str, Any]:
    """Accredita una somma iniziale di AiloCoin da Genesis per consentire di testare la rete."""
    amount = 100.0 if body is None or body.amount is None else body.amount
    identity = _get_identity()
    wallet = _get_wallet()
    peer_id = identity["peer_id"]

    try:
        receipt = wallet.mint_faucet(peer_id, amount=amount)
        totals = wallet.balance(peer_id)
        return {
            "status": "success",
            "credited": amount,
            "new_balance": totals["balance"],
            "receipt": receipt,
        }
    except ValueError as e:
        totals = wallet.balance(peer_id)
        # Se il saldo residuo è inferiore a 10 AILO, consentiamo la ricarica per test
        if totals["balance"] < 10.0:
            try:
                receipt = wallet.mint_faucet(peer_id, amount=amount, force=True)
                totals = wallet.balance(peer_id)
                return {
                    "status": "success",
                    "credited": amount,
                    "new_balance": totals["balance"],
                    "receipt": receipt,
                    "note": "Ricarica faucet erogata poiché il saldo era esaurito.",
                }
            except Exception as inner_err:
                logger.error("Errore ricarica faucet forzata: %s", inner_err)

        return {
            "status": "already_claimed",
            "credited": 0.0,
            "new_balance": totals["balance"],
            "detail": f"Genesis Faucet già riscattato per questo wallet. Saldo attuale: {totals['balance']} AILO.",
        }


@router.get("/mining/status")
def get_mining_status() -> Dict[str, Any]:
    """Restituisce lo stato attuale della computazione neurale e ricompense di mining."""
    return _get_mining().get_status()


@router.post("/mining/toggle")
def toggle_mining() -> Dict[str, Any]:
    """Avvia o arresta il mining Proof-of-Useful-Work in background."""
    miner = _get_mining()
    if miner.is_running():
        miner.stop()
    else:
        miner.start()
    return miner.get_status()


@router.post("/mining/step")
def mining_step() -> Dict[str, Any]:
    """Esegue immediatamente un ciclo di calcolo utile e accredita la ricompensa."""
    miner = _get_mining()
    result = miner.compute_step_now()
    status = miner.get_status()
    status["last_step"] = result
    return status


@router.post("/mining/intensity")
def set_mining_intensity(body: MiningIntensityRequest) -> Dict[str, Any]:
    """Imposta l'intensità del mining (1=bassa, 2=bilanciata, 3=alta)."""
    miner = _get_mining()
    miner.set_intensity(body.intensity)
    return miner.get_status()


@router.post("/wallet/verify_chain")
def wallet_verify_chain() -> Dict[str, Any]:
    """Verifica l'integrità crittografica di tutte le ricevute e blocchi registrati nel ledger."""
    wallet = _get_wallet()
    return wallet.verify_chain()


@router.post("/wallet/transfer")
def wallet_transfer(body: WalletTransferRequest) -> Dict[str, Any]:
    """Trasferisce AiloCoin dal peer locale a un peer destinatario con firma Ed25519."""
    identity = _get_identity()
    wallet = _get_wallet()
    priv_bytes = base64.b64decode(identity["private_key"])
    try:
        receipt = wallet.transfer(
            sender_id=identity["peer_id"],
            recipient_id=body.recipient_id,
            amount=body.amount,
            private_key_bytes=priv_bytes,
            note=body.note or "",
        )
        totals = wallet.balance(identity["peer_id"])
        return {
            "status": "success",
            "receipt": receipt,
            "new_balance": totals["balance"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/federated/status")
def get_federated_status() -> Dict[str, Any]:
    """Restituisce lo stato dell'aggregatore Federated Averaging."""
    return _get_aggregator().get_state()


@router.post("/federated/gradients")
def push_federated_gradients(body: GradientsPushRequest) -> Dict[str, Any]:
    """Invia gradienti compressi da un peer/miner all'aggregatore federato."""
    identity = _get_identity()
    peer_id = body.peer_id or identity["peer_id"]
    aggregator = _get_aggregator()
    payload = {
        "data": body.data,
        "step": body.step,
        "loss": body.loss,
    }
    return aggregator.push_gradients(
        peer_id=peer_id,
        gradients_payload=payload,
        signature=body.signature,
    )


@router.post("/federated/aggregate")
def force_federated_aggregate() -> Dict[str, Any]:
    """Esegue un round forzato di aggregazione FedAvg se ci sono gradienti nel buffer."""
    aggregator = _get_aggregator()
    success, version = aggregator.aggregate_now()
    return {
        "aggregated": success,
        "model_version": version,
        "state": aggregator.get_state(),
    }


@router.get("/federated/weights")
def get_federated_weights() -> Dict[str, Any]:
    """Restituisce i metadati e versione dei pesi globali aggiornati via federated learning."""
    return _get_aggregator().get_latest_weights_metadata()


# ---------------------------------------------------------------------------
# Autenticazione & Custodia Wallet
# ---------------------------------------------------------------------------

@router.post("/auth/register")
def auth_register(body: UserRegisterRequest) -> Dict[str, Any]:
    """Registra un nuovo account utente con Seed Phrase a 12 parole e wallet Ed25519 cifrato."""
    global _current_session_token
    auth = _get_auth()
    try:
        res = auth.register_user(username=body.username, password=body.password)
        _current_session_token = res["session_token"]
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/login")
def auth_login(body: UserLoginRequest) -> Dict[str, Any]:
    """Esegue il login, decifra la chiave privata del wallet e attiva la sessione."""
    global _current_session_token
    auth = _get_auth()
    try:
        res = auth.login(username=body.username, password=body.password)
        _current_session_token = res["session_token"]
        return res
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/import")
def auth_import(body: UserImportRequest) -> Dict[str, Any]:
    """Ripristina un wallet esistente tramite 12 parole mnemoniche o chiave privata."""
    global _current_session_token
    auth = _get_auth()
    try:
        res = auth.import_wallet(
            username=body.username,
            password=body.password,
            mnemonic_or_privkey=body.mnemonic_or_privkey,
        )
        _current_session_token = res["session_token"]
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/session")
def auth_session() -> Dict[str, Any]:
    """Restituisce lo stato dell'utente e wallet correntemente autenticato."""
    auth = _get_auth()
    sess = auth.get_session(_current_session_token)
    local_accs = auth.list_local_accounts()
    has_accounts = len(local_accs) > 0
    if not sess:
        return {
            "authenticated": False,
            "username": None,
            "peer_id": _get_identity()["peer_id"],
            "wallet_assigned": True,
            "has_accounts": has_accounts,
            "accounts_count": len(local_accs),
            "accounts": local_accs,
        }
    return {
        "authenticated": True,
        "username": sess["username"],
        "peer_id": sess["peer_id"],
        "public_key": sess["public_key"],
        "created_at": sess["created_at"],
        "wallet_assigned": True,
        "has_accounts": has_accounts,
        "accounts_count": len(local_accs),
        "accounts": local_accs,
    }


@router.post("/auth/login_node")
def auth_login_node() -> Dict[str, Any]:
    """Attiva una sessione usando l'identita predefinita del nodo locale."""
    global _current_session_token
    identity = load_identity(_identity_file or _default_path("identity.json"))
    auth = _get_auth()
    priv_raw = base64.b64decode(identity["private_key"])
    account_data = {
        "username": f"Nodo Locale ({identity['peer_id'][:6]})",
        "peer_id": identity["peer_id"],
        "public_key": identity["public_key"],
    }
    session_token = auth._create_session(account_data, priv_raw)
    _current_session_token = session_token
    return {
        "status": "success",
        "username": account_data["username"],
        "peer_id": account_data["peer_id"],
        "public_key": account_data["public_key"],
        "session_token": session_token,
    }


@router.post("/auth/logout")
def auth_logout(body: Optional[UserSessionTokenRequest] = None) -> Dict[str, Any]:
    """Disconnette la sessione del wallet utente."""
    global _current_session_token
    auth = _get_auth()
    token = body.session_token if (body and body.session_token) else _current_session_token
    auth.logout(token)
    _current_session_token = None
    return {"status": "logged_out"}


@router.get("/auth/accounts")
def auth_accounts() -> List[Dict[str, str]]:
    """Elenca i profili / wallet utente salvati localmente su questa macchina."""
    return _get_auth().list_local_accounts()


# ---------------------------------------------------------------------------
# Provider Operations Hub & Profiling
# ---------------------------------------------------------------------------

@router.get("/provider/telemetry")
def get_provider_telemetry() -> Dict[str, Any]:
    """Restituisce la telemetria live del nodo Provider: richieste, throughput, guadagni AILO e RAM."""
    return _provider().get_telemetry()


@router.post("/provider/benchmark")
def run_model_benchmark(body: BenchmarkRequest) -> Dict[str, Any]:
    """Esegue un benchmark prestazionale hardware per il modello specificato determinando il QoS Tier."""
    mid = body.model_id or body.model or "default"
    tokens = body.test_tokens or body.tokens or 48
    res = _provider().benchmark_model(model_id=mid, test_tokens=tokens)
    res["ok"] = True
    return res


@router.post("/provider/guard")
def set_provider_guard(body: ProviderGuardRequest) -> Dict[str, Any]:
    """Aggiorna le impostazioni dello Smart Resource Guard (priorità utente locale, soglia RAM)."""
    settings = _get_settings()
    with _lock:
        if body.local_user_priority is not None:
            settings["local_user_priority"] = body.local_user_priority
        if body.max_memory_percent is not None:
            settings["max_memory_percent"] = body.max_memory_percent
        if body.access_policy is not None:
            settings["access_policy"] = body.access_policy

    _provider().update_guard(
        max_memory_percent=settings.get("max_memory_percent"),
        local_user_priority=settings.get("local_user_priority"),
    )

    guard_data = {
        "local_user_priority": settings.get("local_user_priority", True),
        "max_memory_percent": settings.get("max_memory_percent", 88.0),
        "access_policy": settings.get("access_policy", "open_market"),
    }
    return {
        "ok": True,
        "guard": guard_data,
        **guard_data,
    }


# ==============================================================================
# Rete AiLo — AiloCoin (ALC) e inferenza distribuita
# ==============================================================================
# Collegamento nativo al coordinatore AiLo (ailo-network). Le password non
# passano mai dalla configurazione: arrivano nella singola richiesta di login o
# trasferimento e vengono inoltrate al server senza essere salvate o loggate.

from core.modules.sigma_network.ailo_bridge import (  # noqa: E402 - sezione autonoma
    AiloConfig,
    AiloError,
    AiloInferenceNode,
    AiloNetworkClient,
)

_ailo_config_file: Optional[str] = None
_ailo_config_instance: Optional[AiloConfig] = None
_ailo_node_instance: Optional[AiloInferenceNode] = None


class AiloConfigRequest(BaseModel):
    server_url: Optional[str] = None
    wallet: Optional[str] = None
    email: Optional[str] = None
    node_max_tokens: Optional[int] = None
    node_model: Optional[str] = None
    gpu_label: Optional[str] = None


class AiloCredentialsRequest(BaseModel):
    email: str
    password: str


class AiloTransferRequest(BaseModel):
    to_wallet: str
    amount: float
    password: str


class AiloInferRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 200
    temperature: Optional[float] = 0.8
    backend: Optional[str] = "gpu"


def _ailo_config() -> AiloConfig:
    global _ailo_config_instance
    with _lock:
        if _ailo_config_instance is None:
            _ailo_config_instance = AiloConfig(_ailo_config_file or _default_path("ailo.json"))
        return _ailo_config_instance


def _ailo_client() -> AiloNetworkClient:
    try:
        return AiloNetworkClient(_ailo_config().get()["server_url"])
    except AiloError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _ailo_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Traduce gli errori della rete AiLo in 502: il guasto e' a monte, non qui."""
    try:
        return fn(*args, **kwargs)
    except AiloError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _ailo_generate(prompt: str, max_tokens: int, temperature: float) -> Tuple[str, int]:
    """Genera la risposta per la rete AiLo con il motore locale di Sigma Studio."""
    from core.engine.unified_runtime import sigma_engine
    from core.engine.provider_server import is_notice

    model = _ailo_config().get().get("node_model") or None
    parts: List[str] = []
    tokens = 0
    for chunk in sigma_engine.generate_stream(
        prompt=prompt, model_name=model, max_tokens=max_tokens, temperature=temperature,
    ):
        if is_notice(chunk):
            continue
        if isinstance(chunk, dict):
            text = chunk.get("token") or chunk.get("content") or ""
        else:
            text = str(chunk or "")
        if text:
            parts.append(text)
            tokens += 1
    return "".join(parts), tokens


def _ailo_gate() -> Tuple[bool, str]:
    """Stessi guard del provider P2P (RAM, priorita' utente locale, concorrenza).

    ``sharing_enabled`` e' forzato a vero: avviare il nodo AiLo e' gia' il
    consenso esplicito a servire quella rete, indipendente dalla condivisione
    verso i peer Sigma.
    """
    if not _is_inference_engine_available():
        return False, "Motore di inferenza Sigma non disponibile"
    settings = {**_get_settings(), "sharing_enabled": True}
    return _provider().can_serve(None, None, settings)


def _ailo_node_state() -> Dict[str, Any]:
    node = _ailo_node_instance
    return node.status() if node else {"running": False, "connected": False}


@router.get("/ailo/config")
def ailo_get_config() -> Dict[str, Any]:
    return _ailo_config().get()


@router.post("/ailo/config")
def ailo_set_config(body: AiloConfigRequest) -> Dict[str, Any]:
    changes = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    return _ailo_config().update(changes)


@router.get("/ailo/status")
def ailo_status() -> Dict[str, Any]:
    """Verifica il server e riassume rete, catena ALC e nodo locale."""
    cfg = _ailo_config().get()
    out: Dict[str, Any] = {
        "configured": bool(cfg["server_url"]), "server_url": cfg["server_url"],
        "wallet": cfg["wallet"], "email": cfg["email"], "node": _ailo_node_state(), "verified": False,
    }
    if not cfg["server_url"]:
        return out
    client = _ailo_client()
    try:
        verified = client.verify_server()
        out.update(verified=True, token=verified["token"], coordinator=verified["status"])
        out["chain"] = client.chain_stats()
        out["network"] = client.network_stats()
    except AiloError as exc:
        out["error"] = str(exc)
    return out


@router.get("/ailo/wallet")
def ailo_wallet() -> Dict[str, Any]:
    cfg = _ailo_config().get()
    if not cfg["wallet"]:
        raise HTTPException(status_code=400, detail="Wallet AiLo non collegato")
    client = _ailo_client()
    balance = _ailo_call(client.balance, cfg["wallet"])
    txs = _ailo_call(client.transactions, cfg["wallet"], 50)
    return {**balance, "transactions": txs, "symbol": "ALC"}


def _ailo_link_account(user: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _ailo_config().update({"wallet": user.get("wallet"), "email": user.get("email")})
    return {"linked": True, "wallet": cfg["wallet"], "email": cfg["email"],
            "balance": user.get("balance", 0)}


@router.post("/ailo/login")
def ailo_login(body: AiloCredentialsRequest) -> Dict[str, Any]:
    client = _ailo_client()
    _ailo_call(client.verify_server)
    return _ailo_link_account(_ailo_call(client.login, body.email, body.password))


@router.post("/ailo/register")
def ailo_register(body: AiloCredentialsRequest) -> Dict[str, Any]:
    client = _ailo_client()
    _ailo_call(client.verify_server)
    return _ailo_link_account(_ailo_call(client.register, body.email, body.password))


@router.post("/ailo/transfer")
def ailo_transfer(body: AiloTransferRequest) -> Dict[str, Any]:
    cfg = _ailo_config().get()
    if not cfg["email"]:
        raise HTTPException(status_code=400, detail="Account AiLo non collegato")
    return _ailo_call(_ailo_client().transfer, cfg["email"], body.to_wallet, body.amount, body.password)


@router.post("/ailo/infer")
def ailo_infer(body: AiloInferRequest) -> Dict[str, Any]:
    """Inferenza distribuita sulla rete AiLo (nodi GPU remoti o modello Fused)."""
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt vuoto")
    max_tokens = max(1, min(int(body.max_tokens or 200), 4096))
    return _ailo_call(_ailo_client().infer, body.prompt, max_tokens,
                      float(body.temperature or 0.8), body.backend or "gpu")


@router.post("/ailo/node/start")
def ailo_node_start() -> Dict[str, Any]:
    """Mette questo PC nella rete AiLo come nodo di inferenza che guadagna ALC."""
    global _ailo_node_instance
    cfg = _ailo_config().get()
    if not cfg["server_url"] or not cfg["wallet"]:
        raise HTTPException(status_code=400, detail="Configura server e wallet AiLo prima di avviare il nodo")
    _ailo_call(_ailo_client().verify_server)
    with _lock:
        node = _ailo_node_instance
        if node is not None and (node.wallet != cfg["wallet"] or node.max_tokens != cfg["node_max_tokens"]):
            node.stop()
            node = None
        if node is None:
            node = AiloInferenceNode(
                server_url=cfg["server_url"], wallet=cfg["wallet"], email=cfg["email"],
                generate_fn=_ailo_generate, gate_fn=_ailo_gate,
                max_tokens=cfg["node_max_tokens"], gpu_label=cfg["gpu_label"] or "Sigma Studio",
            )
            _ailo_node_instance = node
        node.start()
    _ailo_config().update({"node_enabled": True})
    return node.status()


@router.post("/ailo/node/stop")
def ailo_node_stop() -> Dict[str, Any]:
    node = _ailo_node_instance
    if node is not None:
        node.stop()
    _ailo_config().update({"node_enabled": False})
    return _ailo_node_state()


@router.get("/ailo/node/status")
def ailo_node_status() -> Dict[str, Any]:
    return _ailo_node_state()


def _reset_ailo_singletons() -> None:
    """Ferma il nodo AiLo e scorda la configurazione (usata dai test)."""
    global _ailo_config_instance, _ailo_node_instance
    with _lock:
        if _ailo_node_instance is not None:
            _ailo_node_instance.stop()
        _ailo_config_instance = None
        _ailo_node_instance = None
    # Definita piu' in basso: a runtime esiste sempre.
    _reset_ailo_hub_singletons()


# ==============================================================================
# Hub AiLo nativo — l'infrastruttura AiLo ospitata da Sigma Studio
# ==============================================================================
# Il coordinatore AiLo originale e' dismesso: queste route ne riproducono le API
# sotto /api/sigma_network/ailo_hub, cosi' il bridge (e qualunque client AiLo)
# usa come server l'URL di un'istanza Sigma con l'hub attivo.

from fastapi import Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from core.modules.sigma_network.ailo_hub import (  # noqa: E402
    TOKEN_SCHEMA,
    AiloLedger,
    AiloNodeHub,
    LedgerError,
    MIN_LEDGER_FEE,
)

HUB_PREFIX = "/ailo_hub"
_ailo_hub_db_file: Optional[str] = None
_ailo_ledger_instance: Optional[AiloLedger] = None
_ailo_node_hub_instance: Optional[AiloNodeHub] = None

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _ailo_ledger() -> AiloLedger:
    global _ailo_ledger_instance
    with _lock:
        if _ailo_ledger_instance is None:
            _ailo_ledger_instance = AiloLedger(_ailo_hub_db_file or _default_path("ailo_hub.db"))
        return _ailo_ledger_instance


def _ailo_node_hub() -> AiloNodeHub:
    global _ailo_node_hub_instance
    with _lock:
        if _ailo_node_hub_instance is None:
            _ailo_node_hub_instance = AiloNodeHub(_ailo_ledger())
        return _ailo_node_hub_instance


def _hub_enabled() -> bool:
    return bool(_ailo_config().get().get("hub_enabled"))


def _hub_off() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "Hub AiLo non attivo su questa istanza"})


def _hub_error(exc: LedgerError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"success": False, "error": str(exc)})


def _is_local(request: Request) -> bool:
    """I comandi di amministrazione dell'hub si danno solo da questa macchina."""
    return bool(request.client and request.client.host in _LOOPBACK)


async def _json_body(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


# --- API pubbliche compatibili con il coordinatore AiLo ---------------------

@router.get(HUB_PREFIX + "/api/status")
def hub_status() -> Any:
    if not _hub_enabled():
        return _hub_off()
    nodes = _ailo_node_hub().nodes()
    return {"activeNodes": len(nodes), "globalHashrate": 0, "globalModelVersion": 1,
            "isNetworkActive": True, "hub": "sigma-network", "hubVersion": MODULE_VERSION}


@router.get(HUB_PREFIX + "/api/network-stats")
def hub_network_stats() -> Any:
    if not _hub_enabled():
        return _hub_off()
    nodes = _ailo_node_hub().nodes()
    return {"totalNodes": len(nodes), "trainingNodes": 0, "inferenceNodes": len(nodes),
            "globalHashrate": 0, "models": {"total": 0, "available": 0, "comingSoon": 0, "list": []}}


@router.get(HUB_PREFIX + "/api/nodes")
def hub_nodes() -> Any:
    if not _hub_enabled():
        return _hub_off()
    return _ailo_node_hub().nodes()


@router.get(HUB_PREFIX + "/api/v1/token")
def hub_token() -> Any:
    return TOKEN_SCHEMA if _hub_enabled() else _hub_off()


@router.get(HUB_PREFIX + "/api/balance/{wallet}")
def hub_balance(wallet: str) -> Any:
    if not _hub_enabled():
        return _hub_off()
    return _ailo_ledger().balance(wallet)


@router.post(HUB_PREFIX + "/api/register")
async def hub_register(request: Request) -> Any:
    if not _hub_enabled():
        return _hub_off()
    body = await _json_body(request)
    try:
        return {"user": _ailo_ledger().register(str(body.get("email") or ""), body.get("password"))}
    except LedgerError as exc:
        return _hub_error(exc)


@router.post(HUB_PREFIX + "/api/login")
async def hub_login(request: Request) -> Any:
    if not _hub_enabled():
        return _hub_off()
    body = await _json_body(request)
    try:
        return {"user": _ailo_ledger().login(str(body.get("email") or ""), body.get("password"))}
    except LedgerError as exc:
        return _hub_error(exc)


@router.post(HUB_PREFIX + "/api/transfer")
async def hub_transfer(request: Request) -> Any:
    if not _hub_enabled():
        return _hub_off()
    body = await _json_body(request)
    try:
        return _ailo_ledger().transfer(str(body.get("fromEmail") or ""), str(body.get("toWallet") or ""),
                                       body.get("amount"), body.get("password"))
    except LedgerError as exc:
        return _hub_error(exc)


@router.post(HUB_PREFIX + "/api/ledger/transfer")
async def hub_ledger_transfer(request: Request) -> Any:
    """Variante del wallet web: mittente per wallet o email, commissione minima."""
    if not _hub_enabled():
        return _hub_off()
    body = await _json_body(request)
    try:
        fee = max(float(body.get("fee") or MIN_LEDGER_FEE), MIN_LEDGER_FEE)
    except (TypeError, ValueError):
        fee = MIN_LEDGER_FEE
    try:
        return _ailo_ledger().transfer(str(body.get("from") or ""), str(body.get("to") or ""),
                                       body.get("amount"), body.get("password"), fee=fee,
                                       note=str(body.get("note") or ""))
    except LedgerError as exc:
        return _hub_error(exc)


@router.post(HUB_PREFIX + "/api/v1/rpc")
async def hub_rpc(request: Request) -> Any:
    """JSON-RPC 2.0 con i metodi alc_* dell'AiloCoin SDK."""
    if not _hub_enabled():
        return _hub_off()
    body = await _json_body(request)
    rpc_id = body.get("id")
    if body.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request - must be JSON-RPC 2.0"}, "id": rpc_id}
    params = body.get("params") or []
    ledger = _ailo_ledger()

    def need(i: int) -> Any:
        if len(params) <= i or not params[i]:
            raise LedgerError("Invalid params", -32602)
        return params[i]

    try:
        method = body.get("method")
        if method == "alc_getBalance":
            result: Any = ledger.balance(str(need(0)))["balance"]
        elif method == "alc_getTransaction":
            result = ledger.transaction(str(need(0)))
            if result is None:
                raise LedgerError("Transaction not found", -32602)
        elif method == "alc_getTransactionsByAddress":
            result = ledger.transactions(str(need(0)), int(params[1]) if len(params) > 1 else 50)
        elif method == "alc_getBlockNumber":
            result = ledger.stats()["blockNumber"]
        elif method == "alc_getTotalSupply":
            result = ledger.stats()["totalSupply"]
        elif method == "alc_getNetworkStats":
            result = ledger.stats()
        elif method == "alc_getTokenInfo":
            result = TOKEN_SCHEMA
        else:
            raise LedgerError(f"Method not found: {method}", -32601)
    except LedgerError as exc:
        return {"jsonrpc": "2.0", "error": {"code": exc.status, "message": str(exc)}, "id": rpc_id}
    except (TypeError, ValueError) as exc:
        return {"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Invalid params: {exc}"}, "id": rpc_id}
    return {"jsonrpc": "2.0", "result": result, "id": rpc_id}


def _hub_infer_args(body: Dict[str, Any]) -> Tuple[str, int, float]:
    prompt = str(body.get("prompt") or "")
    try:
        max_tokens = max(1, min(int(body.get("max_tokens") or 100), 4096))
    except (TypeError, ValueError):
        max_tokens = 100
    try:
        temperature = float(body.get("temperature", 0.8))
    except (TypeError, ValueError):
        temperature = 0.8
    return prompt, max_tokens, temperature


@router.post(HUB_PREFIX + "/api/inference/gpu")
async def hub_inference_gpu(request: Request) -> Any:
    """Smista la richiesta al nodo GPU libero usato meno di recente."""
    if not _hub_enabled():
        return _hub_off()
    prompt, max_tokens, temperature = _hub_infer_args(await _json_body(request))
    if not prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt required"})
    return await _ailo_node_hub().dispatch(prompt, max_tokens, temperature)


@router.post(HUB_PREFIX + "/api/inference/fused")
async def hub_inference_fused(request: Request) -> Any:
    """Il modello "fused" dell'hub e' il motore locale di questa istanza."""
    if not _hub_enabled():
        return _hub_off()
    prompt, max_tokens, temperature = _hub_infer_args(await _json_body(request))
    if not prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt required"})
    if not _is_inference_engine_available():
        return {"success": False, "error": "Motore dell'hub non disponibile", "model": "AILO-Fused",
                "response": "[AILO Fused] Nessun modello caricato sull'hub."}
    started = time.monotonic()
    try:
        loop = asyncio.get_running_loop()
        text, tokens = await loop.run_in_executor(None, _ailo_generate, prompt, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001 - l'errore torna al chiamante
        log.warning("Inferenza fused fallita: %s", exc)
        return {"success": False, "error": str(exc), "model": "AILO-Fused"}
    return {"success": True, "prompt": prompt, "response": text, "tokens_generated": tokens,
            "model": "AILO-Fused", "backend": "sigma-hub", "latency_ms": int((time.monotonic() - started) * 1000)}


@router.websocket(HUB_PREFIX + "/ws/gpu-inference")
async def hub_gpu_inference_ws(websocket: WebSocket) -> None:
    """Endpoint dei nodi di inferenza (protocollo del client CUDA AiLo)."""
    if not _hub_enabled():
        await websocket.close(code=1008)
        return
    await websocket.accept()
    hub = _ailo_node_hub()
    node_id = hub.connect(websocket)
    try:
        while True:
            await hub.handle_message(node_id, await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - un nodo guasto non deve toccare gli altri
        log.warning("Nodo AiLo %s scollegato per errore: %s", node_id, exc)
    finally:
        hub.disconnect(node_id)


# --- Amministrazione locale dell'hub -----------------------------------------

def _local_hub_url() -> str:
    scheme = "http"
    try:
        from sigma_server import _get_configured_host_port_ssl

        scheme = "https" if _get_configured_host_port_ssl()[2] else "http"
    except Exception as exc:  # noqa: BLE001 - senza config si assume http
        log.debug("Config server non leggibile: %s", exc)
    return f"{scheme}://127.0.0.1:{_detect_server_port()}/api/sigma_network{HUB_PREFIX}"


@router.get("/ailo/hub/status")
def ailo_hub_admin_status() -> Dict[str, Any]:
    enabled = _hub_enabled()
    out: Dict[str, Any] = {"enabled": enabled, "local_url": _local_hub_url()}
    if enabled:
        out["ledger"] = _ailo_ledger().stats()
        out["nodes"] = _ailo_node_hub().nodes()
    return out


class AiloHubToggleRequest(BaseModel):
    enabled: bool


@router.post("/ailo/hub/enable")
def ailo_hub_enable(body: AiloHubToggleRequest, request: Request) -> Dict[str, Any]:
    if not _is_local(request):
        raise HTTPException(status_code=403, detail="Solo da questa macchina")
    _ailo_config().update({"hub_enabled": bool(body.enabled)})
    return ailo_hub_admin_status()


@router.post("/ailo/hub/use_local")
def ailo_hub_use_local(request: Request) -> Dict[str, Any]:
    """Collega il bridge all'hub di questa stessa istanza."""
    if not _is_local(request):
        raise HTTPException(status_code=403, detail="Solo da questa macchina")
    if not _hub_enabled():
        raise HTTPException(status_code=400, detail="Attiva prima l'hub AiLo")
    return _ailo_config().update({"server_url": _local_hub_url()})


class AiloHubImportRequest(BaseModel):
    path: str


@router.post("/ailo/hub/import")
def ailo_hub_import(body: AiloHubImportRequest, request: Request) -> Dict[str, Any]:
    """Migra account, saldi e storico da un ailo.db del vecchio coordinatore."""
    if not _is_local(request):
        raise HTTPException(status_code=403, detail="Solo da questa macchina")
    try:
        return _ailo_ledger().import_ailo_db(body.path)
    except LedgerError as exc:
        raise HTTPException(status_code=exc.status if exc.status >= 400 else 400, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=400, detail=f"Database non leggibile: {exc}") from exc


def _reset_ailo_hub_singletons() -> None:
    global _ailo_ledger_instance, _ailo_node_hub_instance
    with _lock:
        if _ailo_ledger_instance is not None:
            _ailo_ledger_instance.close()
        _ailo_ledger_instance = None
        _ailo_node_hub_instance = None
