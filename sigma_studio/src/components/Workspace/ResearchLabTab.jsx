import React, { useState } from 'react';
import ResearchLab from '../Chat/ResearchLab';
import PipelineDesigner from '../Chat/PipelineDesigner';
import { FlaskConical, GitCompare } from 'lucide-react';

// ==============================================================================
// RESEARCH LAB TAB — Due modalità:
// 1. "Pipeline Predefinita" (ResearchLab) — Template pronti con feedback loop
// 2. "Pipeline Designer" — Editor visuale DAG per configurazioni custom
// ==============================================================================

const MODES = [
  { id: 'default', label: '🚀 Pipeline Predefinita', icon: FlaskConical, desc: 'Template pronti con 4-7 agenti, feedback loop automatico, memoria distribuita' },
  { id: 'designer', label: '🧩 Pipeline Designer', icon: GitCompare, desc: 'Editor visuale DAG per creare pipeline custom con routing condizionale' },
];

export default function ResearchLabTab({ onTasksUpdated, addToast }) {
  const [mode, setMode] = useState('default');

  const handleClose = () => {
    // Just a no-op or could close the tab if needed
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Mode Switcher */}
      <div className="research-tab-mode-switcher">
        {MODES.map(m => (
          <button
            key={m.id}
            className={`research-tab-mode-btn ${mode === m.id ? 'active' : ''}`}
            onClick={() => setMode(m.id)}
          >
            <m.icon size={14} />
            <span>{m.label}</span>
            <span className="research-tab-mode-desc">{m.desc}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
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
