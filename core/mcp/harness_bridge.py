"""Adatta gli strumenti registrati nell'hub al formato dell'harness."""
from core.mcp.mcp_hub import mcp_hub


def is_mcp_tool(name: str) -> bool:
    from core.harness.policy import canonical
    from core.harness.tool_schema import declared_tools
    if canonical(name) in declared_tools():
        return False
    return mcp_hub.find_tool(str(name).lower()) is not None


def execute_via_mcp(name: str, arguments: dict) -> dict:
    outcome = mcp_hub.execute_tool(name, arguments)
    result = {"tool": name, "success": outcome["status"] == "ok", "via_mcp": True}
    if outcome["status"] == "ok":
        content = "\n".join(part.get("text", "") for part in outcome.get("result", {}).get("content", [])
                            if isinstance(part, dict))
        return {**result, "content": content, "message": content or "Eseguito.", "server": outcome.get("server", "")}
    if outcome["status"] == "confirmation_required":
        return {**result, "requires_approval": True, "approval_id": outcome["approval"]["request_id"],
                "message": "Operazione in attesa dell'assenso umano."}
    return {**result, "error": outcome.get("error", "Esecuzione fallita.")}


def build_mcp_tools_section(allowed_tools=None) -> str:
    from core.harness.policy import canonical
    permessi = ({canonical(name) for name in allowed_tools}
                if allowed_tools is not None else None)
    tools = [tool for tool in mcp_hub.get_agent_tools() if is_mcp_tool(tool["name"])]
    if permessi is not None:
        tools = [tool for tool in tools if canonical(tool["name"]) in permessi]
    if not tools:
        return ""
    lines = ["\n## STRUMENTI AGGIUNTIVI (MCP)"]
    for tool in tools:
        schema = tool.get("inputSchema") or {}
        required = set(schema.get("required") or ())
        args = ", ".join(name + ("*" if name in required else "")
                         for name in (schema.get("properties") or {}))
        lines.append(f"- {tool['name']}({args}): {tool.get('description', '')}")
    return "\n".join(lines)
