# ==============================================================================
# SIGMA SERVER | Unified Research Environment
# Backend orchestrator for Sigma Studio v6.2 — modular refactored.
# ==============================================================================

import os
import json
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

# ==============================================================================
# Verifica delle dipendenze, prima di tutto il resto
#
# Questo file puo' essere lanciato direttamente — a mano, da un servizio, da un
# .bat scritto male — e in quel caso l'ambiente puo' essere vuoto. Senza questo
# controllo l'avvio proseguiva comunque: il router segnalava "No module named
# 'requests'", la preparazione "No module named 'psutil'", il frontend falliva
# con "vite non e' riconosciuto", e solo alla fine il processo moriva su
# `import uvicorn`. Quattro sintomi diversi di un unico fatto — le dipendenze
# non erano installate — e nessuno dei quattro che lo dicesse.
# ==============================================================================

#: Modulo -> a cosa serve. Se manca uno di questi, il server non parte comunque.
_DIPENDENZE_ESSENZIALI = (
    ("uvicorn", "il server ASGI che serve l'applicazione"),
    ("fastapi", "le rotte HTTP"),
    ("requests", "le chiamate ai provider e al Model Hub"),
    ("psutil", "il rilevamento dell'hardware"),
)


def _dipendenze_mancanti() -> list[tuple[str, str]]:
    import importlib.util

    mancanti = []
    for modulo, motivo in _DIPENDENZE_ESSENZIALI:
        try:
            if importlib.util.find_spec(modulo) is None:
                mancanti.append((modulo, motivo))
        except Exception:
            mancanti.append((modulo, motivo))
    return mancanti


def _spiega_ambiente_incompleto(mancanti: list[tuple[str, str]]) -> str:
    elenco = "\n".join(f"    - {modulo}: {motivo}" for modulo, motivo in mancanti)
    avvio = "sigma_studio.bat" if os.name == "nt" else "./sigma_studio.sh"
    return (
        "\n  L'ambiente Python non e' completo. Mancano:\n\n"
        f"{elenco}\n\n"
        f"  Avvia Sigma Studio con `{avvio}`: installa cio' che serve e poi\n"
        "  parte da solo. Per reinstallare tutto da capo:\n\n"
        f"      {avvio} --install\n"
    )


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

def prepare_environment(solo_verifica: bool = False) -> dict:
    """Prepara l'ambiente: hardware, manifesti, indice, venv, frontend, runtime.

    Con solo_verifica non scarica niente: riferisce e basta.
    """
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

    # Runtime GGUF e modello di partenza, in quest'ordine: scaricare prima il
    # modello vorrebbe dire far scaricare mezzo giga a una macchina che poi non
    # riesce a eseguirlo. In modalita' --check non si scarica niente e si dice
    # soltanto a che punto e' l'installazione.
    try:
        from core.first_run import prepare as _primo_avvio
        esiti["primo_avvio"] = _primo_avvio(
            progress=lambda t: log.info(t), scarica=not solo_verifica)
    except Exception as exc:
        log.warning("Preparazione del primo avvio saltata: %s", exc)
        esiti["primo_avvio"] = {"errore": str(exc)}

    return esiti


def _build_frontend_if_needed() -> bool:
    """Ricompila il frontend solo se i sorgenti sono cambiati."""
    npm_path = shutil.which("npm") or (shutil.which("npm.cmd") if os.name == "nt" else None)
    if not npm_path:
        log.warning("npm non trovato: build del frontend saltata. Se in "
                    "sigma_studio/dist c'e' gia' un'interfaccia compilata "
                    "viene servita quella.")
        return False

    if not _needs_frontend_rebuild():
        log.info("Frontend source unchanged — skipping build.")
        return True

    # Le dipendenze del frontend prima del comando che le usa. Senza, `npm run
    # build` fallisce con "vite non e' riconosciuto come comando interno o
    # esterno": un messaggio che nomina lo strumento e non la causa, ed e' la
    # riga che su una copia appena clonata mandava fuori strada.
    frontend = str(paths.frontend_dir())
    if not os.path.isdir(os.path.join(frontend, "node_modules")):
        log.info("Dipendenze del frontend assenti: le installo (solo la prima volta)...")
        installa = subprocess.run(
            [npm_path, "install"], cwd=frontend,
            capture_output=True, text=True, shell=(os.name == "nt"),
        )
        if installa.returncode != 0:
            log.error("npm install non riuscito:\n%s", (installa.stderr or "")[-1500:])
            return False

    log.info("Frontend source changed — rebuilding...")
    res = subprocess.run(
        [npm_path, "run", "build"],
        cwd=frontend,
        capture_output=True,
        text=True,
        shell=(os.name == "nt"),
    )
    if res.returncode != 0:
        log.error("Build del frontend non riuscita:\n%s", (res.stderr or "")[-1500:])
        return False

    _write_build_stamp()
    log.info("Frontend built successfully.")
    return True


