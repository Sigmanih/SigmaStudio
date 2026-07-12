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

from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.agent_registry import get_all_agents, get_specialized_agent, increment_usage, SIGMA_ARCHITECT_ID
from core.agent_memory import save_session_memory, get_memory_context
from core.logger import get_logger

# --- Chat helpers (now in core/chat sub-package) ---
from core.chat.prompt_builder import (
    _get_manifesto_content, _get_time_context,
    _build_filesystem_context, _collect_context_files,
)
from core.chat.response_parser import _extract_json_from_response

# --- Orchestration sub-package ---
from core.orchestration.agent_config import (
    AGENT_COLORS, get_agent_color, load_agent_config,
)

log = get_logger(__name__)

MAX_PARALLEL_WORKERS = 5

# Backward-compat alias (old callers used _load_agent_config)
_load_agent_config = load_agent_config



def _get_available_agents_for_goal(goal):
    agents = get_all_agents()
    return [a for a in agents if a.get("status") == "active"]


# ==============================================================================
# PHASE 1 — DECOMPOSE
# ==============================================================================

def _decompose_goal(goal, agents_list, ai_cfg, model_override):
    main_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
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
    response, thinking, error = call_ai_model(messages, ai_cfg, main_model,
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
    model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = _load_agent_config(ai_cfg, model, agent_id)
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
        response, thinking, error = call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, 0.3, max_tokens * 2, top_p, timeout)
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
        stream_callback({"type": "orchestrate_start", "goal": goal, "strategy": strategy, "message": f"🎯 Avvio orchestrazione per: {goal}..."})
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
    """Generate generic micro-objectives when AI decomposition fails. Used as last resort.
    Solo sigma_architect scrive teoria. Niente test/review a meno che non siano esplicitamente richiesti."""
    from core.research_sessions import add_micro_objective, get_session
    
    session = get_session(session_id)
    session_name = (session.get("name") or goal[:40]) if session else goal[:40]
    
    goal_lower = goal.lower()
    needs_testing = any(kw in goal_lower for kw in ['test', 'validazione', 'verifica', 'testing'])
    needs_review = any(kw in goal_lower for kw in ['revisione', 'review', 'revisore'])
    
    objectives = [
        {"title": f"Analisi e pianificazione: {goal[:200]}", "description": f"Analizza approfonditamente l'obiettivo: {goal[:2000]}. Leggi i file esistenti, analizza la struttura del progetto, e crea un documento di analisi iniziale con piano di lavoro dettagliato.", "assigned_to": "sigma_architect", "actions_hint": ["read_file", "create_file"], "completion_criteria": "Analisi iniziale documentata con piano di lavoro"},
        {"title": f"Teoria: {goal[:200]}", "description": f"CREA file di teoria completi e dettagliati per: '{goal[:2000]}'. Scrivi definizioni rigorose, teoremi con dimostrazioni formali, esempi svolti passo-passo. Usa LaTeX per ogni formula matematica. Crea ALMENO 3 file di teoria separati per coprire l'argomento in modo esaustivo. I file vanno in data/<topic>/01_base/teoria/.", "assigned_to": "sigma_architect", "actions_hint": ["create_file", "read_file"], "completion_criteria": "Almeno 3 file di teoria creati con contenuti sostanziosi (min 500 parole ciascuno)"},
    ]
    
    # Only add testing/review if explicitly mentioned in the goal
    if needs_testing:
        objectives.append({"title": f"Test: {goal[:200]}", "description": f"Verifica e testa i risultati per '{goal[:2000]}'. Crea test Python con pytest/sympy, esegui validazioni. Crea file in data/<topic>/01_base/test/.", "assigned_to": "sigma_architect", "actions_hint": ["create_file", "run_test"], "completion_criteria": "Test creati ed eseguiti con successo"})
    if needs_review:
        objectives.append({"title": f"Revisione: {goal[:200]}", "description": f"Verifica tutto il lavoro prodotto per '{goal[:2000]}'. Controlla completezza, coerenza, correttezza matematica. Crea file di revisione in data/<topic>/01_base/docs/.", "assigned_to": "sigma_architect", "actions_hint": ["read_file", "create_file"], "completion_criteria": "Report di revisione completato"})
    
    added = []
    for obj in objectives:
        result = add_micro_objective(session_id, obj)
        if result:
            added.append(result)
    
    return {"success": True, "objectives": added, "analysis": f"Obiettivi generici generati (coordinatore AI non disponibile): {len(added)} task", "count": len(added)}


# ==============================================================================
# THEORY FILE TEMPLATES — Used when AI fails to generate proper JSON actions
# Genera file di teoria strutturati per argomento con contenuti reali
# ==============================================================================

