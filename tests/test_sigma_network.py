"""Test del modulo Sigma Network — Task 1: identita crittografica del peer.

Task 2: registro dei peer (PeerRegistry).
Task 3: contabilita AiloCoin (Wallet).
Task 4: provider e broker di inferenza.
Task 5: scoperta dei peer (PeerDiscovery).
"""


from __future__ import annotations

# Una dipendenza opzionale assente non deve fermare la raccolta: senza questa
# riga `pytest tests/` usciva con un errore di collection e **nessun** test
# partiva. La rete firmata usa `cryptography` per le identita.
import pytest

pytest.importorskip("cryptography")

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

# Una dipendenza opzionale assente non deve fermare la raccolta: senza
# questa riga `pytest tests/` usciva con un errore di collection e nessun
# test partiva. La rete firmata usa `cryptography` per le identita.
import pytest
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


# ---------------------------------------------------------------------------
# Task 7 — Mappa Radar, Faucet e Ailo PoUW Mining Engine
# ---------------------------------------------------------------------------


def test_network_map_genera_topologia_e_radar_coords(tmp_path):
    """get_network_map() deve calcolare coordinate polari, stato e statistiche."""
    reg = PeerRegistry(str(tmp_path / "peers.json"))
    reg.add_peer(
        host="192.168.1.50",
        port=8000,
        peer_id="x" * 32,
        public_key="pk_x",
        name="peer_x",
        models=["AILO-152M", "qwen"],
    )
    reg.touch("x" * 32, latency_ms=45.0)

    net_map = reg.get_network_map({"peer_id": "me" * 16, "name": "Me", "models": ["llama"]})
    assert net_map["local_node"]["peer_id"] == "me" * 16
    assert len(net_map["peers"]) == 1
    peer_entry = net_map["peers"][0]
    assert peer_entry["peer_id"] == "x" * 32
    assert peer_entry["is_online"] is True
    assert 0 <= peer_entry["radar_angle"] <= 360
    assert 0.2 <= peer_entry["radar_distance"] <= 1.0
    assert net_map["summary"]["online_count"] == 2


def test_wallet_faucet_e_mining_rewards(tmp_path):
    """mint_faucet e mint_mining_reward devono accreditare correttamente il saldo."""
    wallet = Wallet(str(tmp_path / "wallet.json"))
    pid = "miner" * 6 + "12"

    bal0 = wallet.balance(pid)
    assert bal0["balance"] == 0.0

    wallet.mint_faucet(pid, amount=100.0)
    bal1 = wallet.balance(pid)
    assert bal1["faucet"] == 100.0
    assert bal1["balance"] == 100.0

    wallet.mint_mining_reward(pid, amount=5.5, task_type="ailo_gradient_batch", meta={"loss": 2.1, "step": 1})
    bal2 = wallet.balance(pid)
    assert bal2["mined"] == 5.5
    assert bal2["balance"] == 105.5


def test_mining_engine_step_now(tmp_path):
    """MiningEngine deve eseguire passi di calcolo e convergere la loss."""
    from core.modules.sigma_network.mining_engine import MiningEngine
    miner = MiningEngine()
    status0 = miner.get_status()
    assert status0["step"] == 0

    res = miner.compute_step_now()
    assert res["step"] == 1
    assert res["reward"] > 0
    assert res["loss"] <= 4.25


