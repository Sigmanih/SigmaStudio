import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../../contexts/AppContext';
import WorkspaceExplorer from './WorkspaceExplorer';
import CodeEditor from './CodeEditor';
import TerminalPanel from './TerminalPanel';
import ModulePublisher from './ModulePublisher';
import FanoutPanel from './FanoutPanel';
import ActivityTerminalStrip from './ActivityTerminalStrip';
import SigmaEngineNativeBar from './SigmaEngineNativeBar';
import AdminAgentChat from './AdminAgentChat';
import McpQuickActionsBar from './McpQuickActionsBar';
import AiCreateFileModal from './AiCreateFileModal';

const normPath = (p) => String(p || '').replace(/\\/g, '/').toLowerCase().trim();
const isSamePath = (p1, p2) => {
  if (!p1 || !p2) return false;
  const n1 = normPath(p1);
  const n2 = normPath(p2);
  return n1 === n2 || n1.endsWith(n2) || n2.endsWith(n1);
};

export default function DeveloperStudio() {
  const { theme, addToast } = useApp();
  const isLight = theme === 'light';

  // Workspace & Filesystem state
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [workspaceRoots, setWorkspaceRoots] = useState([]);
  const [treeData, setTreeData] = useState(null);
  const [treeVersion, setTreeVersion] = useState(0);
  const [openFiles, setOpenFiles] = useState([]);
  const [activeFilePath, setActiveFilePath] = useState(null);
  const [activeDiff, setActiveDiff] = useState(null);
  const [aiModalState, setAiModalState] = useState({ isOpen: false, node: null });

  // Apertura della scheda speciale Grafo D3
  const handleOpenGraph = useCallback((target) => {
    const rawPath = typeof target === 'string' ? target : (target?.path || '');
    const cleanPath = String(rawPath).trim().replace(/^["']|["']$/g, '');
    const folderName = cleanPath ? cleanPath.split(/[/\\]/).pop() : 'Workspace';
    const graphTabId = `__graph__:${cleanPath || 'root'}`;

    setOpenFiles(prev => {
      const existing = prev.find(f => f.path === graphTabId);
      if (existing) return prev;
      return [...prev, {
        path: graphTabId,
        filename: `🌐 Grafo: ${folderName}`,
        is_graph: true,
        targetPath: cleanPath,
        content: '',
        dirty: false
      }];
    });
    setActiveFilePath(graphTabId);
  }, []);

  // Terminal state
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [isRunningCommand, setIsRunningCommand] = useState(false);

  // 1. Fetch workspace roots
  const fetchRoots = useCallback(() => {
    fetch('/api/developer/workspace/roots')
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setWorkspaceRoots(d.roots || []);
          if (!workspaceRoot) {
            setWorkspaceRoot(d.current || d.roots[0]?.path);
          }
        }
      })
      .catch(err => console.error('Error fetching workspace roots:', err));
  }, [workspaceRoot]);

  useEffect(() => {
    fetchRoots();
  }, [fetchRoots]);

  const handleAddCustomRoot = useCallback(async (path, label) => {
    try {
      const res = await fetch('/api/developer/workspace/roots/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, label })
      });
      const d = await res.json();
      if (d.success) {
        if (addToast) addToast({ type: 'success', message: 'Cartella salvata nella Developer Map!' });
        fetchRoots();
        if (d.path) setWorkspaceRoot(d.path);
      } else {
        if (addToast) addToast({ type: 'error', message: d.error || 'Errore aggiunta cartella' });
      }
    } catch (e) {
      if (addToast) addToast({ type: 'error', message: String(e) });
    }
  }, [addToast, fetchRoots]);

  const handleRemoveCustomRoot = useCallback(async (path) => {
    try {
      const res = await fetch('/api/developer/workspace/roots/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const d = await res.json();
      if (d.success) {
        if (addToast) addToast({ type: 'info', message: 'Cartella rimossa dalla Developer Map' });
        fetchRoots();
      }
    } catch (e) {
      if (addToast) addToast({ type: 'error', message: String(e) });
    }
  }, [addToast, fetchRoots]);

  // 2. Fetch file tree when workspaceRoot changes
  const fetchTree = useCallback(() => {
    if (!workspaceRoot) return;
    fetch(`/api/developer/fs/tree?path=${encodeURIComponent(workspaceRoot)}&_t=${Date.now()}`)
      .then(r => r.json())
      .then(d => {
        if (d.success && d.tree) {
          setTreeData(JSON.parse(JSON.stringify(d.tree)));
          setTreeVersion(v => v + 1);
        }
      })
      .catch(err => console.error('Error fetching workspace tree:', err));
  }, [workspaceRoot]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  // 3. Open file in editor
  const handleOpenFile = useCallback(async (filePath) => {
    if (!filePath) return;
    const cleanPath = String(filePath).trim().replace(/^["']|["']$/g, '');

    // Controlla se il file è già aperto nella lista
    setOpenFiles(prev => {
      const existing = prev.find(f => isSamePath(f.path, cleanPath));
      if (existing) {
        setActiveFilePath(existing.path);
        return prev;
      }
      return prev;
    });

    try {
      const res = await fetch(`/api/developer/fs/read?path=${encodeURIComponent(cleanPath)}`);
      const data = await res.json();
      if (data.success) {
        const resolvedPath = data.path || cleanPath;
        const newFile = {
          path: resolvedPath,
          filename: data.filename || cleanPath.split(/[/\\]/).pop(),
          content: data.content ?? '',
          originalContent: data.content ?? '',
          is_binary: !!data.is_binary,
          is_image: !!data.is_image,
          is_pdf: !!data.is_pdf,
          is_media: !!data.is_media,
          is_model: !!data.is_model,
          size_label: data.size_label,
          dirty: false
        };
        setOpenFiles(prev => {
          const already = prev.find(f => isSamePath(f.path, resolvedPath));
          if (already) return prev;
          return [...prev, newFile];
        });
        setActiveFilePath(resolvedPath);
      } else {
        addToast?.(data.error || 'Errore lettura file', 'error');
      }
    } catch (e) {
      addToast?.('Errore di connessione', 'error');
    }
  }, [addToast]);

  // Ascolto per aperture file richieste dall'esterno (es. Chat principale)
  useEffect(() => {
    const handleExternalOpen = (e) => {
      const targetPath = e.detail?.path;
      if (targetPath) {
        handleOpenFile(targetPath);
      }
    };
    window.addEventListener('sigma_dev_open_file', handleExternalOpen);

    const checkPending = () => {
      try {
        const pending = localStorage.getItem('sigma_dev_pending_open_file');
        if (pending) {
          localStorage.removeItem('sigma_dev_pending_open_file');
          handleOpenFile(pending);
        }
      } catch (e) {}
    };

    checkPending();
    const timer = setTimeout(checkPending, 250);

    return () => {
      window.removeEventListener('sigma_dev_open_file', handleExternalOpen);
      clearTimeout(timer);
    };
  }, [handleOpenFile]);

  // 4. Save file
  const handleSaveFile = async (filePath, content) => {
    try {
      const res = await fetch('/api/developer/fs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, content })
      });
      const data = await res.json();
      if (data.success) {
        setOpenFiles(prev => prev.map(f => isSamePath(f.path, filePath) ? { ...f, content, originalContent: content, dirty: false } : f));
        addToast?.('File salvato con successo', 'success');
        fetchTree();
      } else {
        addToast?.(data.error || 'Errore salvataggio file', 'error');
      }
    } catch (e) {
      addToast?.('Errore durante il salvataggio', 'error');
    }
  };

  // 5. Create new file or folder
  const handleCreateFile = async (parentPath) => {
    const filename = prompt('Nome del nuovo file (es. script.py, index.html):');
    if (!filename) return;
    const targetPath = `${parentPath}/${filename}`.replace(/\/+/g, '/');

    try {
      const res = await fetch('/api/developer/fs/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, is_dir: false })
      });
      const data = await res.json();
      if (data.success) {
        addToast?.('File creato', 'success');
        fetchTree();
        handleOpenFile(targetPath);
      } else {
        addToast?.(data.error || 'Errore creazione file', 'error');
      }
    } catch (e) {
      addToast?.('Errore durante la creazione', 'error');
    }
  };

  // 6. Delete file or folder
  const handleDeletePath = async (targetPath, isDir) => {
    const name = targetPath.split('/').pop();
    if (!confirm(`Sei sicuro di voler eliminare definitivamente ${isDir ? 'la cartella' : 'il file'} "${name}"?`)) {
      return;
    }

    try {
      const res = await fetch('/api/developer/fs/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, recursive: true })
      });
      const data = await res.json();
      if (data.success) {
        addToast?.(`${isDir ? 'Cartella' : 'File'} eliminato con successo`, 'success');
        // Close if open
        setOpenFiles(prev => prev.filter(f => f.path !== targetPath && !f.path.startsWith(targetPath + '/')));
        if (activeFilePath === targetPath || activeFilePath?.startsWith(targetPath + '/')) {
          setActiveFilePath(openFiles[0]?.path || null);
        }
        fetchTree();
      } else {
        addToast?.(data.error || 'Errore eliminazione', 'error');
      }
    } catch (e) {
      addToast?.('Errore eliminazione', 'error');
    }
  };

  // 7. Execute command in Terminal
  const handleExecuteTerminalCommand = async (command) => {
    if (!command.trim() || isRunningCommand) return;
    setIsRunningCommand(true);

    setTerminalLogs(prev => [
      ...prev,
      { type: 'command', text: command, cwd: workspaceRoot }
    ]);

    try {
      const res = await fetch('/api/developer/terminal/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, cwd: workspaceRoot, stream: false })
      });
      const data = await res.json();
      if (data.stdout) {
        setTerminalLogs(prev => [...prev, { type: 'stdout', text: data.stdout }]);
      }
      if (data.stderr) {
        setTerminalLogs(prev => [...prev, { type: 'stderr', text: data.stderr }]);
      }
      setTerminalLogs(prev => [
        ...prev,
        { type: 'info', text: `[Processo terminato con codice ${data.returncode} in ${data.duration_ms}ms]` }
      ]);
      fetchTree();
    } catch (err) {
      setTerminalLogs(prev => [
        ...prev,
        { type: 'stderr', text: `Errore esecuzione: ${err.message}` }
      ]);
    } finally {
      setIsRunningCommand(false);
    }
  };

  // 8. Run active file in terminal
  const handleRunFileInTerminal = (filePath) => {
    let cmd = '';
    if (filePath.endsWith('.py')) {
      cmd = `python "${filePath}"`;
    } else if (filePath.endsWith('.js')) {
      cmd = `node "${filePath}"`;
    } else if (filePath.endsWith('.ps1')) {
      cmd = `powershell -File "${filePath}"`;
    } else {
      cmd = `cat "${filePath}"`;
    }
    setTerminalExpanded(true);
    handleExecuteTerminalCommand(cmd);
  };

  // Content edit handler
  const handleContentChange = (path, newContent) => {
    setOpenFiles(prev => prev.map(f => {
      if (isSamePath(f.path, path)) {
        return {
          ...f,
          content: newContent,
          dirty: newContent !== f.originalContent
        };
      }
      return f;
    }));
  };

  // Tab close handler
  const handleCloseTab = (path) => {
    const nextFiles = openFiles.filter(f => !isSamePath(f.path, path));
    setOpenFiles(nextFiles);
    if (isSamePath(activeFilePath, path)) {
      setActiveFilePath(nextFiles[nextFiles.length - 1]?.path || null);
    }
  };

  // Resizable Panel Widths & Collapsed States
  const [leftWidth, setLeftWidth] = useState(() => {
    const saved = localStorage.getItem('sigma_dev_left_width');
    return saved ? Number(saved) : 260;
  });
  const [rightWidth, setRightWidth] = useState(() => {
    const saved = localStorage.getItem('sigma_dev_right_width');
    return saved ? Number(saved) : 380;
  });
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [headerPortalNode, setHeaderPortalNode] = useState(null);

  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isResizingLeft) {
        const newW = Math.min(550, Math.max(160, e.clientX));
        setLeftWidth(newW);
        localStorage.setItem('sigma_dev_left_width', newW);
      } else if (isResizingRight) {
        const newW = Math.min(750, Math.max(260, window.innerWidth - e.clientX));
        setRightWidth(newW);
        localStorage.setItem('sigma_dev_right_width', newW);
      }
    };

    const handleMouseUp = () => {
      setIsResizingLeft(false);
      setIsResizingRight(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    if (isResizingLeft || isResizingRight) {
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingLeft, isResizingRight]);

  return (
    <div style={{
      display: 'flex',
      width: '100%',
      height: '100%',
      overflow: 'hidden',
      background: isLight ? '#f6f8fa' : '#07090e',
      position: 'relative'
    }}>
      {/* 1. Left Panel: Workspace Explorer (Resizable & Collapsible) */}
      {!leftCollapsed ? (
        <div style={{
          width: `${leftWidth}px`,
          minWidth: `${leftWidth}px`,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative'
        }}>
          <WorkspaceExplorer
            key={treeVersion}
            treeData={treeData}
            activeFilePath={activeFilePath}
            workspaceRoot={workspaceRoot}
            workspaceRoots={workspaceRoots}
            onSelectWorkspaceRoot={setWorkspaceRoot}
            onFileSelect={handleOpenFile}
            onRefreshTree={fetchTree}
            onCreateFile={handleCreateFile}
            onDeletePath={handleDeletePath}
            onOpenGraph={handleOpenGraph}
            onAiCreate={(node) => setAiModalState({ isOpen: true, node })}
            onOpenStudy={(node) => handleOpenFile(node?.path)}
            onShowDiff={(node) => handleOpenFile(node?.path)}
            onAddCustomRoot={handleAddCustomRoot}
            onRemoveCustomRoot={handleRemoveCustomRoot}
            onRefreshRoots={fetchRoots}
            theme={theme}
            isLight={isLight}
          />
          {/* Telemetria e stato in tempo reale del micro-kernel nativo Rust */}
          <SigmaEngineNativeBar isLight={isLight} />
          {/* Il lavoro grande, spezzato e dato a piu' agenti */}
          <FanoutPanel workspaceRoot={workspaceRoot} isLight={isLight} />
          {/* Dove va a finire il lavoro fatto sui moduli */}
          <ModulePublisher isLight={isLight} />
        </div>
      ) : (
        <div 
          onClick={() => setLeftCollapsed(false)}
          title="Espandi Esploratore File"
          style={{
            width: '28px',
            height: '100%',
            background: isLight ? '#f6f8fa' : '#0d1117',
            borderRight: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            writingMode: 'vertical-rl',
            fontSize: '0.66rem',
            fontWeight: 700,
            color: '#8b949e',
            letterSpacing: '1px'
          }}
        >
          📂 ESPLORATORE
        </div>
      )}

      {/* Left Resizer Splitter */}
      {!leftCollapsed && (
        <div
          onMouseDown={() => setIsResizingLeft(true)}
          style={{
            width: '5px',
            cursor: 'col-resize',
            background: isResizingLeft ? '#00f2fe' : 'transparent',
            zIndex: 10,
            position: 'relative',
            transition: 'background 0.15s ease'
          }}
          onMouseEnter={e => { if (!isResizingLeft) e.currentTarget.style.background = 'rgba(0, 242, 254, 0.4)'; }}
          onMouseLeave={e => { if (!isResizingLeft) e.currentTarget.style.background = 'transparent'; }}
        />
      )}

      {/* 2 & 3. Main Center + Right Workspace Area with Unified Modern Top Header */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        minWidth: 0,
        position: 'relative'
      }}>
        {/* Unified Top Header Bar Container spanning both center and right columns */}
        <div 
          ref={node => { if (node && node !== headerPortalNode) setHeaderPortalNode(node); }}
          id="dev-studio-top-header"
          style={{
            width: '100%',
            flexShrink: 0,
            zIndex: 30
          }}
        />

        {/* Lower Split Area: Code Editor (Center) + Admin Chat (Right) */}
        <div style={{
          flex: 1,
          display: 'flex',
          width: '100%',
          overflow: 'hidden',
          minHeight: 0
        }}>
          {/* 2. Center Panel: Code Editor + Bottom Terminal */}
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            overflow: 'hidden',
            minWidth: '320px'
          }}>
            <McpQuickActionsBar
              workspaceRoot={workspaceRoot}
              onLogTerminal={(msg) => setTerminalLogs(prev => [...prev, msg])}
              isLight={isLight}
            />

            <CodeEditor
              openFiles={openFiles}
              activeFilePath={activeFilePath}
              onSelectTab={setActiveFilePath}
              onCloseTab={handleCloseTab}
              onContentChange={handleContentChange}
              onSaveFile={handleSaveFile}
              onRunFileInTerminal={handleRunFileInTerminal}
              onOpenGraph={handleOpenGraph}
              onAiCreate={(node) => setAiModalState({ isOpen: true, node })}
              workspaceRoot={workspaceRoot}
              activeDiff={activeDiff}
              onAcceptDiff={() => {
                setActiveDiff(null);
                fetchTree();
              }}
              onRejectDiff={() => setActiveDiff(null)}
              theme={theme}
              isLight={isLight}
            />

            {/* Striscia compatta ad una riga con lo stato dell'attività/agente in corso */}
            <ActivityTerminalStrip isLight={isLight} />

            <TerminalPanel
              workspaceRoot={workspaceRoot}
              isExpanded={terminalExpanded}
              onToggleExpand={() => setTerminalExpanded(!terminalExpanded)}
              terminalLogs={terminalLogs}
              onExecuteCommand={handleExecuteTerminalCommand}
              onClearLogs={() => setTerminalLogs([])}
              isRunningCommand={isRunningCommand}
              theme={theme}
              isLight={isLight}
            />
          </div>

          {/* Right Resizer Splitter */}
          {!rightCollapsed && (
            <div
              onMouseDown={() => setIsResizingRight(true)}
              style={{
                width: '5px',
                cursor: 'col-resize',
                background: isResizingRight ? '#00f2fe' : 'transparent',
                zIndex: 10,
                position: 'relative',
                transition: 'background 0.15s ease'
              }}
              onMouseEnter={e => { if (!isResizingRight) e.currentTarget.style.background = 'rgba(0, 242, 254, 0.4)'; }}
              onMouseLeave={e => { if (!isResizingRight) e.currentTarget.style.background = 'transparent'; }}
            />
          )}

          {/* 3. Right Panel: Admin AI Developer Agent (Resizable & Collapsible) */}
          {!rightCollapsed ? (
            <div style={{
              width: `${rightWidth}px`,
              minWidth: `${rightWidth}px`,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              position: 'relative'
            }}>
              <AdminAgentChat
                workspaceRoot={workspaceRoot}
                activeFilePath={activeFilePath}
                activeFileContent={openFiles.find(f => f.path === activeFilePath)?.content}
                onApplyDiff={(diff, path, content) => {
                  setActiveDiff(diff);
                  if (path) {
                    handleOpenFile(path);
                  }
                }}
                onOpenFile={handleOpenFile}
                onExecuteTerminalCommand={handleExecuteTerminalCommand}
                onRefreshTree={fetchTree}
                theme={theme}
                isLight={isLight}
                headerPortalNode={headerPortalNode}
              />
            </div>
          ) : (
            <div 
              onClick={() => setRightCollapsed(false)}
              title="Espandi Admin AI Chat"
              style={{
                width: '28px',
                height: '100%',
                background: isLight ? '#f6f8fa' : '#0d1117',
                borderLeft: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                writingMode: 'vertical-rl',
                fontSize: '0.66rem',
                fontWeight: 700,
                color: '#00f2fe',
                letterSpacing: '1px'
              }}
            >
              ⚡ ADMIN AI AGENT
            </div>
          )}
        </div>
      </div>
      {/* Modale Creazione Guidata con Ruoli AI */}
      <AiCreateFileModal
        isOpen={aiModalState.isOpen}
        onClose={() => setAiModalState({ isOpen: false, node: null })}
        targetFolderNode={aiModalState.node}
        workspaceRoot={workspaceRoot}
        onFileCreated={(createdPath) => {
          fetchTree();
          handleOpenFile(createdPath);
        }}
        addToast={addToast}
        isLight={isLight}
      />
    </div>
  );
}
