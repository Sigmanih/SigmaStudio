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
def _normalize_data_path(path_str: str) -> str:
    """Coerce and normalize any file path to strictly reside inside `./data/`."""
    if not path_str:
        return ""
    clean = path_str.strip().replace('\\', '/')
    clean = re.sub(r'^[📄\s`\'"]+', '', clean)
    clean = re.sub(r'[`\'"]+$', '', clean)
    clean = re.sub(r'/+', '/', clean)
    if clean.startswith('./data/'):
        clean = clean[2:]
    elif not clean.startswith('data/'):
        clean = re.sub(r'^(?:[a-zA-Z]:/|/)+', '', clean)
        if not clean.startswith('data/'):
            clean = f"data/{clean}"
    return clean


def _sanitize_history_message(content: str) -> str:
    """Sanitize history messages to remove old system prompts, role headers, welcome badges, and reasoning monologues.
    Prevents Ollama models from getting trapped in identity-conflict loops or referencing deleted topics.
    """
    if not content:
        return ""
    if "Chat pronta." in content or "🤖 **Sigma AI Studio**" in content:
        return ""
    clean = re.sub(r'FROM\s+[a-zA-Z0-9_\.\:]+[\s\S]*?SYSTEM\s+"""[\s\S]*?"""', '', content, flags=re.IGNORECASE)
    clean = re.sub(r'SYSTEM\s+"""[\s\S]*?"""', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Ruolo\s+attivo:[\s\S]*?\n', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Analyze\s+User\s+Input:[\s\S]*?(?:Final\s+Output\s+Generation:|Proceeds\.?|✅|\n\n)', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<think>[\s\S]*?</think>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'📁\s*\*\*File salvati con successo su disco:\*\*[\s\S]*$', '', clean, flags=re.IGNORECASE)
    return clean.strip()


def _ensure_module_subfolders(clean_path: str):
    """Ensure that standard subfolders (teoria, scripts, viz, test, docs) are automatically created
    under the target module folder, even if empty.
    """
    parts = clean_path.split('/')
    if len(parts) >= 3 and parts[0] == 'data':
        module_dir = os.path.join(parts[0], parts[1], parts[2])
        for sub in ('teoria', 'scripts', 'viz', 'test', 'docs'):
            sub_path = os.path.join(module_dir, sub)
            os.makedirs(sub_path, exist_ok=True)


