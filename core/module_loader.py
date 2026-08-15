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
from typing import Any

from core.logger import get_logger

log = get_logger(__name__)

# Paths risolti rispetto alla root del progetto
_ROOT = os.path.dirname(os.path.dirname(__file__))
_CORE_MODULES_DIR    = os.path.join(_ROOT, "core", "modules")
_FRONTEND_MODULES_DIR = os.path.join(_ROOT, "sigma_studio", "src", "modules")
_FRONTEND_DIR        = os.path.join(_ROOT, "sigma_studio")
_STATE_FILE          = os.path.join(_ROOT, "data", "marketplace_installed.json")


class ModuleLoader:
    """Gestisce il ciclo di vita dei moduli opzionali di Sigma Studio."""

    def __init__(self) -> None:
        self._loaded: dict[str, Any] = {}
        # Assicura che core/modules esista come package Python
        os.makedirs(_CORE_MODULES_DIR, exist_ok=True)
        init_file = os.path.join(_CORE_MODULES_DIR, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

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

    def install(self, module_id: str, repo_url: str, branch: str, module_path: str, app: Any) -> dict:
        """
        Installa un modulo da GitHub:
        1. git clone / sparse checkout della sottocartella
        2. pip install -r requirements.txt
        3. Copia backend → core/modules/{module_id}/
        4. Copia frontend → sigma_studio/src/modules/{module_id}/
        5. npm run build
        6. Registra route a runtime
        7. Persiste stato installato
        """
        import tempfile

        log.info(f"[ModuleLoader] Inizio installazione '{module_id}' da {repo_url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Clone sparse della sottocartella del modulo
            module_tmp = os.path.join(tmp_dir, module_id)
            self._git_sparse_checkout(repo_url, branch, module_path, module_tmp)

            # 2. pip install dipendenze specifiche del modulo
            req_file = os.path.join(module_tmp, "requirements.txt")
            if os.path.exists(req_file):
                log.info(f"[ModuleLoader] pip install -r {req_file}")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    log.warning(f"[ModuleLoader] pip warning: {result.stderr[:500]}")

            # 3. Copia backend
            backend_src = os.path.join(module_tmp, "backend")
            backend_dst = os.path.join(_CORE_MODULES_DIR, module_id)
            if os.path.exists(backend_dst):
                shutil.rmtree(backend_dst)
            if os.path.exists(backend_src):
                shutil.copytree(backend_src, backend_dst)
                log.info(f"[ModuleLoader] Backend copiato → {backend_dst}")

            # 4. Copia frontend
            frontend_src = os.path.join(module_tmp, "frontend")
            frontend_dst = os.path.join(_FRONTEND_MODULES_DIR, module_id)
            if os.path.exists(frontend_dst):
                shutil.rmtree(frontend_dst)
            if os.path.exists(frontend_src):
                shutil.copytree(frontend_src, frontend_dst)
                log.info(f"[ModuleLoader] Frontend copiato → {frontend_dst}")

        # 5. Rebuild frontend
        self._rebuild_frontend()

        # 6. Registra route a runtime
        self._load_module(module_id, app)

        # 7. Persisti stato
        self._set_state(module_id, True)

        log.info(f"[ModuleLoader] '{module_id}' installato con successo.")
        return {"success": True, "module_id": module_id, "rebuilt": True}

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

        # 3. Rebuild frontend (senza il modulo)
        self._rebuild_frontend()

        # 4. Rimuovi dalla registry in-memory
        # Nota: le route FastAPI rimangono fino al prossimo restart del server.
        # Le chiamate alle route con codice rimosso ritorneranno 500; accettabile.
        self._loaded.pop(module_id, None)

        # 5. Persisti stato
        self._set_state(module_id, False)

        log.info(f"[ModuleLoader] '{module_id}' disinstallato.")
        return {"success": True, "module_id": module_id, "rebuilt": True}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_module(self, module_id: str, app: Any) -> bool:
        """Importa dinamicamente gli handler del modulo e registra le route."""
        # Assicura che il path sia importabile
        if _CORE_MODULES_DIR not in sys.path:
            sys.path.insert(0, os.path.dirname(_CORE_MODULES_DIR))

        handler_module_path = f"core.modules.{module_id}.backend.handlers"
        try:
            # Force-reload se già importato (caso install runtime)
            if handler_module_path in sys.modules:
                importlib.reload(sys.modules[handler_module_path])
                mod = sys.modules[handler_module_path]
            else:
                mod = importlib.import_module(handler_module_path)

            if hasattr(mod, "register_routes"):
                mod.register_routes(app)
                self._loaded[module_id] = mod
                log.info(f"[ModuleLoader] '{module_id}' route registrate.")
                return True
            else:
                log.warning(f"[ModuleLoader] '{module_id}/handlers.py' non espone register_routes().")
                return False
        except ModuleNotFoundError:
            log.warning(f"[ModuleLoader] '{module_id}' non trovato su disco, skip.")
            return False
        except Exception as e:
            log.error(f"[ModuleLoader] Errore caricamento '{module_id}': {e}")
            return False

    def _rebuild_frontend(self) -> None:
        """Esegue npm run build nella directory sigma_studio/."""
        log.info("[ModuleLoader] Avvio rebuild frontend...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=_FRONTEND_DIR,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            log.info("[ModuleLoader] Frontend rebuild completato.")
        else:
            log.error(f"[ModuleLoader] Build fallita:\n{result.stderr[-1000:]}")
            raise RuntimeError(f"npm run build fallito: {result.stderr[-500:]}")

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

        # Scrivi sparse-checkout config
        sparse_file = os.path.join(dst, ".git", "info", "sparse-checkout")
        os.makedirs(os.path.dirname(sparse_file), exist_ok=True)
        with open(sparse_file, "w") as f:
            f.write(f"{module_path}/*\n")

        subprocess.run(
            ["git", "pull", "--depth=1", "origin", branch],
            cwd=dst, check=True, capture_output=True
        )

        # Sposta il contenuto della sottocartella nella root di dst
        module_subdir = os.path.join(dst, module_path)
        if os.path.exists(module_subdir):
            for item in os.listdir(module_subdir):
                shutil.move(os.path.join(module_subdir, item), dst)
            # Cleanup
            shutil.rmtree(os.path.join(dst, module_path.split("/")[0]), ignore_errors=True)

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
