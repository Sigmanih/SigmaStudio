import React, { useEffect, useState } from 'react';
import {
  Box, Sparkles, Layers, Download, GitMerge, Clock, Trash2, Play, Scissors, History,
  Eye, Film, Gauge
} from 'lucide-react';

/** Ricostruisce l'albero di provenienza come lista indentata. */
function LineageTree({ node, depth = 0, onSelect }) {
  if (!node) return null;
  return (
    <>
      <div
        className="cs-lineage-row"
        style={{ paddingLeft: `${depth * 12}px` }}
        onClick={() => depth > 0 && onSelect?.(node.asset_id)}
        title={depth > 0 ? 'Apri questo asset' : undefined}
      >
        <GitMerge size={13} color={depth === 0 ? 'var(--primary)' : 'var(--text-dim)'} />
        <span className={depth === 0 ? 'current' : ''}>{node.name || node.asset_id?.slice(0, 8)}</span>
        {node.operation && <em>{node.operation}</em>}
      </div>
      {(node.parents || []).map(p => (
        <LineageTree key={p.asset_id} node={p} depth={depth + 1} onSelect={onSelect} />
      ))}
    </>
  );
}

export default function PropertiesPanel({
  asset, busy, capabilities = {},
  onUpscale, onEdit, onGenerate3D, onMaterial, onRender, onVideo, onVision, onDelete, onSelectAsset,
}) {
  const [lineage, setLineage] = useState(null);
  const [versions, setVersions] = useState([]);
  const [vision, setVision] = useState(null);

  useEffect(() => {
    setLineage(null);
    setVersions([]);
    setVision(null);
    if (!asset?.id) return;
    const id = encodeURIComponent(asset.id);
    fetch(`/api/creative/assets/lineage?id=${id}`)
      .then(r => r.json()).then(d => { if (d.success) setLineage(d.lineage); }).catch(() => {});
    fetch(`/api/creative/assets/versions?id=${id}`)
      .then(r => r.json()).then(d => { if (d.success) setVersions(d.versions || []); }).catch(() => {});
  }, [asset?.id]);

  if (busy) {
    return (
      <div className="cs-inspector-busy">
        <div className="cs-spinner" />
        <h3>{busy.label}</h3>
        <p>{busy.message}</p>
      </div>
    );
  }

  if (!asset) {
    return <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-dim)' }}><p>Nessun asset selezionato.</p></div>;
  }

  const isImage = asset.type === 'image' || asset.type === 'render';
  const is3D = asset.type === 'mesh' || asset.type === 'model_3d';
  const can3D = (capabilities.image_to_3d || []).length > 0;
  const canRender = (capabilities.render || []).length > 0;
  const canVision = (capabilities.vision_describe || []).length > 0;
  const canVideo = (capabilities.image_to_video || []).length > 0;
  const downloadUrl = asset.model_url || asset.video_url || asset.file_urls?.image || asset.url;
  const score = asset.quality_score;

  const runVision = (task, params = {}) => {
    setVision({ pending: true });
    onVision?.(task, { asset_id: asset.id, ...params })
      .then(result => setVision(result))
      .catch(err => setVision({ error: err.message }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="cs-panel-header"><span>Inspector</span></div>

      <div className="cs-panel-content">
        {asset.url
          ? <img src={asset.url} alt={asset.name} className="cs-inspector-preview" />
          : <div className="cs-inspector-preview placeholder"><Box size={28} style={{ opacity: 0.3 }} /></div>}

        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '6px', wordBreak: 'break-word' }}>{asset.name || 'Untitled'}</h3>
          <div className="cs-tag-row">
            <span className="cs-tag">{asset.type}</span>
            <span className="cs-tag">v{asset.current_version || 1}</span>
            {asset.generator && <span className="cs-tag">{asset.generator}</span>}
            {asset.model && <span className="cs-tag">{asset.model}</span>}
            {score != null && (
              <span className={`cs-tag score ${score >= 0.75 ? 'good' : score >= 0.5 ? 'mid' : 'bad'}`}>
                <Gauge size={11} /> {Number(score).toFixed(2)}
              </span>
            )}
          </div>
        </div>

        <section>
          <h4 className="cs-section-title">Azioni</h4>
          <div className="cs-button-grid">
            {isImage && (
              <>
                <button className="cs-tool-btn" disabled={!can3D} title={can3D ? '' : 'Nessun backend 3D configurato'}
                        onClick={() => onGenerate3D('image_to_3d', { asset_id: asset.id })}>
                  <Box size={14} /> Converti in 3D
                </button>
                <button className="cs-tool-btn"
                        onClick={() => onMaterial('generate_from_image', { asset_id: asset.id })}>
                  <Layers size={14} /> Estrai PBR
                </button>
                <button className="cs-tool-btn" onClick={() => onUpscale(asset.id, 2)}>
                  <Sparkles size={14} /> Upscale 2x
                </button>
                <button className="cs-tool-btn" onClick={() => onEdit('remove_background', asset.id)}>
                  <Scissors size={14} /> Rimuovi sfondo
                </button>
                <button className="cs-tool-btn" onClick={() => onUpscale(asset.id, 2, true)}
                        title="Ricostruzione generativa per sorgenti degradate">
                  <Sparkles size={14} /> Restaura
                </button>
                <button className="cs-tool-btn" disabled={!canVideo}
                        title={canVideo ? 'Anima questa immagine' : 'Nessun backend video attivo'}
                        onClick={() => onVideo('image_to_video', { asset_id: asset.id, prompt: '' })}>
                  <Film size={14} /> Anima
                </button>
              </>
            )}
            {is3D && (
              <button className="cs-tool-btn" disabled={!canRender} title={canRender ? '' : 'Blender non configurato'}
                      onClick={() => onRender(asset.id, { engine: 'cycles', samples: 96 })}>
                <Play size={14} /> Render
              </button>
            )}
            {downloadUrl && (
              <a className="cs-tool-btn" href={downloadUrl} download><Download size={14} /> Scarica</a>
            )}
            <button className="cs-tool-btn danger" onClick={() => onDelete(asset.id)}>
              <Trash2 size={14} /> Elimina
            </button>
          </div>
        </section>

        {asset.file_urls && Object.keys(asset.file_urls).length > 1 && (
          <section>
            <h4 className="cs-section-title">File</h4>
            <div className="cs-map-grid small">
              {Object.entries(asset.file_urls).map(([role, url]) => (
                <figure key={role}>
                  {/\.(png|jpg|jpeg|webp)$/i.test(url)
                    ? <img src={url} alt={role} loading="lazy" />
                    : <div className="cs-file-chip">{role}</div>}
                  <figcaption><a href={url} download>{role}</a></figcaption>
                </figure>
              ))}
            </div>
          </section>
        )}

        {isImage && (
          <section>
            <h4 className="cs-section-title"><Eye size={13} /> Vision Agent</h4>
            {!canVision && <p className="cs-hint">Avvia Ollama con un modello vision (es. <code>qwen2.5vl:7b</code>).</p>}
            <div className="cs-button-grid">
              <button className="cs-tool-btn" disabled={!canVision} onClick={() => runVision('analyze')}>
                Analizza
              </button>
              <button className="cs-tool-btn" disabled={!canVision}
                      onClick={() => runVision('score', { intent: asset.metadata?.params?.prompt || asset.name })}>
                <Gauge size={14} /> Valuta
              </button>
              <button className="cs-tool-btn" disabled={!canVision} onClick={() => runVision('describe')}>
                Descrivi
              </button>
              <button className="cs-tool-btn" disabled={!canVision} onClick={() => runVision('ocr')}>
                Estrai testo
              </button>
            </div>
            {vision?.pending && <p className="cs-hint">Analisi in corso...</p>}
            {vision?.error && <p className="cs-hint" style={{ color: '#ff8888' }}>{vision.error}</p>}
            {vision && !vision.pending && !vision.error && (
              <pre className="cs-metadata">{
                vision.description || vision.text || JSON.stringify(vision, null, 2)
              }</pre>
            )}
          </section>
        )}

        <section>
          <h4 className="cs-section-title">Provenienza</h4>
          {lineage
            ? <div className="cs-lineage"><LineageTree node={lineage} onSelect={onSelectAsset} /></div>
            : <p className="cs-hint">Caricamento...</p>}
          {lineage && !lineage.parents?.length && <p className="cs-hint">Asset radice — nessuna sorgente.</p>}
        </section>

        <section>
          <h4 className="cs-section-title"><History size={13} /> Versioni</h4>
          {versions.length === 0 && <p className="cs-hint">Nessuna versione registrata.</p>}
          {versions.map(v => (
            <div key={v.version} className="cs-version-row">
              <span>v{v.version}</span>
              <span>{Object.keys(v.files || {}).length} file</span>
              <span>{v.created_at ? new Date(v.created_at).toLocaleString() : ''}</span>
            </div>
          ))}
        </section>

        {asset.metadata && Object.keys(asset.metadata).length > 0 && (
          <section>
            <h4 className="cs-section-title"><Clock size={13} /> Metadata</h4>
            <pre className="cs-metadata">{JSON.stringify(asset.metadata, null, 2)}</pre>
          </section>
        )}
      </div>
    </div>
  );
}
