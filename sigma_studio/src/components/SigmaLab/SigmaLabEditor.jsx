import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Save, Trash2, Eye, FileText, ChevronRight, X } from 'lucide-react';
import { marked } from 'marked';
import katex from 'katex';
import mermaid from 'mermaid';
import Editor from 'react-simple-code-editor';
import { highlight, languages } from 'prismjs/components/prism-core';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-javascript';
import 'prismjs/themes/prism-tomorrow.css';
import 'katex/dist/katex.min.css';

// ==============================================================================
// SigmaLabEditor — Editor/Preview unificato
// Gestisce .md (editor+preview), .py (editor+console), .html/viz (editor+iframe)
// ==============================================================================

const CodeEditor = typeof Editor === 'function' ? Editor : Editor.default;

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true },
});

function detectFileType(path) {
  if (!path) return 'teoria';
  const p = path.toLowerCase();
  if (p.endsWith('.py')) return 'test';
  if (p.endsWith('.html') || p.includes('/viz/')) return 'viz';
  if (p.includes('/test/')) return 'test';
  if (p.includes('/docs/')) {
    const fn = path.split('/').pop() || '';
    if (fn.toUpperCase().startsWith('WHITEPAPER_')) return 'whitepaper';
    return 'docs';
  }
  if (p.includes('/teoria/')) return 'teoria';
  return 'teoria';
}

