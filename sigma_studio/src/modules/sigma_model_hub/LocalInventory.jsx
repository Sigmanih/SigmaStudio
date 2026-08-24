import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power,
  Activity, Upload, Download, Pause, Play, X, AlertTriangle, Package,
  RotateCcw, Search, ChevronDown, ChevronUp, Sliders, Layers, Sparkles,
  Loader, Check
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';

export default function LocalInventory({
  isLight,
  addToast,
  onDeployRequested,
  activeDownloads = [],
  onDownloadsChanged,
  engineStatus
}) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unloading, setUnloading] = useState(false);
  const [deletingPath, setDeletingPath] = useState(null);
  const [publishingModel, setPublishingModel] = useState(null);

  // Search & Filter state for local inventory
  const [searchQuery, setSearchQuery] = useState('');
  const [formatFilter, setFormatFilter] = useState('all'); // 'all' | 'gguf' | 'safetensors'

  // GGUF Converter state
  const [showConverter, setShowConverter] = useState(true);
  const [converterModels, setConverterModels] = useState([]);
  const [quantTypes, setQuantTypes] = useState([]);
  const [tooling, setTooling] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedConvertModel, setSelectedConvertModel] = useState('');
  const [selectedQuant, setSelectedQuant] = useState('Q4_K_M');
  const [convertingBusy, setConvertingBusy] = useState(false);
  const [converterLoading, setConverterLoading] = useState(false);
  const [converterError, setConverterError] = useState(null);

  const converterRef = useRef(null);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';
  const inputBg = isLight ? '#f3ede1' : 'rgba(0, 0, 0, 0.3)';

  // 1. Fetch local models
  const fetchLocalModels = useCallback(async () => {
    try {
      const res = await fetch('/api/models/local/list');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setModels(json.models || []);
        }
      }
    } catch (e) {
      console.error('Error fetching local models:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. Fetch GGUF converter info & jobs
  const fetchConverterInfo = useCallback(async () => {
    try {
      setConverterLoading(true);
      const res = await fetch('/api/models/convert/info');
      if (!res.ok) {
        setConverterError(res.status === 404 ? 'Modulo conversione non disponibile.' : `Errore server: ${res.status}`);
        return;
      }
      const json = await res.json();
      setConverterError(json.success ? null : (json.error || 'Risposta non valida.'));
      if (json.success) {
        setConverterModels(json.models || []);
        setQuantTypes(json.quantization_types || []);
        setTooling(json.tooling || null);
        setJobs(json.jobs || []);
        if (!selectedConvertModel && json.models?.length) {
          setSelectedConvertModel(json.models[0].name);
        }
      }
    } catch (e) {
      setConverterError(`Errore connessione: ${e.message}`);
    } finally {
      setConverterLoading(false);
    }
  }, [selectedConvertModel]);

  useEffect(() => {
    fetchLocalModels();
    fetchConverterInfo();
  }, [fetchLocalModels, fetchConverterInfo]);

  // Poll conversion jobs while active
  const activeConvertJob = jobs.find(j => ['queued', 'converting', 'quantizing'].includes(j.status));
  useEffect(() => {
    if (!activeConvertJob) return undefined;
    const timer = setInterval(async () => {
      try {
        const res = await fetch('/api/models/convert/jobs');
        const json = await res.json();
        if (json.success) {
          setJobs(json.jobs || []);
          fetchLocalModels();
        }
      } catch { /* retry next tick */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [activeConvertJob, fetchLocalModels]);

  // Actions
  const handleUnloadModel = async () => {
    setUnloading(true);
    try {
      const res = await fetch('/api/models/engine/unload', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🧹 ${json.message}`, 'info');
        fetchLocalModels();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setUnloading(false);
    }
  };

  const handleDeleteModel = async (model) => {
    const name = model.filename || model.display_name || model.model_id;
    const sizeInfo = model.size_label || (model.size_gb ? `${model.size_gb} GB` : '');
    const confirmMsg = `Sei sicuro di voler eliminare definitivamente il modello "${name}"${sizeInfo ? ` (${sizeInfo})` : ''} dallo storage locale?`;

    if (!window.confirm(confirmMsg)) return;

    setDeletingPath(model.path || model.filename);
    try {
      const res = await fetch('/api/models/local/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename,
          filename: model.filename
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(`🗑️ ${json.message || 'Modello eliminato con successo.'}`, 'success');
        fetchLocalModels();
        fetchConverterInfo();
        if (onDownloadsChanged) onDownloadsChanged();
      } else {
        if (addToast) addToast(`❌ ${json.error || 'Errore durante l\'eliminazione del modello.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setDeletingPath(null);
    }
  };

  // Download Task Controls
  const handlePauseDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`⏸️ Download #${taskId} messo in pausa.`, 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore pausa: ${e.message}`, 'error');
    }
  };

  const handleResumeDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🚀 Ripresa del download #${taskId}!`, 'success');
        if (onDownloadsChanged) onDownloadsChanged();
      } else {
        if (addToast) addToast(`Errore ripresa: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    }
  };

  const handleCancelDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`Download #${taskId} annullato.`, 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleRemoveDownloadTask = async (taskId, deleteFromDisk = false) => {
    try {
      const res = await fetch('/api/models/hf/download/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, delete_from_disk: deleteFromDisk })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(deleteFromDisk ? `🗑️ Download e file eliminati.` : `Notifica download rimossa.`, 'info');
        if (onDownloadsChanged) onDownloadsChanged();
        fetchLocalModels();
      }
    } catch (e) {
      if (addToast) addToast(`Errore rimozione: ${e.message}`, 'error');
    }
  };

  const handleClearCompletedDownloads = async () => {
    try {
      const res = await fetch('/api/models/hf/downloads/clear', { method: 'POST' });
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          if (addToast) addToast(`🧹 ${json.message || 'Cronologia download pulita.'}`, 'info');
          if (onDownloadsChanged) onDownloadsChanged();
          return;
        }
      }
    } catch (e) {
      console.warn('Backend clear endpoint error, fallback to batch remove:', e);
    }

    // Fallback: batch remove all finished/failed/cancelled tasks
    const tasksToClear = activeDownloads.filter(t => t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled');
    if (tasksToClear.length === 0) {
      if (addToast) addToast('Nessun download completato o terminato da rimuovere.', 'info');
      return;
    }

    try {
      await Promise.all(
        tasksToClear.map(t =>
          fetch('/api/models/hf/download/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: t.task_id, delete_from_disk: false })
          }).catch(() => {})
        )
      );
      if (addToast) addToast(`🧹 ${tasksToClear.length} notifiche di download rimosse.`, 'info');
      if (onDownloadsChanged) onDownloadsChanged();
    } catch (err) {
      if (addToast) addToast(`Errore pulizia: ${err.message}`, 'error');
    }
  };

  // Converter Handlers
  const handleInstallTooling = async () => {
    setConvertingBusy(true);
    try {
      const res = await fetch('/api/models/convert/tooling', { method: 'POST' });
      const json = await res.json();
      if (addToast) addToast(json.success ? `✅ ${json.message}` : `❌ ${json.error}`, json.success ? 'success' : 'error');
      fetchConverterInfo();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setConvertingBusy(false);
    }
  };

  const handleStartConversion = async () => {
    if (!selectedConvertModel) return;
    setConvertingBusy(true);
    try {
      const res = await fetch('/api/models/convert/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedConvertModel, quantization: selectedQuant })
      });
      const json = await res.json();
      if (json.success) {
        setJobs(prev => [json.job, ...prev]);
        if (addToast) addToast('🔄 Conversione GGUF avviata in background.', 'info');
      } else {
        if (addToast) addToast(`❌ ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setConvertingBusy(false);
    }
  };

  const handleTriggerConvertForModel = (modelName) => {
    setSelectedConvertModel(modelName);
    setShowConverter(true);
    if (converterRef.current) {
      converterRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Stats calculation
  const totalModelsCount = models.length;
  const ggufCount = models.filter(m => m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf')).length;
  const safetensorsCount = models.filter(m => m.format_tag === 'Safetensors' || !m.filename?.toLowerCase().endsWith('.gguf')).length;
  const totalStorageGb = models.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0).toFixed(1);

  // Filter models
  const filteredModels = models.filter(m => {
    const isGguf = m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf');
    if (formatFilter === 'gguf' && !isGguf) return false;
    if (formatFilter === 'safetensors' && isGguf) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const text = `${m.filename || ''} ${m.model_id || ''} ${m.format || ''} ${m.quantization || ''}`.toLowerCase();
      return text.includes(q);
    }
    return true;
  });

  const selectedConvertModelObj = converterModels.find(m => m.name === selectedConvertModel);
  const convertEstimate = selectedConvertModelObj?.estimated_outputs?.[selectedQuant];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* 1. TOP STORAGE & ENGINE SUMMARY BANNER */}
      <div style={{
        padding: '16px 20px', borderRadius: '16px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf5ec 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(26, 32, 54, 0.85) 100%)',
        border: cardBorder,
        boxShadow: isLight ? '0 4px 20px rgba(0,0,0,0.05)' : '0 8px 30px rgba(0,0,0,0.4)',
        display: 'flex', flexDirection: 'column', gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <HardDrive size={18} color="#ffb86c" />
              <h2 style={{ margin: 0, fontSize: '1.12rem', fontWeight: 800, color: textPrimary }}>
                Modelli Locali & Storage
              </h2>
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
              Gestisci i modelli presenti su disco, monitora i download attivi e converti checkpoint Safetensors in formato GGUF.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={handleUnloadModel}
              disabled={unloading}
              title="Scarica il modello attivo da VRAM/RAM e libera le risorse"
              style={{
                padding: '6px 14px', borderRadius: '8px',
                border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '5px',
                transition: 'all 0.15s ease'
              }}
            >
              <Power size={12} /> {unloading ? 'Rilascio...' : 'Rilascia Memoria Motore'}
            </button>

            <button
              onClick={() => {
                fetchLocalModels();
                fetchConverterInfo();
                if (onDownloadsChanged) onDownloadsChanged();
              }}
              title="Ricarica elenco modelli e stato"
              style={{
                padding: '6px 12px', borderRadius: '8px',
                border: subBorder, background: subBg,
                color: textPrimary, fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '4px'
              }}
            >
              <RefreshCw size={13} /> Aggiorna
            </button>
          </div>
        </div>

        {/* Storage Metric Badges */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
          <div style={{ padding: '8px 12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>MODELLI TOTALI</div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: textPrimary, marginTop: '2px' }}>
              {totalModelsCount} <span style={{ fontSize: '0.72rem', color: textMuted, fontWeight: 600 }}>modelli</span>
            </div>
          </div>

          <div style={{ padding: '8px 12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>FORMATI SU DISCO</div>
            <div style={{ fontSize: '0.90rem', fontWeight: 800, marginTop: '2px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: '#10b981' }}>⚡ {ggufCount} GGUF</span>
              <span style={{ color: textMuted }}>•</span>
              <span style={{ color: '#00d2ff' }}>📦 {safetensorsCount} Safetensors</span>
            </div>
          </div>

          <div style={{ padding: '8px 12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>SPAZIO OCCUPATO</div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#ffb86c', marginTop: '2px' }}>
              {totalStorageGb} <span style={{ fontSize: '0.72rem', color: textMuted, fontWeight: 600 }}>GB totali</span>
            </div>
          </div>

          <div style={{ padding: '8px 12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>STATO SIGMAENGINE</div>
            <div style={{ fontSize: '0.78rem', fontWeight: 800, color: engineStatus?.loaded_model ? '#00d2ff' : textMuted, marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {engineStatus?.loaded_model ? `⚡ ${engineStatus.loaded_model}` : 'Nessun modello caricato'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. ACTIVE DOWNLOADS & TASK NOTIFICATIONS MANAGEMENT */}
      {activeDownloads.length > 0 && (
        <div style={{
          padding: '16px 20px', borderRadius: '16px',
          background: cardBg, border: '1.5px solid rgba(0, 210, 255, 0.35)',
          boxShadow: '0 8px 24px rgba(0, 210, 255, 0.08)',
          display: 'flex', flexDirection: 'column', gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Download size={16} color="#00d2ff" />
              <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                Download in Corso & Notifiche ({activeDownloads.length})
              </span>
            </div>

            <button
              onClick={handleClearCompletedDownloads}
              title="Rimuove tutti i download terminati o falliti dalla vista"
              style={{
                padding: '4px 10px', borderRadius: '6px',
                border: subBorder, background: subBg,
                color: textMuted, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '4px'
              }}
            >
              <Trash2 size={11} /> Pulisci completati
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeDownloads.map(task => {
              const isRunning = task.status === 'downloading' || task.status === 'queued';
              const isPaused = task.status === 'paused';
              const isDone = task.status === 'completed';
              const isFailed = task.status === 'failed' || task.status === 'cancelled';

              return (
                <div
                  key={task.task_id}
                  style={{
                    padding: '12px 14px', borderRadius: '12px',
                    background: subBg,
                    border: isRunning ? '1px solid rgba(0, 210, 255, 0.4)' : (isFailed ? '1px solid rgba(239, 68, 68, 0.3)' : subBorder),
                    display: 'flex', flexDirection: 'column', gap: '8px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                      {isRunning && <Activity className="mh-spin" size={13} color="#00d2ff" />}
                      {isDone && <CheckCircle2 size={13} color="#10b981" />}
                      {isPaused && <Pause size={13} color="#ffb86c" />}
                      {isFailed && <AlertTriangle size={13} color="#ef4444" />}
                      <span style={{ fontSize: '0.80rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {task.model_id || task.filename}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      <span style={{
                        fontSize: '0.64rem', padding: '2px 6px', borderRadius: '4px',
                        fontWeight: 800,
                        background: isDone ? 'rgba(16, 185, 129, 0.15)' : (isRunning ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255, 184, 108, 0.15)'),
                        color: isDone ? '#10b981' : (isRunning ? '#00d2ff' : '#ffb86c')
                      }}>
                        {task.status.toUpperCase()} ({task.progress_pct}%)
                      </span>

                      {/* Controls per task */}
                      {isRunning && (
                        <button
                          onClick={() => handlePauseDownload(task.task_id)}
                          title="Metti in pausa il download (i file su disco rimangono salvati)"
                          style={{
                            padding: '3px 8px', borderRadius: '5px',
                            border: '1px solid rgba(255, 184, 108, 0.4)', background: 'rgba(255, 184, 108, 0.1)',
                            color: '#ffb86c', fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '2px'
                          }}
                        >
                          <Pause size={10} /> Pausa
                        </button>
                      )}

                      {(isPaused || isFailed) && (
                        <button
                          onClick={() => handleResumeDownload(task.task_id)}
                          title="Riprendi il download dai byte già scaricati su disco"
                          style={{
                            padding: '3px 8px', borderRadius: '5px',
                            border: '1px solid rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.1)',
                            color: '#10b981', fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '2px'
                          }}
                        >
                          <Play size={10} /> Riprendi
                        </button>
                      )}

                      {isRunning && (
                        <button
                          onClick={() => handleCancelDownload(task.task_id)}
                          title="Annulla download"
                          style={{
                            padding: '3px 8px', borderRadius: '5px',
                            border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.08)',
                            color: '#ef4444', fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '2px'
                          }}
                        >
                          <X size={10} /> Annulla
                        </button>
                      )}

                      <button
                        onClick={() => handleRemoveDownloadTask(task.task_id, false)}
                        title="Rimuovi notifica dalla lista"
                        style={{
                          background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: '2px 4px'
                        }}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div style={{ height: '4px', borderRadius: '2px', background: 'rgba(255, 255, 255, 0.08)', overflow: 'hidden' }}>
                    <div style={{
                      width: `${task.progress_pct}%`, height: '100%', borderRadius: '2px',
                      background: isDone
                        ? '#10b981'
                        : (isFailed ? '#ef4444' : 'linear-gradient(90deg, #00d2ff, #0090ff)'),
                      transition: 'width 0.3s ease'
                    }} />
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.66rem', color: textMuted }}>
                    <span>
                      {task.is_repo_download
                        ? `File ${task.current_file_idx || 1}/${task.total_files || 1} • ${task.current_file_name || ''}`
                        : `${task.downloaded_mb || 0} / ${task.total_mb || '...'} MB`}
                      {task.speed_mbps ? ` • ${task.speed_mbps} MB/s` : ''}
                    </span>
                    {task.error_message && (
                      <span style={{ color: '#ef4444', fontWeight: 600 }}>{task.error_message}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. INTEGRATED GGUF CONVERTER & QUANTIZATION TOOL */}
      <div
        ref={converterRef}
        style={{
          padding: '16px 20px', borderRadius: '16px',
          background: cardBg, border: cardBorder,
          display: 'flex', flexDirection: 'column', gap: '14px',
          boxShadow: isLight ? '0 4px 18px rgba(0,0,0,0.04)' : '0 8px 24px rgba(0,0,0,0.3)'
        }}
      >
        <div
          onClick={() => setShowConverter(!showConverter)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', userSelect: 'none' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.35)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Package size={17} color="#22c55e" />
            </div>
            <div>
              <div style={{ fontSize: '0.94rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                Conversione & Quantizzazione GGUF per SigmaEngine
                {jobs.length > 0 && (
                  <span style={{ fontSize: '0.64rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(34, 197, 94, 0.15)', color: '#22c55e', fontWeight: 800 }}>
                    {jobs.length} {jobs.length === 1 ? 'job' : 'jobs'}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.72rem', color: textMuted }}>
                Trasforma checkpoint Safetensors / PyTorch in formato GGUF quantizzato ad alta velocità per llama.cpp
              </div>
            </div>
          </div>

          <button style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer' }}>
            {showConverter ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </div>

        {showConverter && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderTop: subBorder, paddingTop: '12px' }}>
            {/* Tooling check banner */}
            {tooling && !tooling.ready && (
              <div style={{
                padding: '12px 14px', borderRadius: '10px',
                background: 'rgba(245, 158, 11, 0.10)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
              }}>
                <div>
                  <div style={{ fontSize: '0.76rem', color: isLight ? '#92400e' : '#fbbf24', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <AlertTriangle size={13} /> Strumento di conversione llama.cpp non ancora installato
                  </div>
                  <div style={{ fontSize: '0.70rem', color: textMuted, marginTop: '2px' }}>
                    Scarica lo script ufficiale di conversione llama.cpp (v{tooling.converter_version}) per consentire la trasformazione dei pesi.
                  </div>
                </div>

                <button
                  onClick={handleInstallTooling}
                  disabled={convertingBusy}
                  style={{
                    padding: '6px 14px', borderRadius: '6px',
                    border: 'none', background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                    color: '#ffffff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px'
                  }}
                >
                  <Download size={12} /> Installa Tooling
                </button>
              </div>
            )}

            {converterError ? (
              <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', fontSize: '0.75rem' }}>
                {converterError}
              </div>
            ) : converterModels.length === 0 ? (
              <div style={{ padding: '12px 14px', borderRadius: '10px', background: subBg, border: subBorder, color: textMuted, fontSize: '0.74rem' }}>
                ℹ️ Nessun modello Safetensors grezzo presente nella cartella storage. Scarica un modello Safetensors da Hugging Face per convertirlo in GGUF.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '4px' }}>
                    MODELLO SAFETENSORS DI PARTENZA
                  </div>
                  <select
                    value={selectedConvertModel}
                    onChange={e => setSelectedConvertModel(e.target.value)}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '8px',
                      background: inputBg, border: subBorder, color: textPrimary,
                      fontSize: '0.80rem', fontWeight: 700, outline: 'none'
                    }}
                  >
                    {converterModels.map(m => (
                      <option key={m.name} value={m.name} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                        {m.name} ({m.params_b}B • {m.size_gb} GB)
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '4px' }}>
                    QUANTIZZAZIONE TARGET
                  </div>
                  <select
                    value={selectedQuant}
                    onChange={e => setSelectedQuant(e.target.value)}
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: '8px',
                      background: inputBg, border: subBorder, color: textPrimary,
                      fontSize: '0.80rem', fontWeight: 700, outline: 'none'
                    }}
                  >
                    {quantTypes.map(q => (
                      <option key={q.id} value={q.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                        {q.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Model estimate & compatibility bar */}
            {selectedConvertModelObj && (
              <div style={{
                padding: '10px 14px', borderRadius: '10px',
                background: subBg, border: subBorder,
                fontSize: '0.72rem', color: textMuted, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
              }}>
                <div>
                  <strong style={{ color: textPrimary }}>{selectedConvertModelObj.name}</strong> • Architettura: {selectedConvertModelObj.architecture} ({selectedConvertModelObj.layers} layers)
                  <div style={{ marginTop: '2px' }}>
                    Dimensione stimata GGUF: <strong style={{ color: '#10b981' }}>~{convertEstimate ?? '?'} GB</strong> (da {selectedConvertModelObj.size_gb} GB iniziali)
                  </div>
                </div>

                <button
                  onClick={handleStartConversion}
                  disabled={convertingBusy || !selectedConvertModel || !tooling?.ready || !!activeConvertJob}
                  style={{
                    padding: '8px 16px', borderRadius: '8px',
                    border: 'none',
                    background: (convertingBusy || !tooling?.ready || !!activeConvertJob)
                      ? 'rgba(107, 114, 128, 0.2)'
                      : 'linear-gradient(135deg, #10b981, #00d2ff)',
                    color: '#ffffff', fontSize: '0.76rem', fontWeight: 800,
                    cursor: (convertingBusy || !tooling?.ready || !!activeConvertJob) ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: '5px',
                    boxShadow: '0 0 12px rgba(16, 185, 129, 0.25)'
                  }}
                >
                  {activeConvertJob ? <Activity className="mh-spin" size={13} /> : <Play size={13} />}
                  {activeConvertJob ? 'Conversione in corso...' : 'Avvia Conversione in GGUF'}
                </button>
              </div>
            )}

            {/* Conversion jobs history */}
            {jobs.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                  Cronologia Conversioni
                </span>
                {jobs.map(job => (
                  <div
                    key={job.job_id}
                    style={{
                      padding: '10px 14px', borderRadius: '10px',
                      background: inputBg, border: subBorder,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {job.status === 'completed' && <CheckCircle2 size={14} color="#10b981" />}
                      {job.status === 'failed' && <AlertTriangle size={14} color="#ef4444" />}
                      {['queued', 'converting', 'quantizing'].includes(job.status) && <Activity className="mh-spin" size={14} color="#00d2ff" />}
                      <div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary }}>
                          {job.source_model} → {job.quantization}
                        </div>
                        <div style={{ fontSize: '0.66rem', color: textMuted }}>
                          {job.status} • {job.elapsed_seconds}s {job.error ? `• ${job.error}` : ''}
                        </div>
                      </div>
                    </div>

                    {job.status === 'completed' && (
                      <button
                        onClick={() => setPublishingModel({
                          filename: job.output_filename || `${job.source_model}-${job.quantization}.gguf`,
                          path: job.output_path || job.output_filename,
                          format_tag: 'GGUF',
                          quantization: job.quantization
                        })}
                        style={{
                          padding: '4px 10px', borderRadius: '6px',
                          border: '1px solid rgba(255, 184, 108, 0.4)', background: 'rgba(255, 184, 108, 0.12)',
                          color: '#ffb86c', fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px'
                        }}
                      >
                        <Upload size={11} /> Pubblica su HF
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. LOCAL MODELS CATALOG & INVENTORY */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Search and Format Filter Bar */}
        <div style={{
          padding: '12px 16px', borderRadius: '14px',
          background: cardBg, border: cardBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px'
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            background: subBg, border: subBorder, borderRadius: '10px',
            padding: '6px 12px', flex: 1, minWidth: '220px'
          }}>
            <Search size={14} color="#ffb86c" />
            <input
              type="text"
              placeholder="Filtra tra i modelli scaricati..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent', border: 'none', outline: 'none',
                color: textPrimary, fontSize: '0.78rem', width: '100%'
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: 0 }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {[
              { id: 'all', label: `Tutti (${totalModelsCount})` },
              { id: 'gguf', label: `⚡ GGUF (${ggufCount})` },
              { id: 'safetensors', label: `📦 Safetensors (${safetensorsCount})` },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setFormatFilter(f.id)}
                style={{
                  padding: '5px 12px', borderRadius: '8px',
                  border: formatFilter === f.id ? '1px solid #ffb86c' : subBorder,
                  background: formatFilter === f.id ? (isLight ? '#fff' : 'rgba(255, 184, 108, 0.15)') : subBg,
                  color: formatFilter === f.id ? (isLight ? '#ea580c' : '#ffb86c') : textMuted,
                  fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Models List */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: textMuted }}>
            <Activity className="mh-spin" size={20} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
            <span>Scansione storage modelli...</span>
          </div>
        ) : filteredModels.length === 0 ? (
          <div style={{
            padding: '50px 20px', borderRadius: '14px', background: cardBg, border: cardBorder,
            textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px'
          }}>
            <HardDrive size={28} color="#bc8cff" />
            <div style={{ fontSize: '0.86rem', fontWeight: 700, color: textPrimary }}>
              {searchQuery || formatFilter !== 'all' ? 'Nessun modello corrispondente ai filtri.' : 'Nessun modello trovato nello storage locale.'}
            </div>
            <div style={{ fontSize: '0.74rem' }}>
              Esplora la tab "🔍 Esplora Hugging Face" per scaricare modelli GGUF o Safetensors.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filteredModels.map((m, idx) => {
              const isGguf = m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf');
              return (
                <div
                  key={idx}
                  style={{
                    padding: '12px 16px', borderRadius: '12px',
                    background: m.is_active_in_engine ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'rgba(0, 210, 255, 0.06)') : cardBg,
                    border: m.is_active_in_engine ? '1.5px solid #00d2ff' : cardBorder,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap'
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary, wordBreak: 'break-all' }}>
                        {m.filename}
                      </span>
                      <span style={{
                        fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                        fontWeight: 800,
                        background: isGguf ? 'rgba(34, 197, 94, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                        color: isGguf ? '#22c55e' : '#00d2ff',
                      }}>
                        {m.format_tag || (isGguf ? 'GGUF' : 'Safetensors')}
                      </span>
                      {m.quantization && (
                        <span style={{
                          fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                          background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', fontWeight: 800
                        }}>
                          {m.quantization}
                        </span>
                      )}
                      {m.is_active_in_engine && (
                        <span style={{
                          fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                          background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 800
                        }}>
                          ATTIVO IN SIGMAENGINE
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '3px' }}>
                      {m.format || (isGguf ? 'GGUF' : 'Safetensors')} • {m.size_gb} GB • VRAM stimata ~{m.est_vram_gb} GB
                      {m.added_at && <> • Aggiunto: {m.added_at}</>}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                    {/* Run in SigmaEngine */}
                    <button
                      onClick={() => onDeployRequested && onDeployRequested(m)}
                      style={{
                        padding: '5px 12px', borderRadius: '6px',
                        border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                        color: '#ffffff', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '4px',
                        boxShadow: '0 0 10px rgba(0, 210, 255, 0.25)'
                      }}
                    >
                      <Zap size={12} /> {m.is_active_in_engine ? 'Rialloca' : '⚡ Avvia in SigmaEngine'}
                    </button>

                    {/* If Safetensors, quick convert to GGUF */}
                    {!isGguf && (
                      <button
                        onClick={() => handleTriggerConvertForModel(m.model_id || m.filename)}
                        title="Configura e converti questo modello in GGUF quantizzato"
                        style={{
                          padding: '5px 10px', borderRadius: '6px',
                          border: '1px solid rgba(34, 197, 94, 0.35)', background: 'rgba(34, 197, 94, 0.10)',
                          color: '#22c55e', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '3px'
                        }}
                      >
                        <Package size={12} /> Converti GGUF
                      </button>
                    )}

                    {/* Publish to HF */}
                    <button
                      onClick={() => setPublishingModel(m)}
                      title="Pubblica questo modello sul tuo account Hugging Face Hub"
                      style={{
                        padding: '5px 10px', borderRadius: '6px',
                        border: '1px solid rgba(255, 184, 108, 0.35)',
                        background: isLight ? 'rgba(255, 184, 108, 0.12)' : 'rgba(255, 184, 108, 0.10)',
                        color: '#ffb86c', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '3px'
                      }}
                    >
                      <Upload size={12} /> Pubblica HF
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => handleDeleteModel(m)}
                      disabled={deletingPath === (m.path || m.filename)}
                      title="Elimina definitivamente dallo storage locale"
                      style={{
                        padding: '5px 9px', borderRadius: '6px',
                        border: isLight ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid rgba(239, 68, 68, 0.3)',
                        background: isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.1)',
                        color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '3px',
                        opacity: deletingPath === (m.path || m.filename) ? 0.6 : 1
                      }}
                    >
                      <Trash2 size={12} />
                      {deletingPath === (m.path || m.filename) ? '...' : 'Elimina'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {publishingModel && (
        <HfPublishModal
          model={publishingModel}
          onClose={() => setPublishingModel(null)}
          isLight={isLight}
          addToast={addToast}
        />
      )}
    </div>
  );
}
