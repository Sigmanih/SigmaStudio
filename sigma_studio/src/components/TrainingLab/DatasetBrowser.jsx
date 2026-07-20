import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Download, Database, Trash2, Upload, Star, RefreshCw, Brain, ExternalLink } from 'lucide-react';

// ==============================================================================
// DatasetBrowser — HuggingFace search + local import + My Datasets list
// ==============================================================================

const SOURCE_ICON = {
  huggingface: '🤗',
  local: '📁',
  sigma: '🧬',
};

function DatasetCard({ ds, onAdd, added }) {
  const icon = SOURCE_ICON[ds.source || 'huggingface'] || '📊';
  const dlFmt = (n) => n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(0)}K` : String(n);

  return (
    <div className="training-dataset-card">
      <div className="training-dataset-card-header">
        <div className="training-dataset-card-icon">{icon}</div>
        <div>
          <div className="training-dataset-card-title">{ds.name || ds.id}</div>
          <div className="training-dataset-card-author">{ds.author || ds.hf_id || ''}</div>
        </div>
      </div>
      {ds.description && (
        <div className="training-dataset-card-desc">{ds.description}</div>
      )}
      <div className="training-dataset-card-footer">
        {ds.downloads > 0 && (
          <span className="training-dataset-stat">
            <Download size={9} /> {dlFmt(ds.downloads)}
          </span>
        )}
        {ds.likes > 0 && (
          <span className="training-dataset-stat">
            <Star size={9} /> {ds.likes}
          </span>
        )}
        {ds.size_category && ds.size_category !== 'unknown' && (
          <span className="training-dataset-stat">{ds.size_category}</span>
        )}
        {(ds.task_categories || []).slice(0, 1).map(t => (
          <span key={t} className="training-dataset-tag">{t.replace(/_/g, ' ')}</span>
        ))}
        <button
          className={`training-dataset-add-btn ${added ? 'added' : ''}`}
          onClick={() => onAdd(ds)}
          disabled={added}
        >
          {added ? '✓ Aggiunto' : '+ Aggiungi'}
        </button>
      </div>
    </div>
  );
}

function MyDatasetItem({ ds, selected, onSelect, onDelete }) {
  const rows = ds.row_count ? `${ds.row_count.toLocaleString()} righe` : '';
  const size = ds.size_bytes ? `${(ds.size_bytes / 1024).toFixed(0)} KB` : '';
  const badge = ds.source === 'huggingface' ? 'HF' : 'locale';
  const isHf = ds.source === 'huggingface';

  return (
    <div
      className={`training-my-dataset-item ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(ds.id)}
    >
      <div className="training-my-dataset-icon">{SOURCE_ICON[ds.source] || '📊'}</div>
      <div className="training-my-dataset-info">
        <div className="training-my-dataset-name" title={ds.name}>{ds.name}</div>
        <div className="training-my-dataset-meta">
          {isHf ? (ds.hf_id || ds.name) : [rows, size].filter(Boolean).join(' · ')}
        </div>
      </div>
      <span className={`training-my-dataset-badge ${isHf ? 'hf' : ''}`}>{badge}</span>
      <button
        className="training-my-dataset-delete"
        onClick={(e) => { e.stopPropagation(); onDelete(ds.id); }}
        title="Rimuovi dataset"
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
}

