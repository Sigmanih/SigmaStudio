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
    handle_update_manifesto_image, handle_upload_agent_image, handle_upload_user_avatar,
    handle_manifesti_hub, handle_manifesti_install_from_hub, handle_manifesti_uninstall
)
SigmaAPIHandler.handle_api_modules = handle_api_modules
SigmaAPIHandler.handle_api_topics = handle_api_topics
SigmaAPIHandler.handle_knowledge_db = handle_knowledge_db
SigmaAPIHandler.handle_list_manifesti = handle_list_manifesti
SigmaAPIHandler.handle_update_manifesto_image = handle_update_manifesto_image
SigmaAPIHandler.handle_upload_agent_image = handle_upload_agent_image
SigmaAPIHandler.handle_upload_user_avatar = handle_upload_user_avatar
SigmaAPIHandler.handle_manifesti_hub = handle_manifesti_hub
SigmaAPIHandler.handle_manifesti_install_from_hub = handle_manifesti_install_from_hub
SigmaAPIHandler.handle_manifesti_uninstall = handle_manifesti_uninstall

from core.tts_handler import handle_tts_engines, handle_tts_speak
SigmaAPIHandler.handle_tts_engines = handle_tts_engines
SigmaAPIHandler.handle_tts_speak = handle_tts_speak

from core.mcp_handler import (
    handle_mcp_servers, handle_mcp_tools, handle_mcp_resources, handle_mcp_rpc,
    handle_mcp_policy,
    handle_mcp_integration,
    handle_mcp_test_integration,
    handle_mcp_external_add,
    handle_mcp_external_remove,
    handle_mcp_external_connect,
    handle_mcp_pending,
    handle_mcp_approve,
)
SigmaAPIHandler.handle_mcp_servers = handle_mcp_servers
SigmaAPIHandler.handle_mcp_tools = handle_mcp_tools
SigmaAPIHandler.handle_mcp_resources = handle_mcp_resources
SigmaAPIHandler.handle_mcp_rpc = handle_mcp_rpc
SigmaAPIHandler.handle_mcp_policy = handle_mcp_policy
SigmaAPIHandler.handle_mcp_integration = handle_mcp_integration
SigmaAPIHandler.handle_mcp_test_integration = handle_mcp_test_integration
SigmaAPIHandler.handle_mcp_external_add = handle_mcp_external_add
SigmaAPIHandler.handle_mcp_external_remove = handle_mcp_external_remove
SigmaAPIHandler.handle_mcp_external_connect = handle_mcp_external_connect
SigmaAPIHandler.handle_mcp_pending = handle_mcp_pending
SigmaAPIHandler.handle_mcp_approve = handle_mcp_approve

from core.swarm_handler import (
    handle_swarm_agents, handle_swarm_plan, handle_swarm_execute
)
SigmaAPIHandler.handle_swarm_agents = handle_swarm_agents
SigmaAPIHandler.handle_swarm_plan = handle_swarm_plan
SigmaAPIHandler.handle_swarm_execute = handle_swarm_execute




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


def handle_router_train(self):
    """API Endpoint to rebuild the sigma-router model and generate training dataset."""
    try:
        from core.router_trainer import ensure_sigma_router_model, generate_routing_dataset
        dataset_count = generate_routing_dataset()
        model_ok = ensure_sigma_router_model()
        return self.send_json_response({
            "success": True,
            "message": f"Modello router 'sigma-router' inizializzato con successo. Generati {dataset_count} esempi nel dataset.",
            "dataset_path": "training/datasets/router_dataset.jsonl",
            "model": "sigma-router",
            "status": "ready"
        })
    except Exception as exc:
        return self.send_json_response({"success": False, "error": str(exc)}, status=500)

SigmaAPIHandler.handle_router_train = handle_router_train

# 19. Skills & Marketplace Handlers
from core.integrations.handlers import (
    handle_skills_list, handle_skills_toggle, handle_apps_status,
    handle_apps_launch, handle_apps_autoconfigure,
    handle_marketplace_modules, handle_marketplace_install, handle_marketplace_uninstall, handle_marketplace_rebuild,
    handle_audio_studio_status, handle_audio_studio_stations
)
SigmaAPIHandler.handle_skills_list = handle_skills_list
SigmaAPIHandler.handle_skills_toggle = handle_skills_toggle
SigmaAPIHandler.handle_apps_status = handle_apps_status
SigmaAPIHandler.handle_apps_launch = handle_apps_launch
SigmaAPIHandler.handle_apps_autoconfigure = handle_apps_autoconfigure
SigmaAPIHandler.handle_marketplace_modules = handle_marketplace_modules
SigmaAPIHandler.handle_marketplace_install = handle_marketplace_install
SigmaAPIHandler.handle_marketplace_uninstall = handle_marketplace_uninstall
SigmaAPIHandler.handle_marketplace_rebuild = handle_marketplace_rebuild
SigmaAPIHandler.handle_audio_studio_status = handle_audio_studio_status
SigmaAPIHandler.handle_audio_studio_stations = handle_audio_studio_stations

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
        
        # 3. CPU Core Multi-threading Optimization (Dynamic detection)
        cpu_threads = str(os.cpu_count() or 8)
        os.environ["OMP_NUM_THREADS"] = cpu_threads
        os.environ["MKL_NUM_THREADS"] = cpu_threads
        
        log.info("Hardware Acceleration active: GPUs=%s | Parallel Slots=%s | FlashAttention=1 | VRAM Warm Cache=24h | CPU Threads=%s",
                 devices, num_parallel, cpu_threads)
        
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

    log.info("Listening on http://localhost:8000 (FastAPI ASGI v8.0)")
    log.info("Interactive OpenAPI Docs available at http://localhost:8000/docs")
    try:
        import uvicorn
        from core.fastapi_app import app
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        graceful_shutdown(None, None)