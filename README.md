<p align="center">
  <img src="images/sigma_logo_harmonic_flow.jpg" alt="Sigma Studio Logo" width="160" style="border-radius: 24px; box-shadow: 0 8px 30px rgba(0,210,255,0.25);" />
</p>

<h1 align="center">🧬 Σ-SIGMA Studio</h1>

<p align="center">
  <strong>Modular AI-Native Cognitive Operating Kernel for Multi-GPU Inference, Autonomous Multi-Agent Swarms & Dynamic Extensible Ecosystem</strong>
</p>

<p align="center">
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://react.dev"><img src="https://img.shields.io/badge/react-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/fastapi-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://developer.nvidia.com/cuda-zone"><img src="https://img.shields.io/badge/cuda-multi--gpu-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="NVIDIA CUDA Multi-GPU"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/mcp-12--servers-00f2fe?style=flat-square" alt="Model Context Protocol"></a>
  <a href="https://github.com/Sigmanih/SigmaStudio"><img src="https://img.shields.io/badge/architecture-modular--microkernel-success?style=flat-square" alt="Modular Microkernel"></a>
</p>

<p align="center">
  <a href="README.md">🇬🇧 English</a> • <a href="README_IT.md">🇮🇹 Italiano</a> • <a href="https://github.com/Sigmanih/SigmaStudio">📦 GitHub Repository</a>
</p>

---

## 📸 Platform Screenshots

<p align="center">
  <img src="images/screenshots/bacheca.png" alt="Sigma Studio Bacheca & Skills Hub" width="100%" />
</p>
<p align="center"><em>1. Interactive Release Board, Dynamic Skills Showcase Slider & 4-Step Kernel Workflow</em></p>

<p align="center">
  <img src="images/screenshots/chat.png" alt="Sigma Studio Chat AI & Multi-Agent Swarm" width="100%" />
</p>
<p align="center"><em>2. Streaming Chat AI Workspace with Sub-100ms TTFT, SigmaEngine Multi-GPU & 12 MCP Servers</em></p>

<p align="center">
  <img src="images/screenshots/modelli.png" alt="Sigma Studio Modelli Hub & GGUF Forge" width="100%" />
</p>
<p align="center"><em>3. Modelli Hub: Hugging Face Downloader & Tab 2 GGUF Quantization Forge</em></p>

---

## 🚀 Overview

**Sigma Studio** is an open-source, executable AI Operating Kernel engineered around a lightweight, watertight **Micro-Kernel** paired with a dynamic **Runtime Module Ecosystem**. It combines an ultra-fast **Python 3.10+ FastAPI backend** with a GPU-accelerated **React 19 + Vite 8 frontend**.

Multi-agent teams interact through Modelfile manifests, standard Model Context Protocol (MCP) tools, and specialized lab environments installed on-demand from the official GitHub ecosystem.

```
+-----------------------------------------------------------------------------------------+
|                               Σ-SIGMA STUDIO COGNITIVE KERNEL                           |
+-----------------------------------------------------------------------------------------+
|  ⚡ SigmaEngine (Multi-GPU CUDA) |  ⚙️ Providers Hub (100% Interoperable) |  📜 20 Modelfiles  |
|  (C++/PyTorch FlashAttn-2 Shard) |  (OpenAI, Claude, Gemini, DeepSeek)   |  (Manifesti Hub)  |
+-----------------------------------------------------------------------------------------+
|                              🔌 12 MODEL CONTEXT PROTOCOL SERVERS                       |
+-----------------------------------------------------------------------------------------+
|  🛠️ Dev / Workspace  |  🌐 Web Search & DNS |  ✉️ Email Client |  💬 Telegram / Slack  |
|  📅 Calendar & Tasks |  🧠 Vector Memory RAG |  🏠 IoT HomeAss  |  ⚡ GPU VRAM Flush    |
+-----------------------------------------------------------------------------------------+
|                              🧩 15 MODULAR OPEN-SOURCE LABS                             |
+-----------------------------------------------------------------------------------------+
| 🎨 Creative Lab 3D/2D      | 🧠 Training Lab & SLM     | 🎙️ Voice Studio (Kokoro)      |
| 🔬 Pipelines Lab & Swarm   | ⚡ Hardware & GPU Telemetry| 🏠 Smart Domotica Assistant    |
| 📅 Roadmap & Task Audit    | 📊 Knowledge Graph D3     | 📻 Hi-Fi Audio Lounge          |
+-----------------------------------------------------------------------------------------+
```

---

## 🌟 Key Architecture & Capabilities

### 1. ⚡ SigmaEngine Cross-Platform Inference
- **Zero-Bottleneck C++/PyTorch Layer Sharding**: Automatically partitions large LLMs (from 0.5B to 70B+) across available GPUs, Apple Silicon Metal, or CPU cores and system RAM.
- **Sub-100ms TTFT**: Ultra-low Time To First Token with native FlashAttention-2 acceleration and continuous KV-cache streaming.

