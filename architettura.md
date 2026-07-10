# 🧬 Σ-SIGMA Studio — Architettura Completa della Piattaforma

```
Versione: 6.2
Backend: Python HTTP Server custom (porta 8000)
Frontend: React 19 + Vite 6
AI: Multi-Provider (Ollama, DeepSeek, OpenAI, Anthropic, Groq, OpenRouter)
Dati: File system modulare JSON-based
Totale: ~11.000+ righe di codice
```

---

## 1. 🌐 Panoramica Generale

Sigma Studio è un **motore di orchestrazione cognitiva AI-native** per ricerca scientifica, sviluppo software e gestione della conoscenza. Non è un wiki, non è un CMS, non è un IDE — è un ambiente eseguibile dove l'intelligenza artificiale crea, verifica, documenta e organizza conoscenza, regolamentata da manifesti Modelfile che ne determinano il comportamento.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                              Σ-SIGMA STUDIO v6                               │
│                                                                               │
│  ┌──────────────────────────┐     ┌───────────────────┐    ┌───────────────┐  │
│  │    sigma_server.py       │     │  sigma_studio/    │    │  manifesti/   │  │
│  │    (Backend Python)      │◄──► │  (Frontend React) │    │  (Modelfile)  │  │
│  └──────────┬───────────────┘     └───────────────────┘    └───────────────┘  │
│             │                                                                  │
│             ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐         │
│  │                      data/  (Knowledge Base)                     │         │
│  │  matematica/  │  scratch/  │  (topic/NN_modulo/sezione/file)    │         │
│  └──────────────────────────────────────────────────────────────────┘         │
│             │                                                                  │
│             ▼                                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐         │
│  │              core/  (10 moduli backend — Separation of Concerns) │         │
│  │  sandbox.py  │  ai_providers.py  │  chat_handler.py  │  api_router.py     │
│  │  task_handler.py │ file_handler.py │ data_handler.py │ module_handler.py  │
│  │  config_handler.py │ loop_handler.py │ execute_loop.py │ plan_handler.py  │
│  │  sandbox_manager.py                                                  │    │
│  └──────────────────────────────────────────────────────────────────┘         │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐         │
│  │              File di Sistema (Project Root)                       │         │
│  │  tasks.json  │  modules_meta.json  │  config.json               │         │
│  └──────────────────────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Principi Fondamentali

| Principio | Descrizione |
|-----------|-------------|
| 🔒 **Sandbox Security** | Ogni operazione confinata in path whitelist (`data/`, `manifesti/`, `sigma_studio/`, `core/`, `scratch/`) |
| 📜 **Manifesti Modelfile** | Agenti AI definiti come Modelfile Ollama con identità, regole, parametri |
| 📋 **Notifiche Obbligatorie** | "Una notifica non lasciata è un'azione mai avvenuta" — ogni azione genera traccia in `tasks.json` |
| 🧩 **Modularità** | Separation of concerns in 10 moduli core + componenti React indipendenti |
| 🧠 **Multi-Provider AI** | Supporto per 6 provider con routing intelligente basato sul nome del modello |
| 🏗️ **Full-Stack AI** | Dalla teoria accademica al software funzionante: teoremi → test → visualizzazioni → whitepaper |
| 🚫 **Niente Dati nel Frontend** | Il frontend React è "stupido" — fa fetch da `/api/*` |

---

## 2. 🏗️ Backend (`sigma_server.py` + `core/`)

### 2.1 Server HTTP Custom

| Proprietà | Valore |
|-----------|--------|
| **File** | `sigma_server.py` (248 righe) |
| **Stack** | Python HTTP server puro con `ThreadingMixIn` (multi-thread) |
| **Porta** | 8000 |
| **Architettura** | Handler HTTP leggero (`SigmaAPIHandler`) che delega a moduli esterni |
| **Pattern** | Monkey-patching dei metodi handler sulla classe server |
| **Auto-build** | Esegue `npm run build` all'avvio in `sigma_studio/` |
| **Startup** | Ricostruisce `modules_meta.json` dal filesystem al boot |
| **Shutdown** | Graceful con `signal.SIGINT`/`SIGTERM` |

**Struttura della classe server:**

```python
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class SigmaAPIHandler(SimpleHTTPRequestHandler):
    _is_path_allowed = staticmethod(is_path_allowed)

    def do_GET(self):    route_get(self)
    def do_POST(self):   route_post(self)
    def read_json_body(self):    ...
    def send_json_response(self): ...
    def serve_static_file(self): ...
    def get_module_meta(self):   ...
    def save_module_meta(self):  ...
```

**Importazione handler esterni (monkey-patching):**

```python
from core.data_handler import handle_api_modules, ...
SigmaAPIHandler.handle_api_modules = handle_api_modules

from core.chat_handler import handle_chat
SigmaAPIHandler.handle_chat = handle_chat

# ... 10 moduli caricati così
```

### 2.2 Moduli Core (10 file in `core/`)

| # | Modulo | File | Funzione | Righe |
|---|--------|------|----------|-------|
| 1 | **Sandbox** | `sandbox.py` | Validazione path, whitelist `ALLOWED_PREFIXES` | 42 |
| 2 | **AI Providers** | `ai_providers.py` | Config loader, provider resolver, chiamate API (Ollama/OpenAI/Anthropic) | 501 |
| 3 | **API Router** | `api_router.py` | Routing GET/POST, serving static files da `sigma_studio/dist/` | 91 |
| 4 | **Chat Handler** | `chat_handler.py` | Orchestrazione chat, 4 modalità, streaming SSE, web search | 766 |
| 5 | **Execute Loop** | `execute_loop.py` | Loop iterativo AI → azioni → risultati → AI (Cline-style) | 341 |
| 6 | **Plan Handler** | `plan_handler.py` | Plan → Act workflow: genera piano strutturato, esegue step-by-step | 397 |
| 7 | **Loop Handler** | `loop_handler.py` | Loop autonomo: pianifica task → esegue → verifica → report | 551 |
| 8 | **Task Handler** | `task_handler.py` | Esecuzione azioni AI, validazione moduli, notifiche automatiche | 516 |
| 9 | **Config Handler** | `config_handler.py` | CRUD configurazione AI, lista modelli Ollama, creazione modelli | 120 |
| 10 | **File Handler** | `file_handler.py` | CRUD file, upload multipart, esecuzione test | 139 |
| 11 | **Data Handler** | `data_handler.py` | Lettura moduli/topics, knowledge graph D3, lista manifesti | 158 |
| 12 | **Module Handler** | `module_handler.py` | CRUD topics e moduli, creazione cartella con sottocartelle | 168 |
| 13 | **Sandbox Manager** | `sandbox_manager.py` | Gestione venv, npm, sandbox isolate per progetti | 451 |

