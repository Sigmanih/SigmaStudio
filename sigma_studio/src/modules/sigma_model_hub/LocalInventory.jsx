import React, { useState, useEffect, useCallback } from 'react';
import {
  HardDrive, Zap, RefreshCw, Trash2, Power, Pencil,
  Activity, Upload, Download, Search, ChevronDown, ChevronUp, Sliders, Layers, Sparkles,
  Trophy, Award, Gauge, Cpu, ExternalLink,
  RotateCcw, Code, Brain, Eye, Tag, User, Dna, Boxes, CheckCircle2, AlertTriangle, Package,
  X, Check, ChevronRight, BarChart2, CornerDownRight, Minimize2, Maximize2
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';
import InferenceTestModal from './InferenceTestModal.jsx';
import DownloadLogSidebar from './DownloadLogSidebar.jsx';

// ==============================================================================
// Family Metadata Definitions (Coloring, Badges, Brand Labels)
// ==============================================================================
const FAMILY_CONFIG = {
  sigmanih: {
    title: 'Modelli & Release Ufficiali Sigmanih',
    brand: 'Sigmanih Ecosystem',
    icon: Sparkles,
    color: '#ffb86c',
    gradient: 'linear-gradient(135deg, rgba(255, 184, 108, 0.20) 0%, rgba(0, 210, 255, 0.14) 100%)',
    borderColor: 'rgba(255, 184, 108, 0.40)'
  },
  gemma: {
    title: 'Famiglia Gemma',
    brand: 'Google DeepMind',
    icon: Dna,
    color: '#00d2ff',
    gradient: 'linear-gradient(135deg, rgba(0, 210, 255, 0.16) 0%, rgba(59, 130, 246, 0.10) 100%)',
    borderColor: 'rgba(0, 210, 255, 0.30)'
  },
  qwen: {
    title: 'Famiglia Qwen',
    brand: 'Alibaba Cloud',
    icon: Dna,
    color: '#a855f7',
    gradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.16) 0%, rgba(192, 132, 252, 0.10) 100%)',
    borderColor: 'rgba(168, 85, 247, 0.30)'
  },
  llama: {
    title: 'Famiglia Llama',
    brand: 'Meta AI',
    icon: Dna,
    color: '#38bdf8',
    gradient: 'linear-gradient(135deg, rgba(56, 189, 248, 0.16) 0%, rgba(99, 102, 241, 0.10) 100%)',
    borderColor: 'rgba(56, 189, 248, 0.30)'
  },
  deepseek: {
    title: 'Famiglia DeepSeek',
    brand: 'DeepSeek AI',
    icon: Brain,
    color: '#f43f5e',
    gradient: 'linear-gradient(135deg, rgba(244, 63, 94, 0.16) 0%, rgba(239, 68, 68, 0.10) 100%)',
    borderColor: 'rgba(244, 63, 94, 0.30)'
  },
  mistral: {
    title: 'Famiglia Mistral & Mixtral',
    brand: 'Mistral AI',
    icon: Dna,
    color: '#10b981',
    gradient: 'linear-gradient(135deg, rgba(16, 185, 129, 0.16) 0%, rgba(5, 150, 105, 0.10) 100%)',
    borderColor: 'rgba(16, 185, 129, 0.30)'
  },
  phi: {
    title: 'Famiglia Phi',
    brand: 'Microsoft Research',
    icon: Dna,
    color: '#fb923c',
    gradient: 'linear-gradient(135deg, rgba(251, 146, 60, 0.16) 0%, rgba(245, 158, 11, 0.10) 100%)',
    borderColor: 'rgba(251, 146, 60, 0.30)'
  },
  glm: {
    title: 'Famiglia GLM & ChatGLM',
    brand: 'Zhipu AI',
    icon: Dna,
    color: '#06b6d4',
    gradient: 'linear-gradient(135deg, rgba(6, 182, 212, 0.16) 0%, rgba(14, 165, 233, 0.10) 100%)',
    borderColor: 'rgba(6, 182, 212, 0.30)'
  },
  altro: {
    title: 'Altre Famiglie & Modelli',
    brand: 'Open Source Community',
    icon: Boxes,
    color: '#94a3b8',
    gradient: 'linear-gradient(135deg, rgba(148, 163, 184, 0.12) 0%, rgba(100, 116, 139, 0.06) 100%)',
    borderColor: 'rgba(148, 163, 184, 0.25)'
  }
};

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
  const [familyFilter, setFamilyFilter] = useState('all');       // 'all' | 'sigmanih' | 'gemma' | 'qwen' | 'llama' | 'deepseek' | 'mistral' | 'phi' | 'glm' | 'altro'
  const [categoryFilter, setCategoryFilter] = useState('all');   // 'all' | 'sigmanih' | 'reasoning' | 'code' | 'vision' | 'moe' | 'llm' | 'gguf' | 'safetensors' | 'benchmarked' | 'published'
  const [publisherFilter, setPublisherFilter] = useState('all'); // 'all' | 'sigmanih' | 'google' | 'qwen' | 'meta' | 'deepseek' | 'mistralai' | 'microsoft'
  const [sortBy, setSortBy] = useState('recent');                // 'recent' | 'size_desc' | 'size_asc' | 'vram_desc' | 'benchmark' | 'name'

  // Sector Collapsing: map of familyKey -> bool
  const [collapsedFamilies, setCollapsedFamilies] = useState({});

  // Expanded Details per model card: set of model identifiers
  const [expandedCards, setExpandedCards] = useState(() => new Set());

  const [renamingPath, setRenamingPath] = useState(null);
  const [updatingCard, setUpdatingCard] = useState(null);
  const [discovering, setDiscovering] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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

  useEffect(() => {
    fetchLocalModels();
  }, [fetchLocalModels]);

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

    // Chiave famiglia standardizzata
    let familyKey = 'altro';
    if (isSigmanih) familyKey = 'sigmanih';
    else if (family.toLowerCase() === 'gemma') familyKey = 'gemma';
    else if (family.toLowerCase() === 'qwen') familyKey = 'qwen';
    else if (family.toLowerCase() === 'llama') familyKey = 'llama';
    else if (family.toLowerCase() === 'deepseek') familyKey = 'deepseek';
    else if (family.toLowerCase() === 'mistral') familyKey = 'mistral';
    else if (family.toLowerCase() === 'phi') familyKey = 'phi';
    else if (family.toLowerCase() === 'glm') familyKey = 'glm';

    return {
      isGguf,
      isSafetensors,
      isSigmanih,
      publisher,
      family,
      familyKey,
      category,
      hasBenchmark: !!m.benchmark_summary?.has_benchmarks,
      isPublished: Boolean(repoId)
    };
  };

  // Helper per estrazione dettagliata delle suite di benchmark
  const getSuiteEntries = (bm) => {
    if (!bm) return [];
    if (bm.suites && typeof bm.suites === 'object' && Object.keys(bm.suites).length > 0) {
      return Object.entries(bm.suites).map(([name, data]) => {
        if (!data || typeof data !== 'object') {
          return { name, passed: 0, failed: 0, total: 0, pct: 0 };
        }
        const passed = data.passed ?? 0;
        const failed = data.failed ?? 0;
        const total = data.total ?? (passed + failed) ?? 0;
        const pct = total > 0 ? Math.round((passed / total) * 100) : (data.score ?? data.pass_rate ?? 0);
        return { name, passed, failed, total, pct };
      });
    }
    if (bm.results && typeof bm.results === 'object' && Object.keys(bm.results).length > 0) {
      return Object.entries(bm.results).map(([name, data]) => {
        if (typeof data === 'number') {
          return { name, passed: data, failed: 0, total: 100, pct: data };
        }
        const passed = data.passed ?? data.score ?? 0;
        const total = data.total ?? 100;
        const failed = data.failed ?? (total - passed);
        const pct = data.score ?? (total > 0 ? Math.round((passed / total) * 100) : 0);
        return { name, passed, failed, total, pct };
      });
    }
    return [];
  };

  // Stats calculation
  const totalModelsCount = models.length;
  const sigmanihModels = models.filter(m => getModelInfo(m).isSigmanih);
  const ggufModels = models.filter(m => getModelInfo(m).isGguf);
  const safetensorsModels = models.filter(m => getModelInfo(m).isSafetensors);
  const benchmarkedModels = models.filter(m => getModelInfo(m).hasBenchmark);
  const publishedModels = models.filter(m => getModelInfo(m).isPublished);

  const sigmanihCount = sigmanihModels.length;
  const ggufCount = ggufModels.length;
  const safetensorsCount = safetensorsModels.length;
  const benchmarkedCount = benchmarkedModels.length;

  const ggufStorageGb = ggufModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const safetensorsStorageGb = safetensorsModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0);
  const totalStorageGb = (ggufStorageGb + safetensorsStorageGb).toFixed(1);

  // Multi-Filter & Search models
  const filteredModels = models.filter(m => {
    const info = getModelInfo(m);

    // 1. Filtro Settore / Famiglia
    if (familyFilter !== 'all') {
      if (familyFilter === 'sigmanih' && !info.isSigmanih) return false;
      if (familyFilter !== 'sigmanih') {
        if (info.isSigmanih) return false;
        if (info.familyKey !== familyFilter) return false;
      }
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

  // Raggruppamento per Famiglia
  const familyOrder = ['sigmanih', 'gemma', 'qwen', 'llama', 'deepseek', 'mistral', 'phi', 'glm', 'altro'];
  const groupedByFamily = familyOrder.reduce((acc, famKey) => {
    const items = sortedModels.filter(m => {
      const info = getModelInfo(m);
      if (famKey === 'sigmanih') return info.isSigmanih;
      if (info.isSigmanih) return false;
      return info.familyKey === famKey;
    });
    if (items.length > 0) {
      acc[famKey] = items;
    }
    return acc;
  }, {});

  // Aggiungi eventuali famiglie non predefinite sotto 'altro'
  const knownKeys = new Set(familyOrder);
  sortedModels.forEach(m => {
    const info = getModelInfo(m);
    if (!knownKeys.has(info.familyKey) && !info.isSigmanih) {
      if (!groupedByFamily['altro']) groupedByFamily['altro'] = [];
      if (!groupedByFamily['altro'].includes(m)) {
        groupedByFamily['altro'].push(m);
      }
    }
  });

  // Toggle Sector Accordion
  const toggleFamilyCollapse = (famKey) => {
    setCollapsedFamilies(prev => ({
      ...prev,
      [famKey]: !prev[famKey]
    }));
  };

  const collapseAllSectors = () => {
    const allCollapsed = {};
    Object.keys(groupedByFamily).forEach(k => { allCollapsed[k] = true; });
    setCollapsedFamilies(allCollapsed);
  };

  const expandAllSectors = () => {
    setCollapsedFamilies({});
  };

  // Toggle Model Card Details
  const toggleCardDetails = (modelKey) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(modelKey)) next.delete(modelKey);
      else next.add(modelKey);
      return next;
    });
  };

  // Count models per family
  const getFamilyCount = (key) => {
    return models.filter(m => {
      const info = getModelInfo(m);
      if (key === 'sigmanih') return info.isSigmanih;
      if (info.isSigmanih) return false;
      return info.familyKey === key;
    }).length;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* 1. COMPACT STORAGE & TELEMETRY STRIP */}
      <div style={{
        padding: '12px 18px', borderRadius: '14px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf6ee 100%)'
          : 'linear-gradient(135deg, rgba(14, 18, 28, 0.95) 0%, rgba(20, 26, 42, 0.85) 100%)',
        border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(0, 210, 255, 0.18)',
        boxShadow: isLight ? '0 2px 10px rgba(0,0,0,0.04)' : '0 4px 18px rgba(0,0,0,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px'
      }}>
        {/* Left: Title + Key Metrics Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '30px', height: '30px', borderRadius: '8px',
              background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(188, 140, 255, 0.2))',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <HardDrive size={16} color="#00d2ff" />
            </div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 900, color: textPrimary, letterSpacing: '-0.02em' }}>
              Modelli Locali & Storage
            </h3>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{
              fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: subBg, border: subBorder, color: textPrimary
            }}>
              📦 <b>{totalModelsCount}</b> Modelli
            </span>
            <span style={{
              fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: 'rgba(255, 184, 108, 0.12)', border: '1px solid rgba(255, 184, 108, 0.3)', color: '#ffb86c'
            }}>
              ✨ <b>{sigmanihCount}</b> Sigmanih
            </span>
            <span style={{
              fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: 'rgba(16, 185, 129, 0.10)', border: '1px solid rgba(16, 185, 129, 0.25)', color: '#10b981'
            }}>
              ⚡ <b>{ggufCount}</b> GGUF
            </span>
            <span style={{
              fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: 'rgba(0, 210, 255, 0.10)', border: '1px solid rgba(0, 210, 255, 0.25)', color: '#00d2ff'
            }}>
              📦 <b>{safetensorsCount}</b> Safe
            </span>
            <span style={{
              fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: 'rgba(188, 140, 255, 0.10)', border: '1px solid rgba(188, 140, 255, 0.25)', color: '#bc8cff'
            }}>
              💾 <b>{totalStorageGb} GB</b> Totali
            </span>
          </div>
        </div>

        {/* Right: Quick Global Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={handleDiscoverRepos}
            disabled={discovering}
            title="Cerca sul tuo account Hugging Face i repository corrispondenti"
            style={{
              padding: '5px 10px', borderRadius: '7px',
              border: '1px solid rgba(255,184,108,0.35)', background: 'rgba(255,184,108,0.08)',
              color: '#ffb86c', fontSize: '0.68rem', fontWeight: 700, cursor: discovering ? 'wait' : 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: '4px'
            }}
          >
            <ExternalLink size={11} />
            {discovering ? 'Cerco...' : 'Collega HF'}
          </button>

          <button
            onClick={handleUnloadModel}
            disabled={unloading}
            title="Scarica il modello attivo da VRAM/RAM"
            style={{
              padding: '5px 10px', borderRadius: '7px',
              border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px'
            }}
          >
            <Power size={11} /> {unloading ? 'Rilascio...' : 'Libera VRAM'}
          </button>

          <button
            onClick={() => {
              fetchLocalModels();
              if (onDownloadsChanged) onDownloadsChanged();
            }}
            title="Ricarica elenco modelli"
            style={{
              padding: '5px 10px', borderRadius: '7px',
              border: subBorder, background: subBg,
              color: textPrimary, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px'
            }}
          >
            <RefreshCw size={11} /> Aggiorna
          </button>
        </div>
      </div>

      {/* 2. MAIN 2-COLUMN WORKSPACE: SECTORIZED CATALOG + DOWNLOAD SIDEBAR */}
      <div style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', position: 'relative' }}>

        {/* LEFT / CENTER COLUMN: SECTORIZED MODELS */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>

          {/* ── SETTORIALIZZAZIONE RAPIDA: SECTOR TABS (FAMIGLIE MODELLI) ── */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto',
            paddingBottom: '4px', scrollbarWidth: 'none'
          }}>
            <button
              onClick={() => setFamilyFilter('all')}
              style={{
                padding: '6px 12px', borderRadius: '8px',
                border: familyFilter === 'all' ? '1.5px solid #00d2ff' : subBorder,
                background: familyFilter === 'all' ? 'rgba(0, 210, 255, 0.15)' : cardBg,
                color: familyFilter === 'all' ? '#00d2ff' : textMuted,
                fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer', whiteSpace: 'nowrap',
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                boxShadow: familyFilter === 'all' ? '0 0 10px rgba(0, 210, 255, 0.25)' : 'none',
                transition: 'all 0.15s ease'
              }}
            >
              <Boxes size={13} />
              <span>Tutti i Settori</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.8 }}>({totalModelsCount})</span>
            </button>

            {familyOrder.map(fKey => {
              const conf = FAMILY_CONFIG[fKey];
              const count = getFamilyCount(fKey);
              if (count === 0) return null;
              const Icon = conf.icon;
              const active = familyFilter === fKey;
              const isSig = fKey === 'sigmanih';

              return (
                <button
                  key={fKey}
                  onClick={() => setFamilyFilter(fKey)}
                  style={{
                    padding: '6px 12px', borderRadius: '8px',
                    border: active ? `1.5px solid ${conf.color}` : subBorder,
                    background: active
                      ? (isSig ? 'linear-gradient(135deg, rgba(255, 184, 108, 0.25), rgba(0, 210, 255, 0.15))' : `${conf.color}18`)
                      : cardBg,
                    color: active ? conf.color : textMuted,
                    fontSize: '0.72rem', fontWeight: active ? 900 : 700, cursor: 'pointer', whiteSpace: 'nowrap',
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    boxShadow: active ? `0 0 10px ${conf.color}35` : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Icon size={12} color={active ? conf.color : textMuted} />
                  <span>{isSig ? 'Sigmanih' : conf.title.replace('Famiglia ', '')}</span>
                  <span style={{
                    fontSize: '0.60rem', padding: '1px 5px', borderRadius: '4px',
                    background: active ? `${conf.color}25` : subBg, color: active ? conf.color : textMuted,
                    fontWeight: 800
                  }}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* ── TOOLBAR DI RICERCA & FILTRI COMPATTI ── */}
          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: cardBg, border: cardBorder,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
          }}>
            {/* Search Input */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              background: subBg, border: subBorder, borderRadius: '8px',
              padding: '5px 10px', flex: 1, minWidth: '200px'
            }}>
              <Search size={13} color="#00d2ff" />
              <input
                type="text"
                placeholder="Cerca modello, tag quantizzazione, publisher o repo..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{
                  background: 'transparent', border: 'none', outline: 'none',
                  color: textPrimary, fontSize: '0.76rem', width: '100%'
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: 0 }}
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Quick Category & Format Filters */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'Tutti' },
                { id: 'gguf', label: '⚡ GGUF' },
                { id: 'safetensors', label: '📦 Safe' },
                { id: 'benchmarked', label: '🏆 Valutati' },
                { id: 'published', label: '🤗 Pubblicati' }
              ].map(f => {
                const active = categoryFilter === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => setCategoryFilter(f.id)}
                    style={{
                      padding: '4px 8px', borderRadius: '6px',
                      border: active ? '1px solid #00d2ff' : subBorder,
                      background: active ? 'rgba(0, 210, 255, 0.12)' : subBg,
                      color: active ? '#00d2ff' : textMuted,
                      fontSize: '0.66rem', fontWeight: active ? 800 : 600, cursor: 'pointer'
                    }}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>

            {/* Sorting & Sector View Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                style={{
                  padding: '4px 8px', borderRadius: '6px',
                  background: inputBg, border: subBorder, color: textPrimary,
                  fontSize: '0.68rem', fontWeight: 700, outline: 'none', cursor: 'pointer'
                }}
              >
                <option value="recent">⏱️ Recenti</option>
                <option value="size_desc">💾 Peso (GB ↓)</option>
                <option value="size_asc">💾 Peso (GB ↑)</option>
                <option value="vram_desc">⚡ VRAM (GB ↓)</option>
                <option value="benchmark">🏆 Benchmark (%)</option>
                <option value="name">🔤 Nome (A-Z)</option>
              </select>

              {/* Expand / Collapse All Sectors */}
              <button
                onClick={Object.keys(collapsedFamilies).length > 0 ? expandAllSectors : collapseAllSectors}
                title={Object.keys(collapsedFamilies).length > 0 ? 'Espandi tutti i settori' : 'Comprimi tutti i settori'}
                style={{
                  padding: '4px 8px', borderRadius: '6px',
                  border: subBorder, background: subBg, color: textMuted,
                  fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '3px'
                }}
              >
                {Object.keys(collapsedFamilies).length > 0 ? <Maximize2 size={11} /> : <Minimize2 size={11} />}
                <span>{Object.keys(collapsedFamilies).length > 0 ? 'Espandi' : 'Comprimi'}</span>
              </button>

              {/* Reset filter button if any active */}
              {(familyFilter !== 'all' || publisherFilter !== 'all' || categoryFilter !== 'all' || searchQuery) && (
                <button
                  onClick={() => {
                    setFamilyFilter('all');
                    setPublisherFilter('all');
                    setCategoryFilter('all');
                    setSearchQuery('');
                  }}
                  title="Resetta tutti i filtri"
                  style={{
                    padding: '4px 7px', borderRadius: '6px',
                    background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#ef4444', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer'
                  }}
                >
                  <RotateCcw size={10} />
                </button>
              )}
            </div>
          </div>

          {/* ── MODELS LIST: SECTORIZED & ERGONOMIC ── */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px', color: textMuted }}>
              <Activity className="mh-spin" size={22} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
              <span style={{ fontSize: '0.78rem' }}>Caricamento inventario locale...</span>
            </div>
          ) : Object.keys(groupedByFamily).length === 0 ? (
            <div style={{
              padding: '40px 20px', borderRadius: '14px', background: cardBg, border: cardBorder,
              textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px'
            }}>
              <HardDrive size={28} color="#bc8cff" />
              <div style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                {searchQuery || familyFilter !== 'all' || publisherFilter !== 'all' || categoryFilter !== 'all'
                  ? 'Nessun modello corrispondente ai filtri selezionati.'
                  : 'Nessun modello trovato nello storage locale.'}
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {Object.entries(groupedByFamily).map(([famKey, famModels]) => {
                const conf = FAMILY_CONFIG[famKey] || FAMILY_CONFIG.altro;
                const FamIcon = conf.icon;
                const isCollapsed = Boolean(collapsedFamilies[famKey]);
                const famSizeGb = famModels.reduce((sum, m) => sum + (parseFloat(m.size_gb) || 0), 0).toFixed(1);

                return (
                  <div
                    key={famKey}
                    style={{
                      borderRadius: '12px',
                      background: isLight ? 'rgba(255, 255, 255, 0.70)' : 'rgba(12, 16, 26, 0.60)',
                      border: `1px solid ${conf.borderColor}`,
                      overflow: 'hidden',
                      display: 'flex',
                      flexDirection: 'column'
                    }}
                  >
                    {/* SECTOR HEADER (SLIM ACCORDION) */}
                    <div
                      onClick={() => toggleFamilyCollapse(famKey)}
                      style={{
                        padding: '8px 14px',
                        background: conf.gradient,
                        borderBottom: isCollapsed ? 'none' : `1px solid ${conf.borderColor}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        userSelect: 'none'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FamIcon size={14} color={conf.color} />
                        <span style={{ fontSize: '0.82rem', fontWeight: 900, color: textPrimary }}>
                          {conf.title}
                        </span>
                        <span style={{
                          fontSize: '0.58rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px',
                          background: `${conf.color}18`, border: `1px solid ${conf.color}35`, color: conf.color
                        }}>
                          {conf.brand}
                        </span>
                        <span style={{ fontSize: '0.64rem', color: textMuted }}>
                          • {famModels.length} {famModels.length === 1 ? 'modello' : 'modelli'} ({famSizeGb} GB)
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '0.62rem', fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                          background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', color: textPrimary
                        }}>
                          {famModels.length}
                        </span>
                        {isCollapsed ? <ChevronDown size={14} color={textMuted} /> : <ChevronUp size={14} color={textMuted} />}
                      </div>
                    </div>

                    {/* COMPACT MODEL CARDS LIST */}
                    {!isCollapsed && (
                      <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {famModels.map((m, idx) => {
                          const info = getModelInfo(m);
                          const isGguf = info.isGguf;
                          const isSigmanih = info.isSigmanih;
                          const bm = m.benchmark_summary || {};
                          const hasBenchmark = info.hasBenchmark;
                          const bmScore = bm.score ?? bm.best_score ?? bm.latest_score ?? bm.overall_pass_rate ?? 0;
                          const bmScoreColor = bmScore >= 75 ? '#10b981' : (bmScore >= 50 ? '#00d2ff' : '#ffb86c');
                          const isPublished = info.isPublished;
                          const cardKey = m.path || m.filename || String(idx);
                          const isExpanded = expandedCards.has(cardKey);

                          return (
                            <div
                              key={cardKey}
                              style={{
                                borderRadius: '10px',
                                background: m.is_active_in_engine
                                  ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.12) 0%, rgba(15, 18, 28, 0.92) 100%)')
                                  : (isSigmanih
                                    ? (isLight ? 'linear-gradient(135deg, #ffffff 0%, #fffcf5 100%)' : 'linear-gradient(135deg, rgba(22, 26, 40, 0.90) 0%, rgba(15, 18, 28, 0.95) 100%)')
                                    : cardBg),
                                border: m.is_active_in_engine
                                  ? '1.5px solid #00d2ff'
                                  : (isSigmanih ? '1px solid rgba(255, 184, 108, 0.35)' : cardBorder),
                                boxShadow: m.is_active_in_engine
                                  ? '0 0 14px rgba(0, 210, 255, 0.18)'
                                  : 'none',
                                overflow: 'hidden',
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {/* ── ROW PRINCIPALE: COMPATTA, ELEGANTE & VELOCE ── */}
                              <div style={{
                                padding: '8px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                gap: '10px',
                                flexWrap: 'wrap'
                              }}>
                                {/* Left Side: Badges + Model Name + Size & VRAM */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '260px', flexWrap: 'wrap' }}>

                                  {/* Publisher Badge */}
                                  {isSigmanih ? (
                                    <span style={{
                                      fontSize: '0.62rem', fontWeight: 900,
                                      background: 'linear-gradient(135deg, rgba(255, 184, 108, 0.20), rgba(0, 210, 255, 0.15))',
                                      border: '1px solid rgba(255, 184, 108, 0.45)', color: '#ffb86c',
                                      borderRadius: '5px', padding: '2px 6px',
                                      display: 'inline-flex', alignItems: 'center', gap: '3px'
                                    }}>
                                      <Sparkles size={9} color="#ffb86c" /> sigmanih
                                    </span>
                                  ) : (
                                    <span style={{
                                      fontSize: '0.60rem', fontWeight: 800,
                                      background: subBg, border: subBorder, color: textMuted,
                                      borderRadius: '5px', padding: '2px 5px'
                                    }}>
                                      {info.publisher}
                                    </span>
                                  )}

                                  {/* Model Clean Name */}
                                  <span style={{
                                    fontSize: '0.84rem', fontWeight: 800, color: textPrimary,
                                    letterSpacing: '-0.01em', wordBreak: 'break-all'
                                  }}>
                                    {m.clean_name || m.display_name || m.filename}
                                  </span>

                                  {/* Format & Quantization Pill */}
                                  <span style={{
                                    fontSize: '0.58rem', fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                                    background: isGguf ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                                    color: isGguf ? '#10b981' : '#00d2ff',
                                    border: isGguf ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)'
                                  }}>
                                    {m.quantization ? `${m.format_tag || 'GGUF'} ${m.quantization}` : (m.format_tag || (isGguf ? 'GGUF' : 'SAFETENSORS'))}
                                  </span>

                                  {/* Storage & VRAM metrics */}
                                  <span style={{ fontSize: '0.68rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                                    <span>💾 <b>{m.size_gb} GB</b></span>
                                    <span>•</span>
                                    <span style={{ color: isLight ? '#0284c7' : '#00d2ff' }}>⚡ VRAM: <b>~{m.est_vram_gb} GB</b></span>
                                  </span>

                                  {/* Active in Engine Badge */}
                                  {m.is_active_in_engine && (
                                    <span style={{
                                      fontSize: '0.58rem', fontWeight: 900, padding: '2px 6px', borderRadius: '4px',
                                      background: 'rgba(0, 210, 255, 0.20)', border: '1px solid #00d2ff', color: '#00d2ff'
                                    }}>
                                      ⚡ ATTIVO
                                    </span>
                                  )}

                                  {/* Benchmark Score Pill (if present) */}
                                  {hasBenchmark && (
                                    <span style={{
                                      fontSize: '0.58rem', fontWeight: 800, padding: '2px 7px', borderRadius: '5px',
                                      background: `${bmScoreColor}18`, border: `1px solid ${bmScoreColor}35`, color: bmScoreColor,
                                      display: 'inline-flex', alignItems: 'center', gap: '4px'
                                    }}>
                                      <Trophy size={10} color={bmScoreColor} />
                                      <span>{bmScore}% Pass</span>
                                      {bm.tests_total > 0 && (
                                        <span style={{ opacity: 0.85, fontSize: '0.54rem' }}>
                                          ({bm.tests_passed || 0}/{bm.tests_total})
                                        </span>
                                      )}
                                    </span>
                                  )}

                                  {/* Incomplete Warning Badge */}
                                  {(!m.is_complete || m.has_part_files) && (
                                    <span style={{
                                      fontSize: '0.58rem', fontWeight: 800, padding: '1px 6px', borderRadius: '4px',
                                      background: 'rgba(255, 184, 108, 0.20)', border: '1px solid #ffb86c', color: '#ffb86c',
                                      display: 'inline-flex', alignItems: 'center', gap: '3px'
                                    }}>
                                      <AlertTriangle size={10} /> INCOMPLETO ({m.shards_present || 1}/{m.total_shards_declared || 1})
                                    </span>
                                  )}
                                </div>

                                {/* Right Side: Actions Strip */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
                                  {/* Primary Run / Resume Button */}
                                  {(!m.is_complete || m.has_part_files) ? (
                                    <button
                                      onClick={() => handleResumeDownload(m)}
                                      disabled={resumingModelId === (m.model_id || m.filename)}
                                      title="Riprendi download degli shard mancanti"
                                      style={{
                                        padding: '5px 11px', borderRadius: '7px',
                                        border: 'none', background: 'linear-gradient(135deg, #ffb86c, #f59e0b)',
                                        color: '#111827', fontSize: '0.68rem', fontWeight: 900, cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', gap: '4px'
                                      }}
                                    >
                                      {resumingModelId === (m.model_id || m.filename) ? <Activity className="mh-spin" size={11} /> : <Download size={11} />}
                                      <span>Continua</span>
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => onDeployRequested && onDeployRequested(m)}
                                      title={m.is_active_in_engine ? 'Rialloca in SigmaEngine' : 'Carica ed esegui in SigmaEngine'}
                                      style={{
                                        padding: '5px 12px', borderRadius: '7px',
                                        border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0088ff)',
                                        color: '#ffffff', fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', gap: '4px',
                                        boxShadow: '0 2px 8px rgba(0, 210, 255, 0.25)'
                                      }}
                                    >
                                      <Zap size={11} /> {m.is_active_in_engine ? 'Rialloca' : 'Avvia'}
                                    </button>
                                  )}

                                  {/* Prova Inferenza Quick Playground */}
                                  <button
                                    onClick={() => {
                                      if (!m.is_complete || m.has_part_files) {
                                        if (addToast) addToast('⚠️ Il modello è incompleto. Clicca "Continua" per completarlo prima del test.', 'warning');
                                        return;
                                      }
                                      setInferenceTestingModel(m);
                                    }}
                                    title="Playground inferenza con telemetria tok/s"
                                    style={{
                                      padding: '5px 10px', borderRadius: '7px',
                                      border: '1px solid rgba(0, 210, 255, 0.35)', background: 'rgba(0, 210, 255, 0.10)',
                                      color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer',
                                      display: 'flex', alignItems: 'center', gap: '4px'
                                    }}
                                  >
                                    <Gauge size={11} /> Prova
                                  </button>

                                  {/* Toggle Details Drawer Button */}
                                  <button
                                    onClick={() => toggleCardDetails(cardKey)}
                                    title={isExpanded ? 'Chiudi dettagli' : 'Apri dettagli, benchmark e opzioni HF'}
                                    style={{
                                      padding: '5px 8px', borderRadius: '7px',
                                      border: isExpanded ? '1px solid #ffb86c' : subBorder,
                                      background: isExpanded ? 'rgba(255, 184, 108, 0.12)' : subBg,
                                      color: isExpanded ? '#ffb86c' : textMuted,
                                      fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                                      display: 'flex', alignItems: 'center', gap: '3px'
                                    }}
                                  >
                                    <span>Opzioni</span>
                                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                  </button>
                                </div>
                              </div>

                              {/* ── SUB-DRAWER: DETTAGLI ESPANSIBILI ON-DEMAND ── */}
                              {isExpanded && (
                                <div style={{
                                  padding: '10px 14px',
                                  borderTop: subBorder,
                                  background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.20)',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '10px'
                                }}>
                                  {/* ROW 1: HUGGING FACE SYNC & ACTIONS */}
                                  <div style={{
                                    padding: '8px 12px', borderRadius: '8px',
                                    background: isPublished ? 'rgba(255, 184, 108, 0.08)' : subBg,
                                    border: isPublished ? '1px solid rgba(255, 184, 108, 0.25)' : subBorder,
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    gap: '10px', flexWrap: 'wrap'
                                  }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.70rem' }}>
                                      <ExternalLink size={12} color="#ffb86c" />
                                      {isPublished ? (
                                        <span>
                                          Repository HF: <a href={m.publication.url} target="_blank" rel="noreferrer" style={{ color: '#ffb86c', fontWeight: 800, textDecoration: 'none' }}>
                                            {m.publication.repo_id}
                                          </a>
                                          {m.publication.publish_count > 1 && ` · ${m.publication.publish_count} sincronizzazioni`}
                                        </span>
                                      ) : (
                                        <span style={{ color: textMuted }}>
                                          Modello non ancora pubblicato su Hugging Face
                                        </span>
                                      )}
                                    </div>

                                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
                                      {isPublished ? (
                                        <>
                                          <button
                                            onClick={() => handleUpdateCard(m)}
                                            disabled={updatingCard === (m.path || m.filename)}
                                            style={{
                                              padding: '3px 8px', borderRadius: '5px',
                                              border: '1px solid rgba(255,184,108,0.4)', background: 'transparent',
                                              color: '#ffb86c', fontSize: '0.65rem', fontWeight: 800, cursor: 'pointer'
                                            }}
                                          >
                                            {updatingCard === (m.path || m.filename) ? 'Aggiorno...' : 'Aggiorna scheda'}
                                          </button>
                                          <button
                                            onClick={() => handleRenameHfRepoFromInventory(m)}
                                            style={{
                                              padding: '3px 8px', borderRadius: '5px',
                                              border: '1px solid rgba(255,184,108,0.25)', background: 'transparent',
                                              color: '#ffb86c', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer'
                                            }}
                                          >
                                            Rinomina HF
                                          </button>
                                          <button
                                            onClick={() => handleAttachHfRepo(m)}
                                            style={{
                                              padding: '3px 8px', borderRadius: '5px',
                                              border: '1px solid rgba(0,210,255,0.3)', background: 'transparent',
                                              color: '#00d2ff', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer'
                                            }}
                                          >
                                            Modifica link
                                          </button>
                                          <button
                                            onClick={() => handleForgetPublication(m)}
                                            style={{
                                              padding: '3px 7px', borderRadius: '5px',
                                              border: subBorder, background: 'transparent',
                                              color: textMuted, fontSize: '0.65rem', fontWeight: 600, cursor: 'pointer'
                                            }}
                                          >
                                            Scollega
                                          </button>
                                        </>
                                      ) : (
                                        <button
                                          onClick={() => setPublishingModel(m)}
                                          style={{
                                            padding: '4px 10px', borderRadius: '6px',
                                            border: '1px solid rgba(255, 184, 108, 0.40)', background: 'rgba(255, 184, 108, 0.12)',
                                            color: '#ffb86c', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer',
                                            display: 'inline-flex', alignItems: 'center', gap: '4px'
                                          }}
                                        >
                                          <Upload size={11} /> Pubblica su Hugging Face
                                        </button>
                                      )}
                                    </div>
                                  </div>

                                  {/* ROW 2: BENCHMARK BREAKDOWN & TEST SUITE OUTCOMES */}
                                  {hasBenchmark && (() => {
                                    const suiteEntries = getSuiteEntries(bm);
                                    const totalPassed = bm.tests_passed ?? 0;
                                    const totalTests = bm.tests_total ?? 0;
                                    const totalFailed = bm.tests_failed ?? (totalTests > totalPassed ? totalTests - totalPassed : 0);
                                    const tokSpeed = bm.tokens_per_sec || bm.speed_tok_s || null;

                                    return (
                                      <div style={{
                                        padding: '10px 14px', borderRadius: '10px',
                                        background: isLight ? 'rgba(255, 184, 108, 0.08)' : 'linear-gradient(135deg, rgba(255, 184, 108, 0.08) 0%, rgba(16, 185, 129, 0.05) 100%)',
                                        border: '1px solid rgba(255, 184, 108, 0.28)',
                                        display: 'flex', flexDirection: 'column', gap: '8px'
                                      }}>
                                        {/* Top Benchmark Summary Line */}
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                            <div style={{
                                              width: '24px', height: '24px', borderRadius: '6px',
                                              background: 'rgba(255, 184, 108, 0.20)', display: 'flex', alignItems: 'center', justifyContent: 'center'
                                            }}>
                                              <Trophy size={13} color="#ffb86c" />
                                            </div>
                                            <span style={{ fontSize: '0.74rem', fontWeight: 900, color: textPrimary }}>
                                              Benchmark Ufficiale Training Lab:
                                            </span>
                                            <span style={{
                                              fontSize: '0.76rem', fontWeight: 900, color: bmScoreColor,
                                              padding: '2px 8px', borderRadius: '5px', background: `${bmScoreColor}20`, border: `1px solid ${bmScoreColor}40`
                                            }}>
                                              🏆 {bmScore}% Pass
                                            </span>

                                            {totalTests > 0 && (
                                              <span style={{ fontSize: '0.70rem', color: textPrimary, fontWeight: 700 }}>
                                                • <span style={{ color: '#10b981' }}>✅ {totalPassed} superati</span> su <b>{totalTests}</b> test totali
                                                {totalFailed > 0 && <span style={{ color: '#ef4444' }}> (❌ {totalFailed} non superati)</span>}
                                              </span>
                                            )}
                                          </div>

                                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.66rem', color: textMuted, flexWrap: 'wrap' }}>
                                            {bm.suite_name && <span>📊 Suite: <b>{bm.suite_name}</b></span>}
                                            {tokSpeed && <span style={{ color: '#00d2ff', fontWeight: 700 }}>• ⚡ {tokSpeed} tok/s</span>}
                                            {bm.last_run_at && <span>• ⏱️ {bm.last_run_at}</span>}
                                          </div>
                                        </div>

                                        {/* Individual Test Suite Breakdown Cards */}
                                        {suiteEntries.length > 0 && (
                                          <div style={{
                                            display: 'grid',
                                            gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                                            gap: '6px',
                                            paddingTop: '6px',
                                            borderTop: '1px solid rgba(255, 184, 108, 0.15)'
                                          }}>
                                            {suiteEntries.map(s => {
                                              const sColor = s.pct >= 75 ? '#10b981' : (s.pct >= 50 ? '#00d2ff' : '#ffb86c');
                                              return (
                                                <div
                                                  key={s.name}
                                                  style={{
                                                    padding: '6px 9px', borderRadius: '7px',
                                                    background: subBg, border: subBorder,
                                                    display: 'flex', flexDirection: 'column', gap: '4px'
                                                  }}
                                                >
                                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.64rem', fontWeight: 800 }}>
                                                    <span style={{ color: textPrimary, textTransform: 'uppercase' }}>{s.name}</span>
                                                    <span style={{ color: sColor, fontWeight: 900 }}>{s.pct}%</span>
                                                  </div>

                                                  <div style={{ height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                                                    <div style={{ width: `${Math.min(100, Math.max(0, s.pct))}%`, height: '100%', background: sColor }} />
                                                  </div>

                                                  <div style={{ fontSize: '0.58rem', color: textMuted, display: 'flex', justifyContent: 'space-between' }}>
                                                    <span>{s.passed}/{s.total} superati</span>
                                                    {s.failed > 0 && <span style={{ color: '#ef4444' }}>-{s.failed}</span>}
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })()}

                                  {/* ROW 3: FILE OPERATIONS & TECHNICAL DETAILS */}
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', fontSize: '0.68rem', color: textMuted }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                      {m.architecture && <span>🧬 Architettura: <b>{m.architecture}</b></span>}
                                      {m.added_at && <span>🕒 Aggiunto: <b>{m.added_at}</b></span>}
                                      {m.path && <span title={m.path} style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>📁 {m.path}</span>}
                                    </div>

                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                      {/* Convert GGUF Shortcut */}
                                      {(!isGguf || m.is_repo_folder) && (
                                        <button
                                          onClick={() => {
                                            if (onNavigateToConverter) {
                                              onNavigateToConverter(m.model_id || m.filename);
                                            }
                                          }}
                                          style={{
                                            padding: '4px 8px', borderRadius: '5px',
                                            border: '1px solid rgba(16, 185, 129, 0.35)', background: 'rgba(16, 185, 129, 0.10)',
                                            color: '#10b981', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer',
                                            display: 'inline-flex', alignItems: 'center', gap: '3px'
                                          }}
                                        >
                                          <Package size={11} /> Converti GGUF
                                        </button>
                                      )}

                                      {/* Rename */}
                                      <button
                                        onClick={() => handleRenameModel(m)}
                                        disabled={renamingPath === (m.path || m.filename)}
                                        style={{
                                          padding: '4px 8px', borderRadius: '5px',
                                          border: subBorder, background: subBg,
                                          color: textMuted, fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                                          display: 'inline-flex', alignItems: 'center', gap: '3px'
                                        }}
                                      >
                                        <Pencil size={11} /> Rinomina
                                      </button>

                                      {/* Delete */}
                                      <button
                                        onClick={() => handleDeleteModel(m)}
                                        disabled={deletingPath === (m.path || m.filename)}
                                        style={{
                                          padding: '4px 8px', borderRadius: '5px',
                                          border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)',
                                          color: '#ef4444', fontSize: '0.66rem', fontWeight: 700, cursor: 'pointer',
                                          display: 'inline-flex', alignItems: 'center', gap: '3px'
                                        }}
                                      >
                                        <Trash2 size={11} /> Elimina
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
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
