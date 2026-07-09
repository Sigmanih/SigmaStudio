import React from 'react';
import { FileText } from 'lucide-react';
import AgentMessage from '../AgentMessage';
import AgentPipelineStatus from '../AgentPipelineStatus';

export default function ChatMessages({
  messages, loading, actionsLog, expandedThinking, onToggleThinking,
  selectedModel, onDeleteMessage, refs, onStop, agentPipeline,
}) {
  return (
    <div className="chat-messages">
      {/* Pipeline status bar */}
      <AgentPipelineStatus pipeline={agentPipeline} />
      
      {messages.map((msg, i) => (
        <div key={i} className="chat-message-wrapper">
          <AgentMessage
            msg={msg}
            msgId={`msg-${i}`}
            msgIndex={i}
            expandedThinking={expandedThinking}
            onToggleThinking={(id) => onToggleThinking(id)}
            effectiveModelName={selectedModel}
            onDeleteMessage={onDeleteMessage}
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