def _get_configured_host_port_ssl() -> tuple[str, int, bool, str | None, str | None]:
    """Recupera host, porta e configurazione SSL da config.json / provider.json."""
    host = "0.0.0.0"
    port = 8000
    ssl_enabled = False
    ssl_certfile = None
    ssl_keyfile = None
    try:
        from core.paths import provider_config_file, project_root
        cfg_files = [provider_config_file(), project_root() / "config.json"]

        for cfg_path in cfg_files:
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ai_data = data.get("ai", {}) if isinstance(data.get("ai"), dict) else {}
                p = (data.get("provider_server_port") or data.get("server_port") or
                     ai_data.get("provider_server_port") or ai_data.get("server_port"))
                if p:
                    port = int(p)
                h = (data.get("provider_server_host") or data.get("server_host") or
                     ai_data.get("provider_server_host") or ai_data.get("server_host"))
                if h:
                    host = str(h)
                ssl_on = data.get("ssl_enabled") if "ssl_enabled" in data else ai_data.get("ssl_enabled")
                if ssl_on is not None:
                    ssl_enabled = bool(ssl_on)
                cert = data.get("ssl_certfile") or ai_data.get("ssl_certfile")
                if cert:
                    ssl_certfile = str(cert)
                key = data.get("ssl_keyfile") or ai_data.get("ssl_keyfile")
                if key:
                    ssl_keyfile = str(key)
    except Exception as exc:
        log.warning("Impossibile leggere configurazione porta/host/ssl: %s", exc)
    return host, port, ssl_enabled, ssl_certfile, ssl_keyfile


def serve(host: str | None = None, port: int | None = None, ssl: bool | None = None) -> None:
    """Avvia il server ASGI su host e porta specificati o configurati, con supporto opzionale HTTPS."""
    cfg_host, cfg_port, cfg_ssl, cfg_cert, cfg_key = _get_configured_host_port_ssl()
    final_host = host if host is not None else cfg_host
    final_port = port if port is not None else cfg_port
    final_ssl = ssl if ssl is not None else cfg_ssl

    from core.ssl_manager import get_lan_ip, ensure_ssl_certificates
    lan_ip = get_lan_ip()

    ssl_key_path = None
    ssl_cert_path = None
    scheme = "http"

    if final_ssl:
        cert_p, key_p = ensure_ssl_certificates(cfg_cert, cfg_key)
        if cert_p and key_p and cert_p.exists() and key_p.exists():
            ssl_cert_path = str(cert_p)
            ssl_key_path = str(key_p)
            scheme = "https"
            log.info("[SSL] Modalita' HTTPS (TLS/SSL) abilitata con successo.")
        else:
            log.warning("[SSL] Impossibile abilitare HTTPS: certificati non generati. Avvio in HTTP standard.")

    log.info("Listening on %s://localhost:%d (FastAPI ASGI v8.0)", scheme, final_port)
    if final_host in ("0.0.0.0", "") and lan_ip != "127.0.0.1":
        log.info("Wi-Fi & LAN Network access available at %s://%s:%d", scheme, lan_ip, final_port)
    log.info("Interactive OpenAPI Docs available at %s://localhost:%d/docs", scheme, final_port)

    try:
        import uvicorn
        from core.fastapi_app import app
        # timeout_graceful_shutdown=1 chiude subito le connessioni keep-alive
        # inattive del browser quando si preme Ctrl+C.
        uvicorn_kwargs = {
            "app": app,
            "host": final_host,
            "port": final_port,
            "log_level": "info",
            "timeout_graceful_shutdown": 1,
            "timeout_keep_alive": 5,
        }
        if ssl_cert_path and ssl_key_path:
            uvicorn_kwargs["ssl_certfile"] = ssl_cert_path
            uvicorn_kwargs["ssl_keyfile"] = ssl_key_path

        uvicorn.run(**uvicorn_kwargs)
    except (KeyboardInterrupt, SystemExit):
        log.info("Server arrestato correttamente.")


def main(argv: list[str] | None = None) -> int:
    argomenti = list(sys.argv[1:] if argv is None else argv)
    solo_verifica = "--check" in argomenti

    # CLI flag overrides
    enable_ssl = None
    if "--https" in argomenti or "--ssl" in argomenti:
        enable_ssl = True
    elif "--http" in argomenti or "--no-ssl" in argomenti:
        enable_ssl = False

    custom_port = None
    for i, arg in enumerate(argomenti):
        if (arg == "--port" or arg == "-p") and i + 1 < len(argomenti):
            try:
                custom_port = int(argomenti[i + 1])
            except ValueError:
                pass

    custom_host = None
    for i, arg in enumerate(argomenti):
        if (arg == "--host" or arg == "-h") and i + 1 < len(argomenti):
            custom_host = argomenti[i + 1]

    mancanti = _dipendenze_mancanti()
    if mancanti:
        # Prima di ogni altra cosa e senza traccia di stack: qui non c'e' un
        # difetto da diagnosticare, c'e' un passaggio di installazione saltato.
        print(_spiega_ambiente_incompleto(mancanti), file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    esiti = prepare_environment(solo_verifica=solo_verifica)

    if solo_verifica:
        log.info("Verifica completata: %s", esiti)
        return 0

    if custom_host is None and custom_port is None and enable_ssl is None:
        serve()
    else:
        serve(host=custom_host, port=custom_port, ssl=enable_ssl)
    return 0




if __name__ == "__main__":
    sys.exit(main())
