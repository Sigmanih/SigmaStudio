import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, Download, Star, ArrowDown, Sparkles, Filter, CheckCircle2,
  Layers, Cpu, Activity, ExternalLink, HardDrive, ArrowUpDown, ChevronDown,
  Calendar, RefreshCw, PlusCircle, ShieldCheck
} from 'lucide-react';

const CATEGORIES = [
  { id: 'all', label: 'Tutte le Categorie' },
  { id: 'reasoning', label: '🧠 Reasoning (R1 / DeepSeek)' },
  { id: 'llm', label: '💬 LLM Conversazionali' },
  { id: 'code', label: '💻 Coding & Agenti' },
  { id: 'moe', label: '⚡ MoE Sharded (70B+)' },
  { id: 'vision', label: '👁️ Vision & Multimodale' },
  { id: 'audio', label: '🎙️ Audio & Whisper' },
];

const SIZE_BRACKETS = [
  { id: 'all', label: 'Tutti i Pesi', badge: 'ALL' },
  { id: 'under_4gb', label: '< 4 GB', hint: 'CPU / NPU', color: '#10b981' },
  { id: '4_8gb', label: '4 - 8 GB', hint: 'RTX 5060 (8GB)', color: '#00d2ff' },
  { id: '8_16gb', label: '8 - 16 GB', hint: 'RTX 5070 Ti (16GB)', color: '#bc8cff' },
  { id: '16_32gb', label: '16 - 32 GB', hint: 'Dual-GPU 24GB', color: '#ffb86c' },
  { id: '32_48gb', label: '32 - 48 GB', hint: '70B Q4 (~42GB)', color: '#ea580c' },
  { id: '48_70gb', label: '48 - 70 GB', hint: '70B Q8 / MoE', color: '#ff5064' },
  { id: '70_140gb', label: '70 - 140 GB', hint: 'Cluster / 140B MoE', color: '#d946ef' },
  { id: 'over_140gb', label: '> 140 GB', hint: 'DeepSeek 671B Sharded', color: '#8b5cf6' },
];

const PARAM_BRACKETS = [
  { id: 'all', label: 'Tutti i Parametri' },
  { id: 'under_3b', label: 'Micro (< 3B)' },
  { id: '7b_8b', label: '7B - 8B' },
  { id: '12b_14b', label: '12B - 14B' },
  { id: '27b_34b', label: '27B - 34B' },
  { id: '70b_plus', label: '70B+ & MoE Sharded' },
];

const SORT_OPTIONS = [
  { id: 'newest', label: '✨ Nuove Uscite / Più Recenti (Data Rilascio)' },
  { id: 'downloads', label: '📥 Più Scaricati (Downloads)' },
  { id: 'likes', label: '⭐ Più Popolari (Likes / Trending)' },
  { id: 'size_asc', label: '💾 Peso Minore prima (GB ↑)' },
  { id: 'size_desc', label: '💾 Peso Maggiore prima (GB ↓)' },
];

const FORMAT_OPTIONS = [
  { id: 'all', label: 'Tutti i Formati' },
  { id: 'gguf', label: '⚡ Solo GGUF' },
  { id: 'safetensors', label: '📦 Solo Safetensors' },
];

