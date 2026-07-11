"""Agent Orchestrator for Sigma Studio — Multi-Agent Collaboration System.
Permette a più agenti specializzati di collaborare su un obiettivo comune,
scomponendolo in sotto-task e assegnando ciascuno all'agente più adatto.
Supporta esecuzione parallela con ThreadPoolExecutor e sintesi finale."""
import os
import json
import datetime
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.ai_providers import load_ai_config, resolve_provider_config, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.agent_registry import get_all_agents, get_specialized_agent, increment_usage, SIGMA_ARCHITECT_ID
from core.agent_memory import save_session_memory, get_memory_context
from core.chat_handler import _get_manifesto_content, _get_time_context, _build_filesystem_context, _extract_json_from_response, _collect_context_files


MAX_PARALLEL_WORKERS = 5


def _call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, request_timeout):
    route_provider = provider
    if route_provider in ('deepseek', 'openai'):
        route_provider = 'api'
    elif route_provider not in ('ollama', 'api', 'anthropic'):
        route_provider = 'api'
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


def _load_agent_config(ai_cfg, model_override, agent_id=None):
    provider = ai_cfg.get("active_provider", "ollama")
    providers_config = ai_cfg.get("providers", {})
    active_prov_cfg = providers_config.get(provider, {})
    model = model_override or ai_cfg.get("model", "llama3.2")
    if agent_id:
        from core.agent_registry import get_agent
        agent = get_agent(agent_id)
        if agent and agent.get("models"):
            model = agent["models"][0]
    endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
    api_url = active_prov_cfg.get("api_url", "")
    api_key = active_prov_cfg.get("api_key", "")
    temperature = active_prov_cfg.get("temperature", 0.7)
    max_tokens = active_prov_cfg.get("max_tokens", 4096)
    top_p = active_prov_cfg.get("top_p", 0.9)
    request_timeout = active_prov_cfg.get("timeout", 300)
    # Auto-detect provider from model name prefix with default API URLs
    if model.startswith('deepseek'):
        provider = 'deepseek'
        if not api_url: api_url = 'https://api.deepseek.com/v1/chat/completions'
    elif model.startswith(('gpt-', 'o1', 'o3')):
        provider = 'openai'
        if not api_url: api_url = 'https://api.openai.com/v1/chat/completions'
    elif model.startswith('claude'):
        provider = 'anthropic'
        if not api_url: api_url = 'https://api.anthropic.com/v1/messages'
    
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


AGENT_COLORS = {
    "sigma_architect": {"bg": "#7c5bf0", "color": "#ffffff", "icon": "🏗️", "short": "Arch"},
    "math1": {"bg": "#3fb950", "color": "#ffffff", "icon": "∑", "short": "Math"},
    "code_architect": {"bg": "#00d2ff", "color": "#0e1016", "icon": "⚙️", "short": "Code"},
    "default": {"bg": "#8b8fa3", "color": "#0e1016", "icon": "🤖", "short": "AI"},
}


def get_agent_color(agent_id):
    return AGENT_COLORS.get(agent_id, AGENT_COLORS["default"])


def _get_available_agents_for_goal(goal):
    agents = get_all_agents()
    return [a for a in agents if a.get("status") == "active"]


# ==============================================================================
# PHASE 1 — DECOMPOSE
# ==============================================================================

