"""Un file non si cancella un pezzo per volta.

La guardia sul troncamento confrontava ogni scrittura con quella
immediatamente precedente. Su un run vero un agente ha riscritto lo stesso
file undici volte, ogni volta un po' piu' corto: 2600 caratteri, poi 1800,
poi 900, poi 400, poi 167. Nessun singolo passo scendeva sotto un quarto del
precedente, quindi ogni passo veniva accettato — e alla fine restava un
moncone di sette righe, con l'harness che aveva risposto «ok» undici volte.

La guardia va bene contro una cancellazione in un colpo solo. Contro
l'erosione non serviva a niente, ed e' il modo in cui un agente in
difficolta' distrugge il proprio lavoro.
"""

import inspect

import pytest

from core.harness.fs_tools import TRUNCATION_MIN_CHARS, would_truncate


class TestErosioneProgressiva:
    def test_il_caso_vero_viene_fermato(self):
        """La sequenza esatta osservata sul run."""
        precedente, massimo, bloccate = "", 0, []
        for dimensione in (2600, 1800, 900, 400, 167):
            nuovo = "x" * dimensione
            if would_truncate(precedente, nuovo, high_water=massimo):
                bloccate.append(dimensione)
            else:
                precedente, massimo = nuovo, max(massimo, dimensione)

        assert bloccate, "l'erosione non e' stata fermata"
        assert len(precedente.strip()) >= 900, "il file e' stato eroso lo stesso"

    def test_senza_memoria_del_massimo_l_erosione_passa(self):
        """Il difetto, riprodotto: e' la stessa sequenza senza `high_water`."""
        precedente = ""
        for dimensione in (2600, 1800, 900, 400, 167):
            nuovo = "x" * dimensione
            assert would_truncate(precedente, nuovo) is False
            precedente = nuovo
        assert len(precedente) == 167


class TestCosaResta:
    def test_una_cancellazione_in_un_colpo_solo_resta_bloccata(self):
        assert would_truncate("x" * 3000, "x" * 10) is True

    def test_un_file_che_cresce_non_e_un_problema(self):
        assert would_truncate("x" * 500, "x" * 900, high_water=500) is False

    def test_una_riscrittura_di_pari_dimensione_passa(self):
        assert would_truncate("x" * 500, "y" * 480, high_water=500) is False

    def test_i_file_piccoli_restano_liberi(self):
        """Sotto la soglia non si sorveglia: un file di due righe si riscrive
        continuamente, ed e' normale."""
        piccolo = "x" * (TRUNCATION_MIN_CHARS - 10)
        assert would_truncate(piccolo, "y", high_water=len(piccolo)) is False

    def test_il_massimo_del_run_vince_sul_file_attuale(self):
        """Anche se il file su disco e' gia' stato ridotto, il metro resta il
        piu' grande che si e' visto."""
        assert would_truncate("x" * 300, "x" * 100, high_water=3000) is True


class TestIlCicloRicorda:
    def test_il_ciclo_tiene_le_dimensioni_viste(self):
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "dimensioni_viste: Dict[str, int] = {}" in sorgente
        assert "dimensioni_viste=dimensioni_viste" in sorgente

    def test_lo_strumento_le_aggiorna_dopo_una_scrittura(self, tmp_path):
        """Il registro delle dimensioni si riempie davvero.

        Prima questo test leggeva il **sorgente** di `execute_admin_tool` e
        cercava la riga che aggiorna il dizionario. Ha smesso di passare
        appena la funzione e' diventata un guscio attorno alla sua
        implementazione — pur funzionando esattamente come prima. Un test che
        controlla com'e' scritto il codice fallisce quando il codice viene
        spostato e tace quando smette di funzionare: qui si guarda l'effetto.
        """
        from core.harness.loop import execute_admin_tool

        parametri = inspect.signature(execute_admin_tool).parameters
        assert "dimensioni_viste" in parametri

        viste = {}
        contenuto = "riga di codice\n" * 200
        esito = execute_admin_tool(
            "write_file", {"path": "modulo.py", "content": contenuto},
            str(tmp_path), dimensioni_viste=viste)
        assert esito.get("success") is True
        assert viste, "dopo una scrittura il registro non puo' essere vuoto"
        assert max(viste.values()) >= len(contenuto.strip())

    def test_una_riscrittura_erosiva_viene_rifiutata_dallo_strumento(self, tmp_path):
        from core.harness.loop import execute_admin_tool

        viste = {}
        grande = "riga di codice\n" * 200
        primo = execute_admin_tool(
            "write_file", {"path": "modulo.py", "content": grande},
            str(tmp_path), dimensioni_viste=viste)
        assert primo.get("success") is True

        # Meta': passa, ed e' giusto — puo' essere una riscrittura legittima.
        meta = "riga di codice\n" * 100
        assert execute_admin_tool(
            "write_file", {"path": "modulo.py", "content": meta},
            str(tmp_path), dimensioni_viste=viste).get("success") is True

        # Un moncone: rifiutato, perche' il metro e' il massimo del run.
        moncone = "import sys\n"
        esito = execute_admin_tool(
            "write_file", {"path": "modulo.py", "content": moncone},
            str(tmp_path), dimensioni_viste=viste)
        assert esito.get("success") is False
        assert "gia visti in questo run" in esito.get("error", "")

    def test_la_riduzione_voluta_resta_possibile(self, tmp_path):
        """Chi sa quello che fa lo dichiara e passa."""
        from core.harness.loop import execute_admin_tool

        viste = {}
        execute_admin_tool("write_file", {"path": "m.py", "content": "x\n" * 400},
                           str(tmp_path), dimensioni_viste=viste)
        esito = execute_admin_tool(
            "write_file",
            {"path": "m.py", "content": "import sys\n", "allow_truncate": True},
            str(tmp_path), dimensioni_viste=viste)
        assert esito.get("success") is True
