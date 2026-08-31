import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power, Pencil,
  Activity, Upload, Download, Pause, Play, X, AlertTriangle, Package,
  RotateCcw, Search, ChevronDown, ChevronUp, Sliders, Layers, Sparkles,
  Loader, Check, Trophy, Award, BarChart2, Gauge, Clock, Cpu, ExternalLink,
  PanelRightClose, PanelRightOpen, ArrowRight, ShieldCheck, Filter,
  Code, Brain, Eye, Tag, User, Dna, Boxes
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';
import InferenceTestModal from './InferenceTestModal.jsx';
import DownloadLogSidebar from './DownloadLogSidebar.jsx';

// ==============================================================================
// LocalInventory — Gestione Modelli Locali & Storage Sigma Hub
// Supporta: Filtri per Famiglia, Categoria, Publisher (con riconoscimento Sigmanih)
// e layout grafico moderno per specifiche, benchmark e sincronizzazione HF.
// ==============================================================================

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
  const [resumingModelId, setResumingModelId] = useState(null);

  // Search, Filters & Sorting state
  const [searchQuery, setSearchQuery] = useState('');
  const [familyFilter, setFamilyFilter] = useState('all');       // 'all' | 'Gemma' | 'Qwen' | 'Llama' | 'DeepSeek' | 'Mistral' | 'Phi' | 'GLM' | 'Altro'
  const [categoryFilter, setCategoryFilter] = useState('all');   // 'all' | 'sigmanih' | 'reasoning' | 'code' | 'vision' | 'moe' | 'llm' | 'gguf' | 'safetensors' | 'benchmarked' | 'published'
  const [publisherFilter, setPublisherFilter] = useState('all'); // 'all' | 'sigmanih' | 'google' | 'qwen' | 'meta' | 'deepseek' | 'mistralai' | 'microsoft'
  const [sortBy, setSortBy] = useState('recent');                // 'recent' | 'size_desc' | 'size_asc' | 'vram_desc' | 'benchmark' | 'name'

  const [renamingPath, setRenamingPath] = useState(null);
  const [updatingCard, setUpdatingCard] = useState(null);
  const [discovering, setDiscovering] = useState(false);
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

  const handleDeleteModel = async (model) => {
    const label = model.clean_name || model.filename;
    if (!window.confirm(`Sei sicuro di voler eliminare definitivamente "${label}" dallo storage locale?`)) {
      return;
    }
    setDeletingPath(model.path || model.filename);
    try {
      const res = await fetch('/api/models/local/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          filename: model.filename,
          model_id: model.model_id
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🗑️ ${json.message}`, 'info');
        fetchLocalModels();
        fetchConverterInfo();
      } else {
        if (addToast) addToast(`❌ ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setDeletingPath(null);
    }
  };

  const handleResumeDownload = async (model) => {
    const rawTarget = model.model_id || model.filename || '';
    const cleanRepoId = rawTarget.replace(/--/g, '/');
    const mid = model.publication?.repo_id || cleanRepoId;
    const isSingleFile = !model.is_repo_folder;
    const fname = isSingleFile ? (model.filename?.split('/').pop() || model.filename) : undefined;

    setResumingModelId(rawTarget);
    if (addToast) addToast(`📥 Ripresa download per "${mid}" in corso...`, 'info');

    try {
      const res = await fetch('/api/models/hf/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: mid,
          filename: fname,
          resume: true
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`⚡ Download avviato in background per ${mid}`, 'success');
        if (onDownloadsChanged) onDownloadsChanged();
      } else {
        if (addToast) addToast(`❌ Errore ripresa download: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setResumingModelId(null);
    }
  };

  const handleForgetPublication = async (model) => {
    if (!window.confirm(`Vuoi scollegare questo modello locale dal repository Hugging Face "${model.publication?.repo_id}"?\n\nIl repository su Hugging Face resterà intatto.`)) {
      return;
    }
    try {
      const res = await fetch('/api/models/publication/forget', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('🔗 Modello scollegato da Hugging Face.', 'info');
        fetchLocalModels();
      } else {
        if (addToast) addToast(`❌ ${json.error || 'Impossibile scollegare.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleDiscoverRepos = async () => {
    setDiscovering(true);
    try {
      const res = await fetch('/api/models/publications/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const json = await res.json();
      if (res.ok && json.success) {
        const c = json.discovered_count || 0;
        if (addToast) {
          if (c > 0) {
            addToast(`✨ Trovati e collegati ${c} repository Hugging Face!`, 'success');
          } else {
            addToast('Nessun nuovo repository corrispondente trovato su Hugging Face.', 'info');
          }
        }
        fetchLocalModels();
      } else if (addToast) {
        addToast(`❌ ${json.error || 'Ricerca non riuscita.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setDiscovering(false);
    }
  };

  const handleAttachHfRepo = async (model) => {
    const attuale = model.publication?.repo_id || '';
    const repo = window.prompt(
      'Inserisci il repository Hugging Face a cui collegare questo modello locale (es: username/nome-modello):\n\n'
      + 'Verrà usato per aggiornare la scheda o caricare nuove quantizzazioni.',
      attuale
    );
    if (repo === null) return;
    if (!repo.trim() || !repo.includes('/')) {
      if (addToast) addToast('⚠️ Inserisci un repository valido nel formato "username/nome-modello".', 'warning');
      return;
    }
    try {
      const res = await fetch('/api/models/publication/attach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename,
          repo_id: repo.trim()
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(`🔗 Collegato a ${json.repo_id}`, 'success');
        fetchLocalModels();
      } else if (addToast) {
        addToast(`❌ ${json.error || 'Collegamento fallito.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleUpdateCard = async (model) => {
    const repoId = model.publication?.repo_id;
    if (!repoId) return;
    setUpdatingCard(model.path || model.filename);
    try {
      const res = await fetch('/api/models/hf/publish/card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename,
          repo_id: repoId
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(`📄 Scheda del modello aggiornata su Hugging Face (${repoId})!`, 'success');
      } else if (addToast) {
        addToast(`❌ Aggiornamento scheda non riuscito: ${json.error || 'errore sconosciuto'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setUpdatingCard(null);
    }
  };

  const handleRenameHfRepoFromInventory = async (model) => {
    const vecchioRepo = model.publication?.repo_id;
    if (!vecchioRepo) return;
    const nuovoNome = window.prompt(
      `Rinomina il repository "${vecchioRepo}" su Hugging Face.\n\n`
      + 'Puoi inserire solo il nuovo nome (il tuo username resta invariato) '
      + 'oppure "nuovo-username/nuovo-nome".',
      vecchioRepo.split('/')[1] || vecchioRepo
    );
    if (nuovoNome === null) return;
    if (!nuovoNome.trim()) return;

    try {
      const res = await fetch('/api/models/hf/repo/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_id: vecchioRepo,
          new_name: nuovoNome.trim(),
          model_path: model.path
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(`✏️ Repository rinominato in "${json.new_repo_id}"!`, 'success');
        fetchLocalModels();
      } else if (addToast) {
        addToast(`❌ Rinomina su HF non riuscita: ${json.error || 'errore'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
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

  // Helper per estrazione precisa di attributi, autore/publisher e famiglia
  const getModelInfo = (m) => {
    const isGguf = m.format_tag === 'GGUF' || m.filename?.toLowerCase().endsWith('.gguf');
    const isSafetensors = m.format_tag === 'SAFETENSORS' || m.filename?.toLowerCase().endsWith('.safetensors') || (m.is_repo_folder && !isGguf);
    const repoId = m.publication?.repo_id || '';
    const rawAuthor = m.publisher || m.author || '';
    const rawName = m.clean_name || m.display_name || m.filename || '';

    // Riconoscimento speciale per Sigmanih
    const isSigmanih = Boolean(
      repoId.toLowerCase().startsWith('sigmanih/') ||
      rawAuthor.toLowerCase() === 'sigmanih' ||
      rawName.toLowerCase().startsWith('sigmanih') ||
      rawName.toLowerCase().startsWith('sigma-') ||
      m.is_sigmanih
    );

    const publisher = isSigmanih ? 'sigmanih' : (repoId ? repoId.split('/')[0] : (rawAuthor || 'Altro'));
    
    // Riconoscimento famiglia architetturale
    let family = m.family || 'Altro';
    const combinedText = `${rawName} ${m.architecture || ''} ${publisher}`.toLowerCase();
    if (combinedText.includes('gemma')) family = 'Gemma';
    else if (combinedText.includes('qwen')) family = 'Qwen';
    else if (combinedText.includes('llama') || combinedText.includes('meta')) family = 'Llama';
    else if (combinedText.includes('deepseek')) family = 'DeepSeek';
    else if (combinedText.includes('mistral') || combinedText.includes('mixtral') || combinedText.includes('codestral')) family = 'Mistral';
    else if (combinedText.includes('phi')) family = 'Phi';
    else if (combinedText.includes('glm') || combinedText.includes('chatglm') || combinedText.includes('zai')) family = 'GLM';
    else if (m.architecture) family = m.architecture.charAt(0).toUpperCase() + m.architecture.slice(1);

    // Categoria
    let category = m.category || 'llm';
    if (isSigmanih) category = 'sigmanih';
    else if (combinedText.includes('r1') || combinedText.includes('reason') || combinedText.includes('think') || combinedText.includes('qwq')) category = 'reasoning';
    else if (combinedText.includes('coder') || combinedText.includes('code') || combinedText.includes('dev')) category = 'code';
    else if (m.is_multimodal || combinedText.includes('vision') || combinedText.includes('vl') || combinedText.includes('clip')) category = 'vision';
    else if (combinedText.includes('moe') || combinedText.includes('expert') || combinedText.includes('8x')) category = 'moe';

    return {
      isGguf,
      isSafetensors,
      isSigmanih,
      publisher,
      family,
      category,
      hasBenchmark: !!m.benchmark_summary?.has_benchmarks,
      isPublished: Boolean(repoId)
    };
  };

  // Stats calculation
  const totalModelsCount = models.length;
  const sigmanihModels = models.filter(m => getModelInfo(m).isSigmanih);
  const ggufModels = models.filter(m => getModelInfo(m).isGguf);
  const safetensorsModels = models.filter(m => getModelInfo(m).isSafetensors);
  const benchmarkedModels = models.filter(m => getModelInfo(m).hasBenchmark);
  const publishedModels = models.filter(m => getModelInfo(m).isPublished);
  const reasoningModels = models.filter(m => getModelInfo(m).category === 'reasoning');
  const codeModels = models.filter(m => getModelInfo(m).category === 'code');
  const visionModels = models.filter(m => getModelInfo(m).category === 'vision');

  const sigmanihCount = sigmanihModels.length;
  const ggufCount = ggufModels.length;
  const safetensorsCount = safetensorsModels.length;
  const benchmarkedCount = benchmarkedModels.length;
  const publishedCount = publishedModels.length;
  const reasoningCount = reasoningModels.length;
  const codeCount = codeModels.length;
  const visionCount = visionModels.length;

  const ggufStorageGb = ggufModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const safetensorsStorageGb = safetensorsModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const totalStorageGb = (ggufStorageGb + safetensorsStorageGb).toFixed(1);

  const ggufPct = totalStorageGb > 0 ? Math.round((ggufStorageGb / totalStorageGb) * 100) : 0;
  const safePct = totalStorageGb > 0 ? Math.round((safetensorsStorageGb / totalStorageGb) * 100) : 0;

  // Lista dinamica delle famiglie e publisher presenti
  const availableFamilies = Array.from(new Set(models.map(m => getModelInfo(m).family).filter(Boolean))).sort();
  const availablePublishers = Array.from(new Set(models.map(m => getModelInfo(m).publisher).filter(Boolean))).sort();

  // Multi-Filter & Search models
  const filteredModels = models.filter(m => {
    const info = getModelInfo(m);

    // 1. Filtro Famiglia
    if (familyFilter !== 'all' && info.family.toLowerCase() !== familyFilter.toLowerCase()) {
      return false;
    }

    // 2. Filtro Publisher / Autore
    if (publisherFilter !== 'all' && info.publisher.toLowerCase() !== publisherFilter.toLowerCase()) {
      return false;
    }

    // 3. Filtro Categoria & Formato
    if (categoryFilter === 'sigmanih' && !info.isSigmanih) return false;
    if (categoryFilter === 'reasoning' && info.category !== 'reasoning') return false;
    if (categoryFilter === 'code' && info.category !== 'code') return false;
    if (categoryFilter === 'vision' && info.category !== 'vision') return false;
    if (categoryFilter === 'moe' && info.category !== 'moe') return false;
    if (categoryFilter === 'gguf' && !info.isGguf) return false;
    if (categoryFilter === 'safetensors' && !info.isSafetensors) return false;
    if (categoryFilter === 'benchmarked' && !info.hasBenchmark) return false;
    if (categoryFilter === 'published' && !info.isPublished) return false;

    // 4. Ricerca testuale
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (m.filename || '').toLowerCase().includes(q);
      const matchId = (m.model_id || '').toLowerCase().includes(q);
      const matchDisp = (m.display_name || '').toLowerCase().includes(q);
      const matchQuant = (m.quantization || '').toLowerCase().includes(q);
      const matchArch = (m.architecture || '').toLowerCase().includes(q);
      const matchFam = (info.family || '').toLowerCase().includes(q);
      const matchPub = (info.publisher || '').toLowerCase().includes(q);
      const matchSuite = (m.benchmark_summary?.suite_name || '').toLowerCase().includes(q);
      const matchRepo = (m.publication?.repo_id || '').toLowerCase().includes(q);
      return matchName || matchId || matchDisp || matchQuant || matchArch || matchFam || matchPub || matchSuite || matchRepo;
    }
    return true;
  });

  // Sorting
  const sortedModels = [...filteredModels].sort((a, b) => {
    if (sortBy === 'recent') {
      return (b.modified_at || '').localeCompare(a.modified_at || '');
    }
    if (sortBy === 'size_desc') {
      return (parseFloat(b.size_gb) || 0) - (parseFloat(a.size_gb) || 0);
    }
    if (sortBy === 'size_asc') {
      return (parseFloat(a.size_gb) || 0) - (parseFloat(b.size_gb) || 0);
    }
    if (sortBy === 'vram_desc') {
      return (parseFloat(b.est_vram_gb) || 0) - (parseFloat(a.est_vram_gb) || 0);
    }
    if (sortBy === 'benchmark') {
      const aPass = a.benchmark_summary?.overall_pass_rate || a.benchmark_summary?.score || 0;
      const bPass = b.benchmark_summary?.overall_pass_rate || b.benchmark_summary?.score || 0;
      return bPass - aPass;
    }
    if (sortBy === 'name') {
      return (a.clean_name || a.filename || '').localeCompare(b.clean_name || b.filename || '');
    }
    return 0;
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
                width: '36px', height: '36px', borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(188, 140, 255, 0.25))',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <HardDrive size={19} color="#00d2ff" />
              </div>
              <h2 style={{ margin: 0, fontSize: '1.24rem', fontWeight: 900, color: textPrimary, letterSpacing: '-0.02em' }}>
                Modelli Locali & Hub Storage
              </h2>
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '3px' }}>
              Gestisci i modelli presenti su disco, seleziona per famiglia e categoria, prova l'inferenza con telemetria tok/s e sincronizza con Hugging Face.
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
          <div style={{ padding: '10px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Cpu size={12} color="#00d2ff" /> MODELLI TOTALI
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: textPrimary, marginTop: '2px' }}>
              {totalModelsCount} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>su disco</span>
            </div>
          </div>

          <div style={{ padding: '10px 14px', borderRadius: '12px', background: 'rgba(255, 184, 108, 0.08)', border: '1px solid rgba(255, 184, 108, 0.25)' }}>
            <div style={{ fontSize: '0.64rem', color: '#ffb86c', fontWeight: 800, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={12} color="#ffb86c" /> SIGMANIH RELEASES
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#ffb86c', marginTop: '2px' }}>
              {sigmanihCount} <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 600 }}>modelli</span>
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

          {/* ADVANCED MULTI-FILTER CONTROL BAR */}
          <div style={{
            padding: '14px 18px', borderRadius: '16px',
            background: cardBg, border: cardBorder,
            display: 'flex', flexDirection: 'column', gap: '12px',
            backdropFilter: 'blur(12px)', boxShadow: '0 4px 16px rgba(0,0,0,0.15)'
          }}>
            {/* Top Row: Search Input + Sorting + Live Counter */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: subBg, border: subBorder, borderRadius: '10px',
                padding: '7px 12px', flex: 1, minWidth: '240px'
              }}>
                <Search size={15} color="#00d2ff" />
                <input
                  type="text"
                  placeholder="Cerca per nome, famiglia (Gemma, Qwen...), categoria o repo HF..."
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
                    <X size={13} />
                  </button>
                )}
              </div>

              {/* Sorting Selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: textMuted, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Sliders size={12} /> Ordina:
                </span>
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value)}
                  style={{
                    padding: '6px 10px', borderRadius: '8px',
                    background: inputBg, border: subBorder, color: textPrimary,
                    fontSize: '0.72rem', fontWeight: 700, outline: 'none', cursor: 'pointer'
                  }}
                >
                  <option value="recent">⏱️ Più Recenti</option>
                  <option value="size_desc">💾 Più Pesanti (GB ↓)</option>
                  <option value="size_asc">💾 Più Leggeri (GB ↑)</option>
                  <option value="vram_desc">⚡ Più VRAM (GB ↓)</option>
                  <option value="benchmark">🏆 Top Benchmark (%)</option>
                  <option value="name">🔤 Nome Alfabetico (A-Z)</option>
                </select>

                <div style={{
                  fontSize: '0.68rem', fontWeight: 800, padding: '4px 9px', borderRadius: '6px',
                  background: 'rgba(0, 210, 255, 0.10)', border: '1px solid rgba(0, 210, 255, 0.25)',
                  color: '#00d2ff'
                }}>
                  {sortedModels.length} / {totalModelsCount} Modelli
                </div>
              </div>
            </div>

            {/* Middle Row: Quick Category Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.66rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginRight: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Tag size={11} /> Categoria:
              </span>
              {[
                { id: 'all', label: `Tutti (${totalModelsCount})`, color: '#00d2ff' },
                { id: 'sigmanih', label: `✨ Sigmanih (${sigmanihCount})`, color: '#ffb86c', isSpecial: true },
                { id: 'reasoning', label: `🧠 Reasoning (${reasoningCount})`, color: '#f43f5e' },
                { id: 'code', label: `💻 Coding (${codeCount})`, color: '#38bdf8' },
                { id: 'vision', label: `👁️ Vision (${visionCount})`, color: '#a855f7' },
                { id: 'gguf', label: `⚡ GGUF (${ggufCount})`, color: '#10b981' },
                { id: 'safetensors', label: `📦 Safetensors (${safetensorsCount})`, color: '#00d2ff' },
                { id: 'benchmarked', label: `🏆 Valutati (${benchmarkedCount})`, color: '#ffb86c' },
                { id: 'published', label: `🤗 Pubblicati (${publishedCount})`, color: '#ff79c6' },
              ].map(f => {
                const active = categoryFilter === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => setCategoryFilter(f.id)}
                    style={{
                      padding: '5px 10px', borderRadius: '8px',
                      border: active
                        ? (f.isSpecial ? '1.5px solid #ffb86c' : `1.5px solid ${f.color}`)
                        : subBorder,
                      background: active
                        ? (f.isSpecial ? 'linear-gradient(135deg, rgba(255, 184, 108, 0.25), rgba(0, 210, 255, 0.15))' : `${f.color}18`)
                        : subBg,
                      color: active ? (f.isSpecial ? '#ffb86c' : f.color) : textMuted,
                      fontSize: '0.70rem', fontWeight: active ? 900 : 700, cursor: 'pointer',
                      boxShadow: active && f.isSpecial ? '0 0 10px rgba(255, 184, 108, 0.35)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>

            {/* Bottom Row: Model Family & Publisher Filter Selectors */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', paddingTop: '8px', borderTop: subBorder }}>
              {/* Family Selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#c084fc', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Dna size={12} /> Famiglia Modello:
                </span>
                <select
                  value={familyFilter}
                  onChange={e => setFamilyFilter(e.target.value)}
                  style={{
                    padding: '5px 10px', borderRadius: '7px',
                    background: inputBg, border: familyFilter !== 'all' ? '1.5px solid #c084fc' : subBorder,
                    color: familyFilter !== 'all' ? '#c084fc' : textPrimary,
                    fontSize: '0.72rem', fontWeight: 800, outline: 'none', cursor: 'pointer'
                  }}
                >
                  <option value="all">🧬 Tutte le Famiglie ({totalModelsCount})</option>
                  {availableFamilies.map(fam => {
                    const cnt = models.filter(m => getModelInfo(m).family.toLowerCase() === fam.toLowerCase()).length;
                    return (
                      <option key={fam} value={fam}>
                        {fam} ({cnt})
                      </option>
                    );
                  })}
                </select>
              </div>

              {/* Publisher Selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <User size={12} /> Rilasciato da / Publisher:
                </span>
                <select
                  value={publisherFilter}
                  onChange={e => setPublisherFilter(e.target.value)}
                  style={{
                    padding: '5px 10px', borderRadius: '7px',
                    background: inputBg, border: publisherFilter !== 'all' ? '1.5px solid #ffb86c' : subBorder,
                    color: publisherFilter !== 'all' ? '#ffb86c' : textPrimary,
                    fontSize: '0.72rem', fontWeight: 800, outline: 'none', cursor: 'pointer'
                  }}
                >
                  <option value="all">🏢 Tutti i Publisher ({totalModelsCount})</option>
                  {availablePublishers.map(pub => {
                    const cnt = models.filter(m => getModelInfo(m).publisher.toLowerCase() === pub.toLowerCase()).length;
                    const isSig = pub.toLowerCase() === 'sigmanih';
                    return (
                      <option key={pub} value={pub}>
                        {isSig ? `✨ ${pub} (Ufficiale Sigmanih)` : pub} ({cnt})
                      </option>
                    );
                  })}
                </select>
              </div>

              {/* Active filters reset */}
              {(familyFilter !== 'all' || publisherFilter !== 'all' || categoryFilter !== 'all' || searchQuery) && (
                <button
                  onClick={() => {
                    setFamilyFilter('all');
                    setPublisherFilter('all');
                    setCategoryFilter('all');
                    setSearchQuery('');
                  }}
                  style={{
                    padding: '4px 9px', borderRadius: '6px',
                    background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#ef4444', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer',
                    display: 'inline-flex', alignItems: 'center', gap: '4px'
                  }}
                >
                  <RotateCcw size={11} /> Reset Filtri
                </button>
              )}
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

          {/* MODELS LIST */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '50px', color: textMuted }}>
              <Activity className="mh-spin" size={24} color="#00d2ff" style={{ margin: '0 auto 10px' }} />
              <span style={{ fontSize: '0.84rem' }}>Scansione modelli locali in corso...</span>
            </div>
          ) : sortedModels.length === 0 ? (
            <div style={{
              padding: '50px 20px', borderRadius: '16px', background: cardBg, border: cardBorder,
              textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'
            }}>
              <HardDrive size={32} color="#bc8cff" />
              <div style={{ fontSize: '0.92rem', fontWeight: 800, color: textPrimary }}>
                {searchQuery || familyFilter !== 'all' || publisherFilter !== 'all' || categoryFilter !== 'all'
                  ? 'Nessun modello corrispondente ai filtri selezionati.'
                  : 'Nessun modello trovato nello storage locale.'}
              </div>
              <div style={{ fontSize: '0.76rem' }}>
                Esplora la tab "🔍 Esplora Hugging Face" per scaricare modelli GGUF o Safetensors.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {sortedModels.map((m, idx) => {
                const info = getModelInfo(m);
                const isGguf = info.isGguf;
                const isSigmanih = info.isSigmanih;
                const bm = m.benchmark_summary || {};
                const hasBenchmark = info.hasBenchmark;
                const bmScore = bm.score ?? bm.best_score ?? bm.latest_score ?? bm.overall_pass_rate ?? 0;
                const bmScoreColor = bmScore >= 75 ? '#10b981' : (bmScore >= 50 ? '#00d2ff' : '#ffb86c');
                const isPublished = info.isPublished;

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '18px 22px', borderRadius: '16px',
                      background: m.is_active_in_engine
                        ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.12) 0%, rgba(15, 18, 28, 0.92) 100%)')
                        : (isSigmanih
                          ? (isLight ? 'linear-gradient(135deg, #ffffff 0%, #fffcf5 100%)' : 'linear-gradient(135deg, rgba(20, 24, 38, 0.92) 0%, rgba(15, 18, 28, 0.96) 100%)')
                          : cardBg),
                      border: m.is_active_in_engine
                        ? '1.5px solid #00d2ff'
                        : (isSigmanih ? '1.5px solid rgba(255, 184, 108, 0.35)' : cardBorder),
                      boxShadow: m.is_active_in_engine
                        ? '0 0 24px rgba(0, 210, 255, 0.20)'
                        : (isSigmanih ? '0 4px 20px rgba(255, 184, 108, 0.06)' : 'none'),
                      display: 'flex', flexDirection: 'column', gap: '14px',
                      transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                    }}
                  >
                    {/* TOP HEADER: PUBLISHER + FAMILY + CATEGORY + STATUS TAGS */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                      <div style={{ minWidth: 0, flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        
                        {/* Badges Bar: Rilasciato da + Famiglia + Categoria */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          
                          {/* Publisher Pill */}
                          {isSigmanih ? (
                            <div style={{
                              fontSize: '0.68rem', fontWeight: 900,
                              background: 'linear-gradient(135deg, rgba(255, 184, 108, 0.22) 0%, rgba(0, 210, 255, 0.16) 100%)',
                              border: '1px solid rgba(255, 184, 108, 0.55)',
                              color: '#ffb86c', borderRadius: '7px', padding: '3px 10px',
                              display: 'inline-flex', alignItems: 'center', gap: '5px',
                              boxShadow: '0 0 10px rgba(255, 184, 108, 0.25)'
                            }}>
                              <Sparkles size={11} color="#ffb86c" />
                              <span style={{ color: '#00d2ff', fontSize: '0.62rem', fontWeight: 900 }}>🏢 Rilasciato da:</span>
                              <span style={{ color: '#ffb86c', fontWeight: 900, letterSpacing: '0.02em' }}>sigmanih</span>
                              <span style={{ fontSize: '0.54rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255, 184, 108, 0.25)', color: '#ffffff', fontWeight: 800 }}>
                                UFFICIALE
                              </span>
                            </div>
                          ) : (
                            <div style={{
                              fontSize: '0.68rem', fontWeight: 800,
                              color: '#ffffff', background: 'rgba(255, 255, 255, 0.08)',
                              border: '1px solid rgba(255, 255, 255, 0.16)',
                              borderRadius: '7px', padding: '3px 9px',
                              display: 'inline-flex', alignItems: 'center', gap: '4px'
                            }}>
                              <span style={{ color: '#00d2ff', fontSize: '0.62rem', fontWeight: 900 }}>🏢 Rilasciato da:</span>
                              <span style={{ color: textPrimary, fontWeight: 800 }}>{info.publisher}</span>
                              {m.is_official && (
                                <span style={{ fontSize: '0.54rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.2)', color: '#38bdf8', fontWeight: 800 }}>
                                  Ufficiale
                                </span>
                              )}
                            </div>
                          )}

                          {/* Family Pill */}
                          <div style={{
                            fontSize: '0.66rem', fontWeight: 800,
                            color: '#c084fc', background: 'rgba(192, 132, 252, 0.12)',
                            border: '1px solid rgba(192, 132, 252, 0.32)',
                            borderRadius: '7px', padding: '3px 8px',
                            display: 'inline-flex', alignItems: 'center', gap: '4px'
                          }}>
                            <span>🧬 Famiglia:</span>
                            <b style={{ color: '#f0abfc' }}>{info.family}</b>
                          </div>

                          {/* Category Pill */}
                          {info.category === 'code' && (
                            <div style={{
                              fontSize: '0.64rem', fontWeight: 800,
                              color: '#38bdf8', background: 'rgba(56, 189, 248, 0.12)',
                              border: '1px solid rgba(56, 189, 248, 0.35)',
                              borderRadius: '6px', padding: '2px 7px',
                              display: 'inline-flex', alignItems: 'center', gap: '4px'
                            }}>
                              <Code size={11} /> Coding & Dev
                            </div>
                          )}

                          {info.category === 'reasoning' && (
                            <div style={{
                              fontSize: '0.64rem', fontWeight: 800,
                              color: '#f43f5e', background: 'rgba(244, 63, 94, 0.12)',
                              border: '1px solid rgba(244, 63, 94, 0.35)',
                              borderRadius: '6px', padding: '2px 7px',
                              display: 'inline-flex', alignItems: 'center', gap: '4px'
                            }}>
                              <Brain size={11} /> Reasoning & R1
                            </div>
                          )}

                          {info.category === 'vision' && (
                            <div style={{
                              fontSize: '0.64rem', fontWeight: 800,
                              color: '#a855f7', background: 'rgba(168, 85, 247, 0.12)',
                              border: '1px solid rgba(168, 85, 247, 0.35)',
                              borderRadius: '6px', padding: '2px 7px',
                              display: 'inline-flex', alignItems: 'center', gap: '4px'
                            }}>
                              <Eye size={11} /> Vision & VL
                            </div>
                          )}
                        </div>

                        {/* Model Main Name & HF Direct Link */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginTop: '2px' }}>
                          <span style={{ fontSize: '1.02rem', fontWeight: 900, color: textPrimary, wordBreak: 'break-all', letterSpacing: '-0.01em' }}>
                            {m.clean_name || m.display_name || m.filename}
                          </span>

                          {/* Format Tag */}
                          <span style={{
                            fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                            fontWeight: 800,
                            background: isGguf ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                            color: isGguf ? '#10b981' : '#00d2ff',
                            border: isGguf ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)'
                          }}>
                            {m.format_tag || (isGguf ? 'GGUF' : 'SAFETENSORS')}
                          </span>

                          {/* Quantization */}
                          {m.quantization && (
                            <span style={{
                              fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                              background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', fontWeight: 800,
                              border: '1px solid rgba(188, 140, 255, 0.35)'
                            }}>
                              {m.quantization}
                            </span>
                          )}

                          {/* Parameter size */}
                          {m.params_label && (
                            <span style={{
                              fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                              background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800,
                              border: '1px solid rgba(255, 184, 108, 0.35)'
                            }}>
                              ⚡ {m.params_label}
                            </span>
                          )}

                          {/* Active in Engine badge */}
                          {m.is_active_in_engine && (
                            <span style={{
                              fontSize: '0.64rem', padding: '3px 9px', borderRadius: '6px',
                              background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(16, 185, 129, 0.25))',
                              color: '#00d2ff', fontWeight: 900,
                              border: '1px solid #00d2ff',
                              boxShadow: '0 0 12px rgba(0, 210, 255, 0.35)'
                            }}>
                              ⚡ CARICATO IN SIGMAENGINE
                            </span>
                          )}

                          {/* Hugging Face Link Pill */}
                          {isPublished && (
                            <a
                              href={m.publication.url}
                              target="_blank"
                              rel="noreferrer"
                              title={`Pubblicato su Hugging Face: ${m.publication.repo_id}`}
                              style={{
                                fontSize: '0.64rem', padding: '3px 9px', borderRadius: '6px',
                                background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800,
                                border: '1px solid rgba(255, 184, 108, 0.35)', textDecoration: 'none',
                                display: 'inline-flex', alignItems: 'center', gap: '4px'
                              }}
                            >
                              🤗 HF: <span style={{ textDecoration: 'underline' }}>{m.publication.repo_id}</span> <ExternalLink size={10} />
                            </a>
                          )}
                        </div>

                        {/* Incomplete / Partial Download Alert */}
                        {(!m.is_complete || m.has_part_files) && (
                          <div style={{
                            marginTop: '8px',
                            padding: '8px 12px', borderRadius: '10px',
                            background: isLight ? 'rgba(255, 184, 108, 0.16)' : 'rgba(255, 184, 108, 0.08)',
                            border: '1px solid rgba(255, 184, 108, 0.35)',
                            color: '#ffb86c', fontSize: '0.72rem', fontWeight: 600,
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                              <AlertTriangle size={14} color="#ffb86c" />
                              <span>
                                Download incompleto: scaricati solo <b>{m.shards_present || m.total_shards}</b> su <b>{m.total_shards_declared || '?'}</b> shard ({m.size_gb} GB presenti su disco).
                              </span>
                            </div>
                            <button
                              onClick={() => handleResumeDownload(m)}
                              disabled={resumingModelId === (m.model_id || m.filename)}
                              style={{
                                padding: '5px 12px', borderRadius: '7px',
                                background: 'linear-gradient(135deg, #ffb86c, #f59e0b)',
                                border: 'none', color: '#111827', fontSize: '0.70rem', fontWeight: 900,
                                cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '5px',
                                boxShadow: '0 0 10px rgba(255, 184, 108, 0.35)',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {resumingModelId === (m.model_id || m.filename) ? <Activity className="mh-spin" size={12} /> : <Download size={12} />}
                              {resumingModelId === (m.model_id || m.filename) ? 'Avvio ripresa...' : '📥 Continua Download'}
                            </button>
                          </div>
                        )}

                        {/* Specs Row */}
                        <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            💾 <b>{m.size_gb} GB</b> su disco
                          </span>
                          <span>•</span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            ⚡ VRAM stimata: <b>~{m.est_vram_gb} GB</b>
                          </span>
                          {m.architecture && (
                            <>
                              <span>•</span>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                🧬 Architettura: <b>{m.architecture}</b>
                              </span>
                            </>
                          )}
                          {m.added_at && (
                            <>
                              <span>•</span>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                🕒 Aggiunto: {m.added_at}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions Bar */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0, flexWrap: 'wrap' }}>
                        {/* Primary Button: Continua Download for incomplete, otherwise Run in SigmaEngine */}
                        {(!m.is_complete || m.has_part_files) ? (
                          <button
                            onClick={() => handleResumeDownload(m)}
                            disabled={resumingModelId === (m.model_id || m.filename)}
                            title="Riprendi il download degli shard mancanti da Hugging Face"
                            style={{
                              padding: '7px 15px', borderRadius: '9px',
                              border: 'none', background: 'linear-gradient(135deg, #ffb86c, #f59e0b)',
                              color: '#111827', fontSize: '0.74rem', fontWeight: 900, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '5px',
                              boxShadow: '0 0 14px rgba(255, 184, 108, 0.40)',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            {resumingModelId === (m.model_id || m.filename) ? <Activity className="mh-spin" size={13} /> : <Download size={13} />}
                            {resumingModelId === (m.model_id || m.filename) ? 'Ripresa...' : '📥 Continua Download'}
                          </button>
                        ) : (
                          <button
                            onClick={() => onDeployRequested && onDeployRequested(m)}
                            style={{
                              padding: '7px 15px', borderRadius: '9px',
                              border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                              color: '#ffffff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '5px',
                              boxShadow: '0 0 14px rgba(0, 210, 255, 0.35)',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            <Zap size={13} /> {m.is_active_in_engine ? 'Rialloca' : '⚡ Avvia'}
                          </button>
                        )}

                        {/* Prova Inferenza Interactive Modal */}
                        <button
                          onClick={() => {
                            if (!m.is_complete || m.has_part_files) {
                              if (addToast) addToast('⚠️ Il modello è incompleto. Clicca "Continua Download" per completarlo prima di testare l\'inferenza.', 'warning');
                              return;
                            }
                            setInferenceTestingModel(m);
                          }}
                          title="Apri il playground per scrivere prompt ed eseguire la telemetria t/s"
                          style={{
                            padding: '7px 13px', borderRadius: '9px',
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
                          title={isPublished ? 'Aggiorna questo modello o carica nuove quantizzazioni su Hugging Face' : 'Pubblica questo modello su Hugging Face'}
                          style={{
                            padding: '7px 12px', borderRadius: '9px',
                            border: '1px solid rgba(255, 184, 108, 0.40)',
                            background: isPublished ? 'rgba(255, 184, 108, 0.18)' : 'rgba(255, 184, 108, 0.08)',
                            color: '#ffb86c', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '5px'
                          }}
                        >
                          <Upload size={13} /> {isPublished ? 'Aggiorna su HF' : 'Pubblica su HF'}
                        </button>

                        {/* GGUF Converter shortcut (if Safetensors) */}
                        {(!isGguf || m.is_repo_folder) && (
                          <button
                            onClick={() => {
                              if (!m.is_complete || m.has_part_files) {
                                if (addToast) addToast('⚠️ Il modello Safetensors è incompleto. Completa prima il download per convertirlo in GGUF.', 'warning');
                                return;
                              }
                              handleTriggerConvertForModel(m.model_id || m.filename);
                            }}
                            title="Configura e converti questo modello in GGUF quantizzato"
                            style={{
                              padding: '7px 11px', borderRadius: '9px',
                              border: '1px solid rgba(16, 185, 129, 0.35)', background: 'rgba(16, 185, 129, 0.10)',
                              color: '#10b981', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '4px'
                            }}
                          >
                            <Package size={13} /> Converti
                          </button>
                        )}

                        {/* Rename */}
                        <button
                          onClick={() => handleRenameModel(m)}
                          disabled={renamingPath === (m.path || m.filename)}
                          title="Rinomina il modello sul disco"
                          style={{
                            padding: '7px 9px', borderRadius: '9px',
                            border: subBorder, background: subBg,
                            color: textMuted, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '3px',
                            opacity: renamingPath === (m.path || m.filename) ? 0.6 : 1
                          }}
                        >
                          <Pencil size={13} />
                        </button>

                        {/* Delete */}
                        <button
                          onClick={() => handleDeleteModel(m)}
                          disabled={deletingPath === (m.path || m.filename)}
                          title="Elimina definitivamente dallo storage locale"
                          style={{
                            padding: '7px 9px', borderRadius: '9px',
                            border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)',
                            color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '3px',
                            opacity: deletingPath === (m.path || m.filename) ? 0.6 : 1
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    {/* REPOSITORY COLLEGATO SU HUGGING FACE */}
                    {isPublished && (
                      <div style={{
                        padding: '10px 14px', borderRadius: '12px',
                        background: isLight ? 'rgba(255, 184, 108, 0.08)' : 'rgba(255, 184, 108, 0.06)',
                        border: '1px solid rgba(255, 184, 108, 0.25)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        gap: '10px', flexWrap: 'wrap'
                      }}>
                        <span style={{ fontSize: '0.72rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <ExternalLink size={13} color="#ffb86c" />
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
                              padding: '4px 10px', borderRadius: '6px',
                              border: '1px solid rgba(255,184,108,0.4)', background: 'transparent',
                              color: '#ffb86c', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer'
                            }}
                          >
                            {updatingCard === (m.path || m.filename) ? 'Aggiorno...' : 'Aggiorna scheda'}
                          </button>

                          <button
                            onClick={() => handleRenameHfRepoFromInventory(m)}
                            title="Rinomina il repository su Hugging Face e aggiorna la scheda con il nuovo titolo"
                            style={{
                              padding: '4px 10px', borderRadius: '6px',
                              border: '1px solid rgba(255,184,108,0.25)', background: 'transparent',
                              color: '#ffb86c', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                            }}
                          >
                            Rinomina
                          </button>

                          <button
                            onClick={() => handleAttachHfRepo(m)}
                            title="Modifica o ricollega questo modello a un altro repository Hugging Face"
                            style={{
                              padding: '4px 10px', borderRadius: '6px',
                              border: '1px solid rgba(0,210,255,0.3)', background: 'transparent',
                              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                            }}
                          >
                            Modifica link
                          </button>

                          <button
                            onClick={() => handleForgetPublication(m)}
                            title="Scollega questo modello dal repository HF (non tocca niente su HF)"
                            style={{
                              padding: '4px 9px', borderRadius: '6px',
                              border: subBorder, background: 'transparent',
                              color: textMuted, fontSize: '0.68rem', fontWeight: 600, cursor: 'pointer'
                            }}
                          >
                            Scollega
                          </button>
                        </div>
                      </div>
                    )}

                    {/* BENCHMARK SHOWCASE BANNER */}
                    {hasBenchmark ? (
                      <div style={{
                        padding: '12px 16px', borderRadius: '12px',
                        background: isLight ? 'rgba(255, 184, 108, 0.08)' : 'linear-gradient(135deg, rgba(255, 184, 108, 0.08) 0%, rgba(16, 185, 129, 0.06) 100%)',
                        border: '1px solid rgba(255, 184, 108, 0.30)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0 }}>
                          <div style={{
                            width: '36px', height: '36px', borderRadius: '10px',
                            background: 'rgba(255, 184, 108, 0.18)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                          }}>
                            <Trophy size={18} color="#ffb86c" />
                          </div>

                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary }}>
                                Benchmark Ufficiale Training Lab:
                              </span>
                              <span style={{
                                fontSize: '0.84rem', fontWeight: 900, color: bmScoreColor,
                                padding: '2px 9px', borderRadius: '6px',
                                background: `${bmScoreColor}18`, border: `1px solid ${bmScoreColor}44`
                              }}>
                                🏆 {bmScore}% Pass
                              </span>
                            </div>

                            <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '3px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
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
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '8px' }}>
                                {Object.entries(bm.suites).map(([sid, st]) => {
                                  const quota = st.total ? Math.round((st.passed / st.total) * 100) : 0;
                                  const colore = quota >= 75 ? '#10b981' : quota >= 50 ? '#ffb86c' : '#ef4444';
                                  return (
                                    <span key={sid} title={`${st.passed} superati su ${st.total}`}
                                      style={{
                                        fontSize: '0.62rem', fontWeight: 700, padding: '3px 8px',
                                        borderRadius: '6px', whiteSpace: 'nowrap',
                                        background: `${colore}14`, border: `1px solid ${colore}40`, color: colore,
                                      }}>
                                      {sid} <b>{st.passed}/{st.total}</b> ({quota}%)
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{
                            fontSize: '0.64rem', fontWeight: 800, color: '#10b981',
                            padding: '4px 9px', borderRadius: '6px',
                            background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)'
                          }}>
                            ✓ VALUTAZIONE REGISTRATA
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div style={{
                        padding: '9px 14px', borderRadius: '10px',
                        background: subBg, border: subBorder,
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'
                      }}>
                        <span style={{ fontSize: '0.68rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <Award size={13} color={textMuted} /> Nessun benchmark registrato per questo modello.
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
