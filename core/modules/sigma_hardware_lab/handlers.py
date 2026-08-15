# ==============================================================================
# sigma_hardware_lab/backend/handlers.py
# HTTP routes & MCP server registration for Hardware Lab & VRAM Telemetry
# ==============================================================================
from __future__ import annotations
import os
import json
from core.logger import get_logger

log = get_logger(__name__)


def register_routes(app=None) -> None:
    """Registra tutte le route HTTP di Hardware Lab su FastAPI / Handler Adapter."""
    from core.training_api import (
        handle_hardware_status,
        handle_hardware_config,
        handle_hardware_restart_ollama,
        handle_hardware_gpu_processes,
        handle_hardware_gpu_kill,
    )

    get_routes = {
        '/api/hardware/status': handle_hardware_status,
        '/api/hardware/restart-ollama': handle_hardware_restart_ollama,
        '/api/hardware/gpu/processes': handle_hardware_gpu_processes,
        '/api/hardware/gpu-processes': handle_hardware_gpu_processes,
    }

    post_routes = {
        '/api/hardware/config': handle_hardware_config,
        '/api/hardware/restart-ollama': handle_hardware_restart_ollama,
        '/api/hardware/gpu/kill': handle_hardware_gpu_kill,
        '/api/hardware/kill-process': handle_hardware_gpu_kill,
        '/api/hardware/kill_process': handle_hardware_gpu_kill,
    }

    try:
        from core.fastapi_app import FastAPIHandlerAdapter
        for path, fn in get_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._GET_HANDLERS[path] = fn.__name__
        for path, fn in post_routes.items():
            setattr(FastAPIHandlerAdapter, fn.__name__, fn)
            FastAPIHandlerAdapter._POST_HANDLERS[path] = fn.__name__
        log.info('[sigma_hardware_lab] Route Hardware collegate a FastAPIHandlerAdapter.')
    except Exception as e:
        log.warning(f'[sigma_hardware_lab] Avviso binding FastAPIHandlerAdapter: {e}')


def register_mcp(mcp_hub) -> None:
    """Registra il server MCP di Hardware Lab nell'hub MCP del kernel."""
    try:
        from .mcp_server import HardwareMCPServer
        mcp_hub.register_server(HardwareMCPServer)
        log.info('[sigma_hardware_lab] Hardware MCP Server registrato.')
    except Exception as e:
        log.warning(f'[sigma_hardware_lab] Hardware MCP Server non registrato: {e}')
