import React, { useEffect, useState, useRef, useCallback } from 'react';

// ==============================================================================
// WelcomeDashboard — Modern Home with Force-Directed Topic Graph + CRUD
// ==============================================================================

/* ----- Domain Color Mapping ----- */
const DOMAIN_COLORS = {
  'Analisi':   { bg: '#00d2ff', label: 'Analisi' },
  'Algebra':   { bg: '#a78bfa', label: 'Algebra' },
  'Numeri':    { bg: '#3fb950', label: 'Numeri' },
  'Topologia': { bg: '#faa03c', label: 'Topologia' },
  'Fisica':    { bg: '#ff5064', label: 'Fisica' },
  'Generale':  { bg: '#9494a5', label: 'Generale' },
};

/* ----- Domain Picker (modern pill UX) ----- */
function DomainPicker({ value, onChange }) {
  return (
    <div className="wg-domain-picker">
      {Object.entries(DOMAIN_COLORS).map(([key, { bg }]) => (
        <button
          key={key}
          type="button"
          className={`wg-domain-pill ${value === key ? 'active' : ''}`}
          style={{
            '--domain-color': bg,
            '--domain-color-15': bg + '26',
            '--domain-color-08': bg + '14',
          }}
          onClick={() => onChange(key)}
        >
          <span className="wg-domain-dot" style={{ background: bg }} />
          {key}
        </button>
      ))}
    </div>
  );
}

