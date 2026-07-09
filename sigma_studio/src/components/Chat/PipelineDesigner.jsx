import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Square, Plus, Trash2, Link, Download, Upload, ZoomIn, ZoomOut, Target, ChevronRight, FlaskConical } from 'lucide-react';
import usePipelineDesigner from './core/usePipelineDesigner';

// ==============================================================================
// SIGMA PIPELINE DESIGNER — Mappa interattiva per orchestrazione multi-agente
// Ogni agente è un nodo configurabile con provider, modello, condizioni e routing
// ==============================================================================

function AgentNode({ node, selected, onSelect, onMove, onConnectorStart, onConnectorEnd, onRemove }) {
  const nodeRef = useRef(null);
  const isDragging = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const role = node.config.role || 'custom';

  const handleMouseDown = (e) => {
    if (e.target.closest('.pipeline-node-remove') || e.target.closest('.pipeline-node-connector')) return;
    isDragging.current = true;
    const rect = nodeRef.current.getBoundingClientRect();
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    onSelect(node.id);
    e.stopPropagation();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging.current) return;
      const container = nodeRef.current?.parentElement;
      if (!container) return;
      const crect = container.getBoundingClientRect();
      const x = e.clientX - crect.left - dragOffset.current.x;
      const y = e.clientY - crect.top - dragOffset.current.y;
      onMove(node.id, Math.max(0, x), Math.max(0, y));
    };
    const handleMouseUp = () => { isDragging.current = false; };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [node.id, onMove]);

  const hasCondition = node.condition?.enabled;

  return (
    <div
      ref={nodeRef}
      className={`pipeline-node ${selected ? 'selected' : ''}`}
      style={{
        position: 'absolute',
        left: node.x,
        top: node.y,
        borderTop: `3px solid ${node.config.color || '#8b8fa3'}`,
      }}
      onMouseDown={handleMouseDown}
    >
      <div className="pipeline-node-header" style={{ color: node.config.color || '#8b8fa3' }}>
        <span className="pipeline-node-icon">{node.config.icon || '🤖'}</span>
        <span className="pipeline-node-label">{node.label}</span>
        <button className="pipeline-node-remove" onClick={(e) => { e.stopPropagation(); onRemove(node.id); }} title="Rimuovi">
          <Trash2 size={12} />
        </button>
      </div>
      <div className="pipeline-node-body">
        <div className="pipeline-node-info">
          <span className="pipeline-node-provider">{node.config.provider}</span>
          <span className="pipeline-node-model">{node.config.model}</span>
        </div>
        {hasCondition && (
          <div className="pipeline-node-condition-badge">
            🔗 {node.condition.operator} "{node.condition.value}"
          </div>
        )}
      </div>
      <div className="pipeline-node-footer">
        <span className="pipeline-node-temp">{node.config.temperature?.toFixed(2) || '0.70'} temp</span>
        <button
          className="pipeline-node-connector"
          title="Connetti a un altro agente"
          onMouseDown={(e) => { e.stopPropagation(); onConnectorStart(node.id); }}
          onMouseUp={(e) => { e.stopPropagation(); onConnectorEnd(node.id); }}
        >
          <Link size={12} />
        </button>
      </div>
    </div>
  );
}

function ConditionRoute({ condition, fromNode, toNodeTrue, toNodeFalse }) {
  if (!condition?.enabled) return null;
  return (
    <div className="pipeline-condition-route">
      <div className="pipeline-condition-label">
        <span>🔗</span>
        <span>{condition.operator} "{condition.value?.slice(0, 20)}"</span>
      </div>
      {toNodeTrue && <div className="pipeline-route-true">✅ → {toNodeTrue.label}</div>}
      {toNodeFalse && <div className="pipeline-route-false">🔁 → {toNodeFalse.label}</div>}
    </div>
  );
}

