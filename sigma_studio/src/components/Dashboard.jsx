import React, { useState, useMemo } from 'react';
import { 
  PlusCircle, CheckCircle2, Clock, ChevronRight, Trash2, 
  AlertCircle
} from 'lucide-react';

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