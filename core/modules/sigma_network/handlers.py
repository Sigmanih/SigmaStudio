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

import base64
import json
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
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

router = APIRouter()

MODULE_VERSION = "0.2.0"

#: Percorsi di persistenza. Riassegnabili dai test prima di ``_reset_singletons``.
_identity_file: Optional[str] = None
_peers_file: Optional[str] = None
_wallet_file: Optional[str] = None
_auth_file: Optional[str] = None

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
        _broker_instance = None
        _mining_instance = None
        _aggregator_instance = None
        _auth_instance = None
        _provider_instance = None
        _current_session_token = None


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
            _settings = dict(DEFAULT_SETTINGS)
        return _settings


def _detect_server_port() -> int:
    try:
        from sigma_server import _get_configured_host_port_ssl
        _, port, _, _, _ = _get_configured_host_port_ssl()
        return port or 8000
    except Exception:
        return 8000


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
    """Aggiorna le impostazioni e diffonde immediatamente l'annuncio UDP broadcast se attivo."""
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    with _lock:
        current = _get_settings()
        current.update(changes)
        res = dict(current)

    # Annuncio gossip/UDP immediato se discovery è attiva
    try:
        disc = _discovery_instance
        if disc and getattr(disc, "is_running", lambda: False)():
            disc.announce_now()
    except Exception:
        pass

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

    Nome, versione e modelli non stanno nell'identita: l'identita e' la coppia
    di chiavi e non cambia mai, mentre questi sono impostazioni che l'utente
    modifica. Leggerli dal posto sbagliato li restituiva vuoti, e un peer senza
    nome ne' modelli e' indistinguibile da uno che non condivide nulla.
    """
    identity = _get_identity()
    settings = _get_settings()
    return {
        "peer_id": identity["peer_id"],
        "name": str(settings.get("display_name") or "Sigma Peer"),
        "version": MODULE_VERSION,
        "models": list(settings.get("shared_models") or []),
        "accepting": bool(settings.get("sharing_enabled")),
    }


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




