"""Il lavoro fatto sui moduli torna nel repository dei moduli.

Si sviluppa dentro Sigma Studio, ma i moduli non appartengono a questo
repository: ognuno dichiara nel manifest da dove viene. Il loader sa portarli
da li' a qui; finora non esisteva il verso inverso, e la conseguenza era che
il lavoro sui moduli **non stava in nessun repository** — non in questo, che li
ignora, e non nel loro, che non veniva mai aggiornato.

I test qui sotto tengono ferme le proprieta' che rendono la sincronizzazione
affidabile invece che pericolosa: rispecchia davvero (cancellazioni comprese),
non tocca cio' che non sa produrre, non pubblica credenziali, e non butta via
i commit locali quando il remoto e' andato avanti.

Nessun test parla con la rete: i "remoti" sono repository bare locali.
"""

import json
import subprocess
from pathlib import Path

import pytest

from core import module_sync
from core.module_sync import (
    ModuloLocale,
    Rispecchiamento,
    mirror_tree,
    stage_module,
)


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


@pytest.fixture
def remoto(tmp_path):
    """Un repository bare che fa da GitHub, in locale."""
    bare = tmp_path / "moduli.git"
    _git(["init", "--bare", "-b", "main", str(bare)], tmp_path)

    semina = tmp_path / "semina"
    _git(["clone", str(bare), str(semina)], tmp_path)
    for args in (["config", "user.email", "t@sigma.local"],
                 ["config", "user.name", "Test"],
                 ["config", "commit.gpgsign", "false"]):
        _git(args, semina)
    (semina / "README.md").write_text("moduli\n", encoding="utf-8")
    _git(["add", "-A"], semina)
    _git(["commit", "-m", "iniziale"], semina)
    _git(["push", "origin", "main"], semina)
    return bare


@pytest.fixture
def albero_vivo(tmp_path, monkeypatch):
    """Un finto albero di Sigma Studio con un modulo installato."""
    backend = tmp_path / "core" / "modules"
    frontend = tmp_path / "sigma_studio" / "src" / "modules"
    (backend / "modulo_prova").mkdir(parents=True)
    (frontend / "modulo_prova").mkdir(parents=True)

    monkeypatch.setattr(module_sync, "_CORE_MODULES_DIR", backend)
    monkeypatch.setattr(module_sync, "_FRONTEND_MODULES_DIR", frontend)
    monkeypatch.setattr(module_sync.paths, "var_dir", lambda: tmp_path / "var")
    # Anche la configurazione: `save_config` scrive davvero, e un test che
    # scrive in `config/` cambia la macchina di chi lo esegue.
    finta_config = tmp_path / "config"
    finta_config.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module_sync.paths, "config_dir", lambda: finta_config)
    # L'attesa fra due sincronizzazioni non richieste e' stato di processo:
    # senza azzerarla, l'ordine dei test deciderebbe quali passano.
    monkeypatch.setattr(module_sync, "_ultima_automatica", 0.0)
    return tmp_path


def _scrivi_modulo(radice, repository, module_id="modulo_prova"):
    backend = radice / "core" / "modules" / module_id
    frontend = radice / "sigma_studio" / "src" / "modules" / module_id
    (backend / "manifest.json").write_text(json.dumps({
        "id": module_id,
        "repository": str(repository),
        "branch": "main",
        "path": f"modules/{module_id}",
    }), encoding="utf-8")
    (backend / "handlers.py").write_text("VERSIONE = 1\n", encoding="utf-8")
    (frontend / "Vista.jsx").write_text("export default null;\n", encoding="utf-8")
    return backend, frontend


# ---------------------------------------------------------------------------
# Rispecchiamento
# ---------------------------------------------------------------------------


