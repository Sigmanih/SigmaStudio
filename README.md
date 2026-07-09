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
    <a href="#"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  </p>
</p>

---

## 🚀 What is Sigma Studio?

**Sigma Studio is a cognitive orchestration engine** — an executable environment where AI agents create, verify, document, and organize knowledge, governed by Modelfile manifests that define their behavior.

Imagine a **team of specialized AI agents** (a mathematician, an architect, a tester) working 24/7 on your research, tracking every action, testing every theorem, and building a navigable knowledge graph of everything they produce.

**This is Sigma Studio.**

### Key Differentiators

| Feature | Why It Matters |
|:--------|:---------------|
| 🧠 **Multi-Provider AI** | Ollama (local), DeepSeek, OpenAI, Anthropic, Groq, OpenRouter — you choose the brain |
| 📜 **Manifesto System** | Every agent has a "code of conduct" written as an Ollama Modelfile. Not human instructions — executable contracts |
| 🔬 **Automated Research** | AI explores, proves, refutes, and documents — without you lifting a finger |
| 🏗️ **Full-Stack AI** | From academic theory to working software: theorems → tests → D3.js visualizations → whitepapers |
| 🔒 **Sandbox Security** | Every operation is confined to whitelisted paths. No agent touches system files |
| 🧩 **Modular Architecture** | Python backend + React 19 frontend + Multi-provider AI: fully composable |

---

## 🖼️ Screenshots

<p align="center">
  <img src="screenshots/dashboard.svg" alt="Dashboard — Navigator with Knowledge Graph and task overview" width="48%" />
  <img src="screenshots/chat.svg" alt="Chat — Multi-agent conversation with Architect mode" width="48%" />
</p>
<p align="center">
  <em>Interactive Knowledge Graph (left) and AI Chat with specialized agents (right).</em>
</p>

<p align="center">
  <img src="screenshots/pipeline.svg" alt="Pipeline Designer — DAG-based multi-agent pipeline execution" width="70%" />
</p>
<p align="center">
  <em>Pipeline Designer: define, execute and review multi-agent DAG pipelines with feedback loops.</em>
</p>

<p align="center">
  <img src="screenshots/editor.svg" alt="Sigma Lab Editor — Module editing with real-time preview" width="70%" />
</p>
<p align="center">
  <em>Sigma Lab Editor: navigate modules, edit Markdown with live preview, manage visualizations.</em>
</p>

---

