"""Da dove viene lo stato di lavoro all'inizio di un run.

Tre provenienze, e sbagliarne l'ordine costa in modi diversi. Prendere uno
stato nuovo quando ce n'era uno salvato fa rileggere tutto. Prendere quello
salvato quando l'orchestratore ne ha passato uno proprio spezza la squadra:
il Tester tornerebbe a non sapere cosa ha scritto il Coder. Prendere quello
salvato di un altro workspace e' il caso peggiore, perche' l'agente ci crede.
"""

import pytest

from core.developer_studio import session_store
from core.developer_studio.admin_agent import resolve_ledger
from core.developer_studio.session_ledger import DevSessionLedger

WS = "C:/progetto"


@pytest.fixture
def store_isolato(tmp_path, monkeypatch):
    cartella = tmp_path / "dev_sessions"
    monkeypatch.setattr(session_store, "dev_sessions_dir", lambda: cartella)
    monkeypatch.setattr(session_store, "SAVE_INTERVAL_S", 0.0)
    session_store._last_save.clear()
    return cartella


def _con_una_lettura(goal="Correggi core/x.py", root=WS):
    ledger = DevSessionLedger(goal=goal, workspace_root=root)
    ledger.record_tool(
        "read_file",
        {"path": f"{root}/core/x.py"},
        {"success": True, "path": f"{root}/core/x.py", "offset": 1,
         "last_line": 9, "total_lines": 9, "content": "VALORE = 1"},
    )
    return ledger


class TestPrecedenza:
    def test_il_ledger_passato_vince_su_tutto(self, store_isolato):
        """E' l'orchestratore: i ruoli devono condividere lo stesso stato."""
        session_store.save("s1", _con_una_lettura(goal="salvato"), force=True)
        proprio = DevSessionLedger(goal="passato", workspace_root=WS)

        ledger, ripreso = resolve_ledger("s1", proprio, "passato", WS)

        assert ledger is proprio
        assert ripreso is False

    def test_senza_ledger_si_riprende_la_sessione(self, store_isolato):
        session_store.save("s1", _con_una_lettura(), force=True)

        ledger, ripreso = resolve_ledger("s1", None, "Correggi core/x.py", WS)

        assert ripreso is True
        assert ledger.read_files  # il lavoro precedente e' tornato

    def test_senza_sessione_se_ne_crea_uno_nuovo(self, store_isolato):
        ledger, ripreso = resolve_ledger(None, None, "Nuovo obiettivo", WS)

        assert ripreso is False
        assert ledger.goal == "Nuovo obiettivo"
        assert ledger.read_files == []

    def test_una_sessione_mai_salvata_non_e_una_ripresa(self, store_isolato):
        ledger, ripreso = resolve_ledger("mai_vista", None, "obiettivo", WS)
        assert ripreso is False
        assert ledger.goal == "obiettivo"


class TestSicurezza:
    def test_lo_stato_di_un_altro_workspace_non_viene_ripreso(self, store_isolato):
        session_store.save("s1", _con_una_lettura(), force=True)

        ledger, ripreso = resolve_ledger("s1", None, "obiettivo", "D:/altro")

        assert ripreso is False
        assert ledger.read_files == []

    def test_uno_store_rotto_non_impedisce_il_run(self, store_isolato, monkeypatch):
        """Un ripristino fallito e' lento, un'eccezione qui e' fatale."""
        def esplodi(*_a, **_k):
            raise RuntimeError("store inservibile")
        monkeypatch.setattr(session_store, "load_ledger", esplodi)

        ledger, ripreso = resolve_ledger("s1", None, "obiettivo", WS)

        assert ripreso is False
        assert ledger.goal == "obiettivo"


class TestObiettivo:
    def test_un_ledger_passato_senza_obiettivo_lo_riceve(self):
        vuoto = DevSessionLedger(goal="", workspace_root=WS)
        ledger, _ = resolve_ledger(None, vuoto, "Obiettivo dal messaggio", WS)
        assert ledger.goal == "Obiettivo dal messaggio"

    def test_un_ledger_passato_con_obiettivo_lo_conserva(self):
        """L'obiettivo del ruolo non deve essere sovrascritto dal task del ruolo."""
        proprio = DevSessionLedger(goal="Obiettivo generale", workspace_root=WS)
        ledger, _ = resolve_ledger(None, proprio, "Sotto-task del ruolo", WS)
        assert ledger.goal == "Obiettivo generale"

    def test_riprendendo_l_obiettivo_si_aggiorna(self, store_isolato):
        """Domande in sequenza nella stessa sessione: cambia il fine, non i fatti."""
        session_store.save("s1", _con_una_lettura(goal="prima"), force=True)

        ledger, ripreso = resolve_ledger("s1", None, "poi", WS)

        assert ripreso is True
        assert ledger.goal == "poi"
        assert ledger.read_files
