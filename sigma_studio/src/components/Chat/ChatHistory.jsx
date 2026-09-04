import React from 'react';
import { FileText, Plus, Bot, Trash2, ChevronDown, X, Copy } from 'lucide-react';
import { getSessionStats, formatSessionTime } from './chatStorage';

export default function ChatHistory({
  showHistory, onToggle,
  sessions, groupedSessions, sessionMessages,
  activeSessionId, onSwitchSession,
  editingSessionName, editNameValue, onEditNameChange, onFinishRename, onKeyDown,
  onStartRename, onDeleteSession, onNewSession, onDuplicateSession
}) {
  const handleItemSelect = (sessionId) => {
    onSwitchSession(sessionId);
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      onToggle();
    }
  };

  const handleNewSessionMobile = () => {
    onNewSession();
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      onToggle();
    }
  };

  const handleDuplicateMobile = () => {
    onDuplicateSession();
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      onToggle();
    }
  };

  return (
    <>
      {/* Mobile Backdrop overlay to close drawer by tapping outside */}
      {showHistory && (
        <div
          className="chat-history-backdrop"
          onClick={onToggle}
          title="Chiudi cronologia"
        />
      )}

      <button className="chat-collapse-btn" onClick={onToggle} title={showHistory ? 'Nascondi cronologia' : 'Mostra cronologia'}>
        <ChevronDown size={14} style={{ transform: showHistory ? 'rotate(270deg)' : 'rotate(90deg)', transition: 'transform 0.2s ease' }} />
      </button>
      <div className={`chat-history-panel ${showHistory ? '' : 'collapsed'}`}>
        <div className="chat-history-header">
          <div className="chat-history-header-left">
            <FileText size={13} />
            <span className="chat-history-title">Cronologia</span>
          </div>

          <div className="chat-history-header-actions">
            {showHistory && (
              <>
                <button 
                  className="chat-new-session-btn" 
                  onClick={handleDuplicateMobile} 
                  title="Duplica chat attiva corrente"
                >
                  Duplica
                </button>
                <button
                  className="chat-new-session-btn highlight"
                  onClick={handleNewSessionMobile}
                  title="Nuova conversazione"
                >
                  <Plus size={12} /> Nuova
                </button>
              </>
            )}
            <button
              className="chat-history-close-btn"
              onClick={onToggle}
              title="Chiudi cronologia"
              aria-label="Chiudi cronologia"
            >
              <X size={14} />
            </button>
          </div>
        </div>
        {showHistory && (
          <div className="chat-history-list">
            {sessions.length === 0 && <div className="chat-history-empty">Nessuna chat precedente</div>}
            {Object.entries(groupedSessions).map(([label, sesis]) => (
              <div key={label} className="chat-history-group">
                <div className="chat-history-group-label">{label}</div>
                {sesis.map(session => {
                  const { count: msgCount, lastTime } = getSessionStats(session, sessionMessages);
                  const timeStr = formatSessionTime(lastTime);
                  const modelName = session.model ? session.model.split('/').pop() : 'Default';

                  return (
                    <div
                      key={session.id}
                      className={`chat-history-item ${activeSessionId === session.id ? 'active' : ''}`}
                      onClick={() => handleItemSelect(session.id)}
                    >
                      <div className="chat-history-item-icon"><Bot size={12} /></div>
                      <div className="chat-history-item-content">
                        {editingSessionName === session.id ? (
                          <input className="chat-history-item-edit" value={editNameValue} onChange={e => onEditNameChange(e.target.value)} onBlur={() => onFinishRename(session.id)} onKeyDown={e => onKeyDown(e, session.id)} autoFocus onClick={e => e.stopPropagation()} />
                        ) : (
                          <span className="chat-history-item-name" onDoubleClick={e => onStartRename(e, session.id)} title={session.name}>{session.name}</span>
                        )}
                        <div className="chat-history-item-meta">
                          <span className="chat-history-item-meta-main" title={session.model || 'Modello default'}>
                            {modelName} · {msgCount} msg
                          </span>
                          {timeStr && (
                            <span className="chat-history-item-meta-time" title={`Ultimo messaggio: ${timeStr}`}>
                              {timeStr}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="chat-history-item-actions" style={{ display: 'flex', alignItems: 'center', gap: '3px', flexShrink: 0 }}>
                        {onDuplicateSession && (
                          <button 
                            type="button"
                            className="chat-history-item-duplicate" 
                            onClick={e => onDuplicateSession(e, session.id)} 
                            title="Duplica sessione"
                          >
                            <Copy size={11} />
                          </button>
                        )}
                        <button 
                          type="button"
                          className="chat-history-item-delete" 
                          onClick={e => onDeleteSession(e, session.id)} 
                          title="Elimina sessione"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}