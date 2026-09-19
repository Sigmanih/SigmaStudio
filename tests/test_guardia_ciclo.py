# ==============================================================================
# tests/test_guardia_ciclo.py — Riconoscere il ciclo, non solo la ripetizione
# ==============================================================================
"""Tre buchi nella guardia anti-ripetizione, e il confine da non superare.

La guardia precedente riconosceva una cosa sola: la stessa identica chiamata,
serializzata negli stessi byte, dopo che era gia' fallita. Bastava uno spazio
in piu' per aggirarla senza farlo apposta, e il ciclo a due mosse — `edit_file`
fallisce, `read_file` riesce, `edit_file` fallisce di nuovo — non lo vedeva
affatto, perche' nessuna chiamata era ripetuta *di seguito*.

Il confine e' l'altra meta' del lavoro: **dopo una modifica vera, riprovare non
e' ripetersi.** E' il ciclo correggi-verifica, l'unico modo che l'agente ha di
sapere se ha finito, e stringerlo per sbaglio costerebbe piu' dello stallo che
si voleva evitare.
"""
import unittest

from core.harness.cicli import (
    RilevatoreCicli,
    comando_bloccato_in_ciclo,
    firma,
)


class TestLaFirmaNonSiAggiraPerCaso(unittest.TestCase):
    """La firma era il JSON esatto: ogni variazione innocua la cambiava."""

    def test_le_chiavi_riordinate_danno_la_stessa_firma(self):
        a = firma("edit_file", {"path": "a.py", "old": "x", "new": "y"})
        b = firma("edit_file", {"new": "y", "old": "x", "path": "a.py"})
        self.assertEqual(a, b)

    def test_lo_stesso_file_scritto_in_modi_diversi_ha_la_stessa_firma(self):
        a = firma("read_file", {"path": "core/loop.py"})
        b = firma("read_file", {"path": "./core\\\\loop.py"})
        self.assertEqual(a, b)

    def test_la_radice_del_workspace_non_cambia_la_firma(self):
        radice = "C:/lavoro/progetto"
        a = firma("read_file", {"path": "src/app.py"}, radice)
        b = firma("read_file", {"path": "C:/lavoro/progetto/src/app.py"}, radice)
        self.assertEqual(a, b)

    def test_uno_spazio_in_piu_non_cambia_la_firma(self):
        a = firma("terminal", {"command": "npm  run   test"})
        b = firma("terminal", {"command": "npm run test"})
        self.assertEqual(a, b)

    def test_due_chiamate_davvero_diverse_restano_diverse(self):
        a = firma("read_file", {"path": "a.py"})
        b = firma("read_file", {"path": "b.py"})
        self.assertNotEqual(a, b)


class TestIlCicloADueMosse(unittest.TestCase):

    def setUp(self):
        self.r = RilevatoreCicli("C:/lavoro")

    def test_edit_read_edit_read_viene_riconosciuto(self):
        """La forma piu' comune di stallo: ogni giro sembra un tentativo nuovo."""
        self.r.registra("edit_file", {"path": "a.py", "old": "x"}, riuscito=False)
        self.r.registra("read_file", {"path": "a.py"}, riuscito=True)
        # Primo giro concluso: la seconda `edit_file` e' ancora un tentativo.
        self.assertIsNone(
            self.r.ciclo_in_corso("edit_file", {"path": "a.py", "old": "x"}),
            "il secondo tentativo non e' ancora un ciclo",
        )

        self.r.registra("edit_file", {"path": "a.py", "old": "x"}, riuscito=False)
        self.r.registra("read_file", {"path": "a.py"}, riuscito=True)
        # Secondo giro concluso: rifare `edit_file` chiuderebbe il giro una
        # terza volta, e nel frattempo non e' cambiato niente.
        ciclo = self.r.ciclo_in_corso("edit_file", {"path": "a.py", "old": "x"})
        self.assertIsNotNone(ciclo)
        self.assertIn("edit_file", ciclo)
        self.assertIn("read_file", ciclo)

    def test_il_messaggio_nomina_la_sequenza(self):
        for _ in range(2):
            self.r.registra("search_code", {"query": "foo"}, riuscito=True)
            self.r.registra("read_file", {"path": "b.py"}, riuscito=True)
        self.r.registra("search_code", {"query": "foo"}, riuscito=True)
        ciclo = self.r.ciclo_in_corso("read_file", {"path": "b.py"})
        self.assertIsNotNone(ciclo)
        self.assertIn("search_code -> read_file", ciclo)

    def test_il_ciclo_a_tre_mosse(self):
        passi = [("read_file", {"path": "a.py"}), ("edit_file", {"path": "a.py"}),
                 ("search_code", {"query": "z"})]
        for _ in range(2):
            for nome, par in passi:
                self.r.registra(nome, par, riuscito=False)
        for nome, par in passi[:2]:
            self.r.registra(nome, par, riuscito=False)
        self.assertIsNotNone(self.r.ciclo_in_corso("search_code", {"query": "z"}))


