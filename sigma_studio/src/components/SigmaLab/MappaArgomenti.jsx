import React, { useRef, useEffect, useState, useCallback } from 'react';
import { PieChart, BookOpen, Layers } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

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
  scripts: { stroke: '#3fb950', fill: 'rgba(63,185,80,0.2)' },
  test: { stroke: '#3fb950', fill: 'rgba(63,185,80,0.2)' },
  viz: { stroke: '#d29922', fill: 'rgba(210,153,34,0.2)' },
  docs: { stroke: '#58a6ff', fill: 'rgba(88,166,255,0.2)' },
  whitepapers: { stroke: '#ffd700', fill: 'rgba(255,215,0,0.2)' },
  pdf: { stroke: '#ff5555', fill: 'rgba(255,85,85,0.2)' },
  media: { stroke: '#bd93f9', fill: 'rgba(189,147,249,0.2)' },
};
const DOC_ICONS = { teoria: '📖', scripts: '⚡', test: '⚡', viz: '📊', docs: '📄', whitepapers: '📜', pdf: '📕', media: '🎵' };
const DOC_PATHS = { teoria: 'teoria', scripts: 'scripts', test: 'scripts', viz: 'viz', docs: 'docs', whitepapers: 'whitepapers', pdf: 'pdf', media: 'media' };
const CATEGORY_AGENT_MAP = {
  teoria: 'math1',
  scripts: 'code_architect',
  viz: 'viz-designer',
  docs: 'proof-reviewer',
  whitepaper: 'proof-reviewer',
  pdf: 'online_journalist',
  media: 'online_journalist'
};