class TestRispecchiamento:
    def test_copia_cio_che_manca(self, tmp_path):
        src, dst = tmp_path / "a", tmp_path / "b"
        (src / "sub").mkdir(parents=True)
        (src / "uno.py").write_text("X = 1\n", encoding="utf-8")
        (src / "sub" / "due.py").write_text("Y = 2\n", encoding="utf-8")

        esito = mirror_tree(src, dst)

        assert sorted(esito.aggiunti) == ["sub/due.py", "uno.py"]
        assert (dst / "sub" / "due.py").read_text(encoding="utf-8") == "Y = 2\n"

    def test_riconosce_cio_che_e_cambiato(self, tmp_path):
        src, dst = tmp_path / "a", tmp_path / "b"
        src.mkdir(); dst.mkdir()
        (src / "uno.py").write_text("X = 1\n", encoding="utf-8")
        (dst / "uno.py").write_text("X = 0\n", encoding="utf-8")

        esito = mirror_tree(src, dst)
        assert esito.modificati == ["uno.py"]
        assert (dst / "uno.py").read_text(encoding="utf-8") == "X = 1\n"

    def test_un_file_identico_non_risulta_cambiato(self, tmp_path):
        src, dst = tmp_path / "a", tmp_path / "b"
        src.mkdir(); dst.mkdir()
        (src / "uno.py").write_text("X = 1\n", encoding="utf-8")
        (dst / "uno.py").write_text("X = 1\n", encoding="utf-8")

        assert mirror_tree(src, dst).vuoto

    def test_cancella_cio_che_non_esiste_piu(self, tmp_path):
        """Senza questo, un file rinominato resta anche col vecchio nome e chi
        installa il modulo si ritrova due versioni dello stesso codice."""
        src, dst = tmp_path / "a", tmp_path / "b"
        src.mkdir(); dst.mkdir()
        (src / "nuovo.py").write_text("X = 1\n", encoding="utf-8")
        (dst / "vecchio.py").write_text("X = 1\n", encoding="utf-8")

        esito = mirror_tree(src, dst)

        assert esito.rimossi == ["vecchio.py"]
        assert not (dst / "vecchio.py").exists()
        assert (dst / "nuovo.py").exists()

    def test_le_cartelle_svuotate_spariscono(self, tmp_path):
        src, dst = tmp_path / "a", tmp_path / "b"
        src.mkdir()
        (dst / "morta").mkdir(parents=True)
        (dst / "morta" / "x.py").write_text("", encoding="utf-8")

        mirror_tree(src, dst)
        assert not (dst / "morta").exists()

    def test_non_pubblica_cache_e_prodotti_di_compilazione(self, tmp_path):
        src, dst = tmp_path / "a", tmp_path / "b"
        (src / "__pycache__").mkdir(parents=True)
        (src / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\x00")
        (src / "node_modules").mkdir()
        (src / "node_modules" / "pacchetto.js").write_text("", encoding="utf-8")
        (src / "buono.py").write_text("X = 1\n", encoding="utf-8")

        esito = mirror_tree(src, dst)

        assert esito.aggiunti == ["buono.py"]
        assert not (dst / "__pycache__").exists()
        assert not (dst / "node_modules").exists()

    def test_non_pubblica_file_che_sembrano_credenziali(self, tmp_path):
        """Pubblicare su GitHub non si annulla: nel dubbio il file resta qui."""
        src, dst = tmp_path / "a", tmp_path / "b"
        src.mkdir()
        (src / ".env").write_text("TOKEN=abc\n", encoding="utf-8")
        (src / "api_key.json").write_text("{}", encoding="utf-8")
        (src / "server.pem").write_text("x", encoding="utf-8")
        (src / "handlers.py").write_text("X = 1\n", encoding="utf-8")

        esito = mirror_tree(src, dst)

        assert esito.aggiunti == ["handlers.py"]
        assert sorted(esito.segreti_saltati) == [".env", "api_key.json", "server.pem"]
        assert not (dst / ".env").exists()


class TestDisposizioneDelModulo:
    """La disposizione nel repository e' l'inverso esatto di quella che il
    loader produce installando: se le due divergono, il modulo pubblicato non
    e' installabile."""

    def test_backend_e_frontend_finiscono_nelle_loro_cartelle(
        self, albero_vivo, tmp_path
    ):
        _scrivi_modulo(albero_vivo, "https://esempio.invalid/moduli")
        modulo = module_sync.discover_modules()[0]
        repo = tmp_path / "repo"

        stage_module(modulo, repo)

        assert (repo / "modules/modulo_prova/backend/handlers.py").is_file()
        assert (repo / "modules/modulo_prova/frontend/Vista.jsx").is_file()

    def test_il_manifest_sta_nella_radice_del_modulo_non_nel_backend(
        self, albero_vivo, tmp_path
    ):
        """Il loader lo cerca li', e ce lo rimette dentro al backend da solo:
        pubblicarlo due volte creerebbe due copie che possono divergere."""
        _scrivi_modulo(albero_vivo, "https://esempio.invalid/moduli")
        modulo = module_sync.discover_modules()[0]
        repo = tmp_path / "repo"

        stage_module(modulo, repo)

        assert (repo / "modules/modulo_prova/manifest.json").is_file()
        assert not (repo / "modules/modulo_prova/backend/manifest.json").exists()

    def test_un_modulo_senza_repository_non_viene_toccato(self, albero_vivo):
        """Non si inventa dove mandare qualcosa che non dice da dove viene."""
        backend = albero_vivo / "core" / "modules" / "modulo_prova"
        (backend / "manifest.json").write_text(
            json.dumps({"id": "modulo_prova"}), encoding="utf-8"
        )
        assert module_sync.discover_modules() == []


# ---------------------------------------------------------------------------
# Sincronizzazione completa
# ---------------------------------------------------------------------------


class TestSincronizzazione:
    def test_commit_e_push_portano_il_lavoro_sul_remoto(self, albero_vivo, remoto, tmp_path):
        _scrivi_modulo(albero_vivo, str(remoto))

        esito = module_sync.sync_modules(push=True)

        assert esito["success"] is True, esito["errors"]
        assert esito["committed"] is True
        assert esito["pushed"] is True

        verifica = tmp_path / "verifica"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert (verifica / "modules/modulo_prova/backend/handlers.py").read_text(
            encoding="utf-8") == "VERSIONE = 1\n"
        assert (verifica / "modules/modulo_prova/frontend/Vista.jsx").is_file()

    def test_senza_push_il_lavoro_resta_qui(self, albero_vivo, remoto, tmp_path):
        """Committare e' reversibile e resta su questa macchina; pubblicare no."""
        _scrivi_modulo(albero_vivo, str(remoto))

        esito = module_sync.sync_modules(push=False)

        assert esito["committed"] is True
        assert esito["pushed"] is False

        verifica = tmp_path / "verifica"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert not (verifica / "modules").exists()

    def test_una_seconda_sincronizzazione_senza_modifiche_non_committa(
        self, albero_vivo, remoto
    ):
        _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.sync_modules(push=True)

        secondo = module_sync.sync_modules(push=True)
        assert secondo["committed"] is False
        assert secondo["changed"] == {}

    def test_una_modifica_successiva_arriva_sul_remoto(
        self, albero_vivo, remoto, tmp_path
    ):
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.sync_modules(push=True)

        (backend / "handlers.py").write_text("VERSIONE = 2\n", encoding="utf-8")
        esito = module_sync.sync_modules(push=True)

        assert esito["changed"]["modulo_prova"]["modificati"] == ["backend/handlers.py"]
        verifica = tmp_path / "verifica2"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert (verifica / "modules/modulo_prova/backend/handlers.py").read_text(
            encoding="utf-8") == "VERSIONE = 2\n"

    def test_un_file_cancellato_qui_sparisce_anche_di_la(
        self, albero_vivo, remoto, tmp_path
    ):
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))
        (backend / "vecchio.py").write_text("X = 0\n", encoding="utf-8")
        module_sync.sync_modules(push=True)

        (backend / "vecchio.py").unlink()
        module_sync.sync_modules(push=True)

        verifica = tmp_path / "verifica3"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert not (verifica / "modules/modulo_prova/backend/vecchio.py").exists()

    def test_la_prova_a_vuoto_prepara_e_si_ferma(self, albero_vivo, remoto, tmp_path):
        _scrivi_modulo(albero_vivo, str(remoto))

        esito = module_sync.sync_modules(dry_run=True)

        assert esito["committed"] is False
        assert "modulo_prova" in esito["changed"]
        verifica = tmp_path / "verifica4"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert not (verifica / "modules").exists()

    def test_si_puo_sincronizzare_un_solo_modulo(self, albero_vivo, remoto):
        _scrivi_modulo(albero_vivo, str(remoto))
        (albero_vivo / "core/modules/altro").mkdir()
        (albero_vivo / "core/modules/altro/manifest.json").write_text(json.dumps({
            "id": "altro", "repository": str(remoto), "branch": "main",
            "path": "modules/altro",
        }), encoding="utf-8")
        (albero_vivo / "core/modules/altro/x.py").write_text("A = 1\n", encoding="utf-8")

        esito = module_sync.sync_modules(module_ids=["modulo_prova"], push=False)
        assert set(esito["changed"]) == {"modulo_prova"}

    def test_un_push_fallito_non_perde_il_commit(self, albero_vivo, remoto, tmp_path):
        """Il commit resta nella copia di lavoro: e' l'unica copia di quel
        lavoro, e il messaggio deve dire dov'e'."""
        _scrivi_modulo(albero_vivo, str(remoto))
        # Il remoto sparisce fra il commit e il push.
        import shutil as _sh

        def push_impossibile(args, cwd, timeout_s=120.0):
            if args and args[0] == "push":
                _sh.rmtree(remoto, ignore_errors=True)
            return _esegui_vero(args, cwd, timeout_s)

        _esegui_vero = module_sync._esegui_git
        module_sync._esegui_git = push_impossibile
        try:
            esito = module_sync.sync_modules(push=True)
        finally:
            module_sync._esegui_git = _esegui_vero

        assert esito["success"] is False
        assert esito["committed"] is True
        assert esito["pushed"] is False
        assert any("push fallito" in e for e in esito["errors"])

        copia = module_sync.repo_workdir(str(remoto))
        registro = _git(["log", "--oneline"], copia).stdout
        assert "modulo_prova" in registro