def _decompose_goal(goal, agents_list, ai_cfg, model_override):
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        _load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
    agents_json = json.dumps([{
        "id": a.get("id"), "name": a.get("name"),
        "specialization": a.get("specialization"), "capabilities": a.get("capabilities"),
    } for a in agents_list], indent=2)
    system_prompt = f"""Sei un orchestratore di agenti AI specializzati.
Il tuo compito è analizzare un goal e scomporlo in sotto-task, assegnando
ciascun sotto-task all'agente più adatto in base alla sua specializzazione.
Agenti disponibili:
{agents_json}
## REGOLE
1. Massimo 5 sotto-task
2. Ogni sotto-task DEVE essere assegnato a un agente esistente
3. Usa descrizioni chiare e specifiche. Parla SEMPRE in italiano.
4. Se un task è troppo generico, assegnalo all'agente più versatile
## FORMATO RISPOSTA — SOLO JSON
{{"analysis": "...", "subtasks": [
  {{"agent_id": "sigma_architect", "task": "Titolo task", "description": "Cosa fare...", "actions_hint": ["create_file", "run_test"]}},
  ...
]}}"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analizza e scomponi il seguente goal:\n\n{goal}\n\nAssegna ogni sotto-task all'agente più adatto."}
    ]
    main_model = ai_cfg.get("active_model", ai_cfg.get("model", "deepseek-v4-flash"))
    for a in agents_list:
        if a.get("id") == SIGMA_ARCHITECT_ID and a.get("models"):
            main_model = a["models"][0]
            break
    response, thinking, error = _call_ai_model(messages, ai_cfg, main_model,
        provider, endpoint, api_url, api_key, 0.4, max_tokens * 4, top_p, timeout)
    if error or not response:
        return _generate_fallback_tasks(agents_list, goal), None
    json_match = _extract_json_from_response(response)
    if not json_match:
        return _generate_fallback_tasks(agents_list, goal), None
    try:
        parsed = json.loads(json_match.group())
        subtasks = parsed.get("subtasks", [])
        validated = []
        for st in subtasks:
            agent_id = st.get("agent_id", SIGMA_ARCHITECT_ID)
            agent = next((a for a in agents_list if a.get("id") == agent_id), None)
            if not agent:
                agent = next((a for a in agents_list if a.get("id") == SIGMA_ARCHITECT_ID), None)
                agent_id = SIGMA_ARCHITECT_ID
            validated.append({
                "agent_id": agent_id,
                "agent_name": agent.get("name", "Sigma Agent") if agent else "Sigma Agent",
                "task": st.get("task", "Sotto-task"),
                "description": st.get("description", ""),
                "actions_hint": st.get("actions_hint", ["create_file"]),
                "status": "pending", "result": None, "error": None,
            })
        if len(validated) < 2:
            return _generate_fallback_tasks(agents_list, goal), None
        return validated, None
    except json.JSONDecodeError:
        return _generate_fallback_tasks(agents_list, goal), None


def _generate_fallback_tasks(agents_list, goal):
    tasks = []
    task_templates = {
        "sigma_architect": {"task": "Coordinare l'intera pipeline: leggere tutti i file esistenti, eseguire test, produrre un report riepilogativo", "description": f"Leggi lo stato completo ({goal[:100]}). Esegui TUTTI i test in test/ e controlla i risultati. Crea il file docs/report_completo.md con: riepilogo di ogni file di teoria, risultati test, struttura moduli, metriche. Usa update_task per aggiornare lo stato.", "hint": ["read_file", "run_test", "create_file", "edit_file", "update_task"]},
        "math1": {"task": "Ricerca e analisi matematica: leggere, verificare e documentare tutta la teoria matematica esistente", "description": f"Leggi tutti i file in teoria/ e docs/. Verifica la correttezza logica delle dimostrazioni. Se mancano dimostrazioni formali, crea nuovi file teoria/NN_teorema.md. Esegui i test in test/ per validazione. Crea almeno 1-2 nuovi file di teoria se necessario.", "hint": ["read_file", "create_file", "run_test", "edit_file", "update_task"]},
        "code_architect": {"task": "Sviluppo e refactoring: analizzare il codice, eseguire test, correggere errori, ottimizzare", "description": f"Leggi tutti i file .py in test/. Esegui ogni test. Se ci sono errori, correggi i file. Crea nuovi test per coprire casi mancanti. Documenta le modifiche. Obiettivo: tutti i test PASSANO.", "hint": ["read_file", "run_test", "create_file", "edit_file", "update_task"]},
        "math-collatz": {"task": "Analisi matematica e dimostrazioni formali", "description": "Studia la teoria esistente. Crea file di teoria con dimostrazioni formali, analisi strutturale e teoremi. Usa LaTeX per formule. Almeno 2 file di teoria.", "hint": ["read_file", "create_file", "run_test", "update_task"]},
        "test-engineer": {"task": "Test e validazione: scrivere, eseguire e correggere test Python", "description": f"Leggi i test esistenti. Esegui tutti i test. Se falliscono, correggi. Crea nuovi test per coprire i casi mancanti. Documenta risultati.", "hint": ["read_file", "run_test", "create_file", "edit_file", "update_task"]},
        "viz-designer": {"task": "Visualizzazioni: creare grafici D3.js interattivi per le transizioni e le classi mod 6", "description": f"Leggi la teoria in teoria/ per capire le transizioni. Crea file HTML viz/NN_nome.html usando D3.js via CDN. Crea: grafo delle transizioni (force-directed graph) e heatmap delle frequenze. Tema scuro, legenda colori, interattivo.", "hint": ["read_file", "create_file", "update_task"]},
        "proof-reviewer": {"task": "Revisione critica: verificare TUTTI i file prodotti e produrre report di validazione finale", "description": f"Leggi TUTTI i file in teoria/, test/, viz/, docs/. Verifica la correttezza logica di ogni affermazione. Cerca controesempi. Crea docs/revisione_finale.md con: errori trovati, validazioni positive, raccomandazioni. Aggiorna il task.", "hint": ["read_file", "create_file", "edit_file", "update_task"]},
    }
    for agent in agents_list:
        if agent.get("status") != "active":
            continue
        aid = agent.get("id", "")
        template = task_templates.get(aid, {"task": f"Contributo al goal", "description": goal[:200], "hint": ["create_file"]})
        tasks.append({"agent_id": aid, "agent_name": agent.get("name", "Sigma Agent"), "task": template["task"], "description": template["description"], "actions_hint": template["hint"], "status": "pending", "result": None, "error": None})
    return tasks


# ==============================================================================
# PHASE 2 — EXECUTE SUBTASK
# ==============================================================================

def _execute_subtask(self, subtask, goal, stream_callback):
    agent_id = subtask.get("agent_id", SIGMA_ARCHITECT_ID)
    agent_name = subtask.get("agent_name", "Agent")
    task = subtask.get("task", "")
    description = subtask.get("description", "")
    if stream_callback:
        stream_callback({"type": "agent_task_start", "agent_id": agent_id, "agent_name": agent_name, "task": task, "description": description, "message": f"▶️ {agent_name} sta lavorando su: {task}"})
        stream_callback({"type": "agent_task_thinking", "agent_id": agent_id, "agent_name": agent_name, "task": task, "message": f"🧠 {agent_name} sta analizzando..."})
    from core.agent_registry import get_agent
    agent = get_agent(agent_id)
    agent_model = agent["models"][0] if agent and agent.get("models") else None
    ai_cfg = load_ai_config()
    model = agent_model or ai_cfg.get("model", "llama3.2")
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = _load_agent_config(ai_cfg, model, agent_id)
    manifesto_path = agent.get("manifesto", "") if agent else ""
    system_prompt = _get_manifesto_content(manifesto_path)
    if not system_prompt.strip():
        system_prompt = f"Sei {agent_name}, un assistente AI specializzato. Rispondi in italiano."
    time_ctx = _get_time_context()
    fs_context = _build_filesystem_context()
    memory_context = get_memory_context(agent_id) if agent_id else ""
    action_prompt = f"""\n## OBIETTIVO GENERALE\n{goal}\n\n## TASK ASSEGNATO\n{task}\n{description}\n\n## REGOLE OBBLIGATORIE\n- Rispondi SOLO con JSON: {{"response": "...", "actions": [...]}}\n- Usa tipi di azione validi: create_file, edit_file, run_test, read_file, update_task\n- Struttura corretta: data/<topic>/<NN_modulo>/<sezione>/<file>\n- Sezioni permesse: teoria/, test/, viz/, docs/, whitepapers/\n- Alla fine usa update_task se appropriato\n"""
    full_system = f"{system_prompt}\n\n{time_ctx}\n\n{action_prompt}"
    if fs_context: full_system += f"\n\nStruttura progetto:\n{fs_context[:2000]}"
    if memory_context: full_system += f"\n\n{memory_context}"
    messages = [{"role": "system", "content": full_system}, {"role": "user", "content": f"Esegui il task: {task}\n\n{description}"}]
    max_iterations = 3
    all_actions_log = []
    for iteration in range(max_iterations):
        response, thinking, error = _call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, 0.3, max_tokens * 2, top_p, timeout)
        if error:
            if stream_callback: stream_callback({"type": "agent_task_error", "agent_id": agent_id, "iteration": iteration + 1, "error": error})
            return False, all_actions_log, error
        if not response:
            return False, all_actions_log, "L'agente non ha prodotto una risposta valida (risposta vuota)"
        json_match = _extract_json_from_response(response)
        if not json_match:
            return False, all_actions_log, f"L'agente non ha risposto con JSON valido. Risposta: {response[:200]}..."
        try:
            parsed = json.loads(json_match.group())
            ai_response = parsed.get("response", "")
            actions = parsed.get("actions", [])
            is_done = parsed.get("done", False)
            if not actions:
                return False, all_actions_log, f"L'agente ha risposto ma senza azioni da eseguire. Response: {ai_response[:150]}..."
            iteration_log = execute_ai_actions(self, actions, agent_name)
            all_actions_log.extend(iteration_log)
            success_count = sum(1 for a in iteration_log if a.get("success"))
            fail_count = sum(1 for a in iteration_log if not a.get("success"))
            full_response = ""
            if thinking and thinking.strip(): full_response += f"🧠 **Thinking:**\n{thinking.strip()[:2000]}\n\n"
            full_response += f"💬 **Risposta:**\n{(response or ai_response or '')[:2000]}"
            if stream_callback:
                stream_callback({"type": "agent_task_iteration", "agent_id": agent_id, "iteration": iteration + 1, "max_iterations": max_iterations, "success_count": success_count, "fail_count": fail_count, "actions_log": iteration_log, "ai_response": ai_response[:1000] if ai_response else "", "full_response": full_response[:3000] if full_response else ""})
            if iteration >= 1 and is_done: break
            if iteration >= 1 and fail_count == 0:
                if is_done: break
                if iteration < max_iterations - 1: continue
            details = "\n".join(f"  {'✅' if a.get('success') else '❌'} {a.get('type','?')}: {a.get('message', a.get('error',''))}" for a in iteration_log)
            messages.append({"role": "system", "content": f"📋 Iterazione {iteration + 1}: {success_count}/{len(iteration_log)} azioni riuscite\n\n{details}"})
        except json.JSONDecodeError: break
    if agent_id:
        total_success = sum(1 for a in all_actions_log if a.get("success"))
        total_fail = sum(1 for a in all_actions_log if not a.get("success"))
        try:
            save_session_memory(agent_id, {"goal": f"[Orchestrator] {task[:100]}", "actions_performed": all_actions_log, "success_count": total_success, "fail_count": total_fail, "learning": "", "summary": f"Task orchestrato: {total_success}✅/{total_fail}❌"})
            increment_usage(agent_id, success=total_fail == 0)
        except Exception: pass
    total_success = sum(1 for a in all_actions_log if a.get("success"))
    return total_success > 0 or len(all_actions_log) == 0, all_actions_log, None


