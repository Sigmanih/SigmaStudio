"""La coda che sopravvive ai run, e i run che la consumano in parallelo.

Il ledger racconta un run. Quando il lavoro e' duecento file il run non e' piu'
l'unita' giusta: servono molti run, in parallelo, ripresi anche domani — e un
posto dove sta scritto cosa e' gia' stato fatto. Senza, ogni ripartenza
ricomincia dalla mappa, che e' la parte costosa.

Le proprieta' che rendono una coda una coda, e non una lista:

1. **prendere una voce e' atomico** — due agenti non lavorano sullo stesso pezzo;
2. **il lavoro non resta appeso** — chi muore a meta' non blocca la sua voce
   per sempre;
3. **lo stato e' sul disco** — spegnere il computer non cancella la mappa.
"""

import json
import threading
import time

import pytest

from core.harness import workqueue
from core.harness.workqueue import DA_FARE, FALLITA, FATTA, IN_CORSO, WorkQueue


@pytest.fixture(autouse=True)
def coda_isolata(tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
    workqueue._code.clear()
    yield
    workqueue._code.clear()


def _coda(nome="prova", voci=("uno", "due", "tre"), **kw):
    q = WorkQueue(nome, goal="tradurre l'interfaccia", **kw)
    q.add_many(list(voci))
    return q


class TestPrendereUnaVoce:
    def test_si_prende_in_ordine(self):
        q = _coda()
        assert q.claim("a").title == "uno"
        assert q.claim("a").title == "due"

    def test_una_voce_presa_non_la_prende_nessun_altro(self):
        """La proprieta' che impedisce a due agenti di fare lo stesso lavoro."""
        q = _coda(voci=("sola",))
        assert q.claim("a") is not None
        assert q.claim("b") is None

    def test_prendere_e_atomico_fra_thread(self):
        """Dieci lavoratori su dieci voci: nessuna deve toccare a due."""
        q = _coda(voci=[f"v{i}" for i in range(10)])
        presi, lucchetto = [], threading.Lock()

        def lavora():
            while True:
                v = q.claim()
                if v is None:
                    return
                with lucchetto:
                    presi.append(v.id)
                time.sleep(0.001)

        thread = [threading.Thread(target=lavora) for _ in range(10)]
        for t in thread:
            t.start()
        for t in thread:
            t.join(timeout=10)

        assert len(presi) == 10
        assert len(set(presi)) == 10, "una voce e' stata presa piu' di una volta"

    def test_una_coda_vuota_non_da_niente(self):
        assert WorkQueue("vuota").claim() is None


class TestIlLavoroNonRestaAppeso:
    def test_una_voce_abbandonata_torna_disponibile(self):
        """Un agente che muore a meta' bloccherebbe la sua voce per sempre."""
        q = _coda(voci=("sola",), abbandono_s=0.05)
        presa = q.claim("morto")
        time.sleep(0.1)

        ripresa = q.claim("vivo")
        assert ripresa is not None
        assert ripresa.id == presa.id
        assert ripresa.attempts == 2

    def test_dopo_troppi_tentativi_la_voce_si_arrende(self):
        """Altrimenti una voce avvelenata terrebbe occupati gli agenti mentre
        il resto della coda aspetta."""
        q = _coda(voci=("difficile",), abbandono_s=0.02, tentativi_massimi=2)
        for _ in range(3):
            q.claim("w")
            time.sleep(0.03)
        q.claim("w")  # innesca il recupero

        assert q.items(FALLITA), "la voce doveva arrendersi"
        assert q.claim("w") is None

    def test_una_voce_ancora_viva_non_viene_rubata(self):
        q = _coda(voci=("sola",), abbandono_s=1000.0)
        q.claim("a")
        assert q.claim("b") is None


class TestEsiti:
    def test_completare_la_toglie_dal_giro(self):
        q = _coda(voci=("sola",))
        v = q.claim()
        assert q.complete(v.id, {"files": ["a.py"]}) is True
        assert q.progress()["done"] == 1
        assert q.is_finished() is True

    def test_fallire_la_rimette_in_coda_se_restano_tentativi(self):
        """Un errore di rete non dice che la voce sia impossibile."""
        q = _coda(voci=("sola",), tentativi_massimi=3)
        v = q.claim()
        q.fail(v.id, "rete assente")
        assert q.progress()["todo"] == 1
        assert q.claim() is not None

    def test_finiti_i_tentativi_il_fallimento_e_definitivo(self):
        q = _coda(voci=("sola",), tentativi_massimi=1)
        v = q.claim()
        q.fail(v.id, "rotta")
        assert q.progress()["failed"] == 1
        assert q.claim() is None

    def test_restituire_una_voce_non_consuma_un_tentativo(self):
        q = _coda(voci=("sola",))
        v = q.claim()
        assert v.attempts == 1
        q.release(v.id)
        assert q.claim().attempts == 1

    def test_si_puo_ridare_una_possibilita_a_cio_che_e_fallito(self):
        q = _coda(voci=("sola",), tentativi_massimi=1)
        v = q.claim()
        q.fail(v.id, "rotta")
        assert q.reset_failed() == 1
        assert q.claim() is not None


class TestLoStatoStaSulDisco:
    def test_una_coda_riaperta_ricorda_cosa_e_stato_fatto(self):
        """E' l'unica differenza che conta fra una coda e una lista."""
        q = _coda(nome="persistente")
        v = q.claim()
        q.complete(v.id)

        workqueue._code.clear()
        riaperta = WorkQueue("persistente")
        assert riaperta.progress()["done"] == 1
        assert riaperta.progress()["todo"] == 2
        assert riaperta.goal == "tradurre l'interfaccia"

    def test_il_salvataggio_non_lascia_file_a_meta(self, tmp_path):
        """Una coda troncata a meta' salvataggio farebbe rifare lavoro gia'
        fatto senza dirlo: si scrive a fianco e si sposta."""
        q = _coda(nome="atomica")
        contenuto = json.loads(q.path.read_text(encoding="utf-8"))
        assert len(contenuto["items"]) == 3
        assert not list(q.path.parent.glob("*.tmp"))

    def test_la_stessa_coda_e_lo_stesso_oggetto(self):
        """Due copie avrebbero due lucchetti, e `claim` smetterebbe di essere
        atomico — cioe' la coda smetterebbe di essere una coda."""
        a = workqueue.get_queue("condivisa")
        b = workqueue.get_queue("condivisa")
        assert a is b

    def test_le_code_su_disco_si_possono_elencare(self):
        _coda(nome="elencabile")
        elenco = workqueue.list_queues()
        assert any(c["queue_id"] == "elencabile" for c in elenco)


class TestRiempimento:
    def test_si_puo_riempire_con_dizionari(self):
        q = WorkQueue("dettagliata")
        q.add_many([
            {"id": "f1", "title": "traduci sigma_network", "modulo": "sigma_network"},
        ])
        v = q.items()[0]
        assert v.id == "f1"
        assert v.payload["modulo"] == "sigma_network"

    def test_un_id_ripetuto_non_duplica_il_lavoro(self):
        """Riempire due volte la stessa coda e' cio' che succede riprendendo
        un lavoro: non deve raddoppiarlo."""
        q = WorkQueue("idempotente")
        q.add_many([{"id": "f1", "title": "uno"}])
        q.add_many([{"id": "f1", "title": "uno"}, {"id": "f2", "title": "due"}])
        assert len(q.items()) == 2

    def test_il_consuntivo_dice_a_che_punto_e(self):
        q = _coda()
        v = q.claim()
        q.complete(v.id)
        p = q.progress()
        assert (p["total"], p["done"], p["todo"], p["doing"]) == (3, 1, 2, 0)
        assert p["finished"] is False
