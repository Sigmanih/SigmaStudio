import React from 'react';
import useChatCore from '../core/useChatCore';
import ChatHeader from '../ui/ChatHeader';
import ChatMessages from '../ui/ChatMessages';
import ChatInput from '../ui/ChatInput';
import ChatHistory from '../ChatHistory';
import FilePicker from '../FilePicker';
import ActionsBar from '../ActionsBar';
import QuickConfigPanel from '../ui/QuickConfigPanel';

export default function ChatWorkspaceTab() {
  const core = useChatCore({});


  const groupedSessions = core.sessions.reduce((acc, s) => {
    const diff = new Date() - new Date(s.updatedAt);
    const days = Math.floor(diff / 86400000);
    const l = days === 0 ? 'Oggi' : days === 1 ? 'Ieri' : days < 7 ? `${days} giorni fa` : new Date(s.updatedAt).toLocaleDateString();
    if (!acc[l]) acc[l] = [];
    acc[l].push(s);
    return acc;
  }, {});

  return (
    <div className="chat-workspace-root">
      <ChatHeader
        isPanel={false}
        selectedModel={core.selectedModel}
        availableModels={core.availableModels}
        loadingModels={core.loadingModels}
        showModelDropdown={core.showModelDropdown}
        onToggleDropdown={core.openModelDropdown}
        onSelectModel={core.handleModelSelect}
        providerConfigs={core.providerConfigs}
        modelBtnRef={core.refs.modelBtn}
        activeManifesto={core.activeManifesto}
        manifestos={core.manifestos}
        showManifestoDropdown={core.showManifestoDropdown}
        setShowManifestoDropdown={core.setShowManifestoDropdown}
        onSelectManifesto={core.handleSelectManifesto}
        onOpenQuickConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        showQuickConfig={core.showQuickConfig}
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
        <ChatHistory
          showHistory={core.showHistory}
          onToggle={() => core.setShowHistory(!core.showHistory)}
          sessions={core.sessions}
          groupedSessions={groupedSessions}
          activeSessionId={core.activeSessionId}
          onSwitchSession={core.switchToSession}
          editingSessionName={core.editingSessionName}
          editNameValue={core.editNameValue}
          onEditNameChange={core.setEditNameValue}
          onFinishRename={core.handleFinishRename}
          onKeyDown={core.handleRenameKeyDown}
          onStartRename={core.handleStartRename}
          onDeleteSession={core.handleDeleteSession}
          onNewSession={core.handleNewSession}
          onDuplicateSession={core.handleDuplicateSession}
        />
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
        refs={core.refs}
        providerColors={core.providerColors}
        currentRouting={core.currentRouting}
        webSearch={core.webSearch}
        setWebSearch={core.setWebSearch}
        autoScroll={core.autoScroll}
        setAutoScroll={core.setAutoScroll}
        speakerEnabled={core.speakerEnabled}
        setSpeakerEnabled={core.setSpeakerEnabled}
        isRecording={core.isRecording}
        onToggleRecording={core.onToggleRecording}
        loopMaxIterations={core.loopMaxIterations}
        setLoopMaxIterations={core.setLoopMaxIterations}
        loopActive={core.loopActive}
        onSend={core.sendMessage}
        onStop={core.stopInference}
        onOpenFilePicker={() => core.setShowFilePicker(true)}
        attachedFiles={core.attachedFiles}
      />

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