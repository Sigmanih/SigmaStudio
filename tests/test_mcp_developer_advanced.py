# ==============================================================================
# tests/test_mcp_developer_advanced.py — Unit tests per i nuovi server MCP
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
import pytest
from unittest.mock import patch, MagicMock

from core.modules.sigma_developer_lab.mcp_tools.web_server import WebSearchMCPServer
from core.modules.sigma_developer_lab.mcp_tools.docker_server import DockerMCPServer
from core.modules.sigma_developer_lab.mcp_tools.runtime_server import RuntimeInspectorMCPServer
from core.modules.sigma_developer_lab.mcp_tools.cargo_server import (
    RustCargoMCPServer,
    _parse_cargo_test_output,
)
from core.modules.sigma_developer_lab.mcp_tools.bridge import is_mcp_tool, ADMIN_TO_MCP


# ---------------------------------------------------------------------------
# WebSearchMCPServer
# ---------------------------------------------------------------------------

class TestWebSearchMCPServer:
    def setup_method(self):
        self.server = WebSearchMCPServer()

    def test_metadata(self):
        assert self.server.name == "web_search_server"
        tools = self.server.get_tools()
        names = [t["name"] for t in tools]
        assert "web_search" in names
        assert "fetch_web_page" in names
        assert "docs_rust_search" in names

    def test_web_search_empty_query(self):
        res = self.server.call_tool("web_search", {"query": ""})
        assert res["success"] is False
        assert "query" in res["error"]

    def test_web_search_mocked(self):
        with patch("core.modules.sigma_developer_lab.mcp_tools.web_server._ddg_search") as mock_s:
            mock_s.return_value = [{"title": "Rust Lang", "snippet": "A language empowering everyone", "url": "https://rust-lang.org"}]
            res = self.server.call_tool("web_search", {"query": "rust language"})
            assert res["success"] is True
            assert res["results_count"] == 1
            assert res["results"][0]["title"] == "Rust Lang"

    def test_fetch_web_page_empty_url(self):
        res = self.server.call_tool("fetch_web_page", {"url": ""})
        assert res["success"] is False

    def test_fetch_web_page_mocked(self):
        with patch("core.modules.sigma_developer_lab.mcp_tools.web_server._scrape_page") as mock_scrape:
            mock_scrape.return_value = {
                "success": True,
                "url": "https://docs.rs/tokio",
                "title": "Tokio Docs",
                "content": "Asynchronous runtime for Rust",
            }
            res = self.server.call_tool("fetch_web_page", {"url": "https://docs.rs/tokio"})
            assert res["success"] is True
            assert "Tokio" in res["title"]

    def test_docs_rust_search(self):
        res = self.server.call_tool("docs_rust_search", {"crate_name": "tokio"})
        assert res["success"] is True
        assert res["crate"] == "tokio"
        assert "docs.rs/tokio" in res["documentation"]

    def test_unknown_tool(self):
        res = self.server.call_tool("non_existent", {})
        assert res["success"] is False


# ---------------------------------------------------------------------------
# DockerMCPServer
# ---------------------------------------------------------------------------

class TestDockerMCPServer:
    def setup_method(self):
        self.server = DockerMCPServer()

    def test_metadata(self):
        assert self.server.name == "docker_server"
        tools = self.server.get_tools()
        names = [t["name"] for t in tools]
        assert "docker_list_containers" in names
        assert "docker_run_container" in names
        assert "docker_exec" in names
        assert "docker_container_status" in names
        assert "docker_stop_container" in names

    def test_run_container_missing_params(self):
        res = self.server.call_tool("docker_run_container", {"image": ""})
        assert res["success"] is False

    def test_exec_missing_params(self):
        res = self.server.call_tool("docker_exec", {"container": "c1", "command": ""})
        assert res["success"] is False

    def test_status_missing_container(self):
        res = self.server.call_tool("docker_container_status", {"container": ""})
        assert res["success"] is False

    def test_list_containers_mocked(self):
        with patch("core.modules.sigma_developer_lab.mcp_tools.docker_server._run_docker_cli") as mock_cli:
            mock_cli.return_value = {
                "success": True,
                "stdout": '{"ID":"123","Names":"rust_dev","Image":"rust:1.80","Status":"Up"}',
            }
            res = self.server.call_tool("docker_list_containers", {})
            assert res["success"] is True
            assert res["containers_count"] == 1
            assert res["containers"][0]["Names"] == "rust_dev"

    def test_exec_mocked(self):
        with patch("core.modules.sigma_developer_lab.mcp_tools.docker_server._run_docker_cli") as mock_cli:
            mock_cli.return_value = {
                "success": True,
                "stdout": "cargo 1.80.0",
                "stderr": "",
                "returncode": 0,
            }
            res = self.server.call_tool("docker_exec", {"container": "rust_dev", "command": "cargo --version"})
            assert res["success"] is True
            assert "cargo 1.80.0" in res["stdout"]


# ---------------------------------------------------------------------------
# RuntimeInspectorMCPServer
# ---------------------------------------------------------------------------

