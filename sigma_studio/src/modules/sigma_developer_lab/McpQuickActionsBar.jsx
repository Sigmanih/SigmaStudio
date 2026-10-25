import React, { useState } from 'react';
import { Activity, Package, Gauge, Camera, Search, RefreshCw, X, Copy, Check, Terminal } from 'lucide-react';

/**
 * McpQuickActionsBar — Toolbar Azioni Rapide MCP per il Developer Studio
 * Permette agli sviluppatori di lanciare istantaneamente i server MCP avanzati:
 * - server_health (Stato ambiente, venv, file chiave)
 * - deps_audit (Verifica requisiti, sicurezza e coerenza)
 * - profile_app (Profiling cProfile / Node.js)
 * - screenshot_page (Cattura anteprima visiva browser)
 * - semantic_search / index (Indicizzazione semantica del codice)
 */
export default function McpQuickActionsBar({ workspaceRoot, onLogTerminal, isLight = false }) {
  const [runningTool, setRunningTool] = useState(null);
  const [modalResult, setModalResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const executeTool = async (toolName, params = {}, title = '') => {
    setRunningTool(toolName);
    try {
      const res = await fetch('/api/developer/mcp/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: toolName,
          arguments: params
        })
      });
      const data = await res.json();
      const outputText = data.message || data.content || (data.result ? JSON.stringify(data.result, null, 2) : 'Esecuzione completata.');
      
      setModalResult({
        title: title || toolName,
        success: data.success !== false,
        output: outputText
      });

      if (onLogTerminal) {
        onLogTerminal(`[MCP] ${toolName} completato: ${outputText.slice(0, 150)}...`);
      }
    } catch (e) {
      setModalResult({
        title: title || toolName,
        success: false,
        output: `Errore durante l'esecuzione del tool MCP: ${e.message}`
      });
    } finally {
      setRunningTool(null);
    }
  };

  const handleCopy = () => {
    if (!modalResult?.output) return;
    navigator.clipboard.writeText(modalResult.output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const actions = [
    {
      id: 'server_health',
      icon: Activity,
      label: 'Health Check',
      color: '#10b981',
      title: '🩺 Stato Workspace & Ambiente',
      onClick: () => executeTool('server_health', {}, '🩺 Health Check Workspace')
    },
    {
      id: 'deps_audit',
      icon: Package,
      label: 'Audit Dipendenze',
      color: '#00d2ff',
      title: '📦 Audit Dipendenze (Python & JS)',
      onClick: () => executeTool('deps_audit', {}, '📦 Audit Dipendenze')
    },
    {
      id: 'profile_app',
      icon: Gauge,
      label: 'Profila App',
      color: '#f59e0b',
      title: '⚡ Profiling Prestazioni (cProfile)',
      onClick: () => executeTool('profile_app', { target: 'sigma_server.py', language: 'python' }, '⚡ Profiling Applicazione')
    },
    {
      id: 'screenshot_page',
      icon: Camera,
      label: 'Screenshot UI',
      color: '#bc8cff',
      title: '📸 Screenshot Frontend Headless',
      onClick: () => executeTool('screenshot_page', { url: 'http://localhost:8000' }, '📸 Screenshot Frontend')
    },
    {
      id: 'index_status',
      icon: Search,
      label: 'Indice Semantico',
      color: '#ec4899',
      title: '🔍 Stato Indice Codice Semantico',
      onClick: () => executeTool('index_status', {}, '🔍 Stato Indice Semantico')
    }
  ];

  return (
    <>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 12px',
        background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.02)',
        borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)',
        overflowX: 'auto',
        flexShrink: 0
      }}>
        <span style={{
          fontSize: '0.66rem',
          fontWeight: 800,
          color: isLight ? '#57606a' : '#8b949e',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          marginRight: '4px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px'
        }}>
          ⚡ Tool MCP:
        </span>

        {actions.map(act => {
          const Icon = act.icon;
          const isBusy = runningTool === act.id;
          return (
            <button
              key={act.id}
              onClick={act.onClick}
              disabled={!!runningTool}
              title={act.title}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '3px 9px',
                borderRadius: '6px',
                fontSize: '0.72rem',
                fontWeight: 600,
                color: isLight ? '#24292f' : '#f0f6fc',
                background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
                cursor: runningTool ? 'not-allowed' : 'pointer',
                opacity: runningTool && !isBusy ? 0.6 : 1,
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap'
              }}
              onMouseEnter={e => {
                if (!runningTool) {
                  e.currentTarget.style.borderColor = act.color;
                  e.currentTarget.style.color = act.color;
                  e.currentTarget.style.background = isLight ? '#f6f8fa' : 'rgba(255,255,255,0.08)';
                }
              }}
              onMouseLeave={e => {
                if (!runningTool) {
                  e.currentTarget.style.borderColor = isLight ? '#d0d7de' : 'rgba(255,255,255,0.08)';
                  e.currentTarget.style.color = isLight ? '#24292f' : '#f0f6fc';
                  e.currentTarget.style.background = isLight ? '#ffffff' : 'rgba(255,255,255,0.04)';
                }
              }}
            >
              {isBusy ? (
                <RefreshCw size={12} className="spin" style={{ color: act.color }} />
              ) : (
                <Icon size={12} style={{ color: act.color }} />
              )}
              <span>{act.label}</span>
            </button>
          );
        })}
      </div>

      {/* Modal Risultato Esecuzione Tool */}
      {modalResult && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.65)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          padding: '20px'
        }}>
          <div style={{
            width: '100%',
            maxWidth: '680px',
            maxHeight: '80vh',
            background: isLight ? '#ffffff' : '#0d1117',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '12px',
            boxShadow: '0 16px 36px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.08)',
              background: isLight ? '#f6f8fa' : 'rgba(255,255,255,0.02)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1rem' }}>{modalResult.success ? '✅' : '⚠️'}</span>
                <span style={{ fontWeight: 700, fontSize: '0.88rem', color: isLight ? '#24292f' : '#f0f6fc' }}>
                  {modalResult.title}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={handleCopy}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 10px',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    borderRadius: '6px',
                    background: copied ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255,255,255,0.06)',
                    border: copied ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.1)',
                    color: copied ? '#10b981' : (isLight ? '#24292f' : '#e6edf3'),
                    cursor: 'pointer'
                  }}
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  <span>{copied ? 'Copiato!' : 'Copia'}</span>
                </button>
                <button
                  onClick={() => setModalResult(null)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '4px',
                    borderRadius: '6px',
                    background: 'transparent',
                    border: 'none',
                    color: '#8b949e',
                    cursor: 'pointer'
                  }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div style={{
              padding: '16px',
              overflowY: 'auto',
              flex: 1,
              fontFamily: 'Consolas, Monaco, "Courier New", monospace',
              fontSize: '0.78rem',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: isLight ? '#1f2328' : '#e6edf3',
              background: isLight ? '#f6f8fa' : '#090d13'
            }}>
              {modalResult.output}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
