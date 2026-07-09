# ==============================================================================
# core/plan_handler.py — Plan → Act workflow (Cline-style)
# Sigma Studio v7 — Produce piani strutturati, li mostra all'utente,
# e li esegue solo dopo approvazione (o automaticamente con Auto-approve).
# ==============================================================================
"""Plan → Act workflow handler.
Phase 1 — PLAN: AI analizza il goal e produce un piano con step strutturati.
Phase 2 — APPROVE: Utente approva o rifiuta il piano (o Auto-approve salta).
Phase 3 — ACT: Esegue ogni step del piano in sequenza con feedback."""
import os
import json
import datetime
import re
from core.ai_providers import load_ai_config, resolve_provider_config, call_ollama, call_openai_compatible, call_anthropic
from core.task_handler import execute_ai_actions
from core.chat_handler import _get_manifesto_content, _get_time_context, _build_filesystem_context, _extract_json_from_response, _collect_context_files, _perform_web_search

# ==============================================================================
# PHASE 1 — PLAN: Genera un piano strutturato
# ==============================================================================

def _generate_plan(self, req):
    """Generate a structured plan for a given goal.
    
    Returns: {
        "goal": "...",
        "analysis": "Analisi del modello...",
        "steps": [
            {
                "id": 1,
                "description": "Leggere il file principale",
                "actions": [{"type": "read_file", "path": "sigma_studio/src/App.jsx"}],
                "status": "pending"  # pending | approved | executing | done | failed
            },
            ...
        ],
        "plan_approved": false
    }
    """
    goal = req.get("message", "").strip()
    if not goal:
        return None, "Goal vuoto"
    
    model_override = req.get("model", "")
    manifesto_path = req.get("manifesto_path", "")
    context_files = req.get("context", {}).get("open_files", [])
    history = req.get("context", {}).get("history", [])
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
    temperature = 0.3  # Lower temperature for planning (more deterministic)
    max_tokens = 4096
    top_p = active_prov_cfg.get("top_p", 0.9)
    request_timeout = active_prov_cfg.get("timeout", 300)
    
    # Resolve provider
    detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
    if detected_prov:
        provider = detected_provider
        if detected_prov.get("endpoint"): endpoint = detected_prov["endpoint"]
        if detected_prov.get("api_url"): api_url = detected_prov["api_url"]
        if detected_prov.get("api_key"): api_key = detected_prov["api_key"]
    
    if req.get("model_provider"): provider = req.get("model_provider")
    if req.get("model_endpoint"): endpoint = req.get("model_endpoint")
    if req.get("model_api_url"): api_url = req.get("model_api_url")
    
    # --- Build context ---
    time_ctx = _get_time_context()
    from core.chat_handler import _build_filesystem_context as fs_ctx
    fs_context = fs_ctx()
    system_prompt = _get_manifesto_content(manifesto_path or "")
    if not system_prompt.strip():
        system_prompt = "Sei Sigma AI Studio, un assistente AI integrato in Sigma Studio. Rispondi in italiano."
    
    context_str = _collect_context_files(self, context_files)
    
    # Build filesystem tree for the target project (sigma_studio/src)
    project_tree = ""
    src_dir = "sigma_studio/src"
    if os.path.isdir(src_dir):
        tree_lines = []
        for root, dirs, files in os.walk(src_dir):
            # Skip node_modules, dist, etc.
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'dist')]
            level = root.replace(src_dir, '').count(os.sep)
            indent = '  ' * level
            folder_name = os.path.basename(root) or 'src'
            tree_lines.append(f"{indent}{'📁 ' if level > -1 else ''}{folder_name}/")
            subindent = '  ' * (level + 1)
            for f in sorted(files):
                if f.endswith(('.jsx', '.js', '.tsx', '.ts', '.css', '.html', '.json')):
                    fpath = os.path.join(root, f)
                    fsize = os.path.getsize(fpath)
                    tree_lines.append(f"{subindent}📄 {f} ({fsize}B)")
        project_tree = '\n'.join(tree_lines)
    
    # --- Planning prompt ---
    plan_prompt = f"""{system_prompt}

## 🎯 OBIETTIVO
{goal}

## CONTESTO
Oggi: {time_ctx}

### Struttura del progetto (sigma_studio/src/):
{project_tree[:2000]}

{f'### File aperti:\n{context_str}' if context_str else ''}

### AZIONI DISPONIBILI
I tipi di azione validi sono:
- read_file: legge un file. Parametri: "path"
- create_file: crea un nuovo file. Parametri: "path", "content"
- edit_file: modifica un file esistente. Parametri: "path", "content"[, "search" per sostituzione testo]
- delete_file: elimina file. Parametri: "path"
- run_test: esegue un test. Parametri: "path"

## COMPITO
Analizza l'obiettivo e la struttura del progetto, poi crea un **piano dettagliato** 
con step specifici. Ogni step deve contenere le azioni necessarie e una descrizione.

## FORMATO RISPOSTA — SOLO JSON VALIDO
{{"analysis": "La tua analisi della situazione... cosa serve fare e perché...",
  "steps": [
    {{
      "description": "Leggere App.jsx per capire la struttura attuale",
      "actions": [{{"type": "read_file", "path": "sigma_studio/src/App.jsx"}}]
    }},
    {{
      "description": "Modificare App.jsx per aggiungere il footer",
      "actions": [{{"type": "edit_file", "path": "sigma_studio/src/App.jsx", "search": "</div>\\n</div>\\n);", "content": "<footer>Powered by Diego Saitta</footer>\\n</div>\\n</div>\\n);"}}]
    }}
  ]
}}

### REGOLE PER I PATH
- Usa path ASSOLUTI relativi alla root del progetto: sigma_studio/src/...
- NON usare data/scratch/ per file di progetto
- I file sigma_studio/package.json, sigma_studio/src/main.jsx, sigma_studio/src/App.jsx ESISTONO
- Per edit_file, fornisci SEMPRE "search" (testo esistente da sostituire) + "content" (nuovo testo)

### REGOLE PER GLI STEP
- Massimo 5 step
- Primo step: SEMPRE read_file per capire la struttura
- Step successivi: azioni concrete per completare l'obiettivo
- Ogni step deve avere UNA descrizione chiara
- Non servono step di verifica finale
"""
    
    plan_messages = [{"role": "system", "content": plan_prompt}]
    plan_messages.append({"role": "user", "content": f"Analizza e crea un piano per: {goal}"})
    
    # Call AI
    route_provider = provider
    if route_provider not in ('ollama', 'api', 'anthropic'):
        route_provider = 'api' if 'anthropic' not in api_url.lower() else 'anthropic'
    
    if route_provider == "ollama":
        num_ctx = active_prov_cfg.get("num_ctx", 8192)
        top_k = active_prov_cfg.get("top_k", 40)
        repeat_penalty = active_prov_cfg.get("repeat_penalty", 1.1)
        seed = active_prov_cfg.get("seed", 0)
        response, thinking, error = call_ollama(plan_messages, model, endpoint, 0.3, max_tokens, top_p, top_k, repeat_penalty, num_ctx, seed, request_timeout)
    elif route_provider == "api":
        response, thinking, error = call_openai_compatible(plan_messages, model, api_url, api_key, 0.3, max_tokens, top_p, request_timeout)
    elif route_provider == "anthropic":
        result = call_anthropic(plan_messages, model, api_url, api_key, 0.3, max_tokens, top_p)
        response, error = result[0], result[1] if len(result) > 1 else None
        thinking = None
    else:
        error = f"Provider sconosciuto: {provider}"
    
    if error:
        return None, f"Errore pianificazione: {error}"
    
    if not response:
        return None, "Risposta vuota dal modello"
    
    # Extract JSON from response
    json_match = _extract_json_from_response(response)
    if not json_match:
        # Try more lenient: find any JSON with "steps"
        json_match = re.search(r'\{[\s\S]*"steps"[\s\S]*\}', response)
    
    if not json_match:
        return None, f"Risposta non contiene JSON valido. Testo: {response[:500]}"
    
    try:
        parsed = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None, f"JSON non valido: {json_match.group()[:200]}"
    
    analysis = parsed.get("analysis", "Analisi completata.")
    steps = parsed.get("steps", [])
    
    if not steps:
        return None, "Nessuno step generato"
    
    # Validate and normalize steps
    validated_steps = []
    for i, step in enumerate(steps):
        desc = step.get("description", f"Step {i+1}")
        actions = step.get("actions", [])
        if not actions:
            continue
        # Normalize action types
        for a in actions:
            atype = a.get("type", "")
            path = a.get("path", "")
            # If path doesn't start with sigma_studio/ or data/ or core/ or manifesti/, warn but keep
        validated_steps.append({
            "id": i + 1,
            "description": desc,
            "actions": actions,
            "status": "pending"
        })
    
    if not validated_steps:
        return None, "Nessuno step valido generato"
    
    plan = {
        "goal": goal,
        "analysis": analysis,
        "thinking": thinking,
        "steps": validated_steps,
        "plan_approved": False,
        "plan_id": int(datetime.datetime.now().timestamp() * 1000),
    }
    
    return plan, None


