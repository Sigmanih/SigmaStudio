"""Cio' che un run apre viene chiuso, e cio' che produce non viene buttato via.

Tre difetti veri, trovati rileggendo l'integrazione del worktree nel ciclo
dell'agente. Nessuno dei tre era visibile dai test del modulo, perche' tutti
e tre stanno nel punto in cui il modulo incontra il ciclo:

1. **Il worktree non era raggiungibile.** `isolate_worktree` era dichiarato
   nella firma del ciclo e nessuno lo passava: l'intero isolamento — copia
   fisica del repository, checkpoint di turno, rollback — non poteva essere
   acceso da nessun percorso di produzione.

2. **Un run interrotto lasciava tutto aperto.** La chiusura stava dopo il
   ciclo, e un generatore abbandonato non esegue le proprie ultime righe.
   Premere stop lasciava sul disco un worktree git e un branch per ogni run.

3. **Un run che non chiudeva l'obiettivo veniva cancellato.** `git branch -D`
   su tutto il lavoro, ogni volta che `goal_reached` era falso. Poiche' il
   cancello di completamento e' severo per costruzione, quello e' l'esito
   ordinario: trenta turni di lavoro buono sparivano per l'ultimo passo
   mancante.
"""

import inspect

import pytest

from core.harness import worktree


# ---------------------------------------------------------------------------
# 1. Raggiungibilita'
# ---------------------------------------------------------------------------


class TestLIsolamentoEAccendibile:
    """Una funzionalita' che nessun chiamante puo' accendere non esiste."""

    def test_il_gestore_della_chat_passa_la_scelta_al_ciclo(self):
        from core.modules.sigma_developer_lab import handlers

        sorgente = inspect.getsource(handlers.handle_agent_chat)
        assert 'body.get("isolate_worktree")' in sorgente, (
            "il gestore non legge la scelta dalla richiesta"
        )
        assert "isolate_worktree=isolate_worktree" in sorgente, (
            "la scelta non arriva al ciclo dell'agente"
        )

    def test_la_squadra_si_isola_una_volta_sola_per_tutto_l_obiettivo(self):
        """L'orchestratore e' l'unico posto dove cinque ruoli lavorano di fila
        senza che nessuno guardi: escluderlo sarebbe stato il contrario. Ma
        l'unita' dell'isolamento e' **l'obiettivo**, non il ruolo.

        Un worktree per ruolo darebbe cinque alberi che non si vedono fra loro:
        il Tester non troverebbe i file che il Coder ha appena scritto, e la
        squadra smetterebbe di essere una squadra. Si apre un albero solo, e
        tutti e cinque ci lavorano dentro perche' ereditano `workspace_root`.
        """
        from core.harness.roles import RoleEngine
        from core.modules.sigma_developer_lab.orchestrator import DevOrchestrator

        parametri = inspect.signature(RoleEngine.generate_with_role).parameters
        assert "review_writes" in parametri, "questa e' per scrittura: resta"
        assert "verify_command" in parametri, "questa e' per task: resta"
        assert "isolate_worktree" not in parametri, (
            "un ruolo non ha un albero suo da isolare")

        apertura = inspect.getsource(DevOrchestrator.execute_goal)
        assert "isolate_worktree" in inspect.signature(
            DevOrchestrator.execute_goal).parameters
        assert "create_session_worktree" in apertura
        assert "self.context.session.workspace_root = " in apertura, (
            "senza questo i ruoli continuerebbero a scrivere nell'albero vero")

        chiusura = inspect.getsource(DevOrchestrator._chiudi_worktree)
        assert "release_session_worktree" in chiusura


# ---------------------------------------------------------------------------
# 2. Chiusura garantita
# ---------------------------------------------------------------------------


