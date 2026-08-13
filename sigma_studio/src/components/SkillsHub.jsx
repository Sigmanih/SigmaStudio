import React, { useCallback, useEffect, useState } from 'react';
import {
  Blocks, CheckCircle2, AlertTriangle, Play, ExternalLink, Power,
  Puzzle, RefreshCw, Wrench, Loader
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';

/**
 * Kernel di Sigma Studio: skill componibili e motori di supporto.
 *
 * Una skill non è "installata o no": è pronta, degradata o bloccata a seconda di
 * cosa c'è davvero sul sistema. Qui l'utente vede il perché e può agire —
 * avviare un motore, collegarlo, o spegnere una skill che non usa.
 */
export default function SkillsHub() {
  const { theme } = useApp();
  const [skills, setSkills] = useState([]);
  const [apps, setApps] = useState([]);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState(null);

  const load = useCallback(() => Promise.all([
    fetch('/api/skills').then(r => r.json()),
    fetch('/api/apps').then(r => r.json()),
  ]).then(([s, a]) => {
    if (s.success) setSkills(s.skills || []);
    if (a.success) setApps(a.apps || []);
  }).catch(e => setMessage({ type: 'error', text: e.message })), []);

  useEffect(() => { load(); }, [load]);

  const toggleSkill = (id, enabled) => {
    setBusy(id);
    fetch('/api/skills/toggle', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skill_id: id, enabled }),
    })
      .then(r => r.json())
      .then(d => {
        if (!d.success) setMessage({ type: 'error', text: d.error });
        return load();
      })
      .finally(() => setBusy(''));
  };

  const launchApp = (id) => {
    setBusy(id);
    fetch('/api/apps/launch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app_id: id }),
    })
      .then(r => r.json())
      .then(d => {
        setMessage(d.success
          ? { type: 'ok', text: d.message || 'Avviato' }
          : { type: 'error', text: d.error });
        // L'app impiega qualche secondo a rispondere: si ricontrolla dopo.
        setTimeout(load, 4000);
      })
      .finally(() => setBusy(''));
  };

  const autoconfigure = () => {
    setBusy('auto');
    fetch('/api/apps/autoconfigure', { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        const n = Object.keys(d.changed || {}).length;
        setMessage({ type: 'ok', text: n ? `Collegati: ${Object.keys(d.changed).join(', ')}` : 'Tutto già collegato' });
        return load();
      })
      .finally(() => setBusy(''));
  };

  return (
    <div className="skills-hub" style={{ padding: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      {/* Hero Visual Banner with Standardized Theme System & Dimensions */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: theme === 'light' ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: theme === 'light'
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/skills_engines_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/skills_engines_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: theme === 'light' ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Blocks size={14} /> SIGMA KERNEL SKILLS & ENGINE CATALOG
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: theme === 'light' ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              🛠️ Skills & <span style={{
                color: theme === 'light' ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Motori Componibili</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: theme === 'light' ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Sigma Studio è il kernel dell'Agente: ogni skill è una capacità componibile ed ogni motore è una dipendenza di calcolo locale.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={autoconfigure}
              disabled={busy === 'auto'}
              style={{
                padding: '10px 16px', borderRadius: '12px',
                background: theme === 'light' ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
                border: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.45)' : '1px solid rgba(0, 210, 255, 0.35)',
                color: theme === 'light' ? '#ea580c' : '#00d2ff', 
                fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              {busy === 'auto' ? <Loader size={15} className="cs-spin" /> : <Wrench size={15} />}
              Collega ciò che è installato
            </button>

            <button
              onClick={load}
              style={{
                padding: '10px 16px', borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#e2e8f0', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              <RefreshCw size={15} /> Aggiorna
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
        {message && (
          <div className={`skills-message ${message.type}`}>
            {message.type === 'ok' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)}>×</button>
          </div>
        )}

      <section>
        <h2><Puzzle size={16} /> Skill</h2>
        <div className="skills-grid">
          {skills.map(skill => (
            <article key={skill.id} className={`skill-card ${skill.enabled ? '' : 'off'}`}>
              <header>
                <span className="skill-name">{skill.label}</span>
                {skill.core ? (
                  <span className="skill-badge core">base</span>
                ) : (
                  <button
                    className={`skill-toggle ${skill.enabled ? 'on' : ''}`}
                    disabled={busy === skill.id}
                    title={skill.enabled ? 'Disattiva skill' : 'Attiva skill'}
                    onClick={() => toggleSkill(skill.id, !skill.enabled)}
                  >
                    <Power size={13} />
                  </button>
                )}
              </header>

              <p className="skill-desc">{skill.description}</p>

              <div className="skill-provides">
                {skill.provides.map(p => <span key={p}>{p}</span>)}
              </div>

              <footer>
                {!skill.ready && (
                  <span className="skill-status blocked">
                    <AlertTriangle size={12} />
                    manca {[
                      ...skill.missing_apps.map(a => a.label),
                      ...skill.missing_python,
                    ].join(', ')}
                  </span>
                )}
                {skill.ready && skill.degraded.length > 0 && (
                  <span className="skill-status degraded">
                    <AlertTriangle size={12} /> ridotta: {skill.degraded.join(', ')} non in esecuzione
                  </span>
                )}
                {skill.ready && !skill.degraded.length && (
                  <span className="skill-status ok"><CheckCircle2 size={12} /> pronta</span>
                )}
                {skill.mcp_server && (
                  <span className="skill-mcp" title="Esposta agli agenti della chat via MCP">
                    {skill.mcp_server}
                  </span>
                )}
              </footer>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h2><Wrench size={16} /> Motori di supporto</h2>
        <div className="skills-grid">
          {apps.map(app => (
            <article key={app.id} className="skill-card app">
              <header>
                <span className="skill-name">{app.label}</span>
                <span className={`app-dot ${app.running ? 'on' : app.installed ? 'idle' : 'off'}`}
                      title={app.running ? 'in esecuzione' : app.installed ? 'installato, fermo' : 'non installato'} />
              </header>

              <p className="skill-desc">{app.description}</p>

              <div className="skill-provides">
                {app.powers.map(p => <span key={p}>{p}</span>)}
              </div>

              {app.path && <p className="app-path" title={app.path}>{app.path}</p>}

              <footer>
                {app.running ? (
                  <span className="skill-status ok"><CheckCircle2 size={12} /> in esecuzione</span>
                ) : app.installed ? (
                  <button className="skills-btn small" disabled={busy === app.id}
                          onClick={() => launchApp(app.id)}>
                    {busy === app.id ? <Loader size={13} className="cs-spin" /> : <Play size={13} />} Avvia
                  </button>
                ) : (
                  <a className="skills-btn small ghost" href={app.install_url} target="_blank" rel="noreferrer">
                    <ExternalLink size={13} /> Installa
                  </a>
                )}
              </footer>
            </article>
          ))}
        </div>
      </section>
      </div>
    </div>
  );
}