def handle_chat_plan(self):
    """POST /api/chat/plan — Produce un piano strutturato per un goal.
    
    Returns JSON with:
    - analysis: analisi testuale
    - steps: lista di step strutturati
    - plan_id: ID univoco del piano
    
    L'utente approva il piano, poi lo esegue con /api/chat/execute.
    """
    try:
        req = self.read_json_body()
        plan, error = _generate_plan(self, req)
        
        if error:
            return self.send_json_response({"success": False, "error": error}, 400)
        
        return self.send_json_response({
            "success": True,
            "plan": plan
        })
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_chat_execute_plan(self):
    """POST /api/chat/execute_plan — Esegue un piano pre-approvato.
    
    Riceve un piano (con steps e actions) e lo esegue step-by-step
    con feedback loop continuo, simile a execute_feedback_loop ma
    partendo da un piano invece che da un goal generico.
    """
    try:
        req = self.read_json_body()
        plan = req.get("plan", {})
        auto_approve = req.get("auto_approve", False)
        
        if not plan or not plan.get("steps"):
            return self.send_json_response({"error": "Piano non valido o senza step"}, 400)
        
        goal = plan.get("goal", "Esecuzione piano")
        steps = plan.get("steps", [])
        bot_name = req.get("bot_name", "SigmaBot")
        manifesto_path = req.get("manifesto_path", "")
        model_override = req.get("model", "")
        context_files = req.get("context", {}).get("open_files", [])
        history = req.get("context", {}).get("history", [])
        
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
            except:
                pass
        
        _sse({
            "type": "plan_execute_start",
            "total_steps": len(steps),
            "goal": goal,
            "auto_approve": auto_approve,
            "message": f"Avvio esecuzione piano: {len(steps)} step"
        })
        
        all_actions_log = []
        
        for step_idx, step in enumerate(steps):
            step_id = step.get("id", step_idx + 1)
            description = step.get("description", f"Step {step_id}")
            actions = step.get("actions", [])
            status = step.get("status", "pending")
            
            if status == "done":
                continue
            
            _sse({
                "type": "plan_step_start",
                "step_id": step_id,
                "total_steps": len(steps),
                "description": description,
                "actions_count": len(actions),
                "message": f"▶️ Step {step_id}/{len(steps)}: {description}"
            })
            
            # Esegui azioni per questo step
            step_log = execute_ai_actions(self, actions, bot_name)
            all_actions_log.extend(step_log)
            
            success_count = sum(1 for a in step_log if a.get("success"))
            fail_count = sum(1 for a in step_log if not a.get("success"))
            
            _sse({
                "type": "plan_step_complete",
                "step_id": step_id,
                "total_steps": len(steps),
                "description": description,
                "actions_log": step_log,
                "success_count": success_count,
                "fail_count": fail_count,
                "message": f"{'✅' if fail_count == 0 else '⚠️'} Step {step_id}/{len(steps)}: {success_count}/{len(step_log)} azioni riuscite"
            })
        
        # Final summary
        total_success = sum(1 for a in all_actions_log if a.get("success"))
        total_fail = sum(1 for a in all_actions_log if not a.get("success"))
        files_created = [a for a in all_actions_log if a.get("type") == "create_file" and a.get("success")]
        files_edited = [a for a in all_actions_log if a.get("type") == "edit_file" and a.get("success")]
        
        _sse({
            "type": "plan_execute_done",
            "total_actions": len(all_actions_log),
            "successful_actions": total_success,
            "failed_actions": total_fail,
            "files_created": len(files_created),
            "files_modified": len(files_edited),
            "summary": {
                "total_steps": len(steps),
                "total_actions": len(all_actions_log),
                "successful_actions": total_success,
                "files_created": len(files_created),
                "files_modified": len(files_edited),
            },
            "message": f"🎯 Piano completato: {total_success}/{len(all_actions_log)} azioni, {len(files_created)} file creati, {len(files_edited)} file modificati"
        })
        
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        
    except Exception as e:
        try:
            self.send_json_response({"error": str(e)}, 500)
        except:
            pass