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
    /((?:data\/|manifesti\/)[^\s<>"'`]+\.(?:md|py|html|js|jsx|css|json|txt|png|jpg|jpeg|webp|svg|gif))/gi,
    (match) => {
      const isImage = /\.(?:png|jpg|jpeg|webp|svg|gif)$/i.test(match);
      if (isImage) {
        return `<div class="chat-image-preview-card"><img src="/${match}" class="chat-inline-image" loading="lazy" /><span class="chat-image-caption">📄 ${match}</span></div>`;
      }
      return `<a class="chat-file-link" title="Apri ${match}" data-path="${match}">📄 ${match}</a>`;
    }
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
 * Extract YouTube video metadata (id and title) from text or markdown links.
 */
function extractYouTubeVideos(text) {
  if (!text || typeof text !== 'string') return [];
  const results = [];
  const seen = new Set();

  // 1. Markdown link format: [Title](https://www.youtube.com/watch?v=ID)
  const mdRegex = /\[([^\]]+)\]\((?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})[^\)]*\)/gi;
  let mdMatch;
  while ((mdMatch = mdRegex.exec(text)) !== null) {
    const title = mdMatch[1].trim();
    const id = mdMatch[2];
    if (id && !seen.has(id)) {
      seen.add(id);
      results.push({ id, title: title || 'Video YouTube' });
    }
  }

  // 2. Direct URLs or embedded IDs
  const rawRegex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/gi;
  let rawMatch;
  while ((rawMatch = rawRegex.exec(text)) !== null) {
    const id = rawMatch[1];
    if (id && !seen.has(id)) {
      seen.add(id);
      results.push({ id, title: 'Video YouTube' });
    }
  }

  return results;
}

