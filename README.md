<p align="center">
  <h1 align="center">🧬 Σ-SIGMA Studio</h1>
  <p align="center"><strong>AI-Native Platform for Cognitive Orchestration & Research Automation</strong></p>
  <p align="center">
    <a href="#"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License MIT"></a>
    <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="#"><img src="https://img.shields.io/badge/react-19-61DAFB.svg" alt="React 19"></a>
    <a href="#"><img src="https://img.shields.io/badge/ollama-ready-FF6F00.svg" alt="Ollama Ready"></a>
    <a href="#"><img src="https://img.shields.io/badge/ai-multi--provider-9B59B6.svg" alt="Multi-Provider AI"></a>
    <a href="#"><img src="https://img.shields.io/badge/status-v6.0--stable-success.svg" alt="v6.0 Stable"></a>
  </p>
</p>

---

## 🚀 Perché Sigma Studio è la Piattaforma che il Tuo Cervello (e la Tua AI) Stavano Aspettando

Sigma Studio non è un altro wiki. Non è un CMS. Non è un IDE qualunque.

**Sigma Studio è un motore di orchestrazione cognitiva** — un ambiente eseguibile dove l'intelligenza artificiale crea, verifica, documenta e organizza conoscenza, regolamentata da manifesti Modelfile che ne determinano il comportamento.

Immagina di avere un **team di agenti AI specializzati** (un matematico, un avvocato, un architetto software) che lavorano 24/7 sulla tua ricerca, lasciando traccia di ogni azione, testando ogni teorema, e costruendo una knowledge graph navigabile di tutto ciò che producono.

**Questo è Sigma Studio.**

### Cosa Lo Rende Unico?

| Caratteristica | Perché Cambia le Regole |
|:--------------|:------------------------|
| 🧠 **AI Multi-Provider** | Ollama (locale), DeepSeek, OpenAI, Anthropic, Groq, OpenRouter — scegli tu il cervello |
| 📜 **Manifesti Modelfile** | Ogni agente AI ha un "codice di condotta" scritto in Modelfile Ollama. Non istruzioni umane, ma contratti eseguibili |
| 🔬 **Ricerca Automatizzata** | L'AI esplora, dimostra, confuta e documenta — senza che tu muova un dito |
| 🏗️ **Full-Stack AI** | Dalla teoria accademica al software funzionante: teoremi → test → visualizzazioni D3.js → whitepaper |
| 🔒 **Sandbox Security** | Ogni operazione è confinata in path whitelist. Nessun agente tocca file di sistema |
| 📋 **Notifiche Obbligatorie** | Ogni azione è tracciata in `tasks.json`. Se non c'è notifica, non è successo |
| 🌐 **Knowledge Graph** | Visualizzazione D3.js delle correlazioni tra moduli, teoremi e agenti |
| 🧩 **Architettura Modulare** | Backend Python (sigma_server.py) + Frontend React 19 + AI multi-provider: tutto componibile |

### 🖼️ Dai Un'occhiata

<p align="center">
  <img src="screenshots/dashboard.svg" alt="Dashboard Sigma Studio — panoramica con grafo conoscenza e task" width="48%" />
  <img src="screenshots/chat.svg" alt="AI Chat — conversazione con agente Architetto in modalita Tutto Insieme" width="48%" />
</p>
<p align="center">
  <em>Dashboard con Knowledge Graph interattivo (sinistra) e Chat AI con agente specializzato (destra).</em>
</p>

<p align="center">
  <img src="screenshots/editor.svg" alt="Sigma Lab Editor — modifica di un teorema con test e visualizzazioni correlate" width="70%" />
</p>
<p align="center">
  <em>Sigma Lab Editor: navigazione moduli, editing Markdown e correlazione automatica con test e visualizzazioni D3.js.</em>
</p>

---

