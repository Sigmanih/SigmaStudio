"""Piu' agenti sullo stesso obiettivo, in parallelo, sulla stessa coda.

C'e' un ciclo per volta e un orchestratore che fa lavorare cinque ruoli uno
dopo l'altro. Per duecento file non basta, e non e' questione di pazienza: il
contesto di un singolo run non ci sta, e a meta' strada l'agente non ricorda
piu' cosa aveva gia' sistemato.

I test qui sotto non provano che l'agente scriva bene — quello lo provano
altrove. Provano che il ventaglio **non perde e non duplica lavoro**: ogni voce
tocca a un lavoratore solo, chi fallisce non blocca gli altri, e fermarsi ferma
davvero.
"""

import threading
import time

import pytest

from core.harness import fanout, workqueue


@pytest.fixture(autouse=True)
def coda_isolata(tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
    workqueue._code.clear()
    yield
    workqueue._code.clear()


def _run_finto(non_riesce=(), ritardo=0.0, esplode_su=()):
    """Sostituisce il ciclo dell'agente con qualcosa di prevedibile.

    Il ventaglio non deve sapere cosa fa l'agente: deve sapere quando ha finito
    e se ha raggiunto l'obiettivo. E' esattamente quello che si simula qui.
    """
    visti, lucchetto = [], threading.Lock()
    insieme = threading.Semaphore(0)

    def finto(messages, **kw):
        titolo = messages[0]["content"].splitlines()[0]
        with lucchetto:
            visti.append(titolo)
        if titolo in esplode_su:
            raise RuntimeError("il run e' morto")
        if ritardo:
            time.sleep(ritardo)
        yield {"type": "ledger", "state": {"modified_files": [f"{titolo}.py"]}}
        yield {"type": "run_metrics", "turns": 3,
               "goal_reached": titolo not in non_riesce}
        yield {"type": "done", "full_text": ""}

    finto.visti = visti
    finto.insieme = insieme
    return finto


def _esegui(monkeypatch, coda_id, titoli, workers=2, finto=None, **kw):
    from core.harness import loop as modulo_loop

    finto = finto or _run_finto()
    monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)

    q = workqueue.get_queue(coda_id, goal="tradurre l'interfaccia")
    q.add_many(list(titoli))
    eventi = list(fanout.run_queue(
        coda_id, workspace_root=".", workers=workers, deliver=False, **kw
    ))
    return q, eventi, finto


