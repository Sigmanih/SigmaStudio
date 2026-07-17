# ==============================================================================
# core/execute_loop.py — Continuous Iterative Feedback Loop (Cline-style)
# Sigma Studio v7 — Esegue azioni in loop: AI → azioni → risultati → AI → ...
# Fix: quando l'AI risponde in testo normale, mostra il testo ed esce dal loop
# ==============================================================================
import os, json, datetime, re
from core.logger import get_logger
log = get_logger("execute_loop")
from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.chat_handler import _get_manifesto_content, _get_time_context, _build_filesystem_context, _extract_json_from_response, _collect_context_files
from core.chat.prompt_builder import _determine_agent_by_request


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

def _detect_and_add_mentioned_files(goal: str) -> str:
    """Scan the goal for filenames and look up their absolute/relative paths in the project to ease model routing."""
    import re
    # Find words ending with common file extensions
    matches = re.findall(r'\b[a-zA-Z0-9_\-\.]+\.(?:html|js|css|py|md|json)\b', goal)
    if not matches:
        return ""
        
    found_files = []
    for root, dirs, files in os.walk('.'):
        # Ignore system, node_modules, build and brain dirs
        root_norm = root.replace("\\", "/")
        if any(p in root_norm for p in ('node_modules', '.git', 'dist', 'build', '.gemini', 'brain')):
            continue
        for f in files:
            if f in matches:
                full_path = os.path.join(root, f).replace("\\", "/")
                found_files.append(full_path)
                
    if found_files:
        lines = ["\n### FILE RILEVATI NEL PROGETTO CORRISPONDENTI ALLA RICHIESTA:"]
        for ff in found_files:
            lines.append(f"- Percorso reale: {ff} (Usa questo percorso esatto per l'azione read_file o edit_file)")
        return "\n".join(lines)
    return ""


