# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/docker_server.py — Docker MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP Server per la gestione e l'esecuzione di comandi in container Docker.

Consente agli agenti di sviluppo di creare ambienti isolati, avviare container
(es. compilatori Rust, ambienti Linux), eseguire comandi all'interno del container
tramite `docker exec`, monitorarne lo stato e gestire i volumi montati.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.harness.esecutori import docker_disponibile, trova_docker, _ambiente_per_docker
from core.harness.fs_manager import get_default_workspace_root

log = get_logger(__name__)


def _run_docker_cli(args: List[str], timeout: int = 60) -> Dict[str, Any]:
    """Esegue un comando Docker CLI con timeout e cattura output."""
    disponibile, motivo = docker_disponibile()
    if not disponibile:
        return {
            "success": False,
            "error": f"Docker non disponibile: {motivo}. Assicurati che Docker Desktop sia avviato.",
            "docker_available": False,
        }

    docker_bin = trova_docker()
    env = _ambiente_per_docker()
    cmd = [docker_bin] + args

    try:
        t0 = time.perf_counter()
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "returncode": res.returncode,
            "elapsed_ms": elapsed_ms,
            "docker_available": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Comando Docker scaduto dopo {timeout} secondi.",
            "docker_available": True,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Errore esecuzione Docker: {exc}",
            "docker_available": True,
        }


