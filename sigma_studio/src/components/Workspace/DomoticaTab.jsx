import React, { useState } from 'react';
import { 
  Home, Sun, Moon, Thermometer, Shield, Power, 
  Lightbulb, Lock, Cpu, RefreshCw, Send, Zap, Sliders, Palette, Plus, Minus
} from 'lucide-react';

const COLOR_PRESETS = [
  { name: 'Ciano Cyber', hex: '#00d2ff' },
  { name: 'Bianco Caldo', hex: '#ffb86c' },
  { name: 'Viola Neon', hex: '#a78bfa' },
  { name: 'Smeraldo', hex: '#3fb950' },
  { name: 'Rosso Allarme', hex: '#ff5064' },
];

export default function DomoticaTab() {
  const [devices, setDevices] = useState([
    { id: 'light_lab', name: 'Luci Sigma Studio', type: 'light', state: 'on', brightness: 85, color: '#00d2ff', room: 'Laboratorio' },
    { id: 'light_main', name: 'Luce Principale', type: 'light', state: 'on', brightness: 100, color: '#ffb86c', room: 'Laboratorio' },
    { id: 'temp_sensor', name: 'Sensore Temperatura', type: 'sensor', val: '21.5 °C', humidity: '48%', room: 'Laboratorio' },
    { id: 'ac_unit', name: 'Climatizzatore AI', type: 'climate', state: 'auto', setpoint: 21, room: 'Laboratorio' },
    { id: 'lock_front', name: 'Serratura Principale', type: 'lock', state: 'locked', room: 'Ingresso' },
    { id: 'cam_studio', name: 'Telecamera Studio', type: 'camera', state: 'active', room: 'Laboratorio' },
    { id: 'plug_gpu', name: 'Presa Smart GPU Cluster', type: 'plug', state: 'on', power: '420W', room: 'Server Room' },
    { id: 'switch_audio', name: 'Impianto Audio', type: 'switch', state: 'off', room: 'Laboratorio' },
  ]);

  const [expandedControl, setExpandedControl] = useState(null); // id of expanded device
  const [prompt, setPrompt] = useState('');
  const [logs, setLogs] = useState([
    { time: '17:35:10', msg: 'Home Assistant MCP Server connesso [WS ok]', type: 'info' },
    { time: '17:36:02', msg: 'Presa Smart GPU Cluster: Misurazione 420W attiva', type: 'success' },
    { time: '17:37:15', msg: 'Scena "Modalità Studio Focus" sincronizzata', type: 'success' },
  ]);
  const [loading, setLoading] = useState(false);

  const addLog = (msg, type = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [{ time, msg, type }, ...prev]);
  };

  const toggleDevice = (id) => {
    setDevices(prev => prev.map(d => {
      if (d.id === id) {
        const nextState = d.state === 'on' ? 'off' : (d.state === 'off' ? 'on' : (d.state === 'locked' ? 'unlocked' : 'locked'));
        addLog(`Dispositivo ${d.name} commutato a ${nextState.toUpperCase()}`, 'action');
        return { ...d, state: nextState };
      }
      return d;
    }));
  };

  const updateBrightness = (id, newBrightness) => {
    setDevices(prev => prev.map(d => {
      if (d.id === id) {
        return { ...d, brightness: newBrightness, state: newBrightness > 0 ? 'on' : 'off' };
      }
      return d;
    }));
  };

  const updateColor = (id, newColor) => {
    setDevices(prev => prev.map(d => {
      if (d.id === id) {
        return { ...d, color: newColor };
      }
      return d;
    }));
    const dev = devices.find(d => d.id === id);
    if (dev) {
      addLog(`Colore di ${dev.name} impostato a ${newColor}`, 'action');
    }
  };

  const updateSetpoint = (id, delta) => {
    setDevices(prev => prev.map(d => {
      if (d.id === id && d.type === 'climate') {
        const nextVal = Math.max(16, Math.min(30, (d.setpoint || 21) + delta));
        addLog(`Temperatura target ${d.name} impostata a ${nextVal}°C`, 'action');
        return { ...d, setpoint: nextVal };
      }
      return d;
    }));
  };

  const handleAiCommand = (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    const cmd = prompt;
    setPrompt('');
    
    addLog(`Comando AI Domotico inviato: "${cmd}"`, 'ai');

    setTimeout(() => {
      setLoading(false);
      const lower = cmd.toLowerCase();
      if (lower.includes('spegni') || lower.includes('off')) {
        setDevices(prev => prev.map(d => d.type === 'light' ? { ...d, state: 'off' } : d));
        addLog('AI Home Assistant: Tutte le luci del laboratorio spente.', 'success');
      } else if (lower.includes('accendi') || lower.includes('on')) {
        setDevices(prev => prev.map(d => d.type === 'light' ? { ...d, state: 'on' } : d));
        addLog('AI Home Assistant: Tutte le luci accese al 100%.', 'success');
      } else if (lower.includes('ross') || lower.includes('allarme')) {
        setDevices(prev => prev.map(d => d.type === 'light' ? { ...d, color: '#ff5064' } : d));
        addLog('AI Home Assistant: Colore ambiente impostato su Rosso Allarme.', 'success');
      } else if (lower.includes('21') || lower.includes('clima')) {
        setDevices(prev => prev.map(d => d.type === 'climate' ? { ...d, setpoint: 21 } : d));
        addLog('AI Home Assistant: Climatizzatore impostato a 21°C.', 'success');
      } else {
        addLog(`AI Home Assistant: Eseguito comando "${cmd}" via MCP Home Assistant Bus.`, 'success');
      }
    }, 800);
  };

  const runScene = (sceneName) => {
    addLog(`Attivata scena domotica "${sceneName}"`, 'action');
    if (sceneName === 'Notte / Standby') {
      setDevices(prev => prev.map(d => d.type === 'light' ? { ...d, state: 'off' } : (d.type === 'lock' ? { ...d, state: 'locked' } : d)));
    } else if (sceneName === 'Focus Ricerca') {
      setDevices(prev => prev.map(d => d.type === 'light' ? { ...d, state: 'on', brightness: 90, color: '#00d2ff' } : d));
    } else if (sceneName === 'Sicurezza Studio') {
      setDevices(prev => prev.map(d => d.type === 'camera' ? { ...d, state: 'active' } : (d.type === 'lock' ? { ...d, state: 'locked' } : d)));
    }
  };

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: '#0a0c10',
      color: '#e2e8f0',
      fontFamily: 'Inter, system-ui, sans-serif',
      overflowY: 'auto'
    }}>
      {/* Header */}
      <div style={{
        padding: '24px 32px 16px 32px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        background: 'rgba(14, 16, 22, 0.85)',
        backdropFilter: 'blur(16px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(124, 91, 240, 0.2))',
            border: '1px solid rgba(0, 210, 255, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#00d2ff'
          }}>
            <Home size={24} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              Home Assistant & Controllo Domotico
            </h1>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#8b8fa3' }}>
              Regolazione Intensità Luci, Palette Colori RGB & Climatizzazione — MCP Home Assistant Bus
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            padding: '6px 14px',
            borderRadius: '20px',
            background: 'rgba(63, 185, 80, 0.12)',
            border: '1px solid rgba(63, 185, 80, 0.3)',
            color: '#3fb950',
            fontSize: '0.76rem',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3fb950', boxShadow: '0 0 8px #3fb950' }} />
            MCP Home Assistant Connesso
          </div>
          <button
            onClick={() => addLog('Sincronizzazione manuale Home Assistant completata', 'info')}
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#c0c4d0',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <RefreshCw size={14} /> Sincronizza
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ padding: '32px', flex: 1, maxWidth: '1400px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
        
        {/* Quick Scene Selectors */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '32px' }}>
          <div 
            onClick={() => runScene('Focus Ricerca')}
            style={{
              padding: '18px 20px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.12), rgba(18, 20, 28, 0.9))',
              border: '1px solid rgba(0, 210, 255, 0.25)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <Sun size={20} color="#00d2ff" />
              <span style={{ fontSize: '0.7rem', color: '#00d2ff', fontWeight: 700, background: 'rgba(0, 210, 255, 0.15)', padding: '2px 8px', borderRadius: '10px' }}>ATTIVA</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>Focus Ricerca</div>
            <div style={{ fontSize: '0.76rem', color: '#8b8fa3', marginTop: '4px' }}>Luci laboratorio 90%, Clima 21°C</div>
          </div>

          <div 
            onClick={() => runScene('Notte / Standby')}
            style={{
              padding: '18px 20px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(167, 139, 250, 0.12), rgba(18, 20, 28, 0.9))',
              border: '1px solid rgba(167, 139, 250, 0.25)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <Moon size={20} color="#a78bfa" />
              <span style={{ fontSize: '0.7rem', color: '#a78bfa', fontWeight: 700, background: 'rgba(167, 139, 250, 0.15)', padding: '2px 8px', borderRadius: '10px' }}>SCENA</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>Notte / Standby</div>
            <div style={{ fontSize: '0.76rem', color: '#8b8fa3', marginTop: '4px' }}>Spegni luci, serrature bloccate</div>
          </div>

          <div 
            onClick={() => runScene('Sicurezza Studio')}
            style={{
              padding: '18px 20px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(255, 80, 100, 0.12), rgba(18, 20, 28, 0.9))',
              border: '1px solid rgba(255, 80, 100, 0.25)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <Shield size={20} color="#ff5064" />
              <span style={{ fontSize: '0.7rem', color: '#ff5064', fontWeight: 700, background: 'rgba(255, 80, 100, 0.15)', padding: '2px 8px', borderRadius: '10px' }}>PROTEZIONE</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>Sicurezza Studio</div>
            <div style={{ fontSize: '0.76rem', color: '#8b8fa3', marginTop: '4px' }}>Telecamere attive, sensori di movimento</div>
          </div>
        </div>

        {/* AI Voice/Text Domotica Assistant Bar */}
        <div style={{
          padding: '20px',
          borderRadius: '16px',
          background: 'rgba(18, 20, 28, 0.85)',
          border: '1px solid rgba(0, 210, 255, 0.2)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          marginBottom: '32px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.86rem', fontWeight: 700, color: '#00d2ff' }}>
            <Zap size={16} /> Assistente AI Domotico — MCP Home Assistant Command Bus
          </div>
          <form onSubmit={handleAiCommand} style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="es. Spegni tutte le luci del laboratorio e imposta il climatizzatore a 21°C..."
              style={{
                flex: 1,
                padding: '12px 18px',
                borderRadius: '12px',
                background: 'rgba(10, 12, 16, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#fff',
                fontSize: '0.88rem',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '12px 24px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)',
                border: 'none',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              {loading ? <RefreshCw className="spin" size={16} /> : <Send size={16} />} Invio Comando
            </button>
          </form>
        </div>

        {/* Devices Grid & Activity Logs */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '28px' }}>
          {/* Smart Devices List with Intensita & Colore Controls */}
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>💡</span> Dispositivi Smart Domotici & Regolazione Avanzata ({devices.length})
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {devices.map(dev => {
                const isLight = dev.type === 'light';
                const isClimate = dev.type === 'climate';
                const isActive = dev.state === 'on' || dev.state === 'active' || dev.state === 'auto';
                const glowColor = isLight && isActive ? (dev.color || '#00d2ff') : (isActive ? '#00d2ff' : '#6b7080');

                return (
                  <div
                    key={dev.id}
                    style={{
                      padding: '18px 20px',
                      borderRadius: '16px',
                      background: 'rgba(18, 20, 28, 0.85)',
                      border: '1px solid ' + (isActive ? 'rgba(0, 210, 255, 0.25)' : 'rgba(255, 255, 255, 0.08)'),
                      boxShadow: isActive ? `0 4px 20px ${glowColor}15` : 'none',
                      transition: 'all 0.25s ease'
                    }}
                  >
                    {/* Top Row: Device Icon, Info & Primary Toggle Button */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                        <div style={{
                          width: '42px',
                          height: '42px',
                          borderRadius: '12px',
                          background: isActive ? `${glowColor}25` : 'rgba(255, 255, 255, 0.04)',
                          border: '1px solid ' + (isActive ? glowColor : 'transparent'),
                          color: glowColor,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          boxShadow: isActive ? `0 0 12px ${glowColor}40` : 'none'
                        }}>
                          {dev.type === 'light' && <Lightbulb size={22} />}
                          {dev.type === 'sensor' && <Thermometer size={22} />}
                          {dev.type === 'climate' && <Sun size={22} />}
                          {dev.type === 'lock' && <Lock size={22} />}
                          {dev.type === 'plug' && <Cpu size={22} />}
                          {dev.type === 'camera' && <Shield size={22} />}
                          {dev.type === 'switch' && <Power size={22} />}
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#fff' }}>{dev.name}</div>
                          <div style={{ fontSize: '0.76rem', color: '#8b8fa3', marginTop: '2px' }}>
                            {dev.room} • {dev.val || dev.power || (isClimate ? `Target: ${dev.setpoint}°C` : `Stato: ${(dev.state || 'OFF').toUpperCase()}`)}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {isLight && (
                          <button
                            onClick={() => setExpandedControl(expandedControl === dev.id ? null : dev.id)}
                            style={{
                              padding: '6px 10px',
                              borderRadius: '10px',
                              background: expandedControl === dev.id ? 'rgba(0, 210, 255, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                              border: '1px solid rgba(255, 255, 255, 0.1)',
                              color: '#e2e8f0',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                          >
                            <Sliders size={14} /> Regola
                          </button>
                        )}

                        <button
                          onClick={() => toggleDevice(dev.id)}
                          style={{
                            padding: '6px 16px',
                            borderRadius: '20px',
                            border: '1px solid ' + (isActive ? `${glowColor}60` : 'rgba(255, 255, 255, 0.1)'),
                            background: isActive ? `${glowColor}20` : 'rgba(255, 255, 255, 0.05)',
                            color: isActive ? glowColor : '#8b8fa3',
                            fontSize: '0.76rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          {(dev.state || 'OFF').toUpperCase()}
                        </button>
                      </div>
                    </div>

                    {/* Expandable Light Control Panel: Intensità & Palette Colori */}
                    {isLight && (expandedControl === dev.id || isActive) && (
                      <div style={{
                        marginTop: '16px',
                        paddingTop: '16px',
                        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px'
                      }}>
                        {/* Intensità Slider */}
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600, marginBottom: '6px' }}>
                            <span>Intensità Luminosa:</span>
                            <span style={{ color: glowColor, fontWeight: 800 }}>{dev.brightness || 0}%</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={dev.brightness || 0}
                            onChange={(e) => updateBrightness(dev.id, parseInt(e.target.value, 10))}
                            style={{
                              width: '100%',
                              accentColor: glowColor,
                              cursor: 'pointer'
                            }}
                          />
                        </div>

                        {/* Palette Colore RGB & Presets */}
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', color: '#c0c4d0', fontWeight: 600, marginBottom: '8px' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                              <Palette size={13} /> Colore Ambiente:
                            </span>
                            <input
                              type="color"
                              value={dev.color || '#00d2ff'}
                              onChange={(e) => updateColor(dev.id, e.target.value)}
                              style={{
                                width: '28px',
                                height: '24px',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                background: 'none'
                              }}
                              title="Scegli Colore Personalizzato"
                            />
                          </div>

                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            {COLOR_PRESETS.map(preset => (
                              <button
                                key={preset.hex}
                                onClick={() => updateColor(dev.id, preset.hex)}
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: '12px',
                                  background: dev.color === preset.hex ? `${preset.hex}30` : 'rgba(255,255,255,0.04)',
                                  border: `1px solid ${dev.color === preset.hex ? preset.hex : 'rgba(255,255,255,0.1)'}`,
                                  color: dev.color === preset.hex ? '#fff' : '#8b8fa3',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '6px'
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

                    {/* Climate Controls for AC Unit */}
                    {isClimate && (
                      <div style={{
                        marginTop: '14px',
                        paddingTop: '14px',
                        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                      }}>
                        <span style={{ fontSize: '0.76rem', color: '#8b8fa3', fontWeight: 600 }}>Temperatura Desiderata:</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <button
                            onClick={() => updateSetpoint(dev.id, -1)}
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '8px',
                              background: 'rgba(0, 210, 255, 0.15)',
                              border: '1px solid rgba(0, 210, 255, 0.3)',
                              color: '#00d2ff',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              cursor: 'pointer'
                            }}
                          >
                            <Minus size={14} />
                          </button>
                          <span style={{ fontWeight: 800, fontSize: '0.95rem', color: '#fff' }}>{dev.setpoint || 21}°C</span>
                          <button
                            onClick={() => updateSetpoint(dev.id, 1)}
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '8px',
                              background: 'rgba(255, 80, 100, 0.15)',
                              border: '1px solid rgba(255, 80, 100, 0.3)',
                              color: '#ff5064',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              cursor: 'pointer'
                            }}
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
          </div>

          {/* MCP Home Assistant Event Logs */}
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: '0 0 16px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📜</span> Log Eventi MCP Home Assistant
            </h2>
            <div style={{
              padding: '18px',
              borderRadius: '16px',
              background: 'rgba(10, 12, 16, 0.9)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              maxHeight: '560px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              {logs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '10px 14px',
                    borderRadius: '10px',
                    background: 'rgba(18, 20, 28, 0.7)',
                    borderLeft: `3px solid ${log.type === 'success' ? '#3fb950' : (log.type === 'action' ? '#00d2ff' : (log.type === 'ai' ? '#a78bfa' : '#6b7080'))}`,
                    fontSize: '0.78rem'
                  }}
                >
                  <div style={{ color: '#6b7080', fontSize: '0.7rem', marginBottom: '2px' }}>{log.time}</div>
                  <div style={{ color: '#e2e8f0', fontWeight: 500 }}>{log.msg}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
