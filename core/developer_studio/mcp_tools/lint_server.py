# ==============================================================================
# core/developer_studio/mcp_tools/lint_server.py — Code Quality MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP server for code linting, formatting, and static analysis.

All tools are SAFE: they read code and report issues without modifying files
(except format_code which writes back the formatted version, still SAFE because
it is a deterministic transformation the user can undo).

The server tries multiple linters in order of preference and gracefully falls
back when one is not installed.
"""

import os
import subprocess
import json
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE
from core.developer_studio.fs_manager import get_default_workspace_root

log = get_logger(__name__)

LINT_TIMEOUT = 30


def _run_tool(args: List[str], cwd: Optional[str] = None,
              timeout: int = LINT_TIMEOUT) -> Dict[str, Any]:
    """Execute a linter/formatter CLI tool."""
    cwd = cwd or get_default_workspace_root()
    try:
        result = subprocess.run(
            args,
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
        }
    except FileNotFoundError:
        tool_name = args[0] if args else "tool"
        return {"success": False, "error": f"'{tool_name}' non trovato. Installalo con: pip install {tool_name}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout dopo {timeout}s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _find_linter() -> str:
    """Find the best available Python linter."""
    for linter in ["ruff", "flake8", "pylint"]:
        try:
            subprocess.run([linter, "--version"], capture_output=True, timeout=5)
            return linter
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""


def _find_formatter() -> str:
    """Find the best available Python formatter."""
    for fmt in ["ruff", "black", "autopep8"]:
        try:
            subprocess.run([fmt, "--version"], capture_output=True, timeout=5)
            return fmt
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""


class LintMCPServer(BaseMCPServer):
    """MCP server for code quality tools: linting, formatting, analysis."""

    def __init__(self):
        super().__init__(
            name="Developer Lint",
            version="1.0.0",
            description="Linting, formattazione e analisi statica del codice per Python e JavaScript.",
        )
        self._python_linter = _find_linter()
        self._python_formatter = _find_formatter()
        self._register_tools()

    def is_configured(self) -> bool:
        return bool(self._python_linter or self._python_formatter)

    def missing_dependency(self) -> Optional[str]:
        if not self._python_linter and not self._python_formatter:
            return "pip install ruff  (linter e formatter consigliato)"
        return None

    def _register_tools(self):
        self.register_tool(
            name="lint_python",
            description="Analizza file Python per errori, warning e problemi di stile.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella da analizzare (relativo al workspace)",
                    },
                    "fix": {
                        "type": "boolean",
                        "description": "Applica automaticamente le fix sicure (default: false)",
                    },
                },
                "required": ["path"],
            },
            handler=self._lint_python,
            safety=SAFE,
            category="developer_lint",
        )

        self.register_tool(
            name="format_code",
            description="Formatta il codice Python secondo gli standard del progetto.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella da formattare",
                    },
                    "check_only": {
                        "type": "boolean",
                        "description": "Solo verifica senza modificare (default: false)",
                    },
                },
                "required": ["path"],
            },
            handler=self._format_code,
            safety=SAFE,
            category="developer_lint",
        )

        self.register_tool(
            name="analyze_imports",
            description="Trova import inutilizzati o mancanti nei file Python.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella da analizzare",
                    },
                },
                "required": ["path"],
            },
            handler=self._analyze_imports,
            safety=SAFE,
            category="developer_lint",
        )

        self.register_tool(
            name="find_dead_code",
            description="Identifica codice potenzialmente morto o inutilizzato.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella da analizzare",
                    },
                },
                "required": ["path"],
            },
            handler=self._find_dead_code,
            safety=SAFE,
            category="developer_lint",
        )

    # -- Tool handlers -------------------------------------------------------

    def _resolve_path(self, path: str) -> str:
        """Resolve a relative path against the workspace root."""
        root = get_default_workspace_root()
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(root, path))

    def _lint_python(self, path: str, fix: bool = False) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"Percorso non trovato: {path}"}]}

        if not self._python_linter:
            return {"isError": True, "content": [{"type": "text", "text": "Nessun linter Python installato. Installa con: pip install ruff"}]}

        if self._python_linter == "ruff":
            args = ["ruff", "check", full_path, "--output-format", "text"]
            if fix:
                args.append("--fix")
        elif self._python_linter == "flake8":
            args = ["flake8", full_path, "--max-line-length", "120"]
        else:
            args = ["pylint", full_path, "--output-format", "text"]

        result = _run_tool(args)

        # Ruff returns exit code 1 when issues are found (not an error)
        output = result.get("stdout", "") or result.get("stderr", "")
        if not output and result["success"]:
            output = f"✅ Nessun problema trovato in {path}"

        return {"content": [{"type": "text", "text": output}]}

    def _format_code(self, path: str, check_only: bool = False) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"Percorso non trovato: {path}"}]}

        formatter = self._python_formatter
        if not formatter:
            return {"isError": True, "content": [{"type": "text", "text": "Nessun formatter Python installato. Installa con: pip install ruff"}]}

        if formatter == "ruff":
            args = ["ruff", "format", full_path]
            if check_only:
                args.append("--check")
        elif formatter == "black":
            args = ["black", full_path]
            if check_only:
                args.append("--check")
        else:
            args = ["autopep8", full_path]
            if not check_only:
                args.append("--in-place")
            else:
                args.append("--diff")

        result = _run_tool(args)
        output = result.get("stdout", "") or result.get("stderr", "")
        if result["success"] and not output:
            action = "verificato" if check_only else "formattato"
            output = f"✅ {path} {action} con successo."

        return {"content": [{"type": "text", "text": output}]}

    def _analyze_imports(self, path: str) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"Percorso non trovato: {path}"}]}

        # Use ruff's import rules if available
        if self._python_linter == "ruff":
            args = ["ruff", "check", full_path, "--select", "F401,I", "--output-format", "text"]
            result = _run_tool(args)
            output = result.get("stdout", "")
            if not output and result["success"]:
                output = f"✅ Nessun import inutilizzato in {path}"
            return {"content": [{"type": "text", "text": output}]}

        # Fallback: basic analysis via grep
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                imports = [
                    f"  L{i+1}: {line.strip()}"
                    for i, line in enumerate(lines)
                    if line.strip().startswith(("import ", "from "))
                ]
                output = f"Import trovati in {path}:\n" + "\n".join(imports) if imports else f"Nessun import in {path}"
                return {"content": [{"type": "text", "text": output}]}
            except Exception as exc:
                return {"isError": True, "content": [{"type": "text", "text": f"Errore: {exc}"}]}

        return {"content": [{"type": "text", "text": "Analisi import disponibile solo su file singoli senza ruff."}]}

    def _find_dead_code(self, path: str) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"Percorso non trovato: {path}"}]}

        # Try vulture first
        try:
            result = _run_tool(["vulture", full_path, "--min-confidence", "80"])
            output = result.get("stdout", "")
            if not output and result["success"]:
                output = f"✅ Nessun codice morto rilevato in {path}"
            return {"content": [{"type": "text", "text": output}]}
        except Exception:
            pass

        # Fallback to ruff dead code rules
        if self._python_linter == "ruff":
            args = ["ruff", "check", full_path, "--select", "F811,F841,E711", "--output-format", "text"]
            result = _run_tool(args)
            output = result.get("stdout", "")
            if not output and result["success"]:
                output = f"✅ Nessun codice morto rilevato con ruff in {path}"
            return {"content": [{"type": "text", "text": output}]}

        return {"content": [{"type": "text", "text": "Installa vulture (pip install vulture) o ruff per l'analisi del codice morto."}]}
