import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, Download, Star, ArrowDown, Sparkles, Filter, CheckCircle2,
  Layers, Cpu, Activity, ExternalLink, HardDrive, ArrowUpDown, ChevronDown,
  Calendar, RefreshCw, PlusCircle, ShieldCheck, FolderDown, FileCode, ArrowUp,
  XCircle, Zap, RotateCcw, X, AlertTriangle, Sliders
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

// Brackets describe the model, never a particular card: `maxGb` is what the
// bracket demands, and whether that fits is answered by the VRAM this machine
// reports at runtime — see annotateBrackets below.
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

// Weights are not the only thing in VRAM; the same slack the backend applies.
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
  { id: 'newest', label: '✨ Nuove Uscite / Più Recenti (Data Rilascio)' },
  { id: 'downloads', label: '📥 Più Scaricati (Downloads)' },
  { id: 'likes', label: '⭐ Più Popolari (Likes / Trending)' },
  { id: 'size_asc', label: '💾 Peso Minore prima (GB ↑)' },
  { id: 'size_desc', label: '💾 Peso Maggiore prima (GB ↓)' },
];

const getModelTargetQuantLabel = (m, preferredQuant = 'Q4_K_M', activeFilterQuant = 'all') => {
  if (!m) return 'Modello';
  const text = `${m.id || ''} ${m.name || ''} ${m.precision || ''} ${m.default_file || ''}`.toUpperCase().replace(/-/g, '_');

  // 1. Check if model ID / name / precision explicitly defines a specific quantization
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

  // 2. If user selected a specific quantization filter, adapt to that
  if (activeFilterQuant && activeFilterQuant !== 'all') {
    return activeFilterQuant.toUpperCase();
  }

  // 3. If GGUF repository with generic name, use preferredQuant
  if ((m.format && m.format.toUpperCase().includes('GGUF')) || (m.precision && m.precision.toUpperCase().includes('GGUF')) || text.includes('GGUF')) {
    return preferredQuant || 'Q4_K_M';
  }

  // 4. Safetensors / Full model
  return 'Modello';
};

