"""Il lavoro su percorsi che git ignora non deve sparire con il worktree.

Un worktree porta soltanto cio' che e' versionato, e restituisce soltanto cio'
che finisce in un diff. Un file su un percorso **ignorato** non e' ne' l'uno ne'
l'altro: viene scritto nella cartella del run e sparisce con essa, senza che
nessuno lo dica.

Non e' un caso limite in questo progetto. `/sigma_studio/src/modules/*` e'
ignorato — i moduli vivono nel loro repository — quindi **ogni lavoro
sull'interfaccia fatto in isolamento veniva buttato**.

Misurato su un ventaglio vero: l'agente scrive `SandboxPanel.jsx`,
`ActivityBar.jsx` e `DeveloperStudio.jsx`, il ledger ne conta tre, il branch ne
contiene zero, e l'unico file sopravvissuto e' il test — che sta in `tests/`,
versionato. Il resoconto diceva «3 file toccati» e sul disco non ce n'era
nessuno: successo dichiarato, lavoro perduto.
"""

import subprocess

import pytest

from core.harness import worktree as W


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                          text=True, timeout=30)


@pytest.fixture
def repository(tmp_path):
    """Un repository vero, con una cartella ignorata come quella dei moduli."""
    radice = tmp_path / "progetto"
    radice.mkdir()
    _git(["init", "-q"], radice)
    _git(["config", "user.email", "prova@prova"], radice)
    _git(["config", "user.name", "Prova"], radice)
    (radice / ".gitignore").write_text("/moduli/*\n", encoding="utf-8")
    (radice / "app.py").write_text("VERSIONE = 1\n", encoding="utf-8")
    (radice / "moduli").mkdir()
    _git(["add", "-A"], radice)
    _git(["commit", "-q", "-m", "primo"], radice)
    return radice


class TestIlRecuperoDegliIgnorati:
    def test_un_file_ignorato_scritto_nel_worktree_torna_nell_albero(
            self, repository, monkeypatch, tmp_path):
        monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
        sessione = W.create_session_worktree(repository, "s_ignorati")
        assert sessione is not None

        # L'agente scrive un file versionato e uno ignorato.
        (sessione.worktree_path / "app.py").write_text("VERSIONE = 2\n",
                                                       encoding="utf-8")
        # La cartella non esiste nel worktree: git non porta le cartelle
        # vuote, e il contenuto e' ignorato. `write_file` la creerebbe.
        (sessione.worktree_path / "moduli").mkdir(exist_ok=True)
        (sessione.worktree_path / "moduli" / "Pannello.jsx").write_text(
            "export default function Pannello() { return null; }\n",
            encoding="utf-8")

        esito = W.release_session_worktree(
            "s_ignorati", apply_changes=True,
            percorsi_scritti=["app.py", "moduli/Pannello.jsx"])

        assert esito["applied"] is True
        assert (repository / "app.py").read_text(encoding="utf-8") == "VERSIONE = 2\n"
        recuperato = repository / "moduli" / "Pannello.jsx"
        assert recuperato.is_file(), (
            "il file ignorato e' sparito con il worktree: e' il difetto")
        assert "Pannello" in recuperato.read_text(encoding="utf-8")
        assert esito["ignored_recovered"] == ["moduli/Pannello.jsx"]

    def test_i_file_versionati_non_vengono_ricopiati(self, repository,
                                                     monkeypatch, tmp_path):
        """Passano gia' dal diff: ricopiarli sovrascriverebbe l'esito della
        revisione con la versione grezza del worktree."""
        monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
        sessione = W.create_session_worktree(repository, "s_versionati")
        (sessione.worktree_path / "app.py").write_text("VERSIONE = 3\n",
                                                       encoding="utf-8")
        esito = W.release_session_worktree("s_versionati", apply_changes=True,
                                           percorsi_scritti=["app.py"])
        assert esito["ignored_recovered"] == []

    def test_senza_approvazione_non_si_recupera_niente(self, repository,
                                                       monkeypatch, tmp_path):
        """Il lavoro non approvato resta sul branch, e cio' che git ignora
        resta dov'e': copiarlo lo farebbe entrare dalla finestra."""
        monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
        sessione = W.create_session_worktree(repository, "s_non_approvato")
        (sessione.worktree_path / "moduli").mkdir(exist_ok=True)
        (sessione.worktree_path / "moduli" / "Intruso.jsx").write_text(
            "x", encoding="utf-8")
        esito = W.release_session_worktree(
            "s_non_approvato", apply_changes=False,
            percorsi_scritti=["moduli/Intruso.jsx"])
        assert esito["ignored_recovered"] == []
        assert not (repository / "moduli" / "Intruso.jsx").exists()

    def test_un_percorso_che_esce_dal_worktree_viene_ignorato(
            self, repository, monkeypatch, tmp_path):
        """L'elenco viene dal ledger, ma resta un dato: un `..` dentro non
        deve poter scrivere fuori dal progetto."""
        monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
        W.create_session_worktree(repository, "s_fuga")
        esito = W.release_session_worktree(
            "s_fuga", apply_changes=True,
            percorsi_scritti=["../../fuori.txt", "moduli/../../fuori2.txt"])
        assert esito["ignored_recovered"] == []
        assert not (tmp_path / "fuori.txt").exists()

    def test_un_elenco_vuoto_non_rompe_niente(self, repository, monkeypatch,
                                              tmp_path):
        monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
        W.create_session_worktree(repository, "s_vuoto")
        esito = W.release_session_worktree("s_vuoto", apply_changes=True)
        assert esito["ignored_recovered"] == []


class TestIlCicloPassaLElenco:
    def test_la_chiusura_riceve_i_file_scritti(self):
        import inspect

        from core.harness.loop import _chiudi_run, _stream_agent_turn_impl

        ciclo = inspect.getsource(_stream_agent_turn_impl)
        assert '_chiusura["file_scritti"]' in ciclo

        chiusura = inspect.getsource(_chiudi_run)
        assert "percorsi_scritti=" in chiusura, (
            "senza l'elenco il recupero non ha su cosa lavorare")
