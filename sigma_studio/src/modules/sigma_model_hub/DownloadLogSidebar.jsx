import React, { useState } from 'react';
import {
  Download, Activity, CheckCircle2, Pause, Play, X, AlertTriangle,
  RotateCcw, Trash2, Clock, HardDrive, Zap, ChevronRight, ChevronLeft,
  Calendar, Layers, Filter, Check
} from 'lucide-react';

export default function DownloadLogSidebar({
  isLight,
  downloads = [],
  onDownloadsChanged,
  addToast,
  onDeployRequested,
  isCollapsed = false,
  onToggleCollapse
}) {
  const [filter, setFilter] = useState('all'); // 'all' | 'active' | 'completed' | 'failed'

  const cardBg = isLight ? '#ffffff' : '#0e111a';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.20)' : '1px solid rgba(255, 255, 255, 0.06)';

  const handlePause = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⏸️ Download messo in pausa.', 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleResume = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('▶️ Ripresa download con auto-resume da disco.', 'success');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleCancel = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('🛑 Download annullato.', 'info');
        if (onDownloadsChanged) onDownloadsChanged();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const handleRemove = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, delete_files: false })
      });
      const json = await res.json();
      if (json.success && onDownloadsChanged) {
        onDownloadsChanged();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearCompleted = async () => {
    try {
      const res = await fetch('/api/models/hf/downloads/clear', { method: 'POST' });
      const json = await res.json();
      if (json.success && onDownloadsChanged) {
        onDownloadsChanged();
        if (addToast) addToast('🧹 Registro download completati ripulito.', 'info');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const activeTasks = downloads.filter(d => ['downloading', 'queued', 'paused'].includes(d.status));
  const completedTasks = downloads.filter(d => d.status === 'completed');
  const failedTasks = downloads.filter(d => ['failed', 'cancelled'].includes(d.status));

  const filteredTasks = downloads.filter(d => {
    if (filter === 'active') return ['downloading', 'queued', 'paused'].includes(d.status);
    if (filter === 'completed') return d.status === 'completed';
    if (filter === 'failed') return ['failed', 'cancelled'].includes(d.status);
    return true;
  });

  if (isCollapsed) {
    return (
      <div
        onClick={onToggleCollapse}
        style={{
          width: '46px',
          background: cardBg,
          border: cardBorder,
          borderRadius: '16px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '16px 8px',
          cursor: 'pointer',
          gap: '14px',
          transition: 'all 0.2s ease',
          userSelect: 'none',
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)'
        }}
        title="Espandi Log Download & Attività"
      >
        <button
          style={{
            background: 'none', border: 'none', color: '#00d2ff',
            cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}
        >
          <ChevronLeft size={18} />
        </button>

        <div style={{
          width: '28px', height: '28px', borderRadius: '8px',
          background: 'rgba(0, 210, 255, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          {activeTasks.length > 0 ? (
            <Activity size={15} color="#00d2ff" className="mh-spin" />
          ) : (
            <Download size={15} color="#00d2ff" />
          )}
        </div>

        {activeTasks.length > 0 && (
          <span style={{
            fontSize: '0.62rem', fontWeight: 900, color: '#00d2ff',
            background: 'rgba(0, 210, 255, 0.2)', padding: '2px 5px', borderRadius: '10px'
          }}>
            {activeTasks.length}
          </span>
        )}

        <div style={{
          writingMode: 'vertical-rl',
          transform: 'rotate(180deg)',
          fontSize: '0.72rem',
          fontWeight: 800,
          color: textMuted,
          letterSpacing: '0.5px',
          marginTop: '10px'
        }}>
          LOG DOWNLOAD ({downloads.length})
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        width: '340px',
        minWidth: '300px',
        maxWidth: '380px',
        background: cardBg,
        border: cardBorder,
        borderRadius: '18px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '16px 18px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        backdropFilter: 'blur(16px)',
        alignSelf: 'stretch'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: subBorder, paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '30px', height: '30px', borderRadius: '8px',
            background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(0, 144, 255, 0.2))',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            {activeTasks.length > 0 ? (
              <Activity size={16} color="#00d2ff" className="mh-spin" />
            ) : (
              <Download size={16} color="#00d2ff" />
            )}
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
              Log Download & Attività
            </h3>
            <div style={{ fontSize: '0.66rem', color: textMuted, marginTop: '1px' }}>
              {activeTasks.length > 0
                ? `${activeTasks.length} in download attivo`
                : `${completedTasks.length} modelli scaricati`}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            onClick={handleClearCompleted}
            title="Pulisci download completati dal registro"
            style={{
              background: 'none', border: 'none', color: textMuted,
              cursor: 'pointer', padding: '5px', borderRadius: '6px',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
          >
            <Trash2 size={13} />
          </button>
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              title="Comprimi pannello laterale"
              style={{
                background: 'none', border: 'none', color: textMuted,
                cursor: 'pointer', padding: '5px', borderRadius: '6px',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}
            >
              <ChevronRight size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '4px', background: subBg, padding: '3px', borderRadius: '8px' }}>
        {[
          { id: 'all', label: `Tutti (${downloads.length})` },
          { id: 'active', label: `In Corso (${activeTasks.length})` },
          { id: 'completed', label: `Finiti (${completedTasks.length})` },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            style={{
              flex: 1, padding: '4px 6px', borderRadius: '6px', border: 'none',
              background: filter === tab.id ? (isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.1)') : 'transparent',
              color: filter === tab.id ? (isLight ? '#000000' : '#00d2ff') : textMuted,
              fontSize: '0.66rem', fontWeight: 800, cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tasks List Container */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: '8px',
        maxHeight: 'calc(100vh - 280px)', overflowY: 'auto', paddingRight: '2px'
      }}>
        {filteredTasks.length === 0 ? (
          <div style={{
            padding: '30px 12px', textAlign: 'center', color: textMuted,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px'
          }}>
            <Download size={22} color={textMuted} />
            <span style={{ fontSize: '0.74rem', fontWeight: 600 }}>Nessuna attività registrata.</span>
          </div>
        ) : (
          filteredTasks.map(task => {
            const isRunning = task.status === 'downloading' || task.status === 'queued';
            const isPaused = task.status === 'paused';
            const isDone = task.status === 'completed';
            const isFailed = task.status === 'failed' || task.status === 'cancelled';

            return (
              <div
                key={task.task_id}
                style={{
                  padding: '10px 12px', borderRadius: '12px',
                  background: subBg,
                  border: isRunning
                    ? '1.5px solid rgba(0, 210, 255, 0.45)'
                    : (isFailed ? '1px solid rgba(239, 68, 68, 0.3)' : subBorder),
                  display: 'flex', flexDirection: 'column', gap: '6px',
                  boxShadow: isRunning ? '0 0 12px rgba(0, 210, 255, 0.1)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                {/* Title & Status */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '6px' }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      {isRunning && <Activity className="mh-spin" size={12} color="#00d2ff" />}
                      {isDone && <CheckCircle2 size={12} color="#10b981" />}
                      {isPaused && <Pause size={12} color="#ffb86c" />}
                      {isFailed && <AlertTriangle size={12} color="#ef4444" />}
                      <span style={{
                        fontSize: '0.75rem', fontWeight: 800, color: textPrimary,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block'
                      }}>
                        {task.model_id || task.filename}
                      </span>
                    </div>

                    {/* Date / Time info */}
                    <div style={{ fontSize: '0.62rem', color: textMuted, marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Calendar size={10} />
                      <span>{task.completed_at_label || task.created_at_label || 'Recente'}</span>
                      {task.total_mb > 0 && (
                        <>
                          <span>•</span>
                          <span>{task.total_mb >= 1024 ? `${(task.total_mb/1024).toFixed(1)} GB` : `${task.total_mb} MB`}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Actions / Status Pill */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0 }}>
                    {isRunning ? (
                      <button
                        onClick={() => handlePause(task.task_id)}
                        title="Metti in pausa"
                        style={{
                          padding: '3px 6px', borderRadius: '5px',
                          border: '1px solid rgba(255, 184, 108, 0.4)', background: 'rgba(255, 184, 108, 0.1)',
                          color: '#ffb86c', fontSize: '0.62rem', fontWeight: 700, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '2px'
                        }}
                      >
                        <Pause size={9} />
                      </button>
                    ) : (isPaused || isFailed) ? (
                      <button
                        onClick={() => handleResume(task.task_id)}
                        title="Riprendi download da disco"
                        style={{
                          padding: '3px 6px', borderRadius: '5px',
                          border: '1px solid rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.1)',
                          color: '#10b981', fontSize: '0.62rem', fontWeight: 700, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '2px'
                        }}
                      >
                        <Play size={9} />
                      </button>
                    ) : isDone && onDeployRequested ? (
                      <button
                        onClick={() => onDeployRequested({
                          filename: task.filename,
                          model_id: task.model_id,
                          path: task.save_path
                        })}
                        title="Avvia in SigmaEngine"
                        style={{
                          padding: '2px 6px', borderRadius: '5px',
                          border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                          color: '#ffffff', fontSize: '0.62rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '2px'
                        }}
                      >
                        <Zap size={9} /> Avvia
                      </button>
                    ) : null}

                    {isRunning && (
                      <button
                        onClick={() => handleCancel(task.task_id)}
                        title="Annulla"
                        style={{
                          padding: '3px 6px', borderRadius: '5px',
                          border: '1px solid rgba(239, 68, 68, 0.3)', background: 'rgba(239, 68, 68, 0.1)',
                          color: '#ef4444', fontSize: '0.62rem', cursor: 'pointer', display: 'flex', alignItems: 'center'
                        }}
                      >
                        <X size={9} />
                      </button>
                    )}

                    {!isRunning && (
                      <button
                        onClick={() => handleRemove(task.task_id)}
                        title="Rimuovi dal registro"
                        style={{
                          background: 'none', border: 'none', color: textMuted,
                          cursor: 'pointer', padding: '2px 4px', display: 'flex', alignItems: 'center'
                        }}
                      >
                        <X size={11} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar (if in progress or paused) */}
                {isRunning && (
                  <>
                    <div style={{ height: '3px', borderRadius: '2px', background: 'rgba(255, 255, 255, 0.08)', overflow: 'hidden' }}>
                      <div style={{
                        width: `${task.progress_pct}%`, height: '100%',
                        background: 'linear-gradient(90deg, #00d2ff, #0090ff)',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                      <span>
                        {task.downloaded_mb || 0} / {task.total_mb || '...'} MB
                        {task.speed_mbps ? ` • ${task.speed_mbps} MB/s` : ''}
                      </span>
                      <span style={{ color: '#00d2ff', fontWeight: 800 }}>
                        {task.progress_pct}%
                      </span>
                    </div>
                  </>
                )}

                {isFailed && task.error_message && (
                  <div style={{ fontSize: '0.60rem', color: '#ef4444', fontWeight: 600, wordBreak: 'break-all' }}>
                    {task.error_message}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
