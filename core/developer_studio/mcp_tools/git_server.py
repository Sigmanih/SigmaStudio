# ==============================================================================
# core/developer_studio/mcp_tools/git_server.py — Git Operations MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP server exposing Git operations to AI agents through the unified hub.

Read operations (status, diff, log) are SAFE — they cannot alter the
repository.  Write operations (branch, checkout, add, commit, push) are
SENSITIVE and require human approval unless auto_approve is enabled.

All operations shell out to the `git` CLI rather than using a Python library:
the CLI is always present if the repo exists, its output is well-defined, and
the agent can read the same messages a human would.
"""

import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.developer_studio.fs_manager import get_default_workspace_root

log = get_logger(__name__)

# Git command timeout in seconds
GIT_TIMEOUT = 30


def _run_git(args: List[str], cwd: Optional[str] = None,
             timeout: int = GIT_TIMEOUT) -> Dict[str, Any]:
    """Execute a git command and return structured output."""
    cwd = cwd or get_default_workspace_root()
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout dopo {timeout}s", "command": " ".join(cmd)}
    except FileNotFoundError:
        return {"success": False, "error": "Git non trovato nel PATH di sistema."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _sanitize_branch_name(name: str) -> str:
    """Sanitize a branch name to be Git-safe."""
    safe = re.sub(r"[^a-zA-Z0-9/_-]", "-", name.strip())
    safe = re.sub(r"-{2,}", "-", safe).strip("-")
    return safe[:80] or "dev-branch"


class GitMCPServer(BaseMCPServer):
    """MCP server for Git repository operations."""

    def __init__(self):
        super().__init__(
            name="Developer Git",
            version="1.0.0",
            description="Operazioni Git: status, diff, log, branch, commit, push per il Developer Studio.",
        )
        self._register_tools()

    def is_configured(self) -> bool:
        """Check if we're in a git repository."""
        result = _run_git(["rev-parse", "--is-inside-work-tree"], timeout=5)
        return result.get("success", False)

    def missing_dependency(self) -> Optional[str]:
        result = _run_git(["--version"], timeout=5)
        if not result.get("success"):
            return "Git non installato. Scarica da https://git-scm.com/"
        return None

    def _register_tools(self):
        # -- Safe (read-only) tools --

        self.register_tool(
            name="git_status",
            description="Mostra lo stato del repository Git: file modificati, staged, untracked.",
            input_schema={
                "type": "object",
                "properties": {
                    "short": {
                        "type": "boolean",
                        "description": "Formato compatto (default: false)",
                    },
                },
            },
            handler=self._git_status,
            safety=SAFE,
            category="developer_git",
        )

        self.register_tool(
            name="git_diff",
            description="Mostra le differenze tra working tree e staged, o tra due riferimenti.",
            input_schema={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "Mostra diff dei file staged (default: false)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Limita il diff a un file o cartella specifici",
                    },
                },
            },
            handler=self._git_diff,
            safety=SAFE,
            category="developer_git",
        )

        self.register_tool(
            name="git_log",
            description="Mostra gli ultimi commit del repository.",
            input_schema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Numero di commit da mostrare (default: 10, max: 50)",
                    },
                    "oneline": {
                        "type": "boolean",
                        "description": "Formato compatto una riga per commit (default: true)",
                    },
                },
            },
            handler=self._git_log,
            safety=SAFE,
            category="developer_git",
        )

        self.register_tool(
            name="git_branch_list",
            description="Elenca tutti i branch locali e remoti.",
            input_schema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Includi anche i branch remoti (default: false)",
                    },
                },
            },
            handler=self._git_branch_list,
            safety=SAFE,
            category="developer_git",
        )

        # -- Sensitive (write) tools --

        self.register_tool(
            name="git_branch_create",
            description="Crea un nuovo branch Git e si sposta su di esso.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nome del branch (es. feat/nuova-funzione)",
                    },
                    "from_ref": {
                        "type": "string",
                        "description": "Branch o commit di partenza (default: HEAD)",
                    },
                },
                "required": ["name"],
            },
            handler=self._git_branch_create,
            safety=SENSITIVE,
            category="developer_git",
        )

        self.register_tool(
            name="git_checkout",
            description="Cambia branch attivo nel repository.",
            input_schema={
                "type": "object",
                "properties": {
                    "branch": {
                        "type": "string",
                        "description": "Nome del branch su cui spostarsi",
                    },
                },
                "required": ["branch"],
            },
            handler=self._git_checkout,
            safety=SENSITIVE,
            category="developer_git",
        )

        self.register_tool(
            name="git_add",
            description="Aggiunge file all'area di staging per il prossimo commit.",
            input_schema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File o cartelle da aggiungere allo staging. Usa ['.'] per tutto.",
                    },
                },
                "required": ["paths"],
            },
            handler=self._git_add,
            safety=SENSITIVE,
            category="developer_git",
        )

        self.register_tool(
            name="git_commit",
            description="Crea un commit con i file attualmente in staging.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Messaggio del commit (formato Conventional Commits)",
                    },
                },
                "required": ["message"],
            },
            handler=self._git_commit,
            safety=SENSITIVE,
            category="developer_git",
        )

        self.register_tool(
            name="git_push",
            description="Invia i commit locali al repository remoto.",
            input_schema={
                "type": "object",
                "properties": {
                    "remote": {
                        "type": "string",
                        "description": "Nome del remote (default: origin)",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch da pushare (default: branch corrente)",
                    },
                    "set_upstream": {
                        "type": "boolean",
                        "description": "Imposta il tracking upstream (default: true per branch nuovi)",
                    },
                },
            },
            handler=self._git_push,
            safety=SENSITIVE,
            category="developer_git",
        )

        self.register_tool(
            name="git_stash",
            description="Salva o ripristina modifiche temporanee con git stash.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["push", "pop", "list"],
                        "description": "Azione: push (salva), pop (ripristina), list (elenca)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Messaggio per lo stash (solo con push)",
                    },
                },
                "required": ["action"],
            },
            handler=self._git_stash,
            safety=SENSITIVE,
            category="developer_git",
        )

    # -- Tool handlers -------------------------------------------------------

    def _git_status(self, short: bool = False) -> Dict[str, Any]:
        args = ["status"]
        if short:
            args.append("--short")
        result = _run_git(args)
        if result["success"]:
            # Also get the current branch
            branch = _run_git(["branch", "--show-current"])
            return {
                "content": [{
                    "type": "text",
                    "text": f"Branch corrente: {branch.get('stdout', '?')}\n\n{result['stdout']}",
                }]
            }
        return {"isError": True, "content": [{"type": "text", "text": result.get("error", result.get("stderr", ""))}]}

    def _git_diff(self, staged: bool = False, path: str = "") -> Dict[str, Any]:
        args = ["diff"]
        if staged:
            args.append("--staged")
        args.append("--stat")  # summary first
        stat_result = _run_git(args)

        # Full diff (capped)
        full_args = ["diff"]
        if staged:
            full_args.append("--staged")
        if path:
            full_args.extend(["--", path])
        full_result = _run_git(full_args)

        if full_result["success"]:
            diff_text = full_result["stdout"]
            if len(diff_text) > 8000:
                diff_text = diff_text[:8000] + "\n[...diff troncato...]"
            output = f"Statistiche:\n{stat_result.get('stdout', '')}\n\nDiff:\n{diff_text}"
            return {"content": [{"type": "text", "text": output}]}
        return {"isError": True, "content": [{"type": "text", "text": full_result.get("stderr", "")}]}

    def _git_log(self, count: int = 10, oneline: bool = True) -> Dict[str, Any]:
        count = min(max(count, 1), 50)
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--format=%h %s (%an, %ar)"])
        result = _run_git(args)
        if result["success"]:
            return {"content": [{"type": "text", "text": result["stdout"] or "Nessun commit."}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}

    def _git_branch_list(self, all: bool = False) -> Dict[str, Any]:
        args = ["branch"]
        if all:
            args.append("-a")
        result = _run_git(args)
        if result["success"]:
            return {"content": [{"type": "text", "text": result["stdout"] or "Nessun branch."}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}

    def _git_branch_create(self, name: str, from_ref: str = "") -> Dict[str, Any]:
        safe_name = _sanitize_branch_name(name)
        args = ["checkout", "-b", safe_name]
        if from_ref:
            args.append(from_ref)
        result = _run_git(args)
        if result["success"]:
            return {"content": [{"type": "text", "text": f"Branch '{safe_name}' creato e attivato."}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", result.get("error", ""))}]}

    def _git_checkout(self, branch: str) -> Dict[str, Any]:
        result = _run_git(["checkout", branch.strip()])
        if result["success"]:
            return {"content": [{"type": "text", "text": f"Switchato al branch '{branch.strip()}'."}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}

    def _git_add(self, paths: List[str] = None) -> Dict[str, Any]:
        if not paths:
            paths = ["."]
        result = _run_git(["add"] + paths)
        if result["success"]:
            # Show what was staged
            status = _run_git(["status", "--short"])
            return {"content": [{"type": "text", "text": f"File aggiunti allo staging.\n{status.get('stdout', '')}"}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}

    def _git_commit(self, message: str) -> Dict[str, Any]:
        if not message or not message.strip():
            return {"isError": True, "content": [{"type": "text", "text": "Messaggio di commit mancante."}]}
        result = _run_git(["commit", "-m", message.strip()])
        if result["success"]:
            return {"content": [{"type": "text", "text": result["stdout"]}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}

    def _git_push(self, remote: str = "origin", branch: str = "",
                  set_upstream: bool = True) -> Dict[str, Any]:
        args = ["push"]
        if not branch:
            br = _run_git(["branch", "--show-current"])
            branch = br.get("stdout", "").strip()
        if set_upstream:
            args.extend(["-u", remote, branch])
        else:
            args.extend([remote, branch])
        result = _run_git(args, timeout=60)
        if result["success"]:
            output = result["stdout"] or result["stderr"]  # git push outputs to stderr
            return {"content": [{"type": "text", "text": f"Push completato.\n{output}"}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", result.get("error", ""))}]}

    def _git_stash(self, action: str = "push", message: str = "") -> Dict[str, Any]:
        args = ["stash", action]
        if action == "push" and message:
            args.extend(["-m", message])
        result = _run_git(args)
        if result["success"]:
            return {"content": [{"type": "text", "text": result["stdout"] or f"Stash {action} completato."}]}
        return {"isError": True, "content": [{"type": "text", "text": result.get("stderr", "")}]}