class TestNienteSiPerdeENienteSiDuplica:
    def test_tutte_le_voci_vengono_lavorate(self, monkeypatch):
        q, eventi, finto = _esegui(monkeypatch, "c1", [f"voce {i}" for i in range(6)])

        assert q.progress()["done"] == 6
        assert q.is_finished() is True
        assert len(finto.visti) == 6

    def test_nessuna_voce_viene_lavorata_due_volte(self, monkeypatch):
        """La proprieta' che rende il parallelismo utile invece che dannoso."""
        q, eventi, finto = _esegui(
            monkeypatch, "c2", [f"voce {i}" for i in range(8)],
            workers=4, finto=_run_finto(ritardo=0.01),
        )
        assert sorted(finto.visti) == sorted(f"voce {i}" for i in range(8))

    def test_ogni_voce_produce_un_inizio_e_una_fine(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c3", ["a", "b", "c"])

        iniziate = [e for e in eventi if e["type"] == "item_started"]
        finite = [e for e in eventi if e["type"] == "item_finished"]
        assert len(iniziate) == 3
        assert len(finite) == 3
        assert all(e["ok"] for e in finite)

    def test_il_lavoro_viene_diviso_fra_i_lavoratori(self, monkeypatch):
        """Con un ritardo, un lavoratore solo non puo' averle prese tutte."""
        q, eventi, _ = _esegui(
            monkeypatch, "c4", [f"v{i}" for i in range(6)],
            workers=3, finto=_run_finto(ritardo=0.05),
        )
        lavoratori = {e["worker"] for e in eventi if e["type"] == "item_finished"}
        assert len(lavoratori) > 1, "hanno lavorato tutte lo stesso thread"


class TestQuandoUnaVoceVaMale:
    def test_una_voce_non_riuscita_non_ferma_le_altre(self, monkeypatch):
        q, eventi, _ = _esegui(
            monkeypatch, "c5", ["buona", "cattiva", "altra"],
            finto=_run_finto(non_riesce=("cattiva",)),
        )
        p = q.progress()
        assert p["done"] == 2
        assert p["todo"] + p["failed"] == 1

    def test_un_run_che_muore_diventa_un_fallimento_registrato(self, monkeypatch):
        """Un lavoratore che muore lascerebbe gli altri a girare a vuoto."""
        q, eventi, _ = _esegui(
            monkeypatch, "c6", ["buona", "esplosiva"],
            workers=1, finto=_run_finto(esplode_su=("esplosiva",)),
        )
        finite = [e for e in eventi if e["type"] == "item_finished"]
        rotta = [e for e in finite if e["title"] == "esplosiva"]
        assert rotta and rotta[0]["ok"] is False
        assert "morto" in rotta[0]["error"]
        assert q.progress()["done"] == 1

    def test_una_voce_che_fallisce_va_in_fondo_non_in_testa(self, monkeypatch):
        """Restando dov'era, il lavoratore la riprenderebbe subito e la
        rifarebbe tre volte prima che il resto della coda avanzi: una voce
        difficile fermerebbe duecento voci facili."""
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn",
                            _run_finto(non_riesce=("difficile",)))
        q = workqueue.get_queue("c7", goal="x")
        q.add_many(["difficile", "facile uno", "facile due"])
        _, eventi, _ = None, list(fanout.run_queue(
            "c7", workspace_root=".", workers=1, deliver=False)), None

        ordine = [e["title"] for e in eventi if e["type"] == "item_started"]
        # Le facili non aspettano che la difficile esaurisca i tentativi.
        assert ordine[:3] == ["difficile", "facile uno", "facile due"]
        assert q.progress()["done"] == 2

    def test_finiti_i_tentativi_la_voce_si_arrende_e_la_coda_finisce(self, monkeypatch):
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn",
                            _run_finto(non_riesce=("sola",)))
        q = workqueue.get_queue("c7bis", goal="x")
        q.add_many(["sola"])
        list(fanout.run_queue("c7bis", workspace_root=".", workers=1, deliver=False))

        assert q.progress()["failed"] == 1
        assert q.is_finished() is True


class TestFermarsi:
    def test_annullare_ferma_il_ventaglio(self, monkeypatch):
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn",
                            _run_finto(ritardo=0.05))
        q = workqueue.get_queue("c8", goal="x")
        q.add_many([f"v{i}" for i in range(40)])

        fermare = threading.Event()
        threading.Timer(0.25, fermare.set).start()
        eventi = list(fanout.run_queue(
            "c8", workspace_root=".", workers=2, deliver=False,
            should_cancel=fermare.is_set,
        ))

        finale = [e for e in eventi if e["type"] == "fanout_finished"][0]
        assert finale["cancelled"] is True
        assert q.progress()["done"] < 40, "non doveva finirle tutte"

    def test_il_lavoro_fatto_prima_dello_stop_resta_fatto(self, monkeypatch):
        """E' il motivo per cui la coda sta su disco."""
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn",
                            _run_finto(ritardo=0.05))
        q = workqueue.get_queue("c9", goal="x")
        q.add_many([f"v{i}" for i in range(30)])

        fermare = threading.Event()
        threading.Timer(0.3, fermare.set).start()
        list(fanout.run_queue("c9", workspace_root=".", workers=2,
                              deliver=False, should_cancel=fermare.is_set))
        fatti = q.progress()["done"]

        workqueue._code.clear()
        riaperta = workqueue.WorkQueue("c9")
        assert riaperta.progress()["done"] == fatti
        assert fatti > 0


