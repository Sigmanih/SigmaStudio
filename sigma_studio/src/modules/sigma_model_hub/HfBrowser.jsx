import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import {
  Search, Download, Star, ArrowDown, Sparkles, Filter, CheckCircle2,
  Layers, Cpu, Activity, ExternalLink, HardDrive, ArrowUpDown, ChevronDown, ChevronUp,
  Calendar, RefreshCw, PlusCircle, ShieldCheck, FolderDown, FileCode, ArrowUp,
  XCircle, Zap, RotateCcw, X, AlertTriangle, Sliders, Globe, Brain, Shield, Flame, Boxes
} from 'lucide-react';

const CATEGORIES = [
  { id: 'all', label: 'Tutte le Categorie' },
  { id: 'reasoning', label: '🧠 Reasoning (DeepSeek R1 / O1)' },
  { id: 'llm', label: '💬 LLM Conversazionali (Chat / Instruct)' },
  { id: 'code', label: '💻 Coding & Agenti (Coder)' },
  { id: 'moe', label: '⚡ MoE Sharded (Architetture MoE)' },
  { id: 'vision', label: '👁️ Vision & Multimodale (VLM / OCR)' },
  { id: 'audio', label: '🎙️ Audio & Voice (Whisper / TTS)' },
];

const SIZE_BRACKETS = [
  { id: 'all', label: 'Tutti i Pesi (All GB)', maxGb: null },
  { id: 'under_4gb', label: '🟢 < 4 GB (Leggero • CPU / NPU)', maxGb: 4 },
  { id: '4_8gb', label: '🔵 4 - 8 GB', maxGb: 8 },
  { id: '8_16gb', label: '🟣 8 - 16 GB', maxGb: 16 },
  { id: '16_32gb', label: '🟡 16 - 32 GB', maxGb: 32 },
  { id: '32_48gb', label: '🟠 32 - 48 GB (es. 70B Q4)', maxGb: 48 },
  { id: '48_70gb', label: '🔴 48 - 70 GB (70B Q8 / MoE)', maxGb: 70 },
  { id: '70_140gb', label: '🟣 70 - 140 GB (MoE di grandi dimensioni)', maxGb: 140 },
  { id: 'over_140gb', label: '🔮 > 140 GB (Sharding multi-tier)', maxGb: null },
];

const FIT_HEADROOM = 1.15;

function annotateBrackets(brackets, totalVramGb) {
  if (!totalVramGb) return brackets;
  return brackets.map(b => (
    b.maxGb && b.maxGb * FIT_HEADROOM <= totalVramGb
      ? { ...b, label: `${b.label} ✓ VRAM` }
      : b
  ));
}

const PARAM_BRACKETS = [
  { id: 'all', label: 'Tutti i Parametri' },
  { id: 'under_3b', label: 'Micro (< 3B)' },
  { id: '7b_8b', label: '7B - 8B' },
  { id: '12b_14b', label: '12B - 14B' },
  { id: '27b_34b', label: '27B - 34B' },
  { id: '70b_plus', label: '70B+ & MoE Sharded' },
];

const FORMAT_OPTIONS = [
  { id: 'all', label: 'Tutti i Formati (GGUF + Safetensors)' },
  { id: 'gguf', label: '⚡ Solo GGUF (llama.cpp)' },
  { id: 'safetensors', label: '📦 Solo Safetensors (FP16 / FP8 / HF)' },
];

const QUANT_OPTIONS = [
  { id: 'all', label: 'Tutte le Quantizzazioni' },
  { id: 'q4_k_m', label: '⚡ Q4_K_M (4-bit • Consigliato)' },
  { id: 'q5_k_m', label: '⚡ Q5_K_M (5-bit • Alta Fedeltà)' },
  { id: 'q8_0', label: '⚡ Q8_0 (8-bit • Quasi-Lossless)' },
  { id: 'q4_k_s', label: '⚡ Q4_K_S (4-bit • Leggero)' },
  { id: 'q6_k', label: '⚡ Q6_K (6-bit • Bilanciato)' },
  { id: 'q3_k_m', label: '⚡ Q3_K_M (3-bit • Basso VRAM)' },
  { id: 'q2_k', label: '⚡ Q2_K (2-bit • Ultra-Compatto)' },
  { id: 'imatrix', label: '⚡ iMatrix (IQ4 / IQ3 / IQ2)' },
  { id: 'fp8', label: '📦 FP8 / W8A8 (8-bit Ada/Blackwell)' },
  { id: 'nvfp4', label: '📦 NVFP4 / FP4 (4-bit Blackwell)' },
  { id: 'awq_gptq', label: '📦 AWQ / GPTQ (4-bit GPU)' },
  { id: 'fp16_bf16', label: '📦 FP16 / BF16 (16-bit Piena Precisione)' },
];

const SORT_OPTIONS = [
  { id: 'newest', label: '✨ Nuove Uscite / Più Recenti' },
  { id: 'downloads', label: '📥 Più Scaricati (Downloads)' },
  { id: 'likes', label: '⭐ Più Popolari (Likes)' },
  { id: 'size_asc', label: '💾 Peso Minore prima (GB ↑)' },
  { id: 'size_desc', label: '💾 Peso Maggiore prima (GB ↓)' },
];

