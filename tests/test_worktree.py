# ==============================================================================
# tests/test_worktree.py — Test per l'isolamento tramite Git Worktree
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Test dell'isolamento con git worktree, checkpoint di turno e rollback."""

import subprocess
from pathlib import Path

import pytest

from core.harness import worktree
from core.harness.worktree import (
    WorktreeSession,
    create_session_worktree,
    get_session_worktree,
    is_git_repository,
    release_session_worktree,
)


@pytest.fixture
def repo_temporaneo(tmp_path):
    """Crea un repository Git reale in una cartella temporanea."""
    repo = tmp_path / "repo_test"
    repo.mkdir()

    # Inizializza git con configurazione utente locale al test
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "agent@sigma.test"], cwd=str(repo), check=True)

    # Crea un file iniziale e il commit root
    readme = repo / "README.md"
    readme.write_text("# Repo di Prova\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(repo), check=True)

    return repo


class TestRilevamentoGit:
    def test_cartella_normale_non_e_repo(self, tmp_path):
        assert not is_git_repository(tmp_path)

    def test_repo_git_valido(self, repo_temporaneo):
        assert is_git_repository(repo_temporaneo)


class TestCicloDiVitaWorktree:
    def test_creazione_checkpoint_e_rollback(self, repo_temporaneo, monkeypatch, tmp_path):
        # Redirigi la cartella dei worktree sul percorso di test
        var_mock = tmp_path / "var"
        monkeypatch.setattr("core.paths.var_dir", lambda: var_mock)

        session_id = "test_run_123"
        session = create_session_worktree(repo_temporaneo, session_id)
        assert session is not None
        assert session.worktree_path.is_dir()
        assert (session.worktree_path / "README.md").exists()

        # Turno 1: l'agente scrive un nuovo file
        file_uno = session.worktree_path / "modulo_uno.py"
        file_uno.write_text("X = 1\n", encoding="utf-8")

        c1 = session.checkpoint(1, "creato modulo_uno")
        assert c1 is not None
        assert len(session.checkpoints) == 1

        # Il file NON deve esistere nel repository principale
        assert not (repo_temporaneo / "modulo_uno.py").exists()

        # Turno 2: l'agente scrive un secondo file errato
        file_due = session.worktree_path / "modulo_errato.py"
        file_due.write_text("Y = rotto\n", encoding="utf-8")

        c2 = session.checkpoint(2, "creato modulo errato")
        assert c2 is not None
        assert len(session.checkpoints) == 2
        assert file_due.exists()

        # Rollback del turno 2: il file errato deve sparire istantaneamente!
        ok = session.rollback(1)
        assert ok is True
        assert not file_due.exists()
        # Il file del turno 1 deve restare intatto
        assert file_uno.exists()
        assert len(session.checkpoints) == 1

        # Rilascio senza applicare: la cartella sparisce, il lavoro no.
        esito = release_session_worktree(session_id, apply_changes=False)
        assert esito["released"] is True
        assert esito["applied"] is False
        assert not session.worktree_path.exists()
        # Il branch resta, perche' c'era del lavoro vero da conservare.
        assert esito["branch"] == session.branch_name
        assert esito["checkpoints"] == 1

    def test_applicazione_modifiche_validate_a_main(self, repo_temporaneo, monkeypatch, tmp_path):
        var_mock = tmp_path / "var"
        monkeypatch.setattr("core.paths.var_dir", lambda: var_mock)

        session_id = "test_apply_456"
        session = create_session_worktree(repo_temporaneo, session_id)
        assert session is not None

        # Modifica un file e creane uno nuovo
        (session.worktree_path / "nuovo.py").write_text("VAL = 42\n", encoding="utf-8")
        session.checkpoint(1, "nuovo file validato")

        # Rilascia con apply_changes=True
        esito = release_session_worktree(session_id, apply_changes=True)
        assert esito["applied"] is True
        # Il lavoro e' sull'albero principale: il branch non serve piu'.
        assert esito["branch"] == ""

        # Ora il file deve esistere nel repository principale
        assert (repo_temporaneo / "nuovo.py").exists()
        assert (repo_temporaneo / "nuovo.py").read_text(encoding="utf-8") == "VAL = 42\n"
