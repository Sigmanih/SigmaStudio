<p align="center">
  <h1 align="center">🧬 Σ-SIGMA Studio</h1>
  <p align="center"><strong>Piattaforma AI-Native per l'Orchestrazione Cognitiva e l'Automazione della Ricerca</strong></p>
  <p align="center">
    <a href="#"><img src="https://img.shields.io/badge/license-GPLv3%20%2F%20Commercial-blue.svg" alt="Licenza GPL v3 / Commerciale"></a>
    <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="#"><img src="https://img.shields.io/badge/react-19-61DAFB.svg" alt="React 19"></a>
    <a href="#"><img src="https://img.shields.io/badge/ollama-ready-FF6F00.svg" alt="Ollama Ready"></a>
    <a href="#"><img src="https://img.shields.io/badge/ai-multi--provider-9B59B6.svg" alt="Multi-Provider AI"></a>
    <a href="#"><img src="https://img.shields.io/badge/status-v8.1--beta-success.svg" alt="v8.1 Beta"></a>
    <a href="#"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  </p>
</p>

---

## 🚀 Cos'è Sigma Studio?

**Sigma Studio è un motore di orchestrazione cognitiva** — un ambiente eseguibile in cui agenti AI creano, verificano, documentano e organizzano la conoscenza, governati da manifesti Modelfile che ne definiscono il comportamento.

Immagina un **team di agenti AI specializzati** (un matematico, un architetto, un test engineer, un revisore, un visualizzatore) che lavorano 24 ore su 24 sulla tua ricerca, tracciando ogni azione, testando ogni teorema e costruendo un grafo relazionale navigabile di tutto ciò che producono.

**Questo è Sigma Studio.**

### Differenziali Chiave

| Caratteristica | Perché è Importante |
|:---------------|:--------------------|
| 🧠 **AI Multi-Provider** | Ollama (locale), DeepSeek, OpenAI, Anthropic, Groq, OpenRouter — scegli tu il cervello |
| 📜 **Sistema dei Manifesti** | Ogni agente ha un "codice di condotta" scritto come Modelfile di Ollama. Contratti eseguibili, non semplici istruzioni |
| 🏃 **Autopilota** | Scegli un modello e lascialo migliorare da solo: round di valutazione, test statistici e specializzazione automatica |
| 🔬 **Motore Benchmark Ufficiale** | Valuta i modelli su 11 suite ufficiali (MMLU, GSM8K, HumanEval, ARC, BBH…) con coda di revisione e audit |
| 🔨 **Forgia SLM** | Costruisci piccoli modelli linguistici da zero, in italiano — pre-training, distillazione, export GGUF |
| 🔌 **MCP Server Hub** | 6 server MCP integrati (Memory, Developer, Hardware, Training, Inference, Network) |
| 🤖 **Orchestrazione Multi-Agente** | Pipeline parallele, condivisione del contesto, sciami dinamici e delega automatica |
| 🏗️ **AI Full-Stack** | Dalla teoria accademica al codice funzionante: teoremi → test → visualizzazioni D3.js → whitepaper |
| 🔒 **Sicurezza Sandbox** | Ogni operazione è confinata a percorsi autorizzati. Nessun agente tocca i file di sistema |
| 🧩 **Architettura Modulare** | Backend Python + Frontend React 19 + AI Multi-provider: completamente componibile |

> 📐 **Vuoi i dettagli tecnici approfonditi?** L'architettura completa, il riferimento degli endpoint, le strutture dati e gli internals del backend vivono in **[`architettura.md`](architettura.md)**. Questo README parla di cosa puoi fare con la piattaforma e di come avviarla.

---

## 🖼️ Screenshots

<p align="center">
  <img src="images/screenshots/argomenti.png" alt="Mappa degli Argomenti e Grafo Relazionale" width="48%" />
  <img src="images/screenshots/test.png" alt="Test e Validazione Computazionale" width="48%" />