const KNOWN_SECTOR_META = {
  sigmanih: { label: '✨ Sigmanih', icon: Sparkles, color: '#ffb86c' },
  google: { label: '💎 Google / Gemma', icon: Sparkles, color: '#ec4899' },
  gemma: { label: '💎 Google / Gemma', icon: Sparkles, color: '#ec4899' },
  qwen: { label: '⚡ Qwen', icon: Cpu, color: '#10b981' },
  'meta-llama': { label: '🦙 Meta Llama', icon: Shield, color: '#818cf8' },
  llama: { label: '🦙 Meta Llama', icon: Shield, color: '#818cf8' },
  'deepseek-ai': { label: '🧠 DeepSeek', icon: Brain, color: '#00d2ff' },
  deepseek: { label: '🧠 DeepSeek', icon: Brain, color: '#00d2ff' },
  mistralai: { label: '⚡ Mistral', icon: Zap, color: '#f59e0b' },
  mistral: { label: '⚡ Mistral', icon: Zap, color: '#f59e0b' },
  microsoft: { label: '🔷 Phi / Microsoft', icon: Layers, color: '#60a5fa' },
  phi: { label: '🔷 Phi / Microsoft', icon: Layers, color: '#60a5fa' },
  'zai-org': { label: '🏮 GLM / ZAI', icon: Flame, color: '#f43f5e' },
  zai: { label: '🏮 GLM / ZAI', icon: Flame, color: '#f43f5e' },
  thudm: { label: '🏮 THUDM / GLM', icon: Flame, color: '#f43f5e' },
  glm: { label: '🏮 GLM / ZAI', icon: Flame, color: '#f43f5e' },
  nvidia: { label: '🟢 NVIDIA', icon: Cpu, color: '#76b900' },
  apple: { label: '🍎 Apple', icon: Sparkles, color: '#a3a3a3' },
  openai: { label: '🤖 OpenAI', icon: Brain, color: '#10a37f' },
  stabilityai: { label: '🎨 Stability AI', icon: Sparkles, color: '#8b5cf6' },
  '01-ai': { label: '🌟 01.AI (Yi)', icon: Sparkles, color: '#38bdf8' },
  internlm: { label: '🌐 InternLM', icon: Globe, color: '#06b6d4' },
  tiiuae: { label: '🦅 Falcon / TII', icon: Shield, color: '#eab308' },
  allenai: { label: '🔬 AllenAI (OLMo)', icon: Brain, color: '#f97316' },
  'black-forest-labs': { label: '🌌 FLUX / BFL', icon: Sparkles, color: '#f43f5e' },
};

const getProviderBadge = (m, officialPublishers = []) => {
  if (!m) return null;
  const auth = (m.author || (m.id && m.id.includes('/') ? m.id.split('/')[0] : '')).toLowerCase().trim();
  const id = (m.id || '').toLowerCase().trim();
  const org = id.includes('/') ? id.split('/')[0] : auth;

  if (auth === 'sigmanih' || id.startsWith('sigmanih/')) {
    return {
      label: '⚡ Sigmanih Ufficiale',
      color: '#ffb86c',
      bg: 'rgba(255, 184, 108, 0.18)',
      border: '1px solid rgba(255, 184, 108, 0.45)'
    };
  }

  const isCustomFavorite = (officialPublishers || []).some(
    p => p.toLowerCase() === org || p.toLowerCase() === auth
  );

  if (isCustomFavorite || m.is_favorite || m.is_official) {
    const displayName = m.author || org;
    return {
      label: `⭐ ${displayName}`,
      color: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.15)',
      border: '1px solid rgba(245, 158, 11, 0.40)'
    };
  }

  const known = KNOWN_SECTOR_META[org] || KNOWN_SECTOR_META[auth];
  if (known) {
    return {
      label: known.label,
      color: known.color,
      bg: `${known.color}22`,
      border: `1px solid ${known.color}55`
    };
  }

  return null;
};

const getModelTargetQuantLabel = (m, preferredQuant = 'Q4_K_M', activeFilterQuant = 'all') => {
  if (!m) return 'Modello';
  const text = `${m.id || ''} ${m.name || ''} ${m.precision || ''} ${m.default_file || ''}`.toUpperCase().replace(/-/g, '_');

  if (text.includes('Q8_0') || text.includes('Q8_K') || text.includes('Q80')) return 'Q8_0';
  if (text.includes('Q5_K_M') || text.includes('Q5KM')) return 'Q5_K_M';
  if (text.includes('Q5_K_S') || text.includes('Q5KS')) return 'Q5_K_S';
  if (text.includes('Q5_0') || text.includes('Q5_1')) return 'Q5_0';
  if (text.includes('Q4_K_M') || text.includes('Q4KM')) return 'Q4_K_M';
  if (text.includes('Q4_K_S') || text.includes('Q4KS')) return 'Q4_K_S';
  if (text.includes('Q4_0') || text.includes('Q4_1')) return 'Q4_0';
  if (text.includes('Q6_K') || text.includes('Q6K')) return 'Q6_K';
  if (text.includes('Q3_K_M') || text.includes('Q3KM')) return 'Q3_K_M';
  if (text.includes('Q3_K_S') || text.includes('Q3KS')) return 'Q3_K_S';
  if (text.includes('Q3_K_L') || text.includes('Q3KL')) return 'Q3_K_L';
  if (text.includes('Q2_K') || text.includes('Q2K')) return 'Q2_K';
  if (text.includes('IQ4_XS') || text.includes('IQ4_NL') || text.includes('IQ4')) return 'IQ4';
  if (text.includes('IQ3_M') || text.includes('IQ3_XXS') || text.includes('IQ3')) return 'IQ3';
  if (text.includes('IQ2_XXS') || text.includes('IQ2_XS') || text.includes('IQ2')) return 'IQ2';
  if (text.includes('NVFP4') || text.includes('MXFP4')) return 'NVFP4';
  if (text.includes('FP8') || text.includes('W8A8')) return 'FP8';
  if (text.includes('AWQ')) return 'AWQ';
  if (text.includes('GPTQ')) return 'GPTQ';
  if (text.includes('EXL2')) return 'EXL2';
  if (text.includes('BF16') || text.includes('BFLOAT16')) return 'BF16';
  if (text.includes('FP16') || text.includes('FLOAT16')) return 'FP16';

  if (activeFilterQuant && activeFilterQuant !== 'all') {
    return activeFilterQuant.toUpperCase();
  }

  if ((m.format && m.format.toUpperCase().includes('GGUF')) || (m.precision && m.precision.toUpperCase().includes('GGUF')) || text.includes('GGUF')) {
    return preferredQuant || 'Q4_K_M';
  }

  return 'Modello';
};

// Helper to normalize model strings for robust comparison between Hugging Face repo IDs and local inventory names
const normalizeModelKey = (s) => {
  if (!s) return '';
  let str = String(s).toLowerCase().trim();
  str = str.replace(/\.gguf$/i, '').replace(/\.bin$/i, '').replace(/\.safetensors$/i, '');
  str = str.replace(/[\/\\_]/g, '-').replace(/--+/g, '-');
  while (str.includes('--')) {
    str = str.replace(/--/g, '-');
  }
  return str.replace(/^-+|-+$/g, '');
};

