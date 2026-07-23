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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

# --- Core modules ---
from core.logger import get_logger
from core.sandbox import is_path_allowed
from core.store import modules_store, tasks_store
from core.api_router import register_get_handlers, register_post_handlers, route_get, route_post

log = get_logger("server")

# --- MIME types ---
mimetypes.add_type(".js", "application/javascript")
mimetypes.add_type(".css", "text/css")
mimetypes.add_type(".svg", "image/svg+xml")
mimetypes.add_type(".md", "text/markdown")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class SigmaAPIHandler(SimpleHTTPRequestHandler):
    """Lightweight HTTP handler — routes to modular core/ handlers."""

    # Sandbox
    _is_path_allowed = staticmethod(is_path_allowed)

    def do_GET(self):
        route_get(self)

    def do_POST(self):
        route_post(self)

    def do_DELETE(self):
        route_delete(self)

    def do_PATCH(self):
        route_patch(self)

    # --- Helpers ---

    def get_module_meta(self) -> dict:
        """Return modules_meta via the thread-safe store."""
        return modules_store.load()

    def save_module_meta(self, meta: dict) -> None:
        """Persist modules_meta via the thread-safe store."""
        modules_store.save(meta)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

    def send_json_response(self, data: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def serve_static_file(self, file_path: str) -> None:
        try:
            with open(file_path, "rb") as fh:
                content = fh.read()
            self.send_response(200)
            mime, _ = mimetypes.guess_type(file_path)
            self.send_header("Content-Type", mime or "text/plain")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            self.send_error(500, f"Server Error: {exc!s}")

    def log_message(self, fmt, *args):
        """Route HTTP access logs through the structured logger."""
        log.debug(fmt, *args)


# ==============================================================================
# Register all external handlers via import
# ==============================================================================

# 1. Data handlers (modules, topics, knowledge DB, manifesti)
from core.data_handler import (
    handle_api_modules, handle_api_topics, handle_knowledge_db, handle_list_manifesti,
    handle_update_manifesto_image, handle_upload_agent_image
)
SigmaAPIHandler.handle_api_modules = handle_api_modules
SigmaAPIHandler.handle_api_topics = handle_api_topics
SigmaAPIHandler.handle_knowledge_db = handle_knowledge_db
SigmaAPIHandler.handle_list_manifesti = handle_list_manifesti
SigmaAPIHandler.handle_update_manifesto_image = handle_update_manifesto_image
SigmaAPIHandler.handle_upload_agent_image = handle_upload_agent_image



# 2. Module and Topic CRUD
from core.module_handler import (
    handle_create_topic, handle_update_topic, handle_delete_topic,
    handle_create_module, handle_delete_module, handle_update_module
)
SigmaAPIHandler.handle_create_topic = handle_create_topic
SigmaAPIHandler.handle_update_topic = handle_update_topic
SigmaAPIHandler.handle_delete_topic = handle_delete_topic
SigmaAPIHandler.handle_create_module = handle_create_module
SigmaAPIHandler.handle_delete_module = handle_delete_module
SigmaAPIHandler.handle_update_module = handle_update_module

# 3. File CRUD
from core.file_handler import (
    handle_get_file, handle_create_file, handle_delete_file,
    handle_upload_file, handle_run_test, handle_api_action,
    handle_rename_file, handle_api_rollback
)
SigmaAPIHandler.handle_get_file = handle_get_file
SigmaAPIHandler.handle_create_file = handle_create_file
SigmaAPIHandler.handle_delete_file = handle_delete_file
SigmaAPIHandler.handle_upload_file = handle_upload_file
SigmaAPIHandler.handle_run_test = handle_run_test
SigmaAPIHandler.handle_api_action = handle_api_action
SigmaAPIHandler.handle_rename_file = handle_rename_file
SigmaAPIHandler.handle_api_rollback = handle_api_rollback

# 4. Task handlers
from core.task_handler import (
    handle_api_tasks_get, handle_api_tasks_post,
    handle_api_tasks_by_agent, handle_api_tasks_assign
)
SigmaAPIHandler.handle_api_tasks_get = handle_api_tasks_get
SigmaAPIHandler.handle_api_tasks_post = handle_api_tasks_post
SigmaAPIHandler.handle_api_tasks_by_agent = handle_api_tasks_by_agent
SigmaAPIHandler.handle_api_tasks_assign = handle_api_tasks_assign

# 5. Config handlers
from core.config_handler import (
    handle_api_config_get, handle_api_config_post,
    handle_api_ollama_models, handle_api_create_model
)
SigmaAPIHandler.handle_api_config_get = handle_api_config_get
SigmaAPIHandler.handle_api_config_post = handle_api_config_post
SigmaAPIHandler.handle_api_ollama_models = handle_api_ollama_models
SigmaAPIHandler.handle_api_create_model = handle_api_create_model

# 6. Chat handler
from core.chat_handler import handle_chat
SigmaAPIHandler.handle_chat = handle_chat

# 7. Loop handler (task-driven autonomous loop)
from core.loop_handler import handle_chat_loop
SigmaAPIHandler.handle_chat_loop = handle_chat_loop

# 8. Execute handler (continuous feedback loop — Cline-style)
from core.execute_loop import handle_chat_execute
SigmaAPIHandler.handle_chat_execute = handle_chat_execute

# 9. Plan handler (Plan → Act workflow)
from core.plan_handler import handle_chat_plan, handle_chat_execute_plan
SigmaAPIHandler.handle_chat_plan = handle_chat_plan
SigmaAPIHandler.handle_chat_execute_plan = handle_chat_execute_plan

# 10. Sandbox manager (virtual environments, npm, pip, isolated projects)
from core.sandbox_manager import (
    handle_sandbox_create, handle_sandbox_run, handle_sandbox_install,
    handle_sandbox_list, handle_sandbox_destroy, ensure_venv, ensure_npm
)
SigmaAPIHandler.handle_sandbox_create = handle_sandbox_create
SigmaAPIHandler.handle_sandbox_run = handle_sandbox_run
SigmaAPIHandler.handle_sandbox_install = handle_sandbox_install
SigmaAPIHandler.handle_sandbox_list = handle_sandbox_list
SigmaAPIHandler.handle_sandbox_destroy = handle_sandbox_destroy

# 11. Agent registry
from core.agent_registry import (
    handle_agents_list, handle_agents_get, handle_agents_register,
    handle_agents_update, handle_agents_for_topic, handle_agents_colors,
)
SigmaAPIHandler.handle_agents_list = handle_agents_list
SigmaAPIHandler.handle_agents_get = handle_agents_get
SigmaAPIHandler.handle_agents_register = handle_agents_register
SigmaAPIHandler.handle_agents_update = handle_agents_update
SigmaAPIHandler.handle_agents_for_topic = handle_agents_for_topic
SigmaAPIHandler.handle_agents_colors = handle_agents_colors

# 12. Agent orchestrator (multi-agent collaboration)
from core.agent_orchestrator import handle_chat_orchestrate
SigmaAPIHandler.handle_chat_orchestrate = handle_chat_orchestrate

# 13. Agent templates (scaffolding new agents)
from core.agent_templates import handle_agents_templates, handle_agents_create
SigmaAPIHandler.handle_agents_templates = handle_agents_templates
SigmaAPIHandler.handle_agents_create = handle_agents_create

# 14. Pipeline engine (DAG pipeline execution with feedback loops)
from core.pipeline_engine import handle_pipeline_start, handle_pipeline_status, handle_pipeline_stop
SigmaAPIHandler.handle_pipeline_start = handle_pipeline_start
SigmaAPIHandler.handle_pipeline_status = handle_pipeline_status
SigmaAPIHandler.handle_pipeline_stop = handle_pipeline_stop

# 15. Context Broker (SQLite shared context between agents)
from core.context_broker import (
    handle_context_share, handle_context_get, handle_context_chat_log, handle_chat_message_save
)
SigmaAPIHandler.handle_context_share = handle_context_share
SigmaAPIHandler.handle_context_get = handle_context_get
SigmaAPIHandler.handle_context_chat_log = handle_context_chat_log
SigmaAPIHandler.handle_chat_message_save = handle_chat_message_save

# 16. Research Sessions (multi-session research with micro-objectives)
from core.research_sessions import (
    handle_research_create, handle_research_list, handle_research_status,
    handle_research_delete, handle_research_update_objective,
    handle_research_chat_history, handle_research_update_agents,
)
SigmaAPIHandler.handle_research_create = handle_research_create
SigmaAPIHandler.handle_research_list = handle_research_list
SigmaAPIHandler.handle_research_status = handle_research_status
SigmaAPIHandler.handle_research_delete = handle_research_delete
SigmaAPIHandler.handle_research_update_objective = handle_research_update_objective
SigmaAPIHandler.handle_research_update_agents = handle_research_update_agents
SigmaAPIHandler.handle_research_chat_history = handle_research_chat_history

# 17. Research Decompose + Next Steps (Agent Orchestrator v2)
from core.agent_orchestrator import (
    handle_research_decompose, handle_research_next_steps, handle_research_start
)
SigmaAPIHandler.handle_research_decompose = handle_research_decompose
SigmaAPIHandler.handle_research_next_steps = handle_research_next_steps
SigmaAPIHandler.handle_research_start = handle_research_start

# 18. Training Lab (LLM training, fine-tuning, dataset management)
from core.training_handler import (
    search_hf_datasets, get_hf_dataset_info,
    import_local_dataset, register_hf_dataset, list_datasets, delete_dataset,
    create_training_job, start_training_job, stop_training_job,
    get_job_status, get_job_logs, list_jobs, delete_job, clear_job_logs,
    export_to_ollama, get_hardware_info, get_featured_datasets,
    check_training_dependencies,
)
import json as _json_mod
from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs

def _handle_training_list_datasets(self):
    self.send_json_response(list_datasets())
SigmaAPIHandler.handle_training_list_datasets = _handle_training_list_datasets

def _handle_training_dataset_search(self):
    parsed = _urlparse(self.path)
    qs = _parse_qs(parsed.query)
    query = qs.get("q", [""])[0] or qs.get("query", [""])[0]
    limit = int(qs.get("limit", ["20"])[0])
    self.send_json_response(search_hf_datasets(query, limit=limit))
SigmaAPIHandler.handle_training_dataset_search = _handle_training_dataset_search

def _handle_training_featured_datasets(self):
    self.send_json_response(get_featured_datasets())
SigmaAPIHandler.handle_training_featured_datasets = _handle_training_featured_datasets

def _handle_training_hardware(self):
    self.send_json_response(get_hardware_info())
SigmaAPIHandler.handle_training_hardware = _handle_training_hardware

def _handle_training_list_jobs(self):
    self.send_json_response(list_jobs())
SigmaAPIHandler.handle_training_list_jobs = _handle_training_list_jobs

def _handle_training_job_status(self):
    parsed = _urlparse(self.path)
    qs = _parse_qs(parsed.query)
    job_id = qs.get("job_id", [""])[0]
    self.send_json_response(get_job_status(job_id))
SigmaAPIHandler.handle_training_job_status = _handle_training_job_status

def _handle_training_job_logs(self):
    parsed = _urlparse(self.path)
    qs = _parse_qs(parsed.query)
    job_id = qs.get("job_id", [""])[0]
    offset = int(qs.get("offset", ["0"])[0])
    self.send_json_response(get_job_logs(job_id, offset=offset))
SigmaAPIHandler.handle_training_job_logs = _handle_training_job_logs

def _handle_training_dataset_import(self):
    body = self.read_json_body()
    result = import_local_dataset(
        body.get("path", ""), body.get("name"), body.get("format")
    )
    self.send_json_response(result)
SigmaAPIHandler.handle_training_dataset_import = _handle_training_dataset_import

def _handle_training_dataset_register_hf(self):
    body = self.read_json_body()
    result = register_hf_dataset(body.get("dataset_id", ""), body.get("split", "train"))
    self.send_json_response(result)
SigmaAPIHandler.handle_training_dataset_register_hf = _handle_training_dataset_register_hf

def _handle_training_dataset_delete(self):
    body = self.read_json_body()
    self.send_json_response(delete_dataset(body.get("dataset_id", "")))
SigmaAPIHandler.handle_training_dataset_delete = _handle_training_dataset_delete

def _handle_training_job_create(self):
    body = self.read_json_body()
    self.send_json_response(create_training_job(body))
SigmaAPIHandler.handle_training_job_create = _handle_training_job_create

def _handle_training_job_start(self):
    body = self.read_json_body()
    self.send_json_response(start_training_job(body.get("job_id", "")))
SigmaAPIHandler.handle_training_job_start = _handle_training_job_start

def _handle_training_job_stop(self):
    body = self.read_json_body()
    self.send_json_response(stop_training_job(body.get("job_id", "")))
SigmaAPIHandler.handle_training_job_stop = _handle_training_job_stop

def _handle_training_job_delete(self):
    body = self.read_json_body()
    self.send_json_response(delete_job(body.get("job_id", "")))
SigmaAPIHandler.handle_training_job_delete = _handle_training_job_delete

def _handle_training_export_ollama(self):
    body = self.read_json_body()
    self.send_json_response(export_to_ollama(
        body.get("job_id", ""), body.get("model_name", ""), body.get("system_prompt", "")
    ))
SigmaAPIHandler.handle_training_export_ollama = _handle_training_export_ollama

def _handle_training_dependencies(self):
    body = self.read_json_body()
    self.send_json_response(check_training_dependencies(body.get("method", "")))
SigmaAPIHandler.handle_training_dependencies = _handle_training_dependencies

def _handle_training_clear_logs(self):
    body = self.read_json_body()
    self.send_json_response(clear_job_logs(body.get("job_id", "")))
SigmaAPIHandler.handle_training_clear_logs = _handle_training_clear_logs

def _handle_hardware_status(self):
    from core.training_handler import get_hardware_info
    hw_res = get_hardware_info()
    cfg = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    hw_config = cfg.get("hardware", {
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "0,1"),
        "ollama_num_parallel": int(os.environ.get("OLLAMA_NUM_PARALLEL", 4)),
        "ollama_max_loaded_models": int(os.environ.get("OLLAMA_MAX_LOADED_MODELS", 2)),
        "num_gpu_layers": -1,
        "preferred_training_gpu": "cuda:0",
        "fp16_enabled": True,
    })
    hf_token = cfg.get("hf_token", "")
    masked_token = hf_token[:8] + "..." if len(hf_token) > 8 else ""
    env_status = {
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0,1"),
        "OLLAMA_NUM_PARALLEL": os.environ.get("OLLAMA_NUM_PARALLEL", "4"),
        "OLLAMA_MAX_LOADED_MODELS": os.environ.get("OLLAMA_MAX_LOADED_MODELS", "2"),
        "HF_TOKEN": masked_token,
        "HF_HAS_TOKEN": bool(hf_token),
    }
    self.send_json_response({
        "success": True,
        "hardware": hw_res.get("hardware", {}),
        "config": hw_config,
        "env": env_status,
        "hf_token": masked_token,
        "hf_has_token": bool(hf_token),
    })
