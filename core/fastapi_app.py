# ==============================================================================
# core/fastapi_app.py — FastAPI High-Performance Server Integration (v8.0)
# Sigma Studio v8 — ASGI Server & Interactive Swagger Documentation (/docs)
# ==============================================================================
"""FastAPI ASGI application with CORS middleware, static file mounts, SSE streaming,
and complete API routing for all 70+ Sigma Studio endpoints.
"""

import os
import json
import asyncio
import queue
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.logger import get_logger
from core.sandbox import is_path_allowed
from core.store import modules_store, tasks_store
from core.api_router import register_get_handlers, register_post_handlers

log = get_logger("fastapi_server")

app = FastAPI(
    title="Σ-SIGMA Studio API",
    description="Unified Research Environment & Cognitive Orchestration Engine",
    version="8.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
    handle_update_manifesto_image, handle_upload_agent_image, handle_upload_user_avatar
)
FastAPIHandlerAdapter.handle_api_modules = handle_api_modules
FastAPIHandlerAdapter.handle_api_topics = handle_api_topics
FastAPIHandlerAdapter.handle_knowledge_db = handle_knowledge_db
FastAPIHandlerAdapter.handle_list_manifesti = handle_list_manifesti
FastAPIHandlerAdapter.handle_update_manifesto_image = handle_update_manifesto_image
FastAPIHandlerAdapter.handle_upload_agent_image = handle_upload_agent_image
FastAPIHandlerAdapter.handle_upload_user_avatar = handle_upload_user_avatar

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
    handle_api_ollama_models, handle_api_create_model
)
FastAPIHandlerAdapter.handle_api_config_get = handle_api_config_get
FastAPIHandlerAdapter.handle_api_config_post = handle_api_config_post
FastAPIHandlerAdapter.handle_api_ollama_models = handle_api_ollama_models
FastAPIHandlerAdapter.handle_api_create_model = handle_api_create_model

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

from core.training_handler import (
    search_hf_datasets, get_hf_dataset_info, import_local_dataset,
    register_hf_dataset, list_datasets, delete_dataset, create_training_job,
    start_training_job, stop_training_job, get_job_status, get_job_logs,
    list_jobs, delete_job, export_to_ollama, get_hardware_info, get_featured_datasets
)
FastAPIHandlerAdapter.handle_training_list_datasets = lambda self: self.send_json_response(list_datasets())
FastAPIHandlerAdapter.handle_training_dataset_search = lambda self: self.send_json_response(search_hf_datasets(self.read_json_body().get("query", "")))
def _handle_hardware_restart_ollama(self):
    from core.training_handler import restart_ollama_service
    res = restart_ollama_service()
    self.send_json_response(res)
FastAPIHandlerAdapter.handle_hardware_restart_ollama = _handle_hardware_restart_ollama

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
    os.environ["CUDA_VISIBLE_DEVICES"] = hw_cfg["cuda_visible_devices"]
    os.environ["OLLAMA_NUM_PARALLEL"] = str(hw_cfg["ollama_num_parallel"])
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = str(hw_cfg["ollama_max_loaded_models"])
    self.send_json_response({"success": True, "config": hw_cfg})
FastAPIHandlerAdapter.handle_hardware_config = _handle_hardware_config

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

FastAPIHandlerAdapter.handle_training_featured_datasets = lambda self: self.send_json_response(get_featured_datasets())
FastAPIHandlerAdapter.handle_training_list_jobs = lambda self: self.send_json_response(list_jobs())
FastAPIHandlerAdapter.handle_training_hardware = lambda self: self.send_json_response(get_hardware_info())
FastAPIHandlerAdapter.handle_hardware_status = lambda self: self.send_json_response(get_hardware_info())
FastAPIHandlerAdapter.handle_training_job_status = lambda self: self.send_json_response(get_job_status(self.read_json_body().get("id", "")))
FastAPIHandlerAdapter.handle_training_job_logs = lambda self: self.send_json_response(get_job_logs(self.read_json_body().get("id", "")))

register_get_handlers(FastAPIHandlerAdapter)
register_post_handlers(FastAPIHandlerAdapter)


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
    if request.url.path in ("/api/chat", "/api/chat/loop", "/api/chat/pipeline/start", "/api/research/start"):
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


DIST_DIR = Path("sigma_studio/dist")


@app.get("/")
async def serve_root():
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Σ-SIGMA Studio API Running (v8.0). Use /docs for Swagger UI."})


@app.get("/{path:path}")
async def serve_static_or_spa(path: str):
    target_img = Path("images") / path
    if target_img.exists() and target_img.is_file():
        return FileResponse(target_img)

    if path.startswith("images/"):
        target_img2 = Path(path)
        if target_img2.exists() and target_img2.is_file():
            return FileResponse(target_img2)

    target_dist = DIST_DIR / path
    if target_dist.exists() and target_dist.is_file():
        return FileResponse(target_dist)

    target_data = Path("data") / path
    if target_data.exists() and target_data.is_file():
        return FileResponse(target_data)

    target_manifesti = Path("manifesti") / path
    if target_manifesti.exists() and target_manifesti.is_file():
        return FileResponse(target_manifesti)

    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(status_code=404, content={"error": f"Path '{path}' non trovato"})
