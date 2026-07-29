import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BookOpen, Database, Cpu, BarChart2, Brain, ShieldCheck, Award, Hammer, X } from 'lucide-react';
import TrainingDocs from './TrainingDocs';
import DatasetBrowser from './DatasetBrowser';
import TrainingConfigurator from './TrainingConfigurator';
import TrainingMonitor from './TrainingMonitor';
import TrainingBenchmark from './TrainingBenchmark';
import SlmForge from './SlmForge';
import TrainingHFToken from './TrainingHFToken';
import '../../styles/training-lab.css';

// ==============================================================================
// TRAINING LAB — Sigma Studio v7.0
// 7 sub-tab: Documentazione | Dataset | Training | Monitor | Forgia SLM | Benchmark | HF Token
// ==============================================================================

const MODES = [
  { id: 'docs', label: '📖 Documentazione', icon: BookOpen, desc: 'Guida completa al training' },
  { id: 'dataset', label: '🗃️ Dataset', icon: Database, desc: 'HuggingFace + Import locale' },
  { id: 'training', label: '⚙️ Configurazione', icon: Cpu, desc: 'Modello, metodo, iperparametri' },
  { id: 'monitor', label: '📊 Monitor', icon: BarChart2, desc: 'Log live, loss chart, export' },
  { id: 'forge', label: '🔨 Forgia SLM', icon: Hammer, desc: 'Modelli piccoli da zero, in italiano' },
  { id: 'benchmark', label: '🧪 Benchmark Test', icon: Award, desc: 'Test & valutazione modelli' },
  { id: 'token', label: '🔑 HF Token', icon: ShieldCheck, desc: 'Configura HuggingFace Token' },
];

function Toast({ toast, onClose }) {
  if (!toast) return null;
  const colors = {
    success: { border: 'rgba(63,185,80,0.25)', color: '#3fb950' },
    error:   { border: 'rgba(255,85,85,0.25)', color: '#ff5555' },
    warning: { border: 'rgba(255,184,108,0.25)', color: '#ffb86c' },
    info:    { border: 'rgba(0,210,255,0.25)', color: '#00d2ff' },
  };
  const c = colors[toast.type] || colors.info;
  return (
    <div style={{
      position: 'fixed', top: '20px', right: '20px', zIndex: 9999,
      background: 'rgba(10,12,26,0.95)', backdropFilter: 'blur(12px)',
      border: `1px solid ${c.border}`, borderRadius: '12px',
      padding: '12px 16px', maxWidth: '400px',
      boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'flex-start', gap: '10px',
    }}>
      <span style={{ fontSize: '0.9rem' }}>
        {toast.type === 'success' ? '✅' : toast.type === 'error' ? '❌' : toast.type === 'warning' ? '⚠️' : 'ℹ️'}
      </span>
      <div style={{ flex: 1, fontSize: '0.75rem', color: 'var(--text)', lineHeight: 1.5 }}>{toast.message}</div>
      <button onClick={onClose} style={{
        background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer',
        padding: '2px', borderRadius: '4px', display: 'flex',
      }}>
        <X size={14} />
      </button>
    </div>
  );
}

export default function TrainingLab({ addToast: _addToast, onTasksUpdated }) {
  const [mode, setMode] = useState('docs');
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [myDatasets, setMyDatasets] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // Load datasets from backend
  const loadMyDatasets = useCallback(async () => {
    try {
      const res = await fetch('/api/training/datasets');
      const data = await res.json();
      if (data.success) {
        setMyDatasets(data.datasets || []);
        return data.datasets || [];
      }
      return [];
    } catch (e) {
      return [];
    }
  }, []);

  // Load on mount
  useEffect(() => { loadMyDatasets(); }, [loadMyDatasets]);

  // Reload when switching to training tab
  useEffect(() => {
    if (mode === 'training') loadMyDatasets();
  }, [mode, loadMyDatasets]);

  // Toast system
  const showToast = (message, type = 'info', dur = 3500) => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), dur);
  };

  // Handler: dataset aggiunto → carica → naviga
  const handleDatasetAdded = async () => {
    const datasets = await loadMyDatasets();  // <-- ASPETTA che la fetch finisca!
    if (datasets.length > 0) {
      showToast('✅ Dataset aggiunto con successo! Ora configura il training.', 'success', 5000);
      setTimeout(() => setMode('training'), 300);
    } else {
      showToast('⚠️ Dataset aggiunto ma non trovato nella lista. Ricarica la pagina.', 'warning', 5000);
    }
  };

  const handleJobCreated = (job) => {
    setActiveJobId(job.id);
    setTimeout(() => setMode('monitor'), 400);
    if (onTasksUpdated) onTasksUpdated();
  };

  const selectedDs = myDatasets.find(d => d.id === selectedDatasetId);

  return (
    <div className="training-lab">
      <Toast toast={toast} onClose={() => setToast(null)} />

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
        {mode === 'docs' && <TrainingDocs />}

        {mode === 'dataset' && (
          <DatasetBrowser
            onDatasetSelect={(id) => {
              setSelectedDatasetId(id);
              loadMyDatasets();
              if (id) setTimeout(() => setMode('training'), 400);
            }}
            onDatasetAdded={handleDatasetAdded}
            selectedDatasetId={selectedDatasetId}
          />
        )}

        {mode === 'training' && (
          <TrainingConfigurator
            myDatasets={myDatasets}
            selectedDatasetId={selectedDatasetId}
            onDatasetSelect={setSelectedDatasetId}
            onJobCreated={handleJobCreated}
            addToast={showToast}
          />
        )}

        {mode === 'monitor' && (
          <TrainingMonitor
            activeJobId={activeJobId}
            onAddToast={showToast}
          />
        )}

        {mode === 'forge' && (
          <SlmForge addToast={showToast} onJobCreated={handleJobCreated} />
        )}

        {mode === 'benchmark' && (
          <TrainingBenchmark addToast={showToast} />
        )}

        {mode === 'token' && (
          <TrainingHFToken addToast={showToast} />
        )}
      </div>
    </div>
  );
}