def _format_conversational_summary(ai_response: str, created_paths: list[str]) -> str:
    """Preserve AI conversational response/summary and attach file creation details."""
    if not created_paths:
        return ai_response
    
    # Strip explicit Path headers and saved codeblocks to prevent giant code dumps in chat
    text = ai_response
    text = re.sub(r'(?:Path|Percorso|File)[:\s]+`?(?:data/|\./data/)[^`\n]+`?[^\n]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```[a-zA-Z0-9]*[\s\S]*?```', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    clean_text = text.strip()
    if len(clean_text) < 20:
        clean_text = "Ho elaborato la tua richiesta e generato la documentazione formale su disco."
        
    file_summary = _generate_files_summary(created_paths, ai_response)
    return f"{clean_text}\n\n{file_summary}".strip()


def _generate_files_summary(created_paths: list[str], full_response: str) -> str:
    """Generate an elegant markdown summary description of the created files."""
    if not created_paths:
        return ""
    
    summary_parts = []
    
    # Try extracting main introduction or summary from the full response first
    intro_match = re.search(r'^(?:#\s+[^\n]+\n+)?([\s\S]{30,300}?)(?=\n##|\n```|\Z)', full_response)
    if intro_match and len(full_response) > 350:
        clean_intro = intro_match.group(1).strip()
        summary_parts.append(f"### 📋 Sintesi dei Contenuti Generati\n{clean_intro}\n")

    summary_parts.append("📁 **File creati e salvati su disco:**")
    
    for path in created_paths:
        file_desc = ""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                # Extract H1 title
                h_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                title = h_match.group(1).strip() if h_match else os.path.basename(path)
                
                # Extract first short paragraph
                para_match = re.search(r'^(?:#+\s+[^\n]+\n+)+([\s\S]{20,120}?)(?=\n#|\Z)', content)
                short_text = para_match.group(1).replace('\n', ' ').strip() if para_match else ""
                if short_text:
                    file_desc = f" — *{short_text[:100]}...*"
                summary_parts.append(f"- **{title}**: `{path}`{file_desc}")
            except Exception:
                summary_parts.append(f"- `{path}`")
        else:
            summary_parts.append(f"- `{path}`")
            
    return "\n\n" + "\n".join(summary_parts)


def _determine_default_module_path(topic_slug: str, folder: str, fname: str) -> str:
    """Determine clean module path using existing topic module folders or fallback to 01_base."""
    topic_dir = os.path.join("data", topic_slug)
    if os.path.isdir(topic_dir):
        subdirs = [d for d in sorted(os.listdir(topic_dir)) if os.path.isdir(os.path.join(topic_dir, d))]
        if subdirs:
            return f"data/{topic_slug}/{subdirs[0]}/{folder}/{fname}"
    return f"data/{topic_slug}/01_base/{folder}/{fname}"


def _extract_and_create_files_from_text(clean_response: str, prompt_topic: str = "", force_save: bool = False) -> tuple[list[str], list[dict]]:
    """Extract multiple files from markdown text response, save them with backup and diff tracking.
    
    Returns:
        tuple of (created_paths, actions_log) where each action contains backup_id and diff.
    """
    created_paths = []
    actions_log = []
    from core.data_handler import rebuild_modules_meta
    from core.backup_manager import create_backup
    from core.task_handler import _compute_diff

    def _save_file_with_backup(clean_path: str, file_content: str):
        if not clean_path or not file_content.strip():
            return
        
        clean_path = _normalize_data_path(clean_path)
        filename = os.path.basename(clean_path)
        
        # Strict validation: reject placeholders, dot-only extensions, double slashes, instructions
        if (
            '<' in clean_path or '>' in clean_path
            or filename.startswith('.')
            or len(filename.split('.')[0]) < 2
            or clean_path.endswith('/.md')
            or clean_path.endswith('/.py')
            or clean_path.endswith('/.html')
            or '01_...' in clean_path
            or clean_path in created_paths
        ):
            log.warning("Rejected invalid/placeholder file path extraction: %s", clean_path)
            return

        backup_id = create_backup(clean_path, "chat_save")
        old_content = ""
        if os.path.exists(clean_path):
            try:
                with open(clean_path, "r", encoding="utf-8") as fh:
                    old_content = fh.read()
            except Exception:
                pass
        
        dir_name = os.path.dirname(clean_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        _ensure_module_subfolders(clean_path)
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(file_content.strip())
        
        file_diff = _compute_diff(old_content, file_content.strip(), os.path.basename(clean_path))
        created_paths.append(clean_path)
        actions_log.append({
            "type": "edit_file" if old_content else "create_file",
            "success": True,
            "path": clean_path,
            "message": f"File {'modificato' if old_content else 'creato'}: {clean_path}",
            "backup_id": backup_id,
            "diff": file_diff
        })
        log.info("Auto-extracted & backed-up file: %s (%d chars)", clean_path, len(file_content))

    # Infer topic slug cleanly without command verbs
    raw_prompt = prompt_topic.lower() if prompt_topic else ""
    raw_prompt = re.sub(r'^(?:crea(?:mi)?|scrivi(?:mi)?|genera|sviluppa)\s+(?:un|l[\'\"]|il|lo|la|i|gli|le)?\s*(?:argomento|modulo|documento|file|teoria)?\s*(?:su(?:gli)?|di|per)?\s*', '', raw_prompt).strip()
    topic_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_prompt).strip('_') if raw_prompt else ""
    if not topic_slug or len(topic_slug) < 2 or topic_slug in ('ciao', 'ok', 'test', 'analyze_user_input'):
        t_match = re.search(r'^#\s+(.+)', clean_response, re.MULTILINE)
        if t_match:
            topic_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', t_match.group(1).lower()).strip('_')
    if not topic_slug or topic_slug in ('ciao', 'ok', 'test', 'analyze_user_input'):
        topic_slug = "matematica"

    # Pattern 0: Pseudo-code command create_file path="..." content="..."
    pseudo_matches = re.findall(
        r"create_file\s+path=[\"']?(?:📄\s*)?([^\s\"']+)[\"']?\s+content=[\"']([\s\S]*?)(?:[\"']\s*(?:create_file|\Z))",
        clean_response,
        re.IGNORECASE
    )
    if pseudo_matches:
        for path_str, file_content in pseudo_matches:
            clean_path = _normalize_data_path(path_str)
            _save_file_with_backup(clean_path, file_content)

    # Pattern 0.5: math_researcher manifesto format — Path: `data/...` followed by ```markdown block
    backtick_path_matches = re.findall(
        r"(?:Path|Percorso|File)[:\s]+`((?:data/|\./data/)[^`]+\.[a-zA-Z0-9]+)`[^\n]*\n+```[a-zA-Z0-9]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )
    if backtick_path_matches:
        for path_str, file_content in backtick_path_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                _save_file_with_backup(clean_path, file_content)

    # Pattern 1: Explicit Path markers + codeblock (supports 📄, ./data/, backticks, quotes)
    file_matches = re.findall(
        r"(?:Path|Percorso|File|Salva\s+in|###|##|\*\*|-|\*|\b)?\s*[`'\"]?(?:📄\s*)?((?:data/|\./data/)[^\s`'\"]+\.[a-zA-Z0-9]+)[`'\"]?[\s\S]*?```[a-zA-Z0-9]*\n([\s\S]*?)\n```",
        clean_response,
        re.IGNORECASE
    )
    if file_matches:
        for path_str, file_content in file_matches:
            clean_path = _normalize_data_path(path_str)
            if clean_path and clean_path not in created_paths:
                _save_file_with_backup(clean_path, file_content)

    # Pattern 2: Standalone Codeblocks paired with preceding filenames or headers
    if not created_paths:
        codeblocks = re.findall(r"(?:###|##|\*\*|[a-zA-Z0-9_\-\./]+)?\s*([a-zA-Z0-9_\-\./]+\.(?:md|py|html|js|css|json))?[^\n]*\n```([a-zA-Z0-9]*)\n([\s\S]*?)\n```", clean_response, re.IGNORECASE)
        if codeblocks:
            for idx, (filename_hint, lang, file_content) in enumerate(codeblocks, start=1):
                if file_content.strip():
                    if filename_hint and (filename_hint.endswith('.md') or filename_hint.endswith('.py') or filename_hint.endswith('.html')):
                        fname = os.path.basename(filename_hint)
                    else:
                        fname = f"modulo_{idx}.{'py' if lang == 'python' else ('html' if lang == 'html' else 'md')}"
                    
                    folder = "scripts" if lang == "python" else ("viz" if lang == "html" else "teoria")
                    clean_path = _determine_default_module_path(topic_slug, folder, fname)
                    _save_file_with_backup(clean_path, file_content)

    # Pattern 4: Fallback — save entire response as a structured topic file
    is_reasoning_only = clean_response.strip().startswith("Analyze User Input:") or clean_response.strip().startswith("Identify Constraints")
    should_fallback = not is_reasoning_only and (force_save or (
        len(clean_response) > 50
        and any(w in (prompt_topic + " " + clean_response[:200]).lower()
                for w in ('crea', 'genera', 'scrivi', 'file', 'argomento', 'modulo', 'teoria', 'script', 'documento'))
    ))
    if not created_paths and should_fallback:
        title_match = re.search(r'^#\s+(.+)', clean_response, re.MULTILINE)
        raw_title = title_match.group(1).strip() if title_match else raw_prompt or topic_slug
        file_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_title.lower()).strip('_')[:40] or topic_slug
        if file_slug in ('analyze_user_input', 'identify_constraints', 'documento'):
            file_slug = topic_slug
        
        clean_path = _determine_default_module_path(topic_slug, "teoria", f"{file_slug}.md")
        _save_file_with_backup(clean_path, clean_response)

    if created_paths:
        rebuild_modules_meta()

    return created_paths, actions_log


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

        msg_lower = message.lower().strip()

        # -------------------------------------------------------------------
        # DETERMINISTIC HANDLER 1: Deletion Requests (elimina / cancella / rimuovi)
        # -------------------------------------------------------------------
        _delete_keywords = ["elimina", "cancella", "rimuovi", "delete", "remove"]
        is_deletion = any(re.search(rf"\b{re.escape(w)}\b", msg_lower) for w in _delete_keywords)
        
        if is_deletion:
            log.info("Deterministic Deletion Request detected for prompt: %s", message)
            import shutil
            from core.data_handler import rebuild_modules_meta

            # Extract target name (e.g. "elimina l'argomento frattali" -> "frattali")
            raw_target = re.sub(
                r"^(?:elimina|cancella|rimuovi|delete|remove)\s+(?:l[\'\"]|il|lo|la|i|gli|le)?\s*(?:argomento|topic|modulo|file|cartella)?\s*(?:di|su)?\s*",
                "", msg_lower, flags=re.IGNORECASE
            ).strip()
            target_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_target).strip('_')

            deleted_paths = []
            if target_slug:
                # Check 1: Topic folder directly inside data/
                possible_topic = os.path.join("data", target_slug)
                if os.path.exists(possible_topic):
                    try:
                        shutil.rmtree(possible_topic)
                        deleted_paths.append(possible_topic.replace('\\', '/'))
                    except Exception as e:
                        log.error("Failed to delete topic folder %s: %s", possible_topic, e)
                
                # Check 2: Partial matches inside data/
                if not deleted_paths and os.path.exists("data"):
                    for entry in os.listdir("data"):
                        if entry.lower() == target_slug or target_slug in entry.lower():
                            full_p = os.path.join("data", entry)
                            try:
                                if os.path.isdir(full_p):
                                    shutil.rmtree(full_p)
                                else:
                                    os.remove(full_p)
                                deleted_paths.append(full_p.replace('\\', '/'))
                            except Exception as e:
                                log.error("Failed to delete %s: %s", full_p, e)

            if deleted_paths:
                rebuild_modules_meta()
                del_msg = f"🗑️ **Eliminazione completata su disco:**\n" + "\n".join([f"- Eliminata cartella/file `{p}`" for p in deleted_paths])
                actions_log = [{"type": "delete_file", "success": True, "path": p, "message": f"Eliminato {p}"} for p in deleted_paths]
                return self.send_json_response({
                    "response": del_msg,
                    "thinking": f"Richiesta di eliminazione eseguita con successo per: {raw_target}",
                    "actions_log": actions_log,
                    "created_files": [],
                    "error": None,
                    "manifesto_used": "sigma_architect",
                    "agent_name": "Sigma AI Architect",
                    "agent_id": "sigma_architect"
                })
            else:
                return self.send_json_response({
                    "response": f"⚠️ **Nessun elemento trovato:** Non è stato trovato alcun argomento o file corrispondente a `{raw_target or message}` nella cartella `data/`.",
                    "thinking": f"Ricerca elemento da eliminare fallita per: {message}",
                    "actions_log": [],
                    "created_files": [],
                    "error": None,
                    "manifesto_used": "sigma_architect",
                    "agent_name": "Sigma AI Architect",
                    "agent_id": "sigma_architect"
                })

        # -------------------------------------------------------------------
        # Auto-detect file creation requests: if user explicitly asks to create/write a file
        # -------------------------------------------------------------------
        user_requested_file_creation = False
        _create_keywords = [
            "crea un file", "crea file", "scrivi un file", "scrivi file",
            "crea un documento", "crea documento", "genera un file", "genera file",
            "crea un modulo", "crea modulo", "crea un argomento", "crea argomento",
            "salva in un file", "salva un file", "salva file", "salva su file",
        ]
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

        # --- Inject agent memory context with Sanitization & Role Isolation ---
        role_isolation = f"\n\nTASSATIVO: Il tuo UNICO ed ESCLUSIVO ruolo per questa risposta è l'agente '{manifesto_name}' come espresso nel System Prompt soprastante. Ignora qualsiasi nome di ruolo o istruzione di ruoli passati presente nella cronologia dei messaggi."
        system_parts.append(role_isolation)
        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        for h in history[-10:]:
            raw_c = h.get("content", "")
            sanitized_c = _sanitize_history_message(raw_c)
            if sanitized_c:
                messages.append({"role": h.get("role", "user"), "content": sanitized_c})

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
                    from core.ai_providers import check_ollama_vram_status
                    vram_info = check_ollama_vram_status(model, endpoint) if route_provider == "ollama" else {"loaded": True, "status_message": "⚡ Modello pronto"}
                    meta_payload = {
                        "meta": {
                            "agent_id": manifesto_name,
                            "agent_name": bot_name,
                            "manifesto_used": manifesto_name,
                            "web_search_active": web_search,
                            "model_status": vram_info.get("status_message", ""),
                            "model_loaded": vram_info.get("loaded", False),
                            "web_sources": [{"title": r["title"], "href": r["href"]} for r in web_sources_list]
                        }
                    }
                    self.wfile.write(f"data: {json.dumps(meta_payload)}\n\n".encode())
                    self.wfile.flush()
                    accumulated_response = ""
                    for chunk in chunks:
                        if chunk is None: self.wfile.write(b"data: [ERROR]\n\n"); break
                        if chunk.get("error"): self.wfile.write(f"data: {json.dumps({'error': chunk['message']})}\n\n".encode()); self.wfile.flush(); break
                        if "token" in chunk:
                            accumulated_response += chunk["token"]
                        if chunk.get("done"):
                            clean_res, _ = _clean_all_tags(accumulated_response)
                            created_paths, extracted_actions = _extract_and_create_files_from_text(clean_res, message, force_save=True)
                            if created_paths:
                                file_links = _format_conversational_summary(clean_res, created_paths)
                                self.wfile.write(f"data: {json.dumps({'token': file_links, 'created_files': created_paths, 'actions_log': extracted_actions})}\n\n".encode())
                                self.wfile.flush()
                            if chunk.get("truncated") or chunk.get("done_reason") == "length":
                                self.wfile.write(f"data: {json.dumps({'done': True, 'truncated': True, 'done_reason': 'length'})}\n\n".encode())
                            self.wfile.write(b"data: [DONE]\n\n")
                            self.wfile.flush()
                            break
                        payload = {}
                        if payload: self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode()); self.wfile.flush()
                    else:
                        clean_res, _ = _clean_all_tags(accumulated_response)
                        created_paths, extracted_actions = _extract_and_create_files_from_text(clean_res, message, force_save=True)
                        if created_paths:
                            file_links = _format_conversational_summary(clean_res, created_paths)
                            self.wfile.write(f"data: {json.dumps({'token': file_links, 'created_files': created_paths, 'actions_log': extracted_actions})}\n\n".encode())
                            self.wfile.flush()
                        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError) as sock_err:
                    log.info("Client disconnected during SSE stream: %s", sock_err)
                except Exception as ex:
                    log.warning("SSE Stream write error: %s", ex)
                    try:
                        self.wfile.write(b"data: [ERROR]\n\n")
                        self.wfile.flush()
                    except Exception:
                        pass
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
            return self.send_json_response({"response": f"âš ï¸  Errore IA ({provider}): {error}", "actions_log": [], "error": error, "manifesto_used": manifesto_name})

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

            # Extract and save files automatically from plain chat response with backup & diff
            created_paths, extracted_actions = _extract_and_create_files_from_text(clean_response, message, force_save=True)
            actions_log = extracted_actions
            if created_paths:
                clean_response = _format_conversational_summary(clean_response, created_paths)

            log.debug("ASK mode: response_len=%d thinking=%s created_files=%d", len(clean_response), 'yes' if thinking else 'none', len(created_paths))
            manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
            self.send_json_response({
                "response": clean_response,
                "thinking": thinking,
                "actions_log": actions_log,
                "created_files": created_paths,
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
                    # FIX: use manifesto_name (agent_id was never defined in this scope)
                    _agent_mem_id = manifesto_name
                    if _agent_mem_id:
                        success_count = sum(1 for a in actions_log if a.get("success"))
                        fail_count = sum(1 for a in actions_log if not a.get("success"))
                        try:
                            save_session_memory(_agent_mem_id, {
                                "goal": message[:200],
                                "actions_performed": actions_log,
                                "success_count": success_count,
                                "fail_count": fail_count,
                                "learning": "",
                                "summary": f"{success_count} azioni riuscite, {fail_count} fallite"
                            })
                            # Update agent usage stats
                            increment_usage(_agent_mem_id, success=fail_count == 0)
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
            # FIX: force_save=True when user explicitly asked to create/write a file, so Pattern 4 fallback always fires
            created_files = []
            if len(clean_response) > 30:
                has_path_marker = ("data/" in clean_response or "Path:" in clean_response or "Percorso:" in clean_response)
                should_extract = user_requested_file_creation or has_path_marker
                if should_extract:
                    try:
                        created_files = _extract_and_create_files_from_text(
                            clean_response,
                            prompt_topic=message[:60],
                            force_save=user_requested_file_creation,
                        )
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