</p>
<p align="center">
  <em>Mappa degli Argomenti con Grafo Relazionale D3.js (sinistra) e Test Automatici / Validazione dei moduli (destra).</em>
</p>

<p align="center">
  <img src="images/screenshots/ResearchLab.png" alt="Research Lab — Orchestrazione e Roadmap del Team di Agenti" width="48%" />
  <img src="images/screenshots/chat.png" alt="Chat Multi-Agente con Manifesti" width="48%" />
</p>
<p align="center">
  <em>Research Lab con la pianificazione in micro-task (sinistra) e la Chat Multi-Agente con integrazione dei Manifesti (destra).</em>
</p>

<p align="center">
  <img src="images/screenshots/modificafile.png" alt="Modifica File / Editor" width="48%" />
  <img src="images/screenshots/visualizzazioni.png" alt="Visualizzazioni Interattive Generate" width="48%" />
</p>
<p align="center">
  <em>Sigma Lab Editor per la redazione e modifica dei file (sinistra) e le Visualizzazioni interattive D3.js generate dagli agenti (destra).</em>
</p>

### 🆕 Training Lab — guardalo in azione

<p align="center">
  <img src="images/screenshots/autopilot.png" alt="Autopilota — specializzazione automatica del modello" width="48%" />
  <img src="images/screenshots/benchmark.png" alt="Benchmark Test ufficiale" width="48%" />
</p>
<p align="center">
  <em>Ciclo Autopilota con profilo per competenza e verdetti statistici (sinistra) e Benchmark Test ufficiale su 11 suite (destra).</em>
</p>

<p align="center">
  <img src="images/screenshots/mcphub.png" alt="MCP Server Hub" width="48%" />
  <img src="images/screenshots/slmforge.png" alt="Forgia SLM" width="48%" />
</p>
<p align="center">
  <em>MCP Server Hub con 6 server specializzati e console JSON-RPC (sinistra) e Forgia SLM per costruire piccoli modelli da zero (destra).</em>
</p>

<p align="center">
  <img src="images/screenshots/trainingstudio.png" alt="Training Studio — fine-tuning semi-assistito" width="48%" />
  <img src="images/screenshots/pipelinedesigner.png" alt="Pipelines Lab — progettazione pipeline DAG" width="48%" />
</p>
<p align="center">
  <em>Training Studio percorso guidato di fine-tuning (sinistra) e Pipelines Lab con designer DAG (destra).</em>
</p>

### 💡 Da un singolo Prompt a una Knowledge Base Completa

Tutti i file di teoria, i formulari, i grafici interattivi D3.js e gli script di test visibili negli screenshot sono stati generati a partire da **un unico, singolo prompt iniziale** inserito nel **Research Lab**:

> *"Scriviamo tutti gli argomenti e i sottoargomenti trattati in un corso di Analisi 1 matematica ingegneria con dimostrazioni, formulari, esercizi in files separati e tutto il necessario a comprendere perfettamente la materia"*

Da questo singolo input, il coordinatore **Sigma Architect** e la pipeline di agenti hanno:
1. **Analizzato il dominio** e suddiviso la roadmap in 7 moduli sequenziali (dalle Successioni alle Equazioni Differenziali).
2. **Generato la teoria** in file Markdown arricchiti con formule LaTeX e definizioni rigorose.
3. **Scritto ed eseguito i test unitari Python** (`test-engineer`) con validazione matematica e self-healing automatico in caso di errori.
4. **Disegnato visualizzazioni interattive** (`viz-designer`) pronte da navigare nel Sigma Lab.
5. **Redatto whitepaper** e report di validazione formali per certificare il lavoro.

---

## 💬 Il potere della Chat AI e dell'Orchestrazione

La chat di Sigma Studio non è un semplice chatbot, ma un pannello di controllo cognitivo flessibile che vanta funzionalità avanzate:

