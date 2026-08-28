# ==============================================================================
# core/developer_studio/admin_agent.py — Multi-Step Autonomous AI Developer Agent
# Sigma Studio v8 — Developer Studio AI Pair Programmer & Multi-Turn Tool Loop
# ==============================================================================
"""Provides the autonomous Admin Developer Agent that performs multi-turn coding,
file modifications with diff generation, and terminal executions across the workspace.
"""

import os
import re
import json
import time
import difflib
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Generator

from core.logger import get_logger
from core.developer_studio.fs_manager import (
    read_file_content,
    write_file_content,
    delete_fs_entry,
    create_fs_entry,
    get_workspace_tree,
    search_workspace_files,
    get_default_workspace_root,
    restore_file_backup,
    list_file_backups,
)
from core.developer_studio.terminal_runner import execute_shell_command_sync

log = get_logger("admin_developer_agent")

# Maximum characters of a single tool observation fed back to the model.
# Without this cap a broad search or a verbose command can inflate the prompt
# until RAM saturates and inference stalls.
MAX_OBSERVATION_CHARS = 4000
MAX_HISTORY_CHARS = 24000

ADMIN_DEVELOPER_SYSTEM_PROMPT = """Sei Σ-SIGMA Developer Admin, un Pair-Programmer e Software Architect esperto integrato nativamente in Sigma Studio.
Hai permessi di AMMINISTRATORE completi sul workspace per esplorare la struttura, leggere, creare, modificare, eliminare file ed eseguire comandi da terminale (PowerShell/Bash).

REGOLE CRITICHE E OBBLIGATORIE:
1. Rispondi SEMPRE ed ESCLUSIVAMENTE in lingua ITALIANA.
2. Ragiona internamente all'interno dei tag <think> ... </think>. NON scrivere mai ragionamenti in inglese al di fuori dei tag <think>.
3. Quando ricevi una richiesta di sviluppo o modifica:
   - FASE 1: Esplora il workspace con `list_dir`, `read_file` o `search_code` per capire la struttura esistente.
   - FASE 2: Definisci la pipeline dei task da fare (tutti con status "pending" o "in_progress").
   - FASE 3: Esegui le modifiche necessarie scrivendo file completi con `write_file` o eseguendo comandi con `terminal`.
   - FASE 4: Solo quando tutti i file sono stati REALMENTE creati/modificati e verificati, emetti `complete_goal`.
4. NON dichiarare MAI un task o un obiettivo completato senza aver PRIMA letto o scritto file reali con i tool.
5. NON emettere MAI `complete_goal` al primo turno di una richiesta di sviluppo.

GUIDA AI PERCORSI:
- La radice del workspace si indica con "." (oppure percorsi relativi come "core", "sigma_studio/src").
- I percorsi dei file sono relativi alla radice del workspace (es. "sigma_server.py", "core/api_router.py", "package.json").

TAG STRUTTURATI DEI TOOL:

1. Per esplorare una cartella (usa "." per la radice):
```tool:list_dir
{
  "path": "."
}
```

2. Per leggere un file esistente:
```tool:read_file
{
  "path": "ARCHITECTURE.md"
}
```

3. Per scrivere o creare un file:
```tool:write_file
{
  "path": "core/modules/mio_modulo/handlers.py",
  "content": "# codice completo qui"
}
```

4. Per definire la pipeline dei task da eseguire:
```tool:pipeline
{
  "tasks": [
    {"id": "1", "title": "Esplorazione struttura moduli esistenti", "status": "in_progress"},
    {"id": "2", "title": "Creazione backend e route", "status": "pending"},
    {"id": "3", "title": "Creazione interfaccia frontend", "status": "pending"},
    {"id": "4", "title": "Verifica e test", "status": "pending"}
  ]
}
```

5. Per eseguire un comando terminale (PowerShell):
```tool:terminal
{
  "command": "python -m pytest tests/ -v",
  "cwd": "."
}
```

6. Per cercare codice nel workspace:
```tool:search_code
{
  "query": "class NetworkLab"
}
```

7. Per eliminare un file temporaneo:
```tool:delete
{
  "path": "scratch/temp.txt"
}
```

7. Per ripristinare un file allo stato di backup precedente (se una modifica ha causato errori):
```tool:restore_file
{
  "path": "sigma_server.py"
}
```

8. Per visualizzare lo storico dei backup di un file o del workspace:
```tool:list_backups
{
  "path": "sigma_server.py"
}
```

9. Per dichiarare il completamento:
```tool:complete_goal
{
  "summary": "Implementazione completata con successo e verificata."
}
```
"""


