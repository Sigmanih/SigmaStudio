# ==============================================================================
# core/fastapi_app.py — FastAPI High-Performance Server Integration (v8.0)
# Sigma Studio v8 — ASGI Server & Interactive Swagger Documentation (/docs)
# ==============================================================================
"""FastAPI ASGI application with CORS middleware, static file mounts, SSE streaming,
and complete API routing for all 70+ Sigma Studio endpoints.
"""

import os
import json
import time
import uuid
import datetime
import asyncio
import queue
import threading
import warnings
from pathlib import Path
from urllib.parse import urlparse

warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", message=".*expandable_segments.*")
warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
warnings.filterwarnings("ignore", message=".*weight_norm is deprecated.*")
warnings.filterwarnings("ignore", message=".*Redirects are currently not supported.*")

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.logger import get_logger
from core.sandbox import is_path_allowed
from core.store import modules_store, tasks_store
from core.api_router import register_get_handlers, register_post_handlers
from core.system_cleanup import handle_system_clear_memory, shutdown_all_tasks

log = get_logger("fastapi_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Graceful Shutdown: detach running tasks, stop child processes, free VRAM/RAM
    log.info("[FastAPI] Shutdown avviato: arresto ordinato di tutti i task e liberazione risorse...")
    shutdown_all_tasks()


app = FastAPI(
    title="Σ-SIGMA Studio API",
    description="Unified Research Environment & Cognitive Orchestration Engine",
    version="8.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FastAPIHandlerAdapter:
    """Bridge adapter that allows existing core handlers to run seamlessly on FastAPI."""

    _is_path_allowed = staticmethod(is_path_allowed)

    def __init__(self, request_path: str, headers: dict, body_bytes: bytes):
        self.path = request_path
        self.headers = headers
        self._body_bytes = body_bytes
        self._response_data = None
        self._response_status = 200
        self._response_headers = {}
        self.sse_queue = queue.Queue()
        self.wfile = self._SSEWriter(self.sse_queue)

    class _SSEWriter:
        def __init__(self, q: queue.Queue):
            self._queue = q

        def write(self, b: bytes):
            self._queue.put(b.decode("utf-8", errors="replace"))

        def flush(self):
            pass

    def get_module_meta(self) -> dict:
        return modules_store.load()

    def save_module_meta(self, meta: dict) -> None:
        modules_store.save(meta)

    def read_json_body(self) -> dict:
        if not self._body_bytes:
            return {}
        try:
            return json.loads(self._body_bytes.decode("utf-8"))
        except Exception:
            return {}

    def send_response(self, status: int):
        self._response_status = status

    def send_header(self, keyword: str, value: str):
        self._response_headers[keyword] = value

    def end_headers(self):
        pass

    def send_json_response(self, data: dict, status: int = 200) -> None:
        self._response_data = data
        self._response_status = status

    def send_error(self, status: int, message: str = ""):
        self._response_data = {"error": message or f"Error {status}"}
        self._response_status = status


# Register all handler methods onto the FastAPIHandlerAdapter
from core.data_handler import (
    handle_api_modules, handle_api_topics, handle_knowledge_db, handle_list_manifesti,
    handle_update_manifesto_image, handle_upload_agent_image, handle_upload_user_avatar,
    handle_manifesti_hub, handle_manifesti_install_from_hub, handle_manifesti_uninstall
)
FastAPIHandlerAdapter.handle_api_modules = handle_api_modules
FastAPIHandlerAdapter.handle_api_topics = handle_api_topics
FastAPIHandlerAdapter.handle_knowledge_db = handle_knowledge_db
FastAPIHandlerAdapter.handle_list_manifesti = handle_list_manifesti
FastAPIHandlerAdapter.handle_update_manifesto_image = handle_update_manifesto_image
FastAPIHandlerAdapter.handle_upload_agent_image = handle_upload_agent_image
FastAPIHandlerAdapter.handle_upload_user_avatar = handle_upload_user_avatar
FastAPIHandlerAdapter.handle_manifesti_hub = handle_manifesti_hub
FastAPIHandlerAdapter.handle_manifesti_install_from_hub = handle_manifesti_install_from_hub
FastAPIHandlerAdapter.handle_manifesti_uninstall = handle_manifesti_uninstall


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
    handle_mcp_ha_entities,
    handle_mcp_ha_control,
)
FastAPIHandlerAdapter.handle_mcp_servers = handle_mcp_servers
FastAPIHandlerAdapter.handle_mcp_tools = handle_mcp_tools
FastAPIHandlerAdapter.handle_mcp_resources = handle_mcp_resources
FastAPIHandlerAdapter.handle_mcp_rpc = handle_mcp_rpc
FastAPIHandlerAdapter.handle_mcp_policy = handle_mcp_policy
FastAPIHandlerAdapter.handle_mcp_integration = handle_mcp_integration
FastAPIHandlerAdapter.handle_mcp_test_integration = handle_mcp_test_integration
FastAPIHandlerAdapter.handle_mcp_external_add = handle_mcp_external_add
FastAPIHandlerAdapter.handle_mcp_external_remove = handle_mcp_external_remove
FastAPIHandlerAdapter.handle_mcp_external_connect = handle_mcp_external_connect
FastAPIHandlerAdapter.handle_mcp_pending = handle_mcp_pending
FastAPIHandlerAdapter.handle_mcp_approve = handle_mcp_approve
FastAPIHandlerAdapter.handle_mcp_ha_entities = handle_mcp_ha_entities
FastAPIHandlerAdapter.handle_mcp_ha_control = handle_mcp_ha_control

from core.swarm_handler import (
    handle_swarm_agents, handle_swarm_plan, handle_swarm_execute
)
FastAPIHandlerAdapter.handle_swarm_agents = handle_swarm_agents
FastAPIHandlerAdapter.handle_swarm_plan = handle_swarm_plan
FastAPIHandlerAdapter.handle_swarm_execute = handle_swarm_execute


from core.module_handler import (
    handle_create_topic, handle_update_topic, handle_delete_topic,
    handle_create_module, handle_delete_module, handle_update_module
)
FastAPIHandlerAdapter.handle_create_topic = handle_create_topic
FastAPIHandlerAdapter.handle_update_topic = handle_update_topic
FastAPIHandlerAdapter.handle_delete_topic = handle_delete_topic
FastAPIHandlerAdapter.handle_create_module = handle_create_module
FastAPIHandlerAdapter.handle_delete_module = handle_delete_module
FastAPIHandlerAdapter.handle_update_module = handle_update_module

from core.file_handler import (
    handle_get_file, handle_create_file, handle_delete_file,
    handle_upload_file, handle_run_test, handle_api_action,
    handle_rename_file, handle_api_rollback
)
FastAPIHandlerAdapter.handle_get_file = handle_get_file
FastAPIHandlerAdapter.handle_create_file = handle_create_file
FastAPIHandlerAdapter.handle_delete_file = handle_delete_file
FastAPIHandlerAdapter.handle_upload_file = handle_upload_file
FastAPIHandlerAdapter.handle_run_test = handle_run_test
FastAPIHandlerAdapter.handle_api_action = handle_api_action
FastAPIHandlerAdapter.handle_rename_file = handle_rename_file
FastAPIHandlerAdapter.handle_api_rollback = handle_api_rollback

from core.task_handler import (
    handle_api_tasks_get, handle_api_tasks_post,
    handle_api_tasks_by_agent, handle_api_tasks_assign
)
FastAPIHandlerAdapter.handle_api_tasks_get = handle_api_tasks_get
FastAPIHandlerAdapter.handle_api_tasks_post = handle_api_tasks_post
FastAPIHandlerAdapter.handle_api_tasks_by_agent = handle_api_tasks_by_agent
FastAPIHandlerAdapter.handle_api_tasks_assign = handle_api_tasks_assign

from core.config_handler import (
    handle_api_config_get, handle_api_config_post,
    handle_api_ollama_models, handle_api_create_model,
    handle_hf_token_config, handle_hf_token_get,
    handle_tts_engines_fallback
)
FastAPIHandlerAdapter.handle_api_config_get = handle_api_config_get
FastAPIHandlerAdapter.handle_api_config_post = handle_api_config_post
FastAPIHandlerAdapter.handle_api_ollama_models = handle_api_ollama_models
FastAPIHandlerAdapter.handle_api_create_model = handle_api_create_model
FastAPIHandlerAdapter.handle_hf_token_config = handle_hf_token_config
FastAPIHandlerAdapter.handle_hf_token_get = handle_hf_token_get
FastAPIHandlerAdapter.handle_tts_engines_fallback = handle_tts_engines_fallback

from core.engine import (
    handle_engine_status, handle_engine_profile, handle_engine_partition,
    handle_engine_hf_import, handle_engine_models, handle_engine_optimize,
    handle_engine_plan, handle_engine_unload, handle_engine_benchmark
)
from core.engine.provider_server import (
    handle_v1_models, handle_v1_embeddings,
    handle_ollama_tags, handle_ollama_version, handle_ollama_ps, handle_ollama_show,
    handle_engine_server_info, handle_provider_server_toggle,
    is_provider_server_enabled, set_provider_server_enabled,
    stream_openai_chat_generator, execute_openai_chat_non_stream,
    stream_ollama_chat_generator, execute_ollama_chat_non_stream,
    stream_ollama_generate_generator, execute_ollama_generate_non_stream,
    get_all_available_models,
)
FastAPIHandlerAdapter.handle_engine_status = handle_engine_status
FastAPIHandlerAdapter.handle_engine_profile = handle_engine_profile
FastAPIHandlerAdapter.handle_engine_partition = handle_engine_partition
FastAPIHandlerAdapter.handle_engine_hf_import = handle_engine_hf_import
FastAPIHandlerAdapter.handle_engine_models = handle_engine_models
FastAPIHandlerAdapter.handle_engine_optimize = handle_engine_optimize
FastAPIHandlerAdapter.handle_engine_plan = handle_engine_plan
FastAPIHandlerAdapter.handle_engine_unload = handle_engine_unload
FastAPIHandlerAdapter.handle_engine_benchmark = handle_engine_benchmark
FastAPIHandlerAdapter.handle_v1_models = handle_v1_models
FastAPIHandlerAdapter.handle_v1_embeddings = handle_v1_embeddings
FastAPIHandlerAdapter.handle_provider_server_toggle = handle_provider_server_toggle
FastAPIHandlerAdapter.handle_ollama_tags = handle_ollama_tags
FastAPIHandlerAdapter.handle_ollama_version = handle_ollama_version
FastAPIHandlerAdapter.handle_ollama_ps = handle_ollama_ps
FastAPIHandlerAdapter.handle_ollama_show = handle_ollama_show
FastAPIHandlerAdapter.handle_engine_server_info = handle_engine_server_info





from core.chat_handler import handle_chat, handle_chat_extract_files
FastAPIHandlerAdapter.handle_chat = handle_chat
FastAPIHandlerAdapter.handle_chat_extract_files = handle_chat_extract_files

from core.loop_handler import handle_chat_loop
FastAPIHandlerAdapter.handle_chat_loop = handle_chat_loop

from core.execute_loop import handle_chat_execute
FastAPIHandlerAdapter.handle_chat_execute = handle_chat_execute

from core.plan_handler import handle_chat_plan, handle_chat_execute_plan
FastAPIHandlerAdapter.handle_chat_plan = handle_chat_plan
FastAPIHandlerAdapter.handle_chat_execute_plan = handle_chat_execute_plan

from core.sandbox_manager import (
    handle_sandbox_create, handle_sandbox_run, handle_sandbox_install,
    handle_sandbox_list, handle_sandbox_destroy
)
FastAPIHandlerAdapter.handle_sandbox_create = handle_sandbox_create
FastAPIHandlerAdapter.handle_sandbox_run = handle_sandbox_run
FastAPIHandlerAdapter.handle_sandbox_install = handle_sandbox_install
FastAPIHandlerAdapter.handle_sandbox_list = handle_sandbox_list
FastAPIHandlerAdapter.handle_sandbox_destroy = handle_sandbox_destroy

from core.agent_registry import (
    handle_agents_list, handle_agents_get, handle_agents_register,
    handle_agents_update, handle_agents_for_topic, handle_agents_colors,
)
FastAPIHandlerAdapter.handle_agents_list = handle_agents_list
FastAPIHandlerAdapter.handle_agents_get = handle_agents_get
FastAPIHandlerAdapter.handle_agents_register = handle_agents_register
FastAPIHandlerAdapter.handle_agents_update = handle_agents_update
FastAPIHandlerAdapter.handle_agents_for_topic = handle_agents_for_topic
FastAPIHandlerAdapter.handle_agents_colors = handle_agents_colors

from core.agent_orchestrator import handle_chat_orchestrate
FastAPIHandlerAdapter.handle_chat_orchestrate = handle_chat_orchestrate

from core.agent_templates import handle_agents_templates, handle_agents_create
FastAPIHandlerAdapter.handle_agents_templates = handle_agents_templates
FastAPIHandlerAdapter.handle_agents_create = handle_agents_create

from core.pipeline_engine import handle_pipeline_start, handle_pipeline_status, handle_pipeline_stop
FastAPIHandlerAdapter.handle_pipeline_start = handle_pipeline_start
FastAPIHandlerAdapter.handle_pipeline_status = handle_pipeline_status
FastAPIHandlerAdapter.handle_pipeline_stop = handle_pipeline_stop

from core.hardware_api import (
    handle_hardware_status, handle_hardware_gpu_processes, handle_hardware_config,
    handle_hardware_restart_ollama, handle_hardware_gpu_kill
)
FastAPIHandlerAdapter.handle_hardware_status = handle_hardware_status
FastAPIHandlerAdapter.handle_hardware_gpu_processes = handle_hardware_gpu_processes
FastAPIHandlerAdapter.handle_hardware_config = handle_hardware_config
FastAPIHandlerAdapter.handle_hardware_restart_ollama = handle_hardware_restart_ollama
FastAPIHandlerAdapter.handle_hardware_gpu_kill = handle_hardware_gpu_kill

# Caricamento dinamico dei moduli opzionali installati (Creative Lab, Domotica, Model Hub, etc.)
try:
    from core.module_loader import ModuleLoader
    module_loader = ModuleLoader()
    module_loader.load_installed(app)
except Exception as _mod_err:
    log.warning(f"[FastAPI] Avviso inizializzazione ModuleLoader: {_mod_err}")

try:
    from core.modules.sigma_model_hub.backend.handlers import (
        handle_models_hf_search, handle_models_hf_details, handle_models_hf_downloads_list,
        handle_models_local_list, handle_models_local_delete, handle_models_config_get,
        handle_models_hf_download_start, handle_models_hf_download_repo, handle_models_hf_download_cancel,
        handle_models_hf_download_retry, handle_models_hf_download_remove,
        handle_models_hf_whoami, handle_models_hf_upload, handle_models_hf_upload_tasks,
        handle_models_hf_upload_cancel, handle_models_hf_upload_remove,
        handle_models_engine_load, handle_models_engine_unload, handle_models_config_save,
        handle_models_convert_info, handle_models_convert_jobs,
        handle_models_convert_start, handle_models_convert_tooling,
        handle_models_browse_dirs, handle_models_hf_token_test,
        handle_models_hf_test_connection
    )
    FastAPIHandlerAdapter.handle_models_hf_search = handle_models_hf_search
    FastAPIHandlerAdapter.handle_models_hf_details = handle_models_hf_details
    FastAPIHandlerAdapter.handle_models_hf_downloads_list = handle_models_hf_downloads_list
    FastAPIHandlerAdapter.handle_models_hf_test_connection = handle_models_hf_test_connection
    FastAPIHandlerAdapter.handle_models_hf_whoami = handle_models_hf_whoami
    FastAPIHandlerAdapter.handle_models_hf_upload = handle_models_hf_upload
    FastAPIHandlerAdapter.handle_models_hf_upload_tasks = handle_models_hf_upload_tasks
    FastAPIHandlerAdapter.handle_models_hf_upload_cancel = handle_models_hf_upload_cancel
    FastAPIHandlerAdapter.handle_models_hf_upload_remove = handle_models_hf_upload_remove
    FastAPIHandlerAdapter.handle_models_local_list = handle_models_local_list
    FastAPIHandlerAdapter.handle_models_local_delete = handle_models_local_delete
    FastAPIHandlerAdapter.handle_models_config_get = handle_models_config_get
    FastAPIHandlerAdapter.handle_models_hf_download_start = handle_models_hf_download_start
    FastAPIHandlerAdapter.handle_models_hf_download_repo = handle_models_hf_download_repo
    FastAPIHandlerAdapter.handle_models_hf_download_cancel = handle_models_hf_download_cancel
    FastAPIHandlerAdapter.handle_models_hf_download_retry = handle_models_hf_download_retry
    FastAPIHandlerAdapter.handle_models_hf_download_remove = handle_models_hf_download_remove
    FastAPIHandlerAdapter.handle_models_hf_token_test = handle_models_hf_token_test
    FastAPIHandlerAdapter.handle_models_engine_load = handle_models_engine_load
    FastAPIHandlerAdapter.handle_models_engine_unload = handle_models_engine_unload
    FastAPIHandlerAdapter.handle_models_config_save = handle_models_config_save
    FastAPIHandlerAdapter.handle_models_convert_info = handle_models_convert_info
    FastAPIHandlerAdapter.handle_models_convert_jobs = handle_models_convert_jobs
    FastAPIHandlerAdapter.handle_models_convert_start = handle_models_convert_start
    FastAPIHandlerAdapter.handle_models_convert_tooling = handle_models_convert_tooling
    FastAPIHandlerAdapter.handle_models_browse_dirs = handle_models_browse_dirs


except Exception as _mh_err:
    log.warning(f"[FastAPI] Avviso binding Model Hub: {_mh_err}")





from core.integrations.handlers import (
    handle_skills_list, handle_skills_toggle, handle_apps_status,
    handle_apps_launch, handle_apps_autoconfigure,
    handle_marketplace_modules, handle_marketplace_install, handle_marketplace_uninstall, handle_marketplace_rebuild,
    handle_audio_studio_status, handle_audio_studio_stations,
    handle_training_list_jobs, handle_training_list_datasets
)
FastAPIHandlerAdapter.handle_skills_list = handle_skills_list
FastAPIHandlerAdapter.handle_skills_toggle = handle_skills_toggle
FastAPIHandlerAdapter.handle_apps_status = handle_apps_status
FastAPIHandlerAdapter.handle_apps_launch = handle_apps_launch
FastAPIHandlerAdapter.handle_apps_autoconfigure = handle_apps_autoconfigure
FastAPIHandlerAdapter.handle_marketplace_modules = handle_marketplace_modules
FastAPIHandlerAdapter.handle_marketplace_install = handle_marketplace_install
FastAPIHandlerAdapter.handle_marketplace_uninstall = handle_marketplace_uninstall
FastAPIHandlerAdapter.handle_marketplace_rebuild = handle_marketplace_rebuild
FastAPIHandlerAdapter.handle_audio_studio_status = handle_audio_studio_status
FastAPIHandlerAdapter.handle_audio_studio_stations = handle_audio_studio_stations
FastAPIHandlerAdapter.handle_training_list_jobs = handle_training_list_jobs
FastAPIHandlerAdapter.handle_training_list_datasets = handle_training_list_datasets

from core.context_broker import (
    handle_context_share, handle_context_get, handle_context_chat_log, handle_chat_message_save
)
FastAPIHandlerAdapter.handle_context_share = handle_context_share
FastAPIHandlerAdapter.handle_context_get = handle_context_get
FastAPIHandlerAdapter.handle_context_chat_log = handle_context_chat_log
FastAPIHandlerAdapter.handle_chat_message_save = handle_chat_message_save

from core.research_sessions import (
    handle_research_create, handle_research_list, handle_research_status,
    handle_research_delete, handle_research_update_objective,
    handle_research_chat_history, handle_research_update_agents,
)
FastAPIHandlerAdapter.handle_research_create = handle_research_create
FastAPIHandlerAdapter.handle_research_list = handle_research_list
FastAPIHandlerAdapter.handle_research_status = handle_research_status
FastAPIHandlerAdapter.handle_research_delete = handle_research_delete
FastAPIHandlerAdapter.handle_research_update_objective = handle_research_update_objective
FastAPIHandlerAdapter.handle_research_update_agents = handle_research_update_agents
FastAPIHandlerAdapter.handle_research_chat_history = handle_research_chat_history

from core.agent_orchestrator import (
    handle_research_decompose, handle_research_next_steps, handle_research_start
)
FastAPIHandlerAdapter.handle_research_decompose = handle_research_decompose
FastAPIHandlerAdapter.handle_research_next_steps = handle_research_next_steps
FastAPIHandlerAdapter.handle_research_start = handle_research_start


def _handle_router_train(self):
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
        return self.send_json_response({"success": False, "error": str(exc)}, 500)
FastAPIHandlerAdapter.handle_router_train = _handle_router_train
FastAPIHandlerAdapter.handle_system_clear_memory = handle_system_clear_memory

register_get_handlers(FastAPIHandlerAdapter)
register_post_handlers(FastAPIHandlerAdapter)


# Endpoints whose handlers push SSE events on `wfile` instead of returning JSON.
# Missing entries here are silently swallowed: the handler writes into the queue,
# nobody drains it, and the client receives an empty 200.
SSE_ENDPOINTS = (
    "/api/chat",
    "/api/chat/loop",
    "/api/chat/orchestrate",
    "/api/chat/pipeline/start",
    "/api/research/start",
    "/api/creative/generate",
    "/api/creative/edit",
    "/api/creative/3d",
    "/api/creative/mesh",
    "/api/creative/material",
    "/api/creative/video",
    "/api/creative/render",
    "/api/creative/pipeline/execute",
)


# Helper function to execute a route via the adapter
async def _dispatch_route(request: Request, method: str):
    url_path = request.url.path
    if request.query_params:
        url_path += f"?{request.query_params}"

    headers = dict(request.headers)
    body = await request.body()
    adapter = FastAPIHandlerAdapter(url_path, headers, body)

    handler_name = None
    if method == "GET":
        handler_name = adapter._GET_HANDLERS.get(request.url.path)
    elif method == "POST":
        handler_name = adapter._POST_HANDLERS.get(request.url.path)

    if not handler_name or not hasattr(adapter, handler_name):
        return JSONResponse(status_code=404, content={"error": f"Endpoint '{request.url.path}' non trovato"})

    handler_fn = getattr(adapter, handler_name)

    # Check if SSE streaming is expected
    if request.url.path in SSE_ENDPOINTS:
        def _run_in_thread():
            try:
                handler_fn()
                if adapter._response_data is not None:
                    res_data = dict(adapter._response_data)
                    if "response" in res_data and "token" not in res_data:
                        res_data["token"] = res_data["response"]
                    payload = json.dumps(res_data)
                    adapter.sse_queue.put(f"data: {payload}\n\n")
                    adapter.sse_queue.put("data: [DONE]\n\n")
            except Exception as e:
                adapter.sse_queue.put(f"data: {json.dumps({'error': str(e)})}\n\n")
            finally:
                adapter.sse_queue.put(None)

        threading.Thread(target=_run_in_thread, daemon=True).start()

        async def sse_generator():
            while True:
                item = await asyncio.to_thread(adapter.sse_queue.get)
                if item is None:
                    break
                yield item

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # Standard JSON dispatch
    await asyncio.to_thread(handler_fn)

    if adapter._response_data is not None:
        return JSONResponse(status_code=adapter._response_status, content=adapter._response_data)
    
    return Response(status_code=adapter._response_status)


# ==============================================================================
# SigmaEngine Standard Interoperability Endpoints (OpenAI & Ollama Standards)
# For Visual Studio Code (Continue, Cline, Roo Code, Copilot, Cursor) & SDKs
# ==============================================================================

@app.get("/v1/models")
@app.get("/api/v1/models")
@app.get("/api/models")
@app.get("/models")
async def v1_list_models():
    """List available models in OpenAI standard format."""
    models_list = get_all_available_models()
    created_ts = int(time.time())
    openai_data = []
    for m in models_list:
        openai_data.append({
            "id": m["id"],
            "object": "model",
            "created": m.get("created", created_ts),
            "owned_by": "sigmaengine",
            "permission": [{
                "id": f"modelperm-{uuid.uuid4().hex[:12]}",
                "object": "model_permission",
                "created": created_ts,
                "allow_create_engine": False,
                "allow_sampling": True,
                "allow_logprobs": True,
                "allow_search_indices": False,
                "allow_view": True,
                "allow_fine_tuning": False,
                "organization": "*",
                "group": None,
                "is_blocking": False,
            }],
            "root": m["id"],
            "parent": None,
        })
    return JSONResponse(status_code=200, content={"object": "list", "data": openai_data})


@app.get("/v1/models/{model_id:path}")
async def v1_retrieve_model(model_id: str):
    """Retrieve single model details in OpenAI standard format."""
    created_ts = int(time.time())
    return JSONResponse(status_code=200, content={
        "id": model_id,
        "object": "model",
        "created": created_ts,
        "owned_by": "sigmaengine",
        "root": model_id,
        "parent": None
    })


@app.post("/v1/chat/completions")
@app.post("/api/v1/chat/completions")
@app.post("/chat/completions")
async def v1_chat_completions(request: Request):
    """OpenAI standard Chat Completions endpoint with SSE Streaming & JSON support."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    model = body.get("model") or "sigmaengine"
    messages = body.get("messages", [])
    stream = bool(body.get("stream", False))
    temperature = float(body.get("temperature", 0.7))
    max_tokens = int(body.get("max_tokens") or body.get("max_completion_tokens") or 4096)
    top_p = float(body.get("top_p", 0.9))

    if stream:
        async def sse_stream():
            try:
                for chunk in stream_openai_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                ):
                    yield chunk
                    await asyncio.sleep(0.001)
            except Exception as e:
                err_payload = {"error": {"message": str(e), "type": "server_error"}}
                yield f"data: {json.dumps(err_payload)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            sse_stream(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        res = await asyncio.to_thread(
            execute_openai_chat_non_stream,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p
        )
        return JSONResponse(status_code=200, content=res)


@app.post("/v1/completions")
@app.post("/api/v1/completions")
@app.post("/completions")
async def v1_completions(request: Request):
    """OpenAI standard Text Completions endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    model = body.get("model") or "sigmaengine"
    prompt = body.get("prompt", "")
    if isinstance(prompt, list):
        prompt = prompt[0] if prompt else ""
    stream = bool(body.get("stream", False))
    temperature = float(body.get("temperature", 0.7))
    max_tokens = int(body.get("max_tokens", 4096))

    messages = [{"role": "user", "content": str(prompt)}]
    if stream:
        async def sse_stream():
            req_id = f"cmpl-{uuid.uuid4().hex[:20]}"
            created_ts = int(time.time())
            from core.engine.unified_runtime import sigma_engine
            for chunk in sigma_engine.generate_stream(
                prompt=str(prompt),
                system_prompt="Sei Sigma Assistant.",
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model,
                messages=messages,
            ):
                token = chunk.get("token", "")
                if token:
                    payload = {
                        "id": req_id,
                        "object": "text_completion",
                        "created": created_ts,
                        "model": model,
                        "choices": [{"text": token, "index": 0, "logprobs": None, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0.001)
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream; charset=utf-8")
    else:
        from core.engine.unified_runtime import sigma_engine
        tokens = []
        for chunk in sigma_engine.generate_stream(
            prompt=str(prompt),
            system_prompt="Sei Sigma Assistant.",
            temperature=temperature,
            max_tokens=max_tokens,
            model_name=model,
            messages=messages,
        ):
            t = chunk.get("token", "")
            if t:
                tokens.append(t)
        full_text = "".join(tokens)
        req_id = f"cmpl-{uuid.uuid4().hex[:20]}"
        created_ts = int(time.time())
        return JSONResponse(status_code=200, content={
            "id": req_id,
            "object": "text_completion",
            "created": created_ts,
            "model": model,
            "choices": [{"text": full_text, "index": 0, "logprobs": None, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": max(1, len(str(prompt).split())),
                "completion_tokens": max(1, len(tokens)),
                "total_tokens": max(1, len(str(prompt).split())) + max(1, len(tokens))
            }
        })


@app.post("/v1/embeddings")
@app.post("/api/v1/embeddings")
@app.post("/api/embed")
@app.post("/api/embeddings")
@app.post("/v1/api/embed")
@app.post("/v1/api/embeddings")
async def v1_embeddings(request: Request):
    """OpenAI & Ollama standard Embeddings endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    input_data = body.get("input", "") or body.get("prompt", "")
    model = body.get("model", "sigmaengine")
    if isinstance(input_data, str):
        inputs = [input_data]
    elif isinstance(input_data, list):
        inputs = input_data
    else:
        inputs = [str(input_data)]

    import hashlib
    data = []
    raw_embeddings = []
    for idx, text in enumerate(inputs):
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(1536):
            byte_val = seed_bytes[i % len(seed_bytes)]
            vector.append(round((float(byte_val) / 255.0) * 2.0 - 1.0, 6))
        data.append({
            "object": "embedding",
            "embedding": vector,
            "index": idx
        })
        raw_embeddings.append(vector)

    # Return structure compatible with both OpenAI and Ollama formats
    return JSONResponse(status_code=200, content={
        "object": "list",
        "data": data,
        "model": model,
        "embeddings": raw_embeddings if len(raw_embeddings) > 1 else (raw_embeddings[0] if raw_embeddings else []),
        "embedding": raw_embeddings[0] if raw_embeddings else [],
        "usage": {
            "prompt_tokens": sum(len(t.split()) for t in inputs),
            "total_tokens": sum(len(t.split()) for t in inputs)
        }
    })


@app.get("/api/tags")
@app.get("/v1/api/tags")
@app.get("/api/v1/tags")
@app.get("/tags")
@app.get("/v1/tags")
async def ollama_tags_route():
    """Ollama standard /api/tags endpoint."""
    models_list = get_all_available_models()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ollama_models = []
    for m in models_list:
        m_name = m["id"]
        m_name_tagged = f"{m_name}:latest" if ":" not in m_name else m_name
        ollama_models.append({
            "name": m_name_tagged,
            "model": m_name_tagged,
            "modified_at": now_iso,
            "size": m.get("size", 4 * 1024**3),
            "digest": f"sha256:{abs(hash(m_name)):016x}{abs(hash(m_name)):016x}"[:64],
            "details": {
                "parent_model": "",
                "format": "gguf" if "gguf" in str(m.get("quant", "")).lower() else "safetensors",
                "family": m.get("family", "llama"),
                "families": [m.get("family", "llama")],
                "parameter_size": "7B",
                "quantization_level": str(m.get("quant", "Q4_K_M"))
            }
        })
    return JSONResponse(status_code=200, content={"models": ollama_models})


@app.get("/api/version")
@app.get("/v1/api/version")
@app.get("/api/v1/version")
@app.get("/version")
@app.get("/v1/version")
async def ollama_version_route():
    """Ollama standard /api/version endpoint."""
    return JSONResponse(status_code=200, content={"version": "0.5.4-sigmaengine"})


@app.get("/api/ps")
@app.get("/v1/api/ps")
@app.get("/api/v1/ps")
@app.get("/ps")
@app.get("/v1/ps")
async def ollama_ps_route():
    """Ollama standard /api/ps running models endpoint."""
    from core.engine.unified_runtime import sigma_engine
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    models = []
    if sigma_engine.loaded_model_name:
        m_name = sigma_engine.loaded_model_name
        models.append({
            "name": f"{m_name}:latest" if ":" not in m_name else m_name,
            "model": m_name,
            "size": 4 * 1024**3,
            "digest": f"sha256:{abs(hash(m_name)):016x}"[:64],
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "llama",
                "families": ["llama"],
                "parameter_size": "7B",
                "quantization_level": "Q4_K_M"
            },
            "expires_at": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)).isoformat(),
            "size_vram": 4 * 1024**3
        })
    return JSONResponse(status_code=200, content={"models": models})


@app.post("/api/show")
@app.post("/v1/api/show")
@app.post("/api/v1/show")
@app.post("/show")
@app.post("/v1/show")
async def ollama_show_route(request: Request):
    """Ollama standard /api/show endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    model_name = body.get("name") or body.get("model") or "sigmaengine"
    return JSONResponse(status_code=200, content={
        "modelfile": f"# Modelfile for {model_name}\nFROM {model_name}\nPARAMETER temperature 0.7\nSYSTEM Sei Sigma Assistant.\n",
        "parameters": "temperature 0.7\nstop \"<|im_end|>\"\n",
        "template": "{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n{{ end }}{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n<|im_start|>assistant\n{{ end }}",
        "details": {
            "parent_model": "",
            "format": "gguf",
            "family": "llama",
            "families": ["llama"],
            "parameter_size": "7B",
            "quantization_level": "Q4_K_M"
        }
    })


@app.post("/api/chat")
@app.post("/v1/api/chat")
@app.post("/api/v1/chat")
@app.post("/v1/chat")
async def ollama_chat_route(request: Request):
    """
    Intelligently routes between:
    1. Sigma Studio UI Internal Chat (messages with UI metadata, tools, agents, SSE)
    2. Ollama Standard Protocol Chat (messages list with NDJSON streaming)
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Check if this is Sigma Studio internal chat request
    is_internal_ui = (
        "message" in body
        or "user_name" in body
        or "allow_actions" in body
        or "context" in body
        or "uploaded_files" in body
        or "manifesto_path" in body
        or "user_profile" in body
        or "selected_preset" in body
        or not body.get("messages")
    )

    if is_internal_ui:
        return await _dispatch_route(request, "POST")

    # Ollama standard protocol chat
    model = body.get("model") or "sigmaengine"
    messages = body.get("messages", [])
    stream = body.get("stream", True)
    options = body.get("options", {})
    temperature = float(options.get("temperature", 0.7))
    max_tokens = int(options.get("num_predict", 4096))

    if stream:
        async def ndjson_stream():
            try:
                for chunk in stream_ollama_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    yield chunk
                    await asyncio.sleep(0.001)
            except Exception as e:
                err_obj = {"error": str(e)}
                yield json.dumps(err_obj) + "\n"

        return StreamingResponse(
            ndjson_stream(),
            media_type="application/x-ndjson; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        res = await asyncio.to_thread(
            execute_ollama_chat_non_stream,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return JSONResponse(status_code=200, content=res)


@app.post("/api/generate")
@app.post("/v1/api/generate")
@app.post("/api/v1/generate")
@app.post("/generate")
@app.post("/v1/generate")
async def ollama_generate_route(request: Request):
    """Ollama standard /api/generate endpoint with NDJSON streaming."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    model = body.get("model") or "sigmaengine"
    prompt = body.get("prompt", "")
    system_prompt = body.get("system", "")
    stream = body.get("stream", True)
    options = body.get("options", {})
    temperature = float(options.get("temperature", 0.7))
    max_tokens = int(options.get("num_predict", 4096))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if prompt:
        messages.append({"role": "user", "content": prompt})

    if stream:
        async def ndjson_stream():
            try:
                for chunk in stream_ollama_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    try:
                        parsed = json.loads(chunk.strip())
                        gen_payload = {
                            "model": model,
                            "created_at": parsed.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                            "response": parsed.get("message", {}).get("content", ""),
                            "done": parsed.get("done", False),
                        }
                        if parsed.get("done"):
                            gen_payload["total_duration"] = parsed.get("total_duration", 0)
                        yield json.dumps(gen_payload) + "\n"
                    except Exception:
                        yield chunk
                    await asyncio.sleep(0.001)
            except Exception as e:
                yield json.dumps({"error": str(e)}) + "\n"

        return StreamingResponse(
            ndjson_stream(),
            media_type="application/x-ndjson; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        res = await asyncio.to_thread(
            execute_ollama_chat_non_stream,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return JSONResponse(status_code=200, content={
            "model": model,
            "created_at": res.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            "response": res.get("message", {}).get("content", ""),
            "done": True,
            "total_duration": res.get("total_duration", 0),
        })
        return JSONResponse(status_code=200, content={
            "model": model,
            "created_at": res.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            "response": res.get("message", {}).get("content", ""),
            "done": True,
            "total_duration": res.get("total_duration", 0),
        })


@app.post("/api/embed")
@app.post("/api/embeddings")
async def ollama_embeddings_route(request: Request):
    """Ollama standard /api/embed and /api/embeddings endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    input_data = body.get("input") or body.get("prompt") or ""
    if isinstance(input_data, str):
        inputs = [input_data]
    elif isinstance(input_data, list):
        inputs = input_data
    else:
        inputs = [str(input_data)]

    import hashlib
    embeddings = []
    for text in inputs:
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(1536):
            byte_val = seed_bytes[i % len(seed_bytes)]
            vector.append(round((float(byte_val) / 255.0) * 2.0 - 1.0, 6))
        embeddings.append(vector)

    return JSONResponse(status_code=200, content={
        "model": body.get("model", "sigmaengine"),
        "embeddings": embeddings if len(embeddings) > 1 else (embeddings[0] if embeddings else []),
        "embedding": embeddings[0] if embeddings else []
    })


@app.post("/api/engine/provider_server/toggle")
async def engine_provider_server_toggle_route(request: Request):
    """POST /api/engine/provider_server/toggle — Toggles or sets provider server status."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    target_state = body.get("enabled")
    if target_state is None:
        new_state = not is_provider_server_enabled()
    else:
        new_state = bool(target_state)

    set_provider_server_enabled(new_state)
    return JSONResponse(status_code=200, content={
        "success": True,
        "provider_server_enabled": new_state,
        "message": f"Servizio SigmaEngine Provider Server {'abilitato' if new_state else 'disabilitato'}."
    })


@app.get("/api/engine/server_info")
async def engine_server_info_route():
    """GET /api/engine/server_info — Returns comprehensive connection info for external clients."""
    from core.engine.unified_runtime import sigma_engine
    models = get_all_available_models()
    resident = sigma_engine.loaded_model_name or "Nessun modello caricato"
    is_enabled = is_provider_server_enabled()

    return JSONResponse(status_code=200, content={
        "success": True,
        "engine_name": "SigmaEngine Universal Runtime",
        "version": "8.0",
        "provider_server_enabled": is_enabled,
        "status": "online" if is_enabled else "disabled",
        "active_backend": sigma_engine.active_backend,
        "resident_model": resident,
        "has_resident_model": sigma_engine.has_resident_model,
        "total_models_available": len(models),
        "available_models": models,
        "endpoints": {
            "openai_base_url": "http://localhost:8000/v1",
            "openai_chat_url": "http://localhost:8000/v1/chat/completions",
            "openai_models_url": "http://localhost:8000/v1/models",
            "ollama_base_url": "http://localhost:8000",
            "ollama_chat_url": "http://localhost:8000/api/chat",
            "ollama_tags_url": "http://localhost:8000/api/tags",
            "ollama_generate_url": "http://localhost:8000/api/generate",
        }
    })


# ==============================================================================
# Sigma Developer Studio API Endpoints (Admin Filesystem, Terminal, AI Agent)
# ==============================================================================
from core.developer_studio.handlers import (
    handle_fs_tree,
    handle_fs_read,
    handle_fs_raw,
    handle_fs_write,
    handle_fs_delete,
    handle_fs_create,
    handle_fs_rename,
    handle_fs_search,
    handle_agent_chat,
    handle_workspace_roots,
    handle_get_tasks,
    handle_save_tasks
)

@app.get("/api/developer/tasks")
async def dev_get_tasks_route(request: Request):
    return await handle_get_tasks(request)

@app.post("/api/developer/tasks")
async def dev_save_tasks_route(request: Request):
    return await handle_save_tasks(request)

@app.get("/api/developer/fs/tree")
async def dev_fs_tree_route(request: Request):
    return await handle_fs_tree(request)

@app.get("/api/developer/fs/read")
async def dev_fs_read_route(request: Request):
    return await handle_fs_read(request)

@app.get("/api/developer/fs/raw")
async def dev_fs_raw_route(request: Request):
    return await handle_fs_raw(request)

@app.post("/api/developer/fs/write")
async def dev_fs_write_route(request: Request):
    return await handle_fs_write(request)

@app.post("/api/developer/fs/delete")
async def dev_fs_delete_route(request: Request):
    return await handle_fs_delete(request)

@app.post("/api/developer/fs/create")
async def dev_fs_create_route(request: Request):
    return await handle_fs_create(request)

@app.post("/api/developer/fs/rename")
async def dev_fs_rename_route(request: Request):
    return await handle_fs_rename(request)

@app.post("/api/developer/fs/search")
async def dev_fs_search_route(request: Request):
    return await handle_fs_search(request)

@app.post("/api/developer/terminal/exec")
async def dev_terminal_exec_route(request: Request):
    return await handle_terminal_exec(request)

@app.post("/api/developer/agent/chat")
async def dev_agent_chat_route(request: Request):
    return await handle_agent_chat(request)

@app.get("/api/developer/workspace/roots")
async def dev_workspace_roots_route(request: Request):
    return await handle_workspace_roots(request)


# ------------------------------------------------------------------------------
# Generic dispatchers
# ------------------------------------------------------------------------------

@app.get("/api/{path:path}")
async def api_get_dispatcher(request: Request, path: str):
    return await _dispatch_route(request, "GET")


@app.post("/api/{path:path}")
async def api_post_dispatcher(request: Request, path: str):
    return await _dispatch_route(request, "POST")


@app.delete("/api/{path:path}")
async def api_delete_dispatcher(request: Request, path: str):
    return await _dispatch_route(request, "DELETE")


@app.patch("/api/{path:path}")
async def api_patch_dispatcher(request: Request, path: str):
    return await _dispatch_route(request, "PATCH")


# Anchored to the installation, not the working directory: launched from
# anywhere else, these resolved to folders that do not exist and the UI
# served nothing but 404s.
from core.model_paths import project_root as _project_root
_ROOT = Path(_project_root())
DIST_DIR = _ROOT / "sigma_studio" / "dist"


@app.get("/")
@app.head("/")
async def serve_root(request: Request):
    accept = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "").lower()
    
    # If client is Ollama / Cline / Roo / API client probing root or requesting text
    if "text/html" not in accept and ("ollama" in user_agent or "curl" in user_agent or "cline" in user_agent or "roo" in user_agent or accept == "*/*" or not accept):
        return Response(content="Ollama is running", media_type="text/plain", status_code=200)

    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return Response(content="Ollama is running", media_type="text/plain", status_code=200)


DATA_DIR = _ROOT / "data"


def _resolve_inside(root: Path, path: str) -> Path | None:
    """Risolve `path` dentro `root` bloccando i path traversal (`../`)."""
    try:
        root_abs = root.resolve()
        target = (root_abs / path).resolve()
        target.relative_to(root_abs)
    except (ValueError, OSError):
        return None
    return target if target.exists() and target.is_file() else None


@app.get("/{path:path}")
async def serve_static_or_spa(path: str):
    # Any unmatched API endpoint must return JSON 404, never index.html
    if path.startswith("api/") or path.startswith("v1/"):
        return JSONResponse(status_code=404, content={"error": f"API endpoint '/{path}' non trovato"})

    # Gli asset del Creative Studio vivono sotto data/creative/assets/<id>/ e sono
    # referenziati dalla UI con l'URL assoluto `/data/...`: senza questo ramo la
    # richiesta ricadeva sull'index.html e le immagini restavano rotte.
    if path.startswith("data/"):
        target = _resolve_inside(DATA_DIR, path[len("data/"):])
        if target:
            return FileResponse(target)

    target_img = _ROOT / "images" / path
    if target_img.exists() and target_img.is_file():
        return FileResponse(target_img)

    if path.startswith("images/"):
        target_img2 = Path(path)
        if target_img2.exists() and target_img2.is_file():
            return FileResponse(target_img2)

    target_dist = DIST_DIR / path
    if target_dist.exists() and target_dist.is_file():
        return FileResponse(target_dist)

    target_data = _ROOT / "data" / path
    if target_data.exists() and target_data.is_file():
        return FileResponse(target_data)

    target_manifesti = _ROOT / "manifesti" / path
    if target_manifesti.exists() and target_manifesti.is_file():
        return FileResponse(target_manifesti)

    # Missing static assets, scripts, stylesheets, fonts or images must NEVER return index.html (which causes MIME text/html errors)
    if path.startswith("assets/") or any(path.lower().endswith(ext) for ext in [
        ".js", ".css", ".map", ".json", ".wasm", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".eot"
    ]):
        return Response(status_code=404, content=f"Asset '/{path}' non trovato.", media_type="text/plain")

    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(status_code=404, content={"error": f"Path '{path}' non trovato"})
