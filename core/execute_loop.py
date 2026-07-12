# ==============================================================================
# core/execute_loop.py — Continuous Iterative Feedback Loop (Cline-style)
# Sigma Studio v7 — Esegue azioni in loop: AI → azioni → risultati → AI → ...
# Fix: quando l'AI risponde in testo normale, mostra il testo ed esce dal loop
# ==============================================================================
import os, json, datetime, re
from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.chat_handler import _get_manifesto_content, _get_time_context, _build_filesystem_context, _extract_json_from_response, _collect_context_files

_VALID_ACTION_TYPES = frozenset([
    'create_file', 'edit_file', 'rename_file', 'delete_file',
    'create_module', 'run_test', 'update_task', 'read_file',
    'send_notification', 'run_terminal',
])
_WRITE_ACTIONS = frozenset([
    'create_file', 'edit_file', 'rename_file', 'delete_file', 'create_module',
])


def _validate_action_types(actions):
    valid, invalid = [], []
    for a in actions:
        # Accept both "type" and "action" as the action type field (LLMs often use "action" instead of "type")
        action_type = a.get("type") or a.get("action")
        if not action_type:
            invalid.append({"type": "MISSING", "path": a.get("path", ""), "reason": "Manca 'type' o 'action'!"})
        elif action_type in _VALID_ACTION_TYPES:
            # Normalize to "type" if it was "action"
            if "action" in a and "type" not in a:
                a["type"] = a["action"]
            valid.append(a)
        else:
            invalid.append({"type": action_type, "path": a.get("path", ""), "reason": f"Tipo sconosciuto: {action_type}"})
    return valid, invalid

def _completion_keywords(text):
    """Check if natural language text indicates completion."""
    if not text: return False
    t = text.lower()
    signals = [
        "completato", "finito", "done", "concluso", "terminato", 
        "ho finito", "è tutto", "non ho altro", "nessuna azione",
        "task completato", "lavoro completato", "fine della spiegazione",
        "ho concluso", "risposta finale", "knowledge transfer",
        "blocco conversazionale", "system core lockdown", "protocollo",
        "spiegazione terminata", "fase teorica è conclusa",
    ]
    return any(s in t for s in signals)

