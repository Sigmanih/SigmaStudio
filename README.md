<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sigma-banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sigma-banner-light.svg">
    <img src="images/sigma-banner-dark.svg" alt="Sigma Studio Cognitive Kernel Banner" width="100%">
  </picture>
</p>

<p align="center">
  <a href="#-quick-start"><img src="https://img.shields.io/badge/🚀_Get_Started-0284C7?style=for-the-badge" alt="Get Started" /></a>
  <a href="#-see-sigma-studio-in-action"><img src="https://img.shields.io/badge/🎥_Watch_Demo-7C3AED?style=for-the-badge" alt="Watch Demo" /></a>
  <a href="https://github.com/Sigmanih/SigmaStudio"><img src="https://img.shields.io/badge/⭐_Star_on_GitHub-10B981?style=for-the-badge" alt="Star on GitHub" /></a>
  <a href="https://github.com/Sigmanih/SigmaStudio-Moduli"><img src="https://img.shields.io/badge/🧩_Explore_Modules-F59E0B?style=for-the-badge" alt="Explore Modules" /></a>
  <a href="#-support-sigmastudio"><img src="https://img.shields.io/badge/💙_Support_Development-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Support Development" /></a>
</p>

<p align="center">
  <a href="README.md">🇬🇧 English</a> • 
  <a href="README_IT.md">🇮🇹 Italiano</a> • 
  <a href="#-quick-start">⚡ Quick Start</a> • 
  <a href="#-system-architecture">🏛️ Architecture</a> • 
  <a href="#-modular-ecosystem">🧩 Modules</a> • 
  <a href="https://github.com/Sigmanih/SigmaStudio">📦 GitHub</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/C++-Inference_Sharding-00599C?style=flat-square&logo=c%2B%2B&logoColor=white" alt="C++" />
  <img src="https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch 2.0+" />
  <img src="https://img.shields.io/badge/NVIDIA_CUDA-12.0+-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="CUDA 12.0+" />
  <img src="https://img.shields.io/badge/React-19-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React 19" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/MCP-12_Servers-00F2FE?style=flat-square" alt="Model Context Protocol" />
  <img src="https://img.shields.io/badge/License-AGPL--3.0_%2F_Commercial-7C3AED?style=flat-square" alt="License" />
</p>

---

## 🎬 See Sigma Studio in Action

https://github.com/user-attachments/assets/3b03d269-f130-4d09-8919-89cb54ee7d0f

> _Run local models, connect agents, use MCP tools, orchestrate workflows and work across your hardware seamlessly._

<p align="center">
  <em>▶️ Live Demo: Multi-Agent Streaming Chat, Autonomous Swarm, MCP Tools Execution & Real-Time Cognitive Pipeline (<code>chat_record.mp4</code>)</em><br/>
  👉 <strong><a href="https://github.com/Sigmanih/SigmaStudio/blob/main/images/screenshots/chat_record.mp4">Click here to play the full demo directly in the GitHub Video Player</a></strong>
</p>

---

## 🚀 What is Sigma Studio?

**Sigma Studio** is a modular AI workspace that turns local hardware into an extensible AI development environment.

Within a single unified desktop interface, without wrestling with complex terminal scripts or environment conflicts, you can:
- 📥 **Download any open-source model**: Search, fetch, and organize models from Hugging Face or GGUF repositories with resumable multi-stream downloads.
- 💬 **Chat with low-latency streaming**: Converse with local models (via native SigmaEngine) or external cloud providers (OpenAI, Claude, Gemini, DeepSeek) with real-time token rendering.
- 🎭 **Assign specialized roles**: Switch between 20 predefined Modelfiles with 1 click (Software Architect, Coder, Mathematician, Medical Specialist, Jurist, Security Auditor...).
- 🧪 **Test & benchmark hardware**: Measure real tokens per second, Time-to-First-Token (TTFT), and VRAM saturation under realistic workloads.
- 🧠 **Train & fine-tune**: Fine-tune Small Language Models (SLMs) locally on your own GPU using Unsloth QLoRA, PEFT, and the Gradus Functional Weight Engine.
- ⚙️ **Quantize locally (GGUF Forge)**: Convert raw FP16/FP32 weights into Q4_K_M, Q5_K_M, or Q8_0 formats directly in memory to match your hardware VRAM.
- 🔌 **Equip models with system tools (MCP)**: Connect 12 Model Context Protocol servers to browse the web, execute terminal scripts, manage calendar/email, and control smart home devices within a watertight sandbox.