## ⚙️ Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js / npm**
- **Ollama** (for local AI — [download here](https://ollama.com))

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/sigma-studio.git
cd sigma-studio

# 2. Install Python dependencies
pip install -r requirements-backend.txt

# 3. Install frontend dependencies
cd sigma_studio && npm install && cd ..

# 4. Start the backend (automatically builds frontend)
python sigma_server.py

# 5. (Optional) Start frontend in dev mode
cd sigma_studio && npm run dev
```

The backend is now live at **http://localhost:8000** and the frontend at **http://localhost:5173**.

### Quick Verification

```bash
# Verify core modules
python -c "from core.sandbox import is_path_allowed; from core.ai_providers import load_ai_config; print('✅ System OK')"

# Verify API
curl http://localhost:8000/api/tasks

# Create an Ollama model from a manifesto
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d '{"name": "agente0", "modelfile": "FROM llama3.2\nSYSTEM \"\"\"You are a software architect...\"\"\""}'
```

---

## 🧠 Multi-Provider AI

Sigma Studio supports **6 AI providers** dynamically configurable via `config.json`:

| Provider | Type | Setup |
|:---------|:-----|:-------|
| **Ollama** 🦙 | Local (free) | `http://localhost:11434` |
| **DeepSeek** 🔍 | Cloud API | `API Key` |
| **OpenAI** 🤖 | Cloud API | `API Key` |
| **Anthropic (Claude)** 🟣 | Cloud API | `API Key` |
| **Groq** ⚡ | Cloud API | `API Key` |
| **OpenRouter** 🌐 | Cloud API (multi-model) | `API Key` |

### 4 Chat Modes

> Sigma Principle: **"A notification not left is an action that never happened."**

| Mode | Backend Params | What It Does | Notifications? |
|:-----|:--------------|:-------------|:---------------|
| 💬 **Ask** | `allow_actions=false` | AI responds without modifying anything | None (chat only) |
| 📋 **Plan** | `planning_mode=true` | Analyzes a goal and creates tasks in the Roadmap | ✅ Each task gets a creation notification |
| ⚡ **Execute** | `allow_actions=true` | AI creates, modifies, or deletes files | ✅ **Automatic**: every file action generates a notification |
| ✅ **Complete Task** | `execute_task_id` + `allow_actions=true` | Executes a specific task from the Roadmap and marks it done | ✅ Notifications for every action + completion marking |

---

## 📜 Manifesto System

AI agents aren't black boxes. They're defined by **Ollama Modelfiles** that specify:
- **Identity**: "You are a mathematician specialized in number theory..."
- **Rules**: "Never modify files outside `data/`..."
- **Protocol**: "Before acting, analyze the context..."
- **Parameters**: Temperature, context window, conversation template

### Available Agents

| Agent | Base Model | Version | Role |
|:------|:-----------|:--------|:-----|
| `agente0.md` | llama3.2 | **v6.0** | Software Architect — full-stack engineer, main orchestrator |
| `math1.md` | llama3.2 | v5.0 | Math Research Assistant — template for new agents |

### Create a New Agent in 30 Seconds

```bash
# 1. Create a manifesto file
cat > manifesti/my_agent.md << 'EOF'
FROM llama3.2
SYSTEM """
You are an agent specialized in molecular biology...
Rules:
- Only modify files within data/biology/
- Use exclusively Ollama provider for research
- Every discovery must generate a notification in tasks.json
"""
PARAMETER temperature 0.3
PARAMETER num_ctx 32768
EOF

# 2. Load the model into Ollama
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"my_agent\", \"modelfile\": \"$(cat manifesti/my_agent.md)\"}"
```

---

## 🏛️ Architecture

```
Sigma_Studio/
│
├── sigma_server.py                 ← Python Backend — REST API + AI orchestration
├── config.json                     ← Multi-provider AI configuration
├── .gitignore                      ← Ignores node_modules, .env, dist, data/
├── LICENSE                         ← MIT License
├── README.md                       ← This file
│
├── core/                           ← Backend modules (separation of concerns)
│   ├── sandbox.py                  ← Path validation & whitelist
│   ├── ai_providers.py             ← Config + provider resolver + API calls
│   ├── api_router.py               ← HTTP route mapping
│   ├── chat_handler.py             ← Chat orchestration + planning modes
│   ├── config_handler.py           ← Config CRUD
│   ├── data_handler.py             ← Data operations
│   ├── file_handler.py             ← File CRUD + sandbox
│   ├── loop_handler.py             ← AI action loop
│   ├── pipeline_engine.py          ← DAG pipeline execution engine
│   ├── context_broker.py           ← SQLite shared context between agents
│   ├── agent_orchestrator.py       ← Multi-agent parallel orchestration
│   ├── agent_registry.py           ← Agent metadata management
│   ├── module_handler.py           ← Module CRUD
│   └── task_handler.py             ← Task CRUD + notifications
│
├── sigma_studio/                   ← React 19 Frontend (Vite)
│   ├── index.html                  ← Entry point
│   ├── vite.config.js              ← Proxy /api/* → localhost:8000
│   └── src/
│       ├── main.jsx                ← React mount (StrictMode)
│       ├── App.jsx                 ← Global state orchestrator
│       ├── components/
│       │   ├── Sidebar.jsx         ← Module tree navigation
│       │   ├── Workspace.jsx       ← Central tab system
│       │   ├── Dashboard.jsx       ← Roadmap task cards
│       │   ├── Chat/               ← AI Chat (4 operating modes)
│       │   │   ├── core/           ← Hooks: useChatCore, useResearchPipeline, usePipelineDesigner
│       │   │   └── layouts/        ← Floating panel & workspace tab
│       │   ├── SigmaLab/           ← Multi-format editor (Markdown, D3 viz, code runner)
│       │   └── Workspace/          ← Sub-components (ManifestiGallery, ModuleView, etc.)
│       └── styles/                 ← Modular CSS (glass-morphism dark theme)
│
├── data/                           ← Knowledge Base (sandbox for AI agents)
└── scratch/                        ← Temporary workspace for experiments
```

---

## 🔗 API Reference

| Method | Endpoint | Function |
|:-------|:---------|:---------|
| `GET` | `/api/modules` | List modules with files by category |
| `GET` | `/api/topics` | Topics with parent/child hierarchy |
| `GET` | `/api/tasks` | Roadmap + notifications |
| `GET` | `/api/get_file?path=...` | Read file (sandbox-safe) |
| `GET` | `/api/list_manifesti` | List available AI agents |
| `GET` | `/api/config` | AI config (without API keys) |
| `GET` | `/api/ollama_models` | Installed Ollama models |
| `POST` | `/api/tasks` | Save tasks.json |
| `POST` | `/api/create_file` | Create/overwrite file |
| `POST` | `/api/chat` | AI Chat (4 modes) |
| `POST` | `/api/chat/orchestrate` | Multi-agent orchestration |
| `POST` | `/api/chat/pipeline/start` | Start DAG pipeline execution |
| `POST` | `/api/create_model` | Create Ollama model from Modelfile |
| `POST` | `/api/run_test` | Execute Python/Node script |
| `POST` | `/api/create_topic` | New research topic |
| `POST` | `/api/create_module` | New module in a topic |

---

## 🤝 Contributing

Sigma Studio is **open source** under the **MIT license**. We welcome contributions of all kinds:

- 🐛 **Report bugs** — open a GitHub issue
- 💡 **Propose features** — discussions and PRs welcome
- 🧠 **Create new AI agents** — Modelfile manifests are easy to write
- 📚 **Add research topics** — the modular structure makes it immediate
- 🎨 **Improve UI/UX** — React 19 components are well-isolated
- 🔧 **Extend the backend** — new API endpoints, providers, sandbox features

### Development Setup

```bash
# Clone and install as above, then:
cd sigma_studio && npm run dev  # Hot-reload frontend
python sigma_server.py          # Auto-builds + serves on :8000
```

### Project Structure for Contributors

- `core/` — Python modules, each < 600 lines, single responsibility
- `sigma_studio/src/components/` — React components, one file per component
- `sigma_studio/src/hooks/` — Custom React hooks for data fetching
- `sigma_studio/src/styles/` — Modular CSS files per section

---

## 📜 License

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

> *"A system is well designed when an AI can understand it without external instructions."* 
> *"A theorem is not proven until it has been refuted, corrected, and refuted again."*
> *"A notification not left is an action that never happened."*
> *"Separate responsibilities, compose modules, maintain the sandbox."*
> — Sigma Principles

---

<p align="center">
  <strong>⭐ If Sigma Studio changed the way you do research, leave a star on GitHub!</strong>
</p>