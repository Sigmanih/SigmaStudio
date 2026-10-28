import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Terminal, Palette, Clapperboard, CircuitBoard, CloudDownload, Sparkles, ChevronDown,
  RefreshCw, ExternalLink, Heart, Layers, X, Cpu, MemoryStick,
  Gauge, History, MessageSquare, Orbit, Calendar, Settings, Trash2, Music, Send,
  Paperclip, Mic, MicOff, AudioLines, FileText, Box, LayoutGrid
} from 'lucide-react';
import { initSpeechRecognition, createWakeWordMic } from './Chat/audioSpeech';

import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';
import CyberSpace3DCanvas, { detectLowEndGpu } from './common/CyberSpace3DCanvas';
import Plancia2D from './common/Plancia2D';
import { resolveRoleLucide, roleInitials } from './common/roleIcons';
import { loadSessions, formatSessionTime, saveActiveSessionId } from './Chat/chatStorage';
import { useAgentActivity, activityText } from './common/agentActivity';

// ==============================================================================
// Helper di risoluzione visiva per i ruoli caricati dinamicamente
// ==============================================================================
const ROLE_PALETTE = ['#00d2ff', '#ff007a', '#7c5bf0', '#10b981', '#f59e0b', '#ec4899', '#38bdf8', '#a855f7', '#06b6d4', '#14b8a6'];

const QUALITY_KEY = 'sigma_home_3d_quality';
const QUALITY_CYCLE = ['auto', 'high', 'lite', 'off'];
const QUALITY_LABEL = { auto: 'Auto', high: 'Alta', lite: 'Leggera', off: 'Spenta' };

// Vista della plancia: 3D (WebGL) o 2D (solo DOM e CSS). Senza una scelta
// salvata, sulle GPU che la 3D non regge (VideoCore del Pi, renderer software)
// si parte in 2D invece di far girare la plancia a scatti.
const VIEW_KEY = 'sigma_home_view';
const readViewPref = () => {
  try {
    const saved = localStorage.getItem(VIEW_KEY);
    if (saved === '2d' || saved === '3d') return saved;
  } catch {
    // localStorage non disponibile: si decide dalla GPU
  }
  return detectLowEndGpu() ? '2d' : '3d';
};