- **4 Modalità Operative**:
  - **Ask**: Spiegazioni rapide e domande teoriche senza modificare il workspace.
  - **Plan**: Scomposizione di obiettivi complessi in micro-task salvati direttamente nella Roadmap.
  - **Execute**: Modifica e scrittura di file sul disco in tempo reale con controllo del Sandbox.
  - **Complete Task**: Risoluzione assistita o autonoma di compiti specifici della Roadmap.
- **Associazione del Manifesto**: Cambio al volo del comportamento dell'agente associando i Manifesti di configurazione, con ripristino automatico quando si naviga tra sessioni diverse.
- **Tracciamento in Tempo Reale**: Ogni azione (creazione di file, esecuzione di comandi, test di validazione) lascia una notifica strutturata per la massima trasparenza operativa.
- **Ricerca Web**: Ricerca integrata (DuckDuckGo + Wikipedia) per fondare le risposte degli agenti su fonti esterne.
- **Pipelines Lab**: Progetta ed esegui pipeline DAG con condizioni di branching, loop self-healing e streaming di avanzamento SSE.

---

## 🏃 Autopilota — Lascia che il Modello Migliori Da Sè

L'**Autopilota** è il modo più nuovo di addestrare dentro Sigma Studio: scegli un modello e lascialo specializzare da solo.

- **Cicli automatici**: il modello viene valutato, vengono identificate le competenze deboli, viene generato un round di fine-tuning e il risultato viene valutato di nuovo.
- **Profilo per competenza**: 19 competenze con doppia barra — il modello standard in azzurro, il miglioramento guadagnato in verde — così il guadagno si legge come uno spessore, non come due numeri da sottrarre a mente.
- **Verdetti statistici**: ogni round riporta vittorie, sconfitte e un p-value su uno split di holdout dedicato, così poche decine di quesiti non possono essere scambiati per un miglioramento reale.
- **Diario e curva di loss live**: guarda la loss del training e l'avanzamento della valutazione in tempo reale mentre il ciclo gira.
- **Sicuro per progettazione**: lo split di training è deliberatamente **diverso** dalle suite di benchmark usate per giudicare — niente barare sulle metriche.

Accesso: barra laterale → `🧠 Training Lab` → **🤖 Autopilota**.

---

## 🎛️ Training Studio — Fine-Tuning Semi-Assistito

Il **Training Studio** è il percorso guidato tra configurazione manuale e automazione totale:

- Workflow passo-passo di fine-tuning (dataset → metodo → modello → iperparametri → lancio).
- Preset best-practice e controlli di validazione in ogni fase.
- Si collega automaticamente al Monitor dei job quando viene creato un job di training.

Accesso: barra laterale → `🧠 Training Lab` → **🎛️ Semi-assistito**.

---

## 🧠 Training Lab — Cassetta degli Attrezzi Manuale

Il **Training Lab** espone anche la cassetta degli attrezzi manuale completa, organizzata in 5 strumenti:

| Strumento | Cosa Fa |
|:----------|:--------|
| 🗃️ **Dataset** | 15+ dataset open-source curati, ricerca HuggingFace (100K+), import locale drag & drop |
| ⚙️ **Training** | 4 metodi (LoRA/Unsloth, SFT/TRL, Full Pre-Training, Script Custom), model picker, controllo completo degli iperparametri |
| 🔨 **Forgia SLM** | Costruisci piccoli modelli da zero — dataset italiani, pre-training e/o distillazione, export GGUF, chat sui checkpoint |
| 🧪 **Benchmark Test** | Valutazione ufficiale su 11 suite con grader, coda di revisione, audit e capacity probe multi-GPU |
| 📊 **Monitor** | Log live, grafico interattivo della loss, diagnostica CUDA, controlli job, **Export → Ollama** |

### 🗃️ Dataset