class TestLaCopiaDiLavoroNonPerdeLavoro:
    def test_i_commit_locali_non_pubblicati_sopravvivono_a_un_riallineamento(
        self, albero_vivo, remoto
    ):
        """`reset --hard` sarebbe stato piu' semplice e avrebbe cancellato
        proprio il lavoro che un push fallito lascia solo li'."""
        _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.sync_modules(push=False)   # commit locale, mai pubblicato

        copia = module_sync.repo_workdir(str(remoto))
        prima = _git(["rev-parse", "HEAD"], copia).stdout.strip()

        radice, errore = module_sync.ensure_clone(str(remoto), "main")
        assert errore == ""
        registro = _git(["log", "--oneline"], radice).stdout
        assert "modulo_prova" in registro, "il commit locale e' stato perso"
        assert prima


class TestQualiModuliSonoStatiToccati:
    """Serve a chi ha appena scritto dei file e non sa se siano di un modulo."""

    def test_riconosce_un_file_di_backend(self, albero_vivo):
        backend, _ = _scrivi_modulo(albero_vivo, "https://esempio.invalid/m")
        assert module_sync.modules_touched_by(
            [str(backend / "handlers.py")]) == ["modulo_prova"]

    def test_riconosce_un_file_di_frontend(self, albero_vivo):
        _, frontend = _scrivi_modulo(albero_vivo, "https://esempio.invalid/m")
        assert module_sync.modules_touched_by(
            [str(frontend / "Vista.jsx")]) == ["modulo_prova"]

    def test_un_file_del_kernel_non_appartiene_a_nessun_modulo(self, albero_vivo):
        _scrivi_modulo(albero_vivo, "https://esempio.invalid/m")
        assert module_sync.modules_touched_by(
            [str(albero_vivo / "core" / "harness" / "loop.py")]) == []

    def test_lo_stesso_modulo_non_viene_riportato_due_volte(self, albero_vivo):
        backend, frontend = _scrivi_modulo(albero_vivo, "https://esempio.invalid/m")
        toccati = module_sync.modules_touched_by([
            str(backend / "handlers.py"), str(frontend / "Vista.jsx"),
        ])
        assert toccati == ["modulo_prova"]


