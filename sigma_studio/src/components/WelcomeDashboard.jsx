import React, { useEffect, useState, useRef, useCallback } from 'react';
import { 
  FolderTree, MessageSquare, Edit3, Share2, Palette, 
  FlaskConical, Cpu, Home as HomeIcon, Scroll, Microscope, ArrowRight 
} from 'lucide-react';

const PRIMI_PASSI_CARDS = [
  {
    step: '01',
    title: 'Organizza Argomenti & Moduli',
    subtitle: 'Crea domini e moduli in data/ per raggruppare Teoria, Script Python, Visualizzazioni e Whitepaper.',
    icon: FolderTree,
    color: '#00d2ff',
    actionText: 'Mappa Argomenti',
    onClick: (openTab) => openTab({ name: 'Argomenti' }, 'knowledge')
  },
  {
    step: '02',
    title: 'AI Chat & Swarm Multi-Agente',
    subtitle: 'Collabora con modelli LLM locali (Ollama) o Cloud e delega compiti a uno swarm di agenti specializzati.',
    icon: MessageSquare,
    color: '#7c5bf0',
    actionText: 'AI Chat Studio',
    onClick: (openTab) => openTab({ name: 'AI Chat Workspace' }, 'chat')
  },
  {
    step: '03',
    title: 'Editor Markdown & KaTeX',
    subtitle: 'Scrivi documenti scientifici con formule LaTeX in tempo reale e diagrammi di flusso Mermaid esportabili.',
    icon: Edit3,
    color: '#3fb950',
    actionText: 'Apri Editor',
    onClick: (openTab) => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')
  },
  {
    step: '04',
    title: 'Mappa Interattiva Knowledge',
    subtitle: 'Esplora la rete gerarchica dei nodi di conoscenza con navigazione visiva e gestione argomenti.',
    icon: Share2,
    color: '#d29922',
    actionText: 'Knowledge Graph',
    onClick: (openTab) => openTab({ name: 'Argomenti' }, 'knowledge')
  },
  {
    step: '05',
    title: 'Creative Studio & Asset 8K/3D',
    subtitle: 'Usa i motori MCP Grafici per generare immagini 8K, render 3D e visualizzare lightbox ad alta risoluzione.',
    icon: Palette,
    color: '#ff5064',
    actionText: 'Creative Studio',
    onClick: (openTab) => openTab({ name: '🎨 Creative Studio' }, 'creative_studio')
  },
  {
    step: '06',
    title: 'Training Lab & SLM Forge',
    subtitle: 'Esegui il fine-tuning con Unsloth QLoRA, avvia l\'Autopilota o valuta il tuo modello su 11 benchmark.',
    icon: FlaskConical,
    color: '#d29922',
    actionText: 'Training Lab',
    onClick: (openTab) => openTab({ name: 'Training Lab' }, 'training_lab')
  },
  {
    step: '07',
    title: 'Hardware Lab & GPU Monitor',
    subtitle: 'Controlla il consumo VRAM delle GPU NVIDIA, gestisci il demone Ollama ed ottimizzi le risorse di calcolo.',
    icon: Cpu,
    color: '#00d2ff',
    actionText: 'Hardware Lab',
    onClick: (openTab) => openTab({ name: '⚡ Hardware & GPU Monitor' }, 'hardware_lab')
  },
  {
    step: '08',
    title: 'Domotica IoT & Home Assistant',
    subtitle: 'Controlla dispositivi smart, luci, climatizzatori ed attiva scene domotiche via comandi vocali/AI.',
    icon: HomeIcon,
    color: '#a78bfa',
    actionText: 'Pannello Domotica',
    onClick: (openTab) => openTab({ name: '🏠 Domotica & Home Assistant' }, 'domotica')
  },
  {
    step: '09',
    title: 'Modelfile & Manifesti AI',
    subtitle: 'Personalizza system prompt permanenti, parametri di generazione e registra manifesti di condotta.',
    icon: Scroll,
    color: '#3fb950',
    actionText: 'Manifesti AI',
    onClick: (openTab) => openTab({ name: 'Manifesti' }, 'whitepapers_lib')
  },
  {
    step: '10',
    title: 'Research Lab & Task Pipeline',
    subtitle: 'Pianifica task, monitora le attività collegate ai moduli ed esegui pipeline scientifiche autonome.',
    icon: Microscope,
    color: '#7c5bf0',
    actionText: 'Research Lab',
    onClick: (openTab) => openTab({ name: 'Research Lab' }, 'research_lab')
  }
];

