"""Quando il piano se lo scrivono loro, il piano e' la cosa piu' importante da mostrare.

Lasciati liberi di pianificare, gli agenti si sono scritti sette voci di lavoro
con i loro comandi di verifica. Tre di quelle voci dichiaravano gli stessi file,
e la coda l'aveva notato — `_avvisa_sovrapposizioni` fa esattamente questo, e
funziona.

L'avviso pero' finiva solo nell'osservazione dell'agente. Chi guardava da fuori
vedeva il lavoro partire senza sapere in cosa fosse stato diviso, e senza
sapere che due voci si sarebbero contese lo stesso file. Un piano che nessuno
puo' leggere non si puo' nemmeno criticare.
"""

import pytest

from core.harness.loop import execute_admin_tool


class TestLaCodaSaVedereLeSovrapposizioni:
    """La capacita' c'era gia': e' quella che non usciva."""

    def test_due_voci_sullo_stesso_file_producono_un_avviso(self, tmp_path, monkeypatch):
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_sovrapposizioni", goal="x")
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "tocca App.jsx", "files": ["frontend/src/App.jsx"]},
            {"id": "b", "title": "tocca anche App.jsx", "files": ["frontend/src/App.jsx"]},
        ], avvisi=avvisi)
        assert avvisi and "App.jsx" in avvisi[0]

    def test_file_diversi_non_producono_rumore(self, tmp_path, monkeypatch):
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        coda = workqueue.WorkQueue("prova_sovrapposizioni2", goal="x")
        avvisi = []
        coda.add_many([
            {"id": "a", "title": "x", "files": ["a.js"]},
            {"id": "b", "title": "y", "files": ["b.js"]},
        ], avvisi=avvisi)
        assert avvisi == []


class TestIlToolLiRiporta:
    def test_gli_avvisi_tornano_nel_risultato(self, tmp_path, monkeypatch):
        from core.harness import workqueue

        monkeypatch.setattr(workqueue.paths, "var_dir", lambda: str(tmp_path))
        workqueue.forget_queue("prova_tool")
        esito = execute_admin_tool("queue_add", {
            "queue_id": "prova_tool",
            "items": [
                {"id": "a", "title": "tocca App.jsx", "files": ["frontend/src/App.jsx"]},
                {"id": "b", "title": "tocca anche App.jsx", "files": ["frontend/src/App.jsx"]},
            ],
        }, str(tmp_path))
        assert esito["success"] is True
        assert esito["warnings"]


class TestEArrivanoAChiGuarda:
    """Il ciclo emette eventi: e' l'unico modo che ha chi sta fuori di sapere
    cosa sta succedendo. `pipeline` ne aveva uno, `queue_add` no — e da quando
    il piano lo scrivono gli agenti, e' `queue_add` quello che conta."""

    def _sorgente(self):
        import inspect

        from core.harness import loop

        return inspect.getsource(loop._stream_agent_turn_impl)

    def test_il_ciclo_emette_l_evento(self):
        assert '"type": "queue_updated"' in self._sorgente()

    def test_e_ci_mette_dentro_gli_avvisi(self):
        sorgente = self._sorgente()
        i = sorgente.index('"type": "queue_updated"')
        blocco = sorgente[i:i + 400]
        assert '"warnings"' in blocco
        assert '"queue_id"' in blocco

    def test_solo_quando_la_chiamata_e_riuscita(self):
        """Annunciare un piano che non e' stato accettato confonde chi guarda."""
        sorgente = self._sorgente()
        i = sorgente.index("elif t_name in (\"queue_add\"")
        assert 'result.get("success")' in sorgente[i:i + 900]
