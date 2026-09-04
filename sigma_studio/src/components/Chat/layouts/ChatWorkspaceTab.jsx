import React from 'react';
import { MessageSquare } from 'lucide-react';
import { useApp } from '../../../contexts/AppContext';
import useChatCore from '../core/useChatCore';
import ChatHeader from '../ui/ChatHeader';
import ChatMessages from '../ui/ChatMessages';
import ChatInput from '../ui/ChatInput';
import ChatHistory from '../ChatHistory';
import FilePicker from '../FilePicker';
import ActionsBar from '../ActionsBar';
import QuickConfigPanel from '../ui/QuickConfigPanel';

export default function ChatWorkspaceTab() {
  const { theme } = useApp();
  const core = useChatCore({});


  const groupedSessions = core.sessions.reduce((acc, s) => {
    const diff = new Date() - new Date(s.updatedAt);
    const days = Math.floor(diff / 86400000);
    const l = days === 0 ? 'Oggi' : days === 1 ? 'Ieri' : days < 7 ? `${days} giorni fa` : new Date(s.updatedAt).toLocaleDateString();
    if (!acc[l]) acc[l] = [];
    acc[l].push(s);
    return acc;
  }, {});

  const handleSwitchSession = (sessionId) => {
    core.switchToSession(sessionId);
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      core.setShowHistory(false);
    }
  };

  const handleNewSession = () => {
    core.handleNewSession();
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      core.setShowHistory(false);
    }
  };

  return (
    <div className="chat-workspace-root">
      {/* Minimal Chat AI Header */}
      <ChatHeader
        isPanel={false}
        onNewSession={handleNewSession}
        onOpenConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        contextStats={core.contextStats}
        onCopyAll={() => {
          const msgs = core.messages || [];
          if (msgs.length === 0) return;
          const formatted = msgs.map(m => {
            const role = m.role === 'user' ? '👤 Tu' : `🤖 ${m.agentRole || m.agentName || 'AI'}`;
            const text = m.content || m.thinking || '';
            return `${role}:\n${text}`;
          }).join('\n\n---\n\n');
          navigator.clipboard.writeText(formatted);
        }}
      />

      <div className="chat-workspace-body">
        {core.showHistory && (
          <ChatHistory
            showHistory={core.showHistory}
            onToggle={() => core.setShowHistory(!core.showHistory)}
          sessions={core.sessions}
          groupedSessions={groupedSessions}
          sessionMessages={core.sessionMessages}
          activeSessionId={core.activeSessionId}
          onSwitchSession={handleSwitchSession}
          editingSessionName={core.editingSessionName}
          editNameValue={core.editNameValue}
          onEditNameChange={core.setEditNameValue}
          onFinishRename={core.handleFinishRename}
          onKeyDown={core.handleRenameKeyDown}
          onStartRename={core.handleStartRename}
          onDeleteSession={core.handleDeleteSession}
          onNewSession={handleNewSession}
          onDuplicateSession={core.handleDuplicateSession}
        />
        )}
        <ChatMessages
          messages={core.messages}
          loading={core.loading}
          actionsLog={core.actionsLog}
          expandedThinking={core.expandedThinking}
          onToggleThinking={(id) => core.setExpandedThinking(prev => ({ ...prev, [id]: !prev[id] }))}
          selectedModel={core.selectedModel}
          onDeleteMessage={core.deleteMessage}
          refs={core.refs}
          onStop={core.stopInference}
          activeManifesto={core.activeManifesto}
          manifestos={core.manifestos}
          autoScroll={core.autoScroll}
          setAutoScroll={core.setAutoScroll}
        />
      </div>

      {core.showQuickConfig && (
        <QuickConfigPanel
          quickConfig={core.quickConfig}
          setQuickConfig={core.setQuickConfig}
          onClose={() => core.setShowQuickConfig(false)}
          selectedModel={core.selectedModel}
          onSelectModel={core.handleModelSelect}
          availableModels={core.availableModels}
          activeManifesto={core.activeManifesto}
          onSelectManifesto={core.handleSelectManifesto}
          manifestos={core.manifestos}
        />
      )}

      <ActionsBar
        activeMode={core.activeMode}
        onSetMode={core.setActiveMode}
        availableTasks={[]}
        onExecuteTask={() => {}}
        executingAll={false}
        onExecuteAll={() => {}}
        taskDone={0}
        taskTotal={0}
        taskProgress={0}
        maxTaskIterations={core.maxTaskIterations}
        contextStats={core.contextStats}
        onOpenQuickConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        showQuickConfig={core.showQuickConfig}
      />

      <ChatInput
        input={core.input}
        setInput={core.setInput}
        loading={core.loading}
        selectedModel={core.selectedModel}
        availableModels={core.availableModels}
        loadingModels={core.loadingModels}
        showModelDropdown={core.showModelDropdown}
        onToggleModelDropdown={core.openModelDropdown}
        onSelectModel={core.handleModelSelect}
        providerConfigs={core.providerConfigs}
        modelBtnRef={core.refs.modelBtn}
        favoriteModel={core.favoriteModel}
        favoriteModels={core.favoriteModels}
        onSetFavoriteModel={core.handleSetFavoriteModel}
        activeManifesto={core.activeManifesto}
        manifestos={core.manifestos}
        showManifestoDropdown={core.showManifestoDropdown}
        setShowManifestoDropdown={core.setShowManifestoDropdown}
        onSelectManifesto={core.handleSelectManifesto}
        onOpenConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        refs={core.refs}
        providerColors={core.providerColors}
        currentRouting={core.currentRouting}
        autoScroll={core.autoScroll}
        setAutoScroll={core.setAutoScroll}
        mcpAutoApprove={core.mcpAutoApprove}
        setMcpAutoApprove={core.setMcpAutoApprove}
        speakerEnabled={core.speakerEnabled}
        setSpeakerEnabled={core.setSpeakerEnabled}
        isRecording={core.isRecording}
        onToggleRecording={core.onToggleRecording}
        smartMicState={core.smartMicState}
        onToggleSmartMic={core.onToggleSmartMic}
        loopMaxIterations={core.loopMaxIterations}
        setLoopMaxIterations={core.setLoopMaxIterations}
        loopActive={core.loopActive}
        onSend={core.sendMessage}
        onStop={core.stopInference}
        onOpenFilePicker={() => core.setShowFilePicker(true)}
        attachedFiles={core.attachedFiles}
      />

      {/* File Picker Modal */}
      {core.showFilePicker && (
        <FilePicker
          onSelect={(selected) => { core.setAttachedFiles(selected); core.setShowFilePicker(false); }}
          onClose={() => core.setShowFilePicker(false)}
          attachedFiles={core.attachedFiles}
        />
      )}
    </div>
  );
}