import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Home, Sun, Moon, Thermometer, Lock, Power, Lightbulb, RefreshCw, Send,
  Zap, Sliders, Palette, Plus, Minus, Key, AlertCircle, Search, Filter,
  Tv, Music, Camera, Fan, Waves, DoorOpen, ChevronDown, ChevronUp,
  Droplets, ShieldCheck, Plug, Wifi, WifiOff, Pencil, Check, X, FlaskConical,
  Radio, Eye, Sparkles, Activity, Layers, ArrowRight, ShieldAlert, CheckCircle2
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import TechSpaceCanvas from '../common/TechSpaceCanvas';

const CUSTOM_NAMES_KEY = 'domotica_custom_names';

// ── Colour presets for quick light colour selection ──────────────────────
const COLOR_PRESETS = [
  { name: 'Ciano', hex: '#00d2ff', rgb: [0, 210, 255] },
  { name: 'Caldo', hex: '#ffb86c', rgb: [255, 184, 108] },
  { name: 'Viola', hex: '#a78bfa', rgb: [167, 139, 250] },
  { name: 'Verde', hex: '#3fb950', rgb: [63, 185, 80] },
  { name: 'Rosso', hex: '#ff5064', rgb: [255, 80, 100] },
  { name: 'Arancione', hex: '#ff8c42', rgb: [255, 140, 66] },
  { name: 'Rosa', hex: '#ff79c6', rgb: [255, 121, 198] },
  { name: 'Blu', hex: '#6272a4', rgb: [98, 114, 164] },
];

// ── Domain → UI metadata map ─────────────────────────────────────────────
const DOMAIN_META = {
  light:        { icon: Lightbulb,   label: 'Luce',         color: '#fbbf24' },
  switch:       { icon: Plug,        label: 'Presa',        color: '#60a5fa' },
  climate:      { icon: Thermometer, label: 'Clima',        color: '#f87171' },
  lock:         { icon: Lock,        label: 'Serratura',    color: '#a78bfa' },
  cover:        { icon: DoorOpen,    label: 'Tapparella',   color: '#94a3b8' },
  media_player: { icon: Music,       label: 'Media',        color: '#34d399' },
  camera:       { icon: Camera,      label: 'Telecamera',   color: '#fb923c' },
  vacuum:       { icon: Waves,       label: 'Aspirapolvere',color: '#38bdf8' },
  fan:          { icon: Fan,         label: 'Ventilatore',  color: '#818cf8' },
  humidifier:   { icon: Droplets,    label: 'Umidificatore',color: '#2dd4bf' },
};

// ── Shared style tokens ───────────────────────────────────────────────────
const getThemeTokens = (isLight) => ({
  bg:        isLight ? '#f7f4ed' : '#080a10',
  cardBg:    isLight ? '#fffdf9' : '#0e1017',
  cardHover: isLight ? '#f2ede2' : '#141824',
  border:    isLight ? 'rgba(190, 160, 110, 0.35)' : 'rgba(255,255,255,0.06)',
  borderHov: isLight ? 'rgba(234, 88, 12, 0.4)' : 'rgba(255,255,255,0.12)',
  accent:    isLight ? '#ea580c' : '#00d2ff',
  accent2:   isLight ? '#d97706' : '#7c5bf0',
  text:      isLight ? '#111111' : '#e2e8f0',
  muted:     isLight ? '#2e2820' : '#8892b0',
  on:        isLight ? '#166534' : '#3fb950',
  off:       isLight ? '#78716c' : '#64748b'
});

const T = getThemeTokens(false);

// ── Standby / Inactive Smart Features definitions (Card Grigie) ───────────
const INACTIVE_FEATURES = [
  {
    id: 'facial_lock',
    title: 'Accessi Biometrici & Facial ID AI',
    subtitle: 'Sblocco serrature con riconoscimento facciale locale YOLOv8 e registro accessi audit criptato.',
    prerequisite: 'Telecamera RTSP Studio + Modello FaceID On-Device',
    statusBadge: 'IN ATTESA DI ACTIVATION',
    icon: Lock,
    color: '#a78bfa',
    actionText: 'Abilita Modello FaceID',
    details: 'Questa funzione integra la scansione biometrica in tempo reale su RTSP per consentire lo sblocco automatizzato della serratura di laboratorio ed il tracciamento dei log di ingresso in SQLite.'
  },
  {
    id: 'solar_energy',
    title: 'Smart Energy Autopilot & Solar Balancing',
    subtitle: 'Bilanciamento dinamico dei carichi VRAM GPU ed Ollama in base alla produzione dei pannelli fotovoltaici.',
    prerequisite: 'Inverter SolarEdge / Huawei Modbus TCP',
    statusBadge: 'HARDWARE IN ATTESA',
    icon: Zap,
    color: '#3fb950',
    actionText: 'Associa Inverter Solare',
    details: 'Modula la potenza di elaborazione del cluster GPU e del demone Ollama sincronizzandola con l\'eccedenza di energia solare prodotta dagli inverter connessi via Modbus.'
  },
  {
    id: 'adaptive_climate',
    title: 'Microclima Adattativo AI Predictive',
    subtitle: 'Regolazione automatica della temperatura di laboratorio in base a previsioni meteo ed abitudini giornaliere.',
    prerequisite: 'Sensori di Presenza Termica Zigbee + Meteo API',
    statusBadge: 'MODULO ML STANDBY',
    icon: Thermometer,
    color: '#ffb86c',
    actionText: 'Abilita Autopilota Clima',
    details: 'Predice la curva termica ottimale per il laboratorio combinando i sensori di presenza PIR Zigbee con i modelli di previsione meteo per abbattere i consumi del 35%.'
  },
  {
    id: 'multiroom_audio',
    title: 'Filodiffusione Multiroom & Annunci Vocali AI',
    subtitle: 'Diffusione sonora coordinata via AirPlay/Chromecast per annunci dell\'assistente AI e musica d\'ambiente.',
    prerequisite: 'Speaker Google Home / Sonos Stream',
    statusBadge: 'SPEAKER STANDBY',
    icon: Radio,
    color: '#00d2ff',
    actionText: 'Associa Speaker Multiroom',
    details: 'Permette agli agenti dello Swarm di Sigma Studio di pronunciare notifiche vocali ad alta priorità e sintesi TTS attraverso l\'impianto audio coordinato del laboratorio.'
  },
  {
    id: 'yolo_security',
    title: 'Sentinella Video Night Vision YOLOv8',
    subtitle: 'Analisi video in locale a 30 FPS sui flussi telecamere per rilevamento intrusioni, pacchetti e fumo.',
    prerequisite: 'Telecamera RTSP H.265 visione notturna',
    statusBadge: 'FLUSSO RTSP RICHIESTO',
    icon: Eye,
    color: '#ff5064',
    actionText: 'Configura Flusso RTSP',
    details: 'Esegue un modello di computer vision in background per la sicurezza perimetrale. Invia alert visivi ed acustici imminenti in chat in caso di anomalie riscontrate nei flussi video.'
  },
  {
    id: 'water_air_safety',
    title: 'Prevenzione Allagamenti & Qualità Aria VOC',
    subtitle: 'Chiusura automatica elettrovalvola idrica in caso di perdite ed attivazione purificatori su soglie CO2 elevate.',
    prerequisite: 'Valvola Smart Zigbee + Sensore CO2 NDIR',
    statusBadge: 'SENSORI ZIGBEE STANDBY',
    icon: Droplets,
    color: '#38bdf8',
    actionText: 'Collega Sensori Sicurezza',
    details: 'Chiusura istantanea dell\'afflusso d\'acqua in meno di 500ms al rilevamento di umidità a pavimento e regolazione della ventilazione meccanica sui picchi di particolato.'
  }
];

