import React from 'react';
import { Bot, User, Terminal, FileText } from 'lucide-react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import { useApp } from '../../contexts/AppContext';
import 'katex/dist/katex.min.css';

// ==============================================================================
// AGENT MESSAGE v5.0 — Header inside bubble
// Avatar 64px + ruolo in header con bg scuro, bubble full-width
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
import { useState } from 'react';

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
  const app = useApp();
  const openTab = app ? app.openTab : null;
  const [rolledBacks, setRolledBacks] = useState({});
  const [expandedDiffs, setExpandedDiffs] = useState({});
  const toggleDiff = (key) => {
    setExpandedDiffs(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleRollback = async (backupId) => {
    if (!window.confirm("Sei sicuro di voler annullare questa modifica e ripristinare il file allo stato precedente?")) {
      return;
    }
    try {
      const res = await fetch('/api/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backup_id: backupId })
      });
      const data = await res.json();
      if (data.success) {
        localStorage.setItem(`sigma_rolled_back_${backupId}`, 'true');
        setRolledBacks(prev => ({ ...prev, [backupId]: true }));
        alert(data.message || 'Ripristino completato con successo!');
      } else {
        alert('Errore di ripristino: ' + (data.error || 'Errore sconosciuto'));
      }
    } catch (e) {
      alert('Errore di connessione: ' + e.message);
    }
  };

  const handleFileClick = (path) => {
    if (!path || !openTab) return;
    const filename = path.split('/').pop() || path;
    const pathLower = path.toLowerCase();
    let type = 'teoria';
    if (pathLower.includes('/test/')) type = 'test';
    else if (pathLower.includes('/viz/')) type = 'viz';
    else if (pathLower.includes('/docs/')) {
      type = path.split('/').pop()?.toUpperCase().startsWith('WHITEPAPER_') ? 'whitepaper' : 'docs';
    }
    else if (pathLower.includes('/teoria/')) type = 'teoria';
    openTab({ path, filename }, type);
  };

  const messages = groupedMessages || (msg ? [msg] : []);
  if (messages.length === 0) return null;

  const first = messages[0];
  const isUser = first.role === 'user';
  const isSystem = first.role === 'system';
  const agentId = first.agent_id || first.agentId;
  const agentStyle = agentId ? getAgentStyle(agentId) : null;
  const isOrchestrated = first.is_orchestrated;
  const isLoading = standaloneLoading || first.loading;
  const isGrouped = messages.length > 1;

  const avatarSrc = agentId ? agentStyle.image : (first.agentImage || '/images/default.png');
  const avatarBg = agentId ? agentStyle.bg : 'var(--primary)';
  const roleName = isUser
    ? 'Tu'
    : (agentId ? (first.agentRole || first.agent_name || agentId) : (first.agentRole || 'AI'));

  const modelName = isUser ? '' : (first.agentName || effectiveModelName || 'AI');

  if (isLoading && !first.content && !first.thinking && messages.length === 1) {
    return (
      <div className={`chat-message chat-assistant ${isGrouped ? 'chat-message-grouped' : ''}`}>
        <div className="chat-bubble">
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
            {modelName && <div className="chat-msg-model">· {modelName}</div>}
          </div>
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
      {/* Bubble contenente header + contenuto */}
      <div className="chat-bubble">
        {/* Header inside bubble */}
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
          {modelName && <div className="chat-msg-model">· {modelName}</div>}
          {isOrchestrated && <span className="chat-msg-orchestrated" title="Assegnato dall'Orchestrator">🎯</span>}
          <div className="chat-msg-header-spacer" />
          <div className="chat-msg-time">{formatTimestamp(first.timestamp)}</div>
          {onDeleteMessage && (
            <button className="chat-msg-delete-btn" title="Elimina" onClick={() => onDeleteMessage(msgIndex)}>✕</button>
          )}
        </div>

        {/* Active agent role banner */}
        {!isUser && !isSystem && (agentId || first.agentRole) && (
          <div className="chat-msg-agent-badge" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: 'rgba(255,255,255,0.02)',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            fontSize: '0.72rem',
            color: '#8b8fa3'
          }}>
            <span style={{ fontSize: '1rem' }}>{agentStyle?.icon || '🤖'}</span>
            <span>Ruolo attivo: <strong style={{ color: 'var(--primary)' }}>{first.agentRole || agentStyle?.short || roleName}</strong></span>
          </div>
        )}

        {/* Content area */}
        <div className="chat-msg-content">
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
                        onClick={e => {
                          const link = e.target.closest('.chat-file-link');
                          if (link) {
                            e.preventDefault();
                            const path = link.getAttribute('data-path') || link.dataset.path;
                            handleFileClick(path);
                          }
                        }}
                        dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(m.thinking) }}
                      />
                    )}
                  </div>
                )}

                {/* Content */}
                {m.isAction ? (
                  <div className="chat-actions-log" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {m.actions_log && m.actions_log.length > 0 ? (
                      m.actions_log.map((action, actionIdx) => {
                        const isRollbackable = action.success && action.backup_id;
                        const hasBeenRolledBack = isRollbackable && (rolledBacks[action.backup_id] || localStorage.getItem(`sigma_rolled_back_${action.backup_id}`) === 'true');
                        const diffKey = `${mid}-${actionIdx}`;
                        const isDiffExpanded = expandedDiffs[diffKey];
                        const hasDiff = !!action.diff;
                        return (
                          <div key={actionIdx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <div className="action-log-item" style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '6px 8px',
                              background: 'rgba(255,255,255,0.02)',
                              border: '1px solid rgba(255,255,255,0.04)',
                              borderRadius: '6px',
                              fontSize: '0.75rem'
                            }}>
                              <div className="action-log-item-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                                <span>{action.success ? '✅' : '❌'}</span>
                                <span style={{ fontWeight: '600', color: action.success ? 'var(--primary)' : 'var(--error)', flexShrink: 0 }}>
                                  {action.type}
                                </span>
                                <span 
                                  style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', cursor: action.path ? 'pointer' : 'default' }}
                                  title={action.path || ''}
                                  onClick={() => action.path && handleFileClick(action.path)}
                                >
                                  {action.message || action.error || ''}
                                </span>
                              </div>
                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
                                {action.path && (action.path.toLowerCase().includes('/viz/') || action.path.toLowerCase().endsWith('.html')) && (
                                  <button
                                    onClick={() => handleFileClick(action.path)}
                                    style={{
                                      background: 'rgba(57,185,80,0.15)',
                                      border: '1px solid rgba(57,185,80,0.3)',
                                      color: '#3fb950',
                                      fontSize: '0.65rem',
                                      padding: '2px 8px',
                                      borderRadius: '4px',
                                      cursor: 'pointer',
                                      transition: 'all 0.15s ease'
                                    }}
                                    title="Apri l'anteprima interattiva nel workspace"
                                  >
                                    Anteprima 👁️
                                  </button>
                                )}
                                {hasDiff && (
                                  <button
                                    onClick={() => toggleDiff(diffKey)}
                                    style={{
                                      background: 'rgba(0,210,255,0.1)',
                                      border: '1px solid rgba(0,210,255,0.25)',
                                      color: 'var(--primary)',
                                      fontSize: '0.65rem',
                                      padding: '2px 8px',
                                      borderRadius: '4px',
                                      cursor: 'pointer',
                                      transition: 'all 0.15s ease'
                                    }}
                                  >
                                    {isDiffExpanded ? 'Nascondi Modifiche' : 'Visualizza Modifiche'}
                                  </button>
                                )}
                                {isRollbackable && (
                                  <button
                                    onClick={() => handleRollback(action.backup_id)}
                                    disabled={hasBeenRolledBack}
                                    style={{
                                      background: hasBeenRolledBack ? 'transparent' : 'rgba(255,85,85,0.15)',
                                      border: hasBeenRolledBack ? 'none' : '1px solid rgba(255,85,85,0.3)',
                                      color: hasBeenRolledBack ? '#3fb950' : '#ff5555',
                                      fontSize: '0.65rem',
                                      padding: '2px 8px',
                                      borderRadius: '4px',
                                      cursor: hasBeenRolledBack ? 'default' : 'pointer',
                                      transition: 'all 0.15s ease'
                                    }}
                                  >
                                    {hasBeenRolledBack ? 'Annullato ✓' : 'Annulla Modifica'}
                                  </button>
                                )}
                              </div>
                            </div>
                            
                            {hasDiff && isDiffExpanded && (
                              <div className="action-diff-container" style={{
                                background: '#090b10',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: '6px',
                                padding: '8px 10px',
                                fontFamily: 'Consolas, Monaco, monospace',
                                fontSize: '0.7rem',
                                lineHeight: '1.25rem',
                                overflowX: 'auto',
                                whiteSpace: 'pre',
                                color: '#adbac7',
                                marginTop: '2px',
                                maxHeight: '350px',
                                boxShadow: 'inset 0 0 10px rgba(0,0,0,0.5)'
                              }}>
                                {action.diff.split('\n').map((line, lineIdx) => {
                                  let lineStyle = { padding: '2px 4px', borderRadius: '2px', display: 'block' };
                                  if (line.startsWith('+') && !line.startsWith('+++')) {
                                    lineStyle.background = 'rgba(46, 160, 67, 0.15)';
                                    lineStyle.color = '#3fb950';
                                  } else if (line.startsWith('-') && !line.startsWith('---')) {
                                    lineStyle.background = 'rgba(248, 81, 73, 0.15)';
                                    lineStyle.color = '#f85149';
                                  } else if (line.startsWith('@@')) {
                                    lineStyle.color = '#79c0ff';
                                    lineStyle.background = 'rgba(121, 192, 255, 0.05)';
                                    lineStyle.fontWeight = 'bold';
                                  }
                                  return (
                                    <span key={lineIdx} style={lineStyle}>
                                      {line}
                                    </span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      (m.content || '').split('\n').map((l, j) => (
                        <div key={j} className="action-line">{l}</div>
                      ))
                    )}
                  </div>
                ) : m.content ? (
                  <div
                    className="chat-content chat-md"
                    onClick={e => {
                      const link = e.target.closest('.chat-file-link');
                      if (link) {
                        e.preventDefault();
                        const path = link.getAttribute('data-path') || link.dataset.path;
                        handleFileClick(path);
                      }
                    }}
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
    </div>
  );
}