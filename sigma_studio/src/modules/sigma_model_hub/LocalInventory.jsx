import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power, Pencil,
  Activity, Upload, Download, Pause, Play, X, AlertTriangle, Package,
  RotateCcw, Search, ChevronDown, ChevronUp, Sliders, Layers, Sparkles,
  Loader, Check, Trophy, Award, BarChart2, Gauge, Clock, Cpu, ExternalLink,
  PanelRightClose, PanelRightOpen, ArrowRight
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';
import InferenceTestModal from './InferenceTestModal.jsx';
import DownloadLogSidebar from './DownloadLogSidebar.jsx';

export default function LocalInventory({
  isLight,
  addToast,
  onDeployRequested,
  activeDownloads = [],
  onDownloadsChanged,
  engineStatus,
  onNavigateToConverter
}) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unloading, setUnloading] = useState(false);
  const [deletingPath, setDeletingPath] = useState(null);
  const [publishingModel, setPublishingModel] = useState(null);
  const [inferenceTestingModel, setInferenceTestingModel] = useState(null);

  // Search & Filter state for local inventory
  const [searchQuery, setSearchQuery] = useState('');
  const [renamingPath, setRenamingPath] = useState(null);
  const [updatingCard, setUpdatingCard] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [formatFilter, setFormatFilter] = useState('all'); // 'all' | 'gguf' | 'safetensors' | 'benchmarked' | 'published'
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // GGUF Converter state
  const [showConverter, setShowConverter] = useState(false);
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

  const cardBg = isLight ? '#ffffff' : 'rgba(15, 18, 28, 0.85)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.28)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.20)' : '1px solid rgba(255, 255, 255, 0.06)';
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

  const handleRenameModel = async (model) => {
    const attuale = model.model_id || model.filename || '';
    const nuovo = window.prompt(
      'Nuovo nome del modello.\n\nPuoi usare la forma autore/modello: sul disco '
      + 'diventa autore--modello, come i modelli scaricati da Hugging Face.',
      attuale
    );
    if (nuovo === null) return;
    if (!nuovo.trim() || nuovo.trim() === attuale) return;

    setRenamingPath(model.path || model.filename);
    try {
      const res = await fetch('/api/models/local/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename,
          new_name: nuovo.trim()
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(
          json.renamed ? `✏️ Rinominato in "${json.new_name}"` : (json.message || 'Nessuna modifica'),
          'success');
        fetchLocalModels();
        fetchConverterInfo();
      } else if (addToast) {
        addToast(`❌ ${json.error || 'Rinomina non riuscita.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setRenamingPath(null);
    }
  };

  const handleDiscoverRepos = async () => {
    setDiscovering(true);
    try {
      const res = await fetch('/api/models/hf/repo/discover', { method: 'POST' });
      const json = await res.json();
      if (!json.success) {
        if (addToast) addToast(`${json.error || 'Ricerca non riuscita'}`, 'error');
        return;
      }
      const certi = (json.matches || []).filter(m => m.repo_id);
      const dubbi = (json.matches || []).filter(m => m.ambiguous);
      if (!certi.length) {
        if (addToast) addToast(
          dubbi.length
            ? `Nessuna corrispondenza univoca (${dubbi.length} ambigue: collegale a mano).`
            : 'Nessun repository da collegare: sono già tutti collegati o non ce ne sono.',
          'info');
        return;
      }
      const elenco = certi.map(m => `  ${m.model_id}  →  ${m.repo_id}`).join('\n');
      const salto = String.fromCharCode(10, 10);
      const domanda = 'Collego questi modelli ai repository trovati sul tuo account?'
        + salto + elenco + salto
        + 'Nessun file viene caricato o modificato su Hugging Face.';
      if (!window.confirm(domanda)) return;

      let collegati = 0;
      for (const m of certi) {
        const r = await fetch('/api/models/hf/repo/attach', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ local_path: m.local_ref, repo_id: m.repo_id })
        });
        if ((await r.json()).success) collegati += 1;
      }
      if (addToast) addToast(`${collegati} modelli collegati al proprio repository.`, 'success');
      fetchLocalModels();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setDiscovering(false);
    }
  };

  const handleUpdateCard = async (model) => {
    const chiave = model.path || model.filename;
    const note = window.prompt(
      'Note da inserire nella scheda su Hugging Face (il testo del paper, una '
      + 'correzione, un aggiornamento). Lascia vuoto per rigenerarla soltanto '
      + 'con i benchmark e le misure più recenti.',
      ''
    );
    if (note === null) return;

    setUpdatingCard(chiave);
    try {
      const res = await fetch('/api/models/hf/card/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: model.path || model.filename,
          model_id: model.model_id,
          custom_notes: note.trim() || undefined
        })
      });
      const json = await res.json();
      if (json.success && addToast) {
        addToast(`Scheda aggiornata su ${json.repo_id} (${json.characters} caratteri)`, 'success');
      } else if (addToast) {
        addToast(`${json.error || 'Aggiornamento non riuscito'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setUpdatingCard(null);
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
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setDeletingPath(null);
    }
  };

  // Converter Handlers
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
    if (onNavigateToConverter) {
      onNavigateToConverter(modelName);
    } else {
      setSelectedConvertModel(modelName);
      setShowConverter(true);
      if (converterRef.current) {
        converterRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  // Stats calculation
  const totalModelsCount = models.length;
  const ggufModels = models.filter(m => m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf'));
  const safetensorsModels = models.filter(m => m.format_tag === 'SAFETENSORS' || m.filename?.toLowerCase().endsWith('.safetensors') || (m.is_repo_folder && !m.format_tag?.includes('GGUF')));
  const benchmarkedModels = models.filter(m => m.benchmark_summary?.has_benchmarks);
  const publishedModels = models.filter(m => m.publication?.repo_id);

  const ggufCount = ggufModels.length;
  const safetensorsCount = safetensorsModels.length;
  const benchmarkedCount = benchmarkedModels.length;
  const publishedCount = publishedModels.length;

  const ggufStorageGb = ggufModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const safetensorsStorageGb = safetensorsModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const totalStorageGb = (ggufStorageGb + safetensorsStorageGb).toFixed(1);

  const ggufPct = totalStorageGb > 0 ? Math.round((ggufStorageGb / totalStorageGb) * 100) : 0;
  const safePct = totalStorageGb > 0 ? Math.round((safetensorsStorageGb / totalStorageGb) * 100) : 0;

  // Filter models
  const filteredModels = models.filter(m => {
    const isGguf = m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf');
    const isSafetensors = m.format_tag === 'SAFETENSORS' || m.filename?.toLowerCase().endsWith('.safetensors') || (m.is_repo_folder && !isGguf);
    const hasBenchmark = !!m.benchmark_summary?.has_benchmarks;
    const isPublished = !!m.publication?.repo_id;

    if (formatFilter === 'gguf' && !isGguf) return false;
    if (formatFilter === 'safetensors' && !isSafetensors) return false;
    if (formatFilter === 'benchmarked' && !hasBenchmark) return false;
    if (formatFilter === 'published' && !isPublished) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (m.filename || '').toLowerCase().includes(q);
      const matchId = (m.model_id || '').toLowerCase().includes(q);
      const matchDisp = (m.display_name || '').toLowerCase().includes(q);
      const matchQuant = (m.quantization || '').toLowerCase().includes(q);
      const matchArch = (m.architecture || '').toLowerCase().includes(q);
      const matchSuite = (m.benchmark_summary?.suite_name || '').toLowerCase().includes(q);
      const matchRepo = (m.publication?.repo_id || '').toLowerCase().includes(q);
      return matchName || matchId || matchDisp || matchQuant || matchArch || matchSuite || matchRepo;
    }
    return true;
  });

  const selectedConvertModelObj = converterModels.find(m => m.name === selectedConvertModel);
  const convertEstimate = selectedConvertModelObj?.estimated_outputs?.[selectedQuant];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

      {/* 1. TOP STORAGE & ENGINE DASHBOARD */}
      <div style={{
        padding: '18px 22px', borderRadius: '18px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf5ec 100%)'
          : 'linear-gradient(135deg, rgba(14, 18, 28, 0.95) 0%, rgba(24, 30, 48, 0.85) 100%)',
        border: isLight ? '1.5px solid rgba(190, 160, 110, 0.35)' : '1.5px solid rgba(0, 210, 255, 0.20)',
        boxShadow: isLight ? '0 4px 20px rgba(0,0,0,0.05)' : '0 8px 32px rgba(0,0,0,0.45)',
        display: 'flex', flexDirection: 'column', gap: '14px',
        backdropFilter: 'blur(16px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '34px', height: '34px', borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(188, 140, 255, 0.25))',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <HardDrive size={18} color="#00d2ff" />
              </div>
              <h2 style={{ margin: 0, fontSize: '1.20rem', fontWeight: 900, color: textPrimary, letterSpacing: '-0.02em' }}>
                Modelli Locali & Hub Storage
              </h2>
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '3px' }}>
              Gestisci i modelli presenti su disco, prova l'inferenza con telemetria tok/s e pubblica/aggiorna su Hugging Face.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={handleDiscoverRepos}
              disabled={discovering}
              title="Cerca sul tuo account Hugging Face i repository che corrispondono ai modelli locali e li collega, così da poterli aggiornare"
              style={{
                padding: '6px 12px', borderRadius: '8px',
                border: '1px solid rgba(255,184,108,0.35)',
                background: 'rgba(255,184,108,0.08)', color: '#ffb86c',
                fontSize: '0.72rem', fontWeight: 700, cursor: discovering ? 'wait' : 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: '5px'
              }}
            >
              <ExternalLink size={12} />
              {discovering ? 'Cerco su Hugging Face...' : 'Collega repo HF esistenti'}
            </button>

            <button
              onClick={handleUnloadModel}
              disabled={unloading}
              title="Scarica il modello attivo da VRAM/RAM e libera le risorse"
              style={{
                padding: '6px 13px', borderRadius: '8px',
                border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px',
                transition: 'all 0.15s ease'
              }}
            >
              <Power size={12} /> {unloading ? 'Rilascio...' : 'Rilascia VRAM'}
            </button>

            <button
              onClick={() => {
                fetchLocalModels();
                fetchConverterInfo();
                if (onDownloadsChanged) onDownloadsChanged();
              }}
              title="Ricarica elenco modelli e stato"
              style={{
                padding: '6px 13px', borderRadius: '8px',
                border: subBorder, background: subBg,
                color: textPrimary, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              <RefreshCw size={12} /> Ricarica
            </button>
          </div>
        </div>

        {/* Storage Metric Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Cpu size={12} color="#00d2ff" /> MODELLI TOTALI
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: textPrimary, marginTop: '2px' }}>
              {totalModelsCount} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>su disco</span>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Layers size={12} color="#10b981" /> FORMATI SU DISCO
            </div>
            <div style={{ fontSize: '0.86rem', fontWeight: 800, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: '#10b981' }}>⚡ {ggufCount} GGUF</span>
              <span style={{ color: textMuted }}>•</span>
              <span style={{ color: '#00d2ff' }}>📦 {safetensorsCount} Safe</span>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Trophy size={12} color="#ffb86c" /> BENCHMARK
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#ffb86c', marginTop: '2px' }}>
              {benchmarkedCount} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>valutati</span>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Upload size={12} color="#ff79c6" /> SU HUGGING FACE
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#ff79c6', marginTop: '2px' }}>
              {publishedCount} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>pubblicati</span>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <HardDrive size={12} color="#bc8cff" /> SPAZIO DISCO
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#bc8cff', marginTop: '2px' }}>
              {totalStorageGb} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>GB</span>
            </div>
          </div>
        </div>

        {/* Visual Storage Distribution Bar */}
        {totalStorageGb > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted, fontWeight: 700 }}>
              <span style={{ color: '#10b981' }}>⚡ GGUF: {ggufStorageGb.toFixed(1)} GB ({ggufPct}%)</span>
              <span style={{ color: '#00d2ff' }}>📦 Safetensors: {safetensorsStorageGb.toFixed(1)} GB ({safePct}%)</span>
            </div>
            <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden', display: 'flex' }}>
              <div style={{ width: `${ggufPct}%`, height: '100%', background: '#10b981', transition: 'width 0.3s ease' }} />
              <div style={{ width: `${safePct}%`, height: '100%', background: '#00d2ff', transition: 'width 0.3s ease' }} />
            </div>
          </div>
        )}
      </div>

      {/* 2. MAIN 2-COLUMN WORKSPACE: MODEL CATALOG + DOWNLOAD LOG SIDEBAR */}
      <div style={{ display: 'flex', gap: '18px', alignItems: 'flex-start', position: 'relative' }}>

        {/* LEFT / CENTER COLUMN: MODELS CATALOG */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '14px' }}>

          {/* Search & Filter Bar */}
          <div style={{
            padding: '12px 16px', borderRadius: '16px',
            background: cardBg, border: cardBorder,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px',
            backdropFilter: 'blur(12px)'
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              background: subBg, border: subBorder, borderRadius: '10px',
              padding: '6px 12px', flex: 1, minWidth: '220px'
            }}>
              <Search size={14} color="#00d2ff" />
              <input
                type="text"
                placeholder="Cerca modello per nome, quantizzazione, architettura o repo HF..."
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
                  <X size={13} />
                </button>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: `Tutti (${totalModelsCount})`, color: '#00d2ff' },
                { id: 'gguf', label: `⚡ GGUF (${ggufCount})`, color: '#10b981' },
                { id: 'safetensors', label: `📦 Safetensors (${safetensorsCount})`, color: '#38bdf8' },
                { id: 'benchmarked', label: `🏆 Valutati (${benchmarkedCount})`, color: '#ffb86c' },
                { id: 'published', label: `🤗 Pubblicati (${publishedCount})`, color: '#ff79c6' },
              ].map(f => (
                <button
                  key={f.id}
                  onClick={() => setFormatFilter(f.id)}
                  style={{
                    padding: '5px 11px', borderRadius: '8px',
                    border: formatFilter === f.id ? `1.5px solid ${f.color}` : subBorder,
                    background: formatFilter === f.id ? (isLight ? '#fff' : 'rgba(255, 255, 255, 0.08)') : subBg,
                    color: formatFilter === f.id ? f.color : textMuted,
                    fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Integrated GGUF Converter Tool (Collapsible) */}
          <div
            ref={converterRef}
            style={{
              padding: '14px 18px', borderRadius: '14px',
              background: cardBg, border: cardBorder,
              display: 'flex', flexDirection: 'column', gap: '10px'
            }}
          >
            <div
              onClick={() => setShowConverter(!showConverter)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                cursor: 'pointer', userSelect: 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Package size={15} color="#10b981" />
                <span style={{ fontSize: '0.84rem', fontWeight: 800, color: textPrimary }}>
                  Convertitore & Quantizzazione GGUF (llama.cpp)
                </span>
                <span style={{
                  fontSize: '0.60rem', padding: '2px 6px', borderRadius: '4px',
                  background: tooling?.ready ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: tooling?.ready ? '#10b981' : '#ef4444', fontWeight: 800
                }}>
                  {tooling?.ready ? '⚡ STRUMENTI PRONTI' : '⚠️ STRUMENTI NON CONFIGURATI'}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: textMuted }}>
                <span style={{ fontSize: '0.68rem' }}>{showConverter ? 'Comprimi' : 'Espandi'}</span>
                {showConverter ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </div>
            </div>

            {showConverter && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingTop: '8px', borderTop: subBorder }}>
                {converterError && (
                  <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', fontSize: '0.74rem' }}>
                    {converterError}
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.66rem', fontWeight: 800, color: textMuted, marginBottom: '4px', textTransform: 'uppercase' }}>
                      Modello Safetensors di Partenza
                    </label>
                    <select
                      value={selectedConvertModel}
                      onChange={e => setSelectedConvertModel(e.target.value)}
                      disabled={convertingBusy || !converterModels.length}
                      style={{
                        width: '100%', padding: '7px 10px', borderRadius: '8px',
                        background: inputBg, border: subBorder, color: textPrimary,
                        fontSize: '0.74rem', fontWeight: 700, outline: 'none'
                      }}
                    >
                      {converterModels.length === 0 ? (
                        <option value="">Nessun modello Safetensors convertibile trovato</option>
                      ) : (
                        converterModels.map(m => (
                          <option key={m.name} value={m.name}>
                            {m.name} ({m.param_size || '?'} • {m.size_gb} GB)
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.66rem', fontWeight: 800, color: textMuted, marginBottom: '4px', textTransform: 'uppercase' }}>
                      Quantizzazione Target
                    </label>
                    <select
                      value={selectedQuant}
                      onChange={e => setSelectedQuant(e.target.value)}
                      disabled={convertingBusy}
                      style={{
                        width: '100%', padding: '7px 10px', borderRadius: '8px',
                        background: inputBg, border: subBorder, color: textPrimary,
                        fontSize: '0.74rem', fontWeight: 700, outline: 'none'
                      }}
                    >
                      {quantTypes.map(q => (
                        <option key={q.type} value={q.type}>
                          {q.type} ({q.description}) {q.recommended ? '★ CONSIGLIATO' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {selectedConvertModelObj && (
                  <div style={{
                    padding: '10px 12px', borderRadius: '8px',
                    background: subBg, border: subBorder,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
                  }}>
                    <div>
                      <div style={{ fontSize: '0.76rem', fontWeight: 800, color: textPrimary }}>
                        {selectedConvertModelObj.name} • {selectedConvertModelObj.size_gb} GB
                      </div>
                      <div style={{ fontSize: '0.68rem', color: '#10b981', marginTop: '1px', fontWeight: 600 }}>
                        Stima output GGUF: ~{convertEstimate?.size_gb || '?'} GB
                      </div>
                    </div>

                    <button
                      onClick={handleStartConversion}
                      disabled={convertingBusy || !tooling?.ready || !!activeConvertJob}
                      style={{
                        padding: '7px 14px', borderRadius: '8px',
                        border: 'none', background: 'linear-gradient(135deg, #10b981, #059669)',
                        color: '#ffffff', fontSize: '0.74rem', fontWeight: 800,
                        cursor: (convertingBusy || !tooling?.ready || !!activeConvertJob) ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', gap: '5px'
                      }}
                    >
                      {activeConvertJob ? <Activity className="mh-spin" size={12} /> : <Play size={12} />}
                      {activeConvertJob ? 'Conversione...' : 'Avvia Conversione'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Models List */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '50px', color: textMuted }}>
              <Activity className="mh-spin" size={24} color="#00d2ff" style={{ margin: '0 auto 10px' }} />
              <span style={{ fontSize: '0.84rem' }}>Scansione modelli locali in corso...</span>
            </div>
          ) : filteredModels.length === 0 ? (
            <div style={{
              padding: '50px 20px', borderRadius: '16px', background: cardBg, border: cardBorder,
              textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'
            }}>
              <HardDrive size={32} color="#bc8cff" />
              <div style={{ fontSize: '0.92rem', fontWeight: 800, color: textPrimary }}>
                {searchQuery || formatFilter !== 'all' ? 'Nessun modello corrispondente ai filtri selezionati.' : 'Nessun modello trovato nello storage locale.'}
              </div>
              <div style={{ fontSize: '0.76rem' }}>
                Esplora la tab "🔍 Esplora Hugging Face" per scaricare modelli GGUF o Safetensors.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {filteredModels.map((m, idx) => {
                const isGguf = m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf');
                const bm = m.benchmark_summary || {};
                const hasBenchmark = !!bm.has_benchmarks;
                const bmScore = bm.score ?? bm.best_score ?? bm.latest_score ?? 0;
                const bmScoreColor = bmScore >= 70 ? '#10b981' : (bmScore >= 40 ? '#00d2ff' : '#ffb86c');
                const isPublished = Boolean(m.publication?.repo_id);

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '16px 20px', borderRadius: '16px',
                      background: m.is_active_in_engine
                        ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.12) 0%, rgba(15, 18, 28, 0.92) 100%)')
                        : cardBg,
                      border: m.is_active_in_engine ? '1.5px solid #00d2ff' : cardBorder,
                      boxShadow: m.is_active_in_engine ? '0 0 22px rgba(0, 210, 255, 0.18)' : 'none',
                      display: 'flex', flexDirection: 'column', gap: '12px',
                      transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                    }}
                  >
                    {/* Top Bar: Title & Status Badges */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.98rem', fontWeight: 900, color: textPrimary, wordBreak: 'break-all', letterSpacing: '-0.01em' }}>
                            {m.display_name || m.filename}
                          </span>

                          {/* Format Tag */}
                          <span style={{
                            fontSize: '0.62rem', padding: '2px 7px', borderRadius: '5px',
                            fontWeight: 800,
                            background: isGguf ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                            color: isGguf ? '#10b981' : '#00d2ff',
                            border: isGguf ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)'
                          }}>
                            {m.format_tag || (isGguf ? 'GGUF' : 'SAFETENSORS')}
                          </span>

                          {/* Quantization */}
                          {m.quantization && (
                            <span style={{
                              fontSize: '0.62rem', padding: '2px 7px', borderRadius: '5px',
                              background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', fontWeight: 800,
                              border: '1px solid rgba(188, 140, 255, 0.3)'
                            }}>
                              {m.quantization}
                            </span>
                          )}

                          {/* Parameter size */}
                          {m.params_label && (
                            <span style={{
                              fontSize: '0.62rem', padding: '2px 7px', borderRadius: '5px',
                              background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800,
                              border: '1px solid rgba(255, 184, 108, 0.3)'
                            }}>
                              ⚡ {m.params_label}
                            </span>
                          )}

                          {/* Active in Engine badge */}
                          {m.is_active_in_engine && (
                            <span style={{
                              fontSize: '0.62rem', padding: '2px 8px', borderRadius: '5px',
                              background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(16, 185, 129, 0.25))',
                              color: '#00d2ff', fontWeight: 900,
                              border: '1px solid #00d2ff',
                              boxShadow: '0 0 10px rgba(0, 210, 255, 0.35)'
                            }}>
                              ⚡ CARICATO IN SIGMAENGINE
                            </span>
                          )}

                          {/* Hugging Face Published Badge */}
                          {isPublished && (
                            <a
                              href={m.publication.url}
                              target="_blank"
                              rel="noreferrer"
                              title={`Pubblicato su Hugging Face: ${m.publication.repo_id}`}
                              style={{
                                fontSize: '0.62rem', padding: '2px 8px', borderRadius: '5px',
                                background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800,
                                border: '1px solid rgba(255, 184, 108, 0.35)', textDecoration: 'none',
                                display: 'inline-flex', alignItems: 'center', gap: '3px'
                              }}
                            >
                              🤗 HF: {m.publication.repo_id} <ExternalLink size={9} />
                            </a>
                          )}
                        </div>

                        {/* Specs Row */}
                        <div style={{ fontSize: '0.70rem', color: textMuted, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span>💾 <b>{m.size_gb} GB</b> su disco</span>
                          <span>•</span>
                          <span>⚡ VRAM stimata: <b>~{m.est_vram_gb} GB</b></span>
                          {m.architecture && (
                            <>
                              <span>•</span>
                              <span>🧬 Architettura: <b>{m.architecture}</b></span>
                            </>
                          )}
                          {m.added_at && (
                            <>
                              <span>•</span>
                              <span>🕒 Aggiunto: {m.added_at}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions Bar */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0, flexWrap: 'wrap' }}>
                        {/* Run in SigmaEngine */}
                        <button
                          onClick={() => onDeployRequested && onDeployRequested(m)}
                          style={{
                            padding: '6px 14px', borderRadius: '8px',
                            border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                            color: '#ffffff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '5px',
                            boxShadow: '0 0 12px rgba(0, 210, 255, 0.30)',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          <Zap size={13} /> {m.is_active_in_engine ? 'Rialloca' : '⚡ Avvia'}
                        </button>

                        {/* Prova Inferenza Interactive Modal */}
                        <button
                          onClick={() => setInferenceTestingModel(m)}
                          title="Apri il playground per scrivere prompt ed eseguire la telemetria t/s"
                          style={{
                            padding: '6px 12px', borderRadius: '8px',
                            border: '1px solid rgba(0,210,255,0.4)',
                            background: 'rgba(0,210,255,0.12)',
                            color: '#00d2ff', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '5px'
                          }}
                        >
                          <Gauge size={13} /> Prova Inferenza
                        </button>

                        {/* Publish vs Update on HF */}
                        <button
                          onClick={() => setPublishingModel(m)}
                          title={isPublished ? `Modello già pubblicato su HF (${m.publication.repo_id}): clicca per sincronizzare o aggiornare la scheda` : "Pubblica questo modello su Hugging Face Hub"}
                          style={{
                            padding: '6px 11px', borderRadius: '8px',
                            border: isPublished ? '1px solid rgba(255, 184, 108, 0.5)' : '1px solid rgba(255, 184, 108, 0.35)',
                            background: isPublished ? 'rgba(255, 184, 108, 0.18)' : (isLight ? 'rgba(255, 184, 108, 0.12)' : 'rgba(255, 184, 108, 0.10)'),
                            color: '#ffb86c', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '4px'
                          }}
                        >
                          {isPublished ? <RefreshCw size={12} /> : <Upload size={12} />}
                          {isPublished ? 'Aggiorna su HF' : 'Pubblica HF'}
                        </button>

                        {/* Convert Safetensors */}
                        {!isGguf && (
                          <button
                            onClick={() => handleTriggerConvertForModel(m.model_id || m.filename)}
                            title="Configura e converti questo modello in GGUF quantizzato"
                            style={{
                              padding: '6px 10px', borderRadius: '8px',
                              border: '1px solid rgba(16, 185, 129, 0.35)', background: 'rgba(16, 185, 129, 0.10)',
                              color: '#10b981', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '4px'
                            }}
                          >
                            <Package size={12} /> Converti
                          </button>
                        )}

                        {/* Rename */}
                        <button
                          onClick={() => handleRenameModel(m)}
                          disabled={renamingPath === (m.path || m.filename)}
                          title="Rinomina il modello sul disco"
                          style={{
                            padding: '6px 8px', borderRadius: '8px',
                            border: subBorder, background: subBg,
                            color: textMuted, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '3px',
                            opacity: renamingPath === (m.path || m.filename) ? 0.6 : 1
                          }}
                        >
                          <Pencil size={12} />
                        </button>

                        {/* Delete */}
                        <button
                          onClick={() => handleDeleteModel(m)}
                          disabled={deletingPath === (m.path || m.filename)}
                          title="Elimina definitivamente dallo storage locale"
                          style={{
                            padding: '6px 8px', borderRadius: '8px',
                            border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)',
                            color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '3px',
                            opacity: deletingPath === (m.path || m.filename) ? 0.6 : 1
                          }}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    {/* Repository collegato su Hugging Face */}
                    {isPublished && (
                      <div style={{
                        padding: '8px 12px', borderRadius: '10px',
                        background: isLight ? 'rgba(255, 184, 108, 0.08)' : 'rgba(255, 184, 108, 0.06)',
                        border: '1px solid rgba(255, 184, 108, 0.25)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        gap: '8px', flexWrap: 'wrap'
                      }}>
                        <span style={{ fontSize: '0.70rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <ExternalLink size={12} color="#ffb86c" />
                          Repository Hugging Face:
                          <a href={m.publication.url} target="_blank" rel="noreferrer"
                            style={{ color: '#ffb86c', fontWeight: 800, textDecoration: 'none' }}>
                            {m.publication.repo_id}
                          </a>
                          {m.publication.publish_count > 1 ? ` · ${m.publication.publish_count} sincronizzazioni` : ''}
                        </span>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            onClick={() => handleUpdateCard(m)}
                            disabled={updatingCard === (m.path || m.filename)}
                            title="Riscrive solo la scheda (paper, note, benchmark) senza ricaricare i pesi"
                            style={{
                              padding: '3px 9px', borderRadius: '6px',
                              border: '1px solid rgba(255,184,108,0.4)', background: 'transparent',
                              color: '#ffb86c', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer'
                            }}
                          >
                            {updatingCard === (m.path || m.filename) ? 'Aggiorno...' : 'Aggiorna scheda'}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Benchmark Showcase Banner */}
                    {hasBenchmark ? (
                      <div style={{
                        padding: '10px 14px', borderRadius: '12px',
                        background: isLight ? 'rgba(255, 184, 108, 0.08)' : 'linear-gradient(135deg, rgba(255, 184, 108, 0.08) 0%, rgba(16, 185, 129, 0.06) 100%)',
                        border: '1px solid rgba(255, 184, 108, 0.30)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '32px', height: '32px', borderRadius: '8px',
                            background: 'rgba(255, 184, 108, 0.18)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}>
                            <Trophy size={16} color="#ffb86c" />
                          </div>

                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '0.80rem', fontWeight: 800, color: textPrimary }}>
                                Benchmark Ufficiale Training Lab:
                              </span>
                              <span style={{
                                fontSize: '0.82rem', fontWeight: 900, color: bmScoreColor,
                                padding: '1px 8px', borderRadius: '6px',
                                background: `${bmScoreColor}18`, border: `1px solid ${bmScoreColor}44`
                              }}>
                                🏆 {bmScore}% Pass
                              </span>
                            </div>

                            <div style={{ fontSize: '0.66rem', color: textMuted, marginTop: '2px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span>📊 Suite: <b>{bm.suite_name}</b></span>
                              <span>•</span>
                              <span>⚡ Velocità: <b>{bm.tokens_per_sec > 0 ? `${bm.tokens_per_sec} tok/s` : '—'}</b></span>
                              {bm.last_run_at && (
                                <>
                                  <span>•</span>
                                  <span>⏱️ Testato: {bm.last_run_at}</span>
                                </>
                              )}
                              {bm.tests_total > 0 && (
                                <>
                                  <span>•</span>
                                  <span>✅ <b>{bm.tests_passed}/{bm.tests_total}</b> superati</span>
                                </>
                              )}
                            </div>

                            {bm.suites && Object.keys(bm.suites).length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
                                {Object.entries(bm.suites).map(([sid, st]) => {
                                  const quota = st.total ? Math.round((st.passed / st.total) * 100) : 0;
                                  const colore = quota >= 70 ? '#10b981' : quota >= 40 ? '#ffb86c' : '#ef4444';
                                  return (
                                    <span key={sid} title={`${st.passed} superati su ${st.total}`}
                                      style={{
                                        fontSize: '0.58rem', fontWeight: 700, padding: '1px 6px',
                                        borderRadius: '5px', whiteSpace: 'nowrap',
                                        background: `${colore}14`, border: `1px solid ${colore}40`, color: colore,
                                      }}>
                                      {sid} {quota}%
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{
                            fontSize: '0.62rem', fontWeight: 800, color: '#10b981',
                            padding: '3px 8px', borderRadius: '5px',
                            background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)'
                          }}>
                            ✓ VALUTAZIONE REGISTRATA
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div style={{
                        padding: '8px 12px', borderRadius: '10px',
                        background: subBg, border: subBorder,
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'
                      }}>
                        <span style={{ fontSize: '0.68rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <Award size={12} color={textMuted} /> Nessun benchmark registrato per questo modello.
                        </span>
                        <span style={{ fontSize: '0.64rem', color: '#ffb86c', fontWeight: 700 }}>
                          Eseguibile dalla scheda Training Lab
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: LATERAL DOWNLOAD & ACTIVITY LOG SIDEBAR */}
        <DownloadLogSidebar
          isLight={isLight}
          downloads={activeDownloads}
          onDownloadsChanged={onDownloadsChanged}
          addToast={addToast}
          onDeployRequested={onDeployRequested}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />
      </div>

      {/* MODALS */}
      {publishingModel && (
        <HfPublishModal
          model={publishingModel}
          onClose={() => {
            setPublishingModel(null);
            fetchLocalModels();
          }}
          isLight={isLight}
          addToast={addToast}
        />
      )}

      {inferenceTestingModel && (
        <InferenceTestModal
          model={inferenceTestingModel}
          onClose={() => setInferenceTestingModel(null)}
          isLight={isLight}
          addToast={addToast}
        />
      )}
    </div>
  );
}
