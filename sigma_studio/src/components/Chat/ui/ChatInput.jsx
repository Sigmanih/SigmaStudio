import React, { useState } from 'react';
import { Send, Paperclip, RefreshCw, StopCircle, Mic, MicOff, AudioLines, Volume2, VolumeX, Sliders, Square, ChevronDown } from 'lucide-react';
import { setVoiceConfig as saveVoiceConfigToSpeechEngine, getVoiceConfig } from '../audioSpeech';
import ModelSelector from '../ModelSelector';

export default function ChatInput({
  input, setInput, loading, refs, providerColors, currentRouting,
  autoScroll, setAutoScroll,
  mcpAutoApprove, setMcpAutoApprove,
  speakerEnabled, setSpeakerEnabled,
  isRecording, onToggleRecording,
  smartMicState = 'off', onToggleSmartMic,
  loopMaxIterations, setLoopMaxIterations, loopActive,
  onSend, onStop, onOpenFilePicker, attachedFiles,
  // Model Selector props
  selectedModel, availableModels, loadingModels,
  showModelDropdown, onToggleModelDropdown, onSelectModel,
  providerConfigs, modelBtnRef,
  favoriteModel, favoriteModels, onSetFavoriteModel, onOpenConfig,
  // Manifesto / Role Selector props
  activeManifesto, manifestos,
  showManifestoDropdown, setShowManifestoDropdown, onSelectManifesto,
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

  const effectiveFavs = Array.isArray(favoriteModels) && favoriteModels.length > 0 
    ? favoriteModels 
    : (favoriteModel ? [favoriteModel] : []);

  return (
    <div className="chat-input-area">
      {/* Modern Extended Model & Role Selection Strip */}
      <div className="chat-input-controls-strip">
        <div className="chat-input-model-role-group">
          {/* 1. Extended Model Selector with explicit Label */}
          <div className="chat-control-field">
            <span className="chat-control-label">Modello:</span>
            <ModelSelector
              modelBtnRef={modelBtnRef}
              effectiveModelName={selectedModel}
              showDropdown={showModelDropdown}
              models={availableModels}
              selectedModel={selectedModel}
              loadingModels={loadingModels}
              providerConfigs={providerConfigs}
              onToggle={onToggleModelDropdown}
              onSelect={onSelectModel}
              onOpenConfig={onOpenConfig}
              favoriteModel={favoriteModel}
              favoriteModels={effectiveFavs}
              onSetFavorite={onSetFavoriteModel}
            />
          </div>

          {/* 2. Extended Role / Manifesto Selector with explicit Label */}
          <div className="chat-control-field">
            <span className="chat-control-label">Ruolo:</span>
            <div className="manifesto-selector-wrapper" style={{ position: 'relative' }}>
              <button
                type="button"
                className={`manifesto-selector-btn ${!activeManifesto?.name ? 'no-manifesto' : ''}`}
                onClick={(e) => { e.stopPropagation(); setShowManifestoDropdown && setShowManifestoDropdown(!showManifestoDropdown); }}
                title="Seleziona il Ruolo / Manifesto dell'Agente per la conversazione"
              >
                <span className="manifesto-icon">{activeManifesto?.icon || '📋'}</span>
                <div className="manifesto-info">
                  <span className="manifesto-name">{activeManifesto?.name || 'Sigma Assistant'}</span>
                  {activeManifesto?.role && (
                    <span className="manifesto-role-preview">{activeManifesto.role}</span>
                  )}
                </div>
                <ChevronDown size={11} className={`manifesto-chevron ${showManifestoDropdown ? 'open' : ''}`} />
              </button>

              {showManifestoDropdown && (
                <div className="model-selector-popover manifesto-popover" style={{ left: 0, transform: 'none', minWidth: '280px', maxHeight: '340px', overflowY: 'auto', zIndex: 2100 }}>
                  {(!manifestos || manifestos.length === 0) && (
                    <div className="model-selector-option disabled" style={{ padding: '8px 12px', fontSize: '0.74rem', color: '#8b8fa3' }}>
                      Nessun manifesto installato
                    </div>
                  )}
                  {(manifestos || []).map(m => (
                    <div
                      key={m.path || m.name}
                      className={`model-selector-option ${activeManifesto?.name === m.name ? 'selected' : ''}`}
                      onClick={(e) => { e.stopPropagation(); onSelectManifesto && onSelectManifesto(m); }}
                      style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '8px 12px', gap: '2px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 800, fontSize: '0.76rem', color: activeManifesto?.name === m.name ? '#00d2ff' : '#f1f5f9' }}>
                          {m.icon || '📋'} {m.name}
                        </span>
                        {activeManifesto?.name === m.name && <span style={{ fontSize: '0.74rem', color: '#10b981', fontWeight: 800 }}>✓</span>}
                      </div>
                      {m.role && (
                        <span style={{ fontSize: '0.64rem', color: 'var(--text-muted, #8b8fa3)', paddingLeft: '18px', lineHeight: 1.3 }}>
                          {m.role}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Group: Utility Toggles & Speaker Controls */}
        <div className="chat-input-utilities-group">
          <label className="chat-scroll-toggle" title="Auto-scroll verso l'ultimo messaggio inviato o generato">
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
              onChange={e => setMcpAutoApprove?.(e.target.checked)}
            />
            <span>{mcpAutoApprove ? '⚡' : '🛡️'} Auto Approve</span>
          </label>
          {setSpeakerEnabled !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', position: 'relative' }}>
              <label 
                className={`chat-speaker-toggle ${speakerEnabled ? 'active' : ''}`} 
                title={speakerEnabled ? 'Speaker Agente: ON (Voce attiva - Clicca per disattivare)' : 'Speaker Agente: OFF (Clicca per attivare la lettura vocale TTS)'}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '28px',
                  height: '24px',
                  color: speakerEnabled ? '#00d2ff' : '#8b8fa3',
                  background: speakerEnabled ? 'rgba(0, 210, 255, 0.16)' : 'rgba(255, 255, 255, 0.04)',
                  border: speakerEnabled ? '1px solid rgba(0, 210, 255, 0.45)' : '1px solid rgba(255, 255, 255, 0.08)',
                  boxShadow: speakerEnabled ? '0 0 10px rgba(0, 210, 255, 0.35)' : 'none',
                  borderRadius: '7px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <input 
                  type="checkbox" 
                  checked={speakerEnabled} 
                  onChange={e => setSpeakerEnabled(e.target.checked)} 
                  style={{ display: 'none' }}
                />
                {speakerEnabled ? <Volume2 size={13} style={{ color: '#00d2ff' }} /> : <VolumeX size={13} style={{ color: '#64748b' }} />}
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
        {(onToggleSmartMic || onToggleRecording) && (
          <button
            className={`chat-attach-inline-btn ${smartMicState !== 'off' || isRecording ? 'recording' : ''}`}
            onClick={onToggleSmartMic || onToggleRecording}
            title={
              smartMicState === 'listening'
                ? '🎤 Ti sto ascoltando... Parla adesso (invio automatico al termine)'
                : smartMicState === 'waiting'
                ? '✨ Microfono in ascolto: pronuncia "Sigma" ed inizia a fare la tua domanda'
                : 'Attiva microfono vocale (risponde ed ascolta pronunciando "Sigma")'
            }
            style={{
              color: smartMicState === 'listening' ? '#22c55e'
                : smartMicState === 'waiting' ? '#00d2ff'
                : 'var(--text-muted, #8b8fa3)',
              background: smartMicState === 'listening' ? 'rgba(34, 197, 94, 0.18)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.15)'
                : 'transparent',
              borderColor: smartMicState === 'listening' ? 'rgba(34, 197, 94, 0.5)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.4)'
                : 'transparent',
              boxShadow: smartMicState === 'listening' ? '0 0 12px rgba(34, 197, 94, 0.4)'
                : smartMicState === 'waiting' ? '0 0 12px rgba(0, 210, 255, 0.35)'
                : 'none',
              animation: smartMicState === 'listening' ? 'pulseMic 1.2s infinite' : 'none'
            }}
          >
            {smartMicState === 'listening' || smartMicState === 'waiting' || isRecording ? (
              <Mic size={15} />
            ) : (
              <MicOff size={15} />
            )}
          </button>
        )}
        <button className="chat-attach-inline-btn" onClick={onOpenFilePicker} title="Allega file">
          <Paperclip size={14} />
          {attachedFiles.length > 0 && <span className="chat-attach-count">{attachedFiles.length}</span>}
        </button>
        {loading ? (
          <button 
            className="chat-send-btn stop" 
            onClick={(e) => { e.preventDefault(); onStop && onStop(e); }} 
            title="Ferma task (puoi sempre riprenderlo)"
            style={{
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              borderColor: '#b91c1c',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(239, 68, 68, 0.4)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Square size={14} fill="#ffffff" />
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