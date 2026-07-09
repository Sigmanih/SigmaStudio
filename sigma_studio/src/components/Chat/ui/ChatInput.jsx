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
          <button className="chat-send-btn stop" onClick={onStop} title="Stop">
            <Send size={16} />
          </button>
        ) : (
          <>
            <button className="chat-send-btn" onClick={onSend} disabled={!input.trim()} title="Invia">
              <Send size={16} />
            </button>
            <div className="chat-loop-wrapper">
              <select
                className="chat-loop-max-select"
                value={loopMaxIterations}
                onChange={e => setLoopMaxIterations(parseInt(e.target.value))}
                disabled={loopActive}
              >
                <option value={1}>1x</option><option value={3}>3x</option>
                <option value={5}>5x</option><option value={10}>10x</option>
                <option value={25}>25x</option><option value={50}>50x</option>
                <option value={100}>100x</option>
              </select>
              <button
                className="chat-loop-btn"
                onClick={onSend}
                disabled={!input.trim() || loading || loopActive}
                title={`Esegui (max ${loopMaxIterations} iterazioni)`}
              >
                <RefreshCw size={14} />
                <span className="chat-loop-badge">{loopMaxIterations}</span>
              </button>
            </div>
          </>
        )}
      </div>
      {children}
    </div>
  );
}