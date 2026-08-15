# ==============================================================================
# core/modules/sigma_model_hub/backend/handlers.py
# HTTP Route Handlers for Hugging Face Model Hub & SigmaEngine Deployment
# ==============================================================================
from __future__ import annotations
import os
import json
import urllib.parse
from core.logger import get_logger
from .hf_client import search_hf_models, get_hf_model_details
from .downloader_engine import downloader_manager, DEFAULT_MODELS_DIR
from .model_inventory import scan_local_models, deploy_model_to_sigma_engine, unload_sigma_engine_model

log = get_logger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "model_hub_config.json")


def _load_hub_config() -> dict:
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "models_dir": DEFAULT_MODELS_DIR,
        "hf_token": "",
        "auto_deploy_on_download": True,
        "preferred_quantization": "Q4_K_M"
    }


def _save_hub_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


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
    """GET /api/models/config — Restituisce impostazioni del Model Hub."""
    try:
        cfg = _load_hub_config()
        self.send_json_response({"success": True, "config": cfg})
    except Exception as e:
        log.error("Error in handle_models_config_get: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_models_config_save(self):
    """POST /api/models/config — Salva impostazioni del Model Hub."""
    try:
        body = self.read_json_body()
        _save_hub_config(body)
        self.send_json_response({"success": True, "message": "Impostazioni salvate con successo.", "config": body})
    except Exception as e:
        log.error("Error in handle_models_config_save: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def register_routes(app=None) -> None:
    """Registra tutte le route HTTP di Model Hub su FastAPI / Handler Adapter."""
    get_routes = {
        '/api/models/hf/search': handle_models_hf_search,
        '/api/models/hf/details': handle_models_hf_details,
        '/api/models/hf/downloads': handle_models_hf_downloads_list,
        '/api/models/local/list': handle_models_local_list,
        '/api/models/config': handle_models_config_get,
    }

    post_routes = {
        '/api/models/hf/download/start': handle_models_hf_download_start,
        '/api/models/hf/download/cancel': handle_models_hf_download_cancel,
        '/api/models/engine/load': handle_models_engine_load,
        '/api/models/engine/unload': handle_models_engine_unload,
        '/api/models/config': handle_models_config_save,
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