### 2. ⚡ Modelli Hub: Hugging Face Downloader & GGUF Forge
- **Hugging Face Downloader**: Search and download any open-source model directly from Hugging Face with resilient resumable multi-stream downloading.
- **Tab 2 GGUF Quantization Forge**: Integrated in-memory converter and quantizer (Q4_K_M, Q5_K_M, Q8_0, FP16) to tailor model weight precision to your hardware VRAM without external CLI tools.

### 3. ⚙️ Providers Hub (100% Interoperable Routing)
- Seamlessly switch between native local SigmaEngine execution and external Cloud Providers (**OpenAI GPT-4o, Anthropic Claude 3.5, Google Gemini 2.0 Flash, DeepSeek-R1, Groq, Ollama**).
- Intelligent local intent router for rapid ~100ms classification and autonomous multi-agent dispatching.

### 4. 📜 Manifesti Hub (20 Standardized Modelfiles)
- Enforce strict persona contracts, ethical boundaries, and reasoning pipelines through 20 specialized Modelfile manifests (Architect, Developer, Mathematician, Medical Specialist, Legal Jurist, Security Auditor, etc.).

### 5. 🔌 12 Model Context Protocol (MCP) Servers
- **Native Kernel Servers**: Developer CLI & Pytest, Web Search & DNS Diagnostics, Email Management, Messaging Webhooks, Calendar Scheduling, Inference Fallbacks.
- **Modular Extension Servers**: Home Assistant IoT, NVIDIA NVML Hardware & VRAM Flush, Neural Voice TTS, D3 Memory Graph, QLoRA Training.
- **Interactive Permission Governance**: Granular confirmation dialogs and access control for system-level operations.

### 6. 🏛️ Watertight Sandboxed Execution
- **Strict Path Whitelist**: Confines filesystem writes to authorized directories (`data/`, `manifesti/`, `scratch/`, `sigma_studio/`, `core/`).
- **Subprocess Isolation**: Static AST analysis preventing unauthorized Python code execution.

---

## 📦 Official Modules Catalog

All optional modules can be installed with a single click from the **Hub Skills & Extensions**:

| Module ID | Name | Category | Key Features |
|:---|:---|:---|:---|
| [`sigma_creative_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab) | **Creative Lab 3D/2D** | Multimodal & Graphics | FLUX/SDXL Text-to-Image, SAM2/rembg background removal, Hunyuan3D/TripoSR generation, PBR materials, Blender headless rendering. |
| [`sigma_training_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab) | **Training Lab & SLM** | LLM Training & SLM | Unsloth QLoRA, PEFT, Gradus Functional Weight Engine (FWE), Autopilot hyperparameter search, GGUF quantization, MMLU benchmarks. |
| [`sigma_voice_studio`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio) | **Voice Studio & Speech** | Neural Voice & Audio | Kokoro 82M ultra-fast TTS (<80ms), Coqui XTTS-v2 zero-shot voice cloning, pitch/speed tuning, live waveform visualizer, Voice MCP. |
| [`sigma_hardware_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab) | **Hardware & GPU Telemetry** | System & VRAM | Live VRAM allocation, GPU/CPU telemetry charts, CUDA process monitor, zombie task termination, one-click VRAM flush. |
| [`sigma_research_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab) | **Pipelines Lab & Swarm** | Research & Automation | Visual DAG pipeline designer, multi-agent research loops, step-by-step execution inspector, self-healing code generator. |
| [`sigma_knowledge`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge) | **Argomenti & Knowledge Graph** | Knowledge & Memory | D3 force-directed interactive relational graph, Universal Knowledge Nodes explorer, RAG vector search, Memory MCP server. |
| [`sigma_roadmap`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap) | **Roadmap & Task Kanban** | Productivity & Tasks | Interactive Calendar, drag-and-drop Kanban task board, chronological audit trail, milestone tracker. |
| [`sigma_domotica`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica) | **Smart Home Assistant** | IoT & Home Automation | Home Assistant WebSocket/REST bridge, device control, automation triggers, climate & solar power modulation. |

---

## ⚡ Installation & Quick Start

### Prerequisites
- **OS**: Windows 10/11 or Linux x86_64
- **Python**: 3.10 or higher
- **Node.js**: 18.0+ and npm 9.0+
- **CUDA Toolkit** (Recommended for GPU acceleration): NVIDIA CUDA 12.0+

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

### 3. Manual Setup (Linux / macOS)
```bash
# 1. Setup Virtual Environment
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

Run the Pytest kernel test suite:
```bash
pytest tests/ -v
```
All kernel tests validate MCP governance, agent routing, FastAPI endpoints, security sandboxing, and chat streaming with a 100% success rate.

---

## 📜 License & Community
Sigma Studio is licensed under the **Apache-2.0 License**. Continuous updates and optimizations are pushed regularly. Check the official [GitHub Repository](https://github.com/Sigmanih/SigmaStudio) for new releases.