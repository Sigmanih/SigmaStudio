# ==============================================================================
# core/developer_studio/mcp_tools/test_server.py — Test Runner MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP server for running and managing test suites.

All tools are SAFE: running tests is a read-only operation that cannot alter
source code (tests that write to disk use temporary directories).
"""

import os
import subprocess
import json
import glob
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE
from core.developer_studio.fs_manager import get_default_workspace_root

log = get_logger(__name__)

TEST_TIMEOUT = 120  # tests can be slow


def _run_pytest(args: List[str], cwd: Optional[str] = None,
                timeout: int = TEST_TIMEOUT) -> Dict[str, Any]:
    """Execute pytest with structured output."""
    cwd = cwd or get_default_workspace_root()
    cmd = ["python", "-m", "pytest"] + args
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
        }
    except FileNotFoundError:
        return {"success": False, "error": "Python o pytest non trovato. Installa con: pip install pytest"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Test interrotti dopo {timeout}s (timeout)"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


class TestMCPServer(BaseMCPServer):
    """MCP server for test execution and management."""

    def __init__(self):
        super().__init__(
            name="Developer Tests",
            version="1.0.0",
            description="Esecuzione test pytest, coverage report e gestione della suite di test.",
        )
        self._register_tools()

    def is_configured(self) -> bool:
        """Check if pytest is available."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--version"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def missing_dependency(self) -> Optional[str]:
        if not self.is_configured():
            return "pip install pytest"
        return None

    def _register_tools(self):
        self.register_tool(
            name="run_tests",
            description="Esegue la suite di test pytest completa o un subset specifico.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella di test da eseguire (default: tests/)",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Filtro per nome del test (-k pattern)",
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Output verboso con dettagli per ogni test (default: true)",
                    },
                    "stop_on_first_failure": {
                        "type": "boolean",
                        "description": "Ferma al primo fallimento (-x) (default: false)",
                    },
                },
            },
            handler=self._run_tests,
            safety=SAFE,
            category="developer_tests",
        )

        self.register_tool(
            name="run_test_file",
            description="Esegue un singolo file di test con output dettagliato.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Percorso del file di test da eseguire",
                    },
                },
                "required": ["path"],
            },
            handler=self._run_test_file,
            safety=SAFE,
            category="developer_tests",
        )

        self.register_tool(
            name="list_test_files",
            description="Elenca tutti i file di test presenti nel workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Cartella da cercare (default: tests/)",
                    },
                },
            },
            handler=self._list_test_files,
            safety=SAFE,
            category="developer_tests",
        )

        self.register_tool(
            name="get_coverage",
            description="Esegue i test con report di coverage del codice.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File o cartella di test (default: tests/)",
                    },
                    "source": {
                        "type": "string",
                        "description": "Cartella sorgente da misurare (default: core/)",
                    },
                },
            },
            handler=self._get_coverage,
            safety=SAFE,
            category="developer_tests",
        )

    # -- Tool handlers -------------------------------------------------------

    def _resolve_path(self, path: str) -> str:
        root = get_default_workspace_root()
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(root, path))

    def _run_tests(self, path: str = "tests/", filter: str = "",
                   verbose: bool = True,
                   stop_on_first_failure: bool = False) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        args = [full_path]

        if verbose:
            args.append("-v")
        if filter:
            args.extend(["-k", filter])
        if stop_on_first_failure:
            args.append("-x")
        args.append("--tb=short")  # compact traceback

        result = _run_pytest(args)

        if result.get("error"):
            return {"isError": True, "content": [{"type": "text", "text": result["error"]}]}

        output = result.get("stdout", "")
        stderr = result.get("stderr", "")

        # Parse summary line
        summary = ""
        for line in output.splitlines():
            if "passed" in line or "failed" in line or "error" in line:
                summary = line
                break

        text = f"{'✅ Test superati' if result['success'] else '❌ Test falliti'}\n\n"
        if summary:
            text += f"Sommario: {summary}\n\n"
        text += f"Output completo:\n{output}"
        if stderr and not result["success"]:
            text += f"\n\nStderr:\n{stderr}"

        # Cap output
        if len(text) > 6000:
            text = text[:6000] + "\n[...output troncato...]"

        return {"content": [{"type": "text", "text": text}]}

    def _run_test_file(self, path: str) -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.isfile(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"File di test non trovato: {path}"}]}

        result = _run_pytest([full_path, "-v", "--tb=long"])

        if result.get("error"):
            return {"isError": True, "content": [{"type": "text", "text": result["error"]}]}

        output = result.get("stdout", "")
        status = "✅ Tutti i test superati" if result["success"] else "❌ Alcuni test falliti"
        text = f"{status}\n\n{output}"

        if len(text) > 6000:
            text = text[:6000] + "\n[...output troncato...]"

        return {"content": [{"type": "text", "text": text}]}

    def _list_test_files(self, path: str = "tests/") -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        if not os.path.isdir(full_path):
            return {"isError": True, "content": [{"type": "text", "text": f"Cartella non trovata: {path}"}]}

        test_files = []
        for root_dir, dirs, files in os.walk(full_path):
            # Skip __pycache__ and hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            for f in sorted(files):
                if f.startswith("test_") and f.endswith(".py"):
                    rel = os.path.relpath(os.path.join(root_dir, f), get_default_workspace_root())
                    test_files.append(rel.replace("\\", "/"))

        if not test_files:
            return {"content": [{"type": "text", "text": f"Nessun file di test trovato in {path}"}]}

        text = f"📝 {len(test_files)} file di test trovati:\n\n"
        for tf in test_files:
            text += f"  🧪 {tf}\n"
        return {"content": [{"type": "text", "text": text}]}

    def _get_coverage(self, path: str = "tests/",
                      source: str = "core/") -> Dict[str, Any]:
        full_path = self._resolve_path(path)
        full_source = self._resolve_path(source)

        # Check if pytest-cov is available
        args = [
            full_path, "-v", "--tb=short",
            f"--cov={full_source}", "--cov-report=term-missing",
        ]

        result = _run_pytest(args, timeout=180)

        if result.get("error"):
            # Likely missing pytest-cov
            if "cov" in result.get("error", "").lower() or "No module" in result.get("stderr", ""):
                return {"content": [{"type": "text", "text":
                    "pytest-cov non installato. Installa con: pip install pytest-cov\n\n"
                    "Fallback: esecuzione test senza coverage..."}]}
            return {"isError": True, "content": [{"type": "text", "text": result["error"]}]}

        output = result.get("stdout", "")
        if len(output) > 6000:
            output = output[:6000] + "\n[...output troncato...]"

        return {"content": [{"type": "text", "text": output}]}