class TestChiusuraDiUnRunAbbandonato:
    """Il caso che il codice non copriva: l'utente preme stop."""

    def test_abbandonare_il_generatore_rilascia_comunque_il_worktree(self, monkeypatch):
        from core.harness import loop as modulo_loop

        rilasciati = []
        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False, **_: rilasciati.append((sid, apply_changes)) or {},
        )

        finto_wt = object()

        def impl_finta(*args, **kwargs):
            chiusura = kwargs["_chiusura"]
            chiusura.update({
                "session_id": "sess-abbandonata",
                "token_workspace": None,
                "review_gate": None,
                "worktree": finto_wt,
                "goal_reached": False,
            })
            yield {"type": "token", "text": "sto lavorando"}
            yield {"type": "token", "text": "ancora"}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        gen = modulo_loop.stream_admin_agent_turn(messages=[])
        next(gen)          # il run e' partito e ha allocato il worktree
        assert rilasciati == []
        gen.close()        # l'utente preme stop

        assert rilasciati == [("sess-abbandonata", False)], (
            "un run interrotto deve rilasciare cio' che aveva allocato"
        )

    def test_abbandonare_il_generatore_sblocca_il_gate_di_revisione(self, monkeypatch):
        """Altrimenti resta un'attesa che nessuno soddisfera' mai."""
        from core.harness import loop as modulo_loop

        rilasciati = []
        monkeypatch.setattr(
            modulo_loop.review, "release_gate", lambda sid: rilasciati.append(sid)
        )

        def impl_finta(*args, **kwargs):
            kwargs["_chiusura"].update({
                "session_id": "sess-gate",
                "review_gate": object(),
                "worktree": None,
                "goal_reached": False,
            })
            yield {"type": "token", "text": "x"}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        gen = modulo_loop.stream_admin_agent_turn(messages=[])
        next(gen)
        gen.close()

        assert rilasciati == ["sess-gate"]

    def test_la_chiusura_avviene_una_volta_sola(self, monkeypatch):
        """Un run che finisce normalmente e poi viene chiuso non rilascia due volte."""
        from core.harness import loop as modulo_loop

        conta = []
        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False, **_: conta.append(sid) or {},
        )

        def impl_finta(*args, **kwargs):
            kwargs["_chiusura"].update({
                "session_id": "sess-doppia",
                "review_gate": None,
                "worktree": object(),
                "goal_reached": True,
            })
            yield {"type": "done", "full_text": ""}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        gen = modulo_loop.stream_admin_agent_turn(messages=[])
        list(gen)
        gen.close()

        assert conta == ["sess-doppia"]

    def test_una_chiusura_che_fallisce_non_travolge_il_run(self, monkeypatch):
        """E' codice di pulizia: se rompe, lascia i residui che doveva togliere."""
        from core.harness import loop as modulo_loop

        def esplode(sid, apply_changes=False, **_):
            raise RuntimeError("git non risponde")

        monkeypatch.setattr(modulo_loop.worktree, "release_session_worktree", esplode)

        chiusura = {
            "session_id": "sess-rotta",
            "review_gate": None,
            "worktree": object(),
            "goal_reached": False,
        }
        assert modulo_loop._chiudi_run(chiusura) == {}


# ---------------------------------------------------------------------------
# 3. Il lavoro non si butta
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_temporaneo(tmp_path):
    """Un repository git minimo su cui allocare worktree veri."""
    import subprocess

    repo = tmp_path / "progetto"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "test@sigma.local"],
        ["config", "user.name", "Test"],
        ["config", "commit.gpgsign", "false"],
    ):
        subprocess.run(["git"] + args, cwd=str(repo), capture_output=True, text=True)
    (repo / "README.md").write_text("progetto\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True)
    subprocess.run(["git", "commit", "-m", "iniziale"], cwd=str(repo), capture_output=True)
    return repo


def _branch_esistenti(repo):
    import subprocess
    res = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=str(repo), capture_output=True, text=True,
    )
    return {r.strip() for r in res.stdout.splitlines() if r.strip()}


