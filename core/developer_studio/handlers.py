# ==============================================================================
# core/developer_studio/handlers.py — FastAPI Handlers for Developer Studio
# Sigma Studio v8 — Developer Studio API Endpoints
# ==============================================================================
"""Registers and exposes all REST and SSE streaming endpoints for Developer Studio."""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from core.logger import get_logger
from core.developer_studio.fs_manager import (
    get_workspace_tree,
    read_file_content,
    write_file_content,
    delete_fs_entry,
    create_fs_entry,
    rename_fs_entry,
    search_workspace_files,
    get_default_workspace_root
)
from core.developer_studio.terminal_runner import execute_shell_command_sync, stream_shell_command
from core.developer_studio.admin_agent import stream_admin_agent_turn, execute_admin_tool

log = get_logger("developer_handlers")


async def handle_fs_tree(request: Request):
    """GET /api/developer/fs/tree?path=<optional> — Returns workspace directory tree."""
    path = request.query_params.get("path") or get_default_workspace_root()
    depth = int(request.query_params.get("depth", 4))
    tree = await asyncio.to_thread(get_workspace_tree, path, depth)
    return JSONResponse(status_code=200, content={"success": True, "tree": tree, "root": path})


async def handle_fs_read(request: Request):
    """GET /api/developer/fs/read?path=<file_path> — Reads file content in admin mode."""
    path = request.query_params.get("path")
    if not path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'path' mancante."})
    res = await asyncio.to_thread(read_file_content, path)
    return JSONResponse(status_code=200 if res.get("success") else 400, content=res)


async def handle_fs_raw(request: Request):
    """GET /api/developer/fs/raw?path=<file_path> — Serves raw binary files (images, audio, video)."""
    from fastapi.responses import FileResponse
    path = request.query_params.get("path")
    if not path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'path' mancante."})
    p = Path(path).resolve()
    if not p.exists() or p.is_dir():
        return JSONResponse(status_code=404, content={"success": False, "error": "File non trovato."})
    return FileResponse(str(p))


async def handle_fs_write(request: Request):
    """POST /api/developer/fs/write — Writes content to a file."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = body.get("path")
    content = body.get("content", "")
    if not path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'path' mancante."})
    res = await asyncio.to_thread(write_file_content, path, content)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


async def handle_fs_delete(request: Request):
    """POST /api/developer/fs/delete — Deletes a file or directory in admin mode."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = body.get("path")
    recursive = bool(body.get("recursive", True))
    if not path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'path' mancante."})
    res = await asyncio.to_thread(delete_fs_entry, path, recursive)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


async def handle_fs_create(request: Request):
    """POST /api/developer/fs/create — Creates an empty file or folder."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = body.get("path")
    is_dir = bool(body.get("is_dir", False))
    if not path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'path' mancante."})
    res = await asyncio.to_thread(create_fs_entry, path, is_dir)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


async def handle_fs_rename(request: Request):
    """POST /api/developer/fs/rename — Renames or moves a file or folder."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    old_path = body.get("old_path") or body.get("source_path")
    new_path = body.get("new_path") or body.get("target_path")
    if not old_path or not new_path:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametri 'old_path' e 'new_path' richiesti."})
    res = await asyncio.to_thread(rename_fs_entry, old_path, new_path)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


async def handle_fs_search(request: Request):
    """POST /api/developer/fs/search — Searches workspace files."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", "")
    path = body.get("path") or get_default_workspace_root()
    is_regex = bool(body.get("is_regex", False))
    res = await asyncio.to_thread(search_workspace_files, path, query, is_regex)
    return JSONResponse(status_code=200 if res.get("success") else 500, content=res)


async def handle_terminal_exec(request: Request):
    """POST /api/developer/terminal/exec — Executes a shell command synchronously or streaming."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    command = body.get("command", "")
    cwd = body.get("cwd") or get_default_workspace_root()
    stream = bool(body.get("stream", False))

    if not command:
        return JSONResponse(status_code=400, content={"success": False, "error": "Parametro 'command' richiesto."})

    if stream:
        async def sse_gen():
            for item in stream_shell_command(command, cwd):
                yield f"data: {json.dumps(item)}\n\n"
                await asyncio.sleep(0.001)

        return StreamingResponse(
            sse_gen(),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    else:
        res = await asyncio.to_thread(execute_shell_command_sync, command, cwd)
        return JSONResponse(status_code=200, content=res)


async def handle_agent_chat(request: Request):
    """POST /api/developer/agent/chat — Streams Admin AI Developer Agent reasoning and tools."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    messages = body.get("messages", [])
    workspace_root = body.get("workspace_root") or get_default_workspace_root()
    model = body.get("model") or "sigmaengine"
    auto_execute = bool(body.get("auto_execute_tools", True))

    async def sse_stream():
        try:
            for event in stream_admin_agent_turn(
                messages=messages,
                workspace_root=workspace_root,
                model_name=model,
                auto_execute_tools=auto_execute
            ):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0.001)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


async def handle_workspace_roots(request: Request):
    """GET /api/developer/workspace/roots — Lists suggested workspace roots and drives."""
    roots = []
    default_root = get_default_workspace_root()
    roots.append({"label": f"Project Root ({Path(default_root).name})", "path": default_root.replace("\\", "/")})
    
    # Windows drive roots (C:/, D:/, etc.) or home
    home = str(Path.home())
    roots.append({"label": f"User Home ({Path(home).name})", "path": home.replace("\\", "/")})

    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                roots.append({"label": f"Drive {letter}:", "path": f"{letter}:/"})

    return JSONResponse(status_code=200, content={"success": True, "roots": roots, "current": default_root.replace("\\", "/")})


def _get_tasks_filepath() -> Path:
    base = Path(get_default_workspace_root()) / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "developer_tasks.json"


async def handle_get_tasks(request: Request):
    """GET /api/developer/tasks — Returns all developer tasks saved on server."""
    fp = _get_tasks_filepath()
    tasks = []
    if fp.exists():
        try:
            tasks = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not read developer_tasks.json: %s", e)
    return JSONResponse(status_code=200, content={"success": True, "tasks": tasks})


async def handle_save_tasks(request: Request):
    """POST /api/developer/tasks — Persists developer tasks to server disk."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tasks = body.get("tasks", [])
    fp = _get_tasks_filepath()
    try:
        fp.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        return JSONResponse(status_code=200, content={"success": True})
    except Exception as e:
        log.error("Could not write developer_tasks.json: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
