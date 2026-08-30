"""Test del modulo Sigma Network — Task 1: identita crittografica del peer.

Task 2: registro dei peer (PeerRegistry).
Task 3: contabilita AiloCoin (Wallet).
Task 4: provider e broker di inferenza.
Task 5: scoperta dei peer (PeerDiscovery).
"""

from __future__ import annotations

import base64
import json

import pytest

from core.modules.sigma_network.ailocoin import Wallet
from core.modules.sigma_network.identity import (
    generate_identity,
    load_identity,
    peer_id_from_public_key,
    public_identity,
    sign,
    verify,
)
from core.modules.sigma_network.peer_registry import PeerRegistry
from core.modules.sigma_network.provider import InferenceProvider
from core.modules.sigma_network.inference_broker import InferenceBroker
from core.modules.sigma_network.discovery import PeerDiscovery


def test_peer_id_stabile_fra_due_caricamenti(tmp_path):
    """Il peer_id deve essere identico fra due caricamenti consecutivi."""
    identity_file = tmp_path / "identity.json"

    first = load_identity(str(identity_file))
    second = load_identity(str(identity_file))

    assert first["peer_id"] == second["peer_id"]
    # La chiave pubblica deve essere la stessa (stessa identita).
    assert first["public_key"] == second["public_key"]


def test_firma_valida_verifica_correttamente(tmp_path):
    """Una firma valida deve verificare correttamente."""
    identity = generate_identity(str(tmp_path / "identity.json"))

    message = "messaggio di prova per Sigma Network"
    private_key_bytes = base64.b64decode(identity["private_key"])
    signature_b64 = sign(private_key_bytes, message)

    assert verify(identity["public_key"], message, signature_b64) is True


def test_firma_manomessa_viene_rifiutata(tmp_path):
    """Una firma su un messaggio diverso deve essere rifiutata."""
    identity = generate_identity(str(tmp_path / "identity.json"))

    original_message = "messaggio originale"
    tampered_message = "messaggio manomesso"

    private_key_bytes = base64.b64decode(identity["private_key"])
    signature_b64 = sign(private_key_bytes, original_message)

    # La firma dell'originale non deve verificare sul messaggio manomesso.
    assert verify(identity["public_key"], tampered_message, signature_b64) is False


def test_firma_malformata_restituisce_false(tmp_path):
    """Una firma malformata deve restituire False senza sollevare eccezioni."""
    identity = generate_identity(str(tmp_path / "identity.json"))

    message = "qualunque messaggio"

    # Firma non decodificabile come base64 valido.
    assert verify(identity["public_key"], message, "!!!non-base64!!!") is False

    # Base64 valido ma byte non validi come firma Ed25519 (lunghezza errata).
    bad_signature_b64 = base64.b64encode(b"firma-troppo-corta").decode("ascii")
    assert verify(identity["public_key"], message, bad_signature_b64) is False

    # Chiave pubblica malformata.
    valid_sig = sign(
        base64.b64decode(identity["private_key"]), message
    )
    bad_public_b64 = base64.b64encode(b"chiave-pubblica-invalida").decode("ascii")
    assert verify(bad_public_b64, message, valid_sig) is False


def test_identita_pubblica_non_contiene_chiave_privata(tmp_path):
    """L'identita pubblica non deve mai contenere la chiave privata."""
    identity = generate_identity(str(tmp_path / "identity.json"))

    public = public_identity(identity)

    assert "private_key" not in public
    assert "public_key" in public
    assert "peer_id" in public


def test_peer_id_formato_hex_32_caratteri(tmp_path):
    """Il peer_id deve essere una stringa hex di 32 caratteri (16 byte)."""
    identity = generate_identity(str(tmp_path / "identity.json"))

    peer_id = identity["peer_id"]
    assert len(peer_id) == 32
    # Deve essere esadecimale valido.
    int(peer_id, 16)


# ---------------------------------------------------------------------------
# Task 2 — PeerRegistry
# ---------------------------------------------------------------------------


def _make_registry(tmp_path):
    return PeerRegistry(str(tmp_path / "peers.json"))


