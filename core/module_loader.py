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
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
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

    def __init__(self) -> None:
        self._loaded: dict[str, Any] = {}
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
        state = self._read_state()
        for module_id, installed in state.items():
            if installed:
                self._load_module(module_id, app)

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(self, module_id: str, repo_url: str = "", branch: str = "main", module_path: str = "", app: Any = None) -> dict:
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
        self._load_module(module_id, app)

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
            shutil.copytree(backend_src, backend_dst)
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
            shutil.copytree(frontend_src, frontend_dst)
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
                log.warning(f"[ModuleLoader] Avviso installazione dipendenze pip per '{module_id}': {res.stderr[:200] if res.stderr else ''}")
        except Exception as err:
            log.warning(f"[ModuleLoader] Impossibile verificare dipendenze pip per '{module_id}': {err}")

    # ------------------------------------------------------------------
    # Uninstall
    # ------------------------------------------------------------------

    def uninstall(self, module_id: str) -> dict:
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

        # 3.5 Rimuovi server MCP associati dall'Hub MCP
        try:
            from core.mcp.mcp_hub import mcp_hub
            mcp_hub.unregister_server(module_id)
        except Exception as mcp_err:
            log.warning(f"[ModuleLoader] Avviso rimozione MCP server per '{module_id}': {mcp_err}")

        # 4. Rimuovi dalla registry in-memory
        self._loaded.pop(module_id, None)

        # 5. Persisti stato
        self._set_state(module_id, False)

        log.info(f"[ModuleLoader] '{module_id}' disinstallato.")
        return {"success": True, "module_id": module_id, "rebuilt": True}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_module(self, module_id: str, app: Any) -> bool:
        """Importa dinamicamente gli handler del modulo e registra le route e i server MCP."""
        import traceback
        if _CORE_MODULES_DIR not in sys.path:
            sys.path.insert(0, os.path.dirname(_CORE_MODULES_DIR))
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)

        candidate_module_paths = [
            f"core.modules.{module_id}.handlers",
            f"core.modules.{module_id}.backend.handlers",
            f"core.modules.{module_id}",
        ]

        mod = None
        loaded_path = None
        for handler_module_path in candidate_module_paths:
            try:
                if handler_module_path in sys.modules:
                    mod = importlib.reload(sys.modules[handler_module_path])
                else:
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
            return False

        try:
            if hasattr(mod, "register_routes"):
                mod.register_routes(app)
                log.info(f"[ModuleLoader] '{module_id}' route registrate da {loaded_path}.")

            if hasattr(mod, "register_mcp"):
                try:
                    from core.mcp.mcp_hub import mcp_hub
                    mod.register_mcp(mcp_hub)
                    log.info(f"[ModuleLoader] '{module_id}' server MCP registrati da {loaded_path}.")
                except Exception as mcp_err:
                    log.warning(f"[ModuleLoader] Avviso registrazione MCP per '{module_id}': {mcp_err}")

            self._loaded[module_id] = mod
            return True
        except Exception as e:
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
                log.warning(f"[ModuleLoader] Build completata con avvisi: {result.stderr[-300:] if result.stderr else ''}")
        except Exception as err:
            log.warning(f"[ModuleLoader] Subprocess build notice: {err}")

    def _git_sparse_checkout(self, repo_url: str, branch: str, module_path: str, dst: str) -> None:
        """Clona solo la sottocartella del modulo via sparse-checkout."""
        os.makedirs(dst, exist_ok=True)
        cmds = [
            ["git", "init"],
            ["git", "remote", "add", "origin", repo_url],
            ["git", "config", "core.sparseCheckout", "true"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, cwd=dst, check=True, capture_output=True)

        sparse_file = os.path.join(dst, ".git", "info", "sparse-checkout")
        os.makedirs(os.path.dirname(sparse_file), exist_ok=True)
        with open(sparse_file, "w", encoding="utf-8") as f:
            f.write(f"{module_path}/*\n")

        subprocess.run(
            ["git", "pull", "--depth=1", "origin", branch],
            cwd=dst, check=True, capture_output=True
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
                shutil.copyfileobj(resp, out_f)

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Cerca file che appartengono a modules/{module_id}
                prefix_to_find = f"modules/{module_id}/"
                extracted_any = False
                for member in zf.infolist():
                    if prefix_to_find in member.filename:
                        # Estrai rimuovendo il prefisso fino a modules/{module_id}/
                        rel_path = member.filename.split(prefix_to_find, 1)[1]
                        if not rel_path:
                            continue
                        target_file = os.path.join(dst, rel_path)
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
                return json.load(f)
        except Exception:
            return {}

    def _set_state(self, module_id: str, value: bool) -> None:
        state = self._read_state()
        state[module_id] = value
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def is_loaded(self, module_id: str) -> bool:
        return module_id in self._loaded

    def list_loaded(self) -> list[str]:
        return list(self._loaded.keys())

