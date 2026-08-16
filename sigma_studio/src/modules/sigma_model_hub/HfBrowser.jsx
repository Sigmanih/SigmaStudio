import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, Download, Star, ArrowDown, Sparkles, Filter, CheckCircle2,
  Layers, Cpu, Activity, ExternalLink, HardDrive, ArrowUpDown, ChevronDown,
  Calendar, RefreshCw, PlusCircle, ShieldCheck, FolderDown, FileCode, ArrowUp,
  XCircle, Zap, RotateCcw, X
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
  { id: 'all', label: 'Tutti i Pesi (All GB)' },
  { id: 'under_4gb', label: '🟢 < 4 GB (Leggero • CPU / NPU)' },
  { id: '4_8gb', label: '🔵 4 - 8 GB (RTX 5060 8GB)' },
  { id: '8_16gb', label: '🟣 8 - 16 GB (RTX 5070 Ti 16GB)' },
  { id: '16_32gb', label: '🟡 16 - 32 GB (Dual-GPU 24GB)' },
  { id: '32_48gb', label: '🟠 32 - 48 GB (70B Q4 ~42GB)' },
  { id: '48_70gb', label: '🔴 48 - 70 GB (70B Q8 / MoE)' },
  { id: '70_140gb', label: '🟣 70 - 140 GB (Cluster / 140B MoE)' },
  { id: 'over_140gb', label: '🔮 > 140 GB (DeepSeek 671B Sharded)' },
];

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

const SORT_OPTIONS = [
  { id: 'newest', label: '✨ Nuove Uscite / Più Recenti (Data Rilascio)' },
  { id: 'downloads', label: '📥 Più Scaricati (Downloads)' },
  { id: 'likes', label: '⭐ Più Popolari (Likes / Trending)' },
  { id: 'size_asc', label: '💾 Peso Minore prima (GB ↑)' },
  { id: 'size_desc', label: '💾 Peso Maggiore prima (GB ↓)' },
];