def test_peer_registry_roundtrip_persistenza(tmp_path):
    """Salva, ricarica: i peer devono coincidere."""
    reg = _make_registry(tmp_path)
    reg.add_peer(
        host="10.0.0.1",
        port=8443,
        peer_id="a" * 32,
        public_key="pubkey-aaa",
        name="alpha",
        models=["llama-7b", "whisper"],
    )
    reg.add_peer(
        host="10.0.0.2",
        port=9000,
        peer_id="b" * 32,
        public_key="pubkey-bbb",
        name="beta",
        models=["llama-70b"],
    )
    reg.set_state("a" * 32, "trusted")
    reg.touch("b" * 32, latency_ms=42)
    reg.save()

    # Ricarica da zero.
    reg2 = PeerRegistry(str(tmp_path / "peers.json"))
    reg2.load()

    assert {p["peer_id"] for p in reg2.all_peers()} == {"a" * 32, "b" * 32}
    pa = reg2.get("a" * 32)
    pb = reg2.get("b" * 32)
    assert pa["host"] == "10.0.0.1"
    assert pa["port"] == 8443
    assert pa["name"] == "alpha"
    assert pa["models"] == ["llama-7b", "whisper"]
    assert pa["state"] == "trusted"
    assert pb["state"] == "discovered"
    assert pb["latency_ms"] == 42


def test_peer_registry_rifiuta_stato_non_valido(tmp_path):
    """set_state con uno stato non valido deve sollevare ValueError."""
    reg = _make_registry(tmp_path)
    reg.add_peer(
        host="10.0.0.9",
        port=1234,
        peer_id="c" * 32,
        public_key="pk",
        name="gamma",
        models=[],
    )
    with pytest.raises(ValueError):
        reg.set_state("c" * 32, "unknown_state")


def test_peer_registry_trusted_peers_esclude_discovered_e_blocked(tmp_path):
    """trusted_peers() deve restituire solo i peer in stato trusted."""
    reg = _make_registry(tmp_path)
    for pid, state in [("d" * 32, "discovered"), ("e" * 32, "trusted"), ("f" * 32, "blocked")]:
        reg.add_peer(
            host="10.0.0.1",
            port=80,
            peer_id=pid,
            public_key=f"pk-{pid[:4]}",
            name=pid[:4],
            models=[],
        )
        reg.set_state(pid, state)

    trusted = reg.trusted_peers()
    assert {p["peer_id"] for p in trusted} == {"e" * 32}


def test_peer_registry_file_corrotto_non_esplode(tmp_path):
    """Un file peers.json corrotto non deve far esplodere load()."""
    peers_file = tmp_path / "peers.json"
    peers_file.write_text("{ questo non e JSON valido !!!", encoding="utf-8")

    reg = PeerRegistry(str(peers_file))
    # Non deve sollevare eccezioni.
    reg.load()

    assert reg.all_peers() == []


# ---------------------------------------------------------------------------
# Task 3 — Wallet / AiloCoin
# ---------------------------------------------------------------------------


def _make_wallet(tmp_path):
    return Wallet(str(tmp_path / "wallet.json"))


def _identities(tmp_path, n=2):
    """Genera ``n`` identita distinte e le restituisce come lista."""
    out = []
    for i in range(n):
        out.append(generate_identity(str(tmp_path / f"id-{i}.json")))
    return out


def test_ricevuta_emessa_e_controfirmata_verifica(tmp_path):
    """Una ricevuta emessa dal provider e controfirmata dal consumer deve verificare."""
    wallet = _make_wallet(tmp_path)
    provider, consumer = _identities(tmp_path, 2)

    priv_p = base64.b64decode(provider["private_key"])
    priv_c = base64.b64decode(consumer["private_key"])

    receipt = wallet.issue_receipt(
        request_id="req-1",
        provider_id=provider["peer_id"],
        consumer_id=consumer["peer_id"],
        model="Qwen/Qwen3.8-27B-GGUF-Q4_K_S",
        tokens=1450,
        rate=1000,
        private_key_bytes=priv_p,
    )

    # Firma provider presente e valida.
    assert receipt["provider_signature"] is not None
    assert receipt["consumer_signature"] is None
    assert receipt["amount"] == pytest.approx(1.45)

    # Il consumer controfirma.
    countersigned = wallet.countersign(receipt, priv_c)
    assert countersigned["consumer_signature"] is not None

    # Verifica completa: entrambe le firme valide.
    assert wallet.verify_receipt(
        countersigned,
        provider["public_key"],
        consumer["public_key"],
    ) is True