def _get_analisi1_files(base_path):
    """Generate all Analisi 1 theory files with real mathematical content."""
    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    
    def t(text):
        """Template helper: replaces {date_str} with actual date and fixes f-string escaped braces."""
        return text.replace('{date_str}', date_str).replace('{{', '{').replace('}}', '}')
    
    return [
        {
            "path": f"{base_path}/teoria/01_insiemi_numerici.md",
            "content": t("""# Insiemi Numerici e Proprietà Fondamentali

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Insieme dei Numeri Naturali ($\\mathbb{{N}}$)

L'insieme dei numeri naturali è definito assiomaticamente da Peano:
$$\\mathbb{{N}} = \\{{1, 2, 3, \\dots\\}}$$

### Assiomi di Peano
1. $1 \\in \\mathbb{{N}}$
2. Ogni $n \\in \\mathbb{{N}}$ ha un successore $s(n) \\in \\mathbb{{N}}$
3. $1$ non è successore di alcun numero
4. Se $s(n) = s(m)$ allora $n = m$
5. **Principio di induzione**: se $P(1)$ è vera e $P(k) \\implies P(k+1)$, allora $P(n)$ è vera $\\forall n \\in \\mathbb{{N}}$

### Proprietà
- **Chiusura**: $\\forall a,b \\in \\mathbb{{N}}: a+b \\in \\mathbb{{N}}, a\\cdot b \\in \\mathbb{{N}}$
- **Commutatività**: $a+b = b+a$, $a\\cdot b = b\\cdot a$
- **Associatività**: $(a+b)+c = a+(b+c)$, $(a\\cdot b)\\cdot c = a\\cdot(b\\cdot c)$
- **Elemento neutro**: $1$ per la moltiplicazione

## 2. Insieme dei Numeri Interi ($\\mathbb{{Z}}$)

$$\\mathbb{{Z}} = \\{{\\dots, -3, -2, -1, 0, 1, 2, 3, \\dots\\}}$$

$\\mathbb{{Z}}$ è un **anello commutativo unitario**: chiuso rispetto a somma, prodotto, differenza.

## 3. Insieme dei Numeri Razionali ($\\mathbb{{Q}}$)

$$\\mathbb{{Q}} = \\left\\{{ \\frac{{p}}{{q}} \\mid p \\in \\mathbb{{Z}}, q \\in \\mathbb{{Z}} \\setminus \\{{0\\}} \\right\\}}$$

### Proprietà
- $\\mathbb{{Q}}$ è un **campo**: ogni elemento non nullo ha inverso moltiplicativo
- $\\mathbb{{Q}}$ è **denso**: tra due razionali qualsiasi esiste sempre un altro razionale
- $\\mathbb{{Q}}$ è **numerabile** (dimostrazione di Cantor)

### Incompletezza di $\\mathbb{{Q}}$
$\\sqrt{{2}} \\notin \\mathbb{{Q}}$ (dimostrazione per assurdo).

## 4. Insieme dei Numeri Reali ($\\mathbb{{R}}$)

Costruzione tramite **sezioni di Dedekind** o **successioni di Cauchy**.

### Proprietà fondamentali
- $\\mathbb{{R}}$ è un **campo ordinato completo**
- **Assioma di completezza (o dell'estremo superiore)**: Ogni sottoinsieme non vuoto e superiormente limitato di $\\mathbb{{R}}$ ammette estremo superiore in $\\mathbb{{R}}$
- $\\mathbb{{R}}$ è **non numerabile** (argomento diagonale di Cantor)

### Estremo superiore e inferiore
- **Maggiorante**: $M$ è maggiorante di $A \\subseteq \\mathbb{{R}}$ se $\\forall a \\in A: a \\le M$
- **Estremo superiore ($\\sup A$)**: il minimo dei maggioranti
- **Estremo inferiore ($\\inf A$)**: il massimo dei minoranti
- **Massimo ($\\max A$)**: se $\\sup A \\in A$
- **Minimo ($\\min A$)**: se $\\inf A \\in A$

## 5. Numeri Complessi ($\\mathbb{{C}}$)

$$\\mathbb{{C}} = \\{{a + ib \\mid a,b \\in \\mathbb{{R}}, i^2 = -1\\}}$$

### Rappresentazioni
- **Algebrica**: $z = a + ib$
- **Polare**: $z = \\rho(\\cos\\theta + i\\sin\\theta)$ dove $\\rho = \\sqrt{{a^2 + b^2}}$, $\\theta = \\arctan(b/a)$
- **Esponenziale**: $z = \\rho e^{{i\\theta}}$ (formula di Eulero)

### Formula di De Moivre
$$(\\cos\\theta + i\\sin\\theta)^n = \\cos(n\\theta) + i\\sin(n\\theta)$$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/02_funzioni.md",
            "content": t("""# Funzioni Reali di Variabile Reale

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Definizione e Concetti Fondamentali

Una **funzione** $f: A \\to B$ è una legge che associa a ogni $x \\in A$ un unico $y \\in B$.

- **Dominio**: $A = \\text{{dom}}(f)$
- **Codominio**: $B$
- **Immagine**: $f(A) = \\{{f(x) \\mid x \\in A\\}}$
- **Grafico**: $G_f = \\{{(x, f(x)) \\mid x \\in A\\}} \\subseteq \\mathbb{{R}}^2$

### Classificazione
- **Iniettiva**: $x_1 \\neq x_2 \\implies f(x_1) \\neq f(x_2)$
- **Suriettiva**: $f(A) = B$
- **Biiettiva**: iniettiva e suriettiva

## 2. Funzioni Elementari

### Funzione Potenza
$$f(x) = x^n, \\quad n \\in \\mathbb{{N}}$$

- $n$ pari: dominio $\\mathbb{{R}}$, immagine $[0, +\\infty)$
- $n$ dispari: dominio $\\mathbb{{R}}$, immagine $\\mathbb{{R}}$

### Funzione Esponenziale
$$f(x) = a^x, \\quad a > 0, a \\neq 1$$

- Dominio: $\\mathbb{{R}}$
- Immagine: $(0, +\\infty)$
- $a > 1$: crescente; $0 < a < 1$: decrescente
- **Limite notevole**: $\\lim_{{x \\to 0}} \\frac{{e^x - 1}}{{x}} = 1$

### Funzione Logaritmo
$$f(x) = \\log_a(x), \\quad a > 0, a \\neq 1$$

- Dominio: $(0, +\\infty)$
- Immagine: $\\mathbb{{R}}$
- È l'inversa dell'esponenziale: $a^{{\\log_a(x)}} = x$, $\\log_a(a^x) = x$

### Proprietà dei Logaritmi
1. $\\log_a(xy) = \\log_a(x) + \\log_a(y)$
2. $\\log_a\\left(\\frac{{x}}{{y}}\\right) = \\log_a(x) - \\log_a(y)$
3. $\\log_a(x^n) = n\\log_a(x)$
4. $\\log_a(x) = \\frac{{\\log_b(x)}}{{\\log_b(a)}}$ (cambio di base)

### Funzioni Trigonometriche
- $\\sin x$: periodica $2\\pi$, dispari, $[-1, 1]$
- $\\cos x$: periodica $2\\pi$, pari, $[-1, 1]$
- $\\tan x = \\frac{{\\sin x}}{{\\cos x}}$, periodica $\\pi$

### Identità Fondamentali
$$\\sin^2 x + \\cos^2 x = 1$$
$$\\sin(2x) = 2\\sin x \\cos x$$
$$\\cos(2x) = \\cos^2 x - \\sin^2 x$$

## 3. Funzioni Inverse

### Arcsin, Arccos, Arctan
- $\\arcsin: [-1,1] \\to [-\\pi/2, \\pi/2]$
- $\\arccos: [-1,1] \\to [0, \\pi]$
- $\\arctan: \\mathbb{{R}} \\to (-\\pi/2, \\pi/2)$

## 4. Composizione di Funzioni

$$(g \\circ f)(x) = g(f(x))$$

Dominio: $\\{{x \\in \\text{{dom}}(f) \\mid f(x) \\in \\text{{dom}}(g)\\}}$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/03_limiti.md",
            "content": t("""# Limiti e Continuità

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Definizione di Limite (Weierstrass)

### Limite Finito per $x \\to x_0$
$$\\lim_{{x \\to x_0}} f(x) = L \\iff \\forall \\varepsilon > 0\\; \\exists \\delta > 0 : 0 < |x - x_0| < \\delta \\implies |f(x) - L| < \\varepsilon$$

### Limite Infinito
$$\\lim_{{x \\to x_0}} f(x) = +\\infty \\iff \\forall M > 0\\; \\exists \\delta > 0 : 0 < |x - x_0| < \\delta \\implies f(x) > M$$

### Limite all'Infinito
$$\\lim_{{x \\to +\\infty}} f(x) = L \\iff \\forall \\varepsilon > 0\\; \\exists N > 0 : x > N \\implies |f(x) - L| < \\varepsilon$$

## 2. Teoremi sui Limiti

### Teorema di Unicità
Se $\\lim_{{x \\to x_0}} f(x) = L_1$ e $\\lim_{{x \\to x_0}} f(x) = L_2$, allora $L_1 = L_2$.

### Teorema della Permanenza del Segno
Se $\\lim_{{x \\to x_0}} f(x) = L > 0$, allora esiste un intorno di $x_0$ in cui $f(x) > 0$.

### Teorema del Confronto (dei Carabinieri)
Se $g(x) \\le f(x) \\le h(x)$ in un intorno di $x_0$ e $\\lim g(x) = \\lim h(x) = L$, allora $\\lim f(x) = L$.

### Algebra dei Limiti
$$\\lim (f + g) = \\lim f + \\lim g$$
$$\\lim (f \\cdot g) = \\lim f \\cdot \\lim g$$
$$\\lim \\frac{{f}}{{g}} = \\frac{{\\lim f}}{{\\lim g}},\\quad \\text{{se }} \\lim g \\neq 0$$

## 3. Forme Indeterminate
$$\\frac{{0}}{{0}},\\quad \\frac{{\\infty}}{{\\infty}},\\quad 0 \\cdot \\infty,\\quad \\infty - \\infty,\\quad 1^\\infty,\\quad 0^0,\\quad \\infty^0$$

## 4. Limiti Notevoli

### Trigonometrici
$$\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}} = 1$$
$$\\lim_{{x \\to 0}} \\frac{{1 - \\cos x}}{{x^2}} = \\frac{{1}}{{2}}$$

### Esponenziali e Logaritmici
$$\\lim_{{x \\to 0}} \\frac{{e^x - 1}}{{x}} = 1$$
$$\\lim_{{x \\to 0}} \\frac{{\\ln(1 + x)}}{{x}} = 1$$
$$\\lim_{{x \\to \\infty}} \\left(1 + \\frac{{1}}{{x}}\\right)^x = e$$

## 5. Continuità

$f$ è **continua** in $x_0$ se:
$$\\lim_{{x \\to x_0}} f(x) = f(x_0)$$

### Proprietà delle Funzioni Continue
- Somma, prodotto, quoziente di continue è continua
- Composizione di continue è continua
- **Teorema di Weierstrass**: una funzione continua su $[a,b]$ ammette massimo e minimo
- **Teorema dei Valori Intermedi**: se $f$ continua su $[a,b]$, allora $f$ assume tutti i valori tra $f(a)$ e $f(b)$
- **Teorema di Bolzano**: se $f(a) \\cdot f(b) < 0$, esiste $c \\in (a,b)$ tale che $f(c) = 0$

## 6. Punti di Discontinuità

1. **Prima specie (salto)**: $\\lim_{{x \\to x_0^-}} f(x) \\neq \\lim_{{x \\to x_0^+}} f(x)$
2. **Seconda specie**: almeno uno dei limiti non esiste o è infinito
3. **Terza specie (eliminabile)**: $\\lim_{{x \\to x_0}} f(x)$ esiste ma $f(x_0) \\neq \\lim f$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/04_derivate.md",
            "content": t("""# Derivate e Calcolo Differenziale

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Definizione di Derivata

La derivata di $f$ in $x_0$ è:
$$f'(x_0) = \\lim_{{h \\to 0}} \\frac{{f(x_0 + h) - f(x_0)}}{{h}}$$

### Interpretazione Geometrica
$f'(x_0)$ è il coefficiente angolare della retta tangente al grafico di $f$ in $(x_0, f(x_0))$.

$$\\text{{retta tangente}}: y - f(x_0) = f'(x_0)(x - x_0)$$

## 2. Derivate Fondamentali

| $f(x)$ | $f'(x)$ |
|--------|---------|
| $c$ (costante) | $0$ |
| $x^n$ | $nx^{{n-1}}$ |
| $e^x$ | $e^x$ |
| $a^x$ | $a^x \\ln a$ |
| $\\ln x$ | $1/x$ |
| $\\sin x$ | $\\cos x$ |
| $\\cos x$ | $-\\sin x$ |
| $\\tan x$ | $1/\\cos^2 x = 1 + \\tan^2 x$ |
| $\\arcsin x$ | $1/\\sqrt{{1-x^2}}$ |
| $\\arccos x$ | $-1/\\sqrt{{1-x^2}}$ |
| $\\arctan x$ | $1/(1+x^2)$ |

## 3. Regole di Derivazione

### Linearità
$$(f+g)' = f' + g', \\quad (cf)' = c f'$$

### Prodotto (Leibniz)
$$(f \\cdot g)' = f'g + fg'$$

### Quoziente
$$\\left(\\frac{{f}}{{g}}\\right)' = \\frac{{f'g - fg'}}{{g^2}}$$

### Catena (Composizione)
$$(g \\circ f)'(x) = g'(f(x)) \\cdot f'(x)$$

## 4. Teoremi Fondamentali

### Teorema di Fermat
Se $f$ ha un estremo locale in $x_0$ ed è derivabile, allora $f'(x_0) = 0$.

### Teorema di Rolle
Se $f$ è continua su $[a,b]$, derivabile su $(a,b)$ e $f(a) = f(b)$, allora esiste $c \\in (a,b)$ tale che $f'(c) = 0$.

### Teorema di Lagrange (Valore Medio)
Se $f$ è continua su $[a,b]$ e derivabile su $(a,b)$, esiste $c \\in (a,b)$ tale che:
$$f'(c) = \\frac{{f(b) - f(a)}}{{b - a}}$$

### Teorema di Cauchy
Generalizzazione di Lagrange: esistono $g$ continua/derivabile, $g' \\neq 0$, allora:
$$\\frac{{f(b)-f(a)}}{{g(b)-g(a)}} = \\frac{{f'(c)}}{{g'(c)}}$$

## 5. Regola di De L'Hôpital

Se $\\lim \\frac{{f}}{{g}}$ è $\\frac{{0}}{{0}}$ o $\\frac{{\\infty}}{{\\infty}}$:
$$\\lim_{{x \\to x_0}} \\frac{{f(x)}}{{g(x)}} = \\lim_{{x \\to x_0}} \\frac{{f'(x)}}{{g'(x)}}$$

## 6. Studio di Funzione

1. **Dominio**: trovare dove $f$ è definita
2. **Simmetrie**: $f$ pari ($f(-x)=f(x)$) o dispari ($f(-x)=-f(x)$)
3. **Intersezioni** con gli assi
4. **Segno** della funzione
5. **Asintoti**:
   - Orizzontale: $\\lim_{{x \\to \\pm\\infty}} f(x) = L$
   - Verticale: $\\lim_{{x \\to x_0}} f(x) = \\pm\\infty$
   - Obliquo: $y = mx + q$ con $m = \\lim f(x)/x$, $q = \\lim (f(x)-mx)$
6. **Crescenza/decrescenza**: $f'(x) > 0$ crescente, $f'(x) < 0$ decrescente
7. **Punti critici**: $f'(x) = 0$ o $f'$ non esiste
8. **Concavità**: $f''(x) > 0$ concava verso l'alto

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/05_integrali.md",
            "content": t("""# Integrali e Calcolo Integrale

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Integrale di Riemann

Sia $f: [a,b] \\to \\mathbb{{R}}$ limitata. Si considera una partizione $P = \\{{x_0, x_1, \\dots, x_n\\}}$ di $[a,b]$.

### Somme di Riemann
$$S(P,f) = \\sum_{{k=1}}^n f(\\xi_k)(x_k - x_{{k-1}}), \\quad \\xi_k \\in [x_{{k-1}}, x_k]$$

### Integrale Definito
$$\\int_a^b f(x)\\,dx = \\lim_{{n \\to \\infty}} \\sum_{{k=1}}^n f(\\xi_k)\\Delta x_k$$

## 2. Teorema Fondamentale del Calcolo Integrale (Primo)

Se $f$ è continua su $[a,b]$, allora $F(x) = \\int_a^x f(t)\\,dt$ è derivabile e:
$$F'(x) = f(x)$$

## 3. Teorema Fondamentale del Calcolo Integrale (Secondo)

Se $F$ è una primitiva di $f$ (cioè $F' = f$), allora:
$$\\int_a^b f(x)\\,dx = F(b) - F(a)$$

## 4. Integrali Indefiniti

| $f(x)$ | $\\int f(x)\\,dx$ |
|--------|-------------------|
| $x^n$ ($n \\neq -1$) | $\\frac{{x^{{n+1}}}}{{n+1}} + C$ |
| $1/x$ | $\\ln|x| + C$ |
| $e^x$ | $e^x + C$ |
| $a^x$ | $a^x/\\ln a + C$ |
| $\\sin x$ | $-\\cos x + C$ |
| $\\cos x$ | $\\sin x + C$ |
| $1/\\cos^2 x$ | $\\tan x + C$ |
| $1/(1+x^2)$ | $\\arctan x + C$ |
| $1/\\sqrt{{1-x^2}}$ | $\\arcsin x + C$ |

## 5. Tecniche di Integrazione

### Integrazione per Parti
$$\\int f(x)g'(x)\\,dx = f(x)g(x) - \\int f'(x)g(x)\\,dx$$

### Integrazione per Sostituzione
$$\\int f(g(x))g'(x)\\,dx = \\int f(u)\\,du, \\quad u = g(x)$$

### Integrazione di Frazioni Razionali
Frazioni proprie con denominatore scomponibile in fattori:
1. Denominatore con radici reali semplici
2. Denominatore con radici reali multiple
3. Denominatore con radici complesse coniugate

## 6. Integrali Impropri

### Estensione a Intervalli Illimitati
$$\\int_a^{+\\infty} f(x)\\,dx = \\lim_{{b \\to +\\infty}} \\int_a^b f(x)\\,dx$$

### Funzioni non Limitate
$$\\int_a^b f(x)\\,dx \\quad \\text{{con }} \\lim_{{x \\to c}} f(x) = \\pm\\infty,\\; c \\in [a,b]$$

**Criteri di convergenza**: confronto, confronto asintotico, convergenza assoluta.

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/06_successioni.md",
            "content": t("""# Successioni e Serie Numeriche

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Definizione di Successione

Una **successione** è una funzione $a: \\mathbb{{N}} \\to \\mathbb{{R}}$, indicata con $\\{{a_n\\}}_{{n \\in \\mathbb{{N}}}}$.

### Limite di una Successione
$$\\lim_{{n \\to \\infty}} a_n = L \\iff \\forall \\varepsilon > 0\\; \\exists N : n > N \\implies |a_n - L| < \\varepsilon$$

## 2. Teoremi sulle Successioni

### Convergenza e Limitatezza
Ogni successione convergente è limitata. Non vale il viceversa.

### Teorema del Confronto
Se $a_n \\le b_n \\le c_n$ definitivamente e $\\lim a_n = \\lim c_n = L$, allora $\\lim b_n = L$.

### Criterio di Cauchy
$\\{{a_n\\}}$ converge $\\iff$ $\\forall \\varepsilon > 0\\; \\exists N : m,n > N \\implies |a_m - a_n| < \\varepsilon$.

## 3. Serie Numeriche

### Definizione
$$\\sum_{{n=1}}^{\\infty} a_n = \\lim_{{N \\to \\infty}} S_N = \\lim_{{N \\to \\infty}} \\sum_{{n=1}}^N a_n$$

### Serie Geometrica
$$\\sum_{{n=0}}^{\\infty} q^n = \\frac{{1}}{{1-q}} \\quad \\text{{se }} |q| < 1$$
Diverge se $|q| \\ge 1$.

### Serie Armonica
$$\\sum_{{n=1}}^{\\infty} \\frac{{1}}{{n}} = +\\infty$$
La serie armonica diverge (lentamente).

### Serie di Mengoli
$$\\sum_{{n=1}}^{\\infty} \\frac{{1}}{{n(n+1)}} = 1$$

## 4. Criteri di Convergenza

### Criterio del Confronto
Se $0 \\le a_n \\le b_n$ e $\\sum b_n$ converge, allora $\\sum a_n$ converge.

### Criterio della Radice (Cauchy)
Se $\\limsup \\sqrt[n]{{|a_n|}} = L$:
- $L < 1$: converge
- $L > 1$: diverge
- $L = 1$: dubbio

### Criterio del Rapporto (d'Alembert)
Se $\\lim \\left|\\frac{{a_{{n+1}}}}{{a_n}}\\right| = L$:
- $L < 1$: converge
- $L > 1$: diverge
- $L = 1$: dubbio

### Criterio di Leibniz (Serie a Segni Alterni)
$$\\sum (-1)^n a_n \\text{{ con }} a_n \\to 0, a_n \\text{{ decrescente}} \\implies \\text{{converge}}$$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/07_esponenziali_logaritmi.md",
            "content": t("""# Esponenziali, Logaritmi e Funzioni Trascendenti

**Data:** {date_str} | **Argomento:** Analisi Matematica 1

## 1. Funzione Esponenziale

### Definizione
$$f(x) = a^x, \\quad a > 0, a \\neq 1$$

### Numero di Nepero $e$
$$e = \\lim_{{n \\to \\infty}} \\left(1 + \\frac{{1}}{{n}}\\right)^n = \\sum_{{n=0}}^{\\infty} \\frac{{1}}{{n!}} \\approx 2.71828$$

### Proprietà
1. $a^0 = 1$
2. $a^{{x+y}} = a^x a^y$
3. $a^{{x-y}} = a^x / a^y$
4. $(a^x)^y = a^{{xy}}$

### Limiti Notevoli
$$\\lim_{{x \\to 0}} \\frac{{e^x - 1}}{{x}} = 1$$
$$\\lim_{{x \\to -\\infty}} e^x = 0$$
$$\\lim_{{x \\to +\\infty}} e^x = +\\infty$$
$$\\lim_{{x \\to +\\infty}} \\frac{{x^n}}{{e^x}} = 0 \\quad \\forall n$$

## 2. Funzione Logaritmo

### Definizione
$$\\log_a(x) = y \\iff a^y = x, \\quad x > 0$$

### Relazione con Esponenziale
$$a^{{\\log_a x}} = x, \\quad \\log_a(a^x) = x$$

### Proprietà dei Logaritmi
1. $\\log_a(xy) = \\log_a x + \\log_a y$
2. $\\log_a\\left(\\frac{{x}}{{y}}\\right) = \\log_a x - \\log_a y$
3. $\\log_a(x^n) = n\\log_a x$
4. $\\log_a\\sqrt[n]{{x}} = \\frac{{1}}{{n}}\\log_a x$
5. **Cambio di base**: $\\log_a x = \\frac{{\\log_b x}}{{\\log_b a}}$

### Logaritmo Naturale
$$\\ln x = \\log_e x$$
$$\\frac{{d}}{{dx}}\\ln x = \\frac{{1}}{{x}}$$
$$\\int \\frac{{1}}{{x}}\\,dx = \\ln|x| + C$$

## 3. Funzioni Iperboliche

### Definizioni
$$\\sinh x = \\frac{{e^x - e^{{-x}}}}{{2}}$$
$$\\cosh x = \\frac{{e^x + e^{{-x}}}}{{2}}$$
$$\\tanh x = \\frac{{\\sinh x}}{{\\cosh x}}$$

### Proprietà
- $\\cosh^2 x - \\sinh^2 x = 1$
- $\\sinh$ è dispari, $\\cosh$ è pari
- $\\frac{{d}}{{dx}}\\sinh x = \\cosh x$
- $\\frac{{d}}{{dx}}\\cosh x = \\sinh x$

## 4. Confronto tra Funzioni (Gerarchia degli Infiniti)

Per $x \\to +\\infty$:
$$\\log_a x \\ll x^\\alpha \\ll a^x \\ll x! \\ll x^x$$
dove $\\ll$ significa "cresce più lentamente".

Per $x \\to 0^+$:
$$x^\\alpha \\ll \\log_a x$$

## 5. Sviluppi di Taylor (principali)

$$e^x = 1 + x + \\frac{{x^2}}{{2!}} + \\frac{{x^3}}{{3!}} + \\frac{{x^4}}{{4!}} + \\dots = \\sum_{{n=0}}^{\\infty} \\frac{{x^n}}{{n!}}$$
$$\\ln(1+x) = x - \\frac{{x^2}}{{2}} + \\frac{{x^3}}{{3}} - \\frac{{x^4}}{{4}} + \\dots = \\sum_{{n=1}}^{\\infty} \\frac{{(-1)^{{n+1}}}}{{n}}x^n$$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
        {
            "path": f"{base_path}/teoria/08_formulario.md",
            "content": t("""# Formulario di Analisi Matematica 1

**Data:** {date_str} | **Argomento:** Analisi Matematica 1 — Riepilogo

## 1. Derivate Fondamentali

$$
\\begin{{array}}{{ll}}
\\frac{{d}}{{dx}}c = 0 & \\frac{{d}}{{dx}}x^n = nx^{{n-1}} \\\\
\\frac{{d}}{{dx}}e^x = e^x & \\frac{{d}}{{dx}}a^x = a^x\\ln a \\\\
\\frac{{d}}{{dx}}\\ln x = \\frac{{1}}{{x}} & \\frac{{d}}{{dx}}\\log_a x = \\frac{{1}}{{x\\ln a}} \\\\
\\frac{{d}}{{dx}}\\sin x = \\cos x & \\frac{{d}}{{dx}}\\cos x = -\\sin x \\\\
\\frac{{d}}{{dx}}\\tan x = \\frac{{1}}{{\\cos^2 x}} & \\frac{{d}}{{dx}}\\arcsin x = \\frac{{1}}{{\\sqrt{{1-x^2}}}} \\\\
\\frac{{d}}{{dx}}\\arccos x = -\\frac{{1}}{{\\sqrt{{1-x^2}}}} & \\frac{{d}}{{dx}}\\arctan x = \\frac{{1}}{{1+x^2}}
\\end{{array}}
$$

## 2. Regole di Derivazione

$$
\\begin{{aligned}}
(f+g)' &= f' + g' \\\\
(f\\cdot g)' &= f'g + fg' \\\\
\\left(\\frac{{f}}{{g}}\\right)' &= \\frac{{f'g - fg'}}{{g^2}} \\\\
(g\\circ f)' &= g'(f(x)) \\cdot f'(x)
\\end{{aligned}}
$$

## 3. Integrali Indefiniti

$$
\\begin{{array}}{{ll}}
\\int x^n\\,dx = \\frac{{x^{{n+1}}}}{{n+1}} + C\\;(n\\neq -1) & \\int \\frac{{1}}{{x}}\\,dx = \\ln|x| + C \\\\
\\int e^x\\,dx = e^x + C & \\int a^x\\,dx = \\frac{{a^x}}{{\\ln a}} + C \\\\
\\int \\sin x\\,dx = -\\cos x + C & \\int \\cos x\\,dx = \\sin x + C \\\\
\\int \\frac{{1}}{{\\cos^2 x}}\\,dx = \\tan x + C & \\int \\frac{{1}}{{1+x^2}}\\,dx = \\arctan x + C \\\\
\\int \\frac{{1}}{{\\sqrt{{1-x^2}}}}\\,dx = \\arcsin x + C
\\end{{array}}
$$

## 4. Tecniche di Integrazione

$$
\\int fg' = fg - \\int f'g \\quad\\text{{(parti)}}
$$
$$
\\int f(g(x))g'(x)\\,dx = \\int f(u)\\,du,\\; u=g(x) \\quad\\text{{(sostituzione)}}
$$

## 5. Limiti Notevoli

$$
\\begin{{aligned}}
\\lim_{{x\\to 0}} \\frac{{\\sin x}}{{x}} &= 1 \\\\
\\lim_{{x\\to 0}} \\frac{{1-\\cos x}}{{x^2}} &= \\frac{{1}}{{2}} \\\\
\\lim_{{x\\to 0}} \\frac{{e^x-1}}{{x}} &= 1 \\\\
\\lim_{{x\\to 0}} \\frac{{\\ln(1+x)}}{{x}} &= 1 \\\\
\\lim_{{x\\to \\infty}} \\left(1+\\frac{{1}}{{x}}\\right)^x &= e
\\end{{aligned}}
$$

## 6. Sviluppi di Taylor

$$
\\begin{{aligned}}
e^x &= 1 + x + \\frac{{x^2}}{{2!}} + \\frac{{x^3}}{{3!}} + o(x^3) \\\\
\\sin x &= x - \\frac{{x^3}}{{3!}} + \\frac{{x^5}}{{5!}} + o(x^5) \\\\
\\cos x &= 1 - \\frac{{x^2}}{{2!}} + \\frac{{x^4}}{{4!}} + o(x^4) \\\\
\\ln(1+x) &= x - \\frac{{x^2}}{{2}} + \\frac{{x^3}}{{3}} + o(x^3) \\\\
(1+x)^\\alpha &= 1 + \\alpha x + \\frac{{\\alpha(\\alpha-1)}}{{2}}x^2 + o(x^2)
\\end{{aligned}}
$$

## 7. Teoremi Fondamentali

- **Rolle**: $f(a)=f(b) \\implies \\exists c: f'(c)=0$
- **Lagrange**: $\\exists c: f'(c) = \\frac{{f(b)-f(a)}}{{b-a}}$
- **De L'Hôpital**: $\\lim \\frac{{f}}{{g}} = \\lim \\frac{{f'}}{{g'}}$ (se $\\frac{{0}}{{0}}$ o $\\frac{{\\infty}}{{\\infty}}$)
- **Fondamentale Calcolo**: $\\int_a^b f = F(b)-F(a)$ dove $F'=f$

---
*Generato automaticamente da Sigma Studio — {date_str}*
"""),
        },
    ]


def _execute_default_action(self, session_id, obj, goal, _sse):
    """When AI fails to produce actions, generate structured theory files with real content.
    Instead of creating a single placeholder, creates multiple well-organized files
    covering the full topic curriculum."""
    from core.research_sessions import add_actions_log
    
    # Extract topic from session goal — use session name if available
    from core.research_sessions import get_session
    session = get_session(session_id)
    session_name = (session.get("name") or "").lower() if session else ""
    topic = None
    
    # Priority: goal keywords > session name > "generale"
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
    
    from core.task_handler import execute_ai_actions
    
    # Generate files based on topic
    all_actions = []
    file_count = 0
    
    if topic == "analisi_1":
        files = _get_analisi1_files(module_path)
        for f in files:
            all_actions.append({"type": "create_file", "path": f["path"], "content": f["content"]})
            file_count += 1
    else:
        # Generic fallback: single file with descriptive name
        filename = f"{topic.replace('_', '_')}_teoria.md"
        filepath = f"{module_path}/teoria/{filename}"
        content = f"""# {topic.replace('_', ' ').title()}

**Goal originale:** {goal[:300]}

## Contenuti
Documento generato automaticamente per l'argomento: {topic}.

*Generato il {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        all_actions.append({"type": "create_file", "path": filepath, "content": content})
        file_count = 1
    
    # Execute all actions
    total_log = []
    for action in all_actions:
        result = execute_ai_actions(self, [action], "Sistema")
        total_log.extend(result)
    
    print(f"[RESEARCH_START] Default actions: created {file_count} files for topic '{topic}'", flush=True)
    _sse({"type": "agent_actions", "agent_id": "sistema",
          "actions_log": total_log, "success_count": file_count, "fail_count": 0,
          "message": f"📚 Creati {file_count} file di teoria per {topic}"})
    add_actions_log(session_id, total_log)
    return total_log


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
    
    coordinator_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
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
    
    model = coordinator_model
    print(f"[DECOMPOSE] Calling coordinator with model={model}, provider={provider}", flush=True)
    response, thinking, error = call_ai_model(messages, ai_cfg, model,
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
    
    next_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
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
    
    model = next_model
    response, thinking, error = call_ai_model(messages, ai_cfg, model,
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
                plan_lines.append(f"{icon} **{o.get('title', '')}** → {o.get('assigned_to', '?')}")
            plan_msg = "📋 **Piano di lavoro:**\n" + "\n".join(plan_lines)
            _sse({"type": "agent_response", "agent_id": "sigma_architect", "agent_name": "Coordinatore",
                  "response": plan_msg, "message": f"📋 Piano di lavoro: {len(objectives)} task assegnati"})
            
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
                agent_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
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

## REGOLE OBBLIGATORIE — LEGGI ATTENTAMENTE
1. DEVI SEMPRE includere almeno 1 azione create_file con contenuto SOSTANZIOSO (min 800 parole)
2. Rispondi SOLO con JSON. NIENTE altro. NIENTE testo fuori dal JSON. NIENTE spiegazioni.
3. Azioni valide: create_file, edit_file, run_test, read_file
4. Parla sempre in italiano all'interno del campo "response".
5. Il campo "thinking" DEVE contenere il tuo ragionamento in italiano.
6. NON iniziare mai con "Ecco" o altre frasi — SOLO JSON puro.

## ESEMPIO CONCRETO di risposta corretta:
{{"response": "Ho creato il file di teoria sugli insiemi numerici con definizioni e teoremi.", "thinking": "Analizzo il topic e preparo il contenuto...", "actions": [{{"type": "create_file", "path": "data/analisi_1/01_base/teoria/01_insiemi_numerici.md", "content": "# Insiemi Numerici\\n\\n## Insieme dei numeri naturali\\nL'insieme dei numeri naturali si indica con N = {{1,2,3,...}}.\\n\\n### Proprietà\\n- Chiusura rispetto a somma e prodotto\\n- Principio di induzione\\n\\n## Numeri Interi\\nZ = {{..., -2, -1, 0, 1, 2, ...}}..."}}]}}"""
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Esegui: {obj['title']}"}
                ]
                print(f"[RESEARCH_START] Calling {agent_id}: model={agent_model}, provider={provider}", flush=True)
                response, thinking, error = call_ai_model(messages, ai_cfg, agent_model,
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
                              "thinking": thinking[:8000], "message": f"🧠 {agent_name}: {thinking[:200]}..."})
                    json_match = _extract_json_from_response(response or "")
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group())
                            ai_response = parsed.get("response", response or "")
                            actions = parsed.get("actions", [])
                            _sse({"type": "agent_response", "agent_id": agent_id, "agent_name": agent_name,
                                  "response": ai_response, "message": f"💬 {agent_name}: {ai_response[:500]}"})
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
                              "response": (response or "")[:8000], "message": f"💬 {agent_name}: {(response or '')[:200]}"})
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