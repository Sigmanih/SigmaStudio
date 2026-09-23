"""L hub di Sigma Studio, raggiungibile da fuori su stdin e stdout.

Il server dei file copre la scrittura; questo copre il resto: un client esterno
vede gli stessi tool che vede Sigma Studio - lint, test, git, docker, cargo,
ricerca semantica, i file - con la stessa policy. Non e una porta di servizio:
l elenco passa da `get_aggregated_tools(only_enabled=True)` e ogni chiamata da
`execute_tool`, quindi un tool spento nella scheda MCP e spento anche per chi
arriva da fuori, e un server disattivato non compare affatto.

Si verifica: cosa espone, che ogni tool dichiari da quale server viene, che un
tool disattivato sparisca e venga rifiutato, che il filtro `SIGMA_MCP_ONLY`
limiti l elenco, che un client MCP esterno ci parli su stdio, e che su stdout non
finisca niente che non sia protocollo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.mcp import governance
from core.mcp.client import ExternalMCPServer
from core.modules.sigma_developer_lab.mcp_tools.fs_server import VAR_RADICE
from core.modules.sigma_developer_lab.mcp_tools.hub_stdio import HubMCPServer

RADICE_PROGETTO = Path(__file__).resolve().parent.parent
FS_TOOLS = {"read_file_window", "edit_file_exact", "write_file", "append_file",
            "read_write_journal"}
#: I due tool del trasporto, non dell hub: ci sono sempre, anche sotto filtro,
#: perche' senza di loro un assenso non si potrebbe ne leggere ne attendere.
SERVIZIO = {"approval_status", "await_approval"}


def _nomi(server):
    return [t["name"] for t in server.list_tools()]


def _testo(esito):
    return esito["content"][0]["text"]


@pytest.fixture
def radice(tmp_path, monkeypatch):
    monkeypatch.setenv(VAR_RADICE, str(tmp_path))
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "modulo.py").write_text("VALORE = 1\n", encoding="utf-8")
    return tmp_path


class TestCosaEspone:
    def test_i_tool_dei_moduli_ci_sono_tutti(self, radice):
        nomi = set(_nomi(HubMCPServer()))
        assert FS_TOOLS <= nomi, nomi
        assert "lint_python" in nomi

    def test_ogni_tool_ha_schema_e_provenienza(self, radice):
        for tool in HubMCPServer().list_tools():
            assert (tool.get("inputSchema") or {}).get("type") == "object", tool["name"]
            assert (tool.get("annotations") or {}).get("server"), tool["name"]

    def test_il_filtro_limita_l_elenco(self, radice, monkeypatch):
        monkeypatch.setenv("SIGMA_MCP_ONLY", "Developer Files")
        nomi = set(_nomi(HubMCPServer()))
        assert nomi == FS_TOOLS | SERVIZIO, nomi


class TestEsecuzione:
    def test_un_tool_dell_hub_si_chiama(self, radice):
        esito = HubMCPServer()._chiama("read_file_window", {"path": "core/modulo.py"})
        assert "VALORE = 1" in _testo(esito)

    def test_un_tool_inesistente_lo_dice(self, radice):
        esito = HubMCPServer()._chiama("non_esiste", {})
        assert esito.get("isError") is True


class TestLaPolicyValeAnchePerChiArrivaDaFuori:
    """E il requisito: si spegne come ogni altro server MCP."""

    def test_un_tool_disattivato_sparisce_e_non_si_esegue(self, radice, tmp_path, monkeypatch):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({
            governance.CONFIG_SECTION: {"disabled_tools": ["read_file_window"]}
        }), encoding="utf-8")
        monkeypatch.setattr(governance, "CONFIG_PATH", str(config))

        server = HubMCPServer()
        assert "read_file_window" not in _nomi(server)
        esito = server._chiama("read_file_window", {"path": "core/modulo.py"})
        assert esito.get("isError") is True
        assert "disattivato" in _testo(esito)

    def test_e_gli_altri_restano_accesi(self, radice, tmp_path, monkeypatch):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({
            governance.CONFIG_SECTION: {"disabled_tools": ["read_file_window"]}
        }), encoding="utf-8")
        monkeypatch.setattr(governance, "CONFIG_PATH", str(config))
        nomi = set(_nomi(HubMCPServer()))
        assert {"edit_file_exact", "write_file", "append_file"} <= nomi


class TestUnClientEsternoCiParla:
    def _cliente(self, radice, only="Developer Files", automatico=True):
        """Un client esterno con la sua installazione, e la policy decisa qui.

        Senza `SIGMA_HOME` il figlio leggerebbe il `config.json` della macchina,
        dove la modalita' automatica puo' essere accesa o spenta: il test
        direbbe cose diverse su macchine diverse.
        """
        casa = Path(radice) / ".casa-di-prova"
        (casa / "config").mkdir(parents=True, exist_ok=True)
        (casa / "config" / "config.json").write_text(
            json.dumps({"mcp": {"auto_approve": bool(automatico)}}), encoding="utf-8")
        return ExternalMCPServer({
            "id": "hub-prova",
            "name": "Sigma Studio Hub (prova)",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "core.modules.sigma_developer_lab.mcp_tools.hub_stdio"],
            "env": {VAR_RADICE: str(radice), "SIGMA_MCP_ONLY": only,
                    "SIGMA_HOME": str(casa), "SIGMA_MCP_CLIENT": "prova"},
            "cwd": str(RADICE_PROGETTO),
        })

    def test_giro_completo(self, radice):
        cliente = self._cliente(radice)
        try:
            assert cliente.connect().get("connected") is True
            assert sorted(t["name"] for t in cliente.list_tools()) == sorted(FS_TOOLS | SERVIZIO)
            scrittura = cliente.call_tool("write_file", {
                "path": "core/nuovo.py", "content": "VALORE = 7\n"})
            assert scrittura.get("isError") is not True, scrittura
            assert (radice / "core" / "nuovo.py").read_text(encoding="utf-8") == "VALORE = 7\n"
            lettura = cliente.call_tool("read_file_window", {"path": "core/nuovo.py"})
            assert "VALORE = 7" in _testo(lettura)
        finally:
            cliente.disconnect()

    def test_in_modalita_manuale_non_scrive_e_lo_dice(self, radice):
        """Senza assenso umano un client esterno non scrive: e lo viene a sapere."""
        cliente = self._cliente(radice, automatico=False)
        try:
            assert cliente.connect().get("connected") is True
            esito = cliente.call_tool("write_file",
                                      {"path": "core/nuovo.py", "content": "x = 1\n"})
            assert esito.get("isError") is True, esito
            assert "await_approval" in _testo(esito), _testo(esito)
            assert not (radice / "core" / "nuovo.py").exists(), "ha scritto senza assenso"
            stato = cliente.call_tool("approval_status", {})
            assert "\"quante\": 1" in _testo(stato), _testo(stato)
        finally:
            cliente.disconnect()

    def test_il_canale_resta_pulito(self, radice):
        richieste = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        ingresso = (chr(10).join(json.dumps(r) for r in richieste) + chr(10)).encode("utf-8")
        esito = subprocess.run(
            [sys.executable, "-m", "core.modules.sigma_developer_lab.mcp_tools.hub_stdio"],
            input=ingresso, capture_output=True, cwd=str(RADICE_PROGETTO),
            env={**os.environ, VAR_RADICE: str(radice), "SIGMA_MCP_ONLY": "Developer Files"},
            timeout=180)
        righe = [r for r in esito.stdout.decode("utf-8", errors="replace").splitlines() if r.strip()]
        assert righe, "il server non ha risposto"
        for riga in righe:
            assert riga.lstrip().startswith("{"), "riga non protocollare: %r" % riga[:90]
            assert json.loads(riga).get("jsonrpc") == "2.0"