# ==============================================================================
# PHASE 3 — PARALLEL EXECUTION
# ==============================================================================

def _execute_subtask_wrapper(args):
    self, subtask, goal, stream_callback = args
    try:
        return subtask["agent_id"], *_execute_subtask(self, subtask, goal, stream_callback)
    except Exception as e:
        return subtask["agent_id"], False, [], str(e)


def _execute_parallel_subtasks(self, subtasks, goal, stream_callback):
    all_actions_log = []
    subtask_results = []
    args_list = [(self, st, goal, stream_callback) for st in subtasks]
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_WORKERS, len(subtasks))) as executor:
        future_map = {executor.submit(_execute_subtask_wrapper, args): args[1] for args in args_list}
        for future in as_completed(future_map):
            subtask = future_map[future]
            try:
                agent_id, success, actions_log, error = future.result()
            except Exception as e:
                agent_id = subtask.get("agent_id", "unknown")
                success, actions_log, error = False, [], str(e)
            if actions_log: all_actions_log.extend(actions_log)
            subtask["status"] = "done" if success else "failed"
            subtask["result"] = {"actions_count": len(actions_log or [])}
            subtask["error"] = error
            subtask_results.append(subtask)
            if stream_callback:
                stream_callback({"type": "orchestrate_subtask_complete", "subtask_idx": 0, "total_subtasks": len(subtasks), "agent_id": agent_id, "success": success, "error": error, "message": f"{'✅' if success else '❌'} {subtask.get('agent_name', agent_id)}: {subtask.get('task', '')}"})
    return all_actions_log, subtask_results


# ==============================================================================
# PHASE 4 — SYNTHESIS
# ==============================================================================