### 2.3 Sistema API — Endpoint Completi

#### GET (9 endpoint)

| Endpoint | Handler | Funzione |
|----------|---------|----------|
| `/api/modules` | `handle_api_modules` | Lista moduli con file per categoria |
| `/api/topics` | `handle_api_topics` | Argomenti con gerarchia parent/child |
| `/api/tasks` | `handle_api_tasks_get` | Roadmap + notifiche |
| `/api/get_file` | `handle_get_file` | Legge file (sandbox-safe) |
| `/api/list_manifesti` | `handle_list_manifesti` | Elenca agenti AI disponibili |
| `/api/knowledge_db` | `handle_knowledge_db` | Dati per grafo conoscenza D3 |
| `/api/config` | `handle_api_config_get` | Config AI (senza API key) |
| `/api/ollama_models` | `handle_api_ollama_models` | Modelli Ollama installati |
| `/api/sandbox/list` | `handle_sandbox_list` | Lista sandbox attive |

#### POST (20 endpoint)

| Endpoint | Handler | Funzione |
|----------|---------|----------|
| `/api/run_test` | `handle_run_test` | Esegue script Python/Node |
| `/api/create_file` | `handle_create_file` | Crea/scrive file |
| `/api/delete_file` | `handle_delete_file` | Elimina file |
| `/api/tasks` | `handle_api_tasks_post` | Salva tasks.json |
| `/api/create_module` | `handle_create_module` | Crea modulo con sottocartelle |
| `/api/delete_module` | `handle_delete_module` | Elimina modulo |
| `/api/upload_file` | `handle_upload_file` | Upload multipart |
| `/api/update_module` | `handle_update_module` | Rinomina modulo |
| `/api/create_topic` | `handle_create_topic` | Crea argomento in data/ |
| `/api/update_topic` | `handle_update_topic` | Modifica metadati argomento |
| `/api/delete_topic` | `handle_delete_topic` | Elimina argomento |
| `/api/config` | `handle_api_config_post` | Aggiorna config AI |
| `/api/chat` | `handle_chat` | Chat con AI (4 modalità) |
| `/api/chat/loop` | `handle_chat_loop` | Loop autonomo task-driven |
| `/api/chat/execute` | `handle_chat_execute` | Loop esecutivo continuo |
| `/api/chat/plan` | `handle_chat_plan` | Genera piano strutturato |
| `/api/chat/execute_plan` | `handle_chat_execute_plan` | Esegue piano step-by-step |
| `/api/create_model` | `handle_api_create_model` | Crea modello Ollama da Modelfile |
| `/api/ollama_models` | `handle_api_ollama_models` | Aggiorna lista modelli |
| `/api/sandbox/create/run/install/destroy` | `handle_sandbox_*` | CRUD sandbox |

#### Routing Statico

```python
def _serve_static(self, rel_path):
    dist_path = os.path.join('sigma_studio', 'dist')
    # Se il file non esiste in dist/ e non è una richiesta API → index.html (SPA fallback)
    # Altrimenti → file richiesto o 404
```

### 2.4 Architettura AI Multi-Provider

```
┌─────────────────────────────────────────────────────┐
│             core/ai_providers.py                     │
│                                                      │
│  load_ai_config() → config.json (6 provider)        │
│  resolve_provider_config(model) → (provider, cfg)   │
│                                                      │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐          │
│  │ Ollama  │  │ OpenAI-  │  │ Anthropic │          │
│  │ locale  │  │ compat.  │  │ Claude    │          │
│  └─────────┘  └──────────┘  └───────────┘          │
│                                                     │
│  call_ollama() / call_ollama_stream()               │
│  call_openai_compatible() / call_openai_compatible_stream()
│  call_anthropic()                                    │
└─────────────────────────────────────────────────────┘
```

#### Provider Supportati

| Provider | Tipo | Endpoint Default |
|----------|------|------------------|
| **Ollama** 🦙 | Locale (gratuito) | `http://localhost:11434/api/chat` |
| **DeepSeek** 🔍 | Cloud API | `https://api.deepseek.com/v1/chat/completions` |
| **OpenAI** 🤖 | Cloud API | `https://api.openai.com/v1/chat/completions` |
| **Anthropic (Claude)** 🟣 | Cloud API | API URL configurabile |
| **Groq** ⚡ | Cloud API | API URL configurabile |
| **OpenRouter** 🌐 | Cloud API (multi-modello) | API URL configurabile |

#### Strategia di Risoluzione Provider

```
1. Match esatto in models[] di un provider
2. Match sul modello di default del provider
3. Prefix match (es. 'deepseek-chat' → provider DeepSeek)
4. Cloud prefix mapping:
   - 'gpt-*', 'o1', 'o3-*' → OpenAI
   - 'claude-*' → Anthropic
   - 'deepseek-*' → DeepSeek
   - 'llama-3.3', 'mixtral-8x7b', 'gemma2-9b' → Groq
   - 'openai/', 'anthropic/', 'google/', 'mistral/' → OpenRouter
5. FALLBACK: modelli sconosciuti → SEMPRE Ollama (locale), mai cloud
```