def resolve_workspace_path(path: Optional[str], workspace_root: str) -> str:
    """Normalizes and safely resolves paths within the workspace root."""
    if not workspace_root:
        workspace_root = get_default_workspace_root()
    workspace_root = os.path.abspath(workspace_root)

    if not path or not isinstance(path, str):
        return workspace_root

    clean = path.strip().strip("'\"`")
    if clean in (
        "", ".", "./", ".\\", "/", "\\", "percorso cartella", "percorso_cartella",
        "percorso del file", "percorso_file", "percorso da eliminare",
        "root", "workspace", "project", "folder_path", "file_path", "null", "undefined"
    ):
        return workspace_root

    # Strip redundant leading slashes and prefix words
    clean = re.sub(r"^[./\\]+", "", clean)
    clean = re.sub(r"^(?:Sigma_Studio|SigmaStudio|workspace)[/\\]", "", clean, flags=re.IGNORECASE)

    if os.path.isabs(clean):
        return os.path.abspath(clean)

    norm = os.path.normpath(os.path.join(workspace_root, clean))
    return norm


def normalize_tool_params(raw_body: str, tool_name: str) -> Dict[str, Any]:
    """Safely extracts JSON or fallback dictionary from tool body."""
    raw_body = raw_body.strip()
    try:
        data = json.loads(raw_body)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            if tool_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                return {"tasks": data}
            return {"items": data}
    except Exception:
        pass

    # Try extracting JSON object {...} or [...] inside text
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw_body)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and tool_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                return {"tasks": data}
        except Exception:
            pass

    # Fallback to key-value or raw mapping
    if tool_name in ("terminal", "shell", "exec", "command"):
        return {"command": raw_body}
    elif tool_name in ("read_file", "read", "delete", "list_dir", "ls"):
        return {"path": raw_body}
    elif tool_name in ("search_code", "grep"):
        return {"query": raw_body}
    elif tool_name in ("pipeline", "tasks", "set_tasks"):
        lines = [l.strip("- *0123456789.) ").strip() for l in raw_body.splitlines() if l.strip()]
        tasks = [{"id": str(i+1), "title": l, "status": "pending"} for i, l in enumerate(lines)]
        return {"tasks": tasks}

    return {"raw": raw_body}


