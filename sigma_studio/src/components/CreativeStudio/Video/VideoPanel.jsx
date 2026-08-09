import React, { useState } from 'react';
import { Film, Image as ImageIcon, AlertTriangle, Play } from 'lucide-react';

export default function VideoPanel({ asset, assets = [], busy, canVideo, onVideo }) {
  const [prompt, setPrompt] = useState('');
  const [frames, setFrames] = useState(97);
  const [fps, setFps] = useState(24);

  const videos = assets.filter(a => a.type === 'video');
  const sourceImage = (asset?.type === 'image' || asset?.type === 'render') ? asset : null;

  return (
    <div className="cs-mesh-container">
      {!canVideo && (
        <div className="cs-banner warn">
          <AlertTriangle size={16} />
          <span>
            Nessun backend video attivo. Servono ComfyUI con il workflow Wan/LTX esportato
            in <code>data/creative/workflows/</code>, oppure una API key fal.ai.
          </span>
        </div>
      )}

      <div className="cs-mesh-card">
        <h3 className="cs-mesh-title"><Film size={20} /> Genera video</h3>
        <textarea
          className="cs-textarea"
          rows={2}
          placeholder="Descrivi il movimento: 'lenta orbita attorno al prodotto, luce da destra'"
          value={prompt}
          onChange={e => setPrompt(e.target.value)} />

        <div className="cs-inline-params" style={{ marginBottom: '12px' }}>
          <label>Frame
            <input type="number" min="17" max="257" step="8" value={frames} onChange={e => setFrames(Number(e.target.value))} />
          </label>
          <label>FPS
            <input type="number" min="8" max="60" value={fps} onChange={e => setFps(Number(e.target.value))} />
          </label>
        </div>

        <div className="cs-button-grid">
          <button className="cs-tool-btn" disabled={busy || !canVideo || !prompt.trim()}
                  onClick={() => onVideo('text_to_video', { prompt, num_frames: frames, fps })}>
            <Play size={16} /> Text → Video
          </button>
          <button className="cs-tool-btn"
                  disabled={busy || !canVideo || !sourceImage}
                  title={sourceImage ? '' : 'Seleziona un\'immagine nel vault'}
                  onClick={() => onVideo('image_to_video', {
                    asset_id: sourceImage.id, prompt, num_frames: frames, fps,
                  })}>
            <ImageIcon size={16} /> Image → Video
          </button>
        </div>
        {sourceImage && <p className="cs-hint">Sorgente: «{sourceImage.name}»</p>}
      </div>

      {asset?.video_url && (
        <div className="cs-mesh-card">
          <h3 className="cs-mesh-title"><Film size={20} /> {asset.name}</h3>
          <video src={asset.video_url} controls loop className="cs-video-player" />
          <div className="cs-action-group" style={{ marginTop: '10px' }}>
            <a className="cs-tool-btn" href={asset.video_url} download>Scarica</a>
          </div>
        </div>
      )}

      {videos.length > 0 && (
        <div className="cs-mesh-card">
          <h3 className="cs-mesh-title">Video nel vault ({videos.length})</h3>
          <div className="cs-map-grid">
            {videos.map(v => (
              <figure key={v.id}>
                <video src={v.video_url} muted preload="metadata" />
                <figcaption>{v.name}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
