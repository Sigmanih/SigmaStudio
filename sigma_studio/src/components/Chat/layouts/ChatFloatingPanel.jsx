import React, { useCallback } from 'react';
import useChatCore from '../core/useChatCore';
import ChatHeader from '../ui/ChatHeader';
import ChatMessages from '../ui/ChatMessages';
import ChatInput from '../ui/ChatInput';
import ChatHistory from '../ChatHistory';
import FilePicker from '../FilePicker';
import ActionsBar from '../ActionsBar';
import { createSession } from '../chatStorage';
import useChatResize from '../useChatResize';
import useChatDrag from '../useChatDrag';

export default function ChatFloatingPanel({ openFiles, onClose, onOpenConfig, onTasksUpdated, addToast }) {
  const core = useChatCore({ openFiles, onTasksUpdated, addToast });
  const { panelPos, setPanelPos, isDragging, startDrag } = useChatDrag({ width: 800, height: 600 });
  const { panelSize, resizing, resizeHandles, handleResizeStart } = useChatResize(panelPos, setPanelPos);

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x) && panelPos.x > -500) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y) && panelPos.y > 0) ? panelPos.y : undefined;
  const panelStyle = {
    ...(safeX !== undefined ? { left: safeX, right: 'auto' } : { right: 24 }),
    ...(safeY !== undefined ? { bottom: 'auto', top: safeY } : { bottom: 80 }),
    width: panelSize.width, height: panelSize.height,
  };

  const handleDeleteMsg = useCallback((i) => {
    const sid = core.activeSessionId;
    core.setMessagesForSession(sid, prev => {
      const newMsgs = prev.filter((_, j) => j !== i);
      core.saveMessagesImmediately(sid, newMsgs);
      return newMsgs;
    });
  }, [core.activeSessionId]);

  const handleDuplicateSession = useCallback(() => {
    const dup = createSession(core.selectedModel, 'Copia di ' + (core.sessions.find(s => s.id === core.activeSessionId)?.name || 'Chat'));
    const msgs = [...core.messages];
    core.setSessionMessages(prev => ({ ...prev, [dup.id]: msgs }));
    core.saveMessagesImmediately(dup.id, msgs);
    const updated = [dup, ...core.sessions].slice(0, 25);
    core.saveSessionsState(updated);
    core.setActiveSessionId(dup.id);
  }, [core.selectedModel, core.activeSessionId, core.sessions, core.messages]);

  const groupedSessions = (() => {
    if (core.sessions.length === 0) return {};
    const g = {};
    core.sessions.forEach(s => {
      const diff = new Date() - new Date(s.updatedAt);
      const days = Math.floor(diff / 86400000);
      const l = days === 0 ? 'Oggi' : days === 1 ? 'Ieri' : days < 7 ? `${days} giorni fa` : new Date(s.updatedAt).toLocaleDateString();
      if (!g[l]) g[l] = [];
      g[l].push(s);
    });
    return g;
  })();

  return (
    <div
      className={`ai-chat-panel ${resizing ? 'is-resizing' : ''} ${core.dragOver ? 'drag-over' : ''}`}
      ref={core.refs.panel}
      style={{ ...panelStyle, pointerEvents: 'auto' }}
      onDragOver={core.handleDragOver}
      onDragLeave={core.handleDragLeave}
      onDrop={core.handleDrop}
    >
      {resizeHandles.map(rh => (
        <div key={rh.dir} className={`chat-resize-handle ${rh.className}`} style={{ cursor: rh.cursor }}
          onMouseDown={(e) => handleResizeStart(rh.dir, e)} />
      ))}

      <ChatHeader
        isPanel={true}
        isDragging={isDragging}
        onStartDrag={startDrag}
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
        onDuplicateSession={handleDuplicateSession}
        onOpenQuickConfig={() => core.setShowQuickConfig(!core.showQuickConfig)}
        showQuickConfig={core.showQuickConfig}
        onOpenConfig={onOpenConfig}
        onClose={onClose}
      />

      <div className="chat-body">
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
          onDeleteMessage={handleDeleteMsg}
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

      {core.dragOver && <div className="chat-drop-overlay"><div>📤 Trascina i file qui per allegarli</div></div>}
      {core.showFilePicker && (
        <FilePicker
          onSelect={(selected, pcFilesResult) => {
            core.setAttachedFiles(selected);
            if (pcFilesResult) core.setPcFiles(pcFilesResult);
            core.setShowFilePicker(false);
          }}
          onClose={() => core.setShowFilePicker(false)}
          attachedFiles={core.attachedFiles}
          pcFiles={core.pcFiles}
          onPcFilesChange={core.setPcFiles}
        />
      )}
    </div>
  );
}