## 🏗️ Architettura del Sistema — Tre Strati, Un Ecosistema

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Σ-SIGMA STUDIO v6                                           │
│                                                                                               │
│  ┌──────────────────────────┐     ┌───────────────────┐    ┌───────────────────────────────┐  │
│  │    sigma_server.py       │     │  sigma_studio/    │    │  manifesti/                   │  │
│  │    (Backend Python)      │◄──► │  (Frontend React) │    │  (Modelfile Ollama)           │  │
│  │                          │     │                   │    │                               │  │
│  │  • API REST (~18 endpnt) │     │  • Vite + React 19│    │  • agente0.md (Architetto)    │  │
│  │  • core/sandbox.py       │     │  • Proxy /api →   │    │  • model.md (altro modello)   │  │
│  │  • core/ai_providers.py  │     │    localhost:8000 │    │                               │  │
│  │  • Multi-provider AI     │     │  • Componenti:    │    └───────────────────────────────┘  │
│  │  • Path whitelist sandbox│     │    App, Sidebar,  │                                       │
│  │  • Build automatico      │     │    Workspace,     │                                       │
│  │    frontend a ogni avvio │     │    Dashboard,     │                                       │
│  │  • Threaded server       │     │    ChatPanel,     │                                       │
│  │  • Ollama integration    │     │    AIConfig,      │                                       │
│  │  • Model creation API    │     │    SigmaLabEditor │                                       │
│  └──────────┬───────────────┘     └──────────────────┘                                        │
│             │                                                                                 │
│             ▼                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐         │
│  │                      data/  (Knowledge Base Repository)                          │         │
│  │  ┌────────────────────────┐  ┌───────────────────┐  ┌───────────────────────┐    │         │
│  │  │ topic_1/               │  │ topic_2/          │  │ topic_3/              │    │         │
│  │  │ (Attivo, 2+ moduli)    │  │ (Bozza)           │  │ (Bozza, padre)        │    │         │
│  │  └────────────────────────┘  └───────────────────┘  └───────────────────────┘    │         │
│  └──────────────────────────────────────────────────────────────────────────────────┘         │
│                                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐        │
│  │              core/  (Moduli Backend — Separation of Concerns)                     │        │
│  │  sandbox.py        │  ai_providers.py    │  chat_handler.py    │  api_router.py   │        │
│  │  • Path validation │  • Config loading   │  • Chat orchestration│  • Route mapping│        │
│  │  • Sandbox rules   │  • Provider resolver│  • Planning modes    │                 │        │
│  │                    │  • API calls        │  • Loop handler      │                 │        │
│  └───────────────────────────────────────────────────────────────────────────────────┘        │
│                                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐         │
│  │              File di Sistema (Project Root)                                      │         │
│  │  tasks.json  │  modules_meta.json  │  config.json  │  package.json               │         │
│  └──────────────────────────────────────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Regole Architetturali Fondamentali

1. **Sandbox**: I file creati dall'API devono stare dentro `data/`, `manifesti/`, `sigma_studio/src/`, `scratch/`
2. **Path Whitelist**: Gestita da `core/sandbox.py` — solo directory autorizzate + file root specifici
3. **Build Automatica**: All'avvio, `sigma_server.py` esegue `npm run build` in `sigma_studio/`
4. **Metadati Centrali**: `modules_meta.json` è l'unica fonte di verità per correlazioni tra file
5. **Niente Dati nel Frontend**: Il frontend React è "stupido" — fa fetch da `/api/*`
6. **Manifesti Modelfile**: Gli agenti sono definiti come Modelfile Ollama in `manifesti/`
7. **Notifiche Obbligatorie**: Ogni operazione IA deve essere registrata in `tasks.json` con notifica

---

## ⚙️ Quick Start — Da Zero a Produttivo in 2 Minuti

### Prerequisiti