All completely **free, private, and sovereign** — running locally on your terms without recurring subscriptions.

---

## ⚡ Sigma Studio & SigmaEngine: The Architecture

Sigma Studio is engineered around a clean architectural separation between the **workspace orchestrator** and the **underlying native inference engine**:

| Component | Responsibility |
|:---|:---|
| **Σ-SIGMA STUDIO** | **AI workspace and orchestration environment** built around the watertight Sigma Kernel. Provides the React 19 UI, streaming multi-agent chat, MCP tool execution governance, AST sandbox security, and dynamic module loading. |
| **⚡ SIGMAENGINE** | **High-performance local inference engine** for heterogeneous hardware. Features zero-bottleneck C++/PyTorch layer sharding across multi-GPU CUDA, CPU and system RAM offloading, Apple Metal, sub-100ms TTFT FlashAttention-2, and an in-memory GGUF Quantization Forge (Q4/Q5/Q8). |

---

## ⚖️ Why Sigma Studio?

| Problem in Local AI | Sigma Studio Solution |
|:---|:---|
| **Local models are fragmented** | **Unified model & provider abstraction layer** (seamlessly route between local weights and OpenAI, Claude, Gemini, DeepSeek, Groq, Ollama). |
| **Large models exceed single GPU VRAM** | **Zero-bottleneck layer sharding & RAM offloading** across multiple NVIDIA GPUs, Apple Silicon Metal, or system RAM. |
| **Agents lack real system tools** | **Native Model Context Protocol (MCP)** with 12 built-in servers (Terminal CLI, Web, Email, IoT, Memory Graph). |
| **AI workflows are hard to inspect** | **Visual execution DAG & real-time telemetry**, tracking token streaming, VRAM allocations, and tool call confirmations. |
| **Extensions become monolithic bloat** | **Decoupled Modular Labs** that can be installed on-demand from [`SigmaStudio-Moduli`](https://github.com/Sigmanih/SigmaStudio-Moduli) without restarting the kernel. |
| **Hardware setups vary widely** | **Hardware-aware execution** optimizing automatically for multi-GPU workstations, laptops, or edge devices like Raspberry Pi 5. |
| **Local AI lacks an integrated environment** | **All-in-one sovereign AI development workspace**: Chat, Forge, Fine-Tuning, 3D/2D Generation, Voice, and Task Automation. |

---

## 🎯 Built For...

- 💻 **Developers**: Build AI applications, orchestrate multi-agent swarms, debug MCP tool servers, and run sandboxed code safely.
- 🔬 **Researchers**: Benchmark open-source LLMs, experiment with Unsloth QLoRA fine-tuning, and test distributed model layer partitioning.
- ⚡ **AI Enthusiasts**: Run private, sovereign frontier models locally with zero subscription fees and 100% data sovereignty.
- 🛠️ **Hardware Builders**: Combine heterogeneous GPUs, system RAM, and edge devices into a unified, high-throughput AI runtime.

---

## 🏛️ System Architecture

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sigma-arch-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sigma-arch-light.svg">
    <img src="images/sigma-arch-dark.svg" alt="Sigma Studio System Architecture Diagram" width="100%">
  </picture>
</p>

1. **Workspace UI Layer**: GPU-accelerated React 19 + Vite 8 frontend featuring streaming agent terminals, D3 relational memory graphs, Three.js 3D viewport, and real-time hardware telemetry.
2. **Sigma Kernel**: Lightweight Python 3.10+ FastAPI microkernel providing strict path whitelisting, AST static analysis sandboxing, intent classification, and session management.
3. **Pillars of Orchestration**:
   - **Autonomous Agents**: 20 standardized Modelfiles (Architect, Developer, Mathematician, Medical Specialist, Jurist, Security Auditor, etc.).
   - **Providers Hub**: 100% interoperable routing between local inference and cloud APIs (OpenAI, Anthropic Claude, Google Gemini, DeepSeek, Groq, Ollama).
   - **12 MCP Servers**: Model Context Protocol servers for filesystem, live web search, messaging, calendar, IoT, and VRAM management.
4. **SigmaEngine**: The raw C++/PyTorch execution engine sharding layers across NVIDIA CUDA GPUs, system RAM, or Apple Metal with FlashAttention-2.
5. **Modular Ecosystem**: Hot-loaded on demand from the community catalog [`SigmaStudio-Moduli`](https://github.com/Sigmanih/SigmaStudio-Moduli).

---

## 🌟 Core Capabilities & Extensible Labs

### Core Runtime (Built-in)
- **⚡ SigmaEngine Local Inference**: Multi-GPU layer sharding, sub-100ms TTFT, continuous KV-cache streaming.
- **🛠️ Hugging Face Downloader & GGUF Forge**: In-memory converter and quantizer (Q4_K_M, Q5_K_M, Q8_0, FP16) to fit any model to your hardware without external CLI tools.
- **🤖 Autonomous Agent Swarm & 20 Modelfiles**: Persona contracts and reasoning workflows tailored for specific professional domains.
- **🔌 12 Model Context Protocol (MCP) Servers**: Interactive permission governance and tool execution for system-level operations.
- **🛡️ Watertight Sandboxed Execution**: Confines filesystem writes to authorized directories (`data/`, `scratch/`, `core/`) with AST code protection.

### Extensible Labs (Installable on demand)
- **🎨 Creative Lab 3D/2D**: FLUX/SDXL text-to-image, SAM2 background removal, Hunyuan3D/TripoSR mesh generation, PBR materials.
- **🎙️ Voice Studio & Speech**: Kokoro 82M ultra-fast TTS (<80ms), Coqui XTTS-v2 zero-shot voice cloning, pitch/speed tuning, live waveform visualizer.
- **🧠 Training Lab & SLM**: Unsloth QLoRA, PEFT, Gradus Functional Weight Engine (FWE), Autopilot hyperparameter search.
- **🔬 Pipelines Lab & Swarm**: Visual DAG pipeline designer, multi-agent research loops, step-by-step execution inspector.
- **📊 Argomenti & Knowledge Graph**: D3 force-directed relational memory graph with vector RAG search.
- **⚡ Hardware & GPU Telemetry**: Real-time VRAM allocation, CUDA process monitor, zombie task termination, one-click VRAM flush.
- **🏠 Smart Home Domotica**: Home Assistant WebSocket/REST bridge, device control, automation triggers, climate and solar modulation.

---

## 🧩 Modular Ecosystem

Sigma Studio is engineered to keep the core runtime ultra-lightweight. Optional features and specialized lab environments are distributed as independently installable modules:

<p align="center">
  <a href="https://github.com/Sigmanih/SigmaStudio-Moduli">
    <img src="https://img.shields.io/badge/Explore_SigmaStudio--Moduli-Official_Catalog_→-7C3AED?style=for-the-badge&logo=github&logoColor=white" alt="Explore SigmaStudio Modules" />
  </a>
</p>

All modules can be installed with a single click directly inside the **Hub Skills & Extensions** tab in the Sigma Studio UI without restarting the server.

---

## ⚡ Quick Start

Zero manual configuration required: dependencies, virtual environments, hardware detection, and frontend assets are **automatically verified and installed upon first launch**.

### 1. Clone the Repository
```bash
git clone https://github.com/Sigmanih/SigmaStudio.git
cd SigmaStudio
```

### 2. Launch (Automatic Auto-Setup)
- **Windows**:
  ```powershell
  .\sigma_studio.bat
  ```
- **Linux / macOS / Raspberry Pi**:
  ```bash
  chmod +x sigma_studio.sh
  ./sigma_studio.sh
  ```

> 💡 *On the very first run, Sigma Studio automatically creates the virtual environment, installs Python requirements, sets up the native inference runtime, builds the frontend if needed, and opens `http://localhost:8000`.*

#### ⚙️ Launcher Options
- Force reinstall/update dependencies: `.\sigma_studio.bat --install` (or `./sigma_studio.sh --install`)
- Run pre-flight environment check: `.\sigma_studio.bat --check` (or `./sigma_studio.sh --check`)
- Inspect detected hardware and accelerators: `python sigma_launcher.py --info`

### 🖥️ Supported Hardware & Platform Matrix

Sigma Studio is engineered to run seamlessly across heterogeneous architectures — from multi-GPU workstation clusters to single-board edge computers:

| Platform | Architecture | Accelerators & Compute | Recommended Models | One-Click Launcher |
|:---|:---|:---|:---|:---|
| **Windows Workstation** | `x86_64` (Windows 10/11) | NVIDIA CUDA (RTX 30xx/40xx), Vulkan, CPU | All sizes (0.5B – 70B+) | `.\sigma_studio.bat` |
| **Linux Server & Desktop** | `x86_64` (Ubuntu / Debian / Arch) | NVIDIA Multi-GPU, AMD ROCm, Intel SYCL, CPU | All sizes (0.5B – 70B+) | `./sigma_studio.sh` |
| **Apple Silicon Mac** | `arm64` (M1 / M2 / M3 / M4) | Apple Metal (Unified Memory up to 128GB+) | 0.5B – 32B+ Q4_K_M | `./sigma_studio.sh` |
| **Raspberry Pi 5 / 4** | `aarch64` (Debian Bookworm 64-bit) | Broadcom Quad-Core ARM Cortex-A76 (NEON) | 0.5B – 3B SLMs (Qwen 2.5, Llama 3.2, SmolLM2) | `./sigma_studio.sh` |
| **Edge & PC CPU-Only** | `x86_64` / `arm64` | Intel / AMD AVX2/AVX-512, Snapdragon X | 0.5B – 7B Quantized (Q4_K_M) | `.\sigma_studio.bat` / `./sigma_studio.sh` |

> 🍓 **Raspberry Pi 5 Ready**: On aarch64 Linux, `./sigma_studio.sh` automatically detects the ARM Cortex CPU, selects the lightweight CPU wheel set, configures the native ARM runtime, and runs modern SLMs (Small Language Models) with zero manual setup.

---

## 🧪 Automated Tests & Verification

Run the comprehensive Pytest kernel test suite:
```bash
pytest tests/ -v
```
All kernel tests validate MCP governance, agent routing, FastAPI endpoints, security sandboxing, and chat streaming with a 100% success rate.

---

## 💙 Support Sigma Studio

Sigma Studio is developed as an independent, sovereign open-source project. If you find it useful for your research, workflows, or homelab setup, consider supporting continued development:

<p align="center">
  <a href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC">
    <img src="https://img.shields.io/badge/Support_SigmaStudio-Donate_with_PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Support SigmaStudio via PayPal" />
  </a>
  <br/>
  <small><em>Your sponsorship supports multi-GPU inference optimizations, open-source model roles, and zero-cost sovereign AI tools.</em></small>
</p>

---

## 📜 License & Community

Sigma Studio is open source software dual-licensed under:
- **GNU Affero General Public License v3 (AGPL-3.0)** for the open source community, developers, and researchers.
- **Commercial License** for enterprise deployments, proprietary integrations, and closed-source SaaS offerings.

See the [LICENSE](file:///LICENSE) file for complete licensing terms, trademark guidelines, and commercial licensing contacts.

- [CONTRIBUTING.md](file:///CONTRIBUTING.md) — Contribution guidelines, Developer Certificate of Origin, and CLA terms
- [SECURITY.md](file:///SECURITY.md) — Vulnerability reporting and security policy
- [CODE_OF_CONDUCT.md](file:///CODE_OF_CONDUCT.md) — Contributor Covenant v2.1
- [GitHub Repository](https://github.com/Sigmanih/SigmaStudio) — Official repository and updates
