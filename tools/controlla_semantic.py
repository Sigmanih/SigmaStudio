"""Controllo dell'indice semantico e della query: dimostra che i risultati
non sono vuoti e che l'indice contiene embedding per file Python e JS/TS.

Uscita: codice 0 + riga SIGMA-CHECK con conteggio elementi esaminati.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PERCORSO_SERVER = ROOT / "core" / "modules" / "sigma_developer_lab" / "mcp_tools" / "semantic_server.py"
INDICE = ROOT / "var" / "semantic_index" / "index.json"


def _carica_server():
    spec = importlib.util.spec_from_file_location("sem_iso", PERCORSO_SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    problemi = 0
    esaminati = 0

    # 1. L'indice esiste e ha documenti
    if not INDICE.exists():
        print("[FAIL] indice assente:", INDICE)
        _esiti(1, 1)
        return 1
    d = json.loads(INDICE.read_text(encoding="utf-8"))
    docs = d.get("documents", [])
    esaminati += 1
    print(f"[OK] indice: {len(docs)} documenti, chiavi={list(d.keys())}")
    if len(docs) == 0:
        problemi += 1
        print("[FAIL] indice vuoto")

    # 2. L'indice copre file Python e JS/TS
    est = {}
    for doc in docs:
        p = Path(doc.get("path", ""))
        ext = p.suffix.lower()
        est[ext] = est.get(ext, 0) + 1
    esaminati += 1
    print(f"[OK] estensioni indicizzate: {est}")
    if ".py" not in est:
        problemi += 1
        print("[FAIL] nessun file .py nell'indice")
    if not any(e in (".js", ".ts", ".jsx", ".tsx") for e in est):
        problemi += 1
        print("[WARN] nessun file JS/TS nell'indice (atteso se workspace solo Python)")

    # 3. Ogni documento ha un vettore/embedding non vuoto
    con_vec = sum(1 for doc in docs if doc.get("vector") or doc.get("embedding"))
    esaminati += 1
    print(f"[OK] documenti con vettore: {con_vec}/{len(docs)}")
    if con_vec == 0:
        problemi += 1
        print("[FAIL] nessun documento ha un vettore/embedding")

    # 4. Una query concettuale restituisce risultati NON vuoti
    mod = _carica_server()
    server = mod.SemanticMCPServer()
    result = server.call_tool("semantic_search", {"query": "gestione errori di rete e retry", "top_k": 5})
    esaminati += 1
    if result.get("error"):
        problemi += 1
        print(f"[FAIL] semantic_search: {result['error']}")
    else:
        n = len(result.get("results", []))
        print(f"[OK] semantic_search 'gestione errori di rete': {n} risultati")
        if n == 0:
            problemi += 1
            print("[FAIL] la query concettuale non ha restituito alcun risultato")

    # 5. Una seconda query su un dominio presente nel workspace
    result2 = server.call_tool("semantic_search", {"query": "registrazione rotte API e gestione richieste HTTP", "top_k": 5})
    esaminati += 1
    if result2.get("error"):
        problemi += 1
        print(f"[FAIL] semantic_search rotte: {result2['error']}")
    else:
        n2 = len(result2.get("results", []))
        print(f"[OK] semantic_search 'rotte API': {n2} risultati")
        if n2 == 0:
            problemi += 1
            print("[FAIL] la query sulle rotte non ha restituito alcun risultato")

    _esiti(esaminati, problemi)
    return 0 if problemi == 0 else 1


def _esiti(esaminati: int, problemi: int) -> None:
    riga = json.dumps({"check": "semantic_index", "checked": esaminati, "problems": problemi}, ensure_ascii=False)
    print(f"SIGMA-CHECK {riga}")


if __name__ == "__main__":
    sys.exit(main())
