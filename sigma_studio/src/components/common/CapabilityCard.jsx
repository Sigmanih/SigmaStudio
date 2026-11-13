import { ArrowUpRight, CheckCircle2, CircleAlert } from 'lucide-react';
import WorkspaceIcon from './WorkspaceIcon';
import { navigateStudio } from '../../services/studioNavigation';

export default function CapabilityCard({ entry, openTab, compact = false }) {
  const skill = entry.skill;
  const blocked = skill && !skill.ready;
  const degraded = skill?.degraded?.length > 0;
  const status = blocked ? 'Da configurare' : degraded ? 'Disponibilità ridotta' : 'Disponibile';
  return <article className={`capability-card${compact ? ' is-compact' : ''}`} data-agent-component="CapabilityCard">
    <button type="button" className="capability-open" onClick={() => navigateStudio(entry, openTab)}
      data-agent-action="open-capability">
      <span className="capability-icon"><WorkspaceIcon name={entry.icon} /></span>
      <span><strong>{entry.name}</strong><small>{status}</small></span>
      <ArrowUpRight size={16} aria-hidden="true" />
    </button>
    {!compact && <>
      <p>{entry.description || skill?.description || 'Apri lo spazio di lavoro e crea con gli agenti di Sigma.'}</p>
      {!!skill?.provides?.length && <div className="capability-tags">{skill.provides.map(p => <span key={p}>{p}</span>)}</div>}
      <span className={`capability-status${blocked || degraded ? ' needs-attention' : ''}`}>
        {blocked || degraded ? <CircleAlert size={13} /> : <CheckCircle2 size={13} />}
        {blocked ? `Mancano: ${[...(skill.missing_apps || []).map(a => a.label), ...(skill.missing_python || [])].join(', ')}` : status}
      </span>
    </>}
    {!!entry.children?.length && <div className="capability-sections" aria-label={`Sezioni di ${entry.name}`}>
      {entry.children.map(child => <button type="button" key={child.id}
        onClick={() => navigateStudio(entry, openTab, child.id)}>{child.name}</button>)}
    </div>}
  </article>;
}
