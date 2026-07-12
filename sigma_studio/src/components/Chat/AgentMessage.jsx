import React from 'react';
import { Bot, User, Terminal, FileText } from 'lucide-react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import 'katex/dist/katex.min.css';

// ==============================================================================
// AGENT MESSAGE v4.0 — Modern Header Layout
// Avatar + ruolo/modello in header, contenuto full-width sotto
// ==============================================================================

const AGENT_COLORS = {
  sigma_architect: { bg: '#7c5bf0', color: '#ffffff', icon: '🏗️', short: 'Arch', image: '/images/agente0.png' },
  math1: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math', image: '/images/matematicoAi.png' },
  code_architect: { bg: '#00d2ff', color: '#0e1016', icon: '⚙️', short: 'Code', image: '/images/programmatoreAi.png' },
};

function getAgentStyle(agentId) {
  return AGENT_COLORS[agentId] || { bg: '#8b8fa3', color: '#0e1016', icon: '🤖', short: 'AI', image: '/images/default.png' };
}

function formatTimestamp(ts) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString(); } catch { return ''; }
}

// ==============================================================================
// Main AgentMessage Component
// ==============================================================================
export default function AgentMessage({
  msg,
  groupedMessages,
  msgId,
  expandedThinking,
  onToggleThinking,
  effectiveModelName,
  onDeleteMessage,
  msgIndex,
  loading: standaloneLoading,
}) {
  const messages = groupedMessages || (msg ? [msg] : []);
  if (messages.length === 0) return null;

  const first = messages[0];
  const isUser = first.role === 'user';
  const isSystem = first.role === 'system';
  const agentId = first.agent_id;
  const agentStyle = agentId ? getAgentStyle(agentId) : null;
  const isOrchestrated = first.is_orchestrated;
  const isLoading = standaloneLoading || first.loading;
  const isGrouped = messages.length > 1;

  // Agent image from message (frozen at creation) or fallback to agent style
  const avatarSrc = agentId ? agentStyle.image : (first.agentImage || '/images/default.png');
  const avatarBg = agentId ? agentStyle.bg : '#2a2d3e';
  const roleName = agentId
    ? (first.agent_name || agentId)
    : (first.agentRole || 'AI');

  const modelName = first.agentName || effectiveModelName || 'AI';

  if (isLoading && !first.content && !first.thinking && messages.length === 1) {
    return (
      <div className={`chat-message chat-assistant ${isGrouped ? 'chat-message-grouped' : ''}`}>
        <div className="chat-msg-header">
          <div className="chat-msg-avatar chat-msg-avatar-loading">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <div className="chat-msg-role">{roleName}</div>
          <div className="chat-msg-model">· {modelName}</div>
        </div>
        <div className="chat-bubble">
          <div className="chat-loading">
            <span className="chat-loading-cursor">●</span>
            <span>Sto pensando...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`chat-message ${isUser ? 'chat-user' : isSystem ? 'chat-system' : 'chat-assistant'} ${agentId ? 'chat-agent-message' : ''} ${isGrouped ? 'chat-message-grouped' : ''}`}
    >
      {/* Header: Avatar + Role + Model */}
      <div className="chat-msg-header">
        <div className="chat-msg-avatar" style={{ borderColor: avatarBg }}>
          <img
            src={avatarSrc}
            alt={roleName}
            className="chat-msg-avatar-img"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        </div>
        <div className="chat-msg-role">{roleName}</div>
        <div className="chat-msg-model">· {modelName}</div>
        {isOrchestrated && <span className="chat-msg-orchestrated" title="Assegnato dall'Orchestrator">🎯</span>}
        <div className="chat-msg-header-spacer" />
        <div className="chat-msg-time">{formatTimestamp(first.timestamp)}</div>
        {onDeleteMessage && !isGrouped && (
          <button className="chat-msg-del-btn" title="Elimina" onClick={() => onDeleteMessage(msgIndex)}>✕</button>
        )}
      </div>

      {/* Bubble content */}
      <div className="chat-bubble">
        {/* Attachments for user messages */}
        {isUser && first.attachments?.length > 0 && (
          <div className="chat-message-attachments">
            {first.attachments.map(p => (
              <span key={p} className="chat-attachment-chip">
                <FileText size={10} /> {p.split('/').pop()}
              </span>
            ))}
          </div>
        )}

        {/* Rendered messages (single or grouped) */}
        {messages.map((m, idx) => {
          const mid = msgId || `msg-${idx}`;
          const isLast = idx === messages.length - 1;
          return (
            <div key={idx} className={isGrouped && !isLast ? 'chat-msg-grouped-item chat-msg-grouped-border' : 'chat-msg-grouped-item'}>
              {/* Thinking toggle */}
              {!isUser && !isSystem && m.thinking && (
                <div className={`chat-thinking ${m.streamingThinking ? 'chat-thinking-streaming' : ''}`}>
                  <button className="chat-thinking-toggle" onClick={() => onToggleThinking(mid)}>
                    <span>
                      🧠 {m.streamingThinking
                        ? <span className="chat-thinking-live"><span className="thinking-pulse"></span> Ragionando...</span>
                        : (expandedThinking?.[mid] ? 'Nascondi ragionamento' : 'Mostra ragionamento')
                      }
                    </span>
                  </button>
                  {(m.streamingThinking || expandedThinking?.[mid]) && (
                    <div
                      className="chat-thinking-content chat-md"
                      dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(m.thinking) }}
                    />
                  )}
                </div>
              )}

              {/* Content */}
              {m.isAction ? (
                <div className="chat-actions-log">
                  {(m.content || '').split('\n').map((l, j) => (
                    <div key={j} className="action-line">{l}</div>
                  ))}
                </div>
              ) : m.content ? (
                <div
                  className="chat-content chat-md"
                  dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(m.content) }}
                />
              ) : null}

              {/* Error */}
              {m.error && <div className="chat-error">⚠️ {m.error}</div>}

              {/* Timestamp + model for grouped items */}
              {isGrouped && (
                <div className="chat-timestamp">
                  {formatTimestamp(m.timestamp)}
                  <span className="chat-message-agent">
                    {' · '}{m.agent_name || agentId || m.agentName || effectiveModelName || 'AI'}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}