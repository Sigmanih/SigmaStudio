import React, { useState, useEffect, useCallback } from 'react';
import { 
  ExternalLink, 
  CheckCircle2, 
  RefreshCw, 
  AlertCircle, 
  Download, 
  GitBranch, 
  Check, 
  Bell, 
  Heart
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // GitHub & Roles Update Check State
  const [updateState, setUpdateState] = useState({
    loading: true,
    checking: false,
    updateAvailable: false,
    latestVersion: '0.9.0',
    currentVersion: '0.9.0',
    phase: 'Beta Open Release',
    releaseTitle: 'Sigma AI Studio v0.9.0 (Beta)',
    releaseNotes: '',
    publishedAt: '',
    htmlUrl: 'https://github.com/Sigmanih/SigmaStudio/releases',
    downloadUrl: 'https://github.com/Sigmanih/SigmaStudio/archive/refs/heads/main.zip',
    activeRolesCount: 20,
    hasRoleUpdates: false,
    gitAvailable: false,
    commitsBehind: 0,
    newCommits: [],
    localCommit: '',
    localBranch: '',
    remoteCommit: '',
    remoteBranch: 'main',
    diverged: false,
    lastChecked: null,
    error: null,
    applying: false,
    applyResult: null
  });
  const [showCommits, setShowCommits] = useState(false);

  // Check for updates
  const checkForUpdates = useCallback(async (isManual = false) => {
    if (isManual) {
      setUpdateState(p => ({ ...p, checking: true, error: null, applyResult: null }));
    }
    try {
      const res = await fetch(`/api/system/updates/check${isManual ? '?force=1' : ''}`);
      const data = await res.json();
      if (data && data.success) {
        setUpdateState(p => ({
          ...p,
          loading: false,
          checking: false,
          updateAvailable: !!data.update_available,
          latestVersion: data.latest_version || '0.9.0',
          currentVersion: data.current_version || '0.9.0',
          phase: data.phase || 'Beta Open Release',
          releaseTitle: data.release_title || `Sigma AI Studio v${data.current_version || '0.9.0'}`,
          releaseNotes: data.release_notes || '',
          publishedAt: data.published_at || '',
          htmlUrl: data.html_url || 'https://github.com/Sigmanih/SigmaStudio/releases',
          downloadUrl: data.download_url || 'https://github.com/Sigmanih/SigmaStudio/archive/refs/heads/main.zip',
          activeRolesCount: data.active_roles_count || 20,
          hasRoleUpdates: !!data.has_role_updates,
          gitAvailable: !!data.git_available,
          commitsBehind: data.commits_behind || 0,
          newCommits: Array.isArray(data.new_commits) ? data.new_commits : [],
          localCommit: data.local_commit || '',
          localBranch: data.local_branch || '',
          remoteCommit: data.remote_commit || '',
          remoteBranch: data.remote_branch || 'main',
          diverged: !!data.diverged,
          lastChecked: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          error: null
        }));
      } else {
        setUpdateState(p => ({ ...p, loading: false, checking: false }));
      }
    } catch (e) {
      console.debug("Update check fallback:", e);
      setUpdateState(p => ({
        ...p,
        loading: false,
        checking: false,
        lastChecked: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }));
    }
  }, []);

  const applyUpdate = async () => {
    setUpdateState(p => ({ ...p, applying: true, applyResult: null }));
    try {
      const res = await fetch('/api/system/updates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      setUpdateState(p => ({
        ...p,
        applying: false,
        applyResult: {
          success: data.success,
          message: data.message || (data.success ? 'Aggiornamento applicato con successo!' : 'Verifica manuale richiesta.'),
          log: data.log || '',
          restartRequired: !!data.restart_required
        },
        updateAvailable: data.success ? false : p.updateAvailable
      }));
      setTimeout(() => checkForUpdates(false), 2000);
    } catch (err) {
      setUpdateState(p => ({
        ...p,
        applying: false,
        applyResult: {
          success: false,
          message: `Errore durante l'aggiornamento: ${err.message}`
        }
      }));
    }
  };

  useEffect(() => {
    checkForUpdates(false);
  }, [checkForUpdates]);

  return (
    <div className="home-dashboard-wrapper">
      {/* ── Top Bar Minimale e Fluida ── */}
      <div className="home-topbar">
        <div className="home-topbar-left">
          <div className="home-status-dot" />
          <span className="home-kernel-badge">KERNEL v{updateState.currentVersion}</span>
          <span className="home-topbar-divider">•</span>
          <span className="home-topbar-roles">{updateState.activeRolesCount} Ruoli Attivi</span>
          <span className="home-topbar-divider">•</span>
          <span className="home-topbar-status">Pronto & Operativo</span>
        </div>

        <div className="home-topbar-right">
          <a
            href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
            target="_blank"
            rel="noreferrer"
            className="home-topbar-donate-link"
            title="Sostieni lo sviluppo indipendente di Sigma Studio con PayPal"
          >
            <Heart size={11} fill="#f43f5e" color="#f43f5e" />
            <span>Sostieni</span>
          </a>

          <button
            onClick={() => checkForUpdates(true)}
            disabled={updateState.checking || updateState.applying}
            className="home-check-btn"
            title="Verifica se ci sono novità o nuovi manifesti su GitHub"
          >
            <RefreshCw size={11} className={updateState.checking ? "spin" : ""} />
            <span>{updateState.checking ? 'Controllo...' : 'Verifica Aggiornamenti'}</span>
          </button>

          {updateState.updateAvailable && (
            <button
              onClick={applyUpdate}
              disabled={updateState.applying}
              className="home-update-btn-alert"
            >
              <Download size={11} />
              <span>{updateState.applying ? 'Download...' : 'Aggiorna Ora'}</span>
            </button>
          )}

          <a
            href={updateState.htmlUrl || "https://github.com/Sigmanih/SigmaStudio/releases"}
            target="_blank"
            rel="noreferrer"
            className="home-github-link"
          >
            <ExternalLink size={11} />
            <span>GitHub</span>
          </a>
        </div>
      </div>

      <div className="home-main-scrollable">

        {/* ── Bacheca di Sistema: Aggiornamenti Git & Ruoli ── */}
        <div className={`home-bacheca-card ${updateState.updateAvailable ? 'has-update' : ''}`}>
          <div className="home-bacheca-main">
            {/* Sinistra: Icona + Info Stato Git/Sistema */}
            <div className="home-bacheca-left">
              <div className="home-bacheca-icon-box">
                {updateState.checking ? (
                  <RefreshCw size={20} className="spin" color="#00d2ff" />
                ) : updateState.updateAvailable ? (
                  <Bell size={20} color="#faa03c" />
                ) : (
                  <CheckCircle2 size={20} color="#3fb950" />
                )}
              </div>

              <div className="home-bacheca-info">
                <div className="home-bacheca-title-row">
                  <span className="home-bacheca-title">
                    {updateState.updateAvailable
                      ? (updateState.commitsBehind > 0
                          ? `⚡ ${updateState.commitsBehind} ${updateState.commitsBehind === 1 ? 'nuovo commit disponibile' : 'nuovi commit disponibili'} su GitHub`
                          : `⚡ Nuova Versione Rilasciata: v${updateState.latestVersion}`)
                      : `🟢 Sigma AI Studio v${updateState.currentVersion} • Sistema & Ruoli Sincronizzati`}
                  </span>
                  <span className={`home-bacheca-badge ${updateState.updateAvailable ? 'update' : 'synced'}`}>
                    {updateState.updateAvailable ? 'Aggiornamento Disponibile' : 'Sistema Sincronizzato'}
                  </span>
                </div>

                <p className="home-bacheca-desc-text">
                  Sigma Studio è un IDE intelligente e modulare per la ricerca e lo sviluppo con intelligenza artificiale locale e sovrana.
                  Integra agenti cognitivi specializzati, elaborazione hardware trasparente e automazione guidata da protocollo MCP.
                </p>

                <div className="home-bacheca-sub">
                  {updateState.updateAvailable ? (
                    <span>{updateState.releaseNotes || updateState.releaseTitle || 'Disponibile nuova versione con miglioramenti kernel e nuovi manifesti.'}</span>
                  ) : updateState.gitAvailable && updateState.localCommit ? (
                    <span>
                      Allineato al commit <code className="home-bacheca-mono">{updateState.localCommit}</code>
                      {updateState.localBranch ? ` · ramo ${updateState.localBranch}` : ''}
                      <span> • Catalogo ruoli verificato ({updateState.activeRolesCount} ruoli attivi)</span>
                    </span>
                  ) : (
                    <span>Versione open per la community. Repository GitHub sincronizzato con il catalogo dei ruoli attivi ({updateState.activeRolesCount} ruoli).</span>
                  )}
                  {updateState.lastChecked && (
                    <span className="home-bacheca-time">• Verificato alle {updateState.lastChecked}</span>
                  )}

                  {/* Dettaglio delta commit locale -> remoto */}
                  {updateState.updateAvailable && updateState.commitsBehind > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%', marginTop: '2px' }}>
                      <span className="home-bacheca-mono">
                        {updateState.localCommit} → {updateState.remoteCommit}
                      </span>
                      <span style={{ opacity: 0.8 }}>· ramo {updateState.remoteBranch}</span>
                      {updateState.newCommits.length > 0 && (
                        <button
                          type="button"
                          className="home-bacheca-toggle-commits"
                          onClick={() => setShowCommits(v => !v)}
                        >
                          {showCommits ? 'Nascondi novità' : 'Vedi cosa cambia'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Destra: Azioni Bacheca */}
            <div className="home-bacheca-actions">
              {/* Verifica Manuale */}
              <button
                type="button"
                className="home-bacheca-btn check"
                onClick={() => checkForUpdates(true)}
                disabled={updateState.checking || updateState.applying}
                title="Verifica se ci sono novità o nuovi manifesti su GitHub"
              >
                <RefreshCw size={12} className={updateState.checking ? "spin" : ""} />
                <span>{updateState.checking ? 'Controllo...' : 'Verifica Aggiornamenti'}</span>
              </button>

              {/* Aggiorna Ora o Sincronizza Ruoli */}
              {updateState.updateAvailable ? (
                <button
                  type="button"
                  className="home-bacheca-btn apply"
                  onClick={applyUpdate}
                  disabled={updateState.applying}
                  title="Scarica e applica i commit da GitHub"
                >
                  {updateState.applying ? <RefreshCw size={13} className="spin" /> : <Download size={13} />}
                  <span>{updateState.applying ? 'Download...' : 'Scarica & Aggiorna Ora'}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="home-bacheca-btn sync"
                  onClick={applyUpdate}
                  disabled={updateState.applying}
                  title="Sincronizza i manifesti e ruoli dal repository ufficiale"
                >
                  {updateState.applying ? <RefreshCw size={12} className="spin" /> : <GitBranch size={12} />}
                  <span>{updateState.applying ? 'Sincronizzazione...' : 'Sincronizza Ruoli'}</span>
                </button>
              )}

              {/* Link Release GitHub */}
              <a
                href={updateState.htmlUrl || "https://github.com/Sigmanih/SigmaStudio/releases"}
                target="_blank"
                rel="noreferrer"
                className="home-bacheca-link"
                title="Apri le release o il repository su GitHub"
              >
                <ExternalLink size={12} />
                <span>{updateState.commitsBehind > 0 ? 'Vedi su GitHub' : 'Release GitHub'}</span>
              </a>
            </div>
          </div>

          {/* Drawer Novità Commit */}
          {showCommits && updateState.newCommits.length > 0 && (
            <div className="home-bacheca-commits">
              <div className="home-bacheca-commits-header">
                Nuovi commit da integrare da GitHub ({updateState.newCommits.length}):
              </div>
              {updateState.newCommits.map(c => (
                <div key={c.sha} className="home-bacheca-commit-row">
                  <code className="home-bacheca-commit-sha">{c.sha}</code>
                  <span className="home-bacheca-commit-msg">{c.message}</span>
                  <span className="home-bacheca-commit-date">{c.date}</span>
                </div>
              ))}
            </div>
          )}

          {/* Feedback Applicazione Aggiornamento */}
          {updateState.applyResult && (
            <div className={`home-bacheca-feedback ${updateState.applyResult.success ? 'success' : 'error'}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {updateState.applyResult.success ? <Check size={14} /> : <AlertCircle size={14} />}
                <span>{updateState.applyResult.message}</span>
                {updateState.applyResult.restartRequired && (
                  <span style={{ fontSize: '0.70rem', opacity: 0.9 }}>
                    (Riavvio del kernel consigliato)
                  </span>
                )}
              </div>
              <button
                type="button"
                className="home-toast-close"
                onClick={() => setUpdateState(p => ({ ...p, applyResult: null }))}
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* ── Banner Sostegno Indipendente & Community (posizionato in evidenza in alto) ── */}
        <section className="home-community-banner">
          <div className="home-community-left">
            <div className="home-community-icon">
              <Heart size={18} color="#f43f5e" fill="rgba(244, 63, 94, 0.35)" />
            </div>
            <div>
              <div className="home-community-title">
                Sviluppo Indipendente & Sovranità Cognitiva Locale
              </div>
              <div className="home-community-desc">
                Sigma Studio è libero, open source e rigorosamente locale. Se trovi utile il progetto, sostieni la ricerca e lo sviluppo di nuovi moduli con una libera donazione.
              </div>
            </div>
          </div>
          <div className="home-community-actions">
            <a
              href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
              target="_blank"
              rel="noreferrer"
              className="home-community-btn-donate"
              title="Fai una libera donazione con PayPal a supporto del progetto"
            >
              <Heart size={12} fill="#ffffff" />
              <span>Supporta su PayPal</span>
              <ExternalLink size={11} />
            </a>
          </div>
        </section>

        {/* ── Catalogo Skills Showcase Slider ── */}
        <section className="home-skills-showcase">
          <SkillsShowcaseSlider openTab={openTab} />
        </section>

        {/* ── Footer Minimale ── */}
        <footer className="home-footer">
          <div className="home-footer-left">
            <button
              onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
              className="home-footer-link"
            >
              📖 Documentation (README)
            </button>
            <span className="home-footer-bullet">•</span>
            <button
              onClick={() => openTab({ path: 'ARCHITECTURE.md', filename: 'ARCHITECTURE.md' }, 'editor')}
              className="home-footer-link"
            >
              🏛️ Architecture
            </button>
            <span className="home-footer-bullet">•</span>
            <a
              href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
              target="_blank"
              rel="noreferrer"
              className="home-footer-link"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#fb7185', textDecoration: 'none' }}
              title="Supporta lo sviluppo indipendente con PayPal"
            >
              <Heart size={10} fill="#fb7185" />
              <span>Sostieni la Ricerca</span>
            </a>
          </div>

          <div className="home-footer-right">
            <span className="home-footer-dot">●</span>
            <span>Sigma AI Studio v{updateState.currentVersion} • Open Community Release</span>
          </div>
        </footer>
      </div>
    </div>
  );
}