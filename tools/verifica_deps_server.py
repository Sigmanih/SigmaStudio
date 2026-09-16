#!/usr/bin/env python3
"""Verifica che DepsMCPServer sia importabile e registri i suoi tool.

Evita l'import di core.modules.sigma_developer_lab (che richiede fastapi)
caricando il modulo deps_server direttamente dal file, con un sys.modules
finto per il package.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Crea i package fittizi per evitare di importare __init__.py del modulo
for pkg in [
    "core.modules.sigma_developer_lab",
    "core.modules.sigma_developer_lab.mcp_tools",
]:
    if pkg not in sys.modules:
        m = type(sys)(pkg)
        m.__path__ = [str(ROOT / pkg.replace(".", "/"))]
        sys.modules[pkg] = m

spec = importlib.util.spec_from_file_location(
    "core.modules.sigma_developer_lab.mcp_tools.deps_server",
    ROOT / "core/modules/sigma_developer_lab/mcp_tools/deps_server.py",
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

server = mod.DepsMCPServer()
tools = server.list_tools()
names = [t["name"] for t in tools]
print(f"Server: {server.name} v{server.version}")
print(f"Tools registrati: {names}")
assert "deps_audit" in names, "deps_audit non registrato"

# Esegui il tool per verificare che non esploda
result = server.call_tool("deps_audit", {"check_vulnerabilities": False})
print("Risultato call_tool:", result)

print('SIGMA-CHECK {"check": "deps_server", "checked": 1, "problems": 0}')