- **⭐ Consigliati**: 15 dataset open-source curati per LLM training (Alpaca, Dolly, OpenHermes, UltraChat, OpenOrca, CodeAlpaca, MetaMathQA, GSM8K, MATH, TinyStories, The Pile, Italian Dolly, OPUS-100…).
- **🔍 Ricerca HuggingFace**: 100.000+ dataset con preview e metadati.
- **📂 Import Locale**: trascina e rilascia file JSONL, JSON, CSV o TXT — parsing automatico.
- **🗂️ I Miei Dataset**: gestisci i dataset importati e selezionali per il training.

### ⚙️ Configurazione

| Metodo | Descrizione | VRAM Min | Quando Usarlo |
|:-------|:------------|:---------|:--------------|
| ⚡ **LoRA (Unsloth)** | Fine-tuning efficiente con LoRA 4-bit | 8 GB | Consigliato per la maggior parte dei casi — 2x più veloce, 60% meno VRAM |
| 🔬 **SFT (TRL)** | Supervised Fine-Tuning con PEFT | 12 GB | Stabile e versatile, supporta tutti i modelli HuggingFace |
| 🌐 **Full Pre-Training** | Training da zero su testo grezzo | 4-80 GB | Per addestrare modelli da zero |
| 🛠️ **Script Custom** | Template Python personalizzabile | — | Massima flessibilità, modifica lo script prima di avviare |

Modelli base: LLaMA 3.2, Mistral, Phi-3, Gemma + modelli Ollama locali + modello custom. Iperparametri: epoche, batch size, learning rate, max sequence length, LoRA rank/alpha, gradient accumulation.

### 🔨 Forgia SLM

Costruisci **piccoli modelli linguistici da zero**:
- Dataset italiani da HuggingFace, pre-training e/o distillazione da un modello insegnante.
- Training del tokenizer, preset di architettura (micro/mini), vocab size, sequence length.
- Formati di export GGUF e altri, e una **chat sui checkpoint** per provare il modello mentre si allena.

### 🧪 Benchmark Test

Il **motore di valutazione ufficiale dei modelli**:
- **11 suite ufficiali** (MMLU, GSM8K, HumanEval, ARC, BBH…) con dataset in cache.
- Grader robusto con **coda di revisione** per risposte doppie, illeggibili o in errore.
- **Audit** che verifica i verdetti quesito per quesito (falsi positivi / falsi negativi).
- **Capacity probe**: misura quanto carico parallelo regge davvero un modello sulla tua GPU.
- **Endpoint multi-GPU**: avvia server Ollama legati a singole GPU e distribuisci la valutazione su tutte.

### 📊 Monitor

- Hardware strip (CUDA, GPU, VRAM, temperatura, RAM, versione PyTorch) + diagnostica CUDA.
- Selettore job con cronologia completa e stati (Pronto/In esecuzione/Completato/Fallito/Fermato).
- Grafico SVG interattivo della loss con parsing automatico dal log.
- Terminale live con colorazione per righe SIGMA/Error/Warning/Success.
- **Export → Ollama**: generazione automatica del Modelfile, system prompt personalizzabile, comandi `ollama create` / `ollama run` integrati.

---

## 🔌 MCP Server Hub

Sigma Studio include **6 server MCP integrati**, che espongono i loro strumenti e risorse attraverso un hub unificato con console di test JSON-RPC:

| Server | Strumenti |
|:-------|:----------|
| 🧠 **Memory MCP** | Query su vector DB, memoria episodica, ricerca nel knowledge graph |
| 👨‍💻 **Developer MCP** | Esecuzione pytest, file del workspace, codice in sandbox, git status |
| ⚙️ **Hardware MCP** | Stato hardware, pulizia cache VRAM, benchmark GPU |
| 🎓 **Training MCP** | Import dataset, training LoRA, export modello Ollama |
| ⚡ **Inference MCP** | Selezione modello routato, swap KV-cache, ensemble di logits |
| 🌐 **Network MCP** | Scoperta peer, broadcast task allo sciame, ricerca web & fetch pagine |

