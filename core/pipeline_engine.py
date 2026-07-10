"""Pipeline Engine for Sigma Studio — Esegue pipeline DAG di agenti con feedback loop.
Carica definizioni pipeline da JSON, ordina i nodi topologicamente, esegue ogni nodo
chiamando l'agente appropriato, gestisce feedback loops (revisione → correzione)
e produce report finale. Termina quando tutti i nodi sono eseguiti con successo
e la revisione finale non trova errori."""

import os
import json
import datetime
import threading
import concurrent.futures
import re
from core.ai_providers import load_ai_config, resolve_provider_config, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.agent_registry import get_agent, increment_usage
from core.agent_memory import save_session_memory, get_memory_context
from core.chat_handler import _get_manifesto_content, _get_time_context, _build_filesystem_context, _extract_json_from_response, _collect_context_files
from core.output_validator import validate_agent_output

# ==============================================================================
# CONSTANTS
# ==============================================================================

MAX_FEEDBACK_ITERATIONS = 3  # Max correction cycles per node
PIPELINE_STATUS_DIR = "scratch/pipelines"
MAX_WORKERS = 10  # Max parallel threads for node execution

# Ensure pipeline status directory exists
os.makedirs(PIPELINE_STATUS_DIR, exist_ok=True)

# ==============================================================================
# PIPELINE STATUS MANAGEMENT
# ==============================================================================

_active_pipelines = {}  # In-memory: pipeline_id -> status dict


def _save_checkpoint(pipeline_id: str, pipeline_status: dict):
    """Save pipeline checkpoint to disk for resume/audit."""
    checkpoints = _load_checkpoints()
    checkpoints[pipeline_id] = pipeline_status
    ckpt_path = os.path.join(PIPELINE_STATUS_DIR, f"{pipeline_id}.json")
    with open(ckpt_path, "w", encoding="utf-8") as f:
        json.dump(pipeline_status, f, indent=2)


