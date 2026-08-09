<p align="center">
  <h1 align="center">🧬 Σ-SIGMA Studio</h1>
  <p align="center"><strong>AI-Native Platform for Cognitive Orchestration, Model Fine-Tuning & Multimodal Research Automation</strong></p>
  <p align="center">
    <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="#"><img src="https://img.shields.io/badge/react-19-61DAFB.svg" alt="React 19"></a>
    <a href="#"><img src="https://img.shields.io/badge/fastapi-0.100+-009688.svg" alt="FastAPI"></a>
    <a href="#"><img src="https://img.shields.io/badge/ollama-ready-FF6F00.svg" alt="Ollama Ready"></a>
    <a href="#"><img src="https://img.shields.io/badge/status-v8.0--stable-success.svg" alt="v8.0 Stable"></a>
  </p>
</p>

---

## 🚀 Overview

**Sigma Studio** is an open-source, executable platform for cognitive agent orchestration, model fine-tuning, automated research, and multimodal asset management. It pairs a **Python 3.10+ FastAPI backend** with a **React 19 + Vite 8 frontend**, providing a unified workspace where multi-agent teams interact through Modelfile manifests, Model Context Protocol (MCP) tools, and specialized lab environments.

### Key Implemented Capabilities

| Subsystem | Capabilities & Architecture |
|:---|:---|
| 🧠 **Multi-Provider AI Engine** | Integrates local **Ollama** models alongside remote APIs (**DeepSeek, OpenAI, Anthropic, Groq, OpenRouter**). Features a local intent router (`Ailo-152M`) for ~100ms fast task classification. |
| 📜 **Manifesto System** | Agent roles defined as Markdown Modelfiles (`manifesti/*.md`) specifying system contracts, domain boundaries, context windows, and operational constraints. |
| 🤖 **Multi-Agent Orchestration** | Dynamic DAG swarm planning (`dynamic_swarm.py`), parallel thread-pool execution, context sharing (`context_broker.py`), and continuous task execution loops. |
| 🔌 **MCP Server Hub** | 12 built-in MCP servers (Memory, Developer, Hardware, Training, Inference, Network, Benchmark, Creative, Home Assistant, Email, Messaging, Calendar) plus stdio client for external MCP servers. |
| 🏠 **Home Assistant Integration** | Native MCP server communicating via REST/WebSocket with Home Assistant instances for smart home state discovery, service execution, climate control, and automation triggering. |
| 🔬 **Training Lab & SLM Forge** | Fine-tuning via **Unsloth QLoRA, PEFT QLoRA, and Gradus FWE** (Functional Weight Engine). Includes dataset registration, automated hyperparameter tuning (Autopilot), GGUF quantization, and Ollama registration. |
| 📊 **Benchmark Engine** | Evaluates models on official benchmark suites (MMLU, GSM8K, HumanEval, ARC, BBH, etc.) with detailed JSONL sidecar logging and error review queues. |
| 🎨 **Creative Studio & Multimodal** | Text-to-Image, Img2Img, Background Removal (RemBG), SAM Segmentation, 3D Mesh Generation (GLB/OBJ), Headless Blender rendering, PBR material synthesis, and Video generation. |
| 🖼️ **Inline Chat & Workspace Viewer** | In-chat inline thumbnail previews for generated images, fullscreen glassmorphism Lightbox, and dedicated Workspace `ImageViewer` tab with zoom, pan, and checkerboard transparency. |
| 🔒 **Whitelisted Path Sandboxing** | Confines filesystem access to explicit whitelisted paths (`data/`, `manifesti/`, `scratch/`, `sigma_studio/`, `core/`) with shlex subprocess isolation and AST static code checking. |

> 📐 **Looking for comprehensive technical specifications?** Refer to **[`ARCHITECTURE.md`](ARCHITECTURE.md)** for detailed system component diagrams, API endpoint reference tables, data schemas, and internal module dependency graphs.

---

## 🛠️ Repository Structure

