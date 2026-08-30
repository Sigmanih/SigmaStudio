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
from core.developer_studio.fs_tools import (
    read_file_slice,
    edit_file_content,
    append_file_content,
    glob_workspace_files,
)
from core.developer_studio.session_ledger import (
    RECENT_TURNS_KEPT,
    DevSessionLedger,
    check_completion_allowed,
)
from core.engine.grammars import fenced_tool_grammar
from core.engine.sampling import SamplingParams
from core.developer_studio.terminal_runner import execute_shell_command_sync

log = get_logger("admin_developer_agent")

# How many characters of a tool observation are fed back to the model.
#
# One flat cap cannot serve every tool: a directory listing says everything it
# has to say in a few hundred characters, while a source file the model is
# about to edit is useless unless it arrives whole. A single 4000-char ceiling
# applied to all of them is what made this agent unable to write code — it saw
# the first ~50 lines of every file and had to guess the rest. Budgets are
# therefore per-tool, and the file-reading budget is the one that matters.
OBSERVATION_BUDGETS = {
    "read_file": 120_000,      # ~1500 lines of source: enough to edit safely
    "search_code": 24_000,
    "terminal": 32_000,
    "glob": 16_000,
    "list_dir": 8_000,
    "edit_file": 12_000,       # the diff, so the model can verify its own patch
    "append_file": 2_000,
    "write_file": 4_000,
    "_default": 8_000,
}
MAX_OBSERVATION_CHARS = OBSERVATION_BUDGETS["_default"]

# Roughly how many characters a token is worth for budgeting purposes. Only the
# order of magnitude matters here: the point is to stop a single observation
# from claiming more of the window than exists.
CHARS_PER_TOKEN = 3.5
# No single observation may exceed this share of the context window. Above it,
# each new tool result evicts the previous one and the agent re-reads the same
# files forever instead of acting on them.
MAX_OBSERVATION_CONTEXT_SHARE = 0.35


def observation_budget(tool_name: str, context_tokens: int) -> int:
    """Characters of a tool result to feed back, capped against the window."""
    nominal = OBSERVATION_BUDGETS.get(tool_name, OBSERVATION_BUDGETS["_default"])
    ceiling = int(context_tokens * CHARS_PER_TOKEN * MAX_OBSERVATION_CONTEXT_SHARE)
    return max(2000, min(nominal, ceiling))
MAX_HISTORY_CHARS = 24000
# How many consecutive tool-less turns are tolerated before the run is
# considered stalled rather than merely thinking.
MAX_IDLE_TURNS = 3
# An upper bound on transcript turns, applied only after the character budget.
# Generous on purpose: the character budget is the real constraint, and cutting
# turns first is what starved the agent of files it had just read.
MAX_RECENT_TURNS = 24
# Tools that change the workspace or prove something about it. Everything
# else is orientation, and orientation that never ends is a stall.
PRODUCTIVE_TOOLS = ("write_file", "write", "save_file", "append_file", "append", "add_to_file", "edit_file", "edit", "replace_in_file", "str_replace", "terminal", "shell", "exec", "command", "complete_goal", "finish_task", "task_complete")
# Consecutive orientation-only turns tolerated before the transcript is
# rebuilt from the ledger and exploration is suspended for one turn.
MAX_UNPRODUCTIVE_TURNS = 3
# The tools a recovery turn may emit. Narrow on purpose: the point of that
# turn is to change the workspace, and read_file stays out because reading
# again is what the agent was doing instead.
RECOVERY_TOOLS = ("write_file", "edit_file", "append_file", "terminal")
# Suspended during a recovery turn. Only the tools that scan the tree: reading
# a specific file stays available, because a recovery turn follows a transcript
# reset and the file the agent needs is exactly what was just discarded.
SUSPENDED_DURING_RECOVERY = (
    "list_dir", "list_directory", "ls", "glob", "find_files", "glob_files",
    "search_code", "grep",
)

ADMIN_DEVELOPER_SYSTEM_PROMPT = """Sei un ingegnere del software autonomo dentro Sigma Studio.
Hai accesso completo al workspace: leggi, scrivi, modifichi file ed esegui comandi.

## REGOLA FONDAMENTALE
Ad ogni tuo messaggio emetti UN SOLO blocco tool e NIENT'ALTRO.
Il sistema lo esegue e ti restituisce il risultato. Poi emetti il tool successivo.
Non spiegare cosa farai: fallo. Non emettere due tool nello stesso messaggio.

Formato, sempre identico:
```tool:NOME_DEL_TOOL
{ ...un solo oggetto JSON valido... }
```

## CICLO DI LAVORO
1. ORIENTATI: `glob` o `search_code` per trovare i file, `list_dir` per esplorare.
2. LEGGI: `read_file` su OGNI file che devi toccare. Obbligatorio.
3. AGISCI: `edit_file` per modificare, `write_file` solo per file NUOVI.
4. VERIFICA: `terminal` con un test, un lint o un import. Deve uscire con codice 0.
5. CHIUDI: `complete_goal`.

Non puoi saltare il passo 2: senza aver letto un file non conosci il testo
esatto da sostituire e `edit_file` verra rifiutato.
Non puoi saltare il passo 4: `complete_goal` viene rifiutato senza una verifica
riuscita dopo l'ultima modifica.

## TOOL DISPONIBILI

`read_file` — legge righe numerate. Dice quante righe ha il file e se continua.
{"path": "PERCORSO", "offset": PRIMA_RIGA, "limit": QUANTE_RIGHE}
offset e limit sono opzionali (default: dalla riga 1, 800 righe).

`edit_file` — sostituisce un frammento esatto. Il modo normale di modificare.
{"path": "PERCORSO", "old_string": "TESTO_ESATTO_DA_SOSTITUIRE", "new_string": "TESTO_NUOVO"}
old_string deve essere copiato dal risultato di read_file SENZA i numeri di
riga, e deve essere UNIVOCO nel file: se compare piu volte, allargalo con le
righe intorno.

`append_file` — aggiunge testo IN FONDO a un file. Usalo quando devi
aggiungere funzioni, route o test a un file che esiste gia': non serve alcuna
ancora, la posizione e' la fine del file.
{"path": "PERCORSO", "content": "TESTO_DA_AGGIUNGERE"}

`write_file` — crea un file nuovo, o ne riscrive uno da zero.
{"path": "PERCORSO", "content": "CONTENUTO_COMPLETO"}

`terminal` — esegue un comando (PowerShell).
{"command": "COMANDO", "cwd": "."}

`glob` — trova file per pattern.
{"pattern": "PATTERN"}

`search_code` — cerca testo dentro i file.
{"query": "TESTO_DA_CERCARE"}

`list_dir` — elenca una cartella. La radice del workspace e ".".
{"path": "PERCORSO"}

`delete` — elimina un file.
{"path": "PERCORSO"}

`restore_file` — ripristina un file dal backup automatico.
{"path": "PERCORSO"}

`pipeline` — registra i task del TUO piano per l'obiettivo corrente.
{"tasks": [{"id": "1", "title": "TITOLO", "status": "in_progress"}]}
I titoli devono descrivere QUESTO obiettivo, non un esempio generico.
Emettilo una volta all'inizio e aggiornalo solo quando lo stato cambia davvero.

`complete_goal` — dichiara finito il lavoro.
{"summary": "COSA_HAI_FATTO"}

## VINCOLI
- I percorsi sono relativi alla radice del workspace ("." e la radice).
- Rispondi in italiano.
- Se un tool fallisce, leggi l'errore e correggi la chiamata. Non ripeterla identica.
- Non inventare percorsi o contenuti: verificali con i tool.
"""