def _load_checkpoints() -> dict:
    """Load all pipelines from disk checkpoint files."""
    checkpoints = {}
    if not os.path.isdir(PIPELINE_STATUS_DIR):
        return checkpoints
    for fname in os.listdir(PIPELINE_STATUS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(PIPELINE_STATUS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pid = data.get("id", fname.replace(".json", ""))
                    checkpoints[pid] = data
            except Exception:
                pass
    return checkpoints


def _get_parallel_levels(execution_order: list, connections: list) -> list:
    """Group node IDs into parallel execution levels.
    
    Nodes at the same level have no dependencies on each other and can run in parallel.
    Returns list of lists: [[level0_nodes], [level1_nodes], ...]
    """
    # Compute in-degree for each node
    in_deg = {nid: 0 for nid in execution_order}
    for conn in connections:
        to = conn.get("to", "")
        if to in in_deg:
            in_deg[to] += 1
    
    levels = []
    remaining = set(execution_order)
    current_indeg = dict(in_deg)
    
    while remaining:
        # Find nodes with in_deg == 0 (no unresolved dependencies)
        ready = [nid for nid in remaining if current_indeg.get(nid, 0) == 0]
        if not ready:
            break  # Cycle or error
        
        levels.append(ready)
        for nid in ready:
            remaining.remove(nid)
            # Reduce in_deg for downstream nodes
            for conn in connections:
                if conn.get("from") == nid:
                    to = conn.get("to", "")
                    if to in current_indeg and current_indeg[to] > 0:
                        current_indeg[to] -= 1
    
    return levels


def _evaluate_condition(node_result: dict, condition: dict) -> bool:
    """Evaluate a routing condition against a node's execution result.
    
    Args:
        node_result: Dict from _execute_node result with 'success', 'actions_log', 'review_notes', etc.
        condition: Dict with 'field', 'operator', 'value'
    
    Returns:
        True if condition matches, False otherwise
    """
    if not condition or not condition.get("enabled"):
        return True  # No condition = always proceed
    
    field = condition.get("field", "response")
    operator = condition.get("operator", "contains")
    expected = condition.get("value", "")
    
    # Get the actual value from node result
    if field == "success":
        actual = str(node_result.get("success", False))
    elif field == "fail_count":
        actual = str(node_result.get("failed_actions", 0))
    elif field == "success_count":
        actual = str(node_result.get("successful_actions", 0))
    elif field == "actions_count":
        actual = str(node_result.get("total_actions", 0))
    elif field == "has_error":
        actual = "true" if node_result.get("error") else "false"
    elif field == "review_notes":
        notes = node_result.get("review_notes", "")
        actual = notes if notes else ""
    elif field == "response":
        # Try to get from the first action's message
        actions = node_result.get("actions_log", [])
        actual = " ".join(a.get("message", "") for a in actions)
    else:
        actual = str(node_result.get(field, ""))
    
    # Apply operator
    if operator == "contains":
        return expected.lower() in actual.lower()
    elif operator == "not_contains":
        return expected.lower() not in actual.lower()
    elif operator == "equals":
        return actual.lower() == expected.lower()
    elif operator == "starts_with":
        return actual.lower().startswith(expected.lower())
    elif operator == "regex":
        try:
            return bool(re.search(expected, actual))
        except Exception:
            return False
    elif operator == "gt":
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "gte":
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "lt":
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == "lte":
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False
    
    return True  # Default: proceed


def _load_pipeline_def(path: str) -> dict:
    """Load a pipeline definition from JSON file."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _topological_sort(nodes: list, connections: list) -> list:
    """Sort nodes in topological order based on connections (DAG).
    
    Args:
        nodes: List of node dicts with 'id'
        connections: List of {'from': node_id, 'to': node_id}
    
    Returns:
        List of node ids in execution order
    """
    # Build adjacency and in-degree maps
    adj = {n["id"]: [] for n in nodes}
    in_deg = {n["id"]: 0 for n in nodes}
    
    for conn in connections:
        frm = conn.get("from", "")
        to = conn.get("to", "")
        if frm in adj and to in adj:
            adj[frm].append(to)
            in_deg[to] = in_deg.get(to, 0) + 1
    
    # Kahn's algorithm
    queue = [nid for nid, deg in in_deg.items() if deg == 0]
    sorted_nodes = []
    
    while queue:
        node = queue.pop(0)
        sorted_nodes.append(node)
        for neighbor in adj.get(node, []):
            in_deg[neighbor] -= 1
            if in_deg[neighbor] == 0:
                queue.append(neighbor)
    
    return sorted_nodes


def _get_upstream_nodes(node_id: str, connections: list) -> list:
    """Get all nodes that feed into the given node (upstream dependencies)."""
    upstream = []
    for conn in connections:
        if conn.get("to") == node_id:
            upstream.append(conn.get("from"))
    return upstream


def _get_node_by_id(nodes: list, node_id: str) -> dict:
    """Get a node definition by its ID."""
    for n in nodes:
        if n["id"] == node_id:
            return n
    return None


def _map_role_to_agent_id(role: str) -> str:
    """Map pipeline node role to registered agent ID."""
    role_map = {
        "researcher": "math1",
        "mathematician": "math1",
        "coder": "test-engineer",
        "tester": "test-engineer",
        "critic": "proof-reviewer",
        "reviewer": "proof-reviewer",
        "analyst": "viz-designer",
        "visualizer": "viz-designer",
        "architect": "sigma_architect",
        "developer": "code_architect",
    }
    return role_map.get(role, "sigma_architect")


# ==============================================================================
# AI MODEL CALL
# ==============================================================================

def _call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    """Call AI model and return response."""
    route_provider = provider
    if route_provider not in ('ollama', 'api', 'anthropic'):
        route_provider = 'api' if 'anthropic' not in api_url.lower() else 'anthropic'
    ac = ai_cfg.get("providers", {}).get(provider, {})
    try:
        if route_provider == "ollama":
            return call_ollama(messages, model, endpoint, temperature, max_tokens, top_p,
                ac.get("top_k", 40), ac.get("repeat_penalty", 1.1), ac.get("num_ctx", 8192), ac.get("seed", 0), request_timeout)
        elif route_provider == "api":
            return call_openai_compatible(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
        elif route_provider == "anthropic":
            r = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
            return r[0], None, r[1] if len(r) > 1 else None
    except Exception as e:
        return None, None, str(e)
    return None, None, "Provider sconosciuto"


def _load_agent_config_for_node(ai_cfg: dict, node_config: dict, agent_id: str) -> tuple:
    """Load config for a pipeline node's agent.
    
    Returns:
        (provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout)
    """
    # First try node-specific config
    model = node_config.get("model", ai_cfg.get("model", "llama3.2"))
    provider = node_config.get("provider", ai_cfg.get("active_provider", "ollama"))
    temperature = node_config.get("temperature", ai_cfg.get("temperature", 0.7))
    # Use provider's max_tokens from config, fallback to 32768 for large responses
    max_tokens = node_config.get("max_tokens", ai_cfg.get("max_tokens", 65536))
    top_p = node_config.get("top_p", ai_cfg.get("top_p", 0.9))
    
    # If agent specified, try to use its model
    agent = get_agent(agent_id)
    if agent and agent.get("models"):
        model = agent["models"][0]
    
    providers_config = ai_cfg.get("providers", {})
    prov_cfg = providers_config.get(provider, {})
    
    endpoint = prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
    api_url = prov_cfg.get("api_url", "")
    api_key = prov_cfg.get("api_key", "")
    request_timeout = prov_cfg.get("timeout", 300)
    
    # Try provider resolution for this model
    dp, dpv = resolve_provider_config(ai_cfg, model)
    if dpv:
        provider = dp
        if dpv.get("endpoint"): endpoint = dpv["endpoint"]
        if dpv.get("api_url"): api_url = dpv["api_url"]
        if dpv.get("api_key"): api_key = dpv["api_key"]
        temperature = dpv.get("temperature", temperature)
        max_tokens = dpv.get("max_tokens", max_tokens)
        top_p = dpv.get("top_p", top_p)
    
    return provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout


# ==============================================================================
# NODE EXECUTION (Single Pipeline Node)
# ==============================================================================

def _execute_node(self, node_def: dict, pipeline_goal: str, context_from_upstream: list,
                  stream_callback, node_results: dict, feedback_iteration: int = 0) -> dict:
    """Execute a single pipeline node.
    
    This is the core execution function: it calls the agent assigned to this node,
    collects actions, validates output, and returns results.
    
    Args:
        self: SigmaAPIHandler instance (for execute_ai_actions)
        node_def: Node definition from pipeline JSON
        pipeline_goal: Overall pipeline goal
        context_from_upstream: List of action logs from upstream nodes
        stream_callback: SSE streaming callback
        node_results: Dict of node_id -> result for all previously executed nodes
        feedback_iteration: Current feedback iteration (0-based)
    
    Returns:
        Dict with node execution result
    """
    node_id = node_def["id"]
    node_label = node_def.get("label", node_id)
    role = node_def.get("config", {}).get("role", "general")
    node_config = node_def.get("config", {})
    
    # Map role to registered agent
    agent_id = _map_role_to_agent_id(role)
    agent = get_agent(agent_id)
    agent_name = agent.get("name", node_label) if agent else node_label
    
    if stream_callback:
        stream_callback({
            "type": "pipeline_node_start",
            "node_id": node_id,
            "node_label": node_label,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "feedback_iteration": feedback_iteration + 1,
            "message": f"▶️ Esecuzione nodo '{node_label}' (iterazione {feedback_iteration + 1}/{MAX_FEEDBACK_ITERATIONS})"
        })
    
    # Load configuration
    ai_cfg = load_ai_config()
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        _load_agent_config_for_node(ai_cfg, node_config, agent_id)
    
    # Build system prompt from agent manifesto
    manifesto_path = agent.get("manifesto", "") if agent else ""
    system_prompt = _get_manifesto_content(manifesto_path)
    if not system_prompt.strip():
        # Fallback: generic prompt based on role
        system_prompt = f"Sei {agent_name}, un assistente AI specializzato in {role}. Rispondi in italiano."
    
    # Build context
    time_ctx = _get_time_context()
    fs_context = _build_filesystem_context()
    memory_context = get_memory_context(agent_id) if agent_id else ""
    
    # Build upstream context (what previous nodes produced)
    upstream_context = ""
    if context_from_upstream:
        upstream_context = "\n\n## CONTESTO DAI NODI PRECEDENTI\n"
        for ctx in context_from_upstream:
            node_id_src = ctx.get("node_id", "?")
            node_label_src = ctx.get("node_label", "?")
            actions = ctx.get("actions_log", [])
            files_created = [a for a in actions if a.get("type") == "create_file" and a.get("success")]
            tests_run = [a for a in actions if a.get("type") == "run_test" and a.get("success")]
            
            upstream_context += f"\n### {node_label_src}\n"
            if files_created:
                upstream_context += f"- File creati: {', '.join(f.get('path', '?') for f in files_created)}\n"
            if tests_run:
                upstream_context += f"- Test eseguiti: {len(tests_run)}\n"
    
    # Build feedback context (if this is a re-execution due to review failure)
    feedback_context = ""
    if feedback_iteration > 0:
        # Get the review that triggered this re-execution
        reviewer_id = None
        for nid, nres in node_results.items():
            ndef = _get_node_by_id([n["id"] for n in _load_pipeline_def(req.get("pipeline_path", "pipeline.json")).get("nodes", [])], nid)
            # We'll use stored review notes
            nres_data = nres if isinstance(nres, dict) else {}
            if nres_data.get("review_notes"):
                reviewer_id = nid
        
        feedback_context = f"\n\n## FEEDBACK DI REVISIONE (Iterazione {feedback_iteration})\n"
        # Collect all review notes from reviewer nodes
        for nid, nres in node_results.items():
            nres_data = nres if isinstance(nres, dict) else {}
            review = nres_data.get("review_notes", "")
            if review:
                feedback_context += f"\nDa nodo '{nid}':\n{review}\n"
        
        feedback_context += "\nCorreggi gli errori segnalati prima di procedere."
    
    # Build the action prompt
    action_prompt = f"""
## OBIETTIVO GENERALE DELLA PIPELINE
{pipeline_goal}

## RUOLO ATTUALE
Sei {agent_name}. Il tuo compito specifico è:

{_get_role_instructions(role, node_label)}

## REGOLE OBBLIGATORIE
- Rispondi SOLO con JSON: {{"response": "...", "actions": [...]}}
- Usa tipi di azione validi: create_file, edit_file, run_test, read_file, update_task
- Struttura corretta: data/<topic>/<NN_modulo>/<sezione>/<file>
- Sezioni permesse: teoria/, test/, viz/, docs/, whitepapers/
- Alla fine del lavoro, imposta "done": true nel JSON
- Non ripetere lavoro già fatto dai nodi precedenti
"""
    
    full_system = f"{system_prompt}\n\n{time_ctx}\n\n{action_prompt}"
    if fs_context:
        full_system += f"\n\nStruttura progetto:\n{fs_context[:2000]}"
    if memory_context:
        full_system += f"\n\n{memory_context}"
    if upstream_context:
        full_system += upstream_context
    if feedback_context:
        full_system += feedback_context
    
    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": f"Esegui il tuo compito per la pipeline. Obiettivo: {pipeline_goal[:200]}"}
    ]
    
    # Execute with iterations
    max_local_iterations = 5
    all_actions_log = []
    
    for iteration in range(max_local_iterations):
        response, thinking, error = _call_ai_model(
            messages, ai_cfg, 
            node_config.get("model", agent.get("models", [ai_cfg.get("model", "llama3.2")])[0] if agent else ai_cfg.get("model", "llama3.2")),
            provider, endpoint, api_url, api_key,
            node_config.get("temperature", temperature), 
            node_config.get("max_tokens", max_tokens * 2) if node_config.get("max_tokens") else max_tokens * 2,
            node_config.get("top_p", top_p), timeout
        )
        
        if error:
            if stream_callback:
                stream_callback({
                    "type": "pipeline_node_error",
                    "node_id": node_id,
                    "iteration": iteration + 1,
                    "error": error
                })
            return {
                "node_id": node_id,
                "node_label": node_label,
                "success": False,
                "error": error,
                "actions_log": all_actions_log
            }
        
        if not response:
            break
        
        json_match = _extract_json_from_response(response)
        if not json_match:
            break
        
        try:
            parsed = json.loads(json_match.group())
            
            # Validate output
            is_valid, validation_errors = validate_agent_output(agent_id or "default", parsed)
            if not is_valid:
                if stream_callback:
                    stream_callback({
                        "type": "pipeline_validation_error",
                        "node_id": node_id,
                        "errors": validation_errors
                    })
                # Try again with clearer instructions
                messages.append({"role": "system", "content": f"ERRORE DI VALIDAZIONE: {'; '.join(validation_errors)}. Correggi il formato JSON."})
                continue
            
            ai_response = parsed.get("response", "")
            actions = parsed.get("actions", [])
            is_done = parsed.get("done", False)
            
            if not actions:
                # No actions to perform, consider done
                break
            
            # Execute actions
            iteration_log = execute_ai_actions(self, actions, agent_name)
            all_actions_log.extend(iteration_log)
            
            success_count = sum(1 for a in iteration_log if a.get("success"))
            fail_count = sum(1 for a in iteration_log if not a.get("success"))
            
            if stream_callback:
                stream_callback({
                    "type": "pipeline_node_iteration",
                    "node_id": node_id,
                    "node_label": node_label,
                    "iteration": iteration + 1,
                    "max_iterations": max_local_iterations,
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "actions_log": iteration_log,
                    "ai_response": ai_response[:1000] if ai_response else ""
                })
            
            # Check completion
            if is_done or (success_count > 0 and fail_count == 0):
                break
            
            # Prepare next iteration with feedback
            if fail_count > 0:
                details = "\n".join(f"  {'✅' if a.get('success') else '❌'} {a.get('type','?')}: {a.get('message', a.get('error',''))}" 
                                  for a in iteration_log)
                feedback = f"📋 Iterazione {iteration + 1}: {success_count}/{len(iteration_log)} azioni riuscite\n\nAzioni fallite:\n{details}\n\nCorreggi e completa."
                messages.append({"role": "system", "content": feedback})
            
        except json.JSONDecodeError:
            break
    
    # Save memory for this agent
    if agent_id:
        total_success = sum(1 for a in all_actions_log if a.get("success"))
        total_fail = sum(1 for a in all_actions_log if not a.get("success"))
        try:
            save_session_memory(agent_id, {
                "goal": f"[Pipeline:{node_id}] {pipeline_goal[:80]}",
                "actions_performed": all_actions_log,
                "success_count": total_success,
                "fail_count": total_fail,
                "learning": "",
                "summary": f"Pipeline node {node_label}: {total_success}✅/{total_fail}❌"
            })
            increment_usage(agent_id, success=total_fail == 0)
        except Exception:
            pass
    
    total_success = sum(1 for a in all_actions_log if a.get("success"))
    overall_success = total_success > 0 or len(all_actions_log) == 0
    
    if stream_callback:
        status = "✅" if overall_success else "❌"
        stream_callback({
            "type": "pipeline_node_complete",
            "node_id": node_id,
            "node_label": node_label,
            "success": overall_success,
            "total_actions": len(all_actions_log),
            "successful_actions": total_success,
            "message": f"{status} Nodo '{node_label}': {total_success}/{len(all_actions_log)} azioni riuscite"
        })
    
    return {
        "node_id": node_id,
        "node_label": node_label,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "success": overall_success,
        "error": None,
        "actions_log": all_actions_log,
        "total_actions": len(all_actions_log),
        "successful_actions": total_success,
        "failed_actions": len(all_actions_log) - total_success,
        "feedback_iteration": feedback_iteration,
        "review_notes": "",  # Will be filled by reviewer
    }


def _get_role_instructions(role: str, node_label: str) -> str:
    """Get specific instructions for a pipeline role."""
    instructions = {
        "researcher": """- Analizza il problema matematico/scientifico
- Produci documentazione teorica (teoria/)
- Scrivi definizioni, teoremi, dimostrazioni
- Usa notazione LaTeX per le formule
- Crea file .md con nomenclatura chiara""",
        
        "mathematician": """- Analizza il problema con focus su classi modulo 6
- Produci documentazione formale in teoria/
- Scrivi definizioni, teoremi, dimostrazioni rigorose
- Usa notazione LaTeX ($...$ inline, $$...$$ display)
- Verifica le transizioni tra classi""",
        
        "coder": """- Scrivi test Python in test/ per verificare la teoria
- I test devono essere eseguibili con: python -u <path>
- Usa la funzione T(n) = n/2 se pari, (3n+1)/2 se dispari
- Ogni test deve avere output chiaro (print)
- Verifica le transizioni con esempi computazionali""",
        
        "tester": """- Scrivi test Python in test/ per verificare la teoria prodotta
- I test devono coprire tutti i casi esposti nella teoria
- Usa assert e print per risultati chiari
- Verifica computazionalmente ogni affermazione""",
        
        "critic": """- Revisiona criticamente i file prodotti dai nodi precedenti
- Cerca controesempi, errori logici, incongruenze
- Verifica che le transizioni siano corrette
- Se trovi errori, produci un report di revisione dettagliato
- Se tutto è corretto, conferma con validazione formale""",
        
        "reviewer": """- Leggi TUTTI i file di teoria, test e visualizzazioni
- Verifica la correttezza logica di ogni affermazione
- Cerca errori, omissioni, incongruenze
- Produci un report di validazione in docs/
- Se trovi errori, usa update_task per segnalarli
- Se tutto è corretto, conferma e marca come validato""",
        
        "analyst": """- Crea visualizzazioni interattive in viz/
- Usa D3.js via CDN per grafici autonomi (.html)
- Tema scuro coerente con Sigma Studio
- Includi legenda, tooltip, zoom
- Visualizza le transizioni, i dati e i pattern scoperti""",
        
        "visualizer": """- Crea visualizzazioni HTML/D3.js in viz/
- Ogni file deve essere autonomo (D3 via CDN)
- Usa tema scuro glass-morphism
- Aggiungi tooltip interattivi e legende
- Visualizza i risultati della ricerca""",
        
        "architect": """- Coordina il lavoro degli altri agenti
- Assicurati che la struttura dei moduli sia corretta
- Verifica che tutti i file siano nei path giusti
- Aggiorna tasks.json con lo stato dei lavori""",
        
        "developer": """- Modifica codice frontend/backend se necessario
- Non modificare file in data/ (ricerca)
- Fai backup prima di ogni modifica
- Verifica il build dopo ogni modifica""",
    }
    
    return instructions.get(role, f"- Esegui il compito del nodo '{node_label}' nella pipeline")


# ==============================================================================
# REVIEW NODE (Special: validates and may trigger feedback)
# ==============================================================================

def _execute_review_node(self, node_def: dict, pipeline_goal: str, 
                          all_node_results: dict, stream_callback) -> dict:
    """Execute a reviewer/critic node with special feedback loop logic.
    
    The reviewer reads all files produced so far, validates them, and either:
    - Confirms correctness (done: true)
    - Reports errors that trigger re-execution of upstream nodes
    
    Returns:
        Dict with review result including 'review_notes' and 'needs_correction'
    """
    node_id = node_def["id"]
    node_label = node_def.get("label", node_id)
    role = node_def.get("config", {}).get("role", "reviewer")
    node_config = node_def.get("config", {})
    
    agent_id = _map_role_to_agent_id(role)
    agent = get_agent(agent_id)
    agent_name = agent.get("name", node_label) if agent else node_label
    
    if stream_callback:
        stream_callback({
            "type": "pipeline_review_start",
            "node_id": node_id,
            "node_label": node_label,
            "agent_name": agent_name,
            "message": f"🔍 {agent_name} sta revisionando i risultati..."
        })
    
    ai_cfg = load_ai_config()
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        _load_agent_config_for_node(ai_cfg, node_config, agent_id)
    
    # Build review context: list all files created by upstream nodes
    all_files = []
    for nid, nres in all_node_results.items():
        if not isinstance(nres, dict):
            continue
        actions = nres.get("actions_log", [])
        for act in actions:
            if act.get("type") == "create_file" and act.get("success"):
                all_files.append(act.get("path", ""))
    
    # Build system prompt
    manifesto_path = agent.get("manifesto", "") if agent else ""
    system_prompt = _get_manifesto_content(manifesto_path)
    if not system_prompt.strip():
        system_prompt = f"Sei {agent_name}, un revisore critico specializzato. Revisiona il lavoro prodotto."
    
    review_prompt = f"""
## OBIETTIVO DELLA PIPELINE
{pipeline_goal}

## COMPITO DI REVISIONE
Sei {agent_name}. Il tuo compito è revisionare criticamente TUTTI i file prodotti dai nodi precedenti della pipeline.

### File prodotti da revisionare:
{chr(10).join(f"- {f}" for f in all_files) if all_files else "(Nessun file trovato)"}

### Cosa verificare:
1. Correttezza logica e matematica
2. Completezza della documentazione
3. Qualità del codice (test funzionanti)
4. Coerenza tra teoria, test e visualizzazioni
5. Eventuali errori o omissioni

### Output richiesto — SOLO JSON:
{{"response": "...", "review_notes": "Dettaglio degli errori trovati (o 'Nessun errore')", 
  "needs_correction": true/false, "action": "approve"|"correct",
  "actions": [azioni di correzione se needed]}}
  
- needs_correction: true se ci sono errori da correggere
- action: "approve" se tutto OK, "correct" se servono correzioni
- Se needs_correction è true, includi azioni per correggere (es. update_task, create_file report)
"""
    
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n{review_prompt}"},
        {"role": "user", "content": f"Revisiona il lavoro della pipeline per l'obiettivo: {pipeline_goal[:200]}"}
    ]
    
    response, thinking, error = _call_ai_model(
        messages, ai_cfg,
        node_config.get("model", agent.get("models", [ai_cfg.get("model", "llama3.2")])[0] if agent else ai_cfg.get("model", "llama3.2")),
        provider, endpoint, api_url, api_key,
        node_config.get("temperature", 0.3),  # Low temp for review precision
        node_config.get("max_tokens", max_tokens) if node_config.get("max_tokens") else max_tokens,
        node_config.get("top_p", top_p), timeout
    )
    
    review_result = {
        "node_id": node_id,
        "node_label": node_label,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "success": False,
        "error": error,
        "actions_log": [],
        "review_notes": "",
        "needs_correction": True,
        "all_files_reviewed": all_files,
    }
    
    if error:
        if stream_callback:
            stream_callback({"type": "pipeline_review_error", "node_id": node_id, "error": error})
        return review_result
    
    if not response:
        review_result["success"] = True
        review_result["needs_correction"] = False
        return review_result
    
    json_match = _extract_json_from_response(response)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            review_notes = parsed.get("review_notes", "")
            needs_correction = parsed.get("needs_correction", True)
            review_action = parsed.get("action", "correct")
            
            # Execute any correction actions
            actions = parsed.get("actions", [])
            if actions:
                iteration_log = execute_ai_actions(self, actions, agent_name)
                review_result["actions_log"] = iteration_log
            
            review_result["success"] = True
            review_result["review_notes"] = review_notes
            review_result["needs_correction"] = needs_correction and review_action == "correct"
            
            if stream_callback:
                status = "❌" if review_result["needs_correction"] else "✅"
                stream_callback({
                    "type": "pipeline_review_complete",
                    "node_id": node_id,
                    "node_label": node_label,
                    "needs_correction": review_result["needs_correction"],
                    "review_notes": review_notes[:300] if review_notes else "",
                    "message": f"{status} Revisione: {'errori trovati' if review_result['needs_correction'] else 'tutto corretto'}"
                })
            
        except json.JSONDecodeError:
            pass
    
    return review_result


# ==============================================================================
# MAIN PIPELINE EXECUTION
# ==============================================================================

def _build_connection_map(connections: list) -> dict:
    """Build a map from node_id -> list of downstream connections."""
    conn_map = {}  # from_node_id -> [connection dicts]
    for conn in connections:
        frm = conn.get("from", "")
        if frm:
            conn_map.setdefault(frm, []).append(conn)
    return conn_map


def run_pipeline(self, req, stream_callback=None) -> dict:
    """Execute a full pipeline DAG with feedback loops.
    
    Args:
        self: SigmaAPIHandler instance
        req: Request dict with:
            - "pipeline_path": Path to pipeline JSON file (optional, default pipeline.json)
            - "nodes": Optional inline node definitions (overrides file)
            - "connections": Optional inline connections (overrides file)
            - "goal": Custom goal override (optional)
            - "agent_configs": Dict of agent_id -> {provider, model, temperature} overrides
            - "max_execution_minutes": Global timeout in minutes (default 30)
        stream_callback: SSE streaming callback
    
    Returns:
        Final pipeline report dict
    """
    pipeline_path = req.get("pipeline_path", "pipeline.json")
    goal_override = req.get("goal", "")
    agent_configs = req.get("agent_configs", {}) or {}
    max_minutes = req.get("max_execution_minutes", 30)
    
    # Load pipeline definition (file or inline)
    pipeline_def = None
    if req.get("nodes") and req.get("connections"):
        # Inline definition from PipelineDesigner
        pipeline_def = {
            "goal": goal_override or req.get("goal", "Pipeline personalizzata"),
            "nodes": req["nodes"],
            "connections": req["connections"],
        }
        pipeline_path = pipeline_def.get("goal", "inline_pipeline")[:40]
    else:
        pipeline_def = _load_pipeline_def(pipeline_path)
    
    if not pipeline_def:
        return {"error": f"Pipeline '{pipeline_path}' non trovata"}, 404
    
    goal = goal_override or pipeline_def.get("goal", "Pipeline automatizzata")
    nodes = pipeline_def.get("nodes", [])
    connections = pipeline_def.get("connections", [])
    
    if not nodes:
        return {"error": "Nessun nodo definito nella pipeline"}, 400
    
    # Merge agent config overrides into node configs
    if agent_configs:
        for node in nodes:
            node_id = node.get("id", "")
            if node_id in agent_configs:
                ac = agent_configs[node_id]
                if "provider" in ac:
                    node.setdefault("config", {})["provider"] = ac["provider"]
                if "model" in ac:
                    node.setdefault("config", {})["model"] = ac["model"]
                if "temperature" in ac:
                    node.setdefault("config", {})["temperature"] = ac["temperature"]
    
    # Topological sort
    execution_order = _topological_sort(nodes, connections)
    
    # Parallel execution levels (for future parallel mode)
    parallel_levels = _get_parallel_levels(execution_order, connections)
    
    # Build connection map for conditional routing
    conn_map = _build_connection_map(connections)
    
    if stream_callback:
        stream_callback({
            "type": "pipeline_start",
            "pipeline": pipeline_path,
            "goal": goal[:200],
            "total_nodes": len(nodes),
            "execution_order": execution_order,
            "parallel_levels": parallel_levels,
            "message": f"🚀 Avvio pipeline {pipeline_path}: {len(nodes)} nodi, {len(connections)} connessioni, {len(parallel_levels)} livelli paralleli"
        })
    
    # Store active pipeline with timeout
    started_at = datetime.datetime.now()
    pipeline_id = started_at.strftime("%Y%m%d_%H%M%S")
    pipeline_status = {
        "id": pipeline_id,
        "goal": goal,
        "pipeline_path": pipeline_path,
        "started_at": started_at.isoformat(),
        "status": "running",
        "nodes_completed": 0,
        "nodes_failed": 0,
        "current_node": "",
        "feedback_iterations": 0,
        "max_execution_minutes": max_minutes,
        "parallel_levels": len(parallel_levels),
        "skipped_nodes": [],
    }
    _active_pipelines[pipeline_id] = pipeline_status
    
    # Execute nodes in topological order
    node_results = {}  # node_id -> result dict
    all_actions_log = []
    feedback_cycles = 0
    skipped_nodes = []
    
    try:
        for idx, node_id in enumerate(execution_order):
            # Check global timeout
            elapsed = (datetime.datetime.now() - started_at).total_seconds() / 60
            if elapsed > max_minutes:
                raise TimeoutError(f"Pipeline timeout dopo {max_minutes} minuti")
            
            # Check if pipeline was stopped externally
            if _active_pipelines.get(pipeline_id, {}).get("status") in ("stopped",):
                if stream_callback:
                    stream_callback({"type": "pipeline_stopped", "message": "Pipeline fermata dall'utente"})
                break
            
            node_def = _get_node_by_id(nodes, node_id)
            if not node_def:
                continue
            
            pipeline_status["current_node"] = node_id
            role = node_def.get("config", {}).get("role", "general")
            
            # --- CONDITIONAL ROUTING: evaluate conditions from upstream connections ---
            # Before executing, check if any upstream connection has a condition that
            # controls routing TO this node (i.e., condition on the edge that comes here)
            should_execute = True
            for conn in connections:
                if conn.get("to") == node_id:
                    condition = conn.get("condition", {})
                    if condition and condition.get("enabled"):
                        from_node = conn.get("from", "")
                        from_result = node_results.get(from_node, {})
                        if not _evaluate_condition(from_result, condition):
                            should_execute = False
                            if stream_callback:
                                stream_callback({
                                    "type": "pipeline_node_skipped",
                                    "node_id": node_id,
                                    "node_label": node_def.get("label", node_id),
                                    "reason": f"Condizione '{condition.get('operator', '?')}' su '{condition.get('field', '?')}' non soddisfatta"
                                })
                            break
            
            if not should_execute:
                skipped_nodes.append(node_id)
                pipeline_status["skipped_nodes"] = skipped_nodes
                continue
            
            # Get context from upstream nodes
            upstream_ids = _get_upstream_nodes(node_id, connections)
            context_from_upstream = []
            for uid in upstream_ids:
                if uid in node_results:
                    context_from_upstream.append(node_results[uid])
            
            # Check if this is a reviewer/critic node (special handling)
            is_reviewer = role in ("critic", "reviewer")
            
            if is_reviewer:
                # Execute review with feedback loop
                feedback_iteration = 0
                review_result = None
                
                while feedback_iteration <= MAX_FEEDBACK_ITERATIONS:
                    review_result = _execute_review_node(
                        self, node_def, goal, node_results, stream_callback
                    )
                    
                    if not review_result.get("needs_correction"):
                        break
                    
                    feedback_iteration += 1
                    feedback_cycles += 1
                    pipeline_status["feedback_iterations"] = feedback_cycles
                    
                    if feedback_iteration >= MAX_FEEDBACK_ITERATIONS:
                        if stream_callback:
                            stream_callback({
                                "type": "pipeline_feedback_max",
                                "message": f"⚠️ Raggiunto massimo iterazioni di feedback ({MAX_FEEDBACK_ITERATIONS}). Forzatura approvazione."
                            })
                        review_result["needs_correction"] = False
                        break
                    
                    # Re-execute upstream nodes with feedback
                    for uid in upstream_ids:
                        if uid in node_results:
                            upstream_node = _get_node_by_id(nodes, uid)
                            if upstream_node:
                                if stream_callback:
                                    stream_callback({
                                        "type": "pipeline_feedback_loop",
                                        "from_node": uid,
                                        "to_node": node_id,
                                        "iteration": feedback_iteration,
                                        "message": f"🔄 Feedback loop: {uid} → {node_id} (iterazione {feedback_iteration})"
                                    })
                                
                                newer_result = _execute_node(
                                    self, upstream_node, goal, 
                                    [node_results.get(u) for u in _get_upstream_nodes(uid, connections) if u in node_results],
                                    stream_callback, node_results, feedback_iteration
                                )
                                node_results[uid] = newer_result
                                if newer_result.get("actions_log"):
                                    all_actions_log.extend(newer_result["actions_log"])
                
                if review_result:
                    node_results[node_id] = review_result
                    if review_result.get("actions_log"):
                        all_actions_log.extend(review_result["actions_log"])
            else:
                # Normal node execution with ERROR RECOVERY (retry up to 2 times)
                max_retries = 2
                result = None
                for attempt in range(max_retries + 1):
                    result = _execute_node(
                        self, node_def, goal, context_from_upstream,
                        stream_callback, node_results, 0
                    )
                    
                    if result.get("success"):
                        break  # Success, no retry needed
                    
                    if attempt < max_retries and result.get("error"):
                        if stream_callback:
                            stream_callback({
                                "type": "pipeline_node_retry",
                                "node_id": node_id,
                                "node_label": node_def.get("label", node_id),
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "error": result.get("error"),
                                "message": f"🔄 Retry {attempt + 1}/{max_retries} per '{node_def.get('label', node_id)}'"
                            })
                        # Give feedback to AI about the failure
                        context_from_upstream.append(result)
                    else:
                        break  # No retry on last attempt or no error
                
                node_results[node_id] = result
                if result and result.get("actions_log"):
                    all_actions_log.extend(result["actions_log"])
            
            # Update pipeline status
            completed = sum(1 for nid in execution_order[:idx + 1] if nid in node_results)
            failed = sum(1 for nid in execution_order[:idx + 1] 
                        if nid in node_results and not node_results[nid].get("success"))
            pipeline_status["nodes_completed"] = completed
            pipeline_status["nodes_failed"] = failed
            
            # --- CHECKPOINT after each node ---
            pipeline_status["node_results"] = {k: v for k, v in node_results.items()}
            _save_checkpoint(pipeline_id, pipeline_status)
            
            if stream_callback:
                stream_callback({
                    "type": "pipeline_progress",
                    "completed": completed,
                    "total": len(nodes),
                    "failed": failed,
                    "skipped": len(skipped_nodes),
                    "current_node": node_id,
                    "percent": int((idx + 1) / len(nodes) * 100)
                })
        
        # All nodes executed — compute final report
        pipeline_status["status"] = "completed"
        pipeline_status["skipped_nodes"] = skipped_nodes
        total_success = sum(1 for a in all_actions_log if a.get("success"))
        total_fail = sum(1 for a in all_actions_log if not a.get("success"))
        files_created = [a for a in all_actions_log if a.get("type") == "create_file" and a.get("success")]
        tests_run = [a for a in all_actions_log if a.get("type") == "run_test"]
        tests_passed = sum(1 for a in tests_run if a.get("success"))
        
        report = {
            "pipeline_id": pipeline_id,
            "pipeline_path": pipeline_path,
            "goal": goal,
            "strategy": "dag_topological",
            "total_nodes": len(nodes),
            "nodes_completed": pipeline_status["nodes_completed"],
            "nodes_failed": pipeline_status["nodes_failed"],
            "nodes_skipped": len(skipped_nodes),
            "skipped_nodes": skipped_nodes,
            "total_actions": len(all_actions_log),
            "successful_actions": total_success,
            "failed_actions": total_fail,
            "files_created": len(files_created),
            "tests_run": len(tests_run),
            "tests_passed": tests_passed,
            "feedback_cycles": feedback_cycles,
            "node_results": node_results,
            "execution_order": execution_order,
            "parallel_levels": parallel_levels,
            "agents_used": list(set(r.get("agent_id") for r in node_results.values() if isinstance(r, dict) and r.get("agent_id"))),
            "elapsed_minutes": round((datetime.datetime.now() - started_at).total_seconds() / 60, 1),
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "completed"
        }
        
        pipeline_status["report"] = report
        _save_checkpoint(pipeline_id, pipeline_status)
        
        if stream_callback:
            stream_callback({
                "type": "pipeline_done",
                "report": report,
                "message": f"🎯 Pipeline completata: {report['nodes_completed']}/{len(nodes)} nodi, "
                           f"{total_success}/{len(all_actions_log)} azioni, {len(files_created)} file, "
                           f"{feedback_cycles} cicli di feedback"
            })
        
        return {"success": True, "report": report, "actions_log": all_actions_log}
    
    except Exception as e:
        pipeline_status["status"] = "error"
        pipeline_status["error"] = str(e)
        pipeline_status["skipped_nodes"] = skipped_nodes
        _save_checkpoint(pipeline_id, pipeline_status)
        
        if stream_callback:
            stream_callback({
                "type": "pipeline_error",
                "error": str(e),
                "message": f"❌ Pipeline interrotta: {str(e)}"
            })
        
        return {"success": False, "error": str(e), "report": {
            "pipeline_id": pipeline_id,
            "goal": goal,
            "nodes_completed": pipeline_status["nodes_completed"],
            "nodes_failed": pipeline_status["nodes_failed"],
            "nodes_skipped": len(skipped_nodes),
            "error": str(e),
            "status": "error"
        }}
# ==============================================================================
# PIPELINE STATUS & STOP
# ==============================================================================

def get_pipeline_status(pipeline_id: str = None) -> dict:
    """Get status of active or completed pipelines.
    
    Checks both in-memory and disk checkpoints for completed/stopped pipelines.
    """
    if pipeline_id:
        status = _active_pipelines.get(pipeline_id)
        if not status:
            # Try loading from checkpoint file (for completed pipelines)
            status = _load_checkpoints().get(pipeline_id)
        if status:
            return {"success": True, "pipeline": status}
        return {"success": False, "error": f"Pipeline '{pipeline_id}' non trovata"}
    
    # Merge in-memory + checkpoint pipelines, sorted by start time
    result = list(_active_pipelines.values())
    checkpoints = _load_checkpoints()
    for pid, data in checkpoints.items():
        if pid not in _active_pipelines:
            result.append(data)
    return {
        "success": True,
        "pipelines": sorted(result, key=lambda x: x.get("started_at", ""), reverse=True)
    }


def stop_pipeline(pipeline_id: str) -> dict:
    """Stop a running pipeline and save final checkpoint."""
    if pipeline_id in _active_pipelines:
        _active_pipelines[pipeline_id]["status"] = "stopped"
        _save_checkpoint(pipeline_id, _active_pipelines[pipeline_id])
        return {"success": True, "message": f"Pipeline '{pipeline_id}' fermata"}
    return {"success": False, "error": f"Pipeline '{pipeline_id}' non trovata"}


# ==============================================================================
# API HANDLERS
# ==============================================================================

def handle_pipeline_start(self):
    """POST /api/chat/pipeline/start — Start a pipeline execution with SSE streaming."""
    try:
        req = self.read_json_body()
        
        # SSE streaming
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        def _sse(event):
            try:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        
        try:
            result = run_pipeline(self, req, stream_callback=_sse)
            if isinstance(result, tuple) and len(result) == 2:
                _sse({"type": "error", "error": result[0].get("error", "Errore sconosciuto")})
        except Exception as e:
            _sse({"type": "error", "error": str(e)})
        
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except Exception:
            pass


def handle_pipeline_status(self):
    """GET /api/chat/pipeline/status — Get pipeline execution status."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        pipeline_id = query.get("id", [None])[0]
        result = get_pipeline_status(pipeline_id)
        return self.send_json_response(result)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_pipeline_stop(self):
    """POST /api/chat/pipeline/stop — Stop a running pipeline."""
    try:
        req = self.read_json_body()
        pipeline_id = req.get("id", "")
        result = stop_pipeline(pipeline_id)
        if result.get("success"):
            return self.send_json_response(result)
        return self.send_json_response(result, 404)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)
