import React, { useState, useEffect, useCallback } from 'react';
import { Database, Cpu, BarChart2, Brain } from 'lucide-react';
import DatasetBrowser from './DatasetBrowser';
import TrainingConfigurator from './TrainingConfigurator';
import TrainingMonitor from './TrainingMonitor';
import '../../styles/training-lab.css';

// ==============================================================================
// TRAINING LAB — Sigma Studio v7.0
// 3 sub-tab: Dataset | Training | Monitor
// Fully integrated with the Sigma agent system and task notifications
// ==============================================================================

const MODES = [
  {
    id: 'dataset',
    label: '🗃️ Dataset',
    icon: Database,
    desc: 'HuggingFace + Import locale + AI generate',
  },
  {
    id: 'training',
    label: '⚙️ Configurazione',
    icon: Cpu,
    desc: 'Modello base, metodo, iperparametri',
  },
  {
    id: 'monitor',
    label: '📊 Monitor',
    icon: BarChart2,
    desc: 'Log live, loss chart, export Ollama',
  },
];

export default function TrainingLab({ addToast, onTasksUpdated }) {
  const [mode, setMode] = useState('dataset');
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [myDatasets, setMyDatasets] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);

  // Shared dataset list (passed to both DatasetBrowser and TrainingConfigurator)
  const loadMyDatasets = useCallback(async () => {
    try {
      const res = await fetch('/api/training/datasets');
      const data = await res.json();
      if (data.success) setMyDatasets(data.datasets || []);
    } catch (e) {}
  }, []);

  useEffect(() => { loadMyDatasets(); }, [loadMyDatasets]);

  const handleDatasetSelect = (id) => {
    setSelectedDatasetId(id);
    // Auto-navigate to training configurator after selection
    if (id) {
      setTimeout(() => setMode('training'), 300);
    }
  };

  const handleJobCreated = (job) => {
    setActiveJobId(job.id);
    // Navigate to monitor
    setTimeout(() => setMode('monitor'), 400);
    // Notify task system if available
    if (onTasksUpdated) onTasksUpdated();
  };

  const handleAddToast = (msg, type = 'info', dur = 3000) => {
    if (addToast) addToast(msg, type, dur);
  };

  const selectedDs = myDatasets.find(d => d.id === selectedDatasetId);

  return (
    <div className="training-lab">
      {/* ── Mode switcher ── */}
      <div className="training-mode-switcher">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '12px' }}>
          <Brain size={16} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '0.02em' }}>
            TRAINING LAB
          </span>
        </div>
        {MODES.map(m => (
          <button
            key={m.id}
            className={`training-mode-btn ${mode === m.id ? 'active' : ''}`}
            onClick={() => setMode(m.id)}
          >
            <m.icon size={13} />
            <span>{m.label}</span>
            {/* Status badges */}
            {m.id === 'dataset' && myDatasets.length > 0 && (
              <span className="training-mode-badge">{myDatasets.length}</span>
            )}
            {m.id === 'training' && selectedDs && (
              <span className="training-mode-badge" style={{ background: 'rgba(63,185,80,0.12)', color: 'var(--success)' }}>
                ✓
              </span>
            )}
            {m.id === 'monitor' && activeJobId && (
              <span className="training-mode-badge" style={{ background: 'rgba(188,140,255,0.12)', color: 'var(--accent)' }}>
                ▶
              </span>
            )}
          </button>
        ))}

        {/* Breadcrumb status */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.62rem', color: 'var(--text-dark)' }}>
          {selectedDs && (
            <>
              <span style={{ color: 'var(--success)' }}>✓ {selectedDs.name}</span>
              <span>›</span>
            </>
          )}
          {activeJobId && (
            <span style={{ color: 'var(--accent)' }}>Job {activeJobId}</span>
          )}
        </div>
      </div>

      {/* ── Content area ── */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {mode === 'dataset' && (
          <DatasetBrowser
            onDatasetSelect={(id) => {
              setSelectedDatasetId(id);
              loadMyDatasets();
            }}
            selectedDatasetId={selectedDatasetId}
          />
        )}
        {mode === 'training' && (
          <TrainingConfigurator
            myDatasets={myDatasets}
            onJobCreated={handleJobCreated}
            addToast={handleAddToast}
          />
        )}
        {mode === 'monitor' && (
          <TrainingMonitor
            activeJobId={activeJobId}
            onAddToast={handleAddToast}
          />
        )}
      </div>
    </div>
  );
}
