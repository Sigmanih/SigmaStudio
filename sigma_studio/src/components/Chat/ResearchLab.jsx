import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, Square, RotateCcw, ChevronRight, Cpu, Target, Layers, RefreshCw, 
  Database, Wifi, WifiOff, X, MessageSquare, Send, Plus, Trash2, 
  CheckCircle, Circle, Clock, AlertTriangle, ArrowRight, GitBranch
} from 'lucide-react';
import useResearchPipeline from './core/useResearchPipeline';

// ==============================================================================
// RESEARCH LAB v2 — Multi-Session Research with Micro-Objectives & Next Steps
// ==============================================================================

const PIPELINE_TEMPLATES = {
  math_research: {
    id: 'math_research',
    name: '∑ Ricerca Matematica',
    description: 'Teoria, test computazionali, visualizzazioni D3 e revisione formale',
    agents: ['math1', 'test-engineer', 'viz-designer', 'proof-reviewer'],
  },
  full_analysis: {
    id: 'full_analysis',
    name: '📋 Analisi Completa',
    description: 'Coordinamento, ricerca, sviluppo test, visualizzazione e revisione',
    agents: ['sigma_architect', 'math1', 'code_architect', 'viz-designer', 'proof-reviewer'],
  },
  code_review: {
    id: 'code_review',
    name: '⚙️ Code Review',
    description: 'Analisi codice, refactoring, test, ottimizzazione e documentazione',
    agents: ['code_architect', 'sigma_architect', 'proof-reviewer'],
  },
  general_research: {
    id: 'general_research',
    name: '🔬 Ricerca Generale',
    description: 'Ricerca scientifica completa con validazione e documentazione',
    agents: ['sigma_architect', 'math1', 'test-engineer', 'proof-reviewer'],
  },
};

function SessionListItem({ session, isActive, onClick, onDelete }) {
  const statusColors = {
    created: '#5a5e72', active: '#00d2ff', completed: '#3fb950', failed: '#ff5555',
  };
  const statusIcons = {
    created: '📝', active: '⚡', completed: '✅', failed: '❌',
  };
  return (
    <div className={`rl-session-item ${isActive ? 'active' : ''}`} onClick={onClick}>
      <div className="rl-session-status" style={{ color: statusColors[session.status] || '#5a5e72' }}>
        {statusIcons[session.status] || '📝'}
      </div>
      <div className="rl-session-info">
        <div className="rl-session-name">{session.name}</div>
        <div className="rl-session-meta">
          {session.objectives_total > 0 && `${session.objectives_done}/${session.objectives_total} obiettivi · `}
          {session.agents_count} agenti
        </div>
      </div>
      <button className="rl-session-delete" onClick={e => { e.stopPropagation(); onDelete(session.id); }}>
        <Trash2 size={12} />
      </button>
    </div>
  );
}

function ObjectiveCard({ obj, agentsMeta }) {
  const statusColors = {
    pending: '#5a5e72', in_progress: '#00d2ff', done: '#3fb950', failed: '#ff5555',
  };
  const statusIcons = {
    pending: <Circle size={14} />, in_progress: <RefreshCw size={14} className="spin" />,
    done: <CheckCircle size={14} />, failed: <AlertTriangle size={14} />,
  };
  const agentMeta = agentsMeta[obj.assigned_to] || {};
  return (
    <div className="rl-objective-card" style={{ borderLeftColor: statusColors[obj.status] || '#5a5e72' }}>
      <div className="rl-objective-header">
        <span className="rl-objective-status" style={{ color: statusColors[obj.status] }}>
          {statusIcons[obj.status]}
        </span>
        <span className="rl-objective-title">{obj.title}</span>
        {agentMeta.icon && <span className="rl-objective-agent" title={agentMeta.name}>{agentMeta.icon}</span>}
      </div>
      <div className="rl-objective-desc">{obj.description}</div>
      {obj.completion_criteria && (
        <div className="rl-objective-criteria">✓ {obj.completion_criteria}</div>
      )}
    </div>
  );
}