/* ----- Parent Selector (styled dropdown) ----- */
function ParentSelector({ value, onChange, allTopics, excludeId }) {
  // Compute available parents (exclude self and descendants to prevent cycles)
  const getDescendantIds = (tid, topics) => {
    const ids = new Set();
    const find = (pid) => {
      for (const t of topics) {
        if (t.id !== pid && t.parent_id === pid) {
          ids.add(t.id);
          find(t.id);
        }
      }
    };
    find(tid);
    return ids;
  };

  const excluded = new Set();
  if (excludeId) {
    excluded.add(excludeId);
    getDescendantIds(excludeId, allTopics || []).forEach(id => excluded.add(id));
  }

  const available = (allTopics || []).filter(t => !excluded.has(t.id));

  return (
    <div className="wg-field">
      <label>Argomento Padre (opzionale)</label>
      <select
        className="wg-parent-select"
        value={value || ''}
        onChange={e => onChange(e.target.value || null)}
      >
        <option value="">— Nessuno —</option>
        {available.map(t => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
      <span className="wg-field-sub">Collega questo argomento come figlio di un altro</span>
    </div>
  );
}

/* ----- Inline Rename / Edit Modal ----- */
function TopicEditModal({ topic, onSave, onCancel, allTopics }) {
  const [name, setName] = useState(topic?.name || '');
  const [description, setDescription] = useState(topic?.description || '');
  const [domain, setDomain] = useState(topic?.domain || 'Generale');
  const [parentId, setParentId] = useState(topic?.parent_id || null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!name.trim()) return setError('Il nome è obbligatorio');
    setSaving(true);
    setError('');
    try {
      const body = {
        topic_id: topic.id,
        name: name.trim(),
        description,
        domain,
        parent_id: parentId
      };
      const r = await fetch('/api/update_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const d = await r.json();
      if (d.success) {
        onSave({ ...topic, name: name.trim(), description, domain, parent_id: parentId });
      } else {
        setError(d.error || 'Errore durante il salvataggio');
      }
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setSaving(false);
    }
  };

  if (!topic) return null;

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Modifica Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <div className="wg-field">
            <label>Nome</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="es. Topologia non archimedea" autoFocus />
          </div>
          <div className="wg-field">
            <label>Descrizione</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Descrizione dell'argomento…" />
          </div>
          <div className="wg-field">
            <label>Dominio</label>
            <DomainPicker value={domain} onChange={setDomain} />
          </div>
          <ParentSelector
            value={parentId}
            onChange={setParentId}
            allTopics={allTopics}
            excludeId={topic.id}
          />
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Salvataggio…' : 'Salva'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Create Topic Modal ----- */
function CreateTopicModal({ onCreated, onCancel, allTopics }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState('Generale');
  const [parentId, setParentId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    if (!name.trim()) return setError('Il nome è obbligatorio');
    const id = name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/(^_|_$)/g, '');
    if (!id) return setError('ID non valido (usa solo lettere, numeri e underscore)');
    setSaving(true);
    setError('');
    try {
      const r = await fetch('/api/create_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name: name.trim(), description, domain, parent_id: parentId })
      });
      const d = await r.json();
      if (d.success) {
        onCreated({
          id,
          name: name.trim(),
          description,
          domain,
          parent_id: parentId,
          manifesto_ref: '',
          modules: []
        });
      } else {
        setError(d.error || 'Errore durante la creazione');
      }
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Nuovo Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <div className="wg-field">
            <label>Nome</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="es. Topologia non archimedea" autoFocus />
          </div>
          <div className="wg-field">
            <label>Descrizione</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Descrizione dell'argomento…" />
          </div>
          <div className="wg-field">
            <label>Dominio</label>
            <DomainPicker value={domain} onChange={setDomain} />
          </div>
          <ParentSelector
            value={parentId}
            onChange={setParentId}
            allTopics={allTopics}
            excludeId={null}
          />
          <div className="wg-field-hint">
            L'ID verrà generato automaticamente dal nome: <code>{name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/(^_|_$)/g, '') || '…'}</code>
          </div>
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-primary" onClick={handleCreate} disabled={saving}>
            {saving ? 'Creazione…' : 'Crea Argomento'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Delete Confirmation ----- */
function DeleteConfirmModal({ topic, onConfirm, onCancel }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async () => {
    setDeleting(true);
    setError('');
    try {
      const r = await fetch('/api/delete_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_id: topic.id })
      });
      const d = await r.json();
      if (d.success) onConfirm(topic.id);
      else setError(d.error || 'Errore durante l\'eliminazione');
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal wg-modal-danger" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Elimina Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <p>Sei sicuro di voler eliminare <strong>"{topic.name}"</strong>?</p>
          <p className="wg-modal-warn">Tutti i moduli e file associati verranno cancellati definitivamente.</p>
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Eliminazione…' : 'Elimina definitivamente'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Force-Directed Graph Component ----- */
function TopicGraph({ topics, selectedTopic, onSelectTopic }) {
  const svgRef = useRef(null);
  const animRef = useRef(null);
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const dims = { w: 540, h: 440 };

  // Build nodes from topics
  useEffect(() => {
    if (!topics.length) return;
    const nodes = topics.map((t, i) => ({
      id: t.id,
      label: t.name,
      domain: t.domain || 'Generale',
      description: t.description,
      count: t.modules?.length || 1,
      x: dims.w / 2 + (Math.random() - 0.5) * 300,
      y: dims.h / 2 + (Math.random() - 0.5) * 200,
      vx: 0, vy: 0,
      radius: 20 + (t.modules?.length || 1) * 6,
    }));
    nodesRef.current = nodes;

    // Build edges from parent-child relationships
    const edges = [];
    for (const t of topics) {
      if (t.parent_id) {
        const exists = topics.find(p => p.id === t.parent_id);
        if (exists) {
          edges.push({ source: t.parent_id, target: t.id });
        }
      }
    }
    edgesRef.current = edges;

    runSimulation(nodes, edges);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [topics]);

  const runSimulation = (nodes, edges) => {
    const springLength = 120;
    const springStrength = 0.006;
    const repulsion = 800;
    const centerForce = 0.01;
    const iterations = 200;
    let iter = 0;

    const step = () => {
      if (iter > iterations) return;
      iter++;
      // Center force
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        a.vx += (dims.w / 2 - a.x) * centerForce;
        a.vy += (dims.h / 2 - a.y) * centerForce;
      }
      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 20);
          const force = repulsion / (dist * dist);
          a.vx += dx / dist * force;
          b.vx -= dx / dist * force;
          a.vy += dy / dist * force;
          b.vy -= dy / dist * force;
        }
      }
      // Spring force along parent-child edges
      for (const edge of edges) {
        const src = nodes.find(n => n.id === edge.source);
        const tgt = nodes.find(n => n.id === edge.target);
        if (!src || !tgt) continue;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (dist - springLength) * springStrength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        src.vx += fx;
        src.vy += fy;
        tgt.vx -= fx;
        tgt.vy -= fy;
      }
      // Apply velocities
      for (const n of nodes) {
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(n.radius + 10, Math.min(dims.w - n.radius - 10, n.x));
        n.y = Math.max(n.radius + 10, Math.min(dims.h - n.radius - 10, n.y));
      }
      forceRender(nodes);
      if (iter <= iterations) animRef.current = requestAnimationFrame(step);
    };
    animRef.current = requestAnimationFrame(step);
  };

  const forceRender = (nodes) => {
    const svg = svgRef.current;
    if (!svg) return;

    // Update edge lines
    const edges = edgesRef.current;
    const lines = svg.querySelectorAll('.topic-edge');
    edges.forEach((edge, i) => {
      const src = nodes.find(n => n.id === edge.source);
      const tgt = nodes.find(n => n.id === edge.target);
      if (src && tgt && lines[i]) {
        lines[i].setAttribute('x1', src.x);
        lines[i].setAttribute('y1', src.y);
        lines[i].setAttribute('x2', tgt.x);
        lines[i].setAttribute('y2', tgt.y);
      }
    });

    // Update arrowheads
    const arrows = svg.querySelectorAll('.topic-edge-arrow');
    edges.forEach((edge, i) => {
      const src = nodes.find(n => n.id === edge.source);
      const tgt = nodes.find(n => n.id === edge.target);
      if (src && tgt && arrows[i]) {
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const arrowSize = 8;
        const tipX = tgt.x - (dx / dist) * (tgt.radius + 4);
        const tipY = tgt.y - (dy / dist) * (tgt.radius + 4);
        const bx = -(dy / dist) * arrowSize * 0.4;
        const by = (dx / dist) * arrowSize * 0.4;
        const points = `${tipX},${tipY} ${tipX - (dx / dist) * arrowSize + bx},${tipY - (dy / dist) * arrowSize + by} ${tipX - (dx / dist) * arrowSize - bx},${tipY - (dy / dist) * arrowSize - by}`;
        arrows[i].setAttribute('points', points);
      }
    });

    const circles = svg.querySelectorAll('.topic-node');
    const labels = svg.querySelectorAll('.topic-label');
    nodes.forEach((n, i) => {
      if (circles[i]) {
        circles[i].setAttribute('cx', n.x);
        circles[i].setAttribute('cy', n.y);
      }
      if (labels[i]) {
        labels[i].setAttribute('x', n.x);
        labels[i].setAttribute('y', n.y + 4);
      }
    });
  };

  const domainColors = {
    'Analisi': '#00d2ff',
    'Algebra': '#a78bfa',
    'Numeri': '#3fb950',
    'Topologia': '#faa03c',
    'Fisica': '#ff5064',
    'Generale': '#9494a5',
  };

  const getDomainColor = (d) => domainColors[d] || '#9494a5';

  const handleNodeClick = (nodeId) => {
    const topic = topics.find(t => t.id === nodeId);
    if (topic) onSelectTopic(topic);
  };

  if (!topics.length) return <div className="wg-empty">Caricamento argomenti…</div>;

  const edges = edgesRef.current;

  return (
    <div className="wg-graph-wrapper">
      <svg ref={svgRef} viewBox={`0 0 ${dims.w} ${dims.h}`} className="wg-svg">
        {/* Edge lines */}
        {edges.map((edge, i) => (
          <g key={`edge-${edge.source}-${edge.target}`}>
            <line
              className="topic-edge"
              x1={0} y1={0} x2={0} y2={0}
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
            <polygon
              className="topic-edge-arrow"
              points="0,0 0,0 0,0"
              fill="rgba(255,255,255,0.2)"
            />
          </g>
        ))}
        {/* Node groups */}
        {nodesRef.current.map((n, i) => (
          <g key={n.id} className="topic-node-group" onClick={() => handleNodeClick(n.id)} style={{ cursor: 'pointer' }}>
            <circle
              className="topic-node"
              cx={n.x} cy={n.y} r={n.radius}
              fill={getDomainColor(n.domain)}
              fillOpacity={selectedTopic?.id === n.id ? '0.35' : '0.15'}
              stroke={getDomainColor(n.domain)}
              strokeWidth={selectedTopic?.id === n.id ? '3' : '1.5'}
              strokeOpacity={selectedTopic?.id === n.id ? '1' : '0.5'}
            />
            <text className="topic-label" x={n.x} y={n.y + 4} textAnchor="middle" dominantBaseline="central"
              fill={selectedTopic?.id === n.id ? getDomainColor(n.domain) : '#fff'}
              fontSize={Math.max(9, Math.min(12, n.radius * 0.45))}
              fontWeight="600"
              pointerEvents="none"
              style={{ userSelect: 'none' }}
            >
              {n.label.length > 12 ? n.label.slice(0, 11) + '…' : n.label}
            </text>
            {selectedTopic?.id === n.id && (
              <circle cx={n.x} cy={n.y} r={n.radius + 6}
                fill="none" stroke={getDomainColor(n.domain)}
                strokeWidth="1.5" strokeDasharray="4 3"
                opacity="0.6"
              >
                <animate attributeName="r" values={`${n.radius + 6};${n.radius + 12};${n.radius + 6}`} dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
        ))}
      </svg>
      <div className="wg-legend">
        {Object.entries(domainColors).map(([domain, color]) => (
          <span key={domain} className="wg-legend-item">
            <span className="wg-legend-dot" style={{ background: color }} />
            {domain}
          </span>
        ))}
        <span className="wg-legend-item" style={{ marginLeft: 'auto', opacity: 0.5, fontSize: 11 }}>
          linee = relazioni padre-figlio
        </span>
      </div>
    </div>
  );
}

/* ----- Topic Detail Panel (with Edit/Delete actions) ----- */
function TopicDetail({ topic, topics, openTab, onEdit, onDelete }) {
  if (!topic) {
    return (
      <div className="wg-detail wg-detail-empty">
        <div className="wg-detail-empty-icon">☝️</div>
        <h4>Seleziona un Nodo</h4>
        <p>Clicca su un argomento nel grafo per visualizzarne i dettagli e i moduli correlati.</p>
      </div>
    );
  }

  const domainColors = {
    'Analisi': '#00d2ff', 'Algebra': '#a78bfa', 'Numeri': '#3fb950',
    'Topologia': '#faa03c', 'Fisica': '#ff5064', 'Generale': '#9494a5',
  };
  const color = domainColors[topic.domain] || '#9494a5';
  const temaModules = topic.modules || [];

  // Find parent topic
  const parentTopic = topic.parent_id ? (topics || []).find(t => t.id === topic.parent_id) : null;

  // Find child topics
  const childTopics = (topics || []).filter(t => t.parent_id === topic.id);

  return (
    <div className="wg-detail">
      <div className="wg-detail-head">
        <span className="wg-detail-domain" style={{ background: `${color}18`, color, border: `1px solid ${color}44` }}>
          {topic.domain || 'Generale'}
        </span>
        <span className="wg-detail-badge">{temaModules.length} moduli</span>
      </div>
      <h3 className="wg-detail-title">{topic.name}</h3>
      <p className="wg-detail-desc">{topic.description}</p>

      {/* Parent-child relationships */}
      {parentTopic && (
        <div className="wg-detail-rel wg-detail-rel-parent">
          <span className="wg-detail-rel-label">Argomento Padre</span>
          <span className="wg-detail-rel-value">{parentTopic.name}</span>
        </div>
      )}
      {childTopics.length > 0 && (
        <div className="wg-detail-rel wg-detail-rel-children">
          <span className="wg-detail-rel-label">Argomenti Figli ({childTopics.length})</span>
          <div className="wg-detail-rel-list">
            {childTopics.map(ct => (
              <span key={ct.id} className="wg-detail-rel-tag">{ct.name}</span>
            ))}
          </div>
        </div>
      )}

      <div className="wg-detail-actions">
        <button className="wg-btn-sm wg-btn-sm-edit" onClick={() => onEdit(topic)} title="Modifica argomento">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Modifica
        </button>
        <button className="wg-btn-sm wg-btn-sm-delete" onClick={() => onDelete(topic)} title="Elimina argomento">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          Elimina
        </button>
      </div>

      {temaModules.length > 0 && (
        <div className="wg-detail-modules">
          <div className="wg-detail-subtitle">Moduli Associati</div>
          {temaModules.map(mod => {
            const totalFiles = (mod.teoria?.length || 0) + (mod.test?.length || 0) + (mod.viz?.length || 0) + (mod.docs?.length || 0) + (mod.whitepapers?.length || 0);
            return (
              <div key={mod.number} className="wg-detail-module" onClick={() => openTab(mod, 'module')}>
                <span className="wg-detail-mod-num" style={{ background: `${color}15`, color, border: `1px solid ${color}33` }}>
                  MOD {mod.number}
                </span>
                <div className="wg-detail-mod-info">
                  <span className="wg-detail-mod-name">{mod.name}</span>
                  <span className="wg-detail-mod-files">{totalFiles} file</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ----- Quick Feature Card ----- */
function QuickFeature({ icon, title, desc, color }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(14,16,22,0.9), rgba(20,22,28,0.9))',
      border: `1px solid ${color}22`,
      borderRadius: '12px',
      padding: '20px',
      transition: 'all 0.2s',
      cursor: 'default'
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = `${color}44`; e.currentTarget.style.transform = 'translateY(-2px)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = `${color}22`; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${color}14`, border: `1px solid ${color}22`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.3rem', flexShrink: 0
        }}>
          {icon}
        </div>
        <div>
          <h4 style={{ margin: '0 0 6px 0', fontSize: '0.82rem', fontWeight: 600, color: color }}>
            {title}
          </h4>
          <p style={{ margin: 0, fontSize: '0.68rem', color: '#5a5e72', lineHeight: 1.6 }}>
            {desc}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ----- Quick Link button style ----- */
const quickLinkStyle = (color) => ({
  padding: '10px 22px',
  borderRadius: '10px',
  fontSize: '0.72rem',
  fontWeight: 600,
  cursor: 'pointer',
  border: `1px solid ${color}33`,
  background: `${color}0d`,
  color: color,
  fontFamily: 'inherit',
  transition: 'all 0.15s',
  display: 'flex',
  alignItems: 'center',
  gap: '8px'
});

/* ----- WelcomeScreen Export ----- */
export default function WelcomeDashboard({ modules, openTab }) {
  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);

  // Modal states
  const [showCreate, setShowCreate] = useState(false);
  const [editTopic, setEditTopic] = useState(null);
  const [deleteTopic, setDeleteTopic] = useState(null);

  const fetchTopics = useCallback(() => {
    fetch('/api/topics')
      .then(r => r.json())
      .then(d => { if (d.topics) setTopics(d.topics); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchTopics();
  }, [fetchTopics]);

  const handleCreated = (newTopic) => {
    setTopics(prev => [...prev, newTopic]);
    setShowCreate(false);
  };

  const handleEdited = (updatedTopic) => {
    setTopics(prev => prev.map(t => t.id === updatedTopic.id ? { ...t, ...updatedTopic } : t));
    setSelectedTopic(prev => prev?.id === updatedTopic.id ? { ...prev, ...updatedTopic } : prev);
    setEditTopic(null);
  };

  const handleDeleted = (topicId) => {
    // Also orphan children
    setTopics(prev => prev.map(t => t.parent_id === topicId ? { ...t, parent_id: null } : t).filter(t => t.id !== topicId));
    if (selectedTopic?.id === topicId) setSelectedTopic(null);
    setDeleteTopic(null);
  };

  const countModules = topics.reduce((acc, t) => acc + (t.modules?.length || 0), 0);
  const countTeoria = topics.reduce((acc, t) => {
    for (const m of (t.modules || [])) acc += (m.teoria?.length || 0);
    return acc;
  }, 0);
  const countTest = topics.reduce((acc, t) => {
    for (const m of (t.modules || [])) acc += (m.test?.length || 0);
    return acc;
  }, 0);
  const countViz = topics.reduce((acc, t) => {
    for (const m of (t.modules || [])) acc += (m.viz?.length || 0) + (m.docs?.length || 0) + (m.whitepapers?.length || 0);
    return acc;
  }, 0);

  return (
    <div className="wg-container">
      {/* Hero */}
      <div className="wg-hero">
        <div className="wg-hero-badge">Σ SIGMA STUDIO v6.2</div>
        <h1 className="wg-hero-title">
          Sigma <span className="wg-hero-accent">Research</span> Studio
        </h1>
        <p className="wg-hero-sub">
          Piattaforma modulare per la ricerca assistita dall'AI — organizza argomenti, scrivi teoria, esegui test, visualizza dati e collabora con modelli linguistici avanzati.
        </p>
      </div>

      {/* Metrics */}
      <div className="wg-metrics">
        <div className="wg-metric">
          <span className="wg-metric-value">{topics.length}</span>
          <span className="wg-metric-label">Argomenti</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value">{countModules}</span>
          <span className="wg-metric-label">Moduli</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value">{countTeoria}</span>
          <span className="wg-metric-label">Documenti Teorici</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value">{countTest}</span>
          <span className="wg-metric-label">Test Computazionali</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value">{countViz}</span>
          <span className="wg-metric-label">Viz & Docs</span>
        </div>
      </div>

      {/* Features Grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '16px', marginBottom: '24px'
      }}>
        <QuickFeature
          icon="🧬"
          title="Argomenti & Moduli"
          desc="Organizza la tua ricerca in argomenti strutturati con moduli numerati. Ogni modulo contiene teoria, test, visualizzazioni e documenti."
          color="#bc8cff"
        />
        <QuickFeature
          icon="🗺️"
          title="Roadmap di Ricerca"
          desc="Pianifica e traccia le attività con task collegati ai moduli. Filtra per stato, priorità e monitora il progresso globale."
          color="#00d2ff"
        />
        <QuickFeature
          icon="🤖"
          title="AI Studio Chat"
          desc="Collabora con modelli linguistici locali (Ollama) o API cloud. Allega file dal progetto o dal PC per un contesto completo."
          color="#3fb950"
        />
        <QuickFeature
          icon="📜"
          title="Modelfile AI"
          desc="Crea modelli AI specializzati con system prompt permanenti. Personalizza parametri e crea un modello su misura per ogni dominio."
          color="#d29922"
        />
        <QuickFeature
          icon="📊"
          title="Mappa Interattiva"
          desc="Visualizza le relazioni tra argomenti con un grafo force-directed. Naviga, filtra e accedi rapidamente ai file di ogni modulo."
          color="#ff6b6b"
        />
        <QuickFeature
          icon="✏️"
          title="Editor Markdown + LaTeX"
          desc="Scrivi documenti scientifici con supporto KaTeX per formule matematiche e diagrammi Mermaid. Anteprima in tempo reale e stampa PDF."
          color="#a78bfa"
        />
      </div>

      {/* Quick Links */}
      <div style={{
        display: 'flex', gap: '12px', flexWrap: 'wrap',
        justifyContent: 'center', marginBottom: '40px'
      }}>
        <button onClick={() => openTab({ name: 'Argomenti' }, 'knowledge')} style={quickLinkStyle('#bc8cff')}>
          🧬 Esplora Argomenti
        </button>
        <button onClick={() => openTab({ name: 'Research Roadmap' }, 'roadmap')} style={quickLinkStyle('#00d2ff')}>
          🗺️ Vai alla Roadmap
        </button>
        <button onClick={() => openTab({ name: 'Manifesti' }, 'whitepapers_lib')} style={quickLinkStyle('#d29922')}>
          📜 Gestisci Modelfile
        </button>
      </div>
    </div>
  );
}