#!/usr/bin/env python3
"""Verifica che HealthMCPServer sia importabile e registri i suoi tool.

Stessa strategia di verifica_deps_server.py: carico il modulo direttamente
dal file con un sys.modules finto per il package, evitando l'import di
fastapi che farebbe esplodere l'__init__.py del modulo.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for pkg in [
    "core.modules.sigma_developer_lab",
    "core.modules.sigma_developer_lab.mcp_tools",
]:
    if pkg not in sys.modules:
        m = type(sys)(pkg)
        m.__path__ = [str(ROOT / pkg.replace(".", "/"))]
        sys.modules[pkg] = m

spec = importlib.util.spec_from_file_location(
    "core.modules.sigma_developer_lab.mcp_tools.health_server",
    ROOT / "core/modules/sigma_developer_lab/mcp_tools/health_server.py",
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

server = mod.HealthMCPServer()
tools = server.list_tools()
names = [t["name"] for t in tools]
print(f"Server: {server.name} v{server.version}")
print(f"Tools registrati: {names}")
assert "server_health" in names, "server_health non registrato"

result = server.call_tool("server_health", {})
print("Risultato call_tool (chiavi):", list(result.keys()))
print('SIGMA-CHECK {"check": "health_server", "checked": 1, "problems": 0}')