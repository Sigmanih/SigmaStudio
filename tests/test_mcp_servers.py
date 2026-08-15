# ==============================================================================
# tests/test_mcp_servers.py — Test Suite for Multi-MCP Server & Hub Architecture
# ==============================================================================
import unittest
from core.mcp import (
    mcp_hub, DeveloperMCPServer,
    InferenceMCPServer, NetworkMCPServer, EmailMCPServer,
    MessagingMCPServer, CalendarMCPServer
)


class TestMCPServers(unittest.TestCase):
    def test_hub_initialization(self):
        """Verify that kernel built-in MCP servers are registered on the hub."""
        servers = mcp_hub.list_all_servers()
        names = {s["name"] for s in servers}
        self.assertEqual(len(servers), len(names), "nomi di server duplicati sull'hub")
        for expected in ("Developer MCP", "Inference MCP", "Network MCP",
                         "Email MCP", "Messaging MCP", "Calendar MCP"):
            self.assertIn(expected, names)

    def test_tools_aggregation(self):
        """Verify that tools are aggregated across servers."""
        tools = mcp_hub.get_aggregated_tools()
        self.assertGreater(len(tools), 4)
        tool_names = {t["name"] for t in tools}
        self.assertIn("run_pytest", tool_names)
        self.assertIn("select_routed_model", tool_names)
        self.assertIn("discover_peers", tool_names)

    def test_resources_aggregation(self):
        """Verify that resources are aggregated across servers."""
        resources = mcp_hub.get_aggregated_resources()
        self.assertGreater(len(resources), 0)
        uris = {r["uri"] for r in resources}
        self.assertIn("developer://git/status", uris)

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
