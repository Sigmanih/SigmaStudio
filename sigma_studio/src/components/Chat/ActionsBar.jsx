import React, { useState } from 'react';

// ==============================================================================
// ACTIONS BAR — 4 modalità operative ottimizzate + descrizione
// 
// Principio Sigma: "Una notifica non lasciata è un'azione mai avvenuta."
// Le notifiche vengono generate AUTOMATICAMENTE dal backend per ogni azione.
// ==============================================================================

const MODES = [
  {
    key: 'ask',
    icon: '💬',
    label: 'Chiedi',
    desc: 'Fai domande sul progetto. L\'IA risponde in chat senza modificare nulla. Nessuna notifica generata.',
  },
  {
    key: 'plan',
    icon: '📋',
    label: 'Pianifica',
    desc: 'L\'IA analizza un obiettivo e crea task nella Roadmap. Ogni task riceve una notifica di creazione.',
  },
  {
    key: 'execute',
    icon: '⚡',
    label: 'Esegui',
    desc: 'L\'IA crea, modifica o elimina file. Le notifiche vengono generate automaticamente per ogni azione.',
  },
  {
    key: 'complete',
    icon: '✅',
    label: 'Completa',
    desc: 'Esegue un task dalla Roadmap, modifica i file necessari e marca come completato. Notifiche automatiche.',
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

      {activeMode === 'complete' && (
        <div className="chat-tasks-actions">
          <select
            className="chat-task-select"
            value={selectedTaskIdx}
            onChange={(e) => setSelectedTaskIdx(e.target.value)}
          >
            <option value="" disabled>Seleziona task...</option>
            {availableTasks.map((t, i) => (
              <option key={t.id || t.titolo} value={i}>{t.titolo}</option>
            ))}
          </select>
          <button
            className="chat-tasks-btn"
            onClick={handleExecuteSelected}
            disabled={selectedTaskIdx === '' || executingAll}
            title="Esegui il task selezionato"
          >▶ Esegui</button>
          <button
            className="chat-tasks-btn"
            onClick={onExecuteAll}
            title={`Esegui tutti i task pendenti (max ${maxTaskIterations})`}
            disabled={executingAll}
          >{executingAll ? '⏳' : '▶▶'} Tutti</button>
          {executingAll && taskProgress > 0 && (
            <span className="chat-task-progress">{taskDone}/{taskTotal}</span>
          )}
        </div>
      )}
    </div>
  );
}