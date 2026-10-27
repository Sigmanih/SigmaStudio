import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Terminal, Palette, Clapperboard, CircuitBoard, Zap, CloudDownload, Sparkles,
  ArrowRight, RefreshCw, ExternalLink, Heart, Layers, X, Cpu, MemoryStick,
  Gauge, History, MessageSquare, Orbit
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import CyberSpace3DCanvas, { roleInitials } from './common/CyberSpace3DCanvas';
import { resolveRoleLucide } from './common/roleIcons';
import { loadSessions, formatSessionTime } from './Chat/chatStorage';

// ==============================================================================
// Helper di risoluzione visiva per i ruoli caricati dinamicamente
// ==============================================================================
const ROLE_PALETTE = ['#00d2ff', '#ff007a', '#7c5bf0', '#10b981', '#f59e0b', '#ec4899', '#38bdf8', '#a855f7', '#06b6d4', '#14b8a6'];

const QUALITY_KEY = 'sigma_home_3d_quality';
const QUALITY_CYCLE = ['auto', 'high', 'lite', 'off'];
const QUALITY_LABEL = { auto: 'Auto', high: 'Alta', lite: 'Leggera', off: 'Spenta' };

const DOCK_ITEMS = [
  { id: 'developer_studio', name: 'Developer Sigma', label: 'Developer Studio', Icon: Terminal, color: '#eab308' },
  { id: 'kicad_lab', name: 'KiCad Lab', label: 'KiCad Lab', Icon: CircuitBoard, color: '#10b981' },
  { id: 'creative_studio', name: 'Creative Studio', label: 'Creative Studio', Icon: Palette, color: '#ff5064' },
  { id: 'video_studio', name: 'Video Studio', label: 'Video Studio', Icon: Clapperboard, color: '#ff007a' },
  { id: 'hardware_lab', name: 'Monitor Hardware', label: 'Monitor Hardware', Icon: Zap, color: '#00d2ff' },
  { id: 'model_hub', name: 'Modelli', label: 'Modelli', Icon: CloudDownload, color: '#bc8cff' },
  { id: 'developer_studio', name: 'Developer Sigma', label: 'Grafo delle dipendenze', Icon: Layers, color: '#38bdf8', event: 'sigma_dev_open_graph' }
];

const readQualityPref = () => {
  try {
    const saved = localStorage.getItem(QUALITY_KEY);
    return QUALITY_CYCLE.includes(saved) ? saved : 'auto';
  } catch {
    return 'auto';
  }
};

const resolveRoleImage = (role) => {
  if (!role) return '/images/default.png';
  if (role.image && role.image !== '/images/default.png') return role.image;
  const text = `${role.id || ''} ${role.filename || ''} ${role.name || ''} ${role.role || ''} ${role.category || ''}`.toLowerCase();
  if (text.includes('regis')) return '/images/regista_cinematografico.jpg';
  if (text.includes('scenegg')) return '/images/sceneggiatore.jpg';
  if (text.includes('fotograf') || text.includes('dop') || text.includes('direttore_fotografia')) return '/images/direttore_fotografia.jpg';
  if (text.includes('medic') || text.includes('clin') || text.includes('salut') || text.includes('biol')) return '/images/medico_ai.jpg';
  if (text.includes('design') || text.includes('grafic') || text.includes('visual') || text.includes('art') || text.includes('sound') || text.includes('audio') || text.includes('montat')) return '/images/designer_ai.jpg';
  if (text.includes('avvocat') || text.includes('leg') || text.includes('giur') || text.includes('finanz') || text.includes('quant') || text.includes('proof') || text.includes('review') || text.includes('audit')) return '/images/quant_law_ai.jpg';
  if (text.includes('matemat') || text.includes('fisic') || text.includes('scienz') || text.includes('statist')) return '/images/matematicoAi.png';
  if (text.includes('programm') || text.includes('cod') || text.includes('svilupp') || text.includes('dev') || text.includes('test')) return '/images/programmatoreAi.png';
  if (text.includes('hardware') || text.includes('kicad') || text.includes('elettron') || text.includes('circuit')) return '/images/hardware_cluster_lab.jpg';
  if (text.includes('arch') || text.includes('kernel') || text.includes('admin') || text.includes('sistem')) return '/images/agente0.png';
  if (text.includes('sigma') || text.includes('assistan')) return '/images/sigma_logo_harmonic_flow.jpg';
  return '/images/default.png';
};