#### Parametri AI Supportati

```python
options = {
    "temperature": 0.0-2.0,       # Creatività (default: 0.7)
    "num_predict": max_tokens,     # Token massimi output
    "top_p": 0.0-1.0,             # Nucleus sampling
    "top_k": 1-100,               # Top K tokens per step
    "repeat_penalty": 0.0-2.0,    # Penalità ripetizione (1.0=off)
    "num_ctx": 512-131072,        # Finestra contesto
    "seed": 0,                    # Seed per riproducibilità (0=random)
}
```

#### Gestione Errori

- **ConnectionError**: Modello Ollama non raggiungibile
- **Timeout**: Modello troppo grande o hardware lento
- **Rate limiting**: Gestito dal provider cloud
- **Fallback**: Provider non disponibile → messaggio chiaro all'utente

### 2.5 Sistema di Chat — 4 Modalità Operative

| Modalità | Descrizione | Endpoint | Streaming | Azioni | Notifiche |
|----------|-------------|----------|-----------|--------|-----------|
| 💬 **Chiedi** | Risposte testuali senza modifiche | `/api/chat` | ✅ SSE | ❌ | Nessuna |
| 📋 **Pianifica** | Analisi e creazione task in Roadmap | `/api/chat` | ❌ JSON | Crea task | ✅ |
| ⚡ **Esegui** | Loop continuo AI → azioni → feedback | `/api/chat/execute` | ✅ SSE | ✅ | ✅ |
| ✅ **Completa Task** | Esegue task specifico da Roadmap | `/api/chat` | ❌ JSON | ✅ | ✅ |

#### Flusso Esecutivo (`chat_handler.py`)

```
handle_chat(self):
  1. Leggi richiesta (messaggio, modalità, contesto, file)
  2. Risolvi manifesto → sistema identità agente
  3. Costruisci system prompt:
     - Manifesto agente (identità, regole, parametri)
     - Action prompt (formato JSON obbligatorio se allow_actions)
     - Contesto: files aperti, struttura filesystem, tasks.json
  4. Web search opzionale (DuckDuckGo + Wikipedia)
  5. Chiamata provider AI (Ollama, OpenAI, Anthropic)
  6. Estrazione JSON dalla risposta
  7. Se planning_mode: crea task in tasks.json
  8. Se allow_actions: esegui azioni (execute_ai_actions)
  9. Auto-completa task se execute_task_id presente
  10. Ritorna {response, thinking, actions_log, manifesto_used}
```

#### Sistema di Cleaning delle Risposte AI

```python
def _clean_all_tags(content):
    """Rimozione universale di tutti i container tags e thinking process."""
    # Fase 1: Estrai thinking da tag XML (<thinking>, <Thought>, <reasoning>)
    # Fase 2: Rimuovi container tags (<response>, <output>, <answer>, ...)
    # Fase 3: Estrai English thinking process (modelli Gemma, fine-tuned)
    # Fase 4: Rimuovi tag XML rimanenti
    # Fase 5: Pulisci linee vuote eccessive
```

#### Ricerca Web Integrata

```python
def _perform_web_search(query):
    # 1. Se è un URL → scrape diretto
    # 2. Match dominio noto (corriere, repubblica, wikipedia, github)
    # 3. DuckDuckGo search (html.duckduckgo.com)
    # 4. Fallback: Wikipedia API
```

### 2.6 Execute Loop — Iterativo Cline-style (`execute_loop.py`)

```
execute_feedback_loop(self, req, stream_callback):
  1. AI riceve goal + contesto completo
  2. Risponde con JSON: {"response": "...", "actions": [...]}
  3. Se no JSON → mostra come testo + detect completamento da keyword
  4. Sistema esegue azioni (create_file, edit_file, run_test, ...)
  5. Risultati tornano all'AI come feedback
  6. AI analizza e decide: continuare o completare ({"done": true})
  7. Fino a N iterazioni (default 100, max 1000)
  8. Alla fine: report riepilogativo
```

**Validazione azioni:**

```python
_VALID_ACTION_TYPES = frozenset([
    'create_file', 'edit_file', 'rename_file', 'delete_file',
    'create_module', 'run_test', 'update_task', 'read_file',
    'send_notification', 'run_terminal',
])
```

### 2.7 Plan Handler — Plan → Act Workflow (`plan_handler.py`)

```
FASE 1 — PLAN:  POST /api/chat/plan
  - AI analizza goal → produce piano con step strutturati
  - Ogni step: description + actions[] + status
  - Output: {analysis, steps[{description, actions}], plan_id}

FASE 2 — APPROVE: Utente approva o rifiuta (o Auto-approve salta)

FASE 3 — ACT:  POST /api/chat/execute_plan
  - Esegue ogni step in sequenza
  - SSE streaming per ogni step
  - Report finale con statistiche
```

### 2.8 Task Handler — Esecuzione Azioni AI (`task_handler.py`)

#### Azioni Supportate da `execute_ai_actions()`

| Tipo | Parametri | Sandbox Check | Descrizione |
|------|-----------|---------------|-------------|
| `create_file` | path, content | ✅ `_validate_module_path()` + `_ensure_module_structure()` + `_is_path_allowed()` | Crea file con contenuto |
| `edit_file` | path, content, search | ✅ Path consentito + esistenza file | Modifica file (sostituzione testo o sovrascrittura) |
| `rename_file` | old_path, new_path | ✅ Entrambi i path | Rinomina/sposta file |
| `delete_file` | path | ✅ Path consentito + esistenza | Elimina file |
| `create_module` | topic, number, name | Crea 5 sottocartelle whitelist | Crea modulo con struttura standard |
| `update_task` | titolo, status, notifica | Aggiorna tasks.json | Aggiorna stato/notifiche task |
| `run_test` | path | ✅ Subprocess Python o Node | Esegue script di test |
| `read_file` | path | ✅ Path consentito + size < 100KB | Legge file per contesto AI |
| `send_notification` | destinatario, messaggio | Log in tasks.json | Invia notifica |
| `run_terminal` | cmd, cwd | ✅ Directory consentite + timeout | Esegui comando shell |

