import React from 'react';
import { FileText } from 'lucide-react';
import AgentMessage from '../AgentMessage';
import AgentPipelineStatus from '../AgentPipelineStatus';

// ==============================================================================
// ChatMessages — raggruppa messaggi system/assistant consecutivi
// ==============================================================================

/**
 * Raggruppa messaggi consecutivi con stesso ruolo (system o assistant)
 * per mostrarli in un unico bubble
 */
function groupMessages(messages) {
  if (!messages || messages.length === 0) return [];

  const grouped = [];
  let currentGroup = null;

  for (const msg of messages) {
    // Start a new group for user messages, or for system/assistant that follow a user msg
    const isSystem = msg.role === 'system';
    const isAssistant = !msg.role === 'user' && !msg.role === 'system';
    const isUser = msg.role === 'user';

    if (isUser) {
      // User messages are always solo
      if (currentGroup) {
        grouped.push(currentGroup);
        currentGroup = null;
      }
      grouped.push([msg]);
    } else if (isSystem || (!isUser)) {
      // System or assistant: group consecutive
      if (currentGroup) {
        currentGroup.push(msg);
      } else {
        currentGroup = [msg];
      }
    } else {
      if (currentGroup) {
        grouped.push(currentGroup);
        currentGroup = null;
      }
      grouped.push([msg]);
    }
  }

  if (currentGroup) {
    grouped.push(currentGroup);
  }

  return grouped;
}

export default function ChatMessages({
  messages, loading, actionsLog, expandedThinking, onToggleThinking,
  selectedModel, onDeleteMessage, refs, onStop, agentPipeline,
  activeManifesto, manifestos, availableModels, autoScroll, setAutoScroll,
}) {
  let displayMessages = messages || [];
  if (loading && displayMessages.length > 0) {
    const lastMsg = displayMessages[displayMessages.length - 1];
    if (lastMsg.role === 'user') {
      displayMessages = [
        ...displayMessages,
        {
          role: 'assistant',
          loading: true,
          agent_id: activeManifesto?.path?.replace('manifesti/', '')?.replace('.md', '') || selectedModel,
          agentRole: activeManifesto?.name || selectedModel,
          agentName: selectedModel,
          timestamp: new Date().toISOString()
        }
      ];
    }
  }

  const grouped = groupMessages(displayMessages);

  const handleScroll = (e) => {
    if (!setAutoScroll) return;
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    // Se la distanza dal fondo è inferiore a 55px, consideriamo che l'utente è alla fine
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 55;
    if (isAtBottom && !autoScroll) {
      setAutoScroll(true);
    } else if (!isAtBottom && autoScroll) {
      setAutoScroll(false);
    }
  };

  return (
    <div className="chat-messages" onScroll={handleScroll}>
      <div className="chat-messages-container">
        {/* Pipeline status bar */}
        <AgentPipelineStatus pipeline={agentPipeline} />
        
        {grouped.map((msgGroup, i) => {
          // Calcola l'indice reale di ciascun messaggio del gruppo all'interno dell'array flat 'messages'
          const realIndices = msgGroup.map(m => messages.indexOf(m)).filter(idx => idx !== -1);
          const indexValue = realIndices.length === 1 ? realIndices[0] : realIndices;
          const firstMsg = msgGroup[0] || {};
          const isUserGroup = firstMsg.role === 'user';
          const isWelcomeGroup = !isUserGroup && (
            firstMsg.isWelcome ||
            firstMsg.content === '# 🤖 Sigma AI Studio\n\nChat pronta.' ||
            firstMsg.content === 'Chat pronta.' ||
            (typeof firstMsg.content === 'string' && firstMsg.content.includes('Chat pronta.') && !firstMsg.thinking && msgGroup.length === 1)
          );

          let wrapperClass = 'chat-message-wrapper';
          if (isUserGroup) wrapperClass += ' user-wrapper';
          else if (isWelcomeGroup) wrapperClass += ' welcome-wrapper';
          else wrapperClass += ' assistant-wrapper';

          return (
            <div key={i} className={wrapperClass}>
              <AgentMessage
                groupedMessages={msgGroup.length > 1 ? msgGroup : undefined}
                msg={msgGroup.length === 1 ? msgGroup[0] : undefined}
                msgId={`msg-${i}`}
                msgIndex={indexValue}
                expandedThinking={expandedThinking}
                onToggleThinking={(id, forced) => onToggleThinking && onToggleThinking(id, forced)}
                effectiveModelName={selectedModel}
                onDeleteMessage={onDeleteMessage}
                activeManifesto={activeManifesto}
                manifestos={manifestos}
                availableModels={availableModels}
                autoScroll={autoScroll}
                setAutoScroll={setAutoScroll}
              />
            </div>
          );
        })}
        {actionsLog.length > 0 && !loading && (
          <div className="chat-actions-summary">
            <FileText size={12} />
            <span>{actionsLog.filter(a => a.success).length}/{actionsLog.length} azioni</span>
          </div>
        )}
        <div ref={refs.messagesEnd} />
      </div>
    </div>
  );
}