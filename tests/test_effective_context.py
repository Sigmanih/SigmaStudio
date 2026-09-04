"""La finestra su cui budgetare non e' quella dichiarata.

`-np N` non aggiunge contesto: lo divide. Un server avviato con `-c 32768
-np 4` dichiara 32768 e da' 8192 token a ogni generazione. Chi costruisce il
prompt sulla cifra dichiarata ne prepara uno quattro volte piu' grande di
quello che entra, e il modo in cui fallisce e' il peggiore possibile: nel caso
buono il prompt viene troncato in silenzio e l'agente si comporta come se
avesse letto un file che non ha visto; nel caso cattivo — documentato dentro
llamaserver_backend — il server smette di rispondere con i pesi ancora in
memoria, e da fuori sembra un modello lento.
"""

import pytest

from core.harness.loop import (
    CHARS_PER_TOKEN,
    MAX_OBSERVATION_CONTEXT_SHARE,
    observation_budget,
)


class MotoreFinto:
    """Quel tanto di motore che serve: contesto dichiarato e slot."""

    def __init__(self, dichiarato, slot=None):
        self._dichiarato = dichiarato
        self.active_backend_instance = _BackendFinto(slot) if slot is not None else None

    def context_window(self):
        return self._dichiarato

    # copia esatta della logica del runtime, per poterla verificare senza
    # caricare un modello vero
    def effective_context_window(self):
        totale = self.context_window()
        if not totale:
            return 0
        backend = self.active_backend_instance
        if backend is None:
            return totale
        try:
            slot = int(backend.parallel_slots())
        except Exception:
            return totale
        return max(1, totale // max(1, slot))


class _BackendFinto:
    def __init__(self, slot):
        self._slot = slot

    def parallel_slots(self):
        if self._slot == "rotto":
            raise RuntimeError("telemetria non disponibile")
        return self._slot


class TestFinestraEffettiva:
    def test_con_quattro_slot_la_finestra_si_divide(self):
        assert MotoreFinto(32768, slot=4).effective_context_window() == 8192

    def test_con_uno_slot_resta_intera(self):
        assert MotoreFinto(32768, slot=1).effective_context_window() == 32768

    def test_senza_backend_a_slot_resta_intera(self):
        """Il percorso in-process ha un contesto solo: nulla da dividere."""
        assert MotoreFinto(16384).effective_context_window() == 16384

    def test_un_backend_che_non_sa_rispondere_non_riduce(self):
        """Meglio la cifra dichiarata che zero: un budget nullo blocca il run."""
        assert MotoreFinto(16384, slot="rotto").effective_context_window() == 16384

    def test_senza_modello_caricato_e_zero(self):
        assert MotoreFinto(0, slot=4).effective_context_window() == 0

    def test_il_risultato_non_e_mai_zero_con_un_contesto_valido(self):
        assert MotoreFinto(100, slot=1000).effective_context_window() >= 1


class TestBudgetDelleOsservazioni:
    """Il motivo per cui la finestra sbagliata fa danno."""

    def test_il_tetto_segue_la_finestra_reale(self):
        dichiarata = observation_budget("read_file", 32768)
        reale = observation_budget("read_file", 8192)
        assert reale < dichiarata

    def test_su_una_finestra_da_quattro_slot_una_lettura_ci_sta(self):
        """Il difetto in una riga: con 32768 il tetto supera lo slot intero."""
        finestra_reale_token = 8192
        tetto = observation_budget("read_file", finestra_reale_token)
        caratteri_dello_slot = finestra_reale_token * CHARS_PER_TOKEN
        assert tetto < caratteri_dello_slot

        # Con la cifra dichiarata il tetto e' piu' grande dell'intero slot:
        # una sola osservazione non entrerebbe nel contesto disponibile.
        tetto_sbagliato = observation_budget("read_file", 32768)
        assert tetto_sbagliato > caratteri_dello_slot

    def test_il_tetto_resta_una_frazione_della_finestra(self):
        for finestra in (4096, 8192, 32768, 131072):
            tetto = observation_budget("read_file", finestra)
            assert tetto <= max(
                2000, finestra * CHARS_PER_TOKEN * MAX_OBSERVATION_CONTEXT_SHARE
            ) + 1

    def test_esiste_comunque_un_minimo_utilizzabile(self):
        """Una finestra minuscola non deve produrre osservazioni vuote."""
        assert observation_budget("read_file", 512) >= 2000
