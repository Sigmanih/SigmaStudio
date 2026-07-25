# ==============================================================================
# core/chat/chat_runner.py — Conversational Chat Runner & Streaming Engine
# Sigma Studio v8 — Modular Chat Sub-package
# ==============================================================================
"""AI chat conversation engine with multi-provider model routing, action execution,
file creation tracking, SSE streaming, and deterministic command handlers.
"""

import os
import json
import re
import datetime
import shutil

from core.logger import get_logger
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
from core.data_handler import rebuild_modules_meta
from core.backup_manager import create_backup
from core.task_handler import _compute_diff

from core.chat.response_parser import (
    _TAG_PATTERNS, _clean_all_tags, _extract_json_from_response,
    _extract_english_thinking, _extract_bullet_thinking, _extract_done_thinking,
    _format_response,
)
from core.chat.prompt_builder import (
    _get_time_context, _get_manifesto_content, _build_filesystem_context,
    _collect_context_files, _resolve_manifesto_for_model, _determine_agent_by_request,
    _build_agent_identity_header,
)
from core.chat.file_extractor import (
    _normalize_data_path, _ensure_module_subfolders, _determine_default_module_path,
    _generate_files_summary, _format_conversational_summary, _extract_and_create_files_from_text,
)
from core.chat.web_search import _perform_web_search

log = get_logger(__name__)


def _sanitize_history_message(content: str) -> str:
    """Sanitize history messages to remove old system prompts, role headers, welcome badges, and reasoning monologues."""
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


