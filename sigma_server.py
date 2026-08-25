# ==============================================================================
# SIGMA SERVER | Unified Research Environment
# Backend orchestrator for Sigma Studio v6.2 — modular refactored.
# ==============================================================================

import os
import hashlib
import subprocess
import mimetypes
import signal
import sys
import shutil
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", message=".*expandable_segments.*")
warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
warnings.filterwarnings("ignore", message=".*weight_norm is deprecated.*")
warnings.filterwarnings("ignore", message=".*Redirects are currently not supported.*")

# --- Core modules ---
from core import paths
from core.logger import get_logger
# L'ambiente virtuale serve all'agente per eseguire codice: la verifica
# vive con la sandbox che quel codice lo esegue.
from core.sandbox_manager import ensure_venv

log = get_logger("server")

# --- MIME types ---
mimetypes.add_type(".js", "application/javascript")
mimetypes.add_type(".css", "text/css")
mimetypes.add_type(".svg", "image/svg+xml")
mimetypes.add_type(".md", "text/markdown")


# ==============================================================================
# Perche' qui non c'e' piu' un server HTTP
#
# Fino a poco fa questo file conteneva una seconda pipeline completa: una
# sottoclasse di SimpleHTTPRequestHandler con 121 handler montati sopra a mano,
# uno per uno, e la tabella delle rotte registrata su di essa. Era la copia
# gemella di quella che core/fastapi_app.py monta sul suo adapter.
#
# Non veniva mai istanziata: nessuno costruiva il ThreadedHTTPServer, il
# processo e' sempre partito con uvicorn su core.fastapi_app:app. Erano
# duecentosettanta righe di codice morto che pero' andavano tenute allineate a
# mano, e che allineate non erano: due handler di sistema esistevano solo qui e
# rispondevano 404 sul server vero, handle_router_train era scritto due volte
# in due file, e la suite del Training Lab falliva da tempo proprio su questa
# divergenza.
#
# Ora la pipeline e' una sola. Questo file fa quello che il suo nome promette:
# prepara l'ambiente e avvia il server.
# ==============================================================================



# ==============================================================================
# Startup helpers
# ==============================================================================

def _hash_dir(path: str) -> str:
    """Compute a quick SHA-1 fingerprint of all source files in *path*."""
    h = hashlib.sha1()
    for root, _, files in os.walk(path):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "rb") as fh:
                    h.update(fh.read())
            except OSError:
                pass
    return h.hexdigest()


def _needs_frontend_rebuild() -> bool:
    """Return True if the frontend source has changed since the last build."""
    src_dir = str(paths.frontend_src_dir())
    dist_dir = str(paths.frontend_dist_dir())
    stamp_file = str(paths.frontend_build_stamp())

    if not os.path.isdir(dist_dir):
        return True

    current_hash = _hash_dir(src_dir)
    if os.path.exists(stamp_file):
        try:
            with open(stamp_file, "r") as fh:
                if fh.read().strip() == current_hash:
                    return False
        except OSError:
            pass
    return True


def _write_build_stamp() -> None:
    src_dir = str(paths.frontend_src_dir())
    stamp_file = str(paths.frontend_build_stamp())
    try:
        with open(stamp_file, "w") as fh:
            fh.write(_hash_dir(src_dir))
    except OSError:
        pass


def _init_manifesti() -> None:
    """Ensure the manifesti/ directory exists (default manifestos are already stored here)."""
    manifesti_dir = "manifesti"

    if not os.path.exists(manifesti_dir):
        try:
            os.makedirs(manifesti_dir)
            log.info("Created directory %s/", manifesti_dir)
        except OSError as exc:
            log.error("Failed to create directory %s: %s", manifesti_dir, exc)


from core.data_handler import rebuild_modules_meta as _rebuild_modules_meta


