"""Le primitive di filesystem dell harness, esposte come server MCP.

Perche serve: nel Developer Studio i tool che scrivono file non passano dall hub
MCP - sono `LOCAL_TOOLS` del ciclo - quindi un agente **esterno** non aveva modo
di scrivere con le stesse garanzie (backup automatico, controllo di sintassi,
diagnostica). Finiva per usare la shell: e il caso dei dieci estratti in
`tools/*_src.txt`, tutti illeggibili, tutti invisibili al registro.

Questo server espone quattro tool - lettura a finestre, modifica per frammento
esatto, scrittura, aggiunta in coda - e nient altro. Si spegne come ogni altro
server MCP, e i tre tool di scrittura nascono SENSITIVE: la prima volta chiedono
un assenso. Ogni tentativo di scrittura lascia una riga nel diario del modulo.

Si verifica: cosa espone, che un percorso fuori dalla radice venga rifiutato, che
la diagnostica della patch sbagliata arrivi intera, che il guard contro i
troncamenti tenga, che il diario registri anche i rifiuti senza poter fermare una
scrittura, che sia registrabile e disattivabile nell hub, e soprattutto che un
client MCP esterno - quello che Sigma Studio usa per i server di terzi - riesca a
parlarci su stdio.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.mcp.client import ExternalMCPServer
from core.mcp.mcp_hub import MCPHub
from core.modules.sigma_developer_lab.handlers import register_mcp
from core.modules.sigma_developer_lab.mcp_tools import fs_server as modulo_fs
from core.modules.sigma_developer_lab.mcp_tools.fs_server import (
    DeveloperFsMCPServer,
    VAR_DIARIO,
    VAR_RADICE,
)

RADICE_PROGETTO = Path(__file__).resolve().parent.parent
NOME_SERVER = "Developer Files"


def _testo(esito):
    return esito["content"][0]["text"]


@pytest.fixture(autouse=True)
def diario_provvisorio(tmp_path, monkeypatch):
    """Il diario dei test non deve essere quello dell installazione vera."""
    percorso = tmp_path / "diario-scritture.jsonl"
    monkeypatch.setenv(VAR_DIARIO, str(percorso))
    return percorso


def _righe_diario(percorso):
    if not percorso.exists():
        return []
    return [json.loads(r) for r in percorso.read_text(encoding="utf-8").splitlines() if r.strip()]


@pytest.fixture
def radice(tmp_path, monkeypatch):
    monkeypatch.setenv(VAR_RADICE, str(tmp_path))
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "modulo.py").write_text(
        "def saluta(nome):\n    return \"ciao \" + nome\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def server(radice):
    return DeveloperFsMCPServer()


class TestCosaEspone:
    def test_i_cinque_tool(self, server):
        nomi = [t["name"] for t in server.list_tools()]
        assert nomi == ["read_file_window", "edit_file_exact", "write_file",
                        "append_file", "read_write_journal"]

    def test_le_scritture_sono_sensibili(self, server):
        classi = {t["name"]: t["safety"] for t in server.list_tools()}
        assert classi["read_file_window"] == "safe"
        for nome in ("edit_file_exact", "write_file", "append_file"):
            assert classi[nome] == "sensitive"

    def test_ogni_tool_ha_il_suo_schema(self, server):
        for tool in server.list_tools():
            schema = tool.get("inputSchema") or {}
            assert schema.get("type") == "object", tool["name"]
            # `required` c'e' sempre, anche vuoto: un tool senza parametri
            # obbligatori lo dichiara, e chi legge lo schema non deve indovinare.
            assert "required" in schema, tool["name"]
            for nome, campo in (schema.get("properties") or {}).items():
                assert campo.get("type"), (tool["name"], nome)


class TestLaLettura:
    def test_una_finestra_con_i_numeri_di_riga(self, server):
        esito = server.call_tool("read_file_window",
                                 {"path": "core/modulo.py", "limit": 2})
        testo = _testo(esito)
        assert "righe 1-2 di 2" in testo
        assert "def saluta" in testo

    def test_oltre_la_fine_lo_dice(self, radice, server):
        (radice / "lungo.txt").write_text("\n".join(str(i) for i in range(30)),
                                          encoding="utf-8")
        testo = _testo(server.call_tool("read_file_window",
                                        {"path": "lungo.txt", "limit": 10}))
        assert "continua oltre la riga 10" in testo
        assert "offset=11" in testo


class TestLaModifica:
    def test_sostituisce_un_frammento(self, radice, server):
        esito = server.call_tool("edit_file_exact", {
            "path": "core/modulo.py",
            "old_string": "return \"ciao \" + nome",
            "new_string": "return f\"ciao {nome}\""})
        assert "Modificato" in _testo(esito)
        assert "f\"ciao {nome}\"" in (radice / "core" / "modulo.py").read_text(encoding="utf-8")

    def test_la_patch_sbagliata_porta_la_diagnostica(self, server):
        esito = server.call_tool("edit_file_exact", {
            "path": "core/modulo.py",
            "old_string": "    return \"ciao\" + nome",
            "new_string": "return 1"})
        testo = _testo(esito)
        assert esito.get("isError") is True
        assert "somiglianza" in testo or "simile" in testo
        assert "riga" in testo


class TestLeGuardie:
    def test_fuori_dalla_radice_si_rifiuta(self, server):
        esito = server.call_tool("write_file",
                                 {"path": "../fuori.txt", "content": "x"})
        assert esito.get("isError") is True
        assert "fuori dalla cartella" in _testo(esito)

    def test_un_assoluto_altrove_si_rifiuta(self, server, tmp_path):
        altrove = str(Path(tmp_path).parent / "altrove.txt")
        esito = server.call_tool("write_file", {"path": altrove, "content": "x"})
        assert esito.get("isError") is True

    def test_il_troncamento_involontario_si_rifiuta(self, radice, server):
        (radice / "grande.py").write_text("x = 1\n" * 200, encoding="utf-8")
        esito = server.call_tool("write_file",
                                 {"path": "grande.py", "content": "x = 2\n"})
        assert esito.get("isError") is True
        assert "allow_truncate" in _testo(esito)
        assert (radice / "grande.py").read_text(encoding="utf-8").count("x = 1") == 200

    def test_e_si_puo_volere(self, radice, server):
        (radice / "grande.py").write_text("x = 1\n" * 200, encoding="utf-8")
        esito = server.call_tool("write_file", {
            "path": "grande.py", "content": "x = 2\n", "allow_truncate": True})
        assert esito.get("isError") is None


class TestNellHub:
    def test_si_registra_e_si_disattiva(self):
        hub = MCPHub()
        register_mcp(hub)
        nomi = [s["name"] for s in hub.list_all_servers()]
        assert NOME_SERVER in nomi, nomi
        strumenti = [t["name"] for t in hub.get_aggregated_tools()]
        assert "edit_file_exact" in strumenti
        assert hub.unregister_server(NOME_SERVER) is True
        assert NOME_SERVER not in [s["name"] for s in hub.list_all_servers()]


class TestUnClientEsternoCiParla:
    def _cliente(self, radice, automatico=True):
        """Un client sulla porta minima, con l'installazione e la policy decise qui.

        Senza `SIGMA_HOME` il figlio leggerebbe il `config.json` della macchina,
        dove la modalita' automatica puo' essere accesa o spenta: il test
        direbbe cose diverse su macchine diverse.
        """
        casa = Path(radice) / ".casa-porta-minima"
        (casa / "config").mkdir(parents=True, exist_ok=True)
        (casa / "config" / "config.json").write_text(
            json.dumps({"mcp": {"auto_approve": bool(automatico)}}), encoding="utf-8")
        return ExternalMCPServer({
            "id": "fs-prova",
            "name": "File di sviluppo (prova)",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "core.modules.sigma_developer_lab.mcp_tools.fs_stdio"],
            "env": {VAR_RADICE: str(radice), "SIGMA_HOME": str(casa),
                    "SIGMA_MCP_CLIENT": "prova"},
            "cwd": str(RADICE_PROGETTO),
        })

    def test_giro_completo_su_stdio(self, radice, diario_provvisorio):
        cliente = self._cliente(radice)
        try:
            stato = cliente.connect()
            assert stato.get("connected") is True, stato
            nomi = sorted(t["name"] for t in cliente.list_tools())
            # I cinque tool dei file piu' i due del trasporto: da quando questa
            # porta passa dall'hub li porta anche lei, ed e' il motivo per cui
            # adesso un assenso si puo' chiedere e si puo' aspettare.
            assert nomi == ["append_file", "approval_status", "await_approval",
                            "edit_file_exact", "read_file_window",
                            "read_write_journal", "write_file"]

            scrittura = cliente.call_tool("write_file", {
                "path": "core/nuovo.py", "content": "VALORE = 42\n"})
            assert scrittura.get("isError") is not True, scrittura
            assert (radice / "core" / "nuovo.py").read_text(encoding="utf-8") == "VALORE = 42\n"

            modifica = cliente.call_tool("edit_file_exact", {
                "path": "core/nuovo.py", "old_string": "42", "new_string": "43"})
            assert modifica.get("isError") is not True, modifica
            assert "43" in (radice / "core" / "nuovo.py").read_text(encoding="utf-8")

            lettura = cliente.call_tool("read_file_window", {"path": "core/nuovo.py"})
            assert "VALORE = 43" in _testo(lettura)

            # Il processo figlio ha scritto nel diario passato per ambiente: senza
            # quello, la traccia di un client esterno sarebbe quella dell
            # installazione vera, e i test la sporcherebbero.
            diario = _righe_diario(diario_provvisorio)
            assert [r["esito"] for r in diario] == ["scritto", "modificato"], diario
        finally:
            cliente.disconnect()

    def test_in_manuale_non_scrive_perche_il_cancello_c_e(self, radice):
        """Il buco che questa porta aveva: scriveva senza chiedere a nessuno.

        Fino al 23 settembre 2026 `fs_stdio` chiamava il server dei file diretto:
        nessuna policy, nessun assenso, e una docstring che prometteva il
        contrario. Qui si verifica che adesso la scrittura si ferma in attesa.
        """
        cliente = self._cliente(radice, automatico=False)
        try:
            assert cliente.connect().get("connected") is True
            esito = cliente.call_tool("write_file",
                                      {"path": "core/nuovo.py", "content": "VALORE = 1\n"})
            assert esito.get("isError") is True, esito
            assert "await_approval" in _testo(esito), _testo(esito)
            assert not (radice / "core" / "nuovo.py").exists(), "ha scritto senza assenso"
        finally:
            cliente.disconnect()

    def test_il_canale_del_protocollo_resta_pulito(self, radice):
        # Ogni riga su stdout deve essere un messaggio JSON-RPC. Il logger del
        # programma si lega a `sys.stdout` quando viene importato, e in un
        # processo figlio quello e il canale dei messaggi: una riga di log li
        # dentro e un messaggio che il client non sa leggere. Succedeva, e si
        # vedeva solo guardando il flusso grezzo.
        richieste = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        ingresso = (chr(10).join(json.dumps(r) for r in richieste) + chr(10)).encode("utf-8")
        esito = subprocess.run(
            [sys.executable, "-m", "core.modules.sigma_developer_lab.mcp_tools.fs_stdio"],
            input=ingresso, capture_output=True, cwd=str(RADICE_PROGETTO),
            env={**os.environ, VAR_RADICE: str(radice)}, timeout=120)
        righe = [r for r in esito.stdout.decode("utf-8", errors="replace").splitlines()
                 if r.strip()]
        assert righe, "il server non ha risposto"
        for riga in righe:
            assert riga.lstrip().startswith("{"), (
                "riga non protocollare su stdout: %r" % riga[:90])
            assert json.loads(riga).get("jsonrpc") == "2.0"
        errori = esito.stderr.decode("utf-8", errors="replace")
        assert "Registered MCP Server" in errori, "i log devono finire su stderr"


class TestIlDiarioDelleScritture:
    """Chi arriva da fuori scrive, ma non di nascosto."""

    def test_una_scrittura_lascia_una_riga(self, radice, server, diario_provvisorio):
        server.call_tool("write_file", {"path": "core/nuovo.py", "content": "VALORE = 1\n"})
        righe = _righe_diario(diario_provvisorio)
        assert len(righe) == 1
        voce = righe[0]
        assert voce["tool"] == "write_file"
        assert voce["esito"] == "scritto"
        assert voce["path"].endswith("nuovo.py")
        # Il byte registrato deve essere quello vero: su Windows `write_text`
        # traduce i ritorni a capo, quindi contare qui a mano sarebbe sbagliato.
        assert voce["byte"] == (radice / "core" / "nuovo.py").stat().st_size
        assert voce["quando"], "senza orario la traccia non dice quando"

    def test_il_backup_resta_nella_riga(self, radice, server, diario_provvisorio):
        (radice / "core" / "modulo.py").write_text(
            "def saluta(nome):\n    return \"ciao \" + nome\n# una nota in piu\n",
            encoding="utf-8")
        server.call_tool("write_file", {
            "path": "core/modulo.py",
            "content": "def saluta(nome):\n    return \"salve \" + nome\n# una nota in piu\n"})
        voce = _righe_diario(diario_provvisorio)[0]
        assert voce["backup"], "una riscrittura senza backup_id non e annullabile"

    def test_anche_i_rifiuti_finiscono_nel_diario(self, radice, server, diario_provvisorio):
        # La guardia anti-troncamento non scatta sui file minuscoli - sarebbe
        # rumore - quindi il rifiuto si provoca su un file lungo.
        prima = "x = 1\n" * 200
        (radice / "grande.py").write_text(prima, encoding="utf-8")
        esito = server.call_tool("write_file", {"path": "grande.py", "content": "x = 2\n"})
        assert esito.get("isError") is True
        righe = _righe_diario(diario_provvisorio)
        assert [r["esito"] for r in righe] == ["rifiutato"]
        assert "troncamento" in righe[0]["motivo"]
        assert (radice / "grande.py").read_text(encoding="utf-8") == prima

    def test_un_percorso_fuori_radice_viene_annotato(self, server, diario_provvisorio):
        server.call_tool("write_file", {"path": "../fuori.py", "content": "x = 1\n"})
        voce = _righe_diario(diario_provvisorio)[0]
        assert voce["esito"] == "fuori radice"
        assert voce["path"] == "../fuori.py"

    def test_la_modifica_esatta_e_annotata(self, server, diario_provvisorio):
        server.call_tool("edit_file_exact", {
            "path": "core/modulo.py", "old_string": "ciao ", "new_string": "salve "})
        voce = _righe_diario(diario_provvisorio)[0]
        assert voce["tool"] == "edit_file_exact"
        assert voce["esito"] == "modificato"
        assert "->" in voce["righe"]

    def test_una_lettura_non_sporca_il_diario(self, server, diario_provvisorio):
        server.call_tool("read_file_window", {"path": "core/modulo.py"})
        assert _righe_diario(diario_provvisorio) == []

    def test_un_diario_impossibile_non_ferma_la_scrittura(self, radice, server, tmp_path, monkeypatch):
        # Prima la modifica, poi la traccia: un diario che impedisce la scrittura
        # che doveva registrare e peggio del diario mancante.
        blocco = tmp_path / "blocco"
        blocco.write_text("sono un file, non una cartella\n", encoding="utf-8")
        monkeypatch.setenv(VAR_DIARIO, str(blocco / "diario.jsonl"))
        esito = server.call_tool("write_file", {"path": "core/nuovo.py", "content": "VALORE = 7\n"})
        assert esito.get("isError") is not True, esito
        assert (radice / "core" / "nuovo.py").read_text(encoding="utf-8") == "VALORE = 7\n"


class TestIlDiarioSiRilegge:
    """Una traccia che nessuno legge non e' una traccia: e' un file che cresce."""

    def test_la_riga_dice_chi_ha_scritto(self, radice, server, diario_provvisorio,
                                         monkeypatch):
        monkeypatch.setenv("SIGMA_MCP_CLIENT", "Cline")
        server.call_tool("write_file", {"path": "core/nuovo.py", "content": "VALORE = 1\n"})
        voce = _righe_diario(diario_provvisorio)[0]
        assert voce["chi"] == "Cline"
        assert isinstance(voce["pid"], int), "senza pid due client si confondono"

    def test_senza_client_la_riga_dice_sigma_studio(self, radice, server, diario_provvisorio,
                                                     monkeypatch):
        monkeypatch.delenv("SIGMA_MCP_CLIENT", raising=False)
        server.call_tool("append_file", {"path": "core/nuovo.py", "content": "x\n"})
        assert _righe_diario(diario_provvisorio)[0]["chi"] == "sigma-studio"

    def test_si_filtra_per_esito_e_per_percorso(self, radice, server, diario_provvisorio):
        server.call_tool("write_file", {"path": "core/nuovo.py", "content": "x = 1\n"})
        (radice / "grande.py").write_text("x = 1\n" * 200, encoding="utf-8")
        server.call_tool("write_file", {"path": "grande.py", "content": "x = 2\n"})
        server.call_tool("read_file_window", {"path": "core/nuovo.py"})

        tutto = json.loads(_testo(server.call_tool("read_write_journal", {})))
        assert tutto["totale"] == 2, "le letture non entrano nel diario"

        rifiuti = json.loads(_testo(server.call_tool("read_write_journal",
                                                     {"esito": "rifiutato"})))
        assert [r["path"] for r in rifiuti["righe"]] == ["grande.py"]
        assert "troncamento" in rifiuti["righe"][0]["motivo"]

        mirato = json.loads(_testo(server.call_tool("read_write_journal",
                                                    {"path": "core/nuovo"})))
        assert mirato["mostrate"] == 1
        assert mirato["righe"][0]["esito"] == "scritto"

    def test_un_diario_vuoto_lo_dice(self, server):
        assert "vuoto" in _testo(server.call_tool("read_write_journal", {}))

    def test_il_diario_gira_pagina(self, radice, server, diario_provvisorio, monkeypatch):
        tetto = 1200
        monkeypatch.setattr(modulo_fs, "TETTO_DIARIO", tetto)
        for indice in range(20):
            server.call_tool("write_file",
                             {"path": "core/f%d.py" % indice, "content": "x = %d\n" % indice})
        precedente = diario_provvisorio.with_suffix(".1.jsonl")
        assert precedente.is_file(), "il diario cresce senza fine"
        nuove = _righe_diario(diario_provvisorio)
        # La rotazione avviene *prima* della riga nuova, quindi la pagina in corso
        # puo' superare il tetto di una riga, non di piu'.
        assert len(nuove) < 20, "non ha mai girato pagina"
        assert diario_provvisorio.stat().st_size <= tetto + 600
        assert _righe_diario(precedente), "la pagina precedente e' vuota"
        assert nuove[-1]["path"].endswith("f19.py"), "la storia non finisce dove deve"
