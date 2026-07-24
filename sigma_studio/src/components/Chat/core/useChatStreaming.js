import { useState, useCallback, useRef, useEffect } from 'react';
import { MAX_ATTACHMENTS, createSession, MAX_HISTORY } from '../chatStorage';
import { getModelRoutingInfo } from '../modelProviderMap';
import { getAgentStyle } from '../AgentMessage';

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
  let cleaned = text;

  // 1. Remove XML thinking tags
  cleaned = cleaned.replace(/<(thinking|Thought|reasoning|Rationale|scratchpad)>[\s\S]*?<\/\1>/gi, '');

  // 2. Remove "Here's a thinking process:" English self-analysis blocks
  cleaned = cleaned.replace(/^(?:We\s+need\s+to|We\s+must|Let'?s\s+craft|Here'?s\s+a\s+thinking\s+process|Analyze\s+User\s+Input|Determine\s+Output\s+Structure|Draft\s+Content|Self-Correction|Execution|Plan|Requirements\s+from\s+System\s+Prompt)[\s\S]*?(?=\n#|\nEcco|\n1️⃣|\n[A-ZÀ-Ü]|\n\{|\n\n|\Z)/gi, '');
  cleaned = cleaned.replace(/^(?:-\s*(?:Request|Language|Domain|Requirements|Identity|Rules|Structure):[^\n]*\n)+/gi, '');

  // 3. Extract "response" value if raw JSON object string was outputted by LLM
  if (cleaned.trim().startsWith('{') && cleaned.includes('"response"')) {
    try {
      const parsed = JSON.parse(cleaned.trim());
      if (parsed.response && typeof parsed.response === 'string') {
        cleaned = parsed.response;
      }
    } catch (e) {
      const match = cleaned.match(/"response"\s*:\s*"([\s\S]*?)"\s*,\s*"thinking"/);
      if (match && match[1]) {
        cleaned = match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
      }
    }
  }

  // 4. Remove meta-reasoning headers (e.g. "🧭 **Ragionamento e procedura operativa:**")
  cleaned = cleaned.replace(/^(?:🧭|🧠|🔍)?\s*\*\*Ragionamento\s+e\s+procedura\s+operativa[^*]*\*\*:[^\n]*\n(?:[0-9]+\.[^\n]*\n)*/gi, '');
  cleaned = cleaned.replace(/^(?:🧭|🧠|🔍)?\s*\*\*Ragionamento\s+passo-passo[^*]*\*\*:[^\n]*\n(?:[0-9]+\.[^\n]*\n)*/gi, '');

  // 5. Remove container tags and cleanup
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
    
    const sid = streamingSessionIdRef.current || sessionRefs.activeSessionId.current;
    if (sid) {
      setSessionMessages(prev => {
        const msgs = [...(prev[sid] || [])];
        if (msgs.length > 0) {
          const last = msgs[msgs.length - 1];
          if (last.role === 'assistant') {
            msgs[msgs.length - 1] = {
              ...last,
              streaming: false,
              streamingThinking: false,
              statusMessage: undefined,
              content: last.content?.trim() || '🛑 *Generazione interrotta dall\'utente.*'
            };
          }
          saveMessagesImmediately(sid, msgs);
          try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (e) {}
        }
        return { ...prev, [sid]: msgs };
      });
    }

    setLoopActive(false);
    setLoading(false);
    streamingSessionIdRef.current = null;
    sessionStorage.removeItem('sigma_pending_chat');
  }, [saveMessagesImmediately, sessionRefs]);

  const handleStreamResponse = async (res, sessionId, continuationCount = 0) => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '', fullThinking = '', buffer = '';
    let firstToken = true, hasThinking = false, wasTruncated = false;
    const modelName = selectedModel;
    
    let streamAgentId = activeManifesto?.path?.replace('manifesti/', '')?.replace('.md', '') || '';
    let streamAgentName = activeManifesto?.name || '';
    let streamAgentStyle = getAgentStyle(streamAgentId);

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
              if (p.truncated || p.done_reason === 'length') {
                wasTruncated = true;
              }
              if (p.meta) {
                streamAgentId = p.meta.agent_id || p.meta.manifesto_used;
                streamAgentName = p.meta.agent_name || streamAgentId;
                streamAgentStyle = getAgentStyle(streamAgentId);
                const modelStatus = p.meta.model_status;
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      agent_id: streamAgentId,
                      agentRole: streamAgentStyle.name || streamAgentName,
                      agentName: `${streamAgentStyle.name || streamAgentName} (${selectedModel})`,
                      agentImage: streamAgentStyle.image || '/images/default.png',
                      statusMessage: modelStatus || n[n.length - 1].statusMessage
                    };
                  }
                  return { ...prev, [sessionId]: n };
                });
              }
              if (p.thinking) { hasThinking = true; fullThinking += p.thinking; }
              if (p.token) { fullText += p.token; }
              if (firstToken && continuationCount === 0) {
                firstToken = false;
                setSessionMessages(prev => ({
                  ...prev,
                  [sessionId]: [...(prev[sessionId] || []), {
                    role: 'assistant',
                    content: fullText,
                    agent_id: streamAgentId,
                    agentName: `${streamAgentStyle.name || streamAgentName || selectedModel} (${selectedModel})`,
                    agentRole: streamAgentStyle.name || streamAgentName || activeManifesto?.name || '',
                    agentImage: streamAgentStyle.image || activeManifesto?.image || '/images/default.png',
                    timestamp: new Date().toISOString(),
                    streaming: true,
                    thinking: hasThinking ? fullThinking : undefined,
                    streamingThinking: hasThinking
                  }]
                }));
              } else {
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    const existingContent = continuationCount > 0 ? n[n.length - 1].content : '';
                    const updatedContent = continuationCount > 0 ? existingContent + fullText : fullText;
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      content: updatedContent,
                      thinking: hasThinking ? fullThinking : n[n.length - 1].thinking,
                      streamingThinking: hasThinking
                    };
                  }
                  return { ...prev, [sessionId]: n };
                });
              }
            } catch (e) {}
          }
          if (streamDone) break;
        }
      }

      if (wasTruncated && continuationCount < 3) {
        setSessionMessages(prev => {
          const n = [...(prev[sessionId] || [])];
          if (n.length > 0 && n[n.length - 1].role === 'assistant') {
            n[n.length - 1] = {
              ...n[n.length - 1],
              statusMessage: '⚡ Token massimi raggiunti: Auto-continuazione in corso...'
            };
          }
          return { ...prev, [sessionId]: n };
        });

        try {
          const contRes = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: "Continua esattamente da dove ti sei fermato nell'ultimo messaggio, senza ripetere il testo già scritto.",
              history: sessionRefs.sessionMessages.current[sessionId] || [],
              stream: true,
              provider: activeProvider,
              model: selectedModel,
              manifesto: activeManifesto?.path
            })
          });
          if (contRes.ok) {
            await handleStreamResponse(contRes, sessionId, continuationCount + 1);
            return;
          }
        } catch (contErr) {
          console.warn("Auto-continuation fetch failed:", contErr);
        }
      }

      setLoading(false);
      const finalContent = cleanModelTags(fullText) || (fullThinking ? cleanModelTags(fullThinking) : (hasError ? streamErrorMsg || '⚠️ Error' : '⚠️ Nessuna risposta.'));
      setSessionMessages(prev => {
        const n = [...(prev[sessionId] || [])];
        if (n.length > 0 && n[n.length - 1].role === 'assistant') n[n.length - 1] = { ...n[n.length - 1], content: finalContent, streaming: false, streamingThinking: false, statusMessage: undefined };
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
      const routedAgentId = data.agent_id || data.manifesto_used;
      const routedAgentName = data.agent_name || data.bot_name;
      const style = getAgentStyle(routedAgentId);
      const assistant = {
        role: 'assistant',
        content: cleanModelTags(data.response) || '⚠️ Nessuna risposta.',
        thinking: data.thinking || null,
        actions_log: data.actions_log || [],
        timestamp: new Date().toISOString(),
        error: data.error || null,
        agent_id: routedAgentId,
        agentName: `${style.name || routedAgentName || selectedModel} (${selectedModel})`,
        agentRole: style.name || routedAgentName || activeManifesto?.name || 'AI',
        agentImage: style.image || activeManifesto?.image || '/images/default.png'
      };
      if (sessionRefs.activeSessionId.current === sessionId) {
        const finalMessages = [...updatedMessages, assistant];
        setMessagesForSession(sessionId, finalMessages);
        saveMessagesImmediately(sessionId, finalMessages);
        if (data.actions_log?.length > 0) {
          setActionsLog(data.actions_log);
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

      const useStream = !isPlan;
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
      const contentType = res.headers.get("content-type") || "";
      if (res.ok && contentType.includes("text/event-stream")) {
        await handleStreamResponse(res, currentSessionId);
      } else {
        await handleJsonResponse(res, currentSessionId, updatedMessages);
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        sessionStorage.removeItem('sigma_pending_chat');
        const sid = currentSessionId || sessionRefs.activeSessionId.current;
        if (sid) {
          const msgs = sessionRefs.sessionMessages.current[sid] || [];
          if (msgs.length > 0) {
            saveMessagesImmediately(sid, msgs);
            try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (err) {}
          }
        }
        return;
      }
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