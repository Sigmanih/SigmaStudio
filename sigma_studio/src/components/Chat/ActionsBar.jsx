import React, { useState } from 'react';

// ==============================================================================
// ACTIONS BAR — 4 modalità operative ottimizzate + descrizione
// 
// Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
// Le notifiche vengono generate AUTOMATICAMENTE dal backend per ogni azione.
// ==============================================================================

const MODES = [
  {
    key: 'chat',
    icon: '🗨️',
    label: 'Chat',
    desc: 'Parla con l\'AI: chiedi informazioni, crea file, modifica codice. Il sistema decide automaticamente se rispondere in chat o salvare file.',
  },
  {
    key: 'plan',
    icon: '📋',
    label: 'Pianifica',
    desc: 'L\'IA analizza un obiettivo e crea task nella Roadmap. Ogni task riceve una notifica di creazione.',
  },
];

export default function ActionsBar({
  activeMode, onSetMode,
  availableTasks, onExecuteTask,
  executingAll, onExecuteAll,
  taskDone, taskTotal, taskProgress, maxTaskIterations,
  contextStats, onOpenQuickConfig, showQuickConfig,
}) {
  const activeModeData = MODES.find(m => m.key === activeMode) || MODES[0];

  return (
    <div className="chat-actions-bar">
      <div className="chat-modes-group">
        {MODES.map(m => (
          <button
            key={m.key}
            className={`chat-mode-btn ${activeMode === m.key ? 'active' : ''}`}
            onClick={() => onSetMode(m.key)}
            title={m.desc}
          >
            <span className="chat-mode-icon">{m.icon}</span>
            <span className="chat-mode-label">{m.label}</span>
          </button>
        ))}
      </div>

      <div className="chat-actions-right">
        {contextStats && (
          <div
            className="context-gauge-pill"
            onClick={(e) => { e.stopPropagation(); onOpenQuickConfig(); }}
            title={`Finestra di Contesto: ${contextStats.usedTokens?.toLocaleString() || 0} / ${contextStats.numCtx?.toLocaleString() || 32768} Token (${contextStats.pct || 0}% in uso)\n• Conversazione: ~${contextStats.messagesTokens || 0} token\n• Allegati: ~${contextStats.attachedTokens || 0} token\n• Sistema: ~${contextStats.systemTokens || 1500} token`}
          >
            <div className="context-gauge-bar-outer">
              <div
                className="context-gauge-bar-inner"
                style={{
                  width: `${contextStats.pct || 0}%`,
                  backgroundColor: (contextStats.pct || 0) > 85 ? '#ef4444' : (contextStats.pct || 0) > 60 ? '#f59e0b' : '#00f2fe'
                }}
              />
            </div>
            <span className="context-gauge-text">
              {contextStats.usedTokens >= 1000 ? `${(contextStats.usedTokens / 1000).toFixed(1)}K` : contextStats.usedTokens} / {contextStats.numCtx >= 1000 ? `${Math.round(contextStats.numCtx / 1000)}K` : contextStats.numCtx}
            </span>
            <span className="context-gauge-text-short">
              {contextStats.pct || 0}% ctx
            </span>
          </div>
        )}
        <button
          className={`chat-header-btn ${showQuickConfig ? 'active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onOpenQuickConfig(); }}
          title="Impostazioni di interazione e parametri modello"
        >
          ⚙️
        </button>
      </div>
    </div>
  );
}