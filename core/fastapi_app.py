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
import concurrent.futures
import queue
import threading
import warnings
from pathlib import Path
from typing import Optional
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
from core.sse import ClientGone
from core.system_cleanup import handle_system_clear_memory, shutdown_all_tasks
from core.system_handler import (
    handle_system_available_modules,
    handle_system_capabilities,
    handle_system_updates_check,
    handle_system_updates_apply,
)

log = get_logger("fastapi_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup. asyncio's default executor is sized min(32, cpu_count + 4), so
    # on a four-core board every `asyncio.to_thread` in the app shares eight
    # threads with everything else. Pointing it at our own pool makes the size
    # a property of the workload -- blocking I/O and a serialised engine -- and
    # not of how many cores the machine happens to have.
    asyncio.get_running_loop().set_default_executor(_api_executor)
    # Idempotent: a no-op when sigma_server.py already applied it, and the only
    # place it happens when uvicorn is pointed straight at this module.
    try:
        from core.runtime_env import apply_hardware_env
        apply_hardware_env()
    except Exception as exc:
        log.warning("[FastAPI] Ambiente hardware non applicato: %s", exc)
    log.info(
        "[FastAPI] Pool richieste: %d thread API + %d thread streaming (CPU: %s core).",
        _API_WORKERS, _STREAM_WORKERS, os.cpu_count(),
    )
    yield
    # Graceful Shutdown: detach running tasks, stop child processes, free VRAM/RAM
    log.info("[FastAPI] Shutdown avviato: arresto ordinato di tutti i task e liberazione risorse...")
    shutdown_all_tasks()
    # Do not wait: a generation in flight can take minutes, and the point of
    # Ctrl+C is that the port is free now.
    _api_executor.shutdown(wait=False, cancel_futures=True)
    _stream_executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(
    title="Σ-SIGMA Studio API",
    description="Unified Research Environment & Cognitive Orchestration Engine",
    version="0.9.0-beta",
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


# Handlers are synchronous, so every API request spends its life on a worker
# thread. Left to asyncio's default executor that pool is min(32, cpu_count+4)
# threads -- twenty-eight on the workstation this was written on, and eight on
# a four-core Raspberry Pi. Eight is few enough that a couple of slow handlers
# starve every other endpoint, which is exactly how a board that was merely
# generating slowly ended up answering nothing at all.
#
# Two pools rather than one, because the two kinds of work have different
# shapes: a status poll must never queue behind a model load. The sizes are set
# from the workload (these threads block on I/O and on the engine lock, they do
# not compete for CPU) rather than from the core count.
_API_WORKERS = 32
_STREAM_WORKERS = 16

_api_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=_API_WORKERS, thread_name_prefix="sigma-api"
)
_stream_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=_STREAM_WORKERS, thread_name_prefix="sigma-stream"
)




_STREAM_SENTINEL = object()


async def _aiter_blocking(factory):
    """
    Iterates a blocking generator without ever holding the event loop.

    Every streaming route here used to write `for chunk in generator()` inside
    an `async def`, which runs the generator's body -- the whole forward pass --
    on the event loop itself. On a machine fast enough that each token arrives
    in microseconds nobody notices. On a Raspberry Pi, where prefill alone is
    tens of seconds, it means the server stops accepting connections entirely
    for the duration: not a slow answer, a dead port.

    The generator runs on a worker thread and hands items to the loop instead.
    `factory` is a zero-argument callable so the generator is created on that
    thread, never on the loop.
    """
    loop = asyncio.get_running_loop()
    items: asyncio.Queue = asyncio.Queue()
    stop = threading.Event()

    def _deliver(item) -> bool:
        try:
            loop.call_soon_threadsafe(items.put_nowait, item)
            return True
        except RuntimeError:                    # loop closed under us
            stop.set()
            return False

    def _pump():
        source = None
        try:
            source = factory()
            for item in source:
                if stop.is_set():
                    break
                if not _deliver(item):
                    break
        except BaseException as exc:            # re-raised on the consumer side
            _deliver(exc)
        finally:
            # Closed explicitly rather than left to the collector: abandoning
            # an engine generator mid-iteration leaves its `finally` -- and the
            # generation lock it releases there -- waiting on a garbage
            # collection nobody has scheduled.
            if source is not None and hasattr(source, "close"):
                try:
                    source.close()
                except Exception as exc:
                    log.debug("[FastAPI] chiusura generatore ignorata: %s", exc)
            _deliver(_STREAM_SENTINEL)

    _stream_executor.submit(_pump)
    try:
        while True:
            item = await items.get()
            if item is _STREAM_SENTINEL:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        # Set on client disconnect as well as normal completion, so an
        # abandoned stream stops generating instead of running to its full
        # token budget with nobody reading.
        stop.set()


