# ==============================================================================
# core/orchestration/orchestrator.py — Classic Multi-Agent Orchestrator
# Extracted from core/agent_orchestrator.py for Single Responsibility
# ==============================================================================
"""Coordinating multi-agent parallel/sequential sub-task execution.

Takes a global goal, decomposes it into agent sub-tasks, schedules them via
ThreadPoolExecutor, runs role-specific loops, and synthesizes the results.
"""

import json
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.ai_providers import load_ai_config, call_ai_model
from core.task_handler import execute_ai_actions
from core.agent_registry import get_all_agents, increment_usage, SIGMA_ARCHITECT_ID
from core.agent_memory import save_session_memory, get_memory_context
from core.logger import get_logger

# Chat helpers (now in core/chat sub-package)
from core.chat.prompt_builder import (
    _get_manifesto_content, _get_time_context,
    _build_filesystem_context,
)
from core.chat.response_parser import _extract_json_from_response

# Orchestration sub-package
from core.orchestration.agent_config import get_agent_color, load_agent_config

log = get_logger(__name__)

MAX_PARALLEL_WORKERS = 5


def _get_available_agents_for_goal(goal: str) -> list[dict]:
    agents = get_all_agents()
    return [a for a in agents if a.get("status") == "active"]


def _decompose_goal(goal: str, agents_list: list[dict], ai_cfg: dict, model_override: str) -> tuple[list[dict], str | None]:
    """Decompose the main goal into specific tasks for active agents."""
    main_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)

    agents_json = json.dumps([{
        "id": a.get("id"), "name": a.get("name"),
        "role": a.get("role"), "specialization": a.get("specialization")
    } for a in agents_list], indent=2)

    system_prompt = f"""Sei Sigma AI Architect, il coordinatore del team di ricerca.
Il tuo compito è analizzare l'obiettivo finale e creare un piano di lavoro distribuendo compiti precisi (sotto-task) agli agenti del team.

## AGENTI DISPONIBILI
{agents_json}

## STRUTTURA DEL PROGETTO (CONTESTO)
{_build_filesystem_context()[:1500]}

## REGOLE DI SCOMPOSIZIONE
1. Scomponi l'obiettivo in 2-4 sotto-task ben descritti
2. Assegna ogni sotto-task all'agente più adatto basandoti sulla sua specializzazione
3. Spiega chiaramente cosa deve fare l'agente (es. scrivere teoria in LaTeX, scrivere test in pytest, creare grafici D3 in viz/, etc.)
4. Rispondi SOLO ed ESCLUSIVAMENTE con un array JSON di sotto-task

## FORMATO RISPOSTA (SOLO JSON)
[
  {{
    "agent_id": "math1",
    "agent_name": "Sigma Math Researcher",
    "task": "Titolo sintetico del task",
    "description": "Istruzioni dettagliate di cosa fare concretamente. Sii specifico.",
    "actions_hint": ["create_file", "edit_file"]
  }}
]"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Scomponi l'obiettivo: {goal}"}
    ]

    log.info("Decomposing goal using model=%s provider=%s", main_model, provider)
    response, thinking, error = call_ai_model(
        messages, ai_cfg, main_model, provider, endpoint, api_url, api_key,
        0.3, max_tokens, top_p, timeout
    )
    if error:
        return _generate_fallback_tasks(agents_list, goal), error

    if not response:
        return _generate_fallback_tasks(agents_list, goal), "Nessuna risposta dal coordinatore"

    json_match = _extract_json_from_response(response)
    if not json_match:
        return _generate_fallback_tasks(agents_list, goal), None

    try:
        parsed = json.loads(json_match.group())
        if not isinstance(parsed, list):
            return _generate_fallback_tasks(agents_list, goal), None
        validated = []
        for t in parsed:
            validated.append({
                "agent_id": t.get("agent_id", SIGMA_ARCHITECT_ID),
                "agent_name": t.get("agent_name", "Agent"),
                "task": t.get("task", "Contributo al goal"),
                "description": t.get("description", ""),
                "actions_hint": t.get("actions_hint", ["create_file"]),
                "status": "pending", "result": None, "error": None,
            })
        if len(validated) < 2:
            return _generate_fallback_tasks(agents_list, goal), None
        return validated, None
    except json.JSONDecodeError:
        return _generate_fallback_tasks(agents_list, goal), None


def _generate_fallback_tasks(agents_list: list[dict], goal: str) -> list[dict]:
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
        template = task_templates.get(aid, {"task": "Contributo al goal", "description": goal[:200], "hint": ["create_file"]})
        tasks.append({"agent_id": aid, "agent_name": agent.get("name", "Sigma Agent"), "task": template["task"], "description": template["description"], "actions_hint": template["hint"], "status": "pending", "result": None, "error": None})
    return tasks


def _execute_subtask(self, subtask: dict, goal: str, stream_callback) -> tuple[bool, list[dict], str | None]:
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
    model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = load_agent_config(ai_cfg, model, agent_id)
    manifesto_path = agent.get("manifesto", "") if agent else ""
    system_prompt = _get_manifesto_content(manifesto_path)
    if not system_prompt.strip():
        system_prompt = f"Sei {agent_name}, un assistente AI specializzato. Rispondi in italiano."

    time_ctx = _get_time_context()
    fs_context = _build_filesystem_context()
    memory_context = get_memory_context(agent_id) if agent_id else ""
    action_prompt = f"""\n## OBIETTIVO GENERALE\n{goal}\n\n## TASK ASSEGNATO\n{task}\n{description}\n\n## REGOLE OBBLIGATORIE\n- Rispondi SOLO con JSON: {{"response": "...", "actions": [...]}}\n- Usa tipi di azione validi: create_file, edit_file, run_test, read_file, update_task\n- Struttura corretta: data/<topic>/<NN_modulo>/<sezione>/<file>\n- Sezioni permesse: teoria/, test/, viz/, docs/, whitepapers/\n- Alla fine usa update_task se appropriato\n"""
    full_system = f"{system_prompt}\n\n{time_ctx}\n\n{action_prompt}"
    if fs_context:
        full_system += f"\n\nStruttura progetto:\n{fs_context[:2000]}"
    if memory_context:
        full_system += f"\n\n{memory_context}"

    messages = [{"role": "system", "content": full_system}, {"role": "user", "content": f"Esegui il task: {task}\n\n{description}"}]
    max_iterations = 3
    all_actions_log = []

    for iteration in range(max_iterations):
        response, thinking, error = call_ai_model(
            messages, ai_cfg, model, provider, endpoint, api_url, api_key,
            0.3, max_tokens * 2, top_p, timeout
        )
        if error:
            if stream_callback:
                stream_callback({"type": "agent_task_error", "agent_id": agent_id, "iteration": iteration + 1, "error": error})
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
            if thinking and thinking.strip():
                full_response += f"🧠 **Thinking:**\n{thinking.strip()[:2000]}\n\n"
            full_response += f"💬 **Risposta:**\n{(response or ai_response or '')[:2000]}"

            if stream_callback:
                stream_callback({
                    "type": "agent_task_iteration", "agent_id": agent_id,
                    "iteration": iteration + 1, "max_iterations": max_iterations,
                    "success_count": success_count, "fail_count": fail_count,
                    "actions_log": iteration_log,
                    "ai_response": ai_response[:1000] if ai_response else "",
                    "full_response": full_response[:3000] if full_response else ""
                })
            if iteration >= 1 and is_done:
                break
            if iteration >= 1 and fail_count == 0:
                if is_done:
                    break
                if iteration < max_iterations - 1:
                    continue
            details = "\n".join(f"  {'✅' if a.get('success') else '❌'} {a.get('type','?')}: {a.get('message', a.get('error',''))}" for a in iteration_log)
            messages.append({"role": "system", "content": f"📋 Iterazione {iteration + 1}: {success_count}/{len(iteration_log)} azioni riuscite\n\n{details}"})
        except json.JSONDecodeError:
            break

    if agent_id:
        total_success = sum(1 for a in all_actions_log if a.get("success"))
        total_fail = sum(1 for a in all_actions_log if not a.get("success"))
        try:
            save_session_memory(agent_id, {
                "goal": f"[Orchestrator] {task[:100]}",
                "actions_performed": all_actions_log,
                "success_count": total_success,
                "fail_count": total_fail,
                "learning": "",
                "summary": f"Task orchestrato: {total_success}✅/{total_fail}❌"
            })
            increment_usage(agent_id, success=total_fail == 0)
        except Exception:
            pass

    total_success = sum(1 for a in all_actions_log if a.get("success"))
    return total_success > 0 or len(all_actions_log) == 0, all_actions_log, None