def extract_tool_invocations(text: str) -> List[Dict[str, Any]]:
    """Extracts structured tool calls from model output (code blocks, XML, JSON)."""
    tools = []

    # 1. Matches ```tool:name ... ```
    tool_named_block = re.compile(r"```tool:(\w+)\s*([\s\S]*?)```", re.IGNORECASE)
    for match in tool_named_block.finditer(text):
        tool_name = match.group(1).lower()
        body = match.group(2)
        params = normalize_tool_params(body, tool_name)
        tools.append({"tool": tool_name, "params": params, "raw_block": match.group(0)})

    # 2. Matches ```tool\n...``` or ```json\n{"tool": "..."}``` or ```json\n{"action": "..."}```
    if not tools:
        generic_block = re.compile(r"```(?:tool|json|bash|sh|powershell)?\s*([\s\S]*?)```", re.IGNORECASE)
        for match in generic_block.finditer(text):
            body = match.group(1).strip()
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    tool_name = (
                        data.get("tool") or data.get("action") or data.get("name") or data.get("tool_name") or ""
                    ).lower()
                    if tool_name:
                        params = data.get("parameters") or data.get("arguments") or data.get("params") or data.get("action_input") or data
                        tools.append({"tool": tool_name, "params": params, "raw_block": match.group(0)})
            except Exception:
                json_match = re.search(r"(\{[\s\S]*\})", body)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        if isinstance(data, dict):
                            tool_name = (
                                data.get("tool") or data.get("action") or data.get("name") or data.get("tool_name") or ""
                            ).lower()
                            if tool_name:
                                params = data.get("parameters") or data.get("arguments") or data.get("params") or data.get("action_input") or data
                                tools.append({"tool": tool_name, "params": params, "raw_block": match.group(0)})
                    except Exception:
                        pass

    # 3. Matches <tool_call>\n<name>...</name>\n<arguments>...</arguments>\n</tool_call>
    if not tools:
        xml_tool_calls = re.findall(r"<tool_call>([\s\S]*?)</tool_call>", text, re.IGNORECASE)
        for tc in xml_tool_calls:
            try:
                data = json.loads(tc.strip())
                if isinstance(data, dict) and ("name" in data or "tool" in data):
                    t_name = (data.get("name") or data.get("tool", "")).lower()
                    t_args = data.get("arguments") or data.get("parameters") or data
                    tools.append({"tool": t_name, "params": t_args, "raw_block": f"<tool_call>{tc}</tool_call>"})
                    continue
            except Exception:
                pass

            name_m = re.search(r"<name>([\s\S]*?)</name>", tc, re.IGNORECASE)
            args_m = re.search(r"<arguments>([\s\S]*?)</arguments>", tc, re.IGNORECASE)
            if name_m:
                t_name = name_m.group(1).strip().lower()
                raw_args = args_m.group(1).strip() if args_m else ""
                params = normalize_tool_params(raw_args, t_name)
                tools.append({"tool": t_name, "params": params, "raw_block": f"<tool_call>{tc}</tool_call>"})

    # 4. Matches XML-style <execute_command>, <read_file>, <write_file>, <list_dir>, <delete>, <search_code>, <pipeline>
    if not tools:
        for tag in ["terminal", "shell", "execute_command", "read_file", "write_file", "write_to_file", "delete", "list_dir", "search_code", "pipeline"]:
            m = re.search(rf"<{tag}>\s*([\s\S]*?)\s*</{tag}>", text, re.IGNORECASE)
            if m:
                raw_content = m.group(1).strip()
                t_name = "terminal" if tag in ("shell", "execute_command") else ("write_file" if tag == "write_to_file" else tag)
                params = normalize_tool_params(raw_content, t_name)
                tools.append({"tool": t_name, "params": params, "raw_block": m.group(0)})

    return tools