```text
Sigma_Studio/
├── sigma_server.py             # Server entrypoint (FastAPI / Uvicorn runner)
├── config.json                 # Production system config (Providers, MCP, Creative, Hardware)
├── config.example.json         # Configuration template
├── requirements.txt            # Python dependencies (FastAPI, PyTorch, Transformers, PEFT, etc.)
├── install_dependencies.bat    # Windows automated setup script (.venv, pip, npm build)
├── sigma_studio.bat            # Windows one-click launcher (Hardware env + server startup)
├── agents_meta.json            # Agent definitions, permitted topics, and usage statistics
├── modules_meta.json           # Auto-generated workspace module metadata cache
├── pytest.ini                  # Pytest runner configuration
├── ARCHITECTURE.md             # In-depth system architecture specification
├── README.md                   # Technical project overview and user guide
├── core/                       # Python Backend Modules
│   ├── fastapi_app.py          # FastAPI application definitions & static mounts
│   ├── api_router.py           # Central GET/POST HTTP routing dispatch table
│   ├── ai_providers.py         # Multi-provider AI interface (Ollama, OpenAI, DeepSeek, Anthropic, etc.)
│   ├── sandbox.py              # Whitelisted path security enforcer
│   ├── sandbox_manager.py      # Subprocess execution sandbox with timeout & AST validation
│   ├── router_trainer.py       # Local Ailo-152M intent router model trainer
│   ├── chat/                   # Chat runner, prompt builders, file extractors
│   ├── creative/               # Creative Studio (Asset Graph SQLite DB, Generators, Editors, 3D, Video)
│   ├── integrations/           # App launcher & skill toggles
│   ├── loop/                   # Autonomous continuous execution loop engine
│   ├── mcp/                    # MCP Hub, Governance policy, and 12 built-in MCP servers
│   ├── orchestration/          # Parallel thread-pool orchestrator & research sessions
│   ├── pipeline/               # Dynamic swarm DAG planner & self-healing runner
│   ├── training/               # Training Lab (Unsloth, QLoRA, Autopilot, Forge, Benchmarks, GPU telemetry)
│   └── tts/                    # Text-to-Speech engines (Kokoro, XTTS v2)
├── gradus/                     # Gradus Functional Weight Engine (FWE) codebook & weight generator
├── manifesti/                  # Agent Modelfile specifications (*.md)
├── data/                       # Workspace files (data/<topic>/<module>/<section>/<file>)
├── images/                     # System avatars and static assets
├── tests/                      # Automated test suite (Pytest)
└── sigma_studio/               # React 19 + Vite 8 Frontend Application
    ├── package.json            # Node.js dependencies & scripts
    ├── vite.config.js          # Vite config & API proxy settings
    ├── index.html              # HTML5 entrypoint & print stylesheet
    └── src/
        ├── App.jsx             # React root layout & state orchestrator
        ├── contexts/           # AppContext state provider
        ├── hooks/              # Custom hooks (useModules, useTasks, useTabs, useFileOps, etc.)
        ├── utils/              # markdownLatex.js unified renderer & simpleMarkdown.js
        └── components/         # UI Components
            ├── Workspace.jsx           # Main workspace tab manager
            ├── SigmaLab/               # SigmaLabEditor (MD, Python, Viz editor/preview)
            ├── Workspace/              # ImageViewer, ManifestiGallery, ModuleView, ResearchLabTab
            ├── Chat/                   # AgentMessage, MessageBubble, McpToolStrip, ImageLightbox
            ├── CreativeStudio/         # Generative AI Studio UI
            ├── TrainingLab/            # Fine-tuning, Autopilot & Benchmark UI
            ├── HardwareLab/            # Hardware monitoring & GPU process control
            └── McpHubTab.jsx           # MCP Server governance & JSON-RPC console
```

---

## ⚡ Prerequisites & Requirements