#### Regola WHITELIST per i Moduli

```python
_ALLOWED_MODULE_SECTIONS = frozenset({
    'teoria', 'test', 'viz', 'docs', 'whitepapers',
})
```

**Validazione struttura:**

```python
def _validate_module_path(path):
    """Regola ferrea: dentro un modulo sono permesse SOLO 5 sezioni."""
    # data/argomento/file → ❌ (root del topic)
    # data/topic/sezione/file → ❌ (sezione senza modulo)
    # data/topic/NN_modulo/file → ❌ (root del modulo)
    # data/topic/NN_modulo/ALTRO/file → ❌ (sezione non whitelist)
    # data/topic/NN_modulo/teoria/file → ✅
```

#### Auto-Wrapping Modulo

Se l'AI crea `data/topic/teoria/file.md` (senza modulo), il sistema auto-crea `01_base`:

```python
def _ensure_module_structure(path):
    # data/topic/teoria/file.md → data/topic/01_base/teoria/file.md
    # data/topic/docs/file.md → data/topic/01_base/docs/file.md
```

#### Notifiche Automatiche

```python
def _add_action_notifications(log, bot_name):
    """Ogni azione di successo genera notifica nel task attivo."""
    # Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
    # Trova task con status "in_corso" o crea task di default
    # Per ogni action_type in (create_file, edit_file, delete_file, ...):
    #   → Aggiunge notifica con timestamp ISO 8601
```

### 2.9 Sandbox — Validazione Path (`sandbox.py`)

```python
ROOT_FILES = frozenset({
    'tasks.json', 'modules_meta.json', 'config.json',
    'sigma_server.py', 'README.md', 'package.json'
})

ALLOWED_PREFIXES = (
    'data/', 'manifesti/', 'scratch/',
    'sigma_studio/', 'core/', 'sigma_studio/src/'
)

def is_path_allowed(path: str) -> bool:
    if not path or '..' in path:
        return False
    normalized = path.replace('\\', '/')
    if normalized in ROOT_FILES:
        return True
    return normalized.startswith(ALLOWED_PREFIXES)
```

### 2.10 Sandbox Manager — Ambienti Virtuali (`sandbox_manager.py`)

| Operazione | Endpoint | Descrizione |
|------------|----------|-------------|
| `create_sandbox()` | `POST /api/sandbox/create` | Crea progetto in `projects/` con venv o node_modules |
| `run_in_sandbox()` | `POST /api/sandbox/run` | Esegue comando in sandbox |
| `install_package()` | `POST /api/sandbox/install` | Installa pip/npm packages |
| `destroy_sandbox()` | `POST /api/sandbox/destroy` | Pulisce venv/node_modules o elimina tutto |
| `list_sandboxes()` | `GET /api/sandbox/list` | Lista sandbox attive |

**Templates:** `python`, `node`, `fullstack`

**Auto-setup all'avvio:**
- `ensure_venv()` → crea `.venv` con requests, beautifulsoup4, lxml
- `ensure_npm()` → installa node_modules in `sigma_studio/`

### 2.11 Flusso di Avvio Server

```
1. Avvio sigma_server.py (o sigma_studio.bat)
2. Segnali graceful shutdown (SIGINT, SIGTERM)
3. Ricostruisce modules_meta.json dal filesystem:
   - Scansiona data/ per topic e moduli
   - Preserva campi custom (parent_id, descrizione, domain)
   - Rimuove riferimenti stale (parent_id di topic cancellati)
4. ensure_venv() → crea/verifica virtual environment Python
5. npm run build → build frontend in sigma_studio/dist/
6. Avvia ThreadedHTTPServer su porta 8000
```

---

## 3. 🎨 Frontend (`sigma_studio/` — React 19 + Vite)

### 3.1 Stack Tecnologico

| Componente | Tecnologia |
|-----------|------------|
| **Framework** | React 19 (StrictMode) |
| **Build** | Vite 6 |
| **Linguaggio** | JavaScript (JSX) |
| **Package Manager** | npm |
| **Proxy Dev** | `/api/*` → `localhost:8000` (vite.config.js) |
| **Tema** | Dark glass-morphism |
| **Font** | Inter + JetBrains Mono |

### 3.2 Entry Point

```
index.html → src/main.jsx → App.jsx
```

```jsx
// main.jsx
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### 3.3 App.jsx — Orchestratore Centrale (313 righe)

```
┌─────────────────────────────────────────────────────────────┐
│                         App.jsx                             │
│                                                             │
│  Hooks: useModules, useTasks, useTabs, useToast             │
│                                                             │
│  ┌────────────┐  ┌───────────┐  ┌──────────────┐          │
│  │  Sidebar   │  │ Workspace │  │  Dashboard   │          │
│  │ (sinistra) │  │ (centro)  │  │ (destra)     │          │
│  └────────────┘  └───────────┘  └──────────────┘          │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │  Modali: ModuleModal, TaskModal, NewFileModal     │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │  Float: ChatPanel + AIConfig + ToastNotification │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**Stato locale gestito:**

```javascript
const [leftVisible, setLeftVisible] = useState(true);
const [rightVisible, setRightVisible] = useState(true);
const [aiChatOpen, setAiChatOpen] = useState(false);
const [aiConfigOpen, setAiConfigOpen] = useState(false);
const [isModalOpen, setIsModalOpen] = useState(false);
const [terminalOutput, setTerminalOutput] = useState("...");
```

