import React, { useState, useEffect } from 'react';
import { 
  Trash2, X, RefreshCw, Cpu, Database, History, 
  ShieldAlert, Sparkles, CheckSquare, Square, AlertCircle, HardDrive, CheckCircle2
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

export default function SystemCleanupModal({ isOpen, onClose }) {
  const { theme, addToast } = useApp();
  const isLight = theme === 'light';

  const [loadingStats, setLoadingStats] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [stats, setStats] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  // Selected options
  const [options, setOptions] = useState({
    free_memory: true,
    stop_background_tasks: true,
    clear_tasks: true,
    clear_history: false,
    clear_backups: false,
    clear_cache: true
  });

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await fetch('/api/system/cleanup/stats');
      const data = await res.json();
      if (data.success) {
        setStats(data);
      }
    } catch (e) {
      console.error('Failed to fetch cleanup stats:', e);
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setLastResult(null);
      fetchStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const toggleOption = (key) => {
    setOptions(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const selectAll = () => {
    setOptions({
      free_memory: true,
      stop_background_tasks: true,
      clear_tasks: true,
      clear_history: true,
      clear_backups: true,
      clear_cache: true
    });
  };

  const deselectAll = () => {
    setOptions({
      free_memory: false,
      stop_background_tasks: false,
      clear_tasks: false,
      clear_history: false,
      clear_backups: false,
      clear_cache: false
    });
  };

  const handleExecuteCleanup = async () => {
    setCleaning(true);
    try {
      const res = await fetch('/api/system/cleanup/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options)
      });
      const data = await res.json();
      if (data.success) {
        setLastResult(data);
        addToast(data.message || 'Pulizia completata con successo.', 'success');
        if (options.clear_history) {
          try {
            localStorage.removeItem('sigma_chat_sessions');
            localStorage.removeItem('sigma_active_session');
            Object.keys(localStorage).forEach(k => {
              if (k.startsWith('sigma_chat_msgs_') || k.startsWith('sigma_chat_session_')) {
                localStorage.removeItem(k);
              }
            });
          } catch (e) {}
          window.dispatchEvent(new CustomEvent('sigma-chat-cleared', { detail: { clear_history: true } }));
        }
        window.dispatchEvent(new CustomEvent('sigma-system-cleanup-done', { detail: options }));
        await fetchStats();
      } else {
        addToast(data.error || 'Errore durante la pulizia.', 'error');
      }
    } catch (err) {
      addToast('Errore di connessione: ' + err.message, 'error');
    } finally {
      setCleaning(false);
    }
  };

  let selectedDiskBytes = 0;
  if (stats) {
    if (options.clear_tasks) selectedDiskBytes += (stats.tasks?.bytes || 0);
    if (options.clear_history) selectedDiskBytes += (stats.history?.bytes || 0);
    if (options.clear_backups) selectedDiskBytes += (stats.backups?.bytes || 0);
    if (options.clear_cache) selectedDiskBytes += (stats.cache?.bytes || 0);
  }

  const formatBytes = (bytes) => {
    if (!bytes || bytes <= 0) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 99999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)'
    }}>
      <div style={{
        width: '94%',
        maxWidth: '680px',
        maxHeight: '90vh',
        borderRadius: '16px',
        background: isLight ? '#ffffff' : '#0d1117',
        border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255, 255, 255, 0.12)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5), 0 0 30px rgba(0, 242, 254, 0.15)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        color: isLight ? '#24292f' : '#f0f6fc'
      }}>
        
        <div style={{
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255, 255, 255, 0.08)',
          background: isLight ? 'linear-gradient(135deg, rgba(0,242,254,0.06), rgba(124,91,240,0.06))' : 'linear-gradient(135deg, rgba(0,242,254,0.08), rgba(124,91,240,0.08))'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(0, 242, 254, 0.3)'
            }}>
              <Trash2 size={20} color="#000" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.2px' }}>
                Centro Pulizia & Ottimizzazione Sistema
              </h2>
              <p style={{ margin: 0, fontSize: '0.72rem', color: isLight ? '#57606a' : '#8b949e' }}>
                Libera memoria e pulisci task o snapshot in tempo reale senza interrompere Sigma Studio
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={fetchStats}
              disabled={loadingStats}
              title="Aggiorna dimensioni e statistiche"
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#57606a' : '#8b949e',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px'
              }}
            >
              <RefreshCw size={16} className={loadingStats ? 'spin' : ''} />
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#57606a' : '#8b949e',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px'
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div style={{
          padding: '8px 20px',
          background: isLight ? 'rgba(63, 185, 80, 0.08)' : 'rgba(63, 185, 80, 0.1)',
          borderBottom: isLight ? '1px solid rgba(63, 185, 80, 0.2)' : '1px solid rgba(63, 185, 80, 0.15)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.70rem',
          color: '#3fb950',
          fontWeight: 600
        }}>
          <CheckCircle2 size={14} />
          <span>Sigma Studio Server rimane sempre ATTIVO e pronto all'uso dopo ogni pulizia.</span>
        </div>

        <div style={{
          padding: '16px 20px',
          overflowY: 'auto',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: isLight ? '#57606a' : '#8b949e' }}>
              Seleziona le aree da ottimizzare:
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                onClick={selectAll}
                style={{
                  background: 'none', border: 'none', color: '#00f2fe', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Seleziona Tutto
              </button>
              <span style={{ color: isLight ? '#d0d7de' : '#30363d' }}>|</span>
              <button
                type="button"
                onClick={deselectAll}
                style={{
                  background: 'none', border: 'none', color: '#8b949e', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Deseleziona
              </button>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('free_memory')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.free_memory 
                ? (isLight ? 'rgba(0, 242, 254, 0.08)' : 'rgba(0, 242, 254, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.free_memory 
                ? '1px solid rgba(0, 242, 254, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.free_memory ? '#00f2fe' : '#8b949e' }}>
              {options.free_memory ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Cpu size={15} color="#00f2fe" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Libera Memoria RAM & VRAM</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(0, 242, 254, 0.15)',
                  color: '#00f2fe'
                }}>
                  {stats?.memory?.is_model_loaded ? `VRAM Modello: ${stats.memory.vram_formatted}` : `RAM Processo: ${stats?.memory?.ram_formatted || '~350 MB'}`}
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                {stats?.memory?.is_model_loaded 
                  ? `Scarica il modello residente '${stats.memory.loaded_model}' dalla VRAM e forza la liberazione della memoria.`
                  : 'Svuota la cache allocata e forza il Garbage Collector del runtime.'}
              </p>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('stop_background_tasks')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.stop_background_tasks 
                ? (isLight ? 'rgba(255, 184, 108, 0.08)' : 'rgba(255, 184, 108, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.stop_background_tasks 
                ? '1px solid rgba(255, 184, 108, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.stop_background_tasks ? '#ffb86c' : '#8b949e' }}>
              {options.stop_background_tasks ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <RefreshCw size={15} color="#ffb86c" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Arresta Task di Background in Corso</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(255, 184, 108, 0.15)',
                  color: '#ffb86c'
                }}>
                  {stats?.background_tasks?.total_active ? `${stats.background_tasks.total_active} attivi` : 'Nessuno attivo'}
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                Arresta e stacca download di modelli o conversioni GGUF senza chiudere il server.
              </p>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('clear_tasks')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.clear_tasks 
                ? (isLight ? 'rgba(124, 91, 240, 0.08)' : 'rgba(124, 91, 240, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.clear_tasks 
                ? '1px solid rgba(124, 91, 240, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.clear_tasks ? '#a78bfa' : '#8b949e' }}>
              {options.clear_tasks ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Database size={15} color="#a78bfa" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Azzera Task & Roadmap Eseguiti</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(124, 91, 240, 0.15)',
                  color: '#a78bfa'
                }}>
                  {stats?.tasks?.formatted || '0 B'}
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                Svuota i registri dei task eseguiti in Developer Studio (developer_tasks.json) e Roadmap.
              </p>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('clear_history')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.clear_history 
                ? (isLight ? 'rgba(56, 189, 248, 0.08)' : 'rgba(56, 189, 248, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.clear_history 
                ? '1px solid rgba(56, 189, 248, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.clear_history ? '#38bdf8' : '#8b949e' }}>
              {options.clear_history ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <History size={15} color="#38bdf8" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Cancella Cronologia Chat & Sessioni</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8'
                }}>
                  {stats?.history?.formatted || '0 B'} ({stats?.history?.count || 0} sessioni)
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                Rimuove i log delle conversazioni archiviate in data/conversations e nel context broker.
              </p>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('clear_backups')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.clear_backups 
                ? (isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.clear_backups 
                ? '1px solid rgba(239, 68, 68, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.clear_backups ? '#ef4444' : '#8b949e' }}>
              {options.clear_backups ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ShieldAlert size={15} color="#ef4444" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Elimina Snapshot e File di Backup (.sigma_backups)</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  color: '#ef4444'
                }}>
                  {stats?.backups?.formatted || '0 B'} ({stats?.backups?.count || 0} snapshot)
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                Elimina tutti gli snapshot di backup automatici creati prima delle modifiche ai file.
              </p>
            </div>
          </div>

          <div 
            onClick={() => toggleOption('clear_cache')}
            style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: options.clear_cache 
                ? (isLight ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.06)')
                : (isLight ? '#f6f8fa' : '#161b22'),
              border: options.clear_cache 
                ? '1px solid rgba(16, 185, 129, 0.4)' 
                : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'),
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              transition: 'all 0.15s ease'
            }}
          >
            <div style={{ marginTop: '2px', color: options.clear_cache ? '#10b981' : '#8b949e' }}>
              {options.clear_cache ? <CheckSquare size={16} /> : <Square size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <HardDrive size={15} color="#10b981" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Svuota Cache Temporanee (__pycache__, pytest)</span>
                </div>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981'
                }}>
                  {stats?.cache?.formatted || '0 B'}
                </span>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.70rem', color: isLight ? '#57606a' : '#8b949e', lineHeight: 1.4 }}>
                Rimuove file bytecode .pyc e cache dei test per liberare spazio su disco.
              </p>
            </div>
          </div>

          {lastResult && (
            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: 'rgba(63, 185, 80, 0.12)',
              border: '1px solid #3fb950',
              fontSize: '0.72rem',
              color: '#3fb950',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontWeight: 800 }}>✓ {lastResult.message}</div>
              {lastResult.cleaned && (
                <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
                  {lastResult.cleaned.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

        </div>

        <div style={{
          padding: '14px 20px',
          borderTop: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255, 255, 255, 0.08)',
          background: isLight ? '#f6f8fa' : '#07090e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ fontSize: '0.68rem', color: isLight ? '#57606a' : '#8b949e' }}>
              Spazio selezionato da liberare:
            </div>
            <div style={{ fontSize: '0.86rem', fontWeight: 800, color: '#00f2fe' }}>
              {formatBytes(selectedDiskBytes)} {options.free_memory ? '+ RAM/VRAM' : ''}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                background: isLight ? '#e1e4e8' : '#21262d',
                border: 'none',
                color: isLight ? '#24292f' : '#c9d1d9',
                fontSize: '0.74rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Chiudi
            </button>
            <button
              type="button"
              onClick={handleExecuteCleanup}
              disabled={cleaning || (!options.free_memory && !options.stop_background_tasks && !options.clear_tasks && !options.clear_history && !options.clear_backups && !options.clear_cache)}
              style={{
                padding: '8px 18px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                border: 'none',
                color: '#000000',
                fontSize: '0.74rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 4px 14px rgba(0, 242, 254, 0.35)',
                opacity: cleaning ? 0.7 : 1
              }}
            >
              {cleaning ? <RefreshCw size={14} className="spin" /> : <Sparkles size={14} />}
              <span>{cleaning ? 'Pulizia in corso...' : 'Esegui Pulizia'}</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}