def test_ricevuta_con_importo_alterato_non_verifica(tmp_path):
    """Se l'importo viene alterato dopo la firma, la verifica deve fallire."""
    wallet = _make_wallet(tmp_path)
    provider, consumer = _identities(tmp_path, 2)

    priv_p = base64.b64decode(provider["private_key"])
    priv_c = base64.b64decode(consumer["private_key"])

    receipt = wallet.issue_receipt(
        request_id="req-2",
        provider_id=provider["peer_id"],
        consumer_id=consumer["peer_id"],
        model="Qwen/Qwen3.8-27B-GGUF-Q4_K_S",
        tokens=1000,
        rate=1000,
        private_key_bytes=priv_p,
    )
    countersigned = wallet.countersign(receipt, priv_c)

    # Tampering: cambio l'importo.
    tampered = dict(countersigned)
    tampered["amount"] = 99.0

    assert wallet.verify_receipt(
        tampered,
        provider["public_key"],
        consumer["public_key"],
    ) is False


def test_balance_calcola_guadagni_spese_e_saldo(tmp_path):
    """balance() deve sommare earned (provider) e spent (consumer)."""
    wallet = _make_wallet(tmp_path)
    a, b, c = _identities(tmp_path, 3)

    priv_a = base64.b64decode(a["private_key"])
    priv_b = base64.b64decode(b["private_key"])
    priv_c = base64.b64decode(c["private_key"])

    # A fornisce 2000 token a B (rate 1000 -> 2.0 coin): A guadagna, B spende.
    r1 = wallet.issue_receipt(
        request_id="r1",
        provider_id=a["peer_id"],
        consumer_id=b["peer_id"],
        model="m1",
        tokens=2000,
        rate=1000,
        private_key_bytes=priv_a,
    )
    wallet.countersign(r1, priv_b)

    # B fornisce 500 token a C (rate 1000 -> 0.5 coin): B guadagna, C spende.
    r2 = wallet.issue_receipt(
        request_id="r2",
        provider_id=b["peer_id"],
        consumer_id=c["peer_id"],
        model="m2",
        tokens=500,
        rate=1000,
        private_key_bytes=priv_b,
    )
    wallet.countersign(r2, priv_c)

    # A: earned 2.0, spent 0, balance 2.0
    bal_a = wallet.balance(a["peer_id"])
    assert bal_a["earned"] == pytest.approx(2.0)
    assert bal_a["spent"] == pytest.approx(0.0)
    assert bal_a["balance"] == pytest.approx(2.0)

    # B: earned 0.5, spent 2.0, balance -1.5
    bal_b = wallet.balance(b["peer_id"])
    assert bal_b["earned"] == pytest.approx(0.5)
    assert bal_b["spent"] == pytest.approx(2.0)
    assert bal_b["balance"] == pytest.approx(-1.5)

    # C: earned 0, spent 0.5, balance -0.5
    bal_c = wallet.balance(c["peer_id"])
    assert bal_c["earned"] == pytest.approx(0.0)
    assert bal_c["spent"] == pytest.approx(0.5)
    assert bal_c["balance"] == pytest.approx(-0.5)


def test_controfirma_rifiuta_se_firma_provider_non_valida(tmp_path):
    """countersign() deve rifiutare se la firma del provider non e valida."""
    wallet = _make_wallet(tmp_path)
    provider, consumer = _identities(tmp_path, 2)

    priv_p = base64.b64decode(provider["private_key"])
    priv_c = base64.b64decode(consumer["private_key"])

    receipt = wallet.issue_receipt(
        request_id="r3",
        provider_id=provider["peer_id"],
        consumer_id=consumer["peer_id"],
        model="m3",
        tokens=100,
        rate=1000,
        private_key_bytes=priv_p,
    )

    # Tampering: altero i token dopo la firma del provider.
    tampered = dict(receipt)
    tampered["tokens"] = 9999

    with pytest.raises(ValueError):
        wallet.countersign(tampered, priv_c, provider_public_key=provider["public_key"])