def execute_feedback_loop(self, req, stream_callback=None):
    goal = req.get("message", "").strip()
    if not goal: return {"error": "Messaggio vuoto"}, 400

    bot_name = req.get("bot_name", "SigmaBot")
    manifesto_path = req.get("manifesto_path", "")
    model_override = req.get("model", "")
    context_files = req.get("context", {}).get("open_files", [])
    history = req.get("context", {}).get("history", [])
    uploaded_files = req.get("uploaded_files", [])
    web_search = req.get("web_search", False)
    max_iterations = min(int(req.get("max_iterations", 100)), 1000)
    if max_iterations < 1: max_iterations = 1

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

    dp, dpv = resolve_provider_config(ai_cfg, model)
    if dpv:
        provider = dp
        if dpv.get("endpoint"): endpoint = dpv["endpoint"]
        if dpv.get("api_url"): api_url = dpv["api_url"]
        if dpv.get("api_key"): api_key = dpv["api_key"]
    if req.get("model_provider"): provider = req.get("model_provider")
    if req.get("model_endpoint"): endpoint = req.get("model_endpoint")
    if req.get("model_api_url"): api_url = req.get("model_api_url")
    t = req.get("timeout", 0)
    if t and t > 0: request_timeout = int(t)

    time_ctx = _get_time_context()
    fs_context = _build_filesystem_context()
    system_prompt = _get_manifesto_content(manifesto_path or "")
    if not system_prompt.strip():
        system_prompt = "Sei Sigma AI Studio. Rispondi in italiano."
    context_str = _collect_context_files(self, context_files)

    tasks_context = ""
    if os.path.exists('tasks.json'):
        try:
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks_context = json.dumps(json.load(f), indent=2)
        except: tasks_context = "[]"

    full_system = system_prompt + "\n\n" + time_ctx
    if fs_context:
        from core.chat_handler import _build_filesystem_context as bfc
        full_system += "\n\nStruttura:\n" + bfc()[:3000]
    if tasks_context:
        full_system += "\n\nTasks:\n" + tasks_context

    loop_prompt = f"""
## LOOP — Leggi → Rifletti → Esegui

Obiettivo: {goal}

### REGOLE
1. Rispondi SEMPRE con JSON: {{"response": "...", "actions": [...]}}
2. "response" = spiegazione in italiano (sarà mostrata all'utente)
3. Dopo le azioni, riceverai i risultati. Analizza e decidi se continuare.
4. Per completare: {{"done": true, "response": "riepilogo", "summary": {{...}}}}

### AZIONI DISPONIBILI (campi obbligatori):
- create_module: {{"type": "create_module", "topic": "nome_topic", "number": "01", "name": "nome_modulo"}}
  Crea un modulo con le 5 sezioni standard (teoria, test, viz, docs, whitepapers)
- create_file: {{"type": "create_file", "path": "data/topic/NN_modulo/sezione/file", "content": "..."}}
- edit_file: {{"type": "edit_file", "path": "...", "content": "..."}} (cerca e sostituisci)
- read_file: {{"type": "read_file", "path": "..."}}
- delete_file: {{"type": "delete_file", "path": "..."}}
- rename_file: {{"type": "rename_file", "old_path": "sorgente", "new_path": "destinazione"}} (sposta file)
- run_test: {{"type": "run_test", "path": "..."}}
- update_task: {{"type": "update_task", "task_id": "...", "status": "..."}}
- send_notification: {{"type": "send_notification", "message": "..."}}
"""
    full_system += loop_prompt

    messages = [{"role": "system", "content": full_system}]
    for h in history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": goal})

    all_actions_log = []
    current_iteration = 0
    completed = False
    final_response = ""

    callback = stream_callback
    if callback:
        callback({"type": "execute_start", "message": f"Avvio con {model}", "max_iterations": max_iterations, "goal": goal})

    while current_iteration < max_iterations and not completed:
        current_iteration += 1
        if callback:
            callback({"type": "iteration_start", "iteration": current_iteration, "max_iterations": max_iterations})

        response, thinking, error = call_ai_model(messages, ai_cfg, model, provider, endpoint, api_url, api_key, temperature, max_tokens * 2, top_p, request_timeout)

        if error:
            if callback:
                callback({"type": "error", "iteration": current_iteration, "error": f"Errore AI: {error}"})
            break

        if not response:
            if callback:
                callback({"type": "error", "iteration": current_iteration, "error": "Risposta AI vuota"})
            break

        # Try to extract JSON
        json_match = _extract_json_from_response(response)
        parsed = None
        ai_response_text = ""
        actions = []
        is_done = False

        if json_match:
            try:
                parsed = json.loads(json_match.group())
                ai_response_text = parsed.get("response", response[:500])
                actions = parsed.get("actions", [])
                is_done = parsed.get("done", False)
            except json.JSONDecodeError:
                parsed = None

        if parsed is None:
            # Natural language response — show it to user and detect completion
            ai_response_text = response[:2000]

            # Send as chat message
            if callback:
                callback({
                    "type": "iteration_response",
                    "iteration": current_iteration,
                    "response": ai_response_text,
                    "thinking": thinking,
                })

            # Check if AI is done based on keywords
            is_done = _completion_keywords(response)

            if is_done:
                completed = True
                final_response = ai_response_text
                if callback:
                    callback({
                        "type": "execute_done",
                        "iteration": current_iteration,
                        "total_iterations": current_iteration,
                        "response": final_response,
                        "message": f"✅ Completato in {current_iteration} iterazioni"
                    })
                break
            else:
                # Not a JSON, not done — still show it and continue
                messages.append({"role": "assistant", "content": response})
                # Tell AI to produce JSON next time
                messages.append({
                    "role": "system", 
                    "content": f"⚠️ **Iterazione {current_iteration}:** Hai risposto in testo normale. Per favore rispondi con JSON: {{'response': '...', 'actions': [...]}} o {{'done': true, 'response': '...'}} se hai completato."
                })
                continue

        # ==== JSON Mode ====
        messages.append({"role": "assistant", "content": response})

        # Show AI response
        if callback and ai_response_text:
            callback({
                "type": "iteration_response",
                "iteration": current_iteration,
                "response": ai_response_text,
                "thinking": thinking,
            })

        if not actions and not is_done:
            lower = ai_response_text.lower()
            if any(w in lower for w in ["completato", "finito", "done", "concluso", "terminato"]):
                is_done = True

        if is_done:
            if len(all_actions_log) == 0 and current_iteration <= 2:
                messages.append({"role": "system", "content": "⚠️ done:true ma 0 azioni. Esegui azioni prima."})
                if callback:
                    callback({"type": "error", "iteration": current_iteration, "error": "Falso completamento"})
                continue
            completed = True
            final_response = ai_response_text
            if callback:
                callback({
                    "type": "execute_done",
                    "iteration": current_iteration,
                    "total_iterations": current_iteration,
                    "response": final_response,
                    "message": f"✅ Completato in {current_iteration} iterazioni"
                })
            break

        valid_actions, invalid_actions = _validate_action_types(actions)

        if not valid_actions:
            fb = f"⚠️ {len(actions)} azioni invalide. Usa tipi validi."
            messages.append({"role": "system", "content": fb})
            if callback:
                callback({"type": "iteration_validation_error", "iteration": current_iteration, "actions_raw": actions})
            continue

        # Execute actions
        if callback:
            callback({"type": "iteration_actions", "iteration": current_iteration, "actions_count": len(valid_actions), "actions": [a.get("type") for a in valid_actions]})

        iteration_log = execute_ai_actions(self, valid_actions, bot_name)
        for inv in invalid_actions:
            iteration_log.append({"type": inv["type"], "success": False, "error": inv["reason"]})
        all_actions_log.extend(iteration_log)

        success = sum(1 for a in iteration_log if a.get("success"))
        fail = sum(1 for a in iteration_log if not a.get("success"))

        details = "\n".join(f"  {'✅' if a.get('success') else '❌'} {a.get('type','?')}: {a.get('message',a.get('error',''))}" for a in iteration_log)

        fb = f"📋 **Iterazione {current_iteration}**: {success}/{len(iteration_log)} azioni riuscite\n\nDettaglio:\n{details}"
        messages.append({"role": "system", "content": fb})

        if callback:
            callback({
                "type": "iteration_complete",
                "iteration": current_iteration,
                "success_count": success, "fail_count": fail,
                "actions_log": iteration_log,
                "message": f"Iterazione {current_iteration}: {success}/{len(iteration_log)} ✅"
            })

    if not completed:
        final_response = f"Limite di {max_iterations} iterazioni."
        if callback:
            callback({"type": "execute_timeout", "iteration": current_iteration, "max_iterations": max_iterations})

    if callback:
        callback({"type": "done", "summary": {
            "iterations": current_iteration, "total_actions": len(all_actions_log),
            "successful_actions": sum(1 for a in all_actions_log if a.get("success")),
            "files_created": sum(1 for a in all_actions_log if a.get("type") == "create_file" and a.get("success")),
        }, "actions_log": all_actions_log})

    return {"response": final_response, "actions_log": all_actions_log, "iterations": current_iteration, "completed": completed}


def handle_chat_execute(self):
    try:
        req = self.read_json_body()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def _sse(e):
            try:
                self.wfile.write(f"data: {json.dumps(e)}\n\n".encode())
                self.wfile.flush()
            except: pass

        try:
            r = execute_feedback_loop(self, req, stream_callback=_sse)
            if isinstance(r, tuple) and len(r) == 2:
                _sse({"type": "error", "error": r[0].get("error", "Errore")})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception as e:
            try:
                self.wfile.write(f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except: pass
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except: pass