const checkIsModelLocal = (m, localList = []) => {
  if (!m || !localList || localList.length === 0) return null;

  const mId = (m.id || '').toLowerCase().trim();
  const mSlug = (mId.includes('/') ? mId.split('/').slice(1).join('/') : mId).toLowerCase().trim();
  const mNormFull = normalizeModelKey(mId);
  const mNormSlug = normalizeModelKey(mSlug);

  return localList.find(loc => {
    const locId = (loc.model_id || '').toLowerCase().trim();
    const locFile = (loc.filename || '').toLowerCase().trim();
    const locClean = (loc.clean_name || '').toLowerCase().trim();
    const locPub = (loc.publication?.repo_id || '').toLowerCase().trim();

    // 1. Direct publication repo_id match
    if (locPub && (locPub === mId || locPub.endsWith(`/${mSlug}`))) return true;

    // 2. Direct model_id match
    if (locId && (locId === mId || locId === mSlug || locId.endsWith(`/${mSlug}`))) return true;

    // 3. Exact normalized matches
    const locNormId = normalizeModelKey(locId);
    const locNormFile = normalizeModelKey(locFile);
    const locNormClean = normalizeModelKey(locClean);
    const locNormPub = normalizeModelKey(locPub);

    if (locNormPub && (locNormPub === mNormFull || locNormPub === mNormSlug)) return true;
    if (locNormId && (locNormId === mNormFull || locNormId === mNormSlug)) return true;
    if (locNormFile && (locNormFile === mNormFull || locNormFile === mNormSlug)) return true;
    if (locNormClean && (locNormClean === mNormFull || locNormClean === mNormSlug)) return true;

    // 4. EndsWith / startsWith match
    if (locNormFile && (locNormFile.endsWith(mNormSlug) || mNormFull.endsWith(locNormFile))) return true;
    if (locNormClean && (locNormClean.endsWith(mNormSlug) || mNormSlug.endsWith(locNormClean))) return true;
    if (locNormId && (locNormId.endsWith(mNormSlug) || mNormFull.endsWith(locNormId))) return true;

    // 5. Check if multi-file repo has any file matching local model
    if (Array.isArray(loc.files) && loc.files.some(f => {
      const fNorm = normalizeModelKey(f);
      return fNorm === mNormSlug || fNorm.includes(mNormSlug) || mNormSlug.includes(fNorm);
    })) return true;

    return false;
  }) || null;
};

const checkIsFileLocal = (fileName, localList = []) => {
  if (!fileName || !localList || localList.length === 0) return false;
  const fNorm = normalizeModelKey(fileName.split('/').pop());
  return localList.some(loc => {
    const locFileNorm = normalizeModelKey(loc.filename?.split('/').pop());
    const locCleanNorm = normalizeModelKey(loc.clean_name);
    const locIdNorm = normalizeModelKey(loc.model_id?.split('/').pop());
    return locFileNorm === fNorm || locCleanNorm === fNorm || locIdNorm === fNorm || (fNorm && locFileNorm.endsWith(fNorm));
  });
};

