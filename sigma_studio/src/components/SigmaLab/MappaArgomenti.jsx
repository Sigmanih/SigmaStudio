import React, { useRef, useEffect, useState, useCallback } from 'react';

// ==============================================================================
// MappaArgomenti — Mappa interattiva degli argomenti con D3 force-directed graph
// Porting di web_explorer/mappa_argomenti.html in React
// ==============================================================================

const TOPIC_COLOR = '#bc8cff';
const MODULE_COLOR = '#00d2ff';
const MODULE_FILL = 'rgba(0,210,255,0.12)';
const TOPIC_FILL = 'rgba(188,140,255,0.12)';
const ORANGE_COLOR = '#d29922';
const ORANGE_FILL = 'rgba(210,153,34,0.25)';
const DOC_COLORS = {
  teoria: { stroke: '#bc8cff', fill: 'rgba(188,140,255,0.2)' },
  test: { stroke: '#3fb950', fill: 'rgba(63,185,80,0.2)' },
  viz: { stroke: '#d29922', fill: 'rgba(210,153,34,0.2)' },
  docs: { stroke: '#ffd700', fill: 'rgba(255,215,0,0.2)' },
  whitepapers: { stroke: '#ffd700', fill: 'rgba(255,215,0,0.2)' },
};
const DOC_ICONS = { teoria: '📖', test: '🧪', viz: '📊', docs: '📄', whitepapers: '📜' };
const DOC_PATHS = { teoria: 'teoria', test: 'test', viz: 'viz', docs: 'docs', whitepapers: 'whitepapers' };

