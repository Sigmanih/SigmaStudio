import React, { useState, useCallback } from 'react';
import {
  Terminal,
  FileText,
  Folder,
  Search,
  GitBranch,
  Zap,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Eye,
  Code,
  AlertCircle,
  CheckCircle2,
  Loader
} from 'lucide-react';

export default function ChatToolActionItem({
  action,
  onFileClick,
  onOpenInDevStudio,
  diffKey,
  isDiffExpanded,
  onToggleDiff,
  onRollback,
  isRollbackable,
  hasBeenRolledBack
}) {
  const [expandedContent, setExpandedContent] = useState(false);
  const [expandedTerminal, setExpandedTerminal] = useState(false);
  const [expandedDetails, setExpandedDetails] = useState(false);
  const [copied, setCopied] = useState(false);

  // Normalizzazione metadati dell'azione
  const tool = (action.tool || action.type || 'tool').toLowerCase();
  const rawPath = action.path || action.params?.path || action.params?.file_path || action.params?.target_file || action.result?.path || action.result?.full_path || '';
  const path = typeof rawPath === 'string' ? rawPath : (rawPath?.path || '');
  const command = action.command || action.params?.command || action.params?.cmd || action.result?.command || (tool === 'terminal' ? action.params?.raw : '') || '';
  const stdout = action.stdout !== undefined ? action.stdout : (action.result?.stdout || '');
  const stderr = action.stderr !== undefined ? action.stderr : (action.result?.stderr || '');
  const returncode = action.returncode !== undefined ? action.returncode : action.result?.returncode;
  const content = action.content !== undefined ? action.content : (action.result?.content || '');
  const diff = action.diff;
  const error = action.error || action.result?.error || '';
  const isSuccess = action.status === 'success' || (action.status !== 'error' && action.success !== false && !error);
  const isRunning = action.status === 'running';

  // Identificazione del tipo di tool
  const isReadFile = tool === 'read_file' || tool === 'read' || (!command && !!path && (!!content || tool.includes('read')));
  const isTerminal = tool === 'terminal' || tool === 'shell' || tool === 'exec' || tool === 'command' || !!command;
  const isListDir = tool === 'list_dir' || tool === 'glob' || tool === 'ls';
  const isSearch = tool === 'search_code' || tool === 'find_symbol' || tool === 'grep';
  const isGit = tool.startsWith('git_') || tool === 'git';
  const isCargo = tool.startsWith('cargo_');
  const isDocker = tool.startsWith('docker_');

  // Icona tematica
  const renderIcon = () => {
    if (isRunning) {
      return <Loader size={13} style={{ color: '#00d2ff', animation: 'spin 1s linear infinite' }} />;
    }
    if (isTerminal) return <Terminal size={13} style={{ color: '#00f2fe' }} />;
    if (isReadFile) return <FileText size={13} style={{ color: '#a371f7' }} />;
    if (isListDir) return <Folder size={13} style={{ color: '#e3b341' }} />;
    if (isSearch) return <Search size={13} style={{ color: '#79c0ff' }} />;
    if (isGit) return <GitBranch size={13} style={{ color: '#ff7b72' }} />;
    if (isCargo) return <Code size={13} style={{ color: '#f0883e' }} />;
    return <Zap size={13} style={{ color: '#00d2ff' }} />;
  };

  const handleCopy = useCallback((text) => {
    if (!text) return;
    try {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {}
  }, []);

  const lineCount = content ? content.split('\n').length : 0;
  const hasTerminalOutput = stdout || stderr || returncode !== undefined;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
      margin: '3px 0',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Riga Principale della Tool Action */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        background: isRunning ? 'rgba(0, 210, 255, 0.05)' : 'rgba(255, 255, 255, 0.02)',
        border: isRunning
          ? '1px solid rgba(0, 210, 255, 0.3)'
          : isSuccess
            ? '1px solid rgba(255, 255, 255, 0.06)'
            : '1px solid rgba(255, 85, 85, 0.3)',
        borderRadius: '8px',
        fontSize: '0.75rem',
        backdropFilter: 'blur(8px)',
        transition: 'all 0.15s ease'
      }}>
        {/* Lato Sinistro: Icona, Badge Tool, Descrizione / Percorso / Comando */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
          <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {renderIcon()}
          </span>

          {/* Badge del nome tool */}
          <span style={{
            fontSize: '0.65rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            padding: '2px 6px',
            borderRadius: '4px',
            background: isTerminal
              ? 'rgba(0, 242, 254, 0.12)'
              : isReadFile
                ? 'rgba(163, 113, 247, 0.12)'
                : 'rgba(255, 255, 255, 0.06)',
            color: isTerminal ? '#00f2fe' : isReadFile ? '#bc8cff' : '#8b949e',
            flexShrink: 0
          }}>
            {tool}
          </span>

          {/* Dettaglio descrittivo */}
          {isReadFile ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, overflow: 'hidden' }}>
              <span
                onClick={() => path && onFileClick && onFileClick(path)}
                title={path ? `Clicca per aprire ${path}` : ''}
                style={{
                  color: path ? '#79c0ff' : '#8b949e',
                  fontWeight: 500,
                  textDecoration: path ? 'underline' : 'none',
                  textUnderlineOffset: '2px',
                  cursor: path ? 'pointer' : 'default',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap'
                }}
              >
                {path || 'lettura file'}
              </span>
              {lineCount > 0 && (
                <span style={{
                  fontSize: '0.65rem',
                  color: '#8b949e',
                  background: 'rgba(255, 255, 255, 0.04)',
                  padding: '1px 5px',
                  borderRadius: '4px',
                  flexShrink: 0
                }}>
                  {lineCount} righe
                </span>
              )}
            </div>
          ) : isTerminal ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, overflow: 'hidden' }}>
              <span
                onClick={() => hasTerminalOutput && setExpandedTerminal(prev => !prev)}
                title={command ? `$ ${command}` : ''}
                style={{
                  fontFamily: 'Consolas, Monaco, monospace',
                  color: '#adbac7',
                  background: 'rgba(0, 0, 0, 0.25)',
                  padding: '1px 6px',
                  borderRadius: '4px',
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  cursor: hasTerminalOutput ? 'pointer' : 'default'
                }}
              >
                $ {command || action.message || 'comando shell'}
              </span>
              {returncode !== undefined && (
                <span style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  color: returncode === 0 ? '#3fb950' : '#ff7b72',
                  background: returncode === 0 ? 'rgba(63, 185, 80, 0.1)' : 'rgba(255, 123, 114, 0.1)',
                  padding: '1px 5px',
                  borderRadius: '4px',
                  flexShrink: 0
                }}>
                  exit {returncode}
                </span>
              )}
            </div>
          ) : (
            <span style={{
              color: '#adbac7',
              textOverflow: 'ellipsis',
              overflow: 'hidden',
              whiteSpace: 'nowrap'
            }}>
              {action.message || error || tool}
            </span>
          )}
        </div>

        {/* Lato Destro: Azioni interattive e pulsanti */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0, marginLeft: '8px' }}>
          {/* File Reading Actions */}
          {isReadFile && path && (
            <>
              {content && (
                <button
                  onClick={() => setExpandedContent(prev => !prev)}
                  title={expandedContent ? 'Chiudi anteprima contenuto' : 'Mostra contenuto letto'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: expandedContent ? 'rgba(163, 113, 247, 0.25)' : 'rgba(163, 113, 247, 0.1)',
                    border: '1px solid rgba(163, 113, 247, 0.3)',
                    color: '#d2a8ff',
                    fontSize: '0.65rem',
                    padding: '2px 7px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  <Eye size={11} />
                  <span>{expandedContent ? 'Nascondi' : 'Leggi'}</span>
                  {expandedContent ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                </button>
              )}

              {onFileClick && (
                <button
                  onClick={() => onFileClick(path)}
                  title="Apri file nel visualizzatore"
                  style={{
                    background: 'rgba(0, 210, 255, 0.08)',
                    border: '1px solid rgba(0, 210, 255, 0.25)',
                    color: 'var(--primary, #00d2ff)',
                    fontSize: '0.65rem',
                    padding: '2px 7px',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Visualizza 📄
                </button>
              )}

              {onOpenInDevStudio && (
                <button
                  onClick={() => onOpenInDevStudio(path)}
                  title="Apri nell'editor del Developer Studio"
                  style={{
                    background: 'rgba(0, 210, 255, 0.08)',
                    border: '1px solid rgba(0, 210, 255, 0.25)',
                    color: '#00d2ff',
                    fontSize: '0.65rem',
                    padding: '2px 7px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  Dev Studio 🛠️
                </button>
              )}
            </>
          )}

          {/* Terminal Actions */}
          {isTerminal && hasTerminalOutput && (
            <button
              onClick={() => setExpandedTerminal(prev => !prev)}
              title={expandedTerminal ? 'Nascondi output console' : 'Visualizza output terminale (stdout/stderr)'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                background: expandedTerminal ? 'rgba(0, 242, 254, 0.2)' : 'rgba(0, 242, 254, 0.08)',
                border: '1px solid rgba(0, 242, 254, 0.25)',
                color: '#00f2fe',
                fontSize: '0.65rem',
                padding: '2px 7px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 600
              }}
            >
              <Terminal size={11} />
              <span>{expandedTerminal ? 'Nascondi Output' : 'Output Terminale'}</span>
              {expandedTerminal ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </button>
          )}

          {/* Generic Diff Toggle */}
          {diff && onToggleDiff && (
            <button
              onClick={() => onToggleDiff(diffKey)}
              style={{
                background: isDiffExpanded ? 'rgba(0, 210, 255, 0.2)' : 'rgba(0, 210, 255, 0.08)',
                border: '1px solid rgba(0, 210, 255, 0.25)',
                color: 'var(--primary, #00d2ff)',
                fontSize: '0.65rem',
                padding: '2px 7px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              {isDiffExpanded ? 'Nascondi Diff' : 'Mostra Modifiche'}
            </button>
          )}

          {/* Generic Details Toggle for other tools */}
          {!isReadFile && !isTerminal && (action.result || action.params) && (
            <button
              onClick={() => setExpandedDetails(prev => !prev)}
              style={{
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: '#8b949e',
                fontSize: '0.65rem',
                padding: '2px 6px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              {expandedDetails ? 'Meno' : 'Dettagli'}
            </button>
          )}

          {/* Rollback button */}
          {isRollbackable && onRollback && (
            <button
              onClick={() => onRollback(action.backup_id)}
              disabled={hasBeenRolledBack}
              style={{
                background: hasBeenRolledBack ? 'transparent' : 'rgba(255, 85, 85, 0.15)',
                border: hasBeenRolledBack ? 'none' : '1px solid rgba(255, 85, 85, 0.3)',
                color: hasBeenRolledBack ? '#3fb950' : '#ff5555',
                fontSize: '0.65rem',
                padding: '2px 7px',
                borderRadius: '4px',
                cursor: hasBeenRolledBack ? 'default' : 'pointer'
              }}
            >
              {hasBeenRolledBack ? 'Annullato ✓' : 'Annulla'}
            </button>
          )}

          {/* Status Icon */}
          <span style={{ fontSize: '0.75rem', marginLeft: '2px' }}>
            {isRunning ? (
              <span style={{ color: '#00d2ff' }}>●</span>
            ) : isSuccess ? (
              <span style={{ color: '#3fb950' }} title="Esecuzione completata con successo">✓</span>
            ) : (
              <span style={{ color: '#ff5555' }} title={error || 'Errore durante l\'esecuzione'}>✗</span>
            )}
          </span>
        </div>
      </div>

      {/* Box Espanso: Contenuto del File Letto */}
      {isReadFile && expandedContent && content && (
        <div style={{
          background: '#090d16',
          border: '1px solid rgba(163, 113, 247, 0.25)',
          borderRadius: '6px',
          overflow: 'hidden',
          fontSize: '0.72rem',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
          marginTop: '2px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '5px 10px',
            background: 'rgba(163, 113, 247, 0.08)',
            borderBottom: '1px solid rgba(163, 113, 247, 0.15)',
            fontSize: '0.7rem',
            color: '#bc8cff'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileText size={12} />
              <span style={{ fontWeight: 600 }}>Contenuto di {path}</span>
              <span style={{ color: '#8b949e' }}>({lineCount} righe)</span>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={() => handleCopy(content)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'transparent',
                  border: 'none',
                  color: copied ? '#3fb950' : '#8b949e',
                  cursor: 'pointer',
                  fontSize: '0.65rem'
                }}
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                <span>{copied ? 'Copiato!' : 'Copia'}</span>
              </button>
              {onOpenInDevStudio && path && (
                <button
                  onClick={() => onOpenInDevStudio(path)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#00d2ff',
                    cursor: 'pointer',
                    fontSize: '0.65rem',
                    fontWeight: 600
                  }}
                >
                  Apri nell'IDE ↗
                </button>
              )}
            </div>
          </div>
          <div style={{
            padding: '8px 12px',
            maxHeight: '320px',
            overflowY: 'auto',
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            lineHeight: '1.4',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            color: '#adbac7',
            background: '#070a10'
          }}>
            {content}
          </div>
        </div>
      )}

      {/* Box Espanso: Console di Output Terminale */}
      {isTerminal && expandedTerminal && (
        <div style={{
          background: '#070a11',
          border: '1px solid rgba(0, 242, 254, 0.25)',
          borderRadius: '6px',
          overflow: 'hidden',
          fontSize: '0.72rem',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5)',
          marginTop: '2px'
        }}>
          {/* Header console */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '5px 10px',
            background: 'rgba(0, 242, 254, 0.08)',
            borderBottom: '1px solid rgba(0, 242, 254, 0.15)',
            fontSize: '0.7rem',
            color: '#00f2fe'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={12} />
              <span style={{ fontWeight: 600 }}>Console Terminale</span>
              {returncode !== undefined && (
                <span style={{
                  color: returncode === 0 ? '#3fb950' : '#ff7b72',
                  fontWeight: 600,
                  fontSize: '0.65rem'
                }}>
                  (Exit code {returncode})
                </span>
              )}
            </div>
            <button
              onClick={() => handleCopy(`${stdout}\n${stderr}`.trim())}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                background: 'transparent',
                border: 'none',
                color: copied ? '#3fb950' : '#8b949e',
                cursor: 'pointer',
                fontSize: '0.65rem'
              }}
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              <span>{copied ? 'Copiato!' : 'Copia Output'}</span>
            </button>
          </div>

          {/* Body console */}
          <div style={{
            padding: '8px 12px',
            maxHeight: '300px',
            overflowY: 'auto',
            fontFamily: 'Consolas, Monaco, monospace',
            lineHeight: '1.35',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            background: '#05070c'
          }}>
            {/* Comando eseguito */}
            <div style={{ color: '#00d2ff', marginBottom: '6px', fontWeight: 600 }}>
              $ {command || 'terminal'}
            </div>

            {/* Output standard (stdout) */}
            {stdout && (
              <div style={{ color: '#adbac7', marginBottom: stderr ? '6px' : '0' }}>
                {stdout}
              </div>
            )}

            {/* Errori terminale (stderr) */}
            {stderr && (
              <div style={{ color: '#ff7b72', background: 'rgba(255, 123, 114, 0.08)', padding: '4px 6px', borderRadius: '4px' }}>
                {stderr}
              </div>
            )}

            {/* Fallback se vuoto */}
            {!stdout && !stderr && (
              <div style={{ color: '#57606a', fontStyle: 'italic' }}>
                (Comando terminato con codice {returncode !== undefined ? returncode : 0}, nessun output su stdout/stderr)
              </div>
            )}
          </div>
        </div>
      )}

      {/* Box Espanso: Dettagli Generici / Risultato Tool */}
      {expandedDetails && (
        <div style={{
          background: '#090b10',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '6px',
          padding: '8px 10px',
          fontSize: '0.7rem',
          fontFamily: 'Consolas, Monaco, monospace',
          color: '#8b949e',
          maxHeight: '200px',
          overflowY: 'auto',
          whiteSpace: 'pre-wrap'
        }}>
          {action.result ? JSON.stringify(action.result, null, 2) : JSON.stringify(action.params || {}, null, 2)}
        </div>
      )}

      {/* Box Espanso: Diff Modifiche File */}
      {diff && isDiffExpanded && (
        <div className="action-diff-container" style={{
          background: '#090b10',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: '6px',
          padding: '8px 10px',
          fontFamily: 'Consolas, Monaco, monospace',
          fontSize: '0.7rem',
          lineHeight: '1.25rem',
          overflowX: 'auto',
          whiteSpace: 'pre',
          color: '#adbac7',
          marginTop: '2px',
          maxHeight: '350px',
          boxShadow: 'inset 0 0 10px rgba(0,0,0,0.5)'
        }}>
          {diff.split('\n').map((line, lineIdx) => {
            let lineStyle = { padding: '2px 4px', borderRadius: '2px', display: 'block' };
            if (line.startsWith('+') && !line.startsWith('+++')) {
              lineStyle.background = 'rgba(46, 160, 67, 0.15)';
              lineStyle.color = '#3fb950';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              lineStyle.background = 'rgba(248, 81, 73, 0.15)';
              lineStyle.color = '#f85149';
            } else if (line.startsWith('@@')) {
              lineStyle.color = '#79c0ff';
              lineStyle.background = 'rgba(121, 192, 255, 0.05)';
              lineStyle.fontWeight = 'bold';
            }
            return <span key={lineIdx} style={lineStyle}>{line}</span>;
          })}
        </div>
      )}
    </div>
  );
}