**CRUD Centralizzato:**
- `handleCreateFile()` / `deleteFileDirectly()` / `runTest()`
- `handleCreateModule()` / `handleUpdateModule()` / `handleDeleteModule()`
- `onTaskSave()` / `toggleTaskStatus()` / `deleteTask()`

**Event Listeners:**
- `window.addEventListener('message', ...)` — per messaggi cross-frame
- `window.addEventListener('sigma-open-file', ...)` — per eventi custom

### 3.4 Componenti Principali

| Componente | File | Funzione | Righe |
|-----------|------|----------|-------|
| **App.jsx** | `App.jsx` | Orchestratore stato globale, CRUD file/moduli/task | 313 |
| **Sidebar** | `components/Sidebar.jsx` | Navigazione laterale con albero moduli | — |
| **Workspace** | `components/Workspace.jsx` | Sistema a tab centrale | — |
| **Dashboard** | `components/Dashboard.jsx` | Roadmap task con cards | — |
| **Modals** | `components/modals/index.js` | CRUD per task, moduli, topic, file | — |
| **AIConfig** | `components/AIConfig.jsx` | Configurazione provider AI (6 provider) | — |
| **ChatPanel** | `components/Chat/ChatPanel.jsx` | Wrapper per ChatFloatingPanel | 13 |
| **ChatFloatingPanel** | `components/Chat/layouts/ChatFloatingPanel.jsx` | Pannello chat flottante | 187 |
| **useChatCore** | `components/Chat/core/useChatCore.js` | Hook centrale per tutta la logica chat | 667 |
| **ChatHistory** | `components/Chat/ChatHistory.jsx` | Cronologia sessioni chat | — |
| **ChatHeader** | `components/Chat/ui/ChatHeader.jsx` | Header pannello chat | — |
| **ChatMessages** | `components/Chat/ui/ChatMessages.jsx` | Visualizzazione messaggi | — |
| **ChatInput** | `components/Chat/ui/ChatInput.jsx` | Input messaggio | — |
| **MappaArgomenti** | `components/SigmaLab/MappaArgomenti.jsx` | Grafo D3.js interattivo | 1.264 |
| **ManifestiGallery** | `components/Workspace/ManifestiGallery.jsx` | AI Model Lab + gestione Modelfile | 400 |

### 3.5 Architettura Chat — useChatCore (667 righe)

Hook centrale che gestisce l'intera logica della chat AI.

```
useChatCore() → {
  // === Stato Core ===
  sessions[], activeSessionId, sessionMessages{},
  input, loading, selectedModel, configProvider,
  activeMode ('ask' | 'plan' | 'execute' | 'complete'),
  actionsLog[], attachedFiles[], pcFiles[], dragOver,
  webSearch, autoScroll, expandedThinking{},

  // === Configurazione AI ===
  quickConfig { temperature, max_tokens, top_p, top_k, ... },
  providerConfigs, availableModels, loadingModels,

  // === Manifesto ===
  activeManifesto, manifestos, selectedManifestoPath,

  // === Loop/Execute ===
  loopMaxIterations, loopIteration, loopActive,
  actionStrategy, currentPlan, planExecuting,

  // === UI ===
  showHistory, showModelDropdown, showFilePicker, ...

  // === Azioni ===
  sendMessage, stopInference,
  switchToSession, handleNewSession, handleDeleteSession,
  handleModelSelect, handleStartRename,
  handleStreamResponse, handleExecuteStream, handleJsonResponse,
  removePcFile, handleDragOver, handleDragLeave, handleDrop,
  saveQuickConfig, refreshConfig,
}
```

#### Pipeline di Invio Messaggio

```
1. refreshConfig() — aggiorna configurazione AI dal server
2. Crea o riusa sessione esistente
3. Aggiunge messaggio utente + file di contesto + file caricati dal PC
4. Determina routing provider da getModelRoutingInfo()
5. Se activeMode === 'execute' | 'complete':
   → POST /api/chat/execute (streaming SSE)
   → handleExecuteStream()
6. Se activeMode === 'ask' | 'plan':
   → POST /api/chat (stream o JSON)
   → handleStreamResponse() o handleJsonResponse()
7. Gestione errori e abort (AbortController)
8. Salvataggio forzato messaggi in localStorage
```

#### Streaming SSE — handleStreamResponse

```javascript
const handleStreamResponse = async (res, sessionId) => {
  const reader = res.body.getReader();
  let fullText = '', fullThinking = '';
  // Legge chunk SSE: "data: {token, thinking}" o "data: [DONE]"
  // Aggiorna incrementale il messaggio assistant in sessione
  // Alla fine: cleanModelTags() + salvataggio localStorage
};
```

#### Streaming Execute — handleExecuteStream

Gestisce eventi SSE complessi:
- `execute_start` → avvio loop
- `iteration_start` → nuova iterazione
- `iteration_actions` → azioni in esecuzione
- `iteration_complete` → iterazione completata con log
- `iteration_response` → risposta AI testuale intermedia
- `iteration_validation_error` → azioni non valide
- `execute_done` / `done` → completamento con summary
- `error` / `execute_timeout` → errori

### 3.6 Hooks Personalizzati

| Hook | File | Funzione |
|------|------|----------|
| `useModules` | `hooks/useModules.js` | Fetch/CRUD moduli da `/api/modules` |
| `useTasks` | `hooks/useTasks.js` | Fetch/CRUD task da `/api/tasks` |
| `useTabs` | `hooks/useTabs.js` | Gestione tab aperti (open, close, dirty, reorder) |
| `useToast` | `hooks/useToast.js` | Notifiche toast temporanee |
| `useChatResize` | `components/Chat/useChatResize.js` | Ridimensionamento pannello chat |
| `useChatDrag` | `components/Chat/useChatDrag.js` | Trascinamento pannello chat |
| `chatStorage` | `components/Chat/chatStorage.js` | Utility session storage |

### 3.7 MappaArgomenti — Knowledge Graph D3.js (1.264 righe)

