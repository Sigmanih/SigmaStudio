import React, { useEffect, useMemo, useState } from 'react';
import { Cpu, CheckCircle2, XCircle, AlertTriangle, HardDrive, Zap, Star, Copy } from 'lucide-react';
import ModelDownloads from './ModelDownloads';
import ModelBrowser from './ModelBrowser';
import ModelInventory from './ModelInventory';
import WorkflowPanel from './WorkflowPanel';

const TASK_LABELS = {
  text_to_image: 'Text→Image', img_to_img: 'Image→Image', inpaint: 'Inpaint', outpaint: 'Outpaint',
  instruct_edit: 'Instruct Edit', upscale: 'Upscale', restore: 'Restauro',
  vision_describe: 'Vision', vision_qa: 'Vision QA', quality_score: 'Quality', ocr: 'OCR',
  segment: 'Segmentazione', remove_background: 'Scontorno',
  image_to_3d: 'Image→3D', multiview_to_3d: 'Multi-view→3D', texture_3d: 'Texture 3D',
  texture_pbr: 'PBR', text_to_video: 'Text→Video', image_to_video: 'Image→Video',
};

const GROUPS = [
  { id: 'image', label: 'Generazione immagini', tasks: ['text_to_image', 'img_to_img'] },
  { id: 'edit', label: 'Editing', tasks: ['instruct_edit', 'inpaint', 'outpaint'] },
  { id: 'upscale', label: 'Upscaling', tasks: ['upscale', 'restore'] },
  { id: 'vision', label: 'Vision', tasks: ['vision_describe', 'vision_qa', 'quality_score', 'ocr'] },
  { id: 'segment', label: 'Segmentazione', tasks: ['segment', 'remove_background'] },
  { id: '3d', label: '3D', tasks: ['image_to_3d', 'multiview_to_3d', 'texture_3d'] },
  { id: 'materials', label: 'Materiali', tasks: ['texture_pbr'] },
  { id: 'video', label: 'Video', tasks: ['text_to_video', 'image_to_video'] },
];

function Meter({ value, icon: Icon, title }) {
  return (
    <span className="cs-meter" title={`${title}: ${value}/5`}>
      <Icon size={11} />
      {[1, 2, 3, 4, 5].map(i => <i key={i} className={i <= value ? 'on' : ''} />)}
    </span>
  );
}

export default function ModelsPanel({ models = [], inventory = null, onRefresh }) {
  const [meta, setMeta] = useState(null);
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [enabling, setEnabling] = useState(false);

  useEffect(() => {
    fetch('/api/creative/models').then(r => r.json())
      .then(d => { if (d.success) setMeta(d); })
      .catch(() => {});
  }, [models]);

  const grouped = useMemo(() => GROUPS.map(g => ({
    ...g,
    models: models
      .filter(m => m.tasks.some(t => g.tasks.includes(t)))
      .filter(m => !onlyAvailable || m.available)
      .sort((a, b) => (b.available - a.available) || (b.quality - a.quality)),
  })).filter(g => g.models.length), [models, onlyAvailable]);

  /** ComfyUI è in esecuzione ma spento in config: un click lo collega. */
  const enableComfy = () => {
    setEnabling(true);
    fetch('/api/creative/backends/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backends: { comfyui: { enabled: true, url: inventory.url } } }),
    })
      .then(() => onRefresh?.())
      .finally(() => setEnabling(false));
  };

  if (!models.length) {
    return <div className="cs-canvas-wrapper"><p>Caricamento registro modelli...</p></div>;
  }

  const data = meta || { models, available_backends: [], workflows: {} };

  return (
    <div className="cs-models-container">
      <div className="cs-models-header">
        <div>
          <h2><Cpu size={20} /> Registro modelli</h2>
          <p className="cs-hint">
            Sigma sceglie automaticamente il modello per ogni task in base a backend attivi,
            capacità VRAM e priorità. Qui vedi cosa è realmente eseguibile su questa macchina.
          </p>
        </div>
        <div className="cs-models-stats">
          <span><HardDrive size={13} /> {data.vram_free_gb ? `${data.vram_free_gb} GB VRAM` : 'VRAM n/d'}</span>
          <span>{(data.available_backends || []).join(' · ') || 'nessun backend'}</span>
          <label className="cs-check">
            <input type="checkbox" checked={onlyAvailable} onChange={e => setOnlyAvailable(e.target.checked)} />
            solo disponibili
          </label>
          <button className="cs-copy-btn" onClick={() => onRefresh?.()}>Aggiorna</button>
        </div>
      </div>

      {inventory?.reachable && !inventory.enabled && (
        <div className="cs-banner ok">
          <CheckCircle2 size={16} />
          <span>ComfyUI è in esecuzione su <code>{inventory.url}</code> ma non è collegato a Sigma.</span>
          <button className="cs-tool-btn" disabled={enabling} onClick={enableComfy}>
            {enabling ? 'Collegamento...' : 'Collega ComfyUI'}
          </button>
        </div>
      )}

      <div className="cs-mesh-card">
        <ModelInventory onRefresh={onRefresh} />
      </div>

      <div className="cs-mesh-card">
        <WorkflowPanel onChanged={onRefresh} />
      </div>

      {grouped.map(group => (
        <section key={group.id} className="cs-model-group">
          <h3>{group.label}</h3>
          <div className="cs-model-grid">
            {group.models.map(m => (
              <article key={m.id} className={`cs-model-card ${m.available ? '' : 'off'}`}>
                <header>
                  <span className="cs-model-name">{m.label}</span>
                  {m.available
                    ? <CheckCircle2 size={14} className="ok" />
                    : <XCircle size={14} className="off" />}
                </header>

                <div className="cs-model-meters">
                  <Meter value={m.quality} icon={Star} title="Qualità" />
                  <Meter value={m.speed} icon={Zap} title="Velocità" />
                  {m.vram_gb > 0 && (
                    <span className={`cs-vram ${m.fits_vram ? '' : 'over'}`} title="VRAM consigliata">
                      <HardDrive size={11} /> {m.vram_gb} GB
                    </span>
                  )}
                </div>

                <div className="cs-model-tasks">
                  {m.tasks.map(t => <span key={t}>{TASK_LABELS[t] || t}</span>)}
                </div>

                {m.strengths.length > 0 && (
                  <p className="cs-model-strengths">{m.strengths.map(s => s.replace(/_/g, ' ')).join(' · ')}</p>
                )}
                {m.notes && <p className="cs-model-notes">{m.notes}</p>}

                <footer>
                  <span>{m.available_via.length ? `via ${m.available_via.join(', ')}` : `richiede ${m.backends.join(' o ')}`}</span>
                  {m.workflow && (
                    <button
                      className="cs-copy-btn"
                      title="Copia il nome del file workflow da creare"
                      onClick={() => navigator.clipboard?.writeText(`${m.workflow}.json`)}
                    >
                      <Copy size={11} /> {m.workflow}
                    </button>
                  )}
                </footer>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