def _should_activate_loop(goal: str, ai_cfg: dict, model_override: str) -> bool:
    """Classify the user's intent to decide whether to activate loop execution or direct text mode."""
    import re
    
    # 1. Immediate Heuristics
    goal_lower = goal.lower().strip()
    
    # Check for operational keywords or file references first
    operational_keywords = [
        "modifica", "sostituisci", "salva", "crea", "scrivi", "cancella", "elimina", 
        "rinomina", "sposta", "esegui", "run", "testa", "test", "correggi", "risolvi",
        "implementa", "aggiungi"
    ]
    has_operation = any(w in goal_lower for w in operational_keywords)
    has_file = any(ext in goal_lower for ext in [".html", ".py", ".js", ".css", ".json", ".txt", "file", "cartella", "modulo"])

    # Saluti e domande semplici su identità (usando regex con word boundary per evitare falsi positivi)
    greetings = ["ciao", "hello", "hi", "buongiorno", "buonasera", "chi sei", "come ti chiami", "come stai"]
    is_greeting = any(re.search(rf"\b{re.escape(w)}\b", goal_lower) for w in greetings)
    
    # Only bypass the loop if it's a pure greeting/identity check with no operational intent
    if is_greeting and not (has_operation or has_file):
        log.info("Heuristic INFO match (greeting/identity): %s", goal[:50])
        return False
        
    # Richieste informative chiare
    informative_keywords = [
        "spiegami", "spiega", "cos'è", "cosa significa", "teoria", "formula", 
        "informazioni", "descrivi", "illustra", "riepilogo", "riassunto"
    ]
    # Exclusion: if message contains write/create keywords, don't bypass even if informative keywords match
    write_keywords = ["scrivi", "crea", "creami", "scrivimi", "crea un file", "scrivi un file", "documento su"]
    has_write_intent = any(w in goal_lower for w in write_keywords)
    if any(w in goal_lower for w in informative_keywords) and not has_write_intent and not any(ext in goal_lower for ext in [".html", ".py", ".js", ".css", ".json", ".txt"]):
        log.info("Heuristic INFO match (conceptual search without file extensions): %s", goal[:50])
        return False

    # 2. Fallback check: if there are no file extensions and no command keywords, it's highly likely informational
    if not has_operation and not has_file:
        log.info("Heuristic INFO match (no operational keywords and no file references): %s", goal[:50])
        return False

    # 3. LLM-based classification as a fallback
    from core.orchestration.agent_config import load_agent_config
    from core.agent_registry import SIGMA_ARCHITECT_ID
    from core.ai_providers import call_ai_model

    # Use default coordinator credentials
    main_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)
        
    system_prompt = """Sei Sigma AI Architect. Analizza la richiesta dell'utente e stabilisci se richiede di EFFETTUARE MODIFICHE (scrivere file, modificare codice, eseguire test, creare moduli, cancellare file, o agire sulla sandbox/sistema) o se è puramente INFORMATIVA/TEORICA (domande matematiche, richieste di spiegazione di formule, spiegazione del codice, saluti o riepiloghi).
    
Rispondi esclusivamente con:
- LOOP: se l'utente chiede modifiche fisiche a file o azioni operative.
- INFO: se l'utente fa una domanda teorica, chiede spiegazioni o informazioni.

Scrivi SOLO LOOP o INFO. Nessun altro commento.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Richiesta: {goal}"}
    ]
    try:
        # Aumentato max_tokens a 1000 per supportare modelli con ragionamento/thinking (come DeepSeek)
        response, _, error = call_ai_model(
            messages, ai_cfg, main_model, provider, endpoint, api_url, api_key,
            0.1, 1000, top_p, timeout
        )
        if not error and response:
            res = response.strip().upper()
            if "INFO" in res:
                log.info("Direct INFO response classified by LLM for goal: %s", goal[:50])
                return False
            elif "LOOP" in res:
                log.info("LLM classified request as LOOP for goal: %s", goal[:50])
                return True
    except Exception as e:
        log.error("Error in LLM loop classification: %s", e)
        
    # Default fallback: if LLM call fails, use the structural heuristics
    if has_operation or has_file:
        return True
    return False


def _extract_partial_string_field(field_name: str, accumulated: str) -> str:
    import re
    # Cerca "field_name": "..." o "field_name": '...' o parziale
    match = re.search(f'"{field_name}"\\s*:\\s*"(.*?)"', accumulated, re.DOTALL)
    if match:
        return match.group(1).replace('\\"', '"').replace('\\n', '\n')
    
    # Esempio parziale non ancora chiuso
    match_open = re.search(f'"{field_name}"\\s*:\\s*"(.*)', accumulated, re.DOTALL)
    if match_open:
        text = match_open.group(1)
        # Tronchiamo all'eventuale virgoletta di chiusura non preceduta da escape
        parts = re.split(r'(?<!\\)"', text)
        if parts:
            text = parts[0]
        return text.replace('\\"', '"').replace('\\n', '\n')
    return ""


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

    # Automatic Agent Routing in Loop Mode
    if not manifesto_path or manifesto_path in ("auto", "auto.md", "manifesti/auto.md", "MANIFESTO.md"):
        if manifesto_path in ("auto", "auto.md", "manifesti/auto.md"):
            manifesto_path = _determine_agent_by_request(goal, ai_cfg, model)
        else:
            from core.chat.prompt_builder import _resolve_manifesto_for_model
            manifesto_path = _resolve_manifesto_for_model(model)
            
    if not manifesto_path:
        manifesto_path = "MANIFESTO.md"

    # Force override bot_name based on chosen agent for active routing accuracy
    agent_id_match = os.path.splitext(os.path.basename(manifesto_path))[0]
    from core.agent_registry import get_agent
    ag = get_agent(agent_id_match)
    if ag:
        bot_name = ag.get("name", bot_name)
    elif agent_id_match == "sigma_architect":
        bot_name = "Sigma AI Architect"

    def send_event(e):
        if stream_callback:
            # Inject active agent metadata
            e["agent_id"] = agent_id_match
            e["agent_name"] = bot_name
            stream_callback(e)

    callback = send_event

    time_ctx = _get_time_context()
    fs_context = _build_filesystem_context()
    system_prompt = _get_manifesto_content(manifesto_path)
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

    # Add auto-detected files matching the user's prompt
    detected_files_context = _detect_and_add_mentioned_files(goal)
    if detected_files_context:
        full_system += "\n" + detected_files_context

    loop_prompt = f"""
