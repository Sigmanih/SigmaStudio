import React from 'react';
import { Settings, MessageSquare, Plus, Download } from 'lucide-react';
import ThinkingOrb from '../../common/ThinkingOrb';

export default function ChatHeader({
  isDragging, onStartDrag,
  onOpenConfig, onClose, isPanel = false, contextStats, onCopyAll,
  onNewSession, onExportPdf, agentState = 'idle'
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
        minHeight: '38px',
        margin: 0,
        boxSizing: 'border-box'
      }}
    >
      <div className="chat-header-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <div style={{
          width: '22px', height: '22px', borderRadius: '6px',
          background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#00d2ff'
        }}>
          <MessageSquare size={12} />
        </div>
        <span className="chat-header-title" style={{ fontSize: '0.80rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '0.2px' }}>
          Chat AI
        </span>

        {/* Ambient Thinking Orb */}
        <ThinkingOrb state={agentState} size={18} showLabel={agentState !== 'idle'} />

        {/* Tastino laterale Nuova Conversazione */}
        {onNewSession && (
          <button
            className="chat-header-new-btn"
            onClick={(e) => { e.stopPropagation(); onNewSession(); }}
            title="Avvia una nuova conversazione"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: '6px',
              background: 'rgba(0, 210, 255, 0.12)',
              border: '1px solid rgba(0, 210, 255, 0.3)',
              color: '#00d2ff',
              fontSize: '0.68rem',
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            <Plus size={11} />
            <span>Nuova Conversazione</span>
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
              borderRadius: '6px',
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
                width: '54px',
                height: '6px',
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

      <div className="chat-header-right" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {onCopyAll && (
          <button
            className={`chat-header-btn chat-header-copy-btn ${copiedAll ? 'copied' : ''}`}
            onClick={handleCopyAll}
            title="Copia l'intera conversazione negli appunti"
            style={{
              gap: '4px',
              fontSize: '0.68rem',
              padding: '3px 8px',
              background: copiedAll ? 'rgba(74, 222, 128, 0.15)' : 'rgba(255,255,255,0.05)',
              color: copiedAll ? '#4ade80' : 'var(--text-muted, #8b8fa3)',
              border: copiedAll ? '1px solid rgba(74, 222, 128, 0.3)' : '1px solid rgba(255,255,255,0.08)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              transition: 'all 0.2s ease'
            }}
          >
            <span className="chat-header-copy-full">{copiedAll ? '✓ Copiato!' : '📋 Copia Tutto'}</span>
            <span className="chat-header-copy-short">{copiedAll ? '✓' : '📋'}</span>
          </button>
        )}
        {onExportPdf && (
          <button
            className="chat-header-btn chat-header-pdf-btn"
            onClick={(e) => {
              e.stopPropagation();
              onExportPdf();
            }}
            title="Salva l'intera conversazione in un documento PDF impaginato"
            style={{
              gap: '4px',
              fontSize: '0.68rem',
              padding: '3px 8px',
              background: 'rgba(239, 68, 68, 0.12)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.28)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              fontWeight: 600,
              transition: 'all 0.2s ease'
            }}
          >
            <Download size={12} />
            <span className="chat-header-pdf-full">Salva PDF</span>
            <span className="chat-header-pdf-short">PDF</span>
          </button>
        )}
        {onOpenConfig && (
          <button
            className="chat-header-btn"
            onClick={(e) => { e.stopPropagation(); onOpenConfig(); }}
            title="Impostazioni AI, Modello, Ruolo & Parametri"
            style={{
              padding: '4px 7px',
              borderRadius: '6px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.1)',
              cursor: 'pointer',
              color: '#00d2ff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Settings size={13} />
          </button>
        )}
        {onClose && (
          <button
            className="chat-header-btn"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            title="Riduci in basso nel dock"
            style={{ padding: '4px 6px', borderRadius: '6px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer', color: '#8b8fa3' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14" />
            </svg>
          </button>
        )}
        {onClose && (
          <button
            className="chat-close-btn"
            onClick={(e) => { e.stopPropagation(); onClose(); }}
            title="Chiudi"
            style={{ padding: '4px 6px', borderRadius: '6px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', cursor: 'pointer', color: '#ef4444', fontWeight: 700 }}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}