L'hub espone anche gli strumenti del **Benchmark MCP** (lista/scarica suite, avvia benchmark, stato, coda di revisione) così gli agenti possono guidare le valutazioni in modo programmatico.

Accesso: barra laterale → `⚡ MCP Server Hub`.

---

## 🧩 Knowledge Nodes

Il sistema dei **Knowledge Nodes** aggiunge un albero universale di nodi di conoscenza (cartelle + file sub-app) sopra la classica struttura a moduli — navigabile dall'interfaccia con anteprima codice/visualizzazione e percorribile nodo per nodo.

---

## ⚡ Hardware & GPU Monitor

L'**Hardware & GPU Monitor** è un pannello di controllo completo per il monitoraggio e la configurazione della GPU.

- **Card GPU in tempo reale**: modello, driver, bus PCIe, barra VRAM, carico compute, consumo, temperatura, compute capability.
- **Configurazione multi-GPU**: `CUDA_VISIBLE_DEVICES`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, GPU preferita per il Training Lab.
- **HuggingFace Token**: imposta il token HF per velocizzare i download (fino a 10x), con indicatore "token configurato".
- **Processi attivi GPU**: tabella dei processi con bus ID, PID, eseguibile, VRAM usata.

Accesso: barra laterale → `⚡ Hardware & GPU`.

---

## 📜 Il Sistema dei Manifesti

Gli agenti AI non sono scatole nere. Sono definiti tramite **Modelfile di Ollama** che specificano:
- **Identità**: "Sei un matematico specializzato in teoria dei numeri..."
- **Regole**: "Non modificare mai i file esterni a `data/`..."
- **Protocollo**: "Prima di agire, analizza il contesto..."
- **Parametri**: Temperatura, finestra di contesto, template di conversazione

### Agenti Disponibili

| File Agente | Modello Base | Versione | Ruolo |
|:------------|:-------------|:---------|:------|
| `sigma_architect.md` | llama3.2 / sigma:latest | **v7.0** | Sigma Architect — amministratore, orchestratore principale, coordinatore di ricerca |
| `agente0.md` | sigma:latest | **v7.2** | Enterprise AI Architect — versione estesa con flusso esecutivo completo |
| `code_architect.md` | sigma:latest | **v1.0** | Full-Stack Developer — modifica codice React/Python con backup e build check |
| `math1.md` | llama3.2 | **v6.0** | Assistente di Ricerca Matematica — genera teoria formale, dimostrazioni, esercizi |
| `math-collatz.md` | llama3.2 | **v1.0** | Specialista Matematico Collatz — teoria dei numeri, analisi mod 6, dimostrazioni formali |
| `test-engineer.md` | llama3.2 | **v1.0** | Ingegnere dei Test — scrive ed esegue test Python scientifici |
| `viz-designer.md` | llama3.2 | **v1.0** | Visualizzatore D3.js — crea grafici interattivi e force graphs |
| `proof-reviewer.md` | llama3.2 | **v1.0** | Revisore Critico — valida dimostrazioni, confuta affermazioni errate |

Tutti i manifesti degli agenti si trovano in `manifesti/` e possono essere caricati tramite API o dalla **Galleria Manifesti** nell'interfaccia.

### Crea un Nuovo Agente in 30 Secondi

