import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import {
  ZoomIn, ZoomOut, RotateCcw, Save, Search, GitBranch,
  Layers, RefreshCw, Eye, Sparkles, FileCode, Check, GitCommit, Sliders
} from 'lucide-react';

const CATEGORY_COLORS = {
  folder: { stroke: '#00f2fe', fill: 'rgba(0, 242, 254, 0.15)' },
  docs: { stroke: '#bc8cff', fill: 'rgba(188, 140, 255, 0.18)' },
  code: { stroke: '#38bdf8', fill: 'rgba(56, 189, 248, 0.18)' },
  test: { stroke: '#3fb950', fill: 'rgba(63, 185, 80, 0.2)' },
  config: { stroke: '#eab308', fill: 'rgba(234, 179, 8, 0.18)' },
  media: { stroke: '#f43f5e', fill: 'rgba(244, 63, 94, 0.2)' },
  ui: { stroke: '#fb923c', fill: 'rgba(251, 146, 60, 0.18)' },
  other: { stroke: '#8b949e', fill: 'rgba(139, 148, 158, 0.12)' },
};

export default function DevGraphView({
  targetPath = '',
  workspaceRoot = '',
  onOpenFile,
  onAiCreate,
  onShowDiff,
  theme = 'dark',
  isLight = false
}) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);
  const zoomBehaviorRef = useRef(null);

  const [graphData, setGraphData] = useState({ nodes: [], links: [], git_branch: 'main' });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [depth, setDepth] = useState(3);
  const [searchQuery, setSearchQuery] = useState('');
  const [gitOnlyFilter, setGitOnlyFilter] = useState(false);
  const [showSliders, setShowSliders] = useState(false);

  // Configurazioni layout salvate in localStorage
  const [fontSize, setFontSize] = useState(() => {
    try {
      const v = localStorage.getItem('sigma_dev_graph_font_size');
      return v ? parseInt(v, 10) : 11;
    } catch {
      return 11;
    }
  });

  const [branchDist, setBranchDist] = useState(() => {
    try {
      const v = localStorage.getItem('sigma_dev_graph_branch_dist');
      return v ? parseInt(v, 10) : 90;
    } catch {
      return 90;
    }
  });

  // 1. Fetch Grafo da backend
  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams({
        path: targetPath || '',
        depth: String(depth),
        workspace_root: workspaceRoot || ''
      });
      const res = await fetch(`/api/developer/fs/graph?${q.toString()}`);
      const data = await res.json();
      if (data.success) {
        setGraphData({
          nodes: data.nodes || [],
          links: data.links || [],
          git_branch: data.git_branch || 'main',
          stats: data.stats || {}
        });
      }
    } catch (err) {
      console.error('Errore caricamento grafo developer:', err);
    } finally {
      setLoading(false);
    }
  }, [targetPath, depth, workspaceRoot]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // 2. Filtro nodi e archi
  const filteredData = useMemo(() => {
    let activeNodes = graphData.nodes;
    if (gitOnlyFilter) {
      activeNodes = activeNodes.filter(n => n.git_status && n.git_status !== 'clean');
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      activeNodes = activeNodes.filter(n =>
        n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q)
      );
    }

    const activeIds = new Set(activeNodes.map(n => n.id));
    const activeLinks = graphData.links.filter(
      l => activeIds.has(l.source?.id || l.source) && activeIds.has(l.target?.id || l.target)
    );

    return { nodes: activeNodes, links: activeLinks };
  }, [graphData, gitOnlyFilter, searchQuery]);

  // 3. Rendering D3 Force Simulation
  useEffect(() => {
    if (!svgRef.current || !containerRef.current || filteredData.nodes.length === 0) return;

    let isMounted = true;
    import('d3').then((d3) => {
      if (!isMounted || !svgRef.current || !containerRef.current) return;

      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const width = containerRef.current.clientWidth || 800;
      const height = containerRef.current.clientHeight || 600;

      // Definizioni Marker frecce per gli Import
      const defs = svg.append('defs');
      defs.append('marker')
        .attr('id', 'dev-import-arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', '#38bdf8')
        .attr('d', 'M0,-5L10,0L0,5');

      defs.append('marker')
        .attr('id', 'dev-ref-arrow')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 18)
        .attr('refY', 0)
        .attr('markerWidth', 5)
        .attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', '#bc8cff')
        .attr('d', 'M0,-4L8,0L0,4');

      // Zoom container
      const g = svg.append('g');
      const zoom = d3.zoom()
        .scaleExtent([0.2, 4])
        .on('zoom', (e) => g.attr('transform', e.transform));
      svg.call(zoom);
      zoomBehaviorRef.current = zoom;

      // Copia nodi e links per evitare mutazioni dirette di React
      const nodesCopy = filteredData.nodes.map(d => ({ ...d }));
      const linksCopy = filteredData.links.map(d => ({
        ...d,
        source: typeof d.source === 'object' ? d.source.id : d.source,
        target: typeof d.target === 'object' ? d.target.id : d.target
      }));

      // Inizializzazione fisica
      const simulation = d3.forceSimulation(nodesCopy)
        .force('link', d3.forceLink(linksCopy).id(d => d.id).distance(d => {
          if (d.type === 'import') return branchDist * 1.3;
          if (d.type === 'reference') return branchDist * 1.1;
          return branchDist;
        }))
        .force('charge', d3.forceManyBody().strength(-220))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => (d.is_dir ? 26 : 16) + 4));

      simulationRef.current = simulation;

      // Ripristino posizioni personalizzate da localStorage se presenti
      try {
        const saved = JSON.parse(localStorage.getItem('sigma_dev_graph_positions') || '{}');
        nodesCopy.forEach(n => {
          if (saved[n.id]) {
            n.fx = saved[n.id].x;
            n.fy = saved[n.id].y;
          }
        });
      } catch (_) {}

      // Disegno Links
      const link = g.append('g')
        .selectAll('line')
        .data(linksCopy)
        .enter()
        .append('line')
        .attr('stroke', d => {
          if (d.type === 'import') return '#38bdf8';
          if (d.type === 'reference') return '#bc8cff';
          return isLight ? '#d0d7de' : 'rgba(255, 255, 255, 0.12)';
        })
        .attr('stroke-width', d => d.type === 'import' ? 1.6 : 1.2)
        .attr('stroke-dasharray', d => {
          if (d.type === 'import') return '4,3';
          if (d.type === 'reference') return '2,3';
          return 'none';
        })
        .attr('marker-end', d => {
          if (d.type === 'import') return 'url(#dev-import-arrow)';
          if (d.type === 'reference') return 'url(#dev-ref-arrow)';
          return null;
        });

      // Disegno Nodi
      const node = g.append('g')
        .selectAll('g')
        .data(nodesCopy)
        .enter()
        .append('g')
        .style('cursor', 'pointer')
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
          }))
        .on('click', (event, d) => {
          event.stopPropagation();
          setSelectedNode(d);
        })
        .on('dblclick', (event, d) => {
          event.stopPropagation();
          if (!d.is_dir && onOpenFile) {
            onOpenFile(d.path);
          }
        });

      // Cerchio del nodo
      node.append('circle')
        .attr('r', d => d.is_root ? 24 : (d.is_dir ? 18 : 12))
        .attr('fill', d => {
          const cfg = CATEGORY_COLORS[d.category] || CATEGORY_COLORS.other;
          return cfg.fill;
        })
        .attr('stroke', d => {
          // Highlight stato Git se modificato
          if (d.git_status === 'modified') return '#f59e0b';
          if (d.git_status === 'untracked') return '#10b981';
          if (d.git_status === 'conflict') return '#ef4444';
          const cfg = CATEGORY_COLORS[d.category] || CATEGORY_COLORS.other;
          return cfg.stroke;
        })
        .attr('stroke-width', d => (d.git_status && d.git_status !== 'clean') ? 2.8 : (d.is_dir ? 2.2 : 1.5))
        .attr('filter', d => (d.git_status && d.git_status !== 'clean') ? 'drop-shadow(0 0 6px rgba(245, 158, 11, 0.6))' : 'none');

      // Badge Git sui nodi modificati
      node.filter(d => d.git_status && d.git_status !== 'clean')
        .append('text')
        .attr('dx', 10)
        .attr('dy', -8)
        .attr('font-size', '8px')
        .attr('font-weight', '800')
        .attr('fill', d => d.git_status === 'untracked' ? '#10b981' : (d.git_status === 'conflict' ? '#ef4444' : '#f59e0b'))
        .text(d => d.git_status === 'untracked' ? 'U' : (d.git_status === 'conflict' ? '!' : 'M'));

      // Icona testuale / estensione nel centro per nodi cartella o file
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('font-size', d => d.is_dir ? '11px' : '7px')
        .attr('font-weight', '700')
        .attr('fill', isLight ? '#24292f' : '#f0f6fc')
        .attr('pointer-events', 'none')
        .text(d => d.is_dir ? '📁' : (d.extension || '').slice(0, 3).toUpperCase());

      // Etichetta del nome sotto il nodo
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', d => (d.is_dir ? 28 : 22))
        .attr('font-size', `${fontSize}px`)
        .attr('font-weight', d => d.is_dir ? '700' : '500')
        .attr('fill', isLight ? '#24292f' : '#c9d1d9')
        .attr('pointer-events', 'none')
        .text(d => d.name.length > 20 ? d.name.slice(0, 19) + '…' : d.name);

      // Tick listener
      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
      });
    });

    return () => {
      isMounted = false;
      if (simulationRef.current) simulationRef.current.stop();
    };
  }, [filteredData, isLight, fontSize, branchDist, onOpenFile]);

  // Azioni Layout: Salva posizioni
  const handleSavePositions = () => {
    if (!simulationRef.current) return;
    const positions = {};
    simulationRef.current.nodes().forEach(n => {
      positions[n.id] = { x: n.x, y: n.y };
    });
    try {
      localStorage.setItem('sigma_dev_graph_positions', JSON.stringify(positions));
    } catch (_) {}
  };

  // Azioni Layout: Reset
  const handleResetPositions = () => {
    try {
      localStorage.removeItem('sigma_dev_graph_positions');
    } catch (_) {}
    if (simulationRef.current) {
      simulationRef.current.nodes().forEach(n => {
        n.fx = null;
        n.fy = null;
      });
      simulationRef.current.alpha(1).restart();
    }
  };

  const handleZoom = (factor) => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    import('d3').then((d3) => {
      d3.select(svgRef.current).transition().duration(250).call(zoomBehaviorRef.current.scaleBy, factor);
    });
  };

  const handleResetZoom = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    import('d3').then((d3) => {
      d3.select(svgRef.current).transition().duration(250).call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
    });
  };

  return (
    <div ref={containerRef} className="dev-graph-container">
      {/* Top Floating Toolbar */}
      <div className={`dev-graph-toolbar ${isLight ? 'light' : 'dark'}`}>
        {/* Branch Git Badge */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          fontSize: '0.74rem',
          fontWeight: 700,
          padding: '3px 8px',
          borderRadius: '5px',
          background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)',
          color: '#00f2fe'
        }}>
          <GitBranch size={13} />
          <span>{graphData.git_branch || 'main'}</span>
        </div>

        {/* Ricerca veloce */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '5px',
          background: isLight ? '#fff' : '#07090e',
          border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
          padding: '2px 6px',
          borderRadius: '5px'
        }}>
          <Search size={12} color="#8b949e" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtra nodi..."
            style={{
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: '0.72rem',
              color: isLight ? '#24292f' : '#e6edf3',
              width: '100px'
            }}
          />
        </div>

        {/* Filtro Git Solo Modificati */}
        <button
          className={`dev-graph-btn ${isLight ? 'light' : 'dark'} ${gitOnlyFilter ? 'active-git' : ''}`}
          onClick={() => setGitOnlyFilter(!gitOnlyFilter)}
          title="Mostra solo i file toccati da Git (Modified, Untracked, Conflicts)"
        >
          <GitCommit size={13} />
          <span>Solo Modifiche Git</span>
        </button>

        {/* Selettore Profondità Depth */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem' }}>
          <span style={{ color: '#8b949e' }}>Profondità:</span>
          {[1, 2, 3, 4].map((d) => (
            <button
              key={d}
              onClick={() => setDepth(d)}
              style={{
                background: depth === d ? '#00f2fe' : 'transparent',
                color: depth === d ? '#07090e' : (isLight ? '#24292f' : '#c9d1d9'),
                border: 'none',
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '0.72rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              {d}
            </button>
          ))}
        </div>

        {/* Zoom & Sliders Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={() => handleZoom(1.3)} title="Ingrandisci">
            <ZoomIn size={13} />
          </button>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={() => handleZoom(0.7)} title="Riduci">
            <ZoomOut size={13} />
          </button>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={handleResetZoom} title="Centra vista">
            <RotateCcw size={13} />
          </button>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={handleSavePositions} title="Salva posizioni attuali">
            <Save size={13} />
          </button>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={() => setShowSliders(!showSliders)} title="Regola fisica e font">
            <Sliders size={13} />
          </button>
          <button className={`dev-graph-btn ${isLight ? 'light' : 'dark'}`} onClick={fetchGraph} title="Ricarica Grafo">
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Sliders drawer se attivo */}
      {showSliders && (
        <div style={{
          position: 'absolute',
          top: '56px',
          left: '12px',
          zIndex: 20,
          padding: '10px 14px',
          borderRadius: '8px',
          background: isLight ? 'rgba(255,255,255,0.95)' : 'rgba(13,17,23,0.95)',
          border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          fontSize: '0.72rem',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3)'
        }}>
          <div>
            <span style={{ color: '#8b949e' }}>Dimensione Font ({fontSize}px):</span>
            <input
              type="range"
              min="9"
              max="16"
              value={fontSize}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                setFontSize(v);
                try { localStorage.setItem('sigma_dev_graph_font_size', String(v)); } catch (_) {}
              }}
              style={{ width: '100%', marginTop: '3px' }}
            />
          </div>
          <div>
            <span style={{ color: '#8b949e' }}>Distanza Rami ({branchDist}px):</span>
            <input
              type="range"
              min="50"
              max="180"
              value={branchDist}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                setBranchDist(v);
                try { localStorage.setItem('sigma_dev_graph_branch_dist', String(v)); } catch (_) {}
              }}
              style={{ width: '100%', marginTop: '3px' }}
            />
          </div>
          <button
            onClick={handleResetPositions}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.15)',
              background: 'transparent',
              color: isLight ? '#24292f' : '#c9d1d9',
              fontSize: '0.68rem',
              cursor: 'pointer'
            }}
          >
            Ripristina Posizioni Automatiche
          </button>
        </div>
      )}

      {/* SVG Canvas principale */}
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />

      {/* Card Dettagli Nodo Selezionato */}
      {selectedNode && (
        <div className={`dev-graph-node-card ${isLight ? 'light' : 'dark'}`}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '0.82rem' }}>
              <span>{selectedNode.is_dir ? '📁' : '📄'}</span>
              <span>{selectedNode.name}</span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', color: '#8b949e', fontSize: '0.7rem' }}>
            <div><strong>Percorso:</strong> {selectedNode.path}</div>
            <div><strong>Categoria:</strong> {selectedNode.category}</div>
            {selectedNode.size !== undefined && <div><strong>Dimensione:</strong> {(selectedNode.size / 1024).toFixed(1)} KB</div>}
            {selectedNode.git_status && (
              <div style={{
                color: selectedNode.git_status === 'clean' ? '#3fb950' : '#f59e0b',
                fontWeight: 600
              }}>
                <strong>Git Status:</strong> {selectedNode.git_status.toUpperCase()}
              </div>
            )}
          </div>

          {/* Quick Action buttons */}
          <div style={{ display: 'flex', gap: '6px', marginTop: '12px' }}>
            {!selectedNode.is_dir && onOpenFile && (
              <button
                onClick={() => onOpenFile(selectedNode.path)}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: '5px',
                  border: 'none',
                  background: '#00f2fe',
                  color: '#07090e',
                  fontWeight: 700,
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px'
                }}
              >
                <FileCode size={13} />
                <span>Apri File</span>
              </button>
            )}

            {selectedNode.is_dir && onAiCreate && (
              <button
                onClick={() => onAiCreate(selectedNode)}
                style={{
                  flex: 1,
                  padding: '5px 8px',
                  borderRadius: '5px',
                  border: 'none',
                  background: '#eab308',
                  color: '#07090e',
                  fontWeight: 700,
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px'
                }}
              >
                <Sparkles size={13} />
                <span>Crea con AI</span>
              </button>
            )}

            {selectedNode.git_status && selectedNode.git_status !== 'clean' && onShowDiff && (
              <button
                onClick={() => onShowDiff(selectedNode)}
                style={{
                  padding: '5px 8px',
                  borderRadius: '5px',
                  border: '1px solid #f59e0b',
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: '#f59e0b',
                  fontWeight: 600,
                  fontSize: '0.72rem',
                  cursor: 'pointer'
                }}
              >
                Vedi Diff
              </button>
            )}
          </div>
        </div>
      )}

      {loading && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0,0,0,0.3)',
          color: '#00f2fe',
          fontWeight: 600,
          fontSize: '0.84rem'
        }}>
          Caricamento Grafo Relazionale...
        </div>
      )}
    </div>
  );
}
