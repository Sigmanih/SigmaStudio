"""Chi guarda deve vedere cosa sta girando, chiunque lo abbia lanciato.

Un ventaglio lanciato da riga di comando non compariva da nessuna parte nel
Developer Studio: l'interfaccia mostrava un sistema fermo mentre due agenti
riscrivevano il progetto. E la chat, interrogata nello stesso momento,
rispondeva come se nulla stesse accadendo — e poteva mettersi a modificare gli
stessi file.

La causa non era l'interfaccia: era che «cosa sta girando» non esisteva come
dato. Ogni percorso d'ingresso apriva il proprio run e lo teneva per se', e lo
stream degli eventi vale solo per chi e' attaccato a quello stream.
"""

import time

import pytest

from core.harness import attivita as A


@pytest.fixture(autouse=True)
def registro_isolato(tmp_path, monkeypatch):
    """Questi test non devono scrivere nel `var/` vero."""
    monkeypatch.setattr(A.paths, "var_dir", lambda: tmp_path)
    yield


class TestIlRegistroDiceLaVerita:
    def test_una_voce_aperta_risulta_attiva(self):
        A.apri("ventaglio", "coda biblioteca", queue_id="biblioteca")
        stato = A.stato()
        assert stato["busy"] is True
        assert stato["count"] == 1
        assert stato["running"][0]["queue_id"] == "biblioteca"

    def test_chiusa_non_risulta_piu_attiva_ma_resta_nello_storico(self):
        voce = A.apri("agente", "scrivi il parser")
        A.chiudi(voce, "obiettivo raggiunto", turni=9)
        stato = A.stato()
        assert stato["busy"] is False
        assert stato["recent"][0]["esito"] == "obiettivo raggiunto"
        assert stato["recent"][0]["turni"] == 9

    def test_l_avanzamento_si_aggiorna(self):
        voce = A.apri("obiettivo", "rendere traducibile sigma_network")
        A.aggiorna(voce, progress="fase Implementazione (coder)")
        assert A.attive()[0]["progress"] == "fase Implementazione (coder)"

    def test_una_voce_senza_battito_non_e_viva(self, monkeypatch):
        """Un processo che muore non chiude la propria riga. Senza scadenza il
        registro direbbe per sempre che qualcosa sta girando, e la chat si
        rifiuterebbe di lavorare per un agente che non c'e' piu'."""
        A.apri("agente", "run morto")
        # `A.time` E' il modulo time: sostituendo time.time con una lambda che
        # chiama time.time si ottiene una ricorsione infinita. Il valore vero
        # va preso prima.
        adesso = time.time()
        monkeypatch.setattr(A.time, "time", lambda: adesso + A.SCADENZA_S + 10)
        stato = A.stato()
        assert stato["busy"] is False
        assert "nessun battito" in stato["recent"][0]["esito"]

    def test_il_battito_tiene_viva_la_voce(self, monkeypatch):
        partenza = time.time()
        voce = A.apri("agente", "run vivo")
        monkeypatch.setattr(A.time, "time", lambda: partenza + A.SCADENZA_S - 5)
        A.aggiorna(voce, progress="turno 12")
        monkeypatch.setattr(A.time, "time", lambda: partenza + A.SCADENZA_S + 5)
        assert A.stato()["busy"] is True, "l'aggiornamento ha rinnovato il battito"

    def test_aggiornare_una_voce_che_non_esiste_non_esplode(self):
        A.aggiorna("mai_esistita", progress="x")
        A.chiudi("mai_esistita", "boh")

    def test_lo_storico_ha_un_tetto(self):
        for i in range(A.STORICO_MASSIMO + 12):
            A.chiudi(A.apri("agente", f"run {i}"), "finito")
        assert len(A.storico(999)) == A.STORICO_MASSIMO

    def test_il_registro_sopravvive_al_processo(self, tmp_path):
        """La domanda «cosa sta girando» arriva da una richiesta HTTP diversa
        da quella che sta lavorando, e spesso da una scheda aperta dopo."""
        A.apri("ventaglio", "lavoro lungo")
        assert (tmp_path / "attivita.json").is_file()
        assert A.stato()["count"] == 1


class TestLaRigaPerLaChat:
    def test_a_riposo_non_dice_niente(self):
        assert A.riga_per_la_chat() == ""

    def test_al_lavoro_dice_cosa_e_dove(self):
        A.apri("ventaglio", "traduci i moduli",
               workspace_root="C:/progetti/app")
        riga = A.riga_per_la_chat()
        assert "sta lavorando" in riga
        assert "traduci i moduli" in riga
        assert "C:/progetti/app" in riga

    def test_avverte_del_rischio_sui_file(self):
        """E' il motivo per cui questa riga esiste: chat e agenti scrivono
        negli stessi file."""
        A.apri("obiettivo", "x")
        assert "stessi" in A.riga_per_la_chat()


class TestTuttiEQuattroIPercorsiSiRegistrano:
    """Un registro che copre due ingressi su tre e' un registro che mente:
    l'interfaccia direbbe «fermo» proprio nel caso che non copre."""

    def test_il_ciclo_dell_agente(self):
        import inspect

        from core.harness.loop import stream_admin_agent_turn

        sorgente = inspect.getsource(stream_admin_agent_turn)
        assert "attivita.apri(" in sorgente
        assert "attivita.chiudi(" in sorgente
        assert "attivita.aggiorna(" in sorgente, "senza battito la voce scade"

    def test_il_ventaglio(self):
        import inspect

        from core.harness import fanout

        sorgente = inspect.getsource(fanout.run_queue)
        assert "attivita.apri(" in sorgente
        assert "attivita.chiudi(" in sorgente

    def test_l_obiettivo_della_squadra(self):
        import inspect

        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        apertura = inspect.getsource(DevOrchestrator.execute_goal)
        assert "attivita.apri(" in apertura
        assert "attivita.chiudi(" in apertura

        fase = inspect.getsource(DevOrchestrator._run_phase)
        assert "attivita.aggiorna(" in fase, (
            "la fase corrente e' cio' che la UI mostra: senza, il registro "
            "direbbe solo che qualcosa gira, non a che punto e'")

    def test_la_chat(self):
        import inspect

        from core.chat import chat_runner

        sorgente = inspect.getsource(chat_runner)
        assert "riga_per_la_chat()" in sorgente
        assert "volatile_parts.append(riga_agenti)" in sorgente, (
            "nel prefisso stabile invaliderebbe la cache a ogni messaggio")


def test_la_rotta_esiste():
    import core.fastapi_app as app_mod

    rotte = {getattr(r, "path", "") for r in app_mod.app.routes}
    assert "/api/harness/activity" in rotte
