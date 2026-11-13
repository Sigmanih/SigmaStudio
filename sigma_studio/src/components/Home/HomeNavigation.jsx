import { useState, useEffect } from 'react';
import { Search, X, ChevronDown, ArrowUpRight } from 'lucide-react';
import { coreNavigation, workspaceEntries, navigateStudio } from '../../services/studioNavigation';
import { useCapabilities } from '../../hooks/useCapabilities';
import WorkspaceIcon from '../common/WorkspaceIcon';
import { useApp } from '../../contexts/AppContext';
import { WORK_DOMAINS, workDomainFor } from '../../utils/workDomains';
import { prepareRoleChat } from '../../services/chatNavigation';
import '../../styles/03-modules/home-navigation.css';

export default function HomeNavigation({ catalog, openTab, loading, error }) {
  const [active, setActive] = useState(null);
  const [query, setQuery] = useState('');
  const { skills } = useCapabilities();
  const { manifesti, aiChatOpen, setAiChatOpen } = useApp();
  const [actionError, setActionError] = useState('');
  const workspaces = workspaceEntries(catalog, skills);
  const core = coreNavigation(catalog, skills);
  const modules = workspaces.filter(entry => !core.some(c => c.tabType === entry.tabType)
    && !['creative_studio', 'video_studio', 'voice_studio', 'music'].includes(entry.tabType));
  const matches = entry => [entry.name, entry.description, ...(entry.children || []).map(c => c.name)]
    .join(' ').toLocaleLowerCase('it').includes(query.trim().toLocaleLowerCase('it'));
  const open = (entry, section) => {
    if (entry.area) { setActive(entry.area); setQuery(''); return; }
    if (entry.role) {
      const roleId = entry.role.id || entry.role.filename || entry.role.path;
      try { prepareRoleChat(localStorage, { roleId, send: false }); }
      catch (exc) { setActionError(exc.message); return; }
      if (aiChatOpen) window.dispatchEvent(new CustomEvent('sigma-chat-select-role', { detail: roleId }));
      else setAiChatOpen(true);
    } else if (entry.quickTool) quickTool(entry.quickTool);
    else navigateStudio(entry, openTab, section);
    setActive(null);
  };
  const quickTool = id => window.dispatchEvent(new CustomEvent('sigma-quick-tool', { detail: { id } }));
  const laboratoryGroups = WORK_DOMAINS.map(domain => ({ name: domain.name,
    entries: [...modules, ...core.filter(e => e.tabType === 'developer_studio')].filter(entry => workDomainFor(entry).id === domain.id) })).filter(group => group.entries.length);
  const areas = [
    { id: 'all', name: 'Tutti', icon: 'Blocks' },
    ...['model_hub', 'multimedia', 'whitepapers_lib', 'ai_config', 'marketplace'].map(type => core.find(entry => entry.tabType === type)).filter(Boolean).map(entry => ({ ...entry, id: entry.tabType })),
    { id: 'labs', name: 'Laboratori', icon: 'Workflow' },
    { ...core.find(e => e.tabType === 'chat'), id: 'chat', name: 'Chat' },
    { ...core.find(e => e.tabType === 'account'), id: 'account', name: 'Impostazioni' },
  ];
  const current = areas.find(area => area.id === active);
  const children = (current?.children || []).map(child => ({ ...child,
    tabType: child.tabType || current.tabType, section: child.tabType ? child.section : child.id,
    icon: child.icon || ({ benchmark: 'Gauge', training: 'Brain' }[child.id]) || current.icon }));
  const agentGroups = WORK_DOMAINS.map(domain => ({ name: domain.name,
    entries: (Array.isArray(manifesti) ? manifesti : []).filter(role => role.active !== false && workDomainFor(role).id === domain.id)
      .map(role => ({ id: role.id || role.filename || role.path, name: role.name || role.id, description: role.title || '', icon: 'Users', role })) })).filter(group => group.entries.length);
  const groups = active === 'all' ? [
    { name: 'Aree dello studio', entries: areas.filter(a => !['all', 'labs'].includes(a.id)).map(area => ({ ...area, area: area.id })) }, ...laboratoryGroups,
  ] : active === 'labs' ? laboratoryGroups
    : active === 'whitepapers_lib' ? [{ name: 'Gestione agenti', entries: children }, ...agentGroups]
    : [{ name: current?.name, entries: [
      ...children,
      ...(active === 'chat' ? [{ ...current, id: 'chat-workspace', name: 'Conversazioni' }, { id: 'chat-float', name: 'Chat flottante', icon: 'MessageSquare', quickTool: 'chat' }] : []),
      ...(active === 'ai_config' ? [{ id: 'providers-float', name: 'Providers flottanti', icon: 'SlidersHorizontal', quickTool: 'providers' }] : []),
      ...(active === 'account' ? [{ id: 'cleanup', name: 'Pulisci e ottimizza', icon: 'Wrench', quickTool: 'cleanup' }] : []),
    ] }];
  const toggle = id => { setActive(previous => previous === id ? null : id); setQuery(''); setActionError(''); };
  useEffect(() => {
    if (!active) return;
    const dismiss = event => { if (!event.target.closest('.home-navigation')) setActive(null); };
    document.addEventListener('pointerdown', dismiss);
    return () => document.removeEventListener('pointerdown', dismiss);
  }, [active]);

  return <div className="home-navigation" data-agent-component="HomeNavigation"
    onKeyDown={event => { if (event.key === 'Escape' && active) { event.stopPropagation(); setActive(null); event.currentTarget.querySelector(`[data-home-area="${active}"]`)?.focus(); } }}>
    {current && <section key={active} className="home-navigation-panel" id="home-navigation-panel" aria-label={`Navigazione ${current.name}`}>
      <header><div><span className="studio-eyebrow">IL TUO STUDIO</span><h2>{active === 'all' ? 'Tutti gli strumenti' : current.name}</h2></div>
        <div className="home-nav-panel-actions">{current.tabType && <button type="button" className="home-nav-open-area" onClick={() => open(current)}>Apri area <ArrowUpRight size={13} /></button>}
        <button type="button" className="home-nav-icon-button" onClick={() => setActive(null)} aria-label="Chiudi elenco"><X size={18} /></button></div></header>
      <label className="studio-search"><Search size={17} aria-hidden="true" /><input autoFocus value={query}
        onChange={event => setQuery(event.target.value)} placeholder="Cerca strumenti, laboratori o sezioni…" aria-label="Cerca nella navigazione" /></label>
      {loading && <p role="status">Caricamento dei laboratori disponibili…</p>}
      {error && <p role="alert">{error}</p>}
      {actionError && <p role="alert">{actionError}</p>}
      {groups.map(group => {
        const entries = group.entries.filter(matches);
        return entries.length > 0 && <section key={group.name} className="home-nav-group"><h3>{group.name}</h3>
          <div className="home-nav-grid is-compact">{entries.map(entry => <article key={entry.id || entry.tabType}>
            <button type="button" className="home-nav-destination" onClick={() => open(entry)}>
              <WorkspaceIcon name={entry.icon} size={16} /><span>{entry.name}</span><ArrowUpRight size={12} /></button>
          </article>)}</div></section>;
      })}
      {!groups.some(group => group.entries.some(matches)) && <p role="status">Nessuno strumento corrisponde a “{query}”.</p>}
    </section>}
    <nav className="home-navigation-dock" aria-label="Laboratori e strumenti">
      {areas.map(area => <button type="button" key={area.id} data-home-area={area.id} className={area.id === 'all' ? 'home-nav-launcher' : ''}
        aria-expanded={active === area.id} aria-controls="home-navigation-panel" onClick={() => toggle(area.id)}>
        <WorkspaceIcon name={area.icon} size={17} /><span>{area.name}</span><ChevronDown size={12} /></button>)}
    </nav>
  </div>;
}
