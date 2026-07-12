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
  activeManifesto, manifestos,
}) {
  const grouped = groupMessages(messages);

  return (
    <div className="chat-messages">
      {/* Pipeline status bar */}
      <AgentPipelineStatus pipeline={agentPipeline} />
      
      {grouped.map((msgGroup, i) => (
        <div key={i} className="chat-message-wrapper">
          <AgentMessage
            groupedMessages={msgGroup.length > 1 ? msgGroup : undefined}
            msg={msgGroup.length === 1 ? msgGroup[0] : undefined}
            msgId={`msg-${i}`}
            msgIndex={i}
            expandedThinking={expandedThinking}
            onToggleThinking={(id) => onToggleThinking(id)}
            effectiveModelName={selectedModel}
            onDeleteMessage={onDeleteMessage}
            activeManifesto={activeManifesto}
            manifestos={manifestos}
          />
        </div>
      ))}
      {loading && <AgentMessage msg={{}} loading={true} onStop={onStop} />}
      {actionsLog.length > 0 && !loading && (
        <div className="chat-actions-summary">
          <FileText size={12} />
          <span>{actionsLog.filter(a => a.success).length}/{actionsLog.length} azioni</span>
        </div>
      )}
      <div ref={refs.messagesEnd} />
    </div>
  );
}