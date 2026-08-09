import React from 'react';
import { Box } from 'lucide-react';

/** Barra di controllo del viewport 3D: ambiente luci, wireframe e azioni. */
export default function SceneControls({
  environment, environments = [], onEnvironmentChange,
  wireframe, onWireframeToggle, extra,
}) {
  return (
    <div className="cs-3d-controls">
      <div className="cs-3d-control-group">
        {environments.map(env => (
          <button
            key={env}
            className={`cs-pill ${environment === env ? 'active' : ''}`}
            onClick={() => onEnvironmentChange(env)}
          >
            {env}
          </button>
        ))}
      </div>
      <button className={`cs-pill ${wireframe ? 'active' : ''}`} onClick={onWireframeToggle}>
        <Box size={14} /> Wireframe
      </button>
      {extra}
    </div>
  );
}
