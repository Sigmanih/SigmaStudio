import React, { useState } from 'react';
import {
  Zap, X, Gauge, Clock, Cpu, Sparkles, Copy, Check,
  AlertTriangle, RefreshCw, Send, Play, Layers, Terminal
} from 'lucide-react';

const QUICK_PROMPTS = [
  {
    id: 'speed',
    icon: '⚡',
    label: 'Test Velocità (Throughput)',
    text: 'Spiega in tre frasi concise perché il cielo di giorno è azzurro e al tramonto diventa rosso, citando lo scattering di Rayleigh.'
  },
  {
    id: 'reasoning',
    icon: '🧠',
    label: 'Ragionamento Logico',
    text: 'In una stanza ci sono 4 gatti. Ognuno vede 3 gatti. Quanti gatti ci sono in totale nella stanza? Motiva brevemente la risposta.'
  },
  {
    id: 'code',
    icon: '💻',
    label: 'Funzione Python',
    text: 'Scrivi una funzione Python con type hints e docstring per trovare i primi N numeri primi utilizzando il Crivello di Eratostene.'
  },
  {
    id: 'creative',
    icon: '✨',
    label: 'Sintesi & Creatività',
    text: 'Descrivi in 40 parole il futuro dell\'intelligenza artificiale locale su hardware consumer con tono epico e futuristico.'
  }
];