export default function HfBrowser({ isLight, addToast, onDownloadStarted, activeDownloads = [], officialPublishers = [], localModels = [] }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sizeBracket, setSizeBracket] = useState('all');
  const [paramBracket, setParamBracket] = useState('all');
  const [formatFilter, setFormatFilter] = useState('all');
  const [quantFilter, setQuantFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  // Filtro Da Preferiti (false di default per permettere ricerca aperta su tutto HF)
  const [officialOnly, setOfficialOnly] = useState(false);
  // Stato visibilità filtri secondari su Mobile
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  // Local Inventory Cache & Poll
  const [internalLocalModels, setInternalLocalModels] = useState([]);
  const fetchLocalInventory = useCallback(async () => {
    try {
      const res = await fetch('/api/models/local/list');
      if (res.ok) {
        const json = await res.json();
        if (json.success && Array.isArray(json.models)) {
          setInternalLocalModels(json.models);
        }
      }
    } catch (e) {
      console.debug("Local models fetch in HfBrowser:", e);
    }
  }, []);

  useEffect(() => {
    fetchLocalInventory();
  }, [fetchLocalInventory, activeDownloads]);

  const effectiveLocalModels = (localModels && localModels.length > 0) ? localModels : internalLocalModels;



  const [results, setResults] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  const [loadingMore, setLoadingMore] = useState(false);
  const [loadedPagesCount, setLoadedPagesCount] = useState(1);

  // Expanded card options drawers
  const [expandedCards, setExpandedCards] = useState(new Set());
  const [modelDetailsMap, setModelDetailsMap] = useState({});
  const [loadingDetailsId, setLoadingDetailsId] = useState(null);
  const [selectedQuantMap, setSelectedQuantMap] = useState({});

  const [downloadingFile, setDownloadingFile] = useState(null);
  const [downloadingRepo, setDownloadingRepo] = useState(false);

  // Total VRAM measured on this machine
  const [totalVramGb, setTotalVramGb] = useState(0);

  useEffect(() => {
    fetch('/api/hardware/status')
      .then(r => r.json())
      .then(data => {
        const gpus = data?.hardware?.gpu || [];
        const total = gpus
          .filter(g => !g.is_integrated && g.vram_total_mb)
          .reduce((sum, g) => sum + g.vram_total_mb / 1024, 0);
        setTotalVramGb(Math.round(total * 10) / 10);
      })
      .catch(() => setTotalVramGb(0));
  }, []);

  const sizeBrackets = annotateBrackets(SIZE_BRACKETS, totalVramGb);
  const topRef = useRef(null);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const hasActiveFilters = category !== 'all' || sizeBracket !== 'all' || paramBracket !== 'all' || formatFilter !== 'all' || quantFilter !== 'all' || officialOnly || search.trim() !== '';

  const handleResetFilters = () => {
    setSearch('');
    setCategory('all');
    setSizeBracket('all');
    setParamBracket('all');
    setFormatFilter('all');
    setQuantFilter('all');
    setOfficialOnly(false);
  };

  // Dynamic Live Query with debounce
  const fetchModels = useCallback(async (targetCursor = null, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setLoadedPagesCount(1);
    }

    try {
      const q = encodeURIComponent(search);
      let url = `/api/models/hf/search?q=${q}&category=${category}&size_bracket=${sizeBracket}&param_bracket=${paramBracket}&format_filter=${formatFilter}&quant_filter=${quantFilter}&sort=${sortBy}&official_only=${officialOnly}&limit=30`;
      if (targetCursor) {
        url += `&cursor=${encodeURIComponent(targetCursor)}`;
      }

      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          const list = json.results || [];
          if (append) {
            setResults(prev => {
              const existingIds = new Set(prev.map(p => p.id));
              const uniqueNew = list.filter(item => !existingIds.has(item.id));
              return [...prev, ...uniqueNew];
            });
            setLoadedPagesCount(c => c + 1);
          } else {
            setResults(list);
          }
          setNextCursor(json.next_cursor || null);
          setHasMore(Boolean(json.next_cursor) || (list.length >= 20 && json.has_more));
        }
      }
    } catch (e) {
      console.error('Error fetching dynamic HF models:', e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [search, category, sizeBracket, paramBracket, formatFilter, quantFilter, sortBy, officialOnly]);

  // Trigger dynamic query on filter change with smooth debounce
  useEffect(() => {
    const delay = setTimeout(() => {
      fetchModels(null, false);
    }, 220);
    return () => clearTimeout(delay);
  }, [fetchModels]);

  const handleLoadMore = () => {
    if (!loadingMore && nextCursor) {
      fetchModels(nextCursor, true);
    }
  };

  const scrollToTop = () => {
    topRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadModelDetails = async (modelId) => {
    if (modelDetailsMap[modelId]) return modelDetailsMap[modelId];
    setLoadingDetailsId(modelId);
    try {
      const res = await fetch(`/api/models/hf/details?model_id=${encodeURIComponent(modelId)}`);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setModelDetailsMap(prev => ({ ...prev, [modelId]: json }));
          const ggufFiles = (json.files || []).filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf'));
          if (ggufFiles.length > 0) {
            const preferred = ggufFiles.find(f => f.filename?.toLowerCase().includes('q4_k_m') || f.filename?.toLowerCase().includes('q4-k-m'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q4_k_s') || f.filename?.toLowerCase().includes('q4-k-s'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q5_k_m') || f.filename?.toLowerCase().includes('q5-k-m'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q8_0') || f.filename?.toLowerCase().includes('q8-0'))
              || ggufFiles[0];
            if (preferred) {
              setSelectedQuantMap(prev => ({ ...prev, [modelId]: preferred.filename }));
            }
          }
          return json;
        }
      }
    } catch (e) {
      console.error('Error fetching model details:', e);
    } finally {
      setLoadingDetailsId(null);
    }
    return null;
  };

  const toggleCardDetails = (m) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(m.id)) {
        next.delete(m.id);
      } else {
        next.add(m.id);
        loadModelDetails(m.id);
      }
      return next;
    });
  };

  const handleStartSingleDownload = async (modelId, filename, downloadUrl) => {
    setDownloadingFile(filename);
    try {
      const res = await fetch('/api/models/hf/download/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: modelId,
          filename: filename,
          download_url: downloadUrl
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`📥 Download avviato: ${filename}`, 'success');
        if (onDownloadStarted) onDownloadStarted(json.task);
      } else {
        if (addToast) addToast(`❌ Errore: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`❌ Errore di rete: ${e.message}`, 'error');
    } finally {
      setDownloadingFile(null);
    }
  };

  const handleStartWholeRepoDownload = async (modelId, filesList = null) => {
    setDownloadingRepo(true);
    try {
      const res = await fetch('/api/models/hf/download/repo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: modelId,
          files: filesList
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🚀 Download avviato per l'intero modello ${modelId}! Mostro progresso in tempo reale.`, 'success');
        if (onDownloadStarted) onDownloadStarted(json.task);
      } else {
        if (addToast) addToast(`❌ Errore: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`❌ Errore di rete: ${e.message}`, 'error');
    } finally {
      setDownloadingRepo(false);
    }
  };

  const handleRetryDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🚀 Ripresa del download in corso dai file salvati su disco!`, 'success');
        if (onDownloadStarted) onDownloadStarted(json.task);
      } else {
        if (addToast) addToast(`Errore ripresa: ${json.error}`, 'error');
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
        if (addToast) addToast(`Download annullato. File parziali preservati su disco.`, 'info');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', position: 'relative' }}>
      <div ref={topRef} />




      {/* 2. MODERN COMPACT SEARCH & FILTER TOOLBAR */}
      <div
        className="mh-sticky-filters"
        style={{
          padding: '12px 16px', borderRadius: '14px',
          background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
          border: cardBorder,
          display: 'flex', flexDirection: 'column', gap: '10px',
          boxShadow: isLight ? '0 2px 14px rgba(0,0,0,0.04)' : '0 6px 24px rgba(0,0,0,0.40)'
        }}
      >
        {/* Top Row: Hero Search Input + "Solo Ufficiali" Checkbox + Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div
            className="mh-search-hero"
            style={{
              background: subBg, border: subBorder, flex: 1, minWidth: '240px', padding: '7px 12px'
            }}
          >
            <Search size={16} color="#ffb86c" style={{ flexShrink: 0 }} />
            <input
              type="text"
              placeholder="Cerca qualsiasi modello Hugging Face in tempo reale (es. Qwen, DeepSeek-R1, Gemma, Llama-3.3)..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                background: 'transparent', border: 'none',
                color: textPrimary, fontSize: '0.82rem', outline: 'none', width: '100%'
              }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: 0 }}
                title="Cancella ricerca"
              >
                <X size={15} />
              </button>
            )}
          </div>

          {/* "Da Preferiti" Button Toggle */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '8px 14px', borderRadius: '10px',
            background: officialOnly ? (isLight ? 'rgba(245, 158, 11, 0.12)' : 'rgba(245, 158, 11, 0.18)') : subBg,
            border: officialOnly ? '1.5px solid #f59e0b' : subBorder,
            boxShadow: officialOnly ? '0 0 10px rgba(245, 158, 11, 0.25)' : 'none',
            cursor: 'pointer', userSelect: 'none', transition: 'all 0.15s ease'
          }}>
            <input
              type="checkbox"
              checked={officialOnly}
              onChange={e => setOfficialOnly(e.target.checked)}
              style={{ accentColor: '#f59e0b', cursor: 'pointer' }}
            />
            <Star size={15} color={officialOnly ? '#f59e0b' : textMuted} fill={officialOnly ? '#f59e0b' : 'none'} />
            <span style={{ fontSize: '0.78rem', fontWeight: 800, color: officialOnly ? '#f59e0b' : textPrimary }}>
              Da Preferiti
            </span>
          </label>
 
          {/* Mobile Filters Toggle Button */}
          <button
            type="button"
            className="mh-mobile-filters-toggle-btn"
            onClick={() => setShowMobileFilters(prev => !prev)}
            title="Mostra / Nascondi filtri avanzati"
          >
            <Sliders size={13} />
            <span>Filtri</span>
            {hasActiveFilters && (
              <span className="mh-mobile-filters-dot" />
            )}
            <ChevronDown size={12} style={{ transform: showMobileFilters ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }} />
          </button>

          {/* Reset Filters Button */}
          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                padding: '8px 12px', borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.10)', border: '1px solid rgba(239, 68, 68, 0.25)',
                color: '#ef4444', fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer'
              }}
              title="Reimposta tutti i filtri ai valori predefiniti"
            >
              <RotateCcw size={12} /> Reset
            </button>
          )}
        </div>

        {/* Bottom Row: 5 Clean Select Dropdowns (Category, Size, Params, Format, Quant, Sort) */}
        <div className={`mh-filter-selects-grid ${showMobileFilters ? 'mobile-open' : ''}`}>
          {/* 1. CATEGORIA */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: textMuted }}>
              <Layers size={10} color="#ffb86c" /> Categoria
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                style={{ color: textPrimary }}
              >
                {CATEGORIES.map(c => (
                  <option key={c.id} value={c.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {c.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 2. FASCIA PESO GB */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#ffb86c' }}>
              <HardDrive size={10} color="#ffb86c" /> Fascia Peso GB
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={sizeBracket}
                onChange={e => setSizeBracket(e.target.value)}
                style={{ color: textPrimary }}
              >
                {sizeBrackets.map(b => (
                  <option key={b.id} value={b.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {b.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 3. PARAMETRI */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#00d2ff' }}>
              <Cpu size={10} color="#00d2ff" /> Parametri
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={paramBracket}
                onChange={e => setParamBracket(e.target.value)}
                style={{ color: textPrimary }}
              >
                {PARAM_BRACKETS.map(p => (
                  <option key={p.id} value={p.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {p.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 4. FORMATO PESI */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#10b981' }}>
              <FileCode size={10} color="#10b981" /> Formato Pesi
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={formatFilter}
                onChange={e => setFormatFilter(e.target.value)}
                style={{ color: textPrimary }}
              >
                {FORMAT_OPTIONS.map(f => (
                  <option key={f.id} value={f.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {f.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 5. TIPO QUANTIZZAZIONE */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#00d2ff' }}>
              <Sliders size={10} color="#00d2ff" /> Quantizzazione
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={quantFilter}
                onChange={e => setQuantFilter(e.target.value)}
                style={{ color: textPrimary }}
              >
                {QUANT_OPTIONS.map(q => (
                  <option key={q.id} value={q.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {q.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 6. ORDINAMENTO */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#bc8cff' }}>
              <ArrowUpDown size={10} color="#bc8cff" /> Ordina Per
            </span>
            <div className="mh-select-wrapper" style={{ background: subBg, border: subBorder }}>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                style={{ color: textPrimary }}
              >
                {SORT_OPTIONS.map(s => (
                  <option key={s.id} value={s.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                    {s.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} className="mh-select-icon" color={textMuted} />
            </div>
          </div>
        </div>
      </div>

      {/* 3. STATS STRIP */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 4px', fontSize: '0.72rem', color: textMuted
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 800, color: textPrimary }}>
            Modelli trovati: <b>{results.length}</b>
          </span>
          <span>•</span>
          <span>{loadedPagesCount} {loadedPagesCount === 1 ? 'blocco' : 'blocchi'} caricati</span>
          {officialOnly && (
            <span style={{ fontSize: '0.66rem', color: '#f59e0b', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
              <Star size={11} fill="#f59e0b" /> Da Creator Preferiti
            </span>
          )}
        </div>

        {results.length > 20 && (
          <button
            onClick={scrollToTop}
            style={{
              background: subBg, border: subBorder, borderRadius: '6px',
              padding: '3px 8px', color: textPrimary, fontSize: '0.68rem',
              fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px'
            }}
          >
            <ArrowUp size={11} /> Torna su
          </button>
        )}
      </div>

      {/* 4. DYNAMIC LIVE COMPACT MODELS LIST */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px 20px', color: textMuted }}>
          <Activity className="mh-spin" size={22} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
          <span style={{ fontSize: '0.78rem' }}>Ricerca live in corso su Hugging Face Hub...</span>
        </div>
      ) : results.length === 0 ? (
        <div style={{
          padding: '40px 20px', borderRadius: '14px', background: cardBg, border: cardBorder,
          textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px'
        }}>
          <HardDrive size={26} color="#bc8cff" />
          <div style={{ fontSize: '0.84rem', fontWeight: 800, color: textPrimary }}>
            Nessun modello trovato per i filtri selezionati.
          </div>
          <div style={{ fontSize: '0.72rem' }}>
            Prova a disattivare "Da Preferiti" o a selezionare "Tutti i Pesi".
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {results.map((m, idx) => {
            const isExpanded = expandedCards.has(m.id);
            const details = modelDetailsMap[m.id];
            const isLoadingDetails = loadingDetailsId === m.id;
            const targetQuant = getModelTargetQuantLabel(m, 'Q4_K_M', quantFilter);
            const isGguf = (m.format?.toLowerCase().includes('gguf') || m.precision?.toLowerCase().includes('gguf') || m.id.toLowerCase().includes('gguf') || targetQuant.startsWith('Q') || targetQuant.startsWith('IQ'));
            const pBadge = getProviderBadge(m, officialPublishers);
            const isSigmanih = (m.author || '').toLowerCase() === 'sigmanih' || m.id.toLowerCase().startsWith('sigmanih/');

            // Local Inventory Matching Check
            const localMatch = checkIsModelLocal(m, effectiveLocalModels);
            const isLocallyInstalled = !!localMatch;

            // Active / Completed / Failed Task Check
            const activeTask = activeDownloads.find(t => t.model_id === m.id && (t.status === 'downloading' || t.status === 'queued'));
            const completedTask = activeDownloads.find(t => t.model_id === m.id && t.status === 'completed');
            const failedTask = activeDownloads.find(t => t.model_id === m.id && (t.status === 'failed' || t.status === 'cancelled'));

            return (
              <div
                key={m.id || idx}
                style={{
                  borderRadius: '10px',
                  background: activeTask
                    ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.12) 0%, rgba(15, 18, 28, 0.92) 100%)')
                    : (isSigmanih
                      ? (isLight ? 'linear-gradient(135deg, #ffffff 0%, #fffcf5 100%)' : 'linear-gradient(135deg, rgba(22, 26, 40, 0.90) 0%, rgba(15, 18, 28, 0.95) 100%)')
                      : cardBg),
                  border: activeTask
                    ? '1.5px solid #00d2ff'
                    : (isLocallyInstalled
                      ? (isLight ? '1.5px solid rgba(16, 185, 129, 0.45)' : '1.5px solid rgba(16, 185, 129, 0.35)')
                      : (failedTask ? '1.5px solid rgba(239, 68, 68, 0.4)' : (isSigmanih ? '1px solid rgba(255, 184, 108, 0.35)' : cardBorder))),
                  boxShadow: activeTask ? '0 0 14px rgba(0, 210, 255, 0.18)' : (isLocallyInstalled ? '0 0 10px rgba(16, 185, 129, 0.08)' : 'none'),
                  overflow: 'hidden',
                  transition: 'all 0.15s ease'
                }}
              >
                {/* ── ROW PRINCIPALE COMPATTA ── */}
                <div style={{
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px',
                  flexWrap: 'wrap'
                }}>
                  {/* Left Side: Badges + Model Name + Specs */}
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
                    ) : pBadge ? (
                      <span style={{
                        fontSize: '0.58rem', fontWeight: 800, padding: '2px 6px', borderRadius: '5px',
                        background: pBadge.bg, color: pBadge.color, border: pBadge.border,
                        display: 'inline-flex', alignItems: 'center', gap: '3px'
                      }}>
                        <Star size={9} fill={pBadge.color} /> {pBadge.label}
                      </span>
                    ) : (
                      <span style={{
                        fontSize: '0.58rem', fontWeight: 700, padding: '2px 5px', borderRadius: '4px',
                        background: subBg, border: subBorder, color: textMuted
                      }}>
                        {m.author || (m.id.includes('/') ? m.id.split('/')[0] : 'Community')}
                      </span>
                    )}

                    {/* Local Inventory Installed Badge */}
                    {isLocallyInstalled && (
                      <span style={{
                        fontSize: '0.60rem', fontWeight: 900, padding: '2px 7px', borderRadius: '5px',
                        background: 'rgba(16, 185, 129, 0.18)', color: '#10b981',
                        border: '1px solid rgba(16, 185, 129, 0.45)',
                        display: 'inline-flex', alignItems: 'center', gap: '3px',
                        boxShadow: '0 0 8px rgba(16, 185, 129, 0.2)'
                      }}>
                        <CheckCircle2 size={10} color="#10b981" /> IN LOCALE
                      </span>
                    )}

                    {/* Model Title */}
                    <span
                      style={{
                        fontSize: '0.84rem', fontWeight: 800, color: textPrimary,
                        letterSpacing: '-0.01em', wordBreak: 'break-all'
                      }}
                      title={m.name || m.id}
                    >
                      {m.name || m.id}
                    </span>

                    {/* Format / Target Quant Pill */}
                    <span style={{
                      fontSize: '0.58rem', fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                      background: isGguf ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                      color: isGguf ? '#10b981' : '#00d2ff',
                      border: isGguf ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)'
                    }}>
                      {targetQuant !== 'Modello' ? `GGUF ${targetQuant}` : (m.precision || (isGguf ? 'GGUF' : 'SAFETENSORS'))}
                    </span>

                    {/* Storage & VRAM metrics */}
                    <span style={{ fontSize: '0.68rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span>💾 <b>{m.size_label || (m.size_gb >= 1000 ? `~${(m.size_gb / 1000).toFixed(1)} TB` : `~${m.size_gb} GB`)}</b></span>
                      <span>•</span>
                      <span style={{ color: isLight ? '#0284c7' : '#00d2ff' }}>⚡ VRAM: <b>{m.active_vram_label || `~${m.active_vram_gb || 8} GB`}</b></span>
                    </span>

                    {/* Release Date */}
                    {m.release_date_label && (
                      <span style={{
                        fontSize: '0.58rem', padding: '1px 6px', borderRadius: '4px',
                        background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255, 255, 255, 0.06)',
                        border: subBorder, color: textMuted, fontWeight: 700
                      }}>
                        📅 {m.release_date_label}
                      </span>
                    )}

                    {/* Likes & Downloads */}
                    <span style={{ fontSize: '0.62rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span>⭐ {m.likes || 0}</span>
                      <span>📥 {m.downloads > 1000 ? `${Math.round(m.downloads / 1000)}k` : (m.downloads || 0)}</span>
                    </span>
                  </div>

                  {/* Right Side: Actions Strip */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                    {/* Live in-row download progress */}
                    {activeTask ? (
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '4px 10px', borderRadius: '7px',
                        background: 'rgba(0, 210, 255, 0.12)', border: '1px solid #00d2ff'
                      }}>
                        <Activity className="mh-spin" size={12} color="#00d2ff" />
                        <span style={{ fontSize: '0.68rem', fontWeight: 900, color: '#00d2ff' }}>
                          {activeTask.progress_pct}% ({activeTask.speed_mbps} MB/s)
                        </span>
                        <button
                          onClick={() => handleCancelDownload(activeTask.task_id)}
                          style={{
                            background: 'none', border: 'none', color: '#ef4444',
                            fontSize: '0.64rem', fontWeight: 800, cursor: 'pointer', padding: '0 2px'
                          }}
                        >
                          Annulla
                        </button>
                      </div>
                    ) : failedTask ? (
                      <button
                        onClick={() => handleRetryDownload(failedTask.task_id)}
                        style={{
                          padding: '5px 10px', borderRadius: '7px',
                          border: 'none', background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                          color: '#ffffff', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px'
                        }}
                      >
                        <RotateCcw size={11} /> Riprendi
                      </button>
                    ) : isLocallyInstalled ? (
                      <div style={{
                        padding: '4px 10px', borderRadius: '7px',
                        background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981',
                        color: '#10b981', fontSize: '0.68rem', fontWeight: 800,
                        display: 'inline-flex', alignItems: 'center', gap: '4px'
                      }}>
                        <CheckCircle2 size={12} color="#10b981" />
                        <span>Già in Locale</span>
                      </div>
                    ) : completedTask ? (
                      <span style={{
                        fontSize: '0.68rem', fontWeight: 800, padding: '4px 9px', borderRadius: '6px',
                        background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#10b981',
                        display: 'inline-flex', alignItems: 'center', gap: '4px'
                      }}>
                        <CheckCircle2 size={12} /> Scaricato
                      </span>
                    ) : (
                      <button
                        onClick={() => {
                          if (isGguf) {
                            toggleCardDetails(m);
                          } else {
                            handleStartWholeRepoDownload(m.id);
                          }
                        }}
                        style={{
                          padding: '5px 12px', borderRadius: '7px',
                          border: 'none',
                          background: isGguf
                            ? 'linear-gradient(135deg, #10b981, #00d2ff)'
                            : 'linear-gradient(135deg, #ffb86c, #ea580c)',
                          color: '#ffffff', fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px',
                          boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
                        }}
                      >
                        <Download size={11} />
                        <span>{targetQuant !== 'Modello' ? `Scarica (${targetQuant})` : 'Scarica'}</span>
                      </button>
                    )}

                    {/* Toggle Details Drawer Button */}
                    <button
                      onClick={() => toggleCardDetails(m)}
                      title={isExpanded ? 'Chiudi dettagli' : 'Mostra quantizzazioni, file e dettagli'}
                      style={{
                        padding: '5px 9px', borderRadius: '7px',
                        border: isExpanded ? '1px solid #ffb86c' : subBorder,
                        background: isExpanded ? 'rgba(255, 184, 108, 0.12)' : subBg,
                        color: isExpanded ? '#ffb86c' : textMuted,
                        fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '3px'
                      }}
                    >
                      <span>Visualizza</span>
                      {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                  </div>
                </div>

                {/* ── EXPANDED OPTIONS DRAWER ── */}
                {isExpanded && (
                  <div style={{
                    padding: '12px 14px',
                    borderTop: subBorder,
                    background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.25)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                  }}>
                    {/* Row 1: External link and quick metadata */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem' }}>
                        <ExternalLink size={12} color="#ffb86c" />
                        <span>Hugging Face Repo:</span>
                        <a
                          href={m.hf_url || `https://huggingface.co/${m.id}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: '#ffb86c', fontWeight: 800, textDecoration: 'none' }}
                        >
                          {m.id}
                        </a>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button
                          onClick={() => handleStartWholeRepoDownload(m.id, details?.files)}
                          disabled={downloadingRepo}
                          style={{
                            padding: '4px 10px', borderRadius: '6px',
                            border: '1px solid rgba(255, 184, 108, 0.40)', background: 'rgba(255, 184, 108, 0.12)',
                            color: '#ffb86c', fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer',
                            display: 'inline-flex', alignItems: 'center', gap: '4px'
                          }}
                        >
                          <FolderDown size={11} />
                          {downloadingRepo ? 'Avvio...' : `Scarica Intero Repository (${details?.files?.length || 1} file)`}
                        </button>
                      </div>
                    </div>

                    {/* Row 2: Quantization Chips Picker if GGUF Repository */}
                    {isLoadingDetails ? (
                      <div style={{ textAlign: 'center', padding: '16px', color: textMuted }}>
                        <Activity className="mh-spin" size={16} color="#00d2ff" style={{ margin: '0 auto 6px' }} />
                        <span style={{ fontSize: '0.70rem' }}>Caricamento rami e versioni quantizzate da Hugging Face...</span>
                      </div>
                    ) : details?.files && details.files.some(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf')) ? (
                      (() => {
                        const ggufFiles = details.files.filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf'));
                        const currentSel = selectedQuantMap[m.id] || ggufFiles[0]?.filename;
                        const activeFile = ggufFiles.find(f => f.filename === currentSel) || ggufFiles[0];
                        const isActiveFileDownloaded = activeFile ? (checkIsFileLocal(activeFile.filename, effectiveLocalModels) || isLocallyInstalled) : false;

                        return (
                          <div style={{
                            padding: '10px 12px', borderRadius: '8px',
                            background: isLight ? 'rgba(16, 185, 129, 0.06)' : 'rgba(16, 185, 129, 0.08)',
                            border: '1px solid rgba(16, 185, 129, 0.25)',
                            display: 'flex', flexDirection: 'column', gap: '8px'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                              <div style={{ fontSize: '0.72rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Download size={13} color="#10b981" />
                                <span>Versioni Quantizzate Disponibili ({ggufFiles.length}):</span>
                              </div>

                              {isActiveFileDownloaded ? (
                                <div style={{
                                  padding: '4px 10px', borderRadius: '6px',
                                  background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981',
                                  color: '#10b981', fontSize: '0.68rem', fontWeight: 800,
                                  display: 'inline-flex', alignItems: 'center', gap: '4px'
                                }}>
                                  <CheckCircle2 size={11} color="#10b981" />
                                  <span>Già in Locale ({activeFile?.filename ? activeFile.filename.split('/').pop() : 'GGUF'})</span>
                                </div>
                              ) : (
                                <button
                                  onClick={() => {
                                    if (activeFile) {
                                      handleStartSingleDownload(m.id, activeFile.filename, activeFile.download_url);
                                    }
                                  }}
                                  disabled={downloadingFile === activeFile?.filename}
                                  style={{
                                    padding: '5px 12px', borderRadius: '6px',
                                    border: 'none', background: 'linear-gradient(135deg, #10b981, #00d2ff)',
                                    color: '#ffffff', fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', gap: '4px'
                                  }}
                                >
                                  {downloadingFile === activeFile?.filename ? <Activity className="mh-spin" size={11} /> : <Download size={11} />}
                                  <span>Scarica Selezionata ({activeFile?.filename ? activeFile.filename.split('/').pop() : 'GGUF'})</span>
                                </button>
                              )}
                            </div>

                            {/* Preset chips */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', maxHeight: '100px', overflowY: 'auto' }}>
                              {ggufFiles.map((gf) => {
                                const isSelected = currentSel === gf.filename;
                                const isRecommended = gf.filename?.toLowerCase().includes('q4_k_m') || gf.filename?.toLowerCase().includes('q4-k-m');
                                const isGfDownloaded = checkIsFileLocal(gf.filename, effectiveLocalModels) || isLocallyInstalled;
                                return (
                                  <button
                                    key={gf.filename}
                                    onClick={() => setSelectedQuantMap(prev => ({ ...prev, [m.id]: gf.filename }))}
                                    style={{
                                      padding: '3px 8px', borderRadius: '5px',
                                      border: isSelected 
                                        ? '1.5px solid #10b981' 
                                        : (isGfDownloaded ? '1px solid rgba(16, 185, 129, 0.45)' : subBorder),
                                      background: isSelected 
                                        ? 'rgba(16, 185, 129, 0.25)' 
                                        : (isGfDownloaded ? 'rgba(16, 185, 129, 0.08)' : subBg),
                                      color: isSelected ? '#10b981' : (isGfDownloaded ? '#10b981' : textPrimary),
                                      fontSize: '0.66rem', fontWeight: (isSelected || isGfDownloaded) ? 800 : 600,
                                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px'
                                    }}
                                  >
                                    {isGfDownloaded ? '✅ ' : (isRecommended ? '⭐ ' : '')}
                                    {gf.filename.split('/').pop()}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()
                    ) : null}

                    {/* Row 3: Sigmanih Benchmark Results (eval_results from HF card_data) */}
                    {isSigmanih && details?.eval_results && details.eval_results.length > 0 && (
                      <div style={{
                        padding: '10px 12px', borderRadius: '8px',
                        background: isLight ? 'rgba(255, 184, 108, 0.06)' : 'rgba(255, 184, 108, 0.08)',
                        border: '1px solid rgba(255, 184, 108, 0.25)',
                        display: 'flex', flexDirection: 'column', gap: '8px'
                      }}>
                        <div style={{ fontSize: '0.72rem', fontWeight: 800, color: '#ffb86c', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Sparkles size={13} color="#ffb86c" />
                          <span>Benchmark & Valutazioni Sigmanih ({details.eval_results.length} metriche):</span>
                        </div>
                        <div style={{
                          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '6px',
                          maxHeight: '160px', overflowY: 'auto'
                        }}>
                          {details.eval_results.map((ev, evIdx) => {
                            const pct = typeof ev.value === 'number'
                              ? (ev.value > 1 ? ev.value : ev.value * 100)
                              : parseFloat(ev.value) || 0;
                            const barColor = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';
                            return (
                              <div key={evIdx} style={{
                                padding: '6px 8px', borderRadius: '6px',
                                background: subBg, border: subBorder
                              }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                                  <span style={{ fontSize: '0.62rem', fontWeight: 800, color: textPrimary }}>
                                    {ev.dataset || ev.task}
                                  </span>
                                  <span style={{ fontSize: '0.62rem', fontWeight: 900, color: barColor }}>
                                    {pct.toFixed(1)}%
                                  </span>
                                </div>
                                <div style={{ height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.08)' }}>
                                  <div style={{
                                    height: '100%', borderRadius: '2px',
                                    width: `${Math.min(pct, 100)}%`,
                                    background: barColor,
                                    transition: 'width 0.4s ease'
                                  }} />
                                </div>
                                <div style={{ fontSize: '0.54rem', color: textMuted, marginTop: '2px' }}>
                                  {ev.metric}{ev.verified ? ' ✓' : ''}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Row 4: File Tree Shards */}
                    {details?.files && details.files.length > 0 && (
                      <div>
                        <div style={{ fontSize: '0.68rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '4px' }}>
                          File e Shards del Modello ({details.files.length}):
                        </div>
                        <div style={{ maxHeight: '140px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {details.files.map((file, fIdx) => (
                            <div
                              key={fIdx}
                              style={{
                                padding: '5px 10px', borderRadius: '6px',
                                background: subBg, border: subBorder,
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'
                              }}
                            >
                              <span style={{ fontSize: '0.70rem', color: textPrimary, wordBreak: 'break-all' }}>
                                {file.filename}
                              </span>
                              <button
                                onClick={() => handleStartSingleDownload(m.id, file.filename, file.download_url)}
                                disabled={downloadingFile === file.filename}
                                style={{
                                  padding: '3px 8px', borderRadius: '5px',
                                  border: subBorder, background: 'transparent',
                                  color: textPrimary, fontSize: '0.64rem', fontWeight: 700, cursor: 'pointer',
                                  display: 'inline-flex', alignItems: 'center', gap: '3px', flexShrink: 0
                                }}
                              >
                                {downloadingFile === file.filename ? <Activity className="mh-spin" size={10} /> : <Download size={10} />}
                                Scarica
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 5. LOAD MORE PAGINATION */}
      {hasMore && !loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 20px' }}>
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            style={{
              padding: '10px 24px', borderRadius: '10px',
              background: isLight ? '#111827' : 'linear-gradient(135deg, #00d2ff, #0077ff)',
              border: 'none', color: '#ffffff', fontSize: '0.78rem', fontWeight: 800,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              boxShadow: '0 4px 14px rgba(0, 210, 255, 0.25)'
            }}
          >
            {loadingMore ? <Activity className="mh-spin" size={13} /> : <ArrowDown size={13} />}
            {loadingMore ? 'Caricamento altri modelli...' : 'Carica Altri Modelli'}
          </button>
        </div>
      )}
    </div>
  );
}
