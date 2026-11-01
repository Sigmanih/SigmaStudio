import { ArrowUpRight, MessageSquare } from 'lucide-react';
import { modulesForDomain, workDomainFor } from '../../utils/workDomains';
import '../../styles/03-modules/work-domains.css';

export default function WorkDomainActions({ agent, catalog, onOpenTab, onChat }) {
  const domain = workDomainFor(agent);
  const modules = modulesForDomain(domain.id, catalog);
  return (
    <nav className="work-domain-actions" aria-label={`Funzioni: ${domain.name}`}
      data-agent-component="WorkDomainActions">
      <button type="button" onClick={onChat} data-agent-action="open-domain-chat">
        <MessageSquare size={15} aria-hidden="true" /> Parla con {agent.roleName || agent.name}
      </button>
      {modules.map(entry => (
        <button type="button" key={`${entry.id}:${entry.tabType}`} data-agent-action="open-domain-workspace"
          onClick={() => onOpenTab({ name: entry.name }, entry.tabType)}>
          {entry.name} <ArrowUpRight size={15} aria-hidden="true" />
        </button>
      ))}
      {agent.members?.length > 1 && <span>{agent.members.length} specialisti disponibili nella selezione ruoli</span>}
    </nav>
  );
}