```bash
# 1. Crea un file manifesto
cat > manifesti/mio_agente.md << 'EOF'
FROM llama3.2
SYSTEM """
Sei un agente specializzato in biologia molecolare...
Regole:
- Modifica solo file dentro data/biology/
- Usa esclusivamente il provider Ollama per la ricerca
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

## 🤖 Orchestrazione Multi-Agente

Sigma Studio supporta collaborazione multi-agente avanzata:

- **Orchestrazione Parallela**: assegna task a più agenti simultaneamente via `/api/chat/orchestrate`.
- **Context Broker**: contesto condiviso SQLite tra agenti, permettendo loro di referenziare il lavoro altrui.
- **Registro Agenti**: gestione metadati, template agenti e codici colore per l'interfaccia.
- **Sessioni di Ricerca**: scomposizione autonoma di obiettivi complessi con tracciamento del progresso.
- **Pipeline Engine**: esecuzione di pipeline DAG con monitoraggio dello stato e stop/resume.
- **Swarm**: sciami dinamici di agenti con endpoint plan/execute (`/api/swarm/plan`, `/api/swarm/execute`).

---

## 🔒 Sistema Sandbox

Tutte le operazioni degli agenti AI sono rigorosamente confinate:

- **Whitelist Percorsi**: `data/`, `manifesti/`, `sigma_studio/src/`, `scratch/`, `core/`.
- **Struttura Moduli**: solo 5 sottodirectory consentite per modulo: `teoria/`, `test/`, `viz/`, `docs/`, `whitepapers/`.
- **API Sandbox**: crea ambienti isolati, esegui script, installa pacchetti e distruggi ambienti (python/node/fullstack).
- **Backup Manager**: backup automatici prima di modifiche critiche ai file.
- **Supporto Rollback**: annulla modifiche tramite `/api/rollback`.

---

## 📐 Architettura e Documentazione

- **📐 [architettura.md](architettura.md)** — l'architettura completa della piattaforma: internals del backend, layout dei moduli, strutture dati, modello di sicurezza, riferimento endpoint, grafo delle dipendenze e flussi operativi.
- **`manifesti/README.md`** — il sistema dei manifesti per gli agenti AI.

---

## ⚙️ Avvio Rapido

### Prerequisiti

- **Python 3.10+**
- **Node.js / npm**
- **Ollama** (per l'AI locale — [scarica qui](https://ollama.com))

### 🚀 Opzione A — Avvio con un clic (consigliata)

```bash
# 1. Clona il repository
git clone https://github.com/Sigmanih/SigmaStudio.git
cd SigmaStudio

# 2. (Opzionale, su Windows) Installa tutte le dipendenze una sola volta
install_dependencies.bat   # crea .venv, installa dipendenze Python + npm, build frontend

# 3. Avvia Sigma Studio — crea venv, installa dipendenze, build frontend, avvia il server
sigma_studio.bat
```

`sigma_studio.bat` gestisce tutto: creazione dell'ambiente virtuale, dipendenze Python, npm install + build e avvio del server su **http://localhost:8000** — con l'ambiente di accelerazione hardware ottimale (CUDA, parallelismo Ollama, FlashAttention).

### ⌨️ Opzione B — Configurazione Manuale

```bash
# 1. Clona il repository
git clone https://github.com/Sigmanih/SigmaStudio.git
cd SigmaStudio

# 2. Installa le dipendenze Python
pip install -r requirements.txt

# 3. Installa e compila il frontend
cd sigma_studio
npm install
npm run build
cd ..

# 4. Avvia il backend (serve il frontend compilato)
python sigma_server.py
```

Il backend è ora attivo su **http://localhost:8000**.

### 🧪 Verifica Rapida

```bash
# Verifica i moduli core
python -c "from core.sandbox import is_path_allowed; from core.ai_providers import load_ai_config; print('✅ Sistema OK')"

# Verifica l'API delle attività
curl http://localhost:8000/api/tasks

# Verifica Training Lab
curl http://localhost:8000/api/training/datasets/featured

# Verifica Hardware Monitor
curl http://localhost:8000/api/hardware/status

# Verifica MCP Hub
curl http://localhost:8000/api/mcp/servers
```

---

## 🧠 AI Multi-Provider

Sigma Studio supporta **6 provider di modelli AI** configurabili dinamicamente tramite `config.json`:

| Provider | Tipo | Configurazione |
|:---------|:-----|:---------------|
| **Ollama** 🦙 | Locale (gratuito) | `http://localhost:11434` |
| **DeepSeek** 🔍 | Cloud API | `Chiave API` |
| **OpenAI** 🤖 | Cloud API | `Chiave API` |
| **Anthropic (Claude)** 🟣 | Cloud API | `Chiave API` |
| **Groq** ⚡ | Cloud API | `Chiave API` |
| **OpenRouter** 🌐 | Cloud API (multi-modello) | `Chiave API` |

