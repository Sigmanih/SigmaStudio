<p align="center">
  <h1 align="center">🧬 Σ-SIGMA Studio</h1>
  <p align="center"><strong>Modular AI-Native Micro-Kernel for Cognitive Orchestration, Autonomous Multi-Agent Swarms & Dynamic Modular Ecosystem</strong></p>
  <p align="center">
    <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="#"><img src="https://img.shields.io/badge/react-19-61DAFB.svg" alt="React 19"></a>
    <a href="#"><img src="https://img.shields.io/badge/fastapi-0.100+-009688.svg" alt="FastAPI"></a>
    <a href="#"><img src="https://img.shields.io/badge/ollama-ready-FF6F00.svg" alt="Ollama Ready"></a>
    <a href="#"><img src="https://img.shields.io/badge/mcp-standard-00f2fe.svg" alt="Model Context Protocol"></a>
    <a href="#"><img src="https://img.shields.io/badge/architecture-modular--microkernel-success.svg" alt="Modular Micro-Kernel"></a>
  </p>
  <p align="center">
    <a href="README.md">🇬🇧 English</a> • <a href="README_IT.md">🇮🇹 Italiano</a> • <a href="https://github.com/Sigmanih/SigmaStudio-Moduli">📦 Modules Catalog</a>
  </p>
</p>

---

## 🚀 Overview

**Sigma Studio** is an open-source, executable platform engineered around a lightweight, sandboxed **Micro-Kernel** paired with a dynamic **Runtime Module Ecosystem**. It combines a high-performance **Python 3.10+ FastAPI backend** with an ultra-responsive **React 19 + Vite 8 frontend**.

