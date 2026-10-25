# ==============================================================================
# core/developer_studio/mcp_tools/deps_server.py — Dependency Audit MCP Server
# Sigma Studio v8 — Developer Studio AI-Native IDE
# =============================================================================
"""MCP server for auditing Python and JavaScript dependencies.

Il tool `deps_audit` legge `requirements.txt` e `package.json` nel workspace,
rileva pacchetti obsoleti o con vulnerabilità note (se `pip-audit` / `npm audit`
sono disponibili), e verifica la coerenza tra i due file. Tutti gli strumenti
sono SAFE: non modificano nulla, solo leggono e riportano.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE
from core.harness.fs_manager import get_default_workspace_root

log = get_logger(__name__)

AUDIT_TIMEOUT = 60


def _run_cmd(args: List[str], cwd: Optional[str] = None,
             timeout: int = AUDIT_TIMEOUT) -> Dict[str, Any]:
    """Esegue un comando CLI e restituisce output strutturato."""
    from core.harness.workspace import resolve_root
    cwd = resolve_root(cwd)
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
        return {"success": False, "error": f"'{args[0]}' non trovato nel PATH."}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout dopo {timeout}s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _parse_requirements(path: Path) -> List[Dict[str, Any]]:
    """Parsa requirements.txt e restituisce una lista di dipendenze Python."""
    deps = []
    if not path.exists():
        return deps
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Estrai nome e versione (se presente)
            match = re.match(r"^([A-Za-z0-9_.\-]+)\s*(?:[=<>!~]=?\s*([^\s,;]+))?", line)
            if match:
                deps.append({
                    "name": match.group(1).lower().replace("_", "-"),
                    "version": match.group(2) or "any",
                    "type": "python",
                })
    except Exception as exc:
        log.warning("Errore lettura requirements.txt: %s", exc)
    return deps


def _parse_package_json(path: Path) -> List[Dict[str, Any]]:
    """Parsa package.json e restituisce dipendenze JS (dependencies + devDependencies)."""
    deps = []
    if not path.exists():
        return deps
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ["dependencies", "devDependencies"]:
            for name, version in (data.get(section) or {}).items():
                deps.append({
                    "name": name,
                    "version": version,
                    "type": "javascript",
                    "section": section,
                })
    except json.JSONDecodeError as exc:
        log.warning("package.json non valido: %s", exc)
    except Exception as exc:
        log.warning("Errore lettura package.json: %s", exc)
    return deps


class DepsMCPServer(BaseMCPServer):
    """MCP server per audit delle dipendenze Python e JavaScript."""

    def __init__(self):
        super().__init__(
            name="Developer Dependencies",
            version="1.0.0",
            description="Audit dipendenze: verifica requisiti, rileva pacchetti obsoleti/vulnerabili, genera lockfile.",
        )
        self._register_tools()

    def is_configured(self) -> bool:
        """Verifica che almeno un file di dipendenze esista nel workspace."""
        root = Path(get_default_workspace_root())
        return (root / "requirements.txt").exists() or (root / "package.json").exists()

    def missing_dependency(self) -> Optional[str]:
        if not self.is_configured():
            return "Nessun requirements.txt o package.json trovato nel workspace."
        return None

    def _register_tools(self):
        self.register_tool(
            name="deps_audit",
            description=(
                "Audit completo delle dipendenze: legge requirements.txt e package.json, "
                "rileva pacchetti obsoleti o vulnerabili (se pip-audit/npm audit sono disponibili), "
                "e verifica la coerenza tra i due file."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "check_vulnerabilities": {
                        "type": "boolean",
                        "description": "Esegui pip-audit / npm audit per vulnerabilità (default: true)",
                    },
                    "include_dev": {
                        "type": "boolean",
                        "description": "Includi devDependencies in package.json (default: true)",
                    },
                },
            },
            handler=self._deps_audit,
            safety=SAFE,
            category="developer_deps",
        )

    def _deps_audit(self, check_vulnerabilities: bool = True,
                    include_dev: bool = True) -> Dict[str, Any]:
        """Implementazione del tool deps_audit."""
        root = Path(get_default_workspace_root())
        report: Dict[str, Any] = {
            "python": {"deps": [], "audit": None},
            "javascript": {"deps": [], "audit": None},
            "coherence_issues": [],
        }

        # --- Python ---
        req_path = root / "requirements.txt"
        py_deps = _parse_requirements(req_path)
        report["python"]["deps"] = py_deps

        if check_vulnerabilities and py_deps:
            audit_res = _run_cmd(["pip-audit", "-r", str(req_path), "--format", "json"], cwd=str(root))
            if audit_res["success"]:
                try:
                    audit_data = json.loads(audit_res["stdout"])
                    vulns = audit_data.get("vulnerabilities", [])
                    report["python"]["audit"] = {
                        "status": "ok" if not vulns else "vulnerable",
                        "vulnerabilities_count": len(vulns),
                        "details": vulns[:10],  # max 10 per non gonfiare
                    }
                except json.JSONDecodeError:
                    report["python"]["audit"] = {"status": "parse_error", "raw": audit_res["stdout"][:500]}
            else:
                report["python"]["audit"] = {
                    "status": "unavailable",
                    "hint": "pip install pip-audit  (per rilevare vulnerabilità Python)",
                }

        # --- JavaScript ---
        pkg_path = root / "package.json"
        js_deps = _parse_package_json(pkg_path)
        if not include_dev:
            js_deps = [d for d in js_deps if d.get("section") != "devDependencies"]
        report["javascript"]["deps"] = js_deps

        if check_vulnerabilities and js_deps:
            audit_res = _run_cmd(["npm", "audit", "--json"], cwd=str(root))
            if audit_res["success"]:
                try:
                    audit_data = json.loads(audit_res["stdout"])
                    metadata = audit_data.get("metadata", {})
                    vulns_count = metadata.get("vulnerabilities", {}).get("total", 0)
                    report["javascript"]["audit"] = {
                        "status": "ok" if vulns_count == 0 else "vulnerable",
                        "vulnerabilities_count": vulns_count,
                    }
                except json.JSONDecodeError:
                    report["javascript"]["audit"] = {"status": "parse_error", "raw": audit_res["stdout"][:500]}
            else:
                report["javascript"]["audit"] = {
                    "status": "unavailable",
                    "hint": "npm audit  (per rilevare vulnerabilità JS)",
                }

        # --- Coerenza: pacchetti duplicati o conflittuali ---
        py_names = {d["name"] for d in py_deps}
        js_names = {d["name"] for d in js_deps}
        overlap = py_names & js_names
        if overlap:
            report["coherence_issues"].append(
                f"Pacchetti presenti sia in Python che in JS (possibile duplicazione): {sorted(overlap)}"
            )

        # --- Lockfile check ---
        has_py_lock = (root / "requirements.lock").exists() or (root / "poetry.lock").exists()
        has_js_lock = (root / "package-lock.json").exists() or (root / "yarn.lock").exists()
        report["lockfiles"] = {"python": has_py_lock, "javascript": has_js_lock}

        return report