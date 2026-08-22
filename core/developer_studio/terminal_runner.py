# ==============================================================================
# core/developer_studio/terminal_runner.py — Terminal & Shell Command Engine
# Sigma Studio v8 — Developer Studio Terminal Backend
# ==============================================================================
"""Provides asynchronous execution and real-time streaming of terminal commands
using native shell (PowerShell on Windows, Bash on POSIX) for the Developer Studio.
"""

import os
import sys
import time
import queue
import asyncio
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Generator

from core.logger import get_logger
from core.developer_studio.fs_manager import get_default_workspace_root

log = get_logger("developer_terminal")


def get_default_shell() -> list[str]:
    """Determines the default shell executable."""
    if sys.platform == "win32":
        # Check PowerShell Core or standard Windows PowerShell
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        return [shell, "-c"]


def execute_shell_command_sync(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: int = 120
) -> Dict[str, Any]:
    """Executes a command synchronously and returns stdout, stderr, and exit code."""
    if not cwd or not Path(cwd).exists():
        cwd = get_default_workspace_root()

    shell_cmd = get_default_shell() + [command]
    t_start = time.perf_counter()

    try:
        proc = subprocess.run(
            shell_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace"
        )
        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_ms": duration_ms,
            "cwd": cwd,
            "command": command
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Comando terminato per timeout ({timeout_seconds}s).",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "cwd": cwd,
            "command": command
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "cwd": cwd,
            "command": command
        }


def stream_shell_command(
    command: str,
    cwd: Optional[str] = None
) -> Generator[Dict[str, Any], None, None]:
    """Streams command output lines in real-time."""
    if not cwd or not Path(cwd).exists():
        cwd = get_default_workspace_root()

    shell_cmd = get_default_shell() + [command]
    t_start = time.perf_counter()

    try:
        proc = subprocess.Popen(
            shell_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        yield {
            "type": "start",
            "command": command,
            "cwd": cwd,
            "pid": proc.pid
        }

        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                if line:
                    yield {
                        "type": "output",
                        "text": line
                    }

        proc.stdout.close()
        returncode = proc.wait()
        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)

        yield {
            "type": "done",
            "returncode": returncode,
            "success": returncode == 0,
            "duration_ms": duration_ms
        }
    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "returncode": -1
        }
