import React, { useRef, useEffect } from 'react';
import katex from 'katex';
import { marked } from 'marked';
import 'katex/dist/katex.min.css';
import { Bot, User, Terminal, FileText, StopCircle, Loader, ExternalLink } from 'lucide-react';

// ==============================================================================
// MESSAGE BUBBLE — Full markdown rendering with KaTeX (same engine as SigmaLabEditor)
// Uses the `marked` library for proper markdown parsing, then renders LaTeX via KaTeX
// ==============================================================================

// ---- Configure marked to render LaTeX blocks correctly ----
// We override the default paragraph renderer so that $$...$$ and $...$ blocks
// pass through unescaped for KaTeX processing in renderMathInElement

const originalParagraph = marked.Renderer.prototype.paragraph;
marked.use({
  renderer: {
    paragraph(text) {
      // If the text is just a LaTeX display block, don't wrap in <p>
      if (text.trim().startsWith('$$') && text.trim().endsWith('$$')) {
        return text + '\n';
      }
      return `<p>${text}</p>\n`;
    }
  }
});

/**
 * Renderiza formule LaTeX in un elemento HTML dopo che marked ha prodotto il markup.
 * Same implementation as MarkdownPreview.jsx's renderMathInElement.
 */
function renderMathInElement(container) {
  if (!container) return;
  renderMathBlocks(container, '$$', '$$', true);
  renderMathBlocks(container, '$', '$', false);
  renderMathBlocks(container, '\\[', '\\]', true);
  renderMathBlocks(container, '\\(', '\\)', false);
}

function renderMathBlocks(container, leftDelim, rightDelim, displayMode) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);

  for (const node of textNodes) {
    const text = node.textContent;
    if (!text.includes(leftDelim)) continue;

    const parts = text.split(leftDelim);
    if (parts.length < 2) continue;

    const fragment = document.createDocumentFragment();
    let i = 0;

    while (i < parts.length) {
      if (i > 0) {
        const mathContent = parts[i];
        const rightIdx = mathContent.indexOf(rightDelim);

        if (rightIdx !== -1) {
          const beforeText = document.createTextNode(mathContent.substring(0, rightIdx));
          const mathExpr = mathContent.substring(rightIdx + rightDelim.length);

          try {
            const mathEl = document.createElement('span');
            katex.render(mathExpr, mathEl, { displayMode, throwOnError: false, output: 'html' });
            fragment.appendChild(mathEl);
            const afterText = document.createTextNode(mathContent.substring(rightIdx + rightDelim.length));
            fragment.appendChild(afterText);
          } catch (e) {
            fragment.appendChild(document.createTextNode(leftDelim + mathContent));
          }
        } else {
          fragment.appendChild(document.createTextNode(leftDelim + parts[i]));
        }
      } else {
        fragment.appendChild(document.createTextNode(parts[0]));
      }
      i++;
    }

    if (node.parentNode) {
      node.parentNode.replaceChild(fragment, node);
    }
  }
}

/**
 * Converte percorsi Sigma Studio in link cliccabili.
 */
function linkifyPaths(text) {
  return text.replace(
    /((?:data\/|manifesti\/)[^\s<>"'`]+\.(?:md|py|html|js|jsx|css|json|txt))/gi,
    (match) => `<a class="chat-file-link" title="Apri ${match}" data-path="${match}">📄 ${match}</a>`
  );
}

/**
 * Renderer markdown professionale usando la libreria `marked`,
 * con supporto KaTeX per LaTeX e linkify per percorsi file.
 */
function renderMarkdown(text) {
  if (!text) return '';

  // 1. Parse markdown with marked
  let html = marked.parse(text, { breaks: true, gfm: true });

  // 2. Linkify file paths (data/..., manifesti/...)
  html = linkifyPaths(html);

  return html;
}

export default function MessageBubble({ msg, isLast, onStop, onFileLinkClick }) {
  const contentRef = useRef(null);

  // Re-render KaTeX after DOM update
  useEffect(() => {
    if (contentRef.current) {
      renderMathInElement(contentRef.current);
    }
  }, [msg.content]);

  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    const isError = msg.error || msg.content?.startsWith('❌');
    const isAction = msg.isAction;
    return (
      <div className={`chat-message system-message ${isError ? 'error-message' : ''} ${isAction ? 'action-message' : ''}`}>
        <div className="system-icon">
          {isError ? <Terminal size={14} /> : isAction ? <FileText size={14} /> : <Loader size={14} />}
        </div>
        <span className="system-text" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
      </div>
    );
  }

  return (
    <div className={`chat-message ${isUser ? 'user-message' : 'ai-message'}`}>
      <div className="message-avatar">
        {isUser ? <User size={16} /> : <Bot size={16} />}
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
                ref={el => el && renderMathInElement(el)}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.thinking) }}
              />
            </details>
          </div>
        )}

        {/* Main message content — rendered with marked + KaTeX */}
        <div
          ref={contentRef}
          className="message-text chat-md"
          onClick={e => {
            const link = e.target.closest('.chat-file-link');
            if (link && onFileLinkClick) {
              e.preventDefault();
              onFileLinkClick(link.dataset.path);
            }
          }}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
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