def handle_chat(self):
    """POST /api/chat — Send message to AI agent and execute actions."""
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

        _delete_keywords = ["elimina", "cancella", "rimuovi", "delete", "remove"]
        is_deletion = any(re.search(rf"\b{re.escape(w)}\b", msg_lower) for w in _delete_keywords)
        
        if is_deletion:
            log.info("Deterministic Deletion Request detected for prompt: %s", message)

            raw_target = re.sub(
                r"^(?:elimina|cancella|rimuovi|delete|remove)\s+(?:l[\'\"]|il|lo|la|i|gli|le)?\s*(?:argomento|topic|modulo|file|cartella)?\s*(?:di|su)?\s*",
                "", msg_lower, flags=re.IGNORECASE
            ).strip()
            target_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_target).strip('_')

            deleted_paths = []
            if target_slug:
                possible_topic = os.path.join("data", target_slug)
                if os.path.exists(possible_topic):
                    try:
                        shutil.rmtree(possible_topic)
                        deleted_paths.append(possible_topic.replace('\\', '/'))
                    except Exception as e:
                        log.error("Failed to delete topic folder %s: %s", possible_topic, e)
                
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
                    "thinking": f"Impossibile trovare il target di eliminazione: {raw_target}",
                    "actions_log": [],
                    "created_files": [],
                    "error": "Elemento non trovato",
                    "manifesto_used": "sigma_architect",
                    "agent_name": "Sigma AI Architect",
                    "agent_id": "sigma_architect"
                })

        ai_cfg = load_ai_config()
        active_provider = ai_cfg.get("active_provider", "ollama")
        model = model_override or ai_cfg.get("active_model") or ai_cfg.get("model") or ""

        if not model:
            prov_cfg = ai_cfg.get("providers", {}).get(active_provider, {})
            model = prov_cfg.get("model") or "llama3.2"

        detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
        if detected_prov:
            active_provider = detected_provider
            active_prov_cfg = detected_prov
        else:
            active_prov_cfg = ai_cfg.get("providers", {}).get(active_provider, {})

        system_prompt = _get_manifesto_content(manifesto_path)
        time_ctx = _get_time_context()
        fs_context = _build_filesystem_context()

        user_name = req.get('user_name') or req.get('user_profile', {}).get('name')
        user_title = req.get('user_title') or req.get('user_profile', {}).get('title')
        identity_header = _build_agent_identity_header(user_name, user_title)

        # Integration with MCP Hub (Hardware VRAM Guard & Memory MCP RAG)
        mcp_context_info = ""
        try:
            from core.mcp import mcp_hub
            # 1. Hardware MCP VRAM Check
            hw_server = mcp_hub.get_server("Hardware MCP")
            if hw_server:
                hw_status = hw_server.call_tool("get_hardware_status")
                # Pre-warm or clean VRAM if needed

            # 2. Memory MCP Context Retrieval
            mem_server = mcp_hub.get_server("Memory MCP")
            if mem_server and message:
                rag_res = mem_server.call_tool("query_vector_db", {"query": message, "limit": 3})
                if rag_res and not rag_res.get("isError"):
                    mcp_context_info += f"\n\n## 🧠 CONTESTO RECUPERATO DA MEMORY MCP:\n{json.dumps(rag_res.get('results', []), indent=2)}\n"

            # 3. Available MCP Tools List Injection
            mcp_tools = mcp_hub.get_aggregated_tools()
            tools_desc = "\n".join([f"- {t['name']} [{t.get('server', 'MCP')}]: {t['description']}" for t in mcp_tools[:8]])
            mcp_context_info += f"\n\n## ⚡ MCP TOOLS & STRUMENTI ATTIVI NELL'HUB:\n{tools_desc}\n"
        except Exception as mcp_err:
            log.debug("MCP Hub chat pipeline enrichment skipped: %s", mcp_err)

        full_prompt = f"""{identity_header}

{system_prompt}

## STRUTTURA PROGETTO
{fs_context}

## ORA CORRENTE
{time_ctx}{mcp_context_info}

## ISTRUZIONI CREAZIONE E SALVATAGGIO FILE SU DISCO
Quando l'utente ti chiede di creare, scrivere o generare un file o un argomento, DEVI SEMPRE specificare il percorso relativo esplicito direttamente nella cartella dell'argomento (es. `data/ARGOMENTO/NOME_FILE.md`) e racchiudere il contenuto completo all'interno di un blocco di codice markdown:

Path: `data/ARGOMENTO/NOME_FILE.md`
```markdown
# Titolo del Documento
Contenuto completo...
```
"""

        messages = [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": message}
        ]

        if active_provider == "ollama":
            ai_response, thinking, err = call_ollama(
                messages, model,
                endpoint=active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat"),
                temperature=active_prov_cfg.get("temperature", 0.7),
                max_tokens=active_prov_cfg.get("max_tokens", 4096),
                top_p=active_prov_cfg.get("top_p", 0.9),
                timeout=active_prov_cfg.get("timeout", 300)
            )
        elif active_provider == "anthropic":
            ai_response, thinking, err = call_anthropic(
                messages, model,
                api_key=active_prov_cfg.get("api_key", ""),
                temperature=active_prov_cfg.get("temperature", 0.7),
                max_tokens=active_prov_cfg.get("max_tokens", 4096),
                timeout=active_prov_cfg.get("timeout", 300)
            )
        else:
            ai_response, thinking, err = call_openai_compatible(
                messages, model,
                api_url=active_prov_cfg.get("api_url") or active_prov_cfg.get("endpoint", ""),
                api_key=active_prov_cfg.get("api_key", ""),
                temperature=active_prov_cfg.get("temperature", 0.7),
                max_tokens=active_prov_cfg.get("max_tokens", 4096),
                top_p=active_prov_cfg.get("top_p", 0.9),
                timeout=active_prov_cfg.get("timeout", 300)
            )

        if err:
            return self.send_json_response({"error": err}, 500)

        created_files = []
        actions_log = []
        if allow_actions and ai_response:
            created_files, actions_log = _extract_and_create_files_from_text(ai_response, prompt_topic=message)

        formatted_res = _format_response(ai_response)
        if created_files:
            formatted_res = _format_conversational_summary(formatted_res, created_files)

        return self.send_json_response({
            "response": formatted_res,
            "thinking": thinking or "",
            "actions_log": actions_log,
            "created_files": created_files,
            "error": None,
            "manifesto_used": manifesto_path,
            "agent_name": bot_name,
            "agent_id": bot_name.lower().replace(" ", "_")
        })

    except Exception as exc:
        log.error("Unhandled error in handle_chat: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)


def handle_chat_extract_files(self):
    """POST /api/chat/extract_files — Extract and save files from completed chat response text."""
    try:
        req = self.read_json_body()
        text = req.get("text", "").strip()
        prompt_topic = req.get("prompt_topic", "").strip()
        if not text:
            return self.send_json_response({"created_files": [], "actions_log": []})

        created_files, actions_log = _extract_and_create_files_from_text(text, prompt_topic=prompt_topic)
        return self.send_json_response({
            "success": True,
            "created_files": created_files,
            "actions_log": actions_log
        })
    except Exception as exc:
        log.error("handle_chat_extract_files error: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)
