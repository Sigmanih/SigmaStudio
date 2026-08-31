import React from 'react';
import { 
  MessageSquare, Scroll, ExternalLink,
  DownloadCloud, Layers, Cpu, ShieldCheck, Terminal, 
  ArrowRight, Sparkles, Zap, Wrench, Globe, CheckCircle2
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import TechSpaceCanvas from './common/TechSpaceCanvas';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#94a3b8';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(190, 160, 110, 0.12)' : '0 10px 30px rgba(0, 0, 0, 0.4)';

  return (
    <div className="wg-container" style={{ position: 'relative' }}>
      {/* Canvas Sfondo Spaziale Animato */}
      <TechSpaceCanvas isLight={isLight} />

      {/* Hero Header Moderno */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '18px', maxWidth: '750px' }}>
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
                  Σ v0.8.2 KERNEL
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

          {/* Azioni Rapide nell'Header */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              onClick={() => openTab({ name: 'Chat' }, 'chat')}
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
              💬 Chat
            </button>

            <button
              onClick={() => openTab({ name: 'Modelli' }, 'model_hub')}
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
              ⚡ Modelli
            </button>

            <button
              onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
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
      <div style={{ padding: '20px 24px 28px 24px', display: 'flex', flexDirection: 'column', gap: '22px', flex: 1 }}>
        
        {/* ── DIV DI BENVENUTO E SPIEGAZIONE APPROFONDITA DI SIGMA STUDIO ──────── */}
        <div style={{
          padding: '28px 32px',
          borderRadius: '20px',
          background: isLight 
            ? 'linear-gradient(135deg, #ffffff 0%, #faf8f5 100%)' 
            : 'linear-gradient(135deg, rgba(17, 21, 34, 0.96) 0%, rgba(11, 14, 23, 0.98) 100%)',
          border: cardBorder,
          boxShadow: cardShadow,
          display: 'flex',
          flexDirection: 'column',
          gap: '24px'
        }}>
          {/* Header del Benvenuto */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{
                fontSize: '0.68rem',
                fontWeight: 800,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                padding: '3px 10px',
                borderRadius: '6px',
                background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.14)',
                color: isLight ? '#c2410c' : '#00d2ff',
                border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)'
              }}>
                ⚡ Piattaforma AI Locale & Modulare
              </span>
              <span style={{ fontSize: '0.76rem', color: subtitleColor, fontWeight: 600 }}>
                • Autonomia Sovrana & Zero Costi API
              </span>
            </div>

            <h2 style={{
              margin: '0 0 10px 0',
              fontSize: '1.4rem',
              fontWeight: 800,
              color: titleColor,
              letterSpacing: '-0.3px'
            }}>
              Benvenuto in Sigma AI Studio
            </h2>

            <p style={{
              margin: 0,
              fontSize: '0.88rem',
              color: subtitleColor,
              lineHeight: 1.65,
              maxWidth: '1000px'
            }}>
              Grazie al motore <strong>SigmaEngine</strong> integrato con Sigma Studio, puoi fare il download dei modelli open-source, quantizzarli e <strong>ottimizzarli su misura per il tuo hardware</strong> — da workstation con GPU dedicate a dispositivi a basso consumo come il Raspberry Pi 5. Tutto viene eseguito in locale, garantendo <strong>privacy assoluta</strong>, <strong>zero latenza di rete</strong> e totale indipendenza dal cloud.
            </p>
          </div>

          {/* I 4 Pilastri del Sistema Sintetizzati ed Enfatici */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px'
          }}>
            {/* Pilastro 1: SigmaEngine & Download Modelli */}
            <div style={{
              padding: '18px 20px',
              borderRadius: '14px',
              background: isLight ? 'rgba(0, 210, 255, 0.04)' : 'rgba(0, 210, 255, 0.03)',
              border: isLight ? '1px solid rgba(0, 210, 255, 0.25)' : '1px solid rgba(0, 210, 255, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Cpu size={18} color="#00d2ff" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  1. SigmaEngine & Download Modelli
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Scarica qualsiasi modello open-source (GGUF, Safetensors) da Hugging Face ed eseguilo in locale con <strong>gestione automatica della VRAM/RAM</strong> per massime prestazioni sul tuo hardware.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#00d2ff', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Modelli' }, 'model_hub')}
              >
                <span>Gestisci modelli in Modelli</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 2: Manifesti & Ruoli Specialistici */}
            <div style={{
              padding: '18px 20px',
              borderRadius: '14px',
              background: isLight ? 'rgba(188, 140, 255, 0.04)' : 'rgba(188, 140, 255, 0.03)',
              border: isLight ? '1px solid rgba(188, 140, 255, 0.25)' : '1px solid rgba(188, 140, 255, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(188, 140, 255, 0.15)', border: '1px solid rgba(188, 140, 255, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Scroll size={18} color="#bc8cff" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  2. Ruoli AI & Professioni Specialistiche
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Trasforma all'istante l'assistente in un esperto di codice, ingegneria, medicina o ricerca: i manifesti e ruoli applicano <strong>regole etiche e direttive disciplinari</strong> senza dover riaddestrare il modello.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#bc8cff', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Ruoli AI' }, 'whitepapers_lib')}
              >
                <span>Esplora Ruoli AI e Professioni</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 3: Protocollo MCP & Automazione */}
            <div style={{
              padding: '18px 20px',
              borderRadius: '14px',
              background: isLight ? 'rgba(255, 80, 100, 0.04)' : 'rgba(255, 80, 100, 0.03)',
              border: isLight ? '1px solid rgba(255, 80, 100, 0.25)' : '1px solid rgba(255, 80, 100, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(255, 80, 100, 0.15)', border: '1px solid rgba(255, 80, 100, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Terminal size={18} color="#ff5064" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  3. Protocollo MCP & Azione sul Sistema
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Dai all'AI strumenti pratici tramite <strong>Model Context Protocol</strong>: esecuzione di script, gestione file, diagnostica hardware in tempo reale e controllo domotico IoT.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#ff5064', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')}
              >
                <span>Accedi al Gateway MCP</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 4: Hub Skills & Estensioni da GitHub */}
            <div style={{
              padding: '18px 20px',
              borderRadius: '14px',
              background: isLight ? 'rgba(63, 185, 80, 0.04)' : 'rgba(63, 185, 80, 0.03)',
              border: isLight ? '1px solid rgba(63, 185, 80, 0.25)' : '1px solid rgba(63, 185, 80, 0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Layers size={18} color="#3fb950" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  4. Skills ed Estensioni Modulari
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Scarica e attiva con un click nuovi moduli ed estensioni (Creative Lab 3D, Audio Studio, Training Lab, Hardware Monitor) mantenendo il <strong>kernel sempre pulito e leggero</strong>.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#3fb950', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
              >
                <span>Apri Skills & Moduli</span> <ArrowRight size={12} />
              </div>
            </div>
          </div>

          {/* Quick Guide: Come iniziare */}
          <div style={{
            padding: '16px 20px',
            borderRadius: '12px',
            background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Sparkles size={20} color={isLight ? '#c2410c' : '#00d2ff'} />
              <div>
                <div style={{ fontSize: '0.84rem', fontWeight: 700, color: titleColor }}>
                  Pronto per iniziare?
                </div>
                <div style={{ fontSize: '0.75rem', color: subtitleColor }}>
                  Apri la Chat per dialogare con l'assistente oppure visita la scheda Modelli per scaricare il tuo primo LLM locale.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={() => openTab({ name: 'Chat' }, 'chat')}
                style={{
                  padding: '7px 14px', borderRadius: '8px',
                  background: isLight ? '#ea580c' : '#00d2ff',
                  border: 'none', color: '#ffffff',
                  fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                💬 Chat
              </button>
              <button
                onClick={() => openTab({ name: 'Modelli' }, 'model_hub')}
                style={{
                  padding: '7px 14px', borderRadius: '8px',
                  background: isLight ? '#ffffff' : 'rgba(255,255,255,0.08)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.15)',
                  color: isLight ? '#111827' : '#ffffff',
                  fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                ⚡ Modelli
              </button>
            </div>
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
            <span>Sigma Studio v0.8.2 • Pronto e operativo</span>
          </div>
        </div>

      </div>
    </div>
  );
}