def test_wallet_transfer_e_chain_verification(tmp_path):
    """Wallet.transfer deve trasferire fondi, aggiornare i saldi e preservare la validità della catena."""
    w = Wallet(str(tmp_path / "wallet.json"))
    alice = generate_identity(str(tmp_path / "alice.json"))
    bob = generate_identity(str(tmp_path / "bob.json"))
    alice_priv = base64.b64decode(alice["private_key"])

    # Alice riceve 100 AiloCoin da Faucet
    w.mint_faucet(alice["peer_id"], amount=100.0)
    assert w.balance(alice["peer_id"])["balance"] == 100.0

    # Alice trasferisce 25 AiloCoin a Bob
    tx = w.transfer(
        sender_id=alice["peer_id"],
        recipient_id=bob["peer_id"],
        amount=25.0,
        private_key_bytes=alice_priv,
        note="Regalo di benvenuto su Ailo Network",
    )
    assert tx["amount"] == 25.0
    assert tx["consumer_signature"] is not None
    assert tx["provider_id"] == bob["peer_id"]
    assert tx["consumer_id"] == alice["peer_id"]

    # Saldo Alice = 75, Saldo Bob = 25
    assert w.balance(alice["peer_id"])["balance"] == 75.0
    assert w.balance(bob["peer_id"])["balance"] == 25.0

    # Verifica crittografica catena
    verif = w.verify_chain()
    assert verif["valid"] is True
    assert verif["chain_length"] == 2
    assert verif["corrupted_count"] == 0


def test_federated_aggregator_push_and_aggregate():
    """FederatedAggregator deve accumulare gradienti e avanzare versione globale del modello."""
    from core.modules.sigma_network.federated_aggregator import FederatedAggregator
    agg = FederatedAggregator(min_gradients=2, timeout_s=999.0)

    state0 = agg.get_state()
    assert state0["model_version"] == 1
    assert state0["buffered_gradients"] == 0

    # Invio gradiente peer 1
    res1 = agg.push_gradients("peer1", {"data": "H4sIC...", "step": 1, "loss": 2.5})
    assert res1["status"] == "accepted"
    assert res1["buffered"] == 1
    assert res1["current_version"] == 1

    # Invio gradiente peer 2 -> raggiunge min_gradients=2 e scatta aggregate_now
    res2 = agg.push_gradients("peer2", {"data": "H4sIC...", "step": 1, "loss": 2.3})
    assert res2["status"] == "accepted"

    state1 = agg.get_state()
    assert state1["model_version"] == 2
    assert state1["buffered_gradients"] == 0
    assert state1["total_aggregations"] == 1


def test_handlers_wallet_transfer_and_verify(tmp_path):
    """I nuovi endpoint /wallet/transfer e /wallet/verify_chain devono funzionare regolarmente."""
    client = _make_client(tmp_path)
    # Faucet prima
    client.post("/wallet/faucet", json={"amount": 50.0})

    # Verifica chain
    resp_v = client.post("/wallet/verify_chain")
    assert resp_v.status_code == 200
    assert resp_v.json()["valid"] is True

    # Trasferimento a un peer fittizio
    bob_id = "bob" * 10 + "01"
    resp_tx = client.post("/wallet/transfer", json={"recipient_id": bob_id, "amount": 15.0, "note": "Test transfer"})
    assert resp_tx.status_code == 200
    data_tx = resp_tx.json()
    assert data_tx["status"] == "success"
    assert data_tx["new_balance"] == 35.0

    # Ri-verifica chain
    resp_v2 = client.post("/wallet/verify_chain")
    assert resp_v2.status_code == 200
    assert resp_v2.json()["valid"] is True
    assert resp_v2.json()["chain_length"] == 2


def test_handlers_federated_routes(tmp_path):
    """Endpoint /federated/status, /federated/gradients, /federated/aggregate devono rispondere correttamente."""
    client = _make_client(tmp_path)

    # Status iniziale
    resp_st = client.get("/federated/status")
    assert resp_st.status_code == 200
    assert resp_st.json()["model_version"] == 1

    # Push gradient
    resp_push = client.post("/federated/gradients", json={"data": "abc123compressed", "step": 10, "loss": 1.85})
    assert resp_push.status_code == 200
    assert resp_push.json()["status"] == "accepted"

    # Force aggregate
    resp_agg = client.post("/federated/aggregate")
    assert resp_agg.status_code == 200
    assert resp_agg.json()["aggregated"] is True
    assert resp_agg.json()["model_version"] == 2

    # Get weights metadata
    resp_w = client.get("/federated/weights")
    assert resp_w.status_code == 200
    assert resp_w.json()["version"] == 2