def _apply_hardware_env():
    """
    Apply device visibility, threading and credentials for this process.

    Delegated to core.runtime_env so that every entry point gets the same
    environment: this one, `uvicorn core.fastapi_app:app`, and anything the
    launcher spawns. It used to live here, which meant the settings existed
    only when the server was started through this exact file.
    """
    try:
        from core.runtime_env import apply_hardware_env
        applied = apply_hardware_env()
        log.info(
            "Ambiente hardware applicato: %s",
            ", ".join(f"{k}={v}" for k, v in applied.items()) or "nessuna modifica",
        )
    except Exception as exc:
        log.warning("Could not apply hardware env: %s", exc)


def graceful_shutdown(signum, frame):
    log.info("Ricevuto segnale di arresto. Disconnessione e stacco di tutti i task in corso...")
    try:
        from core.system_cleanup import shutdown_all_tasks
        shutdown_all_tasks()
    except Exception as exc:
        log.warning("Errore durante shutdown dei task: %s", exc)
    log.info("Server arrestato correttamente.")
    sys.exit(0)


# ==============================================================================
# STARTUP
# ==============================================================================
# La sequenza sta in una funzione, non dentro `if __name__ == "__main__"`, per
# un motivo preciso: un blocco __main__ non viene mai importato, quindi non
# viene mai esercitato. Un nome rimasto senza import li' dentro non lo scopre
# nessun test e nessun import — lo scopre l'utente, all'avvio, con un
# NameError. E' successo con `ensure_venv` dopo la rimozione della pipeline
# legacy. `--check` esegue tutta la preparazione e si ferma prima di servire.

def prepare_environment() -> dict:
    """Prepara l'ambiente: hardware, manifesti, indice, venv, frontend."""
    esiti: dict = {}

    _apply_hardware_env()
    _init_manifesti()
    _rebuild_modules_meta()

    try:
        from core.router_trainer import ensure_sigma_router_model, generate_routing_dataset
        ensure_sigma_router_model()
        generate_routing_dataset()
        esiti["router"] = True
    except Exception as exc:
        log.warning("Router model initialization skipped: %s", exc)
        esiti["router"] = False

    log.info("Checking virtual environment...")
    venv_ok, venv_msg = ensure_venv()
    log.info(venv_msg)
    esiti["venv"] = venv_ok

    esiti["frontend"] = _build_frontend_if_needed()
    return esiti


def _build_frontend_if_needed() -> bool:
    """Ricompila il frontend solo se i sorgenti sono cambiati."""
    npm_path = shutil.which("npm")
    if not npm_path:
        log.warning("npm not found — skipping frontend build.")
        return False

    if not _needs_frontend_rebuild():
        log.info("Frontend source unchanged — skipping build.")
        return True

    log.info("Frontend source changed — rebuilding...")
    res = subprocess.run(
        [npm_path, "run", "build"],
        cwd=str(paths.frontend_dir()),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        log.error("Frontend build failed:\n%s", res.stderr)
        return False

    _write_build_stamp()
    log.info("Frontend built successfully.")
    return True


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Avvia il server ASGI."""
    log.info("Listening on http://localhost:%d (FastAPI ASGI v8.0)", port)
    log.info("Interactive OpenAPI Docs available at http://localhost:%d/docs", port)
    try:
        import uvicorn
        from core.fastapi_app import app
        # timeout_graceful_shutdown=1 chiude subito le connessioni keep-alive
        # inattive del browser quando si preme Ctrl+C.
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            timeout_graceful_shutdown=1,
            timeout_keep_alive=5,
        )
    except (KeyboardInterrupt, SystemExit):
        log.info("Server arrestato correttamente.")


def main(argv: list[str] | None = None) -> int:
    argomenti = list(sys.argv[1:] if argv is None else argv)
    solo_verifica = "--check" in argomenti

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    esiti = prepare_environment()

    if solo_verifica:
        log.info("Verifica completata: %s", esiti)
        return 0

    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
