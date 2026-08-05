import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Hammer, Search, Cpu, Database, GraduationCap, Package,
  Play, MessageSquare, Send, Loader, RefreshCw, Check,
} from 'lucide-react';

// ==============================================================================
// SLM Forge — costruzione di modelli piccoli da zero
// Dataset italiani da HuggingFace, pre-training e/o distillazione, fine-tuning,
// export (GGUF e altri), chat di prova sui checkpoint mentre il modello si allena.
// ==============================================================================

const SECTION = { marginBottom: '20px' };

function Field({ label, desc, children }) {
  return (
    <div className="training-field">
      <label>{label}</label>
      {desc && <div className="training-field-desc">{desc}</div>}
      {children}
    </div>
  );
}

function Slider({ label, desc, value, min, max, step, onChange, display }) {
  return (
    <div className="training-field">
      <label>{label}</label>
      {desc && <div className="training-field-desc">{desc}</div>}
      <div className="training-slider-row">
        <input type="range" className="training-slider" min={min} max={max} step={step}
               value={value} onChange={e => onChange(parseFloat(e.target.value))} />
        <div className="training-slider-val">{display ? display(value) : value}</div>
      </div>
    </div>
  );
}

const chip = (active, color = 'var(--primary)') => ({
  padding: '3px 10px', borderRadius: '7px', cursor: 'pointer', fontSize: '0.6rem',
  border: `1px solid ${active ? color + '55' : 'rgba(255,255,255,0.07)'}`,
  background: active ? color + '14' : 'rgba(255,255,255,0.02)',
  color: active ? color : 'var(--text-dim)',
});

