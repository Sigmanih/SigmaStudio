# ==============================================================================
# tests/test_mcp_servers.py — Test Suite for Multi-MCP Server & Hub Architecture
# ==============================================================================
import unittest
from core.mcp import (
    mcp_hub, MemoryMCPServer, DeveloperMCPServer, HardwareMCPServer,
    TrainingMCPServer, InferenceMCPServer, NetworkMCPServer
)


class TestMCPServers(unittest.TestCase):
    def test_hub_initialization(self):
        """Verify that every specialized MCP server is registered on the hub."""
        servers = mcp_hub.list_all_servers()
        names = {s["name"] for s in servers}
        self.assertEqual(len(servers), len(names), "nomi di server duplicati sull'hub")
        for expected in ("Memory MCP", "Developer MCP", "Hardware MCP", "Training MCP",
                         "Inference MCP", "Network MCP", "Benchmark MCP"):
            self.assertIn(expected, names)

    def test_tools_aggregation(self):
        """Verify that tools are aggregated across servers."""
        tools = mcp_hub.get_aggregated_tools()
        self.assertGreater(len(tools), 10)
        tool_names = {t["name"] for t in tools}
        self.assertIn("query_vector_db", tool_names)
        self.assertIn("run_pytest", tool_names)
        self.assertIn("get_hardware_status", tool_names)
        self.assertIn("import_dataset", tool_names)
        self.assertIn("select_routed_model", tool_names)
        self.assertIn("discover_peers", tool_names)

    def test_resources_aggregation(self):
        """Verify that resources are aggregated across servers."""
        resources = mcp_hub.get_aggregated_resources()
        self.assertGreater(len(resources), 5)
        uris = {r["uri"] for r in resources}
        self.assertIn("hardware://gpu_telemetry", uris)
        self.assertIn("developer://git/status", uris)
        self.assertIn("memory://knowledge/graph", uris)

    def test_hardware_mcp_telemetry(self):
        """Test Hardware MCP status tool execution."""
        server = mcp_hub.get_server("Hardware MCP")
        self.assertIsNotNone(server)
        res = server.call_tool("get_hardware_status")
        self.assertFalse(res.get("isError", False))
        self.assertIn("content", res)

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

    def test_web_search_tool(self):
        """Test Network MCP search_web tool execution via JSON-RPC."""
        server = mcp_hub.get_server("Network MCP")
        self.assertIsNotNone(server)
        res = server.call_tool("search_web", {"query": "Sigma Studio AI"})
        self.assertFalse(res.get("isError", False))


if __name__ == "__main__":
    unittest.main()