def _execute_subtask_wrapper(args: tuple) -> tuple:
    self, subtask, goal, stream_callback = args
    try:
        return subtask["agent_id"], *_execute_subtask(self, subtask, goal, stream_callback)
    except Exception as exc:
        return subtask["agent_id"], False, [], str(exc)


def _execute_parallel_subtasks(self, subtasks: list[dict], goal: str, stream_callback) -> tuple[list[dict], list[dict]]:
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
            if actions_log:
                all_actions_log.extend(actions_log)
            subtask["status"] = "done" if success else "failed"
            subtask["result"] = {"actions_count": len(actions_log or [])}
            subtask["error"] = error
            subtask_results.append(subtask)
            if stream_callback:
                stream_callback({
                    "type": "orchestrate_subtask_complete", "subtask_idx": 0,
                    "total_subtasks": len(subtasks), "agent_id": agent_id, "success": success, "error": error,
                    "message": f"{'✅' if success else '❌'} {subtask.get('agent_name', agent_id)}: {subtask.get('task', '')}"
                })
    return all_actions_log, subtask_results


def _synthesize_results(self, goal: str, subtask_results: list[dict], all_actions_log: list[dict], stream_callback) -> dict:
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
        stream_callback({
            "type": "orchestrate_done", "report": report,
            "message": f"🎯 Orchestrazione completata: {report['subtasks_completed']}/{len(subtask_results)} task, {total_success}/{total_actions} azioni, {len(files_created)} file creati"
        })
    return {"success": True, "report": report, "actions_log": all_actions_log}


