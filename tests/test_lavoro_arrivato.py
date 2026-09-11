"""Una voce e' fatta solo se il lavoro e' arrivato dove serve.

Su un ventaglio vero — otto voci, due lavoratori, trenta minuti — la coda ha
riportato «8 su 8, zero ferme». Andando a guardare, quattro di quelle otto non
avevano il proprio lavoro nell'albero: `backend/register.test.js` e
`backend/opere.test.js` non esistevano, il frontend non era quello nuovo. Il
codice stava su otto branch di sessione che nessuno avrebbe guardato.

Erano fallite le patch verso l'albero principale, per due motivi distinti:

1. **la contabilita' del sistema entrava in conflitto con se' stessa**:
   `.sigma_backups/backups_index.jsonl` — gli snapshot che l'harness crea da
   solo — finiva nel diff e faceva fallire l'applicazione con «already exists
   in working directory». Quattro volte su cinque;
2. **due lavoratori applicavano insieme**: il secondo trovava
   `backend/index.js` gia' cambiato dal primo.

E il difetto piu' grave non e' nessuno dei due: e' che il run chiudeva
l'obiettivo, la patch falliva **dopo**, e la voce veniva segnata fatta lo
stesso. Sesta volta in questo progetto che il sistema dichiara successo mentre
il lavoro resta indietro.
"""

import inspect
import subprocess

import pytest

from core.harness import fanout, worktree


class TestLaContabilitaNonEntraNellaPatch:
    def test_i_backup_dell_harness_sono_esclusi(self):
        assert any(".sigma_backups" in e for e in worktree.ESCLUSI_DAL_DIFF)

    def test_anche_node_modules_e_escluso(self):
        """Millequattrocento file di dipendenze in una patch non sono lavoro."""
        assert any("node_modules" in e for e in worktree.ESCLUSI_DAL_DIFF)

    def test_il_diff_del_run_applica_le_esclusioni(self):
        sorgente = inspect.getsource(worktree.WorktreeSession._diff)
        assert "ESCLUSI_DAL_DIFF" in sorgente

    def test_anche_il_trasferimento_le_applica(self):
        sorgente = inspect.getsource(worktree.WorktreeSession.apply_to_main)
        assert "ESCLUSI_DAL_DIFF" in sorgente


class TestUnTrasferimentoPerVolta:
    def test_il_rilascio_prende_il_lucchetto_del_repository(self):
        sorgente = inspect.getsource(worktree.release_session_worktree)
        assert "_lucchetto_repo(session.repo_root)" in sorgente

    def test_lo_stesso_repository_da_lo_stesso_lucchetto(self, tmp_path):
        from pathlib import Path
        a = worktree._lucchetto_repo(Path(tmp_path))
        b = worktree._lucchetto_repo(Path(tmp_path))
        assert a is b

    def test_repository_diversi_non_si_bloccano_a_vicenda(self, tmp_path):
        from pathlib import Path
        a = worktree._lucchetto_repo(Path(tmp_path) / "uno")
        b = worktree._lucchetto_repo(Path(tmp_path) / "due")
        assert a is not b


class TestUnaVoceNonApplicataNonEFatta:
    def _esegui(self, monkeypatch, eventi, coda_id):
        from core.harness import loop as modulo_loop
        from core.harness import workqueue

        def finto(messages, **kw):
            for e in eventi:
                yield e

        monkeypatch.setattr(modulo_loop, "stream_admin_agent_turn", finto)
        q = workqueue.get_queue(coda_id, goal="x")
        q.add_many(["una voce"])
        eventi_fanout = list(fanout.run_queue(coda_id, workspace_root=".",
                                              workers=1, deliver=False))
        finita = [e for e in eventi_fanout if e["type"] == "item_finished"][0]
        return q, finita

    @pytest.fixture(autouse=True)
    def coda_isolata(self, tmp_path, monkeypatch):
        from core.harness import workqueue
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
        workqueue._code.clear()
        yield
        workqueue._code.clear()

    def test_obiettivo_chiuso_ma_patch_fallita_non_e_una_voce_fatta(self, monkeypatch):
        """Il caso vero: cinque voci su otto segnate fatte a torto."""
        q, finita = self._esegui(monkeypatch, [
            {"type": "run_metrics", "turns": 12, "goal_reached": True},
            {"type": "apply_failed", "branch": "sigma-run/x", "checkpoints": 3},
        ], "c40")

        assert finita["ok"] is False
        assert "non e' arrivato nell'albero" in finita["error"]
        assert finita["branch"] == "sigma-run/x"
        assert q.progress()["done"] == 0

    def test_il_branch_dove_sta_il_lavoro_viene_detto(self, monkeypatch):
        """Un branch di cui nessuno conosce il nome e' perso quanto uno
        cancellato."""
        q, finita = self._esegui(monkeypatch, [
            {"type": "run_metrics", "turns": 5, "goal_reached": True},
            {"type": "apply_failed", "branch": "sigma-run/perduto", "checkpoints": 1},
        ], "c41")
        assert "sigma-run/perduto" in finita["error"]

    def test_una_voce_arrivata_davvero_resta_fatta(self, monkeypatch):
        q, finita = self._esegui(monkeypatch, [
            {"type": "run_metrics", "turns": 7, "goal_reached": True},
        ], "c42")
        assert finita["ok"] is True
        assert q.progress()["done"] == 1
