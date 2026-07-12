# ==============================================================================
# core/loop_handler.py — Autonomous Task-Driven Loop Mode v3
# Sigma Studio v7 — Loop orchestrato che: pianifica task → esegue uno per uno
# con notifiche → verifica → report finale.
# Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
# ==============================================================================
"""Autonomous task-driven loop with planning, sequential task execution,
verification, notifications, and final report."""

import os
import json
import datetime
import re
from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions, _add_action_notifications


# --- Filesystem context ---

def _build_loop_filesystem_context():
    """Build concise filesystem context for the loop."""
    lines = []
    data_dir = 'data'
    if not os.path.isdir(data_dir):
        return ""
    for topic in sorted(os.listdir(data_dir)):
        topic_path = os.path.join(data_dir, topic)
        if not os.path.isdir(topic_path):
            continue
        lines.append(f"\n📂 {topic}/")
        for mod in sorted(os.listdir(topic_path)):
            mod_path = os.path.join(topic_path, mod)
            if not os.path.isdir(mod_path) or not (mod[:2].isdigit()):
                continue
            mod_label = mod[3:] if len(mod) > 3 else mod
            lines.append(f"  📁 {mod} ({mod_label})")
            for section in ['teoria', 'test', 'viz', 'docs']:
                sec_path = os.path.join(mod_path, section)
                if os.path.isdir(sec_path):
                    files = sorted(os.listdir(sec_path))
                    if files:
                        lines.append(f"    {section}/")
                        for f_name in files:
                            f_path = os.path.join(sec_path, f_name).replace('\\', '/')
                            f_size = os.path.getsize(f_path) if os.path.isfile(f_path) else 0
                            lines.append(f"      {f_name} ({f_size}B)")
    return '\n'.join(lines)


def _get_tasks_context():
    """Get tasks.json as formatted string for context."""
    try:
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            return json.dumps(tasks, indent=2)
    except:
        pass
    return "[]"


