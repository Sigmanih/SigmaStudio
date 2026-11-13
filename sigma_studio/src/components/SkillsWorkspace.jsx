import { useState, useEffect } from 'react';
import { Sparkles, Search, RefreshCw, Power } from 'lucide-react';
import TabHeader from './common/TabHeader';
import CapabilityCard from './common/CapabilityCard';
import SkillsHub from './SkillsHub';
import { useModuleState } from '../hooks/useModuleState';
import { useCapabilities } from '../hooks/useCapabilities';
import { WORK_DOMAINS, workDomainFor } from '../utils/workDomains';
import { CORE_NAVIGATION, workspaceEntries } from '../services/studioNavigation';
import { useApp } from '../contexts/AppContext';
import { prepareRoleChat } from '../services/chatNavigation';
import '../styles/03-modules/skills-workspace.css';

export default function SkillsWorkspace({ openTab, embedded = false }) {
  const { manifesti, aiChatOpen, setAiChatOpen } = useApp();
  const { moduleCatalog, isLoaded, error: moduleError } = useModuleState();
  const { skills, loading, error, reload } = useCapabilities();
  const [query, setQuery] = useState('');
  const [domain, setDomain] = useState(() => {
    try { return sessionStorage.getItem('sigma_skills_domain') || 'all'; } catch { return 'all'; }
  });
  const [enginesOpen, setEnginesOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => {
    const select = event => { setDomain(event.detail || 'all'); setQuery(''); };
    window.addEventListener('sigma-skills-domain', select);
    return () => window.removeEventListener('sigma-skills-domain', select);
  }, []);
  const toggle = async (id, enabled) => {
    setBusy(id); setMessage('');
    try {
      const response = await fetch('/api/skills/toggle', { method: 'POST', signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ skill_id: id, enabled }) });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Aggiornamento non riuscito');
      window.dispatchEvent(new CustomEvent('sigma_skills_updated'));
      window.dispatchEvent(new CustomEvent('sigma_modules_updated'));
    } catch (exc) { setMessage(exc.message); }
    finally { setBusy(''); }
  };
  const entries = workspaceEntries(moduleCatalog, skills);
  const core = CORE_NAVIGATION.filter(c => skills.some(s => s.tab_type === c.tabType && s.enabled))
    .filter(c => !entries.some(e => e.tabType === c.tabType)).map(c => ({ ...c,
      id: c.tabType, skill: skills.find(s => s.tab_type === c.tabType),
      workDomain: c.tabType === 'chat' ? 'general' : 'systems' }));
  const all = [...entries, ...core];
  const domains = WORK_DOMAINS.filter(d => all.some(e => workDomainFor(e).id === d.id));
  const visible = all.filter(e => (domain === 'all' || workDomainFor(e).id === domain)
    && [e.name, e.description, ...(e.skill?.provides || [])].join(' ').toLowerCase().includes(query.toLowerCase().trim()));
  const attention = skills.filter(s => s.enabled && (!s.ready || s.degraded?.length)).length;
  const agents = (Array.isArray(manifesti) ? manifesti : []).filter(role => role.active !== false
    && (domain === 'all' || workDomainFor(role).id === domain));
  const chatWith = role => {
    const roleId = role.id || role.filename || role.path;
    try { prepareRoleChat(localStorage, { roleId, send: false }); }
    catch (exc) { setMessage(exc.message); return; }
    if (aiChatOpen) window.dispatchEvent(new CustomEvent('sigma-chat-select-role', { detail: roleId }));
    else setAiChatOpen(true);
  };
  return <div className={`capabilities-hub${embedded ? ' is-embedded' : ''}`} data-agent-component="SkillsWorkspace">
    {!embedded && <TabHeader icon={Sparkles} title="Skills" description="Le capacità dei tuoi agenti, pronte da aprire." />}
    <div className="capabilities-body">
      <header className="capabilities-intro"><div><span className="studio-eyebrow">DALL’IDEA ALLO SPAZIO DI LAVORO</span>
        <h2>Cosa vuoi creare oggi?</h2><p>Le stesse skill che trovi selezionando un agente nella Home. Apri un laboratorio o scegli una delle sue sezioni.</p></div>
        <button type="button" className="capabilities-secondary" onClick={reload} disabled={loading}><RefreshCw size={15} /> Aggiorna</button></header>
      <div className="capabilities-summary"><span><strong>{all.length}</strong> spazi disponibili</span>
        <span><strong>{domains.length}</strong> campi di lavoro</span><span><strong>{attention}</strong> capacità da configurare</span></div>
      {(error || moduleError || message) && <p role="status">{error || moduleError || message}</p>}
      <label className="studio-search"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)}
        placeholder="Cerca una capacità, un laboratorio o un’attività…" aria-label="Cerca skill" /></label>
      <nav className="capabilities-filters" aria-label="Campi delle skill">
        {[{ id: 'all', name: 'Tutte' }, ...domains].map(d => <button type="button" key={d.id} aria-pressed={domain === d.id}
          onClick={() => setDomain(d.id)}>{d.name}</button>)}</nav>
      {(!isLoaded || loading) && <p role="status">Verifica delle capacità installate…</p>}
      <div className="capabilities-grid">{visible.map(entry => <div key={entry.id} className="capability-wrapper">
        <CapabilityCard entry={entry} openTab={openTab} />
        {entry.skill && !entry.skill.core && <button type="button" className="capability-disable" disabled={!!busy}
          onClick={() => toggle(entry.skill.id, false)}><Power size={12} /> Disattiva capacità</button>}
      </div>)}</div>
      {!!agents.length && <section className="capabilities-agents"><h3>Agenti per questo campo</h3>
        <div>{agents.map(role => <button type="button" className="capabilities-secondary" key={role.id || role.path || role.filename}
          onClick={() => chatWith(role)}>Parla con {role.name || role.id}</button>)}</div></section>}
      {isLoaded && !loading && !visible.length && <div className="capabilities-empty"><Sparkles size={24} />
        <h3>Nessuna capacità in questa selezione</h3><p>Prova un altro campo o cerca nel catalogo dei moduli.</p>
        <button type="button" className="capabilities-secondary" onClick={() => { setDomain('all'); setQuery(''); }}>Mostra tutte</button></div>}
      {skills.some(s => !s.enabled) && <section className="capabilities-disabled"><h3>Capacità disattivate</h3>
        {skills.filter(s => !s.enabled).map(s => <button type="button" key={s.id} disabled={!!busy}
          className="capabilities-secondary" onClick={() => toggle(s.id, true)}><Power size={14} /> Attiva {s.label}</button>)}</section>}
      <section className="capabilities-engines"><button type="button" className="capabilities-secondary" aria-expanded={enginesOpen}
        onClick={() => setEnginesOpen(value => !value)}>Motori e collegamenti</button>
        {enginesOpen && <SkillsHub enginesOnly />}</section>
    </div>
  </div>;
}