class FastAPIHandlerAdapter:
    """Bridge adapter that allows existing core handlers to run seamlessly on FastAPI."""

    _is_path_allowed = staticmethod(is_path_allowed)
    _GET_HANDLERS: dict[str, str] = {}
    _POST_HANDLERS: dict[str, str] = {}

    def __init__(self, request_path: str, headers: dict, body_bytes: bytes):
        self.path = request_path
        self.headers = headers
        self._body_bytes = body_bytes
        self._response_data = None
        self._response_status = 200
        self._response_headers = {}
        # Streaming state, populated by attach_stream() on the SSE path only.
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stream_queue: Optional[asyncio.Queue] = None
        self.client_gone = threading.Event()
        self.sse_queue = queue.Queue()
        self.wfile = self._SSEWriter(self)

    def attach_stream(self, loop: "asyncio.AbstractEventLoop") -> "asyncio.Queue":
        """
        Wires this adapter's writer to an asyncio queue on the running loop.

        The events are handed to the loop with call_soon_threadsafe instead of
        being parked in a thread-safe queue somebody has to block on. That
        matters more than it looks: draining a queue.Queue meant one worker
        thread sat in `get()` for the entire generation, so on a small machine
        a handful of open chats could hold every thread the pool had while
        doing nothing at all.
        """
        self._loop = loop
        self._stream_queue = asyncio.Queue()
        return self._stream_queue

    def emit(self, item) -> None:
        """Push one item to the reader, or raise if there is no reader left."""
        if self.client_gone.is_set():
            raise ClientGone("Il client ha chiuso lo stream.")
        if self._loop is None or self._stream_queue is None:
            self.sse_queue.put(item)
            return
        try:
            self._loop.call_soon_threadsafe(self._stream_queue.put_nowait, item)
        except RuntimeError as exc:            # loop already closed
            self.client_gone.set()
            raise ClientGone(str(exc)) from exc

    class _SSEWriter:
        """File-like shim: handlers write SSE frames here as if to a socket."""

        def __init__(self, adapter: "FastAPIHandlerAdapter"):
            self._adapter = adapter

        def write(self, b: bytes):
            self._adapter.emit(b.decode("utf-8", errors="replace"))

        def flush(self):
            # A write that cannot reach the reader must fail on the next call
            # too, so callers polling flush() also learn the stream is dead.
            if self._adapter.client_gone.is_set():
                raise ClientGone("Il client ha chiuso lo stream.")

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
    handle_engine_overrides_get,
    handle_engine_overrides_set,
    handle_engine_overrides_clear,
    handle_engine_runtime_check,

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
FastAPIHandlerAdapter.handle_engine_overrides_get = handle_engine_overrides_get
FastAPIHandlerAdapter.handle_engine_overrides_set = handle_engine_overrides_set
FastAPIHandlerAdapter.handle_engine_overrides_clear = handle_engine_overrides_clear
FastAPIHandlerAdapter.handle_engine_runtime_check = handle_engine_runtime_check
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
FastAPIHandlerAdapter.handle_system_capabilities = handle_system_capabilities
FastAPIHandlerAdapter.handle_system_available_modules = handle_system_available_modules
FastAPIHandlerAdapter.handle_system_updates_check = handle_system_updates_check
FastAPIHandlerAdapter.handle_system_updates_apply = handle_system_updates_apply

