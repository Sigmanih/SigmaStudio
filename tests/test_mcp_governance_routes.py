"""La scelta esplicita del server non deve aggirare l'assenso umano."""
import json
import threading

import pytest

from core.mcp import governance
from core.mcp.base_server import BaseMCPServer
from core.mcp.mcp_hub import MCPHub


@pytest.fixture
def hub(tmp_path, monkeypatch):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"mcp": {"auto_approve": False}}), encoding="utf-8")
    monkeypatch.setattr(governance, "CONFIG_PATH", str(policy))
    monkeypatch.setattr(governance, "shared_dir", lambda: tmp_path / "approvals")
    governance.reset_pending()
    result = MCPHub.__new__(MCPHub)
    result.servers, result.external, result._lock = {}, {}, threading.RLock()
    yield result
    governance.reset_pending()


def _server(hub, name, calls, safety=governance.SENSITIVE):
    server = BaseMCPServer(name)
    server.register_tool("azione", "Operazione di prova", {"type": "object"},
                         lambda **args: calls.append((name, args)) or name, safety=safety)
    hub.register_server(server)
    return server


def _call(hub, server, **params):
    return hub.dispatch_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "azione", "server": server, **params}})


def test_server_esplicito_richiede_assenso(hub):
    calls = []
    _server(hub, "destinazione", calls)
    response = _call(hub, "destinazione")
    assert response["result"]["confirmationRequired"]
    assert calls == []


def test_server_disabilitato_non_esegue(hub):
    calls = []
    _server(hub, "destinazione", calls, governance.SAFE)
    governance.set_server_enabled("destinazione", False)
    assert "error" in _call(hub, "destinazione")
    assert calls == []


def test_nomi_uguali_rispettano_il_server_e_l_assenso(hub):
    calls = []
    _server(hub, "primo", calls)
    _server(hub, "secondo", calls)
    pending = _call(hub, "secondo", arguments={"valore": 7})["result"]["approval"]
    governance.confirm_approval(pending["request_id"], approved=True)
    response = _call(hub, "primo", approval_id=pending["request_id"], arguments={"valore": 99})
    assert "error" not in response
    assert calls == [("secondo", {"valore": 7})]


def test_server_inesistente_non_ripiega_su_un_altro(hub):
    calls = []
    _server(hub, "primo", calls, governance.SAFE)
    assert "error" in _call(hub, "assente")
    assert calls == []