# ---------------------------------------------------------------------------
# Task 4 — InferenceProvider e InferenceBroker
# ---------------------------------------------------------------------------


def _settings(**overrides):
    base = {
        "sharing_enabled": True,
        "max_concurrent_requests": 2,
        "hourly_token_limit": 100_000,
        "max_tokens_per_request": 512,
        "shared_models": ["llama-7b", "qwen-27b"],
    }
    base.update(overrides)
    return base


def _registry_with(peer_id, state):
    reg = PeerRegistry.__new__(PeerRegistry)
    reg._peers = {peer_id: {"peer_id": peer_id, "state": state}}
    return reg


def test_can_serve_rifiuta_peer_non_trusted():
    provider = InferenceProvider()
    registry = _registry_with("a" * 32, "discovered")
    settings = _settings()

    ok, reason = provider.can_serve("a" * 32, registry, settings)
    assert ok is False
    assert "trusted" in reason.lower() or "non" in reason.lower()



def test_can_serve_rifiuta_se_sharing_disattivato():
    provider = InferenceProvider()
    registry = _registry_with("a" * 32, "trusted")
    settings = _settings(sharing_enabled=False)

    ok, reason = provider.can_serve("a" * 32, registry, settings)
    assert ok is False
    assert "sharing" in reason.lower() or "disattivato" in reason.lower()


def test_clamp_request_riduce_max_tokens_eccessivo():
    provider = InferenceProvider()
    settings = _settings(max_tokens_per_request=256)

    payload, ok = provider.clamp_request(
        {"prompt": "ciao", "model": "llama-7b", "max_tokens": 9999},
        settings,
    )
    assert ok is True
    assert payload["max_tokens"] == 256


def test_clamp_request_rifiuta_modello_non_condiviso():
    provider = InferenceProvider()
    settings = _settings(shared_models=["llama-7b"])

    _, ok = provider.clamp_request(
        {"prompt": "ciao", "model": "gpt-4", "max_tokens": 100},
        settings,
    )
    assert ok is False


def test_broker_peer_irraggiungibile_restituisce_evento_errore(monkeypatch):
    import requests as _requests

    broker = InferenceBroker()

    def _raise(*args, **kwargs):
        raise _requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(broker._session, "post", _raise)

    peer = {"host": "127.0.0.1", "port": 9999}
    identity = {"peer_id": "a" * 32, "private_key": "b64key"}

    events = list(broker.request_inference(peer, "prompt", "llama-7b", 100, identity))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "error" in events[0]


# ---------------------------------------------------------------------------
# Task 5 — PeerDiscovery (senza socket reali)
# ---------------------------------------------------------------------------


class _FakeRegistry:
    """Registro finto che registra i peer chiamati da PeerDiscovery."""

    def __init__(self):
        self.registered = []

    def register(self, **kwargs):
        self.registered.append(kwargs)


def test_discovery_parsa_annuncio_valido():
    """parse_announcement() su un JSON valido restituisce i campi attesi."""
    text = json.dumps({
        "peer_id": "f" * 32,
        "name": "remote-peer",
        "port": 9000,
        "models": ["llama-7b"],
        "version": "1.2.3",
    })

    parsed = PeerDiscovery.parse_announcement(text)

    assert parsed is not None
    assert parsed["peer_id"] == "f" * 32
    assert parsed["name"] == "remote-peer"
    assert parsed["port"] == 9000
    assert parsed["models"] == ["llama-7b"]
    assert parsed["version"] == "1.2.3"


