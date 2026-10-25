import React, { useState, useEffect, useCallback } from 'react';
import { 
  Terminal, MessageSquare, Palette, Clapperboard, Mic,
  CircuitBoard, Zap, DownloadCloud, Sparkles,
  ArrowRight, CheckCircle2, RefreshCw, AlertCircle, Download, 
  ExternalLink, Heart, ChevronRight, Layers,
  Brain, ShieldCheck, HardDrive, Cpu, X, Film, Camera, Activity
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import TechSpaceCanvas from './common/TechSpaceCanvas';
import ThinkingOrb from './common/ThinkingOrb';

const INSPIRATION_PILLS = [
  {
    label: '⚡ PCB KiCad',
    role: 'code_architect',
    prompt: 'Progetta uno schematico KiCad per un controller ESP32 con alimentazione switching a 5V e filtri EMC.'
  },
  {
    label: '🎬 Regia Cinema',
    role: 'regista_cinematografico',
    prompt: 'Imposta la direzione visiva e la lista inquadrature per una sequenza notturna cyberpunk con neon e pioggia.'
  },
  {
    label: '📜 Sceneggiatura',
    role: 'sceneggiatore',
    prompt: 'Scrivi la struttura in 3 atti e il dialogo di apertura per una storia thriller noir tra un ingegnere e un androide.'
  },
  {
    label: '🎥 DoP Luci & LUT',
    role: 'direttore_fotografia',
    prompt: 'Crea una color palette teal & orange anamorfica con lighting ratio 4:1 e note ottiche 35mm T1.5.'
  },
  {
    label: '⚙️ Code Refactor',
    role: 'code_architect',
    prompt: 'Scrivi un modulo ad alte prestazioni in Rust con architettura a zero-allocazioni ed esegui i test unitari.'
  },
  {
    label: '∑ Math & KaTeX',
    role: 'math1',
    prompt: 'Deriva la formulazione analitica per un filtro di Kalman esteso con matrici formattate in KaTeX e note operative.'
  }
];

export default function WelcomeDashboard({ modules = [], openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Stato per l'input rapido del prompt e rotazione suggerimenti
  const [quickPrompt, setQuickPrompt] = useState('');
  const [selectedRole, setSelectedRole] = useState('sigma_architect');
  const [suggestionIdx, setSuggestionIdx] = useState(0);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  // Rotazione dinamica dei suggerimenti se l'utente non ha scritto nulla
  useEffect(() => {
    const timer = setInterval(() => {
      setSuggestionIdx(prev => (prev + 1) % INSPIRATION_PILLS.length);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  // Gestore per il riflesso spotlight dinamico al movimento del cursore
  const handleCardMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
    e.currentTarget.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
  };

  // GitHub & Roles Update Check State
  const [updateState, setUpdateState] = useState({
    loading: true,
    checking: false,
    updateAvailable: false,
    latestVersion: '0.9.0',
    currentVersion: '0.9.0',
    phase: 'Beta Open Release',
    releaseTitle: 'Sigma AI Studio v0.9.0',
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

  // Check for updates via API
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

  // Avvia chat con ruolo e/o prompt rapido
  const handleStartChatWithRole = (roleId, customText = '') => {
    try {
      if (roleId) {
        localStorage.setItem('sigma_active_role', roleId);
        window.dispatchEvent(new CustomEvent('sigma-chat-select-role', { detail: roleId }));
      }
      if (customText && customText.trim()) {
        localStorage.setItem('sigma_pending_chat_prompt', customText.trim());
        window.dispatchEvent(new CustomEvent('sigma-chat-set-prompt', { detail: customText.trim() }));
      }
    } catch (e) { }
    if (openTab) {
      openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
    }
  };

  const handleQuickPromptSubmit = (e) => {
    e.preventDefault();
    if (!quickPrompt.trim()) return;
    handleStartChatWithRole(selectedRole, quickPrompt);
    setQuickPrompt('');
  };

  // Elenco dei ruoli card in evidenza
  const FEATURED_ROLES = [
    {
      id: 'sigma_architect',
      name: 'Sigma Architect',
      title: 'Architetto & Core Swarm',
      icon: '🏗️',
      image: '/images/agente0.png',
      color: '#7c5bf0',
      desc: 'Pianificazione di sistema, orchestrazione e sintesi.'
    },
    {
      id: 'regista_cinematografico',
      name: 'Regista',
      title: 'Direzione & Visione Visiva',
      icon: '🎬',
      image: '/images/regista_cinematografico.jpg',
      color: '#ff007a',
      desc: 'Grammatica visiva, note di regia e inquadrature.'
    },
    {
      id: 'sceneggiatore',
      name: 'Sceneggiatore',
      title: 'Screenplay & Dialoghi',
      icon: '📜',
      image: '/images/sceneggiatore.jpg',
      color: '#f59e0b',
      desc: 'Scrittura in 3 atti, dialoghi e schede personaggi.'
    },
    {
      id: 'direttore_fotografia',
      name: 'DoP Fotografia',
      title: 'Luci, LUT & Prompt Visivi',
      icon: '🎥',
      image: '/images/direttore_fotografia.jpg',
      color: '#8b5cf6',
      desc: 'Lighting design, palette e prompt di generazione.'
    },
    {
      id: 'code_architect',
      name: 'Code Architect',
      title: 'Ingegneria & Refactor',
      icon: '⚙️',
      image: '/images/programmatoreAi.png',
      color: '#00d2ff',
      desc: 'Scrittura codice pulito, algoritmi e test unitari.'
    },
    {
      id: 'math1',
      name: 'Math Researcher',
      title: 'Scienza & Formule LaTeX',
      icon: '∑',
      image: '/images/matematicoAi.png',
      color: '#3fb950',
      desc: 'Formulari KaTeX, modelli computazionali e calcolo.'
    }
  ];

  return (
    <div className="home-dashboard-wrapper">
      {/* ── 0. Canvas Dinamico Cyber-Space / Rete Neurale Reattiva ── */}
      <TechSpaceCanvas isLight={isLight} />

      {/* ── 1. Top Bar Futuristica & Telemetria Live ── */}
      <header className="home-topbar">
        <div className="home-topbar-left">
          <div className="home-status-dot-pulse" title="Micro-kernel locale attivo" />
          <span className="home-kernel-badge">KERNEL v{updateState.currentVersion}</span>
          <span className="home-topbar-divider">•</span>
          <span className="home-topbar-pill">{updateState.activeRolesCount} Ruoli Attivi</span>
          <span className="home-topbar-divider">•</span>
          <span className="home-topbar-pill">Workspace: <code className="home-topbar-code">data/</code></span>
        </div>

        <div className="home-topbar-right">
          {updateState.updateAvailable ? (
            <button
              onClick={() => setShowUpdateModal(true)}
              className="home-update-pill alert"
              title="Ci sono nuovi aggiornamenti da GitHub"
            >
              <Sparkles size={11} className="pulse" />
              <span>{updateState.commitsBehind > 0 ? `${updateState.commitsBehind} Nuovi Commit` : 'Nuova Versione'}</span>
            </button>
          ) : (
            <button
              onClick={() => checkForUpdates(true)}
              disabled={updateState.checking}
              className="home-update-pill synced"
              title="Verifica stato aggiornamenti GitHub"
            >
              <RefreshCw size={10} className={updateState.checking ? 'spin' : ''} />
              <span>{updateState.checking ? 'Controllo...' : 'Sistema Sincronizzato'}</span>
            </button>
          )}

          <a
            href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
            target="_blank"
            rel="noreferrer"
            className="home-topbar-donate"
            title="Sostieni la ricerca e lo sviluppo di Sigma Studio"
          >
            <Heart size={11} fill="#f43f5e" color="#f43f5e" />
            <span>Sostieni</span>
          </a>

          <a
            href={updateState.htmlUrl || 'https://github.com/Sigmanih/SigmaStudio'}
            target="_blank"
            rel="noreferrer"
            className="home-topbar-github"
          >
            <ExternalLink size={11} />
            <span>GitHub</span>
          </a>
        </div>
      </header>

      {/* ── 2. Scrollable Body ── */}
      <div className="home-main-scrollable">

        {/* ── 3. Futuristic Hero Section con Thinking Orb Olografico ── */}
        <section className="home-hero-section">
          <div className="home-hero-spotlight" />
          <div className="home-hero-glow-back" />
          
          {/* Holographic Cognitive Core / Reactor Pod */}
          <div className="home-hero-orb-cluster" title="Sigma Cognitive Core — In ascolto e attivo">
            <div className="orb-radar-ring ring-outer" />
            <div className="orb-radar-ring ring-middle" />
            <div className="orb-radar-ring ring-inner" />
            <ThinkingOrb size={50} state="thinking" />
            <div className="orb-status-capsule">
              <span className="orb-pulse-led" />
              <span>SIGMA COGNITIVE CORE • ONLINE</span>
            </div>
          </div>

          <h1 className="home-hero-title">
            Crea, Progetta ed Esegui con <span className="gradient-shimmer-text">Agenti Intelligenti</span>
          </h1>

          <p className="home-hero-sub">
            Studio modulare ad alte prestazioni: reasoning multi-agente, editing di codice,
            generazione audiovisiva e progettazione hardware, tutto confinato e sovrano sulla tua macchina.
          </p>

          {/* Quick Prompt Superwrap con Idee Rapide in 1-Click */}
          <div className="home-prompt-superwrap">
            <form className="home-quick-prompt-bar cyber-beam-border" onSubmit={handleQuickPromptSubmit}>
              <div className="prompt-role-selector">
                <span className="role-dot pulse" />
                <select
                  value={selectedRole}
                  onChange={e => setSelectedRole(e.target.value)}
                  className="home-role-select"
                  title="Seleziona il ruolo dell'agente con cui iniziare"
                >
                  {FEATURED_ROLES.map(r => (
                    <option key={r.id} value={r.id}>{r.icon} {r.name}</option>
                  ))}
                </select>
              </div>

              <input
                type="text"
                className="home-prompt-input"
                placeholder={quickPrompt ? '' : `Es: ${INSPIRATION_PILLS[suggestionIdx].prompt}`}
                value={quickPrompt}
                onChange={e => setQuickPrompt(e.target.value)}
              />

              <button type="submit" className="home-prompt-submit-btn" title="Invia prompt e apri Chat">
                <span>Avvia Missione</span>
                <ArrowRight size={14} className="arrow-pulse" />
              </button>
            </form>

            {/* Quick Inspiration Pills */}
            <div className="home-prompt-chips">
              <span className="chips-label"><Sparkles size={11} color="#00d2ff" /> Idee Rapide:</span>
              {INSPIRATION_PILLS.map((chip, i) => (
                <button
                  key={i}
                  type="button"
                  className={`prompt-chip-btn ${selectedRole === chip.role && quickPrompt === chip.prompt ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedRole(chip.role);
                    setQuickPrompt(chip.prompt);
                  }}
                  title="Clicca per caricare questo obiettivo e ruolo"
                >
                  <span>{chip.label}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── 4. The Bento Launchpad con Dynamic Mouse Spotlight ── */}
        <section className="home-bento-grid">

          {/* Card 1: Sciame Agenti & Ruoli Specializzati (Area Grande) */}
          <div className="bento-card bento-agents card-beam-highlight" onMouseMove={handleCardMouseMove}>
            <div className="bento-header">
              <div className="bento-tag" style={{ color: '#00d2ff', borderColor: 'rgba(0, 210, 255, 0.3)' }}>
                <Brain size={12} />
                <span>TEAM COGNITIVO SPECIALIZZATO</span>
              </div>
              <button
                type="button"
                className="bento-action-link"
                onClick={() => openTab?.({ name: 'Ruoli AI' }, 'whitepapers_lib')}
              >
                <span>Vedi tutti i 20 ruoli</span>
                <ChevronRight size={13} />
              </button>
            </div>

            <h3 className="bento-title">Scegli un Agente ed Inizia a Lavorare</h3>
            <p className="bento-desc">
              Ogni agente possiede una specializzazione verticale, strumenti MCP dedicati e prompt ottimizzati.
            </p>

            <div className="bento-roles-cards">
              {FEATURED_ROLES.map(role => (
                <div
                  key={role.id}
                  className="role-mini-card"
                  onClick={() => handleStartChatWithRole(role.id)}
                  title={`Avvia una sessione con ${role.name}`}
                >
                  <div className="role-avatar-wrap" style={{ borderColor: role.color }}>
                    <img
                      src={role.image}
                      alt={role.name}
                      className="role-avatar-img"
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                    <span className="role-fallback-icon">{role.icon}</span>
                  </div>
                  <div className="role-details">
                    <div className="role-name" style={{ color: role.color }}>{role.name}</div>
                    <div className="role-title">{role.title}</div>
                    <div className="role-subdesc">{role.desc}</div>
                  </div>
                  <div className="role-open-btn">
                    <MessageSquare size={13} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 2: Developer Studio Core (Kernel Nativo) */}
          <div className="bento-card bento-dev" onMouseMove={handleCardMouseMove}>
            <div className="bento-header">
              <div className="bento-tag" style={{ color: '#eab308', borderColor: 'rgba(234, 179, 8, 0.3)' }}>
                <Terminal size={12} />
                <span>KERNEL CORE IDE</span>
              </div>
              <span className="bento-status-badge">Default: data/</span>
            </div>

            <h3 className="bento-title">Developer Studio</h3>
            <p className="bento-desc">
              Editor di codice avanzato, terminale, ispezione filesystem protetta in <code>data/</code> e gestione cartelle PC personalizzate.
            </p>

            <div className="bento-quick-buttons">
              <button
                type="button"
                className="bento-btn-primary"
                onClick={() => openTab?.({ name: 'Developer Sigma' }, 'developer_studio')}
              >
                <Terminal size={14} />
                <span>Apri Workspace IDE</span>
              </button>

              <button
                type="button"
                className="bento-btn-secondary"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('sigma_dev_open_graph'));
                  openTab?.({ name: 'Developer Sigma' }, 'developer_studio');
                }}
              >
                <Layers size={14} color="#00d2ff" />
                <span>Grafo Relazionale D3</span>
              </button>
            </div>
          </div>

          {/* Card 3: Creazione Multimediale & Audiovisiva */}
          <div className="bento-card bento-creative" onMouseMove={handleCardMouseMove}>
            <div className="bento-header">
              <div className="bento-tag" style={{ color: '#ff5064', borderColor: 'rgba(255, 80, 100, 0.3)' }}>
                <Palette size={12} />
                <span>LABORATORI CREATIVI</span>
              </div>
            </div>

            <h3 className="bento-title">Studio Audiovisivo & 3D</h3>
            <p className="bento-desc">
              Grafica 8K FLUX, Blender headless, storyboard da manga e sintetizzatore neurale.
            </p>

            <div className="bento-features-list">
              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'Creative Studio' }, 'creative_studio')}
              >
                <Palette size={15} color="#ff5064" />
                <div className="feat-text">
                  <span className="feat-title">Creative Lab 3D/2D</span>
                  <span className="feat-sub">FLUX 8K & Render Blender 3D</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>

              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'Video Studio' }, 'video_studio')}
              >
                <Clapperboard size={15} color="#ff007a" />
                <div className="feat-text">
                  <span className="feat-title">Video Studio & Manga</span>
                  <span className="feat-sub">Regia, montaggio scene e soundtrack</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>

              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'Audio Studio' }, 'audio_studio')}
              >
                <Mic size={15} color="#bc8cff" />
                <div className="feat-text">
                  <span className="feat-title">Voice & Audio Studio</span>
                  <span className="feat-sub">TTS neurale e radio FM procedurale</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>
            </div>
          </div>

          {/* Card 4: Ingegneria, Hardware & Modelli */}
          <div className="bento-card bento-engineering" onMouseMove={handleCardMouseMove}>
            <div className="bento-header">
              <div className="bento-tag" style={{ color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                <CircuitBoard size={12} />
                <span>HARDWARE & MODELLI</span>
              </div>
            </div>

            <h3 className="bento-title">Ingegneria Elettronica & SLM</h3>
            <p className="bento-desc">
              Progettazione PCB KiCad, telemetria micro-kernel Rust e gestione modelli GGUF locali.
            </p>

            <div className="bento-features-list">
              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'KiCad Lab' }, 'kicad_lab')}
              >
                <CircuitBoard size={15} color="#10b981" />
                <div className="feat-text">
                  <span className="feat-title">KiCad PCB Designer</span>
                  <span className="feat-sub">Schematici, routing 2D e viewer 3D</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>

              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'Monitor Hardware' }, 'hardware_lab')}
              >
                <Zap size={15} color="#eab308" />
                <div className="feat-text">
                  <span className="feat-title">Hardware Monitor & Rust</span>
                  <span className="feat-sub">VRAM, KV-cache ed engine telemetrico</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>

              <button
                type="button"
                className="bento-feature-item"
                onClick={() => openTab?.({ name: 'Modelli' }, 'model_hub')}
              >
                <DownloadCloud size={15} color="#00d2ff" />
                <div className="feat-text">
                  <span className="feat-title">Model Hub Hugging Face</span>
                  <span className="feat-sub">Catalogo GGUF e quantizzazione locale</span>
                </div>
                <ChevronRight size={13} className="feat-arrow" />
              </button>
            </div>
          </div>

        </section>

        {/* ── 5. HUD Telemetry Strip: I Valori Fondamentali di Sigma Studio ── */}
        <section className="home-hud-strip">
          <div className="hud-metric-card hud-waveform-card">
            <div className="hud-metric-icon pulse-cyan" style={{ color: '#00d2ff', background: 'rgba(0, 210, 255, 0.1)' }}>
              <Activity size={18} />
            </div>
            <div className="hud-metric-info">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <span className="hud-metric-val">100% Locale • Zero Cloud</span>
                <span className="hud-live-tag">LIVE</span>
              </div>
              <span className="hud-metric-lbl">Nessuna telemetria esterna né costi per token</span>
              <div className="hud-wave-container">
                <svg className="hud-wave-svg" viewBox="0 0 160 16" preserveAspectRatio="none">
                  <path
                    className="hud-wave-path"
                    d="M0,8 L20,8 L30,2 L40,14 L50,8 L70,8 L80,3 L90,13 L100,8 L130,8 L140,4 L150,12 L160,8"
                  />
                </svg>
              </div>
            </div>
          </div>

          <div className="hud-metric-card">
            <div className="hud-metric-icon" style={{ color: '#3fb950', background: 'rgba(63, 185, 80, 0.1)' }}>
              <Cpu size={18} />
            </div>
            <div className="hud-metric-info">
              <span className="hud-metric-val">Pi 5 & PC Ready</span>
              <span className="hud-metric-lbl">Micro-kernel ottimizzato per CPU pura e GPU dedicata</span>
            </div>
          </div>

          <div className="hud-metric-card">
            <div className="hud-metric-icon" style={{ color: '#bc8cff', background: 'rgba(188, 140, 255, 0.1)' }}>
              <Brain size={18} />
            </div>
            <div className="hud-metric-info">
              <span className="hud-metric-val">20 Ruoli Specializzati</span>
              <span className="hud-metric-lbl">Dalla regia cinematografica all'ingegneria software</span>
            </div>
          </div>

          <div className="hud-metric-card">
            <div className="hud-metric-icon" style={{ color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)' }}>
              <HardDrive size={18} />
            </div>
            <div className="hud-metric-info">
              <span className="hud-metric-val">Protocollo MCP Nativo</span>
              <span className="hud-metric-lbl">14 tool server: git, lint, test, docker, filesystem</span>
            </div>
          </div>
        </section>


        {/* ── 6. Minimal Footer ── */}
        <footer className="home-footer">
          <div className="home-footer-left">
            <button
              onClick={() => openTab?.({ path: 'README.md', filename: 'README.md' }, 'editor')}
              className="home-footer-link"
            >
              📖 Guida Utente (README)
            </button>
            <span className="home-footer-dot">•</span>
            <button
              onClick={() => openTab?.({ path: 'ARCHITECTURE.md', filename: 'ARCHITECTURE.md' }, 'editor')}
              className="home-footer-link"
            >
              🏛️ Architettura di Sistema
            </button>
            <span className="home-footer-dot">•</span>
            <a
              href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
              target="_blank"
              rel="noreferrer"
              className="home-footer-link donate"
            >
              <Heart size={10} fill="#f43f5e" color="#f43f5e" />
              <span>Sostieni lo sviluppo</span>
            </a>
          </div>

          <div className="home-footer-right">
            <span>Sigma AI Studio v{updateState.currentVersion} • Sovranità Cognitiva Locale</span>
          </div>
        </footer>

      </div>

      {/* ── 7. Modale Aggiornamenti Elegante & Non Invasivo ── */}
      {showUpdateModal && (
        <div className="home-modal-backdrop" onClick={() => setShowUpdateModal(false)}>
          <div className="home-modal-card" onClick={e => e.stopPropagation()}>
            <div className="home-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={16} color="#00d2ff" />
                <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800 }}>Aggiornamenti di Sistema & Ruoli</h4>
              </div>
              <button
                type="button"
                className="home-modal-close"
                onClick={() => setShowUpdateModal(false)}
              >
                <X size={15} />
              </button>
            </div>

            <div className="home-modal-body">
              <div className="modal-commit-summary">
                <span className="commit-badge">
                  {updateState.commitsBehind > 0 ? `${updateState.commitsBehind} commit dietro a origin/main` : 'Nuova release disponibile'}
                </span>
                <span className="commit-sha">
                  {updateState.localCommit} → {updateState.remoteCommit}
                </span>
              </div>

              {updateState.newCommits.length > 0 ? (
                <div className="modal-commits-list">
                  {updateState.newCommits.map(c => (
                    <div key={c.sha} className="modal-commit-item">
                      <code>{c.sha}</code>
                      <span className="modal-commit-msg">{c.message}</span>
                      <span className="modal-commit-date">{c.date}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                  {updateState.releaseNotes || 'Nuovi miglioramenti kernel e definizioni dei ruoli disponibili nel repository ufficiale.'}
                </p>
              )}

              {updateState.applyResult && (
                <div className={`modal-apply-alert ${updateState.applyResult.success ? 'success' : 'error'}`}>
                  {updateState.applyResult.success ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                  <span>{updateState.applyResult.message}</span>
                </div>
              )}
            </div>

            <div className="home-modal-footer">
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={() => setShowUpdateModal(false)}
              >
                Chiudi
              </button>
              <button
                type="button"
                className="btn-modal-apply"
                onClick={applyUpdate}
                disabled={updateState.applying}
              >
                {updateState.applying ? <RefreshCw size={12} className="spin" /> : <Download size={12} />}
                <span>{updateState.applying ? 'Download in corso...' : 'Scarica & Aggiorna Ora'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}