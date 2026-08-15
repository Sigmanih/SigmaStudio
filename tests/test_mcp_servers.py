# ==============================================================================
# tests/test_mcp_servers.py — Test Suite for Multi-MCP Server & Hub Architecture
# ==============================================================================
import unittest
from core.mcp import mcp_hub, InferenceMCPServer, BaseMCPServer, SAFE


class _DemoCustomMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(name="Demo Custom MCP", version="1.0.0", description="Demo module server")
        self.register_tool(
            name="demo_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
            handler=lambda args: {"output": f"Echo: {args.get('msg', '')}"},
            safety=SAFE,
            category="custom"
        )
        self.register_resource(
            uri="demo://data/status",
            name="Demo Status",
            description="Demo status resource",
            mime_type="application/json",
            handler=lambda uri: {"status": "ok"}
        )


class TestMCPServers(unittest.TestCase):
    def test_hub_initialization(self):
        """Verify that micro-kernel built-in MCP servers are registered on the hub."""
        servers = mcp_hub.list_all_servers()
        names = {s["name"] for s in servers}
        self.assertIn("Inference MCP", names)

    def test_dynamic_server_registration(self):
        """Verify that optional modules can register custom MCP servers at runtime."""
        mcp_hub.register_server(_DemoCustomMCPServer)
        server = mcp_hub.get_server("Demo Custom MCP")
        self.assertIsNotNone(server)
        
        tools = mcp_hub.get_aggregated_tools()
        tool_names = {t["name"] for t in tools}
        self.assertIn("demo_tool", tool_names)

        resources = mcp_hub.get_aggregated_resources()
        uris = {r["uri"] for r in resources}
        self.assertIn("demo://data/status", uris)

    def test_json_rpc_dispatch(self):
        """Test JSON-RPC 2.0 dispatching on MCP Hub."""
        req = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "tools/list"
        }
        res = mcp_hub.dispatch_rpc(req)
        self.assertEqual(res.get("id"), "req-1")
        self.assertIn("tools", res.get("result", {}))

    def test_inference_tool_call(self):
        """Test calling Inference MCP tool via JSON-RPC."""
        server = mcp_hub.get_server("Inference MCP")
        self.assertIsNotNone(server)
        res = server.call_tool("select_routed_model", {"task_type": "coding", "complexity": "high"})
        self.assertFalse(res.get("isError", False))


if __name__ == "__main__":
    unittest.main()
