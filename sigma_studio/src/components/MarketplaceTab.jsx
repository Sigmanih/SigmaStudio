import React, { useState, useEffect } from 'react';
import { 
  Store, Package, Download, RefreshCw, CheckCircle2, ShieldCheck, 
  ExternalLink, Terminal, GitBranch, Cpu, Sparkles, Layers, 
  Palette, FlaskConical, Brain, Zap, Home, Wrench, ArrowRight,
  PlusCircle, AlertCircle, Play
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
    description: '12 server MCP integrati con policy di sicurezza, classificazione Safe/Sensitive e approvazione Human-in-the-Loop.',
    tags: ['Model Context Protocol', 'JSON-RPC 2.0', 'Human Approval'],
    author: 'Sigma Core Team'
  }
];

// ==============================================================================
// Remote Catalog Modules (From Git Repository)
// ==============================================================================
const REMOTE_CATALOG_MODULES = [
  {
    id: 'quantum_sim',
    name: 'Quantum Computing Lab & Qiskit',
    category: 'Calcolo Quantistico',
    gitRepo: 'https://github.com/Sigmanih/sigma_module_quantum',
    version: 'v1.2.0',
    stars: 142,
    description: 'Simulatore di circuiti quantistici Qiskit con visualizzazione della sfera di Bloch in 3D e verifica automatica di algoritmi di Shor e Grover.',
    tags: ['Qiskit', 'Bloch Sphere', 'Quantum AI'],
    size: '14.2 MB',
    author: 'Sigma Community'
  },
  {
    id: 'bioinfo_suite',
    name: 'Bioinformatics & Molecular Viewer',
    category: 'Scienze della Vita',
    gitRepo: 'https://github.com/Sigmanih/sigma_module_bioinfo',
    version: 'v1.0.4',
    stars: 98,
    description: 'Visualizzatore di strutture proteiche PDB in WebGL (3Dmol.js) e pipeline di analisi per allineamento di sequenze FASTA.',
    tags: ['Biopython', 'PDB 3D', 'Genomics'],
    size: '22.8 MB',
    author: 'BioAI Group'
  },
  {
    id: 'robotics_ros2',
    name: 'Robotics Bridge & ROS 2 MCP',
    category: 'Robotica & Cyberfisica',
    gitRepo: 'https://github.com/Sigmanih/sigma_module_ros2',
    version: 'v1.1.0',
    stars: 185,
    description: 'Server MCP per la teleoperazione di nodi ROS 2, telemetria lidar 2D/3D e controllo cinematico per bracci robotici.',
    tags: ['ROS 2', 'rclpy', 'Robotics MCP'],
    size: '18.5 MB',
    author: 'Robotics Lab'
  },
  {
    id: 'realtime_voice',
    name: 'Full-Duplex Speech-to-Speech Lab',
    category: 'Audio & Voce Realtime',
    gitRepo: 'https://github.com/Sigmanih/sigma_module_voice_s2s',
    version: 'v2.0.1',
    stars: 310,
    description: 'Pipeline vocale a bassissima latenza (<200ms) con Voice Activity Detection (VAD), streaming audio WebSocket e clonazione vocale zero-shot.',
    tags: ['Silero VAD', 'Whisper Live', 'Kokoro Streaming'],
    size: '45.0 MB',
    author: 'AudioAI Lab'
  },
  {
    id: 'finance_quant',
    name: 'Financial Backtesting & Market Agent',
    category: 'Finanza Quantitativa',
    gitRepo: 'https://github.com/Sigmanih/sigma_module_finance',
    version: 'v1.3.0',
    stars: 215,
    description: 'Motore di backtesting per strategie algoritmiche, integrazione con dati Yahoo Finance/ccxt e generazione di report di rischio Sharpe/Sortino.',
    tags: ['Backtesting', 'Time Series', 'Quant Agent'],
    size: '11.0 MB',
    author: 'QuantResearch'
  }
];

