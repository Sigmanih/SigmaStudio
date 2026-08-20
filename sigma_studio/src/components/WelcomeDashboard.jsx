import React, { useEffect, useState } from 'react';
import { 
  MessageSquare, Scroll, ExternalLink,
  DownloadCloud, Layers, ArrowRight
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';
import TechSpaceCanvas from './common/TechSpaceCanvas';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

// ==============================================================================
// 4 PILASTRI ARCHITETTURALI DI SIGMA STUDIO — INTEGRATI NEL FLUSSO OPERATIVO
// ==============================================================================
const SYSTEM_PILLARS = [
  {
    id: 'chat',
    step: '1. Interfaccia & Esecuzione',
    title: 'Chat AI & Kernel Cognitivo',
    roleTag: 'Interfaccia & Flusso Operativo',
    description: 'Il centro di controllo conversazionale. Riceve le istruzioni, coordina il routing semantico e sfrutta i protocolli MCP per interrogare file e lanciare codice.',
    bullets: ['Streaming neurale real-time', 'Tool-calling MCP automatico', 'Routing locale / cloud'],
    icon: MessageSquare,
    color: '#00d2ff',
    tabId: 'chat',
    tabName: 'Chat AI',
    actionText: 'Avvia Chat AI'
  },
  {
    id: 'model_hub',
    step: '2. Runtime & Pesi Locali',
    title: 'Modelli Hub & SigmaEngine',
    roleTag: 'Infrastruttura di Inferenza',
    description: 'Il motore di inferenza sovrano. Esplora e scarica LLM open-source da Hugging Face, ottimizza i quantizzati GGUF per la tua VRAM e alloca i modelli con un click.',
    bullets: ['Supporto GGUF & Safetensors', 'Quantizzazione dinamica VRAM', 'Scaricamento & eliminazione sicura'],
    icon: DownloadCloud,
    color: '#faa03c',
    tabId: 'model_hub',
    tabName: '⚡ Modelli Hub',
    actionText: 'Gestisci Modelli'
  },
  {
    id: 'whitepapers_lib',
    step: '3. Allineamento & Ruoli',
    title: 'Manifesti & Personalità',
    roleTag: 'Governance & Specializzazione',
    description: 'Il layer di configurazione comportamentale. Guida il modello applicando regole deontologiche, stili di ragionamento e prompt di sistema per qualsiasi professione.',
    bullets: ['Ruoli professionali pronti', 'Hot-swap istantaneo senza riavvio', 'Manifesti personalizzabili'],
    icon: Scroll,
    color: '#bc8cff',
    tabId: 'whitepapers_lib',
    tabName: '📜 Manifesti Hub',
    actionText: 'Sfoglia Manifesti'
  },
  {
    id: 'marketplace',
    step: '4. Ecosistema Estendibile',
    title: 'Hub Skills & Gateway MCP',
    roleTag: 'Estensioni & Protocolli I/O',
    description: 'Il ponte operativo verso l\'esterno. Espandi il kernel con laboratori 3D, audio neurale, domotica Home Assistant e server MCP per automatizzare il sistema operativo.',
    bullets: ['Moduli modulari isolati', 'Server MCP multi-tool integrati', 'Installazione a 1-click da GitHub'],
    icon: Layers,
    color: '#3fb950',
    tabId: 'marketplace',
    tabName: '📦 Hub Skills & Estensioni',
    actionText: 'Esplora Hub Skills'
  }
];

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#94a3b8';
  const cardBg = isLight ? '#ffffff' : '#111522';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(190, 160, 110, 0.12)' : '0 10px 30px rgba(0, 0, 0, 0.4)';

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

    // 2. Recupera modelli locali effettivamente scaricati
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
        setActiveMcpCount(6);
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

    // 5. Moduli installati dal marketplace
    try {
      const stored = localStorage.getItem('sigma_market_installed');
      if (stored) setDynamicInstalledModules(JSON.parse(stored));
    } catch (e) {}
  }, []);

  const activeSkillsCount = Object.keys(modulesState || {}).filter(k => k !== 'sigma_model_hub' && modulesState[k] === true).length + dynamicInstalledModules.length;

  return (
    <div className="wg-container" style={{ position: 'relative' }}>
      {/* Canvas Sfondo Spaziale Animato */}
      <TechSpaceCanvas isLight={isLight} />

      {/* Hero Banner Moderno */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        padding: '24px 32px',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.25)' : '1px solid rgba(0, 210, 255, 0.2)',
        backgroundImage: isLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.88) 0%, rgba(248, 242, 232, 0.8) 100%), url("/images/hero_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.9) 0%, rgba(14, 22, 42, 0.85) 100%), url("/images/hero_banner.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center center',
        flexShrink: 0
      }}>
        <div style={{
          position: 'relative',
          zIndex: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '18px'
        }}>
          {/* Logo & Headline */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '18px', maxWidth: '720px' }}>
            <div style={{
              width: '54px',
              height: '54px',
              borderRadius: '16px',
              overflow: 'hidden',
              border: isLight ? '2px solid #ea580c' : '2px solid #00d2ff',
              boxShadow: isLight ? '0 0 16px rgba(234, 88, 12, 0.3)' : '0 0 20px rgba(0, 210, 255, 0.4)',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                  color: isLight ? '#c2410c' : '#00d2ff',
                  border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.35)'
                }}>
                  Σ v8.2 KERNEL
                </span>
              </div>
              <h1 style={{
                fontSize: '1.45rem',
                fontWeight: 800,
                color: titleColor,
                margin: '0 0 4px 0',
                letterSpacing: '-0.3px'
              }}>
                Sigma AI Studio
              </h1>
              <p style={{
                fontSize: '0.82rem',
                color: subtitleColor,
                lineHeight: 1.4,
                margin: 0
              }}>
                L'ambiente operativo per l'Intelligenza Artificiale locale, autonoma e modulare.
              </p>
            </div>
          </div>

          {/* Azioni Rapide */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              onClick={() => openTab({ name: 'AI Chat Workspace' }, 'chat')}
              style={{
                padding: '9px 18px',
                borderRadius: '10px',
                background: isLight ? '#ea580c' : '#00d2ff',
                border: 'none',
                color: '#ffffff',
                fontWeight: 700,
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

            <button
              onClick={() => openTab({ name: '⚡ Modelli Hub' }, 'model_hub')}
              style={{
                padding: '9px 15px',
                borderRadius: '10px',
                background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                color: isLight ? '#111827' : '#ffffff',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              ⚡ Modelli Hub
            </button>

            <button
              onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
              style={{
                padding: '9px 15px',
                borderRadius: '10px',
                background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                color: isLight ? '#111827' : '#ffffff',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              📦 Hub Skills
            </button>

            <a
              href="https://github.com/Sigmanih/SigmaStudio"
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '9px 14px',
                borderRadius: '10px',
                background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                color: isLight ? '#4b5563' : '#cbd5e1',
                fontWeight: 600,
                fontSize: '0.82rem',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <ExternalLink size={14} />
              GitHub
            </a>
          </div>
        </div>
      </div>

      {/* Corpo Principale */}
      <div style={{ padding: '16px 20px 24px 20px', display: 'flex', flexDirection: 'column', gap: '18px', flex: 1 }}>
        
        {/* ── 5 METRICHE TELEMETRICHE CHIAVE ──────── */}
        <div className="wg-metrics" style={{ margin: 0 }}>
          {/* Card 1: Modelli Locali */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '⚡ Modelli Hub' }, 'model_hub')}
            style={{ borderTop: '3px solid #00d2ff', background: cardBg, cursor: 'pointer' }}
            title="Clicca per aprire Modelli Hub"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🤖</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#0284c7' : '#00d2ff' }}>{localModelsCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: subtitleColor }}>Modelli Scaricati</span>
          </div>

          {/* Card 2: Manifesti */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '📜 Manifesti Hub' }, 'whitepapers_lib')}
            style={{ borderTop: '3px solid #bc8cff', background: cardBg, cursor: 'pointer' }}
            title="Clicca per esplorare i Manifesti"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>📜</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#9333ea' : '#bc8cff' }}>{manifestiCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: subtitleColor }}>Ruoli & Manifesti</span>
          </div>

          {/* Card 3: Skills */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
            style={{ borderTop: '3px solid #3fb950', background: cardBg, cursor: 'pointer' }}
            title="Clicca per visualizzare l'Hub Skills"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🧩</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#16a34a' : '#3fb950' }}>{activeSkillsCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: subtitleColor }}>Skills Attive</span>
          </div>

          {/* Card 4: Server MCP */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')}
            style={{ borderTop: '3px solid #ff5064', background: cardBg, cursor: 'pointer' }}
            title="Clicca per accedere al gateway MCP"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔌</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#dc2626' : '#ff5064' }}>{activeMcpCount}</span>
            </div>
            <span className="wg-metric-label" style={{ color: subtitleColor }}>Server MCP</span>
          </div>

          {/* Card 5: Provider AI */}
          <div 
            className="wg-metric" 
            onClick={() => openTab({ name: '⚙️ Providers Hub' }, 'ai_config')}
            style={{ borderTop: '3px solid #faa03c', background: cardBg, cursor: 'pointer' }}
            title="Clicca per configurare i Provider AI"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.2rem' }}>⚡</span>
              <span className="wg-metric-value" style={{ color: isLight ? '#d97706' : '#faa03c', fontSize: activeProviderName.length > 10 ? '1rem' : '1.2rem' }}>{activeProviderName}</span>
            </div>
            <span className="wg-metric-label" style={{ color: subtitleColor }}>Provider Attivo</span>
          </div>
        </div>

        {/* ── SEZIONE GRAFICA: COS'È SIGMA STUDIO & FLUSSO ARCHITETTURALE ──────── */}
        <div style={{
          padding: '22px 24px',
          borderRadius: '16px',
          background: isLight 
            ? 'linear-gradient(135deg, rgba(255,255,255,0.95), rgba(248, 245, 238, 0.95))' 
            : 'linear-gradient(135deg, rgba(17, 21, 34, 0.95), rgba(13, 16, 26, 0.95))',
          border: cardBorder,
          boxShadow: cardShadow,
          display: 'flex',
          flexDirection: 'column',
          gap: '18px'
        }}>
          {/* Header Introduttivo */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
            <div style={{ maxWidth: '850px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <span style={{
                  fontSize: '0.66rem',
                  fontWeight: 800,
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: 'rgba(0, 210, 255, 0.12)',
                  color: '#00d2ff',
                  border: '1px solid rgba(0, 210, 255, 0.25)'
                }}>
                  Cos'è Sigma Studio
                </span>
                <span style={{ fontSize: '0.74rem', color: subtitleColor, fontWeight: 600 }}>
                  • Architettura Unificata a 4 Livelli
                </span>
              </div>
              <h2 style={{
                margin: '0 0 8px 0',
                fontSize: '1.2rem',
                fontWeight: 800,
                color: titleColor,
                letterSpacing: '-0.2px'
              }}>
                Il Sistema Operativo AI per l'Autonomia Sovrana
              </h2>
              <p style={{
                margin: 0,
                fontSize: '0.82rem',
                color: subtitleColor,
                lineHeight: 1.55
              }}>
                <strong>Sigma AI Studio</strong> trasforma qualsiasi macchina (da PC Windows/Mac/Linux a dispositivi ARM come Raspberry Pi) in una stazione di intelligenza artificiale locale e modulare. Il sistema integra in una pipeline fluida l'<strong>inferenza neurale</strong> dei modelli, la <strong>governance comportamentale</strong> dei manifesti, l'<strong>interfaccia di chat</strong> e l'<strong>esecuzione attiva</strong> tramite protocolli di strumenti MCP.
              </p>
            </div>

            {/* Pipeline Visual Diagram Indicator */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '12px',
              background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid rgba(190,160,110,0.25)' : '1px solid rgba(255,255,255,0.06)',
              fontSize: '0.72rem',
              fontWeight: 700,
              color: titleColor,
              flexShrink: 0
            }}>
              <span>⚡ Pesi</span>
              <span style={{ color: subtitleColor }}>➔</span>
              <span>📜 Ruolo</span>
              <span style={{ color: subtitleColor }}>➔</span>
              <span style={{ color: '#00d2ff' }}>🧠 Kernel</span>
              <span style={{ color: subtitleColor }}>➔</span>
              <span style={{ color: '#3fb950' }}>🔌 Tool MCP</span>
            </div>
          </div>

          {/* ── LE 4 AREE CHIAVE INTEGRATE NEL CONTESTO ──────── */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '14px'
          }}>
            {SYSTEM_PILLARS.map((pillar) => {
              const PillarIcon = pillar.icon;
              return (
                <div
                  key={pillar.id}
                  onClick={() => openTab({ name: pillar.tabName }, pillar.tabId)}
                  style={{
                    padding: '16px 18px',
                    borderRadius: '14px',
                    background: isLight ? '#ffffff' : '#0e121e',
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.28)' : '1px solid rgba(255, 255, 255, 0.06)',
                    boxShadow: isLight ? '0 2px 10px rgba(190, 160, 110, 0.08)' : '0 4px 16px rgba(0, 0, 0, 0.25)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '12px',
                    cursor: 'pointer',
                    transition: 'all 0.22s ease',
                    position: 'relative'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = pillar.color;
                    e.currentTarget.style.transform = 'translateY(-2px)';
                    e.currentTarget.style.boxShadow = `0 8px 24px ${pillar.color}22`;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.28)' : 'rgba(255, 255, 255, 0.06)';
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = isLight ? '0 2px 10px rgba(190, 160, 110, 0.08)' : '0 4px 16px rgba(0, 0, 0, 0.25)';
                  }}
                >
                  <div>
                    {/* Header Card: Step & Ruolo */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <span style={{
                        fontSize: '0.65rem',
                        fontWeight: 800,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        color: pillar.color,
                      }}>
                        {pillar.step}
                      </span>
                      <span style={{
                        fontSize: '0.62rem',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: `${pillar.color}15`,
                        color: pillar.color,
                        fontWeight: 700
                      }}>
                        {pillar.roleTag}
                      </span>
                    </div>

                    {/* Titolo e Icona */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                      <div style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '10px',
                        background: `${pillar.color}18`,
                        border: `1px solid ${pillar.color}40`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0
                      }}>
                        <PillarIcon size={18} style={{ color: pillar.color }} />
                      </div>
                      <h3 style={{
                        margin: 0,
                        fontSize: '0.95rem',
                        fontWeight: 800,
                        color: titleColor
                      }}>
                        {pillar.title}
                      </h3>
                    </div>

                    {/* Descrizione Integrata */}
                    <p style={{
                      margin: '0 0 10px 0',
                      fontSize: '0.76rem',
                      color: subtitleColor,
                      lineHeight: 1.45
                    }}>
                      {pillar.description}
                    </p>

                    {/* Feature Bullets */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {pillar.bullets.map((b, bIdx) => (
                        <div key={bIdx} style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '0.7rem',
                          color: isLight ? '#374151' : '#cbd5e1',
                          fontWeight: 500
                        }}>
                          <span style={{ color: pillar.color, fontSize: '0.75rem', lineHeight: 1 }}>•</span>
                          <span>{b}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Bottone Azione */}
                  <div style={{
                    paddingTop: '8px',
                    borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <span style={{
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      color: pillar.color,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      {pillar.actionText} <ArrowRight size={13} />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── CATALOGO SKILLS SHOWCASE SLIDER ──────── */}
        <SkillsShowcaseSlider openTab={openTab} />

        {/* ── FOOTER ESSENZIALE & PULITO ──────── */}
        <div style={{
          marginTop: 'auto',
          padding: '16px 0 6px 0',
          borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: subtitleColor,
          fontSize: '0.76rem',
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
                fontSize: '0.76rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: 0
              }}
            >
              🇮🇹 Documentazione IT
            </button>
            <span>•</span>
            <button
              onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#7c3aed' : '#a78bfa',
                cursor: 'pointer',
                fontSize: '0.76rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: 0
              }}
            >
              🏛️ Architettura
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: '#3fb950' }}>●</span>
            <span>Sigma Studio v8.2 • Pronto e operativo</span>
          </div>
        </div>

      </div>
    </div>
  );
}