def execute_admin_tool(
    tool_name: str,
    params: Dict[str, Any],
    workspace_root: str,
    should_cancel: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """Executes a single admin developer tool with full workspace resolution."""
    tool_name = tool_name.lower()
    
    if tool_name in ("terminal", "shell", "exec", "command"):
        cmd = params.get("command") or params.get("raw", "")
        raw_cwd = params.get("cwd") or "."
        cwd = resolve_workspace_path(raw_cwd, workspace_root)
        res = execute_shell_command_sync(cmd, cwd=cwd)
        return {
            "tool": "terminal",
            "command": cmd,
            "cwd": cwd,
            "success": res.get("success", False),
            "stdout": res.get("stdout", ""),
            "stderr": res.get("stderr", ""),
            "returncode": res.get("returncode", 0)
        }

    elif tool_name in ("read_file", "read"):
        raw_path = params.get("path") or params.get("raw", "")
        full_path = resolve_workspace_path(raw_path, workspace_root)
        
        # If full_path is a directory instead of a file, fall back to list_dir gracefully
        if os.path.isdir(full_path):
            tree = get_workspace_tree(full_path, max_depth=1)
            entries = [f"{'📁' if c.get('is_dir') else '📄'} {c.get('name')}" for c in tree.get("children", [])]
            return {
                "tool": "read_file",
                "path": raw_path,
                "success": True,
                "content": f"'{raw_path}' è una cartella contenente:\n" + "\n".join(entries),
                "message": f"'{raw_path}' è una cartella con {len(entries)} elementi."
            }

        res = read_file_content(full_path)
        return {"tool": "read_file", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("write_file", "write", "save_file"):
        raw_path = params.get("path") or ""
        content = params.get("content") or params.get("raw", "")
        full_path = resolve_workspace_path(raw_path, workspace_root)

        # Create parent directories automatically
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        diff_text = None
        if os.path.exists(full_path):
            try:
                old_content = Path(full_path).read_text(encoding="utf-8", errors="replace")
                diff = difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{Path(full_path).name}",
                    tofile=f"b/{Path(full_path).name}"
                )
                diff_text = "".join(diff)
            except Exception:
                pass

        res = write_file_content(full_path, content, root=workspace_root)
        return {
            "tool": "write_file",
            "path": raw_path,
            "full_path": full_path,
            "diff": diff_text,
            **res
        }

    elif tool_name in ("delete", "delete_file", "remove_file", "rm"):
        raw_path = params.get("path") or params.get("raw", "")
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = delete_fs_entry(full_path, root=workspace_root)
        return {"tool": "delete", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("list_dir", "list_directory", "ls"):
        raw_path = params.get("path") or params.get("raw", "")
        full_path = resolve_workspace_path(raw_path, workspace_root)
        
        display_rel = os.path.relpath(full_path, workspace_root) if os.path.exists(full_path) else (raw_path or ".")
        if display_rel == ".":
            display_rel = "root workspace"

        tree = get_workspace_tree(full_path, max_depth=2)
        
        # Build readable list of entries with details
        entries = []
        if tree and "children" in tree:
            for c in tree["children"]:
                is_d = c.get("is_dir", False)
                sub_count = len(c.get("children", []))
                if is_d:
                    entries.append(f"📁 {c.get('name')} (cartella{f', ~{sub_count} elementi' if sub_count else ''})")
                else:
                    size_kb = round(c.get("size", 0) / 1024, 1)
                    entries.append(f"📄 {c.get('name')}{f' ({size_kb} KB)' if size_kb else ''}")

        return {
            "tool": "list_dir",
            "path": raw_path or ".",
            "full_path": full_path,
            "entries": entries,
            "tree": tree,
            "success": True,
            "message": f"Trovati {len(entries)} elementi in '{display_rel}'."
        }

    elif tool_name in ("search_code", "grep"):
        query = (params.get("query") or params.get("pattern") or params.get("raw", "") or "").strip()
        raw_path = params.get("path") or "."
        full_path = resolve_workspace_path(raw_path, workspace_root)
        if not query:
            return {
                "tool": "search_code", "query": "", "path": raw_path, "success": False,
                "results": [],
                "error": "Nessun termine di ricerca fornito: specifica il campo 'query'."
            }
        res = search_workspace_files(full_path, query, should_cancel=should_cancel)
        return {"tool": "search_code", "query": query, "path": raw_path, **res}

    elif tool_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
        raw_tasks = params.get("tasks") or params.get("task_list") or params.get("pipeline") or params.get("items") or []
        if isinstance(raw_tasks, str):
            try:
                raw_tasks = json.loads(raw_tasks)
            except Exception:
                lines = [l.strip("- *0123456789.) ").strip() for l in raw_tasks.splitlines() if l.strip()]
                raw_tasks = [{"id": str(i+1), "title": l, "status": "pending"} for i, l in enumerate(lines)]

        normalized_tasks = []
        if isinstance(raw_tasks, list):
            for i, t in enumerate(raw_tasks):
                if isinstance(t, dict):
                    t_id = str(t.get("id") or (i + 1))
                    t_title = str(t.get("title") or t.get("name") or t.get("task") or f"Task {i+1}")
                    t_status = str(t.get("status") or "pending").lower()
                    if t_status not in ("pending", "in_progress", "done"):
                        t_status = "done" if "complet" in t_status or "done" in t_status else ("in_progress" if "prog" in t_status or "corr" in t_status else "pending")
                    normalized_tasks.append({"id": t_id, "title": t_title, "status": t_status})
                elif isinstance(t, str) and t.strip():
                    normalized_tasks.append({"id": str(i+1), "title": t.strip(), "status": "pending"})

        return {
            "tool": "pipeline",
            "tasks": normalized_tasks,
            "success": True,
            "message": f"Pipeline aggiornata con {len(normalized_tasks)} sotto-task."
        }

    elif tool_name in ("restore_file", "undo_file", "restore_backup", "revert_file"):
        raw_path = params.get("path") or params.get("file_path") or params.get("target") or ""
        backup_id = params.get("backup_id")
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = restore_file_backup(full_path, backup_id=backup_id, root=workspace_root)
        return {"tool": "restore_file", "path": raw_path, **res}

    elif tool_name in ("list_backups", "get_backups", "backup_history"):
        raw_path = params.get("path") or params.get("file_path")
        full_path = resolve_workspace_path(raw_path, workspace_root) if raw_path else None
        backups = list_file_backups(full_path, root=workspace_root, limit=20)
        return {
            "tool": "list_backups",
            "path": raw_path or "tutti",
            "count": len(backups),
            "backups": backups,
            "success": True,
            "message": f"Trovati {len(backups)} snapshot di backup."
        }

    elif tool_name in ("complete_goal", "finish_task", "task_complete"):
        summary = params.get("summary") or params.get("message") or "Obiettivo completato con successo."
        return {
            "tool": "complete_goal",
            "summary": summary,
            "is_completed": True,
            "success": True,
            "message": summary
        }

    return {"tool": tool_name, "success": False, "error": f"Tool sconosciuto: {tool_name}"}


def stream_admin_agent_turn(
    messages: List[Dict[str, str]],
    workspace_root: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    auto_execute_tools: bool = True,
    max_turns: int = 8,
    should_cancel: Optional[Callable[[], bool]] = None,
    system_prompt_override: Optional[str] = None,
    current_pipeline: Optional[List[Dict[str, Any]]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Multi-Turn Autonomous Admin Developer Agent Loop:
    1. Sends conversation history + Admin prompt to SigmaEngine.
    2. Streams reasoning (<think>...) and response tokens.
    3. If a tool call is detected: executes it, emits the tool event, and automatically
       feeds the observation back to the model to produce the final conversational answer!
    """
    if not workspace_root:
        workspace_root = get_default_workspace_root()

    def _cancelled() -> bool:
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    from core.engine.unified_runtime import sigma_engine

    # Prepare conversation history
    # Allow Role Engine to inject role-specific system prompts
    active_system_prompt = system_prompt_override or ADMIN_DEVELOPER_SYSTEM_PROMPT

    # Inject current pipeline status if present
    if current_pipeline and isinstance(current_pipeline, list) and len(current_pipeline) > 0:
        pipeline_lines = ["\n## 📋 STATO ATTUALE DELLA PIPELINE DEI TASK:"]
        for p in current_pipeline:
            pid = p.get("id", "")
            title = p.get("title", "")
            desc = p.get("description", "")
            status = p.get("status", "pending")
            status_tag = "✅ FATTO" if status == "done" else ("⚡ IN CORSO" if status == "in_progress" else "⏳ IN CODA")
            line = f"- [{status_tag}] Task #{pid}: {title}"
            if desc and desc != title:
                line += f" — Dettagli: {desc}"
            pipeline_lines.append(line)
        pipeline_lines.append("\nPuoi aggiornare la pipeline (modificare stati, descrizioni o aggiungere task) usando il tool `pipeline`.")
        active_system_prompt = active_system_prompt + "\n" + "\n".join(pipeline_lines)

    # Append MCP developer tools section if available
    try:
        from core.developer_studio.mcp_tools.bridge import build_mcp_tools_section
        mcp_section = build_mcp_tools_section()
        if mcp_section:
            active_system_prompt = active_system_prompt + "\n" + mcp_section
    except Exception:
        pass  # MCP tools not yet registered — proceed without them

    full_messages = [{"role": "system", "content": active_system_prompt}]
    for m in messages:
        if m.get("role") != "system":
            m_content = m.get("content", "")
            attachments = m.get("attachments", [])
            if attachments:
                att_texts = []
                for att in attachments:
                    att_name = att.get("name") or att.get("filename") or "allegato"
                    att_content = att.get("content") or ""
                    att_path = att.get("path") or ""
                    if att_content:
                        att_texts.append(f"--- FILE ALLEGATO: {att_name} ---\n```\n{att_content[:35000]}\n```")
                    elif att_path:
                        att_texts.append(f"--- RIFERIMENTO FILE ALLEGATO: {att_path} ---")
                if att_texts:
                    m_content = f"{m_content}\n\n" + "\n\n".join(att_texts)
            full_messages.append({"role": m.get("role", "user"), "content": m_content})

    def trim_history(msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Sliding window so the prompt never grows unbounded across tool turns."""
        if len(msgs) <= 2:
            return msgs
        system_msg = msgs[0]
        conversation = msgs[1:]
        while len(conversation) > 2 and sum(len(m.get("content", "")) for m in conversation) > MAX_HISTORY_CHARS:
            conversation.pop(0)
        return [system_msg] + conversation

    full_messages = trim_history(full_messages)

    last_user_prompt = full_messages[-1].get("content", "") if len(full_messages) > 1 else "Ciao"

    current_turn = 0
    total_generated_tokens = 0
    t_turn_start = time.perf_counter()
    overall_first_token_time = None

    while current_turn < max_turns:
        if _cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return
        current_turn += 1
        accumulated_response = []
        in_think_block = False
        in_tool_block = False
        has_notified_tool = False
        turn_tokens = 0
        turn_first_token_time = None
        t_call_start = time.perf_counter()

        yield {"type": "turn_start", "turn": current_turn}
        if current_turn == 1:
            yield {"type": "status", "text": f"🧠 Preparazione e caricamento modello ({model_name or 'sigmaengine'})..."}
        else:
            yield {"type": "status", "text": "🔍 Sintesi e formattazione risposta..."}

        try:
            for chunk in sigma_engine.generate_stream(
                prompt=last_user_prompt,
                system_prompt=active_system_prompt,
                temperature=temperature,
                max_tokens=4096,
                model_name=model_name or "sigmaengine",
                messages=full_messages
            ):
                if chunk.get("model_status") or (chunk.get("status") and chunk.get("text")):
                    status_text = chunk.get("model_status") or chunk.get("text")
                    if status_text:
                        yield {"type": "status", "text": status_text}

                if _cancelled():
                    yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
                    return

                token = chunk.get("token", "")
                if not token:
                    continue

                if turn_first_token_time is None:
                    turn_first_token_time = time.perf_counter()
                    if overall_first_token_time is None:
                        overall_first_token_time = turn_first_token_time

                turn_tokens += 1
                total_generated_tokens += 1
                accumulated_response.append(token)

                # Filter thinking tags
                if "<think>" in token:
                    in_think_block = True
                    cleaned = token.replace("<think>", "")
                    if cleaned:
                        yield {"type": "thought", "token": cleaned}
                    continue
                elif "</think>" in token:
                    in_think_block = False
                    cleaned = token.replace("</think>", "")
                    if cleaned:
                        yield {"type": "token", "token": cleaned}
                    continue

                if in_think_block:
                    yield {"type": "thought", "token": token}
                    continue

                # Detect if entering or inside a structured tool block (```tool: or XML tags)
                current_text = "".join(accumulated_response)
                
                if not in_tool_block:
                    if "```tool:" in token or "```tool:" in current_text[-25:]:
                        in_tool_block = True
                    elif re.search(r"<(?:execute_command|shell|terminal|read_file|write_to_file|list_dir|search_code|tool)>", current_text[-35:]):
                        in_tool_block = True

                if in_tool_block:
                    if not has_notified_tool:
                        has_notified_tool = True
                        yield {"type": "status", "text": "⚡ Generazione ed esecuzione azione..."}
                    
                    # Check if tool block closed
                    if "```" in token and current_text.count("```") % 2 == 0:
                        in_tool_block = False
                    elif re.search(r"</(?:execute_command|shell|terminal|read_file|write_to_file|list_dir|search_code|tool)>", current_text[-45:]):
                        in_tool_block = False
                    continue

                yield {"type": "token", "token": token}

        except Exception as e:
            yield {"type": "error", "error": f"Errore inferenza: {str(e)}"}
            return

        # Calculate metrics for this generation pass
        t_now = time.perf_counter()
        gen_duration = max(t_now - (turn_first_token_time or t_call_start), 0.001)
        tps = round(turn_tokens / gen_duration, 1) if turn_tokens > 0 else 0.0
        ttft_ms = round(((turn_first_token_time or t_now) - t_call_start) * 1000, 1)

        yield {
            "type": "metrics",
            "tps": tps,
            "ttft_ms": ttft_ms,
            "tokens": turn_tokens,
            "total_tokens": total_generated_tokens,
            "duration_s": round(t_now - t_turn_start, 2)
        }

        full_text = "".join(accumulated_response)

        # Detect tools
        tools_found = extract_tool_invocations(full_text)
        if not tools_found or not auto_execute_tools:
            # Finished - no tools requested
            break

        # Execute tools and prepare observation for next turn
        tool_observations = []
        for t in tools_found:
            if _cancelled():
                yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
                return
            t_name = t["tool"]
            t_params = t["params"]
            
            yield {
                "type": "tool_start",
                "tool": t_name,
                "params": t_params
            }

            # Route through MCP Hub for Git/Lint/Test tools, local for FS/Terminal
            try:
                from core.developer_studio.mcp_tools.bridge import is_mcp_tool, execute_via_mcp
                if is_mcp_tool(t_name):
                    result = execute_via_mcp(t_name, t_params)
                else:
                    result = execute_admin_tool(t_name, t_params, workspace_root, should_cancel=should_cancel)
            except ImportError:
                result = execute_admin_tool(t_name, t_params, workspace_root, should_cancel=should_cancel)

            yield {
                "type": "tool_result",
                "tool": t_name,
                "result": result
            }

            if t_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                yield {
                    "type": "pipeline_update",
                    "tasks": result.get("tasks", [])
                }
            elif t_name in ("complete_goal", "finish_task", "task_complete"):
                # If complete_goal is called on turn 1 without any prior action, reject it
                if current_turn <= 1 and not any(t["tool"] in ("write_file", "terminal", "read_file", "search_code") for t in tools_found):
                    result = {
                        "tool": "complete_goal",
                        "success": False,
                        "error": "Azione prematura: prima di completare l'obiettivo devi eseguire le modifiche ai file con write_file o verificare la struttura con list_dir/read_file."
                    }
                else:
                    yield {
                        "type": "goal_complete",
                        "summary": result.get("summary", "")
                    }

            # Format concise observation for the model
            obs_str = f"Tool '{t_name}' eseguito con successo.\n"
            if t_name == "list_dir":
                obs_str += f"Elementi trovati in '{result.get('path')}':\n" + "\n".join(result.get("entries", [])[:40])
            elif t_name == "read_file":
                content_preview = str(result.get("content", ""))[:2000]
                obs_str += f"Contenuto di '{result.get('path')}':\n{content_preview}"
            elif t_name == "terminal":
                obs_str += f"Output terminale (exit code {result.get('returncode')}):\n{result.get('stdout', '')}\n{result.get('stderr', '')}"
            elif t_name == "delete":
                obs_str += result.get("message", "Eliminato.")
            elif t_name == "write_file":
                obs_str += result.get("message", "File salvato.")
            elif t_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                obs_str += f"Pipeline aggiornata: {len(result.get('tasks', []))} task registrati."
            elif t_name in ("complete_goal", "finish_task", "task_complete"):
                obs_str += f"Obiettivo finale completato: {result.get('summary', '')}"
            elif t_name in ("search_code", "grep"):
                matches = result.get("results", []) or []
                if result.get("error"):
                    obs_str = f"Tool 'search_code' non eseguito: {result.get('error')}\n"
                elif not matches:
                    obs_str += f"Nessuna corrispondenza per '{result.get('query')}' in '{result.get('path')}'."
                else:
                    lines = [
                        f"{m.get('path')}:{m.get('line_number')}: {str(m.get('line_content', ''))[:160]}"
                        for m in matches[:25]
                    ]
                    obs_str += (
                        f"{len(matches)} corrispondenze per '{result.get('query')}' "
                        f"(file analizzati: {result.get('scanned_files', 0)}):\n" + "\n".join(lines)
                    )
                    if result.get("capped"):
                        obs_str += f"\n[Risultati troncati: {result.get('stop_reason') or 'limite raggiunto'}]"
            else:
                obs_str += json.dumps(result, ensure_ascii=False)

            if len(obs_str) > MAX_OBSERVATION_CHARS:
                obs_str = obs_str[:MAX_OBSERVATION_CHARS] + "\n[...output troncato...]"

            tool_observations.append(obs_str)

        yield {"type": "turn_end", "turn": current_turn, "has_tools": True}

        # Append assistant turn + tool observations to message history for synthesis
        full_messages.append({"role": "assistant", "content": full_text})
        observation_prompt = "Risultati dei Tool eseguiti:\n" + "\n---\n".join(tool_observations) + "\n\nOra rispondi all'utente spiegando in modo chiaro ed esaustivo cosa è stato trovato o eseguito."
        full_messages.append({"role": "user", "content": observation_prompt})
        full_messages = trim_history(full_messages)
        last_user_prompt = observation_prompt

    yield {"type": "done", "full_text": full_text}
