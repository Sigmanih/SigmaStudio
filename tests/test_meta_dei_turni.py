"""La via d uscita che nessuno usava, e i turni che nessuno diceva.

`PIANO_TASK.md` 1.1: nove run su nove hanno consumato tutti i turni disponibili,
con due esiti ricorrenti ? nessuna modifica prodotta, lavoro prodotto ma non
dimostrato. `queue_add` con `replaces` esisteva e nessun agente lo ha mai usato:
la via d uscita stava in fondo a un prompt lungo e chiedeva di comporre a mano un
JSON con quattro campi annidati. E il ciclo non sapeva nemmeno di essere dentro
una coda: il `queue_id` viaggiava solo nel testo del prompt, mai come parametro
(`core/harness/fanout.py` lo passava a `_prompt_voce`, non al ciclo).

Il 23 settembre 2026 la prova: meta dei turni passata, zero scritture, dieci
ricerche identiche che il contatore contava tutte come progresso perche ogni
successo lo azzerava. Il recupero non e entrato in scena una volta.

Qui si verifica: la forma pronta arriva a meta turni senza scritture, arriva una
volta sola, i turni consumati sono scritti nello stato, e una ripetizione non e
progresso.
"""

import inspect

from core.harness.ledger import DevSessionLedger
from core.harness.loop import (
    READING_RECOVERY_TOOLS,
    _proposta_di_spezzatura,
    _recovery_directive,
    _stream_agent_turn_impl,
    recovery_stage,
    recovery_tools,
)

WS = "C:/progetto"
FILE = "core/harness/loop.py"
RIGHE = 4212


def _ledger(letto=None, scritto=False):
    led = DevSessionLedger(goal="Implementa l intervento in loop.py",
                           workspace_root=WS)
    if letto:
        led.record_tool(
            "read_file", {"path": "%s/%s" % (WS, FILE)},
            {"success": True, "path": "%s/%s" % (WS, FILE),
             "offset": letto[0], "last_line": letto[1],
             "total_lines": RIGHE, "content": "..."})
    if scritto:
        led.record_tool(
            "write_file", {"path": "%s/core/x.py" % WS},
            {"success": True, "path": "%s/core/x.py" % WS, "lines_after": 10})
    return led


class TestITurniNelloStato:
    def test_dice_a_che_turno_siamo_e_cosa_manca(self):
        stato = _ledger().render_state_block(19, 30)
        assert "**Turni:** 19 di 30" in stato
        assert "nessuna scrittura in questa sessione" in stato
        assert "la meta era il turno 15" in stato
        assert "ed e passata" in stato

    def test_chi_ha_scritto_non_viene_rimproverato(self):
        stato = _ledger(scritto=True).render_state_block(19, 30)
        assert "**Turni:** 19 di 30" in stato
        assert "nessuna scrittura" not in stato

    def test_senza_i_numeri_la_riga_non_compare(self):
        assert "**Turni:**" not in _ledger().render_state_block()


class TestLaPropostaDiSpezzare:
    def test_con_la_coda_la_forma_e_gia_scritta(self):
        proposta = _proposta_di_spezzatura(
            "sigma_studio_migliorie", "s1_spezzare", 16, 30)
        assert "sigma_studio_migliorie" in proposta
        assert '"item_id": "s1_spezzare"' in proposta
        assert '"replaces": true' in proposta
        assert '"items"' in proposta and "PRIMO PEZZO" in proposta

    def test_senza_coda_la_via_d_uscita_e_la_pipeline(self):
        proposta = _proposta_di_spezzatura("", "", 16, 30)
        assert "`pipeline`" in proposta
        assert "queue_add" not in proposta

    def test_dice_perche_conviene(self):
        proposta = _proposta_di_spezzatura("coda", "voce", 16, 30)
        assert "turno 16 di 30" in proposta
        assert "la meta era 15" in proposta
        assert "senza consegnare niente" in proposta


class TestLoStadioDelBuco:
    def test_con_un_buco_lo_stadio_e_gap(self):
        assert recovery_stage(_ledger(letto=(1, 300))) == "gap"

    def test_un_file_letto_tutto_non_ha_buchi(self):
        assert recovery_stage(_ledger(letto=(1, RIGHE))) == "act"

    def test_gli_strumenti_del_buco_sono_la_lettura(self):
        assert recovery_tools(_ledger(letto=(1, 300))) == READING_RECOVERY_TOOLS

    def test_la_direttiva_porta_la_chiamata_pronta(self):
        testo = _recovery_directive(_ledger(letto=(1, 300)))
        assert "ti manca una finestra" in testo
        assert '"offset": 301' in testo
        assert "SOSPESI" in testo


class TestUnaVoltaSola:
    def _sorgente(self):
        return inspect.getsource(_stream_agent_turn_impl)

    def test_il_controllo_e_una_volta_per_run(self):
        assert "not spezzatura_proposta" in self._sorgente()

    def test_scatta_a_meta_turni_senza_scritture(self):
        sorgente = self._sorgente()
        assert "current_turn > max_turns // 2 and not ledger.modified_files" in sorgente

    def test_la_ricerca_ripetuta_non_conta_come_progresso(self):
        sorgente = self._sorgente()
        assert "ripetizione_inerte" in sorgente
        assert "inert_call_signatures.add(firma_inerte)" in sorgente

    def test_anche_la_ricerca_e_soggetta_alla_guardia(self):
        assert '"search_code", "grep")' in self._sorgente()


class TestLaCodaArrivaAlCiclo:
    def test_il_ciclo_accetta_la_coda(self):
        parametri = inspect.signature(_stream_agent_turn_impl).parameters
        assert "queue_id" in parametri and "item_id" in parametri

    def test_il_ventaglio_la_passa(self):
        from pathlib import Path
        sorgente = Path("core/harness/fanout.py").read_text(encoding="utf-8")
        assert "queue_id=coda.queue_id" in sorgente
        assert "item_id=voce.id" in sorgente

