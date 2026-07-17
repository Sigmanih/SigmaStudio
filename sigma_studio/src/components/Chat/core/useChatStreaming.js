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
  openFiles: externalOpenFiles,
  onTasksUpdated,
  addToast,
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
  const [activeMode, setActiveMode] = useState('chat');
  const [actionsLog, setActionsLog] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [pcFiles, setPcFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
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
  const [showFilePicker, setShowFilePicker] = useState(false);

  const abortRef = useRef(null);
  const streamingSessionIdRef = useRef(null);
  const loopActiveRef = useRef(loopActive);
  const loopIterationRef = useRef(loopIteration);
  const loopMaxIterationsRef = useRef(loopMaxIterations);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [sessionMessages, activeSessionId, loading, autoScroll]);

  useEffect(() => { loopActiveRef.current = loopActive; }, [loopActive]);
  useEffect(() => { loopIterationRef.current = loopIteration; }, [loopIteration]);
  useEffect(() => { loopMaxIterationsRef.current = loopMaxIterations; }, [loopMaxIterations]);

  const stopInference = useCallback(() => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    if (globalAbortController) { globalAbortController.abort(); globalAbortController = null; }
    setLoopActive(false);
    setLoading(false);
    streamingSessionIdRef.current = null;
    sessionStorage.removeItem('sigma_pending_chat');
  }, []);

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
          const withActions = [...finalMessages, { role: 'system', content: `⚡ **Azioni eseguite:**`, timestamp: new Date().toISOString(), isAction: true, actions_log: data.actions_log }];
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

  // --- Send Message (unified: chat + plan) ---
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

      // Unified: chat mode (allow_actions=true, auto-detect) or plan mode (planning_mode=true)
      const useStream = !isPlan;
      const body = {
        message: input.trim(), bot_name: selectedModel, model: selectedModel,
        model_provider: routing.provider, model_endpoint: routing.endpoint, model_api_url: routing.api_url,
        allow_actions: !isPlan, planning_mode: isPlan, stream: useStream,
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
  }, [input, loading, selectedModel, providerConfigs, quickConfig, loopMaxIterations, webSearch, attachedFiles, pcFiles, activeMode, selectedManifestoPath, externalOpenFiles, refreshConfig, saveSessionsState, setMessagesForSession, saveMessagesImmediately, sessionRefs, setActiveSessionId]);

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
    input, setInput, loading, setLoading, activeMode, setActiveMode,
    actionsLog, setActionsLog, attachedFiles, setAttachedFiles,
    pcFiles, setPcFiles, dragOver, expandedThinking, setExpandedThinking,
    autoScroll, setAutoScroll, webSearch, setWebSearch,
    loopMaxIterations, setLoopMaxIterations, loopIteration, setLoopIteration,
    loopActive, setLoopActive, actionStrategy, setActionStrategy,
    actionMaxReadIterations, setActionMaxReadIterations,
    actionMaxTotalReads, setActionMaxTotalReads, autoApprove, setAutoApprove,
    currentPlan, setCurrentPlan, planExecuting, setPlanExecuting,
    showHistory, setShowHistory, showFilePicker, setShowFilePicker,
    sendMessage, stopInference, removePcFile,
    handleDragOver, handleDragLeave, handleDrop,
    streamingRefs: {
      abort: abortRef, streamingSessionId: streamingSessionIdRef,
      loopActive: loopActiveRef, loopIteration: loopIterationRef,
      loopMaxIterations: loopMaxIterationsRef, messagesEnd: messagesEndRef
    }
  };
}