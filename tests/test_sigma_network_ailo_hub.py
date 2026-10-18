"""Test dell'hub AiLo nativo: registro AiloCoin, migrazione e smistamento ai nodi.

Nessun socket reale: le route passano dal TestClient di FastAPI, WebSocket
compresi.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

import pytest

pytest.importorskip("cryptography")

from core.modules.sigma_network.ailo_hub import (
    REWARD_MAX_PER_HOUR,
    AiloLedger,
    LedgerError,
    hash_password,
    verify_password,
)

#: Hash prodotto dal coordinatore Node (crypto.scryptSync) per 'ailo-password-1'.
NODE_HASH = ("0123456789abcdef0123456789abcdef:01202bb0d883c0b0e82017b1118069f2cbd0ad5b92d9cbbf"
             "06703a5e1300dd35951a3dc418209a6be8d704fd5f75f2fc592af87b05bdd45939be5c3196e76260")


@pytest.fixture
def ledger(tmp_path):
    led = AiloLedger(tmp_path / "hub.db")
    yield led
    led.close()


def _funded(ledger, email, amount):
    user = ledger.register(email, "password-123")
    ledger._db.execute("UPDATE users SET balance = ? WHERE email = ?", (amount, email))
    return user


# --------------------------------------------------------------------- password


def test_password_compatibile_con_il_coordinatore_node():
    assert verify_password("ailo-password-1", NODE_HASH)
    assert not verify_password("sbagliata", NODE_HASH)
    assert verify_password("nuova-pass", hash_password("nuova-pass"))
    assert not verify_password("x", "formato-legacy-senza-salt")


# --------------------------------------------------------------------- account


def test_registrazione_e_login(ledger):
    user = ledger.register("Mario@Example.com", "password-123")
    assert user["wallet"].startswith("0x") and len(user["wallet"]) == 42 and user["balance"] == 0
    assert ledger.login("mario@example.com", "password-123")["wallet"] == user["wallet"]
    with pytest.raises(LedgerError) as e:
        ledger.login("mario@example.com", "sbagliata")
    assert e.value.status == 401
    with pytest.raises(LedgerError) as e:
        ledger.register("mario@example.com", "password-123")
    assert e.value.status == 409
    with pytest.raises(LedgerError):
        ledger.register("non-una-email", "password-123")
    with pytest.raises(LedgerError):
        ledger.register("b@example.com", "corta")


# --------------------------------------------------------------------- trasferimenti


def test_trasferimento_valido_e_commissione(ledger):
    a = _funded(ledger, "a@example.com", 1.0)
    b = ledger.register("b@example.com", "password-123")
    out = ledger.transfer("a@example.com", b["wallet"], 0.3, "password-123", fee=0.01)
    assert out["success"] and out["newBalance"] == pytest.approx(0.69)
    assert ledger.balance(b["wallet"])["balance"] == pytest.approx(0.3)
    # Il mittente si puo' indicare anche per wallet.
    ledger.transfer(a["wallet"], b["wallet"], 0.1, "password-123")
    assert ledger.balance(a["wallet"])["confirmedBalance"] == pytest.approx(0.59)
    txs = ledger.transactions(a["wallet"])
    assert [t["type"] for t in txs] == ["TRANSFER", "TRANSFER"] and txs[0]["hash"].startswith("0x")
    assert ledger.transaction(txs[0]["hash"])["amount"] == pytest.approx(0.3)


@pytest.mark.parametrize("amount", [-1, 0, "abc", float("inf"), None])
def test_importi_non_validi_rifiutati(ledger, amount):
    _funded(ledger, "a@example.com", 1.0)
    b = ledger.register("b@example.com", "password-123")
    with pytest.raises(LedgerError, match="Invalid amount"):
        ledger.transfer("a@example.com", b["wallet"], amount, "password-123")
    assert ledger.balance(b["wallet"])["balance"] == 0


def test_attacchi_ai_trasferimenti(ledger):
    a = _funded(ledger, "a@example.com", 1.0)
    b = ledger.register("b@example.com", "password-123")
    with pytest.raises(LedgerError) as e:
        ledger.transfer("a@example.com", b["wallet"], 0.1, "sbagliata")
    assert e.value.status == 401
    with pytest.raises(LedgerError, match="own wallet"):
        ledger.transfer("a@example.com", a["wallet"], 0.1, "password-123")
    with pytest.raises(LedgerError, match="Insufficient"):
        ledger.transfer("a@example.com", b["wallet"], 5, "password-123")
    # Una fee negativa non fa spendere meno di quanto si invia.
    ledger.transfer("a@example.com", b["wallet"], 0.5, "password-123", fee=-10)
    assert ledger.balance(a["wallet"])["balance"] == pytest.approx(0.5)
    assert ledger.stats()["totalSupply"] == pytest.approx(1.0)


def test_spese_concorrenti_non_superano_il_saldo(ledger):
    _funded(ledger, "a@example.com", 1.0)
    b = ledger.register("b@example.com", "password-123")
    ok, ko = [], []

    def spend():
        try:
            ledger.transfer("a@example.com", b["wallet"], 0.3, "password-123")
            ok.append(1)
        except LedgerError:
            ko.append(1)

    threads = [threading.Thread(target=spend) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ok) == 3 and len(ko) == 3
    assert ledger.balance(b["wallet"])["balance"] == pytest.approx(0.9)


def test_ricompense_con_tetto_orario(ledger):
    a = ledger.register("a@example.com", "password-123")
    paid = [ledger.reward(a["wallet"]) for _ in range(REWARD_MAX_PER_HOUR + 5)]
    assert sum(1 for p in paid if p is not None) == REWARD_MAX_PER_HOUR
    assert ledger.balance(a["wallet"])["contributions"] == REWARD_MAX_PER_HOUR
    assert ledger.reward("0xinesistente") is None


# --------------------------------------------------------------------- migrazione


def _make_ailo_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE users (email TEXT PRIMARY KEY, password TEXT NOT NULL, wallet TEXT UNIQUE NOT NULL,
            balance REAL DEFAULT 0, contributions INTEGER DEFAULT 0, last_seen INTEGER, created_at INTEGER);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, from_wallet TEXT,
            to_wallet TEXT, amount REAL, timestamp INTEGER, metadata TEXT, status TEXT DEFAULT 'PENDING');
    """)
    db.execute("INSERT INTO users VALUES ('old@ailo.site', ?, '0xold', 12.5, 3, 1, 1)", (NODE_HASH,))
    db.execute("INSERT INTO transactions (type, from_wallet, to_wallet, amount, timestamp, metadata) "
               "VALUES ('INFERENCE_REWARD', 'NETWORK', '0xold', 12.5, 5, '{}')")
    db.commit()
    db.close()


