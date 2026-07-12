import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, Square, RotateCcw, ChevronRight, Cpu, Target, Layers, RefreshCw, 
  Database, GitCompare, Settings, Wifi, WifiOff, X, Sliders, MessageSquare, Send,
  Plus, Trash2, CheckCircle, Circle, ArrowRight, GitBranch, StopCircle, AlertTriangle
} from 'lucide-react';
import useResearchPipeline from './core/useResearchPipeline';

const PIPELINE_TEMPLATES = {
  math_research: {
    id: 'math_research', name: '∑ Ricerca Matematica',
    description: 'Teoria, test computazionali, visualizzazioni D3 e revisione formale',
    agents: ['math1', 'test-engineer', 'viz-designer', 'proof-reviewer'],
  },
  full_analysis: {
    id: 'full_analysis', name: '📋 Analisi Completa',
    description: 'Coordinamento, ricerca, sviluppo test, visualizzazione e revisione',
    agents: ['sigma_architect', 'math1', 'code_architect', 'viz-designer', 'proof-reviewer'],
  },
  code_review: {
    id: 'code_review', name: '⚙️ Code Review',
    description: 'Analisi codice, refactoring, test, ottimizzazione e documentazione',
    agents: ['code_architect', 'sigma_architect', 'proof-reviewer'],
  },
  general_research: {
    id: 'general_research', name: '🔬 Ricerca Generale',
    description: 'Ricerca scientifica completa con validazione e documentazione',
    agents: ['sigma_architect', 'math1', 'test-engineer', 'proof-reviewer'],
  },
};

