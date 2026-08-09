# ==============================================================================
# core/mcp/developer_server.py — Developer MCP Server
# Git, Pytest, Code Editing, Workspace Files, and Python Sandbox
# ==============================================================================
import os
import json
import subprocess
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.logger import get_logger

log = get_logger(__name__)


class DeveloperMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="Developer MCP",
            version="1.0.0",
            description="Git, Pytest, code compilation, workspace file manipulation, and Python sandbox"
        )
        self._init_tools()
        self._init_resources()

    def _init_tools(self):
        self.register_tool(
            name="run_pytest",
            description="Execute automated pytest unit test suite or specific test file.",
            input_schema={
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Optional test file or test expression"}
                }
            },
            handler=self._handle_run_pytest,
            safety=SAFE,
            category="dev_tools",
        )

        self.register_tool(
            name="create_workspace_file",
            description="Safely create or update a file in the workspace data/ or scripts/ directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path (e.g. data/Topic/file.md)"},
                    "content": {"type": "string", "description": "File content text"}
                },
                "required": ["path", "content"]
            },
            handler=self._handle_create_workspace_file,
            safety=SENSITIVE,
            category="dev_tools",
        )

        self.register_tool(
            name="execute_sandbox_code",
            description="Run Python code snippet in safe isolated execution sandbox.",
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code snippet to execute"}
                },
                "required": ["code"]
            },
            handler=self._handle_execute_sandbox_code,
            safety=SENSITIVE,
            category="dev_tools",
        )

        self.register_tool(
            name="git_status",
            description="Get current Git status, modified files, and active branch.",
            input_schema={"type": "object", "properties": {}},
            handler=self._handle_git_status,
            safety=SAFE,
            category="dev_tools",
        )

    def _init_resources(self):
        self.register_resource(
            uri="developer://git/status",
            name="Git Repository Status",
            description="Current git branch and modified status",
            mime_type="application/json",
            handler=self._read_git_status
        )
        self.register_resource(
            uri="developer://workspace/structure",
            name="Workspace Directory Tree",
            description="Overview of files and folders in workspace",
            mime_type="application/json",
            handler=self._read_workspace_structure
        )

    def _handle_run_pytest(self, test_path: str = None, **kwargs):
        try:
            cmd = ["pytest"]
            if test_path:
                cmd.append(test_path)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=os.getcwd())
            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout[-4000:],
                "stderr": res.stderr[-2000:]
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_create_workspace_file(self, path: str = "data/test_sample.md", content: str = "Sample content", **kwargs):
        try:
            from core.file_handler import handle_create_file
            target_path = path or "data/test_sample.md"
            target_content = content or kwargs.get("query") or "Sample content"
            clean_path = target_path.replace("\\", "/").strip("/")
            os.makedirs(os.path.dirname(clean_path), exist_ok=True)
            with open(clean_path, "w", encoding="utf-8") as f:
                f.write(target_content)
            return {"success": True, "path": clean_path, "message": f"File '{clean_path}' created successfully"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_execute_sandbox_code(self, code: str = "print('MCP Sandbox Active')", **kwargs):
        try:
            from core.sandbox import run_in_sandbox
            target_code = code or kwargs.get("query") or "print('MCP Sandbox Active')"
            res = run_in_sandbox(target_code)
            return {"success": True, "result": res}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_git_status(self, **kwargs):
        try:
            branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
            status = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
            return {"success": True, "branch": branch, "modified_files": status.splitlines()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _read_git_status(self, uri: str):
        return self._handle_git_status()

    def _read_workspace_structure(self, uri: str):
        try:
            from core.chat.prompt_builder import _build_filesystem_context
            return {"structure": _build_filesystem_context()}
        except Exception as exc:
            return {"error": str(exc)}
