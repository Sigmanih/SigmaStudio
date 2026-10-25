# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/cargo_server.py — Rust Toolchain MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP Server per la toolchain Rust (cargo build, cargo test, cargo clippy, cargo check).

Offre esecuzione assistita con fallback intelligente:
- Se Rust/Cargo è presente sull'host, esegue localmente.
- Se l'host è privo di toolchain Rust, delega trasparentemente l'esecuzione al
  container Docker configurato (es. `sigma_rust_dev`).
- Parsa l'output strutturato di `cargo test` per verificare il superamento dei test.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SENSITIVE, SAFE
from core.harness.fs_manager import get_default_workspace_root

log = get_logger(__name__)


def _has_host_cargo() -> bool:
    """Verifica se cargo è disponibile nel PATH dell'host."""
    return shutil.which("cargo") is not None


def _run_cargo(
    args: List[str],
    project_dir: str,
    container_name: Optional[str] = None,
    timeout: int = 180,
) -> Dict[str, Any]:
    """Esegue un comando cargo su host o all'interno del container Docker."""
    from core.harness.workspace import resolve_root
    abs_dir = resolve_root(project_dir)

    # 1. Se cargo è su host e non è richiesto forzatamente un container
    if _has_host_cargo() and not container_name:
        try:
            t0 = time.perf_counter()
            cmd = ["cargo"] + args
            res = subprocess.run(
                cmd,
                cwd=abs_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "returncode": res.returncode,
                "environment": "host",
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:
            return {"success": False, "error": f"Errore cargo host: {exc}", "environment": "host"}

    # 2. Fallback su container Docker
    target_container = container_name or "sigma_rust_dev"
    try:
        from core.modules.sigma_developer_lab.mcp_tools.docker_server import _run_docker_cli
        cmd_str = "cargo " + " ".join(args)
        t0 = time.perf_counter()
        docker_res = _run_docker_cli(
            ["exec", target_container, "sh", "-c", cmd_str],
            timeout=timeout,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        # Se il container predefinito non esiste o non e' avviato, esegui on-demand con rust:1.85-slim
        if not docker_res.get("success") and any(s in docker_res.get("stderr", "") for s in ("No such container", "is not running", "not running")):
            p_abs = Path(abs_dir).resolve()
            montaggio = f"{p_abs}:/usr/src/app"
            docker_res = _run_docker_cli(
                ["run", "--rm", "-v", montaggio, "-w", "/usr/src/app", "rust:slim", "cargo"] + args,
                timeout=timeout,
            )
            target_container = "rust:slim"

        return {
            "success": docker_res.get("success", False),
            "stdout": docker_res.get("stdout", ""),
            "stderr": docker_res.get("stderr", ""),
            "returncode": docker_res.get("returncode", -1),
            "environment": f"docker:{target_container}",
            "elapsed_ms": elapsed_ms,
            "error": docker_res.get("error"),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Toolchain cargo non presente su host e container '{target_container}' non raggiungibile: {exc}",
            "environment": "unavailable",
        }


def _parse_cargo_test_output(stdout: str, stderr: str) -> Dict[str, Any]:
    """Estrae il resoconto dei test da output cargo (passed, failed, ignored)."""
    full_text = f"{stdout}\n{stderr}"
    # Match tipico: test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
    match = re.search(r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored", full_text)
    if match:
        status = match.group(1)
        passed = int(match.group(2))
        failed = int(match.group(3))
        ignored = int(match.group(4))
        return {
            "test_status": status,
            "passed": passed,
            "failed": failed,
            "ignored": ignored,
            "all_passed": failed == 0 and status == "ok",
        }
    return {
        "test_status": "unknown",
        "passed": 0,
        "failed": 0,
        "ignored": 0,
        "all_passed": "test result: ok" in full_text,
    }


class RustCargoMCPServer(BaseMCPServer):
    """Server MCP per la toolchain Rust (build, test, check, clippy)."""

    def __init__(self):
        super().__init__(
            name="cargo_server",
            version="1.0.0",
            description="Compilazione e collaudo progetti Rust (cargo build, test, check, clippy) su host o container Docker.",
        )
        for t in self.get_tools():
            self.register_tool(
                name=t["name"],
                description=t["description"],
                input_schema=t["inputSchema"],
                handler=lambda args, tool_name=t["name"]: self.call_tool(tool_name, args),
                safety=t.get("safety", SENSITIVE),
            )

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "cargo_build",
                "description": "Compila il progetto Rust (cargo build). Esegue su host o delega trasparentemente al container Docker se l'host è privo di Rust.",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string", "description": "Directory del progetto contenente Cargo.toml (default: workspace root)."},
                        "release": {"type": "boolean", "description": "Compilazione ottimizzata in modalità --release (default: false).", "default": False},
                        "container": {"type": "string", "description": "Nome container Docker opzionale (default: 'sigma_rust_dev')."},
                    },
                },
            },
            {
                "name": "cargo_test",
                "description": "Esegue i test del progetto Rust (cargo test) e restituisce un report strutturato con test passati e falliti.",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string", "description": "Directory del progetto (default: workspace root)."},
                        "test_name": {"type": "string", "description": "Filtro opzionale per eseguire solo un test specifico."},
                        "container": {"type": "string", "description": "Nome container Docker opzionale (default: 'sigma_rust_dev')."},
                    },
                },
            },
            {
                "name": "cargo_check",
                "description": "Verifica rapidamente la correttezza del codice senza produrre binari (cargo check). Molto più veloce di build.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string", "description": "Directory del progetto."},
                        "container": {"type": "string", "description": "Nome container Docker opzionale."},
                    },
                },
            },
            {
                "name": "cargo_clippy",
                "description": "Esegue linter e analisi statica avanzata per codice Rust idiomatico e performante (cargo clippy).",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_dir": {"type": "string", "description": "Directory del progetto."},
                        "container": {"type": "string", "description": "Nome container Docker opzionale."},
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "cargo_build":
            return self._tool_build(arguments)
        elif name == "cargo_test":
            return self._tool_test(arguments)
        elif name == "cargo_check":
            return self._tool_check(arguments)
        elif name == "cargo_clippy":
            return self._tool_clippy(arguments)
        return {"success": False, "error": f"Tool sconosciuto: {name}"}

    def _tool_build(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pdir = str(args.get("project_dir", "")).strip() or get_default_workspace_root()
        release = bool(args.get("release", False))
        container = args.get("container")

        cargo_args = ["build"]
        if release:
            cargo_args.append("--release")

        res = _run_cargo(cargo_args, project_dir=pdir, container_name=container, timeout=240)
        res["tool"] = "cargo_build"
        res["release"] = release
        return res

    def _tool_test(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pdir = str(args.get("project_dir", "")).strip() or get_default_workspace_root()
        tname = str(args.get("test_name", "")).strip()
        container = args.get("container")

        cargo_args = ["test"]
        if tname:
            cargo_args.append(tname)
        cargo_args.extend(["--", "--nocapture"])

        res = _run_cargo(cargo_args, project_dir=pdir, container_name=container, timeout=180)
        parsed = _parse_cargo_test_output(res.get("stdout", ""), res.get("stderr", ""))
        res["tool"] = "cargo_test"
        res["test_summary"] = parsed
        return res

    def _tool_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pdir = str(args.get("project_dir", "")).strip() or get_default_workspace_root()
        container = args.get("container")

        res = _run_cargo(["check"], project_dir=pdir, container_name=container, timeout=120)
        res["tool"] = "cargo_check"
        return res

    def _tool_clippy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pdir = str(args.get("project_dir", "")).strip() or get_default_workspace_root()
        container = args.get("container")

        res = _run_cargo(["clippy", "--", "-D", "warnings"], project_dir=pdir, container_name=container, timeout=120)
        res["tool"] = "cargo_clippy"
        return res
