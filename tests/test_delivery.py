"""Il lavoro dell'agente arriva su `dev` e si accetta con una pull request.

Prima il lavoro approvato finiva nell'albero di lavoro. Era meglio che scrivere
di nascosto, ma la revisione restava una cosa sola, subito, davanti a un diff:
chi vuole guardare con calma — o due giorni dopo, o farlo guardare a un altro —
non aveva dove.

Qui il lavoro prende la strada normale del software: branch di integrazione,
richiesta, accettazione. Le proprieta' che i test tengono ferme:

1. **l'albero di lavoro dell'utente non viene toccato**, mai, nemmeno per un
   checkout — e' gia' successo in questo progetto che un comando git agisse sul
   repository sbagliato mentre qualcuno ci stava lavorando;
2. **il lavoro non si perde se la consegna fallisce**: resta sul branch del run;
3. **non si apre una richiesta verso un branch che non esiste**: si guarda come
   il repository chiama davvero il proprio principale.

Nessun test parla con la rete: i remoti sono repository bare locali.
"""

import subprocess
from pathlib import Path

import pytest

from core.harness import delivery


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


@pytest.fixture
def progetto(tmp_path, monkeypatch):
    """Un repository con un remoto bare, come un progetto vero."""
    monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
    monkeypatch.setattr(delivery.paths, "config_dir", lambda: tmp_path / "config")
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)

    bare = tmp_path / "origine.git"
    _git(["init", "--bare", "-b", "main", str(bare)], tmp_path)

    repo = tmp_path / "progetto"
    _git(["clone", str(bare), str(repo)], tmp_path)
    for a in (["config", "user.email", "t@s.local"], ["config", "user.name", "T"],
              ["config", "commit.gpgsign", "false"]):
        _git(a, repo)
    (repo / "app.py").write_text("TITOLO = 'Ciao'\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "iniziale"], repo)
    _git(["push", "origin", "main"], repo)
    return repo


def _branch_di_lavoro(repo, nome="sigma-run/test", file=None):
    """Simula il branch prodotto da un run, senza toccare l'albero corrente."""
    from core.harness import worktree

    sessione = worktree.create_session_worktree(repo, nome.split("/")[-1])
    assert sessione is not None
    for percorso, contenuto in (file or {"locales/it.json": '{"titolo": "Ciao"}\n'}).items():
        f = sessione.worktree_path / percorso
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(contenuto, encoding="utf-8")
    sessione.checkpoint(1, "lavoro del run")
    return sessione


class TestScopertaDelBranchPrincipale:
    """Chiedere «verso master» a un repository che ha solo `main` produrrebbe
    una richiesta verso un branch inesistente."""

    def test_usa_quello_che_esiste_davvero(self, progetto):
        assert delivery.scopri_branch_principale(progetto) == "main"

    def test_una_preferenza_inesistente_non_viene_imposta(self, progetto):
        assert delivery.scopri_branch_principale(progetto, "master") == "main"

    def test_una_preferenza_valida_viene_rispettata(self, progetto):
        _git(["branch", "stable"], progetto)
        _git(["push", "origin", "stable"], progetto)
        assert delivery.scopri_branch_principale(progetto, "stable") == "stable"


class TestConsegna:
    def test_il_lavoro_arriva_su_dev(self, progetto, tmp_path):
        sessione = _branch_di_lavoro(progetto)

        esito = delivery.deliver_branch(
            progetto, sessione.branch_name, obiettivo="aggiungi le lingue",
            file=["locales/it.json"],
        )

        assert esito.delivered is True, esito.error
        assert esito.pushed is True
        assert esito.base == "main"

        verifica = tmp_path / "verifica"
        _git(["clone", "--branch", "dev", str(tmp_path / "origine.git"), str(verifica)], tmp_path)
        assert (verifica / "locales" / "it.json").is_file()

    def test_il_principale_resta_intatto(self, progetto, tmp_path):
        """La richiesta serve proprio a non far arrivare niente da solo."""
        sessione = _branch_di_lavoro(progetto)
        delivery.deliver_branch(progetto, sessione.branch_name, file=["locales/it.json"])

        verifica = tmp_path / "verifica_main"
        _git(["clone", "--branch", "main", str(tmp_path / "origine.git"), str(verifica)], tmp_path)
        assert not (verifica / "locales").exists()

    def test_l_albero_di_lavoro_dell_utente_non_viene_toccato(self, progetto):
        """Un `git checkout dev` nel repository vivo cambierebbe i file sotto le
        mani di chi ci sta lavorando. E' gia' successo in questo progetto."""
        (progetto / "in_corso.py").write_text("STO_LAVORANDO = True\n", encoding="utf-8")
        branch_prima = _git(["rev-parse", "--abbrev-ref", "HEAD"], progetto).stdout.strip()

        sessione = _branch_di_lavoro(progetto)
        delivery.deliver_branch(progetto, sessione.branch_name, file=["locales/it.json"])

        assert _git(["rev-parse", "--abbrev-ref", "HEAD"], progetto).stdout.strip() == branch_prima
        assert (progetto / "in_corso.py").read_text(encoding="utf-8") == "STO_LAVORANDO = True\n"
        # E il lavoro dell'agente non e' comparso qui.
        assert not (progetto / "locales").exists()

    def test_l_indirizzo_per_aprire_la_richiesta_viene_sempre_dato(self, progetto):
        """Anche senza `gh` e senza token: spingere il branch e dire dove
        cliccare e' una consegna riuscita, non un fallimento."""
        sessione = _branch_di_lavoro(progetto)
        esito = delivery.deliver_branch(progetto, sessione.branch_name)
        assert esito.delivered is True
        # Il remoto qui e' una cartella, non GitHub: l'indirizzo non c'e', ma
        # la consegna e' comunque avvenuta.
        assert esito.compare_url == ""

    def test_due_consegne_di_fila_aggiornano_lo_stesso_dev(self, progetto, tmp_path):
        prima = _branch_di_lavoro(progetto, "sigma-run/uno", {"a.py": "A = 1\n"})
        assert delivery.deliver_branch(progetto, prima.branch_name).delivered is True

        seconda = _branch_di_lavoro(progetto, "sigma-run/due", {"b.py": "B = 2\n"})
        assert delivery.deliver_branch(progetto, seconda.branch_name).delivered is True

        verifica = tmp_path / "verifica_due"
        _git(["clone", "--branch", "dev", str(tmp_path / "origine.git"), str(verifica)], tmp_path)
        assert (verifica / "a.py").is_file()
        assert (verifica / "b.py").is_file()


class TestQuandoLaConsegnaNonRiesce:
    """Il lavoro non si perde mai per un errore di consegna."""

    def test_un_conflitto_lascia_il_lavoro_sul_branch_del_run(self, progetto, tmp_path):
        # Qualcuno ha gia' scritto lo stesso file su dev.
        primo = _branch_di_lavoro(progetto, "sigma-run/primo", {"conteso.py": "VERSIONE = 'a'\n"})
        assert delivery.deliver_branch(progetto, primo.branch_name).delivered is True

        secondo = _branch_di_lavoro(progetto, "sigma-run/secondo", {"conteso.py": "VERSIONE = 'b'\n"})
        esito = delivery.deliver_branch(progetto, secondo.branch_name)

        assert esito.delivered is False
        assert "conflitti" in esito.error or "innesta" in esito.error
        assert secondo.branch_name in esito.error
        # Il lavoro e' ancora leggibile dove l'agente lo ha lasciato.
        letto = _git(["show", f"{secondo.branch_name}:conteso.py"], progetto).stdout
        assert "VERSIONE = 'b'" in letto

    def test_senza_remoto_lo_dice_invece_di_fingere(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")
        monkeypatch.setattr(delivery.paths, "config_dir", lambda: tmp_path / "config")

        repo = tmp_path / "senza_remoto"
        repo.mkdir()
        for a in (["init", "-b", "main"], ["config", "user.email", "t@s"],
                  ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
            _git(a, repo)
        (repo / "x.py").write_text("X = 1\n", encoding="utf-8")
        _git(["add", "-A"], repo)
        _git(["commit", "-m", "i"], repo)

        sessione = _branch_di_lavoro(repo, "sigma-run/orfano", {"y.py": "Y = 1\n"})
        esito = delivery.deliver_branch(repo, sessione.branch_name)

        assert esito.delivered is False
        assert esito.error


class TestIndirizziGitHub:
    def test_riconosce_il_progetto_da_un_indirizzo_https(self):
        assert delivery._slug_github("https://github.com/Sigmanih/SigmaStudio.git") == "Sigmanih/SigmaStudio"

    def test_riconosce_il_progetto_da_un_indirizzo_ssh(self):
        assert delivery._slug_github("git@github.com:Sigmanih/SigmaStudio.git") == "Sigmanih/SigmaStudio"

    def test_un_remoto_non_github_non_produce_indirizzi_inventati(self):
        assert delivery._slug_github("/percorso/locale/repo.git") == ""
        assert delivery.compare_url("/percorso/locale", "main", "dev") == ""

    def test_l_indirizzo_di_confronto_punta_al_posto_giusto(self):
        atteso = "https://github.com/Sigmanih/SigmaStudio/compare/main...dev?expand=1"
        assert delivery.compare_url(
            "https://github.com/Sigmanih/SigmaStudio.git", "main", "dev") == atteso


class TestConfigurazione:
    def test_di_default_si_consegna_con_una_richiesta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(delivery.paths, "config_dir", lambda: tmp_path / "config")
        assert delivery.in_pull_request_mode() is True

    def test_si_puo_tornare_al_comportamento_locale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(delivery.paths, "config_dir", lambda: tmp_path / "config")
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        delivery.save_config({"mode": "local"})
        assert delivery.in_pull_request_mode() is False


class TestIlCicloConsegna:
    """Il difetto ricorrente: scritto, testato, scollegato."""

    def test_il_ciclo_chiama_la_consegna(self):
        import inspect
        from core.harness.loop import _stream_agent_turn_impl

        sorgente = inspect.getsource(_stream_agent_turn_impl)
        assert "delivery.in_pull_request_mode()" in sorgente
        assert "_consegna_il_lavoro(" in sorgente

    def test_una_consegna_riuscita_non_applica_anche_all_albero(self, monkeypatch):
        """Sarebbe il lavoro in due posti, e uno dei due nessuno lo ha accettato."""
        from core.harness import loop as modulo_loop

        class Sessione:
            branch_name = "sigma-run/x"
            checkpoints = []
            def changed_files(self): return ["a.py"]
            def checkpoint(self, *a, **k): return "abc"

        monkeypatch.setattr(
            modulo_loop.delivery, "deliver_branch",
            lambda *a, **k: delivery.Consegna(delivered=True, branch="dev", pushed=True),
        )
        class Ledger:
            goal = "obiettivo"

        eventi = list(modulo_loop._consegna_il_lavoro(Sessione(), ".", Ledger()))
        assert eventi[0]["type"] == "run_delivered"
        assert eventi[-1] == {"type": "__consegnato__", "ok": True}

    def test_una_consegna_fallita_lascia_applicare_all_albero(self, monkeypatch):
        """Altrimenti il lavoro non finirebbe in nessuno dei due posti."""
        from core.harness import loop as modulo_loop

        class Sessione:
            branch_name = "sigma-run/x"
            checkpoints = []
            def changed_files(self): return ["a.py"]
            def checkpoint(self, *a, **k): return "abc"

        monkeypatch.setattr(
            modulo_loop.delivery, "deliver_branch",
            lambda *a, **k: delivery.Consegna(delivered=False, error="rete assente"),
        )
        class Ledger:
            goal = "obiettivo"

        eventi = list(modulo_loop._consegna_il_lavoro(Sessione(), ".", Ledger()))
        assert eventi[0]["type"] == "delivery_failed"
        assert eventi[-1] == {"type": "__consegnato__", "ok": False}

    def test_un_run_senza_modifiche_non_consegna_niente(self):
        from core.harness import loop as modulo_loop

        class Vuota:
            branch_name = "b"
            checkpoints = []
            def changed_files(self): return []

        class Ledger:
            goal = "x"

        eventi = list(modulo_loop._consegna_il_lavoro(Vuota(), ".", Ledger()))
        assert eventi == [{"type": "__consegnato__", "ok": False}]
