import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { 
  Home, 
  Scroll, 
  ExternalLink, 
  DownloadCloud, 
  Layers, 
  Cpu, 
  ShieldCheck, 
  Terminal, 
  ArrowRight, 
  Sparkles, 
  Zap, 
  CheckCircle2, 
  RefreshCw, 
  AlertCircle, 
  Download, 
  GitBranch, 
  Check, 
  Bell, 
  Info, 
  ChevronDown, 
  ChevronUp, 
  Activity, 
  Sliders, 
  Flame, 
  Globe,
  Play,
  Heart,
  X
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Stato per l'espansione dei pilastri informativi (click o hover)
  const [expandedPillar, setExpandedPillar] = useState(null);
  const [hoveredPillar, setHoveredPillar] = useState(null);

  // Stato per apertura modale video demo (chat_record.mp4)
  const [showVideoModal, setShowVideoModal] = useState(false);

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

  // Toggle espansione dei pilastri
  const togglePillar = (id) => {
    setExpandedPillar(prev => prev === id ? null : id);
  };

  const openLocalModels = () => {
    try {
      localStorage.setItem('sigma_model_hub_active_subtab', 'inventory');
    } catch {}
    window.dispatchEvent(new CustomEvent('sigma-model-hub-set-tab', { detail: 'inventory' }));
    openTab({ name: 'Modelli' }, 'model_hub');
  };

  const pillarsData = [
    {
      id: 'engine',
      title: 'SigmaEngine',
      badge: 'GGUF & Safetensors',
      short: 'Inferenza neurale locale ad alta velocità con gestione dinamica di RAM/VRAM.',
      full: 'Esegui qualsiasi modello open-source direttamente sul tuo hardware senza passare dal cloud. Ottimizzato sia per potenti workstation con GPU dedicate che per architetture compatte come Raspberry Pi 5 (CPU aarch64). Zero latenza esterna, privacy al 100% e nessun costo di token.',
      icon: Cpu,
      color: '#00f2fe',
      bgGlow: 'rgba(0, 242, 254, 0.15)',
      actionText: 'Gestisci Modelli',
      actionTab: 'model_hub'
    },
    {
      id: 'roles',
      title: 'Ruoli Cognitivi',
      badge: `${updateState.activeRolesCount} Specialisti Attivi`,
      short: 'Manifesti etico-disciplinari che trasformano l\'assistente in professionisti dedicati.',
      full: 'Attiva all\'istante figure specializzate: dal programmatore senior al ricercatore matematico, dal revisore legale all\'analista finanziario. Ogni ruolo applica direttive etiche, stili comunicativi e metodologie di ragionamento strutturate pronte all\'uso in chat e pipeline.',
      icon: Scroll,
      color: '#bc8cff',
      bgGlow: 'rgba(188, 140, 255, 0.15)',
      actionText: 'Esplora Ruoli',
      actionTab: 'whitepapers_lib'
    },
    {
      id: 'mcp',
      title: 'Protocollo MCP',
      badge: 'Gateway Strumenti & Azione',
      short: 'Standard aperto Model Context Protocol per interagire con file, test e periferiche.',
      full: 'Fornisci all\'intelligenza artificiale braccia e occhi per agire nel tuo ambiente. Esegui script nel terminale, sincronizza file nel workspace, interroga sensori hardware in tempo reale e connetti server MCP esterni in totale trasparenza e sicurezza controllata.',
      icon: Terminal,
      color: '#ff5064',
      bgGlow: 'rgba(255, 80, 100, 0.15)',
      actionText: 'Gateway MCP',
      actionTab: 'mcp_hub'
    },
    {
      id: 'skills',
      title: 'Skills Hub & Moduli',
      badge: 'Architettura Modulare',
      short: 'Estendi l\'IDE con moduli avanzati (3D Lab, Audio Studio, Training) ad aggancio automatico.',
      full: 'Il kernel di Sigma Studio rimane leggero e minimale: installa e attiva con un click moduli specialistici opzionali mantenendo la separazione architetturale pulita. Condividi o crea nuove feature modulari per la community open source.',
      icon: Layers,
      color: '#3fb950',
      bgGlow: 'rgba(63, 185, 80, 0.15)',
      actionText: 'Apri Skills',
      actionTab: 'marketplace'
    }
  ];

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
          <button
            type="button"
            onClick={() => setShowVideoModal(true)}
            className="home-topbar-video-btn"
            title="Guarda il video tour e la dimostrazione di Sigma Studio"
          >
            <Play size={11} fill="currentColor" />
            <span>Video Demo</span>
          </button>

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
              {/* Guarda Video Demo */}
              <button
                type="button"
                className="home-bacheca-btn video"
                onClick={() => setShowVideoModal(true)}
                title="Guarda la sessione dimostrativa video di Sigma Studio"
              >
                <Play size={12} fill="currentColor" />
                <span>Video Demo</span>
              </button>

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

        {/* ── 4 Pilastri Card Interattive (Hover & Click per info complete) ── */}
        <section className="home-pillars-section">
          <div className="home-section-header">
            <div>
              <h2 className="home-section-title">Architettura & Capacità Chiave</h2>
              <p className="home-section-sub">
                Passa il cursore o clicca su ogni card per accedere alla scheda tecnica completa e alle direttive operative.
              </p>
            </div>
          </div>

          <div className="home-pillars-grid">
            {pillarsData.map(p => {
              const IconComp = p.icon;
              const isExpanded = expandedPillar === p.id;
              const isHovered = hoveredPillar === p.id;

              return (
                <div
                  key={p.id}
                  className={`home-pillar-card ${isExpanded ? 'is-expanded' : ''} ${isHovered ? 'is-hovered' : ''}`}
                  onMouseEnter={() => setHoveredPillar(p.id)}
                  onMouseLeave={() => setHoveredPillar(null)}
                  onClick={() => togglePillar(p.id)}
                >
                  <div className="home-pillar-header">
                    <div 
                      className="home-pillar-icon-box"
                      style={{ background: p.bgGlow, borderColor: `${p.color}55`, color: p.color }}
                    >
                      <IconComp size={20} />
                    </div>

                    <div className="home-pillar-title-area">
                      <div className="home-pillar-badge" style={{ color: p.color, borderColor: `${p.color}40` }}>
                        {p.badge}
                      </div>
                      <h3 className="home-pillar-title">{p.title}</h3>
                    </div>

                    <button 
                      type="button" 
                      className={`home-pillar-toggle-btn ${isExpanded ? 'open' : ''}`}
                      title={isExpanded ? "Comprimi dettagli" : "Espandi descrizione completa"}
                    >
                      {isExpanded ? <ChevronUp size={14} /> : <Info size={14} />}
                    </button>
                  </div>

                  {/* Sintesi immediata sempre visibile */}
                  <p className="home-pillar-short-desc">
                    {p.short}
                  </p>

                  {/* Descrizione approfondita espandibile su Click o visibile con dettaglio */}
                  {isExpanded && (
                    <div className="home-pillar-full-desc" onClick={e => e.stopPropagation()}>
                      <p>{p.full}</p>
                    </div>
                  )}

                  {/* Footer della card con Action CTA */}
                  <div className="home-pillar-footer" onClick={e => e.stopPropagation()}>
                    <button
                      type="button"
                      className="home-pillar-action-link"
                      style={{ color: p.color }}
                      onClick={() => {
                        if (p.actionTab === 'model_hub') {
                          openLocalModels();
                        } else {
                          openTab({ name: p.title }, p.actionTab);
                        }
                      }}
                    >
                      <span>{p.actionText}</span>
                      <ArrowRight size={12} />
                    </button>

                    <span className="home-pillar-hint">
                      {isExpanded ? 'Clicca per comprimere' : 'Clicca per info estese'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── Quick System Specs Counter Bar ── */}
        <section className="home-stats-strip">
          <div className="home-stat-item">
            <span className="home-stat-val">100% Locale</span>
            <span className="home-stat-lbl">Nessuna telemetria cloud</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat-item">
            <span className="home-stat-val">GGUF & SafeT</span>
            <span className="home-stat-lbl">Quantizzazione e VRAM dinamica</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat-item">
            <span className="home-stat-val">{updateState.activeRolesCount} Ruoli AI</span>
            <span className="home-stat-lbl">Manifesti cognitivi pronti</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat-item">
            <span className="home-stat-val">MCP Gateway</span>
            <span className="home-stat-lbl">Automazione di file e comandi</span>
          </div>
        </section>

        {/* ── Banner Sostegno Indipendente & Community (Efficace e Sobrio) ── */}
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
            <button
              type="button"
              className="home-community-btn-video"
              onClick={() => setShowVideoModal(true)}
              title="Guarda la registrazione dimostrativa del sistema"
            >
              <Play size={12} fill="currentColor" />
              <span>Video Demo (chat_record.mp4)</span>
            </button>
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
              onClick={() => setShowVideoModal(true)}
              className="home-footer-link"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              <Play size={10} fill="currentColor" />
              <span>Video Tour</span>
            </button>
            <span className="home-footer-bullet">•</span>
            <button
              onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
              className="home-footer-link"
            >
              🇮🇹 Documentazione IT
            </button>
            <span className="home-footer-bullet">•</span>
            <button
              onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
              className="home-footer-link"
            >
              🏛️ Architettura Kernel
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

      {/* ── Modale Video Demo (chat_record.mp4) tramite React Portal ── */}
      {showVideoModal && createPortal(
        <div className="home-video-modal-overlay" onClick={() => setShowVideoModal(false)}>
          <div className="home-video-modal-box" onClick={e => e.stopPropagation()}>
            <div className="home-video-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'rgba(0, 210, 255, 0.12)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#00d2ff'
                }}>
                  <Play size={16} fill="currentColor" />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f1f5f9' }}>
                    Tour Operativo & Demo Swarm Multi-Agente
                  </h3>
                  <span style={{ fontSize: '0.70rem', color: '#94a3b8' }}>
                    Sessione registrata: streaming sub-100ms, coordinamento ruoli e strumenti MCP
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="home-video-modal-close-btn"
                onClick={() => setShowVideoModal(false)}
                title="Chiudi Video"
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '16px', background: '#000000', display: 'flex', justifyContent: 'center' }}>
              <video
                src="/images/screenshots/chat_record.mp4"
                controls
                autoPlay
                style={{
                  width: '100%',
                  maxHeight: '62vh',
                  borderRadius: '10px',
                  outline: 'none',
                  backgroundColor: '#000'
                }}
              >
                Il tuo browser non supporta la riproduzione video HTML5.
              </video>
            </div>

            <div className="home-video-modal-footer">
              <a
                href="/images/screenshots/chat_record.mp4"
                download="chat_record.mp4"
                className="home-footer-link"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#38bdf8', textDecoration: 'none', fontSize: '0.74rem', fontWeight: 700 }}
              >
                <Download size={13} />
                <span>Scarica File Video (chat_record.mp4)</span>
              </a>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <a
                  href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
                  target="_blank"
                  rel="noreferrer"
                  className="home-community-btn-donate"
                  style={{ padding: '6px 14px', fontSize: '0.74rem' }}
                >
                  <Heart size={12} fill="#ffffff" />
                  <span>Sostieni su PayPal</span>
                </a>

                <button
                  type="button"
                  onClick={() => setShowVideoModal(false)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: isLight ? '#0f172a' : '#f1f5f9',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Chiudi
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}