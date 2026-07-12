import React, { useState, useMemo } from 'react';
import { 
  Plus, Edit, PlusCircle, CheckCircle2, Clock, ChevronRight, Trash2, 
  AlertCircle, Filter, X, FileText, BookOpen, Terminal, PieChart
} from 'lucide-react';

// ==============================================================================
// RoadmapView — Modern Kanban-style Task Board with filters & file references
// ==============================================================================

export function RoadmapView({ tasks, onEdit, onAdd, onDelete, onToggleStatus, onOpenFile, onClearAll }) {
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterModule, setFilterModule] = useState('all');

  const modules = useMemo(() => {
    const mods = new Set();
    tasks.forEach(t => (t.moduli || []).forEach(m => mods.add(m)));
    return ['all', ...Array.from(mods).sort()];
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      if (filterStatus !== 'all' && t.status !== filterStatus) return false;
      if (filterModule !== 'all' && !(t.moduli || []).includes(filterModule)) return false;
      return true;
    });
  }, [tasks, filterStatus, filterModule]);

  const stats = useMemo(() => {
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'done').length;
    const inCorso = tasks.filter(t => t.status === 'in_corso').length;
    const blocked = tasks.filter(t => t.status === 'blocked').length;
    return { total, done, inCorso, blocked, progress: total > 0 ? Math.round((done / total) * 100) : 0 };
  }, [tasks]);

  const priorityColors = {
    critica: { bg: 'rgba(255,85,85,0.15)', color: '#ff5555', label: 'Critica' },
    alta: { bg: 'rgba(255,184,108,0.15)', color: '#ffb86c', label: 'Alta' },
    media: { bg: 'rgba(0,210,255,0.12)', color: '#00d2ff', label: 'Media' },
    bassa: { bg: 'rgba(148,148,165,0.12)', color: '#9494a5', label: 'Bassa' },
  };

  const statusIcons = {
    done: <CheckCircle2 size={16} color="#3fb950" />,
    in_corso: <Clock size={16} color="#00d2ff" />,
    blocked: <AlertCircle size={16} color="#ff5555" />,
  };

  const statusLabels = {
    done: 'Completato',
    in_corso: 'In Corso',
    blocked: 'Bloccato',
  };

  const getFileIcon = (type) => {
    switch (type) {
      case 'test': return <Terminal size={14} />;
      case 'viz': return <PieChart size={14} />;
      case 'whitepaper': return <BookOpen size={14} />;
      default: return <FileText size={14} />;
    }
  };

  return (
    <div className="roadmap-view">
      <style>{`
        .roadmap-view {
          height: 100%; display: flex; flex-direction: column; overflow: hidden;
          padding: 24px; background: transparent;
        }
        .roadmap-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 20px; flex-shrink: 0;
        }
        .roadmap-header h2 {
          font-size: 1.2rem; font-weight: 700; color: #e2e4eb;
          display: flex; align-items: center; gap: 10px;
        }
        .roadmap-header h2 span { font-size: 0.55rem; color: #5a5e72; font-weight: 400; }
        .roadmap-header .btn-add-task {
          padding: 10px 20px; border-radius: 8px; font-size: 0.8rem; font-weight: 600;
          cursor: pointer; border: 1px solid rgba(0,210,255,0.3);
          background: rgba(0,210,255,0.1); color: #00d2ff;
          display: flex; align-items: center; gap: 8px; transition: all 0.15s;
          font-family: inherit;
        }
        .roadmap-header .btn-add-task:hover { background: rgba(0,210,255,0.2); box-shadow: 0 0 20px rgba(0,210,255,0.15); }

        /* Stats bar */
        .roadmap-stats {
          display: flex; gap: 12px; margin-bottom: 16px; flex-shrink: 0;
        }
        .stat-card {
          flex: 1; padding: 14px 16px; border-radius: 10px;
          background: #11131b; border: 1px solid #1e2030;
          display: flex; flex-direction: column; gap: 4px;
        }
        .stat-card .stat-value { font-size: 1.4rem; font-weight: 700; }
        .stat-card .stat-label { font-size: 0.6rem; color: #5a5e72; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card .stat-bar { height: 3px; border-radius: 2px; margin-top: 6px; background: #1e2030; overflow: hidden; }
        .stat-card .stat-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

        /* Filters */
        .roadmap-filters {
          display: flex; gap: 8px; margin-bottom: 16px; flex-shrink: 0; align-items: center;
        }
        .filter-btn-group { display: flex; gap: 2px; }
        .filter-btn {
          padding: 5px 12px; border-radius: 6px; font-size: 0.6rem; cursor: pointer;
          border: 1px solid #1e2030; background: transparent; color: #5a5e72;
          font-family: inherit; transition: all 0.12s;
        }
        .filter-btn:hover { color: #8b8fa3; border-color: #2a2d3e; }
        .filter-btn.active { color: #00d2ff; border-color: rgba(0,210,255,0.3); background: rgba(0,210,255,0.08); }
        .filter-select {
          padding: 5px 10px; border-radius: 6px; font-size: 0.6rem;
          border: 1px solid #1e2030; background: #11131b; color: #8b8fa3;
          font-family: inherit; cursor: pointer; outline: none;
        }

        /* Task grid */
        .roadmap-grid {
          flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px;
          padding-right: 4px;
        }
        .roadmap-grid::-webkit-scrollbar { width: 3px; }
        .roadmap-grid::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 2px; }

        /* Task card */
        .task-card-rd {
          background: #11131b; border: 1px solid #1e2030; border-radius: 10px;
          padding: 14px 16px; transition: all 0.15s; cursor: pointer;
        }
        .task-card-rd:hover { border-color: #2a2d3e; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .task-card-rd.status-done { opacity: 0.7; }
        .task-card-rd.status-done:hover { opacity: 0.85; }
        .task-card-rd.status-blocked { border-left: 3px solid #ff5555; }
        .task-card-rd.status-done { border-left: 3px solid #3fb950; }
        .task-card-rd.status-in_corso { border-left: 3px solid #00d2ff; }

        .tc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
        .tc-mod-badge {
          font-size: 0.5rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;
          background: rgba(0,210,255,0.1); color: #00d2ff; letter-spacing: 0.5px;
        }
        .tc-priority {
          font-size: 0.5rem; font-weight: 600; padding: 2px 8px; border-radius: 4px;
        }
        .tc-title {
          font-size: 0.85rem; font-weight: 600; color: #e2e4eb;
          margin-bottom: 4px; line-height: 1.3;
        }
        .tc-desc {
          font-size: 0.65rem; color: #5a5e72; margin-bottom: 8px;
          line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .tc-footer {
          display: flex; align-items: center; justify-content: space-between; gap: 8px;
        }
        .tc-status {
          display: flex; align-items: center; gap: 6px; font-size: 0.6rem; color: #5a5e72;
        }
        .tc-actions { display: flex; gap: 4px; }
        .tc-btn {
          padding: 4px 8px; border-radius: 4px; font-size: 0.55rem; cursor: pointer;
          border: 1px solid #1e2030; background: transparent; color: #5a5e72;
          font-family: inherit; transition: all 0.12s; display: flex; align-items: center; gap: 4px;
        }
        .tc-btn:hover { border-color: #2a2d3e; color: #8b8fa3; }
        .tc-btn.done:hover { border-color: #3fb950; color: #3fb950; background: rgba(63,185,80,0.08); }
        .tc-btn.del:hover { border-color: #ff5555; color: #ff5555; background: rgba(255,85,85,0.08); }

        /* Reference files in task card */
        .tc-files {
          display: flex; gap: 4px; flex-wrap: wrap; margin-top: 6px; padding-top: 6px;
          border-top: 1px solid rgba(255,255,255,0.03);
        }
        .tc-file-link {
          display: flex; align-items: center; gap: 3px; padding: 2px 6px;
          border-radius: 4px; font-size: 0.5rem; cursor: pointer;
          background: rgba(255,255,255,0.03); color: #5a5e72;
          transition: all 0.12s; border: 1px solid transparent;
        }
        .tc-file-link:hover { background: rgba(255,255,255,0.06); color: #8b8fa3; border-color: #1e2030; }
        .tc-file-link .tc-fl-icon { width: 12px; display: flex; align-items: center; }

        .empty-roadmap {
          flex: 1; display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 10px; color: #5a5e72; font-size: 0.75rem;
        }
        .empty-roadmap .big-icon { font-size: 2rem; opacity: 0.3; }
      `}</style>

      {/* Header */}
      <div className="roadmap-header">
        <h2>
          🗺️ Research Roadmap
          <span>{stats.total} tasks</span>
        </h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          {tasks.length > 1 && (
            <button className="btn-add-task" onClick={() => {
              if (confirm(`Eliminare TUTTI i ${tasks.length} task? Opera irreversibile.`)) {
                onClearAll && onClearAll();
              }
            }} style={{ background: 'rgba(255,85,85,0.1)', borderColor: 'rgba(255,85,85,0.3)', color: '#ff5555' }}>
              <Trash2 size={16} /> Cancella tutti
            </button>
          )}
          <button className="btn-add-task" onClick={onAdd}>
            <Plus size={18} /> Nuovo Task
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="roadmap-stats">
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#e2e4eb' }}>{stats.total}</div>
          <div className="stat-label">Totale Task</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#3fb950' }}>{stats.done}</div>
          <div className="stat-label">Completati</div>
          <div className="stat-bar"><div className="stat-bar-fill" style={{ width: stats.progress + '%', background: '#3fb950' }} /></div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#00d2ff' }}>{stats.inCorso}</div>
          <div className="stat-label">In Corso</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: stats.blocked > 0 ? '#ff5555' : '#5a5e72' }}>{stats.blocked}</div>
          <div className="stat-label">Bloccati</div>
        </div>
      </div>

      {/* Filters */}
      <div className="roadmap-filters">
        <span style={{ fontSize: '0.6rem', color: '#5a5e72', marginRight: '4px' }}>Filtri:</span>
        <div className="filter-btn-group">
          {[
            { key: 'all', label: 'Tutti' },
            { key: 'in_corso', label: 'In Corso' },
            { key: 'done', label: 'Completati' },
            { key: 'blocked', label: 'Bloccati' },
          ].map(f => (
            <button key={f.key} className={`filter-btn ${filterStatus === f.key ? 'active' : ''}`} onClick={() => setFilterStatus(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
        <select className="filter-select" value={filterModule} onChange={e => setFilterModule(e.target.value)}>
          <option value="all">Tutti i moduli</option>
          {modules.filter(m => m !== 'all').map(m => (
            <option key={m} value={m}>Modulo {m}</option>
          ))}
        </select>
        {(filterStatus !== 'all' || filterModule !== 'all') && (
          <button className="filter-btn" onClick={() => { setFilterStatus('all'); setFilterModule('all'); }} style={{ color: '#ff5555' }}>
            <X size={12} /> Reset
          </button>
        )}
      </div>

      {/* Task list */}
      <div className="roadmap-grid">
        {filteredTasks.length === 0 && (
          <div className="empty-roadmap" style={{ gap: '20px', padding: '48px 24px' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(0,210,255,0.1) 0%, rgba(188,140,255,0.08) 100%)',
              border: '1px solid rgba(0,210,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.6rem'
            }}>
              📋
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e2e4eb', marginBottom: '4px' }}>
                Nessun task ancora
              </div>
              <div style={{ fontSize: '0.7rem', color: '#5a5e72', lineHeight: 1.5 }}>
                Crea il tuo primo task per pianificare e tracciare<br />le attività di ricerca della roadmap.
              </div>
            </div>
            <button
              className="btn-add-task"
              onClick={onAdd}
              style={{
                padding: '10px 22px',
                fontSize: '0.72rem',
                background: 'linear-gradient(135deg, #00d2ff 0%, #0099cc 100%)',
                border: 'none',
                borderRadius: '8px',
                color: '#000',
                cursor: 'pointer',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 20px rgba(0,210,255,0.2)',
                transition: 'all 0.15s'
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 6px 28px rgba(0,210,255,0.3)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,210,255,0.2)'; }}
            >
              <Plus size={16} /> Crea il primo task
            </button>
          </div>
        )}
        {filteredTasks.map((task, i) => {
          const prio = priorityColors[task.priorita] || priorityColors.media;
          return (
            <div key={task.id || i} className={`task-card-rd status-${task.status}`} onClick={() => onEdit(task)}>
              <div className="tc-header">
                <span className="tc-mod-badge">MOD {task.moduli?.[0] || '??'}</span>
                <span className="tc-priority" style={{ background: prio.bg, color: prio.color }}>{prio.label}</span>
              </div>
              <div className="tc-title">{task.titolo}</div>
              {task.descrizione && <div className="tc-desc">{task.descrizione}</div>}
              
              {/* Reference files */}
              {task.files && task.files.length > 0 && (
                <div className="tc-files">
                  {task.files.map((f, fi) => (
                    <span key={fi} className="tc-file-link" onClick={(e) => { e.stopPropagation(); onOpenFile && onOpenFile(f.path); }} title={f.path}>
                      <span className="tc-fl-icon">{getFileIcon(f.type)}</span>
                      {f.filename}
                    </span>
                  ))}
                </div>
              )}

              <div className="tc-footer">
                <div className="tc-status">
                  {statusIcons[task.status]} {statusLabels[task.status]}
                </div>
                <div className="tc-actions">
                  {task.status !== 'done' && (
                    <button className="tc-btn done" onClick={(e) => { e.stopPropagation(); onToggleStatus(task); }}>
                      <CheckCircle2 size={12} /> Completa
                    </button>
                  )}
                  {task.status === 'done' && (
                    <button className="tc-btn" onClick={(e) => { e.stopPropagation(); onToggleStatus(task); }}>
                      <Clock size={12} /> Riapri
                    </button>
                  )}
                  <button className="tc-btn del" onClick={(e) => { e.stopPropagation(); onDelete(task); }}>
                    <Trash2 size={12} /> Elimina
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ==============================================================================
// Dashboard — Right sidebar summary widget
// ==============================================================================

export default function Dashboard({ 
  tasks, 
  rightVisible, 
  setRightVisible, 
  toggleTaskStatus, 
  setEditingTask, 
  setIsTaskModalOpen,
  deleteTask,
  activeTabId
}) {
  const isResearchMode = activeTabId && activeTabId.startsWith('research_lab');

  const [researchObjectives, setResearchObjectives] = useState(window.__activeSessionObjectives || []);
  const [researchName, setResearchName] = useState(window.__activeSessionName || '');
  const [researchProgress, setResearchProgress] = useState(window.__activeSessionProgress || { done: 0, total: 0 });
  const [expandedTaskId, setExpandedTaskId] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');

  React.useEffect(() => {
    const handleUpdate = () => {
      setResearchObjectives(window.__activeSessionObjectives || []);
      setResearchName(window.__activeSessionName || '');
      setResearchProgress(window.__activeSessionProgress || { done: 0, total: 0 });
    };
    window.addEventListener('sigma-research-objectives-updated', handleUpdate);
    handleUpdate();
    return () => window.removeEventListener('sigma-research-objectives-updated', handleUpdate);
  }, [activeTabId]);

  const total = isResearchMode ? researchProgress.total : tasks.length;
  const done = isResearchMode ? researchProgress.done : tasks.filter(t => t.status === 'done').length;
  const progress = total > 0 ? Math.round((done / total) * 100) : 0;

  const filteredObjectives = useMemo(() => {
    return researchObjectives.filter(obj => {
      if (filterStatus === 'all') return true;
      if (filterStatus === 'done') return obj.status === 'done' || obj.status === 'failed';
      return obj.status === filterStatus;
    });
  }, [researchObjectives, filterStatus]);

  return (
    <section className="dashboard">
      <button className="collapse-btn right" onClick={() => setRightVisible(!rightVisible)}>
         <ChevronRight size={14} style={{transform: rightVisible ? 'none' : 'rotate(180deg)'}} />
      </button>
      <div className="dashboard-content">
        <div className="dash-header" style={{ flexShrink: 0 }}>
          <h3 className="glow-text" style={{fontSize: '1rem', letterSpacing: '1px'}}>
            {isResearchMode ? '🔬 Lab Objectives' : '📊 Research Status'}
          </h3>
        </div>

        <div className="dash-section" style={{ flexShrink: 0, marginTop: '8px' }}>
          <div className="section-title" style={{ margin: '8px 0' }}>PROGRESSO GLOBALE</div>
          <div className="progress-ring-container" style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
            <div style={{ position: 'relative', width: '70px', height: '70px' }}>
              <svg width="70" height="70" viewBox="0 0 70 70">
                <circle cx="35" cy="35" r="30" fill="none" stroke="#1e2030" strokeWidth="5" />
                <circle cx="35" cy="35" r="30" fill="none" stroke="#3fb950" strokeWidth="5"
                  strokeDasharray={`${2 * Math.PI * 30}`} strokeDashoffset={`${2 * Math.PI * 30 * (1 - progress / 100)}`}
                  strokeLinecap="round" transform="rotate(-90 35 35)" style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
              </svg>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: '1rem', fontWeight: 700, color: '#3fb950' }}>
                {progress}%
              </div>
            </div>
            <div style={{ fontSize: '0.55rem', color: '#5a5e72' }}>{done}/{total} completati</div>
          </div>
        </div>

        <div className="dash-section" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, marginTop: '8px' }}>
          {isResearchMode ? (
            <>
              <div className="section-title" style={{ margin: '8px 0', flexShrink: 0 }}>TASK ATTIVI DEL LAB</div>
              
              {/* Filtri orizzontali */}
              <div className="rl-filter-row" style={{ display: 'flex', gap: '4px', margin: '4px 0 8px 0', overflowX: 'auto', paddingBottom: '4px', flexShrink: 0 }}>
                {[
                  { id: 'all', label: 'Tutti' },
                  { id: 'pending', label: 'In attesa' },
                  { id: 'in_progress', label: 'In corso' },
                  { id: 'done', label: 'Finiti' }
                ].map(f => {
                  const active = filterStatus === f.id;
                  return (
                    <button
                      key={f.id}
                      onClick={() => setFilterStatus(f.id)}
                      style={{
                        padding: '4px 8px',
                        fontSize: '0.58rem',
                        fontWeight: 600,
                        borderRadius: '6px',
                        border: '1px solid rgba(255,255,255,0.06)',
                        background: active ? 'rgba(0,210,255,0.12)' : 'rgba(255,255,255,0.02)',
                        color: active ? '#00d2ff' : '#8b8fa3',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        transition: 'all 0.15s'
                      }}
                    >
                      {f.label}
                    </button>
                  );
                })}
              </div>

              {/* Lista scrollabile */}
              <div className="tasks-list" style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '10px', 
                flex: 1, 
                overflowY: 'auto', 
                minHeight: 0, 
                paddingRight: '4px' 
              }}>
                {filteredObjectives.map((obj, i) => {
                  const statusColors = {
                    pending: { bg: 'rgba(90,94,114,0.06)', border: '1px solid rgba(90,94,114,0.15)', text: '#8b8fa3', label: 'In attesa' },
                    in_progress: { bg: 'rgba(0,210,255,0.06)', border: '1px solid rgba(0,210,255,0.15)', text: '#00d2ff', label: 'In Corso' },
                    done: { bg: 'rgba(63,185,80,0.06)', border: '1px solid rgba(63,185,80,0.15)', text: '#3fb950', label: 'Completato' },
                    failed: { bg: 'rgba(255,85,85,0.06)', border: '1px solid rgba(255,85,85,0.15)', text: '#ff5555', label: 'Fallito' }
                  };
                  const c = statusColors[obj.status] || statusColors.pending;
                  const isExpanded = expandedTaskId === obj.id;
                  return (
                    <div 
                      key={obj.id || i} 
                      className={`task-card status-${obj.status}`}
                      onClick={() => setExpandedTaskId(isExpanded ? null : obj.id)}
                      style={{
                        background: `linear-gradient(135deg, ${c.bg} 0%, rgba(21,23,38,0.2) 100%)`,
                        border: c.border,
                        borderRadius: '10px',
                        padding: '12px 14px',
                        position: 'relative',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        boxShadow: isExpanded ? '0 4px 15px rgba(0,0,0,0.25)' : 'none'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span className="mod-chip" style={{
                          background: 'rgba(255,255,255,0.04)',
                          color: '#e2e4eb',
                          fontSize: '0.55rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: 600
                        }}>
                          {obj.assigned_to}
                        </span>
                        <span style={{ fontSize: '0.55rem', fontWeight: 700, color: c.text }}>
                          {c.label.toUpperCase()}
                        </span>
                      </div>
                      <p style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        margin: '4px 0',
                        color: '#e2e4eb',
                        lineHeight: 1.3
                      }}>
                        {obj.title}
                      </p>
                      <p style={{
                        fontSize: '0.62rem',
                        color: '#8b8fa3',
                        margin: '4px 0 0 0',
                        lineHeight: 1.3,
                        display: isExpanded ? 'block' : '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: isExpanded ? 'visible' : 'hidden'
                      }}>
                        {obj.description}
                      </p>

                      {isExpanded && (
                        <div 
                          style={{
                            marginTop: '10px',
                            paddingTop: '10px',
                            borderTop: '1px solid rgba(255,255,255,0.04)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '8px'
                          }}
                          onClick={e => e.stopPropagation()}
                        >
                          {obj.completion_criteria && (
                            <div>
                              <div style={{ fontSize: '0.55rem', color: '#5a5e72', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '2px' }}>Criteri Completamento</div>
                              <div style={{ fontSize: '0.62rem', color: '#e2e4eb', lineHeight: 1.2 }}>{obj.completion_criteria}</div>
                            </div>
                          )}
                          {obj.actions_hint && obj.actions_hint.length > 0 && (
                            <div>
                              <div style={{ fontSize: '0.55rem', color: '#5a5e72', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '2px' }}>Azioni Richieste</div>
                              <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap', marginTop: '2px' }}>
                                {obj.actions_hint.map((act, idx) => (
                                  <span key={idx} style={{ fontSize: '0.5rem', background: 'rgba(255,255,255,0.03)', color: '#8b8fa3', padding: '1px 4px', borderRadius: '3px' }}>
                                    {act}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {obj.result && (
                            <div>
                              <div style={{ fontSize: '0.55rem', color: '#5a5e72', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '2px' }}>Risultati ed Esito</div>
                              <div style={{
                                fontSize: '0.62rem',
                                color: '#b2c0d4',
                                lineHeight: 1.3,
                                background: 'rgba(0,0,0,0.2)',
                                padding: '6px 8px',
                                borderRadius: '6px',
                                maxHeight: '120px',
                                overflowY: 'auto',
                                fontFamily: 'monospace',
                                whiteSpace: 'pre-wrap',
                                border: '1px solid rgba(255,255,255,0.02)'
                              }}>
                                {obj.result}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {filteredObjectives.length === 0 && (
                  <p className="empty-hint" style={{ fontSize: '0.62rem', color: '#5a5e72', textAlign: 'center', marginTop: '12px' }}>
                    Nessun task per il filtro selezionato.
                  </p>
                )}
              </div>
            </>
          ) : (
            <>
              <div className="section-title" style={{ flexShrink: 0 }}>
                TASK IN EVIDENZA
                <PlusCircle size={14} style={{color: 'var(--primary)'}} onClick={() => { setEditingTask(null); setIsTaskModalOpen(true); }} />
              </div>
              <div className="tasks-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: '4px' }}>
                {tasks.map((task, i) => (
                  <div key={i} 
                    className={`task-card status-${task.status}`} 
                    onClick={() => { setEditingTask(task); setIsTaskModalOpen(true); }}
                    style={{
                      background: task.status === 'done' 
                        ? 'linear-gradient(135deg, rgba(63,185,80,0.06) 0%, rgba(63,185,80,0.02) 100%)' 
                        : task.status === 'blocked'
                        ? 'linear-gradient(135deg, rgba(255,85,85,0.06) 0%, rgba(255,85,85,0.02) 100%)'
                        : 'linear-gradient(135deg, rgba(210,153,34,0.06) 0%, rgba(210,153,34,0.02) 100%)',
                      border: task.status === 'done' 
                        ? '1px solid rgba(63,185,80,0.15)' 
                        : task.status === 'blocked'
                        ? '1px solid rgba(255,85,85,0.15)'
                        : '1px solid rgba(210,153,34,0.15)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                      transition: 'all 0.15s'
                    }}>
                    <div className="task-header">
                      {task.moduli?.[0] ? (
                        <span className="mod-chip" style={{
                          background: task.status === 'done' ? 'rgba(63,185,80,0.12)' : task.status === 'blocked' ? 'rgba(255,85,85,0.12)' : 'rgba(210,153,34,0.12)',
                          color: task.status === 'done' ? '#3fb950' : task.status === 'blocked' ? '#ff5555' : '#d29922',
                          fontSize: '0.6rem',
                          padding: '2px 8px',
                          borderRadius: '5px',
                          fontWeight: 600,
                          letterSpacing: '0.5px'
                        }}>
                          MOD {task.moduli[0]}
                        </span>
                      ) : (
                        <span />
                      )}
                      <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                        <span className={`priority-tag ${task.priorita}`} style={{
                          fontSize: '0.58rem',
                          padding: '2px 8px',
                          borderRadius: '5px',
                          fontWeight: 600,
                          letterSpacing: '0.5px',
                          background: task.priorita === 'alta' ? 'rgba(255,85,85,0.12)' : task.priorita === 'media' ? 'rgba(210,153,34,0.12)' : 'rgba(0,210,255,0.12)',
                          color: task.priorita === 'alta' ? '#ff5555' : task.priorita === 'media' ? '#d29922' : '#00d2ff'
                        }}>
                          {task.priorita}
                        </span>
                        <Trash2 size={12} style={{cursor: 'pointer', opacity: 0.4, transition: 'opacity 0.15s'}} 
                          onClick={(e) => { e.stopPropagation(); deleteTask(task.titolo); }}
                          onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                          onMouseLeave={e => e.currentTarget.style.opacity = '0.4'}
                        />
                      </div>
                    </div>
                    <p style={{
                      fontSize: '0.72rem', 
                      fontWeight: 500, 
                      margin: '6px 0', 
                      color: '#e2e4eb',
                      lineHeight: 1.4,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {task.titolo}
                    </p>
                    {task.descrizione && (
                      <p style={{
                        fontSize: '0.62rem',
                        color: '#5a5e72',
                        margin: '0 0 4px 0',
                        lineHeight: 1.3,
                        display: '-webkit-box',
                        WebkitLineClamp: 1,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}>
                        {task.descrizione}
                      </p>
                    )}
                    <div className="task-footer" onClick={(e) => { e.stopPropagation(); toggleTaskStatus(task); }} style={{
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginTop: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: task.status === 'done' ? 'rgba(63,185,80,0.08)' : 'rgba(210,153,34,0.08)',
                      width: 'fit-content',
                      transition: 'all 0.15s'
                    }}>
                      {task.status === 'done' 
                        ? <CheckCircle2 size={13} color="#3fb950" /> 
                        : task.status === 'blocked'
                        ? <AlertCircle size={13} color="#ff5555" />
                        : <Clock size={13} color="#d29922" />
                      }
                      <span style={{
                        fontSize: '0.6rem', 
                        fontWeight: 600,
                        color: task.status === 'done' ? '#3fb950' : task.status === 'blocked' ? '#ff5555' : '#d29922'
                      }}>
                        {task.status === 'done' ? 'Completato' : task.status === 'blocked' ? 'Bloccato' : 'In Corso'}
                      </span>
                    </div>
                  </div>
                ))}
                {tasks.length === 0 && <p className="empty-hint">Nessun task.</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}