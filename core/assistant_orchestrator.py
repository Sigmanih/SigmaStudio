"""Assistant Orchestrator — Handles switch_agent routing for Sigma Assistant.

When Sigma Assistant decides a request needs a specialized agent,
it outputs: {"actions": [{"type": "switch_agent", "agent": "...", "message": "..."}]}
This module intercepts that action and re-routes the request.
"""

import os
import json
import re
import logging

from core.ai_providers import load_ai_config, call_ollama, call_openai_compatible, call_anthropic
from core.chat.prompt_builder import _get_manifesto_content
from core.task_handler import execute_ai_actions
from core.agent_registry import get_agent

log = logging.getLogger("sigma.orchestrator")

def get_routable_agents() -> dict:
    """Dynamically scan manifesti/ and manifesti/Private/ for all routable agents."""
    agents = {}
    manifesto_dir = 'manifesti'
    if os.path.isdir(manifesto_dir):
        for f in os.listdir(manifesto_dir):
            if f.endswith('.md') and f.lower() != 'readme.md':
                agent_id = f[:-3]
                agents[agent_id] = f"manifesti/{f}"
        p_dir = os.path.join(manifesto_dir, 'Private')
        if os.path.isdir(p_dir):
            for f in os.listdir(p_dir):
                if f.endswith('.md'):
                    agent_id = f[:-3]
                    agents[agent_id] = f"manifesti/Private/{f}"
    return agents


def handle_switch_agent(self, agent_name: str, message: str, history: list, bot_name: str = "Sigma Assistant") -> dict:
    """Route a request to a specialized agent and return its response.
    
    Args:
        self: HTTP handler instance
        agent_name: Name of the target agent (e.g. "code_architect")
        message: The message/prompt to send to the agent
        history: Chat history context
        bot_name: Original bot name
    
    Returns:
        Response dict with 'response', 'thinking', 'actions_log'
    """
    routable = get_routable_agents()
    manifesto_path = routable.get(agent_name) or routable.get(agent_name.lower().replace(' ', '_'))
    if not manifesto_path:
        return {
            "response": f"Agente '{agent_name}' non trovato. Agenti disponibili: {', '.join(routable.keys())}",
            "thinking": None,
            "actions_log": []
        }
    
    log.info("Routing to agent '%s' (manifesto: %s)", agent_name, manifesto_path)
    
    # Load the agent's system prompt
    system_prompt = _get_manifesto_content(manifesto_path)
    if not system_prompt.strip():
        system_prompt = f"Sei {agent_name}, un assistente specializzato in Sigma Studio."
    
    # Add the routing reason
    full_prompt = f"{system_prompt}\n\n---\nRichiesta inoltrata da Sigma Assistant: {message}"
    
    # Build messages
    messages = [{"role": "system", "content": full_prompt}]
    for h in history[-5:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})
    
    # Call the AI
    ai_cfg = load_ai_config()
    provider = ai_cfg.get("active_provider", "ollama")
    providers_config = ai_cfg.get("providers", {})
    active_prov_cfg = providers_config.get(provider, {})
    model = ai_cfg.get("model", "llama3.2")
    endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
    api_url = active_prov_cfg.get("api_url", "")
    api_key = active_prov_cfg.get("api_key", "")
    # Dynamic Execution Profile Tuning ("Intensità" dell'Agente)
    AGENT_PROFILE_MAP = {
        "math_researcher": "mathematics",
        "code_architect": "code",
        "viz_designer": "creative",
        "proof_reviewer": "analysis",
        "test_engineer": "code",
        "sigma_architect": "analysis",
        "sigma_admin": "conversation",
        "sigma_assistant": "conversation",
    }
    profile_key = AGENT_PROFILE_MAP.get(agent_name, "code")
    from core.ai_providers import apply_execution_profile
    tuned_cfg = apply_execution_profile(profile_key, active_prov_cfg)

    temperature = tuned_cfg.get("temperature", 0.3)
    max_tokens = tuned_cfg.get("max_tokens", 8192)
    top_p = tuned_cfg.get("top_p", 0.9)
    num_ctx = tuned_cfg.get("num_ctx", 16384)
    top_k = tuned_cfg.get("top_k", 40)
    repeat_penalty = tuned_cfg.get("repeat_penalty", 1.1)
    timeout = tuned_cfg.get("timeout", 120)

    log.info("Centralino Switchboard -> Agent '%s' | Profilo: '%s' | Temp: %.2f | Ctx: %d",
             agent_name, profile_key, temperature, num_ctx)

    if provider == "ollama":
        seed = tuned_cfg.get("seed", 0)
        ai_response, ai_thinking, error = call_ollama(
            messages, model, endpoint, temperature, max_tokens, top_p,
            top_k, repeat_penalty, num_ctx, seed, timeout
        )
    elif "anthropic" in api_url.lower():
        ai_response, error = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
        ai_thinking = None
    else:
        ai_response, ai_thinking, error = call_openai_compatible(
            messages, model, api_url, api_key, temperature, max_tokens, top_p, timeout
        )
    
    if error:
        return {"response": f"Errore agente {agent_name}: {error}", "thinking": None, "actions_log": []}
    
    # Parse JSON + execute actions
    from core.chat.response_parser import _extract_json_from_response, _clean_all_tags, _format_response
    
    clean_response, extracted_thinking = _clean_all_tags(ai_response)
    thinking = ai_thinking or extracted_thinking
    actions_log = []
    
    json_match = _extract_json_from_response(clean_response)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            clean_response = parsed.get("response", clean_response)
            clean_response = _format_response(clean_response)
            json_thinking = parsed.get("thinking", None)
            if json_thinking:
                thinking = json_thinking
            
            actions = parsed.get("actions", [])
            if actions:
                # Re-inject the routing context
                for action in actions:
                    if action.get("type") in ("create_file", "edit_file"):
                        log.info("Agent %s executing: %s %s", agent_name, action["type"], action.get("path", ""))
                
                actions_log = execute_ai_actions(self, actions, agent_name)
        except Exception as e:
            log.error("Parse error for agent %s: %s", agent_name, e)
    
    # Auto-extract text files only if the user explicitly requested file creation
    _create_keywords = ['crea', 'scrivi', 'genera', 'salva', 'file', 'documento', 'modulo', 'argomento']
    user_requested_creation = any(kw in message.lower() for kw in _create_keywords)
    
    if user_requested_creation and not any(a.get("type") in ("create_file", "edit_file") for a in actions_log) and len(clean_response) > 50:
        try:
            from core.chat_handler import _extract_and_create_files_from_text
            created = _extract_and_create_files_from_text(clean_response, message)
            for cp in created:
                actions_log.append({
                    "type": "create_file", "success": True, "path": cp,
                    "message": f"File creato da {agent_name}: {cp}"
                })
        except Exception as exc:
            log.error("Agent %s auto file extraction error: %s", agent_name, exc)

    return {
        "response": clean_response,
        "thinking": thinking,
        "actions_log": actions_log
    }