def test_import_da_ailo_db_mantiene_saldi_e_password(ledger, tmp_path):
    src = tmp_path / "ailo.db"
    _make_ailo_db(src)
    out = ledger.import_ailo_db(src)
    assert out == {"users": 1, "transactions": 1, "skipped_users": 0}
    assert ledger.login("old@ailo.site", "ailo-password-1")["balance"] == 12.5
    assert ledger.transactions("0xold")[0]["metadata"]["imported_from"] == "ailo-network"
    # Rieseguire l'import non raddoppia nulla.
    assert ledger.import_ailo_db(src) == {"users": 0, "transactions": 0, "skipped_users": 1}
    assert ledger.balance("0xold")["balance"] == 12.5


def test_import_rifiuta_file_non_ailo(ledger, tmp_path):
    other = tmp_path / "altro.db"
    sqlite3.connect(other).execute("CREATE TABLE x (a)").connection.close()
    with pytest.raises(LedgerError):
        ledger.import_ailo_db(other)
    with pytest.raises(LedgerError):
        ledger.import_ailo_db(tmp_path / "manca.db")


# --------------------------------------------------------------------- route


@pytest.fixture
def hub(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import core.modules.sigma_network.handlers as h

    h._reset_singletons()
    monkeypatch.setattr(h, "_ailo_config_file", str(tmp_path / "ailo.json"))
    monkeypatch.setattr(h, "_ailo_hub_db_file", str(tmp_path / "hub.db"))
    app = FastAPI()
    app.include_router(h.router, prefix="/api/sigma_network")
    with TestClient(app) as client:
        yield client, h, monkeypatch
    h._reset_singletons()


B = "/api/sigma_network/ailo_hub"


def _enable(client, h, monkeypatch):
    monkeypatch.setattr(h, "_is_local", lambda request: True)
    assert client.post("/api/sigma_network/ailo/hub/enable", json={"enabled": True}).json()["enabled"] is True


def test_hub_spento_e_amministrazione_solo_locale(hub):
    client, h, monkeypatch = hub
    assert client.get(f"{B}/api/status").status_code == 404
    # Il TestClient non e' loopback: i comandi di amministrazione sono rifiutati.
    assert client.post("/api/sigma_network/ailo/hub/enable", json={"enabled": True}).status_code == 403
    assert client.post("/api/sigma_network/ailo/hub/import", json={"path": "x"}).status_code == 403
    _enable(client, h, monkeypatch)
    status = client.get(f"{B}/api/status").json()
    assert status["globalModelVersion"] == 1 and status["activeNodes"] == 0


def test_hub_api_compatibili_col_bridge(hub):
    """Il client del bridge parla con l'hub come col vecchio coordinatore."""
    client, h, monkeypatch = hub
    _enable(client, h, monkeypatch)
    from core.modules.sigma_network.ailo_bridge import AiloError, AiloNetworkClient

    class Session:
        def request(self, method, url, timeout=0, json=None, **_):
            path = url.split("testserver", 1)[1]
            return client.request(method, path, json=json)

    bridge = AiloNetworkClient("http://testserver" + B, session=Session())
    assert bridge.verify_server()["token"]["symbol"] == "ALC"
    user = bridge.register("c@example.com", "password-123")
    assert bridge.login("c@example.com", "password-123")["wallet"] == user["wallet"]
    with pytest.raises(AiloError, match="Invalid credentials"):
        bridge.login("c@example.com", "nope-nope")
    assert bridge.balance(user["wallet"])["balance"] == 0
    other = bridge.register("d@example.com", "password-123")
    with pytest.raises(AiloError, match="Insufficient"):
        bridge.transfer("c@example.com", other["wallet"], 1, "password-123")
    assert bridge.chain_stats()["activeAddresses"] == 2
    with pytest.raises(AiloError, match="-32601"):
        bridge.rpc("alc_boh")
    assert bridge.infer("ciao")["success"] is False  # nessun nodo collegato


def test_ledger_transfer_web_richiede_password(hub):
    client, h, monkeypatch = hub
    _enable(client, h, monkeypatch)
    a = client.post(f"{B}/api/register", json={"email": "a@example.com", "password": "password-123"}).json()["user"]
    b = client.post(f"{B}/api/register", json={"email": "b@example.com", "password": "password-123"}).json()["user"]
    h._ailo_ledger()._db.execute("UPDATE users SET balance = 1 WHERE email = 'a@example.com'")
    r = client.post(f"{B}/api/ledger/transfer", json={"from": a["wallet"], "to": b["wallet"], "amount": 0.2})
    assert r.status_code == 401
    r = client.post(f"{B}/api/ledger/transfer", json={"from": a["wallet"], "to": b["wallet"], "amount": 0.2,
                                                        "fee": -3, "password": "password-123"}).json()
    assert r["success"] and r["fee"] == 0.01 and r["newBalance"] == pytest.approx(0.79)


def test_inferenza_smistata_al_nodo_websocket_e_ricompensata(hub):
    client, h, monkeypatch = hub
    _enable(client, h, monkeypatch)
    node_user = client.post(f"{B}/api/register", json={"email": "n@example.com", "password": "password-123"}).json()["user"]

    with client.websocket_connect(f"{B}/ws/gpu-inference") as ws:
        ws.send_text(json.dumps({"type": "register_inference", "wallet": node_user["wallet"], "gpu": "Test GPU"}))
        assert json.loads(ws.receive_text())["type"] == "registered"
        assert client.get(f"{B}/api/nodes").json()[0]["gpu"] == "Test GPU"

        result = {}
        t = threading.Thread(target=lambda: result.update(client.post(
            f"{B}/api/inference/gpu", json={"prompt": "ciao", "max_tokens": 99999}).json()))
        t.start()
        req = json.loads(ws.receive_text())
        assert req["type"] == "inference_request" and req["prompt"] == "ciao" and req["max_tokens"] == 4096
        # Una risposta per un'altra richiesta viene ignorata.
        ws.send_text(json.dumps({"type": "inference_response", "request_id": "falso", "response": "x"}))
        ws.send_text(json.dumps({"type": "inference_response", "request_id": req["request_id"],
                                 "response": "risposta del nodo", "tokens_generated": 3}))
        t.join(10)

    assert result["success"] and result["response"] == "risposta del nodo" and result["tokens_generated"] == 3
    assert result["processed_by"] == node_user["wallet"][:12] + "..."
    bal = client.get(f"{B}/api/balance/{node_user['wallet']}").json()
    assert bal["balance"] == pytest.approx(0.05)
    deadline = time.time() + 2
    while client.get(f"{B}/api/nodes").json() and time.time() < deadline:
        time.sleep(0.05)
    assert client.get(f"{B}/api/nodes").json() == []


def test_errore_del_nodo_torna_al_chiamante(hub):
    client, h, monkeypatch = hub
    _enable(client, h, monkeypatch)
    with client.websocket_connect(f"{B}/ws/gpu-inference") as ws:
        ws.send_text(json.dumps({"type": "register_inference", "wallet": "0xabc"}))
        ws.receive_text()
        result = {}
        t = threading.Thread(target=lambda: result.update(client.post(f"{B}/api/inference/gpu", json={"prompt": "x"}).json()))
        t.start()
        req = json.loads(ws.receive_text())
        ws.send_text(json.dumps({"type": "inference_error", "request_id": req["request_id"], "error": "OOM"}))
        t.join(10)
    assert result["success"] is False and result["error"] == "OOM"


def test_import_via_route(hub, tmp_path):
    client, h, monkeypatch = hub
    _enable(client, h, monkeypatch)
    src = tmp_path / "ailo.db"
    _make_ailo_db(src)
    out = client.post("/api/sigma_network/ailo/hub/import", json={"path": str(src)}).json()
    assert out["users"] == 1
    r = client.post(f"{B}/api/login", json={"email": "old@ailo.site", "password": "ailo-password-1"}).json()
    assert r["user"]["balance"] == 12.5
    assert client.post("/api/sigma_network/ailo/hub/import", json={"path": str(tmp_path / "no.db")}).status_code == 404