# Prefixes of a tool fence that must never reach the UI as prose. A token
# stream delivers "`", "``", "```t" one piece at a time, so the only way to
# avoid printing a fence that has not finished arriving is to withhold any
# tail that could still become one.
_FENCE_MARKER = "```tool:"


def _split_emittable(buffer: str) -> tuple:
    """Splits a buffer into (safe to emit now, must keep waiting).

    The retained part is the longest suffix that is a proper prefix of the
    tool fence marker; everything before it can never be part of one.
    """
    for keep in range(min(len(buffer), len(_FENCE_MARKER) - 1), 0, -1):
        if _FENCE_MARKER.startswith(buffer[-keep:]):
            return buffer[:-keep], buffer[-keep:]
    return buffer, ""


# The literal tokens used as placeholders in the system prompt. A model that
# echoes one of these back as a value has copied the schema instead of filling
# it in; executing the call would act on a path or command that does not exist.
PROMPT_PLACEHOLDERS = frozenset({
    "PERCORSO", "PRIMA_RIGA", "QUANTE_RIGHE", "TESTO_ESATTO_DA_SOSTITUIRE",
    "TESTO_NUOVO", "CONTENUTO_COMPLETO", "COMANDO", "PATTERN",
    "TESTO_DA_CERCARE", "TITOLO", "COSA_HAI_FATTO", "NOME_DEL_TOOL",
    "path", "content", "command", "query",
})


# Names a model plausibly reaches for when it means "the file". Accepting them
# costs one lookup; refusing them costs a whole turn on a call whose intent was
# never in doubt.
_PATH_KEYS = ("path", "file", "filename", "file_path", "filepath", "target")


def _path_of(params: Dict[str, Any]) -> str:
    """The path argument under whichever of its usual names it arrived."""
    for key in _PATH_KEYS:
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def find_placeholder_params(params: Dict[str, Any]) -> List[str]:
    """Parameter names whose value is one of the prompt's own placeholders."""
    offenders = []
    for key, value in (params or {}).items():
        if isinstance(value, str) and value.strip() in PROMPT_PLACEHOLDERS:
            offenders.append(key)
    return offenders


# What an assistant turn is allowed to occupy in the transcript once its
# reasoning has been removed. Enough to keep the tool call it made legible,
# far too little to displace the file the next step depends on.
MAX_ASSISTANT_HISTORY_CHARS = 1500

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)


