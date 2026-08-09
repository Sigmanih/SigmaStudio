import React from 'react';
import { Trash2, Settings2 } from 'lucide-react';

const ENUMS = {
  operation: ['inpaint', 'outpaint', 'replace_object', 'style_transfer'],
  direction: ['all', 'top', 'bottom', 'left', 'right'],
  light_direction: ['front', 'left', 'right', 'top', 'bottom'],
  method: ['smart_project', 'lightmap', 'angle_based'],
  engine: ['cycles', 'eevee'],
  format: ['keep', 'glb', 'fbx', 'obj', 'stl'],
};

/** Pannello parametri del nodo selezionato: i campi derivano dal catalogo server. */
export default function NodeInspector({ node, def, assets = [], onChange, onDelete }) {
  const params = node.params || {};

  const set = (key, value) => onChange({ ...params, [key]: value });

  const renderField = (key, value) => {
    if (key === 'asset_id') {
      return (
        <select value={value || ''} onChange={e => set(key, e.target.value)}>
          <option value="">— scegli un asset —</option>
          {assets.map(a => (
            <option key={a.id} value={a.id}>{a.name} ({a.type})</option>
          ))}
        </select>
      );
    }
    if (ENUMS[key]) {
      return (
        <select value={value ?? ENUMS[key][0]} onChange={e => set(key, e.target.value)}>
          {ENUMS[key].map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      );
    }
    if (key === 'prompt' || key === 'negative_prompt' || key === 'style_prompt') {
      return (
        <textarea
          rows={key === 'prompt' ? 3 : 2}
          value={value ?? ''}
          placeholder={key === 'negative_prompt' ? 'cosa evitare...' : 'descrivi...'}
          onChange={e => set(key, e.target.value)}
        />
      );
    }
    if (typeof value === 'boolean') {
      return <input type="checkbox" checked={value} onChange={e => set(key, e.target.checked)} />;
    }
    if (typeof value === 'number') {
      return (
        <input
          type="number"
          value={value}
          step={Number.isInteger(value) ? 1 : 0.1}
          onChange={e => set(key, e.target.value === '' ? '' : Number(e.target.value))}
        />
      );
    }
    return <input type="text" value={value ?? ''} onChange={e => set(key, e.target.value)} />;
  };

  const keys = Object.keys({ ...(def?.params || {}), ...params });

  return (
    <div className="cs-node-inspector" onPointerDown={e => e.stopPropagation()}>
      <div className="cs-inspector-head">
        <span style={{ color: def?.color }}><Settings2 size={14} /> {def?.label || node.type}</span>
        <button onClick={onDelete} title="Elimina nodo (Canc)"><Trash2 size={14} /></button>
      </div>

      {keys.length === 0 && <p className="cs-palette-hint">Questo nodo non ha parametri.</p>}

      <div className="cs-inspector-fields">
        {keys.map(key => (
          <label key={key} className="cs-inspector-field">
            <span>{key.replace(/_/g, ' ')}</span>
            {renderField(key, params[key] ?? def?.params?.[key])}
          </label>
        ))}
      </div>

      <div className="cs-inspector-ports">
        <span>in: {(def?.inputs || []).join(', ') || '—'}</span>
        <span>out: {(def?.outputs || []).join(', ') || '—'}</span>
      </div>
    </div>
  );
}
