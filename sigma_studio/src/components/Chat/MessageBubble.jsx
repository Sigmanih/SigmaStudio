import React from 'react';
import katex from 'katex';
import { Bot, User, Terminal, FileText, StopCircle, Loader, ExternalLink } from 'lucide-react';

// ==============================================================================
// MESSAGE BUBBLE — Markdown + file links + thinking
// ==============================================================================

/**
 * Converte percorsi Sigma Studio completi in link cliccabili.
 * Supporta solo percorsi che iniziano con data/ o manifesti/ per evitare link rotti.
 */
function linkifyPaths(text) {
  return text.replace(
    /((?:data\/|manifesti\/)[^\s<>"'`]+\.(?:md|py|html|js|jsx|css|json|txt))/gi,
    (match) => `<a class="chat-file-link" title="Apri ${match}" data-path="${match}">📄 ${match}</a>`
  );
}

/**
 * Renderizza formule LaTeX inline ($...$) e display ($$...$$) con KaTeX.
 * I blocchi $$ vengono processati prima per non interferire con gli inline.
 */
function renderLatex(html) {
  // Display math: $$ ... $$
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false });
    } catch (e) {
      return `<div class="katex-error">⚠️ Errore formula: ${formula.trim()}</div>`;
    }
  });
  // Inline math: $ ... $ (match anche singoli caratteri come $m$, $n$, $x>0$)
  html = html.replace(/\$([^$]+)\$/g, (_, formula) => {
    const trimmed = formula.trim();
    if (!trimmed) return '$ $';
    try {
      return katex.renderToString(trimmed, { displayMode: false, throwOnError: false });
    } catch (e) {
      // Se KaTeX fallisce, renderizza comunque in italico per leggibilità
      return `<span class="chat-math">${trimmed}</span>`;
    }
  });
  return html;
}

/**
 * Renderer Markdown semplificato ma robusto:
 * - Code blocks (```) con <pre><code>
 * - Inline code (`)
 * - Bold (**), italic (*)
 * - Headers h1-h4
 * - Tables (| ... |)
 * - Unordered lists (- items)
 * - Newline → <br/>
 * - File path links
 * - LaTeX math ($...$ e $$...$$) via KaTeX (processato PRIMA delle <br/> per preservare multi-line $$)
 */
function renderMarkdown(text) {
  let html = text
    // Escape HTML entities (safe default)
    .replace(/&/g, '&' + 'amp;')
    .replace(/</g, '&' + 'lt;')
    .replace(/>/g, '&' + 'gt;')
    // Code blocks first (to avoid processing markdown inside)
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Headers (must be before line breaks)
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Tables: | col1 | col2 | (preserve \n inside table rows temporarily)
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map(c => c.trim()).filter(c => c);
      if (cells.length > 0 && cells.every(c => /^-+$/.test(c.replace(/:+/g, '')))) {
        return '';
      }
      return `<tr>${cells.map(c => c.startsWith('**') && c.endsWith('**') ? `<th>${c.slice(2, -2)}</th>` : `<td>${c}</td>`).join('')}</tr>`;
    })
    // Wrap table rows in table
    .replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table class="chat-table">$1</table>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');

  // Convert Markdown links [text](url) to <a> tags (before LaTeX which may contain brackets)
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // Autolink bare URLs (not already in <a> tags)
  html = html.replace(
    /(?<![">])(https?:\/\/[^\s<>\[\]()]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // Linkify file paths (before line breaks, paths may contain slashes)
  html = linkifyPaths(html);

  // Render LaTeX math BEFORE converting \n to <br/> to preserve multi-line $$...$$
  html = renderLatex(html);

  // Line breaks: skip inside <pre>, <table>, <svg> blocks
  html = html.replace(/\n\n/g, '<br/><br/>');
  
  // Protect special blocks from newline conversion
  const blocks = [];
  html = html.replace(/(<pre[\s\S]*?<\/pre>|<table[\s\S]*?<\/table>|<svg[\s\S]*?<\/svg>)/g, (match) => {
    blocks.push(match);
    return `%%BLOCK${blocks.length - 1}%%`;
  });
  
  html = html.replace(/\n/g, '<br/>');
  
  // Restore protected blocks
  html = html.replace(/%%BLOCK(\d+)%%/g, (_, i) => blocks[parseInt(i)]);

  return html;
}

/**
 * Quando l'utente clicca su un link-file nella chat,
 * invia un evento per aprirlo nel workspace di Sigma Studio.
 */
function handleFileLinkClick(e) {
  const anchor = e.target.closest('.chat-file-link');
  if (!anchor) return;
  e.preventDefault();
  const path = anchor.getAttribute('data-path');
  if (path) {
    window.dispatchEvent(new CustomEvent('sigma-open-file', { detail: { path } }));
  }
}

export default function MessageBubble({ msg, msgId, expandedThinking, onToggleThinking, effectiveModelName, onStop, loading }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (loading) {
    return (
      <div className="chat-message chat-assistant">
      <div className="chat-avatar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
        </svg>
      </div>
        <div className="chat-bubble">
          <div className="chat-loading">
            <Loader size={16} className="spin" /> L'IA sta scrivendo...
            {onStop && <button className="chat-stop-btn" onClick={onStop} title="Interrompi"><StopCircle size={16} /></button>}
          </div>
          <div className="chat-loading-cursor">▊</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`chat-message ${isUser ? 'chat-user' : isSystem ? 'chat-system' : 'chat-assistant'}`}>
      <div className="chat-avatar">
        {isUser ? <User size={14} /> : isSystem ? <Terminal size={14} /> : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
          </svg>
        )}
      </div>
      <div className="chat-bubble">
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

        {/* Native model thinking / reasoning — visually distinct, collapsible */}
        {!isUser && !isSystem && msg.thinking && (
          <div className={`chat-thinking ${msg.streamingThinking ? 'chat-thinking-streaming' : ''}`}>
            <button className="chat-thinking-toggle" onClick={() => onToggleThinking(msgId)}>
              <span>
                🧠 {msg.streamingThinking
                  ? <span className="chat-thinking-live"><span className="thinking-pulse"></span> Ragionando...</span>
                  : (expandedThinking[msgId] ? 'Nascondi ragionamento nativo' : 'Mostra ragionamento nativo')
                }
              </span>
            </button>
            {(msg.streamingThinking || expandedThinking[msgId]) && (
              <div
                className="chat-thinking-content"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.thinking) }}
              />
            )}
          </div>
        )}

        {/* Main content */}
        {msg.isAction
          ? (
            <div className="chat-actions-log">
              {msg.content.split('\n').map((l, j) => (
                <div key={j} className="action-line">{l}</div>
              ))}
            </div>
          )
          : (
            <div
              className="chat-content"
              onClick={handleFileLinkClick}
              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
            />
          )
        }

        {/* Error indicator */}
        {msg.error && <div className="chat-error">⚠️ {msg.error}</div>}

        {/* Timestamp & agent name */}
        <div className="chat-timestamp">
          {new Date(msg.timestamp).toLocaleTimeString()}
          {!isSystem && (
            <span className="chat-message-agent"> · {msg.agentName || effectiveModelName}</span>
          )}
        </div>
      </div>
    </div>
  );
}