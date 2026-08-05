import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BookOpen, Database, Cpu, BarChart2, Brain, Award, Hammer, Layers, Bot, Wrench, X } from 'lucide-react';
import TrainingDocs from './TrainingDocs';
import DatasetBrowser from './DatasetBrowser';
import TrainingConfigurator from './TrainingConfigurator';
import TrainingMonitor from './TrainingMonitor';
import TrainingStudio from './TrainingStudio';
import AutopilotStudio from './AutopilotStudio';
import TrainingBenchmark from './TrainingBenchmark';
import SlmForge from './SlmForge';
import '../../styles/training-lab.css';

// ==============================================================================
// TRAINING LAB — Sigma Studio v7.0
// Main modes: Documentazione (1st) | Autopilota (2nd) | Semi-assistito (3rd) | Manuale (4th)
// Inside Manuale: Dataset | Training | Forgia SLM | Benchmark Test | Monitor
// ==============================================================================

const MAIN_MODES = [
  { id: 'docs', label: '📖 Documentazione', icon: BookOpen, desc: 'Guida completa al training' },
  { id: 'autopilot', label: '🤖 Autopilota', icon: Bot, desc: 'Scegli un modello e lascialo migliorare da solo' },
  { id: 'studio', label: '🎛️ Semi-assistito', icon: Layers, desc: 'Percorso guidato per il fine-tuning' },
  { id: 'manual', label: '🧰 Manuale', icon: Wrench, desc: 'Dataset, Training, Forgia, Benchmark e Monitor' },
];

