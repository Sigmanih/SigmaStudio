"""Il resoconto deve dire cosa e' successo davvero, non cosa e' stato dichiarato.

Lo snapshot da cui parte il resoconto lo costruisce un `DevSessionLedger`
**vero**, alimentato dai risultati dei tool come nel ciclo reale. Il difetto
della chiave `modified_files` era sfuggito proprio a un test che lo snapshot se
lo costruiva a mano, con una chiave che nel ledger non esiste: era il finto a
nascondere il difetto.
"""

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.resoconto import narra, resoconto


@pytest.fixture
def ledger(tmp_path):
    return DevSessionLedger(goal="Rendere traducibile sigma_network",
                            workspace_root=str(tmp_path))


def _scrittura(ledger, percorso, righe=40):
    ledger.record_tool("write_file", {"path": percorso}, {
        "tool": "write_file", "success": True, "path": percorso,
        "full_path": percorso, "created": True,
        "content": "x\n" * righe, "lines": righe,
    })


def _comando(ledger, comando, rc=0, stdout=""):
    ledger.record_tool("terminal", {"command": comando}, {
        "tool": "terminal", "success": rc == 0, "command": comando,
        "returncode": rc, "stdout": stdout, "stderr": "",
    })


class TestIFattiFinisconoNelResoconto:
    def test_i_file_scritti_compaiono(self, ledger):
        _scrittura(ledger, "locales/it.json")
        testo = resoconto(ledger.snapshot())
        assert "locales/it.json" in testo
        assert "Cosa e' stato fatto" in testo

    def test_i_criteri_accettati_compaiono_con_il_loro_esito(self, ledger):
        registrati = ledger.set_spec(
            "Spostare le stringhe nel catalogo",
            ["il file locales/it.json esiste", "nessuna stringa resta nel jsx"],
        )
        assert len(registrati) == 2
        testo = resoconto(ledger.snapshot())
        assert "Criteri di accettazione" in testo
        assert "locales/it.json esiste" in testo

    def test_cosa_aveva_capito_compare(self, ledger):
        ledger.set_spec("Spostare le 34 stringhe nel catalogo", ["a"])
        assert "34 stringhe" in resoconto(ledger.snapshot())

    def test_la_verifica_eseguita_compare_con_i_numeri(self, ledger):
        _scrittura(ledger, "tools/check_i18n.py")
        _comando(ledger, "python -m pytest tests/ -q", rc=0,
                 stdout="11 passed in 0.4s")
        testo = resoconto(ledger.snapshot())
        assert "Come e' stato verificato" in testo
        assert "pytest" in testo
        assert "11 passati" in testo

    def test_un_comando_fallito_finisce_fra_i_guasti(self, ledger):
        _scrittura(ledger, "app.py")
        _comando(ledger, "python -m pytest tests/ -q", rc=1,
                 stdout="2 failed, 3 passed")
        testo = resoconto(ledger.snapshot())
        assert "Cosa non ha funzionato" in testo


class TestIlResocontoNonMente:
    def test_scrivere_senza_verificare_viene_detto(self, ledger):
        """E' il caso che il cancello di completamento esiste per impedire: se
        arriva fin qui, dirlo vale piu' che tacerlo."""
        _scrittura(ledger, "app.py")
        testo = resoconto(ledger.snapshot())
        assert "non e' dimostrato" in testo

    def test_un_echo_non_e_una_prova(self, ledger):
        """Solo i comandi che il ledger ha riconosciuto come verifiche."""
        _scrittura(ledger, "app.py")
        _comando(ledger, "echo fatto", rc=0, stdout="fatto")
        testo = resoconto(ledger.snapshot())
        assert "non e' dimostrato" in testo

    def test_un_run_che_non_ha_fatto_niente_lo_dice(self):
        assert "Nessun lavoro registrato" in resoconto({})

    def test_leggere_un_file_non_e_averci_fatto_qualcosa(self, ledger, tmp_path):
        percorso = tmp_path / "letto.py"
        percorso.write_text("x = 1\n", encoding="utf-8")
        ledger.record_tool("read_file", {"path": str(percorso)}, {
            "tool": "read_file", "success": True, "path": str(percorso),
            "full_path": str(percorso), "content": "x = 1\n", "total_lines": 1,
        })
        testo = resoconto(ledger.snapshot())
        assert "Cosa e' stato fatto" not in testo

    def test_un_obiettivo_non_chiuso_viene_dichiarato(self, ledger):
        _scrittura(ledger, "app.py")
        testo = resoconto(ledger.snapshot(), branch="sigma-run/x", raggiunto=False)
        assert "non** e' stato chiuso" in testo
        assert "sigma-run/x" in testo