def _as_history(full_text: str) -> str:
    """An assistant turn reduced to what later turns actually need.

    The reasoning block is dropped: it is the model narrating its way to a
    decision the ledger already records, and on this checkpoint it cannot be
    switched off, so left in it would crowd out everything else.
    """
    text = _THINK_BLOCK_RE.sub("", full_text or "")
    # A generation cut off mid-thought leaves the tag unclosed.
    text = _THINK_OPEN_RE.sub("", text).strip()
    if not text:
        return "(nessun output oltre al ragionamento interno)"
    if len(text) > MAX_ASSISTANT_HISTORY_CHARS:
        head = text[: MAX_ASSISTANT_HISTORY_CHARS // 2]
        tail = text[-MAX_ASSISTANT_HISTORY_CHARS // 2:]
        return f"{head}\n[...]\n{tail}"
    return text


def _recovery_directive(ledger: Optional["DevSessionLedger"] = None) -> str:
    """The message that replaces a stalled transcript.

    Leads with the concrete failure when there is one. A test that failed with
    `cannot import name X from Y` has already identified the symbol, the file
    and the edit; repeating a generic "write the next file" instead throws that
    away and invites another round of exploration.
    """
    failure = ledger.last_command() if ledger else None
    if failure and not failure.get("ok") and failure.get("error"):
        return (
            "STOP ESPLORAZIONE. L'ultima verifica e fallita e il suo errore dice "
            "gia cosa correggere:\n\n"
            f"    $ {failure['command']}\n"
            f"    {failure['error']}\n\n"
            "Correggi ESATTAMENTE questo, ora, con edit_file o write_file. "
            "Se manca un simbolo, aggiungilo al file che dovrebbe definirlo. "
            "Se un import e sbagliato, correggi l'import.\n\n"
            "In questo turno list_dir, glob e search_code sono SOSPESI, e "
            "read_file e ammesso solo su file mai letti in questa sessione: i "
            "nomi definiti dai file che hai gia letto sono elencati nello stato "
            "del lavoro qui sopra."
        )

    return (
        "STOP ESPLORAZIONE. Hai gia raccolto le informazioni che ti servono: "
        "lo stato completo del lavoro e nel prompt di sistema qui sopra, e "
        "l'obiettivo e nel primo messaggio.\n\n"
        "Nel prossimo messaggio emetti UN SOLO blocco ```tool:write_file che "
        "crea il prossimo file previsto dall'obiettivo, oppure ```tool:edit_file "
        "se il file esiste gia. Se non sei sicuro del contenuto definitivo, "
        "scrivine una versione minima ma funzionante: la completerai dopo.\n\n"
        "In questo turno list_dir, glob e search_code sono SOSPESI. read_file "
        "resta disponibile se ti serve rivedere un file preciso."
    )


_JSON_CONTROL_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _repair_json_control_chars(text: str) -> str:
    """Escapes raw control characters that appear inside JSON string literals.

    Models writing source code into a JSON argument escape the quotes and
    forget the newlines. The result is rejected by a strict parser even though
    nothing about it is ambiguous. Since a bare newline inside a string literal
    is invalid JSON by definition, escaping it is lossless for any document
    that was already well-formed.
    """
    out = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            elif ch in _JSON_CONTROL_ESCAPES:
                out.append(_JSON_CONTROL_ESCAPES[ch])
                continue
        elif ch == '"':
            in_string = True
        out.append(ch)
    return "".join(out)


def _loads_forgiving(text: str) -> Optional[Any]:
    """json.loads, retried once on the repaired text. None if both fail."""
    for candidate in (text, _repair_json_control_chars(text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _first_json_object(text: str) -> Optional[str]:
    """The first complete, balanced JSON object in `text`, or None.

    Brace counting has to respect string literals: a tool call that writes
    Python is full of braces inside quoted content, and counting them as
    structure truncates the object at the first f-string.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _unterminated_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """A tool call opened with ```tool: whose closing fence is absent.

    Returns the parsed call when the body holds a complete JSON object, and
    None when it does not — which is the honest signal that the generation was
    cut off mid-argument.
    """
    marker = text.rfind("```tool:")
    if marker == -1:
        return None
    rest = text[marker + len("```tool:"):]
    if "```" in rest:
        return None  # properly closed; the normal patterns handle it

    newline = rest.find("\n")
    if newline == -1:
        return None
    name = rest[:newline].strip().lower()
    if not name or not name.isidentifier():
        return None

    body = _first_json_object(rest[newline:])
    if body is None:
        return None
    params = _loads_forgiving(body)
    if not isinstance(params, dict):
        return None
    return {"tool": name, "params": params, "raw_block": text[marker:]}


def _drop_superseded_reads(messages: List[Dict[str, str]], path: str) -> None:
    """Removes earlier observations that showed the same file.

    Two readings of one file differ only in which window they show, and the
    older window is the one the model has already decided was insufficient.
    Keeping both spends the context twice to say one thing, and on a long run
    that is what pushes the useful half out of the window.
    """
    marker = f"Contenuto di '{path}'"
    for i in range(len(messages) - 1, 1, -1):
        if marker in messages[i].get("content", ""):
            messages.pop(i)


def _has_unclosed_tool_fence(text: str) -> bool:
    """Whether a tool call was genuinely cut off mid-argument.

    A missing closing fence alone does not qualify: the model habitually stops
    once its JSON is complete. Only a body that will not parse means the
    generator was interrupted with the call still unfinished — and that is the
    one case where asking it to write something smaller actually helps.
    """
    marker = text.rfind("```tool:")
    if marker == -1:
        return False
    if "```" in text[marker + len("```tool:"):]:
        return False
    return _unterminated_tool_call(text) is None


def extract_implicit_pipeline_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Detects markdown task lists, numbered steps, or checklists in model output
    when the model wrote a plan in natural text without an explicit tool:pipeline call.
    """
    clean_text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    clean_text = re.sub(r"```[\s\S]*?```", "", clean_text)
    
    tasks = []
    # 1. Checklist lines: - [ ] or - [x] or * [ ]
    checklist = re.findall(r"^[ \t]*[-*]\s*\[([ xX])\]\s*(.+)$", clean_text, re.MULTILINE)
    if checklist and len(checklist) >= 2:
        for idx, (check, title) in enumerate(checklist):
            status = "done" if check.lower() == "x" else ("in_progress" if idx == 0 else "pending")
            tasks.append({"id": str(idx + 1), "title": title.strip(), "status": status})
        return tasks

    # 2. Numbered steps: 1. ... 2. ... 3. ...
    numbered = re.findall(r"^[ \t]*(\d+)[\.\)]\s+([^\n\r]+)", clean_text, re.MULTILINE)
    if numbered and len(numbered) >= 2:
        for idx, (num, title) in enumerate(numbered):
            t_clean = title.strip().strip("*`_")
            if len(t_clean) > 3 and not t_clean.lower().startswith(("http", "www")):
                tasks.append({"id": str(idx + 1), "title": t_clean, "status": "in_progress" if idx == 0 else "pending"})
        if len(tasks) >= 2:
            return tasks

    return []


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
    data = _loads_forgiving(raw_body)
    if data is not None:
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            if tool_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                return {"tasks": data}
            return {"items": data}

    # Try extracting a balanced JSON object embedded in surrounding prose.
    body = _first_json_object(raw_body)
    if body is not None:
        data = _loads_forgiving(body)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and tool_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
            return {"tasks": data}

    # A body that still looks like JSON (or like the prompt's own placeholder)
    # is a malformed call, not a bare path. Treating it as one produces
    # nonsense such as reading a file literally named `{"path": ...}`, which
    # costs a whole turn and tells the model nothing about what went wrong.
    looks_malformed = (
        raw_body.startswith(("{", "[", "<"))
        or "..." in raw_body
        or "\n" in raw_body.strip()
    )
    if looks_malformed and tool_name not in ("pipeline", "tasks", "set_tasks"):
        return {
            "__malformed__": True,
            "raw": raw_body[:400],
        }

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

    # Last: a fence that was opened and never closed. The model routinely omits
    # the trailing ``` once its JSON argument is complete, and refusing the call
    # over missing punctuation discards work that is entirely well-formed.
    if not tools:
        salvaged = _unterminated_tool_call(text)
        if salvaged:
            tools.append(salvaged)

    return tools


def execute_admin_tool(
    tool_name: str,
    params: Dict[str, Any],
    workspace_root: str,
    should_cancel: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """Executes a single admin developer tool with full workspace resolution."""
    tool_name = tool_name.lower()

    if params.get("__malformed__"):
        return {
            "tool": tool_name,
            "success": False,
            "error": (
                f"Chiamata a '{tool_name}' malformata: il corpo non e un oggetto JSON valido. "
                "Riemetti il blocco nel formato esatto, per esempio:\n"
                '```tool:' + tool_name + '\n{"path": "core/api_router.py"}\n```'
            ),
            "received": params.get("raw", ""),
        }
    
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
        raw_path = _path_of(params) or params.get("raw", "")
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

        res = read_file_slice(
            full_path,
            offset=params.get("offset") or params.get("start_line") or 1,
            limit=params.get("limit") or params.get("max_lines"),
        )
        return {"tool": "read_file", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("write_file", "write", "save_file"):
        raw_path = _path_of(params)
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

    elif tool_name in ("edit_file", "edit", "replace_in_file", "str_replace"):
        raw_path = _path_of(params)
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = edit_file_content(
            full_path,
            old_string=params.get("old_string") or params.get("old") or params.get("search") or "",
            new_string=params.get("new_string") or params.get("new") or params.get("replace") or "",
            replace_all=bool(params.get("replace_all") or params.get("all")),
            root=workspace_root,
        )
        return {"tool": "edit_file", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("append_file", "append", "add_to_file"):
        raw_path = _path_of(params)
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = append_file_content(
            full_path,
            content=params.get("content") or params.get("text") or "",
            root=workspace_root,
        )
        return {"tool": "append_file", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("glob", "find_files", "glob_files"):
        pattern = params.get("pattern") or params.get("glob") or params.get("raw") or "**/*"
        raw_path = params.get("path") or "."
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = glob_workspace_files(full_path, pattern, limit=params.get("limit") or 300)
        return {"tool": "glob", "pattern": pattern, "path": raw_path, **res}

    elif tool_name in ("delete", "delete_file", "remove_file", "rm"):
        raw_path = _path_of(params) or params.get("raw", "")
        full_path = resolve_workspace_path(raw_path, workspace_root)
        res = delete_fs_entry(full_path, root=workspace_root)
        return {"tool": "delete", "path": raw_path, "full_path": full_path, **res}

    elif tool_name in ("list_dir", "list_directory", "ls"):
        raw_path = _path_of(params) or params.get("raw", "")
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
    max_turns: int = 30,
    should_cancel: Optional[Callable[[], bool]] = None,
    system_prompt_override: Optional[str] = None,
    current_pipeline: Optional[List[Dict[str, Any]]] = None,
    context_tokens: int = 32768,
    max_tokens: int = 20000,
    thinking: Optional[bool] = False,
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
    base_system_prompt = system_prompt_override or ADMIN_DEVELOPER_SYSTEM_PROMPT

    # Append MCP developer tools section if available
    try:
        from core.developer_studio.mcp_tools.bridge import build_mcp_tools_section
        mcp_section = build_mcp_tools_section()
        if mcp_section:
            base_system_prompt = base_system_prompt + "\n" + mcp_section
    except Exception:
        pass  # MCP tools not yet registered — proceed without them

    # Durable working state. Facts about the workspace live here rather than in
    # the transcript, so trimming old turns can no longer make the agent forget
    # what it has already read, written or verified.
    goal_text = ""
    for m in messages:
        if m.get("role") == "user":
            goal_text = str(m.get("content", ""))[:1500]
            break
    ledger = DevSessionLedger(goal=goal_text, workspace_root=workspace_root)
    if current_pipeline:
        ledger.set_pipeline(current_pipeline)
    active_system_prompt = base_system_prompt

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

    # The transcript now carries only the recent exchange; everything durable
    # has already been distilled into the ledger and is re-emitted with the
    # system prompt each turn. That makes trimming safe, so it can be far more
    # aggressive than a context-proportional window and keeps prefill cheap.
    # Sized so the transcript plus the system prompt and the state block fit
    # inside the window with room for the answer. Characters, not turns, is the
    # right unit: six turns of directory listings and six turns of source files
    # are not remotely the same amount of context.
    max_history_chars = int(context_tokens * CHARS_PER_TOKEN * 0.55)

    def trim_history(msgs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keeps the system prompt, the root objective and the recent turns."""
        if len(msgs) <= 3:
            return msgs
        system_msg, first_user_msg, rest = msgs[0], msgs[1], msgs[2:]
        while len(rest) > 1 and sum(len(m.get("content", "")) for m in rest) > max_history_chars:
            rest.pop(0)
        while len(rest) > MAX_RECENT_TURNS:
            rest.pop(0)
        return [system_msg, first_user_msg] + rest

    full_messages = trim_history(full_messages)

    last_user_prompt = full_messages[-1].get("content", "") if len(full_messages) > 1 else "Ciao"

    current_turn = 0
    goal_reached = False
    unproductive_turns = 0
    force_action_turn = False
    consecutive_truncations = 0
    last_pipeline_signature = None
    failed_call_signatures: set = set()
    # Successful calls whose repetition cannot produce new information.
    inert_call_signatures: set = set()
    total_generated_tokens = 0
    t_turn_start = time.perf_counter()
    overall_first_token_time = None

    while current_turn < max_turns:
        if _cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return
        current_turn += 1

        # Re-emit the distilled working state with the system prompt. This is
        # the only copy of it the model gets: it replaces the old turns that
        # trimming has thrown away.
        state_block = ledger.render_state_block()
        active_system_prompt = f"{base_system_prompt}\n\n{state_block}"
        full_messages[0] = {"role": "system", "content": active_system_prompt}

        accumulated_response = []
        in_think_block = False
        in_tool_block = False
        has_notified_tool = False
        turn_tokens = 0
        pending_out = ""
        turn_first_token_time = None
        t_call_start = time.perf_counter()

        yield {"type": "turn_start", "turn": current_turn}
        if current_turn == 1:
            approx_tokens = sum(len(m.get("content", "")) for m in full_messages) // 4
            yield {
                "type": "context_info",
                "prompt_tokens": approx_tokens,
                "context_limit": context_tokens,
                "max_tokens": max_tokens,
            }
            yield {"type": "status", "text": f"🧠 Preparazione e caricamento modello ({model_name or 'sigmaengine'})..."}
        else:
            yield {"type": "status", "text": "🔍 Sintesi e formattazione risposta..."}

        try:
            # On a recovery turn the decode is masked to the tool-call shape.
            # The agent reached this turn by producing prose or nothing at all
            # when an action was required; a grammar makes both unreachable
            # rather than merely discouraged.
            turn_params = None
            if force_action_turn:
                gbnf = fenced_tool_grammar(RECOVERY_TOOLS)
                if gbnf:
                    turn_params = (
                        SamplingParams.resolve(model_name=model_name or "")
                        .with_overrides(temperature=temperature, max_tokens=max_tokens)
                        .with_grammar(gbnf)
                    )
                    yield {"type": "status", "text": "\u2699 Decodifica vincolata a una tool call"}

            for chunk in sigma_engine.generate_stream(
                prompt=last_user_prompt,
                system_prompt=active_system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name or "sigmaengine",
                messages=full_messages,
                params=turn_params,
                thinking=thinking,
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
                        # Whatever part of the opening fence is still sitting in
                        # the hold-back buffer is dropped rather than emitted.
                        pending_out = ""
                    elif re.search(r"<(?:execute_command|shell|terminal|read_file|write_to_file|list_dir|search_code|tool)>", current_text[-35:]):
                        in_tool_block = True
                        pending_out = ""

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

                # Hold back any tail that could still turn out to be the start
                # of a tool fence. Emitting it optimistically is what leaves a
                # stray ```tool in the rendered answer once the fence completes
                # on the following token — and a retraction event cannot undo
                # text the client has already laid out.
                pending_out += token
                safe, pending_out = _split_emittable(pending_out)
                if safe:
                    yield {"type": "token", "token": safe}

            # Flush whatever survived the hold-back at end of stream.
            if pending_out and not in_tool_block:
                yield {"type": "token", "token": pending_out}
            pending_out = ""

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

        # An output cut off by the token budget is indistinguishable, to the
        # extractor, from an output that contained no tool at all — and the two
        # need opposite responses. Saying which one happened is what lets the
        # model split an oversized write instead of retrying it whole.
        truncated_call = _has_unclosed_tool_fence(full_text)
        hit_budget = turn_tokens >= max_tokens - 8
        if (truncated_call or (hit_budget and not tools_found)):
            if current_turn < max_turns:
                consecutive_truncations += 1
                size_hint = (
                    "Scrivi al massimo 80 righe in questa chiamata."
                    if consecutive_truncations >= 2
                    else "Se stavi scrivendo un file lungo, spezzalo."
                )
                advice = (
                    "La tua risposta e stata TRONCATA: ha raggiunto il limite di "
                    f"{max_tokens} token prima di completare il blocco tool.\n"
                    f"{size_hint}\n"
                    "Non ripetere la stessa chiamata: verrebbe troncata di nuovo.\n"
                    "Se stavi scrivendo un file, spezzalo: crea prima una versione "
                    "piu corta con write_file, poi aggiungi il resto con edit_file, "
                    "una sezione per volta.\n"
                    "Se stavi ragionando a lungo, smetti: emetti direttamente il "
                    "prossimo blocco tool, senza premesse."
                )
                yield {"type": "status", "text": "\u2702 Risposta troncata: chiedo di spezzare il lavoro"}
                yield {"type": "output_truncated", "max_tokens": max_tokens}
                full_messages.append({"role": "assistant", "content": _as_history(full_text)})
                full_messages.append({"role": "user", "content": advice})
                full_messages = trim_history(full_messages)
                last_user_prompt = advice
                continue

        # Check if pipeline was defined via implicit markdown text if no pipeline tool call was issued
        has_pipeline_tool = any(t["tool"] in ("pipeline", "tasks", "set_tasks", "update_pipeline") for t in tools_found)
        if not has_pipeline_tool:
            implicit_tasks = extract_implicit_pipeline_from_text(full_text)
            if implicit_tasks:
                yield {
                    "type": "pipeline_update",
                    "tasks": implicit_tasks
                }

        if not tools_found or not auto_execute_tools:
            # No tool this turn. That is the end of the work only if the work is
            # actually finished; otherwise the model has drifted into narrating
            # instead of acting, and one explicit nudge recovers the run far more
            # cheaply than restarting it.
            gate = check_completion_allowed(ledger)
            if gate["allowed"] or not ledger.goal:
                break
            unproductive_turns += 1
            if unproductive_turns >= MAX_UNPRODUCTIVE_TURNS:
                unproductive_turns = 0
                force_action_turn = True
                yield {"type": "status", "text": "\u26a0 Stallo: contesto ripulito, azione forzata"}
                yield {"type": "context_reset", "reason": "nessuna azione per piu turni"}
                directive = _recovery_directive(ledger)
                full_messages = [full_messages[0], full_messages[1],
                                 {"role": "user", "content": directive}]
                last_user_prompt = directive
                continue
            if unproductive_turns >= MAX_UNPRODUCTIVE_TURNS * 3:
                yield {"type": "error", "error": "L'agente non avanza: interrotto."}
                break
            yield {"type": "status", "text": "↻ Nessuna azione richiesta: sollecito la ripresa..."}
            full_messages.append({"role": "assistant", "content": _as_history(full_text)})
            nudge = (
                "Non hai emesso alcun tool in questo turno e l'obiettivo non risulta "
                f"ancora completato: {gate['reason']}\n\n"
                "Emetti ORA il prossimo blocco tool necessario per avanzare, nel "
                "formato ```tool:nome seguito dal JSON. Non scrivere spiegazioni: "
                "solo il blocco tool."
            )
            full_messages.append({"role": "user", "content": nudge})
            full_messages = trim_history(full_messages)
            last_user_prompt = nudge
            continue

        # Execute at most one acting tool per turn.
        #
        # The model routinely emits an entire plan's worth of calls in a single
        # response - read, edit, test and complete_goal together - which defeats
        # the whole point of a tool loop: the edit is written before the read has
        # returned, and the completion is claimed before either has been seen.
        # Serialising restores the observe-then-act cycle the loop exists for.
        bookkeeping = ("pipeline", "tasks", "set_tasks", "update_pipeline")
        serialised = []
        for t in tools_found:
            if t["tool"] not in bookkeeping:
                continue
            signature = json.dumps(t["params"], sort_keys=True, default=str)
            # Re-registering an unchanged plan is not progress. Left in, it
            # counts as "a tool was emitted" and the loop stops nudging the
            # model back towards doing actual work.
            if signature == last_pipeline_signature:
                continue
            last_pipeline_signature = signature
            serialised.append(t)
        acting = [t for t in tools_found if t["tool"] not in bookkeeping]
        if not serialised and not acting:
            unproductive_turns += 1
            if unproductive_turns >= MAX_UNPRODUCTIVE_TURNS * 3:
                yield {
                    "type": "error",
                    "error": (
                        "L'agente ha smesso di avanzare: ha ripetuto lo stesso "
                        "piano senza eseguire azioni. Riformula l'obiettivo in "
                        "modo piu specifico, oppure usa un modello piu capace."
                    ),
                }
                break
            yield {"type": "status", "text": "↻ Piano invariato: sollecito un'azione..."}
            full_messages.append({"role": "assistant", "content": _as_history(full_text)})
            nudge = (
                "Hai ripetuto lo stesso piano senza agire. Emetti ORA un blocco "
                "tool che compia un'azione concreta (read_file, edit_file, "
                "write_file o terminal). Nient'altro."
            )
            full_messages.append({"role": "user", "content": nudge})
            full_messages = trim_history(full_messages)
            last_user_prompt = nudge
            continue
        if acting:
            serialised.append(acting[0])
            if len(acting) > 1:
                deferred = ", ".join(t["tool"] for t in acting[1:])
                yield {
                    "type": "status",
                    "text": f"⏳ Un tool per turno: rimandati {deferred}",
                }
        tools_found = serialised

        # Execute tools and prepare observation for next turn
        tool_observations = []
        reads_this_turn: List[str] = []
        turn_was_productive = False
        # Signatures of calls that have already failed, so an identical retry
        # can be short-circuited instead of burning a turn on the same error.
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

            # During a forced-action turn the only useful move is to write.
            # Refusing exploration outright is blunter than asking again, and
            # asking again is exactly what has already failed several times.
            if force_action_turn and t_name in SUSPENDED_DURING_RECOVERY:
                msg = (
                    f"Tool '{t_name}' SOSPESO: hai gia esplorato la struttura "
                    "del progetto e non hai ancora scritto nulla. Se ti serve il "
                    "contenuto di un file specifico usa read_file; altrimenti "
                    "crea ORA il file previsto dall'obiettivo con write_file, "
                    "anche in versione minima: lo completerai con edit_file."
                )
                yield {
                    "type": "tool_result",
                    "tool": t_name,
                    "result": {"tool": t_name, "success": False, "error": msg},
                }
                tool_observations.append(msg + "\n")
                continue

            # A second identical listing of a directory nobody has changed
            # returns the same bytes and teaches the model nothing. Left
            # unchecked it is a stall that looks like activity, because every
            # call succeeds.
            inert_signature = (t_name, json.dumps(t_params, sort_keys=True, default=str)[:400])
            if t_name in ("list_dir", "list_directory", "ls", "glob") and inert_signature in inert_call_signatures:
                msg = (
                    f"Tool '{t_name}' NON eseguito: hai gia ottenuto esattamente "
                    "questo elenco e nulla e cambiato da allora. Il risultato "
                    "sarebbe identico. Passa all'azione: crea o modifica i file "
                    "previsti dall'obiettivo."
                )
                yield {
                    "type": "tool_result",
                    "tool": t_name,
                    "result": {"tool": t_name, "success": False, "error": msg},
                }
                tool_observations.append(msg + "\n")
                continue

            # During recovery a read is allowed only for a file this session
            # has never seen. Patch 14 left read_file open so the agent could
            # recover a spec the context reset had just discarded; the cost was
            # that it could re-read forever, which is the stall the recovery
            # turn exists to break.
            if force_action_turn and t_name in ("read_file", "read"):
                probe = t_params.get("path") or ""
                already = ledger.was_read_before_change(
                    resolve_workspace_path(probe, workspace_root).replace("\\", "/")
                )
                if already:
                    msg = (
                        f"Tool 'read_file' SOSPESO su '{probe}': lo hai gia letto "
                        "in questa sessione, e i nomi che quel file definisce sono "
                        "elencati nello stato del lavoro qui sopra, sotto 'API dei "
                        "file gia letti'. Usa quelli. Scrivi ORA con write_file il "
                        "file previsto dall'obiettivo."
                    )
                    yield {
                        "type": "tool_result",
                        "tool": t_name,
                        "result": {"tool": t_name, "success": False, "error": msg},
                    }
                    tool_observations.append(msg + "\n")
                    continue

            if t_name in ("read_file", "read"):
                probe = t_params.get("path") or ""
                resolved = resolve_workspace_path(probe, workspace_root)
                marker = f"Contenuto di '{resolved.replace(chr(92), '/')}'"
                still_visible = any(
                    marker in m.get("content", "") for m in full_messages[2:]
                )
                if still_visible:
                    msg = (
                        f"Tool 'read_file' NON eseguito: il contenuto di "
                        f"'{probe}' e gia presente qui sopra in questa "
                        "conversazione. Rileggerlo non aggiunge nulla e consuma "
                        "il contesto. Passa all'azione: usa edit_file o "
                        "write_file. Se ti serve una porzione diversa del file, "
                        "chiedila con un offset esplicito."
                    )
                    yield {
                        "type": "tool_result",
                        "tool": t_name,
                        "result": {"tool": t_name, "success": False, "error": msg},
                    }
                    tool_observations.append(msg + "\n")
                    continue

            placeholder_keys = find_placeholder_params(t_params)
            if placeholder_keys:
                candidates = ledger.goal_paths or ledger.read_files
                hint = (
                    "Percorsi reali disponibili: "
                    + ", ".join(f"`{c}`" for c in candidates[:6])
                    if candidates
                    else "Usa `glob` o `list_dir` per trovare il percorso reale."
                )
                msg = (
                    f"Tool '{t_name}' NON eseguito: i parametri "
                    f"{', '.join(placeholder_keys)} contengono un segnaposto del "
                    "formato, non un valore reale. Sostituiscilo con il valore "
                    f"concreto. {hint}"
                )
                yield {
                    "type": "tool_result",
                    "tool": t_name,
                    "result": {"tool": t_name, "success": False, "error": msg},
                }
                tool_observations.append(msg + "\n")
                continue

            # An edit whose `old_string` was never read is a guess about the
            # file's contents. The model does make that guess — and when it
            # misses, the failure looks like a tool problem rather than a
            # missing read, so it guesses again. Refusing the call and naming
            # the missing step is what breaks that cycle.
            if t_name in ("edit_file", "edit", "replace_in_file", "str_replace"):
                target = t_params.get("path") or t_params.get("file_path") or ""
                if target and not ledger.was_read_before_change(target.replace("\\", "/")):
                    result = {
                        "tool": "edit_file",
                        "path": target,
                        "success": False,
                        "error": (
                            f"Non hai ancora letto '{target}' in questa sessione. "
                            "Non puoi conoscere il testo esatto da sostituire. "
                            f'Esegui prima: ```tool:read_file\n{{"path": "{target}"}}\n``` '
                            "e ricopia le righe dal risultato, senza i numeri di riga."
                        ),
                    }
                    ledger.record_tool(t_name, t_params, result)
                    yield {"type": "tool_result", "tool": t_name, "result": result}
                    yield {"type": "ledger", "state": ledger.snapshot()}
                    tool_observations.append(
                        f"Tool 'edit_file' NON eseguito (errore): {result['error']}\n"
                    )
                    continue

            # A call repeated verbatim after failing will fail verbatim again.
            # Saying so costs one line and saves the rest of the turn budget.
            call_signature = (t_name, json.dumps(t_params, sort_keys=True, default=str)[:600])
            if call_signature in failed_call_signatures:
                repeat_note = (
                    f"Tool '{t_name}' NON eseguito: hai gia effettuato questa "
                    "identica chiamata e ha gia fallito. Ripeterla dara lo stesso "
                    "risultato. Cambia approccio: leggi il file, cerca il percorso "
                    "corretto, oppure esegui l'azione mancante che ti e stata indicata."
                )
                yield {
                    "type": "tool_result",
                    "tool": t_name,
                    "result": {"tool": t_name, "success": False, "error": repeat_note},
                }
                tool_observations.append(repeat_note + "\n")
                continue

            # Route through MCP Hub for Git/Lint/Test tools, local for FS/Terminal
            try:
                from core.developer_studio.mcp_tools.bridge import is_mcp_tool, execute_via_mcp
                if is_mcp_tool(t_name):
                    result = execute_via_mcp(t_name, t_params)
                else:
                    result = execute_admin_tool(t_name, t_params, workspace_root, should_cancel=should_cancel)
            except ImportError:
                result = execute_admin_tool(t_name, t_params, workspace_root, should_cancel=should_cancel)

            ledger.record_tool(t_name, t_params, result)
            if result.get("success") and t_name in PRODUCTIVE_TOOLS:
                turn_was_productive = True
                consecutive_truncations = 0
            if t_name == "read_file" and result.get("success") and result.get("path"):
                reads_this_turn.append(str(result["path"]))
            if result.get("success") and t_name in ("list_dir", "list_directory", "ls", "glob"):
                inert_call_signatures.add(
                    (t_name, json.dumps(t_params, sort_keys=True, default=str)[:400])
                )
            if not result.get("success"):
                failed_call_signatures.add(
                    (t_name, json.dumps(t_params, sort_keys=True, default=str)[:600])
                )

            yield {
                "type": "tool_result",
                "tool": t_name,
                "result": result
            }
            # Let the Developer Studio panel mirror exactly what the model sees.
            yield {"type": "ledger", "state": ledger.snapshot()}

            if t_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                yield {
                    "type": "pipeline_update",
                    "tasks": result.get("tasks", [])
                }
            elif t_name in ("complete_goal", "finish_task", "task_complete"):
                # Completion is granted on evidence in the ledger, never on the
                # model's own say-so: nobody is checking behind an autonomous
                # loop, so "done" has to mean something was actually verified.
                gate = check_completion_allowed(ledger)
                if not gate["allowed"]:
                    result = {
                        "tool": "complete_goal",
                        "success": False,
                        "is_completed": False,
                        "error": f"Completamento rifiutato. {gate['reason']}",
                    }
                    yield {"type": "completion_rejected", "reason": gate["reason"]}
                else:
                    goal_reached = True
                    yield {
                        "type": "goal_complete",
                        "summary": result.get("summary", ""),
                        "evidence": gate.get("evidence", {}),
                    }

            # Format concise observation for the model.
            # The prefix must track the real outcome: a failed call announced as
            # "eseguito con successo" is worse than no feedback at all — the
            # model believes the step is behind it and moves on.
            if result.get("success"):
                obs_str = f"Tool '{t_name}' eseguito con successo.\n"
            else:
                obs_str = (
                    f"Tool '{t_name}' NON eseguito (errore): "
                    f"{result.get('error', 'causa non specificata')}\n"
                    "Correggi la chiamata prima di proseguire. "
                    "NON ripetere la stessa identica chiamata.\n"
                )
            if t_name == "list_dir":
                obs_str += f"Elementi trovati in '{result.get('path')}':\n" + "\n".join(result.get("entries", [])[:40])
            elif t_name == "read_file":
                body = result.get("numbered") or result.get("content") or ""
                total = result.get("total_lines")
                if not result.get("success"):
                    obs_str = f"Tool 'read_file' fallito: {result.get('error')}\n"
                elif result.get("is_sliceable") is False:
                    obs_str += (
                        f"'{result.get('path')}' non e un file di testo "
                        f"({result.get('size_label', '')}). {result.get('message', '')}"
                    )
                else:
                    header = f"Contenuto di '{result.get('path')}'"
                    if total is not None:
                        header += (
                            f" — righe {result.get('offset')}-{result.get('last_line')} "
                            f"di {total} totali"
                        )
                    obs_str += f"{header}:\n{body}"
                    if result.get("has_more"):
                        obs_str += (
                            f"\n\n[Il file continua oltre la riga {result.get('last_line')}. "
                            f"Per leggere il resto: read_file con "
                            f'"offset": {result.get("last_line", 0) + 1}]'
                        )
            elif t_name == "terminal":
                obs_str += f"Output terminale (exit code {result.get('returncode')}):\n{result.get('stdout', '')}\n{result.get('stderr', '')}"
            elif t_name == "delete":
                obs_str += result.get("message", "Eliminato.")
            elif t_name == "write_file":
                obs_str += result.get("message", "File salvato.")
            elif t_name == "append_file":
                if not result.get("success"):
                    obs_str = f"Tool 'append_file' fallito: {result.get('error')}\n"
                else:
                    obs_str += result.get("message", "Contenuto aggiunto.")
            elif t_name == "edit_file":
                if not result.get("success"):
                    obs_str = f"Tool 'edit_file' fallito su '{result.get('path')}': {result.get('error')}\n"
                else:
                    obs_str += result.get("message", "File modificato.")
                    if result.get("diff"):
                        obs_str += f"\n\nDiff applicato:\n```diff\n{result.get('diff')}\n```"
            elif t_name == "glob":
                files = result.get("files", []) or []
                if not result.get("success"):
                    obs_str = f"Tool 'glob' fallito: {result.get('error')}\n"
                elif not files:
                    obs_str += f"Nessun file corrisponde al pattern '{result.get('pattern')}'."
                else:
                    obs_str += (
                        f"{len(files)} file per '{result.get('pattern')}' "
                        f"(dal piu recente):\n"
                        + "\n".join(f["rel"] for f in files)
                    )
                    if result.get("truncated"):
                        obs_str += "\n[Elenco troncato: restringi il pattern.]"
            elif t_name in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                obs_str += f"Pipeline aggiornata: {len(result.get('tasks', []))} task registrati."
            elif t_name in ("complete_goal", "finish_task", "task_complete"):
                if result.get("success"):
                    obs_str += f"Obiettivo finale completato: {result.get('summary', '')}"
                else:
                    obs_str = (
                        "COMPLETAMENTO RIFIUTATO dal sistema di verifica.\n"
                        f"{result.get('error', '')}\n"
                        "Non richiamare complete_goal finche non hai eseguito le "
                        "azioni mancanti indicate sopra: ripeterlo identico "
                        "verra rifiutato di nuovo.\n"
                    )
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

            budget = observation_budget(t_name, context_tokens)
            if len(obs_str) > budget:
                obs_str = (
                    obs_str[:budget]
                    + f"\n[...osservazione troncata a {budget} caratteri. "
                    "Richiedi una porzione piu piccola per vedere il resto...]"
                )

            tool_observations.append(obs_str)

        yield {"type": "turn_end", "turn": current_turn, "has_tools": True}

        # Append assistant turn + tool observations to message history for synthesis
        if turn_was_productive:
            unproductive_turns = 0
            force_action_turn = False
        else:
            unproductive_turns += 1

        if unproductive_turns >= MAX_UNPRODUCTIVE_TURNS and not goal_reached:
            # Rebuild from the ledger and drop the accumulated refusals. The
            # facts survive because they were never stored in the transcript
            # in the first place.
            unproductive_turns = 0
            force_action_turn = True
            directive = _recovery_directive(ledger)
            yield {
                "type": "status",
                "text": "\u26a0 Stallo in esplorazione: contesto ripulito, azione forzata",
            }
            yield {"type": "context_reset", "reason": "stallo in esplorazione"}
            full_messages = [
                full_messages[0],
                full_messages[1],
                {"role": "user", "content": directive},
            ]
            last_user_prompt = directive
            continue

        full_messages.append({"role": "assistant", "content": _as_history(full_text)})
        # A fresh view of a file supersedes every older view of it.
        for read_path in reads_this_turn:
            _drop_superseded_reads(full_messages, read_path)
        # The goal is restated with every observation. Without it the model
        # drifts into treating the latest tool output as the whole task —
        # "the user is asking me to explain this directory listing" — because
        # that output is the most recent thing in its window.
        goal_reminder = (
            f"OBIETTIVO IN CORSO: {ledger.goal[:600]}"
            if ledger.goal else "OBIETTIVO IN CORSO: vedi il primo messaggio."
        )
        if goal_reached:
            closing = (
                "Il lavoro e completo e verificato. Ora, e SOLO ora, scrivi "
                "all'utente un riepilogo chiaro di cosa hai fatto."
            )
        else:
            closing = (
                f"{goal_reminder}\n\n"
                "NON scrivere spiegazioni: non hai finito. Emetti il PROSSIMO "
                "blocco tool necessario per avanzare verso l'obiettivo, e "
                "nient'altro. Quando tutto e fatto e verificato, emetti "
                "complete_goal."
            )
        observation_prompt = (
            "Risultati dei Tool eseguiti:\n"
            + "\n---\n".join(tool_observations)
            + "\n\n"
            + closing
        )
        full_messages.append({"role": "user", "content": observation_prompt})
        full_messages = trim_history(full_messages)
        last_user_prompt = observation_prompt

    yield {"type": "done", "full_text": full_text}