SigmaAPIHandler.handle_hardware_status = _handle_hardware_status

def _handle_hardware_config(self):
    body = self.read_json_body()
    cfg = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    hw_cfg = cfg.get("hardware", {})
    hw_cfg.update({
        "cuda_visible_devices": body.get("cuda_visible_devices", "0,1"),
        "ollama_num_parallel": int(body.get("ollama_num_parallel", 4)),
        "ollama_max_loaded_models": int(body.get("ollama_max_loaded_models", 2)),
        "num_gpu_layers": int(body.get("num_gpu_layers", -1)),
        "preferred_training_gpu": body.get("preferred_training_gpu", "cuda:0"),
        "fp16_enabled": bool(body.get("fp16_enabled", True)),
    })
    cfg["hardware"] = hw_cfg
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as exc:
        return self.send_json_response({"success": False, "error": str(exc)}, 500)

    # Apply environment variables
    os.environ["CUDA_VISIBLE_DEVICES"] = hw_cfg["cuda_visible_devices"]
    os.environ["OLLAMA_NUM_PARALLEL"] = str(hw_cfg["ollama_num_parallel"])
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = str(hw_cfg["ollama_max_loaded_models"])
    
    self.send_json_response({"success": True, "config": hw_cfg})
SigmaAPIHandler.handle_hardware_config = _handle_hardware_config

