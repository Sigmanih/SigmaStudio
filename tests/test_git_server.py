# ==============================================================================
# tests/test_git_server.py — Unit Tests for Developer Studio Git MCP Server
# ==============================================================================
import pytest
from core.developer_studio.mcp_tools.git_server import GitMCPServer, _sanitize_branch_name
from core.mcp.governance import SAFE, SENSITIVE


def test_git_branch_name_sanitizer():
    assert _sanitize_branch_name("feat/aggiungi api") == "feat/aggiungi-api"
    assert _sanitize_branch_name("fix: risoluzione bug #123") == "fix-risoluzione-bug-123"
    assert _sanitize_branch_name("---test---") == "test"
    assert _sanitize_branch_name("") == "dev-branch"


def test_git_server_tools_registration():
    server = GitMCPServer()
    tools = server.list_tools()
    assert len(tools) == 10

    tool_names = [t["name"] for t in tools]
    assert "git_status" in tool_names
    assert "git_diff" in tool_names
    assert "git_log" in tool_names
    assert "git_branch_create" in tool_names
    assert "git_checkout" in tool_names
    assert "git_commit" in tool_names
    assert "git_push" in tool_names

    # Check safety classifications
    for tool in tools:
        if tool["name"] in ("git_status", "git_diff", "git_log", "git_branch_list"):
            assert tool["safety"] == SAFE
        else:
            assert tool["safety"] == SENSITIVE


def test_git_status_call():
    server = GitMCPServer()
    if server.is_configured():
        res = server.call_tool("git_status", {"short": True})
        assert "content" in res
        assert isinstance(res["content"], list)
        text = res["content"][0]["text"]
        assert "Branch corrente" in text
