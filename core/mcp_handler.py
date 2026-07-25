# ==============================================================================
# core/mcp_handler.py — MCP Backend Endpoints Handler
# Exposes MCP Hub endpoints for REST, JSON-RPC 2.0, and status monitoring
# ==============================================================================
import json
from core.mcp import mcp_hub
from core.logger import get_logger

log = get_logger(__name__)


def handle_mcp_servers(self):
    """GET /api/mcp/servers — List status of all 6 specialized MCP servers."""
    try:
        servers = mcp_hub.list_all_servers()
        self.send_json_response({"success": True, "servers": servers})
    except Exception as exc:
        log.error("handle_mcp_servers error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_tools(self):
    """GET /api/mcp/tools — List all tools registered across MCP servers."""
    try:
        tools = mcp_hub.get_aggregated_tools()
        self.send_json_response({"success": True, "tools": tools, "total": len(tools)})
    except Exception as exc:
        log.error("handle_mcp_tools error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_mcp_resources(self):
    """GET /api/mcp/resources — List all resources across MCP servers."""
    try:
        resources = mcp_hub.get_aggregated_resources()
        self.send_json_response({"success": True, "resources": resources, "total": len(resources)})
    except Exception as exc:
        log.error("handle_mcp_resources error: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def _read_request_payload(handler) -> dict:
    """Universal helper to read request JSON payload on FastAPIHandlerAdapter or BaseHTTPRequestHandler."""
    if hasattr(handler, 'read_json_body'):
        return handler.read_json_body()
    if hasattr(handler, '_body_bytes') and handler._body_bytes:
        try:
            return json.loads(handler._body_bytes.decode('utf-8'))
        except Exception:
            return {}
    if hasattr(handler, 'rfile') and handler.rfile:
        try:
            content_length = int(handler.headers.get('Content-Length', 0))
            if content_length > 0:
                body_bytes = handler.rfile.read(content_length)
                return json.loads(body_bytes.decode('utf-8'))
        except Exception:
            return {}
    return {}


def handle_mcp_rpc(self):
    """POST /api/mcp/rpc — Dispatch JSON-RPC 2.0 request to target MCP server."""
    try:
        payload = _read_request_payload(self)
        response = mcp_hub.dispatch_rpc(payload)
        self.send_json_response(response)
    except Exception as exc:
        log.error("handle_mcp_rpc error: %s", exc)
        self.send_json_response({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32603, "message": f"Internal JSON-RPC Error: {str(exc)}"}
        }, 500)
