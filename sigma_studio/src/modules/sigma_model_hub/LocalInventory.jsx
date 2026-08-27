import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power, Pencil,
  Activity, Upload, Download, Pause, Play, X, AlertTriangle, Package,
  RotateCcw, Search, ChevronDown, ChevronUp, Sliders, Layers, Sparkles,
  Loader, Check, Trophy, Award, BarChart2, Gauge, Clock, Cpu, ExternalLink
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';

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

  // Search & Filter state for local inventory
  const [searchQuery, setSearchQuery] = useState('');
  const [renamingPath, setRenamingPath] = useState(null);
  const [speedTesting, setSpeedTesting] = useState(null);
  const [speedResult, setSpeedResult] = useState({});
  const [updatingCard, setUpdatingCard] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [formatFilter, setFormatFilter] = useState('all'); // 'all' | 'gguf' | 'safetensors' | 'benchmarked'

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

  // Rinominare non e' cosmetica: il nome della cartella e' l'identificativo con
  // cui il motore lo carica, con cui il Training Lab lo cerca nei referti e con
  // cui viene proposto su Hugging Face. Per questo la rinomina passa dal
  // backend, che scarica il modello dal motore prima di toccarne i file.
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

  // Una misura di velocita' senza la risposta che l'ha prodotta si puo' leggere
  // come si vuole. Qui vanno insieme: i due tempi che il motore cronometra —
  // lettura del prompt e generazione — e il testo che il modello ha davvero
  // scritto su questa macchina.
  // Il testo del paper, una correzione, un benchmark rifatto: sono modifiche al
  // README, non ai pesi. Ricaricare gigabyte per cambiare una frase è tempo e
  // banda spesi per niente, e su un repository con cronologia aggiunge un
  // commit enorme che non contiene nessuna modifica ai pesi.
  // Tutto cio' che e' stato pubblicato prima che esistesse il registro e' su
  // Hugging Face senza che niente lo colleghi al modello locale: "aggiorna la
  // scheda" non trova un repository, e la pubblicazione successiva ne creerebbe
  // uno nuovo. Qui si cercano e si collegano, ma solo dopo conferma: un
  // collegamento sbagliato manderebbe un aggiornamento sul repository di
  // qualcun altro.
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

  const handleSpeedTest = async (model) => {
    const chiave = model.path || model.filename;
    setSpeedTesting(chiave);
    setSpeedResult(r => ({ ...r, [chiave]: null }));
    try {
      const res = await fetch('/api/models/speedtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model.model_id || model.filename, max_tokens: 96 })
      });
      const json = await res.json();
      if (json.success) {
        setSpeedResult(r => ({ ...r, [chiave]: json }));
      } else if (addToast) {
        addToast(`${json.error || 'Prova non riuscita'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setSpeedTesting(null);
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

  const handlePauseDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⏸️ Download messo in pausa.', 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
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
        if (addToast) addToast('▶️ Ripresa download con auto-resume da disco.', 'success');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
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
        if (addToast) addToast('🛑 Download annullato.', 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleRemoveDownloadTask = async (taskId, deleteFiles = false) => {
    try {
      const res = await fetch('/api/models/hf/download/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, delete_files: deleteFiles })
      });
      const json = await res.json();
      if (json.success) {
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearCompletedDownloads = async () => {
    try {
      const res = await fetch('/api/models/hf/downloads/clear', { method: 'POST' });
      const json = await res.json();
      if (json.success && onDownloadsChanged) {
        onDownloadsChanged();
        if (addToast) addToast('🧹 Notifiche download completate ripulite.', 'info');
      }
    } catch (e) {
      console.error(e);
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

  const ggufCount = ggufModels.length;
  const safetensorsCount = safetensorsModels.length;
  const benchmarkedCount = benchmarkedModels.length;

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

    if (formatFilter === 'gguf' && !isGguf) return false;
    if (formatFilter === 'safetensors' && !isSafetensors) return false;
    if (formatFilter === 'benchmarked' && !hasBenchmark) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (m.filename || '').toLowerCase().includes(q);
      const matchId = (m.model_id || '').toLowerCase().includes(q);
      const matchDisp = (m.display_name || '').toLowerCase().includes(q);
      const matchQuant = (m.quantization || '').toLowerCase().includes(q);
      const matchArch = (m.architecture || '').toLowerCase().includes(q);
      const matchSuite = (m.benchmark_summary?.suite_name || '').toLowerCase().includes(q);
      return matchName || matchId || matchDisp || matchQuant || matchArch || matchSuite;
    }
    return true;
  });

  const selectedConvertModelObj = converterModels.find(m => m.name === selectedConvertModel);
  const convertEstimate = selectedConvertModelObj?.estimated_outputs?.[selectedQuant];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

      {/* 1. TOP STORAGE & ENGINE DASHBOARD */}
      <div style={{
        padding: '20px 24px', borderRadius: '18px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf5ec 100%)'
          : 'linear-gradient(135deg, rgba(14, 18, 28, 0.95) 0%, rgba(24, 30, 48, 0.85) 100%)',
        border: isLight ? '1.5px solid rgba(190, 160, 110, 0.35)' : '1.5px solid rgba(0, 210, 255, 0.20)',
        boxShadow: isLight ? '0 4px 20px rgba(0,0,0,0.05)' : '0 8px 32px rgba(0,0,0,0.45)',
        display: 'flex', flexDirection: 'column', gap: '16px',
        backdropFilter: 'blur(16px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(188, 140, 255, 0.2))',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <HardDrive size={18} color="#00d2ff" />
              </div>
              <h2 style={{ margin: 0, fontSize: '1.18rem', fontWeight: 800, color: textPrimary, letterSpacing: '-0.02em' }}>
                Modelli Locali & Storage
              </h2>
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '3px' }}>
              Gestisci i modelli presenti su disco, monitora i benchmark e converti checkpoint Safetensors in GGUF.
            </div>
            <button
              onClick={handleDiscoverRepos}
              disabled={discovering}
              title="Cerca sul tuo account Hugging Face i repository che corrispondono ai modelli locali e li collega, così da poterli aggiornare"
              style={{
                marginTop: '8px', padding: '5px 11px', borderRadius: '7px',
                border: '1px solid rgba(255,184,108,0.35)',
                background: 'rgba(255,184,108,0.08)', color: '#ffb86c',
                fontSize: '0.68rem', fontWeight: 700, cursor: discovering ? 'wait' : 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: '5px'
              }}
            >
              <ExternalLink size={11} />
              {discovering ? 'Cerco su Hugging Face...' : 'Collega repository già pubblicati'}
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={handleUnloadModel}
              disabled={unloading}
              title="Scarica il modello attivo da VRAM/RAM e libera le risorse"
              style={{
                padding: '7px 14px', borderRadius: '10px',
                border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px',
                transition: 'all 0.15s ease'
              }}
            >
              <Power size={13} /> {unloading ? 'Rilascio...' : 'Rilascia VRAM'}
            </button>

            <button
              onClick={() => {
                fetchLocalModels();
                fetchConverterInfo();
                if (onDownloadsChanged) onDownloadsChanged();
              }}
              title="Ricarica elenco modelli e stato"
              style={{
                padding: '7px 14px', borderRadius: '10px',
                border: subBorder, background: subBg,
                color: textPrimary, fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              <RefreshCw size={13} /> Aggiorna
            </button>
          </div>
        </div>

        {/* Storage Metric Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <div style={{ padding: '12px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Cpu size={12} color="#00d2ff" /> MODELLI TOTALI
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: textPrimary, marginTop: '3px' }}>
              {totalModelsCount} <span style={{ fontSize: '0.72rem', color: textMuted, fontWeight: 600 }}>su disco</span>
            </div>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Layers size={12} color="#10b981" /> FORMATI SU DISCO
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 800, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ color: '#10b981' }}>⚡ {ggufCount} GGUF</span>
              <span style={{ color: textMuted }}>•</span>
              <span style={{ color: '#00d2ff' }}>📦 {safetensorsCount} Safetensors</span>
            </div>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Trophy size={12} color="#ffb86c" /> BENCHMARK ESEGUITI
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#ffb86c', marginTop: '3px' }}>
              {benchmarkedCount} <span style={{ fontSize: '0.72rem', color: textMuted, fontWeight: 600 }}>modelli valutati</span>
            </div>
          </div>

          <div style={{ padding: '12px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <HardDrive size={12} color="#bc8cff" /> SPAZIO OCCUPATO
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#bc8cff', marginTop: '3px' }}>
              {totalStorageGb} <span style={{ fontSize: '0.72rem', color: textMuted, fontWeight: 600 }}>GB totali</span>
            </div>
          </div>
        </div>

        {/* Visual Storage Distribution Bar */}
        {totalStorageGb > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '2px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>
              <span style={{ color: '#10b981' }}>⚡ GGUF: {ggufStorageGb.toFixed(1)} GB ({ggufPct}%)</span>
              <span style={{ color: '#00d2ff' }}>📦 Safetensors: {safetensorsStorageGb.toFixed(1)} GB ({safePct}%)</span>
            </div>
            <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden', display: 'flex' }}>
              <div style={{ width: `${ggufPct}%`, height: '100%', background: '#10b981', transition: 'width 0.3s ease' }} title={`GGUF: ${ggufStorageGb.toFixed(1)} GB`} />
              <div style={{ width: `${safePct}%`, height: '100%', background: '#00d2ff', transition: 'width 0.3s ease' }} title={`Safetensors: ${safetensorsStorageGb.toFixed(1)} GB`} />
            </div>
          </div>
        )}
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
                          title="Metti in pausa il download"
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
                          title="Riprendi il download dai byte già scaricati"
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
          display: 'flex', flexDirection: 'column', gap: '12px'
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
            <Package size={16} color="#10b981" />
            <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
              Convertitore & Quantizzazione GGUF (llama.cpp)
            </span>
            <span style={{
              fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
              background: tooling?.ready ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: tooling?.ready ? '#10b981' : '#ef4444', fontWeight: 800
            }}>
              {tooling?.ready ? '⚡ STRUMENTI PRONTI' : '⚠️ STRUMENTI NON CONFIGURATI'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: textMuted }}>
            <span style={{ fontSize: '0.70rem' }}>{showConverter ? 'Comprimi' : 'Espandi'}</span>
            {showConverter ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </div>

        {showConverter && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', paddingTop: '8px', borderTop: subBorder }}>
            {converterError && (
              <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', fontSize: '0.74rem' }}>
                {converterError}
              </div>
            )}

            {/* Selection Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.68rem', fontWeight: 800, color: textMuted, marginBottom: '4px', textTransform: 'uppercase' }}>
                  Modello Safetensors di Partenza
                </label>
                <select
                  value={selectedConvertModel}
                  onChange={e => setSelectedConvertModel(e.target.value)}
                  disabled={convertingBusy || !converterModels.length}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '8px',
                    background: inputBg, border: subBorder, color: textPrimary,
                    fontSize: '0.76rem', fontWeight: 700, outline: 'none'
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
                <label style={{ display: 'block', fontSize: '0.68rem', fontWeight: 800, color: textMuted, marginBottom: '4px', textTransform: 'uppercase' }}>
                  Quantizzazione Target
                </label>
                <select
                  value={selectedQuant}
                  onChange={e => setSelectedQuant(e.target.value)}
                  disabled={convertingBusy}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '8px',
                    background: inputBg, border: subBorder, color: textPrimary,
                    fontSize: '0.76rem', fontWeight: 700, outline: 'none'
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

            {/* Convert Summary & Action */}
            {selectedConvertModelObj && (
              <div style={{
                padding: '12px 14px', borderRadius: '10px',
                background: subBg, border: subBorder,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px'
              }}>
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary }}>
                    {selectedConvertModelObj.name} • Architettura: {selectedConvertModelObj.architecture || 'Auto'} ({selectedConvertModelObj.num_layers ? `${selectedConvertModelObj.num_layers} layers` : 'Standard'})
                  </div>
                  <div style={{ fontSize: '0.70rem', color: '#10b981', marginTop: '2px', fontWeight: 600 }}>
                    Dimensione stimata GGUF: ~{convertEstimate?.size_gb || '?'} GB (da {selectedConvertModelObj.size_gb} GB iniziali)
                  </div>
                </div>

                <button
                  onClick={handleStartConversion}
                  disabled={convertingBusy || !tooling?.ready || !!activeConvertJob}
                  style={{
                    padding: '8px 16px', borderRadius: '8px',
                    border: 'none', background: 'linear-gradient(135deg, #10b981, #059669)',
                    color: '#ffffff', fontSize: '0.76rem', fontWeight: 800,
                    cursor: (convertingBusy || !tooling?.ready || !!activeConvertJob) ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: '5px',
                    boxShadow: '0 0 12px rgba(16, 185, 129, 0.25)'
                  }}
                >
                  {activeConvertJob ? <Activity className="mh-spin" size={13} /> : <Play size={13} />}
                  {activeConvertJob ? 'Conversione in corso...' : 'Avvia Conversione'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 4. LOCAL MODELS CATALOG & INVENTORY */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Search and Format Filter Bar */}
        <div style={{
          padding: '14px 18px', borderRadius: '16px',
          background: cardBg, border: cardBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px',
          backdropFilter: 'blur(12px)'
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            background: subBg, border: subBorder, borderRadius: '12px',
            padding: '7px 14px', flex: 1, minWidth: '240px'
          }}>
            <Search size={15} color="#00d2ff" />
            <input
              type="text"
              placeholder="Cerca modello per nome, quantizzazione, architettura..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent', border: 'none', outline: 'none',
                color: textPrimary, fontSize: '0.80rem', width: '100%'
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            {[
              { id: 'all', label: `Tutti (${totalModelsCount})`, color: '#00d2ff' },
              { id: 'gguf', label: `⚡ GGUF (${ggufCount})`, color: '#10b981' },
              { id: 'safetensors', label: `📦 Safetensors (${safetensorsCount})`, color: '#38bdf8' },
              { id: 'benchmarked', label: `🏆 Valutati (${benchmarkedCount})`, color: '#ffb86c' },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setFormatFilter(f.id)}
                style={{
                  padding: '6px 14px', borderRadius: '10px',
                  border: formatFilter === f.id ? `1.5px solid ${f.color}` : subBorder,
                  background: formatFilter === f.id ? (isLight ? '#fff' : 'rgba(255, 255, 255, 0.08)') : subBg,
                  color: formatFilter === f.id ? f.color : textMuted,
                  fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: formatFilter === f.id ? `0 0 12px ${f.color}22` : 'none'
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
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

              return (
                <div
                  key={idx}
                  style={{
                    padding: '16px 20px', borderRadius: '16px',
                    background: m.is_active_in_engine
                      ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.10) 0%, rgba(15, 18, 28, 0.9) 100%)')
                      : cardBg,
                    border: m.is_active_in_engine ? '1.5px solid #00d2ff' : cardBorder,
                    boxShadow: m.is_active_in_engine ? '0 0 20px rgba(0, 210, 255, 0.15)' : 'none',
                    display: 'flex', flexDirection: 'column', gap: '12px',
                    transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                  }}
                >
                  {/* Top Bar: Title & Status Badges */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.94rem', fontWeight: 900, color: textPrimary, wordBreak: 'break-all', letterSpacing: '-0.01em' }}>
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
                            boxShadow: '0 0 10px rgba(0, 210, 255, 0.3)'
                          }}>
                            ⚡ CARICATO IN SIGMAENGINE
                          </span>
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
                        <Zap size={13} /> {m.is_active_in_engine ? 'Rialloca' : '⚡ Avvia in SigmaEngine'}
                      </button>

                      {/* Convert Safetensors */}
                      {!isGguf && (
                        <button
                          onClick={() => handleTriggerConvertForModel(m.model_id || m.filename)}
                          title="Configura e converti questo modello in GGUF quantizzato"
                          style={{
                            padding: '6px 12px', borderRadius: '8px',
                            border: '1px solid rgba(16, 185, 129, 0.35)', background: 'rgba(16, 185, 129, 0.10)',
                            color: '#10b981', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '4px'
                          }}
                        >
                          <Package size={13} /> Converti GGUF
                        </button>
                      )}

                      {/* Publish to HF */}
                      <button
                        onClick={() => setPublishingModel(m)}
                        title="Pubblica questo modello su Hugging Face Hub"
                        style={{
                          padding: '6px 10px', borderRadius: '8px',
                          border: '1px solid rgba(255, 184, 108, 0.35)',
                          background: isLight ? 'rgba(255, 184, 108, 0.12)' : 'rgba(255, 184, 108, 0.10)',
                          color: '#ffb86c', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px'
                        }}
                      >
                        <Upload size={13} /> Pubblica HF
                      </button>

                      {/* Prova di inferenza */}
                      <button
                        onClick={() => handleSpeedTest(m)}
                        disabled={speedTesting === (m.path || m.filename)}
                        title="Genera una risposta vera e misura la velocità su questo hardware"
                        style={{
                          padding: '6px 10px', borderRadius: '8px',
                          border: '1px solid rgba(0,210,255,0.35)',
                          background: 'rgba(0,210,255,0.10)',
                          color: '#00d2ff', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px',
                          opacity: speedTesting === (m.path || m.filename) ? 0.6 : 1
                        }}
                      >
                        <Gauge size={13} />
                        {speedTesting === (m.path || m.filename) ? 'Misuro...' : 'Prova inferenza'}
                      </button>

                      {/* Rename */}
                      <button
                        onClick={() => handleRenameModel(m)}
                        disabled={renamingPath === (m.path || m.filename)}
                        title="Rinomina il modello sul disco"
                        style={{
                          padding: '6px 10px', borderRadius: '8px',
                          border: isLight ? '1px solid rgba(148,163,184,0.35)' : '1px solid rgba(148,163,184,0.28)',
                          background: isLight ? 'rgba(148,163,184,0.10)' : 'rgba(148,163,184,0.10)',
                          color: textMuted, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px',
                          opacity: renamingPath === (m.path || m.filename) ? 0.6 : 1
                        }}
                      >
                        <Pencil size={13} />
                        {renamingPath === (m.path || m.filename) ? '...' : 'Rinomina'}
                      </button>

                      {/* Delete */}
                      <button
                        onClick={() => handleDeleteModel(m)}
                        disabled={deletingPath === (m.path || m.filename)}
                        title="Elimina definitivamente dallo storage locale"
                        style={{
                          padding: '6px 10px', borderRadius: '8px',
                          border: isLight ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid rgba(239, 68, 68, 0.3)',
                          background: isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.1)',
                          color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px',
                          opacity: deletingPath === (m.path || m.filename) ? 0.6 : 1
                        }}
                      >
                        <Trash2 size={13} />
                        {deletingPath === (m.path || m.filename) ? '...' : 'Elimina'}
                      </button>
                    </div>
                  </div>

                  {/* Esito della prova di inferenza: i due tempi che il motore
                      cronometra, e la risposta che li ha prodotti. Il numero da
                      solo non dice a cosa si riferisce. */}
                  {speedResult[m.path || m.filename] && (() => {
                    const sr = speedResult[m.path || m.filename];
                    return (
                      <div style={{
                        padding: '10px 14px', borderRadius: '12px', marginTop: '8px',
                        background: isLight ? 'rgba(0,210,255,0.06)' : 'rgba(0,210,255,0.07)',
                        border: '1px solid rgba(0,210,255,0.28)'
                      }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'baseline' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff' }}>
                            {sr.decode_tok_s} tok/s
                          </span>
                          <span style={{ fontSize: '0.66rem', color: textMuted }}>
                            generazione, una risposta alla volta — è quello che si sente in chat
                          </span>
                          <span style={{ fontSize: '0.66rem', color: textMuted }}>
                            • lettura prompt <b>{sr.prefill_tok_s} tok/s</b>
                          </span>
                          <span style={{ fontSize: '0.66rem', color: textMuted }}>
                            • prima parola dopo <b>{sr.ttft_ms} ms</b>
                          </span>
                        </div>
                        <div style={{ fontSize: '0.64rem', color: textMuted, marginTop: '4px' }}>
                          Risposta reale: <b>{sr.answer_tokens} token in {sr.answer_seconds}s</b>
                          {sr.hardware?.device ? ` su ${sr.hardware.device}` : ''}
                          {sr.backend ? ` · ${sr.backend}` : ''}
                        </div>
                        {sr.answer && (
                          <div style={{
                            fontSize: '0.66rem', color: textPrimary, marginTop: '6px',
                            padding: '6px 8px', borderRadius: '8px', background: subBg,
                            maxHeight: '90px', overflow: 'auto', whiteSpace: 'pre-wrap'
                          }}>
                            {sr.answer}
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {/* Repository collegato: senza questo, aggiornare la scheda
                      significava ricordarsi a mano dove si era pubblicato, e
                      sbagliare l'identificativo creava un secondo repository. */}
                  {m.publication?.repo_id && (
                    <div style={{
                      padding: '8px 12px', borderRadius: '10px', marginTop: '8px',
                      background: subBg, border: subBorder,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      gap: '8px', flexWrap: 'wrap'
                    }}>
                      <span style={{ fontSize: '0.68rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <ExternalLink size={12} />
                        Pubblicato su{' '}
                        <a href={m.publication.url} target="_blank" rel="noreferrer"
                          style={{ color: '#ffb86c', fontWeight: 700 }}>
                          {m.publication.repo_id}
                        </a>
                        {m.publication.publish_count > 1 ? ` · ${m.publication.publish_count} pubblicazioni` : ''}
                      </span>
                      <button
                        onClick={() => handleUpdateCard(m)}
                        disabled={updatingCard === (m.path || m.filename)}
                        title="Riscrive solo la scheda (paper, note, benchmark) senza ricaricare i pesi"
                        style={{
                          padding: '4px 10px', borderRadius: '6px',
                          border: '1px solid rgba(255,184,108,0.4)', background: 'transparent',
                          color: '#ffb86c', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer'
                        }}
                      >
                        {updatingCard === (m.path || m.filename) ? 'Aggiorno...' : 'Aggiorna scheda'}
                      </button>
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

                          {/* Un punteggio complessivo da solo non dice quali
                              materie il modello regge e quali no: e' proprio il
                              dettaglio per suite il parametro che serve a
                              scegliere un modello per un compito. */}
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

                          {(bm.dataset_complete === false || bm.completed === false) && (
                            <div style={{ fontSize: '0.6rem', color: '#ffb86c', marginTop: '4px' }}>
                              ⚠️ {bm.completed === false
                                ? 'Valutazione non conclusa: la percentuale copre solo i quesiti eseguiti.'
                                : 'Misurato su una porzione del dataset: non confrontabile con un run sulla suite intera.'}
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
