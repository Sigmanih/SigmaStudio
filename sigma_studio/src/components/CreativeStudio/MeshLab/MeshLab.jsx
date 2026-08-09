import React, { useEffect, useState } from 'react';
import { Hexagon, Scissors, Eraser, Move, AlertTriangle, Waves, Download } from 'lucide-react';

const UNWRAP_METHODS = [
  { id: 'smart_project', label: 'Smart Project' },
  { id: 'angle_based', label: 'Angle Based' },
  { id: 'lightmap', label: 'Lightmap Pack' },
];

const EXPORT_FORMATS = ['glb', 'fbx', 'obj', 'stl'];

export default function MeshLab({ asset, busy, blenderAvailable, onMeshOp }) {
  const [ratio, setRatio] = useState(50);
  const [unwrapMethod, setUnwrapMethod] = useState('smart_project');
  const [iterations, setIterations] = useState(2);
  const [voxelSize, setVoxelSize] = useState(0.05);
  const [format, setFormat] = useState('glb');
  const [info, setInfo] = useState(null);

  const isMesh = asset && (asset.type === 'mesh' || asset.type === 'model_3d');

  useEffect(() => {
    setInfo(null);
    if (!isMesh) return;
    fetch(`/api/creative/mesh/info?id=${encodeURIComponent(asset.id)}`)
      .then(r => r.json())
      .then(data => { if (data.success) setInfo(data.info); })
      .catch(() => {});
  }, [asset, isMesh]);

  if (!isMesh) {
    return (
      <div className="cs-canvas-wrapper">
        <Hexagon size={48} style={{ opacity: 0.2 }} />
        <p>Seleziona una mesh per il Mesh Lab</p>
      </div>
    );
  }

  const disabled = busy || !blenderAvailable;
  const run = (task, params) => onMeshOp(task, asset.id, params);

  return (
    <div className="cs-mesh-container">
      {!blenderAvailable && (
        <div className="cs-banner warn">
          <AlertTriangle size={16} />
          <span>
            Blender non è configurato: le operazioni mesh sono eseguite da Blender headless.
            Imposta <code>backends.blender.path</code> in Impostazioni → Creative.
          </span>
        </div>
      )}

      {info && (
        <div className="cs-mesh-card">
          <h3 className="cs-mesh-title"><Hexagon size={20} /> Geometria</h3>
          <div className="cs-stat-grid">
            <span>Vertici:</span><span>{(info.vertices ?? 0).toLocaleString()}</span>
            <span>Facce:</span><span>{(info.faces ?? 0).toLocaleString()}</span>
            <span>Oggetti:</span><span>{info.objects ?? '—'}</span>
            <span>Materiali:</span><span>{info.materials ?? '—'}</span>
            <span>UV:</span><span>{info.has_uv ? 'presenti' : 'assenti'}</span>
            <span>Fonte:</span><span>{info.source || info.status}</span>
          </div>
          {info.message && <p className="cs-hint">{info.message}</p>}
        </div>
      )}

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Scissors size={20} /> Decimazione</h3>
        <p className="cs-hint">Riduce i poligoni preservando la silhouette.</p>
        <div className="cs-slider-row">
          <span>Poligoni target</span>
          <span style={{ color: 'var(--primary)' }}>{ratio}%</span>
        </div>
        <input type="range" min="1" max="100" value={ratio} onChange={e => setRatio(Number(e.target.value))}
               style={{ width: '100%', accentColor: 'var(--success)', marginBottom: '16px' }} />
        <button className="cs-generate-btn cs-block-btn success" disabled={disabled}
                onClick={() => run('decimate', { ratio: ratio / 100 })}>
          Applica decimazione
        </button>
      </div>

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Eraser size={20} /> Cleanup</h3>
        <div className="cs-button-grid">
          <button className="cs-tool-btn" disabled={disabled} onClick={() => run('cleanup', { merge_distance: 0.001 })}>
            <Move size={16} /> Merge by distance
          </button>
          <button className="cs-tool-btn" disabled={disabled} onClick={() => run('fix_normals')}>
            Ricalcola normali
          </button>
          <button className="cs-tool-btn" disabled={disabled} onClick={() => run('smooth', { iterations })}>
            <Waves size={16} /> Smooth ×{iterations}
          </button>
          <button className="cs-tool-btn" disabled={disabled} onClick={() => run('remesh', { voxel_size: voxelSize, mode: 'VOXEL' })}>
            Remesh voxel
          </button>
        </div>
        <div className="cs-inline-params">
          <label>Smooth iterations
            <input type="number" min="1" max="20" value={iterations} onChange={e => setIterations(Number(e.target.value))} />
          </label>
          <label>Voxel size
            <input type="number" min="0.005" max="1" step="0.005" value={voxelSize} onChange={e => setVoxelSize(Number(e.target.value))} />
          </label>
        </div>
      </div>

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Hexagon size={20} /> UV Unwrap</h3>
        <div className="cs-radio-row">
          {UNWRAP_METHODS.map(m => (
            <label key={m.id}>
              <input type="radio" checked={unwrapMethod === m.id} onChange={() => setUnwrapMethod(m.id)} /> {m.label}
            </label>
          ))}
        </div>
        <button className="cs-generate-btn cs-block-btn" disabled={disabled}
                onClick={() => run('uv_unwrap', { method: unwrapMethod })}>
          Genera UV map
        </button>
      </div>

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Download size={20} /> Export</h3>
        <div className="cs-action-group">
          <select className="cs-select" value={format} onChange={e => setFormat(e.target.value)}>
            {EXPORT_FORMATS.map(f => <option key={f} value={f}>{f.toUpperCase()}</option>)}
          </select>
          <button className="cs-tool-btn" disabled={disabled} onClick={() => run('export', { format })}>
            Converti
          </button>
          {asset.model_url && (
            <a className="cs-tool-btn" href={asset.model_url} download>Scarica originale</a>
          )}
        </div>
      </div>
    </div>
  );
}
