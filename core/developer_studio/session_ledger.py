# ==============================================================================
# core/developer_studio/session_ledger.py — Durable Working State for the Agent
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""What the agent must never forget, kept separate from what it may.

A sliding window over the message history has exactly the wrong eviction order
for an agent: the oldest messages are the tool observations that established
what the code *is*, and the newest are the model's own commentary. Trim from
the front and the agent forgets that it already read a file, already wrote one,
already saw a test fail — so it reads it again, rewrites it again, and loops.

The fix is not a bigger window. It is to stop storing facts in the transcript.
Every tool result is distilled here the moment it is produced: which files were
read and through which line, what was written, which commands passed and which
failed. That distillation is small, bounded, and re-emitted verbatim into every
subsequent prompt. The transcript above it then becomes disposable, and can be
trimmed hard without losing anything the agent needs to act correctly.
"""

import ast
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# How many recent conversational turns survive verbatim alongside the ledger.
RECENT_TURNS_KEPT = 6
# Caps that keep the re-emitted state block bounded no matter how long the run.
MAX_TRACKED_FILES = 60
MAX_TRACKED_COMMANDS = 25
MAX_TRACKED_DECISIONS = 20
MAX_ERROR_CHARS = 300


@dataclass
class FileRecord:
    """Everything the agent knows about one file it has touched."""

    path: str
    total_lines: Optional[int] = None
    lines_seen: List[Tuple[int, int]] = field(default_factory=list)
    reads: int = 0
    edits: int = 0
    writes: int = 0
    created: bool = False
    last_error: Optional[str] = None
    # Top-level names the file defines. Kept because an agent that has
    # forgotten a module's API does not ask again, it invents one.
    symbols: List[str] = field(default_factory=list)
    last_touch: float = field(default_factory=time.time)

    def mark_read(self, offset: int, last_line: int, total: Optional[int],
                  symbols: Optional[List[str]] = None) -> None:
        self.reads += 1
        if symbols:
            for name in symbols:
                if name not in self.symbols:
                    self.symbols.append(name)
        self.last_touch = time.time()
        if total is not None:
            self.total_lines = total
        if offset and last_line:
            self.lines_seen.append((int(offset), int(last_line)))
            self.lines_seen = _merge_ranges(self.lines_seen)

    @property
    def fully_read(self) -> bool:
        """True when the union of read windows covers the whole file."""
        if not self.total_lines or not self.lines_seen:
            return False
        return self.lines_seen[0] == (1, self.total_lines)

    def coverage_note(self) -> str:
        if self.total_lines is None:
            return "letto"
        if self.fully_read:
            return f"letto integralmente ({self.total_lines} righe)"
        spans = ", ".join(f"{a}-{b}" for a, b in self.lines_seen[:4])
        return f"letto righe {spans} di {self.total_lines}"


# Something that looks like a workspace path: at least one separator or a
# recognised source extension. Deliberately loose — a false positive costs one
# extra line in the prompt, a false negative costs the agent its target.
_PATH_RE = re.compile(
    r"(?<![\w./\\])((?:[\w.\-]+[/\\])+[\w.\-]+"
    r"|[\w.\-]+\.(?:json|jsonc|yaml|yml|py|tsx|jsx|ts|js|md|css|scss|html|toml|txt|sh|bat|cfg|ini))"
)


def _extract_paths(text: str) -> List[str]:
    """File paths mentioned in a goal, in order, de-duplicated."""
    seen, out = set(), []
    for m in _PATH_RE.finditer(text or ""):
        p = m.group(1).replace("\\", "/").strip(".,;:)")
        if p and p not in seen and not p.startswith("http"):
            seen.add(p)
            out.append(p)
    return out[:12]


def _public_symbols(path: str, content: str) -> List[str]:
    """Top-level classes and functions a Python source file defines.

    Parsed rather than pattern-matched, so a `def` inside a docstring or a
    nested helper does not end up advertised as part of the module's API. A
    file that does not parse — because only part of it was read — yields
    nothing rather than a misleading half-list.
    """
    if not path.endswith(".py") or not content:
        return []
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(f"def {node.name}")
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            # The methods matter more than the class name: knowing a class
            # exists tells the caller nothing about what to call on it, and
            # that is precisely the gap an agent fills by inventing.
            methods = [
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and (not child.name.startswith("_") or child.name == "__init__")
            ]
            if methods:
                names.append(f"class {node.name}({', '.join(methods[:20])})")
            else:
                names.append(f"class {node.name}")
    return names[:40]


def _merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Collapses overlapping or adjacent line spans into a minimal cover."""
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