class TestRiepilogo:
    def test_il_messaggio_di_commit_dice_cosa_e_cambiato(self):
        messaggio = module_sync._messaggio_commit({
            "sigma_network": Rispecchiamento(aggiunti=["a.py"], modificati=["b.py"]),
        })
        assert "sigma_network" in messaggio
        assert "1 aggiunti" in messaggio

    def test_con_piu_moduli_il_titolo_li_conta(self):
        messaggio = module_sync._messaggio_commit({
            "uno": Rispecchiamento(aggiunti=["a"]),
            "due": Rispecchiamento(modificati=["b"]),
        })
        assert messaggio.splitlines()[0] == "Aggiorna 2 moduli da Sigma Studio"


# ---------------------------------------------------------------------------
# L'automatismo
# ---------------------------------------------------------------------------


class TestSincronizzazioneAutomatica:
    """Il passaggio manuale e' esattamente quello che finora non avveniva mai:
    e' il motivo per cui il repository dei moduli era rimasto indietro."""

    def test_un_run_che_tocca_un_modulo_lo_sincronizza(
        self, albero_vivo, remoto, tmp_path
    ):
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))

        esito = module_sync.auto_sync_paths([str(backend / "handlers.py")])

        assert esito is not None
        assert esito["pushed"] is True
        verifica = tmp_path / "verifica_auto"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert (verifica / "modules/modulo_prova/backend/handlers.py").is_file()

    def test_un_run_che_tocca_solo_il_kernel_non_sincronizza_niente(
        self, albero_vivo, remoto
    ):
        _scrivi_modulo(albero_vivo, str(remoto))
        assert module_sync.auto_sync_paths(
            [str(albero_vivo / "core" / "harness" / "loop.py")]) is None

    def test_spegnere_l_automatismo_lo_spegne(self, albero_vivo, remoto):
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.save_config({"auto_commit": False})
        assert module_sync.auto_sync_paths([str(backend / "handlers.py")]) is None

    def test_si_puo_committare_senza_pubblicare(self, albero_vivo, remoto, tmp_path):
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.save_config({"auto_commit": True, "auto_push": False})

        esito = module_sync.auto_sync_paths([str(backend / "handlers.py")])

        assert esito["committed"] is True
        assert esito["pushed"] is False
        verifica = tmp_path / "verifica_nopush"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert not (verifica / "modules").exists()

    def test_un_errore_di_git_non_fa_fallire_il_run(self, albero_vivo, remoto, monkeypatch):
        """E' un passo accessorio a fine run: non deve travolgere il lavoro."""
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))

        def esplode(**kwargs):
            raise RuntimeError("git non risponde")

        monkeypatch.setattr(module_sync, "sync_modules", esplode)
        esito = module_sync.auto_sync_paths([str(backend / "handlers.py")])
        assert esito["success"] is False

    def test_il_ciclo_agente_annuncia_i_moduli_sincronizzati(self, monkeypatch):
        from core.harness import loop as modulo_loop

        class LedgerFinto:
            modified_files = ["core/modules/x/handlers.py"]

        monkeypatch.setattr(
            "core.module_sync.auto_sync_paths",
            lambda percorsi, nota="": {
                "changed": {"sigma_network": {}}, "pushed": True, "errors": [],
            },
        )
        evento = modulo_loop._sincronizza_moduli_toccati(LedgerFinto(), "obiettivo")
        assert evento["type"] == "modules_synced"
        assert evento["modules"] == ["sigma_network"]
        assert evento["pushed"] is True

    def test_senza_file_modificati_il_ciclo_non_annuncia_niente(self, monkeypatch):
        from core.harness import loop as modulo_loop

        class LedgerVuoto:
            modified_files = []

        assert modulo_loop._sincronizza_moduli_toccati(LedgerVuoto(), "x") is None


