"""Un worktree e' una cartella diversa, e per certi lavori quella differenza e' fatale.

La voce `online` della Biblioteca doveva tirare su lo stack con `docker
compose`, ed e' fallita tre volte di fila. Docker Compose si ancora alla
cartella da cui parte — ci monta i volumi, da li' deriva il nome del progetto —
quindi lo stack nasceva dentro `var/dev_worktrees/...`:

    working_dir = ...\\var\\dev_worktrees\\fanout_biblioteca_app_online_ddaad0

e appena quella cartella temporanea spariva, l'API rispondeva 500 con il volume
di `dati.json` puntato nel vuoto. In piu' i `container_name` fissi collidevano
fra un tentativo e l'altro: «Conflict. The container name /biblioteca-backend is
already in use».

Non e' un difetto di Docker ne' dell'agente. L'isolamento e' una scelta con un
prezzo, e per un progetto il cui prodotto **e'** uno stack acceso quel prezzo e'
che il prodotto non puo' esistere. Si spegne per progetto, con la ragione
scritta accanto, e si perde il parallelismo: e' il baratto, ed e' esplicito.
"""

import json

import pytest

from core.harness.fanout import isolamento_possibile


class TestQuandoSiIsola:
    def test_di_norma_si(self, tmp_path):
        """Il comportamento di chi non ha chiesto niente non deve cambiare."""
        assert isolamento_possibile(str(tmp_path)) is True

    def test_una_sandbox_che_non_ne_parla_non_cambia_niente(self, tmp_path):
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"mode": "container"}), encoding="utf-8")
        assert isolamento_possibile(str(tmp_path)) is True

    def test_si_spegne_dicendolo(self, tmp_path):
        (tmp_path / "sandbox.json").write_text(
            json.dumps({"isola": False}), encoding="utf-8")
        assert isolamento_possibile(str(tmp_path)) is False

    def test_una_sandbox_illeggibile_non_toglie_l_isolamento(self, tmp_path):
        """Nel dubbio si isola: e' la scelta che non puo' fare danni."""
        (tmp_path / "sandbox.json").write_text("{rotto", encoding="utf-8")
        assert isolamento_possibile(str(tmp_path)) is True

    def test_senza_radice_si_isola(self):
        assert isolamento_possibile("") is True


class TestIlProgettoVero:
    def test_la_biblioteca_lo_ha_spento_con_la_ragione_scritta(self):
        """Una configurazione senza il perche' diventa incomprensibile al
        primo che la legge, e viene rimessa a posto per sbaglio."""
        import pathlib

        percorso = pathlib.Path(r"C:\Users\Sigma\Desktop\BibliotecaDigitale\sandbox.json")
        if not percorso.is_file():
            pytest.skip("il progetto non e' su questa macchina")
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        assert dati.get("isola") is False
        assert "compose" in dati.get("_nota_isolamento", "").lower()


class TestEDavveroCollegato:
    def test_il_ventaglio_la_interroga(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout._esegui_voce)
        assert "isolate_worktree=isolamento_possibile(workspace_root)" in sorgente

    def test_senza_isolamento_si_lavora_in_uno_solo(self):
        """Due agenti nello stesso albero non e' parallelismo, e' corruzione.
        Chi ha spento l'isolamento ha accettato di andare piano, non di
        rompere."""
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout.run_queue)
        i = sorgente.index("not isolamento_possibile(workspace_root)")
        assert "numero = 1" in sorgente[i:i + 700]
