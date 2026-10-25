# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/health_server.py — Server Health MCP
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""MCP server per la verifica dello stato di salute del workspace.

Il tool `server_health` esegue una serie di controlli non invasivi (SAFE) sul
workspace: presenza e validità dei file di configurazione, stato del venv,
disponibilità dei tool di audit (pip-audit, npm), stato del server FastAPI
se in esecuzione, e un riepilogo delle dimensioni del progetto. Non modifica
nulla: solo legge e riporta.
"""

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE
from core.harness.fs_manager import get_default_workspace_root

log = get_logger(__name__)


def _check_file(path: Path) -> Dict[str, Any]:
    """Verifica esistenza e leggibilità di un file."""
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file() if path.exists() else False,
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
    }


def _check_python_env() -> Dict[str, Any]:
    """Raccoglie informazioni sull'ambiente Python corrente."""
    venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX")
    return {
        "version": platform.python_version(),
        "executable": sys.executable,
        "in_venv": bool(venv),
        "venv_path": venv,
        "platform": platform.platform(),
        "arch": platform.machine(),
    }


def _check_cli_tool(name: str) -> Dict[str, Any]:
    """Verifica se un tool CLI è disponibile nel PATH."""
    found = shutil.which(name)
    return {
        "name": name,
        "available": bool(found),
        "path": found,
    }


def _check_http_endpoint(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    """Verifica se un endpoint HTTP risponde (GET, senza body)."""
    import urllib.request
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {
                "url": url,
                "reachable": True,
                "status_code": resp.status,
            }
    except Exception as exc:
        return {
            "url": url,
            "reachable": False,
            "error": str(exc),
        }


#: Cartelle che non contengono sorgente del progetto e che pesano quanto tutto
#: il resto messo insieme. Senza potarle, `os.walk` dalla radice attraversa
#: centinaia di migliaia di voci: in questo repository `projects/*/target/` da
#: solo ne ha oltre trentamila dopo una compilazione release, e il conteggio
#: passava da istantaneo a minuti. Un tool di salute che ci mette minuti non
#: viene usato, e un agente che lo chiama ci perde il turno.
CARTELLE_DA_SALTARE = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env",
    "target", "dist", "build", "out",
    ".backups", ".sigma_backups", "unsloth_compiled_cache",
})


def _conta_per_gruppo(root: Path, gruppi: Dict[str, List[str]]) -> Dict[str, int]:
    """Conta i file di ogni gruppo di pattern con **una sola** passata.

    Prima si camminava l'albero una volta per gruppo — quattro passate
    complete — e senza saltare niente.
    """
    import fnmatch

    conteggi = {etichetta: 0 for etichetta in gruppi}
    try:
        for _dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in CARTELLE_DA_SALTARE]
            for fname in filenames:
                for etichetta, patterns in gruppi.items():
                    if any(fnmatch.fnmatch(fname, p) for p in patterns):
                        conteggi[etichetta] += 1
                        break
    except PermissionError:
        pass
    return conteggi


def _count_files(root: Path, patterns: List[str]) -> int:
    """Conta i file che corrispondono ai pattern sotto root."""
    return _conta_per_gruppo(root, {"_": list(patterns)})["_"]


class HealthMCPServer(BaseMCPServer):
    """MCP server per lo stato di salute del workspace e dell'ambiente."""

    def __init__(self):
        super().__init__(
            name="Developer Health",
            version="1.0.0",
            description=(
                "Verifica lo stato di salute del workspace: file di configurazione, "
                "ambiente Python, tool CLI disponibili, endpoint HTTP e dimensioni progetto."
            ),
        )
        self._register_tools()

    def is_configured(self) -> bool:
        return True

    def missing_dependency(self) -> Optional[str]:
        return None

    def _register_tools(self):
        self.register_tool(
            name="server_health",
            description=(
                "Report completo di salute del workspace: presenza file chiave, "
                "ambiente Python/venv, tool CLI (pip-audit, npm, node), endpoint HTTP "
                "del server Sigma se attivo, e conteggio file per tipo."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "check_http": {
                        "type": "boolean",
                        "description": "Verifica endpoint HTTP del server (default: true)",
                    },
                    "http_port": {
                        "type": "integer",
                        "description": "Porta del server Sigma da verificare (default: 8000)",
                    },
                },
            },
            handler=self._server_health,
            safety=SAFE,
            category="developer_health",
        )

    def _server_health(self, check_http: bool = True,
                       http_port: int = 8000) -> Dict[str, Any]:
        """Implementazione del tool server_health."""
        root = Path(get_default_workspace_root())
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "workspace_root": str(root),
            "python_env": _check_python_env(),
            "key_files": [],
            "cli_tools": [],
            "http_endpoints": [],
            "project_stats": {},
        }

        # --- File chiave del workspace ---
        key_files = [
            root / "requirements.txt",
            root / "package.json",
            root / "sigma_server.py",
            root / "AGENTS.md",
            root / "ARCHITECTURE.md",
            root / "config/settings.json",
            root / "core/__init__.py",
        ]
        report["key_files"] = [_check_file(p) for p in key_files]

        # --- Tool CLI rilevanti per lo sviluppo ---
        cli_tools = ["pip-audit", "npm", "node", "python", "git"]
        report["cli_tools"] = [_check_cli_tool(t) for t in cli_tools]

        # --- Endpoint HTTP del server Sigma ---
        if check_http:
            base_url = f"http://127.0.0.1:{http_port}"
            endpoints = [
                f"{base_url}/api/health",
                f"{base_url}/api/mcp/tools",
                f"{base_url}/",
            ]
            report["http_endpoints"] = [
                _check_http_endpoint(url) for url in endpoints
            ]

        # --- Statistiche progetto (conteggio file per tipo) ---
        stats_patterns = {
            "python": ["*.py"],
            "javascript": ["*.js", "*.jsx", "*.ts", "*.tsx"],
            "css": ["*.css"],
            "markdown": ["*.md"],
            "json": ["*.json"],
        }
        # Una passata sola sull'albero, non una per gruppo.
        report["project_stats"] = _conta_per_gruppo(root, stats_patterns)

        # --- Riepilogo rapido ---
        missing_key = [f["path"] for f in report["key_files"] if not f["exists"]]
        unavailable_cli = [t["name"] for t in report["cli_tools"] if not t["available"]]
        report["summary"] = {
            "missing_key_files": missing_key,
            "unavailable_cli_tools": unavailable_cli,
            "overall_status": "ok" if not missing_key else "degraded",
        }

        return report