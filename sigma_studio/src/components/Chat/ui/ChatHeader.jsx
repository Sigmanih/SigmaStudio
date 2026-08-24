import React from 'react';
import { Cpu, MessageSquare } from 'lucide-react';

export default function ChatHeader({
  isDragging, onStartDrag,
  onOpenConfig, onClose, isPanel = false, contextStats, onCopyAll,
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
        padding: '10px 14px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        background: 'rgba(10, 14, 26, 0.65)',
        backdropFilter: 'blur(10px)'
      }}
    >
      <div className="chat-header-left" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          width: '24px', height: '24px', borderRadius: '6px',
          background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#00d2ff'
        }}>
          <MessageSquare size={13} />
        </div>
        <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '0.2px' }}>
          Sigma Swarm Chat
        </span>
        {contextStats && typeof contextStats === 'object' && contextStats.usedTokens !== undefined && (
          <span style={{ fontSize: '0.66rem', color: '#8b8fa3', paddingLeft: '4px' }}>
            • {contextStats.usedTokens >= 1000 ? `${(contextStats.usedTokens / 1000).toFixed(1)}k` : contextStats.usedTokens} / {contextStats.numCtx >= 1000 ? `${Math.round(contextStats.numCtx / 1000)}k` : contextStats.numCtx} ctx
          </span>
        )}
      </div>

      <div className="chat-header-right" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {onCopyAll && (
          <button
            className={`chat-header-btn ${copiedAll ? 'copied' : ''}`}
            onClick={handleCopyAll}
            title="Copia l'intera conversazione negli appunti"
            style={{
              gap: '4px',
              fontSize: '0.72rem',
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
            {copiedAll ? '✓ Copiato!' : '📋 Copia Tutto'}
          </button>
        )}
        {onOpenConfig && (
          <button
            className="chat-header-btn"
            onClick={(e) => { e.stopPropagation(); onOpenConfig(); }}
            title="Configurazione AI & Modelli"
            style={{ padding: '4px 6px', borderRadius: '6px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer', color: '#8b8fa3' }}
          >
            <Cpu size={14} />
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