def orchestrate(self, req: dict, stream_callback=None) -> dict:
    """Coordinate multi-agent sub-task execution based on the goal."""
    goal = req.get("message", "").strip()
    if not goal:
        return {"error": "Goal vuoto"}, 400
    strategy = req.get("strategy", "parallel")
    model_override = req.get("model", "")
    ai_cfg = load_ai_config()

    if stream_callback:
        stream_callback({"type": "orchestrate_start", "goal": goal, "strategy": strategy, "message": f"🎯 Avvio orchestrazione per: {goal}..."})
        stream_callback({"type": "orchestrate_phase", "phase": "decompose", "message": "📋 Scomposizione del goal in sotto-task..."})

    agents = _get_available_agents_for_goal(goal)
    subtasks, error = _decompose_goal(goal, agents, ai_cfg, model_override)
    if error:
        if stream_callback:
            stream_callback({"type": "orchestrate_error", "error": error})
        return {"error": error}, 500

    if stream_callback:
        stream_callback({
            "type": "orchestrate_plan", "total_subtasks": len(subtasks),
            "subtasks": [{"agent_id": s["agent_id"], "agent_name": s["agent_name"], "task": s["task"]} for s in subtasks],
            "message": f"✅ Piano creato: {len(subtasks)} sotto-task da {len(set(s['agent_id'] for s in subtasks))} agenti"
        })
        stream_callback({"type": "orchestrate_phase", "phase": "execute", "message": f"⚡ Esecuzione {'parallela' if strategy == 'parallel' else 'sequenziale'} di {len(subtasks)} sotto-task..."})

    if strategy == "parallel":
        all_actions_log, subtask_results = _execute_parallel_subtasks(self, subtasks, goal, stream_callback)
    else:
        all_actions_log = []
        subtask_results = []
        for idx, subtask in enumerate(subtasks):
            if stream_callback:
                stream_callback({
                    "type": "orchestrate_subtask_start", "subtask_idx": idx + 1, "total_subtasks": len(subtasks),
                    "agent_id": subtask["agent_id"], "agent_name": subtask["agent_name"], "task": subtask["task"]
                })
            success, actions_log, error = _execute_subtask(self, subtask, goal, stream_callback)
            all_actions_log.extend(actions_log or [])
            subtask["status"] = "done" if success else "failed"
            subtask["result"] = {"actions_count": len(actions_log or [])}
            subtask["error"] = error
            subtask_results.append(subtask)
            if stream_callback:
                stream_callback({
                    "type": "orchestrate_subtask_complete", "subtask_idx": idx + 1, "total_subtasks": len(subtasks),
                    "agent_id": subtask["agent_id"], "success": success, "error": error,
                    "message": f"{'✅' if success else '❌'} {subtask['agent_name']}: {subtask['task']}"
                })

    return _synthesize_results(self, goal, subtask_results, all_actions_log, stream_callback)


def handle_chat_orchestrate(self) -> None:
    """POST /api/chat/orchestrate — Stream orchestrator events (SSE)."""
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
                except Exception:
                    pass

        try:
            result = orchestrate(self, req, stream_callback=_sse)
            if isinstance(result, tuple) and len(result) == 2:
                _sse({"type": "error", "error": result[0].get("error", "Errore sconosciuto")})
        except Exception as e:
            _sse({"type": "error", "error": str(e)})

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    except Exception as exc:
        log.error("handle_chat_orchestrate failed: %s", exc)
        try:
            self.send_json_response({"error": str(exc)}, 500)
        except Exception:
            pass
