"""Chat handler for Sigma Studio â€” AI conversation, streaming, actions, web search."""
import os
import json
import re
import datetime

from core.ai_providers import (
    load_ai_config, resolve_provider_config,
    call_ollama, call_ollama_stream,
    call_openai_compatible, call_openai_compatible_stream,
    call_anthropic,
    detect_execution_profile, apply_execution_profile,
)
from core.task_handler import execute_ai_actions
from core.agent_memory import get_memory_context, save_session_memory, save_decision_memory, load_memory
from core.agent_registry import increment_usage, get_agent
from core.store import tasks_store
from core.logger import get_logger

# --- Chat sub-package (extracted for single responsibility) ---
from core.chat.response_parser import (
    _TAG_PATTERNS, _clean_all_tags, _extract_json_from_response,
    _extract_english_thinking, _extract_bullet_thinking, _extract_done_thinking,
    _format_response,
)
from core.chat.prompt_builder import (
    _get_time_context, _get_manifesto_content, _build_filesystem_context,
    _collect_context_files, _resolve_manifesto_for_model, _determine_agent_by_request,
)
from core.chat.web_search import _perform_web_search

log = get_logger(__name__)

# ==============================================================================
# The following module-level functions have been MOVED to core/chat/ sub-package:
#   _TAG_PATTERNS, _format_response, _clean_all_tags, _extract_json_from_response,
#   _extract_english_thinking, _extract_bullet_thinking, _extract_done_thinking
#       â†’ core/chat/response_parser.py
#
#   _get_time_context, _get_manifesto_content, _build_filesystem_context,
#   _collect_context_files, _resolve_manifesto_for_model
#       â†’ core/chat/prompt_builder.py
#
#   _scrape_url, _search_duckduckgo, _perform_web_search
#       â†’ core/chat/web_search.py
#
# All are re-exported via core/chat/__init__.py and imported at the top of this
# file for full backward compatibility with other modules that imported them
# directly from core.chat_handler.
def _extract_and_create_files_from_text(clean_response: str, prompt_topic: str = "") -> list[str]:
    """Extract multiple files from markdown text response and save them cleanly."""
    created_paths = []
    from core.data_handler import rebuild_modules_meta

    # Pattern 0: Pseudo-code command create_file path="..." content="..."
    pseudo_matches = re.findall(
        r"create_file\s+path=[\"']?(?:📄\s*)?(data/[^\s\"']+)[\"']?\s+content=[\"']([\s\S]*?)(?:[\"']\s*(?:create_file|\Z))",
        clean_response,
        re.IGNORECASE
    )
    if pseudo_matches:
        for path_str, file_content in pseudo_matches:
            clean_path = path_str.strip().replace('\\', '/')
            if clean_path and file_content.strip():
                dir_name = os.path.dirname(clean_path)
                os.makedirs(dir_name, exist_ok=True)
                with open(clean_path, "w", encoding="utf-8") as f:
                    f.write(file_content.strip())
                created_paths.append(clean_path)
                log.info("Auto-extracted pseudo create_file: %s (%d chars)", clean_path, len(file_content))

    # Pattern 1: Explicit Path markers + codeblock
    file_matches = re.findall(
        r"(?:Path|Percorso|File|Salva\s+in):\s*[`'\"]?(data/[a-zA-Z0-9_/-]+\.[a-zA-Z0-9]+)[`'\"]?[\s\S]*?```[a-zA-Z0-9]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )

    if file_matches:
        for path_str, file_content in file_matches:
            clean_path = path_str.strip().replace('\\', '/')
            if clean_path and file_content.strip() and clean_path not in created_paths:
                dir_name = os.path.dirname(clean_path)
                os.makedirs(dir_name, exist_ok=True)
                with open(clean_path, "w", encoding="utf-8") as f:
                    f.write(file_content.strip())
                created_paths.append(clean_path)
                log.info("Auto-extracted file from text: %s (%d chars)", clean_path, len(file_content))
    else:
        # Pattern 1b: Explicit inline file path markers (e.g. "nella directory: 📄 data/studiare/02_approfondimenti/teoria/serie_numeriche.md")
        inline_paths = re.findall(
            r"(?:directory|percorso|cartella|path|file):\s*(?:📄\s*)?[`'\"]?(data/[a-zA-Z0-9_/-]+\.[a-zA-Z0-9]+)[`'\"]?",
            clean_response,
            re.IGNORECASE
        )
        if inline_paths:
            for clean_path in inline_paths:
                clean_path = clean_path.strip().replace('\\', '/')
                if clean_path and clean_path not in created_paths:
                    dir_name = os.path.dirname(clean_path)
                    os.makedirs(dir_name, exist_ok=True)
                    with open(clean_path, "w", encoding="utf-8") as f:
                        f.write(clean_response)
                    created_paths.append(clean_path)
                    log.info("Auto-extracted inline path file: %s (%d chars)", clean_path, len(clean_response))
        # Pattern 2: Section headers (Teoria, Viz, Test, Docs) + codeblocks
        blocks = re.findall(
            r"(?:###|##|\*\*)\s*(?:[0-9\.\s]*)(Teoria|Viz|Test|Docs|Whitepaper)[^\n]*\n(?:[^\n]*\n)*?```([a-zA-Z0-9]*)\n([\s\S]*?)\n```",
            clean_response,
            re.IGNORECASE
        )
        if blocks:
            topic_id = re.sub(r'[^a-zA-Z0-9_]+', '_', prompt_topic.lower()).strip('_') if prompt_topic else ""
            if not topic_id:
                timestamp = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
                topic_id = f"auto_{timestamp}"

            for idx, (section_type, lang, file_content) in enumerate(blocks, start=1):
                sec = section_type.lower()
                if "teoria" in sec or lang == "markdown":
                    folder, ext = "teoria", "md"
                elif "viz" in sec or lang == "html":
                    folder, ext = "viz", "html"
                elif "test" in sec or lang == "python":
                    folder, ext = "test", "py"
                else:
                    folder, ext = "docs", "md"

                clean_path = f"data/{topic_id}/01_base/{folder}/documento_{idx}.{ext}"
                dir_name = os.path.dirname(clean_path)
                os.makedirs(dir_name, exist_ok=True)
                with open(clean_path, "w", encoding="utf-8") as f:
                    f.write(file_content.strip())
                created_paths.append(clean_path)
                log.info("Auto-extracted section file: %s (%d chars)", clean_path, len(file_content))

    if not created_paths and len(clean_response) > 50:
        # Fallback for single document
        title_match = re.search(r'^#\s+(.+)', clean_response, re.MULTILINE)
        raw_title = title_match.group(1).strip() if title_match else prompt_topic or "documento"
        topic_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', prompt_topic.lower()).strip('_') if prompt_topic else "matematica"
        file_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_title.lower()).strip('_')[:40] or "documento"
        
        clean_path = f"data/{topic_slug}/01_base/teoria/{file_slug}.md"
        dir_name = os.path.dirname(clean_path)
        os.makedirs(dir_name, exist_ok=True)
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(clean_response)
        created_paths.append(clean_path)
        log.info("Auto-extracted fallback topic file: %s (%d chars)", clean_path, len(clean_response))

    if created_paths:
        rebuild_modules_meta()

    return created_paths


