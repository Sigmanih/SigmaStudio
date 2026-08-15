import React, { useState, useEffect, useCallback } from 'react';
import { Search, Download, Star, ArrowDown, Sparkles, Filter, CheckCircle2, Layers, Cpu, Activity, ExternalLink } from 'lucide-react';

const CATEGORIES = [
  { id: 'all', label: 'Tutti i Modelli' },
  { id: 'reasoning', label: '🧠 Reasoning (R1 / DeepSeek)' },
  { id: 'llm', label: '💬 LLM Conversazionali' },
  { id: 'code', label: '💻 Coding & Agenti' },
  { id: 'moe', label: '⚡ MoE Sharded (70B+)' },
  { id: 'vision', label: '👁️ Vision & Multimodale' },
  { id: 'audio', label: '🎙️ Audio & Whisper' },
];

export default function HfBrowser({ isLight, addToast, onDownloadStarted }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
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

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const q = encodeURIComponent(search);
      const res = await fetch(`/api/models/hf/search?q=${q}&category=${category}&limit=24`);
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setResults(json.results || []);
        }
      }
    } catch (e) {
      console.error('Error fetching HF models:', e);
    } finally {
      setLoading(false);
    }
  }, [search, category]);

  useEffect(() => {
    const delay = setTimeout(fetchModels, 300);
    return () => clearTimeout(delay);
  }, [fetchModels]);

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
      {/* 1. Search Bar & Categories */}
      <div style={{
        padding: '14px 18px', borderRadius: '14px',
        background: cardBg, border: cardBorder,
        display: 'flex', flexDirection: 'column', gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            padding: '8px 14px', borderRadius: '10px',
            background: subBg, border: subBorder, flex: 1
          }}>
            <Search size={15} color="#00d2ff" />
            <input
              type="text"
              placeholder="Cerca modelli su Hugging Face (es. DeepSeek-R1, Qwen2.5-Coder, Llama-3.1, GGUF)..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                background: 'transparent', border: 'none',
                color: textPrimary, fontSize: '0.84rem', outline: 'none', width: '100%'
              }}
            />
          </div>
        </div>

        {/* Category Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setCategory(cat.id)}
              className="mh-pill-btn"
              style={{
                background: category === cat.id ? (isLight ? '#111827' : '#00d2ff') : subBg,
                color: category === cat.id ? '#ffffff' : textMuted,
                border: category === cat.id ? '1px solid transparent' : subBorder
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Models Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          <Activity className="mh-spin" size={24} color="#00d2ff" style={{ margin: '0 auto 10px' }} />
          <div>Ricerca modelli su Hugging Face in corso...</div>
        </div>
      ) : results.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: textMuted }}>
          Nessun modello trovato per i criteri specificati.
        </div>
      ) : (
        <div className="mh-models-grid">
          {results.map(m => (
            <div
              key={m.id}
              onClick={() => handleSelectModel(m)}
              className="mh-card mh-card-hover"
              style={{
                padding: '16px', borderRadius: '14px',
                background: cardBg, border: selectedModel?.id === m.id ? '1.5px solid #00d2ff' : cardBorder,
                cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '12px'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                  <div>
                    <span style={{ fontSize: '0.64rem', color: textMuted, textTransform: 'uppercase', fontWeight: 800 }}>
                      {m.author}
                    </span>
                    <h3 style={{ margin: '2px 0 0 0', fontSize: '0.94rem', fontWeight: 800, color: textPrimary, lineHeight: '1.3' }}>
                      {m.name}
                    </h3>
                  </div>
                  <span style={{
                    fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                    background: 'rgba(0, 210, 255, 0.12)', color: '#00d2ff', fontWeight: 800, flexShrink: 0
                  }}>
                    {m.category?.toUpperCase() || 'LLM'}
                  </span>
                </div>

                <p style={{ margin: '8px 0 0 0', fontSize: '0.72rem', color: textMuted, lineHeight: '1.4' }}>
                  {m.description}
                </p>
              </div>

              <div>
                {/* Stats & Quantizations */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: subBorder, paddingTop: '8px', fontSize: '0.68rem', color: textMuted }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>⭐ {m.likes}</span>
                    <span>📥 {m.downloads > 1000 ? `${Math.round(m.downloads / 1000)}k` : m.downloads}</span>
                  </div>
                  <span style={{ color: '#10b981', fontWeight: 700 }}>
                    {m.recommended_gpu || 'SigmaEngine'}
                  </span>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelectModel(m);
                  }}
                  style={{
                    width: '100%', marginTop: '10px',
                    padding: '7px 12px', borderRadius: '8px',
                    border: 'none', background: 'rgba(0, 210, 255, 0.12)', color: isLight ? '#0284c7' : '#00d2ff',
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
      )}

      {/* 3. Model Files & Download Picker Drawer / Modal */}
      {selectedModel && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)',
          zIndex: 10030, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div style={{
            maxWidth: '560px', width: '100%',
            background: cardBg, border: cardBorder, borderRadius: '16px',
            padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px',
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.7)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontSize: '0.66rem', color: '#00d2ff', fontWeight: 800, textTransform: 'uppercase' }}>
                  FILE & QUANTIZZAZIONI DISPONIBILI
                </span>
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
                <Activity className="mh-spin" size={20} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
                <span>Caricamento file da Hugging Face...</span>
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
                        border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
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
