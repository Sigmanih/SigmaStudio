import React, { useState, useEffect, useCallback } from 'react';
import { useApp } from '../../contexts/AppContext';
import WorkspaceExplorer from './WorkspaceExplorer';
import CodeEditor from './CodeEditor';
import TerminalPanel from './TerminalPanel';
import AdminAgentChat from './AdminAgentChat';

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

  // Terminal state
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [isRunningCommand, setIsRunningCommand] = useState(false);

  // 1. Fetch workspace roots
  useEffect(() => {
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
  }, []);

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
  const handleOpenFile = async (filePath) => {
    const existing = openFiles.find(f => f.path === filePath);
    if (existing) {
      setActiveFilePath(filePath);
      return;
    }

    try {
      const res = await fetch(`/api/developer/fs/read?path=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (data.success) {
        const newFile = {
          path: data.path,
          filename: data.filename,
          content: data.content,
          originalContent: data.content,
          is_binary: !!data.is_binary,
          is_image: !!data.is_image,
          is_pdf: !!data.is_pdf,
          is_media: !!data.is_media,
          is_model: !!data.is_model,
          size_label: data.size_label,
          dirty: false
        };
        setOpenFiles(prev => [...prev, newFile]);
        setActiveFilePath(data.path);
      } else {
        addToast?.(data.error || 'Errore lettura file', 'error');
      }
    } catch (e) {
      addToast?.('Errore di connessione', 'error');
    }
  };

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
        setOpenFiles(prev => prev.map(f => f.path === filePath ? { ...f, content, originalContent: content, dirty: false } : f));
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
      if (f.path === path) {
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
    const nextFiles = openFiles.filter(f => f.path !== path);
    setOpenFiles(nextFiles);
    if (activeFilePath === path) {
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
            theme={theme}
            isLight={isLight}
          />
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

      {/* 2. Center Panel: Code Editor + Bottom Terminal */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
        minWidth: '320px'
      }}>
        <CodeEditor
          openFiles={openFiles}
          activeFilePath={activeFilePath}
          onSelectTab={setActiveFilePath}
          onCloseTab={handleCloseTab}
          onContentChange={handleContentChange}
          onSaveFile={handleSaveFile}
          onRunFileInTerminal={handleRunFileInTerminal}
          activeDiff={activeDiff}
          onAcceptDiff={() => {
            setActiveDiff(null);
            fetchTree();
          }}
          onRejectDiff={() => setActiveDiff(null)}
          theme={theme}
          isLight={isLight}
        />

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
  );
}
