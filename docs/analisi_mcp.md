# Analisi Tool MCP — Sigma Studio

## 1. Tool MCP attualmente disponibili

| Server | File sorgente | Tool principali |
|:---|:---|:---|
| **Inference MCP** | `core/mcp/inference_server.py` | Selezione provider LLM, routing dinamico |
| **Progetto MCP** | `core/mcp/progetto_server.py` | Documentazione interrogabile di Sigma Studio |
| **Developer Git** | `core/modules/sigma_developer_lab/mcp_tools/git_server.py` | 10 tool: status, diff, log, branch_list/create/checkout, add, commit, push, stash |
| **Developer Lint** | `core/modules/sigma_developer_lab/mcp_tools/lint_server.py` | lint_python (ruff), lint_js (eslint) |
| **Developer Test** | `core/modules/sigma_developer_lab/mcp_tools/test_server.py` | run_tests, run_test_file, list_test_files, get_coverage |
| **Creative Lab** | `core/modules/sigma_creative_lab/mcp_server.py` | Generazione immagini, audio, video |
| **Benchmark Lab** | `core/modules/sigma_benchmark_lab/benchmark_server.py` | Benchmark modelli LLM, misurazione latenza/throughput |
| **Deps Audit (NUOVO)** | `core/modules/sigma_developer_lab/mcp_tools/deps_server.py` | deps_audit: verifica requisiti, vulnerabilità, coerenza Python/JS |
| **Developer Health (NUOVO)** | `core/modules/sigma_developer_lab/mcp_tools/health_server.py` | server_health: stato workspace, venv, CLI tool, key files, project stats |
| **Developer Profile (NUOVO)** | `core/modules/sigma_developer_lab/mcp_tools/profile_server.py` | profile_app: profiling cProfile (Python) / node --prof (JS), top N funzioni per tempo |
| **Developer Screenshot (NUOVO)** | `core/modules/sigma_developer_lab/mcp_tools/screenshot_server.py` | screenshot_page: apre URL in browser headless, salva PNG, restituisce percorso e dimensioni |

> **Nota:** `semantic_code_search` (ricerca semantica del codice) è stato implementato in questa sessione come server MCP autonomo `SemanticMCPServer` in `core/modules/sigma_developer_lab/mcp_tools/semantic_server.py`. Offre 4 tool: `semantic_search`, `index_codebase`, `index_status`, `explain_code`. Usa un approccio ibrido: estrazione strutturata + embedding semantici via sentence-transformers (se disponibile) con fallback TF-IDF + cosine similarity. L'indice vive in `var/semantic_index/index.json` (2377 documenti al primo build).

| Task | Stato | Note |
|:---|:---|:---|
| #1 deps_audit + server_health | ✅ FATTO | Implementati e verificati (`deps_server.py`, `health_server.py`) |
| #2 profile_app + screenshot_page | ✅ FATTO | Implementati e verificati (`profile_server.py`, `screenshot_server.py`) |
| #3 semantic_code_search | ✅ FATTO | Implementato come `SemanticMCPServer` in `semantic_server.py` con fallback TF-IDF + sentence-transformers |
| #4 Suite di collaudo completa | ✅ FATTO | 48 test unitari in `tests/test_mcp_developer_tools.py` eseguiti con successo (48 passed, 0 failed) |

## 2. Gap identificati nel flusso di sviluppo attuale

1. **Assenza audit dipendenze** — Non esisteva un tool per verificare `requirements.txt` / `package.json`, rilevare pacchetti obsoleti o vulnerabili, e controllare la coerenza tra i due ecosistemi. → **RISOLTO** con `deps_audit`.

2. **Assenza verifica stato workspace** — Non esisteva un tool che desse agli agenti una fotografia immediata dello stato del progetto: presenza di file chiave (requirements.txt, package.json, pyproject.toml), stato del venv, disponibilità dei CLI tool (pip-audit, npm, node), e statistiche di conteggio file per linguaggio. → **RISOLTO** con `server_health`.

