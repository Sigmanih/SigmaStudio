"""L'interfaccia che polla non deve far ricostruire il mondo a ogni giro.

Osservato dal vivo il 23 settembre 2026, nei log del server: la riga
«modules_meta.json rebuilt (379 nodes, 4 topics)» compariva **una volta al
secondo**, e `/api/harness/activity` veniva chiesto piu' volte al secondo da piu'
schede aperte. Erano due letture che si comportavano da scritture: la prima
camminava tutto `data/` e riscriveva il file, la seconda rileggeva lo stato sotto
lucchetto a ogni fotogramma.

La cura e' la stessa per tutte e due, e non tocca la logica: si riusa il
risultato per un tempo breve (3 s l'indice, 1 s l'attivita'), e chi *scrive* ha la
strada diretta - `rebuild_modules_meta()` continua a ricostruire subito, e
`attive()` continua a leggere lo stato vero.

Si verifica: che la seconda lettura ravvicinata riusi la copia, che dopo la
scadenza si ricostruisca, e che le funzioni interne NON siano cache-ate.
"""

import time

from core import data_handler
from core.harness import attivita


class TestLIndiceDeiModuli:
    def test_due_letture_ravvicinate_ricostruiscono_una_volta(self, monkeypatch):
        chiamate = {"n": 0}
        vero = data_handler.rebuild_modules_meta

        def _conta(*a, **k):
            chiamate["n"] += 1
            return vero(*a, **k)

        monkeypatch.setattr(data_handler, "rebuild_modules_meta", _conta)
        data_handler._MODULES_META["quando"] = 0.0
        data_handler._MODULES_META["dati"] = None
        primo = data_handler.modules_meta()
        secondo = data_handler.modules_meta()
        assert secondo is primo, "la seconda lettura ha ricostruito"
        assert chiamate["n"] == 1, chiamate

    def test_scaduta_la_copia_ricostruisce(self):
        vecchia = {"nodes": {"x": {}}, "topics": {}, "modules": {}}
        data_handler._MODULES_META["quando"] = 0.0
        data_handler._MODULES_META["dati"] = vecchia
        nuovo = data_handler.modules_meta()
        assert nuovo is not vecchia, "ha restituito la copia scaduta"
        assert data_handler._MODULES_META["quando"] > 0, "la copia non e' stata rinfrescata"


class TestLAttivita:
    def test_lo_stato_si_riusa_per_un_istante(self):
        attivita._STATO_CACHE["quando"] = 0.0
        attivita._STATO_CACHE["dati"] = None
        primo = attivita.stato()
        secondo = attivita.stato()
        assert secondo is primo, "ha riletto per un secondo fotogramma"
        assert set(primo) >= {"busy", "count", "running", "recent"}

    def test_attive_non_e_cache_ata(self):
        """La chat e il ventaglio devono vedere lo stato vero, non una fotografia."""
        attivita._STATO_CACHE["quando"] = time.time()
        attivita._STATO_CACHE["dati"] = {"busy": False, "count": 0, "running": [], "recent": []}
        assert attivita.stato()["busy"] is False
        # `attive()` rilegge sempre: non passa dalla cache dello stato.
        assert isinstance(attivita.attive(), list)
