"""Test dell'integrazione nativa con la rete AiLo (AiloCoin + inferenza distribuita).

Nessun socket reale: l'HTTP passa da una sessione finta e il WebSocket da una
connessione finta che parla il protocollo di ``/ws/gpu-inference`` del server
ailo-network (register_inference -> inference_request -> inference_response).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

import pytest

pytest.importorskip("cryptography")

from core.modules.sigma_network.ailo_bridge import (
    AiloConfig,
    AiloError,
    AiloInferenceNode,
    AiloNetworkClient,
    normalize_server_url,
    ws_url_for,
)

TOKEN = {"name": "AiloCoin", "symbol": "ALC", "decimals": 8}
STATUS = {"activeNodes": 1, "globalModelVersion": 7}


class FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Riproduce le risposte del server ailo-network per le route usate."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.token = TOKEN

    def request(self, method: str, url: str, timeout: float = 0, json: Any = None, **_: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "json": json})
        path = url.split("://", 1)[1].split("/", 1)[1]
        path = "/" + path
        if path == "/api/v1/rpc":
            m = json["method"]
            results = {
                "alc_getTokenInfo": self.token,
                "alc_getNetworkStats": {"blockNumber": 3, "totalSupply": 10.0},
                "alc_getTransactionsByAddress": [{"type": "INFERENCE_REWARD", "amount": 0.05}],
            }
            if m not in results:
                return FakeResponse(200, {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1})
            return FakeResponse(200, {"jsonrpc": "2.0", "result": results[m], "id": json["id"]})
        if path == "/api/status":
            return FakeResponse(200, STATUS)
        if path == "/api/network-stats":
            return FakeResponse(200, {"totalNodes": 2, "inferenceNodes": 1})
        if path.startswith("/api/balance/"):
            return FakeResponse(200, {"wallet": path.rsplit("/", 1)[1], "balance": 1.5,
                                      "confirmedBalance": 1.0, "pendingBalance": 0.5})
        if path == "/api/login":
            if json["password"] != "segreta":
                return FakeResponse(401, {"error": "Invalid credentials"})
            return FakeResponse(200, {"user": {"email": json["email"], "wallet": "0xabc", "balance": 1.5}})
        if path == "/api/register":
            return FakeResponse(200, {"user": {"email": json["email"], "wallet": "0xnew", "balance": 0}})
        if path == "/api/transfer":
            return FakeResponse(200, {"success": True, "newBalance": 1.0})
        if path == "/api/inference/gpu":
            return FakeResponse(200, {"success": True, "response": "ciao dal nodo", "tokens_generated": 3})
        return FakeResponse(404, "<html>Not found</html>")


# --------------------------------------------------------------------- utilita


def test_normalizzazione_url_e_websocket():
    assert normalize_server_url("ailo.example/") == "https://ailo.example"
    assert ws_url_for("https://ailo.example") == "wss://ailo.example/ws/gpu-inference"
    assert ws_url_for("http://localhost:3000") == "ws://localhost:3000/ws/gpu-inference"


def test_config_non_salva_mai_la_password(tmp_path):
    cfg = AiloConfig(tmp_path / "ailo.json")
    cfg.update({"server_url": "localhost:3000", "password": "segreta", "node_max_tokens": 99999})
    on_disk = (tmp_path / "ailo.json").read_text(encoding="utf-8")
    assert "segreta" not in on_disk
    data = AiloConfig(tmp_path / "ailo.json").get()
    assert data["server_url"] == "https://localhost:3000"
    assert data["node_max_tokens"] == 4096


# --------------------------------------------------------------------- client


def test_client_senza_server_rifiuta():
    with pytest.raises(AiloError):
        AiloNetworkClient("")


def test_verify_server_accetta_un_nodo_ailo():
    client = AiloNetworkClient("http://ailo.test", session=FakeSession())
    out = client.verify_server()
    assert out["token"]["symbol"] == "ALC"


def test_verify_server_rifiuta_un_host_qualunque():
    session = FakeSession()
    session.token = {"symbol": "XYZ"}
    client = AiloNetworkClient("http://ailo.test", session=session)
    with pytest.raises(AiloError):
        client.verify_server()


def test_risposta_html_diventa_errore_leggibile():
    client = AiloNetworkClient("http://ailo.test", session=FakeSession())
    with pytest.raises(AiloError, match="non JSON"):
        client._request("GET", "/route/inesistente")


def test_saldo_login_transfer_e_inferenza():
    session = FakeSession()
    client = AiloNetworkClient("http://ailo.test", session=session)
    assert client.balance("0xabc")["confirmedBalance"] == 1.0
    assert client.login("a@b.c", "segreta")["wallet"] == "0xabc"
    with pytest.raises(AiloError, match="Invalid credentials"):
        client.login("a@b.c", "sbagliata")
    assert client.transfer("a@b.c", "0xdef", 0.5, "segreta")["success"] is True
    with pytest.raises(AiloError):
        client.transfer("a@b.c", "0xdef", 0, "segreta")
    out = client.infer("ciao", max_tokens=10)
    assert out["response"] == "ciao dal nodo"
    assert session.calls[-1]["json"] == {"prompt": "ciao", "max_tokens": 10, "temperature": 0.8}


def test_rpc_errore_propagato():
    client = AiloNetworkClient("http://ailo.test", session=FakeSession())
    with pytest.raises(AiloError, match="-32601"):
        client.rpc("alc_inesistente")


# --------------------------------------------------------------------- nodo


class FakeWebSocket:
    """Lato server di ``/ws/gpu-inference`` controllato dal test."""

    def __init__(self, incoming: List[Dict[str, Any]]) -> None:
        self.incoming = [json.dumps(m) for m in incoming]
        self.sent: List[Dict[str, Any]] = []
        self.url = None

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def recv(self) -> str:
        if self.incoming:
            return self.incoming.pop(0)
        await asyncio.sleep(3600)
        return ""

    async def __aenter__(self) -> "FakeWebSocket":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _run_node(node: AiloInferenceNode, ws: FakeWebSocket, until, timeout: float = 5.0) -> None:
    node.start()
    deadline = time.time() + timeout
    while time.time() < deadline and not until():
        time.sleep(0.05)
    node.stop()


def test_nodo_si_registra_e_risponde_alle_richieste():
    ws = FakeWebSocket([
        {"type": "registered", "nodeId": "gpu_inf_1"},
        {"type": "ping"},
        {"type": "inference_request", "request_id": "inf_1", "prompt": "ciao", "max_tokens": 99999, "temperature": 0.5},
    ])
    seen: Dict[str, Any] = {}

    def generate(prompt: str, max_tokens: int, temperature: float):
        seen.update(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
        return "risposta locale", 2

    def connect(url, **_):
        ws.url = url
        return ws

    node = AiloInferenceNode("http://ailo.test", "0xabc", "a@b.c", generate,
                             max_tokens=64, connect=connect)
    _run_node(node, ws, lambda: any(m["type"] == "inference_response" for m in ws.sent))

    assert ws.url == "ws://ailo.test/ws/gpu-inference"
    assert ws.sent[0] == {"type": "register_inference", "wallet": "0xabc", "email": "a@b.c",
                          "gpu": "Sigma Studio", "vram": 0}
    assert {"type": "pong"} in ws.sent
    resp = next(m for m in ws.sent if m["type"] == "inference_response")
    assert resp["request_id"] == "inf_1" and resp["response"] == "risposta locale"
    assert resp["tokens_generated"] == 2 and resp["wallet"] == "0xabc"
    # Il server chiedeva 99999 token: il nodo applica il proprio limite.
    assert seen["max_tokens"] == 64 and seen["temperature"] == 0.5
    status = node.status()
    assert status["node_id"] == "gpu_inf_1" and status["inferences"] == 1 and status["tokens_generated"] == 2


def test_nodo_rifiuta_quando_il_guard_dice_no():
    ws = FakeWebSocket([{"type": "inference_request", "request_id": "inf_2", "prompt": "x"}])
    called = []
    node = AiloInferenceNode("http://ailo.test", "0xabc", "", lambda *a: called.append(a) or ("", 0),
                             gate_fn=lambda: (False, "RAM satura"), connect=lambda url, **_: ws)
    _run_node(node, ws, lambda: any(m["type"] == "inference_error" for m in ws.sent))
    err = next(m for m in ws.sent if m["type"] == "inference_error")
    assert err == {"type": "inference_error", "request_id": "inf_2", "error": "RAM satura"}
    assert not called and node.status()["rejected"] == 1


def test_errore_di_generazione_torna_al_server():
    ws = FakeWebSocket([{"type": "inference_request", "request_id": "inf_3", "prompt": "x"}])

    def boom(*_):
        raise RuntimeError("modello non caricato")

    node = AiloInferenceNode("http://ailo.test", "0xabc", "", boom, connect=lambda url, **_: ws)
    _run_node(node, ws, lambda: any(m["type"] == "inference_error" for m in ws.sent))
    err = next(m for m in ws.sent if m["type"] == "inference_error")
    assert err["error"] == "modello non caricato"


def test_nodo_senza_wallet_rifiutato():
    with pytest.raises(AiloError):
        AiloInferenceNode("http://ailo.test", "", "", lambda *a: ("", 0))


# --------------------------------------------------------------------- route


@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import core.modules.sigma_network.handlers as h

    h._reset_singletons()
    monkeypatch.setattr(h, "_ailo_config_file", str(tmp_path / "ailo.json"))
    session = FakeSession()
    real_init = AiloNetworkClient.__init__

    def init(self, server_url, timeout=20.0, session_=None):
        real_init(self, server_url, timeout, session)

    monkeypatch.setattr(AiloNetworkClient, "__init__", init)
    app = FastAPI()
    app.include_router(h.router, prefix="/api/sigma_network")
    yield TestClient(app), session
    h._reset_singletons()


def test_route_stato_senza_configurazione(api):
    client, _ = api
    out = client.get("/api/sigma_network/ailo/status").json()
    assert out["configured"] is False and out["verified"] is False


def test_route_flusso_completo_wallet_e_inferenza(api):
    client, session = api
    base = "/api/sigma_network/ailo"
    assert client.post(f"{base}/config", json={"server_url": "http://ailo.test"}).status_code == 200

    status = client.get(f"{base}/status").json()
    assert status["verified"] is True and status["token"]["symbol"] == "ALC"

    bad = client.post(f"{base}/login", json={"email": "a@b.c", "password": "sbagliata"})
    assert bad.status_code == 502

    linked = client.post(f"{base}/login", json={"email": "a@b.c", "password": "segreta"}).json()
    assert linked["wallet"] == "0xabc"
    assert "segreta" not in json.dumps(client.get(f"{base}/config").json())

    wallet = client.get(f"{base}/wallet").json()
    assert wallet["balance"] == 1.5 and wallet["transactions"][0]["type"] == "INFERENCE_REWARD"

    assert client.post(f"{base}/transfer", json={"to_wallet": "0xdef", "amount": 0.5,
                                                 "password": "segreta"}).json()["success"] is True

    inf = client.post(f"{base}/infer", json={"prompt": "ciao", "max_tokens": 50000}).json()
    assert inf["response"] == "ciao dal nodo"
    assert session.calls[-1]["json"]["max_tokens"] == 4096

    assert client.post(f"{base}/infer", json={"prompt": "  "}).status_code == 400


def test_route_nodo_richiede_wallet(api):
    client, _ = api
    client.post("/api/sigma_network/ailo/config", json={"server_url": "http://ailo.test"})
    assert client.post("/api/sigma_network/ailo/node/start").status_code == 400
    assert client.get("/api/sigma_network/ailo/node/status").json()["running"] is False
