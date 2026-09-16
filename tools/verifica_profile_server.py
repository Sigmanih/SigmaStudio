#!/usr/bin/env python3
"""Verifica che ProfileMCPServer si registri ed esponga il tool profile_app.

Importa il modulo direttamente per file (importlib.util) per evitare di
innescare __init__.py del package sigma_developer_lab, che importa fastapi
(non installato in questo ambiente di verifica).
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, '.')
from core.mcp.base_server import BaseMCPServer

# Carica profile_server.py come modulo isolato, senza passare da __init__.py
_spec = importlib.util.spec_from_file_location(
    "profile_server",
    Path("core/modules/sigma_developer_lab/mcp_tools/profile_server.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["profile_server"] = _mod
_spec.loader.exec_module(_mod)
ProfileMCPServer = _mod.ProfileMCPServer

server = ProfileMCPServer()
tools = server.list_tools()
names = [t["name"] for t in tools]
print(f"Server: {server.name} v{server.version}")
print(f"Tools registrati: {names}")
assert "profile_app" in names, f"Tool 'profile_app' non trovato in {names}"

# Verifica che la schema sia coerente
schema = next(t["inputSchema"] for t in tools if t["name"] == "profile_app")
props = schema.get("properties", {})
assert "target_type" in props, "Manca 'target_type' nello schema"
assert "target" in props, "Manca 'target' nello schema"

# Call di prova: funzione non esistente -> deve restituire isError=False ma success=False nel payload
res = server.call_tool("profile_app", {"target_type": "function", "target": "non.esiste.funzione"})
assert res["isError"] is False, f"isError inatteso: {res}"
payload = res["content"][0]["text"]
print(f"Risultato call_tool (funzione inesistente): {payload[:120]}...")

print('SIGMA-CHECK {"check": "profile_server", "checked": 1, "problems": 0}')
