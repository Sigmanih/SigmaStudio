import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal as TermIcon, Play, Trash2, X, ChevronUp, ChevronDown, 
  Maximize2, Minimize2, CornerDownLeft, ShieldAlert, Sparkles 
} from 'lucide-react';

export default function TerminalPanel({
  workspaceRoot,
  isExpanded,
  onToggleExpand,
  terminalLogs = [],
  onExecuteCommand,
  onClearLogs,
  isRunningCommand = false,
  theme,
  isLight
}) {
  const [commandInput, setCommandInput] = useState('');
  const [history, setHistory] = useState([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const logEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [terminalLogs]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const cmd = commandInput.trim();
    if (!cmd) return;

    setHistory(prev => [cmd, ...prev]);
    setHistoryIdx(-1);
    setCommandInput('');
    onExecuteCommand(cmd);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length > 0 && historyIdx < history.length - 1) {
        const nextIdx = historyIdx + 1;
        setHistoryIdx(nextIdx);
        setCommandInput(history[nextIdx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx > 0) {
        const prevIdx = historyIdx - 1;
        setHistoryIdx(prevIdx);
        setCommandInput(history[prevIdx]);
      } else if (historyIdx === 0) {
        setHistoryIdx(-1);
        setCommandInput('');
      }
    }
  };

  const quickCommands = [
    { label: 'dir / ls', cmd: 'Get-ChildItem' },
    { label: 'git status', cmd: 'git status' },
    { label: 'python -V', cmd: 'python --version' },
    { label: 'npm test', cmd: 'npm test' }
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: isExpanded ? '260px' : '36px',
      background: isLight ? '#f6f8fa' : '#07090e',
      borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(0, 242, 254, 0.25)',
      transition: 'height 0.2s ease',
      overflow: 'hidden'
    }}>
      {/* Terminal Header Bar */}
      <div 
        onClick={onToggleExpand}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: isLight ? '#ebeef2' : '#0a0e14',
          borderBottom: isExpanded ? (isLight ? '1px solid #d0d7de' : '1px solid rgba(255, 255, 255, 0.08)') : 'none',
          cursor: 'pointer',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <TermIcon size={14} color="#00f2fe" />
          <span style={{ fontSize: '0.74rem', fontWeight: 800, color: isLight ? '#24292f' : '#f0f6fc' }}>
            TERMINALE ADMIN (POWERSHELL / BASH)
          </span>
          <span style={{
            fontSize: '0.62rem',
            padding: '1px 6px',
            borderRadius: '4px',
            background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)',
            color: '#8b949e',
            fontFamily: 'monospace'
          }}>
            {workspaceRoot || '.'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }} onClick={e => e.stopPropagation()}>
          {isExpanded && (
            <>
              {/* Quick Action Chips */}
              <div style={{ display: 'flex', gap: '4px' }}>
                {quickCommands.map(qc => (
                  <button
                    key={qc.label}
                    onClick={() => onExecuteCommand(qc.cmd)}
                    disabled={isRunningCommand}
                    style={{
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '0.64rem',
                      fontWeight: 600,
                      background: isLight ? '#ffffff' : '#161b22',
                      border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
                      color: isLight ? '#24292f' : '#c9d1d9',
                      cursor: 'pointer'
                    }}
                  >
                    {qc.label}
                  </button>
                ))}
              </div>

              <button
                onClick={onClearLogs}
                title="Pulisci Terminale"
                style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '2px' }}
              >
                <Trash2 size={12} />
              </button>
            </>
          )}

          <button
            onClick={onToggleExpand}
            style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '2px' }}
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {/* Terminal Output Area */}
      {isExpanded && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div 
            onClick={() => inputRef.current?.focus()}
            style={{
              flex: 1,
              padding: '8px 12px',
              overflowY: 'auto',
              fontFamily: '"JetBrains Mono", Consolas, monospace',
              fontSize: '0.74rem',
              lineHeight: 1.45,
              color: isLight ? '#24292f' : '#e6edf3',
              background: isLight ? '#ffffff' : '#07090e'
            }}
          >
            {terminalLogs.length === 0 ? (
              <div style={{ color: '#8b949e', fontStyle: 'italic', fontSize: '0.7rem' }}>
                Pronto. Digita un comando o usa l'AI Developer Agent per eseguire script, test e compilazioni.
              </div>
            ) : (
              terminalLogs.map((log, idx) => (
                <div key={idx} style={{ marginBottom: '4px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {log.type === 'command' && (
                    <div style={{ color: '#00f2fe', fontWeight: 700 }}>
                      <span style={{ color: '#3fb950' }}>PS {log.cwd || workspaceRoot}&gt; </span>
                      {log.text}
                    </div>
                  )}
                  {log.type === 'stdout' && (
                    <div style={{ color: isLight ? '#24292f' : '#c9d1d9' }}>{log.text}</div>
                  )}
                  {log.type === 'stderr' && (
                    <div style={{ color: '#ef4444' }}>{log.text}</div>
                  )}
                  {log.type === 'info' && (
                    <div style={{ color: '#d29922', fontSize: '0.68rem' }}>{log.text}</div>
                  )}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>

          {/* Interactive Command Input Bar */}
          <form 
            onSubmit={handleSubmit}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '6px 12px',
              background: isLight ? '#f6f8fa' : '#0d1117',
              borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)'
            }}
          >
            <span style={{ color: '#3fb950', fontSize: '0.74rem', fontWeight: 800, marginRight: '6px', userSelect: 'none' }}>
              PS&gt;
            </span>
            <input
              ref={inputRef}
              type="text"
              value={commandInput}
              onChange={e => setCommandInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRunningCommand ? "Comando in esecuzione..." : "Digita un comando PowerShell/Bash..."}
              disabled={isRunningCommand}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                color: isLight ? '#24292f' : '#00f2fe',
                fontSize: '0.76rem',
                fontFamily: '"JetBrains Mono", Consolas, monospace',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              disabled={isRunningCommand || !commandInput.trim()}
              style={{
                background: 'none',
                border: 'none',
                color: commandInput.trim() ? '#00f2fe' : '#8b949e',
                cursor: commandInput.trim() ? 'pointer' : 'default',
                padding: '2px'
              }}
            >
              <CornerDownLeft size={13} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