export default function HfBrowser({ isLight, addToast, onDownloadStarted, activeDownloads = [] }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sizeBracket, setSizeBracket] = useState('all');
  const [paramBracket, setParamBracket] = useState('all');
  const [formatFilter, setFormatFilter] = useState('all');
  const [quantFilter, setQuantFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [officialOnly, setOfficialOnly] = useState(false);

  const [results, setResults] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadedPagesCount, setLoadedPagesCount] = useState(1);

  const [selectedModel, setSelectedModel] = useState(null);
  const [modelDetails, setModelDetails] = useState(null);
  const [selectedQuantFilename, setSelectedQuantFilename] = useState('');
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [downloadingFile, setDownloadingFile] = useState(null);
  const [downloadingRepo, setDownloadingRepo] = useState(false);

  // Total VRAM measured on this machine, used to mark which size brackets fit.
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

  // Reset to initial on filter changes
  useEffect(() => {
    const delay = setTimeout(() => {
      fetchModels(null, false);
    }, 250);
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

  const handleSelectModel = async (m) => {
    setSelectedModel(m);
    setModelDetails(null);
    setSelectedQuantFilename('');
    setLoadingDetails(true);
    try {
      const res = await fetch(`/api/models/hf/details?model_id=${encodeURIComponent(m.id)}`);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setModelDetails(json);
          const ggufFiles = (json.files || []).filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf'));
          if (ggufFiles.length > 0) {
            const targetQ = getModelTargetQuantLabel(m, 'Q4_K_M', quantFilter).toLowerCase().replace('_', '').replace('-', '');
            const preferred = ggufFiles.find(f => f.filename?.toLowerCase().replace('_', '').replace('-', '').includes(targetQ))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q4_k_m') || f.filename?.toLowerCase().includes('q4-k-m'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q4_k_s') || f.filename?.toLowerCase().includes('q4-k-s'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q5_k_m') || f.filename?.toLowerCase().includes('q5-k-m'))
              || ggufFiles.find(f => f.filename?.toLowerCase().includes('q8_0') || f.filename?.toLowerCase().includes('q8-0'))
              || ggufFiles[0];
            if (preferred) {
              setSelectedQuantFilename(preferred.filename);
            }
          }
        }
      }
    } catch (e) {
      console.error('Error fetching model details:', e);
    } finally {
      setLoadingDetails(false);
    }
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
        setSelectedModel(null);
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
      <div ref={topRef} />

      {/* 0. HERO DESCRIPTION BANNER & QUICK PRESET CHIPS */}
      <div style={{
        padding: '16px 20px', borderRadius: '16px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf6ef 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(22, 28, 48, 0.85) 100%)',
        border: isLight ? '1px solid rgba(234, 88, 12, 0.25)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 4px 18px rgba(234, 88, 12, 0.08)' : '0 8px 24px rgba(0, 0, 0, 0.35)',
        display: 'flex', flexDirection: 'column', gap: '10px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              fontSize: '0.66rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.6px',
              color: isLight ? '#ea580c' : '#00d2ff'
            }}>
              <Sparkles size={12} /> HUGGING FACE MODEL DISCOVERY & PROVISIONING
            </div>
            <h2 style={{ margin: '2px 0 0 0', fontSize: '1.08rem', fontWeight: 800, color: textPrimary, letterSpacing: '-0.2px' }}>
              Esplora, Scarica e Avvia Modelli AI Open-Source
            </h2>
          </div>
          <div style={{ fontSize: '0.72rem', color: textMuted }}>
            Supporto nativo per <strong style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>GGUF (llama.cpp)</strong> e <strong style={{ color: '#10b981' }}>Safetensors</strong>
          </div>
        </div>

        <p style={{ margin: 0, fontSize: '0.76rem', color: textMuted, lineHeight: '1.45' }}>
          Cerca tra decine di migliaia di modelli su Hugging Face, filtra per quantizzazione, architettura (LLM, Coder, Reasoning, MoE, Vision) o taglia VRAM. I modelli scaricati vengono salvati nello storage locale e possono essere eseguiti direttamente con <strong>⚡ SigmaEngine</strong>.
        </p>

        {/* Quick Recommended Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', paddingTop: '2px' }}>
          <span style={{ fontSize: '0.66rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginRight: '2px' }}>
            CONSIGLIATI:
          </span>
          {[
            { label: '🧠 DeepSeek-R1', query: 'DeepSeek-R1' },
            { label: '💻 Qwen 2.5 Coder', query: 'Qwen2.5-Coder' },
            { label: '🦙 Llama 3.3', query: 'Llama-3.3' },
            { label: '🔥 Mistral NeMo', query: 'Mistral-Nemo' },
            { label: '💎 Gemma 2', query: 'gemma-2' },
            { label: '🔬 Phi-4', query: 'phi-4' },
            { label: '👁️ Vision VLM', query: 'Qwen2-VL' },
            { label: '🇮🇹 Italiano', query: 'Italian' }
          ].map(p => (
            <button
              key={p.label}
              type="button"
              onClick={() => {
                setSearch(p.query);
                scrollToTop();
              }}
              style={{
                padding: '3px 9px', borderRadius: '6px',
                background: isLight ? '#f3ede1' : 'rgba(255, 255, 255, 0.05)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                color: textPrimary, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = isLight ? '#ea580c' : '#00d2ff';
                e.currentTarget.style.color = isLight ? '#ffffff' : '#0a0d14';
                e.currentTarget.style.borderColor = isLight ? '#ea580c' : '#00d2ff';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = isLight ? '#f3ede1' : 'rgba(255, 255, 255, 0.05)';
                e.currentTarget.style.color = textPrimary;
                e.currentTarget.style.borderColor = isLight ? 'rgba(190, 160, 110, 0.3)' : 'rgba(255, 255, 255, 0.1)';
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 1. MODERN ULTRA-SLEEK SEARCH & FILTER TOOLBAR */}
      <div
        className="mh-sticky-filters"
        style={{
          padding: '14px 18px', borderRadius: '16px',
          background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
          border: cardBorder,
          display: 'flex', flexDirection: 'column', gap: '12px',
          boxShadow: isLight ? '0 4px 20px rgba(0,0,0,0.06)' : '0 10px 30px rgba(0,0,0,0.45)'
        }}
      >
        {/* Top Row: Hero Search Bar + "Solo Ufficiali" Toggle + Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div
            className="mh-search-hero"
            style={{
              background: subBg, border: subBorder, flex: 1, minWidth: '260px', padding: '8px 14px'
            }}
          >
            <Search size={18} color="#ffb86c" style={{ flexShrink: 0 }} />
            <input
              type="text"
              placeholder="Cerca qualsiasi modello Hugging Face in tempo reale (es. Qwen3.8, DeepSeek-R1, Llama-3.3)..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                background: 'transparent', border: 'none',
                color: textPrimary, fontSize: '0.86rem', outline: 'none', width: '100%'
              }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: 0 }}
                title="Cancella ricerca"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* "Solo Ufficiali" Switch / Pill Toggle */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '10px 16px', borderRadius: '12px',
            background: officialOnly ? (isLight ? '#eff6ff' : 'rgba(59, 130, 246, 0.15)') : subBg,
            border: officialOnly ? '1.5px solid #3b82f6' : subBorder,
            cursor: 'pointer', userSelect: 'none', transition: 'all 0.15s ease'
          }}>
            <input
              type="checkbox"
              checked={officialOnly}
              onChange={e => setOfficialOnly(e.target.checked)}
              style={{ accentColor: '#3b82f6', cursor: 'pointer' }}
            />
            <ShieldCheck size={16} color={officialOnly ? '#3b82f6' : textMuted} />
            <span style={{ fontSize: '0.80rem', fontWeight: 800, color: officialOnly ? '#3b82f6' : textPrimary }}>
              Solo Ufficiali
            </span>
          </label>

          {/* Reset Filters Button */}
          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '10px 14px', borderRadius: '12px',
                background: subBg, border: subBorder,
                color: '#ff5064', fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              title="Reimposta tutti i filtri ai valori predefiniti"
            >
              <RotateCcw size={13} /> Azzera Filtri
            </button>
          )}
        </div>

        {/* Bottom Row: 5 Clean Select Dropdowns (Category, Size, Params, Format, Sort) */}
        <div className="mh-filter-selects-grid">
          {/* 1. CATEGORIA */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: textMuted }}>
              <Layers size={11} color="#ffb86c" /> Categoria
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 2. FASCIA PESO GB */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#ffb86c' }}>
              <HardDrive size={11} color="#ffb86c" /> Fascia Peso GB
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 3. PARAMETRI */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#00d2ff' }}>
              <Cpu size={11} color="#00d2ff" /> Parametri
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 4. FORMATO PESI */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#10b981' }}>
              <FileCode size={11} color="#10b981" /> Formato Pesi
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 5. TIPO QUANTIZZAZIONE */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#00d2ff' }}>
              <Sliders size={11} color="#00d2ff" /> Quantizzazione
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>

          {/* 6. ORDINAMENTO */}
          <div className="mh-select-container">
            <span className="mh-select-label" style={{ color: '#bc8cff' }}>
              <ArrowUpDown size={11} color="#bc8cff" /> Ordina Per
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
              <ChevronDown size={14} className="mh-select-icon" color={textMuted} />
            </div>
          </div>
        </div>

        {/* Active Filter Chips Bar (when active) */}
        {hasActiveFilters && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', borderTop: subBorder, paddingTop: '10px' }}>
            <span style={{ fontSize: '0.64rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
              FILTRI ATTIVI:
            </span>
            {category !== 'all' && (
              <span
                onClick={() => setCategory('all')}
                className="mh-active-chip"
                style={{ background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', border: '1px solid rgba(255, 184, 108, 0.3)' }}
              >
                {CATEGORIES.find(c => c.id === category)?.label} <X size={12} />
              </span>
            )}
            {sizeBracket !== 'all' && (
              <span
                onClick={() => setSizeBracket('all')}
                className="mh-active-chip"
                style={{ background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', border: '1px solid rgba(0, 210, 255, 0.3)' }}
              >
                {sizeBrackets.find(b => b.id === sizeBracket)?.label} <X size={12} />
              </span>
            )}
            {paramBracket !== 'all' && (
              <span
                onClick={() => setParamBracket('all')}
                className="mh-active-chip"
                style={{ background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', border: '1px solid rgba(188, 140, 255, 0.3)' }}
              >
                {PARAM_BRACKETS.find(p => p.id === paramBracket)?.label} <X size={12} />
              </span>
            )}
            {formatFilter !== 'all' && (
              <span
                onClick={() => setFormatFilter('all')}
                className="mh-active-chip"
                style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' }}
              >
                {FORMAT_OPTIONS.find(f => f.id === formatFilter)?.label} <X size={12} />
              </span>
            )}
            {quantFilter !== 'all' && (
              <span
                onClick={() => setQuantFilter('all')}
                className="mh-active-chip"
                style={{ background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', border: '1px solid rgba(0, 210, 255, 0.3)' }}
              >
                {QUANT_OPTIONS.find(q => q.id === quantFilter)?.label} <X size={12} />
              </span>
            )}
            {officialOnly && (
              <span
                onClick={() => setOfficialOnly(false)}
                className="mh-active-chip"
                style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)' }}
              >
                🛡️ Solo Ufficiali <X size={12} />
              </span>
            )}
          </div>
        )}
      </div>

      {/* 2. STATS & PAGINATION HEADER */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '2px 8px', fontSize: '0.74rem', color: textMuted
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 800, color: textPrimary }}>
            Mostrati {results.length} modelli
          </span>
          <span>•</span>
          <span>{loadedPagesCount} {loadedPagesCount === 1 ? 'blocco caricato' : 'blocchi caricati'}</span>
          {officialOnly && (
            <span style={{
              fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
              background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', fontWeight: 800
            }}>
              Solo Provider Ufficiali
            </span>
          )}
        </div>

        {results.length > 20 && (
          <button
            onClick={scrollToTop}
            style={{
              background: subBg, border: subBorder, borderRadius: '6px',
              padding: '4px 10px', color: textPrimary, fontSize: '0.7rem',
              fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
            }}
          >
            <ArrowUp size={12} /> Torna su
          </button>
        )}
      </div>

      {/* 3. DYNAMIC LIVE MODELS GRID */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          <Activity className="mh-spin" size={24} color="#ffb86c" style={{ margin: '0 auto 10px' }} />
          <div>Interrogazione live in tempo reale da Hugging Face Hub...</div>
        </div>
      ) : results.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          Nessun modello trovato per i filtri selezionati. Prova a deselezionare "Solo Ufficiali" o seleziona "Tutti i Pesi".
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="mh-models-grid">
            {results.map(m => {
              // Check if this model is currently in active download
              const activeTask = activeDownloads.find(t => t.model_id === m.id && (t.status === 'downloading' || t.status === 'queued'));
              const completedTask = activeDownloads.find(t => t.model_id === m.id && t.status === 'completed');
              const failedTask = activeDownloads.find(t => t.model_id === m.id && (t.status === 'failed' || t.status === 'cancelled'));

              return (
                <div
                  key={m.id}
                  onClick={() => handleSelectModel(m)}
                  className="mh-card mh-card-hover"
                  style={{
                    padding: '12px 14px', borderRadius: '12px',
                    background: cardBg,
                    border: activeTask
                      ? '1.5px solid #00d2ff'
                      : (failedTask ? '1.5px solid rgba(239, 68, 68, 0.4)' : (selectedModel?.id === m.id ? '1.5px solid #ffb86c' : cardBorder)),
                    cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '8px'
                  }}
                >
                  <div>
                    {/* Card Top: Author & Badges */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginBottom: '2px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', overflow: 'hidden' }}>
                        <span style={{ fontSize: '0.62rem', color: textMuted, textTransform: 'uppercase', fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '120px' }}>
                          {m.author}
                        </span>
                        {m.is_official && (
                          <span style={{
                            fontSize: '0.54rem', padding: '1px 4px', borderRadius: '3px',
                            background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)',
                            fontWeight: 800, display: 'flex', alignItems: 'center', gap: '2px', flexShrink: 0
                          }}>
                            <ShieldCheck size={9} /> Ufficiale
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                        <span style={{
                          fontSize: '0.58rem', padding: '1px 5px', borderRadius: '3px',
                          background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800
                        }}>
                          ⚡ {m.active_params_label || m.params_label || '7B'}
                        </span>
                        {m.precision && (
                          <span style={{
                            fontSize: '0.56rem', padding: '1px 4px', borderRadius: '3px',
                            background: m.precision.includes('FP8') ? 'rgba(0, 210, 255, 0.12)' : (m.precision.includes('GGUF') ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 184, 108, 0.12)'),
                            color: m.precision.includes('FP8') ? '#00d2ff' : (m.precision.includes('GGUF') ? '#10b981' : '#ffb86c'),
                            fontWeight: 800
                          }}>
                            {m.precision.split(' ')[0]}
                          </span>
                        )}
                        <span style={{
                          fontSize: '0.58rem', padding: '1px 5px', borderRadius: '3px',
                          background: subBg, color: textPrimary, border: subBorder, fontWeight: 800
                        }}>
                          💾 {m.size_label || (m.size_gb >= 1000 ? `~${(m.size_gb / 1000).toFixed(1)} TB` : `~${m.size_gb} GB`)}
                        </span>
                      </div>
                    </div>

                    {/* Model Title */}
                    <h3 style={{ margin: '2px 0 4px 0', fontSize: '0.88rem', fontWeight: 800, color: textPrimary, lineHeight: '1.25', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={m.name}>
                      {m.name}
                    </h3>

                    {/* Description Clamped */}
                    <p style={{
                      margin: 0, fontSize: '0.70rem', color: textMuted, lineHeight: '1.35',
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', height: '2.7em'
                    }}>
                      {m.description || `Modello ${m.name} rilasciato da ${m.author}.`}
                    </p>

                    {/* Target GPU / Hardware Fit */}
                    <div style={{
                      marginTop: '6px', padding: '3px 6px', borderRadius: '5px',
                      background: 'rgba(0, 210, 255, 0.04)', border: '1px solid rgba(0, 210, 255, 0.14)',
                      fontSize: '0.62rem', color: '#00d2ff', fontWeight: 700,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                    }} title={m.recommended_gpu}>
                      🎯 {m.recommended_gpu || '⚡ SigmaEngine'}
                    </div>
                  </div>

                  <div>
                    {/* Release Date & Stats */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: subBorder, paddingTop: '6px', fontSize: '0.66rem', color: textMuted }}>
                      <span style={{ color: textPrimary, fontWeight: 600 }}>
                        📅 {m.release_date_label || 'Recente'}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>⭐ {m.likes}</span>
                        <span>📥 {m.downloads > 1000 ? `${Math.round(m.downloads / 1000)}k` : m.downloads}</span>
                        <a
                          href={m.hf_url || `https://huggingface.co/${m.id}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={e => e.stopPropagation()}
                          style={{
                            color: textMuted, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '2px',
                            fontWeight: 700, padding: '1px 4px', borderRadius: '3px', background: subBg, border: subBorder, fontSize: '0.60rem'
                          }}
                          title="Apri su Hugging Face"
                        >
                          <ExternalLink size={9} /> HF
                        </a>
                      </div>
                    </div>

                    {/* LIVE IN-CARD DOWNLOAD PROGRESS OR ACTION BUTTONS */}
                    {activeTask ? (
                      <div
                        onClick={e => e.stopPropagation()}
                        style={{
                          marginTop: '8px', padding: '6px 8px', borderRadius: '8px',
                          background: 'rgba(0, 210, 255, 0.08)', border: '1px solid rgba(0, 210, 255, 0.3)',
                          display: 'flex', flexDirection: 'column', gap: '4px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                          <span style={{ color: '#00d2ff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Activity className="mh-spin" size={11} color="#00d2ff" />
                            {activeTask.progress_pct}%
                          </span>
                          <span style={{ color: textPrimary, fontWeight: 700, fontFamily: 'monospace' }}>
                            {activeTask.speed_mbps} MB/s
                          </span>
                        </div>

                        <div className="mh-progress-track" style={{ height: '4px' }}>
                          <div
                            className="mh-progress-bar"
                            style={{
                              width: `${activeTask.progress_pct}%`,
                              background: 'linear-gradient(90deg, #00d2ff, #0090ff)'
                            }}
                          />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.60rem', color: textMuted }}>
                          <span>
                            {activeTask.is_repo_download
                              ? `File ${activeTask.current_file_idx}/${activeTask.total_files}`
                              : `${activeTask.downloaded_mb} / ${activeTask.total_mb || '...'} MB`}
                          </span>
                          <button
                            onClick={() => handleCancelDownload(activeTask.task_id)}
                            style={{
                              background: 'none', border: 'none', color: '#ef4444',
                              fontWeight: 700, cursor: 'pointer', padding: 0
                            }}
                          >
                            Annulla
                          </button>
                        </div>
                      </div>
                    ) : failedTask ? (
                      <div
                        onClick={e => e.stopPropagation()}
                        style={{
                          marginTop: '8px', padding: '6px 8px', borderRadius: '8px',
                          background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)',
                          display: 'flex', flexDirection: 'column', gap: '4px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem' }}>
                          <span style={{ color: '#ef4444', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <AlertTriangle size={11} /> Errore ({failedTask.progress_pct}%)
                          </span>
                          <button
                            onClick={() => handleRetryDownload(failedTask.task_id)}
                            style={{
                              padding: '3px 8px', borderRadius: '5px', border: 'none',
                              background: 'linear-gradient(135deg, #10b981, #00d2ff)', color: '#ffffff',
                              fontSize: '0.64rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '2px'
                            }}
                          >
                            <RotateCcw size={9} /> Riprendi
                          </button>
                        </div>
                      </div>
                    ) : completedTask ? (
                      <div style={{
                        marginTop: '8px', padding: '5px 8px', borderRadius: '6px',
                        background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem'
                      }}>
                        <span style={{ color: '#10b981', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <CheckCircle2 size={12} /> Scaricato
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectModel(m);
                          }}
                          style={{
                            padding: '2px 7px', borderRadius: '4px', border: 'none',
                            background: '#10b981', color: '#ffffff', fontWeight: 800, cursor: 'pointer', fontSize: '0.64rem'
                          }}
                        >
                          ⚡ Dettagli
                        </button>
                      </div>
                    ) : (() => {
                      const targetQuant = getModelTargetQuantLabel(m, 'Q4_K_M', quantFilter);
                      const isGguf = (m.format?.toLowerCase().includes('gguf') || m.precision?.toLowerCase().includes('gguf') || m.id.toLowerCase().includes('gguf') || targetQuant.startsWith('Q') || targetQuant.startsWith('IQ'));
                      return (
                        <div style={{ display: 'flex', gap: '5px', marginTop: '8px' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartWholeRepoDownload(m.id);
                            }}
                            style={{
                              flex: 1, padding: '5px 8px', borderRadius: '6px',
                              border: 'none',
                              background: isGguf
                                ? 'linear-gradient(135deg, #10b981, #00d2ff)'
                                : (targetQuant !== 'Modello'
                                  ? 'linear-gradient(135deg, #00d2ff, #7928ca)'
                                  : 'linear-gradient(135deg, #ffb86c, #ea580c)'),
                              color: '#ffffff',
                              fontSize: '0.70rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px'
                            }}
                          >
                            <Download size={11} /> {targetQuant !== 'Modello' ? `Scarica (${targetQuant})` : 'Scarica Modello'}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectModel(m);
                            }}
                            style={{
                              padding: '5px 8px', borderRadius: '6px',
                              border: subBorder, background: subBg, color: textPrimary,
                              fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}
                            title="Visualizza file e quantizzazioni"
                          >
                            <Sliders size={11} />
                          </button>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 4. PAGINATION FOOTER */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', padding: '16px 0 30px' }}>
            {hasMore ? (
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                style={{
                  padding: '12px 28px', borderRadius: '12px',
                  background: isLight ? '#111827' : 'linear-gradient(135deg, #ffb86c, #ea580c)',
                  border: 'none',
                  color: '#ffffff', fontSize: '0.84rem', fontWeight: 800,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
                  boxShadow: '0 6px 20px rgba(255, 184, 108, 0.3)'
                }}
              >
                {loadingMore ? <Activity className="mh-spin" size={16} color="#ffffff" /> : <PlusCircle size={16} color="#ffffff" />}
                {loadingMore ? 'Caricamento da Hugging Face...' : `Carica Altri Modelli da Hugging Face (+30)`}
              </button>
            ) : (
              <div style={{ fontSize: '0.76rem', color: textMuted }}>
                ✓ Tutti i modelli disponibili per questa selezione sono stati caricati.
              </div>
            )}

            {results.length > 20 && (
              <button
                onClick={scrollToTop}
                style={{
                  background: 'transparent', border: 'none', color: textMuted,
                  fontSize: '0.74rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                <ArrowUp size={12} /> Torna all'inizio della lista
              </button>
            )}
          </div>
        </div>
      )}

      {/* 5. QUANTIZATION & FILE SELECTION MODAL */}
      {selectedModel && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)',
          zIndex: 10030, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div style={{
            maxWidth: '620px', width: '100%',
            background: cardBg, border: cardBorder, borderRadius: '16px',
            padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px',
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.7)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.66rem', color: '#ffb86c', fontWeight: 800, textTransform: 'uppercase' }}>
                    DETTAGLI MODELLO
                  </span>
                  {selectedModel.release_date_label && (
                    <span style={{ fontSize: '0.66rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Calendar size={11} /> {selectedModel.release_date_label}
                    </span>
                  )}
                  <a
                    href={selectedModel.hf_url || `https://huggingface.co/${selectedModel.id}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: '0.66rem', color: '#00d2ff', textDecoration: 'none',
                      display: 'flex', alignItems: 'center', gap: '3px', fontWeight: 700
                    }}
                  >
                    <ExternalLink size={11} /> Scheda Hugging Face
                  </a>
                </div>
                <h3 style={{ margin: '2px 0 0 0', fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                  {selectedModel.name}
                </h3>
              </div>
              <button onClick={() => setSelectedModel(null)} style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', fontSize: '0.8rem' }}>
                Chiudi
              </button>
            </div>

            {loadingDetails ? (
              <div style={{ textAlign: 'center', padding: '30px', color: textMuted }}>
                <Activity className="mh-spin" size={20} color="#ffb86c" style={{ margin: '0 auto 8px' }} />
                <span>Interrogazione live dei rami Hugging Face per i file del modello...</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* HERO BANNER: QUANTIZATION-AWARE DOWNLOAD */}
                {(() => {
                  const ggufFiles = (modelDetails?.files || []).filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf'));
                  const isGgufRepo = ggufFiles.length > 0;

                  if (isGgufRepo) {
                    const activeFile = ggufFiles.find(f => f.filename === selectedQuantFilename) || ggufFiles[0];
                    return (
                      <div style={{
                        padding: '14px', borderRadius: '12px',
                        background: isLight ? '#f0fdf4' : 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(0, 210, 255, 0.12))',
                        border: '1.5px solid #10b981',
                        display: 'flex', flexDirection: 'column', gap: '12px'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                          <div>
                            <div style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <Download size={16} color="#10b981" /> Scarica Versione Quantizzata ({ggufFiles.length} versioni)
                            </div>
                            <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
                              Verrà scaricata <strong>solo la versione selezionata</strong>, evitando di scaricare file duplicati.
                            </div>
                          </div>

                          <button
                            onClick={() => {
                              if (activeFile) {
                                handleStartSingleDownload(selectedModel.id, activeFile.filename, activeFile.download_url);
                              }
                            }}
                            disabled={downloadingFile === activeFile?.filename}
                            style={{
                              padding: '8px 18px', borderRadius: '8px',
                              border: 'none', background: 'linear-gradient(135deg, #10b981, #00d2ff)',
                              color: '#ffffff', fontSize: '0.80rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '6px',
                              boxShadow: '0 0 12px rgba(16, 185, 129, 0.35)'
                            }}
                          >
                            {downloadingFile === activeFile?.filename ? <Activity className="mh-spin" size={13} /> : <Download size={13} />}
                            {downloadingFile === activeFile?.filename ? 'Avvio...' : `Scarica Versione Selezionata`}
                          </button>
                        </div>

                        {/* Quantization picker chips */}
                        <div>
                          <div style={{ fontSize: '0.68rem', fontWeight: 800, color: textMuted, marginBottom: '6px', textTransform: 'uppercase' }}>
                            Scegli la quantizzazione desiderata:
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '120px', overflowY: 'auto' }}>
                            {ggufFiles.map((gf, i) => {
                              const isSelected = (selectedQuantFilename === gf.filename) || (!selectedQuantFilename && i === 0);
                              const isRecommended = gf.filename?.toLowerCase().includes('q4_k_m') || gf.filename?.toLowerCase().includes('q4-k-m');
                              return (
                                <button
                                  key={gf.filename}
                                  onClick={() => setSelectedQuantFilename(gf.filename)}
                                  style={{
                                    padding: '5px 10px', borderRadius: '6px',
                                    border: isSelected ? '1.5px solid #10b981' : subBorder,
                                    background: isSelected ? 'rgba(16, 185, 129, 0.2)' : subBg,
                                    color: isSelected ? '#10b981' : textPrimary,
                                    fontSize: '0.70rem', fontWeight: isSelected ? 800 : 600,
                                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                                  }}
                                >
                                  {isRecommended && '⭐ '}
                                  {gf.filename}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div style={{
                      padding: '14px', borderRadius: '12px',
                      background: isLight ? '#fef3c7' : 'linear-gradient(135deg, rgba(255, 184, 108, 0.15), rgba(234, 88, 12, 0.15))',
                      border: '1.5px solid #ffb86c',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap'
                    }}>
                      <div>
                        <div style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <FolderDown size={16} color="#ffb86c" /> Scarica Modello Completo ({modelDetails?.files?.length || 1} file / shard)
                        </div>
                        <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px' }}>
                          Scarica tutti i file (pesi, tokenizer, config) in un colpo solo per SigmaEngine.
                        </div>
                      </div>

                      <button
                        onClick={() => handleStartWholeRepoDownload(selectedModel.id, modelDetails?.files)}
                        disabled={downloadingRepo}
                        style={{
                          padding: '8px 16px', borderRadius: '8px',
                          border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)',
                          color: '#ffffff', fontSize: '0.78rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '6px',
                          boxShadow: '0 0 12px rgba(255, 184, 108, 0.35)'
                        }}
                      >
                        {downloadingRepo ? <Activity className="mh-spin" size={13} /> : <Download size={13} />}
                        {downloadingRepo ? 'Avvio...' : 'Scarica Modello Completo'}
                      </button>
                    </div>
                  );
                })()}

                {/* Model Specs Quick Overview Grid */}
                {(() => {
                  const ggufFiles = (modelDetails?.files || []).filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf'));
                  const activeFile = ggufFiles.find(f => f.filename === selectedQuantFilename) || ggufFiles[0];
                  
                  const computeActiveFileDetails = (activeFilename, model, details) => {
                    const basePrecision = details?.precision || model?.precision || 'Safetensors';
                    const baseSizeGb = details?.size_gb || model?.size_gb || 0;
                    const totalB = details?.total_b || model?.total_b || 7.0;

                    if (!activeFilename) {
                      return {
                        precision: basePrecision,
                        sizeLabel: details?.size_label || model?.size_label || `~${baseSizeGb} GB`,
                        sizeGb: baseSizeGb
                      };
                    }

                    const fnLower = activeFilename.toLowerCase();
                    let precision = basePrecision;
                    let mult = 0.58;

                    if (fnLower.includes('q8_0') || fnLower.includes('q8')) {
                      precision = 'GGUF Q8_0 (8-bit)';
                      mult = 1.05;
                    } else if (fnLower.includes('q6_k') || fnLower.includes('q6')) {
                      precision = 'GGUF Q6_K (6-bit)';
                      mult = 0.82;
                    } else if (fnLower.includes('q5_k_m') || fnLower.includes('q5_m')) {
                      precision = 'GGUF Q5_K_M (5-bit)';
                      mult = 0.70;
                    } else if (fnLower.includes('q5_k_s') || fnLower.includes('q5_s') || fnLower.includes('q5_0') || fnLower.includes('q5')) {
                      precision = 'GGUF Q5_K_S (5-bit)';
                      mult = 0.66;
                    } else if (fnLower.includes('q4_k_s') || fnLower.includes('q4_s')) {
                      precision = 'GGUF Q4_K_S (4-bit)';
                      mult = 0.54;
                    } else if (fnLower.includes('q4_0')) {
                      precision = 'GGUF Q4_0 (4-bit)';
                      mult = 0.52;
                    } else if (fnLower.includes('iq4_xs') || fnLower.includes('iq4')) {
                      precision = 'GGUF IQ4_XS (4-bit)';
                      mult = 0.49;
                    } else if (fnLower.includes('q4_k_m') || fnLower.includes('q4_m')) {
                      precision = 'GGUF Q4_K_M (4-bit)';
                      mult = 0.58;
                    } else if (fnLower.includes('q3_k_m') || fnLower.includes('iq3_m')) {
                      precision = 'GGUF Q3_K_M (3-bit)';
                      mult = 0.45;
                    } else if (fnLower.includes('q3_k_s') || fnLower.includes('iq3_xs') || fnLower.includes('q3')) {
                      precision = 'GGUF Q3_K_S (3-bit)';
                      mult = 0.40;
                    } else if (fnLower.includes('q2_k') || fnLower.includes('iq2') || fnLower.includes('q2')) {
                      precision = 'GGUF Q2_K (2-bit)';
                      mult = 0.30;
                    } else if (fnLower.includes('f16') || fnLower.includes('fp16') || fnLower.includes('bf16')) {
                      precision = 'GGUF F16 (16-bit)';
                      mult = 2.0;
                    }

                    const isSingleGguf = details?.files?.filter(f => f.is_gguf || f.filename?.toLowerCase().endsWith('.gguf')).length === 1;
                    const computedGb = isSingleGguf && baseSizeGb ? baseSizeGb : parseFloat((totalB * mult).toFixed(1));
                    const sizeLabel = computedGb >= 1000 ? `~${(computedGb / 1000).toFixed(1)} TB` : `~${computedGb} GB`;

                    return { precision, sizeLabel, sizeGb: computedGb };
                  };

                  const activeDetails = computeActiveFileDetails(activeFile?.filename, selectedModel, modelDetails);

                  return (
                    <div style={{
                      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px',
                      padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, fontSize: '0.74rem'
                    }}>
                      <div>
                        <div style={{ color: textMuted, fontSize: '0.64rem', fontWeight: 700 }}>PARAMETRI ATTIVI</div>
                        <div style={{ color: '#00d2ff', fontWeight: 800 }}>⚡ {modelDetails?.active_params_label || selectedModel.active_params_label || selectedModel.params_label}</div>
                      </div>
                      <div>
                        <div style={{ color: textMuted, fontSize: '0.64rem', fontWeight: 700 }}>PARAMETRI TOTALI</div>
                        <div style={{ color: textPrimary, fontWeight: 800 }}>📊 {modelDetails?.total_params_label || selectedModel.total_params_label}</div>
                      </div>
                      <div>
                        <div style={{ color: textMuted, fontSize: '0.64rem', fontWeight: 700 }}>PRECISIONE PESI</div>
                        <div style={{ color: '#ffb86c', fontWeight: 800 }}>{activeDetails.precision}</div>
                      </div>
                      <div>
                        <div style={{ color: textMuted, fontSize: '0.64rem', fontWeight: 700 }}>DIMENSIONE PESI</div>
                        <div style={{ color: textPrimary, fontWeight: 800 }}>{activeDetails.sizeLabel}</div>
                      </div>
                    </div>
                  );
                })()}

                {/* Individual files accordion/list */}
                <div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '6px' }}>
                    Oppure scarica singoli file / quantizzazioni ({modelDetails?.files?.length || 0}):
                  </div>
                  <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {(modelDetails?.files || []).map((file, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '8px 12px', borderRadius: '8px',
                          background: subBg, border: subBorder,
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: '0.76rem', fontWeight: 700, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {file.filename}
                          </div>
                          <div style={{ fontSize: '0.64rem', color: textMuted }}>
                            {file.is_gguf ? '⚡ GGUF' : (file.is_safetensors ? '📦 Safetensors' : 'Config / JSON')}
                          </div>
                        </div>

                        <button
                          onClick={() => handleStartSingleDownload(selectedModel.id, file.filename, file.download_url)}
                          disabled={downloadingFile === file.filename}
                          style={{
                            padding: '4px 10px', borderRadius: '6px',
                            border: subBorder, background: subBg,
                            color: textPrimary, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0
                          }}
                        >
                          {downloadingFile === file.filename ? <Activity className="mh-spin" size={10} /> : <Download size={10} />}
                          Singolo
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