class DevSessionLedger:
    """Durable, bounded record of what an agent run has actually done.

    Thread-safe because the agent loop runs on a worker thread while the SSE
    handler reads the same state to stream progress to the UI.
    """

    def __init__(self, goal: str = "", workspace_root: Optional[str] = None):
        self.goal = goal
        # Paths are rendered relative to the workspace: an absolute Windows path
        # repeated across sixty files is pure prompt tax, and the model reasons
        # about the tree in the same relative terms the tools accept.
        self.workspace_root = str(workspace_root).replace("\\", "/").rstrip("/") if workspace_root else ""
        self._files: Dict[str, FileRecord] = {}
        self._commands: List[Dict[str, Any]] = []
        self._decisions: List[str] = []
        self._failures: List[str] = []
        self._pipeline: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self.started_at = time.time()
        self.goal_paths: List[str] = _extract_paths(goal)

    # -- recording -----------------------------------------------------------

    def set_goal(self, goal: str) -> None:
        with self._lock:
            self.goal = goal

    def set_pipeline(self, tasks: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._pipeline = list(tasks or [])

    def add_decision(self, text: str) -> None:
        with self._lock:
            text = (text or "").strip()
            if text and text not in self._decisions:
                self._decisions.append(text)
                del self._decisions[:-MAX_TRACKED_DECISIONS]

    def _rel(self, path: str) -> str:
        """Workspace-relative form of a path, or the path itself if outside."""
        p = str(path or "").replace("\\", "/")
        root = self.workspace_root
        if root and p.lower().startswith(root.lower() + "/"):
            return p[len(root) + 1:]
        return p

    def _file(self, path: str) -> FileRecord:
        rec = self._files.get(path)
        if rec is None:
            rec = FileRecord(path=path)
            self._files[path] = rec
            # Evict the least recently touched file rather than the first one
            # recorded: recency is what predicts relevance to the next step.
            if len(self._files) > MAX_TRACKED_FILES:
                oldest = min(self._files.values(), key=lambda r: r.last_touch)
                self._files.pop(oldest.path, None)
        return rec

    def record_tool(self, tool: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Distils one tool execution into durable state."""
        tool = (tool or "").lower()
        params = params or {}
        result = result or {}
        ok = bool(result.get("success"))
        path = self._rel(result.get("full_path") or result.get("path") or params.get("path") or "")

        with self._lock:
            if tool == "read_file" and path:
                rec = self._file(path)
                if ok:
                    rec.mark_read(
                        result.get("offset") or 1,
                        result.get("last_line") or 0,
                        result.get("total_lines"),
                        symbols=_public_symbols(path, result.get("content") or ""),
                    )
                else:
                    rec.last_error = str(result.get("error", ""))[:MAX_ERROR_CHARS]

            elif tool in ("write_file", "edit_file") and path:
                rec = self._file(path)
                rec.last_touch = time.time()
                if ok:
                    if tool == "edit_file":
                        rec.edits += 1
                        if result.get("lines_after") is not None:
                            rec.total_lines = result.get("lines_after")
                    else:
                        rec.writes += 1
                        rec.created = rec.created or rec.reads == 0
                        # A full rewrite invalidates every previously read window.
                        rec.lines_seen = []
                        rec.total_lines = None
                    rec.last_error = None
                else:
                    rec.last_error = str(result.get("error", ""))[:MAX_ERROR_CHARS]

            elif tool == "terminal":
                cmd = str(params.get("command") or result.get("command") or "")[:200]
                rc = result.get("returncode", 0)
                entry = {
                    "command": cmd,
                    "returncode": rc,
                    "ok": ok and rc == 0,
                    "at": time.time(),
                }
                if not entry["ok"]:
                    tail = (result.get("stderr") or result.get("stdout") or "").strip()
                    entry["error"] = tail[-MAX_ERROR_CHARS:]
                self._commands.append(entry)
                del self._commands[:-MAX_TRACKED_COMMANDS]

            elif tool in ("pipeline", "tasks", "set_tasks", "update_pipeline"):
                self._pipeline = list(result.get("tasks") or [])

            if not ok and result.get("error"):
                note = f"{tool}: {str(result['error'])[:MAX_ERROR_CHARS]}"
                self._failures.append(note)
                del self._failures[:-10]

    # -- querying (used by the verification gate and the UI) -----------------

    @property
    def modified_files(self) -> List[str]:
        with self._lock:
            return [p for p, r in self._files.items() if r.edits or r.writes]

    @property
    def read_files(self) -> List[str]:
        with self._lock:
            return [p for p, r in self._files.items() if r.reads]

    def has_modifications(self) -> bool:
        return bool(self.modified_files)

    def was_read_before_change(self, path: str) -> bool:
        with self._lock:
            rec = self._files.get(self._rel(path))
            return bool(rec and rec.reads)

    def successful_commands(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c for c in self._commands if c["ok"]]

    def failed_commands(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [c for c in self._commands if not c["ok"]]

    def last_command(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._commands[-1] if self._commands else None

    def last_verification(self) -> Optional[Dict[str, Any]]:
        """The most recent command that plausibly proves the code works.

        Recency matters more than existence: an agent that ran a green test
        suite, then broke the code, then ran nothing has not verified anything
        about the code as it now stands.
        """
        with self._lock:
            for c in reversed(self._commands):
                if looks_like_verification(c["command"]):
                    return c
            return None

    def snapshot(self) -> Dict[str, Any]:
        """Machine-readable state, for the Developer Studio monitoring panel."""
        with self._lock:
            return {
                "goal": self.goal,
                "elapsed_s": round(time.time() - self.started_at, 1),
                "files": [
                    {
                        "path": r.path,
                        "reads": r.reads,
                        "edits": r.edits,
                        "writes": r.writes,
                        "total_lines": r.total_lines,
                        "fully_read": r.fully_read,
                        "created": r.created,
                        "last_error": r.last_error,
                    }
                    for r in sorted(self._files.values(), key=lambda x: -x.last_touch)
                ],
                "commands": list(self._commands),
                "decisions": list(self._decisions),
                "failures": list(self._failures),
                "pipeline": list(self._pipeline),
            }

    # -- prompt rendering ----------------------------------------------------

    def render_state_block(self) -> str:
        """The state block re-emitted into every prompt, in place of old turns."""
        with self._lock:
            parts: List[str] = ["## STATO DEL LAVORO (aggiornato automaticamente, non ripetere azioni gia svolte)"]

            if self.goal:
                parts.append(f"\n**Obiettivo:** {self.goal}")

            if self.goal_paths:
                parts.append(
                    "\n**Percorsi citati nell'obiettivo — usa ESATTAMENTE questi, "
                    "non inventarne altri:**"
                )
                parts.extend(f"- `{p}`" for p in self.goal_paths)

            if self._pipeline:
                parts.append("\n**Pipeline:**")
                for t in self._pipeline:
                    status = str(t.get("status", "pending"))
                    tag = {"done": "[FATTO]", "in_progress": "[IN CORSO]"}.get(status, "[IN CODA]")
                    parts.append(f"- {tag} #{t.get('id', '?')} {t.get('title', '')}")

            read_only = [r for r in self._files.values() if r.reads and not (r.edits or r.writes)]
            changed = [r for r in self._files.values() if r.edits or r.writes]

            if changed:
                parts.append("\n**File GIA modificati da te in questa sessione:**")
                for r in sorted(changed, key=lambda x: -x.last_touch):
                    what = []
                    if r.created:
                        what.append("creato")
                    if r.edits:
                        what.append(f"{r.edits} edit")
                    if r.writes and not r.created:
                        what.append(f"{r.writes} riscrittur{'a' if r.writes == 1 else 'e'}")
                    line = f"- `{r.path}` — {', '.join(what)}"
                    if r.total_lines:
                        line += f" ({r.total_lines} righe)"
                    if r.last_error:
                        line += f"  !! ultimo errore: {r.last_error}"
                    parts.append(line)

            with_api = [r for r in self._files.values() if r.symbols]
            if with_api:
                parts.append(
                    "\n**API dei file gia letti — usa ESATTAMENTE questi nomi, "
                    "non inventarne altri:**"
                )
                for r in sorted(with_api, key=lambda x: -x.last_touch)[:15]:
                    parts.append(f"- `{r.path}`: {', '.join(r.symbols)}")

            if read_only:
                parts.append("\n**File gia letti (non rileggerli senza motivo):**")
                for r in sorted(read_only, key=lambda x: -x.last_touch)[:25]:
                    parts.append(f"- `{r.path}` — {r.coverage_note()}")

            if self._commands:
                parts.append("\n**Comandi eseguiti:**")
                for c in self._commands[-10:]:
                    mark = "OK " if c["ok"] else "FALLITO"
                    line = f"- [{mark}] `{c['command']}`"
                    if not c["ok"] and c.get("error"):
                        line += f"\n      -> {c['error']}"
                    parts.append(line)

            if self._decisions:
                parts.append("\n**Decisioni prese:**")
                parts.extend(f"- {d}" for d in self._decisions)

            if self._failures:
                parts.append("\n**Errori recenti da non ripetere:**")
                parts.extend(f"- {f}" for f in self._failures[-5:])

            return "\n".join(parts)


# ---------------------------------------------------------------------------
# Verification gate
# ---------------------------------------------------------------------------

# Commands that count as having actually verified something, as opposed to
# having merely looked at the code again.
VERIFICATION_HINTS = (
    "pytest", "unittest", "npm test", "npm run test", "yarn test", "vitest",
    "jest", "ruff", "flake8", "mypy", "pylint", "eslint", "tsc",
    "npm run build", "npm run lint", "py_compile", "-m compileall",
    "import ", "node -e",
)


def looks_like_verification(command: str) -> bool:
    """Whether a shell command plausibly proves the code works."""
    c = (command or "").lower()
    return any(hint in c for hint in VERIFICATION_HINTS)


def check_completion_allowed(ledger: DevSessionLedger) -> Dict[str, Any]:
    """Decides whether `complete_goal` may be honoured yet.

    An agent declaring success is the cheapest token it can emit and the most
    expensive one to trust: the whole point of an autonomous loop is that
    nobody is checking behind it. So completion is gated on evidence that
    already exists in the ledger, not on the model's own assessment.
    """
    if not ledger.has_modifications():
        return {
            "allowed": False,
            "reason": (
                "Nessun file risulta creato o modificato in questa sessione. "
                "Non puoi dichiarare completato un obiettivo di sviluppo senza "
                "aver scritto codice reale con write_file o edit_file."
            ),
        }

    # A failure that was subsequently fixed must not block forever, so only the
    # *current* state of the workspace is judged: the last command run, and the
    # last verification run. Anything older has been superseded.
    last = ledger.last_command()
    if last and not last["ok"]:
        return {
            "allowed": False,
            "reason": (
                f"L'ultimo comando eseguito e fallito (exit {last['returncode']}): "
                f"`{last['command']}`. Correggi la causa e rilancialo con esito "
                "positivo prima di completare."
            ),
        }

    verification = ledger.last_verification()
    if verification is None:
        return {
            "allowed": False,
            "reason": (
                "Hai modificato dei file ma non hai ancora VERIFICATO nulla. "
                "Esegui con `terminal` almeno un test, un lint o un import del "
                "codice che hai scritto (es. `python -m pytest`, `python -m "
                "py_compile <file>`, `npm run build`) e ottieni exit code 0, "
                "poi richiama complete_goal."
            ),
        }
    if not verification["ok"]:
        return {
            "allowed": False,
            "reason": (
                f"L'ultima verifica eseguita e fallita: `{verification['command']}`. "
                "Il codice non e in uno stato consegnabile: correggilo e rilancia "
                "la verifica con esito positivo."
            ),
        }

    return {
        "allowed": True,
        "evidence": {
            "modified_files": ledger.modified_files,
            "verified_by": verification["command"],
        },
    }
