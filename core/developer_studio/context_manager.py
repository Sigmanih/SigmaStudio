# ==============================================================================
# core/developer_studio/context_manager.py — Shared Context Between Roles
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Manages the shared context between development roles, optimising what each
role sees in its prompt window.

The key insight: each role in a development workflow needs the same *project
context* (file tree, goal, prior decisions) but different *working context*
(the Architect sees architecture diagrams, the Coder sees implementation
details, the Tester sees test coverage).  By structuring the context into a
stable prefix and a role-specific suffix, the KV-cache of the prefix portion
can be shared across role switches.
"""

import os
import time
import difflib
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.logger import get_logger
from core.developer_studio.fs_manager import get_workspace_tree, get_default_workspace_root

log = get_logger(__name__)

# Maximum characters of file tree to include in context
MAX_TREE_CHARS = 3000
# Maximum characters per tracked file content in context
MAX_FILE_PREVIEW_CHARS = 2000
# Maximum total characters for role context
MAX_ROLE_CONTEXT_CHARS = 12000


# ---------------------------------------------------------------------------
# File change tracker
# ---------------------------------------------------------------------------

@dataclass
class FileChange:
    """Tracks a single file modification during a session."""
    path: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    diff: Optional[str] = None
    timestamp: float = 0.0
    role: str = ""                # which role made the change

    @property
    def is_new(self) -> bool:
        return self.old_content is None

    @property
    def is_deletion(self) -> bool:
        return self.new_content is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "is_new": self.is_new,
            "is_deletion": self.is_deletion,
            "role": self.role,
            "diff_lines": len(self.diff.splitlines()) if self.diff else 0,
        }


class FileContextTracker:
    """Tracks all file changes during a development session."""

    def __init__(self):
        self._changes: Dict[str, FileChange] = {}
        self._lock = threading.Lock()

    def track_change(self, path: str, old_content: Optional[str],
                     new_content: Optional[str], role: str = "") -> FileChange:
        """Record a file modification with diff generation."""
        diff_text = None
        if old_content is not None and new_content is not None:
            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{Path(path).name}",
                tofile=f"b/{Path(path).name}",
            )
            diff_text = "".join(diff)

        change = FileChange(
            path=path,
            old_content=old_content,
            new_content=new_content,
            diff=diff_text,
            timestamp=time.time(),
            role=role,
        )

        with self._lock:
            self._changes[path] = change
        return change

    def get_changes(self) -> List[FileChange]:
        with self._lock:
            return list(self._changes.values())

    def get_changed_paths(self) -> List[str]:
        with self._lock:
            return list(self._changes.keys())

    def get_summary(self) -> str:
        """Human-readable summary of all changes for commit messages."""
        changes = self.get_changes()
        if not changes:
            return "Nessuna modifica."

        lines = [f"📝 {len(changes)} file modificati:"]
        for ch in sorted(changes, key=lambda c: c.timestamp):
            status = "🆕 NUOVO" if ch.is_new else "❌ ELIMINATO" if ch.is_deletion else "✏️ MODIFICATO"
            diff_info = f" ({len(ch.diff.splitlines())} righe di diff)" if ch.diff else ""
            lines.append(f"  {status} {ch.path}{diff_info}")
        return "\n".join(lines)

    def get_diffs_for_review(self) -> str:
        """All diffs concatenated for code review."""
        changes = self.get_changes()
        parts = []
        for ch in sorted(changes, key=lambda c: c.path):
            if ch.diff:
                parts.append(f"--- {ch.path} ---\n{ch.diff}")
            elif ch.is_new and ch.new_content:
                preview = ch.new_content[:MAX_FILE_PREVIEW_CHARS]
                parts.append(f"--- {ch.path} (NUOVO) ---\n{preview}")
        return "\n\n".join(parts)

    def clear(self) -> None:
        with self._lock:
            self._changes.clear()


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------

@dataclass
class SessionContext:
    """Global session state shared across all roles."""

    goal: str = ""
    branch_name: str = ""
    workspace_root: str = ""
    file_tree_cache: str = ""
    file_tree_updated_at: float = 0.0
    decisions: List[str] = field(default_factory=list)
    phase: str = "init"                 # init → analyze → setup → implement → verify → deliver
    start_time: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Context Manager
# ---------------------------------------------------------------------------

class DevContextManager:
    """Manages shared context between roles, optimising KV-cache reuse.

    The context is structured in two layers:

    1. **Shared prefix** (stable across roles):
       - Project description and goal
       - File tree summary
       - Prior decisions and outputs from upstream tasks

    2. **Role-specific suffix** (changes per role):
       - Role instructions and focus areas
       - Relevant file contents
       - Prior outputs from this specific role

    This structure lets the KV-cache of the shared prefix be reused when
    switching between roles, saving ~60% of prefill time.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.session = SessionContext(
            workspace_root=workspace_root or get_default_workspace_root()
        )
        self.files = FileContextTracker()
        self.role_outputs: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def set_goal(self, goal: str) -> None:
        self.session.goal = goal

    def set_branch(self, branch_name: str) -> None:
        self.session.branch_name = branch_name

    def set_phase(self, phase: str) -> None:
        self.session.phase = phase

    def add_decision(self, decision: str) -> None:
        self.session.decisions.append(decision)

    def record_role_output(self, role_id: str, output: str) -> None:
        """Store a role's output for use by downstream roles."""
        with self._lock:
            if role_id not in self.role_outputs:
                self.role_outputs[role_id] = []
            self.role_outputs[role_id].append(output)

    # -- file tree -----------------------------------------------------------

    def refresh_file_tree(self, force: bool = False) -> str:
        """Get a compact file tree of the workspace, cached for 30 seconds."""
        now = time.time()
        if not force and self.session.file_tree_cache and (now - self.session.file_tree_updated_at) < 30:
            return self.session.file_tree_cache

        try:
            tree = get_workspace_tree(self.session.workspace_root, max_depth=3)
            tree_text = self._format_tree(tree)
            if len(tree_text) > MAX_TREE_CHARS:
                tree_text = tree_text[:MAX_TREE_CHARS] + "\n[...albero troncato...]"
            self.session.file_tree_cache = tree_text
            self.session.file_tree_updated_at = now
        except Exception as exc:
            log.warning("Could not refresh file tree: %s", exc)
            self.session.file_tree_cache = "(albero non disponibile)"

        return self.session.file_tree_cache

    def _format_tree(self, tree: Dict[str, Any], indent: int = 0) -> str:
        """Format a tree dict into readable text."""
        if not tree:
            return ""
        lines = []
        name = tree.get("name", "")
        is_dir = tree.get("is_dir", False)
        prefix = "  " * indent
        icon = "📁" if is_dir else "📄"
        lines.append(f"{prefix}{icon} {name}")
        for child in tree.get("children", []):
            lines.append(self._format_tree(child, indent + 1))
        return "\n".join(lines)

    # -- context building ----------------------------------------------------

    def build_shared_prefix(self) -> str:
        """The stable portion of the context, shared across all roles.

        This is what goes into the KV-cache prefix: it must be identical
        across role switches for the cache to hit.
        """
        parts = [
            "# CONTESTO SESSIONE DI SVILUPPO",
            "",
            f"**Obiettivo**: {self.session.goal}" if self.session.goal else "",
            f"**Fase corrente**: {self.session.phase}",
            f"**Branch**: {self.session.branch_name}" if self.session.branch_name else "",
            f"**Workspace**: {self.session.workspace_root}",
            "",
        ]

        # Decisions log
        if self.session.decisions:
            parts.append("## Decisioni prese:")
            for d in self.session.decisions[-10:]:  # last 10
                parts.append(f"- {d}")
            parts.append("")

        # File tree
        tree = self.refresh_file_tree()
        if tree:
            parts.append("## Struttura del progetto:")
            parts.append(f"```\n{tree}\n```")
            parts.append("")

        # File changes summary
        changes_summary = self.files.get_summary()
        if changes_summary and "Nessuna" not in changes_summary:
            parts.append("## Modifiche nella sessione corrente:")
            parts.append(changes_summary)
            parts.append("")

        return "\n".join(p for p in parts if p is not None)

    def build_context_for_role(self, role_id: str,
                               task_description: str = "",
                               upstream_outputs: Optional[Dict[str, str]] = None
                               ) -> str:
        """Build the complete context for a specific role.

        The result is: shared_prefix + role_specific_suffix.
        The shared_prefix is stable across roles for KV-cache reuse.
        """
        parts = [self.build_shared_prefix()]

        # Upstream role outputs (e.g., Architect's plan for the Coder)
        if upstream_outputs:
            parts.append("## Output dei ruoli precedenti:")
            for upstream_role, output in upstream_outputs.items():
                truncated = output[:MAX_FILE_PREVIEW_CHARS]
                parts.append(f"### {upstream_role}:")
                parts.append(truncated)
                if len(output) > MAX_FILE_PREVIEW_CHARS:
                    parts.append("[...output troncato...]")
            parts.append("")

        # Task-specific instructions
        if task_description:
            parts.append("## Task corrente:")
            parts.append(task_description)
            parts.append("")

        # Recent diffs for review roles
        if role_id in ("reviewer", "tester"):
            diffs = self.files.get_diffs_for_review()
            if diffs:
                truncated = diffs[:MAX_ROLE_CONTEXT_CHARS]
                parts.append("## Diff delle modifiche da revisionare:")
                parts.append(f"```diff\n{truncated}\n```")
                if len(diffs) > MAX_ROLE_CONTEXT_CHARS:
                    parts.append("[...diff troncato...]")
                parts.append("")

        result = "\n".join(parts)
        if len(result) > MAX_ROLE_CONTEXT_CHARS * 2:
            result = result[:MAX_ROLE_CONTEXT_CHARS * 2] + "\n[...contesto troncato...]"
        return result

    def get_commit_context(self) -> Dict[str, Any]:
        """Context for generating a commit message."""
        return {
            "goal": self.session.goal,
            "branch": self.session.branch_name,
            "changes": self.files.get_summary(),
            "diffs": self.files.get_diffs_for_review(),
            "decisions": self.session.decisions,
            "files_modified": self.files.get_changed_paths(),
        }

    def reset(self) -> None:
        """Reset all context for a new session."""
        self.session = SessionContext(workspace_root=self.session.workspace_root)
        self.files.clear()
        self.role_outputs.clear()
