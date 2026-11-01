# ==============================================================================
# core/module_loader.py — Sigma Studio Module Loader
# Carica dinamicamente i moduli opzionali installati dall'utente.
# Registra route HTTP e MCP server a runtime, senza modificare il kernel.
# ==============================================================================
"""Loader runtime per i moduli opzionali di Sigma Studio.

I moduli vengono scaricati da GitHub, installati in:
  - core/modules/{module_id}/    ← backend Python
  - sigma_studio/src/modules/{module_id}/  ← frontend React

Questo loader importa il backend di ogni modulo installato e chiama
handlers.register_routes(app) per registrare le route sull'app FastAPI.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from core import paths
from core.logger import get_logger
from core.net_utils import safe_urlopen

log = get_logger(__name__)

# Paths risolti rispetto alla root del progetto
_ROOT                 = str(paths.project_root())
_CORE_MODULES_DIR     = str(paths.modules_backend_dir())
_FRONTEND_MODULES_DIR = str(paths.frontend_modules_dir())
_FRONTEND_DIR         = str(paths.frontend_dir())
_STATE_FILE           = str(paths.installed_modules_file())


def _sanitize_git_url(raw_url: str) -> tuple[str, str, str]:
    """
    Estrae repo_url pulito, branch e module_subpath da un eventuale URL GitHub web.
    Esempio: https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab
    -> ('https://github.com/Sigmanih/SigmaStudio-Moduli.git', 'main', 'modules/sigma_hardware_lab')
    """
    if not raw_url:
        return ("https://github.com/Sigmanih/SigmaStudio-Moduli.git", "main", "")

    if "/tree/" in raw_url:
        base_repo, rest = raw_url.split("/tree/", 1)
        parts = rest.split("/", 1)
        branch = parts[0] if parts else "main"
        subpath = parts[1] if len(parts) > 1 else ""
        clean_repo = base_repo.rstrip("/")
        if not clean_repo.endswith(".git"):
            clean_repo += ".git"
        return (clean_repo, branch, subpath)

    clean_repo = raw_url.rstrip("/")
    if not clean_repo.endswith(".git") and "github.com" in clean_repo:
        clean_repo += ".git"
    return (clean_repo, "main", "")


class ModuleLoader:
    """Gestisce il ciclo di vita dei moduli opzionali di Sigma Studio."""

    _operation_lock = threading.RLock()

    def __init__(self) -> None:
        self._loaded: dict[str, Any] = {}
        self._registrations: dict[str, dict] = {}
        self._app = None
        # Assicura che core/modules esista come package Python
        os.makedirs(_CORE_MODULES_DIR, exist_ok=True)
        init_file = os.path.join(_CORE_MODULES_DIR, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w", encoding="utf-8").close()

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    def load_installed(self, app: Any) -> None:
        """Chiamato al boot: registra route di tutti i moduli installati."""
        self._app = app
        for module_id in self._enabled_module_ids():
            try:
                self._validate_module_id(module_id)
                self._load_module(module_id, app)
            except (ValueError, OSError) as exc:
                log.error("Modulo non caricabile %s: %s", module_id, exc)

    def _enabled_module_ids(self) -> list[str]:
        state = self._read_state()
        for manifest in sorted(Path(_CORE_MODULES_DIR).glob("*/manifest.json")):
            try:
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
                if metadata.get("id") == manifest.parent.name and metadata.get("enabled_by_default") is True:
                    state.setdefault(manifest.parent.name, True)
            except (OSError, ValueError, AttributeError) as exc:
                log.warning("Manifest non leggibile %s: %s", manifest, exc)
        return [module_id for module_id, installed in state.items() if installed is True]

    def load_services(self) -> None:
        """Prepara le capacita' necessarie al launcher prima di avviare HTTP."""
        from core import service_registry
        for module_id in self._enabled_module_ids():
            previous = service_registry.snapshot()
            try:
                backend = self._import_backend(module_id)
                if backend is not None and hasattr(backend[0], "register_services"):
                    backend[0].register_services(service_registry)
            except Exception as exc:
                service_registry.restore(previous)
                log.error("Servizi del modulo %s non caricati: %s", module_id, exc)

    @staticmethod
    def _validate_module_id(module_id: str) -> None:
        if not isinstance(module_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", module_id):
            raise ValueError("Identificativo modulo non valido.")

    @contextmanager
    def _filesystem_transaction(self, module_id: str):
        """Ripristina codice e build precedente se un passaggio fallisce."""
        self._validate_module_id(module_id)
        roots = [Path(_CORE_MODULES_DIR), Path(_FRONTEND_MODULES_DIR)]
        destinations = [root / module_id for root in roots]
        destinations.append(Path(_FRONTEND_DIR) / "dist")
        for root, target in zip(roots, destinations):
            if target.resolve().parent != root.resolve() or target.is_symlink() or getattr(target, "is_junction", lambda: False)():
                raise ValueError("Il modulo collegato va gestito dal registro dei collegamenti.")
        with self._operation_lock, tempfile.TemporaryDirectory(prefix="sigma-module-rollback-") as backup:
            saved = []
            runtime = self._runtime_snapshot(self._app)
            state_path = Path(_STATE_FILE)
            state_before = state_path.read_bytes() if state_path.exists() else None
            loaded_before = dict(self._loaded)
            registrations_before = dict(self._registrations)
            prefix = f"core.modules.{module_id}"
            imported_before = {name: value for name, value in sys.modules.items()
                               if name == prefix or name.startswith(prefix + ".")}
            try:
                for index, destination in enumerate(destinations):
                    old = Path(backup) / str(index)
                    if destination.exists():
                        shutil.copytree(destination, old)
                    saved.append((destination, old))
                yield
            except Exception:
                self._restore_runtime(self._app, runtime)
                self._loaded = loaded_before
                self._registrations = registrations_before
                for name in list(sys.modules):
                    if name == prefix or name.startswith(prefix + "."):
                        sys.modules.pop(name, None)
                sys.modules.update(imported_before)
                for destination, old in reversed(saved):
                    if destination.exists():
                        shutil.rmtree(destination)
                    if old.exists():
                        shutil.copytree(old, destination)
                if state_before is None:
                    state_path.unlink(missing_ok=True)
                else:
                    state_path.write_bytes(state_before)
                raise

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(self, module_id: str, repo_url: str = "", branch: str = "main", module_path: str = "", app: Any = None) -> dict:
        self._app = app or self._app
        with self._filesystem_transaction(module_id):
            return self._install(module_id, repo_url, branch, module_path, self._app)

    @staticmethod
    def _runtime_snapshot(app: Any) -> dict:
        from core import service_registry
        from core.mcp.mcp_hub import mcp_hub
        from core.harness import tool_providers
        adapter = getattr(sys.modules.get("core.fastapi_app"), "FastAPIHandlerAdapter", None)
        return {"services": service_registry.snapshot(), "routes": list(app.router.routes) if app is not None else [],
                "servers": dict(mcp_hub.servers), "tools": tool_providers.snapshot(),
                "adapter": adapter,
                "get": dict(getattr(adapter, "_GET_HANDLERS", {})),
                "post": dict(getattr(adapter, "_POST_HANDLERS", {})),
                "handlers": {k: v for k, v in vars(adapter).items() if k.startswith("handle_")} if adapter else {}}

    @staticmethod
    def _restore_runtime(app: Any, snapshot: dict) -> None:
        from core import service_registry
        service_registry.restore(snapshot["services"])
        from core.mcp.mcp_hub import mcp_hub
        from core.harness import tool_providers
        if app is not None:
            app.router.routes[:] = snapshot["routes"]
            app.openapi_schema = None
        mcp_hub.servers.clear()
        mcp_hub.servers.update(snapshot["servers"])
        tool_providers.restore(snapshot["tools"])
        adapter = snapshot["adapter"]
        if adapter:
            adapter._GET_HANDLERS = snapshot["get"]
            adapter._POST_HANDLERS = snapshot["post"]
            for name in list(vars(adapter)):
                if name.startswith("handle_") and name not in snapshot["handlers"]:
                    delattr(adapter, name)
            for name, handler in snapshot["handlers"].items():
                setattr(adapter, name, handler)

    def _runtime_additions(self, app: Any, snapshot: dict) -> dict:
        return {"before": snapshot, "after": self._runtime_snapshot(app), "app": app}

    def _unregister_module(self, module_id: str) -> None:
        from core import service_registry
        from core.mcp.mcp_hub import mcp_hub
        from core.harness import tool_providers
        registration = self._registrations.pop(module_id, None)
        if registration is None:
            return
        before, after, app = registration["before"], registration["after"], registration["app"]
        service_registry.remove_changes(before["services"], after["services"])
        if app is not None:
            added = {id(route) for route in after["routes"]} - {id(route) for route in before["routes"]}
            app.router.routes[:] = [route for route in app.router.routes if id(route) not in added]
            app.openapi_schema = None
        for name, server in after["servers"].items():
            if before["servers"].get(name) is not server and mcp_hub.servers.get(name) is server:
                mcp_hub.servers.pop(name, None)
                if name in before["servers"]:
                    mcp_hub.servers[name] = before["servers"][name]
        tool_providers.remove_changes(before["tools"], after["tools"])
        adapter = after["adapter"]
        if adapter:
            for key, attr in (("get", "_GET_HANDLERS"), ("post", "_POST_HANDLERS")):
                mapping = getattr(adapter, attr)
                for name, value in after[key].items():
                    if before[key].get(name) != value and mapping.get(name) == value:
                        mapping.pop(name, None)
                        if name in before[key]:
                            mapping[name] = before[key][name]
            for name, handler in after["handlers"].items():
                if before["handlers"].get(name) is not handler and getattr(adapter, name, None) is handler:
                    if name in before["handlers"]:
                        setattr(adapter, name, before["handlers"][name])
                    else:
                        delattr(adapter, name)

    def _install(self, module_id: str, repo_url: str, branch: str,
                 module_path: str, app: Any) -> dict:
        """
        Installa un modulo da repository locale o GitHub:
        1. Copia backend -> core/modules/{module_id}/
        2. Copia frontend -> sigma_studio/src/modules/{module_id}/
        3. npm run build
        4. Registra route a runtime
        5. Persiste stato installato
        """
        log.info(f"[ModuleLoader] Inizio installazione '{module_id}'...")

        clean_repo, parsed_branch, parsed_path = _sanitize_git_url(repo_url)
        if not branch or branch == "main":
            branch = parsed_branch or "main"
        if not module_path:
            module_path = parsed_path or f"modules/{module_id}"
        if Path(module_path).is_absolute() or ".." in Path(module_path.replace("\\", "/")).parts:
            raise ValueError("Percorso sorgente del modulo non valido.")
        if not branch or branch.startswith("-") or "\n" in branch:
            raise ValueError("Branch non valido.")

        # 1. Verifica se esiste una cartella sorgente locale (sviluppo o repo collegata)
        possible_local_paths = [
            os.path.abspath(os.path.join(_ROOT, "..", "SigmaStudio-Moduli", "modules", module_id)),
            os.path.abspath(os.path.join(_ROOT, "SigmaStudio-Moduli", "modules", module_id)),
            os.path.abspath(os.path.join(_ROOT, "..", "..", "SigmaStudio-Moduli", "modules", module_id)),
        ]

        found_local = None
        for p in possible_local_paths:
            if os.path.exists(p):
                found_local = p
                break

        if found_local:
            log.info(f"[ModuleLoader] Trovato modulo locale in: {found_local}")
            self._copy_module_from_dir(found_local, module_id)
        else:
            log.info(f"[ModuleLoader] Download remoto per '{module_id}' da {clean_repo} (branch: {branch})...")
            with tempfile.TemporaryDirectory() as tmp_dir:
                module_tmp = os.path.join(tmp_dir, module_id)
                downloaded = False

                # Metodo A: Git sparse-checkout
                try:
                    self._git_sparse_checkout(clean_repo, branch, module_path, module_tmp)
                    if os.path.exists(module_tmp) and os.listdir(module_tmp):
                        downloaded = True
                except Exception as git_err:
                    log.warning(f"[ModuleLoader] Git checkout fallito ({git_err}), provo download ZIP archivio...")

                # Metodo B: Download ZIP Fallback (se Git non disponibile o fallito)
                if not downloaded:
                    self._download_github_zip(clean_repo, branch, module_id, module_tmp)

                self._copy_module_from_dir(module_tmp, module_id)

        # 2.5 Installa dipendenze Python se presenti in requirements.txt
        self._install_python_dependencies(found_local if found_local else module_tmp, module_id)

        # 3. Rebuild frontend
        self._rebuild_frontend()

        # 4. Registra route e MCP a runtime
        self._unregister_module(module_id)
        prefix = f"core.modules.{module_id}"
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name, None)
        importlib.invalidate_caches()
        if not self._load_module(module_id, app):
            raise RuntimeError(f"Il modulo '{module_id}' non ha completato la registrazione.")

        # 5. Persisti stato
        self._set_state(module_id, True)

        log.info(f"[ModuleLoader] '{module_id}' installato con successo.")
        return {"success": True, "module_id": module_id, "rebuilt": True}

    def _copy_module_from_dir(self, source_dir: str, module_id: str) -> None:
        """Copia i file backend e frontend dalla cartella sorgente alle destinazioni di Sigma Studio."""
        backend_src = os.path.join(source_dir, "backend")
        frontend_src = os.path.join(source_dir, "frontend")

        # Se non esistono sottocartelle backend/frontend, usa la root per entrambe
        if not os.path.exists(backend_src) and not os.path.exists(frontend_src):
            backend_src = source_dir
            frontend_src = source_dir

        backend_dst = os.path.join(_CORE_MODULES_DIR, module_id)
        if os.path.exists(backend_dst):
            shutil.rmtree(backend_dst)
        if os.path.exists(backend_src):
            shutil.copytree(backend_src, backend_dst, ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules"))
            log.info(f"[ModuleLoader] Backend copiato in: {backend_dst}")

        # Copia file radice opzionali del modulo (manifest.json, requirements.txt, README.md)
        for root_file in ["manifest.json", "requirements.txt", "README.md"]:
            rf_src = os.path.join(source_dir, root_file)
            if os.path.exists(rf_src):
                shutil.copy2(rf_src, os.path.join(backend_dst, root_file))

        frontend_dst = os.path.join(_FRONTEND_MODULES_DIR, module_id)
        if os.path.exists(frontend_dst):
            shutil.rmtree(frontend_dst)
        if os.path.exists(frontend_src):
            shutil.copytree(frontend_src, frontend_dst, ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules"))
            log.info(f"[ModuleLoader] Frontend copiato in: {frontend_dst}")

    def _install_python_dependencies(self, source_dir: str, module_id: str) -> None:
        """Installa le dipendenze Python se presente requirements.txt nel modulo."""
        req_paths = [
            os.path.join(source_dir, "requirements.txt"),
            os.path.join(_CORE_MODULES_DIR, module_id, "requirements.txt"),
        ]
        found_req = None
        for p in req_paths:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                found_req = p
                break

        if not found_req:
            return

        log.info(f"[ModuleLoader] Trovato requirements.txt per '{module_id}', verifica dipendenze in corso...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", "-r", found_req, "--no-warn-script-location"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if res.returncode == 0:
                log.info(f"[ModuleLoader] Dipendenze Python per '{module_id}' verificate/installate con successo.")
            else:
                raise RuntimeError(f"Installazione dipendenze fallita: {(res.stderr or '')[-500:]}")
        except Exception as err:
            raise RuntimeError(f"Dipendenze del modulo '{module_id}' non disponibili: {err}") from err

    # ------------------------------------------------------------------
    # Uninstall
    # ------------------------------------------------------------------

    def uninstall(self, module_id: str) -> dict:
        with self._filesystem_transaction(module_id):
            return self._uninstall(module_id)

    def _uninstall(self, module_id: str) -> dict:
        """
        Disinstalla un modulo:
        1. Rimuove backend da core/modules/{module_id}/
        2. Rimuove frontend da sigma_studio/src/modules/{module_id}/
        3. npm run build
        4. Aggiorna stato
        """
        log.info(f"[ModuleLoader] Inizio disinstallazione '{module_id}'")

        # 1. Rimuovi backend
        backend_dst = os.path.join(_CORE_MODULES_DIR, module_id)
        if os.path.exists(backend_dst):
            shutil.rmtree(backend_dst)
            log.info(f"[ModuleLoader] Backend rimosso: {backend_dst}")

        # 2. Rimuovi frontend
        frontend_dst = os.path.join(_FRONTEND_MODULES_DIR, module_id)
        if os.path.exists(frontend_dst):
            shutil.rmtree(frontend_dst)
            log.info(f"[ModuleLoader] Frontend rimosso: {frontend_dst}")

        # 3. Rebuild frontend
        self._rebuild_frontend()

        self._unregister_module(module_id)

        # 4. Rimuovi dalla registry in-memory
        self._loaded.pop(module_id, None)

        # 5. Persisti stato
        self._set_state(module_id, False)

        log.info(f"[ModuleLoader] '{module_id}' disinstallato.")
        return {"success": True, "module_id": module_id, "rebuilt": True}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _import_backend(self, module_id: str):
        """Risolve il backend senza inizializzare l'applicazione HTTP."""
        import traceback
        self._validate_module_id(module_id)
        if _CORE_MODULES_DIR not in sys.path:
            sys.path.insert(0, os.path.dirname(_CORE_MODULES_DIR))
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)

        # Gli handler si trovano per convenzione, non per dichiarazione. Nei
        # manifest c'era un campo `backend.handlers_module` che nessuno leggeva:
        # in 7 moduli su 15 indicava un percorso che dal vivo non esiste, e
        # nessuno se n'era accorto proprio perche' non veniva letto. E' stato
        # tolto; se un giorno servira' davvero dichiararlo, va prima reso
        # l'unica sorgente di verita', non aggiunto accanto a questa lista.
        candidate_module_paths = [
            f"core.modules.{module_id}.handlers",
            f"core.modules.{module_id}.backend.handlers",
            f"core.modules.{module_id}",
        ]

        mod = None
        loaded_path = None
        for handler_module_path in candidate_module_paths:
            try:
                mod = importlib.import_module(handler_module_path)
                loaded_path = handler_module_path
                break
            except ModuleNotFoundError as mnfe:
                # Se il modulo mancante è proprio quello che stiamo provando a
                # importare, è normale: passiamo al candidato successivo.
                # Se è una dipendenza interna che manca, è un errore reale.
                missing_name = mnfe.name or ""
                if missing_name and not handler_module_path.startswith(missing_name) and \
                        not missing_name.startswith(handler_module_path.rsplit(".", 1)[0]):
                    log.error(
                        f"[ModuleLoader] Dipendenza mancante per '{module_id}' "
                        f"(import '{handler_module_path}'): {mnfe}\n"
                        f"{traceback.format_exc()}"
                    )
                    # Non continuare: il modulo è presente ma incompleto
                    break
                # Il percorso candidato non esiste su disco → proviamo il prossimo
                continue
            except Exception as e:
                log.error(
                    f"[ModuleLoader] Errore import '{handler_module_path}' per '{module_id}': "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                )
                # Errore reale (SyntaxError, ImportError su deps, ecc.): stop
                break

        if mod is None:
            log.warning(
                f"[ModuleLoader] Modulo '{module_id}' non caricato: "
                f"handler non trovati in {candidate_module_paths}"
            )
            return None

        return mod, loaded_path

    def _load_module(self, module_id: str, app: Any) -> bool:
        """Registra servizi, route e strumenti di un backend risolto."""
        import traceback
        backend = self._import_backend(module_id)
        if backend is None:
            return False
        mod, loaded_path = backend

        try:
            if app is None:
                try:
                    from core.fastapi_app import app as _fastapi_app
                    app = _fastapi_app
                except Exception:
                    app = None

            snapshot = self._runtime_snapshot(app)
            if hasattr(mod, "register_services"):
                from core import service_registry
                mod.register_services(service_registry)

            if hasattr(mod, "register_routes"):
                mod.register_routes(app)
                log.info(f"[ModuleLoader] '{module_id}' route registrate da {loaded_path}.")

            if hasattr(mod, "register_mcp"):
                try:
                    from core.mcp.mcp_hub import mcp_hub
                    mod.register_mcp(mcp_hub)
                    log.info(f"[ModuleLoader] '{module_id}' server MCP registrati da {loaded_path}.")
                except Exception as mcp_err:
                    raise RuntimeError(f"Registrazione MCP fallita: {mcp_err}") from mcp_err

            # I tool con cui un modulo fa lavorare un agente. Il kernel non li
            # elenca e non li conosce: li riceve da chi li possiede, e senza
            # questo hook un modulo installato resterebbe invisibile all'harness
            # — che e' lo stato in cui versava KiCad fino al 25 settembre 2026,
            # quando l'elenco dei suoi tool stava scritto in `tool_schema.py`.
            if hasattr(mod, "register_harness_tools"):
                try:
                    mod.register_harness_tools()
                    log.info(f"[ModuleLoader] '{module_id}' tool dell'harness registrati da {loaded_path}.")
                except Exception as tools_err:
                    raise RuntimeError(f"Registrazione tool fallita: {tools_err}") from tools_err

            self._loaded[module_id] = mod
            self._registrations[module_id] = self._runtime_additions(app, snapshot)
            return True
        except Exception as e:
            if "snapshot" in locals():
                self._restore_runtime(app, snapshot)
            log.error(
                f"[ModuleLoader] Errore register_routes/register_mcp per '{module_id}': "
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
            return False

    def _rebuild_frontend(self) -> None:
        """Esegue npm run build nella directory sigma_studio/."""
        log.info("[ModuleLoader] Avvio rebuild frontend...")
        is_win = sys.platform == "win32"
        cmd = ["npm.cmd" if is_win else "npm", "run", "build"]
        try:
            result = subprocess.run(
                cmd,
                cwd=_FRONTEND_DIR,
                capture_output=True,
                text=True,
                shell=is_win,
                timeout=120
            )
            if result.returncode == 0:
                log.info("[ModuleLoader] Frontend rebuild completato con successo.")
            else:
                raise RuntimeError(f"Build frontend fallita: {(result.stderr or '')[-500:]}")
        except Exception as err:
            raise RuntimeError(f"Frontend del modulo non compilato: {err}") from err

    def _git_sparse_checkout(self, repo_url: str, branch: str, module_path: str, dst: str) -> None:
        """Clona solo la sottocartella del modulo via sparse-checkout."""
        os.makedirs(dst, exist_ok=True)
        cmds = [
            ["git", "init"],
            ["git", "remote", "add", "origin", repo_url],
            ["git", "config", "core.sparseCheckout", "true"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, cwd=dst, check=True, capture_output=True, timeout=120)

        sparse_file = os.path.join(dst, ".git", "info", "sparse-checkout")
        os.makedirs(os.path.dirname(sparse_file), exist_ok=True)
        with open(sparse_file, "w", encoding="utf-8") as f:
            f.write(f"{module_path}/*\n")

        subprocess.run(
            ["git", "pull", "--depth=1", "origin", branch],
            cwd=dst, check=True, capture_output=True, timeout=180
        )

        module_subdir = os.path.join(dst, module_path)
        if os.path.exists(module_subdir):
            for item in os.listdir(module_subdir):
                shutil.move(os.path.join(module_subdir, item), dst)
            shutil.rmtree(os.path.join(dst, module_path.split("/")[0]), ignore_errors=True)

    def _download_github_zip(self, repo_url: str, branch: str, module_id: str, dst: str) -> None:
        """Scarica l'archivio ZIP da GitHub ed estrae la cartella del modulo."""
        # Da https://github.com/Sigmanih/SigmaStudio-Moduli.git a https://github.com/Sigmanih/SigmaStudio-Moduli/archive/refs/heads/main.zip
        clean_base = repo_url.replace(".git", "").rstrip("/")
        zip_url = f"{clean_base}/archive/refs/heads/{branch}.zip"
        log.info(f"[ModuleLoader] Download ZIP archivio: {zip_url}")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
            zip_path = tf.name

        try:
            req = urllib.request.Request(zip_url, headers={"User-Agent": "SigmaStudio/1.0"})
            with safe_urlopen(req, timeout=30) as resp, open(zip_path, "wb") as out_f:
                downloaded = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > 256 * 1024 * 1024:
                        raise ValueError("Archivio modulo oltre il limite di 256 MB.")
                    out_f.write(chunk)

            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.infolist()
                if len(members) > 20000 or sum(member.file_size for member in members) > 2 * 1024**3:
                    raise ValueError("Archivio modulo oltre il budget di estrazione.")
                # Cerca file che appartengono a modules/{module_id}
                prefix_to_find = f"modules/{module_id}/"
                extracted_any = False
                for member in members:
                    if prefix_to_find in member.filename:
                        # Estrai rimuovendo il prefisso fino a modules/{module_id}/
                        rel_path = member.filename.split(prefix_to_find, 1)[1]
                        if not rel_path:
                            continue
                        target_file = Path(dst).joinpath(rel_path.replace("\\", "/")).resolve()
                        if not target_file.is_relative_to(Path(dst).resolve()):
                            raise ValueError("Archivio modulo con percorso fuori destinazione.")
                        if (member.external_attr >> 16) & 0o170000 == 0o120000:
                            raise ValueError("Collegamento simbolico non ammesso nell'archivio.")
                        if member.is_dir():
                            os.makedirs(target_file, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_file), exist_ok=True)
                            with zf.open(member) as src, open(target_file, "wb") as dst_file:
                                shutil.copyfileobj(src, dst_file)
                        extracted_any = True

                if not extracted_any:
                    raise RuntimeError(f"Nessun file trovato nello ZIP per '{prefix_to_find}'")
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass

    def _read_state(self) -> dict:
        try:
            with open(_STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                raise ValueError("Lo stato dei moduli deve essere un oggetto JSON.")
            return {name: value for name, value in state.items()
                    if isinstance(name, str) and isinstance(value, bool)}
        except (OSError, ValueError) as exc:
            log.debug("Stato dei moduli non disponibile: %s", exc)
            return {}

    def _set_state(self, module_id: str, value: bool) -> None:
        state = self._read_state()
        state[module_id] = value
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        temporary = Path(_STATE_FILE).with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        temporary.replace(_STATE_FILE)

    def is_loaded(self, module_id: str) -> bool:
        return module_id in self._loaded

    def list_loaded(self) -> list[str]:
        return list(self._loaded.keys())

    def describe_modules(self) -> list[dict]:
        """Catalogo locale per la navigazione, senza contattare repository remoti."""
        state = self._read_state()
        result = []
        for index, manifest in enumerate(sorted(Path(_CORE_MODULES_DIR).glob("*/manifest.json"))):
            if index >= 128:
                break
            try:
                if manifest.stat().st_size > 65536:
                    raise ValueError("Manifest oltre il limite di 64 KB.")
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
                module_id = metadata.get("id", "")
                self._validate_module_id(module_id)
                if module_id != manifest.parent.name:
                    raise ValueError("Il manifest non corrisponde alla cartella.")
                entry = {key: metadata.get(key, "") for key in
                         ("id", "name", "category", "description", "tabType", "workDomain")}
                entry.update(installed=state.get(module_id, metadata.get("enabled_by_default")) is True,
                             available=module_id in self._loaded,
                             workspaceTabs=metadata.get("workspaceTabs", []))
                result.append(entry)
            except (OSError, ValueError, AttributeError) as exc:
                log.warning("Manifest ignorato %s: %s", manifest, exc)
        return result