def _synthesize_results(self, goal, subtask_results, all_actions_log, stream_callback):
    total_actions = len(all_actions_log)
    total_success = sum(1 for a in all_actions_log if a.get("success"))
    total_fail = sum(1 for a in all_actions_log if not a.get("success"))
    files_created = [a for a in all_actions_log if a.get("type") == "create_file" and a.get("success")]
    tests_run = [a for a in all_actions_log if a.get("type") == "run_test"]
    tests_passed = sum(1 for a in tests_run if a.get("success"))
    synthesis_parts = []
    for sr in subtask_results:
        agent_name = sr.get("agent_name", "Agent")
        task = sr.get("task", "")
        status = sr.get("status", "unknown")
        actions = sr.get("result", {}).get("actions_count", 0)
        synthesis_parts.append(f"{agent_name}: {task} - {'✅' if status == 'done' else '❌'} ({actions} azioni)")
    report = {
        "goal": goal, "total_subtasks": len(subtask_results),
        "subtasks_completed": sum(1 for s in subtask_results if s.get("status") == "done"),
        "subtasks_failed": sum(1 for s in subtask_results if s.get("status") == "failed"),
        "total_actions": total_actions, "successful_actions": total_success, "failed_actions": total_fail,
        "files_created": len(files_created), "tests_run": len(tests_run), "tests_passed": tests_passed,
        "subtasks": subtask_results,
        "agents_used": list(set(s.get("agent_id") for s in subtask_results if s.get("agent_id"))),
        "synthesis": "\n".join(synthesis_parts), "timestamp": datetime.datetime.now().isoformat()
    }
    if stream_callback:
        stream_callback({"type": "orchestrate_done", "report": report,
            "message": f"🎯 Orchestrazione completata: {report['subtasks_completed']}/{len(subtask_results)} task, {total_success}/{total_actions} azioni, {len(files_created)} file creati"})
    return {"success": True, "report": report, "actions_log": all_actions_log}


# ==============================================================================
# PHASE 5 — MAIN ORCHESTRATOR
# ==============================================================================

def orchestrate(self, req, stream_callback=None):
    goal = req.get("message", "").strip()
    if not goal: return {"error": "Goal vuoto"}, 400
    strategy = req.get("strategy", "parallel")
    model_override = req.get("model", "")
    ai_cfg = load_ai_config()
    if stream_callback:
        stream_callback({"type": "orchestrate_start", "goal": goal, "strategy": strategy, "message": f"🎯 Avvio orchestrazione per: {goal[:100]}..."})
    if stream_callback:
        stream_callback({"type": "orchestrate_phase", "phase": "decompose", "message": "📋 Scomposizione del goal in sotto-task..."})
    agents = _get_available_agents_for_goal(goal)
    subtasks, error = _decompose_goal(goal, agents, ai_cfg, model_override)
    if error:
        if stream_callback: stream_callback({"type": "orchestrate_error", "error": error})
        return {"error": error}, 500
    if stream_callback:
        stream_callback({"type": "orchestrate_plan", "total_subtasks": len(subtasks), "subtasks": [{"agent_id": s["agent_id"], "agent_name": s["agent_name"], "task": s["task"]} for s in subtasks], "message": f"✅ Piano creato: {len(subtasks)} sotto-task da {len(set(s['agent_id'] for s in subtasks))} agenti"})
    if stream_callback:
        stream_callback({"type": "orchestrate_phase", "phase": "execute", "message": f"⚡ Esecuzione {'parallela' if strategy == 'parallel' else 'sequenziale'} di {len(subtasks)} sotto-task..."})
    if strategy == "parallel":
        all_actions_log, subtask_results = _execute_parallel_subtasks(self, subtasks, goal, stream_callback)
    else:
        all_actions_log = []
        subtask_results = []
        for idx, subtask in enumerate(subtasks):
            if stream_callback:
                stream_callback({"type": "orchestrate_subtask_start", "subtask_idx": idx + 1, "total_subtasks": len(subtasks), "agent_id": subtask["agent_id"], "agent_name": subtask["agent_name"], "task": subtask["task"]})
            success, actions_log, error = _execute_subtask(self, subtask, goal, stream_callback)
            all_actions_log.extend(actions_log or [])
            subtask["status"] = "done" if success else "failed"
            subtask["result"] = {"actions_count": len(actions_log or [])}
            subtask["error"] = error
            subtask_results.append(subtask)
            if stream_callback:
                stream_callback({"type": "orchestrate_subtask_complete", "subtask_idx": idx + 1, "total_subtasks": len(subtasks), "agent_id": subtask["agent_id"], "success": success, "error": error, "message": f"{'✅' if success else '❌'} {subtask['agent_name']}: {subtask['task']}"})
    return _synthesize_results(self, goal, subtask_results, all_actions_log, stream_callback)


# ==============================================================================
# API HANDLER
# ==============================================================================

def handle_chat_orchestrate(self):
    try:
        req = self.read_json_body()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        _sse_lock = threading.Lock()
        def _sse(event):
            with _sse_lock:
                try:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                except Exception: pass
        try:
            result = orchestrate(self, req, stream_callback=_sse)
            if isinstance(result, tuple) and len(result) == 2:
                _sse({"type": "error", "error": result[0].get("error", "Errore sconosciuto")})
        except Exception as e:
            _sse({"type": "error", "error": str(e)})
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    except Exception as e:
        try: self.send_json_response({"error": str(e)}, 500)
        except Exception: pass


# ==============================================================================
# RESEARCH DECOMPOSE + NEXT STEPS (Research Lab v2)
# ==============================================================================

def _fallback_objectives(session_id, agents_list, goal):
    """Generate generic micro-objectives when AI decomposition fails. Used as last resort."""
    from core.research_sessions import add_micro_objective, get_session
    
    session = get_session(session_id)
    session_name = (session.get("name") or goal[:40]) if session else goal[:40]
    
    # Dynamic, topic-agnostic objectives based on the goal
    objectives = [
        {"title": f"Analisi: {goal[:60]}", "description": f"Analizza approfonditamente l'obiettivo: {goal[:200]}. Leggi i file esistenti e crea un documento di analisi iniziale.", "assigned_to": "sigma_architect", "actions_hint": ["read_file", "create_file"], "completion_criteria": "Analisi iniziale documentata con next steps"},
        {"title": f"Teoria e documentazione: {goal[:40]}", "description": f"Sulla base dell'obiettivo '{goal[:100]}', crea file di teoria con definizioni, spiegazioni, esempi. Usa data/ come root directory.", "assigned_to": "math1", "actions_hint": ["create_file"], "completion_criteria": "File di teoria creati con contenuti sostanziosi"},
        {"title": f"Validazione: {goal[:40]}", "description": f"Verifica e testa i risultati dell'obiettivo '{goal[:100]}'. Crea test Python se applicabile, esegui validazioni.", "assigned_to": "test-engineer", "actions_hint": ["run_test", "create_file"], "completion_criteria": "Validazione completata con risultati"},
        {"title": f"Revisione: {goal[:40]}", "description": f"Verifica tutto il lavoro prodotto per '{goal[:100]}'. Controlla completezza, coerenza e correttezza.", "assigned_to": "proof-reviewer", "actions_hint": ["read_file", "create_file"], "completion_criteria": "Report di revisione completato"},
    ]
    
    added = []
    for obj in objectives:
        result = add_micro_objective(session_id, obj)
        if result:
            added.append(result)
    
    return {"success": True, "objectives": added, "analysis": f"Obiettivi generici generati (coordinatore AI non disponibile): {len(added)} task", "count": len(added)}