class DockerMCPServer(BaseMCPServer):
    """Server MCP per orchestrazione ed esecuzione comandi in Docker."""

    def __init__(self):
        super().__init__(
            name="docker_server",
            version="1.0.0",
            description="Gestione container Docker, esecuzione comandi isolati (cargo, build, test) e status monitoring.",
        )
        for t in self.get_tools():
            self.register_tool(
                name=t["name"],
                description=t["description"],
                input_schema=t["inputSchema"],
                handler=lambda args, tool_name=t["name"]: self.call_tool(tool_name, args),
                safety=t.get("safety", SAFE),
            )

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "docker_list_containers",
                "description": "Elenca tutti i container Docker attivi e disponibili con ID, immagine e stato.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "all": {"type": "boolean", "description": "Includi anche i container fermati (default: true).", "default": True},
                    },
                },
            },
            {
                "name": "docker_run_container",
                "description": "Crea e avvia un nuovo container Docker (es. rust:1.80-slim per compilazione/sviluppo) in background con volumi montati.",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image": {"type": "string", "description": "Immagine Docker da avviare (es. 'rust:1.80-slim', 'ubuntu:latest')."},
                        "name": {"type": "string", "description": "Nome univoco da assegnare al container (es. 'sigma_rust_dev')."},
                        "host_dir": {"type": "string", "description": "Percorso directory host da montare nel container (default: workspace root)."},
                        "container_dir": {"type": "string", "description": "Percorso all'interno del container dove montare (default: '/workspace').", "default": "/workspace"},
                        "command": {"type": "string", "description": "Comando di avvio iniziale (default: 'sleep infinity' per mantenerlo attivo).", "default": "sleep infinity"},
                    },
                    "required": ["image", "name"],
                },
            },
            {
                "name": "docker_exec",
                "description": "Esegue un comando all'interno di un container Docker attivo (es. 'cargo build --release', 'cargo test', 'rustc --version').",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "container": {"type": "string", "description": "Nome o ID del container in cui eseguire il comando."},
                        "command": {"type": "string", "description": "Comando shell da eseguire nel container (es. 'cargo test')."},
                        "workdir": {"type": "string", "description": "Directory di lavoro nel container (default: '/workspace').", "default": "/workspace"},
                        "timeout": {"type": "integer", "description": "Timeout in secondi (default: 120).", "default": 120},
                    },
                    "required": ["container", "command"],
                },
            },
            {
                "name": "docker_container_status",
                "description": "Restituisce lo stato, consumo risorse o log di un container Docker.",
                "safety": SAFE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "container": {"type": "string", "description": "Nome o ID del container."},
                        "tail_logs": {"type": "integer", "description": "Numero di righe di log recenti da includere (default: 30).", "default": 30},
                    },
                    "required": ["container"],
                },
            },
            {
                "name": "docker_stop_container",
                "description": "Ferma ed eventualmente rimuove un container Docker.",
                "safety": SENSITIVE,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "container": {"type": "string", "description": "Nome o ID del container da fermare."},
                        "remove": {"type": "boolean", "description": "Se true, rimuove il container dopo averlo fermato (default: true).", "default": True},
                    },
                    "required": ["container"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "docker_list_containers":
            return self._tool_list_containers(arguments)
        elif name == "docker_run_container":
            return self._tool_run_container(arguments)
        elif name == "docker_exec":
            return self._tool_exec(arguments)
        elif name == "docker_container_status":
            return self._tool_status(arguments)
        elif name == "docker_stop_container":
            return self._tool_stop(arguments)
        return {"success": False, "error": f"Tool sconosciuto: {name}"}

    def _tool_list_containers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        all_flag = ["-a"] if args.get("all", True) else []
        cmd = ["ps"] + all_flag + ["--format", "{{json .}}"]
        res = _run_docker_cli(cmd, timeout=15)
        if not res["success"]:
            return res

        containers = []
        for line in res.get("stdout", "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except Exception:
                pass

        return {
            "success": True,
            "containers_count": len(containers),
            "containers": containers,
            "message": f"Trovati {len(containers)} container.",
        }

    def _tool_run_container(self, args: Dict[str, Any]) -> Dict[str, Any]:
        image = str(args.get("image", "")).strip()
        name = str(args.get("name", "")).strip()
        host_dir = str(args.get("host_dir", "")).strip() or get_default_workspace_root()
        container_dir = str(args.get("container_dir", "/workspace")).strip()
        initial_cmd = str(args.get("command", "sleep infinity")).strip()

        if not image or not name:
            return {"success": False, "error": "Parametri 'image' e 'name' obbligatori."}

        # Converte host_dir in path assoluto e risolve barre per Docker
        host_path = Path(host_dir).resolve()
        host_path.mkdir(parents=True, exist_ok=True)
        mount_arg = f"{str(host_path)}:{container_dir}"

        cmd = [
            "run", "-d",
            "--name", name,
            "-v", mount_arg,
            "-w", container_dir,
            image,
        ] + initial_cmd.split()

        res = _run_docker_cli(cmd, timeout=120)
        if res["success"]:
            cid = res.get("stdout", "")[:12]
            return {
                "success": True,
                "container_id": cid,
                "name": name,
                "image": image,
                "mount": mount_arg,
                "message": f"Container '{name}' ({cid}) avviato con successo con volume {mount_arg}.",
            }
        return res

    def _tool_exec(self, args: Dict[str, Any]) -> Dict[str, Any]:
        container = str(args.get("container", "")).strip()
        command = str(args.get("command", "")).strip()
        workdir = str(args.get("workdir", "")).strip()
        timeout = int(args.get("timeout", 120))

        if not container or not command:
            return {"success": False, "error": "Parametri 'container' e 'command' obbligatori."}

        cmd = ["exec"]
        if workdir:
            cmd.extend(["-w", workdir])
        cmd.extend([container, "sh", "-c", command])
        res = _run_docker_cli(cmd, timeout=timeout)
        res["container"] = container
        res["command"] = command
        return res

    def _tool_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        container = str(args.get("container", "")).strip()
        tail = int(args.get("tail_logs", 30))
        if not container:
            return {"success": False, "error": "Parametro 'container' obbligatorio."}

        inspect_res = _run_docker_cli(["inspect", container], timeout=10)
        logs_res = _run_docker_cli(["logs", "--tail", str(tail), container], timeout=10)

        details = {}
        if inspect_res["success"] and inspect_res.get("stdout"):
            try:
                parsed = json.loads(inspect_res["stdout"])
                if parsed and isinstance(parsed, list):
                    cdata = parsed[0]
                    state = cdata.get("State", {})
                    details = {
                        "status": state.get("Status", "unknown"),
                        "running": state.get("Running", False),
                        "started_at": state.get("StartedAt", ""),
                        "exit_code": state.get("ExitCode", 0),
                    }
            except Exception:
                pass

        return {
            "success": inspect_res["success"],
            "container": container,
            "details": details,
            "logs": logs_res.get("stdout", "") or logs_res.get("stderr", ""),
        }

    def _tool_stop(self, args: Dict[str, Any]) -> Dict[str, Any]:
        container = str(args.get("container", "")).strip()
        remove = bool(args.get("remove", True))
        if not container:
            return {"success": False, "error": "Parametro 'container' obbligatorio."}

        stop_res = _run_docker_cli(["stop", container], timeout=30)
        if remove and stop_res["success"]:
            rm_res = _run_docker_cli(["rm", "-f", container], timeout=15)
            return {
                "success": True,
                "container": container,
                "message": f"Container '{container}' fermato e rimosso.",
            }
        return stop_res
