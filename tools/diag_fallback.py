"""Diagnosi mirata del fallback TF-IDF di semantic_server.

Stampa: quanti documenti hanno 'auth' nel contenuto, cosa restituisce la query,
e se il fallback viene effettivamente eseguito.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PERCORSO = ROOT / "core" / "modules" / "sigma_developer_lab" / "mcp_tools" / "semantic_server.py"

spec = importlib.util.spec_from_file_location("sem_diag", PERCORSO)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
server = mod.SemanticMCPServer()

# 1. Quanti documenti contengono 'auth' nel contenuto?
docs = server._index["documents"]
con_auth = [d for d in docs if "auth" in d.get("content", "").lower()]
print(f"Documenti totali: {len(docs)}")
print(f"Documenti con 'auth' nel contenuto: {len(con_auth)}")
if con_auth:
    print(f"  Esempio: {con_auth[0]['path']} (line {con_auth[0].get('line_start')})")

# 2. Query con force_fallback
result = server.call_tool("semantic_search", {"query": "autenticazione utente", "force_fallback": True})
print(f"\nRisultato call_tool: isError={result.get('isError')}, error={result.get('error')}")
content = result.get("content") or []
texto = content[0].get("text", "") if content else ""
print(f"Testo risposta (prime 300): {texto[:300]}")

# 3. Prova diretta sul metodo _search_fallback se esiste
if hasattr(server, "_search_fallback"):
    try:
        fb = server._search_fallback("autenticazione utente", top_k=5)
        print(f"\n_search_fallback diretto: {len(fb)} risultati")
        for r in fb[:3]:
            print(f"  - {r.get('file')} score={r.get('score')}")
    except Exception as e:
        print(f"\n_search_fallback eccezione: {e}")
else:
    print("\nMetodo _search_fallback non trovato. Metodi disponibili:", [m for m in dir(server) if not m.startswith('__')])