class TestGliEventiRaccontanoIlLavoro:
    def test_si_comincia_dicendo_quanti_e_quanto(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c10", ["a", "b"], workers=2)
        inizio = eventi[0]
        assert inizio["type"] == "fanout_started"
        assert inizio["workers"] == 2
        assert inizio["total"] == 2

    def test_il_progresso_arriva_mentre_gira(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c11", ["a", "b", "c"])
        progressi = [e for e in eventi if e["type"] == "fanout_progress"]
        assert len(progressi) == 3
        assert progressi[-1]["done"] == 3

    def test_si_finisce_con_il_consuntivo(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c12", ["a"])
        finale = eventi[-1]
        assert finale["type"] == "fanout_finished"
        assert finale["cancelled"] is False
        assert finale["done"] == 1


class TestIlNumeroDiLavoratori:
    def test_un_numero_assurdo_non_produce_zero_lavoratori(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c13", ["a"], workers=-5)
        assert eventi[0]["workers"] == 1
        assert q.progress()["done"] == 1

    def test_non_indicarlo_vale_il_predefinito(self, monkeypatch):
        q, eventi, _ = _esegui(monkeypatch, "c13bis", ["a"], workers=0)
        assert eventi[0]["workers"] == fanout.LAVORATORI_PREDEFINITI

    def test_non_si_sale_oltre_il_tetto(self, monkeypatch):
        """Oltre un certo punto non e' parallelismo, e' contesa: la banda verso
        i pesi del modello e' condivisa."""
        q, eventi, _ = _esegui(monkeypatch, "c14", ["a"], workers=99)
        assert eventi[0]["workers"] == fanout.LAVORATORI_MASSIMI


class TestIlCompitoDelSingoloLavoratore:
    def test_la_voce_viene_prima_dell_obiettivo_generale(self):
        """Cio' che l'agente deve fare adesso e' la voce; l'obiettivo serve a
        capirla, non a sostituirla."""
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(
            Voce(id="x", title="traduci sigma_network/index.jsx"),
            "rendere impostabile la lingua",
        )
        assert testo.startswith("traduci sigma_network/index.jsx")
        assert "rendere impostabile la lingua" in testo

    def test_l_agente_viene_avvisato_che_non_e_solo(self):
        """Senza, riscriverebbe parti condivise mentre un altro le sta toccando."""
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(Voce(id="x", title="un pezzo"), "l'obiettivo")
        assert "in parallelo" in testo

    def test_i_dettagli_della_voce_arrivano_all_agente(self):
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(
            Voce(id="x", title="traduci", payload={"modulo": "sigma_network"}), "")
        assert "modulo: sigma_network" in testo


class TestOgniLavoratoreNelProprioWorktree:
    """E' cio' che rende sicuro farli scrivere nello stesso momento: senza,
    questo modulo sarebbe un modo elegante di corrompere un repository."""

    def test_ogni_run_chiede_l_isolamento(self, monkeypatch):
        from core.harness import loop as modulo_loop

        opzioni = []

        def finto(messages, **kw):
            opzioni.append(kw)
            yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)
        q = workqueue.get_queue("c15", goal="x")
        q.add_many(["a", "b"])
        list(fanout.run_queue("c15", workspace_root=".", workers=1, deliver=False))

        assert opzioni, "nessun run avviato"
        assert all(o.get("isolate_worktree") for o in opzioni)

    def test_ogni_run_ha_una_sessione_diversa(self, monkeypatch):
        """Sessioni uguali significherebbero lo stesso worktree, cioe' due
        agenti che si scrivono addosso."""
        from core.harness import loop as modulo_loop

        sessioni = []

        def finto(messages, **kw):
            sessioni.append(kw.get("session_id"))
            yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)
        q = workqueue.get_queue("c16", goal="x")
        q.add_many(["a", "b", "c"])
        list(fanout.run_queue("c16", workspace_root=".", workers=2, deliver=False))

        assert len(sessioni) == 3
        assert len(set(sessioni)) == 3


class TestRaggiungibilita:
    """Il difetto ricorrente di questo progetto: scritto, testato, scollegato."""

    def test_esistono_le_rotte_per_creare_e_far_girare_una_coda(self):
        import inspect
        from core import fastapi_app

        sorgente = inspect.getsource(fastapi_app)
        assert '"/api/harness/queue"' in sorgente
        assert '"/api/harness/queues"' in sorgente
        assert '"/api/harness/fanout"' in sorgente

    def test_la_rotta_del_ventaglio_usa_davvero_il_ventaglio(self):
        import inspect
        from core import fastapi_app

        sorgente = inspect.getsource(fastapi_app.api_harness_fanout)
        assert "from core.harness.fanout import run_queue" in sorgente
        assert "run_queue(queue_id" in sorgente


class TestLaProvaRichiestaDaUnaVoce:
    """Difetto trovato dal vivo: un agente ha scritto il file giusto, non ha
    saputo dimostrarlo, il cancello di completamento l'ha respinto, e la voce e'
    stata riprovata tre volte per nulla. Dire in anticipo come si dimostra il
    lavoro costa una riga e vale tre run."""

    def test_una_voce_puo_dichiarare_il_comando_che_la_dimostra(self):
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(
            Voce(id="x", title="crea locales/it.json",
                 payload={"verify": "python -m json.tool locales/it.json"}),
            "tradurre l'interfaccia",
        )
        assert "VERIFICA RICHIESTA" in testo
        assert "python -m json.tool locales/it.json" in testo

    def test_il_comando_di_verifica_non_finisce_fra_i_dettagli(self):
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(
            Voce(id="x", title="crea x", payload={"verify": "pytest -q"}), "")
        assert "verify: pytest -q" not in testo

    def test_senza_comando_l_agente_viene_avvisato_che_dovra_trovarne_uno(self):
        from core.harness.workqueue import Voce

        testo = fanout._prompt_voce(Voce(id="x", title="crea x"), "")
        assert "DIMOSTRARE" in testo
        assert "codice 0" in testo


class TestLavoroProdottoMaNonDimostrato:
    """Non e' la stessa cosa di «non ha fatto niente», e chiede un rimedio
    diverso: riprovare identico non aggiunge una prova."""

    def test_l_errore_dice_dov_e_finito_il_lavoro(self, tmp_path, monkeypatch):
        """Lo snapshot e' quello vero, non uno inventato: la prima versione di
        questo test usava una chiave che nel ledger non esiste, ed e' per
        questo che non ha visto il difetto."""
        from core.harness import loop as modulo_loop
        from core.harness.ledger import DevSessionLedger

        led = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        for nome in ("a.py", "b.py"):
            led.record_tool("write_file", {"path": nome},
                            {"success": True, "path": str(tmp_path / nome)})
        stato = led.snapshot()

        def scrive_e_non_dimostra(messages, **kw):
            yield {"type": "ledger", "state": stato}
            yield {"type": "run_metrics", "turns": 8, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", scrive_e_non_dimostra)
        q = workqueue.get_queue("c20", goal="x")
        q.add_many(["una voce"])
        eventi = list(fanout.run_queue("c20", workspace_root=".", workers=1,
                                       deliver=False))

        finita = [e for e in eventi if e["type"] == "item_finished"][0]
        assert finita["ok"] is False
        assert "non dimostrato" in finita["error"]
        assert "2 file" in finita["error"]
        assert finita["branch"].startswith("sigma-run/")

    def test_non_aver_fatto_niente_si_dice_diversamente(self, monkeypatch):
        from core.harness import loop as modulo_loop

        def non_fa_niente(messages, **kw):
            yield {"type": "run_metrics", "turns": 8, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", non_fa_niente)
        q = workqueue.get_queue("c21", goal="x")
        q.add_many(["una voce"])
        eventi = list(fanout.run_queue("c21", workspace_root=".", workers=1,
                                       deliver=False))

        finita = [e for e in eventi if e["type"] == "item_finished"][0]
        assert "nessuna modifica prodotta" in finita["error"]

    def test_anche_una_voce_riuscita_dice_su_quale_branch_sta(self, monkeypatch):
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", _run_finto())
        q = workqueue.get_queue("c22", goal="x")
        q.add_many(["una voce"])
        eventi = list(fanout.run_queue("c22", workspace_root=".", workers=1,
                                       deliver=False))

        finita = [e for e in eventi if e["type"] == "item_finished"][0]
        assert finita["ok"] is True
        assert finita["branch"].startswith("sigma-run/")


class TestQualiFileHaCambiatoDavvero:
    """Difetto trovato dal vivo: il ventaglio leggeva dallo stato del ledger una
    chiave `modified_files` che non esiste. La lista restava sempre vuota, e il
    resoconto diceva «nessuna modifica prodotta» su run che avevano scritto il
    file giusto — un messaggio che mente e' il modo peggiore in cui puo'
    rompersi un resoconto.

    Il test qui sotto usa uno snapshot **vero**, non uno inventato: era proprio
    il finto a nascondere il difetto.
    """

    def _snapshot_vero(self, tmp_path, scritti=(), letti=()):
        from core.harness.ledger import DevSessionLedger

        led = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        for nome in letti:
            led.record_tool("read_file", {"path": nome},
                            {"success": True, "path": str(tmp_path / nome),
                             "content": "x", "total_lines": 1})
        for nome in scritti:
            led.record_tool("write_file", {"path": nome},
                            {"success": True, "path": str(tmp_path / nome)})
        return led.snapshot()

    def test_i_file_scritti_vengono_riconosciuti(self, tmp_path):
        stato = self._snapshot_vero(tmp_path, scritti=("a.py", "b.py"))
        trovati = fanout._file_modificati(stato)
        assert len(trovati) == 2
        assert any(t.endswith("a.py") for t in trovati)

    def test_un_file_solo_letto_non_e_una_modifica(self, tmp_path):
        stato = self._snapshot_vero(tmp_path, letti=("visto.py",))
        assert fanout._file_modificati(stato) == []

    def test_uno_stato_vuoto_non_esplode(self):
        assert fanout._file_modificati({}) == []
        assert fanout._file_modificati({"files": None}) == []

    def test_il_ventaglio_non_dice_piu_che_non_e_stato_fatto_niente(
        self, tmp_path, monkeypatch
    ):
        """Il difetto in una riga: lavoro prodotto, resoconto che lo nega."""
        from core.harness import loop as modulo_loop

        stato = self._snapshot_vero(tmp_path, scritti=("locales/it.json",))

        def scrive_senza_dimostrare(messages, **kw):
            yield {"type": "ledger", "state": stato}
            yield {"type": "run_metrics", "turns": 12, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn",
                            scrive_senza_dimostrare)
        q = workqueue.get_queue("c23", goal="x")
        q.add_many(["una voce"])
        eventi = list(fanout.run_queue("c23", workspace_root=".", workers=1,
                                       deliver=False))

        finita = [e for e in eventi if e["type"] == "item_finished"][0]
        assert "non dimostrato" in finita["error"]
        assert "nessuna modifica" not in finita["error"]
        assert len(finita["files"]) == 1

    def test_il_branch_arriva_dall_evento_del_ciclo(self, monkeypatch):
        from core.harness import loop as modulo_loop

        def con_branch(messages, **kw):
            yield {"type": "worktree_preserved", "branch": "sigma-run/vero", "checkpoints": 2}
            yield {"type": "run_metrics", "turns": 5, "goal_reached": False}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", con_branch)
        q = workqueue.get_queue("c24", goal="x")
        q.add_many(["una voce"])
        eventi = list(fanout.run_queue("c24", workspace_root=".", workers=1,
                                       deliver=False))

        finita = [e for e in eventi if e["type"] == "item_finished"][0]
        assert finita["branch"] == "sigma-run/vero"


class TestLaSceltaSullaConsegna:
    """`deliver` era dichiarato, passato al lavoratore, e li' ignorato: il ciclo
    decideva comunque dalla configurazione, e chiedere «non consegnare» non
    aveva alcun effetto."""

    def _opzioni_viste(self, monkeypatch, **kw):
        from core.harness import loop as modulo_loop

        viste = []

        def finto(messages, **opzioni):
            viste.append(opzioni)
            yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)
        q = workqueue.get_queue(kw.pop("coda"), goal="x")
        q.add_many(["una voce"])
        list(fanout.run_queue(q.queue_id, workspace_root=".", workers=1, **kw))
        return viste[0]

    def test_non_consegnare_arriva_al_ciclo(self, monkeypatch):
        assert self._opzioni_viste(monkeypatch, coda="c30", deliver=False)["deliver"] is False

    def test_consegnare_arriva_al_ciclo(self, monkeypatch):
        assert self._opzioni_viste(monkeypatch, coda="c31", deliver=True)["deliver"] is True

    def test_la_prova_della_voce_arriva_al_ciclo(self, monkeypatch):
        from core.harness import loop as modulo_loop

        viste = []

        def finto(messages, **opzioni):
            viste.append(opzioni)
            yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)
        q = workqueue.get_queue("c32", goal="x")
        q.add_many([{"id": "v", "title": "fai", "payload": {"verify": "pytest -q"}}])
        list(fanout.run_queue("c32", workspace_root=".", workers=1, deliver=False))

        assert viste[0]["verify_command"] == "pytest -q"


# ==============================================================================
# La diagnosi arriva anche al ventaglio
# ==============================================================================
# L'orchestratore guarda cos'e' andato storto e sceglie la mossa. Il ventaglio —
# che e' il percorso per il lavoro *grande*, dove i fallimenti costano di piu' —
# rimetteva la voce in coda tre volte identica, e la terza falliva come la
# prima. Riprovare identico dopo un fallimento e' esattamente cio' che il banco
# sul protocollo misura come errore in un modello: vale anche per il sistema.

class TestUnaVoceFallitaImparaQualcosa:
    def _voce_e_coda(self, tmp_path, monkeypatch):
        from core.harness import workqueue as WQ

        monkeypatch.setattr(WQ.paths, "var_dir", lambda: tmp_path)
        WQ._code.clear()
        coda = WQ.get_queue("diagnosi")
        coda.add_many([{"id": "v1", "title": "scrivi il modulo"}])
        return coda, coda.claim("w1")

    def test_il_motivo_finisce_nell_errore_della_voce(self, tmp_path, monkeypatch):
        from core.harness import fanout, workqueue as WQ
        from core.harness.ledger import DevSessionLedger

        coda, voce = self._voce_e_coda(tmp_path, monkeypatch)
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        ledger.record_tool("write_file", {"path": "app.py"}, {
            "tool": "write_file", "success": True, "path": "app.py",
            "full_path": "app.py", "content": "x\n", "created": True})
        ledger.record_tool("terminal", {"command": "python -m pytest -q"}, {
            "tool": "terminal", "success": False, "command": "python -m pytest -q",
            "returncode": 1, "stdout": "2 failed", "stderr": ""})

        esito = fanout.EsitoVoce(item_id="v1", title="scrivi il modulo", ok=False,
                                 error="lavoro prodotto ma non dimostrato",
                                 files=["app.py"])
        fanout._annota_la_diagnosi(coda, voce, esito, ledger.snapshot())

        assert esito.diagnosi == "correggi"
        assert "verifiche fallite" in esito.error
        WQ._code.clear()

    def test_il_tentativo_successivo_riceve_cio_che_si_e_imparato(
            self, tmp_path, monkeypatch):
        """Se la voce torna in coda senza portarsi dietro la diagnosi, il
        secondo tentativo e' il primo."""
        from core.harness import fanout, workqueue as WQ
        from core.harness.ledger import DevSessionLedger

        coda, voce = self._voce_e_coda(tmp_path, monkeypatch)
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        ledger.record_tool("write_file", {"path": "app.py"}, {
            "tool": "write_file", "success": True, "path": "app.py",
            "full_path": "app.py", "content": "x\n", "created": True})
        ledger.record_tool("terminal", {"command": "python app.py"}, {
            "tool": "terminal", "success": False, "command": "python app.py",
            "returncode": 1, "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'validatore'"})

        esito = fanout.EsitoVoce(item_id="v1", title="scrivi il modulo", ok=False,
                                 error="non dimostrato", files=["app.py"])
        fanout._annota_la_diagnosi(coda, voce, esito, ledger.snapshot())

        nota = voce.payload.get("nota dal tentativo precedente", "")
        assert nota, "la diagnosi deve arrivare a chi riprova"
        # E il prompt della voce la deve stampare: una nota nel payload che
        # nessuno legge non e' una nota.
        assert "nota dal tentativo precedente" in fanout._prompt_voce(voce, "")
        WQ._code.clear()

    def test_una_diagnosi_impossibile_non_fa_fallire_di_piu(
            self, tmp_path, monkeypatch):
        """Accessoria per costruzione: se la diagnosi va storta, la voce
        fallisce comunque come prima. Si perde il consiglio, non il resto."""
        from core.harness import fanout, workqueue as WQ

        coda, voce = self._voce_e_coda(tmp_path, monkeypatch)
        esito = fanout.EsitoVoce(item_id="v1", title="x", ok=False,
                                 error="originale")
        fanout._annota_la_diagnosi(coda, voce, esito, None)
        assert "originale" in esito.error
        WQ._code.clear()

    def test_l_esito_porta_la_diagnosi_a_chi_guarda(self):
        from core.harness import fanout

        esito = fanout.EsitoVoce(item_id="v", title="t", ok=False,
                                 diagnosi="ripianifica")
        assert esito.to_dict()["diagnosi"] == "ripianifica"

    def test_il_percorso_di_fallimento_la_chiama(self):
        import inspect

        from core.harness import fanout

        assert "_annota_la_diagnosi(" in inspect.getsource(fanout._esegui_voce)