// ==============================================================================
// AGENT CONFIG PANEL — restored from original working version
// ==============================================================================
function AgentConfigPanel({ agentId, meta, config, onUpdate, onClose, testState, onTest, agentsMeta }) {
  const isTesting = testState?.testing;
  const testSuccess = testState?.success;
  const testError = testState?.error;
  const testLatency = testState?.latency;
  const [manifesti, setManifesti] = React.useState([]);
  const [ollamaModels, setOllamaModels] = React.useState([]);
  const [saving, setSaving] = React.useState(false);
  
  React.useEffect(() => {
    fetch('/api/list_manifesti').then(r => r.json()).then(d => {
      if (d.success) setManifesti(d.manifesti || []);
    }).catch(() => {});
  }, []);
  
  // Fetch Ollama models dynamically when provider is ollama
  React.useEffect(() => {
    if (config.provider === 'ollama') {
      fetch('/api/ollama_models').then(r => r.json()).then(d => {
        if (d.success && d.models?.length > 0) {
          setOllamaModels(d.models.map(m => m.name || m.model || m));
        }
      }).catch(() => {});
    }
  }, [config.provider]);
  
  const handleSave = async () => {
    setSaving(true);
    try {
      if (typeof window !== 'undefined' && window.__activeSessionId) {
        await fetch('/api/research/update_agents', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: window.__activeSessionId,
            action: 'update',
            agent: { agent_id: agentId, provider: config.provider, model: config.model, temperature: config.temperature, manifesto: config.manifesto || '' }
          }),
        });
      }
    } catch (e) { /* ignore */ }
    setSaving(false);
    onClose();
  };
  
  return (
    <div className="agent-config-overlay" onClick={onClose}>
      <div className="agent-config-panel" onClick={e => e.stopPropagation()}>
        <div className="agent-config-header" style={{ borderBottomColor: meta.bg }}>
          <span className="agent-config-icon">{meta.icon}</span>
          <span className="agent-config-name" style={{ color: meta.bg }}>{meta.name}</span>
          <button className="agent-config-close" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="agent-config-body">
          <div className="agent-config-field">
            <span className="agent-config-label">Provider AI</span>
            <select className="agent-config-select" value={config.provider} onChange={e => onUpdate(agentId, { provider: e.target.value, model: '' })}>
              <option value="deepseek">DeepSeek</option>
              <option value="ollama">Ollama (Locale)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic (Claude)</option>
            </select>
          </div>
          <div className="agent-config-field">
            <span className="agent-config-label">Modello</span>
            <select className="agent-config-select" value={config.model} onChange={e => onUpdate(agentId, { model: e.target.value })}>
              {config.provider === 'deepseek' && ['deepseek-v4-flash','deepseek-chat','deepseek-reasoner','deepseek-coder','deepseek-v4-pro'].map(m => <option key={m} value={m}>{m}</option>)}
              {config.provider === 'ollama' && ollamaModels.length > 0 && ollamaModels.map(m => <option key={m} value={m}>{m}</option>)}
              {config.provider === 'ollama' && ollamaModels.length === 0 && <option value="">— Caricamento modelli... —</option>}
              {config.provider === 'openai' && ['gpt-4o','gpt-4o-mini','gpt-4-turbo','o1','o3-mini'].map(m => <option key={m} value={m}>{m}</option>)}
              {config.provider === 'anthropic' && ['claude-sonnet-4','claude-3-5-sonnet','claude-3-opus'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="agent-config-field">
            <span className="agent-config-label">Manifesto / Ruolo</span>
            <select className="agent-config-select" value={config.manifesto || agentsMeta?.[agentId]?.manifesto || ''} onChange={e => onUpdate(agentId, { manifesto: e.target.value })}>
              <option value="">— Nessun manifesto —</option>
              {manifesti.map((mf, i) => (
                <option key={i} value={mf.path}>{mf.name || mf.filename}</option>
              ))}
            </select>
          </div>
          <div className="agent-config-field">
            <span className="agent-config-label">Temperatura <strong>{config.temperature?.toFixed(2)}</strong></span>
            <input type="range" className="agent-config-range" min="0" max="2" step="0.05" value={config.temperature} onChange={e => onUpdate(agentId, { temperature: parseFloat(e.target.value) })} />
          </div>
          <div className="agent-config-test-section">
            <button className={`agent-config-test-btn ${isTesting ? 'testing' : ''}`} onClick={() => onTest(agentId)} disabled={isTesting}>
              {isTesting ? <><RefreshCw size={14} className="spin" /> Test...</> : <><Wifi size={14} /> Test Connessione</>}
            </button>
            {testSuccess && <div className="agent-config-test-result success"><Wifi size={12} /> Risposta OK ({testLatency}ms)</div>}
            {testError && <div className="agent-config-test-result error"><WifiOff size={12} /> Errore: {testError}</div>}
          </div>
          <div className="agent-config-status">
            <span className={`agent-config-status-dot ${testSuccess ? 'connected' : testError ? 'error' : 'unknown'}`} />
            <span className="agent-config-status-text">{testSuccess ? '🟢 Connesso' : testError ? '🔴 Non connesso' : '⚪ Non testato'}</span>
          </div>
          <button className="agent-config-save-btn" onClick={handleSave} disabled={saving}>
            {saving ? <><RefreshCw size={14} className="spin" />Salvataggio...</> : <><Wifi size={14} /> Salva</>}
          </button>
        </div>
      </div>
    </div>
  );
}

function SessionListItem({ session, isActive, onClick, onDelete }) {
  const sc = { created: '#5a5e72', active: '#00d2ff', completed: '#3fb950', failed: '#ff5555' };
  const si = { created: '📝', active: '⚡', completed: '✅', failed: '❌' };
  return (
    <div className={`rl-session-item ${isActive ? 'active' : ''}`} onClick={onClick}>
      <div className="rl-session-status" style={{ color: sc[session.status] || '#5a5e72' }}>{si[session.status] || '📝'}</div>
      <div className="rl-session-info">
        <div className="rl-session-name">{session.name}</div>
        <div className="rl-session-meta">
          {session.objectives_total > 0 && `${session.objectives_done}/${session.objectives_total} obiettivi · `}{session.agents_count} agenti
        </div>
      </div>
      <button className="rl-session-delete" onClick={e => { e.stopPropagation(); onDelete(session.id); }}><Trash2 size={12} /></button>
    </div>
  );
}

// ==============================================================================
// AGENT AVATAR — Reusable image + fallback icon for any agent meta
// ==============================================================================
function AgentAvatar({ meta, size = 24, style = {} }) {
  const imgSize = size;
  const containerStyle = {
    width: imgSize,
    height: imgSize,
    borderRadius: '50%',
    overflow: 'hidden',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    border: meta?.bg ? `2px solid ${meta.bg}` : 'none',
    ...style,
  };
  const [imgError, setImgError] = React.useState(false);
  return (
    <span style={containerStyle} title={meta?.name || ''}>
      {!imgError && meta?.image ? (
        <img
          src={meta.image}
          alt={meta?.short || ''}
          style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
          onError={() => setImgError(true)}
        />
      ) : (
        <span style={{ fontSize: imgSize * 0.65, lineHeight: 1 }}>{meta?.icon || '🤖'}</span>
      )}
    </span>
  );
}

// ==============================================================================
// TASK DETAIL MODAL — Visualizza dettagli completi di un micro-obiettivo
// ==============================================================================
function TaskDetailModal({ obj, agentsMeta, onClose }) {
  if (!obj) return null;
  const sc = { pending: '#5a5e72', in_progress: '#00d2ff', done: '#3fb950', failed: '#ff5555' };
  const sl = { pending: 'In attesa', in_progress: 'In corso', done: 'Completato', failed: 'Fallito' };
  const meta = agentsMeta[obj.assigned_to] || {};
  return (
    <div className="task-detail-overlay" onClick={onClose}>
      <div className="task-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="task-detail-header" style={{ borderBottomColor: sc[obj.status] || '#5a5e72' }}>
          <span className="task-detail-status" style={{ color: sc[obj.status] }}>{sl[obj.status] || obj.status}</span>
          <button className="task-detail-close" onClick={onClose}><X size={14} /></button>
        </div>
        <div className="task-detail-body">
          <div className="task-detail-row">
            <span className="task-detail-label">Titolo</span>
            <span className="task-detail-value">{obj.title}</span>
          </div>
          <div className="task-detail-row">
            <span className="task-detail-label">Assegnato a</span>
            <span className="task-detail-value" style={{ color: meta.bg }}>
              <AgentAvatar meta={meta} size={20} /> {meta.name || obj.assigned_to}
            </span>
          </div>
          <div className="task-detail-row">
            <span className="task-detail-label">Descrizione</span>
            <span className="task-detail-value task-detail-desc">{obj.description}</span>
          </div>
          {obj.completion_criteria && (
            <div className="task-detail-row">
              <span className="task-detail-label">Criterio</span>
              <span className="task-detail-value">✓ {obj.completion_criteria}</span>
            </div>
          )}
          {obj.result && (
            <div className="task-detail-row">
              <span className="task-detail-label">Risultato</span>
              <span className="task-detail-value">{obj.result}</span>
            </div>
          )}
          {obj.iterations > 0 && (
            <div className="task-detail-row">
              <span className="task-detail-label">Iterazioni</span>
              <span className="task-detail-value">{obj.iterations}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ObjectiveCard({ obj, agentsMeta, onClick }) {
  const sc = { pending: '#5a5e72', in_progress: '#00d2ff', done: '#3fb950', failed: '#ff5555' };
  const si = { pending: <Circle size={14} />, in_progress: <RefreshCw size={14} className="spin" />, done: <CheckCircle size={14} />, failed: <AlertTriangle size={14} /> };
  const meta = agentsMeta[obj.assigned_to] || {};
  return (
    <div className="rl-objective-card" style={{ borderLeftColor: sc[obj.status] || '#5a5e72', cursor: onClick ? 'pointer' : 'default' }} onClick={onClick}>
      <div className="rl-objective-header">
        <span className="rl-objective-status" style={{ color: sc[obj.status] }}>{si[obj.status]}</span>
        <span className="rl-objective-title">{obj.title}</span>
        {meta.icon && <AgentAvatar meta={meta} size={24} />}
      </div>
    </div>
  );
}

export default function ResearchLab({ onClose, onTasksUpdated, addToast }) {
  const pipeline = useResearchPipeline(onTasksUpdated, addToast);
  
  // --- Full pipeline hook (restored) ---
  const {
    AGENTS_META, getAgentColor,
    getAgentConfig, updateAgentConfig,
    selectedAgentId, selectAgentForConfig, closeAgentConfig,
    testStates, testAgentConnection,
    enabledAgents, toggleAgent,
    saveChatMessage, loadChatMessages, pipelineId,
    loadSessionConfigs,
  } = pipeline;

  // --- Research Sessions State ---
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionData, setSessionData] = useState(null);
  const [showNewSession, setShowNewSession] = useState(false);
  const [newGoal, setNewGoal] = useState('');
  const [newTemplate, setNewTemplate] = useState('full_analysis');
  const [launching, setLaunching] = useState(false);
  const [generatingSteps, setGeneratingSteps] = useState(false);
  const [nextSteps, setNextSteps] = useState([]);
  const [commandInput, setCommandInput] = useState('');
  const [editingGoal, setEditingGoal] = useState(null);
  const [interactiveMode, setInteractiveMode] = useState(true);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [hoveredAgent, setHoveredAgent] = useState(null);

  const getAgentColorWithFallback = (id) => {
    if (!id) return { bg: '#8b8fa3', color: '#fff', icon: '🤖', short: 'AI', name: 'AI' };
    if (AGENTS_META[id]) return AGENTS_META[id];
    const prefix = id.split('_')[0].split('-')[0];
    const baseId = Object.keys(AGENTS_META).find(k => k.startsWith(prefix) || k.includes(prefix));
    if (baseId && AGENTS_META[baseId]) {
      const baseMeta = AGENTS_META[baseId];
      const numMatch = id.match(/_(\d+)$/);
      const numberSuffix = numMatch ? ` ${numMatch[1]}` : '';
      const shortSuffix = numMatch ? `-${numMatch[1]}` : '';
      return {
        ...baseMeta,
        name: `${baseMeta.name}${numberSuffix}`,
        short: `${baseMeta.short}${shortSuffix}`
      };
    }
    return getAgentColor(id);
  };

  useEffect(() => {
    if (sessionData) {
      const objs = sessionData.micro_objectives || [];
      const doneCount = objs.filter(o => o.status === 'done').length;
      window.__activeSessionObjectives = objs;
      window.__activeSessionName = sessionData.name || '';
      window.__activeSessionProgress = { done: doneCount, total: objs.length };
    } else {
      window.__activeSessionObjectives = [];
      window.__activeSessionName = '';
      window.__activeSessionProgress = { done: 0, total: 0 };
    }
    window.dispatchEvent(new CustomEvent('sigma-research-objectives-updated'));
  }, [sessionData]);

  // --- Live execution state ---
  const [executing, setExecuting] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [agentStates, setAgentStates] = useState({});
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const abortRef = useRef(null);
  const chatEndRef = useRef(null);

  // --- Task detail modal ---
  const [selectedObjective, setSelectedObjective] = useState(null);

  // --- Selected agent for config panel ---
  const selectedAgent = selectedAgentId ? {
    id: selectedAgentId,
    meta: AGENTS_META[selectedAgentId] || getAgentColor(selectedAgentId),
    config: getAgentConfig(selectedAgentId),
  } : null;

  useEffect(() => { fetchSessions(); }, []);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/research/list');
      const data = await res.json();
      if (data.success) {
        setSessions(data.sessions || []);
        // Auto-seleziona l'ultima ricerca (la prima in lista, ordinata per data decrescente)
        if (data.sessions?.length > 0 && !activeSessionId) {
          handleSelectSession(data.sessions[0].id);
        }
      }
    } catch (e) {}
  };

  const fetchSessionStatus = async (sessionId) => {
    try {
      const res = await fetch(`/api/research/status?id=${encodeURIComponent(sessionId)}`);
      const data = await res.json();
      if (data.success) {
        setSessionData(data.session);
        loadSessionConfigs(data.session.agents);
        if (data.session.next_steps?.length) setNextSteps(data.session.next_steps);
        const objs = data.session.micro_objectives || [];
        setProgress({ done: objs.filter(o => o.status === 'done').length, total: objs.length });
      }
    } catch (e) {}
  };

  const handleSelectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    if (typeof window !== 'undefined') window.__activeSessionId = sessionId;
    setChatMessages([]);
    setAgentStates({});
    fetchSessionStatus(sessionId);
    // Carica cronologia chat dalla sessione salvata
    try {
      const res = await fetch(`/api/research/chat_history?id=${encodeURIComponent(sessionId)}`);
      const data = await res.json();
      if (data.success && data.messages?.length > 0) {
        setChatMessages(data.messages.map(m => ({
          type: m.type,
          agent_id: m.agent_id,
          message: m.message,
          thinking: m.thinking,
          response: m.response,
          ts: m.ts || Date.now(),
        })));
      }
    } catch (e) {
      console.error('[ResearchLab] Failed to load chat history:', e);
    }
    console.log('[ResearchLab] Chat messages after load:', chatMessages.length);
  };

  const handleCreateAndStart = async () => {
    if (!newGoal.trim() || launching) return;
    setLaunching(true);
    try {
      const template = PIPELINE_TEMPLATES[newTemplate];
      const agents = (template?.agents || ['sigma_architect']).map(id => {
        const config = getAgentConfig(id);
        return { agent_id: id, provider: config.provider || 'deepseek', model: config.model || 'deepseek-v4-flash', temperature: config.temperature ?? 0.4 };
      });
      // 1. Create session
      const r1 = await fetch('/api/research/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newGoal.slice(0, 80), goal: newGoal, pipeline_template: newTemplate, agents, interactive_mode: interactiveMode }),
      });
      const d1 = await r1.json();
      if (!d1.success) { setLaunching(false); return; }
      const sid = d1.session.id;
      setShowNewSession(false); setNewGoal('');
      fetchSessions();
      setActiveSessionId(sid);
      setChatMessages([]); setAgentStates({});
      // 2. Decompose
      const r2 = await fetch('/api/research/decompose', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, goal: newGoal, agents }),
      });
      const d2 = await r2.json();
      // 3. Refresh status
      const r3 = await fetch(`/api/research/status?id=${encodeURIComponent(sid)}`);
      const d3 = await r3.json();
      if (d3.success) {
        setSessionData(d3.session);
        const objs = d3.session.micro_objectives || [];
        setProgress({ done: objs.filter(o => o.status === 'done').length, total: objs.length });
      }
      // 4. Start execution
      setExecuting(true);
      const controller = new AbortController();
      abortRef.current = controller;
      const res = await fetch('/api/research/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid }), signal: controller.signal,
      });
      const reader = res.body.getReader(); const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n'); buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const p = line.slice(6); if (p === '[DONE]') break;
            try { handleSSEEvent(JSON.parse(p)); } catch (e) {}
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setChatMessages(prev => [...prev, { type: 'error', message: `❌ ${e.message}`, ts: Date.now() }]);
    }
    setExecuting(false); abortRef.current = null; setLaunching(false);
  };

  const handleGenerateNextSteps = async () => {
    if (!activeSessionId) return;
    setGeneratingSteps(true);
    try {
      const res = await fetch('/api/research/next_steps', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId }),
      });
      const data = await res.json();
      if (data.success) { setNextSteps(data.next_steps || []); fetchSessionStatus(activeSessionId); }
    } catch (e) {}
    setGeneratingSteps(false);
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await fetch('/api/research/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: sessionId }) });
      if (activeSessionId === sessionId) { setActiveSessionId(null); setSessionData(null); }
      fetchSessions();
    } catch (e) {}
  };

  // ============================
  // LIVE EXECUTION
  // ============================
  const handleStartResearch = async () => {
    if (!activeSessionId || executing) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setExecuting(true);
    // Mantieni la cronologia chat esistente, resetta solo stati agenti
    setAgentStates({});

    try {
      const res = await fetch('/api/research/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId }), signal: controller.signal,
      });
      const reader = res.body.getReader(); const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const p = line.slice(6);
            if (p === '[DONE]') break;
            try { handleSSEEvent(JSON.parse(p)); } catch (e) {}
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setChatMessages(prev => [...prev, { type: 'error', message: `❌ Errore: ${e.message}`, ts: Date.now() }]);
      }
    }
    setExecuting(false);
    abortRef.current = null;
    fetchSessionStatus(activeSessionId);
  };

  const handleSSEEvent = (event) => {
    const { type } = event;
    const now = Date.now();

    if (type === 'research_start') {
      setProgress({ done: 0, total: event.total_objectives });
      setChatMessages(prev => [...prev, { type: 'agent_start', message: event.message, ts: now }]);
      return;
    }

    if (type === 'research_done' || type === 'all_done') {
      setExecuting(false);
      setProgress(prev => ({ ...prev, done: prev.total }));
      setChatMessages(prev => [...prev, { type: 'all_done', message: event.message, ts: now }]);
      return;
    }

    if (type === 'next_steps_ready') {
      if (event.next_steps) setNextSteps(event.next_steps);
      return;
    }

    // Agent-specific events
    const agentId = event.agent_id;
    if (agentId) {
      if (type === 'agent_start') {
        setAgentStates(prev => ({ ...prev, [agentId]: { status: 'working', task: event.objective } }));
        if (event.objective_id) {
          setSessionData(prev => prev ? {
            ...prev,
            micro_objectives: (prev.micro_objectives || []).map(o =>
              o.id === event.objective_id ? { ...o, status: 'in_progress' } : o
            )
          } : null);
        }
      } else if (type === 'objective_complete') {
        setProgress(prev => ({ ...prev, done: Math.min(prev.total, prev.done + 1) }));
        setAgentStates(prev => ({ ...prev, [agentId]: { status: 'done' } }));
        if (event.objective_id) {
          setSessionData(prev => prev ? {
            ...prev,
            micro_objectives: (prev.micro_objectives || []).map(o =>
              o.id === event.objective_id ? { ...o, status: 'done' } : o
            )
          } : null);
        }
      } else if (type === 'agent_error') {
        setAgentStates(prev => ({ ...prev, [agentId]: { status: 'error' } }));
      }

      setChatMessages(prev => {
        const lastMsg = prev.length > 0 ? prev[prev.length - 1] : null;
        if (lastMsg && lastMsg.agent_id === agentId && agentId !== 'user') {
          const updated = [...prev];
          const msg = { ...lastMsg };

          if (type === 'agent_start') {
            msg.message = event.message;
          } else if (type === 'agent_thinking') {
            msg.thinking = event.thinking;
            if (event.message) msg.message = event.message;
          } else if (type === 'agent_actions') {
            msg.message = (msg.message ? msg.message + '\n' : '') + event.message;
          } else if (type === 'agent_response') {
            msg.response = event.response;
            if (event.message) msg.message = event.message;
          } else if (type === 'objective_complete') {
            msg.message = (msg.message ? msg.message + '\n' : '') + event.message;
            msg.type = 'objective_complete';
          } else if (type === 'agent_error') {
            msg.message = (msg.message ? msg.message + '\n' : '') + event.message;
            msg.type = 'error';
          }

          msg.ts = now;
          updated[updated.length - 1] = msg;
          return updated;
        } else {
          let msgObj = { type: type, agent_id: agentId, ts: now };
          if (type === 'agent_start') {
            msgObj.message = event.message;
          } else if (type === 'agent_thinking') {
            msgObj.thinking = event.thinking;
            msgObj.message = event.message;
          } else if (type === 'agent_actions') {
            msgObj.message = event.message;
          } else if (type === 'agent_response') {
            msgObj.response = event.response;
            msgObj.message = event.message;
          } else if (type === 'objective_complete') {
            msgObj.message = event.message;
          } else if (type === 'agent_error') {
            msgObj.message = event.message;
          }
          return [...prev, msgObj];
        }
      });
    } else {
      if (type === 'objective_complete') {
        setProgress(prev => ({ ...prev, done: Math.min(prev.total, prev.done + 1) }));
        if (event.objective_id) {
          setSessionData(prev => prev ? {
            ...prev,
            micro_objectives: (prev.micro_objectives || []).map(o =>
              o.id === event.objective_id ? { ...o, status: 'done' } : o
            )
          } : null);
        }
      }
      setChatMessages(prev => [...prev, { type: type, message: event.message, ts: now }]);
    }
  };

  const handleStopResearch = () => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    setExecuting(false);
  };

  const handleSaveGoal = async () => {
    if (editingGoal === null || !activeSessionId || editingGoal === sessionData?.goal) {
      setEditingGoal(null); return;
    }
    try {
      await fetch('/api/research/update_objective', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId, goal: editingGoal }),
      });
      setSessionData(prev => prev ? { ...prev, goal: editingGoal } : null);
      if (addToast) addToast('✅ Obiettivo aggiornato', 'success', 2000);
    } catch (e) { console.error(e); }
    setEditingGoal(null);
  };

  const handleRemoveAgent = async (agentId) => {
    if (!activeSessionId) return;
    try {
      const res = await fetch('/api/research/update_agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId, action: 'remove', agent: { agent_id: agentId } }),
      });
      const data = await res.json();
      if (data.success) setSessionData(data.session);
    } catch (e) { console.error(e); }
  };

  const handleAddAgent = async (agentId) => {
    if (!activeSessionId) return;
    const config = getAgentConfig(agentId);
    const newAgent = { agent_id: agentId, provider: config.provider || 'deepseek', model: config.model || 'deepseek-v4-flash', temperature: config.temperature ?? 0.4, manifesto: config.manifesto || '' };
    try {
      const res = await fetch('/api/research/update_agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId, action: 'add', agent: newAgent }),
      });
      const data = await res.json();
      if (data.success) setSessionData(data.session);
    } catch (e) { console.error(e); }
  };

  const handleAddNewAgentInstance = async (prefix, baseId) => {
    if (!activeSessionId) return;
    
    const activeAgents = sessionData?.agents || [];
    const team = activeAgents.filter(a => (a.agent_id || a.id) !== 'sigma_architect');

    // Count existing agents starting with this prefix in the current session
    const count = team.filter(a => {
      const aid = a.agent_id || a.id;
      return aid.startsWith(prefix);
    }).length;
    
    // Generate unique numbered ID (e.g., math_2, math_3)
    let newAgentId = count === 0 ? baseId : `${prefix}_${count + 1}`;
    
    // Safety check to avoid duplicate ID
    let idx = count + 1;
    while (team.some(a => (a.agent_id || a.id) === newAgentId)) {
      idx++;
      newAgentId = `${prefix}_${idx}`;
    }
    
    const baseConfig = getAgentConfig(baseId);
    const newAgent = {
      agent_id: newAgentId,
      provider: baseConfig.provider || 'deepseek',
      model: baseConfig.model || 'deepseek-v4-flash',
      temperature: baseConfig.temperature ?? 0.4,
      manifesto: baseConfig.manifesto || `manifesti/${baseId}.md`
    };
    
    try {
      const res = await fetch('/api/research/update_agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId, action: 'add', agent: newAgent }),
      });
      const data = await res.json();
      if (data.success) {
        setSessionData(data.session);
        if (addToast) addToast(`✅ Agente ${newAgentId} aggiunto`, 'success', 2000);
      }
    } catch (e) {
      console.error(e);
    }
    setShowAddMenu(false);
  };

  const handleSendCommand = async () => {
    if (!commandInput.trim() || !activeSessionId) return;
    const cmd = commandInput.trim();
    setCommandInput('');
    setChatMessages(prev => [...prev, { type: 'agent_start', agent_id: 'user', message: `👤 Tu: ${cmd}`, ts: Date.now() }]);
    // Execute as new objective
    try {
      const res = await fetch('/api/research/decompose', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId, goal: cmd, agents: sessionData?.agents || [] }),
      });
      await res.json();
      handleStartResearch();
    } catch (e) { console.error(e); }
  };

  const renderAgentCard = (agent) => {
    const id = agent.agent_id || agent.id;
    const meta = AGENTS_META[id] || getAgentColor(id);
    const state = agentStates[id] || {};
    const isWorking = state.status === 'working';
    const config = getAgentConfig(id);
    return (
      <div className={`rl-agent-card-live ${isWorking ? 'working' : ''} ${state.status === 'done' ? 'done' : ''} ${state.status === 'error' ? 'error' : ''}`}
        style={{ borderColor: isWorking ? meta.bg : 'rgba(255,255,255,0.06)', cursor: 'pointer' }}>
        <div className="rl-agent-icon-live" style={{ background: meta.bg + '20', color: meta.bg }}>
          <AgentAvatar meta={meta} size={48} />
          {isWorking && <span className="rl-agent-pulse" style={{ background: meta.bg }} />}
        </div>
        <div className="rl-agent-info-live">
          <div className="rl-agent-name-live" style={{ color: meta.bg }}>{meta.name || id}</div>
          <div className="rl-agent-role-live" style={{ color: meta.bg + 'CC' }}>{meta.role || ''}</div>
          <div className="rl-agent-model-live">{config.model || agent.model}</div>
          {state.task && <div className="rl-agent-task-live">{state.task}</div>}
        </div>
        <div className="rl-agent-status-live" style={{ color: isWorking ? meta.bg : state.status === 'done' ? '#3fb950' : state.status === 'error' ? '#ff5555' : '#5a5e72' }}>
          {isWorking ? <RefreshCw size={12} className="spin" /> : state.status === 'done' ? <CheckCircle size={12} /> : state.status === 'error' ? <AlertTriangle size={12} /> : <Circle size={12} />}
        </div>
      </div>
    );
  };

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  // Kanban
  const objectives = sessionData?.micro_objectives || [];
  const pendingO = objectives.filter(o => o.status === 'pending');
  const progressO = objectives.filter(o => o.status === 'in_progress');
  const doneO = objectives.filter(o => o.status === 'done');
  const failedO = objectives.filter(o => o.status === 'failed');

  return (
    <div className="research-lab-v2">
      {/* LEFT BAR — Session List */}
      <div className="rl-sidebar">
        <div className="rl-sidebar-header">
          <Target size={14} /><span>Ricerche</span>
          <button className="rl-btn-icon" onClick={() => setShowNewSession(true)}><Plus size={14} /></button>
        </div>
        <div className="rl-session-list">
          {sessions.map(s => <SessionListItem key={s.id} session={s} isActive={activeSessionId === s.id} onClick={() => handleSelectSession(s.id)} onDelete={handleDeleteSession} />)}
          {sessions.length === 0 && <div className="rl-empty"><Layers size={24} /><span>Nessuna ricerca</span><button className="rl-btn" onClick={() => setShowNewSession(true)}>Nuova</button></div>}
        </div>
      </div>

      {/* MAIN */}
      <div className="rl-main">
        {/* New Session Modal */}
        {showNewSession && (
          <div className="rl-new-session-overlay" onClick={() => setShowNewSession(false)}>
            <div className="rl-new-session" onClick={e => e.stopPropagation()}>
              <div className="rl-new-header"><span>🔬 Nuova Ricerca</span><button className="rl-btn-icon" onClick={() => setShowNewSession(false)}><X size={14} /></button></div>
              <div className="rl-new-body">
                <label>Obiettivo della ricerca</label>
                <textarea className="rl-goal-input" value={newGoal} onChange={e => setNewGoal(e.target.value)} placeholder="Descrivi l'obiettivo della ricerca..." rows={4} />
                <label>Pipeline template</label>
                <div className="rl-template-grid">
                  {Object.values(PIPELINE_TEMPLATES).map(t => (
                    <div key={t.id} className={`rl-template-card ${newTemplate === t.id ? 'active' : ''}`} onClick={() => setNewTemplate(t.id)}>
                      <div className="rl-template-name">{t.name}</div><div className="rl-template-desc">{t.description}</div>
                      <div className="rl-template-agents">{t.agents.map(a => <AgentAvatar key={a} meta={AGENTS_META[a]} size={28} />)}</div>
                    </div>
                  ))}
                </div>

                {/* Agent Configuration Chips */}
                <label>Configurazione Agenti</label>
                <div className="rl-agent-config-row">
                  {Object.entries(AGENTS_META).map(([id, meta]) => {
                    const config = getAgentConfig(id);
                    const isSelected = selectedAgentId === id;
                    const isTested = testStates[id]?.success;
                    return (
                      <button key={id}
                        className={`rl-agent-config-chip ${isSelected ? 'selected' : ''}`}
                        style={{ borderColor: meta.bg }}
                        onClick={() => selectAgentForConfig(id)}
                        title={`${meta.name}: ${config.provider}/${config.model} @ ${config.temperature?.toFixed(2)}`}>
                        <AgentAvatar meta={meta} size={28} /><span style={{ color: meta.bg }}>{meta.short}</span>
                        {isTested && <span className="rl-chip-ok">✓</span>}
                      </button>
                    );
                  })}
                </div>

                {/* Modalità di Iterazione */}
                <div className="rl-interactive-mode-toggle" style={{ margin: '15px 0' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.8rem', color: '#8b8fa3' }}>Modalità di Iterazione</label>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                      type="button"
                      className="rl-btn-sm"
                      onClick={(e) => { e.preventDefault(); setInteractiveMode(true); }}
                      style={{ flex: 1, padding: '8px', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '4px', cursor: 'pointer', background: interactiveMode ? '#7c5bf0' : 'rgba(255,255,255,0.03)', color: '#fff', fontSize: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
                    >
                      👤 Iterazione con l'utente
                    </button>
                    <button
                      type="button"
                      className="rl-btn-sm"
                      onClick={(e) => { e.preventDefault(); setInteractiveMode(false); }}
                      style={{ flex: 1, padding: '8px', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '4px', cursor: 'pointer', background: !interactiveMode ? '#7c5bf0' : 'rgba(255,255,255,0.03)', color: '#fff', fontSize: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
                    >
                      🤖 Iterazione automatica
                    </button>
                  </div>
                </div>

                <button className="rl-btn-primary" onClick={handleCreateAndStart} disabled={!newGoal.trim() || launching}>
                  {launching ? <><RefreshCw size={14} className="spin" /> Creazione...</> : <><Plus size={14} /> Crea Ricerca</>}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Agent Config Panel Overlay */}
        {selectedAgent && (
          <AgentConfigPanel
            agentId={selectedAgent.id} meta={selectedAgent.meta} config={selectedAgent.config}
            onUpdate={updateAgentConfig} onClose={closeAgentConfig}
            testState={testStates[selectedAgent.id]} onTest={testAgentConnection}
            agentsMeta={AGENTS_META}
          />
        )}

        {sessionData ? (
          <div className="rl-content-row">
            {/* LEFT PANE */}
            <div className="rl-left-pane">
              {/* Compact header — single line with actions right-aligned */}
              <div className="rl-left-header">
                <span className="rl-left-title">{sessionData.name?.slice(0, 40)}</span>
                <div className="rl-left-header-spacer" />
                 <span className={`rl-badge rl-badge-${executing ? 'active' : sessionData.status}`}>{executing ? 'LIVE' : sessionData.status?.toUpperCase()}</span>
                 <span className="rl-badge" style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: '#8b8fa3', marginLeft: '6px' }}>
                   {sessionData.interactive_mode ? '👤 Interattivo' : '🤖 Automatico'}
                 </span>
                <span className="rl-progress">{progress.done}/{progress.total}</span>
                <div className="rl-left-header-actions">
                  {!executing ? (
                    <button className="rl-btn-sm" onClick={handleStartResearch} title="Avvia esecuzione"><Play size={12} /> Avvia</button>
                  ) : (
                    <button className="rl-btn-sm" onClick={handleStopResearch} style={{ color: '#ff5555' }} title="Ferma esecuzione"><StopCircle size={12} /> Ferma</button>
                  )}
                  {!executing && sessionData.status === 'completed' && (
                    <button className="rl-btn-sm" onClick={handleGenerateNextSteps} disabled={generatingSteps} title="Genera prossimi passi">
                      <GitBranch size={12} /> Next
                    </button>
                  )}
                  <button className="rl-btn-icon" onClick={() => { setActiveSessionId(null); setSessionData(null); closeAgentConfig(); }} title="Chiudi"><X size={14} /></button>
                </div>
              </div>
              {/* Grafo Relazionale Piramidale degli Agenti */}
              <div className="rl-agents-grid" style={{
                background: 'rgba(21, 23, 38, 0.25)',
                backdropFilter: 'blur(10px)',
                borderRadius: '12px',
                border: '1px solid rgba(255,255,255,0.02)',
                padding: '10px 15px',
                position: 'relative',
                overflow: 'visible',
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                margin: '8px'
              }}>
                {(() => {
                  const allAgents = sessionData.agents?.some(a => (a.agent_id || a.id) === 'sigma_architect')
                    ? sessionData.agents
                    : [{ agent_id: 'sigma_architect', provider: 'deepseek', model: 'deepseek-v4-flash' }, ...(sessionData.agents || [])];

                  const coordinator = allAgents.find(a => (a.agent_id || a.id) === 'sigma_architect');
                  const team = allAgents.filter(a => (a.agent_id || a.id) !== 'sigma_architect');

                  // Direct reports: agents the architect manages directly
                  const DIRECT_ROLES = ['math', 'code_architect', 'formulario', 'proof-reviewer'];
                  const directAgents = team.filter(a => {
                    const aid = a.agent_id || a.id;
                    return DIRECT_ROLES.some(r => aid.startsWith(r));
                  });
                  // Indirect: downstream agents (test-engineer, viz-designer, math-collatz, others)
                  const INDIRECT_ROLES = ['test-engineer', 'viz-designer', 'math-collatz'];
                  const indirectAgents = team.filter(a => {
                    const aid = a.agent_id || a.id;
                    return !DIRECT_ROLES.some(r => aid.startsWith(r));
                  });

                  const availableAgents = Object.keys(AGENTS_META).filter(id => !allAgents.some(a => (a.agent_id || a.id) === id));

                  // ---- Layout parameters ----
                  const W = 480;         // viewBox width
                  const ROW_Y = [55, 170, 290];   // Y centers: architect / direct / indirect
                  const AVATAR_R = 28;   // radius of avatar circle
                  const COORD_R = 36;   // bigger for architect

                  // Compute X positions for a row of N nodes
                  const rowX = (n, i, total) => {
                    if (total === 1) return W / 2;
                    const span = Math.min((total - 1) * 90, W - 80);
                    const start = (W - span) / 2;
                    return start + i * (span / Math.max(total - 1, 1));
                  };

                  const positions = {};
                  if (coordinator) positions['sigma_architect'] = { x: W / 2, y: ROW_Y[0] };
                  directAgents.forEach((a, i) => {
                    positions[a.agent_id || a.id] = { x: rowX(i, i, directAgents.length), y: ROW_Y[1] };
                  });
                  indirectAgents.forEach((a, i) => {
                    positions[a.agent_id || a.id] = { x: rowX(i, i, indirectAgents.length), y: ROW_Y[2] };
                  });

                  // Add-button position (below last row)
                  const hasAdd = availableAgents.length > 0;
                  const addPos = { x: W / 2, y: ROW_Y[2] + 80 };

                  // ---- Connection lines ----
                  const lines = [];
                  if (coordinator) {
                    directAgents.forEach(a => lines.push({ from: 'sigma_architect', to: a.agent_id || a.id, type: 'direct' }));
                    if (directAgents.length === 0) {
                      indirectAgents.forEach(a => lines.push({ from: 'sigma_architect', to: a.agent_id || a.id, type: 'direct' }));
                    }
                  }
                  // Math → test & viz
                  directAgents.filter(a => (a.agent_id||a.id).startsWith('math')).forEach(m => {
                    indirectAgents.filter(a => {
                      const aid = a.agent_id||a.id;
                      return aid.startsWith('test') || aid.startsWith('viz');
                    }).forEach(t => lines.push({ from: m.agent_id||m.id, to: t.agent_id||t.id, type: 'indirect' }));
                  });
                  // code → test
                  directAgents.filter(a => (a.agent_id||a.id).startsWith('code')).forEach(c => {
                    indirectAgents.filter(a => (a.agent_id||a.id).startsWith('test')).forEach(t =>
                      lines.push({ from: c.agent_id||c.id, to: t.agent_id||t.id, type: 'indirect' })
                    );
                  });
                  // proof-reviewer ← everything
                  directAgents.filter(a => (a.agent_id||a.id).startsWith('proof')).forEach(p => {
                    indirectAgents.forEach(t => lines.push({ from: t.agent_id||t.id, to: p.agent_id||p.id, type: 'indirect' }));
                  });
                  // Safeguard: orphan → architect
                  team.forEach(a => {
                    const aid = a.agent_id || a.id;
                    if (!lines.some(l => l.from === aid || l.to === aid) && coordinator) {
                      lines.push({ from: 'sigma_architect', to: aid, type: 'direct' });
                    }
                  });

                  const roleDescriptions = {
                    architect: 'Coordina il team, assegna i task e supervisiona la qualità complessiva',
                    researcher: 'Ricerca teorica, formulazione di teoremi e dimostrazioni matematiche',
                    developer: 'Sviluppo codice, implementazione algoritmi e ottimizzazione',
                    tester: 'Test computazionali, verifica correttezza e benchmark prestazioni',
                    visualizer: 'Grafici interattivi D3.js, visualizzazioni dati e dashboard',
                    formulario: 'Sintesi di formulari, tabelle riassuntive e documentazione strutturata',
                    reviewer: 'Revisione critica, confutazione errori e validazione formale',
                    mathematician: 'Analisi matematica specialistica e computazione simbolica',
                  };

                  const addAgentOptions = [
                    { label: '∑ Ricercatore Matematica', prefix: 'math', baseId: 'math1' },
                    { label: '⚙️ Sviluppatore Codice', prefix: 'code_architect', baseId: 'code_architect' },
                    { label: '🧪 Ingegnere dei Test', prefix: 'test-engineer', baseId: 'test-engineer' },
                    { label: '📊 Visualizzatore Grafico', prefix: 'viz-designer', baseId: 'viz-designer' },
                    { label: '🔍 Revisore e Confutatore', prefix: 'proof-reviewer', baseId: 'proof-reviewer' }
                  ];

                  // Compute dynamic viewBox height
                  const hasIndirect = indirectAgents.length > 0;
                  const vbH = hasIndirect ? (hasAdd ? 410 : 360) : (hasAdd ? 300 : 250);

                  return (
                    <div style={{ position: 'relative', width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', paddingTop: '6px' }}>
                      <svg
                        width="100%"
                        viewBox={`0 0 ${W} ${vbH}`}
                        style={{ overflow: 'visible', maxHeight: '380px' }}
                      >
                        <defs>
                          <filter id="glow-strong">
                            <feGaussianBlur stdDeviation="3" result="blur"/>
                            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                          </filter>
                          <filter id="glow-soft">
                            <feGaussianBlur stdDeviation="1.5" result="blur"/>
                            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                          </filter>
                          {/* Avatar clip paths */}
                          {coordinator && (
                            <clipPath id="clip-sigma_architect">
                              <circle cx={positions['sigma_architect'].x} cy={positions['sigma_architect'].y} r={COORD_R} />
                            </clipPath>
                          )}
                          {team.map(a => {
                            const aid = a.agent_id || a.id;
                            const pos = positions[aid];
                            if (!pos) return null;
                            return (
                              <clipPath key={`clip-${aid}`} id={`clip-${aid}`}>
                                <circle cx={pos.x} cy={pos.y} r={AVATAR_R} />
                              </clipPath>
                            );
                          })}
                        </defs>

                        {/* Row labels */}
                        {coordinator && (
                          <text x={10} y={ROW_Y[0] - COORD_R - 6} fill="rgba(255,255,255,0.18)" fontSize="7.5" fontWeight="700" textAnchor="start" letterSpacing="1.5">COORDINATORE</text>
                        )}
                        {directAgents.length > 0 && (
                          <text x={10} y={ROW_Y[1] - AVATAR_R - 8} fill="rgba(255,255,255,0.12)" fontSize="7" fontWeight="700" textAnchor="start" letterSpacing="1.5">COLLABORATORI DIRETTI</text>
                        )}
                        {indirectAgents.length > 0 && (
                          <text x={10} y={ROW_Y[2] - AVATAR_R - 8} fill="rgba(255,255,255,0.10)" fontSize="7" fontWeight="700" textAnchor="start" letterSpacing="1.5">AGENTI SPECIALIZZATI</text>
                        )}

                        {/* Connection lines */}
                        {lines.map((link, idx) => {
                          const fp = positions[link.from];
                          const tp = positions[link.to];
                          if (!fp || !tp) return null;
                          const fromMeta = getAgentColorWithFallback(link.from);
                          const isActive = agentStates[link.from]?.status === 'working' || agentStates[link.to]?.status === 'working';
                          const isDirect = link.type === 'direct';
                          return (
                            <g key={`line-${idx}`}>
                              <line x1={fp.x} y1={fp.y} x2={tp.x} y2={tp.y}
                                stroke="rgba(255,255,255,0.04)" strokeWidth={isDirect ? 3 : 1.5} />
                              <line x1={fp.x} y1={fp.y} x2={tp.x} y2={tp.y}
                                stroke={fromMeta.bg}
                                strokeWidth={isDirect ? 1.5 : 1}
                                strokeDasharray={isActive ? '5,3' : isDirect ? '0' : '4,5'}
                                opacity={isActive ? 0.85 : isDirect ? 0.35 : 0.18}
                                style={{ animation: isActive ? 'dash 1s linear infinite' : isDirect ? 'none' : 'dash 3s linear infinite' }}
                              />
                            </g>
                          );
                        })}

                        {/* Architect node */}
                        {coordinator && (() => {
                          const meta = getAgentColorWithFallback('sigma_architect');
                          const state = agentStates['sigma_architect'] || {};
                          const isWorking = state.status === 'working';
                          const pos = positions['sigma_architect'];
                          const agentData = allAgents.find(a => (a.agent_id || a.id) === 'sigma_architect');
                          return (
                            <g
                              key="node-arch"
                              style={{ cursor: 'pointer' }}
                              onClick={() => selectAgentForConfig('sigma_architect')}
                              onMouseEnter={() => setHoveredAgent('sigma_architect')}
                              onMouseLeave={() => setHoveredAgent(null)}
                            >
                              {/* Outer glow ring */}
                              <circle cx={pos.x} cy={pos.y} r={COORD_R + 8}
                                fill="none" stroke={meta.bg}
                                strokeWidth="1.5" opacity="0.2"
                                style={{ animation: isWorking ? 'pulse-ring 1.2s ease-in-out infinite' : 'none' }}
                              />
                              <circle cx={pos.x} cy={pos.y} r={COORD_R + 4}
                                fill="none" stroke={meta.bg}
                                strokeWidth={isWorking ? 2.5 : 1.5}
                                opacity={isWorking ? 0.7 : 0.4}
                              />
                              {/* Avatar circle background */}
                              <circle cx={pos.x} cy={pos.y} r={COORD_R} fill="#1a1d2e" />
                              {/* Agent image */}
                              <image
                                href={meta.image || '/images/agente0.png'}
                                x={pos.x - COORD_R} y={pos.y - COORD_R}
                                width={COORD_R * 2} height={COORD_R * 2}
                                clipPath="url(#clip-sigma_architect)"
                                preserveAspectRatio="xMidYMid slice"
                              />
                              {/* Status ring */}
                              <circle cx={pos.x} cy={pos.y} r={COORD_R}
                                fill="none"
                                stroke={isWorking ? meta.bg : state.status === 'done' ? '#3fb950' : state.status === 'error' ? '#ff5555' : meta.bg}
                                strokeWidth={isWorking ? 2.5 : 2}
                                filter={isWorking ? 'url(#glow-strong)' : undefined}
                                opacity={isWorking ? 1 : 0.6}
                              />
                              {/* Working pulse dot */}
                              {isWorking && <circle cx={pos.x + COORD_R - 5} cy={pos.y - COORD_R + 5} r={5} fill={meta.bg} filter="url(#glow-soft)" style={{ animation: 'pulse-ring 0.8s ease-in-out infinite' }} />}
                              {/* Name label */}
                              <text x={pos.x} y={pos.y + COORD_R + 14} textAnchor="middle" fill={meta.bg} fontSize="9" fontWeight="800" letterSpacing="0.5">
                                {meta.short || 'Arch'}
                              </text>
                              <text x={pos.x} y={pos.y + COORD_R + 24} textAnchor="middle" fill="rgba(255,255,255,0.35)" fontSize="6.5" fontWeight="600">
                                {agentData?.model || meta.name || ''}
                              </text>
                            </g>
                          );
                        })()}

                        {/* Team nodes (direct + indirect merged) */}
                        {team.map(agent => {
                          const aid = agent.agent_id || agent.id;
                          const meta = getAgentColorWithFallback(aid);
                          const state = agentStates[aid] || {};
                          const isWorking = state.status === 'working';
                          const isDone = state.status === 'done';
                          const isError = state.status === 'error';
                          const pos = positions[aid];
                          if (!pos) return null;
                          const borderColor = isWorking ? meta.bg : isDone ? '#3fb950' : isError ? '#ff5555' : meta.bg;

                          return (
                            <g
                              key={`node-${aid}`}
                              style={{ cursor: 'pointer' }}
                              onClick={() => selectAgentForConfig(aid)}
                              onMouseEnter={() => setHoveredAgent(aid)}
                              onMouseLeave={() => setHoveredAgent(null)}
                            >
                              {/* Outer working animation ring */}
                              {isWorking && (
                                <circle cx={pos.x} cy={pos.y} r={AVATAR_R + 6}
                                  fill="none" stroke={meta.bg} strokeWidth="1.2" opacity="0.3"
                                  style={{ animation: 'pulse-ring 1.2s ease-in-out infinite' }}
                                />
                              )}
                              <circle cx={pos.x} cy={pos.y} r={AVATAR_R + 2}
                                fill="none" stroke={borderColor}
                                strokeWidth={isWorking ? 2 : 1.2}
                                opacity={isWorking ? 0.6 : 0.3}
                              />
                              {/* Avatar bg */}
                              <circle cx={pos.x} cy={pos.y} r={AVATAR_R} fill="#1a1d2e" />
                              {/* Agent image */}
                              <image
                                href={meta.image || '/images/default.png'}
                                x={pos.x - AVATAR_R} y={pos.y - AVATAR_R}
                                width={AVATAR_R * 2} height={AVATAR_R * 2}
                                clipPath={`url(#clip-${aid})`}
                                preserveAspectRatio="xMidYMid slice"
                              />
                              {/* Status border */}
                              <circle cx={pos.x} cy={pos.y} r={AVATAR_R}
                                fill="none" stroke={borderColor}
                                strokeWidth={isWorking ? 2.5 : 1.8}
                                filter={isWorking ? 'url(#glow-soft)' : undefined}
                                opacity={isWorking ? 1 : 0.5}
                              />
                              {/* Done badge */}
                              {isDone && !isWorking && (
                                <g transform={`translate(${pos.x + AVATAR_R - 8}, ${pos.y - AVATAR_R + 2})`}>
                                  <circle r={6} fill="#0e1016" />
                                  <text textAnchor="middle" dy="3.5" fontSize="7" fill="#3fb950">✓</text>
                                </g>
                              )}
                              {/* Error badge */}
                              {isError && !isWorking && (
                                <g transform={`translate(${pos.x + AVATAR_R - 8}, ${pos.y - AVATAR_R + 2})`}>
                                  <circle r={6} fill="#0e1016" />
                                  <text textAnchor="middle" dy="3.5" fontSize="7" fill="#ff5555">!</text>
                                </g>
                              )}
                              {/* Working dot */}
                              {isWorking && <circle cx={pos.x + AVATAR_R - 5} cy={pos.y - AVATAR_R + 5} r={4} fill={meta.bg} filter="url(#glow-soft)" style={{ animation: 'pulse-ring 0.8s ease-in-out infinite' }} />}
                              {/* Remove button */}
                              <g transform={`translate(${pos.x - AVATAR_R + 4}, ${pos.y - AVATAR_R + 4})`}
                                onClick={e => { e.stopPropagation(); handleRemoveAgent(aid); }}
                                style={{ cursor: 'pointer', opacity: 0 }}
                                className="rl-node-remove-btn"
                              >
                                <circle r={7} fill="rgba(255,85,85,0.8)" />
                                <text textAnchor="middle" dy="3.5" fontSize="8" fill="#fff" fontWeight="800">✕</text>
                              </g>
                              {/* Label */}
                              <text x={pos.x} y={pos.y + AVATAR_R + 12} textAnchor="middle" fill={meta.bg} fontSize="8.5" fontWeight="700">
                                {meta.short || aid}
                              </text>
                              <text x={pos.x} y={pos.y + AVATAR_R + 22} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="6">
                                {agent.model || ''}
                              </text>
                            </g>
                          );
                        })}

                        {/* Add Agent node */}
                        {hasAdd && (
                          <g style={{ cursor: 'pointer' }} onClick={() => setShowAddMenu(!showAddMenu)}>
                            <circle cx={addPos.x} cy={addPos.y} r={22}
                              fill="rgba(255,255,255,0.02)"
                              stroke="rgba(255,255,255,0.08)"
                              strokeWidth="1.5"
                              strokeDasharray="4,4"
                            />
                            <text x={addPos.x} y={addPos.y + 4} textAnchor="middle" fill="#8b8fa3" fontSize="18" fontWeight="300">+</text>
                            <text x={addPos.x} y={addPos.y + 34} textAnchor="middle" fill="#5a5e72" fontSize="7" fontWeight="600">AGGIUNGI</text>
                          </g>
                        )}

                        {/* Hover Tooltip (rendered as foreignObject for rich HTML) */}
                        {hoveredAgent && positions[hoveredAgent] && (() => {
                          const pos = positions[hoveredAgent];
                          const meta = getAgentColorWithFallback(hoveredAgent);
                          const state = agentStates[hoveredAgent] || {};
                          const agentData = allAgents.find(a => (a.agent_id || a.id) === hoveredAgent);
                          const role = meta.role || 'agent';
                          const statusLabel = { working: '⚡ In esecuzione', done: '✅ Completato', error: '❌ Errore', pending: '⏳ In attesa', idle: '💤 Inattivo' }[state.status] || '💤 Inattivo';

                          // Smart tooltip positioning
                          const ttW = 180, ttH = 115;
                          let ttX = pos.x - ttW / 2;
                          let ttY = pos.y - ttH - 52;
                          if (ttX < 5) ttX = 5;
                          if (ttX + ttW > W - 5) ttX = W - ttW - 5;
                          if (ttY < 5) ttY = pos.y + 50;

                          return (
                            <foreignObject x={ttX} y={ttY} width={ttW} height={ttH + 20} style={{ overflow: 'visible', pointerEvents: 'none' }}>
                              <div style={{
                                background: 'rgba(14,16,22,0.97)',
                                border: `1px solid ${meta.bg}40`,
                                borderRadius: '10px',
                                padding: '10px 12px',
                                boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${meta.bg}20`,
                                backdropFilter: 'blur(12px)',
                                fontFamily: 'Inter, sans-serif',
                                minWidth: '160px'
                              }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                  <div style={{
                                    width: '32px', height: '32px', borderRadius: '50%',
                                    background: `${meta.bg}22`, border: `1.5px solid ${meta.bg}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: '14px', flexShrink: 0
                                  }}>{meta.icon}</div>
                                  <div>
                                    <div style={{ fontSize: '0.72rem', fontWeight: '800', color: '#fff', lineHeight: 1.2 }}>{meta.name || hoveredAgent}</div>
                                    <div style={{ fontSize: '0.58rem', color: meta.bg, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{role}</div>
                                  </div>
                                </div>
                                <div style={{ fontSize: '0.6rem', color: '#8b8fa3', lineHeight: 1.4, marginBottom: '6px' }}>
                                  {roleDescriptions[role] || 'Agente specializzato del team di ricerca'}
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '0.58rem', color: '#5a5e72', background: 'rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: '4px' }}>
                                    {agentData?.provider || 'deepseek'} · {agentData?.model || '—'}
                                  </span>
                                  <span style={{ fontSize: '0.58rem', fontWeight: '700', color: state.status === 'working' ? '#00d2ff' : state.status === 'done' ? '#3fb950' : state.status === 'error' ? '#ff5555' : '#8b8fa3' }}>
                                    {statusLabel}
                                  </span>
                                </div>
                              </div>
                            </foreignObject>
                          );
                        })()}
                      </svg>

                      {/* Add Agent Dropdown */}
                      {showAddMenu && (
                        <div style={{
                          position: 'absolute',
                          bottom: '10px',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          background: '#151726',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: '10px',
                          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                          zIndex: 100,
                          padding: '6px 0',
                          minWidth: '220px'
                        }}>
                          <div style={{ padding: '6px 14px', fontSize: '0.6rem', fontWeight: '700', color: '#8b8fa3', borderBottom: '1px solid rgba(255,255,255,0.04)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Aggiungi Agente al Team
                          </div>
                          {addAgentOptions.map(opt => (
                            <button
                              key={opt.prefix}
                              onClick={() => { handleAddNewAgentInstance(opt.prefix, opt.baseId); setShowAddMenu(false); }}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '8px',
                                width: '100%', padding: '9px 14px',
                                background: 'none', border: 'none',
                                color: '#e2e4eb', textAlign: 'left',
                                fontSize: '0.72rem', cursor: 'pointer',
                                transition: 'background 0.12s'
                              }}
                              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                              onMouseLeave={e => e.currentTarget.style.background = 'none'}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>

              {/* Goal — editable */}
              <div className="rl-goal-display">
                <div className="rl-goal-header">
                  <div className="rl-goal-title">
                    <Target size={12} style={{ color: '#00d2ff' }} />
                    <span>Obiettivo Iniziale della Ricerca</span>
                  </div>
                  <span className="rl-goal-subtitle">MODIFICABILE</span>
                </div>
                <textarea
                  className="rl-goal-edit"
                  value={editingGoal !== null ? editingGoal : (sessionData.goal || '')}
                  onChange={e => setEditingGoal(e.target.value)}
                  onBlur={handleSaveGoal}
                  onFocus={() => setEditingGoal(sessionData.goal || '')}
                  placeholder="Definisci qui l'obiettivo primario della ricerca..."
                />
              </div>

              {/* Task Detail Modal */}
              {selectedObjective && (
                <TaskDetailModal obj={selectedObjective} agentsMeta={AGENTS_META} onClose={() => setSelectedObjective(null)} />
              )}
            </div>

            <div className="rl-right-pane">
              {/* Live Chat Panel */}
              <div className="rl-chat-panel">
                <div className="rl-chat-header"><MessageSquare size={14} /><span>Chat Agenti Live</span><span className="rl-chat-count">{chatMessages.length}</span></div>
              <div className="rl-chat-msgs">
                {chatMessages.length === 0 && !executing && <div className="rl-chat-empty">I messaggi degli agenti appariranno qui durante l'esecuzione</div>}
                {chatMessages.map((msg, i) => {
                  const meta = AGENTS_META[msg.agent_id] || {};
                  const colorMap = { agent_start: '#00d2ff', agent_thinking: '#bc8cff', agent_response: '#3fb950', agent_actions: '#d29922', error: '#ff5555' };
                  const color = colorMap[msg.type] || '#8b8fa3';
                  return (
                    <div key={i} className="rl-chat-msg" style={{ borderLeftColor: color }}>
                      <div className="rl-chat-msg-header">
                        {msg.agent_id && <AgentAvatar meta={meta} size={24} />}
                        {msg.agent_id && <span className="rl-chat-msg-agent" style={{ color: meta.bg || color }}>{meta.name || msg.agent_id}</span>}
                        <span className="rl-chat-msg-type" style={{ color }}>{msg.type.replace('_', ' ').toUpperCase()}</span>
                        <span className="rl-chat-msg-time" style={{ marginLeft: 'auto', fontSize: '0.65rem', color: '#8b8fa3' }}>
                          {msg.ts ? new Date(msg.ts).toLocaleTimeString() : ''}
                        </span>
                      </div>
                      {msg.message && <div className="rl-chat-msg-text" style={{ whiteSpace: 'pre-wrap' }}>{msg.message}</div>}
                      {msg.thinking && <div className="rl-chat-msg-thinking" style={{ whiteSpace: 'pre-wrap' }}>{msg.thinking}</div>}
                      {msg.response && <div className="rl-chat-msg-response" style={{ whiteSpace: 'pre-wrap' }}>{msg.response}</div>}
                    </div>
                  );
                })}
                {executing && <div className="rl-chat-typing">Agenti al lavoro <RefreshCw size={10} className="spin" /></div>}
                <div ref={chatEndRef} />
              </div>
              </div>

              {/* Agent Command Input */}
              <div className="rl-agent-input">
                <input
                  className="rl-agent-input-field"
                  type="text"
                  placeholder="Scrivi un comando per il team..."
                  value={commandInput}
                  onChange={e => setCommandInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && commandInput.trim()) handleSendCommand(); }}
                />
                <button className="rl-btn-primary" onClick={handleSendCommand} disabled={!commandInput.trim()}>
                  <Send size={14} /> Invia
                </button>
              </div>
            </div>

            {/* Next Steps */}
            {nextSteps.length > 0 && (
              <div className="rl-next-steps">
                <div className="rl-next-header"><GitBranch size={14} /><span>Prossimi Passi Suggeriti</span></div>
                <div className="rl-next-list">
                  {nextSteps.map((step, i) => (
                    <div key={i} className="rl-next-item">
                      <div className="rl-next-title"><span className={`rl-priority rl-priority-${step.priority}`}>{step.priority?.toUpperCase()}</span>{step.title}</div>
                      <div className="rl-next-desc">{step.description}</div>
                      <button className="rl-btn-sm" onClick={() => { setNewGoal(step.description); setShowNewSession(true); }}><Play size={10} /> Usa</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="rl-welcome">
            <Cpu size={48} /><h2>Research Lab v3</h2>
            <p>Seleziona una ricerca esistente o creane una nuova per iniziare.</p>
            <button className="rl-btn-primary" onClick={() => setShowNewSession(true)}><Plus size={16} /> Nuova Ricerca</button>
          </div>
        )}
      </div>
    </div>
  );
}