class TestIlLavoroNonSiButta:
    def test_un_run_non_concluso_lascia_il_lavoro_su_un_branch(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """Il difetto grave: `git branch -D` su trenta turni di lavoro buono."""
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-incompiuta")
        assert sessione is not None
        (sessione.worktree_path / "lavoro.py").write_text("VALORE = 1\n", encoding="utf-8")
        sessione.checkpoint(1, "primo pezzo")

        esito = worktree.release_session_worktree("sess-incompiuta", apply_changes=False)

        assert esito["applied"] is False
        assert esito["branch"] == sessione.branch_name
        assert esito["checkpoints"] == 1
        # Il branch e' ancora li', con dentro il lavoro.
        assert sessione.branch_name in _branch_esistenti(repo_temporaneo)

    def test_il_lavoro_conservato_e_davvero_recuperabile(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """Conservare il branch senza il contenuto sarebbe una consolazione."""
        import subprocess

        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-recupero")
        (sessione.worktree_path / "lavoro.py").write_text("VALORE = 7\n", encoding="utf-8")
        sessione.checkpoint(1)
        branch = sessione.branch_name
        worktree.release_session_worktree("sess-recupero", apply_changes=False)

        res = subprocess.run(
            ["git", "show", f"{branch}:lavoro.py"],
            cwd=str(repo_temporaneo), capture_output=True, text=True,
        )
        assert res.returncode == 0
        assert "VALORE = 7" in res.stdout

    def test_un_run_a_vuoto_non_lascia_branch_da_ripulire(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """Conservare tutto sarebbe l'errore opposto: i checkpoint di turno si
        fanno con `--allow-empty`, quindi esistono anche quando non c'e' nulla."""
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-vuota")
        sessione.checkpoint(1)
        sessione.checkpoint(2)
        branch = sessione.branch_name

        esito = worktree.release_session_worktree("sess-vuota", apply_changes=False)

        assert esito["branch"] == ""
        assert branch not in _branch_esistenti(repo_temporaneo)

    def test_a_obiettivo_raggiunto_il_lavoro_va_sull_albero_principale(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-conclusa")
        (sessione.worktree_path / "fatto.py").write_text("OK = True\n", encoding="utf-8")
        sessione.checkpoint(1)
        branch = sessione.branch_name

        esito = worktree.release_session_worktree("sess-conclusa", apply_changes=True)

        assert esito["applied"] is True
        assert (repo_temporaneo / "fatto.py").exists()
        # Il lavoro e' al sicuro nell'albero principale: il branch non serve.
        assert esito["branch"] == ""
        assert branch not in _branch_esistenti(repo_temporaneo)

    def test_rilasciare_una_sessione_inesistente_non_esplode(self):
        esito = worktree.release_session_worktree("mai-esistita")
        assert esito["released"] is False


class TestIlBranchConservatoVieneDetto:
    """Un branch di cui nessuno conosce il nome e' perso quanto uno cancellato."""

    def test_il_ciclo_annuncia_il_branch_rimasto(self, monkeypatch):
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False, **_: {
                "released": True, "applied": False,
                "branch": "sigma-run/sess-x", "checkpoints": 3,
            },
        )

        def impl_finta(*args, **kwargs):
            kwargs["_chiusura"].update({
                "session_id": "sess-x",
                "review_gate": None,
                "worktree": object(),
                "goal_reached": False,
            })
            yield {"type": "done", "full_text": ""}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        eventi = list(modulo_loop.stream_admin_agent_turn(messages=[]))
        annunci = [e for e in eventi if e.get("type") == "worktree_preserved"]
        assert len(annunci) == 1
        assert annunci[0]["branch"] == "sigma-run/sess-x"
        assert annunci[0]["checkpoints"] == 3

    def test_senza_branch_rimasto_non_si_annuncia_niente(self, monkeypatch):
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False: {"released": True, "applied": True, "branch": ""},
        )

        def impl_finta(*args, **kwargs):
            kwargs["_chiusura"].update({
                "session_id": "sess-y", "review_gate": None,
                "worktree": object(), "goal_reached": True,
            })
            yield {"type": "done", "full_text": ""}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        eventi = list(modulo_loop.stream_admin_agent_turn(messages=[]))
        assert not [e for e in eventi if e.get("type") == "worktree_preserved"]


class TestIlTrasferimentoAllAlberoPrincipale:
    """`apply_to_main` era irraggiungibile e quindi mai messo alla prova: da
    quando l'isolamento si puo' accendere, gira sul repository vero."""

    def test_l_ultimo_turno_non_va_perduto(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """Il diff guarda solo cio' che e' committato. Senza un checkpoint di
        chiusura si perdeva la modifica che aveva appena chiuso l'obiettivo."""
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-ultimo")
        (sessione.worktree_path / "primo.py").write_text("A = 1\n", encoding="utf-8")
        sessione.checkpoint(1)
        # Scritto dopo l'ultimo checkpoint, come nell'ultimo turno di un run.
        (sessione.worktree_path / "ultimo.py").write_text("B = 2\n", encoding="utf-8")

        assert sessione.apply_to_main() is True
        assert (repo_temporaneo / "primo.py").exists()
        assert (repo_temporaneo / "ultimo.py").exists(), (
            "il lavoro dell'ultimo turno non e' arrivato all'albero principale"
        )

    def test_la_base_del_diff_sopravvive_a_un_rollback(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """`HEAD~N` contava i checkpoint: dopo un rollback quel numero mente."""
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-base")
        assert sessione.base_commit, "il commit di partenza non e' stato registrato"

        (sessione.worktree_path / "buono.py").write_text("OK = 1\n", encoding="utf-8")
        sessione.checkpoint(1)
        (sessione.worktree_path / "sbagliato.py").write_text("NO = 1\n", encoding="utf-8")
        sessione.checkpoint(2)
        sessione.rollback(1)

        assert sessione.apply_to_main() is True
        assert (repo_temporaneo / "buono.py").exists()
        assert not (repo_temporaneo / "sbagliato.py").exists()

    def test_un_trasferimento_fallito_conserva_comunque_il_lavoro(
        self, repo_temporaneo, monkeypatch, tmp_path
    ):
        """Il caso peggiore: obiettivo raggiunto, merge in conflitto. Buttare il
        branch qui vorrebbe dire perdere un run riuscito."""
        monkeypatch.setattr("core.paths.var_dir", lambda: tmp_path / "var")

        sessione = worktree.create_session_worktree(repo_temporaneo, "sess-conflitto")
        (sessione.worktree_path / "conteso.py").write_text("VERSIONE = 'agente'\n", encoding="utf-8")
        sessione.checkpoint(1)
        # Nel frattempo qualcuno ha scritto lo stesso file sull'albero vivo.
        (repo_temporaneo / "conteso.py").write_text("VERSIONE = 'umano'\n", encoding="utf-8")

        esito = worktree.release_session_worktree("sess-conflitto", apply_changes=True)

        assert esito["applied"] is False
        assert esito["branch"] == sessione.branch_name
        assert (repo_temporaneo / "conteso.py").read_text(encoding="utf-8") == "VERSIONE = 'umano'\n"

    def test_il_conflitto_viene_distinto_dall_obiettivo_non_chiuso(self, monkeypatch):
        """Sono due messaggi diversi: uno informa, l'altro chiede di agire."""
        from core.harness import loop as modulo_loop

        monkeypatch.setattr(
            modulo_loop.worktree, "release_session_worktree",
            lambda sid, apply_changes=False, **_: {
                "released": True, "applied": False,
                "branch": "sigma-run/sess-c", "checkpoints": 2,
            },
        )

        def impl_finta(*args, **kwargs):
            kwargs["_chiusura"].update({
                "session_id": "sess-c", "review_gate": None,
                "worktree": object(), "goal_reached": True,
            })
            yield {"type": "done", "full_text": ""}

        monkeypatch.setattr(modulo_loop, "_stream_agent_turn_impl", impl_finta)

        eventi = list(modulo_loop.stream_admin_agent_turn(messages=[]))
        annuncio = [e for e in eventi if e.get("type") == "worktree_preserved"][0]
        assert annuncio["goal_reached"] is True
        assert annuncio["apply_failed"] is True
