import React, { useState, useEffect, useCallback } from 'react';
import { 
  Home, 
  MessageSquare, 
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
  Globe
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Stato per l'espansione dei pilastri informativi (click o hover)
  const [expandedPillar, setExpandedPillar] = useState(null);
  const [hoveredPillar, setHoveredPillar] = useState(null);

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
        {/* ── Hero Section ad Alto Impatto ── */}
        <section className="home-hero-section">
          <div className="home-hero-glow" />
          
          <div className="home-hero-badge">
            <Sparkles size={13} className="home-sparkle-icon" />
            <span>SIGMA AI STUDIO • SOVRANITÀ COGNITIVA LOCALE</span>
          </div>

          <h1 className="home-hero-title">
            Intelligenza Artificiale Sovrana &<br />
            <span className="home-hero-title-accent">Ambiente di Sviluppo Modulare</span>
          </h1>

          <p className="home-hero-subtitle">
            Inferenza locale ad alte prestazioni, orchestratore multi-ruolo, protocollo MCP estendibile e zero dipendenze cloud.
          </p>

          {/* Quick Launchpad Buttons */}
          <div className="home-quick-actions">
            <button
              className="home-cta-btn primary"
              onClick={() => openTab({ name: 'Chat' }, 'chat')}
              title="Apri l'interfaccia di conversazione AI"
            >
              <MessageSquare size={16} />
              <span>Avvia Chat AI</span>
            </button>

            <button
              className="home-cta-btn secondary"
              onClick={openLocalModels}
              title="Gestisci ed esegui i modelli locali GGUF e Safetensors"
            >
              <Cpu size={16} />
              <span>Modelli Locali</span>
            </button>

            <button
              className="home-cta-btn glass"
              onClick={() => openTab({ name: 'Ruoli AI' }, 'whitepapers_lib')}
              title="Esplora il catalogo dei ruoli specialistici e manifesti"
            >
              <Scroll size={16} />
              <span>Ruoli & Specialisti</span>
            </button>

            <button
              className="home-cta-btn glass"
              onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')}
              title="Apri il pannello degli strumenti di sistema e protocollo MCP"
            >
              <Terminal size={16} />
              <span>Gateway MCP</span>
            </button>
          </div>
        </section>

        {/* ── Strip Aggiornamenti Git (se disponibili o al click) ── */}
        {updateState.updateAvailable && (
          <div className="home-alert-strip">
            <div className="home-alert-left">
              <Bell size={16} color="#faa03c" />
              <div className="home-alert-text">
                <strong>Aggiornamento Disponibile:</strong> {updateState.commitsBehind > 0 
                  ? `${updateState.commitsBehind} nuovi commit da scaricare su GitHub.`
                  : `Nuova versione v${updateState.latestVersion} pronta.`}
              </div>
            </div>
            <div className="home-alert-right">
              {updateState.newCommits.length > 0 && (
                <button 
                  className="home-alert-toggle" 
                  onClick={() => setShowCommits(v => !v)}
                >
                  {showCommits ? 'Nascondi novità' : 'Cosa cambia'}
                </button>
              )}
              <button className="home-alert-apply-btn" onClick={applyUpdate} disabled={updateState.applying}>
                {updateState.applying ? <RefreshCw size={12} className="spin" /> : <Download size={12} />}
                <span>{updateState.applying ? 'Applicazione...' : 'Aggiorna Adesso'}</span>
              </button>
            </div>
          </div>
        )}

        {/* Elenco novità commit a scomparsa */}
        {showCommits && updateState.newCommits.length > 0 && (
          <div className="home-commits-box">
            {updateState.newCommits.map(c => (
              <div key={c.sha} className="home-commit-row">
                <code className="home-commit-sha">{c.sha}</code>
                <span className="home-commit-msg">{c.message}</span>
                <span className="home-commit-date">{c.date}</span>
              </div>
            ))}
          </div>
        )}

        {/* Feedback applicazione update */}
        {updateState.applyResult && (
          <div className={`home-toast-banner ${updateState.applyResult.success ? 'success' : 'error'}`}>
            <div className="home-toast-content">
              {updateState.applyResult.success ? <Check size={14} /> : <AlertCircle size={14} />}
              <span>{updateState.applyResult.message}</span>
            </div>
            <button className="home-toast-close" onClick={() => setUpdateState(p => ({ ...p, applyResult: null }))}>✕</button>
          </div>
        )}

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

        {/* ── Catalogo Skills Showcase Slider ── */}
        <section className="home-skills-showcase">
          <SkillsShowcaseSlider openTab={openTab} />
        </section>

        {/* ── Footer Minimale ── */}
        <footer className="home-footer">
          <div className="home-footer-left">
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