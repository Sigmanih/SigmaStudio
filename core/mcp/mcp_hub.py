# ==============================================================================
# core/mcp/mcp_hub.py — Central MCP Router, Multiplexer & Policy Gate
# ==============================================================================
"""Il punto unico da cui passa ogni strumento, interno o esterno.

L'hub fa tre cose che prima erano sparse o non esistevano:

* **registra** i server interni e quelli di terze parti configurati dall'utente;
* **filtra** — un tool spento qui è spento per tutti, agenti compresi, perché
  il controllo sta davanti all'esecuzione e non dentro un prompt;
* **ferma** i tool sensibili in attesa di un assenso umano, a meno che
  l'operatore non abbia scelto la modalità automatica.
"""

import threading
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp import governance
from core.mcp.base_server import BaseMCPServer
from core.mcp.calendar_server import CalendarMCPServer
from core.mcp.client import ExternalMCPServer
from core.mcp.developer_server import DeveloperMCPServer
from core.mcp.email_server import EmailMCPServer
from core.mcp.inference_server import InferenceMCPServer
from core.mcp.memory_server import MemoryMCPServer
from core.mcp.messaging_server import MessagingMCPServer
from core.mcp.network_server import NetworkMCPServer

log = get_logger(__name__)

# Built-in kernel servers
BUILTIN_SERVERS = [
    MemoryMCPServer,
    DeveloperMCPServer,
    InferenceMCPServer,
    NetworkMCPServer,
    EmailMCPServer,
    MessagingMCPServer,
    CalendarMCPServer,
]