Componente di visualizzazione interattiva con **D3 force-directed graph**.

#### Tre Livelli di Nodi

```
TOPIC (cerchio grande, r=22)
  ├── MODULO (cerchio medio, r=16)
  │   ├── DOCUMENTO: teoria (📖)
  │   ├── DOCUMENTO: test   (🧪)
  │   ├── DOCUMENTO: viz    (📊)
  │   ├── DOCUMENTO: docs   (📄)
  │   └── DOCUMENTO: whitepapers (📜)
```

#### Schema Grafo

```
┌────────────┐
│  Dashboard │ ← radice
└─────┬──────┘
      │ link topic-modulo
      ▼
┌────────────┐     ┌────────────┐
│  Topic A   │────→│  Topic B   │ ← parent-child (linea tratteggiata)
└─────┬──────┘     └────────────┘
      │
      ▼
┌────────────┐
│ Modulo 01  │
└─────┬──────┘
      │
      ├──→ 📖 teoria/file.md
      ├──→ 🧪 test/file.py
      ├──→ 📊 viz/file.html
      └──→ 📄 docs/file.md
```

#### Colori per Tipo

| Tipo | Stroke | Fill |
|------|--------|------|
| Topic | `#bc8cff` | `rgba(188,140,255,0.12)` |
| Modulo | `#00d2ff` | `rgba(0,210,255,0.12)` |
| Teoria | `#bc8cff` | `rgba(188,140,255,0.2)` |
| Test | `#3fb950` | `rgba(63,185,80,0.2)` |
| Viz | `#d29922` | `rgba(210,153,34,0.2)` |
| Docs | `#ffd700` | `rgba(255,215,0,0.2)` |

#### Interazioni

- **Click**: Seleziona nodo → mostra dettagli nel pannello laterale
- **Hover**: Highlight connessioni + opacità ridotta per nodi non collegati
- **Zoom**: Zoom/Pan mouse + pulsanti zoom (+/-/reset)
- **Force simulation**: D3 force con collision detection

#### Azioni dal Grafo

- Creare nuovo argomento, sottoargomento, file
- Rinominare/eliminare argomenti e moduli
- Aggiornare parent_id dei topic (selettore dropdown)
- Click documento → apre file nel workspace

#### Statistiche Calcolate

```javascript
const stats = { topics, modules, docs, teoria, test, viz, parentLinks };
```

### 3.8 ManifestiGallery — AI Model Lab (400 righe)

Pannello per creare e gestire modelli AI su Ollama.

#### Sezioni

1. **Manifesto Hero** — Introduzione ai Modelfile
2. **Cosa sono i Modelfile** — 3 card informative (System Prompt, Specializzazione, Parametri)
3. **Come costruire un Modelfile** — Guida in 5 passi con esempio di codice
4. **AI Model Lab** — Pannello di creazione:
   - Seleziona Modelfile base (`sigma_architect.md`, `math1.md`, ...)
   - Seleziona modello base Ollama (lista live da `/api/ollama_models`)
   - Assegna nome al nuovo modello
   - Sostituisce `FROM` nel Modelfile con il modello base scelto
   - Invia a `POST /api/create_model`
5. **Ollama Models** — Lista modelli disponibili con refresh
6. **Modelfile Collection** — Lista manifesti con apertura in workspace

#### Flusso di Creazione Modello

```
1. GET /api/get_file → legge Modelfile selezionato
2. replace(/^FROM .+$/m, `FROM ${baseModel}`) → personalizza modello base
3. POST /api/create_model { name, modelfile } → Ollama
4. GET /api/ollama_models → refresh lista
```

---

## 4. 📁 Struttura Dati

### 4.1 Knowledge Base (`data/`)

```
data/<topic_id>/
├── <NN>_nome_modulo/
│   ├── teoria/         → File .md di teoria
│   ├── test/           → File .py di test (pytest)
│   ├── viz/            → File .html di visualizzazione (D3.js)
│   ├── docs/           → Documenti
│   └── whitepapers/    → Whitepaper (WHITEPAPER_*.md)
```

**Topic correnti in `modules_meta.json`:**

```json
{
    "topics": {
        "matematica": {
            "name": "Matematica",
            "description": "Argomenti matematici",
            "domain": "matematica",
            "modules": ["01", "02", "03"],
            "folder": "data/matematica"
        },
        "scratch": {
            "folder": "data/scratch",
            "modules": [],
            "name": "scratch",
            "description": ""
        }
    },
    "modules": {
        "01": "Esempio Modulo 1",
        "02": "Esempio Modulo 2",
        "03": "Esempio Modulo 3"
    }
}
```

### 4.2 File di Sistema

| File | Ruolo | Creato/Modificato da | Formato |
|------|-------|----------------------|---------|
| `tasks.json` | Roadmap task + notifiche | AI actions + manuale | JSON Array |
| `modules_meta.json` | Metadati topic/moduli con gerarchia | Server startup + CRUD moduli | JSON Object |
| `config.json` | Configurazione AI multi-provider | Config handler | JSON Object |
| `sandboxes.json` | Stato sandbox progetti | Sandbox manager | JSON Object |
| `package.json` | Dipendenze npm root | Manuale | JSON |

### 4.3 Struttura tasks.json

```json
[
    {
        "titolo": "Task di esempio",
        "descrizione": "Descrizione del task di esempio...",
        "status": "in_corso",
        "priorita": "critica",
        "moduli": ["01"],
        "id": 1779996110564,
        "notifiche": [
            {
        "da": "Agente",
        "messaggio": "Iniziata analisi. Creato file analisi.md",
                "timestamp": "2026-05-10T12:00:00"
            }
        ]
    }
]
```

