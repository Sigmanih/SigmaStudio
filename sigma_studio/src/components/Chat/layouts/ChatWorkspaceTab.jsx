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

  return (
    <div className="chat-workspace-root">
      {/* Hero Visual Banner with Standardized Theme System & Dimensions */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: theme === 'light' ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: theme === 'light'
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/chat_swarm_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/chat_swarm_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: theme === 'light' ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <MessageSquare size={14} /> SWARM AGENTS & MULTI-MODEL CHAT
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: theme === 'light' ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              💬 Chat Swarm & <span style={{
                color: theme === 'light' ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Assistente AI</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: theme === 'light' ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Assistente agentico multi-modello con controlli TTS, memoria episodica e bus strumenti MCP Hub.
            </p>
          </div>

          {/* Action Buttons on the Right */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={core.handleNewSession}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: theme === 'light' ? '#ea580c' : '#00d2ff',
                color: theme === 'light' ? '#fff' : '#0a0d14',
                border: 'none',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                boxShadow: theme === 'light' ? '0 4px 14px rgba(234, 88, 12, 0.25)' : '0 4px 16px rgba(0, 210, 255, 0.3)'
              }}
            >
              + Nuova Conversazione
            </button>
            <button
              onClick={() => core.setShowHistory(!core.showHistory)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: theme === 'light' ? '#fffdf9' : '#181b28',
                color: theme === 'light' ? '#111' : '#fff',
                border: theme === 'light' ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              📜 Cronologia Sessioni
            </button>
          </div>
        </div>
      </div>
      <ChatHeader
        isPanel={false}
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