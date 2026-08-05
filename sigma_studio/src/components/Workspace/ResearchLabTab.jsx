import React, { useState } from 'react';
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
  const [mode, setMode] = useState('default');

  const handleClose = () => {};

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '20px 24px', boxSizing: 'border-box', background: '#090a0f', color: '#e2e4eb' }}>
      
      {/* 1. TOP HEADER — POSIZIONATO IN ALTO SOPRA I BUTTONS */}
      <div className="app-page-header" style={{ marginBottom: '16px', flexShrink: 0 }}>
        <div className="app-page-header-title">
          <div className="app-page-header-icon" style={{ width: '42px', height: '42px' }}>
            <FlaskConical size={22} color="#00f2fe" />
          </div>
          <div>
            <h1 style={{ fontSize: '20px' }}>Pipelines Lab</h1>
            <div className="app-page-header-subtitle">
              <span>Orchestrazione Pipeline Multi-Agente & Editor Visuale DAG</span>
              <span>•</span>
              <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                Swarm Multidisciplinare & Workflow Automation
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. MODE SWITCHER BUTTONS BAR — POSIZIONATA SOTTO L'HEADER */}
      <div 
        style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: '12px', 
          marginBottom: '16px', 
          padding: '8px',
          background: 'rgba(17, 19, 27, 0.8)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '14px',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
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
                gap: '12px',
                padding: '12px 18px',
                borderRadius: '10px',
                cursor: 'pointer',
                fontFamily: 'Inter, system-ui, sans-serif',
                transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                background: isActive 
                  ? (m.id === 'default' 
                      ? 'linear-gradient(135deg, rgba(0, 210, 255, 0.16), rgba(0, 114, 255, 0.1))' 
                      : 'linear-gradient(135deg, rgba(188, 140, 255, 0.16), rgba(124, 91, 240, 0.1))')
                  : 'transparent',
                border: isActive 
                  ? (m.id === 'default' ? '1px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(188, 140, 255, 0.4)')
                  : '1px solid transparent',
                color: isActive 
                  ? (m.id === 'default' ? '#00d2ff' : '#bc8cff')
                  : '#8b8fa3',
                boxShadow: isActive 
                  ? (m.id === 'default' ? '0 4px 20px rgba(0, 210, 255, 0.15)' : '0 4px 20px rgba(188, 140, 255, 0.15)')
                  : 'none'
              }}
            >
              <div 
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isActive 
                    ? (m.id === 'default' ? 'rgba(0, 210, 255, 0.2)' : 'rgba(188, 140, 255, 0.2)')
                    : 'rgba(255, 255, 255, 0.04)',
                  color: isActive ? '#fff' : '#8b8fa3',
                  boxShadow: isActive ? (m.id === 'default' ? '0 0 10px rgba(0,210,255,0.3)' : '0 0 10px rgba(188,140,255,0.3)') : 'none',
                  flexShrink: 0
                }}
              >
                <Icon size={18} />
              </div>
              <div style={{ textAlign: 'left', minWidth: 0 }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: isActive ? '#fff' : '#e2e4eb', marginBottom: '2px' }}>
                  {m.label}
                </div>
                <div style={{ fontSize: '0.7rem', color: isActive ? 'rgba(226, 228, 235, 0.8)' : '#5a5e72', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {m.desc}
                </div>
              </div>
            </button>
          );
        })}
      </div>

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
  );
}
