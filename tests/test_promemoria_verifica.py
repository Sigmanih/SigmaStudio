"""Chi scrive e non dimostra va fermato prima della fine, non dopo.

Il recupero dallo stallo copre l'esplorazione infinita: chi legge e rilegge
senza scrivere. Non copriva il caso opposto, ed e' quello che costa di piu':
`turn_was_productive` e' vero per **qualunque** tool riuscito, quindi un agente
che scrive dieci file di fila non accumula mai un turno improduttivo e non
viene mai interrotto.

Misurato su una prova dal vivo: ventisei turni, cinque file scritti, **zero
comandi eseguiti**, e il cancello che rifiuta la chiusura alla fine per una
verifica che nessuno aveva chiesto per tempo. Il difetto nel codice prodotto
sarebbe stato visibile alla prima esecuzione del test.
"""

import os

import pytest

from core.harness.ledger import DevSessionLedger
from core.harness.loop import SCRITTURE_SENZA_PROVA, _promemoria_di_verifica


@pytest.fixture
def ledger(tmp_path):
    return DevSessionLedger(goal="scrivi il modulo", workspace_root=str(tmp_path))


def _scrivi(ledger, tmp_path, quanti):
    for i in range(quanti):
        percorso = os.path.join(str(tmp_path), f"modulo_{i}.py")
        ledger.record_tool("write_file", {"path": percorso}, {
            "tool": "write_file", "success": True, "path": percorso,
            "full_path": percorso, "content": "x = 1\n", "created": True})


def _esegui(ledger, comando="python -m pytest -q", rc=0):
    ledger.record_tool("terminal", {"command": comando}, {
        "tool": "terminal", "success": rc == 0, "command": comando,
        "returncode": rc, "stdout": "2 passed" if rc == 0 else "", "stderr": ""})


class TestQuandoScatta:
    def test_tace_finche_le_scritture_sono_poche(self, ledger, tmp_path):
        """Una scrittura non ancora verificata e' il caso normale a meta'
        lavoro: interrompere li' sarebbe rumore a ogni run."""
        _scrivi(ledger, tmp_path, SCRITTURE_SENZA_PROVA - 1)
        assert _promemoria_di_verifica(ledger, "pytest -q") == ""

    def test_parla_quando_le_scritture_si_accumulano_senza_prove(self, ledger, tmp_path):
        _scrivi(ledger, tmp_path, SCRITTURE_SENZA_PROVA)
        riga = _promemoria_di_verifica(ledger, "python -m pytest tests/ -q")
        assert riga
        assert "python -m pytest tests/ -q" in riga, "deve dire QUALE comando"
        assert str(SCRITTURE_SENZA_PROVA) in riga, "e quanti file sono in ballo"

    def test_un_comando_riuscito_qualsiasi_lo_zittisce(self, ledger, tmp_path):
        """L'agente ha mostrato di saper eseguire: il resto lo valuta il
        cancello di completamento, che e' il posto giusto."""
        _scrivi(ledger, tmp_path, SCRITTURE_SENZA_PROVA + 2)
        _esegui(ledger)
        assert _promemoria_di_verifica(ledger, "pytest -q") == ""

    def test_un_comando_fallito_non_lo_zittisce(self, ledger, tmp_path):
        """Averci provato e non esserci riusciti non e' aver dimostrato."""
        _scrivi(ledger, tmp_path, SCRITTURE_SENZA_PROVA + 2)
        _esegui(ledger, rc=1)
        assert _promemoria_di_verifica(ledger, "pytest -q")

    def test_senza_scritture_non_dice_niente(self, ledger):
        assert _promemoria_di_verifica(ledger, "pytest -q") == ""


class TestCosaDice:
    def test_col_comando_dichiarato_lo_nomina(self, ledger, tmp_path):
        _scrivi(ledger, tmp_path, 4)
        riga = _promemoria_di_verifica(ledger, "npm run build")
        assert "npm run build" in riga
        assert "terminal" in riga

    def test_senza_comando_dichiarato_dice_come_sceglierlo(self, ledger, tmp_path):
        """Senza un'indicazione l'agente puo' restare fermo a chiedersi cosa
        contare come prova: qui gli si danno tre esempi concreti."""
        _scrivi(ledger, tmp_path, 4)
        riga = _promemoria_di_verifica(ledger)
        assert "import" in riga and "lint" in riga

    def test_dice_anche_perche_conviene_farlo_adesso(self, ledger, tmp_path):
        _scrivi(ledger, tmp_path, 4)
        riga = _promemoria_di_verifica(ledger, "pytest -q")
        assert "rifiutata" in riga


class TestIlCicloLoUsaDavvero:
    """Il difetto piu' frequente di questo progetto e' la funzione scritta,
    testata e mai chiamata."""

    def test_il_turno_lo_calcola(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "_promemoria_di_verifica(ledger, verify_command)" in sorgente
        assert "coda_verifica or STATE_TAIL_ACT" in sorgente

    def test_non_scatta_mentre_si_definiscono_i_criteri(self):
        """Il turno della `spec` ha gia' la sua coda, e sovrascriverla
        manderebbe l'agente a verificare prima di sapere cosa deve fare."""
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "if not needs_spec_turn and not goal_reached" in sorgente

    def test_chi_guarda_lo_vede(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "Scritture senza prove" in sorgente, (
            "un sollecito invisibile non si puo' diagnosticare")


def test_un_errore_di_programmazione_non_viene_inghiottito(ledger, tmp_path):
    """La prima versione avvolgeva tutto in `except Exception: return ""`.

    `successful_commands` e' un metodo e `modified_files` una proprieta': la
    `list()` sul metodo legato sollevava, l'eccezione veniva inghiottita, e il
    promemoria taceva sempre sembrando funzionare. Un `except` largo su codice
    che interroga un'API trasforma un difetto in silenzio.
    """
    _scrivi(ledger, tmp_path, 4)

    class LedgerRotto:
        modified_files = ["a.py", "b.py", "c.py", "d.py"]

        def successful_commands(self):
            raise RuntimeError("il ledger e' cambiato sotto")

    with pytest.raises(RuntimeError):
        _promemoria_di_verifica(LedgerRotto(), "pytest -q")
