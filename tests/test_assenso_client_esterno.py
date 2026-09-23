"""L'assenso sui tool sensibili, quando a chiedere e' un client esterno.

Il cancello esisteva ma non attraversava il confine fra processi: le richieste in
attesa vivevano in un dizionario in memoria, e chi deve approvarle - l'app - e'
un processo diverso. Un client collegato via stdio, quindi, non aveva nessun modo
di farsi approvare una scrittura: o la modalita' automatica era accesa e
scriveva senza chiedere a nessuno, o restava muto e ripiegava sulla shell.

Peggio: l'identificativo della richiesta tornava al richiedente, e prenderla in
carico non chiedeva *chi* la stesse prendendo. Cioe' il client poteva
auto-approvarsi riprovando con l'identificativo che la richiesta stessa gli aveva
appena consegnato: un cancello che si apre dall'interno non e' un cancello.

Adesso: la richiesta di un processo esterno vive in un file sotto `var/`, l'app
la vede, l'umano decide, l'app esegue, e chi ha chiesto legge l'esito. Chi chiede
non approva, mai.

Si verifica: che riprovare con l'identificativo non esegua niente, che la
richiesta si veda da un altro processo, che l'assenso e il rifiuto arrivino a chi
aspetta, e che il percorso interno (chat, Home Assistant) resti quello di prima.
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from core.mcp import governance
from core.mcp.mcp_hub import mcp_hub
from core.modules.sigma_developer_lab.handlers import register_mcp
from core.modules.sigma_developer_lab.mcp_tools.fs_server import VAR_RADICE
from core.modules.sigma_developer_lab.mcp_tools.hub_stdio import HubMCPServer

CLIENTE = "Cline"
RADICE_PROGETTO = Path(__file__).resolve().parent.parent


def _testo(esito):
    return esito["content"][0]["text"]


@pytest.fixture(scope="module")
def hub():
    """L'hub con i server del modulo, registrati una volta sola."""
    if not mcp_hub.find_tool("write_file"):
        register_mcp(mcp_hub)
    return mcp_hub


@pytest.fixture(autouse=True)
def processo_pulito(tmp_path, monkeypatch):
    """Policy esplicita e archivio delle richieste dentro la cartella di prova.

    Senza dirottare `CONFIG_PATH` questi test leggerebbero il `config.json` della
    macchina, dove la modalita' automatica puo' essere accesa - e allora il
    cancello non scatterebbe e i test direbbero il falso.
    """
    configurazione = tmp_path / "config.json"
    configurazione.write_text(json.dumps({"mcp": {"auto_approve": False}}),
                              encoding="utf-8")
    monkeypatch.setattr(governance, "CONFIG_PATH", str(configurazione))
    monkeypatch.setattr(governance, "shared_dir", lambda: tmp_path / "approvazioni")
    governance.reset_pending()
    yield
    governance.reset_pending()


@pytest.fixture
def radice(tmp_path, monkeypatch):
    monkeypatch.setenv(VAR_RADICE, str(tmp_path))
    (tmp_path / "core").mkdir(exist_ok=True)
    return tmp_path


def _apri(hub, contenuto="VALORE = 1\n"):
    """Chiede una scrittura sensibile da fuori e restituisce l'esito."""
    return hub.execute_tool("write_file",
                            {"path": "core/nuovo.py", "content": contenuto},
                            client=CLIENTE)


