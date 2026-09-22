"""Verifica fattuale dell'hub MCP e dello stato del server easyeda_pro.

Esegue un controllo deterministico: importa l'istanza singleton dell'hub,
elenca i server esterni dichiarati e ne riporta lo stato di configurazione.
Chiude con la riga SIGMA-CHECK richiesta dalle convenzioni del progetto.
"""
import json
import sys
from pathlib import Path

# Garantisce che la radice del workspace sia sul path di importazione.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.mcp.mcp_hub import mcp_hub  # istanza singleton

checked = 0
problems = 0

try:
    servers = list(mcp_hub.external.keys())
except Exception as exc:  # pragma: no cover - difensivo
    print(f"ERRORE: impossibile leggere i server esterni: {exc}")
    print('SIGMA-CHECK ' + json.dumps({"check": "mcp_hub", "checked": 0, "problems": 1}))
    sys.exit(1)

print("external servers:", servers)
for name in servers:
    checked += 1
    try:
        server = mcp_hub.external[name]
        configured = bool(server.is_configured())
    except Exception as exc:  # pragma: no cover - difensivo
        problems += 1
        print(f"{name} -> ERRORE: {exc}")
        continue
    print(f"{name} -> configured={configured}")

# Problema solo se il server easyeda_pro e' assente: in quel caso l'integrazione
# non e' nemmeno dichiarata. Se presente ma non configurato, e' uno stato atteso
# (da avviare), non un difetto del codice.
if "easyeda_pro" not in servers:
    problems += 1

print('SIGMA-CHECK ' + json.dumps({"check": "mcp_hub", "checked": checked, "problems": problems}))
sys.exit(0 if problems == 0 else 1)