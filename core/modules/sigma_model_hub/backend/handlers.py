# ==============================================================================
# core/modules/sigma_model_hub/backend/handlers.py
# HTTP Route Handlers for Hugging Face Model Hub & SigmaEngine Deployment
# ==============================================================================
from __future__ import annotations
import os
import json
import urllib.parse
from core.logger import get_logger
from .hf_client import (search_hf_models, get_hf_model_details, get_effective_hf_token,
                        persist_hf_token, resolve_hf_token)
from .downloader_engine import downloader_manager, DEFAULT_MODELS_DIR
from .model_inventory import (scan_local_models, deploy_model_to_sigma_engine,
                            unload_sigma_engine_model, delete_local_model)

log = get_logger(__name__)

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
_CONFIG_PATH = os.path.join(_ROOT_DIR, "data", "model_hub_config.json")


def _load_hub_config() -> dict:
    from .hf_client import get_effective_hf_token
    cfg = {
        "models_dir": DEFAULT_MODELS_DIR,
        "hf_token": "",
        "auto_deploy_on_download": True,
        "preferred_quantization": "Q4_K_M"
    }
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception:
            pass

    # If hf_token is empty in config, check env vars or cached token
    if not cfg.get("hf_token"):
        effective = get_effective_hf_token()
        if effective:
            cfg["hf_token"] = effective

    return cfg


def _save_hub_config(cfg: dict) -> dict:
    existing = _load_hub_config()
    if isinstance(cfg, dict):
        existing.update(cfg)
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    return existing


