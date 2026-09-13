"""Due lavoratori sullo stesso file non devono perdere il lavoro.

La patch di un run e' calcolata dal commit da cui e' partito. `git apply` e'
tutto-o-niente sul contenuto esatto: se nel frattempo un altro lavoratore ha
gia' trasferito il suo lavoro sullo stesso file, basta una riga diversa altrove
perche' l'intera patch venga rifiutata.

Misurato su un ventaglio vero: **quattro voci su otto** morte con «obiettivo
chiuso ma il lavoro non e' arrivato nell'albero» — e gli stessi diff si
applicavano benissimo uno per uno. Il lavoro c'era, era buono, ed e' rimasto su
branch che nessuno avrebbe guardato.

La fusione a tre vie risolve il caso normale (due parti diverse dello stesso
file) e rifiuta quello vero (la stessa riga cambiata da entrambi), che e' una
decisione per una persona.
"""

import subprocess

import pytest

from core.harness import worktree as W


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                          text=True, timeout=30)


PARTENZA = """def uno():
    return 1


def due():
    return 2


def tre():
    return 3
"""


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setattr(W.paths, "var_dir", lambda: tmp_path / "var")
    radice = tmp_path / "progetto"
    radice.mkdir()
    _git(["init", "-q"], radice)
    _git(["config", "user.email", "p@p"], radice)
    _git(["config", "user.name", "P"], radice)
    (radice / "modulo.py").write_text(PARTENZA, encoding="utf-8")
    _git(["add", "-A"], radice)
    _git(["commit", "-q", "-m", "primo"], radice)
    return radice