- **Operating System**: Windows 10/11 (primary supported OS with launch scripts) or Linux x86_64.
- **Python**: Python 3.10 or higher.
- **Node.js**: Node.js 18.0+ and npm 9.0+.
- **NVIDIA GPU (Recommended)**: CUDA 11.8 / 12.x compatible GPU with 8GB+ VRAM for local inference/fine-tuning.
- **Local AI Provider (Optional)**: [Ollama](https://ollama.ai/) installed and running locally on default port `11434`.

---

## ⚙️ Configuration & Installation

### Option A: One-Click Windows Setup (Recommended)

1. Clone the repository:
   ```cmd
   git clone https://github.com/Sigmanih/SigmaStudio.git
   cd Sigma_Studio
   ```
2. Copy the example configuration file:
   ```cmd
   copy config.example.json config.json
   ```
3. Run the installer script:
   ```cmd
   install_dependencies.bat
   ```
   *This script initializes the Python virtual environment (`.venv`), installs `requirements.txt`, and compiles the React frontend inside `sigma_studio/`.*

4. Launch Sigma Studio:
   ```cmd
   sigma_studio.bat
   ```
   *This script sets CUDA/Ollama environment variables, checks the build, and starts the FastAPI server on `http://localhost:8000`.*

---

### Option B: Manual Cross-Platform Setup

1. **Configure Environment**:
   ```bash
   cp config.example.json config.json
   ```
2. **Setup Python Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Build Frontend Bundle**:
   ```bash
   cd sigma_studio
   npm install
   npm run build
   cd ..
   ```
4. **Start Backend Server**:
   ```bash
   python sigma_server.py
   ```
   *Access the web application at `http://localhost:8000`.*

---

## 💻 Development Workflow

To run Sigma Studio with Vite frontend Hot-Module Replacement (HMR) during development:

1. Start the FastAPI backend server in Terminal 1:
   ```bash
   python sigma_server.py
   ```
2. Start the Vite development server in Terminal 2:
   ```bash
   cd sigma_studio
   npm run dev
   ```
3. Open `http://localhost:5173`. Vite proxies `/api` and `/web_explorer` requests directly to `http://localhost:8000`.

---

## 🔌 Model Context Protocol (MCP) Integration

Sigma Studio integrates a full MCP Hub supporting **12 built-in servers** and external third-party stdio servers.

### MCP Safety Policy Governance
- **`SAFE` Tools**: Read-only operations (memory recall, status probes, file reads) execute automatically.
- **`SENSITIVE` Tools**: Operations that modify state, write files, control hardware, or interact with external services (Home Assistant, Email, Telegram) park in a pending approval queue.
- **Human Approval**: Pending calls display banner notices in the chat UI (`McpToolStrip.jsx`). Operators can approve or reject calls via the `/api/mcp/approve` endpoint.

---

## 🏠 Home Assistant Integration

Sigma Studio natively connects to Home Assistant instances via the **HomeAssistant MCP Server** (`core/mcp/homeassistant_server.py`).

- **Protocol**: HTTP REST & WebSocket API (default target `http://localhost:8123`).
- **Authentication**: Long-Lived Access Token configured in `config.json` under `mcp.homeassistant.token`.
- **Supported Capabilities**:
  - Entity state listing (`ha_get_states`)
  - Service invocation (`ha_call_service`)
  - Historical state queries (`ha_get_history`)
  - Light control & color toggling (`ha_toggle_light`)
  - Climate / thermostat adjustments (`ha_set_climate`)
  - Automation triggering (`ha_trigger_automation`)
  - Live camera frame capture (`ha_get_camera_frame`)

---

## 🧪 Testing & Quality Assurance

Run the automated test suite using `pytest`:

```bash
# Run full backend test suite
pytest

# Run specific subsystem tests
pytest tests/test_fastapi_server.py
pytest tests/test_mcp_governance.py
pytest tests/test_training_jobs.py
```

---

## 🔒 Security & Privacy Notice

- **Sandboxed Operations**: All AI agent file creation, modification, and script execution are strictly bounded by `core/sandbox.py`. Access outside whitelisted project directories is blocked.
- **Network Exposure**: By default, `sigma_server.py` binds to `0.0.0.0:8000`. If deploying on a shared network, ensure firewall rules restrict port 8000 access as `/api/*` endpoints do not currently enforce bearer token authentication.
- **Secrets Protection**: Do not commit active API keys or JWT tokens inside `config.json`. Use environment variables (`HF_TOKEN`, `OPENAI_API_KEY`, etc.) or copy from `config.example.json`.

---

## 🗺️ Roadmap & Future Architecture

The following features are strategically planned and explicitly marked as **PLANNED** for future releases:

- [ ] **Docker & Docker Compose Packaging**: Official containerization manifests for zero-dependency Linux deployment.
- [ ] **CI/CD Pipeline Automation**: Automated GitHub Actions workflows for linting, pytest, and frontend builds.
- [ ] **Native ARM64 / Raspberry Pi 5 Optimization**: Specialized quantization and setup scripts for ARM64 single-board computers.
- [ ] **Bearer Token API Authentication**: Add JWT/Bearer token authorization headers to `/api/*` endpoints.
- [ ] **Multi-Node Distributed Swarms**: Distributed agent execution across multiple physical Sigma Studio nodes over gRPC/WebSocket.

---

## 📄 License

Dual-licensed under **GPL v3 / Commercial License**. See `LICENSE` for details.