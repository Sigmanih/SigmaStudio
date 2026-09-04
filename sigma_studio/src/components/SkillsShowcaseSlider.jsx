import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Palette, FlaskConical, Brain, Zap, Mic, Terminal, Home, 
  PieChart, Calendar, Globe, Mail, Send, Radio, DownloadCloud, 
  Wrench, ChevronLeft, ChevronRight, Play, Pause, Search, 
  ExternalLink, Sparkles, CheckCircle2, ArrowRight, BookOpen, 
  Layers, Cpu, ShieldCheck, Download, Code, Info, X
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';

// ==============================================================================
// CATALOGO COMPLETO DELLE SKILLS & MODULI (KERNEL + GITHUB OPEN SOURCE)
// ==============================================================================
export const SKILLS_CATALOG = [
  {
    id: 'sigma_creative_lab',
    name: 'Creative Lab 3D/2D',
    category: 'Multimodale & Grafica',
    categoryKey: 'multimodal',
    icon: Palette,
    color: '#ff5064',
    tabType: 'creative_studio',
    version: 'v1.0.0',
    size: '2 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab',
    image: '/images/creative_lab_banner.jpg',
    badge: 'STUDIO 3D & GENERAZIONE 8K',
    objective: 'Crea render 3D fotorealistici con Blender headless, genera grafiche 8K (FLUX/SDXL) e sconta soggetti in un click con SAM2, tutto accelerato dalla tua GPU.',
    components: [
      {
        icon: '🖼️',
        title: 'Grafica 8K FLUX/SDXL',
        desc: 'Generazione fotorealistica da testo con prompt positivi/negativi e controllo seed.'
      },
      {
        icon: '🧊',
        title: 'Blender 3D Headless',
        desc: 'Rendering procedurale di scene 3D, luci volumetriche e animazioni da Python.'
      },
      {
        icon: '🪄',
        title: 'SAM2 & RemBG Segmenter',
        desc: 'Scontorno istantaneo chirurgico del soggetto con esportazione trasparente.'
      },
      {
        icon: '🧱',
        title: 'Mappe PBR Fisiche',
        desc: 'Generazione di texture Normal, Roughness e Height per motori 3D e videogame.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Scegli la Modalità', text: 'Accedi al Creative Lab e seleziona il tab tra Generatore 8K, Blender 3D o Texturizzatore PBR.' },
      { step: '2', title: 'Imposta Prompt & Parametri', text: 'Descrivi la scena o fornisci uno script 3D, regolando risoluzione, passi e campionamento.' },
      { step: '3', title: 'Esporta o Invia in Chat', text: 'Salva l\'asset in alta risoluzione o invialo alla Chat AI per analisi visiva multimodale.' }
    ],
    tags: ['FLUX.1', 'SDXL', 'Blender 3D', 'RemBG', 'PBR Maps', 'SAM2'],
    samplePrompt: 'Genera un render 3D fotorealistico di un processore quantistico a luce blu neon con riflessi metallici in stile cyberpunk.'
  },
  {
    id: 'sigma_research_lab',
    name: 'Pipelines Lab & Dynamic Swarm',
    category: 'Studio & AI',
    categoryKey: 'studio_ai',
    icon: FlaskConical,
    color: '#7c5bf0',
    tabType: 'research_lab',
    version: 'v1.0.0',
    size: '1.5 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab',
    image: '/images/pipelines_lab_banner.jpg',
    badge: 'SCIAME AI & AUTO-HEALING',
    objective: 'Coordina uno sciame di agenti AI specializzati (Architetto, Matematico, Coder) per risolvere problemi scientifici complessi con pipeline parallele e auto-correzione del codice.',
    components: [
      {
        icon: '🤖',
        title: 'Team Swarm Multi-Agente',
        desc: '4 ruoli cooperanti: Architetto, Sviluppatore, Matematico e Validatore.'
      },
      {
        icon: '📈',
        title: 'Pianificatore DAG Parallelo',
        desc: 'Scomposizione dell\'obiettivo in compiti paralleli con risoluzione dipendenze.'
      },
      {
        icon: '🛡️',
        title: 'Self-Healing Automatico',
        desc: 'Ispezione autonoma dei log e correzione del codice se i test Pytest falliscono.'
      },
      {
        icon: '📑',
        title: 'Deliverable Completi',
        desc: 'Produzione automatica di formulari LaTeX, script Python e test unitari.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Definisci l\'Obiettivo', text: 'Inserisci la specifica del problema o il modulo che vuoi ricercare e sviluppare da zero.' },
      { step: '2', title: 'Genera la Roadmap DAG', text: 'Lo Swarm crea l\'alberatura dei compiti e assegna le mansioni agli agenti in parallelo.' },
      { step: '3', title: 'Valida & Integra', text: 'Segui l\'avanzamento in tempo reale con i test automatici fino al salvataggio finale.' }
    ],
    tags: ['Swarm DAG', 'Multi-Agent', 'Self-Healing', 'Pytest Runner', 'LaTeX Gen'],
    samplePrompt: 'Crea una pipeline di ricerca per modellare la dinamica dei fluidi con equazioni di Navier-Stokes e codice di simulazione.'
  },
  {
    id: 'sigma_training_lab',
    name: 'Training Lab & SLM Forge',
    category: 'Studio & AI',
    categoryKey: 'studio_ai',
    icon: Brain,
    color: '#d29922',
    tabType: 'training_lab',
    version: 'v1.0.0',
    size: '3 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab',
    image: '/images/training_lab_hero.jpg',
    badge: 'FINE-TUNING QLORA 5X & FORGIA GGUF',
    objective: 'Addestra e forgia Small Language Models (SLM) in locale con Unsloth QLoRA 5x più veloce, autopilota di iperparametri ed export diretto in GGUF per SigmaEngine.',
    components: [
      {
        icon: '🚀',
        title: 'Unsloth QLoRA 5x Fast',
        desc: 'Fine-tuning accelerato su GPU NVIDIA con consumo di memoria VRAM ridotto.'
      },
      {
        icon: '🤖',
        title: 'Autopilota Iperparametri',
        desc: 'Taratura autonoma di Learning Rate, Batch Size e LoRA Rank in base all\'hardware.'
      },
      {
        icon: '🔨',
        title: 'Forgia SLM & Export GGUF',
        desc: 'Conversione e quantizzazione (Q4_K_M, Q8_0) pronta per la Chat AI e SigmaEngine.'
      },
      {
        icon: '📊',
        title: '11 Benchmark Ufficiali',
        desc: 'Valutazione rigorosa di accuratezza su MMLU, GSM8K, HumanEval e ARC.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Carica il Dataset', text: 'Importa file di addestramento in formato JSONL o seleziona un dataset di sistema preconfigurato.' },
      { step: '2', title: 'Avvia l\'Autopilota', text: 'Seleziona il modello base e premi "Avvia Autopilota" per calibrare i pesi LoRA in tempo reale.' },
      { step: '3', title: 'Esporta in GGUF', text: 'Converti i checkpoint addestrati in formato GGUF e caricali nella Chat con un click.' }
    ],
    tags: ['Unsloth QLoRA', 'GGUF Export', 'SLM Forge', 'Autopilot', '11 Benchmarks'],
    samplePrompt: 'Specializza il modello Qwen-2.5-7B sul dominio giuridico italiano ed esegui il benchmark di accuratezza.'
  },
  {
    id: 'sigma_voice_studio',
    name: 'Voice Studio & Neural Speech Lab',
    category: 'Audio & Voce',
    categoryKey: 'audio_voice',
    icon: Mic,
    color: '#ff79c6',
    tabType: 'voice_studio',
    version: 'v1.0.0',
    size: '3 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio',
    image: '/images/account_voice_banner.jpg',
    badge: 'KOKORO 82M & VOCE REAL-TIME',
    objective: 'Sintesi vocale neurale real-time (<80ms) con Kokoro 82M e clonazione vocale zero-shot da 5s di audio per risposte parlate direttamente nella Chat AI.',
    components: [
      {
        icon: '⚡',
        title: 'Kokoro 82M Real-Time',
        desc: 'Generazione vocale fluida a bassissima latenza (<80ms) per streaming parlato.'
      },
      {
        icon: '🎙️',
        title: 'Clonazione Zero-Shot XTTS-v2',
        desc: 'Replica fedele di qualsiasi timbro vocale con soli 5 secondi di audio sorgente.'
      },
      {
        icon: '🎚️',
        title: 'Controllo Timbro & Velocità',
        desc: 'Regolazione fine di pitch, cadenza, enfasi espressiva e pause naturali.'
      },
      {
        icon: '🔌',
        title: 'Voice MCP per la Chat',
        desc: 'Permette agli agenti della Chat di leggere le risposte a voce alta in tempo reale.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Seleziona Voce o Clona', text: 'Scegli uno dei preset vocali italiani/multilingue o carica un file WAV per clonare una nuova voce.' },
      { step: '2', title: 'Genera & Ascolta', text: 'Digita il testo da riprodurre e ascolta l\'anteprima istantanea con visualizzatore a onde sonore.' },
      { step: '3', title: 'Attiva Speaker in Chat', text: 'Abilita "Speaker Agente: ON" nella Chat per ascoltare le risposte mentre vengono generate.' }
    ],
    tags: ['Kokoro 82M', 'XTTS-v2', 'Voice Cloning', 'Neural TTS', 'Voice MCP'],
    samplePrompt: 'Sintetizza questo testo con tono accademico caloroso e cadenza naturale a 1.05x di velocità.'
  },
  {
    id: 'sigma_developer_lab',
    name: 'Developer Lab & Docker Sandbox',
    category: 'Infrastruttura & Rete',
    categoryKey: 'infra_net',
    icon: Terminal,
    color: '#00d2ff',
    tabType: 'developer_lab',
    version: 'v1.0.0',
    size: '2 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_developer_lab',
    image: '/images/skills_engines_banner.jpg',
    badge: 'SANDBOX DOCKER & RUNNER PYTEST',
    objective: 'Esegui, testa e collauda codice Python, Node.js e Bash in ambienti container Docker totalmente isolati con test unitari Pytest e terminale ANSI in streaming.',
    components: [
      {
        icon: '🐳',
        title: 'Sandbox Container Docker',
        desc: 'Esecuzione protetta di script Python, Node.js e Bash isolata dal PC host.'
      },
      {
        icon: '💻',
        title: 'Terminale Live Interattivo',
        desc: 'Console integrata con streaming output real-time, colori ANSI e input diretto.'
      },
      {
        icon: '🧪',
        title: 'Runner Automatico Pytest',
        desc: 'Esecuzione istantanea dei test con report visuale dei tempi di risposta.'
      },
      {
        icon: '📦',
        title: 'Gestore Dipendenze Dinamico',
        desc: 'Installazione veloce di pacchetti pip e librerie npm nell\'ambiente sandbox.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Scrivi o Carica Codice', text: 'Utilizza l\'editor per visualizzare e modificare script, librerie e moduli computazionali.' },
      { step: '2', title: 'Esegui nel Container', text: 'Clicca "Esegui in Sandbox" per lanciare il processo nel container Docker protetto.' },
      { step: '3', title: 'Verifica con Pytest', text: 'Lancia la suite di test unitari con un click per validare la correttezza algoritmica.' }
    ],
    tags: ['Docker Sandbox', 'Pytest Runner', 'ANSI Terminal', 'Python 3.12', 'Developer MCP'],
    samplePrompt: 'Esegui lo script di benchmark matriciale all\'interno del container Docker e restituisci il grafico delle performance.'
  },
  {
    id: 'sigma_hardware_lab',
    name: 'Hardware Lab & VRAM Telemetry',
    category: 'Infrastruttura & Rete',
    categoryKey: 'infra_net',
    icon: Zap,
    color: '#00f2fe',
    tabType: 'hardware_lab',
    version: 'v1.0.0',
    size: '1 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab',
    image: '/images/hardware_cluster_lab.jpg',
    badge: 'TELEMETRIA GPU & FLUSH VRAM',
    objective: 'Telemetria in tempo reale di GPU VRAM, CPU e temperature con svuotamento forzato della memoria video e arresto immediato dei processi bloccati.',
    components: [
      {
        icon: '📊',
        title: 'Telemetria SVG Live',
        desc: 'Sparkline continua con monitoraggio di GPU/NPU, VRAM, CPU e RAM di sistema.'
      },
      {
        icon: '🧹',
        title: 'Svuotamento Rapido VRAM',
        desc: 'Flush forzato istantaneo della memoria video GPU senza riavviare il sistema.'
      },
      {
        icon: '🛑',
        title: 'Process Killer PID',
        desc: 'Ispezione e terminazione forzata di processi CUDA o server AI bloccati.'
      },
      {
        icon: '⚙️',
        title: 'Tuning Multi-Dispositivo',
        desc: 'Distribuzione automatica dei layer tra GPU, acceleratori e RAM di sistema.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Controlla l\'Occupazione', text: 'Apri la telemetria per visualizzare i gigabyte di VRAM liberi prima di caricare un modello.' },
      { step: '2', title: 'Libera Risorse Saturate', text: 'Se la memoria video è piena, clicca "Flush VRAM" per scaricare i modelli inattivi.' },
      { step: '3', title: 'Ispeziona i Processi', text: 'Monitora la tabella dei processi CUDA attivi e arresta selettivamente quelli non necessari.' }
    ],
    tags: ['NVIDIA NVML', 'GPU VRAM', 'Multi-GPU', 'CUDA Monitor', 'Process Killer'],
    samplePrompt: 'Mostra la telemetria attuale della memoria video GPU e termina i processi orfani che occupano VRAM.'
  },
  {
    id: 'sigma_domotica',
    name: 'Domotica & Home Assistant IoT',
    category: 'Multimodale & Grafica',
    categoryKey: 'multimodal',
    icon: Home,
    color: '#10b981',
    tabType: 'domotica',
    version: 'v1.0.0',
    size: '8 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica',
    image: '/images/domotica_smart_hub.jpg',
    badge: 'SMART HOME & IOT MCP GATEWAY',
    objective: 'Controlla la tua smart home via Home Assistant: gestisci luci, clima, sensori e routine sia dalla dashboard interattiva sia tramite comandi vocali/chat.',
    components: [
      {
        icon: '💡',
        title: 'Controllo Luci & Clima',
        desc: 'Regolazione istantanea di tonalità RGB, dimmer, termostati e condizionatori.'
      },
      {
        icon: '🌡️',
        title: 'Sensori Ambientali Live',
        desc: 'Monitoraggio continuo di temperatura, umidità, Watt e presenza.'
      },
      {
        icon: '🎬',
        title: 'Scene & Routine AI',
        desc: 'Attivazione di scenari complessi ("Studio Concentrato", "Notte", "Relax").'
      },
      {
        icon: '🔒',
        title: 'Governance MCP Protetta',
        desc: 'Richiesta di conferma esplicita per azioni fisiche critiche sui dispositivi.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Collega Home Assistant', text: 'Inserisci l\'URL del tuo server Home Assistant locale e il Long-Lived Access Token.' },
      { step: '2', title: 'Gestisci le Entità', text: 'Accendi luci, imposta temperature e monitora i sensori dalla dashboard visuale interattiva.' },
      { step: '3', title: 'Controlla via Chat AI', text: 'Chiedi all\'agente in linguaggio naturale: "Accendi le luci dello studio e imposta il clima a 21 gradi".' }
    ],
    tags: ['Home Assistant', 'IoT MCP', 'Zigbee', 'Smart Lighting', 'Thermostats'],
    samplePrompt: 'Imposta la scena "Studio Notturno" accendendo le luci soffuse a tonalità calda e verificando la temperatura.'
  },
  {
    id: 'sigma_knowledge',
    name: 'Argomenti, Memoria & Knowledge Graph',
    category: 'Studio & AI',
    categoryKey: 'studio_ai',
    icon: PieChart,
    color: '#00d2ff',
    tabType: 'knowledge',
    version: 'v1.0.0',
    size: '2 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge',
    image: '/images/knowledge_graph_banner.jpg',
    badge: 'GRAFO D3.JS & MEMORIA RAG',
    objective: 'Mappa concettuale interattiva in D3.js, rendering KaTeX di formule matematiche e memoria RAG episodica per dare agli agenti AI un contesto infallibile.',
    components: [
      {
        icon: '🌐',
        title: 'Grafo Force-Directed D3.js',
        desc: 'Navigazione visiva dei nodi concettuali con collegamenti dinamici tra materie.'
      },
      {
        icon: '📐',
        title: 'Formulario & Teoria LaTeX',
        desc: 'Rendering tipografico immediato di formule matematiche e scientifiche KaTeX.'
      },
      {
        icon: '🧠',
        title: 'Memoria Episodica RAG',
        desc: 'Indicizzazione semantica per recuperare appunti e decisioni passate.'
      },
      {
        icon: '📑',
        title: 'Nodi Conoscenza Organizzati',
        desc: 'Strutturazione logica di cartelle in data/ con codice, test e whitepaper.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Esplora il Grafo', text: 'Clicca e trascina i nodi nella Mappa per esplorare le relazioni e i collegamenti tra gli argomenti.' },
      { step: '2', title: 'Crea Nuovi Nodi', text: 'Aggiungi nuovi temi di studio con l\'editor visuale specificando titolo, descrizione e nodo genitore.' },
      { step: '3', title: 'Usa come Memoria AI', text: 'Gli agenti interrogheranno automaticamente questo grafo per rispondere con precisione contestuale.' }
    ],
    tags: ['D3.js Graph', 'RAG Memory', 'LaTeX KaTeX', 'Knowledge Base'],
    samplePrompt: 'Trova tutti i nodi collegati alla teoria delle onde elettromagnetiche e apri la scheda di approfondimento.'
  },
  {
    id: 'sigma_roadmap',
    name: 'Pianificazione, Roadmap & Task Audit',
    category: 'Studio & AI',
    categoryKey: 'studio_ai',
    icon: Calendar,
    color: '#faa03c',
    tabType: 'roadmap',
    version: 'v1.0.0',
    size: '1 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap',
    image: '/images/roadmap_plan_banner.jpg',
    badge: 'KANBAN, CALENDARIO & AUDIT LOG',
    objective: 'Organizza progetti e compiti con tabellone Kanban drag & drop, calendario scadenze e registro cronologico di audit per monitorare ogni operazione completata.',
    components: [
      {
        icon: '📌',
        title: 'Tabellone Kanban Drag & Drop',
        desc: 'Gestione intuitiva: Da Fare, In Corso, In Revisione e Completati.'
      },
      {
        icon: '📅',
        title: 'Calendario Milestone',
        desc: 'Visualizzazione cronologica delle scadenze e pianificazione sessioni.'
      },
      {
        icon: '📑',
        title: 'Registro Audit Cronologico',
        desc: 'Tracciamento con timestamp di ogni operazione svolta dagli agenti AI.'
      },
      {
        icon: '🎯',
        title: 'Prioritizzazione Intelligente',
        desc: 'Evidenziazione automatica dei task critici collegati ai moduli.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Aggiungi un Task', text: 'Definisci titolo, priorità, data di scadenza e modulo associato.' },
      { step: '2', title: 'Aggiorna lo Stato', text: 'Trascina i task tra le colonne del Kanban man mano che procedi nello studio.' },
      { step: '3', title: 'Consulta l\'Audit', text: 'Verifica il verbale cronologico per ripercorrere tutte le tappe completate.' }
    ],
    tags: ['Kanban Board', 'Roadmap', 'Milestone Calendar', 'Audit Trail', 'Timeline'],
    samplePrompt: 'Aggiungi un task prioritario per la stesura del whitepaper di fisica quantistica con scadenza venerdì.'
  },
  {
    id: 'sigma_network_lab',
    name: 'Network Explorer & Web Research',
    category: 'Infrastruttura & Rete',
    categoryKey: 'infra_net',
    icon: Globe,
    color: '#3fb950',
    tabType: 'network_lab',
    version: 'v1.0.0',
    size: '1 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_network_lab',
    image: '/images/skills_engines_banner.jpg',
    badge: 'RICERCA WEB & CLIENT REST MCP',
    objective: 'Ricerche web in tempo reale, collaudo di API HTTP REST (GET/POST) e diagnostica di rete DNS/Ping per nutrire le risposte degli agenti con dati aggiornati.',
    components: [
      {
        icon: '🔍',
        title: 'Ricerca Web Live',
        desc: 'Interrogazione del web con estrazione di testo pulito e sintesi delle fonti.'
      },
      {
        icon: '📡',
        title: 'Client HTTP API Builder',
        desc: 'Compositore di chiamate REST (GET, POST) con headers e body JSON.'
      },
      {
        icon: '🌐',
        title: 'Diagnostica DNS & Ping',
        desc: 'Verifica immediata di latenza, risoluzione record e connettività host.'
      },
      {
        icon: '🔌',
        title: 'Network MCP Server',
        desc: 'Abilita gli agenti a scaricare documentazione tecnica da internet in autonomia.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Esegui Ricerche Web', text: 'Cerca articoli e documentazione tecnica per arricchire il contesto della sessione.' },
      { step: '2', title: 'Testa Endpoint API', text: 'Invia richieste HTTP verso qualsiasi web service e visualizza le risposte JSON formattate.' },
      { step: '3', title: 'Valida la Rete', text: 'Esegui diagnostica di connettività per verificare lo stato di endpoint remoti.' }
    ],
    tags: ['Web Search', 'HTTP Client', 'API Tester', 'DNS Lookup', 'Network MCP'],
    samplePrompt: 'Esegui una richiesta GET verso l\'endpoint di test e mostra il payload JSON di risposta.'
  },
  {
    id: 'sigma_email_client',
    name: 'Email Hub & Client',
    category: 'Comunicazione & Social',
    categoryKey: 'comm_social',
    icon: Mail,
    color: '#ffb454',
    tabType: 'email_client',
    version: 'v1.0.0',
    size: '1 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_email_client',
    image: '/images/hero_banner.jpg',
    badge: 'WEBMAIL SICURA & BOZZE AI',
    objective: 'Client webmail sicuro IMAP/SMTP con compositore AI per redigere risposte perfette e inviare automaticamente report periodici sulle attività.',
    components: [
      {
        icon: '📬',
        title: 'Inbox & Cartelle IMAP',
        desc: 'Sincronizzazione della posta in arrivo, allegati e navigazione dei thread.'
      },
      {
        icon: '✍️',
        title: 'Compositore con Bozze AI',
        desc: 'Redazione e correzione stilistica assistita per risposte professionali.'
      },
      {
        icon: '🔒',
        title: 'Sicurezza SSL/TLS',
        desc: 'Connessioni protette e salvataggio cifrato delle credenziali utente.'
      },
      {
        icon: '🔌',
        title: 'Email MCP Server',
        desc: 'Consente agli agenti di inviare report periodici o notifiche via email.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Configura l\'Account', text: 'Inserisci i parametri del tuo provider di posta IMAP/SMTP in modo protetto.' },
      { step: '2', title: 'Leggi & Organizza', text: 'Consulta la casella di posta con rendering HTML protetto e ricerca rapida tra i messaggi.' },
      { step: '3', title: 'Componi con l\'AI', text: 'Fatti aiutare dall\'assistente a scrivere email chiare, sintetiche e impeccabili.' }
    ],
    tags: ['Email Client', 'IMAP', 'SMTP', 'HTML Mail', 'AI Drafts', 'Email MCP'],
    samplePrompt: 'Prepara una bozza di risposta cordiale confermando la ricezione del documento e allegando il report.'
  },
  {
    id: 'sigma_messaging_hub',
    name: 'Messaging & Notification Hub',
    category: 'Comunicazione & Social',
    categoryKey: 'comm_social',
    icon: Send,
    color: '#bc8cff',
    tabType: 'messaging_hub',
    version: 'v1.0.0',
    size: '1 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_messaging_hub',
    image: '/images/chat_swarm_banner.jpg',
    badge: 'TELEGRAM, DISCORD & MESSAGING MCP',
    objective: 'Invia notifiche push istantanee su Telegram Bot, Discord e Slack al termine di elaborazioni Swarm o fine addestramento LoRA, interagendo anche da mobile.',
    components: [
      {
        icon: '🤖',
        title: 'Gateway Telegram Bot',
        desc: 'Ricezione aggiornamenti ed invio comandi all\'AI direttamente da mobile.'
      },
      {
        icon: '💬',
        title: 'Webhook Slack & Discord',
        desc: 'Invio di messaggi formattati nei canali di team per report e log.'
      },
      {
        icon: '🔔',
        title: 'Notifiche Broadcast',
        desc: 'Avvisi centralizzati per completamento training LoRA e pipeline Swarm.'
      },
      {
        icon: '🔌',
        title: 'Messaging MCP Server',
        desc: 'Invocabile direttamente dagli agenti per inviare notifiche push su smartphone.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Imposta i Token', text: 'Configura il Bot Token di Telegram o l\'URL del Webhook Discord/Slack.' },
      { step: '2', title: 'Invia Notifiche di Prova', text: 'Testa la corretta ricezione dei messaggi broadcast con un click.' },
      { step: '3', title: 'Automatizza gli Alert', text: 'Ricevi una notifica push quando una pipeline DAG o un training LoRA hanno terminato.' }
    ],
    tags: ['Telegram Bot', 'Slack Webhook', 'Discord Webhook', 'Broadcast', 'Messaging MCP'],
    samplePrompt: 'Invia un messaggio Telegram di notifica per segnalare che la pipeline DAG ha completato tutti i test con successo.'
  },
  {
    id: 'audio_studio',
    name: 'Hi-Fi Sound & FM Radio Studio',
    category: 'Audio & Voce',
    categoryKey: 'audio_voice',
    icon: Radio,
    color: '#00f2fe',
    tabType: 'music',
    version: 'v1.0.0',
    size: '12 MB',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_audio_studio',
    image: '/images/hero_banner.jpg',
    badge: 'RADIO FM LIVE & ONDE 432HZ',
    objective: 'Radio FM nazionali in streaming continuo, sintetizzatore di onde binaurali a 432Hz per il massimo focus mentale e riproduttore MP3 con spettrogramma live.',
    components: [
      {
        icon: '📻',
        title: 'Dirette Radio FM Nazionali',
        desc: 'Streaming a bassa latenza di RTL, 105, Radio 24, Deejay, Rai e Kiss Kiss.'
      },
      {
        icon: '🎵',
        title: 'Generatore Onde 432Hz',
        desc: 'Toni binaurali Alfa e Theta per favorire il focus mentale e lo studio profondo.'
      },
      {
        icon: '🎧',
        title: 'Lettore MP3 Spettrografico',
        desc: 'Riproduzione brani locali con barre di frequenza visuali in tempo reale.'
      },
      {
        icon: '📺',
        title: 'YouTube Live Audio',
        desc: 'Musica continua di sottofondo (Lo-Fi, Synthwave) senza interruzioni.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Scegli la Stazione', text: 'Seleziona una radio nazionale o attiva il generatore di onde 432Hz.' },
      { step: '2', title: 'Regola il Volume', text: 'Personalizza l\'equalizzazione e l\'intensità per creare l\'ambiente di studio ideale.' },
      { step: '3', title: 'Ascolta in Background', text: 'L\'audio continua a suonare mentre navighi negli altri laboratori di Sigma Studio.' }
    ],
    tags: ['Radio FM', '432Hz Synth', 'YouTube Live', 'Lounge Player', 'Web Audio API'],
    samplePrompt: 'Avvia il sintetizzatore di onde binaurali a 432Hz per una sessione di studio concentrato.'
  },
  {
    id: 'sigma_model_hub',
    name: 'Modelli Hub (Kernel Optimizer & Forgia GGUF)',
    category: 'Protocollo & Kernel',
    categoryKey: 'protocol_kernel',
    icon: DownloadCloud,
    color: '#ffb86c',
    tabType: 'model_hub',
    version: 'v0.8.2',
    size: 'Kernel',
    gitUrl: 'https://huggingface.co/models',
    image: '/images/hardware_cluster_lab.jpg',
    badge: 'HUGGING FACE & DEPLOY SIGMAENGINE',
    objective: 'Grazie a SigmaEngine cerchi e scarichi qualsiasi LLM open-source da Hugging Face, quantizzi i pesi in GGUF e li ottimizzi per la tua VRAM/RAM con deploy istantaneo.',
    components: [
      {
        icon: '🔍',
        title: 'Esploratore Hugging Face',
        desc: 'Ricerca istantanea di modelli GGUF, SafeTensors, MoE, Vision e Coder.'
      },
      {
        icon: '📥',
        title: 'Download Streaming con Resume',
        desc: 'Scaricamento in background ad alta velocità con ripresa automatica.'
      },
      {
        icon: '⚡',
        title: 'Deploy Diretto in SigmaEngine',
        desc: 'Partizionamento intelligente tra VRAM GPU primaria, secondaria e RAM.'
      },
      {
        icon: '🚀',
        title: 'FlashAttention-2 & KV FP8',
        desc: 'Quantizzazione dinamica per generare token al secondo al massimo delle prestazioni.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Cerca su Hugging Face', text: 'Cerca qualsiasi modello (es. Qwen 2.5, DeepSeek-R1, Llama 3.3) o sfoglia i raccomandati.' },
      { step: '2', title: 'Avvia il Download', text: 'Clicca "Scarica" per avviare il download streaming protetto nella cartella dei modelli.' },
      { step: '3', title: 'Usa Subito in Chat', text: 'Il modello scaricato diventa immediatamente selezionabile nella Chat AI senza riavvii.' }
    ],
    tags: ['Hugging Face', 'GGUF', 'FlashAttention-2', 'Multi-Tier Sharding', 'Kernel Engine'],
    samplePrompt: 'Scarica il modello Qwen2.5-Coder-7B-Instruct-GGUF e configuralo per l\'esecuzione su GPU.'
  },
  {
    id: 'mcp_hub',
    name: 'MCP Tools & Governance Gateway',
    category: 'Protocollo & Kernel',
    categoryKey: 'protocol_kernel',
    icon: Wrench,
    color: '#00f2fe',
    tabType: 'mcp_hub',
    version: 'v8.0.0',
    size: 'Kernel',
    gitUrl: 'https://github.com/modelcontextprotocol',
    image: '/images/mcp_protocol_hub.jpg',
    badge: '12 SERVER MCP & SICUREZZA GOVERNATA',
    objective: 'Il ponte operativo tra l\'AI e il tuo PC: 12 Server MCP per eseguire file, comandi, interrogazioni SQLite e domotica con policy di sicurezza e whitelist governate.',
    components: [
      {
        icon: '🔌',
        title: '12 Server MCP Standard',
        desc: 'Accesso controllato a File, SQLite, Browser, Domotica, Ricerca Web e Voce.'
      },
      {
        icon: '🛡️',
        title: 'Governance & Safety Policy',
        desc: 'Whitelist di comandi sicuri con blocco automatico delle azioni a rischio.'
      },
      {
        icon: '🧪',
        title: 'Tester JSON-RPC Diagnostico',
        desc: 'Invio manuale di chiamate RPC con ispezione visiva dei payload JSON.'
      },
      {
        icon: '📜',
        title: 'Audit Log delle Invocazioni',
        desc: 'Registro cronologico trasparente di ogni strumento usato dagli agenti.'
      }
    ],
    usageGuide: [
      { step: '1', title: 'Verifica lo Stato', text: 'Controlla lo stato di connessione e la latenza di tutti i server MCP attivi.' },
      { step: '2', title: 'Imposta le Policy', text: 'Decidi quali strumenti possono essere eseguiti in automatico e quali richiedono conferma manuale.' },
      { step: '3', title: 'Collauda i Tool', text: 'Esegui chiamate di test per verificare la risposta dei server I/O in tempo reale.' }
    ],
    tags: ['MCP Standard', 'JSON-RPC', 'Security Governance', 'Safety Whitelist', 'Tool Execution'],
    samplePrompt: 'Esegui il test diagnostico del server MCP Filesystem verificando i permessi di lettura sulla cartella data/.'
  }
];