function NodeEditorPanel({ node, onUpdateConfig, onUpdateCondition, PROVIDERS, AGENT_ROLES, CONDITION_OPERATORS, CONDITION_FIELDS, availableNodes, onRemove }) {
  if (!node) return (
    <div className="pipeline-editor-empty">
      <FlaskConical size={32} />
      <span>Seleziona un nodo per modificarlo</span>
    </div>
  );

  const roleData = AGENT_ROLES.find(r => r.id === node.config.role) || AGENT_ROLES[5];
  const currentProvider = PROVIDERS.find(p => p.id === node.config.provider);
  const providerModels = currentProvider?.models || [];

  return (
    <div className="pipeline-editor-panel">
      <div className="pipeline-editor-header">
        <span className="pipeline-editor-icon">{node.config.icon}</span>
        <input className="pipeline-editor-name" value={node.label}
          onChange={e => onUpdateConfig(node.id, { ...node.config, label: e.target.value })}
          placeholder="Nome agente" />
        <button className="pipeline-editor-close" onClick={() => onRemove(node.id)} title="Elimina nodo">
          <Trash2 size={14} />
        </button>
      </div>

      <div className="pipeline-editor-section">
        <div className="pipeline-editor-section-title">Ruolo & Provider</div>
        <label className="pipeline-editor-field">
          <span>Ruolo</span>
          <select value={node.config.role} onChange={e => {
            const role = AGENT_ROLES.find(r => r.id === e.target.value) || AGENT_ROLES[5];
            onUpdateConfig(node.id, { role: e.target.value, color: role.color, icon: role.icon, prompt: role.desc });
          }}>
            {AGENT_ROLES.map(r => <option key={r.id} value={r.id}>{r.icon} {r.label}</option>)}
          </select>
        </label>
        <label className="pipeline-editor-field">
          <span>Provider</span>
          <select value={node.config.provider} onChange={e => {
            const prov = PROVIDERS.find(p => p.id === e.target.value);
            onUpdateConfig(node.id, { provider: e.target.value, model: prov?.models[0] || '' });
          }}>
            {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <label className="pipeline-editor-field">
          <span>Modello</span>
          <select value={node.config.model} onChange={e => onUpdateConfig(node.id, { model: e.target.value })}>
            {providerModels.map(m => <option key={m} value={m}>{m}</option>)}
            {!providerModels.includes(node.config.model) && (
              <option value={node.config.model}>{node.config.model}</option>
            )}
          </select>
        </label>
      </div>

      <div className="pipeline-editor-section">
        <div className="pipeline-editor-section-title">Parametri</div>
        <label className="pipeline-editor-field">
          <span>Temperatura <strong>{node.config.temperature?.toFixed(2)}</strong></span>
          <input type="range" min="0" max="2" step="0.05" value={node.config.temperature}
            onChange={e => onUpdateConfig(node.id, { temperature: parseFloat(e.target.value) })} />
        </label>
        <label className="pipeline-editor-field">
          <span>Max Tokens</span>
          <select value={node.config.max_tokens} onChange={e => onUpdateConfig(node.id, { max_tokens: parseInt(e.target.value) })}>
            {[1024, 2048, 4096, 8192, 16384, 32768].map(n => <option key={n} value={n}>{n/1024}K</option>)}
          </select>
        </label>
        <label className="pipeline-editor-field">
          <span>Context (num_ctx)</span>
          <select value={node.config.num_ctx} onChange={e => onUpdateConfig(node.id, { num_ctx: parseInt(e.target.value) })}>
            {[2048, 4096, 8192, 16384, 32768, 65536].map(n => <option key={n} value={n}>{n/1024}K</option>)}
          </select>
        </label>
      </div>

      <div className="pipeline-editor-section">
        <div className="pipeline-editor-section-title">
          Condizione di Routing
          <label className="pipeline-editor-toggle">
            <input type="checkbox" checked={node.condition?.enabled || false}
              onChange={e => onUpdateCondition(node.id, { enabled: e.target.checked })} />
            <span>Attiva</span>
          </label>
        </div>
        {node.condition?.enabled && (
          <>
            <label className="pipeline-editor-field">
              <span>Campo da valutare</span>
              <select value={node.condition.field} onChange={e => onUpdateCondition(node.id, { field: e.target.value })}>
                {CONDITION_FIELDS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}
              </select>
            </label>
            <label className="pipeline-editor-field">
              <span>Operatore</span>
              <select value={node.condition.operator} onChange={e => onUpdateCondition(node.id, { operator: e.target.value })}>
                {CONDITION_OPERATORS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </label>
            <label className="pipeline-editor-field">
              <span>Valore atteso</span>
              <input value={node.condition.value} onChange={e => onUpdateCondition(node.id, { value: e.target.value })}
                placeholder='es: "✅", "proved", "success"' />
            </label>
            <label className="pipeline-editor-field">
              <span>✅ Se vero →</span>
              <select value={node.condition.ifTrue} onChange={e => onUpdateCondition(node.id, { ifTrue: e.target.value })}>
                <option value="">— Prossimo nodo —</option>
                {availableNodes.filter(n => n.id !== node.id).map(n => (
                  <option key={n.id} value={n.id}>{n.label}</option>
                ))}
              </select>
            </label>
            <label className="pipeline-editor-field">
              <span>❌ Se falso →</span>
              <select value={node.condition.ifFalse} onChange={e => onUpdateCondition(node.id, { ifFalse: e.target.value })}>
                <option value="">— Fine pipeline —</option>
                {availableNodes.filter(n => n.id !== node.id).map(n => (
                  <option key={n.id} value={n.id}>{n.label}</option>
                ))}
              </select>
            </label>
          </>
        )}
      </div>
    </div>
  );
}

export default function PipelineDesigner({ onClose, onTasksUpdated, addToast }) {
  const designer = usePipelineDesigner();
  const canvasRef = useRef(null);
  const [connectingFromId, setConnectingFromId] = useState(null);
  const [connectTargets, setConnectTargets] = useState([]);

  const {
    nodes, connections, selectedNode, selectedNodeId,
    canvasOffset, canvasZoom, pipelineGoal, setPipelineGoal,
    addNode, removeNode, updateNodeConfig, updateNodeCondition, moveNode,
    addConnection, removeConnection, clearAll, exportPipeline, importPipeline,
    setSelectedNodeId, handleCanvasWheel,
    PROVIDERS, AGENT_ROLES, CONDITION_OPERATORS, CONDITION_FIELDS, availableNodes,
  } = designer;

  const handleConnectorStart = (nodeId) => {
    setConnectingFromId(nodeId);
    setConnectTargets(nodes.filter(n => n.id !== nodeId));
  };

  const handleConnectorEnd = (targetId) => {
    if (connectingFromId && connectingFromId !== targetId) {
      addConnection(connectingFromId, targetId);
    }
    setConnectingFromId(null);
    setConnectTargets([]);
  };

  const handleCanvasClick = (e) => {
    if (e.target === canvasRef.current || e.target.classList.contains('pipeline-canvas')) {
      setSelectedNodeId(null);
    }
  };

  const handleAddNode = () => {
    addNode(50 + Math.random() * 200, 50 + Math.random() * 200);
  };

  const handleExport = () => {
    const data = exportPipeline();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'pipeline_config.json'; a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.onchange = async (e) => {
      const text = await e.target.files[0].text();
      try { importPipeline(JSON.parse(text)); if (addToast) addToast('✅ Pipeline importata', 'success'); }
      catch { if (addToast) addToast('❌ File JSON non valido', 'error'); }
    };
    input.click();
  };

  // Find connected nodes
  const getConnectedNodes = (nodeId) => {
    return connections.filter(c => c.from === nodeId).map(c => {
      const target = nodes.find(n => n.id === c.to);
      return { conn: c, target };
    });
  };

  return (
    <div className="pipeline-designer">
      {/* Header */}
      <div className="pipeline-header">
        <div className="pipeline-header-title">
          <FlaskConical size={18} />
          <span>🧪 Sigma Pipeline Designer</span>
        </div>
        <div className="pipeline-header-actions">
          <button className="pipeline-btn pipeline-btn-primary" onClick={handleAddNode}>
            <Plus size={14} /> Aggiungi Agente
          </button>
          <button className="pipeline-btn pipeline-btn-glass" onClick={handleExport} title="Esporta configurazione">
            <Download size={14} />
          </button>
          <button className="pipeline-btn pipeline-btn-glass" onClick={handleImport} title="Importa configurazione">
            <Upload size={14} />
          </button>
          <button className="pipeline-btn pipeline-btn-ghost" onClick={clearAll} title="Pulisci tutto">
            <Trash2 size={14} />
          </button>
          <button className="pipeline-btn pipeline-btn-ghost" onClick={onClose}>✕</button>
        </div>
      </div>

      {/* Goal input */}
      <div className="pipeline-goal-row">
        <Target size={14} />
        <input className="pipeline-goal-input" value={pipelineGoal}
          onChange={e => setPipelineGoal(e.target.value)}
          placeholder="Definisci l'obiettivo della pipeline..."
        />
      </div>

      {/* Main area: Canvas + Editor */}
      <div className="pipeline-main">
        {/* Canvas */}
        <div className="pipeline-canvas-container"
          ref={canvasRef}
          onClick={handleCanvasClick}
          onWheel={handleCanvasWheel}
          style={{ cursor: connectingFromId ? 'crosshair' : 'default' }}
        >
          <div className="pipeline-canvas"
            style={{
              transform: `scale(${canvasZoom}) translate(${canvasOffset.x}px, ${canvasOffset.y}px)`,
              transformOrigin: '0 0',
            }}
          >
            {/* Connection lines */}
            <svg className="pipeline-svg" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }}>
              {connections.map(conn => {
                const from = nodes.find(n => n.id === conn.from);
                const to = nodes.find(n => n.id === conn.to);
                if (!from || !to) return null;
                const x1 = from.x + 140, y1 = from.y + 60;
                const x2 = to.x + 10, y2 = to.y + 60;
                const midX = (x1 + x2) / 2;
                return (
                  <g key={conn.id}>
                    <path d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                      fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2" />
                    <circle cx={x2} cy={y2} r="4" fill="rgba(0,210,255,0.4)" />
                  </g>
                );
              })}
            </svg>

            {/* Nodes */}
            {nodes.map(node => (
              <AgentNode
                key={node.id}
                node={node}
                selected={selectedNodeId === node.id}
                onSelect={setSelectedNodeId}
                onMove={moveNode}
                onConnectorStart={handleConnectorStart}
                onConnectorEnd={handleConnectorEnd}
                onRemove={removeNode}
              />
            ))}

            {/* Empty state */}
            {nodes.length === 0 && (
              <div className="pipeline-canvas-empty">
                <FlaskConical size={48} />
                <h3>Nessun agente nella pipeline</h3>
                <p>Clicca "Aggiungi Agente" per iniziare</p>
              </div>
            )}

            {/* Connection target hints */}
            {connectingFromId && connectTargets.map(t => (
              <div key={t.id} className="pipeline-connect-hint"
                style={{ left: t.x, top: t.y, width: 140, height: 110 }}
                onClick={() => handleConnectorEnd(t.id)}>
                + Collega a {t.label}
              </div>
            ))}
          </div>
        </div>

        {/* Editor panel */}
        <div className="pipeline-editor-sidebar">
          <NodeEditorPanel
            node={selectedNode}
            onUpdateConfig={updateNodeConfig}
            onUpdateCondition={updateNodeCondition}
            onRemove={removeNode}
            PROVIDERS={PROVIDERS}
            AGENT_ROLES={AGENT_ROLES}
            CONDITION_OPERATORS={CONDITION_OPERATORS}
            CONDITION_FIELDS={CONDITION_FIELDS}
            availableNodes={availableNodes}
          />
        </div>
      </div>

      {/* Connections list */}
      {connections.length > 0 && (
        <div className="pipeline-connections-bar">
          {connections.map(conn => {
            const from = nodes.find(n => n.id === conn.from);
            const to = nodes.find(n => n.id === conn.to);
            return (
              <div key={conn.id} className="pipeline-connection-chip">
                <span>{from?.label || '?'}</span>
                <ChevronRight size={12} />
                <span>{to?.label || '?'}</span>
                <button className="pipeline-chip-remove" onClick={() => removeConnection(conn.id)}>✕</button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}