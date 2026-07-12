import { useState, useRef, useCallback, useEffect } from 'react';

// ==============================================================================
// useResearchPipeline — Hook centrale per il Research Lab multi-agente
// Gestisce: definizione pipeline, esecuzione SSE, stato agenti, cicli, history
// Configurazione agenti (provider/modello/temp) e test connessione
// Supporto duale: /api/chat/orchestrate + /api/chat/pipeline/start
// ==============================================================================

// --- Provider options available to agents ---
const PROVIDER_OPTIONS = [
  {
    id: 'deepseek',
    label: 'DeepSeek',
    models: ['deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner', 'deepseek-coder', 'deepseek-v4-pro'],
    defaultModel: 'deepseek-v4-flash',
    defaultTemp: 0.4,
    apiKeyRequired: true,
  },
  {
    id: 'ollama',
    label: 'Ollama (Locale)',
    models: ['llama3.2', 'qwen3.6', 'gemma2', 'mistral', 'phi3'],
    defaultModel: 'llama3.2',
    defaultTemp: 0.7,
    apiKeyRequired: false,
  },
  {
    id: 'openai',
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o3-mini'],
    defaultModel: 'gpt-4o-mini',
    defaultTemp: 0.7,
    apiKeyRequired: true,
  },
  {
    id: 'anthropic',
    label: 'Anthropic (Claude)',
    models: ['claude-sonnet-4', 'claude-3-5-sonnet', 'claude-3-opus'],
    defaultModel: 'claude-sonnet-4',
    defaultTemp: 0.7,
    apiKeyRequired: true,
  },
];

// --- Default config for each agent (deepseek-v4-flash) ---
const DEFAULT_AGENT_CONFIG = {
  provider: 'deepseek',
  model: 'deepseek-v4-flash',
  temperature: 0.4,
};

// --- All 7 registered agents with colors, icons, roles ---
const AGENTS_META = {
  sigma_architect: { bg: '#7c5bf0', color: '#ffffff', icon: '🏗️', short: 'Arch', name: 'Sigma AI Architect', role: 'architect', image: '/images/agente0.png', manifesto: 'sigma0/sigma_architect.md' },
  math1: { bg: '#3fb950', color: '#ffffff', icon: '∑', short: 'Math', name: 'Sigma Math Researcher', role: 'researcher', image: '/images/matematicoAi.png', manifesto: '' },
  code_architect: { bg: '#00d2ff', color: '#0e1016', icon: '⚙️', short: 'Code', name: 'Sigma Code Architect', role: 'developer', image: '/images/programmatoreAi.png', manifesto: '' },
  'math-collatz': { bg: '#2ea043', color: '#ffffff', icon: '🧮', short: 'Math', name: 'Matematico Specialista', role: 'mathematician', image: '/images/default.png', manifesto: '' },
  'test-engineer': { bg: '#58a6ff', color: '#0e1016', icon: '🧪', short: 'Test', name: 'Ingegnere dei Test', role: 'tester', image: '/images/default.png', manifesto: '' },
  'viz-designer': { bg: '#d29922', color: '#0e1016', icon: '📊', short: 'Viz', name: 'Visualizzatore D3.js', role: 'visualizer', image: '/images/default.png', manifesto: '' },
  'proof-reviewer': { bg: '#ff5555', color: '#ffffff', icon: '🔍', short: 'Review', name: 'Revisore e Confutatore', role: 'reviewer', image: '/images/default.png', manifesto: '' },
};

