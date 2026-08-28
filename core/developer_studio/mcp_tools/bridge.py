# ==============================================================================
# core/developer_studio/mcp_tools/bridge.py — Admin Agent ↔ MCP Hub Bridge
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Bridge that unifies the admin agent's custom tool format with the MCP Hub.

The admin agent currently uses its own tool extraction and execution path
(```tool:name {...}```) separate from the MCP agent loop (```sigma-tool```).
This bridge allows the admin agent to also invoke MCP Hub tools, and allows
MCP-aware agents to invoke admin-style filesystem/terminal tools.

This is a compatibility layer: long-term, the admin agent should migrate fully
to the MCP Hub's tool execution path.
"""

from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

# Mapping from admin agent tool names → MCP tool names
ADMIN_TO_MCP: Dict[str, str] = {
    # Git tools
    "git_status": "git_status",
    "git_diff": "git_diff",
    "git_log": "git_log",
    "git_branch_create": "git_branch_create",
    "git_branch_list": "git_branch_list",
    "git_checkout": "git_checkout",
    "git_add": "git_add",
    "git_commit": "git_commit",
    "git_push": "git_push",
    "git_stash": "git_stash",
    # Lint tools
    "lint_python": "lint_python",
    "lint_code": "lint_python",
    "format_code": "format_code",
    "analyze_imports": "analyze_imports",
    "find_dead_code": "find_dead_code",
    # Test tools
    "run_tests": "run_tests",
    "run_test_file": "run_test_file",
    "list_test_files": "list_test_files",
    "get_coverage": "get_coverage",
}

# Admin agent tools that should NOT be bridged (handled locally)
LOCAL_TOOLS = {
    "list_dir", "read_file", "write_file", "delete", "terminal",
    "search_code", "pipeline", "complete_goal",
    # Aliases
    "read", "write", "save_file", "ls", "shell", "exec", "command",
    "delete_file", "remove_file", "rm", "grep", "tasks", "set_tasks",
    "update_pipeline", "finish_task", "task_complete",
    "list_directory",
}


def is_mcp_tool(tool_name: str) -> bool:
    """Check if a tool name should be routed through the MCP Hub."""
    return tool_name.lower() in ADMIN_TO_MCP


def is_local_tool(tool_name: str) -> bool:
    """Check if a tool name is handled locally by the admin agent."""
    return tool_name.lower() in LOCAL_TOOLS


def execute_via_mcp(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool through the MCP Hub, returning admin-agent-compatible output.

    Translates the MCP result format back to the admin agent's expected format.
    """
    from core.mcp.mcp_hub import mcp_hub

    mcp_name = ADMIN_TO_MCP.get(tool_name.lower(), tool_name)
    result = mcp_hub.execute_tool(mcp_name, params)

    if result["status"] == "ok":
        # Extract text from MCP content format
        content_parts = result.get("result", {}).get("content", [])
        text = "\n".join(
            part.get("text", "") for part in content_parts
            if isinstance(part, dict)
        )
        return {
            "tool": tool_name,
            "success": True,
            "message": text or "Eseguito con successo.",
            "content": text,
            "via_mcp": True,
            "server": result.get("server", ""),
        }

    elif result["status"] == "confirmation_required":
        approval = result.get("approval", {})
        return {
            "tool": tool_name,
            "success": False,
            "requires_approval": True,
            "approval_id": approval.get("request_id", ""),
            "message": f"⚠️ Questa operazione richiede approvazione: {approval.get('summary', tool_name)}",
            "via_mcp": True,
        }

    else:
        return {
            "tool": tool_name,
            "success": False,
            "error": result.get("error", "Errore sconosciuto"),
            "via_mcp": True,
        }


def format_mcp_observation(result: Dict[str, Any]) -> str:
    """Format MCP execution result as observation text for the model."""
    tool_name = result.get("tool", "unknown")

    if result.get("requires_approval"):
        return (
            f"Tool '{tool_name}' richiede approvazione dell'utente. "
            f"L'operazione è stata messa in attesa."
        )

    if result.get("success"):
        content = result.get("content", "") or result.get("message", "")
        return f"Tool '{tool_name}' eseguito con successo.\n{content}"

    error = result.get("error", "Errore sconosciuto")
    return f"Tool '{tool_name}' fallito: {error}"


def get_available_mcp_tools() -> List[Dict[str, Any]]:
    """Get all MCP tools available for the admin agent, formatted for the prompt."""
    try:
        from core.mcp.mcp_hub import mcp_hub
        tools = mcp_hub.get_agent_tools()
        # Filter to developer-relevant tools
        dev_tools = [
            t for t in tools
            if t.get("category", "").startswith("developer_")
        ]
        return dev_tools
    except Exception as exc:
        log.warning("Could not load MCP tools for bridge: %s", exc)
        return []


def build_mcp_tools_section() -> str:
    """Build the prompt section describing available MCP developer tools."""
    tools = get_available_mcp_tools()
    if not tools:
        return ""

    lines = [
        "\n## STRUMENTI AGGIUNTIVI (MCP)",
        "",
        "Puoi usare anche questi strumenti con il formato standard ```tool:nome```:",
        "",
    ]
    for tool in tools:
        desc = tool.get("description", "")
        lines.append(f"- **{tool['name']}**: {desc}")
        params = (tool.get("inputSchema") or {}).get("properties", {})
        required = set((tool.get("inputSchema") or {}).get("required", []))
        if params:
            param_list = ", ".join(
                f"{k}{'*' if k in required else ''}: {v.get('type', 'string')}"
                for k, v in params.items()
            )
            lines.append(f"  argomenti — {param_list}")
    lines.append("")
    return "\n".join(lines)
