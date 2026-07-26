import React from 'react';
import { Send, Paperclip, RefreshCw, StopCircle, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';

export default function ChatInput({
  input, setInput, loading, selectedModel, refs, providerColors, currentRouting,
  webSearch, setWebSearch, autoScroll, setAutoScroll,
  speakerEnabled, setSpeakerEnabled,
  isRecording, onToggleRecording,
  loopMaxIterations, setLoopMaxIterations, loopActive,
  onSend, onStop, onOpenFilePicker, attachedFiles,
  children,
}) {
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
        {setSpeakerEnabled !== undefined && (
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
              marginLeft: 'auto'
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
        )}
      </div>
      <div className="chat-input-row">
        <textarea
          ref={refs.input}
          className="chat-input"
          placeholder={isRecording ? "🔴 Registrazione in corso... Parla adesso..." : `Chiedi qualcosa a ${selectedModel}...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          rows={1}
          disabled={loading}
          style={isRecording ? { borderColor: '#ff5555', background: 'rgba(255, 85, 85, 0.06)' } : {}}
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