- **Python 3.10+**
- **Node.js / npm**
- **Ollama** (per AI locale — [scarica qui](https://ollama.com))

### Setup

```bash
# 1. Clona il repository
git clone https://github.com/your-org/sigma-studio.git
cd sigma-studio

# 2. Installa dipendenze Python
pip install -r requirements-backend.txt

# 3. Installa dipendenze frontend
cd sigma_studio && npm install && cd ..

# 4. Avvia il backend (builda automaticamente il frontend)
python sigma_server.py

# 5. (Opzionale) Avvia frontend in modalità sviluppo
cd sigma_studio && npm run dev
```

Il backend è ora attivo su **http://localhost:8000** e il frontend su **http://localhost:5173**.

### Verifica Rapida

```bash
# Verifica moduli core
python -c "from core.sandbox import is_path_allowed; from core.ai_providers import load_ai_config; print('✅ Sistema OK')"

# Verifica API
curl http://localhost:8000/api/tasks

# Crea un modello Ollama da un manifesto
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d '{"name": "agente0", "modelfile": "FROM llama3.2\nSYSTEM \"\"\"Sei un architetto software...\"\"\""}'
```

---

## 🧠 Sistema AI Multi-Provider — Il Cervello che Scegli Tu

Sigma Studio supporta **6 provider AI** configurabili dinamicamente via `config.json`:

| Provider | Tipo | Setup |
|:---------|:-----|:-------|
| **Ollama** 🦙 | Locale (gratuito) | `http://localhost:11434` |
| **DeepSeek** 🔍 | Cloud API | `API Key` |
| **OpenAI** 🤖 | Cloud API | `API Key` |
| **Anthropic (Claude)** 🟣 | Cloud API | `API Key` |
| **Groq** ⚡ | Cloud API | `API Key` |
| **OpenRouter** 🌐 | Cloud API (multi-modello) | `API Key` |

### Configurazione (config.json)

```json
{
  "ai": {
    "active_provider": "ollama",
    "active_model": "llama3.2",
    "providers": {
      "ollama": {
        "label": "Ollama (Locale)",
        "endpoint": "http://localhost:11434/api/chat",
        "model": "llama3.2",
        "temperature": 0.7,
        "max_tokens": 4096
      },
      "deepseek": {
        "label": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "api_key": "<YOUR_API_KEY>",
        "model": "deepseek-chat"
      }
    }
  }
}
```

### 4 Modalità Operative della Chat AI (Ottimizzate)

> Principio Sigma: **"Una notifica non lasciata è un'azione mai avvenuta."**  
> Ogni azione eseguita genera automaticamente una notifica in `tasks.json`.

| Modalità | Parametri Backend | Cosa Fa | Notifiche? |
|:---------|:-----------------|:--------|:-----------|
| 💬 **Chiedi** | `allow_actions=false` | L'IA risponde senza modificare nulla | Nessuna (solo chat) |
| 📋 **Pianifica** | `planning_mode=true` | Analizza un obiettivo e crea task nella Roadmap | ✅ Ogni task riceve notifica di creazione |
| ⚡ **Esegui** | `allow_actions=true` | L'IA crea, modifica o elimina file. **Sostituisce le vecchie modalità "Modifica" e "Tutto Insieme"** | ✅ **Automatiche**: ogni azione file (crea/modifica/elimina) genera notifica nel task attivo |
| ✅ **Completa Task** | `execute_task_id` + `allow_actions=true` | Esegue un task specifico dalla Roadmap, modifica i file necessari e lo marca completato | ✅ Notifiche per ogni azione + marcatura completamento |

---

## 📜 Sistema dei Manifesti — Agenti AI con Personalità

Gli agenti AI non sono scatole nere. Sono definiti da **Modelfile Ollama** che specificano esattamente:
- **Identità**: "Sei un matematico specializzato in teoria dei numeri..."
- **Regole**: "Non modificare mai file fuori da `data/`..."
- **Protocollo**: "Prima di agire, analizza il contesto..."
- **Parametri**: Temperatura, context window, template di conversazione

### Agenti Disponibili

| Agente | Modello Base | Versione | Ruolo |
|:-------|:-------------|:---------|:-------|
| `agente0.md` | llama3.2 | **v6.0** | Architetto software — full-stack engineer, orchestratore principale |
| `math1.md` | llama3.2 | v5.0 | Assistente di ricerca matematica — template per nuovi agenti |

### Crea un Nuovo Agente in 30 Secondi

```bash
# 1. Crea un file manifesto
cat > manifesti/mio_agente.md << 'EOF'
FROM llama3.2
SYSTEM """
Sei un agente specializzato in biologia molecolare...
Regole:
- Non modificare file fuori da data/biologia/
- Usa esclusivamente provider Ollama per la ricerca
- Ogni scoperta deve generare una notifica in tasks.json
"""
PARAMETER temperature 0.3
PARAMETER num_ctx 32768
EOF

# 2. Carica il modello in Ollama
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"mio_agente\", \"modelfile\": \"$(cat manifesti/mio_agente.md)\"}"
```

---

## 📂 Struttura del Progetto — Tutto al Suo Posto

```
Sigma_Studio/
│
├── sigma_server.py                 ← Backend Python — API REST + AI orchestration
├── tasks.json                      ← Roadmap eseguibile + archivio notifiche
├── modules_meta.json               ← Grafo di conoscenza (correlazioni tra file)
├── config.json                     ← Configurazione AI multi-provider
├── package.json                    ← Script npm root
├── .gitignore                      ← Ignora node_modules, .env, dist, data/
├── LICENSE                         ← MIT License
├── README.md                       ← Questo file (v6.0 — ibrido marketing + tecnico)
│
├── core/                           ← Moduli backend (separation of concerns)
│   ├── __init__.py
│   ├── sandbox.py                  ← Path validation e whitelist
│   ├── ai_providers.py             ← Config + provider resolver + API calls
│   ├── api_router.py               ← Route mapping HTTP
│   ├── chat_handler.py             ← Chat orchestration + planning modes
│   ├── config_handler.py           ← Config CRUD
│   ├── data_handler.py             ← Data operations
│   ├── file_handler.py             ← File CRUD + sandbox
│   ├── loop_handler.py             ← AI action loop
│   ├── module_handler.py           ← Module CRUD
│   └── task_handler.py             ← Task CRUD
│
├── manifesti/                      ← Modelfile Ollama — identità degli agenti AI
│   ├── agente0.md                  ← Architetto Software v6.0
│   └── math1.md                    ← Matematico v5.0
│
├── sigma_studio/                   ← Frontend React 19 (Vite)
│   ├── index.html                  ← Entry point
│   ├── vite.config.js              ← Proxy /api/* → localhost:8000
│   ├── package.json                ← Dipendenze React/Vite/D3/KaTeX/Mermaid
│   ├── eslint.config.js            ← ESLint config
│   ├── public/                     ← Asset statici
│   └── src/
│       ├── main.jsx                ← Mount React (StrictMode)
│       ├── index.css               ← Tema scuro glass-morphism
│       ├── App.jsx                 ← Orchestratore stato globale
│       ├── styles/                 ← Fogli di stile modulari
│       └── components/
│           ├── Sidebar.jsx         ← Navigazione laterale
│           ├── Workspace.jsx       ← Tab system centrale
│           ├── WelcomeDashboard.jsx← Homepage
│           ├── Dashboard.jsx       ← Roadmap cards
│           ├── Modals.jsx          ← CRUD modali
│           ├── AIConfig.jsx        ← Configurazione provider AI
│           ├── Chat/               ← Chat AI (4 modalità operative)
│           ├── SigmaLab/           ← Editor multi-formato
│           └── Workspace/          ← Sotto-componenti tab
│
├── data/                           ← Knowledge Base (sandbox per agenti AI)
│   ├── example_topic_1/            ← Primo argomento di esempio
│   ├── example_topic_2/            ← Secondo argomento (bozza)
│   └── example_topic_3/            ← Terzo argomento (bozza, padre)
│
└── scratch/                        ← Area temporanea per esperimenti
```

### Struttura di un Modulo

```
data/<topic>/<NN_nome_modulo>/
├── docs/                           ← Whitepaper e documenti immutabili
├── teoria/                         ← Teoremi, lemmi, dimostrazioni
├── test/                           ← Test Python (pytest) — verifica computazionale
└── viz/                            ← Visualizzazioni HTML/D3.js
```

---

## 📋 Ciclo di Vita dei Task e Sistema di Notifiche

Ogni azione dell'AI è tracciata in `tasks.json` con un sistema di notifiche obbligatorie:

```json
{
  "titolo": "Esempio di Task",
  "status": "in_corso",
  "priorita": "critica",
  "moduli": ["01"],
  "id": 1779996110564,
  "notifiche": [
    {
      "da": "Agente-1",
      "messaggio": "Iniziata analisi. Creato file analisi.md",
      "timestamp": "2026-05-10T12:00:00"
    }
  ]
}
```

**Regole del Sistema di Notifiche:**
1. ✅ **Obbligatorie**: ogni modifica a file, test o cambio stato DEVE generare una notifica
2. 🔒 **Immutabili**: una volta inserita, una notifica non viene mai modificata
3. 👤 **Tracciabili**: ogni notifica identifica l'agente che l'ha generata
4. 🌍 **Internazionali**: timestamp in formato ISO 8601

---

## 🛠️ API Reference — Endpoint Principali

| Metodo | Endpoint | Funzione |
|:-------|:---------|:---------|
| `GET` | `/api/modules` | Lista moduli con file per categoria |
| `GET` | `/api/topics` | Argomenti con gerarchia parent/child |
| `GET` | `/api/tasks` | Roadmap + notifiche |
| `GET` | `/api/get_file?path=...` | Legge file (sandbox-safe) |
| `GET` | `/api/list_manifesti` | Elenca agenti AI disponibili |
| `GET` | `/api/config` | Config AI (senza API key) |
| `GET` | `/api/ollama_models` | Modelli Ollama installati |
| `POST` | `/api/tasks` | Salva tasks.json |
| `POST` | `/api/create_file` | Crea/scrive file |
| `POST` | `/api/chat` | Chat con AI (supporta 4 modalità) |
| `POST` | `/api/create_model` | Crea modello Ollama da Modelfile |
| `POST` | `/api/run_test` | Esegue script Python/Node |
| `POST` | `/api/create_topic` | Nuovo argomento di ricerca |
| `POST` | `/api/create_module` | Nuovo modulo in un argomento |

---

## 🧪 Workflow Completo: Dalla Teoria al Software

Ecco come Sigma Studio trasforma un'ipotesi in un prodotto validato:

```
1. 📥 INPUT TEORICO
   L'utente carica introduzione.md in data/esempio/01_modulo/teoria/

2. 📋 PIANIFICAZIONE (AI Mode: plan)
   L'AI analizza e genera task in tasks.json:
   - Task 1: Scrivere codice di verifica
   - Task 2: Generare analisi visuale

3. ✅ ESECUZIONE (AI Mode: complete)
   L'AI esegue i test e salva risultati in test/

4. 📊 VISUALIZZAZIONE
   I test alimentano la generazione di HTML/D3.js in viz/

5. 📝 DOCUMENTAZIONE
   Whitepaper aggiornato in docs/ con risultati e scoperte

6. 🔗 KNOWLEDGE GRAPH
   modules_meta.json aggiornato con nuove correlazioni
```

---

## 🌍 Comunità e Contributi

Sigma Studio è **open source** con licenza **MIT**. Puoi:
- 🐛 **Segnalare bug** — apri una issue su GitHub
- 💡 **Proporre feature** — discussioni e pull request benvenute
- 🧠 **Creare nuovi agenti AI** — i manifesti Modelfile sono facili da scrivere
- 📚 **Aggiungere argomenti di ricerca** — la struttura modulare lo rende immediato

---

## 📜 Licenza

```
MIT License

Copyright (c) 2026 Diego Saitta

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

> *"Un sistema è ben progettato quando un'IA può capirlo senza istruzioni esterne."*
> *"Un teorema non è dimostrato finché non è stato confutato, corretto, e confutato di nuovo."*
> *"Una notifica non lasciata è un'azione mai avvenuta."*
> *"Separa le responsabilità, componi i moduli, mantieni la sandbox."*
> — Principi Sigma

---

<p align="center">
  <strong>⭐ Se Sigma Studio ti ha cambiato il modo di fare ricerca, lascia una stella su GitHub!</strong>
</p>