def test_sigma_network_mcp_server(tmp_path):
    """SigmaNetworkMCPServer deve esporre i tool di rete, cluster e wallet agli agenti."""
    from core.modules.sigma_network.network_server import SigmaNetworkMCPServer
    import core.modules.sigma_network.handlers as h

    _reset_singletons()
    h._identity_file = str(tmp_path / "identity.json")
    h._peers_file = str(tmp_path / "peers.json")
    h._wallet_file = str(tmp_path / "wallet.json")

    server = SigmaNetworkMCPServer()
    assert "p2p_list_peers" in server._tools
    assert "p2p_get_network_map" in server._tools
    assert "p2p_cluster_infer" in server._tools
    assert "p2p_wallet_balance" in server._tools
    assert "p2p_mine_block" in server._tools
    assert "p2p_federated_status" in server._tools

    # Test chiamata tool sincrono wallet
    wallet_info = server._tool_wallet_balance()
    assert "balance" in wallet_info
    assert wallet_info["chain_valid"] is True

    # Test chiamata tool mining
    mine_info = server._tool_mine_block(intensity=1)
    assert mine_info["step_result"]["step"] == 1

    # Test mappa di rete
    net_map = server._tool_get_network_map()
    assert "local_node" in net_map


def test_auth_manager_register_and_login(tmp_path):
    """AuthManager deve registrare un utente, creare seed mnemonic 12 parole e consentire il login."""
    from core.modules.sigma_network.auth_manager import AuthManager
    auth = AuthManager(str(tmp_path / "accounts.json"))

    reg = auth.register_user("alice", "password123")
    assert reg["username"] == "alice"
    assert "peer_id" in reg
    assert len(reg["mnemonic_seed"].split()) == 12
    assert "session_token" in reg

    # Login con password corretta
    login_ok = auth.login("alice", "password123")
    assert login_ok["peer_id"] == reg["peer_id"]
    assert "session_token" in login_ok

    # Login con password errata -> fallisce
    import pytest
    with pytest.raises(ValueError):
        auth.login("alice", "wrong_password")


def test_auth_manager_mnemonic_import(tmp_path):
    """AuthManager deve ripristinare esattamente lo stesso wallet dato il seed mnemonico."""
    from core.modules.sigma_network.auth_manager import AuthManager
    auth = AuthManager(str(tmp_path / "accounts.json"))

    reg = auth.register_user("bob", "secret123")
    seed_phrase = reg["mnemonic_seed"]
    bob_pid = reg["peer_id"]

    # Importa lo stesso seed con un altro username o dopo reset
    auth2 = AuthManager(str(tmp_path / "accounts2.json"))
    imp = auth2.import_wallet("bob_restored", "newsecret456", seed_phrase)
    assert imp["peer_id"] == bob_pid


def test_faucet_anti_sybil_defense(tmp_path):
    """Il faucet Genesis non deve consentire erogazioni duplicate allo stesso peer senza force."""
    import pytest
    w = Wallet(str(tmp_path / "wallet.json"))
    pid = "victim_sybil" * 2

    # Primo claim: OK
    w.mint_faucet(pid, amount=100.0)
    assert w.balance(pid)["faucet"] == 100.0

    # Secondo claim sullo stesso wallet: deve fallire
    with pytest.raises(ValueError, match="già riscattato"):
        w.mint_faucet(pid, amount=100.0)


def test_pouw_solution_and_chain_verification(tmp_path):
    """La Proof-of-Useful-Work deve generare un hash valido verificato da verify_chain."""
    w = Wallet(str(tmp_path / "wallet.json"))
    miner_id = "miner_secure" * 2

    # Mint reward con PoUW valido
    r = w.mint_mining_reward(miner_id, amount=10.0, meta={"step": 1, "loss": 2.1, "difficulty": 2})
    assert r["pouw_hash"].startswith("00")
    assert "nonce" in r

    verif = w.verify_chain()
    assert verif["valid"] is True
    assert verif["chain_length"] == 1


