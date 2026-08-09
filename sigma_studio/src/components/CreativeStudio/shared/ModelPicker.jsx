import React from 'react';
import { Cpu, AlertTriangle, HardDrive } from 'lucide-react';

/**
 * Selettore esplicito di modello + checkpoint.
 *
 * "Auto" lascia decidere il router di Sigma; qualsiasi altra scelta è vincolante
 * e viaggia nei params come `model_id` (registro) o `ckpt` (file su disco).
 */
export default function ModelPicker({
  task = 'text_to_image',
  models = [],
  inventory,
  value = {},              // { model_id, ckpt }
  onChange,
  compact = false,
}) {
  const candidates = models.filter(m => m.tasks.includes(task));
  const selected = candidates.find(m => m.id === value.model_id);

  const checkpointOptions = [
    ...(inventory?.checkpoints || []).map(c => ({ value: c, group: 'Checkpoint' })),
    ...(inventory?.unets || []).map(c => ({ value: c, group: 'UNET / diffusion' })),
  ];

  const set = (patch) => onChange({ ...value, ...patch });

  return (
    <div className="cs-model-picker">
      <span className="cs-sublabel">
        <Cpu size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Modello
      </span>
      <select className="cs-select" value={value.model_id || ''} onChange={e => set({ model_id: e.target.value })}>
        <option value="">Auto — il router sceglie in base a VRAM e priorità</option>
        {candidates.map(m => (
          <option key={m.id} value={m.id} disabled={!m.available}>
            {m.label}
            {m.vram_gb ? ` · ${m.vram_gb} GB` : ''}
            {m.available ? '' : ' (non disponibile)'}
          </option>
        ))}
      </select>

      {selected && !compact && (
        <p className="cs-hint">
          {selected.strengths.slice(0, 4).map(s => s.replace(/_/g, ' ')).join(' · ')}
          {selected.vram_gb > 0 && !selected.fits_vram && (
            <span className="cs-warn-inline">
              <AlertTriangle size={11} /> richiede {selected.vram_gb} GB
            </span>
          )}
        </p>
      )}
      {selected && !selected.available && (
        <p className="cs-hint" style={{ color: '#ffb86c' }}>
          <AlertTriangle size={12} />
          {selected.workflow_missing
            ? `Serve il workflow ComfyUI ${selected.workflow}.json in data/creative/workflows/`
            : `Richiede uno di questi backend: ${selected.backends.join(', ')}`}
        </p>
      )}

      {checkpointOptions.length > 0 && (
        <>
          <span className="cs-sublabel" style={{ marginTop: '10px' }}>
            <HardDrive size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
            Checkpoint installato
          </span>
          <select className="cs-select" value={value.ckpt || ''} onChange={e => set({ ckpt: e.target.value })}>
            <option value="">Default del modello</option>
            {['Checkpoint', 'UNET / diffusion'].map(group => {
              const items = checkpointOptions.filter(o => o.group === group);
              if (!items.length) return null;
              return (
                <optgroup key={group} label={group}>
                  {items.map(o => <option key={o.value} value={o.value}>{o.value}</option>)}
                </optgroup>
              );
            })}
          </select>
        </>
      )}

      {inventory?.reachable && checkpointOptions.length === 0 && (
        <p className="cs-hint" style={{ color: '#ffb86c' }}>
          <AlertTriangle size={12} /> ComfyUI è raggiungibile ma non ha checkpoint immagine
          installati: scaricane uno (es. SDXL o FLUX) nella cartella <code>models/checkpoints</code>.
        </p>
      )}
    </div>
  );
}
