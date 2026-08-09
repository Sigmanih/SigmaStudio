import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Home, Sun, Thermometer, Lock, Power, Lightbulb, RefreshCw, Send,
  Zap, Sliders, Palette, Plus, Minus, Key, AlertCircle, Search, Filter,
  Tv, Music, Camera, Fan, Waves, DoorOpen, ChevronDown, ChevronUp,
  Droplets, ShieldCheck, Plug, Wifi, WifiOff, Pencil, Check, X, FlaskConical
} from 'lucide-react';

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

const SECRET_MARKER = '••••••••';

// ── Domain → UI metadata map ─────────────────────────────────────────────
const DOMAIN_META = {
  light:       { icon: Lightbulb, label: 'Luce',       color: '#fbbf24' },
  switch:      { icon: Plug,       label: 'Presa',       color: '#60a5fa' },
  climate:     { icon: Thermometer, label: 'Clima',      color: '#f87171' },
  lock:        { icon: Lock,       label: 'Serratura',   color: '#a78bfa' },
  cover:       { icon: DoorOpen,   label: 'Tapparella',  color: '#94a3b8' },
  media_player:{ icon: Music,      label: 'Media',       color: '#34d399' },
  camera:      { icon: Camera,     label: 'Telecamera',  color: '#fb923c' },
  vacuum:      { icon: Waves,      label: 'Aspirapolvere', color: '#38bdf8' },
  fan:         { icon: Fan,        label: 'Ventilatore', color: '#818cf8' },
  humidifier:  { icon: Droplets,   label: 'Umidificatore', color: '#2dd4bf' },
};

// ── Shared style tokens ───────────────────────────────────────────────────
const T = {
  bg:       '#080a10',
  cardBg:   'rgba(14,17,25,0.75)',
  cardHover:'rgba(18,22,32,0.85)',
  border:   'rgba(255,255,255,0.06)',
  borderHov:'rgba(255,255,255,0.12)',
  accent:   '#00d2ff',
  accent2:  '#7c5bf0',
  text:     '#e2e8f0',
  muted:    '#8892b0',
  on:       '#3fb950',
  off:      '#4a4f60',
  glow:     c => `0 0 24px ${c}22, 0 0 8px ${c}18`,
};