function escapeAttr(str) {
  if (!str) return '';
  return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Generate YouTube responsive video preview HTML block for a list of video objects or IDs.
 */
function generateYouTubePreviewsHtml(videoList) {
  if (!videoList || videoList.length === 0) return '';
  
  const cards = videoList.map(v => {
    const id = typeof v === 'string' ? v : v.id;
    const title = (typeof v === 'object' && v.title) ? v.title : 'Video Musicale YouTube';
    const escapedTitle = escapeAttr(title);

    return `
<div class="youtube-preview-card" style="margin: 12px 0 6px 0; border-radius: 12px; overflow: hidden; background: #0c0e17; border: 1px solid rgba(0, 210, 255, 0.25); max-width: 620px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); transition: transform 0.2s ease, border-color 0.2s ease;">
  <div style="padding: 10px 14px; background: rgba(14, 17, 28, 0.95); border-bottom: 1px solid rgba(255, 255, 255, 0.06); display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
    <div style="display: flex; align-items: center; gap: 8px; overflow: hidden; min-width: 140px; flex: 1;">
      <span style="display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: #ff0000; color: #fff; font-size: 0.65rem; flex-shrink: 0; box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);">▶</span>
      <span style="font-size: 0.82rem; font-weight: 700; color: #f1f5f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapedTitle}">${escapedTitle}</span>
    </div>
    
    <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
      <button class="chat-yt-fav-btn" data-yt-id="${id}" data-yt-title="${escapedTitle}" title="Salva nei Preferiti di Sigma Radio" style="display: inline-flex; align-items: center; gap: 4px; padding: 4px 9px; border-radius: 6px; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.35); color: #ef4444; font-size: 0.72rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease;">
        ❤️ Preferiti
      </button>
      <button class="chat-yt-play-radio-btn" data-yt-id="${id}" data-yt-title="${escapedTitle}" title="Ascolta in background su Sigma Radio" style="display: inline-flex; align-items: center; gap: 4px; padding: 4px 9px; border-radius: 6px; background: rgba(0, 242, 254, 0.15); border: 1px solid rgba(0, 242, 254, 0.35); color: #00f2fe; font-size: 0.72rem; font-weight: 700; cursor: pointer; transition: all 0.15s ease;">
        ▶ Riproduci
      </button>
      <a href="https://www.youtube.com/watch?v=${id}" target="_blank" rel="noopener noreferrer" class="chat-external-link" style="font-size: 0.72rem; color: #94a3b8; text-decoration: none; font-weight: 600; padding: 4px 8px; border-radius: 6px; background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.1);">YouTube ↗</a>
    </div>
  </div>
  <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; background: #000;">
    <iframe
      src="https://www.youtube-nocookie.com/embed/${id}?rel=0&modestbranding=1"
      title="${escapedTitle}"
      loading="lazy"
      frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; compute-pressure"
      referrerpolicy="strict-origin-when-cross-origin"
      allowfullscreen
      style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;"
    ></iframe>
  </div>
</div>
`;
  }).join('');

  return `<div class="youtube-preview-container" style="display: flex; flex-direction: column; gap: 12px; margin-top: 12px;">${cards}</div>`;
}

function isBadgeUrl(url) {
  return /shields\.io|badgen\.net|badge|badge\.svg|\.svg($|\?)/i.test(url);
}

/**
 * Process inline formatting: bold, italic, inline code, links, raw URLs.
 * Must be called AFTER LaTeX rendering so we don't process $ inside KaTeX HTML.
 */
function processInlineFormatting(text) {
  // Bold: **text**
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text* (but not **)
  text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  // Inline code: `text`
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Markdown linked images: [![alt](imgUrl)](linkUrl)
  text = text.replace(/\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)/g, (match, alt, imgUrl, linkUrl) => {
    const isBadge = isBadgeUrl(imgUrl);
    return `<a href="${linkUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-block; vertical-align:middle; text-decoration:none; margin:2px 3px 2px 0;"><img src="${imgUrl}" alt="${alt}" class="${isBadge ? 'inline-badge' : 'chat-inline-image'}" style="vertical-align:middle; max-height:${isBadge ? '22px' : 'auto'}; border-radius:3px; display:inline-block;" loading="lazy" /></a>`;
  });
  // Markdown images: ![alt](url)
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    const isBadge = isBadgeUrl(url);
    if (isBadge) {
      return `<img src="${url}" alt="${alt}" class="inline-badge" style="display:inline-block; vertical-align:middle; margin:2px 3px 2px 0; max-height:22px; border-radius:3px;" loading="lazy" />`;
    }
    const caption = alt && alt.trim().length > 0 && !alt.startsWith('http') ? `<span class="chat-image-caption">${alt}</span>` : '';
    return `<div class="chat-image-preview-card" style="margin:14px 0;"><img src="${url}" alt="${alt}" class="chat-inline-image" loading="lazy" />${caption}</div>`;
  });
  // Markdown links: [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-external-link" style="color: #00d2ff; text-decoration: underline; text-underline-offset: 3px; word-break: break-all;">${linkText}</a>`;
  });
  // Auto-linkify raw URLs (https://... or http://...) that are NOT inside href="..." or existing <a> tags
  text = text.replace(
    /(?<!href="|href='|">)(https?:\/\/[^\s<>"'`\)]+?)(?=[.,;:!?\)]?(?:\s|$|<|"|'))/gi,
    '<a href="$1" target="_blank" rel="noopener noreferrer" class="chat-external-link" style="color: #00d2ff; text-decoration: underline; text-underline-offset: 3px; word-break: break-all;">$1</a>'
  );
  // Strikethrough: ~~text~~
  text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
  return text;
}

export function formatCodeBlockHtml(code, lang = '') {
  const cleanLang = (lang || '').trim();
  const displayLang = cleanLang ? cleanLang.toUpperCase() : 'CODE';
  const langClass = cleanLang ? ` class="language-${escapeHtml(cleanLang)}"` : '';
  const escapedCode = escapeHtml(code.trimEnd());

  return `<div class="chat-code-block-wrapper" data-lang="${escapeHtml(cleanLang)}">` +
    `<div class="chat-code-header">` +
      `<span class="chat-code-lang">${displayLang}</span>` +
      `<button class="chat-copy-code-btn" type="button" title="Copia codice">📋 Copia</button>` +
    `</div>` +
    `<pre><code${langClass}>${escapedCode}</code></pre>` +
  `</div>`;
}

function isTableStart(lines, index) {
  if (index + 1 >= lines.length) return false;
  const current = lines[index].trim();
  const next = lines[index + 1].trim();

  // Current line contains pipes and next line is divider line like |---|---| or |:---|---:| or ---|---
  const isHeader = /^\|?.*\|.*\|?$/.test(current) && current.includes('|');
  const isDivider = /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(next);

  return isHeader && isDivider;
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
        result.push(formatCodeBlockHtml(codeBlockContent, codeBlockLang));
        i++;
        continue;
      }
    }

    if (inCodeBlock) {
      codeBlockContent += (codeBlockContent ? '\n' : '') + line;
      i++;
      continue;
    }

    // Markdown Table parsing
    if (isTableStart(lines, i)) {
      const headerLine = lines[i];
      i += 2; // Skip header and divider row

      const dataRows = [];
      while (i < lines.length) {
        const trimmed = lines[i].trim();
        if (/^\|.*\|?$/.test(trimmed) || (trimmed.includes('|') && trimmed.length > 2)) {
          dataRows.push(lines[i]);
          i++;
        } else if (trimmed === '' && i + 1 < lines.length && (lines[i + 1].trim().startsWith('|') || lines[i + 1].trim().includes('|'))) {
          i++; // Skip empty line between table rows
        } else {
          break;
        }
      }

      const parseCells = (rowStr) => {
        let clean = rowStr.trim();
        if (clean.startsWith('|')) clean = clean.slice(1);
        if (clean.endsWith('|')) clean = clean.slice(0, -1);
        return clean.split('|').map(c => c.trim());
      };

      const headers = parseCells(headerLine);
      const rows = dataRows.map(parseCells);

      let tableHtml = '<div class="chat-table-wrapper"><table class="chat-table"><thead><tr>';
      headers.forEach(h => {
        tableHtml += `<th>${processInlineFormatting(h)}</th>`;
      });
      tableHtml += '</tr></thead><tbody>';

      rows.forEach(row => {
        tableHtml += '<tr>';
        row.forEach(cell => {
          tableHtml += `<td>${processInlineFormatting(cell)}</td>`;
        });
        tableHtml += '</tr>';
      });

      tableHtml += '</tbody></table></div>';
      result.push(tableHtml);
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

    // Unordered list — group consecutive bullet items into one <ul>
    if (/^[\-\*\+]\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^[\-\*\+]\s/.test(lines[i])) {
        items.push(`<li>${lines[i].replace(/^[\-\*\+]\s/, '')}</li>`);
        i++;
      }
      result.push(`<ul>${items.join('')}</ul>`);
      continue;
    }

    // Ordered list — group consecutive numbered items into one <ol>
    if (/^\d+\.\s/.test(line)) {
      const items = [];
      const startNum = parseInt(line.match(/^(\d+)\./)[1], 10);
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(`<li>${lines[i].replace(/^\d+\.\s/, '')}</li>`);
        i++;
      }
      result.push(`<ol start="${startNum}">${items.join('')}</ol>`);
      continue;
    }

    // Empty line → paragraph break
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Image / Badge syntax — check for single or consecutive image/badge lines
    const isImageLine = (l) => {
      const t = l.trim();
      return t.length > 0 && (
        /^(\[!\[.*?\]\(.*?\)\]\(.*?\)|\!\[.*?\]\(.*?\))+$/.test(t) ||
        (t.startsWith('![') && t.endsWith(')')) ||
        (t.startsWith('[![') && t.endsWith(')'))
      );
    };

    if (isImageLine(line)) {
      const badgeGroup = [];
      while (i < lines.length && isImageLine(lines[i])) {
        badgeGroup.push(lines[i].trim());
        i++;
      }
      const renderedGroup = badgeGroup.map(b => processInlineFormatting(b)).join(' ');
      result.push(`<div class="badge-row" style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin: 8px 0;">${renderedGroup}</div>`);
      continue;
    }

    // Regular paragraph
    result.push(`<p>${line}</p>`);
    i++;
  }

  // Handle unclosed code block
  if (inCodeBlock) {
    result.push(formatCodeBlockHtml(codeBlockContent, codeBlockLang));
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
      codeBlocks.push(formatCodeBlockHtml(code, lang));
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

    // Pre-pass: collapse empty lines between markdown table rows (| ... |)
    processed = processed.replace(/^([ \t]*\|.*\|[ \t]*\n)(?:[ \t]*\n)+([ \t]*\|.*\|[ \t]*)/gm, '$1$2');
    processed = processed.replace(/^([ \t]*\|.*\|[ \t]*\n)(?:[ \t]*\n)+([ \t]*\|.*\|[ \t]*)/gm, '$1$2');

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

    // Step 8: Extract YouTube videos and append responsive video previews
    const ytVideos = extractYouTubeVideos(text);
    if (ytVideos.length > 0) {
      processed += generateYouTubePreviewsHtml(ytVideos);
    }

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