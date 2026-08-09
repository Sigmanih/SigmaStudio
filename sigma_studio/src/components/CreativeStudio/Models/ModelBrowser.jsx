import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Search, Download, CheckCircle2, ExternalLink, HardDrive, AlertTriangle,
  Lock, Heart, Loader, FolderOpen, X
} from 'lucide-react';

const SOURCES = [
  { id: 'huggingface', label: 'Hugging Face' },
  { id: 'civitai', label: 'Civitai' },
];

const fmtCount = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)}k` : `${n || 0}`);
const fmtGB = (b) => `${(b / 1024 ** 3).toFixed(1)} GB`;

/**
 * Ricerca e download di modelli da Hugging Face e Civitai.
 *
 * La categoria guida tutto: filtra la ricerca e determina la cartella di
 * ComfyUI in cui il file viene scritto — che è ciò che lo rende usabile subito
 * dopo il download, senza spostamenti manuali.
 */
export default function ModelBrowser({ onInstalled }) {
  const [meta, setMeta] = useState(null);
  const [category, setCategory] = useState('checkpoint');
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState(['huggingface', 'civitai']);
  const [results, setResults] = useState(null);
  const [errors, setErrors] = useState({});
  const [searching, setSearching] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [notice, setNotice] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const poll = useRef(null);

  const loadMeta = useCallback(() => (
    fetch('/api/creative/models/categories').then(r => r.json())
      .then(d => { if (d.success) setMeta(d); })
      .catch(() => {})
  ), []);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  // I job vanno seguiti solo mentre esistono: nessun polling a vuoto.
  useEffect(() => {
    const tick = () => fetch('/api/creative/downloads').then(r => r.json()).then(d => {
      const active = (d.jobs || []).filter(j => ['queued', 'downloading'].includes(j.status));
      setJobs(active);
      if (!active.length && poll.current) {
        clearInterval(poll.current);
        poll.current = null;
        loadMeta();
        onInstalled?.();
      }
    }).catch(() => {});
    if (jobs.length && !poll.current) poll.current = setInterval(tick, 1500);
    return () => { if (poll.current && !jobs.length) { clearInterval(poll.current); poll.current = null; } };
  }, [jobs.length, loadMeta, onInstalled]);

  const runSearch = (e) => {
    e?.preventDefault();
    if (!sources.length) return setNotice({ type: 'error', text: 'Seleziona almeno una sorgente' });
    setSearching(true);
    setNotice(null);
    const params = new URLSearchParams({ q: query, category, source: sources.join(','), limit: 20 });
    fetch(`/api/creative/models/search?${params}`)
      .then(r => r.json())
      .then(d => {
        if (!d.success) return setNotice({ type: 'error', text: d.error });
        setResults(d.results || []);
        setErrors(d.errors || {});
      })
      .catch(e2 => setNotice({ type: 'error', text: e2.message }))
      .finally(() => setSearching(false));
  };

  const download = (item, file) => {
    fetch('/api/creative/downloads/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file: {
          source: item.source, model_id: item.id, label: `${item.name} · ${file.filename}`,
          folder: item.folder || meta?.categories.find(c => c.id === category)?.folder,
          filename: file.filename, url: file.url, size_gb: file.size_gb,
          license: item.license, kind: category,
        },
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (!d.success) return setNotice({ type: 'error', text: d.error });
        setJobs(j => [...j, ...(d.jobs || [])]);
        setNotice({ type: 'ok', text: `Download avviato: ${file.filename}` });
      })
      .catch(e2 => setNotice({ type: 'error', text: e2.message }));
  };

  const toggleSource = (id) => setSources(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]));

  if (!meta) return <p className="cs-hint">Caricamento categorie...</p>;

  const activeCategory = meta.categories.find(c => c.id === category);
  const installedHere = meta.installed?.[category]?.files || [];

  return (
    <div className="cs-browser">
      <div className="cs-downloads-head">
        <div>
          <h3 className="cs-mesh-title"><Search size={18} /> Cerca modelli</h3>
          <p className="cs-hint">
            <FolderOpen size={12} />
            {meta.models_root || 'cartella ComfyUI non trovata'}
            {activeCategory && ` → ${activeCategory.folder}/`}
          </p>
        </div>
        <span className="cs-hint"><HardDrive size={12} /> {meta.disk_free_gb} GB liberi</span>
      </div>

      <div className="cs-category-tabs">
        {meta.categories.map(c => (
          <button
            key={c.id}
            className={`cs-pill ${category === c.id ? 'active' : ''}`}
            title={c.description}
            onClick={() => { setCategory(c.id); setResults(null); }}
          >
            {c.label}
            {(meta.installed?.[c.id]?.files || []).length > 0 && (
              <span className="cs-cat-count">{meta.installed[c.id].files.length}</span>
            )}
          </button>
        ))}
      </div>

      {activeCategory && <p className="cs-hint">{activeCategory.description}</p>}

      <form className="cs-search-row" onSubmit={runSearch}>
        <input
          className="cs-inline-input"
          placeholder={`Cerca ${activeCategory?.label.toLowerCase()}... (vuoto = più scaricati)`}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        {SOURCES.map(s => (
          <button
            key={s.id} type="button"
            className={`cs-pill ${sources.includes(s.id) ? 'active' : ''}`}
            disabled={s.id === 'civitai' && !activeCategory?.sources.includes('civitai')}
            title={s.id === 'civitai' && !activeCategory?.sources.includes('civitai')
              ? 'Civitai non classifica questa categoria' : ''}
            onClick={() => toggleSource(s.id)}
          >
            {s.label}
          </button>
        ))}
        <button className="cs-tool-btn" type="submit" disabled={searching}>
          {searching ? <Loader size={14} className="cs-spin" /> : <Search size={14} />} Cerca
        </button>
      </form>

      {notice && (
        <div className={`cs-banner ${notice.type === 'ok' ? 'ok' : 'warn'}`}>
          {notice.type === 'ok' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          <span>{notice.text}</span>
          <button className="cs-copy-btn" onClick={() => setNotice(null)}><X size={11} /></button>
        </div>
      )}

      {Object.entries(errors).map(([src, err]) => (
        <div key={src} className="cs-banner warn"><AlertTriangle size={15} /><span><strong>{src}</strong>: {err}</span></div>
      ))}

      {jobs.length > 0 && (
        <div className="cs-active-jobs">
          {jobs.map(j => (
            <div key={j.job_id} className="cs-job-row">
              <span>{j.label}</span>
              <div className="cs-progress-bar"><div className="cs-progress-fill" style={{ width: `${j.progress}%` }} /></div>
              <span>{j.progress}% · {fmtGB(j.downloaded)}</span>
            </div>
          ))}
        </div>
      )}

      {results === null ? (
        installedHere.length > 0 && (
          <div className="cs-installed-list">
            <h5>Già installati in {activeCategory.folder}/</h5>
            {installedHere.map(f => (
              <div key={f.path} className="cs-installed-row">
                <CheckCircle2 size={13} /> <span>{f.filename}</span> <em>{f.size_gb} GB</em>
              </div>
            ))}
          </div>
        )
      ) : results.length === 0 ? (
        <p className="cs-hint">Nessun risultato per questa ricerca.</p>
      ) : (
        <div className="cs-result-list">
          {results.map(item => (
            <div key={`${item.source}-${item.id}`} className="cs-result-card">
              {item.thumbnail && <img src={item.thumbnail} alt="" className="cs-result-thumb" loading="lazy" />}
              <div className="cs-result-body">
                <div className="cs-result-head">
                  <span className="cs-result-name">{item.name}</span>
                  <span className={`cs-source-tag ${item.source}`}>{item.source === 'civitai' ? 'Civitai' : 'HF'}</span>
                  {item.gated && <span className="cs-download-kind gated"><Lock size={10} /> gated</span>}
                </div>
                <p className="cs-result-meta">
                  {item.author && <>di {item.author} · </>}
                  <Download size={11} /> {fmtCount(item.downloads)}
                  {item.likes ? <> · <Heart size={11} /> {fmtCount(item.likes)}</> : null}
                  {item.license && ` · ${item.license}`}
                </p>
                {item.description && <p className="cs-hint">{item.description}</p>}

                <div className="cs-result-actions">
                  <a className="cs-copy-btn" href={item.url} target="_blank" rel="noreferrer">
                    <ExternalLink size={11} /> pagina
                  </a>
                  {item.files.length === 0 ? (
                    <span className="cs-hint">nessun file scaricabile diretto</span>
                  ) : (
                    <button className="cs-copy-btn"
                            onClick={() => setExpanded(expanded === item.id ? null : item.id)}>
                      {item.files.length} file {expanded === item.id ? '−' : '+'}
                    </button>
                  )}
                </div>

                {expanded === item.id && (
                  <div className="cs-file-list">
                    {item.files.map(f => (
                      <div key={f.url} className="cs-file-row">
                        <span title={f.filename}>{f.filename}</span>
                        <em>{f.size_gb ? `${f.size_gb} GB` : '—'}</em>
                        {f.installed ? (
                          <span className="cs-download-done"><CheckCircle2 size={12} /> installato</span>
                        ) : (
                          <button className="cs-tool-btn" onClick={() => download(item, f)}>
                            <Download size={13} /> Scarica
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