def handle_models_hf_search(self):
    """GET /api/models/hf/search — Cerca modelli su Hugging Face con filtri multi-dimensionali e paginazione."""
    try:
        query = ""
        category = "all"
        size_bracket = "all"
        param_bracket = "all"
        format_filter = "all"
        sort = "downloads"
        official_only = False
        cursor = None
        page = 1
        limit = 30

        # Parse query params if available
        if hasattr(self, 'path') and '?' in self.path:
            qs = self.path.split('?', 1)[1]
            params = urllib.parse.parse_qs(qs)
            query = params.get('q', [''])[0]
            category = params.get('category', ['all'])[0]
            size_bracket = params.get('size_bracket', ['all'])[0]
            param_bracket = params.get('param_bracket', ['all'])[0]
            format_filter = params.get('format_filter', ['all'])[0]
            quant_filter = params.get('quant_filter', ['all'])[0]
            sort = params.get('sort', ['downloads'])[0]
            official_only = params.get('official_only', ['false'])[0].lower() in ['true', '1', 'yes']
            cursor = params.get('cursor', [''])[0] or None
            page = int(params.get('page', ['1'])[0])
            limit = int(params.get('limit', ['30'])[0])

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None
        data = search_hf_models(
            query=query,
            category=category,
            size_bracket=size_bracket,
            param_bracket=param_bracket,
            format_filter=format_filter,
            quant_filter=quant_filter,
            sort=sort,
            official_only=official_only,
            cursor=cursor,
            page=page,
            limit=limit,
            hf_token=token
        )

        self.send_json_response({
            "success": True,
            "results": data.get("results", []),
            "total": data.get("total", 0),
            "page": page,
            "next_cursor": data.get("next_cursor"),
            "has_more": data.get("has_more", False)
        })

    except Exception as e:
        log.error("Error in handle_models_hf_search: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)




def handle_models_hf_details(self):
    """GET /api/models/hf/details — Restituisce dettagli e lista file del modello HF."""
    try:
        model_id = ""
        if hasattr(self, 'path') and '?' in self.path:
            qs = self.path.split('?', 1)[1]
            params = urllib.parse.parse_qs(qs)
            model_id = params.get('model_id', [''])[0]

        if not model_id:
            self.send_json_response({"success": False, "error": "model_id mancante"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None
        data = get_hf_model_details(model_id=model_id, hf_token=token)
        self.send_json_response(data)
    except Exception as e:
        log.error("Error in handle_models_hf_details: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_start(self):
    """POST /api/models/hf/download/start — Avvia download in background."""
    try:
        body = self.read_json_body()
        model_id = body.get("model_id")
        filename = body.get("filename")
        download_url = body.get("download_url")

        if not model_id or not filename:
            self.send_json_response({"success": False, "error": "model_id e filename obbligatori"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None

        task = downloader_manager.start_download(
            model_id=model_id,
            filename=filename,
            download_url=download_url,
            hf_token=token
        )
        self.send_json_response({"success": True, "task": task})
    except Exception as e:
        log.error("Error in handle_models_hf_download_start: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_repo(self):
    """POST /api/models/hf/download/repo — Scarica l'intero modello con tutti i suoi file e shard."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model_id = body.get("model_id")
        files = body.get("files")

        if not model_id:
            self.send_json_response({"success": False, "error": "model_id obbligatorio"}, 400)
            return

        cfg = _load_hub_config()
        token = cfg.get("hf_token") or None

        task = downloader_manager.start_repo_download(
            model_id=model_id,
            files_list=files,
            hf_token=token
        )
        self.send_json_response({"success": True, "task": task})
    except Exception as e:
        log.error("Error in handle_models_hf_download_repo: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)



def handle_models_hf_downloads_list(self):
    """GET /api/models/hf/downloads — Restituisce tutti i download attivi e completati."""
    try:
        tasks = downloader_manager.get_tasks()
        self.send_json_response({"success": True, "downloads": tasks})
    except Exception as e:
        log.error("Error in handle_models_hf_downloads_list: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_cancel(self):
    """POST /api/models/hf/download/cancel — Annulla un download attivo."""
    try:
        body = self.read_json_body()
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = downloader_manager.cancel_download(task_id)
        self.send_json_response({"success": success, "message": f"Task {task_id} annullato." if success else "Task non trovato o già terminato."})
    except Exception as e:
        log.error("Error in handle_models_hf_download_cancel: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_retry(self):
    """POST /api/models/hf/download/retry — Riprende/Riprova un download interrotto o fallito."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        task = downloader_manager.retry_download(task_id)
        if task:
            self.send_json_response({"success": True, "task": task, "message": f"Download #{task_id} ripreso con successo."})
        else:
            self.send_json_response({"success": False, "error": f"Task #{task_id} non trovato."}, 404)
    except Exception as e:
        log.error("Error in handle_models_hf_download_retry: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_download_remove(self):
    """POST /api/models/hf/download/remove — Rimuove un task completato o fallito dalla lista."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        task_id = body.get("task_id")
        if not task_id:
            self.send_json_response({"success": False, "error": "task_id mancante"}, 400)
            return

        success = downloader_manager.remove_task(task_id)
        self.send_json_response({"success": success, "message": f"Task #{task_id} rimosso." if success else "Task non trovato."})
    except Exception as e:
        log.error("Error in handle_models_hf_download_remove: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)



def handle_models_local_list(self):
    """GET /api/models/local/list — Restituisce elenco modelli scaricati in locale."""
    try:
        cfg = _load_hub_config()
        custom_dir = cfg.get("models_dir")
        models = scan_local_models(custom_dir=custom_dir)
        self.send_json_response({"success": True, "models": models})
    except Exception as e:
        log.error("Error in handle_models_local_list: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_local_delete(self):
    """POST /api/models/local/delete — Elimina un modello scaricato dallo storage locale."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model_path = body.get("model_path") or body.get("path") or body.get("model_id") or body.get("filename")
        if not model_path:
            self.send_json_response({"success": False, "error": "model_path o model_id mancante"}, 400)
            return

        cfg = _load_hub_config()
        custom_dir = cfg.get("models_dir")
        res = delete_local_model(model_path, custom_dir=custom_dir)
        status_code = 200 if res.get("success") else 400
        self.send_json_response(res, status_code)
    except Exception as e:
        log.error("Error in handle_models_local_delete: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_engine_load(self):
    """POST /api/models/engine/load — Carica e attiva il modello in SigmaEngine."""
    try:
        body = self.read_json_body()
        path = body.get("model_path")
        quant = body.get("quantization")

        if not path:
            self.send_json_response({"success": False, "error": "model_path obbligatorio"}, 400)
            return

        res = deploy_model_to_sigma_engine(model_path=path, quantization=quant)
        self.send_json_response(res)
    except Exception as e:
        log.error("Error in handle_models_engine_load: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_engine_unload(self):
    """POST /api/models/engine/unload — Scarica il modello attivo da SigmaEngine."""
    try:
        res = unload_sigma_engine_model()
        self.send_json_response(res)
    except Exception as e:
        log.error("Error in handle_models_engine_unload: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_config_get(self):
    """GET /api/models/config — Restituisce impostazioni del Model Hub e stato del token HF."""
    try:
        from .hf_client import resolve_hf_token

        cfg = _load_hub_config()
        resolved = resolve_hf_token()
        self.send_json_response({
            "success": True,
            "config": cfg,
            # The tab is the only place the token is managed, so it also has to
            # show where an already-active token is coming from: an env var or
            # a huggingface-cli login is not editable from here.
            "hf_has_token": bool(resolved["token"]),
            "hf_token_source": resolved["source"],
            "hf_token_source_detail": resolved["detail"],
        })
    except Exception as e:
        log.error("Error in handle_models_config_get: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_config_save(self):
    """POST /api/models/config — Salva impostazioni del Model Hub e aggiorna i token attivi."""
    try:
        from core.model_paths import models_dir, set_models_dir

        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        if not isinstance(body, dict):
            body = {}

        saved_cfg = _save_hub_config(body)

        # Update models_dir
        new_dir = body.get("models_dir")
        if new_dir:
            resolved_dir = set_models_dir(new_dir)
            downloader_manager.set_models_dir(resolved_dir)

        # A single write path for the token: environment, every config file that
        # is read back on resolution, and the downloads already in flight, so an
        # interrupted gated download retries with the new token straight away.
        hf_token = (body.get("hf_token") or "").strip() if "hf_token" in body else (saved_cfg.get("hf_token") or "").strip()
        persist_hf_token(hf_token)
        saved_cfg["hf_token"] = hf_token

        resolved = resolve_hf_token()
        self.send_json_response({
            "success": True,
            "message": "Impostazioni e Token salvati con successo.",
            "config": saved_cfg,
            "hf_has_token": bool(resolved["token"]),
            "hf_token_source": resolved["source"],
            "hf_token_source_detail": resolved["detail"],
            "active_models_dir": models_dir(),
        })
    except Exception as e:
        log.error("Error in handle_models_config_save: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_hf_test_connection(self):
    """GET/POST /api/models/hf/test-connection — Esegue test completo di connettività verso Hugging Face e verifica token."""
    import time
    import json
    import urllib.request
    import urllib.error

    body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
    if not isinstance(body, dict):
        body = {}
    # A GET carries no body: fall back to the token already configured, so the
    # header pill can test the connection without the settings tab being open.
    token = (body.get("hf_token") or "").strip()
    if not token:
        token = (get_effective_hf_token() or "").strip()

    t_start = time.time()
    reachability_ok = False
    latency_ms = 0
    token_valid = False
    user_info = {}
    error_detail = None

    # 1. Test basic reachability to Hugging Face API
    try:
        req = urllib.request.Request("https://huggingface.co/api/models?limit=1")
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                reachability_ok = True
                latency_ms = round((time.time() - t_start) * 1000, 1)
    except Exception as ex:
        error_detail = f"Impossibile raggiungere i server Hugging Face: {ex}"

    if not reachability_ok:
        self.send_json_response({
            "success": False,
            "connected": False,
            "latency_ms": None,
            "token_valid": False,
            "error": error_detail or "Connessione a Hugging Face fallita. Controlla la connessione internet.",
            "message": "❌ Hugging Face non raggiungibile."
        })
        return

    # 2. Test token if present
    if token:
        try:
            req_auth = urllib.request.Request("https://huggingface.co/api/whoami-v2")
            req_auth.add_header("Authorization", f"Bearer {token}")
            req_auth.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
            with urllib.request.urlopen(req_auth, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    token_valid = True
                    user_info = {
                        "username": data.get("name") or data.get("fullname") or "Utente HF",
                        "email": data.get("email") or "",
                        "type": data.get("type") or "user",
                        "orgs": [o.get("name") for o in data.get("orgs", []) if o.get("name")]
                    }
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                error_detail = "Token Hugging Face non valido o revocato (HTTP 401 Unauthorized)."
            else:
                error_detail = f"Errore verifica token: HTTP {http_err.code}"
        except Exception as ex:
            error_detail = f"Errore verifica token: {ex}"
    else:
        error_detail = "Nessun token configurato (download anonimo con velocità ridotta ~50KB/s e senza accesso a modelli Gated come Llama)."

    msg = f"✅ Connessione a Hugging Face attiva ({latency_ms}ms)."
    if token_valid:
        msg += f" Autenticato come @{user_info.get('username')}."
    else:
        msg += f" {error_detail}"

    self.send_json_response({
        "success": True,
        "connected": True,
        "latency_ms": latency_ms,
        "token_valid": token_valid,
        "token_configured": bool(token),
        "user_info": user_info,
        "error": error_detail if not token_valid else None,
        "message": msg
    })


def handle_models_hf_token_test(self):
    """POST /api/models/hf/token/test — Verifica la validità del token Hugging Face contattando l'API ufficiale."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        token = (body.get("hf_token") or "").strip()
        if not token:
            from .hf_client import get_effective_hf_token
            token = get_effective_hf_token() or ""

        if not token:
            self.send_json_response({"success": False, "error": "Nessun token inserito da verificare."}, 400)
            return

        import urllib.request
        import json
        req = urllib.request.Request("https://huggingface.co/api/whoami-v2")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    username = data.get("name") or data.get("fullname") or "Utente HF"
                    email = data.get("email") or ""
                    auth_type = data.get("type") or "user"
                    orgs = [o.get("name") for o in data.get("orgs", []) if o.get("name")]
                    self.send_json_response({
                        "success": True,
                        "valid": True,
                        "username": username,
                        "email": email,
                        "type": auth_type,
                        "orgs": orgs,
                        "message": f"✅ Token Hugging Face valido! Autenticato come @{username}."
                    })
                else:
                    self.send_json_response({
                        "success": False,
                        "valid": False,
                        "error": f"Risposta inattesa da Hugging Face: HTTP {resp.status}"
                    }, 400)
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                self.send_json_response({
                    "success": False,
                    "valid": False,
                    "error": "❌ Token non valido o revocato (HTTP 401 Unauthorized). Verifica di aver copiato l'intero token 'hf_...' da huggingface.co/settings/tokens"
                }, 200)
            else:
                self.send_json_response({
                    "success": False,
                    "valid": False,
                    "error": f"Errore server Hugging Face: HTTP {http_err.code}"
                }, 200)
    except Exception as e:
        log.error("Error in handle_models_hf_token_test: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


# ---------------------------------------------------------------- conversion

def handle_models_convert_info(self):
    """GET /api/models/convert/info — Modelli convertibili, tipi e stato tooling."""
    try:
        from core.engine.gguf_converter import GgufConverter
        self.send_json_response({
            "success": True,
            "models": GgufConverter.convertible_models(),
            "quantization_types": GgufConverter.quantization_types(),
            "tooling": GgufConverter.converter_status(),
            "jobs": GgufConverter.jobs(),
        })
    except Exception as e:
        log.error("Error in handle_models_convert_info: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_convert_tooling(self):
    """POST /api/models/convert/tooling — Scarica lo script di conversione."""
    try:
        from core.engine.gguf_converter import GgufConverter
        res = GgufConverter.fetch_converter()
        self.send_json_response(res, 200 if res.get("success") else 502)
    except Exception as e:
        log.error("Error in handle_models_convert_tooling: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_convert_start(self):
    """POST /api/models/convert/start — Avvia la conversione in GGUF."""
    try:
        from core.engine.gguf_converter import GgufConverter
        body = self.read_json_body() if hasattr(self, "read_json_body") else {}
        res = GgufConverter.start(
            model_name=body.get("model"),
            quantization=body.get("quantization", "Q4_K_M"),
        )
        self.send_json_response(res, 200 if res.get("success") else 400)
    except Exception as e:
        log.error("Error in handle_models_convert_start: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_convert_jobs(self):
    """GET /api/models/convert/jobs — Stato delle conversioni."""
    try:
        from core.engine.gguf_converter import GgufConverter
        self.send_json_response({"success": True, "jobs": GgufConverter.jobs()})
    except Exception as e:
        log.error("Error in handle_models_convert_jobs: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_browse_dirs(self):
    """
    GET /api/models/browse — Lists subdirectories, for picking a models folder.

    A server-side browser rather than a file input: the browser only ever hands
    back a relative name for a chosen directory, and the path this setting needs
    is an absolute one on the machine running the engine.
    """
    try:
        from urllib.parse import urlparse, parse_qs
        from core.model_paths import models_dir

        query = parse_qs(urlparse(self.path).query)
        requested = (query.get("path", [""])[0] or "").strip()

        if not requested:
            current = models_dir()
            base = os.path.dirname(current) or current
        else:
            base = os.path.abspath(requested)

        if not os.path.isdir(base):
            self.send_json_response(
                {"success": False, "error": f"Non e' una cartella: {base}"}, 400)
            return

        entries = []
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            if not os.path.isdir(full) or name.startswith("."):
                continue
            entries.append({
                "name": name, "path": full, "has_models": _holds_models(full),
            })

        parent = os.path.dirname(base.rstrip(os.sep))
        self.send_json_response({
            "success": True,
            "current": base,
            "parent": parent if parent and parent != base else None,
            "entries": entries,
            "roots": _list_drive_roots(),
        })
    except Exception as e:
        log.error("Error in handle_models_browse_dirs: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def _holds_models(folder: str) -> bool:
    """
    Whether a folder is, or contains, model weights.

    A models directory holds one subfolder per model rather than loose weight
    files, so checking only its own contents marks the very folder the user is
    looking for as empty.
    """
    suffixes = (".safetensors", ".gguf", ".bin")
    try:
        names = os.listdir(folder)
    except Exception:
        return False

    if any(n.endswith(suffixes) for n in names):
        return True

    for name in names[:60]:          # one level down is enough, and bounded
        child = os.path.join(folder, name)
        if not os.path.isdir(child):
            continue
        try:
            if any(n.endswith(suffixes) for n in os.listdir(child)):
                return True
        except Exception:
            continue
    return False


def _list_drive_roots():
    """Mount points to jump to, so the user is not stuck below one root."""
    try:
        import psutil
        return [
            p.mountpoint for p in psutil.disk_partitions(all=False)
            if os.path.isdir(p.mountpoint)
        ]
    except Exception:
        return []


def register_routes(app=None) -> None:
    """Registra tutte le route HTTP di Model Hub su FastAPI / Handler Adapter."""
    get_routes = {
        '/api/models/hf/search': handle_models_hf_search,
        '/api/models/hf/details': handle_models_hf_details,
        '/api/models/hf/downloads': handle_models_hf_downloads_list,
        '/api/models/hf/test-connection': handle_models_hf_test_connection,
        '/api/models/local/list': handle_models_local_list,
        '/api/models/config': handle_models_config_get,
        '/api/models/convert/info': handle_models_convert_info,
        '/api/models/convert/jobs': handle_models_convert_jobs,
        '/api/models/browse': handle_models_browse_dirs,
    }

    post_routes = {
        '/api/models/hf/download/start': handle_models_hf_download_start,
        '/api/models/hf/download/repo': handle_models_hf_download_repo,
        '/api/models/hf/download/cancel': handle_models_hf_download_cancel,
        '/api/models/hf/download/retry': handle_models_hf_download_retry,
        '/api/models/hf/download/remove': handle_models_hf_download_remove,
        '/api/models/hf/token/test': handle_models_hf_token_test,
        '/api/models/hf/test-connection': handle_models_hf_test_connection,
        '/api/models/local/delete': handle_models_local_delete,
        '/api/models/delete': handle_models_local_delete,
        '/api/models/engine/load': handle_models_engine_load,
        '/api/models/engine/unload': handle_models_engine_unload,
        '/api/models/config': handle_models_config_save,
        '/api/models/convert/start': handle_models_convert_start,
        '/api/models/convert/tooling': handle_models_convert_tooling,
    }

    try:
        from core.fastapi_app import FastAPIHandlerAdapter
        for path, fn in get_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._GET_HANDLERS[path] = fn.__name__
        for path, fn in post_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._POST_HANDLERS[path] = fn.__name__
        log.info('[sigma_model_hub] 10 Route Model Hub registrate su FastAPIHandlerAdapter.')
    except Exception as e:
        log.warning(f'[sigma_model_hub] Avviso binding FastAPIHandlerAdapter: {e}')


def register_mcp(mcp_hub) -> None:
    """Registra il server MCP di Model Hub nell'hub MCP del kernel."""
    try:
        from .mcp_server import ModelHubMCPServer
        mcp_hub.register_server(ModelHubMCPServer)
        log.info('[sigma_model_hub] Model Hub MCP Server registrato con successo.')
    except Exception as e:
        log.warning(f'[sigma_model_hub] Model Hub MCP Server non registrato: {e}')