def _execute_default_action(self, session_id, obj, goal, _sse):
    """When AI fails to produce actions, execute a default file creation."""
    import datetime
    from core.research_sessions import add_actions_log
    
    # Extract topic from session goal — use session name if available
    from core.research_sessions import get_session
    session = get_session(session_id)
    session_name = (session.get("name") or "").lower() if session else ""
    topic = None
    
    # Priority: goal keywords > session name > "generale"
    # NOTE: Do NOT use random words from session name as topic directory
    goal_lower = goal.lower()
    if "analisi_1" in goal_lower or "analisi 1" in goal_lower or "analisi_1" in session_name:
        topic = "analisi_1"
    if not topic and ("analisi_2" in goal.lower() or "analisi 2" in goal.lower()):
        topic = "analisi_2"
    if not topic and ("fisica" in goal.lower()):
        topic = "fisica"
    if not topic and ("informatica" in goal.lower() or "codice" in goal.lower()):
        topic = "informatica"
    if not topic:
        topic = "generale"
    
    module_path = f"data/{topic}/01_base"
    os.makedirs(f"{module_path}/teoria", exist_ok=True)
    
    filename = f"analisi_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = f"{module_path}/teoria/{filename}"
    
    content = f"""# {obj.get('title', 'Analisi')}

**Goal originale:** {goal[:300]}

**Obiettivo specifico:** {obj.get('title', '')}
{obj.get('description', '')}

---

## Analisi automatica
Questa analisi è stata generata automaticamente dal sistema quando l'AI non ha prodotto azioni specifiche.

### Contesto
Il sistema ha tentato di chiamare l'AI per eseguire un'analisi completa, ma la risposta non conteneva azioni eseguibili. Questo file viene creato come punto di partenza.

### Azioni suggerite
1. Verificare i file esistenti nella directory `data/{topic}/`
2. Completare l'analisi con contenuti specifici
3. Eseguire test di validazione

---
*Generato il {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    
    actions = [{"type": "create_file", "path": filepath, "content": content}]
    from core.task_handler import execute_ai_actions
    result = execute_ai_actions(self, actions, "Sistema")
    print(f"[RESEARCH_START] Default action: created {filepath}", flush=True)
    _sse({"type": "agent_actions", "agent_id": "sistema",
          "actions_log": result, "success_count": 1, "fail_count": 0,
          "message": f"📄 Creato file predefinito: {filepath}"})
    add_actions_log(session_id, result)
    return result


def decompose_goal_to_micro_objectives(goal, agents_list, ai_cfg, model_override, session_id):
    """Decompose a research goal into micro-objectives using the coordinator agent.
    The coordinator is the BRAIN — it must analyze and delegate with precision."""
    from core.research_sessions import get_session, add_micro_objective, save_session
    
    session = get_session(session_id)
    session_name = (session.get("name") or goal[:40]) if session else goal[:40]
    
    # Detect topic for path generation
    topic = "generale"
    session_lower = session_name.lower()
    goal_lower = goal.lower()
    if "analisi_1" in session_lower or "analisi 1" in goal_lower or "analisi matematica 1" in goal_lower:
        topic = "analisi_1"
    elif "analisi_2" in session_lower or "analisi 2" in goal_lower:
        topic = "analisi_2"
    elif "fisica" in goal_lower:
        topic = "fisica"
    elif "informatica" in goal_lower or "codice" in goal_lower:
        topic = "informatica"
    
    base_path = f"data/{topic}/01_base"
    
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        _load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
    
    agents_json = json.dumps([{
        "id": a.get("id", a.get("agent_id", "")),
        "name": a.get("name", a.get("agent_name", "")),
        "specialization": a.get("specialization", "general"),
        "capabilities": a.get("capabilities", []),
    } for a in agents_list], indent=2)

    # Build existing filesystem context
    fs_context = ""
    if os.path.exists(f"data/{topic}"):
        try:
            import subprocess
            result = subprocess.run(["dir", f"data\\{topic}", "/s", "/b"], capture_output=True, text=True, shell=True, timeout=5)
            files = result.stdout.strip().split("\n")
            fs_context = "File già esistenti:\n" + "\n".join(f"  {f}" for f in files[:20])
        except: pass
    
    system_prompt = f"""Sei il COORDINATORE PRINCIPALE di un team di agenti AI specializzati.
Il tuo compito è analizzare l'obiettivo dell'utente e scomporlo in micro-task PRECISI e DETTAGLIATI.

## TEAM DISPONIBILE
{agents_json}

## TOPIC E STRUTTURA
Topic: {topic}
Directory base: {base_path}/
Sottodirectory: teoria/, test/, docs/, viz/
{fs_context}

