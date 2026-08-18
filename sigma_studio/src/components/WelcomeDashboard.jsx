import React, { useEffect, useState, useCallback } from 'react';
import { 
  FolderTree, MessageSquare, Edit3, Share2, Palette, 
  FlaskConical, Cpu, Home as HomeIcon, Scroll, Microscope, ArrowRight,
  Sun, Moon, Store, Sparkles, ShieldCheck, Zap, Layers,
  Activity, Calendar, Brain, FileText, PieChart, Wrench, Compass, CheckCircle2, Key, DownloadCloud,
  Clock, GitBranch, RefreshCw, AlertTriangle, ExternalLink, Terminal, Check
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';
import TechSpaceCanvas from './common/TechSpaceCanvas';
import SkillsShowcaseSlider, { SKILLS_CATALOG } from './SkillsShowcaseSlider';



// ==============================================================================
// WORKFLOW OPERATIVO DEL KERNEL: DAL DOWNLOAD HUGGING FACE ALLA CHAT AI
// ==============================================================================
const KERNEL_WORKFLOW_STEPS = [
  {
    step: '01',
    phase: '1. ACQUISIZIONE MODELLO',
    badge: 'HUGGING FACE DOWNLOADER',
    title: 'Cerca & Scarica il Modello da Hugging Face',
    subtitle: 'Accedi a Modelli Hub per cercare qualsiasi LLM Open Source (DeepSeek-R1, Qwen 2.5, Llama 3.3, Mistral) con download streaming ad alta velocità e ripresa automatica dei byte.',
    tip: 'Verifica la VRAM richiesta stimata nella scheda del modello prima di scaricare.',
    icon: DownloadCloud,
    color: '#00d2ff',
    tabId: 'model_hub',
    tabName: '⚡ Modelli Hub',
    actionText: 'Cerca su Hugging Face 📥'
  },
  {
    step: '02',
    phase: '2. QUANTIZZAZIONE & FORGIA (TAB 2 MODELLI HUB)',
    badge: 'GGUF CONVERTER & FORGE',
    title: 'Quantizza in GGUF nel 2° Tab di Modelli Hub',
    subtitle: 'Apri la seconda tab di Modelli Hub ("Convertitore & Forgia GGUF") per convertire i pesi nel formato preferito (Q4_K_M per risparmio VRAM, Q5_K_M, Q8_0 o FP16) ed ottimizzare l\'inferenza.',
    tip: 'La quantizzazione è integrata direttamente in Modelli Hub (tab 2) senza bisogno di avviare il training lab.',
    icon: Brain,
    color: '#d29922',
    tabId: 'model_hub',
    tabName: '⚡ Modelli Hub',
    actionText: 'Quantizza in Modelli Hub 🔨'
  },
  {
    step: '03',
    phase: '3. IDENTITÀ OPERATIVA',
    badge: '20 MODELFILE MANIFESTI',
    title: 'Assegna il Ruolo Specialistico con Manifesti Hub',
    subtitle: 'Seleziona uno dei 20 Manifesti disciplinari vincolanti in Manifesti Hub (Architetto, Dev, Matematico, Medico, Giurista, ecc.) per infondere competenze, regole di condotta e parametri operativi standardizzati.',
    tip: 'Il Manifesto vincola l\'agente con istruzioni di sistema rigorose e formato di risposta pulito.',
    icon: Scroll,
    color: '#bc8cff',
    tabId: 'whitepapers_lib',
    tabName: '📜 Manifesti Hub',
    actionText: 'Esplora Manifesti Hub 📜'
  },
  {
    step: '04',
    phase: '4. ESECUZIONE RUNTIME',
    badge: 'SIGMAENGINE O PROVIDERS CLOUD & 12 MCP',
    title: 'Collabora in Chat AI su SigmaEngine o Providers Preferiti',
    subtitle: 'Dialoga in streaming con il modello caricato direttamente in memoria su SigmaEngine Nativo, oppure scegli i tuoi Providers preferiti (OpenAI, Claude, DeepSeek, Google Gemini, Groq, Ollama) per il 100% di integrabilità.',
    tip: '100% interoperabile: puoi passare istantaneamente dal motore locale ai Providers esterni con 12 Server MCP sempre attivi.',
    icon: MessageSquare,
    color: '#3fb950',
    tabId: 'chat',
    tabName: 'AI Chat Workspace',
    actionText: 'Avvia Chat AI Workspace 💬'
  }
];

// ==============================================================================
// GUIDA INSTALLAZIONE MODULI & SKILLS A PIACERE (HOT-RELOAD)
// ==============================================================================
const MODULE_INSTALL_METHODS = [
  {
    method: '01',
    badge: '1-CLICK VISUALE (CONSIGLIATO)',
    title: 'Download Istantaneo dall\'Hub Skills',
    desc: 'Accedi al tab Hub Skills & Estensioni, individua la skill di tuo interesse (Creative Lab 3D, Voice Studio, Docker Sandbox, Domotica) e premi "Scarica". Il modulo viene scaricato gratuitamente da GitHub e montato a caldo nel runtime senza riavviare.',
    icon: Store,
    color: '#00d2ff',
    actionText: 'Apri Hub Skills 📦',
    tabId: 'marketplace',
    tabName: '📦 Hub Skills & Estensioni'
  },
  {
    method: '02',
    badge: 'MODULO CUSTOM / CARTELLE LOCALI',
    title: 'Aggiunta Modulo Manuale in modules/',
    desc: 'Vuoi creare una tua skill personalizzata? Crea una cartella in modules/<nome_skill>/ contenente il file manifest.json (con ID, nome, categoria, icona e percorso componenti). Sigma Studio lo rileva all\'istante aggiungendolo alla barra laterale.',
    icon: FolderTree,
    color: '#7c5bf0',
    actionText: 'Esplora Struttura Cartelle 📁',
    tabId: 'editor',
    tabName: 'Editor Codice'
  },
  {
    method: '03',
    badge: 'STRUMENTI I/O & GOVERNANCE',
    title: 'Estensione con Server MCP Standard',
    desc: 'Per dotare gli agenti AI di nuovi strumenti operativi (Database SQLite personalizzati, API esterne REST, sensori IoT o script CLI), aggiungi la configurazione JSON del server nel tab MCP Tools con governance dei permessi.',
    icon: Wrench,
    color: '#10b981',
    actionText: 'Gestione Server MCP 🔌',
    tabId: 'mcp_hub',
    tabName: 'MCP Tools'
  }
];

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const titleColor = isLight ? '#000000' : '#ffffff';
  const subtitleColor = isLight ? '#000000' : '#8b8fa3';
  const cardBg = isLight ? '#ffffff' : '#121622';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 6px 20px rgba(190, 160, 110, 0.15)' : '0 12px 40px rgba(0,0,0,0.5)';
  const innerCardBg = isLight ? '#fbf8f2' : '#181e2b';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.06)';
  const innerCardText = isLight ? '#000000' : '#cbd5e1';
  const { modulesState } = useModuleState();
  const [manifestiCount, setManifestiCount] = useState(0);
  const [localModelsCount, setLocalModelsCount] = useState(0);
  const [activeMcpCount, setActiveMcpCount] = useState(0);
  const [activeProviderName, setActiveProviderName] = useState('SigmaEngine');
  const [dynamicInstalledModules, setDynamicInstalledModules] = useState([]);

  useEffect(() => {
    // 1. Recupera manifesti attivi
    fetch('/api/list_manifesti')
      .then(r => r.json())
      .then(d => {
        if (d.files && Array.isArray(d.files)) {
          setManifestiCount(d.files.length);
        } else if (d.manifesti && Array.isArray(d.manifesti)) {
          setManifestiCount(d.manifesti.length);
        }
      })
      .catch(() => {});

    // 2. Recupera modelli locali effettivamente scaricati / attivi
    fetch('/api/models/local/list')
      .then(r => r.json())
      .then(d => {
        if (d.models && Array.isArray(d.models)) {
          setLocalModelsCount(d.models.length);
        }
      })
      .catch(() => {});

    // 3. Recupera server MCP attivi
    fetch('/api/mcp/servers')
      .then(r => r.json())
      .then(d => {
        if (d.servers && Array.isArray(d.servers)) {
          const active = d.servers.filter(s => s.status === 'online' || s.status === 'active' || s.connected || s.enabled !== false);
          setActiveMcpCount(active.length);
        }
      })
      .catch(() => {
        setActiveMcpCount(6); // Default baseline MCP servers
      });

    // 4. Recupera provider AI attivo
    fetch('/api/config')
      .then(r => r.json())
      .then(d => {
        if (d.config) {
          const p = d.config.active_provider || d.config.provider;
          if (p === 'sigma_engine') setActiveProviderName('SigmaEngine');
          else if (p === 'ollama') setActiveProviderName('Ollama');
          else if (p === 'openai') setActiveProviderName('OpenAI');
          else if (p === 'anthropic') setActiveProviderName('Claude');
          else if (p === 'deepseek') setActiveProviderName('DeepSeek');
          else if (p === 'google') setActiveProviderName('Gemini');
          else if (p === 'groq') setActiveProviderName('Groq');
          else if (p) setActiveProviderName(p);
        }
      })
      .catch(() => {});

    // 5. Plugin extra installati dal marketplace
    try {
      const stored = localStorage.getItem('sigma_market_installed');
      if (stored) setDynamicInstalledModules(JSON.parse(stored));
    } catch (e) {}
  }, []);

  // Calcolo skills effettivamente attive / installate
  const activeSkillsCount = Object.keys(modulesState || {}).filter(k => k !== 'sigma_model_hub' && modulesState[k] === true).length + dynamicInstalledModules.length;

  return (
    <div className="wg-container" style={{ position: 'relative' }}>
      {/* Canvas Sfondo Spaziale Animato */}
      <TechSpaceCanvas isLight={isLight} />

      {/* Hero Visual Banner */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: isLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.78) 0%, rgba(248, 242, 232, 0.72) 100%), url("/images/hero_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.88) 0%, rgba(14, 22, 42, 0.82) 100%), url("/images/hero_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: 0,
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '740px', display: 'flex', alignItems: 'center', gap: '18px' }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              overflow: 'hidden',
              border: isLight ? '2px solid #ea580c' : '2px solid #00d2ff',
              boxShadow: isLight ? '0 0 20px rgba(234, 88, 12, 0.4)' : '0 0 20px rgba(0, 210, 255, 0.5), inset 0 0 10px rgba(0, 210, 255, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#0a0d14',
              flexShrink: 0
            }}>
              <img 
                src="/images/sigma_logo_harmonic_flow.jpg" 
                alt="Sigma Logo" 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={(e) => { e.target.src = '/sigma_logo.jpg'; }}
              />
            </div>
            <div>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 12px',
                borderRadius: '14px',
                background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
                color: isLight ? '#9a3412' : '#00d2ff',
                fontSize: '0.68rem',
                fontWeight: 800,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                marginBottom: '6px'
              }}>
                <span>🧬</span> Σ SIGMA STUDIO v8.2 — KERNEL COGNITIVO & SKILLS
              </div>

              <h1 style={{
                fontSize: '1.4rem',
                fontWeight: 800,
                color: isLight ? '#000000' : '#ffffff',
                margin: '0 0 6px 0',
                letterSpacing: '-0.3px',
                textShadow: 'none'
              }}>
                Il Sistema Operativo AI-Native per la Conoscenza, la Ricerca e le <span style={{
                  color: isLight ? '#c2410c' : '#00d2ff',
                  fontWeight: 800
                }}>Professioni</span>
              </h1>

              <p style={{
                fontSize: '0.82rem',
                color: isLight ? '#000000' : '#cbd5e0',
                lineHeight: 1.45,
                margin: 0,
                fontWeight: isLight ? 600 : 400
              }}>
                Sigma Studio orchestra il modello unificato Sigma su motore nativo SigmaEngine, i Manifesti per ogni disciplina, 15 Skills componibili da GitHub e 12 Server MCP in un unico ambiente integrato.
              </p>
            </div>
          </div>

          {/* Quick Action Buttons con Tasto Diretto GitHub */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <a
              href="https://github.com/Sigmanih/Sigma_Studio"
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '10px 16px',
                borderRadius: '12px',
                background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(255, 255, 255, 0.15)',
                color: isLight ? '#000000' : '#ffffff',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 16px rgba(0,0,0,0.4)'
              }}
            >
              <ExternalLink size={15} />
              ⭐ GitHub Sigma Studio
            </a>

            <button
              onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
              style={{
                padding: '10px 16px',
                borderRadius: '12px',
                background: isLight ? '#ffffff' : '#181b28',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 210, 255, 0.5)',
                color: isLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 16px rgba(0,0,0,0.4)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              📦 Hub Skills & Estensioni
            </button>

            <button
              onClick={() => openTab({ name: 'AI Chat Workspace' }, 'chat')}
              style={{
                padding: '10px 16px',
                borderRadius: '12px',
                background: isLight ? '#ea580c' : '#00d2ff',
                border: 'none',
                color: '#ffffff',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.3)' : '0 4px 16px rgba(0, 210, 255, 0.35)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              💬 Avvia Chat AI
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 12px 12px 12px', display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
        
        {/* ── METRICHE CHIAVE: SOLO ELEMENTI ATTIVI ──────── */}
        <div className="wg-metrics" style={{ marginTop: '18px', marginBottom: '12px' }}>
          {/* Card 1: Modelli Locali Attivi */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '⚡ Modelli Hub' }, 'model_hub')}
            style={{ borderTop: '3px solid #00d2ff', background: cardBg, cursor: 'pointer' }}
            title="Clicca per aprire Modelli Hub e gestire i modelli scaricati"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🤖</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#0284c7' : '#00d2ff' }}>{localModelsCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Modelli Locali Attivi</span>
          </div>

          {/* Card 2: Manifesti Hub Attivi */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '📜 Manifesti Hub' }, 'whitepapers_lib')}
            style={{ borderTop: '3px solid #bc8cff', background: cardBg, cursor: 'pointer' }}
            title="Clicca per esplorare i ruoli e manifesti attivi"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>📜</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#9333ea' : '#bc8cff' }}>{manifestiCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Manifesti Hub Attivi</span>
          </div>

          {/* Card 3: Skills Modulari Attive */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
            style={{ borderTop: '3px solid #3fb950', background: cardBg, cursor: 'pointer' }}
            title="Clicca per visualizzare o scaricare le skills dall'Hub"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🧩</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#16a34a' : '#3fb950' }}>{activeSkillsCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Skills Modulari Attive</span>
          </div>

          {/* Card 4: Server MCP Attivi */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')}
            style={{ borderTop: '3px solid #ff5064', background: cardBg, cursor: 'pointer' }}
            title="Clicca per accedere al gateway MCP e agli strumenti I/O"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔌</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#dc2626' : '#ff5064' }}>{activeMcpCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Server MCP Attivi</span>
          </div>

          {/* Card 5: Provider AI Attivo */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '⚙️ Configurazione Providers' }, 'ai_config')}
            style={{ borderTop: '3px solid #faa03c', background: cardBg, cursor: 'pointer' }}
            title="Clicca per configurare o cambiare il Provider AI attivo"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>⚡</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#d97706' : '#faa03c', fontSize: activeProviderName.length > 10 ? '1rem' : '1.2rem' }}>{activeProviderName}</span>
            </div>
            <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Provider AI Attivo</span>
          </div>
        </div>

        {/* ── BACHECA RILASCI & EVOLUZIONE (COMPATTA, MODERNA & AD ALTO IMPATTO) ─────────── */}
        <div style={{
          margin: '4px 0 16px 0',
          padding: '20px 24px',
          borderRadius: '20px',
          background: cardBg,
          border: cardBorder,
          boxShadow: cardShadow,
          position: 'relative',
          overflow: 'hidden'
        }}>
          {/* Header Bacheca con Versione in Grande Evidenza */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px',
            marginBottom: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
              {/* Badge Versione in Mostra con Effetto Neon / Pill */}
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '12px',
                background: isLight ? 'linear-gradient(135deg, rgba(234, 88, 12, 0.15) 0%, rgba(249, 115, 22, 0.25) 100%)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.2) 0%, rgba(0, 242, 254, 0.3) 100%)',
                border: isLight ? '1.5px solid #ea580c' : '1.5px solid #00d2ff',
                boxShadow: isLight ? '0 0 12px rgba(234, 88, 12, 0.25)' : '0 0 16px rgba(0, 210, 255, 0.35)'
              }}>
                <span style={{ fontSize: '1rem', fontWeight: 900, color: isLight ? '#9a3412' : '#00d2ff', letterSpacing: '0.5px' }}>
                  Σ v8.2.0
                </span>
                <span style={{
                  fontSize: '0.66rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: isLight ? '#ea580c' : '#00d2ff',
                  color: '#ffffff',
                  letterSpacing: '0.5px'
                }}>
                  RELEASE ATTIVA
                </span>
              </div>

              <div>
                <h2 style={{
                  fontSize: '1.25rem',
                  color: titleColor,
                  fontWeight: 800,
                  margin: '0 0 2px 0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span>⚡</span> Bacheca Rilasci: SigmaEngine Nativo, Providers & Suite Modulare
                </h2>
                <div style={{ fontSize: '0.78rem', color: subtitleColor, fontWeight: isLight ? 600 : 400 }}>
                  📅 18 Agosto 2026 • Inferenza C++/PyTorch Multi-GPU, 100% Interoperabilità Providers & 15 Skills
                </div>
              </div>
            </div>

            {/* Quick Actions GitHub & Hub */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <button
                onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
                style={{
                  padding: '7px 14px',
                  borderRadius: '9px',
                  background: isLight ? '#ea580c' : '#00d2ff',
                  border: 'none',
                  color: '#ffffff',
                  fontSize: '0.76rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: isLight ? '0 2px 10px rgba(234, 88, 12, 0.25)' : '0 2px 10px rgba(0, 210, 255, 0.3)'
                }}
              >
                <span>📦</span> Hub Skills
              </button>

              <a
                href="https://github.com/Sigmanih/Sigma_Studio"
                target="_blank"
                rel="noreferrer"
                style={{
                  padding: '7px 14px',
                  borderRadius: '9px',
                  background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.12)',
                  color: isLight ? '#000000' : '#ffffff',
                  fontSize: '0.76rem',
                  fontWeight: 800,
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <ExternalLink size={12} />
                GitHub Sync
              </a>
            </div>
          </div>

          {/* Griglia Compatta (3 Colonne Spotlight: SigmaEngine + Providers Esterni 100% Interoperabilità + 15 Skills) */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
            gap: '14px',
            marginBottom: '14px'
          }}>
            {/* Spotlight 1: SigmaEngine Nativo */}
            <div style={{
              padding: '14px 18px',
              borderRadius: '14px',
              background: innerCardBg,
              border: isLight ? '1px solid rgba(2, 132, 199, 0.35)' : '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '10px'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 800, color: isLight ? '#0284c7' : '#00d2ff', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    ⚡ MOTORE IN-MEMORY NATIVO
                  </span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: isLight ? '#15803d' : '#3fb950' }}>
                    ● LOCALE
                  </span>
                </div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: titleColor, marginBottom: '4px' }}>
                  SigmaEngine: Inferenza Ottimizzata Multi-GPU
                </div>
                <p style={{ fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.45, margin: '0 0 10px 0', fontWeight: isLight ? 500 : 400 }}>
                  Motore C++/PyTorch: partizionamento intelligente dei layer tra RTX 5070 Ti, RTX 5060 e RAM per modelli fino a 70B+ senza saturazione VRAM.
                </p>

                {/* Chips compatte */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🔀 Multi-Tier Sharding</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🚀 FlashAttention-2 & FP8</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🧠 Thinking Deterministico</span>
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)' }}>
                <button
                  onClick={() => openTab({ name: '⚡ Modelli Hub' }, 'model_hub')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: isLight ? '#0284c7' : '#00d2ff',
                    fontSize: '0.74rem',
                    fontWeight: 800,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: 0
                  }}
                >
                  Gestisci e scarica in Modelli Hub <ArrowRight size={12} />
                </button>
              </div>
            </div>

            {/* Spotlight 2: Providers Esterni & 100% Interoperabilità */}
            <div style={{
              padding: '14px 18px',
              borderRadius: '14px',
              background: innerCardBg,
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(234, 88, 12, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '10px'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 800, color: isLight ? '#c2410c' : '#f97316', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    🌐 PROVIDERS & AGENTI ESTERNI
                  </span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: isLight ? '#15803d' : '#3fb950' }}>
                    ● 100% INTEROPERABILE
                  </span>
                </div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: titleColor, marginBottom: '4px' }}>
                  Collega i tuoi Providers & Agenti Preferiti
                </div>
                <p style={{ fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.45, margin: '0 0 10px 0', fontWeight: isLight ? 500 : 400 }}>
                  Massima libertà: puoi scegliere i tuoi Providers preferiti (OpenAI, Claude, DeepSeek, Google Gemini, Groq, Ollama) al posto di SigmaEngine con pieno supporto a Manifesti e Server MCP.
                </p>

                {/* Chips compatte */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🌐 OpenAI • Claude • Gemini</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>⚡ DeepSeek R1 & Groq</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🔀 Routing & MCP Universale</span>
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)' }}>
                <button
                  onClick={() => openTab({ name: '⚙️ Configurazione Providers' }, 'ai_config')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: isLight ? '#c2410c' : '#f97316',
                    fontSize: '0.74rem',
                    fontWeight: 800,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: 0
                  }}
                >
                  Configura Providers & Routing <ArrowRight size={12} />
                </button>
              </div>
            </div>

            {/* Spotlight 3: Suite 15 Skills */}
            <div style={{
              padding: '14px 18px',
              borderRadius: '14px',
              background: innerCardBg,
              border: isLight ? '1px solid rgba(124, 91, 240, 0.35)' : '1px solid rgba(124, 91, 240, 0.3)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '10px'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 800, color: isLight ? '#6d28d9' : '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    🧩 SUITE 15 SKILLS MODULARI
                  </span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: isLight ? '#15803d' : '#3fb950' }}>
                    ● 100% OPEN SOURCE
                  </span>
                </div>
                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: titleColor, marginBottom: '4px' }}>
                  Laboratori Specialistici Collegabili a Caldo
                </div>
                <p style={{ fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.45, margin: '0 0 10px 0', fontWeight: isLight ? 500 : 400 }}>
                  Laboratori gratuiti da GitHub: Creative 3D con Blender headless, Voice Studio Kokoro (&lt;80ms), Developer Docker Sandbox e Domotica IoT.
                </p>

                {/* Chips compatte */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🎨 Creative 3D & SAM2</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🎙️ Voice Kokoro (&lt;80ms)</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)', border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.08)', color: titleColor }}>🐳 Developer Docker Sandbox</span>
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)' }}>
                <button
                  onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: isLight ? '#6d28d9' : '#a78bfa',
                    fontSize: '0.74rem',
                    fontWeight: 800,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: 0
                  }}
                >
                  Sfoglia e scarica le 15 skills dall'Hub <ArrowRight size={12} />
                </button>
              </div>
            </div>
          </div>

          {/* Striscia di Avviso Costruzione Attiva & Milestone Compatta */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
            padding: '10px 14px',
            borderRadius: '10px',
            background: isLight ? 'rgba(217, 119, 6, 0.08)' : 'rgba(250, 160, 60, 0.08)',
            border: isLight ? '1px solid rgba(217, 119, 6, 0.25)' : '1px solid rgba(250, 160, 60, 0.2)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.74rem', color: isLight ? '#9a3412' : '#faa03c', fontWeight: 600 }}>
              <span style={{ fontSize: '1rem' }}>🚧</span>
              <span><strong>Costruzione Attiva:</strong> Nuovi moduli e ottimizzazioni kernel vengono aggiunti regolarmente. Verifica costantemente gli aggiornamenti su GitHub.</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.7rem', color: subtitleColor }}>
              <span style={{ fontWeight: 800, color: isLight ? '#c2410c' : '#00d2ff' }}>v8.2.0 (Oggi)</span>
              <span>•</span>
              <span>v8.1.0 (Voice & Docker)</span>
              <span>•</span>
              <span>v8.0.0 (Swarm & 12 MCP)</span>
            </div>
          </div>
        </div>

        {/* ── VISUAL KERNEL COGNITIVO & DESCRIZIONE SIGMAENGINE INTERNO ──────── */}
        <div className="wg-showcase-card" style={{
          margin: '4px 0 16px 0',
          padding: '28px',
          borderRadius: '20px',
          background: cardBg,
          border: isLight ? '1px solid rgba(124, 91, 240, 0.35)' : '1px solid rgba(124, 91, 240, 0.3)',
          boxShadow: cardShadow,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '24px',
          alignItems: 'center'
        }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '4px 12px', borderRadius: '12px',
              background: 'rgba(124, 91, 240, 0.15)', color: isLight ? '#6d28d9' : '#7c5bf0',
              fontSize: '0.72rem', fontWeight: 800, marginBottom: '12px'
            }}>
              <span>🧠</span> ARCHITETTURA DI SISTEMA & SIGMAENGINE
            </div>
            <h2 style={{ margin: '0 0 12px 0', fontSize: '1.4rem', color: titleColor, fontWeight: 800 }}>
              Sigma Studio come Kernel Cognitivo Eseguibile
            </h2>
            <p style={{ fontSize: '0.86rem', color: subtitleColor, lineHeight: 1.65, margin: '0 0 16px 0', fontWeight: isLight ? 500 : 400 }}>
              Come un sistema operativo orchestra processi, memoria e periferiche hardware, Sigma Studio trasforma i Modelli Linguistici in unità di calcolo (CPU), coordinate dall'esclusivo motore nativo <strong>SigmaEngine</strong> o dai tuoi <strong>Providers Cloud preferiti</strong> (OpenAI, Claude, DeepSeek, Gemini, Groq, Ollama) per il 100% di integrabilità, regolamentate da <strong>Manifesti Hub</strong> vincolanti, collegate al bus I/O dei <strong>12 Server MCP</strong> ed estendibili con la suite di 15 Skills open source.
            </p>

            {/* Griglia 2x2 dei Componenti del Kernel & SigmaEngine */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#0284c7' : '#00d2ff' }}>⚡ SigmaEngine o Providers Cloud</div>
                <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Inferenza nativa C++/PyTorch locale o routing istantaneo verso OpenAI, Claude, DeepSeek, Gemini & Groq.</div>
              </div>
              <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#16a34a' : '#3fb950' }}>🔀 Modelli Hub & Forgia GGUF</div>
                <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Downloader Hugging Face e convertitore/quantizzatore GGUF integrato direttamente nel tab 2.</div>
              </div>
              <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#6d28d9' : '#7c5bf0' }}>📜 Manifesti Hub = Ruoli & Regole</div>
                <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Modelfile vincolanti per ogni professione e specializzazione scientifica.</div>
              </div>
              <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#d97706' : '#ffb86c' }}>🔌 12 Server MCP = Bus I/O Standard</div>
                <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Accesso sicuro a Filesystem, Domotica, Ricerca Web, Browser e Memoria.</div>
              </div>
            </div>
          </div>

          <div style={{
            position: 'relative',
            borderRadius: '16px',
            overflow: 'hidden',
            border: '1px solid rgba(124, 91, 240, 0.3)',
            boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
            minHeight: '280px',
            maxHeight: '320px'
          }}>
            <img
              src="/images/kernel_graphic.jpg"
              alt="Kernel Cognitivo Architecture"
              style={{ width: '100%', height: '320px', maxHeight: '320px', objectFit: 'cover', display: 'block' }}
              onError={(e) => { e.target.src = '/images/hero_banner.jpg'; }}
            />
            <div style={{
              position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
              padding: '12px 16px',
              background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
              fontSize: '0.75rem', color: '#ffffff', fontWeight: 600
            }}>
              🌐 Schema Architetturale del Kernel di Orchestrazione AI & SigmaEngine
            </div>
          </div>
        </div>

        {/* ── SLIDER INTERATTIVO: SKILLS & MODULI GITHUB OPEN SOURCE ──────────── */}
        <SkillsShowcaseSlider openTab={openTab} />

        {/* ── WORKFLOW OPERATIVO DEL KERNEL: DAL DOWNLOAD HUGGING FACE ALLA CHAT AI (STACKED CYBERPUNK) ── */}
        <div style={{
          margin: '20px 0 16px 0',
          padding: '28px',
          borderRadius: '24px',
          background: cardBg,
          border: cardBorder,
          boxShadow: cardShadow,
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ marginBottom: '22px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '4px 12px', borderRadius: '12px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
              color: isLight ? '#c2410c' : '#00d2ff',
              fontSize: '0.72rem', fontWeight: 800, marginBottom: '8px'
            }}>
              <Compass size={14} />
              <span>GUIDA OPERATIVA KERNEL • WORKFLOW SEQUENZIALE</span>
            </div>
            <h2 style={{ fontSize: '1.45rem', color: titleColor, fontWeight: 800, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🧬</span> Dal Download Hugging Face alla Chat AI su SigmaEngine
            </h2>
            <p style={{ fontSize: '0.86rem', color: subtitleColor, margin: 0, fontWeight: isLight ? 500 : 400, maxWidth: '840px' }}>
              La sequenza logica del sistema operativo: acquisisci qualsiasi modello open-source, forgia la quantizzazione GGUF ideale per la tua VRAM, infondi il ruolo operativo con i Manifesti ed avvia l'inferenza su SigmaEngine.
            </p>
          </div>

          {/* Stacked Cyberpunk Steps (1 sopra l'altro) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {KERNEL_WORKFLOW_STEPS.map((st) => {
              const StepIcon = st.icon;
              return (
                <div
                  key={st.step}
                  onClick={() => openTab({ name: st.tabName }, st.tabId)}
                  style={{
                    padding: '18px 22px',
                    borderRadius: '16px',
                    background: innerCardBg,
                    border: isLight ? `1.5px solid rgba(190, 160, 110, 0.35)` : `1.5px solid ${st.color}35`,
                    boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.08)' : `0 4px 20px ${st.color}10`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = st.color;
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.35)' : `${st.color}35`;
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '18px', flex: 1, minWidth: '280px' }}>
                    {/* Step Number & Icon Box */}
                    <div style={{
                      width: '52px',
                      height: '52px',
                      borderRadius: '14px',
                      background: `${st.color}18`,
                      border: `1.5px solid ${st.color}50`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      boxShadow: `0 0 16px ${st.color}25`
                    }}>
                      <StepIcon size={24} style={{ color: st.color }} />
                    </div>

                    {/* Step Content */}
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                        <span style={{
                          fontSize: '0.66rem',
                          fontWeight: 900,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: `${st.color}20`,
                          color: isLight ? '#000000' : st.color,
                          border: `1px solid ${st.color}40`,
                          letterSpacing: '0.5px'
                        }}>
                          PASSO {st.step}
                        </span>
                        <span style={{ fontSize: '0.68rem', fontWeight: 800, color: isLight ? '#7a7060' : '#8b8fa3', textTransform: 'uppercase' }}>
                          {st.phase}
                        </span>
                      </div>

                      <h3 style={{ margin: '0 0 4px 0', fontSize: '1.05rem', fontWeight: 800, color: titleColor }}>
                        {st.title}
                      </h3>
                      <p style={{ margin: '0 0 8px 0', fontSize: '0.8rem', color: subtitleColor, lineHeight: 1.45, fontWeight: isLight ? 500 : 400 }}>
                        {st.subtitle}
                      </p>

                      {/* Tech Tip Pill */}
                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '8px',
                        background: isLight ? '#ffffff' : 'rgba(255,255,255,0.03)',
                        border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)',
                        fontSize: '0.72rem',
                        color: innerCardText,
                        fontWeight: isLight ? 500 : 400
                      }}>
                        <span>💡</span>
                        <span>{st.tip}</span>
                      </div>
                    </div>
                  </div>

                  {/* Action CTA Button */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openTab({ name: st.tabName }, st.tabId);
                      }}
                      style={{
                        padding: '9px 18px',
                        borderRadius: '10px',
                        background: isLight ? '#ea580c' : st.color,
                        border: 'none',
                        color: '#ffffff',
                        fontSize: '0.78rem',
                        fontWeight: 800,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        boxShadow: isLight ? '0 2px 10px rgba(234, 88, 12, 0.25)' : `0 2px 12px ${st.color}35`,
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {st.actionText} <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── GUIDA MODULI: COME INSTALLARE & AGGIUNGERE SKILLS A PIACERE (HOT-RELOAD) ── */}
        <div style={{
          margin: '0 0 20px 0',
          padding: '26px 28px',
          borderRadius: '24px',
          background: cardBg,
          border: isLight ? '1px solid rgba(124, 91, 240, 0.35)' : '1px solid rgba(124, 91, 240, 0.3)',
          boxShadow: cardShadow,
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ marginBottom: '18px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '4px 12px', borderRadius: '12px',
              background: 'rgba(124, 91, 240, 0.15)', color: isLight ? '#6d28d9' : '#a78bfa',
              fontSize: '0.72rem', fontWeight: 800, marginBottom: '8px'
            }}>
              <span>🧩</span> ESTENDIBILITÀ DEL KERNEL & HOT-RELOAD
            </div>
            <h2 style={{ fontSize: '1.35rem', color: titleColor, fontWeight: 800, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📦</span> Come Installare ed Aggiungere Moduli e Skills a Piacere
            </h2>
            <p style={{ fontSize: '0.84rem', color: subtitleColor, margin: 0, fontWeight: isLight ? 500 : 400, maxWidth: '820px' }}>
              Sigma Studio supporta l'architettura a plugin dinamici: puoi scaricare i moduli ufficiali con un click da GitHub, creare le tue estensioni custom in locale o aggiungere nuovi Server MCP per connettere qualsiasi strumento esterno.
            </p>
          </div>

          {/* Griglia 3 Metodi di Installazione (Stack / Split) */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
            gap: '16px'
          }}>
            {MODULE_INSTALL_METHODS.map((m) => {
              const MethodIcon = m.icon;
              return (
                <div
                  key={m.method}
                  onClick={() => openTab({ name: m.tabName }, m.tabId)}
                  style={{
                    padding: '18px',
                    borderRadius: '16px',
                    background: innerCardBg,
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : `1px solid ${m.color}30`,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = m.color;
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.35)' : `${m.color}30`;
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <div style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        background: `${m.color}18`,
                        border: `1px solid ${m.color}45`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <MethodIcon size={20} style={{ color: m.color }} />
                      </div>

                      <span style={{
                        fontSize: '0.66rem',
                        fontWeight: 800,
                        padding: '3px 8px',
                        borderRadius: '6px',
                        background: `${m.color}15`,
                        color: isLight ? '#000000' : m.color,
                        border: `1px solid ${m.color}35`,
                        letterSpacing: '0.5px'
                      }}>
                        METODO {m.method}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.95rem', fontWeight: 800, color: titleColor, marginBottom: '6px' }}>
                      {m.title}
                    </div>
                    <p style={{ fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5, margin: 0, fontWeight: isLight ? 500 : 400 }}>
                      {m.desc}
                    </p>
                  </div>

                  <div style={{ paddingTop: '10px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <span style={{
                      fontSize: '0.76rem',
                      fontWeight: 800,
                      color: isLight ? '#c2410c' : m.color,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      {m.actionText} <ArrowRight size={13} />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── FOOTER ────────────────────────────────────────────────────────── */}
        <div style={{
          marginTop: '8px',
          padding: '24px 0 12px 0',
          borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: isLight ? '#000000' : '#6b7080',
          fontSize: '0.78rem',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#c2410c' : '#00d2ff',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: 0
              }}
            >
              🇮🇹 README_IT.md
            </button>
            <span>•</span>
            <button
              onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#15803d' : '#3fb950',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: 0
              }}
            >
              🇬🇧 README.md
            </button>
            <span>•</span>
            <button
              onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#7c3aed' : '#a78bfa',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: 0
              }}
            >
              🏛️ Specifica Architetturale
            </button>
          </div>

          <div style={{ color: isLight ? '#000000' : '#8b8fa3', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>⚡ Creato da <strong style={{ color: isLight ? '#000000' : '#ffffff' }}>Diego Saitta</strong> — 🧬 <strong style={{ color: isLight ? '#000000' : '#ffffff' }}>Sigma Studio v8.2</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
}