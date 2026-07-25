# ==============================================================================
# core/loop/autonomous_runner.py — Task-Driven Autonomous Loop Engine
# Sigma Studio v7 — Modular Loop Sub-package
# ==============================================================================
"""Task-driven autonomous execution loop engine with 3 phases:
Phase 1 — PLAN: AI creates tasks in tasks.json
Phase 2 — EXECUTE: Execute task actions sequentially with verification
Phase 3 — REPORT: Final summary & audit log
"""

import os
import json
import datetime
from core.logger import get_logger
from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model
from core.task_handler import execute_ai_actions
from core.loop.verification import _build_loop_filesystem_context, _get_tasks_context, _extract_json_from_response

log = get_logger(__name__)


def execute_task_driven_loop(self, req: dict, stream_callback=None):
    """Execute a task-driven autonomous loop with 3 phases.
    
    Args:
        self: SigmaAPIHandler instance
        req: Request dict
        stream_callback: SSE callback function
    """
    session_id = req.get("session_id", "")
    if not session_id:
        return {"error": "session_id mancante"}, 400
    
    goal = req.get("message", "").strip()
    if not goal:
        return {"error": "Obiettivo mancante"}, 400
    
    bot_name = req.get("bot_name", "SigmaBot")
    model_override = req.get("model", "")
    manifesto_path = req.get("manifesto_path", "")
    
    ai_cfg = load_ai_config()
    model = model_override or ai_cfg.get("model", "llama3.2")
    provider = ai_cfg.get("active_provider", "ollama")
    providers_config = ai_cfg.get("providers", {})
    active_prov_cfg = providers_config.get(provider, {})
    endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
    api_url = active_prov_cfg.get("api_url", "")
    api_key = active_prov_cfg.get("api_key", "")
    temperature = active_prov_cfg.get("temperature", 0.7)
    max_tokens = active_prov_cfg.get("max_tokens", 4096)
    top_p = active_prov_cfg.get("top_p", 0.9)
    request_timeout = active_prov_cfg.get("timeout", 300)
    
    detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
    if detected_prov:
        provider = detected_provider
        if detected_prov.get("endpoint"):
            endpoint = detected_prov["endpoint"]
        if detected_prov.get("api_url"):
            api_url = detected_prov["api_url"]
        if detected_prov.get("api_key"):
            api_key = detected_prov["api_key"]
    
    from core.chat_handler import _get_manifesto_content, _get_time_context
    
    time_ctx = _get_time_context()
    fs_context = _build_loop_filesystem_context()
    system_prompt = _get_manifesto_content(manifesto_path or "")
    if not system_prompt.strip():
        system_prompt = "Sei Sigma AI Studio, un assistente AI specializzato in Sigma Studio."
    
    if stream_callback:
        stream_callback({"type": "phase", "phase": "plan", "message": "Avvio fase di pianificazione..."})
    
    plan_prompt = f"""{system_prompt}

## OBBLETTIVO
{goal}

## STRUTTURA PROGETTO
{fs_context}

## AZIONE RICHIESTA
Crea una serie di task strutturati in tasks.json per raggiungere l'obbiettivo sopra.

## REGOLE PER OGNI TASK
- "titolo": DESCRITTIVO e specifico. MAI "Nuovo task". Es: "Analizzare distribuzione Mod 6"
- "descrizione": ALMENO una frase che spiega cosa fare e perché
- "moduli": array di moduli coinvolti, es: ["01", "02"] o [] se generico
- "priorita": "critica"|"alta"|"media"|"bassa"

## FORMATO RISPOSTA
Rispondi SOLO con JSON:
{{"response": "...", "tasks": [
  {{"titolo": "...", "descrizione": "...", "moduli": [...], "priorita": "..."}}
]}}
"""
    
    plan_messages = [
        {"role": "system", "content": plan_prompt},
        {"role": "user", "content": f"Pianifica i task necessari per: {goal}\n\nOra: {time_ctx}"}
    ]
    
    plan_response, plan_thinking, plan_error = call_ai_model(
        plan_messages, ai_cfg, model, provider, endpoint, api_url, api_key,
        temperature, max_tokens, top_p, request_timeout
    )
    
    if plan_error:
        return {"error": f"Errore pianificazione: {plan_error}"}, 500
    
    plan_json = _extract_json_from_response(plan_response)
    created_tasks = []
    
    if plan_json:
        try:
            parsed = json.loads(plan_json.group())
            tasks_from_ai = parsed.get("tasks", [])
            
            tasks_list = []
            if os.path.exists('tasks.json'):
                try:
                    with open('tasks.json', 'r', encoding='utf-8') as f:
                        tasks_list = json.load(f)
                except Exception:
                    tasks_list = []
            
            for t in tasks_from_ai:
                titolo = t.get("titolo", "").strip()
                if not titolo or titolo.lower() in ("nuovo task", "task", ""):
                    continue
                descrizione = t.get("descrizione", f"Task pianificato per: {goal[:100]}")
                priorita = t.get("priorita", "media")
                if priorita not in ("critica", "alta", "media", "bassa"):
                    priorita = "media"
                moduli = t.get("moduli", []) if isinstance(t.get("moduli"), list) else []
                
                new_task = {
                    "titolo": titolo,
                    "descrizione": descrizione,
                    "status": "todo",
                    "priorita": priorita,
                    "moduli": moduli,
                    "id": int(datetime.datetime.now().timestamp() * 1000) + len(tasks_list),
                    "notifiche": [{
                        "da": bot_name,
                        "messaggio": f"Task pianificato da Loop: {titolo}",
                        "timestamp": datetime.datetime.now().isoformat()
                    }]
                }
                tasks_list.append(new_task)
                created_tasks.append(new_task)
            
            with open('tasks.json', 'w', encoding='utf-8') as f:
                json.dump(tasks_list, f, indent=4)
        except json.JSONDecodeError:
            pass
    
    if not created_tasks:
        return {"error": "Nessun task valido creato dall'AI"}, 500
    
    if stream_callback:
        stream_callback({
            "type": "plan_complete",
            "tasks_created": len(created_tasks),
            "tasks": [t["titolo"] for t in created_tasks],
            "message": f"Creati {len(created_tasks)} task"
        })
    
    execution_log = []
    completed_tasks = []
    failed_tasks = []
    all_actions_log = []
    
    for task_idx, task in enumerate(created_tasks):
        if stream_callback:
            stream_callback({
                "type": "task_start",
                "task_idx": task_idx + 1,
                "total_tasks": len(created_tasks),
                "task_title": task["titolo"],
                "message": f"Esecuzione task {task_idx + 1}/{len(created_tasks)}: {task['titolo']}"
            })
        
        try:
            if os.path.exists('tasks.json'):
                with open('tasks.json', 'r', encoding='utf-8') as f:
                    all_tasks = json.load(f)
                for t in all_tasks:
                    if t.get("id") == task["id"]:
                        t["status"] = "in_corso"
                        t.setdefault("notifiche", []).append({
                            "da": bot_name,
                            "messaggio": f"Iniziata esecuzione task: {task['titolo']}",
                            "timestamp": datetime.datetime.now().isoformat()
                        })
                        break
                with open('tasks.json', 'w', encoding='utf-8') as f:
                    json.dump(all_tasks, f, indent=4)
        except Exception:
            pass
        
        execute_prompt = f"""{system_prompt}

## OBBLETTIVO GENERALE
{goal}

## TASK DA ESEGUIRE
Titolo: {task['titolo']}
Descrizione: {task['descrizione']}
Priorità: {task['priorita']}
Moduli: {task.get('moduli', [])}

## STRUTTURA PROGETTO
{fs_context}

## 🛑 REGOLA PIÙ IMPORTANTE — DEVI RISPONDERE SOLO CON JSON VALIDO
Non scrivere NIENTE fuori dal JSON. Non usare <thinking>, non spiegare, non commentare.
SOLO un oggetto JSON valido in una sola riga o multilinea.

## AZIONI DISPONIBILI (usa SOLO questi tipi)
- create_module: {{"type": "create_module", "topic": "...", "number": "NN", "name": "..."}}
- create_file: {{"type": "create_file", "path": "data/...", "content": "..."}}
- edit_file: {{"type": "edit_file", "path": "data/...", "content": "...", "search": "..."}}
- run_test: {{"type": "run_test", "path": "data/.../test/...py"}}
- update_task: {{"type": "update_task", "titolo": "...", "status": "done", "notifica": "..."}}

## REGOLE — STRUTTURA MODULARE OBBLIGATORIA (WHITELIST)
1. Crea file DENTRO i moduli: data/<topic>/<NN_modulo>/<sezione>/<file>
2. WHITELIST — Le UNICHE sezioni permesse dentro un modulo sono:
   ✅ teoria/  ✅ test/  ✅ viz/  ✅ docs/  ✅ whitepapers/
3. Ogni create_file DEVE avere "path" e "content" completi
4. Esegui test per verificare se possibile
5. Alla fine usa update_task per marcare completato

## FORMATO OBBLIGATORIO
{{"response": "descrizione", "actions": [AZIONI]}}
"""
        
        exec_messages = [
            {"role": "system", "content": execute_prompt},
            {"role": "user", "content": f"Esegui il task: {task['titolo']}\n\n{task['descrizione']}\n\nOra: {time_ctx}"}
        ]
        
        exec_response, exec_thinking, exec_error = call_ai_model(
            exec_messages, ai_cfg, model, provider, endpoint, api_url, api_key,
            0.3, max_tokens * 2, top_p, request_timeout
        )
        
        task_actions_log = []
        if exec_error:
            failed_tasks.append({"titolo": task["titolo"], "error": exec_error})
        else:
            exec_json = _extract_json_from_response(exec_response)
            if exec_json:
                try:
                    parsed = json.loads(exec_json.group())
                    actions = parsed.get("actions", [])
                    if actions:
                        task_actions_log = execute_ai_actions(self, actions, bot_name)
                        all_actions_log.extend(task_actions_log)
                except json.JSONDecodeError:
                    pass
        
        try:
            if os.path.exists('tasks.json'):
                with open('tasks.json', 'r', encoding='utf-8') as f:
                    all_tasks = json.load(f)
                for t in all_tasks:
                    if t.get("id") == task["id"]:
                        t["status"] = "done"
                        t.setdefault("notifiche", []).append({
                            "da": bot_name,
                            "messaggio": f"Task completato dal Loop. Azioni: {sum(1 for a in task_actions_log if a.get('success'))}/{len(task_actions_log)} riuscite.",
                            "timestamp": datetime.datetime.now().isoformat()
                        })
                        break
                with open('tasks.json', 'w', encoding='utf-8') as f:
                    json.dump(all_tasks, f, indent=4)
        except Exception:
            pass
        
        completed_tasks.append(task["titolo"])
        execution_log.append({
            "task": task["titolo"],
            "actions_log": task_actions_log,
            "error": exec_error
        })
        
        if stream_callback:
            stream_callback({
                "type": "task_complete",
                "task_idx": task_idx + 1,
                "total_tasks": len(created_tasks),
                "task_title": task["titolo"],
                "actions_count": len(task_actions_log),
                "success_count": sum(1 for a in task_actions_log if a.get("success")),
                "actions_log": task_actions_log,
                "message": f"Task completato: {task['titolo']} ({sum(1 for a in task_actions_log if a.get('success'))}/{len(task_actions_log)} azioni)"
            })
    
    all_files_created = [a for a in all_actions_log if a.get("type") == "create_file" and a.get("success")]
    all_files_edited = [a for a in all_actions_log if a.get("type") == "edit_file" and a.get("success")]
    all_tests_run = [a for a in all_actions_log if a.get("type") == "run_test"]
    tests_passed = sum(1 for a in all_tests_run if a.get("success"))
    
    report = {
        "session_id": session_id,
        "goal": goal,
        "phase": "completed",
        "tasks_created": len(created_tasks),
        "tasks_completed": len(completed_tasks),
        "tasks_failed": len(failed_tasks),
        "tasks": [t["titolo"] for t in created_tasks],
        "total_actions": len(all_actions_log),
        "files_created": len(all_files_created),
        "files_modified": len(all_files_edited),
        "tests_run": len(all_tests_run),
        "tests_passed": tests_passed,
        "execution_log": execution_log,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    if stream_callback:
        stream_callback({
            "type": "done",
            "summary": {
                "tasks_created": len(created_tasks),
                "tasks_completed": len(completed_tasks),
                "files_created": len(all_files_created),
                "files_modified": len(all_files_edited),
                "tests_run": len(all_tests_run),
                "tests_passed": tests_passed,
            },
            "report": report
        })
    
    return report


def handle_chat_loop(self):
    """POST /api/chat/loop — Task-driven loop execution with SSE streaming."""
    try:
        req = self.read_json_body()
        use_stream = req.get("stream", True)
        
        if use_stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            def _sse_callback(event):
                try:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()
                except Exception:
                    pass
            
            try:
                result = execute_task_driven_loop(self, req, stream_callback=_sse_callback)
                if isinstance(result, tuple):
                    _sse_callback({"type": "error", "error": result[0].get("error", "Unknown error")})
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as e:
                try:
                    self.wfile.write(f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except Exception:
                    pass
        else:
            result = execute_task_driven_loop(self, req)
            if isinstance(result, tuple):
                return self.send_json_response(result[0], result[1])
            self.send_json_response(result)
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except Exception:
            pass
