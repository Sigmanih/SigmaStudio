// ==============================================================================
// useChatCore.js — Central hook orchestrating refactored composite hooks
// Sigma Studio v7 — Refactored to compose useChatSessions, useChatConfig & useChatStreaming
// ==============================================================================
import { useEffect, useCallback } from 'react';
import { PROVIDER_COLORS, getModelRoutingInfo } from '../modelProviderMap';
import { loadMessagesFromStorage, saveMessagesToStorage } from '../chatStorage';
const saveMessagesImmediately = saveMessagesToStorage;


// Import composite hooks
import { useChatSessions } from './useChatSessions';
import { useChatConfig } from './useChatConfig';
import { useChatStreaming } from './useChatStreaming';

export default function useChatCore(extraProps = {}) {
  const { openFiles: externalOpenFiles, onTasksUpdated, addToast } = extraProps;
  
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

  // Sync selected model and active manifesto when activeSessionId changes
  useEffect(() => {
    if (!sessionsHook.activeSessionId) return;
    const currentSession = sessionsHook.sessions.find(s => s.id === sessionsHook.activeSessionId);
    if (currentSession) {
      if (currentSession.model) {
        configHook.setSelectedModel(currentSession.model);
      }

      const manifestoPath = currentSession.manifestoPath || 'manifesti/sigma_architect.md';
      const m = configHook.manifestos.find(x => x.path === manifestoPath || x.filename === manifestoPath.split('/').pop());
      if (m) {
        configHook.setActiveManifesto({
          name: m.name,
          path: m.path,
          exists: true,
          image: m.image || '/images/default.png'
        });
        configHook.setSelectedManifestoPath(m.path);
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
    }
  }, [sessionsHook.activeSessionId, configHook.manifestos]);

  // Sync state between config model selection and localStorage
  const handleModelSelectWrapped = async (name) => {
    await configHook.handleModelSelect(name);
  };

  const messages = sessionsHook.activeSessionId ? (sessionsHook.sessionMessages[sessionsHook.activeSessionId] || []) : [];
  const currentRouting = getModelRoutingInfo(configHook.selectedModel, configHook.providerConfigs);
  const providerColors = PROVIDER_COLORS[currentRouting.provider] || { bg: '#333', color: '#ccc' };

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
    maxTaskIterations: 10,

    // --- Actions ---
    sendMessage: streamingHook.sendMessage,
    stopInference: streamingHook.stopInference,
    switchToSession: sessionsHook.switchToSession,
    handleNewSession: sessionsHook.handleNewSession,
    handleDeleteSession: sessionsHook.handleDeleteSession,
    handleStartRename: sessionsHook.handleStartRename,
    handleFinishRename: sessionsHook.handleFinishRename,
    handleRenameKeyDown: sessionsHook.handleRenameKeyDown,
    handleModelSelect: handleModelSelectWrapped,
    handleSelectManifesto,
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