// ── Toggle Switch component ───────────────────────────────────────────────
function ToggleSwitch({ active, onChange, color }) {
  return (
    <button
      onClick={onChange}
      style={{
        width: 52, height: 28, borderRadius: 14, border: 'none', cursor: 'pointer',
        background: active
          ? `linear-gradient(135deg, ${color}, ${color}cc)`
          : 'rgba(255,255,255,0.08)',
        boxShadow: active ? `0 0 12px ${color}40` : 'inset 0 1px 3px rgba(0,0,0,0.3)',
        position: 'relative', transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        flexShrink: 0,
      }}
    >
      <span style={{
        position: 'absolute', top: 3, left: active ? 27 : 3,
        width: 22, height: 22, borderRadius: '50%',
        background: '#fff', boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
        transition: 'left 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }} />
    </button>
  );
}

// ── Slider component ──────────────────────────────────────────────────────
function GlowSlider({ value, onChange, color, min = 0, max = 100 }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div style={{ position: 'relative', height: 6, flex: 1 }}>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: 3,
        background: 'rgba(255,255,255,0.06)',
      }} />
      <div style={{
        position: 'absolute', top: 0, left: 0, height: 6, borderRadius: 3,
        width: `${pct}%`,
        background: `linear-gradient(90deg, ${color}88, ${color})`,
        boxShadow: `0 0 8px ${color}40`,
        transition: 'width 0.15s ease',
      }} />
      <input
        type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          position: 'absolute', inset: 0, width: '100%', opacity: 0, cursor: 'pointer',
          margin: 0,
        }}
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────
export default function DomoticaTab() {
  const [devices, setDevices] = useState([]);
  const [areas, setAreas] = useState([]);
  const [isConfigured, setIsConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('all');
  const [collapsedRooms, setCollapsedRooms] = useState({});

  // Config modal
  const [serverConfig, setServerConfig] = useState({});
  const [haUrl, setHaUrl] = useState('http://homeassistant.local:8123');
  const [haToken, setHaToken] = useState('');
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [testStatus, setTestStatus] = useState(null);

  // Control
  const [expandedDevice, setExpandedDevice] = useState(null);
  const [editingName, setEditingName] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [prompt, setPrompt] = useState('');
  const [logs, setLogs] = useState([{ time: new Date().toLocaleTimeString(), msg: 'Bus domotico inizializzato.', type: 'info' }]);
  const [aiLoading, setAiLoading] = useState(false);
  const [customNames, setCustomNames] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CUSTOM_NAMES_KEY) || '{}'); }
    catch { return {}; }
  });

  const addLog = (msg, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs(p => [{ time, msg, type }, ...p].slice(0, 100));
  };

  const saveCustomNames = (patch) => {
    const next = { ...customNames, ...patch };
    // Remove entries that reset to default (empty)
    for (const k of Object.keys(next)) { if (!next[k]) delete next[k]; }
    setCustomNames(next);
    try { localStorage.setItem(CUSTOM_NAMES_KEY, JSON.stringify(next)); } catch {}
  };

  const deviceName = (dev) => customNames[dev.id] || dev.name || dev.id;

  // ── Data fetching ────────────────────────────────────────────────────────
  const fetchHaEntities = async () => {
    setLoading(true);
    addLog('Scansione dispositivi Home Assistant in corso…', 'info');
    try {
      const res = await fetch('/api/mcp/ha/entities');
      if (!res.ok) { setIsConfigured(false); return; }
      const data = await res.json();
      if (data.is_configured && data.entities?.length > 0) {
        setIsConfigured(true);
        const mapped = data.entities.map(e => mapEntity(e));
        setDevices(mapped);
        setAreas(data.areas || []);
        addLog(`${mapped.length} dispositivi trovati in ${(data.areas || []).length} stanze.`, 'success');
      } else {
        setIsConfigured(false);
        setDevices([]); setAreas([]);
        if (data.error) addLog(data.error, 'action');
      }
    } catch (e) {
      setIsConfigured(false);
      addLog(`Errore: ${e.message}`, 'action');
    } finally { setLoading(false); }
  };

  const loadServerConfig = async () => {
    try {
      const res = await fetch('/api/mcp/servers');
      const d = await res.json();
      const ha = (d.servers || []).find(s => s.integration_key === 'home_assistant');
      if (ha?.config) {
        setServerConfig(ha.config);
        setHaUrl(ha.config.base_url || 'http://homeassistant.local:8123');
        setHaToken(ha.config.token || '');
      }
    } catch {}
  };

  useEffect(() => { fetchHaEntities(); loadServerConfig(); }, []);

  const openConfigModal = () => { setTestStatus(null); loadServerConfig(); setShowConfigModal(true); };

  // ── Entity mapping ───────────────────────────────────────────────────────
  const mapEntity = (e) => {
    const domain = e.entity_id.split('.')[0];
    const meta = DOMAIN_META[domain] || DOMAIN_META.switch;
    return {
      id: e.entity_id,
      name: e.name || e.entity_id,
      domain,
      type: domain,
      icon: meta.icon,
      color: meta.color,
      state: (e.state || 'off').toLowerCase(),
      brightness: e.capabilities?.brightness != null ? Math.round(e.capabilities.brightness / 2.55) : 80,
      kelvin: e.capabilities?.kelvin_range || [2700, 6500],
      kelvinVal: e.capabilities?.kelvin_range ? e.capabilities.kelvin_range[1] : 4000,
      rgbColor: e.capabilities?.rgb_color || [0, 210, 255],
      effects: e.capabilities?.effects || [],
      currentEffect: e.capabilities?.current_effect || '',
      colorModes: e.capabilities?.color_modes || [],
      unit: e.unit || '',
      setpoint: 21,
    };
  };

  // ── Room grouping ────────────────────────────────────────────────────────
  const roomGroups = useMemo(() => {
    // Build a lookup: entity_id → area name
    const entityArea = {};
    for (const area of areas) {
      for (const eid of (area.entities || [])) {
        entityArea[eid] = area.name || area.id;
      }
    }

    const groups = {};
    for (const dev of devices) {
      const room = entityArea[dev.id] || 'Altri dispositivi';
      if (!groups[room]) groups[room] = [];
      groups[room].push(dev);
    }

    // Sort rooms: keep "Altri dispositivi" last
    return Object.entries(groups).sort(([a], [b]) =>
      a === 'Altri dispositivi' ? 1 : b === 'Altri dispositivi' ? -1 : a.localeCompare(b));
  }, [devices, areas]);

  const toggleRoom = (room) => setCollapsedRooms(p => ({ ...p, [room]: !p[room] }));

  // ── Domain filter pills ──────────────────────────────────────────────────
  const domainCounts = useMemo(() => {
    const counts = { all: devices.length };
    for (const d of devices) counts[d.domain] = (counts[d.domain] || 0) + 1;
    return counts;
  }, [devices]);

  const filterPills = [
    { id: 'all', label: 'Tutti', icon: Home },
    ...Object.entries(DOMAIN_META).filter(([k]) => domainCounts[k] > 0).map(([k, v]) => ({
      id: k, label: v.label, icon: v.icon,
    })),
  ];

  const filteredDeviceIds = useMemo(() => {
    const s = searchQuery.toLowerCase();
    return new Set(devices.filter(d => {
      const domainOk = selectedDomain === 'all' || d.domain === selectedDomain;
      const searchOk = !s || d.name.toLowerCase().includes(s) || d.id.toLowerCase().includes(s);
      return domainOk && searchOk;
    }).map(d => d.id));
  }, [devices, searchQuery, selectedDomain]);

  // ── Control actions ──────────────────────────────────────────────────────
  const sendControl = async (id, payload) => {
    try {
      const res = await fetch('/api/mcp/ha/control', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: id, ...payload }),
      });
      const data = await res.json();
      if (data.success) addLog(`${id}: OK`, 'success');
      else addLog(`${id}: ${data.error || 'fallito'}`, 'action');
    } catch (e) { addLog(`${id}: ${e.message}`, 'action'); }
  };

  // Command an entire area via the new 'area' parameter (one API call).
  const sendAreaControl = async (area, domain, payload) => {
    try {
      const res = await fetch('/api/mcp/ha/control', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ area, domain, ...payload }),
      });
      const data = await res.json();
      if (data.success) addLog(`${area} (${domain}): OK`, 'success');
      else addLog(`${area}: ${data.error || 'fallito'}`, 'action');
    } catch (e) { addLog(`${area}: ${e.message}`, 'action'); }
  };

  const toggleDevice = (dev) => {
    const next = dev.state === 'on' ? 'off' : 'on';
    setDevices(p => p.map(d => d.id === dev.id ? { ...d, state: next } : d));
    sendControl(dev.id, { state: next });
    addLog(`${deviceName(dev)} → ${next.toUpperCase()}`, 'action');
  };

  const setBrightness = (dev, val) => {
    setDevices(p => p.map(d => d.id === dev.id ? { ...d, brightness: val, state: val > 0 ? 'on' : 'off' } : d));
    sendControl(dev.id, { state: val > 0 ? 'on' : 'off', brightness: val });
  };

  const setColor = (dev, hex, rgb) => {
    setDevices(p => p.map(d => d.id === dev.id ? { ...d, rgbColor: rgb, state: 'on' } : d));
    sendControl(dev.id, { state: 'on', color_rgb: rgb });
  };

  const setKelvin = (dev, k) => {
    setDevices(p => p.map(d => d.id === dev.id ? { ...d, kelvinVal: k, state: 'on' } : d));
    sendControl(dev.id, { state: 'on', color_temp_kelvin: k });
  };

  const setSetpoint = (dev, delta) => {
    const next = Math.max(16, Math.min(30, (dev.setpoint || 21) + delta));
    setDevices(p => p.map(d => d.id === dev.id ? { ...d, setpoint: next } : d));
    sendControl(dev.id, { setpoint: next });
  };

  // ── AI command via real agent ────────────────────────────────────────────
  const handleAiCommand = async (e) => {
    e.preventDefault();
    if (!prompt.trim() || !isConfigured) return;
    setAiLoading(true);
    const cmd = prompt.trim(); setPrompt('');
    addLog(`💬 "${cmd}"`, 'ai');
    try {
      const res = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: cmd, session_id: 'domotica_tab' }),
      });
      if (!res.ok) { addLog(`AI non raggiungibile (${res.status})`, 'action'); setAiLoading(false); return; }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = '', buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const p = line.slice(6);
            if (p === '[DONE]') continue;
            try { const j = JSON.parse(p); if (j.response) full = j.response; } catch {}
          }
        }
      }
      if (full) addLog(`AI: ${full}`, 'success');
      await fetchHaEntities();
    } catch (err) { addLog(`AI: ${err.message}`, 'action'); }
    finally { setAiLoading(false); }
  };

  // ── Config modal handlers ────────────────────────────────────────────────
  const testHaConnection = async () => {
    setTestLoading(true); setTestStatus(null);
    const urlChanged = haUrl && haUrl !== serverConfig.base_url;
    const tokenWritten = haToken && haToken !== SECRET_MARKER && haToken !== serverConfig.token;
    const body = (urlChanged || tokenWritten)
      ? { key: 'home_assistant', values: { base_url: haUrl, token: haToken } }
      : { key: 'home_assistant' };
    try {
      const res = await fetch('/api/mcp/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      setTestStatus(data.success
        ? { ok: true, msg: `✅ Connesso! ${data.result?.entities?.length || data.result?.total_found || 0} entità.` }
        : { ok: false, msg: `❌ ${data.error || 'Fallito'}` });
    } catch (err) { setTestStatus({ ok: false, msg: `❌ ${err.message}` }); }
    finally { setTestLoading(false); }
  };

  const saveHaIntegration = async (e) => {
    e.preventDefault(); setSavingConfig(true);
    try {
      await fetch('/api/mcp/integration', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'home_assistant', values: { base_url: haUrl, token: haToken } }),
      });
      setShowConfigModal(false);
      await fetchHaEntities();
      addLog('Configurazione salvata.', 'success');
    } catch (err) { addLog(`Salvataggio fallito: ${err.message}`, 'action'); }
    finally { setSavingConfig(false); }
  };

  // ── Device card ──────────────────────────────────────────────────────────
  const DeviceCard = ({ dev }) => {
    const meta = DOMAIN_META[dev.domain] || DOMAIN_META.switch;
    const IconC = meta.icon;
    const active = dev.state === 'on' || dev.state === 'playing' || dev.state === 'open';
    const glow = active ? dev.color || meta.color : T.off;
    const isExpanded = expandedDevice === dev.id;
    const hidden = !filteredDeviceIds.has(dev.id);
    const isEditing = editingName === dev.id;

    const startEdit = () => { setEditingName(dev.id); setEditValue(deviceName(dev)); };
    const confirmEdit = () => {
      if (editValue.trim() && editValue.trim() !== (dev.name || dev.id)) {
        saveCustomNames({ [dev.id]: editValue.trim() });
      } else {
        saveCustomNames({ [dev.id]: '' });
      }
      setEditingName(null);
    };
    const cancelEdit = () => setEditingName(null);

    if (hidden) return null;

    return (
      <div style={{
        background: isExpanded ? T.cardHover : T.cardBg,
        border: `1px solid ${isExpanded ? T.borderHov : T.border}`,
        borderRadius: 16, padding: '20px 22px',
        backdropFilter: 'blur(20px)',
        boxShadow: isExpanded ? T.glow(glow) : '0 4px 16px rgba(0,0,0,0.2)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {/* Top row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flex: 1, minWidth: 0 }}>
            <div style={{
              width: 46, height: 46, borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: active ? `${glow}18` : 'rgba(255,255,255,0.04)',
              border: `1px solid ${active ? `${glow}40` : 'transparent'}`,
              boxShadow: active ? `0 0 16px ${glow}30` : 'none',
              transition: 'all 0.3s ease',
            }}>
              <IconC size={22} color={active ? glow : T.muted} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              {isEditing ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input autoFocus value={editValue} onChange={e => setEditValue(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') confirmEdit(); if (e.key === 'Escape') cancelEdit(); }}
                    style={{
                      flex: 1, background: 'rgba(8,10,16,0.9)', border: `1px solid ${T.accent}40`,
                      borderRadius: 8, color: '#fff', padding: '4px 10px', fontSize: '0.88rem', outline: 'none',
                    }} />
                  <button onClick={confirmEdit} style={{ background: 'none', border: 'none', color: T.on, cursor: 'pointer', padding: 2 }}>
                    <Check size={14} />
                  </button>
                  <button onClick={cancelEdit} style={{ background: 'none', border: 'none', color: '#ff5064', cursor: 'pointer', padding: 2 }}>
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: '0.9rem', color: T.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {deviceName(dev)}
                  </span>
                  <button onClick={startEdit} style={{ background: 'none', border: 'none', color: T.muted, cursor: 'pointer', padding: 2, opacity: 0.5, flexShrink: 0 }}
                    title="Rinomina">
                    <Pencil size={11} />
                  </button>
                </div>
              )}
              <div style={{ fontSize: '0.7rem', color: T.muted, fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>
                {dev.id}
              </div>
            </div>
          </div>
          <ToggleSwitch active={active} onChange={() => toggleDevice(dev)} color={meta.color} />
        </div>

        {/* Expanded controls */}
        {isExpanded && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 4, borderTop: `1px solid ${T.border}` }}>
            {/* Light controls */}
            {(dev.domain === 'light') && (
              <>
                {/* Brightness */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Sun size={14} color={T.muted} />
                  <GlowSlider value={dev.brightness} onChange={v => setBrightness(dev, v)} color={glow} />
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: T.text, minWidth: 36, textAlign: 'right' }}>
                    {dev.brightness}%
                  </span>
                </div>

                {/* RGB colour picker + presets  */}
                {dev.colorModes.some(m => m === 'hs' || m === 'rgb' || m === 'xy') && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Palette size={14} color={T.muted} />
                      <span style={{ fontSize: '0.72rem', color: T.muted, fontWeight: 600 }}>Colore</span>
                      <input type="color"
                        value={`#${dev.rgbColor.map(c => c.toString(16).padStart(2, '0')).join('')}`}
                        onChange={e => setColor(dev, e.target.value, [
                          parseInt(e.target.value.slice(1,3),16),
                          parseInt(e.target.value.slice(3,5),16),
                          parseInt(e.target.value.slice(5,7),16),
                        ])}
                        style={{ width: 28, height: 22, border: 'none', borderRadius: 6, cursor: 'pointer', background: 'none', marginLeft: 'auto' }}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {COLOR_PRESETS.map(p => (
                        <button key={p.hex} onClick={() => setColor(dev, p.hex, p.rgb)}
                          style={{
                            padding: '4px 10px', borderRadius: 20, border: `1px solid ${p.hex}50`,
                            background: `${p.hex}18`, color: '#fff', fontSize: '0.68rem',
                            fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                          }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.hex, boxShadow: `0 0 6px ${p.hex}60` }} />
                          {p.name}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Colour temperature */}
                {dev.colorModes.includes('color_temp') && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Thermometer size={14} color={T.muted} />
                    <GlowSlider
                      value={dev.kelvinVal} min={dev.kelvin[0]} max={dev.kelvin[1]}
                      onChange={v => setKelvin(dev, v)} color="#f59e0b"
                    />
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, color: T.text, minWidth: 42, textAlign: 'right' }}>
                      {dev.kelvinVal}K
                    </span>
                  </div>
                )}

                {/* Effects */}
                {dev.effects.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <Waves size={14} color={T.muted} />
                    {dev.effects.slice(0, 8).map(eff => (
                      <button key={eff} onClick={() => sendControl(dev.id, { state: 'on', effect: eff })}
                        style={{
                          padding: '4px 10px', borderRadius: 20, fontSize: '0.68rem', fontWeight: 600, cursor: 'pointer',
                          border: `1px solid ${dev.currentEffect === eff ? `${glow}50` : T.border}`,
                          background: dev.currentEffect === eff ? `${glow}18` : 'rgba(255,255,255,0.04)',
                          color: dev.currentEffect === eff ? glow : T.muted,
                        }}>
                        {eff}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* Climate controls */}
            {dev.domain === 'climate' && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
                <button onClick={() => setSetpoint(dev, -1)}
                  style={{ width: 36, height: 36, borderRadius: 12, border: `1px solid ${T.borderHov}`, background: 'rgba(255,255,255,0.04)', color: T.accent, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Minus size={16} />
                </button>
                <span style={{ fontWeight: 800, fontSize: '1.3rem', color: T.text, minWidth: 70, textAlign: 'center' }}>
                  {dev.setpoint || 21}°C
                </span>
                <button onClick={() => setSetpoint(dev, 1)}
                  style={{ width: 36, height: 36, borderRadius: 12, border: `1px solid ${T.borderHov}`, background: 'rgba(255,80,100,0.1)', color: '#ff5064', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Plus size={16} />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Expand/collapse handle */}
        <button onClick={() => setExpandedDevice(isExpanded ? null : dev.id)}
          style={{
            background: 'none', border: 'none', color: T.muted, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
            fontSize: '0.7rem', padding: '2px 0', marginTop: -6,
          }}>
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {isExpanded ? 'Meno opzioni' : 'Controlli'}
        </button>
      </div>
    );
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column', background: T.bg,
      color: T.text, fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
      overflowY: 'auto', overflowX: 'hidden',
    }}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{
        padding: '28px 36px 20px',
        borderBottom: `1px solid ${T.border}`,
        background: 'rgba(8,10,16,0.92)',
        backdropFilter: 'blur(30px)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 16, position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 16,
            background: `linear-gradient(135deg, ${T.accent}22, ${T.accent2}22)`,
            border: `1px solid ${T.accent}40`, display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 4px 20px ${T.accent}20`,
          }}>
            <Home size={26} color={T.accent} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              Domotica
            </h1>
            <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: T.muted }}>
              {isConfigured ? `${devices.length} dispositivi in ${roomGroups.length} stanze` : 'Home Assistant non connesso'}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            padding: '6px 14px', borderRadius: 20, fontSize: '0.74rem', fontWeight: 700,
            display: 'flex', alignItems: 'center', gap: 6,
            background: isConfigured ? 'rgba(63,185,80,0.12)' : 'rgba(210,153,34,0.12)',
            border: `1px solid ${isConfigured ? 'rgba(63,185,80,0.3)' : 'rgba(210,153,34,0.3)'}`,
            color: isConfigured ? T.on : '#d29922',
          }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: isConfigured ? T.on : '#d29922', boxShadow: `0 0 8px ${isConfigured ? T.on : '#d29922'}` }} />
            {isConfigured ? 'Connesso' : 'Non connesso'}
          </div>
          <button onClick={openConfigModal} style={{
            padding: '8px 16px', borderRadius: 12, border: `1px solid ${T.borderHov}`,
            background: 'rgba(255,255,255,0.04)', color: T.accent, fontSize: '0.78rem',
            fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Key size={14} /> Token
          </button>
          <button onClick={fetchHaEntities} style={{
            padding: '8px 18px', borderRadius: 12, border: 'none',
            background: `linear-gradient(135deg, ${T.accent}, ${T.accent2})`,
            color: '#fff', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
            boxShadow: `0 4px 16px ${T.accent}30`,
          }}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Scansiona
          </button>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div style={{ padding: '28px 36px', flex: 1, maxWidth: 1200, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

        {/* Config banner */}
        {!isConfigured && (
          <div style={{
            marginBottom: 28, padding: '24px 28px', borderRadius: 20,
            background: 'linear-gradient(135deg, rgba(210,153,34,0.1), rgba(14,17,25,0.9))',
            border: '1px solid rgba(210,153,34,0.25)', backdropFilter: 'blur(20px)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <AlertCircle size={28} color="#d29922" />
              <div>
                <div style={{ fontWeight: 800, fontSize: '1rem', color: '#fff' }}>Connetti Home Assistant</div>
                <div style={{ fontSize: '0.8rem', color: T.muted, marginTop: 4 }}>
                  Inserisci URL e Long-Lived Access Token per controllare i tuoi dispositivi.
                </div>
              </div>
            </div>
            <button onClick={openConfigModal} style={{
              padding: '12px 24px', borderRadius: 14, border: 'none',
              background: 'linear-gradient(135deg, #d29922, #00d2ff)', color: '#fff',
              fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,210,255,0.2)',
            }}>🔑 Configura</button>
          </div>
        )}

        {/* AI command bar */}
        <div style={{
          padding: '18px 22px', borderRadius: 18, marginBottom: 24,
          background: T.cardBg, border: `1px solid ${T.border}`, backdropFilter: 'blur(20px)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontSize: '0.82rem', fontWeight: 700, color: T.accent }}>
            <Zap size={15} /> Comando vocale AI
          </div>
          <form onSubmit={handleAiCommand} style={{ display: 'flex', gap: 10 }}>
            <input type="text" value={prompt} onChange={e => setPrompt(e.target.value)}
              placeholder={"Spegni le luci dell'ufficio e metti blu la scrivania"}
              style={{
                flex: 1, padding: '12px 18px', borderRadius: 12,
                background: 'rgba(8,10,16,0.8)', border: `1px solid ${T.border}`,
                color: '#fff', fontSize: '0.86rem', outline: 'none',
              }}
            />
            <button type="submit" disabled={aiLoading} style={{
              padding: '12px 20px', borderRadius: 12, border: 'none',
              background: `linear-gradient(135deg, ${T.accent}, ${T.accent2})`,
              color: '#fff', fontWeight: 700, fontSize: '0.82rem', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              {aiLoading ? <RefreshCw size={15} className="spin" /> : <Send size={15} />} Invia
            </button>
          </form>
        </div>

        {/* Search + filter pills */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 28 }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: T.muted }} />
            <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              placeholder="Cerca dispositivo o stanza..."
              style={{
                width: '100%', padding: '11px 16px 11px 40px', borderRadius: 14,
                background: T.cardBg, border: `1px solid ${T.border}`, color: T.text,
                fontSize: '0.84rem', outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {filterPills.map(p => {
              const IconP = p.icon;
              const sel = selectedDomain === p.id;
              return (
                <button key={p.id} onClick={() => setSelectedDomain(p.id)} style={{
                  padding: '5px 12px', borderRadius: 20, fontSize: '0.73rem', fontWeight: 700, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: sel ? `${T.accent}18` : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${sel ? `${T.accent}40` : T.border}`,
                  color: sel ? T.accent : T.muted,
                }}>
                  <IconP size={12} /> {p.label}
                  <span style={{ fontSize: '0.65rem', padding: '1px 6px', borderRadius: 10, background: 'rgba(255,255,255,0.06)' }}>
                    {domainCounts[p.id] || 0}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Room groups */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
          {roomGroups.map(([room, roomDevices]) => {
            const visibleCount = roomDevices.filter(d => filteredDeviceIds.has(d.id)).length;
            if (visibleCount === 0) return null;
            const collapsed = collapsedRooms[room];
            const lightsInRoom = roomDevices.filter(d => d.domain === 'light');
            const hasLights = lightsInRoom.length > 0;
            const anyLightOn = lightsInRoom.some(d => d.state === 'on');
            const avgBrightness = hasLights ? Math.round(lightsInRoom.reduce((s, d) => s + d.brightness, 0) / lightsInRoom.length) : 50;
            const roomHasRgb = lightsInRoom.some(d => d.colorModes.some(m => m === 'hs' || m === 'rgb' || m === 'xy'));
            const roomHasKelvin = lightsInRoom.some(d => d.colorModes.includes('color_temp'));
            const avgKelvin = roomHasKelvin ? Math.round(lightsInRoom.reduce((s, d) => s + (d.kelvinVal || 4000), 0) / lightsInRoom.length) : 4000;

            return (
              <div key={room}>
                <button onClick={() => toggleRoom(room)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', color: T.text,
                  display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0', marginBottom: 12,
                  width: '100%', textAlign: 'left',
                }}>
                  <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.2px' }}>
                    {room}
                  </h2>
                  <span style={{ fontSize: '0.76rem', color: T.muted, fontWeight: 600 }}>
                    {visibleCount} dispositivi
                  </span>
                  {collapsed ? <ChevronDown size={16} color={T.muted} /> : <ChevronUp size={16} color={T.muted} />}
                </button>

                {/* Master control bar for the room (lights only) */}
                {!collapsed && hasLights && (
                  <div style={{
                    padding: '14px 18px', borderRadius: 14, marginBottom: 12,
                    background: T.cardBg, border: `1px solid ${T.border}`,
                    display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
                    backdropFilter: 'blur(14px)',
                  }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: T.muted, whiteSpace: 'nowrap' }}>
                      🎛️ {lightsInRoom.length} luci
                    </span>

                    {/* Master toggle */}
                    <ToggleSwitch active={anyLightOn} onChange={() =>
                      sendAreaControl(room, 'light', { state: anyLightOn ? 'off' : 'on' })
                    } color="#fbbf24" />
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: anyLightOn ? T.on : T.muted, minWidth: 32 }}>
                      {anyLightOn ? 'ON' : 'OFF'}
                    </span>

                    {/* Master brightness */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 120 }}>
                      <Sun size={13} color={T.muted} />
                      <GlowSlider value={avgBrightness} onChange={v => {
                        // Update all lights locally, then send one area call
                        lightsInRoom.forEach(d => setBrightness(d, v));
                        sendAreaControl(room, 'light', { state: v > 0 ? 'on' : 'off', brightness: v });
                      }} color="#fbbf24" />
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: T.text, minWidth: 30, textAlign: 'right' }}>
                        {avgBrightness}%
                      </span>
                    </div>

                    {/* Master colour presets */}
                    {roomHasRgb && (
                      <div style={{ display: 'flex', gap: 4 }}>
                        {COLOR_PRESETS.slice(0, 6).map(p => (
                          <button key={p.hex} onClick={() => {
                            lightsInRoom.forEach(d => setColor(d, p.hex, p.rgb));
                            sendAreaControl(room, 'light', { state: 'on', color_rgb: p.rgb });
                          }}
                          style={{ width: 18, height: 18, borderRadius: '50%', border: `1px solid ${p.hex}60`, background: p.hex, cursor: 'pointer', padding: 0 }}
                          title={p.name} />
                        ))}
                      </div>
                    )}

                    {/* Master kelvin */}
                    {roomHasKelvin && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 100 }}>
                        <Thermometer size={12} color={T.muted} />
                        <GlowSlider value={avgKelvin} min={2000} max={6500}
                          onChange={v => {
                            lightsInRoom.forEach(d => setKelvin(d, v));
                            sendAreaControl(room, 'light', { state: 'on', color_temp_kelvin: v });
                          }} color="#f59e0b" />
                        <span style={{ fontSize: '0.68rem', color: T.muted }}>{avgKelvin}K</span>
                      </div>
                    )}
                  </div>
                )}

                {!collapsed && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 }}>
                    {roomDevices.map(d => <DeviceCard key={d.id} dev={d} />)}
                  </div>
                )}
              </div>
            );
          })}

          {roomGroups.length === 0 && !loading && (
            <div style={{ textAlign: 'center', padding: 60, color: T.muted }}>
              <Home size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
              <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: 8 }}>Nessun dispositivo trovato</div>
              <p style={{ fontSize: '0.82rem', margin: 0 }}>Connetti Home Assistant per vedere i tuoi dispositivi.</p>
            </div>
          )}
        </div>

        {/* Log panel */}
        <details style={{ marginTop: 32, cursor: 'pointer' }}>
          <summary style={{ fontSize: '0.85rem', fontWeight: 700, color: T.muted, marginBottom: 10 }}>
            📜 Log eventi ({logs.length})
          </summary>
          <div style={{
            padding: 16, borderRadius: 14, maxHeight: 280, overflowY: 'auto',
            background: T.cardBg, border: `1px solid ${T.border}`,
            display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.76rem',
          }}>
            {logs.map((l, i) => (
              <div key={i} style={{
                padding: '8px 12px', borderRadius: 10, background: 'rgba(14,17,25,0.8)',
                borderLeft: `3px solid ${l.type === 'success' ? T.on : l.type === 'action' ? T.accent : l.type === 'ai' ? '#a78bfa' : T.muted}`,
              }}>
                <span style={{ color: T.muted, marginRight: 10 }}>{l.time}</span>
                {l.msg}
              </div>
            ))}
          </div>
        </details>

      </div>

      {/* ── Config modal ─────────────────────────────────────────────────── */}
      {showConfigModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(16px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }}>
          <div style={{
            width: '100%', maxWidth: 540, background: 'rgba(18,22,32,0.96)',
            border: `1px solid ${T.accent}30`, borderRadius: 24, padding: 32,
            backdropFilter: 'blur(40px)', boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18, color: T.accent }}>
              <Key size={24} />
              <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#fff', fontWeight: 800 }}>Configurazione Home Assistant</h2>
            </div>
            <p style={{ fontSize: '0.82rem', color: T.muted, lineHeight: 1.5, marginBottom: 22 }}>
              Inserisci URL e Long-Lived Access Token (Profilo Utente → Token a Lunga Durata → Crea token).
            </p>
            <form onSubmit={saveHaIntegration} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: '#c0c4d0', fontWeight: 700, marginBottom: 6 }}>URL Istanza</label>
                <input type="text" value={haUrl} onChange={e => setHaUrl(e.target.value)}
                  placeholder="http://192.168.1.10:8123" required
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 12, background: 'rgba(8,10,16,0.8)', border: `1px solid ${T.border}`, color: '#fff', fontSize: '0.84rem', boxSizing: 'border-box' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.76rem', color: '#c0c4d0', fontWeight: 700, marginBottom: 6 }}>Long-Lived Access Token</label>
                <textarea value={haToken} onChange={e => setHaToken(e.target.value)}
                  placeholder="eyJhbGci..." required rows={4}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: 12, background: 'rgba(8,10,16,0.8)', border: `1px solid ${T.border}`, color: '#fff', fontSize: '0.8rem', fontFamily: 'JetBrains Mono, monospace', resize: 'vertical', boxSizing: 'border-box' }} />
              </div>
              {testStatus && (
                <div style={{
                  padding: '12px 16px', borderRadius: 12, fontSize: '0.8rem', fontWeight: 600,
                  background: testStatus.ok ? 'rgba(63,185,80,0.1)' : 'rgba(255,80,100,0.1)',
                  border: `1px solid ${testStatus.ok ? 'rgba(63,185,80,0.25)' : 'rgba(255,80,100,0.25)'}`,
                  color: testStatus.ok ? T.on : '#ff5064',
                }}>{testStatus.msg}</div>
              )}
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 6 }}>
                <button type="button" onClick={testHaConnection} disabled={testLoading || !haUrl || !haToken}
                  style={{ padding: '10px 16px', borderRadius: 12, border: `1px solid ${T.borderHov}`, background: 'rgba(255,255,255,0.04)', color: T.accent, cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <FlaskConical size={14} /> {testLoading ? 'Test...' : 'Test'}
                </button>
                <button type="button" onClick={() => setShowConfigModal(false)}
                  style={{ padding: '10px 18px', borderRadius: 12, border: `1px solid ${T.border}`, background: 'rgba(255,255,255,0.03)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                  Annulla
                </button>
                <button type="submit" disabled={savingConfig}
                  style={{ padding: '10px 22px', borderRadius: 12, border: 'none', background: `linear-gradient(135deg, ${T.accent}, #3fb950)`, color: '#fff', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700 }}>
                  {savingConfig ? 'Salvo…' : 'Connetti 🔌'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}