class TestIlClientEsternoNonSiAutoApprova:
    def test_la_scrittura_viene_parcheggiata_e_non_eseguita(self, hub, radice):
        esito = _apri(hub)
        assert esito["status"] == "confirmation_required", esito
        assert esito["approval"]["client"] == CLIENTE
        assert not (radice / "core" / "nuovo.py").exists(), "ha scritto senza assenso"

    def test_riprovare_con_l_identificativo_non_esegue(self, hub, radice):
        """Il buco: l'identificativo tornava al richiedente e bastava quello."""
        prima = _apri(hub)
        richiesta = prima["approval"]["request_id"]
        ripresa = hub.execute_tool("write_file", {},
                                   approval_id=richiesta, client=CLIENTE)
        assert ripresa["status"] == "error", ripresa
        # Il motivo esatto conta: "attende ancora" e "non e' tua" chiedono mosse
        # diverse a chi legge, e qui la verita' e' che nessuno ha ancora deciso.
        assert "attende ancora l'assenso umano" in ripresa["error"], ripresa
        assert not (radice / "core" / "nuovo.py").exists(), "si e' auto-approvato"

    def test_un_altro_client_non_puo_prendere_un_assenso(self, hub, radice):
        richiesta = _apri(hub)["approval"]["request_id"]
        governance.confirm_approval(richiesta, approved=True, by="operatore")
        furto = hub.execute_tool("write_file", {},
                                 approval_id=richiesta, client="un altro client")
        assert furto["status"] == "error", furto
        assert "applicazione" in furto["error"], furto
        assert not (radice / "core" / "nuovo.py").exists(), "assenso rubato"

    def test_il_messaggio_insegna_la_mossa_giusta(self, hub, radice):
        server = HubMCPServer(hub=hub)
        esito = server._chiama("write_file",
                               {"path": "core/nuovo.py", "content": "x = 1\n"})
        testo = _testo(esito)
        assert esito.get("isError") is True
        assert "await_approval" in testo, testo
        assert "scheda MCP" in testo, testo

    def test_lo_stato_delle_richieste_si_legge(self, hub, radice):
        richiesta = _apri(hub)["approval"]["request_id"]
        server = HubMCPServer(hub=hub)
        elenco = json.loads(_testo(server._chiama("approval_status", {})))
        assert elenco["quante"] == 1
        assert elenco["in_attesa"][0]["client"] == CLIENTE
        una = json.loads(_testo(server._chiama("approval_status",
                                               {"request_id": richiesta})))
        assert una["status"] == governance.PENDING
        assert una["tool"] == "write_file"


class TestLAppVedeEDecide:
    def test_la_richiesta_si_vede_da_un_altro_processo(self, hub, radice, monkeypatch):
        """L'app e' un altro processo: la memoria del figlio non la raggiunge."""
        richiesta = _apri(hub)["approval"]["request_id"]
        monkeypatch.setattr(governance, "_pending", {})
        attese = governance.list_pending()
        assert [r["request_id"] for r in attese] == [richiesta]
        assert attese[0]["status"] == governance.PENDING

    def test_l_operatore_approva_e_l_app_esegue(self, hub, radice, monkeypatch):
        richiesta = _apri(hub)["approval"]["request_id"]
        monkeypatch.setattr(governance, "_pending", {})
        assert governance.confirm_approval(richiesta, approved=True,
                                           by="operatore") is not None
        esito = hub.execute_tool("", {}, approval_id=richiesta)
        assert esito["status"] == "ok", esito
        assert (radice / "core" / "nuovo.py").read_text(encoding="utf-8") == "VALORE = 1\n"
        record = governance.get_approval(richiesta)
        assert record["status"] == governance.DONE
        assert record["confirmed_by"] == "operatore"
        assert "salvato" in record["output"].lower(), record["output"]

    def test_chi_ha_chiesto_legge_l_esito(self, hub, radice):
        """Il client aspetta: la chiamata gli torna con il risultato dentro."""
        richiesta = _apri(hub)["approval"]["request_id"]
        server = HubMCPServer(hub=hub)
        raccolta = {}

        def attesa():
            raccolta["esito"] = server._attendi_assenso(
                {"request_id": richiesta, "timeout_seconds": 30})

        filo = threading.Thread(target=attesa, daemon=True)
        filo.start()
        time.sleep(0.4)
        assert filo.is_alive(), "ha risposto prima che qualcuno decidesse"

        # Il ruolo dell'app: prima il verdetto umano, poi l'esecuzione.
        governance.confirm_approval(richiesta, approved=True, by="operatore")
        hub.execute_tool("", {}, approval_id=richiesta)
        filo.join(timeout=15)
        assert not filo.is_alive(), "l'attesa non e' finita dopo l'esito"
        letto = _testo(raccolta["esito"])
        assert "Approvata ed eseguita" in letto, letto
        assert "salvato" in letto.lower(), letto

    def test_il_rifiuto_non_esegue_e_si_legge(self, hub, radice):
        richiesta = _apri(hub)["approval"]["request_id"]
        governance.confirm_approval(richiesta, approved=False, by="operatore")
        esito = hub.execute_tool("", {}, approval_id=richiesta)
        assert esito["status"] == "error"
        assert "rifiutata" in esito["error"]
        assert not (radice / "core" / "nuovo.py").exists()
        letto = _testo(HubMCPServer(hub=hub)._attendi_assenso(
            {"request_id": richiesta, "timeout_seconds": 5}))
        assert "Rifiutata" in letto, letto

    def test_scaduta_l_attesa_lo_dice(self, hub, radice):
        richiesta = _apri(hub)["approval"]["request_id"]
        letto = _testo(HubMCPServer(hub=hub)._attendi_assenso(
            {"request_id": richiesta, "timeout_seconds": 1}))
        assert "Ancora in attesa" in letto, letto


