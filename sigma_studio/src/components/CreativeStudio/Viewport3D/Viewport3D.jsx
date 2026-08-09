import React, { useState } from 'react';
import { Box, Play, Download, AlertTriangle, Loader, Boxes } from 'lucide-react';
import { useThreeViewer } from './useThreeViewer';
import SceneControls from './SceneControls';

export default function Viewport3D({ asset, busy, canGenerate3D, blenderAvailable, onGenerate3D, onRender }) {
  const [wireframe, setWireframe] = useState(false);
  const [environment, setEnvironment] = useState('Studio');

  const modelUrl = asset?.model_url || null;
  const { containerRef, status, error, stats, environments } = useThreeViewer({
    url: modelUrl, wireframe, environment,
  });

  if (!asset) {
    return (
      <div className="cs-canvas-wrapper">
        <Box size={48} style={{ opacity: 0.2 }} />
        <p>Seleziona un asset per la vista 3D</p>
      </div>
    );
  }

  // Un'immagine selezionata è il punto di partenza della ricostruzione 3D.
  if (!modelUrl) {
    return (
      <div className="cs-canvas-wrapper cs-3d-empty">
        <Boxes size={48} style={{ opacity: 0.25 }} />
        <p>«{asset.name}» non contiene geometria 3D</p>
        {asset.type === 'image' ? (
          <>
            <button
              className="cs-generate-btn"
              disabled={busy || !canGenerate3D}
              onClick={() => onGenerate3D('image_to_3d', { asset_id: asset.id })}
            >
              <Box size={18} /> Ricostruisci in 3D da questa immagine
            </button>
            {!canGenerate3D && (
              <p className="cs-hint">
                <AlertTriangle size={13} /> Nessun backend 3D attivo: abilita Stability o fal.ai
                con la relativa API key in Impostazioni → Creative.
              </p>
            )}
          </>
        ) : (
          <p className="cs-hint">Genera o importa un modello 3D per usarlo qui.</p>
        )}
      </div>
    );
  }

  return (
    <div className="cs-3d-container">
      <div ref={containerRef} className="cs-3d-canvas" />

      {status === 'loading' && (
        <div className="cs-3d-loading"><Loader size={18} className="cs-spin" /> Caricamento modello...</div>
      )}
      {status === 'error' && (
        <div className="cs-3d-loading error"><AlertTriangle size={18} /> {error}</div>
      )}

      <div className="cs-3d-overlay">
        <div className="cs-3d-stats">
          <h4 style={{ margin: '0 0 8px', color: 'var(--primary)' }}>{asset.name}</h4>
          {stats ? (
            <div className="cs-stat-grid">
              <span>Vertici:</span><span>{stats.vertices.toLocaleString()}</span>
              <span>Triangoli:</span><span>{stats.triangles.toLocaleString()}</span>
              <span>Mesh:</span><span>{stats.meshes}</span>
              <span>Materiali:</span><span>{stats.materials}</span>
              <span>UV:</span><span>{stats.hasUV ? 'sì' : 'no'}</span>
            </div>
          ) : (
            <p className="cs-hint">Statistiche in lettura dal modello...</p>
          )}
        </div>

        <SceneControls
          environment={environment}
          environments={environments}
          onEnvironmentChange={setEnvironment}
          wireframe={wireframe}
          onWireframeToggle={() => setWireframe(w => !w)}
          extra={(
            <>
              <a className="cs-pill" href={modelUrl} download title="Scarica il modello">
                <Download size={14} /> GLB
              </a>
              <button
                className="cs-pill cs-pill-warn"
                disabled={busy || !blenderAvailable}
                title={blenderAvailable ? 'Render fotorealistico con Blender' : 'Blender non configurato'}
                onClick={() => onRender(asset.id, { engine: 'cycles', width: 1280, height: 720, samples: 96 })}
              >
                <Play size={14} /> Blender Render
              </button>
            </>
          )}
        />
      </div>
    </div>
  );
}