def test_discovery_annuncio_malformato_ignorato():
    """parse_announcement() su testo non JSON restituisce None senza sollevare."""
    assert PeerDiscovery.parse_announcement("{ questo non e JSON !!!") is None
    assert PeerDiscovery.parse_announcement("") is None
    assert PeerDiscovery.parse_announcement("[1,2,3]") is None  # non un oggetto
    assert PeerDiscovery.parse_announcement(json.dumps({"name": "no-peer-id"})) is None


def test_discovery_ignora_proprio_annuncio():
    """Un annuncio con lo stesso peer_id del locale non viene registrato."""
    reg = _FakeRegistry()
    discovery = PeerDiscovery(
        registry=reg,
        peer_id="a" * 32,
        name="local",
        port=8080,
        models=["llama-7b"],
        version="1.0.0",
    )

    own_announcement = json.dumps({
        "peer_id": "a" * 32,
        "name": "local",
        "port": 8080,
        "models": ["llama-7b"],
        "version": "1.0.0",
    }).encode("utf-8")

    discovery._handle_announcement(own_announcement, ("127.0.0.1", 47777))

    assert reg.registered == []


def test_discovery_registra_peer_remoto():
    """Un annuncio di un peer diverso viene registrato nel registry."""
    reg = _FakeRegistry()
    discovery = PeerDiscovery(
        registry=reg,
        peer_id="a" * 32,
        name="local",
        port=8080,
        models=["llama-7b"],
        version="1.0.0",
    )

    remote = json.dumps({
        "peer_id": "b" * 32,
        "name": "remote",
        "port": 9000,
        "models": ["qwen-27b"],
        "version": "1.1.0",
    }).encode("utf-8")

    discovery._handle_announcement(remote, ("10.0.0.5", 47777))

    assert len(reg.registered) == 1
    entry = reg.registered[0]
    assert entry["peer_id"] == "b" * 32
    assert entry["host"] == "10.0.0.5"
    assert entry["port"] == 9000
    assert entry["name"] == "remote"
    assert entry["models"] == ["qwen-27b"]
    assert entry["version"] == "1.1.0"


def test_discovery_is_running_inizialmente_falso():
    """is_running() deve essere False prima di start()."""
    reg = _FakeRegistry()
    discovery = PeerDiscovery(registry=reg, peer_id="a" * 32)
    assert discovery.is_running() is False


# ---------------------------------------------------------------------------
# Task 6a — Route HTTP locali (handlers.py)
# ---------------------------------------------------------------------------

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.modules.sigma_network.handlers import router, _reset_singletons
from core.modules.sigma_network.identity import generate_identity
from core.modules.sigma_network.peer_registry import PeerRegistry


def _make_client(tmp_path):
    """Costruisce un TestClient sul solo router, con singletons puntati su tmp_path."""
    _reset_singletons()
    # Puntiamo i singletons su file in tmp_path.
    import core.modules.sigma_network.handlers as h
    h._identity_file = str(tmp_path / "identity.json")
    h._peers_file = str(tmp_path / "peers.json")
    h._wallet_file = str(tmp_path / "wallet.json")
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_identity_non_espone_chiave_privata(tmp_path):
    """GET /identity non deve mai restituire private_key."""
    client = _make_client(tmp_path)
    resp = client.get("/identity")
    assert resp.status_code == 200
    body = resp.json()
    assert "private_key" not in body
    assert "peer_id" in body
    assert "public_key" in body
    assert "name" in body
    assert "version" in body


def test_peers_trust_cambia_stato(tmp_path):
    """POST /peers/trust deve cambiare lo stato del peer."""
    client = _make_client(tmp_path)

    # Aggiungi un peer.
    resp = client.post("/peers/add", json={"host": "10.0.0.1", "port": 8443})
    assert resp.status_code == 200
    peer_id = resp.json()["peer_id"]

    # Verifica che sia discovered.
    resp = client.get("/peers")
    peers = resp.json()
    target = next(p for p in peers if p["peer_id"] == peer_id)
    assert target["state"] == "discovered"

    # Mettilo in trusted.
    resp = client.post("/peers/trust", json={"peer_id": peer_id, "trusted": True})
    assert resp.status_code == 200

    # Verifica che ora sia trusted.
    resp = client.get("/peers")
    peers = resp.json()
    target = next(p for p in peers if p["peer_id"] == peer_id)
    assert target["state"] == "trusted"


