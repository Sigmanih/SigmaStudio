import { useState, useCallback, useRef, useEffect } from 'react';
import { MAX_ATTACHMENTS, createSession, MAX_HISTORY } from '../chatStorage';
import { getModelRoutingInfo } from '../modelProviderMap';

let globalAbortController = null;

function appendAndSave(sid, msg, setFn) {
  setFn(prev => {
    const updated = [...(prev[sid] || []), msg];
    try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(updated)); } catch (e) {}
    return { ...prev, [sid]: updated };
  });
}

function cleanModelTags(text) {
  if (!text) return text;
  let cleaned = text.replace(/<(thinking|Thought|reasoning|Rationale|scratchpad)>[\s\S]*?<\/\1>/gi, '');
  cleaned = cleaned.replace(/<\/?(response|Response|output|Output|answer|Answer|result|Result|tool_call|ToolCall|function_call|FunctionCall)>/gi, '');
  cleaned = cleaned.replace(/<\/?[a-zA-Z_][a-zA-Z0-9_]*>/g, '');
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  return cleaned.trim();
}

export function useChatStreaming({
  // From extraProps
  openFiles: externalOpenFiles,
  onTasksUpdated,
  addToast,

  // From useChatSessions
  sessions,
  activeSessionId,
  setActiveSessionId,
  sessionMessages,
  setSessionMessages,
  saveSessionsState,
  setMessagesForSession,
  saveMessagesImmediately,
  loadMessagesFromStorage,
  welcomeMsg,
  sessionRefs,

  // From useChatConfig
  selectedModel,
  providerConfigs,
  quickConfig,
  selectedManifestoPath,
  fetchOllamaModels,
  refreshConfig,
  activeManifesto,
}) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeMode, setActiveMode] = useState('execute');
  const [actionsLog, setActionsLog] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [pcFiles, setPcFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [webSearch, setWebSearch] = useState(false);

  // Loop/execute settings
  const [loopMaxIterations, setLoopMaxIterations] = useState(25);
  const [loopIteration, setLoopIteration] = useState(0);
  const [loopActive, setLoopActive] = useState(false);
  const [actionStrategy, setActionStrategy] = useState('bilanciata');
  const [actionMaxReadIterations, setActionMaxReadIterations] = useState('2');
  const [actionMaxTotalReads, setActionMaxTotalReads] = useState('5');
  const [autoApprove, setAutoApprove] = useState(false);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [planExecuting, setPlanExecuting] = useState(false);
  const [showHistory, setShowHistory] = useState(true);

  // Additional UI states
  const [showFilePicker, setShowFilePicker] = useState(false);

  // Refs
  const abortRef = useRef(null);
  const streamingSessionIdRef = useRef(null);
  const loopActiveRef = useRef(loopActive);
  const loopIterationRef = useRef(loopIteration);
  const loopMaxIterationsRef = useRef(loopMaxIterations);
  const messagesEndRef = useRef(null);

  // Scroll to bottom on message changes if auto-scroll is enabled
  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [sessionMessages, activeSessionId, loading, autoScroll]);

  useEffect(() => { loopActiveRef.current = loopActive; }, [loopActive]);
  useEffect(() => { loopIterationRef.current = loopIteration; }, [loopIteration]);
  useEffect(() => { loopMaxIterationsRef.current = loopMaxIterations; }, [loopMaxIterations]);

  // --- Stop ---
  const stopInference = useCallback(() => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    if (globalAbortController) { globalAbortController.abort(); globalAbortController = null; }
    setLoopActive(false);
    setLoading(false);
    streamingSessionIdRef.current = null;
    sessionStorage.removeItem('sigma_pending_chat');
  }, []);

  // --- Streaming responses ---
  const handleStreamResponse = async (res, sessionId) => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '', fullThinking = '', buffer = '';
    let firstToken = true, hasThinking = false;
    const modelName = selectedModel;
    try {
      let streamDone = false, hasError = false, streamErrorMsg = '';
      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') { streamDone = true; break; }
            if (payload === '[ERROR]') { hasError = true; streamDone = true; break; }
            try {
              const p = JSON.parse(payload);
              if (p.thinking) { hasThinking = true; fullThinking += p.thinking; }
              if (p.token) { fullText += p.token; }
              if (firstToken) {
                firstToken = false;
                setSessionMessages(prev => ({ ...prev, [sessionId]: [...(prev[sessionId] || []), { role: 'assistant', content: fullText, agentName: modelName, timestamp: new Date().toISOString(), streaming: true, thinking: hasThinking ? fullThinking : undefined, streamingThinking: hasThinking, agentImage: activeManifesto?.image || '/images/default.png', agentRole: activeManifesto?.name || '' }] }));
              } else {
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') n[n.length - 1] = { ...n[n.length - 1], content: fullText, thinking: hasThinking ? fullThinking : n[n.length - 1].thinking, streamingThinking: hasThinking };
                  return { ...prev, [sessionId]: n };
                });
              }
            } catch (e) {}
          }
          if (streamDone) break;
        }
      }
      setLoading(false);
      const finalContent = cleanModelTags(fullText) || (fullThinking ? cleanModelTags(fullThinking) : (hasError ? streamErrorMsg || '⚠️ Error' : '⚠️ Nessuna risposta.'));
      setSessionMessages(prev => {
        const n = [...(prev[sessionId] || [])];
        if (n.length > 0 && n[n.length - 1].role === 'assistant') n[n.length - 1] = { ...n[n.length - 1], content: finalContent, streaming: false, streamingThinking: false };
        return { ...prev, [sessionId]: n };
      });
      saveMessagesImmediately(sessionId, sessionRefs.sessionMessages.current[sessionId] || []);
    } catch (e) {
      setLoading(false);
      setSessionMessages(prev => [...(prev[sessionId] || []), { role: 'assistant', content: `⚠️ **Errore:** ${e.message}`, timestamp: new Date().toISOString(), error: true, agentImage: activeManifesto?.image || '/images/default.png', agentRole: activeManifesto?.name || '' }]);
    }
  };

  const handleJsonResponse = async (res, sessionId, updatedMessages) => {
    try {
      const data = await res.json();
      const assistant = { role: 'assistant', content: data.response || '⚠️ Nessuna risposta.', thinking: data.thinking || null, timestamp: new Date().toISOString(), error: data.error || null, agentName: selectedModel, agentImage: activeManifesto?.image || '/images/default.png', agentRole: activeManifesto?.name || '' };
      if (sessionRefs.activeSessionId.current === sessionId) {
        const finalMessages = [...updatedMessages, assistant];
        setMessagesForSession(sessionId, finalMessages);
        saveMessagesImmediately(sessionId, finalMessages);
        if (data.actions_log?.length > 0) {
          setActionsLog(data.actions_log);
          const withActions = [...finalMessages, { 
            role: 'system', 
            content: `⚡ **Azioni eseguite:**`, 
            timestamp: new Date().toISOString(), 
            isAction: true,
            actions_log: data.actions_log
          }];
          setMessagesForSession(sessionId, withActions);
          saveMessagesImmediately(sessionId, withActions);
          if (onTasksUpdated) onTasksUpdated();
        }
      } else {
        const prevForSession = sessionRefs.sessionMessages.current[sessionId] || [];
        const finalMessages = [...prevForSession, ...updatedMessages.slice(prevForSession.length), assistant];
        setSessionMessages(prev => ({ ...prev, [sessionId]: finalMessages }));
        saveMessagesImmediately(sessionId, finalMessages);
      }
    } catch (e) {
      if (sessionRefs.activeSessionId.current === sessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore nella risposta del server:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...updatedMessages, errorMsg];
        setMessagesForSession(sessionId, finalMsgs);
        saveMessagesImmediately(sessionId, finalMsgs);
      }
    }
  };

  const handleExecuteStream = useCallback(async (res, sessionId) => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    const streamRunId = Math.random().toString(36).substring(7);
    let buffer = '', done = false;
    try {
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
            let event;
            try { event = JSON.parse(payload); } catch (e) { continue; }
            const sid = sessionRefs.activeSessionId.current || sessionId;
            let msgContent = '', toastType = 'info', toastDuration = 3000;

            if (event.type === 'execute_start') {
              msgContent = '';
              setLoopIteration(0);
            } else if (event.type === 'iteration_start') {
              msgContent = '';
              setLoopIteration(event.iteration);
            } else if (event.type === 'iteration_actions') {
              msgContent = '';
            } else if (event.type === 'iteration_complete') {
              if (event.actions_log && event.actions_log.length > 0) {
                msgContent = `⚡ **Azioni eseguite (Iterazione ${event.iteration}):**`;
                if (event.actions_log) setActionsLog(event.actions_log);
              } else {
                msgContent = '';
              }
              if (onTasksUpdated) onTasksUpdated();
              toastType = 'success'; toastDuration = 3000;
            } else if (event.type === 'execute_done') {
              msgContent = '';
              if (onTasksUpdated) onTasksUpdated();
              toastType = 'success'; toastDuration = 5000;
            } else if (event.type === 'execute_timeout') {
              msgContent = `⏱️ **Limite iterazioni raggiunto:** ${event.max_iterations}`;
              toastType = 'warning'; toastDuration = 5000;
            } else if (event.type === 'iteration_plan') {
              msgContent = '';
            } else if (event.type === 'iteration_response') {
              if (event.response && sid) {
                const iterId = `iter-response-${streamRunId}-${event.iteration || 1}`;
                const newMsg = {
                  id: iterId,
                  role: 'assistant',
                  content: event.response,
                  timestamp: new Date().toISOString(),
                  agentName: event.agent_name || selectedModel,
                  agentId: event.agent_id || undefined,
                  agentRole: event.agent_name || undefined,
                  thinking: event.thinking || undefined,
                };
                setSessionMessages(prev => {
                  const currentMsgs = prev[sid] || [];
                  const existingIdx = currentMsgs.findIndex(m => m.id === iterId);
                  let updated;
                  if (existingIdx !== -1) {
                    updated = [...currentMsgs];
                    // Mantieni il timestamp originale per non alterare l'ordinamento visivo della chat
                    updated[existingIdx] = {
                      ...updated[existingIdx],
                      content: newMsg.content,
                      thinking: newMsg.thinking || updated[existingIdx].thinking
                    };
                  } else {
                    updated = [...currentMsgs, newMsg];
                  }
                  try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(updated)); } catch (e) {}
                  return { ...prev, [sid]: updated };
                });
              }
              continue;
            } else if (event.type === 'error') {
              msgContent = `❌ ${event.message || event.error || 'Errore'}`;
              toastType = 'error'; toastDuration = 8000;
            } else if (event.type === 'done') {
              msgContent = '';
              if (onTasksUpdated) onTasksUpdated();
              toastType = 'success'; toastDuration = 8000;
            } else if (event.type === 'iteration_validation_error') {
              const invalidTypes = (event.invalid_types || []).join(', ');
              const actionsRaw = event.actions_raw || [];
              let actionsDetail = '';
              if (actionsRaw.length > 0) {
                actionsDetail = '\n\n' + actionsRaw.map((a, i) => {
                  const typeVal = a.type || 'MISSING (nessun campo "type")';
                  const pathVal = a.path ? ` path="${a.path}"` : '';
                  const titoloVal = a.titolo ? ` titolo="${a.titolo}"` : '';
                  return `  ${i+1}. type="${typeVal}"${pathVal}${titoloVal}`;
                }).join('\n');
              }
              msgContent = `⚠️ **Azioni non valide (Iterazione ${event.iteration})**\n\nTipi sconosciuti: ${invalidTypes || 'MISSING'}${actionsDetail}\n\n✅ I tipi validi sono: create_file, edit_file, read_file, rename_file, delete_file, create_module, run_test, update_task, send_notification\n\n📝 **Nota:** Ogni azione DEVE avere un campo "type".`;
              toastType = 'warning'; toastDuration = 8000;
            }

            if (msgContent && sid) {
              const newMsg = { 
                role: 'system', 
                content: msgContent, 
                timestamp: new Date().toISOString(), 
                isAction: true,
                actions_log: event.actions_log || undefined,
                agentId: event.agent_id || undefined,
                agentRole: event.agent_name || undefined
              };
              appendAndSave(sid, newMsg, setSessionMessages);
            }
            if (addToast && msgContent) addToast(msgContent.replace(/\*\*/g, '').split('\n')[0], toastType, toastDuration);
          }
          if (done) break;
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError' && sessionRefs.activeSessionId.current) {
        const errMsg = { role: 'system', content: `❌ **Errore execute:** ${e.message}`, timestamp: new Date().toISOString(), isAction: true, error: true };
        appendAndSave(sessionRefs.activeSessionId.current, errMsg, setSessionMessages);
      }
    }
  }, [selectedModel, addToast, onTasksUpdated, setSessionMessages, sessionRefs]);

  // --- Send Message ---
  const sendMessage = useCallback(async () => {
    if (!input.trim() || loading) return;
    if (refreshConfig) await refreshConfig();
    let currentSessionId = sessionRefs.activeSessionId.current;
    let currentSessions = sessionRefs.sessions.current;
    if (!currentSessionId) {
      const session = createSession(selectedModel);
      currentSessions = [session, ...currentSessions].slice(0, MAX_HISTORY);
      saveSessionsState(currentSessions);
      currentSessionId = session.id;
      setActiveSessionId(currentSessionId);
    }
    streamingSessionIdRef.current = currentSessionId;
    const openFiles = externalOpenFiles || [];
    const contextFiles = [...(openFiles || []), ...attachedFiles].slice(0, MAX_ATTACHMENTS);
    const userMsg = { role: 'user', content: input.trim(), timestamp: new Date().toISOString(), attachments: attachedFiles.length > 0 ? [...attachedFiles] : undefined, agentName: selectedModel };
    const currentMsgs = sessionRefs.sessionMessages.current[currentSessionId] || [];
    const updatedMessages = [...currentMsgs, userMsg];
    setMessagesForSession(currentSessionId, updatedMessages);
    saveMessagesImmediately(currentSessionId, updatedMessages);
    const sessionName = sessionRefs.sessions.current.find(s => s.id === currentSessionId)?.name;
    if (sessionName && sessionName.startsWith('Chat ')) {
      const firstWords = input.trim().slice(0, 50).replace(/\n/g, ' ');
      const newName = `${firstWords}... (${selectedModel.split(':')[0]})`;
      saveSessionsState(sessionRefs.sessions.current.map(s => s.id === currentSessionId ? { ...s, name: newName } : s));
    }
    setInput('');
    setLoading(true);
    setActionsLog([]);
    const controller = new AbortController();
    abortRef.current = controller;
    globalAbortController = controller;

    try {
      const routing = getModelRoutingInfo(selectedModel, providerConfigs);
      const isPlan = activeMode === 'plan';
      const isExecute = activeMode === 'execute';
      const isComplete = activeMode === 'complete';

      if (isExecute || isComplete) {
        const body = {
          message: input.trim(), bot_name: selectedModel, model: selectedModel,
          model_provider: routing.provider, model_endpoint: routing.endpoint, model_api_url: routing.api_url,
          allow_actions: true, stream: true, timeout: quickConfig.timeout || 300,
          max_iterations: loopMaxIterations,
          web_search: webSearch,
          context: { open_files: contextFiles, history: updatedMessages.slice(-10).map(m => ({ role: m.role, content: m.content })) },
          uploaded_files: pcFiles.length > 0 ? pcFiles : undefined
        };
        if (selectedManifestoPath) body.manifesto_path = selectedManifestoPath;
        const res = await fetch('/api/chat/execute', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal
        });
        if (res.ok) await handleExecuteStream(res, currentSessionId);
        else {
          const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
          const errMsg = { role: 'assistant', content: `❌ **Errore execute:** ${err.error || res.statusText}`, timestamp: new Date().toISOString(), error: true };
          setMessagesForSession(currentSessionId, prev => [...prev, errMsg]);
          saveMessagesImmediately(currentSessionId, [...(sessionRefs.sessionMessages.current[currentSessionId] || []), errMsg]);
        }
      } else {
        const useStream = !isPlan && routing.provider !== 'anthropic';
        const body = {
          message: input.trim(), bot_name: selectedModel, model: selectedModel,
          model_provider: routing.provider, model_endpoint: routing.endpoint, model_api_url: routing.api_url,
          allow_actions: false, planning_mode: isPlan, stream: useStream,
          timeout: quickConfig.timeout || 300, web_search: webSearch,
          context: { open_files: contextFiles, history: updatedMessages.slice(-10).map(m => ({ role: m.role, content: m.content })) },
          uploaded_files: pcFiles.length > 0 ? pcFiles : undefined
        };
        if (selectedManifestoPath) body.manifesto_path = selectedManifestoPath;
        const res = await fetch('/api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal
        });
        if (useStream && res.ok) {
          await handleStreamResponse(res, currentSessionId);
        } else {
          await handleJsonResponse(res, currentSessionId, updatedMessages);
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') { sessionStorage.removeItem('sigma_pending_chat'); return; }
      if (sessionRefs.activeSessionId.current === currentSessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore di connessione:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...(sessionRefs.sessionMessages.current[currentSessionId] || []), errorMsg];
        setMessagesForSession(currentSessionId, finalMsgs);
        saveMessagesImmediately(currentSessionId, finalMsgs);
      }
    } finally {
      const sid = sessionRefs.activeSessionId.current;
      if (sid) {
        const msgs = sessionRefs.sessionMessages.current[sid];
        if (msgs && msgs.length > 0) {
          try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (e) {}
        }
      }
      setLoading(false);
      abortRef.current = null;
      globalAbortController = null;
      streamingSessionIdRef.current = null;
    }
  }, [input, loading, selectedModel, providerConfigs, quickConfig, loopMaxIterations, actionStrategy, actionMaxReadIterations, actionMaxTotalReads, webSearch, attachedFiles, pcFiles, activeMode, selectedManifestoPath, externalOpenFiles, refreshConfig, saveSessionsState, setMessagesForSession, saveMessagesImmediately, handleExecuteStream, sessionRefs, setActiveSessionId]);

  // --- Drag & Drop ---
  const removePcFile = useCallback((filename) => { setPcFiles(prev => prev.filter(f => f.filename !== filename)); }, []);
  const handleDragOver = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    Promise.all(files.map(f => new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve({ filename: f.name, content: ev.target.result });
      reader.onerror = () => resolve(null);
      reader.readAsText(f);
    }))).then(results => { const valid = results.filter(Boolean); setPcFiles(prev => [...prev, ...valid].slice(0, 20)); });
  }, []);

  return {
    input,
    setInput,
    loading,
    setLoading,
    activeMode,
    setActiveMode,
    actionsLog,
    setActionsLog,
    attachedFiles,
    setAttachedFiles,
    pcFiles,
    setPcFiles,
    dragOver,
    expandedThinking,
    setExpandedThinking,
    autoScroll,
    setAutoScroll,
    webSearch,
    setWebSearch,
    loopMaxIterations,
    setLoopMaxIterations,
    loopIteration,
    setLoopIteration,
    loopActive,
    setLoopActive,
    actionStrategy,
    setActionStrategy,
    actionMaxReadIterations,
    setActionMaxReadIterations,
    actionMaxTotalReads,
    setActionMaxTotalReads,
    autoApprove,
    setAutoApprove,
    currentPlan,
    setCurrentPlan,
    planExecuting,
    setPlanExecuting,
    showHistory,
    setShowHistory,
    showFilePicker,
    setShowFilePicker,
    sendMessage,
    stopInference,
    removePcFile,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    streamingRefs: {
      abort: abortRef,
      streamingSessionId: streamingSessionIdRef,
      loopActive: loopActiveRef,
      loopIteration: loopIterationRef,
      loopMaxIterations: loopMaxIterationsRef,
      messagesEnd: messagesEndRef
    }
  };
}