class TestIlDiario:
    def test_una_scrittura_diventa_una_riga(self):
        riga = narra({"type": "tool_result", "tool": "write_file", "result": {
            "tool": "write_file", "success": True, "path": "src/App.jsx",
            "created": True}})
        assert riga and "App.jsx" in riga and "Creato" in riga

    def test_un_comando_riuscito_dice_l_uscita(self):
        riga = narra({"type": "tool_result", "tool": "terminal", "result": {
            "tool": "terminal", "success": True, "command": "npm run build",
            "returncode": 0}})
        assert riga and "npm run build" in riga and "uscita 0" in riga

    def test_un_comando_fallito_dice_perche(self):
        riga = narra({"type": "tool_result", "tool": "terminal", "result": {
            "tool": "terminal", "success": False, "command": "npm test",
            "returncode": 1, "error": "2 failing"}})
        assert riga and "uscita 1" in riga and "2 failing" in riga

    def test_leggere_non_merita_una_riga(self):
        """Raccontare ogni evento produce un elenco che nessuno legge."""
        assert narra({"type": "tool_result", "tool": "read_file", "result": {
            "tool": "read_file", "success": True, "path": "a.py"}}) is None

    def test_i_token_non_meritano_una_riga(self):
        assert narra({"type": "token", "token": "ciao"}) is None

    def test_il_piano_dice_quanti_task_e_quali_ruoli(self):
        riga = narra({"type": "pipeline_update", "tasks": [
            {"id": "1", "title": "x", "role": "coder"},
            {"id": "2", "title": "y", "role": "tester"},
        ]})
        assert riga and "2 task" in riga and "coder" in riga and "tester" in riga

    def test_una_chiusura_rifiutata_si_racconta(self):
        riga = narra({"type": "completion_rejected",
                      "reason": "nessuna verifica eseguita"})
        assert riga and "nessuna verifica" in riga

    def test_il_lavoro_non_atterrato_si_racconta(self):
        riga = narra({"type": "apply_failed", "error": "patch does not apply"})
        assert riga and "patch does not apply" in riga


class TestIlCorpoDellaRichiesta:
    def test_il_resoconto_finisce_nella_pull_request(self, ledger):
        from core.harness.delivery import _corpo_richiesta

        _scrittura(ledger, "locales/it.json")
        _comando(ledger, "python -m pytest tests/ -q", stdout="3 passed")
        racconto = resoconto(ledger.snapshot(), obiettivo="tradurre")
        corpo = _corpo_richiesta("tradurre", ["locales/it.json"],
                                 "sigma-run/abc", racconto)
        assert "Come e' stato verificato" in corpo
        assert "pytest" in corpo
        assert "sigma-run/abc" in corpo

    def test_senza_resoconto_il_corpo_resta_quello_di_prima(self):
        from core.harness.delivery import _corpo_richiesta

        corpo = _corpo_richiesta("tradurre", ["a.py"], "sigma-run/abc")
        assert "**Obiettivo:** tradurre" in corpo
        assert "a.py" in corpo


def test_il_ciclo_emette_il_diario_e_il_resoconto():
    """Un evento nuovo che nessuno spedisce e' il difetto piu' frequente di
    questo progetto: qui si verifica che i due punti d'emissione esistano."""
    import inspect

    from core.harness import loop

    guscio = inspect.getsource(loop.stream_admin_agent_turn)
    assert '"type": "diario"' in guscio
    assert "narra(evento)" in guscio

    ciclo = inspect.getsource(loop._stream_agent_turn_impl)
    assert '"type": "run_report"' in ciclo