// ==============================================================================
// CATEGORIE DI FILTRO
// ==============================================================================
const CATEGORIES = [
  { id: 'all', label: '✨ Tutte le Skills', count: 15 },
  { id: 'multimodal', label: '🎨 Multimodale & Grafica', count: 2 },
  { id: 'studio_ai', label: '🤖 Studio & AI', count: 4 },
  { id: 'audio_voice', label: '🎙️ Audio & Voce', count: 2 },
  { id: 'infra_net', label: '⚡ Infrastruttura & Rete', count: 3 },
  { id: 'comm_social', label: '💬 Comunicazione & Social', count: 2 },
  { id: 'protocol_kernel', label: '⚙️ Protocollo & Kernel', count: 2 },
];

// ==============================================================================
// SUB-COMPONENT: SkillSlideCard (Singola Scheda Completa nel Track)
// ==============================================================================
function SkillSlideCard({
  skill,
  isInstalled,
  isLight,
  openTab,
  onOpenModal,
  titleColor,
  subtitleColor,
  innerCardBg,
  innerCardBorder,
  innerCardText
}) {
  const IconComponent = skill.icon;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      {/* Header Card: Icona, Titolo, Categoria, Badge e Azioni Top */}
      <div className="skills-card-header" style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '20px',
        borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)',
        paddingBottom: '16px'
      }}>
        <div className="skills-card-header-left" style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          {/* Icona Skill */}
          <div style={{
            width: '54px',
            height: '54px',
            borderRadius: '16px',
            background: `${skill.color}18`,
            border: `1px solid ${skill.color}45`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 20px ${skill.color}25`,
            color: isLight ? '#c2410c' : skill.color,
            flexShrink: 0
          }}>
            <IconComponent size={28} style={{ color: skill.color }} />
          </div>

          <div>
            <div className="skills-card-header-badges" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
              {/* Badge Categoria */}
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 10px',
                borderRadius: '10px',
                background: `${skill.color}18`,
                border: `1px solid ${skill.color}35`,
                color: isLight ? '#9a3412' : skill.color,
                fontSize: '0.68rem',
                fontWeight: 800,
                letterSpacing: '0.5px'
              }}>
                {skill.badge}
              </span>

              {/* Badge Stato Installazione */}
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 10px',
                borderRadius: '10px',
                background: isInstalled 
                  ? (isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(63, 185, 80, 0.15)')
                  : (isLight ? 'rgba(234, 88, 12, 0.1)' : 'rgba(0, 210, 255, 0.12)'),
                border: isInstalled 
                  ? (isLight ? '1px solid rgba(22, 163, 74, 0.35)' : '1px solid rgba(63, 185, 80, 0.35)')
                  : (isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.3)'),
                color: isInstalled 
                  ? (isLight ? '#15803d' : '#3fb950')
                  : (isLight ? '#c2410c' : '#00d2ff'),
                fontSize: '0.68rem',
                fontWeight: 800
              }}>
                {isInstalled ? <CheckCircle2 size={12} /> : <Download size={12} />}
                {isInstalled ? 'Pronta & Installata' : 'Disponibile su GitHub'}
              </span>

              <span style={{
                fontSize: '0.66rem',
                fontWeight: 700,
                color: isLight ? '#7a7060' : '#8b8fa3',
                background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                padding: '3px 8px',
                borderRadius: '8px'
              }}>
                {skill.version} • {skill.size}
              </span>
            </div>

            <h3 style={{
              margin: 0,
              fontSize: '1.35rem',
              fontWeight: 800,
              color: titleColor,
              lineHeight: 1.3
            }}>
              {skill.name}
            </h3>
          </div>
        </div>

        {/* Pulsanti di Azione Destra */}
        <div className="skills-card-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={onOpenModal}
            title="Guida approfondita ed esempi di integrazione"
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: isLight ? '#fbf8f2' : 'rgba(255,255,255,0.06)',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
              color: isLight ? '#374151' : '#e2e8f0',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <BookOpen size={14} />
            Guida Rapida
          </button>

          {skill.gitUrl && (
            <a
              href={skill.gitUrl}
              target="_blank"
              rel="noreferrer"
              title="Apri sorgente GitHub del modulo"
              style={{
                padding: '8px 12px',
                borderRadius: '10px',
                background: isLight ? '#fbf8f2' : 'rgba(255,255,255,0.06)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
                color: isLight ? '#374151' : '#e2e8f0',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                textDecoration: 'none'
              }}
            >
              <ExternalLink size={14} />
              GitHub
            </a>
          )}

          {/* Pulsante Lancio / Installazione */}
          {isInstalled ? (
            <button
              onClick={() => openTab({ name: skill.name }, skill.tabType)}
              style={{
                padding: '8px 18px',
                borderRadius: '10px',
                background: isLight
                  ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)'
                  : `linear-gradient(135deg, ${skill.color}, ${skill.color}cc)`,
                border: 'none',
                color: '#ffffff',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.25)' : `0 4px 18px ${skill.color}35`,
                transition: 'all 0.2s ease'
              }}
            >
              Apri Skill
              <ArrowRight size={15} />
            </button>
          ) : (
            <button
              onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
              style={{
                padding: '8px 18px',
                borderRadius: '10px',
                background: isLight
                  ? 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
                  : 'linear-gradient(135deg, #00d2ff 0%, #0077ff 100%)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 14px rgba(0, 210, 255, 0.3)',
                transition: 'all 0.2s ease'
              }}
            >
              <Download size={15} />
              Installa dalle Skills
            </button>
          )}
        </div>
      </div>

      {/* Banner Informativo: Download Gratuito da GitHub */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        flexWrap: 'wrap',
        padding: '10px 16px',
        borderRadius: '12px',
        background: isLight ? 'rgba(234, 88, 12, 0.08)' : 'rgba(0, 210, 255, 0.08)',
        border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.25)',
        marginBottom: '18px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: isLight ? '#9a3412' : '#00d2ff', fontWeight: 700 }}>
          <Sparkles size={15} style={{ flexShrink: 0 }} />
          <span>
            <strong>Skills 100% Gratuite & Modulari:</strong> Espandi Sigma Studio aggiungendo nuove funzionalità da GitHub con un solo click dalla scheda <strong style={{ color: isLight ? '#ea580c' : '#ffffff' }}>Skills</strong> senza appesantire il sistema.
          </span>
        </div>
        <button
          onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
          style={{
            background: 'none',
            border: 'none',
            color: isLight ? '#ea580c' : '#00d2ff',
            fontSize: '0.76rem',
            fontWeight: 800,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: 0,
            textDecoration: 'underline'
          }}
        >
          Vai all'Hub Skills <ArrowRight size={13} />
        </button>
      </div>

      {/* Body Card: Layout a 3 Colonne */}
      <div className="skills-card-body-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '20px',
        marginBottom: '12px',
        alignItems: 'start'
      }}>
        {/* Colonna 1: Banner Immagine */}
        <div style={{
          position: 'relative',
          borderRadius: '16px',
          overflow: 'hidden',
          border: isLight ? `1px solid ${skill.color}45` : `1px solid ${skill.color}35`,
          boxShadow: isLight ? `0 8px 24px ${skill.color}15` : '0 12px 30px rgba(0,0,0,0.5)',
          minHeight: '220px',
          maxHeight: '260px',
          background: '#0a0d14'
        }}>
          <img
            src={skill.image}
            alt={skill.name}
            style={{
              width: '100%',
              height: '260px',
              maxHeight: '260px',
              objectFit: 'cover',
              display: 'block'
            }}
            onError={(e) => { e.target.src = '/images/hero_banner.jpg'; }}
          />
          <div style={{
            position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
            padding: '10px 14px',
            background: 'linear-gradient(to top, rgba(10,13,20,0.95), transparent)',
            fontSize: '0.72rem', color: '#ffffff', fontWeight: 700,
            display: 'flex', alignItems: 'center', gap: '6px'
          }}>
            <span>🖼️ {skill.badge}</span>
          </div>
        </div>

        {/* Colonna 2: Obiettivo e Componenti Chiave */}
        <div>
          {/* Box Obiettivo */}
          <div style={{
            padding: '12px 14px',
            borderRadius: '12px',
            background: isLight ? '#fbf8f2' : `${skill.color}10`,
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : `1px solid ${skill.color}25`,
            marginBottom: '14px'
          }}>
            <div style={{
              fontSize: '0.68rem',
              fontWeight: 800,
              color: isLight ? '#c2410c' : skill.color,
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              marginBottom: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <Info size={13} />
              🎯 Obiettivo Primario & Ambito
            </div>
            <p style={{
              margin: 0,
              fontSize: '0.82rem',
              color: isLight ? '#111827' : '#e2e8f0',
              lineHeight: 1.5,
              fontWeight: isLight ? 600 : 500
            }}>
              {skill.objective}
            </p>
          </div>

          {/* Griglia 2x2 dei Componenti Chiave */}
          <div>
            <div style={{
              fontSize: '0.7rem',
              fontWeight: 800,
              color: isLight ? '#7a7060' : '#8b8fa3',
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              marginBottom: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <Layers size={13} />
              🧩 Componenti Chiave & Tecnologie
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '8px'
            }}>
              {skill.components.map((comp, cIdx) => (
                <div
                  key={cIdx}
                  style={{
                    padding: '8px 10px',
                    borderRadius: '10px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-start'
                  }}
                >
                  <div style={{
                    fontWeight: 800,
                    fontSize: '0.76rem',
                    color: isLight ? '#9a3412' : skill.color,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    marginBottom: '2px'
                  }}>
                    <span>{comp.icon}</span>
                    <span>{comp.title}</span>
                  </div>
                  <div style={{
                    fontSize: '0.7rem',
                    color: innerCardText,
                    lineHeight: 1.4,
                    fontWeight: isLight ? 500 : 400
                  }}>
                    {comp.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Colonna Destra: Guida Pratica Step-by-Step */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              color: isLight ? '#7a7060' : '#8b8fa3',
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              marginBottom: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <Code size={13} />
              💡 Come Usarlo (Guida Pratica Step-by-Step)
            </div>

            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              marginBottom: '16px'
            }}>
              {skill.usageGuide.map((stepItem, sIdx) => (
                <div
                  key={sIdx}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '10px 14px',
                    borderRadius: '12px',
                    background: innerCardBg,
                    border: innerCardBorder
                  }}
                >
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: `${skill.color}25`,
                    border: `1px solid ${skill.color}45`,
                    color: isLight ? '#9a3412' : skill.color,
                    fontSize: '0.72rem',
                    fontWeight: 900,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    {stepItem.step}
                  </div>
                  <div>
                    <div style={{
                      fontWeight: 800,
                      fontSize: '0.78rem',
                      color: titleColor,
                      marginBottom: '2px'
                    }}>
                      {stepItem.title}
                    </div>
                    <div style={{
                      fontSize: '0.72rem',
                      color: subtitleColor,
                      lineHeight: 1.45,
                      fontWeight: isLight ? 500 : 400
                    }}>
                      {stepItem.text}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Prompt Esempio & Tag */}
          <div style={{
            padding: '10px 12px',
            borderRadius: '10px',
            background: innerCardBg,
            border: innerCardBorder
          }}>
            <div style={{
              fontSize: '0.68rem',
              fontWeight: 800,
              color: isLight ? '#7a7060' : '#8b8fa3',
              marginBottom: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <span>⚡ STACK & TAG TECNOLOGICI:</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {skill.tags.map((tag, tIdx) => (
                <span
                  key={tIdx}
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '6px',
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)',
                    color: isLight ? '#111827' : '#cbd5e1'
                  }}
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// MAIN COMPONENT: SkillsShowcaseSlider
// ==============================================================================
export default function SkillsShowcaseSlider({ openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const { modulesState } = useModuleState();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isAutoPlay, setIsAutoPlay] = useState(true);
  const [selectedModalSkill, setSelectedModalSkill] = useState(null);

  // Swipe / Touch Support
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);

  const autoPlayRef = useRef(null);

  // Filtra le skills in base a categoria e ricerca
  const filteredSkills = useMemo(() => {
    return SKILLS_CATALOG.filter(skill => {
      const matchCategory = activeCategory === 'all' || skill.categoryKey === activeCategory;
      if (!matchCategory) return false;
      if (!searchQuery.trim()) return true;

      const q = searchQuery.toLowerCase();
      return (
        skill.name.toLowerCase().includes(q) ||
        skill.objective.toLowerCase().includes(q) ||
        skill.badge.toLowerCase().includes(q) ||
        skill.tags.some(t => t.toLowerCase().includes(q)) ||
        skill.components.some(c => c.title.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q))
      );
    });
  }, [activeCategory, searchQuery]);

  // Se la lista filtrata cambia, resetta l'indice se fuori range
  useEffect(() => {
    if (currentIndex >= filteredSkills.length) {
      setCurrentIndex(0);
    }
  }, [filteredSkills.length, currentIndex]);

  // Gestione Autoplay (avanza ogni 8 secondi, si ferma al hover o se disattivato)
  useEffect(() => {
    if (!isAutoPlay || filteredSkills.length <= 1) return;
    autoPlayRef.current = setInterval(() => {
      setCurrentIndex(prev => (prev + 1) % filteredSkills.length);
    }, 8000);
    return () => clearInterval(autoPlayRef.current);
  }, [isAutoPlay, filteredSkills.length]);

  const handlePrev = () => {
    setCurrentIndex(prev => (prev - 1 + filteredSkills.length) % filteredSkills.length);
  };

  const handleNext = () => {
    setCurrentIndex(prev => (prev + 1) % filteredSkills.length);
  };

  // Touch Swipe Handlers
  const handleTouchStart = (e) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 45;
    const isRightSwipe = distance < -45;
    if (isLeftSwipe) handleNext();
    if (isRightSwipe) handlePrev();
  };

  const currentSkill = filteredSkills[currentIndex] || SKILLS_CATALOG[0];
  const IconComponent = currentSkill.icon;

  // Stili Tematizzati
  const cardBg = isLight 
    ? '#ffffff' 
    : 'linear-gradient(135deg, rgba(14, 18, 28, 0.95) 0%, rgba(10, 13, 20, 0.98) 100%)';
  const cardBorder = isLight 
    ? '1px solid rgba(190, 160, 110, 0.45)' 
    : `1px solid ${currentSkill ? currentSkill.color : '#00d2ff'}35`;
  const cardShadow = isLight 
    ? '0 12px 32px rgba(234, 88, 12, 0.08)' 
    : `0 16px 40px rgba(0,0,0,0.6), 0 0 30px ${currentSkill ? currentSkill.color : '#00d2ff'}15`;

  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#a0a6bc';
  const innerCardBg = isLight ? '#fbf8f2' : 'rgba(255, 255, 255, 0.03)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.07)';
  const innerCardText = isLight ? '#374151' : '#cbd5e1';

  return (
    <div 
      className="skills-showcase-section"
      style={{
        margin: '28px 0 16px 0',
        position: 'relative'
      }}
      onMouseEnter={() => setIsAutoPlay(false)}
      onMouseLeave={() => setIsAutoPlay(true)}
    >
      {/* ── HEADER DELLA SEZIONE ────────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '18px'
      }}>
        <div>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            borderRadius: '12px',
            background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
            color: isLight ? '#c2410c' : '#00d2ff',
            fontSize: '0.72rem',
            fontWeight: 800,
            letterSpacing: '0.6px',
            textTransform: 'uppercase',
            marginBottom: '8px'
          }}>
            <Sparkles size={14} />
            <span>CATALOGO SKILLS & ESTENSIONI GITHUB</span>
          </div>
          <h2 style={{
            margin: '0 0 6px 0',
            fontSize: '1.25rem',
            fontWeight: 800,
            color: titleColor,
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            <span>🧩</span> Skills & Moduli Componibili di <span style={{ color: isLight ? '#ea580c' : '#00d2ff' }}>Sigma Studio</span>
          </h2>
          <p style={{
            margin: 0,
            fontSize: '0.86rem',
            color: subtitleColor,
            lineHeight: 1.5,
            fontWeight: isLight ? 500 : 400,
            maxWidth: '820px'
          }}>
            Espandi le capacità di Sigma Studio in un click: scarica laboratori 3D, sintesi vocale neurale, telemetria hardware e server MCP da GitHub, mantenendo il kernel sempre leggero e veloce.
          </p>
        </div>

        {/* Pulsante rapido verso l'Hub Skills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
            style={{
              padding: '9px 18px',
              borderRadius: '12px',
              background: isLight ? 'rgba(234, 88, 12, 0.1)' : 'rgba(0, 210, 255, 0.12)',
              border: isLight ? '1px solid rgba(234, 88, 12, 0.4)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: isLight ? '#c2410c' : '#00d2ff',
              fontSize: '0.82rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.2s ease',
              boxShadow: isLight ? '0 2px 8px rgba(234, 88, 12, 0.12)' : 'none'
            }}
          >
            <Download size={15} />
            Apri Hub Skills & Estensioni
          </button>
        </div>
      </div>

      {/* ── BARRA FILTRI CATEGORIA & RICERCA LIVE ──────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '16px',
        background: isLight ? '#ffffff' : 'rgba(255,255,255,0.03)',
        padding: '8px 12px',
        borderRadius: '16px',
        border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.07)'
      }}>
        {/* Pills Categoria */}
        <div className="skills-cat-filter-container" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          overflowX: 'auto',
          paddingBottom: '2px',
          maxWidth: '100%'
        }}>
          {CATEGORIES.map(cat => {
            const active = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                className="skills-cat-filter-btn"
                onClick={() => { setActiveCategory(cat.id); setCurrentIndex(0); }}
                style={{
                  padding: '6px 12px',
                  borderRadius: '10px',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  background: active
                    ? (isLight ? '#ea580c' : '#00d2ff')
                    : (isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)'),
                  color: active
                    ? '#ffffff'
                    : (isLight ? '#374151' : '#a0a6bc'),
                  boxShadow: active
                    ? (isLight ? '0 2px 8px rgba(234, 88, 12, 0.3)' : '0 2px 10px rgba(0, 210, 255, 0.35)')
                    : 'none'
                }}
              >
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Input Ricerca Live */}
        <div style={{
          position: 'relative',
          minWidth: '220px',
          maxWidth: '300px',
          flex: '1 1 auto'
        }}>
          <Search size={14} style={{
            position: 'absolute',
            left: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: isLight ? '#7a7060' : '#8b8fa3'
          }} />
          <input
            type="text"
            placeholder="Cerca skill, componente o tag..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setCurrentIndex(0); }}
            style={{
              width: '100%',
              padding: '6px 12px 6px 30px',
              borderRadius: '10px',
              fontSize: '0.76rem',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
              background: isLight ? '#fbf8f2' : 'rgba(10, 14, 24, 0.8)',
              color: isLight ? '#111827' : '#ffffff',
              outline: 'none'
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{
                position: 'absolute',
                right: '8px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                color: '#888',
                cursor: 'pointer',
                padding: '2px'
              }}
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── CARD PRINCIPALE DELLO SLIDER DINAMICO (CAROUSEL TRACK) ────────── */}
      {filteredSkills.length === 0 ? (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          borderRadius: '20px',
          background: cardBg,
          border: cardBorder,
          color: subtitleColor
        }}>
          <p style={{ fontSize: '0.9rem', margin: 0 }}>Nessuna skill trovata per i criteri selezionati.</p>
        </div>
      ) : (
        <div
          style={{
            position: 'relative',
            borderRadius: '24px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            overflow: 'hidden',
            transition: 'border-color 0.4s ease, box-shadow 0.4s ease'
          }}
        >
          {/* Barra di Avanzamento Autoplay al Bordo Superiore */}
          <div style={{
            position: 'relative',
            width: '100%',
            height: '3px',
            background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)',
            overflow: 'hidden'
          }}>
            <div
              key={`progress-${currentIndex}-${isAutoPlay}`}
              style={{
                height: '100%',
                background: isLight
                  ? 'linear-gradient(90deg, #ea580c, #f97316)'
                  : `linear-gradient(90deg, ${currentSkill.color}, #00d2ff)`,
                width: isAutoPlay ? '100%' : '0%',
                transition: isAutoPlay ? 'width 8s linear' : 'none',
                boxShadow: `0 0 8px ${currentSkill.color}`
              }}
            />
          </div>

          {/* Freccia Flottante Sinistra */}
          {filteredSkills.length > 1 && (
            <button
              className="skills-floating-arrow"
              onClick={(e) => { e.stopPropagation(); handlePrev(); }}
              aria-label="Skill precedente"
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                zIndex: 25,
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                background: isLight ? 'rgba(255, 255, 255, 0.9)' : 'rgba(15, 20, 32, 0.88)',
                backdropFilter: 'blur(10px)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(255, 255, 255, 0.18)',
                boxShadow: isLight ? '0 4px 16px rgba(0,0,0,0.12)' : '0 6px 20px rgba(0,0,0,0.6)',
                color: isLight ? '#111827' : '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                e.currentTarget.style.borderColor = currentSkill.color;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
                e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.45)' : 'rgba(255, 255, 255, 0.18)';
              }}
            >
              <ChevronLeft size={22} />
            </button>
          )}

          {/* Freccia Flottante Destra */}
          {filteredSkills.length > 1 && (
            <button
              className="skills-floating-arrow"
              onClick={(e) => { e.stopPropagation(); handleNext(); }}
              aria-label="Prossima skill"
              style={{
                position: 'absolute',
                right: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                zIndex: 25,
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                background: isLight ? 'rgba(255, 255, 255, 0.9)' : 'rgba(15, 20, 32, 0.88)',
                backdropFilter: 'blur(10px)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(255, 255, 255, 0.18)',
                boxShadow: isLight ? '0 4px 16px rgba(0,0,0,0.12)' : '0 6px 20px rgba(0,0,0,0.6)',
                color: isLight ? '#111827' : '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)';
                e.currentTarget.style.borderColor = currentSkill.color;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
                e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.45)' : 'rgba(255, 255, 255, 0.18)';
              }}
            >
              <ChevronRight size={22} />
            </button>
          )}

          {/* ── TRACK A SCIVOLAMENTO ORIZZONTALE FLUIDO (GPU ACCELERATO) ───── */}
          <div
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
            style={{
              display: 'flex',
              width: `${filteredSkills.length * 100}%`,
              transform: `translateX(-${currentIndex * (100 / filteredSkills.length)}%)`,
              transition: 'transform 0.36s cubic-bezier(0.16, 1, 0.3, 1)',
              willChange: 'transform'
            }}
          >
            {filteredSkills.map((skill) => {
              const isInstalled = skill.size === 'Kernel' || modulesState[skill.id] === true;
              return (
                <div
                  key={skill.id}
                  className="skills-slider-track-item"
                  style={{
                    width: `${100 / filteredSkills.length}%`,
                    flexShrink: 0,
                    boxSizing: 'border-box'
                  }}
                >
                  <SkillSlideCard
                    skill={skill}
                    isInstalled={isInstalled}
                    isLight={isLight}
                    openTab={openTab}
                    onOpenModal={() => setSelectedModalSkill(skill)}
                    titleColor={titleColor}
                    subtitleColor={subtitleColor}
                    innerCardBg={innerCardBg}
                    innerCardBorder={innerCardBorder}
                    innerCardText={innerCardText}
                  />
                </div>
              );
            })}
          </div>

          {/* ── BARRA INFERIORE DI CONTROLLO SLIDER & PAGINAZIONE ───────────── */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px',
            padding: '16px 28px',
            background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.25)',
            borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)'
          }}>
            {/* Controlli Prev / Next + Play/Pausa */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={handlePrev}
                title="Skill precedente"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: isLight ? '#fbf8f2' : 'rgba(255,255,255,0.06)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
                  color: isLight ? '#111827' : '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <ChevronLeft size={18} />
              </button>

              <button
                onClick={() => setIsAutoPlay(prev => !prev)}
                title={isAutoPlay ? 'Metti in pausa autoplay' : 'Avvia autoplay'}
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: isAutoPlay 
                    ? (isLight ? 'rgba(234, 88, 12, 0.15)' : `${currentSkill.color}25`)
                    : (isLight ? '#fbf8f2' : 'rgba(255,255,255,0.06)'),
                  border: isAutoPlay 
                    ? (isLight ? '1px solid rgba(234, 88, 12, 0.4)' : `1px solid ${currentSkill.color}45`)
                    : (isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)'),
                  color: isAutoPlay 
                    ? (isLight ? '#c2410c' : currentSkill.color)
                    : (isLight ? '#111827' : '#ffffff'),
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                {isAutoPlay ? <Pause size={14} /> : <Play size={14} />}
              </button>

              <button
                onClick={handleNext}
                title="Prossima skill"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: isLight ? '#fbf8f2' : 'rgba(255,255,255,0.06)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
                  color: isLight ? '#111827' : '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <ChevronRight size={18} />
              </button>

              {/* Indicatore Numerico */}
              <span style={{
                fontSize: '0.76rem',
                fontWeight: 800,
                color: isLight ? '#7a7060' : '#8b8fa3',
                marginLeft: '6px'
              }}>
                Skill <strong style={{ color: titleColor }}>{currentIndex + 1}</strong> di <strong style={{ color: titleColor }}>{filteredSkills.length}</strong>
              </span>
            </div>

            {/* Traccia di Paginazione a Pillole */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flexWrap: 'wrap',
              maxWidth: '100%'
            }}>
              {filteredSkills.map((skill, idx) => {
                const isSelected = idx === currentIndex;
                return (
                  <button
                    key={skill.id}
                    onClick={() => setCurrentIndex(idx)}
                    title={skill.name}
                    style={{
                      height: '8px',
                      width: isSelected ? '28px' : '8px',
                      borderRadius: '4px',
                      background: isSelected 
                        ? (isLight ? '#ea580c' : currentSkill.color) 
                        : (isLight ? 'rgba(190, 160, 110, 0.35)' : 'rgba(255,255,255,0.15)'),
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                      boxShadow: isSelected 
                        ? (isLight ? '0 0 8px rgba(234, 88, 12, 0.4)' : `0 0 10px ${currentSkill.color}65`) 
                        : 'none'
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── MODALE GUIDA DETTAGLIATA (POPUP INTERATTIVO) ───────────────────── */}
      {selectedModalSkill && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div style={{
            width: '100%',
            maxWidth: '680px',
            maxHeight: '90vh',
            overflowY: 'auto',
            borderRadius: '24px',
            background: cardBg,
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : `1px solid ${selectedModalSkill.color}45`,
            boxShadow: '0 24px 60px rgba(0,0,0,0.8)',
            padding: '28px',
            position: 'relative'
          }}>
            {/* Chiudi Modale */}
            <button
              onClick={() => setSelectedModalSkill(null)}
              style={{
                position: 'absolute',
                right: '18px',
                top: '18px',
                background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.08)',
                border: 'none',
                borderRadius: '50%',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isLight ? '#111827' : '#ffffff',
                cursor: 'pointer'
              }}
            >
              <X size={16} />
            </button>

            {/* Intestazione Modale */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '18px' }}>
              <div style={{
                width: '46px',
                height: '46px',
                borderRadius: '14px',
                background: `${selectedModalSkill.color}20`,
                border: `1px solid ${selectedModalSkill.color}45`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isLight ? '#c2410c' : selectedModalSkill.color
              }}>
                {React.createElement(selectedModalSkill.icon, { size: 24, style: { color: selectedModalSkill.color } })}
              </div>
              <div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  color: isLight ? '#9a3412' : selectedModalSkill.color,
                  letterSpacing: '0.5px'
                }}>
                  {selectedModalSkill.badge}
                </span>
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: titleColor }}>
                  {selectedModalSkill.name}
                </h3>
              </div>
            </div>

            {/* Prompt di Esempio */}
            <div style={{
              padding: '14px',
              borderRadius: '14px',
              background: isLight ? '#fbf8f2' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.08)',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '0.7rem',
                fontWeight: 800,
                color: isLight ? '#c2410c' : selectedModalSkill.color,
                textTransform: 'uppercase',
                marginBottom: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Sparkles size={13} />
                Esempio di Prompt per la Chat AI
              </div>
              <div style={{
                fontSize: '0.82rem',
                fontFamily: 'monospace',
                color: isLight ? '#111827' : '#00d2ff',
                lineHeight: 1.45
              }}>
                "{selectedModalSkill.samplePrompt}"
              </div>
            </div>

            {/* Componenti Approfonditi */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: titleColor, fontWeight: 800 }}>
                Dettaglio Tecnico dei Componenti:
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {selectedModalSkill.components.map((c, idx) => (
                  <div key={idx} style={{
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: innerCardBg,
                    border: innerCardBorder
                  }}>
                    <div style={{ fontWeight: 800, fontSize: '0.8rem', color: isLight ? '#9a3412' : selectedModalSkill.color, marginBottom: '2px' }}>
                      {c.icon} {c.title}
                    </div>
                    <div style={{ fontSize: '0.74rem', color: innerCardText, lineHeight: 1.4 }}>
                      {c.desc}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer Modale */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setSelectedModalSkill(null)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '10px',
                  background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                  border: 'none',
                  color: isLight ? '#111827' : '#ffffff',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Chiudi
              </button>
              <button
                onClick={() => {
                  const s = selectedModalSkill;
                  setSelectedModalSkill(null);
                  openTab({ name: s.name }, s.tabType);
                }}
                style={{
                  padding: '8px 20px',
                  borderRadius: '10px',
                  background: isLight
                    ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)'
                    : `linear-gradient(135deg, ${selectedModalSkill.color}, ${selectedModalSkill.color}cc)`,
                  border: 'none',
                  color: '#ffffff',
                  fontSize: '0.8rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                Apri Skill Subito 🚀
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
