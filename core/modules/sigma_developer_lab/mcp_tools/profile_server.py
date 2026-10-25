# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/profile_server.py — Profiling MCP
# Sigma Studio v8 — Developer Studio AI-Native IDE
# =============================================================================
"""MCP server per il profiling applicativo.

Il tool `profile_app` esegue un profiling non invasivo (SAFE) di una funzione
Python o di un endpoint HTTP: misura tempo di esecuzione, picco di memoria,
count di chiamate e fornisce un riepilogo strutturato. Non modifica nulla:
solo esegue e riporta.
"""

import cProfile
import importlib
import io
import pstats
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE

log = get_logger(__name__)


def _get_peak_memory_kb() -> int:
    """Restituisce il picco di memoria in KB, cross-platform.

    Usa psutil se disponibile, altrimenti resource su Unix. Su Windows
    senza psutil restituisce 0 — mai far esplodere un import di modulo.
    """
    try:
        import psutil
        proc = psutil.Process()
        if sys.platform == "win32":
            return proc.memory_info().peak_wset // 1024
        return proc.memory_info().rss // 1024
    except (ImportError, AttributeError):
        pass
    if sys.platform != "win32":
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:
            pass
    return 0


def _profile_function(func_path: str, args: Optional[List[Any]] = None,
                      kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Profila una funzione Python specificata per percorso (modulo.funzione)."""
    args = args or []
    kwargs = kwargs or {}

    try:
        module_path, func_name = func_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Impossibile importare la funzione '{func_path}': {exc}",
        }

    profiler = cProfile.Profile()
    mem_before = _get_peak_memory_kb()
    start_time = time.perf_counter()

    try:
        profiler.runcall(func, *args, **kwargs)
    except Exception as exc:
        return {
            "success": False,
            "error": f"Errore durante l'esecuzione di '{func_path}': {exc}",
        }

    duration_ms = (time.perf_counter() - start_time) * 1000
    mem_after = _get_peak_memory_kb()

    # stats.stats: dict con chiave (filename, line_number, function_name)
    # e valore (primitive_calls, total_calls, total_time, cumulative_time, callers)
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")

    top_functions = []
    for (filename, lineno, fname), (cc, nc, tt, ct, _callers) in stats.stats.items():
        top_functions.append({
            "function": f"{fname} ({Path(filename).name}:{lineno})",
            "calls": nc,
            "total_time_s": round(tt, 6),
            "cumulative_time_s": round(ct, 6),
        })
    top_functions.sort(key=lambda x: x["cumulative_time_s"], reverse=True)

    return {
        "success": True,
        "function": func_path,
        "duration_ms": round(duration_ms, 2),
        "peak_memory_delta_kb": max(0, mem_after - mem_before),
        "top_functions": top_functions[:10],
        "total_calls": sum(nc for (_, nc, _, _, _) in stats.stats.values()),
    }


def _profile_http_endpoint(url: str, method: str = "GET",
                           timeout: float = 10.0) -> Dict[str, Any]:
    """Profila un endpoint HTTP: tempo di risposta, dimensione payload, status code."""
    import urllib.request

    start_time = time.perf_counter()
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            end_time = time.perf_counter()

            return {
                "success": True,
                "url": url,
                "method": method,
                "status_code": resp.status,
                "duration_ms": round((end_time - start_time) * 1000, 2),
                "payload_bytes": len(body),
                "content_type": resp.headers.get("Content-Type", "unknown"),
            }
    except Exception as exc:
        end_time = time.perf_counter()
        return {
            "success": False,
            "url": url,
            "method": method,
            "duration_ms": round((end_time - start_time) * 1000, 2),
            "error": str(exc),
        }


class ProfileMCPServer(BaseMCPServer):
    """MCP server per il profiling applicativo."""

    def __init__(self):
        super().__init__(
            name="profile",
            version="1.0.0",
            description="Profiling applicativo: timing, memoria, CPU",
        )
        self.register_tool(
            name="profile_app",
            description=(
                "Profila una funzione Python o un endpoint HTTP. "
                "Misura tempo, memoria e fornisce top funzioni per costo."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "target_type": {
                        "type": "string",
                        "enum": ["function", "http"],
                        "description": "Tipo di target da profilare",
                    },
                    "target": {
                        "type": "string",
                        "description": "Percorso funzione (modulo.funzione) o URL endpoint",
                    },
                    "args": {
                        "type": "array",
                        "description": "Argomenti posizionali (solo per function)",
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "Argomenti keyword (solo per function)",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                        "description": "Metodo HTTP (solo per http)",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in secondi (default 10)",
                    },
                },
                "required": ["target_type", "target"],
            },
            handler=self._handle_profile_app,
            safety=SAFE,
        )

    def _handle_profile_app(self, **kwargs) -> Dict[str, Any]:
        target_type = kwargs.get("target_type")
        target = kwargs.get("target")

        if target_type == "function":
            return _profile_function(
                target, kwargs.get("args"), kwargs.get("kwargs")
            )
        elif target_type == "http":
            return _profile_http_endpoint(
                target, kwargs.get("method", "GET"), kwargs.get("timeout", 10.0)
            )
        else:
            return {"success": False, "error": f"target_type non valido: {target_type}"}

