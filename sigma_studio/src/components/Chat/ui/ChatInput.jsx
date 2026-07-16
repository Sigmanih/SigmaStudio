import React from 'react';
import { Send, Paperclip, RefreshCw, StopCircle } from 'lucide-react';

export default function ChatInput({
  input, setInput, loading, selectedModel, refs, providerColors, currentRouting,
  webSearch, setWebSearch, autoScroll, setAutoScroll,
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
        <label className="chat-websearch-toggle" title="Cerca su Internet">
          <input type="checkbox" checked={webSearch} onChange={e => setWebSearch(e.target.checked)} />
          <span>🔍 Web Search</span>
        </label>
        <label className="chat-scroll-toggle" title="Auto-scroll">
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
          <span>📜 Auto Scroll</span>
        </label>
      </div>
      <div className="chat-input-row">
        <textarea
          ref={refs.input}
          className="chat-input"
          placeholder={`Chiedi qualcosa a ${selectedModel}...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          rows={1}
          disabled={loading}
        />
        <button className="chat-attach-inline-btn" onClick={onOpenFilePicker} title="Allega file">
          <Paperclip size={14} />
          {attachedFiles.length > 0 && <span className="chat-attach-count">{attachedFiles.length}</span>}
        </button>
        {loading ? (
          <button className="chat-send-btn stop" onClick={onStop} title="Ferma esecuzione">
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