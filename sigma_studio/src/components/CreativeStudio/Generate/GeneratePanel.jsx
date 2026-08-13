import React, { useRef, useState } from 'react';
import {
  Wand2, Dices, Image as ImageIcon, Smartphone, Monitor, MonitorPlay,
  Upload, Cpu, Sparkles, Sliders, History, Download, Eye, Layers, Box,
  Repeat, Settings2, ZoomIn, Scissors, Film
} from 'lucide-react';
import ModelPicker from '../shared/ModelPicker';

const STYLES = ["Photorealistic", "Cyberpunk", "3D Render", "Anime", "Concept Art", "Cinematic", "Vaporwave", "Digital Art"];

const RATIOS = [
  { label: '1:1 Quadrato', w: 1024, h: 1024, icon: ImageIcon },
  { label: '16:9 Cinema', w: 1280, h: 720, icon: Monitor },
  { label: '9:16 Mobile', w: 720, h: 1280, icon: Smartphone },
  { label: '21:9 Ultra-Wide', w: 1536, h: 640, icon: MonitorPlay },
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
  const [model, setModel] = useState({});
  const [sampler, setSampler] = useState('');
  const [scheduler, setScheduler] = useState('');
  const [batch, setBatch] = useState(1);
  const [priority, setPriority] = useState('balanced');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showNegative, setShowNegative] = useState(false);
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
    <div className="cs-generate-v2" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      padding: '20px 24px',
      boxSizing: 'border-box',
      overflowY: 'auto',
      gap: '20px'
    }}>
      {/* 1. TOP CREATIVE PROMPT & CONTROL HUB */}
      <div style={{
        background: 'var(--surface, rgba(17, 20, 29, 0.75))',
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--border-color, rgba(255, 255, 255, 0.08))',
        borderRadius: '16px',
        padding: '18px 20px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} color="#00d2ff" />
            <span style={{ fontSize: '0.86rem', fontWeight: 800 }}>Prompt & Visione Creativa</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setShowNegative(!showNegative)}
              style={{
                background: showNegative ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255,255,255,0.05)',
                border: showNegative ? '1px solid #ef4444' : '1px solid rgba(255,255,255,0.1)',
                color: showNegative ? '#ef4444' : 'inherit',
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            >
              {showNegative ? '− Negative Prompt' : '+ Negative Prompt'}
            </button>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                background: showAdvanced ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255,255,255,0.05)',
                border: showAdvanced ? '1px solid #00d2ff' : '1px solid rgba(255,255,255,0.1)',
                color: showAdvanced ? '#00d2ff' : 'inherit',
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <Settings2 size={12} /> {showAdvanced ? 'Meno Parametri' : 'Parametri Avanzati'}
            </button>
          </div>
        </div>

        {/* Main Prompt Textarea */}
        <div style={{ position: 'relative' }}>
          <textarea
            placeholder="Descrivi l'immagine che vuoi creare... (es. 'Un tempio futuristico sulle vette innevate di una montagna aliena, neon soffusi, atmosfera cinematografica, risoluzione 8k')"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerateClick(); }}
            rows={3}
            style={{
              width: '100%',
              padding: '12px 14px',
              borderRadius: '12px',
              background: 'rgba(0, 0, 0, 0.25)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: 'inherit',
              fontSize: '0.85rem',
              resize: 'vertical',
              outline: 'none',
              boxSizing: 'border-box',
              fontFamily: 'inherit',
              lineHeight: 1.5
            }}
          />
        </div>

        {/* Negative Prompt (Collapsible) */}
        {showNegative && (
          <div>
            <textarea
              placeholder="Cosa escludere (es. 'blurry, low quality, deformed, duplicate, watermark')"
              value={negativePrompt}
              onChange={e => setNegativePrompt(e.target.value)}
              rows={2}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.05)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: 'inherit',
                fontSize: '0.78rem',
                resize: 'none',
                outline: 'none',
                boxSizing: 'border-box',
                fontFamily: 'inherit'
              }}
            />
          </div>
        )}

        {/* Style Preset Chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.72rem', opacity: 0.7, marginRight: '4px' }}>Stili:</span>
          {STYLES.map(s => (
            <button
              key={s}
              type="button"
              onClick={() => appendStyle(s)}
              style={{
                padding: '4px 10px',
                borderRadius: '8px',
                background: prompt.includes(s.toLowerCase()) ? 'rgba(0, 210, 255, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                border: prompt.includes(s.toLowerCase()) ? '1px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.08)',
                color: prompt.includes(s.toLowerCase()) ? '#00d2ff' : 'inherit',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              + {s}
            </button>
          ))}
        </div>

        {/* Action Controls & Aspect Ratio Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          paddingTop: '6px',
          borderTop: '1px solid rgba(255, 255, 255, 0.06)'
        }}>
          {/* Aspect Ratio Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.72rem', opacity: 0.7, marginRight: '4px' }}>Formato:</span>
            {RATIOS.map(ratio => {
              const active = width === ratio.w && height === ratio.h;
              const Icon = ratio.icon;
              return (
                <button
                  key={ratio.label}
                  type="button"
                  onClick={() => { setWidth(ratio.w); setHeight(ratio.h); }}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    background: active ? '#00d2ff' : 'rgba(255, 255, 255, 0.04)',
                    border: active ? '1px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.08)',
                    color: active ? '#000000' : 'inherit',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}
                >
                  <Icon size={13} /> {ratio.label}
                </button>
              );
            })}
          </div>

          {/* Quick Quality Sliders */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.72rem', opacity: 0.7 }}>Steps:</span>
              <input
                type="range"
                min="15"
                max="100"
                value={steps}
                onChange={e => setSteps(Number(e.target.value))}
                style={{ width: '80px', accentColor: '#00d2ff' }}
              />
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#00d2ff', minWidth: '20px' }}>{steps}</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.72rem', opacity: 0.7 }}>CFG:</span>
              <input
                type="range"
                min="1"
                max="20"
                step="0.5"
                value={cfg}
                onChange={e => setCfg(Number(e.target.value))}
                style={{ width: '70px', accentColor: '#bc8cff' }}
              />
              <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#bc8cff', minWidth: '20px' }}>{cfg}</span>
            </div>

            {/* Main Generate Button */}
            <button
              onClick={handleGenerateClick}
              disabled={isGenerating || !prompt.trim()}
              style={{
                padding: '10px 24px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)',
                border: 'none',
                color: '#ffffff',
                fontSize: '0.84rem',
                fontWeight: 800,
                cursor: isGenerating || !prompt.trim() ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 18px rgba(0, 210, 255, 0.35)',
                opacity: isGenerating || !prompt.trim() ? 0.6 : 1,
                transition: 'all 0.18s ease'
              }}
            >
              <Wand2 size={16} className={isGenerating ? 'spin' : ''} />
              <span>{isGenerating ? 'Generazione in corso...' : 'Genera Immagine'}</span>
            </button>
          </div>
        </div>

        {/* Advanced Settings Drawer (Optional) */}
        {showAdvanced && (
          <div style={{
            padding: '12px',
            borderRadius: '10px',
            background: 'rgba(0, 0, 0, 0.2)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            fontSize: '0.75rem'
          }}>
            <div>
              <label style={{ display: 'block', opacity: 0.7, marginBottom: '4px' }}>Motore Backend</label>
              <select
                value={backend}
                onChange={e => setBackend(e.target.value)}
                style={{ width: '100%', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'inherit' }}
              >
                <option value="">Auto (Router Intelligente)</option>
                {imageBackends.map(b => <option key={b.name} value={b.name}>{b.name}</option>)}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', opacity: 0.7, marginBottom: '4px' }}>Seed Casuale o Fisso</label>
              <div style={{ display: 'flex', gap: '4px' }}>
                <input
                  type="number"
                  value={seed}
                  onChange={e => setSeed(Number(e.target.value))}
                  style={{ flex: 1, padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'inherit' }}
                />
                <button
                  type="button"
                  onClick={() => setSeed(-1)}
                  style={{ padding: '6px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.08)', border: 'none', color: 'inherit', cursor: 'pointer' }}
                  title="Seed casuale"
                >
                  <Dices size={14} />
                </button>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', opacity: 0.7, marginBottom: '4px' }}>Dimensioni Esatte (W × H)</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <input
                  type="number"
                  value={width}
                  onChange={e => setWidth(Number(e.target.value))}
                  style={{ width: '60px', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'inherit' }}
                />
                <span>×</span>
                <input
                  type="number"
                  value={height}
                  onChange={e => setHeight(Number(e.target.value))}
                  style={{ width: '60px', padding: '6px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'inherit' }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. LARGE INTERACTIVE VISUAL STAGE */}
      <div style={{
        flex: 1,
        minHeight: '380px',
        borderRadius: '16px',
        background: 'var(--surface, rgba(10, 13, 20, 0.8))',
        border: '1px solid var(--border-color, rgba(255, 255, 255, 0.08))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: 'inset 0 0 40px rgba(0,0,0,0.4)'
      }}>
        {isGenerating ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div className="cs-pulse-orb" style={{ margin: '0 auto 16px auto' }} />
            <h3 style={{ margin: '0 0 6px 0', fontSize: '1.1rem', fontWeight: 800 }}>Sintesi Creativa in Corso...</h3>
            <p style={{ margin: 0, fontSize: '0.8rem', opacity: 0.7 }}>I modelli neurali stanno generando la tua opera d'arte ad alta fedeltà.</p>
          </div>
        ) : activeAsset?.url ? (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
            <img
              src={activeAsset.url}
              alt={activeAsset.name || 'Opera generata'}
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
                borderRadius: '8px'
              }}
            />

            {/* Overlay Toolbar */}
            <div style={{
              position: 'absolute',
              bottom: '16px',
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '8px 16px',
              borderRadius: '24px',
              background: 'rgba(10, 14, 24, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              boxShadow: '0 8px 30px rgba(0,0,0,0.5)'
            }}>
              <span style={{ fontSize: '0.76rem', fontWeight: 700, paddingRight: '8px', borderRight: '1px solid rgba(255,255,255,0.1)' }}>
                {activeAsset.name || 'Generazione'}
              </span>
              <a
                href={activeAsset.url}
                download
                title="Scarica immagine"
                style={{ color: '#00d2ff', display: 'flex', alignItems: 'center', textDecoration: 'none' }}
              >
                <Download size={16} />
              </a>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', maxWidth: '400px' }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '20px',
              background: 'rgba(0, 210, 255, 0.1)',
              border: '1px solid rgba(0, 210, 255, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto'
            }}>
              <Wand2 size={28} color="#00d2ff" />
            </div>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '1.1rem', fontWeight: 800 }}>Canvas di Generazione Creativa</h3>
            <p style={{ margin: 0, fontSize: '0.8rem', opacity: 0.7, lineHeight: 1.5 }}>
              Inserisci un prompt nel box superiore e premi <strong>Genera Immagine</strong> per sintetizzare artwork in tempo reale.
            </p>
          </div>
        )}
      </div>

      {/* 3. RECENT GENERATIONS STRIP */}
      {recentAssets.length > 0 && (
        <div style={{
          background: 'var(--surface, rgba(17, 20, 29, 0.6))',
          borderRadius: '14px',
          padding: '12px 16px',
          border: '1px solid var(--border-color, rgba(255, 255, 255, 0.06))'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', fontWeight: 800 }}>
              <History size={14} color="#00d2ff" />
              <span>Generazioni Recenti</span>
              <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: '8px', background: 'rgba(0,210,255,0.15)', color: '#00d2ff' }}>
                {recentAssets.length}
              </span>
            </div>
          </div>

          <div style={{
            display: 'flex',
            gap: '10px',
            overflowX: 'auto',
            paddingBottom: '4px'
          }}>
            {recentAssets.map(asset => {
              const isActive = activeAsset?.id === asset.id;
              return (
                <div
                  key={asset.id}
                  onClick={() => handleSelectHistoryAsset(asset)}
                  style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '10px',
                    overflow: 'hidden',
                    flexShrink: 0,
                    border: isActive ? '2px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.1)',
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'all 0.15s ease',
                    boxShadow: isActive ? '0 0 12px rgba(0,210,255,0.3)' : 'none'
                  }}
                  title={asset.name}
                >
                  {asset.url ? (
                    <img src={asset.url} alt={asset.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)' }}>
                      <ImageIcon size={18} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
