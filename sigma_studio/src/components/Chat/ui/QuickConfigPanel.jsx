import React, { useState } from 'react';

export default function QuickConfigPanel({ quickConfig, setQuickConfig, onClose }) {
  const [hoveredKey, setHoveredKey] = useState(null);

  const applyPreset = (preset) => {
    setQuickConfig(prev => ({ ...prev, ...preset }));
  };

  const descriptions = {
    temperature: {
      text: 'Controlla la "creatività" del modello. Più alto = più inventivo ma meno preciso.\n\n• 0.1–0.4: Risposte precise, deterministiche (ideale per codice, logica, matematica)\n• 0.5–0.8: Bilanciato tra creatività e coerenza (ideale per uso generale)\n• 0.9–2.0: Molto creativo, possibili allucinazioni (ideale per brainstorming)',
    },
    top_p: {
      text: 'Nucleus sampling: seleziona un insieme di token la cui probabilità cumulativa raggiunge P.\n\n• 0.1–0.4: Selezione ristretta, risposte più sicure e prevedibili\n• 0.5–0.8: Bilanciamento tra varietà e coerenza\n• 0.9–1.0: Massima diversità nei token selezionati\n\nFunziona insieme a Temperature: alzando uno, abbassa l\'altro.',
    },
    top_k: {
      text: 'Limita il numero di token candidati durante la generazione. Il modello sceglie solo tra i K token più probabili.\n\n• 1–20: Scelta molto ristretta (risposte precise, ripetitive)\n• 20–50: Bilanciato (buon compromesso)\n• 50–100: Ampia scelta (maggiore varietà linguistica)\n\nValori più bassi = meno sorprese, valori più alti = più creatività.',
    },
    repeat_penalty: {
      text: 'Penalizza i token già generati per evitare loop e ripetizioni.\n\n• 0.0–0.9: Permette ripetizioni (utile per testi tecnici con terminologia ripetuta)\n• 1.0–1.1: Neutro / lieve penalità (consigliato per uso generale)\n• 1.15–2.0: Forte penalità (evita quasi tutte le ripetizioni, può frammentare il testo)\n\nIl valore predefinito consigliato è 1.10.',
    },
    max_tokens: {
      text: 'Numero massimo di token che il modello può generare in una singola risposta.\n\n• 512–1024: Risposte brevi e concise (domande rapide, Q&A)\n• 2048–4096: Risposte dettagliate (analisi, spiegazioni) — consigliato\n• 8192–16384: Risposte molto estese (codice lungo, documenti)\n• 32768: Massima estensione (richiede contesto molto grande)\n\nNota: valori più alti richiedono più tempo e memoria.',
    },
    num_ctx: {
      text: 'Dimensione della finestra di contesto: quanti token il modello "ricorda" della conversazione.\n\n• 2K–4K: Contesto minimo (chat semplici, domanda-risposta)\n• 8K: Buono per la maggior parte dei casi (consigliato)\n• 16K–32K: Conversazioni lunghe o analisi di documenti estesi\n• 65K–128K: Sessioni avanzate con molto materiale di riferimento\n\nPiù alto = più memoria ma anche più lento e costoso in risorse.',
    },
    timeout: {
      text: 'Tempo massimo di attesa per la risposta del modello prima di interrompere.\n\n• 60s (1m): Risposte semplici e rapide\n• 120s (2m): Query di media complessità\n• 300s (5m): Analisi e generazione di contenuti complessi — consigliato\n• 600s (10m): Risposte molto elaborate o modelli grandi\n• 900s (15m): Operazioni pesanti o modelli locali lenti\n\nSe le richieste vanno in timeout, aumentare questo valore.',
    },
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
          onClick={() => applyPreset({ temperature: 0.7, top_p: 0.95, top_k: 40, repeat_penalty: 1.1, max_tokens: 16384, num_ctx: 32768 })}
        >
          🎯 Bilanciato (32K Ctx)
        </button>
        <button
          className="qc-preset-btn"
          onClick={() => applyPreset({ temperature: 0.2, top_p: 0.9, top_k: 40, repeat_penalty: 1.05, max_tokens: 32768, num_ctx: 65536 })}
        >
          🔬 Codice & Logica (65K Ctx)
        </button>
        <button
          className="qc-preset-btn"
          onClick={() => applyPreset({ temperature: 0.85, top_p: 0.95, top_k: 50, repeat_penalty: 1.05, max_tokens: 16384, num_ctx: 65536 })}
        >
          🎨 Creativo (65K Ctx)
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
              <span
                className="qc-card-label"
                onMouseEnter={() => setHoveredKey(cfg.key)}
                onMouseLeave={() => setHoveredKey(null)}
              >
                {cfg.icon} {cfg.label}
                <span className="qc-label-hint">ⓘ</span>
              </span>
              <span className="qc-card-val">{cfg.format(quickConfig[cfg.key])}</span>
              {hoveredKey === cfg.key && (
                <div className="qc-tooltip">
                  <div className="qc-tooltip-text">{descriptions[cfg.key].text}</div>
                </div>
              )}
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
            <span
              className="qc-card-label"
              onMouseEnter={() => setHoveredKey('max_tokens')}
              onMouseLeave={() => setHoveredKey(null)}
            >
              📝 Max Tokens
              <span className="qc-label-hint">ⓘ</span>
            </span>
            {hoveredKey === 'max_tokens' && (
              <div className="qc-tooltip">
                <div className="qc-tooltip-text">{descriptions.max_tokens.text}</div>
              </div>
            )}
          </div>
          <select
            className="qc-select"
            value={quickConfig.max_tokens}
            onChange={e => setQuickConfig(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
          >
            {[2048, 4096, 8192, 16384, 32768, 65536].map(v => (
              <option key={v} value={v}>{v >= 1024 ? `${v/1024}K token` : `${v} token`}</option>
            ))}
          </select>
        </div>

        <div className="qc-card">
          <div className="qc-card-header">
            <span
              className="qc-card-label"
              onMouseEnter={() => setHoveredKey('num_ctx')}
              onMouseLeave={() => setHoveredKey(null)}
            >
              🧠 Finestra Contesto (num_ctx)
              <span className="qc-label-hint">ⓘ</span>
            </span>
            {hoveredKey === 'num_ctx' && (
              <div className="qc-tooltip">
                <div className="qc-tooltip-text">{descriptions.num_ctx.text}</div>
              </div>
            )}
          </div>
          <select
            className="qc-select"
            value={quickConfig.num_ctx}
            onChange={e => setQuickConfig(prev => ({ ...prev, num_ctx: parseInt(e.target.value) }))}
          >
            {[8192, 16384, 32768, 65536, 131072, 262144].map(v => (
              <option key={v} value={v}>{v >= 1024 ? `${v/1024}K token` : `${v} token`}</option>
            ))}
          </select>
        </div>

        <div className="qc-card">
          <div className="qc-card-header">
            <span
              className="qc-card-label"
              onMouseEnter={() => setHoveredKey('timeout')}
              onMouseLeave={() => setHoveredKey(null)}
            >
              ⏱️ Timeout Risposta
              <span className="qc-label-hint">ⓘ</span>
            </span>
            {hoveredKey === 'timeout' && (
              <div className="qc-tooltip">
                <div className="qc-tooltip-text">{descriptions.timeout.text}</div>
              </div>
            )}
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