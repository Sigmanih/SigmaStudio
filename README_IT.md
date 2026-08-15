<p align="center">
  <h1 align="center">🧬 Σ-SIGMA Studio</h1>
  <p align="center"><strong>Micro-Kernel Modulare AI-Native per Orchestrazione Cognitiva, Swarm Multi-Agente Autonomi ed Ecosistema Modulare Dinamico</strong></p>
  <p align="center">
    <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="#"><img src="https://img.shields.io/badge/react-19-61DAFB.svg" alt="React 19"></a>
    <a href="#"><img src="https://img.shields.io/badge/fastapi-0.100+-009688.svg" alt="FastAPI"></a>
    <a href="#"><img src="https://img.shields.io/badge/ollama-ready-FF6F00.svg" alt="Ollama Ready"></a>
    <a href="#"><img src="https://img.shields.io/badge/mcp-standard-00f2fe.svg" alt="Model Context Protocol"></a>
    <a href="#"><img src="https://img.shields.io/badge/architettura-microkernel--modulare-success.svg" alt="Micro-Kernel Modulare"></a>
  </p>
  <p align="center">
    <a href="README.md">🇬🇧 English</a> • <a href="README_IT.md">🇮🇹 Italiano</a> • <a href="https://github.com/Sigmanih/SigmaStudio-Moduli">📦 Catalogo Moduli</a>
  </p>
</p>

---

## 🚀 Panoramica

**Sigma Studio** è una piattaforma open-source progettata attorno a un **Micro-Kernel** ultraleggero e sicuro, affiancato da un **Ecosistema Modulare Runtime a Camere Stagne**. Combina un backend ad altissime prestazioni in **Python 3.10+ FastAPI** con un'interfaccia reattiva in **React 19 + Vite 8**.

