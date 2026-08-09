import React, { useCallback, useEffect, useState } from 'react';
import {
  Workflow, CheckCircle2, AlertTriangle, FolderOpen, Trash2, Upload, X, Package
} from 'lucide-react';

const CAPABILITY_LABEL = {
  text_to_image: 'Text → Image', img_to_img: 'Image → Image', inpaint: 'Inpaint',
  outpaint: 'Outpaint', instruct_edit: 'Instruct Edit', upscale: 'Upscale',
  segment: 'Segmentazione', image_to_3d: 'Image → 3D',
  image_to_video: 'Image → Video', text_to_video: 'Text → Video',
};

const EMPTY_FORM = { id: '', name: '', capability: 'text_to_image', description: '', workflow: '' };

/**
 * Registro dei workflow: dati su disco, non codice.
 *
 * Sigma sa che un workflow genera immagini e richiede SDXL; com'è costruito il
 * grafo non la riguarda. Qui si vede quali esistono, quali sono pronti e cosa
 * manca a quelli che non lo sono.
 */
export default function WorkflowPanel({ onChanged }) {
  const [data, setData] = useState(null);
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState(null);

  const load = useCallback(() => (
    fetch('/api/creative/workflows').then(r => r.json())
      .then(d => (d.success ? setData(d) : setNotice({ type: 'error', text: d.error })))
      .catch(e => setNotice({ type: 'error', text: e.message }))
  ), []);

  useEffect(() => { load(); }, [load]);

  const save = () => {
    let graph;
    try {
      graph = JSON.parse(form.workflow);
    } catch (e) {
      return setNotice({ type: 'error', text: `JSON non valido: ${e.message}` });
    }
    fetch('/api/creative/workflows/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ manifest: form, workflow: graph }),
    })
      .then(r => r.json())
      .then(d => {
        if (!d.success) return setNotice({ type: 'error', text: d.error });
        setNotice({ type: 'ok', text: `Workflow '${d.workflow.id}' registrato` });
        setForm(null);
        load();
        onChanged?.();
      });
  };

  const remove = (id) => {
    fetch('/api/creative/workflows/delete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    })
      .then(r => r.json())
      .then(d => {
        setNotice(d.success ? { type: 'ok', text: `Rimosso '${id}'` } : { type: 'error', text: d.error });
        load();
        onChanged?.();
      });
  };

  if (!data) return <p className="cs-hint">Lettura registro workflow...</p>;

  const ready = data.workflows.filter(w => w.ready).length;

  return (
    <div className="cs-workflows">
      <div className="cs-downloads-head">
        <div>
          <h3 className="cs-mesh-title"><Workflow size={18} /> Registro workflow</h3>
          <p className="cs-hint">
            <FolderOpen size={12} /> {data.directory} · {ready}/{data.workflows.length} pronti
          </p>
        </div>
        <button className="cs-tool-btn" onClick={() => setForm(form ? null : EMPTY_FORM)}>
          {form ? <><X size={14} /> Annulla</> : <><Upload size={14} /> Importa workflow</>}
        </button>
      </div>

      {notice && (
        <div className={`cs-banner ${notice.type === 'ok' ? 'ok' : 'warn'}`}>
          {notice.type === 'ok' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          <span>{notice.text}</span>
          <button className="cs-copy-btn" onClick={() => setNotice(null)}><X size={11} /></button>
        </div>
      )}

      {form && (
        <div className="cs-wf-form">
          <p className="cs-hint">
            Esporta il workflow da ComfyUI con <strong>Save (API format)</strong>, sostituisci i valori
            variabili con i placeholder <code>{'{{prompt}}'}</code>, <code>{'{{width}}'}</code>,{' '}
            <code>{'{{seed}}'}</code>, <code>{'{{input_image}}'}</code> e incollalo qui.
          </p>
          <div className="cs-wf-fields">
            <label className="cs-field">
              <span>id</span>
              <input className="cs-num-input" style={{ width: '100%' }} value={form.id}
                     placeholder="es. flux_kontext"
                     onChange={e => setForm({ ...form, id: e.target.value })} />
            </label>
            <label className="cs-field">
              <span>nome</span>
              <input className="cs-num-input" style={{ width: '100%' }} value={form.name}
                     onChange={e => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="cs-field">
              <span>capability</span>
              <select className="cs-select" value={form.capability}
                      onChange={e => setForm({ ...form, capability: e.target.value })}>
                {Object.entries(CAPABILITY_LABEL).map(([id, label]) =>
                  <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
          </div>
          <textarea
            className="cs-textarea" rows={7} placeholder='{ "3": { "class_type": "KSampler", ... } }'
            value={form.workflow}
            onChange={e => setForm({ ...form, workflow: e.target.value })} />
          <button className="cs-tool-btn" onClick={save} disabled={!form.id || !form.workflow}>
            <Package size={14} /> Registra
          </button>
        </div>
      )}

      <div className="cs-wf-list">
        {data.workflows.map(w => (
          <div key={w.id} className={`cs-wf-row ${w.ready ? '' : 'blocked'}`}>
            <div className="cs-wf-main">
              <span className="cs-wf-name">{w.name}</span>
              <span className="cs-wf-cap">{CAPABILITY_LABEL[w.capability] || w.capability}</span>
              <span className={`cs-wf-src ${w.source}`}>{w.source === 'builtin' ? 'Sigma' : 'tuo'}</span>
            </div>
            <div className="cs-wf-detail">
              <span className="cs-hint">
                {w.node_count} nodi · {w.placeholders.length} parametri
                {w.requirements?.checkpoint ? ` · richiede ${w.requirements.checkpoint}` : ''}
                {w.requirements?.vram_gb ? ` · ${w.requirements.vram_gb} GB VRAM` : ''}
              </span>
              {w.ready ? (
                <span className="skill-status ok"><CheckCircle2 size={12} /> pronto</span>
              ) : (
                <span className="skill-status blocked">
                  <AlertTriangle size={12} /> manca {w.missing.join(', ')}
                </span>
              )}
              {w.notes?.map(n => (
                <span key={n} className="skill-status degraded"><AlertTriangle size={12} /> {n}</span>
              ))}
              {w.source === 'user' && (
                <button className="cs-copy-btn" onClick={() => remove(w.id)}>
                  <Trash2 size={11} /> rimuovi
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
