import React from 'react';
import { CheckCircle, XCircle, Clock, Loader } from 'lucide-react';

// ==============================================================================
// AGENT PIPELINE STATUS — Barra visuale della pipeline multi-agente
// Mostra lo stato di ogni agente nell'orchestrazione corrente
// ==============================================================================

const STATUS_ICONS = {
  pending: <Clock size={14} />,
  active: <Loader size={14} className="spin" />,
  done: <CheckCircle size={14} />,
  failed: <XCircle size={14} />,
};

const STATUS_COLORS = {
  pending: '#5a5e72',
  active: '#00d2ff',
  done: '#3fb950',
  failed: '#ff5555',
};

const AGENT_ICONS = {
  sigma_architect: '🏗️',
  math1: '∑',
  code_architect: '⚙️',
};

const AGENT_COLORS = {
  sigma_architect: '#7c5bf0',
  math1: '#3fb950',
  code_architect: '#00d2ff',
};

export default function AgentPipelineStatus({ pipeline }) {
  if (!pipeline || !pipeline.active) return null;

  const { agents, currentStep, totalSteps, goal } = pipeline;

  return (
    <div className="agent-pipeline-status">
      <div className="agent-pipeline-header">
        <span className="agent-pipeline-title">🎯 Pipeline Orchestrata</span>
        <span className="agent-pipeline-goal" title={goal}>
          {goal && goal.length > 60 ? goal.slice(0, 60) + '...' : goal}
        </span>
      </div>
      <div className="agent-pipeline-steps">
        {agents.map((agent, i) => {
          const statusColor = STATUS_COLORS[agent.status] || STATUS_COLORS.pending;
          const agentColor = AGENT_COLORS[agent.id] || '#8b8fa3';
          const isActive = agent.status === 'active';
          const isLast = i === agents.length - 1;

          return (
            <div key={agent.id} className={`agent-pipeline-step ${agent.status}`}>
              <div className="agent-pipeline-node" style={{ borderColor: isActive ? agentColor : statusColor }}>
                <span className="agent-pipeline-icon">{AGENT_ICONS[agent.id] || '🤖'}</span>
                {STATUS_ICONS[agent.status] || STATUS_ICONS.pending}
              </div>
              <div className="agent-pipeline-info">
                <div className="agent-pipeline-agent-name" style={{ color: agentColor }}>
                  {agent.name || agent.id}
                </div>
                <div className="agent-pipeline-task">{agent.task}</div>
                {agent.progress && (
                  <div className="agent-pipeline-progress">{agent.progress}</div>
                )}
              </div>
              {!isLast && <div className="agent-pipeline-connector" style={{ backgroundColor: statusColor }} />}
            </div>
          );
        })}
      </div>
      <div className="agent-pipeline-footer">
        <span>Step {currentStep}/{totalSteps}</span>
      </div>
    </div>
  );
}