export default function MappaArgomenti({ onOpenFile }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [topicsData, setTopicsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null); // { type, data, topicId }
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [selectedModule, setSelectedModule] = useState(null); // null = all modules in active topic
  const [dimensions, setDimensions] = useState({ width: 500, height: 260 });
  const [stats, setStats] = useState({ topics: 0, modules: 0, docs: 0, teoria: 0, test: 0, viz: 0, parentLinks: 0 });
  const [showDocs, setShowDocs] = useState(() => {
    return localStorage.getItem('sigma_mappa_explore') === 'true';
  });

  // D3 refs
  const simulationRef = useRef(null);
  const zoomRef = useRef(null);
  const linksRef = useRef([]);

  // Fetch data — returns the fetched topics array
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/topics');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.topics) throw new Error('Formato risposta non valido');
      setTopicsData(data.topics);
      return data.topics;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Update dimensions on resize
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        const h = containerRef.current.clientHeight;
        if (w > 0 && h > 0) {
          setDimensions({ width: w, height: h });
        }
      }
    };
    // Delay initial measurement to ensure layout is complete
    const timer = setTimeout(handleResize, 50);
    window.addEventListener('resize', handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // Compute stats
  useEffect(() => {
    let totalModules = 0, totalDocs = 0, totalTeoria = 0, totalTest = 0, totalViz = 0, parentLinks = 0;
    for (const topic of topicsData) {
      if (!topic.modules) continue;
      totalModules += topic.modules.length;
      for (const mod of topic.modules) {
        totalDocs += (mod.docs || []).length + (mod.whitepapers || []).length;
        totalTeoria += (mod.teoria || []).length;
        totalTest += (mod.test || []).length;
        totalViz += (mod.viz || []).length;
      }
      if (topic.parent_id) parentLinks++;
    }
    setStats({ topics: topicsData.length, modules: totalModules, docs: totalDocs, teoria: totalTeoria, test: totalTest, viz: totalViz, parentLinks });
  }, [topicsData]);

  // Build D3 graph data
  const buildGraphData = useCallback(() => {
    const nodes = [];
    const links = [];
    const nodeMap = {};
    for (const topic of topicsData) {
      const topicId = 'topic-' + topic.id;
      nodes.push({ id: topicId, label: topic.name, type: 'topic', data: topic, r: 22 });
      nodeMap[topicId] = true;
      if (topic.modules) {
        for (const mod of topic.modules) {
          const modId = 'mod-' + topic.id + '-' + mod.number;
          nodes.push({ id: modId, label: mod.name, type: 'module', data: mod, topicId: topic.id, r: 16 });
          nodeMap[modId] = true;
          links.push({ source: topicId, target: modId });

          // Optionally add document nodes linked to this module
          if (showDocs) {
            for (const docType of ['teoria', 'test', 'viz', 'docs', 'whitepapers']) {
              const files = mod[docType] || [];
              for (const f of files) {
                const docId = 'doc-' + topic.id + '-' + mod.number + '-' + f.path.replace(/[^a-zA-Z0-9_-]/g, '_');
                nodes.push({
                  id: docId,
                  label: f.filename,
                  type: 'doc',
                  docType,
                  filePath: f.path,
                  parentModId: modId,
                  r: 6
                });
                nodeMap[docId] = true;
                links.push({ source: modId, target: docId });
              }
            }
          }
        }
      }
    }
    for (const topic of topicsData) {
      if (topic.parent_id) {
        const parentId = 'topic-' + topic.parent_id;
        const childId = 'topic-' + topic.id;
        if (nodeMap[parentId] && nodeMap[childId]) {
          links.push({ source: parentId, target: childId, type: 'parent' });
        }
      }
    }
    return { nodes, links };
  }, [topicsData, showDocs]);

  // D3 rendering
  useEffect(() => {
    if (!svgRef.current || topicsData.length === 0) return;
    // Guard against invalid dimensions (NaN/0)
    const width = dimensions.width;
    const height = dimensions.height;
    if (!width || !height || width <= 0 || height <= 0) return;

    let isCancelled = false;

    import('d3').then(d3 => {
      if (isCancelled) return;

      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const graphData = buildGraphData();
      const { nodes, links } = graphData;
      if (nodes.length === 0) return;
      linksRef.current = links;

      const width = dimensions.width;
      const height = dimensions.height;

      // Arrow markers
      const defs = svg.append('defs');
      defs.selectAll('marker')
        .data(['topic-module', 'parent-child'])
        .enter().append('marker')
        .attr('id', d => d)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', d => d === 'parent-child' ? 'rgba(210,153,34,0.3)' : 'rgba(255,255,255,0.15)')
        .attr('d', 'M0,-5L10,0L0,5');

      // Zoom
      const g = svg.append('g').attr('class', 'zoom-group');
      const zoom = d3.zoom()
        .scaleExtent([0.3, 4])
        .on('zoom', (event) => { g.attr('transform', event.transform); });
      svg.call(zoom);
      zoomRef.current = zoom;

      const initialScale = Math.min(width, height) / 600;
      svg.call(zoom.transform, d3.zoomIdentity.scale(initialScale));

      // Link type map
      const linkTypeMap = {};
      for (const topic of topicsData) {
        if (topic.parent_id) {
          const key = 'topic-' + topic.parent_id + '|topic-' + topic.id;
          linkTypeMap[key] = true;
        }
      }

      // Links
      const linkGroup = g.append('g').attr('class', 'links');
      const linkElements = linkGroup.selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('class', d => {
          const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
          return isParent ? 'graph-link parent-link' : 'graph-link';
        })
        .attr('stroke', d => {
          const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
          return isParent ? 'rgba(210,153,34,0.2)' : 'rgba(255,255,255,0.08)';
        })
        .attr('stroke-width', d => {
          const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
          return isParent ? 2 : 1.5;
        })
        .attr('stroke-dasharray', d => {
          const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
          return isParent ? '4,3' : 'none';
        })
        .attr('marker-end', d => {
          const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
          return isParent ? 'url(#parent-child)' : 'url(#topic-module)';
        });

      // Nodes
      const nodeGroup = g.append('g').attr('class', 'nodes');
      const nodeElements = nodeGroup.selectAll('g')
        .data(nodes)
        .enter().append('g')
        .attr('class', d => 'graph-node' + (selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number) ? ' selected' : ''))
        .on('click', (event, d) => {
          event.stopPropagation();
          if (d.type === 'doc') {
            if (onOpenFile && d.filePath) onOpenFile(d.filePath);
            return;
          }
          if (d.type === 'topic') {
            setSelectedNode({ type: 'topic', data: d.data });
            setActiveTopicId(d.data.id);
            setSelectedModule(null);
          } else {
            setSelectedNode({ type: 'module', data: d.data, topicId: d.topicId });
            // Set active topic to the module's parent topic and filter by this module
            setActiveTopicId(d.topicId);
            setSelectedModule(d.data.number);
          }
        })
        .on('mouseenter', (event, d) => {
          if (!simulationRef.current) return;
          linkElements.attr('class', l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            const isParent = linkTypeMap[sourceId + '|' + targetId] || linkTypeMap[targetId + '|' + sourceId];
            const baseClass = isParent ? 'graph-link parent-link' : 'graph-link';
            if (sourceId === d.id || targetId === d.id) return baseClass + ' highlight';
            return baseClass;
          });
          nodeElements.attr('opacity', n => {
            if (n.id === d.id) return 1;
            for (const l of links) {
              const s = typeof l.source === 'object' ? l.source.id : l.source;
              const t = typeof l.target === 'object' ? l.target.id : l.target;
              if ((s === d.id && t === n.id) || (t === d.id && s === n.id)) return 1;
            }
            return 0.25;
          });
        })
        .on('mouseleave', () => {
          linkElements.attr('class', l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            const isParent = linkTypeMap[sourceId + '|' + targetId] || linkTypeMap[targetId + '|' + sourceId];
            return isParent ? 'graph-link parent-link' : 'graph-link';
          });
          nodeElements.attr('opacity', 1);
        });

      nodeElements.append('circle')
        .attr('r', d => d.r)
        .attr('fill', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.fill;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return ORANGE_FILL;
          return d.type === 'topic' ? TOPIC_FILL : MODULE_FILL;
        })
        .attr('stroke', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.stroke;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return ORANGE_COLOR;
          return d.type === 'topic' ? TOPIC_COLOR : MODULE_COLOR;
        })
        .attr('stroke-width', d => {
          if (d.type === 'doc') return 1.5;
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          return isSelected ? 3.5 : 2.5;
        })
        .style('filter', d => {
          if (d.type === 'doc') return 'none';
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return 'drop-shadow(0 0 12px rgba(210,153,34,0.5))';
          return d.type === 'topic' ? 'drop-shadow(0 0 8px rgba(188,140,255,0.3))' : 'drop-shadow(0 0 6px rgba(0,210,255,0.2))';
        });

      nodeElements.append('text')
        .attr('class', d => 'node-label ' + d.type)
        .attr('dy', d => d.r + 14)
        .attr('text-anchor', 'middle')
        .attr('fill', '#8b8fa3')
        .attr('font-size', d => d.type === 'topic' ? '12px' : '10px')
        .attr('font-weight', d => d.type === 'topic' ? '700' : '500')
        .attr('pointer-events', 'none')
        .text(d => d.label.length > 30 ? d.label.slice(0, 28) + '…' : d.label);

      // Simulation
      const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(180).strength(0.4))
        .force('charge', d3.forceManyBody().strength(d => d.type === 'topic' ? -900 : -450))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => {
          if (d.type === 'topic') return d.r + 65;
          if (d.type === 'module') return d.r + 45;
          return d.r + 35;
        }).strength(0.85))
        .on('tick', () => {
          linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
          nodeElements.attr('transform', d => `translate(${d.x},${d.y})`);
        });

      simulationRef.current = simulation;

      return () => {
        simulation.stop();
      };
    });

    return () => { isCancelled = true; };
  }, [topicsData, dimensions, buildGraphData]);

  // Update node visuals on selection change without restarting simulation
  useEffect(() => {
    if (!svgRef.current || topicsData.length === 0) return;
    import('d3').then(d3 => {
      const svg = d3.select(svgRef.current);
      // Update node fills/strokes
      svg.selectAll('.graph-node circle')
        .attr('fill', d => {
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return ORANGE_FILL;
          return d.type === 'topic' ? TOPIC_FILL : MODULE_FILL;
        })
        .attr('stroke', d => {
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return ORANGE_COLOR;
          return d.type === 'topic' ? TOPIC_COLOR : MODULE_COLOR;
        })
        .attr('stroke-width', d => {
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          return isSelected ? 3.5 : 2.5;
        })
        .style('filter', d => {
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return 'drop-shadow(0 0 12px rgba(210,153,34,0.5))';
          return d.type === 'topic' ? 'drop-shadow(0 0 8px rgba(188,140,255,0.3))' : 'drop-shadow(0 0 6px rgba(0,210,255,0.2))';
        });
      // Update node class
      svg.selectAll('.graph-node')
        .attr('class', n => 'graph-node' + (selectedNode && n.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number) ? ' selected' : ''));
    });
  }, [selectedNode, topicsData]);

  const zoomIn = () => {
    if (svgRef.current && zoomRef.current) {
      const sel = window.d3 ? window.d3.select(svgRef.current) : null;
      if (sel) sel.transition().duration(300).call(zoomRef.current.scaleBy, 1.3);
    }
  };
  const zoomOut = () => {
    if (svgRef.current && zoomRef.current) {
      const sel = window.d3 ? window.d3.select(svgRef.current) : null;
      if (sel) sel.transition().duration(300).call(zoomRef.current.scaleBy, 0.7);
    }
  };
  const resetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      const sel = window.d3 ? window.d3.select(svgRef.current) : null;
      if (sel) {
        const initialScale = Math.min(dimensions.width, dimensions.height) / 600;
        sel.transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity.scale(initialScale));
      }
    }
  };

  // --- Detail Panel ---
  const escapeStr = (s) => {
    if (!s) return '';
    return String(s).replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>').replace(/"/g, '"');
  };

  const renderDetail = () => {
    if (!selectedNode) {
      return (
        <div className="detail-empty">
          <div className="detail-empty-icon">🔍</div>
          <div className="detail-empty-text">Seleziona un nodo nel grafo<br />per vedere i dettagli</div>
        </div>
      );
    }

    if (selectedNode.type === 'topic') {
      return renderTopicDetail(selectedNode.data);
    }
    return renderModuleDetail(selectedNode.data, selectedNode.topicId);
  };

  const handleCreateSubTopic = async (topic, modNum, modName) => {
    const name = prompt('Nome del nuovo sottoargomento:', 'nuovo_modulo');
    if (!name) return;
    const num = modNum || String(Date.now()).slice(-2);
    try {
      const res = await fetch('/api/create_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic_id: topic.id,
          number: num,
          name: name,
          description: ''
        })
      });
      const data = await res.json();
      if (data.success) {
        const freshTopics = await fetchData(); // refresh graph + columns, returns fresh data
        if (freshTopics) {
          const updatedTopic = freshTopics.find(t => t.id === topic.id);
          if (updatedTopic) {
            const newMod = updatedTopic.modules?.find(m => m.number === num);
            if (newMod) {
              setSelectedNode({ type: 'module', data: newMod, topicId: topic.id });
              setActiveTopicId(topic.id);
              setSelectedModule(newMod.number);
            }
          }
        }
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleCreateTopic = async () => {
    const name = prompt('Nome del nuovo argomento:', 'nuovo_argomento');
    if (!name) return;
    const topicId = name.toLowerCase().replace(/ /g, '_').replace(/[^a-z0-9_]/g, '');
    const domain = prompt('Dominio (matematica, fisica, informatica...):', 'matematica') || 'generale';
    const description = prompt('Descrizione:', '') || '';
    try {
      const res = await fetch('/api/create_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: topicId, name, description, domain })
      });
      const data = await res.json();
      if (data.success) {
        const freshTopics = await fetchData();
        if (freshTopics) {
          const newTopic = freshTopics.find(t => t.id === topicId);
          if (newTopic) {
            setActiveTopicId(topicId);
            setSelectedNode({ type: 'topic', data: newTopic });
            setSelectedModule(null);
          }
        }
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleUpdateTopicParent = async (topic, newParentId) => {
    try {
      const res = await fetch('/api/update_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_id: topic.id, parent_id: newParentId || null })
      });
      const data = await res.json();
      if (data.success) {
        await fetchData();
        setSelectedNode({ type: 'topic', data: { ...topic, parent_id: newParentId || null } });
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleDeleteModule = async (mod, topicId) => {
    if (!confirm(`Eliminare definitivamente il sottoargomento "${mod.name}" e tutti i suoi file?`)) return;
    const parentTopic = topicsData.find(t => t.id === topicId);
    if (!parentTopic) return;
    try {
      const res = await fetch('/api/delete_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: mod.folder || `${parentTopic.folder}/${mod.number}_${mod.name}`.toLowerCase().replace(/ /g, '_') })
      });
      const data = await res.json();
      if (data.success) {
        const freshTopics = await fetchData();
        if (freshTopics) {
          setSelectedNode(null);
          setSelectedModule(null);
        }
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleDeleteTopic = async (topic) => {
    if (!confirm(`Eliminare definitivamente l'argomento "${topic.name}" e tutti i suoi sottoargomenti e file?`)) return;
    try {
      const res = await fetch('/api/delete_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_id: topic.id })
      });
      const data = await res.json();
      if (data.success) {
        const freshTopics = await fetchData();
        if (freshTopics) {
          setSelectedNode(null);
          setActiveTopicId(freshTopics.length > 0 ? freshTopics[0].id : null);
          setSelectedModule(null);
        }
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleRenameModule = async (mod, topicId) => {
    const newName = prompt('Nuovo nome per il sottoargomento:', mod.name);
    if (!newName || newName === mod.name) return;
    const parentTopic = topicsData.find(t => t.id === topicId);
    if (!parentTopic) return;
    try {
      const res = await fetch('/api/update_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          old_folder: mod.folder || `${parentTopic.folder}/${mod.number}_${mod.name}`.toLowerCase().replace(/ /g, '_'),
          number: mod.number,
          name: newName,
          description: mod.description || ''
        })
      });
      const result = await res.json();
      if (result.success) {
        const freshTopics = await fetchData();
        if (freshTopics) {
          const updatedTopic = freshTopics.find(t => t.id === topicId);
          if (updatedTopic) {
            const renamedMod = updatedTopic.modules?.find(m => m.number === mod.number);
            if (renamedMod) {
              setSelectedNode({ type: 'module', data: renamedMod, topicId });
              setSelectedModule(renamedMod.number);
            }
          }
        }
      } else {
        alert('Errore: ' + (result.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleDeleteFile = async (path) => {
    if (!confirm(`Eliminare definitivamente il file "${path.split('/').pop()}"?`)) return;
    try {
      const res = await fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      if (data.success) {
        await fetchData();
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const handleCreateFile = async (folderPath, fileType) => {
    const subdirs = {
      whitepaper: 'whitepapers',
      teoria: 'teoria',
      docs: 'docs',
      test: 'test',
      viz: 'viz'
    };
    const extensions = {
      whitepaper: '.md',
      teoria: '.md',
      test: '.py',
      viz: '.html',
      docs: '.md'
    };
    const subdir = subdirs[fileType] || fileType;
    const ext = extensions[fileType] || '.md';
    const filename = prompt(`Nome del nuovo file ${fileType} (senza estensione):`, `nuovo_${fileType}`);
    if (!filename) return;
    const fullPath = `${folderPath}/${subdir}/${filename}${ext}`;
    const template = fileType === 'test'
      ? `# ${filename}\n# Test script for Sigma\n\ndef run():\n    print('Running ${filename}...')\n\nif __name__ == '__main__':\n    run()\n`
      : `# ${filename}\n\nContenuto del file ${fileType}.\n`;
    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath, content: template })
      });
      const data = await res.json();
      if (data.success) {
        await fetchData(); // refresh
        if (onOpenFile) onOpenFile(fullPath);
      } else {
        alert('Errore: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  const renderTopicDetail = (topic) => {
    const modCount = (topic.modules || []).length;
    let totalFiles = 0;
    let filesHtml = '';
    if (topic.modules) {
      for (const mod of topic.modules) {
        for (const key of ['teoria', 'test', 'viz']) {
          const files = mod[key] || [];
          for (const f of files) {
            totalFiles++;
            filesHtml += `<div class="detail-file-item" onclick="${onOpenFile ? `window.__openFile('${escapeStr(f.path)}')` : ''}">
              <span class="icon">${key === 'teoria' ? '📖' : key === 'test' ? '🧪' : '📊'}</span>
              <span class="fname">${escapeStr(f.filename)}</span>
            </div>`;
          }
        }
        for (const f of [...(mod.docs || []), ...(mod.whitepapers || [])]) {
          totalFiles++;
          filesHtml += `<div class="detail-file-item" onclick="${onOpenFile ? `window.__openFile('${escapeStr(f.path)}')` : ''}">
            <span class="icon">📄</span>
            <span class="fname">${escapeStr(f.filename)}</span>
          </div>`;
        }
      }
    }

    const parentTopic = topic.parent_id ? topicsData.find(t => t.id === topic.parent_id) : null;
    const childTopics = topicsData.filter(t => t.parent_id === topic.id);

    return (
      <div className="detail-body">
        <div className="detail-header">
          <div className="detail-type">ARGOMENTO</div>
          <div className="detail-title" style={{ color: '#bc8cff' }}>{escapeStr(topic.name)}</div>
        </div>
        <div className="detail-desc">{escapeStr(topic.description)}</div>
        <div className="detail-meta">
          <span className="tag modules-tag">{modCount} moduli</span>
          <span className="tag">{totalFiles} file</span>
          <span className="tag">{escapeStr(topic.domain)}</span>
        </div>
        {topic.manifesto_ref && <div className="detail-meta manifesto-ref">📜 {escapeStr(topic.manifesto_ref)}</div>}
        {parentTopic && (
          <div className="detail-rel">
            <span className="detail-rel-label">ARGOMENTO PADRE</span>
            <span className="detail-rel-value">⬆ {escapeStr(parentTopic.name)}</span>
          </div>
        )}
        {childTopics.length > 0 && (
          <div className="detail-rel">
            <span className="detail-rel-label">ARGOMENTI FIGLI ({childTopics.length})</span>
            <div className="detail-rel-list">
              {childTopics.map(ct => <span key={ct.id} className="detail-rel-tag">{escapeStr(ct.name)}</span>)}
            </div>
          </div>
        )}
        {filesHtml && <div className="detail-files"><h4>FILE DEI MODULI</h4><div dangerouslySetInnerHTML={{ __html: filesHtml }} /></div>}
        
        {/* Parent selector */}
        {topicsData.length > 0 && (
          <div className="detail-parent-select" style={{ marginTop: '8px' }}>
            <div style={{ fontSize: '0.5rem', fontWeight: 600, color: '#5a5e72', letterSpacing: '1px', marginBottom: '4px' }}>ARGOMENTO PADRE</div>
            <select 
              value={topic.parent_id || ''} 
              onChange={e => handleUpdateTopicParent(topic, e.target.value)}
              style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', fontSize: '0.6rem', border: '1px solid #1e2030', background: '#0e1016', color: '#8b8fa3', fontFamily: 'inherit', outline: 'none' }}
            >
              <option value="">— Nessun padre —</option>
              {topicsData.filter(t => t.id !== topic.id).map(t => (
                <option key={t.id} value={t.id}>{escapeStr(t.name)}</option>
              ))}
            </select>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <button className="detail-action-btn" onClick={() => handleCreateTopic()}>
            🌐 Nuovo Argomento
          </button>
          <button className="detail-action-btn" onClick={() => handleCreateSubTopic(topic)}>
            ➕ Nuovo Sottoargomento
          </button>
          <button className="detail-action-btn" onClick={() => handleDeleteTopic(topic)} style={{ color: '#ff5555' }}>
            🗑️ Elimina Argomento
          </button>
        </div>
      </div>
    );
  };

  const renderModuleDetail = (mod, topicId) => {
    const renderFileList = (files, icon) => {
      if (!files || files.length === 0) return '';
      return files.map(f => (
        <div key={f.path} className="detail-file-item" onClick={() => onOpenFile && onOpenFile(f.path)}>
          <span className="icon">{icon}</span>
          <span className="fname">{escapeStr(f.filename)}</span>
        </div>
      ));
    };

    const parentTopic = topicId ? topicsData.find(t => t.id === topicId) : null;
    const totalFiles = (mod.docs || []).length + (mod.whitepapers || []).length
      + (mod.teoria || []).length + (mod.test || []).length + (mod.viz || []).length;

    const folderPath = mod.folder || (parentTopic ? `${parentTopic.folder}/${mod.number}_${mod.name}`.toLowerCase().replace(/ /g, '_') : '');

    return (
      <div className="detail-body">
        <div className="detail-header">
          <div className="detail-type">MODULO {mod.number}</div>
          <div className="detail-title" style={{ color: '#00d2ff' }}>{escapeStr(mod.name)}</div>
        </div>
        <div className="detail-desc">{escapeStr(mod.description)}</div>
        <div className="detail-meta">
          <span className="tag">{totalFiles} file</span>
          <span className="tag modules-tag">{escapeStr(mod.number)}</span>
        </div>
        {parentTopic && (
          <div className="detail-rel">
            <span className="detail-rel-label">ARGOMENTO PADRE</span>
            <span className="detail-rel-value" style={{ color: '#bc8cff' }}>⬆ {escapeStr(parentTopic.name)}</span>
          </div>
        )}
        {mod.teoria && mod.teoria.length > 0 && (
          <div className="detail-files"><h4>📖 TEORIA</h4>{renderFileList(mod.teoria, '📖')}</div>
        )}
        {mod.whitepapers && mod.whitepapers.length > 0 && (
          <div className="detail-files"><h4>📜 WHITEPAPERS</h4>{renderFileList(mod.whitepapers, '📜')}</div>
        )}
        {mod.docs && mod.docs.length > 0 && (
          <div className="detail-files"><h4>📄 DOCS</h4>{renderFileList(mod.docs, '📄')}</div>
        )}
        {mod.test && mod.test.length > 0 && (
          <div className="detail-files"><h4>🧪 TEST</h4>{renderFileList(mod.test, '🧪')}</div>
        )}
        {mod.viz && mod.viz.length > 0 && (
          <div className="detail-files"><h4>📊 VISUALIZZAZIONI</h4>{renderFileList(mod.viz, '📊')}</div>
        )}
        {totalFiles === 0 && <div className="detail-empty-files">Nessun file in questo modulo.</div>}
        
        {/* Rename & Action buttons */}
        <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <button className="detail-action-btn" onClick={() => handleRenameModule(mod, topicId)} style={{ color: '#d29922' }}>
            ✏️ Rinomina Sottoargomento
          </button>
          <button className="detail-action-btn" onClick={() => handleDeleteModule(mod, topicId)} style={{ color: '#ff5555' }}>
            🗑️ Elimina Sottoargomento
          </button>
          <div style={{ fontSize: '0.5rem', fontWeight: 600, color: '#5a5e72', letterSpacing: '1px', margin: '8px 0 4px' }}>CREA NUOVO FILE</div>
          {[
            { type: 'whitepaper', icon: '📜', label: 'Whitepaper' },
            { type: 'teoria', icon: '📖', label: 'Teoria' },
            { type: 'test', icon: '🧪', label: 'Test' },
            { type: 'viz', icon: '📊', label: 'Visualizzazione' },
            { type: 'docs', icon: '📄', label: 'Documento' },
          ].map(btn => (
            <button key={btn.type} className="detail-action-btn" onClick={() => handleCreateFile(folderPath, btn.type)}>
              {btn.icon} Nuovo {btn.label}
            </button>
          ))}
        </div>
      </div>
    );
  };

  // Set active topic when data loads
  useEffect(() => {
    if (topicsData.length > 0 && !activeTopicId) {
      setActiveTopicId(topicsData[0].id);
    }
  }, [topicsData, activeTopicId]);

  // Get current active topic
  const activeTopic = topicsData.find(t => t.id === activeTopicId);

  // Collect all files from all modules of a topic, grouped by type
  const getTopicFiles = (topic) => {
    const groups = {
      whitepapers: [],
      docs: [],
      teoria: [],
      test: [],
      viz: []
    };
    if (!topic || !topic.modules) return groups;
    for (const mod of topic.modules) {
      if (mod.whitepapers) mod.whitepapers.forEach(f => groups.whitepapers.push({ ...f, modNum: mod.number, modName: mod.name }));
      if (mod.docs) mod.docs.forEach(f => groups.docs.push({ ...f, modNum: mod.number, modName: mod.name }));
      if (mod.teoria) mod.teoria.forEach(f => groups.teoria.push({ ...f, modNum: mod.number, modName: mod.name }));
      if (mod.test) mod.test.forEach(f => groups.test.push({ ...f, modNum: mod.number, modName: mod.name }));
      if (mod.viz) mod.viz.forEach(f => groups.viz.push({ ...f, modNum: mod.number, modName: mod.name }));
    }
    return groups;
  };

  const iconMap = {
    matematica: '∑', fisica: 'Φ', informatica: '⚙', mathematics: '∑', physics: 'Φ', cs: '⚙'
  };
  const topicIcon = (domain) => iconMap[domain] || '🔬';

  // Reset module filter when topic tab changes
  const selectTopic = (topic) => {
    setActiveTopicId(topic.id);
    setSelectedModule(null);
    setSelectedNode({ type: 'topic', data: topic });
  };

  const columnDefs = [
    { key: 'whitepapers', icon: '📜', label: 'Whitepapers', color: '#ffd700', borderColor: '#ffd700' },
    { key: 'teoria', icon: '📖', label: 'Teoria', color: '#bc8cff', borderColor: 'rgba(188,140,255,0.2)' },
    { key: 'docs', icon: '📄', label: 'Docs', color: '#ffd700', borderColor: 'rgba(255,215,0,0.2)' },
    { key: 'test', icon: '🧪', label: 'Test', color: '#3fb950', borderColor: 'rgba(63,185,80,0.2)' },
    { key: 'viz', icon: '📊', label: 'Visualizzazioni', color: '#d29922', borderColor: 'rgba(210,153,34,0.2)' },
  ];

  // --- Loading / Error ---
  if (loading) {
    return (
      <div className="mappa-loading">
        <div className="spinner"></div>
        <div className="label">Caricamento bacheca…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mappa-error">
        <div className="error-icon">⚠️</div>
        <div className="error-msg">Errore di caricamento: {escapeStr(error)}<br />Assicurati che Sigma Server sia in esecuzione.</div>
        <button className="retry-btn" onClick={fetchData}>⟳ Riprova</button>
      </div>
    );
  }

  if (topicsData.length === 0) {
    return (
      <div className="mappa-loading" style={{ gap: 0, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Hero card */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(188,140,255,0.04) 0%, rgba(0,210,255,0.04) 100%)',
          border: '1px solid rgba(188,140,255,0.12)',
          borderRadius: '16px',
          padding: '48px 32px',
          maxWidth: '520px',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '20px',
          backdropFilter: 'blur(4px)',
          boxShadow: '0 0 60px rgba(188,140,255,0.03), inset 0 1px 0 rgba(255,255,255,0.02)',
          margin: 'auto'
        }}>
          {/* Icon */}
          <div style={{
            width: '72px',
            height: '72px',
            borderRadius: '20px',
            background: 'linear-gradient(135deg, rgba(188,140,255,0.15) 0%, rgba(0,210,255,0.1) 100%)',
            border: '1px solid rgba(188,140,255,0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.8rem',
            boxShadow: '0 8px 32px rgba(188,140,255,0.08)'
          }}>
            🧬
          </div>
          
          {/* Title */}
          <div style={{ textAlign: 'center' }}>
            <h2 style={{
              margin: 0,
              fontSize: '1.15rem',
              fontWeight: 700,
              color: '#e2e4eb',
              letterSpacing: '-0.02em',
              lineHeight: 1.3
            }}>
              Inizia la tua ricerca
            </h2>
            <p style={{
              margin: '8px 0 0 0',
              fontSize: '0.78rem',
              color: '#5a5e72',
              lineHeight: 1.6,
              maxWidth: '380px'
            }}>
              Crea il tuo primo argomento per organizzare moduli, teoria, test e visualizzazioni in una mappa interattiva.
            </p>
          </div>

          {/* CTA Button */}
          <button
            onClick={handleCreateTopic}
            style={{
              padding: '12px 28px',
              background: 'linear-gradient(135deg, #bc8cff 0%, #9b6fff 100%)',
              border: 'none',
              borderRadius: '10px',
              color: '#0e1016',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '0.8rem',
              fontFamily: 'inherit',
              letterSpacing: '0.01em',
              boxShadow: '0 4px 24px rgba(188,140,255,0.25)',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 8px 32px rgba(188,140,255,0.35)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 24px rgba(188,140,255,0.25)';
            }}
          >
            <span style={{ fontSize: '1rem' }}>+</span>
            Crea il primo argomento
          </button>

          {/* Hint */}
          <div style={{
            fontSize: '0.65rem',
            color: '#3d4050',
            textAlign: 'center',
            lineHeight: 1.5
          }}>
            Ogni argomento contiene moduli con <span style={{ color: '#bc8cff' }}>teoria</span>, <span style={{ color: '#3fb950' }}>test</span> e <span style={{ color: '#d29922' }}>visualizzazioni</span>
          </div>
        </div>
      </div>
    );
  }

  const topicFiles = activeTopic ? getTopicFiles(activeTopic) : null;

  return (
    <div className="mappa-argomenti">
      <style>{`
        .mappa-argomenti {
          display: flex;
          flex-direction: column;
          height: 100%;
          background: #0e1016;
          color: #e2e4eb;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 15px;
          overflow: hidden;
        }
        .mappa-argomenti ::-webkit-scrollbar { width: 3px; height: 3px; }
        .mappa-argomenti ::-webkit-scrollbar-track { background: transparent; }
        .mappa-argomenti ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
        .mappa-argomenti ::-webkit-scrollbar-thumb:hover { background: #00d2ff; }
        .mappa-loading, .mappa-error {
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          height: 100%; gap: 12px; color: #5a5e72; font-size: 0.75rem;
        }
        .spinner { width: 28px; height: 28px; border: 2px solid #1e2030; border-top-color: #bc8cff; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .retry-btn { padding: 6px 16px; background: #1e2030; border: 1px solid #2a2d3e; border-radius: 6px; color: #e2e4eb; cursor: pointer; font-size: 0.7rem; }
        .retry-btn:hover { background: #2a2d3e; }
        
        /* === TOP: graph + detail panel (35%) === */
        .mappa-top-section {
          height: 55%; display: flex; flex-shrink: 0;
          border-bottom: 1px solid #1e2030;
        }
        .mappa-graph-container {
          flex: 1; position: relative; overflow: hidden;
          min-width: 0;
          background: radial-gradient(circle at 30% 40%, rgba(188,140,255,0.02) 0%, transparent 60%);
        }
        .mappa-graph-svg { width: 100%; height: 100%; display: block; }
        .graph-link { stroke: rgba(255,255,255,0.08); stroke-width: 1.5; transition: opacity 0.2s; }
        .graph-link.parent-link { stroke: rgba(210,153,34,0.2); stroke-dasharray: 4,3; }
        .graph-link.highlight { stroke: rgba(255,255,255,0.25) !important; stroke-width: 2.5 !important; }
        .graph-link.parent-link.highlight { stroke: rgba(210,153,34,0.5) !important; }
        .graph-node { cursor: pointer; transition: opacity 0.2s; }
        .mappa-zoom-controls {
          position: absolute; bottom: 12px; left: 12px; display: flex; gap: 6px; align-items: center;
        }
        .mappa-zoom-controls button {
          background: rgba(17,19,27,0.92); border: 1px solid #1e2030; border-radius: 8px;
          color: #8b8fa3; cursor: pointer; font-family: inherit;
          transition: all 0.15s; backdrop-filter: blur(8px);
          display: flex; align-items: center; justify-content: center;
        }
        .mappa-zoom-controls button:hover { background: #1e2030; color: #e2e4eb; border-color: #2a2d3e; }
        .mappa-zoom-controls .btn-explore { padding: 7px 14px; font-size: 0.7rem; font-weight: 600; gap: 6px; border-color: rgba(63,185,80,0.25); color: #3fb950; }
        .mappa-zoom-controls .btn-explore:hover { background: rgba(63,185,80,0.12); border-color: rgba(63,185,80,0.4); }
        .mappa-zoom-controls .btn-explore.active { background: rgba(255,85,85,0.1); border-color: rgba(255,85,85,0.25); color: #ff5555; }
        .mappa-zoom-controls .btn-update { padding: 7px 14px; font-size: 0.7rem; font-weight: 600; border-color: rgba(0,210,255,0.25); color: #00d2ff; display: flex; align-items: center; gap: 6px; }
        .mappa-zoom-controls .btn-update:hover { background: rgba(0,210,255,0.12); border-color: rgba(0,210,255,0.4); }
        .mappa-zoom-controls .btn-new-topic { padding: 7px 14px; font-size: 0.7rem; font-weight: 600; border-color: rgba(188,140,255,0.25); color: #bc8cff; display: flex; align-items: center; gap: 6px; }
        .mappa-zoom-controls .btn-new-topic:hover { background: rgba(188,140,255,0.12); border-color: rgba(188,140,255,0.4); }

        /* Detail Panel (side panel in top section) */
        .mappa-detail-panel {
          width: 350px; border-left: 1px solid #1e2030; overflow-y: auto;
          padding: 10px 14px; flex-shrink: 0; background: #11131b;
        }
        .detail-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; color: #5a5e72; font-size: 0.65rem; text-align: center; }
        .detail-empty-icon { font-size: 1.2rem; }
        .detail-body { flex: 1; display: flex; flex-direction: column; gap: 0; }
        .detail-header { margin-bottom: 6px; }
        .detail-type { font-size: 0.45rem; font-weight: 600; color: #5a5e72; letter-spacing: 1px; margin-bottom: 1px; }
        .detail-title { font-size: 0.8rem; font-weight: 700; line-height: 1.2; }
        .detail-desc { font-size: 0.85rem; color: #8b8fa3; margin-bottom: 6px; line-height: 1.4; }
        .detail-meta { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }
        .detail-meta .tag { font-size: 0.45rem; background: #1e2030; padding: 1px 6px; border-radius: 4px; color: #8b8fa3; }
        .detail-meta .tag.modules-tag { color: #00d2ff; background: rgba(0,210,255,0.08); }
        .detail-meta.manifesto-ref { font-size: 0.5rem; color: #5a5e72; }
        .detail-rel { font-size: 0.55rem; margin-bottom: 4px; }
        .detail-rel-label { color: #5a5e72; font-size: 0.45rem; display: block; margin-bottom: 1px; }
        .detail-rel-value { color: #8b8fa3; }
        .detail-rel-list { display: flex; gap: 3px; flex-wrap: wrap; margin-top: 2px; }
        .detail-rel-tag { font-size: 0.45rem; background: rgba(188,140,255,0.08); border: 1px solid rgba(188,140,255,0.15); padding: 1px 5px; border-radius: 3px; color: #bc8cff; }
        .detail-files { margin-top: 2px; }
        .detail-files h4 { font-size: 0.5rem; font-weight: 600; color: #5a5e72; letter-spacing: 0.5px; margin-bottom: 2px; border-bottom: 1px solid #1e2030; padding-bottom: 2px; }
        .detail-file-item { display: flex; align-items: center; gap: 4px; padding: 3px 6px; cursor: pointer; border-radius: 4px; transition: background 0.1s; font-size: 0.75rem; }
        .detail-file-item:hover { background: rgba(255,255,255,0.05); }
        .detail-file-item .icon { flex-shrink: 0; font-size: 0.6rem; }
        .detail-file-item .fname { color: #8b8fa3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .detail-file-item .fname:hover { color: #e2e4eb; }
        .detail-action-btn {
          width: 100%; padding: 8px 12px; border-radius: 6px; font-size: 0.65rem;
          cursor: pointer; border: 1px solid #1e2030; background: transparent;
          color: #8b8fa3; font-family: inherit; transition: all 0.12s;
          display: flex; align-items: center; gap: 6px;
        }
        .detail-action-btn:hover { background: rgba(0,210,255,0.06); color: #00d2ff; border-color: rgba(0,210,255,0.2); }

        /* === BOTTOM: tab bar + columns (65%) === */
        .mappa-bottom-section {
          flex: 1; display: flex; flex-direction: column; min-height: 0;
        }

        /* === MODULE FILTER BAR === */
        .module-filter-bar {
          display: flex; gap: 4px; padding: 6px 24px; align-items: center;
          background: #0e1016; border-bottom: 1px solid #1e2030; flex-shrink: 0; overflow-x: auto;
        }
        .module-filter-bar::-webkit-scrollbar { height: 2px; }
        .module-filter-bar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); }
        .mfb-label {
          font-size: 0.6rem; color: #5a5e72; white-space: nowrap; margin-right: 4px; font-weight: 500;
        }
        .mfb-btn {
          padding: 4px 10px; border-radius: 6px; font-size: 0.6rem; cursor: pointer;
          border: 1px solid #1e2030; background: transparent; color: #5a5e72;
          font-family: inherit; transition: all 0.12s; white-space: nowrap;
        }
        .mfb-btn:hover { color: #8b8fa3; border-color: #2a2d3e; }
        .mfb-btn.active { color: #00d2ff; border-color: rgba(0,210,255,0.3); background: rgba(0,210,255,0.08); }

        /* === TOPIC TAB BAR === */
        .topic-tab-bar {
          display: flex; gap: 2px; padding: 0 24px; background: #11131b;
          border-bottom: 1px solid #1e2030; flex-shrink: 0; overflow-x: auto; flex-wrap: nowrap;
        }
        .topic-tab-bar::-webkit-scrollbar { height: 2px; }
        .topic-tab-bar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 2px; }
        .topic-tab {
          display: flex; align-items: center; gap: 8px; padding: 10px 16px;
          font-size: 0.7rem; cursor: pointer; border-bottom: 2px solid transparent;
          color: #5a5e72; white-space: nowrap; transition: all 0.15s;
          font-family: inherit; background: transparent; border-top: none; border-left: none; border-right: none;
        }
        .topic-tab:hover { color: #8b8fa3; background: rgba(255,255,255,0.015); }
        .topic-tab.active { color: #e2e4eb; border-bottom-color: #bc8cff; background: rgba(188,140,255,0.05); }
        .topic-tab .tab-icon { width: 22px; height: 22px; background: rgba(188,140,255,0.08); border: 1px solid rgba(188,140,255,0.15); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; flex-shrink: 0; }
        .topic-tab .tab-count { font-size: 0.5rem; background: #1e2030; padding: 1px 6px; border-radius: 4px; color: #5a5e72; }
        .topic-tab.active .tab-count { background: rgba(188,140,255,0.08); color: #bc8cff; }

        /* === FILE COLUMNS === */
        .file-columns-area {
          flex: 1; overflow-y: auto; padding: 18px 24px; display: flex; gap: 16px;
          border-top: 1px solid #1e2030;
        }
        .file-column {
          flex: 1; min-width: 200px; display: flex; flex-direction: column;
          background: #11131b; border: 1px solid #1e2030; border-radius: 8px; overflow: hidden;
        }
        .file-column-header {
          padding: 10px 12px; font-size: 0.6rem; font-weight: 600; letter-spacing: 1px;
          border-bottom: 1px solid #1e2030; flex-shrink: 0; display: flex; align-items: center; gap: 6px;
        }
        .file-column-list { padding: 6px 8px; overflow-y: auto; flex: 1; }
        .file-column .empty-col-hint { font-size: 0.55rem; color: #5a5e72; text-align: center; padding: 16px 8px; }

        .col-file-item {
          display: flex; align-items: center; gap: 6px; padding: 5px 8px;
          border-radius: 6px; cursor: pointer; transition: all 0.12s; font-size: 0.6rem;
          border-left: 2px solid transparent; margin-bottom: 2px;
        }
        .col-file-item:hover { background: rgba(255,255,255,0.04); transform: translateX(2px); }
        .col-file-item .col-file-icon { flex-shrink: 0; font-size: 0.6rem; }
        .col-file-item .col-file-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #8b8fa3; }
        .col-file-item .col-file-name:hover { color: #e2e4eb; }
        .col-file-item .col-file-del {
          opacity: 0; font-size: 0.5rem; cursor: pointer; padding: 1px 3px; border: none; background: none;
          color: #ff5555; transition: opacity 0.12s; border-radius: 2px;
        }
        .col-file-item:hover .col-file-del { opacity: 0.6; }
        .col-file-item .col-file-del:hover { opacity: 1 !important; background: rgba(255,85,85,0.1); }
        .col-file-item .col-mod-badge {
          font-size: 0.45rem; background: #1e2030; padding: 1px 5px; border-radius: 3px;
          color: #5a5e72; flex-shrink: 0; font-weight: 500;
        }
      `}</style>
      
      {/* TOP SECTION — graph + detail panel */}
      <div className="mappa-top-section">
        <div ref={containerRef} className="mappa-graph-container" style={{ display: 'flex' }}>
          <svg ref={svgRef} className="mappa-graph-svg" style={{ flex: 1 }}></svg>
          <div className="mappa-zoom-controls">
            <button className={`btn-explore ${showDocs ? 'active' : ''}`} onClick={() => {
              setShowDocs(prev => {
                const next = !prev;
                localStorage.setItem('sigma_mappa_explore', String(next));
                return next;
              });
            }} title={showDocs ? 'Collidi' : 'Esplora'}>
              {showDocs ? '✕ Collidi' : '🔍 Esplora'}
            </button>
            <button className="btn-update" onClick={fetchData} title="Aggiorna dati e grafico">
              🔄 Aggiorna
            </button>
            <button className="btn-new-topic" onClick={handleCreateTopic} title="Crea nuovo argomento">
              🌐 Nuovo Argomento
            </button>
          </div>
        </div>
        <div className="mappa-detail-panel">
          {renderDetail()}
        </div>
      </div>

      {/* BOTTOM SECTION — tab bar + file columns (65%) */}
      <div className="mappa-bottom-section">
        {/* Topic Tab Bar */}
        <div className="topic-tab-bar">
          {topicsData.map(topic => (
            <button key={topic.id} className={`topic-tab ${activeTopicId === topic.id ? 'active' : ''}`} onClick={() => selectTopic(topic)}>
              <span className="tab-icon">{topicIcon(topic.domain)}</span>
              <span>{escapeStr(topic.name)}</span>
              <span className="tab-count">{(topic.modules || []).length}</span>
            </button>
          ))}
        </div>

        {/* Module Filter Bar */}
        {activeTopic && activeTopic.modules && activeTopic.modules.length > 1 && (
          <div className="module-filter-bar">
            <span className="mfb-label">Sottoargomento:</span>
            <button className={`mfb-btn ${selectedModule === null ? 'active' : ''}`} onClick={() => setSelectedModule(null)}>
              Tutti
            </button>
            {activeTopic.modules.map(mod => (
              <button key={mod.number} className={`mfb-btn ${selectedModule === mod.number ? 'active' : ''}`} onClick={() => setSelectedModule(mod.number)}>
                M{mod.number} — {escapeStr(mod.name)}
              </button>
            ))}
          </div>
        )}

        {/* File Columns — filtered by selectedModule */}
        <div className="file-columns-area">
          {topicFiles && columnDefs.map(col => {
            let files = topicFiles[col.key] || [];
            // Filter by selected module
            if (selectedModule) {
              files = files.filter(f => f.modNum === selectedModule);
            }
            return (
              <div key={col.key} className="file-column">
                <div className="file-column-header" style={{ color: col.color }}>
                  <span>{col.icon}</span> {col.label}
                  <span style={{ marginLeft: 'auto', fontSize: '0.5rem', opacity: 0.6 }}>{files.length}</span>
                </div>
                <div className="file-column-list">
                  {files.length === 0 && <div className="empty-col-hint">Nessun file</div>}
                  {files.map((f, idx) => (
                    <div key={f.path || idx} className="col-file-item" style={{ borderLeftColor: col.borderColor }}>
                      <span className="col-file-icon">{col.icon}</span>
                      <span className="col-file-name" onClick={() => onOpenFile && onOpenFile(f.path)}>{escapeStr(f.filename)}</span>
                      <span className="col-file-del" onClick={(e) => { e.stopPropagation(); handleDeleteFile(f.path); }} title="Elimina file">🗑️</span>
                      <span className="col-mod-badge" style={{ cursor: 'pointer', background: selectedModule === f.modNum ? 'rgba(0,210,255,0.15)' : '#1e2030', color: selectedModule === f.modNum ? '#00d2ff' : '#5a5e72' }}
                        onClick={(e) => { e.stopPropagation(); setSelectedModule(selectedModule === f.modNum ? null : f.modNum); }}
                        title={selectedModule === f.modNum ? 'Mostra tutti' : `Filtra per M${f.modNum}`}>
                        {f.modNum}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {topicsData.length === 0 && (
            <div className="mappa-loading" style={{ flex: 1 }}>
              <div className="label">Nessun argomento disponibile.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