def handle_chat(self):
    """POST /api/chat â€” Send message to AI agent and execute actions."""
    try:
        req = self.read_json_body()
        message = req.get("message", "").strip()
        if not message:
            return self.send_json_response({"error": "Messaggio vuoto"}, 400)

        bot_name = req.get("bot_name", "SigmaBot")
        manifesto_path = req.get("manifesto_path", "")
        model_override = req.get("model", "")
        allow_actions = req.get("allow_actions", True)
        planning_mode = req.get("planning_mode", False)

        # Auto-detect file creation requests: if user explicitly asks to create/write a file
        user_requested_file_creation = False
        _create_keywords = [
            "crea un file", "crea file", "scrivi un file", "scrivi file",
            "crea un documento", "crea documento", "genera un file", "genera file",
            "crea un modulo", "crea modulo", "crea un argomento", "crea argomento",
            "salva in un file", "salva un file", "salva file", "salva su file",
        ]
        msg_lower = message.lower()
        for kw in _create_keywords:
            if kw in msg_lower:
                user_requested_file_creation = True
                allow_actions = True
                log.info("Auto-detected file creation request: forcing allow_actions=True")
                break
        execute_task_id = req.get("execute_task_id", "")
        context_files = req.get("context", {}).get("open_files", [])
        history = req.get("context", {}).get("history", [])
        uploaded_files = req.get("uploaded_files", [])

        ai_cfg = load_ai_config()
        model = model_override or ai_cfg.get("model", "llama3.2")

        # Automatic Agent Routing: Front-Desk Switchboard evaluates domain & intent
        if not manifesto_path or manifesto_path in ("auto", "auto.md", "manifesti/auto.md", "MANIFESTO.md", "manifesti/sigma_assistant.md"):
            determined = _determine_agent_by_request(message, ai_cfg, model)
            if determined:
                manifesto_path = determined
            elif not manifesto_path:
                manifesto_path = _resolve_manifesto_for_model(model)
        
        if not manifesto_path:
            manifesto_path = "MANIFESTO.md"

        manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''

        # Update bot_name based on chosen agent
        if bot_name in ("SigmaBot", "Sigma AI Studio", "Sigma Agent", "Sigma Assistant", "auto"):
            agent_id_match = os.path.splitext(os.path.basename(manifesto_path))[0]
            from core.agent_registry import get_agent
            ag = get_agent(agent_id_match)
            if ag:
                bot_name = ag.get("name", bot_name)

        model = model_override or ai_cfg.get("model", "llama3.2")
        provider = ai_cfg.get("active_provider", "ollama")
        providers_config = ai_cfg.get("providers", {})
        active_prov_cfg = providers_config.get(provider, {})
        endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
        api_url = active_prov_cfg.get("api_url", "")
        api_key = active_prov_cfg.get("api_key", "")
        temperature = active_prov_cfg.get("temperature", 0.7)
        max_tokens = active_prov_cfg.get("max_tokens", 16384)
        top_p = active_prov_cfg.get("top_p", 0.9)
        request_timeout = active_prov_cfg.get("timeout", 300)

        model_provider = req.get("model_provider", "")
        model_endpoint = req.get("model_endpoint", "")
        model_api_url = req.get("model_api_url", "")
        model_api_key = req.get("model_api_key", "")

        if model_provider:
            provider = model_provider
            if model_endpoint: endpoint = model_endpoint
            if model_api_url: api_url = model_api_url
            if model_api_key: api_key = model_api_key
            pv = providers_config.get(provider, {})
            if pv:
                temperature = pv.get("temperature", temperature)
                max_tokens = pv.get("max_tokens", max_tokens)
                top_p = pv.get("top_p", top_p)
        else:
            detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
            if detected_prov:
                provider = detected_provider
                if detected_prov.get("endpoint"): endpoint = detected_prov["endpoint"]
                if detected_prov.get("api_url"): api_url = detected_prov["api_url"]
                if detected_prov.get("api_key"): api_key = detected_prov["api_key"]
                temperature = detected_prov.get("temperature", temperature)
                max_tokens = detected_prov.get("max_tokens", 16384)
                top_p = detected_prov.get("top_p", top_p)
                request_timeout = detected_prov.get("timeout", request_timeout)

        frontend_timeout = req.get("timeout", 0)
        if frontend_timeout and frontend_timeout > 0:
            request_timeout = int(frontend_timeout)

        # Centralino Switchboard: Apply dynamic "Intensità" (Execution Profile Tuning) based on active Agent & Prompt Domain
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
        agent_key = manifesto_name.lower().replace('.md', '')
        profile_key = AGENT_PROFILE_MAP.get(agent_key, detect_execution_profile(message))
        
        prov_dict = {"temperature": temperature, "max_tokens": max_tokens, "top_p": top_p, "num_ctx": active_prov_cfg.get("num_ctx", 16384)}
        tuned_cfg = apply_execution_profile(profile_key, prov_dict)
        
        temperature = tuned_cfg.get("temperature", temperature)
        max_tokens = tuned_cfg.get("max_tokens", max_tokens)
        top_p = tuned_cfg.get("top_p", top_p)
        active_prov_cfg["num_ctx"] = tuned_cfg.get("num_ctx", active_prov_cfg.get("num_ctx", 16384))
        active_prov_cfg["top_k"] = tuned_cfg.get("top_k", active_prov_cfg.get("top_k", 40))
        active_prov_cfg["repeat_penalty"] = tuned_cfg.get("repeat_penalty", active_prov_cfg.get("repeat_penalty", 1.1))

        log.info("Centralino Switchboard -> Agent '%s' | Profilo: '%s' | Temp: %.2f | Ctx: %d",
                 manifesto_name, profile_key, temperature, active_prov_cfg["num_ctx"])

        system_prompt = _get_manifesto_content(manifesto_path)
        if not system_prompt.strip():
            system_prompt = """Sei Sigma AI Studio, un assistente AI avanzato ed elegante integrato in Sigma Studio.
Rispondi in italiano in modo chiaro, diretto, elegante e ben strutturato.
Non stampare mai preamboli meta-cognitivi (es. 'Here's a thinking process:', 'Analisi input:'), né sintassi JSON grezza nel messaggio per l'utente."""

        # --- BUILD SYSTEM PROMPT ---
        if allow_actions or planning_mode:
            action_prompt = """
## REGOLE FONDAMENTALI SULLA CREAZIONE DEI FILE ED ESECUZIONE
1. Rispondi all'utente in modo chiaro, pulito, elegante ed esplicativo in italiano.
2. Crea o modifica file SOLO se l'utente lo ha esplicitamente richiesto o se è strettamente necessario per completare l'azione. Non salvare mai file per semplici risposte o conversazioni in chat.

## STRUTTURA MODULARE
Salva i file in: data/<argomento>/<NN_modulo>/{teoria|test|viz|docs|whitepapers}/<file>
Solo 5 cartelle permesse dentro un modulo: teoria/, test/, viz/, docs/, whitepapers/
Mai salvare file nella root del topic o del modulo.

### COSA PUOI FARE
- create_module: "topic", "number", "name" — crea un modulo con le 5 sottocartelle
- create_file: "path", "content" — salva un file
- edit_file: "path", "content", "search" — modifica un file
- update_task: "titolo", "status", "notifica" — aggiorna un task
- run_test: "path" — esegue un test

### REGOLA VITALE — FILE ESISTENTI VANNO SOVRASCRITTI
Se un file esiste già, riscrivilo comunque con create_file. Mai dire "il file esiste già".
"""
            full_system = f"{system_prompt}\n\n{action_prompt}"
        else:
            full_system = f"{system_prompt}\n\nRispondi all'utente in italiano in modo chiaro, naturale, elegante e ben strutturato in Markdown. Evita preamboli meta-cognitivi o prolissità non necessarie."

        context_str = _collect_context_files(self, context_files)
        tasks_context = json.dumps(tasks_store.load(), indent=2)
        topics_context = _build_filesystem_context()
        time_ctx = _get_time_context()

        system_parts = [full_system, time_ctx]
        if context_str: system_parts.append(f"File aperti:\n{context_str}")
        if uploaded_files:
            us = ""
            for uf in uploaded_files[:10]:
                fn = uf.get("filename", "sconosciuto")
                ct = uf.get("content", "")
                us += f"\n--- FILE CARICATO: {fn} ---\n{ct[:8000]}\n"
            system_parts.append(f"File caricati dal PC:\n{us}")
        if topics_context: system_parts.append(f"Struttura:\n{topics_context}")
        if tasks_context: system_parts.append(f"Tasks:\n{tasks_context}")

        # --- Inject agent memory context ---
        # Context is strictly isolated per chat session — no cross-chat memory leaks
        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        for h in history[-10:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

        user_prompt = message
        if planning_mode:
            user_prompt += """
## MODALITÃ€ PIANIFICAZIONE â€” REGOLE OBBLIGATORIE
Rispondi con JSON: {"response": "...", "tasks": [...]}

IMPORTANTE â€” STRUTTURA MINIMA DI OGNI TASK:
- "titolo": DESCRITTIVO e specifico. MAI "Nuovo task". Esempio: "Dimostrare Lemma di Saturazione" o "Analizzare distribuzione Mod 24"
- "descrizione": ALMENO una frase che spiega cosa fare e perchÃ©. MAI vuota.
- "moduli": array di stringhe con i numeri dei moduli coinvolti. Es: ["01", "02"]. Se non specifico per un modulo, usa [].
- "priorita": una tra "critica", "alta", "media", "bassa". Spiega brevemente perchÃ© in descrizione.
"""
        if execute_task_id:
            task_detail = ""
            if os.path.exists('tasks.json'):
                try:
                    with open('tasks.json', 'r', encoding='utf-8') as f:
                        all_tasks = json.load(f)
                    task = next((t for t in all_tasks if t.get('id') == execute_task_id or t.get('titolo') == execute_task_id), None)
                    if task: task_detail = f"\n\nTask da eseguire: {task.get('titolo','')}\n{task.get('descrizione','')}"
                except: pass
            if task_detail: user_prompt += task_detail
        messages.append({"role": "user", "content": user_prompt})

        ai_response = ""
        ai_thinking = None
        error = None
        route_provider = provider
        if route_provider not in ('ollama', 'api', 'anthropic'):
            route_provider = 'api' if 'anthropic' not in api_url.lower() else 'anthropic'

        web_search = req.get("web_search", False)
        web_sources_list = []
        if web_search and not planning_mode:
            search_results = _perform_web_search(message)
            if search_results and not search_results[0].get("body", "").startswith("Nessun risultato"):
                web_sources_list = [r for r in search_results if r.get("href")]
                st = "\n\n====================================================\n"
                st += "## 🌐 RISULTATI RICERCA WEB & BROWSING (FONTI E LINK REALI)\n"
                st += "L'utente ha attivato la Ricerca Web. DEVI utilizzare le informazioni e i link sottostanti per la tua risposta.\n"
                st += "REGOLE TASSATIVE SULLE CITAZIONI E LINK:\n"
                st += "1. PER OGNI CANALE, VIDEO, ARTICOLO O RISULTATO MENZIONATO, INCLUDI OBBLIGATORIAMENTE IL LINK MARKDOWN CLICCABILE nel formato `[Titolo/Canale](URL)`.\n"
                st += "2. NON elencare MAI nomi di video, canali o siti web senza il relativo link Markdown `[Nome](https://...)`.\n"
                st += "3. RISPONDI DIRETTAMENTE ED IMMEDIATAMENTE ALL'UTENTE CON I LINK ED I DETTAGLI. NON SCRIVERE MAI PREAMBOLI META-COGNITIVI (Es: 'L'utente chiede... devo usare la funzione...').\n\n"
                st += "FONTI TROVATE SULLA RETE:\n"
                for i, r in enumerate(web_sources_list[:7], 1):
                    st += f"{i}. **[{r['title']}]({r['href']})**\n   Descrizione: {r['body'][:400]}\n   URL Diretto: {r['href']}\n\n"
                st += "====================================================\n"
                messages[0]["content"] += st

        stream_mode = req.get("stream", False)
        if stream_mode and not allow_actions and not planning_mode:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            def _sw(chunks):
                try:
                    meta_payload = {
                        "meta": {
                            "agent_id": manifesto_name,
                            "agent_name": bot_name,
                            "manifesto_used": manifesto_name,
                            "web_search_active": web_search,
                            "web_sources": [{"title": r["title"], "href": r["href"]} for r in web_sources_list]
                        }
                    }
                    self.wfile.write(f"data: {json.dumps(meta_payload)}\n\n".encode())
                    self.wfile.flush()
                    for chunk in chunks:
                        if chunk is None: self.wfile.write(b"data: [ERROR]\n\n"); break
                        if chunk.get("error"): self.wfile.write(f"data: {json.dumps({'error': chunk['message']})}\n\n".encode()); self.wfile.flush(); break
                        if chunk.get("done"): self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush(); break
                        payload = {}
                        if "token" in chunk: payload["token"] = chunk["token"]
                        if "thinking" in chunk: payload["thinking"] = chunk["thinking"]
                        if payload: self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode()); self.wfile.flush()
                    else: self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                except: self.wfile.write(b"data: [ERROR]\n\n"); self.wfile.flush()
            if route_provider == "ollama":
                num_ctx = active_prov_cfg.get("num_ctx", 8192)
                top_k = active_prov_cfg.get("top_k", 40)
                repeat_penalty = active_prov_cfg.get("repeat_penalty", 1.1)
                seed = active_prov_cfg.get("seed", 0)
                chunks = call_ollama_stream(messages, model, endpoint, temperature, max_tokens, top_p, top_k, repeat_penalty, num_ctx, seed, request_timeout)
                _sw(chunks); return
            elif route_provider == "api":
                chunks = call_openai_compatible_stream(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
                _sw(chunks); return

        if route_provider == "ollama":
            num_ctx = active_prov_cfg.get("num_ctx", 8192)
            top_k = active_prov_cfg.get("top_k", 40)
            repeat_penalty = active_prov_cfg.get("repeat_penalty", 1.1)
            seed = active_prov_cfg.get("seed", 0)
            ai_response, ai_thinking, error = call_ollama(messages, model, endpoint, temperature, max_tokens, top_p, top_k, repeat_penalty, num_ctx, seed, request_timeout)
        elif route_provider == "api":
            ai_response, ai_thinking, error = call_openai_compatible(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
        elif route_provider == "anthropic":
            ai_response, error = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
        else:
            error = f"Provider sconosciuto: {provider}"

        if error:
            manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
            return self.send_json_response({"response": f"âš ï¸ Errore IA ({provider}): {error}", "actions_log": [], "error": error, "manifesto_used": manifesto_name})

        actions_log = []
        clean_response = ai_response
        thinking = ai_thinking

        # In Ask mode (no actions), keep the raw response intact â€” don't mess with it
        # LaTeX, markdown, line breaks, etc. must be preserved for the frontend KaTeX renderer
        if not allow_actions and not planning_mode:
            # If JSON response/thinking format detected, extract cleanly
            json_match = _extract_json_from_response(ai_response)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    resp_text = parsed.get("response", "")
                    think_text = parsed.get("thinking", parsed.get("reasoning", ""))
                    if resp_text:
                        clean_response = resp_text
                    if think_text and not thinking:
                        thinking = think_text
                except Exception:
                    pass
            
            # If thinking is still not set, try separating using response parser tags & transition checks
            if not thinking:
                clean_response, extracted_tags_thinking = _clean_all_tags(clean_response)
                thinking = extracted_tags_thinking

            log.debug("ASK mode: response_len=%d thinking=%s", len(clean_response), 'yes' if thinking else 'none')
            manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
            self.send_json_response({
                "response": clean_response,
                "thinking": thinking,
                "actions_log": [],
                "error": None,
                "manifesto_used": manifesto_name,
                "agent_name": bot_name,
                "agent_id": manifesto_name
            })
            return

        # --- From here on: ALLOW ACTIONS or PLANNING mode ---
        # Remove container tags, extract thinking, and look for JSON with actions
        clean_response, extracted_tags_thinking = _clean_all_tags(clean_response)
        thinking = ai_thinking or extracted_tags_thinking

        log.debug("actions=%s planning=%s resp_preview=%.200s", allow_actions, planning_mode, clean_response)

        json_match = _extract_json_from_response(clean_response)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                log.debug("JSON parsed. actions_count=%d", len(parsed.get('actions', [])))
                clean_response = parsed.get("response", ai_response)
                clean_response = _format_response(clean_response)
                json_thinking = parsed.get("thinking", parsed.get("reasoning", None))
                if json_thinking and not thinking:
                    thinking = json_thinking
                actions = parsed.get("actions", [])

                if planning_mode and "tasks" in parsed:
                    plan_tasks = parsed.get("tasks", [])
                    if plan_tasks:
                        now_ms = int(datetime.datetime.now().timestamp() * 1000)

                        def _add_plan_tasks(existing: list) -> list:
                            for i, t in enumerate(plan_tasks):
                                titolo = t.get("titolo", "Nuovo task")
                                descrizione = t.get("descrizione", "")
                                priorita = t.get("priorita", "media")
                                moduli = t.get("moduli", [])
                                if titolo.lower() in ("nuovo task", "task", "nuovo", "new task", ""):
                                    titolo = f"Task: {message[:60]}"
                                if not descrizione.strip():
                                    descrizione = f"Task pianificato dall'AI in risposta a: {message[:200]}"
                                if priorita not in ("critica", "alta", "media", "bassa"):
                                    priorita = "media"
                                if not isinstance(moduli, list):
                                    moduli = []
                                existing.append({
                                    "titolo": titolo, "descrizione": descrizione,
                                    "status": "in_corso", "priorita": priorita,
                                    "moduli": moduli,
                                    "id": now_ms + i,
                                    "notifiche": [{
                                        "da": bot_name,
                                        "messaggio": f"Task pianificato da {bot_name}",
                                        "timestamp": datetime.datetime.now().isoformat(),
                                    }],
                                })
                            return existing

                        tasks_store.update(_add_plan_tasks)
                        actions_log.append({"type": "plan_tasks", "success": True, "message": f"{len(plan_tasks)} task creati"})

                if allow_actions and actions:
                    log.debug("Executing %d actions...", len(actions))
                    actions_log = execute_ai_actions(self, actions, bot_name)
                    log.debug("Actions result: %s", actions_log)
                    
                    # Save session memory for the agent
                    if agent_id:
                        success_count = sum(1 for a in actions_log if a.get("success"))
                        fail_count = sum(1 for a in actions_log if not a.get("success"))
                        try:
                            save_session_memory(agent_id, {
                                "goal": message[:200],
                                "actions_performed": actions_log,
                                "success_count": success_count,
                                "fail_count": fail_count,
                                "learning": "",
                                "summary": f"{success_count} azioni riuscite, {fail_count} fallite"
                            })
                            # Update agent usage stats
                            increment_usage(agent_id, success=fail_count == 0)
                        except Exception as mem_err:
                            log.error("Memory save error: %s", mem_err)
                    
                    # Auto-update task when execute_task_id is present
                    # Se siamo in modalitÃ  completa task, aggiorna automaticamente lo stato
                    if execute_task_id and actions_log:
                        try:
                            now_ts = datetime.datetime.now().isoformat()
                            success_count = sum(1 for e in actions_log if e.get("success"))
                            fail_count = sum(1 for e in actions_log if not e.get("success"))
                            summary = f"Task completato: {success_count} azioni riuscite"
                            if fail_count:
                                summary += f", {fail_count} fallite"

                            _notifiable = frozenset({
                                "create_file", "edit_file", "delete_file",
                                "rename_file", "create_module", "run_test",
                            })

                            def _complete_task(tasks_list: list) -> list:
                                for t in tasks_list:
                                    if t.get("id") == execute_task_id or t.get("titolo") == execute_task_id:
                                        t["status"] = "done"
                                        for entry in actions_log:
                                            if entry.get("success") and entry.get("type") in _notifiable:
                                                t.setdefault("notifiche", []).append({
                                                    "da": bot_name,
                                                    "messaggio": f"[{entry['type']}] {entry.get('message', '')}",
                                                    "timestamp": now_ts,
                                                })
                                        t.setdefault("notifiche", []).append({
                                            "da": bot_name, "messaggio": summary, "timestamp": now_ts,
                                        })
                                        break
                                return tasks_list

                            tasks_store.update(_complete_task)
                            actions_log.append({
                                "type": "complete_task", "success": True,
                                "message": f"Task '{execute_task_id}' completato automaticamente",
                            })
                        except Exception as exc:
                            log.error("Auto-update task error: %s", exc)
            except json.JSONDecodeError as exc:
                log.error("JSON decode error: %s", exc)
        elif allow_actions or planning_mode:
            log.warning("No JSON match found in AI response")

            # Pseudo switch_agent interception: if text output mentions a target agent and file creation
            pseudo_agent = re.search(r'\b(math_researcher|code_architect|viz_designer|test_engineer|proof_reviewer|sigma_architect)\b', clean_response, re.IGNORECASE)
            if pseudo_agent and ("data/" in clean_response or "crea" in clean_response.lower() or "file" in clean_response.lower()):
                target_agent = pseudo_agent.group(1).lower()
                log.info("Intercepted pseudo switch_agent to '%s' in text response", target_agent)
                from core.assistant_orchestrator import handle_switch_agent
                switch_res = handle_switch_agent(self, target_agent, message, history, bot_name)
                if switch_res and switch_res.get("response"):
                    return self.send_json_response(switch_res)

            # Attempt automatic file extraction if user explicitly requested file creation or text contains files
            created_files = []
            if (user_requested_file_creation or "data/" in clean_response or "Path:" in clean_response) and len(clean_response) > 30:
                try:
                    created_files = _extract_and_create_files_from_text(clean_response, prompt_topic=message[:60])
                    for cp in created_files:
                        actions_log.append({
                            "type": "create_file", "success": True, "path": cp,
                            "message": f"File creato: {cp}"
                        })
                except Exception as exc:
                    log.error("Auto-create files failed: %s", exc)
            
            # Always show the AI response in chat, plus auto-create file notice if created
            manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
            if created_files:
                files_str = "\n".join([f"- 📄 **`{p}`**" for p in created_files])
                show_response = clean_response + f"\n\n---\n### 📄 File Creato con Successo nel Sistema!\n{files_str}\n\n*Il file è stato salvato nel tuo workspace ed è subito accessibile.*"
            else:
                show_response = clean_response
            
            self.send_json_response({
                "response": show_response,
                "thinking": thinking,
                "actions_log": actions_log,
                "created_files": created_files,
                "error": None,
                "manifesto_used": manifesto_name
            })
            return

        manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
        self.send_json_response({"response": clean_response, "thinking": thinking, "actions_log": actions_log, "error": None, "manifesto_used": manifesto_name})
    except Exception as exc:
        log.error("handle_chat unhandled error: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)
