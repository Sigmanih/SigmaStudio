import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Download, CheckCircle2, X, HardDrive, AlertTriangle, Lock, FolderOpen, Loader
} from 'lucide-react';

const KIND_LABEL = {
  checkpoint: 'Checkpoint', diffusion: 'Diffusion model', text_encoder: 'Text encoder',
  vae: 'VAE', upscaler: 'Upscaler', lora: 'LoRA',
};

const fmtGB = (bytes) => `${(bytes / 1024 ** 3).toFixed(1)} GB`;
const fmtSpeed = (bps) => (bps > 1024 ** 2 ? `${(bps / 1024 ** 2).toFixed(1)} MB/s` : `${(bps / 1024).toFixed(0)} kB/s`);

/** Scarica i pesi nella cartella models/ di ComfyUI, senza uscire da Sigma. */
export default function ModelDownloads({ onInstalled }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const wasDownloading = useRef(false);

  const load = useCallback(() => (
    fetch('/api/creative/downloads')
      .then(r => r.json())
      .then(d => {
        if (!d.success) return setError(d.error);
        setData(d);
        const active = (d.jobs || []).some(j => ['queued', 'downloading'].includes(j.status));
        // Al passaggio da "scaricando" a "fermo" il registro va riletto:
        // i modelli appena scesi diventano selezionabili.
        if (wasDownloading.current && !active) onInstalled?.();
        wasDownloading.current = active;
      })
      .catch(e => setError(e.message))
  ), [onInstalled]);

  useEffect(() => {
    load();
    timer.current = setInterval(load, 1500);
    return () => clearInterval(timer.current);
  }, [load]);

  const start = (assetId) => {
    fetch('/api/creative/downloads/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id: assetId }),
    }).then(r => r.json()).then(d => { if (!d.success) setError(d.error); load(); });
  };

  const cancel = (jobId) => {
    fetch('/api/creative/downloads/cancel', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId }),
    }).then(() => load());
  };

  if (!data) return <p className="cs-hint">Lettura catalogo download...</p>;

  const jobByAsset = Object.fromEntries((data.jobs || [])
    .filter(j => ['queued', 'downloading'].includes(j.status))
    .map(j => [j.asset_id, j]));
  const failed = (data.jobs || []).filter(j => j.status === 'error').slice(0, 3);

  return (
    <div className="cs-downloads">
      <div className="cs-downloads-head">
        <div>
          <h3 className="cs-mesh-title"><Download size={18} /> Scarica modelli</h3>
          <p className="cs-hint">
            <FolderOpen size={12} />
            {data.models_root || 'cartella ComfyUI non trovata — avvia ComfyUI o imposta backends.comfyui.models_dir'}
          </p>
        </div>
        <span className="cs-hint"><HardDrive size={12} /> {data.disk_free_gb} GB liberi</span>
      </div>

      {error && <div className="cs-banner warn"><AlertTriangle size={16} /><span>{error}</span></div>}
      {failed.map(j => (
        <div key={j.job_id} className="cs-banner warn">
          <AlertTriangle size={16} /><span><strong>{j.label}</strong>: {j.error}</span>
        </div>
      ))}

      <div className="cs-download-list">
        {data.catalog.map(item => {
          const job = jobByAsset[item.id];
          const blocked = !data.models_root;
          return (
            <div key={item.id} className={`cs-download-row ${item.installed ? 'installed' : ''}`}>
              <div className="cs-download-info">
                <div className="cs-download-title">
                  <span>{item.label}</span>
                  <span className="cs-download-kind">{KIND_LABEL[item.kind] || item.kind}</span>
                  {item.requires_token && (
                    <span className="cs-download-kind gated" title="Repository gated: serve un token Hugging Face">
                      <Lock size={10} /> gated
                    </span>
                  )}
                </div>
                {item.notes && <p className="cs-hint">{item.notes}</p>}
                <p className="cs-download-meta">
                  {item.size_gb} GB · {item.folder}/{item.filename}
                  {item.license ? ` · ${item.license}` : ''}
                </p>
              </div>

              <div className="cs-download-action">
                {item.installed ? (
                  <span className="cs-download-done"><CheckCircle2 size={14} /> installato</span>
                ) : job ? (
                  <div className="cs-download-progress">
                    <div className="cs-progress-bar">
                      <div className="cs-progress-fill" style={{ width: `${job.progress}%` }} />
                    </div>
                    <span>
                      {job.progress}% · {fmtGB(job.downloaded)}
                      {job.speed_bps ? ` · ${fmtSpeed(job.speed_bps)}` : ''}
                      {job.eta_s ? ` · ${Math.round(job.eta_s / 60)} min` : ''}
                    </span>
                    <button className="cs-copy-btn" onClick={() => cancel(job.job_id)}><X size={11} /> annulla</button>
                  </div>
                ) : (
                  <button
                    className="cs-tool-btn"
                    disabled={blocked || (item.requires_token && !data.has_token)}
                    title={item.requires_token && !data.has_token
                      ? 'Imposta hf_token in config per i repository gated'
                      : `Scarica in ${item.folder}/`}
                    onClick={() => start(item.id)}
                  >
                    <Download size={14} /> Scarica
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {(data.jobs || []).some(j => j.status === 'downloading') && (
        <p className="cs-hint"><Loader size={12} className="cs-spin" /> I download proseguono anche
          cambiando scheda; il registro si aggiorna da solo al termine.</p>
      )}
    </div>
  );
}
