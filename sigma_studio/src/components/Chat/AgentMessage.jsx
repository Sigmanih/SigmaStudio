import React from 'react';
import { Bot, User, Terminal, FileText, Zap, Play, Pause, RotateCcw, RotateCw, Square } from 'lucide-react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import McpToolStrip from './McpToolStrip';
import { useApp } from '../../contexts/AppContext';
import 'katex/dist/katex.min.css';

// ==============================================================================
// AGENT MESSAGE v5.0 — Header inside bubble + Audio Player Bar & Karaoke Highlight
// Avatar 64px + ruolo in header con bg scuro, bubble full-width
// ==============================================================================

const AGENT_COLORS = {
  sigma_architect: { bg: '#7c5bf0', color: '#ffffff', icon: '🏗️', short: 'Arch', name: 'Sigma Architect', image: '/images/agente0.png' },
  math_researcher: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math', name: 'Sigma Math Researcher', image: '/images/matematicoAi.png' },
  code_architect: { bg: '#00d2ff', color: '#0e1016', icon: '⚙️', short: 'Code', name: 'Sigma Code Architect', image: '/images/programmatoreAi.png' },
  viz_designer: { bg: '#ff79c6', color: '#ffffff', icon: '🎨', short: 'Viz', name: 'Sigma Viz Designer', image: '/images/default.png' },
  test_engineer: { bg: '#f1fa8c', color: '#0e1016', icon: '🧪', short: 'Test', name: 'Sigma Test Engineer', image: '/images/default.png' },
  proof_reviewer: { bg: '#ff5555', color: '#ffffff', icon: '🔍', short: 'Review', name: 'Sigma Proof Reviewer', image: '/images/default.png' },
  sigma_assistant: { bg: '#00f2fe', color: '#0e1016', icon: '🤖', short: 'Assist', name: 'Sigma Assistant', image: '/images/default.png' },
  sigma_admin: { bg: '#ffb86c', color: '#0e1016', icon: '⚡', short: 'Admin', name: 'Sigma Admin', image: '/images/agente0.png' },
  math1: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math', name: 'Sigma Math Researcher', image: '/images/matematicoAi.png' },
};

export function getAgentStyle(agentId) {
  if (!agentId) return { bg: '#00d2ff', color: '#0e1016', icon: '🤖', short: 'AI', name: 'AI', image: '/images/default.png' };
  const cleanId = agentId.toLowerCase().replace('-', '_');
  return AGENT_COLORS[cleanId] || { bg: '#8b8fa3', color: '#0e1016', icon: '🤖', short: 'AI', name: agentId.replace('_', ' '), image: '/images/default.png' };
}

function formatTimestamp(ts) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString(); } catch { return ''; }
}

function highlightCurrentWordInHtml(htmlContent, fullCleanText, charIndex, charLength) {
  if (!htmlContent || charIndex === undefined || charIndex < 0 || !fullCleanText) return htmlContent;

  let validCharIdx = Math.min(fullCleanText.length - 1, Math.max(0, charIndex));

  // If validCharIdx lands on whitespace/punctuation, look forward up to 15 chars for a word char
  if (!/[\p{L}\p{N}]/u.test(fullCleanText[validCharIdx])) {
    let forward = validCharIdx;
    while (forward < fullCleanText.length && !/[\p{L}\p{N}]/u.test(fullCleanText[forward])) {
      forward++;
    }
    if (forward < fullCleanText.length) {
      validCharIdx = forward;
    } else {
      let backward = validCharIdx;
      while (backward > 0 && !/[\p{L}\p{N}]/u.test(fullCleanText[backward])) {
        backward--;
      }
      validCharIdx = backward;
    }
  }

  if (!/[\p{L}\p{N}]/u.test(fullCleanText[validCharIdx])) return htmlContent;

  // Find exact word boundaries around validCharIdx in fullCleanText
  let start = validCharIdx;
  while (start > 0 && /[\p{L}\p{N}]/u.test(fullCleanText[start - 1])) {
    start--;
  }
  let end = validCharIdx;
  while (end < fullCleanText.length && /[\p{L}\p{N}]/u.test(fullCleanText[end])) {
    end++;
  }

  const activeWord = fullCleanText.slice(start, end).trim().replace(/[^\p{L}\p{N}]/gu, '');
  if (!activeWord || activeWord.length < 2) return htmlContent;

  const escapedWord = activeWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const textBefore = fullCleanText.slice(0, start);
  const targetOccurrence = (textBefore.match(new RegExp(`\\b${escapedWord}\\b`, 'gi')) || []).length;

  let currentOccurrence = 0;

  // Replace target occurrence inside HTML text nodes only (safe against tags)
  return htmlContent.replace(/(<[^>]+>)|([^<]+)/g, (match, tag, textNode) => {
    if (tag) return tag;
    if (!textNode) return match;

    return textNode.replace(new RegExp(`\\b${escapedWord}\\b`, 'gi'), (wordMatch) => {
      if (currentOccurrence === targetOccurrence) {
        currentOccurrence++;
        return `<mark class="speech-word-highlight">${wordMatch}</mark>`;
      }
      currentOccurrence++;
      return wordMatch;
    });
  });
}

