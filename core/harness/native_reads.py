"""Letture native opzionali, limitate allo stesso workspace del run."""
from __future__ import annotations
import json
import mmap
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import threading
import time
import tempfile
import urllib.request

from core.logger import get_logger

log = get_logger(__name__)
_lock = threading.Lock()
_cached = {}


def _normal_path(value):
    value=str(value).replace("\\","/")
    return value[4:] if value.startswith("//?/") else value


def _post(path: str, body=None):
    from core.engine.backends.sigmarust_backend import _DEFAULT_RUST_URL, _intestazioni
    request = urllib.request.Request(os.environ.get("SIGMA_RUST_ENGINE_URL",_DEFAULT_RUST_URL) + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=_intestazioni({"Content-Type":"application/json"}))
    with urllib.request.urlopen(request, timeout=0.5) as response:
        return json.load(response)


def _capabilities():
    with _lock:
        if time.monotonic() >= _cached.get("expires", 0):
            try:
                _cached["value"] = _post("/api/engine/status").get("native_tools") or {}
            except (OSError, ValueError) as error:
                log.debug("Letture native non disponibili: %s",error)
                _cached["value"] = {}
            _cached["expires"] = time.monotonic() + 15
        return dict(_cached["value"])


def read_mapping(descriptor: dict, remote_root: str, local_root: Path) -> str:
    remote_root=_normal_path(remote_root)
    path_type=PureWindowsPath if PureWindowsPath(remote_root).drive else PurePosixPath
    relative = path_type(_normal_path(descriptor["path"])).relative_to(path_type(remote_root))
    root = local_root.resolve()
    path = root.joinpath(*relative.parts).resolve()
    path.relative_to(root)
    length = descriptor["length"]
    if isinstance(length,bool) or not isinstance(length,int) or not 0 <= length <= 16 * 1024 * 1024:
        raise ValueError("Lunghezza del buffer condiviso non valida")
    with path.open("rb") as source:
        if source.seek(0,2) < max(1,length):
            raise ValueError("Buffer condiviso troncato")
        with mmap.mmap(source.fileno(),0,access=mmap.ACCESS_READ) as mapping:
            return mapping[:length].decode("utf-8")


def try_read_slice(path: Path, offset: int, limit: int, workspace: Path):
    try:
        path, workspace = path.resolve(), workspace.resolve()
        relative = path.relative_to(workspace)
        if path.stat().st_size < 512 * 1024 or path.stat().st_size > 5 * 1024 * 1024:
            return None
        caps = _capabilities()
        remote = caps.get("workspace_root")
        if not remote:
            return None
        remote=_normal_path(remote)
        host_root = Path(_normal_path(os.environ.get("SIGMA_RUST_HOST_WORKSPACE",remote))).resolve()
        if host_root != workspace:
            return None
        remote_path = str(PurePosixPath(remote.replace("\\","/")).joinpath(*relative.parts))
        shared_remote = _normal_path(caps.get("shared_buffer_root") or "")
        shared_host = Path(os.environ.get("SIGMA_RUST_HOST_SHARED",shared_remote))
        # Su disco Windows il costo di creare un mapping supera quello della copia della finestra.
        mapped = bool(os.environ.get("SIGMA_NATIVE_READ_MMAP") == "1" and shared_remote and shared_host.is_absolute() and limit >= 256)
        params={"path":remote_path,"offset":offset,"limit":limit,
                "inline":not mapped,"transfer":"mmap" if mapped else "inline"}
        ffi_root=os.environ.get("SIGMA_WORKSPACE_ROOT")
        response=None
        if ffi_root and Path(ffi_root).resolve()==workspace and host_root==Path(remote).resolve():
            from core.engine.backends.sigma_ffi import execute_tool_ffi
            response=execute_tool_ffi("fast_read_file",params)
        ffi_used=bool(response and response.get("success"))
        if not ffi_used:
            response=_post("/api/engine/tools/execute",{"tool":"fast_read_file","params":params})
        result = response.get("result") or {}
        handle=result.get("buffer_handle")
        try:
            if not response.get("success") or not result.get("success") or result.get("truncated") or result.get("python_lines_compatible") is not True:
                return None
            content=result.get("content")
            mapped=bool(result.get("mapping"))
            if mapped and ffi_used:
                shared_remote=_normal_path(os.environ.get("SIGMA_SHARED_BUFFER_DIR") or str(Path(tempfile.gettempdir())/f"sigma-shared-{os.getpid()}"))
                shared_host=Path(shared_remote)
            if mapped:
                content=read_mapping(result["mapping"],shared_remote,shared_host)
            if not isinstance(content,str) or not isinstance(result.get("total_lines"),int):
                return None
            return {"success":True,"content":content,"total_lines":result["total_lines"],
                    "path":str(path).replace("\\","/"),"filename":path.name,
                    "extension":path.suffix.lstrip("."),"size":path.stat().st_size,
                    "is_binary":False,"native_slice":True,"native_transport":"file_mmap" if mapped else ("ffi" if ffi_used else "http")}
        finally:
            if handle is not None:
                if ffi_used:
                    execute_tool_ffi("direct_memory_pipe",{"op":"evict","handle":handle})
                else:
                    _post("/api/engine/tools/execute",{"tool":"direct_memory_pipe","params":{"op":"evict","handle":handle}})
    except (OSError, ValueError, KeyError, TypeError) as error:
        log.debug("Ripiego sulla lettura locale: %s",error)
        return None