def test_delete_peer_inesistente_404(tmp_path):
    """DELETE /peers/{peer_id} su un peer inesistente deve rispondere 404."""
    client = _make_client(tmp_path)
    resp = client.delete("/peers/" + "z" * 32)
    assert resp.status_code == 404



# ---------------------------------------------------------------------------
# TASK 6b — Test route peer-to-peer
# ---------------------------------------------------------------------------
import base64
from unittest.mock import patch, MagicMock



# ---------------------------------------------------------------------------
# Task 6b — Route peer-to-peer
# ---------------------------------------------------------------------------
# La verifica della firma e' l'unico controllo che distingue un peer dal resto
# di internet, ed era il punto in cui il codice generato sbagliava: confrontava
# la firma del chiamante con la chiave pubblica di QUESTO nodo, cioe' non
# verificava nulla di attribuibile al mittente. Questi test fissano l'ordine
# corretto — prima si stabilisce chi parla, poi si verifica con la sua chiave.

import base64 as _base64

from core.modules.sigma_network.identity import sign as _sign


def _peer_client(tmp_path):
    """TestClient sul router, con i singleton isolati in tmp_path."""
    import core.modules.sigma_network.handlers as h

    h._reset_singletons()
    h._identity_file = str(tmp_path / "identity.json")
    h._peers_file = str(tmp_path / "peers.json")
    h._wallet_file = str(tmp_path / "wallet.json")
    app = FastAPI()
    app.include_router(h.router)
    return TestClient(app), h


def _peer_firmatario(tmp_path, nome="altro"):
    """Un peer esterno con identita' propria e un messaggio gia' firmato."""
    identita = generate_identity(str(tmp_path / f"{nome}.json"))
    messaggio = "richiesta-di-inferenza"
    firma = _sign(_base64.b64decode(identita["private_key"]), messaggio)
    return identita, messaggio, firma


def test_p2p_hello_espone_identita_e_impostazioni(tmp_path):
    """Nome, versione e modelli vengono dalle impostazioni, non dall'identita."""
    client, _ = _peer_client(tmp_path)
    body = client.get("/p2p/hello").json()

    assert body["peer_id"]
    assert body["name"]
    assert body["version"]
    assert "private_key" not in body
    assert body["accepting"] is False


def test_p2p_infer_senza_firma_401(tmp_path):
    client, _ = _peer_client(tmp_path)
    assert client.post("/p2p/infer", json={"peer_id": "x" * 32}).status_code == 401


def test_p2p_infer_peer_sconosciuto_401(tmp_path):
    client, _ = _peer_client(tmp_path)
    identita, messaggio, firma = _peer_firmatario(tmp_path)
    resp = client.post("/p2p/infer", json={
        "peer_id": identita["peer_id"], "message": messaggio, "signature": firma,
    })
    assert resp.status_code == 401


def test_p2p_infer_firma_di_un_altro_peer_401(tmp_path):
    """Il caso che il codice originale lasciava passare per la ragione sbagliata."""
    client, h = _peer_client(tmp_path)
    vero, messaggio, _ = _peer_firmatario(tmp_path, "vero")
    _, _, firma_altrui = _peer_firmatario(tmp_path, "impostore")

    h._get_registry().add_peer(
        host="10.0.0.9", port=8000, peer_id=vero["peer_id"],
        public_key=vero["public_key"], name="vero", models=[],
    )
    h._get_registry().set_state(vero["peer_id"], "trusted")

    resp = client.post("/p2p/infer", json={
        "peer_id": vero["peer_id"], "message": messaggio, "signature": firma_altrui,
    })
    assert resp.status_code == 401


def test_p2p_infer_peer_non_trusted_403(tmp_path):
    """Firma valida ma fiducia mai concessa: la scoperta non e' un permesso."""
    client, h = _peer_client(tmp_path)
    identita, messaggio, firma = _peer_firmatario(tmp_path)

    h._get_registry().add_peer(
        host="10.0.0.9", port=8000, peer_id=identita["peer_id"],
        public_key=identita["public_key"], name="altro", models=[],
    )
    resp = client.post("/p2p/infer", json={
        "peer_id": identita["peer_id"], "message": messaggio, "signature": firma,
    })
    assert resp.status_code == 403