export default function HfBrowser({ isLight, addToast, onDownloadStarted }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sizeBracket, setSizeBracket] = useState('all');
  const [paramBracket, setParamBracket] = useState('all');
  const [formatFilter, setFormatFilter] = useState('all');
  const [sortBy, setSortBy] = useState('newest');
  const [officialOnly, setOfficialOnly] = useState(false);
  const [page, setPage] = useState(1);

  const [results, setResults] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const [selectedModel, setSelectedModel] = useState(null);
  const [modelDetails, setModelDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [downloadingFile, setDownloadingFile] = useState(null);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const fetchModels = useCallback(async (targetPage = 1, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }

    try {
      const q = encodeURIComponent(search);
      const url = `/api/models/hf/search?q=${q}&category=${category}&size_bracket=${sizeBracket}&param_bracket=${paramBracket}&format_filter=${formatFilter}&sort=${sortBy}&official_only=${officialOnly}&page=${targetPage}&limit=30`;
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          const list = json.results || [];
          setResults(list);
          setHasMore(json.has_more === true || list.length >= targetPage * 30);
          setPage(targetPage);
        }
      }
    } catch (e) {
      console.error('Error fetching dynamic HF models:', e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [search, category, sizeBracket, paramBracket, formatFilter, sortBy, officialOnly]);

  // Reset to page 1 on filter changes
  useEffect(() => {
    const delay = setTimeout(() => {
      fetchModels(1, false);
    }, 250);
    return () => clearTimeout(delay);
  }, [fetchModels]);

  const handleLoadMore = () => {
    const nextPage = page + 1;
    fetchModels(nextPage, true);
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

  const handleStartDownload = async (modelId, filename, downloadUrl) => {
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. SEARCH BAR & MULTI-DIMENSIONAL FILTERS CONTAINER */}
      <div style={{
        padding: '16px 20px', borderRadius: '16px',
        background: cardBg, border: cardBorder,
        display: 'flex', flexDirection: 'column', gap: '14px',
        boxShadow: isLight ? '0 2px 10px rgba(0,0,0,0.03)' : '0 4px 20px rgba(0,0,0,0.3)'
      }}>
        {/* Search Input, Official Toggle & Sort / Format Dropdowns */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '9px 14px', borderRadius: '10px',
            background: subBg, border: subBorder, flex: 1, minWidth: '260px'
          }}>
            <Search size={16} color="#ffb86c" />
            <input
              type="text"
              placeholder="Cerca qualsiasi modello Hugging Face in tempo reale (es. Qwen/Qwen2.5, deepseek-ai/DeepSeek-R1, Meta-Llama)..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                background: 'transparent', border: 'none',
                color: textPrimary, fontSize: '0.84rem', outline: 'none', width: '100%'
              }}
            />
          </div>

          {/* "Solo Ufficiali" Checkbox Filter */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '9px 14px', borderRadius: '10px',
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
            <ShieldCheck size={15} color={officialOnly ? '#3b82f6' : textMuted} />
            <span style={{ fontSize: '0.78rem', fontWeight: 800, color: officialOnly ? '#3b82f6' : textPrimary }}>
              Solo Ufficiali
            </span>
          </label>

          {/* Sort Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowUpDown size={14} color="#ffb86c" />
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              style={{
                padding: '9px 12px', borderRadius: '10px',
                background: subBg, border: subBorder,
                color: textPrimary, fontSize: '0.78rem', fontWeight: 700, outline: 'none', cursor: 'pointer'
              }}
            >
              {SORT_OPTIONS.map(opt => (
                <option key={opt.id} value={opt.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Format Selector */}
          <select
            value={formatFilter}
            onChange={e => setFormatFilter(e.target.value)}
            style={{
              padding: '9px 12px', borderRadius: '10px',
              background: subBg, border: subBorder,
              color: textPrimary, fontSize: '0.78rem', fontWeight: 700, outline: 'none', cursor: 'pointer'
            }}
          >
            {FORMAT_OPTIONS.map(f => (
              <option key={f.id} value={f.id} style={{ background: isLight ? '#fff' : '#0d1019', color: textPrimary }}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        {/* Categories Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.66rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginRight: '4px' }}>
            CATEGORIA:
          </span>
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setCategory(cat.id)}
              className="mh-pill-btn"
              style={{
                background: category === cat.id ? (isLight ? '#111827' : '#ffb86c') : subBg,
                color: category === cat.id ? (isLight ? '#ffffff' : '#0d1019') : textMuted,
                border: category === cat.id ? '1px solid transparent' : subBorder
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Granular Size in GB Bracket Pills (including >32G, 48G, 70G, 140G+) */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center', borderTop: subBorder, paddingTop: '10px' }}>
          <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#ffb86c', textTransform: 'uppercase', marginRight: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <HardDrive size={12} /> FASCIA PESO GB:
          </span>
          {SIZE_BRACKETS.map(b => (
            <button
              key={b.id}
              onClick={() => setSizeBracket(b.id)}
              className="mh-pill-btn"
              style={{
                background: sizeBracket === b.id ? (b.color || '#ffb86c') : subBg,
                color: sizeBracket === b.id ? '#ffffff' : textMuted,
                border: sizeBracket === b.id ? '1px solid transparent' : subBorder
              }}
            >
              <span>{b.label}</span>
              {b.hint && (
                <span style={{
                  fontSize: '0.62rem', opacity: 0.85, padding: '1px 4px', borderRadius: '3px',
                  background: sizeBracket === b.id ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.06)'
                }}>
                  {b.hint}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Parameter Count Bracket Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#00d2ff', textTransform: 'uppercase', marginRight: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Cpu size={12} /> PARAMETRI:
          </span>
          {PARAM_BRACKETS.map(p => (
            <button
              key={p.id}
              onClick={() => setParamBracket(p.id)}
              className="mh-pill-btn"
              style={{
                background: paramBracket === p.id ? '#00d2ff' : subBg,
                color: paramBracket === p.id ? '#07090e' : textMuted,
                border: paramBracket === p.id ? '1px solid transparent' : subBorder
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. DYNAMIC LIVE MODELS GRID */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          <Activity className="mh-spin" size={24} color="#ffb86c" style={{ margin: '0 auto 10px' }} />
          <div>Interrogazione live in tempo reale da Hugging Face API...</div>
        </div>
      ) : results.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          Nessun modello trovato per i filtri selezionati. Prova a deselezionare "Solo Ufficiali" o seleziona "Tutti i Pesi".
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="mh-models-grid">
            {results.map(m => (
              <div
                key={m.id}
                onClick={() => handleSelectModel(m)}
                className="mh-card mh-card-hover"
                style={{
                  padding: '16px', borderRadius: '14px',
                  background: cardBg, border: selectedModel?.id === m.id ? '1.5px solid #ffb86c' : cardBorder,
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
                      <span style={{
                        fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                        background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800
                      }}>
                        {m.params_label || '7B'}
                      </span>
                      <span style={{
                        fontSize: '0.60rem', padding: '1px 5px', borderRadius: '3px',
                        background: subBg, color: textMuted, border: subBorder, fontWeight: 700
                      }}>
                        ~{m.size_gb} GB
                      </span>
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
                    {/* Direct Hugging Face External Link */}
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

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectModel(m);
                    }}
                    style={{
                      width: '100%', marginTop: '10px',
                      padding: '7px 12px', borderRadius: '8px',
                      border: 'none', background: 'rgba(255, 184, 108, 0.15)', color: isLight ? '#ea580c' : '#ffb86c',
                      fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px'
                    }}
                  >
                    <Download size={13} /> Seleziona Quantizzazione & Scarica
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* 3. PAGINATION / LOAD MORE BUTTON */}
          {hasMore && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 20px' }}>
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                style={{
                  padding: '10px 24px', borderRadius: '12px',
                  background: subBg, border: subBorder,
                  color: textPrimary, fontSize: '0.82rem', fontWeight: 800,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
                  boxShadow: '0 4px 15px rgba(0,0,0,0.1)'
                }}
              >
                {loadingMore ? <Activity className="mh-spin" size={16} color="#ffb86c" /> : <PlusCircle size={16} color="#ffb86c" />}
                {loadingMore ? 'Caricamento da Hugging Face...' : 'Carica Altri Modelli da Hugging Face'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* 4. QUANTIZATION & FILE SELECTION MODAL */}
      {selectedModel && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)',
          zIndex: 10030, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div style={{
            maxWidth: '580px', width: '100%',
            background: cardBg, border: cardBorder, borderRadius: '16px',
            padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px',
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.7)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.66rem', color: '#ffb86c', fontWeight: 800, textTransform: 'uppercase' }}>
                    FILE & QUANTIZZAZIONI
                  </span>
                  {selectedModel.release_date_label && (
                    <span style={{ fontSize: '0.66rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Calendar size={11} /> {selectedModel.release_date_label}
                    </span>
                  )}
                  {/* External link in Modal */}
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
              <button onClick={() => setSelectedModel(null)} style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer' }}>
                Chiudi
              </button>
            </div>

            {loadingDetails ? (
              <div style={{ textAlign: 'center', padding: '30px', color: textMuted }}>
                <Activity className="mh-spin" size={20} color="#ffb86c" style={{ margin: '0 auto 8px' }} />
                <span>Interrogazione live dei rami Hugging Face per i file del modello...</span>
              </div>
            ) : (
              <div style={{ maxHeight: '280px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(modelDetails?.files || []).map((file, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '10px 12px', borderRadius: '10px',
                      background: subBg, border: subBorder,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px'
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {file.filename}
                      </div>
                      <div style={{ fontSize: '0.66rem', color: textMuted }}>
                        {file.is_gguf ? '⚡ Formato GGUF (Ottimizzato SigmaEngine)' : 'Safetensors'}
                      </div>
                    </div>

                    <button
                      onClick={() => handleStartDownload(selectedModel.id, file.filename, file.download_url)}
                      disabled={downloadingFile === file.filename}
                      style={{
                        padding: '6px 12px', borderRadius: '6px',
                        border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)',
                        color: '#fff', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0
                      }}
                    >
                      {downloadingFile === file.filename ? <Activity className="mh-spin" size={12} /> : <Download size={12} />}
                      {downloadingFile === file.filename ? 'Avvio...' : 'Scarica'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
