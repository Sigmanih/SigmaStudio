"""Tool Registry for Sigma Studio — Plugin system for agent tools.
Permette agli agenti di scoprire e usare strumenti dinamicamente."""
import json
import inspect

# Global tool registry
_registered_tools = {}


class AgentTool:
    """A tool that an agent can use, similar to ChatGPT plugins/function calling."""

    def __init__(self, name, description, parameters, handler, category="general"):
        """
        Args:
            name: Tool name (e.g., 'web_search', 'run_code')
            description: Description of what the tool does
            parameters: JSON Schema dict describing parameters
            handler: Callable that executes the tool
            category: Tool category for grouping
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.category = category

    def to_dict(self):
        """Convert tool to dict for injection into AI system prompt."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def execute(self, params):
        """Execute the tool with given parameters."""
        try:
            result = self.handler(**params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_tool(tool):
    """Register a tool in the global registry.

    Args:
        tool: AgentTool instance
    """
    _registered_tools[tool.name] = tool


def get_tool(name):
    """Get a registered tool by name."""
    return _registered_tools.get(name)


def get_tools_for_agent(agent_id=None, capabilities=None):
    """Get tools available for a specific agent.

    Args:
        agent_id: Agent identifier (optional, for filtering)
        capabilities: List of agent capabilities (optional)

    Returns:
        List of tool dicts
    """
    all_tools = list(_registered_tools.values())

    # If agent has specific capabilities, filter tools
    if capabilities:
        # Map capabilities to tool categories
        cap_to_categories = {
            "run_test": ["testing", "code"],
            "run_terminal": ["terminal", "code"],
            "create_file": ["filesystem", "code"],
            "edit_file": ["filesystem", "code"],
        }
        allowed_categories = set()
        for cap in capabilities:
            if cap in cap_to_categories:
                allowed_categories.update(cap_to_categories[cap])

        if allowed_categories:
            all_tools = [t for t in all_tools if t.category in allowed_categories or t.category == "general"]

    return [t.to_dict() for t in all_tools]


def execute_tool(name, params):
    """Execute a registered tool by name.

    Args:
        name: Tool name
        params: Dict of parameters

    Returns:
        Dict with success/result/error
    """
    tool = _registered_tools.get(name)
    if not tool:
        return {"success": False, "error": f"Tool '{name}' non trovato"}
    return tool.execute(params)


def get_tools_prompt_section(agent_id=None, capabilities=None):
    """Generate a system prompt section describing available tools.

    Returns:
        Formatted string describing tools for AI context injection.
    """
    tools = get_tools_for_agent(agent_id, capabilities)
    if not tools:
        return ""

    lines = ["\n## 🛠️ STRUMENTI DISPONIBILI"]
    for tool in tools:
        lines.append(f"\n### {tool['name']}")
        lines.append(f"{tool['description']}")
        if tool.get("parameters"):
            params = tool["parameters"]
            if isinstance(params, dict):
                props = params.get("properties", params)
                if props:
                    lines.append("Parametri:")
                    for pname, pinfo in props.items():
                        ptype = pinfo.get("type", "string")
                        desc = pinfo.get("description", "")
                        required = " (obbligatorio)" if pname in params.get("required", []) else ""
                        lines.append(f"  - {pname}: {ptype}{required} — {desc}")

    lines.append("\nUsa il campo 'tool' nelle tue azioni per chiamare questi strumenti.")
    return "\n".join(lines)


# ==============================================================================
# Built-in Tool Definitions
# ==============================================================================

def _register_builtin_tools():
    """Register all built-in tools.

    These are tools that any agent can use, mapped to existing actions
    in execute_ai_actions().
    """

    register_tool(AgentTool(
        name="create_file",
        description="Crea un nuovo file con contenuto specificato",
        parameters={
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string", "description": "Percorso completo del file"},
                "content": {"type": "string", "description": "Contenuto del file"},
            }
        },
        handler=lambda **kw: kw,
        category="filesystem",
    ))

    register_tool(AgentTool(
        name="edit_file",
        description="Modifica un file esistente (sostituzione testo o sovrascrittura)",
        parameters={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Percorso del file da modificare"},
                "content": {"type": "string", "description": "Nuovo contenuto"},
                "search": {"type": "string", "description": "Testo da cercare e sostituire"},
            }
        },
        handler=lambda **kw: kw,
        category="filesystem",
    ))

    register_tool(AgentTool(
        name="run_test",
        description="Esegue uno script Python o Node.js di test",
        parameters={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Percorso dello script da eseguire"},
            }
        },
        handler=lambda **kw: kw,
        category="testing",
    ))

    register_tool(AgentTool(
        name="read_file",
        description="Legge il contenuto di un file (massimo 100KB)",
        parameters={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Percorso del file da leggere"},
            }
        },
        handler=lambda **kw: kw,
        category="filesystem",
    ))

    register_tool(AgentTool(
        name="delete_file",
        description="Elimina un file dal progetto",
        parameters={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "Percorso del file da eliminare"},
            }
        },
        handler=lambda **kw: kw,
        category="filesystem",
    ))

    register_tool(AgentTool(
        name="web_search",
        description="Cerca informazioni sul web (DuckDuckGo + Wikipedia)",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Query di ricerca"},
                "max_results": {"type": "integer", "description": "Numero massimo di risultati (default 5)"},
            }
        },
        handler=lambda **kw: kw,
        category="general",
    ))

    register_tool(AgentTool(
        name="run_terminal",
        description="Esegue un comando nel terminale (solo directory consentite)",
        parameters={
            "type": "object",
            "required": ["cmd"],
            "properties": {
                "cmd": {"type": "string", "description": "Comando da eseguire"},
                "cwd": {"type": "string", "description": "Directory di lavoro (opzionale)"},
            }
        },
        handler=lambda **kw: kw,
        category="terminal",
    ))

    register_tool(AgentTool(
        name="create_module",
        description="Crea un nuovo modulo con le 5 sezioni standard (teoria, test, viz, docs, whitepapers)",
        parameters={
            "type": "object",
            "required": ["topic", "number", "name"],
            "properties": {
                "topic": {"type": "string", "description": "Nome del topic (argomento)"},
                "number": {"type": "string", "description": "Numero del modulo (es. '01')"},
                "name": {"type": "string", "description": "Nome descrittivo del modulo"},
            }
        },
        handler=lambda **kw: kw,
        category="filesystem",
    ))


# Register built-in tools on import
_register_builtin_tools()