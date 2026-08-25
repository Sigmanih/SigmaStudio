# ==============================================================================
# tests/test_sse.py — Che una disconnessione fermi davvero la generazione
#
# Il meccanismo con cui questa applicazione interrompe un lavoro abbandonato e'
# indiretto: nessuno controlla "il client c'e' ancora?", si prova a scrivere e
# si lascia fallire. ClientGone risale attraverso il ciclo di generazione, e il
# ciclo si ferma.
#
# Un meccanismo del genere si rompe in silenzio. Bastava un `except: pass` nel
# writer perche' il segnale sparisse e la generazione proseguisse fino al budget
# completo di token, scrivendo in una coda che nessuno legge: cinque handler
# avevano ognuno la propria copia di quel writer, e tre di quelle copie il
# segnale lo cancellavano. Nessun test se n'era accorto.
# ==============================================================================
import json
import threading
import unittest

from core.sse import ClientGone, sse_frame, sse_writer


class _Wfile:
    """Il minimo che un writer di stream si aspetta."""

    def __init__(self, fallisce_con=None):
        self.scritti = []
        self._fallisce_con = fallisce_con

    def write(self, frame):
        if self._fallisce_con is not None:
            raise self._fallisce_con
        self.scritti.append(frame)

    def flush(self):
        pass


class _Handler:
    def __init__(self, wfile):
        self.wfile = wfile


class TestFrame(unittest.TestCase):

    def test_il_frame_ha_il_formato_che_il_browser_si_aspetta(self):
        frame = sse_frame({"type": "token", "token": "ciao"})
        self.assertTrue(frame.startswith(b"data: "))
        self.assertTrue(frame.endswith(b"\n\n"))
        self.assertEqual(json.loads(frame[6:-2])["token"], "ciao")

    def test_gli_accenti_non_diventano_sequenze_di_escape(self):
        """L'interfaccia e' in italiano: ensure_ascii rovinerebbe ogni messaggio."""
        frame = sse_frame({"testo": "però è così"})
        self.assertIn("però è così", frame.decode("utf-8"))


class TestDisconnessione(unittest.TestCase):

    def test_client_gone_arriva_fino_a_chi_genera(self):
        """Il caso che conta: se il segnale non passa, la generazione non si ferma."""
        scrivi = sse_writer(_Handler(_Wfile(fallisce_con=ClientGone("chiuso"))))
        with self.assertRaises(ClientGone):
            scrivi({"type": "token"})

    def test_una_pipe_rotta_e_la_stessa_cosa(self):
        """Il socket solleva BrokenPipeError, l'adapter ClientGone: stesso esito."""
        for errore in (BrokenPipeError("pipe"), ConnectionResetError("reset")):
            with self.subTest(errore=type(errore).__name__):
                scrivi = sse_writer(_Handler(_Wfile(fallisce_con=errore)))
                with self.assertRaises(ClientGone):
                    scrivi({"type": "token"})

    def test_nessun_guasto_di_scrittura_viene_ingoiato(self):
        """Qualunque guasto dello stream ferma la generazione, non la prosegue."""
        scrivi = sse_writer(_Handler(_Wfile(fallisce_con=OSError("disco pieno"))))
        with self.assertRaises(ClientGone):
            scrivi({"type": "token"})

    def test_un_evento_non_serializzabile_non_ferma_il_lavoro(self):
        """Perdere un frame di avanzamento non giustifica far fallire un job."""
        wfile = _Wfile()
        scrivi = sse_writer(_Handler(wfile))
        scrivi({"oggetto": object()})          # non deve sollevare
        scrivi({"type": "ok"})
        self.assertEqual(len(wfile.scritti), 1)
        self.assertIn(b'"ok"', wfile.scritti[0])


class TestScrittureConcorrenti(unittest.TestCase):

    def test_con_il_lock_i_frame_non_si_interlacciano(self):
        """Gli agenti dello swarm scrivono in parallelo sullo stesso stream."""
        wfile = _Wfile()
        scrivi = sse_writer(_Handler(wfile), lock=threading.Lock())

        thread = [threading.Thread(target=scrivi, args=({"i": i},)) for i in range(40)]
        for t in thread:
            t.start()
        for t in thread:
            t.join()

        self.assertEqual(len(wfile.scritti), 40)
        for frame in wfile.scritti:
            self.assertTrue(frame.startswith(b"data: "))
            json.loads(frame[6:-2])            # ogni frame e' JSON intero


class TestUnaSolaImplementazione(unittest.TestCase):

    def test_nessun_handler_si_riscrive_il_writer(self):
        """Cinque copie divergenti sono il motivo per cui esiste core/sse.py."""
        import re
        from pathlib import Path

        from core.paths import project_root

        colpevoli = []
        for f in (project_root() / "core").rglob("*.py"):
            if "__pycache__" in str(f) or f.name == "sse.py":
                continue
            testo = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"def _sse\(", testo):
                colpevoli.append(f.name)

        self.assertEqual(colpevoli, [],
                         "questi file si sono riscritti il writer SSE invece di "
                         "usare core.sse.sse_writer")


if __name__ == "__main__":
    unittest.main()
