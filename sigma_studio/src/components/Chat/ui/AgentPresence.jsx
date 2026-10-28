import React from 'react';
import { Sparkles, Wrench, Globe, PenLine, Check, TriangleAlert, Circle } from 'lucide-react';
import { activityText } from '../../common/agentActivity';
import { roleInitials } from '../../common/roleIcons';

const STATE_ICON = {
  idle: Circle,
  thinking: Sparkles,
  tool: Wrench,
  browsing: Globe,
  writing: PenLine,
  done: Check,
  error: TriangleAlert
};

// Ritratto vivo dell'agente: l'anello e la riga di stato mostrano cosa sta
// facendo davvero (ragiona, quale tool usa, scrive), al posto dell'etichetta fissa "Chat AI".
export default function AgentPresence({ activity, compact = false }) {
  const state = activity?.state || 'idle';
  const Icon = STATE_ICON[state] || Circle;
  const name = activity?.roleName || 'Sigma';
  const label = activityText(activity || undefined);
  // Il nome del tool e' gia' nella frase: il dettaglio dice su cosa lavora
  const detail = state === 'tool' || state === 'browsing' || state === 'thinking' ? (activity?.detail || '') : '';

  return (
    <div
      className={`agent-presence state-${state} ${compact ? 'is-compact' : ''}`}
      style={activity?.color ? { '--agent-color': activity.color } : undefined}
    >
      <span className="agent-presence-avatar" aria-hidden="true">
        <span className="agent-presence-ring" />
        <span className="agent-presence-face">
          {activity?.image
            ? <img src={activity.image} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
            : roleInitials(name)}
        </span>
        {state !== 'idle' && (
          <span className="agent-presence-badge"><Icon size={9} strokeWidth={3} /></span>
        )}
      </span>
      <span className="agent-presence-text">
        <span className="agent-presence-name">{name}</span>
        <span className="agent-presence-status" role="status" aria-live="polite" title={detail || label}>
          {label}{detail ? <span className="agent-presence-detail"> · {detail}</span> : null}
        </span>
      </span>
    </div>
  );
}
