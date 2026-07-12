"""Agent Registry for Sigma Studio — Gestione strutturata degli agenti AI."""
import os
import json
import datetime


AGENTS_META_FILE = "agents_meta.json"

# Default agent registry seed data
DEFAULT_AGENTS_REGISTRY = {
    "agents": {}
}


def load_agents_meta() -> dict:
    """Load agent registry from agents_meta.json."""
    if not os.path.exists(AGENTS_META_FILE):
        return DEFAULT_AGENTS_REGISTRY
    try:
        with open(AGENTS_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_AGENTS_REGISTRY


def save_agents_meta(meta: dict) -> None:
    """Save agent registry to agents_meta.json."""
    with open(AGENTS_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4)


def get_all_agents() -> list:
    """Get list of all registered agents with their metadata."""
    meta = load_agents_meta()
    agents = meta.get("agents", {})
    result = []
    for agent_id, agent_data in agents.items():
        entry = {"id": agent_id, **agent_data}
        entry.pop("parent_id", None)
        result.append(entry)
    return result


def get_agent(agent_id: str) -> dict:
    """Get a single agent by ID. Returns None if not found."""
    meta = load_agents_meta()
    agents = meta.get("agents", {})
    if agent_id == "sigma_architect" and "sigma_architect" not in agents and "agente0" in agents:
        return agents.get("agente0")
    return agents.get(agent_id)



def register_agent(
    agent_id: str,
    name: str,
    manifesto: str,
    specialization: str = "general",
    capabilities: list = None,
    models: list = None,
    temperature: float = 0.7,
    context_window: int = 8192,
    allowed_topics: list = None,
    parent_id: str = None,
) -> tuple:
    """Register a new agent in the registry.

    Args:
        agent_id: Unique identifier (e.g., 'math1')
        name: Display name (e.g., 'Sigma Math Researcher')
        manifesto: Path to Modelfile manifest
        specialization: Area of expertise
        capabilities: List of action types the agent can perform
        models: List of AI models this agent can use
        temperature: Default temperature
        context_window: Default context window in tokens
        allowed_topics: List of topic IDs this agent can work on
        parent_id: ID of parent agent (for hierarchies)

    Returns:
        Tuple of (success, message_or_agent_data)
    """
    if not agent_id or not name:
        return False, "agent_id e name sono obbligatori"

    meta = load_agents_meta()
    agents = meta.setdefault("agents", {})

    if agent_id in agents:
        return False, f"Agente '{agent_id}' già registrato"

    now = datetime.datetime.now().isoformat()

    agents[agent_id] = {
        "name": name,
        "version": "1.0",
        "manifesto": manifesto,
        "specialization": specialization or "general",
        "capabilities": capabilities or [],
        "models": models or [],
        "temperature": temperature,
        "context_window": context_window,
        "status": "active",
        "usage_count": 0,
        "success_rate": 0.0,
        "allowed_topics": allowed_topics or [],
        "parent_id": parent_id,
        "created": now,
        "updated": now,
    }

    save_agents_meta(meta)
    return True, agents[agent_id]


def update_agent(agent_id: str, updates: dict) -> tuple:
    """Update an existing agent's metadata.

    Args:
        agent_id: Agent ID to update
        updates: Dict of fields to update

    Returns:
        Tuple of (success, message_or_agent_data)
    """
    meta = load_agents_meta()
    agents = meta.setdefault("agents", {})

    if agent_id not in agents:
        return False, f"Agente '{agent_id}' non trovato"

    # Allowed fields for update
    allowed_fields = {
        "name", "version", "manifesto", "specialization", "capabilities",
        "models", "temperature", "context_window", "status",
        "allowed_topics", "parent_id",
    }

    for key, value in updates.items():
        if key in allowed_fields:
            agents[agent_id][key] = value

    agents[agent_id]["updated"] = datetime.datetime.now().isoformat()

    save_agents_meta(meta)
    return True, agents[agent_id]


def increment_usage(agent_id: str, success: bool = True) -> None:
    """Increment usage counter and update success rate for an agent."""
    meta = load_agents_meta()
    agents = meta.setdefault("agents", {})

    if agent_id not in agents:
        return

    agent = agents[agent_id]
    old_count = agent.get("usage_count", 0)
    old_rate = agent.get("success_rate", 0.0)

    agent["usage_count"] = old_count + 1
    # Weighted moving average for success rate
    if success:
        agent["success_rate"] = (old_rate * old_count + 1.0) / (old_count + 1)
    else:
        agent["success_rate"] = (old_rate * old_count) / (old_count + 1)

    agent["updated"] = datetime.datetime.now().isoformat()
    save_agents_meta(meta)


def get_agents_for_topic(topic_id: str) -> list:
    """Get all agents allowed to work on a specific topic."""
    meta = load_agents_meta()
    agents = meta.get("agents", {})
    result = []
    for agent_id, agent_data in agents.items():
        if agent_data.get("status") != "active":
            continue
        allowed = agent_data.get("allowed_topics", [])
        if not allowed or topic_id in allowed:
            result.append({"id": agent_id, **agent_data})
    return result


def get_specialized_agent(specialization: str) -> dict:
    """Find the best agent for a given specialization.

    Specializations: 'mathematics', 'software_architecture',
                     'full_stack_development', 'general'
    """
    meta = load_agents_meta()
    agents = meta.get("agents", {})
    best = None
    best_score = 0

    for agent_id, agent_data in agents.items():
        if agent_data.get("status") != "active":
            continue
        spec = agent_data.get("specialization", "")
        # Exact match scores highest
        if spec == specialization:
            return {"id": agent_id, **agent_data}
        # Partial match
        score = 0
        if specialization in spec or spec in specialization:
            score = 0.5
        if score > best_score:
            best_score = score
            best = {"id": agent_id, **agent_data}

    return best


# Agent display colors (matching AGENT_COLORS in orchestrator)
SIGMA_ARCHITECT_ID = "sigma_architect"

AGENT_DISPLAY_COLORS = {
    "sigma_architect": {"bg": "#7c5bf0", "color": "#ffffff", "icon": "🏗️", "short": "Arch", "image": "/images/agente0.png"},
    "math1": {"bg": "#3fb950", "color": "#ffffff", "icon": "∑", "short": "Math", "image": "/images/matematicoAi.png"},
    "code_architect": {"bg": "#00d2ff", "color": "#0e1016", "icon": "⚙️", "short": "Code", "image": "/images/programmatoreAi.png"},
}


def get_agents_colors() -> dict:
    """Get all agent colors for frontend display."""
    meta = load_agents_meta()
    agents = meta.get("agents", {})
    result = {}
    for agent_id in agents:
        color = AGENT_DISPLAY_COLORS.get(agent_id, {"bg": "#8b8fa3", "color": "#0e1016", "icon": "🤖", "short": "AI", "image": "/images/default.png"})
        result[agent_id] = color
    return result


# ==============================================================================
# API Handlers
# ==============================================================================


def handle_agents_list(self):
    """GET /api/agents — List all registered agents."""
    try:
        agents = get_all_agents()
        return self.send_json_response({"success": True, "agents": agents})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_agents_colors(self):
    """GET /api/agents/colors — Get agent display colors."""
    try:
        colors = get_agents_colors()
        return self.send_json_response({"success": True, "colors": colors})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_agents_get(self):
    """GET /api/agents/get — Get a single agent by ID."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        agent_id = query.get("id", [None])[0]
        if not agent_id:
            return self.send_json_response({"success": False, "error": "id richiesto"}, 400)
        agent = get_agent(agent_id)
        if not agent:
            return self.send_json_response({"success": False, "error": f"Agente '{agent_id}' non trovato"}, 404)
        return self.send_json_response({"success": True, "agent": {"id": agent_id, **agent}})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_agents_register(self):
    """POST /api/agents/register — Register a new agent."""
    try:
        req = self.read_json_body()
        agent_id = req.get("id", "").strip().lower().replace(" ", "_")
        name = req.get("name", "").strip()
        manifesto = req.get("manifesto", "")
        specialization = req.get("specialization", "general")
        capabilities = req.get("capabilities", [])
        models = req.get("models", [])
        temperature = req.get("temperature", 0.7)
        context_window = req.get("context_window", 8192)
        allowed_topics = req.get("allowed_topics", [])
        parent_id = req.get("parent_id")

        if not agent_id or not name:
            return self.send_json_response({"success": False, "error": "id e name sono obbligatori"}, 400)

        # Validate manifesto file exists
        if manifesto and not os.path.exists(manifesto):
            return self.send_json_response({"success": False, "error": f"Manifesto '{manifesto}' non trovato"}, 400)

        success, result = register_agent(
            agent_id, name, manifesto, specialization,
            capabilities, models, temperature, context_window,
            allowed_topics, parent_id
        )

        if success:
            return self.send_json_response({"success": True, "agent": {"id": agent_id, **result}})
        return self.send_json_response({"success": False, "error": result}, 400)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_agents_update(self):
    """POST /api/agents/update — Update an existing agent."""
    try:
        req = self.read_json_body()
        agent_id = req.get("id", "").strip()
        if not agent_id:
            return self.send_json_response({"success": False, "error": "id richiesto"}, 400)

        updates = {k: v for k, v in req.items() if k != "id"}
        success, result = update_agent(agent_id, updates)

        if success:
            return self.send_json_response({"success": True, "agent": {"id": agent_id, **result}})
        return self.send_json_response({"success": False, "error": result}, 404)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_agents_for_topic(self):
    """GET /api/agents/for_topic — Get agents for a specific topic."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        topic_id = query.get("topic", [None])[0]
        if not topic_id:
            return self.send_json_response({"success": False, "error": "topic richiesto"}, 400)
        agents = get_agents_for_topic(topic_id)
        return self.send_json_response({"success": True, "agents": agents})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)