class TestLaFusioneSalvaIlLavoroDelSecondo:
    def test_due_modifiche_in_punti_diversi_si_fondono(self, repository):
        """E' il caso normale del ventaglio, e quello che si perdeva."""
        sessione = W.create_session_worktree(repository, "s_fusione")
        assert sessione is not None

        # Il run cambia la funzione in fondo.
        (sessione.worktree_path / "modulo.py").write_text(
            PARTENZA.replace("return 3", "return 33"), encoding="utf-8")

        # Nel frattempo qualcun altro ha cambiato quella in cima: e' cio' che
        # fa rifiutare la patch calcolata dal commit di partenza.
        (repository / "modulo.py").write_text(
            PARTENZA.replace("return 1", "return 11"), encoding="utf-8")

        assert W.release_session_worktree("s_fusione", apply_changes=True)["applied"] is True

        finale = (repository / "modulo.py").read_text(encoding="utf-8")
        assert "return 11" in finale, "il lavoro dell'altro non va perso"
        assert "return 33" in finale, "e nemmeno quello del run"
        assert "<<<<<<<" not in finale

    def test_la_stessa_riga_cambiata_da_entrambi_viene_rifiutata(self, repository):
        """Un conflitto vero e' una decisione per una persona. Il lavoro resta
        sul branch e si recupera; un file con i marcatori dentro non compila e
        nessuno sa perche'."""
        sessione = W.create_session_worktree(repository, "s_conflitto")
        (sessione.worktree_path / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 222"), encoding="utf-8")
        (repository / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 999"), encoding="utf-8")

        esito = W.release_session_worktree("s_conflitto", apply_changes=True)

        assert esito["applied"] is False
        assert esito["branch"], "il lavoro rifiutato deve restare raggiungibile"
        finale = (repository / "modulo.py").read_text(encoding="utf-8")
        assert "<<<<<<<" not in finale, "mai marcatori nell'albero di lavoro"
        assert "return 999" in finale, "l'albero resta com'era"

    def test_niente_viene_scritto_se_anche_un_solo_file_confligge(self, repository):
        """Tutto o niente: meta' trasferimento e' lo stato peggiore di tutti,
        perche' sembra riuscito e non lo e'."""
        (repository / "altro.py").write_text("VALORE = 1\n", encoding="utf-8")
        _git(["add", "-A"], repository)
        _git(["commit", "-q", "-m", "secondo"], repository)

        sessione = W.create_session_worktree(repository, "s_parziale")
        (sessione.worktree_path / "altro.py").write_text("VALORE = 2\n",
                                                         encoding="utf-8")
        (sessione.worktree_path / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 222"), encoding="utf-8")

        # Conflitto vero solo su modulo.py.
        (repository / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 999"), encoding="utf-8")

        esito = W.release_session_worktree("s_parziale", apply_changes=True)
        assert esito["applied"] is False
        assert (repository / "altro.py").read_text(encoding="utf-8") == "VALORE = 1\n", (
            "il file che si sarebbe fuso non deve essere scritto da solo")

    def test_un_file_nuovo_arriva_lo_stesso(self, repository):
        sessione = W.create_session_worktree(repository, "s_nuovo")
        (sessione.worktree_path / "nuovo.py").write_text("NUOVO = 1\n",
                                                         encoding="utf-8")
        (repository / "modulo.py").write_text(
            PARTENZA.replace("return 1", "return 11"), encoding="utf-8")
        esito = W.release_session_worktree("s_nuovo", apply_changes=True)
        assert esito["applied"] is True
        assert (repository / "nuovo.py").is_file()

    def test_la_via_veloce_resta_quella_di_prima(self, repository):
        """Senza nessuno che abbia toccato niente, si applica la patch e
        basta: la fusione costa un processo per file e non serve."""
        sessione = W.create_session_worktree(repository, "s_veloce")
        (sessione.worktree_path / "modulo.py").write_text(
            PARTENZA.replace("return 3", "return 33"), encoding="utf-8")
        esito = W.release_session_worktree("s_veloce", apply_changes=True)
        assert esito["applied"] is True
        assert "return 33" in (repository / "modulo.py").read_text(encoding="utf-8")


class TestLoStrumentoDiFusione:
    def test_due_cambiamenti_lontani_si_uniscono(self):
        fuso, pulito = W._fondi_tre_testi(
            PARTENZA.replace("return 1", "return 11"),
            PARTENZA,
            PARTENZA.replace("return 3", "return 33"))
        assert pulito is True
        assert "return 11" in fuso and "return 33" in fuso

    def test_lo_stesso_punto_da_entrambi_non_e_pulito(self):
        _, pulito = W._fondi_tre_testi(
            PARTENZA.replace("return 2", "return 999"),
            PARTENZA,
            PARTENZA.replace("return 2", "return 222"))
        assert pulito is False

    def test_nessuna_modifica_da_una_parte_prende_l_altra(self):
        fuso, pulito = W._fondi_tre_testi(
            PARTENZA, PARTENZA, PARTENZA.replace("return 3", "return 33"))
        assert pulito is True
        assert "return 33" in fuso


class TestIlBranchNonSiButtaMaiConDentroIlLavoro:
    """`has_work()` guarda i commit, e l'ultimo turno puo' aver scritto dopo
    l'ultimo checkpoint. Chiedendolo prima del checkpoint di chiusura, un run
    che ha prodotto tutto nell'ultimo turno risultava vuoto — e se il
    trasferimento falliva, il branch veniva buttato con dentro l'unica copia
    del lavoro."""

    def test_un_run_che_scrive_solo_alla_fine_conserva_il_branch(self, repository):
        sessione = W.create_session_worktree(repository, "s_ultimo_turno")
        # Nessun checkpoint di turno: tutto il lavoro arriva adesso.
        (sessione.worktree_path / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 222"), encoding="utf-8")
        # E un conflitto vero, cosi' il trasferimento non riesce.
        (repository / "modulo.py").write_text(
            PARTENZA.replace("return 2", "return 999"), encoding="utf-8")

        esito = W.release_session_worktree("s_ultimo_turno", apply_changes=True)
        assert esito["applied"] is False
        assert esito["branch"], (
            "il branch e' l'unica copia rimasta: buttarlo perde tutto")

    def test_un_run_davvero_vuoto_non_lascia_un_branch(self, repository):
        """Un branch per ogni run a vuoto sarebbe rumore in `git branch`."""
        W.create_session_worktree(repository, "s_niente")
        esito = W.release_session_worktree("s_niente", apply_changes=False)
        assert esito["branch"] == ""