# Core routes registration
register_get_handlers(FastAPIHandlerAdapter)
register_post_handlers(FastAPIHandlerAdapter)

# ==============================================================================
# sigma_model_hub — Modulo core sempre attivo
#
# Viene caricato qui direttamente, senza dipendere da marketplace_installed.json.
# Questo garantisce che /api/models/* funzioni su qualunque installazione fresca
# (Raspberry Pi, server remoto, clone da git) anche prima che l'utente abbia
# configurato il marketplace o salvato qualsiasi impostazione.
# ==============================================================================
try:
    from core.modules.sigma_model_hub.backend import handlers as _hub_handlers
    _hub_handlers.register_routes(app)
    log.info("[FastAPI] sigma_model_hub caricato come modulo core.")
except Exception as _hub_err:
    import traceback as _hub_tb
    log.warning(
        f"[FastAPI] sigma_model_hub non caricato (verrà riprovato dal ModuleLoader): "
        f"{type(_hub_err).__name__}: {_hub_err}\n{_hub_tb.format_exc()}"
    )

# Caricamento dinamico dei moduli opzionali installati (Training Lab, Creative Lab, Domotica, etc.)
_module_loader_error: str | None = None
try:
    from core.module_loader import ModuleLoader
    module_loader = ModuleLoader()
    module_loader.load_installed(app)
    log.info(f"[FastAPI] Moduli opzionali caricati: {module_loader.list_loaded()}")
except Exception as _mod_err:
    import traceback as _tb
    _module_loader_error = f"{type(_mod_err).__name__}: {_mod_err}\n{_tb.format_exc()}"
    log.warning(f"[FastAPI] Avviso inizializzazione ModuleLoader: {_mod_err}")


@app.get("/api/modules/status")
async def api_modules_status():
    """Diagnostica: quali moduli opzionali sono caricati e quali route /api/models/* sono registrate."""
    import os
    from core import paths

    # Leggi stato installazione
    installed: dict = {}
    try:
        import json as _json
        state_file = str(paths.installed_modules_file())
        if os.path.exists(state_file):
            with open(state_file, encoding="utf-8") as _f:
                installed = _json.load(_f)
    except Exception as _e:
        installed = {"error": str(_e)}

    # Moduli registrati nel loader
    loaded_modules: list = []
    try:
        loaded_modules = module_loader.list_loaded()
    except Exception:
        loaded_modules = ["(ModuleLoader non disponibile)"]

    # Route registrate
    model_get_routes = [p for p in FastAPIHandlerAdapter._GET_HANDLERS if p.startswith("/api/models")]
    model_post_routes = [p for p in FastAPIHandlerAdapter._POST_HANDLERS if p.startswith("/api/models")]
    total_get = len(FastAPIHandlerAdapter._GET_HANDLERS)
    total_post = len(FastAPIHandlerAdapter._POST_HANDLERS)

    return JSONResponse(status_code=200, content={
        "module_loader_error": _module_loader_error,
        "installed_state": installed,
        "loaded_modules": loaded_modules,
        "sigma_model_hub_active": "sigma_model_hub" in loaded_modules,
        "model_hub_get_routes": sorted(model_get_routes),
        "model_hub_post_routes": sorted(model_post_routes),
        "total_registered_get": total_get,
        "total_registered_post": total_post,
    })


