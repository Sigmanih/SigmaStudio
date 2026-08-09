import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ZoomIn, ZoomOut, Maximize, Play, Trash2, Square, AlertTriangle, Loader } from 'lucide-react';
import NodePalette from './NodePalette';
import NodeInspector from './NodeInspector';
import { PIPELINE_TEMPLATES, newNodeId } from './pipelineTemplates';

const NODE_W = 200;
const HEADER_H = 34;
const PORT_H = 22;
const PORT_TOP = 10;

// Geometria delle porte: deve restare allineata al CSS di .cs-node-block,
// altrimenti i cavi non partono dai pallini.
const portY = (index) => HEADER_H + PORT_TOP + index * PORT_H + PORT_H / 2;
const outPos = (node, def, port) => ({
  x: node.x + NODE_W,
  y: node.y + portY(Math.max(0, (def?.outputs || []).indexOf(port))),
});
const inPos = (node, def, port) => ({
  x: node.x,
  y: node.y + portY(Math.max(0, (def?.inputs || []).indexOf(port))),
});

const cablePath = (a, b) => {
  const dx = Math.max(40, Math.abs(b.x - a.x) * 0.5);
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
};

export default function CreativeNodeEditor({ assets = [], onAssetsProduced }) {
  const [catalog, setCatalog] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [view, setView] = useState({ x: 0, y: 0, zoom: 1 });
  const [linking, setLinking] = useState(null);   // {from, fromPort, cursor:{x,y}}
  const [running, setRunning] = useState(false);
  const [nodeStatus, setNodeStatus] = useState({});   // nodeId -> 'running'|'done'|'error'
  const [runLog, setRunLog] = useState([]);
  const [error, setError] = useState(null);

  const canvasRef = useRef(null);
  const dragRef = useRef(null);
  const abortRef = useRef(null);

  const defs = useMemo(() => Object.fromEntries(catalog.map(c => [c.type, c])), [catalog]);

  useEffect(() => {
    fetch('/api/creative/pipeline/nodes')
      .then(r => r.json())
      .then(data => { if (data.success) setCatalog(data.catalog || []); })
      .catch(() => setError('Catalogo nodi non raggiungibile'));
    return () => abortRef.current?.abort();
  }, []);

  // --- coordinate ------------------------------------------------------

  const toGraph = useCallback((clientX, clientY) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (clientX - rect.left - view.x) / view.zoom,
      y: (clientY - rect.top - view.y) / view.zoom,
    };
  }, [view]);

  // --- editing ---------------------------------------------------------

  const addNode = useCallback((type, at) => {
    const def = defs[type];
    if (!def) return;
    const node = {
      id: newNodeId(),
      type,
      x: Math.round(at.x - NODE_W / 2),
      y: Math.round(at.y - HEADER_H),
      params: { ...(def.params || {}) },
    };
    setNodes(prev => [...prev, node]);
    setSelectedId(node.id);
  }, [defs]);

  const removeNode = useCallback((id) => {
    setNodes(prev => prev.filter(n => n.id !== id));
    setConnections(prev => prev.filter(c => c.from !== id && c.to !== id));
    setSelectedId(prev => (prev === id ? null : prev));
  }, []);

  const updateParams = useCallback((id, params) => {
    setNodes(prev => prev.map(n => (n.id === id ? { ...n, params } : n)));
  }, []);

  const connect = useCallback((from, fromPort, to, toPort) => {
    if (from === to) return;
    setConnections(prev => [
      // una porta di input accetta una sola sorgente
      ...prev.filter(c => !(c.to === to && c.toPort === toPort)),
      { id: newNodeId('c'), from, fromPort, to, toPort },
    ]);
  }, []);

  const loadTemplate = useCallback((key) => {
    const tpl = PIPELINE_TEMPLATES[key];
    if (!tpl) return;
    const { nodes: n, connections: c } = tpl.create();
    setNodes(n);
    setConnections(c);
    setSelectedId(null);
    setNodeStatus({});
    setRunLog([]);
  }, []);

  // --- interazione mouse -----------------------------------------------

  const onNodePointerDown = (e, node) => {
    e.stopPropagation();
    setSelectedId(node.id);
    const start = toGraph(e.clientX, e.clientY);
    dragRef.current = { kind: 'node', id: node.id, dx: start.x - node.x, dy: start.y - node.y };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const onCanvasPointerDown = (e) => {
    if (e.target !== e.currentTarget && !e.target.classList.contains('cs-svg-canvas')) return;
    setSelectedId(null);
    dragRef.current = { kind: 'pan', startX: e.clientX - view.x, startY: e.clientY - view.y };
  };

  const onPointerMove = (e) => {
    const drag = dragRef.current;
    if (drag?.kind === 'node') {
      const p = toGraph(e.clientX, e.clientY);
      setNodes(prev => prev.map(n => (
        n.id === drag.id ? { ...n, x: Math.round(p.x - drag.dx), y: Math.round(p.y - drag.dy) } : n
      )));
    } else if (drag?.kind === 'pan') {
      setView(v => ({ ...v, x: e.clientX - drag.startX, y: e.clientY - drag.startY }));
    } else if (linking) {
      setLinking(l => ({ ...l, cursor: toGraph(e.clientX, e.clientY) }));
    }
  };

  const onPointerUp = () => { dragRef.current = null; };

  const startLink = (e, nodeId, port) => {
    e.stopPropagation();
    setLinking({ from: nodeId, fromPort: port, cursor: toGraph(e.clientX, e.clientY) });
  };

  const finishLink = (e, nodeId, port) => {
    e.stopPropagation();
    if (!linking) return;
    connect(linking.from, linking.fromPort, nodeId, port);
    setLinking(null);
  };

  const onWheel = (e) => {
    e.preventDefault();
    const rect = canvasRef.current.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    setView(v => {
      const zoom = Math.min(2, Math.max(0.3, v.zoom * factor));
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      // zoom centrato sul puntatore
      return { zoom, x: mx - (mx - v.x) * (zoom / v.zoom), y: my - (my - v.y) * (zoom / v.zoom) };
    });
  };

  const fitView = () => {
    if (!nodes.length) return setView({ x: 0, y: 0, zoom: 1 });
    const rect = canvasRef.current.getBoundingClientRect();
    const minX = Math.min(...nodes.map(n => n.x)) - 40;
    const minY = Math.min(...nodes.map(n => n.y)) - 40;
    const maxX = Math.max(...nodes.map(n => n.x + NODE_W)) + 40;
    const maxY = Math.max(...nodes.map(n => n.y + 180)) + 40;
    const zoom = Math.min(1.4, Math.max(0.3, Math.min(rect.width / (maxX - minX), rect.height / (maxY - minY))));
    setView({ zoom, x: -minX * zoom, y: -minY * zoom });
  };

  useEffect(() => {
    const onKey = (e) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId
          && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        removeNode(selectedId);
      }
      if (e.key === 'Escape') setLinking(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedId, removeNode]);

  // --- esecuzione -------------------------------------------------------

  const runPipeline = async () => {
    if (!nodes.length || running) return;
    setRunning(true);
    setError(null);
    setNodeStatus({});
    setRunLog([]);

    const pipeline_def = {
      nodes: nodes.map(n => ({ node_id: n.id, node_type: n.type, params: n.params })),
      connections: connections.map(c => ({
        from_node: c.from, from_port: c.fromPort, to_node: c.to, to_port: c.toPort,
      })),
    };

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch('/api/creative/pipeline/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pipeline_def }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const produced = [];
      const handleEvent = (evt) => {
        if (evt.error) { setError(evt.error); if (evt.node_id) setNodeStatus(s => ({ ...s, [evt.node_id]: 'error' })); }
        if (evt.node_id && evt.status === 'executing') setNodeStatus(s => ({ ...s, [evt.node_id]: 'running' }));
        if (evt.node_id && evt.status === 'node_complete') {
          setNodeStatus(s => ({ ...s, [evt.node_id]: 'done' }));
          if (evt.asset) produced.push(evt.asset);
        }
        if (evt.node_type || evt.message) {
          setRunLog(l => [...l.slice(-40), evt.message || `${evt.status}: ${evt.node_type || ''}`]);
        }
        if (Array.isArray(evt.results)) produced.push(...evt.results);
      };

      if (response.headers.get('content-type')?.includes('application/json')) {
        const data = await response.json();
        if (!data.success) throw new Error(data.error || 'Pipeline fallita');
        (data.results || []).forEach(r => produced.push(r));
      } else {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ') || line === 'data: [DONE]') continue;
            try { handleEvent(JSON.parse(line.slice(6))); } catch { /* frame parziale */ }
          }
        }
      }

      if (produced.length) onAssetsProduced?.(produced);
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const selected = nodes.find(n => n.id === selectedId) || null;

  return (
    <div className="cs-node-editor" ref={canvasRef}
         onPointerDown={onCanvasPointerDown}
         onPointerMove={onPointerMove}
         onPointerUp={onPointerUp}
         onWheel={onWheel}
         onDragOver={e => e.preventDefault()}
         onDrop={e => {
           e.preventDefault();
           const type = e.dataTransfer.getData('nodeType');
           if (type) addNode(type, toGraph(e.clientX, e.clientY));
         }}>

      <NodePalette
        catalog={catalog}
        templates={PIPELINE_TEMPLATES}
        onLoadTemplate={loadTemplate}
        onAddNode={(type) => {
          const rect = canvasRef.current.getBoundingClientRect();
          addNode(type, toGraph(rect.left + rect.width / 2, rect.top + rect.height / 2));
        }}
      />

      <svg className="cs-svg-canvas">
        <g transform={`translate(${view.x} ${view.y}) scale(${view.zoom})`}>
          {connections.map(c => {
            const from = nodes.find(n => n.id === c.from);
            const to = nodes.find(n => n.id === c.to);
            if (!from || !to) return null;
            const a = outPos(from, defs[from.type], c.fromPort);
            const b = inPos(to, defs[to.type], c.toPort);
            const active = nodeStatus[c.from] === 'done' && nodeStatus[c.to] === 'running';
            return (
              <g key={c.id}>
                <path d={cablePath(a, b)} className="cs-cable" onClick={() => setConnections(p => p.filter(x => x.id !== c.id))} />
                {active && <path d={cablePath(a, b)} className="cs-cable-anim" />}
              </g>
            );
          })}
          {linking && (() => {
            const from = nodes.find(n => n.id === linking.from);
            if (!from) return null;
            return <path d={cablePath(outPos(from, defs[from.type], linking.fromPort), linking.cursor)}
                         className="cs-cable cs-cable-pending" />;
          })()}
        </g>
      </svg>

      <div className="cs-node-layer" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.zoom})` }}>
        {nodes.map(node => {
          const def = defs[node.type] || { label: node.type, inputs: [], outputs: [] };
          const status = nodeStatus[node.id];
          return (
            <div
              key={node.id}
              className={`cs-node-block ${selectedId === node.id ? 'selected' : ''} ${status ? `status-${status}` : ''}`}
              style={{ left: node.x, top: node.y, width: NODE_W, borderTopColor: def.color }}
              onPointerDown={(e) => onNodePointerDown(e, node)}
            >
              <div className="cs-node-header" style={{ color: def.color }}>
                <span>{def.label || node.type}</span>
                {status === 'running' && <Loader size={12} className="cs-spin" />}
                {status === 'done' && <span className="cs-node-dot done" />}
                {status === 'error' && <AlertTriangle size={12} color="var(--error)" />}
              </div>
              <div className="cs-node-ports">
                {(def.inputs || []).map(port => (
                  <div className="cs-port cs-port-in" key={`i-${port}`}>
                    <div className="cs-port-circle" onPointerUp={(e) => finishLink(e, node.id, port)} />
                    <span>{port}</span>
                  </div>
                ))}
                {(def.outputs || []).map(port => (
                  <div className="cs-port cs-port-out" key={`o-${port}`}>
                    <span>{port}</span>
                    <div className="cs-port-circle" onPointerDown={(e) => startLink(e, node.id, port)} />
                  </div>
                ))}
                {node.params?.prompt && <div className="cs-node-preview">{node.params.prompt}</div>}
              </div>
            </div>
          );
        })}
      </div>

      {selected && (
        <NodeInspector
          node={selected}
          def={defs[selected.type]}
          assets={assets}
          onChange={(params) => updateParams(selected.id, params)}
          onDelete={() => removeNode(selected.id)}
        />
      )}

      <div className="cs-zoom-controls">
        <button className="cs-zoom-btn" onClick={() => setView(v => ({ ...v, zoom: Math.max(0.3, v.zoom - 0.1) }))}><ZoomOut size={16} /></button>
        <button className="cs-zoom-btn" onClick={fitView} title="Adatta alla vista"><Maximize size={16} /></button>
        <button className="cs-zoom-btn" onClick={() => setView(v => ({ ...v, zoom: Math.min(2, v.zoom + 0.1) }))}><ZoomIn size={16} /></button>
        <button className="cs-zoom-btn" onClick={() => { setNodes([]); setConnections([]); setNodeStatus({}); }} title="Svuota il canvas"><Trash2 size={16} /></button>
        {running ? (
          <button className="cs-generate-btn cs-run-btn" onClick={() => abortRef.current?.abort()}>
            <Square size={14} /> Interrompi
          </button>
        ) : (
          <button className="cs-generate-btn cs-run-btn" onClick={runPipeline} disabled={!nodes.length}>
            <Play size={16} /> Esegui pipeline
          </button>
        )}
        <span className="cs-zoom-label">{Math.round(view.zoom * 100)}%</span>
      </div>

      {(error || runLog.length > 0) && (
        <div className={`cs-run-console ${error ? 'error' : ''}`}>
          {error ? <><AlertTriangle size={14} /> {error}</> : runLog[runLog.length - 1]}
        </div>
      )}
    </div>
  );
}
