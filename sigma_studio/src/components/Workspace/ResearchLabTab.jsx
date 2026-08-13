import React, { useState } from 'react';
import { useApp } from '../../contexts/AppContext';
import TechSpaceCanvas from '../common/TechSpaceCanvas';
import ResearchLab from '../Chat/ResearchLab';
import PipelineDesigner from '../Chat/PipelineDesigner';
import { FlaskConical, GitCompare } from 'lucide-react';

// ==============================================================================
// PIPELINES LAB TAB — Due modalità:
// 1. "Pipeline Predefinita" (ResearchLab) — Template pronti con feedback loop
// 2. "Pipeline Designer" — Editor visuale DAG per configurazioni custom
// ==============================================================================

const MODES = [
  { 
    id: 'default', 
    label: '🚀 Pipeline Predefinita', 
    icon: FlaskConical, 
    desc: 'Template pronti con 4-7 agenti, feedback loop automatico e memoria distribuita' 
  },
  { 
    id: 'designer', 
    label: '🧩 Pipeline Designer', 
    icon: GitCompare, 
    desc: 'Editor visuale DAG per creare pipeline custom con routing condizionale' 
  },
];

export default function ResearchLabTab({ onTasksUpdated, addToast }) {
  const { theme } = useApp();
  const [mode, setMode] = useState('default');

  const handleClose = () => {};

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 0, boxSizing: 'border-box', background: 'var(--bg)', color: '#e2e4eb', overflowY: 'auto', position: 'relative' }}>
      
      {/* Animated Translucent Cyber Space Background Canvas */}
      <TechSpaceCanvas isLight={theme === 'light'} />

      {/* Hero Visual Banner with Standardized Theme System & Dimensions */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: theme === 'light' ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: theme === 'light'
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/pipelines_lab_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/pipelines_lab_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: 0,
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: theme === 'light' ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <FlaskConical size={14} /> MULTI-AGENT PIPELINES & DAG ORCHESTRATION
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: theme === 'light' ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              🔬 Pipelines Lab & <span style={{
                color: theme === 'light' ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Workflow Automation</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: theme === 'light' ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Orchestrazione avanzata di swarm multidisciplinari, routing condizionale e grafi aciclici diretti (DAG) per automazioni complesse.
            </p>
          </div>

          {/* Action Buttons on the Right */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setMode('default')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: mode === 'default' 
                  ? (theme === 'light' ? '#ea580c' : '#00d2ff') 
                  : (theme === 'light' ? '#fffdf9' : '#181b28'),
                color: mode === 'default' ? (theme === 'light' ? '#fff' : '#0a0d14') : (theme === 'light' ? '#111' : '#fff'),
                border: mode === 'default' ? 'none' : (theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)'),
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              <FlaskConical size={14} /> Pipeline Predefinita
            </button>
            <button
              onClick={() => setMode('designer')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: mode === 'designer' 
                  ? (theme === 'light' ? '#ea580c' : '#00d2ff') 
                  : (theme === 'light' ? '#fffdf9' : '#181b28'),
                color: mode === 'designer' ? (theme === 'light' ? '#fff' : '#0a0d14') : (theme === 'light' ? '#111' : '#fff'),
                border: mode === 'designer' ? 'none' : (theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)'),
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              <GitCompare size={14} /> Pipeline Designer
            </button>
          </div>
        </div>
      </div>

      {/* 2. MODE SWITCHER BUTTONS BAR — SENZA MARGINI SOPRA E SOTTO */}
      <div 
        className="plab-mode-switcher"
        style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: '8px', 
          margin: 0, 
          padding: '6px 24px',
          background: 'var(--surface-bright)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 0,
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
          flexShrink: 0
        }}
      >
        {MODES.map(m => {
          const isActive = mode === m.id;
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '6px 14px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontFamily: 'Inter, system-ui, sans-serif',
                transition: 'all 0.2s ease',
                background: isActive 
                  ? (m.id === 'default' 
                      ? 'linear-gradient(135deg, rgba(0, 210, 255, 0.16), rgba(0, 114, 255, 0.1))' 
                      : 'linear-gradient(135deg, rgba(188, 140, 255, 0.16), rgba(124, 91, 240, 0.1))')
                  : 'transparent',
                border: isActive 
                  ? (m.id === 'default' ? '1px solid rgba(0, 210, 255, 0.35)' : '1px solid rgba(188, 140, 255, 0.35)')
                  : '1px solid transparent',
                color: isActive 
                  ? (m.id === 'default' ? '#00d2ff' : '#bc8cff')
                  : '#8b8fa3',
                boxShadow: isActive 
                  ? (m.id === 'default' ? '0 2px 12px rgba(0, 210, 255, 0.12)' : '0 2px 12px rgba(188, 140, 255, 0.12)')
                  : 'none'
              }}
            >
              <div 
                style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isActive 
                    ? (m.id === 'default' ? 'rgba(0, 210, 255, 0.2)' : 'rgba(188, 140, 255, 0.2)')
                    : 'rgba(255, 255, 255, 0.04)',
                  color: isActive ? '#fff' : '#8b8fa3',
                  flexShrink: 0
                }}
              >
                <Icon size={14} />
              </div>
              <div style={{ textAlign: 'left', minWidth: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: isActive ? '#fff' : '#e2e4eb' }}>
                  {m.label}
                </span>
                <span style={{ fontSize: '0.68rem', color: isActive ? 'rgba(226, 228, 235, 0.7)' : '#5a5e72', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  • {m.desc}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Main Content Workspace Body */}
      <div style={{ padding: '24px', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px', minHeight: 0 }}>

      {/* 3. MAIN CONTENT */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {mode === 'default' && (
          <ResearchLab onClose={handleClose} onTasksUpdated={onTasksUpdated} addToast={addToast} />
        )}
        {mode === 'designer' && (
          <PipelineDesigner onClose={handleClose} onTasksUpdated={onTasksUpdated} addToast={addToast} />
        )}
      </div>
      </div>
    </div>
  );
}