export default function HfBrowser({ isLight, addToast, onDownloadStarted, activeDownloads = [] }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sizeBracket, setSizeBracket] = useState('all');
  const [paramBracket, setParamBracket] = useState('all');
  const [formatFilter, setFormatFilter] = useState('all');
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
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [downloadingFile, setDownloadingFile] = useState(null);
  const [downloadingRepo, setDownloadingRepo] = useState(false);

  const topRef = useRef(null);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const hasActiveFilters = category !== 'all' || sizeBracket !== 'all' || paramBracket !== 'all' || formatFilter !== 'all' || officialOnly || search.trim() !== '';

  const handleResetFilters = () => {
    setSearch('');
    setCategory('all');
    setSizeBracket('all');
    setParamBracket('all');
    setFormatFilter('all');
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
      let url = `/api/models/hf/search?q=${q}&category=${category}&size_bracket=${sizeBracket}&param_bracket=${paramBracket}&format_filter=${formatFilter}&sort=${sortBy}&official_only=${officialOnly}&limit=30`;
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
  }, [search, category, sizeBracket, paramBracket, formatFilter, sortBy, officialOnly]);

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
    setLoadingDetails(true);
    try {
      const res = await fetch(`/api/models/hf/details?model_id=${encodeURIComponent(m.id)}`);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setModelDetails(json);
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative' }}>
      <div ref={topRef} />

      {/* 1. MODERN ULTRA-SLEEK SEARCH & FILTER TOOLBAR */}
      <div
        className="mh-sticky-filters"
        style={{
          padding: '16px 20px', borderRadius: '16px',
          background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
          border: cardBorder,
          display: 'flex', flexDirection: 'column', gap: '14px',
          boxShadow: isLight ? '0 4px 20px rgba(0,0,0,0.06)' : '0 10px 30px rgba(0,0,0,0.45)'
        }}
      >
        {/* Top Row: Hero Search Bar + "Solo Ufficiali" Toggle + Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div
            className="mh-search-hero"
            style={{
              background: subBg, border: subBorder, flex: 1, minWidth: '280px'
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
                {SIZE_BRACKETS.map(b => (
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

          {/* 5. ORDINAMENTO */}
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
                {SIZE_BRACKETS.find(s => s.id === sizeBracket)?.label} <X size={12} />
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
                    padding: '16px', borderRadius: '14px',
                    background: cardBg,
                    border: activeTask
                      ? '1.5px solid #00d2ff'
                      : (failedTask ? '1.5px solid rgba(239, 68, 68, 0.4)' : (selectedModel?.id === m.id ? '1.5px solid #ffb86c' : cardBorder)),
                    cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '12px'
                  }}
                >

                  <div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '0.64rem', color: textMuted, textTransform: 'uppercase', fontWeight: 800 }}>
                            {m.author}
                          </span>
                          {m.is_official && (
                            <span style={{
                              fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                              background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.3)',
                              fontWeight: 800, display: 'flex', alignItems: 'center', gap: '3px'
                            }}>
                              <ShieldCheck size={10} /> Ufficiale
                            </span>
                          )}
                        </div>
                        <h3 style={{ margin: '2px 0 0 0', fontSize: '0.94rem', fontWeight: 800, color: textPrimary, lineHeight: '1.3' }}>
                          {m.name}
                        </h3>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
                        {m.is_moe || (m.total_params_label && m.total_params_label !== m.active_params_label) ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <span style={{
                              fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                              background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', fontWeight: 800
                            }}>
                              ⚡ {m.active_params_label || m.params_label}
                            </span>
                            <span style={{
                              fontSize: '0.60rem', padding: '2px 5px', borderRadius: '4px',
                              background: subBg, color: textMuted, border: subBorder, fontWeight: 700
                            }}>
                              📊 {m.total_params_label}
                            </span>
                          </div>
                        ) : (
                          <span style={{
                            fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                            background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800
                          }}>
                            {m.params_label || '7B'}
                          </span>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          {m.precision && (
                            <span style={{
                              fontSize: '0.58rem', padding: '1px 5px', borderRadius: '3px',
                              background: m.precision.includes('FP8') ? 'rgba(0, 210, 255, 0.12)' : (m.precision.includes('GGUF') ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 184, 108, 0.12)'),
                              color: m.precision.includes('FP8') ? '#00d2ff' : (m.precision.includes('GGUF') ? '#10b981' : '#ffb86c'),
                              fontWeight: 800
                            }}>
                              {m.precision.split(' ')[0]}
                            </span>
                          )}
                          <span style={{
                            fontSize: '0.60rem', padding: '1px 5px', borderRadius: '3px',
                            background: subBg, color: textPrimary, border: subBorder, fontWeight: 800
                          }}>
                            ~{m.size_gb} GB
                          </span>
                        </div>
                      </div>
                    </div>

                    <p style={{ margin: '8px 0 0 0', fontSize: '0.72rem', color: textMuted, lineHeight: '1.4' }}>
                      {m.description}
                    </p>
                  </div>

                  <div>
                    {/* Release Date & Stats */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: subBorder, paddingTop: '8px', fontSize: '0.68rem', color: textMuted }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Calendar size={12} color="#ffb86c" />
                        <span style={{ color: textPrimary, fontWeight: 700 }}>
                          {m.release_date_label || 'Recente'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>⭐ {m.likes}</span>
                        <span>📥 {m.downloads > 1000 ? `${Math.round(m.downloads / 1000)}k` : m.downloads}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.66rem' }}>
                      <span style={{ color: '#00d2ff', fontWeight: 700 }}>
                        {m.recommended_gpu || '⚡ SigmaEngine'}
                      </span>

                      <a
                        href={m.hf_url || `https://huggingface.co/${m.id}`}
                        target="_blank"
                        rel="noreferrer"
                        onClick={e => e.stopPropagation()}
                        style={{
                          color: textMuted, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '3px',
                          fontWeight: 700, padding: '2px 5px', borderRadius: '4px', background: subBg, border: subBorder
                        }}
                        title="Apri pagina ufficiale su Hugging Face"
                      >
                        <ExternalLink size={10} /> Hugging Face
                      </a>
                    </div>

                    {/* LIVE IN-CARD DOWNLOAD PROGRESS OR ACTION BUTTONS */}
                    {activeTask ? (
                      <div
                        onClick={e => e.stopPropagation()}
                        style={{
                          marginTop: '10px', padding: '8px 10px', borderRadius: '8px',
                          background: 'rgba(0, 210, 255, 0.08)', border: '1px solid rgba(0, 210, 255, 0.3)',
                          display: 'flex', flexDirection: 'column', gap: '6px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                          <span style={{ color: '#00d2ff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Activity className="mh-spin" size={12} color="#00d2ff" />
                            Scaricamento: {activeTask.progress_pct}%
                          </span>
                          <span style={{ color: textPrimary, fontWeight: 700, fontFamily: 'monospace' }}>
                            {activeTask.speed_mbps} MB/s
                          </span>
                        </div>

                        <div className="mh-progress-track">
                          <div
                            className="mh-progress-bar"
                            style={{
                              width: `${activeTask.progress_pct}%`,
                              background: 'linear-gradient(90deg, #00d2ff, #0090ff)'
                            }}
                          />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.64rem', color: textMuted }}>
                          <span>
                            {activeTask.is_repo_download
                              ? `File ${activeTask.current_file_idx}/${activeTask.total_files} (${activeTask.current_file_name})`
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
                          marginTop: '10px', padding: '8px 10px', borderRadius: '8px',
                          background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)',
                          display: 'flex', flexDirection: 'column', gap: '6px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                          <span style={{ color: '#ef4444', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <AlertTriangle size={12} /> Interrotto ({failedTask.progress_pct}%)
                          </span>
                          <button
                            onClick={() => handleRetryDownload(failedTask.task_id)}
                            style={{
                              padding: '4px 10px', borderRadius: '6px', border: 'none',
                              background: 'linear-gradient(135deg, #10b981, #00d2ff)', color: '#ffffff',
                              fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: '3px', boxShadow: '0 0 8px rgba(16, 185, 129, 0.3)'
                            }}
                          >
                            <RotateCcw size={10} /> Riprendi
                          </button>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                          <span style={{ color: '#10b981' }}>💾 {failedTask.downloaded_mb} MB già salvati su disco</span>
                          <button
                            onClick={() => handleStartWholeRepoDownload(m.id)}
                            style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', fontSize: '0.62rem', textDecoration: 'underline' }}
                          >
                            Ricomincia da zero
                          </button>
                        </div>
                      </div>
                    ) : completedTask ? (
                      <div style={{
                        marginTop: '10px', padding: '7px 10px', borderRadius: '8px',
                        background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)',
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem'
                      }}>
                        <span style={{ color: '#10b981', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={13} /> Scaricato
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectModel(m);
                          }}
                          style={{
                            padding: '3px 8px', borderRadius: '4px', border: 'none',
                            background: '#10b981', color: '#ffffff', fontWeight: 800, cursor: 'pointer', fontSize: '0.68rem'
                          }}
                        >
                          ⚡ Avvia
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '6px', marginTop: '10px' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartWholeRepoDownload(m.id);
                          }}
                          style={{
                            flex: 1, padding: '7px 10px', borderRadius: '8px',
                            border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)', color: '#ffffff',
                            fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
                            boxShadow: '0 0 10px rgba(255, 184, 108, 0.25)'
                          }}
                        >
                          <FolderDown size={13} /> Scarica Tutto
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectModel(m);
                          }}
                          style={{
                            padding: '7px 10px', borderRadius: '8px',
                            border: subBorder, background: subBg, color: textPrimary,
                            fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                          }}
                          title="Ispeziona file e quantizzazioni"
                        >
                          <FileCode size={13} />
                        </button>
                      </div>
                    )}

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
                {/* HERO BANNER: 1-CLICK WHOLE REPO DOWNLOAD */}
                <div style={{
                  padding: '14px', borderRadius: '12px',
                  background: isLight ? '#fef3c7' : 'linear-gradient(135deg, rgba(255, 184, 108, 0.15), rgba(234, 88, 12, 0.15))',
                  border: '1.5px solid #ffb86c',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap'
                }}>
                  <div>
                    <div style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FolderDown size={16} color="#ffb86c" /> Scarica Intero Modello ({modelDetails?.files?.length || 1} file / shard)
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

                {/* Model Specs Quick Overview Grid */}
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
                    <div style={{ color: '#ffb86c', fontWeight: 800 }}>{modelDetails?.precision || selectedModel.precision || 'Safetensors'}</div>
                  </div>
                  <div>
                    <div style={{ color: textMuted, fontSize: '0.64rem', fontWeight: 700 }}>PESO STIMATO</div>
                    <div style={{ color: textPrimary, fontWeight: 800 }}>~{selectedModel.size_gb} GB</div>
                  </div>
                </div>

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
