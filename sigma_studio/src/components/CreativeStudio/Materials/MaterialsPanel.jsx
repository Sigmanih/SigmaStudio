import React, { useMemo, useState } from 'react';
import { Layers, Wand2, Image as ImageIcon, Grid3x3, AlertTriangle, PaintBucket } from 'lucide-react';

const MAP_ORDER = ['albedo', 'normal', 'roughness', 'metallic', 'height', 'ao'];

export default function MaterialsPanel({ asset, assets = [], busy, blenderAvailable, onMaterial }) {
  const [prompt, setPrompt] = useState('');
  const [resolution, setResolution] = useState(1024);
  const [meshId, setMeshId] = useState('');

  const materials = useMemo(() => assets.filter(a => a.type === 'material'), [assets]);
  const meshes = useMemo(() => assets.filter(a => a.type === 'mesh' || a.type === 'model_3d'), [assets]);

  const isMaterial = asset?.type === 'material';
  const isImage = asset?.type === 'image' || asset?.type === 'render';

  return (
    <div className="cs-mesh-container">
      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Wand2 size={20} /> Genera materiale PBR</h3>
        <p className="cs-hint">
          L'albedo viene generato dal backend attivo; normal, roughness, height, AO e metallic
          sono derivate dall'albedo per restare coerenti tra loro.
        </p>
        <textarea
          className="cs-textarea"
          rows={2}
          placeholder="es. weathered oak planks, rusted metal, marble..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)} />
        <div className="cs-action-group" style={{ marginTop: '12px' }}>
          <select className="cs-select" value={resolution} onChange={e => setResolution(Number(e.target.value))}>
            {[512, 1024, 2048].map(r => <option key={r} value={r}>{r}px</option>)}
          </select>
          <button className="cs-generate-btn cs-block-btn" disabled={busy || !prompt.trim()}
                  onClick={() => onMaterial('generate_pbr', { prompt, resolution })}>
            Genera set PBR
          </button>
        </div>
      </div>

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><ImageIcon size={20} /> Da immagine</h3>
        {isImage ? (
          <>
            <p className="cs-hint">Deriva un set PBR completo da «{asset.name}».</p>
            <div className="cs-button-grid">
              <button className="cs-tool-btn" disabled={busy}
                      onClick={() => onMaterial('generate_from_image', { asset_id: asset.id, resolution })}>
                <Grid3x3 size={16} /> Estrai PBR
              </button>
              <button className="cs-tool-btn" disabled={busy}
                      onClick={() => onMaterial('make_tileable', { asset_id: asset.id })}>
                Rendi tileable
              </button>
            </div>
          </>
        ) : (
          <p className="cs-hint">Seleziona un'immagine nel vault per estrarne le mappe.</p>
        )}
      </div>

      {isMaterial && (
        <div className="cs-mesh-card">
          <h3 className="cs-mesh-title"><Layers size={20} /> {asset.name}</h3>
          <div className="cs-map-grid">
            {MAP_ORDER.filter(m => asset.file_urls?.[m]).map(map => (
              <figure key={map}>
                <img src={asset.file_urls[map]} alt={map} loading="lazy" />
                <figcaption>{map}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><PaintBucket size={20} /> Applica a una mesh</h3>
        {!blenderAvailable && (
          <div className="cs-banner warn">
            <AlertTriangle size={16} />
            <span>L'applicazione del materiale usa Blender headless: configura <code>backends.blender.path</code>.</span>
          </div>
        )}
        <div className="cs-action-group">
          <select className="cs-select" value={meshId} onChange={e => setMeshId(e.target.value)}>
            <option value="">— scegli la mesh —</option>
            {meshes.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <button
            className="cs-tool-btn"
            disabled={busy || !blenderAvailable || !meshId || !isMaterial}
            title={isMaterial ? '' : 'Seleziona prima un materiale nel vault'}
            onClick={() => onMaterial('apply_to_mesh', { mesh_asset_id: meshId, material_asset_id: asset.id })}
          >
            Applica
          </button>
        </div>
        {materials.length === 0 && <p className="cs-hint">Nessun materiale nel vault: generane uno qui sopra.</p>}
      </div>
    </div>
  );
}
