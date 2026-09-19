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
import { exportChatPdf } from '../../../utils/exportChatPdf';
import { loadMessagesFromStorage } from '../chatStorage';

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
            const parts = [];

            // 1. Ragionamento / Thinking
            if (m.thinking && typeof m.thinking === 'string' && m.thinking.trim()) {
              parts.push(`💭 RAGIONAMENTO:\n${m.thinking.trim()}`);
            }

            // 2. Div Azioni / Tools
            const tools = m.tools || m.tool_calls || m.actions || [];
            if (Array.isArray(tools) && tools.length > 0) {
              const toolLines = tools.map((t, i) => {
                const name = t.name || t.tool || `Tool #${i + 1}`;
                const args = t.arguments || t.args || t.input;
                const argsStr = args ? (typeof args === 'string' ? args : JSON.stringify(args)) : '';
                const result = t.output || t.result || t.response;
                const resStr = result ? ` -> ${typeof result === 'string' ? result : JSON.stringify(result)}` : '';
                return `⚙️ Azione: ${name}${argsStr ? ` (${argsStr})` : ''}${resStr}`;
              }).join('\n');
              parts.push(`🔧 STRUMENTI E AZIONI:\n${toolLines}`);
            }

            // 3. Contenuto principale
            if (m.content && typeof m.content === 'string' && m.content.trim()) {
              parts.push(m.content.trim());
            }

            // 4. Metriche di prestazione (tps, ttft, token, durata)
            const metrics = m.metrics || {};
            const tps = metrics.tokens_per_second ?? m.tps;
            const ttft = metrics.routing_time_ms ?? m.ttft_ms ?? metrics.ttft_ms;
            const tokens = metrics.token_count ?? m.tokens ?? metrics.tokens;
            const dur = m.duration_s ?? (metrics.generation_time_ms ? (metrics.generation_time_ms / 1000).toFixed(2) : null);

            const metricParts = [];
            if (tps) metricParts.push(`⚡ ${tps} t/s`);
            if (ttft !== undefined && ttft !== null) metricParts.push(`⏱️ TTFT: ${Math.round(ttft)}ms`);
            if (tokens) metricParts.push(`🔢 Token: ${tokens}`);
            if (dur) metricParts.push(`🕒 Durata: ${dur}s`);

            if (metricParts.length > 0) {
              parts.push(`📊 METRICHE: ${metricParts.join(' | ')}`);
            }

            if (parts.length === 0) return null;
            return `${role}:\n${parts.join('\n\n')}`;
          }).filter(Boolean).join('\n\n---\n\n');

          if (formatted) {
            navigator.clipboard.writeText(formatted);
          }
        }}
        onExportPdf={() => {
          const msgs = core.messages || [];
          if (msgs.length === 0) return;
          const currentSession = core.sessions.find(s => s.id === core.activeSessionId) || {
            name: 'Conversazione AI',
            model: core.selectedModel
          };
          exportChatPdf({
            session: currentSession,
            messages: msgs,
            selectedModel: core.selectedModel
          });
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
            onExportPdfSession={(session) => {
              const msgs = core.sessionMessages[session.id] || loadMessagesFromStorage(session.id) || [];
              if (msgs.length === 0) return;
              exportChatPdf({
                session,
                messages: msgs,
                selectedModel: session.model || core.selectedModel
              });
            }}
          />
        )}
        <ChatMessages
          messages={core.messages}
          loading={core.loading}
          actionsLog={core.actionsLog}
          expandedThinking={core.expandedThinking}
          onToggleThinking={(id, forced) => core.setExpandedThinking(prev => ({
            ...prev,
            [id]: forced !== undefined ? forced : !prev[id]
          }))}
          selectedModel={core.selectedModel}
          onDeleteMessage={core.deleteMessage}
          refs={core.refs}
          onStop={core.stopInference}
          activeManifesto={core.activeManifesto}
          manifestos={core.manifestos}
          availableModels={core.availableModels}
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
        devModeAvailable={core.devModeAvailable}
        devModeEnabled={core.devModeEnabled}
        setDevModeEnabled={core.setDevModeEnabled}
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