const MANUAL_SUBMODES = [
  { id: 'dataset', label: '🗃️ Dataset', icon: Database, desc: 'HuggingFace + Import locale' },
  { id: 'training', label: '⚙️ Training', icon: Cpu, desc: 'Modello, metodo, iperparametri' },
  { id: 'forge', label: '🔨 Forgia SLM', icon: Hammer, desc: 'Modelli piccoli da zero, in italiano' },
  { id: 'benchmark', label: '🧪 Benchmark Test', icon: Award, desc: 'Test & valutazione modelli' },
  { id: 'monitor', label: '📊 Monitor', icon: BarChart2, desc: 'Log live, loss chart, export' },
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
  // Impostiamo 'docs' (Documentazione) come scheda iniziale predefinita
  const [mode, setMode] = useState('docs');
  const [manualSubMode, setManualSubMode] = useState('dataset');
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
    if (mode === 'training' || (mode === 'manual' && manualSubMode === 'training')) loadMyDatasets();
  }, [mode, manualSubMode, loadMyDatasets]);

  // Toast system
  const showToast = (message, type = 'info', dur = 3500) => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), dur);
  };

  // Handler: dataset aggiunto → carica → naviga a training
  const handleDatasetAdded = async () => {
    const datasets = await loadMyDatasets();
    if (datasets.length > 0) {
      showToast('✅ Dataset aggiunto con successo! Ora configura il training.', 'success', 5000);
      setTimeout(() => {
        setMode('manual');
        setManualSubMode('training');
      }, 300);
    } else {
      showToast('⚠️ Dataset aggiunto ma non trovato nella lista. Ricarica la pagina.', 'warning', 5000);
    }
  };

  const handleJobCreated = (job) => {
    setActiveJobId(job.id);
    if (mode !== 'studio') {
      setTimeout(() => {
        setMode('manual');
        setManualSubMode('monitor');
      }, 400);
    }
    if (onTasksUpdated) onTasksUpdated();
  };

  const isManualActive = mode === 'manual' || ['dataset', 'training', 'forge', 'benchmark', 'monitor'].includes(mode);
  const currentActiveTab = isManualActive ? manualSubMode : mode;

  const handleMainTabClick = (id) => {
    if (id === 'manual') {
      setMode('manual');
    } else {
      setMode(id);
    }
  };

  const handleSubTabClick = (subId) => {
    setMode('manual');
    setManualSubMode(subId);
  };

  const selectedDs = myDatasets.find(d => d.id === selectedDatasetId);

  return (
    <div className="training-lab">
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* ── Top Level Bar ── */}
      <div className="training-mode-switcher">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '12px' }}>
          <Brain size={16} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '0.02em' }}>
            TRAINING LAB
          </span>
        </div>

        {MAIN_MODES.map(m => {
          const active = (m.id === 'manual' && isManualActive) || (m.id === mode && !isManualActive);
          return (
            <button
              key={m.id}
              className={`training-mode-btn ${active ? 'active' : ''}`}
              onClick={() => handleMainTabClick(m.id)}
            >
              <m.icon size={13} />
              <span>{m.label}</span>
              {m.id === 'manual' && (
                <span className="training-mode-badge" style={{ background: 'rgba(188,140,255,0.12)', color: '#bc8cff' }}>
                  5 strumenti
                </span>
              )}
            </button>
          );
        })}

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

      {/* ── Sub-navigation Bar per la modalità Manuale ── */}
      {isManualActive && (
        <div className="training-manual-subbar">
          <span style={{ fontSize: '0.64rem', color: 'var(--text-dark)', fontWeight: 700, marginRight: '4px', letterSpacing: '0.04em' }}>
            STRUMENTI MANUALE ›
          </span>
          {MANUAL_SUBMODES.map(sm => (
            <button
              key={sm.id}
              className={`training-manual-subbtn ${manualSubMode === sm.id ? 'active' : ''}`}
              onClick={() => handleSubTabClick(sm.id)}
            >
              <sm.icon size={12} />
              <span>{sm.label}</span>
              {sm.id === 'dataset' && myDatasets.length > 0 && (
                <span style={{ fontSize: '0.55rem', background: 'rgba(0,210,255,0.12)', color: 'var(--primary)', borderRadius: '6px', padding: '1px 5px', fontWeight: 700 }}>
                  {myDatasets.length}
                </span>
              )}
              {sm.id === 'training' && selectedDs && (
                <span style={{ fontSize: '0.55rem', color: 'var(--success)', fontWeight: 700 }}>✓</span>
              )}
              {sm.id === 'monitor' && activeJobId && (
                <span style={{ fontSize: '0.55rem', color: 'var(--accent)', fontWeight: 700 }}>▶</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* ── Content area ── */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {mode === 'docs' && <TrainingDocs />}

        {mode === 'autopilot' && <AutopilotStudio addToast={showToast} />}

        {mode === 'studio' && (
          <TrainingStudio
            myDatasets={myDatasets}
            selectedDatasetId={selectedDatasetId}
            onDatasetSelect={setSelectedDatasetId}
            onJobCreated={handleJobCreated}
            addToast={showToast}
          />
        )}

        {isManualActive && currentActiveTab === 'dataset' && (
          <DatasetBrowser
            onDatasetSelect={(id) => {
              setSelectedDatasetId(id);
              loadMyDatasets();
              if (id) setTimeout(() => { setMode('manual'); setManualSubMode('training'); }, 400);
            }}
            onDatasetAdded={handleDatasetAdded}
            selectedDatasetId={selectedDatasetId}
          />
        )}

        {isManualActive && currentActiveTab === 'training' && (
          <TrainingConfigurator
            myDatasets={myDatasets}
            selectedDatasetId={selectedDatasetId}
            onDatasetSelect={setSelectedDatasetId}
            onJobCreated={handleJobCreated}
            addToast={showToast}
          />
        )}

        {isManualActive && currentActiveTab === 'forge' && (
          <SlmForge addToast={showToast} onJobCreated={handleJobCreated} />
        )}

        {isManualActive && currentActiveTab === 'benchmark' && (
          <TrainingBenchmark addToast={showToast} />
        )}

        {isManualActive && currentActiveTab === 'monitor' && (
          <TrainingMonitor
            activeJobId={activeJobId}
            onAddToast={showToast}
          />
        )}
      </div>
    </div>
  );
}