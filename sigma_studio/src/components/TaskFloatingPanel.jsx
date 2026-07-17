import React, { useState, useMemo, useEffect, useRef } from 'react';
import { 
  Plus, Edit, PlusCircle, CheckCircle2, Clock, ChevronRight, Trash2, 
  AlertCircle, Filter, X, FileText, BookOpen, Terminal, PieChart, GripVertical
} from 'lucide-react';

const MIN_WIDTH = 480;
const MIN_HEIGHT = 400;

// ==============================================================================
// TaskFloatingPanel — Draggable & resizable floating task board
// Inspired by ChatFloatingPanel with glassmorphism Sigma Studio style
// ==============================================================================

export default function TaskFloatingPanel({ tasks, onAdd, onEdit, onDelete, onToggleStatus, onOpenFile, onClearAll, onClose }) {
  const [panelPos, setPanelPos] = useState({ x: undefined, y: undefined });
  const [panelSize, setPanelSize] = useState({ width: 600, height: 500 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [resizing, setResizing] = useState(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0 });
  const resizeSizeStart = useRef({ width: 600, height: 500 });
  const resizePosStart = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const [filterStatus, setFilterStatus] = useState('all');
  const [filterModule, setFilterModule] = useState('all');

  // Drag logic
  useEffect(() => {
    if (!isDragging) return;
    const hMM = (e) => {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        setPanelPos(prev => ({
          x: (prev.x !== undefined ? prev.x : (window.innerWidth - panelSize.width) / 2) + dx,
          y: (prev.y !== undefined ? prev.y : 60) + dy
        }));
        setDragStart({ x: e.clientX, y: e.clientY });
      }
    };
    const hMU = () => setIsDragging(false);
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [isDragging, dragStart, panelSize]);

  // Resize logic
  useEffect(() => {
    if (!resizing) return;
    const hMM = (e) => {
      const dx = e.clientX - resizeStart.x;
      const dy = e.clientY - resizeStart.y;
      
      setPanelPos(prev => {
        let newX = prev.x;
        let newY = prev.y;
        if (resizing.includes('w')) {
          const diff = resizeSizeStart.current.width - dx;
          if (diff >= MIN_WIDTH) newX = (resizePosStart.current.x || 0) + dx;
        }
        if (resizing.includes('n')) {
          const diff = resizeSizeStart.current.height - dy;
          if (diff >= MIN_HEIGHT) newY = (resizePosStart.current.y || 0) + dy;
        }
        return { x: newX !== undefined ? newX : prev.x, y: newY !== undefined ? newY : prev.y };
      });
      
      setPanelSize(() => ({
        width: resizing.includes('e') ? Math.max(MIN_WIDTH, resizeSizeStart.current.width + dx) :
                resizing.includes('w') ? Math.max(MIN_WIDTH, resizeSizeStart.current.width - dx) : resizeSizeStart.current.width,
        height: resizing.includes('s') ? Math.max(MIN_HEIGHT, resizeSizeStart.current.height + dy) :
                 resizing.includes('n') ? Math.max(MIN_HEIGHT, resizeSizeStart.current.height - dy) : resizeSizeStart.current.height
      }));
    };
    const hMU = () => setResizing(null);
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [resizing, resizeStart]);

  const startDrag = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleResizeStart = (direction, e) => {
    e.preventDefault();
    e.stopPropagation();
    setResizing(direction);
    setResizeStart({ x: e.clientX, y: e.clientY });
    resizeSizeStart.current = { width: panelSize.width, height: panelSize.height };
    resizePosStart.current = { x: panelPos.x, y: panelPos.y };
  };

  const resizeHandles = [
    { dir: 'n', className: 'task-resize-n', cursor: 'n-resize' },
    { dir: 's', className: 'task-resize-s', cursor: 's-resize' },
    { dir: 'e', className: 'task-resize-e', cursor: 'e-resize' },
    { dir: 'w', className: 'task-resize-w', cursor: 'w-resize' },
    { dir: 'ne', className: 'task-resize-ne', cursor: 'ne-resize' },
    { dir: 'nw', className: 'task-resize-nw', cursor: 'nw-resize' },
    { dir: 'se', className: 'task-resize-se', cursor: 'se-resize' },
    { dir: 'sw', className: 'task-resize-sw', cursor: 'sw-resize' },
  ];

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

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x)) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y)) ? panelPos.y : undefined;

  return (
    <div
      ref={panelRef}
      className={`task-floating-panel ${resizing ? 'is-resizing' : ''}`}
      style={{
        position: 'fixed',
        zIndex: 9999,
        ...(safeX !== undefined ? { left: safeX, right: 'auto' } : { left: '50%', marginLeft: -panelSize.width / 2 }),
        ...(safeY !== undefined ? { bottom: 'auto', top: safeY } : { top: 60 }),
        width: panelSize.width,
        height: panelSize.height,
        maxHeight: 'calc(100vh - 120px)',
        background: 'rgba(14, 14, 24, 0.97)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '16px',
        boxShadow: '0 32px 64px -16px rgba(0,0,0,0.6)',
        backdropFilter: 'blur(18px) saturate(180%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* Resize handles */}
      {resizeHandles.map(rh => (
        <div key={rh.dir} style={{
          position: 'absolute',
          zIndex: 100,
          ...(rh.dir === 'n' ? { top: -2, left: 0, right: 0, height: 4, cursor: 'n-resize' } : {}),
          ...(rh.dir === 's' ? { bottom: -2, left: 0, right: 0, height: 4, cursor: 's-resize' } : {}),
          ...(rh.dir === 'e' ? { right: -2, top: 0, bottom: 0, width: 4, cursor: 'e-resize' } : {}),
          ...(rh.dir === 'w' ? { left: -2, top: 0, bottom: 0, width: 4, cursor: 'w-resize' } : {}),
          ...(rh.dir === 'ne' ? { top: -2, right: -2, width: 8, height: 8, cursor: 'ne-resize' } : {}),
          ...(rh.dir === 'nw' ? { top: -2, left: -2, width: 8, height: 8, cursor: 'nw-resize' } : {}),
          ...(rh.dir === 'se' ? { bottom: -2, right: -2, width: 8, height: 8, cursor: 'se-resize' } : {}),
          ...(rh.dir === 'sw' ? { bottom: -2, left: -2, width: 8, height: 8, cursor: 'sw-resize' } : {}),
        }}
          onMouseDown={(e) => handleResizeStart(rh.dir, e)}
        />
      ))}

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(0,0,0,0.2)', userSelect: 'none', flexShrink: 0
      }}>
        <div onMouseDown={startDrag} style={{ cursor: 'grab', display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <GripVertical size={14} color="#5a5a6a" />
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#00d2ff' }}>
            🗺️ Task Roadmap
          </span>
          <span style={{ fontSize: '0.6rem', color: '#5a5a6a', fontWeight: 400 }}>
            {stats.total} tasks
          </span>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {tasks.length > 1 && (
            <button onClick={() => { if (confirm(`Eliminare TUTTI i ${tasks.length} task?`)) onClearAll?.(); }}
              style={{
                padding: '4px 10px', borderRadius: '6px', fontSize: '0.6rem', fontWeight: 600,
                border: '1px solid rgba(255,85,85,0.3)', background: 'rgba(255,85,85,0.1)',
                color: '#ff5555', cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s'
              }}>
              <Trash2 size={12} /> Cancella
            </button>
          )}
          <button onClick={onAdd} style={{
            padding: '5px 12px', borderRadius: '6px', fontSize: '0.65rem', fontWeight: 600,
            border: '1px solid rgba(0,210,255,0.3)', background: 'rgba(0,210,255,0.1)',
            color: '#00d2ff', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '6px',
            transition: 'all 0.15s'
          }}>
            <Plus size={14} /> Nuovo Task
          </button>
          <button onClick={onClose} style={{
            padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent',
            color: '#5a5a6a', cursor: 'pointer', display: 'flex', alignItems: 'center'
          }}>
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 16px', flexShrink: 0
      }}>
        {[
          { value: stats.total, label: 'Totale', color: '#e2e4eb' },
          { value: stats.done, label: 'Completati', color: '#3fb950', bar: stats.progress, barColor: '#3fb950' },
          { value: stats.inCorso, label: 'In Corso', color: '#00d2ff' },
          { value: stats.blocked, label: 'Bloccati', color: stats.blocked > 0 ? '#ff5555' : '#5a5a6a' },
        ].map((s, i) => (
          <div key={i} style={{
            flex: 1, padding: '10px 12px', borderRadius: '10px',
            background: '#11131b', border: '1px solid #1e2030',
            display: 'flex', flexDirection: 'column', gap: '2px'
          }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: '0.55rem', color: '#5a5a6a', textTransform: 'uppercase', letterSpacing: '1px' }}>{s.label}</div>
            {s.bar !== undefined && (
              <div style={{ height: '3px', borderRadius: '2px', background: '#1e2030', overflow: 'hidden', marginTop: '4px' }}>
                <div style={{ height: '100%', borderRadius: '2px', background: s.barColor, width: s.bar + '%', transition: 'width 0.5s ease' }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex', gap: '8px', padding: '0 16px 10px', flexShrink: 0, alignItems: 'center'
      }}>
        <span style={{ fontSize: '0.55rem', color: '#5a5a6a' }}>Filtri:</span>
        <div style={{ display: 'flex', gap: '2px' }}>
          {[
            { key: 'all', label: 'Tutti' },
            { key: 'in_corso', label: 'In Corso' },
            { key: 'done', label: 'Completati' },
            { key: 'blocked', label: 'Bloccati' },
          ].map(f => (
            <button key={f.key} onClick={() => setFilterStatus(f.key)} style={{
              padding: '4px 10px', borderRadius: '6px', fontSize: '0.55rem',
              border: `1px solid ${filterStatus === f.key ? 'rgba(0,210,255,0.3)' : '#1e2030'}`,
              background: filterStatus === f.key ? 'rgba(0,210,255,0.08)' : 'transparent',
              color: filterStatus === f.key ? '#00d2ff' : '#5a5a6a',
              cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.12s'
            }}>
              {f.label}
            </button>
          ))}
        </div>
        <select value={filterModule} onChange={e => setFilterModule(e.target.value)} style={{
          padding: '4px 8px', borderRadius: '6px', fontSize: '0.55rem',
          border: '1px solid #1e2030', background: '#11131b', color: '#8b8fa3',
          fontFamily: 'inherit', cursor: 'pointer', outline: 'none'
        }}>
          <option value="all">Tutti i moduli</option>
          {modules.filter(m => m !== 'all').map(m => (
            <option key={m} value={m}>Modulo {m}</option>
          ))}
        </select>
        {(filterStatus !== 'all' || filterModule !== 'all') && (
          <button onClick={() => { setFilterStatus('all'); setFilterModule('all'); }} style={{
            padding: '4px 10px', borderRadius: '6px', fontSize: '0.55rem',
            border: '1px solid #1e2030', background: 'transparent', color: '#ff5555',
            cursor: 'pointer', fontFamily: 'inherit'
          }}>
            <X size={12} /> Reset
          </button>
        )}
      </div>

      {/* Task list */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px'
      }}>
        {filteredTasks.length === 0 && (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: '16px', color: '#5a5a6a', padding: '40px'
          }}>
            <div style={{
              width: '56px', height: '56px', borderRadius: '14px',
              background: 'linear-gradient(135deg, rgba(0,210,255,0.1), rgba(188,140,255,0.08))',
              border: '1px solid rgba(0,210,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem'
            }}>
              📋
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e2e4eb', marginBottom: '4px' }}>
                Nessun task ancora
              </div>
              <div style={{ fontSize: '0.65rem', color: '#5a5a6a', lineHeight: 1.5 }}>
                Crea il tuo primo task per pianificare e tracciare<br />le attività di ricerca della roadmap.
              </div>
            </div>
          </div>
        )}
        {filteredTasks.map((task, i) => {
          const prio = priorityColors[task.priorita] || priorityColors.media;
          return (
            <div key={task.id || i} onClick={() => onEdit(task)} style={{
              background: '#11131b', border: '1px solid #1e2030', borderRadius: '10px',
              padding: '14px 16px', transition: 'all 0.15s', cursor: 'pointer',
              ...(task.status === 'done' ? { opacity: 0.7 } : {}),
              ...(task.status === 'blocked' ? { borderLeft: '3px solid #ff5555' } : {}),
              ...(task.status === 'done' ? { borderLeft: '3px solid #3fb950' } : {}),
              ...(task.status === 'in_corso' ? { borderLeft: '3px solid #00d2ff' } : {})
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <span style={{
                  fontSize: '0.5rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px',
                  background: 'rgba(0,210,255,0.1)', color: '#00d2ff', letterSpacing: '0.5px'
                }}>
                  MOD {task.moduli?.[0] || '??'}
                </span>
                <span style={{
                  fontSize: '0.5rem', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
                  background: prio.bg, color: prio.color
                }}>
                  {prio.label}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e4eb', marginBottom: '4px', lineHeight: 1.3 }}>
                {task.titolo}
              </div>
              {task.descrizione && (
                <div style={{
                  fontSize: '0.62rem', color: '#5a5a6a', marginBottom: '6px',
                  lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden'
                }}>
                  {task.descrizione}
                </div>
              )}

              {/* Reference files */}
              {task.files && task.files.length > 0 && (
                <div style={{
                  display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '6px', paddingTop: '6px',
                  borderTop: '1px solid rgba(255,255,255,0.03)'
                }}>
                  {task.files.map((f, fi) => (
                    <span key={fi} onClick={(e) => { e.stopPropagation(); onOpenFile && onOpenFile(f.path); }}
                      title={f.path} style={{
                        display: 'flex', alignItems: 'center', gap: '3px', padding: '2px 6px',
                        borderRadius: '4px', fontSize: '0.5rem', cursor: 'pointer',
                        background: 'rgba(255,255,255,0.03)', color: '#5a5a6a',
                        border: '1px solid transparent', transition: 'all 0.12s'
                      }}>
                      {getFileIcon(f.type)} {f.filename}
                    </span>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6rem', color: '#5a5a6a' }}>
                  {statusIcons[task.status]} {statusLabels[task.status]}
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {task.status !== 'done' && (
                    <button onClick={(e) => { e.stopPropagation(); onToggleStatus(task); }} style={{
                      padding: '4px 8px', borderRadius: '4px', fontSize: '0.55rem',
                      border: '1px solid #1e2030', background: 'transparent', color: '#3fb950',
                      cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '4px'
                    }}>
                      <CheckCircle2 size={12} /> Completa
                    </button>
                  )}
                  {task.status === 'done' && (
                    <button onClick={(e) => { e.stopPropagation(); onToggleStatus(task); }} style={{
                      padding: '4px 8px', borderRadius: '4px', fontSize: '0.55rem',
                      border: '1px solid #1e2030', background: 'transparent', color: '#8b8fa3',
                      cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '4px'
                    }}>
                      <Clock size={12} /> Riapri
                    </button>
                  )}
                  <button onClick={(e) => { e.stopPropagation(); onDelete(task); }} style={{
                    padding: '4px 8px', borderRadius: '4px', fontSize: '0.55rem',
                    border: '1px solid #1e2030', background: 'transparent', color: '#ff5555',
                    cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: '4px'
                  }}>
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