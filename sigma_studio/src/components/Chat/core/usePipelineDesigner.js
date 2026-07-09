import { useState, useCallback, useRef } from 'react';

// ==============================================================================
// usePipelineDesigner — Gestione mappa interattiva della pipeline agenti
// Nodi, connessioni, condizioni, posizioni, configurazioni
// ==============================================================================

const PROVIDERS = [
  { id: 'ollama', label: 'Ollama', models: ['llama3.2', 'qwen3.6', 'gemma2', 'mistral', 'phi3'] },
  { id: 'deepseek', label: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder', 'deepseek-v4-flash'] },
  { id: 'openai', label: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'] },
  { id: 'anthropic', label: 'Anthropic', models: ['claude-sonnet-4', 'claude-3-5-sonnet', 'claude-3-opus'] },
  { id: 'google', label: 'Google Gemini', models: ['gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-1.5-pro'] },
  { id: 'mistral', label: 'Mistral AI', models: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest'] },
  { id: 'xai', label: 'xAI Grok', models: ['grok-2', 'grok-2-mini', 'grok-beta'] },
  { id: 'perplexity', label: 'Perplexity', models: ['sonar-pro', 'sonar', 'llama-3.1-sonar'] },
  { id: 'together', label: 'Together AI', models: ['mistralai/Mixtral-8x22B', 'meta-llama/Llama-3.3-70B'] },
  { id: 'qwen', label: 'Qwen', models: ['qwen-max', 'qwen-plus', 'qwen-turbo'] },
  { id: 'glm', label: 'GLM', models: ['glm-4-plus', 'glm-4-flash', 'glm-4v'] },
  { id: 'moonshot', label: 'Moonshot', models: ['moonshot-v1-8k', 'moonshot-v1-32k'] },
  { id: 'yi', label: 'Yi', models: ['yi-large', 'yi-medium', 'yi-lightning'] },
];

const AGENT_ROLES = [
  { id: 'planner', label: 'Pianificatore', icon: '📋', color: '#7c5bf0', desc: 'Analizza e suddivide il problema in sotto-task' },
  { id: 'researcher', label: 'Ricercatore', icon: '∑', color: '#3fb950', desc: 'Ricerca informazioni e produce dimostrazioni' },
  { id: 'coder', label: 'Sviluppatore', icon: '⚙️', color: '#00d2ff', desc: 'Scrive codice, test e visualizzazioni' },
  { id: 'analyst', label: 'Analista', icon: '📊', color: '#d29922', desc: 'Analizza dati e produce report' },
  { id: 'critic', label: 'Critico', icon: '🔍', color: '#ff5555', desc: 'Valuta risultati e trova errori' },
  { id: 'custom', label: 'Personalizzato', icon: '🤖', color: '#8b8fa3', desc: 'Ruolo liberamente configurabile' },
];

const CONDITION_OPERATORS = [
  { id: 'contains', label: 'Contiene' },
  { id: 'not_contains', label: 'Non contiene' },
  { id: 'equals', label: 'Uguale a' },
  { id: 'starts_with', label: 'Inizia con' },
  { id: 'regex', label: 'Regex match' },
  { id: 'gt', label: 'Maggiore di' },
  { id: 'gte', label: '≥ Maggiore uguale' },
  { id: 'lt', label: 'Minore di' },
  { id: 'lte', label: '≤ Minore uguale' },
];

const CONDITION_FIELDS = [
  { id: 'response', label: 'Testo risposta' },
  { id: 'success_count', label: 'Azioni riuscite' },
  { id: 'fail_count', label: 'Azioni fallite' },
  { id: 'actions_count', label: 'Totale azioni' },
  { id: 'has_error', label: 'Ha errori' },
];

let nodeIdCounter = 3;

function createNodeId() {
  nodeIdCounter += 1;
  return `node_${nodeIdCounter}`;
}

function createDefaultNode(x, y) {
  return {
    id: createNodeId(),
    type: 'agent',
    x: x || 100,
    y: y || 100,
    label: 'Nuovo Agente',
    config: {
      provider: 'ollama',
      model: 'llama3.2',
      temperature: 0.7,
      max_tokens: 4096,
      top_p: 0.9,
      num_ctx: 8192,
      role: 'custom',
      prompt: '',
      color: '#8b8fa3',
      icon: '🤖',
    },
    condition: {
      enabled: false,
      field: 'response',
      operator: 'contains',
      value: '',
      ifTrue: '',
      ifFalse: '',
    },
  };
}

export default function usePipelineDesigner() {
  const [nodes, setNodes] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [canvasOffset, setCanvasOffset] = useState({ x: 0, y: 0 });
  const [canvasZoom, setCanvasZoom] = useState(1);
  const [connectingFrom, setConnectingFrom] = useState(null);
  const [pipelineGoal, setPipelineGoal] = useState('');
  const isDraggingCanvas = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const selectedNode = nodes.find(n => n.id === selectedNodeId) || null;
  const availableNodes = nodes.filter(n => n.type === 'agent');

  // --- Node CRUD ---
  const addNode = useCallback((x, y) => {
    const newNode = createDefaultNode(x, y);
    setNodes(prev => [...prev, newNode]);
    setSelectedNodeId(newNode.id);
    return newNode;
  }, []);

  const removeNode = useCallback((nodeId) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setConnections(prev => prev.filter(c => c.from !== nodeId && c.to !== nodeId));
    setSelectedNodeId(prev => prev === nodeId ? null : prev);
  }, []);

  const updateNode = useCallback((nodeId, updates) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, ...updates } : n));
  }, []);

  const updateNodeConfig = useCallback((nodeId, configUpdates) => {
    setNodes(prev => prev.map(n => {
      if (n.id !== nodeId) return n;
      return { ...n, config: { ...n.config, ...configUpdates } };
    }));
  }, []);

  const updateNodeCondition = useCallback((nodeId, conditionUpdates) => {
    setNodes(prev => prev.map(n => {
      if (n.id !== nodeId) return n;
      return { ...n, condition: { ...n.condition, ...conditionUpdates } };
    }));
  }, []);

  // --- Node Position ---
  const moveNode = useCallback((nodeId, x, y) => {
    setNodes(prev => prev.map(n => n.id === nodeId ? { ...n, x, y } : n));
  }, []);

  // --- Connections ---
  const addConnection = useCallback((fromId, toId, label = '') => {
    setConnections(prev => {
      const exists = prev.find(c => c.from === fromId && c.to === toId);
      if (exists) return prev;
      return [...prev, { id: `conn_${Date.now()}`, from: fromId, to: toId, label }];
    });
  }, []);

  const removeConnection = useCallback((connId) => {
    setConnections(prev => prev.filter(c => c.id !== connId));
  }, []);

  const updateConnection = useCallback((connId, updates) => {
    setConnections(prev => prev.map(c => c.id === connId ? { ...c, ...updates } : c));
  }, []);

  // --- Canvas controls ---
  const handleCanvasWheel = useCallback((e) => {
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setCanvasZoom(prev => Math.min(Math.max(prev * delta, 0.3), 3));
  }, []);

  const handleCanvasPan = useCallback((dx, dy) => {
    setCanvasOffset(prev => ({ x: prev.x + dx, y: prev.y + dy }));
  }, []);

  // --- Clear all ---
  const clearAll = useCallback(() => {
    setNodes([]);
    setConnections([]);
    setSelectedNodeId(null);
  }, []);

  // --- Import/Export ---
  const exportPipeline = useCallback(() => {
    return { nodes, connections, pipelineGoal };
  }, [nodes, connections, pipelineGoal]);

  const importPipeline = useCallback((data) => {
    if (data.nodes) setNodes(data.nodes);
    if (data.connections) setConnections(data.connections);
    if (data.pipelineGoal) setPipelineGoal(data.pipelineGoal);
  }, []);

  // --- Build execution config from pipeline ---
  const buildExecutionConfig = useCallback(() => {
    const agentNodes = nodes.filter(n => n.type === 'agent');
    const executionNodes = agentNodes.map(n => ({
      id: n.id,
      label: n.label,
      config: n.config,
      condition: n.condition.enabled ? n.condition : null,
    }));

    return {
      goal: pipelineGoal,
      nodes: executionNodes,
      connections,
    };
  }, [nodes, connections, pipelineGoal]);

  return {
    // State
    nodes, connections, selectedNodeId, selectedNode,
    canvasOffset, canvasZoom,
    pipelineGoal, setPipelineGoal,
    connectingFrom, setConnectingFrom,
    availableNodes,

    // Providers & roles
    PROVIDERS, AGENT_ROLES,
    CONDITION_OPERATORS, CONDITION_FIELDS,

    // Node CRUD
    addNode, removeNode, updateNode, updateNodeConfig, updateNodeCondition,
    moveNode,

    // Connections
    addConnection, removeConnection, updateConnection,

    // Canvas
    handleCanvasWheel, handleCanvasPan,
    setCanvasOffset, setCanvasZoom,

    // Pipeline
    clearAll, exportPipeline, importPipeline, buildExecutionConfig,

    // Selection
    setSelectedNodeId,
  };
}