export default function DatasetBrowser({ onDatasetSelect, selectedDatasetId }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [myDatasets, setMyDatasets] = useState([]);
  const [addedIds, setAddedIds] = useState(new Set());
  const [activeTab, setActiveTab] = useState('search'); // 'search' | 'mine' | 'import'
  const [dragOver, setDragOver] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importStatus, setImportStatus] = useState(null);
  const [aiPromptOpen, setAiPromptOpen] = useState(false);
  const fileInputRef = useRef();
  const searchTimeout = useRef();

  // Load my datasets on mount
  const loadMyDatasets = useCallback(async () => {
    try {
      const res = await fetch('/api/training/datasets');
      const data = await res.json();
      if (data.success) setMyDatasets(data.datasets || []);
    } catch (e) {}
  }, []);

  useEffect(() => { loadMyDatasets(); }, [loadMyDatasets]);

  const handleSearch = useCallback(async (q = searchQuery) => {
    if (!q.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const res = await fetch(`/api/training/datasets/search?q=${encodeURIComponent(q.trim())}&limit=20`);
      const data = await res.json();
      if (data.success) setSearchResults(data.results || []);
    } catch (e) {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [searchQuery]);

  // Debounced search on enter
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleAddHF = async (ds) => {
    try {
      const res = await fetch('/api/training/dataset/register_hf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: ds.id || ds.name, split: 'train' }),
      });
      const data = await res.json();
      if (data.success) {
        setAddedIds(prev => new Set([...prev, ds.id]));
        setMyDatasets(prev => [...prev, data.dataset]);
        if (onDatasetSelect) onDatasetSelect(data.dataset.id);
        setActiveTab('mine');
      }
    } catch (e) {}
  };

  const handleFileImport = async (file) => {
    if (!file) return;
    setImporting(true);
    setImportStatus(null);
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['jsonl', 'json', 'csv', 'txt', 'ndjson'].includes(ext)) {
      setImportStatus({ error: `Formato non supportato: .${ext}` });
      setImporting(false);
      return;
    }

    // Read file content and upload via JSON (base64 for binary safety)
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        // We save the file via the backend import endpoint 
        // For simplicity we send the file name + content as text
        const content = ev.target.result;
        // Write file to scratch area first, then import
        const uploadRes = await fetch('/api/create_file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: `scratch/training_import/${file.name}`,
            content: content,
          }),
        });
        const uploadData = await uploadRes.json();
        if (!uploadData.success) throw new Error(uploadData.error || 'Upload failed');

        // Now import from the scratch path
        const importRes = await fetch('/api/training/dataset/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: `scratch/training_import/${file.name}`,
            name: file.name.replace(/\.[^.]+$/, ''),
          }),
        });
        const importData = await importRes.json();
        if (importData.success) {
          setMyDatasets(prev => [...prev, importData.dataset]);
          setImportStatus({ success: true, name: importData.dataset.name });
          if (onDatasetSelect) onDatasetSelect(importData.dataset.id);
          setActiveTab('mine');
        } else {
          setImportStatus({ error: importData.error || 'Import fallito' });
        }
      } catch (e) {
        setImportStatus({ error: e.message });
      } finally {
        setImporting(false);
      }
    };
    reader.readAsText(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileImport(file);
  };

  const handleDelete = async (dsId) => {
    if (!confirm('Rimuovere questo dataset?')) return;
    try {
      const res = await fetch('/api/training/dataset/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: dsId }),
      });
      const data = await res.json();
      if (data.success) {
        setMyDatasets(prev => prev.filter(d => d.id !== dsId));
        if (selectedDatasetId === dsId && onDatasetSelect) onDatasetSelect(null);
      }
    } catch (e) {}
  };

  // Suggested searches (popular LLM training datasets)
  const SUGGESTED = ['alpaca', 'dolly', 'openhermes', 'sharegpt', 'math', 'code', 'instruct', 'chat'];

  return (
    <div className="training-panel">
      {/* AI Generate hint */}
      <div style={{ padding: '12px 16px 0' }}>
        <div className="training-ai-generate-bar">
          <div className="training-ai-generate-icon">🧬</div>
          <div className="training-ai-generate-text">
            <strong>Genera dataset con Sigma AI</strong>
            Chiedi agli agenti Sigma di generare esempi di training dal tuo materiale
          </div>
          <button
            className="training-ai-generate-btn"
            onClick={() => setAiPromptOpen(!aiPromptOpen)}
          >
            <Brain size={12} /> Genera
          </button>
        </div>
        {aiPromptOpen && (
          <div style={{
            background: 'rgba(188,140,255,0.05)', border: '1px solid rgba(188,140,255,0.12)',
            borderRadius: '10px', padding: '12px', marginBottom: '10px', fontSize: '0.68rem',
            color: 'var(--text-dim)', lineHeight: 1.6
          }}>
            <strong style={{ color: 'var(--accent)' }}>Prompt suggerito per la chat AI:</strong>
            <br />
            <code style={{ display: 'block', marginTop: '6px', fontFamily: 'JetBrains Mono', color: 'var(--primary)', fontSize: '0.62rem' }}>
              "Genera un dataset di training in formato JSONL con 50 esempi Q&A sul tema [TOPIC] partendo dal materiale in [FILE/MODULO].
              Salva il file in scratch/training_import/dataset_[nome].jsonl"
            </code>
            <div style={{ marginTop: '8px', fontSize: '0.6rem' }}>
              Dopo che l'agente ha completato, usa <em>"Import locale"</em> per caricare il file JSONL generato.
            </div>
          </div>
        )}
      </div>

      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: '4px', padding: '0 16px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        {[
          { id: 'search', label: '🔍 HuggingFace' },
          { id: 'mine', label: `🗂️ I Miei (${myDatasets.length})` },
          { id: 'import', label: '📂 Import Locale' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '5px 12px', borderRadius: '8px', border: '1px solid',
              borderColor: activeTab === t.id ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.05)',
              background: activeTab === t.id ? 'rgba(0,210,255,0.06)' : 'transparent',
              color: activeTab === t.id ? 'var(--primary)' : 'var(--text-dim)',
              fontSize: '0.68rem', fontWeight: 500, cursor: 'pointer',
              transition: 'var(--trans-fast)',
            }}
          >
            {t.label}
          </button>
        ))}
        <button className="training-btn" style={{ marginLeft: 'auto' }} onClick={loadMyDatasets} title="Aggiorna">
          <RefreshCw size={12} />
        </button>
      </div>

      <div className="training-scroll-area">

        {/* ── HuggingFace Search ── */}
        {activeTab === 'search' && (
          <>
            <div className="training-search-bar">
              <input
                className="training-search-input"
                placeholder="Cerca su HuggingFace Datasets... (es: alpaca, dolly, math)"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                className="training-search-btn"
                onClick={() => handleSearch()}
                disabled={searching || !searchQuery.trim()}
              >
                {searching ? <div className="training-spinner" /> : <Search size={14} />}
                {searching ? '' : 'Cerca'}
              </button>
            </div>

            {/* Quick chips */}
            {searchResults.length === 0 && !searching && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-dark)', marginBottom: '6px' }}>
                  Suggeriti:
                </div>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {SUGGESTED.map(s => (
                    <button
                      key={s}
                      onClick={() => { setSearchQuery(s); handleSearch(s); }}
                      style={{
                        padding: '3px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)',
                        background: 'rgba(255,255,255,0.03)', color: 'var(--text-dim)',
                        fontSize: '0.65rem', cursor: 'pointer',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {searching && (
              <div className="training-empty">
                <div className="training-spinner" />
                <div className="training-empty-sub">Ricerca su HuggingFace...</div>
              </div>
            )}

            {!searching && searchResults.length === 0 && searchQuery && (
              <div className="training-empty">
                <div className="training-empty-icon">🔍</div>
                <div className="training-empty-title">Nessun risultato</div>
                <div className="training-empty-sub">Prova parole chiave diverse</div>
              </div>
            )}

            {!searching && searchResults.length === 0 && !searchQuery && (
              <div className="training-empty">
                <div className="training-empty-icon">🤗</div>
                <div className="training-empty-title">HuggingFace Dataset Hub</div>
                <div className="training-empty-sub">Cerca tra 100.000+ dataset open-source</div>
              </div>
            )}

            {searchResults.length > 0 && (
              <>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginBottom: '10px' }}>
                  {searchResults.length} risultati per "{searchQuery}"
                </div>
                <div className="training-dataset-grid">
                  {searchResults.map(ds => (
                    <DatasetCard
                      key={ds.id}
                      ds={ds}
                      onAdd={handleAddHF}
                      added={addedIds.has(ds.id) || myDatasets.some(m => m.hf_id === ds.id)}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}

        {/* ── My Datasets ── */}
        {activeTab === 'mine' && (
          <>
            {myDatasets.length === 0 ? (
              <div className="training-empty">
                <div className="training-empty-icon">🗂️</div>
                <div className="training-empty-title">Nessun dataset ancora</div>
                <div className="training-empty-sub">
                  Cerca su HuggingFace o importa un file locale
                </div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginBottom: '10px' }}>
                  {myDatasets.length} dataset disponibili — clicca per selezionarlo per il training
                </div>
                {myDatasets.map(ds => (
                  <MyDatasetItem
                    key={ds.id}
                    ds={ds}
                    selected={selectedDatasetId === ds.id}
                    onSelect={(id) => onDatasetSelect && onDatasetSelect(id)}
                    onDelete={handleDelete}
                  />
                ))}
              </>
            )}
          </>
        )}

        {/* ── Local Import ── */}
        {activeTab === 'import' && (
          <>
            <div
              className={`training-dropzone ${dragOver ? 'drag-over' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".jsonl,.json,.csv,.txt,.ndjson"
                onChange={e => handleFileImport(e.target.files[0])}
              />
              {importing ? (
                <>
                  <div className="training-dropzone-icon">⏳</div>
                  <div className="training-dropzone-title">Import in corso...</div>
                </>
              ) : (
                <>
                  <div className="training-dropzone-icon">
                    <Upload size={28} style={{ margin: '0 auto', display: 'block', opacity: 0.5 }} />
                  </div>
                  <div className="training-dropzone-title">
                    Trascina un file qui, oppure clicca per selezionare
                  </div>
                  <div className="training-dropzone-sub">Supporta JSONL, JSON, CSV e TXT</div>
                  <div className="training-dropzone-formats">
                    {['.jsonl', '.json', '.csv', '.txt', '.ndjson'].map(f => (
                      <span key={f} className="training-dropzone-fmt">{f}</span>
                    ))}
                  </div>
                </>
              )}
            </div>

            {importStatus && (
              <div style={{
                padding: '10px 14px', borderRadius: '10px', marginBottom: '12px', fontSize: '0.72rem',
                background: importStatus.error ? 'rgba(255,85,85,0.08)' : 'rgba(63,185,80,0.08)',
                border: `1px solid ${importStatus.error ? 'rgba(255,85,85,0.2)' : 'rgba(63,185,80,0.2)'}`,
                color: importStatus.error ? 'var(--error)' : 'var(--success)',
              }}>
                {importStatus.error ? `❌ ${importStatus.error}` : `✅ Dataset "${importStatus.name}" importato con successo!`}
              </div>
            )}

            {/* Format guide */}
            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
              borderRadius: '12px', padding: '14px',
            }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)', marginBottom: '10px' }}>
                📋 Formato consigliato — JSONL (instruction tuning)
              </div>
              {[
                { label: 'Instruction+Output', code: '{"instruction":"Calcola la derivata di x²","output":"2x"}' },
                { label: 'Instruction+Input+Output', code: '{"instruction":"Traduci","input":"Hello","output":"Ciao"}' },
                { label: 'Text puro', code: '{"text":"Il teorema di Pitagora afferma che..."}' },
                { label: 'Chat format', code: '{"messages":[{"role":"user","content":"Ciao"},{"role":"assistant","content":"..."}]}' },
              ].map(({ label, code }) => (
                <div key={label} style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', marginBottom: '3px' }}>{label}</div>
                  <code style={{
                    display: 'block', background: 'rgba(0,0,0,0.3)', borderRadius: '6px',
                    padding: '5px 9px', fontSize: '0.58rem', color: 'var(--primary)',
                    fontFamily: 'JetBrains Mono', wordBreak: 'break-all',
                  }}>{code}</code>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
