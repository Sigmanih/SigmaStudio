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
  docs: { stroke: '#58a6ff', fill: 'rgba(88,166,255,0.2)' },
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
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedModules, setExpandedModules] = useState({});
  const [expandedCategories, setExpandedCategories] = useState({});
  const [expandedTopicsSection, setExpandedTopicsSection] = useState(true);

  // AI Overlay States
  const [showAiOverlay, setShowAiOverlay] = useState(false);
  const [overlayNode, setOverlayNode] = useState(null); // the D3 node data
  const [overlayPos, setOverlayPos] = useState({ x: 0, y: 0 }); // pixel coordinates
  const [aiModels, setAiModels] = useState([]);
  const [aiOverlayLoading, setAiOverlayLoading] = useState(false);

  // Form states for the AI Action Overlay
  const [newFileName, setNewFileName] = useState('');
  const [newFileCategory, setNewFileCategory] = useState('teoria');
  const [isAiMode, setIsAiMode] = useState(false);
  const [selectedAiModel, setSelectedAiModel] = useState('');
  const [selectedAiRole, setSelectedAiRole] = useState('code_architect');
  const [aiPromptText, setAiPromptText] = useState('');
  const [aiError, setAiError] = useState('');

  // File Overlay Specific States
  const [moveTargetTopicId, setMoveTargetTopicId] = useState('');
  const [moveTargetModuleNum, setMoveTargetModuleNum] = useState('');
  const [moveTargetCategory, setMoveTargetCategory] = useState('teoria');
  const [existingFileContent, setExistingFileContent] = useState('');
  const [fileTab, setFileTab] = useState('ai_edit'); // 'ai_edit' | 'move' | 'delete'

  // States for file upload integration
  const [creationTab, setCreationTab] = useState('standard'); // 'standard' | 'ai' | 'upload'
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Auto clean upload states when overlay is closed
  useEffect(() => {
    if (!showAiOverlay) {
      setCreationTab('standard');
      setSelectedUploadFile(null);
      setIsDragActive(false);
      setAiError('');
    }
  }, [showAiOverlay]);


  useEffect(() => {
    if (showAiOverlay && overlayNode && overlayNode.type === 'doc') {
      setFileTab('ai_edit');
      setAiError('');
      setAiPromptText('');
      
      // Fetch file content
      const fetchContent = async () => {
        try {
          const res = await fetch(`/api/get_file?path=${encodeURIComponent(overlayNode.filePath)}`);
          const data = await res.json();
          if (data.success) {
            setExistingFileContent(data.content || '');
          }
        } catch (err) {
          console.error('Error fetching file content:', err);
        }
      };
      fetchContent();

      // Initialize move dropdown targets
      if (topicsData.length > 0) {
        setMoveTargetTopicId(topicsData[0].id);
        const mods = topicsData[0].modules || [];
        if (mods.length > 0) {
          setMoveTargetModuleNum(mods[0].number);
        } else {
          setMoveTargetModuleNum('');
        }
      }
      setMoveTargetCategory(overlayNode.docType || 'teoria');
    } else {
      setExistingFileContent('');
    }
  }, [showAiOverlay, overlayNode]);

  // When move target topic changes, update module select target
  useEffect(() => {
    if (moveTargetTopicId) {
      const topic = topicsData.find(t => t.id === moveTargetTopicId);
      const mods = topic?.modules || [];
      if (mods.length > 0) {
        setMoveTargetModuleNum(mods[0].number);
      } else {
        setMoveTargetModuleNum('');
      }
    }
  }, [moveTargetTopicId, topicsData]);

  // Draggable Card States & Handlers
  const [isDraggingOverlay, setIsDraggingOverlay] = useState(false);
  const [overlayDragStart, setOverlayDragStart] = useState({ x: 0, y: 0 });

  const handleOverlayHeaderMouseDown = (e) => {
    if (e.button !== 0) return; // only left click
    setIsDraggingOverlay(true);
    setOverlayDragStart({
      x: e.clientX - overlayPos.x,
      y: e.clientY - overlayPos.y
    });
    e.preventDefault();
  };

  useEffect(() => {
    if (!isDraggingOverlay) return;

    const handleMouseMove = (e) => {
      setOverlayPos({
        x: e.clientX - overlayDragStart.x,
        y: e.clientY - overlayDragStart.y
      });
    };

    const handleMouseUp = () => {
      setIsDraggingOverlay(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingOverlay, overlayDragStart]);

  // Event handlers for drag & drop file upload
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedUploadFile(file);
      const nameParts = file.name.split('.');
      if (nameParts.length > 1) {
        nameParts.pop();
      }
      setNewFileName(nameParts.join('.'));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedUploadFile(file);
      const nameParts = file.name.split('.');
      if (nameParts.length > 1) {
        nameParts.pop();
      }
      setNewFileName(nameParts.join('.'));
    }
  };

  useEffect(() => {
    if (aiModels.length > 0 && !selectedAiModel) {
      setSelectedAiModel(aiModels[0].name);
    }
  }, [aiModels, selectedAiModel]);

  useEffect(() => {
    const fetchAiModels = async () => {
      try {
        const res = await fetch('/api/ollama_models');
        const data = await res.json();
        if (data.success && data.models) {
          setAiModels(data.models);
        }
      } catch (err) {
        console.error('Error fetching AI models:', err);
      }
    };
    fetchAiModels();
  }, []);

  // D3 refs
  const simulationRef = useRef(null);
  const zoomRef = useRef(null);
  const linksRef = useRef([]);

  const [agentColors, setAgentColors] = useState({});
  const [d3, setD3] = useState(null);

  useEffect(() => {
    import('d3').then(module => {
      setD3(module);
      window.d3 = module;
    });
  }, []);

  useEffect(() => {
    if (selectedNode && selectedNode.type === 'module') {
      setExpandedModules(prev => ({ ...prev, [selectedNode.data.number]: true }));
    }
  }, [selectedNode]);

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

      // Reload agent colors dynamically
      try {
        const colorsRes = await fetch('/api/agents/colors');
        if (colorsRes.ok) {
          const colorsData = await colorsRes.json();
          if (colorsData.success) {
            setAgentColors(colorsData.colors);
          }
        }
      } catch (e) {}

      return data.topics;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Update dimensions on resize/load
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
    handleResize();
    const timer = setTimeout(handleResize, 100);
    window.addEventListener('resize', handleResize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
    };
  }, [loading, d3]);

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

    // Calculate depths of topics based on parent_id relations
    const depths = {};
    const getTopicDepth = (tId) => {
      if (depths[tId] !== undefined) return depths[tId];
      const t = topicsData.find(x => x.id === tId);
      if (!t || !t.parent_id) {
        depths[tId] = 0;
        return 0;
      }
      depths[tId] = 0; // fallback to avoid infinite recursion
      const parentDepth = getTopicDepth(t.parent_id);
      depths[tId] = parentDepth + 1;
      return depths[tId];
    };
    topicsData.forEach(t => getTopicDepth(t.id));

    // Map children for parent topics to compute sibling index and total siblings
    const parentChildrenMap = {};
    for (const topic of topicsData) {
      if (topic.parent_id) {
        if (!parentChildrenMap[topic.parent_id]) {
          parentChildrenMap[topic.parent_id] = [];
        }
        parentChildrenMap[topic.parent_id].push(topic.id);
      }
    }

    for (const topic of topicsData) {
      const topicId = 'topic-' + topic.id;
      const topicDepth = depths[topic.id] || 0;
      
      let childTopicIndex = 0;
      let totalChildTopics = 0;
      if (topic.parent_id && parentChildrenMap[topic.parent_id]) {
        childTopicIndex = parentChildrenMap[topic.parent_id].indexOf(topic.id);
        totalChildTopics = parentChildrenMap[topic.parent_id].length;
      }

      nodes.push({
        id: topicId,
        label: topic.name,
        type: 'topic',
        data: topic,
        depth: topicDepth,
        parentTopicId: topic.parent_id ? 'topic-' + topic.parent_id : null,
        childTopicIndex,
        totalChildTopics,
        r: 22
      });
      nodeMap[topicId] = true;

      if (topic.modules) {
        let modIndex = 0;
        const totalMods = topic.modules.length;
        for (const mod of topic.modules) {
          const modId = 'mod-' + topic.id + '-' + mod.number;
          nodes.push({
            id: modId,
            label: mod.name,
            type: 'module',
            data: mod,
            topicId: topic.id,
            depth: topicDepth + 1,
            modIndex,
            totalMods,
            r: 16
          });
          nodeMap[modId] = true;
          links.push({ source: topicId, target: modId });

          // Optionally add document nodes linked to this module
          if (showDocs) {
            let totalDocs = 0;
            for (const docType of ['teoria', 'test', 'viz', 'docs', 'whitepapers']) {
              totalDocs += (mod[docType] || []).length;
            }

            let docIndex = 0;
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
                  depth: topicDepth + 2,
                  docIndex,
                  totalDocs,
                  r: 6
                });
                nodeMap[docId] = true;
                links.push({ source: modId, target: docId });
                docIndex++;
              }
            }
          }
          modIndex++;
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
    if (!d3 || !svgRef.current || topicsData.length === 0) return;
    // Guard against invalid dimensions (NaN/0)
    const width = dimensions.width;
    const height = dimensions.height;
    if (!width || !height || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.on('click', () => {
      setShowAiOverlay(false);
    });

    const graphData = buildGraphData();
    const { nodes, links } = graphData;
    if (nodes.length === 0) return;
    linksRef.current = links;

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
          setSelectedNode({ type: 'doc', data: d });
        } else if (d.type === 'topic') {
          setSelectedNode({ type: 'topic', data: d.data });
          setActiveTopicId(d.data.id);
          setSelectedModule(null);
        } else {
          setSelectedNode({ type: 'module', data: d.data, topicId: d.topicId });
          setActiveTopicId(d.topicId);
          setSelectedModule(d.data.number);
        }
        if (containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          setOverlayPos({ x: event.clientX - rect.left + 15, y: event.clientY - rect.top + 15 });
        }
        setOverlayNode(d);
        setShowAiOverlay(true);
      })
      .on('contextmenu', (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        if (d.type === 'doc') {
          setSelectedNode({ type: 'doc', data: d });
        } else if (d.type === 'topic') {
          setSelectedNode({ type: 'topic', data: d.data });
          setActiveTopicId(d.data.id);
          setSelectedModule(null);
        } else {
          setSelectedNode({ type: 'module', data: d.data, topicId: d.topicId });
          setActiveTopicId(d.topicId);
          setSelectedModule(d.data.number);
        }
        if (containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          setOverlayPos({ x: event.clientX - rect.left + 15, y: event.clientY - rect.top + 15 });
        }
        setOverlayNode(d);
        setShowAiOverlay(true);
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
      .attr('dy', d => d.r + 16)
      .attr('text-anchor', 'middle')
      .attr('fill', '#8b8fa3')
      .attr('font-size', d => d.type === 'topic' ? '15px' : (d.type === 'module' ? '13px' : '11px'))
      .attr('font-weight', d => d.type === 'topic' ? '700' : '500')
      .attr('pointer-events', 'none')
      .text(d => d.label.length > 30 ? d.label.slice(0, 28) + '…' : d.label);

    // Simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(120).strength(0.5))
      .force('charge', d3.forceManyBody().strength(d => d.type === 'topic' ? -1200 : -600))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force('collision', d3.forceCollide().radius(d => {
        if (d.type === 'topic') return d.r + 90;
        if (d.type === 'module') return d.r + 65;
        return d.r + 35;
      }).strength(0.85))
      .on('tick', () => {
        // Enforce hierarchical tree structure
        nodes.forEach(d => {
          if (d.type === 'topic') {
            if (d.parentTopicId) {
              const parentNode = nodes.find(n => n.id === d.parentTopicId);
              if (parentNode) {
                const branchLength = 220;
                let angle = Math.PI / 2; // default straight down
                if (d.totalChildTopics > 1) {
                  // Symmetrical fan spread (45 to 135 deg)
                  angle = 0.78 + (d.childTopicIndex / (d.totalChildTopics - 1)) * 1.57;
                }
                const targetX = parentNode.x + Math.cos(angle) * branchLength;
                const targetY = parentNode.y + Math.sin(angle) * branchLength;
                d.x += (targetX - d.x) * 0.15;
                d.y += (targetY - d.y) * 0.15;
              }
            } else {
              // Root topics: place them near the top-center
              const targetY = 100;
              d.y += (targetY - d.y) * 0.1;
            }
          } else if (d.type === 'module') {
            // Find parent topic node
            const parentNode = nodes.find(n => n.id === 'topic-' + d.topicId);
            if (parentNode) {
              const branchLength = 160;
              let angle = Math.PI / 2;
              if (d.totalMods > 1) {
                // Symmetrical fan spread (50 to 130 deg)
                angle = 0.87 + (d.modIndex / (d.totalMods - 1)) * 1.4;
              }
              const targetX = parentNode.x + Math.cos(angle) * branchLength;
              const targetY = parentNode.y + Math.sin(angle) * branchLength;
              d.x += (targetX - d.x) * 0.2;
              d.y += (targetY - d.y) * 0.2;
            }
          } else if (d.type === 'doc') {
            // Find parent module node
            const parentNode = nodes.find(n => n.id === d.parentModId);
            if (parentNode) {
              const branchLength = 120; // docs further away
              let angle = Math.PI / 2;
              if (d.totalDocs > 1) {
                // Symmetrical fan spread (35 to 145 deg)
                angle = 0.61 + (d.docIndex / (d.totalDocs - 1)) * 1.92;
              }
              const targetX = parentNode.x + Math.cos(angle) * branchLength;
              const targetY = parentNode.y + Math.sin(angle) * branchLength;
              d.x += (targetX - d.x) * 0.25;
              d.y += (targetY - d.y) * 0.25;
            }
          }
        });

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
  }, [d3, topicsData, dimensions, buildGraphData]);

  // Update node visuals on selection change without restarting simulation
  useEffect(() => {
    if (!d3 || !svgRef.current || topicsData.length === 0) return;
    const svg = d3.select(svgRef.current);
    // Update node fills/strokes
    svg.selectAll('.graph-node circle')
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
    // Update node class
    svg.selectAll('.graph-node')
      .attr('class', n => 'graph-node' + (selectedNode && n.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number) ? ' selected' : ''));
  }, [d3, selectedNode, topicsData]);

  const zoomIn = () => {
    if (svgRef.current && zoomRef.current && d3) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.3);
    }
  };
  const zoomOut = () => {
    if (svgRef.current && zoomRef.current && d3) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.7);
    }
  };
  const resetZoom = () => {
    if (svgRef.current && zoomRef.current && d3) {
      const initialScale = Math.min(dimensions.width, dimensions.height) / 600;
      d3.select(svgRef.current).transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity.scale(initialScale));
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

  const handleOverlayEditFile = async (e) => {
    if (e) e.preventDefault();
    if (!aiPromptText.trim()) {
      setAiError('Inserisci le istruzioni di modifica');
      return;
    }
    setAiOverlayLoading(true);
    setAiError('');

    try {
      const res = await fetch('/api/ai/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'edit_file',
          path: overlayNode.filePath,
          model: selectedAiModel,
          role: selectedAiRole,
          prompt: aiPromptText,
          existing_content: existingFileContent
        })
      });
      const data = await res.json();
      if (data.success) {
        setAiPromptText('');
        setShowAiOverlay(false);
        await fetchData();
        if (onOpenFile) onOpenFile(overlayNode.filePath);
      } else {
        setAiError(data.error || 'Errore modifica AI');
      }
    } catch (err) {
      setAiError('Errore di rete: ' + err.message);
    } finally {
      setAiOverlayLoading(false);
    }
  };

  const handleOverlayMoveFile = async (e) => {
    if (e) e.preventDefault();
    if (!moveTargetTopicId) {
      setAiError('Seleziona un argomento di destinazione');
      return;
    }

    setAiOverlayLoading(true);
    setAiError('');

    try {
      const targetTopic = topicsData.find(t => t.id === moveTargetTopicId);
      if (!targetTopic) {
        setAiError('Argomento di destinazione non trovato');
        setAiOverlayLoading(false);
        return;
      }

      let targetFolder = targetTopic.folder;
      if (moveTargetModuleNum) {
        const targetModule = targetTopic.modules?.find(m => m.number === Number(moveTargetModuleNum));
        if (targetModule) {
          targetFolder = targetModule.folder || `${targetTopic.folder}/${targetModule.number}_${targetModule.name}`.toLowerCase().replace(/ /g, '_');
        }
      }

      const subdirs = {
        whitepaper: 'whitepapers',
        teoria: 'teoria',
        docs: 'docs',
        test: 'test',
        viz: 'viz',
        whitepapers: 'whitepapers'
      };
      
      const subdir = subdirs[moveTargetCategory] || moveTargetCategory;
      const filename = overlayNode.label; // e.g. "WHITEPAPER_Collatz.md"
      
      const newPath = `${targetFolder}/${subdir}/${filename}`;

      const res = await fetch('/api/rename_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          old_path: overlayNode.filePath,
          new_path: newPath
        })
      });

      const data = await res.json();
      if (data.success) {
        setShowAiOverlay(false);
        await fetchData();
        if (onOpenFile) onOpenFile(newPath);
      } else {
        setAiError(data.error || 'Errore spostamento file');
      }
    } catch (err) {
      setAiError('Errore di rete: ' + err.message);
    } finally {
      setAiOverlayLoading(false);
    }
  };

  const handleOverlayDeleteFile = async (e) => {
    if (e) e.preventDefault();
    const confirmed = window.confirm(`Sei sicuro di voler eliminare definitivamente il file: ${overlayNode.label}?`);
    if (!confirmed) return;

    setAiOverlayLoading(true);
    setAiError('');

    try {
      const res = await fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: overlayNode.filePath })
      });
      const data = await res.json();
      if (data.success) {
        setShowAiOverlay(false);
        await fetchData();
      } else {
        setAiError(data.error || 'Errore eliminazione file');
      }
    } catch (err) {
      setAiError('Errore di rete: ' + err.message);
    } finally {
      setAiOverlayLoading(false);
    }
  };

  const handleOverlayCreateFile = async (e) => {
    if (e) e.preventDefault();
    
    // Resolve folder path
    let baseFolder = '';
    const activeTopic = topicsData.find(t => t.id === activeTopicId);
    if (overlayNode.type === 'topic') {
      baseFolder = overlayNode.data.folder || (activeTopic ? activeTopic.folder : '');
    } else if (overlayNode.type === 'module') {
      if (activeTopic) {
        baseFolder = overlayNode.data.folder || `${activeTopic.folder}/${overlayNode.data.number}_${overlayNode.data.name}`.toLowerCase().replace(/ /g, '_');
      }
    }
    
    if (!baseFolder) {
      setAiError('Cartella di destinazione non trovata');
      return;
    }
    
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
    
    const subdir = subdirs[newFileCategory] || newFileCategory;
    const ext = extensions[newFileCategory] || '.md';
    
    let sanitizedName = newFileName.trim();
    
    // UPLOAD MODE HANDLER
    if (creationTab === 'upload') {
      if (!selectedUploadFile) {
        setAiError('Seleziona o trascina un file prima di caricarlo');
        return;
      }
      if (!sanitizedName) {
        setAiError('Inserisci un nome file');
        return;
      }
      
      setAiOverlayLoading(true);
      setAiError('');
      
      try {
        // Keep original extension if not manually typed by user
        const origName = selectedUploadFile.name;
        const lastDot = origName.lastIndexOf('.');
        const origExt = lastDot !== -1 ? origName.substring(lastDot) : '';
        
        let finalName = sanitizedName;
        if (!finalName.toLowerCase().endsWith(origExt.toLowerCase())) {
          finalName = finalName + origExt;
        }
        
        if (newFileCategory === 'whitepaper' && !finalName.toUpperCase().startsWith('WHITEPAPER_')) {
          finalName = 'WHITEPAPER_' + finalName;
        }
        
        const fullPath = `${baseFolder}/${subdir}/${finalName}`;
        
        const formData = new FormData();
        formData.append('file', selectedUploadFile, finalName);
        formData.append('folder', baseFolder);
        formData.append('type', newFileCategory);
        
        const res = await fetch('/api/upload_file', {
          method: 'POST',
          body: formData
        });
        
        const data = await res.json();
        if (data.success) {
          setNewFileName('');
          setSelectedUploadFile(null);
          setShowAiOverlay(false);
          await fetchData();
          if (onOpenFile) onOpenFile(fullPath);
        } else {
          setAiError(data.error || 'Errore durante il caricamento');
        }
      } catch (err) {
        setAiError('Errore di rete: ' + err.message);
      } finally {
        setAiOverlayLoading(false);
      }
      return;
    }
    
    // STANDARD / AI CREATE MODES
    if (!sanitizedName) {
      setAiError('Inserisci un nome file');
      return;
    }
    
    if (newFileCategory === 'whitepaper' && !sanitizedName.toUpperCase().startsWith('WHITEPAPER_')) {
      sanitizedName = 'WHITEPAPER_' + sanitizedName;
    }
    
    const fullPath = `${baseFolder}/${subdir}/${sanitizedName}${ext}`;
    
    setAiOverlayLoading(true);
    setAiError('');
    
    try {
      let res;
      if (isAiMode) {
        // AI creation
        res = await fetch('/api/ai/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'create_file',
            path: fullPath,
            model: selectedAiModel,
            role: selectedAiRole,
            prompt: aiPromptText
          })
        });
      } else {
        // Standard creation (empty template)
        const template = newFileCategory === 'test'
          ? `# ${sanitizedName}\n# Test script for Sigma\n\ndef run():\n    print('Running ${sanitizedName}...')\n\nif __name__ == '__main__':\n    run()\n`
          : `# ${sanitizedName}\n\nContenuto del file ${newFileCategory}.\n`;
          
        res = await fetch('/api/create_file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: fullPath, content: template })
        });
      }
      
      const data = await res.json();
      if (data.success) {
        // Clean form states
        setNewFileName('');
        setAiPromptText('');
        setShowAiOverlay(false);
        
        // Refresh D3 graph and explorer list
        await fetchData();
        if (onOpenFile) onOpenFile(fullPath);
      } else {
        setAiError(data.error || 'Errore sconosciuto');
      }
    } catch (err) {
      setAiError('Errore di rete: ' + err.message);
    } finally {
      setAiOverlayLoading(false);
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
    { key: 'docs', icon: '📄', label: 'Docs', color: '#58a6ff', borderColor: 'rgba(88,166,255,0.2)' },
    { key: 'test', icon: '🧪', label: 'Test', color: '#3fb950', borderColor: 'rgba(63,185,80,0.2)' },
    { key: 'viz', icon: '📊', label: 'Visualizzazioni', color: '#d29922', borderColor: 'rgba(210,153,34,0.2)' },
  ];

  // --- Loading / Error ---
  if (error) {
    return (
      <div className="mappa-error">
        <div className="error-icon">⚠️</div>
        <div className="error-msg">Errore di caricamento: {escapeStr(error)}<br />Assicurati che Sigma Server sia in esecuzione.</div>
        <button className="retry-btn" onClick={fetchData}>⟳ Riprova</button>
      </div>
    );
  }

  if (topicsData.length === 0 && !loading) {
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

  const filteredTopics = topicsData.filter(t => 
    (t.name || '').toLowerCase().includes(searchQuery.toLowerCase()) || 
    (t.domain || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filterTopicModules = (topic, query) => {
    if (!topic || !topic.modules) return [];
    if (!query) return topic.modules;
    
    const cleanQuery = query.toLowerCase();
    return topic.modules.map(mod => {
      const modMatches = (mod.name || '').toLowerCase().includes(cleanQuery) || 
                         (mod.number || '').toLowerCase().includes(cleanQuery);
      
      const whitepapers = (mod.whitepapers || []).filter(f => (f.filename || '').toLowerCase().includes(cleanQuery));
      const docs = (mod.docs || []).filter(f => (f.filename || '').toLowerCase().includes(cleanQuery));
      const teoria = (mod.teoria || []).filter(f => (f.filename || '').toLowerCase().includes(cleanQuery));
      const test = (mod.test || []).filter(f => (f.filename || '').toLowerCase().includes(cleanQuery));
      const viz = (mod.viz || []).filter(f => (f.filename || '').toLowerCase().includes(cleanQuery));
      
      const hasMatchingFiles = whitepapers.length > 0 || docs.length > 0 || teoria.length > 0 || test.length > 0 || viz.length > 0;
      
      if (modMatches || hasMatchingFiles) {
        return {
          ...mod,
          whitepapers,
          docs,
          teoria,
          test,
          viz
        };
      }
      return null;
    }).filter(Boolean);
  };

  const filteredModules = activeTopic ? filterTopicModules(activeTopic, searchQuery) : [];

  return (
    <div className="mappa-argomenti">
      {loading && (
        <div className="mappa-loading-overlay" style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(14, 16, 22, 0.8)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          zIndex: 1000
        }}>
          <div className="spinner"></div>
          <div className="label" style={{ color: '#8b8fa3', fontSize: '0.75rem' }}>Caricamento bacheca…</div>
        </div>
      )}
      <style>{`
        .mappa-argomenti {
          position: relative;
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
          height: 100%; display: flex; flex-shrink: 0;
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
        .mappa-zoom-controls .btn-new-subtopic { padding: 7px 14px; font-size: 0.7rem; font-weight: 600; border-color: rgba(255,159,67,0.25); color: #ff9f43; display: flex; align-items: center; gap: 6px; }
        .mappa-zoom-controls .btn-new-subtopic:hover { background: rgba(255,159,67,0.12); border-color: rgba(255,159,67,0.4); }
        .mappa-zoom-controls .btn-delete-topic { padding: 7px 14px; font-size: 0.7rem; font-weight: 600; border-color: rgba(255,85,85,0.25); color: #ff5555; display: flex; align-items: center; gap: 6px; }
        .mappa-zoom-controls .btn-delete-topic:hover { background: rgba(255,85,85,0.12); border-color: rgba(255,85,85,0.4); }
        .mappa-zoom-controls .btn-parent-select-container { display: flex; align-items: center; position: relative; }
        .mappa-zoom-controls .btn-parent-select-container select {
          background: rgba(17,19,27,0.92); border: 1px solid rgba(210, 153, 34, 0.25); border-radius: 8px;
          color: #d29922; cursor: pointer; font-family: inherit; font-size: 0.7rem; font-weight: 600;
          padding: 7px 24px 7px 12px; outline: none; appearance: none; -webkit-appearance: none;
          transition: all 0.15s; backdrop-filter: blur(8px);
          background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23d29922' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
          background-repeat: no-repeat; background-position: right 8px center; background-size: 10px;
        }
        .mappa-zoom-controls .btn-parent-select-container select:hover { background-color: rgba(210, 153, 34, 0.12); border-color: rgba(210, 153, 34, 0.4); }


        /* Detail Panel (side panel in top section) */
        .mappa-detail-panel {
          width: 380px; border-left: 1px solid #1e2030;
          padding: 12px 16px; flex-shrink: 0; background: #11131b;
          display: flex; flex-direction: column; overflow: hidden;
        }
        .detail-body-scrollable {
          flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
          margin-top: 4px;
        }
        
        /* Search Box in Sidebar */
        .sidebar-search-box {
          position: relative; display: flex; align-items: center; margin-bottom: 12px;
          background: #0e1016; border: 1px solid #1e2030; border-radius: 6px; padding: 6px 10px;
          flex-shrink: 0;
        }
        .sidebar-search-box .search-icon { font-size: 0.65rem; color: #5a5e72; margin-right: 6px; }
        .sidebar-search-input {
          flex: 1; background: transparent; border: none; outline: none;
          color: #e2e4eb; font-size: 0.65rem; font-family: inherit;
        }
        .sidebar-search-input::placeholder { color: #5a5e72; }
        .clear-search-btn {
          background: none; border: none; color: #5a5e72; cursor: pointer; font-size: 0.6rem; padding: 2px;
        }
        .clear-search-btn:hover { color: #ff5555; }

        /* Explorer Sections */
        .explorer-section {
          margin-bottom: 10px; border-bottom: 1px solid #1e2030; padding-bottom: 12px;
        }
        .explorer-section-header {
          font-size: 0.5rem; font-weight: 600; color: #5a5e72; letter-spacing: 1px;
          cursor: pointer; display: flex; align-items: center; justify-content: space-between;
          padding: 4px 0; user-select: none;
        }
        .explorer-section-header:hover { color: #8b8fa3; }
        .explorer-section-content { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
        
        /* Topic Item in Explorer */
        .explorer-topic-item {
          display: flex; align-items: center; gap: 8px; padding: 6px 8px;
          border-radius: 6px; cursor: pointer; transition: all 0.15s; font-size: 0.65rem; color: #8b8fa3;
        }
        .explorer-topic-item:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .explorer-topic-item.active { background: rgba(188,140,255,0.06); color: #bc8cff; border-left: 2px solid #bc8cff; }
        .explorer-topic-icon { font-size: 0.6rem; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.03); border-radius: 4px; }
        .explorer-topic-item.active .explorer-topic-icon { background: rgba(188,140,255,0.1); }
        .explorer-topic-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .explorer-topic-count { font-size: 0.5rem; background: #1e2030; padding: 1px 5px; border-radius: 4px; color: #5a5e72; }
        .explorer-topic-item.active .explorer-topic-count { color: #bc8cff; background: rgba(188,140,255,0.1); }

        /* Folder Tree Explorer */
        .folder-tree { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
        .folder-item { display: flex; flex-direction: column; }
        .folder-header {
          display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 6px;
          cursor: pointer; transition: all 0.12s; font-size: 0.65rem; color: #8b8fa3; position: relative;
        }
        .folder-header:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .folder-header-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 4px; }
        .folder-header-count { font-size: 0.5rem; color: #5a5e72; margin-left: 4px; }
        .folder-actions { display: none; align-items: center; gap: 6px; position: absolute; right: 8px; }
        .folder-header:hover .folder-actions { display: flex; }
        .folder-action-btn { background: none; border: none; cursor: pointer; font-size: 0.55rem; color: #5a5e72; padding: 2px; }
        .folder-action-btn:hover { color: #e2e4eb; }
        .folder-action-btn.del:hover { color: #ff5555; }
        .folder-contents { padding-left: 14px; border-left: 1px dashed rgba(255,255,255,0.05); margin: 2px 0 4px 6px; display: flex; flex-direction: column; gap: 2px; }

        /* Category Folder Item */
        .category-folder-header {
          display: flex; align-items: center; gap: 4px; padding: 4px 6px; border-radius: 4px;
          cursor: pointer; transition: all 0.12s; font-size: 0.6rem; color: #8b8fa3; position: relative;
        }
        .category-folder-header:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .category-folder-actions { display: none; align-items: center; position: absolute; right: 6px; }
        .category-folder-header:hover .category-folder-actions { display: flex; }
        .category-folder-add-btn { background: none; border: none; cursor: pointer; font-size: 0.5rem; color: #5a5e72; padding: 1px 3px; border-radius: 3px; }
        .category-folder-add-btn:hover { color: #e2e4eb; background: rgba(255,255,255,0.05); }

        /* File Item inside Folder */
        .file-tree-item {
          display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: 4px;
          cursor: pointer; transition: all 0.1s; font-size: 0.6rem; color: #8b8fa3; position: relative;
        }
        .file-tree-item:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
        .file-tree-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-tree-actions { display: none; align-items: center; position: absolute; right: 6px; }
        .file-tree-item:hover .file-tree-actions { display: flex; }
        .file-tree-del-btn { background: none; border: none; cursor: pointer; font-size: 0.5rem; color: #ff5555; padding: 1px 3px; border-radius: 3px; }
        .file-tree-del-btn:hover { background: rgba(255,85,85,0.1); }

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

        /* AI action overlay card styles */
        .ai-overlay-card {
          position: absolute;
          width: 320px;
          background: rgba(11, 16, 27, 0.96);
          backdrop-filter: blur(16px);
          border: 1px solid rgba(0, 210, 255, 0.2);
          border-radius: 12px;
          box-shadow: 0 8px 32px rgba(0, 210, 255, 0.12), 0 0 0 1px rgba(0, 210, 255, 0.05);
          z-index: 1000;
          padding: 12px 14px;
          color: #e2e4eb;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .ai-overlay-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          padding-bottom: 6px;
          cursor: grab;
          user-select: none;
        }
        .ai-overlay-header:active {
          cursor: grabbing;
        }
        .ai-overlay-title {
          font-size: 0.7rem;
          font-weight: 700;
          color: #00d2ff;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 250px;
        }
        .ai-overlay-close {
          background: none;
          border: none;
          color: #5a5e72;
          cursor: pointer;
          font-size: 0.75rem;
          padding: 2px;
        }
        .ai-overlay-close:hover {
          color: #ff5555;
        }
        .ai-overlay-tabs {
          display: flex;
          background: #0e1016;
          border-radius: 6px;
          padding: 2px;
          gap: 2px;
        }
        .ai-overlay-tab {
          flex: 1;
          background: none;
          border: none;
          border-radius: 4px;
          color: #8b8fa3;
          font-size: 0.6rem;
          font-weight: 600;
          padding: 5px;
          cursor: pointer;
          transition: all 0.12s;
          text-align: center;
        }
        .ai-overlay-tab.active {
          background: rgba(0, 210, 255, 0.12);
          color: #00d2ff;
          border: 1px solid rgba(0, 210, 255, 0.15);
        }
        .ai-overlay-form {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .ai-overlay-group {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .ai-overlay-label {
          font-size: 0.5rem;
          font-weight: 600;
          color: #5a5e72;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }
        .ai-overlay-input, .ai-overlay-select, .ai-overlay-textarea {
          background: #0e1016;
          border: 1px solid #1e2030;
          border-radius: 6px;
          color: #e2e4eb;
          font-size: 0.65rem;
          font-family: inherit;
          padding: 6px 8px;
          outline: none;
          transition: border-color 0.12s;
        }
        .ai-overlay-input:focus, .ai-overlay-select:focus, .ai-overlay-textarea:focus {
          border-color: #00d2ff;
        }
        .ai-overlay-textarea {
          resize: vertical;
          min-height: 50px;
          line-height: 1.4;
        }
        .ai-overlay-error {
          font-size: 0.6rem;
          color: #ff5555;
          background: rgba(255, 85, 85, 0.08);
          border-radius: 6px;
          padding: 6px;
        }
        .ai-overlay-footer {
          display: flex;
          gap: 6px;
          margin-top: 4px;
        }
        .ai-overlay-btn {
          flex: 1;
          padding: 8px;
          border-radius: 6px;
          font-size: 0.65rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid #1e2030;
          background: #1e2030;
          color: #e2e4eb;
          transition: all 0.12s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        .ai-overlay-btn.primary {
          background: rgba(0, 210, 255, 0.10);
          border-color: rgba(0, 210, 255, 0.25);
          color: #00d2ff;
        }
        .ai-overlay-btn.primary:hover:not(:disabled) {
          background: rgba(0, 210, 255, 0.18);
          border-color: rgba(0, 210, 255, 0.45);
        }
        .ai-overlay-btn.secondary {
          background: transparent;
          color: #8b8fa3;
        }
        .ai-overlay-btn.secondary:hover {
          background: rgba(255, 255, 255, 0.03);
          color: #e2e4eb;
        }
        .ai-overlay-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .ai-overlay-spinner {
          width: 12px;
          height: 12px;
          border: 2px solid transparent;
          border-top-color: currentColor;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        .ai-overlay-dropzone:hover {
          border-color: rgba(0, 210, 255, 0.45) !important;
          background: rgba(0, 210, 255, 0.04) !important;
        }
        .ai-overlay-dropzone.dragging {
          border-color: #00d2ff !important;
          background: rgba(0, 210, 255, 0.08) !important;
          box-shadow: 0 0 12px rgba(0, 210, 255, 0.15);
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
            {activeTopic && (
              <>
                <button className="btn-new-subtopic" onClick={() => handleCreateSubTopic(activeTopic)} title="Crea nuovo sottoargomento">
                  ➕ Nuovo Sottoargomento
                </button>
                <button className="btn-delete-topic" onClick={() => handleDeleteTopic(activeTopic)} title="Elimina argomento selezionato">
                  🗑️ Elimina Argomento
                </button>
                {topicsData.length > 0 && (
                  <div className="btn-parent-select-container">
                    <select 
                      value={activeTopic.parent_id || ''} 
                      onChange={e => handleUpdateTopicParent(activeTopic, e.target.value)}
                      title="Assegna argomento padre"
                    >
                      <option value="">— Nessun padre —</option>
                      {topicsData.filter(t => t.id !== activeTopic.id).map(t => (
                        <option key={t.id} value={t.id}>⬆ {escapeStr(t.name)}</option>
                      ))}
                    </select>
                  </div>
                )}
              </>
            )}
          </div>

          {/* AI Overlay Menu */}
          {showAiOverlay && overlayNode && (
            <div 
              className="ai-overlay-card" 
              style={{ left: `${overlayPos.x}px`, top: `${overlayPos.y}px` }}
              onClick={e => e.stopPropagation()} // prevent clicking card from closing it
            >
              <div className="ai-overlay-header" onMouseDown={handleOverlayHeaderMouseDown}>
                <span className="ai-overlay-title">
                  {overlayNode.type === 'doc' ? '📄 ' : overlayNode.type === 'topic' ? '🌐 ' : '➕ '}
                  {escapeStr(overlayNode.label)}
                </span>
                <button className="ai-overlay-close" type="button" onClick={() => setShowAiOverlay(false)} onMouseDown={e => e.stopPropagation()}>✕</button>
              </div>

              {overlayNode.type === 'doc' ? (
                // File Actions Layout
                <>
                  <button
                    type="button"
                    className="ai-overlay-btn primary"
                    style={{
                      width: '100%',
                      padding: '10px',
                      marginBottom: '8px',
                      background: 'rgba(0, 210, 255, 0.15)',
                      borderColor: 'rgba(0, 210, 255, 0.35)',
                      color: '#00d2ff',
                      fontSize: '0.7rem',
                      borderRadius: '8px',
                      boxShadow: '0 0 10px rgba(0, 210, 255, 0.15)'
                    }}
                    onClick={() => {
                      if (onOpenFile && overlayNode.filePath) {
                        onOpenFile(overlayNode.filePath);
                      }
                      setShowAiOverlay(false);
                    }}
                  >
                    👁️ Visualizza / Apri File
                  </button>

                  <div className="ai-overlay-tabs">
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${fileTab === 'ai_edit' ? 'active' : ''}`}
                      onClick={() => { setFileTab('ai_edit'); setAiError(''); }}
                    >
                      🤖 Modifica AI
                    </button>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${fileTab === 'move' ? 'active' : ''}`}
                      onClick={() => { setFileTab('move'); setAiError(''); }}
                    >
                      📦 Sposta
                    </button>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${fileTab === 'delete' ? 'active' : ''}`}
                      onClick={() => { setFileTab('delete'); setAiError(''); }}
                    >
                      🗑️ Elimina
                    </button>
                  </div>

                  {fileTab === 'ai_edit' && (
                    <form className="ai-overlay-form" onSubmit={handleOverlayEditFile}>
                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Modello AI</span>
                        <select 
                          className="ai-overlay-select"
                          value={selectedAiModel}
                          onChange={e => setSelectedAiModel(e.target.value)}
                        >
                          {aiModels.length > 0 ? (
                            aiModels.map(m => (
                              <option key={m.name} value={m.name}>{m.name} ({m.size})</option>
                            ))
                          ) : (
                            <option value="llama3.2">llama3.2 (default)</option>
                          )}
                        </select>
                      </div>

                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Ruolo Agente</span>
                        <select 
                          className="ai-overlay-select"
                          value={selectedAiRole}
                          onChange={e => setSelectedAiRole(e.target.value)}
                        >
                          <option value="code_architect">💻 Code Architect</option>
                          <option value="math1">🔬 Math Architect</option>
                          <option value="test-engineer">🧪 Test Engineer</option>
                          <option value="viz-designer">🎨 Viz Designer</option>
                          <option value="proof-reviewer">👁️ Proof Reviewer</option>
                        </select>
                      </div>

                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Istruzioni di modifica</span>
                        <textarea 
                          className="ai-overlay-textarea"
                          placeholder="Come vuoi modificare il file..."
                          value={aiPromptText}
                          onChange={e => setAiPromptText(e.target.value)}
                          required
                        />
                      </div>

                      {aiError && <div className="ai-overlay-error">{aiError}</div>}

                      <div className="ai-overlay-footer">
                        <button 
                          type="button" 
                          className="ai-overlay-btn secondary"
                          onClick={() => { if (onOpenFile) onOpenFile(overlayNode.filePath); setShowAiOverlay(false); }}
                        >
                          👁️ Visualizza
                        </button>
                        <button 
                          type="submit" 
                          className="ai-overlay-btn primary"
                          disabled={aiOverlayLoading}
                        >
                          {aiOverlayLoading ? (
                            <>
                              <div className="ai-overlay-spinner"></div>
                              Applicazione...
                            </>
                          ) : (
                            '🤖 Modifica'
                          )}
                        </button>
                      </div>
                    </form>
                  )}

                  {fileTab === 'move' && (
                    <form className="ai-overlay-form" onSubmit={handleOverlayMoveFile}>
                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Argomento di destinazione</span>
                        <select 
                          className="ai-overlay-select"
                          value={moveTargetTopicId}
                          onChange={e => setMoveTargetTopicId(e.target.value)}
                        >
                          {topicsData.map(t => (
                            <option key={t.id} value={t.id}>🌐 {escapeStr(t.name)}</option>
                          ))}
                        </select>
                      </div>

                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Sottoargomento (Modulo)</span>
                        <select 
                          className="ai-overlay-select"
                          value={moveTargetModuleNum}
                          onChange={e => setMoveTargetModuleNum(e.target.value)}
                        >
                          <option value="">— Nessun modulo (radice argomento) —</option>
                          {(() => {
                            const activeTopic = topicsData.find(t => t.id === moveTargetTopicId);
                            return (activeTopic?.modules || []).map(m => (
                              <option key={m.number} value={m.number}>M{m.number} — {escapeStr(m.name)}</option>
                            ));
                          })()}
                        </select>
                      </div>

                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Categoria File</span>
                        <select 
                          className="ai-overlay-select"
                          value={moveTargetCategory}
                          onChange={e => setMoveTargetCategory(e.target.value)}
                        >
                          <option value="teoria">📖 Teoria</option>
                          <option value="test">🧪 TestScript</option>
                          <option value="viz">📊 Visualizzazione</option>
                          <option value="docs">📄 Documentazione</option>
                          <option value="whitepaper">📜 Whitepaper</option>
                        </select>
                      </div>

                      {aiError && <div className="ai-overlay-error">{aiError}</div>}

                      <div className="ai-overlay-footer">
                        <button 
                          type="button" 
                          className="ai-overlay-btn secondary"
                          onClick={() => setShowAiOverlay(false)}
                        >
                          Annulla
                        </button>
                        <button 
                          type="submit" 
                          className="ai-overlay-btn primary"
                          disabled={aiOverlayLoading}
                        >
                          {aiOverlayLoading ? (
                            <>
                              <div className="ai-overlay-spinner"></div>
                              Spostamento...
                            </>
                          ) : (
                            '📦 Sposta'
                          )}
                        </button>
                      </div>
                    </form>
                  )}

                  {fileTab === 'delete' && (
                    <div className="ai-overlay-form">
                      <div style={{ fontSize: '0.65rem', color: '#8b8fa3', margin: '4px 0 8px 0', lineHeight: '1.4' }}>
                        Sei sicuro di voler eliminare definitivamente questo file? Questa azione non può essere annullata.
                      </div>
                      
                      {aiError && <div className="ai-overlay-error">{aiError}</div>}

                      <div className="ai-overlay-footer">
                        <button 
                          type="button" 
                          className="ai-overlay-btn secondary"
                          onClick={() => setShowAiOverlay(false)}
                        >
                          Annulla
                        </button>
                        <button 
                          type="button" 
                          className="ai-overlay-btn"
                          style={{ background: 'rgba(255, 85, 85, 0.1)', borderColor: 'rgba(255, 85, 85, 0.25)', color: '#ff5555' }}
                          onClick={handleOverlayDeleteFile}
                          disabled={aiOverlayLoading}
                        >
                          {aiOverlayLoading ? 'Eliminazione...' : '🗑️ Elimina Definitivamente'}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                // Topic/Module Creation Layout
                <>
                  <div className="ai-overlay-tabs">
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${creationTab === 'standard' ? 'active' : ''}`}
                      onClick={() => { setCreationTab('standard'); setIsAiMode(false); setAiError(''); }}
                    >
                      Standard
                    </button>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${creationTab === 'ai' ? 'active' : ''}`}
                      onClick={() => { setCreationTab('ai'); setIsAiMode(true); setAiError(''); }}
                    >
                      🤖 Genera con AI
                    </button>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${creationTab === 'upload' ? 'active' : ''}`}
                      onClick={() => { setCreationTab('upload'); setIsAiMode(false); setAiError(''); }}
                    >
                      📎 Allega File
                    </button>
                  </div>

                  <form className="ai-overlay-form" onSubmit={handleOverlayCreateFile}>
                    <div className="ai-overlay-group">
                      <span className="ai-overlay-label">Categoria File</span>
                      <select 
                        className="ai-overlay-select"
                        value={newFileCategory}
                        onChange={e => setNewFileCategory(e.target.value)}
                      >
                        <option value="teoria">📖 Teoria</option>
                        <option value="test">🧪 Test</option>
                        <option value="viz">📊 Visualizzazione (D3)</option>
                        <option value="docs">📄 Documentazione</option>
                        <option value="whitepaper">📜 Whitepaper</option>
                      </select>
                    </div>

                    {creationTab === 'upload' && (
                      <div className="ai-overlay-group" style={{ gap: '8px' }}>
                        <span className="ai-overlay-label">Carica File da PC</span>
                        
                        {/* Drag and Drop Zone */}
                        <div 
                          className={`ai-overlay-dropzone ${isDragActive ? 'dragging' : ''} ${selectedUploadFile ? 'has-file' : ''}`}
                          onDragEnter={handleDrag}
                          onDragOver={handleDrag}
                          onDragLeave={handleDrag}
                          onDrop={handleDrop}
                          onClick={() => fileInputRef.current?.click()}
                          style={{
                            border: '1.5px dashed rgba(0, 210, 255, 0.25)',
                            borderRadius: '8px',
                            padding: '16px 12px',
                            textAlign: 'center',
                            background: isDragActive ? 'rgba(0, 210, 255, 0.08)' : selectedUploadFile ? 'rgba(0, 210, 255, 0.02)' : 'rgba(0,0,0,0.15)',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px'
                          }}
                        >
                          <input 
                            ref={fileInputRef}
                            type="file"
                            style={{ display: 'none' }}
                            onChange={handleFileChange}
                          />
                          
                          {selectedUploadFile ? (
                            <>
                              <span style={{ fontSize: '1.2rem' }}>📎</span>
                              <div style={{ fontSize: '0.65rem', fontWeight: '600', color: '#00d2ff', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {selectedUploadFile.name}
                              </div>
                              <div style={{ fontSize: '0.5rem', color: '#5a5e72' }}>
                                {(selectedUploadFile.size / 1024).toFixed(1)} KB
                              </div>
                              <button 
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedUploadFile(null);
                                  setNewFileName('');
                                }}
                                style={{
                                  background: 'rgba(255,85,85,0.1)',
                                  border: '1px solid rgba(255,85,85,0.2)',
                                  color: '#ff5555',
                                  fontSize: '0.5rem',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  marginTop: '4px',
                                  cursor: 'pointer'
                                }}
                              >
                                Rimuovi
                              </button>
                            </>
                          ) : (
                            <>
                              <span style={{ fontSize: '1.2rem', opacity: 0.6 }}>📥</span>
                              <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>
                                Trascina qui il file o <span style={{ color: '#00d2ff', textDecoration: 'underline' }}>sfoglia</span>
                              </div>
                              <div style={{ fontSize: '0.5rem', color: '#5a5e72' }}>
                                Supporta qualsiasi tipo di documento
                              </div>
                            </>
                          )}
                        </div>

                        {selectedUploadFile && (
                          <div className="ai-overlay-group">
                            <span className="ai-overlay-label">Nome file sul server (senza estensione)</span>
                            <input 
                              type="text" 
                              className="ai-overlay-input"
                              placeholder="nome_file_salvato"
                              value={newFileName}
                              onChange={e => setNewFileName(e.target.value.replace(/[^a-zA-Z0-9_-]/g, '_'))}
                              required
                            />
                          </div>
                        )}
                      </div>
                    )}

                    {creationTab !== 'upload' && (
                      <div className="ai-overlay-group">
                        <span className="ai-overlay-label">Nome File (senza estensione)</span>
                        <input 
                          type="text" 
                          className="ai-overlay-input"
                          placeholder="nome_file"
                          value={newFileName}
                          onChange={e => setNewFileName(e.target.value.replace(/[^a-zA-Z0-9_-]/g, '_'))}
                          required
                        />
                      </div>
                    )}

                    {creationTab === 'ai' && (
                      <>
                        <div className="ai-overlay-group">
                          <span className="ai-overlay-label">Modello AI</span>
                          <select 
                            className="ai-overlay-select"
                            value={selectedAiModel}
                            onChange={e => setSelectedAiModel(e.target.value)}
                          >
                            {aiModels.length > 0 ? (
                              aiModels.map(m => (
                                <option key={m.name} value={m.name}>{m.name} ({m.size})</option>
                              ))
                            ) : (
                              <option value="llama3.2">llama3.2 (default)</option>
                            )}
                          </select>
                        </div>

                        <div className="ai-overlay-group">
                          <span className="ai-overlay-label">Ruolo Agente</span>
                          <select 
                            className="ai-overlay-select"
                            value={selectedAiRole}
                            onChange={e => setSelectedAiRole(e.target.value)}
                          >
                            <option value="code_architect">💻 Code Architect</option>
                            <option value="math1">🔬 Math Architect</option>
                            <option value="test-engineer">🧪 Test Engineer</option>
                            <option value="viz-designer">🎨 Viz Designer</option>
                            <option value="proof-reviewer">👁️ Proof Reviewer</option>
                          </select>
                        </div>

                        <div className="ai-overlay-group">
                          <span className="ai-overlay-label">Descrizione per l'AI</span>
                          <textarea 
                            className="ai-overlay-textarea"
                            placeholder="Cosa deve contenere il file..."
                            value={aiPromptText}
                            onChange={e => setAiPromptText(e.target.value)}
                            required
                          />
                        </div>
                      </>
                    )}

                    {aiError && <div className="ai-overlay-error">{aiError}</div>}

                    <div className="ai-overlay-footer">
                      <button 
                        type="button" 
                        className="ai-overlay-btn secondary"
                        onClick={() => setShowAiOverlay(false)}
                        disabled={aiOverlayLoading}
                      >
                        Annulla
                      </button>
                      <button 
                        type="submit" 
                        className="ai-overlay-btn primary"
                        disabled={aiOverlayLoading || (creationTab === 'upload' && !selectedUploadFile)}
                      >
                        {aiOverlayLoading ? (
                          <>
                            <div className="ai-overlay-spinner"></div>
                            {creationTab === 'ai' ? 'Generazione...' : creationTab === 'upload' ? 'Caricamento...' : 'Creazione...'}
                          </>
                        ) : (
                          creationTab === 'ai' ? '🤖 Genera' : creationTab === 'upload' ? '📎 Carica' : 'Crea File'
                        )}
                      </button>
                    </div>
                  </form>
                </>
              )}
            </div>
          )}
        </div>
        <div className="mappa-detail-panel">
          {/* Search Box */}
          <div className="sidebar-search-box">
            <span className="search-icon">🔍</span>
            <input 
              type="text" 
              placeholder="Cerca argomenti, moduli o file..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="sidebar-search-input"
            />
            {searchQuery && (
              <button className="clear-search-btn" onClick={() => setSearchQuery('')}>✕</button>
            )}
          </div>

          <div className="detail-body-scrollable">
            {/* Topic Selector Section */}
            <div className="explorer-section">
              <div className="explorer-section-header" onClick={() => setExpandedTopicsSection(!expandedTopicsSection)}>
                <span>{expandedTopicsSection ? '▼' : '▶'} 🌐 ARGOMENTI ({topicsData.length})</span>
              </div>
              {expandedTopicsSection && (
                <div className="explorer-section-content">
                  {filteredTopics.map(topic => (
                    <div 
                      key={topic.id} 
                      className={`explorer-topic-item ${activeTopicId === topic.id ? 'active' : ''}`}
                      onClick={() => selectTopic(topic)}
                    >
                      <span className="explorer-topic-icon">{topicIcon(topic.domain)}</span>
                      <span className="explorer-topic-name">{escapeStr(topic.name)}</span>
                      <span className="explorer-topic-count">{(topic.modules || []).length}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Active Topic Folders Section */}
            {activeTopic && (
              <div className="explorer-section" style={{ borderBottom: 'none' }}>
                <div className="detail-header">
                  <div className="detail-type" style={{ color: '#bc8cff' }}>ARGOMENTO ATTIVO</div>
                  <div className="detail-title" style={{ color: '#bc8cff', fontSize: '0.85rem' }}>{escapeStr(activeTopic.name)}</div>
                  {activeTopic.description && (
                    <div className="detail-desc" style={{ fontSize: '0.65rem', marginTop: '4px', color: '#5a5e72' }}>
                      {escapeStr(activeTopic.description)}
                    </div>
                  )}
                </div>

                <div className="explorer-section-header" style={{ marginTop: '12px' }}>
                  <span>📂 FILE E SOTTOARGOMENTI</span>
                </div>

                <div className="folder-tree">
                  {filteredModules.length === 0 && (
                    <div style={{ fontSize: '0.6rem', color: '#5a5e72', padding: '8px 0' }}>
                      Nessun modulo trovato.
                    </div>
                  )}
                  {filteredModules.map(mod => {
                    const isModExpanded = searchQuery ? true : expandedModules[mod.number];
                    const isModSelected = selectedNode && selectedNode.type === 'module' && selectedNode.data.number === mod.number && selectedNode.topicId === activeTopic.id;
                    
                    const toggleModule = () => {
                      setExpandedModules(prev => ({ ...prev, [mod.number]: !prev[mod.number] }));
                    };

                    const totalFiles = (mod.docs || []).length + (mod.whitepapers || []).length +
                                      (mod.teoria || []).length + (mod.test || []).length + (mod.viz || []).length;

                    const folderPath = mod.folder || `${activeTopic.folder}/${mod.number}_${mod.name}`.toLowerCase().replace(/ /g, '_');

                    return (
                      <div key={mod.number} className="folder-item">
                        <div 
                          className={`folder-header ${isModSelected ? 'selected-folder' : ''}`}
                          onClick={toggleModule}
                          style={{
                            background: isModSelected ? 'rgba(0,210,255,0.06)' : 'transparent',
                            color: isModSelected ? '#00d2ff' : '#8b8fa3'
                          }}
                        >
                          <span className="folder-header-title">
                            <span>{isModExpanded ? '📂' : '📁'}</span>
                            <span>M{mod.number} — {escapeStr(mod.name)}</span>
                            <span className="folder-header-count">({totalFiles})</span>
                          </span>
                          
                          <div className="folder-actions">
                            <button 
                              className="folder-action-btn"
                              onClick={(e) => { e.stopPropagation(); handleRenameModule(mod, activeTopic.id); }}
                              title="Rinomina Sottoargomento"
                            >
                              ✏️
                            </button>
                            <button 
                              className="folder-action-btn del"
                              onClick={(e) => { e.stopPropagation(); handleDeleteModule(mod, activeTopic.id); }}
                              title="Elimina Sottoargomento"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>

                        {isModExpanded && (
                          <div className="folder-contents">
                            {columnDefs.map(col => {
                              const files = mod[col.key] || [];
                              const catKey = `${mod.number}-${col.key}`;
                              const isCatExpanded = searchQuery ? true : expandedCategories[catKey];
                              const fileType = col.key === 'whitepapers' ? 'whitepaper' : col.key;

                              const toggleCat = () => {
                                setExpandedCategories(prev => ({ ...prev, [catKey]: !prev[catKey] }));
                              };

                              return (
                                <div key={col.key} className="category-folder">
                                  <div className="category-folder-header" onClick={toggleCat}>
                                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: col.color }}>
                                      <span>{isCatExpanded ? '📂' : '📁'}</span>
                                      <span>{col.icon} {col.label}</span>
                                      <span style={{ fontSize: '0.5rem', opacity: 0.6 }}>({files.length})</span>
                                    </span>

                                    <div className="category-folder-actions">
                                      <button 
                                        className="category-folder-add-btn"
                                        onClick={(e) => { e.stopPropagation(); handleCreateFile(folderPath, fileType); }}
                                        title={`Crea nuovo ${col.label}`}
                                      >
                                        ➕
                                      </button>
                                    </div>
                                  </div>

                                  {isCatExpanded && (
                                    <div style={{ paddingLeft: '12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                      {files.length === 0 && (
                                        <div style={{ fontStyle: 'italic', color: '#5a5e72', fontSize: '0.55rem', padding: '2px 6px' }}>
                                          Vuoto
                                        </div>
                                      )}
                                      {files.map((file, idx) => (
                                        <div key={file.path || idx} className="file-tree-item">
                                          <span className="explorer-topic-icon" style={{ background: 'none', width: 'auto', height: 'auto' }}>{col.icon}</span>
                                          <span className="file-tree-name" onClick={() => onOpenFile && onOpenFile(file.path)}>
                                            {escapeStr(file.filename)}
                                          </span>
                                          
                                          <div className="file-tree-actions">
                                            <button 
                                              className="file-tree-del-btn"
                                              onClick={(e) => { e.stopPropagation(); handleDeleteFile(file.path); }}
                                              title="Elimina file"
                                            >
                                              🗑️
                                            </button>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>


    </div>
  );
}