export default function ResearchLab({ onClose, onTasksUpdated, addToast }) {
  const pipeline = useResearchPipeline(onTasksUpdated, addToast);
  const {
    AGENTS_META, getAgentColor, agentStates,
    pipelineActionsLog, pipelineStatus, pipelineError,
    startPipeline, stopPipeline, resetPipeline,
    activeTemplate, selectTemplate,
    feedbackCycles, agentResponses,
    saveChatMessage, loadChatMessages, pipelineId,
  } = pipeline;

  // --- Research Sessions State ---
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionData, setSessionData] = useState(null);
  const [showNewSession, setShowNewSession] = useState(false);
  const [newGoal, setNewGoal] = useState('');
  const [newTemplate, setNewTemplate] = useState('full_analysis');
  const [decomposing, setDecomposing] = useState(false);
  const [generatingSteps, setGeneratingSteps] = useState(false);
  const [nextSteps, setNextSteps] = useState([]);

  // ============================
  // Load sessions on mount
  // ============================
  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/research/list');
      const data = await res.json();
      if (data.success) setSessions(data.sessions || []);
    } catch (e) { console.error('Failed to load sessions:', e); }
  };

  const fetchSessionStatus = async (sessionId) => {
    try {
      const res = await fetch(`/api/research/status?id=${encodeURIComponent(sessionId)}`);
      const data = await res.json();
      if (data.success) setSessionData(data.session);
    } catch (e) { console.error('Failed to load session status:', e); }
  };

  const handleSelectSession = (sessionId) => {
    setActiveSessionId(sessionId);
    fetchSessionStatus(sessionId);
  };

  const handleCreateSession = async () => {
    if (!newGoal.trim()) return;
    try {
      const template = PIPELINE_TEMPLATES[newTemplate];
      const agents = (template?.agents || ['sigma_architect']).map(id => ({
        agent_id: id,
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        temperature: 0.4,
      }));
      const res = await fetch('/api/research/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newGoal.slice(0, 80),
          goal: newGoal,
          pipeline_template: newTemplate,
          agents,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setShowNewSession(false);
        setNewGoal('');
        fetchSessions();
        handleSelectSession(data.session.id);
        // Auto-decompose
        handleDecompose(data.session.id, newGoal, agents);
        if (addToast) addToast('✅ Sessione di ricerca creata', 'success', 3000);
      }
    } catch (e) {
      if (addToast) addToast('❌ Errore creazione sessione', 'error', 3000);
    }
  };

  const handleDecompose = async (sessionId, goal, agents) => {
    setDecomposing(true);
    try {
      const res = await fetch('/api/research/decompose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, goal, agents }),
      });
      const data = await res.json();
      if (data.success) {
        fetchSessionStatus(sessionId);
        if (addToast) addToast(`📋 Scomposto in ${data.count} micro-obiettivi`, 'success', 4000);
      } else {
        if (addToast) addToast(`⚠️ ${data.error}`, 'warning', 4000);
      }
    } catch (e) {
      if (addToast) addToast('❌ Errore decomposizione', 'error', 3000);
    }
    setDecomposing(false);
  };

  const handleGenerateNextSteps = async () => {
    if (!activeSessionId) return;
    setGeneratingSteps(true);
    try {
      const res = await fetch('/api/research/next_steps', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId }),
      });
      const data = await res.json();
      if (data.success) {
        setNextSteps(data.next_steps || []);
        fetchSessionStatus(activeSessionId);
        if (addToast) addToast('💡 Next steps generati!', 'success', 3000);
      }
    } catch (e) {
      if (addToast) addToast('❌ Errore', 'error', 3000);
    }
    setGeneratingSteps(false);
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await fetch('/api/research/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: sessionId }),
      });
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setSessionData(null);
      }
      fetchSessions();
    } catch (e) { console.error(e); }
  };

  const handleUseNextStep = (step) => {
    setNewGoal(step.description);
    setShowNewSession(true);
  };

  // Group objectives by status for Kanban
  const getObjectives = () => sessionData?.micro_objectives || [];
  const pendingObjectives = getObjectives().filter(o => o.status === 'pending');
  const inProgressObjectives = getObjectives().filter(o => o.status === 'in_progress');
  const doneObjectives = getObjectives().filter(o => o.status === 'done');
  const failedObjectives = getObjectives().filter(o => o.status === 'failed');

  const isRunning = pipelineStatus === 'running' || pipelineStatus === 'planning';

  return (
    <div className="research-lab-v2">
      {/* LEFT BAR — Session List */}
      <div className="rl-sidebar">
        <div className="rl-sidebar-header">
          <Target size={14} />
          <span>Ricerche</span>
          <button className="rl-btn-icon" onClick={() => setShowNewSession(true)} title="Nuova ricerca">
            <Plus size={14} />
          </button>
        </div>
        <div className="rl-session-list">
          {sessions.map(s => (
            <SessionListItem
              key={s.id}
              session={s}
              isActive={activeSessionId === s.id}
              onClick={() => handleSelectSession(s.id)}
              onDelete={handleDeleteSession}
            />
          ))}
          {sessions.length === 0 && (
            <div className="rl-empty">
              <Layers size={24} />
              <span>Nessuna ricerca</span>
              <button className="rl-btn" onClick={() => setShowNewSession(true)}>Nuova Ricerca</button>
            </div>
          )}
        </div>
      </div>

      {/* MAIN AREA */}
      <div className="rl-main">
        {/* New Session Modal */}
        {showNewSession && (
          <div className="rl-new-session-overlay" onClick={() => setShowNewSession(false)}>
            <div className="rl-new-session" onClick={e => e.stopPropagation()}>
              <div className="rl-new-header">
                <span>🔬 Nuova Ricerca</span>
                <button className="rl-btn-icon" onClick={() => setShowNewSession(false)}><X size={14} /></button>
              </div>
              <div className="rl-new-body">
                <label>Obiettivo della ricerca</label>
                <textarea
                  className="rl-goal-input"
                  value={newGoal}
                  onChange={e => setNewGoal(e.target.value)}
                  placeholder="Descrivi l'obiettivo della ricerca. Es: Studiare le transizioni nella congettura di Collatz per n fino a 10^6, analizzando le classi modulo 6 e producendo visualizzazioni interattive..."
                  rows={4}
                />
                <label>Pipeline template</label>
                <div className="rl-template-grid">
                  {Object.values(PIPELINE_TEMPLATES).map(t => (
                    <div
                      key={t.id}
                      className={`rl-template-card ${newTemplate === t.id ? 'active' : ''}`}
                      onClick={() => setNewTemplate(t.id)}
                    >
                      <div className="rl-template-name">{t.name}</div>
                      <div className="rl-template-desc">{t.description}</div>
                      <div className="rl-template-agents">
                        {t.agents.map(a => {
                          const meta = AGENTS_META[a] || {};
                          return <span key={a} title={meta.name}>{meta.icon || '🤖'}</span>;
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  className="rl-btn-primary"
                  onClick={handleCreateSession}
                  disabled={!newGoal.trim()}
                >
                  <Play size={14} /> Crea e Avvia Ricerca
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Session Dashboard */}
        {sessionData ? (
          <>
            <div className="rl-dashboard-header">
              <div className="rl-dashboard-title">
                <Target size={16} />
                <span>{sessionData.name}</span>
                <span className={`rl-badge rl-badge-${sessionData.status}`}>
                  {sessionData.status?.toUpperCase()}
                </span>
              </div>
              <div className="rl-dashboard-actions">
                <span className="rl-progress">{sessionData.objectives_progress || '0/0'} obiettivi</span>
                {sessionData.status === 'completed' && (
                  <button className="rl-btn" onClick={handleGenerateNextSteps} disabled={generatingSteps}>
                    {generatingSteps ? <RefreshCw size={14} className="spin" /> : <GitBranch size={14} />}
                    {generatingSteps ? 'Generando...' : 'Next Steps'}
                  </button>
                )}
                <button className="rl-btn-icon" onClick={() => { setActiveSessionId(null); setSessionData(null); }}>
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Goal */}
            <div className="rl-goal-display">
              <MessageSquare size={14} />
              <span>{sessionData.goal}</span>
            </div>

            {/* Kanban Board */}
            <div className="rl-kanban">
              <div className="rl-kanban-col">
                <div className="rl-kanban-header" style={{ borderColor: '#5a5e72' }}>
                  <Circle size={12} /> Da Fare ({pendingObjectives.length})
                </div>
                {pendingObjectives.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}
              </div>
              <div className="rl-kanban-col">
                <div className="rl-kanban-header" style={{ borderColor: '#00d2ff' }}>
                  <RefreshCw size={12} /> In Corso ({inProgressObjectives.length})
                </div>
                {inProgressObjectives.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}
              </div>
              <div className="rl-kanban-col">
                <div className="rl-kanban-header" style={{ borderColor: '#3fb950' }}>
                  <CheckCircle size={12} /> Completati ({doneObjectives.length})
                </div>
                {doneObjectives.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}
              </div>
              <div className="rl-kanban-col">
                <div className="rl-kanban-header" style={{ borderColor: '#ff5555' }}>
                  <AlertTriangle size={12} /> Bloccati ({failedObjectives.length})
                </div>
                {failedObjectives.map(o => <ObjectiveCard key={o.id} obj={o} agentsMeta={AGENTS_META} />)}
              </div>
            </div>

            {/* Agents Bar */}
            <div className="rl-agents-bar">
              {sessionData.agents?.map(agent => {
                const meta = AGENTS_META[agent.agent_id || agent.id] || getAgentColor(agent.agent_id);
                return (
                  <div key={agent.agent_id || agent.id} className="rl-agent-chip" style={{ borderColor: meta.bg }}>
                    <span>{meta.icon}</span>
                    <span style={{ color: meta.bg }}>{meta.short || agent.agent_id}</span>
                    <span className="rl-agent-model">{agent.model}</span>
                  </div>
                );
              })}
            </div>

            {/* Next Steps */}
            {nextSteps.length > 0 && (
              <div className="rl-next-steps">
                <div className="rl-next-header">
                  <GitBranch size={14} />
                  <span>Prossimi Passi Suggeriti</span>
                </div>
                <div className="rl-next-list">
                  {nextSteps.map((step, i) => (
                    <div key={i} className="rl-next-item">
                      <div className="rl-next-title">
                        <span className={`rl-priority rl-priority-${step.priority}`}>
                          {step.priority?.toUpperCase()}
                        </span>
                        {step.title}
                      </div>
                      <div className="rl-next-desc">{step.description}</div>
                      <button className="rl-btn-sm" onClick={() => handleUseNextStep(step)}>
                        <Play size={10} /> Usa come nuova ricerca
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="rl-welcome">
            <Cpu size={48} />
            <h2>Research Lab v2</h2>
            <p>Seleziona una ricerca esistente o creane una nuova per iniziare.</p>
            <button className="rl-btn-primary" onClick={() => setShowNewSession(true)}>
              <Plus size={16} /> Nuova Ricerca
            </button>
          </div>
        )}
      </div>
    </div>
  );
}