2. **Assenza profiling applicativo** — Non esiste un tool MCP che esegua `cProfile` / `py-spy` / `node --prof` e restituisca un report strutturato (top N funzioni per tempo, memoria). L'unico modo attuale è lanciare manualmente comandi nel terminale.

3. **Assenza verifica visiva automatizzata** — Per il frontend l'unico modo per "vedere" il risultato è `npm run build` (compila ≠ si vede). Non esiste un tool che apra la pagina in un browser headless e restituisca uno screenshot o un diff visivo. Il tool `screenshot` esiste nel harness (`core/harness/visual.py`) ma non è esposto come MCP server per gli agenti.

4. **Assenza ricerca semantica del codice** — La ricerca attuale è solo testuale (`search_code`). Non esiste un tool che usi embedding per trovare funzioni/classi concettualmente simili, utile per refactoring o comprensione di codice legacy.

## 3. Proposte di nuovi tool MCP

### 3.1 `profile_app` (complessità: media)
- **Funzione**: Esegui profiling Python (`cProfile`) o Node.js (`node --prof`) su un modulo/script specifico, restituisci top N funzioni per tempo cumulativo e memoria.
- **Argomenti**: `language` (python|js), `target` (modulo o file), `top_n` (int, default 10), `include_memory` (bool)
- **Motivazione**: Gap #2. Permette agli agenti di identificare colli di bottiglia senza intervento manuale.
- **File proposto**: `core/modules/sigma_developer_lab/mcp_tools/profile_server.py`

### 3.2 `screenshot_page` (complessità: bassa)
- **Funzione**: Apri una URL in un browser headless (Playwright/Puppeteer), salva uno screenshot PNG, restituisci il percorso del file e dimensioni.
- **Argomenti**: `url` (string), `path` (percorso output, default `var/screenshots/`), `full_page` (bool)
- **Motivazione**: Gap #3. Espone la capacità già presente in `core/harness/visual.py` come MCP tool per gli agenti.
- **File proposto**: `core/modules/sigma_developer_lab/mcp_tools/screenshot_server.py`

### 3.3 `semantic_code_search` (complessità: alta)
- **Funzione**: Usa embedding (es. `sentence-transformers`) per trovare funzioni/classi concettualmente simili a una query testuale.
- **Argomenti**: `query` (string), `language` (python|js|all), `top_k` (int, default 5), `min_similarity` (float, default 0.7)
- **Motivazione**: Gap #4. Permette refactoring guidato e comprensione di codice legacy senza cercare manualmente nomi di funzione.
- **File proposto**: `core/modules/sigma_developer_lab/mcp_tools/semantic_search_server.py`

## 4. Verifica e Collaudo
 
- `deps_audit`: implementato in `core/modules/sigma_developer_lab/mcp_tools/deps_server.py`
- `server_health`: implementato in `core/modules/sigma_developer_lab/mcp_tools/health_server.py`
- `profile_app`: implementato in `core/modules/sigma_developer_lab/mcp_tools/profile_server.py` (cross-platform, fallback psutil/resource, parsing cProfile pstats)
- `screenshot_page`: implementato in `core/modules/sigma_developer_lab/mcp_tools/screenshot_server.py` (Playwright headless con timeout controllato)
- `semantic_code_search`: implementato in `core/modules/sigma_developer_lab/mcp_tools/semantic_server.py` (ibrido: sentence-transformers + fallback TF-IDF cosine similarity, AST chunking Python/JS)
- `bridge.py`: registrati tutti gli 8 nuovi tool nella mappatura `ADMIN_TO_MCP`
- **Suite di test ufficiale:** `tests/test_mcp_developer_tools.py` con **48 test passati su 48** (0 falliti).
- Test autonomi dedicati:
  - `python tools/verifica_deps_server.py` → `SIGMA-CHECK {"check": "deps_server", "checked": 1, "problems": 0}`
  - `python tools/verifica_health_server.py` → `SIGMA-CHECK {"check": "health_server", "checked": 1, "problems": 0}`
  - `python tools/verifica_profile_server.py` → `SIGMA-CHECK {"check": "profile_server", "checked": 1, "problems": 0}`
