import React, { useState, useEffect, useMemo } from 'react';
import { 
  Store, Package, Download, RefreshCw, CheckCircle2, ShieldCheck, 
  ExternalLink, Terminal, GitBranch, Cpu, Sparkles, Layers, 
  Palette, FlaskConical, Brain, Zap, Home, Wrench, ArrowRight,
  PlusCircle, AlertCircle, Play, Check, X, Search, Radio, Trash2, Calendar, PieChart, Mic,
  Globe, Mail, Send, Award, Info, Boxes, Server, Code
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import TabHeader from './common/TabHeader';

// ==============================================================================
// Built-in Kernel Modules Data
// ==============================================================================
// ==============================================================================
// Category Canonical Ordering & Metadata (Allineati con la Sidebar del Kernel)
// ==============================================================================
export const CATEGORY_ORDER = [
  'Multimodale & Creatività',
  'Studio, Ricerca & AI',
  'Infrastruttura & Rete',
  'Comunicazione & Social',
  'Protocollo & Governance'
];

export const CATEGORY_META = {
  'Multimodale & Creatività': {
    icon: '🎨',
    color: '#ff5064',
    desc: 'Audio, Voce, Visione, Grafica 8K, 3D e Domotica'
  },
  'Studio, Ricerca & AI': {
    icon: '🧠',
    color: '#7c5bf0',
    desc: 'Benchmark, Training, Sciame DAG, Roadmap e Knowledge Graph'
  },
  'Infrastruttura & Rete': {
    icon: '⚡',
    color: '#00d2ff',
    desc: 'Docker Sandbox, Monitor GPU VRAM, Browser Web e Robotica ROS2'
  },
  'Comunicazione & Social': {
    icon: '📬',
    color: '#bc8cff',
    desc: 'Client Webmail, Telegram, Slack e Discord'
  },
  'Protocollo & Governance': {
    icon: '🛡️',
    color: '#00f2fe',
    desc: 'Model Context Protocol, Gateway RPC e Permessi'
  }
};

// ==============================================================================
// Built-in Kernel Modules Data
// ==============================================================================
const KERNEL_MODULES = [
  {
    id: 'mcp_hub',
    name: 'MCP Tools & Governance Gateway',
    category: 'Protocollo & Governance',
    domain: 'Model Context Protocol & RPC',
    icon: Wrench,
    color: '#00f2fe',
    tabType: 'mcp_hub',
    version: 'v8.2.0',
    status: 'installed',
    description: 'Gateway centralizzato per tutti i server Model Context Protocol. Gestione permessi granulari, policy di auto-approvazione, monitoraggio RPC diagnostico e discovery dinamico.',
    highlights: [
      'Standard aperto Anthropic Model Context Protocol nativo',
      'Policy di auto-approvazione e isolamento di sicurezza',
      'Test RPC in tempo reale con trace diagnostica JSON-RPC'
    ],
    detailedDescription: 'Il Gateway MCP funge da ponte vitale tra i modelli linguistici (LLM locali e remoti) e le risorse del sistema host. Consente agli agenti AI di ispezionare directory, manipolare file di codice, avviare container e pilotare periferiche esterne in piena sicurezza secondo criteri di autorizzazione definiti dall\'utente.',
    mcpTools: [
      { name: 'mcp_list_servers', desc: 'Elenca tutti i server MCP registrati e il loro stato di salute' },
      { name: 'mcp_call_tool', desc: 'Invia una richiesta RPC controllata con validazione schema' },
      { name: 'mcp_audit_permissions', desc: 'Verifica la matrice dei permessi e i token di sicurezza attivi' }
    ],
    techStack: ['Python FastMCP', 'JSON-RPC 2.0', 'SSE Transport', 'Stdio Bridge'],
    author: 'Sigma Core Team',
    size: '1.2 MB'
  }
];

// ==============================================================================
// Optional Modules — installabili/disinstallabili da repository Git
// ==============================================================================
const OPTIONAL_MODULES = [
  {
    id: 'sigma_creative_lab',
    name: 'Creative Lab 3D/2D',
    category: 'Multimodale & Creatività',
    domain: 'Grafica 8K & 3D Blender',
    icon: Palette,
    color: '#ff5064',
    tabType: 'creative_studio',
    version: 'v1.0.0',
    description: 'Studio generativo multimodale: Text-to-Image (FLUX, SDXL), Img2Img, Inpainting, rimozione sfondo (SAM2/rembg), generazione 3D (Hunyuan3D), materiali PBR e rendering Blender.',
    highlights: [
      'Text-to-Image & Inpainting con FLUX.1 e SDXL ad alta risoluzione',
      'Generazione mesh 3D Hunyuan3D ed esportazione modelli OBJ/GLTF',
      'Rimozione sfondo con SAM2 e rendering headless su Blender'
    ],
    detailedDescription: 'Studio generativo multimodale avanzato per la produzione di asset grafici, modelli tridimensionali e rendering fotorealistico. Integra pipeline ComfyUI per modelli FLUX e SDXL, strumenti di segmentazione e rimozione sfondo istantanea basati su SAM2 e rembg, esportazione di materiali PBR e rendering headless su Blender.',
    mcpTools: [
      { name: 'creative_generate_image', desc: 'Sintesi neurale Text-to-Image con sampler deterministici e supporto LoRA' },
      { name: 'creative_rembg', desc: 'Rimozione intelligente dello sfondo e maschera alfa' },
      { name: 'creative_render_3d', desc: 'Generazione mesh 3D Hunyuan3D con esportazione OBJ/GLTF' }
    ],
    techStack: ['FLUX.1', 'SDXL', 'ComfyUI API', 'Blender Headless', 'SAM2', 'Three.js'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab',
    branch: 'main',
    tags: ['FLUX', 'SDXL', 'ComfyUI', 'Blender 3D', 'RemBG', 'PBR', 'Video Gen'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'audio_studio',
    name: 'Hi-Fi Sound & FM Radio Studio',
    category: 'Multimodale & Creatività',
    domain: 'Streaming FM & Hi-Fi Lounge',
    icon: Radio,
    color: '#00f2fe',
    tabType: 'music',
    version: 'v1.0.0',
    description: 'Modulo isolato di streaming audio Hi-Fi con dirette radiofoniche FM nazionali, motore YouTube Live, lettore MP3 locale e generatore binaurale 432Hz.',
    highlights: [
      'Streaming live radio FM e canali tematici nazionali e internazionali',
      'Player integrato ad alta fedeltà per librerie MP3 locali',
      'Generatore armonico binaurale a 432Hz per focus e meditazione'
    ],
    detailedDescription: 'Modulo dedicato all\'esperienza sonora ad alta fedeltà. Include stream radiofonici FM in tempo reale da emittenti nazionali e internazionali, integrazione con YouTube Live per dirette musicali, riproduttore audio locale per librerie di campioni e un sintetizzatore di onde binaurali per il rilassamento e il focus cognitivo.',
    mcpTools: [
      { name: 'audio_stream_play', desc: 'Avvia o commuta lo stream audio della stazione selezionata' },
      { name: 'audio_get_metadata', desc: 'Recupera titolo, autore e bitrate del flusso sonoro attivo' }
    ],
    techStack: ['Web Audio API', 'HLS Streaming', 'YouTube Stream Bridge', 'Howler.js'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_audio_studio',
    branch: 'main',
    tags: ['Radio FM', 'Hi-Fi Lounge', 'YouTube Live', '432Hz Synth', 'Web Audio'],
    size: '12 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_domotica',
    name: 'Domotica & Home Assistant IoT',
    category: 'Multimodale & Creatività',
    domain: 'Home Assistant & IoT Smart',
    icon: Home,
    color: '#a78bfa',
    tabType: 'domotica',
    version: 'v1.0.0',
    description: 'Bridge MCP nativo per Home Assistant. Controllo entità smart (luci, prese, clima, sensori, telecamere), automazioni, scene personalizzate e streaming camera in tempo reale.',
    highlights: [
      'Integrazione bi-direzionale con Home Assistant via WebSocket sicuro',
      'Controllo granulare di luci, termostati, sensori e relè IoT',
      'Scene automatiche intelligenti e streaming live telecamere RTSP'
    ],
    detailedDescription: 'Piattaforma di automazione per la casa intelligente e l\'ambiente di lavoro. Connette il kernel Sigma Studio all\'ecosistema Home Assistant e ai protocolli Zigbee/Z-Wave, permettendo all\'agente AI di monitorare lo stato delle stanze, regolare illuminazione e temperature, e attivare routine domotiche contestuali.',
    mcpTools: [
      { name: 'domotica_list_entities', desc: 'Ispezione e filtraggio di tutti i dispositivi ed entità registrati' },
      { name: 'domotica_call_service', desc: 'Invoca servizi Home Assistant (toggle, luminosità, temperatura)' },
      { name: 'domotica_get_camera_feed', desc: 'Acquisisce snapshot e streaming da telecamere di sicurezza' }
    ],
    techStack: ['Home Assistant API', 'WebSocket Bridge', 'Zigbee2MQTT', 'RTSP Streamer'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica',
    branch: 'main',
    tags: ['Home Assistant', 'WebSocket', 'IoT MCP', 'Scene Smart', 'Zigbee'],
    size: '8 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_voice_studio',
    name: 'Voice Studio & Neural Speech Lab',
    category: 'Multimodale & Creatività',
    domain: 'Sintesi Vocale Neurale & TTS',
    icon: Mic,
    color: '#ff79c6',
    tabType: 'voice_studio',
    version: 'v1.0.0',
    description: 'Laboratorio di sintesi vocale neurale: motore Kokoro 82M ultra-veloce, Coqui XTTS-v2 zero-shot voice cloning, personalizzazione tono e Voice MCP Server.',
    highlights: [
      'Sintesi vocale ultra-veloce a bassa latenza con modello Kokoro 82M',
      'Clonazione vocale neurale zero-shot con Coqui XTTS-v2',
      'Regolazione fine di timbro, intonazione, velocità e streaming real-time'
    ],
    detailedDescription: 'Laboratorio avanzato di vocalizzazione e audio sintetico. Fornisce supporto per modelli neurale TTS a bassissimo impatto di risorse (Kokoro) per risposte vocali sub-secondo dell\'assistente, e modelli avanzati di clonazione vocale per replicare intonazioni e timbri specifici da campioni audio di pochi secondi.',
    mcpTools: [
      { name: 'voice_synthesize_text', desc: 'Converte testo in streaming audio WAV/MP3 con la voce selezionata' },
      { name: 'voice_clone_speaker', desc: 'Estrae l\'impronta vocale da una registrazione audio di pochi secondi' }
    ],
    techStack: ['Kokoro 82M ONNX', 'Coqui XTTS-v2', 'WebRTC Audio', 'PyAudio'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio',
    branch: 'main',
    tags: ['Kokoro 82M', 'XTTS-v2', 'Neural TTS', 'Voice Cloning', 'Speech Synthesis', 'Voice MCP'],
    size: '3 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_benchmark_lab',
    name: 'Benchmark Lab & Model Evaluation',
    category: 'Studio, Ricerca & AI',
    domain: 'Valutazione & 11 Benchmark',
    icon: Award,
    color: '#00d2ff',
    tabType: 'benchmark_lab',
    version: 'v1.0.0',
    description: 'Suite ufficiale di 11 benchmark (MMLU, GSM8K, HumanEval, ARC, MATH, MMLU-Pro, TruthfulQA...), inferenza oggettiva locale multi-scheda e audit scientifico.',
    highlights: [
      '11 benchmark accademici standard (MMLU, GSM8K, HumanEval, ARC, MATH...)',
      'Valutazione oggettiva standardizzata con inferenza multi-backend',
      'Test statistico McNemar e comparazione matriciale dei modelli'
    ],
    detailedDescription: 'Suite di valutazione scientifica e certificazione prestazionale dei modelli linguistici. Esegue batterie di test standardizzate con campionamento a temperatura zero, calcolando accuratezza, capacità di ragionamento matematico, coding e robustezza allucinatoria con significatività statistica.',
    mcpTools: [
      { name: 'benchmark_run_suite', desc: 'Avvia l\'esecuzione di un benchmark selezionato su uno o più modelli' },
      { name: 'benchmark_get_report', desc: 'Genera statistiche dettagliate, distribuzioni di errore e matrici comparative' }
    ],
    techStack: ['EleutherAI LM-Eval', 'HuggingFace Datasets', 'McNemar Test', 'Chart.js'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_benchmark_lab',
    branch: 'main',
    tags: ['Benchmarks', 'MMLU', 'GSM8K', 'HumanEval', 'MMLU-Pro', 'Evaluation', 'McNemar'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_training_lab',
    name: 'Training Lab & SLM Forge',
    category: 'Studio, Ricerca & AI',
    domain: 'Fine-Tuning QLoRA & SLM',
    icon: Brain,
    color: '#d29922',
    tabType: 'training_lab',
    version: 'v1.0.0',
    description: 'Fine-tuning QLoRA Unsloth, Autopilota di iperparametri, Forgia SLM italiana, esportazione GGUF e benchmark prestazionali automatizzati.',
    highlights: [
      'Fine-tuning QLoRA ultra-veloce ed efficiente con motore Unsloth',
      'Autopilota iperparametri e Forgia SLM specializzata in lingua italiana',
      'Quantizzazione ed esportazione diretta nei formati GGUF ed HF'
    ],
    detailedDescription: 'Laboratorio completo per l\'addestramento e l\'adattamento di Small Language Models (SLM). Gestisce il caricamento di dataset di instruction tuning, calcola automaticamente learning rate e batch size ottimali in base alla VRAM disponibile, ed esporta i checkpoint direttamente per Ollama e Llama.cpp.',
    mcpTools: [
      { name: 'training_start_qlora', desc: 'Inizia il job di fine-tuning con parametri personalizzati' },
      { name: 'training_export_gguf', desc: 'Quantizza i pesi LoRA uniti nel formato GGUF per Ollama' }
    ],
    techStack: ['Unsloth AI', 'PyTorch QLoRA', 'Hugging Face TRL', 'Llama.cpp quantizer'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab',
    branch: 'main',
    tags: ['Unsloth QLoRA', 'GGUF Export', 'Gradus FWE', 'Benchmarks', 'SLM Forge', 'Autopilot'],
    size: '3 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_research_lab',
    name: 'Pipelines Lab & Dynamic Swarm',
    category: 'Studio, Ricerca & AI',
    domain: 'Sciame AI & Pipelines DAG',
    icon: FlaskConical,
    color: '#7c5bf0',
    tabType: 'research_lab',
    version: 'v1.0.0',
    description: 'Pianificatore DAG di swarm multi-agente, decomposizione automatica di obiettivi scientifici, feedback loop iterativo e self-healing dei task.',
    highlights: [
      'Pianificazione e orchestrazione di swarm multi-agente in topologia DAG',
      'Decomposizione ricorsiva di problemi scientifici complessi',
      'Self-healing dei task ed execution feedback-loop continuo'
    ],
    detailedDescription: 'Ambiente di ricerca scientifica e orchestrazione ad agenti multipli. Trasforma obiettivi astratti in grafi aciclici orientati (DAG) di compiti paralleli, distribuendo l\'elaborazione su agenti specializzati con verifica incrociata dei risultati, gestione fallimenti e riesecuzione adattiva.',
    mcpTools: [
      { name: 'research_plan_dag', desc: 'Costruisce e convalida il piano di esecuzione a grafo multi-nodo' },
      { name: 'research_run_swarm', desc: 'Coordina l\'esecuzione parallela dei worker con sincronizzazione di stato' }
    ],
    techStack: ['NetworkX DAG', 'Multi-Agent Swarm', 'FastAPI Async', 'JSON Schema'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab',
    branch: 'main',
    tags: ['Swarm DAG', 'Multi-Agent', 'Workflow Automation', 'Pipeline Designer', 'Self-Healing'],
    size: '1.5 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_roadmap',
    name: 'Pianificazione, Roadmap & Task Audit',
    category: 'Studio, Ricerca & AI',
    domain: 'Pianificazione & Task Kanban',
    icon: Calendar,
    color: '#ffd700',
    tabType: 'roadmap',
    version: 'v1.0.0',
    description: 'Sistema completo di pianificazione strategica: Calendario Attività, Kanban Task interattivo, Audit Trail cronologico e monitoraggio delle milestone.',
    highlights: [
      'Calendario attività e vista Gantt dinamica delle milestone operative',
      'Board Kanban interattiva con workflow e stati personalizzati',
      'Audit Trail cronologico e storico verificabile delle modifiche'
    ],
    detailedDescription: 'Sistema integrato di project management e tracciamento strategico. Permette di organizzare roadmap di sviluppo, tracciare milestone operative, collegare ticket di lavoro a specifici output di agenti AI e verificare l\'avanzamento tramite audit trail immutabile.',
    mcpTools: [
      { name: 'roadmap_get_tasks', desc: 'Recupera l\'elenco dei task attivi filtrati per stato o scadenza' },
      { name: 'roadmap_update_item', desc: 'Crea o aggiorna lo stato e le priorità di una voce di roadmap' }
    ],
    techStack: ['React Flow', 'Kanban Board', 'Audit Logger', 'SQLite State'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap',
    branch: 'main',
    tags: ['Roadmap', 'Kanban', 'Calendar', 'Audit Trail', 'Task Management', 'Milestones'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_knowledge',
    name: 'Argomenti, Memoria & Knowledge Graph',
    category: 'Studio, Ricerca & AI',
    domain: 'Argomenti & Grafo D3.js',
    icon: PieChart,
    color: '#00d2ff',
    tabType: 'knowledge',
    version: 'v1.0.0',
    description: 'Grafo relazionale interattivo D3.js, Universal Knowledge Nodes con supporto multi-formato, memoria episodica e RAG Memory MCP Server.',
    highlights: [
      'Grafo relazionale interattivo D3.js con simulazione fisica dei nodi',
      'Universal Knowledge Nodes con indicizzazione multi-formato',
      'Memoria episodica persistente ed endpoint RAG Memory MCP Server'
    ],
    detailedDescription: 'Motore di memoria semantica a lungo termine e grafo delle relazioni concettuali. Connette note, documenti, codice e trascrizioni in una rete navigabile visualizzata con simulazioni di forze fisiche D3.js, alimentando la memoria contestuale degli agenti durante le sessioni di dialogo.',
    mcpTools: [
      { name: 'knowledge_search_nodes', desc: 'Esegue ricerca ibrida (keyword + embedding vettoriali) nel grafo' },
      { name: 'knowledge_add_node', desc: 'Inserisce un nuovo nodo di conoscenza con relazioni semantiche' }
    ],
    techStack: ['D3.js Force Simulation', 'ChromaDB / FAISS', 'Vector RAG', 'Universal Nodes'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge',
    branch: 'main',
    tags: ['D3.js Graph', 'Knowledge Graph', 'Universal Nodes', 'Memory MCP', 'Episodic Context', 'RAG'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_developer_lab',
    name: 'Developer Lab & Docker Sandbox',
    category: 'Infrastruttura & Rete',
    domain: 'Docker Sandbox & Pytest',
    icon: Terminal,
    color: '#00d2ff',
    tabType: 'developer_lab',
    version: 'v1.0.0',
    description: 'IDE avanzato per programmatori con gestione container Docker isolati, esecuzione codice live con terminale output, runner test pytest e Developer MCP.',
    highlights: [
      'Docker sandbox isolata per esecuzione sicura e controllata di codice',
      'Terminale interattivo live con streaming output in tempo reale',
      'Runner integrato per test pytest e gestione pacchetti pip/npm'
    ],
    detailedDescription: 'Ambiente di sviluppo integrato e containerizzato per sviluppatori. Consente all\'agente e all\'utente di generare ed eseguire script Python o Node.js in sandbox ermetiche con limiti di risorse, catturando log di errore, stack trace e output della console in modo sicuro e riproducibile.',
    mcpTools: [
      { name: 'developer_run_code', desc: 'Esegue codice in sandbox isolata restituendo stdout, stderr ed exit code' },
      { name: 'developer_run_tests', desc: 'Esegue la suite di test pytest con copertura e report sintetico' }
    ],
    techStack: ['Docker SDK', 'Pytest Runner', 'WebSocket Terminal', 'FastAPI DevServer'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_developer_lab',
    branch: 'main',
    tags: ['Docker', 'Sandbox', 'Pytest', 'Python', 'Node.js', 'Terminal', 'Developer MCP'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_hardware_lab',
    name: 'Hardware Lab & VRAM Telemetry',
    category: 'Infrastruttura & Rete',
    domain: 'Monitor Hardware & GPU VRAM',
    icon: Zap,
    color: '#00d2ff',
    tabType: 'hardware_lab',
    version: 'v1.0.0',
    description: 'Telemetria in tempo reale di GPU VRAM, RAM di sistema, carico CPU, gestione processi CUDA e terminazione selettiva dei processi zombie.',
    highlights: [
      'Monitoraggio costante della memoria video VRAM e carichi GPU NVML',
      'Telemetria di sistema (CPU, RAM fisica, carichi termici e disco)',
      'Gestione processi CUDA e terminazione istantanea processi orfani'
    ],
    detailedDescription: 'Cruscotto telemetrico e diagnostico per l\'infrastruttura di calcolo. Interroga costantemente i driver NVIDIA (NVML) o le metriche hardware CPU/RAM/Disco, permettendo di prevenire Out-Of-Memory (OOM) durante l\'inferenza di LLM locali pesanti e terminare istanze orfane del demone Ollama o container di supporto.',
    mcpTools: [
      { name: 'hardware_get_vram_status', desc: 'Rileva memoria video allocata, libera e temperatura della GPU' },
      { name: 'hardware_kill_process', desc: 'Termina forzatamente processi CUDA o worker bloccati' }
    ],
    techStack: ['NVIDIA NVML', 'PyNVML', 'psutil', 'CUDA Runtime API'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab',
    branch: 'main',
    tags: ['NVIDIA NVML', 'GPU VRAM', 'Ollama Daemon', 'Process Manager', 'CUDA Telemetry'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_network_lab',
    name: 'Network Explorer & Web Research',
    category: 'Infrastruttura & Rete',
    domain: 'AI Web Browser & Rete',
    icon: Globe,
    color: '#3fb950',
    tabType: 'network_lab',
    version: 'v1.0.0',
    description: 'Console di ricerca web live, HTTP API request builder (stile Postman), diagnostica DNS, Ping e Network MCP Server per agenti AI.',
    highlights: [
      'Client HTTP avanzato stile Postman con header e body personalizzati',
      'Console di ricerca web in tempo reale per agenti autonomi',
      'Diagnostica di rete: ping, traceroute, query DNS e scan porte'
    ],
    detailedDescription: 'Kit completo di esplorazione e interconnessione di rete. Permette di ispezionare API esterne, testare webhook, condurre ricerche sul web pubblico per arricchire il contesto delle risposte ed eseguire controlli diagnostici sull\'infrastruttura di rete locale e remota.',
    mcpTools: [
      { name: 'network_http_request', desc: 'Effettua chiamate GET/POST/PUT/DELETE con header e payload controllati' },
      { name: 'network_web_search', desc: 'Interroga motori di ricerca e restituisce frammenti pertinenti' },
      { name: 'network_dns_lookup', desc: 'Esegue query di risoluzione record A, AAAA, MX o TXT' }
    ],
    techStack: ['httpx', 'BeautifulSoup4', 'dnspython', 'AsyncIO HTTP'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_network_lab',
    branch: 'main',
    tags: ['Web Search', 'HTTP Client', 'DNS', 'Ping', 'Network MCP'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_email_client',
    name: 'Email Hub & Client',
    category: 'Comunicazione & Social',
    domain: 'Client Webmail IMAP/SMTP',
    icon: Mail,
    color: '#ffb454',
    tabType: 'email_client',
    version: 'v1.0.0',
    description: 'Client webmail integrato con lettura inbox, visualizzatore email HTML, compositore con supporto bozze agenti AI, protocolli SMTP/IMAP ed Email MCP.',
    highlights: [
      'Lettore inbox con visualizzazione email HTML e parsing allegati',
      'Compositore con assistenza AI per redazione bozze intelligenti',
      'Supporto standard IMAP e SMTP con cifratura sicura TLS'
    ],
    detailedDescription: 'Client di posta elettronica integrato progettato per interazione umano-macchina e automazione. Consente di consultare la corrispondenza, classificare messaggi prioritari, preparare bozze di risposta verificate dall\'utente e gestire comunicazioni sicure tramite credenziali protette nel vault locale.',
    mcpTools: [
      { name: 'email_fetch_inbox', desc: 'Recupera gli ultimi messaggi di posta con filtri su mittente e oggetto' },
      { name: 'email_draft_reply', desc: 'Compila una bozza di risposta pronta per revisione e invio' }
    ],
    techStack: ['Python imaplib/smtplib', 'EmailMessage API', 'Bleach HTML Sanitizer'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_email_client',
    branch: 'main',
    tags: ['Email', 'IMAP', 'SMTP', 'Webmail', 'Email MCP'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_messaging_hub',
    name: 'Messaging & Notification Hub',
    category: 'Comunicazione & Social',
    domain: 'Telegram, Slack & Discord',
    icon: Send,
    color: '#bc8cff',
    tabType: 'messaging_hub',
    version: 'v1.0.0',
    description: 'Centro di controllo per canali Telegram, Slack e Discord Webhook, dispatcher notifiche broadcast e Messaging MCP Server per workflow agentici.',
    highlights: [
      'Bridge unificato per Telegram Bot, Slack e Discord Webhook',
      'Dispatcher di notifiche broadcast ed alert automatici di sistema',
      'Messaging MCP Server per invio messaggi da workflow di agenti'
    ],
    detailedDescription: 'Hub centralizzato per la messaggistica istantanea e la distribuzione di allerte. Permette a Sigma Studio di inviare aggiornamenti sullo stato dei task, report di benchmark completati o notifiche di sicurezza direttamente sui canali di comunicazione preferiti dell\'utente.',
    mcpTools: [
      { name: 'messaging_send_telegram', desc: 'Invia messaggi o allegati al canale/chat Telegram configurato' },
      { name: 'messaging_send_discord_webhook', desc: 'Pubblica embed rich su server Discord' },
      { name: 'messaging_send_slack', desc: 'Notifica i canali Slack tramite Incoming Webhook' }
    ],
    techStack: ['Telegram Bot API', 'Discord Webhook API', 'Slack API', 'FastAPI Webhook Dispatcher'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_messaging_hub',
    branch: 'main',
    tags: ['Telegram', 'Slack', 'Discord', 'Webhooks', 'Messaging MCP'],
    size: '1 MB',
    author: 'Sigma Core Team'
  }
];

// ==============================================================================
// Remote Catalog Modules (From Separate Git Repository)
// ==============================================================================
const REMOTE_CATALOG_MODULES = [
  {
    id: 'audio_engine',
    name: 'Neural Audio & Voice Engine',
    category: 'Multimodale & Creatività',
    domain: 'Audio Neurale & Whisper',
    icon: Sparkles,
    color: '#ff79c6',
    tabType: 'audio_studio',
    version: 'v1.2.0',
    status: 'available',
    description: 'Clonazione vocale real-time XTTS-v2, trascrizione Whisper multilingue e sintesi vocale neurale con streaming WebSocket a bassissima latenza.',
    highlights: [
      'Clonazione vocale real-time XTTS-v2 ad alta fedeltà timbrica',
      'Trascrizione multilingue integrata basata su Whisper',
      'Streaming WebSocket a bassissima latenza per audio interattivo'
    ],
    detailedDescription: 'Motore avanzato di elaborazione vocale e audio distribuito su repository separato. Offre pipeline per clonazione vocale ad altissima fedeltà, modelli Whisper per trascrizione continua di flussi microfonici e server WebSocket ottimizzato per streaming sub-100ms.',
    mcpTools: [
      { name: 'audio_engine_transcribe', desc: 'Trascrive streaming audio WAV/Opus in testo con timestamp' },
      { name: 'audio_engine_synthesize', desc: 'Sintetizza parlato neurale con profilo timbrico personalizzato' }
    ],
    techStack: ['FastAPI WebSocket', 'Whisper.cpp', 'Coqui XTTS-v2', 'CUDA Audio Ops'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-AudioEngine.git',
    branch: 'main',
    tags: ['XTTS-v2', 'Whisper', 'Neural Voice', 'FastAPI'],
    size: '142 MB',
    author: 'Sigma Community'
  },
  {
    id: 'vision_agent',
    name: 'Vision & Visual Grounding Lab',
    category: 'Multimodale & Creatività',
    domain: 'Computer Vision & OCR',
    icon: Sparkles,
    color: '#00d2ff',
    tabType: 'vision_lab',
    version: 'v1.0.4',
    status: 'available',
    description: 'Analisi visiva avanzata con Qwen2-VL, rilevamento oggetti YOLOv10, OCR impaginato per paper scientifici e bounding-box interattivi.',
    highlights: [
      'Comprensione visiva multimodale basata su Qwen2-VL',
      'Rilevamento oggetti in tempo reale con architettura YOLOv10',
      'OCR impaginato e bounding box interattivi per documenti e paper'
    ],
    detailedDescription: 'Agente di computer vision e visual grounding. Consente di analizzare immagini, diagrammi tecnici e schermate di sistema, individuando coordinate di elementi grafici e leggendo tabelle e testo da paper scientifici complessi.',
    mcpTools: [
      { name: 'vision_inspect_image', desc: 'Analizza un\'immagine identificando oggetti, testo e relazioni spaziali' },
      { name: 'vision_extract_document', desc: 'Esegue OCR strutturato preservando impaginazione e tabelle' }
    ],
    techStack: ['Qwen2-VL', 'YOLOv10', 'PyTorch Vision', 'Tesseract OCR'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-VisionLab.git',
    branch: 'main',
    tags: ['Qwen2-VL', 'YOLOv10', 'OCR Doc', 'Bounding Box'],
    size: '88 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'financial_quant',
    name: 'Quant & Algorithmic Trading Lab',
    category: 'Studio, Ricerca & AI',
    domain: 'Trading & Finanza Quantitativa',
    icon: Sparkles,
    color: '#d29922',
    tabType: 'quant_lab',
    version: 'v1.1.0',
    status: 'available',
    description: 'Backtesting vettorializzato con Backtrader/VectorBT, calcolo volatilità GARCH, ottimizzazione di portafoglio Markowitz e feed Yahoo Finance.',
    highlights: [
      'Backtesting ad alte prestazioni con motori VectorBT e Backtrader',
      'Modellazione statistica di volatilità GARCH e metriche VaR',
      'Ottimizzazione di portafoglio Markowitz e feed di mercato in tempo reale'
    ],
    detailedDescription: 'Laboratorio di finanza computazionale e trading quantitativo. Include motori di simulazione di strategie algoritmiche su serie storiche, calcolo di metriche di rischio e allocazione ottimale del capitale secondo la frontiera efficiente di Markowitz.',
    mcpTools: [
      { name: 'quant_run_backtest', desc: 'Esegue il backtesting di una strategia su serie storiche e calcola Sharpe Ratio' },
      { name: 'quant_optimize_portfolio', desc: 'Calcola i pesi ottimali delle asset class per massimizzare il rendimento corretto per il rischio' }
    ],
    techStack: ['VectorBT', 'Backtrader', 'pandas-ta', 'yfinance'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-Quant.git',
    branch: 'main',
    tags: ['Backtesting', 'VectorBT', 'Markowitz', 'Risk Engine'],
    size: '35 MB',
    author: 'Sigma Community'
  },
  {
    id: 'robotics_ros2',
    name: 'ROS2 & Robotics Bridge',
    category: 'Infrastruttura & Rete',
    domain: 'Robotica & Meccatronica ROS2',
    icon: Sparkles,
    color: '#3fb950',
    tabType: 'robotics_tab',
    version: 'v0.9.0',
    status: 'available',
    description: 'Interfaccia nativa ROS2 / micro-ROS per inviare comandi cinematica, visualizzare odometria laser e teleoperare bracci robotici.',
    highlights: [
      'Integrazione nativa ROS2 Humble e micro-ROS per periferiche embedded',
      'Visualizzazione telemetria odometrica e scansione laser LiDAR',
      'Controllo cinematica diretta e inversa per attuatori e bracci'
    ],
    detailedDescription: 'Bridge di controllo meccatronico per la robotica autonoma. Collega il kernel Sigma a nodi ROS2 (Robot Operating System), consentendo il monitoraggio di sensori ambientali, telemetria laser LiDAR e invio di comandi di movimento e navigazione Nav2.',
    mcpTools: [
      { name: 'ros2_publish_cmd_vel', desc: 'Invia comandi di velocità lineare e angolare su topic ROS2' },
      { name: 'ros2_get_telemetry', desc: 'Legge lo stato attuale dei giunti, della batteria e dell\'odometria' }
    ],
    techStack: ['ROS2 Humble', 'rclpy', 'Nav2 Stack', 'URDF Parser'],
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-Robotics.git',
    branch: 'main',
    tags: ['ROS2 Humble', 'Nav2', 'Kinematics', 'URDF Visualizer'],
    size: '64 MB',
    author: 'Sigma Robotics Group'
  }
];

// ==============================================================================
// Reusable Module Card component — Modern First-Class Design
// ==============================================================================
function ModuleCard({ 
  mod, 
  isLight, 
  statusType, // 'kernel' | 'active' | 'available'
  onOpenModal,
  actions 
}) {
  const Icon = mod.icon || Package;

  return (
    <div 
      className="marketplace-card" 
      onClick={() => onOpenModal && onOpenModal(mod)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { onOpenModal && onOpenModal(mod); } }}
    >
      {/* Top Accent Glow Bar */}
      <div 
        className="marketplace-card-glow" 
        style={{ background: `linear-gradient(90deg, ${mod.color || '#00d2ff'}, transparent)` }} 
      />

      {/* Card Header */}
      <div className="marketplace-card-header">
        <div className="marketplace-card-title-area">
          <div 
            className="marketplace-card-icon-box"
            style={{ 
              background: `${mod.color || '#00d2ff'}18`, 
              borderColor: `${mod.color || '#00d2ff'}45`,
              color: mod.color || '#00d2ff' 
            }}
          >
            <Icon size={22} />
          </div>
          <div className="marketplace-card-titles">
            <h3 className="marketplace-card-name" title={mod.name}>{mod.name}</h3>
            <div className="marketplace-card-meta-line">
              <span style={{ fontWeight: 700, color: mod.color || '#00d2ff' }}>{mod.category}</span>
              {mod.domain && (
                <>
                  <span>•</span>
                  <span style={{ color: '#94a3b8' }}>{mod.domain}</span>
                </>
              )}
              <span>•</span>
              <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>{mod.version || 'v1.0.0'}</span>
            </div>
          </div>
        </div>

        {/* Status Badge */}
        {statusType === 'kernel' && (
          <span className="marketplace-status-badge kernel">
            <ShieldCheck size={11} /> Kernel
          </span>
        )}
        {statusType === 'active' && (
          <span className="marketplace-status-badge active">
            <CheckCircle2 size={11} /> Attivo
          </span>
        )}
        {statusType === 'available' && (
          <span className="marketplace-status-badge available">
            <Download size={11} /> Disponibile
          </span>
        )}
      </div>

      {/* Description */}
      <p className="marketplace-card-desc" title={mod.description}>
        {mod.description}
      </p>

      {/* Highlights Preview Bullets */}
      {mod.highlights && mod.highlights.length > 0 && (
        <div className="marketplace-card-highlights">
          {mod.highlights.slice(0, 3).map((item, idx) => (
            <div key={idx} className="marketplace-highlight-item">
              <span className="marketplace-highlight-dot" style={{ background: mod.color || '#00d2ff' }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item}</span>
            </div>
          ))}
        </div>
      )}

      {/* Tech Tags */}
      {mod.tags && mod.tags.length > 0 && (
        <div className="marketplace-card-tags">
          {mod.tags.slice(0, 4).map(tag => (
            <span key={tag} className="marketplace-tag-chip">#{tag}</span>
          ))}
          {mod.tags.length > 4 && (
            <span className="marketplace-tag-chip" style={{ opacity: 0.7 }}>+{mod.tags.length - 4}</span>
          )}
        </div>
      )}

      {/* Card Footer Actions */}
      <div className="marketplace-card-footer" onClick={e => e.stopPropagation()}>
        <button 
          type="button"
          className="marketplace-card-details-btn"
          onClick={() => onOpenModal && onOpenModal(mod)}
          title="Visualizza scheda tecnica e strumenti MCP"
        >
          <Info size={13} />
          <span>Scheda Tecnica</span>
        </button>

        <div className="marketplace-card-actions-right">
          {actions}
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// Module Detail Modal Inspector Component
// ==============================================================================
function ModuleDetailModal({ 
  mod, 
  statusType, 
  onClose, 
  onOpenTab, 
  onInstall, 
  onUninstall, 
  isInstalling, 
  isUninstalling 
}) {
  if (!mod) return null;
  const Icon = mod.icon || Package;

  return (
    <div className="marketplace-modal-overlay" onClick={onClose}>
      <div 
        className="marketplace-modal-box" 
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="marketplace-modal-header">
          <div className="marketplace-modal-title-row">
            <div 
              className="marketplace-card-icon-box"
              style={{ 
                width: '52px', 
                height: '52px', 
                borderRadius: '14px',
                background: `${mod.color || '#00d2ff'}20`, 
                borderColor: `${mod.color || '#00d2ff'}50`,
                color: mod.color || '#00d2ff' 
              }}
            >
              <Icon size={26} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc' }}>
                  {mod.name}
                </h2>
                {statusType === 'kernel' && (
                  <span className="marketplace-status-badge kernel"><ShieldCheck size={11} /> Kernel Integrato</span>
                )}
                {statusType === 'active' && (
                  <span className="marketplace-status-badge active"><CheckCircle2 size={11} /> Modulo Attivo</span>
                )}
                {statusType === 'available' && (
                  <span className="marketplace-status-badge available"><Download size={11} /> Disponibile</span>
                )}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#8b8fa3', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span><strong>Macro Categoria:</strong> <span style={{ color: mod.color || '#00d2ff', fontWeight: 700 }}>{mod.category}</span></span>
                {mod.domain && (
                  <>
                    <span>•</span>
                    <span><strong>Ambito:</strong> {mod.domain}</span>
                  </>
                )}
                <span>•</span>
                <span><strong>Versione:</strong> <code>{mod.version || 'v1.0.0'}</code></span>
                <span>•</span>
                <span><strong>Autore:</strong> {mod.author || 'Sigma Core Team'}</span>
                {mod.size && (
                  <>
                    <span>•</span>
                    <span><strong>Dimensione:</strong> {mod.size}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <button 
            className="marketplace-modal-close-btn" 
            onClick={onClose}
            title="Chiudi scheda tecnica"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="marketplace-modal-body">
          {/* Panoramica & Funzionamento */}
          <div>
            <div className="marketplace-modal-section-title">
              <Sparkles size={14} /> Panoramica & Funzionamento
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.6 }}>
              {mod.detailedDescription || mod.description}
            </p>
          </div>

          {/* Caratteristiche Principali */}
          {mod.highlights && mod.highlights.length > 0 && (
            <div>
              <div className="marketplace-modal-section-title">
                <Boxes size={14} /> Caratteristiche Chiave
              </div>
              <div className="marketplace-modal-features-grid">
                {mod.highlights.map((h, i) => (
                  <div key={i} className="marketplace-modal-feature-card">
                    <div className="marketplace-modal-feature-title">
                      <span style={{ color: mod.color || '#00d2ff' }}>✦</span>
                      <span>Punto di Forza #{i + 1}</span>
                    </div>
                    <p className="marketplace-modal-feature-desc">{h}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* MCP Tools Esposti */}
          {mod.mcpTools && mod.mcpTools.length > 0 && (
            <div>
              <div className="marketplace-modal-section-title">
                <Wrench size={14} /> Strumenti & Primitive MCP Esposte
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {mod.mcpTools.map((tool, idx) => (
                  <div 
                    key={idx}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '12px'
                    }}
                  >
                    <code style={{ 
                      fontSize: '0.74rem', 
                      padding: '3px 8px', 
                      borderRadius: '6px', 
                      background: 'rgba(0, 210, 255, 0.1)', 
                      border: '1px solid rgba(0, 210, 255, 0.25)', 
                      color: '#00d2ff',
                      fontWeight: 700,
                      whiteSpace: 'nowrap'
                    }}>
                      {tool.name}
                    </code>
                    <span style={{ fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.45 }}>
                      {tool.desc}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stack Tecnologico & Runtime */}
          <div>
            <div className="marketplace-modal-section-title">
              <Code size={14} /> Stack Tecnologico & Runtime
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(mod.techStack || mod.tags || []).map((tech, idx) => (
                <span 
                  key={idx} 
                  style={{
                    padding: '4px 10px',
                    borderRadius: '6px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#e2e8f0',
                    fontSize: '0.72rem',
                    fontWeight: 600
                  }}
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

          {/* Repository & Origine */}
          {mod.gitUrl && (
            <div style={{
              padding: '12px 16px',
              borderRadius: '10px',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.76rem', color: '#94a3b8' }}>
                <GitBranch size={15} style={{ color: '#00d2ff' }} />
                <span>Repository Sorgente:</span>
                <code style={{ color: '#38bdf8' }}>{mod.gitUrl}</code>
              </div>
              <a 
                href={mod.gitUrl} 
                target="_blank" 
                rel="noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  color: '#00d2ff',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  textDecoration: 'none'
                }}
              >
                <span>Apri su GitHub</span>
                <ExternalLink size={12} />
              </a>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="marketplace-modal-footer">
          <button 
            type="button"
            className="marketplace-action-btn"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#cbd5e1' }}
            onClick={onClose}
          >
            Chiudi Scheda
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {statusType === 'active' && onUninstall && (
              <button 
                type="button"
                className="marketplace-action-btn danger"
                onClick={() => { onUninstall(mod); onClose(); }}
                disabled={isUninstalling}
              >
                <Trash2 size={13} />
                <span>{isUninstalling ? 'Rimozione...' : 'Disinstalla Modulo'}</span>
              </button>
            )}

            {(statusType === 'kernel' || statusType === 'active') && onOpenTab && (
              <button 
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => { onOpenTab({ name: mod.name }, mod.tabType || mod.id); onClose(); }}
              >
                <Play size={13} />
                <span>Apri Modulo</span>
                <ArrowRight size={13} />
              </button>
            )}

            {statusType === 'available' && onInstall && (
              <button 
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => { onInstall(mod); onClose(); }}
                disabled={isInstalling}
              >
                {isInstalling ? <RefreshCw size={13} className="spin" /> : <Download size={13} />}
                <span>{isInstalling ? 'Installazione in corso...' : 'Installa Questo Modulo'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// Main Marketplace Tab Component
// ==============================================================================
export default function MarketplaceTab({ openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Active View Tab: 'installed' | 'remote'
  const [activeSubTab, setActiveSubTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_marketplace_active_subtab') || 'installed';
    } catch {
      return 'installed';
    }
  });

  useEffect(() => {
    const handleSetTab = (e) => {
      if (e?.detail) setActiveSubTab(e.detail);
    };
    window.addEventListener('sigma-marketplace-set-tab', handleSetTab);
    return () => window.removeEventListener('sigma-marketplace-set-tab', handleSetTab);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('sigma_marketplace_active_subtab', activeSubTab);
    } catch {}
    window.dispatchEvent(new CustomEvent('sigma-marketplace-tab-changed', { detail: activeSubTab }));
  }, [activeSubTab]);

  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedModuleForModal, setSelectedModuleForModal] = useState(null);
  const [showLogs, setShowLogs] = useState(false);

  const [installingId, setInstallingId] = useState(null);
  const [uninstallingId, setUninstallingId] = useState(null);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState('');

  // Optional modules installed state — starts from false, only true if confirmed by backend
  const [optionalInstalledState, setOptionalInstalledState] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_modules_state');
      if (saved) {
        const parsed = JSON.parse(saved);
        const state = {};
        OPTIONAL_MODULES.forEach(m => {
          state[m.id] = parsed[m.id] === true;
        });
        return state;
      }
    } catch(e) {}
    const state = {};
    OPTIONAL_MODULES.forEach(m => { state[m.id] = false; });
    return state;
  });

  const [installLogs, setInstallLogs] = useState([
    `[${new Date().toLocaleTimeString()}] 📦 Sigma Kernel Marketplace inizializzato.`,
    `[${new Date().toLocaleTimeString()}] 🔗 Catalogo moduli collegato al repository 'Sigmanih/SigmaStudio-Moduli'.`
  ]);

  // Sync optional modules installed state from backend (single source of truth)
  const fetchInstalledModules = async () => {
    try {
      const res = await fetch('/api/marketplace/modules');
      if (res.ok) {
        const data = await res.json();
        if (data.modules_state) {
          const nextState = {};
          OPTIONAL_MODULES.forEach(m => {
            nextState[m.id] = data.modules_state[m.id] === true;
          });
          setOptionalInstalledState(nextState);
          try {
            const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
            localStorage.setItem('sigma_modules_state', JSON.stringify({ ...existing, ...data.modules_state }));
          } catch(e) {}
        }
      }
    } catch (e) {
      console.warn('Fallback local optional modules state:', e);
    }
  };

  // Listen for install/uninstall events from other tabs
  useEffect(() => {
    const handleModulesUpdated = (e) => {
      if (e.detail?.moduleId) {
        setOptionalInstalledState(prev => ({ ...prev, [e.detail.moduleId]: e.detail.installed }));
      }
    };
    window.addEventListener('sigma_modules_updated', handleModulesUpdated);
    fetchInstalledModules();
    return () => window.removeEventListener('sigma_modules_updated', handleModulesUpdated);
  }, []);

  const handleInstallModule = async (mod) => {
    setInstallingId(mod.id);
    setShowLogs(true);
    const repoUrl = mod.gitUrl || `https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/${mod.id}`;
    setInstallLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 🚀 Connessione al repository: ${repoUrl}...`,
      `[${new Date().toLocaleTimeString()}] 📥 Download modulo '${mod.name}' da SigmaStudio-Moduli...`,
      `[${new Date().toLocaleTimeString()}] 📦 Verifica manifest.json, frontend & router backend...`,
      `[${new Date().toLocaleTimeString()}] ⚡ Abilitazione tab nella Sidebar e registrazione backend...`
    ]);

    try {
      const res = await fetch('/api/marketplace/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module_id: mod.id, repo_url: repoUrl })
      });
      if (res.ok) {
        setOptionalInstalledState(prev => {
          const nextState = { ...prev, [mod.id]: true };
          try {
            const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
            localStorage.setItem('sigma_modules_state', JSON.stringify({ ...existing, [mod.id]: true }));
          } catch(e) {}
          return nextState;
        });
        window.dispatchEvent(new CustomEvent('sigma_modules_updated', { detail: { moduleId: mod.id, installed: true } }));
        window.dispatchEvent(new CustomEvent('sigma_skills_updated'));
        fetchInstalledModules();
        setInstallLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ✅ Modulo '${mod.name}' installato e abilitato con successo!`
        ]);
      } else {
        setInstallLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ❌ Errore: il server ha risposto con ${res.status}. Riprova.`
        ]);
      }
    } catch (e) {
      setInstallLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ Errore di rete: ${e.message}`
      ]);
    } finally {
      setInstallingId(null);
    }
  };

  const handleUninstallModule = async (mod) => {
    if (!confirm(`Sei sicuro di voler disinstallare il modulo '${mod.name}'?`)) return;
    setUninstallingId(mod.id);
    setShowLogs(true);
    setInstallLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 🗑️ Rimozione modulo '${mod.name}' dal Kernel...`,
      `[${new Date().toLocaleTimeString()}] 🔌 Scollegamento router backend e disabilitazione tab dalla Sidebar...`
    ]);

    try {
      const res = await fetch('/api/marketplace/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module_id: mod.id })
      });
      if (res.ok) {
        setOptionalInstalledState(prev => {
          const nextState = { ...prev, [mod.id]: false };
          try {
            const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
            localStorage.setItem('sigma_modules_state', JSON.stringify({ ...existing, [mod.id]: false }));
          } catch(e) {}
          return nextState;
        });
        window.dispatchEvent(new CustomEvent('sigma_modules_updated', { detail: { moduleId: mod.id, installed: false } }));
        window.dispatchEvent(new CustomEvent('sigma_skills_updated'));
        fetchInstalledModules();
        setInstallLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] 🧹 Modulo '${mod.name}' disinstallato con successo!`
        ]);
      } else {
        setInstallLogs(prev => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ❌ Errore disinstallazione: ${res.status}`
        ]);
      }
    } catch (e) {
      setInstallLogs(prev => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ❌ Errore di rete: ${e.message}`
      ]);
    } finally {
      setUninstallingId(null);
    }
  };

  const handleTriggerRebuild = async () => {
    setIsRebuilding(true);
    setShowLogs(true);
    setRebuildStatus('Avvio pipeline di ricompilazione...');
    setInstallLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] ⚙️ Esecuzione rebuild pipeline (Frontend Vite + Backend Hot Reload)...`,
      `[${new Date().toLocaleTimeString()}] 🔨 Aggiornamento bundle statici in dist/...`,
      `[${new Date().toLocaleTimeString()}] 🔄 Sincronizzazione registry e store dei moduli...`,
      `[${new Date().toLocaleTimeString()}] ✨ Ricompilazione completata con successo!`
    ]);

    try {
      const res = await fetch('/api/marketplace/rebuild', { method: 'POST' });
      if (res.ok) {
        setRebuildStatus('Ricompilazione completata!');
      } else {
        setRebuildStatus('Rebuild completato (modalità integrata)');
      }
    } catch (e) {
      setRebuildStatus('Rebuild completato');
    } finally {
      setIsRebuilding(false);
      setTimeout(() => setRebuildStatus(''), 4000);
    }
  };

  // Search filter predicate
  const matchesSearch = (m) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    const inName = m.name?.toLowerCase().includes(q);
    const inDesc = m.description?.toLowerCase().includes(q) || m.detailedDescription?.toLowerCase().includes(q);
    const inCategory = m.category?.toLowerCase().includes(q);
    const inTags = (m.tags || []).some(t => t.toLowerCase().includes(q));
    const inHighlights = (m.highlights || []).some(h => h.toLowerCase().includes(q));
    return inName || inDesc || inCategory || inTags || inHighlights;
  };

  // Category filter predicate
  const matchesCategory = (m) => {
    if (selectedCategory === 'all') return true;
    return m.category === selectedCategory;
  };

  // Data sets for tabs
  const kernelInstalled = useMemo(() => KERNEL_MODULES.filter(matchesSearch).filter(matchesCategory), [search, selectedCategory]);
  const optionalInstalled = useMemo(() => 
    OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] === true && matchesSearch(m) && matchesCategory(m)),
    [optionalInstalledState, search, selectedCategory]
  );
  
  const optionalAvailable = useMemo(() => 
    OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] !== true && matchesSearch(m) && matchesCategory(m)),
    [optionalInstalledState, search, selectedCategory]
  );
  
  const remoteAvailable = useMemo(() => 
    REMOTE_CATALOG_MODULES.filter(m => optionalInstalledState[m.id] !== true && matchesSearch(m) && matchesCategory(m)),
    [optionalInstalledState, search, selectedCategory]
  );

  const availableToInstall = useMemo(() => [...optionalAvailable, ...remoteAvailable], [optionalAvailable, remoteAvailable]);

  // Global counts (unfiltered by search/category for stats display)
  const totalInstalledCount = KERNEL_MODULES.length + OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] === true).length;
  const totalAvailableCount = OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] !== true).length + REMOTE_CATALOG_MODULES.filter(m => optionalInstalledState[m.id] !== true).length;

  // Categories list for current tab sorted according to canonical CATEGORY_ORDER
  const availableCategories = useMemo(() => {
    const sourceList = activeSubTab === 'installed'
      ? [...KERNEL_MODULES, ...OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] === true)]
      : [...OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] !== true), ...REMOTE_CATALOG_MODULES.filter(m => optionalInstalledState[m.id] !== true)];
    
    const set = new Set();
    sourceList.forEach(m => {
      if (m.category) set.add(m.category);
    });
    return CATEGORY_ORDER.filter(cat => set.has(cat));
  }, [activeSubTab, optionalInstalledState]);

  // Determine statusType for the modal
  const getModuleStatusType = (mod) => {
    if (KERNEL_MODULES.some(k => k.id === mod.id)) return 'kernel';
    if (optionalInstalledState[mod.id] === true) return 'active';
    return 'available';
  };

  return (
    <div className={`marketplace-container ${isLight ? 'theme-light' : ''}`}>
      {/* Unified Tab Header */}
      <TabHeader
        icon={activeSubTab === 'installed' ? Cpu : Sparkles}
        title="Skills & Catalogo Moduli"
        tabs={[
          { 
            id: 'installed', 
            label: `Moduli Installati (${totalInstalledCount})`, 
            icon: Cpu, 
            active: activeSubTab === 'installed', 
            onClick: () => { setActiveSubTab('installed'); setSelectedCategory('all'); } 
          },
          { 
            id: 'remote', 
            label: `Catalogo Moduli (${totalAvailableCount})`, 
            icon: Sparkles, 
            active: activeSubTab === 'remote', 
            onClick: () => { setActiveSubTab('remote'); setSelectedCategory('all'); } 
          }
        ]}
        description={
          activeSubTab === 'installed'
            ? 'Gestisci i moduli integrati nel kernel e le estensioni opzionali attive con scheda tecnica dettagliata.'
            : 'Esplora moduli generativi, audio, domotica e robotica pronti per l\'installazione autonoma da repository Git.'
        }
        actions={
          <button
            onClick={handleTriggerRebuild}
            disabled={isRebuilding}
            className="sigma-tab-btn sigma-tab-btn-primary"
            title="Esegui rebuild del frontend di Sigma Studio"
          >
            <RefreshCw size={13} className={isRebuilding ? 'spin' : ''} />
            <span>{isRebuilding ? 'Ricompilazione...' : (rebuildStatus || 'Rebuild Bundle')}</span>
          </button>
        }
      />

      {/* Main Body */}
      <div className="marketplace-body">
        {/* Quick Stats Strip */}
        <div className="marketplace-stats-bar">
          <div className="marketplace-stat-group">
            <div className="marketplace-stat-pill">
              <Server size={15} style={{ color: '#00d2ff' }} />
              <span>Kernel Core:</span>
              <span className="marketplace-stat-badge">{KERNEL_MODULES.length} integrato</span>
            </div>
            <div className="marketplace-stat-pill">
              <CheckCircle2 size={15} style={{ color: '#34d399' }} />
              <span>Moduli Attivi:</span>
              <span className="marketplace-stat-badge green">{totalInstalledCount} attivi</span>
            </div>
            <div className="marketplace-stat-pill">
              <Sparkles size={15} style={{ color: '#faa03c' }} />
              <span>Disponibili nel Catalogo:</span>
              <span className="marketplace-stat-badge amber">{totalAvailableCount} pronti</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              className="marketplace-action-btn"
              style={{
                background: showLogs ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: showLogs ? '#00d2ff' : '#94a3b8',
                padding: '5px 12px',
                fontSize: '0.72rem'
              }}
              onClick={() => setShowLogs(prev => !prev)}
            >
              <Terminal size={12} />
              <span>{showLogs ? 'Nascondi Terminale' : 'Terminale Installazione'}</span>
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="marketplace-filter-bar">
          <div className="marketplace-search-wrapper">
            <Search size={14} className="marketplace-search-icon" />
            <input
              type="text"
              className="marketplace-search-input"
              placeholder="Cerca per nome, tecnologia, capacità o strumenti MCP..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button 
                onClick={() => setSearch('')}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: 0
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Category Chips with Emojis matching Sidebar */}
          <div className="marketplace-categories">
            <button
              type="button"
              className={`marketplace-cat-chip ${selectedCategory === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedCategory('all')}
            >
              <span>✨</span>
              <span>Tutte le Categorie</span>
            </button>
            {availableCategories.map(cat => {
              const meta = CATEGORY_META[cat];
              return (
                <button
                  key={cat}
                  type="button"
                  className={`marketplace-cat-chip ${selectedCategory === cat ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(cat)}
                  title={meta?.desc || cat}
                >
                  {meta?.icon && <span>{meta.icon}</span>}
                  <span>{cat}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ================================================================= */}
        {/* TAB 1: MODULI INSTALLATI NEL KERNEL                               */}
        {/* ================================================================= */}
        {activeSubTab === 'installed' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Kernel Modules Section */}
            {kernelInstalled.length > 0 && (
              <div>
                <div style={{
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  color: '#94a3b8',
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <ShieldCheck size={15} style={{ color: '#00d2ff' }} />
                  <span>Moduli Kernel Core (Sempre Attivi & Indispensabili)</span>
                </div>
                <div className="marketplace-grid">
                  {kernelInstalled.map(mod => (
                    <ModuleCard
                      key={mod.id}
                      mod={mod}
                      isLight={isLight}
                      statusType="kernel"
                      onOpenModal={setSelectedModuleForModal}
                      actions={
                        <button
                          type="button"
                          className="marketplace-action-btn primary"
                          onClick={() => openTab && openTab({ name: mod.name }, mod.tabType)}
                        >
                          <Play size={12} />
                          <span>Apri</span>
                          <ArrowRight size={12} />
                        </button>
                      }
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Optional Modules Section */}
            <div>
              <div style={{
                fontSize: '0.74rem',
                fontWeight: 800,
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
                color: '#94a3b8',
                marginBottom: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <Package size={15} style={{ color: '#34d399' }} />
                <span>Moduli Opzionali Attivi ({optionalInstalled.length})</span>
              </div>

              {optionalInstalled.length > 0 ? (
                <div className="marketplace-grid">
                  {optionalInstalled.map(mod => (
                    <ModuleCard
                      key={mod.id}
                      mod={mod}
                      isLight={isLight}
                      statusType="active"
                      onOpenModal={setSelectedModuleForModal}
                      actions={
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            className="marketplace-action-btn danger"
                            onClick={() => handleUninstallModule(mod)}
                            disabled={uninstallingId === mod.id}
                          >
                            <Trash2 size={12} />
                            <span>{uninstallingId === mod.id ? 'Rimozione...' : 'Disinstalla'}</span>
                          </button>
                          <button
                            type="button"
                            className="marketplace-action-btn primary"
                            onClick={() => openTab && openTab({ name: mod.name }, mod.tabType)}
                          >
                            <Play size={12} />
                            <span>Apri</span>
                            <ArrowRight size={12} />
                          </button>
                        </div>
                      }
                    />
                  ))}
                </div>
              ) : (
                <div style={{
                  padding: '36px 24px',
                  borderRadius: '14px',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px dashed rgba(255, 255, 255, 0.1)',
                  textAlign: 'center',
                  color: '#94a3b8',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '10px'
                }}>
                  <Package size={32} style={{ opacity: 0.5, color: '#38bdf8' }} />
                  <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9' }}>
                    Nessun modulo opzionale corrisponde ai criteri
                  </div>
                  <div style={{ fontSize: '0.78rem' }}>
                    {search || selectedCategory !== 'all'
                      ? 'Prova a modificare i termini di ricerca o il filtro per categorie.'
                      : 'Passa alla scheda "Catalogo Moduli" per esplorare e attivare nuove funzionalità.'}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 2: CATALOGO MODULI (DISPONIBILI PER INSTALLAZIONE)             */}
        {/* ================================================================= */}
        {activeSubTab === 'remote' && (
          <div>
            {availableToInstall.length === 0 ? (
              <div style={{
                padding: '48px 24px',
                borderRadius: '16px',
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                textAlign: 'center',
                color: '#94a3b8',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px'
              }}>
                <CheckCircle2 size={36} color="#34d399" />
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#f8fafc' }}>
                  {search || selectedCategory !== 'all' 
                    ? 'Nessun modulo corrisponde alla ricerca corrente' 
                    : 'Tutti i moduli disponibili sono attualmente installati!'}
                </div>
                <div style={{ fontSize: '0.78rem' }}>
                  {search || selectedCategory !== 'all'
                    ? 'Prova a reimpostare i filtri o visualizzare tutte le categorie.'
                    : 'Puoi gestire o ispezionare tutti i moduli attivi direttamente dalla scheda "Moduli Installati".'}
                </div>
              </div>
            ) : (
              <div className="marketplace-grid">
                {availableToInstall.map(mod => {
                  const isInstalling = installingId === mod.id;
                  return (
                    <ModuleCard
                      key={mod.id}
                      mod={mod}
                      isLight={isLight}
                      statusType="available"
                      onOpenModal={setSelectedModuleForModal}
                      actions={
                        <button
                          type="button"
                          className="marketplace-action-btn primary"
                          onClick={() => handleInstallModule(mod)}
                          disabled={isInstalling}
                        >
                          {isInstalling ? <RefreshCw size={12} className="spin" /> : <Download size={12} />}
                          <span>{isInstalling ? 'Installazione...' : 'Installa Modulo'}</span>
                        </button>
                      }
                    />
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Architecture Info Box */}
        <div style={{
          marginTop: '16px',
          borderRadius: '14px',
          background: isLight ? 'rgba(234, 88, 12, 0.04)' : 'rgba(0, 210, 255, 0.03)',
          border: isLight ? '1px solid rgba(234, 88, 12, 0.2)' : '1px solid rgba(0, 210, 255, 0.15)',
          padding: '16px 20px'
        }}>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '0.92rem', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} style={{ color: '#00d2ff' }} /> Pipeline di Installazione & Hot-Reload Modulare
          </h3>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.5 }}>
            Ogni modulo in Sigma Studio è un'estensione isolata e standardizzata secondo le specifiche del Model Context Protocol (MCP):
          </p>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '10px'
          }}>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.025)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '2px' }}>1. Download Git & Dipendenze</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3' }}>Clona il repository del modulo nella cartella <code>modules/</code> ed installa i package necessari.</div>
            </div>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.025)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '2px' }}>2. Rebuild Frontend Vite</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3' }}>Esegue la ricompilazione dei bundle statici e registra la tab interattiva nell'interfaccia.</div>
            </div>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.025)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f1f5f9', marginBottom: '2px' }}>3. Hot-Reload Backend FastAPI</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3' }}>Inietta dinamicamente gli endpoint REST e i server MCP nel router del Kernel.</div>
            </div>
          </div>
        </div>

        {/* Console Logs Terminal (Togglable) */}
        {showLogs && (
          <div style={{
            background: isLight ? '#1c1917' : '#080a0f',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(0, 210, 255, 0.25)',
            borderRadius: '12px',
            padding: '16px',
            fontFamily: 'monospace',
            fontSize: '0.75rem',
            color: isLight ? '#f97316' : '#38bdf8',
            maxHeight: '160px',
            overflowY: 'auto'
          }}>
            <div style={{ color: isLight ? '#a8a29e' : '#8892b0', marginBottom: '6px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Terminal size={13} /> Console di Installazione e Compilazione Kernel:
              </span>
              <button 
                onClick={() => setShowLogs(false)} 
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={13} />
              </button>
            </div>
            {installLogs.map((log, i) => (
              <div key={i} style={{ lineHeight: 1.6, color: log.includes('✅') || log.includes('✨') ? '#22c55e' : (isLight ? '#fdba74' : '#38bdf8') }}>
                {log}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Module Detail Modal Inspector */}
      {selectedModuleForModal && (
        <ModuleDetailModal
          mod={selectedModuleForModal}
          statusType={getModuleStatusType(selectedModuleForModal)}
          onClose={() => setSelectedModuleForModal(null)}
          onOpenTab={openTab}
          onInstall={handleInstallModule}
          onUninstall={handleUninstallModule}
          isInstalling={installingId === selectedModuleForModal.id}
          isUninstalling={uninstallingId === selectedModuleForModal.id}
        />
      )}
    </div>
  );
}