// --- Pipeline Templates ---
const PIPELINE_TEMPLATES = {
  none: { label: '— Personalizzata —', agents: [] },
  math_research: {
    label: '∑ Ricerca Matematica',
    goal: 'Ricerca matematica assistita: formulazione teoremi, dimostrazioni, test computazionali, visualizzazioni e validazione formale.',
    agents: [
      { id: 'math1', enabled: true, order: 0 },
      { id: 'test-engineer', enabled: true, order: 1 },
      { id: 'viz-designer', enabled: true, order: 2 },
      { id: 'proof-reviewer', enabled: true, order: 3 },
    ],
    use_pipeline_engine: false,
  },
  full_analysis: {
    label: '📋 Analisi Completa Multi-Agente',
    goal: 'Analizzare il problema in modo completo: pianificazione, ricerca, sviluppo test, visualizzazione e revisione critica finale.',
    agents: [
      { id: 'sigma_architect', enabled: true, order: 0 },
      { id: 'math1', enabled: true, order: 1 },
      { id: 'code_architect', enabled: true, order: 2 },
      { id: 'viz-designer', enabled: true, order: 3 },
      { id: 'proof-reviewer', enabled: true, order: 4 },
    ],
    use_pipeline_engine: false,
  },
  code_review: {
    label: '⚙️ Code Review & Refactoring',
    goal: 'Revisione completa del codice: analisi, refactoring, test, ottimizzazione e documentazione tecnica.',
    agents: [
      { id: 'code_architect', enabled: true, order: 0 },
      { id: 'sigma_architect', enabled: true, order: 1 },
      { id: 'proof-reviewer', enabled: true, order: 2 },
    ],
    use_pipeline_engine: false,
  },
};

const DEFAULT_AGENTS = [
  { id: 'sigma_architect', enabled: true, order: 0 },
  { id: 'math1', enabled: true, order: 1 },
  { id: 'code_architect', enabled: true, order: 2 },
];