class TestIlPercorsoInternoNonCambia:
    """Chat e Home Assistant: li' il clic dell'operatore *e'* il consenso."""

    def test_creare_e_prendere_senza_client(self):
        record = governance.create_approval("ha_light_set", {"state": "on"},
                                            "Home Assistant")
        preso = governance.take_approval(record["request_id"])
        assert preso and preso["tool"] == "ha_light_set"
        assert governance.take_approval(record["request_id"]) is None, "riusabile"

    def test_una_richiesta_interna_non_finisce_su_disco(self):
        record = governance.create_approval("send_email", {"to": "x"}, "Mail")
        assert not governance._file_di(record["request_id"]).exists()

    def test_un_rifiuto_non_si_esegue_nemmeno_da_dentro(self):
        record = governance.create_approval("send_email", {"to": "x"}, "Mail")
        governance.confirm_approval(record["request_id"], approved=False)
        assert governance.take_approval(record["request_id"]) is None


class TestDueProcessiVeri:
    """Il giro intero: il figlio chiede, il padre approva ed esegue, il figlio legge.

    Qui non si simula niente: il client e' un processo vero che parla su stdio, e
    fra i due c'e' solo il file delle richieste. E' la topologia reale di Sigma
    Studio con Cline collegato.
    """

    def test_dal_parcheggio_all_esito_attraverso_il_file(self, hub, tmp_path, monkeypatch):
        from core.mcp.client import ExternalMCPServer

        casa = tmp_path / "casa"
        (casa / "config").mkdir(parents=True)
        (casa / "config" / "config.json").write_text(
            json.dumps({"mcp": {"auto_approve": False}}), encoding="utf-8")
        progetto = tmp_path / "progetto"
        (progetto / "core").mkdir(parents=True)
        monkeypatch.setenv(VAR_RADICE, str(progetto))
        monkeypatch.setattr(governance, "shared_dir",
                            lambda: casa / "var" / "mcp" / "approvals")
        governance.reset_pending()

        cliente = ExternalMCPServer({
            "id": "sigma-prova",
            "name": "Hub di prova",
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "core.modules.sigma_developer_lab.mcp_tools.hub_stdio"],
            "env": {"SIGMA_HOME": str(casa), VAR_RADICE: str(progetto),
                    "SIGMA_MCP_ONLY": "Developer Files", "SIGMA_MCP_CLIENT": "Cline"},
            "cwd": str(RADICE_PROGETTO),
        })
        try:
            assert cliente.connect().get("connected") is True
            esito = cliente.call_tool("write_file",
                                      {"path": "core/nuovo.py", "content": "VALORE = 9\n"})
            assert esito.get("isError") is True, esito
            assert "await_approval" in _testo(esito)
            assert not (progetto / "core" / "nuovo.py").exists(), "ha scritto senza assenso"

            # Il ruolo dell'app: vede la richiesta (da un altro processo), decide
            # l'umano, esegue l'applicazione.
            attese = governance.list_pending()
            assert len(attese) == 1, attese
            richiesta = attese[0]["request_id"]
            assert attese[0]["client"] == "Cline"

            governance.confirm_approval(richiesta, approved=True, by="operatore")
            eseguita = hub.execute_tool("", {}, approval_id=richiesta)
            assert eseguita["status"] == "ok", eseguita
            assert (progetto / "core" / "nuovo.py").read_text(encoding="utf-8") == "VALORE = 9\n"

            # E il figlio lo viene a sapere dalla sua richiesta di attesa.
            letto = _testo(cliente.call_tool("await_approval",
                                             {"request_id": richiesta,
                                              "timeout_seconds": 10}))
            assert "Approvata ed eseguita" in letto, letto
            assert "salvato" in letto.lower(), letto
        finally:
            cliente.disconnect()
            governance.reset_pending()
