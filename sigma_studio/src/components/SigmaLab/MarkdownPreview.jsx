import React, { useState, useEffect, useRef } from 'react';
import { marked } from 'marked';
import katex from 'katex';
import mermaid from 'mermaid';

// Load KaTeX CSS
import 'katex/dist/katex.min.css';

// ==============================================================================
// MarkdownPreview — Visualizzatore Markdown professionale con KaTeX e Mermaid
// Porting di web_explorer/md_viewer.html in React
// ==============================================================================

// Configure mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true },
});

export default function MarkdownPreview({ path, onBack, onDelete }) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!path) return;
    setLoading(true);
    fetch(`/api/get_file?path=${encodeURIComponent(path)}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setContent(data.content);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [path]);

  // Render markdown with KaTeX + Mermaid after content loads
  useEffect(() => {
    if (!content || !containerRef.current) return;
    renderContent();
  }, [content]);

  const renderContent = async () => {
    const container = containerRef.current;
    if (!container) return;

    // Parse markdown to HTML
    const html = marked.parse(content);
    container.innerHTML = html;

    // ---- Render KaTeX ----
    // Find all elements that might contain LaTeX
    renderMathInElement(container);

    // ---- Render Mermaid ----
    const mermaidBlocks = container.querySelectorAll('.language-mermaid');
    for (let i = 0; i < mermaidBlocks.length; i++) {
      const block = mermaidBlocks[i];
      const raw = block.textContent;
      const wrapper = document.createElement('div');
      wrapper.className = 'mermaid-wrapper';
      wrapper.id = `mermaid-render-${i}`;
      
      const pre = block.closest('pre') || block;
      if (pre.parentNode) {
        pre.parentNode.replaceChild(wrapper, pre);
      }

      try {
        const { svg } = await mermaid.render(`mermaid-svg-${i}`, raw);
        wrapper.innerHTML = svg;
      } catch (err) {
        wrapper.innerHTML = `<div class="mermaid-error">
          <strong>Mermaid Error:</strong> ${err.message}
        </div>`;
      }
    }

    // ---- Intercept links for in-app navigation ----
    container.querySelectorAll('a[href]').forEach(link => {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('http') && !href.startsWith('https') && !href.startsWith('#') && !href.startsWith('mailto:')) {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          // For relative links, we could navigate within the app
          // For now, just open in new tab as fallback
          window.open(href, '_blank');
        });
        link.style.cursor = 'pointer';
      }
    });
  };

  const handleDelete = () => {
    if (confirm(`Sei sicuro di voler eliminare: ${path}?`)) {
      fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            if (onBack) onBack();
          }
        });
    }
  };

  if (loading) return <div className="placeholder-content md-loading">Caricamento documento...</div>;
  if (!content) return <div className="placeholder-content md-loading">Documento vuoto o non trovato</div>;

  return (
    <div className="markdown-preview">
      <style>{`
        .markdown-preview {
          height: 100%;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .md-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: #5a5e72;
          font-size: 0.85rem;
        }
        .md-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 16px;
          background: rgba(20, 20, 24, 0.95);
          border-bottom: 1px solid #1e2030;
          flex-shrink: 0;
          gap: 12px;
        }
        .md-path {
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.7rem;
          color: #5a5e72;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .md-actions {
          display: flex;
          gap: 8px;
          flex-shrink: 0;
        }
        .md-actions button {
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 0.7rem;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid #1e2030;
          background: transparent;
          color: #8b8fa3;
          font-family: inherit;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .md-actions button:hover { background: rgba(255,255,255,0.05); color: #e2e4eb; }
        .md-actions .btn-delete { color: #ff6b6b; }
        .md-actions .btn-delete:hover { background: rgba(255,107,107,0.1); }
        
        /* Scrolling content area */
        .md-content {
          flex: 1;
          overflow-y: auto;
          padding: 40px;
          display: flex;
          justify-content: center;
          background: #fdfdfc;
        }
        .md-viewer {
          width: 100%;
          max-width: 800px;
          color: #1a1a1a;
          font-family: 'Crimson Pro', 'Georgia', serif;
          font-size: 1.1rem;
          line-height: 1.8;
          min-height: 100%;
        }
        .md-viewer h1 {
          font-family: 'Outfit', 'Segoe UI', sans-serif;
          font-size: 2.6rem;
          border-bottom: 2px solid #0076db;
          padding-bottom: 15px;
          margin-bottom: 30px;
          letter-spacing: -1px;
          font-weight: 700;
        }
        .md-viewer h2 {
          font-family: 'Outfit', 'Segoe UI', sans-serif;
          font-size: 1.8rem;
          border-bottom: 1px solid #ddd;
          padding-bottom: 8px;
          margin-top: 2em;
          font-weight: 600;
        }
        .md-viewer h3 {
          font-family: 'Outfit', 'Segoe UI', sans-serif;
          font-size: 1.4rem;
          margin-top: 1.5em;
          font-weight: 600;
        }
        .md-viewer p { margin: 1.2em 0; }
        .md-viewer blockquote {
          border-left: 4px solid #0076db;
          background: #f7f9fc;
          padding: 16px 20px;
          font-style: italic;
          margin: 20px 0;
        }
        .md-viewer table {
          width: 100%;
          border-collapse: collapse;
          margin: 30px 0;
        }
        .md-viewer th, .md-viewer td {
          border: 1px solid #ddd;
          padding: 12px;
          text-align: left;
        }
        .md-viewer th { background: #f7f7f7; }
        .md-viewer pre {
          background: #f8f8f8;
          padding: 20px;
          border-radius: 8px;
          overflow-x: auto;
          border: 1px solid #eee;
          font-family: 'JetBrains Mono', 'Consolas', monospace;
          font-size: 0.85rem;
        }
        .md-viewer code {
          font-family: 'JetBrains Mono', 'Consolas', monospace;
          font-size: 0.85rem;
        }
        .md-viewer img { max-width: 100%; border-radius: 8px; margin: 20px 0; }
        .md-viewer ul, .md-viewer ol { margin: 1em 0; padding-left: 2em; }
        .md-viewer li { margin: 0.4em 0; }
        
        /* Mermaid */
        .md-viewer .mermaid-wrapper {
          width: 100%;
          margin: 30px auto;
          overflow-x: auto;
          overflow-y: hidden;
          background: #fafafa;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          padding: 20px 0;
        }
        .md-viewer .mermaid-wrapper svg {
          display: block;
          margin: 0 auto;
          max-width: 100%;
          height: auto;
        }
        .md-viewer .mermaid-error {
          color: #c00;
          padding: 20px;
          border: 1px dashed #c00;
          border-radius: 8px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 0.8rem;
        }

        /* KaTeX */
        .md-viewer .katex-display { margin: 2em 0; overflow-x: auto; overflow-y: hidden; }
        .md-viewer .katex { font-size: 1.1em; }

        @media print {
          .markdown-preview { background: #fff; }
          .md-header { display: none; }
          .md-content { padding: 0; }
          .md-viewer { max-width: none; }
          pre, blockquote, img, table, .katex-display { page-break-inside: avoid; }
          h1, h2, h3 { page-break-after: avoid; }
        }
      `}</style>

      <div className="md-header">
        <span className="md-path">{path}</span>
        <div className="md-actions">
          {onDelete && (
            <button className="btn-delete" onClick={handleDelete}>
              🗑️ Elimina
            </button>
          )}
        </div>
      </div>

      <div className="md-content">
        <div ref={containerRef} className="md-viewer"></div>
      </div>
    </div>
  );
}

// ---- KaTeX rendering helper (port from md_viewer logic) ----
function renderMathInElement(container) {
  if (!container) return;

  // Process $$ ... $$ (display math)
  renderMathBlocks(container, '$$', '$$', true);
  // Process $ ... $ (inline math)
  renderMathBlocks(container, '$', '$', false);
  // Process \\[ ... \\] (display math)
  renderMathBlocks(container, '\\[', '\\]', true);
  // Process \\( ... \\) (inline math)
  renderMathBlocks(container, '\\(', '\\)', false);
}

function renderMathBlocks(container, leftDelim, rightDelim, displayMode) {
  // Walk all text nodes and find math delimiters
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
            katex.render(mathExpr, mathEl, {
              displayMode,
              throwOnError: false,
              output: 'html'
            });
            fragment.appendChild(mathEl);
            
            // Remaining text after math
            const afterText = document.createTextNode(mathContent.substring(rightIdx + rightDelim.length));
            fragment.appendChild(afterText);
          } catch (e) {
            // Fallback: render as text
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