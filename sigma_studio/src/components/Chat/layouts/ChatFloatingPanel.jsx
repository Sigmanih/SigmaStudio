import React, { useCallback } from 'react';
import useChatCore from '../core/useChatCore';
import ChatHeader from '../ui/ChatHeader';
import ChatMessages from '../ui/ChatMessages';
import ChatInput from '../ui/ChatInput';
import ChatHistory from '../ChatHistory';
import FilePicker from '../FilePicker';
import ActionsBar from '../ActionsBar';
import QuickConfigPanel from '../ui/QuickConfigPanel';
import useChatResize from '../useChatResize';
import useChatDrag from '../useChatDrag';

export default function ChatFloatingPanel({ openFiles, onClose, onOpenConfig, onTasksUpdated, addToast }) {
  const core = useChatCore({ openFiles, onTasksUpdated, addToast });
  const { panelPos, setPanelPos, isDragging, startDrag } = useChatDrag({ width: 800, height: 600 });
  const { panelSize, resizing, resizeHandles, handleResizeStart } = useChatResize(panelPos, setPanelPos);

  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  const safeX = panelPos?.x;
  const safeY = panelPos?.y;
  const panelStyle = isMobile ? {} : {
    ...(safeX !== undefined ? { left: safeX, right: 'auto' } : { right: 24 }),
    ...(safeY !== undefined ? { bottom: 'auto', top: safeY } : { bottom: 80 }),
    width: panelSize.width, height: panelSize.height,
  };




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
        onNewSession={handleNewSession}
        onOpenConfig={onOpenConfig}
        onClose={onClose}
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

      <div className="chat-body" style={{ flex: 1, minHeight: 0 }}>
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
        onOpenConfig={onOpenConfig}
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