Multi-agent teams interact through Modelfile manifests, Model Context Protocol (MCP) tools, and specialized lab environments installed on-demand from the official [**SigmaStudio-Moduli**](https://github.com/Sigmanih/SigmaStudio-Moduli) catalog.

```
+-------------------------------------------------------------------------+
|                        Σ-SIGMA STUDIO MICRO-KERNEL                       |
+-------------------------------------------------------------------------+
|  🧠 Multi-Provider Router  |  🤖 Multi-Agent DAG Swarm  |  🔌 Core MCP Hub   |
|  (Ollama, DeepSeek, OpenAI)|  (Dynamic Parallel Loops)  |  (6 Kernel Servers)|
+-------------------------------------------------------------------------+
|                    🏪 RUNTIME MODULE MARKETPLACE                        |
+-------------------------------------------------------------------------+
| 🎨 Creative Lab 3D/2D      | 🧠 Training Lab & Forge   | 🎙️ Voice Studio    |
| 🔬 Pipelines Lab & Swarm   | ⚡ Hardware & VRAM Telemetry| 🏠 Smart Domotica  |
| 📅 Roadmap & Task Audit    | 📊 Knowledge & Memory Graph | 📻 Hi-Fi Audio Lab |
+-------------------------------------------------------------------------+
```

---

## 🌟 Key Architecture & Capabilities

### 1. 🏛️ Watertight Modular Architecture (Micro-Kernel)
- **Zero-Bloat Core**: Unused labs or extensions are completely separated from the kernel codebase. Uninstalled modules do not load in memory, are hidden from the sidebar, and register zero static routes.
- **Dynamic Hot-Injection**: Modules are installed and uninstalled runtime via the built-in **Marketplace & Extensions Hub**, dynamically attaching FastAPI endpoints, React components, and MCP servers without rebooting.
- **Ultra-Fast Bundle**: Kernel frontend bundle compiles in **< 700ms** and weighs only **~1.1 MB**.

### 2. 🧠 Multi-Provider AI Inference Engine
- Native support for local **Ollama** models and external Cloud APIs (**DeepSeek, OpenAI, Anthropic Claude, Groq, OpenRouter**).
- Intelligent local intent router for rapid ~100ms task classification and autonomous model switching.

### 3. 🤖 Autonomous Multi-Agent Swarm Orchestration
- **Dynamic Swarm Planner**: Generates real-time Directed Acyclic Graph (DAG) execution plans tailored to complex, multi-step tasks.
- **Context Broker**: Shared episodic memory, tool trace passing, and parallel thread-pool worker dispatching.
- **Manifesto System**: Agent personas and system contracts defined as Markdown Modelfiles (`manifesti/*.md`).

### 4. 🔌 Model Context Protocol (MCP) Hub & Governance
- **6 Built-in Kernel Servers**:
  - `Developer MCP`: File manipulation, workspace operations, pytest runner.
  - `Inference MCP`: Provider selection, context query, fallback execution.
  - `Network MCP`: Web search, HTTP requests, DNS / IP diagnostics.
  - `Email MCP`: Read inbox, compose and send emails.
  - `Messaging MCP`: Telegram, Slack, and webhook notifications.
  - `Calendar MCP`: Google / CalDAV events listing and scheduling.
- **Modular MCP Servers**: Additional servers (`HomeAssistant MCP`, `Hardware MCP`, `Training MCP`, `Memory MCP`, `Voice MCP`, `Creative MCP`) are loaded on-demand by their respective modules.
- **Security Approval Gate**: Granular confirmation dialogs for sensitive tools.

### 5. 🔒 Sandboxed Execution & Security
- Strict path whitelist confining filesystem operations to authorized directories (`data/`, `manifesti/`, `scratch/`, `sigma_studio/`, `core/`).
- Subprocess isolation with AST static validation and execution timeouts.

---

## 📦 Official Modules Catalog (`SigmaStudio-Moduli`)

All optional modules can be installed with a single click from the **Marketplace & Extensions Hub**:

| Module ID | Name | Category | Key Features |
|:---|:---|:---|:---|
| [`sigma_creative_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab) | **Creative Lab 3D/2D** | Multimodal & Graphics | FLUX/SDXL Text-to-Image, SAM2/rembg background removal, Hunyuan3D/TripoSR 3D generation, PBR materials, Blender headless rendering, Wan2.1 video generation. |
| [`sigma_training_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab) | **Training Lab & SLM Forge** | LLM Training & SLM | Unsloth QLoRA, PEFT, Gradus Functional Weight Engine (FWE), Autopilot hyperparameter search, GGUF quantization, MMLU/GSM8K benchmarks. |
| [`sigma_voice_studio`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio) | **Voice Studio & Speech Lab** | Neural Voice & Audio | Kokoro 82M ultra-fast TTS, Coqui XTTS-v2 zero-shot voice cloning, pitch/speed tuning, live waveform visualizer, voice presets, Voice MCP server. |
| [`sigma_hardware_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab) | **Hardware & GPU Telemetry** | System & VRAM | Live VRAM allocation, GPU/CPU telemetry charts, CUDA process monitor, zombie task termination, Ollama daemon restart. |
| [`sigma_research_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab) | **Pipelines Lab & Swarm** | Research & Automation | Visual DAG pipeline designer, multi-agent research loops, step-by-step execution inspector. |
| [`sigma_knowledge`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge) | **Argomenti & Knowledge Graph** | Knowledge & Memory | D3 force-directed interactive relational graph, Universal Knowledge Nodes explorer, RAG vector search, Memory MCP server. |
| [`sigma_roadmap`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap) | **Roadmap & Task Kanban** | Productivity & Tasks | Interactive Calendar, drag-and-drop Kanban task board, chronological audit trail, milestone tracker. |
| [`sigma_domotica`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica) | **Smart Home Assistant** | IoT & Home Automation | Home Assistant WebSocket/REST bridge, device control, automation triggers, climate & lights management. |

---

## ⚡ Installation & Quick Start

### Prerequisites
- **OS**: Windows 10/11 or Linux x86_64
- **Python**: 3.10 or higher
- **Node.js**: 18.0+ and npm 9.0+
- **Ollama** (Recommended for local models): [ollama.com](https://ollama.com)

### 1. Clone the Repository
```bash
git clone https://github.com/Sigmanih/SigmaStudio.git
cd SigmaStudio
```

### 2. Automated Setup (Windows)
Double-click `install_dependencies.bat` or run:
```powershell
.\install_dependencies.bat
```
*This creates the virtual environment (`.venv`), installs Python dependencies, builds the frontend, and initializes data directories.*

### 3. Manual Setup (Linux / macOS / Custom)
```bash
# 1. Setup Python Virtual Environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Build Frontend
cd sigma_studio
npm install
npm run build
cd ..

# 3. Start Server
python sigma_server.py
```

### 4. Launching Sigma Studio
Run the one-click launcher on Windows:
```powershell
.\sigma_studio.bat
```
Or start manually:
```bash
python sigma_server.py
```
Open your browser at **`http://localhost:8000`**.

---

## 🧪 Running Automated Tests

Run the comprehensive Pytest kernel test suite:
```bash
pytest tests/ -v
```
All **147 kernel tests** validate MCP governance, agent routing, FastAPI routing, security sandboxing, and chat streaming with a 100% success rate.

---

## 📄 License & Community

- **License**: MIT License — free for personal, academic, and commercial use.
- **Modules Repository**: [Sigmanih/SigmaStudio-Moduli](https://github.com/Sigmanih/SigmaStudio-Moduli)
- **Author**: Sigma Core Team