export default function MappaArgomenti({ onOpenFile }) {
  const { theme } = useApp();
  const isThemeLight = theme === 'light';
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
  const [selectedAiRole, setSelectedAiRole] = useState('math1');
  const [aiPromptText, setAiPromptText] = useState('');
  const [aiError, setAiError] = useState('');

  // Auto-assign Agent Role when File Category changes
  useEffect(() => {
    if (CATEGORY_AGENT_MAP[newFileCategory]) {
      setSelectedAiRole(CATEGORY_AGENT_MAP[newFileCategory]);
    }
  }, [newFileCategory]);

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

  // Modern Overlay Move Tab State
  const [topicOverlayTab, setTopicOverlayTab] = useState('create'); // 'create' | 'move'
  const [overlayMoveParentId, setOverlayMoveParentId] = useState('');

  // Auto clean upload states when overlay is closed
  // Configurable Font Size state (persisted in localStorage)
  const [labelFontSize, setLabelFontSize] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_graph_font_size');
      return saved ? parseInt(saved, 10) : 16;
    } catch (e) {
      return 16;
    }
  });

  const handleFontSizeChange = (newSize) => {
    setLabelFontSize(newSize);
    try { localStorage.setItem('sigma_graph_font_size', String(newSize)); } catch (e) {}
  };

  // Configurable Branch Length state (persisted in localStorage)
  const [branchLength, setBranchLength] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_graph_branch_length');
      return saved ? parseInt(saved, 10) : 240;
    } catch (e) {
      return 240;
    }
  });

  const handleBranchLengthChange = (newLen) => {
    setBranchLength(newLen);
    try { localStorage.setItem('sigma_graph_branch_length', String(newLen)); } catch (e) {}
  };

  // Argomenti Visualization Theme State
  const [argomentiTheme, setArgomentiTheme] = useState(() => {
    try {
      return localStorage.getItem('sigma_argomenti_theme') || 'costellazione';
    } catch (e) {
      return 'costellazione';
    }
  });

  const handleThemeChange = (newTheme) => {
    setArgomentiTheme(newTheme);
    try { localStorage.setItem('sigma_argomenti_theme', newTheme); } catch (e) {}
    window.dispatchEvent(new CustomEvent('sigma_argomenti_theme_changed', { detail: newTheme }));
  };

  useEffect(() => {
    const onThemeChange = (e) => {
      if (e.detail) setArgomentiTheme(e.detail);
    };
    window.addEventListener('sigma_argomenti_theme_changed', onThemeChange);
    return () => window.removeEventListener('sigma_argomenti_theme_changed', onThemeChange);
  }, []);

  const handleSaveLayout = () => {
    if (!simulationRef.current) return;
    const currentNodes = simulationRef.current.nodes();
    const positions = {};
    const round1 = (val) => val == null ? null : Math.round(val * 10) / 10;
    currentNodes.forEach(node => {
      const x = node.fx != null ? node.fx : node.x;
      const y = node.fy != null ? node.fy : node.y;
      positions[node.id] = { fx: round1(x), fy: round1(y), x: round1(x), y: round1(y) };
      node.fx = x;
      node.fy = y;
    });
    try {
      localStorage.setItem('sigma_graph_custom_positions', JSON.stringify(positions));
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: {
          message: '💾 Layout del grafo salvato con successo!',
          type: 'success',
          duration: 5000
        }
      }));
    } catch (e) {
      if (e.name === 'QuotaExceededError' || e.code === 22 || e.code === 1014) {
        try {
          localStorage.removeItem('sigma_graph_custom_positions');
          localStorage.setItem('sigma_graph_custom_positions', JSON.stringify(positions));
        } catch (retryErr) {}
      }
    }
  };

  const handleResetLayout = () => {
    try {
      localStorage.removeItem('sigma_graph_custom_positions');
    } catch (e) {}
    if (simulationRef.current) {
      const currentNodes = simulationRef.current.nodes();
      currentNodes.forEach(node => {
        node.fx = null;
        node.fy = null;
      });
      simulationRef.current.alpha(1).restart();
    }
    window.dispatchEvent(new CustomEvent('sigma_toast', {
      detail: {
        message: '🔄 Layout del grafo ripristinato ai valori predefiniti!',
        type: 'info',
        duration: 5000
      }
    }));
  };

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

  useEffect(() => { 
    fetchData(); 
    const handleTopicsUpdated = () => {
      fetchData();
    };
    window.addEventListener('sigma_topics_updated', handleTopicsUpdated);
    window.addEventListener('sigma_file_created', handleTopicsUpdated);
    return () => {
      window.removeEventListener('sigma_topics_updated', handleTopicsUpdated);
      window.removeEventListener('sigma_file_created', handleTopicsUpdated);
    };
  }, [fetchData]);

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
      const isTopLevel = !topic.parent_id;
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
        type: isTopLevel ? 'topic' : 'module',
        data: topic,
        topicId: topic.id,
        parentTopicId: topic.parent_id ? 'topic-' + topic.parent_id : null,
        depth: topicDepth,
        childTopicIndex,
        totalChildTopics,
        r: isTopLevel ? 22 : 16
      });
      nodeMap[topicId] = true;

      // Add document nodes directly linked to this topic or subtopic node
      if (showDocs) {
        let totalDocs = 0;
        for (const docType of ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media']) {
          totalDocs += (topic[docType] || []).length;
        }

        let docIndex = 0;
        for (const docType of ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media']) {
          const files = topic[docType] || [];
          for (const f of files) {
            const docId = 'doc-' + topic.id + '-' + f.path.replace(/[^a-zA-Z0-9_-]/g, '_');
            nodes.push({
              id: docId,
              label: f.name || f.filename,
              type: 'doc',
              docType,
              filePath: f.path,
              parentModId: topicId,
              depth: topicDepth + 1,
              docIndex,
              totalDocs,
              r: 6
            });
            nodeMap[docId] = true;
            links.push({ source: topicId, target: docId });
            docIndex++;
          }
        }
      }
    }

    // Connect parent topic / subtopic to child subtopic
    for (const topic of topicsData) {
      if (topic.parent_id) {
        const parentId = 'topic-' + topic.parent_id;
        const childId = 'topic-' + topic.id;
        if (nodeMap[parentId] && nodeMap[childId]) {
          links.push({ source: parentId, target: childId, type: 'parent' });
        }
      }
    }

    // Calculate directional fractal tree angles & initial coordinates
    const topLevelNodes = nodes.filter(n => n.type === 'topic');
    const totalTop = topLevelNodes.length || 1;
    const centerX = (dimensions.width || 800) / 2;
    const centerY = (dimensions.height || 600) / 2.5;

    topLevelNodes.forEach((node, idx) => {
      const topAngle = (idx / totalTop) * (2 * Math.PI) - (Math.PI / 2);
      node.angle = topAngle;
      const topDist = Math.round(branchLength * 1.35);
      node.targetX = centerX + Math.cos(topAngle) * topDist;
      node.targetY = centerY + Math.sin(topAngle) * topDist;
      if (node.x == null) node.x = node.targetX;
      if (node.y == null) node.y = node.targetY;
    });

    const nodeByIdMap = {};
    nodes.forEach(n => { nodeByIdMap[n.id] = n; });

    nodes.forEach(node => {
      if (node.type === 'module' && node.parentTopicId) {
        const parentNode = nodeByIdMap[node.parentTopicId];
        const parentAngle = parentNode?.angle ?? -Math.PI / 2;
        const totalSiblings = node.totalChildTopics || 1;
        const sibIndex = node.childTopicIndex || 0;
        
        // Spread subtopics in a symmetrical fan around parentAngle
        const spreadArc = Math.min(Math.PI * 1.1, Math.max(Math.PI * 0.45, totalSiblings * 0.5));
        const angle = totalSiblings > 1 
          ? parentAngle - (spreadArc / 2) + (sibIndex / (totalSiblings - 1)) * spreadArc 
          : parentAngle;
        
        node.angle = angle;
        const dist = Math.round(branchLength * (1 + 0.12 * (node.depth || 1)));
        const px = parentNode ? (parentNode.targetX ?? parentNode.x) : centerX;
        const py = parentNode ? (parentNode.targetY ?? parentNode.y) : centerY;
        node.targetX = px + Math.cos(angle) * dist;
        node.targetY = py + Math.sin(angle) * dist;
        if (node.x == null) node.x = node.targetX;
        if (node.y == null) node.y = node.targetY;
      } else if (node.type === 'doc' && node.parentModId) {
        const parentNode = nodeByIdMap[node.parentModId];
        const parentAngle = parentNode?.angle ?? 0;
        const totalDocs = node.totalDocs || 1;
        const docIdx = node.docIndex || 0;
        
        const docArc = Math.min(Math.PI * 0.9, Math.max(Math.PI * 0.35, totalDocs * 0.35));
        const angle = totalDocs > 1 
          ? parentAngle - (docArc / 2) + (docIdx / (totalDocs - 1)) * docArc 
          : parentAngle + 0.25;

        node.angle = angle;
        const dist = Math.round(branchLength * 0.55);
        const px = parentNode ? (parentNode.targetX ?? parentNode.x) : centerX;
        const py = parentNode ? (parentNode.targetY ?? parentNode.y) : centerY;
        node.targetX = px + Math.cos(angle) * dist;
        node.targetY = py + Math.sin(angle) * dist;
        if (node.x == null) node.x = node.targetX;
        if (node.y == null) node.y = node.targetY;
      }
    });

    try {
      const saved = localStorage.getItem('sigma_graph_custom_positions');
      if (saved) {
        const positions = JSON.parse(saved);
        nodes.forEach(node => {
          if (positions[node.id]) {
            node.fx = positions[node.id].fx ?? positions[node.id].x;
            node.fy = positions[node.id].fy ?? positions[node.id].y;
            node.x = positions[node.id].x;
            node.y = positions[node.id].y;
          }
        });
      }
    } catch (e) {
      console.error("Error restoring graph positions:", e);
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

    const isConstellation = argomentiTheme === 'costellazione';
    const isClassico = argomentiTheme === 'classico';
    const isMinimal = argomentiTheme === 'minimal';
    const isCrema = argomentiTheme === 'crema';

    // Define SVGs: Defs, Gradients & Glow Filters
    const defs = svg.append('defs');

    if (isConstellation) {
      // Glow Filter
      const glowFilter = defs.append('filter')
        .attr('id', 'constellation-glow')
        .attr('x', '-50%').attr('y', '-50%')
        .attr('width', '200%').attr('height', '200%');
      glowFilter.append('feGaussianBlur')
        .attr('stdDeviation', '3.5')
        .attr('result', 'coloredBlur');
      const feMerge = glowFilter.append('feMerge');
      feMerge.append('feMergeNode').attr('in', 'coloredBlur');
      feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

      // Topic Star Gradient
      const topicGrad = defs.append('radialGradient').attr('id', 'constellation-star-topic');
      topicGrad.append('stop').attr('offset', '0%').attr('stop-color', '#ffffff');
      topicGrad.append('stop').attr('offset', '35%').attr('stop-color', '#d2a8ff');
      topicGrad.append('stop').attr('offset', '75%').attr('stop-color', '#8957e5');
      topicGrad.append('stop').attr('offset', '100%').attr('stop-color', 'rgba(137, 87, 229, 0.3)');

      // Module Star Gradient
      const modGrad = defs.append('radialGradient').attr('id', 'constellation-star-module');
      modGrad.append('stop').attr('offset', '0%').attr('stop-color', '#ffffff');
      modGrad.append('stop').attr('offset', '35%').attr('stop-color', '#7dd3fc');
      modGrad.append('stop').attr('offset', '75%').attr('stop-color', '#0284c7');
      modGrad.append('stop').attr('offset', '100%').attr('stop-color', 'rgba(2, 132, 199, 0.3)');

      // Orange Star Gradient
      const orangeGrad = defs.append('radialGradient').attr('id', 'constellation-star-orange');
      orangeGrad.append('stop').attr('offset', '0%').attr('stop-color', '#ffffff');
      orangeGrad.append('stop').attr('offset', '35%').attr('stop-color', '#fbbf24');
      orangeGrad.append('stop').attr('offset', '75%').attr('stop-color', '#d97706');
      orangeGrad.append('stop').attr('offset', '100%').attr('stop-color', 'rgba(217, 119, 6, 0.3)');

      // Starlight Link Gradients
      const linkGrad = defs.append('linearGradient').attr('id', 'constellation-link-grad')
        .attr('x1', '0%').attr('y1', '0%').attr('x2', '100%').attr('y2', '100%');
      linkGrad.append('stop').attr('offset', '0%').attr('stop-color', '#bc8cff').attr('stop-opacity', '0.75');
      linkGrad.append('stop').attr('offset', '100%').attr('stop-color', '#00d2ff').attr('stop-opacity', '0.75');

      const parentGrad = defs.append('linearGradient').attr('id', 'parent-link-grad')
        .attr('x1', '0%').attr('y1', '0%').attr('x2', '100%').attr('y2', '100%');
      parentGrad.append('stop').attr('offset', '0%').attr('stop-color', '#fbbf24').attr('stop-opacity', '0.85');
      parentGrad.append('stop').attr('offset', '100%').attr('stop-color', '#ec4899').attr('stop-opacity', '0.85');

      // Background Twinkling Starfield Layer
      const starfieldLayer = svg.append('g').attr('class', 'background-starfield');
      const starCount = 100;
      for (let i = 0; i < starCount; i++) {
        const sx = (Math.sin(i * 997 + 12) * 0.5 + 0.5) * (width * 1.8) - width * 0.4;
        const sy = (Math.cos(i * 613 + 45) * 0.5 + 0.5) * (height * 1.8) - height * 0.4;
        const sr = (i % 5 === 0) ? 2.4 : (i % 3 === 0) ? 1.8 : 1.0;
        const opacity = 0.2 + (i % 7) * 0.1;
        const duration = 2 + (i % 5) * 1.2;
        const delay = (i % 9) * 0.4;
        
        starfieldLayer.append('circle')
          .attr('cx', sx)
          .attr('cy', sy)
          .attr('r', sr)
          .attr('fill', i % 4 === 0 ? '#7dd3fc' : i % 3 === 0 ? '#c084fc' : i % 5 === 0 ? '#fde047' : '#ffffff')
          .attr('opacity', opacity)
          .style('animation', `constellation-twinkle ${duration}s ease-in-out ${delay}s infinite alternate`);
      }
    } else if (isClassico) {
      // Arrow Markers for Tech Graph
      defs.selectAll('marker')
        .data(['topic-module', 'parent-child'])
        .enter().append('marker')
        .attr('id', d => d)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', d => d === 'parent-child' ? 'rgba(210,153,34,0.5)' : 'rgba(0,210,255,0.4)')
        .attr('d', 'M0,-5L10,0L0,5');

      // Tech Grid Pattern Background
      const pattern = defs.append('pattern')
        .attr('id', 'tech-grid-pattern')
        .attr('width', 36)
        .attr('height', 36)
        .attr('patternUnits', 'userSpaceOnUse');
      pattern.append('path')
        .attr('d', 'M 36 0 L 0 0 0 36')
        .attr('fill', 'none')
        .attr('stroke', 'rgba(0, 210, 255, 0.06)')
        .attr('stroke-width', 1);
      
      svg.append('rect')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('fill', 'url(#tech-grid-pattern)');
    }

    // Zoom
    const g = svg.append('g').attr('class', 'zoom-group');
    const zoom = d3.zoom()
      .scaleExtent([0.05, 5])
      .on('zoom', (event) => { g.attr('transform', event.transform); });
    svg.call(zoom);
    zoomRef.current = zoom;

    // Initial scale: centered in viewport with comfortable scale
    const initialScale = Math.min(width, height) / 1800;
    const initialTransform = d3.zoomIdentity
      .translate(width / 2, height / 2.5)
      .scale(Math.max(0.2, Math.min(0.425, initialScale)));
    svg.call(zoom.transform, initialTransform);

    // Link type map
    const linkTypeMap = {};
    for (const topic of topicsData) {
      if (topic.parent_id) {
        const key = 'topic-' + topic.parent_id + '|topic-' + topic.id;
        linkTypeMap[key] = true;
      }
    }

    // Links Rendering
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
        if (isConstellation) return isParent ? 'url(#parent-link-grad)' : 'url(#constellation-link-grad)';
        if (isClassico) return isParent ? '#d29922' : 'rgba(0, 210, 255, 0.4)';
        if (isCrema) return isParent ? '#c8963e' : 'rgba(139, 107, 61, 0.45)';
        return isParent ? '#bc8cff' : 'rgba(255, 255, 255, 0.18)';
      })
      .attr('stroke-width', d => {
        const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
        if (isConstellation) return isParent ? 2.6 : 1.8;
        if (isClassico || isCrema) return isParent ? 2.2 : 1.6;
        return 1.4;
      })
      .attr('stroke-dasharray', d => {
        const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
        return isParent ? (isConstellation ? '6,4' : '4,3') : 'none';
      })
      .attr('marker-end', d => {
        if (!isClassico) return null;
        const isParent = linkTypeMap[d.source.id + '|' + d.target.id] || linkTypeMap[d.target.id + '|' + d.source.id];
        return isParent ? 'url(#parent-child)' : 'url(#topic-module)';
      })
      .style('filter', isConstellation ? 'url(#constellation-glow)' : 'none');

    // Nodes Rendering
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

    if (isConstellation) {
      // 1. Constellation Star Orbit Rings
      nodeElements.append('circle')
        .attr('class', 'constellation-orbit-ring')
        .attr('r', d => d.r + (d.type === 'topic' ? 12 : d.type === 'module' ? 8 : 4))
        .attr('fill', 'none')
        .attr('stroke', d => d.type === 'topic' ? 'rgba(188,140,255,0.3)' : d.type === 'module' ? 'rgba(0,210,255,0.25)' : 'none')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '3,3');

      // 2. Constellation Star Flare Sparkles (8-point for topics, 4-point for modules)
      nodeElements.filter(d => d.type !== 'doc').append('path')
        .attr('class', 'constellation-star-flare')
        .attr('d', d => {
          const fl = d.r + (d.type === 'topic' ? 16 : 9);
          if (d.type === 'topic') {
            const s = fl * 0.42;
            const m = fl * 0.18;
            return `M 0,${-fl} Q 0,0 ${m},${-m} L ${s},${-s} Q 0,0 ${fl},0 Q 0,0 ${s},${s} L ${m},${m} Q 0,0 0,${fl} Q 0,0 ${-m},${m} L ${-s},${s} Q 0,0 ${-fl},0 Q 0,0 ${-s},${-s} L ${-m},${-m} Z`;
          }
          return `M 0,${-fl} Q 0,0 ${fl},0 Q 0,0 0,${fl} Q 0,0 ${-fl},0 Q 0,0 0,${-fl} Z`;
        })
        .attr('fill', d => {
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return 'rgba(251, 191, 36, 0.75)';
          return d.type === 'topic' ? 'rgba(188, 140, 255, 0.65)' : 'rgba(0, 210, 255, 0.65)';
        })
        .style('filter', 'url(#constellation-glow)');

      // 3. Central Constellation Star Core
      nodeElements.append('circle')
        .attr('class', 'constellation-star-core')
        .attr('r', d => d.r)
        .attr('fill', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.fill;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return 'url(#constellation-star-orange)';
          return d.type === 'topic' ? 'url(#constellation-star-topic)' : 'url(#constellation-star-module)';
        })
        .attr('stroke', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.stroke;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return '#fbbf24';
          return d.type === 'topic' ? '#bc8cff' : '#00d2ff';
        })
        .attr('stroke-width', d => d.type === 'doc' ? 1.5 : 2.5)
        .style('filter', 'url(#constellation-glow)');

      // 4. Center Bright White Star Point
      nodeElements.filter(d => d.type !== 'doc').append('circle')
        .attr('class', 'constellation-center-dot')
        .attr('r', d => d.type === 'topic' ? 4 : 3)
        .attr('fill', '#ffffff');
    } else {
      // CLASSICO & MINIMAL Node Rendering
      nodeElements.append('circle')
        .attr('class', 'theme-node-circle')
        .attr('r', d => d.r)
        .attr('fill', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.fill;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return 'rgba(210,153,34,0.25)';
          if (isClassico) return d.type === 'topic' ? 'rgba(188,140,255,0.18)' : 'rgba(0,210,255,0.15)';
          if (isCrema) return d.type === 'topic' ? 'rgba(139,107,61,0.22)' : 'rgba(200,150,62,0.18)';
          return d.type === 'topic' ? '#1e1633' : '#102233';
        })
        .attr('stroke', d => {
          if (d.type === 'doc') {
            const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
            return c.stroke;
          }
          const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
          if (isSelected) return '#d29922';
          if (isCrema) return d.type === 'topic' ? '#8b6b3d' : '#c8963e';
          return d.type === 'topic' ? '#bc8cff' : '#00d2ff';
        })
        .attr('stroke-width', d => d.type === 'doc' ? 1.5 : (isClassico ? 2.5 : 2))
        .style('filter', isClassico ? d => d.type === 'topic' ? 'drop-shadow(0 0 6px rgba(188,140,255,0.4))' : 'drop-shadow(0 0 6px rgba(0,210,255,0.3))' : isCrema ? d => d.type === 'topic' ? 'drop-shadow(0 0 6px rgba(139,107,61,0.3))' : 'drop-shadow(0 0 6px rgba(200,150,62,0.25))' : 'none');
    }

    // Node Labels — Dynamic radial orientation to radiate text outwards away from neighbors
    nodeElements.append('text')
      .attr('class', d => 'node-label ' + d.type)
      .attr('text-anchor', d => {
        const cos = Math.cos(d.angle || 0);
        if (cos > 0.25) return 'start';
        if (cos < -0.25) return 'end';
        return 'middle';
      })
      .attr('dx', d => {
        const cos = Math.cos(d.angle || 0);
        if (cos > 0.25) return d.r + 8;
        if (cos < -0.25) return -(d.r + 8);
        return 0;
      })
      .attr('dy', d => {
        const cos = Math.cos(d.angle || 0);
        const sin = Math.sin(d.angle || 0);
        if (Math.abs(cos) > 0.25) return 4;
        if (sin < -0.25) return -(d.r + 8);
        return d.r + Math.round(d.type === 'topic' ? labelFontSize * 1.1 : labelFontSize * 0.95) + 2;
      })
      .attr('fill', isCrema ? '#4a3b25' : '#e2e4eb')
      .attr('font-size', d => {
        if (d.type === 'topic') return Math.round(labelFontSize * 1.15) + 'px';
        if (d.type === 'module') return labelFontSize + 'px';
        return Math.max(10, Math.round(labelFontSize * 0.85)) + 'px';
      })
      .attr('font-weight', d => d.type === 'topic' ? '700' : '600')
      .attr('pointer-events', 'none')
      .attr('stroke', isCrema ? '#faf6ec' : '#050612')
      .attr('stroke-width', '3.5px')
      .attr('stroke-linejoin', 'round')
      .style('paint-order', 'stroke fill')
      .style('text-shadow', d => isConstellation ? (d.type === 'topic' ? '0 0 10px rgba(188,140,255,0.8)' : '0 0 8px rgba(0,210,255,0.7)') : 'none')
      .text(d => d.label.length > 40 ? d.label.slice(0, 38) + '…' : d.label);

    // Simulation with harmonious fractal tree positioning & collision forces
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(d => d.type === 'doc' ? Math.round(branchLength * 0.55) : Math.round(branchLength * 1.15)).strength(0.35))
      .force('charge', d3.forceManyBody().strength(d => d.type === 'topic' ? -1800 : d.type === 'module' ? -1000 : -250))
      .force('center', d3.forceCenter(width / 2, height / 2.5).strength(0.02))
      .force('collision', d3.forceCollide().radius(d => {
        const textLen = (d.label || '').length;
        const textWidthEst = Math.min(180, textLen * (labelFontSize * 0.32));
        if (d.type === 'topic') return Math.max(d.r + 65, textWidthEst + 25);
        if (d.type === 'module') return Math.max(d.r + 45, textWidthEst + 15);
        return d.r + 20;
      }).strength(0.9))
      .on('tick', () => {
        nodes.forEach(d => {
          if (d.fx != null && d.fy != null) {
            d.x = d.fx;
            d.y = d.fy;
            return;
          }
          if (d.targetX != null && d.targetY != null) {
            // Gentle spring pull towards directional fractal tree position
            d.x += (d.targetX - d.x) * 0.12;
            d.y += (d.targetY - d.y) * 0.12;
          }
        });

        linkElements
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
        nodeElements.attr('transform', d => `translate(${d.x},${d.y})`);
      });

    // Helper to find all descendant nodes (child subtopics & files) of a node
    const getSubtreeNodes = (rootNode, allNodes) => {
      const descendants = [];
      const queue = [rootNode.id];
      const visited = new Set([rootNode.id]);

      while (queue.length > 0) {
        const currId = queue.shift();
        allNodes.forEach(n => {
          if (!visited.has(n.id)) {
            if (n.parentTopicId === currId || n.parentModId === currId) {
              visited.add(n.id);
              descendants.push(n);
              queue.push(n.id);
            }
          }
        });
      }
      return descendants;
    };

    let prevDragX = 0;
    let prevDragY = 0;
    let draggedDescendants = [];

    // Helper to persist custom positions of a dragged node & all its descendants
    const saveNodePositions = (draggedRoot, descendants) => {
      try {
        let saved = null;
        try { saved = localStorage.getItem('sigma_graph_custom_positions'); } catch (e) {}
        const positions = saved ? JSON.parse(saved) : {};

        const round1 = (val) => val == null ? null : Math.round(val * 10) / 10;

        // Save root node position
        positions[draggedRoot.id] = {
          x: round1(draggedRoot.x),
          y: round1(draggedRoot.y),
          fx: round1(draggedRoot.fx ?? draggedRoot.x),
          fy: round1(draggedRoot.fy ?? draggedRoot.y)
        };

        // Save all descendant nodes' positions & pin them with fx, fy
        descendants.forEach(child => {
          child.fx = child.x;
          child.fy = child.y;
          positions[child.id] = {
            x: round1(child.x),
            y: round1(child.y),
            fx: round1(child.fx),
            fy: round1(child.fy)
          };
        });

        const jsonStr = JSON.stringify(positions);
        try {
          localStorage.setItem('sigma_graph_custom_positions', jsonStr);
        } catch (e) {
          if (e.name === 'QuotaExceededError' || e.code === 22 || e.code === 1014) {
            // Quota exceeded: store pruned positions to avoid error loop
            const compactPositions = {};
            compactPositions[draggedRoot.id] = positions[draggedRoot.id];
            descendants.forEach(c => { compactPositions[c.id] = positions[c.id]; });
            try {
              localStorage.setItem('sigma_graph_custom_positions', JSON.stringify(compactPositions));
            } catch (retryErr) {}
          }
        }
      } catch (e) {
        // Silently catch layout persistence error to prevent console spam
      }
    };

    // Drag Behavior — Hierarchical dragging (parent drags all child folders & files)
    const drag = d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
        prevDragX = event.x;
        prevDragY = event.y;
        draggedDescendants = getSubtreeNodes(d, nodes);
      })
      .on('drag', (event, d) => {
        const deltaX = event.x - prevDragX;
        const deltaY = event.y - prevDragY;
        prevDragX = event.x;
        prevDragY = event.y;

        d.fx = event.x;
        d.fy = event.y;

        // Simultaneously translate all child subtopic and document nodes in the subtree
        draggedDescendants.forEach(child => {
          if (child.targetX != null) child.targetX += deltaX;
          if (child.targetY != null) child.targetY += deltaY;
          child.x += deltaX;
          child.y += deltaY;
          if (child.fx != null) child.fx += deltaX;
          if (child.fy != null) child.fy += deltaY;
        });
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        saveNodePositions(d, draggedDescendants);
      });

    nodeElements.call(drag);

    simulationRef.current = simulation;

    // Auto-focus camera on the first main topic on initial graph load
    const firstTop = topicsData.find(t => !t.parent_id) || topicsData[0];
    if (firstTop) {
      if (!selectedNode) {
        setSelectedNode({ type: 'topic', data: firstTop });
        setActiveTopicId(firstTop.id);
      }
      setTimeout(() => {
        focusNodeOnGraph(firstTop.id, 0.82);
      }, 250);
    }

    return () => {
      simulation.stop();
    };
  }, [d3, topicsData, dimensions, buildGraphData, branchLength, argomentiTheme]);

  // Update node visuals on selection change without restarting simulation
  useEffect(() => {
    if (!d3 || !svgRef.current || topicsData.length === 0) return;
    const svg = d3.select(svgRef.current);
    // Update constellation star fills/strokes and flares
    svg.selectAll('.graph-node .constellation-star-core')
      .attr('fill', d => {
        if (d.type === 'doc') {
          const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
          return c.fill;
        }
        const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
        if (isSelected) return 'url(#constellation-star-orange)';
        return d.type === 'topic' ? 'url(#constellation-star-topic)' : 'url(#constellation-star-module)';
      })
      .attr('stroke', d => {
        if (d.type === 'doc') {
          const c = DOC_COLORS[d.docType] || DOC_COLORS.docs;
          return c.stroke;
        }
        const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
        if (isSelected) return '#fbbf24';
        return d.type === 'topic' ? '#bc8cff' : '#00d2ff';
      });

    svg.selectAll('.graph-node .constellation-star-flare')
      .attr('fill', d => {
        const isSelected = selectedNode && d.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number);
        if (isSelected) return 'rgba(251, 191, 36, 0.85)';
        return d.type === 'topic' ? 'rgba(188, 140, 255, 0.65)' : 'rgba(0, 210, 255, 0.65)';
      });
    // Update node class
    svg.selectAll('.graph-node')
      .attr('class', n => 'graph-node' + (selectedNode && n.id === (selectedNode.type === 'topic' ? 'topic-' + selectedNode.data.id : 'mod-' + selectedNode.topicId + '-' + selectedNode.data.number) ? ' selected' : ''));
  }, [d3, selectedNode, topicsData]);

  // Dynamic font-size update on label elements
  useEffect(() => {
    if (!d3 || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('.node-label')
      .attr('font-size', d => {
        if (!d) return labelFontSize + 'px';
        if (d.type === 'topic') return Math.round(labelFontSize * 1.15) + 'px';
        if (d.type === 'module') return labelFontSize + 'px';
        return Math.max(10, Math.round(labelFontSize * 0.85)) + 'px';
      });
  }, [d3, labelFontSize]);

  const focusNodeOnGraph = useCallback((targetId, forceScale = null) => {
    if (!simulationRef.current || !svgRef.current || !zoomRef.current || !window.d3) return;
    const d3Obj = window.d3;
    const currentNodes = simulationRef.current.nodes();
    const targetNode = currentNodes.find(n => n.id === targetId || n.id === 'topic-' + targetId || n.topicId === targetId);
    if (targetNode && targetNode.x != null && targetNode.y != null) {
      const width = dimensions.width || 800;
      const height = dimensions.height || 600;
      const currentTransform = d3Obj.zoomTransform(svgRef.current);
      // Maintain user's exact current zoom scale unless explicitly forced
      const targetScale = forceScale || currentTransform.k || 0.82;
      const transform = d3Obj.zoomIdentity
        .translate(width / 2 - targetNode.x * targetScale, height / 2.5 - targetNode.y * targetScale)
        .scale(targetScale);

      d3Obj.select(svgRef.current)
        .transition()
        .duration(700)
        .ease(d3Obj.easeCubicInOut)
        .call(zoomRef.current.transform, transform);
    }
  }, [dimensions]);

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
      const initialScale = Math.min(dimensions.width, dimensions.height) / 1200;
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

  const handleCreateSubTopic = async (parentTarget) => {
    let parentId = null;
    let parentName = 'Argomento';
    
    if (typeof parentTarget === 'string') {
      parentId = parentTarget;
    } else if (parentTarget) {
      parentId = parentTarget.id || (parentTarget.folder ? parentTarget.folder.replace(/^data\//, '') : null);
      parentName = parentTarget.name || parentTarget.label || parentId || 'Argomento';
      if (!parentId && parentTarget.number && parentTarget.name) {
        parentId = parentTarget.folder ? parentTarget.folder.replace(/^data\//, '') : `${parentTarget.topicId || activeTopicId}/${parentTarget.number}_${parentTarget.name}`.toLowerCase().replace(/ /g, '_');
      }
    }

    const name = prompt(`Nome del nuovo sottoargomento (cartella) dentro "${parentName}":`);
    if (!name || !name.trim()) return;

    const rawSlug = name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!rawSlug) return;

    try {
      const res = await fetch('/api/create_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: rawSlug,
          parent_id: parentId,
          name: name.trim(),
          description: `Sottoargomento di ${parentName}`
        })
      });
      const data = await res.json();
      if (data.success) {
        window.dispatchEvent(new CustomEvent('sigma_toast', {
          detail: {
            message: `✨ Sottoargomento "${name}" creato in costellazione!`,
            type: 'success',
            duration: 4000
          }
        }));
        await fetchData();
      } else {
        alert('Errore creazione sottoargomento: ' + (data.error || 'sconosciuto'));
      }
    } catch (e) {
      alert('Errore di rete: ' + e.message);
    }
  };

  // Recursive descendant calculation to prevent cyclic parent-child assignments
  const getDescendantIds = (rootId, allTopics) => {
    const descendants = new Set([rootId]);
    const queue = [rootId];
    while (queue.length > 0) {
      const currentId = queue.shift();
      const children = allTopics.filter(t => t.parent_id === currentId);
      for (const child of children) {
        if (!descendants.has(child.id)) {
          descendants.add(child.id);
          queue.push(child.id);
        }
      }
    }
    return descendants;
  };

  const getValidMoveDestinations = (nodeToMove) => {
    if (!nodeToMove) return [];
    // Exclude nodeToMove itself and all of its descendants
    const invalidIds = getDescendantIds(nodeToMove.id, topicsData);
    return topicsData.filter(t => !invalidIds.has(t.id));
  };

  const handleMoveModule = (mod) => {
    const node = (mod && mod.id) ? mod : topicsData.find(t => t.id === mod.id || t.name === mod.name) || mod;
    if (!node) return;
    const graphNode = simulationRef.current?.nodes().find(n => n.data?.id === node.id || n.id === 'topic-' + node.id);
    if (graphNode && containerRef.current) {
      setOverlayPos({ x: Math.min((graphNode.x || 300) + 15, (dimensions.width || 800) - 320), y: Math.max((graphNode.y || 200) - 20, 20) });
      setOverlayNode(graphNode);
    } else {
      setOverlayNode({ type: node.parent_id ? 'module' : 'topic', data: node, label: node.name });
      setOverlayPos({ x: 200, y: 150 });
    }
    setOverlayMoveParentId(node.parent_id || '');
    setTopicOverlayTab('move');
    setShowAiOverlay(true);
    setAiError('');
    focusNodeOnGraph(node.id);
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
    let baseFolder = overlayNode.data?.folder || (overlayNode.data?.id ? `data/${overlayNode.data.id}` : '');
    
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
    
    if (isAiMode) {
      // AI creation — Close overlay immediately and send persistent start toast
      const targetFileName = `${sanitizedName}${ext}`;
      const roleToUse = selectedAiRole || CATEGORY_AGENT_MAP[newFileCategory] || 'code_architect';
      const toastKeyId = `ai-gen-${Date.now()}`;
      
      setNewFileName('');
      setAiPromptText('');
      setShowAiOverlay(false);

      // Persistent start notification (duration: 0 keeps it active until completed)
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: {
          id: toastKeyId,
          message: `⏳ Generazione AI in corso per "${targetFileName}"...`,
          type: 'loop',
          duration: 0
        }
      }));

      (async () => {
        try {
          const res = await fetch('/api/ai/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              action: 'create_file',
              path: fullPath,
              model: selectedAiModel,
              role: roleToUse,
              prompt: aiPromptText
            })
          });
          const data = await res.json();
          // Remove progress toast
          window.dispatchEvent(new CustomEvent('sigma_toast', {
            detail: { id: toastKeyId, action: 'close' }
          }));

          if (data.success) {
            window.dispatchEvent(new CustomEvent('sigma_toast', {
              detail: {
                message: `✅ File "${targetFileName}" generato con successo!`,
                type: 'success',
                duration: 7000
              }
            }));
            await fetchData();
            window.dispatchEvent(new Event('sigma_topics_updated'));
            if (onOpenFile) onOpenFile(fullPath);
          } else {
            window.dispatchEvent(new CustomEvent('sigma_toast', {
              detail: {
                message: `❌ Errore generazione AI per "${targetFileName}": ${data.error || 'Errore sconosciuto'}`,
                type: 'error',
                duration: 8000
              }
            }));
          }
        } catch (err) {
          window.dispatchEvent(new CustomEvent('sigma_toast', {
            detail: { id: toastKeyId, action: 'close' }
          }));
          window.dispatchEvent(new CustomEvent('sigma_toast', {
            detail: {
              message: `❌ Errore di rete durante la generazione: ${err.message}`,
              type: 'error',
              duration: 8000
            }
          }));
        } finally {
          setAiOverlayLoading(false);
        }
      })();
      return;
    }

    // Standard creation (empty template)
    setAiOverlayLoading(true);
    setAiError('');
    try {
      const template = (newFileCategory === 'scripts' || newFileCategory === 'test')
        ? `# ${sanitizedName}\n# Script per Sigma\n\ndef run():\n    print('Running ${sanitizedName}...')\n\nif __name__ == '__main__':\n    run()\n`
        : `# ${sanitizedName}\n\nContenuto del file ${newFileCategory}.\n`;
        
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath, content: template })
      });
      
      const data = await res.json();
      if (data.success) {
        setNewFileName('');
        setAiPromptText('');
        setShowAiOverlay(false);
        await fetchData();
        window.dispatchEvent(new Event('sigma_topics_updated'));
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
    let totalFiles = 0;
    let filesHtml = '';

    const categoryIcons = {
      teoria: '📖', scripts: '⚡', test: '🧪', viz: '📊', docs: '📄', whitepapers: '📜', pdf: '📕', media: '🎵'
    };

    const directFiles = [
      ...(topic.teoria || []),
      ...(topic.scripts || []),
      ...(topic.viz || []),
      ...(topic.docs || []),
      ...(topic.whitepapers || []),
      ...(topic.pdf || []),
      ...(topic.media || [])
    ];

    // Fallback to modules[0] if direct files empty
    const fileSource = directFiles.length > 0 ? directFiles : (topic.modules && topic.modules[0] ? [
      ...(topic.modules[0].teoria || []),
      ...(topic.modules[0].scripts || []),
      ...(topic.modules[0].viz || []),
      ...(topic.modules[0].docs || []),
      ...(topic.modules[0].whitepapers || []),
      ...(topic.modules[0].pdf || []),
      ...(topic.modules[0].media || [])
    ] : []);

    for (const f of fileSource) {
      totalFiles++;
      const ext = (f.filename || f.name || '').split('.').pop().toLowerCase();
      let icon = '📄';
      if (ext === 'pdf') icon = '📕';
      else if (['png', 'jpg', 'jpeg', 'svg', 'webp', 'gif'].includes(ext)) icon = '🖼️';
      else if (['mp3', 'wav', 'mp4', 'webm'].includes(ext)) icon = '🎵';
      else if (['py', 'js', 'jsx', 'ts'].includes(ext)) icon = '⚡';
      else if (ext === 'md') icon = '📖';

      filesHtml += `<div class="detail-file-item" onclick="${onOpenFile ? `window.__openFile('${escapeStr(f.path)}')` : ''}">
        <span class="icon">${icon}</span>
        <span class="fname">${escapeStr(f.filename || f.name)}</span>
      </div>`;
    }

    const parentTopic = topic.parent_id ? topicsData.find(t => t.id === topic.parent_id) : null;
    const childTopics = topicsData.filter(t => t.parent_id === topic.id);

    return (
      <div className="detail-body">
        <div className="detail-header">
          <div className="detail-type">ARGOMENTO DI CONOSCENZA</div>
          <div className="detail-title" style={{ color: '#bc8cff' }}>{escapeStr(topic.name)}</div>
        </div>
        <div className="detail-desc">{escapeStr(topic.description)}</div>

        {/* Pulsante Nuovo Argomento Collegato e Selettore Argomento Padre DENTRO l'Argomento */}
        <div className="topic-inside-controls" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0 12px', alignItems: 'center' }}>
          <button 
            className="btn-new-subtopic" 
            onClick={() => handleCreateSubTopic(topic)} 
            title="Crea nuovo argomento collegato dentro questo nodo"
            style={{ padding: '6px 12px', fontSize: '0.65rem', background: 'rgba(0,210,255,0.12)', color: '#00d2ff', border: '1px solid rgba(0,210,255,0.3)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
          >
            ➕ Nuovo Argomento Collegato
          </button>
          {topicsData.length > 1 && (
            <select
              value={topic.parent_id || ''}
              onChange={e => handleUpdateTopicParent(topic, e.target.value)}
              title="Seleziona argomento padre"
              style={{ background: '#0e1016', color: '#bc8cff', border: '1px solid rgba(188,140,255,0.3)', borderRadius: '6px', padding: '5px 10px', fontSize: '0.65rem', outline: 'none' }}
            >
              <option value="">— Nessun Argomento Padre —</option>
              {topicsData.filter(t => t.id !== topic.id).map(t => (
                <option key={t.id} value={t.id}>⬆ Padre: {escapeStr(t.name)}</option>
              ))}
            </select>
          )}
        </div>

        <div className="detail-meta">
          <span className="tag">{totalFiles} file integrati</span>
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
          <button className="detail-action-btn" onClick={() => handleCreateSubTopic(mod)} style={{ color: '#00d2ff', borderColor: 'rgba(0,210,255,0.4)', background: 'rgba(0,210,255,0.08)', fontWeight: 600 }}>
            ➕ Nuovo Sottoargomento (Sotto-cartella)
          </button>
          <button className="detail-action-btn" onClick={() => handleMoveModule(mod, topicId)} style={{ color: '#00d2ff', borderColor: 'rgba(0,210,255,0.2)' }}>
            ⇄ Sposta in un altro Argomento
          </button>
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

  // Select topic and center graph focus on target node
  const selectTopic = (topic) => {
    setActiveTopicId(topic.id);
    setSelectedModule(null);
    setSelectedNode({ type: topic.parent_id ? 'module' : 'topic', data: topic });
    focusNodeOnGraph(topic.id);
  };

  const columnDefs = [
    { key: 'teoria', icon: '📄', label: 'Docs', color: '#bc8cff', borderColor: 'rgba(188,140,255,0.2)' },
    { key: 'docs', icon: '📄', label: 'Docs', color: '#58a6ff', borderColor: 'rgba(88,166,255,0.2)' },
    { key: 'scripts', icon: '⚡', label: 'Scripts', color: '#00d2ff', borderColor: 'rgba(0,210,255,0.2)' },
    { key: 'whitepapers', icon: '📜', label: 'Whitepapers', color: '#ffd700', borderColor: '#ffd700' },
    { key: 'test', icon: '🧪', label: 'Test', color: '#3fb950', borderColor: 'rgba(63,185,80,0.2)' },
    { key: 'viz', icon: '📊', label: 'Visualizzazioni', color: '#d29922', borderColor: 'rgba(210,153,34,0.2)' },
    { key: 'pdf', icon: '📜', label: 'PDF', color: '#ff7b72', borderColor: 'rgba(255,123,114,0.2)' },
    { key: 'media', icon: '🎥', label: 'Media', color: '#d2a8ff', borderColor: 'rgba(210,168,255,0.2)' },
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

  // Filter ONLY top-level main topics (where parent_id is null/empty)
  const topLevelTopics = topicsData.filter(t => !t.parent_id);

  const filteredTopLevelTopics = topLevelTopics.filter(t => 
    (t.name || '').toLowerCase().includes(searchQuery.toLowerCase()) || 
    (t.domain || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Filter ONLY subtopics belonging directly to the active topic
  const activeTopicSubtopics = activeTopic 
    ? topicsData.filter(t => t.parent_id === activeTopic.id && (
        !searchQuery || (t.name || '').toLowerCase().includes(searchQuery.toLowerCase())
      ))
    : [];

  return (
    <div className={`mappa-argomenti${isThemeLight ? ' theme-light' : ''}`}>
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
        @keyframes constellation-twinkle {
          0%, 100% { opacity: 0.2; transform: scale(0.85); }
          50% { opacity: 0.95; transform: scale(1.25); }
        }
        @keyframes constellation-orbit-spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .mappa-argomenti {
          position: relative;
          display: flex;
          flex-direction: column;
          height: 100%;
          background: radial-gradient(ellipse at 50% 30%, #10132b 0%, #080918 60%, #03040b 100%);
          color: #e2e4eb;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 15px;
          overflow: hidden;
        }
        /* === TEMA LIGHT OVERRIDES (palette Manifesti crema/bianco) === */
        .mappa-argomenti.theme-light {
          background: radial-gradient(ellipse at 50% 30%, #f7f4ed 0%, #f2ede2 60%, #e8e0d0 100%);
          color: #111111;
        }
        .mappa-argomenti.theme-light ::-webkit-scrollbar-thumb { background: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light ::-webkit-scrollbar-thumb:hover { background: rgba(234, 88, 12, 0.4); }
        .mappa-argomenti.theme-light .mappa-header-bar {
          background: linear-gradient(135deg, rgba(255, 253, 249, 0.97) 0%, rgba(247, 244, 237, 0.94) 100%) !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
          box-shadow: 0 4px 20px rgba(190, 160, 110, 0.12) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar button {
          background: rgba(255, 253, 249, 0.9);
          border-color: rgba(190, 160, 110, 0.35);
          color: #111111;
        }
        .mappa-argomenti.theme-light .mappa-detail-panel {
          background: #fffdf9 !important;
          border-left-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .theme-control,
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control {
          background: #fffdf9 !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
          color: #2e2820 !important;
          box-shadow: 0 2px 8px rgba(190, 160, 110, 0.15) !important;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control span,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control span {
          color: #d97706;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .font-size-control input,
        .mappa-argomenti.theme-light .mappa-header-bar .branch-length-control input {
          accent-color: #ea580c;
        }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-explore,
        .mappa-argomenti.theme-light .mappa-header-bar .btn-explore.active { color: #3fb950; }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-update { color: #d97706; }
        .mappa-argomenti.theme-light .mappa-header-bar .btn-new-topic { color: #111111; background: rgba(190, 160, 110, 0.14); border-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .module-filter-bar,
        .mappa-argomenti.theme-light .topic-tab-bar {
          background: #f7f4ed !important;
          border-bottom-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .mfb-label { color: #2e2820; }
        .mappa-argomenti.theme-light .mfb-btn,
        .mappa-argomenti.theme-light .topic-tab { color: #2e2820; }
        .mappa-argomenti.theme-light .mfb-btn:hover,
        .mappa-argomenti.theme-light .topic-tab:hover { color: #111111; background: #f2ede2; border-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .mfb-btn.active { color: #d97706; border-color: rgba(190, 160, 110, 0.5); background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .topic-tab.active { color: #111111; border-bottom-color: #d97706; background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .topic-tab .tab-count { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .topic-tab.active .tab-count { background: rgba(190, 160, 110, 0.28); color: #111111; }
        .mappa-argomenti.theme-light .file-columns-area { border-top-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .file-column {
          background: #fffdf9 !important;
          border-color: rgba(190, 160, 110, 0.35) !important;
        }
        .mappa-argomenti.theme-light .file-column-header {
          border-bottom-color: rgba(190, 160, 110, 0.35);
          color: #111111;
        }
        .mappa-argomenti.theme-light .file-column .empty-col-hint { color: #2e2820; }
        .mappa-argomenti.theme-light .col-file-item .col-file-name { color: #2e2820; }
        .mappa-argomenti.theme-light .col-file-item .col-file-name:hover { color: #111111; }
        .mappa-argomenti.theme-light .col-file-item:hover { background: #f2ede2; }
        .mappa-argomenti.theme-light .col-file-item .col-mod-badge { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .sidebar-search-box {
          background: #fffdf9;
          border-color: rgba(190, 160, 110, 0.35);
        }
        .mappa-argomenti.theme-light .sidebar-search-box .search-icon { color: #2e2820; }
        .mappa-argomenti.theme-light .sidebar-search-input { color: #111111; }
        .mappa-argomenti.theme-light .sidebar-search-input::placeholder { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-section { border-bottom-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .explorer-section-header { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-section-header:hover { color: #111111; }
        .mappa-argomenti.theme-light .explorer-topic-item { color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-topic-item:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .explorer-topic-item.active { background: rgba(190, 160, 110, 0.14); color: #111111; border-left-color: #d97706; }
        .mappa-argomenti.theme-light .explorer-topic-icon { background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .explorer-topic-count { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .explorer-topic-item.active .explorer-topic-count { color: #111111; background: rgba(190, 160, 110, 0.28); }
        .mappa-argomenti.theme-light .folder-header { color: #2e2820; }
        .mappa-argomenti.theme-light .folder-header:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .folder-header-count { color: #2e2820; }
        .mappa-argomenti.theme-light .category-folder-header { color: #2e2820; }
        .mappa-argomenti.theme-light .category-folder-header:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .file-tree-item { color: #2e2820; }
        .mappa-argomenti.theme-light .file-tree-item:hover { background: #f2ede2; color: #111111; }
        .mappa-argomenti.theme-light .detail-type { color: #2e2820 !important; }
        .mappa-argomenti.theme-light .detail-desc { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-meta .tag { background: rgba(190, 160, 110, 0.14); color: #2e2820; }
        .mappa-argomenti.theme-light .detail-meta .tag.modules-tag { color: #d97706; background: rgba(190, 160, 110, 0.14); }
        .mappa-argomenti.theme-light .detail-rel-label { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-rel-value { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-rel-tag { background: rgba(190, 160, 110, 0.14); border: 1px solid rgba(190, 160, 110, 0.28); color: #111111; }
        .mappa-argomenti.theme-light .detail-files h4 { color: #2e2820; border-bottom-color: rgba(190, 160, 110, 0.35); }
        .mappa-argomenti.theme-light .detail-file-item .fname { color: #2e2820; }
        .mappa-argomenti.theme-light .detail-file-item .fname:hover { color: #111111; }
        .mappa-argomenti.theme-light .detail-file-item:hover { background: #f2ede2; }
        .mappa-argomenti.theme-light .detail-action-btn { border-color: rgba(190, 160, 110, 0.35); color: #2e2820; }
        .mappa-argomenti.theme-light .detail-action-btn:hover { background: rgba(190, 160, 110, 0.14); color: #111111; border-color: rgba(190, 160, 110, 0.5); }
        .mappa-argomenti.theme-light .detail-empty { color: #2e2820; }
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
          background: radial-gradient(ellipse at 40% 40%, rgba(137, 87, 229, 0.09) 0%, rgba(0, 210, 255, 0.04) 45%, transparent 85%);
        }
        .constellation-orbit-ring {
          transform-origin: center;
          animation: constellation-orbit-spin 30s linear infinite;
        }
        .graph-node:hover .constellation-star-flare {
          transform: scale(1.35);
          transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .mappa-graph-svg { width: 100%; height: 100%; display: block; }
        .graph-link { stroke-width: 1.8; transition: opacity 0.2s; }
        .graph-link.parent-link { stroke-dasharray: 6,4; }
        .graph-link.highlight { stroke: #00d2ff !important; stroke-width: 3 !important; }
        .graph-link.parent-link.highlight { stroke: #fbbf24 !important; stroke-width: 3.5 !important; }
        .graph-node { cursor: pointer; transition: opacity 0.2s; }
        .mappa-zoom-controls {
          position: absolute; bottom: 12px; left: 12px; display: flex; gap: 6px; align-items: center;
        }
        .mappa-header-bar button {
          background: rgba(22, 27, 40, 0.75);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #e2e4eb;
          cursor: pointer;
          font-family: inherit;
          font-weight: 600;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .mappa-header-bar .btn-explore {
          background: rgba(46, 160, 67, 0.12);
          border-color: rgba(46, 160, 67, 0.35);
          color: #3fb950;
        }
        .mappa-header-bar .btn-explore:hover {
          background: rgba(46, 160, 67, 0.22);
          border-color: rgba(46, 160, 67, 0.6);
          box-shadow: 0 0 12px rgba(46, 160, 67, 0.25);
          transform: translateY(-1px);
        }
        .mappa-header-bar .btn-explore.active {
          background: rgba(255, 85, 85, 0.12);
          border-color: rgba(255, 85, 85, 0.35);
          color: #ff5555;
        }
        .mappa-header-bar .btn-explore.active:hover {
          background: rgba(255, 85, 85, 0.22);
          border-color: rgba(255, 85, 85, 0.6);
          box-shadow: 0 0 12px rgba(255, 85, 85, 0.25);
        }
        .mappa-header-bar .btn-update {
          background: rgba(0, 210, 255, 0.12);
          border-color: rgba(0, 210, 255, 0.35);
          color: #00d2ff;
        }
        .mappa-header-bar .btn-update:hover {
          background: rgba(0, 210, 255, 0.22);
          border-color: rgba(0, 210, 255, 0.6);
          box-shadow: 0 0 14px rgba(0, 210, 255, 0.3);
          transform: translateY(-1px);
        }
        .mappa-header-bar .btn-new-topic {
          background: linear-gradient(135deg, rgba(188, 140, 255, 0.2), rgba(137, 87, 229, 0.14));
          border-color: rgba(188, 140, 255, 0.4);
          color: #d2a8ff;
        }
        .mappa-header-bar .btn-new-topic:hover {
          background: linear-gradient(135deg, rgba(188, 140, 255, 0.3), rgba(137, 87, 229, 0.25));
          border-color: rgba(188, 140, 255, 0.65);
          box-shadow: 0 0 14px rgba(188, 140, 255, 0.35);
          transform: translateY(-1px);
        }


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
      
      {/* Hero Visual Banner with Standardized Theme System & Dimensions */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: theme === 'light' ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: theme === 'light'
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/knowledge_graph_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/knowledge_graph_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: theme === 'light' ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <PieChart size={14} /> KNOWLEDGE GRAPH & TOPIC EXPLORER
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: theme === 'light' ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              🗺️ Mappa Argomenti & <span style={{
                color: theme === 'light' ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Grafo di Conoscenza</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: theme === 'light' ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Mappe concettuali, grafi della conoscenza interattivi D3 e risorse di studio strutturate.
            </p>
          </div>

          {/* Action Buttons on the Right */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={handleResetLayout}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: theme === 'light' ? '#fffdf9' : '#181b28',
                color: theme === 'light' ? '#111' : '#fff',
                border: theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              🎯 Centra Grafo
            </button>
          </div>
        </div>
      </div>
      
      {/* TOP SECTION — left column (controls + graph) & right column (detail panel) */}
      <div className="mappa-top-section" style={{ flex: 1, minHeight: 0, display: 'flex', gap: '14px', margin: '0 16px 14px 16px' }}>
        {/* COLONNA SINISTRA — BARRA DEI CONTROLLI + CANVAS GRAFO */}
        <div 
          className="mappa-left-column" 
          style={{ 
            flex: 1, 
            minWidth: 0, 
            display: 'flex', 
            flexDirection: 'column', 
            position: 'relative',
            overflow: 'hidden',
            borderRadius: '10px'
          }}
        >
          {/* HEADER CONTROLS BAR (Posizionata sopra il grafo nella colonna di sinistra) */}
          <div 
            className="mappa-header-bar" 
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '10px',
              padding: '8px 12px',
              margin: '0 0 10px 0',
              background: 'linear-gradient(135deg, rgba(17, 19, 27, 0.95), rgba(24, 27, 40, 0.85))',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              backdropFilter: 'blur(12px)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
              zIndex: 5,
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {/* Selettore Tema Visualizzazione */}
              <div className="theme-control" style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#11131b', border: '1px solid rgba(0, 210, 255, 0.25)', padding: '4px 10px', borderRadius: '8px', fontSize: '0.68rem', color: '#8b8fa3', boxShadow: '0 2px 10px rgba(0,0,0,0.3)', transition: 'border-color 0.2s' }} title="Cambia tema della Mappa Argomenti">
                <span style={{ fontSize: '0.72rem' }}>🎨 Tema:</span>
                <select
                  value={argomentiTheme}
                  onChange={e => handleThemeChange(e.target.value)}
                  style={{
                    background: argomentiTheme === 'crema' ? 'rgba(245, 239, 227, 0.98)' : 'rgba(14, 16, 22, 0.95)',
                    color: argomentiTheme === 'costellazione' ? '#bc8cff' : argomentiTheme === 'classico' ? '#00d2ff' : argomentiTheme === 'crema' ? '#8b6b3d' : '#fbbf24',
                    border: '1px solid ' + (argomentiTheme === 'costellazione' ? 'rgba(188, 140, 255, 0.4)' : argomentiTheme === 'classico' ? 'rgba(0, 210, 255, 0.4)' : argomentiTheme === 'crema' ? 'rgba(200, 150, 62, 0.5)' : 'rgba(251, 191, 36, 0.4)'),
                    borderRadius: '6px',
                    padding: '4px 8px',
                    outline: 'none',
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: argomentiTheme === 'costellazione' ? '0 0 10px rgba(188, 140, 255, 0.2)' : argomentiTheme === 'classico' ? '0 0 10px rgba(0, 210, 255, 0.2)' : argomentiTheme === 'crema' ? '0 0 10px rgba(200, 150, 62, 0.3)' : '0 0 10px rgba(251, 191, 36, 0.2)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <option value="costellazione" style={{ background: '#0e1016', color: '#bc8cff' }}>🌌 Costellazione Spaziale</option>
                  <option value="classico" style={{ background: '#0e1016', color: '#00d2ff' }}>📊 Grafo Tecnologico</option>
                  <option value="minimal" style={{ background: '#0e1016', color: '#fbbf24' }}>✨ Minimal & Contrast</option>
                  <option value="crema" style={{ background: '#f5efe3', color: '#8b6b3d' }}>🎨 Tema Crema</option>
                </select>
              </div>

              {/* Slider Dimensione Testo Nodi (Espanso: 6px - 90px) */}
              <div className="font-size-control" style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#11131b', border: '1px solid #1e2030', padding: '5px 10px', borderRadius: '8px', fontSize: '0.68rem', color: '#8b8fa3' }} title="Regola la dimensione del testo dei nodi (da 6px a 90px)">
                <span>🔤 Testo:</span>
                <input
                  type="range"
                  min="6"
                  max="90"
                  step="1"
                  value={labelFontSize}
                  onChange={e => handleFontSizeChange(parseInt(e.target.value, 10))}
                  style={{ width: '85px', accentColor: '#00d2ff', cursor: 'pointer' }}
                />
                <span style={{ color: '#00d2ff', fontWeight: 600, minWidth: '32px' }}>{labelFontSize}px</span>
              </div>

              {/* Slider Lunghezza Rami (Espanso: 40px - 800px) */}
              <div className="branch-length-control" style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#11131b', border: '1px solid #1e2030', padding: '5px 10px', borderRadius: '8px', fontSize: '0.68rem', color: '#8b8fa3' }} title="Regola la lunghezza dei rami del grafico (da 40px a 800px)">
                <span>🌿 Rami:</span>
                <input
                  type="range"
                  min="40"
                  max="800"
                  step="10"
                  value={branchLength}
                  onChange={e => handleBranchLengthChange(parseInt(e.target.value, 10))}
                  style={{ width: '85px', accentColor: '#bc8cff', cursor: 'pointer' }}
                />
                <span style={{ color: '#bc8cff', fontWeight: 600, minWidth: '36px' }}>{branchLength}px</span>
              </div>

              {/* Esplora Button */}
              <button 
                className={`btn-explore ${showDocs ? 'active' : ''}`} 
                onClick={() => {
                  setShowDocs(prev => {
                    const next = !prev;
                    localStorage.setItem('sigma_mappa_explore', String(next));
                    return next;
                  });
                }} 
                title={showDocs ? 'Collidi' : 'Esplora'}
                style={{ padding: '6px 12px', fontSize: '0.72rem', borderRadius: '8px' }}
              >
                {showDocs ? '✕ Collidi' : '🔍 Esplora'}
              </button>

              {/* Refresh Button */}
              <button 
                className="btn-update" 
                onClick={fetchData} 
                title="Aggiorna dati e grafico"
                style={{ padding: '6px 12px', fontSize: '0.72rem', borderRadius: '8px' }}
              >
                🔄 Aggiorna
              </button>

              {/* Salva Layout Button */}
              <button 
                className="btn-update" 
                onClick={handleSaveLayout} 
                title="Salva le posizioni trascinate dei nodi del grafo"
                style={{ padding: '6px 12px', fontSize: '0.72rem', borderRadius: '8px', background: 'rgba(63, 185, 80, 0.12)', borderColor: 'rgba(63, 185, 80, 0.3)', color: '#3fb950' }}
              >
                💾 Salva Layout
              </button>

              {/* Reset Layout Default Button */}
              <button 
                className="btn-update" 
                onClick={handleResetLayout} 
                title="Ripristina il layout predefinito con calcolo automatico della forza"
                style={{ padding: '6px 12px', fontSize: '0.72rem', borderRadius: '8px', background: 'rgba(210, 153, 34, 0.12)', borderColor: 'rgba(210, 153, 34, 0.3)', color: '#d29922' }}
              >
                🔄 Layout Default
              </button>

              {/* Nuovo Argomento Button */}
              <button 
                className="btn-new-topic" 
                onClick={handleCreateTopic} 
                title="Crea nuovo argomento"
                style={{ padding: '6px 12px', fontSize: '0.72rem', borderRadius: '8px' }}
              >
                🌐 Nuovo Argomento
              </button>
            </div>
          </div>

          {/* CANVAS DEL GRAFO */}
          <div 
            ref={containerRef} 
            className="mappa-graph-container" 
            style={{ 
              flex: 1,
              minHeight: 0,
              display: 'flex',
              position: 'relative',
              overflow: 'hidden',
              borderRadius: '10px',
              background: argomentiTheme === 'costellazione' 
                ? 'radial-gradient(ellipse at 40% 40%, rgba(137, 87, 229, 0.14) 0%, rgba(0, 210, 255, 0.06) 45%, #050612 90%)' 
                : argomentiTheme === 'classico' 
                ? 'radial-gradient(circle at 50% 50%, rgba(0, 210, 255, 0.08) 0%, #090b14 85%)' 
                : argomentiTheme === 'crema'
                ? 'radial-gradient(ellipse at 40% 40%, rgba(200, 150, 62, 0.14) 0%, rgba(139, 107, 61, 0.06) 45%, #f2e8d4 100%)'
                : '#0e1018'
            }}
          >
          <svg ref={svgRef} className="mappa-graph-svg" style={{ flex: 1 }}></svg>

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
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {overlayNode.type === 'doc' && (
                    <button 
                      className="ai-overlay-close" 
                      type="button" 
                      style={{ color: '#ff5555', background: 'rgba(255,85,85,0.1)', border: '1px solid rgba(255,85,85,0.2)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem' }} 
                      onClick={() => { setFileTab('delete'); setAiError(''); }} 
                      onMouseDown={e => e.stopPropagation()}
                      title="Elimina questo file"
                    >
                      🗑️
                    </button>
                  )}
                  <button className="ai-overlay-close" type="button" onClick={() => setShowAiOverlay(false)} onMouseDown={e => e.stopPropagation()}>✕</button>
                </div>
              </div>

              {overlayNode.type === 'doc' ? (
                // File Actions Layout
                <>
                  <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                    <button
                      type="button"
                      className="ai-overlay-btn primary"
                      style={{
                        flex: 1,
                        padding: '8px 10px',
                        background: 'rgba(0, 210, 255, 0.15)',
                        borderColor: 'rgba(0, 210, 255, 0.35)',
                        color: '#00d2ff',
                        fontSize: '0.68rem',
                        borderRadius: '8px',
                        fontWeight: 600,
                        boxShadow: '0 0 10px rgba(0, 210, 255, 0.15)'
                      }}
                      onClick={() => {
                        if (onOpenFile && overlayNode.filePath) {
                          onOpenFile(overlayNode.filePath);
                        }
                        setShowAiOverlay(false);
                      }}
                    >
                      👁️ Visualizza
                    </button>

                    <button
                      type="button"
                      className="ai-overlay-btn"
                      style={{
                        flex: 1,
                        padding: '8px 10px',
                        background: 'rgba(255, 85, 85, 0.12)',
                        borderColor: 'rgba(255, 85, 85, 0.3)',
                        color: '#ff5555',
                        fontSize: '0.68rem',
                        borderRadius: '8px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                      onClick={() => {
                        setFileTab('delete');
                        setAiError('');
                      }}
                    >
                      🗑️ Elimina
                    </button>
                  </div>

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
                          <option value="scripts">⚡ Script / Codice</option>
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
                // Topic/Module Overlay Layout
                <>
                  {/* Tabs per Argomento / Sottoargomento nel div Overlay */}
                  <div className="ai-overlay-tabs" style={{ marginBottom: '10px' }}>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${topicOverlayTab === 'create' ? 'active' : ''}`}
                      onClick={() => { setTopicOverlayTab('create'); setAiError(''); }}
                    >
                      ➕ Contenuti & Azioni
                    </button>
                    <button 
                      type="button"
                      className={`ai-overlay-tab ${topicOverlayTab === 'move' ? 'active' : ''}`}
                      onClick={() => { 
                        setTopicOverlayTab('move'); 
                        setOverlayMoveParentId(overlayNode.data?.parent_id || '');
                        setAiError(''); 
                      }}
                    >
                      📦 Sposta
                    </button>
                  </div>

                  {topicOverlayTab === 'move' ? (
                    /* TAB SPOSTA SOTTOARGOMENTO NEL DIV OVERLAY */
                    <div className="ai-overlay-form" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {(() => {
                        const nodeToMove = overlayNode.data;
                        const validDestinations = getValidMoveDestinations(nodeToMove);
                        const currentParent = topicsData.find(t => t.id === nodeToMove?.parent_id);

                        return (
                          <>
                            <div style={{ fontSize: '0.62rem', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.06)', borderRadius: '6px', padding: '6px 8px', color: '#8b8fa3' }}>
                              📍 Posizione Attuale: <strong style={{ color: '#bc8cff' }}>{currentParent ? escapeStr(currentParent.name) : '🌐 Cartella Principale (1° Livello)'}</strong>
                            </div>

                            <div className="ai-overlay-group">
                              <span className="ai-overlay-label">Seleziona Destinazione</span>
                              <select 
                                className="ai-overlay-select"
                                value={overlayMoveParentId}
                                onChange={e => setOverlayMoveParentId(e.target.value)}
                              >
                                <option value="">🌐 Cartella Principale (1° Livello)</option>
                                {validDestinations.map(dest => (
                                  <option key={dest.id} value={dest.id}>
                                    {dest.parent_id ? '📂 ' : '🌐 '}{escapeStr(dest.name)}
                                  </option>
                                ))}
                              </select>
                              <div style={{ fontSize: '0.55rem', color: '#5a5e72', marginTop: '2px', fontStyle: 'italic' }}>
                                * I sottoargomenti figli di questo nodo sono stati nascosti per evitare cicli.
                              </div>
                            </div>

                            {aiError && <div className="ai-overlay-error">{aiError}</div>}

                            <div className="ai-overlay-footer" style={{ marginTop: '8px', display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                              <button 
                                type="button"
                                className="ai-overlay-btn secondary"
                                onClick={() => setTopicOverlayTab('create')}
                              >
                                Annulla
                              </button>
                              <button 
                                type="button"
                                className="ai-overlay-btn primary"
                                disabled={aiOverlayLoading}
                                onClick={async () => {
                                  setAiOverlayLoading(true);
                                  setAiError('');
                                  try {
                                    const res = await fetch('/api/update_topic', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ topic_id: nodeToMove.id, parent_id: overlayMoveParentId || null })
                                    });
                                    const data = await res.json();
                                    if (data.success) {
                                      const freshTopics = await fetchData();
                                      setShowAiOverlay(false);
                                      if (freshTopics) {
                                        const freshNode = freshTopics.find(t => t.id === nodeToMove.id);
                                        if (freshNode) {
                                          setSelectedNode({ type: freshNode.parent_id ? 'module' : 'topic', data: freshNode });
                                          if (freshNode.parent_id) setActiveTopicId(freshNode.parent_id);
                                          focusNodeOnGraph(freshNode.id);
                                        }
                                      }
                                      window.dispatchEvent(new CustomEvent('sigma_toast', {
                                        detail: { message: `📦 "${nodeToMove.name}" spostato con successo!`, type: 'success', duration: 3500 }
                                      }));
                                    } else {
                                      setAiError(data.error || 'Errore durante lo spostamento');
                                    }
                                  } catch (err) {
                                    setAiError('Errore di connessione: ' + err.message);
                                  } finally {
                                    setAiOverlayLoading(false);
                                  }
                                }}
                              >
                                {aiOverlayLoading ? 'Spostamento...' : '📦 Conferma Spostamento'}
                              </button>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  ) : (
                    <>
                      {/* Pulsanti Azione per Argomento nel div Overlay */}
                      {overlayNode.type === 'topic' && (
                        <div className="ai-overlay-actions-section" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <button
                            type="button"
                            className="ai-overlay-btn"
                            style={{ background: 'rgba(0, 210, 255, 0.16)', borderColor: 'rgba(0, 210, 255, 0.4)', color: '#00d2ff', fontSize: '0.65rem', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, width: '100%' }}
                            onClick={() => {
                              handleCreateSubTopic(overlayNode.data);
                              setShowAiOverlay(false);
                            }}
                          >
                            ➕ Nuovo Sottoargomento
                          </button>

                          <button
                            type="button"
                            className="ai-overlay-btn"
                            style={{ background: 'rgba(255, 85, 85, 0.08)', borderColor: 'rgba(255, 85, 85, 0.2)', color: '#ff5555', fontSize: '0.6rem', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', marginTop: '2px' }}
                            onClick={() => {
                              handleDeleteTopic(overlayNode.data);
                              setShowAiOverlay(false);
                            }}
                          >
                            🗑️ Elimina Argomento
                          </button>
                        </div>
                      )}

                      {/* Pulsanti Azione per Sottoargomento (Modulo) nel div Overlay */}
                      {overlayNode.type === 'module' && (
                        <div className="ai-overlay-actions-section" style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <button
                            type="button"
                            className="ai-overlay-btn"
                            style={{ background: 'rgba(0, 210, 255, 0.16)', borderColor: 'rgba(0, 210, 255, 0.4)', color: '#00d2ff', fontSize: '0.65rem', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, width: '100%' }}
                            onClick={() => {
                              handleCreateSubTopic(overlayNode.data);
                              setShowAiOverlay(false);
                            }}
                          >
                            ➕ Nuovo Sottoargomento
                          </button>

                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="ai-overlay-btn"
                              style={{ flex: 1, background: 'rgba(210, 153, 34, 0.1)', borderColor: 'rgba(210, 153, 34, 0.25)', color: '#d29922', fontSize: '0.6rem', padding: '5px', borderRadius: '6px', cursor: 'pointer' }}
                              onClick={() => {
                                handleRenameModule(overlayNode.data, overlayNode.topicId);
                                setShowAiOverlay(false);
                              }}
                            >
                              ✏️ Rinomina
                            </button>
                            <button
                              type="button"
                              className="ai-overlay-btn"
                              style={{ flex: 1, background: 'rgba(255, 85, 85, 0.08)', borderColor: 'rgba(255, 85, 85, 0.2)', color: '#ff5555', fontSize: '0.6rem', padding: '5px', borderRadius: '6px', cursor: 'pointer' }}
                              onClick={() => {
                                handleDeleteModule(overlayNode.data, overlayNode.topicId);
                                setShowAiOverlay(false);
                              }}
                            >
                              🗑️ Elimina
                            </button>
                          </div>
                        </div>
                      )}

                  {/* Lista File Esistenti nel Nodo */}
                  {(() => {
                    const nodeFiles = [];
                    if (overlayNode.data) {
                      ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
                        (overlayNode.data[cat] || []).forEach(f => {
                          const path = typeof f === 'string' ? f : f.path || f.filePath;
                          const name = path ? path.split('/').pop() : f.name || f;
                          if (path) nodeFiles.push({ name, path, category: cat });
                        });
                      });
                    }

                    if (nodeFiles.length === 0) return null;

                    return (
                      <div className="ai-overlay-group" style={{ marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        <span className="ai-overlay-label">📄 File Esistenti ({nodeFiles.length})</span>
                        <div style={{ maxHeight: '110px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', background: 'rgba(0,0,0,0.2)', padding: '6px', borderRadius: '6px' }}>
                          {nodeFiles.map((fileItem, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.6rem', color: '#c5c9db', background: 'rgba(255,255,255,0.03)', padding: '3px 6px', borderRadius: '4px' }}>
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }} title={fileItem.path}>
                                📄 {escapeStr(fileItem.name)}
                              </span>
                              <div style={{ display: 'flex', gap: '4px' }}>
                                <button
                                  type="button"
                                  style={{ background: 'rgba(0,210,255,0.12)', border: '1px solid rgba(0,210,255,0.25)', color: '#00d2ff', padding: '1px 5px', borderRadius: '3px', cursor: 'pointer', fontSize: '0.55rem' }}
                                  onClick={() => {
                                    if (onOpenFile) onOpenFile(fileItem.path);
                                    setShowAiOverlay(false);
                                  }}
                                  title="Apri file"
                                >
                                  👁️
                                </button>
                                <button
                                  type="button"
                                  style={{ background: 'rgba(255,85,85,0.12)', border: '1px solid rgba(255,85,85,0.25)', color: '#ff5555', padding: '1px 5px', borderRadius: '3px', cursor: 'pointer', fontSize: '0.55rem' }}
                                  onClick={async () => {
                                    await handleDeleteFile(fileItem.path);
                                    setShowAiOverlay(false);
                                  }}
                                  title="Elimina file"
                                >
                                  🗑️
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Creazione File abilitata per Argomenti e Sottoargomenti */}
                  <>
                      <div style={{ fontSize: '0.5rem', fontWeight: 600, color: '#5a5e72', letterSpacing: '0.5px', marginBottom: '6px', textTransform: 'uppercase' }}>
                        CREA NUOVO FILE DENTRO QUESTO SOTTOARGOMENTO
                      </div>

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
                            <option value="scripts">⚡ Script / Codice</option>
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
                              <span className="ai-overlay-label">Ruolo Agente (Associato Automaticamente)</span>
                              <div style={{ padding: '6px 10px', background: 'rgba(0, 210, 255, 0.08)', border: '1px solid rgba(0, 210, 255, 0.25)', borderRadius: '6px', fontSize: '0.68rem', color: '#00d2ff', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                                🤖 {selectedAiRole === 'math1' ? '🔬 Math Architect (Teoria)' : selectedAiRole === 'code_architect' ? '💻 Code Architect (Script)' : selectedAiRole === 'viz-designer' ? '🎨 Viz Designer (Visualizzazione)' : '👁️ Proof Reviewer (Documentazione)'}
                              </div>
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
                              creationTab === 'ai' ? '🤖 Genera' : creationTab === 'upload' ? '📎 Carica' : '📄 Crea File'
                            )}
                          </button>
                        </div>
                      </form>
                    </>
                  </>
                )}
              </>
            )}
            </div>
          )}
        </div>
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
            {/* Top-Level Main Topics Section */}
            <div className="explorer-section">
              <div className="explorer-section-header" onClick={() => setExpandedTopicsSection(!expandedTopicsSection)}>
                <span>{expandedTopicsSection ? '▼' : '▶'} 🌐 ARGOMENTI PRINCIPALI ({topLevelTopics.length})</span>
              </div>
              {expandedTopicsSection && (
                <div className="explorer-section-content">
                  {filteredTopLevelTopics.length === 0 && (
                    <div style={{ fontSize: '0.6rem', color: '#5a5e72', padding: '6px 10px' }}>Nessun argomento trovato.</div>
                  )}
                  {filteredTopLevelTopics.map(topic => {
                    const subCount = topicsData.filter(s => s.parent_id === topic.id).length;
                    return (
                      <div 
                        key={topic.id} 
                        className={`explorer-topic-item ${activeTopicId === topic.id ? 'active' : ''}`}
                        onClick={() => selectTopic(topic)}
                      >
                        <span className="explorer-topic-icon">{topicIcon(topic.domain)}</span>
                        <span className="explorer-topic-name">{escapeStr(topic.name)}</span>
                        <span className="explorer-topic-count" title={`${subCount} sottoargomenti`}>{subCount}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Active Topic & Its Subtopics Section */}
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

                  {/* Active topic controls */}
                  <div className="active-topic-controls" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px', alignItems: 'center' }}>
                    <button 
                      className="btn-new-subtopic" 
                      onClick={() => handleCreateSubTopic(activeTopic)} 
                      title="Crea nuovo sottoargomento dentro questo argomento"
                      style={{ padding: '4px 8px', fontSize: '0.6rem', background: 'rgba(0,210,255,0.12)', color: '#00d2ff', border: '1px solid rgba(0,210,255,0.3)', borderRadius: '6px', cursor: 'pointer', fontWeight: 600 }}
                    >
                      ➕ Nuovo Sottoargomento
                    </button>
                    {topicsData.length > 1 && (
                      <select 
                        value={activeTopic.parent_id || ''} 
                        onChange={e => handleUpdateTopicParent(activeTopic, e.target.value)}
                        title="Seleziona argomento padre"
                        style={{ background: '#0e1016', color: '#bc8cff', border: '1px solid rgba(188,140,255,0.3)', borderRadius: '6px', padding: '3px 6px', fontSize: '0.6rem', outline: 'none' }}
                      >
                        <option value="">— Nessun Padre —</option>
                        {topicsData.filter(t => t.id !== activeTopic.id).map(t => (
                          <option key={t.id} value={t.id}>⬆ Padre: {escapeStr(t.name)}</option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>

                <div className="explorer-section-header" style={{ marginTop: '12px' }}>
                  <span>📂 SOTTOARGOMENTI DI {escapeStr(activeTopic.name).toUpperCase()} ({activeTopicSubtopics.length})</span>
                </div>

                <div className="folder-tree">
                  {activeTopicSubtopics.length === 0 && (
                    <div style={{ fontSize: '0.6rem', color: '#5a5e72', padding: '8px 0', fontStyle: 'italic' }}>
                      Nessun sottoargomento presente. Clicca "➕ Nuovo Sottoargomento" per crearne uno.
                    </div>
                  )}
                  {activeTopicSubtopics.map(subtopic => {
                    const subId = subtopic.id;
                    const isSubExpanded = searchQuery ? true : expandedModules[subId];
                    const isSubSelected = selectedNode && (selectedNode.data?.id === subtopic.id);

                    const toggleSubtopic = () => {
                      setExpandedModules(prev => ({ ...prev, [subId]: !prev[subId] }));
                      setSelectedNode({ type: 'module', data: subtopic, topicId: subtopic.id });
                      focusNodeOnGraph(subtopic.id);
                    };

                    // Count attached files directly inside subtopic
                    let totalFiles = 0;
                    ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
                      totalFiles += (subtopic[cat] || []).length;
                    });

                    const folderPath = subtopic.folder || `data/${subtopic.id}`;

                    return (
                      <div key={subtopic.id} className="folder-item">
                        <div 
                          className={`folder-header ${isSubSelected ? 'selected-folder' : ''}`}
                          onClick={toggleSubtopic}
                          style={{
                            background: isSubSelected ? 'rgba(0,210,255,0.08)' : 'transparent',
                            color: isSubSelected ? '#00d2ff' : '#8b8fa3'
                          }}
                        >
                          <span className="folder-header-title">
                            <span>{isSubExpanded ? '📂' : '📁'}</span>
                            <span>{escapeStr(subtopic.name)}</span>
                            <span className="folder-header-count">({totalFiles})</span>
                          </span>
                          
                          <div className="folder-actions">
                            <button 
                              className="folder-action-btn"
                              onClick={(e) => { e.stopPropagation(); handleCreateSubTopic(subtopic); }}
                              title="Crea sotto-sottoargomento dentro questo sottoargomento"
                              style={{ color: '#00d2ff', fontWeight: 'bold' }}
                            >
                              ➕
                            </button>
                            <button 
                              className="folder-action-btn"
                              onClick={(e) => { e.stopPropagation(); handleMoveModule(subtopic, activeTopic.id); }}
                              title="Sposta sottoargomento in un altro Argomento"
                            >
                              ⇄
                            </button>
                            <button 
                              className="folder-action-btn"
                              onClick={(e) => { e.stopPropagation(); handleRenameModule(subtopic, activeTopic.id); }}
                              title="Rinomina Sottoargomento"
                            >
                              ✏️
                            </button>
                            <button 
                              className="folder-action-btn del"
                              onClick={(e) => { e.stopPropagation(); handleDeleteModule(subtopic, activeTopic.id); }}
                              title="Elimina Sottoargomento"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>

                        {isSubExpanded && (
                          <div className="folder-contents">
                            {totalFiles === 0 && (
                              <div style={{ fontStyle: 'italic', color: '#5a5e72', fontSize: '0.6rem', padding: '6px 12px' }}>
                                Nessun file presente in questo sottoargomento.
                              </div>
                            )}
                            {columnDefs.map(col => {
                              const files = subtopic[col.key] || [];
                              if (files.length === 0) return null;

                              const catKey = `${subtopic.id}-${col.key}`;
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
                                      {files.map((file, idx) => {
                                        const filePath = typeof file === 'string' ? file : file.path || file.filePath;
                                        const fileName = typeof file === 'string' ? file.split('/').pop() : file.name || file.filename;
                                        return (
                                          <div key={filePath || idx} className="file-tree-item">
                                            <span className="explorer-topic-icon" style={{ background: 'none', width: 'auto', height: 'auto' }}>{col.icon}</span>
                                            <span className="file-tree-name" onClick={() => onOpenFile && onOpenFile(filePath)}>
                                              {escapeStr(fileName)}
                                            </span>
                                            
                                            <div className="file-tree-actions">
                                              <button 
                                                className="file-tree-del-btn"
                                                onClick={(e) => { e.stopPropagation(); handleDeleteFile(filePath); }}
                                                title="Elimina file"
                                              >
                                                🗑️
                                              </button>
                                            </div>
                                          </div>
                                        );
                                      })}
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
