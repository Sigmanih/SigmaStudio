// ==============================================================================
// exportChatPdf.js — Esportazione PDF / Stampa conversazione Chat per Sigma Studio
// Formattazione tipografica pulita, supporto Markdown, KaTeX, codice e thinking.
// Ottimizzato per impaginazione continua senza sprechi o spazi vuoti.
// ==============================================================================
import { renderMarkdownLatex } from './markdownLatex';

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatDate(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleString('it-IT', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(ts);
  }
}

/**
 * Pulisce l'HTML da paragrafi vuoti e interruzioni multiple che generano buchi vuoti nella stampa.
 */
function cleanPrintHtml(html) {
  if (!html) return '';
  return html
    .replace(/<p>\s*(?:<br\s*\/?>)?\s*<\/p>/gi, '')
    .replace(/(?:<br\s*\/?>\s*){3,}/gi, '<br><br>');
}

/**
 * Esporta la conversazione in un layout PDF professionale pronto per la stampa o il salvataggio in PDF.
 * @param {Object} params
 * @param {Object} params.session - Oggetto sessione ({ id, name, model, createdAt })
 * @param {Array} params.messages - Elenco dei messaggi della chat
 * @param {string} [params.selectedModel] - Modello attivo di fallback
 * @param {string} [params.userName] - Nome utente (default: 'Tu')
 */