export default function InferenceTestModal({ model, onClose, isLight, addToast }) {
  const [prompt, setPrompt] = useState(
    'Spiega in tre frasi perché il cielo di giorno è azzurro e come funziona lo scattering di Rayleigh.'
  );
  const [maxTokens, setMaxTokens] = useState(128);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.07)';
  const inputBg = isLight ? '#ffffff' : '#121624';

  const modelIdentifier = model?.model_id || model?.filename || model?.display_name || '';

  const handleRunInference = async () => {
    if (!prompt.trim()) {
      if (addToast) addToast('⚠️ Inserisci un prompt prima di avviare la prova.', 'warning');
      return;
    }

    setRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/models/speedtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: modelIdentifier,
          prompt: prompt.trim(),
          max_tokens: maxTokens
        })
      });
      const json = await res.json();
      if (json.success) {
        setResult(json);
        if (addToast) addToast(`⚡ Inferenza completata: ${json.decode_tok_s || json.answer_tok_s || '?'} tok/s`, 'success');
      } else {
        setError(json.error || 'Prova di inferenza fallita.');
        if (addToast) addToast(`❌ ${json.error || 'Errore inferenza'}`, 'error');
      }
    } catch (e) {
      setError(`Errore di connessione: ${e.message}`);
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setRunning(false);
    }
  };

  const handleCopy = () => {
    if (!result?.answer) return;
    navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    if (addToast) addToast('📋 Risposta copiata negli appunti!', 'info');
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.80)', backdropFilter: 'blur(10px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px'
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: '780px', maxHeight: '92vh',
          background: cardBg, border: cardBorder, borderRadius: '22px',
          boxShadow: '0 25px 60px rgba(0,0,0,0.7), 0 0 35px rgba(0, 210, 255, 0.15)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '16px 22px', borderBottom: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: isLight ? 'rgba(0, 210, 255, 0.05)' : 'linear-gradient(135deg, rgba(0, 210, 255, 0.12) 0%, rgba(188, 140, 255, 0.04) 100%)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px', height: '38px', borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(0, 144, 255, 0.25))',
              border: '1px solid rgba(0, 210, 255, 0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 15px rgba(0, 210, 255, 0.3)'
            }}>
              <Gauge size={20} color="#00d2ff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 900, color: textPrimary, letterSpacing: '-0.02em' }}>
                  Prova Inferenza & Telemetria Throughput
                </h3>
                <span style={{
                  fontSize: '0.62rem', fontWeight: 800, padding: '2px 7px', borderRadius: '5px',
                  background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', border: '1px solid rgba(0, 210, 255, 0.3)'
                }}>
                  {model?.format_tag || 'GGUF'}
                </span>
                {model?.quantization && (
                  <span style={{
                    fontSize: '0.62rem', fontWeight: 800, padding: '2px 7px', borderRadius: '5px',
                    background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', border: '1px solid rgba(188, 140, 255, 0.3)'
                  }}>
                    {model.quantization}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
                Modello: <strong style={{ color: textPrimary }}>{modelIdentifier}</strong>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: textMuted,
              cursor: 'pointer', padding: '6px', borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px 22px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', flex: 1 }}>

          {/* Quick Prompt Presets */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={11} color="#ffb86c" /> Prompt Rapidi Preimpostati
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '8px' }}>
              {QUICK_PROMPTS.map(qp => (
                <button
                  key={qp.id}
                  onClick={() => setPrompt(qp.text)}
                  style={{
                    padding: '8px 10px', borderRadius: '10px',
                    background: subBg, border: subBorder,
                    color: textPrimary, fontSize: '0.72rem', fontWeight: 700,
                    textAlign: 'left', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(0, 210, 255, 0.4)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = ''}
                >
                  <span>{qp.icon}</span>
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{qp.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Prompt Input Textarea */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                Prompt di Test
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.68rem', color: textMuted, fontWeight: 700 }}>Max Tokens:</span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[64, 96, 128, 256, 512].map(num => (
                    <button
                      key={num}
                      onClick={() => setMaxTokens(num)}
                      style={{
                        padding: '2px 7px', borderRadius: '5px',
                        background: maxTokens === num ? 'rgba(0, 210, 255, 0.2)' : subBg,
                        border: maxTokens === num ? '1px solid #00d2ff' : subBorder,
                        color: maxTokens === num ? '#00d2ff' : textMuted,
                        fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer'
                      }}
                    >
                      {num}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="Scrivi qui il prompt per testare la generazione e la velocità..."
              rows={3}
              disabled={running}
              style={{
                width: '100%', padding: '12px 14px', borderRadius: '12px',
                background: inputBg, border: subBorder, color: textPrimary,
                fontSize: '0.80rem', lineHeight: '1.45', outline: 'none',
                resize: 'vertical', boxSizing: 'border-box'
              }}
            />
          </div>

          {/* Action Trigger */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
            <div style={{ fontSize: '0.68rem', color: textMuted }}>
              💡 Misura sia la lettura del prompt (prefill) che la scrittura (decode) in token/secondo reali.
            </div>

            <button
              onClick={handleRunInference}
              disabled={running || !prompt.trim()}
              style={{
                padding: '10px 22px', borderRadius: '10px', border: 'none',
                background: running
                  ? 'rgba(0, 210, 255, 0.2)'
                  : 'linear-gradient(135deg, #00d2ff, #0090ff)',
                color: '#ffffff', fontSize: '0.80rem', fontWeight: 800,
                cursor: (running || !prompt.trim()) ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px',
                boxShadow: running ? 'none' : '0 0 16px rgba(0, 210, 255, 0.35)',
                transition: 'all 0.15s ease'
              }}
            >
              {running ? (
                <>
                  <RefreshCw size={14} className="mh-spin" /> Generazione & Misura in corso...
                </>
              ) : (
                <>
                  <Zap size={14} /> Esegui Prova di Inferenza
                </>
              )}
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div style={{
              padding: '12px 14px', borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.10)', border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444', fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: '8px'
            }}>
              <AlertTriangle size={16} style={{ flexShrink: 0 }} />
              <div>{error}</div>
            </div>
          )}

          {/* Telemetry Result HUD */}
          {result && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* HUD Cards Grid */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px'
              }}>
                {/* 1. Decode Speed (tok/s) */}
                <div style={{
                  padding: '12px 14px', borderRadius: '14px',
                  background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.15) 0%, rgba(0, 144, 255, 0.08) 100%)',
                  border: '1.5px solid rgba(0, 210, 255, 0.4)',
                  boxShadow: '0 0 16px rgba(0, 210, 255, 0.15)'
                }}>
                  <div style={{ fontSize: '0.64rem', color: '#00d2ff', fontWeight: 800, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Zap size={11} /> GENERAZIONE (DECODE)
                  </div>
                  <div style={{ fontSize: '1.45rem', fontWeight: 900, color: '#00d2ff', marginTop: '2px', fontFamily: 'monospace' }}>
                    {result.decode_tok_s || result.answer_tok_s || 0} <span style={{ fontSize: '0.72rem', fontWeight: 700 }}>tok/s</span>
                  </div>
                  <div style={{ fontSize: '0.60rem', color: textMuted, marginTop: '2px' }}>
                    Velocità percepita in chat
                  </div>
                </div>

                {/* 2. Prefill Speed */}
                <div style={{
                  padding: '12px 14px', borderRadius: '14px',
                  background: subBg, border: subBorder
                }}>
                  <div style={{ fontSize: '0.64rem', color: '#10b981', fontWeight: 800, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Layers size={11} /> LETTURA PROMPT
                  </div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#10b981', marginTop: '2px', fontFamily: 'monospace' }}>
                    {result.prefill_tok_s || 0} <span style={{ fontSize: '0.72rem', fontWeight: 700 }}>tok/s</span>
                  </div>
                  <div style={{ fontSize: '0.60rem', color: textMuted, marginTop: '2px' }}>
                    Prefill throughput
                  </div>
                </div>

                {/* 3. Time to First Token */}
                <div style={{
                  padding: '12px 14px', borderRadius: '14px',
                  background: subBg, border: subBorder
                }}>
                  <div style={{ fontSize: '0.64rem', color: '#ffb86c', fontWeight: 800, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={11} /> PRIMA PAROLA (TTFT)
                  </div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#ffb86c', marginTop: '2px', fontFamily: 'monospace' }}>
                    {result.ttft_ms || 0} <span style={{ fontSize: '0.72rem', fontWeight: 700 }}>ms</span>
                  </div>
                  <div style={{ fontSize: '0.60rem', color: textMuted, marginTop: '2px' }}>
                    Latenza di risposta iniziale
                  </div>
                </div>

                {/* 4. Hardware & Total */}
                <div style={{
                  padding: '12px 14px', borderRadius: '14px',
                  background: subBg, border: subBorder
                }}>
                  <div style={{ fontSize: '0.64rem', color: '#bc8cff', fontWeight: 800, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Cpu size={11} /> HARDWARE & TOTALI
                  </div>
                  <div style={{ fontSize: '0.90rem', fontWeight: 900, color: textPrimary, marginTop: '4px' }}>
                    {result.answer_tokens || 0} token <span style={{ fontSize: '0.70rem', color: textMuted }}>in {result.answer_seconds}s</span>
                  </div>
                  <div style={{ fontSize: '0.60rem', color: '#bc8cff', marginTop: '2px', fontWeight: 700 }}>
                    {result.hardware?.device || 'Dispositivo Locale'} {result.backend ? `• ${result.backend}` : ''}
                  </div>
                </div>
              </div>

              {/* Generated Answer Display */}
              <div style={{
                padding: '14px 16px', borderRadius: '14px',
                background: inputBg, border: subBorder,
                display: 'flex', flexDirection: 'column', gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Terminal size={12} color="#00d2ff" /> Risposta Generata dal Modello
                  </span>
                  <button
                    onClick={handleCopy}
                    style={{
                      padding: '3px 8px', borderRadius: '6px',
                      background: subBg, border: subBorder,
                      color: copied ? '#10b981' : textPrimary,
                      fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '4px'
                    }}
                  >
                    {copied ? <Check size={11} /> : <Copy size={11} />}
                    {copied ? 'Copiato!' : 'Copia Testo'}
                  </button>
                </div>

                <div style={{
                  fontSize: '0.78rem', color: textPrimary, lineHeight: '1.55',
                  maxHeight: '180px', overflowY: 'auto', whiteSpace: 'pre-wrap',
                  fontFamily: 'system-ui, -apple-system, sans-serif'
                }}>
                  {result.answer || 'Nessun output testuale generato.'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '12px 22px', borderTop: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.01)'
        }}>
          <div style={{ fontSize: '0.68rem', color: textMuted }}>
            {model?.size_gb ? `Dimensione: ${model.size_gb} GB` : ''}
            {model?.est_vram_gb ? ` • VRAM: ~${model.est_vram_gb} GB` : ''}
          </div>

          <button
            onClick={onClose}
            style={{
              padding: '7px 18px', borderRadius: '8px',
              border: subBorder, background: subBg,
              color: textPrimary, fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer'
            }}
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}
