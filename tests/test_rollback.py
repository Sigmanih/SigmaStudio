"""Tornare indietro di N turni, quando a deciderlo e' una persona.

`rollback()` esisteva dal primo giorno e non la chiamava nessuno. Il modulo
prometteva che «se l'agente va in stallo, un rollback ripristina» — una promessa
che nessun codice manteneva.

Automatico sarebbe comunque sbagliato: uno stallo del modello non dice che il
codice scritto fino a quel punto sia sbagliato, e annullarlo d'ufficio
butterebbe via lavoro buono. Chi torna indietro deve essere qualcuno che ha
guardato — quindi serviva un comando, non un'euristica.
"""

import subprocess

import pytest

from core.harness import worktree


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "progetto"
    r.mkdir()
    for a in (["init"], ["config", "user.email", "t@s"], ["config", "user.name", "T"],
              ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git"] + a, cwd=str(r), capture_output=True)
    (r / "base.py").write_text("BASE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(r), capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=str(r), capture_output=True)
    return r


@pytest.fixture
def sessione(repo, tmp_path, monkeypatch):
    monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
    s = worktree.create_session_worktree(repo, "sess-rollback")
    assert s is not None
    yield s
    worktree.release_session_worktree("sess-rollback")


def _turno(sessione, nome, contenuto, numero):
    (sessione.worktree_path / nome).write_text(contenuto, encoding="utf-8")
    sessione.checkpoint(numero)


class TestIPuntiACuiTornare:
    def test_si_elencano_solo_i_turni_che_hanno_cambiato_qualcosa(self, sessione):
        """I checkpoint di turno si fanno con `--allow-empty`: offrire di
        tornare a un turno in cui non era cambiato nulla sarebbe offrire di non
        fare niente."""
        _turno(sessione, "uno.py", "A = 1\n", 1)
        sessione.checkpoint(2)          # turno a vuoto
        _turno(sessione, "due.py", "B = 2\n", 3)

        punti = worktree.session_checkpoints("sess-rollback")
        assert [p["turn"] for p in punti] == [1, 3]

    def test_una_sessione_che_non_esiste_non_ha_punti(self):
        assert worktree.session_checkpoints("mai-esistita") == []


class TestTornareIndietro:
    def test_annulla_l_ultimo_turno_e_lascia_il_resto(self, sessione):
        _turno(sessione, "buono.py", "A = 1\n", 1)
        _turno(sessione, "sbagliato.py", "B = 2\n", 2)

        esito = worktree.rollback_session("sess-rollback", 1)

        assert esito["success"] is True
        assert not (sessione.worktree_path / "sbagliato.py").exists()
        assert (sessione.worktree_path / "buono.py").exists()

    def test_dice_cosa_resta_dopo(self, sessione):
        """Chi torna indietro deve vedere dov'e' finito, non fidarsi."""
        _turno(sessione, "buono.py", "A = 1\n", 1)
        _turno(sessione, "sbagliato.py", "B = 2\n", 2)

        esito = worktree.rollback_session("sess-rollback", 1)

        assert esito["files"] == ["buono.py"]
        assert [p["turn"] for p in esito["checkpoints"]] == [1]

    def test_si_puo_tornare_indietro_di_piu_turni(self, sessione):
        for i, nome in enumerate(("a.py", "b.py", "c.py"), start=1):
            _turno(sessione, nome, f"X = {i}\n", i)

        worktree.rollback_session("sess-rollback", 2)

        assert (sessione.worktree_path / "a.py").exists()
        assert not (sessione.worktree_path / "b.py").exists()
        assert not (sessione.worktree_path / "c.py").exists()

    def test_non_si_puo_annullare_tutto_il_run_di_nascosto(self, sessione):
        """Annullare tutto e' una cosa diversa, e va chiesta diversamente:
        rifiutando il lavoro alla revisione di fine run."""
        _turno(sessione, "uno.py", "A = 1\n", 1)

        esito = worktree.rollback_session("sess-rollback", 5)

        assert esito["success"] is False
        assert "revisione di fine run" in esito["error"]
        assert (sessione.worktree_path / "uno.py").exists()

    def test_senza_run_isolato_non_c_e_niente_da_annullare(self):
        esito = worktree.rollback_session("sessione-inventata")
        assert esito["success"] is False
        assert "Nessun run isolato" in esito["error"]

    def test_il_repository_vero_non_viene_toccato(self, sessione, repo):
        """Il rollback vive dentro il worktree del run: l'albero dell'utente
        non c'entra."""
        _turno(sessione, "uno.py", "A = 1\n", 1)
        _turno(sessione, "due.py", "B = 2\n", 2)

        worktree.rollback_session("sess-rollback", 1)

        assert not (repo / "uno.py").exists()
        assert (repo / "base.py").read_text(encoding="utf-8") == "BASE = 1\n"


class TestRaggiungibilita:
    """Il difetto che questo file chiude: la funzione c'era e non la chiamava
    nessuno."""

    def test_esistono_le_rotte_per_elencare_e_tornare_indietro(self):
        from core.modules.sigma_developer_lab.handlers import ROUTES

        percorsi = {(p, tuple(m)) for p, _, m in ROUTES}
        assert ("/api/developer/run/checkpoints", ("GET",)) in percorsi
        assert ("/api/developer/run/rollback", ("POST",)) in percorsi

    def test_la_rotta_usa_davvero_il_rollback(self):
        import inspect
        from core.modules.sigma_developer_lab import handlers

        sorgente = inspect.getsource(handlers.handle_run_rollback)
        assert "rollback_session" in sorgente

    def test_nessuno_lo_invoca_da_solo(self):
        """Automatico sarebbe sbagliato: uno stallo del modello non dice che il
        codice scritto fino a quel punto sia sbagliato."""
        import inspect
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "rollback" not in sorgente