## REGOLE FONDAMENTALI
1. Sei il CAPO — devi pensare TU a quali file servono, cosa devono contenere, chi li crea
2. Ogni task DEVE avere un path file ESATTO (es. {base_path}/teoria/01_limiti.md)
3. Ogni task DEVE specificare ESATTAMENTE cosa scrivere nel file (contenuti, formule, esempi)
4. Assegna task agli agenti in base alla loro specializzazione
5. Bilancia: teoria (math1/code_architect), test (test-engineer), revisione (proof-reviewer)
6. Produci 3-7 micro-obiettivi. Se il topic è UNKNOWN, fanne 3-4 generici
7. Il criterio di completamento deve essere verificabile (file creato, test passato, etc.)

## FORMATO RISPOSTA — SOLO JSON
{{
  "analysis": "Analisi dettagliata del goal (2-3 frasi)",
  "micro_objectives": [
    {{
      "title": "Titolo sintetico del task",
      "description": "ISTRUZIONI DETTAGLIATE: path file esatto, contenuti da scrivere, formule da includere, esempi da fare. Sii PRECISO.",
      "assigned_to": "agent_id",
      "actions_hint": ["create_file"],
      "completion_criteria": "Criterio verificabile (es: 'File {base_path}/teoria/01_limiti.md creato con definizione, teoremi e 5 esempi')"
    }}
  ]
}}

ESEMPIO per analisi_1:
{{"title": "Teoria dei limiti", "description": "Crea {base_path}/teoria/01_limiti.md con: definizione epsilon-delta di limite finito, limite infinito, teorema unicità, permanenza segno, confronto, limiti notevoli (sin x/x, (1+1/n)^n), forme indeterminate, 5 esempi svolti passo-passo in LaTeX", "assigned_to": "math1", "actions_hint": ["create_file"], "completion_criteria": "File {base_path}/teoria/01_limiti.md creato con tutti i contenuti richiesti"}}"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"## OBIETTIVO UTENTE\n{session_name}\n\n{goal}\n\nAnalizza l'obiettivo e produci il piano di lavoro dettagliato con micro-obiettivi."}
    ]
    
    model = model_override or ai_cfg.get("model", "deepseek-v4-flash")
    print(f"[DECOMPOSE] Calling coordinator with model={model}, provider={provider}", flush=True)
    response, thinking, error = _call_ai_model(messages, ai_cfg, model,
        provider, endpoint, api_url, api_key, 0.4, max_tokens * 3, top_p, timeout)
    
    if not session:
        return {"success": False, "error": "Sessione non trovata"}
    
    if error or not response:
        print(f"[DECOMPOSE] Coordinator error: {error}, using fallback", flush=True)
        return _fallback_objectives(session_id, agents_list, goal)
    
    print(f"[DECOMPOSE] Coordinator response: {len(response)} chars", flush=True)
    json_match = _extract_json_from_response(response)
    if not json_match:
        print(f"[DECOMPOSE] No JSON in response, using fallback. Raw: {response[:200]}", flush=True)
        return _fallback_objectives(session_id, agents_list, goal)
    
    try:
        parsed = json.loads(json_match.group())
        objectives = parsed.get("micro_objectives", [])
        analysis = parsed.get("analysis", "")
        print(f"[DECOMPOSE] Coordinator produced {len(objectives)} objectives. Analysis: {analysis[:100]}", flush=True)
        added = []
        for obj in objectives:
            result = add_micro_objective(session_id, obj)
            if result:
                added.append(result)
        if len(added) == 0:
            return _fallback_objectives(session_id, agents_list, goal)
        return {"success": True, "objectives": added, "analysis": analysis, "count": len(added)}
    except json.JSONDecodeError:
        print(f"[DECOMPOSE] JSON decode error, using fallback", flush=True)
        return _fallback_objectives(session_id, agents_list, goal)


def generate_next_steps(session_id, ai_cfg, model_override):
    """After research completion, generate suggested next steps."""
    from core.research_sessions import get_session, set_next_steps
    
    session = get_session(session_id)
    if not session:
        return {"success": False, "error": "Sessione non trovata"}
    
    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        _load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
    
    objectives_summary = "\n".join(
        f"- {o['title']}: {o.get('status', '?')} — {o.get('result', o.get('description', ''))[:200]}"
        for o in session.get("micro_objectives", [])
    )
    
    system_prompt = f"""Sei un coordinatore di ricerca. Hai appena completato uno studio i cui risultati sono:

## Obiettivi completati:
{objectives_summary}

## Azioni eseguite:
{len(session.get('actions_log', []))} azioni totali

Analizza i risultati e suggerisci 3-5 direzioni per continuare la ricerca.
Sii specifico e basati sui pattern e le scoperte emerse.

## FORMATO RISPOSTA — SOLO JSON:
{{
  "analysis": "Analisi complessiva dei risultati...",
  "next_steps": [
    {{"title": "Titolo del prossimo passo", "description": "Descrizione dettagliata", "priority": "alta/media/bassa"}}
  ]
}}"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Goal originale: {session.get('goal', '')}\n\nSuggerisci i prossimi passi di ricerca."}
    ]
    
    model = model_override or ai_cfg.get("model", "deepseek-v4-flash")
    response, thinking, error = _call_ai_model(messages, ai_cfg, model,
        provider, endpoint, api_url, api_key, 0.5, max_tokens, top_p, timeout)
    
    if error or not response:
        return {"success": False, "error": error or "Nessuna risposta"}
    
    json_match = _extract_json_from_response(response)
    if not json_match:
        return {"success": False, "error": "Formato risposta non valido"}
    
    try:
        parsed = json.loads(json_match.group())
        steps = parsed.get("next_steps", [])
        set_next_steps(session_id, steps)
        return {"success": True, "next_steps": steps, "analysis": parsed.get("analysis", "")}
    except json.JSONDecodeError:
        return {"success": False, "error": "JSON malformato"}


def handle_research_decompose(self):
    """POST /api/research/decompose — Decompose goal into micro-objectives."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        goal = req.get("goal", "")
        agents = req.get("agents", [])
        model_override = req.get("model_override", "")
        
        if not session_id or not goal:
            return self.send_json_response({"success": False, "error": "session_id e goal richiesti"}, 400)
        
        ai_cfg = load_ai_config()
        result = decompose_goal_to_micro_objectives(goal, agents, ai_cfg, model_override, session_id)
        if result.get("success"):
            return self.send_json_response(result)
        return self.send_json_response(result, 500)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_research_next_steps(self):
    """POST /api/research/next_steps — Generate next steps after completion."""
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        model_override = req.get("model_override", "")
        
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)
        
        ai_cfg = load_ai_config()
        result = generate_next_steps(session_id, ai_cfg, model_override)
        if result.get("success"):
            return self.send_json_response(result)
        return self.send_json_response(result, 500)
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