def test_handlers_auth_routes(tmp_path):
    """Endpoint HTTP di autenticazione devono gestire il ciclo di vita dell'utente."""
    import core.modules.sigma_network.handlers as h
    _reset_singletons()
    h._identity_file = str(tmp_path / "identity.json")
    h._peers_file = str(tmp_path / "peers.json")
    h._wallet_file = str(tmp_path / "wallet.json")
    h._auth_file = str(tmp_path / "accounts.json")

    client = _make_client(tmp_path)

    # Sessione iniziale
    resp_s0 = client.get("/auth/session")
    assert resp_s0.status_code == 200
    assert resp_s0.json()["authenticated"] is False

    # Registrazione
    resp_r = client.post("/auth/register", json={"username": "charlie", "password": "mypassword123"})
    assert resp_r.status_code == 200
    r_data = resp_r.json()
    assert r_data["username"] == "charlie"
    assert "mnemonic_seed" in r_data

    # Ora la sessione è autenticata per charlie
    resp_s1 = client.get("/auth/session")
    assert resp_s1.status_code == 200
    assert resp_s1.json()["authenticated"] is True
    assert resp_s1.json()["username"] == "charlie"

    # Logout
    resp_lo = client.post("/auth/logout")
    assert resp_lo.status_code == 200

    resp_s2 = client.get("/auth/session")
    assert resp_s2.json()["authenticated"] is False

    # Login
    resp_li = client.post("/auth/login", json={"username": "charlie", "password": "mypassword123"})
    assert resp_li.status_code == 200
    assert resp_li.json()["username"] == "charlie"


# ---------------------------------------------------------------------------
# Test Provider Telemetry, QoS Benchmark & Smart Resource Guard
# ---------------------------------------------------------------------------

def test_provider_telemetry_and_history():
    """L'InferenceProvider deve calcolare metriche aggregate e tracciare la cronologia."""
    from core.modules.sigma_network.provider import InferenceProvider
    settings = {
        "sharing_enabled": True,
        "shared_models": ["model-a"],
        "rate_tokens_per_coin": 1000,
        "max_concurrent": 3,
        "max_tokens_per_request": 512,
    }
    p = InferenceProvider(settings)

    # Inizialmente telemetria a zero
    telem0 = p.get_telemetry()
    assert telem0["active"] is True
    assert telem0["metrics"]["total_requests_served"] == 0
    assert telem0["history"] == []
    assert "system_memory" in telem0

    # Simula una risposta servita
    mock_engine = lambda prompt, max_tokens: "Risposta test " * 20
    res = p.serve("prompt test", model_id="model-a", max_tokens=100, engine_fn=mock_engine, caller_ip="192.168.1.50")
    assert res["status"] == "ok"
    assert res["tokens_generated"] > 0
    assert res["duration_sec"] >= 0
    assert "earned_ailo" in res

    telem1 = p.get_telemetry()
    assert telem1["metrics"]["total_requests_served"] == 1
    assert telem1["metrics"]["total_tokens_served"] == res["tokens_generated"]
    assert telem1["metrics"]["total_coins_earned"] > 0
    assert len(telem1["history"]) == 1
    assert telem1["history"][0]["caller_ip"] == "192.168.1.50"


def test_provider_benchmark_qos():
    """Il benchmark hardware deve calcolare tok/s, assegnare il QoS tier e suggerire la tariffa."""
    from core.modules.sigma_network.provider import InferenceProvider
    p = InferenceProvider({"sharing_enabled": True})

    # Benchmark con test_engine veloce (Diamond)
    fast_engine = lambda prompt, max_tokens: "parola " * max_tokens
    b_fast = p.benchmark_model("fast-model", test_tokens=32, test_engine_fn=fast_engine)
    assert b_fast["model_id"] == "fast-model"
    assert b_fast["tok_per_sec"] > 0
    assert b_fast["qos_tier"] in ("Diamond", "Gold", "Silver")
    assert b_fast["suggested_rate"] > 0

    telem = p.get_telemetry()
    assert "fast-model" in telem["benchmarks"]


