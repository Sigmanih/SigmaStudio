"""Un file letto a pezzi non e un file letto: i buchi vanno nominati.

Il 23 settembre 2026 un agente ha letto `core/harness/loop.py` (4212 righe)
nelle finestre 1-1200 e 2400-2899 e ha passato gli ultimi dieci turni a cercare
la funzione che doveva modificare. Stava alla riga 2132, dentro il buco.

Il sistema lo sapeva: il ledger registra ogni finestra e sa dire "letto righe
1-1200, 2400-2899 di 4212". Sapeva anche che il rifiuto "lo hai gia letto",
ripetuto cinque volte su `gguf_converter.py` e quattro su `pcb-lab.css`, non
diceva mai *quale* finestra chiedere: diceva "usa un offset esplicito", e il
conto di cosa non si era visto restava a chi lo aveva chiesto.

Qui si verificano le tre correzioni: lo stato del lavoro nomina il buco, il
rifiuto porta una chiamata pronta, e durante il turno di recupero una finestra
mai vista non viene piu rifiutata come se fosse una rilettura.
"""

import inspect

from core.harness.ledger import DevSessionLedger
from core.harness.loop import _buchi_di_lettura, _finestra_suggerita

WS = "C:/progetto"
FILE = "core/harness/loop.py"


def _lettura(led, offset, last_line, total):
    led.record_tool(
        "read_file", {"path": f"{WS}/{FILE}"},
        {"success": True, "path": f"{WS}/{FILE}", "offset": offset,
         "last_line": last_line, "total_lines": total, "content": "..."},
    )
    return led


def _ledger_a_pezzi():
    """Le due finestre del run vero: 1-1200 e 2400-2899 di 4212 righe."""
    led = DevSessionLedger(goal="Implementa l intervento in loop.py", workspace_root=WS)
    _lettura(led, 1, 1200, 4212)
    _lettura(led, 2400, 2899, 4212)
    return led


class TestIlBucoVieneNominato:
    def test_lo_stato_dice_cosa_manca(self):
        stato = _ledger_a_pezzi().render_state_block()
        assert "manca 1201-2399, 2900-4212" in stato

    def test_le_finestre_mancanti_sono_in_ordine(self):
        assert _ledger_a_pezzi().gap_windows(f"{WS}/{FILE}") == [
            (1201, 800), (2001, 399), (2900, 800)]

    def test_la_finestra_pronta_da_emettere(self):
        riga = _finestra_suggerita(_ledger_a_pezzi(), f"{WS}/{FILE}", FILE)
        assert "read_file" in riga
        assert '"path": "' + FILE in riga
        assert '"offset": 1201' in riga
        assert '"limit": 800' in riga
        assert "dopo quella restano" in riga


class TestUnFileLettoTutto:
    def test_non_ha_finestre_mancanti(self):
        led = _lettura(DevSessionLedger(goal="x", workspace_root=WS), 1, 40, 40)
        assert led.gap_windows(f"{WS}/{FILE}") == []
        assert _finestra_suggerita(led, f"{WS}/{FILE}", FILE) == ""

    def test_e_lo_stato_lo_dice(self):
        led = _lettura(DevSessionLedger(goal="x", workspace_root=WS), 1, 40, 40)
        assert "letto integralmente (40 righe)" in led.render_state_block()

    def test_senza_letture_non_si_inventa_niente(self):
        led = DevSessionLedger(goal="x", workspace_root=WS)
        assert _buchi_di_lettura(led, f"{WS}/{FILE}") == []

    def test_un_ledger_rotto_non_fa_saltare_il_ciclo(self):
        class Rotto:
            def gap_windows(self, *a, **k):
                raise RuntimeError("rotto")

        assert _buchi_di_lettura(Rotto(), FILE) == []


class TestIlCicloLeUsa:
    def _sorgente(self):
        from core.harness.loop import _stream_agent_turn_impl
        return inspect.getsource(_stream_agent_turn_impl)

    def test_il_rifiuto_della_rilettura_nomina_la_finestra(self):
        assert "_finestra_suggerita(\n" in self._sorgente()

    def test_quando_non_c_e_niente_da_leggere_lo_dice(self):
        assert "visto tutto" in self._sorgente()

    def test_il_recupero_non_rifiuta_una_finestra_mai_vista(self):
        assert "_buchi_di_lettura(ledger, percorso_letto)" in self._sorgente()

    def test_l_osservazione_dice_quante_righe_restano(self):
        sorgente = self._sorgente()
        assert "righe ancora" in sorgente
        assert "5000 righe" in sorgente