def _handle_hardware_restart_ollama(self):
    from core.training_handler import restart_ollama_service
    res = restart_ollama_service()
    self.send_json_response(res)
SigmaAPIHandler.handle_hardware_restart_ollama = _handle_hardware_restart_ollama

def handle_router_train(self):
    """API Endpoint to rebuild the sigma-router model and generate training dataset."""
    try:
        from core.router_trainer import ensure_sigma_router_model, generate_routing_dataset
        dataset_count = generate_routing_dataset()
        model_ok = ensure_sigma_router_model()
        return self.send_json_response({
            "success": True,
            "message": f"Modello router 'sigma-router' inizializzato con successo. Generati {dataset_count} esempi nel dataset.",
            "dataset_path": "data/router_dataset.jsonl",
            "model": "sigma-router",
            "status": "ready"
        })
    except Exception as exc:
        return self.send_json_response({"success": False, "error": str(exc)}, status=500)

SigmaAPIHandler.handle_router_train = handle_router_train

def _handle_hf_token_config(self):
    """Salva HF_TOKEN nella config e lo imposta come variabile d'ambiente."""
    body = self.read_json_body()
    token = body.get("hf_token", "")
    cfg = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg["hf_token"] = token
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACE_TOKEN"] = token
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        masked = token[:8] + "..." if len(token) > 8 else ""
        return self.send_json_response({"success": True, "hf_token": masked, "hf_has_token": bool(token)})
    except Exception as exc:
        return self.send_json_response({"success": False, "error": str(exc)}, 500)