export default function SlmForge({ addToast, onJobCreated }) {
  const [info, setInfo] = useState(null);
  const [creating, setCreating] = useState(false);

  // configurazione
  const [architecture, setArchitecture] = useState('micro');
  const [mode, setMode] = useState('dataset');
  const [teacher, setTeacher] = useState('');
  const [sources, setSources] = useState([]);
  const [tokenizerMode, setTokenizerMode] = useState('train');
  const [vocabSize, setVocabSize] = useState(32000);
  const [seqLen, setSeqLen] = useState(512);
  const [batchSize, setBatchSize] = useState(8);
  const [maxSteps, setMaxSteps] = useState(2000);
  const [lr, setLr] = useState(3e-4);
  const [alpha, setAlpha] = useState(0.5);
  const [temperature, setTemperature] = useState(2.0);
  const [saveEvery, setSaveEvery] = useState(200);
  const [instructDataset, setInstructDataset] = useState(null);
  const [sftSteps, setSftSteps] = useState(300);
  const [exportFormats, setExportFormats] = useState(['gguf_q8', 'ollama']);
  const [outputName, setOutputName] = useState('slm_italiano');

  // ricerca dataset
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [configs, setConfigs] = useState({});

  const [estimate, setEstimate] = useState(null);
  const [instructCheck, setInstructCheck] = useState(null);
  const [teacherQuery, setTeacherQuery] = useState('');
  const [teacherResults, setTeacherResults] = useState([]);
  const [teacherCheck, setTeacherCheck] = useState(null);

  // chat di prova
  const [chatJob, setChatJob] = useState('');
  const [checkpoints, setCheckpoints] = useState([]);
  const [selectedCkpt, setSelectedCkpt] = useState('');
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const chatEnd = useRef(null);

  const distilling = mode === 'distill' || mode === 'both';

  useEffect(() => {
    fetch('/api/training/forge/status').then(r => r.json()).then(d => {
      if (!d.success) return;
      setInfo(d);
      const def = d.defaults || {};
      setArchitecture(def.architecture || 'micro');
      setTeacher(def.teacher || '');
      setSeqLen(def.seq_len || 512);
      setBatchSize(def.batch_size || 8);
      setSources((d.datasets || []).slice(0, 1).map(x => ({
        id: x.id, config: x.config, split: x.split, text_field: x.text_field, label: x.label,
      })));
    }).catch(() => {});
  }, []);

  // stima token/durata, ricalcolata a ogni cambio rilevante
  useEffect(() => {
    const params = new URLSearchParams({
      architecture, seq_len: String(seqLen), batch_size: String(batchSize),
      max_steps: String(maxSteps), mode,
    });
    const timer = setTimeout(() => {
      fetch(`/api/training/forge/estimate?${params}`).then(r => r.json())
        .then(d => d.success && setEstimate(d.estimate)).catch(() => {});
    }, 200);
    return () => clearTimeout(timer);
  }, [architecture, seqLen, batchSize, maxSteps, mode]);

  // Un id inesistente si manifesterebbe solo alla fine del pre-training:
  // meglio verificarlo appena viene scelto.
  useEffect(() => {
    if (!instructDataset?.id) { setInstructCheck(null); return; }
    setInstructCheck({ checking: true });
    fetch(`/api/training/forge/verify?dataset_id=${encodeURIComponent(instructDataset.id)}`)
      .then(r => r.json())
      .then(d => setInstructCheck(d.result))
      .catch(() => setInstructCheck(null));
  }, [instructDataset]);

  // I modelli migliori per l'italiano sono ad accesso riservato: saperlo qui
  // evita di scoprirlo dopo il download del corpus.
  useEffect(() => {
    if (!teacher || !distilling) { setTeacherCheck(null); return; }
    fetch(`/api/training/forge/verify_model?model_id=${encodeURIComponent(teacher)}`)
      .then(r => r.json())
      .then(d => setTeacherCheck(d.result))
      .catch(() => setTeacherCheck(null));
  }, [teacher, distilling]);

  const searchTeachers = useCallback(() => {
    const params = new URLSearchParams({ q: teacherQuery, limit: '20', italian: '1' });
    fetch(`/api/training/forge/teachers?${params}`)
      .then(r => r.json())
      .then(d => setTeacherResults(d.models || []))
      .catch(() => addToast && addToast('Ricerca insegnanti fallita', 'error'));
  }, [teacherQuery, addToast]);

  const searchDatasets = useCallback((instruct = false) => {
    setSearching(true);
    const params = new URLSearchParams({ q: query, limit: '25', instruct: instruct ? '1' : '0' });
    fetch(`/api/training/forge/datasets?${params}`)
      .then(r => r.json())
      .then(d => setResults(d.datasets || []))
      .catch(() => addToast && addToast('Ricerca dataset fallita', 'error'))
      .finally(() => setSearching(false));
  }, [query, addToast]);

  const loadConfigs = (datasetId) => {
    if (configs[datasetId]) return;
    fetch(`/api/training/forge/configs?dataset_id=${encodeURIComponent(datasetId)}`)
      .then(r => r.json())
      .then(d => setConfigs(prev => ({ ...prev, [datasetId]: d })))
      .catch(() => {});
  };

  const addSource = (datasetId) => {
    if (sources.some(s => s.id === datasetId)) return;
    const cfg = configs[datasetId];
    setSources([...sources, {
      id: datasetId,
      config: cfg?.suggested || null,
      split: 'train',
      text_field: 'text',
    }]);
    addToast && addToast(`Corpus aggiunto: ${datasetId}`, 'success');
  };

  const toggleFormat = (id) => setExportFormats(
    exportFormats.includes(id) ? exportFormats.filter(f => f !== id) : [...exportFormats, id]);

  const createJob = async () => {
    if (!sources.length) {
      addToast && addToast('Aggiungi almeno un corpus', 'warning');
      return;
    }
    setCreating(true);
    try {
      const res = await fetch('/api/training/job/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_model: 'from_scratch',
          method: 'slm_forge',
          dataset_id: '',
          output_name: outputName,
          hyperparams: {
            forge_architecture: architecture,
            forge_mode: mode,
            forge_teacher: teacher,
            forge_sources: sources,
            forge_tokenizer_mode: tokenizerMode,
            forge_vocab_size: vocabSize,
            forge_seq_len: seqLen,
            batch_size: batchSize,
            forge_max_steps: maxSteps,
            learning_rate: lr,
            forge_distill_alpha: alpha,
            forge_distill_temperature: temperature,
            forge_save_every: saveEvery,
            forge_instruct_dataset: instructDataset,
            forge_sft_steps: sftSteps,
            forge_export_formats: exportFormats,
          },
        }),
      });
      const data = await res.json();
      if (data.success) {
        addToast && addToast(`🔨 Job "${data.job_id}" creato — avvialo dal Monitor`, 'success', 5000);
        setChatJob(data.job_id);
        onJobCreated && onJobCreated(data.job);
      } else {
        addToast && addToast(`Errore: ${data.error}`, 'error');
      }
    } catch {
      addToast && addToast('Errore di rete', 'error');
    } finally {
      setCreating(false);
    }
  };

  // ── chat di prova ──
  const loadCheckpoints = useCallback(() => {
    if (!chatJob) return;
    fetch(`/api/training/forge/checkpoints?job_id=${chatJob}`)
      .then(r => r.json())
      .then(d => {
        setCheckpoints(d.checkpoints || []);
        if (d.checkpoints?.length && !selectedCkpt) setSelectedCkpt(d.checkpoints[0].path);
      })
      .catch(() => {});
  }, [chatJob, selectedCkpt]);

  useEffect(() => {
    if (!chatJob) return;
    loadCheckpoints();
    const timer = setInterval(loadCheckpoints, 15000);   // ne compaiono di nuovi mentre allena
    return () => clearInterval(timer);
  }, [chatJob, loadCheckpoints]);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const sendChat = async () => {
    const text = chatInput.trim();
    if (!text || chatBusy) return;
    setChatInput('');
    setMessages(m => [...m, { role: 'user', text }]);
    setChatBusy(true);
    try {
      const res = await fetch('/api/training/forge/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: chatJob, checkpoint: selectedCkpt, prompt: text,
          max_new_tokens: 120, temperature: 0.8, device: 'cpu',
        }),
      });
      const d = await res.json();
      setMessages(m => [...m, d.success
        ? { role: 'model', text: d.reply || '(vuoto)', step: d.step, device: d.device, elapsed: d.elapsed_s }
        : { role: 'error', text: d.error }]);
    } catch {
      setMessages(m => [...m, { role: 'error', text: 'Errore di rete' }]);
    } finally {
      setChatBusy(false);
    }
  };

  if (!info) {
    return <div className="training-panel"><div className="training-scroll-area">
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dim)' }}>
        Carico la forgia…
      </div></div></div>;
  }

  const arch = info.architectures.find(a => a.id === architecture);

  return (
    <div className="training-panel">
      <div className="training-scroll-area">

        {/* Top Header — Stile Hardware & GPU Lab */}
        <div className="app-page-header" style={{ marginBottom: '18px' }}>
          <div className="app-page-header-title">
            <div className="app-page-header-icon">
              <Hammer size={22} color="#00f2fe" />
            </div>
            <div>
              <h1>Forgia SLM</h1>
              <div className="app-page-header-subtitle">
                <span>Costruzione di Small Language Models da zero in italiano</span>
                <span>•</span>
                <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                  Architettura: {architecture}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── intestazione ── */}
        <div style={{
          ...SECTION, padding: '12px 16px', borderRadius: '12px',
          background: 'rgba(255,166,0,0.05)', border: '1px solid rgba(255,166,0,0.18)',
          fontSize: '0.66rem', color: 'var(--text-dim)', lineHeight: 1.6,
        }}>
          <div style={{ color: '#ffa600', fontWeight: 700, marginBottom: '4px' }}>
            🔨 SLM Forge — un modello nuovo, non un fine-tuning
          </div>
          Il modello non esiste ancora: scegli l'architettura, il corpus italiano e come
          farlo imparare. Dal testo grezzo (cross-entropy), da un modello insegnante
          (distillazione dei logit), o da entrambi. Poi fine-tuning, export e prova.
          {info.defaults.notes?.map((n, i) => (
            <div key={i} style={{ marginTop: '4px', opacity: 0.85 }}>• {n}</div>
          ))}
        </div>

        {/* ── architettura ── */}
        <div style={SECTION}>
          <div className="training-section-header"><Cpu size={14} /><h3>Architettura</h3></div>
          <div className="training-method-pills">
            {info.architectures.map(a => (
              <button key={a.id} className={`training-method-pill ${architecture === a.id ? 'active' : ''}`}
                      onClick={() => setArchitecture(a.id)}
                      style={architecture === a.id
                        ? { borderColor: 'rgba(255,166,0,0.35)', color: '#ffa600', background: 'rgba(255,166,0,0.07)' }
                        : {}}>
                <span className="training-method-pill-name">{a.label}</span>
                <span className="training-method-pill-desc">{a.desc}</span>
                <span className="training-method-pill-desc" style={{ fontSize: '0.55rem', opacity: 0.55 }}>
                  ≥{a.vram_gb}GB · ~{a.tokens_suggested_m}M token consigliati
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="training-divider" />

        {/* ── modalità ── */}
        <div style={SECTION}>
          <div className="training-section-header"><GraduationCap size={14} /><h3>Come impara</h3></div>
          <div className="training-method-pills">
            {info.modes.map(m => (
              <button key={m.id} className={`training-method-pill ${mode === m.id ? 'active' : ''}`}
                      onClick={() => setMode(m.id)}
                      style={mode === m.id
                        ? { borderColor: 'rgba(188,140,255,0.35)', color: 'var(--accent)', background: 'rgba(188,140,255,0.07)' }
                        : {}}>
                <span className="training-method-pill-name">{m.label}</span>
                <span className="training-method-pill-desc">{m.desc}</span>
              </button>
            ))}
          </div>

          {distilling && (
            <div style={{
              marginTop: '10px', padding: '10px 14px', borderRadius: '10px',
              background: 'rgba(188,140,255,0.05)', border: '1px solid rgba(188,140,255,0.15)',
            }}>
              <Field label="Modello insegnante"
                     desc="Lo studente eredita il suo tokenizer: i logit sono confrontabili solo sullo stesso vocabolario">
                <div className="training-select-wrapper">
                  <select className="training-select" value={teacher} onChange={e => setTeacher(e.target.value)}>
                    {info.teachers.map(t => (
                      <option key={t.id} value={t.id}>
                        {t.gated ? '🔒 ' : ''}{t.label} — {t.desc}
                      </option>
                    ))}
                    {teacherResults.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.gated ? '🔒 ' : ''}{m.id} — {(m.downloads || 0).toLocaleString()} download
                      </option>
                    ))}
                  </select>
                </div>
              </Field>

              <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                <input className="training-input" placeholder="Cerca altri insegnanti italiani su HuggingFace…"
                       value={teacherQuery} onChange={e => setTeacherQuery(e.target.value)}
                       onKeyDown={e => e.key === 'Enter' && searchTeachers()} style={{ flex: 1 }} />
                <button className="training-btn" onClick={searchTeachers}>
                  <Search size={12} /> Cerca
                </button>
              </div>

              {teacherCheck && (
                <div style={{
                  fontSize: '0.6rem', marginTop: '6px',
                  color: teacherCheck.accessible ? 'var(--success)' : 'var(--warning)',
                }}>
                  {teacherCheck.accessible
                    ? `✓ Accessibile${teacherCheck.vocab_size ? ` · vocabolario ${teacherCheck.vocab_size.toLocaleString()}` : ''}`
                    : `🔒 ${teacherCheck.error || 'non accessibile'}`}
                  {!teacherCheck.accessible && teacherCheck.url && (
                    <> <a href={teacherCheck.url} target="_blank" rel="noreferrer"
                          style={{ color: 'var(--primary)' }}>apri la pagina del modello</a></>
                  )}
                </div>
              )}
              <div className="training-config-grid" style={{ marginTop: '8px' }}>
                <Slider label="Peso del dataset (alpha)"
                        desc={mode === 'both' ? 'Alto = più testo, basso = più insegnante' : 'Usato solo in modalità combinata'}
                        value={alpha} min={0} max={1} step={0.05} onChange={setAlpha}
                        display={v => `${v.toFixed(2)} testo / ${(1 - v).toFixed(2)} insegnante`} />
                <Slider label="Temperatura di distillazione"
                        desc="Alta = lo studente impara anche dalle alternative meno probabili"
                        value={temperature} min={1} max={5} step={0.5} onChange={setTemperature} />
              </div>
            </div>
          )}
        </div>

        <div className="training-divider" />

        {/* ── corpus ── */}
        <div style={SECTION}>
          <div className="training-section-header">
            <Database size={14} /><h3>Corpus italiano</h3>
            <span className="training-section-sub">{sources.length} selezionati</span>
          </div>

          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
            <input className="training-input" placeholder="Cerca su HuggingFace (filtro lingua: italiano)…"
                   value={query} onChange={e => setQuery(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && searchDatasets()} style={{ flex: 1 }} />
            <button className="training-btn" onClick={() => searchDatasets(false)} disabled={searching}>
              {searching ? <Loader size={12} className="spin" /> : <Search size={12} />} Cerca
            </button>
          </div>

          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '8px' }}>
            {info.datasets.map(d => (
              <button key={d.id} onClick={() => addSource(d.id)} title={d.desc}
                      style={chip(sources.some(s => s.id === d.id), '#ffa600')}>
                ⭐ {d.label}
              </button>
            ))}
          </div>

          {results.length > 0 && (
            <div className="training-ds-selector" style={{ maxHeight: '190px', overflowY: 'auto' }}>
              {results.map(r => (
                <div key={r.id} className="training-ds-option"
                     onClick={() => { loadConfigs(r.id); addSource(r.id); }}>
                  <span style={{ fontSize: '15px' }}>🤗</span>
                  <span className="training-ds-option-name">{r.id}</span>
                  <span className="training-ds-option-meta">
                    {(r.downloads || 0).toLocaleString()} download
                  </span>
                </div>
              ))}
            </div>
          )}

          {sources.length > 0 && (
            <div style={{ marginTop: '10px' }}>
              {sources.map((s, i) => (
                <div key={s.id} style={{
                  display: 'flex', alignItems: 'center', gap: '8px', padding: '7px 10px',
                  marginBottom: '4px', borderRadius: '8px', fontSize: '0.63rem',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <span style={{ color: 'var(--text)', fontFamily: 'JetBrains Mono' }}>{s.id}</span>
                  <input className="training-input" placeholder="config (es. ita_Latn)"
                         value={s.config || ''} style={{ width: '150px', padding: '2px 8px', fontSize: '0.58rem' }}
                         onChange={e => setSources(sources.map((x, j) =>
                           j === i ? { ...x, config: e.target.value || null } : x))} />
                  <input className="training-input" placeholder="campo testo"
                         value={s.text_field || 'text'} style={{ width: '95px', padding: '2px 8px', fontSize: '0.58rem' }}
                         onChange={e => setSources(sources.map((x, j) =>
                           j === i ? { ...x, text_field: e.target.value } : x))} />
                  <button onClick={() => setSources(sources.filter((_, j) => j !== i))}
                          style={{ marginLeft: 'auto', background: 'none', border: 'none',
                                   color: 'var(--danger)', cursor: 'pointer', fontSize: '0.7rem' }}>✕</button>
                </div>
              ))}
              <div style={{ fontSize: '0.57rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                I corpus multilingua espongono l'italiano come <em>config</em> (es. <code>ita_Latn</code>,
                <code> 20231101.it</code>): senza il nome giusto scarichi la lingua sbagliata.
              </div>
            </div>
          )}
        </div>

        <div className="training-divider" />

        {/* ── tokenizer + iperparametri ── */}
        <div style={SECTION}>
          <div className="training-section-header"><Hammer size={14} /><h3>Tokenizer e training</h3></div>

          {distilling ? (
            <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginBottom: '8px',
                          padding: '8px 12px', borderRadius: '8px',
                          background: 'rgba(188,140,255,0.05)' }}>
              Tokenizer ereditato dall'insegnante (obbligatorio in distillazione).
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
              <button onClick={() => setTokenizerMode('train')} style={chip(tokenizerMode === 'train')}>
                Addestra un tokenizer italiano
              </button>
              <button onClick={() => setTokenizerMode('reuse')} style={chip(tokenizerMode === 'reuse')}>
                Riusa uno esistente
              </button>
            </div>
          )}

          <div className="training-config-grid">
            {!distilling && tokenizerMode === 'train' && (
              <Slider label="Dimensione vocabolario" desc="Più grande = testo più compresso, modello più pesante"
                      value={vocabSize} min={8000} max={64000} step={4000} onChange={setVocabSize} />
            )}
            <Slider label="Lunghezza sequenza" desc="Token per esempio"
                    value={seqLen} min={128} max={arch?.max_position_embeddings || 1024} step={128}
                    onChange={setSeqLen} />
            <Slider label="Batch size" desc="Sequenze per step"
                    value={batchSize} min={1} max={64} step={1} onChange={setBatchSize} />
            <Slider label="Step di training" desc="Checkpoint periodici per la chat di prova"
                    value={maxSteps} min={100} max={50000} step={100} onChange={setMaxSteps} />
            <Slider label="Learning rate" desc="3e-4 è il valore tipico da zero"
                    value={lr} min={1e-5} max={1e-3} step={1e-5} onChange={setLr}
                    display={v => v.toExponential(1)} />
            <Slider label="Checkpoint ogni" desc="Step fra un salvataggio e il successivo"
                    value={saveEvery} min={20} max={2000} step={20} onChange={setSaveEvery} />
          </div>

          {estimate && (
            <div style={{
              marginTop: '10px', padding: '10px 14px', borderRadius: '10px',
              fontSize: '0.62rem', lineHeight: 1.6, color: 'var(--text-dim)',
              background: 'rgba(0,210,255,0.04)', border: '1px solid rgba(0,210,255,0.13)',
            }}>
              <strong style={{ color: 'var(--primary)' }}>Stima:</strong>{' '}
              {estimate.tokens_millions}M token · ~{estimate.hours}h · modello {estimate.params_m}M parametri
              {estimate.coverage_pct != null && (
                <> · <span style={{ color: estimate.coverage_pct < 20 ? 'var(--warning)' : 'var(--success)' }}>
                  {estimate.coverage_pct}% del budget consigliato ({estimate.tokens_suggested_millions}M)
                </span></>
              )}
              {estimate.note && <div style={{ marginTop: '3px', color: 'var(--warning)' }}>{estimate.note}</div>}
            </div>
          )}
        </div>

        <div className="training-divider" />

        {/* ── fine-tuning + export ── */}
        <div style={SECTION}>
          <div className="training-section-header"><Package size={14} /><h3>Fine-tuning ed export</h3></div>

          <Field label="Dataset di istruzioni (opzionale)"
                 desc="Dopo il pre-training, insegna al modello a rispondere invece di proseguire il testo">
            <div className="training-select-wrapper">
              <select className="training-select" value={instructDataset?.id || ''}
                      onChange={e => setInstructDataset(
                        e.target.value ? { id: e.target.value, split: 'train' } : null)}>
                <option value="">Nessuno — solo pre-training</option>
                {info.instruct_datasets.map(d => (
                  <option key={d.id} value={d.id}>{d.label} — {d.desc}</option>
                ))}
              </select>
            </div>
          </Field>

          {instructCheck && !instructCheck.checking && (
            <div style={{
              fontSize: '0.6rem', marginTop: '-4px', marginBottom: '8px',
              color: instructCheck.exists ? 'var(--success)' : 'var(--danger)',
            }}>
              {instructCheck.exists
                ? `✓ Dataset disponibile su HuggingFace${instructCheck.downloads ? ` · ${instructCheck.downloads} download` : ''}`
                : `✗ Non accessibile (${instructCheck.error || 'assente'}) — il fine-tuning verrà saltato, il modello pre-addestrato resta valido`}
            </div>
          )}

          {instructDataset && (
            <Slider label="Step di fine-tuning" desc="Poche centinaia bastano su un modello piccolo"
                    value={sftSteps} min={50} max={5000} step={50} onChange={setSftSteps} />
          )}

          <div style={{ marginTop: '10px' }}>
            <label style={{ fontSize: '0.68rem', color: 'var(--text)' }}>Formati di export</label>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
              {info.export_formats.map(f => (
                <button key={f.id} title={f.desc}
                        onClick={() => !f.always && toggleFormat(f.id)}
                        style={{ ...chip(f.always || exportFormats.includes(f.id), '#3fb950'),
                                 cursor: f.always ? 'default' : 'pointer' }}>
                  {(f.always || exportFormats.includes(f.id)) && <Check size={9} style={{ marginRight: 3 }} />}
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <Field label="Nome del modello" desc="Usato per i file esportati e in Ollama">
            <input className="training-input" value={outputName}
                   onChange={e => setOutputName(e.target.value.replace(/\s+/g, '_').toLowerCase())} />
          </Field>
        </div>

        <button className="training-start-btn" onClick={createJob}
                disabled={creating || !sources.length}>
          {creating
            ? <><div className="training-spinner" style={{ width: 16, height: 16 }} /> Creazione…</>
            : <><Play size={16} fill="currentColor" /> Forgia il modello</>}
        </button>

        <div className="training-divider" />

        {/* ── chat di prova ── */}
        <div style={SECTION}>
          <div className="training-section-header">
            <MessageSquare size={14} /><h3>Prova i checkpoint</h3>
            <span className="training-section-sub">gira su CPU: le GPU restano al training</span>
          </div>

          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
            <input className="training-input" placeholder="ID del job (es. 5f42532a)"
                   value={chatJob} onChange={e => setChatJob(e.target.value.trim())}
                   style={{ width: '170px' }} />
            <div className="training-select-wrapper" style={{ flex: 1 }}>
              <select className="training-select" value={selectedCkpt}
                      onChange={e => setSelectedCkpt(e.target.value)}>
                {checkpoints.length === 0 && <option value="">Nessun checkpoint ancora</option>}
                {checkpoints.map(c => (
                  <option key={c.path} value={c.path}>
                    {c.final ? '★ ' : ''}{c.name}{c.step ? ` · step ${c.step}` : ''} · {c.updated_at}
                  </option>
                ))}
              </select>
            </div>
            <button className="training-btn" onClick={loadCheckpoints} title="Aggiorna la lista">
              <RefreshCw size={12} />
            </button>
          </div>

          <div style={{
            minHeight: '120px', maxHeight: '260px', overflowY: 'auto', padding: '10px',
            borderRadius: '10px', background: 'rgba(0,0,0,0.18)',
            border: '1px solid rgba(255,255,255,0.05)', marginBottom: '8px',
          }}>
            {messages.length === 0 && (
              <div style={{ color: 'var(--text-dark)', fontSize: '0.62rem', textAlign: 'center', padding: '24px 0' }}>
                Scrivi qualcosa per sentire come parla il modello a questo punto del training.
                <br />Gira su CPU, quindi impiega qualche secondo ma non rallenta il training.
                <br />All'inizio produrrà solo rumore: è normale, serve a vedere i progressi.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{ marginBottom: '8px', fontSize: '0.65rem', lineHeight: 1.55 }}>
                <div style={{
                  color: m.role === 'user' ? 'var(--primary)'
                    : m.role === 'error' ? 'var(--danger)' : 'var(--success)',
                  fontWeight: 700, fontSize: '0.58rem', marginBottom: '2px',
                }}>
                  {m.role === 'user' ? 'tu' : m.role === 'error' ? 'errore' : 'modello'}
                  {m.step != null && <span style={{ opacity: 0.6, fontWeight: 400 }}>
                    {' '}· step {m.step} · {m.device} · {m.elapsed}s
                  </span>}
                </div>
                <div style={{ color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{m.text}</div>
              </div>
            ))}
            <div ref={chatEnd} />
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            <input className="training-input" placeholder="Scrivi un prompt…" value={chatInput}
                   onChange={e => setChatInput(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && sendChat()}
                   disabled={!checkpoints.length} style={{ flex: 1 }} />
            <button className="training-btn primary" onClick={sendChat}
                    disabled={chatBusy || !checkpoints.length}>
              {chatBusy ? <Loader size={12} className="spin" /> : <Send size={12} />} Invia
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