// ==============================================================================
// WelcomeDashboard — Modern Home with Force-Directed Topic Graph + CRUD
// ==============================================================================

/* ----- 5 Core Domain Color Mapping ----- */
const DOMAIN_COLORS = {
  'Analisi':     { bg: '#00d2ff', label: 'Analisi' },
  'Algebra':     { bg: '#a78bfa', label: 'Algebra' },
  'Fisica':      { bg: '#ff5064', label: 'Fisica' },
  'Informatica': { bg: '#3fb950', label: 'Informatica' },
  'Generale':    { bg: '#faa03c', label: 'Generale' },
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
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const animRef = useRef(null);
  const dims = { w: 540, h: 440 };

  const domainColors = {
    'Analisi': '#00d2ff', 'Algebra': '#a78bfa', 'Fisica': '#ff5064',
    'Informatica': '#3fb950', 'Generale': '#faa03c',
  };
  const getDomainColor = (d) => domainColors[d] || '#9494a5';

  useEffect(() => {
    if (!topics || !topics.length) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Build graph nodes
    const initialNodes = topics.map((t, i) => {
      const angle = (i / topics.length) * 2 * Math.PI;
      const r = 120;
      return {
        id: t.id,
        label: t.name || t.id,
        domain: t.domain || 'Generale',
        description: t.description || '',
        count: t.modules?.length || 1,
        x: dims.w / 2 + Math.cos(angle) * r,
        y: dims.h / 2 + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
        radius: 24 + Math.min(16, (t.children?.length || 0) * 4),
      };
    });

    const initialEdges = [];
    for (const t of topics) {
      if (t.parent_id) {
        const exists = topics.find(p => p.id === t.parent_id);
        if (exists) {
          initialEdges.push({ source: t.parent_id, target: t.id });
        }
      }
    }

    setNodes(initialNodes);
    setEdges(initialEdges);

    let currentNodes = initialNodes.map(n => ({ ...n }));
    let iter = 0;
    const maxIter = 100;

    const tick = () => {
      if (iter >= maxIter) return;
      iter++;

      const centerForce = 0.012;
      const repulsion = 1200;
      const springLength = 100;
      const springStrength = 0.008;

      for (let a of currentNodes) {
        a.vx += (dims.w / 2 - a.x) * centerForce;
        a.vy += (dims.h / 2 - a.y) * centerForce;
      }

      for (let i = 0; i < currentNodes.length; i++) {
        const a = currentNodes[i];
        for (let j = i + 1; j < currentNodes.length; j++) {
          const b = currentNodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 20);
          const force = repulsion / (dist * dist);
          a.vx += (dx / dist) * force;
          b.vx -= (dx / dist) * force;
          a.vy += (dy / dist) * force;
          b.vy -= (dy / dist) * force;
        }
      }

      for (let edge of initialEdges) {
        const src = currentNodes.find(n => n.id === edge.source);
        const tgt = currentNodes.find(n => n.id === edge.target);
        if (src && tgt) {
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
      }

      for (let n of currentNodes) {
        n.vx *= 0.82;
        n.vy *= 0.82;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(n.radius + 15, Math.min(dims.w - n.radius - 15, n.x));
        n.y = Math.max(n.radius + 15, Math.min(dims.h - n.radius - 15, n.y));
      }

      setNodes([...currentNodes]);
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [topics]);

  if (!topics || !topics.length) {
    return <div className="wg-empty" style={{ padding: '40px', textAlign: 'center', color: '#8b8fa3' }}>Caricamento argomenti…</div>;
  }

  return (
    <div className="wg-graph-wrapper">
      <svg ref={svgRef} viewBox={`0 0 ${dims.w} ${dims.h}`} className="wg-svg">
        {/* Edge lines */}
        {edges.map((edge, i) => {
          const src = nodes.find(n => n.id === edge.source);
          const tgt = nodes.find(n => n.id === edge.target);
          if (!src || !tgt) return null;
          return (
            <line
              key={`edge-${edge.source}-${edge.target}`}
              className="topic-edge"
              x1={src.x} y1={src.y}
              x2={tgt.x} y2={tgt.y}
              stroke="rgba(0, 210, 255, 0.3)"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
          );
        })}

        {/* Node groups */}
        {nodes.map((n) => {
          const isSelected = selectedTopic?.id === n.id;
          const color = getDomainColor(n.domain);
          return (
            <g
              key={n.id}
              className="topic-node-group"
              onClick={() => {
                const topic = topics.find(t => t.id === n.id);
                if (topic) onSelectTopic(topic);
              }}
              style={{ cursor: 'pointer' }}
            >
              <circle
                className="topic-node"
                cx={n.x}
                cy={n.y}
                r={n.radius}
                fill={color}
                fillOpacity={isSelected ? 0.35 : 0.18}
                stroke={color}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeOpacity={isSelected ? 1 : 0.6}
              />
              <text
                className="topic-label"
                x={n.x}
                y={n.y + 4}
                textAnchor="middle"
                dominantBaseline="central"
                fill={isSelected ? '#fff' : '#e2e8f0'}
                fontSize={Math.max(9, Math.min(12, n.radius * 0.42))}
                fontWeight={isSelected ? '700' : '600'}
                pointerEvents="none"
                style={{ userSelect: 'none' }}
              >
                {n.label.length > 14 ? n.label.slice(0, 13) + '…' : n.label}
              </text>
              {isSelected && (
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.radius + 6}
                  fill="none"
                  stroke={color}
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                  opacity="0.6"
                >
                  <animate attributeName="r" values={`${n.radius + 6};${n.radius + 12};${n.radius + 6}`} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          );
        })}
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
    'Analisi': '#00d2ff', 'Algebra': '#a78bfa', 'Fisica': '#ff5064',
    'Informatica': '#3fb950', 'Generale': '#faa03c',
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

  // Categorize files by extension across modules prop and topics API
  const rootTopics = topics.filter(t => !t.parent_id);
  const countRootTopics = rootTopics.length > 0 ? rootTopics.length : 5;
  const countModules = modules?.length > 0 ? modules.length : (topics.length > 0 ? topics.length : 5);

  const allFilePaths = new Set();

  // Collect files from modules prop
  (modules || []).forEach(m => {
    ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
      if (Array.isArray(m[cat])) {
        m[cat].forEach(f => {
          const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
          if (pathStr) allFilePaths.add(pathStr);
        });
      }
    });
  });

  // Collect files from topics API
  (topics || []).forEach(t => {
    if (Array.isArray(t.files)) {
      t.files.forEach(f => {
        const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
        if (pathStr) allFilePaths.add(pathStr);
      });
    }
    ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
      if (Array.isArray(t[cat])) {
        t[cat].forEach(f => {
          const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
          if (pathStr) allFilePaths.add(pathStr);
        });
      }
    });
  });

  let countDocs = 0;
  let countScripts = 0;
  let countVizMedia = 0;

  allFilePaths.forEach(pathStr => {
    const lower = pathStr.toLowerCase();
    if (lower.endsWith('.md') || lower.endsWith('.txt') || lower.endsWith('.pdf') || lower.endsWith('.doc') || lower.endsWith('.docx')) {
      countDocs++;
    } else if (lower.endsWith('.py') || lower.endsWith('.ipynb') || lower.endsWith('.js') || lower.endsWith('.ts') || lower.endsWith('.sh') || lower.endsWith('.bat')) {
      countScripts++;
    } else {
      countVizMedia++;
    }
  });

  return (
    <div className="wg-container">
      {/* Hero Banner with Generated Visual Backdrop */}
      <div style={{
        position: 'relative',
        borderRadius: '20px',
        overflow: 'hidden',
        padding: '48px 36px',
        marginBottom: '32px',
        border: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 16px 48px rgba(0,0,0,0.5), 0 0 32px rgba(0, 210, 255, 0.1)',
        backgroundImage: 'linear-gradient(to right, rgba(14, 16, 22, 0.94) 30%, rgba(14, 16, 22, 0.75) 100%), url("/images/hero_banner.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}>
        <div style={{ position: 'relative', zIndex: 2, maxWidth: '720px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            borderRadius: '20px',
            background: 'rgba(0, 210, 255, 0.12)',
            border: '1px solid rgba(0, 210, 255, 0.3)',
            color: '#00d2ff',
            fontSize: '0.72rem',
            fontWeight: 800,
            letterSpacing: '1.5px',
            textTransform: 'uppercase',
            marginBottom: '16px',
            backdropFilter: 'blur(8px)'
          }}>
            <span>🧬</span> Σ SIGMA STUDIO v8.0 — COGNITIVE KERNEL
          </div>

          <h1 style={{
            fontSize: '2.8rem',
            fontWeight: 900,
            color: '#fff',
            margin: '0 0 16px 0',
            lineHeight: 1.15,
            letterSpacing: '-1.5px',
            textShadow: '0 2px 10px rgba(0,0,0,0.5)'
          }}>
            Piattaforma di Orchestrazione AI & <span style={{
              background: 'linear-gradient(135deg, #00d2ff 0%, #7c5bf0 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>Ricerca Multimodale</span>
          </h1>

          <p style={{
            fontSize: '0.96rem',
            color: '#c0c4d0',
            lineHeight: 1.65,
            margin: '0 0 28px 0',
            maxWidth: '640px'
          }}>
            Un ambiente eseguibile avanzato in cui team di agenti AI collaborano per creare, verificare con script di test, formulare teoria in KaTeX e generare risorse 3D e multimediali.
          </p>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
              style={{
                padding: '12px 20px',
                borderRadius: '12px',
                background: 'rgba(0, 210, 255, 0.08)',
                border: '1px solid rgba(0, 210, 255, 0.3)',
                color: '#00d2ff',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer',
                backdropFilter: 'blur(10px)',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🇮🇹 README (IT)
            </button>

            <button
              onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
              style={{
                padding: '12px 20px',
                borderRadius: '12px',
                background: 'rgba(167, 139, 250, 0.08)',
                border: '1px solid rgba(167, 139, 250, 0.3)',
                color: '#a78bfa',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer',
                backdropFilter: 'blur(10px)',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🇬🇧 README (EN)
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="wg-metrics">
        <div className="wg-metric">
          <span className="wg-metric-value" style={{ color: '#00d2ff' }}>{countRootTopics}</span>
          <span className="wg-metric-label">Argomenti Fondamentali</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value" style={{ color: '#a78bfa' }}>{countModules}</span>
          <span className="wg-metric-label">Moduli di Conoscenza</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value" style={{ color: '#3fb950' }}>{countDocs}</span>
          <span className="wg-metric-label">Documenti (.md, .pdf)</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value" style={{ color: '#ff5064' }}>{countScripts}</span>
          <span className="wg-metric-label">Scripts Python (.py)</span>
        </div>
        <div className="wg-metric">
          <span className="wg-metric-value" style={{ color: '#faa03c' }}>{countVizMedia}</span>
          <span className="wg-metric-label">Viz & Media Assets</span>
        </div>
      </div>



      {/* Visual Kernel Cognitivo Showcase */}
      <div style={{
        margin: '36px 0',
        padding: '28px',
        borderRadius: '20px',
        background: 'linear-gradient(135deg, rgba(18, 20, 28, 0.95), rgba(12, 14, 20, 0.95))',
        border: '1px solid rgba(124, 91, 240, 0.25)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '24px',
        alignItems: 'center'
      }}>
        <div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '4px 12px', borderRadius: '12px',
            background: 'rgba(124, 91, 240, 0.15)', color: '#7c5bf0',
            fontSize: '0.72rem', fontWeight: 700, marginBottom: '12px'
          }}>
            <span>🧠</span> ARCHITETTURA DI SISTEMA
          </div>
          <h2 style={{ margin: '0 0 12px 0', fontSize: '1.4rem', color: '#fff', fontWeight: 800 }}>
            Sigma Studio come Kernel Cognitivo
          </h2>
          <p style={{ fontSize: '0.86rem', color: '#8b8fa3', lineHeight: 1.65, margin: '0 0 20px 0' }}>
            Come un sistema operativo gestisce processi, risorse di memoria e periferiche hardware, Sigma Studio orchestra i Modelli Linguistici (LLM) 
            come unità computazionali centrali, regolamentati da contratti eseguibili e bus di I/O governati.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#00d2ff' }}>⚡ LLM = CPU</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Modelli locali o cloud eseguono la computazione.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#3fb950' }}>📜 Manifesti = Rules</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Modelfile definiti in <code style={{ color: '#00d2ff' }}>manifesti/</code>.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#7c5bf0' }}>🔌 MCP = Bus I/O</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Accesso a filesystem, Home Assistant, memoria.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#ffb86c' }}>🔒 Sandbox = Bounds</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Operazioni verificate e confinate su disco.</div>
            </div>
          </div>
        </div>

        <div style={{
          position: 'relative',
          borderRadius: '16px',
          overflow: 'hidden',
          border: '1px solid rgba(124, 91, 240, 0.3)',
          boxShadow: '0 12px 32px rgba(0,0,0,0.5)'
        }}>
          <img
            src="/images/kernel_graphic.jpg"
            alt="Kernel Cognitivo Architecture"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
          <div style={{
            position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
            padding: '12px 16px',
            background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
            fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600
          }}>
            🌐 Schema Architetturale del Kernel di Orchestrazione AI
          </div>
        </div>
      </div>

      {/* Visual Swarm Orchestration Showcase */}
      <div style={{
        margin: '36px 0',
        padding: '28px',
        borderRadius: '20px',
        background: 'linear-gradient(135deg, rgba(18, 20, 28, 0.95), rgba(12, 14, 20, 0.95))',
        border: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '24px',
        alignItems: 'center'
      }}>
        <div style={{
          position: 'relative',
          borderRadius: '16px',
          overflow: 'hidden',
          border: '1px solid rgba(0, 210, 255, 0.3)',
          boxShadow: '0 12px 32px rgba(0,0,0,0.5)'
        }}>
          <img
            src="/images/swarm_graphic.jpg"
            alt="Swarm Multi-Agent Orchestration"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
          <div style={{
            position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
            padding: '12px 16px',
            background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
            fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600
          }}>
            🤖 Swarm Dinamico di Agenti Specializzati
          </div>
        </div>

        <div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '4px 12px', borderRadius: '12px',
            background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff',
            fontSize: '0.72rem', fontWeight: 700, marginBottom: '12px'
          }}>
            <span>🤖</span> WORKFLOW MULTI-AGENTE
          </div>
          <h2 style={{ margin: '0 0 12px 0', fontSize: '1.4rem', color: '#fff', fontWeight: 800 }}>
            Dynamic Swarm & Orchestrazione Parallela
          </h2>
          <p style={{ fontSize: '0.86rem', color: '#8b8fa3', lineHeight: 1.65, margin: '0 0 20px 0' }}>
            Un team di agenti AI specializzati analizza l'obiettivo di ricerca, genera la struttura in micro-task e collabora per scrivere teoria, codice Python e visualizzazioni D3.js.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem', color: '#e2e8f0' }}>
              <span style={{ color: '#00d2ff' }}>📐</span> <strong>Matematico:</strong> Redazione teoremi e formule KaTeX
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem', color: '#e2e8f0' }}>
              <span style={{ color: '#3fb950' }}>💻</span> <strong>Programmatore:</strong> Scrittura script di test Python
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem', color: '#e2e8f0' }}>
              <span style={{ color: '#a78bfa' }}>🔍</span> <strong>Revisore:</strong> Verifica consistenza logica e self-healing
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem', color: '#e2e8f0' }}>
              <span style={{ color: '#ffb86c' }}>📊</span> <strong>Visualizzatore:</strong> Grafici D3.js ed elementi interattivi
            </div>
          </div>
        </div>
      </div>

      {/* Visual Training Lab Showcase */}
      <div style={{
        margin: '36px 0',
        padding: '28px',
        borderRadius: '20px',
        background: 'linear-gradient(135deg, rgba(18, 20, 28, 0.95), rgba(12, 14, 20, 0.95))',
        border: '1px solid rgba(210, 153, 34, 0.3)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '24px',
        alignItems: 'center'
      }}>
        <div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '4px 12px', borderRadius: '12px',
            background: 'rgba(210, 153, 34, 0.15)', color: '#d29922',
            fontSize: '0.72rem', fontWeight: 700, marginBottom: '12px'
          }}>
            <span>🧪</span> TRAINING LAB & SPECIALIZZAZIONE MODELLI
          </div>
          <h2 style={{ margin: '0 0 10px 0', fontSize: '1.4rem', color: '#fff', fontWeight: 800 }}>
            Evoluzione Continua degli Agenti AI
          </h2>
          <p style={{ fontSize: '0.9rem', color: '#e2e8f0', lineHeight: 1.6, margin: '0 0 12px 0', fontWeight: 600 }}>
            "Crea e migliora i tuoi agenti su un determinato ruolo: renderà la tua squadra AI sempre più forte."
          </p>
          <p style={{ fontSize: '0.84rem', color: '#8b8fa3', lineHeight: 1.65, margin: '0 0 20px 0' }}>
            Addestra piccoli modelli linguistici (SLM) in locale con Unsloth QLoRA, avvia il ciclo Autopilota per l'ottimizzazione automatica degli iperparametri e certifica i miglioramenti con il motore di Benchmark Ufficiale su 11 suite.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#d29922' }}>🚀 Unsloth QLoRA</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Fine-tuning ultra-veloce a basso consumo VRAM.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#3fb950' }}>🔨 Forgia SLM</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Addestramento ed export GGUF da zero in italiano.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#00d2ff' }}>🤖 Autopilota AI</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>Specializzazione autonoma del modello sul ruolo.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#a78bfa' }}>📊 11 Suite Benchmark</div>
              <div style={{ fontSize: '0.74rem', color: '#6b7080', marginTop: '3px' }}>MMLU, GSM8K, HumanEval per verbali di audit.</div>
            </div>
          </div>

          <button
            onClick={() => openTab({ name: 'Training Lab' }, 'training_lab')}
            style={{
              padding: '10px 20px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #d29922, #3fb950)',
              border: 'none',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.82rem',
              cursor: 'pointer',
              boxShadow: '0 6px 20px rgba(210, 153, 34, 0.3)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            🧪 Entra nel Training Lab
          </button>
        </div>

        <div style={{
          position: 'relative',
          borderRadius: '16px',
          overflow: 'hidden',
          border: '1px solid rgba(210, 153, 34, 0.35)',
          boxShadow: '0 12px 32px rgba(0,0,0,0.5)'
        }}>
          <img
            src="/images/training_graphic.jpg"
            alt="Training Lab Specialization"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
          <div style={{
            position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
            padding: '12px 16px',
            background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
            fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600
          }}>
            ⚡ Fine-Tuning e Specializzazione degli Agenti AI
          </div>
        </div>
      </div>

      {/* State & Connection System Status Cards */}
      <div style={{ margin: '36px 0 24px 0' }}>
        <h2 style={{ fontSize: '1.3rem', color: '#fff', fontWeight: 800, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>⚡</span> Stato Connessioni & Kernel Integrati
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {/* Card 1: MCP Hub */}
          <div style={{
            padding: '20px', borderRadius: '16px', background: 'rgba(18, 20, 28, 0.85)',
            border: '1px solid rgba(63, 185, 80, 0.3)', boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#3fb950', background: 'rgba(63, 185, 80, 0.15)', padding: '3px 10px', borderRadius: '12px' }}>CONNESSI (12/12)</span>
                <span style={{ fontSize: '1.2rem' }}>🔌</span>
              </div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '1.05rem', color: '#fff', fontWeight: 800 }}>MCP Hub & Protocol Bus</h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                Tutti i 12 server MCP (Filesystem, Home Assistant, SQLite, Memory, Playwright, Brave Search) sono attivi e verificati.
              </p>
            </div>
            <button onClick={() => openTab({ name: 'MCP Hub' }, 'mcp_hub')} style={{ ...quickLinkStyle('#3fb950'), marginTop: '16px', width: 'fit-content' }}>
              Gestisci MCP Server 🔌
            </button>
          </div>

          {/* Card 2: Hardware & GPU */}
          <div style={{
            padding: '20px', borderRadius: '16px', background: 'rgba(18, 20, 28, 0.85)',
            border: '1px solid rgba(0, 210, 255, 0.3)', boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff', background: 'rgba(0, 210, 255, 0.15)', padding: '3px 10px', borderRadius: '12px' }}>OLLAMA & GPU ONLINE</span>
                <span style={{ fontSize: '1.2rem' }}>⚡</span>
              </div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '1.05rem', color: '#fff', fontWeight: 800 }}>Hardware & Cluster GPU</h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                Monitoraggio VRAM in tempo reale, allocazione dinamica dei pesi su GPU NVIDIA ed esecuzione parallela dei thread.
              </p>
            </div>
            <button onClick={() => openTab({ name: '⚡ Hardware & GPU Monitor' }, 'hardware_lab')} style={{ ...quickLinkStyle('#00d2ff'), marginTop: '16px', width: 'fit-content' }}>
              Hardware Monitor ⚡
            </button>
          </div>

          {/* Card 3: Home Assistant & Domotica */}
          <div style={{
            padding: '20px', borderRadius: '16px', background: 'rgba(18, 20, 28, 0.85)',
            border: '1px solid rgba(167, 139, 250, 0.3)', boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
            display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#a78bfa', background: 'rgba(167, 139, 250, 0.15)', padding: '3px 10px', borderRadius: '12px' }}>HOME ASSISTANT OK</span>
                <span style={{ fontSize: '1.2rem' }}>🏠</span>
              </div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '1.05rem', color: '#fff', fontWeight: 800 }}>Domotica & Smart Home IoT</h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                Integrazione diretta con Home Assistant per il controllo AI di luci, sensori di temperatura, prese smart e scene domotiche.
              </p>
            </div>
            <button onClick={() => openTab({ name: '🏠 Domotica & Home Assistant' }, 'domotica')} style={{ ...quickLinkStyle('#a78bfa'), marginTop: '16px', width: 'fit-content' }}>
              Pannello Domotica 🏠
            </button>
          </div>
        </div>
      </div>

      {/* Primi Passi nella Piattaforma (Interactive Card Grid) */}
      <div style={{ margin: '36px 0 24px 0' }}>
        <h2 style={{ fontSize: '1.3rem', color: '#fff', fontWeight: 800, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🚀</span> Primi Passi & Guida alle Funzionalità della Piattaforma
        </h2>
        <p style={{ fontSize: '0.86rem', color: '#8b8fa3', margin: '0 0 24px 0' }}>
          Panoramica completa ed interattiva: clicca su qualsiasi card per aprire direttamente la funzionalità desiderata:
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px'
        }}>
          {PRIMI_PASSI_CARDS.map(card => {
            const IconComponent = card.icon;
            return (
              <div
                key={card.step}
                onClick={() => card.onClick(openTab)}
                className="primi-passi-card"
                style={{
                  padding: '22px',
                  borderRadius: '18px',
                  background: 'rgba(18, 20, 28, 0.85)',
                  border: `1px solid ${card.color}35`,
                  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.35)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '16px',
                  backdropFilter: 'blur(12px)',
                  transition: 'all 0.25s ease'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: '12px',
                      background: `${card.color}18`,
                      border: `1px solid ${card.color}40`,
                      color: card.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      boxShadow: `0 0 14px ${card.color}25`
                    }}>
                      <IconComponent size={22} />
                    </div>

                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      color: card.color,
                      background: `${card.color}15`,
                      border: `1px solid ${card.color}30`,
                      padding: '3px 10px',
                      borderRadius: '20px',
                      letterSpacing: '0.5px'
                    }}>
                      STEP {card.step}
                    </span>
                  </div>

                  <h3 style={{ margin: '0 0 6px 0', fontSize: '0.98rem', fontWeight: 800, color: '#fff' }}>
                    {card.title}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                    {card.subtitle}
                  </p>
                </div>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  color: card.color,
                  paddingTop: '12px',
                  borderTop: '1px solid rgba(255, 255, 255, 0.05)'
                }}>
                  <span>{card.actionText}</span>
                  <ArrowRight size={14} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        marginTop: '48px',
        padding: '24px 0 12px 0',
        borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        color: '#6b7080',
        fontSize: '0.78rem',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: '#00d2ff',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🇮🇹 README_IT.md
          </button>
          <span>•</span>
          <button
            onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: '#3fb950',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🇬🇧 README.md
          </button>
          <span>•</span>
          <button
            onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: '#a78bfa',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🏛️ Specifica Architetturale
          </button>
        </div>

        <div style={{ color: '#8b8fa3', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>⚡ Creato da <strong>Diego Saitta</strong> — 🧬 <strong>Sigma Studio</strong></span>
        </div>
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateTopicModal
          onCreated={handleCreated}
          onCancel={() => setShowCreate(false)}
          allTopics={topics}
        />
      )}
      {editTopic && (
        <TopicEditModal
          topic={editTopic}
          onSave={handleEdited}
          onCancel={() => setEditTopic(null)}
          allTopics={topics}
        />
      )}
      {deleteTopic && (
        <DeleteConfirmModal
          topic={deleteTopic}
          onConfirm={handleDeleted}
          onCancel={() => setDeleteTopic(null)}
        />
      )}
    </div>
  );
}