export default function DomoticaTab() {
  const [devices, setDevices] = useState([]);
  const [isConfigured, setIsConfigured] = useState(false);
  const [loading, setLoading] = useState(true);

  // Custom device names saved in localStorage
  const [customNames, setCustomNames] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(CUSTOM_NAMES_KEY) || '{}');
    } catch {
      return {};
    }
  });
  const [editingId, setEditingId] = useState(null);
  const [editInputValue, setEditInputValue] = useState('');

  // Search & category filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('all');

  // Config Modal states
  const [haUrl, setHaUrl] = useState('http://homeassistant.local:8123');
  const [haToken, setHaToken] = useState('');
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testStatus, setTestStatus] = useState(null);

  // Activation modal for standby feature cards
  const [activeFeatureModal, setActiveFeatureModal] = useState(null);
  const [activatingId, setActivatingId] = useState(null);
  const [activatedFeatures, setActivatedFeatures] = useState({});

  const [expandedControl, setExpandedControl] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [logs, setLogs] = useState([
    { time: new Date().toLocaleTimeString(), msg: 'Inizializzazione Bus Domotico MCP Home Assistant Protocol...', type: 'info' }
  ]);
  const [aiLoading, setAiLoading] = useState(false);

  const addLog = (msg, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [{ time, msg, type }, ...prev]);
  };

  // Fetch real entities from Home Assistant API
  const fetchHaEntities = async () => {
    setLoading(true);
    addLog('Scansione rete Home Assistant per la ricerca di nuovi dispositivi...', 'info');
    try {
      const res = await fetch('/api/mcp/ha/entities');
      if (res.ok) {
        const data = await res.json();
        if (data.is_configured && Array.isArray(data.entities) && data.entities.length > 0) {
          setIsConfigured(true);
          const mapped = data.entities.map(e => {
            const domain = e.entity_id.split('.')[0];
            const meta = DOMAIN_META[domain] || { icon: Power, label: domain, color: '#94a3b8' };
            const storedName = customNames[e.entity_id];
            const name = storedName || e.name || e.entity_id;

            return {
              id: e.entity_id,
              name,
              originalName: e.name || e.entity_id,
              domain,
              type: domain,
              meta,
              state: (e.state || 'off').toLowerCase(),
              brightness: e.capabilities?.brightness_pct || 80,
              color: '#00d2ff',
              val: e.unit ? `${e.state} ${e.unit}` : null,
              room: e.area || 'Home Assistant',
              setpoint: 21
            };
          });
          setDevices(mapped);
          addLog(`Completata scansione: trovati ${mapped.length} dispositivi reali dall'istanza Home Assistant.`, 'success');
        } else {
          setIsConfigured(false);
          setDevices([]);
          if (data.error) {
            addLog(`Home Assistant: ${data.error}`, 'info');
          }
        }
      } else {
        setIsConfigured(false);
        setDevices([]);
      }
    } catch (e) {
      console.warn("Errore caricamento entità Home Assistant:", e);
      setIsConfigured(false);
      setDevices([]);
      addLog(`Errore di connessione a Home Assistant: ${e.message}`, 'action');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHaEntities();
  }, []);

  // Il form partiva sempre dai valori di default, ignorando la configurazione
  // già salvata: dopo un salvataggio riuscito riapparivano `homeassistant.local`
  // e token vuoto, facendo credere che nulla fosse stato memorizzato — e un
  // Salva successivo avrebbe davvero sovrascritto l'indirizzo giusto.
  useEffect(() => {
    fetch('/api/mcp/servers')
      .then(r => r.json())
      .then(data => {
        const ha = (data.servers || []).find(s => s.integration_key === 'home_assistant');
        if (!ha?.config) return;
        if (ha.config.base_url) setHaUrl(ha.config.base_url);
        // Il token torna mascherato: rimandarlo così com'è significa
        // «lascialo com'era», quindi è sicuro mostrarlo nel campo.
        if (ha.config.token) setHaToken(ha.config.token);
      })
      .catch(() => {});
  }, [showConfigModal]);

  // Save custom device name to localStorage
  const saveCustomName = (id, newName) => {
    const trimmed = newName.trim();
    const updated = { ...customNames };
    if (trimmed) {
      updated[id] = trimmed;
    } else {
      delete updated[id];
    }
    setCustomNames(updated);
    try {
      localStorage.setItem(CUSTOM_NAMES_KEY, JSON.stringify(updated));
    } catch (e) {
      console.warn('Impossibile salvare nome personalizzato:', e);
    }
    setDevices(prev => prev.map(d => d.id === id ? { ...d, name: trimmed || d.originalName } : d));
    setEditingId(null);
    addLog(`Rinominato dispositivo ${id} in "${trimmed || 'nome predefinito'}"`, 'info');
  };

  // Test Connection in Modal
  const testHaConnection = async () => {
    setTestLoading(true);
    setTestStatus(null);
    addLog(`Test di connessione in corso verso ${haUrl}...`, 'info');
    try {
      const res = await fetch('/api/mcp/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: 'home_assistant',
          values: { base_url: haUrl, token: haToken },
          config: { base_url: haUrl, token: haToken }
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          const count = data.result?.entities?.length || data.result?.total_found || 0;
          setTestStatus({
            success: true,
            msg: `✅ Connessione riuscita! Home Assistant ha risposto correttamente (${count} entità rilevate).`
          });
          addLog(`Test connessione Home Assistant superato con successo.`, 'success');
        } else {
          setTestStatus({
            success: false,
            msg: `❌ Test fallito: ${data.error || 'Home Assistant irraggiungibile o token rifiutato.'}`
          });
          addLog(`Test connessione fallito: ${data.error}`, 'action');
        }
      } else {
        setTestStatus({
          success: false,
          msg: '❌ Errore di rete durante la prova di connessione.'
        });
      }
    } catch (err) {
      setTestStatus({
        success: false,
        msg: `❌ Impossibile stabilire la connessione: ${err.message}`
      });
    } finally {
      setTestLoading(false);
    }
  };

  // Save HA Integration credentials
  const saveHaIntegration = async (e) => {
    e.preventDefault();
    setSavingConfig(true);
    try {
      const res = await fetch('/api/mcp/integration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: 'home_assistant',
          values: { base_url: haUrl, token: haToken },
          config: { base_url: haUrl, token: haToken },
          enabled: true
        })
      });
      if (res.ok) {
        addLog('Credenziali Home Assistant salvate con successo! Sincronizzazione entità reali in corso...', 'success');
        setShowConfigModal(false);
        fetchHaEntities();
      } else {
        addLog('Errore durante il salvataggio della configurazione Home Assistant', 'action');
      }
    } catch (err) {
      addLog(`Errore salvataggio Home Assistant: ${err.message}`, 'action');
    } finally {
      setSavingConfig(false);
    }
  };

  // Real Control Dispatcher
  const sendRealControl = async (entityId, payload) => {
    try {
      const res = await fetch('/api/mcp/ha/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: entityId, ...payload })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          addLog(`Inviato comando reale a ${entityId}: ${JSON.stringify(payload)}`, 'success');
        } else {
          addLog(`Errore comando HA su ${entityId}: ${data.error}`, 'action');
        }
        return data;
      }
    } catch (e) {
      console.warn("Comando HA fallito:", e);
      addLog(`Comando HA non inviato a ${entityId}: ${e.message}`, 'action');
    }
    return { success: false, error: 'Comando non inviato' };
  };

  const toggleDevice = async (id) => {
    const device = devices.find(d => d.id === id);
    if (!device) return;
    const previousState = device.state;
    const nextState = previousState === 'on' ? 'off'
      : (previousState === 'off' ? 'on' : (previousState === 'locked' ? 'unlocked' : 'locked'));

    // Anticipare lo stato rende la scheda reattiva; se poi il comando non ha
    // avuto effetto si torna indietro, perché mostrare una lampada accesa che
    // è spenta è peggio di un istante di attesa.
    setDevices(prev => prev.map(d => d.id === id ? { ...d, state: nextState } : d));

    const outcome = await sendRealControl(id, { state: nextState });
    if (outcome?.success) {
      addLog(`Dispositivo ${device.name} (${id}) commutato a ${nextState.toUpperCase()}`, 'action');
    } else {
      setDevices(prev => prev.map(d => d.id === id ? { ...d, state: previousState } : d));
      addLog(`${device.name}: stato invariato. ${outcome?.error || 'Il dispositivo non ha risposto.'}`, 'action');
    }
  };

  // Regolazioni: si applicano subito sulla scheda per non far attendere lo
  // slider, ma vengono annullate se il dispositivo non ha risposto — altrimenti
  // la scheda mostra un colore che la lampada non ha mai avuto.
  const applyAndVerify = async (id, payload, changes, describe) => {
    const device = devices.find(d => d.id === id);
    if (!device) return;
    const previous = { ...device };

    setDevices(prev => prev.map(d => d.id === id ? { ...d, ...changes } : d));
    const outcome = await sendRealControl(id, payload);

    if (outcome?.success) {
      addLog(describe(device), 'action');
    } else {
      setDevices(prev => prev.map(d => d.id === id ? previous : d));
      addLog(`${device.name}: regolazione non applicata. ${outcome?.error || 'Nessuna risposta dal dispositivo.'}`, 'action');
    }
  };

  const updateBrightness = (id, newBrightness) => {
    const nextState = newBrightness > 0 ? 'on' : 'off';
    applyAndVerify(id,
      { state: nextState, brightness: newBrightness },
      { brightness: newBrightness, state: nextState },
      d => `Luminosità di ${d.name} impostata al ${newBrightness}%`);
  };

  const updateColor = (id, newColorHex, rgbArr = null) => {
    applyAndVerify(id,
      { state: 'on', color_rgb: rgbArr || [0, 210, 255] },
      { color: newColorHex, state: 'on' },
      d => `Colore di ${d.name} impostato a ${newColorHex}`);
  };

  const updateSetpoint = (id, delta) => {
    const device = devices.find(d => d.id === id && d.type === 'climate');
    if (!device) return;
    const nextVal = Math.max(16, Math.min(30, (device.setpoint || 21) + delta));
    applyAndVerify(id, { setpoint: nextVal }, { setpoint: nextVal },
      d => `Temperatura target ${d.name} impostata a ${nextVal}°C`);
  };

  // Scene Trigger Preset Handler
  const applyPresetScene = (sceneName) => {
    if (sceneName === 'focus') {
      setDevices(prev => prev.map(d => {
        if (d.domain === 'light') {
          sendRealControl(d.id, { state: 'on', brightness: 90, color_rgb: [0, 210, 255] });
          return { ...d, state: 'on', brightness: 90, color: '#00d2ff' };
        }
        if (d.domain === 'climate') {
          sendRealControl(d.id, { setpoint: 21 });
          return { ...d, setpoint: 21 };
        }
        return d;
      }));
      reportScene('Focus Ricerca', 'light');
    } else if (sceneName === 'standby') {
      setDevices(prev => prev.map(d => {
        if (d.domain === 'light') {
          sendRealControl(d.id, { state: 'off' });
          return { ...d, state: 'off' };
        }
        if (d.domain === 'lock') {
          sendRealControl(d.id, { state: 'locked' });
          return { ...d, state: 'locked' };
        }
        return d;
      }));
      reportScene('Standby Notte', 'light');
    } else if (sceneName === 'creative') {
      setDevices(prev => prev.map(d => {
        if (d.domain === 'light') {
          sendRealControl(d.id, { state: 'on', brightness: 80, color_rgb: [167, 139, 250] });
          return { ...d, state: 'on', brightness: 80, color: '#a78bfa' };
        }
        return d;
      }));
      reportScene('Ambiente Creativo', 'light');
    }
  };

  // Una scena tocca più dispositivi: il registro deve dire quanti hanno
  // risposto davvero, non che la scena "è stata attivata" a prescindere.
  const reportScene = async (name, domain) => {
    const targets = devices.filter(d => d.domain === domain);
    await new Promise(r => setTimeout(r, 400));
    try {
      const res = await fetch('/api/mcp/ha/entities');
      const data = await res.json();
      const live = new Map((data.entities || []).map(e => [e.entity_id, e.state]));
      const responding = targets.filter(d => !['unavailable', 'unknown'].includes(live.get(d.id)));
      if (responding.length === targets.length) {
        addLog(`Scena "${name}" applicata a ${targets.length} dispositivi.`, 'success');
      } else {
        addLog(`Scena "${name}": ${responding.length}/${targets.length} dispositivi hanno risposto`
          + ` — gli altri risultano non disponibili in Home Assistant.`, 'action');
      }
    } catch {
      addLog(`Scena "${name}" inviata; esito non verificabile.`, 'action');
    }
  };

  // Handle AI Command Execution
  //
  // Questo riquadro dichiarava «Tutte le luci reali disattivate» dopo una pausa
  // di 700 ms, senza aver contattato Home Assistant: cambiava solo lo stato
  // locale delle schede. I comandi ora partono davvero, uno per dispositivo, e
  // il registro riporta quanti hanno effettivamente cambiato stato.
  const handleAiCommand = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setAiLoading(true);
    const cmd = prompt;
    setPrompt('');
    addLog(`Comando AI Domotico inviato: "${cmd}"`, 'ai');

    const lower = cmd.toLowerCase();
    const turnOff = /\b(spegni|spegnere|off|chiudi)\b/.test(lower);
    const turnOn = /\b(accendi|accendere|on|apri)\b/.test(lower);

    try {
      if (!turnOff && !turnOn) {
        addLog(`Comando non riconosciuto: usa "accendi"/"spegni", eventualmente con il nome di una stanza.`, 'action');
        return;
      }
      const nextState = turnOff ? 'off' : 'on';

      // Una stanza citata nel testo restringe il bersaglio; altrimenti valgono
      // tutte le luci note.
      const rooms = [...new Set(devices.map(d => d.room).filter(Boolean))];
      const room = rooms.find(r => lower.includes(r.toLowerCase()));
      const targets = devices.filter(d => d.domain === 'light' && (!room || d.room === room));

      if (!targets.length) {
        addLog(room ? `Nessuna luce trovata in "${room}".` : 'Nessuna luce disponibile.', 'action');
        return;
      }

      const results = await Promise.all(
        targets.map(d => sendRealControl(d.id, { state: nextState }).then(r => ({ d, r })))
      );
      const ok = results.filter(x => x.r?.success);
      const failed = results.filter(x => !x.r?.success);

      if (ok.length) {
        setDevices(prev => prev.map(d =>
          ok.some(x => x.d.id === d.id) ? { ...d, state: nextState } : d));
        addLog(`Home Assistant: ${ok.length}/${targets.length} luci`
          + `${room ? ` in ${room}` : ''} portate a ${nextState.toUpperCase()}.`, 'success');
      }
      if (failed.length) {
        addLog(`Nessun effetto su ${failed.length} ${failed.length === 1 ? 'luce' : 'luci'}: `
          + (failed[0].r?.error || 'il dispositivo non ha risposto.'), 'action');
      }
    } finally {
      setAiLoading(false);
    }
  };

  // Simulate Feature Activation for Standby Cards
  const handleActivateFeature = (feature) => {
    setActivatingId(feature.id);
    setTimeout(() => {
      setActivatedFeatures(prev => ({ ...prev, [feature.id]: true }));
      setActivatingId(null);
      setActiveFeatureModal(null);
      addLog(`Modulo Domotico "${feature.title}" attivato con successo nel sistema.`, 'success');
    }, 1200);
  };

  // Filtered devices list
  const filteredDevices = useMemo(() => {
    return devices.filter(d => {
      const matchesSearch = !searchQuery.trim() ||
        d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        d.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.room && d.room.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesDomain = selectedDomain === 'all' ||
        (selectedDomain === 'light' && d.domain === 'light') ||
        (selectedDomain === 'switch' && d.domain === 'switch') ||
        (selectedDomain === 'climate' && d.domain === 'climate') ||
        (selectedDomain === 'sensor' && d.domain === 'sensor') ||
        (selectedDomain === 'media' && d.domain === 'media_player') ||
        (selectedDomain === 'security' && (d.domain === 'lock' || d.domain === 'camera'));

      return matchesSearch && matchesDomain;
    });
  }, [devices, searchQuery, selectedDomain]);

  const { theme } = useApp();
  const isThemeLight = theme === 'light';
  const T = useMemo(() => getThemeTokens(isThemeLight), [isThemeLight]);

  return (
    <div 
      className="domotica-tab-root"
      style={{
        position: 'relative',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: T.bg,
        color: T.text,
        fontFamily: 'Inter, system-ui, sans-serif',
        overflowY: 'auto'
      }}>
      <TechSpaceCanvas isLight={theme === 'light'} />

      {/* Hero Visual Banner with Generated Graphic Backdrop */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: isThemeLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isThemeLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: isThemeLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/domotica_smart_hub.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/domotica_smart_hub.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: isThemeLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: isThemeLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: isThemeLight ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Zap size={14} /> MCP Home Assistant Bus & Smart Domotica Engine
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: isThemeLight ? '#111111' : '#fff', letterSpacing: '-0.3px', textShadow: 'none' }}>
              Controllo Domotico IoT & <span style={{
                color: isThemeLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Gestione Dispositivi Reali</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: isThemeLight ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Scansiona, cerca e controlla in tempo reale luci, climatizzazione, sensori e serrature della tua abitazione o laboratorio.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{
              padding: '8px 16px', borderRadius: '20px',
              background: isConfigured ? 'rgba(63, 185, 80, 0.15)' : 'rgba(210, 153, 34, 0.15)',
              border: `1px solid ${isConfigured ? 'rgba(63, 185, 80, 0.4)' : 'rgba(210, 153, 34, 0.4)'}`,
              color: isConfigured ? '#3fb950' : '#d29922', fontSize: '0.78rem', fontWeight: 800,
              display: 'flex', alignItems: 'center', gap: '8px'
            }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isConfigured ? '#3fb950' : '#d29922', boxShadow: `0 0 10px ${isConfigured ? '#3fb950' : '#d29922'}` }} />
              {isConfigured ? `Home Assistant Connesso (${devices.length} Entità)` : 'HA Non Connesso'}
            </div>

            <button
              onClick={() => { setTestStatus(null); setShowConfigModal(true); }}
              style={{
                padding: '10px 16px', borderRadius: '12px',
                background: 'rgba(0, 210, 255, 0.12)', border: '1px solid rgba(0, 210, 255, 0.35)',
                color: '#00d2ff', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              <Key size={15} /> Configura Token HA
            </button>

            <button
              onClick={fetchHaEntities}
              disabled={loading}
              style={{
                padding: '10px 18px', borderRadius: '12px',
                background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)', border: 'none',
                color: '#fff', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px', boxShadow: '0 4px 16px rgba(0, 210, 255, 0.25)'
              }}
            >
              <RefreshCw size={15} className={loading ? 'spin' : ''} />
              {loading ? 'Scansione in corso...' : '🔍 Rileva Nuovi Dispositivi'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div style={{ padding: '32px', flex: 1, maxWidth: '1440px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

        {/* Preset Smart Scenes Quick Action Toolbar */}
        <div className="domotica-scene-card primi-passi-card" style={{
          marginBottom: '32px',
          padding: '24px',
          borderRadius: '20px',
          backgroundColor: T.cardBg,
          border: `1px solid ${T.border}`,
          boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '20px'
        }}>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#a78bfa', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={14} /> SCENE DOMOTICHE PREIMPOSTATE
            </div>
            <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              Attivazione Rapida Ambiente Studio
            </h3>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={() => applyPresetScene('focus')}
              style={{
                padding: '10px 18px', borderRadius: '12px',
                background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.4)',
                color: '#00d2ff', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s ease'
              }}
            >
              <Lightbulb size={16} /> 🔬 Focus Ricerca (90% Ciano)
            </button>

            <button
              onClick={() => applyPresetScene('creative')}
              style={{
                padding: '10px 18px', borderRadius: '12px',
                background: 'rgba(167, 139, 250, 0.15)', border: '1px solid rgba(167, 139, 250, 0.4)',
                color: '#a78bfa', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s ease'
              }}
            >
              <Palette size={16} /> 🎨 Ambiente Creativo (Viola Neon)
            </button>

            <button
              onClick={() => applyPresetScene('standby')}
              style={{
                padding: '10px 18px', borderRadius: '12px',
                background: 'rgba(255, 80, 100, 0.15)', border: '1px solid rgba(255, 80, 100, 0.4)',
                color: '#ff5064', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s ease'
              }}
            >
              <Moon size={16} /> 🌙 Standby Notte (Spegni Tutto)
            </button>
          </div>
        </div>

        {/* AI Command Input Bar */}
        <div className="domotica-card primi-passi-card" style={{
          padding: '20px', borderRadius: '18px',
          backgroundColor: T.cardBg,
          border: `1px solid ${T.border}`,
          boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
          marginBottom: '32px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.86rem', fontWeight: 800, color: '#00d2ff' }}>
            <Zap size={16} /> Assistente AI Domotico — MCP Home Assistant Command Bus
          </div>
          <form onSubmit={handleAiCommand} style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="es. Spegni le luci dell'ufficio ed imposta il colore su Ciano Cyber..."
              style={{
                flex: 1, padding: '12px 18px', borderRadius: '12px',
                background: 'rgba(8, 10, 16, 0.9)', border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#fff', fontSize: '0.88rem', outline: 'none'
              }}
            />
            <button
              type="submit"
              disabled={aiLoading}
              style={{
                padding: '12px 24px', borderRadius: '12px',
                background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)', border: 'none',
                color: '#fff', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px'
              }}
            >
              {aiLoading ? <RefreshCw className="spin" size={16} /> : <Send size={16} />} Invio Comando
            </button>
          </form>
        </div>

        {/* Device Search & Filter Toolbar */}
        <div className="domotica-card primi-passi-card" style={{
          display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '28px',
          padding: '20px', borderRadius: '18px', backgroundColor: T.cardBg,
          border: `1px solid ${T.border}`
        }}>
          <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '280px', position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: T.muted }} />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="🔍 Cerca dispositivo, stanza o ID entità (es. luce, ufficio, clima)..."
                style={{
                  width: '100%', padding: '12px 18px 12px 46px', borderRadius: '12px',
                  background: isThemeLight ? '#f2ede2' : '#0c0e16', border: `1px solid ${T.border}`,
                  color: T.text, fontSize: '0.86rem', outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>
          </div>

          {/* Category Filter Pills */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.76rem', color: '#6b7080', fontWeight: 700, marginRight: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Filter size={14} /> Categoria:
            </span>

            {[
              { id: 'all', label: 'Tutti', icon: Home, count: devices.length },
              { id: 'light', label: 'Luci', icon: Lightbulb, count: devices.filter(d => d.domain === 'light').length },
              { id: 'switch', label: 'Prese & Interruttori', icon: Plug, count: devices.filter(d => d.domain === 'switch').length },
              { id: 'climate', label: 'Clima', icon: Thermometer, count: devices.filter(d => d.domain === 'climate').length },
              { id: 'sensor', label: 'Sensori', icon: Activity, count: devices.filter(d => d.domain === 'sensor').length },
              { id: 'media', label: 'Media', icon: Music, count: devices.filter(d => d.domain === 'media_player').length },
              { id: 'security', label: 'Sicurezza', icon: Lock, count: devices.filter(d => d.domain === 'lock' || d.domain === 'camera').length },
            ].map(cat => {
              const IconComp = cat.icon;
              const isSel = selectedDomain === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedDomain(cat.id)}
                  style={{
                    padding: '6px 14px', borderRadius: '20px',
                    background: isSel ? 'rgba(0, 210, 255, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid ' + (isSel ? 'rgba(0, 210, 255, 0.4)' : 'rgba(255, 255, 255, 0.08)'),
                    color: isSel ? '#00d2ff' : '#8b8fa3', fontSize: '0.76rem', fontWeight: 700,
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <IconComp size={13} />
                  <span>{cat.label}</span>
                  <span style={{ fontSize: '0.66rem', padding: '1px 6px', borderRadius: '10px', background: isSel ? 'rgba(0, 210, 255, 0.3)' : 'rgba(255, 255, 255, 0.08)', color: isSel ? '#fff' : '#6b7080' }}>
                    {cat.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Real Devices Grid + Event Logs */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '28px', marginBottom: '48px' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>💡</span> Dispositivi Reali Rilevati ({filteredDevices.length} / {devices.length})
            </h2>

            {filteredDevices.length === 0 ? (
              <div style={{
                padding: '40px 24px', borderRadius: '20px', background: 'rgba(14, 17, 25, 0.6)',
                border: '1px dashed rgba(255, 255, 255, 0.15)', textAlign: 'center',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px'
              }}>
                <Search size={38} color="#6b7080" />
                <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#c0c4d0' }}>
                  {searchQuery ? `Nessun dispositivo trovato per "${searchQuery}"` : 'Nessun dispositivo reale rilevato'}
                </div>
                <p style={{ fontSize: '0.78rem', color: '#6b7080', margin: 0, maxWidth: '380px' }}>
                  Esegui una scansione della rete Home Assistant o modifica i filtri di ricerca per trovare i tuoi dispositivi.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {filteredDevices.map(dev => {
                  const isLight = dev.domain === 'light';
                  const isClimate = dev.domain === 'climate';
                  const isActive = dev.state === 'on' || dev.state === 'active' || dev.state === 'auto';
                  const IconComp = dev.meta.icon;
                  const glowColor = isLight && isActive ? (dev.color || '#00d2ff') : (isActive ? '#00d2ff' : '#6b7080');

                  return (
                    <div
                      key={dev.id}
                      className="domotica-device-card primi-passi-card"
                      style={{
                        padding: '18px 20px', borderRadius: '16px',
                        backgroundColor: T.cardBg,
                        border: '1px solid ' + (isActive ? T.accent : T.border),
                        boxShadow: isActive ? `0 4px 20px ${glowColor}15` : 'none', transition: 'all 0.25s ease'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                          <div style={{
                            width: '42px', height: '42px', borderRadius: '12px',
                            background: isActive ? `${glowColor}25` : 'rgba(255, 255, 255, 0.04)',
                            border: '1px solid ' + (isActive ? glowColor : 'transparent'),
                            color: glowColor, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: isActive ? `0 0 12px ${glowColor}40` : 'none'
                          }}>
                            <IconComp size={22} />
                          </div>

                          <div>
                            {editingId === dev.id ? (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <input
                                  type="text"
                                  value={editInputValue}
                                  onChange={e => setEditInputValue(e.target.value)}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter') saveCustomName(dev.id, editInputValue);
                                    if (e.key === 'Escape') setEditingId(null);
                                  }}
                                  autoFocus
                                  style={{
                                    padding: '4px 8px', borderRadius: '6px',
                                    background: 'rgba(8, 10, 16, 0.9)', border: '1px solid rgba(0, 210, 255, 0.4)',
                                    color: '#fff', fontSize: '0.88rem', outline: 'none'
                                  }}
                                />
                                <button
                                  onClick={() => saveCustomName(dev.id, editInputValue)}
                                  style={{ padding: '4px 8px', borderRadius: '6px', background: '#3fb950', border: 'none', color: '#fff', cursor: 'pointer' }}
                                >
                                  <Check size={13} />
                                </button>
                                <button
                                  onClick={() => setEditingId(null)}
                                  style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.1)', border: 'none', color: '#aaa', cursor: 'pointer' }}
                                >
                                  <X size={13} />
                                </button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#fff' }}>{dev.name}</div>
                                <button
                                  onClick={() => { setEditingId(dev.id); setEditInputValue(dev.name); }}
                                  style={{ background: 'none', border: 'none', color: '#6b7080', cursor: 'pointer', padding: 0 }}
                                  title="Rinomina dispositivo"
                                >
                                  <Pencil size={12} />
                                </button>
                              </div>
                            )}
                            <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginTop: '2px' }}>
                              <code style={{ color: '#00d2ff' }}>{dev.id}</code> • {dev.room}
                            </div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {isLight && (
                            <button
                              onClick={() => setExpandedControl(expandedControl === dev.id ? null : dev.id)}
                              style={{
                                padding: '6px 10px', borderRadius: '10px',
                                background: expandedControl === dev.id ? 'rgba(0, 210, 255, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                                border: '1px solid rgba(255, 255, 255, 0.1)', color: '#e2e8f0', fontSize: '0.72rem', fontWeight: 600,
                                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                              }}
                            >
                              <Sliders size={14} /> Regola
                            </button>
                          )}

                          <button
                            onClick={() => toggleDevice(dev.id)}
                            style={{
                              padding: '6px 16px', borderRadius: '20px',
                              border: '1px solid ' + (isActive ? `${glowColor}60` : 'rgba(255, 255, 255, 0.1)'),
                              background: isActive ? `${glowColor}20` : 'rgba(255, 255, 255, 0.05)',
                              color: isActive ? glowColor : '#8b8fa3', fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer'
                            }}
                          >
                            {(dev.state || 'OFF').toUpperCase()}
                          </button>
                        </div>
                      </div>

                      {/* Light Intensity & RGB Controls */}
                      {isLight && (expandedControl === dev.id || isActive) && (
                        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600, marginBottom: '6px' }}>
                              <span>Intensità Luminosa ({dev.name}):</span>
                              <span style={{ color: glowColor, fontWeight: 800 }}>{dev.brightness || 0}%</span>
                            </div>
                            <input
                              type="range" min="0" max="100" value={dev.brightness || 0}
                              onChange={(e) => updateBrightness(dev.id, parseInt(e.target.value, 10))}
                              style={{ width: '100%', accentColor: glowColor, cursor: 'pointer' }}
                            />
                          </div>

                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600, marginBottom: '8px' }}>
                              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                                <Palette size={13} /> Selezione Colore:
                              </span>
                              <input
                                type="color" value={dev.color || '#00d2ff'}
                                onChange={(e) => updateColor(dev.id, e.target.value)}
                                style={{ width: '28px', height: '24px', border: 'none', borderRadius: '6px', cursor: 'pointer', background: 'none' }}
                              />
                            </div>

                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              {COLOR_PRESETS.map(preset => (
                                <button
                                  key={preset.hex}
                                  onClick={() => updateColor(dev.id, preset.hex, preset.rgb)}
                                  style={{
                                    padding: '4px 10px', borderRadius: '12px',
                                    background: dev.color === preset.hex ? `${preset.hex}30` : 'rgba(255,255,255,0.04)',
                                    border: `1px solid ${dev.color === preset.hex ? preset.hex : 'rgba(255,255,255,0.1)'}`,
                                    color: dev.color === preset.hex ? '#fff' : '#8b8fa3', fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', gap: '6px'
                                  }}
                                >
                                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: preset.hex }} />
                                  {preset.name}
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Climate Setpoint Controls */}
                      {isClimate && (
                        <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '0.76rem', color: '#8b8fa3', fontWeight: 600 }}>Temperatura Target:</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <button
                              onClick={() => updateSetpoint(dev.id, -1)}
                              style={{ width: '28px', height: '28px', borderRadius: '8px', background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)', color: '#00d2ff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                            >
                              <Minus size={14} />
                            </button>
                            <span style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>{dev.setpoint || 21}°C</span>
                            <button
                              onClick={() => updateSetpoint(dev.id, 1)}
                              style={{ width: '28px', height: '28px', borderRadius: '8px', background: 'rgba(255, 80, 100, 0.15)', border: '1px solid rgba(255, 80, 100, 0.3)', color: '#ff5064', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                        </div>
                      )}

                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Event Logs Panel */}
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff', margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📜</span> Log Eventi MCP Home Assistant
            </h2>
            <div className="domotica-card primi-passi-card" style={{
              padding: '18px', borderRadius: '16px', backgroundColor: T.cardBg,
              border: `1px solid ${T.border}`, maxHeight: '620px', overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: '10px'
            }}>
              {logs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '10px 14px', borderRadius: '10px',
                    background: isThemeLight ? '#f2ede2' : '#0c0e16',
                    borderLeft: `3px solid ${log.type === 'success' ? '#3fb950' : (log.type === 'action' ? '#00d2ff' : (log.type === 'ai' ? '#a78bfa' : '#6b7080'))}`,
                    fontSize: '0.78rem'
                  }}
                >
                  <div style={{ color: T.muted, fontSize: '0.7rem', marginBottom: '2px' }}>{log.time}</div>
                  <div style={{ color: T.text, fontWeight: 500 }}>{log.msg}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Standby / Inactive Smart Features Section (Card Grigie) ── */}
        <div style={{ marginTop: '48px' }}>
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#8b8fa3', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
              <Layers size={13} /> MODULI DI ESPANSIONE PRONTI PER L'ATTIVAZIONE
            </div>
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: '#fff' }}>
              ⚡ Funzionalità Domotiche Avanzate da Attivare
            </h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#8b8fa3' }}>
              Moduli di domotica intelligente in attesa di configurazione hardware o pairing sensori:
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
            {INACTIVE_FEATURES.map(feat => {
              const IconComp = feat.icon;
              const isActivated = activatedFeatures[feat.id];

              return (
                <div
                  key={feat.id}
                  className="domotica-inactive-card primi-passi-card"
                  style={{
                    padding: '24px', borderRadius: '18px',
                    backgroundColor: T.cardBg,
                    border: '1px solid ' + (isActivated ? `${feat.color}40` : T.border),
                    boxShadow: isActivated ? `0 8px 32px ${feat.color}15` : 'none',
                    display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                    gap: '16px', opacity: isActivated ? 1 : 0.72,
                    filter: isActivated ? 'none' : 'grayscale(35%)',
                    transition: 'all 0.3s ease'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                      <div style={{
                        width: '44px', height: '44px', borderRadius: '12px',
                        background: isActivated ? `${feat.color}25` : 'rgba(255, 255, 255, 0.04)',
                        border: '1px solid ' + (isActivated ? feat.color : 'rgba(255,255,255,0.08)'),
                        color: isActivated ? feat.color : '#8b8fa3',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        <IconComp size={22} />
                      </div>

                      <span style={{
                        fontSize: '0.68rem', fontWeight: 800,
                        color: isActivated ? '#3fb950' : '#8b8fa3',
                        background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.1)'),
                        padding: '3px 10px', borderRadius: '20px', letterSpacing: '0.5px'
                      }}>
                        {isActivated ? 'ATTIVO ⚡' : feat.statusBadge}
                      </span>
                    </div>

                    <h3 style={{ margin: '0 0 6px 0', fontSize: '1rem', fontWeight: 800, color: '#fff' }}>
                      {feat.title}
                    </h3>
                    <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                      {feat.subtitle}
                    </p>
                    <div style={{ fontSize: '0.72rem', color: '#6b7080', background: 'rgba(8, 10, 16, 0.6)', padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                      <strong>Requisito:</strong> {feat.prerequisite}
                    </div>
                  </div>

                  <button
                    onClick={() => setActiveFeatureModal(feat)}
                    disabled={isActivated}
                    style={{
                      padding: '10px 16px', borderRadius: '10px',
                      background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.12)'),
                      color: isActivated ? '#3fb950' : '#e2e8f0', fontSize: '0.8rem', fontWeight: 700,
                      cursor: isActivated ? 'default' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {isActivated ? <CheckCircle2 size={15} /> : <ArrowRight size={15} />}
                    {isActivated ? 'Modulo Attivato' : feat.actionText}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Feature Activation Modal */}
      {activeFeatureModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', background: 'rgba(18, 20, 28, 0.95)',
            border: `1px solid ${activeFeatureModal.color}40`, borderRadius: '20px',
            padding: '28px', boxShadow: '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: activeFeatureModal.color }}>
              <activeFeatureModal.icon size={26} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                  {activeFeatureModal.title}
                </h2>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginTop: '2px' }}>
                  {activeFeatureModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#c0c4d0', lineHeight: 1.6, marginBottom: '20px' }}>
              {activeFeatureModal.details}
            </p>

            <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '24px', fontSize: '0.78rem', color: '#8b8fa3' }}>
              <div style={{ fontWeight: 700, color: '#fff', marginBottom: '4px' }}>📋 Prerequisito Hardware / Sensore:</div>
              {activeFeatureModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveFeatureModal(null)}
                style={{ padding: '10px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
              >
                Annulla
              </button>
              <button
                onClick={() => handleActivateFeature(activeFeatureModal)}
                disabled={activatingId === activeFeatureModal.id}
                style={{
                  padding: '10px 22px', borderRadius: '10px',
                  background: `linear-gradient(135deg, ${activeFeatureModal.color}, #00d2ff)`, border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}
              >
                {activatingId === activeFeatureModal.id ? <RefreshCw className="spin" size={15} /> : <Zap size={15} />}
                {activatingId === activeFeatureModal.id ? 'Attivazione...' : 'Connetti & Attiva Modulo ⚡'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* HA Config Modal */}
      {showConfigModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '540px', background: 'rgba(18, 20, 28, 0.95)',
            border: '1px solid rgba(0, 210, 255, 0.3)', borderRadius: '20px',
            padding: '28px', boxShadow: '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', color: '#00d2ff' }}>
              <Key size={24} />
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                Configurazione Home Assistant
              </h2>
            </div>
            <p style={{ fontSize: '0.82rem', color: '#8b8fa3', lineHeight: 1.5, marginBottom: '20px' }}>
              Inserisci l'URL del tuo server Home Assistant ed un Long-Lived Access Token (generato in HA &rarr; Profilo Utente &rarr; Token a Lunga Durata) per consentire a Sigma Studio di scansionare ed operare sui tuoi dispositivi reali.
            </p>

            <form onSubmit={saveHaIntegration} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: '#c0c4d0', fontWeight: 700, marginBottom: '6px' }}>
                  URL Istanza Home Assistant:
                </label>
                <input
                  type="text" value={haUrl} onChange={e => setHaUrl(e.target.value)}
                  placeholder="http://192.168.1.100:8123" required
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '10px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '0.85rem', boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: '#c0c4d0', fontWeight: 700, marginBottom: '6px' }}>
                  Long-Lived Access Token (Bearer Token):
                </label>
                <textarea
                  value={haToken} onChange={e => setHaToken(e.target.value)}
                  placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." required rows={4}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '10px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '0.82rem', fontFamily: 'monospace', boxSizing: 'border-box' }}
                />
              </div>

              {testStatus && (
                <div style={{
                  padding: '12px 16px', borderRadius: '10px',
                  background: testStatus.success ? 'rgba(63, 185, 80, 0.12)' : 'rgba(255, 80, 100, 0.12)',
                  border: `1px solid ${testStatus.success ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 80, 100, 0.3)'}`,
                  color: testStatus.success ? '#3fb950' : '#ff5064', fontSize: '0.8rem', fontWeight: 600, lineHeight: 1.4
                }}>
                  {testStatus.msg}
                </div>
              )}

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button" onClick={testHaConnection} disabled={testLoading || !haUrl || !haToken}
                  style={{
                    padding: '10px 16px', borderRadius: '10px',
                    background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)',
                    color: '#00d2ff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700,
                    display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <FlaskConical size={15} className={testLoading ? 'spin' : ''} />
                  {testLoading ? 'Verifica...' : '🧪 Test Connessione'}
                </button>

                <button
                  type="button" onClick={() => setShowConfigModal(false)}
                  style={{ padding: '10px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
                >
                  Annulla
                </button>

                <button
                  type="submit" disabled={savingConfig}
                  style={{ padding: '10px 22px', borderRadius: '10px', background: 'linear-gradient(135deg, #00d2ff, #3fb950)', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700 }}
                >
                  {savingConfig ? 'Salvataggio...' : 'Connetti Home Assistant 🔌'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}