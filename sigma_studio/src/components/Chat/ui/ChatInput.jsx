import React, { useState } from 'react';
import { Send, Paperclip, RefreshCw, StopCircle, Mic, MicOff, AudioLines, Volume2, VolumeX, Sliders } from 'lucide-react';
import { setVoiceConfig as saveVoiceConfigToSpeechEngine, getVoiceConfig } from '../audioSpeech';

export default function ChatInput({
  input, setInput, loading, selectedModel, refs, providerColors, currentRouting,
  webSearch, setWebSearch, autoScroll, setAutoScroll,
  mcpAutoApprove, setMcpAutoApprove,
  speakerEnabled, setSpeakerEnabled,
  isRecording, onToggleRecording,
  smartMicState = 'off', onToggleSmartMic,
  loopMaxIterations, setLoopMaxIterations, loopActive,
  onSend, onStop, onOpenFilePicker, attachedFiles,
  children,
}) {
  const [showVoicePopover, setShowVoicePopover] = useState(false);
  const [voiceConfig, setVoiceConfigState] = useState(() => getVoiceConfig());

  const updateVoiceConfig = (updater) => {
    setVoiceConfigState(prev => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      saveVoiceConfigToSpeechEngine(updated);
      return updated;
    });
  };

  return (
    <div className="chat-input-area">
      <div className="chat-input-top-row">
        <div
          className="chat-input-provider-badge"
          style={{ backgroundColor: providerColors.bg, color: providerColors.color }}
        >
          {currentRouting.provider || 'ollama'}
        </div>
        <label
          className={`chat-websearch-toggle ${webSearch ? 'active' : ''}`}
          title={webSearch ? 'Ricerca Web Attiva: gli agenti consultano la rete per verificare informazioni e fonti' : 'Attiva Ricerca Web per consultare la rete'}
        >
          <input type="checkbox" checked={webSearch} onChange={e => setWebSearch(e.target.checked)} />
          <span className="websearch-indicator" />
          <span>🌐 Web Search</span>
        </label>
        <label className="chat-scroll-toggle" title="Auto-scroll">
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
          <span>📜 Auto Scroll</span>
        </label>
        <label
          className="chat-scroll-toggle"
          title={mcpAutoApprove
            ? 'Gli agenti eseguono subito anche gli strumenti che agiscono su casa, email e messaggi'
            : 'Gli strumenti che agiscono verso l\'esterno aspettano la tua conferma in chat'}
          style={{ color: mcpAutoApprove ? '#d29922' : undefined }}
        >
          <input
            type="checkbox"
            checked={!!mcpAutoApprove}
            // Chiamata opzionale: ChatInput vive in due contesti, e uno che
            // dimentichi di passare il setter deve lasciare la casella inerte,
            // non far esplodere il gestore del clic.
            onChange={e => setMcpAutoApprove?.(e.target.checked)}
          />
          <span>{mcpAutoApprove ? '⚡' : '🛡️'} Auto Approve</span>
        </label>
        {setSpeakerEnabled !== undefined && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto', position: 'relative' }}>
            <label 
              className={`chat-speaker-toggle ${speakerEnabled ? 'active' : ''}`} 
              title={speakerEnabled ? 'Speaker Agente Attivo: la voce dell\'agente riproduce la risposta' : 'Attiva lettura vocale della risposta dell\'agente (TTS)'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '0.68rem',
                color: speakerEnabled ? '#00d2ff' : '#8b8fa3',
                background: speakerEnabled ? 'rgba(0, 210, 255, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                border: speakerEnabled ? '1px solid rgba(0, 210, 255, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
                padding: '2px 8px',
                borderRadius: '12px',
                cursor: 'pointer',
                fontWeight: 600,
                transition: 'all 0.2s ease',
              }}
            >
              <input 
                type="checkbox" 
                checked={speakerEnabled} 
                onChange={e => setSpeakerEnabled(e.target.checked)} 
                style={{ display: 'none' }}
              />
              {speakerEnabled ? <Volume2 size={13} style={{ color: '#00d2ff' }} /> : <VolumeX size={13} style={{ color: '#5a5e72' }} />}
              <span>Speaker Agente: {speakerEnabled ? 'ON' : 'OFF'}</span>
            </label>

            {/* Volume Slider accanto al pulsante Speaker Agente */}
            {speakerEnabled && (
              <div 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'rgba(0, 210, 255, 0.08)',
                  border: '1px solid rgba(0, 210, 255, 0.25)',
                  borderRadius: '12px',
                  padding: '2px 7px',
                  transition: 'all 0.2s ease',
                }}
                title={`Volume voce agente: ${Math.round((voiceConfig.volume ?? 1.0) * 100)}%`}
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={voiceConfig.volume ?? 1.0}
                  onChange={e => updateVoiceConfig(prev => ({ ...prev, volume: parseFloat(e.target.value) }))}
                  style={{
                    width: '55px',
                    height: '3px',
                    accentColor: '#00d2ff',
                    cursor: 'pointer',
                  }}
                />
                <span style={{ fontSize: '0.64rem', fontWeight: 700, color: '#00d2ff', minWidth: '24px' }}>
                  {Math.round((voiceConfig.volume ?? 1.0) * 100)}%
                </span>
              </div>
            )}

            {/* Voice Tuning Button */}
            <button
              type="button"
              className={`chat-voice-tune-btn ${showVoicePopover ? 'active' : ''}`}
              onClick={(e) => { e.stopPropagation(); setShowVoicePopover(!showVoicePopover); }}
              title="Regola Velocità (Speed), Tono (Pitch) e Volume della voce dell'agente"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 7px',
                fontSize: '0.66rem',
                fontWeight: 600,
                color: showVoicePopover ? '#bc8cff' : '#8b8fa3',
                background: showVoicePopover ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                border: showVoicePopover ? '1px solid rgba(188, 140, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <Sliders size={12} color={showVoicePopover ? '#bc8cff' : '#00d2ff'} />
              <span>{voiceConfig.rate || 1.05}x</span>
            </button>

            {/* Popover Regolazione Voce */}
            {showVoicePopover && (
              <div 
                style={{
                  position: 'absolute',
                  bottom: '100%',
                  right: 0,
                  marginBottom: '8px',
                  width: '240px',
                  padding: '14px',
                  background: 'rgba(15, 17, 26, 0.95)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  zIndex: 2000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f0f2f8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Sliders size={13} color="#00f2fe" /> Regolazione Voce TTS
                  </span>
                  <button 
                    onClick={() => setShowVoicePopover(false)} 
                    style={{ background: 'none', border: 'none', color: '#8b8fa3', cursor: 'pointer', fontSize: '0.8rem' }}
                  >
                    ✕
                  </button>
                </div>

                {/* Slider Volume */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Volume Voce:</span>
                    <span style={{ color: '#00d2ff', fontWeight: 700 }}>{Math.round((voiceConfig.volume ?? 1.0) * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={voiceConfig.volume ?? 1.0}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, volume: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#00d2ff', cursor: 'pointer', height: '4px' }}
                  />
                </div>

                {/* Slider Velocità */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Velocità Lettura:</span>
                    <span style={{ color: '#bc8cff', fontWeight: 700 }}>{voiceConfig.rate || 1.05}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.7"
                    max="1.6"
                    step="0.05"
                    value={voiceConfig.rate || 1.05}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, rate: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#bc8cff', cursor: 'pointer', height: '4px' }}
                  />
                </div>

                {/* Slider Tono */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Tono Voce (Pitch):</span>
                    <span style={{ color: '#00d2ff', fontWeight: 700 }}>{voiceConfig.pitch || 1.0}</span>
                  </div>
                  <input
                    type="range"
                    min="0.6"
                    max="1.4"
                    step="0.05"
                    value={voiceConfig.pitch || 1.0}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, pitch: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#00d2ff', cursor: 'pointer', height: '4px' }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="chat-input-row">
        <textarea
          ref={refs.input}
          className="chat-input"
          placeholder={
            isRecording ? "🔴 Registrazione in corso... Parla adesso..."
            : smartMicState === 'listening' ? "🎤 Ti sto ascoltando... Parla adesso (invio automatico dopo 2s di silenzio)"
            : smartMicState === 'waiting' ? '✨ Pronuncia "Sigma" ed inizia a fare la tua domanda...'
            : `Chiedi qualcosa a ${selectedModel}...`
          }
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          rows={1}
          disabled={loading}
          style={
            isRecording ? { borderColor: '#ff5555', background: 'rgba(255, 85, 85, 0.06)' }
            : smartMicState === 'listening' ? { borderColor: '#4ade80', background: 'rgba(74, 222, 128, 0.06)' }
            : smartMicState === 'waiting' ? { borderColor: 'rgba(0, 210, 255, 0.4)' }
            : {}
          }
        />
        {onToggleRecording && (
          <button 
            className={`chat-attach-inline-btn ${isRecording ? 'recording' : ''}`} 
            onClick={onToggleRecording} 
            title={isRecording ? 'Interrompi registrazione comando vocale' : 'Registra comando vocale (STT)'}
            style={{
              color: isRecording ? '#ff5555' : 'var(--text-muted)',
              background: isRecording ? 'rgba(255, 85, 85, 0.15)' : 'transparent',
              borderColor: isRecording ? 'rgba(255, 85, 85, 0.4)' : 'transparent',
              animation: isRecording ? 'pulseMic 1.2s infinite' : 'none'
            }}
          >
            {isRecording ? <MicOff size={14} /> : <Mic size={14} />}
          </button>
        )}
        {onToggleSmartMic && (
          <button
            className={`chat-attach-inline-btn ${smartMicState !== 'off' ? 'recording' : ''}`}
            onClick={onToggleSmartMic}
            title={
              smartMicState === 'listening' ? 'Ti sto ascoltando — invio automatico dopo 2 secondi di silenzio'
              : smartMicState === 'waiting' ? '✨ Microfono intelligente attivo — Pronuncia "Sigma" ed inizia a fare la tua domanda'
              : '✨ Microfono intelligente: Pronuncia "Sigma" ed inizia a fare la tua domanda'
            }
            style={{
              color: smartMicState === 'listening' ? '#4ade80'
                : smartMicState === 'waiting' ? '#00d2ff'
                : 'var(--text-muted)',
              background: smartMicState === 'listening' ? 'rgba(74, 222, 128, 0.15)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.12)'
                : 'transparent',
              borderColor: smartMicState === 'listening' ? 'rgba(74, 222, 128, 0.4)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.35)'
                : 'transparent',
              animation: smartMicState === 'listening' ? 'pulseMic 1.2s infinite' : 'none'
            }}
          >
            <AudioLines size={14} />
          </button>
        )}
        <button className="chat-attach-inline-btn" onClick={onOpenFilePicker} title="Allega file">
          <Paperclip size={14} />
          {attachedFiles.length > 0 && <span className="chat-attach-count">{attachedFiles.length}</span>}
        </button>
        {loading ? (
          <button className="chat-send-btn stop" onClick={(e) => { e.preventDefault(); onStop && onStop(e); }} title="Ferma esecuzione">
            <Send size={16} />
          </button>
        ) : (
          <div className="chat-input-controls-group" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div className="chat-loop-wrapper" style={{ display: 'flex', alignItems: 'center' }}>
              <select
                className="chat-loop-max-select"
                value={loopMaxIterations}
                onChange={e => setLoopMaxIterations(parseInt(e.target.value))}
                disabled={loopActive}
                style={{
                  background: '#0e1016',
                  border: '1px solid #1e2030',
                  borderRadius: '4px',
                  color: '#8b8fa3',
                  fontSize: '0.62rem',
                  padding: '4px',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                <option value={1}>1x (Risposta Singola)</option>
                <option value={3}>3x Loop</option>
                <option value={5}>5x Loop</option>
                <option value={10}>10x Loop</option>
                <option value={25}>25x Loop</option>
                <option value={50}>50x Loop</option>
                <option value={999}>∞ Infinito</option>
              </select>
            </div>
            
            <button 
              className="chat-send-btn" 
              onClick={onSend} 
              disabled={!input.trim()} 
              title={loopMaxIterations > 1 ? `Invia in Loop (max ${loopMaxIterations === 999 ? '∞' : loopMaxIterations} iterazioni)` : 'Invia richiesta'}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Send size={16} />
              {loopMaxIterations > 1 && (
                <span className="chat-loop-badge" style={{
                  position: 'absolute',
                  top: '-4px',
                  right: '-4px',
                  background: '#00d2ff',
                  color: '#000',
                  fontSize: '0.5rem',
                  fontWeight: '700',
                  padding: '1px 3px',
                  borderRadius: '3px',
                  lineHeight: 1
                }}>
                  {loopMaxIterations === 999 ? '∞' : loopMaxIterations}
                </span>
              )}
            </button>
          </div>
        )}
      </div>
      {children}
    </div>
  );
}