**Regole del Sistema di Notifiche:**
1. ✅ **Obbligatorie**: ogni modifica a file, test o cambio stato DEVE generare una notifica
2. 🔒 **Immutabili**: una volta inserita, una notifica non viene mai modificata
3. 👤 **Tracciabili**: ogni notifica identifica l'agente che l'ha generata
4. 🌍 **Internazionali**: timestamp in formato ISO 8601

### 4.4 Manifesti — Agenti AI (3 file)

| File | Modello Base | Versione | Ruolo | Temperatura | Context Window |
|------|-------------|----------|-------|-------------|----------------|
| `sigma_architect.md` | llama3.2 (via sigma:latest) | v7.2 | Architetto Software + Ricerca | 0.55 | 16.384 |
| `math1.md` | llama3.2 | v6.0 | Ricerca Matematica | 0.7 | 8.192 |
| `code_architect.md` | sigma:latest | v1.0 | Full-Stack Developer | 0.3 | 16.384 |

**Struttura standard di un Modelfile:**
```
FROM <modello_base>

SYSTEM """
Identità + Regole + Protocollo + API Contract
"""

TEMPLATE """..."""

PARAMETER temperature <valore>
PARAMETER top_p <valore>
PARAMETER top_k <valore>
PARAMETER repeat_penalty <valore>
PARAMETER num_ctx <valore>
PARAMETER num_predict <valore>

PARAMETER stop "<tag>"
```

---

## 5. 🔄 Flussi Operativi Chiave

### 5.1 Ciclo di Vita di una Richiesta HTTP

```
1. Browser → GET http://localhost:8000/
2. route_get() → parsed.path == '' → _serve_static('')
3. Verifica se file esiste in sigma_studio/dist/
4. Se no → serve index.html (SPA fallback)
5. Frontend React si monta → fetch multipli:
   - GET /api/modules → data_handler.py
   - GET /api/tasks → task_handler.py
   - GET /api/list_manifesti → data_handler.py
   - GET /api/topics → data_handler.py
6. Interazione utente → chiamate API POST/GET
```

### 5.2 Flusso Chat con Esecuzione Azioni

```
1. Utente: "Crea un file di teoria per il modulo 01"
2. Frontend → POST /api/chat (allow_actions: true)
3. chat_handler.py:
   a. Carica config AI + manifesto agente
   b. Costruisce system prompt:
      - Manifesto agente (identità, regole)
      - Action prompt (formato JSON obbligatorio)
      - Contesto: files aperti, struttura data/, tasks.json
   c. Invia a provider AI (Ollama, DeepSeek, ...)
   d. Riceve risposta → estrae JSON
4. JSON con azioni: {"response": "...", "actions": [...]}
5. execute_ai_actions() in task_handler.py:
   a. Per ogni azione: validazione modulo, path sandbox, esecuzione
   b. _add_action_notifications() → aggiorna tasks.json
6. Risultato: actions_log[] con success/fail per ogni azione
7. Frontend mostra risultato + azioni eseguite
```

### 5.3 Flusso Loop Autonomo

```
FASE 1 — PIANIFICAZIONE:
  AI analizza goal → crea task strutturati in tasks.json
  Ogni task: titolo, descrizione, priorità, moduli

FASE 2 — ESECUZIONE (per ogni task):
  Per ogni file da creare:
    - Verifica che il modulo esista (se no → create_module)
    - create_file nel path corretto
    - execute_ai_actions()
  Dopo ogni azione → update_task con notifica

FASE 3 — REPORT:
  Riepilogo: quanti file creati, quanti test passati, task completati
```

### 5.4 Flusso Plan → Act

```
1. Utente: "Aggiungi un footer alla app principale"
2. POST /api/chat/plan:
   AI analizza struttura progetto
   Produce piano: [{description, actions[]}]
3. Utente approva piano
4. POST /api/chat/execute_plan:
   Esegue ogni step in sequenza con SSE feedback
   Report: X file modificati, Y azioni riuscite
```

---

## 6. 🔐 Sicurezza

### 6.1 Path Traversal Protection

- Blocco di `..` in tutti i path di input
- Normalizzazione separatori per match consistente
- Whitelist esplicita di directory consentite

### 6.2 Sandbox Whitelist

```python
ALLOWED_PREFIXES = (
    'data/', 'manifesti/', 'scratch/',
    'sigma_studio/', 'core/', 'sigma_studio/src/'
)
ROOT_FILES = {'tasks.json', 'modules_meta.json', 'config.json',
              'sigma_server.py', 'README.md', 'package.json'}
```

### 6.3 Module Structure Validation

```python
_ALLOWED_MODULE_SECTIONS = frozenset({
    'teoria', 'test', 'viz', 'docs', 'whitepapers',
})
# ❌ Qualsiasi altra cartella dentro un modulo è VIETATA
```

### 6.4 Auto-Wrapping Modulo

```python
def _ensure_module_structure(path):
    # data/topic/sezione/file → data/topic/01_base/sezione/file
```

### 6.5 API Key Security

```python
# config GET oscura le chiavi API
safe_cfg['providers'][pk] = {k: v for k, v in pv.items() if k != 'api_key'}
safe_cfg['providers'][pk]['has_api_key'] = bool(pv.get('api_key'))
```

### 6.6 Subprocess Safety

- Timeout obbligatorio (30-120s)
- `capture_output=True`, `text=True`
- `encoding='utf-8', errors='replace'`
- Directory limitate per `run_terminal`

### 6.7 Altre Protezioni

- **Model name validation**: regex `^[a-zA-Z0-9_-]+$`
- **Upload folder check**: no `..` in folder/filename
- **Temporary files**: `tempfile.mkdtemp()` + `shutil.rmtree()` cleanup
- **Graceful shutdown**: signal handler per SIGINT/SIGTERM

---

## 7. 📦 Metriche del Progetto