class TestIlConfineDaNonSuperare(unittest.TestCase):
    """Dopo una modifica vera, riprovare e' il lavoro, non lo stallo."""

    def setUp(self):
        self.r = RilevatoreCicli("C:/lavoro")

    def test_una_scrittura_riuscita_riapre_tutto(self):
        self.r.registra("edit_file", {"path": "a.py", "old": "x"}, riuscito=False)
        self.assertTrue(self.r.gia_fallita("edit_file", {"path": "a.py", "old": "x"}))

        self.r.registra("write_file", {"path": "a.py", "content": "nuovo"},
                        riuscito=True, workspace_cambiato=True)
        self.assertFalse(
            self.r.gia_fallita("edit_file", {"path": "a.py", "old": "x"}),
            "dopo una scrittura sullo stesso file il tentativo torna sensato",
        )

    def test_la_scrittura_riapre_solo_il_file_che_ha_toccato(self):
        """Prima bastava un `write_file` qualunque per dimenticare ogni
        fallimento, compresi quelli su file che non c'entravano."""
        self.r.registra("edit_file", {"path": "altro.py", "old": "x"}, riuscito=False)
        self.r.registra("write_file", {"path": "a.py", "content": "c"},
                        riuscito=True, workspace_cambiato=True)
        self.assertTrue(
            self.r.gia_fallita("edit_file", {"path": "altro.py", "old": "x"}),
            "la scrittura su a.py non rende ritentabile un fallimento su altro.py",
        )

    def test_il_ciclo_correggi_verifica_non_viene_scambiato_per_stallo(self):
        """edit riuscito, test fallito, edit riuscito, test fallito: ogni edit
        cambia il disco, quindi non e' un ciclo."""
        for _ in range(3):
            self.r.registra("edit_file", {"path": "a.py", "old": "x"},
                            riuscito=True, workspace_cambiato=True)
            self.r.registra("terminal", {"command": "pytest"}, riuscito=False)
        self.assertIsNone(self.r.ciclo_in_corso("edit_file", {"path": "a.py", "old": "x"}))

    def test_una_chiamata_riuscita_esce_dalle_fallite(self):
        self.r.registra("read_file", {"path": "a.py"}, riuscito=False)
        self.r.registra("read_file", {"path": "a.py"}, riuscito=True)
        self.assertFalse(self.r.gia_fallita("read_file", {"path": "a.py"}))


class _LedgerFinto:
    def __init__(self, volte, comandi):
        self._consecutive_dup_commands = volte
        self._commands = comandi


class TestIlComandoCheFallisceSempre(unittest.TestCase):
    """Il buco piu' grosso: la guardia scattava solo sul comando RIUSCITO."""

    def test_due_fallimenti_identici_senza_modifiche_vengono_fermati(self):
        ledger = _LedgerFinto(2, [{"command": "pytest", "ok": False,
                                   "error": "2 test falliti in test_a.py"}])
        bloccato = comando_bloccato_in_ciclo(ledger)
        self.assertIsNotNone(bloccato)
        self.assertEqual(bloccato["esito"], "fallito")
        self.assertIn("test_a.py", bloccato["errore"])

    def test_il_comando_riuscito_ripetuto_resta_fermato(self):
        ledger = _LedgerFinto(2, [{"command": "pytest", "ok": True}])
        bloccato = comando_bloccato_in_ciclo(ledger)
        self.assertIsNotNone(bloccato)
        self.assertEqual(bloccato["esito"], "ok")

    def test_una_sola_ripetizione_non_basta(self):
        ledger = _LedgerFinto(1, [{"command": "pytest", "ok": False}])
        self.assertIsNone(comando_bloccato_in_ciclo(ledger))

    def test_senza_comandi_non_dice_niente(self):
        self.assertIsNone(comando_bloccato_in_ciclo(_LedgerFinto(5, [])))


class TestAgganciatoAlCiclo(unittest.TestCase):
    """Le guardie devono stare sul percorso vero, non solo nel modulo."""

    def test_il_rilevatore_e_usato_dal_ciclo_dellagente(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        self.assertIn("rilevatore = RilevatoreCicli(", sorgente)
        self.assertIn("rilevatore.ciclo_in_corso(", sorgente)
        self.assertIn("rilevatore.gia_fallita(", sorgente)
        self.assertIn("comando_bloccato_in_ciclo(ledger)", sorgente)

    def test_il_comando_fallito_ripetuto_ha_un_ramo_suo(self):
        import inspect

        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        self.assertIn('bloccato["esito"] == "fallito"', sorgente)


if __name__ == "__main__":
    unittest.main()