def _extract_json_from_response(content):
    """Robust JSON extractor with balanced brace matcher."""
    if not content or not isinstance(content, str):
        return None
    idx = content.find('{')
    while idx >= 0:
        depth = 0
        start = idx
        for i in range(idx, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = content[start:i+1]
                    if '"response"' in candidate:
                        try:
                            json.loads(candidate)
                            class FakeMatch:
                                def group(self, n=0):
                                    return candidate
                            return FakeMatch()
                        except json.JSONDecodeError:
                            pass
                    break
            elif content[i] in ('"', "'"):
                quote = content[i]
                j = i + 1
                while j < len(content) and content[j] != quote:
                    if content[j] == '\\':
                        j += 1
                    j += 1
                i = j
        idx = content.find('{', idx + 1)
    return re.search(r'\{[\s\S]*"response"[\s\S]*("actions"|"tasks"|"self_reflection")[\s\S]*\}', content)


# ==============================================================================
# TASK-DRIVEN LOOP — 3 Fasi
# ==============================================================================

def execute_task_driven_loop(self, req, stream_callback=None):
    """Execute a task-driven autonomous loop with 3 phases.
    
    Phase 1 — PLAN: Given a goal, AI creates tasks in tasks.json
    Phase 2 — EXECUTE: For each pending task, execute and verify
    Phase 3 — REPORT: Final summary
    
    Each action generates notifications (Principio Sigma).
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
    uploaded_files = req.get("uploaded_files", [])
    web_search = req.get("web_search", False)
    
    # --- Load config ---
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
    
    # Resolve provider for the model
    detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
    if detected_prov:
        provider = detected_provider
        if detected_prov.get("endpoint"):
            endpoint = detected_prov["endpoint"]
        if detected_prov.get("api_url"):
            api_url = detected_prov["api_url"]
        if detected_prov.get("api_key"):
            api_key = detected_prov["api_key"]
    
    # --- Import helpers from chat_handler ---
    from core.chat_handler import _get_manifesto_content, _get_time_context
    
    time_ctx = _get_time_context()
    fs_context = _build_loop_filesystem_context()
    system_prompt = _get_manifesto_content(manifesto_path or "")
    if not system_prompt.strip():
        system_prompt = "Sei Sigma AI Studio, un assistente AI specializzato in Sigma Studio."
    
    # ======================================================================
    # PHASE 1 — PLAN: Crea task in tasks.json
    # ======================================================================
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
  {{"titolo": "...", "descrizione": "...", "moduli": [...], "priorita": "..."}},
  ...
]}}

## Esempio di buona risposta:
{{"response": "Ho analizzato l'obbiettivo e creato 3 task.", "tasks": [
  {{"titolo": "Analizzare distribuzione dati", "descrizione": "Analizzare i dati del topic attivo per identificare pattern nella distribuzione", "moduli": ["01"], "priorita": "alta"}},
  {{"titolo": "Creare visualizzazione heatmap", "descrizione": "Generare una heatmap interattiva per visualizzare i dati", "moduli": ["01"], "priorita": "media"}}
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
    
    # Parse tasks from planning response
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
                except:
                    tasks_list = []
            
            for t in tasks_from_ai:
                titolo = t.get("titolo", "").strip()
                if not titolo or titolo.lower() in ("nuovo task", "task", ""):
                    continue  # skip invalid tasks
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
    
    # ======================================================================
    # PHASE 2 — EXECUTE: Esegui task uno per volta
    # ======================================================================
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
        
        # Set task as in_corso
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
        except:
            pass
        
        # Build execute prompt for this specific task — FORMATO JSON STRETTO
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
           ❌ QUALSIASI altra cartella è automaticamente VIETATA
        3. NON creare MAI file direttamente nella root del modulo (es: data/topic/01_modulo/file.py)
        4. NON creare MAI file direttamente nella root del topic (es: data/topic/report.md)
        5. Ogni create_file DEVE avere "path" e "content" completi
        6. Esegui test per verificare se possibile
        7. Alla fine usa update_task per marcare completato
        
        ## ESEMPIO SCORRETTO (NON FARE MAI):
        {{"type": "create_file", "path": "data/esempio/01_modulo/analisi/file.md", "content": "..."}} ❌
        {{"type": "create_file", "path": "data/esempio/01_modulo/file.py", "content": "..."}} ❌
        {{"type": "create_file", "path": "data/matematica/report.md", "content": "..."}} ❌
        
        ## ESEMPIO DI RISPOSTA CORRETTA
        {{"response": "Creo i file necessari per il task", "actions": [
          {{"type": "create_file", "path": "data/esempio/01_modulo/teoria/analisi.md", "content": "# Analisi\\n\\nTesto..."}},
          {{"type": "run_test", "path": "data/esempio/01_modulo/test/verifica.py"}},
          {{"type": "update_task", "titolo": "{task['titolo']}", "status": "done", "notifica": "Task completato con successo"}}
        ]}}
        
        ## FORMATO OBBLIGATORIO
        {{"response": "descrizione", "actions": [AZIONI]}}
"""
        
        exec_messages = [
            {"role": "system", "content": execute_prompt},
            {"role": "user", "content": f"Esegui il task: {task['titolo']}\n\n{task['descrizione']}\n\nOra: {time_ctx}"}
        ]
        
        print(f"[LOOP_DEBUG] Calling AI for task: {task['titolo']}", flush=True)
        exec_response, exec_thinking, exec_error = call_ai_model(
            exec_messages, ai_cfg, model, provider, endpoint, api_url, api_key,
            0.3,  # Lower temperature for code execution
            max_tokens * 2, top_p, request_timeout  # double max_tokens for code generation
        )
        print(f"[LOOP_DEBUG] AI response (first 500 chars): {(exec_response or '')[:500]}", flush=True)
        
        task_actions_log = []
        task_completed = False
        
        if exec_error:
            failed_tasks.append({"titolo": task["titolo"], "error": exec_error})
        else:
            # Parse and execute actions
            exec_json = _extract_json_from_response(exec_response)
            if exec_json:
                try:
                    parsed = json.loads(exec_json.group())
                    actions = parsed.get("actions", [])
                    
                    if actions:
                        task_actions_log = execute_ai_actions(self, actions, bot_name)
                        all_actions_log.extend(task_actions_log)
                        
                        # Check if any complete_task or update_task was successful
                        for a in task_actions_log:
                            if a.get("success"):
                                if a.get("type") in ("complete_task", "update_task"):
                                    task_completed = True
                except json.JSONDecodeError:
                    pass
        
        # Force task completion (auto-mark as done)
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
        except:
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
    
    # ======================================================================
    # PHASE 3 — REPORT: Riepilogo finale
    # ======================================================================
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


# ==============================================================================
# API Handler for task-driven loop
# ==============================================================================

def handle_chat_loop(self):
    """POST /api/chat/loop — Task-driven loop execution with SSE streaming."""
    try:
        req = self.read_json_body()
        use_stream = req.get("stream", True)
        
        if use_stream:
            # SSE streaming mode
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
            # Non-streaming mode
            result = execute_task_driven_loop(self, req)
            if isinstance(result, tuple):
                return self.send_json_response(result[0], result[1])
            self.send_json_response(result)
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except Exception:
            pass