// Footer della Home: laboratori (aprono una scheda) e strumenti flottanti (si resta
// sulla plancia). Le immagini rendono riconoscibile ogni voce a colpo d'occhio.
const FOOTER_TILES = [
  { key: 'chat', label: 'Chat AI', hint: 'Chat flottante', image: '/images/chat_swarm_banner.jpg', Icon: MessageSquare, color: '#bc8cff', tool: 'chat' },
  { key: 'developer', label: 'Developer', hint: 'Studio di sviluppo', image: '/images/kernel_graphic.jpg', Icon: Terminal, color: '#eab308', tab: { id: 'developer_studio', name: 'Developer Sigma' } },
  { key: 'creative', label: 'Creative', hint: 'Immagini e 3D', image: '/images/creative_lab_banner.jpg', Icon: Palette, color: '#ff5064', tab: { id: 'creative_studio', name: 'Creative Studio' } },
  { key: 'video', label: 'Video', hint: 'Film e manga', image: '/images/regista_cinematografico.jpg', Icon: Clapperboard, color: '#ff007a', tab: { id: 'video_studio', name: 'Video Studio' } },
  { key: 'kicad', label: 'KiCad', hint: 'Schemi e PCB', image: '/images/hardware_cluster_lab.jpg', Icon: CircuitBoard, color: '#10b981', tab: { id: 'kicad_lab', name: 'KiCad Lab' } },
  { key: 'models', label: 'Modelli', hint: 'Model Hub', image: '/images/training_lab_hero.jpg', Icon: CloudDownload, color: '#38bdf8', tab: { id: 'model_hub', name: 'Modelli' } },
  { key: 'graph', label: 'Grafo', hint: 'Dipendenze del codice', image: '/images/knowledge_graph_banner.jpg', Icon: Layers, color: '#06b6d4', tab: { id: 'developer_studio', name: 'Developer Sigma' }, event: 'sigma_dev_open_graph' },
  { key: 'hardware', label: 'Hardware', hint: 'GPU e VRAM', image: '/images/hardware_nodes_cooling.jpg', Icon: Cpu, color: '#3fb950', tool: 'hardware' },
  { key: 'roadmap', label: 'Pianificazione', hint: 'Task e calendario', image: '/images/roadmap_plan_banner.jpg', Icon: Calendar, color: '#00f2fe', tool: 'roadmap', module: 'sigma_roadmap' },
  { key: 'music', label: 'Musica', hint: 'Focus lounge', image: '/images/account_voice_banner.jpg', Icon: Music, color: '#f472b6', tool: 'music', module: 'audio_studio' },
  { key: 'providers', label: 'Providers', hint: 'Modelli e API', image: '/images/mcp_protocol_hub.jpg', Icon: Settings, color: '#ffb86c', tool: 'providers' },
  { key: 'cleanup', label: 'Pulisci', hint: 'RAM e cronologia', image: '/images/swarm_graphic.jpg', Icon: Trash2, color: '#94a3b8', tool: 'cleanup' }
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

// Disinstallato (fuori da list_manifesti, o "installed: false" nel catalogo
// dell'hub) o sospeso in agents_meta: in entrambi i casi il ruolo sparisce
// da plancia, chip e menu.
const isRoleAvailable = (r) => Boolean(r) && r.active !== false && r.installed !== false;

const sessionRoleFile = (s) => {
  const p = s && s.manifestoPath;
  return p && p !== 'auto' ? String(p).split(/[\\/]/).pop().toLowerCase() : '';
};

const loadRecentChats = () => loadSessions()
  // Il messaggio di benvenuto conta come uno: una chat vera ne ha almeno due
  .filter(s => (s.messageCount || (Array.isArray(s.messages) ? s.messages.length : 0)) > 1)
  .sort((a, b) => new Date(b.updatedAt || b.lastMessageAt || 0) - new Date(a.updatedAt || a.lastMessageAt || 0))
  .slice(0, 3);

export default function WelcomeDashboard({ modules = [], openTab }) {
  const { theme, manifesti: contextManifesti, aiChatOpen, setAiChatOpen, addToast } = useApp();
  const { modulesState } = useModuleState();
  // Anche "cream" e' un tema chiaro: prima la plancia restava scura sotto un'interfaccia chiara
  const isLight = theme === 'light' || theme === 'cream';

  // Ruoli dinamici caricati dal backend
  const [loadedRoles, setLoadedRoles] = useState([]);
  const [selectedRole, setSelectedRole] = useState('auto');
  const [quickPrompt, setQuickPrompt] = useState('');
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  const [qualityPref, setQualityPref] = useState(readQualityPref);
  const [viewPref, setViewPref] = useState(readViewPref);
  const [resolvedQuality, setResolvedQuality] = useState(null);
  const [systemStats, setSystemStats] = useState(null);
  const [recentChats, setRecentChats] = useState(loadRecentChats);

  // Documenti e file allegati di qualsiasi tipo
  const [attachedFiles, setAttachedFiles] = useState([]);
  const fileInputRef = useRef(null);

  // Textarea ad auto-espansione dinamica
  const textareaRef = useRef(null);
  const adjustHeight = (el) => {
    if (!el) return;
    el.style.height = 'auto';
    const newHeight = Math.min(Math.max(el.scrollHeight, 26), 220);
    el.style.height = `${newHeight}px`;
  };

  useEffect(() => {
    if (!quickPrompt && textareaRef.current) {
      textareaRef.current.style.height = '26px';
    } else if (textareaRef.current) {
      adjustHeight(textareaRef.current);
    }
  }, [quickPrompt]);

  // Registrazione vocale standard (STT)
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);
  const initialInputRef = useRef('');

  // Wake-word mic ("Hey Sigma", "Ciao Sigma"): 'off' | 'waiting' | 'listening'
  const [smartMicState, setSmartMicState] = useState('off');
  const smartMicRef = useRef(null);

  // Lo stato reale dell'agente, pubblicato dalla chat (anche dal pannello flottante)
  const agentActivity = useAgentActivity();
  const agentBusy = ['thinking', 'tool', 'browsing', 'writing'].includes(agentActivity.state);

  // Caricamento Ruoli
  useEffect(() => {
    let cancel = false;
    const loadDynamicRoles = async () => {
      if (Array.isArray(contextManifesti) && contextManifesti.length > 0) {
        if (!cancel) setLoadedRoles(contextManifesti.filter(isRoleAvailable));
        return;
      }

      try {
        const res = await fetch('/api/list_manifesti');
        if (res.ok) {
          const data = await res.json();
          const items = data.manifesti || data.ruoli || data.files || [];
          if (!cancel && Array.isArray(items) && items.length > 0) {
            setLoadedRoles(items.filter(isRoleAvailable));
            return;
          }
        }
      } catch (err) {}

      try {
        const resHub = await fetch('/api/ruoli/hub');
        if (resHub.ok) {
          const dataHub = await resHub.json();
          // Il catalogo elenca anche i ruoli mai installati: solo quelli presenti
          const installed = Array.isArray(dataHub.catalog) ? dataHub.catalog.filter(r => r.installed && isRoleAvailable(r)) : [];
          if (!cancel && installed.length > 0) {
            setLoadedRoles(installed);
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
        prompt: resolveRolePrompt({ ...r, id }),
        // Busto 3D installato con il ruolo: senza, la plancia usa l'ufficiale procedurale
        model3d: r.model3d || null,
        // Figura intera con scheletro: in qualita' alta cammina nella plancia
        character3d: r.character3d || null
      };
      return enriched;
    });
  }, [loadedRoles]);

  useEffect(() => {
    if (selectedRole === 'auto') return;
    if (enrichedRoles.length > 0 && !enrichedRoles.find(r => r.id === selectedRole)) {
      setSelectedRole('auto');
    }
  }, [enrichedRoles, selectedRole]);

  // Lista di tutti i ruoli dinamici caricati dal sistema, ordinati alfabeticamente per la select
  const sortedRoles = useMemo(() => {
    return [...enrichedRoles].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'it', { sensitivity: 'base' }));
  }, [enrichedRoles]);

  // Le chat di un ruolo disinstallato non si riaprono piu' con quel ruolo:
  // in "Riprendi" restano solo quelle generiche o di ruoli ancora presenti.
  const visibleRecentChats = useMemo(() => {
    if (!loadedRoles || loadedRoles.length === 0) return recentChats;
    const files = new Set(loadedRoles.map(r => String(r.filename || '').toLowerCase()).filter(Boolean));
    return recentChats.filter(s => {
      const f = sessionRoleFile(s);
      return !f || files.has(f);
    });
  }, [recentChats, loadedRoles]);

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

  const toggleView = () => {
    const next = viewPref === '3d' ? '2d' : '3d';
    setViewPref(next);
    try { localStorage.setItem(VIEW_KEY, next); } catch (e) {}
  };

  // Gestione selezione file di qualsiasi tipo
  const handleFileSelect = (e) => {
    const farr = Array.from(e.target.files || []);
    if (!farr.length) return;
    const readers = farr.map(f => new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve({ filename: f.name, content: ev.target.result, size: f.size, type: f.type });
      reader.onerror = () => resolve(null);
      const isBinaryOrPdf = (f.name || '').toLowerCase().endsWith('.pdf') || f.type.startsWith('image/') || f.type === 'application/pdf';
      if (isBinaryOrPdf) {
        reader.readAsDataURL(f);
      } else {
        reader.readAsText(f);
      }
    }));
    Promise.all(readers).then(results => {
      const valid = results.filter(Boolean);
      setAttachedFiles(prev => [...prev, ...valid].slice(0, 10));
      if (addToast) addToast(`📎 ${valid.length} file allegat${valid.length > 1 ? 'i' : 'o'}.`, 'info');
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemoveFile = (idx) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  // Scrivere a un agente apre la chat flottante e invia subito: si resta sulla
  // plancia e si vede l'agente lavorare. La chat sceglie da se' se continuare la
  // conversazione di quell'agente o aprirne una nuova.
  const handleStartChatWithRole = (roleId, customText = '', filesToSend = [], send = true) => {
    try {
      if (roleId) localStorage.setItem('sigma_active_role', roleId);
      if (customText && customText.trim()) {
        localStorage.setItem('sigma_pending_chat_prompt', customText.trim());
      }
      if (Array.isArray(filesToSend) && filesToSend.length > 0) {
        localStorage.setItem('sigma_pending_chat_files', JSON.stringify(filesToSend));
      }
      if (send) localStorage.setItem('sigma_pending_chat_send', '1');
    } catch (e) {}
    // Se la chat e' gia' aperta riceve l'evento, altrimenti legge i valori al montaggio
    if (aiChatOpen) window.dispatchEvent(new CustomEvent('sigma-chat-select-role', { detail: roleId }));
    else setAiChatOpen(true);
  };

  const stopSmartMic = useCallback(() => {
    if (smartMicRef.current) {
      smartMicRef.current.stop();
      smartMicRef.current = null;
    }
    setSmartMicState('off');
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsRecording(false);
      return;
    }

    stopSmartMic();
    initialInputRef.current = quickPrompt || '';

    const recognition = initSpeechRecognition({
      lang: 'it-IT',
      onResult: (accumulatedText) => {
        if (accumulatedText) {
          const prefix = initialInputRef.current ? initialInputRef.current.trim() : '';
          const newText = prefix ? `${prefix} ${accumulatedText}` : accumulatedText;
          setQuickPrompt(newText);
          if (textareaRef.current) adjustHeight(textareaRef.current);
        }
      },
      onError: (err) => {
        console.warn('SpeechRecognition error:', err);
        setIsRecording(false);
        if (addToast) addToast('⚠️ Errore durante la registrazione vocale.', 'warning');
      },
      onEnd: () => {
        setIsRecording(false);
      }
    });

    if (!recognition) {
      if (addToast) addToast('⚠️ Registrazione vocale non supportata dal browser.', 'warning');
      return;
    }

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setIsRecording(true);
      if (addToast) addToast('🎙️ Registrazione vocale attiva... Parla adesso!', 'info');
    } catch (err) {
      console.error('Start recognition error:', err);
      setIsRecording(false);
    }
  }, [isRecording, quickPrompt, addToast, stopSmartMic]);

  const toggleSmartMic = useCallback(() => {
    if (smartMicRef.current) {
      stopSmartMic();
      if (addToast) addToast('🎙️ Ascolto vocale disattivato.', 'info');
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      setIsRecording(false);
    }

    const mic = createWakeWordMic({
      onState: setSmartMicState,
      onTranscript: (text) => {
        setQuickPrompt(text);
        if (textareaRef.current) adjustHeight(textareaRef.current);
      },
      onSubmit: (phrase) => {
        setQuickPrompt('');
        handleStartChatWithRole(selectedRole, phrase, attachedFiles);
        setAttachedFiles([]);
        if (textareaRef.current) textareaRef.current.style.height = '26px';
      },
      onError: (code) => {
        console.warn('Wake-word mic error:', code);
        stopSmartMic();
        if (addToast) addToast(`⚠️ Ascolto vocale interrotto (${code}).`, 'warning');
      },
    });

    if (!mic) {
      if (addToast) addToast('⚠️ Riconoscimento vocale non supportato dal browser.', 'warning');
      return;
    }

    smartMicRef.current = mic;
    if (!mic.start()) {
      smartMicRef.current = null;
      return;
    }
    if (addToast) addToast('✨ In ascolto: pronuncia "Hey Sigma" o "Ciao Sigma" e fai la tua domanda!', 'info');
  }, [isRecording, selectedRole, attachedFiles, addToast, stopSmartMic]);

  // Clean-up all'unmount dei microfoni
  useEffect(() => () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) {}
    }
    if (smartMicRef.current) {
      try { smartMicRef.current.stop(); } catch (e) {}
    }
  }, []);

  const handleOpenRecentChat = (sessionId) => {
    saveActiveSessionId(sessionId);
    if (aiChatOpen) window.dispatchEvent(new CustomEvent('sigma-chat-switch-session', { detail: sessionId }));
    else setAiChatOpen(true);
  };

  const handleFooterTile = (tile) => {
    if (tile.tool) {
      window.dispatchEvent(new CustomEvent('sigma-quick-tool', { detail: { id: tile.tool } }));
      return;
    }
    if (tile.event) window.dispatchEvent(new CustomEvent(tile.event));
    openTab?.({ name: tile.tab.name }, tile.tab.id);
  };

  const footerTiles = FOOTER_TILES.filter(t => !t.module || modulesState?.[t.module] === true);

  const handleQuickPromptSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!quickPrompt.trim() && attachedFiles.length === 0) return;
    handleStartChatWithRole(selectedRole, quickPrompt, attachedFiles);
    setQuickPrompt('');
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = '26px';
  };

  const handleAgentDialogueSubmit = (e) => {
    e.preventDefault();
    const roleId = focusedAgent?.id || selectedRole;
    const promptToSend = quickPrompt.trim() || focusedAgent?.prompt || '';
    handleStartChatWithRole(roleId, promptToSend, attachedFiles);
    setQuickPrompt('');
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = '26px';
  };

  const isAutoRole = selectedRole === 'auto';
  const selectedRoleObj = useMemo(() => {
    if (isAutoRole) {
      return {
        id: 'auto',
        name: 'Auto',
        title: 'Assegnazione Intelligente',
        color: '#00f0ff',
        category: 'Instradamento Dinamico',
        prompt: 'Descrivi la tua richiesta: Sigma individuerà ed assegnerà automaticamente il ruolo più competente…'
      };
    }
    return enrichedRoles.find(r => r.id === selectedRole);
  }, [isAutoRole, enrichedRoles, selectedRole]);

  const SelectedRoleIcon = isAutoRole ? Sparkles : resolveRoleLucide(selectedRoleObj || {});

  const currentPlaceholder = isAutoRole
    ? 'Scrivi cosa vuoi fare: il ruolo più idoneo verrà assegnato automaticamente…'
    : (selectedRoleObj?.prompt || `Invia un messaggio a ${selectedRoleObj?.name || 'questo agente'}…`);

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
      className={`holodeck-viewport ${focusedAgent ? 'is-focused' : ''} ${viewPref === '3d' && qualityPref === 'off' ? 'is-static' : ''} ${viewPref === '2d' ? 'is-2d' : ''}`}
      data-agent-component="CyberHolodeck"
      style={focusedAgent ? { '--agent-glow': focusedAgent.color } : undefined}
    >

      {/* ── 0. Plancia 3D, plancia 2D, o sfondo statico quando la grafica e' spenta ── */}
      {viewPref === '2d' ? (
        <Plancia2D
          roles={enrichedRoles}
          selectedAgentId={focusedAgent ? focusedAgent.id : ''}
          activity={agentActivity}
          onSelectAgent={(agent) => {
            if (agent) focusRole(agent);
            else setFocusedAgent(null);
          }}
        />
      ) : qualityPref === 'off' ? (
        <div className="holodeck-static-bg" aria-hidden="true" />
      ) : (
        <CyberSpace3DCanvas
          isLight={isLight}
          roles={enrichedRoles}
          selectedAgentId={focusedAgent ? focusedAgent.id : ''}
          quality={qualityPref}
          throttled={agentBusy}
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

          {agentActivity.state !== 'idle' && (
            <button
              type="button"
              className={`holodeck-activity-chip state-${agentActivity.state}`}
              style={agentActivity.color ? { '--activity-color': agentActivity.color } : undefined}
              onClick={() => setAiChatOpen(true)}
              title={[agentActivity.roleName, activityText(agentActivity), agentActivity.detail].filter(Boolean).join(' · ')}
            >
              <RoleAvatar role={{ name: agentActivity.roleName, image: agentActivity.image }} className="activity-avatar" />
              <span className="activity-name">{agentActivity.roleName}</span>
              <span className="activity-label">
                {activityText(agentActivity)}
              </span>
            </button>
          )}

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
              onClick={toggleView}
              className="holodeck-action-pill"
              title={viewPref === '3d'
                ? 'Plancia 3D. Clicca per la vista 2D, piu\' leggera.'
                : 'Plancia 2D, senza rendering 3D. Clicca per la vista 3D.'}
            >
              {viewPref === '3d' ? <Box size={13} aria-hidden="true" /> : <LayoutGrid size={13} aria-hidden="true" />}
              <span className="pill-text">Vista: {viewPref === '3d' ? '3D' : '2D'}</span>
            </button>

            {viewPref === '3d' && (
              <button
                type="button"
                onClick={cycleQuality}
                className="holodeck-action-pill"
                title={qualityTitle}
              >
                <Orbit size={13} aria-hidden="true" />
                <span className="pill-text">3D: {QUALITY_LABEL[qualityPref]}</span>
              </button>
            )}

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
        {visibleRecentChats.length > 0 && !focusedAgent && !aiChatOpen && (
          <aside className="holodeck-recent" aria-label="Chat recenti">
            <div className="holodeck-recent-title">
              <History size={13} aria-hidden="true" />
              <span>Riprendi</span>
            </div>
            {visibleRecentChats.map(s => (
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
                <span>Invia</span>
                <Send size={15} aria-hidden="true" />
              </button>
            </form>
          </div>
        ) : (
          /* Barra inferiore: dock dei laboratori + barra dei comandi */
          <footer className="holodeck-bottom-deck">

            <div className="holodeck-omnibar-cluster">
              <form
                className="holodeck-omnibar-form"
                onSubmit={handleQuickPromptSubmit}
                style={selectedRoleObj ? { '--omni-color': selectedRoleObj.color } : undefined}
              >
                <div className="holodeck-role-capsule" title="Seleziona agente o Auto-Routing">
                  <select
                    value={selectedRole}
                    onChange={e => {
                      const val = e.target.value;
                      if (val === 'auto') {
                        setSelectedRole('auto');
                        setFocusedAgent(null);
                      } else {
                        const match = enrichedRoles.find(r => r.id === val);
                        if (match) focusRole(match, false);
                        else setSelectedRole(val);
                      }
                    }}
                    className="holodeck-role-select-overlay"
                    aria-label="Seleziona Agente o Ruolo"
                  >
                    <option value="auto">✨ Auto</option>
                    {sortedRoles.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                  <div className="holodeck-role-icon-box">
                    <SelectedRoleIcon size={15} className={`holodeck-role-icon ${isAutoRole ? 'is-auto' : ''}`} aria-hidden="true" />
                  </div>
                  <div className="holodeck-role-select-wrapper">
                    <span className="holodeck-role-badge-tag">{isAutoRole ? 'AUTO ROUTING' : 'AGENTE'}</span>
                    <span className="holodeck-role-display-text">{isAutoRole ? 'Auto' : (selectedRoleObj?.name || selectedRole)}</span>
                  </div>
                  <ChevronDown size={14} className="holodeck-role-chevron" aria-hidden="true" />
                </div>

                <div className="holodeck-input-container">
                  {attachedFiles.length > 0 && (
                    <div className="holodeck-attached-strip">
                      {attachedFiles.map((file, idx) => (
                        <span key={`${file.filename}-${idx}`} className="holodeck-file-chip" title={`${file.filename} (${file.size ? Math.round(file.size / 1024) + ' KB' : ''})`}>
                          <FileText size={12} className="holodeck-file-icon" />
                          <span className="holodeck-file-name">{file.filename}</span>
                          <button type="button" onClick={() => handleRemoveFile(idx)} className="holodeck-file-remove-btn" title="Rimuovi allegato">
                            <X size={11} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                  <textarea
                    ref={textareaRef}
                    rows={1}
                    className="holodeck-prompt-textarea"
                    placeholder={currentPlaceholder}
                    value={quickPrompt}
                    onChange={e => {
                      setQuickPrompt(e.target.value);
                      adjustHeight(e.target);
                    }}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        if (quickPrompt.trim() || attachedFiles.length > 0) {
                          handleQuickPromptSubmit(e);
                        }
                      }
                    }}
                    aria-label="Messaggio per l'agente"
                  />
                </div>

                <div className="holodeck-omnibar-actions">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    multiple
                    accept="*/*"
                    style={{ display: 'none' }}
                  />
                  <button
                    type="button"
                    className="holodeck-tool-btn"
                    onClick={() => fileInputRef.current?.click()}
                    title="Allega documenti di qualsiasi tipo (PDF, immagini, codice, testo, archivi...)"
                    aria-label="Allega documenti"
                  >
                    <Paperclip size={16} />
                    {attachedFiles.length > 0 && (
                      <span className="holodeck-attach-badge">{attachedFiles.length}</span>
                    )}
                  </button>

                  <button
                    type="button"
                    className={`holodeck-tool-btn ${isRecording ? 'recording' : ''}`}
                    onClick={toggleRecording}
                    title={isRecording ? 'Interrompi dettatura vocale' : 'Dettatura vocale: parla per scrivere'}
                    aria-label="Dettatura vocale"
                  >
                    {isRecording ? <Mic size={16} /> : <MicOff size={16} />}
                  </button>

                  <button
                    type="button"
                    className={`holodeck-tool-btn ${smartMicState !== 'off' ? 'smart-active ' + smartMicState : ''}`}
                    onClick={toggleSmartMic}
                    title={
                      smartMicState === 'listening'
                        ? '🎤 Ti sto ascoltando... Parla adesso'
                        : smartMicState === 'waiting'
                        ? '✨ In ascolto: pronuncia "Hey Sigma" o "Ciao Sigma" per parlare'
                        : 'Ascolto continuo: pronuncia "Hey Sigma" o "Ciao Sigma" per inviare la richiesta'
                    }
                    aria-label="Ascolto continuo Hey Sigma"
                  >
                    <AudioLines size={16} />
                  </button>

                  <button
                    type="submit"
                    className="holodeck-submit-btn"
                    disabled={!quickPrompt.trim() && attachedFiles.length === 0}
                  >
                    <span>Invia</span>
                    <Send size={15} aria-hidden="true" />
                  </button>
                </div>
              </form>
            </div>

            <nav className="holodeck-footer" aria-label="Laboratori e strumenti">
              {footerTiles.map(tile => (
                <button
                  key={tile.key}
                  type="button"
                  className={`holodeck-tile ${tile.tool === 'chat' && aiChatOpen ? 'is-active' : ''}`}
                  style={{ '--tile-color': tile.color, '--tile-image': `url('${tile.image}')` }}
                  onClick={() => handleFooterTile(tile)}
                  title={`${tile.label} · ${tile.hint}${tile.tool ? ' (resta sulla Home)' : ''}`}
                >
                  <span className="tile-image" aria-hidden="true" />
                  <span className="tile-body">
                    <tile.Icon size={14} aria-hidden="true" />
                    <span className="tile-label">{tile.label}</span>
                  </span>
                </button>
              ))}
            </nav>
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
