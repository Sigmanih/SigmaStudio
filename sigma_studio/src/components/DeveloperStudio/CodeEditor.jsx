import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  X, Save, Copy, Check, Play, FileCode, SplitSquareVertical, 
  RotateCcw, Sparkles, Eye, Code, Download, BookOpen 
} from 'lucide-react';
import { getFileIcon } from './WorkspaceExplorer';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import 'katex/dist/katex.min.css';

import EditorComponent from 'react-simple-code-editor';
import { highlight, languages } from 'prismjs/components/prism-core';
import 'prismjs/components/prism-clike';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-bash';
import 'prismjs/themes/prism-tomorrow.css';

const Editor = typeof EditorComponent === 'function' ? EditorComponent : EditorComponent.default;

const highlightCode = (code, ext) => {
  if (!code) return '';
  try {
    if (['py', 'python'].includes(ext) && languages.python) {
      return highlight(code, languages.python, 'python');
    }
    if (['js', 'jsx', 'ts', 'tsx', 'mjs'].includes(ext) && languages.javascript) {
      return highlight(code, languages.javascript, 'javascript');
    }
    if (['html', 'xml', 'svg'].includes(ext) && languages.markup) {
      return highlight(code, languages.markup, 'markup');
    }
    if (['css', 'scss', 'less'].includes(ext) && languages.css) {
      return highlight(code, languages.css, 'css');
    }
    if (['json'].includes(ext) && (languages.json || languages.javascript)) {
      return highlight(code, languages.json || languages.javascript, 'json');
    }
    if (['sh', 'bash', 'ps1', 'bat'].includes(ext) && (languages.bash || languages.clike)) {
      return highlight(code, languages.bash || languages.clike, 'bash');
    }
    if (languages.clike) {
      return highlight(code, languages.clike, 'clike');
    }
  } catch (err) {
    console.debug('Prism syntax highlight error:', err);
  }
  return code;
};

export default function CodeEditor({
  openFiles = [],
  activeFilePath,
  onSelectTab,
  onCloseTab,
  onContentChange,
  onSaveFile,
  onRunFileInTerminal,
  activeDiff,
  onAcceptDiff,
  onRejectDiff,
  theme,
  isLight
}) {
  const [copied, setCopied] = useState(false);
  const [showDiffView, setShowDiffView] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [imageZoom, setImageZoom] = useState(1);
  const textareaRef = useRef(null);

  const activeFile = openFiles.find(f => f.path === activeFilePath) || openFiles[0];

  // Auto-switch to diff view if activeDiff is provided
  useEffect(() => {
    if (activeDiff) {
      setShowDiffView(true);
    }
  }, [activeDiff]);

  // Compute HTML preview reactively
  const previewHtml = useMemo(() => {
    if (!activeFile?.content) return '';
    const ext = (activeFile.filename || '').split('.').pop().toLowerCase();
    if (ext === 'md' || ext === 'markdown') {
      try {
        return renderMarkdownLatex(activeFile.content);
      } catch (e) {
        console.error('Markdown rendering error:', e);
        return `<pre style="color: #ef4444; padding: 12px;">Errore rendering markdown: ${e.message}</pre>`;
      }
    }
    if (ext === 'json') {
      try {
        const parsed = JSON.parse(activeFile.content);
        return `<pre style="font-family: monospace; font-size: 0.8rem; color: #58a6ff;">${JSON.stringify(parsed, null, 2)}</pre>`;
      } catch (e) {
        return `<pre style="font-family: monospace; font-size: 0.8rem;">${activeFile.content}</pre>`;
      }
    }
    return '';
  }, [activeFile?.path, activeFile?.content]);

  // Keyboard shortcut Ctrl+S
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (activeFile) {
          onSaveFile(activeFile.path, activeFile.content);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeFile, onSaveFile]);

  const handleCopy = () => {
    if (activeFile?.content) {
      navigator.clipboard.writeText(activeFile.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleTabKey = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = e.target.selectionStart;
      const end = e.target.selectionEnd;
      const val = e.target.value;
      const newVal = val.substring(0, start) + '    ' + val.substring(end);
      if (activeFile) {
        onContentChange(activeFile.path, newVal);
      }
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 4;
        }
      }, 0);
    }
  };

  if (!activeFile) {
    return (
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: isLight ? '#ffffff' : '#07090e',
        color: isLight ? '#57606a' : '#8b949e',
        gap: '12px'
      }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '16px',
          background: isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <FileCode size={28} color="#00f2fe" />
        </div>
        <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: isLight ? '#24292f' : '#f0f6fc' }}>
          Nessun file aperto
        </h3>
        <p style={{ margin: 0, fontSize: '0.74rem', maxWidth: '320px', textAlign: 'center', lineHeight: 1.4 }}>
          Seleziona un file dall'esploratore a sinistra o chiedi all'AI Developer Agent di creare o esplorare moduli.
        </p>
      </div>
    );
  }

  const lines = (activeFile.content || '').split('\n');
  const fileExt = (activeFile.filename || '').split('.').pop().toLowerCase();
  const isPreviewable = ['md', 'markdown', 'html', 'svg', 'json'].includes(fileExt);
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff'].includes(fileExt) || activeFile.is_image;
  const isPdf = fileExt === 'pdf' || activeFile.is_pdf;
  const isAudio = ['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(fileExt);
  const isVideo = ['mp4', 'webm', 'mov', 'mkv'].includes(fileExt);
  const isModelOrBinary = !isImage && !isPdf && !isAudio && !isVideo && (['gguf', 'safetensors', 'bin', 'pt', 'pth', 'onnx', 'engine', 'zip', 'tar', 'gz', 'parquet', 'exe', 'dll'].includes(fileExt) || activeFile.is_binary);

  const rawFileUrl = `/api/developer/fs/raw?path=${encodeURIComponent(activeFile.path)}&_t=${Date.now()}`;

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: isLight ? '#ffffff' : '#0d1117',
      overflow: 'hidden'
    }}>
      {/* 1. Tab Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: isLight ? '#f6f8fa' : '#07090e',
        borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
        overflowX: 'auto',
        minHeight: '36px',
        padding: '0 8px',
        gap: '4px'
      }}>
        {openFiles.map(file => {
          const isActive = file.path === activeFilePath;
          const isDirty = file.dirty;
          return (
            <div
              key={file.path}
              onClick={() => onSelectTab(file.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: '6px 6px 0 0',
                background: isActive 
                  ? (isLight ? '#ffffff' : '#0d1117') 
                  : (isLight ? '#eaeef2' : '#161b22'),
                borderTop: isActive ? '2px solid #00f2fe' : '2px solid transparent',
                borderLeft: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)',
                borderRight: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)',
                cursor: 'pointer',
                fontSize: '0.72rem',
                fontWeight: isActive ? 700 : 500,
                color: isActive 
                  ? (isLight ? '#24292f' : '#f0f6fc') 
                  : (isLight ? '#57606a' : '#8b949e'),
                userSelect: 'none'
              }}
            >
              {getFileIcon(file.filename)}
              <span>{file.filename}</span>
              {isDirty && (
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#d29922' }} title="Modificato non salvato" />
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseTab(file.path);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#8b949e',
                  cursor: 'pointer',
                  padding: '2px',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <X size={11} />
              </button>
            </div>
          );
        })}
      </div>

      {/* 2. Editor Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 14px',
        background: isLight ? '#f6f8fa' : '#0a0e14',
        borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)',
        fontSize: '0.72rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isLight ? '#57606a' : '#8b949e' }}>
          <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{activeFile.path}</span>
          {activeFile.dirty && (
            <span style={{ color: '#d29922', fontWeight: 800 }}>• Modificato (Premi Ctrl+S)</span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Mostra Preview Toggle (Markdown, HTML, SVG, JSON) */}
          {isPreviewable && !isImage && (
            <button
              type="button"
              onClick={() => setShowPreview(!showPreview)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: showPreview ? 'rgba(0, 242, 254, 0.15)' : (isLight ? '#ffffff' : '#161b22'),
                border: showPreview ? '1px solid rgba(0, 242, 254, 0.4)' : (isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)'),
                color: showPreview ? '#00f2fe' : (isLight ? '#24292f' : '#c9d1d9'),
                fontSize: '0.68rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
              title="Mostra Anteprima Renderizzata"
            >
              {showPreview ? <Code size={12} /> : <Eye size={12} />}
              <span>{showPreview ? 'Mostra Codice' : 'Mostra Preview'}</span>
            </button>
          )}

          {/* Esegui Script Python / Bash */}
          {(fileExt === 'py' || fileExt === 'sh' || fileExt === 'js' || fileExt === 'bat' || fileExt === 'ps1') && (
            <button
              type="button"
              onClick={() => onRunFileInTerminal(activeFile.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: 'rgba(63, 185, 80, 0.15)',
                border: '1px solid rgba(63, 185, 80, 0.3)',
                color: '#3fb950',
                fontSize: '0.68rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
              title="Esegui nel Terminale"
            >
              <Play size={12} />
              <span>Esegui Script</span>
            </button>
          )}

          {/* Save Button */}
          {!isImage && (
            <button
              type="button"
              onClick={() => onSaveFile(activeFile.path, activeFile.content)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: isLight ? '#ffffff' : '#161b22',
                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
                color: isLight ? '#24292f' : '#c9d1d9',
                fontSize: '0.68rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <Save size={12} />
              <span>Salva (Ctrl+S)</span>
            </button>
          )}

          {/* Copy Button */}
          {!isImage && (
            <button
              type="button"
              onClick={handleCopy}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 8px',
                borderRadius: '6px',
                background: isLight ? '#ffffff' : '#161b22',
                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
                color: isLight ? '#24292f' : '#c9d1d9',
                fontSize: '0.68rem',
                cursor: 'pointer'
              }}
            >
              {copied ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
            </button>
          )}
        </div>
      </div>

      {/* 3. Main Workspace Area: Image / PDF / Media / Model / Diff / Preview / Code Editor */}
      {isImage ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: isLight ? '#f6f8fa' : '#07090e',
          position: 'relative',
          overflow: 'hidden',
          padding: '20px'
        }}>
          {/* Zoom Toolbar */}
          <div style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: isLight ? '#ffffff' : '#161b22',
            padding: '4px 8px',
            borderRadius: '8px',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
            zIndex: 10
          }}>
            <button
              onClick={() => setImageZoom(z => Math.max(0.2, z - 0.2))}
              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontWeight: 800, fontSize: '0.8rem' }}
            >
              -
            </button>
            <span style={{ fontSize: '0.68rem', color: isLight ? '#24292f' : '#f0f6fc', fontWeight: 700, minWidth: '40px', textAlign: 'center' }}>
              {Math.round(imageZoom * 100)}%
            </span>
            <button
              onClick={() => setImageZoom(z => Math.min(3.0, z + 0.2))}
              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontWeight: 800, fontSize: '0.8rem' }}
            >
              +
            </button>
            <button
              onClick={() => setImageZoom(1)}
              style={{ background: 'none', border: 'none', color: '#00f2fe', cursor: 'pointer', fontSize: '0.62rem', fontWeight: 700, marginLeft: '4px' }}
            >
              Reset
            </button>
            <a
              href={rawFileUrl}
              download={activeFile.filename}
              style={{ display: 'flex', alignItems: 'center', color: '#8b949e', marginLeft: '6px' }}
              title="Scarica File"
            >
              <Download size={13} />
            </a>
          </div>

          <div style={{
            overflow: 'auto',
            maxHeight: '100%',
            maxWidth: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'repeating-conic-gradient(#80808020 0% 25%, transparent 0% 50%) 50% / 16px 16px',
            padding: '16px',
            borderRadius: '10px'
          }}>
            <img
              src={rawFileUrl}
              alt={activeFile.filename}
              style={{
                transform: `scale(${imageZoom})`,
                transition: 'transform 0.15s ease',
                maxWidth: '90%',
                maxHeight: '75vh',
                objectFit: 'contain',
                borderRadius: '6px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
              }}
            />
          </div>
        </div>
      ) : isPdf ? (
        <div style={{ flex: 1, height: '100%', background: '#525659' }}>
          <iframe
            title="PDF Viewer"
            src={`${rawFileUrl}#toolbar=1`}
            style={{ width: '100%', height: '100%', border: 'none' }}
          />
        </div>
      ) : isAudio || isVideo ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: isLight ? '#f6f8fa' : '#07090e',
          padding: '24px',
          gap: '16px'
        }}>
          <div style={{
            padding: '24px 32px',
            borderRadius: '16px',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '14px',
            boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
            maxWidth: '500px',
            width: '100%'
          }}>
            <h4 style={{ margin: 0, fontSize: '0.9rem', color: isLight ? '#24292f' : '#f0f6fc' }}>
              {activeFile.filename}
            </h4>
            {isVideo ? (
              <video
                controls
                src={rawFileUrl}
                style={{ width: '100%', maxHeight: '50vh', borderRadius: '8px', background: '#000' }}
              />
            ) : (
              <audio
                controls
                src={rawFileUrl}
                style={{ width: '100%', marginTop: '8px' }}
              />
            )}
            <div style={{ fontSize: '0.72rem', color: '#8b949e' }}>
              {activeFile.size_label || 'Riproduzione multimediale'}
            </div>
          </div>
        </div>
      ) : isModelOrBinary ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: isLight ? '#f6f8fa' : '#07090e',
          padding: '24px'
        }}>
          <div style={{
            padding: '28px 36px',
            borderRadius: '16px',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(0, 242, 254, 0.25)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '16px',
            maxWidth: '520px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 8px 30px rgba(0,0,0,0.25)'
          }}>
            <div style={{
              width: '54px',
              height: '54px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, rgba(0, 242, 254, 0.2), rgba(79, 172, 254, 0.2))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <FileCode size={26} color="#00f2fe" />
            </div>

            <div>
              <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: isLight ? '#24292f' : '#f0f6fc' }}>
                {activeFile.filename}
              </h3>
              <p style={{ margin: '6px 0 0 0', fontSize: '0.72rem', color: '#8b949e', fontFamily: 'monospace' }}>
                {activeFile.path}
              </p>
            </div>

            {/* Badges */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px', background: 'rgba(210, 153, 34, 0.15)', color: '#d29922' }}>
                📦 Dimensione: {activeFile.size_label || 'File Binario'}
              </span>
              <span style={{ fontSize: '0.68rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px', background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff' }}>
                ⚡ Formato: {fileExt.toUpperCase()}
              </span>
            </div>

            <p style={{ margin: 0, fontSize: '0.74rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.45 }}>
              Questo è un file di dati/pesi binari non modificabile come testo. Puoi utilizzarlo direttamente con <strong>SigmaEngine</strong> o gestirlo dal <strong>Model Hub</strong>.
            </p>

            <a
              href={rawFileUrl}
              download={activeFile.filename}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                background: isLight ? '#f6f8fa' : '#0d1117',
                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
                color: isLight ? '#24292f' : '#c9d1d9',
                fontSize: '0.72rem',
                fontWeight: 700,
                textDecoration: 'none'
              }}
            >
              <Download size={13} />
              <span>Scarica File ({activeFile.size_label || 'Binario'})</span>
            </a>
          </div>
        </div>
      ) : showDiffView && activeDiff ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: '#07090e'
        }}>
          {/* Diff Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 16px',
            background: '#0d1117',
            borderBottom: '1px solid rgba(255,255,255,0.08)'
          }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00f2fe' }}>
              ⚡ Visualizzatore Diff (Modifiche Proposte dall'AI)
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => {
                  onAcceptDiff();
                  setShowDiffView(false);
                }}
                style={{
                  padding: '4px 12px',
                  borderRadius: '6px',
                  background: '#3fb950',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                Applica Modifiche
              </button>
              <button
                onClick={() => {
                  onRejectDiff();
                  setShowDiffView(false);
                }}
                style={{
                  padding: '4px 12px',
                  borderRadius: '6px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#ef4444',
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                Rifiuta
              </button>
            </div>
          </div>
          <pre style={{
            flex: 1,
            margin: 0,
            padding: '12px 16px',
            overflow: 'auto',
            background: '#07090e',
            color: '#c9d1d9',
            fontFamily: 'Consolas, monospace',
            fontSize: '0.76rem',
            lineHeight: 1.45
          }}>
            {activeDiff.split('\n').map((line, idx) => {
              let color = '#c9d1d9';
              let bg = 'transparent';
              if (line.startsWith('+')) {
                color = '#3fb950';
                bg = 'rgba(63, 185, 80, 0.1)';
              } else if (line.startsWith('-')) {
                color = '#ef4444';
                bg = 'rgba(239, 68, 68, 0.1)';
              } else if (line.startsWith('@@')) {
                color = '#00f2fe';
              }
              return (
                <div key={idx} style={{ color, background: bg, padding: '1px 4px' }}>
                  {line}
                </div>
              );
            })}
          </pre>
        </div>
      ) : showPreview && isPreviewable ? (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          padding: '20px 24px',
          background: isLight ? '#ffffff' : '#0d1117',
          color: isLight ? '#24292f' : '#e6edf3',
          lineHeight: 1.6
        }}>
          {fileExt === 'html' ? (
            <iframe
              key={`html-${activeFile.path}`}
              title="HTML Preview"
              srcDoc={activeFile.content || ''}
              style={{ width: '100%', height: '100%', border: 'none', background: '#fff', borderRadius: '8px' }}
              sandbox="allow-scripts allow-same-origin"
            />
          ) : fileExt === 'svg' ? (
            <div 
              key={`svg-${activeFile.path}`}
              style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}
              dangerouslySetInnerHTML={{ __html: activeFile.content || '' }} 
            />
          ) : (
            <div 
              key={`md-${activeFile.path}`}
              className="markdown-body"
              style={{
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
                fontSize: '0.88rem'
              }}
              dangerouslySetInnerHTML={{ __html: previewHtml }}
            />
          )}
        </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          overflowY: 'auto',
          position: 'relative',
          background: isLight ? '#fbfcfe' : '#07090e'
        }}>
          {/* Line Numbers Gutter */}
          <div style={{
            width: '45px',
            minWidth: '45px',
            padding: '16px 6px',
            background: isLight ? '#f6f8fa' : '#0a0e14',
            borderRight: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)',
            color: '#8b949e',
            fontSize: '0.76rem',
            fontFamily: 'Consolas, monospace',
            textAlign: 'right',
            userSelect: 'none',
            lineHeight: '21px'
          }}>
            {lines.map((_, i) => (
              <div key={i}>{i + 1}</div>
            ))}
          </div>

          {/* Prism Syntax Highlighted Editor */}
          <div style={{ flex: 1, overflowX: 'auto', minWidth: 0 }}>
            <Editor
              value={activeFile.content || ''}
              onValueChange={(val) => onContentChange(activeFile.path, val)}
              highlight={(code) => highlightCode(code, fileExt)}
              padding={16}
              style={{
                fontFamily: '"JetBrains Mono", Consolas, "Fira Code", monospace',
                fontSize: '0.78rem',
                lineHeight: '21px',
                minHeight: '100%',
                background: 'transparent',
                color: isLight ? '#24292f' : '#f0f6fc'
              }}
              textareaClassName="developer-code-textarea"
            />
          </div>
        </div>
      )}

      {/* Editor Footer Status Bar */}
      <div style={{
        padding: '3px 12px',
        background: isLight ? '#f6f8fa' : '#0d1117',
        borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.66rem',
        color: '#8b949e',
        userSelect: 'none'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span>{activeFile.path}</span>
          <span>{lines.length} righe</span>
          <span>{activeFile.content ? activeFile.content.length : 0} caratteri</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>UTF-8</span>
          <span style={{ textTransform: 'uppercase', color: '#00f2fe' }}>
            {activeFile.path.split('.').pop() || 'TXT'}
          </span>
        </div>
      </div>
    </div>
  );
}