const resolveRolePrompt = (role) => {
  const id = (role.id || role.filename || '').toLowerCase();
  if (id.includes('kicad') || id.includes('hardware')) {
    return 'Progetta uno schematico KiCad per un controller ESP32 con alimentazione switching a 5V e filtri EMC.';
  }
  if (id.includes('regis')) {
    return 'Imposta la direzione visiva e la lista inquadrature per una sequenza notturna cyberpunk con neon e pioggia.';
  }
  if (id.includes('scenegg')) {
    return 'Scrivi la struttura in 3 atti e il dialogo di apertura per una storia thriller noir tra un ingegnere e un androide.';
  }
  if (id.includes('fotograf') || id.includes('dop')) {
    return 'Crea una color palette anamorfica teal & orange con lighting ratio 4:1 e note ottiche 35mm T1.5.';
  }
  if (id.includes('cod') || id.includes('dev') || id.includes('programm')) {
    return 'Scrivi un modulo ad alte prestazioni in Rust con architettura a zero-allocazioni ed esegui i test unitari.';
  }
  if (id.includes('math') || id.includes('fisic') || id.includes('professor')) {
    return 'Deriva la formulazione analitica per un filtro di Kalman esteso con matrici formattate in KaTeX.';
  }
  if (id.includes('medic')) {
    return 'Riassumi i protocolli diagnostici basati sulle più recenti linee guida con linguaggio chiaro ed evidenze.';
  }
  if (id.includes('sound') || id.includes('audio')) {
    return 'Progetta il paesaggio sonoro per un ambiente urbano distopico con frequenze sub-bass e texture analogiche.';
  }
  if (id.includes('admin') || id.includes('architect')) {
    return 'Pianifica l\'orchestrazione multi-agente per un audit completo del sistema e mappatura delle dipendenze.';
  }
  return 'Avvia una sessione specializzata focalizzata sui tuoi obiettivi operativi e linee guida.';
};

const formatGb = (value) => (Number.isFinite(value) ? value.toLocaleString('it-IT', { maximumFractionDigits: 1 }) : '–');

const RoleAvatar = ({ role, className }) => (
  <span className={className}>
    {role.image && role.image !== '/images/default.png'
      ? <img src={role.image} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
      : roleInitials(role.name)}
  </span>
);

const loadRecentChats = () => loadSessions()
  .filter(s => (s.messageCount || (Array.isArray(s.messages) ? s.messages.length : 0)) > 0)
  .sort((a, b) => new Date(b.updatedAt || b.lastMessageAt || 0) - new Date(a.updatedAt || a.lastMessageAt || 0))
  .slice(0, 3);

