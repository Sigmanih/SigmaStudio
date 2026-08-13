import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  BookOpen, Database, Cpu, BarChart2, Brain, Award, Hammer, Layers, Bot, Wrench, X,
  Zap, Activity, CheckCircle2, ArrowRight, ShieldCheck
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import TechSpaceCanvas from '../common/TechSpaceCanvas';
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
  { id: 'standby', label: '⚡ Moduli in Standby (6)', icon: Zap, desc: 'Funzionalità avanzate da attivare' },
];

const MANUAL_SUBMODES = [
  { id: 'dataset', label: '🗃️ Dataset', icon: Database, desc: 'HuggingFace + Import locale' },
  { id: 'training', label: '⚙️ Training', icon: Cpu, desc: 'Modello, metodo, iperparametri' },
  { id: 'forge', label: '🔨 Forgia SLM', icon: Hammer, desc: 'Modelli piccoli da zero, in italiano' },
  { id: 'benchmark', label: '🧪 Benchmark Test', icon: Award, desc: 'Test & valutazione modelli' },
  { id: 'monitor', label: '📊 Monitor', icon: BarChart2, desc: 'Log live, loss chart, export' },
];

// Standby / Inactive Training Modules Definitions (Card Grigie)
const STANDBY_TRAINING_MODULES = [
  {
    id: 'deepspeed_zero3',
    title: 'DeepSpeed ZeRO-3 Distributed Offload',
    subtitle: 'Ripartizione dello stato dell\'ottimizzatore AdamW e dei gradienti su più nodi GPU via DeepSpeed ZeRO-3.',
    prerequisite: 'Cluster Multi-GPU >= 2x NVIDIA RTX/A100 + NCCL Backend',
    statusBadge: 'HARDWARE PARALLELISM STANDBY',
    icon: Cpu,
    color: '#bc8cff',
    actionText: 'Abilita DeepSpeed ZeRO-3',
    details: 'Distribuisce i parametri del modello ed i vettori di gradiante tra più schede grafiche, consentendo il fine-tuning di LLM da 70B parametri senza esaurire la memoria VRAM locale.'
  },
  {
    id: 'dpo_rlhf',
    title: 'RLHF / DPO Preference Optimization',
    subtitle: 'Allineamento comportamentale degli agenti AI via Direct Preference Optimization (DPO) su dataset di preferenza.',
    prerequisite: 'Dataset formattato DPO (coppie chosen vs rejected)',
    statusBadge: 'DATASET PREFERENCE IN ATTESA',
    icon: Brain,
    color: '#00d2ff',
    actionText: 'Configura Pipeline DPO',
    details: 'Permette di perfezionare lo stile di risposta degli agenti AI addestrandoli direttamente su preferenze umane senza dover configurare un modello di reward separato.'
  },
  {
    id: 'unsloth_kernels',
    title: 'Unsloth 2x Faster Gradient Checkpointing',
    subtitle: 'Kernel Triton/CUDA personalizzati per raddoppiare la velocità di addestramento e ridurre il consumo VRAM del 70%.',
    prerequisite: 'Pacchetto Python unsloth[cu121-ampere-torch220]',
    statusBadge: 'CUDA KERNELS STANDBY',
    icon: Zap,
    color: '#3fb950',
    actionText: 'Attiva Kernel Unsloth',
    details: 'Inietta i kernel fusi personalizzati di Unsloth nel flusso di backpropagation PyTorch per velocizzare il training delle architetture Llama-3, Mistral e Gemma.'
  },
  {
    id: 'flash_attn2',
    title: 'FlashAttention-2 Multi-Head Fusion',
    subtitle: 'Calcolo esatto dell\'attenzione senza salvare la matrice interattiva in VRAM per contesti lunghi (16k-32k token).',
    prerequisite: 'GPU NVIDIA Ampere, Ada Lovelace o Hopper (Compute Capability >= 8.0)',
    statusBadge: 'NVIDIA AMPERE+ STANDBY',
    icon: Activity,
    color: '#ff5064',
    actionText: 'Abilita FlashAttention-2',
    details: 'Accellera in modo esponenziale l\'elaborazione di sequenze di testo molto lunghe durante il fine-tuning, riducendo l\'impronta di memoria dell\'operatore di attenzione.'
  },
  {
    id: 'wandb_logger',
    title: 'WandB & TensorBoard Live Telemetry Bridge',
    subtitle: 'Sincronizzazione automatica delle curve di Loss, Perplexity e Learning Rate sui dashboard cloud di Weights & Biases.',
    prerequisite: 'WANDB_API_KEY / Server TensorBoard locale',
    statusBadge: 'LOGGER API KEY MANCANTE',
    icon: BarChart2,
    color: '#ffb86c',
    actionText: 'Inserisci Key WandB',
    details: 'Invia in streaming la telemetria di addestramento a Weights & Biases per confrontare grafici di loss, hyperparameter sweep ed esportare report di ricerca.'
  },
  {
    id: 'gguf_exporter',
    title: 'GGUF / ExLlamaV2 Multi-Bit Quantizer',
    subtitle: 'Esportazione ed il confezionamento automatico del modello addestrato in formato quantizzato GGUF (Q4_K_M, Q8_0).',
    prerequisite: 'llama.cpp quantize tool binary',
    statusBadge: 'EXPORT PIPELINE STANDBY',
    icon: Database,
    color: '#38bdf8',
    actionText: 'Configura Esportatore GGUF',
    details: 'Converte automaticamente i pesi FP16/BF16 esportati dal fine-tuning in quantizzazioni a 4 o 8 bit compatibili con Ollama ed inferenza locale ad alta velocità.'
  }
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
  const { theme } = useApp();
  const [mode, setMode] = useState('docs');
  const [manualSubMode, setManualSubMode] = useState('dataset');
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [myDatasets, setMyDatasets] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // Standby training module activation modal state
  const [activeTrainModal, setActiveTrainModal] = useState(null);
  const [activatingTrain, setActivatingTrain] = useState(null);
  const [activatedTrain, setActivatedTrain] = useState({});

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

  useEffect(() => { loadMyDatasets(); }, [loadMyDatasets]);

  useEffect(() => {
    if (mode === 'training' || (mode === 'manual' && manualSubMode === 'training')) loadMyDatasets();
  }, [mode, manualSubMode, loadMyDatasets]);

  const showToast = (message, type = 'info', dur = 3500) => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), dur);
  };

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
    <div className="training-lab" style={{ display: 'flex', flexDirection: 'column', background: 'var(--bg)', color: '#e2e4eb', minHeight: '100%', overflowY: 'auto', position: 'relative' }}>
      {/* Animated Translucent Cyber Space Background Canvas */}
      <TechSpaceCanvas isLight={theme === 'light'} />

      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* ── High-Tech Visual Hero Banner ── */}
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
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/training_lab_hero.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/training_lab_hero.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '16px',
        flexShrink: 0
      }}>
        {/* Top Title & Subtitle with Right Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', zIndex: 2 }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: theme === 'light' ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px'
            }}>
              <Activity size={14} /> UNSLOTH QLORA & SLM MODEL FINE-TUNING LAB
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: theme === 'light' ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              🎓 Training & <span style={{
                color: theme === 'light' ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Fine-Tuning Lab</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: theme === 'light' ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Ambiente integrato per l'addestramento QLoRA 4-bit, la gestione dei dataset e la valutazione dei benchmark LLM.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={() => { setMode('manual'); setManualSubMode('training'); }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: (mode === 'manual' && manualSubMode === 'training') 
                  ? (theme === 'light' ? '#ea580c' : '#00d2ff') 
                  : (theme === 'light' ? '#fffdf9' : '#181b28'),
                color: (mode === 'manual' && manualSubMode === 'training') ? (theme === 'light' ? '#fff' : '#0a0d14') : (theme === 'light' ? '#111' : '#fff'),
                border: (mode === 'manual' && manualSubMode === 'training') ? 'none' : (theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)'),
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              <Cpu size={14} /> Training QLoRA
            </button>
            <button
              onClick={() => { setMode('manual'); setManualSubMode('dataset'); }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: (mode === 'manual' && manualSubMode === 'dataset') 
                  ? (theme === 'light' ? '#ea580c' : '#00d2ff') 
                  : (theme === 'light' ? '#fffdf9' : '#181b28'),
                color: (mode === 'manual' && manualSubMode === 'dataset') ? (theme === 'light' ? '#fff' : '#0a0d14') : (theme === 'light' ? '#111' : '#fff'),
                border: (mode === 'manual' && manualSubMode === 'dataset') ? 'none' : (theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)'),
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              <Database size={14} /> Dataset & SLM Forge
            </button>
          </div>
        </div>

        {/* Live Telemetry Metrics Cards inside Hero (Solid Non-Transparent) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', zIndex: 2 }}>
          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: theme === 'light' ? '#fffdf9' : '#121622',
            border: theme === 'light' ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(0, 210, 255, 0.3)', 
            boxShadow: theme === 'light' ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 18px rgba(0, 210, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: theme === 'light' ? '#554e42' : '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              DATASET CARICATI
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
              {myDatasets.length} Dataset Pronti
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px' }}>
              HuggingFace & JSONL locali
            </div>
          </div>

          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: 'rgba(10, 14, 24, 0.85)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(188, 140, 255, 0.3)', boxShadow: '0 4px 18px rgba(188, 140, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              METODO ADDETRAMENTO
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
              Unsloth QLoRA 4-bit
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px' }}>
              Risparmio VRAM 70% • Gradient Checkpoint
            </div>
          </div>

          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: 'rgba(10, 14, 24, 0.85)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(16, 185, 129, 0.3)', boxShadow: '0 4px 18px rgba(16, 185, 129, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              PIPELINE STATO
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
              {activeJobId ? `Job ${activeJobId} ▶` : 'Pronto per Training'}
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px' }}>
              {selectedDs ? `✓ ${selectedDs.name}` : 'Seleziona un dataset'}
            </div>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
      <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px', flexWrap: 'wrap' }}>
        {MAIN_MODES.map(m => {
          const active = (m.id === 'manual' && isManualActive) || (m.id === mode && !isManualActive);
          return (
            <button
              key={m.id}
              onClick={() => handleMainTabClick(m.id)}
              style={{
                background: active ? 'rgba(188, 140, 255, 0.15)' : 'transparent',
                border: active ? '1px solid rgba(188, 140, 255, 0.35)' : 'none',
                color: active ? '#bc8cff' : '#8b8fa3',
                padding: '8px 18px', borderRadius: '8px', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px',
                transition: 'all 0.15s ease'
              }}
            >
              <m.icon size={14} />
              <span>{m.label}</span>
              {m.id === 'manual' && (
                <span style={{ fontSize: '0.65rem', background: 'rgba(188,140,255,0.15)', color: '#bc8cff', padding: '1px 6px', borderRadius: '10px', fontWeight: 700 }}>
                  5 strumenti
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Sub-navigation Bar per la modalità Manuale ── */}
      {isManualActive && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', padding: '8px 12px', background: 'rgba(14, 17, 25, 0.8)', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
          <span style={{ fontSize: '0.72rem', color: '#6b7080', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginRight: '4px' }}>
            STRUMENTI MANUALE ›
          </span>
          {MANUAL_SUBMODES.map(sm => (
            <button
              key={sm.id}
              onClick={() => handleSubTabClick(sm.id)}
              style={{
                background: manualSubMode === sm.id ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${manualSubMode === sm.id ? 'rgba(0, 210, 255, 0.3)' : 'rgba(255, 255, 255, 0.08)'}`,
                color: manualSubMode === sm.id ? '#00d2ff' : '#8b8fa3',
                padding: '5px 12px', borderRadius: '8px', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              <sm.icon size={12} />
              <span>{sm.label}</span>
              {sm.id === 'dataset' && myDatasets.length > 0 && (
                <span style={{ fontSize: '0.62rem', background: 'rgba(0,210,255,0.15)', color: '#00d2ff', borderRadius: '6px', padding: '1px 5px', fontWeight: 800 }}>
                  {myDatasets.length}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* ── Content Area ── */}
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

        {/* ── SUB TAB: MODULI TRAINING IN STANDBY (Card Grigie) ── */}
        {mode === 'standby' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#8b8fa3', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                <Zap size={13} /> ESPANSIONI TRAINING PIPELINE & KERNEL IN ATTESA
              </div>
              <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: '#fff' }}>
                ⚡ Moduli & Engine di Training in Standby (Da Attivare)
              </h2>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#8b8fa3' }}>
                Architetture di addestramento avanzate, kernel fusi ed ottimizatori in attesa di configurazione hardware:
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
              {STANDBY_TRAINING_MODULES.map(mod => {
                const IconComp = mod.icon;
                const isActivated = activatedTrain[mod.id];

                return (
                  <div
                    key={mod.id}
                    style={{
                      padding: '24px', borderRadius: '18px',
                      background: isActivated ? 'rgba(14, 17, 25, 0.85)' : 'rgba(14, 17, 25, 0.4)',
                      border: '1px solid ' + (isActivated ? `${mod.color}40` : 'rgba(255, 255, 255, 0.08)'),
                      boxShadow: isActivated ? `0 8px 32px ${mod.color}15` : 'none',
                      display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                      gap: '16px', opacity: isActivated ? 1 : 0.72,
                      filter: isActivated ? 'none' : 'grayscale(35%)',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                        <div style={{
                          width: '44px', height: '44px', borderRadius: '12px',
                          background: isActivated ? `${mod.color}25` : 'rgba(255, 255, 255, 0.04)',
                          border: '1px solid ' + (isActivated ? mod.color : 'rgba(255,255,255,0.08)'),
                          color: isActivated ? mod.color : '#8b8fa3',
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          <IconComp size={22} />
                        </div>

                        <span style={{
                          fontSize: '0.68rem', fontWeight: 800,
                          color: isActivated ? '#3fb950' : '#8b8fa3',
                          background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                          border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.1)'),
                          padding: '3px 10px', borderRadius: '20px', letterSpacing: '0.5px'
                        }}>
                          {isActivated ? 'PIPELINE ATTIVA ⚡' : mod.statusBadge}
                        </span>
                      </div>

                      <h3 style={{ margin: '0 0 6px 0', fontSize: '1rem', fontWeight: 800, color: '#fff' }}>
                        {mod.title}
                      </h3>
                      <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                        {mod.subtitle}
                      </p>
                      <div style={{ fontSize: '0.72rem', color: '#6b7080', background: 'rgba(8, 10, 16, 0.6)', padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                        <strong>Requisito:</strong> {mod.prerequisite}
                      </div>
                    </div>

                    <button
                      onClick={() => setActiveTrainModal(mod)}
                      disabled={isActivated}
                      style={{
                        padding: '10px 16px', borderRadius: '10px',
                        background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.12)'),
                        color: isActivated ? '#3fb950' : '#e2e8f0', fontSize: '0.8rem', fontWeight: 700,
                        cursor: isActivated ? 'default' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      {isActivated ? <CheckCircle2 size={15} /> : <ArrowRight size={15} />}
                      {isActivated ? 'Modulo Training Abilitato' : mod.actionText}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Standby Training Activation Modal Popup */}
      {activeTrainModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', background: 'rgba(18, 20, 28, 0.95)',
            border: `1px solid ${activeTrainModal.color}40`, borderRadius: '20px',
            padding: '28px', boxShadow: '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: activeTrainModal.color }}>
              <activeTrainModal.icon size={26} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                  {activeTrainModal.title}
                </h2>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginTop: '2px' }}>
                  {activeTrainModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#c0c4d0', lineHeight: 1.6, marginBottom: '20px' }}>
              {activeTrainModal.details}
            </p>

            <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '24px', fontSize: '0.78rem', color: '#8b8fa3' }}>
              <div style={{ fontWeight: 700, color: '#fff', marginBottom: '4px' }}>📋 Requisito di Abilitazione:</div>
              {activeTrainModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveTrainModal(null)}
                style={{ padding: '10px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
              >
                Annulla
              </button>
              <button
                onClick={() => {
                  setActivatingTrain(activeTrainModal.id);
                  setTimeout(() => {
                    setActivatedTrain(prev => ({ ...prev, [activeTrainModal.id]: true }));
                    setActivatingTrain(null);
                    setActiveTrainModal(null);
                    showToast(`⚡ Modulo ${activeTrainModal.title} abilitato con successo!`, 'success');
                  }, 1200);
                }}
                disabled={activatingTrain === activeTrainModal.id}
                style={{
                  padding: '10px 22px', borderRadius: '10px',
                  background: `linear-gradient(135deg, ${activeTrainModal.color}, #00d2ff)`, border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}
              >
                {activatingTrain === activeTrainModal.id ? <Activity className="spin" size={15} /> : <Zap size={15} />}
                {activatingTrain === activeTrainModal.id ? 'Abilitazione...' : 'Connetti & Attiva Modulo Training ⚡'}
              </button>
            </div>
          </div>
        </div>
      )}

      </div>
    </div>
  );
}