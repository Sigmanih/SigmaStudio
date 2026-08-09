import React, { useState } from 'react';
import { ZoomIn, ZoomOut, Maximize, Download } from 'lucide-react';

export default function ImageViewer({ asset }) {
  const [scale, setScale] = useState(1);

  if (!asset) return null;

  return (
    <div className="cs-viewer">
      <div className="cs-viewer-toolbar">
        <button className="cs-viewer-btn" onClick={() => setScale(s => s * 0.8)} title="Zoom Out">
          <ZoomOut size={18} />
        </button>
        <div style={{ color: 'var(--text)', fontSize: '0.8rem', display: 'flex', alignItems: 'center', padding: '0 8px' }}>
          {Math.round(scale * 100)}%
        </div>
        <button className="cs-viewer-btn" onClick={() => setScale(s => s * 1.2)} title="Zoom In">
          <ZoomIn size={18} />
        </button>
        <div style={{ width: '1px', background: 'var(--border)', margin: '0 8px' }}></div>
        <button className="cs-viewer-btn" onClick={() => setScale(1)} title="Fit to Screen">
          <Maximize size={18} />
        </button>
        <a href={asset.url} download={`${asset.name || 'generated'}.png`} className="cs-viewer-btn" title="Download">
          <Download size={18} />
        </a>
      </div>

      <div className="cs-viewer-canvas">
        {asset.url && (
          <img 
            src={asset.url} 
            alt={asset.name} 
            style={{ transform: `scale(${scale})`, transition: 'transform 0.2s ease' }} 
          />
        )}
      </div>
    </div>
  );
}
