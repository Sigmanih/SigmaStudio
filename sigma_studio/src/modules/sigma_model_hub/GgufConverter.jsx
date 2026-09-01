import React, { useState, useEffect, useCallback } from 'react';
import {
  Package, Download, Play, AlertTriangle, CheckCircle2, Loader, Upload,
  Layers, Cpu, Zap, HardDrive, ShieldCheck, ChevronDown, Check, Info, Dna, Sparkles, Activity
} from 'lucide-react';
import HfPublishModal from './HfPublishModal.jsx';

/**
 * Converts a downloaded Hugging Face checkpoint into GGUF so it can run on the
 * llama.cpp backend. Sits after the download tab because that is the order the
 * work happens in: fetch the weights, then make them runnable on this machine.
 *
 * The job list is owned by the hub, not by this component: a conversion runs
 * for minutes on the server, and leaving this tab must not stop the progress
 * from being polled and shown.
 */
export default function GgufConverter({ isLight, addToast, initialModel, jobs = [], onJobsChanged }) {
  const [models, setModels] = useState([]);
  const [quantTypes, setQuantTypes] = useState([]);
  const [tooling, setTooling] = useState(null);
  const [selected, setSelected] = useState(initialModel || '');
  const [quant, setQuant] = useState('Q4_K_M');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [publishingModel, setPublishingModel] = useState(null);
  // Un rifiuto del server ("mancano 59 GB") non puo' vivere in un toast che
  // sparisce: e' la risposta alla domanda "perche' il pulsante non fa nulla",
  // e deve restare sotto il pulsante finche' non cambia la scelta.
  const [startError, setStartError] = useState(null);
  // L'intermedio a 8 bit e' gia' un modello utilizzabile, e ripartire da li'
  // salta la conversione dai safetensors, che e' la fase lunga. Costa lo
  // spazio di tenerselo, quindi la scelta e' dell'utente.
  const [keepIntermediate, setKeepIntermediate] = useState(false);

  useEffect(() => {
    if (initialModel) {
      setSelected(initialModel);
    }
  }, [initialModel]);

  useEffect(() => { setStartError(null); }, [selected, quant]);

  const cardBg = isLight ? '#ffffff' : 'rgba(15, 18, 28, 0.85)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.28)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.20)' : '1px solid rgba(255, 255, 255, 0.06)';
  const inputBg = isLight ? '#f4eee2' : 'rgba(8, 10, 18, 0.85)';
  const optionBg = isLight ? '#ffffff' : '#0d111d';

  const fetchInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/models/convert/info');
      if (!res.ok) {
        setLoadError(
          res.status === 404
            ? 'Endpoint di conversione non registrato: riavvia il server Sigma Studio.'
            : `Il server ha risposto ${res.status}.`
        );
        return;
      }
      const json = await res.json();
      setLoadError(json.success ? null : (json.error || 'Risposta non valida.'));
      if (json.success) {
        setModels(json.models || []);
        setQuantTypes(json.quantization_types || []);
        setTooling(json.tooling || null);
        if (!selected && json.models?.length) setSelected(initialModel || json.models[0].name);
      }
    } catch (e) {
      setLoadError(`Impossibile contattare il server: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [initialModel, selected]);

  useEffect(() => { fetchInfo(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const activeJob = jobs.find(j => ['queued', 'converting', 'quantizing'].includes(j.status));

  const installTooling = async () => {
    setBusy(true);
    try {
      const res = await fetch('/api/models/convert/tooling', { method: 'POST' });
      const json = await res.json();
      if (addToast) addToast(json.success ? `✅ ${json.message}` : `❌ ${json.error}`,
        json.success ? 'info' : 'error');
      fetchInfo();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  const startConversion = async () => {
    setBusy(true);
    setStartError(null);
    try {
      const res = await fetch('/api/models/convert/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selected,
          quantization: quant,
          keep_intermediate: keepIntermediate,
        }),
      });
      const json = await res.json();
      if (json.success) {
        if (onJobsChanged) onJobsChanged();
        if (addToast) addToast('🔄 Conversione avviata: prosegue anche se cambi scheda.', 'info');
      } else {
        setStartError(json);
        if (addToast) addToast(`❌ ${json.error}`, 'error');
      }
    } catch (e) {
      setStartError({ error: e.message });
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  const model = models.find(m => m.name === selected);
  const estimate = model?.estimated_outputs?.[quant];
  const quantMeta = quantTypes.find(q => q.id === quant);

  // Quick Preset Quantizations
  const POPULAR_QUANTS = [
    { id: 'Q4_K_M', label: '⚡ Q4_K_M', tag: 'Consigliato', color: '#10b981' },
    { id: 'Q5_K_M', label: '⚡ Q5_K_M', tag: 'Alta Fedeltà', color: '#00d2ff' },
    { id: 'Q8_0', label: '⚡ Q8_0', tag: 'Lossless', color: '#bc8cff' },
    { id: 'Q4_K_S', label: '⚡ Q4_K_S', tag: 'Leggero', color: '#38bdf8' },
    { id: 'Q3_K_M', label: '⚡ Q3_K_M', tag: 'Basso VRAM', color: '#f59e0b' },
    { id: 'Q6_K', label: '⚡ Q6_K', tag: 'Bilanciato', color: '#a855f7' },
    { id: 'IQ4_XS', label: '⚡ IQ4_XS', tag: 'iMatrix', color: '#ff79c6' },
  ];

  // Le due larghezze che il convertitore sa produrre: q8_0 quando lo spazio
  // stringe, altrimenti i 16 bit pieni. Quale delle due lo decide il server.
  const intermedioQ8Gb = model?.params_b
    ? (model.params_b * 1e9 * 1.0625) / 2 ** 30
    : null;
  const intermedio16Gb = model?.params_b
    ? (model.params_b * 1e9 * 2) / 2 ** 30
    : null;

  const diskPlan = startError?.disk_plan;
  const fittingQuants = diskPlan
    ? quantTypes
        .filter(q => {
          const out = model?.estimated_outputs?.[q.id];
          return out != null && diskPlan.intermediate_gb + out <= diskPlan.free_gb;
        })
        .map(q => q.id)
    : [];

  // Reso a parte perche' va mostrato anche durante il caricamento: la
  // conversione prosegue sul server mentre si sta su un'altra scheda, e al
  // rientro l'avanzamento deve essere subito li', non dietro uno spinner.
  const jobsPanel = jobs.length > 0 ? (
    <div style={{
      padding: '16px 18px', borderRadius: '14px', background: cardBg,
      border: cardBorder, display: 'flex', flexDirection: 'column', gap: '10px'
    }}>
      <div style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Activity size={14} color="#00d2ff" /> Storico & Attività di Conversione
      </div>

      {jobs.map(job => (
        <div key={job.job_id} style={{
          padding: '10px 14px', borderRadius: '10px',
          background: subBg, border: subBorder,
          display: 'flex', flexDirection: 'column', gap: '6px',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontSize: '0.76rem', color: textPrimary, fontWeight: 700,
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {job.status === 'completed' && <CheckCircle2 size={14} color="#10b981" />}
              {job.status === 'failed' && <AlertTriangle size={14} color="#ef4444" />}
              {['queued', 'converting', 'quantizing'].includes(job.status) && <Loader size={14} className="mh-spin" color="#00d2ff" />}
              <span>{job.source_model}</span>
              <span style={{ color: '#00d2ff' }}>➔</span>
              <span style={{ color: '#10b981' }}>{job.quantization}</span>
            </span>
            <span style={{ color: textMuted, fontSize: '0.68rem', fontWeight: 600 }}>
              {job.elapsed_seconds}s
            </span>
          </div>

          {['converting', 'quantizing'].includes(job.status) && (
            <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{
                width: `${job.progress}%`, height: '100%', borderRadius: '3px',
                background: 'linear-gradient(90deg, #00d2ff, #10b981)',
                transition: 'width 0.4s ease',
              }} />
            </div>
          )}

          {(job.tensor_overrides || []).some(v => v.tipo) && (
            <div style={{
              padding: '7px 10px', borderRadius: '8px',
              background: 'rgba(255, 184, 108, 0.10)',
              border: '1px solid rgba(255, 184, 108, 0.30)',
              fontSize: '0.68rem', color: textMuted, lineHeight: 1.5
            }}>
              <b style={{ color: '#ffb86c' }}>Tensori riportati sotto i 50 GB.</b>{' '}
              Un singolo tensore oltre quel limite rende il modello impubblicabile su
              Hugging Face, e lo split non taglia dentro un tensore.
              {job.tensor_overrides.filter(v => v.tipo).map(v => (
                <div key={v.tensore} style={{ fontFamily: 'monospace', marginTop: '3px' }}>
                  {v.tensore} → <b style={{ color: '#10b981' }}>{v.tipo}</b>{' '}
                  ({v.gb_prima} → {v.gb_dopo} GB)
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
            <div style={{ fontSize: '0.70rem', color: job.status === 'failed' ? '#ef4444' : textMuted }}>
              {job.error || job.message}
            </div>

            {job.status === 'completed' && (
              <button
                onClick={() => setPublishingModel({
                  filename: job.output_filename || `${job.source_model}-${job.quantization}.gguf`,
                  path: job.output_path || job.output_filename,
                  format_tag: 'GGUF',
                  quantization: job.quantization
                })}
                style={{
                  padding: '4px 10px', borderRadius: '6px',
                  border: '1px solid rgba(255, 184, 108, 0.4)',
                  background: 'rgba(255, 184, 108, 0.12)',
                  color: '#ffb86c', fontSize: '0.68rem', fontWeight: 800,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                <Upload size={11} /> Pubblica su Hugging Face
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  ) : null;

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{
          padding: '30px', borderRadius: '14px', background: cardBg, border: cardBorder,
          textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px'
        }}>
          <Activity className="mh-spin" size={22} color="#00d2ff" />
          <span style={{ fontSize: '0.80rem' }}>Scansione modelli Safetensors e strumenti di conversione…</span>
        </div>
        {jobsPanel}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={{
        padding: '18px 20px', borderRadius: '14px', background: cardBg,
        border: cardBorder, display: 'flex', flexDirection: 'column', gap: '16px',
        boxShadow: isLight ? '0 2px 12px rgba(0,0,0,0.04)' : '0 4px 20px rgba(0,0,0,0.25)'
      }}>
        {/* Header Title */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25), rgba(0, 210, 255, 0.15))',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Package size={19} color="#10b981" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.08rem', fontWeight: 900, color: textPrimary, letterSpacing: '-0.02em' }}>
                Convertitore GGUF & Quantizzazione
              </h2>
              <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
                Trasforma un checkpoint Safetensors in GGUF quantizzato, ottimizzato per l'inferenza ultra-rapida su llama.cpp (GPU, Apple Metal o CPU).
              </div>
            </div>
          </div>

          {tooling?.ready && (
            <div style={{
              fontSize: '0.66rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
              background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.35)',
              color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px'
            }}>
              <ShieldCheck size={12} /> Tooling llama.cpp v{tooling.converter_version || 'ready'}
            </div>
          )}
        </div>

        {/* Tooling Alert Banner */}
        {tooling && !tooling.ready && (
          <div style={{
            padding: '12px 16px', borderRadius: '10px',
            background: 'rgba(245, 158, 11, 0.10)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            display: 'flex', flexDirection: 'column', gap: '8px',
          }}>
            <div style={{ fontSize: '0.78rem', color: isLight ? '#92400e' : '#fbbf24', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={14} color="#fbbf24" />
              Strumento di conversione non ancora installato
            </div>
            <div style={{ fontSize: '0.72rem', color: textMuted, lineHeight: 1.5 }}>
              La conversione usa lo script ufficiale di <code>llama.cpp</code>
              (versione <code>{tooling.converter_version}</code>), scaricato una sola volta e poi eseguito localmente.
              La quantizzazione gira interamente in-process a massima efficienza.
            </div>
            <button
              onClick={installTooling}
              disabled={busy}
              style={{
                alignSelf: 'flex-start', padding: '6px 14px', borderRadius: '7px',
                border: 'none', background: 'linear-gradient(135deg, #fbbf24, #f59e0b)',
                color: '#111827', fontSize: '0.72rem', fontWeight: 900, cursor: busy ? 'wait' : 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                boxShadow: '0 2px 10px rgba(245, 158, 11, 0.35)'
              }}
            >
              <Download size={12} />
              {busy ? 'Installazione in corso...' : 'Scarica lo strumento'}
            </button>
          </div>
        )}

        {loadError ? (
          <div style={{
            padding: '12px 14px', borderRadius: '10px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            fontSize: '0.76rem', color: '#ef4444',
          }}>
            {loadError}
          </div>
        ) : models.length === 0 ? (
          <div style={{
            padding: '24px', borderRadius: '10px', background: subBg, border: subBorder,
            textAlign: 'center', color: textMuted, fontSize: '0.78rem'
          }}>
            📦 Nessun modello Safetensors trovato nello storage locale. I modelli GGUF non compaiono qui perché sono già pronti.
          </div>
        ) : (
          /* STYLED DUAL SELECT ROW */
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>

            {/* 1. SELECT MODELLO DI PARTENZA */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{
                fontSize: '0.68rem', fontWeight: 800, color: '#00d2ff',
                letterSpacing: '0.03em', textTransform: 'uppercase',
                display: 'flex', alignItems: 'center', gap: '5px'
              }}>
                <Layers size={13} color="#00d2ff" /> MODELLO SAFETENSORS DI PARTENZA
              </div>

              <div style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                background: inputBg,
                border: isLight ? '1.5px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(0, 210, 255, 0.3)',
                borderRadius: '10px',
                padding: '0 12px',
                transition: 'all 0.15s ease',
                boxShadow: isLight ? '0 1px 4px rgba(0,0,0,0.03)' : '0 2px 8px rgba(0,0,0,0.25)'
              }}>
                <select
                  value={selected}
                  onChange={e => setSelected(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 24px 10px 0',
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: textPrimary,
                    fontSize: '0.80rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    appearance: 'none',
                    WebkitAppearance: 'none'
                  }}
                >
                  {models.map(m => (
                    <option
                      key={m.name}
                      value={m.name}
                      style={{ background: optionBg, color: textPrimary, padding: '8px' }}
                    >
                      📦 {m.name} ({m.params_b ? `${m.params_b}B params` : ''} • {m.size_gb} GB)
                    </option>
                  ))}
                </select>
                <div style={{ position: 'absolute', right: '12px', pointerEvents: 'none', display: 'flex', alignItems: 'center' }}>
                  <ChevronDown size={15} color="#00d2ff" />
                </div>
              </div>
            </div>

            {/* 2. SELECT QUANTIZZAZIONE */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{
                fontSize: '0.68rem', fontWeight: 800, color: '#ffb86c',
                letterSpacing: '0.03em', textTransform: 'uppercase',
                display: 'flex', alignItems: 'center', gap: '5px'
              }}>
                <Cpu size={13} color="#ffb86c" /> FORMATO & QUANTIZZAZIONE GGUF
              </div>

              <div style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                background: inputBg,
                border: isLight ? '1.5px solid rgba(255, 184, 108, 0.45)' : '1px solid rgba(255, 184, 108, 0.35)',
                borderRadius: '10px',
                padding: '0 12px',
                transition: 'all 0.15s ease',
                boxShadow: isLight ? '0 1px 4px rgba(0,0,0,0.03)' : '0 2px 8px rgba(0,0,0,0.25)'
              }}>
                <select
                  value={quant}
                  onChange={e => setQuant(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 24px 10px 0',
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: textPrimary,
                    fontSize: '0.80rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    appearance: 'none',
                    WebkitAppearance: 'none'
                  }}
                >
                  {quantTypes.map(q => (
                    <option
                      key={q.id}
                      value={q.id}
                      style={{ background: optionBg, color: textPrimary, padding: '8px' }}
                    >
                      ⚡ {q.label} {q.note ? `— ${q.note}` : ''}
                    </option>
                  ))}
                </select>
                <div style={{ position: 'absolute', right: '12px', pointerEvents: 'none', display: 'flex', alignItems: 'center' }}>
                  <ChevronDown size={15} color="#ffb86c" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* QUICK QUANT PRESET PILLS */}
        {models.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>
              Preset Rapidi Quantizzazione:
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              {POPULAR_QUANTS.map(p => {
                const active = quant === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => setQuant(p.id)}
                    style={{
                      padding: '4px 9px', borderRadius: '7px',
                      border: active ? `1.5px solid ${p.color}` : subBorder,
                      background: active ? `${p.color}22` : subBg,
                      color: active ? p.color : textMuted,
                      fontSize: '0.68rem', fontWeight: active ? 900 : 700, cursor: 'pointer',
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      boxShadow: active ? `0 0 10px ${p.color}35` : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <span>{p.label}</span>
                    <span style={{
                      fontSize: '0.56rem', padding: '1px 4px', borderRadius: '3px',
                      background: active ? `${p.color}35` : 'rgba(255,255,255,0.06)',
                      color: active ? '#ffffff' : textMuted, fontWeight: 800
                    }}>
                      {p.tag}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* MODEL TELEMETRY & VRAM ESTIMATION CARD */}
        {model && (
          <div style={{
            padding: '14px 16px', borderRadius: '12px',
            background: isLight ? 'rgba(0, 210, 255, 0.04)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.06) 0%, rgba(15, 18, 28, 0.95) 100%)',
            border: isLight ? '1px solid rgba(0, 210, 255, 0.25)' : '1px solid rgba(0, 210, 255, 0.18)',
            display: 'flex', flexDirection: 'column', gap: '10px'
          }}>
            {/* Top Specs Row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: '0.74rem', fontWeight: 900, color: textPrimary,
                  display: 'inline-flex', alignItems: 'center', gap: '4px'
                }}>
                  <Dna size={14} color="#00d2ff" /> {model.architecture || 'Architettura LLM'}
                </span>
                <span style={{ fontSize: '0.68rem', color: textMuted }}>
                  • {model.layers} layer totali
                </span>
                {model.is_multimodal && (
                  <span style={{
                    fontSize: '0.60rem', padding: '1px 6px', borderRadius: '4px',
                    background: 'rgba(168, 85, 247, 0.15)', border: '1px solid rgba(168, 85, 247, 0.35)', color: '#a855f7', fontWeight: 800
                  }}>
                    👁️ Multimodale (Vision/Audio)
                  </span>
                )}
              </div>

              {/* VRAM Fit Badge */}
              {model.fits_in_vram?.per_quantization && (
                <div>
                  {model.fits_in_vram.per_quantization[quant] ? (
                    <span style={{
                      fontSize: '0.68rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
                      background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.4)',
                      color: '#10b981', display: 'inline-flex', alignItems: 'center', gap: '4px'
                    }}>
                      <CheckCircle2 size={12} color="#10b981" /> Entra in VRAM ({model.fits_in_vram.usable_vram_gb} GB disponibili)
                    </span>
                  ) : (
                    <span style={{
                      fontSize: '0.68rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
                      background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.4)',
                      color: '#fbbf24', display: 'inline-flex', alignItems: 'center', gap: '4px'
                    }}>
                      <AlertTriangle size={12} color="#fbbf24" /> Richiede RAM di sistema ({model.fits_in_vram.usable_vram_gb} GB VRAM)
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Size Compression Bar */}
            <div style={{
              padding: '10px 14px', borderRadius: '10px',
              background: subBg, border: subBorder,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px'
            }}>
              <div style={{ fontSize: '0.74rem', color: textPrimary, fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>📦 Originale: <b>{model.size_gb} GB</b> (Safetensors)</span>
                <span style={{ color: '#00d2ff' }}>➔</span>
                <span style={{ color: '#10b981' }}>⚡ Output GGUF: <b>~{estimate ?? '?'} GB</b> ({quant})</span>
              </div>

              {quantMeta?.note && (
                <div style={{ fontSize: '0.68rem', color: textMuted, fontStyle: 'italic' }}>
                  ℹ️ {quantMeta.note}
                </div>
              )}
            </div>

            {/* VRAM Recommendations if too large */}
            {model.fits_in_vram?.largest_that_fits && !model.fits_in_vram.per_quantization?.[quant] && (
              <div style={{
                fontSize: '0.70rem', color: isLight ? '#92400e' : '#fbbf24',
                background: 'rgba(245, 158, 11, 0.08)', padding: '6px 10px', borderRadius: '6px',
                border: '1px solid rgba(245, 158, 11, 0.25)'
              }}>
                💡 Con questa scelta la maggior parte dei layer girerebbe dalla RAM di sistema. La quantizzazione più fedele che entra completamente in VRAM è <b>{model.fits_in_vram.largest_that_fits}</b>.
              </div>
            )}

            {model.already_converted && (
              <div style={{ fontSize: '0.68rem', color: '#ffb86c' }}>
                ℹ️ Esiste già una versione convertita nella cartella <code>{model.name}-GGUF</code>.
              </div>
            )}
          </div>
        )}

        {/* CONSERVA L'INTERMEDIO */}
        {models.length > 0 && quant !== 'F16' && (
          <label style={{
            display: 'flex', alignItems: 'flex-start', gap: '9px',
            padding: '10px 12px', borderRadius: '10px',
            background: keepIntermediate ? 'rgba(16, 185, 129, 0.08)' : subBg,
            border: keepIntermediate ? '1px solid rgba(16, 185, 129, 0.35)' : subBorder,
            cursor: 'pointer', transition: 'all 0.15s ease'
          }}>
            <input
              type="checkbox"
              checked={keepIntermediate}
              onChange={e => setKeepIntermediate(e.target.checked)}
              style={{ marginTop: '2px', accentColor: '#10b981', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: textPrimary }}>
                Conserva anche il GGUF intermedio come modello a sé
              </span>
              <span style={{ fontSize: '0.68rem', color: textMuted, lineHeight: 1.5 }}>
                Per arrivare a {quant} il convertitore produce comunque un GGUF a piena
                precisione e poi lo riduce. Conservandolo ottieni due modelli da una
                sola conversione, e le prossime quantizzazioni ripartono da lì saltando
                la fase lunga.
                {intermedioQ8Gb != null && (
                  <> Occupa <b style={{ color: '#ffb86c' }}>
                    ~{intermedioQ8Gb.toFixed(1)}–{intermedio16Gb.toFixed(1)} GB
                  </b> in più a lavoro finito, secondo l'intermedio che il server sceglie in base allo spazio libero.</>
                )}
              </span>
            </div>
          </label>
        )}

        {/* PRIMARY CONVERT BUTTON */}
        <button
          onClick={startConversion}
          disabled={busy || !selected || !tooling?.ready || !!activeJob || !!model?.compatibility?.blocked_by?.length}
          style={{
            alignSelf: 'flex-start', padding: '9px 20px', borderRadius: '10px',
            border: 'none',
            background: (busy || !tooling?.ready || !!activeJob)
              ? 'rgba(107,114,128,0.2)'
              : 'linear-gradient(135deg, #10b981, #059669)',
            color: (busy || !tooling?.ready || !!activeJob) ? textMuted : '#ffffff',
            fontSize: '0.78rem', fontWeight: 900,
            cursor: (busy || !tooling?.ready || !!activeJob) ? 'not-allowed' : 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            boxShadow: (busy || !tooling?.ready || !!activeJob) ? 'none' : '0 2px 14px rgba(16, 185, 129, 0.35)',
            transition: 'all 0.15s ease'
          }}
        >
          {activeJob ? <Activity className="mh-spin" size={13} /> : <Play size={13} />}
          <span>{activeJob ? 'Conversione in corso…' : '⚡ Avvia Conversione in GGUF'}</span>
        </button>

        {/* Perche' l'avvio e' stato rifiutato. Resta finche' non cambia la scelta. */}
        {startError && (
          <div style={{
            padding: '12px 14px', borderRadius: '10px',
            background: 'rgba(239, 68, 68, 0.10)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            display: 'flex', flexDirection: 'column', gap: '8px'
          }}>
            <div style={{
              fontSize: '0.76rem', fontWeight: 800, color: '#ef4444',
              display: 'flex', alignItems: 'center', gap: '6px'
            }}>
              <AlertTriangle size={14} color="#ef4444" /> Conversione non avviata
            </div>
            <div style={{ fontSize: '0.74rem', color: textPrimary, lineHeight: 1.5 }}>
              {startError.error || 'Il server ha rifiutato la richiesta senza indicarne il motivo.'}
            </div>

            {diskPlan && (
              <div style={{
                display: 'flex', flexWrap: 'wrap', gap: '10px',
                padding: '8px 10px', borderRadius: '8px',
                background: subBg, border: subBorder,
                fontSize: '0.70rem', color: textMuted, fontFamily: 'monospace'
              }}>
                <span>Intermedio <b style={{ color: textPrimary }}>{diskPlan.intermediate_gb} GB</b></span>
                <span>+ Risultato <b style={{ color: textPrimary }}>{diskPlan.final_gb} GB</b></span>
                <span>= Servono <b style={{ color: '#ef4444' }}>{diskPlan.needed_gb} GB</b></span>
                <span>Liberi <b style={{ color: textPrimary }}>{diskPlan.free_gb} GB</b></span>
                <span>Mancano <b style={{ color: '#ef4444' }}>{diskPlan.missing_gb} GB</b></span>
              </div>
            )}

            {diskPlan && (
              <div style={{ fontSize: '0.70rem', color: textMuted, lineHeight: 1.5 }}>
                {fittingQuants.length > 0
                  ? <>💡 Con lo spazio attuale entrerebbero: <b style={{ color: '#10b981' }}>{fittingQuants.join(', ')}</b>.</>
                  : <>💡 Nessuna quantizzazione entra nello spazio rimasto: il solo file intermedio occupa {diskPlan.intermediate_gb} GB. Libera almeno {diskPlan.missing_gb} GB, oppure sposta la cartella dei modelli su un disco piu' capiente dalle Impostazioni.</>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* RECENT / ACTIVE CONVERSION JOBS */}
      {jobsPanel}

      {publishingModel && (
        <HfPublishModal
          model={publishingModel}
          onClose={() => setPublishingModel(null)}
          isLight={isLight}
          addToast={addToast}
        />
      )}
    </div>
  );
}
