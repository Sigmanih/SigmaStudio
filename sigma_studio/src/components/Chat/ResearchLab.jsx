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
function AgentConfigPanel({ agentId, meta, config, onUpdate, onClose, testState, onTest }) {
  const isTesting = testState?.testing;
  const testSuccess = testState?.success;
  const testError = testState?.error;
  const testLatency = testState?.latency;
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
            <select className="agent-config-select" value={config.provider} onChange={e => onUpdate(agentId, { provider: e.target.value })}>
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
              {config.provider === 'ollama' && ['llama3.2','qwen3.6','gemma2','mistral','phi3'].map(m => <option key={m} value={m}>{m}</option>)}
              {config.provider === 'openai' && ['gpt-4o','gpt-4o-mini','gpt-4-turbo','o1','o3-mini'].map(m => <option key={m} value={m}>{m}</option>)}
              {config.provider === 'anthropic' && ['claude-sonnet-4','claude-3-5-sonnet','claude-3-opus'].map(m => <option key={m} value={m}>{m}</option>)}
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

function ObjectiveCard({ obj, agentsMeta }) {
  const sc = { pending: '#5a5e72', in_progress: '#00d2ff', done: '#3fb950', failed: '#ff5555' };
  const si = { pending: <Circle size={14} />, in_progress: <RefreshCw size={14} className="spin" />, done: <CheckCircle size={14} />, failed: <AlertTriangle size={14} /> };
  const meta = agentsMeta[obj.assigned_to] || {};
  return (
    <div className="rl-objective-card" style={{ borderLeftColor: sc[obj.status] || '#5a5e72' }}>
      <div className="rl-objective-header">
        <span className="rl-objective-status" style={{ color: sc[obj.status] }}>{si[obj.status]}</span>
        <span className="rl-objective-title">{obj.title}</span>
        {meta.icon && <span className="rl-objective-agent" title={meta.name}>{meta.icon}</span>}
      </div>
      <div className="rl-objective-desc">{obj.description}</div>
      {obj.completion_criteria && <div className="rl-objective-criteria">✓ {obj.completion_criteria}</div>}
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

  // --- Live execution state ---
  const [executing, setExecuting] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [agentStates, setAgentStates] = useState({});
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const abortRef = useRef(null);
  const chatEndRef = useRef(null);

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
      if (data.success) setSessions(data.sessions || []);
    } catch (e) {}
  };

  const fetchSessionStatus = async (sessionId) => {
    try {
      const res = await fetch(`/api/research/status?id=${encodeURIComponent(sessionId)}`);
      const data = await res.json();
      if (data.success) {
        setSessionData(data.session);
        if (data.session.next_steps?.length) setNextSteps(data.session.next_steps);
        const objs = data.session.micro_objectives || [];
        setProgress({ done: objs.filter(o => o.status === 'done').length, total: objs.length });
      }
    } catch (e) {}
  };

  const handleSelectSession = (sessionId) => {
    setActiveSessionId(sessionId);
    setChatMessages([]);
    setAgentStates({});
    fetchSessionStatus(sessionId);
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
        body: JSON.stringify({ name: newGoal.slice(0, 80), goal: newGoal, pipeline_template: newTemplate, agents }),
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
    setChatMessages([]);
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
    if (type === 'research_start') {
      setProgress({ done: 0, total: event.total_objectives });
    } else if (type === 'agent_start') {
      setAgentStates(prev => ({ ...prev, [event.agent_id]: { status: 'working', task: event.objective } }));
      setChatMessages(prev => [...prev, { type: 'agent_start', agent_id: event.agent_id, message: event.message, ts: Date.now() }]);
    } else if (type === 'agent_thinking') {
      setChatMessages(prev => [...prev, { type: 'agent_thinking', agent_id: event.agent_id, thinking: event.thinking, message: event.message, ts: Date.now() }]);
    } else if (type === 'agent_response') {
      setChatMessages(prev => [...prev, { type: 'agent_response', agent_id: event.agent_id, response: event.response, message: event.message, ts: Date.now() }]);
    } else if (type === 'agent_actions') {
      setChatMessages(prev => [...prev, { type: 'agent_actions', agent_id: event.agent_id, message: event.message, ts: Date.now() }]);
    } else if (type === 'objective_complete') {
      setProgress(prev => ({ ...prev, done: prev.done + 1 }));
      setAgentStates(prev => ({ ...prev, [event.agent_id]: { status: 'done' } }));
      setChatMessages(prev => [...prev, { type: 'objective_complete', message: event.message, ts: Date.now() }]);
    } else if (type === 'agent_error') {
      setAgentStates(prev => ({ ...prev, [event.agent_id]: { status: 'error' } }));
      setChatMessages(prev => [...prev, { type: 'error', agent_id: event.agent_id, message: event.message, ts: Date.now() }]);
    } else if (type === 'all_done') {
      setChatMessages(prev => [...prev, { type: 'all_done', message: event.message, ts: Date.now() }]);
    } else if (type === 'next_steps_ready') {
      if (event.next_steps) setNextSteps(event.next_steps);
    }
  };

  const handleStopResearch = () => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    setExecuting(false);
  };

  const handleSendCommand = () => {
    if (!commandInput.trim() || executing) return;
    setChatMessages(prev => [...prev, { type: 'agent_start', agent_id: 'user', message: `👤 Tu: ${commandInput}`, ts: Date.now() }]);
    setCommandInput('');
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
                      <div className="rl-template-agents">{t.agents.map(a => <span key={a}>{AGENTS_META[a]?.icon || '🤖'}</span>)}</div>
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
                        <span>{meta.icon}</span><span style={{ color: meta.bg }}>{meta.short}</span>
                        {isTested && <span className="rl-chip-ok">✓</span>}
                      </button>
                    );
                  })}
                </div>

                <button className="rl-btn-primary" onClick={handleCreateAndStart} disabled={!newGoal.trim() || launching}>
                  {launching ? <><RefreshCw size={14} className="spin" /> Avvio in corso...</> : <><Play size={14} /> Crea e Avvia</>}
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
          />
        )}

        {sessionData ? (
          <>
            {/* Header */}
            <div className="rl-dashboard-header">
              <div className="rl-dashboard-title">
                <Target size={16} /><span>{sessionData.name}</span>
                <span className={`rl-badge rl-badge-${executing ? 'active' : sessionData.status}`}>{executing ? 'IN ESECUZIONE' : sessionData.status?.toUpperCase()}</span>
                {executing && <RefreshCw size={14} className="spin" />}
              </div>
              <div className="rl-dashboard-actions">
                <span className="rl-progress">{progress.done}/{progress.total} obiettivi</span>
                {!executing ? (
                  <button className="rl-btn-primary" onClick={handleStartResearch}>
                    <Play size={14} /> Avvia Ricerca
                  </button>
                ) : (
                  <button className="rl-btn" onClick={handleStopResearch} style={{ color: '#ff5555', borderColor: 'rgba(255,85,85,0.3)' }}>
                    <StopCircle size={14} /> Ferma
                  </button>
                )}
                {!executing && sessionData.status === 'completed' && (
                  <button className="rl-btn" onClick={handleGenerateNextSteps} disabled={generatingSteps}>
                    {generatingSteps ? <RefreshCw size={14} className="spin" /> : <GitBranch size={14} />} Next Steps
                  </button>
                )}
                <button className="rl-btn-icon" onClick={() => { setActiveSessionId(null); setSessionData(null); closeAgentConfig(); }}>
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Agents Grid — clickable chips that open config */}
            <div className="rl-agents-grid">
              {sessionData.agents?.map(agent => {
                const meta = AGENTS_META[agent.agent_id || agent.id] || getAgentColor(agent.agent_id);
                const state = agentStates[agent.agent_id || agent.id] || {};
                const isWorking = state.status === 'working';
                const config = getAgentConfig(agent.agent_id || agent.id);
                return (
                  <div key={agent.agent_id || agent.id}
                    className={`rl-agent-card-live ${isWorking ? 'working' : ''} ${state.status === 'done' ? 'done' : ''} ${state.status === 'error' ? 'error' : ''}`}
                    style={{ borderColor: isWorking ? meta.bg : 'rgba(255,255,255,0.06)', cursor: 'pointer' }}
                    onClick={() => selectAgentForConfig(agent.agent_id || agent.id)}>
                    <div className="rl-agent-icon-live" style={{ background: meta.bg + '20', color: meta.bg }}>
                      <span>{meta.icon}</span>
                      {isWorking && <span className="rl-agent-pulse" style={{ background: meta.bg }} />}
                    </div>
                    <div className="rl-agent-info-live">
                      <div className="rl-agent-name-live" style={{ color: meta.bg }}>{meta.name || agent.agent_id}</div>
                      <div className="rl-agent-model-live">{config.model || agent.model}</div>
                      {state.task && <div className="rl-agent-task-live">{state.task}</div>}
                    </div>
                    <div className="rl-agent-status-live" style={{ color: isWorking ? meta.bg : state.status === 'done' ? '#3fb950' : state.status === 'error' ? '#ff5555' : '#5a5e72' }}>
                      {isWorking ? <RefreshCw size={12} className="spin" /> : state.status === 'done' ? <CheckCircle size={12} /> : state.status === 'error' ? <AlertTriangle size={12} /> : <Circle size={12} />}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Goal + Kanban */}
            <div className="rl-goal-display"><MessageSquare size={14} /><span>{sessionData.goal}</span></div>
            <div className="rl-kanban">
              <div className="rl-kanban-col"><div className="rl-kanban-header" style={{ borderColor: '#5a5e72' }}><Circle size={12} /> Da Fare ({pendingO.length})</div>{pendingO.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}</div>
              <div className="rl-kanban-col"><div className="rl-kanban-header" style={{ borderColor: '#00d2ff' }}><RefreshCw size={12} /> In Corso ({progressO.length})</div>{progressO.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}</div>
              <div className="rl-kanban-col"><div className="rl-kanban-header" style={{ borderColor: '#3fb950' }}><CheckCircle size={12} /> Completati ({doneO.length})</div>{doneO.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}</div>
              <div className="rl-kanban-col"><div className="rl-kanban-header" style={{ borderColor: '#ff5555' }}><AlertTriangle size={12} /> Bloccati ({failedO.length})</div>{failedO.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}</div>
            </div>

            {/* Agent Command Input — always visible */}
            <div className="rl-agent-input">
              <input
                className="rl-agent-input-field"
                type="text"
                placeholder="Scrivi un comando per il team di agenti..."
                value={commandInput}
                onChange={e => setCommandInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && commandInput.trim()) handleSendCommand(); }}
                disabled={executing}
              />
              <button className="rl-btn-primary" onClick={handleSendCommand} disabled={!commandInput.trim() || executing}>
                <Send size={14} /> Invia
              </button>
            </div>

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
                        {msg.agent_id && meta.icon && <span className="rl-chat-msg-icon">{meta.icon}</span>}
                        {msg.agent_id && <span className="rl-chat-msg-agent" style={{ color: meta.bg || color }}>{meta.name || msg.agent_id}</span>}
                        <span className="rl-chat-msg-type" style={{ color }}>{msg.type.replace('_', ' ').toUpperCase()}</span>
                      </div>
                      {msg.type === 'agent_thinking' && <div className="rl-chat-msg-thinking">{msg.thinking?.slice(0, 500)}</div>}
                      {msg.type === 'agent_response' && <div className="rl-chat-msg-response">{msg.response?.slice(0, 500)}</div>}
                      {(msg.type === 'agent_start' || msg.type === 'objective_complete' || msg.type === 'all_done' || msg.type === 'agent_actions' || msg.type === 'error') && (
                        <div className="rl-chat-msg-text">{msg.message}</div>
                      )}
                    </div>
                  );
                })}
                {executing && <div className="rl-chat-typing">Agenti al lavoro <RefreshCw size={10} className="spin" /></div>}
                <div ref={chatEndRef} />
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
          </>
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