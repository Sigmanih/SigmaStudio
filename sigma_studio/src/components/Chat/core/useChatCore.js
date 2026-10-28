// ==============================================================================
// useChatCore.js — Central hook orchestrating refactored composite hooks
// Sigma Studio v7 — Refactored to compose useChatSessions, useChatConfig & useChatStreaming
// ==============================================================================
import { useEffect, useCallback, useState, useRef, useMemo } from 'react';
import { PROVIDER_COLORS, getModelRoutingInfo } from '../modelProviderMap';
import { loadMessagesFromStorage, saveMessagesToStorage, createSession } from '../chatStorage';
import { initSpeechRecognition, createWakeWordMic, stopSpeech } from '../audioSpeech';
import { deriveAgentActivity, publishAgentActivity, releaseAgentActivity } from '../../common/agentActivity';
const saveMessagesImmediately = saveMessagesToStorage;


// Import composite hooks
import { useChatSessions } from './useChatSessions';
import { useChatConfig } from './useChatConfig';
import { useChatStreaming } from './useChatStreaming';
import { useMcpAutoApprove } from './useMcpAutoApprove';
import { useChatDevMode } from './useChatDevMode';

export default function useChatCore(extraProps = {}) {
  const { openFiles: externalOpenFiles, onTasksUpdated, addToast } = extraProps;
  
  // Dev Mode State (Developer Lab Harness integration)
  const devModeHook = useChatDevMode();
  
  // Speaker Agente State (TTS)
  const [speakerEnabled, setSpeakerEnabledState] = useState(() => {
    try {
      return localStorage.getItem('sigma_speaker_agent_enabled') === 'true';
    } catch (e) {
      return false;
    }
  });

  const setSpeakerEnabled = useCallback((enabled) => {
    setSpeakerEnabledState(enabled);
    try {
      localStorage.setItem('sigma_speaker_agent_enabled', String(enabled));
    } catch (e) {}
    if (!enabled) {
      stopSpeech();
    }
  }, []);

  const welcomeMessageObj = {
    role: 'assistant',
    isWelcome: true,
    content: '',
    timestamp: new Date().toISOString()
  };

  // 1. Sessions State & Handlers
  const sessionsHook = useChatSessions({
    selectedModel: '',
    setSelectedModel: null, // will update post-config
    setActionsLog: null,
    saveMessagesImmediately,
    loadMessagesFromStorage,
    welcomeMsg: welcomeMessageObj
  });

  // 2. Configuration State & Handlers
  const configHook = useChatConfig({
    saveSessionsState: sessionsHook.saveSessionsState,
    sessionRefs: sessionsHook.sessionRefs
  });

  // Connect sessions back to config selection
  sessionsHook.setSelectedModel = configHook.setSelectedModel;

  // 3. Streaming & Execution Loop Handlers
  const streamingHook = useChatStreaming({
    openFiles: externalOpenFiles,
    onTasksUpdated,
    addToast,
    speakerEnabled,
    
    // Sessions bindings
    sessions: sessionsHook.sessions,
    activeSessionId: sessionsHook.activeSessionId,
    setActiveSessionId: sessionsHook.setActiveSessionId,
    sessionMessages: sessionsHook.sessionMessages,
    setSessionMessages: sessionsHook.setSessionMessages,
    saveSessionsState: sessionsHook.saveSessionsState,
    setMessagesForSession: sessionsHook.setMessagesForSession,
    saveMessagesImmediately,
    loadMessagesFromStorage,
    welcomeMsg: welcomeMessageObj,
    sessionRefs: sessionsHook.sessionRefs,

    // Config bindings
    selectedModel: configHook.selectedModel,
    setSelectedModel: configHook.setSelectedModel,
    availableModels: configHook.availableModels,
    favoriteModels: configHook.favoriteModels,
    providerConfigs: configHook.providerConfigs,
    quickConfig: configHook.quickConfig,
    selectedManifestoPath: configHook.selectedManifestoPath,
    fetchOllamaModels: configHook.fetchOllamaModels,
    refreshConfig: configHook.refreshConfig,
    activeManifesto: configHook.activeManifesto,
    selectedHardware: configHook.selectedHardware,
    devModeEnabled: devModeHook.devModeEnabled,
    devRole: devModeHook.devRole,
    workspaceRoot: devModeHook.workspaceRoot
  });

  // Interruttore Auto Approve: stato condiviso con la tab MCP Tools.
  const mcpApproval = useMcpAutoApprove();

  // Connect actions log back to sessions switch
  sessionsHook.setActionsLog = streamingHook.setActionsLog;

  // Load configuration, models and manifestos on mount
  useEffect(() => {
    configHook.fetchConfigAndModels();
    configHook.fetchManifestos();

    try {
      const preload = localStorage.getItem('sigma_preload_agent');
      if (preload) {
        localStorage.removeItem('sigma_preload_agent');
        const mPath = preload.includes('/') ? preload.replace('manifesti/', 'roles/').replace('Ruoli/', 'roles/') : `roles/${preload}.md`;
        const saved = localStorage.getItem('sigma_selected_manifesto');
        let mObj = saved ? JSON.parse(saved) : null;
        if (!mObj) {
          mObj = { name: preload.replace(/_/g, ' '), path: mPath, exists: true, image: '/images/default.png' };
        }
        configHook.setActiveManifesto(mObj);
        configHook.setSelectedManifestoPath(mObj.path);
        configHook.setManifestoManuallySelected(true);
      }
    } catch (e) {}
  }, []);

  const handleSelectManifesto = useCallback((m) => {
    const manifesto = { name: m.name, path: m.path, exists: true, image: m.image || '/images/default.png' };
    configHook.setActiveManifesto(manifesto);
    configHook.setSelectedManifestoPath(m.path);
    configHook.setManifestoManuallySelected(true);
    configHook.setShowManifestoDropdown(false);
    try { localStorage.setItem('sigma_selected_manifesto', JSON.stringify(manifesto)); } catch (e) {}

    // Save selection in the current session
    if (sessionsHook.activeSessionId && sessionsHook.saveSessionsState) {
      sessionsHook.saveSessionsState(sessionsHook.sessions.map(s =>
        s.id === sessionsHook.activeSessionId
          ? { ...s, manifestoPath: m.path, updatedAt: new Date().toISOString() }
          : s
      ));
    }
  }, [sessionsHook.activeSessionId, sessionsHook.sessions, sessionsHook.saveSessionsState]);

  // La Home consegna ruolo, prompt e richiesta di invio via evento (chat gia' montata)
  // o localStorage (chat appena aperta). Il lavoro procede a tappe perche' ogni
  // passo dipende dallo stato aggiornato dal precedente:
  //   session -> se la conversazione attiva e' di un altro agente se ne apre una nuova
  //   role    -> si applica il ruolo (quando i manifesti sono caricati)
  //   send    -> si invia, solo quando il ruolo e' davvero quello attivo
  // Scegliere la sessione prima del ruolo evita di cambiare agente a una chat esistente.
  const homeJobRef = useRef(null);
  const [homeJobTick, setHomeJobTick] = useState(0);
  const bumpHomeJob = useCallback(() => setHomeJobTick(t => t + 1), []);

  useEffect(() => {
    const takePending = () => {
      try {
        const roleId = localStorage.getItem('sigma_active_role') || '';
        const prompt = localStorage.getItem('sigma_pending_chat_prompt') || '';
        const send = localStorage.getItem('sigma_pending_chat_send') === '1';
        const rawFiles = localStorage.getItem('sigma_pending_chat_files') || '';
        localStorage.removeItem('sigma_active_role');
        localStorage.removeItem('sigma_pending_chat_prompt');
        localStorage.removeItem('sigma_pending_chat_send');
        localStorage.removeItem('sigma_pending_chat_files');
        if (rawFiles) {
          try {
            const parsedFiles = JSON.parse(rawFiles);
            if (Array.isArray(parsedFiles) && parsedFiles.length > 0) {
              streamingHook.setPcFiles(parsedFiles);
            }
          } catch (e) {}
        }
        if (!roleId && !prompt && !rawFiles) return;
        homeJobRef.current = { roleId, prompt, send, stage: roleId ? 'session' : 'send', rolePath: '', since: Date.now() };
        bumpHomeJob();
      } catch (e) {}
    };
    takePending();
    window.addEventListener('sigma-chat-select-role', takePending);
    window.addEventListener('sigma-chat-set-prompt', takePending);
    return () => {
      window.removeEventListener('sigma-chat-select-role', takePending);
      window.removeEventListener('sigma-chat-set-prompt', takePending);
    };
  }, [bumpHomeJob]);

  useEffect(() => {
    const job = homeJobRef.current;
    if (!job) return;
    const wanted = `${job.roleId}.md`.toLowerCase();

    if (job.stage === 'session') {
      const activeId = sessionsHook.activeSessionId;
      const session = sessionsHook.sessions.find(x => x.id === activeId);
      const msgs = sessionsHook.sessionMessages[activeId] || loadMessagesFromStorage(activeId) || [];
      const hasConversation = msgs.some(m => m.role === 'user');
      const isAuto = job.roleId === 'auto';
      const currentPath = (session?.manifestoPath || '').toLowerCase();
      const sameAgent = isAuto
        ? (!currentPath || currentPath === 'auto')
        : ((currentPath.split('/').pop() || '') === wanted);
      job.stage = 'role';
      if (hasConversation && !sameAgent) sessionsHook.handleNewSession();
      bumpHomeJob();
      return;
    }

    if (job.stage === 'role') {
      if (job.roleId === 'auto') {
        job.stage = 'send';
        job.rolePath = 'auto';
        handleSelectManifesto({ name: 'Auto (Routing)', path: 'auto', exists: true, image: '/images/default.png' });
        bumpHomeJob();
        return;
      }
      if (!configHook.manifestos.length) return;
      const match = configHook.manifestos.find(m =>
        (m.filename || '').toLowerCase() === wanted ||
        (m.path || '').toLowerCase().endsWith(`/${wanted}`)
      );
      job.stage = 'send';
      if (match) {
        job.rolePath = match.path;
        handleSelectManifesto(match);
      }
      bumpHomeJob();
      return;
    }

    if (job.stage === 'send') {
      // La sincronizzazione sessione->ruolo puo' rimettere "auto" per un render:
      // si aspetta che il ruolo scelto sia quello attivo, con un limite di tempo.
      const roleReady = !job.rolePath || configHook.selectedManifestoPath === job.rolePath;
      if (!roleReady && Date.now() - job.since < 2000) {
        const retry = setTimeout(bumpHomeJob, 120);
        return () => clearTimeout(retry);
      }
      homeJobRef.current = null;
      if (!job.prompt) return;
      // Con una risposta gia' in corso il messaggio resta pronto nel campo invece di perdersi
      if (job.send && !streamingHook.loading) handleSendMessage(job.prompt);
      else streamingHook.setInput(job.prompt);
    }
  }, [homeJobTick, configHook.manifestos, configHook.selectedManifestoPath, sessionsHook.activeSessionId]);

  // Sync selected model and active manifesto when activeSessionId or selectedModel changes
  useEffect(() => {
    if (!sessionsHook.activeSessionId) return;
    const currentSession = sessionsHook.sessions.find(s => s.id === sessionsHook.activeSessionId);
    if (currentSession) {
      if (currentSession.model) {
        configHook.setSelectedModel(currentSession.model);
      }

      const manifestoPath = currentSession.manifestoPath || 'auto';
      const m = configHook.manifestos.find(x => x.path === manifestoPath || x.filename === manifestoPath.split('/').pop());
      if (m) {
        configHook.setActiveManifesto({
          name: m.name,
          path: m.path,
          exists: true,
          image: m.image || '/images/default.png'
        });
        configHook.setSelectedManifestoPath(m.path);
      } else if (manifestoPath === 'auto') {
        configHook.setActiveManifesto({
          name: 'auto',
          path: 'auto',
          exists: true,
          image: '/images/default.png'
        });
        configHook.setSelectedManifestoPath('auto');
      } else {
        const filename = manifestoPath.split('/').pop();
        let name = filename.replace('.md', '');
        if (name === 'sigma_architect' || name === 'agente0') name = 'Sigma AI Architect';
        configHook.setActiveManifesto({
          name: name,
          path: manifestoPath,
          exists: true,
          image: '/images/default.png'
        });
        configHook.setSelectedManifestoPath(manifestoPath);
      }
    } else {
      // Safe fallback if the current session is not yet loaded/found
      configHook.setActiveManifesto({
        name: 'auto',
        path: 'auto',
        exists: true,
        image: '/images/default.png'
      });
      configHook.setSelectedManifestoPath('auto');
    }
  }, [sessionsHook.activeSessionId, configHook.manifestos, configHook.selectedModel, sessionsHook.sessions]);

  // Sync state between config model selection and localStorage
  const handleModelSelectWrapped = async (name) => {
    await configHook.handleModelSelect(name);
  };

  const messages = sessionsHook.activeSessionId
    ? (sessionsHook.sessionMessages[sessionsHook.activeSessionId] || loadMessagesFromStorage(sessionsHook.activeSessionId) || [welcomeMessageObj])
    : [welcomeMessageObj];
  const currentRouting = getModelRoutingInfo(configHook.selectedModel, configHook.providerConfigs);

  // Stato dell'agente pubblicato per Home e plancia: e' la chat a sapere cosa sta facendo
  const activityStatus = deriveAgentActivity({ loading: streamingHook.loading, messages });
  const activeRoleFile = (configHook.activeManifesto?.path || '').split('/').pop() || '';
  const activeRoleMeta = configHook.manifestos.find(m => m.path === configHook.activeManifesto?.path);
  const agentActivity = useMemo(() => ({
    ...activityStatus,
    roleId: activeRoleFile.replace(/\.md$/i, ''),
    roleName: configHook.activeManifesto?.name === 'auto' ? 'Sigma' : (configHook.activeManifesto?.name || 'Sigma'),
    // Il centralino automatico non ha un volto: si presenta con il logo di Sigma Studio
    image: configHook.activeManifesto?.image && configHook.activeManifesto.image !== '/images/default.png'
      ? configHook.activeManifesto.image
      : (!configHook.activeManifesto?.name || configHook.activeManifesto.name === 'auto' ? '/images/SigmaStudio.png' : ''),
    color: activeRoleMeta?.domainColor || ''
  }), [activityStatus.state, activityStatus.tool, activityStatus.detail, activeRoleFile, configHook.activeManifesto?.name, configHook.activeManifesto?.image, activeRoleMeta?.domainColor]);

  const activitySourceRef = useRef(`chat-${Math.random().toString(36).slice(2, 8)}`);
  const activityBusyRef = useRef(false);
  const activityTimerRef = useRef(null);
  const [shownActivity, setShownActivity] = useState(agentActivity);

  // "Ha finito" ed "errore" durano qualche secondo e poi si torna a riposo:
  // sulla plancia un errore vecchio di ore non deve restare acceso.
  useEffect(() => {
    const source = activitySourceRef.current;
    const show = (activity) => {
      setShownActivity(activity);
      publishAgentActivity(source, activity);
    };
    const busy = !['idle', 'error'].includes(agentActivity.state);
    if (busy) {
      clearTimeout(activityTimerRef.current);
      activityTimerRef.current = null;
      activityBusyRef.current = true;
      show(agentActivity);
      return;
    }
    if (activityBusyRef.current) {
      activityBusyRef.current = false;
      show({ ...agentActivity, state: agentActivity.state === 'error' ? 'error' : 'done' });
      clearTimeout(activityTimerRef.current);
      activityTimerRef.current = setTimeout(() => {
        activityTimerRef.current = null;
        show({ ...agentActivity, state: 'idle', tool: '', detail: '' });
      }, 4500);
      return;
    }
    if (!activityTimerRef.current) show({ ...agentActivity, state: 'idle', tool: '', detail: '' });
  }, [agentActivity]);

  useEffect(() => {
    const source = activitySourceRef.current;
    return () => {
      clearTimeout(activityTimerRef.current);
      releaseAgentActivity(source);
    };
  }, []);
  const providerColors = PROVIDER_COLORS[currentRouting.provider] || { bg: '#333', color: '#ccc' };

  // Context Gauge calculation
  const numCtx = configHook.quickConfig.num_ctx || 32768;
  const messagesText = (messages || []).map(m => m.content || '').join('\n');
  const attachedText = (streamingHook.attachedFiles || []).map(f => {
    if (!f) return '';
    if (typeof f === 'string') return f;
    return f.content || f.filename || f.name || '';
  }).join('\n');
  const messagesTokens = Math.ceil(messagesText.length / 3.8);
  const attachedTokens = Math.ceil(attachedText.length / 3.8);
  const systemTokens = 1500;
  const usedTokens = Math.max(0, messagesTokens + attachedTokens + systemTokens);
  const contextPct = Math.min(100, Math.round((usedTokens / numCtx) * 100));
  const contextStats = { usedTokens, numCtx, pct: contextPct, messagesTokens, attachedTokens, systemTokens };

  const modelBtnRef = useRef(null);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  // Sync references for the parent layout components
  const combinedRefs = {
    ...sessionsHook.sessionRefs,
    ...configHook.configRefs,
    ...streamingHook.streamingRefs,
    messagesEnd: streamingHook.streamingRefs.messagesEnd || { current: null },
    input: inputRef,
    modelBtn: modelBtnRef,
    panel: panelRef,
    abort: streamingHook.streamingRefs.abort,
  };

  const handleDuplicateSession = useCallback((e, sid) => {
    sessionsHook.handleDuplicateSession(e, sid);
  }, [sessionsHook.handleDuplicateSession]);

  // Voice Command Audio Recording State
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);
  const initialInputRef = useRef('');

  // Wake-word microphone: 'off' | 'waiting' (listening for "Sigma") | 'listening'
  const [smartMicState, setSmartMicState] = useState('off');
  const smartMicRef = useRef(null);

  const stopSmartMic = useCallback(() => {
    if (smartMicRef.current) {
      smartMicRef.current.stop();
      smartMicRef.current = null;
    }
    setSmartMicState('off');
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsRecording(false);
      return;
    }

    // Chrome allows a single recognition session: the two microphones cannot
    // both hold it, so starting one releases the other.
    stopSmartMic();

    initialInputRef.current = streamingHook.input || '';

    const recognition = initSpeechRecognition({
      lang: 'it-IT',
      onResult: (accumulatedText) => {
        if (accumulatedText) {
          const prefix = initialInputRef.current ? initialInputRef.current.trim() : '';
          const newText = prefix ? `${prefix} ${accumulatedText}` : accumulatedText;
          streamingHook.setInput(newText);
        }
      },
      onError: (err) => {
        console.warn('SpeechRecognition error:', err);
        setIsRecording(false);
        if (addToast) addToast('⚠️ Errore durante la registrazione vocale.', 'warning');
      },
      onEnd: () => {
        setIsRecording(false);
      }
    });

    if (!recognition) {
      if (addToast) addToast('⚠️ Registrazione vocale non supportata dal browser.', 'warning');
      return;
    }

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setIsRecording(true);
      if (addToast) addToast('🎙️ Registrazione vocale avviata... Parla adesso!', 'info');
    } catch (err) {
      console.error('Start recognition error:', err);
      setIsRecording(false);
    }
  }, [isRecording, streamingHook.input, streamingHook.setInput, addToast, stopSmartMic]);

  const handleSendMessage = useCallback(async (textOverride, extraParams) => {
    if (smartMicRef.current && smartMicRef.current.isActive()) {
      smartMicRef.current.reset();
    }
    return streamingHook.sendMessage(textOverride, extraParams);
  }, [streamingHook.sendMessage]);

  const toggleSmartMic = useCallback(() => {
    if (smartMicRef.current) {
      stopSmartMic();
      if (addToast) addToast('🎙️ Microfono intelligente disattivato.', 'info');
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsRecording(false);
    }

    const mic = createWakeWordMic({
      onState: setSmartMicState,
      // Show the phrase as it is captured, so the user can see what was heard.
      onTranscript: (text) => streamingHook.setInput(text),
      onSubmit: (phrase) => {
        streamingHook.setInput(phrase);
        handleSendMessage(phrase);
      },
      onError: (code) => {
        console.warn('Wake-word mic error:', code);
        stopSmartMic();
        if (addToast) addToast(`⚠️ Microfono intelligente interrotto (${code}).`, 'warning');
      },
    });

    if (!mic) {
      if (addToast) addToast('⚠️ Riconoscimento vocale non supportato dal browser.', 'warning');
      return;
    }

    smartMicRef.current = mic;
    if (!mic.start()) {
      smartMicRef.current = null;
      return;
    }
    if (addToast) addToast('✨ Microfono intelligente attivo: Pronuncia "Sigma" ed inizia a fare la tua domanda!', 'info');
  }, [isRecording, streamingHook.setInput, handleSendMessage, addToast, stopSmartMic]);

  // Release the microphone when the chat unmounts.
  useEffect(() => () => {
    if (smartMicRef.current) smartMicRef.current.stop();
  }, []);

  const handleDeleteMessage = useCallback((msgIndexOrIndices) => {
    if (streamingHook.loading) {
      const currentMsgs = sessionsHook.sessionMessages[sessionsHook.activeSessionId] || [];
      const indices = Array.isArray(msgIndexOrIndices) ? msgIndexOrIndices : [msgIndexOrIndices];
      const isDeletingActive = indices.some(idx => idx === currentMsgs.length - 1 || currentMsgs[idx]?.loading);
      if (isDeletingActive) {
        streamingHook.stopInference();
      }
    }
    return sessionsHook.deleteMessage(msgIndexOrIndices);
  }, [sessionsHook, streamingHook]);

  return {
    // --- States ---
    sessions: sessionsHook.sessions,
    activeSessionId: sessionsHook.activeSessionId,
    sessionMessages: sessionsHook.sessionMessages,
    messages,
    agentActivity: shownActivity,
    input: streamingHook.input,
    setInput: streamingHook.setInput,
    loading: streamingHook.loading,
    setLoading: streamingHook.setLoading,
    selectedModel: configHook.selectedModel,
    setSelectedModel: configHook.setSelectedModel,
    speakerEnabled,
    setSpeakerEnabled,
    isRecording,
    onToggleRecording: toggleRecording,
    smartMicState,
    onToggleSmartMic: toggleSmartMic,
    configModel: configHook.configModel,
    configProvider: configHook.configProvider,
    availableModels: configHook.availableModels,
    loadingModels: configHook.loadingModels,
    providerConfigs: configHook.providerConfigs,
    activeMode: streamingHook.activeMode,
    setActiveMode: streamingHook.setActiveMode,
    actionsLog: streamingHook.actionsLog,
    setActionsLog: streamingHook.setActionsLog,
    attachedFiles: streamingHook.attachedFiles,
    setAttachedFiles: streamingHook.setAttachedFiles,
    pcFiles: streamingHook.pcFiles,
    setPcFiles: streamingHook.setPcFiles,
    dragOver: streamingHook.dragOver,
    expandedThinking: streamingHook.expandedThinking,
    setExpandedThinking: streamingHook.setExpandedThinking,
    autoScroll: streamingHook.autoScroll,
    setAutoScroll: streamingHook.setAutoScroll,
    mcpAutoApprove: mcpApproval.mcpAutoApprove,
    setMcpAutoApprove: mcpApproval.setMcpAutoApprove,
    webSearch: streamingHook.webSearch,
    setWebSearch: streamingHook.setWebSearch,
    quickConfig: configHook.quickConfig,
    setQuickConfig: configHook.setQuickConfig,
    showQuickConfig: configHook.showQuickConfig,
    setShowQuickConfig: configHook.setShowQuickConfig,
    selectedHardware: configHook.selectedHardware,
    setSelectedHardware: configHook.setSelectedHardware,
    availableHardware: configHook.availableHardware,
    activeManifesto: configHook.activeManifesto,
    setActiveManifesto: configHook.setActiveManifesto,
    manifestos: configHook.manifestos,
    selectedManifestoPath: configHook.selectedManifestoPath,
    setSelectedManifestoPath: configHook.setSelectedManifestoPath,
    manifestoManuallySelected: configHook.manifestoManuallySelected,
    setManifestoManuallySelected: configHook.setManifestoManuallySelected,
    showManifestoDropdown: configHook.showManifestoDropdown,
    setShowManifestoDropdown: configHook.setShowManifestoDropdown,
    loopMaxIterations: streamingHook.loopMaxIterations,
    setLoopMaxIterations: streamingHook.setLoopMaxIterations,
    loopIteration: streamingHook.loopIteration,
    setLoopIteration: streamingHook.setLoopIteration,
    loopActive: streamingHook.loopActive,
    setLoopActive: streamingHook.setLoopActive,
    actionStrategy: streamingHook.actionStrategy,
    setActionStrategy: streamingHook.setActionStrategy,
    actionMaxReadIterations: streamingHook.actionMaxReadIterations,
    setActionMaxReadIterations: streamingHook.setActionMaxReadIterations,
    actionMaxTotalReads: streamingHook.actionMaxTotalReads,
    setActionMaxTotalReads: streamingHook.setActionMaxTotalReads,
    autoApprove: streamingHook.autoApprove,
    setAutoApprove: streamingHook.setAutoApprove,
    currentPlan: streamingHook.currentPlan,
    setCurrentPlan: streamingHook.setCurrentPlan,
    planExecuting: streamingHook.planExecuting,
    setPlanExecuting: streamingHook.setPlanExecuting,
    showHistory: streamingHook.showHistory,
    setShowHistory: streamingHook.setShowHistory,
    favoriteModel: configHook.favoriteModel,
    favoriteModels: configHook.favoriteModels,
    handleSetFavoriteModel: configHook.handleSetFavoriteModel,
    handleToggleFavoriteModel: configHook.handleToggleFavoriteModel,
    showModelDropdown: configHook.showModelDropdown,
    setShowModelDropdown: configHook.setShowModelDropdown,
    editingSessionName: sessionsHook.editingSessionName,
    editNameValue: sessionsHook.editNameValue,
    setEditNameValue: sessionsHook.setEditNameValue,
    showFilePicker: streamingHook.showFilePicker,
    setShowFilePicker: streamingHook.setShowFilePicker,
    refs: combinedRefs,
    currentRouting,
    providerColors,
    contextStats,
    maxTaskIterations: 10,
    devModeAvailable: devModeHook.devModeAvailable,
    devModeEnabled: devModeHook.devModeEnabled,
    setDevModeEnabled: devModeHook.setDevModeEnabled,
    devRoles: devModeHook.devRoles,
    devRole: devModeHook.devRole,
    setDevRole: devModeHook.setDevRole,
    devModeWorkspaceRoot: devModeHook.workspaceRoot,

    // --- Actions ---
    sendMessage: handleSendMessage,
    stopInference: streamingHook.stopInference,
    switchToSession: sessionsHook.switchToSession,
    handleNewSession: sessionsHook.handleNewSession,
    handleDeleteSession: sessionsHook.handleDeleteSession,
    handleStartRename: sessionsHook.handleStartRename,
    handleFinishRename: sessionsHook.handleFinishRename,
    handleRenameKeyDown: sessionsHook.handleRenameKeyDown,
    deleteMessage: handleDeleteMessage,
    handleModelSelect: handleModelSelectWrapped,
    handleSetFavorite: configHook.handleSetFavoriteModel,
    handleSelectManifesto,
    handleDuplicateSession,
    openModelDropdown: () => {
      configHook.setShowModelDropdown(prev => !prev);
    },
    removePcFile: streamingHook.removePcFile,
    removeAttachedFile: streamingHook.removeAttachedFile,
    handleDragEnter: streamingHook.handleDragEnter,
    handleDragOver: streamingHook.handleDragOver,
    handleDragLeave: streamingHook.handleDragLeave,
    handleDrop: streamingHook.handleDrop,
    saveQuickConfig: configHook.saveQuickConfig,
    refreshConfig: configHook.refreshConfig,
    fetchOllamaModels: configHook.fetchOllamaModels,
    saveSessionsState: sessionsHook.saveSessionsState,
  };
}