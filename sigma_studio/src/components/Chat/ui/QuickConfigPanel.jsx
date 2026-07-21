import React from 'react';

export default function QuickConfigPanel({ quickConfig, setQuickConfig, onClose }) {
  const applyPreset = (preset) => {
    setQuickConfig(prev => ({ ...prev, ...preset }));
  };

  return (
    <div className="chat-quick-config">
      <div className="chat-quick-config-header">
        <div className="qc-header-title">
          <span className="qc-icon">⚙️</span>
          <span>IMPOSTAZIONI INTERAZIONE & PARAMETRI MODELLO</span>
        </div>
        <button className="qc-close-btn" onClick={onClose} title="Chiudi impostazioni">✕</button>
      </div>

      {/* Preset bar */}
      <div className="qc-presets-row">
        <span className="qc-presets-label">Preset Rapidi:</span>
        <button
          className="qc-preset-btn"
          onClick={() => applyPreset({ temperature: 0.7, top_p: 0.9, top_k: 40, repeat_penalty: 1.1 })}
        >
          🎯 Bilanciato
        </button>
        <button
          className="qc-preset-btn"
          onClick={() => applyPreset({ temperature: 0.2, top_p: 0.8, top_k: 20, repeat_penalty: 1.15 })}
        >
          🔬 Codice & Logica
        </button>
        <button
          className="qc-preset-btn"
          onClick={() => applyPreset({ temperature: 1.0, top_p: 0.95, top_k: 60, repeat_penalty: 1.05 })}
        >
          🎨 Creativo
        </button>
      </div>

      <div className="chat-quick-config-grid">
        {/* Sliders group */}
        {[
          { label: 'Temperatura (Creatività)', key: 'temperature', icon: '🌡️', min: 0, max: 2, step: 0.05, format: (v) => v?.toFixed(2) },
          { label: 'Top P (Sampling)', key: 'top_p', icon: '🎯', min: 0, max: 1, step: 0.05, format: (v) => v?.toFixed(2) },
          { label: 'Top K (Vocabolario)', key: 'top_k', icon: '🔝', min: 1, max: 100, step: 1, format: (v) => v },
          { label: 'Penalità Ripetizione', key: 'repeat_penalty', icon: '🔁', min: 0, max: 2, step: 0.05, format: (v) => v?.toFixed(2) },
        ].map(cfg => (
          <div key={cfg.key} className="qc-card">
            <div className="qc-card-header">
              <span className="qc-card-label">{cfg.icon} {cfg.label}</span>
              <span className="qc-card-val">{cfg.format(quickConfig[cfg.key])}</span>
            </div>
            <input
              type="range"
              className="qc-slider"
              min={cfg.min}
              max={cfg.max}
              step={cfg.step}
              value={quickConfig[cfg.key]}
              onChange={e => setQuickConfig(prev => ({ ...prev, [cfg.key]: parseFloat(e.target.value) }))}
            />
          </div>
        ))}

        {/* Dropdowns group */}
        <div className="qc-card">
          <div className="qc-card-header">
            <span className="qc-card-label">📝 Max Tokens</span>
          </div>
          <select
            className="qc-select"
            value={quickConfig.max_tokens}
            onChange={e => setQuickConfig(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
          >
            {[512, 1024, 2048, 4096, 8192, 16384, 32768].map(v => (
              <option key={v} value={v}>{v >= 1024 ? `${v/1024}K token` : `${v} token`}</option>
            ))}
          </select>
        </div>

        <div className="qc-card">
          <div className="qc-card-header">
            <span className="qc-card-label">🧠 Finestra Contesto (num_ctx)</span>
          </div>
          <select
            className="qc-select"
            value={quickConfig.num_ctx}
            onChange={e => setQuickConfig(prev => ({ ...prev, num_ctx: parseInt(e.target.value) }))}
          >
            {[2048, 4096, 8192, 16384, 32768, 65536, 131072].map(v => (
              <option key={v} value={v}>{v >= 1024 ? `${v/1024}K` : v}</option>
            ))}
          </select>
        </div>

        <div className="qc-card">
          <div className="qc-card-header">
            <span className="qc-card-label">⏱️ Timeout Risposta</span>
          </div>
          <select
            className="qc-select"
            value={quickConfig.timeout || 300}
            onChange={e => setQuickConfig(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
          >
            {[60, 120, 300, 600, 900].map(v => (
              <option key={v} value={v}>{v}s ({v/60}m)</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