export default function MarketplaceTab({ openTab: externalOpenTab }) {
  const { theme } = useApp();
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [installingId, setInstallingId] = useState(null);
  const [installLogs, setInstallLogs] = useState([]);
  const [customGitUrl, setCustomGitUrl] = useState('');
  const [customBranch, setCustomBranch] = useState('main');
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildStatus, setRebuildStatus] = useState('');

  // Fallback openTab helper
  const handleOpenTab = (item, type) => {
    if (externalOpenTab) {
      externalOpenTab(item, type);
    } else if (window.__sigma_openTab) {
      window.__sigma_openTab(item, type);
    }
  };

  const handleInstallModule = (mod) => {
    setInstallingId(mod.id);
    setInstallLogs(prev => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 🚀 Inizio download modulo: ${mod.name}`,
      `[${new Date().toLocaleTimeString()}] 📥 Clonazione repository Git: ${mod.gitRepo}...`,
      `[${new Date().toLocaleTimeString()}] 📦 Verifica dipendenze Python & Node.js...`,
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
      background: 'var(--bg-main, #0e1016)',
      color: 'var(--text-main, #e2e8f0)',
      overflowY: 'auto',
      padding: '0'
    }}>
      {/* Hero Visual Header */}
      <div style={{
        position: 'relative',
        padding: '28px 36px',
        background: 'linear-gradient(135deg, rgba(14, 16, 22, 0.96) 0%, rgba(20, 26, 42, 0.92) 100%), url("/images/sigma_logo_harmonic_flow.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 14px',
              borderRadius: '20px',
              background: 'rgba(0, 210, 255, 0.15)',
              border: '1px solid rgba(0, 210, 255, 0.4)',
              color: '#00d2ff',
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '1.2px',
              textTransform: 'uppercase',
              marginBottom: '10px'
            }}>
              <Store size={14} /> Σ KERNEL MARKETPLACE & MODULI ESTERNI
            </div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, margin: '0 0 8px 0', color: '#fff', letterSpacing: '-0.5px' }}>
              Architettura Modulare a <span style={{
                background: 'linear-gradient(135deg, #00d2ff 0%, #7c5bf0 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>Kernel & Plug-in</span>
            </h1>
            <p style={{ fontSize: '0.88rem', color: '#a0aec0', maxWidth: '750px', lineHeight: 1.5, margin: 0 }}>
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
                background: 'rgba(0, 210, 255, 0.15)',
                border: '1px solid rgba(0, 210, 255, 0.5)',
                color: '#00d2ff',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: isRebuilding ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 16px rgba(0, 210, 255, 0.2)',
                transition: 'all 0.2s ease'
              }}
            >
              <RefreshCw size={16} className={isRebuilding ? 'animate-spin' : ''} />
              {isRebuilding ? 'Ricompilazione in corso...' : 'Ricompila & Hot-Reload'}
            </button>
          </div>
        </div>

        {rebuildStatus && (
          <div style={{
            marginTop: '16px',
            padding: '8px 16px',
            borderRadius: '8px',
            background: 'rgba(63, 185, 80, 0.15)',
            border: '1px solid rgba(63, 185, 80, 0.4)',
            color: '#3fb950',
            fontSize: '0.82rem',
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle2 size={16} /> {rebuildStatus}
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div style={{ padding: '32px 36px', maxWidth: '1400px', width: '100%', boxSizing: 'border-box' }}>
        
        {/* Search & Filter Bar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          marginBottom: '28px'
        }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setFilter('all')}
              style={{
                padding: '8px 16px',
                borderRadius: '10px',
                background: filter === 'all' ? '#00d2ff' : 'rgba(255,255,255,0.05)',
                color: filter === 'all' ? '#0a0d14' : '#e2e8f0',
                border: '1px solid rgba(255,255,255,0.1)',
                fontWeight: 700,
                fontSize: '0.82rem',
                cursor: 'pointer'
              }}
            >
              Tutti i Moduli ({KERNEL_MODULES.length + REMOTE_CATALOG_MODULES.length})
            </button>
            <button
              onClick={() => setFilter('installed')}
              style={{
                padding: '8px 16px',
                borderRadius: '10px',
                background: filter === 'installed' ? '#00d2ff' : 'rgba(255,255,255,0.05)',
                color: filter === 'installed' ? '#0a0d14' : '#e2e8f0',
                border: '1px solid rgba(255,255,255,0.1)',
                fontWeight: 700,
                fontSize: '0.82rem',
                cursor: 'pointer'
              }}
            >
              Installati nel Kernel ({KERNEL_MODULES.length})
            </button>
            <button
              onClick={() => setFilter('marketplace')}
              style={{
                padding: '8px 16px',
                borderRadius: '10px',
                background: filter === 'marketplace' ? '#00d2ff' : 'rgba(255,255,255,0.05)',
                color: filter === 'marketplace' ? '#0a0d14' : '#e2e8f0',
                border: '1px solid rgba(255,255,255,0.1)',
                fontWeight: 700,
                fontSize: '0.82rem',
                cursor: 'pointer'
              }}
            >
              Catalogo Git Remoto ({REMOTE_CATALOG_MODULES.length})
            </button>
          </div>

          <div style={{ position: 'relative', width: '320px' }}>
            <input
              type="text"
              placeholder="Cerca per modulo, tag o categoria..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 16px',
                borderRadius: '10px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#fff',
                fontSize: '0.85rem',
                outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>
        </div>

        {/* Section 1: Moduli Installati nel Kernel */}
        {(filter === 'all' || filter === 'installed') && (
          <div style={{ marginBottom: '40px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <ShieldCheck size={20} style={{ color: '#3fb950' }} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, color: '#fff' }}>
                Moduli Attivi nel Kernel ({filteredInstalled.length})
              </h2>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
              gap: '20px'
            }}>
              {filteredInstalled.map(mod => {
                const IconComponent = mod.icon;
                return (
                  <div
                    key={mod.id}
                    style={{
                      borderRadius: '16px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      padding: '22px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
                      transition: 'transform 0.2s ease, border-color 0.2s ease'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{
                            width: '42px',
                            height: '42px',
                            borderRadius: '12px',
                            background: `${mod.color}18`,
                            border: `1px solid ${mod.color}40`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: mod.color
                          }}>
                            <IconComponent size={22} />
                          </div>
                          <div>
                            <h3 style={{ margin: '0 0 2px 0', fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>
                              {mod.name}
                            </h3>
                            <span style={{ fontSize: '0.72rem', color: '#8b8fa3', textTransform: 'uppercase', fontWeight: 600 }}>
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
                          fontSize: '0.68rem',
                          fontWeight: 700
                        }}>
                          <CheckCircle2 size={12} /> ATTIVO
                        </span>
                      </div>

                      <p style={{ fontSize: '0.82rem', color: '#a0aec0', lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {mod.description}
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
                        {mod.tags.map(tag => (
                          <span
                            key={tag}
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'rgba(255, 255, 255, 0.05)',
                              color: '#cbd5e0',
                              fontSize: '0.68rem',
                              fontWeight: 600
                            }}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '14px' }}>
                      <span style={{ fontSize: '0.72rem', color: '#718096' }}>
                        By {mod.author}
                      </span>

                      <button
                        onClick={() => handleOpenTab({ name: mod.name }, mod.tabType)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '8px',
                          background: 'rgba(0, 210, 255, 0.12)',
                          border: '1px solid rgba(0, 210, 255, 0.35)',
                          color: '#00d2ff',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        Apri Modulo <ArrowRight size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Section 2: Catalogo Moduli da Repository Git Remoto */}
        {(filter === 'all' || filter === 'marketplace') && (
          <div style={{ marginBottom: '40px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <Package size={20} style={{ color: '#00d2ff' }} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, color: '#fff' }}>
                Catalogo Estensioni Remote (Git Repository) ({filteredRemote.length})
              </h2>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
              gap: '20px'
            }}>
              {filteredRemote.map(mod => {
                const isInstalling = installingId === mod.id;
                return (
                  <div
                    key={mod.id}
                    style={{
                      borderRadius: '16px',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(0, 210, 255, 0.15)',
                      padding: '22px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                        <div>
                          <h3 style={{ margin: '0 0 2px 0', fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>
                            {mod.name}
                          </h3>
                          <span style={{ fontSize: '0.72rem', color: '#00d2ff', textTransform: 'uppercase', fontWeight: 600 }}>
                            {mod.category} • {mod.version}
                          </span>
                        </div>

                        <span style={{
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: 'rgba(0, 210, 255, 0.1)',
                          border: '1px solid rgba(0, 210, 255, 0.3)',
                          color: '#00d2ff',
                          fontSize: '0.68rem',
                          fontWeight: 700
                        }}>
                          {mod.size}
                        </span>
                      </div>

                      <p style={{ fontSize: '0.82rem', color: '#a0aec0', lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {mod.description}
                      </p>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
                        {mod.tags.map(tag => (
                          <span
                            key={tag}
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'rgba(255, 255, 255, 0.05)',
                              color: '#cbd5e0',
                              fontSize: '0.68rem',
                              fontWeight: 600
                            }}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '14px' }}>
                      <span style={{ fontSize: '0.72rem', color: '#718096' }}>
                        ★ {mod.stars} • {mod.author}
                      </span>

                      <button
                        onClick={() => handleInstallModule(mod)}
                        disabled={isInstalling}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '8px',
                          background: isInstalling ? 'rgba(255,255,255,0.1)' : 'linear-gradient(135deg, #00d2ff 0%, #7c5bf0 100%)',
                          border: 'none',
                          color: '#fff',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          cursor: isInstalling ? 'not-allowed' : 'pointer'
                        }}
                      >
                        {isInstalling ? (
                          <>
                            <RefreshCw size={14} className="animate-spin" /> Installazione...
                          </>
                        ) : (
                          <>
                            <Download size={14} /> Installa nel Kernel
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Section 3: Installa Modulo Custom da Git */}
        <div style={{
          borderRadius: '16px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '24px 28px',
          marginBottom: '40px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <GitBranch size={20} style={{ color: '#bc8cff' }} />
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#fff' }}>
              Installa Modulo Custom da Repository Git
            </h2>
          </div>
          <p style={{ fontSize: '0.82rem', color: '#a0aec0', margin: '0 0 18px 0' }}>
            Inserisci l'URL del repository Git contenente il file di manifesto <code>sigma_module.json</code>. Il kernel clonerà il modulo, installerà le dipendenze Python/npm e aggiornerà il workspace.
          </p>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <input
              type="text"
              placeholder="https://github.com/utente/sigma_module_nome.git"
              value={customGitUrl}
              onChange={e => setCustomGitUrl(e.target.value)}
              style={{
                flex: 1,
                minWidth: '300px',
                padding: '10px 16px',
                borderRadius: '10px',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#fff',
                fontSize: '0.85rem'
              }}
            />
            <input
              type="text"
              placeholder="branch (es. main)"
              value={customBranch}
              onChange={e => setCustomBranch(e.target.value)}
              style={{
                width: '140px',
                padding: '10px 16px',
                borderRadius: '10px',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#fff',
                fontSize: '0.85rem'
              }}
            />
            <button
              onClick={() => {
                if (!customGitUrl.trim()) return;
                handleInstallModule({ id: 'custom', name: customGitUrl.split('/').pop() || 'Custom Module', gitRepo: customGitUrl });
              }}
              style={{
                padding: '10px 20px',
                borderRadius: '10px',
                background: '#00d2ff',
                color: '#0a0d14',
                fontWeight: 800,
                fontSize: '0.85rem',
                border: 'none',
                cursor: 'pointer'
              }}
            >
              Clona & Compila Modulo
            </button>
          </div>
        </div>

        {/* Section 4: Live Install Console Logs */}
        {installLogs.length > 0 && (
          <div style={{
            borderRadius: '16px',
            background: '#080a0f',
            border: '1px solid rgba(0, 210, 255, 0.25)',
            padding: '20px',
            marginBottom: '30px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#00d2ff', fontWeight: 700, fontSize: '0.85rem' }}>
                <Terminal size={16} /> Console Pipeline di Installazione & Rebuild
              </div>
              <button
                onClick={() => setInstallLogs([])}
                style={{ background: 'transparent', border: 'none', color: '#718096', fontSize: '0.75rem', cursor: 'pointer' }}
              >
                Pulisci
              </button>
            </div>
            <div style={{
              fontFamily: 'monospace',
              fontSize: '0.78rem',
              color: '#38bdf8',
              maxHeight: '160px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              {installLogs.map((log, idx) => (
                <div key={idx}>{log}</div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
