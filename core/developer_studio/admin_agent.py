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
from typing import Dict, List, Any, Optional, Generator

from core.logger import get_logger
from core.developer_studio.fs_manager import (
    read_file_content,
    write_file_content,
    delete_fs_entry,
    create_fs_entry,
    get_workspace_tree,
    search_workspace_files,
    get_default_workspace_root
)
from core.developer_studio.terminal_runner import execute_shell_command_sync

log = get_logger("admin_developer_agent")

ADMIN_DEVELOPER_SYSTEM_PROMPT = """Sei Σ-SIGMA Developer Admin, un Pair-Programmer e Software Architect di livello esperto integrato nativamente in Sigma Studio.
Hai permessi di AMMINISTRATORE completi sul workspace: puoi visualizzare, modificare, creare, eliminare file ed eseguire comandi da terminale (PowerShell/Bash).

REGOLE CRITICHE:
1. Rispondi SEMPRE in lingua ITALIANA.
2. Ragiona internamente all'interno dei tag <think> ... </think>. Non esporre ragionamenti interni in inglese all'utente.
3. Quando usi i tool, emetti DIRETTAMENTE i tag dei tool senza commenti intermedi in inglese.
4. Quando ricevi i risultati dei tool, rispondi all'utente con un'analisi dettagliata, ordinata, professionale e chiara in italiano.

TAG STRUTTURATI DEI TOOL:
1. Per esplorare una cartella:
```tool:list_dir
{
  "path": "percorso cartella"
}
```

2. Per leggere un file:
```tool:read_file
{
  "path": "percorso del file"
}
```

3. Per scrivere o modificare un file:
```tool:write_file
{
  "path": "percorso del file",
  "content": "contenuto completo o aggiornato del file"
}
```

4. Per eliminare un file o una cartella:
```tool:delete
{
  "path": "percorso da eliminare"
}
```

5. Per eseguire un comando terminale:
```tool:terminal
{
  "command": "comando qui",
  "cwd": "cartella di lavoro (opzionale)"
}
```

6. Per cercare codice o testo:
```tool:search_code
{
  "query": "testo da cercare"
}
```
"""


def extract_tool_invocations(text: str) -> List[Dict[str, Any]]:
    """Extracts structured tool calls from model output (code blocks or XML/JSON)."""
    tools = []
    
    # 1. Matches ```tool:name ... ```
    tool_block_pattern = re.compile(r"```tool:(\w+)\s*\n([\s\S]*?)```", re.IGNORECASE)
    for match in tool_block_pattern.finditer(text):
        tool_name = match.group(1).lower()
        body_str = match.group(2).strip()
        try:
            params = json.loads(body_str)
        except Exception:
            params = {"raw": body_str}
            if tool_name in ("terminal", "shell", "exec"):
                params = {"command": body_str}
            elif tool_name in ("read_file", "delete", "list_dir"):
                params = {"path": body_str}

        tools.append({
            "tool": tool_name,
            "params": params,
            "raw_block": match.group(0)
        })

    # 2. Matches XML-style <execute_command> or <shell> or <read_file>
    if not tools:
        xml_cmd = re.search(r"<(?:execute_command|shell|terminal)>\s*(?:<command>)?([\s\S]*?)(?:</command>)?\s*</(?:execute_command|shell|terminal)>", text, re.IGNORECASE)
        if xml_cmd:
            cmd = xml_cmd.group(1).strip()
            tools.append({"tool": "terminal", "params": {"command": cmd}, "raw_block": xml_cmd.group(0)})

        xml_read = re.search(r"<read_file>\s*(?:<path>)?([\s\S]*?)(?:</path>)?\s*</read_file>", text, re.IGNORECASE)
        if xml_read:
            p = xml_read.group(1).strip()
            tools.append({"tool": "read_file", "params": {"path": p}, "raw_block": xml_read.group(0)})

        xml_write = re.search(r"<write_to_file>\s*<path>([\s\S]*?)</path>\s*<content>([\s\S]*?)</content>\s*</write_to_file>", text, re.IGNORECASE)
        if xml_write:
            p = xml_write.group(1).strip()
            c = xml_write.group(2)
            tools.append({"tool": "write_file", "params": {"path": p, "content": c}, "raw_block": xml_write.group(0)})

        xml_list = re.search(r"<list_dir>\s*(?:<path>)?([\s\S]*?)(?:</path>)?\s*</list_dir>", text, re.IGNORECASE)
        if xml_list:
            p = xml_list.group(1).strip()
            tools.append({"tool": "list_dir", "params": {"path": p}, "raw_block": xml_list.group(0)})

    return tools


