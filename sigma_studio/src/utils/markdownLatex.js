// ==============================================================================
// markdownLatex.js — Unified Markdown + LaTeX renderer (v1.0)
// Renders markdown with inline KaTeX, zero DOM post-processing needed.
// Solves the previous bug where TreeWalker split() was mishandling LaTeX delimiters.
// ==============================================================================
import katex from 'katex';

// Store KaTeX CSS import is handled by the consuming component

/**
 * Render a LaTeX expression to HTML using KaTeX.
 * Returns raw text on failure.
 */
function renderLatex(expr, displayMode = false) {
  if (!expr || typeof expr !== 'string') return '';
  try {
    return katex.renderToString(expr.trim(), {
      displayMode,
      throwOnError: false,
      output: 'html',
      strict: false,
      trust: true,
    });
  } catch (e) {
    // Fallback: wrap raw expression in a code-like span
    const escaped = expr.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>');
    return `<span class="katex-error">${displayMode ? '$$' : '$'}${escaped}${displayMode ? '$$' : '$'}</span>`;
  }
}

/**
 * Process inline LaTeX ($...$) and display LaTeX ($$...$$) in text,
 * replacing them with KaTeX-rendered HTML.
 * Handles edge cases: escaped dollars, unmatched delimiters, nested usage.
 */
function renderLatexInText(text, katexBlocks = null) {
  if (!text || typeof text !== 'string') return text;

  // Helper: find the position of the next unescaped $, starting from 'start'
  function findUnescapedDollar(str, start) {
    for (let i = start; i < str.length; i++) {
      if (str[i] === '\\' && i + 1 < str.length && str[i + 1] === '$') {
        i++; // skip escaped $
        continue;
      }
      if (str[i] === '$') return i;
    }
    return -1;
  }

  let result = '';
  let i = 0;

  while (i < text.length) {
    const dollarPos = findUnescapedDollar(text, i);
    if (dollarPos === -1) {
      result += text.slice(i);
      break;
    }

    // Add text before the $
    result += text.slice(i, dollarPos);

    // Check if it's $$ (display) or $ (inline)
    if (text[dollarPos + 1] === '$') {
      // Display math: $$...$$
      const endPos = findUnescapedDollar(text, dollarPos + 2);
      if (endPos === -1 || text[endPos + 1] !== '$') {
        // Unmatched $$ — treat as literal
        result += '$$';
        i = dollarPos + 2;
        continue;
      }
      const mathExpr = text.slice(dollarPos + 2, endPos);
      const html = renderLatex(mathExpr, true);
      if (katexBlocks) {
        const idx = katexBlocks.length;
        katexBlocks.push(html);
        result += `%%KATEXBLOCK_${idx}%%`;
      } else {
        result += html;
      }
      i = endPos + 2; // skip past closing $$
    } else {
      // Inline math: $...$
      const endPos = findUnescapedDollar(text, dollarPos + 1);
      if (endPos === -1) {
        // Unmatched $ — treat as literal
        result += '$';
        i = dollarPos + 1;
        continue;
      }
      const mathExpr = text.slice(dollarPos + 1, endPos);
      const html = renderLatex(mathExpr, false);
      if (katexBlocks) {
        const idx = katexBlocks.length;
        katexBlocks.push(html);
        result += `%%KATEXBLOCK_${idx}%%`;
      } else {
        result += html;
      }
      i = endPos + 1; // skip past closing $
    }
  }

  return result;
}


/**
 * Convert paths like data/file.md to clickable links.
 */
