# ==============================================================================
# core/developer_studio/terminal_runner.py — Terminal & Shell Command Engine
# Sigma Studio v8 — Developer Studio Terminal Backend with Background Support
# ==============================================================================
"""Provides asynchronous execution, real-time streaming, and background process
lifecycle management using native shells (PowerShell on Windows, Bash on POSIX).
"""

import os
import sys
import time
import queue
import signal
import subprocess
import threading
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional, Generator

from core.logger import get_logger
from core.developer_studio.fs_manager import get_default_workspace_root

log = get_logger("developer_terminal")

_lock = threading.RLock()
_BG_PROCESSES: Dict[str, Dict[str, Any]] = {}


def get_default_shell() -> list[str]:
    """Determines the default shell executable."""
    if sys.platform == "win32":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]
    else:
        shell = os.environ.get("SHELL", "/bin/bash")
        return [shell, "-c"]


def execute_shell_command_sync(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: int = 300,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """Executes a command synchronously with cancel polling support."""
    if not cwd or not Path(cwd).exists():
        cwd = get_default_workspace_root()

    shell_cmd = get_default_shell() + [command]
    t_start = time.perf_counter()

    try:
        proc = subprocess.Popen(
            shell_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []

        def _reader(pipe, dest_list):
            try:
                for line in iter(pipe.readline, ""):
                    dest_list.append(line)
                pipe.close()
            except Exception:
                pass

        t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_chunks), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_chunks), daemon=True)
        t_out.start()
        t_err.start()

        poll_interval = 0.1
        elapsed = 0.0

        while proc.poll() is None:
            if should_cancel and should_cancel():
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    else:
                        proc.terminate()
                except Exception:
                    pass
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "".join(stdout_chunks),
                    "stderr": "Comando interrotto dall'utente.",
                    "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
                    "cwd": cwd,
                    "command": command,
                    "cancelled": True,
                }

            if elapsed >= timeout_seconds:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    else:
                        proc.terminate()
                except Exception:
                    pass
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "".join(stdout_chunks),
                    "stderr": f"Comando terminato per timeout ({timeout_seconds}s).",
                    "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
                    "cwd": cwd,
                    "command": command,
                }

            time.sleep(poll_interval)
            elapsed = time.perf_counter() - t_start

        t_out.join(timeout=2.0)
        t_err.join(timeout=2.0)

        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)

        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "duration_ms": duration_ms,
            "cwd": cwd,
            "command": command,
        }

    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "cwd": cwd,
            "command": command,
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
            bufsize=1,
        )

        yield {
            "type": "start",
            "command": command,
            "cwd": cwd,
            "pid": proc.pid,
        }

        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                if line:
                    yield {
                        "type": "output",
                        "text": line,
                    }

        proc.stdout.close()
        returncode = proc.wait()
        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)

        yield {
            "type": "done",
            "returncode": returncode,
            "success": returncode == 0,
            "duration_ms": duration_ms,
        }
    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "returncode": -1,
        }


def start_background_process(
    command: str,
    cwd: Optional[str] = None,
    process_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Starts a long-running background process (e.g. dev server, watcher)."""
    if not cwd or not Path(cwd).exists():
        cwd = get_default_workspace_root()

    pid_key = process_id or f"proc_{int(time.time()*1000)}"
    shell_cmd = get_default_shell() + [command]

    try:
        proc = subprocess.Popen(
            shell_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        log_buffer: List[str] = []

        def _collector():
            try:
                for line in iter(proc.stdout.readline, ""):
                    with _lock:
                        log_buffer.append(line)
                        if len(log_buffer) > 500:
                            log_buffer.pop(0)
                proc.stdout.close()
            except Exception:
                pass

        reader_t = threading.Thread(target=_collector, daemon=True)
        reader_t.start()

        with _lock:
            _BG_PROCESSES[pid_key] = {
                "id": pid_key,
                "command": command,
                "cwd": cwd,
                "pid": proc.pid,
                "proc": proc,
                "started_at": time.time(),
                "logs": log_buffer,
            }

        time.sleep(0.3)
        return {
            "success": True,
            "process_id": pid_key,
            "pid": proc.pid,
            "command": command,
            "cwd": cwd,
            "status": "running" if proc.poll() is None else "exited",
        }
    except Exception as ex:
        log.error("Failed to start background process '%s': %s", command, ex)
        return {
            "success": False,
            "error": str(ex),
            "command": command,
        }


def get_background_process_status(process_id: str) -> Dict[str, Any]:
    """Gets status and recent logs for a background process."""
    with _lock:
        info = _BG_PROCESSES.get(process_id)
        if not info:
            return {"success": False, "error": f"Processo '{process_id}' non trovato."}

        proc: subprocess.Popen = info["proc"]
        is_running = proc.poll() is None
        return {
            "success": True,
            "process_id": process_id,
            "pid": info["pid"],
            "command": info["command"],
            "running": is_running,
            "returncode": proc.returncode if not is_running else None,
            "uptime_seconds": round(time.time() - info["started_at"], 1),
            "recent_logs": "".join(info["logs"][-30:]),
        }


def kill_background_process(process_id: str) -> Dict[str, Any]:
    """Kills a running background process."""
    with _lock:
        info = _BG_PROCESSES.get(process_id)
        if not info:
            return {"success": False, "error": f"Processo '{process_id}' non trovato."}

        proc: subprocess.Popen = info["proc"]
        try:
            if proc.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.terminate()
            return {"success": True, "process_id": process_id, "message": "Processo terminato con successo."}
        except Exception as ex:
            return {"success": False, "process_id": process_id, "error": str(ex)}


def list_background_processes() -> List[Dict[str, Any]]:
    """Returns a list of all background processes."""
    with _lock:
        result = []
        for pid_key, info in list(_BG_PROCESSES.items()):
            proc: subprocess.Popen = info["proc"]
            result.append({
                "process_id": pid_key,
                "pid": info["pid"],
                "command": info["command"],
                "running": proc.poll() is None,
                "uptime_seconds": round(time.time() - info["started_at"], 1),
            })
        return result