def execute_admin_tool(tool_name: str, params: Dict[str, Any], workspace_root: str) -> Dict[str, Any]:
    """Executes a single admin developer tool."""
    tool_name = tool_name.lower()
    
    if tool_name in ("terminal", "shell", "exec", "command"):
        cmd = params.get("command") or params.get("raw", "")
        cwd = params.get("cwd") or workspace_root
        res = execute_shell_command_sync(cmd, cwd=cwd)
        return {
            "tool": "terminal",
            "command": cmd,
            "success": res.get("success", False),
            "stdout": res.get("stdout", ""),
            "stderr": res.get("stderr", ""),
            "returncode": res.get("returncode", 0)
        }

    elif tool_name in ("read_file", "read"):
        path = params.get("path") or params.get("raw", "")
        full_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
        res = read_file_content(full_path)
        return {"tool": "read_file", "path": path, **res}

    elif tool_name in ("write_file", "write", "save_file"):
        path = params.get("path") or ""
        content = params.get("content") or ""
        full_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
        
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

        res = write_file_content(full_path, content)
        return {
            "tool": "write_file",
            "path": path,
            "diff": diff_text,
            **res
        }

    elif tool_name in ("delete", "delete_file", "remove_file", "rm"):
        path = params.get("path") or params.get("raw", "")
        full_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
        res = delete_fs_entry(full_path)
        return {"tool": "delete", "path": path, **res}

    elif tool_name in ("list_dir", "list_directory", "ls"):
        path = params.get("path") or params.get("raw", "")
        full_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
        tree = get_workspace_tree(full_path, max_depth=2)
        
        # Build simple readable list of entries
        entries = []
        if tree and "children" in tree:
            for c in tree["children"]:
                entries.append(f"{'📁' if c.get('is_dir') else '📄'} {c.get('name')}")

        return {
            "tool": "list_dir",
            "path": path,
            "full_path": full_path,
            "entries": entries,
            "tree": tree,
            "success": True,
            "message": f"Trovati {len(entries)} elementi in {path or 'root'}."
        }

    elif tool_name in ("search_code", "grep"):
        query = params.get("query") or params.get("raw", "")
        path = params.get("path") or workspace_root
        res = search_workspace_files(path, query)
        return {"tool": "search_code", "query": query, **res}

    return {"tool": tool_name, "success": False, "error": f"Tool sconosciuto: {tool_name}"}


def stream_admin_agent_turn(
    messages: List[Dict[str, str]],
    workspace_root: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.3,
    auto_execute_tools: bool = True,
    max_turns: int = 3
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

    from core.engine.unified_runtime import sigma_engine

    # Prepare conversation history
    full_messages = [{"role": "system", "content": ADMIN_DEVELOPER_SYSTEM_PROMPT}]
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

    # Ensure full_messages fits comfortably in model context window (sliding window)
    if len(full_messages) > 2:
        system_msg = full_messages[0]
        conversation = full_messages[1:]
        while len(conversation) > 2 and sum(len(m.get("content", "")) for m in conversation) > 24000:
            conversation.pop(0)
        full_messages = [system_msg] + conversation

    last_user_prompt = full_messages[-1].get("content", "") if len(full_messages) > 1 else "Ciao"

    current_turn = 0
    total_generated_tokens = 0
    t_turn_start = time.perf_counter()
    overall_first_token_time = None

    while current_turn < max_turns:
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
                system_prompt=ADMIN_DEVELOPER_SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=4096,
                model_name=model_name or "sigmaengine",
                messages=full_messages
            ):
                if chunk.get("model_status") or (chunk.get("status") and chunk.get("text")):
                    status_text = chunk.get("model_status") or chunk.get("text")
                    if status_text:
                        yield {"type": "status", "text": status_text}

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
            t_name = t["tool"]
            t_params = t["params"]
            
            yield {
                "type": "tool_start",
                "tool": t_name,
                "params": t_params
            }

            result = execute_admin_tool(t_name, t_params, workspace_root)

            yield {
                "type": "tool_result",
                "tool": t_name,
                "result": result
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
            else:
                obs_str += json.dumps(result, ensure_ascii=False)

            tool_observations.append(obs_str)

        yield {"type": "turn_end", "turn": current_turn, "has_tools": True}

        # Append assistant turn + tool observations to message history for synthesis
        full_messages.append({"role": "assistant", "content": full_text})
        observation_prompt = "Risultati dei Tool eseguiti:\n" + "\n---\n".join(tool_observations) + "\n\nOra rispondi all'utente spiegando in modo chiaro ed esaustivo cosa è stato trovato o eseguito."
        full_messages.append({"role": "user", "content": observation_prompt})
        last_user_prompt = observation_prompt

    yield {"type": "done", "full_text": full_text}
