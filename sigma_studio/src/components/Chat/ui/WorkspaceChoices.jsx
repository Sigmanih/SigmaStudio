import { ArrowUpRight } from 'lucide-react';
import { useState } from 'react';
import { useModuleState } from '../../../hooks/useModuleState';
import { openAvailableWorkspace, resolveWorkspaceTarget } from '../../../services/workspaceNavigation';
import { loadLocalModules } from '../../../services/moduleCatalog';
import '../../../styles/03-modules/work-domains.css';

export default function WorkspaceChoices({ choices, openTab }) {
  const { moduleCatalog } = useModuleState();
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const available = (Array.isArray(choices) ? choices : [])
    .map(choice => resolveWorkspaceTarget(choice, moduleCatalog)).filter(Boolean);
  if (!available.length) return null;
  const openWorkspace = async entry => {
    setPending(true);
    setNotice('');
    try {
      const { modules } = await loadLocalModules();
      if (!openAvailableWorkspace(entry, modules, openTab)) setNotice('Questo strumento non è più disponibile.');
    } catch {
      setNotice('Impossibile aprire lo strumento. Riprova fra poco.');
    } finally {
      setPending(false);
    }
  };
  return (
    <nav className="work-domain-actions" aria-label="Spazi di lavoro disponibili" data-agent-component="WorkspaceChoices">
      {available.map(entry => <button key={`${entry.moduleId}:${entry.tabType}`} type="button" disabled={pending}
        data-agent-action="open-workspace" onClick={() => openWorkspace(entry)}>
        {entry.name} <ArrowUpRight size={15} aria-hidden="true" />
      </button>)}
      {notice && <span role="status">{notice}</span>}
    </nav>
  );
}