I team di agenti AI interagiscono mediante manifesti Modelfile, strumenti standard Model Context Protocol (MCP) e laboratori specializzati installabili a caldo direttamente dal catalogo ufficiale [**SigmaStudio-Moduli**](https://github.com/Sigmanih/SigmaStudio-Moduli).

```
+-------------------------------------------------------------------------+
|                       Σ-SIGMA STUDIO MICRO-KERNEL                       |
+-------------------------------------------------------------------------+
|  🧠 Router Multi-Provider  |  🤖 Swarm Multi-Agente DAG |  🔌 Core MCP Hub   |
|  (Ollama, DeepSeek, OpenAI)|  (Loop Paralleli Dinamici) |  (6 Server Kernel) |
+-------------------------------------------------------------------------+
|                     🏪 HUB MODULI ED ESTENSIONI                         |
+-------------------------------------------------------------------------+
| 🎨 Creative Lab 3D/2D      | 🧠 Training Lab & Forge   | 🎙️ Voice Studio    |
| 🔬 Pipelines Lab & Swarm   | ⚡ Hardware & Telemetria  | 🏠 Domotica Smart  |
| 📅 Roadmap & Task Audit    | 📊 Grafo Argomenti/Memoria| 📻 Hi-Fi Audio Lab |
+-------------------------------------------------------------------------+
```

---

## 🌟 Architettura & Funzionalità Chiave

### 1. 🏛️ Architettura a Camere Stagne (Micro-Kernel)
- **Zero Codice Superfluo**: I laboratori o le estensioni non installate non appesantiscono il kernel. Non occupano memoria, non registrano rotte statiche e non appaiono nella sidebar.
- **Iniezione a Caldo (Hot-Injection)**: I moduli vengono installati e disinstallati a runtime tramite l'**Hub Moduli & Estensioni**, collegando dinamicamente endpoint FastAPI, viste React e server MCP senza necessità di riavviare il server.
- **Bundle Ultra-Compatto**: Il bundle frontend compila in **< 700ms** con una dimensione di soli **~1.1 MB**.

### 2. 🧠 Motore di Inferenza Multi-Provider
- Supporto nativo per modelli locali **Ollama** e API Cloud esterne (**DeepSeek, OpenAI, Anthropic Claude, Groq, OpenRouter**).
- Router semantico locale ultrarapido (~100ms) per classificazione automatica del task e selezione dinamica del modello ottimale.

### 3. 🤖 Orchestrazione Swarm Multi-Agente Autonoma
- **Dynamic Swarm Planner**: Genera piani di esecuzione a grafo aciclico diretto (DAG) in tempo reale per risolvere task complessi multi-step.
- **Broker di Contesto**: Condivisione sicura della memoria episodica, passaggio dei trace degli strumenti ed esecuzione parallela in thread-pool.
- **Sistema di Manifesti**: Ruoli, personalità e vincoli operativi degli agenti definiti in formato Modelfile Markdown (`manifesti/*.md`).

### 4. 🔌 Hub MCP (Model Context Protocol) & Governance
- **6 Server Kernel Integrati**:
  - `Developer MCP`: Manipolazione file, ispezione workspace, esecuzione test pytest.
  - `Inference MCP`: Selezione provider, recupero contesto, fallback automatico.
  - `Network MCP`: Ricerca web live, richieste HTTP, diagnostica DNS/IP.
  - `Email MCP`: Lettura inbox, composizione e invio email.
  - `Messaging MCP`: Notifiche Telegram, Slack e webhook esterni.
  - `Calendar MCP`: Schedulazione e consultazione eventi Google/CalDAV.
- **Server MCP Modulari**: I server aggiuntivi (`HomeAssistant MCP`, `Hardware MCP`, `Training MCP`, `Memory MCP`, `Voice MCP`, `Creative MCP`) vengono registrati solo quando il rispettivo modulo è installato.
- **Gate di Approvazione Sicura**: Dialoghi di conferma granulari per gli strumenti operativi critici.

### 5. 🔒 Sandbox e Sicurezza
- Whitelist rigorosa dei percorsi che limita le operazioni del filesystem alle cartelle autorizzate (`data/`, `manifesti/`, `scratch/`, `sigma_studio/`, `core/`).
- Isolamento dei sottoprocessi con validazione statica AST e timeout di sicurezza.

---

## 📦 Catalogo Moduli Ufficiali (`SigmaStudio-Moduli`)

Tutti i moduli opzionali possono essere installati con 1-click dall'**Hub Moduli & Estensioni**:

| ID Modulo | Nome | Categoria | Funzionalità Principali |
|:---|:---|:---|:---|
| [`sigma_creative_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab) | **Creative Lab 3D/2D** | Multimodale & Grafica | Text-to-Image (FLUX/SDXL), rimozione sfondo SAM2/rembg, generazione 3D (Hunyuan3D/TripoSR), materiali PBR, rendering Blender headless, generazione video Wan2.1. |
| [`sigma_training_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab) | **Training Lab & SLM Forge** | Fine-Tuning & SLM | Unsloth QLoRA, PEFT, Gradus Functional Weight Engine (FWE), Autopilot iperparametri, quantizzazione GGUF, benchmark MMLU/GSM8K. |
| [`sigma_voice_studio`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio) | **Voice Studio & Speech Lab** | Voce Neurale & Audio | Kokoro 82M ultra-veloce, Coqui XTTS-v2 zero-shot voice cloning, regolazione velocità/pitch, waveform live, preset vocali, Voice MCP server. |
| [`sigma_hardware_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab) | **Hardware & Telemetria GPU** | Sistema & VRAM | Monitoraggio real-time VRAM/GPU/CPU, gestione processi CUDA, terminazione processi zombie, riavvio demone Ollama. |
| [`sigma_research_lab`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab) | **Pipelines Lab & Swarm** | Ricerca & Automazione | Visual designer di pipeline a nodi DAG, loop di ricerca multi-agente, ispezione step-by-step dei risultati. |
| [`sigma_knowledge`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge) | **Argomenti & Grafo Memoria** | Conoscenza & Memoria | Grafo relazionale interattivo D3 force-directed, Universal Knowledge Nodes explorer, ricerca vettoriale RAG, Memory MCP server. |
| [`sigma_roadmap`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap) | **Roadmap & Kanban Task** | Produttività & Attività | Calendario interattivo, lavagna Kanban drag-and-drop, audit log cronologico, pannello flottante per milestone. |
| [`sigma_domotica`](https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica) | **Smart Home Assistant** | IoT & Domotica | Bridge WebSocket/REST con Home Assistant, controllo dispositivi, trigger automazioni, gestione luci e clima. |

---

## ⚡ Installazione & Avvio Rapido

### Prerequisiti
- **Sistema Operativo**: Windows 10/11 o Linux x86_64
- **Python**: 3.10 o superiore
- **Node.js**: 18.0+ e npm 9.0+
- **Ollama** (Consigliato per modelli locali): [ollama.com](https://ollama.com)

### 1. Clonare il Repository
```bash
git clone https://github.com/Sigmanih/SigmaStudio.git
cd SigmaStudio
```

### 2. Setup Automatico (Windows)
Fai doppio clic su `install_dependencies.bat` oppure esegui da PowerShell:
```powershell
.\install_dependencies.bat
```
*Questo script crea l'ambiente virtuale (`.venv`), installa le dipendenze Python, compila il frontend React e prepara i file di configurazione.*

### 3. Setup Manuale (Linux / macOS)
```bash
# 1. Crea e attiva l'ambiente virtuale Python
python -m venv .venv
source .venv/bin/activate  # Su Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Compila il Frontend
cd sigma_studio
npm install
npm run build
cd ..

# 3. Avvia il Server
python sigma_server.py
```

### 4. Avvio di Sigma Studio
Avvia con un clic su Windows:
```powershell
.\sigma_studio.bat
```
Oppure manualmente da terminale:
```bash
python sigma_server.py
```
Apri il browser su **`http://localhost:8000`**.

---

## 🧪 Esecuzione Suite di Test

Esegui la suite completa di test automatizzati con Pytest:
```bash
pytest tests/ -v
```
Tutti i **147 test del kernel** verificano la governance MCP, il routing agenti, le API FastAPI, la sandbox di sicurezza e lo streaming SSE con il 100% di successo.

---

## 📄 Licenza & Community

- **Licenza**: MIT License — libera per uso personale, didattico e commerciale.
- **Repository Moduli**: [Sigmanih/SigmaStudio-Moduli](https://github.com/Sigmanih/SigmaStudio-Moduli)
- **Autore**: Sigma Core Team