SigmaAPIHandler.handle_hf_token_config = _handle_hf_token_config

# --- Register routing tables ---
register_get_handlers(SigmaAPIHandler)
register_post_handlers(SigmaAPIHandler)

# --- Stub DELETE/PATCH routers (future RESTful endpoints) ---
from core.api_router import route_delete, route_patch


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
    src_dir = os.path.join("sigma_studio", "src")
    dist_dir = os.path.join("sigma_studio", "dist")
    stamp_file = os.path.join("sigma_studio", ".build_stamp")

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
    src_dir = os.path.join("sigma_studio", "src")
    stamp_file = os.path.join("sigma_studio", ".build_stamp")
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
    """Apply multi-GPU hardware + high-performance execution variables at startup."""
    try:
        cfg = {}
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        
        hw = cfg.get("hardware", {})
        devices = hw.get("cuda_visible_devices", "0,1")
        num_parallel = str(hw.get("ollama_num_parallel", 4))
        max_loaded = str(hw.get("ollama_max_loaded_models", 2))
        
        # 1. Multi-GPU & Ollama Concurrency Optimization
        os.environ["CUDA_VISIBLE_DEVICES"] = devices
        os.environ["OLLAMA_NUM_PARALLEL"] = num_parallel
        os.environ["OLLAMA_MAX_LOADED_MODELS"] = max_loaded
        os.environ["OLLAMA_FLASH_ATTENTION"] = "1"
        os.environ["OLLAMA_KEEP_ALIVE"] = "24h"
        
        # 2. PyTorch & CUDA Memory Allocation Optimization
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        
        # 3. CPU Core Multi-threading Optimization (12 physical cores)
        os.environ["OMP_NUM_THREADS"] = "12"
        os.environ["MKL_NUM_THREADS"] = "12"
        
        log.info("⚡ Hardware Acceleration active: GPUs=%s | Parallel Slots=%s | FlashAttention=1 | VRAM Warm Cache=24h | CPU Threads=12",
                 devices, num_parallel)
        
        # 4. Apply HF_TOKEN if present
        hf_token = cfg.get("hf_token", "")
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            os.environ["HUGGINGFACE_TOKEN"] = hf_token
            log.info("HF_TOKEN loaded from config (masked: %s...)", hf_token[:8] if len(hf_token) > 8 else "")
    except Exception as exc:
        log.warning("Could not apply hardware env: %s", exc)


