import React from 'react';
import { MonitorSmartphone, Orbit, Presentation, Pause } from 'lucide-react';
import { roleInitials } from './roleIcons';
import { activityText } from './agentActivity';
import { motionFallback } from './agentMotion';

/**
 * Plancia2D — la Home senza WebGL, per l'hardware che la 3D non regge.
 *
 * Gli stessi agenti della plancia 3D, sullo stesso anello attorno al nucleo
 * Sigma: ritratto, nome, ruolo e quello che l'agente sta facendo, con le stesse
 * modalita' dei personaggi 3D (console, tavolo olografico, presenta, in posa).
 * Solo DOM e CSS: nessun canvas da ridisegnare, quindi niente GPU sul Pi.
 */

const MODE_INFO = {
  console: { Icon: MonitorSmartphone, label: 'Alla console' },
  olotavolo: { Icon: Orbit, label: 'Al tavolo olografico' },
  presenta: { Icon: Presentation, label: 'Presenta' },
  posa: { Icon: Pause, label: 'In posa' }
};

export default function Plancia2D({ roles = [], selectedAgentId = '', onSelectAgent, activity }) {
  const count = roles.length || 1;
  const activeId = activity && activity.state !== 'idle' ? activity.roleId : '';

  return (
    // Lo strato esterno fa da contenitore per le query: una container query
    // non si applica all'elemento contenitore, solo a cio' che contiene
    <div className="plancia2d-scena">
      <div className="plancia2d" role="list" aria-label="Agenti della plancia">
        <div className="plancia2d-core" aria-hidden="true">
          <img src="/images/SigmaStudio.png" alt="" />
          <span>{roles.length} agenti</span>
        </div>

        {roles.map((role, i) => {
          // Stesso ordine e stessa partenza (in alto) della plancia 3D
          const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
          const isActive = role.id === activeId;
          const mode = isActive ? motionFallback(activity.state) : 'posa';
          const { Icon, label } = MODE_INFO[mode];
          const selected = role.id === selectedAgentId;
          return (
            <button
              key={role.id}
              type="button"
              role="listitem"
              className={`plancia2d-agent mode-${mode}${isActive ? ' is-active' : ''}${selected ? ' is-selected' : ''}`}
              style={{
                '--agent-color': role.color || '#00d2ff',
                '--ring-x': Math.cos(angle).toFixed(4),
                '--ring-y': Math.sin(angle).toFixed(4)
              }}
              onClick={() => onSelectAgent && onSelectAgent(selected ? null : role)}
              title={`${role.name} — ${role.title || ''}`}
            >
              <span className="plancia2d-avatar">
                {role.image && role.image !== '/images/default.png'
                  ? <img src={role.image} alt="" loading="lazy" />
                  : roleInitials(role.name)}
              </span>
              <span className="plancia2d-name">{role.name}</span>
              <span className="plancia2d-role">{role.title}</span>
              <span className="plancia2d-state">
                <Icon size={12} aria-hidden="true" />
                {isActive ? activityText(activity) : label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
