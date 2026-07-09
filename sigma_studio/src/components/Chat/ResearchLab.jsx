import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Square, RotateCcw, ChevronRight, Cpu, Target, Layers, RefreshCw, Database, GitCompare, Settings, Wifi, WifiOff, X, Sliders, MessageSquare, Send } from 'lucide-react';
import useResearchPipeline from './core/useResearchPipeline';

const STATUS_LABELS = {
  idle: 'In attesa — seleziona un template',
  planning: 'Pianificazione in corso...',
  running: 'Esecuzione pipeline...',
  paused: 'In pausa',
  done: 'Pipeline completata ✅',
  error: 'Errore ❌',
};

const STATUS_ICONS = {
  idle: <Target size={14} />,
  planning: <RefreshCw size={14} className="spin" />,
  running: <RefreshCw size={14} className="spin" />,
  done: <Cpu size={14} />,
  error: <Cpu size={14} />,
};

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

function AgentChatMessage({ msg, meta }) {
  const isUser = msg.message_type === 'user';
  const isSystem = msg.message_type === 'system';
  return (
    <div className={`agent-chat-msg ${isUser ? 'user-msg' : ''} ${isSystem ? 'system-msg' : ''}`}
      style={{ borderLeftColor: isUser ? '#00d2ff' : isSystem ? '#d29922' : (meta?.bg || '#8b8fa3') }}>
      <div className="agent-chat-msg-header">
        <span className="agent-chat-msg-icon">{isUser ? '👤' : isSystem ? '⚙️' : (meta?.icon || '🤖')}</span>
        <span className="agent-chat-msg-agent" style={{ color: isUser ? '#00d2ff' : isSystem ? '#d29922' : (meta?.bg || '#8b8fa3') }}>
          {isUser ? 'Tu' : isSystem ? 'Sistema' : (meta?.name || msg.agent_id)}
        </span>
        <span className="agent-chat-msg-time">{msg.timestamp ? msg.timestamp.slice(11, 19) : ''}</span>
      </div>
      <div className="agent-chat-msg-text">{msg.message?.slice(0, 2000)}</div>
      {msg.actions?.length > 0 && (
        <div className="agent-chat-msg-actions">
          {msg.actions.map((a, i) => (
            <span key={i} className="agent-chat-action-chip">{a.type} ✓</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ResearchLab({ onClose, onTasksUpdated, addToast }) {
  const pipeline = useResearchPipeline(onTasksUpdated, addToast);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef(null);
  const prevAgentStatesRef = useRef({});
  const prevLogLengthRef = useRef(0);

  const {
    pipelineGoal, setPipelineGoal,
    pipelineStatus, pipelineError,
    enabledAgents, toggleAgent, getAgentColor,
    agentStates, currentStep, totalSteps,
    startPipeline, stopPipeline, resetPipeline,
    activeTemplate, selectTemplate, getTemplateList,
    memorySnapshots, feedbackCycles,
    PIPELINE_TEMPLATES, AGENTS_META,
    getAgentConfig, updateAgentConfig,
    selectedAgentId, selectAgentForConfig, closeAgentConfig,
    testStates, testAgentConnection,
    pipelineActionsLog, pipelineGoal: goalFromHook,
    agentResponses,
    saveChatMessage, loadChatMessages, pipelineId,
  } = pipeline;

  const isRunning = pipelineStatus === 'running' || pipelineStatus === 'planning';
  const canStart = pipelineGoal.trim() && !isRunning;
  const templateList = getTemplateList();
  const currentTemplate = PIPELINE_TEMPLATES[activeTemplate];

  const selectedAgent = selectedAgentId ? {
    id: selectedAgentId,
    meta: AGENTS_META[selectedAgentId] || getAgentColor(selectedAgentId),
    config: getAgentConfig(selectedAgentId),
  } : null;

  // Track agentStates changes → chat messages
  useEffect(() => {
    const prev = prevAgentStatesRef.current;
    Object.entries(agentStates).forEach(([agentId, state]) => {
      const prevState = prev[agentId];
      const meta = AGENTS_META[agentId];
      
      // Agent just started working
      if (state?.status === 'active' && (!prevState || prevState.status !== 'active')) {
        const taskName = state?.task || 'Lavorando...';
        addChatMessage(agentId, `▶️ Inizio: ${taskName}`, 'action', meta);
      }
      
      // Agent just completed work
      if (state?.status === 'done' && (!prevState || prevState.status === 'active')) {
        const summary = state?.successful_actions 
          ? `✅ Completato: ${state.successful_actions}/${state.total_actions} azioni riuscite`
          : '✅ Completato';
        addChatMessage(agentId, summary, 'response', meta);
      }
      
      // Agent failed
      if (state?.status === 'failed' && (!prevState || prevState.status === 'active')) {
        const error = state?.error || state?.error_detail || (state?.review_notes ? `Revisione fallita: ${state?.review_notes?.slice(0, 100)}` : 'Errore sconosciuto (nessun dettaglio dal backend)');
        addChatMessage(agentId, `❌ Fallito: ${error}`, 'error', meta);
      }
      
      // New task arrived (orchestrate mode)
      if (state?.task && (!prevState || prevState.task !== state.task)) {
        if (state.status === 'pending') {
          addChatMessage(agentId, `📋 Assegnato: ${state.task}`, 'action', meta);
        }
      }
    });
    prevAgentStatesRef.current = JSON.parse(JSON.stringify(agentStates));
  }, [agentStates]);

  // Track AI responses (from agent_task_iteration SSE events)
  const prevResponsesRef = useRef(0);
  useEffect(() => {
    if (agentResponses.length > prevResponsesRef.current) {
      const newResps = agentResponses.slice(prevResponsesRef.current);
      newResps.forEach(r => {
        const meta = AGENTS_META[r.agent_id];
        addChatMessage(r.agent_id, `💬 ${r.response?.slice(0, 1000)}`, 'response', meta);
      });
      prevResponsesRef.current = agentResponses.length;
    }
  }, [agentResponses]);

  // Track pipeline actions log for new entries
  useEffect(() => {
    if (pipelineActionsLog.length > prevLogLengthRef.current) {
      const newActions = pipelineActionsLog.slice(prevLogLengthRef.current);
      newActions.forEach(action => {
        if (action.type === 'create_file' || action.type === 'run_test' || action.type === 'edit_file') {
          const agentId = action.bot_name || 'agente0';
          const meta = AGENTS_META[agentId];
          const icon = action.type === 'create_file' ? '📄' : action.type === 'edit_file' ? '✏️' : '🧪';
          addChatMessage(agentId, `${icon} ${action.path || action.message || ''}`, 'action', meta);
        }
      });
      prevLogLengthRef.current = pipelineActionsLog.length;
    }
  }, [pipelineActionsLog]);

  // Load saved messages on mount
  useEffect(() => {
    loadChatMessages().then(saved => {
      if (saved.length > 0) {
        setChatMessages(saved);
      }
    });
  }, []);

  // Clear chat on new pipeline
  useEffect(() => {
    if (pipelineStatus === 'planning') {
      // Don't clear — keep persisted messages
      prevLogLengthRef.current = 0;
      prevAgentStatesRef.current = {};
    }
  }, [pipelineStatus]);

  // Scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const addChatMessage = useCallback((agentId, text, type = 'action', meta = null) => {
    if (!text) return;
    // Save to backend immediately
    saveChatMessage(agentId, text, type);
    setChatMessages(prev => {
      if (prev.length > 0 && prev[prev.length - 1].message === text) return prev;
      return [...prev, {
        id: Date.now() + Math.random(),
        agent_id: agentId,
        message: text,
        message_type: type,
        actions: [],
        timestamp: new Date().toISOString(),
      }];
    });
  }, [saveChatMessage]);

  // Send user message to the chat (visible locally)
  const sendUserMessage = useCallback(() => {
    const text = chatInput.trim();
    if (!text) return;
    addChatMessage('user', text, 'user');
    setChatInput('');
  }, [chatInput, addChatMessage]);

  const handleChatKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendUserMessage();
    }
  };

  // Typing indicator — shows "sta scrivendo..." for active agents
  const [typingAgents, setTypingAgents] = useState({});
  useEffect(() => {
    const newTyping = {};
    Object.entries(agentStates).forEach(([agentId, state]) => {
      if (state?.status === 'active') {
        const meta = AGENTS_META[agentId];
        if (!typingAgents[agentId]) {
          newTyping[agentId] = {
            meta,
            startedAt: Date.now(),
            text: `${meta?.icon || '🤖'} ${meta?.name || agentId} sta scrivendo...`,
          };
        } else {
          newTyping[agentId] = typingAgents[agentId];
        }
      }
    });
    setTypingAgents(newTyping);
  }, [agentStates]);

  return (
    <div className="research-lab-new">
      {/* LEFT PANEL */}
      <div className="research-lab-panel">
        <div className="research-lab-header">
          <div className="research-lab-title">
            <Cpu size={16} />
            <span>🔬 Research Lab</span>
          </div>
          <div className="research-lab-controls">
            {!isRunning ? (
              <button className="research-btn research-btn-primary" onClick={startPipeline} disabled={!canStart}>
                <Play size={13} /> Avvia
              </button>
            ) : (
              <button className="research-btn research-btn-danger" onClick={stopPipeline}>
                <Square size={13} />
              </button>
            )}
            <button className="research-btn research-btn-ghost" onClick={resetPipeline} disabled={isRunning}>
              <RotateCcw size={13} />
            </button>
            <button className="research-btn research-btn-ghost" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="research-compact-section">
          <div className="research-compact-status">
            {STATUS_ICONS[pipelineStatus] || STATUS_ICONS.idle}
            <span className="research-status-text">{STATUS_LABELS[pipelineStatus]}</span>
            {isRunning && <span className="research-status-detail">Nodo {currentStep}/{totalSteps}</span>}
            {feedbackCycles > 0 && pipelineStatus === 'done' && <span className="research-status-feedback"> · {feedbackCycles} feedback</span>}
          </div>
          <div className="research-compact-templates">
            {templateList.filter(t => t.id !== 'none').slice(0, 4).map(t => (
              <button key={t.id} className={`research-template-chip ${activeTemplate === t.id ? 'active' : ''}`} onClick={() => selectTemplate(t.id)} disabled={isRunning}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="research-path-compact">
          {enabledAgents.map((agent, i) => {
            const meta = AGENTS_META[agent.id] || getAgentColor(agent.id);
            const state = agentStates[agent.id];
            const isActive = state?.status === 'active';
            const isDone = state?.status === 'done';
            return (
              <React.Fragment key={agent.id}>
                <div className={`research-path-node-compact ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                  style={{ borderColor: meta.bg }} onClick={() => selectAgentForConfig(agent.id)}>
                  <span className="research-path-icon-compact">{meta.icon}</span>
                  {isActive && <span className="research-path-pulse" style={{ background: meta.bg }} />}
                </div>
                {i < enabledAgents.length - 1 && <ChevronRight size={14} className="research-path-arrow-compact" />}
              </React.Fragment>
            );
          })}
        </div>

        <div className="research-agent-chips">
          {Object.entries(AGENTS_META).map(([id, meta]) => {
            const isEnabled = enabledAgents.some(a => a.id === id);
            const isSelected = selectedAgentId === id;
            const hasMemory = memorySnapshots[id];
            const config = getAgentConfig(id);
            const isTested = testStates[id]?.success;
            return (
              <button key={id} className={`research-chip-compact ${isEnabled ? 'on' : ''} ${isSelected ? 'sel' : ''}`}
                style={{ borderColor: isEnabled ? meta.bg : 'rgba(255,255,255,0.06)' }}
                onClick={() => selectAgentForConfig(id)} disabled={isRunning}
                title={`${meta.name}: ${config.provider}/${config.model}`}>
                <span>{meta.icon}{meta.short.slice(0,3)}</span>
                {isTested && <span className="research-chip-ok">✓</span>}
                {hasMemory && <Database size={8} className="research-chip-mem" />}
              </button>
            );
          })}
        </div>

        <div className="research-compact-stats">
          <span>📄 {Object.values(memorySnapshots).reduce((s, m) => s + (m.files_created || 0), 0)} file</span>
          <span>🧪 {Object.values(memorySnapshots).reduce((s, m) => s + (m.tests_passed || 0), 0)} test</span>
          <span>⚡ {Object.values(memorySnapshots).reduce((s, m) => s + (m.actions || 0), 0)} azioni</span>
        </div>
      </div>

      {/* RIGHT PANEL — Agent Chat with Input */}
      <div className="research-chat-sidebar">
        <div className="research-chat-sidebar-header">
          <MessageSquare size={14} />
          <span>Chat Agenti</span>
          <span className="research-chat-sidebar-count">{chatMessages.length}</span>
        </div>
        <div className="research-chat-sidebar-msgs">
          {chatMessages.length === 0 && pipelineStatus === 'idle' && (
            <div className="research-chat-sidebar-empty">
              <MessageSquare size={24} />
              <span>I messaggi degli agenti appariranno qui durante l'esecuzione</span>
              <span style={{ fontSize: '0.6rem', opacity: 0.5, marginTop: 8 }}>Puoi anche scrivere messaggi nella chat sottostante</span>
            </div>
          )}
          {chatMessages.map(msg => (
            <AgentChatMessage key={msg.id} msg={msg} meta={AGENTS_META[msg.agent_id]} />
          ))}
          {/* Typing indicators — shows which agents are currently working */}
          {Object.entries(typingAgents).map(([agentId, ta]) => (
            <div key={agentId} className="research-typing-indicator" style={{ borderLeftColor: ta.meta?.bg || 'var(--primary)' }}>
              <span>{ta.meta?.icon || '🤖'} <strong style={{ color: ta.meta?.bg || 'var(--primary)' }}>{ta.meta?.name || agentId}</strong> sta scrivendo</span>
              <span className="research-typing-dots">
                <span /><span /><span />
              </span>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        {/* Chat Input */}
        <div className="research-chat-input">
          <input
            className="research-chat-input-field"
            type="text"
            placeholder={isRunning ? "Scrivi un messaggio agli agenti..." : "In attesa dell'esecuzione..."}
            value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            onKeyDown={handleChatKeyDown}
            disabled={!isRunning && chatMessages.length === 0}
          />
          <button className="research-chat-send-btn" onClick={sendUserMessage} disabled={!chatInput.trim()}>
            <Send size={14} />
          </button>
        </div>
      </div>

      {pipelineError && <div className="research-error"><span>❌ {pipelineError}</span></div>}

      {selectedAgent && (
        <AgentConfigPanel
          agentId={selectedAgent.id} meta={selectedAgent.meta} config={selectedAgent.config}
          onUpdate={updateAgentConfig} onClose={closeAgentConfig}
          testState={testStates[selectedAgent.id]} onTest={testAgentConnection}
        />
      )}
    </div>
  );
}