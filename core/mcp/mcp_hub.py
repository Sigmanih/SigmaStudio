# ==============================================================================
# core/mcp/mcp_hub.py — Central MCP Router & Multiplexer
# Manages initialization, tool discovery, RPC dispatching for all 6 MCP servers
# ==============================================================================
import logging
from typing import Dict, Any, List, Optional
from core.mcp.base_server import BaseMCPServer
from core.mcp.memory_server import MemoryMCPServer
from core.mcp.developer_server import DeveloperMCPServer
from core.mcp.hardware_server import HardwareMCPServer
from core.mcp.training_server import TrainingMCPServer
from core.mcp.inference_server import InferenceMCPServer
from core.mcp.network_server import NetworkMCPServer

log = logging.getLogger(__name__)


class MCPHub:
    """
    Central Manager and Router for all specialized MCP servers in Sigma Studio.
    Provides unified JSON-RPC multiplexing, tool discovery, and resource access.
    """
    def __init__(self):
        self.servers: Dict[str, BaseMCPServer] = {}
        self._initialize_servers()

    def _initialize_servers(self):
        """Instantiate and register all 6 specialized MCP servers."""
        instances = [
            MemoryMCPServer(),
            DeveloperMCPServer(),
            HardwareMCPServer(),
            TrainingMCPServer(),
            InferenceMCPServer(),
            NetworkMCPServer()
        ]
        for server in instances:
            self.servers[server.name] = server
            log.info("Registered MCP Server: '%s' (v%s)", server.name, server.version)

    def get_server(self, server_name: str) -> Optional[BaseMCPServer]:
        """Get specific MCP server by name."""
        return self.servers.get(server_name)

    def list_all_servers(self) -> List[Dict[str, Any]]:
        """Return status overview of all 6 MCP servers."""
        return [{
            "name": s.name,
            "version": s.version,
            "description": s.description,
            "tools_count": len(s.list_tools()),
            "resources_count": len(s.list_resources())
        } for s in self.servers.values()]

    def list_all_tools(self) -> List[Dict[str, Any]]:
        return self.get_aggregated_tools()

    def get_aggregated_tools(self) -> List[Dict[str, Any]]:
        """Aggregate all tools across all 6 MCP servers for agent awareness."""
        all_tools = []
        for server in self.servers.values():
            for tool in server.list_tools():
                tool_entry = dict(tool)
                tool_entry["server"] = server.name
                all_tools.append(tool_entry)
        return all_tools

    def get_aggregated_resources(self) -> List[Dict[str, Any]]:
        """Aggregate all resources across all 6 MCP servers."""
        all_resources = []
        for server in self.servers.values():
            for res in server.list_resources():
                res_entry = dict(res)
                res_entry["server"] = server.name
                all_resources.append(res_entry)
        return all_resources

    def dispatch_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route JSON-RPC 2.0 request to target MCP server.
        If no server specified in params, broadcasts to candidate tool/resource owner.
        """
        params = request.get("params", {})
        server_name = params.get("server")

        if server_name and server_name in self.servers:
            return self.servers[server_name].handle_json_rpc(request)

        method = request.get("method")
        rpc_id = request.get("id")

        if method == "mcp/servers":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"servers": self.list_all_servers()}
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": self.get_aggregated_tools()}
            }
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"resources": self.get_aggregated_resources()}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            for server in self.servers.values():
                if tool_name in server._tool_handlers:
                    return server.handle_json_rpc(request)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found on any MCP server."}
            }
        elif method == "resources/read":
            uri = params.get("uri")
            for server in self.servers.values():
                if uri in server._resource_handlers:
                    return server.handle_json_rpc(request)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Resource URI '{uri}' not found on any MCP server."}
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Unknown MCP Hub method '{method}'."}
            }


# Singleton Hub Instance
mcp_hub = MCPHub()