export default function useResearchPipeline(onTasksUpdated, addToast) {
  // --- Template ---
  const [activeTemplate, setActiveTemplate] = useState('none');

  // --- Pipeline Definition ---
  const [pipelineAgents, setPipelineAgents] = useState(DEFAULT_AGENTS);
  const [pipelineGoal, setPipelineGoal] = useState('');
  const [pipelineStrategy, setPipelineStrategy] = useState('sequential');
  const [maxCycles, setMaxCycles] = useState(5);
  const [autoApprove, setAutoApprove] = useState(true);
  const [usePipelineEngine, setUsePipelineEngine] = useState(false);
  const [pipelinePath, setPipelinePath] = useState('');

  // --- Agent Configurations (provider, model, temperature per agent) ---
  const [agentConfigs, setAgentConfigs] = useState({});

  // --- Connection Test States ---
  const [testStates, setTestStates] = useState({}); // agent_id -> { testing, success, error, latency }
  const testAbortRef = useRef({});

  // --- Selected agent for configuration panel ---
  const [selectedAgentId, setSelectedAgentId] = useState(null);

  // --- Pipeline Execution State ---
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [agentStates, setAgentStates] = useState({});
  const [currentCycle, setCurrentCycle] = useState(0);
  const [totalCycles, setTotalCycles] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [pipelineActionsLog, setPipelineActionsLog] = useState([]);
  const [pipelineError, setPipelineError] = useState(null);
  const [agentReports, setAgentReports] = useState({});
  const [memorySnapshots, setMemorySnapshots] = useState({});
  const [feedbackCycles, setFeedbackCycles] = useState(0);
  const [agentResponses, setAgentResponses] = useState([]); // [{agent_id, response, timestamp}]

  // --- Pipeline ID — persistent across page reloads ---
  const [pipelineId, setPipelineId] = useState(() => {
    try {
      const saved = localStorage.getItem('research_pipeline_id');
      if (saved) return saved;
    } catch (e) {}
    const id = 'pipeline_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '_' + Date.now().toString(36);
    try { localStorage.setItem('research_pipeline_id', id); } catch (e) {}
    return id;
  });

  // --- Chat persistence functions ---
  const saveChatMessage = useCallback(async (agentId, message, msgType = 'action', actions = null) => {
    try {
      await fetch('/api/context/chat_message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pipeline_id: pipelineId,
          agent_id: agentId,
          message: message?.slice(0, 2000),
          message_type: msgType,
          actions: actions || [],
          timestamp: new Date().toISOString(),
        }),
      });
    } catch (e) {
      console.error('[ChatPersistence] Save error:', e);
    }
  }, [pipelineId]);

  const loadChatMessages = useCallback(async () => {
    try {
      const res = await fetch(`/api/context/chat_log?pipeline_id=${encodeURIComponent(pipelineId)}&limit=500`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.messages || [];
    } catch (e) {
      console.error('[ChatPersistence] Load error:', e);
      return [];
    }
  }, [pipelineId]);

  // --- Pipeline History ---
  const [pipelineHistory, setPipelineHistory] = useState([]);

  // --- Refs ---
  const abortRef = useRef(null);
  const statusRef = useRef('idle');
  const cycleRef = useRef(0);

  useEffect(() => { statusRef.current = pipelineStatus; }, [pipelineStatus]);
  useEffect(() => { cycleRef.current = currentCycle; }, [currentCycle]);

  // --- Agent Display ---
  const enabledAgents = pipelineAgents.filter(a => a.enabled).sort((a, b) => a.order - b.order);

  const getAgentColor = (agentId) => AGENTS_META[agentId] || { bg: '#8b8fa3', color: '#fff', icon: '🤖', short: 'AI', name: agentId };

  const getAgentConfig = useCallback((agentId) => {
    return agentConfigs[agentId] || DEFAULT_AGENT_CONFIG;
  }, [agentConfigs]);

  const toggleAgent = (agentId) => {
    setPipelineAgents(prev => prev.map(a => a.id === agentId ? { ...a, enabled: !a.enabled } : a));
  };

  const reorderAgent = (agentId, newOrder) => {
    setPipelineAgents(prev => prev.map(a => a.id === agentId ? { ...a, order: newOrder } : a));
  };

  // --- Agent Configuration ---
  const updateAgentConfig = useCallback((agentId, configUpdates) => {
    setAgentConfigs(prev => ({
      ...prev,
      [agentId]: { ...(prev[agentId] || DEFAULT_AGENT_CONFIG), ...configUpdates }
    }));
  }, []);

  // --- Load agent configs from session data (persisted settings) ---
  const loadSessionConfigs = useCallback((sessionAgents) => {
    if (!sessionAgents || !Array.isArray(sessionAgents)) return;
    const configs = {};
    sessionAgents.forEach(agent => {
      const aid = agent.agent_id || agent.id;
      if (!aid) return;
      configs[aid] = {
        provider: agent.provider || DEFAULT_AGENT_CONFIG.provider,
        model: agent.model || DEFAULT_AGENT_CONFIG.model,
        temperature: agent.temperature ?? DEFAULT_AGENT_CONFIG.temperature,
        manifesto: agent.manifesto || '',
      };
    });
    setAgentConfigs(prev => ({ ...prev, ...configs }));
  }, []);

  // --- Connection Test ---
  const testAgentConnection = useCallback(async (agentId) => {
    const config = agentConfigs[agentId] || DEFAULT_AGENT_CONFIG;
    
    // Abort any existing test for this agent
    if (testAbortRef.current[agentId]) {
      testAbortRef.current[agentId].abort();
    }
    
    const controller = new AbortController();
    testAbortRef.current[agentId] = controller;
    
    setTestStates(prev => ({
      ...prev,
      [agentId]: { testing: true, success: false, error: null, latency: null }
    }));
    
    const startTime = Date.now();
    
    try {
      // Call /api/config to get the API key for the selected provider
      const configRes = await fetch('/api/config', { signal: controller.signal });
      if (!configRes.ok) throw new Error('Config API non raggiungibile');
      
      const configData = await configRes.json();
      const providers = configData?.ai?.providers || {};
      const provConfig = providers[config.provider] || {};
      const apiKey = provConfig.api_key || '';
      
      // Now test by calling the chat API directly with a simple ping
      const testRes = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'Rispondi solo "OK" senza aggiungere altro testo.',
          mode: 'ask',
          model: config.model,
          provider: config.provider,
          temperature: config.temperature,
          max_tokens: 100,
          allow_actions: false,
        }),
        signal: controller.signal,
      });
      
      if (!testRes.ok) throw new Error(`HTTP ${testRes.status}`);
      
      const testResult = await testRes.json();
      const responseText = (testResult.response || testResult.content || '').trim();
      const latency = Date.now() - startTime;
      
      if (!responseText) throw new Error('Risposta vuota dal modello');
      
      setTestStates(prev => ({
        ...prev,
        [agentId]: {
          testing: false,
          success: true,
          error: null,
          latency,
          response: responseText.slice(0, 100),
        }
      }));
    } catch (e) {
      if (e.name === 'AbortError') return;
      setTestStates(prev => ({
        ...prev,
        [agentId]: {
          testing: false,
          success: false,
          error: e.message,
          latency: null,
        }
      }));
    }
  }, [agentConfigs]);

  // --- Select agent for configuration ---
  const selectAgentForConfig = useCallback((agentId) => {
    setSelectedAgentId(prev => prev === agentId ? null : agentId);
  }, []);

  const closeAgentConfig = useCallback(() => {
    setSelectedAgentId(null);
  }, []);

  // --- Template Selector ---
  const selectTemplate = useCallback((templateId) => {
    const template = PIPELINE_TEMPLATES[templateId];
    if (!template) return;
    setActiveTemplate(templateId);
    if (template.agents && template.agents.length > 0) {
      setPipelineAgents(template.agents);
      // Reset configs for new agents
      const configs = {};
      template.agents.forEach(a => {
        configs[a.id] = DEFAULT_AGENT_CONFIG;
      });
      setAgentConfigs(configs);
    }
    if (template.goal) {
      setPipelineGoal(template.goal);
    }
    setUsePipelineEngine(template.use_pipeline_engine || false);
    setPipelinePath(template.pipeline_path || '');
    // Reset state
    setPipelineStatus('idle');
    setAgentStates({});
    setPipelineActionsLog([]);
    setPipelineError(null);
    setAgentReports({});
    setMemorySnapshots({});
    setFeedbackCycles(0);
    setTestStates({});
    setSelectedAgentId(null);
  }, []);

  const getTemplateList = useCallback(() => {
    return Object.entries(PIPELINE_TEMPLATES).map(([id, t]) => ({
      id,
      label: t.label,
      hasGoal: !!t.goal,
      agentCount: t.agents?.length || 0,
      useEngine: t.use_pipeline_engine || false,
    }));
  }, []);

  // --- SSE Handler ---
  const handleSSEEvent = useCallback((event) => {
    const type = event.type;

    // --- Pipeline Engine Events ---
    if (type === 'pipeline_start') {
      setPipelineStatus('planning');
      setCurrentCycle(0);
      setCurrentStep(0);
      setPipelineActionsLog([]);
      setAgentReports({});
      setPipelineError(null);
      setFeedbackCycles(0);
    } else if (type === 'pipeline_node_start') {
      setCurrentStep(prev => prev + 1);
      setPipelineStatus('running');
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: {
          ...prev[event.agent_id],
          status: 'active',
          task: event.node_label,
          feedback_iteration: event.feedback_iteration || 1,
        }
      }));
    } else if (type === 'pipeline_node_iteration') {
      setAgentStates(prev => ({
        ...prev,
        [event.node_id]: {
          ...prev[event.node_id],
          status: 'active',
          progress: `${event.success_count}/${event.success_count + event.fail_count} azioni`,
          actions_count: (prev[event.node_id]?.actions_count || 0) + event.success_count + event.fail_count,
        }
      }));
      if (event.actions_log) {
        setPipelineActionsLog(prev => [...prev, ...event.actions_log]);
      }
    } else if (type === 'pipeline_node_complete') {
      setAgentStates(prev => ({
        ...prev,
        [event.node_id]: {
          ...prev[event.node_id],
          status: event.success ? 'done' : 'failed',
          total_actions: event.total_actions,
          successful_actions: event.successful_actions,
        }
      }));
    } else if (type === 'pipeline_node_error') {
      setAgentStates(prev => ({
        ...prev,
        [event.node_id]: { ...prev[event.node_id], status: 'failed', error: event.error }
      }));
    } else if (type === 'pipeline_review_start') {
      setAgentStates(prev => ({
        ...prev,
        [event.node_id]: { ...prev[event.node_id], status: 'active', task: 'Revisione in corso...' }
      }));
    } else if (type === 'pipeline_review_complete') {
      setAgentStates(prev => ({
        ...prev,
        [event.node_id]: {
          ...prev[event.node_id],
          status: event.needs_correction ? 'failed' : 'done',
          review_notes: event.review_notes,
        }
      }));
    } else if (type === 'pipeline_feedback_loop') {
      setFeedbackCycles(prev => prev + 1);
      if (addToast) {
        addToast(`🔄 Feedback loop: ${event.from_node} → ${event.to_node} (iter. ${event.iteration})`, 'info', 3000);
      }
    } else if (type === 'pipeline_feedback_max') {
      if (addToast) addToast(event.message, 'warning', 5000);
    } else if (type === 'pipeline_progress') {
      setCurrentStep(event.completed);
      setTotalSteps(event.total);
    } else if (type === 'pipeline_done') {
      setPipelineStatus('done');
      setCurrentCycle(event.report?.nodes_completed || 0);
      setTotalCycles(event.report?.total_nodes || 0);
      setCurrentStep(event.report?.nodes_completed || 0);
      setTotalSteps(event.report?.total_nodes || 0);
      if (event.report) {
        setPipelineHistory(prev => [...prev, event.report]);
        const snapshots = {};
        const nodeResults = event.report.node_results || {};
        Object.entries(nodeResults).forEach(([nodeId, result]) => {
          if (result && result.agent_id) {
            snapshots[result.agent_id] = {
              actions: result.successful_actions || 0,
              errors: result.failed_actions || 0,
              files_created: (result.actions_log || []).filter(a => a.type === 'create_file' && a.success).length,
              tests_passed: (result.actions_log || []).filter(a => a.type === 'run_test' && a.success).length,
              feedback_iteration: result.feedback_iteration || 0,
            };
          }
        });
        setMemorySnapshots(snapshots);
      }
      const fbCycles = event.report?.feedback_cycles || 0;
      setFeedbackCycles(fbCycles);
      if (addToast) {
        addToast(`🎯 Pipeline completata: ${fbCycles > 0 ? `${fbCycles} cicli feedback, ` : ''}${event.report?.nodes_completed}/${event.report?.total_nodes} nodi`, 'success', 5000);
      }
      if (onTasksUpdated) onTasksUpdated();
    } else if (type === 'pipeline_error') {
      setPipelineStatus('error');
      setPipelineError(event.error);
      if (addToast) addToast(`❌ Errore pipeline: ${event.error}`, 'error', 8000);
    } else if (type === 'pipeline_validation_error') {
      if (addToast) addToast(`⚠️ Validazione: ${event.errors?.join('; ')}`, 'warning', 4000);
    }

    // --- Orchestrate Events (fallback) ---
    else if (type === 'orchestrate_start') {
      setPipelineStatus('planning');
      setCurrentCycle(0);
      setPipelineActionsLog([]);
      setAgentReports({});
      setPipelineError(null);
      setFeedbackCycles(0);
    } else if (type === 'orchestrate_plan') {
      setPipelineStatus('running');
      setTotalSteps(event.total_subtasks || 0);
      setCurrentStep(0);
      const states = {};
      (event.subtasks || []).forEach(st => {
        states[st.agent_id] = { status: 'pending', task: st.task, progress: '', actions_count: 0 };
      });
      setAgentStates(states);
    } else if (type === 'orchestrate_subtask_start') {
      setCurrentStep(prev => prev + 1);
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: { ...prev[event.agent_id], status: 'active', task: event.task }
      }));
    } else if (type === 'agent_task_thinking') {
      // Immediately set agent to active so frontend shows typing indicator
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: { ...prev[event.agent_id], status: 'active', task: event.task || prev[event.agent_id]?.task || 'Analisi in corso...' }
      }));
    } else if (type === 'agent_task_start') {
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: { ...prev[event.agent_id], status: 'active', task: event.task || prev[event.agent_id]?.task }
      }));
    } else if (type === 'agent_task_iteration') {
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: {
          ...prev[event.agent_id],
          status: 'active',
          progress: `${event.success_count}/${event.success_count + event.fail_count} azioni`,
          actions_count: (prev[event.agent_id]?.actions_count || 0) + event.success_count + event.fail_count,
        }
      }));
      if (event.actions_log) {
        setPipelineActionsLog(prev => [...prev, ...event.actions_log]);
      }
      // Capture full response text (thinking + response)
      const respText = event.full_response || event.ai_response || '';
      if (respText.trim()) {
        setAgentResponses(prev => [...prev, {
          agent_id: event.agent_id || 'unknown',
          response: respText,
          timestamp: new Date().toISOString(),
        }]);
      }
    } else if (type === 'agent_task_error') {
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: { ...prev[event.agent_id], status: 'failed', error: event.error }
      }));
    } else if (type === 'orchestrate_subtask_complete') {
      setAgentStates(prev => ({
        ...prev,
        [event.agent_id]: { 
          ...prev[event.agent_id], 
          status: event.success ? 'done' : 'failed',
          error: event.error || null,
          error_detail: event.error || null,
        }
      }));
    } else if (type === 'orchestrate_phase' && event.phase === 'execute') {
      setTotalCycles(prev => prev + 1);
    } else if (type === 'orchestrate_done') {
      setPipelineStatus('done');
      setCurrentCycle(event.report?.total_subtasks || 0);
      setCurrentStep(event.report?.total_subtasks || 0);
      setTotalSteps(event.report?.total_subtasks || 0);
      if (event.report) {
        setPipelineHistory(prev => [...prev, event.report]);
      }
      if (addToast) {
        addToast(`🎯 Pipeline completata: ${event.report?.subtasks_completed}/${event.report?.total_subtasks} task`, 'success', 5000);
      }
      if (onTasksUpdated) onTasksUpdated();
    } else if (type === 'orchestrate_error') {
      setPipelineStatus('error');
      setPipelineError(event.error);
      if (addToast) addToast(`❌ Errore pipeline: ${event.error}`, 'error', 8000);
    } else if (type === 'error') {
      setPipelineStatus('error');
      setPipelineError(event.error || event.message);
    }
  }, [addToast, onTasksUpdated]);

  // --- Start Pipeline ---
  const startPipeline = useCallback(async () => {
    if (!pipelineGoal.trim() || pipelineStatus === 'running') return;

    const controller = new AbortController();
    abortRef.current = controller;
    setPipelineStatus('planning');
    setCurrentCycle(0);
    setTotalCycles(0);
    setPipelineActionsLog([]);
    setAgentReports({});
    setPipelineError(null);
    setFeedbackCycles(0);
    setMemorySnapshots({});

    const useEngine = usePipelineEngine && pipelinePath;
    const endpoint = useEngine ? '/api/chat/pipeline/start' : '/api/chat/orchestrate';

    try {
      // Include agent configs so backend uses per-agent provider/model/temperature
      const configsArray = {};
      Object.entries(agentConfigs).forEach(([id, cfg]) => {
        configsArray[id] = cfg;
      });

      const body = useEngine ? {
        pipeline_path: pipelinePath,
        goal: pipelineGoal.trim(),
        agent_configs: configsArray,
        max_execution_minutes: 60,
      } : {
        message: pipelineGoal.trim(),
        strategy: pipelineStrategy,
        max_iterations: maxCycles * 5,
        agent_configs: configsArray,
      };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        setPipelineStatus('error');
        setPipelineError(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let done = false;

      while (!done) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') { done = true; break; }
            try {
              handleSSEEvent(JSON.parse(payload));
            } catch (e) { continue; }
          }
          if (done) break;
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        console.error('[ResearchLab] Pipeline error:', e.message);
        setPipelineStatus('error');
        setPipelineError(e.message);
        // Update ref synchronously so finally block doesn't overwrite
        statusRef.current = 'error';
      }
    } finally {
      // CRITICAL: Never overwrite 'error' state with 'done'
      // statusRef may still be 'planning' due to async React batching,
      // so we check the actual state via the updater function
      setPipelineStatus(prev => {
        if (prev === 'error' || prev === 'done') return prev;
        // If it was 'planning' and no error occurred, mark as 'done'
        if (prev === 'planning') return 'done';
        // If something else (idle, etc.), keep as is
        return prev;
      });
      abortRef.current = null;
    }
  }, [pipelineGoal, pipelineStrategy, maxCycles, usePipelineEngine, pipelinePath, handleSSEEvent]);

  // --- Stop Pipeline ---
  const stopPipeline = useCallback(async () => {
    if (usePipelineEngine && pipelinePath) {
      try {
        await fetch('/api/chat/pipeline/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: 'current' }),
        });
      } catch (e) { /* ignore */ }
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setPipelineStatus('idle');
  }, [usePipelineEngine, pipelinePath]);

  // --- Reset ---
  const resetPipeline = useCallback(() => {
    stopPipeline();
    setPipelineGoal('');
    setPipelineStatus('idle');
    setCurrentCycle(0);
    setTotalCycles(0);
    setAgentStates({});
    setPipelineActionsLog([]);
    setPipelineError(null);
    setAgentReports({});
    setMemorySnapshots({});
    setFeedbackCycles(0);
    setActiveTemplate('none');
    setPipelineAgents(DEFAULT_AGENTS);
    setUsePipelineEngine(false);
    setPipelinePath('');
    setTestStates({});
    setSelectedAgentId(null);
  }, [stopPipeline]);

  // --- Resume ---
  const resumePipeline = useCallback(() => {
    if (pipelineGoal.trim()) {
      startPipeline();
    }
  }, [pipelineGoal, startPipeline]);

  return {
    // Pipeline definition
    pipelineAgents, setPipelineAgents,
    pipelineGoal, setPipelineGoal,
    pipelineStrategy, setPipelineStrategy,
    maxCycles, setMaxCycles,
    autoApprove, setAutoApprove,
    enabledAgents,
    usePipelineEngine, pipelinePath,

    // Agent configuration
    agentConfigs, setAgentConfigs,
    getAgentConfig, updateAgentConfig,
    selectedAgentId, selectAgentForConfig, closeAgentConfig,
    testStates, testAgentConnection,

    // Templates
    activeTemplate, selectTemplate, getTemplateList,
    PIPELINE_TEMPLATES,

    // Pipeline state
    pipelineStatus,
    agentStates,
    currentCycle, totalCycles,
    currentStep, totalSteps,
    pipelineActionsLog,
    pipelineError,
    pipelineHistory,
    memorySnapshots,
    feedbackCycles,
    agentResponses,

    // Actions
    startPipeline, stopPipeline, resetPipeline, resumePipeline,
    toggleAgent, reorderAgent,
    getAgentColor,

    // Chat persistence
    pipelineId,
    saveChatMessage,
    loadChatMessages,

    // Session config loader
    loadSessionConfigs,

    // Refs
    abortRef,

    // Meta
    AGENTS_META,
    DEFAULT_AGENTS,
    PROVIDER_OPTIONS,
    DEFAULT_AGENT_CONFIG,
  };
}