// ==============================================================================
// useChatCore.js — Central hook for all chat logic
// Sigma Studio v7 — Sessioni, messaggi, streaming, execute loop, modelli, piani
// Utilizzato da ChatFloatingPanel e ChatWorkspaceTab
// ==============================================================================
import { useState, useRef, useEffect, useCallback } from 'react';
import { PROVIDER_COLORS, getModelRoutingInfo } from '../modelProviderMap';
import { STORAGE_KEY, MAX_HISTORY, MAX_ATTACHMENTS, createSession, loadLastModel, saveLastModel } from '../chatStorage';

const DEBOUNCE_SAVE_MS = 2000;
let globalAbortController = null;

function appendAndSave(sid, msg, setFn) {
  setFn(prev => {
    const updated = [...(prev[sid] || []), msg];
    try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(updated)); } catch (e) {}
    return { ...prev, [sid]: updated };
  });
}

export default function useChatCore(extraProps = {}) {
  const { openFiles: externalOpenFiles, onTasksUpdated, addToast } = extraProps;

  // --- Core state ---
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionMessages, setSessionMessages] = useState({});
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [configModel, setConfigModel] = useState('llama3.2');
  const [configProvider, setConfigProvider] = useState('ollama');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [providerConfigs, setProviderConfigs] = useState({});
  const [activeMode, setActiveMode] = useState('ask');
  const [actionsLog, setActionsLog] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [pcFiles, setPcFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [webSearch, setWebSearch] = useState(false);

  // --- Quick config ---
  const [quickConfig, setQuickConfig] = useState({ temperature: 0.7, max_tokens: 4096, top_p: 0.9, top_k: 40, repeat_penalty: 1.1, num_ctx: 8192, seed: 0, timeout: 300 });

  // --- Manifesto ---
  const [activeManifesto, setActiveManifesto] = useState({ name: '', path: '', exists: false });
  const [manifestos, setManifestos] = useState([]);
  const [selectedManifestoPath, setSelectedManifestoPath] = useState('');
  const [manifestoManuallySelected, setManifestoManuallySelected] = useState(false);
  const [showManifestoDropdown, setShowManifestoDropdown] = useState(false);

  // --- Loop / Execute state ---
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

  // --- UI state ---
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [editingSessionName, setEditingSessionName] = useState(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [showQuickConfig, setShowQuickConfig] = useState(false);

  // --- Refs ---
  const refs = {
    messagesEnd: useRef(null),
    input: useRef(null),
    modelBtn: useRef(null),
    panel: useRef(null),
    abort: useRef(null),
    sessions: useRef(sessions),
    sessionMessages: useRef(sessionMessages),
    activeSessionId: useRef(activeSessionId),
    loading: useRef(loading),
    saveDebounceTimer: useRef(null),
    streamingSessionId: useRef(null),
    loopActive: useRef(false),
    loopIteration: useRef(0),
    loopMaxIterations: useRef(25),
    taskDrivenLoopRunning: useRef(false),
    manifestoManuallySelected: useRef(false),
  };

  // --- Keep refs in sync ---
  useEffect(() => { refs.sessions.current = sessions; }, [sessions]);
  useEffect(() => { refs.sessionMessages.current = sessionMessages; }, [sessionMessages]);
  useEffect(() => { refs.activeSessionId.current = activeSessionId; }, [activeSessionId]);
  useEffect(() => { refs.loading.current = loading; }, [loading]);
  useEffect(() => { refs.loopActive.current = loopActive; }, [loopActive]);
  useEffect(() => { refs.loopIteration.current = loopIteration; }, [loopIteration]);
  useEffect(() => { refs.loopMaxIterations.current = loopMaxIterations; }, [loopMaxIterations]);
  useEffect(() => { refs.manifestoManuallySelected.current = manifestoManuallySelected; }, [manifestoManuallySelected]);

  const messages = activeSessionId ? (sessionMessages[activeSessionId] || []) : [];
  const currentRouting = getModelRoutingInfo(selectedModel, providerConfigs);
  const providerColors = PROVIDER_COLORS[currentRouting.provider] || { bg: '#333', color: '#ccc' };

  // --- Helpers ---
  const setMessagesForSession = useCallback((sessionId, msgsOrUpdater) => {
    setSessionMessages(prev => {
      const existing = prev[sessionId] || [];
      const next = typeof msgsOrUpdater === 'function' ? msgsOrUpdater(existing) : msgsOrUpdater;
      return { ...prev, [sessionId]: next };
    });
  }, []);

  const saveMessagesImmediately = useCallback((sessionId, msgs) => {
    if (!sessionId) return;
    try {
      if (msgs && msgs.length > 0) localStorage.setItem(`sigma_chat_msgs_${sessionId}`, JSON.stringify(msgs));
    } catch (e) {}
  }, []);

  const loadMessagesFromStorage = (id) => {
    if (!id) return null;
    try {
      const d = localStorage.getItem(`sigma_chat_msgs_${id}`);
      if (d) { const p = JSON.parse(d); if (Array.isArray(p) && p.length > 0) return p; }
    } catch (e) {}
    return null;
  };

  // --- Init ---
  useEffect(() => {
    const lastModel = loadLastModel();
    if (lastModel) setSelectedModel(lastModel);
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      setSessions(saved);
      if (saved.length > 0) {
        const sid = saved[0].id;
        const stored = loadMessagesFromStorage(sid);
        if (stored) { setSessionMessages(prev => ({ ...prev, [sid]: stored })); setActiveSessionId(sid); }
      }
    } catch (e) {}
    try {
      const saved = JSON.parse(localStorage.getItem('sigma_selected_manifesto'));
      if (saved && saved.name) {
        setActiveManifesto(saved); setSelectedManifestoPath(saved.path || ''); setManifestoManuallySelected(true);
      }
    } catch (e) {}
    fetchConfigAndModels();
    fetchManifestos();
  }, []);

  useEffect(() => {
    return () => { if (refs.saveDebounceTimer.current) clearTimeout(refs.saveDebounceTimer.current); };
  }, []);

  useEffect(() => {
    const handleBeforeUnload = () => {
      const sid = refs.activeSessionId.current;
      const msgs = refs.sessionMessages.current[sid];
      if (sid && msgs && msgs.length > 0) {
        try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (e) {}
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  useEffect(() => { if (configProvider) fetchOllamaModels(); }, [configProvider]);
  useEffect(() => { if (autoScroll) refs.messagesEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, actionsLog, autoScroll]);

  // --- API calls ---
  const fetchConfigAndModels = async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        if (d.config?.providers) setProviderConfigs(d.config.providers);
        if (d.config?.model) { setSelectedModel(d.config.model); setConfigModel(d.config.model); }
        if (d.config?.provider) setConfigProvider(d.config.provider);
        if (d.config?.manifesto && !refs.manifestoManuallySelected.current) setActiveManifesto(d.config.manifesto);
      }
    } catch (e) {} finally { fetchOllamaModels(); }
  };

  const fetchOllamaModels = async () => {
    setLoadingModels(true);
    try {
      const res = await fetch('/api/ollama_models');
      const data = await res.json();
      let models = data.models?.length ? data.models : [];
      const known = new Set(models.map(m => m.name));
      if (providerConfigs) {
        Object.entries(providerConfigs).forEach(([, pv]) => {
          (pv.models || []).forEach(m => { if (!known.has(m)) { models.push({ name: m, size: 'API' }); known.add(m); } });
          if (pv.model && !known.has(pv.model)) { models.push({ name: pv.model, size: 'API' }); known.add(pv.model); }
        });
      }
      if (models.length > 0) setAvailableModels(models);
    } catch (e) {}
    if (availableModels.length === 0 && selectedModel) setAvailableModels([{ name: selectedModel, size: configProvider !== 'ollama' ? 'API' : '' }]);
    setLoadingModels(false);
  };

  const refreshConfig = useCallback(async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        if (d.config?.providers) setProviderConfigs(d.config.providers);
        if (d.config?.model) setConfigModel(d.config.model);
        if (d.config?.provider) setConfigProvider(d.config.provider);
        setQuickConfig(prev => ({ ...prev, temperature: d.config?.temperature ?? 0.7, max_tokens: d.config?.max_tokens ?? 32768, top_p: d.config?.top_p ?? 0.9, top_k: d.config?.top_k ?? 40, repeat_penalty: d.config?.repeat_penalty ?? 1.1, num_ctx: d.config?.num_ctx ?? 32768, seed: d.config?.seed ?? 0, timeout: d.config?.timeout ?? 300 }));
        if (d.config?.manifesto && !refs.manifestoManuallySelected.current) setActiveManifesto(d.config.manifesto);
      }
    } catch (e) {}
  }, []);

  const fetchManifestos = useCallback(async () => {
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      if (data.success && data.files) setManifestos(data.files.map(f => ({ path: f.path, name: f.name.replace('.md', '') })));
    } catch (e) {}
  }, []);

  const saveQuickConfig = async (key, value) => {
    const updated = { ...quickConfig, [key]: value };
    setQuickConfig(updated);
    try { await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updated) }); } catch (e) {}
  };

  // --- Session management ---
  const saveSessionsState = useCallback((ns) => {
    setSessions(ns);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ns)); } catch (e) {}
  }, []);

  const switchToSession = useCallback((sid) => {
    const curId = refs.activeSessionId.current;
    const curMsgs = refs.sessionMessages.current[curId];
    if (curId && curMsgs && curMsgs.length > 0) saveMessagesImmediately(curId, curMsgs);
    const s = refs.sessions.current.find(x => x.id === sid);
    if (s) {
      let msgsForSession = refs.sessionMessages.current[sid];
      if (!msgsForSession || msgsForSession.length === 0) {
        const stored = loadMessagesFromStorage(sid);
        msgsForSession = stored && stored.length > 0 ? stored : [{ role: 'assistant', content: '# 🤖 Sigma AI Studio\n\nChat pronta.', timestamp: new Date().toISOString() }];
        setSessionMessages(prev => ({ ...prev, [sid]: msgsForSession }));
      }
      setSelectedModel(s.model || selectedModel);
      setActiveSessionId(sid);
    }
    setActionsLog([]);
  }, [selectedModel, saveMessagesImmediately]);

  const handleNewSession = () => {
    const s = createSession(selectedModel);
    const updated = [s, ...sessions].slice(0, MAX_HISTORY);
    saveSessionsState(updated);
    const welcomeMsg = { role: 'assistant', content: '# 🤖 Sigma AI Studio\n\nChat pronta.', timestamp: new Date().toISOString() };
    setSessionMessages(prev => ({ ...prev, [s.id]: [welcomeMsg] }));
    saveMessagesImmediately(s.id, [welcomeMsg]);
    setActiveSessionId(s.id);
    setActionsLog([]);
    setSelectedModel(s.model);
  };

  const handleDeleteSession = (e, sid) => {
    e.stopPropagation();
    const ns = sessions.filter(s => s.id !== sid);
    saveSessionsState(ns);
    setSessionMessages(prev => { const next = { ...prev }; delete next[sid]; return next; });
    try { localStorage.removeItem(`sigma_chat_msgs_${sid}`); } catch (e) {}
    if (activeSessionId === sid) {
      if (ns.length > 0) switchToSession(ns[0].id);
      else { const s = createSession(selectedModel); saveSessionsState([s]); setSessionMessages({ [s.id]: [{ role: 'assistant', content: '# 🤖 Sigma AI Studio\n\nChat pronta.', timestamp: new Date().toISOString() }] }); saveMessagesImmediately(s.id, [welcomeMsg]); switchToSession(s.id); }
    }
  };

  const handleStartRename = (e, sid) => { e.stopPropagation(); const s = sessions.find(x => x.id === sid); setEditingSessionName(sid); setEditNameValue(s?.name || ''); };
  const handleFinishRename = (sid) => { const name = editNameValue.trim() || 'Chat'; saveSessionsState(sessions.map(s => s.id === sid ? { ...s, name } : s)); setEditingSessionName(null); };
  const handleRenameKeyDown = (e, sid) => { if (e.key === 'Enter') handleFinishRename(sid); if (e.key === 'Escape') setEditingSessionName(null); };

  const handleModelSelect = async (name) => {
    setSelectedModel(name); setShowModelDropdown(false); saveLastModel(name);
    if (refs.activeSessionId.current) saveSessionsState(refs.sessions.current.map(s => s.id === refs.activeSessionId.current ? { ...s, model: name, updatedAt: new Date().toISOString() } : s));
    try {
      const cfg = await (await fetch('/api/config')).json();
      if (cfg.success?.config) await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...cfg.config, model: name }) });
      await fetchOllamaModels();
    } catch (e) {}
  };

  // --- Streaming handler (regular chat) ---
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
              if (p.error) { streamErrorMsg = p.error; hasError = true; streamDone = true; break; }
              if (p.token) fullText += p.token;
              if (p.thinking) { fullThinking += p.thinking; hasThinking = true; }
              if (firstToken && (fullText || fullThinking)) {
                firstToken = false;
                setSessionMessages(prev => ({ ...prev, [sessionId]: [...(prev[sessionId] || []), { role: 'assistant', content: fullText, agentName: modelName, timestamp: new Date().toISOString(), streaming: true, thinking: hasThinking ? fullThinking : undefined, streamingThinking: hasThinking }] }));
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
      saveMessagesImmediately(sessionId, refs.sessionMessages.current[sessionId] || []);
    } catch (e) {
      setLoading(false);
      setSessionMessages(prev => [...(prev[sessionId] || []), { role: 'assistant', content: `⚠️ **Errore:** ${e.message}`, timestamp: new Date().toISOString(), error: true }]);
    }
  };

  // --- JSON response handler ---
  const handleJsonResponse = async (res, sessionId, updatedMessages) => {
    try {
      const data = await res.json();
      const assistant = { role: 'assistant', content: data.response || '⚠️ Nessuna risposta.', thinking: data.thinking || null, timestamp: new Date().toISOString(), error: data.error || null, agentName: selectedModel };
      if (refs.activeSessionId.current === sessionId) {
        const finalMessages = [...updatedMessages, assistant];
        setMessagesForSession(sessionId, finalMessages);
        saveMessagesImmediately(sessionId, finalMessages);
        if (data.actions_log?.length > 0) {
          setActionsLog(data.actions_log);
          const logStr = data.actions_log.map(a => `  ${a.success ? '✅' : '❌'} ${a.type}: ${a.message || a.error}`).join('\n');
          const withActions = [...finalMessages, { role: 'system', content: `📋 **Azioni Eseguite:**\n\`\`\`\n${logStr}\n\`\`\``, timestamp: new Date().toISOString(), isAction: true }];
          setMessagesForSession(sessionId, withActions);
          saveMessagesImmediately(sessionId, withActions);
          if (onTasksUpdated) onTasksUpdated();
        }
      } else {
        const prevForSession = refs.sessionMessages.current[sessionId] || [];
        const finalMessages = [...prevForSession, ...updatedMessages.slice(prevForSession.length), assistant];
        setSessionMessages(prev => ({ ...prev, [sessionId]: finalMessages }));
        saveMessagesImmediately(sessionId, finalMessages);
      }
    } catch (e) {
      if (refs.activeSessionId.current === sessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore nella risposta del server:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...updatedMessages, errorMsg];
        setMessagesForSession(sessionId, finalMsgs);
        saveMessagesImmediately(sessionId, finalMsgs);
      }
    }
  };

  // --- SS Execute handler ---
  const handleExecuteStream = useCallback(async (res, sessionId) => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
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
            const sid = refs.activeSessionId.current || sessionId;
            let msgContent = '', toastType = 'info', toastDuration = 3000;

            if (event.type === 'execute_start') {
              msgContent = `🔄 **Esecuzione continua avviata** con ${selectedModel}`;
              setLoopIteration(0);
            } else if (event.type === 'iteration_start') {
              msgContent = `🔄 **Iterazione ${event.iteration}/${event.max_iterations}**`;
              setLoopIteration(event.iteration);
            } else if (event.type === 'iteration_actions') {
              const actionNames = (event.actions || []).join(', ');
              msgContent = `⚡ **Esecuzione ${event.actions_count} azioni:** ${actionNames}`;
            } else if (event.type === 'iteration_complete') {
              const logStr = (event.actions_log || []).map(a => `  ${a.success ? '✅' : '❌'} ${a.type}: ${a.message || a.error || ''}`).join('\n');
              msgContent = `✅ **Iterazione ${event.iteration} completata:** ${event.success_count}/${event.success_count + event.fail_count} azioni riuscite\n${logStr ? '\n' + logStr : ''}`;
              if (event.actions_log) setActionsLog(event.actions_log);
              if (onTasksUpdated) onTasksUpdated();
              toastType = 'success'; toastDuration = 3000;
            } else if (event.type === 'execute_done') {
              const s = event.summary || {};
              msgContent = `🎯 **Task completato in ${event.total_iterations} iterazioni!**\n📊 Riepilogo:\n- 📋 ${s.actions_count || 0} azioni eseguite`;
              if (onTasksUpdated) onTasksUpdated();
              toastType = 'success'; toastDuration = 5000;
            } else if (event.type === 'execute_timeout') {
              msgContent = `⏱️ **Limite iterazioni raggiunto:** ${event.max_iterations}`;
              toastType = 'warning'; toastDuration = 5000;
            } else if (event.type === 'iteration_plan') {
              msgContent = `📋 **Pianificazione:** ${event.message || ''}`;
            } else if (event.type === 'iteration_response') {
              // Mostra la risposta AI come messaggio nella chat (esattamente come in modalità Chiedi)
              if (event.response && sid) {
                const newMsg = { 
                  role: 'assistant', 
                  content: event.response, 
                  timestamp: new Date().toISOString(), 
                  agentName: selectedModel,
                  thinking: event.thinking || undefined,
                };
                setSessionMessages(prev => {
                  const updated = [...(prev[sid] || []), newMsg];
                  try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(updated)); } catch (e) {}
                  return { ...prev, [sid]: updated };
                });
              }
              // Non mostra toast per non disturbare
              continue;
            } else if (event.type === 'error') {
              msgContent = `❌ ${event.message || event.error || 'Errore'}`;
              toastType = 'error'; toastDuration = 8000;
            } else if (event.type === 'done') {
              const s = event.summary || {};
              msgContent = `🎯 **Loop completato:** ${s.successful_actions || 0}/${s.total_actions || 0} azioni, ${s.files_created || 0} file, ${s.tests_passed || 0}/${s.tests_run || 0} test`;
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
              const newMsg = { role: 'system', content: msgContent, timestamp: new Date().toISOString(), isAction: true };
              appendAndSave(sid, newMsg, setSessionMessages);
            }
            if (addToast && msgContent) addToast(msgContent.replace(/\*\*/g, '').split('\n')[0], toastType, toastDuration);
          }
          if (done) break;
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError' && refs.activeSessionId.current) {
        const errMsg = { role: 'system', content: `❌ **Errore execute:** ${e.message}`, timestamp: new Date().toISOString(), isAction: true, error: true };
        appendAndSave(refs.activeSessionId.current, errMsg, setSessionMessages);
      }
    }
  }, [selectedModel, addToast, onTasksUpdated]);

  // --- Core sendMessage ---
  const sendMessage = useCallback(async () => {
    if (!input.trim() || loading) return;
    await refreshConfig();
    let currentSessionId = refs.activeSessionId.current;
    let currentSessions = refs.sessions.current;
    if (!currentSessionId) {
      const session = createSession(selectedModel);
      currentSessions = [session, ...currentSessions].slice(0, MAX_HISTORY);
      saveSessionsState(currentSessions);
      currentSessionId = session.id;
      setActiveSessionId(currentSessionId);
    }
    refs.streamingSessionId.current = currentSessionId;
    const openFiles = externalOpenFiles || [];
    const contextFiles = [...(openFiles || []), ...attachedFiles].slice(0, MAX_ATTACHMENTS);
    const userMsg = { role: 'user', content: input.trim(), timestamp: new Date().toISOString(), attachments: attachedFiles.length > 0 ? [...attachedFiles] : undefined, agentName: selectedModel };
    const currentMsgs = refs.sessionMessages.current[currentSessionId] || [];
    const updatedMessages = [...currentMsgs, userMsg];
    setMessagesForSession(currentSessionId, updatedMessages);
    saveMessagesImmediately(currentSessionId, updatedMessages);
    const sessionName = refs.sessions.current.find(s => s.id === currentSessionId)?.name;
    if (sessionName && sessionName.startsWith('Chat ')) {
      const firstWords = input.trim().slice(0, 50).replace(/\n/g, ' ');
      const newName = `${firstWords}... (${selectedModel.split(':')[0]})`;
      saveSessionsState(refs.sessions.current.map(s => s.id === currentSessionId ? { ...s, name: newName } : s));
    }
    setInput('');
    setLoading(true);
    setActionsLog([]);
    const controller = new AbortController();
    refs.abort.current = controller;
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
          saveMessagesImmediately(currentSessionId, [...(refs.sessionMessages.current[currentSessionId] || []), errMsg]);
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
      if (refs.activeSessionId.current === currentSessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore di connessione:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...(refs.sessionMessages.current[currentSessionId] || []), errorMsg];
        setMessagesForSession(currentSessionId, finalMsgs);
        saveMessagesImmediately(currentSessionId, finalMsgs);
      }
    } finally {
      // Force save all messages before cleanup
      const sid = refs.activeSessionId.current;
      if (sid) {
        const msgs = refs.sessionMessages.current[sid];
        if (msgs && msgs.length > 0) {
          try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (e) {}
        }
      }
      setLoading(false);
      refs.abort.current = null;
      globalAbortController = null;
      refs.streamingSessionId.current = null;
    }
  }, [input, loading, selectedModel, providerConfigs, quickConfig, loopMaxIterations, actionStrategy, actionMaxReadIterations, actionMaxTotalReads, webSearch, attachedFiles, pcFiles, activeMode, selectedManifestoPath, externalOpenFiles, refreshConfig, saveSessionsState, setMessagesForSession, saveMessagesImmediately, handleExecuteStream]);

  // --- Stop ---
  const stopInference = useCallback(() => {
    if (refs.abort.current) { refs.abort.current.abort(); refs.abort.current = null; }
    if (globalAbortController) { globalAbortController.abort(); globalAbortController = null; }
    setLoopActive(false); setLoading(false);
    refs.streamingSessionId.current = null;
    sessionStorage.removeItem('sigma_pending_chat');
  }, []);

  // --- Drag & drop ---
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
    // State
    sessions, activeSessionId, sessionMessages, messages,
    input, setInput, loading, setLoading,
    selectedModel, setSelectedModel, configModel, configProvider,
    availableModels, loadingModels, providerConfigs, activeMode, setActiveMode,
    actionsLog, setActionsLog, attachedFiles, setAttachedFiles,
    pcFiles, setPcFiles, dragOver,
    expandedThinking, setExpandedThinking,
    autoScroll, setAutoScroll, webSearch, setWebSearch,
    quickConfig, setQuickConfig, showQuickConfig, setShowQuickConfig,
    activeManifesto, setActiveManifesto, manifestos,
    selectedManifestoPath, setSelectedManifestoPath,
    manifestoManuallySelected, showManifestoDropdown, setShowManifestoDropdown,
    loopMaxIterations, setLoopMaxIterations, loopIteration, setLoopIteration,
    loopActive, setLoopActive,
    actionStrategy, setActionStrategy,
    actionMaxReadIterations, setActionMaxReadIterations,
    actionMaxTotalReads, setActionMaxTotalReads,
    autoApprove, setAutoApprove,
    currentPlan, setCurrentPlan, planExecuting, setPlanExecuting,
    showHistory, setShowHistory,
    showModelDropdown, setShowModelDropdown,
    editingSessionName, editNameValue,
    setEditNameValue, showFilePicker, setShowFilePicker,
    refs, currentRouting, providerColors,
    maxTaskIterations: 10,

    // Actions
    sendMessage, stopInference, switchToSession, handleNewSession,
    handleDeleteSession, handleStartRename, handleFinishRename, handleRenameKeyDown,
    handleModelSelect, openModelDropdown: async () => { await refreshConfig(); await fetchOllamaModels(); setShowModelDropdown(!showModelDropdown); },
    removePcFile, handleDragOver, handleDragLeave, handleDrop,
    saveQuickConfig, refreshConfig,
    fetchOllamaModels, saveSessionsState,
  };
}

function cleanModelTags(text) {
  if (!text) return text;
  let cleaned = text.replace(/<(thinking|Thought|reasoning|Rationale|scratchpad)>[\s\S]*?<\/\1>/gi, '');
  cleaned = cleaned.replace(/<\/?(response|Response|output|Output|answer|Answer|result|Result|tool_call|ToolCall|function_call|FunctionCall)>/gi, '');
  cleaned = cleaned.replace(/<\/?[a-zA-Z_][a-zA-Z0-9_]*>/g, '');
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  return cleaned.trim();
}