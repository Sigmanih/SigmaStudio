import React from 'react';
import useChatCore from '../core/useChatCore';
import ChatHeader from '../ui/ChatHeader';
import ChatMessages from '../ui/ChatMessages';
import ChatInput from '../ui/ChatInput';
import ChatHistory from '../ChatHistory';
import FilePicker from '../FilePicker';
import ActionsBar from '../ActionsBar';

export default function ChatWorkspaceTab() {
  const core = useChatCore({});

  const handleSelectManifesto = (m) => {
    const manifesto = { name: m.name, path: m.path, exists: true, image: m.image || '/images/default.png' };
    core.setActiveManifesto(manifesto);
    core.setSelectedManifestoPath(m.path);
    core.setManifestoManuallySelected(true);
    core.setShowManifestoDropdown(false);
    try { localStorage.setItem('sigma_selected_manifesto', JSON.stringify(manifesto)); } catch (e) {}
  };

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
        onSelectManifesto={handleSelectManifesto}
        onOpenQuickConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        showQuickConfig={core.showQuickConfig}
      />

      {core.showQuickConfig && (
        <div className="chat-quick-config">
          <div className="chat-quick-config-grid">
            {[
              { label: '🌡️ Temp', key: 'temperature', min: 0, max: 2, step: 0.05, type: 'range' },
              { label: '🎯 Top P', key: 'top_p', min: 0, max: 1, step: 0.05, type: 'range' },
              { label: '🔝 Top K', key: 'top_k', min: 1, max: 100, step: 1, type: 'range' },
              { label: '🔁 RPen', key: 'repeat_penalty', min: 0, max: 2, step: 0.05, type: 'range' },
            ].map(cfg => (
              <div key={cfg.key} className="qc-item">
                <div className="qc-label">{cfg.label}</div>
                <input type={cfg.type} min={cfg.min} max={cfg.max} step={cfg.step}
                  value={core.quickConfig[cfg.key]}
                  onChange={e => core.setQuickConfig(prev => ({ ...prev, [cfg.key]: parseFloat(e.target.value) }))} />
              </div>
            ))}
            <div className="qc-item">
              <div className="qc-label">📝 MaxT</div>
              <select className="qc-select" value={core.quickConfig.max_tokens}
                onChange={e => core.setQuickConfig(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}>
                {[512, 1024, 2048, 4096, 8192, 16384, 32768].map(v => <option key={v} value={v}>{v >= 1024 ? `${v/1024}K` : v}</option>)}
              </select>
            </div>
            <div className="qc-item">
              <div className="qc-label">🧠 Ctx</div>
              <select className="qc-select" value={core.quickConfig.num_ctx}
                onChange={e => core.setQuickConfig(prev => ({ ...prev, num_ctx: parseInt(e.target.value) }))}>
                {[2048, 4096, 8192, 16384, 32768, 65536, 131072].map(v => <option key={v} value={v}>{v >= 1024 ? `${v/1024}K` : v}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

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
        />
        <ChatMessages
          messages={core.messages}
          loading={core.loading}
          actionsLog={core.actionsLog}
          expandedThinking={core.expandedThinking}
          onToggleThinking={(id) => core.setExpandedThinking(prev => ({ ...prev, [id]: !prev[id] }))}
          selectedModel={core.selectedModel}
          refs={core.refs}
          onStop={core.stopInference}
          activeManifesto={core.activeManifesto}
          manifestos={core.manifestos}
        />
      </div>

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