class MCPHub:
    """Central manager, router and policy gate for every MCP server."""

    def __init__(self):
        self.servers: Dict[str, BaseMCPServer] = {}
        self.external: Dict[str, ExternalMCPServer] = {}
        self._lock = threading.RLock()
        self._initialize_servers()
        self.reload_external_servers()

    def register_server(self, server_cls_or_instance) -> bool:
        """Registra dinamicamente un server MCP da un modulo opzionale."""
        try:
            if isinstance(server_cls_or_instance, type):
                server = server_cls_or_instance()
            else:
                server = server_cls_or_instance
            with self._lock:
                self.servers[server.name] = server
            log.info("Dynamically Registered Module MCP Server: '%s' (v%s)", server.name, server.version)
            return True
        except Exception as exc:
            log.error("Errore registrazione server MCP dinamico: %s", exc, exc_info=True)
            return False


    def _initialize_servers(self):
        for server_cls in BUILTIN_SERVERS:
            try:
                server = server_cls()
            except Exception as exc:
                # One broken server must not take the whole hub — and the chat —
                # down with it at import time.
                log.error("MCP server '%s' non inizializzato: %s", server_cls.__name__, exc, exc_info=True)
                continue
            self.servers[server.name] = server
            log.info("Registered MCP Server: '%s' (v%s)", server.name, server.version)

    # --- external servers ----------------------------------------------------

    def reload_external_servers(self) -> List[Dict[str, Any]]:
        """Rebuild the third-party server list from config.json.

        Connecting is deliberately left to the caller: listing the tab should
        not spawn a dozen child processes.
        """
        with self._lock:
            specs = governance.load_mcp_config().get("external_servers", [])
            wanted = {spec.get("id"): spec for spec in specs if spec.get("id")}

            for server_id in list(self.external):
                if server_id not in wanted:
                    self.external.pop(server_id).disconnect()

            for server_id, spec in wanted.items():
                existing = self.external.get(server_id)
                if existing and existing.spec == spec:
                    continue
                if existing:
                    existing.disconnect()
                self.external[server_id] = ExternalMCPServer(spec)

            return [s.connection_status() for s in self.external.values()]

    def connect_external(self, server_id: str, force: bool = True) -> Dict[str, Any]:
        server = self.external.get(server_id)
        if not server:
            return {"connected": False, "error": f"Server esterno '{server_id}' sconosciuto."}
        result = server.connect(force=force)
        return {**server.connection_status(), **result}

    def _all_servers(self) -> List[BaseMCPServer]:
        return list(self.servers.values()) + list(self.external.values())

    def get_server(self, server_name: str) -> Optional[BaseMCPServer]:
        if server_name in self.servers:
            return self.servers[server_name]
        for server in self.external.values():
            if server.name == server_name or server.server_id == server_name:
                return server
        return None

    # --- listing -------------------------------------------------------------

    def list_all_servers(self) -> List[Dict[str, Any]]:
        """Status of every server, with what the tab needs to configure it."""
        cfg = governance.load_mcp_config()
        disabled_servers = set(cfg.get("disabled_servers", []))
        entries = []

        for server in self._all_servers():
            external = isinstance(server, ExternalMCPServer)
            entry = {
                "name": server.name,
                "version": server.version,
                "description": server.description,
                "tools_count": len(server.list_tools()),
                "resources_count": len(server.list_resources()),
                "enabled": server.name not in disabled_servers,
                "external": external,
                "integration_key": getattr(server, "integration_key", ""),
                "config_fields": getattr(server, "config_fields", []),
                "configured": True,
                "missing_dependency": None,
            }
            try:
                entry["configured"] = server.is_configured()
                entry["missing_dependency"] = server.missing_dependency()
            except Exception as exc:
                entry["configured"] = False
                entry["error"] = str(exc)
            if external:
                entry["connection"] = server.connection_status()
            entries.append(entry)

        return entries

    def get_aggregated_tools(self, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """Every tool across every server, annotated with its origin and policy."""
        cfg = governance.load_mcp_config()
        disabled_tools = set(cfg.get("disabled_tools", []))
        disabled_servers = set(cfg.get("disabled_servers", []))

        tools = []
        for server in self._all_servers():
            server_off = server.name in disabled_servers
            for tool in server.list_tools():
                enabled = not server_off and tool["name"] not in disabled_tools
                if only_enabled and not enabled:
                    continue
                entry = dict(tool)
                entry["server"] = server.name
                entry["enabled"] = enabled
                entry["external"] = isinstance(server, ExternalMCPServer)
                entry.setdefault("safety", governance.SAFE)
                try:
                    entry["ready"] = server.is_configured()
                except Exception:
                    entry["ready"] = False
                tools.append(entry)
        return tools

    def list_all_tools(self) -> List[Dict[str, Any]]:
        return self.get_aggregated_tools()

    def get_agent_tools(self) -> List[Dict[str, Any]]:
        """Tools an agent may actually use: switched on and able to run."""
        return [t for t in self.get_aggregated_tools(only_enabled=True) if t.get("ready")]

    def get_aggregated_resources(self) -> List[Dict[str, Any]]:
        resources = []
        for server in self._all_servers():
            for res in server.list_resources():
                entry = dict(res)
                entry["server"] = server.name
                resources.append(entry)
        return resources

    def find_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Locate a tool and the server that owns it."""
        for server in self._all_servers():
            if tool_name in server._tool_handlers:
                meta = dict(server._tools.get(tool_name, {}))
                meta["server"] = server.name
                meta["_server_obj"] = server
                return meta
        return None

    # --- guarded execution ---------------------------------------------------

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None,
                     approval_id: str = "") -> Dict[str, Any]:
        """Run a tool through the policy gate.

        Returns one of three shapes:
          {"status": "ok", "result": ...}
          {"status": "confirmation_required", "approval": {...}}
          {"status": "error", "error": "..."}
        """
        arguments = arguments or {}

        # An approval names the call it approved; the arguments come from the
        # parked record, never from the caller, so nothing can be swapped in
        # between the operator seeing the request and the tool running.
        if approval_id:
            record = governance.take_approval(approval_id)
            if not record:
                return {"status": "error", "error": "Richiesta di conferma scaduta o già usata."}
            tool_name = record["tool"]
            arguments = record["arguments"]

        meta = self.find_tool(tool_name)
        if not meta:
            return {"status": "error", "error": f"Strumento '{tool_name}' inesistente."}

        server = meta["_server_obj"]
        safety = meta.get("safety", governance.SAFE)

        if not governance.is_tool_enabled(tool_name, server.name):
            return {"status": "error",
                    "error": f"Strumento '{tool_name}' disattivato nella tab MCP Tools."}

        try:
            if not server.is_configured():
                hint = server.missing_dependency()
                detail = f" Installa con: {hint}" if hint else ""
                return {"status": "error",
                        "error": f"'{server.name}' non è configurato.{detail}"}
        except Exception as exc:
            return {"status": "error", "error": f"'{server.name}' non disponibile: {exc}"}

        # Not pre-approved and able to act on the world: park it for a human.
        if not approval_id and governance.requires_approval(safety):
            approval = governance.create_approval(
                tool_name, arguments, server.name, meta.get("description", ""))
            return {"status": "confirmation_required", "approval": approval}

        result = server.call_tool(tool_name, arguments)
        if result.get("isError"):
            text = " ".join(part.get("text", "") for part in result.get("content", []))
            return {"status": "error", "error": text or "Esecuzione fallita."}
        return {"status": "ok", "result": result, "tool": tool_name, "server": server.name}

    # --- JSON-RPC ------------------------------------------------------------

    def dispatch_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route a JSON-RPC 2.0 request to the target MCP server."""
        params = request.get("params", {})
        method = request.get("method")
        rpc_id = request.get("id")
        server_name = params.get("server")

        if server_name and method not in ("mcp/servers",):
            server = self.get_server(server_name)
            if server:
                return server.handle_json_rpc(request)

        if method == "mcp/servers":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"servers": self.list_all_servers()}}

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": self.get_aggregated_tools()}}

        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": rpc_id,
                    "result": {"resources": self.get_aggregated_resources()}}

        if method == "tools/call":
            # The gate lives here too: the RPC endpoint is reachable from the
            # browser, so it must not be a way around the switches.
            outcome = self.execute_tool(params.get("name"), params.get("arguments", {}),
                                        params.get("approval_id", ""))
            if outcome["status"] == "ok":
                return {"jsonrpc": "2.0", "id": rpc_id, "result": outcome["result"]}
            if outcome["status"] == "confirmation_required":
                return {"jsonrpc": "2.0", "id": rpc_id,
                        "result": {"isError": False, "confirmationRequired": True,
                                   "approval": outcome["approval"],
                                   "content": [{"type": "text",
                                                "text": "Questo strumento richiede una conferma."}]}}
            return {"jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32000, "message": outcome["error"]}}

        if method == "resources/read":
            uri = params.get("uri")
            for server in self._all_servers():
                if uri in server._resource_handlers:
                    return server.handle_json_rpc(request)
            return {"jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32601, "message": f"Risorsa '{uri}' inesistente."}}

        return {"jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32601, "message": f"Metodo '{method}' sconosciuto."}}


# Singleton Hub Instance
mcp_hub = MCPHub()
