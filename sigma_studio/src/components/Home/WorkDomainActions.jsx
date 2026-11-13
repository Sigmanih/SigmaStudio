import { ArrowUpRight, MessageSquare } from 'lucide-react';
import { workDomainFor } from '../../utils/workDomains';
import { workspaceEntries, navigateStudio } from '../../services/studioNavigation';
import { useCapabilities } from '../../hooks/useCapabilities';
import CapabilityCard from '../common/CapabilityCard';
import '../../styles/03-modules/skills-workspace.css';
import '../../styles/03-modules/work-domains.css';

export default function WorkDomainActions({ agent, catalog, onOpenTab, onChat }) {
  const domain = workDomainFor(agent);
  const { skills } = useCapabilities();
  const modules = workspaceEntries(catalog, skills).filter(entry => workDomainFor(entry).id === domain.id);
  return (
    <nav className="work-domain-actions" aria-label={`Funzioni: ${domain.name}`}
      data-agent-component="WorkDomainActions">
      <button type="button" onClick={onChat} data-agent-action="open-domain-chat">
        <MessageSquare size={15} aria-hidden="true" /> Parla con {agent.roleName || agent.name}
      </button>
      <button type="button" onClick={() => navigateStudio({ tabType: 'marketplace', name: 'Skills',
        section: 'capabilities', domain: domain.id }, onOpenTab)}>
        Skills di {domain.name} <ArrowUpRight size={15} aria-hidden="true" />
      </button>
      <div className="agent-capabilities">{modules.map(entry =>
        <CapabilityCard key={entry.id} entry={entry} openTab={onOpenTab} compact />)}</div>
      {agent.members?.length > 1 && <span>{agent.members.length} specialisti disponibili nella selezione ruoli</span>}
    </nav>
  );
}