def test_provider_guard_memory_and_busy():
    """Smart Resource Guard deve rifiutare richieste se la memoria o l'utente locale sono occupati."""
    from core.modules.sigma_network.provider import InferenceProvider
    p = InferenceProvider({"sharing_enabled": True, "shared_models": ["model-a"]})

    # Con soglia normale e non occupato: can_serve OK
    ok, reason = p.can_serve("model-a")
    assert ok is True

    # Se l'utente locale sta lavorando e local_user_priority=True: rifiuto
    p.set_busy_local(True)
    ok, reason = p.can_serve("model-a")
    assert ok is False
    assert "utente locale" in reason

    p.set_busy_local(False)

    # Se impostiamo la soglia di memoria allo 0.01% (superamento garantito): rifiuto
    p.update_guard(max_memory_percent=0.01)
    ok, reason = p.can_serve("model-a")
    assert ok is False
    assert "RAM" in reason


def test_handlers_provider_routes(tmp_path):
    """Gli endpoint HTTP di telemetria, benchmark e guard devono rispondere correttamente."""
    import core.modules.sigma_network.handlers as h
    _reset_singletons()
    client = _make_client(tmp_path)

    # Telemetry
    resp_t = client.get("/provider/telemetry")
    assert resp_t.status_code == 200
    t_data = resp_t.json()
    assert "metrics" in t_data
    assert "system_memory" in t_data

    # Guard update
    resp_g = client.post("/provider/guard", json={"max_memory_percent": 85.0, "local_user_priority": False})
    assert resp_g.status_code == 200
    assert resp_g.json()["guard"]["max_memory_percent"] == 85.0
    assert resp_g.json()["guard"]["local_user_priority"] is False

    # Benchmark
    resp_b = client.post("/provider/benchmark", json={"model_id": "test-gguf", "test_tokens": 16})
    assert resp_b.status_code == 200
    b_data = resp_b.json()
    assert b_data["ok"] is True
    assert b_data["model_id"] == "test-gguf"
    assert "qos_tier" in b_data


def test_faucet_double_claim_resilience(tmp_path):
    """Il faucet non deve mai sollevare HTTP 500 al secondo claim ma rispondere con status amichevole."""
    import core.modules.sigma_network.handlers as h
    _reset_singletons()
    client = _make_client(tmp_path)

    # Primo claim: success
    r1 = client.post("/wallet/faucet", json={"amount": 100.0})
    assert r1.status_code == 200
    assert r1.json()["status"] == "success"
    assert r1.json()["credited"] == 100.0

    # Secondo claim con saldo alto: already_claimed (mai 500!)
    r2 = client.post("/wallet/faucet", json={"amount": 100.0})
    assert r2.status_code == 200
    assert r2.json()["status"] == "already_claimed"
    assert r2.json()["credited"] == 0.0


def test_auth_login_node_and_session(tmp_path):
    """auth/login_node deve creare una sessione valida col wallet del nodo locale."""
    import core.modules.sigma_network.handlers as h
    _reset_singletons()
    client = _make_client(tmp_path)

    # Sessione iniziale
    s1 = client.get("/auth/session")
    assert s1.status_code == 200
    assert s1.json()["authenticated"] is False

    # Login con nodo locale
    r_node = client.post("/auth/login_node")
    assert r_node.status_code == 200
    assert r_node.json()["status"] == "success"
    assert "Nodo Locale" in r_node.json()["username"]

    # Sessione post-login
    s2 = client.get("/auth/session")
    assert s2.status_code == 200
    assert s2.json()["authenticated"] is True





