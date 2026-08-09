// ==============================================================================
// useChatCore.js — Central hook orchestrating refactored composite hooks
// Sigma Studio v7 — Refactored to compose useChatSessions, useChatConfig & useChatStreaming
// ==============================================================================
import { useEffect, useCallback, useState, useRef } from 'react';
import { PROVIDER_COLORS, getModelRoutingInfo } from '../modelProviderMap';
import { loadMessagesFromStorage, saveMessagesToStorage, createSession } from '../chatStorage';
import { initSpeechRecognition, createWakeWordMic, stopSpeech } from '../audioSpeech';
const saveMessagesImmediately = saveMessagesToStorage;


// Import composite hooks
import { useChatSessions } from './useChatSessions';
import { useChatConfig } from './useChatConfig';
import { useChatStreaming } from './useChatStreaming';
import { useMcpAutoApprove } from './useMcpAutoApprove';

export default function useChatCore(extraProps = {}) {
  const { openFiles: externalOpenFiles, onTasksUpdated, addToast } = extraProps;
  
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
    content: '# 🤖 Sigma AI Studio\n\nChat pronta.',
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
    providerConfigs: configHook.providerConfigs,
    quickConfig: configHook.quickConfig,
    selectedManifestoPath: configHook.selectedManifestoPath,
    fetchOllamaModels: configHook.fetchOllamaModels,
    refreshConfig: configHook.refreshConfig,
    activeManifesto: configHook.activeManifesto
  });

  // Interruttore Auto Approve: stato condiviso con la tab MCP Tools.
  const mcpApproval = useMcpAutoApprove();

  // Connect actions log back to sessions switch
  sessionsHook.setActionsLog = streamingHook.setActionsLog;

  // Sync back actual selected model to sessions init (first load)
  useEffect(() => {
    if (sessionsHook.sessions.length > 0 && !sessionsHook.activeSessionId) {
      const sid = sessionsHook.sessions[0].id;
      const stored = loadMessagesFromStorage(sid);
      if (stored) {
        sessionsHook.setSessionMessages(prev => ({ ...prev, [sid]: stored }));
      }
      sessionsHook.setActiveSessionId(sid);
      if (sessionsHook.sessions[0].model) configHook.setSelectedModel(sessionsHook.sessions[0].model);
    }
  }, [sessionsHook.sessions, sessionsHook.activeSessionId]);

  // Load configuration, models and manifestos on mount
  useEffect(() => {
    configHook.fetchConfigAndModels();
    configHook.fetchManifestos();
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

  const messages = sessionsHook.activeSessionId ? (sessionsHook.sessionMessages[sessionsHook.activeSessionId] || []) : [];
  const currentRouting = getModelRoutingInfo(configHook.selectedModel, configHook.providerConfigs);
  const providerColors = PROVIDER_COLORS[currentRouting.provider] || { bg: '#333', color: '#ccc' };

  // Context Gauge calculation
  const numCtx = configHook.quickConfig.num_ctx || 32768;
  const messagesText = (messages || []).map(m => m.content || '').join('\n');
  const attachedText = (streamingHook.attachedFiles || []).map(f => f.content || '').join('\n');
  const messagesTokens = Math.ceil(messagesText.length / 3.8);
  const attachedTokens = Math.ceil(attachedText.length / 3.8);
  const systemTokens = 1500;
  const usedTokens = Math.max(0, messagesTokens + attachedTokens + systemTokens);
  const contextPct = Math.min(100, Math.round((usedTokens / numCtx) * 100));
  const contextStats = { usedTokens, numCtx, pct: contextPct, messagesTokens, attachedTokens, systemTokens };

  // Sync references for the parent layout components
  const combinedRefs = {
    ...sessionsHook.sessionRefs,
    ...configHook.configRefs,
    ...streamingHook.streamingRefs,
    messagesEnd: streamingHook.streamingRefs.messagesEnd || { current: null },
    input: { current: null },
    modelBtn: { current: null },
    panel: { current: null },
    abort: streamingHook.streamingRefs.abort,
  };

  const handleDuplicateSession = useCallback(() => {
    const activeModel = configHook.selectedModel || '';
    const activeName = sessionsHook.sessions.find(s => s.id === sessionsHook.activeSessionId)?.name || 'Chat';
    const dup = createSession(activeModel, 'Copia di ' + activeName);
    const msgs = sessionsHook.activeSessionId ? (sessionsHook.sessionMessages[sessionsHook.activeSessionId] || []) : [];
    
    sessionsHook.setSessionMessages(prev => ({ ...prev, [dup.id]: [...msgs] }));
    saveMessagesImmediately(dup.id, [...msgs]);
    const updated = [dup, ...sessionsHook.sessions].slice(0, 25);
    sessionsHook.saveSessionsState(updated);
    sessionsHook.setActiveSessionId(dup.id);
  }, [configHook.selectedModel, sessionsHook.activeSessionId, sessionsHook.sessions, sessionsHook.sessionMessages, sessionsHook.saveSessionsState, sessionsHook.setSessionMessages, sessionsHook.setActiveSessionId]);

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
    handleSelectManifesto,
    handleDuplicateSession,
    openModelDropdown: async () => {
      await configHook.refreshConfig();
      await configHook.fetchOllamaModels();
      configHook.setShowModelDropdown(!configHook.showModelDropdown);
    },
    removePcFile: streamingHook.removePcFile,
    handleDragOver: streamingHook.handleDragOver,
    handleDragLeave: streamingHook.handleDragLeave,
    handleDrop: streamingHook.handleDrop,
    saveQuickConfig: configHook.saveQuickConfig,
    refreshConfig: configHook.refreshConfig,
    fetchOllamaModels: configHook.fetchOllamaModels,
    saveSessionsState: sessionsHook.saveSessionsState,
  };
}