function linkifyPaths(text) {
  if (typeof text !== 'string') return '';
  return text.replace(
    /((?:data\/|manifesti\/)[^\s<>"'`]+\.(?:md|py|html|js|jsx|css|json|txt))/gi,
    (match) => `<a class="chat-file-link" title="Apri ${match}" data-path="${match}">📄 ${match}</a>`
  );
}

/**
 * Escape HTML entities in text (for safe insertion)
 */
function escapeHtml(text) {
  var amp = String.fromCharCode(38);
  var lt = String.fromCharCode(60);
  var gt = String.fromCharCode(62);
  var quot = String.fromCharCode(34);
  return String(text)
    .replace(/&/g, amp + 'amp;')
    .replace(/</g, amp + 'lt;')
    .replace(/>/g, amp + 'gt;')
    .replace(/"/g, amp + 'quot;');
}

/**
 * Process inline formatting: bold, italic, inline code, links.
 * Must be called AFTER LaTeX rendering so we don't process $ inside KaTeX HTML.
 */
function processInlineFormatting(text) {
  // Bold: **text**
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text* (but not **)
  text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  // Inline code: `text`
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Links: [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Strikethrough: ~~text~~
  text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
  return text;
}

/**
 * Process block-level markdown elements.
 * Must be called AFTER LaTeX rendering so delimiters inside KaTeX are preserved.
 */
function processBlocks(text) {
  const lines = text.split('\n');
  const result = [];
  let inCodeBlock = false;
  let codeBlockContent = '';
  let codeBlockLang = '';

  let i = 0;
  while (i < lines.length) {
    let line = lines[i];

    // Fenced code blocks
    if (/^```/.test(line.trim())) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
        codeBlockContent = '';
        i++;
        continue;
      } else {
        // Close code block
        inCodeBlock = false;
        const langClass = codeBlockLang ? ` class="language-${escapeHtml(codeBlockLang)}"` : '';
        result.push(`<pre><code${langClass}>${escapeHtml(codeBlockContent)}</code></pre>`);
        i++;
        continue;
      }
    }

    if (inCodeBlock) {
      codeBlockContent += (codeBlockContent ? '\n' : '') + line;
      i++;
      continue;
    }

    // Headings
    if (/^#### (.+)/.test(line)) {
      result.push(`<h4>${line.replace(/^#### /, '')}</h4>`);
      i++;
      continue;
    }
    if (/^### (.+)/.test(line)) {
      result.push(`<h3>${line.replace(/^### /, '')}</h3>`);
      i++;
      continue;
    }
    if (/^## (.+)/.test(line)) {
      result.push(`<h2>${line.replace(/^## /, '')}</h2>`);
      i++;
      continue;
    }
    if (/^# (.+)/.test(line)) {
      result.push(`<h1>${line.replace(/^# /, '')}</h1>`);
      i++;
      continue;
    }

    // Horizontal rule
    if (/^(---|\*\*\*|___)$/.test(line.trim())) {
      result.push('<hr>');
      i++;
      continue;
    }

    // Blockquote
    if (/^>/.test(line) || /^>/.test(line)) {
      const cleanLine = line.replace(/^(?:>|>)\s?/, '');
      result.push(`<blockquote><p>${cleanLine || '&nbsp;'}</p></blockquote>`);
      i++;
      continue;
    }

    // Unordered list
    if (/^[\-\*\+]\s/.test(line)) {
      result.push(`<ul><li>${line.replace(/^[\-\*\+]\s/, '')}</li></ul>`);
      i++;
      continue;
    }

    // Ordered list
    if (/^\d+\.\s/.test(line)) {
      result.push(`<ol><li>${line.replace(/^\d+\.\s/, '')}</li></ol>`);
      i++;
      continue;
    }

    // Empty line → paragraph break
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Regular paragraph
    result.push(`<p>${line}</p>`);
    i++;
  }

  // Handle unclosed code block
  if (inCodeBlock) {
    const langClass = codeBlockLang ? ` class="language-${escapeHtml(codeBlockLang)}"` : '';
    result.push(`<pre><code${langClass}>${escapeHtml(codeBlockContent)}</code></pre>`);
  }

  return result.join('\n');
}

/**
 * Main render function — converts Markdown + LaTeX to HTML.
 * 
 * Pipeline:
 * 1. Extract and protect code blocks (so we don't touch LaTeX inside code)
 * 2. Render LaTeX ($...$ and $$...$$) with KaTeX
 * 3. Apply block-level markdown (headings, lists, blockquotes, paragraphs)
 * 4. Apply inline formatting (bold, italic, code, links)
 * 5. Restore code blocks
 * 6. Apply linkify for file paths
 * 
 * @param {string} text - Raw markdown text with optional LaTeX
 * @returns {string} - HTML string ready for dangerouslySetInnerHTML
 */
export function renderMarkdownLatex(text) {
  try {
    if (!text) return '';
    if (typeof text !== 'string') text = String(text);
    if (!text.trim()) return '';

    // Step 1: Extract and protect fenced code blocks
    const codeBlocks = [];
    let processed = text.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      const langClass = lang ? ` class="language-${escapeHtml(lang)}"` : '';
      codeBlocks.push(`<pre><code${langClass}>${escapeHtml(code.trimEnd())}</code></pre>`);
      return `%%CODEBLOCK_${idx}%%`;
    });

    // Also protect inline code — we'll process it after LaTeX
    const inlineCodes = [];
    processed = processed.replace(/`([^`]+)`/g, (match, code) => {
      const idx = inlineCodes.length;
      inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
      return `%%INLINECODE_${idx}%%`;
    });

    // Convert alternate LaTeX delimiters \(\) and \[\] to standard $$ and $
    processed = processed
      .replace(/\\\[/g, '$$$$')
      .replace(/\\\]/g, '$$$$')
      .replace(/\\\(/g, '$$')
      .replace(/\\\)/g, '$$');

    // Step 2: Render LaTeX and protect the output in an array
    const katexBlocks = [];
    const lines = processed.split('\n');
    const renderedLines = lines.map(line => {
      // Only render LaTeX if the line is not a heading (starts with #)
      if (/^#{1,4}\s/.test(line)) {
        // Render LaTeX only in the heading content (after the #)
        const headingMatch = line.match(/^(#{1,4})\s(.+)$/);
        if (headingMatch) {
          return headingMatch[1] + ' ' + renderLatexInText(headingMatch[2], katexBlocks);
        }
      }
      return renderLatexInText(line, katexBlocks);
    });
    processed = renderedLines.join('\n');

    // Step 3: Restore inline codes (protected from LaTeX rendering)
    processed = processed.replace(/%%INLINECODE_(\d+)%%/g, (match, idx) => {
      return inlineCodes[parseInt(idx)] || match;
    });

    // Step 4: Apply block-level markdown (safe because LaTeX html is placeholderized)
    processed = processBlocks(processed);

    // Step 5: Apply inline formatting (bold, italic, links, strikethrough)
    // But only outside of HTML tags like <h1>, <pre>, <code>, <a>
    processed = processed.replace(/(<[^>]+>)|([^<]+)/g, (match, tag, text) => {
      if (tag) return tag; // Don't touch HTML tags
      if (text) return processInlineFormatting(text);
      return match;
    });

    // Step 6: Restore code blocks
    processed = processed.replace(/%%CODEBLOCK_(\d+)%%/g, (match, idx) => {
      return codeBlocks[parseInt(idx)] || match;
    });

    // Step 6.5: Restore KaTeX HTML blocks safely
    processed = processed.replace(/%%KATEXBLOCK_(\d+)%%/g, (match, idx) => {
      return katexBlocks[parseInt(idx)] || match;
    });

    // Step 7: Linkify file paths
    processed = linkifyPaths(processed);

    return processed;
  } catch (e) {
    // Ultimate fallback: plain text with newlines
    console.error('markdownLatex render error:', e);
    return String(text).replace(/\n/g, '<br>');
  }
}


/**
 * Simple markdown-only renderer (no LaTeX, no KaTeX dependency).
 * Used as a lightweight alternative when LaTeX is not needed.
 */
export function simpleMarkdownOnly(t) {
  try {
    if (!t) return '';
    if (typeof t !== 'string') t = String(t);
    if (!t) return '';

    var s = t;

    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

    // Italic
    s = s.replace(/\*(.+?)\*/g, '<i>$1</i>');

    // Headings
    s = s.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    s = s.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    s = s.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Newlines to <br>
    s = s.replace(/\n/g, '<br>');

    // Wrap in <p> if not a heading
    if (s.indexOf('<h') !== 0) {
      s = '<p>' + s + '</p>';
    }

    return s;
  } catch (e) {
    return String(t).replace(/\n/g, '<br>');
  }
}

export default renderMarkdownLatex;