class TestGliIngressiSonoCollegati:
    """La lezione che questo progetto ha gia' imparato quattro volte: una
    funzionalita' che nessun percorso reale invoca non esiste."""

    def test_il_salvataggio_dall_editor_avvia_la_sincronizzazione(self):
        import inspect
        from core.modules.sigma_developer_lab import handlers

        sorgente = inspect.getsource(handlers.handle_fs_write)
        assert "auto_sync_in_background" in sorgente

    def test_la_fine_di_un_run_avvia_la_sincronizzazione(self):
        import inspect
        from core.harness.loop import _stream_agent_turn_impl

        assert "_sincronizza_moduli_toccati(" in inspect.getsource(_stream_agent_turn_impl)

    def test_esiste_una_rotta_per_farlo_a_mano(self):
        import inspect
        from core import fastapi_app

        sorgente = inspect.getsource(fastapi_app)
        assert '"/api/modules/sync"' in sorgente
        assert '"/api/modules/sync/status"' in sorgente


class TestUnaCopiaDiLavoroSporca:
    """Una prova a vuoto lascia sempre il rispecchiamento non committato, e
    `git rebase` su un albero sporco si rifiuta di partire: senza ripulitura
    la sincronizzazione successiva falliva sempre dopo un dry-run."""

    def test_dopo_una_prova_a_vuoto_la_sincronizzazione_vera_riesce(
        self, albero_vivo, remoto, tmp_path
    ):
        _scrivi_modulo(albero_vivo, str(remoto))

        module_sync.sync_modules(dry_run=True)
        esito = module_sync.sync_modules(push=True)

        assert esito["success"] is True, esito["errors"]
        assert esito["pushed"] is True
        verifica = tmp_path / "verifica_sporca"
        _git(["clone", str(remoto), str(verifica)], tmp_path)
        assert (verifica / "modules/modulo_prova/backend/handlers.py").is_file()

    def test_la_ripulitura_non_tocca_i_commit_locali(self, albero_vivo, remoto):
        """Butta solo cio' che il rispecchiamento sa riprodurre."""
        backend, _ = _scrivi_modulo(albero_vivo, str(remoto))
        module_sync.sync_modules(push=False)      # commit locale mai pubblicato
        module_sync.sync_modules(dry_run=True)    # sporca l'albero

        radice, errore = module_sync.ensure_clone(str(remoto), "main")

        assert errore == ""
        assert "modulo_prova" in _git(["log", "--oneline"], radice).stdout