export default function WelcomeDashboard({ modules = [], openTab }) {
  const { theme, manifesti: contextManifesti } = useApp();
  // Anche "cream" e' un tema chiaro: prima la plancia restava scura sotto un'interfaccia chiara
  const isLight = theme === 'light' || theme === 'cream';

  // Ruoli dinamici caricati dal backend
  const [loadedRoles, setLoadedRoles] = useState([]);
  const [selectedRole, setSelectedRole] = useState('sigma_architect');
  const [quickPrompt, setQuickPrompt] = useState('');
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  const [qualityPref, setQualityPref] = useState(readQualityPref);
  const [resolvedQuality, setResolvedQuality] = useState(null);
  const [systemStats, setSystemStats] = useState(null);
  const [recentChats, setRecentChats] = useState(loadRecentChats);

  // Caricamento Ruoli
  useEffect(() => {
    let cancel = false;
    const loadDynamicRoles = async () => {
      if (Array.isArray(contextManifesti) && contextManifesti.length > 0) {
        if (!cancel) setLoadedRoles(contextManifesti);
        return;
      }

      try {
        const res = await fetch('/api/list_manifesti');
        if (res.ok) {
          const data = await res.json();
          const items = data.manifesti || data.ruoli || data.files || [];
          if (!cancel && Array.isArray(items) && items.length > 0) {
            setLoadedRoles(items);
            return;
          }
        }
      } catch (err) {}

      try {
        const resHub = await fetch('/api/ruoli/hub');
        if (resHub.ok) {
          const dataHub = await resHub.json();
          if (!cancel && Array.isArray(dataHub.catalog) && dataHub.catalog.length > 0) {
            setLoadedRoles(dataHub.catalog);
          }
        }
      } catch (e) {}
    };

    loadDynamicRoles();
    return () => { cancel = true; };
  }, [contextManifesti]);

  // Telemetria reale al posto dei valori decorativi: si interrompe a scheda
  // nascosta per non tenere occupato il backend sul Pi.
  useEffect(() => {
    let cancel = false;
    const poll = async () => {
      if (document.hidden) return;
      try {
        const res = await fetch('/api/hardware/status');
        if (!res.ok) return;
        const data = await res.json();
        if (!cancel && data && data.success && data.hardware) setSystemStats(data.hardware);
      } catch (e) {}
    };
    poll();
    const timer = setInterval(poll, 8000);
    return () => { cancel = true; clearInterval(timer); };
  }, []);

  // Le chat recenti vivono in localStorage: si aggiornano quando la chat le salva
  useEffect(() => {
    const refresh = () => setRecentChats(loadRecentChats());
    window.addEventListener('sigma-chat-sessions-updated', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener('sigma-chat-sessions-updated', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, []);

  // Ruoli arricchiti per l'ambiente 3D
  const enrichedRoles = useMemo(() => {
    if (!loadedRoles || loadedRoles.length === 0) {
      return [
        {
          id: 'sigma_architect',
          name: 'Sigma Architect',
          title: 'Architetto & Core Swarm',
          image: '/images/agente0.png',
          color: '#7c5bf0',
          desc: 'Pianificazione di sistema, orchestrazione e sintesi.',
          category: 'Architettura & Kernel',
          prompt: resolveRolePrompt({ id: 'sigma_architect' })
        },
        {
          id: 'code_architect',
          name: 'Code Architect',
          title: 'Ingegneria & Refactor',
          image: '/images/programmatoreAi.png',
          color: '#00d2ff',
          desc: 'Scrittura codice pulito, algoritmi e test unitari.',
          category: 'Sviluppo & Codice',
          prompt: resolveRolePrompt({ id: 'code_architect' })
        },
        {
          id: 'regista_cinematografico',
          name: 'Regista',
          title: 'Direzione & Visione Visiva',
          image: '/images/regista_cinematografico.jpg',
          color: '#ff007a',
          desc: 'Grammatica visiva, note di regia e inquadrature.',
          category: 'Comunicazione & Creatività',
          prompt: resolveRolePrompt({ id: 'regista_cinematografico' })
        }
      ];
    }

    return loadedRoles.map((r, i) => {
      const id = r.id || (r.filename ? r.filename.replace(/\.md$/i, '') : `ruolo_${i}`);
      const category = r.category || 'Specializzazione Cognitiva';
      const enriched = {
        id,
        filename: r.filename || `${id}.md`,
        name: r.name || r.title || id,
        title: r.role || r.title || category,
        icon: r.icon,
        image: resolveRoleImage(r),
        // Il colore di dominio del manifesto ha la precedenza: la palette ciclica
        // ripeteva le stesse tinte su agenti diversi.
        color: r.domainColor || ROLE_PALETTE[i % ROLE_PALETTE.length],
        desc: r.description || r.desc || 'Agente intelligente con competenze verticali e tool dedicati.',
        category,
        prompt: resolveRolePrompt({ ...r, id })
      };
      return enriched;
    });
  }, [loadedRoles]);

  useEffect(() => {
    if (enrichedRoles.length > 0 && !enrichedRoles.find(r => r.id === selectedRole)) {
      setSelectedRole(enrichedRoles[0].id);
    }
  }, [enrichedRoles, selectedRole]);

  const inspirationRoles = useMemo(() => enrichedRoles.slice(0, 5), [enrichedRoles]);

  const [suggestionIdx, setSuggestionIdx] = useState(0);
  useEffect(() => {
    if (inspirationRoles.length === 0) return;
    const timer = setInterval(() => {
      setSuggestionIdx(prev => (prev + 1) % inspirationRoles.length);
    }, 6000);
    return () => clearInterval(timer);
  }, [inspirationRoles]);

  // Stato Aggiornamenti Git
  const [updateState, setUpdateState] = useState({
    loading: true,
    checking: false,
    updateAvailable: false,
    currentVersion: '0.9.0',
    commitsBehind: 0,
    newCommits: [],
    localCommit: '',
    remoteCommit: '',
    lastChecked: null,
    applying: false,
    applyResult: null
  });

  const checkForUpdates = useCallback(async (isManual = false) => {
    if (isManual) {
      setUpdateState(p => ({ ...p, checking: true, applyResult: null }));
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
          currentVersion: data.current_version || '0.9.0',
          commitsBehind: data.commits_behind || 0,
          newCommits: Array.isArray(data.new_commits) ? data.new_commits : [],
          localCommit: data.local_commit || '',
          remoteCommit: data.remote_commit || '',
          lastChecked: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }));
      } else {
        setUpdateState(p => ({ ...p, loading: false, checking: false }));
      }
    } catch (e) {
      setUpdateState(p => ({ ...p, loading: false, checking: false }));
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
          message: data.message || 'Aggiornamento applicato con successo!'
        },
        updateAvailable: data.success ? false : p.updateAvailable
      }));
      setTimeout(() => checkForUpdates(false), 2000);
    } catch (err) {
      setUpdateState(p => ({
        ...p,
        applying: false,
        applyResult: { success: false, message: `Errore: ${err.message}` }
      }));
    }
  };

  useEffect(() => {
    checkForUpdates(false);
  }, [checkForUpdates]);

  // Agente selezionato e focalizzato nell'ambiente 3D
  const [focusedAgent, setFocusedAgent] = useState(null);

  const focusRole = useCallback((role, withPrompt = true) => {
    if (!role) return;
    setSelectedRole(role.id);
    setFocusedAgent(role);
    if (withPrompt && role.prompt) setQuickPrompt(role.prompt);
  }, []);

  const cycleQuality = () => {
    const next = QUALITY_CYCLE[(QUALITY_CYCLE.indexOf(qualityPref) + 1) % QUALITY_CYCLE.length];
    setQualityPref(next);
    setResolvedQuality(null);
    try { localStorage.setItem(QUALITY_KEY, next); } catch (e) {}
  };

  const handleQualityResolved = useCallback((level) => setResolvedQuality(level), []);

  // Avvio Chat istantaneo
  const handleStartChatWithRole = (roleId, customText = '') => {
    try {
      if (roleId) {
        localStorage.setItem('sigma_active_role', roleId);
      }
      if (customText && customText.trim()) {
        localStorage.setItem('sigma_pending_chat_prompt', customText.trim());
      }
    } catch (e) {}
    if (openTab) {
      openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
    }
    // Evento dopo openTab: se la chat e' gia' montata legge subito i valori,
    // altrimenti li trova in localStorage al primo montaggio.
    window.dispatchEvent(new CustomEvent('sigma-chat-select-role', { detail: roleId }));
  };

  const handleOpenRecentChat = (sessionId) => {
    if (openTab) openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
    window.dispatchEvent(new CustomEvent('sigma-chat-switch-session', { detail: sessionId }));
  };

  const handleQuickPromptSubmit = (e) => {
    e.preventDefault();
    if (!quickPrompt.trim()) return;
    handleStartChatWithRole(selectedRole, quickPrompt);
    setQuickPrompt('');
  };

  const handleAgentDialogueSubmit = (e) => {
    e.preventDefault();
    const roleId = focusedAgent?.id || selectedRole;
    const promptToSend = quickPrompt.trim() || focusedAgent?.prompt || '';
    handleStartChatWithRole(roleId, promptToSend);
    setQuickPrompt('');
  };

  const currentPlaceholder = inspirationRoles[suggestionIdx]?.prompt ||
    'Scrivi cosa vuoi fare, oppure scegli un agente nella plancia…';

  const selectedRoleObj = enrichedRoles.find(r => r.id === selectedRole);
  const SelectedRoleIcon = resolveRoleLucide(selectedRoleObj || {});

  const gpu = Array.isArray(systemStats?.gpu) ? systemStats.gpu.find(g => !g.is_integrated) || systemStats.gpu[0] : null;
  const ram = systemStats?.ram;
  const cpu = systemStats?.cpu;
  const gpuTitle = Array.isArray(systemStats?.gpu)
    ? systemStats.gpu.map(g => `${g.name}: ${g.gpu_util_pct ?? '–'}% · VRAM ${formatGb((g.vram_used_mb || 0) / 1024)}/${formatGb((g.vram_total_mb || 0) / 1024)} GB`).join('\n')
    : '';

  const effectiveQuality = resolvedQuality || (qualityPref === 'auto' ? null : qualityPref);
  const qualityTitle = qualityPref === 'auto'
    ? `Grafica automatica${effectiveQuality ? `: ${QUALITY_LABEL[effectiveQuality]}` : ''}. Clicca per cambiare.`
    : `Grafica ${QUALITY_LABEL[qualityPref]}. Clicca per cambiare.`;

  return (
    <div
      className={`holodeck-viewport ${focusedAgent ? 'is-focused' : ''} ${qualityPref === 'off' ? 'is-static' : ''}`}
      data-agent-component="CyberHolodeck"
      style={focusedAgent ? { '--agent-glow': focusedAgent.color } : undefined}
    >

      {/* ── 0. Plancia 3D, o sfondo statico quando la grafica e' spenta ── */}
      {qualityPref === 'off' ? (
        <div className="holodeck-static-bg" aria-hidden="true" />
      ) : (
        <CyberSpace3DCanvas
          isLight={isLight}
          roles={enrichedRoles}
          selectedAgentId={focusedAgent ? focusedAgent.id : ''}
          quality={qualityPref}
          onQualityResolved={handleQualityResolved}
          onSelectAgent={(agent) => {
            if (agent) focusRole(agent);
            else setFocusedAgent(null);
          }}
          interactive={true}
        />
      )}

      <div className="holodeck-hud-overlay">

        {/* Barra superiore: identita', stato reale del sistema, azioni */}
        <header className="holodeck-topbar">
          <div className="holodeck-hud-tag">
            <img src="/images/SigmaStudio.png" alt="" className="holodeck-hud-logo" />
            <span className="holodeck-brand">Sigma Studio</span>
            <span className="holodeck-version">v{updateState.currentVersion}</span>
            <span className="holodeck-hud-sep" aria-hidden="true" />
            <span className="holodeck-hud-meta">{enrichedRoles.length} agenti</span>
          </div>

          {systemStats && (
            <div className="holodeck-sysbar" aria-label="Stato del sistema">
              {cpu && (
                <span className="holodeck-sys-chip" title={cpu.name || 'CPU'}>
                  <Cpu size={13} aria-hidden="true" />
                  <span className="sys-chip-label">CPU</span>
                  <strong>{Math.round(cpu.usage_pct ?? cpu.util_pct ?? 0)}%</strong>
                </span>
              )}
              {ram && (
                <span className="holodeck-sys-chip" title={`RAM ${formatGb(ram.used_gb)} di ${formatGb(ram.total_gb)} GB`}>
                  <MemoryStick size={13} aria-hidden="true" />
                  <span className="sys-chip-label">RAM</span>
                  <strong>{formatGb(ram.used_gb)}/{formatGb(ram.total_gb)} GB</strong>
                </span>
              )}
              {gpu && (
                <span className="holodeck-sys-chip is-gpu" title={gpuTitle}>
                  <Gauge size={13} aria-hidden="true" />
                  <span className="sys-chip-label">GPU</span>
                  <strong>{Math.round(gpu.gpu_util_pct ?? 0)}% · {formatGb((gpu.vram_used_mb || 0) / 1024)}/{formatGb((gpu.vram_total_mb || 0) / 1024)} GB</strong>
                </span>
              )}
            </div>
          )}

          <div className="holodeck-hud-actions">
            <button
              type="button"
              onClick={cycleQuality}
              className="holodeck-action-pill"
              title={qualityTitle}
            >
              <Orbit size={13} aria-hidden="true" />
              <span className="pill-text">3D: {QUALITY_LABEL[qualityPref]}</span>
            </button>

            {updateState.updateAvailable ? (
              <button
                type="button"
                onClick={() => setShowUpdateModal(true)}
                className="holodeck-action-pill alert"
                title="Nuovi aggiornamenti disponibili"
              >
                <Sparkles size={13} aria-hidden="true" />
                <span className="pill-text">{updateState.commitsBehind > 0 ? `${updateState.commitsBehind} aggiornamenti` : 'Nuova versione'}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => checkForUpdates(true)}
                disabled={updateState.checking}
                className="holodeck-action-pill"
                title={updateState.lastChecked ? `Aggiornato · controllo delle ${updateState.lastChecked}. Clicca per ricontrollare.` : 'Controlla aggiornamenti'}
              >
                <RefreshCw size={13} className={updateState.checking ? 'spin' : ''} aria-hidden="true" />
                <span className="pill-text">{updateState.checking ? 'Controllo…' : 'Aggiornato'}</span>
              </button>
            )}

            <a
              href="https://www.paypal.com/ncp/payment/RP2DYUXVJ8FRC"
              target="_blank"
              rel="noreferrer"
              className="holodeck-action-pill icon-only"
              title="Sostieni Sigma Studio"
              aria-label="Sostieni Sigma Studio"
            >
              <Heart size={14} className="heart-icon" aria-hidden="true" />
            </a>

            <a
              href="https://github.com/Sigmanih/SigmaStudio"
              target="_blank"
              rel="noreferrer"
              className="holodeck-action-pill icon-only"
              title="Sigma Studio su GitHub"
              aria-label="Sigma Studio su GitHub"
            >
              <ExternalLink size={14} aria-hidden="true" />
            </a>
          </div>
        </header>

        {/* Riprendi da dove eri: le ultime chat con messaggi */}
        {recentChats.length > 0 && !focusedAgent && (
          <aside className="holodeck-recent" aria-label="Chat recenti">
            <div className="holodeck-recent-title">
              <History size={13} aria-hidden="true" />
              <span>Riprendi</span>
            </div>
            {recentChats.map(s => (
              <button
                key={s.id}
                type="button"
                className="holodeck-recent-item"
                onClick={() => handleOpenRecentChat(s.id)}
                title={s.name}
              >
                <MessageSquare size={13} aria-hidden="true" />
                <span className="recent-name">{s.name}</span>
                <span className="recent-time">{formatSessionTime(s.updatedAt || s.lastMessageAt)}</span>
              </button>
            ))}
          </aside>
        )}

        {focusedAgent ? (
          /* Agente raggiunto nella plancia: dialogo diretto */
          <div className="holodeck-dialogue-pod">
            <div className="dialogue-agent-header">
              <div className="dialogue-agent-meta">
                <RoleAvatar role={focusedAgent} className="dialogue-avatar-box" />
                <div className="dialogue-agent-info">
                  <div className="dialogue-agent-name-row">
                    <span className="dialogue-agent-name">{focusedAgent.name}</span>
                    <span className="dialogue-status-tag">
                      <span className="dialogue-status-pulse" />
                      Pronto
                    </span>
                  </div>
                  <span className="dialogue-agent-role">{focusedAgent.title}</span>
                </div>
              </div>

              <button
                type="button"
                className="dialogue-reset-btn"
                onClick={() => setFocusedAgent(null)}
                title="Torna alla vista generale della plancia"
              >
                <X size={13} aria-hidden="true" />
                <span>Vista generale</span>
              </button>
            </div>

            {focusedAgent.prompt && quickPrompt !== focusedAgent.prompt && (
              <button
                type="button"
                className="dialogue-chip-btn"
                onClick={() => setQuickPrompt(focusedAgent.prompt)}
                title={focusedAgent.prompt}
              >
                <Sparkles size={13} aria-hidden="true" />
                <span className="chip-label">Suggerimento:</span>
                <span className="chip-text">{focusedAgent.prompt}</span>
              </button>
            )}

            <form className="dialogue-form" onSubmit={handleAgentDialogueSubmit}>
              <input
                type="text"
                className="dialogue-input"
                placeholder={`Chiedi a ${focusedAgent.name}…`}
                value={quickPrompt}
                onChange={e => setQuickPrompt(e.target.value)}
                aria-label={`Messaggio per ${focusedAgent.name}`}
                autoFocus
              />
              <button type="submit" className="dialogue-submit-btn">
                <span>Avvia chat</span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            </form>
          </div>
        ) : (
          /* Barra inferiore: dock dei laboratori + barra dei comandi */
          <footer className="holodeck-bottom-deck">

            <nav className="holodeck-module-dock" aria-label="Laboratori">
              {DOCK_ITEMS.map(item => (
                <button
                  key={item.label}
                  type="button"
                  className="holodeck-dock-btn"
                  style={{ '--dock-glow': item.color }}
                  data-label={item.label}
                  aria-label={item.label}
                  onClick={() => {
                    if (item.event) window.dispatchEvent(new CustomEvent(item.event));
                    openTab?.({ name: item.name }, item.id);
                  }}
                >
                  <item.Icon size={18} color={item.color} aria-hidden="true" />
                </button>
              ))}
            </nav>

            <div className="holodeck-omnibar-cluster">
              {inspirationRoles.length > 0 && (
                <div className="holodeck-floating-chips">
                  {inspirationRoles.map(role => {
                    const ChipIcon = resolveRoleLucide(role);
                    return (
                      <button
                        key={role.id}
                        type="button"
                        className={`holodeck-chip-btn ${selectedRole === role.id ? 'active' : ''}`}
                        style={{ '--chip-color': role.color }}
                        onClick={() => focusRole(role)}
                        title={role.prompt}
                      >
                        <ChipIcon size={13} aria-hidden="true" />
                        <span>{role.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              <form
                className="holodeck-omnibar-form"
                onSubmit={handleQuickPromptSubmit}
                style={selectedRoleObj ? { '--omni-color': selectedRoleObj.color } : undefined}
              >
                <label className="holodeck-role-capsule" title="Agente che ricevera' il messaggio">
                  <SelectedRoleIcon size={15} aria-hidden="true" />
                  <select
                    value={selectedRole}
                    onChange={e => {
                      const match = enrichedRoles.find(r => r.id === e.target.value);
                      if (match) focusRole(match, false);
                      else setSelectedRole(e.target.value);
                    }}
                    className="holodeck-role-select"
                    aria-label="Agente"
                  >
                    {enrichedRoles.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </label>

                <input
                  type="text"
                  className="holodeck-prompt-input"
                  placeholder={currentPlaceholder}
                  value={quickPrompt}
                  onChange={e => setQuickPrompt(e.target.value)}
                  aria-label="Messaggio per l'agente"
                />

                <button type="submit" className="holodeck-submit-btn" disabled={!quickPrompt.trim()}>
                  <span>Avvia chat</span>
                  <ArrowRight size={15} aria-hidden="true" />
                </button>
              </form>
            </div>

            {/* Spazio speculare al dock: tiene la barra dei comandi al centro */}
            <div className="holodeck-deck-spacer" aria-hidden="true" />
          </footer>
        )}

      </div>

      {/* Modale Aggiornamenti Git */}
      {showUpdateModal && (
        <div className="home-modal-backdrop" onClick={() => setShowUpdateModal(false)}>
          <div className="home-modal-card" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="home-update-title">
            <div className="home-modal-header">
              <div className="home-modal-title">
                <Sparkles size={16} aria-hidden="true" />
                <h4 id="home-update-title">Aggiornamenti di sistema e ruoli</h4>
              </div>
              <button
                type="button"
                className="home-modal-close"
                onClick={() => setShowUpdateModal(false)}
                aria-label="Chiudi"
              >
                <X size={15} />
              </button>
            </div>

            <div className="home-modal-body">
              <div className="modal-commit-summary">
                <span className="commit-badge">
                  {updateState.commitsBehind > 0 ? `${updateState.commitsBehind} commit da origin/main` : 'Nuova release disponibile'}
                </span>
                <span className="commit-sha">
                  {updateState.localCommit} → {updateState.remoteCommit}
                </span>
              </div>

              {updateState.newCommits.length > 0 && (
                <div className="modal-commits-list">
                  {updateState.newCommits.map(c => (
                    <div key={c.sha} className="modal-commit-item">
                      <code>{c.sha}</code>
                      <span className="modal-commit-msg">{c.message}</span>
                      <span className="modal-commit-date">{c.date}</span>
                    </div>
                  ))}
                </div>
              )}

              {updateState.applyResult && (
                <div className={`modal-apply-alert ${updateState.applyResult.success ? 'success' : 'error'}`}>
                  {updateState.applyResult.message}
                </div>
              )}
            </div>

            <div className="home-modal-footer">
              <button
                type="button"
                className="home-modal-btn secondary"
                onClick={() => setShowUpdateModal(false)}
              >
                Chiudi
              </button>

              <button
                type="button"
                className="home-modal-btn primary"
                onClick={applyUpdate}
                disabled={updateState.applying}
              >
                {updateState.applying ? (
                  <>
                    <RefreshCw size={13} className="spin" />
                    <span>Aggiornamento in corso…</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={13} />
                    <span>Applica aggiornamenti</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