export default function SigmaLabEditor({ 
  tab, 
  onBack, 
  onDelete, 
  onDirtyChange,
  terminalOutput,
  onRun,
  onOpenFile
}) {
  const path = tab?.path || '';
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [fileType, setFileType] = useState('teoria');
  const [showEditor, setShowEditor] = useState(true);
  const [showPalette, setShowPalette] = useState(true);
  const [editorVisible, setEditorVisible] = useState(true);
  const [modules, setModules] = useState([]);
  const [currentModule, setCurrentModule] = useState('');
  const previewRef = useRef(null);
  const iframeRef = useRef(null);
  const [consoleOutput, setConsoleOutput] = useState('Console pronta.\n');
  const [consoleVisible, setConsoleVisible] = useState(false);
  const [consoleHeight, setConsoleHeight] = useState(400);
  const [isRunning, setIsRunning] = useState(false);
  // Viz state
  const [vizReloadKey, setVizReloadKey] = useState(0);
  const [vizPreviewOnly, setVizPreviewOnly] = useState(false);
  const [vizShowPreview, setVizShowPreview] = useState(true);
  const isViz = fileType === 'viz';
  const isVizHtml = isViz && path.endsWith('.html');
  const isPy = path.endsWith('.py');

  useEffect(() => {
    if (!path) return;
    const ft = detectFileType(path);
    setFileType(ft);
    setLoading(true);
    
    fetch(`/api/get_file?path=${encodeURIComponent(path)}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) setContent(data.content);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    fetch('/api/modules')
      .then(r => r.json())
      .then(d => setModules(d.modules || []))
      .catch(() => {});

    const match = path.match(/(\d{2})_/);
    setCurrentModule(match ? match[1] : '');
  }, [path]);

  useEffect(() => {
    if (!content || !previewRef.current || fileType === 'test' || fileType === 'viz') return;
    renderPreview();
  }, [content, fileType]);

  const MATH_PLACEHOLDERS = {
    'display': { open: '§§MATH_DISPLAY_OPEN§§', close: '§§MATH_DISPLAY_CLOSE§§' },
    'inline': { open: '§§MATH_INLINE_OPEN§§', close: '§§MATH_INLINE_CLOSE§§' }
  };

  const protectMath = (text) => {
    let protectedText = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, expr) => {
      return MATH_PLACEHOLDERS.display.open + expr.trim() + MATH_PLACEHOLDERS.display.close;
    });
    protectedText = protectedText.replace(/(?<!\$)\$([^\s$][^$]*?[^\s$])\$(?!\$)/g, (match, expr) => {
      return MATH_PLACEHOLDERS.inline.open + expr + MATH_PLACEHOLDERS.inline.close;
    });
    protectedText = protectedText.replace(/\\\[([\s\S]*?)\\\]/g, (match, expr) => {
      return MATH_PLACEHOLDERS.display.open + expr.trim() + MATH_PLACEHOLDERS.display.close;
    });
    protectedText = protectedText.replace(/\\\(([\s\S]*?)\\\)/g, (match, expr) => {
      return MATH_PLACEHOLDERS.inline.open + expr + MATH_PLACEHOLDERS.inline.close;
    });
    return protectedText;
  };

  const restoreMath = (html) => {
    html = html.replace(new RegExp(MATH_PLACEHOLDERS.display.open + '([\\s\\S]*?)' + MATH_PLACEHOLDERS.display.close, 'g'), (match, expr) => {
      try {
        const el = document.createElement('span');
        katex.render(expr, el, { displayMode: true, throwOnError: false, output: 'html' });
        return el.innerHTML;
      } catch (e) {
        return `<div class="math-error">${expr}</div>`;
      }
    });
    html = html.replace(new RegExp(MATH_PLACEHOLDERS.inline.open + '([\\s\\S]*?)' + MATH_PLACEHOLDERS.inline.close, 'g'), (match, expr) => {
      try {
        const el = document.createElement('span');
        katex.render(expr, el, { displayMode: false, throwOnError: false, output: 'html' });
        return el.innerHTML;
      } catch (e) {
        return `<span class="math-error">${expr}</span>`;
      }
    });
    return html;
  };

  const renderPreview = async () => {
    const container = previewRef.current;
    if (!container) return;

    const protectedContent = protectMath(content);
    let html = marked.parse(protectedContent);
    html = restoreMath(html);
    container.innerHTML = html;

    const mermaidBlocks = container.querySelectorAll('.language-mermaid');
    for (let i = 0; i < mermaidBlocks.length; i++) {
      const block = mermaidBlocks[i];
      const raw = block.textContent;
      const wrapper = document.createElement('div');
      wrapper.className = 'mermaid-wrapper';
      const pre = block.closest('pre') || block;
      if (pre.parentNode) pre.parentNode.replaceChild(wrapper, pre);
      try {
        const { svg } = await mermaid.render(`mermaid-svg-${i}`, raw);
        wrapper.innerHTML = svg;
      } catch (err) {
        wrapper.innerHTML = `<div class="mermaid-error">Mermaid Error: ${err.message}</div>`;
      }
    }

    container.querySelectorAll('a[href]').forEach(link => {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('http') && !href.startsWith('https') && !href.startsWith('#') && !href.startsWith('mailto:')) {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const currentDir = path.substring(0, path.lastIndexOf('/') + 1);
          const resolved = currentDir + href;
          window.open(resolved, '_blank');
        });
        link.style.cursor = 'pointer';
      }
    });
  };

  const handleSave = async () => {
    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content })
      });
      const data = await res.json();
      if (data.success) {
        if (onDirtyChange) onDirtyChange(tab.id, false);
        showSaveFeedback();
      }
    } catch (e) {
      alert('Errore salvataggio: ' + e.message);
    }
  };

  const showSaveFeedback = () => {
    const btn = document.getElementById('sigma-save-btn');
    if (btn) {
      const oldText = btn.innerHTML;
      btn.innerHTML = '✅ SALVATO!';
      btn.style.background = '#3fb950';
      setTimeout(() => {
        btn.innerHTML = oldText;
        btn.style.background = '';
      }, 2000);
    }
  };

  const handleRun = async () => {
    if (!path.endsWith('.py')) return;
    setIsRunning(true);
    setConsoleVisible(true);
    setConsoleOutput(prev => prev + `\n⏳ Esecuzione: ${path}...`);
    
    try {
      const res = await fetch('/api/run_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_path: path })
      });
      const data = await res.json();
      let out = '';
      if (data.stdout) out += data.stdout;
      if (data.stderr) out += '\n' + data.stderr;
      out += `\n━━━ Exit code: ${data.exit_code} ━━━`;
      setConsoleOutput(prev => prev + '\n' + out);
    } catch (e) {
      setConsoleOutput(prev => prev + `\n❌ Errore: ${e.message}`);
    }
    setIsRunning(false);
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
          if (data.success && onDelete) onDelete(tab.id, path);
        });
    }
  };

  const getModuleName = () => {
    const num = currentModule;
    if (!num) return 'Root';
    const mod = modules.find(m => m.number === num);
    return mod ? mod.name : `Modulo ${num}`;
  };

  const getFileHierarchy = () => {
    if (!currentModule || modules.length === 0) return [];
    const mod = modules.find(m => m.number === currentModule);
    if (!mod) return [];
    const hierarchy = [];
    if (mod.whitepapers) mod.whitepapers.forEach(f => hierarchy.push({ ...f, level: 'whitepaper', color: '#ffd700', lvlLabel: 'LIVELLO 1 • Whitepaper' }));
    if (mod.teoria) mod.teoria.forEach(f => hierarchy.push({ ...f, level: 'teoria', color: '#bc8cff', lvlLabel: 'LIVELLO 2 • Teoria' }));
    if (mod.test) mod.test.forEach(f => hierarchy.push({ ...f, level: 'test', color: '#3fb950', lvlLabel: 'LIVELLO 3 • Test' }));
    if (mod.viz) mod.viz.forEach(f => hierarchy.push({ ...f, level: 'viz', color: '#d29922', lvlLabel: 'LIVELLO 4 • Visualizzazione' }));
    if (mod.docs) mod.docs.forEach(f => hierarchy.push({ ...f, level: 'docs', color: '#ffd700', lvlLabel: 'LIVELLO 1 • Docs' }));
    return hierarchy;
  };

  if (loading) return <div className="placeholder-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#5a5e72' }}>Caricamento documento...</div>;
  if (!content && !isViz) return <div className="placeholder-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#5a5e72' }}>Documento vuoto o non trovato</div>;

  const hierarchy = getFileHierarchy();
  const highlightHtml = (code) => {
    if (code && languages.markup) {
      try { return highlight(code, languages.markup); }
      catch(e) { return code; }
    }
    return code;
  };

  return (
    <div className="lab-editor app-wrapper">
      <style>{`
        .lab-editor { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: #0a0a0c; color: #e0e0e6; font-family: 'Outfit', sans-serif; font-size: 15px; }
        .lab-editor ::-webkit-scrollbar { width: 4px; }
        .lab-editor ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        .lab-editor-header { display: flex; align-items: center; padding: 8px 16px; background: rgba(20,20,24,0.95); border-bottom: 1px solid #23232a; gap: 12px; flex-shrink: 0; }
        .lab-file-path { font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #5a5e72; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .lab-breadcrumb { display: flex; align-items: center; gap: 4px; font-size: 0.7rem; color: #9494a0; flex: 1; overflow: hidden; }
        .lab-breadcrumb .crumb { white-space: nowrap; }
        .lab-breadcrumb .sep { color: #23232a; margin: 0 2px; }
        .lab-breadcrumb .active-crumb { color: #e0e0e6; font-weight: 500; }
        .lab-actions { display: flex; gap: 6px; flex-shrink: 0; }
        .lab-btn { padding: 6px 12px; border-radius: 6px; font-size: 0.7rem; cursor: pointer; transition: all 0.15s; border: 1px solid #23232a; background: transparent; color: #9494a0; font-family: inherit; display: flex; align-items: center; gap: 4px; }
        .lab-btn:hover { background: rgba(255,255,255,0.05); color: #e0e0e6; }
        .lab-btn.primary { background: #00d2ff; color: #000; border-color: #00d2ff; }
        .lab-btn.primary:hover { box-shadow: 0 0 20px rgba(0,210,255,0.4); }
        
        .lab-main { display: flex; flex: 1; overflow: hidden; }
        
        /* Palette sidebar */
        .lab-palette { width: 240px; background: #141418; border-right: 1px solid #23232a; display: flex; flex-direction: column; overflow-y: auto; padding: 16px 0; flex-shrink: 0; }
        .lab-palette.hidden { width: 0; overflow: hidden; padding: 0; border: none; }
        .lab-palette-section { padding: 0 16px; margin-bottom: 16px; }
        .lab-palette-title { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 1.5px; color: #9494a0; margin-bottom: 8px; font-weight: 700; }
        .lab-file-item { display: flex; align-items: center; gap: 8px; padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 0.65rem; color: #9494a0; transition: all 0.15s; border: 1px solid transparent; text-decoration: none; }
        .lab-file-item:hover { background: rgba(255,255,255,0.04); color: #e0e0e6; border-color: #23232a; }
        .lab-file-item.active { background: rgba(0,210,255,0.08); border-color: rgba(0,210,255,0.2); color: #00d2ff; }
        .lab-level-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
        .lab-file-label { display: flex; flex-direction: column; }
        .lab-file-label .fname { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; }
        .lab-file-label .lvl-tag { font-size: 0.45rem; opacity: 0.6; text-transform: uppercase; }

        /* Editor pane */
        .lab-editor-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid #23232a; background: #0d1117; }
        .lab-editor-pane.hidden { flex: 0; width: 0; overflow: hidden; border: none; }

        /* Preview pane */
        .lab-preview-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        .lab-preview-pane.hidden { flex: 0; width: 0; overflow: hidden; }

        /* Viz specific */
        .viz-iframe { flex: 1; border: none; width: 100%; height: 100%; }
        .viz-controls { display: flex; align-items: center; gap: 4px; padding: 4px 8px; background: rgba(255,255,255,0.03); border-bottom: 1px solid #23232a; flex-shrink: 0; }
        .viz-controls span { font-size: 0.6rem; color: #5a5e72; font-family: 'JetBrains Mono', monospace; }
        .lab-btn-reload { background: rgba(0,210,255,0.1); color: #00d2ff; border-color: rgba(0,210,255,0.2); }
        .lab-btn-reload:hover { background: rgba(0,210,255,0.2); }

        /* Text editor for markdown */
        .lab-text-editor { flex: 1; width: 100%; padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 14px; background: #0d1117; color: #e0e0e6; border: none; outline: none; resize: none; line-height: 1.6; }
        .lab-text-editor:focus { outline: none; }

        /* Preview */
        .lab-preview { flex: 1; overflow-y: auto; padding: 40px; display: flex; justify-content: center; background: #fdfdfc; }
        .lab-viewer { width: 100%; max-width: 800px; color: #1a1a1a; font-family: 'Crimson Pro', 'Georgia', serif; font-size: 1.1rem; line-height: 1.8; }
        .lab-viewer h1 { font-family: 'Outfit', sans-serif; font-size: 2.6rem; border-bottom: 2px solid #0076db; padding-bottom: 15px; margin-bottom: 30px; letter-spacing: -1px; font-weight: 700; }
        .lab-viewer h2 { font-family: 'Outfit', sans-serif; font-size: 1.8rem; border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 2em; font-weight: 600; }
        .lab-viewer h3 { font-family: 'Outfit', sans-serif; font-size: 1.4rem; margin-top: 1.5em; font-weight: 600; }
        .lab-viewer p { margin: 1.2em 0; }
        .lab-viewer blockquote { border-left: 4px solid #0076db; background: #f7f9fc; padding: 16px 20px; font-style: italic; margin: 20px 0; border-radius: 4px; }
        .lab-viewer table { width: 100%; border-collapse: collapse; margin: 30px 0; }
        .lab-viewer th, .lab-viewer td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        .lab-viewer th { background: #f7f7f7; }
        .lab-viewer pre { background: #f8f8f8; padding: 20px; border-radius: 8px; overflow-x: auto; border: 1px solid #eee; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
        .lab-viewer code { font-family: 'JetBrains Mono', monospace; }
        .lab-viewer img { max-width: 100%; border-radius: 8px; margin: 20px 0; }
        .lab-viewer .mermaid-wrapper { width: 100%; margin: 30px auto; overflow-x: auto; background: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px 0; }
        .lab-viewer .mermaid-wrapper svg { display: block; margin: 0 auto; max-width: 100%; height: auto; }
        .lab-viewer .mermaid-error { color: #c00; padding: 20px; border: 1px dashed #c00; border-radius: 8px; font-size: 0.8rem; }

        /* Terminal / Console */
        .lab-console { flex-shrink: 0; border-top: 1px solid #23232a; background: rgba(8,8,10,0.98); display: flex; flex-direction: column; overflow: hidden; }
        .lab-console.hidden { display: none; }
        .lab-console-header { display: flex; align-items: center; justify-content: space-between; padding: 4px 12px; background: rgba(255,255,255,0.02); border-bottom: 1px solid #23232a; flex-shrink: 0; }
        .lab-console-title { font-size: 0.65rem; font-weight: 600; letter-spacing: 1px; color: #9494a0; display: flex; align-items: center; gap: 8px; }
        .lab-console-actions { display: flex; gap: 6px; }
        .lab-console-actions button { padding: 2px 10px; border-radius: 4px; font-size: 0.6rem; cursor: pointer; border: 1px solid #23232a; background: rgba(255,255,255,0.05); color: #9494a0; font-family: inherit; transition: all 0.15s; }
        .lab-console-actions button:hover { background: rgba(0,210,255,0.1); border-color: #00d2ff; color: #00d2ff; }
        .lab-console-actions .btn-run-console { background: rgba(63,185,80,0.15); border-color: rgba(63,185,80,0.3); color: #3fb950; }
        .lab-console-actions .btn-run-console:hover { background: rgba(63,185,80,0.3); }
        .lab-console-body { flex: 1; overflow-y: auto; padding: 6px 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
        .lab-console-body .line-running { color: #d29922; animation: pulse 0.8s ease-in-out infinite alternate; }
        @keyframes pulse { from { opacity: 0.4; } to { opacity: 1; } }
        .lab-console-body .line-exit { color: #7a7a8a; border-top: 1px solid #23232a; margin-top: 4px; padding-top: 4px; }

        /* Code editor overrides */
        .mono-editor { font-family: 'JetBrains Mono', 'Consolas', monospace !important; font-size: 14px !important; }
        .editor-container { flex: 1; overflow: auto; }

        @media print {
          .lab-editor-header, .lab-palette, .lab-editor-pane, .lab-console { display: none !important; }
          .lab-editor { background: #fff !important; overflow: visible !important; height: auto !important; }
          .lab-main { display: block !important; overflow: visible !important; }
          .lab-preview-pane { flex: 1 !important; width: 100% !important; overflow: visible !important; }
          .lab-preview { padding: 0 !important; background: #fff !important; overflow: visible !important; }
          .lab-viewer { max-width: 100% !important; }
        }
      `}</style>

      {/* Header */}
      <div className="lab-editor-header">
        <button className="lab-btn" onClick={() => setShowPalette(!showPalette)} title="Toggle Palette">
          {showPalette ? '◀' : '▶'} Palette
        </button>
        <div className="lab-breadcrumb">
          <span className="crumb">Σ Sigma Studio</span>
          <span className="sep">›</span>
          <span className="crumb">M{currentModule} • {getModuleName()}</span>
          <span className="sep">›</span>
          <span className="crumb active-crumb">{path.split('/').pop()}</span>
        </div>
        <div className="lab-actions">
          {!isViz && isPy && (
            <button className="lab-btn" onClick={handleRun} style={{ background: 'rgba(63,185,80,0.15)', color: '#3fb950', borderColor: 'rgba(63,185,80,0.3)' }}>
              <Play size={14} /> Esegui
            </button>
          )}
          {!isViz && !isPy && (
            <>
              <button className="lab-btn" onClick={() => setShowEditor(!showEditor)}>
                {showEditor ? <Eye size={14} /> : <FileText size={14} />} {showEditor ? 'Preview' : 'Source'}
              </button>
              <button className="lab-btn" onClick={() => setEditorVisible(!editorVisible)} title={editorVisible ? 'Solo anteprima' : 'Mostra editor'}>
                {editorVisible ? '👁️ Solo Anteprima' : '✏️ Modifica'}
              </button>
              <button className="lab-btn" onClick={() => window.print()} title="Stampa anteprima">🖨️ Stampa</button>
              <button className="lab-btn" onClick={() => window.print()} title="Salva come PDF">📄 PDF</button>
            </>
          )}
          {isVizHtml && (
            <>
              <button className="lab-btn lab-btn-reload" onClick={() => { handleSave(); setTimeout(() => setVizReloadKey(k => k + 1), 100); }} title="Salva e ricarica anteprima">
                🔄 Ricarica
              </button>
              <button className="lab-btn" onClick={() => setVizShowPreview(v => !v)}>
                {vizShowPreview ? <Eye size={14} /> : <FileText size={14} />} {vizShowPreview ? 'Nascondi Preview' : 'Mostra Preview'}
              </button>
              <button className="lab-btn" onClick={() => setVizPreviewOnly(v => !v)} title={vizPreviewOnly ? 'Mostra editor' : 'Solo anteprima'}>
                {vizPreviewOnly ? '✏️ Modifica' : '👁️ Solo Anteprima'}
              </button>
            </>
          )}
          <button id="sigma-save-btn" className="lab-btn primary" onClick={handleSave}>
            <Save size={14} /> SALVA
          </button>
          <button className="lab-btn" onClick={handleDelete} style={{ color: '#ff6b6b' }}>🗑️</button>
        </div>
      </div>

      {/* Main workspace */}
      <div className="lab-main">
        {/* Palette */}
        <div className={`lab-palette ${showPalette ? '' : 'hidden'}`}>
          <div className="lab-palette-section">
            <div className="lab-palette-title">📂 File del Modulo</div>
            {hierarchy.length === 0 && <div style={{ fontSize: '0.65rem', color: '#9494a0', textAlign: 'center', padding: '10px' }}>Nessun file</div>}
            {hierarchy.map((item, i) => (
              <div key={i} className={`lab-file-item ${item.path === path ? 'active' : ''}`} onClick={() => { if (onOpenFile) onOpenFile(item.path); }}>
                <span className="lab-level-dot" style={{ background: item.color }}></span>
                <span className="lab-file-label">
                  <span className="fname">{item.filename}</span>
                  <span className="lvl-tag" style={{ color: item.color }}>{item.lvlLabel}</span>
                </span>
              </div>
            ))}
          </div>
          <div className="lab-palette-section" style={{ marginTop: 'auto' }}>
            <div style={{ padding: '12px', background: 'rgba(0,210,255,0.05)', border: '1px dashed rgba(0,210,255,0.2)', borderRadius: '8px' }}>
              <span style={{ fontSize: '0.65rem', color: '#00d2ff', fontWeight: 700 }}>HIERARCHY:</span>
              <p style={{ fontSize: '0.6rem', color: '#9494a0', margin: '5px 0 0 0' }}>
                <span style={{ color: '#ffd700' }}>●</span> Whitepaper<br/>
                <span style={{ color: '#bc8cff' }}>●</span> Teoria<br/>
                <span style={{ color: '#3fb950' }}>●</span> Test<br/>
                <span style={{ color: '#d29922' }}>●</span> Viz<br/>
              </p>
            </div>
          </div>
        </div>

        {/* Editor pane */}
        <div className={`lab-editor-pane ${(isViz ? vizPreviewOnly : !editorVisible) ? 'hidden' : ''}`}>
          {isViz ? (
            <div className="editor-container">
              <CodeEditor
                value={content}
                onValueChange={c => { setContent(c); if (onDirtyChange) onDirtyChange(tab.id, true); }}
                highlight={highlightHtml}
                padding={20}
                className="mono-editor"
                style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 14, minHeight: '100%' }}
              />
            </div>
          ) : isPy ? (
            <div className="editor-container">
              <CodeEditor
                value={content}
                onValueChange={c => { setContent(c); if (onDirtyChange) onDirtyChange(tab.id, true); }}
                highlight={code => highlight(code, languages.python)}
                padding={20}
                className="mono-editor"
                style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 14, minHeight: '100%' }}
              />
            </div>
          ) : (
            <textarea
              className="lab-text-editor"
              value={content}
              onChange={e => { setContent(e.target.value); if (onDirtyChange) onDirtyChange(tab.id, true); }}
              spellCheck={false}
            />
          )}
        </div>
        
        {/* Preview / Console pane */}
        <div className={`lab-preview-pane ${isViz ? (vizShowPreview ? '' : 'hidden') : (showEditor ? '' : 'hidden')}`}>
          {isViz ? (
            <>
              <div className="viz-controls">
                <span>🌐 Preview live</span>
                <span style={{ marginLeft: 'auto', fontSize: '0.55rem', color: '#5a5e72' }}>
                  {content.length} caratteri
                </span>
              </div>
              <iframe
                key={vizReloadKey}
                srcDoc={content}
                className="viz-iframe"
                title="Viz Preview"
              />
            </>
          ) : isPy ? (
            <div className="lab-console" style={{ height: '100%', borderTop: 'none', display: 'flex', flexDirection: 'column' }}>
              <div className="lab-console-header">
                <div className="lab-console-title">
                  <span style={{ color: '#3fb950' }}>▶</span> SIGMA TEST CONSOLE
                </div>
                <div className="lab-console-actions">
                  <button onClick={() => setConsoleOutput('Console pronta.\n')}>✕ Pulisci</button>
                </div>
              </div>
              <div className="lab-console-body" style={{ flex: 1 }}>
                <span style={{ color: '#00d2ff' }}>Σ σ ~ $ </span>
                {consoleOutput.split('\n').map((line, i) => (
                  <div key={i} className={line.startsWith('⏳') ? 'line-running' : line.startsWith('━━━') ? 'line-exit' : ''}>
                    {line}
                  </div>
                ))}
                {isRunning && <div className="line-running">⏳ In esecuzione...</div>}
              </div>
            </div>
          ) : (
            <div className="lab-preview">
              <div ref={previewRef} className="lab-viewer"></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}