def graceful_shutdown(signum, frame):
    log.info("Shutting down gracefully...")
    sys.exit(0)


# ==============================================================================
# STARTUP
# ==============================================================================

if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Apply Multi-GPU Environment
    _apply_hardware_env()

    # 0. Ensure default manifestos are copied
    _init_manifesti()

    # 1. Rebuild modules_meta.json from filesystem
    _rebuild_modules_meta()

    # 1b. Initialize Dedicated LLM Router Model and Dataset
    try:
        from core.router_trainer import ensure_sigma_router_model, generate_routing_dataset
        ensure_sigma_router_model()
        generate_routing_dataset()
    except Exception as exc:
        log.warning("Router model initialization skipped: %s", exc)


    # 2. Ensure virtual environment exists (for AI terminal access)
    log.info("Checking virtual environment...")
    venv_ok, venv_msg = ensure_venv()
    log.info(venv_msg)

    # 3. Conditional frontend build (skip if source unchanged)
    npm_path = shutil.which("npm")
    if npm_path:
        if _needs_frontend_rebuild():
            log.info("Frontend source changed — rebuilding...")
            res = subprocess.run(
                [npm_path, "run", "build"],
                cwd="sigma_studio",
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                _write_build_stamp()
                log.info("Frontend built successfully.")
            else:
                log.error("Frontend build failed:\n%s", res.stderr)
        else:
            log.info("Frontend source unchanged — skipping build.")
    else:
        log.warning("npm not found — skipping frontend build.")

    log.info("Listening on http://localhost:8000")
    try:
        ThreadedHTTPServer(("", 8000), SigmaAPIHandler).serve_forever()
    except KeyboardInterrupt:
        graceful_shutdown(None, None)