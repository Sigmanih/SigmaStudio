import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Bot, User, Terminal, FileText, Zap, Play, Pause, RotateCcw, RotateCw, Square } from 'lucide-react';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import McpToolStrip from './McpToolStrip';
import ImageLightbox from './ImageLightbox';
import { useApp } from '../../contexts/AppContext';
import { useMusic } from '../../context/MusicContext';
import { getModelSpecs } from './core/modelSpecsHelper';
import 'katex/dist/katex.min.css';


// Helper: check if a file path is an image
const IMAGE_EXTENSIONS = /\.(?:png|jpg|jpeg|webp|svg|gif|bmp|tiff)$/i;
const isImagePath = (p) => typeof p === 'string' && IMAGE_EXTENSIONS.test(p);

// ==============================================================================
// AGENT MESSAGE v5.1 — Memoized HTML to prevent iframe/video reload on re-render
// ==============================================================================

const AGENT_COLORS = {
  sigma_architect: { bg: '#bc8cff', color: '#0e1016', icon: '🏗️', short: 'Arch', name: 'Sigma Architect', image: '/images/agente0.png' },
  math_researcher: { bg: '#00d2ff', color: '#0e1016', icon: '∑', short: 'Math', name: 'Sigma Math Researcher', image: '/images/matematicoAi.png' },
  code_architect: { bg: '#3fb950', color: '#0e1016', icon: '⚙️', short: 'Code', name: 'Sigma Code Architect', image: '/images/programmatoreAi.png' },
  viz_designer: { bg: '#ff79c6', color: '#0e1016', icon: '🎨', short: 'Viz', name: 'Sigma Viz Designer', image: '/images/default.png' },
  test_engineer: { bg: '#3fb950', color: '#0e1016', icon: '🧪', short: 'Test', name: 'Sigma Test Engineer', image: '/images/default.png' },
  proof_reviewer: { bg: '#ff5064', color: '#ffffff', icon: '🔍', short: 'Review', name: 'Sigma Proof Reviewer', image: '/images/default.png' },
  physics_professor: { bg: '#ff5064', color: '#ffffff', icon: '⚛️', short: 'Physics', name: 'Professore di Fisica', image: '/images/default.png' },
  chemistry_professor: { bg: '#00f2fe', color: '#0e1016', icon: '🧪', short: 'Chemistry', name: 'Professore di Chimica', image: '/images/default.png' },
  academic_examiner: { bg: '#d29922', color: '#0e1016', icon: '🎓', short: 'Examiner', name: 'Academic Examiner', image: '/images/default.png' },
  online_journalist: { bg: '#d29922', color: '#0e1016', icon: '📰', short: 'News', name: 'Online Journalist', image: '/images/default.png' },
  sigma_assistant: { bg: '#00f2fe', color: '#0e1016', icon: '🤖', short: 'Assist', name: 'Sigma Assistant', image: '/images/default.png' },
  sigma_admin: { bg: '#ffb86c', color: '#0e1016', icon: '⚡', short: 'Admin', name: 'Sigma Admin', image: '/images/agente0.png' },
  tutor_matematica: { bg: '#00d2ff', color: '#0e1016', icon: '📐', short: 'Tutor', name: 'Tutor Matematica', image: '/images/matematicoAi.png' },
  docente_lingue: { bg: '#bc8cff', color: '#0e1016', icon: '🌍', short: 'Lingue', name: 'Docente di Lingue', image: '/images/default.png' },
  consulente_legale: { bg: '#d29922', color: '#0e1016', icon: '⚖️', short: 'Legale', name: 'Consulente Legale', image: '/images/default.png' },
  medico_divulgatore: { bg: '#ff5064', color: '#ffffff', icon: '🩺', short: 'Medico', name: 'Medico Consulente', image: '/images/default.png' },
  financial_analyst: { bg: '#3fb950', color: '#0e1016', icon: '📈', short: 'Finance', name: 'Analista Finanziario', image: '/images/default.png' },
  data_scientist: { bg: '#00d2ff', color: '#0e1016', icon: '📊', short: 'Data', name: 'Data Scientist', image: '/images/default.png' },
  copywriter_storyteller: { bg: '#ff79c6', color: '#0e1016', icon: '✍️', short: 'Copy', name: 'Copywriter Creativo', image: '/images/default.png' },
  ingegnere_strutturista: { bg: '#d29922', color: '#0e1016', icon: '🔧', short: 'Eng', name: 'Ingegnere Meccanico', image: '/images/default.png' },
  math1: { bg: '#00d2ff', color: '#0e1016', icon: '∑', short: 'Math', name: 'Sigma Math Researcher', image: '/images/matematicoAi.png' },
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

function findWordAt(text, charIdx) {
  if (!text || charIdx < 0) return null;
  const len = text.length;
  let idx = Math.min(charIdx, len - 1);
  if (!/[\p{L}\p{N}]/u.test(text[idx])) {
    // Prefer the word we are currently finishing (backward search)
    let backward = idx;
    while (backward >= 0 && !/[\p{L}\p{N}]/u.test(text[backward])) backward--;
    if (backward >= 0) {
      idx = backward;
    } else {
      let forward = idx;
      while (forward < len && !/[\p{L}\p{N}]/u.test(text[forward])) forward++;
      if (forward < len) idx = forward;
      else return null;
    }
  }
  let s = idx, e = idx;
  while (s > 0 && /[\p{L}\p{N}]/u.test(text[s - 1])) s--;
  while (e < len && /[\p{L}\p{N}]/u.test(text[e])) e++;
  const word = text.slice(s, e).trim().replace(/[^\p{L}\p{N}]/gu, '');
  return word && word.length >= 1 ? { word, start: s, end: e } : null;
}

// ==============================================================================
// Main AgentMessage Component
// ==============================================================================
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

/**
 * Memoized content block for a single message within a group.
 * This avoids re-rendering the markdown (and destroying embedded iframes)
 * every time speechProgress ticks. Karaoke highlighting is applied
 * via a persistent, non-flickering <mark> element that smoothly advances.
 */
function MemoizedContent({ displayContent, isPlaying, speechId, speechProgress, messages, idx, onClick }) {
  // Base HTML, recomputed ONLY when the raw content changes
  const baseHtml = useMemo(() => renderMarkdownLatex(displayContent), [displayContent]);
  const containerRef = useRef(null);
  const currentHighlightRef = useRef(null);

  // Helper to safely unwrap a mark element back to plain text
  const unwrapMark = (markEl) => {
    if (!markEl || !markEl.parentNode) return;
    const parent = markEl.parentNode;
    const text = markEl.textContent || '';
    parent.replaceChild(document.createTextNode(text), markEl);
    parent.normalize();
  };

  // Clean up all highlights helper
  const removeAllHighlights = () => {
    const el = containerRef.current;
    if (!el) return;
    const marks = el.querySelectorAll('mark.speech-word-highlight');
    marks.forEach(m => unwrapMark(m));
    currentHighlightRef.current = null;
  };

  // Apply / move karaoke highlight smoothly without DOM thrashing
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    if (!isPlaying || !speechProgress || String(speechProgress.speechId) !== String(speechId) || speechProgress.charIndex < 0) {
      removeAllHighlights();
      return;
    }

    const singleClean = cleanTextForSpeech(displayContent);
    let localIdx = speechProgress.charIndex;
    for (let pi = 0; pi < idx; pi++) {
      const prevText = messages[pi]?.content || messages[pi]?.text || '';
      if (prevText) localIdx -= cleanTextForSpeech(prevText).length;
    }

    if (localIdx < 0) {
      removeAllHighlights();
      return;
    }
    if (localIdx >= singleClean.length && singleClean.length > 0) {
      removeAllHighlights();
      return;
    }

    const found = findWordAt(singleClean, localIdx);
    if (!found) {
      // Keep existing highlight visible while moving between words/spaces
      return;
    }

    const escaped = found.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const rx = new RegExp(`\\b${escaped}\\b`, 'gi');
    const textBefore = singleClean.slice(0, found.start);
    const targetOccurrence = (textBefore.match(rx) || []).length;

    // If already highlighting this exact word occurrence, keep it without re-rendering DOM
    if (
      currentHighlightRef.current &&
      currentHighlightRef.current.word === found.word &&
      currentHighlightRef.current.targetOccurrence === targetOccurrence
    ) {
      return;
    }

    // Find and wrap the new word FIRST before removing the old mark
    let newMark = null;

    function walk(node, count) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (node.parentNode && node.parentNode.tagName === 'MARK') return;
        const txt = node.textContent || '';
        let m;
        rx.lastIndex = 0;
        while ((m = rx.exec(txt)) !== null) {
          if (count.cur === targetOccurrence) {
            const before = txt.slice(0, m.index);
            const mid = txt.slice(m.index, m.index + m[0].length);
            const after = txt.slice(m.index + m[0].length);
            const frag = document.createDocumentFragment();
            if (before) frag.appendChild(document.createTextNode(before));
            const mark = document.createElement('mark');
            mark.className = 'speech-word-highlight is-active';
            mark.textContent = mid;
            frag.appendChild(mark);
            if (after) frag.appendChild(document.createTextNode(after));
            node.parentNode.replaceChild(frag, node);
            newMark = mark;
            count.done = true;
            return;
          }
          count.cur++;
        }
        return;
      }
      if (node.nodeType === Node.ELEMENT_NODE && !['SCRIPT', 'STYLE', 'IFRAME', 'VIDEO', 'AUDIO'].includes(node.tagName)) {
        for (const child of [...node.childNodes]) {
          if (count.done) return;
          walk(child, count);
        }
      }
    }

    const counter = { cur: 0, done: false };
    walk(el, counter);

    // If the new mark was successfully created:
    // 1. Transition previous marks to .is-leaving (initiates gentle fade-out)
    // 2. Safely unwrap once the fade-out completes
    if (newMark) {
      const prevMarks = el.querySelectorAll('mark.speech-word-highlight');
      prevMarks.forEach(pm => {
        if (pm !== newMark) {
          pm.className = 'speech-word-highlight is-leaving';
          setTimeout(() => {
            if (pm && pm.parentNode && pm.classList.contains('is-leaving')) {
              unwrapMark(pm);
            }
          }, 320);
        }
      });
      currentHighlightRef.current = { word: found.word, targetOccurrence, mark: newMark };
    }
  }, [displayContent, isPlaying, speechProgress?.charIndex, speechProgress?.speechId, speechId, idx, messages]);

  return (
    <div
      ref={containerRef}
      className="chat-content chat-md"
      onClick={onClick}
      dangerouslySetInnerHTML={{ __html: baseHtml }}
    />
  );
}

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
  const [lightboxSrc, setLightboxSrc] = useState(null);

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
    if (!clean) return;
    if (isImagePath(clean)) {
      openTab({ path: clean, filename: clean.split('/').pop() || clean }, 'image_viewer');
    } else {
      openTab({ path: clean, filename: clean.split('/').pop() || clean }, 'docs');
    }
  };

  const handleImagePreviewClick = (imgUrl) => {
    setLightboxSrc(imgUrl);
  };

  const musicCtx = useMusic ? useMusic() : null;
  const saveYouTubeFavorite = musicCtx?.saveYouTubeFavorite;
  const addCustomTrack = musicCtx?.addCustomTrack;
  const userCategories = musicCtx?.userCategories || [];
  const createUserCategory = musicCtx?.createUserCategory;

  const [categoryPickerTarget, setCategoryPickerTarget] = useState(null);
  const [newCatInlineName, setNewCatInlineName] = useState('');

  const handleMemoizedContentClick = (e) => {
    // 1. File links
    const link = e.target.closest('.chat-file-link');
    if (link) {
      e.preventDefault();
      const path = link.getAttribute('data-path') || link.dataset.path;
      handleFileClick(path);
      return;
    }

    // 2. YouTube Favorite Button
    const favBtn = e.target.closest('.chat-yt-fav-btn');
    if (favBtn) {
      e.preventDefault();
      e.stopPropagation();
      const ytId = favBtn.getAttribute('data-yt-id') || favBtn.dataset.ytId;
      const ytTitle = favBtn.getAttribute('data-yt-title') || favBtn.dataset.ytTitle || 'Video Musicale';
      setCategoryPickerTarget({
        id: ytId,
        title: ytTitle,
        btnEl: favBtn
      });
      return;
    }

    // 3. YouTube Play in Background Button
    const playRadioBtn = e.target.closest('.chat-yt-play-radio-btn');
    if (playRadioBtn) {
      e.preventDefault();
      e.stopPropagation();
      const ytId = playRadioBtn.getAttribute('data-yt-id') || playRadioBtn.dataset.ytId;
      const ytTitle = playRadioBtn.getAttribute('data-yt-title') || playRadioBtn.dataset.ytTitle || 'Video Musicale';
      if (addCustomTrack) {
        addCustomTrack({
          id: `yt-${ytId}`,
          youtubeId: ytId,
          title: ytTitle,
          engine: 'youtube',
          url: `https://www.youtube.com/watch?v=${ytId}`
        });
        playRadioBtn.innerHTML = '▶ In Riproduzione';
        playRadioBtn.style.background = 'rgba(0, 242, 254, 0.4)';
        playRadioBtn.style.borderColor = '#00f2fe';
        playRadioBtn.style.color = '#ffffff';
      }
      return;
    }
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
  const rawRole = first.agentRole || first.agent_name || (agentId && agentId !== 'auto' ? agentId.replace('_', ' ') : 'Sigma Assistant');
  const roleName = isUser
    ? (userProfile.name || 'Tu')
    : ((rawRole && rawRole.toLowerCase() !== 'auto') ? rawRole : 'Sigma Assistant');

  const rawModelName = first.agentName || effectiveModelName || 'AI';
  const modelName = isUser ? '' : (rawModelName.toLowerCase().startsWith('auto ') || rawModelName.toLowerCase() === 'auto' ? `${roleName} (${effectiveModelName || 'AI'})` : rawModelName);
  const targetModelForSpecs = (first.agentName || effectiveModelName || '').replace(/^.*?\((.*?)\).*$/, '$1');
  const modelSpecs = !isUser && !isSystem ? getModelSpecs(targetModelForSpecs) : null;

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
          {modelName && (
            <div className="chat-msg-model" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
              <span>· {modelName}</span>
              {modelSpecs?.params && (
                <span style={{
                  fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                  background: 'rgba(0, 210, 255, 0.16)', color: '#00d2ff', fontWeight: 800
                }}>
                  ⚡ {modelSpecs.params}
                </span>
              )}
              {modelSpecs?.size && (
                <span style={{
                  fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                  background: 'rgba(255, 184, 108, 0.16)', color: '#ffb86c', fontWeight: 800
                }}>
                  💾 {modelSpecs.size}
                </span>
              )}
              {modelSpecs?.format && (
                <span style={{
                  fontSize: '0.56rem', padding: '1px 4px', borderRadius: '3px',
                  background: 'rgba(188, 140, 255, 0.14)', color: '#bc8cff', fontWeight: 700
                }}>
                  {modelSpecs.format}
                </span>
              )}
            </div>
          )}
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
          {!isUser && !isSystem && (() => {
            const isMessageStreaming = messages.some(m => m.streaming || m.streamingThinking) || Boolean(isLoading);
            return (
              <button
                disabled={isMessageStreaming}
                onClick={() => {
                  if (isMessageStreaming) return;
                  if (isPlayingAudio) {
                    stopSpeech();
                  } else {
                    const textToRead = messages.map(m => m.content || m.text || '').join(' ');
                    speakAgentMessage(textToRead, null, null, speechId);
                  }
                }}
                title={isMessageStreaming ? 'In attesa del completamento della risposta...' : (isPlayingAudio ? 'Ferma lettura' : 'Ascolta risposta vocale (TTS)')}
                style={{
                  background: isPlayingAudio ? 'rgba(0,210,255,0.2)' : 'rgba(255,255,255,0.04)',
                  border: isPlayingAudio ? '1px solid rgba(0,210,255,0.4)' : '1px solid rgba(255,255,255,0.08)',
                  color: isMessageStreaming ? '#55596e' : (isPlayingAudio ? '#00d2ff' : 'var(--text-muted, #8b8fa3)'),
                  opacity: isMessageStreaming ? 0.45 : 1,
                  fontSize: '0.68rem',
                  cursor: isMessageStreaming ? 'not-allowed' : 'pointer',
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
            );
          })()}
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
            justifyContent: 'space-between',
            gap: '8px',
            padding: '8px 12px',
            background: 'rgba(255,255,255,0.02)',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            fontSize: '0.72rem',
            color: '#8b8fa3',
            flexWrap: 'wrap'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1rem' }}>{agentStyle?.icon || '🤖'}</span>
              <span>Ruolo attivo: <strong style={{ color: 'var(--primary)' }}>{roleName}</strong></span>
            </div>

            {modelSpecs && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.66rem' }}>
                <span style={{ color: '#8b8fa3' }}>Modello: <strong style={{ color: 'var(--text-primary, #ffffff)' }}>{modelSpecs.name}</strong></span>
                {modelSpecs.params && (
                  <span style={{
                    fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                    background: 'rgba(0, 210, 255, 0.16)', color: '#00d2ff', fontWeight: 800
                  }}>
                    ⚡ {modelSpecs.params}
                  </span>
                )}
                {modelSpecs.size && (
                  <span style={{
                    fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                    background: 'rgba(255, 184, 108, 0.16)', color: '#ffb86c', fontWeight: 800
                  }}>
                    💾 {modelSpecs.size}
                  </span>
                )}
              </div>
            )}
          </div>
        )}


        {/* Content area */}
        <div className="chat-msg-content">
          {isUser && first.attachments?.length > 0 && (
            <div className="chat-message-attachments">
              {first.attachments.map(p => (
                <span key={p} className="chat-attachment-chip">
                  <FileText size={10} /> {p.split('/').pop()}
                </span>
              ))}
            </div>
          )}

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
              const thinkMatch = displayContent.match(/<(?:think|thinking|thought)>([\s\S]*?)<\/(?:think|thinking|thought)>/i)
                || displayContent.match(/<\|channel\>thought([\s\S]*?)<channel\|>/i)
                || displayContent.match(/<\|thought\|>([\s\S]*?)<\/\|thought\|>/i);
              if (thinkMatch) {
                displayThinking = (thinkMatch[1] || '').trim();
                displayContent = displayContent
                  .replace(/<(?:think|thinking|thought)>[\s\S]*?<\/(?:think|thinking|thought)>/gi, '')
                  .replace(/<\|channel\>thought[\s\S]*?<channel\|>/gi, '')
                  .replace(/<\|thought\|>[\s\S]*?<\/\|thought\|>/gi, '')
                  .replace(/<\|channel\>thought/gi, '')
                  .replace(/<channel\|>/gi, '')
                  .replace(/^thought\s*\n/i, '')
                  .trim();
              } else if (displayContent.startsWith('<|channel>thought') || displayContent.startsWith('<channel|>') || displayContent.startsWith('thought\n')) {
                displayContent = displayContent
                  .replace(/<\|channel\>thought/gi, '')
                  .replace(/<channel\|>/gi, '')
                  .replace(/^thought\s*\n/i, '')
                  .trim();
              } else if (/^(?:Analyze User Input|Identify Key Constraints|Context:|Thinking:|Role:|\*\*Analyze|The user is asking|Need maybe|Need to|Need final|Let me think|Let's draft|Wait, let me|Actually, look|"Ciao)/i.test(displayContent.trim()) || displayContent.includes('Analyze User Input')) {
                const monologueMatch = displayContent.match(/^(Analyze\s+User\s+Input:[\s\S]*?(?:Final\s+Output\s+Generation:[^\n]*|Proceeds\.?|✅)+)\s*([\s\S]+)$/i);
                if (monologueMatch) {
                  displayThinking = monologueMatch[1].trim();
                  displayContent = monologueMatch[2].trim();
                } else {
                  const responseMarker = displayContent.match(/(?:\n\n|\n|^)\s*(?:(?:Let\'?s\s+draft[:\s]*|Let\s+me\s+write\s+the\s+final\s+response\s+now[:\s]*|final\.)\s*\n+)?(Ciao[,!\s]|Salve[,!\s]|Buongiorno[,!\s]|Buonasera[,!\s]|Ecco\s+|Benvenuto[,!\s]|Certamente|Certo[,!]|In\s+\*?\*?Sigma\s+Studio\*?\*?|\*\*Sigma\s+Studio\*\*|Come\s+Sigma\s+Architect|Come\s+Sigma\s+Assistant|La\s+mia\s+opinione|#\s+|Path:)/i);
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
                            <div key={actionIdx} style={{
                              display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px',
                              borderRadius: '8px', background: 'rgba(0, 210, 255, 0.08)',
                              border: '1px solid rgba(0, 210, 255, 0.2)', color: '#00d2ff',
                              fontSize: '0.75rem', fontWeight: 600
                            }}>
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
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              padding: '6px 8px', background: 'rgba(255,255,255,0.02)',
                              border: '1px solid rgba(255,255,255,0.04)', borderRadius: '6px', fontSize: '0.75rem'
                            }}>
                              <div className="action-log-item-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                                <span>{action.success ? '✅' : '❌'}</span>
                                <span style={{ fontWeight: '600', color: action.success ? 'var(--primary)' : 'var(--error)', flexShrink: 0 }}>{action.type}</span>
                                <span style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', cursor: action.path ? 'pointer' : 'default' }}
                                  title={action.path || ''} onClick={() => action.path && handleFileClick(action.path)}>
                                  {action.message || action.error || ''}
                                </span>
                              </div>
                              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
                                {action.path && (() => {
                                  const aPStr = getCleanPathStr(action.path);
                                  const isAViz = aPStr.toLowerCase().includes('/viz/') || aPStr.toLowerCase().endsWith('.html');
                                  return (
                                    <button onClick={() => handleFileClick(aPStr)} style={{
                                      background: isAViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.1)',
                                      border: isAViz ? '1px solid rgba(57,185,80,0.3)' : '1px solid rgba(0,210,255,0.25)',
                                      color: isAViz ? '#3fb950' : 'var(--primary)', fontSize: '0.65rem', padding: '2px 8px',
                                      borderRadius: '4px', cursor: 'pointer', transition: 'all 0.15s ease'
                                    }}>{isAViz ? 'Anteprima 👁️' : 'Visualizza 📄'}</button>
                                  );
                                })()}
                                {hasDiff && (<button onClick={() => toggleDiff(diffKey)} style={{
                                  background: 'rgba(0,210,255,0.1)', border: '1px solid rgba(0,210,255,0.25)',
                                  color: 'var(--primary)', fontSize: '0.65rem', padding: '2px 8px',
                                  borderRadius: '4px', cursor: 'pointer'
                                }}>{isDiffExpanded ? 'Nascondi Modifiche' : 'Visualizza Modifiche'}</button>)}
                                {isRollbackable && (<button onClick={() => handleRollback(action.backup_id)} disabled={hasBeenRolledBack} style={{
                                  background: hasBeenRolledBack ? 'transparent' : 'rgba(255,85,85,0.15)',
                                  border: hasBeenRolledBack ? 'none' : '1px solid rgba(255,85,85,0.3)',
                                  color: hasBeenRolledBack ? '#3fb950' : '#ff5555', fontSize: '0.65rem', padding: '2px 8px',
                                  borderRadius: '4px', cursor: hasBeenRolledBack ? 'default' : 'pointer'
                                }}>{hasBeenRolledBack ? 'Annullato ✓' : 'Annulla Modifica'}</button>)}
                              </div>
                            </div>
                            {hasDiff && isDiffExpanded && (
                              <div className="action-diff-container" style={{
                                background: '#090b10', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '6px',
                                padding: '8px 10px', fontFamily: 'Consolas, Monaco, monospace', fontSize: '0.7rem',
                                lineHeight: '1.25rem', overflowX: 'auto', whiteSpace: 'pre', color: '#adbac7',
                                marginTop: '2px', maxHeight: '350px', boxShadow: 'inset 0 0 10px rgba(0,0,0,0.5)'
                              }}>
                                {action.diff.split('\n').map((line, lineIdx) => {
                                  let lineStyle = { padding: '2px 4px', borderRadius: '2px', display: 'block' };
                                  if (line.startsWith('+') && !line.startsWith('+++')) { lineStyle.background = 'rgba(46, 160, 67, 0.15)'; lineStyle.color = '#3fb950'; }
                                  else if (line.startsWith('-') && !line.startsWith('---')) { lineStyle.background = 'rgba(248, 81, 73, 0.15)'; lineStyle.color = '#f85149'; }
                                  else if (line.startsWith('@@')) { lineStyle.color = '#79c0ff'; lineStyle.background = 'rgba(121, 192, 255, 0.05)'; lineStyle.fontWeight = 'bold'; }
                                  return <span key={lineIdx} style={lineStyle}>{line}</span>;
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      (m.content || '').split('\n').map((l, j) => (<div key={j} className="action-line">{l}</div>))
                    )}
                  </div>
                ) : (
                  <>
                    {displayContent && (
                      <MemoizedContent
                        displayContent={displayContent}
                        isPlaying={isPlayingAudio}
                        speechId={speechId}
                        speechProgress={speechProgress}
                        messages={messages}
                        idx={idx}
                        onClick={handleMemoizedContentClick}
                      />
                    )}
                    {(m.streaming || (isLoading && isLast && (!displayContent || displayContent.length < 10))) && (
                      <div className="chat-generating-indicator" style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginTop: '8px',
                        color: 'var(--primary)',
                        fontSize: '0.78rem'
                      }}>
                        <span className="chat-loading-cursor">●</span>
                        <span style={{ fontStyle: 'italic', fontWeight: '600', letterSpacing: '0.2px' }}>
                          {m.statusMessage || (
                            m.streamingThinking 
                              ? '🧭 Elaborazione e ragionamento profondo in corso...' 
                              : (displayContent && displayContent.length >= 10 
                                  ? '✨ Generazione risposta in corso...' 
                                  : '🧠 Caricamento modello e analisi contesto...')
                          )}
                        </span>
                      </div>
                    )}
                    {(m.tool_calls?.length > 0 || m.tool_approvals?.length > 0) && (
                      <McpToolStrip calls={m.tool_calls} approvals={m.tool_approvals} />
                    )}
                    {((!m.isAction && m.actions_log && m.actions_log.length > 0) || m.created_files?.length > 0) && (
                      <div className="chat-actions-log" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
                        {m.created_files?.map((filePath, fIdx) => {
                          const pStr = getCleanPathStr(filePath);
                          const isViz = pStr.toLowerCase().includes('/viz/') || pStr.toLowerCase().endsWith('.html');
                          const isImg = isImagePath(pStr);
                          const imgUrl = isImg ? (pStr.startsWith('/') ? pStr : `/${pStr}`) : null;
                          return (
                          <div key={`cf-${fIdx}`} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {isImg && imgUrl && (
                              <div className="agent-image-preview" onClick={() => handleImagePreviewClick(imgUrl)} title="Clicca per ingrandire">
                                <img src={imgUrl} alt={pStr.split('/').pop()} loading="lazy" onError={(e) => { e.target.style.display = 'none'; }} />
                                <div className="image-overlay"><span>🔍 Ingrandisci</span></div>
                              </div>
                            )}
                            <div className="action-log-item" style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              padding: '6px 8px', background: isImg ? 'rgba(124, 91, 240, 0.06)' : 'rgba(0, 210, 255, 0.04)',
                              border: isImg ? '1px solid rgba(124, 91, 240, 0.2)' : '1px solid rgba(0, 210, 255, 0.15)',
                              borderRadius: '6px', fontSize: '0.75rem'
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                                <span>{isImg ? '🎨' : '📁'}</span>
                                <span style={{ fontWeight: '600', color: isImg ? '#7c5bf0' : 'var(--primary)', flexShrink: 0 }}>{isImg ? 'Immagine generata' : 'File salvato'}</span>
                                <span style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{pStr}</span>
                              </div>
                              <div style={{ display: 'flex', gap: '5px' }}>
                                <button onClick={() => handleFileClick(pStr)} style={{
                                  background: isImg ? 'rgba(124,91,240,0.15)' : isViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.15)',
                                  border: isImg ? '1px solid rgba(124,91,240,0.35)' : isViz ? '1px solid rgba(57,185,80,0.4)' : '1px solid rgba(0,210,255,0.3)',
                                  color: isImg ? '#7c5bf0' : isViz ? '#3fb950' : 'var(--primary)', fontSize: '0.7rem', padding: '3px 10px',
                                  borderRadius: '4px', cursor: 'pointer', fontWeight: '600'
                                }}>{isImg ? 'Visualizza 🖼️' : isViz ? 'Anteprima 👁️' : 'Visualizza 📄'}</button>
                              </div>
                            </div>
                          </div>);
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
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px',
                                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '6px', fontSize: '0.75rem'
                              }}>
                                <div className="action-log-item-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                                  <span>{action.success ? '✅' : '❌'}</span>
                                  <span style={{ fontWeight: '600', color: action.success ? 'var(--primary)' : 'var(--error)', flexShrink: 0 }}>{action.type}</span>
                                  <span style={{ color: '#8b8fa3', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', cursor: actPathStr ? 'pointer' : 'default' }}
                                    title={actPathStr} onClick={() => actPathStr && handleFileClick(actPathStr)}>
                                    {action.message || action.error || ''}
                                  </span>
                                </div>
                                <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
                                  {actPathStr && (<button onClick={() => handleFileClick(actPathStr)} style={{
                                    background: isActViz ? 'rgba(57,185,80,0.15)' : 'rgba(0,210,255,0.1)',
                                    border: isActViz ? '1px solid rgba(57,185,80,0.3)' : '1px solid rgba(0,210,255,0.25)',
                                    color: isActViz ? '#3fb950' : 'var(--primary)', fontSize: '0.65rem', padding: '2px 8px',
                                    borderRadius: '4px', cursor: 'pointer'
                                  }}>{isActViz ? 'Anteprima 👁️' : 'Visualizza 📄'}</button>)}
                                  {hasDiff && (<button onClick={() => toggleDiff(diffKey)} style={{
                                    background: 'rgba(0,210,255,0.1)', border: '1px solid rgba(0,210,255,0.25)',
                                    color: 'var(--primary)', fontSize: '0.65rem', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer'
                                  }}>{isDiffExpanded ? 'Nascondi Modifiche' : 'Visualizza Modifiche'}</button>)}
                                  {isRollbackable && (<button onClick={() => handleRollback(action.backup_id)} disabled={hasBeenRolledBack} style={{
                                    background: hasBeenRolledBack ? 'transparent' : 'rgba(255,85,85,0.15)',
                                    border: hasBeenRolledBack ? 'none' : '1px solid rgba(255,85,85,0.3)',
                                    color: hasBeenRolledBack ? '#3fb950' : '#ff5555', fontSize: '0.65rem', padding: '2px 8px',
                                    borderRadius: '4px', cursor: hasBeenRolledBack ? 'default' : 'pointer'
                                  }}>{hasBeenRolledBack ? 'Annullato ✓' : 'Annulla Modifica'}</button>)}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}

                {m.error && <div className="chat-error">⚠️ {m.error}</div>}

                {/* Performance & Hardware Metrics in bottom right */}
                {!isUser && !isSystem && (() => {
                  const rawRouting = m.routing_time_ms ?? m.metrics?.routing_time_ms ?? first.routing_time_ms ?? first.metrics?.routing_time_ms;
                  const routingDisplay = rawRouting !== undefined && rawRouting !== null
                    ? (rawRouting >= 1000 ? `${(rawRouting / 1000).toFixed(2)}s` : `${Math.round(rawRouting)}ms`)
                    : null;

                  const rawLoad = m.load_duration_ms ?? m.metrics?.load_duration_ms ?? first.load_duration_ms ?? first.metrics?.load_duration_ms;
                  const loadDisplay = rawLoad !== undefined && rawLoad !== null
                    ? (rawLoad >= 1000 ? `${(rawLoad / 1000).toFixed(2)}s` : `${Math.round(rawLoad)}ms`)
                    : null;

                  const rawTps = m.tokens_per_second ?? m.metrics?.tokens_per_second ?? first.tokens_per_second ?? first.metrics?.tokens_per_second;
                  const tpsDisplay = rawTps !== undefined && rawTps !== null
                    ? `${typeof rawTps === 'number' ? rawTps.toFixed(1) : rawTps}`
                    : null;

                  const rawEngine = m.engine || m.metrics?.engine || first.engine || first.metrics?.engine;
                  const engineDisplay = rawEngine || null;

                  const rawTtft = m.ttft_ms ?? m.metrics?.ttft_ms ?? first.ttft_ms ?? first.metrics?.ttft_ms;
                  const ttftDisplay = rawTtft !== undefined && rawTtft !== null
                    ? `${Math.round(rawTtft)}ms`
                    : null;

                  if (!routingDisplay && !loadDisplay && !tpsDisplay && !engineDisplay && !ttftDisplay) return null;

                  return (
                    <div className="chat-msg-footer-metrics" style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      gap: '8px 14px',
                      marginTop: '8px',
                      paddingTop: '6px',
                      fontSize: '0.67rem',
                      color: '#8b8fa3',
                      borderTop: '1px solid rgba(255, 255, 255, 0.04)',
                      userSelect: 'none'
                    }}>
                      {loadDisplay && (
                        <span title="Tempo impiegato per caricare il modello in memoria / VRAM" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <span>⚡</span>
                          <span>Caricamento: <strong style={{ color: '#eab308', fontWeight: 600 }}>{loadDisplay}</strong></span>
                        </span>
                      )}
                      {engineDisplay && (
                        <span title="Motore di inferenza utilizzato" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <span>⚙️</span>
                          <span>Engine: <strong style={{ color: '#00f2fe', fontWeight: 700 }}>{engineDisplay}</strong></span>
                        </span>
                      )}
                      {ttftDisplay && (
                        <span title="Time To First Token (Latenza primo token)" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <span>⏱️</span>
                          <span>TTFT: <strong style={{ color: '#00f2fe', fontWeight: 600 }}>{ttftDisplay}</strong></span>
                        </span>
                      )}
                      {routingDisplay && (
                        <span title="Tempo impiegato dal centralino per analizzare l'intento e selezionare il ruolo" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <span>🎯</span>
                          <span>Scelta centralino: <strong style={{ color: '#00d2ff', fontWeight: 600 }}>{routingDisplay}</strong></span>
                        </span>
                      )}
                      {tpsDisplay && (
                        <span title="Velocità di generazione del modello (tokens al secondo)" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                          <span>🚀</span>
                          <span>Velocità: <strong style={{ color: '#4ade80', fontWeight: 600 }}>{tpsDisplay} t/s</strong></span>
                        </span>
                      )}
                    </div>
                  );

                })()}

                {isGrouped && (
                  <div className="chat-timestamp">
                    {formatTimestamp(m.timestamp)}
                    <span className="chat-message-agent">{' · '}{m.agent_name || agentId || m.agentName || effectiveModelName || 'AI'}</span>
                  </div>
                )}
              </div>
            );
          }))}
        </div>
      </div>
      {lightboxSrc && (
        <ImageLightbox
          src={lightboxSrc} alt=""
          onClose={() => setLightboxSrc(null)}
          onOpenInEditor={() => {
            const relPath = lightboxSrc.startsWith('/') ? lightboxSrc.slice(1) : lightboxSrc;
            if (openTab) openTab({ path: relPath, filename: relPath.split('/').pop() || relPath }, 'image_viewer');
          }}
        />
      )}

      {/* Interactive Category & Favorite Picker Popover for YouTube Video Cards */}
      {categoryPickerTarget && (
        <div 
          onClick={() => setCategoryPickerTarget(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(5px)',
            zIndex: 99999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#0f172a',
              border: '1px solid rgba(0, 242, 254, 0.4)',
              borderRadius: '16px',
              padding: '22px 26px',
              width: '90%',
              maxWidth: '430px',
              boxShadow: '0 20px 60px rgba(0,0,0,0.85), 0 0 35px rgba(0, 242, 254, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              color: '#f8fafc'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.96rem', fontWeight: 800 }}>
                <span style={{ color: '#ef4444' }}>❤️</span> Salva nei Preferiti & Categorie
              </div>
              <button 
                onClick={() => setCategoryPickerTarget(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1rem' }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: '0.78rem', color: '#94a3b8', background: 'rgba(255, 255, 255, 0.04)', padding: '8px 10px', borderRadius: '8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              🎵 <strong>{categoryPickerTarget.title}</strong>
            </div>

            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#cbd5e1' }}>
              Seleziona una categoria / genere esistente:
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '140px', overflowY: 'auto' }}>
              {userCategories && userCategories.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => {
                    if (saveYouTubeFavorite) {
                      saveYouTubeFavorite({
                        id: categoryPickerTarget.id,
                        title: categoryPickerTarget.title,
                        categoryId: cat.id
                      });
                      if (categoryPickerTarget.btnEl) {
                        categoryPickerTarget.btnEl.innerHTML = `❤️ ${cat.icon} ${cat.name}`;
                        categoryPickerTarget.btnEl.style.background = 'rgba(239, 68, 68, 0.4)';
                        categoryPickerTarget.btnEl.style.borderColor = '#ef4444';
                        categoryPickerTarget.btnEl.style.color = '#ffffff';
                      }
                    }
                    setCategoryPickerTarget(null);
                  }}
                  style={{
                    background: `${cat.color || '#00f2fe'}22`,
                    border: `1px solid ${cat.color || '#00f2fe'}66`,
                    color: cat.color || '#00f2fe',
                    borderRadius: '8px',
                    padding: '6px 10px',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.04)'}
                  onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                >
                  <span>{cat.icon || '📁'}</span>
                  <span>{cat.name}</span>
                </button>
              ))}
            </div>

            <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8' }}>
                Oppure crea un nuovo genere/categoria al volo:
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={newCatInlineName}
                  onChange={(e) => setNewCatInlineName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newCatInlineName.trim()) {
                      if (saveYouTubeFavorite) {
                        saveYouTubeFavorite({
                          id: categoryPickerTarget.id,
                          title: categoryPickerTarget.title,
                          categoryName: newCatInlineName.trim()
                        });
                        if (categoryPickerTarget.btnEl) {
                          categoryPickerTarget.btnEl.innerHTML = `❤️ ${newCatInlineName.trim()}`;
                          categoryPickerTarget.btnEl.style.background = 'rgba(239, 68, 68, 0.4)';
                          categoryPickerTarget.btnEl.style.borderColor = '#ef4444';
                          categoryPickerTarget.btnEl.style.color = '#ffffff';
                        }
                      }
                      setNewCatInlineName('');
                      setCategoryPickerTarget(null);
                    }
                  }}
                  placeholder="es. Cyberpunk Coding, Metal Gym..."
                  style={{
                    flex: 1,
                    background: '#1e293b',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '8px',
                    padding: '8px 10px',
                    color: '#ffffff',
                    fontSize: '0.78rem'
                  }}
                />
                <button
                  onClick={() => {
                    if (newCatInlineName.trim() && saveYouTubeFavorite) {
                      saveYouTubeFavorite({
                        id: categoryPickerTarget.id,
                        title: categoryPickerTarget.title,
                        categoryName: newCatInlineName.trim()
                      });
                      if (categoryPickerTarget.btnEl) {
                        categoryPickerTarget.btnEl.innerHTML = `❤️ ${newCatInlineName.trim()}`;
                        categoryPickerTarget.btnEl.style.background = 'rgba(239, 68, 68, 0.4)';
                        categoryPickerTarget.btnEl.style.borderColor = '#ef4444';
                        categoryPickerTarget.btnEl.style.color = '#ffffff';
                      }
                      setNewCatInlineName('');
                      setCategoryPickerTarget(null);
                    }
                  }}
                  disabled={!newCatInlineName.trim()}
                  style={{
                    background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                    border: 'none',
                    borderRadius: '8px',
                    color: '#000000',
                    fontWeight: 800,
                    fontSize: '0.75rem',
                    padding: '0 14px',
                    cursor: 'pointer',
                    opacity: newCatInlineName.trim() ? 1 : 0.5
                  }}
                >
                  Salva
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}