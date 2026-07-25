# ==============================================================================
# core/mcp/base_server.py — Base MCP Server Implementation (JSON-RPC 2.0)
# Standard Model Context Protocol Server Base Class
# ==============================================================================
import json
import logging
from typing import Dict, Any, List, Callable, Optional

log = logging.getLogger(__name__)


class BaseMCPServer:
    """
    Base class for Model Context Protocol (MCP) servers.
    Implements standard JSON-RPC 2.0 handling for resources, tools, and prompts.
    """
    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._tool_handlers: Dict[str, Callable] = {}
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._resource_handlers: Dict[str, Callable] = {}
        self._prompts: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable):
        """Register a tool with JSON schema and execution handler."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema
        }
        self._tool_handlers[name] = handler
        log.debug(f"[{self.name}] Tool registered: {name}")

    def register_resource(self, uri: str, name: str, description: str, mime_type: str, handler: Callable):
        """Register a resource URI and content retrieval handler."""
        self._resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type
        }
        self._resource_handlers[uri] = handler
        log.debug(f"[{self.name}] Resource registered: {uri}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return array of registered tools."""
        return list(self._tools.values())

    def list_resources(self) -> List[Dict[str, Any]]:
        """Return array of registered resources."""
        return list(self._resources.values())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute registered tool handler."""
        if tool_name not in self._tool_handlers:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found on server '{self.name}'."}]
            }
        try:
            args = arguments or {}
            result = self._tool_handlers[tool_name](**args)
            if isinstance(result, dict) and "content" in result:
                return result
            return {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}]
            }
        except Exception as exc:
            log.error(f"[{self.name}] Tool '{tool_name}' execution error: {exc}", exc_info=True)
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {str(exc)}"}]
            }

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read content from registered resource URI."""
        if uri not in self._resource_handlers:
            return {
                "isError": True,
                "contents": [],
                "message": f"Resource '{uri}' not found on server '{self.name}'."
            }
        try:
            content = self._resource_handlers[uri](uri)
            meta = self._resources.get(uri, {})
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": meta.get("mimeType", "text/plain"),
                    "text": content if isinstance(content, str) else json.dumps(content, indent=2)
                }]
            }
        except Exception as exc:
            log.error(f"[{self.name}] Resource '{uri}' read error: {exc}", exc_info=True)
            return {
                "isError": True,
                "contents": [],
                "message": f"Error reading resource '{uri}': {str(exc)}"
            }

    def handle_json_rpc(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming JSON-RPC 2.0 message."""
        rpc_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": self.name, "version": self.version}
                }
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": self.list_tools()}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            res = self.call_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": res
            }
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"resources": self.list_resources()}
            }
        elif method == "resources/read":
            uri = params.get("uri")
            res = self.read_resource(uri)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": res
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found."}
            }
