# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/runtime_server.py — Runtime Inspector & Hot-Reload MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP Server per l'ispezione in tempo reale e la modifica a caldo (hot-reload) del runtime.

Consente agli agenti e all'utente di visionare lo stato in memoria del sistema
(thread attivi, memoria allocata, moduli importati in sys.modules) e di ricaricare
a caldo componenti Python o modificare configurazioni di runtime senza riavviare
il server principale.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import threading
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE

log = get_logger(__name__)


def _get_memory_usage_mb() -> float:
    """Restituisce l'uso della memoria RSS del processo corrente in MB."""
    try:
        import psutil
        process = psutil.Process()
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


class RuntimeInspectorMCPServer(BaseMCPServer):
    """Server MCP per l'ispezione dello stato in memoria e l'hot-reloading."""

    def __init__(self):
        super().__init__(
            name="runtime_inspector_server",
            version="1.0.0",
            description="Ispezione runtime dello stato in memoria (thread, moduli, heap) e hot-reload a caldo senza riavvio.",
        )

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "inspect_runtime_state",
                "description": "Fornisce una fotografia completa dello stato a runtime: memoria RSS, thread attivi, moduli caricati e stato del motore.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter_prefix": {
                            "type": "string",
                            "description": "Filtra i moduli per prefisso (es. 'core.', 'sigma_'). Default: 'core.'",
                            "default": "core.",
                        },
                    },
                },
            },
            {
                "name": "hot_reload_module",
                "description": "Ricarica a caldo un modulo Python in sys.modules tramite importlib.reload senza riavviare il server.",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string", "description": "Nome completo del modulo da ricaricare (es. 'core.engine.unified_runtime')."},
                    },
                    "required": ["module_name"],
                },
            },
            {
                "name": "inspect_symbol",
                "description": "Ispeziona a runtime un simbolo o classe (metodi, parametri, docstring, tipo) caricato nel processo.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol_path": {"type": "string", "description": "Percorso qualificato (es. 'core.harness.loop.stream_admin_agent_turn')."},
                    },
                    "required": ["symbol_path"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "inspect_runtime_state":
            return self._tool_inspect_state(arguments)
        elif name == "hot_reload_module":
            return self._tool_hot_reload(arguments)
        elif name == "inspect_symbol":
            return self._tool_inspect_symbol(arguments)
        return {"success": False, "error": f"Tool sconosciuto: {name}"}

    def _tool_inspect_state(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prefix = str(args.get("filter_prefix", "core."))

        # 1. Moduli caricati
        loaded_modules = [m for m in sorted(sys.modules.keys()) if m.startswith(prefix)]

        # 2. Thread attivi
        threads_info = []
        for t in threading.enumerate():
            threads_info.append({
                "name": t.name,
                "ident": t.ident,
                "daemon": t.daemon,
                "alive": t.is_alive(),
            })

        # 3. Memoria
        rss_mb = _get_memory_usage_mb()

        return {
            "success": True,
            "python_version": sys.version.split()[0],
            "rss_memory_mb": rss_mb,
            "active_threads_count": len(threads_info),
            "active_threads": threads_info,
            "loaded_modules_matching_count": len(loaded_modules),
            "loaded_modules": loaded_modules[:60],
            "total_sys_modules": len(sys.modules),
            "message": f"Runtime attivo: {rss_mb} MB RSS, {len(threads_info)} thread, {len(loaded_modules)} moduli '{prefix}' in memoria.",
        }

    def _tool_hot_reload(self, args: Dict[str, Any]) -> Dict[str, Any]:
        module_name = str(args.get("module_name", "")).strip()
        if not module_name:
            return {"success": False, "error": "Parametro 'module_name' obbligatorio."}

        if module_name not in sys.modules:
            # Prova a importarlo prima
            try:
                mod = importlib.import_module(module_name)
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Modulo '{module_name}' non presente in memoria e impossibile importarlo: {exc}",
                }
        else:
            mod = sys.modules[module_name]

        try:
            reloaded = importlib.reload(mod)
            file_path = getattr(reloaded, "__file__", "builtin")
            log.info("[RuntimeInspector] Modulo '%s' ricaricato a caldo da %s", module_name, file_path)
            return {
                "success": True,
                "module_name": module_name,
                "file": file_path,
                "message": f"Modulo '{module_name}' ricaricato a caldo con successo a runtime.",
            }
        except Exception as exc:
            log.error("[RuntimeInspector] Fallito hot-reload di '%s': %s", module_name, exc)
            return {
                "success": False,
                "module_name": module_name,
                "error": f"Errore durante l'hot-reload: {exc}",
            }

    def _tool_inspect_symbol(self, args: Dict[str, Any]) -> Dict[str, Any]:
        symbol_path = str(args.get("symbol_path", "")).strip()
        if not symbol_path:
            return {"success": False, "error": "Parametro 'symbol_path' obbligatorio."}

        parts = symbol_path.split(".")
        if len(parts) < 2:
            return {"success": False, "error": "Il percorso deve contenere almeno modulo.simbolo"}

        mod_name = ".".join(parts[:-1])
        target_name = parts[-1]

        try:
            if mod_name not in sys.modules:
                mod = importlib.import_module(mod_name)
            else:
                mod = sys.modules[mod_name]

            obj = getattr(mod, target_name)
            doc = inspect.getdoc(obj) or ""
            is_func = inspect.isfunction(obj) or inspect.ismethod(obj)
            is_cls = inspect.isclass(obj)

            sig = ""
            if is_func or is_cls:
                try:
                    sig = str(inspect.signature(obj))
                except Exception:
                    sig = "(...)"

            members = []
            if is_cls:
                for m_name, m_val in inspect.getmembers(obj):
                    if not m_name.startswith("__"):
                        members.append(m_name)

            return {
                "success": True,
                "symbol": symbol_path,
                "type": "function" if is_func else ("class" if is_cls else str(type(obj))),
                "signature": f"{target_name}{sig}" if sig else target_name,
                "docstring": doc[:1000],
                "members": members[:30] if members else None,
            }
        except Exception as exc:
            return {
                "success": False,
                "symbol": symbol_path,
                "error": f"Impossibile ispezionare '{symbol_path}': {exc}",
            }
