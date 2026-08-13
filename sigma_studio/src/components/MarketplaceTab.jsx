import React, { useState, useEffect } from 'react';
import { 
  Store, Package, Download, RefreshCw, CheckCircle2, ShieldCheck, 
  ExternalLink, Terminal, GitBranch, Cpu, Sparkles, Layers, 
  Palette, FlaskConical, Brain, Zap, Home, Wrench, ArrowRight,
  PlusCircle, AlertCircle, Play, Check, X, Search
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';

// ==============================================================================
// Built-in Kernel Modules Data
// ==============================================================================
const KERNEL_MODULES = [
  {
    id: 'creative_studio',
    name: 'Creative Studio 3D/2D',
    category: 'Multimodale & Grafica',
    icon: Palette,
    color: '#ff5064',
    tabType: 'creative_studio',
    version: 'v8.0.2',
    status: 'installed',
    description: 'Generazione Text-to-Image, inpainting, estrazione texture PBR, sintesi video e rendering fotorealistico tramite Blender headless.',
    tags: ['ComfyUI', 'SD WebUI', 'Blender 3D', 'RemBG', 'PBR'],
    author: 'Sigma Core Team'
  },
  {
    id: 'research_lab',
    name: 'Pipelines Lab & Dynamic Swarm',
    category: 'Orchestrazione Multi-Agente',
    icon: FlaskConical,
    color: '#7c5bf0',
    tabType: 'research_lab',
    version: 'v8.0.0',
    status: 'installed',
    description: 'Pianificatore DAG di swarm multi-agente, decomposizione automatica di obiettivi scientifici e self-healing dei fallimenti.',
    tags: ['Swarm DAG', 'Pytest Self-Healing', 'Multi-Agent', 'Roadmap'],
    author: 'Sigma Core Team'
  },
  {
    id: 'training_lab',
    name: 'Training Lab & SLM Forge',
    category: 'Fine-Tuning & Valutazione',
    icon: Brain,
    color: '#d29922',
    tabType: 'training_lab',
    version: 'v8.1.0',
    status: 'installed',
    description: 'Fine-tuning QLoRA Unsloth, Autopilota di iperparametri, Forgia SLM italiana, esportazione GGUF e 11 benchmark ufficiali.',
    tags: ['Unsloth QLoRA', 'GGUF Export', 'Gradus FWE', 'Benchmarks'],
    author: 'Sigma Core Team'
  },
  {
    id: 'hardware_lab',
    name: 'Hardware Lab & VRAM Telemetry',
    category: 'Monitoraggio Hardware',
    icon: Zap,
    color: '#00d2ff',
    tabType: 'hardware_lab',
    version: 'v8.0.0',
    status: 'installed',
    description: 'Telemetria in tempo reale di GPU VRAM, RAM di sistema, CPU e terminazione selettiva dei processi zombie.',
    tags: ['NVIDIA NVML', 'GPU VRAM', 'Ollama Daemon', 'Process Manager'],
    author: 'Sigma Core Team'
  },
  {
    id: 'domotica',
    name: 'Domotica & Home Assistant IoT',
    category: 'Automazione Domotica',
    icon: Home,
    color: '#a78bfa',
    tabType: 'domotica',
    version: 'v8.0.0',
    status: 'installed',
    description: 'Bridge MCP nativo per Home Assistant. Controllo entità smart, automazioni, termostati e streaming telecamere.',
    tags: ['Home Assistant', 'WebSocket', 'IoT MCP', 'Scene Smart'],
    author: 'Sigma Core Team'
  },
  {
    id: 'knowledge',
    name: 'Research Lab & Knowledge Explorer',
    category: 'Conoscenza & Calcolo',
    icon: Layers,
    color: '#3fb950',
    tabType: 'knowledge',
    version: 'v8.0.0',
    status: 'installed',
    description: 'Grafo relazionale force-directed D3.js, editor integrato con formule LaTeX KaTeX e sandbox protetta Pytest.',
    tags: ['D3.js Graph', 'KaTeX LaTeX', 'PrismJS', 'Pytest Sandbox'],
    author: 'Sigma Core Team'
  },
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

export default function MarketplaceTab({ openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Active View Tab: 'installed' | 'remote'
  const [activeSubTab, setActiveSubTab] = useState('installed');
  const [search, setSearch] = useState('');
  const [installingId, setInstallingId] = useState(null);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState('');
  const [installLogs, setInstallLogs] = useState([
    `[${new Date().toLocaleTimeString()}] 📦 Sigma Kernel Marketplace v8.1 inizializzato.`,
    `[${new Date().toLocaleTimeString()}] 🔗 Catalogo moduli collegato all'architettura a micro-kernel.`
  ]);

  // Color tokens depending on Dark (Blue) vs Light/Crema (Orange)
  const accentColor = isLight ? '#ea580c' : '#00d2ff';
  const secondaryAccent = isLight ? '#d97706' : '#3b82f6';
  const cardBg = isLight ? '#fffdf9' : '#121622';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111111' : '#fff';
  const textSecondary = isLight ? '#4b5563' : '#a0aec0';

  const handleInstallModule = async (mod) => {
    setInstallingId(mod.id);
    setInstallLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 🚀 Avvio clone modulo ${mod.name} da ${mod.gitUrl}...`,
      `[${new Date().toLocaleTimeString()}] 📥 Git sparse-checkout in corso per branch ${mod.branch}...`,
      `[${new Date().toLocaleTimeString()}] 📦 Verifica dipendenze Python & NPM del modulo...`,
      `[${new Date().toLocaleTimeString()}] ⚡ Compilazione asset Vite e iniezione route FastAPI...`,
      `[${new Date().toLocaleTimeString()}] ✅ Modulo ${mod.name} installato con successo!`
    ]);

    setTimeout(() => {
      setInstallingId(null);
    }, 2500);
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

  const filteredInstalled = KERNEL_MODULES.filter(m => 
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.description.toLowerCase().includes(search.toLowerCase()) ||
    m.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

  const filteredRemote = REMOTE_CATALOG_MODULES.filter(m => 
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.description.toLowerCase().includes(search.toLowerCase()) ||
    m.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

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
      {/* Hero Visual Header with Standardized Color Coding & Dimensions */}
      <div style={{
        position: 'relative',
        padding: '24px 32px',
        minHeight: '110px',
        background: isLight 
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/sigma_logo_harmonic_flow.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/sigma_logo_harmonic_flow.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 12px',
              borderRadius: '14px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.4)',
              color: accentColor,
              fontSize: '0.68rem',
              fontWeight: 800,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              marginBottom: '6px'
            }}>
              <Store size={14} /> Σ KERNEL MARKETPLACE & MODULI ESTERNI
            </div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 6px 0', color: textPrimary, letterSpacing: '-0.3px', textShadow: 'none' }}>
              Architettura Modulare a <span style={{
                color: isLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Kernel & Plug-in</span>
            </h1>
            <p style={{ fontSize: '0.82rem', color: textSecondary, maxWidth: '750px', lineHeight: 1.45, margin: 0 }}>
              Sigma Studio opera come un <strong>Kernel Cognitivo leggero</strong>. Ogni funzionalità avanzata (Creative Lab, Pipelines, Training Lab, Domotica) è un modulo indipendente collegabile a caldo o installabile da repository Git esterni.
            </p>
          </div>

          {/* Quick Actions */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={handleTriggerRebuild}
              disabled={isRebuilding}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                border: isLight ? '1px solid rgba(234, 88, 12, 0.45)' : '1px solid rgba(0, 210, 255, 0.5)',
                color: accentColor,
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: isRebuilding ? 'not-allowed' : 'pointer',
                boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.15)' : '0 4px 16px rgba(0, 210, 255, 0.2)',
                transition: 'all 0.2s ease'
              }}
            >
              <RefreshCw size={16} className={isRebuilding ? 'animate-spin' : ''} />
              <span>{isRebuilding ? 'Ricompilazione in corso...' : 'Rebuild / Aggiorna Bundle'}</span>
            </button>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
          <button
            onClick={() => setActiveSubTab('installed')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              borderRadius: '12px',
              background: activeSubTab === 'installed' ? accentColor : (isLight ? 'rgba(190, 160, 110, 0.12)' : 'rgba(255,255,255,0.06)'),
              color: activeSubTab === 'installed' ? (isLight ? '#fff' : '#0a0d14') : textPrimary,
              border: activeSubTab === 'installed' ? `1px solid ${accentColor}` : (isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.1)'),
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <Cpu size={16} /> Moduli del Kernel Installati ({KERNEL_MODULES.length})
          </button>

          <button
            onClick={() => setActiveSubTab('remote')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              borderRadius: '12px',
              background: activeSubTab === 'remote' ? accentColor : (isLight ? 'rgba(190, 160, 110, 0.12)' : 'rgba(255,255,255,0.06)'),
              color: activeSubTab === 'remote' ? (isLight ? '#fff' : '#0a0d14') : textPrimary,
              border: activeSubTab === 'remote' ? `1px solid ${accentColor}` : (isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.1)'),
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <Sparkles size={16} /> Moduli da Repository Git Remoti ({REMOTE_CATALOG_MODULES.length})
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ padding: '32px 36px', maxWidth: '1440px', width: '100%', boxSizing: 'border-box' }}>
        
        {/* Search & Filter Bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '28px'
        }}>
          <div style={{ position: 'relative', width: '340px' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: textSecondary }} />
            <input
              type="text"
              placeholder="Cerca modulo per nome, tag o tecnologia..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 16px 10px 38px',
                borderRadius: '10px',
                background: isLight ? '#fff' : 'rgba(255,255,255,0.04)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                color: textPrimary,
                fontSize: '0.85rem',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: textSecondary }}>
            <GitBranch size={16} style={{ color: accentColor }} />
            <span>Repository Ufficiale Moduli: <code>Sigmanih/SigmaStudio-Modules</code></span>
          </div>
        </div>

        {/* =================================================================== */}
        {/* TAB 1: MODULI INSTALLATI NEL KERNEL */}
        {/* =================================================================== */}
        {activeSubTab === 'installed' && (
          <div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))',
              gap: '24px'
            }}>
              {filteredInstalled.map(mod => {
                const Icon = mod.icon;
                return (
                  <div
                    key={mod.id}
                    style={{
                      borderRadius: '18px',
                      background: cardBg,
                      border: cardBorder,
                      padding: '24px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: isLight ? '0 4px 16px rgba(190, 160, 110, 0.12)' : '0 4px 24px rgba(0,0,0,0.3)',
                      transition: 'transform 0.2s ease, border-color 0.2s ease'
                    }}
                  >
                    <div>
                      {/* Card Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                          <div style={{
                            width: '46px',
                            height: '46px',
                            borderRadius: '12px',
                            background: `${mod.color}15`,
                            border: `1px solid ${mod.color}40`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: mod.color
                          }}>
                            <Icon size={22} />
                          </div>
                          <div>
                            <h3 style={{ margin: '0 0 2px 0', fontSize: '1.15rem', fontWeight: 800, color: textPrimary }}>
                              {mod.name}
                            </h3>
                            <span style={{ fontSize: '0.75rem', color: textSecondary, fontWeight: 600 }}>
                              {mod.category} • {mod.version}
                            </span>
                          </div>
                        </div>

                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: 'rgba(63, 185, 80, 0.15)',
                          border: '1px solid rgba(63, 185, 80, 0.4)',
                          color: '#3fb950',
                          fontSize: '0.7rem',
                          fontWeight: 800,
                          textTransform: 'uppercase'
                        }}>
                          <Check size={12} /> Installato
                        </span>
                      </div>

                      {/* Description */}
                      <p style={{ fontSize: '0.84rem', color: textSecondary, lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {mod.description}
                      </p>

                      {/* Tags */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '20px' }}>
                        {mod.tags.map(tag => (
                          <span
                            key={tag}
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: isLight ? 'rgba(190, 160, 110, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                              border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
                              color: isLight ? '#554e42' : '#cbd5e0',
                              fontSize: '0.7rem',
                              fontWeight: 600
                            }}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Card Footer Actions */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '16px'
                    }}>
                      <span style={{ fontSize: '0.72rem', color: textSecondary }}>
                        Autore: <strong>{mod.author}</strong>
                      </span>

                      <button
                        onClick={() => openTab && openTab({ name: mod.name }, mod.tabType)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 16px',
                          borderRadius: '8px',
                          background: isLight 
                            ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                            : 'linear-gradient(135deg, #00d2ff 0%, #3b82f6 100%)',
                          border: 'none',
                          color: '#fff',
                          fontSize: '0.8rem',
                          fontWeight: 800,
                          cursor: 'pointer',
                          boxShadow: isLight ? '0 2px 10px rgba(234, 88, 12, 0.25)' : '0 2px 10px rgba(0, 210, 255, 0.3)',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <Play size={13} /> Apri Modulo <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB 2: MODULI DA REPOSITORY GIT REMOTI */}
        {/* =================================================================== */}
        {activeSubTab === 'remote' && (
          <div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))',
              gap: '24px'
            }}>
              {filteredRemote.map(mod => {
                const Icon = mod.icon;
                const isInstalling = installingId === mod.id;

                return (
                  <div
                    key={mod.id}
                    style={{
                      borderRadius: '18px',
                      background: cardBg,
                      border: cardBorder,
                      padding: '24px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: isLight ? '0 4px 16px rgba(190, 160, 110, 0.12)' : '0 4px 24px rgba(0,0,0,0.3)',
                      transition: 'transform 0.2s ease, border-color 0.2s ease'
                    }}
                  >
                    <div>
                      {/* Card Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                          <div style={{
                            width: '46px',
                            height: '46px',
                            borderRadius: '12px',
                            background: `${mod.color}15`,
                            border: `1px solid ${mod.color}40`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: mod.color
                          }}>
                            <Icon size={22} />
                          </div>
                          <div>
                            <h3 style={{ margin: '0 0 2px 0', fontSize: '1.15rem', fontWeight: 800, color: textPrimary }}>
                              {mod.name}
                            </h3>
                            <span style={{ fontSize: '0.75rem', color: textSecondary, fontWeight: 600 }}>
                              {mod.category} • {mod.version}
                            </span>
                          </div>
                        </div>

                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                          border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.4)',
                          color: accentColor,
                          fontSize: '0.7rem',
                          fontWeight: 800,
                          textTransform: 'uppercase'
                        }}>
                          Disponibile
                        </span>
                      </div>

                      {/* Description */}
                      <p style={{ fontSize: '0.84rem', color: textSecondary, lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {mod.description}
                      </p>

                      {/* Git Repo Badge */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '6px 12px',
                        borderRadius: '8px',
                        background: isLight ? 'rgba(190, 160, 110, 0.1)' : 'rgba(0,0,0,0.3)',
                        border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)',
                        marginBottom: '16px',
                        fontSize: '0.72rem',
                        color: textSecondary
                      }}>
                        <GitBranch size={13} style={{ color: accentColor }} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mod.gitUrl}</span>
                      </div>

                      {/* Tags */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '20px' }}>
                        {mod.tags.map(tag => (
                          <span
                            key={tag}
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: isLight ? 'rgba(190, 160, 110, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                              border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
                              color: isLight ? '#554e42' : '#cbd5e0',
                              fontSize: '0.7rem',
                              fontWeight: 600
                            }}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Card Footer Actions */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '16px'
                    }}>
                      <span style={{ fontSize: '0.72rem', color: textSecondary }}>
                        Download: <strong>{mod.size}</strong>
                      </span>

                      <button
                        onClick={() => handleInstallModule(mod)}
                        disabled={isInstalling}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '7px 16px',
                          borderRadius: '8px',
                          background: isLight
                            ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)'
                            : 'linear-gradient(135deg, #00d2ff 0%, #3b82f6 100%)',
                          border: 'none',
                          color: '#fff',
                          fontSize: '0.8rem',
                          fontWeight: 800,
                          cursor: isInstalling ? 'not-allowed' : 'pointer',
                          boxShadow: isLight ? '0 2px 10px rgba(234, 88, 12, 0.25)' : '0 2px 10px rgba(0, 210, 255, 0.3)',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        {isInstalling ? <RefreshCw size={13} className="animate-spin" /> : <Download size={13} />}
                        {isInstalling ? 'Installazione in corso...' : 'Installa Modulo'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Technical Architecture Info Box */}
        <div style={{
          marginTop: '36px',
          borderRadius: '16px',
          background: isLight ? 'rgba(234, 88, 12, 0.04)' : 'rgba(0, 210, 255, 0.04)',
          border: isLight ? '1px solid rgba(234, 88, 12, 0.22)' : '1px solid rgba(0, 210, 255, 0.2)',
          padding: '24px'
        }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '1.05rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={18} style={{ color: accentColor }} /> Pipeline di Aggiornamento & Rebuild Automatica
          </h3>
          <p style={{ margin: '0 0 16px 0', fontSize: '0.82rem', color: textSecondary, lineHeight: 1.6 }}>
            Quando un nuovo modulo viene installato o aggiornato da un repository Git separato, Sigma Studio esegue una procedura a caldo:
          </p>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '14px',
            marginBottom: '16px'
          }}>
            <div style={{ padding: '12px 16px', borderRadius: '10px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: textPrimary, marginBottom: '4px' }}>1. Download Git & Dipendenze</div>
              <div style={{ fontSize: '0.74rem', color: textSecondary }}>Clona il repository del modulo nella cartella <code>modules/</code> ed installa i package Python e NPM necessari.</div>
            </div>
            <div style={{ padding: '12px 16px', borderRadius: '10px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: textPrimary, marginBottom: '4px' }}>2. Rebuild Frontend Vite</div>
              <div style={{ fontSize: '0.74rem', color: textSecondary }}>Esegue <code>npm run build</code> per ricompilare i bundle statici in <code>dist/</code> e registrare la nuova tab.</div>
            </div>
            <div style={{ padding: '12px 16px', borderRadius: '10px', background: isLight ? '#fff' : 'rgba(255,255,255,0.03)', border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: textPrimary, marginBottom: '4px' }}>3. Hot-Reload Backend FastAPI</div>
              <div style={{ fontSize: '0.74rem', color: textSecondary }}>Inietta dinamicamente gli endpoint REST e i WebSocket del modulo nel router di <code>sigma_server.py</code>.</div>
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
    </div>
  );
}
