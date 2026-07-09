import React from 'react';
import { Bot, User, Terminal, FileText, CheckCircle, XCircle, Loader } from 'lucide-react';

// ==============================================================================
// AGENT MESSAGE — Bolla messaggio con badge agente colorato
// Visualizza messaggi con badge agente, icona specializzazione e bordo colorato
// ==============================================================================

const AGENT_COLORS = {
  agente0: { bg: '#7c5bf0', color: '#ffffff', icon: '🏗️', short: 'Arch' },
  math1: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math' },
  code_architect: { bg: '#00d2ff', color: '#0e1016', icon: '⚙️', short: 'Code' },
};

function getAgentStyle(agentId) {
  return AGENT_COLORS[agentId] || { bg: '#8b8fa3', color: '#0e1016', icon: '🤖', short: 'AI' };
}

export default function AgentMessage({ msg, msgId, expandedThinking, onToggleThinking, effectiveModelName, onDeleteMessage, msgIndex }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAction = msg.isAction;
  const agentId = msg.agent_id;
  const agentStyle = agentId ? getAgentStyle(agentId) : null;
  const isOrchestrated = msg.is_orchestrated;
  const isError = msg.error;

  return (
    <div
      className={`chat-message ${isUser ? 'chat-user' : isSystem ? 'chat-system' : 'chat-assistant'} ${agentId ? 'chat-agent-message' : ''}`}
      style={agentId ? { borderLeft: `3px solid ${agentStyle.bg}`, paddingLeft: '12px' } : {}}
    >
      <div className="chat-avatar">
        {isUser ? <User size={14} /> : isSystem ? <Terminal size={14} /> : agentId ? (
          <span style={{ fontSize: '16px' }}>{agentStyle.icon}</span>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
          </svg>
        )}
      </div>
      <div className="chat-bubble">
        {/* Agent Badge */}
        {agentId && (
          <div className="chat-agent-badge" style={{ backgroundColor: agentStyle.bg, color: agentStyle.color }}>
            <span className="chat-agent-icon">{agentStyle.icon}</span>
            <span className="chat-agent-name">{msg.agent_name || agentId}</span>
            {isOrchestrated && <span className="chat-agent-orchestrated" title="Assegnato dall'Orchestrator">🎯</span>}
          </div>
        )}

        {/* User attachments */}
        {isUser && msg.attachments?.length > 0 && (
          <div className="chat-message-attachments">
            {msg.attachments.map(p => (
              <span key={p} className="chat-attachment-chip">
                <FileText size={10} /> {p.split('/').pop()}
              </span>
            ))}
          </div>
        )}

        {/* Native model thinking */}
        {!isUser && !isSystem && msg.thinking && (
          <div className={`chat-thinking ${msg.streamingThinking ? 'chat-thinking-streaming' : ''}`}>
            <button className="chat-thinking-toggle" onClick={() => onToggleThinking(msgId)}>
              <span>
                🧠 {msg.streamingThinking
                  ? <span className="chat-thinking-live"><span className="thinking-pulse"></span> Ragionando...</span>
                  : (expandedThinking[msgId] ? 'Nascondi ragionamento' : 'Mostra ragionamento')
                }
              </span>
            </button>
            {(msg.streamingThinking || expandedThinking[msgId]) && (
              <div className="chat-thinking-content">{msg.thinking}</div>
            )}
          </div>
        )}

        {/* Content */}
        {isAction ? (
          <div className="chat-actions-log">
            {msg.content.split('\n').map((l, j) => (
              <div key={j} className="action-line">{l}</div>
            ))}
          </div>
        ) : (
          <div className="chat-content">{msg.content}</div>
        )}

        {/* Error */}
        {isError && <div className="chat-error">⚠️ {msg.error}</div>}

        {/* Timestamp & agent */}
        <div className="chat-timestamp">
          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
          {!isSystem && (
            <span className="chat-message-agent">
              {' · '}{agentId ? agentStyle.short : (msg.agentName || effectiveModelName || 'AI')}
            </span>
          )}
        </div>
      </div>
      {onDeleteMessage && (
        <button className="chat-msg-delete-btn" title="Elimina" onClick={() => onDeleteMessage(msgIndex)}>✕</button>
      )}
    </div>
  );
}