export function exportChatPdf({ session, messages, selectedModel, userName = 'Tu' }) {
  if (!messages || messages.length === 0) {
    alert('Nessun messaggio presente nella conversazione da esportare.');
    return;
  }

  // Filtra messaggi vuoti o di solo caricamento in corso
  const printableMessages = messages.filter(m => {
    if (!m) return false;
    const hasContent = m.content && String(m.content).trim().length > 0;
    const hasThinking = m.thinking && String(m.thinking).trim().length > 0;
    return hasContent || hasThinking;
  });

  if (printableMessages.length === 0) {
    alert('Nessun messaggio con contenuto testuale da esportare.');
    return;
  }

  const sessionTitle = session?.name || 'Conversazione AI';
  const effectiveModel = session?.model || selectedModel || 'Sigma AI';
  const exportDateStr = formatDate(new Date().toISOString());

  // Raccogli fogli di stile KaTeX e font dal documento corrente
  let externalStyles = '';
  try {
    const styleTags = document.querySelectorAll('link[rel="stylesheet"], style');
    styleTags.forEach(el => {
      if (el.tagName.toLowerCase() === 'link' && el.href && (el.href.includes('katex') || el.href.includes('prism'))) {
        externalStyles += el.outerHTML + '\n';
      } else if (el.tagName.toLowerCase() === 'style' && el.innerHTML.includes('katex')) {
        externalStyles += el.outerHTML + '\n';
      }
    });
  } catch (e) {
    console.warn('Impossibile estrarre stili KaTeX:', e);
  }

  // Genera l'HTML dei messaggi
  const messagesHtml = printableMessages.map((msg, index) => {
    const isUser = msg.role === 'user';
    const isSystem = msg.role === 'system';
    const timestampStr = formatDate(msg.timestamp || msg.time);
    const roleLabel = isUser
      ? (msg.userName || userName || 'Tu')
      : isSystem
      ? 'Sistema'
      : (msg.agentRole || msg.agentName || effectiveModel || 'Sigma AI');

    const roleIcon = isUser ? '👤' : isSystem ? '⚙️' : '🤖';
    const badgeClass = isUser ? 'badge-user' : isSystem ? 'badge-system' : 'badge-ai';
    const cardClass = isUser ? 'msg-user' : isSystem ? 'msg-system' : 'msg-ai';

    let thinkingHtml = '';
    if (msg.thinking && String(msg.thinking).trim().length > 0) {
      const renderedThinking = cleanPrintHtml(renderMarkdownLatex(msg.thinking));
      thinkingHtml = `
        <div class="pdf-thinking-box">
          <div class="pdf-thinking-title">🧠 Ragionamento:</div>
          <div class="pdf-thinking-content">${renderedThinking}</div>
        </div>
      `;
    }

    const contentHtml = msg.content ? cleanPrintHtml(renderMarkdownLatex(msg.content)) : '';

    let filesHtml = '';
    if (Array.isArray(msg.files) && msg.files.length > 0) {
      filesHtml = `
        <div class="pdf-files-container">
          <span class="pdf-files-label">📎 File allegati:</span>
          ${msg.files.map(f => `<span class="pdf-file-chip">📄 ${escapeHtml(f.filename || f.path || 'Allegato')}</span>`).join(' ')}
        </div>
      `;
    }

    return `
      <div class="pdf-message-wrapper ${cardClass}">
        <div class="pdf-message-header">
          <span class="pdf-role-badge ${badgeClass}">${roleIcon} ${escapeHtml(roleLabel)}</span>
          ${timestampStr ? `<span class="pdf-msg-timestamp">${escapeHtml(timestampStr)}</span>` : ''}
          <span class="pdf-msg-index">#${index + 1}</span>
        </div>
        ${thinkingHtml}
        <div class="pdf-message-body">
          ${contentHtml}
        </div>
        ${filesHtml}
      </div>
    `;
  }).join('\n');

  // Documento HTML completo per la stampa
  const fullHtml = `<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(sessionTitle)} — Sigma Studio</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css" crossorigin="anonymous">
  ${externalStyles}
  <style>
    @page {
      size: A4;
      margin: 10mm 10mm 10mm 10mm;
      @bottom-right {
        content: counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #64748b;
      }
    }

    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 9.5pt;
      line-height: 1.45;
      color: #0f172a;
      background: #ffffff;
      margin: 0;
      padding: 0;
    }

    /* Intestazione Documento Compatta */
    .pdf-header-container {
      border-bottom: 1.5px solid #cbd5e1;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }

    .pdf-header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }

    .pdf-brand {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .pdf-brand-icon {
      font-size: 16pt;
      font-weight: 800;
      color: #0284c7;
      line-height: 1;
    }

    .pdf-brand-text {
      display: flex;
      flex-direction: column;
    }

    .pdf-brand-title {
      font-size: 12pt;
      font-weight: 800;
      letter-spacing: 0.3px;
      color: #0f172a;
      line-height: 1.1;
    }

    .pdf-brand-sub {
      font-size: 7.5pt;
      color: #64748b;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .pdf-meta-box {
      text-align: right;
      font-size: 8pt;
      color: #475569;
      line-height: 1.3;
    }

    .pdf-session-title {
      font-size: 13pt;
      font-weight: 700;
      color: #1e293b;
      margin: 4px 0 6px 0;
      line-height: 1.25;
    }

    .pdf-meta-pills {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 4px;
    }

    .pdf-pill {
      font-size: 8pt;
      padding: 2px 7px;
      border-radius: 4px;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      color: #334155;
      font-weight: 500;
    }

    /* Contenitore Messaggi — Flussione Continua */
    .pdf-messages-list {
      display: block;
    }

    /* Singolo messaggio: non blocca la pagina, scorre naturalmente */
    .pdf-message-wrapper {
      border-radius: 6px;
      padding: 8px 12px;
      margin-bottom: 8px;
      page-break-inside: auto;
      break-inside: auto;
    }

    /* Stile Messaggio Utente */
    .pdf-message-wrapper.msg-user {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-left: 3.5px solid #0284c7;
    }

    /* Stile Messaggio AI */
    .pdf-message-wrapper.msg-ai {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-left: 3.5px solid #10b981;
    }

    /* Stile Messaggio Sistema */
    .pdf-message-wrapper.msg-system {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-left: 3.5px solid #64748b;
      font-size: 9pt;
      padding: 6px 10px;
    }

    .pdf-message-header {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 6px;
      font-size: 8.5pt;
      page-break-after: avoid;
      break-after: avoid;
    }

    .pdf-role-badge {
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 8pt;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }

    .badge-user {
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }

    .badge-ai {
      background: #d1fae5;
      color: #065f46;
      border: 1px solid #a7f3d0;
    }

    .badge-system {
      background: #e2e8f0;
      color: #334155;
      border: 1px solid #cbd5e1;
    }

    .pdf-msg-timestamp {
      color: #64748b;
      font-size: 8pt;
    }

    .pdf-msg-index {
      margin-left: auto;
      color: #94a3b8;
      font-size: 7.5pt;
      font-family: monospace;
    }

    /* Box Ragionamento (Thinking) */
    .pdf-thinking-box {
      margin: 4px 0 8px 0;
      padding: 6px 10px;
      background: #f8fafc;
      border: 1px dashed #cbd5e1;
      border-radius: 4px;
      font-size: 8.5pt;
      color: #475569;
      page-break-inside: auto;
      break-inside: auto;
    }

    .pdf-thinking-title {
      font-weight: 700;
      color: #475569;
      margin-bottom: 2px;
      font-size: 8pt;
    }

    .pdf-thinking-content {
      font-style: italic;
      line-height: 1.4;
    }

    .pdf-message-body {
      font-size: 9.5pt;
      line-height: 1.45;
      color: #0f172a;
    }

    .pdf-message-body p {
      margin: 0 0 4px 0;
    }

    .pdf-message-body p:last-child {
      margin-bottom: 0;
    }

    /* Tipografia Markdown e blocchi codice compatti */
    h1, h2, h3, h4, h5, h6 {
      color: #0f172a;
      margin: 8px 0 4px 0;
      page-break-after: avoid;
      break-after: avoid;
      font-weight: 700;
    }

    h1 { font-size: 12pt; border-bottom: 1px solid #e2e8f0; padding-bottom: 2px; }
    h2 { font-size: 11pt; }
    h3 { font-size: 10pt; }

    ul, ol {
      margin: 3px 0 4px 16px;
      padding: 0;
    }

    li {
      margin-bottom: 2px;
    }

    blockquote {
      margin: 5px 0;
      padding: 4px 10px;
      background: #f8fafc;
      border-left: 3px solid #94a3b8;
      color: #475569;
      font-style: italic;
      page-break-inside: auto;
      break-inside: auto;
    }

    /* Blocchi di codice continui */
    pre, .chat-code-block-wrapper {
      background: #f8fafc !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 4px;
      margin: 6px 0;
      padding: 0;
      overflow: hidden;
      page-break-inside: auto;
      break-inside: auto;
    }

    .chat-code-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #e2e8f0;
      padding: 3px 8px;
      font-size: 7.5pt;
      font-weight: 600;
      color: #334155;
      font-family: monospace;
    }

    pre {
      padding: 8px 10px !important;
      margin: 0 !important;
      font-family: "JetBrains Mono", Consolas, Monaco, "Courier New", monospace !important;
      font-size: 8.5pt !important;
      line-height: 1.4 !important;
      white-space: pre-wrap !important;
      word-break: break-all !important;
      color: #0f172a !important;
    }

    code {
      font-family: "JetBrains Mono", Consolas, Monaco, "Courier New", monospace !important;
      font-size: 8.5pt;
      background: #f1f5f9;
      padding: 1px 3px;
      border-radius: 2px;
      border: 1px solid #e2e8f0;
      color: #0369a1;
    }

    /* Tabelle */
    table, .chat-table {
      width: 100%;
      border-collapse: collapse;
      margin: 6px 0;
      font-size: 8.5pt;
      page-break-inside: auto;
      break-inside: auto;
    }

    th, td {
      border: 1px solid #cbd5e1;
      padding: 4px 8px;
      text-align: left;
    }

    th {
      background: #f1f5f9;
      font-weight: 700;
      color: #1e293b;
    }

    /* Nascondi bottoni interattivi, iframe video e widget nella stampa */
    button,
    iframe,
    video,
    audio,
    .chat-copy-code-btn,
    .chat-yt-fav-btn,
    .chat-yt-play-radio-btn,
    .youtube-preview-card,
    .no-print {
      display: none !important;
    }

    /* Allegati */
    .pdf-files-container {
      margin-top: 6px;
      padding-top: 4px;
      border-top: 1px solid #e2e8f0;
      font-size: 8pt;
      display: flex;
      align-items: center;
      gap: 5px;
      flex-wrap: wrap;
    }

    .pdf-files-label {
      font-weight: 600;
      color: #64748b;
    }

    .pdf-file-chip {
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 3px;
      padding: 1px 5px;
      color: #334155;
      font-family: monospace;
      font-size: 7.5pt;
    }

    /* KaTeX formule */
    .katex-display {
      margin: 4px 0 !important;
      page-break-inside: auto;
      break-inside: auto;
    }

    /* Footer documento compatto */
    .pdf-footer {
      margin-top: 16px;
      border-top: 1px solid #e2e8f0;
      padding-top: 6px;
      display: flex;
      justify-content: space-between;
      font-size: 7.5pt;
      color: #94a3b8;
    }
  </style>
</head>
<body>
  <div class="pdf-header-container">
    <div class="pdf-header-top">
      <div class="pdf-brand">
        <span class="pdf-brand-icon">Σ</span>
        <div class="pdf-brand-text">
          <span class="pdf-brand-title">Sigma Studio</span>
          <span class="pdf-brand-sub">AI Chat Conversation Report</span>
        </div>
      </div>
      <div class="pdf-meta-box">
        <div><strong>Data:</strong> ${escapeHtml(exportDateStr)}</div>
        <div><strong>Modello:</strong> ${escapeHtml(effectiveModel)}</div>
      </div>
    </div>
    <div class="pdf-session-title">${escapeHtml(sessionTitle)}</div>
    <div class="pdf-meta-pills">
      <span class="pdf-pill">💬 ${printableMessages.length} messaggi</span>
      <span class="pdf-pill">🤖 ${escapeHtml(effectiveModel)}</span>
      <span class="pdf-pill">📅 ${escapeHtml(exportDateStr)}</span>
    </div>
  </div>

  <div class="pdf-messages-list">
    ${messagesHtml}
  </div>

  <div class="pdf-footer">
    <span>Sigma Studio • Conversazione AI archiviata</span>
    <span>Pagina generata il ${escapeHtml(exportDateStr)}</span>
  </div>
</body>
</html>`;

  // Crea iframe nascosto per isolare la stampa
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = 'none';
  iframe.style.zIndex = '-9999';
  iframe.title = 'Sigma Chat PDF Export';
  document.body.appendChild(iframe);

  try {
    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(fullHtml);
    doc.close();

    const triggerPrint = () => {
      try {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
      } catch (err) {
        console.error('Errore durante la stampa del PDF:', err);
      } finally {
        setTimeout(() => {
          if (iframe.parentNode) {
            iframe.parentNode.removeChild(iframe);
          }
        }, 1500);
      }
    };

    if (iframe.contentWindow.document.readyState === 'complete') {
      setTimeout(triggerPrint, 300);
    } else {
      iframe.onload = () => setTimeout(triggerPrint, 300);
    }
  } catch (e) {
    console.error('Errore durante la creazione del frame di stampa:', e);
    if (iframe.parentNode) {
      iframe.parentNode.removeChild(iframe);
    }
  }
}

export default exportChatPdf;