## MODALITÀ FEEDBACK LOOP ITERATIVO (AI -> Azioni -> Risultati)
Obiettivo dell'utente: {goal}

### REGOLE STRINGENTI PER LA RISPOSTA:
1. Devi rispondere **SEMPRE ed ESCLUSIVAMENTE** con un blocco JSON valido che segue questa struttura:
   {{
     "response": "Spiegazione o risposta in italiano per l'utente",
     "actions": [ ... lista di azioni da eseguire ... ]
   }}
2. Se non devi eseguire alcuna azione o hai completato l'obiettivo, rispondi con "done": true:
   {{
     "done": true,
     "response": "Ho completato tutte le modifiche richieste con successo.",
     "summary": {{
       "descrizione": "Matrice griglia semplificata correggendo lo stile CSS",
       "file_modificati": ["..."]
     }}
   }}

### ESEMPI DI RISPOSTA:

* Esempio 1: Se devi LEGGERE un file per analizzarlo:
{{
  "response": "Sto leggendo il file 01_S_analyzer.html per identificare gli stili della griglia.",
  "actions": [
    {{
      "type": "read_file",
      "path": "sigma_studio/src/components/Viz/01_S_analyzer.html"
    }}
  ]
}}

* Esempio 2: Se devi MODIFICARE lo stile di un file:
{{
  "response": "Ho corretto lo stile della griglia all'interno del file visualizzatore.",
  "actions": [
    {{
      "type": "edit_file",
      "path": "sigma_studio/src/components/Viz/01_S_analyzer.html",
      "content": "..."
    }}
  ]
}}