def test_p2p_infer_rifiuta_se_la_condivisione_e_spenta(tmp_path):
    """Default spento: mettere il proprio hardware a disposizione e' una scelta."""
    client, h = _peer_client(tmp_path)
    identita, messaggio, firma = _peer_firmatario(tmp_path)

    h._get_registry().add_peer(
        host="10.0.0.9", port=8000, peer_id=identita["peer_id"],
        public_key=identita["public_key"], name="altro", models=[],
    )
    h._get_registry().set_state(identita["peer_id"], "trusted")

    resp = client.post("/p2p/infer", json={
        "peer_id": identita["peer_id"], "message": messaggio, "signature": firma,
    })
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# /p2p/receipt — controfirma delle ricevute AiloCoin
# ---------------------------------------------------------------------------
# Il difetto della verifica di firma si ripeteva identico qui: la firma del
# chiamante veniva confrontata con la chiave pubblica di questo nodo. E la
# route non controfirmava affatto — costruiva una ricevuta nuova, lasciando le
# due parti con due documenti diversi invece che con lo stesso.


def _ricevuta_firmata(tmp_path, handlers, provider_identity):
    """Una ricevuta emessa e firmata da un provider esterno."""
    return handlers._get_wallet().issue_receipt(
        request_id="req-1",
        provider_id=provider_identity["peer_id"],
        consumer_id=handlers._get_identity()["peer_id"],
        model="modello-di-prova",
        tokens=1000,
        rate=1000,
        private_key_bytes=_base64.b64decode(provider_identity["private_key"]),
    )


def test_receipt_da_peer_sconosciuto_401(tmp_path):
    client, h = _peer_client(tmp_path)
    prov, messaggio, firma = _peer_firmatario(tmp_path, "prov")
    corpo = {
        "receipt": _ricevuta_firmata(tmp_path, h, prov),
        "peer_id": prov["peer_id"], "message": messaggio, "signature": firma,
    }
    assert client.post("/p2p/receipt", json=corpo).status_code == 401


def test_receipt_da_peer_non_trusted_403(tmp_path):
    client, h = _peer_client(tmp_path)
    prov, messaggio, firma = _peer_firmatario(tmp_path, "prov")
    h._get_registry().add_peer(
        host="10.0.0.5", port=8000, peer_id=prov["peer_id"],
        public_key=prov["public_key"], name="prov", models=[],
    )
    corpo = {
        "receipt": _ricevuta_firmata(tmp_path, h, prov),
        "peer_id": prov["peer_id"], "message": messaggio, "signature": firma,
    }
    assert client.post("/p2p/receipt", json=corpo).status_code == 403


def test_receipt_controfirma_senza_alterare_quella_del_provider(tmp_path):
    """Le due parti devono restare in possesso dello STESSO documento."""
    client, h = _peer_client(tmp_path)
    prov, messaggio, firma = _peer_firmatario(tmp_path, "prov")
    h._get_registry().add_peer(
        host="10.0.0.5", port=8000, peer_id=prov["peer_id"],
        public_key=prov["public_key"], name="prov", models=[],
    )
    h._get_registry().set_state(prov["peer_id"], "trusted")

    originale = _ricevuta_firmata(tmp_path, h, prov)
    resp = client.post("/p2p/receipt", json={
        "receipt": originale, "peer_id": prov["peer_id"],
        "message": messaggio, "signature": firma,
    })

    assert resp.status_code == 200
    controfirmata = resp.json()["countersigned"]
    assert controfirmata["consumer_signature"]
    assert controfirmata["provider_signature"] == originale["provider_signature"]


def test_receipt_senza_campi_obbligatori_400(tmp_path):
    client, _ = _peer_client(tmp_path)
    assert client.post("/p2p/receipt", json={"peer_id": "x" * 32}).status_code == 400