| Componente | File | Righe di Codice |
|-----------|------|----------------|
| **Backend** | `sigma_server.py` | 248 |
| **Moduli Core** | 10 file in `core/` | ~3.500 |
| **Frontend** | Componenti vari | ~5.000+ |
| **Chat Core** | `useChatCore.js` | 667 |
| **MappaArgomenti** | Componente D3 | 1.264 |
| **Manifesti Gallery** | Componente | 400 |
| **Manifesti** | 3 Modelfile | ~700 |
| **Configurazione** | JSON, CSS, config | ~500 |
| **Backend Totale** | — | ~4.300 |
| **Frontend Totale** | — | ~6.500 |
| **TOTALE PROGETTO** | — | **~11.000+** |

---

## 8. 🧩 Diagramma delle Dipendenze

```
sigma_server.py
  ├── core/sandbox.py          ← Validazione path
  ├── core/api_router.py        ← Routing endpoint
  ├── core/data_handler.py      ← Moduli, topics, knowledge DB
  ├── core/module_handler.py    ← CRUD topic/modulo
  ├── core/file_handler.py      ← CRUD file + upload
  ├── core/task_handler.py      ← Esecuzione azioni AI
  ├── core/config_handler.py    ← Config AI + modelli Ollama
  ├── core/ai_providers.py      ← Chiamate AI multi-provider
  ├── core/chat_handler.py      ← Chat orchestration
  │     └── core/task_handler.py
  │     └── core/ai_providers.py
  ├── core/loop_handler.py      ← Loop autonomo
  │     └── core/task_handler.py
  │     └── core/ai_providers.py
  ├── core/execute_loop.py      ← Loop esecutivo
  │     └── core/task_handler.py
  │     └── core/ai_providers.py
  ├── core/plan_handler.py      ← Plan → Act
  │     └── core/task_handler.py
  │     └── core/chat_handler.py
  └── core/sandbox_manager.py   ← Ambienti virtuali
```

```
Frontend (React 19 + Vite)
  ├── App.jsx                   ← Orchestratore
  │     ├── useModules          ← fetch /api/modules
  │     ├── useTasks            ← fetch /api/tasks
  │     ├── useTabs             ← Gestione tab interni
  │     └── useToast            ← Notifiche toast
  ├── ChatPanel
  │     └── ChatFloatingPanel
  │           └── useChatCore   ← Logica chat centrale
  │                 ├── chatStorage       ← Session/localStorage
  │                 └── modelProviderMap  ← Routing provider
  ├── MappaArgomenti            ← D3.js force graph
  └── ManifestiGallery          ← AI Model Lab
```

---

## 9. 🔍 Endpoint per Tipo di Dato

### Topics & Moduli

| Azione | Endpoint | Descrizione |
|--------|----------|-------------|
| Lista topics | `GET /api/topics` | Argomenti con gerarchia |
| Lista moduli | `GET /api/modules` | Moduli con file per sezione |
| Crea topic | `POST /api/create_topic` | Nuovo argomento |
| Aggiorna topic | `POST /api/update_topic` | Modifica metadati |
| Elimina topic | `POST /api/delete_topic` | Rimuove topic e moduli |
| Crea modulo | `POST /api/create_module` | Nuovo modulo con 5 sezioni |
| Elimina modulo | `POST /api/delete_module` | Rimuove modulo |
| Rinomina modulo | `POST /api/update_module` | Modifica nome/numero |

### File

| Azione | Endpoint | Descrizione |
|--------|----------|-------------|
| Leggi file | `GET /api/get_file?path=` | Contenuto file |
| Crea file | `POST /api/create_file` | Crea/sovrascrive |
| Elimina file | `POST /api/delete_file` | Rimuove file |
| Upload file | `POST /api/upload_file` | Multipart upload |
| Esegui test | `POST /api/run_test` | Script Python/Node |

### AI & Chat

| Azione | Endpoint | Descrizione |
|--------|----------|-------------|
| Chat | `POST /api/chat` | 4 modalità operative |
| Loop autonomo | `POST /api/chat/loop` | Task-driven loop |
| Execute loop | `POST /api/chat/execute` | Feedback loop |
| Plan | `POST /api/chat/plan` | Genera piano strutturato |
| Execute plan | `POST /api/chat/execute_plan` | Esegue piano |

### Configurazione

| Azione | Endpoint | Descrizione |
|--------|----------|-------------|
| Get config | `GET /api/config` | Config AI (senza API key) |
| Set config | `POST /api/config` | Aggiorna configurazione |
| Lista modelli | `GET /api/ollama_models` | Modelli Ollama installati |
| Crea modello | `POST /api/create_model` | Crea da Modelfile |

### Sandbox

| Azione | Endpoint | Descrizione |
|--------|----------|-------------|
| Crea | `POST /api/sandbox/create` | Nuovo progetto isolato |
| Esegui | `POST /api/sandbox/run` | Comando in sandbox |
| Installa | `POST /api/sandbox/install` | Pacchetto pip/npm |
| Lista | `GET /api/sandbox/list` | Sandbox attive |
| Distruggi | `POST /api/sandbox/destroy` | Pulisce sandbox |

---

## 10. 🛠️ Verbose Debugging

Il backend utilizza `print()` per debug logging:

```python
print(f"[SIGMA_CHAT_DEBUG] allow_actions={allow_actions}", flush=True)
print(f"[SIGMA_CHAT_DEBUG] AI response cleaned: {clean_response[:2000]}", flush=True)
print(f"[SIGMA_CHAT_DEBUG] JSON parsed. actions={parsed.get('actions', [])}", flush=True)
print(f"[LOOP_DEBUG] Calling AI for task: {task['titolo']}", flush=True)
```

I log vengono stampati sulla console del server e sono visibili nel terminale dove viene eseguito `sigma_server.py`.

---

> *"Un sistema è ben progettato quando un'IA può capirlo senza istruzioni esterne."*
> *"Una notifica non lasciata è un'azione mai avvenuta."*
> *"Separa le responsabilità, componi i moduli, mantieni la sandbox."*
> — Principi Sigma