### AZIONI DISPONIBILI (Tutte le azioni richiedono il campo "type"):
- read_file: {{"type": "read_file", "path": "percorso/file.estensione"}} (Legge il contenuto di un file)
- edit_file: {{"type": "edit_file", "path": "percorso/file.estensione", "content": "nuovo contenuto completo o modifiche"}} (Modifica o riscrive un file)
- create_file: {{"type": "create_file", "path": "percorso/file.estensione", "content": "contenuto"}} (Crea un nuovo file)
- create_module: {{"type": "create_module", "topic": "nome_topic", "number": "01", "name": "nome_modulo"}} (Crea la struttura standard di un modulo)
- delete_file: {{"type": "delete_file", "path": "..."}} (Cancella un file)
- rename_file: {{"type": "rename_file", "old_path": "...", "new_path": "..."}} (Sposta/rinomina un file)
- run_test: {{"type": "run_test", "path": "..."}} (Esegue un file di test)
- update_task: {{"type": "update_task", "task_id": "...", "status": "..."}} (Aggiorna un task)
- send_notification: {{"type": "send_notification", "message": "..."}} (Invia notifica all'utente)

IMPORTANTE: Rispondi esclusivamente in formato JSON. Nessun testo prima del JSON, nessun testo dopo.
"""
    full_system += loop_prompt

    messages = [{"role": "system", "content": full_system}]
    for h in history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": goal})

    # Intent classification: check if we should run the iterative feedback loop or bypass to a direct text reply.
    if not _should_activate_loop(goal, ai_cfg, model):
        log.info("Bypassing loop execution for simple info request: %s", goal[:50])
        info_system = system_prompt + "\n\n" + time_ctx
        info_system += "\n\nIMPORTANTE: Rispondi in testo normale (Natural Language), NON usare formato JSON, non usare chiavi come 'response' o 'actions', e non usare parentesi graffe. Scrivi una risposta discorsiva diretta in italiano."
        
        if context_str:
            info_system += "\n\nFile di contesto aperti:\n" + context_str
            
        messages_info = [{"role": "system", "content": info_system}]
        for h in history[-10:]:
            messages_info.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages_info.append({"role": "user", "content": goal})
        
        if callback:
            callback({"type": "execute_start", "message": f"Avvio risposta diretta con {model}", "max_iterations": 1, "goal": goal})
            callback({"type": "iteration_start", "iteration": 1, "max_iterations": 1})
            
        from core.ai_providers import call_ai_model_stream
        
        accumulated_response = ""
        accumulated_thinking = ""
        is_json_detected = False
        
        stream_generator = call_ai_model_stream(
            messages_info, ai_cfg, model, provider, endpoint, api_url, api_key,
            temperature, max_tokens, top_p, request_timeout
        )
        
        for chunk in stream_generator:
            if chunk.get("error"):
                err_msg = chunk.get("message", "Errore sconosciuto")
                if callback:
                    callback({"type": "error", "iteration": 1, "error": f"Errore AI: {err_msg}"})
                return {"response": f"Errore AI: {err_msg}", "actions_log": [], "iterations": 1, "completed": False}
                
            token = chunk.get("token", "")
            thinking_token = chunk.get("thinking", "")
            
            if token:
                accumulated_response += token
                if accumulated_response.strip().startswith("{"):
                    is_json_detected = True
                
                # Se non è JSON, streammiamo in tempo reale!
                if not is_json_detected and callback:
                    callback({
                        "type": "iteration_response",
                        "iteration": 1,
                        "response": accumulated_response,
                        "thinking": accumulated_thinking
                    })
                    
            if thinking_token:
                accumulated_thinking += thinking_token
                if not is_json_detected and callback:
                    callback({
                        "type": "iteration_response",
                        "iteration": 1,
                        "response": accumulated_response,
                        "thinking": accumulated_thinking
                    })
                    
            if chunk.get("done"):
                break
                
        # Alla fine, se abbiamo rilevato un JSON, facciamo il parsing ed estraiamo la risposta
        final_clean_response = accumulated_response
        final_clean_thinking = accumulated_thinking
        
        if is_json_detected:
            # Estraiamo il JSON completo
            json_match = _extract_json_from_response(accumulated_response)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    final_clean_response = parsed.get("response", accumulated_response)
                    final_clean_thinking = parsed.get("thinking", accumulated_thinking)
                except Exception:
                    pass
            else:
                # Prova comunque un parsing ingenuo del testo intero
                try:
                    parsed = json.loads(accumulated_response.strip())
                    final_clean_response = parsed.get("response", accumulated_response)
                    final_clean_thinking = parsed.get("thinking", accumulated_thinking)
                except Exception:
                    pass
                    
        # Inviamo l'evento finale execute_done
        from core.chat.response_parser import _clean_all_tags
        final_clean_response, extracted_thinking = _clean_all_tags(final_clean_response)
        if not final_clean_thinking and extracted_thinking:
            final_clean_thinking = extracted_thinking
            
        if callback:
            # Forziamo un'ultima emissione pulita della risposta completa
            callback({
                "type": "iteration_response",
                "iteration": 1,
                "response": final_clean_response,
                "thinking": final_clean_thinking,
            })
            callback({
                "type": "execute_done",
                "iteration": 1,
                "total_iterations": 1,
                "response": final_clean_response,
                "message": "✅ Risposta diretta completata"
            })
            callback({"type": "done", "summary": {
                "iterations": 1, "total_actions": 0,
                "successful_actions": 0,
                "files_created": 0,
            }, "actions_log": []})
            
        return {"response": final_clean_response, "actions_log": [], "iterations": 1, "completed": True}

    all_actions_log = []
    current_iteration = 0
    completed = False
    final_response = ""

    if callback:
        callback({"type": "execute_start", "message": f"Avvio con {model}", "max_iterations": max_iterations, "goal": goal})

    while current_iteration < max_iterations and not completed:
        current_iteration += 1
        if callback:
            callback({"type": "iteration_start", "iteration": current_iteration, "max_iterations": max_iterations})

        from core.ai_providers import call_ai_model_stream

        response_accumulated = ""
        thinking_accumulated = ""
        is_json_detected = False
        error = None

        stream_generator = call_ai_model_stream(
            messages, ai_cfg, model, provider, endpoint, api_url, api_key, 
            temperature, max_tokens * 2, top_p, request_timeout
        )

        for chunk in stream_generator:
            if chunk.get("error"):
                error = chunk.get("message", "Errore sconosciuto")
                break

            token = chunk.get("token", "")
            thinking_token = chunk.get("thinking", "")

            if token:
                response_accumulated += token
                if response_accumulated.strip().startswith("{"):
                    is_json_detected = True

                # Se non è JSON, streammiamo l'intero testo accumulato
                if not is_json_detected and callback:
                    callback({
                        "type": "iteration_response",
                        "iteration": current_iteration,
                        "response": response_accumulated,
                        "thinking": thinking_accumulated
                    })
                # Se è JSON, estraiamo in streaming il testo parziale di 'response'!
                elif is_json_detected and callback:
                    partial_resp = _extract_partial_string_field("response", response_accumulated)
                    partial_think = _extract_partial_string_field("thinking", response_accumulated) or thinking_accumulated
                    if partial_resp or partial_think:
                        callback({
                            "type": "iteration_response",
                            "iteration": current_iteration,
                            "response": partial_resp,
                            "thinking": partial_think
                        })

            if thinking_token:
                thinking_accumulated += thinking_token
                # Se non è JSON, streammiamo
                if not is_json_detected and callback:
                    callback({
                        "type": "iteration_response",
                        "iteration": current_iteration,
                        "response": response_accumulated,
                        "thinking": thinking_accumulated
                    })
                # Se è JSON, estraiamo in streaming il testo parziale di 'thinking'!
                elif is_json_detected and callback:
                    partial_resp = _extract_partial_string_field("response", response_accumulated)
                    partial_think = _extract_partial_string_field("thinking", response_accumulated) or thinking_accumulated
                    if partial_resp or partial_think:
                        callback({
                            "type": "iteration_response",
                            "iteration": current_iteration,
                            "response": partial_resp,
                            "thinking": partial_think
                        })

            if chunk.get("done"):
                break

        if error:
            if callback:
                callback({"type": "error", "iteration": current_iteration, "error": f"Errore AI: {error}"})
            break

        response = response_accumulated
        thinking = thinking_accumulated

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
                    "role": "user", 
                    "content": f"[SISTEMA] ⚠️ **Iterazione {current_iteration}:** Hai risposto in testo normale. Per favore rispondi con un blocco JSON valido: {{\"response\": \"...\", \"actions\": [...]}} o {{\"done\": true, \"response\": \"...\"}} se hai completato l'obiettivo."
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

        # Se non ci sono azioni nel JSON, assumiamo che l'AI abbia fornito la risposta finale testuale
        if not actions:
            completed = True
            final_response = ai_response_text or response
            if callback:
                callback({
                    "type": "execute_done",
                    "iteration": current_iteration,
                    "total_iterations": current_iteration,
                    "response": final_response,
                    "message": "✅ Risposta testuale ricevuta"
                })
            break

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

        valid_actions, invalid_actions = _validate_action_types(actions)

        if not valid_actions:
            fb = f"[SISTEMA] ⚠️ **Iterazione {current_iteration}:** Hai fornito {len(actions)} azioni non valide o prive del campo obbligatorio 'type'. Assicurati che ogni azione contenga il campo 'type' (es. read_file o edit_file) e che rispetti lo schema definito."
            messages.append({"role": "user", "content": fb})
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

        details_list = []
        for a in iteration_log:
            status = '✅' if a.get('success') else '❌'
            action_type = a.get('type', '?')
            msg = a.get('message', a.get('error', ''))
            details_list.append(f"  {status} {action_type}: {msg}")
            
            # Se è una lettura di file riuscita, iniettiamo il contenuto completo per l'AI
            if a.get('success') and action_type == "read_file" and a.get("content") is not None:
                details_list.append(f"\n--- CONTENUTO FILE LETTO {a.get('path')} ---\n{a.get('content')}\n--- FINE CONTENUTO ---\n")
            
            # Se ha generato un diff, lo mostriamo all'AI nel suo contesto
            elif a.get('success') and a.get('diff'):
                details_list.append(f"\n--- MODIFICHE EFFETTUATE (DIFF) {a.get('path')} ---\n{a.get('diff')}\n--- FINE DIFF ---\n")

        details = "\n".join(details_list)
        fb = f"[SISTEMA] 📋 **Risultati Iterazione {current_iteration}**: {success}/{len(iteration_log)} azioni riuscite\n\nDettaglio:\n{details}"
        messages.append({"role": "user", "content": fb})

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