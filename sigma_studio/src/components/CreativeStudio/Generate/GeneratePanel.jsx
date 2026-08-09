import React, { useRef, useState } from 'react';
import {
  Wand2, Dices, Image as ImageIcon, Smartphone, Monitor, MonitorPlay,
  Upload, Cpu, Sparkles, Sliders, History, Download, Eye, Layers, Box,
  Repeat, Settings2
} from 'lucide-react';
import ModelPicker from '../shared/ModelPicker';

const STYLES = ["Photorealistic", "Cyberpunk", "3D Render", "Anime", "Concept Art", "Cinematic", "Vaporwave"];

const RATIOS = [
  { label: '1:1', w: 1024, h: 1024, icon: ImageIcon, ratioClass: 'ratio-1-1' },
  { label: '16:9', w: 1280, h: 720, icon: Monitor, ratioClass: 'ratio-16-9' },
  { label: '9:16', w: 720, h: 1280, icon: Smartphone, ratioClass: 'ratio-9-16' },
  { label: '21:9', w: 1536, h: 640, icon: MonitorPlay, ratioClass: 'ratio-21-9' },
];

export default function GeneratePanel({
  onGenerate, onUpload, isGenerating, recentAssets = [], onSelectAsset, backends = [],
  models = [], inventory = null,
}) {
  const [prompt, setPrompt] = useState('');
  const [negativePrompt, setNegativePrompt] = useState('');
  const [steps, setSteps] = useState(30);
  const [cfg, setCfg] = useState(7);
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [seed, setSeed] = useState(-1);
  const [backend, setBackend] = useState('');
  const [model, setModel] = useState({});           // { model_id, ckpt }
  const [sampler, setSampler] = useState('');
  const [scheduler, setScheduler] = useState('');
  const [batch, setBatch] = useState(1);
  const [priority, setPriority] = useState('balanced');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeAssetId, setActiveAssetId] = useState(null);
  const fileRef = useRef(null);

  const imageBackends = backends.filter(b => b.available && b.capabilities?.includes('text_to_image'));
  const activeAsset = recentAssets.find(a => a.id === activeAssetId) || recentAssets[0];

  const appendStyle = (style) => {
    const p = prompt.trim();
    if (!p) setPrompt(style);
    else if (!p.includes(style)) setPrompt(`${p}, ${style.toLowerCase()}`);
  };

  const handleGenerateClick = () => {
    if (!prompt.trim() || isGenerating) return;
    // I campi vuoti non vengono inviati: il default lo decide il backend/modello,
    // non una stringa vuota che sovrascriverebbe una scelta sensata.
    const params = {
      prompt,
      negative_prompt: negativePrompt,
      steps,
      cfg_scale: cfg,
      width,
      height,
      seed,
      priority,
    };
    if (model.model_id) params.model_id = model.model_id;
    if (model.ckpt) params.ckpt = model.ckpt;
    if (sampler) params.sampler = sampler;
    if (scheduler) params.scheduler = scheduler;
    if (batch > 1) params.batch_size = batch;

    onGenerate(params, backend || undefined);
  };

  const handleSelectHistoryAsset = (asset) => {
    setActiveAssetId(asset.id);
    onSelectAsset?.(asset);
  };

  return (
    <div className="cs-generate">
      <div className="cs-gen-container">
        {/* COLONNA 1: PROMPT & STILE */}
        <div className="cs-gen-col cs-gen-col-left">
          <div className="cs-card-header">
            <Sparkles size={16} className="cs-icon-accent" />
            <span>Prompt Creativo</span>
          </div>

          <div className="cs-prompt-area">
            <div className="cs-prompt-box">
              <textarea
                placeholder="Descrivi la tua visione artistica nei minimi dettagli... (es. 'Un santuario cyberpunk avvolto nella nebbia neon')"
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerateClick(); }}
              />
            </div>

            <div className="cs-preset-section">
              <span className="cs-sublabel">Stili consigliati</span>
              <div className="cs-style-presets">
                {STYLES.map(s => (
                  <button key={s} type="button" className="cs-preset-chip" onClick={() => appendStyle(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="cs-negative-prompt">
              <span className="cs-sublabel">Negative Prompt</span>
              <div className="cs-prompt-box cs-prompt-box-small">
                <textarea
                  placeholder="Cosa escludere (es. 'blurry, low quality, deformed, duplicate')"
                  value={negativePrompt}
                  onChange={e => setNegativePrompt(e.target.value)}
                />
              </div>
            </div>

            <div className="cs-backend-picker">
              <span className="cs-sublabel"><Cpu size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Motore AI</span>
              <select
                value={backend}
                onChange={e => setBackend(e.target.value)}
                className="cs-select"
              >
                <option value="">Auto (Router Intelligente Sigma)</option>
                {imageBackends.map(b => <option key={b.name} value={b.name}>{b.name}</option>)}
              </select>
            </div>

            <ModelPicker
              task="text_to_image"
              models={models}
              inventory={inventory}
              value={model}
              onChange={setModel}
            />

            {!model.model_id && (
              <div className="cs-priority-picker">
                <span className="cs-sublabel">Criterio di scelta automatica</span>
                <div className="cs-priority-row">
                  {[
                    { id: 'quality', label: 'Qualità' },
                    { id: 'balanced', label: 'Bilanciato' },
                    { id: 'speed', label: 'Velocità' },
                  ].map(p => (
                    <button
                      key={p.id}
                      type="button"
                      className={`cs-pill ${priority === p.id ? 'active' : ''}`}
                      onClick={() => setPriority(p.id)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* COLONNA 2: PREVIEW CANVAS & AZIONE MAIN */}
        <div className="cs-gen-col cs-gen-col-center">
          <div className="cs-card-header">
            <Eye size={16} className="cs-icon-accent" />
            <span>Stage di Anteprima & Output</span>
          </div>

          <div className="cs-stage-container">
            {isGenerating ? (
              <div className="cs-stage-loading">
                <div className="cs-pulse-orb" />
                <span className="cs-stage-loading-text">Sintesi dell'opera in corso...</span>
                <span className="cs-stage-loading-sub">L'IA sta elaborando la tua richiesta</span>
              </div>
            ) : activeAsset?.url ? (
              <div className="cs-stage-preview">
                <img src={activeAsset.url} alt={activeAsset.name || 'Generazione'} className="cs-stage-img" />
                <div className="cs-stage-overlay">
                  <div className="cs-stage-asset-info">
                    <span className="cs-stage-asset-name">{activeAsset.name || 'Senza titolo'}</span>
                    <span className="cs-stage-asset-meta">{activeAsset.type || 'image'}</span>
                  </div>
                  <div className="cs-stage-actions">
                    <a className="cs-stage-btn" href={activeAsset.url} download title="Scarica ad alta risoluzione">
                      <Download size={14} />
                    </a>
                  </div>
                </div>
              </div>
            ) : (
              <div className="cs-stage-empty">
                <div className="cs-empty-icon-wrap">
                  <Wand2 size={36} className="cs-empty-icon" />
                </div>
                <h3>Area di Rendering Creativo</h3>
                <p>Inserisci un prompt a sinistra e clicca su <strong>Genera immagine</strong> per visualizzare il risultato in tempo reale.</p>
              </div>
            )}
          </div>

          <div className="cs-generate-actions-bar">
            <button
              className="cs-generate-btn"
              onClick={handleGenerateClick}
              disabled={isGenerating || !prompt.trim()}
            >
              <Wand2 size={20} className={isGenerating ? 'cs-spin-icon' : ''} />
              <span>{isGenerating ? 'Generazione...' : 'Genera immagine'}</span>
            </button>

            <button
              className="cs-icon-btn cs-upload-btn"
              title="Carica un'immagine nel vault"
              onClick={() => fileRef.current?.click()}
            >
              <Upload size={18} />
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              onChange={e => { const f = e.target.files?.[0]; if (f) onUpload?.(f); e.target.value = ''; }}
            />
          </div>
        </div>

        {/* COLONNA 3: PARAMETRI & VAULT RECENTI */}
        <div className="cs-gen-col cs-gen-col-right">
          <div className="cs-card-header">
            <Sliders size={16} className="cs-icon-accent" />
            <span>Parametri & Vault</span>
          </div>

          <div className="cs-params-panel">
            <div className="cs-param-group">
              <div className="cs-param-header">
                <label>Steps (Qualità)</label>
                <span className="cs-val-badge">{steps}</span>
              </div>
              <input type="range" min="1" max="150" value={steps} onChange={e => setSteps(Number(e.target.value))} />
            </div>

            <div className="cs-param-group">
              <div className="cs-param-header">
                <label>CFG Scale (Aderenza)</label>
                <span className="cs-val-badge">{cfg}</span>
              </div>
              <input type="range" min="1" max="30" step="0.5" value={cfg} onChange={e => setCfg(Number(e.target.value))} />
            </div>

            <div className="cs-param-group">
              <label className="cs-sublabel">Proporzioni (Aspect Ratio)</label>
              <div className="cs-aspect-ratios">
                {RATIOS.map(ratio => (
                  <button
                    key={ratio.label}
                    type="button"
                    className={`cs-ratio-btn ${width === ratio.w && height === ratio.h ? 'active' : ''}`}
                    onClick={() => { setWidth(ratio.w); setHeight(ratio.h); }}
                  >
                    <div className={`cs-ratio-box ${ratio.ratioClass}`} />
                    <span className="cs-ratio-label">{ratio.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="cs-param-group">
              <label className="cs-sublabel">Dimensioni esatte (px)</label>
              <div className="cs-dim-row">
                <input
                  type="number" min="256" max="4096" step="8" value={width}
                  onChange={e => setWidth(Number(e.target.value))}
                  className="cs-num-input" title="Larghezza" />
                <span className="cs-dim-x">×</span>
                <input
                  type="number" min="256" max="4096" step="8" value={height}
                  onChange={e => setHeight(Number(e.target.value))}
                  className="cs-num-input" title="Altezza" />
                <button type="button" className="cs-icon-btn" title="Scambia larghezza e altezza"
                        onClick={() => { setWidth(height); setHeight(width); }}>
                  <Repeat size={14} />
                </button>
              </div>
              <p className="cs-hint">Multipli di 8. SDXL rende al meglio attorno a 1 MP, FLUX regge anche 1536.</p>
            </div>

            <div className="cs-param-group">
              <button type="button" className="cs-advanced-toggle" onClick={() => setShowAdvanced(v => !v)}>
                <Settings2 size={13} /> Parametri avanzati {showAdvanced ? '−' : '+'}
              </button>

              {showAdvanced && (
                <div className="cs-advanced-fields">
                  <label className="cs-field">
                    <span>Sampler</span>
                    <select className="cs-select" value={sampler} onChange={e => setSampler(e.target.value)}>
                      <option value="">Default</option>
                      {(inventory?.samplers || []).map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                  <label className="cs-field">
                    <span>Scheduler</span>
                    <select className="cs-select" value={scheduler} onChange={e => setScheduler(e.target.value)}>
                      <option value="">Default</option>
                      {(inventory?.schedulers || []).map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                  <label className="cs-field">
                    <span>Batch</span>
                    <input type="number" min="1" max="8" value={batch}
                           onChange={e => setBatch(Number(e.target.value))} className="cs-num-input" />
                  </label>
                  {!inventory?.reachable && (
                    <p className="cs-hint">Sampler e scheduler compaiono quando ComfyUI è raggiungibile.</p>
                  )}
                </div>
              )}
            </div>

            <div className="cs-param-group">
              <label className="cs-sublabel">Seed Casuale o Fisso</label>
              <div className="cs-seed-row">
                <input
                  type="number"
                  value={seed}
                  onChange={e => setSeed(Number(e.target.value))}
                  className="cs-num-input cs-seed-input"
                />
                <button type="button" className="cs-icon-btn cs-seed-btn" onClick={() => setSeed(-1)} title="Seed casuale (-1)">
                  <Dices size={16} />
                </button>
              </div>
            </div>

            {recentAssets.length > 0 && (
              <div className="cs-history-section">
                <div className="cs-card-header cs-card-header-sub">
                  <History size={14} className="cs-icon-accent" />
                  <span>Vault Recenti</span>
                  <span className="cs-count-tag">{recentAssets.length}</span>
                </div>
                <div className="cs-history-grid">
                  {recentAssets.slice(0, 8).map(asset => (
                    <div
                      key={asset.id}
                      className={`cs-history-item ${activeAsset?.id === asset.id ? 'active' : ''}`}
                      onClick={() => handleSelectHistoryAsset(asset)}
                      title={asset.name || 'Asset'}
                    >
                      {asset.url ? (
                        <img src={asset.url} alt={asset.name} />
                      ) : (
                        <div className="cs-history-placeholder"><ImageIcon size={16} /></div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