# ==============================================================================
# RESEARCH START — Live Multi-Agent Execution (Research Lab v3)
# ==============================================================================

def handle_research_start(self):
    """POST /api/research/start — Esegue la sessione di ricerca con SSE streaming.
    Coordina gli agenti, invia messaggi live alla chat, aggiorna lo stato in tempo reale."""
    from core.research_sessions import get_session, update_objective, add_actions_log, save_session
    
    try:
        req = self.read_json_body()
        session_id = req.get("session_id", "")
        if not session_id:
            return self.send_json_response({"success": False, "error": "session_id richiesto"}, 400)
        
        session = get_session(session_id)
        if not session:
            return self.send_json_response({"success": False, "error": "Sessione non trovata"}, 404)
        
        # SSE
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        _sse_lock = threading.Lock()
        def _sse(event):
            with _sse_lock:
                try:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                except Exception:
                    pass
        
        try:
            ai_cfg = load_ai_config()
            objectives = session.get("micro_objectives", [])
            agents_config = session.get("agents", [])
            goal = session.get("goal", "")
            model_override = req.get("model_override", "")
            print(f"[RESEARCH_START] session={session_id}, objectives={len(objectives)}, agents={len(agents_config)}, model={model_override or ai_cfg.get('model','?')}", flush=True)
            
            # If no objectives, auto-decompose first
            if len(objectives) == 0:
                print(f"[RESEARCH_START] No objectives found, auto-decomposing...", flush=True)
                _sse({"type": "agent_thinking", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                      "thinking": "Decomposizione automatica del goal in micro-obiettivi...",
                      "message": "🧠 Coordinatore: scomposizione automatica del goal..."})
                decomp_result = _fallback_objectives(session_id, agents_config, goal)
                if decomp_result.get("success"):
                    objectives = decomp_result.get("objectives", [])
                    print(f"[RESEARCH_START] Auto-decomposed: {len(objectives)} objectives", flush=True)
                    _sse({"type": "agent_response", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                          "response": f"✅ Generati {len(objectives)} micro-obiettivi automaticamente",
                          "message": f"✅ Generati {len(objectives)} micro-obiettivi"})
            
            _sse({"type": "research_start", "session_id": session_id, "total_objectives": len(objectives),
                  "agents": agents_config, "message": f"🔬 Avvio ricerca con {len(objectives)} micro-obiettivi, {len(agents_config)} agenti"})
            
            # Coordinator plan visible in chat
            plan_lines = []
            for o in objectives:
                icon = AGENT_COLORS.get(o.get('assigned_to', ''), {}).get('icon', '🤖')
                plan_lines.append(f"{icon} **{o.get('title', '')[:60]}** → {o.get('assigned_to', '?')}")
            plan_msg = "📋 **Piano di lavoro:**\n" + "\n".join(plan_lines)
            _sse({"type": "agent_response", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                  "response": plan_msg, "message": f"📋 Piano: {len(objectives)} task assegnati"})
            
            # Execute objectives in parallel
            def process_objective(obj):
                if obj.get("status") == "done":
                    _sse({"type": "objective_complete", "objective_id": obj["id"], "title": obj["title"],
                          "message": f"✅ Già completato: {obj['title']}"})
                    return
                agent_id = obj.get("assigned_to", SIGMA_ARCHITECT_ID)
                from core.agent_registry import get_agent
                agent_check = get_agent(agent_id)
                if not agent_check:
                    agent_id = SIGMA_ARCHITECT_ID
                agent_name = agent_id
                provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
                    _load_agent_config(ai_cfg, model_override, agent_id)
                update_objective(session_id, obj["id"], {"status": "in_progress"})
                _sse({"type": "agent_start", "agent_id": agent_id, "agent_name": agent_name,
                      "objective_id": obj["id"], "objective": obj["title"],
                      "message": f"▶️ {agent_name} inizia: {obj['title']}"})
                _sse({"type": "agent_thinking", "agent_id": agent_id, "agent_name": agent_name,
                      "thinking": f"Analisi di: {obj['title']}", "objective_id": obj["id"],
                      "message": f"🧠 {agent_name} sta analizzando..."})
                # Role-specific system prompt
                role_prompts = {
                    "sigma_architect": "Sei l'Architetto coordinatore. Il tuo compito è leggere e analizzare TUTTI i file prodotti, verificare la completezza, e creare report riepilogativi.",
                    "math1": "Sei un MATEMATICO esperto. Crea file di teoria con definizioni rigorose, teoremi, dimostrazioni formali, esempi svolti. Usa LaTeX per ogni formula.",
                    "code_architect": "Sei uno SVILUPPATORE esperto. Scrivi codice Python pulito, test automatici, algoritmi efficienti. Documenta le scelte di design.",
                    "test-engineer": "Sei un QA ENGINEER. Scrivi test automatici usando sympy/pytest. Verifica correttezza di formule e algoritmi. Ogni test deve avere assert espliciti.",
                    "proof-reviewer": "Sei un REVISORE critico. Verifica la correttezza logica e matematica di TUTTI i file. Cerca errori, controesempi, imprecisioni. Produci un report di validazione dettagliato.",
                }
                fs_ctx = _build_filesystem_context()
                role_prefix = role_prompts.get(agent_id, f"Sei un agente specializzato: {agent_id}.")
                system_prompt = f"""{role_prefix}

Esegui il seguente micro-obiettivo di ricerca.

## OBIETTIVO GENERALE
{goal}

## MICRO-OBIETTIVO
{obj['title']}
{obj.get('description', '')}

## CRITERIO DI COMPLETAMENTO
{obj.get('completion_criteria', 'Esegui azioni pertinenti e riporta il risultato.')}

## CONTESTO DEL PROGETTO (filesystem)
{fs_ctx[:1500]}

## REGOLE OBBLIGATORIE
- DEVI SEMPRE includere almeno 1 azione create_file con contenuto SOSTANZIOSO (min 500 parole)
- Rispondi SOLO con JSON: {{"response": "...", "thinking": "...", "actions": [...]}}
- Azioni valide: create_file, edit_file, run_test, read_file
- Parla sempre in italiano.
- NON limitarti a descrivere — CREA il file con il contenuto completo."""
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Esegui: {obj['title']}"}
                ]
                model = model_override or ai_cfg.get("model", "deepseek-v4-flash")
                print(f"[RESEARCH_START] Calling {agent_id}: model={model}, provider={provider}", flush=True)
                response, thinking, error = _call_ai_model(messages, ai_cfg, model,
                    provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout)
                actions_executed = []
                if error:
                    print(f"[RESEARCH_START] AI error for {agent_id}: {error}", flush=True)
                    _sse({"type": "agent_error", "agent_id": agent_id, "objective_id": obj["id"],
                          "error": error, "message": f"❌ {agent_name}: {error}"})
                    _sse({"type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                          "response": f"⚠️ Errore AI, creazione file predefinito...", "message": f"⚠️ {agent_name}: errore API"})
                    default_result = _execute_default_action(self, session_id, obj, goal, _sse)
                    actions_executed = default_result
                    update_objective(session_id, obj["id"], {"status": "done", "result": "File creato (AI non disponibile)"})
                else:
                    print(f"[RESEARCH_START] AI response from {agent_id}: {len(response or '')} chars", flush=True)
                    if thinking:
                        _sse({"type": "agent_thinking", "agent_id": agent_id, "agent_name": agent_name,
                              "thinking": thinking[:2000], "message": f"🧠 {agent_name}: {thinking[:150]}..."})
                    json_match = _extract_json_from_response(response or "")
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group())
                            ai_response = parsed.get("response", response or "")
                            actions = parsed.get("actions", [])
                            _sse({"type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                                  "response": ai_response, "message": f"💬 {agent_name}: {ai_response[:300]}"})
                            if actions:
                                from core.task_handler import execute_ai_actions
                                actions_log = execute_ai_actions(self, actions, agent_name)
                                actions_executed = actions_log
                                sc = sum(1 for a in actions_log if a.get("success"))
                                fc = sum(1 for a in actions_log if not a.get("success"))
                                _sse({"type": "agent_actions", "agent_id": agent_id,
                                      "actions_log": actions_log, "success_count": sc, "fail_count": fc,
                                      "message": f"⚡ {agent_name}: {sc}✅/{fc}❌ azioni"})
                                update_objective(session_id, obj["id"], {"status": "done", "result": ai_response[:500]})
                            else:
                                default_result = _execute_default_action(self, session_id, obj, goal, _sse)
                                actions_executed = default_result
                                update_objective(session_id, obj["id"], {"status": "done", "result": "Azioni predefinite"})
                        except json.JSONDecodeError:
                            _sse({"type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                                  "response": (response or "")[:2000]})
                            default_result = _execute_default_action(self, session_id, obj, goal, _sse)
                            actions_executed = default_result
                            update_objective(session_id, obj["id"], {"status": "done", "result": "Analisi (JSON non valido)"})
                    else:
                        _sse({"type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                              "response": (response or "")[:2000], "message": f"💬 {agent_name}: {(response or '')[:200]}"})
                        default_result = _execute_default_action(self, session_id, obj, goal, _sse)
                        actions_executed = default_result
                        update_objective(session_id, obj["id"], {"status": "done", "result": "Azioni predefinite"})
                _sse({"type": "objective_complete", "objective_id": obj["id"],
                      "agent_id": agent_id, "title": obj["title"], "message": f"✅ Completato: {obj['title']}"})
                if actions_executed:
                    add_actions_log(session_id, actions_executed)
            
            # Run non-done objectives in parallel
            pending = [o for o in objectives if o.get("status") != "done"]
            with ThreadPoolExecutor(max_workers=min(4, len(pending))) as executor:
                futures = [executor.submit(process_objective, o) for o in pending]
                for f in futures:
                    try: f.result()
                    except Exception as e: print(f"[RESEARCH_START] Thread error: {e}", flush=True)
            
            # Check completion
            from core.research_sessions import check_all_satisfied
            all_satisfied, done_count, total = check_all_satisfied(session_id)
            
            if all_satisfied and total > 0:
                session["status"] = "completed"
                save_session(session)
                
                _sse({"type": "all_done", "done_count": done_count, "total": total,
                      "message": f"🎯 Tutti i {total} micro-obiettivi completati! Generazione next steps..."})
                
                next_result = generate_next_steps(session_id, ai_cfg, model_override)
                if next_result.get("success"):
                    _sse({"type": "next_steps_ready",
                          "next_steps": next_result.get("next_steps", []),
                          "analysis": next_result.get("analysis", ""),
                          "message": "💡 Next steps generati con successo"})
            else:
                _sse({"type": "research_done", "session_id": session_id,
                      "done_count": done_count, "total": total,
                      "message": f"⏹️ Ricerca completata: {done_count}/{total} obiettivi"})
        
        except Exception as e:
            _sse({"type": "error", "error": str(e), "message": f"❌ Errore: {e}"})
        
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    
    except Exception as e:
        try:
            self.send_json_response({"success": False, "error": str(e)}, 500)
        except Exception:
            pass