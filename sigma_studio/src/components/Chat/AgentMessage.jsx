import React from 'react';
import { Bot, User, Terminal, FileText } from 'lucide-react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import 'katex/dist/katex.min.css';

// ==============================================================================
// AGENT MESSAGE — Premium Markdown + KaTeX rendering (v2.0)
// Utilizza renderMarkdownLatex per rendering unificato, nessuna manipolazione DOM
// ==============================================================================

const AGENT_COLORS = {
  agente0: { bg: '#7c5bf0', color: '#ffffff', icon: '🏗️', short: 'Arch' },
  math1: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math' },
  code_architect: { bg: '#00d2ff', color: '#0e1016', icon: '⚙️', short: 'Code' },
};

function getAgentStyle(agentId) {
  return AGENT_COLORS[agentId] || { bg: '#8b8fa3', color: '#0e1016', icon: '🤖', short: 'AI' };
}

export default function AgentMessage({ msg, msgId, expandedThinking, onToggleThinking, effectiveModelName, onDeleteMessage, msgIndex, loading: standaloneLoading }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAction = msg.isAction;
  const agentId = msg.agent_id;
  const agentStyle = agentId ? getAgentStyle(agentId) : null;
  const isOrchestrated = msg.is_orchestrated;
  const isError = msg.error;
  const isLoading = standaloneLoading || msg.loading;

  if (isLoading && !msg.content && !msg.thinking) {
    return (
      <div className="chat-message chat-assistant">
        <div className="chat-avatar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
          </svg>
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
        {agentId && (
          <div className="chat-agent-badge" style={{ backgroundColor: agentStyle.bg, color: agentStyle.color }}>
            <span className="chat-agent-icon">{agentStyle.icon}</span>
            <span className="chat-agent-name">{msg.agent_name || agentId}</span>
            {isOrchestrated && <span className="chat-agent-orchestrated" title="Assegnato dall'Orchestrator">🎯</span>}
          </div>
        )}

        {isUser && msg.attachments?.length > 0 && (
          <div className="chat-message-attachments">
            {msg.attachments.map(p => (
              <span key={p} className="chat-attachment-chip">
                <FileText size={10} /> {p.split('/').pop()}
              </span>
            ))}
          </div>
        )}

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
              <div
                className="chat-thinking-content chat-md"
                dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(msg.thinking) }}
              />
            )}
          </div>
        )}

        {isAction ? (
          <div className="chat-actions-log">
            {Array.isArray(msg.content)
              ? msg.content.map((l, j) => <div key={j} className="action-line">{String(l)}</div>)
              : (msg.content || '').split('\n').map((l, j) => (
                <div key={j} className="action-line">{l}</div>
              ))}
          </div>
        ) : (
          <div
            className="chat-content chat-md"
            dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(msg.content) }}
          />
        )}

        {isError && <div className="chat-error">⚠️ {msg.error}</div>}

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