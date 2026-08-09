import React, { useCallback, useEffect, useState } from 'react';
import {
  Blocks, CheckCircle2, AlertTriangle, Play, ExternalLink, Power,
  Puzzle, RefreshCw, Wrench, Loader
} from 'lucide-react';

/**
 * Kernel di Sigma Studio: skill componibili e motori di supporto.
 *
 * Una skill non è "installata o no": è pronta, degradata o bloccata a seconda di
 * cosa c'è davvero sul sistema. Qui l'utente vede il perché e può agire —
 * avviare un motore, collegarlo, o spegnere una skill che non usa.
 */
export default function SkillsHub() {
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
    <div className="skills-hub">
      <header className="skills-header">
        <div>
          <h1><Blocks size={22} /> Skills & Motori</h1>
          <p>
            Sigma Studio è il kernel: ogni skill è una capacità componibile, ogni motore
            è una dipendenza gestita. Qui decidi cosa la tua istanza sa fare.
          </p>
        </div>
        <div className="skills-actions">
          <button className="skills-btn" onClick={autoconfigure} disabled={busy === 'auto'}>
            {busy === 'auto' ? <Loader size={14} className="cs-spin" /> : <Wrench size={14} />}
            Collega ciò che è installato
          </button>
          <button className="skills-btn ghost" onClick={load}><RefreshCw size={14} /> Aggiorna</button>
        </div>
      </header>

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
  );
}
