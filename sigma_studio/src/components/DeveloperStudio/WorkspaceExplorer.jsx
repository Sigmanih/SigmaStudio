import React, { useState } from 'react';
import { 
  Folder, FolderOpen, File, FileCode, FileText, ChevronRight, ChevronDown, 
  Plus, Trash2, Edit2, RefreshCw, Search, HardDrive, CornerDownRight 
} from 'lucide-react';

export const getFileIcon = (filename = '') => {
  const ext = filename.split('.').pop().toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
      return <FileCode size={14} color="#f7df1e" />;
    case 'py':
      return <FileCode size={14} color="#3572A5" />;
    case 'json':
      return <FileCode size={14} color="#56b6c2" />;
    case 'html':
      return <FileCode size={14} color="#e34c26" />;
    case 'css':
      return <FileCode size={14} color="#563d7c" />;
    case 'md':
      return <FileText size={14} color="#00f2fe" />;
    default:
      return <File size={14} color="#8b949e" />;
  }
};

const TreeNode = ({ 
  node, 
  activeFilePath, 
  onFileSelect, 
  onDeleteEntry, 
  onCreateEntry, 
  theme, 
  isLight 
}) => {
  const [expanded, setExpanded] = useState(node.name === 'Sigma_Studio' || node.name === 'data' || node.name === 'core' || node.name === 'sigma_studio');

  if (!node) return null;

  const isDir = node.is_dir;
  const isSelected = activeFilePath === node.path;

  const handleRowClick = (e) => {
    e.stopPropagation();
    if (isDir) {
      setExpanded(!expanded);
    } else {
      onFileSelect(node.path);
    }
  };

  return (
    <div style={{ userSelect: 'none', fontSize: '0.74rem' }}>
      <div 
        onClick={handleRowClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '3px 6px',
          borderRadius: '5px',
          cursor: 'pointer',
          background: isSelected ? (isLight ? 'rgba(0, 242, 254, 0.15)' : 'rgba(0, 242, 254, 0.12)') : 'transparent',
          color: isSelected ? '#00f2fe' : (isLight ? '#24292f' : '#c9d1d9'),
          fontWeight: isSelected ? 700 : 500,
          transition: 'all 0.1s ease'
        }}
        onMouseEnter={e => {
          if (!isSelected) e.currentTarget.style.background = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)';
        }}
        onMouseLeave={e => {
          if (!isSelected) e.currentTarget.style.background = 'transparent';
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {isDir ? (
            <>
              {expanded ? <ChevronDown size={13} color="#8b949e" /> : <ChevronRight size={13} color="#8b949e" />}
              {expanded ? <FolderOpen size={14} color="#e5c07b" /> : <Folder size={14} color="#e5c07b" />}
            </>
          ) : (
            <>
              <span style={{ width: '13px', display: 'inline-block' }} />
              {getFileIcon(node.name)}
            </>
          )}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node.name}
          </span>
        </div>

        {/* Hover quick action buttons for delete/create */}
        <div className="node-actions" style={{ display: 'flex', alignItems: 'center', gap: '3px', opacity: 0.6 }} onClick={e => e.stopPropagation()}>
          {isDir && (
            <button
              onClick={() => onCreateEntry(node.path)}
              title="Nuovo file in questa cartella"
              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '2px' }}
            >
              <Plus size={11} />
            </button>
          )}
          <button
            onClick={() => onDeleteEntry(node.path, node.is_dir)}
            title={`Elimina ${node.is_dir ? 'cartella' : 'file'}`}
            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
          >
            <Trash2 size={11} />
          </button>
        </div>
      </div>

      {isDir && expanded && node.children && (
        <div style={{ paddingLeft: '12px', borderLeft: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)', marginLeft: '6px' }}>
          {node.children.length === 0 ? (
            <div style={{ padding: '2px 6px', fontSize: '0.66rem', color: '#8b949e', fontStyle: 'italic' }}>(cartella vuota)</div>
          ) : (
            node.children.map(child => (
              <TreeNode 
                key={child.path} 
                node={child} 
                activeFilePath={activeFilePath} 
                onFileSelect={onFileSelect}
                onDeleteEntry={onDeleteEntry}
                onCreateEntry={onCreateEntry}
                theme={theme}
                isLight={isLight}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default function WorkspaceExplorer({
  treeData,
  activeFilePath,
  workspaceRoot,
  workspaceRoots = [],
  onSelectWorkspaceRoot,
  onFileSelect,
  onRefreshTree,
  onCreateFile,
  onCreateFolder,
  onDeletePath,
  theme,
  isLight
}) {
  const [searchFilter, setSearchFilter] = useState('');

  const filterTree = (node, query) => {
    if (!query) return node;
    if (!node) return null;
    if (!node.is_dir) {
      return node.name.toLowerCase().includes(query.toLowerCase()) ? node : null;
    }
    const filteredChildren = (node.children || [])
      .map(child => filterTree(child, query))
      .filter(Boolean);

    if (filteredChildren.length > 0 || node.name.toLowerCase().includes(query.toLowerCase())) {
      return { ...node, children: filteredChildren };
    }
    return null;
  };

  const displayTree = filterTree(treeData, searchFilter);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      background: isLight ? '#f6f8fa' : '#0d1117',
      userSelect: 'none',
      overflow: 'hidden'
    }}>
      {/* Header with Workspace Selector */}
      <div style={{
        padding: '10px 12px',
        borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', fontWeight: 800, color: isLight ? '#24292f' : '#f0f6fc' }}>
            <HardDrive size={14} color="#00f2fe" />
            <span>WORKSPACE (ADMIN)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
            <button
              onClick={() => onCreateFile(workspaceRoot)}
              title="Nuovo File"
              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '3px' }}
            >
              <Plus size={13} />
            </button>
            <button
              onClick={onRefreshTree}
              title="Ricarica Albero"
              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '3px' }}
            >
              <RefreshCw size={12} />
            </button>
          </div>
        </div>

        {/* Workspace Root Select */}
        <select
          value={workspaceRoot}
          onChange={e => onSelectWorkspaceRoot(e.target.value)}
          style={{
            width: '100%',
            padding: '4px 6px',
            borderRadius: '6px',
            fontSize: '0.68rem',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
            color: isLight ? '#24292f' : '#c9d1d9',
            outline: 'none',
            cursor: 'pointer'
          }}
        >
          {workspaceRoots.map(r => (
            <option key={r.path} value={r.path}>
              {r.label}
            </option>
          ))}
        </select>

        {/* Quick Pinned Bookmarks (Home, data/, manifesti/, core/) */}
        <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
          {[
            { label: '🏠 Home', path: '' },
            { label: '📌 data/', path: 'data' },
            { label: '🧠 Memoria', path: 'data/models' },
            { label: '📜 Manifesti', path: 'manifesti' },
            { label: '🧬 Core', path: 'core' }
          ].map(pin => (
            <button
              key={pin.label}
              type="button"
              onClick={() => {
                const base = workspaceRoots[0]?.path || '';
                const matched = workspaceRoots.find(r => r.path.replace(/\\/g, '/').endsWith(pin.path));
                const target = matched ? matched.path : (base ? `${base.replace(/[/\\]+$/, '')}/${pin.path}` : pin.path);
                onSelectWorkspaceRoot(target);
              }}
              style={{
                padding: '2px 5px',
                borderRadius: '4px',
                fontSize: '0.60rem',
                fontWeight: 700,
                background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)',
                border: 'none',
                color: isLight ? '#57606a' : '#8b949e',
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              {pin.label}
            </button>
          ))}
        </div>

        {/* Quick Filter Input */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '3px 8px',
          borderRadius: '6px',
          background: isLight ? '#ffffff' : '#161b22',
          border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)'
        }}>
          <Search size={11} color="#8b949e" />
          <input
            type="text"
            placeholder="Cerca file o cartella..."
            value={searchFilter}
            onChange={e => setSearchFilter(e.target.value)}
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              color: isLight ? '#24292f' : '#c9d1d9',
              fontSize: '0.68rem',
              outline: 'none'
            }}
          />
        </div>
      </div>

      {/* Tree Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '8px 6px'
      }}>
        {displayTree ? (
          <TreeNode
            node={displayTree}
            activeFilePath={activeFilePath}
            onFileSelect={onFileSelect}
            onDeleteEntry={onDeletePath}
            onCreateEntry={onCreateFile}
            theme={theme}
            isLight={isLight}
          />
        ) : (
          <div style={{ fontSize: '0.72rem', color: '#8b949e', textAlign: 'center', marginTop: '20px' }}>
            Nessun file trovato.
          </div>
        )}
      </div>
    </div>
  );
}
