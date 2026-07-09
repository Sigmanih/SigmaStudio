import React from 'react';
import { FileText, Plus, Bot, Trash2, ChevronDown } from 'lucide-react';

export default function ChatHistory({
  showHistory, onToggle,
  sessions, groupedSessions,
  activeSessionId, onSwitchSession,
  editingSessionName, editNameValue, onEditNameChange, onFinishRename, onKeyDown,
  onStartRename, onDeleteSession, onNewSession
}) {
  return (
    <>
      <button className="chat-collapse-btn" onClick={onToggle} title={showHistory ? 'Nascondi cronologia' : 'Mostra cronologia'}>
        <ChevronDown size={14} style={{ transform: showHistory ? 'rotate(270deg)' : 'rotate(90deg)', transition: 'transform 0.2s ease' }} />
      </button>
      <div className={`chat-history-panel ${showHistory ? '' : 'collapsed'}`}>
        <div className="chat-history-header">
          <span className="chat-history-title"><FileText size={12} /> Cronologia</span>
          {showHistory && <button className="chat-new-session-btn" onClick={onNewSession}><Plus size={12} /> Nuova</button>}
        </div>
        {showHistory && (
          <div className="chat-history-list">
            {sessions.length === 0 && <div className="chat-history-empty">Nessuna chat precedente</div>}
            {Object.entries(groupedSessions).map(([label, sesis]) => (
              <div key={label} className="chat-history-group">
                <div className="chat-history-group-label">{label}</div>
                {sesis.map(session => (
                  <div key={session.id} className={`chat-history-item ${activeSessionId === session.id ? 'active' : ''}`} onClick={() => onSwitchSession(session.id)}>
                    <div className="chat-history-item-icon"><Bot size={12} /></div>
                    <div className="chat-history-item-content">
                      {editingSessionName === session.id ? (
                        <input className="chat-history-item-edit" value={editNameValue} onChange={e => onEditNameChange(e.target.value)} onBlur={() => onFinishRename(session.id)} onKeyDown={e => onKeyDown(e, session.id)} autoFocus onClick={e => e.stopPropagation()} />
                      ) : (
                        <span className="chat-history-item-name" onDoubleClick={e => onStartRename(e, session.id)}>{session.name}</span>
                      )}
                      <span className="chat-history-item-meta">{session.model} · {session.messages?.length || 0} msg</span>
                    </div>
                    <button className="chat-history-item-delete" onClick={e => onDeleteSession(e, session.id)}><Trash2 size={10} /></button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}