# Endpoints whose handlers push SSE events on `wfile` instead of returning JSON.
# Missing entries here are silently swallowed: the handler writes into the queue,
# nobody drains it, and the client receives an empty 200.
SSE_ENDPOINTS = (
    "/api/chat",
    "/api/chat/loop",
    # Questi due scrivono frame SSE da sempre, ma non erano dichiarati qui:
    # il dispatcher li trattava come endpoint JSON, quindi l'adapter non aveva
    # coda ne' loop a cui consegnare e ogni frame finiva in una queue che
    # nessuno leggeva — accumulata in memoria per tutta la richiesta, mentre il
    # client riceveva solo la risposta finale.
    "/api/chat/execute",
    "/api/chat/execute_plan",
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
        loop = asyncio.get_running_loop()
        stream_queue = adapter.attach_stream(loop)

        def _run_in_thread():
            try:
                handler_fn()
                if adapter._response_data is not None:
                    res_data = dict(adapter._response_data)
                    if "response" in res_data and "token" not in res_data:
                        res_data["token"] = res_data["response"]
                    payload = json.dumps(res_data, ensure_ascii=False)
                    adapter.emit(f"data: {payload}\n\n")
                    adapter.emit("data: [DONE]\n\n")
            except ClientGone:
                # The reader left. The handler has already been told, through
                # the failed write, and stopped; there is nobody to report to.
                log.info("[FastAPI] Stream %s interrotto dal client.", request.url.path)
            except Exception as e:
                log.error("[FastAPI] Stream %s fallito: %s", request.url.path, e,
                          exc_info=True)
                try:
                    adapter.emit(f"data: {json.dumps({'error': str(e)})}\n\n")
                except Exception:
                    pass
            finally:
                # The sentinel must arrive even when the client is gone: it is
                # what lets the generator below finish instead of being garbage
                # collected mid-await.
                try:
                    loop.call_soon_threadsafe(stream_queue.put_nowait, None)
                except RuntimeError:
                    pass

        # A dedicated thread rather than a pool slot: this one is a user's chat
        # turn, it spends nearly all its life blocked on the engine's own queue,
        # and queueing it behind a pool would leave the request with no reply at
        # all -- not even the "engine busy" notice the runtime sends.
        threading.Thread(
            target=_run_in_thread, daemon=True,
            name=f"sigma-sse-{request.url.path}",
        ).start()

        async def sse_generator():
            try:
                while True:
                    item = await stream_queue.get()
                    if item is None:
                        break
                    yield item
            finally:
                # Reached on normal completion and on client disconnect alike.
                # Setting it is what turns an abandoned stream into a stopped
                # generation instead of one that runs to its full token budget
                # writing into a queue nobody reads.
                adapter.client_gone.set()

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Standard JSON dispatch. Its own pool, so a burst of long-running POSTs
    # cannot leave a status poll with no thread to run on.
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_api_executor, handler_fn)

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
    # Absent means "the model's own recipe", not 0.7: a client that omits a
    # knob is asking for the default, and answering with a number nobody chose
    # is how a checkpoint tuned for top_p 0.8 ends up served at 0.9.
    temperature = body.get("temperature")
    temperature = float(temperature) if temperature is not None else None
    max_tokens = int(body.get("max_tokens") or body.get("max_completion_tokens") or 4096)
    top_p = body.get("top_p")
    top_p = float(top_p) if top_p is not None else None

    if stream:
        async def sse_stream():
            try:
                async for chunk in _aiter_blocking(lambda: stream_openai_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    extra=body,
                )):
                    yield chunk
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
            top_p=top_p,
            extra=body,
        )
        status = 503 if isinstance(res, dict) and res.get("error") else 200
        return JSONResponse(status_code=status, content=res)


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
    max_tokens = int(body.get("max_tokens", 4096))

    # /v1/completions is the raw-text protocol: there is no place in it for a
    # persona, and a client using it is asking for a continuation of exactly
    # the string it sent.
    from core.engine.provider_server import (
        _estimate_tokens, _sampler_from_request, _thinking_from_request,
    )
    params = _sampler_from_request(model, body.get("temperature"), max_tokens,
                                   body.get("top_p"), body)
    thinking = _thinking_from_request(body)
    temperature = params.temperature

    messages = [{"role": "user", "content": str(prompt)}]
    if stream:
        async def sse_stream():
            req_id = f"cmpl-{uuid.uuid4().hex[:20]}"
            created_ts = int(time.time())
            from core.engine.unified_runtime import sigma_engine
            from core.engine.evaluation import is_notice
            async for chunk in _aiter_blocking(lambda: sigma_engine.generate_stream(
                prompt=str(prompt),
                system_prompt="",
                model_name=model,
                messages=messages,
                params=params,
                thinking=thinking,
            )):
                token = chunk.get("token", "")
                if is_notice(chunk) and not chunk.get("error"):
                    continue
                if token:
                    payload = {
                        "id": req_id,
                        "object": "text_completion",
                        "created": created_ts,
                        "model": model,
                        "choices": [{"text": token, "index": 0, "logprobs": None, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_stream(), media_type="text/event-stream; charset=utf-8")
    else:
        from core.engine.unified_runtime import sigma_engine
        # Collected on a worker thread: iterating the engine here would run the
        # whole generation on the event loop and stop the server answering
        # anything else until it finished.
        def _collect():
            from core.engine.evaluation import collect
            answer = collect(sigma_engine.generate_stream(
                prompt=str(prompt),
                system_prompt="",
                model_name=model,
                messages=messages,
                params=params,
                thinking=thinking,
            ))
            return [answer.text]

        tokens = await asyncio.get_running_loop().run_in_executor(
            _stream_executor, _collect
        )
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
                "prompt_tokens": _estimate_tokens(str(prompt)),
                "completion_tokens": _estimate_tokens(full_text),
                "total_tokens": _estimate_tokens(str(prompt)) + _estimate_tokens(full_text),
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
                async for chunk in _aiter_blocking(lambda: stream_ollama_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )):
                    yield chunk
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
                async for chunk in _aiter_blocking(lambda: stream_ollama_chat_generator(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )):
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
    from core.ai_providers import load_ai_config
    from core.ssl_manager import get_lan_ip
    import socket

    models = get_all_available_models()
    resident = sigma_engine.loaded_model_name or "Nessun modello caricato"
    is_enabled = is_provider_server_enabled()
    ai_cfg = load_ai_config()
    server_port = int(ai_cfg.get("provider_server_port") or ai_cfg.get("server_port") or 8000)
    server_host = str(ai_cfg.get("provider_server_host") or ai_cfg.get("server_host") or "0.0.0.0")
    proxy_alias = str(ai_cfg.get("sigma_proxy_alias") or "sigma")
    is_ssl = bool(ai_cfg.get("ssl_enabled", False))
    proto = "https" if is_ssl else "http"
    base_url = f"{proto}://{server_host}:{server_port}"

    local_lan_ip = "127.0.0.1"
    all_lan_ips = []
    try:
        local_lan_ip = get_lan_ip()
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            cand = info[4][0]
            if cand and not cand.startswith("127.") and cand not in all_lan_ips:
                all_lan_ips.append(cand)
    except Exception:
        pass

    if local_lan_ip not in all_lan_ips and local_lan_ip != "127.0.0.1":
        all_lan_ips.insert(0, local_lan_ip)

    lan_url = f"{proto}://{local_lan_ip}:{server_port}" if local_lan_ip != "127.0.0.1" else None

    try:
        from core.ssl_manager import ssl_status
        # ssl_status interroga il trust store del sistema: fuori dall'event loop.
        tls = await asyncio.to_thread(ssl_status)
    except Exception:
        tls = {}

    return JSONResponse(status_code=200, content={
        "success": True,
        "ssl_enabled": is_ssl,
        "ssl": tls,
        # Relativo: base_url puo' valere 0.0.0.0, che non e' un indirizzo raggiungibile.
        "ca_download_url": "/ssl/ca.crt",
        "lan_ca_download_url": f"{lan_url}/ssl/ca.crt" if lan_url else None,
        "engine_name": "SigmaEngine Universal Runtime",
        "version": "8.0",
        "provider_server_enabled": is_enabled,
        "status": "online" if is_enabled else "disabled",
        "active_backend": sigma_engine.active_backend,
        "resident_model": resident,
        "has_resident_model": sigma_engine.has_resident_model,
        "total_models_available": len(models),
        "available_models": models,
        "port": server_port,
        "host": server_host,
        "lan_ip": local_lan_ip if local_lan_ip != "127.0.0.1" else None,
        "all_lan_ips": all_lan_ips,
        "lan_url": lan_url,
        "is_bind_all": server_host in ("0.0.0.0", ""),
        "proxy_alias": proxy_alias,
        "proxy_model": ai_cfg.get("sigma_proxy_model") or "sigma",
        "endpoints": {
            "openai_base_url": f"{base_url}/v1",
            "openai_chat_url": f"{base_url}/v1/chat/completions",
            "openai_models_url": f"{base_url}/v1/models",
            "ollama_base_url": f"{base_url}",
            "ollama_chat_url": f"{base_url}/api/chat",
            "ollama_tags_url": f"{base_url}/api/tags",
            "ollama_generate_url": f"{base_url}/api/generate",
            "lan_openai_base_url": f"{lan_url}/v1" if lan_url else None,
            "lan_openai_chat_url": f"{lan_url}/v1/chat/completions" if lan_url else None,
        }
    })




# --- Sigma Network ---
# Il modulo ha dipendenze proprie: su un clone appena fatto non sono ancora
# installate, e prima un import fallito qui impediva l'avvio dell'intero Sigma
# Studio per un modulo opzionale.
try:
    from core.modules.sigma_network import router as sigma_network_router
    app.include_router(sigma_network_router, prefix="/api/sigma_network",
                       tags=["Sigma Network"])
except Exception as _sn_exc:
    # Exception e non ImportError soltanto: il modulo esegue codice al
    # caricamento -- identita', registro dei peer -- e un file di stato
    # illeggibile lo ferma senza essere un errore di import.
    log.warning("[FastAPI] Sigma Network non caricato: %s", _sn_exc, exc_info=True)
    from fastapi import APIRouter

    _SIGMA_NETWORK_MOTIVO = f"{type(_sn_exc).__name__}: {_sn_exc}"
    sigma_network_router = APIRouter()

    @sigma_network_router.api_route(
        "/{path:path}", methods=["GET", "POST", "PUT", "DELETE"]
    )
    async def _sigma_network_non_disponibile(path: str):
        # 503 col motivo, non 404: l'endpoint esiste, e' il modulo a non essere
        # partito. Un 404 muto e' indistinguibile da un errore di routing e
        # manda a cercare il guasto dalla parte sbagliata.
        return JSONResponse(status_code=503, content={
            "error": "Modulo Sigma Network non caricato.",
            "reason": _SIGMA_NETWORK_MOTIVO,
            "hint": "pip install -r core/modules/sigma_network/requirements.txt",
        })

    app.include_router(sigma_network_router, prefix="/api/sigma_network",
                       tags=["Sigma Network"])

# --- SSL / TLS: Certificate Authority locale ---

@app.get("/ssl/ca.crt")
@app.get("/api/ssl/ca.crt")
@app.get("/ssl/sigma-ca.pem")
async def ssl_ca_download_route():
    """GET /ssl/ca.crt — Scarica la CA locale da installare su PC, smartphone e tablet."""
    from core.ssl_manager import ensure_local_ca

    ca_path, _ = await asyncio.to_thread(ensure_local_ca)
    if not ca_path or not ca_path.exists():
        return JSONResponse(status_code=503, content={
            "error": "Certificate Authority locale non disponibile.",
            "hint": "Verifica che il pacchetto 'cryptography' sia installato.",
        })
    # Il media type x-x509-ca-cert fa aprire la procedura guidata di installazione
    # su Windows, Android e iOS invece di mostrare il file come testo.
    return FileResponse(
        path=str(ca_path),
        media_type="application/x-x509-ca-cert",
        filename="sigma-studio-ca.crt",
    )


@app.get("/api/ssl/status")
async def ssl_status_route():
    """GET /api/ssl/status — Stato della CA locale e dei certificati HTTPS."""
    from core.ssl_manager import ssl_status

    return JSONResponse(status_code=200, content=await asyncio.to_thread(ssl_status))


@app.post("/api/ssl/install_ca")
async def ssl_install_ca_route():
    """POST /api/ssl/install_ca — Installa la CA locale nel trust store di questa macchina."""
    from core.ssl_manager import install_ca_into_trust_store, ssl_status

    ok, message = await asyncio.to_thread(install_ca_into_trust_store)
    return JSONResponse(status_code=200 if ok else 500, content={
        "success": ok,
        "message": message,
        "status": await asyncio.to_thread(ssl_status),
    })


@app.post("/api/ssl/regenerate")
async def ssl_regenerate_route():
    """POST /api/ssl/regenerate — Rigenera il certificato del server (nuovi IP LAN, scadenza)."""
    from core.ssl_manager import generate_server_cert, ssl_status

    ok = await asyncio.to_thread(generate_server_cert)
    return JSONResponse(status_code=200 if ok else 500, content={
        "success": ok,
        "message": ("Certificato rigenerato. Riavvia il server per applicarlo."
                    if ok else "Rigenerazione del certificato non riuscita."),
        "status": await asyncio.to_thread(ssl_status),
    })


# --- System Cleanup & Resource Optimization ---
from core.system_cleanup import get_cleanup_stats, execute_selective_cleanup

@app.get("/api/system/cleanup/stats")
async def system_cleanup_stats_route(request: Request):
    stats = await asyncio.to_thread(get_cleanup_stats)
    return JSONResponse(status_code=200, content=stats)

@app.post("/api/system/cleanup/execute")
@app.post("/api/system/clear-memory")
async def system_cleanup_execute_route(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    res = await asyncio.to_thread(execute_selective_cleanup, body)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


@app.post("/api/system/restart")
async def system_restart_route(request: Request):
    """POST /api/system/restart — Riavvia il server di Sigma Studio e notifica il client."""
    import sys
    import os
    import subprocess
    import threading
    import time
    from core.paths import project_root
    from core.config_handler import load_ai_config
    from core.ssl_manager import get_lan_ip

    ai_cfg = load_ai_config()
    server_port = int(ai_cfg.get("provider_server_port") or ai_cfg.get("server_port") or 8000)
    is_ssl = bool(ai_cfg.get("ssl_enabled", False))
    proto = "https" if is_ssl else "http"
    lan_ip = get_lan_ip()
    target_url = f"{proto}://localhost:{server_port}"
    target_lan_url = f"{proto}://{lan_ip}:{server_port}" if lan_ip != "127.0.0.1" else target_url

    def _restart_process():
        time.sleep(0.8)
        log.info("[System] Riavvio del server Sigma Studio in corso...")
        try:
            py_exe = sys.executable
            root = str(project_root())
            if os.name == "nt":
                # Su Windows avvia detached senza bloccare il processo padre
                flags = 0
                if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                    flags |= subprocess.CREATE_NEW_PROCESS_GROUP
                if hasattr(subprocess, "DETACHED_PROCESS"):
                    flags |= subprocess.DETACHED_PROCESS
                subprocess.Popen(
                    [py_exe, "sigma_server.py"],
                    cwd=root,
                    creationflags=flags,
                    close_fds=True
                )
            else:
                subprocess.Popen(
                    [py_exe, "sigma_server.py"],
                    cwd=root,
                    start_new_session=True,
                    close_fds=True
                )
        except Exception as exc:
            log.error("[System] Errore avvio nuovo processo: %s", exc)
        finally:
            os._exit(0)

    t = threading.Thread(target=_restart_process, daemon=True)
    t.start()

    return JSONResponse(status_code=200, content={
        "success": True,
        "message": "Server in riavvio...",
        "target_url": target_url,
        "target_lan_url": target_lan_url,
        "port": server_port,
        "ssl_enabled": is_ssl,
        "protocol": proto
    })


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
from core import paths as _paths
_ROOT = _paths.project_root()
DIST_DIR = _paths.frontend_dist_dir()


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