// ==============================================================================
// Main AgentMessage Component
// ==============================================================================
import { useState, useEffect } from 'react';
import { 
  speakAgentMessage, 
  stopSpeech, 
  togglePauseSpeech, 
  seekSpeechRelative, 
  seekSpeechPercent, 
  subscribeSpeech, 
  subscribeSpeechProgress, 
  getSpeechProgress, 
  getActiveSpeechId,
  cleanTextForSpeech
} from './audioSpeech';

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
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [speechProgress, setSpeechProgress] = useState(() => getSpeechProgress());
  const [rolledBacks, setRolledBacks] = useState({});
  const [expandedDiffs, setExpandedDiffs] = useState({});
  const [loadingStep, setLoadingStep] = useState(0);
  const [copiedMsg, setCopiedMsg] = useState(false);

  const handleCopyMessage = (e) => {
    e.stopPropagation();
    const textToCopy = messages.map(m => m.content || m.thinking || '').filter(Boolean).join('\n\n');
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopiedMsg(true);
      setTimeout(() => setCopiedMsg(false), 2000);
    }
  };

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

  const getCleanPathStr = (p) => {
    if (!p) return '';
    if (typeof p === 'string') return p;
    if (typeof p === 'object' && p !== null) return p.path || p.file || p.filename || String(p);
    return String(p);
  };

  const handleFileClick = (rawPath) => {
    if (!openTab) return;
    const clean = getCleanPathStr(rawPath);
    if (clean) openTab({ path: clean, filename: clean.split('/').pop() || clean }, 'docs');
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

  const [userProfile, setUserProfile] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_user_profile');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { name: 'Tu', avatar: '/images/default.png' };
  });

  useEffect(() => {
    const handleProfileUpdate = (e) => {
      if (e.detail) setUserProfile(e.detail);
    };
    window.addEventListener('sigma_profile_updated', handleProfileUpdate);
    return () => window.removeEventListener('sigma_profile_updated', handleProfileUpdate);
  }, []);

  const speechId = String(first.timestamp || first.id || msgId || 'agent-msg');
  useEffect(() => {
    setIsPlayingAudio(String(getActiveSpeechId()) === String(speechId));
    const unsubSpeech = subscribeSpeech(activeId => setIsPlayingAudio(String(activeId) === String(speechId)));
    const unsubProgress = subscribeSpeechProgress(p => {
      if (p && String(p.speechId) === String(speechId)) setSpeechProgress({ ...p });
    });
    return () => { unsubSpeech(); unsubProgress(); };
  }, [speechId]);

  const avatarSrc = isUser
    ? (userProfile.avatar || '/images/default.png')
    : (agentId ? agentStyle.image : (first.agentImage || '/images/default.png'));
  const avatarBg = isUser ? 'rgba(0, 210, 255, 0.5)' : (agentId ? agentStyle.bg : 'var(--primary)');
  const roleName = isUser
    ? (userProfile.name || 'Tu')
    : (agentId ? (first.agentRole || first.agent_name || agentId) : (first.agentRole || 'AI'));

  const modelName = isUser ? '' : (first.agentName || effectiveModelName || 'AI');

  const loadingSteps = [
    "Sto pensando...",
    "🎯 Analisi richiesta ed instradamento agente...",
    "🧠 Elaborazione contenuto ed esecuzione azioni...",
    "📄 Generazione e sincronizzazione file nel workspace..."
  ];

  useEffect(() => {
    if (!isLoading) {
      setLoadingStep(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingStep(prev => (prev + 1) % loadingSteps.length);
    }, 2800);
    return () => clearInterval(interval);
  }, [isLoading]);

  return (
    <div
      className={`chat-message ${isUser ? 'chat-user' : isSystem ? 'chat-system' : 'chat-assistant'} ${agentId ? 'chat-agent-message' : ''} ${isGrouped ? 'chat-message-grouped' : ''}`}
    >
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
          {isOrchestrated && <span className="chat-msg-orchestrated" title="Assegnato dall'Orchestrator">🎯</span>}
          <div className="chat-msg-header-spacer" />
          <div className="chat-msg-time">{formatTimestamp(first.timestamp)}</div>
          <button
            className={`chat-msg-copy-btn ${copiedMsg ? 'copied' : ''}`}
            title="Copia messaggio negli appunti"
            onClick={handleCopyMessage}
            style={{
              background: copiedMsg ? 'rgba(74, 222, 128, 0.15)' : 'rgba(255,255,255,0.04)',
              border: copiedMsg ? '1px solid rgba(74, 222, 128, 0.3)' : '1px solid rgba(255,255,255,0.08)',
              color: copiedMsg ? '#4ade80' : 'var(--text-muted, #8b8fa3)',
              fontSize: '0.68rem',
              cursor: 'pointer',
              padding: '2px 7px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginLeft: '8px',
              transition: 'all 0.2s ease'
            }}
          >
            {copiedMsg ? '✓ Copiato!' : '📋 Copia'}
          </button>
          {!isUser && !isSystem && (
            <button
              onClick={() => {
                if (isPlayingAudio) {
                  stopSpeech();
                } else {
                  const textToRead = messages.map(m => m.content || m.text || '').join(' ');
                  speakAgentMessage(textToRead, null, null, speechId);
                }
              }}
              title={isPlayingAudio ? 'Ferma lettura' : 'Ascolta risposta vocale (TTS)'}
              style={{
                background: isPlayingAudio ? 'rgba(0,210,255,0.2)' : 'rgba(255,255,255,0.04)',
                border: isPlayingAudio ? '1px solid rgba(0,210,255,0.4)' : '1px solid rgba(255,255,255,0.08)',
                color: isPlayingAudio ? '#00d2ff' : 'var(--text-muted, #8b8fa3)',
                fontSize: '0.68rem',
                cursor: 'pointer',
                padding: '2px 7px',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                marginLeft: '6px',
                transition: 'all 0.2s ease'
              }}
            >
              {isPlayingAudio ? '⏹️ Ferma' : '🔊 Ascolta'}
            </button>
          )}
          {onDeleteMessage && (
            <button className="chat-msg-delete-btn" title="Elimina" onClick={() => onDeleteMessage(msgIndex)}>✕</button>
          )}
        </div>

        {/* Audio Player Control Bar when playing */}
        {!isUser && !isSystem && isPlayingAudio && (
          <div className="chat-audio-player-bar" onClick={e => e.stopPropagation()}>
            <div className="chat-audio-player-controls">
              <button 
                type="button" 
                onClick={() => {
                  const textToRead = messages.map(m => m.content || m.text || '').join(' ');
                  seekSpeechRelative(speechId, -40, textToRead);
                }} 
                title="Indietro di ~5 secondi"
                className="chat-audio-btn"
              >
                <RotateCcw size={11} />
                <span>-5s</span>
              </button>

              <button 
                type="button" 
                onClick={togglePauseSpeech} 
                title={speechProgress.paused ? "Riprendi lettura" : "Pausa lettura"}
                className="chat-audio-btn primary"
              >
                {speechProgress.paused ? <Play size={12} /> : <Pause size={12} />}
              </button>

              <button 
                type="button" 
                onClick={() => {
                  const textToRead = messages.map(m => m.content || m.text || '').join(' ');
                  seekSpeechRelative(speechId, +40, textToRead);
                }} 
                title="Avanti di ~5 secondi"
                className="chat-audio-btn"
              >
                <RotateCw size={11} />
                <span>+5s</span>
              </button>
            </div>

            <div className="chat-audio-scrubber-container">
              <input 
                type="range"
                min="0"
                max="100"
                step="1"
                value={Math.round((speechProgress.progress || 0) * 100)}
                onChange={(e) => {
                  const textToRead = messages.map(m => m.content || m.text || '').join(' ');
                  seekSpeechPercent(speechId, parseFloat(e.target.value) / 100, textToRead);
                }}
                className="chat-audio-scrubber"
                title="Trascina per navigare nel testo"
              />
            </div>

            <div className="chat-audio-info">
              <span className="chat-audio-percent">
                {Math.round((speechProgress.progress || 0) * 100)}%
              </span>
              <button 
                type="button" 
                onClick={stopSpeech} 
                title="Interrompi lettura"
                className="chat-audio-btn stop"
              >
                <Square size={11} />
              </button>
            </div>
          </div>
        )}

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

          {/* Loading indicator directly inside chat-msg-content */}
          {isLoading && messages.every(m => !m.content && !m.thinking) ? (
            <div className="chat-loading" style={{ padding: '6px 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="chat-loading-cursor">●</span>
                <span style={{ transition: 'all 0.3s ease', fontWeight: '500' }}>
                  {first.statusMessage || loadingSteps[loadingStep]}
                </span>
              </div>
              {first.modelStatus && (
                <div style={{ fontSize: '0.72rem', color: '#8b8fa3', paddingLeft: '18px' }}>
                  {first.modelStatus}
                </div>
              )}
            </div>
          ) : (
            messages.map((m, idx) => {
            const mid = msgId || `msg-${idx}`;
            const isLast = idx === messages.length - 1;

            let displayContent = m.content || '';
            let displayThinking = m.thinking || '';

            if (!isUser && !isSystem && !displayThinking && displayContent) {
              const thinkMatch = displayContent.match(/<think>(.*?)<\/think>/s);
              if (thinkMatch) {
                displayThinking = thinkMatch[1].trim();
                displayContent = displayContent.replace(/<think>.*?<\/think>/gs, '').trim();
              } else if (/^(?:Analyze User Input|Identify Key Constraints|Context:|Thinking:|Role:|\*\*Analyze)/i.test(displayContent.trim()) || displayContent.includes('Analyze User Input')) {
                const monologueMatch = displayContent.match(/^(Analyze\s+User\s+Input:[\s\S]*?(?:Final\s+Output\s+Generation:[^\n]*|Proceeds\.?|✅)+)\s*([\s\S]+)$/i);
                if (monologueMatch) {
                  displayThinking = monologueMatch[1].trim();
                  displayContent = monologueMatch[2].trim();
                } else {
                  const responseMarker = displayContent.match(/(?:\n|^|\b)(?:Ciao!|Ciao\b|Path:|#\s+|Ecco\s+|Ho\s+|Per\s+|---|Sono\s+Sigma|\*\*Risposta|\*\*Struttura|Dimmi\s+pure)/i);
                  if (responseMarker) {
                    const splitPos = responseMarker.index;
                    displayThinking = displayContent.substring(0, splitPos).trim();
                    displayContent = displayContent.substring(splitPos).trim();
                  } else {
                    displayThinking = displayContent.trim();
                    displayContent = '';
                  }
                }
              } else {
                const splitMatch = displayContent.match(/✅|\bFinal Polish:.*?\n/s);
                if (splitMatch) {
                  const splitPos = splitMatch.index + splitMatch[0].length;
                  displayThinking = displayContent.substring(0, splitPos).trim();
                  displayContent = displayContent.substring(splitPos).replace(/^[🤖✅\s]+/, '').trim();
                }
              }
            }

            return (
              <div key={idx} className={isGrouped && !isLast ? 'chat-msg-grouped-item chat-msg-grouped-border' : 'chat-msg-grouped-item'}>
                {/* Thinking toggle */}
                {!isUser && !isSystem && displayThinking && (
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
                        dangerouslySetInnerHTML={{ __html: renderMarkdownLatex(displayThinking) }}
                      />
                    )}
                  </div>
                )}

                {/* Content & Actions */}
                {(m.isAction || (m.actions_log && m.actions_log.length > 0)) ? (
                  <div className="chat-actions-log" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {m.actions_log && m.actions_log.length > 0 ? (
                      m.actions_log.map((action, actionIdx) => {
                        if (action.type === 'mcp_tool_call') {
                          return (
                            <div 
                              key={actionIdx}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '6px 12px',
                                borderRadius: '8px',
                                background: 'rgba(0, 210, 255, 0.08)',
                                border: '1px solid rgba(0, 210, 255, 0.2)',
                                color: '#00d2ff',
                                fontSize: '0.75rem',
                                fontWeight: 600
                              }}
                            >
                              <Zap size={14} style={{ color: '#00d2ff' }} />
                              <span>{action.message}</span>
                              {action.success && <span style={{ marginLeft: 'auto', color: '#3fb950', fontSize: '0.7rem' }}>✓ Eseguito MCP</span>}
                            </div>
                          );
                        }
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
                                {action.path && (() => {
                                  const aPStr = getCleanPathStr(action.path);
                                  const isAViz = aPStr.toLowerCase().includes('/viz/') || aPStr.toLowerCase().endsWith('.html');
                                  return (
                                    <button
                                      onClick={() => handleFileClick(aPStr)}
                                      style={{
                                        background: isAViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.1)',
                                        border: isAViz ? '1px solid rgba(57,185,80,0.3)' : '1px solid rgba(0,210,255,0.25)',
                                        color: isAViz ? '#3fb950' : 'var(--primary)',
                                        fontSize: '0.65rem',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease'
                                      }}
                                      title={isAViz ? "Apri l'anteprima interattiva nel workspace" : "Apri il file nel workspace"}
                                    >
                                      {isAViz ? 'Anteprima 👁️' : 'Visualizza 📄'}
                                    </button>
                                  );
                                })()}
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
                ) : (
                  <>
                    {displayContent && (
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
                        dangerouslySetInnerHTML={{ 
                          __html: (isPlayingAudio && speechProgress && String(speechProgress.speechId) === String(speechId) && speechProgress.charIndex >= 0)
                            ? (() => {
                                // Calculate per-message charIndex: subtract cleaned lengths
                                // of all previous messages in the group.
                                let localIdx = speechProgress.charIndex;
                                const singleClean = cleanTextForSpeech(displayContent);
                                for (let pi = 0; pi < idx; pi++) {
                                  const prev = messages[pi];
                                  const prevText = prev.content || prev.text || '';
                                  if (prevText) {
                                    localIdx -= cleanTextForSpeech(prevText).length;
                                  }
                                }
                                if (localIdx < 0) localIdx = 0;
                                // Advance to the next word for a "reading ahead" karaoke effect
                                if (localIdx < singleClean.length) {
                                  // Skip the current word (if positioned on one)
                                  while (localIdx < singleClean.length && /[\p{L}\p{N}]/u.test(singleClean[localIdx])) {
                                    localIdx++;
                                  }
                                  // Skip whitespace/punctuation to land on the next word
                                  while (localIdx < singleClean.length && !/[\p{L}\p{N}]/u.test(singleClean[localIdx])) {
                                    localIdx++;
                                  }
                                }
                                return highlightCurrentWordInHtml(
                                  renderMarkdownLatex(displayContent),
                                  singleClean,
                                  localIdx,
                                  speechProgress.charLength
                                );
                              })()
                            : renderMarkdownLatex(displayContent)
                        }}
                      />
                    )}
                    {(m.streaming || (isLoading && isLast && (!displayContent || displayContent.length < 10))) && (
                      <div className="chat-generating-indicator" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px', color: 'var(--primary)', fontSize: '0.78rem' }}>
                        <span className="chat-loading-cursor">●</span>
                        <span style={{ fontStyle: 'italic', fontWeight: '500' }}>Generazione risposta ed elaborazione in corso...</span>
                      </div>
                    )}
                    {/* Strumenti MCP eseguiti e chiamate in attesa di assenso */}
                    {(m.tool_calls?.length > 0 || m.tool_approvals?.length > 0) && (
                      <McpToolStrip calls={m.tool_calls} approvals={m.tool_approvals} />
                    )}
                    {/* Render action cards or created file buttons */}
                    {((!m.isAction && m.actions_log && m.actions_log.length > 0) || m.created_files?.length > 0) && (
                      <div className="chat-actions-log" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
                        {m.created_files?.map((filePath, fIdx) => {
                          const pStr = getCleanPathStr(filePath);
                          const isViz = pStr.toLowerCase().includes('/viz/') || pStr.toLowerCase().endsWith('.html');
                          return (
                          <div key={`cf-${fIdx}`} className="action-log-item" style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 8px',
                            background: 'rgba(0, 210, 255, 0.04)',
                            border: '1px solid rgba(0, 210, 255, 0.15)',
                            borderRadius: '6px',
                            fontSize: '0.75rem'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                              <span>📁</span>
                              <span style={{ fontWeight: '600', color: 'var(--primary)', flexShrink: 0 }}>
                                File salvato
                              </span>
                              <span style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                {pStr}
                              </span>
                            </div>
                            <button
                              onClick={() => handleFileClick(pStr)}
                              style={{
                                background: isViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.15)',
                                border: isViz ? '1px solid rgba(57,185,80,0.4)' : '1px solid rgba(0,210,255,0.3)',
                                color: isViz ? '#3fb950' : 'var(--primary)',
                                fontSize: '0.7rem',
                                padding: '3px 10px',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontWeight: '600'
                              }}
                            >
                              {isViz ? 'Anteprima 👁️' : 'Visualizza 📄'}
                            </button>
                          </div>
                          );
                        })}
                        {m.actions_log && m.actions_log.length > 0 && m.actions_log.map((action, actionIdx) => {
                          const isRollbackable = action.success && action.backup_id;
                          const hasBeenRolledBack = isRollbackable && (rolledBacks[action.backup_id] || localStorage.getItem(`sigma_rolled_back_${action.backup_id}`) === 'true');
                          const diffKey = `${mid}-${actionIdx}`;
                          const isDiffExpanded = expandedDiffs[diffKey];
                          const hasDiff = !!action.diff;
                          const actPathStr = getCleanPathStr(action.path);
                          const isActViz = actPathStr.toLowerCase().includes('/viz/') || actPathStr.toLowerCase().endsWith('.html');
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
                                    style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', cursor: actPathStr ? 'pointer' : 'default' }}
                                    title={actPathStr}
                                    onClick={() => actPathStr && handleFileClick(actPathStr)}
                                  >
                                    {action.message || action.error || ''}
                                  </span>
                                </div>
                                <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
                                  {actPathStr && (
                                    <button
                                      onClick={() => handleFileClick(actPathStr)}
                                      style={{
                                        background: isActViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.1)',
                                        border: isActViz ? '1px solid rgba(57,185,80,0.3)' : '1px solid rgba(0,210,255,0.25)',
                                        color: isActViz ? '#3fb950' : 'var(--primary)',
                                        fontSize: '0.65rem',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        transition: 'all 0.15s ease'
                                      }}
                                      title={isActViz ? "Apri l'anteprima interattiva nel workspace" : "Apri il file nel workspace"}
                                    >
                                      {isActViz ? 'Anteprima 👁️' : 'Visualizza 📄'}
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
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}

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
          }))}
        </div>
      </div>
    </div>
  );
}