class TestRuntimeInspectorMCPServer:
    def setup_method(self):
        self.server = RuntimeInspectorMCPServer()

    def test_metadata(self):
        assert self.server.name == "runtime_inspector_server"
        tools = self.server.get_tools()
        names = [t["name"] for t in tools]
        assert "inspect_runtime_state" in names
        assert "hot_reload_module" in names
        assert "inspect_symbol" in names

    def test_inspect_runtime_state(self):
        res = self.server.call_tool("inspect_runtime_state", {"filter_prefix": "core."})
        assert res["success"] is True
        assert res["rss_memory_mb"] > 0
        assert res["active_threads_count"] >= 1
        assert res["loaded_modules_matching_count"] >= 1
        assert any(m.startswith("core.") for m in res["loaded_modules"])

    def test_hot_reload_existing_module(self):
        # Ricarica un modulo safe del kernel
        res = self.server.call_tool("hot_reload_module", {"module_name": "core.logger"})
        assert res["success"] is True
        assert res["module_name"] == "core.logger"

    def test_hot_reload_nonexistent_module(self):
        res = self.server.call_tool("hot_reload_module", {"module_name": "non_existent_module_xyz_123"})
        assert res["success"] is False

    def test_inspect_symbol(self):
        res = self.server.call_tool("inspect_symbol", {"symbol_path": "core.logger.get_logger"})
        assert res["success"] is True
        assert res["type"] == "function"
        assert "get_logger" in res["signature"]


# ---------------------------------------------------------------------------
# RustCargoMCPServer
# ---------------------------------------------------------------------------

class TestRustCargoMCPServer:
    def setup_method(self):
        self.server = RustCargoMCPServer()

    def test_metadata(self):
        assert self.server.name == "cargo_server"
        tools = self.server.get_tools()
        names = [t["name"] for t in tools]
        assert "cargo_build" in names
        assert "cargo_test" in names
        assert "cargo_check" in names
        assert "cargo_clippy" in names

    def test_parse_cargo_test_output(self):
        output = """
running 5 tests
test tests::test_mmap ... ok
test tests::test_kv_cache ... ok
test tests::test_scheduler ... ok
test tests::test_openai_api ... ok
test tests::test_hot_reload ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.12s
"""
        parsed = _parse_cargo_test_output(output, "")
        assert parsed["all_passed"] is True
        assert parsed["passed"] == 5
        assert parsed["failed"] == 0

    def test_cargo_build_mocked(self):
        with patch("core.modules.sigma_developer_lab.mcp_tools.cargo_server._run_cargo") as mock_run:
            mock_run.return_value = {
                "success": True,
                "stdout": "Compiling sigma_engine v0.1.0\nFinished release [optimized] target(s) in 2.34s",
                "stderr": "",
                "returncode": 0,
                "environment": "docker:sigma_rust_dev",
            }
            res = self.server.call_tool("cargo_build", {"release": True, "container": "sigma_rust_dev"})
            assert res["success"] is True
            assert res["tool"] == "cargo_build"
            assert res["release"] is True


# ---------------------------------------------------------------------------
# Bridge mapping verification
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test Supervisor MCP Server
# ---------------------------------------------------------------------------

class TestSupervisorMCPServer:
    def setup_method(self):
        from core.modules.sigma_developer_lab.mcp_tools.supervisor_server import SupervisorMCPServer
        self.server = SupervisorMCPServer()

    def test_metadata(self):
        tools = self.server.get_tools_metadata()
        names = [t["name"] for t in tools]
        assert "evaluate_team_performance" in names
        assert "register_runtime_role" in names
        assert "run_supervisor_audit" in names

    def test_evaluate_team_performance_perfect_100(self):
        res = self.server.execute_tool("evaluate_team_performance", {"project_dir": "projects/sigma_engine_rust"})
        assert res["success"] is True
        assert res["total_score_percentage"] == 100.0
        assert res["is_perfect_100"] is True
        assert res["breakdown"]["velocita"] == 100
        assert res["breakdown"]["efficienza"] == 100
        assert res["breakdown"]["scelta_tools"] == 100
        assert res["breakdown"]["ricezione_input"] == 100
        assert res["breakdown"]["sviluppo_software"] == 100
        assert res["breakdown"]["qualita_test"] == 100
        assert res["breakdown"]["retrocompatibilita"] == 100
        assert res["breakdown"]["modificabilita_runtime"] == 100

    def test_register_runtime_role(self):
        from core.harness.roles import DEV_ROLES
        res = self.server.execute_tool("register_runtime_role", {
            "id": "test_dynamic_role",
            "name": "Dynamic Tester",
            "icon": "⚡",
            "system_prompt": "Sei un tester dinamico registrato a runtime.",
            "tools": ["terminal", "read_file"],
        })
        assert res["success"] is True
        assert "test_dynamic_role" in DEV_ROLES
        role = DEV_ROLES["test_dynamic_role"]
        assert role.name == "Dynamic Tester"
        assert role.icon == "⚡"
        assert "terminal" in role.tools


# ---------------------------------------------------------------------------
# Bridge mapping verification
# ---------------------------------------------------------------------------

class TestBridgeAdvancedTools:
    def test_all_new_tools_bridged(self):
        new_tools = [
            "web_search", "fetch_web_page", "docs_rust_search",
            "docker_list_containers", "docker_run_container", "docker_exec",
            "docker_container_status", "docker_stop_container",
            "inspect_runtime_state", "hot_reload_module", "inspect_symbol",
            "cargo_build", "cargo_test", "cargo_check", "cargo_clippy",
            "evaluate_team_performance", "register_runtime_role", "run_supervisor_audit",
        ]
        for tool in new_tools:
            assert is_mcp_tool(tool), f"Tool '{tool}' dovrebbe essere registrato in ADMIN_TO_MCP"
            assert tool in ADMIN_TO_MCP
