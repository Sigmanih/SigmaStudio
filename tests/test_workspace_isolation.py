"""Su quale progetto lavorano gli strumenti che il workspace non lo ricevono.

Nasce da un run vero dell'orchestratore, puntato su una cartella di prova.
I tool di filesystem hanno rispettato quella cartella; i tool git no: hanno
creato un branch **nel repository di Sigma Studio** e ci hanno fatto checkout,
mentre l'agente credeva di lavorare altrove.

La causa e' strutturale. I server MCP sono singleton condivisi, invocati con i
soli parametri che il modello scrive nella chiamata, e nessun modello scrive
«e comunque lavora in quell'altra cartella». Ogni comando git ripiegava quindi
sul workspace predefinito del server.

Non e' un fastidio: con `auto_approve` attivo la stessa sequenza sarebbe
arrivata a `git_commit` e `git_push` — modifiche committate e spinte sul
repository sbagliato, senza che nessuno avesse chiesto niente del genere.
"""

import pytest

from core.harness.workspace import (
    active_root,
    reset_active_root,
    resolve_root,
    set_active_root,
)


@pytest.fixture(autouse=True)
def radice_pulita():
    """Ogni test parte senza una radice dichiarata e non la lascia agli altri."""
    token = set_active_root("")
    yield
    reset_active_root(token)


class TestRadiceDelRun:
    def test_senza_dichiarazione_e_vuota(self):
        assert active_root() == ""

    def test_dichiararla_la_rende_visibile(self):
        token = set_active_root("C:/sandbox")
        try:
            assert active_root() == "C:/sandbox"
        finally:
            reset_active_root(token)

    def test_il_ripristino_la_toglie(self):
        token = set_active_root("C:/sandbox")
        reset_active_root(token)
        assert active_root() == ""

    def test_un_token_di_un_altro_contesto_non_fa_saltare_la_chiusura(self):
        """Un run puo' finire su un thread diverso da quello che l'ha aperto."""
        import contextvars

        altro = contextvars.copy_context()
        token = altro.run(lambda: set_active_root("C:/altrove"))
        reset_active_root(token)  # non deve sollevare


class TestRisoluzione:
    def test_una_radice_esplicita_vince_su_tutto(self):
        token = set_active_root("C:/del_run")
        try:
            assert resolve_root("D:/esplicita") == "D:/esplicita"
        finally:
            reset_active_root(token)

    def test_senza_esplicita_vale_quella_del_run(self):
        token = set_active_root("C:/del_run")
        try:
            assert resolve_root() == "C:/del_run"
            assert resolve_root("") == "C:/del_run"
            assert resolve_root(None) == "C:/del_run"
        finally:
            reset_active_root(token)

    def test_senza_niente_si_ricade_sul_predefinito(self):
        """Il comportamento storico, che resta giusto per la chat normale."""
        from core.harness.fs_manager import get_default_workspace_root
        assert resolve_root() == get_default_workspace_root()


class TestGitSegueIlRun:
    """Il difetto in una riga: git lavorava sempre sullo stesso repository."""

    def test_git_usa_la_radice_del_run(self, monkeypatch):
        from core.modules.sigma_developer_lab.mcp_tools import git_server

        visto = {}

        def finto(cmd, cwd=None, **kwargs):
            visto["cwd"] = cwd
            class Esito:
                returncode = 0
                stdout = ""
                stderr = ""
            return Esito()

        monkeypatch.setattr(git_server.subprocess, "run", finto)

        token = set_active_root("C:/sandbox")
        try:
            git_server._run_git(["status"])
        finally:
            reset_active_root(token)

        assert visto["cwd"] == "C:/sandbox"

    def test_senza_run_git_usa_il_predefinito(self, monkeypatch):
        from core.harness.fs_manager import get_default_workspace_root
        from core.modules.sigma_developer_lab.mcp_tools import git_server

        visto = {}

        def finto(cmd, cwd=None, **kwargs):
            visto["cwd"] = cwd
            class Esito:
                returncode = 0
                stdout = ""
                stderr = ""
            return Esito()

        monkeypatch.setattr(git_server.subprocess, "run", finto)
        git_server._run_git(["status"])
        assert visto["cwd"] == get_default_workspace_root()

    def test_una_radice_esplicita_resta_prioritaria(self, monkeypatch):
        from core.modules.sigma_developer_lab.mcp_tools import git_server

        visto = {}

        def finto(cmd, cwd=None, **kwargs):
            visto["cwd"] = cwd
            class Esito:
                returncode = 0
                stdout = ""
                stderr = ""
            return Esito()

        monkeypatch.setattr(git_server.subprocess, "run", finto)

        token = set_active_root("C:/sandbox")
        try:
            git_server._run_git(["status"], cwd="D:/preciso")
        finally:
            reset_active_root(token)

        assert visto["cwd"] == "D:/preciso"


class TestIlCicloDichiaraLaRadice:
    def test_il_ciclo_apre_e_chiude_la_dichiarazione(self):
        """Se il ciclo smettesse di dichiararla, git tornerebbe a sbagliare repository.

        Apertura e chiusura stanno in due funzioni diverse da quando la
        chiusura vale anche per i run abbandonati: il ciclo dichiara la radice,
        `_chiudi_run` la ripristina qualunque cosa succeda.
        """
        import inspect
        from core.harness.loop import _chiudi_run, _stream_agent_turn_impl

        assert "set_active_root(workspace_root)" in inspect.getsource(_stream_agent_turn_impl)
        assert "reset_active_root(" in inspect.getsource(_chiudi_run)
