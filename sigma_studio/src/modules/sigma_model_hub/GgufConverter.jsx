import React, { useState, useEffect, useCallback } from 'react';
import { Package, Download, Play, AlertTriangle, CheckCircle2, Loader } from 'lucide-react';

/**
 * Converts a downloaded Hugging Face checkpoint into GGUF so it can run on the
 * llama.cpp backend. Sits after the download tab because that is the order the
 * work happens in: fetch the weights, then make them runnable on this machine.
 */
export default function GgufConverter({ isLight, addToast }) {
  const [models, setModels] = useState([]);
  const [quantTypes, setQuantTypes] = useState([]);
  const [tooling, setTooling] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState('');
  const [quant, setQuant] = useState('Q4_K_M');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const cardBg = isLight ? '#ffffff' : 'rgba(255,255,255,0.03)';
  const cardBorder = isLight ? '1px solid #e5e7eb' : '1px solid rgba(255,255,255,0.08)';
  const textPrimary = isLight ? '#111827' : '#e5e7eb';
  const textMuted = isLight ? '#6b7280' : '#9ca3af';
  const inputBg = isLight ? '#f9fafb' : 'rgba(0,0,0,0.25)';

  const fetchInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/models/convert/info');
      if (!res.ok) {
        // Distinguish "the server could not answer" from "there is nothing to
        // convert": showing the empty-state for a 404 sent us hunting for
        // missing models when the endpoint simply was not registered.
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
        setJobs(json.jobs || []);
        if (!selected && json.models?.length) setSelected(json.models[0].name);
      }
    } catch (e) {
      setLoadError(`Impossibile contattare il server: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [addToast, selected]);

  useEffect(() => { fetchInfo(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // A conversion runs for minutes; poll only while one is actually active.
  const activeJob = jobs.find(j => ['queued', 'converting', 'quantizing'].includes(j.status));
  useEffect(() => {
    if (!activeJob) return undefined;
    const timer = setInterval(async () => {
      try {
        const res = await fetch('/api/models/convert/jobs');
        const json = await res.json();
        if (json.success) setJobs(json.jobs || []);
      } catch { /* transient; the next tick retries */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [activeJob]);

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
    try {
      const res = await fetch('/api/models/convert/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selected, quantization: quant }),
      });
      const json = await res.json();
      if (json.success) {
        setJobs([json.job, ...jobs]);
        if (addToast) addToast('🔄 Conversione avviata.', 'info');
      } else if (addToast) addToast(`❌ ${json.error}`, 'error');
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  const model = models.find(m => m.name === selected);
  const estimate = model?.estimated_outputs?.[quant];
  const quantMeta = quantTypes.find(q => q.id === quant);

  const panel = {
    padding: '18px', borderRadius: '14px', background: cardBg,
    border: cardBorder, display: 'flex', flexDirection: 'column', gap: '14px',
  };
  const label = { fontSize: '0.72rem', fontWeight: 800, color: textMuted, marginBottom: '4px' };
  const field = {
    width: '100%', padding: '9px 12px', borderRadius: '8px', background: inputBg,
    border: cardBorder, color: textPrimary, fontSize: '0.82rem',
  };

  if (loading) {
    return <div style={{ ...panel, color: textMuted }}>Lettura dei modelli locali…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={panel}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: textPrimary }}>
            <Package size={15} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
            Conversione in GGUF
          </h2>
          <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '4px' }}>
            Trasforma un modello safetensors in GGUF quantizzato, eseguibile dal
            backend llama.cpp su GPU, Apple Metal o CPU ARM.
          </div>
        </div>

        {tooling && !tooling.ready && (
          <div style={{
            padding: '12px 14px', borderRadius: '10px',
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            display: 'flex', flexDirection: 'column', gap: '8px',
          }}>
            <div style={{ fontSize: '0.78rem', color: isLight ? '#92400e' : '#fbbf24', fontWeight: 700 }}>
              <AlertTriangle size={13} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
              Strumento di conversione non ancora installato
            </div>
            <div style={{ fontSize: '0.72rem', color: textMuted, lineHeight: 1.5 }}>
              La conversione usa lo script ufficiale di llama.cpp
              (versione <code>{tooling.converter_version}</code>), che viene scaricato
              una sola volta e poi eseguito in locale. La quantizzazione invece
              gira interamente in-process, senza programmi esterni.
            </div>
            <button
              onClick={installTooling}
              disabled={busy}
              style={{
                alignSelf: 'flex-start', padding: '7px 14px', borderRadius: '8px',
                border: '1px solid rgba(245, 158, 11, 0.5)',
                background: 'rgba(245, 158, 11, 0.15)',
                color: isLight ? '#92400e' : '#fbbf24',
                fontSize: '0.75rem', fontWeight: 800, cursor: busy ? 'wait' : 'pointer',
              }}
            >
              <Download size={12} style={{ verticalAlign: '-2px', marginRight: '5px' }} />
              Scarica lo strumento
            </button>
          </div>
        )}

        {loadError ? (
          <div style={{
            padding: '12px 14px', borderRadius: '10px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            fontSize: '0.78rem', color: '#ef4444',
          }}>
            {loadError}
          </div>
        ) : models.length === 0 ? (
          <div style={{ fontSize: '0.78rem', color: textMuted }}>
            Nessun modello safetensors nella cartella modelli. I GGUF non
            compaiono qui perché sono già nel formato di destinazione.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div>
              <div style={label}>MODELLO DI PARTENZA</div>
              <select style={field} value={selected} onChange={e => setSelected(e.target.value)}>
                {models.map(m => (
                  <option key={m.name} value={m.name}>
                    {m.name} — {m.params_b}B, {m.size_gb} GB
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div style={label}>QUANTIZZAZIONE</div>
              <select style={field} value={quant} onChange={e => setQuant(e.target.value)}>
                {quantTypes.map(q => (
                  <option key={q.id} value={q.id}>{q.label}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {model && (
          <div style={{
            padding: '12px 14px', borderRadius: '10px', background: inputBg,
            border: cardBorder, fontSize: '0.75rem', color: textMuted, lineHeight: 1.6,
          }}>
            <div>
              <strong style={{ color: textPrimary }}>{model.architecture}</strong>
              {' · '}{model.layers} layer
              {model.is_multimodal && ' · multimodale'}
            </div>
            <div>
              {model.size_gb} GB → <strong style={{ color: textPrimary }}>
                ~{estimate ?? '?'} GB
              </strong> in {quant}
              {model.fits_in_vram?.per_quantization && (
                <span style={{
                  marginLeft: '8px', fontWeight: 700,
                  color: model.fits_in_vram.per_quantization[quant]
                    ? (isLight ? '#166534' : '#4ade80') : '#f59e0b',
                }}>
                  {model.fits_in_vram.per_quantization[quant]
                    ? '• entra in VRAM'
                    : `• NON entra in ${model.fits_in_vram.usable_vram_gb} GB di VRAM`}
                </span>
              )}
            </div>
            {model.fits_in_vram?.largest_that_fits
              && !model.fits_in_vram.per_quantization?.[quant] && (
              <div style={{ marginTop: '4px', color: isLight ? '#92400e' : '#fbbf24' }}>
                Con questa scelta la maggior parte dei layer girerebbe dalla RAM,
                circa dieci volte più lentamente. La più fedele che entra in VRAM
                è <strong>{model.fits_in_vram.largest_that_fits}</strong>.
              </div>
            )}
            {quantMeta && <div style={{ marginTop: '4px' }}>{quantMeta.note}</div>}
            {model.compatibility && (
              <div style={{
                marginTop: '6px',
                color: model.compatibility.blocked_by?.length
                  ? '#ef4444'
                  : (isLight ? '#166534' : '#4ade80'),
              }}>
                {model.compatibility.summary}
                {model.compatibility.gguf_architecture && (
                  <span style={{ color: textMuted }}>
                    {' '}(GGUF: <code>{model.compatibility.gguf_architecture}</code>)
                  </span>
                )}
              </div>
            )}
            {model.is_multimodal && (
              <div style={{ marginTop: '6px', color: isLight ? '#92400e' : '#fbbf24' }}>
                I modelli multimodali perdono la parte visiva nella conversione:
                il GGUF conterrà solo il modello di linguaggio.
              </div>
            )}
            {model.already_converted && (
              <div style={{ marginTop: '6px' }}>
                Esiste già una cartella <code>{model.name}-GGUF</code>.
              </div>
            )}
          </div>
        )}

        <button
          onClick={startConversion}
          disabled={busy || !selected || !tooling?.ready || !!activeJob
            || !!model?.compatibility?.blocked_by?.length}
          style={{
            alignSelf: 'flex-start', padding: '9px 18px', borderRadius: '9px',
            border: '1px solid rgba(34,197,94,0.4)',
            background: (busy || !tooling?.ready || !!activeJob)
              ? 'rgba(107,114,128,0.15)' : 'rgba(34,197,94,0.15)',
            color: (busy || !tooling?.ready || !!activeJob) ? textMuted : '#22c55e',
            fontSize: '0.8rem', fontWeight: 800,
            cursor: (busy || !tooling?.ready || !!activeJob) ? 'not-allowed' : 'pointer',
          }}
        >
          <Play size={13} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
          {activeJob ? 'Conversione in corso…' : 'Converti in GGUF'}
        </button>
      </div>

      {jobs.length > 0 && (
        <div style={panel}>
          <div style={{ fontSize: '0.85rem', fontWeight: 800, color: textPrimary }}>
            Conversioni
          </div>
          {jobs.map(job => (
            <div key={job.job_id} style={{
              padding: '12px 14px', borderRadius: '10px',
              background: inputBg, border: cardBorder,
              display: 'flex', flexDirection: 'column', gap: '6px',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: '0.78rem', color: textPrimary, fontWeight: 700,
              }}>
                <span>
                  {job.status === 'completed' && <CheckCircle2 size={13} style={{ verticalAlign: '-2px', marginRight: '5px', color: '#22c55e' }} />}
                  {job.status === 'failed' && <AlertTriangle size={13} style={{ verticalAlign: '-2px', marginRight: '5px', color: '#ef4444' }} />}
                  {['queued', 'converting', 'quantizing'].includes(job.status) && <Loader size={13} className="mh-spin" style={{ verticalAlign: '-2px', marginRight: '5px' }} />}
                  {job.source_model} → {job.quantization}
                </span>
                <span style={{ color: textMuted, fontWeight: 600 }}>
                  {job.elapsed_seconds}s
                </span>
              </div>

              {['converting', 'quantizing'].includes(job.status) && (
                <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)' }}>
                  <div style={{
                    width: `${job.progress}%`, height: '100%', borderRadius: '3px',
                    background: 'linear-gradient(90deg,#00d2ff,#3a7bd5)',
                    transition: 'width 0.4s ease',
                  }} />
                </div>
              )}

              <div style={{ fontSize: '0.72rem', color: job.status === 'failed' ? '#ef4444' : textMuted }}>
                {job.error || job.message}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