### 4 Modalità Chat

> Principio Sigma: **"Una notifica non lasciata è un'azione mai avvenuta."**

| Modalità | Parametri Backend | Cosa Fa | Notifiche? |
|:---------|:------------------|:--------|:-----------|
| 💬 **Ask** | `allow_actions=false` | L'AI risponde senza modificare nulla | Nessuna (solo chat) |
| 📋 **Plan** | `planning_mode=true` | Analizza un obiettivo e crea task nella Roadmap | ✅ Ogni task genera notifica |
| ⚡ **Execute** | `allow_actions=true` | L'AI crea, modifica o elimina file | ✅ **Automatico**: ogni azione file genera notifica |
| ✅ **Complete Task** | `execute_task_id` + `allow_actions=true` | Esegue un task specifico dalla Roadmap e lo segna completo | ✅ Notifiche per ogni azione + completamento |

---

## 🤝 Aperto ai Contributi!

Sigma Studio è un progetto **open-source** in continua evoluzione e accoglie con entusiasmo contributi da parte della community! Puoi collaborare in molti modi:

- 📜 **Nuovi Manifesti**: crea e condividi nuovi ruoli di agenti (`manifesti/*.md`) specializzati in campi scientifici, ingegneristici o creativi.
- 🎨 **Miglioramenti UI/UX**: estendi il design system in vetro (glassmorphism) in React 19.
- 🔧 **Estensioni Backend**: aggiungi nuovi provider AI, ottimizza la pipeline di test o arricchisci le API REST.
- 🔬 **Pipeline di Ricerca**: integra nuovi strumenti di validazione o template di orchestrazione multi-agente.
- 🧠 **Training Lab**: nuovi metodi di training, supporto per quantization (GGUF, AWQ), nuovi template di dataset, nuove suite di benchmark.
- ⚡ **Hardware & MCP**: integrazione AMD ROCm, nuovi server MCP, metriche aggiuntive.

### Setup di Sviluppo

```bash
# Clona e installa come sopra, poi:
python sigma_server.py          # Backend su :8000
cd sigma_studio && npm run dev  # Hot-reload frontend su :5173
```

Consulta **[architettura.md](architettura.md)** per la struttura completa del progetto e la mappa dei moduli backend.

---

## 📜 Licenza

Questo progetto è rilasciato con una **Doppia Licenza (Dual Licensing)**:
1. **GNU GPL v3**: Per la comunità, sviluppatori open-source, ricerca accademica e scopi educativi.
2. **Licenza Commerciale**: Per aziende, prodotti proprietari e software closed-source.

```
                 SigmaStudio
                     |
        +------------+------------+
        |                         |
     GPL v3                  Commercial License
        |                         |
 Comunità, ricerca          Aziende, prodotti chiusi
 gratis                     pagamento
```

Per informazioni o richieste relative all'acquisto di una licenza commerciale, contattare Diego Saitta.
Consulta il file [LICENSE](LICENSE) per i termini dettagliati della licenza.

---

> *"Un sistema è ben progettato quando un'AI può comprenderlo senza istruzioni esterne."*
> *"Un teorema non è dimostrato finché non è stato confutato, corretto e confutato ancora."*
> *"Una notifica non lasciata è un'azione mai avvenuta."*
> *"Separa le responsabilità, componi i moduli, mantieni la sandbox."*
> — Principi Sigma

---

<p align="center">
  <strong>⭐ Se Sigma Studio ha migliorato il tuo modo di fare ricerca, lascia una stella su GitHub!</strong>
</p>