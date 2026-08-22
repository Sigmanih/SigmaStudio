import React, { useState, useRef, useEffect, useMemo } from 'react';
import { 
  Send, Bot, User, Sparkles, Brain, Check, Copy, RefreshCw, 
  Terminal, FileCode, Trash2, ArrowRight, ShieldCheck, Zap, 
  ChevronDown, ChevronUp, SplitSquareVertical, Layers, Folder, 
  Plus, Edit2, Clock, Search, X, MessageSquare 
} from 'lucide-react';
import DeveloperModelSelector from './DeveloperModelSelector';

const STORAGE_TASKS_KEY = 'sigma_dev_tasks_v2';
const STORAGE_ACTIVE_TASK_KEY = 'sigma_dev_active_task_id_v2';

const createNewTask = (title = 'Nuovo Task') => ({
  id: `task_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
  title,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  model: 'sigmaengine',
  autoExecuteTools: true,
  messages: [
    {
      role: 'assistant',
      content: '👋 Ciao! Sono il tuo **Admin AI Developer Agent** di Sigma Studio.\n\nHo permessi completi di amministrazione sul workspace: posso esplorare, modificare, creare ed eliminare file, ed eseguire comandi PowerShell/Bash direttamente nel terminale.\n\nCome posso aiutarti nello sviluppo?',
      tools: []
    }
  ]
});

const formatTimeAgo = (isoString) => {
  if (!isoString) return '';
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Adesso';
    if (diffMins < 60) return `${diffMins} min fa`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h fa`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}g fa`;
  } catch (e) {
    return '';
  }
};

const cleanMessageText = (text) => {
  if (!text) return '';
  let cleaned = text.replace(/```tool:\w+\s*[\s\S]*?```/gi, '');
  cleaned = cleaned.replace(/<(?:execute_command|shell|terminal|read_file|write_to_file|list_dir|search_code)>[\s\S]*?<\/(?:execute_command|shell|terminal|read_file|write_to_file|list_dir|search_code)>/gi, '');
  return cleaned.trim();
};

const sanitizeTasksForLocalStorage = (tasksList) => {
  return (tasksList || []).slice(0, 15).map(t => ({
    ...t,
    messages: (t.messages || []).slice(-30).map(m => ({
      role: m.role,
      content: typeof m.content === 'string' ? m.content.slice(0, 50000) : m.content,
      thought: typeof m.thought === 'string' ? m.thought.slice(0, 10000) : m.thought,
      metrics: m.metrics,
      tools: (m.tools || []).map(tool => ({
        tool: tool.tool,
        status: tool.status,
        params: tool.params,
        result: tool.result ? {
          success: tool.result.success,
          message: tool.result.message,
          diff: typeof tool.result.diff === 'string' ? tool.result.diff.slice(0, 10000) : undefined,
          path: tool.result.path
        } : undefined
      }))
    }))
  }));
};

export default function AdminAgentChat({
  workspaceRoot,
  activeFilePath,
  activeFileContent,
  onApplyDiff,
  onOpenFile,
  onExecuteTerminalCommand,
  onRefreshTree,
  theme,
  isLight
}) {
  // 1. Persistent Tasks State
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_TASKS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.debug('Error loading dev tasks from localStorage:', e);
    }
    return [createNewTask()];
  });

  const [activeTaskId, setActiveTaskId] = useState(() => {
    try {
      const savedActive = localStorage.getItem(STORAGE_ACTIVE_TASK_KEY);
      if (savedActive) return savedActive;
    } catch (e) {}
    return tasks[0]?.id || '';
  });

  // Load server-persisted tasks on initial mount
  useEffect(() => {
    fetch('/api/developer/tasks')
      .then(res => res.json())
      .then(data => {
        if (data.success && Array.isArray(data.tasks) && data.tasks.length > 0) {
          setTasks(data.tasks);
        }
      })
      .catch(err => console.debug('Could not load server tasks:', err));
  }, []);

  // Task selector UI state
  const [showTaskMenu, setShowTaskMenu] = useState(false);
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editTitleInput, setEditTitleInput] = useState('');

  // Input, Auto-Scroll & Streaming State
  const [input, setInput] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [expandedThoughts, setExpandedThoughts] = useState({});

  const chatEndRef = useRef(null);
  const taskMenuRef = useRef(null);

  // Active Task Resolution
  const activeTask = tasks.find(t => t.id === activeTaskId) || tasks[0] || createNewTask();
  const messages = activeTask.messages || [];
  const selectedModel = activeTask.model || 'sigmaengine';
  const autoExecuteTools = activeTask.autoExecuteTools ?? true;

  // 1. Sync full tasks to server file data/developer_tasks.json
  useEffect(() => {
    const timer = setTimeout(() => {
      fetch('/api/developer/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tasks })
      }).catch(err => console.debug('Server tasks sync error:', err));
    }, 500);
    return () => clearTimeout(timer);
  }, [tasks]);

  // 2. Persist sanitized lightweight tasks to localStorage
  useEffect(() => {
    try {
      const sanitized = sanitizeTasksForLocalStorage(tasks);
      localStorage.setItem(STORAGE_TASKS_KEY, JSON.stringify(sanitized));
      localStorage.setItem(STORAGE_ACTIVE_TASK_KEY, activeTask.id);
    } catch (e) {
      try {
        const minimal = sanitizeTasksForLocalStorage([activeTask]);
        localStorage.setItem(STORAGE_TASKS_KEY, JSON.stringify(minimal));
        localStorage.setItem(STORAGE_ACTIVE_TASK_KEY, activeTask.id);
      } catch (innerErr) {
        console.debug('LocalStorage quota reached; server persistence active.');
      }
    }
  }, [tasks, activeTask.id]);

  // Close task dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (taskMenuRef.current && !taskMenuRef.current.contains(e.target)) {
        setShowTaskMenu(false);
        setEditingTaskId(null);
      }
    };
    if (showTaskMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTaskMenu]);

  // Auto-scroll on message updates (if autoScroll enabled)
  useEffect(() => {
    if (autoScroll) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming, autoScroll]);

  // Task Management Handlers
  const handleCreateNewTask = () => {
    const newTask = createNewTask(`Task #${tasks.length + 1}`);
    setTasks(prev => [newTask, ...prev]);
    setActiveTaskId(newTask.id);
    setShowTaskMenu(false);
  };

  const handleSelectTask = (taskId) => {
    setActiveTaskId(taskId);
    setShowTaskMenu(false);
  };

  const handleDeleteTask = (taskId, e) => {
    e?.stopPropagation();
    if (tasks.length <= 1) {
      // If deleting the last task, replace with a fresh one
      const freshTask = createNewTask('Task #1');
      setTasks([freshTask]);
      setActiveTaskId(freshTask.id);
      return;
    }
    const remaining = tasks.filter(t => t.id !== taskId);
    setTasks(remaining);
    if (activeTaskId === taskId) {
      setActiveTaskId(remaining[0].id);
    }
  };

  const handleStartRename = (task, e) => {
    e?.stopPropagation();
    setEditingTaskId(task.id);
    setEditTitleInput(task.title);
  };

  const handleSaveRename = (taskId, e) => {
    e?.stopPropagation();
    if (!editTitleInput.trim()) {
      setEditingTaskId(null);
      return;
    }
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, title: editTitleInput.trim(), updatedAt: new Date().toISOString() } : t));
    setEditingTaskId(null);
  };

  const handleModelChange = (newModel) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, model: newModel, updatedAt: new Date().toISOString() } : t));
  };

  const handleToggleAutoExecute = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, autoExecuteTools: val, updatedAt: new Date().toISOString() } : t));
  };

  const toggleThought = (idx) => {
    setExpandedThoughts(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Filtered Tasks for Dropdown
  const filteredTasks = useMemo(() => {
    if (!taskSearchQuery.trim()) return tasks;
    return tasks.filter(t => t.title.toLowerCase().includes(taskSearchQuery.toLowerCase()));
  }, [tasks, taskSearchQuery]);

  // Send Message & Stream Response with clean turn-based step splitting
  const handleSendMessage = async (textToSend) => {
    const userPrompt = textToSend || input.trim();
    if (!userPrompt || isStreaming) return;

    // Auto-update task title from first user prompt if still generic
    const isGenericTitle = activeTask.title.startsWith('Nuovo Task') || activeTask.title.startsWith('Task #');
    const newTitle = isGenericTitle ? (userPrompt.slice(0, 36) + (userPrompt.length > 36 ? '...' : '')) : activeTask.title;

    const newMessages = [...messages, { role: 'user', content: userPrompt }];
    let activeMsgIndex = newMessages.length;

    // Append user message + first assistant turn placeholder
    const currentTaskId = activeTask.id;
    setTasks(prev => prev.map(t => {
      if (t.id === currentTaskId) {
        return {
          ...t,
          title: newTitle,
          updatedAt: new Date().toISOString(),
          messages: [
            ...newMessages,
            { role: 'assistant', content: '', thought: '', tools: [], isStreaming: true }
          ]
        };
      }
      return t;
    }));

    setInput('');
    setIsStreaming(true);

    try {
      const response = await fetch('/api/developer/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: newMessages.map(m => ({ role: m.role, content: m.content })),
          workspace_root: workspaceRoot,
          model: selectedModel,
          auto_execute_tools: autoExecuteTools
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.replace(/^data: /, '').trim();
          if (!dataStr) continue;

          try {
            const event = JSON.parse(dataStr);

            // If a subsequent turn starts (e.g. after tool execution), seal previous message and start fresh step!
            if (event.type === 'turn_start' && event.turn > 1) {
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const msgs = [...t.messages];
                  if (msgs[activeMsgIndex]) {
                    msgs[activeMsgIndex].isStreaming = false;
                  }
                  msgs.push({
                    role: 'assistant',
                    content: '',
                    thought: '',
                    tools: [],
                    isStreaming: true
                  });
                  activeMsgIndex = msgs.length - 1;
                  return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            if (event.type === 'turn_end') {
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const msgs = [...t.messages];
                  if (msgs[activeMsgIndex]) {
                    msgs[activeMsgIndex].isStreaming = false;
                  }
                  return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            setTasks(prev => prev.map(t => {
              if (t.id === currentTaskId) {
                const msgs = [...t.messages];
                const cur = { ...msgs[activeMsgIndex] };

                if (event.type === 'token') {
                  cur.content = (cur.content || '') + event.token;
                } else if (event.type === 'thought') {
                  cur.thought = (cur.thought || '') + event.token;
                } else if (event.type === 'metrics') {
                  cur.metrics = {
                    tps: event.tps,
                    ttft_ms: event.ttft_ms,
                    tokens: event.tokens,
                    total_tokens: event.total_tokens,
                    duration_s: event.duration_s
                  };
                } else if (event.type === 'tool_start') {
                  cur.tools = [...(cur.tools || []), { tool: event.tool, params: event.params, status: 'running' }];
                } else if (event.type === 'tool_result') {
                  cur.tools = (cur.tools || []).map(toolItem => 
                    toolItem.tool === event.tool ? { ...toolItem, result: event.result, status: 'done' } : toolItem
                  );
                  // Trigger tree refresh when tools complete
                  onRefreshTree?.();

                  // If diff generated, notify parent
                  if (event.result?.diff && onApplyDiff) {
                    onApplyDiff(event.result.diff, event.result.path, event.result.content);
                  }
                }

                msgs[activeMsgIndex] = cur;
                return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
              }
              return t;
            }));
          } catch (e) {
            console.error('Error parsing SSE event', e);
          }
        }
      }
    } catch (err) {
      setTasks(prev => prev.map(t => {
        if (t.id === currentTaskId) {
          const msgs = [...t.messages];
          msgs[activeMsgIndex] = {
            role: 'assistant',
            content: `❌ Errore durante l'elaborazione: ${err.message}`,
            tools: []
          };
          return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
        }
        return t;
      }));
    } finally {
      setIsStreaming(false);
      onRefreshTree?.();
      setTasks(prev => prev.map(t => {
        if (t.id === currentTaskId) {
          const msgs = [...t.messages];
          if (msgs[activeMsgIndex]) {
            msgs[activeMsgIndex].isStreaming = false;
          }
          return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
        }
        return t;
      }));
    }
  };

  const quickPrompts = [
    { label: '🔍 Analizza file attivo', prompt: `Analizza e descrivi l'architettura del file attivo (${activeFilePath || 'nessun file selezionato'}).` },
    { label: '🧪 Esegui test', prompt: 'Esegui i test unitari e verifica se ci sono errori da correggere.' },
    { label: '🧹 Pulisci cartella', prompt: 'Verifica la cartella data/ e rimuovi le cartelle temporanee o di prova.' }
  ];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      minWidth: 0,
      flex: 1,
      background: isLight ? '#f6f8fa' : '#0d1117',
      overflow: 'hidden'
    }}>
      {/* Agent Chat Header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        background: isLight ? '#ffffff' : '#0a0e14',
        position: 'relative'
      }}>
        {/* Row 1: Agent Badge + Auto-Exec + New Task */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '24px',
              height: '24px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Bot size={14} color="#000" />
            </div>
            <div>
              <div style={{ fontSize: '0.76rem', fontWeight: 800, color: isLight ? '#24292f' : '#f0f6fc' }}>
                ADMIN AI DEVELOPER
              </div>
              <div style={{ fontSize: '0.62rem', color: '#3fb950', fontWeight: 700 }}>
                ● Full Workspace Access
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{
              fontSize: '0.64rem',
              fontWeight: 700,
              color: autoScroll ? '#00f2fe' : '#8b949e',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={e => setAutoScroll(e.target.checked)}
                style={{ accentColor: '#00f2fe' }}
              />
              Auto-Scroll
            </label>

            <label style={{
              fontSize: '0.64rem',
              fontWeight: 700,
              color: autoExecuteTools ? '#3fb950' : '#8b949e',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <input
                type="checkbox"
                checked={autoExecuteTools}
                onChange={e => handleToggleAutoExecute(e.target.checked)}
                style={{ accentColor: '#3fb950' }}
              />
              Auto-Exec
            </label>

            {/* "+ Nuovo Task" Button */}
            <button
              type="button"
              onClick={handleCreateNewTask}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                borderRadius: '6px',
                background: 'rgba(0, 242, 254, 0.12)',
                border: '1px solid rgba(0, 242, 254, 0.35)',
                color: '#00f2fe',
                fontSize: '0.66rem',
                fontWeight: 800,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              title="Crea una nuova sessione di lavoro"
            >
              <Plus size={12} />
              <span>Nuovo Task</span>
            </button>
          </div>
        </div>

        {/* Row 2: Task Switcher & History Bar */}
        <div style={{ position: 'relative' }} ref={taskMenuRef}>
          <div
            onClick={() => setShowTaskMenu(!showTaskMenu)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '5px 10px',
              borderRadius: '6px',
              background: isLight ? '#f6f8fa' : '#161b22',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
              cursor: 'pointer',
              fontSize: '0.70rem',
              color: isLight ? '#24292f' : '#f0f6fc'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
              <MessageSquare size={12} color="#00f2fe" style={{ flexShrink: 0 }} />
              <span style={{ fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeTask.title}
              </span>
              <span style={{ fontSize: '0.62rem', color: '#8b949e', flexShrink: 0 }}>
                • {messages.length} msg
              </span>
            </div>
            <ChevronDown size={12} color="#8b949e" style={{ transform: showTaskMenu ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
          </div>

          {/* Task Dropdown Menu / History List */}
          {showTaskMenu && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              zIndex: 100,
              background: isLight ? '#ffffff' : '#0d1117',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.15)',
              borderRadius: '8px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              maxHeight: '280px',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden'
            }}>
              {/* Task Search Bar */}
              <div style={{
                padding: '6px 8px',
                borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Search size={12} color="#8b949e" />
                <input
                  type="text"
                  placeholder="Cerca nei task salvati..."
                  value={taskSearchQuery}
                  onChange={e => setTaskSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    fontSize: '0.68rem',
                    color: isLight ? '#24292f' : '#f0f6fc'
                  }}
                  autoFocus
                />
              </div>

              {/* Task List */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '4px' }}>
                {filteredTasks.map(t => {
                  const isActive = t.id === activeTask.id;
                  const isEditing = editingTaskId === t.id;

                  return (
                    <div
                      key={t.id}
                      onClick={() => !isEditing && handleSelectTask(t.id)}
                      style={{
                        padding: '6px 8px',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        background: isActive ? 'rgba(0, 242, 254, 0.12)' : 'transparent',
                        cursor: 'pointer',
                        marginBottom: '2px',
                        fontSize: '0.68rem',
                        transition: 'background 0.1s'
                      }}
                      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = isLight ? '#f6f8fa' : 'rgba(255,255,255,0.05)'; }}
                      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                    >
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }} onClick={e => e.stopPropagation()}>
                          <input
                            type="text"
                            value={editTitleInput}
                            onChange={e => setEditTitleInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSaveRename(t.id, e)}
                            style={{
                              flex: 1,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              border: '1px solid #00f2fe',
                              background: isLight ? '#fff' : '#161b22',
                              color: isLight ? '#000' : '#fff',
                              fontSize: '0.68rem',
                              outline: 'none'
                            }}
                            autoFocus
                          />
                          <button
                            type="button"
                            onClick={(e) => handleSaveRename(t.id, e)}
                            style={{ background: 'none', border: 'none', color: '#3fb950', cursor: 'pointer' }}
                          >
                            <Check size={12} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, paddingRight: '8px' }}>
                          <div style={{
                            fontWeight: isActive ? 800 : 500,
                            color: isActive ? '#00f2fe' : (isLight ? '#24292f' : '#f0f6fc'),
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {t.title}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.60rem', color: '#8b949e', marginTop: '1px' }}>
                            <span>{t.messages.length} msg</span>
                            <span>• {formatTimeAgo(t.updatedAt)}</span>
                          </div>
                        </div>
                      )}

                      {!isEditing && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <button
                            type="button"
                            onClick={(e) => handleStartRename(t, e)}
                            style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '2px' }}
                            title="Rinomina Task"
                          >
                            <Edit2 size={11} />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteTask(t.id, e)}
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
                            title="Elimina Task"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Row 3: Model Selector with Specs & Weights */}
        <DeveloperModelSelector
          selectedModel={selectedModel}
          onSelectModel={handleModelChange}
          theme={theme}
          isLight={isLight}
        />
      </div>

      {/* Messages List */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        {messages.map((msg, idx) => (
          <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.68rem',
              fontWeight: 700,
              color: msg.role === 'user' ? '#00f2fe' : (isLight ? '#57606a' : '#8b949e')
            }}>
              {msg.role === 'user' ? <User size={12} /> : <Bot size={12} />}
              <span>{msg.role === 'user' ? 'Tu' : 'Admin AI Agent'}</span>
            </div>

            {/* Collapsible Thinking Bubble */}
            {msg.thought && (
              <div style={{
                borderRadius: '8px',
                background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)',
                overflow: 'hidden'
              }}>
                <div
                  onClick={() => toggleThought(idx)}
                  style={{
                    padding: '4px 8px',
                    fontSize: '0.66rem',
                    fontWeight: 700,
                    color: '#8b949e',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    userSelect: 'none'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Brain size={12} color="#00f2fe" />
                    <span>Catena di Ragionamento ({msg.thought.length} caratteri)</span>
                  </div>
                  {expandedThoughts[idx] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </div>

                {expandedThoughts[idx] && (
                  <div style={{
                    padding: '6px 10px',
                    fontSize: '0.7rem',
                    fontFamily: 'Consolas, monospace',
                    color: isLight ? '#57606a' : '#8b949e',
                    borderTop: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.4
                  }}>
                    {msg.thought}
                  </div>
                )}
              </div>
            )}

            {/* Message Bubble Content */}
            {(() => {
              const contentText = msg.role === 'user' ? msg.content : cleanMessageText(msg.content);
              if (!contentText) return null;
              return (
                <div style={{
                  padding: '8px 12px',
                  borderRadius: '10px',
                  fontSize: '0.76rem',
                  lineHeight: 1.45,
                  background: msg.role === 'user'
                    ? (isLight ? 'rgba(0, 242, 254, 0.12)' : 'rgba(0, 242, 254, 0.1)')
                    : (isLight ? '#ffffff' : '#161b22'),
                  border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
                  color: isLight ? '#24292f' : '#e6edf3',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {contentText}
                </div>
              );
            })()}

            {/* Generation Metrics Bar (t/s, TTFT, Tokens, Duration) */}
            {msg.metrics && msg.role === 'assistant' && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.62rem',
                padding: '2px 4px',
                color: isLight ? '#57606a' : '#8b949e',
                flexWrap: 'wrap'
              }}>
                {msg.metrics.tps > 0 && (
                  <span style={{ color: '#3fb950', fontWeight: 800 }}>
                    ⚡ {msg.metrics.tps} t/s
                  </span>
                )}
                {msg.metrics.ttft_ms > 0 && (
                  <span>⏱️ TTFT {msg.metrics.ttft_ms}ms</span>
                )}
                {msg.metrics.tokens > 0 && (
                  <span>• {msg.metrics.tokens} tokens</span>
                )}
                {msg.metrics.duration_s > 0 && (
                  <span>• {msg.metrics.duration_s}s</span>
                )}
              </div>
            )}

            {/* Tool Execution Badges & Sealed Action Alert Cards */}
            {msg.tools && msg.tools.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                {msg.tools.map((t, tIdx) => {
                  const isDone = t.status === 'done';
                  const isSuccess = t.result ? t.result.success !== false : true;
                  const hasDiff = !!t.result?.diff;

                  return (
                    <div
                      key={tIdx}
                      style={{
                        borderRadius: '10px',
                        background: isLight ? '#ffffff' : '#0a0e14',
                        border: isLight 
                          ? (isDone ? '1px solid #d0d7de' : '1px solid rgba(0, 242, 254, 0.4)')
                          : (isDone ? (isSuccess ? '1px solid rgba(63, 185, 80, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)') : '1px solid rgba(0, 242, 254, 0.4)'),
                        overflow: 'hidden',
                        boxShadow: isLight ? '0 1px 4px rgba(0,0,0,0.06)' : '0 2px 8px rgba(0,0,0,0.3)',
                        fontSize: '0.7rem'
                      }}
                    >
                      {/* Action Header Alert Banner */}
                      <div style={{
                        padding: '6px 10px',
                        background: isDone 
                          ? (isSuccess 
                              ? (isLight ? 'rgba(63, 185, 80, 0.1)' : 'rgba(63, 185, 80, 0.08)')
                              : (isLight ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.08)'))
                          : (isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)'),
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderBottom: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)'
                      }}>
                        <span style={{ 
                          fontWeight: 800, 
                          color: isDone ? (isSuccess ? '#3fb950' : '#ef4444') : '#00f2fe', 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '6px' 
                        }}>
                          {t.tool === 'terminal' && <Terminal size={13} />}
                          {t.tool === 'read_file' && <FileCode size={13} />}
                          {t.tool === 'write_file' && <SplitSquareVertical size={13} />}
                          {t.tool === 'delete' && <Trash2 size={13} />}
                          {t.tool === 'list_dir' && <Layers size={13} />}
                          <span>
                            {t.tool === 'write_file' ? 'MODIFICA / SCRITTURA FILE' :
                             t.tool === 'terminal' ? 'ESECUZIONE TERMINALE' :
                             t.tool === 'delete' ? 'ELIMINAZIONE FILE / CARTELLA' :
                             t.tool === 'read_file' ? 'LETTURA FILE' :
                             t.tool === 'list_dir' ? 'ESPLORAZIONE DIRECTORY' : `AZIONE: ${t.tool.toUpperCase()}`}
                          </span>
                        </span>

                        <span style={{
                          fontSize: '0.62rem',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          background: isDone 
                            ? (isSuccess ? 'rgba(63, 185, 80, 0.2)' : 'rgba(239, 68, 68, 0.2)')
                            : 'rgba(0, 242, 254, 0.2)',
                          color: isDone ? (isSuccess ? '#3fb950' : '#ef4444') : '#00f2fe',
                          fontWeight: 800,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}>
                          {isDone ? (isSuccess ? '✓ Completato' : '✕ Errore') : '⏳ In esecuzione...'}
                        </span>
                      </div>

                      {/* Action Details Body */}
                      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {t.params?.command && (
                          <div style={{
                            fontFamily: '"JetBrains Mono", Consolas, monospace',
                            color: '#3fb950',
                            fontSize: '0.68rem',
                            background: isLight ? '#f6f8fa' : '#161b22',
                            padding: '4px 8px',
                            borderRadius: '5px',
                            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
                          }}>
                            $ {t.params.command}
                          </div>
                        )}

                        {t.params?.path && (
                          <div style={{ fontFamily: 'monospace', color: isLight ? '#57606a' : '#8b949e', fontSize: '0.66rem' }}>
                            📂 Percorso: <strong>{t.params.path}</strong>
                          </div>
                        )}

                        {t.result?.message && (
                          <div style={{ 
                            color: t.result.success !== false ? (isLight ? '#24292f' : '#e6edf3') : '#ef4444', 
                            fontSize: '0.68rem', 
                            lineHeight: 1.4,
                            marginTop: '2px', 
                            fontWeight: 500 
                          }}>
                            {t.result.message}
                          </div>
                        )}

                        {/* Diff Preview & Apply button */}
                        {hasDiff && (
                          <div style={{ marginTop: '6px', borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                              <span style={{ fontSize: '0.64rem', fontWeight: 700, color: '#00f2fe' }}>
                                ⚡ Modifiche Proposte nel File
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  onApplyDiff?.(t.result.diff, t.result.path, t.result.content);
                                }}
                                style={{
                                  padding: '3px 10px',
                                  borderRadius: '5px',
                                  background: '#3fb950',
                                  border: 'none',
                                  color: '#fff',
                                  fontSize: '0.64rem',
                                  fontWeight: 800,
                                  cursor: 'pointer'
                                }}
                              >
                                Visualizza / Applica Diff
                              </button>
                            </div>
                            <pre style={{
                              margin: 0,
                              padding: '6px 8px',
                              maxHeight: '120px',
                              overflowY: 'auto',
                              background: '#07090e',
                              borderRadius: '4px',
                              fontSize: '0.64rem',
                              fontFamily: 'Consolas, monospace',
                              lineHeight: 1.35
                            }}>
                              {t.result.diff.split('\n').slice(0, 15).map((line, dIdx) => (
                                <div key={dIdx} style={{
                                  color: line.startsWith('+') ? '#3fb950' : (line.startsWith('-') ? '#ef4444' : '#8b949e')
                                }}>
                                  {line}
                                </div>
                              ))}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Turn Completion Seal */}
            {!msg.isStreaming && msg.role === 'assistant' && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '3px 6px',
                fontSize: '0.60rem',
                color: isLight ? '#57606a' : '#8b949e',
                borderBottom: isLight ? '1px solid rgba(0,0,0,0.05)' : '1px solid rgba(255,255,255,0.04)',
                marginBottom: '4px'
              }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#3fb950', fontWeight: 700 }}>
                  ✓ Risposta completata
                </span>
                <span>
                  {msg.metrics?.duration_s ? `${msg.metrics.duration_s}s` : ''}
                </span>
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Quick Prompts */}
      <div style={{
        padding: '6px 10px',
        display: 'flex',
        gap: '4px',
        overflowX: 'auto',
        borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
      }}>
        {quickPrompts.map(qp => (
          <button
            key={qp.label}
            onClick={() => handleSendMessage(qp.prompt)}
            disabled={isStreaming}
            style={{
              padding: '2px 6px',
              borderRadius: '6px',
              fontSize: '0.62rem',
              fontWeight: 600,
              background: isLight ? '#ffffff' : '#161b22',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
              color: isLight ? '#24292f' : '#c9d1d9',
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <form 
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        style={{
          padding: '8px 10px',
          borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          gap: '6px',
          background: isLight ? '#f6f8fa' : '#0a0e14'
        }}
      >
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={isStreaming ? "L'agente sta elaborando..." : "Chiedi all'AI Developer Agent..."}
          disabled={isStreaming}
          style={{
            flex: 1,
            padding: '6px 10px',
            borderRadius: '8px',
            fontSize: '0.74rem',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
            color: isLight ? '#24292f' : '#f0f6fc',
            outline: 'none'
          }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{
            padding: '6px 12px',
            borderRadius: '8px',
            background: input.trim() && !isStreaming ? 'linear-gradient(135deg, #00f2fe, #4facfe)' : (isLight ? '#e1e4e8' : '#21262d'),
            border: 'none',
            color: input.trim() && !isStreaming ? '#000000' : '#8b949e',
            cursor: input.trim() && !isStreaming ? 'pointer' : 'default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          {isStreaming ? <RefreshCw size={13} className="spin" /> : <Send size={13} />}
        </button>
      </form>
    </div>
  );
}
