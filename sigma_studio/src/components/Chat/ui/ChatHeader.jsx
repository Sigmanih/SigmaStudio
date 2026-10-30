import React from 'react';
import { Plus, Download, Copy, Check, Minus, X } from 'lucide-react';
import AgentPresence from './AgentPresence';

export default function ChatHeader({
  isDragging, onStartDrag,
  onOpenConfig, onClose, isPanel = false, contextStats, onCopyAll,
  onNewSession, onExportPdf, activity
}) {
  const [copiedAll, setCopiedAll] = React.useState(false);

  const handleCopyAll = (e) => {
    e.stopPropagation();
    if (onCopyAll) {
      onCopyAll();
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    }
  };

  return (
    <div 
      className="chat-header"
      onMouseDown={(e) => {
        if (!isPanel || !onStartDrag) return;
        if (e.target.closest('button')) {
          return;
        }
        onStartDrag(e);
      }}
      style={{ 
        cursor: isPanel && onStartDrag ? (isDragging ? 'grabbing' : 'grab') : 'default',
        userSelect: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        background: 'rgba(10, 14, 26, 0.75)',
        backdropFilter: 'blur(10px)',
        minHeight: '40px',
        margin: 0,
        boxSizing: 'border-box'
      }}
    >
      <div className="chat-header-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: '1 1 auto' }}>
        {/* Chi risponde e cosa sta facendo, al posto dell'etichetta fissa "Chat AI" */}
        <AgentPresence activity={activity} compact={isPanel} />

        {/* Tastino tondo Nuova Conversazione */}
        {onNewSession && (
          <button
            type="button"
            className="chat-header-circle-btn chat-header-new-btn"
            onClick={(e) => { e.stopPropagation(); onNewSession(); }}
            title="Nuova conversazione"
            aria-label="Nuova conversazione"
          >
            <Plus size={14} />
          </button>
        )}

        {contextStats && typeof contextStats === 'object' && contextStats.usedTokens !== undefined && (
          <div
            className="chat-header-context-gauge"
            onClick={onOpenConfig ? (e) => { e.stopPropagation(); onOpenConfig(); } : undefined}
            title={`Finestra di Contesto: ${(contextStats.usedTokens || 0).toLocaleString()} / ${(contextStats.numCtx || 32768).toLocaleString()} token (${contextStats.pct || 0}% in uso)\n• Conversazione: ~${contextStats.messagesTokens || 0} token\n• Allegati: ~${contextStats.attachedTokens || 0} token\n• Sistema: ~${contextStats.systemTokens || 1500} token${onOpenConfig ? '\n(Clicca per configurare)' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              cursor: onOpenConfig ? 'pointer' : 'default',
              userSelect: 'none',
              transition: 'all 0.15s ease'
            }}
          >
            <span className="chat-header-tokens" style={{ fontSize: '0.64rem', color: '#94a3b8', fontWeight: 600 }}>
              {contextStats.usedTokens >= 1000 ? `${(contextStats.usedTokens / 1000).toFixed(1)}k` : contextStats.usedTokens} / {contextStats.numCtx >= 1000 ? `${Math.round(contextStats.numCtx / 1000)}k` : contextStats.numCtx} ctx
            </span>

            {/* Barra a riempimento visiva del contesto occupato */}
            <div
              className="chat-header-gauge-track"
              style={{
                width: '46px',
                height: '5px',
                borderRadius: '999px',
                background: 'rgba(255, 255, 255, 0.10)',
                overflow: 'hidden',
                position: 'relative',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              <div
                className="chat-header-gauge-fill"
                style={{
                  height: '100%',
                  width: `${Math.min(100, Math.max(contextStats.pct > 0 ? 4 : 0, contextStats.pct || 0))}%`,
                  background: (contextStats.pct || 0) > 85 
                    ? 'linear-gradient(90deg, #f87171, #ef4444)' 
                    : (contextStats.pct || 0) > 60 
                    ? 'linear-gradient(90deg, #fbbf24, #f59e0b)' 
                    : 'linear-gradient(90deg, #38bdf8, #00d2ff)',
                  borderRadius: '999px',
                  boxShadow: (contextStats.pct || 0) > 85 
                    ? '0 0 6px rgba(239, 68, 68, 0.6)' 
                    : (contextStats.pct || 0) > 60 
                    ? '0 0 6px rgba(245, 158, 11, 0.6)' 
                    : '0 0 6px rgba(0, 210, 255, 0.5)',
                  transition: 'width 0.35s cubic-bezier(0.4, 0, 0.2, 1), background 0.3s ease'
                }}
              />
            </div>

            <span
              style={{
                fontSize: '0.62rem',
                fontWeight: 700,
                color: (contextStats.pct || 0) > 85 
                  ? '#ef4444' 
                  : (contextStats.pct || 0) > 60 
                  ? '#f59e0b' 
                  : '#38bdf8'
              }}
            >
              {contextStats.pct || 0}%
            </span>
          </div>
        )}
      </div>

      <div className="chat-header-right" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
        {onCopyAll && (
          <button
            type="button"
            className={`chat-header-circle-btn chat-header-copy-btn ${copiedAll ? 'copied' : ''}`}
            onClick={handleCopyAll}
            title={copiedAll ? "Copiato negli appunti!" : "Copia l'intera conversazione"}
            aria-label="Copia conversazione"
          >
            {copiedAll ? <Check size={13} /> : <Copy size={13} />}
          </button>
        )}
        {onExportPdf && (
          <button
            type="button"
            className="chat-header-circle-btn chat-header-pdf-btn"
            onClick={(e) => {
              e.stopPropagation();
              onExportPdf();
            }}
            title="Salva l'intera conversazione in PDF"
            aria-label="Salva PDF"
          >
            <Download size={13} />
          </button>
        )}
        {onClose && (
          <button
            type="button"
            className="chat-header-circle-btn chat-header-minimize-btn"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            title="Riduci pannello"
            aria-label="Riduci pannello"
          >
            <Minus size={13} />
          </button>
        )}
        {onClose && (
          <button
            type="button"
            className="chat-header-circle-btn chat-header-close-btn"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            title="Chiudi"
            aria-label="Chiudi"
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  );
}