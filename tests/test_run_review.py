"""La revisione di tutto il lavoro di un run, una volta sola.

Il cancello per singola scrittura funziona su un obiettivo circoscritto e non
regge su uno grande: un lavoro da duecento file chiederebbe duecento
approvazioni, nessuno le da', e il risultato pratico sarebbe spegnere la
revisione — cioe' perdere la rete di sicurezza esattamente dove serve di piu'.

La forma giusta a quella scala e' guardare una volta cio' che il run ha
prodotto e decidere se trasferirlo. Ha senso solo dentro un worktree isolato:
senza, le modifiche sono gia' nell'albero vivo e "rifiuto" non avrebbe niente
da rifiutare.

Due proprieta' non negoziabili, e sono quelle che i test qui sotto tengono
ferme:

1. **il diff mostrato e' quello che verrebbe applicato** — stessa base, stesso
   contenuto, file nuovi e ultimo turno compresi;
2. **un rifiuto non perde il lavoro**: resta sul branch della sessione.
"""

import subprocess

import pytest

from core.harness import review, worktree


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "progetto"
    r.mkdir()
    for args in (["init"], ["config", "user.email", "t@s.local"],
                 ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git"] + args, cwd=str(r), capture_output=True)
    (r / "esistente.py").write_text("VALORE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(r), capture_output=True)
    subprocess.run(["git", "commit", "-m", "iniziale"], cwd=str(r), capture_output=True)
    return r


@pytest.fixture
def sessione(repo, tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
    s = worktree.create_session_worktree(repo, "sess-revisione")
    assert s is not None
    yield s
    worktree.release_session_worktree("sess-revisione")


class TestIlDiffDelRun:
    def test_comprende_i_file_nuovi_mai_committati(self, sessione):
        """I file nuovi non sono tracciati: un `git diff` normale non li vede,
        e su un lavoro di internazionalizzazione sono la maggior parte."""
        (sessione.worktree_path / "nuovo.py").write_text("A = 1\n", encoding="utf-8")

        assert "nuovo.py" in sessione.changed_files()
        assert "+A = 1" in sessione.diff_from_main()

    def test_comprende_il_lavoro_dopo_l_ultimo_checkpoint(self, sessione):
        """Mostrare meno di cio' che verrebbe applicato significa far approvare
        una cosa e applicarne un'altra."""
        (sessione.worktree_path / "uno.py").write_text("A = 1\n", encoding="utf-8")
        sessione.checkpoint(1)
        (sessione.worktree_path / "due.py").write_text("B = 2\n", encoding="utf-8")

        toccati = sessione.changed_files()
        assert "uno.py" in toccati and "due.py" in toccati

    def test_la_base_sopravvive_a_un_rollback(self, sessione):
        """`HEAD~<numero checkpoint>` mente appena c'e' stato un rollback: era
        lo stesso difetto che applicava all'albero principale la porzione
        sbagliata del lavoro."""
        (sessione.worktree_path / "buono.py").write_text("A = 1\n", encoding="utf-8")
        sessione.checkpoint(1)
        (sessione.worktree_path / "sbagliato.py").write_text("B = 2\n", encoding="utf-8")
        sessione.checkpoint(2)
        sessione.rollback(1)

        toccati = sessione.changed_files()
        assert toccati == ["buono.py"]

    def test_lo_stat_e_la_vista_d_insieme(self, sessione):
        for i in range(3):
            (sessione.worktree_path / f"f{i}.py").write_text("X = 1\n", encoding="utf-8")

        stat = sessione.diff_stat_from_main()
        assert "f0.py" in stat and "f2.py" in stat
        assert "3 files changed" in stat or "3 file" in stat

    def test_un_run_che_non_tocca_niente_non_ha_diff(self, sessione):
        assert sessione.changed_files() == []
        assert sessione.diff_from_main().strip() == ""

    def test_il_diff_mostrato_e_quello_che_verrebbe_applicato(self, sessione, repo):
        """La proprieta' che rende la revisione una garanzia e non una vetrina."""
        (sessione.worktree_path / "nuovo.py").write_text("A = 1\n", encoding="utf-8")
        (sessione.worktree_path / "esistente.py").write_text("VALORE = 2\n", encoding="utf-8")
        promessi = set(sessione.changed_files())

        assert sessione.apply_to_main() is True

        applicati = set()
        for nome in promessi:
            assert (repo / nome).exists(), f"{nome} era nel diff ma non e' arrivato"
            applicati.add(nome)
        assert applicati == promessi
        assert (repo / "esistente.py").read_text(encoding="utf-8") == "VALORE = 2\n"


class TestLaDecisioneSulRun:
    """La revisione blocca il run finche' non arriva un giudizio, e il rifiuto
    non butta via niente."""

    def _finto_worktree(self, branch="sigma-run/x", file=("a.py",)):
        class Finto:
            branch_name = branch
            def diff_stat_from_main(self): return " a.py | 2 +-\n"
            def changed_files(self): return list(file)
            def diff_from_main(self): return "--- a/a.py\n+++ b/a.py\n+X = 1\n"
        return Finto()

    def test_approvare_fa_applicare(self):
        from core.harness.loop import _rivedi_lavoro_del_run
        import threading

        gate = review.ReviewGate(timeout_s=5.0)
        eventi = []
        gen = _rivedi_lavoro_del_run(self._finto_worktree(), gate, "s1", True)

        primo = next(gen)
        assert primo["type"] == "run_diff_proposed"
        assert primo["file_count"] == 1
        threading.Timer(0.05, lambda: gate.decide(primo["id"], "approved")).start()
        eventi = list(gen)

        assert eventi[0]["type"] == "run_diff_decided"
        assert eventi[0]["applied"] is True
        assert eventi[-1] == {"type": "__decisione__", "apply": True}

    def test_rifiutare_non_applica_ma_dice_dov_e_il_lavoro(self):
        from core.harness.loop import _rivedi_lavoro_del_run
        import threading

        gate = review.ReviewGate(timeout_s=5.0)
        gen = _rivedi_lavoro_del_run(self._finto_worktree(), gate, "s2", True)
        proposta = next(gen)
        threading.Timer(0.05, lambda: gate.decide(proposta["id"], "rejected")).start()
        eventi = list(gen)

        deciso = eventi[0]
        assert deciso["applied"] is False
        assert deciso["branch"] == "sigma-run/x"
        assert eventi[-1] == {"type": "__decisione__", "apply": False}

    def test_il_silenzio_non_applica(self):
        """Come per la revisione per file: chi non risponde non ha approvato."""
        from core.harness.loop import _rivedi_lavoro_del_run

        gate = review.ReviewGate(timeout_s=0.15)
        eventi = list(_rivedi_lavoro_del_run(self._finto_worktree(), gate, "s3", True))
        assert eventi[-1] == {"type": "__decisione__", "apply": False}

    def test_un_run_senza_modifiche_non_chiede_niente(self):
        from core.harness.loop import _rivedi_lavoro_del_run

        class Vuoto:
            branch_name = "b"
            def diff_stat_from_main(self): return ""
            def changed_files(self): return []
            def diff_from_main(self): return ""

        gate = review.ReviewGate(timeout_s=5.0)
        eventi = list(_rivedi_lavoro_del_run(Vuoto(), gate, "s4", True))
        assert eventi == [{"type": "__decisione__", "apply": True}]

    def test_un_diff_enorme_viene_troncato_e_lo_dichiara(self):
        from core.harness.loop import MAX_CARATTERI_DIFF_RUN, _rivedi_lavoro_del_run

        class Enorme:
            branch_name = "b"
            def diff_stat_from_main(self): return "molti file\n"
            def changed_files(self): return ["f%d.py" % i for i in range(200)]
            def diff_from_main(self): return "+riga\n" * (MAX_CARATTERI_DIFF_RUN // 2)

        gate = review.ReviewGate(timeout_s=0.15)
        gen = _rivedi_lavoro_del_run(Enorme(), gate, "s5", True)
        proposta = next(gen)

        assert proposta["truncated"] is True
        assert len(proposta["diff"]) <= MAX_CARATTERI_DIFF_RUN
        # Lo `stat` e l'elenco dei file restano interi: sono la vista che si
        # legge davvero quando il diff non si legge.
        assert proposta["file_count"] == 200
        list(gen)

    def test_un_errore_nel_calcolo_non_blocca_la_chiusura(self):
        """La revisione e' una garanzia in piu', non un punto di rottura."""
        from core.harness.loop import _rivedi_lavoro_del_run

        class Rotto:
            branch_name = "b"
            def diff_stat_from_main(self): raise RuntimeError("git muto")
            def changed_files(self): return []
            def diff_from_main(self): return ""

        gate = review.ReviewGate(timeout_s=5.0)
        eventi = list(_rivedi_lavoro_del_run(Rotto(), gate, "s6", True))
        assert eventi == [{"type": "__decisione__", "apply": True}]


class TestIlCicloRispettaLaDecisione:
    def test_la_decisione_vince_sull_obiettivo_raggiunto(self, monkeypatch):
        """Un obiettivo raggiunto ma rifiutato non deve finire nell'albero vivo."""
        from core.harness import loop as modulo_loop

        visto = {}
        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False: visto.update(apply=apply_changes) or {},
        )
        modulo_loop._chiudi_run({
            "session_id": "s", "review_gate": None, "worktree": object(),
            "goal_reached": True, "apply_changes": False,
        })
        assert visto["apply"] is False

    def test_senza_revisione_vale_l_obiettivo_raggiunto(self, monkeypatch):
        from core.harness import loop as modulo_loop

        visto = {}
        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False: visto.update(apply=apply_changes) or {},
        )
        modulo_loop._chiudi_run({
            "session_id": "s", "review_gate": None, "worktree": object(),
            "goal_reached": True,
        })
        assert visto["apply"] is True


class TestRaggiungibilita:
    """Il difetto ricorrente: scritto, testato, scollegato."""

    def test_il_gestore_della_chat_passa_la_scelta(self):
        import inspect
        from core.modules.sigma_developer_lab import handlers

        sorgente = inspect.getsource(handlers.handle_agent_chat)
        assert 'body.get("review_run")' in sorgente
        assert "review_run=review_run" in sorgente

    def test_anche_i_ruoli_la_passano(self):
        import inspect
        from core.harness.roles import RoleEngine

        assert "review_run" in inspect.signature(RoleEngine.generate_with_role).parameters
        assert "review_run=review_run" in inspect.getsource(RoleEngine.generate_with_role)

    def test_chiederla_senza_isolamento_lo_dice_invece_di_fingere(self):
        import inspect
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "if review_run and session_wt is None:" in sorgente


class TestLeDueRevisioniNonSiConfondono:
    """Difetto trovato su una prova dal vivo: chiedendo la revisione di fine
    run si attivava anche il cancello per singola scrittura. Le due scritture
    sono scadute per timeout e sono state annullate, il run non ha prodotto
    niente, e alla fine non c'era piu' niente da rivedere — la revisione di
    fine run aveva cancellato il lavoro che doveva farti vedere."""

    def _run(self, tmp_path, monkeypatch, **opzioni):
        from core.harness import loop as modulo_loop

        risposte = [
            '```tool:write_file\n{"path": "nota.py", "content": "X = 1\n"}\n```',
            "Fatto.",
        ]
        stato = {"i": 0}

        def finto(**kw):
            i = min(stato["i"], len(risposte) - 1)
            stato["i"] += 1
            yield {"token": risposte[i]}

        monkeypatch.setattr(modulo_loop, "stream_dev_generation", finto)
        return list(modulo_loop.stream_admin_agent_turn(
            messages=[{"role": "user", "content": "scrivi nota.py"}],
            workspace_root=str(tmp_path), model_name="finto", max_turns=2,
            **opzioni,
        ))

    def test_la_revisione_di_fine_run_non_ferma_le_singole_scritture(
        self, tmp_path, monkeypatch
    ):
        eventi = self._run(
            tmp_path, monkeypatch,
            session_id="sess-solo-run", review_run=True,
        )
        try:
            assert not [e for e in eventi if e.get("type") == "write_proposed"], (
                "la revisione di fine run ha attivato il cancello per scrittura"
            )
            assert (tmp_path / "nota.py").read_text(encoding="utf-8") == "X = 1\n"
        finally:
            review.release_gate("sess-solo-run")

    def test_senza_isolamento_lo_dice_e_non_finge(self, tmp_path, monkeypatch):
        eventi = self._run(
            tmp_path, monkeypatch,
            session_id="sess-senza-wt", review_run=True,
        )
        try:
            avvisi = [e for e in eventi
                      if e.get("type") == "status" and "worktree" in str(e.get("text", ""))]
            assert avvisi, "un run senza worktree deve dire che la revisione non e' attiva"
        finally:
            review.release_gate("sess-senza-wt")
