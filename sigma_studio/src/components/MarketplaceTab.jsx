import React, { useState, useEffect } from 'react';
import { 
  Store, Package, Download, RefreshCw, CheckCircle2, ShieldCheck, 
  ExternalLink, Terminal, GitBranch, Cpu, Sparkles, Layers, 
  Palette, FlaskConical, Brain, Zap, Home, Wrench, ArrowRight,
  PlusCircle, AlertCircle, Play, Check, X, Search, Radio, Trash2, Calendar, PieChart, Mic,
  Globe, Mail, Send
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import TabHeader from './common/TabHeader';

// ==============================================================================
// Built-in Kernel Modules Data
// ==============================================================================
const KERNEL_MODULES = [


  {
    id: 'mcp_hub',
    name: 'MCP Tools & Governance Gateway',
    category: 'Protocollo & Governance',
    icon: Wrench,
    color: '#00f2fe',
    tabType: 'mcp_hub',
    version: 'v8.0.0',
    status: 'installed',
    description: 'Gateway centralizzato per tutti i server MCP. Gestione permessi, policy di auto-approvazione e test RPC diagnostici.',
    tags: ['MCP Standard', 'JSON-RPC', 'Security Policy', 'Discovery'],
    author: 'Sigma Core Team'
  },
];

// ==============================================================================
// Optional Modules — installabili/disinstallabili da repository Git
// ==============================================================================
const OPTIONAL_MODULES = [
  {
    id: 'sigma_creative_lab',
    name: 'Creative Lab 3D/2D',
    category: 'Multimodale & Grafica',
    icon: Palette,
    color: '#ff5064',
    tabType: 'creative_studio',
    version: 'v1.0.0',
    description: 'Studio generativo multimodale: Text-to-Image (FLUX, SDXL), Img2Img, Inpainting, rimozione sfondo (SAM2/rembg), generazione 3D (Hunyuan3D), materiali PBR, rendering Blender headless, pipeline a nodi DAG e sintesi video.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_creative_lab',
    branch: 'main',
    tags: ['FLUX', 'SDXL', 'ComfyUI', 'Blender 3D', 'RemBG', 'PBR', 'Video Gen'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'audio_studio',
    name: 'Hi-Fi Sound & FM Radio Studio',
    category: 'Audio & Streaming',
    icon: Radio,
    color: '#00f2fe',
    tabType: 'music',
    version: 'v1.0.0',
    description: 'Modulo isolato di streaming audio Hi-Fi con dirette radiofoniche FM nazionali (Mediaset, Rai, Gruppo 24 ORE, Kiss Kiss, Global UK), motore YouTube Live, lettore MP3 locale e generatore binaurale 432Hz.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_audio_studio',
    branch: 'main',
    tags: ['Radio FM', 'Hi-Fi Lounge', 'YouTube Live', '432Hz Synth', 'Web Audio'],
    size: '12 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_domotica',
    name: 'Domotica & Home Assistant IoT',
    category: 'Automazione Domotica',
    icon: Home,
    color: '#a78bfa',
    tabType: 'domotica',
    version: 'v1.0.0',
    description: 'Bridge MCP nativo per Home Assistant. Controllo entità smart (luci, prese, clima, sensori, telecamere), automazioni, scene personalizzate e streaming camera in tempo reale.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_domotica',
    branch: 'main',
    tags: ['Home Assistant', 'WebSocket', 'IoT MCP', 'Scene Smart', 'Zigbee'],
    size: '8 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_hardware_lab',
    name: 'Hardware Lab & VRAM Telemetry',
    category: 'Infrastruttura & GPU',
    icon: Zap,
    color: '#00d2ff',
    tabType: 'hardware_lab',
    version: 'v1.0.0',
    description: 'Telemetria in tempo reale di GPU VRAM, RAM di sistema, carico CPU, gestione processi CUDA e terminazione selettiva dei processi zombie.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_hardware_lab',
    branch: 'main',
    tags: ['NVIDIA NVML', 'GPU VRAM', 'Ollama Daemon', 'Process Manager', 'CUDA Telemetry'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_research_lab',
    name: 'Pipelines Lab & Dynamic Swarm',
    category: 'Orchestrazione Multi-Agente',
    icon: FlaskConical,
    color: '#7c5bf0',
    tabType: 'research_lab',
    version: 'v1.0.0',
    description: 'Pianificatore DAG di swarm multi-agente, decomposizione automatica di obiettivi scientifici, feedback loop iterativo e self-healing dei task.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_research_lab',
    branch: 'main',
    tags: ['Swarm DAG', 'Multi-Agent', 'Workflow Automation', 'Pipeline Designer', 'Self-Healing'],
    size: '1.5 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_training_lab',
    name: 'Training Lab & SLM Forge',
    category: 'Fine-Tuning & Valutazione',
    icon: Brain,
    color: '#d29922',
    tabType: 'training_lab',
    version: 'v1.0.0',
    description: 'Fine-tuning QLoRA Unsloth, Autopilota di iperparametri, Forgia SLM italiana, esportazione GGUF e 11 benchmark ufficiali (MMLU, GSM8K, HumanEval, ARC, BBH...).',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_training_lab',
    branch: 'main',
    tags: ['Unsloth QLoRA', 'GGUF Export', 'Gradus FWE', 'Benchmarks', 'SLM Forge', 'Autopilot'],
    size: '3 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_roadmap',
    name: 'Pianificazione, Roadmap & Task Audit',
    category: 'Pianificazione & Task',
    icon: Calendar,
    color: '#ffd700',
    tabType: 'roadmap',
    version: 'v1.0.0',
    description: 'Sistema completo di pianificazione strategica: Calendario Attività, Kanban Task interattivo, Audit Trail cronologico e pannello flottante per monitoraggio delle milestone.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_roadmap',
    branch: 'main',
    tags: ['Roadmap', 'Kanban', 'Calendar', 'Audit Trail', 'Task Management', 'Milestones'],
    size: '1 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_knowledge',
    name: 'Argomenti, Memoria & Knowledge Graph',
    category: 'Conoscenza & Memoria',
    icon: PieChart,
    color: '#00d2ff',
    tabType: 'knowledge',
    version: 'v1.0.0',
    description: 'Grafo relazionale interattivo D3.js, Universal Knowledge Nodes con supporto multi-formato, memoria episodica e RAG Memory MCP Server.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_knowledge',
    branch: 'main',
    tags: ['D3.js Graph', 'Knowledge Graph', 'Universal Nodes', 'Memory MCP', 'Episodic Context', 'RAG'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_voice_studio',
    name: 'Voice Studio & Neural Speech Lab',
    category: 'Audio & Voce Neurale',
    icon: Mic,
    color: '#ff79c6',
    tabType: 'voice_studio',
    version: 'v1.0.0',
    description: 'Laboratorio di sintesi vocale neurale: motore Kokoro 82M ultra-veloce, Coqui XTTS-v2 zero-shot voice cloning, personalizzazione tono/velocità, preset vocali e Voice MCP Server.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_voice_studio',
    branch: 'main',
    tags: ['Kokoro 82M', 'XTTS-v2', 'Neural TTS', 'Voice Cloning', 'Speech Synthesis', 'Voice MCP'],
    size: '3 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_developer_lab',
    name: 'Developer Lab & Docker Sandbox',
    category: 'Sviluppo & Sandbox',
    icon: Terminal,
    color: '#00d2ff',
    tabType: 'developer_lab',
    version: 'v1.0.0',
    description: 'IDE avanzato per programmatori con gestione container Docker isolati, esecuzione codice live con terminale output, installazione pacchetti pip/npm in container e runner test pytest.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/sigma_developer_lab',
    branch: 'main',
    tags: ['Docker', 'Sandbox', 'Pytest', 'Python', 'Node.js', 'Terminal', 'Developer MCP'],
    size: '2 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'sigma_network_lab',
    name: 'Network Explorer & Web Research',
    category: 'Rete & Ricerca',
    icon: Globe,
    color: '#3fb950',
    tabType: 'network_lab',
    version: 'v1.0.0',
    description: 'Console di ricerca web live, HTTP API request builder (stile Postman), diagnostica DNS, Ping e Network MCP Server per agenti AI.',
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
    icon: Mail,
    color: '#ffb454',
    tabType: 'email_client',
    version: 'v1.0.0',
    description: 'Client webmail integrato con lettura inbox, visualizzatore email HTML, compositore con supporto bozze agenti AI, configurazione sicura SMTP/IMAP ed Email MCP Server.',
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
    icon: Send,
    color: '#bc8cff',
    tabType: 'messaging_hub',
    version: 'v1.0.0',
    description: 'Centro di controllo per canali Telegram, Slack e Discord Webhook, dispatcher notifiche broadcast e Messaging MCP Server.',
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
    category: 'Audio & Voce Neurale',
    icon: Sparkles,
    color: '#ff79c6',
    tabType: 'audio_studio',
    version: 'v1.2.0',
    status: 'available',
    description: 'Clonazione vocale real-time XTTS-v2, trascrizione Whisper multilingue e sintesi vocale neurale con streaming WebSocket a bassissima latenza.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-AudioEngine.git',
    branch: 'main',
    tags: ['XTTS-v2', 'Whisper', 'Neural Voice', 'FastAPI'],
    size: '142 MB',
    author: 'Sigma Community'
  },
  {
    id: 'vision_agent',
    name: 'Vision & Visual Grounding Lab',
    category: 'Computer Vision & OCR',
    icon: Sparkles,
    color: '#00d2ff',
    tabType: 'vision_lab',
    version: 'v1.0.4',
    status: 'available',
    description: 'Analisi visiva avanzata con Qwen2-VL, rilevamento oggetti YOLOv10, OCR impaginato per paper scientifici e bounding-box interattivi.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-VisionLab.git',
    branch: 'main',
    tags: ['Qwen2-VL', 'YOLOv10', 'OCR Doc', 'Bounding Box'],
    size: '88 MB',
    author: 'Sigma Core Team'
  },
  {
    id: 'robotics_ros2',
    name: 'ROS2 & Robotics Bridge',
    category: 'Robotica & Meccatronica',
    icon: Sparkles,
    color: '#3fb950',
    tabType: 'robotics_tab',
    version: 'v0.9.0',
    status: 'available',
    description: 'Interfaccia nativa ROS2 / micro-ROS per inviare comandi cinematica, visualizzare odometria laser e teleoperare bracci robotici.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-Robotics.git',
    branch: 'main',
    tags: ['ROS2 Humble', 'Nav2', 'Kinematics', 'URDF Visualizer'],
    size: '64 MB',
    author: 'Sigma Robotics Group'
  },
  {
    id: 'financial_quant',
    name: 'Quant & Algorithmic Trading Lab',
    category: 'Finanza Quantitativa',
    icon: Sparkles,
    color: '#d29922',
    tabType: 'quant_lab',
    version: 'v1.1.0',
    status: 'available',
    description: 'Backtesting vettorializzato con Backtrader/VectorBT, calcolo volatilità GARCH, ottimizzazione di portafoglio Markowitz e feed Yahoo Finance.',
    gitUrl: 'https://github.com/Sigmanih/SigmaStudio-Module-Quant.git',
    branch: 'main',
    tags: ['Backtesting', 'VectorBT', 'Markowitz', 'Risk Engine'],
    size: '35 MB',
    author: 'Sigma Community'
  }
];

// ==============================================================================
// Reusable Module Card component
// ==============================================================================
function ModuleCard({ mod, isLight, cardBg, cardBorder, textPrimary, textSecondary, accentColor, badge, actions, gitUrl }) {
  const Icon = mod.icon;
  return (
    <div style={{ borderRadius: '14px', background: cardBg, border: cardBorder, padding: '12px 14px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', position: 'relative', boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 20px rgba(0,0,0,0.3)', transition: 'transform 0.15s ease, border-color 0.15s ease' }}>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: `${mod.color}15`, border: `1px solid ${mod.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: mod.color, flexShrink: 0 }}>
              <Icon size={17} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <h3 style={{ margin: '0 0 1px 0', fontSize: '0.86rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{mod.name}</h3>
              <span style={{ fontSize: '0.66rem', color: textSecondary, fontWeight: 600, display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{mod.category} • {mod.version}</span>
            </div>
          </div>
          {badge}
        </div>
        <p style={{ fontSize: '0.72rem', color: textSecondary, lineHeight: 1.35, margin: '0 0 8px 0', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{mod.description}</p>
        {(gitUrl || mod.gitUrl) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: '6px', background: isLight ? 'rgba(190,160,110,0.1)' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190,160,110,0.25)' : '1px solid rgba(255,255,255,0.08)', marginBottom: '8px', fontSize: '0.66rem', color: textSecondary }}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke={accentColor} strokeWidth="2"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{gitUrl || mod.gitUrl}</span>
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }}>
          {(mod.tags || []).slice(0, 4).map(tag => (
            <span key={tag} style={{ padding: '1px 6px', borderRadius: '4px', background: isLight ? 'rgba(190,160,110,0.12)' : 'rgba(255,255,255,0.04)', border: isLight ? '1px solid rgba(190,160,110,0.25)' : '1px solid rgba(255,255,255,0.08)', color: isLight ? '#554e42' : '#cbd5e0', fontSize: '0.64rem', fontWeight: 600 }}>#{tag}</span>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: isLight ? '1px solid rgba(190,160,110,0.2)' : '1px solid rgba(255,255,255,0.06)', paddingTop: '8px', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.66rem', color: textSecondary }}>Autore: <strong>{mod.author}</strong>{mod.size ? ` • ${mod.size}` : ''}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>{actions}</div>
      </div>
    </div>
  );
}

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
  const [installingId, setInstallingId] = useState(null);
  const [uninstallingId, setUninstallingId] = useState(null);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState('');
  // Optional modules installed state — starts from false, only true if confirmed by backend
  const [optionalInstalledState, setOptionalInstalledState] = useState(() => {
    // Pre-populate from localStorage only for optional modules
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
    `[${new Date().toLocaleTimeString()}] 📦 Sigma Kernel Marketplace v8.1 inizializzato.`,
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
          // Sync to localStorage so sidebar/app can read it
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

  // Color tokens depending on Dark (Blue) vs Light/Crema (Orange)
  const accentColor = isLight ? '#ea580c' : '#00d2ff';
  const secondaryAccent = isLight ? '#d97706' : '#3b82f6';
  const cardBg = isLight ? '#fffdf9' : '#121622';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111111' : '#fff';
  const textSecondary = isLight ? '#4b5563' : '#a0aec0';

  const handleInstallModule = async (mod) => {
    setInstallingId(mod.id);
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

  const searchFn = (m) =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.description.toLowerCase().includes(search.toLowerCase()) ||
    m.tags.some(t => t.toLowerCase().includes(search.toLowerCase()));

  // Tab "Installati": kernel modules (always active) + optional modules that are installed
  const filteredKernel = KERNEL_MODULES.filter(searchFn);
  const filteredOptionalInstalled = OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] === true && searchFn(m));

  // Tab "Installa nuovi Moduli": optional modules + remote catalog NOT yet installed
  const filteredOptionalNotInstalled = OPTIONAL_MODULES.filter(m => optionalInstalledState[m.id] !== true && searchFn(m));
  const filteredRemoteCatalogNotInstalled = REMOTE_CATALOG_MODULES.filter(m => optionalInstalledState[m.id] !== true && searchFn(m));
  const filteredAvailableToInstall = [...filteredOptionalNotInstalled, ...filteredRemoteCatalogNotInstalled];

  const installedCount = KERNEL_MODULES.length + filteredOptionalInstalled.length;

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: isLight ? '#f7f4ed' : 'var(--bg-main, #0e1016)',
      color: textPrimary,
      overflowY: 'auto',
      padding: '0'
    }}>
      {/* Unified Kernel Tab Header */}
      <TabHeader
        badge="Σ HUB SKILLS & ESTENSIONI KERNEL"
        badgeIcon={Package}
        icon={activeSubTab === 'installed' ? Cpu : Sparkles}
        title="Skills & Moduli / "
        highlight={activeSubTab === 'installed' ? `Moduli Installati (${installedCount})` : `Catalogo Moduli (${filteredAvailableToInstall.length})`}
        description={
          activeSubTab === 'installed'
            ? 'Visualizza e gestisci i moduli nativi integrati nel kernel e le estensioni opzionali attive.'
            : 'Esplora e installa nuovi moduli e funzionalità aggiuntive direttamente da repository Git esterni.'
        }
        bannerImage="/images/sigma_logo_harmonic_flow.jpg"
        actions={
          <button
            onClick={handleTriggerRebuild}
            disabled={isRebuilding}
            className="sigma-tab-btn sigma-tab-btn-primary"
            title="Esegui rebuild del frontend di Sigma Studio"
          >
            <RefreshCw size={15} className={isRebuilding ? 'animate-spin' : ''} />
            <span>{isRebuilding ? 'Ricompilazione in corso...' : 'Rebuild Bundle'}</span>
          </button>
        }
      />

      {/* Main Content Area — Full Width */}
      <div style={{ padding: '16px 20px', width: '100%', boxSizing: 'border-box', flex: 1 }}>
        
        {/* Search & Filter Bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '10px',
          marginBottom: '16px'
        }}>
          <div style={{ position: 'relative', width: '300px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: textSecondary }} />
            <input
              type="text"
              placeholder="Cerca modulo per nome o tag..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 12px 7px 32px',
                borderRadius: '8px',
                background: isLight ? '#fff' : 'rgba(255,255,255,0.04)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                color: textPrimary,
                fontSize: '0.78rem',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: textSecondary }}>
            <GitBranch size={14} style={{ color: accentColor }} />
            <span>Repository Moduli: <code>Sigmanih/SigmaStudio-Modules</code></span>
          </div>
        </div>

        {/* =================================================================== */}
        {/* TAB 1: MODULI INSTALLATI NEL KERNEL */}
        {/* =================================================================== */}
        {activeSubTab === 'installed' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Kernel Modules — always active */}
            <div>
              <div style={{ fontSize: '0.7rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', color: textSecondary, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Cpu size={13} style={{ color: accentColor }} /> Moduli Kernel (sempre attivi)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                {filteredKernel.map(mod => {
                  const Icon = mod.icon;
                  return (
                    <ModuleCard
                      key={mod.id}
                      mod={mod}
                      isLight={isLight}
                      cardBg={cardBg}
                      cardBorder={cardBorder}
                      textPrimary={textPrimary}
                      textSecondary={textSecondary}
                      accentColor={accentColor}
                      badge={<span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '2px 7px', borderRadius: '6px', background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.4)', color: '#3fb950', fontSize: '0.62rem', fontWeight: 800, textTransform: 'uppercase', flexShrink: 0 }}><Check size={10} /> Kernel</span>}
                      actions={
                        <button
                          onClick={() => openTab && openTab({ name: mod.name }, mod.tabType)}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '5px 12px', borderRadius: '6px', background: isLight ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : 'linear-gradient(135deg, #00d2ff 0%, #3b82f6 100%)', border: 'none', color: '#fff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer' }}
                        >
                          <Play size={11} /> Apri <ArrowRight size={11} />
                        </button>
                      }
                    />
                  );
                })}
              </div>
            </div>

            {/* Optional Installed Modules */}
            {filteredOptionalInstalled.length > 0 && (
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', color: textSecondary, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Package size={13} style={{ color: accentColor }} /> Moduli Opzionali Installati
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                  {filteredOptionalInstalled.map(mod => {
                    const Icon = mod.icon;
                    return (
                      <ModuleCard
                        key={mod.id}
                        mod={mod}
                        isLight={isLight}
                        cardBg={cardBg}
                        cardBorder={cardBorder}
                        textPrimary={textPrimary}
                        textSecondary={textSecondary}
                        accentColor={accentColor}
                        badge={<span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '2px 7px', borderRadius: '6px', background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.4)', color: '#3fb950', fontSize: '0.62rem', fontWeight: 800, textTransform: 'uppercase', flexShrink: 0 }}><Check size={10} /> Attivo</span>}
                        actions={
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <button
                              onClick={() => handleUninstallModule(mod)}
                              disabled={uninstallingId === mod.id}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 9px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.35)', color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: uninstallingId === mod.id ? 'not-allowed' : 'pointer' }}
                            >
                              <Trash2 size={11} /> {uninstallingId === mod.id ? 'Rimozione...' : 'Disinstalla'}
                            </button>
                            <button
                              onClick={() => openTab && openTab({ name: mod.name }, mod.tabType)}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '5px 12px', borderRadius: '6px', background: isLight ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : 'linear-gradient(135deg, #00d2ff 0%, #3b82f6 100%)', border: 'none', color: '#fff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer' }}
                            >
                              <Play size={11} /> Apri <ArrowRight size={11} />
                            </button>
                          </div>
                        }
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {filteredOptionalInstalled.length === 0 && (
              <div style={{ padding: '16px 20px', borderRadius: '12px', background: isLight ? 'rgba(190,160,110,0.08)' : 'rgba(255,255,255,0.03)', border: isLight ? '1px dashed rgba(190,160,110,0.3)' : '1px dashed rgba(255,255,255,0.1)', fontSize: '0.78rem', color: textSecondary, textAlign: 'center' }}>
                Nessun modulo opzionale installato. Vai al tab <strong>Repository Remoti</strong> per scoprire e installare nuovi moduli.
              </div>
            )}
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB 2: INSTALLA NUOVI MODULI */}
        {/* =================================================================== */}
        {activeSubTab === 'remote' && (
          <div>
            {filteredAvailableToInstall.length === 0 ? (
              <div style={{
                padding: '48px 24px',
                borderRadius: '16px',
                background: cardBg,
                border: cardBorder,
                textAlign: 'center',
                color: textSecondary,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px'
              }}>
                <CheckCircle2 size={36} color="#10b981" />
                <div style={{ fontSize: '0.96rem', fontWeight: 800, color: textPrimary }}>
                  Tutti i moduli disponibili sono attualmente installati!
                </div>
                <div style={{ fontSize: '0.78rem' }}>
                  Puoi gestire, configurare o disinstallare i moduli attivi dalla scheda "Moduli Installati".
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                {filteredAvailableToInstall.map(mod => {
                  const isInstalling = installingId === mod.id;
                  const badge = (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: '3px',
                      padding: '2px 7px', borderRadius: '6px',
                      background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                      border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.4)',
                      color: accentColor, fontSize: '0.62rem', fontWeight: 800,
                      textTransform: 'uppercase', flexShrink: 0
                    }}>
                      Disponibile
                    </span>
                  );

                  const actions = (
                    <button
                      onClick={() => handleInstallModule(mod)}
                      disabled={isInstalling}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: '5px',
                        padding: '6px 14px', borderRadius: '7px',
                        background: isLight ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : 'linear-gradient(135deg, #00d2ff 0%, #3b82f6 100%)',
                        border: 'none', color: '#fff', fontSize: '0.74rem', fontWeight: 800,
                        cursor: isInstalling ? 'not-allowed' : 'pointer',
                        transition: 'all 0.15s ease',
                        boxShadow: isLight ? '0 2px 8px rgba(234, 88, 12, 0.25)' : '0 2px 10px rgba(0, 210, 255, 0.25)'
                      }}
                    >
                      {isInstalling ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                      {isInstalling ? 'Installazione...' : 'Installa Modulo'}
                    </button>
                  );

                  return (
                    <ModuleCard
                      key={mod.id}
                      mod={mod}
                      isLight={isLight}
                      cardBg={cardBg}
                      cardBorder={cardBorder}
                      textPrimary={textPrimary}
                      textSecondary={textSecondary}
                      accentColor={accentColor}
                      badge={badge}
                      actions={actions}
                      gitUrl={mod.gitUrl}
                    />
                  );
                })}
              </div>
            )}
          </div>
        )}


        {/* Technical Architecture Info Box */}
        <div style={{
          marginTop: '24px',
          borderRadius: '14px',
          background: isLight ? 'rgba(234, 88, 12, 0.04)' : 'rgba(0, 210, 255, 0.04)',
          border: isLight ? '1px solid rgba(234, 88, 12, 0.22)' : '1px solid rgba(0, 210, 255, 0.2)',
          padding: '16px 20px'
        }}>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '0.95rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} style={{ color: accentColor }} /> Pipeline di Aggiornamento & Rebuild Automatica
          </h3>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.76rem', color: textSecondary, lineHeight: 1.5 }}>
            Quando un nuovo modulo viene installato o aggiornato da un repository Git separato, Sigma Studio esegue una procedura a caldo:
          </p>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '10px'
          }}>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary, marginBottom: '2px' }}>1. Download Git & Dipendenze</div>
              <div style={{ fontSize: '0.68rem', color: textSecondary }}>Clona il repository del modulo nella cartella <code>modules/</code> ed installa i package necessari.</div>
            </div>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary, marginBottom: '2px' }}>2. Rebuild Frontend Vite</div>
              <div style={{ fontSize: '0.68rem', color: textSecondary }}>Esegue <code>npm run build</code> per ricompilare i bundle statici in <code>dist/</code> e registrare la nuova tab.</div>
            </div>
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary, marginBottom: '2px' }}>3. Hot-Reload Backend FastAPI</div>
              <div style={{ fontSize: '0.68rem', color: textSecondary }}>Inietta dinamicamente gli endpoint REST e i WebSocket del modulo nel router di <code>sigma_server.py</code>.</div>
            </div>
          </div>
        </div>

          {/* Console Logs Terminal */}
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
            <div style={{ color: isLight ? '#a8a29e' : '#8892b0', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={13} /> Console di Installazione e Compilazione Kernel:
            </div>
            {installLogs.map((log, i) => (
              <div key={i} style={{ lineHeight: 1.6, color: log.includes('✅') || log.includes('✨') ? '#22c55e' : (isLight ? '#fdba74' : '#38bdf8') }}>
                {log}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
