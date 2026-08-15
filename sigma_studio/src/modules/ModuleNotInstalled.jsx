// ==============================================================================
// sigma_studio/src/modules/ModuleNotInstalled.jsx
// Schermata fallback unificata per tab di moduli non installati.
// Sostituisce tutti i singoli blocchi "non installato" sparsi in Workspace.jsx.
// ==============================================================================
import React from 'react';
import { Package, ArrowRight } from 'lucide-react';

const MODULE_META = {
  creative_studio: { icon: '🎨', name: 'Creative Lab 3D/2D',            color: '#ff5064' },
  training_lab:    { icon: '🧠', name: 'Training Lab & SLM Forge',       color: '#a78bfa' },
  hardware_lab:    { icon: '⚡', name: 'Hardware Lab & VRAM',            color: '#fbbf24' },
  research_lab:    { icon: '🔬', name: 'Pipelines Lab & Dynamic Swarm',  color: '#34d399' },
  knowledge:       { icon: '🗺️', name: 'Knowledge Explorer',             color: '#60a5fa' },
  mcp_hub:         { icon: '🔧', name: 'MCP Tools Hub',                  color: '#f87171' },
  music:           { icon: '📻', name: 'Hi-Fi Sound & FM Radio Studio',  color: '#00f2fe' },
  audio_studio:    { icon: '📻', name: 'Hi-Fi Sound & FM Radio Studio',  color: '#00f2fe' },
  domotica:        { icon: '🏠', name: 'Domotica & Home Assistant IoT',  color: '#a78bfa' },
};

export default function ModuleNotInstalled({ tabType, openTab }) {
  const meta = MODULE_META[tabType] || { icon: '📦', name: tabType, color: '#8b8fa3' };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      gap: '20px',
      color: '#a0aec0',
      textAlign: 'center',
      padding: '48px 32px',
    }}>
      {/* Icon */}
      <div style={{
        width: '80px',
        height: '80px',
        borderRadius: '20px',
        background: `linear-gradient(135deg, ${meta.color}18, ${meta.color}08)`,
        border: `1.5px solid ${meta.color}30`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '2.2rem',
      }}>
        {meta.icon}
      </div>

      {/* Title */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.01em' }}>
          {meta.name}
        </h3>
        <p style={{ margin: 0, fontSize: '0.85rem', maxWidth: '380px', lineHeight: 1.6, color: '#6b7280' }}>
          Questo modulo non è installato. Aprilo dal <strong style={{ color: '#a0aec0' }}>Hub Moduli</strong> per scaricarlo e abilitarlo.
        </p>
      </div>

      {/* CTA */}
      <button
        onClick={() => openTab && openTab({ name: '📦 Hub Moduli & Estensioni' }, 'marketplace')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 22px',
          borderRadius: '12px',
          background: 'linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04))',
          border: '1px solid rgba(255,255,255,0.12)',
          color: '#e2e8f0',
          fontWeight: 700,
          fontSize: '0.85rem',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = 'linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06))';
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = 'linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04))';
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
        }}
      >
        <Package size={15} />
        Apri Hub Moduli
        <ArrowRight size={14} />
      </button>
    </div>
  );
}
