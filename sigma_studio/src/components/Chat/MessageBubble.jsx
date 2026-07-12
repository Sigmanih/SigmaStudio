import React from 'react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import 'katex/dist/katex.min.css';
import { Bot, User, Terminal, FileText, Loader } from 'lucide-react';

// ==============================================================================
// AGENT AVATAR MAP — Match agent names/IDs to images
// ==============================================================================
const AGENT_AVATARS = {
  sigma_architect: { image: '/images/agente0.png', name: 'Sigma AI Architect' },
  math1: { image: '/images/matematicoAi.png', name: 'Sigma Math Researcher' },
  code_architect: { image: '/images/programmatoreAi.png', name: 'Sigma Code Architect' },
};

function getAgentAvatar(agentName) {
  if (!agentName) return null;
  const lower = agentName.toLowerCase();
  // Try direct match by id
  if (AGENT_AVATARS[lower]) return AGENT_AVATARS[lower];
  // Try match by name keywords
  for (const [id, info] of Object.entries(AGENT_AVATARS)) {
    if (lower.includes(id) || lower.includes(info.name.toLowerCase())) {
      return info;
    }
  }
  return null;
}

// ==============================================================================
// MESSAGE BUBBLE — Full markdown rendering with KaTeX (v2.0)
// Utilizza renderMarkdownLatex per rendering unificato, nessuna manipolazione DOM
// ==============================================================================

export default function MessageBubble({ msg, isLast, onStop, onFileLinkClick }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const agentInfo = !isUser && !isSystem ? getAgentAvatar(msg.agentName || msg.manifesto_used) : null;

  const renderContent = (text) => {
    if (text == null) return '';
    return renderMarkdownLatex(text);
  };

  if (isSystem) {
    const isError = msg.error || msg.content?.startsWith('❌');
    const isAction = msg.isAction;
    return (
      <div className={`chat-message system-message ${isError ? 'error-message' : ''} ${isAction ? 'action-message' : ''}`}>
        <div className="system-icon">
          {isError ? <Terminal size={14} /> : isAction ? <FileText size={14} /> : <Loader size={14} />}
        </div>
        <span className="system-text" dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }} />
      </div>
    );
  }

  return (
    <div className={`chat-message ${isUser ? 'user-message' : 'ai-message'} ${agentInfo ? 'chat-agent-message' : ''}`}>
      <div className="message-avatar">
        {isUser ? <User size={16} /> : agentInfo ? (
          <img
            src={agentInfo.image}
            alt={agentInfo.name}
            className="message-agent-avatar-img"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
        ) : <Bot size={16} />}
      </div>
      <div className="message-content">
        <div className="message-header">
          <span className="message-role">{isUser ? 'Tu' : msg.agentName || 'Sigma AI'}</span>
          {msg.timestamp && <span className="message-time">{new Date(msg.timestamp).toLocaleTimeString()}</span>}
        </div>

        {/* Thinking section — collapsible */}
        {msg.thinking && (
          <div className="chat-thinking-section">
            <details>
              <summary className="chat-thinking-summary">
                <span className="thinking-icon">🧠</span> Mostra ragionamento
              </summary>
              <div
                className="chat-thinking-content"
                dangerouslySetInnerHTML={{ __html: renderContent(msg.thinking) }}
              />
            </details>
          </div>
        )}

        {/* Main message content — rendered with unified renderMarkdownLatex */}
        <div
          className="message-text chat-md"
          onClick={e => {
            const link = e.target.closest('.chat-file-link');
            if (link && onFileLinkClick) {
              e.preventDefault();
              onFileLinkClick(link.dataset.path);
            }
          }}
          dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }}
        />

        {msg.files && msg.files.length > 0 && (
          <div className="message-files">
            {msg.files.map((f, i) => (
              <div key={i} className="file-chip" onClick={() => onFileLinkClick && onFileLinkClick(f.path)}>
                <FileText size={14} />
                <span>{f.filename}</span>
              </div>
            ))}
          </div>
        )}

        {isLast && msg.loading && (
          <div className="message-typing">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </div>
        )}
      </div>
    </div>
  );
}