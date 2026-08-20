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
// 4 AREE CHIAVE DI SIGMA STUDIO — MODERNE, CONCISE ED EFFICACI
// ==============================================================================
const CORE_PILLARS = [
  {
    id: 'chat',
    title: 'Chat AI & Agenti',
    subtitle: 'Dialoga in streaming con modelli locali o provider cloud con supporto MCP e routing semantico.',
    icon: MessageSquare,
    color: '#00d2ff',
    tabId: 'chat',
    tabName: 'Chat AI',
    actionText: 'Apri Chat'
  },
  {
    id: 'model_hub',
    title: 'Modelli Hub & GGUF',
    subtitle: 'Cerca e scarica LLM da Hugging Face, quantizza pesi per la tua VRAM e gestisci i modelli locali.',
    icon: DownloadCloud,
    color: '#faa03c',
    tabId: 'model_hub',
    tabName: '⚡ Modelli Hub',
    actionText: 'Gestisci Modelli'
  },
  {
    id: 'whitepapers_lib',
    title: 'Manifesti & Ruoli',
    subtitle: 'Attiva personalità disciplinari, regole etiche e prompt di sistema specializzati per ogni professione.',
    icon: Scroll,
    color: '#bc8cff',
    tabId: 'whitepapers_lib',
    tabName: '📜 Manifesti Hub',
    actionText: 'Sfoglia Manifesti'
  },
  {
    id: 'marketplace',
    title: 'Hub Skills & Estensioni',
    subtitle: 'Espandi Sigma con laboratori 3D, sintesi vocale neurale, domotica IoT e sandbox di sviluppo.',
    icon: Layers,
    color: '#3fb950',
    tabId: 'marketplace',
    tabName: '📦 Hub Skills & Estensioni',
    actionText: 'Apri Hub Skills'
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

      {/* Hero Banner Moderno & Pulito */}
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
                Ambiente integrato per l'AI locale, modelli quantizzati, manifesti disciplinari e strumenti MCP.
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

        {/* ── LE 4 AREE CHIAVE (GRIGLIA MODERNA E PULITA) ──────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '14px'
        }}>
          {CORE_PILLARS.map((pillar) => {
            const PillarIcon = pillar.icon;
            return (
              <div
                key={pillar.id}
                onClick={() => openTab({ name: pillar.tabName }, pillar.tabId)}
                style={{
                  padding: '18px 20px',
                  borderRadius: '16px',
                  background: cardBg,
                  border: cardBorder,
                  boxShadow: cardShadow,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '12px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  position: 'relative'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = pillar.color;
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.35)' : 'rgba(255, 255, 255, 0.08)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                    <div style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '10px',
                      background: `${pillar.color}15`,
                      border: `1px solid ${pillar.color}35`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}>
                      <PillarIcon size={20} style={{ color: pillar.color }} />
                    </div>
                    <h2 style={{
                      margin: 0,
                      fontSize: '1rem',
                      fontWeight: 700,
                      color: titleColor
                    }}>
                      {pillar.title}
                    </h2>
                  </div>

                  <p style={{
                    margin: 0,
                    fontSize: '0.78rem',
                    color: subtitleColor,
                    lineHeight: 1.45
                  }}>
                    {pillar.subtitle}
                  </p>
                </div>

                <div style={{
                  paddingTop: '8px',
                  borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255,255,255,0.06)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <span style={{
                    fontSize: '0.76rem',
                    fontWeight: 700,
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