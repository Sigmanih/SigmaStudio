"""Verifica del server MCP semantic_code_search.

Importa il modulo senza attivare __init__ del pacchetto (che richiede fastapi),
e dimostra che l'indice, la query semantica e il fallback TF-IDF funzionano.

Uscita: codice 0 + riga SIGMA-CHECK con conteggio elementi esaminati.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PERCORSO_SERVER = ROOT / "core" / "modules" / "sigma_developer_lab" / "mcp_tools" / "semantic_server.py"


def _carica_server():
    """Carica semantic_server.py come modulo isolato, senza eseguire __init__ del pacchetto."""
    spec = importlib.util.spec_from_file_location("semantic_server_isolato", PERCORSO_SERVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    problemi = 0
    esaminati = 0

    # 1. Caricamento del modulo e istanza del server
    try:
        mod = _carica_server()
        server = mod.SemanticMCPServer()
        tools = [t["name"] for t in server.list_tools()]
        esaminati += 1
        print(f"[OK] Server caricato, tool disponibili: {tools}")
        if "semantic_search" not in tools or "explain_code" not in tools:
            problemi += 1
            print("[FAIL] mancanti semantic_search o explain_code")
    except Exception as exc:
        problemi += 1
        esaminati += 1
        print(f"[FAIL] caricamento server: {exc}")
        _esiti(esaminati, problemi)
        return 1

    # 2. Costruzione dell'indice (tool reale: index_codebase)
    try:
        result = server.call_tool("index_codebase", {})
        esaminati += 1
        if result.get("error") or result.get("isError"):
            problemi += 1
            err = result.get("error") or (result.get("content") or [{}])[0].get("text", "errore sconosciuto")
            print(f"[FAIL] index_codebase: {err}")
        else:
            content = result.get("content") or []
            testo = content[0].get("text", "") if content else ""
            print(f"[OK] Indice costruito: {testo[:120]}")
    except Exception as exc:
        problemi += 1
        esaminati += 1
        print(f"[FAIL] index_codebase eccezione: {exc}")

    # 3. Query semantica concettuale
    try:
        result = server.call_tool("semantic_search", {"query": "gestione errori di rete e retry"})
        esaminati += 1
        if result.get("error"):
            problemi += 1
            print(f"[FAIL] semantic_search: {result['error']}")
        else:
            n = len(result.get("results", []))
            print(f"[OK] semantic_search: {n} risultati")
    except Exception as exc:
        problemi += 1
        esaminati += 1
        print(f"[FAIL] semantic_search eccezione: {exc}")

    # 4. explain_code su un simbolo reale del workspace
    try:
        result = server.call_tool("explain_code", {"symbol": "MCPHub", "path_hint": "core/mcp/mcp_hub.py"})
        esaminati += 1
        if result.get("error"):
            problemi += 1
            print(f"[FAIL] explain_code: {result['error']}")
        else:
            print(f"[OK] explain_code: {str(result.get('explanation', ''))[:80]}...")
    except Exception as exc:
        problemi += 1
        esaminati += 1
        print(f"[FAIL] explain_code eccezione: {exc}")

    # 5. Fallback TF-IDF senza sentence-transformers
    try:
        result = server.call_tool("semantic_search", {"query": "autenticazione utente", "force_fallback": True})
        esaminati += 1
        if result.get("error") or result.get("isError"):
            problemi += 1
            err = result.get("error") or (result.get("content") or [{}])[0].get("text", "errore sconosciuto")
            print(f"[FAIL] fallback search: {err}")
        else:
            content = result.get("content") or []
            testo = content[0].get("text", "") if content else ""
            import json as _json
            n = 0
            try:
                dati = _json.loads(testo)
                if isinstance(dati, list):
                    n = len(dati)
                elif isinstance(dati, dict):
                    n = len(dati.get("results", []))
            except Exception:
                # La risposta e' una lista JSON di risultati: conta gli oggetti
                import re as _re
                n = len(_re.findall(r'\{\s*"file"', testo))
            if n == 0:
                problemi += 1
                print(f"[FAIL] Fallback TF-IDF: 0 risultati (doveva trovarne almeno uno). Testo: {testo[:200]}")
            else:
                print(f"[OK] Fallback TF-IDF: {n} risultati")
    except Exception as exc:
        problemi += 1
        esaminati += 1
        print(f"[FAIL] fallback search eccezione: {exc}")

    _esiti(esaminati, problemi)
    return 0 if problemi == 0 else 1


def _esiti(esaminati: int, problemi: int) -> None:
    riga = json.dumps({"check": "semantic", "checked": esaminati, "problems": problemi}, ensure_ascii=False)
    print(f"SIGMA-CHECK {riga}")


if __name__ == "__main__":
    sys.exit(main())
