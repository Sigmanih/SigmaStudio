# ==============================================================================
# core/orchestration/agent_config.py — Agent Configuration Resolver
# Extracted from core/agent_orchestrator.py for Single Responsibility
# ==============================================================================
"""Resolve AI provider/model configuration for a given agent.

Used by the orchestrator and research engine to determine which model,
endpoint, and credentials to use for each agent's inference call.
"""

from core.ai_providers import load_ai_config, resolve_provider_config
from core.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Color / display metadata (shared between orchestrator and frontend)
# ---------------------------------------------------------------------------

AGENT_COLORS: dict[str, dict] = {
    "sigma_architect": {"bg": "#7c5bf0", "color": "#ffffff", "icon": "🏗️", "short": "Arch", "image": "/images/agente0.png"},
    "math1":           {"bg": "#3fb950", "color": "#ffffff", "icon": "∑",   "short": "Math", "image": "/images/matematicoAi.png"},
    "code_architect":  {"bg": "#00d2ff", "color": "#0e1016", "icon": "⚙️",  "short": "Code", "image": "/images/programmatoreAi.png"},
    "default":         {"bg": "#8b8fa3", "color": "#0e1016", "icon": "🤖",  "short": "AI",   "image": "/images/default.png"},
}


def get_agent_color(agent_id: str) -> dict:
    """Return display metadata for *agent_id*, falling back to ``default``."""
    base = AGENT_COLORS.get(agent_id, AGENT_COLORS["default"]).copy()
    try:
        from core.agent_registry import get_agent
        agent = get_agent(agent_id)
        if agent and agent.get("image"):
            base["image"] = agent["image"]
        else:
            # Fallback check mapping manifesto path if agent_id doesn't match keys directly
            from core.agent_registry import load_agents_meta
            meta = load_agents_meta()
            manifesto_images = meta.get("manifesto_images", {})
            for mpath, img in manifesto_images.items():
                if f"manifesti/{agent_id}.md" == mpath or f"{agent_id}.md" in mpath:
                    base["image"] = img
                    break
    except Exception:
        pass
    return base



def load_agent_config(
    ai_cfg: dict,
    model_override: str = "",
    agent_id: str | None = None,
) -> tuple:
    """Resolve provider/model/credentials for a single agent invocation.

    Resolution order:
    1. ``model_override`` (explicit request-level override).
    2. Agent's own model list from the agent registry.
    3. Global active model in ``ai_cfg``.

    Includes automatic provider detection from model-name prefixes
    (``deepseek-``, ``gpt-``, ``claude-``) and a safe fallback to Ollama
    when no API key is configured for remote providers.

    Returns:
        ``(model, provider, endpoint, api_url, api_key,
           temperature, max_tokens, top_p, request_timeout)``
    """
    provider = ai_cfg.get("active_provider", "ollama")
    providers_config = ai_cfg.get("providers", {})
    active_prov_cfg = providers_config.get(provider, {})
    model = model_override or ai_cfg.get("model", "llama3.2")

    # Override model from agent registry if agent_id is given
    if agent_id:
        from core.agent_registry import get_agent
        agent = get_agent(agent_id)
        if agent and agent.get("models"):
            model = agent["models"][0]

    endpoint        = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
    api_url         = active_prov_cfg.get("api_url", "")
    api_key         = active_prov_cfg.get("api_key", "")
    temperature     = active_prov_cfg.get("temperature", 0.7)
    max_tokens      = active_prov_cfg.get("max_tokens", 4096)
    top_p           = active_prov_cfg.get("top_p", 0.9)
    request_timeout = active_prov_cfg.get("timeout", 300)

    # Auto-detect provider from model name prefix
    if model.startswith("deepseek"):
        provider = "deepseek"
        if not api_url:
            api_url = "https://api.deepseek.com/v1/chat/completions"
    elif model.startswith(("gpt-", "o1", "o3")):
        provider = "openai"
        if not api_url:
            api_url = "https://api.openai.com/v1/chat/completions"
    elif model.startswith("claude"):
        provider = "anthropic"
        if not api_url:
            api_url = "https://api.anthropic.com/v1/messages"

    # Fine-grained override from provider config
    dp, dpv = resolve_provider_config(ai_cfg, model)
    if dpv:
        provider = dp
        if dpv.get("endpoint"):   endpoint   = dpv["endpoint"]
        if dpv.get("api_url"):    api_url    = dpv["api_url"]
        if dpv.get("api_key"):    api_key    = dpv["api_key"]
        temperature     = dpv.get("temperature",     temperature)
        max_tokens      = dpv.get("max_tokens",      max_tokens)
        top_p           = dpv.get("top_p",           top_p)

    # Safety: fallback to Ollama when remote provider has no key
    if provider in ("deepseek", "openai", "anthropic") and not api_key:
        ollama_cfg = providers_config.get("ollama", {})
        fallback_model = model_override or ai_cfg.get("model", "llama3.2")
        if fallback_model.startswith(("deepseek", "gpt-", "o1", "o3", "claude")):
            fallback_model = "llama3.2"

        log.warning(
            "No API key for provider=%s, falling back to Ollama model=%s",
            provider, fallback_model,
        )
        provider        = "ollama"
        endpoint        = ollama_cfg.get("endpoint", "http://localhost:11434/api/chat")
        api_url         = ""
        model           = fallback_model
        temperature     = ollama_cfg.get("temperature", 0.7)
        max_tokens      = ollama_cfg.get("max_tokens", 4096)
        top_p           = ollama_cfg.get("top_p", 0.9)
        request_timeout = ollama_cfg.get("timeout", 300)

    return model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout
