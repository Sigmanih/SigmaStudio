import React, { useEffect, useRef } from 'react';
import {
  PieChart, Sparkles, BookOpen, GitCompare, FileCode,
  Plus, FolderPlus, Copy, Trash2
} from 'lucide-react';

export default function WorkspaceContextMenu({
  x,
  y,
  node,
  onClose,
  onOpenGraph,
  onAiCreate,
  onOpenFile,
  onOpenStudy,
  onNewFile,
  onNewFolder,
  onDelete,
  onShowDiff,
  isLight
}) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('mousedown', handleOutsideClick);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('mousedown', handleOutsideClick);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  if (!node) return null;

  const isDir = !!node.is_dir;
  const ext = (node.name || '').split('.').pop().toLowerCase();
  const isMarkdown = !isDir && (ext === 'md' || ext === 'markdown');
  const isGitModified = node.git_status && node.git_status !== 'clean';

  // Calcolo posizione per non uscire dallo schermo
  const posX = Math.min(x, window.innerWidth - 240);
  const posY = Math.min(y, window.innerHeight - 320);

  const handleCopyPath = () => {
    if (node.path) {
      navigator.clipboard.writeText(node.path);
    }
    onClose();
  };

  return (
    <div
      ref={menuRef}
      className={`dev-context-menu ${isLight ? 'light' : 'dark'}`}
      style={{ left: `${posX}px`, top: `${posY}px` }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Intestazione del nodo */}
      <div style={{
        padding: '5px 8px',
        fontSize: '0.68rem',
        fontWeight: 700,
        color: '#8b949e',
        borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.08)',
        marginBottom: '4px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }}>
        {isDir ? '📁 ' : '📄 '} {node.name}
      </div>

      {/* 1. Visualizza Grafo */}
      <div
        className="dev-context-menu-item"
        onClick={() => {
          onOpenGraph?.(node);
          onClose();
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <PieChart size={14} color="#00f2fe" />
          <span>Visualizza Grafo Relazionale</span>
        </span>
        <span style={{ fontSize: '0.62rem', opacity: 0.6, fontWeight: 600 }}>D3</span>
      </div>

      {/* 2. Crea con AI */}
      <div
        className="dev-context-menu-item"
        onClick={() => {
          onAiCreate?.(node);
          onClose();
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={14} color="#eab308" />
          <span>Crea Documento / Codice AI...</span>
        </span>
      </div>

      {/* 3. Studio Mode per Markdown */}
      {isMarkdown && (
        <div
          className="dev-context-menu-item"
          onClick={() => {
            onOpenStudy?.(node);
            onClose();
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BookOpen size={14} color="#a855f7" />
            <span>Modalità Studio (KaTeX & Formule)</span>
          </span>
        </div>
      )}

      {/* 4. Apri Diff Git se modificato */}
      {isGitModified && (
        <div
          className="dev-context-menu-item"
          onClick={() => {
            onShowDiff?.(node);
            onClose();
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GitCompare size={14} color="#f97316" />
            <span>Visualizza Diff Git</span>
          </span>
        </div>
      )}

      {!isDir && (
        <div
          className="dev-context-menu-item"
          onClick={() => {
            onOpenFile?.(node.path);
            onClose();
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCode size={14} color="#3b82f6" />
            <span>Apri nell'Editor</span>
          </span>
        </div>
      )}

      <div className="dev-context-divider" />

      {/* Operazioni Filesystem */}
      <div
        className="dev-context-menu-item"
        onClick={() => {
          onNewFile?.(node);
          onClose();
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={14} color="#10b981" />
          <span>Nuovo File...</span>
        </span>
      </div>

      <div
        className="dev-context-menu-item"
        onClick={() => {
          onNewFolder?.(node);
          onClose();
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FolderPlus size={14} color="#10b981" />
          <span>Nuova Cartella...</span>
        </span>
      </div>

      <div
        className="dev-context-menu-item"
        onClick={handleCopyPath}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Copy size={14} color="#8b949e" />
          <span>Copia Percorso</span>
        </span>
      </div>

      <div className="dev-context-divider" />

      <div
        className="dev-context-menu-item"
        style={{ color: '#ef4444' }}
        onClick={() => {
          onDelete?.(node);
          onClose();
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Trash2 size={14} color="#ef4444" />
          <span>Elimina definitivamente</span>
        </span>
      </div>
    </div>
  );
}
