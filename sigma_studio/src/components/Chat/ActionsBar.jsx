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
}) {
  const activeModeData = MODES.find(m => m.key === activeMode) || MODES[0];
  const [selectedTaskIdx, setSelectedTaskIdx] = useState('');

  const handleExecuteSelected = () => {
    const idx = parseInt(selectedTaskIdx, 10);
    if (idx >= 0 && availableTasks[idx]) {
      onExecuteTask(availableTasks[idx]);
      setSelectedTaskIdx('');
    }
  };

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

      <div className="chat-mode-description">{activeModeData.desc}</div>
    </div>
  );
}