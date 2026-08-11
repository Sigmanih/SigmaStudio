import React, { useState, useEffect } from 'react';
import { User, Volume2, VolumeX, Play, Square, Upload, RefreshCw, Check, Sparkles, Shield, ShieldCheck, Cpu, AlertTriangle } from 'lucide-react';
import { speakAgentMessage, stopSpeech } from './Chat/audioSpeech';
import HFTokenSettings from './HFTokenSettings';
import { useApp } from '../contexts/AppContext';
import TechSpaceCanvas from './common/TechSpaceCanvas';

const PRESET_AVATARS = [
  { id: 'user_default', name: 'Utente Cyber', url: '/images/default.png' },
  { id: 'user_dev', name: 'Developer', url: '/images/programmatoreAi.png' },
  { id: 'user_math', name: 'Researcher', url: '/images/matematicoAi.png' },
  { id: 'user_architect', name: 'Architect', url: '/images/agente0.png' },
];

export default function AccountTab() {
  const { theme } = useApp();
  const [tokenNotice, setTokenNotice] = useState(null);

  // --- Profile State ---
  const [profile, setProfile] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_user_profile');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { name: 'Utente', title: 'AI Developer & Researcher', avatar: '/images/default.png' };
  });

  // --- Voice Config State ---
  const [voices, setVoices] = useState([]);
  const [ttsEngines, setTtsEngines] = useState([]);
  const [ttsDefault, setTtsDefault] = useState({ engine: 'browser', voice: '' });
  const [voiceConfig, setVoiceConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_assistant_voice_config');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { engine: '', neuralVoice: '', voiceURI: '', rate: 1.05, pitch: 1.0 };
  });

  // Which neural engines the backend can actually run right now.
  useEffect(() => {
    fetch('/api/tts/engines')
      .then(r => r.json())
      .then(data => {
        setTtsEngines(data.engines || []);
        if (data.default) setTtsDefault(data.default);
      })
      .catch(() => setTtsEngines([]));
  }, []);

  const activeEngineId = voiceConfig.engine || ttsDefault.engine || 'browser';
  const activeEngine = ttsEngines.find(e => e.id === activeEngineId);

  const [isPlayingTest, setIsPlayingTest] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Load available Voices from SpeechSynthesis
  useEffect(() => {
    const updateVoices = () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        const available = window.speechSynthesis.getVoices();
        setVoices(available);
        if (!voiceConfig.voiceURI && available.length > 0) {
          // Prefer the neural system voices (Windows/macOS ship them as
          // "Natural"/"Online"): the legacy ones sound noticeably robotic.
          const italian = available.filter(v => v.lang.startsWith('it') || v.lang.includes('IT'));
          const pool = italian.length > 0 ? italian : available;
          const best = pool.find(v => /natural|neural|online|premium|enhanced/i.test(v.name || '')) || pool[0];
          setVoiceConfig(prev => ({ ...prev, voiceURI: best.voiceURI }));
        }
      }
    };

    updateVoices();
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
  }, []);

  // Helper to update profile and auto-save + notify app in real-time
  const updateProfile = (updater) => {
    setProfile(prev => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      try {
        const serialized = JSON.stringify(updated);
        // Safety check before writing to localStorage
        const estimatedSizeKB = (serialized.length * 2) / 1024; // UTF-16 ~2 bytes per char
        if (estimatedSizeKB > 4000) {
          console.warn(`Profile size ~${Math.round(estimatedSizeKB)}KB, approaching localStorage limit`);
        }
        localStorage.setItem('sigma_user_profile', serialized);
        window.dispatchEvent(new CustomEvent('sigma_profile_updated', { detail: updated }));
      } catch (e) {
        console.error("Error updating profile:", e);
        window.dispatchEvent(new CustomEvent('sigma_toast', {
          detail: { message: '❌ Errore nel salvataggio del profilo: quota localStorage esaurita. Riprova con un\'immagine più piccola.', type: 'error' }
        }));
      }
      return updated;
    });
  };

  // Helper to update voice config and auto-save in real-time
  const updateVoiceConfig = (updater) => {
    setVoiceConfig(prev => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      try {
        localStorage.setItem('sigma_assistant_voice_config', JSON.stringify(updated));
      } catch (e) {
        console.error("Error updating voice config:", e);
      }
      return updated;
    });
  };

  // Save profile and voice preferences to localStorage
  const handleSave = () => {
    try {
      const profileSerialized = JSON.stringify(profile);
      // Pre-check size before saving
      const estimatedSizeKB = (profileSerialized.length * 2) / 1024;
      if (estimatedSizeKB > 4000) {
        throw new Error(`Profilo troppo grande (${Math.round(estimatedSizeKB)}KB). Riduci l'immagine del profilo.`);
      }
      localStorage.setItem('sigma_user_profile', profileSerialized);
      localStorage.setItem('sigma_assistant_voice_config', JSON.stringify(voiceConfig));
      
      // Dispatch event to notify Chat and other components of updated profile
      window.dispatchEvent(new CustomEvent('sigma_profile_updated', { detail: profile }));
      
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);

      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: '✅ Profilo ed impostazioni voce salvati con successo!', type: 'success' }
      }));
    } catch (e) {
      console.error("Error saving profile:", e);
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: `❌ ${e.message || 'Errore nel salvataggio del profilo.'}`, type: 'error' }
      }));
    }
  };

  // Compress image to fit within localStorage limits while keeping good quality
  const compressImage = (dataUrl, maxSize = 256, quality = 0.6) => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let { width, height } = img;

        // Scale down if exceeding maxSize in either dimension
        if (width > maxSize || height > maxSize) {
          const ratio = Math.min(maxSize / width, maxSize / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        
        // Fill with dark background in case of transparent PNG/GIF
        ctx.fillStyle = '#11131b';
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);
        
        // Export as JPEG (smaller than PNG, no alpha channel needed for avatars)
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = () => reject(new Error('Failed to load image for compression'));
      img.src = dataUrl;
    });
  };

  // Image / GIF Upload Handler via Backend API (supports ANY file size, including animated GIFs)
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/upload_user_avatar', {
        method: 'POST',
        body: formData
      });

      // Compress the image to a thumbnail
      const compressed = await compressImage(dataUrl, 256, 0.6);

      // Check compressed size: warn if still large (shouldn't happen, but safety)
      const sizeKB = Math.round((compressed.length * 3) / 4 / 1024);
      if (sizeKB > 500) {
        window.dispatchEvent(new CustomEvent('sigma_toast', {
          detail: { message: `⚠️ Immagine compressa a ${sizeKB}KB, ma potrebbe occupare molto spazio.`, type: 'warning' }
        }));
      }

      updateProfile(prev => ({ ...prev, avatar: compressed }));
    } catch (err) {
      console.error("Error uploading/compressing photo:", err);
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: '❌ Errore durante il caricamento dell\'immagine. Riprova con un file più piccolo.', type: 'error' }
      }));
    }
  };

  // Test Speech Voice
  const handleTestVoice = () => {
    if (isPlayingTest) {
      stopSpeech();
      setIsPlayingTest(false);
      return;
    }

    const testPhrase = "Ciao! Sono il tuo assistente AI di Sigma Studio. Ho configurato la mia voce secondo le tue preferenze. Come posso aiutarti oggi?";
    
    // Save transient config for immediate test
    try {
      localStorage.setItem('sigma_assistant_voice_config', JSON.stringify(voiceConfig));
    } catch (e) {}

    const started = speakAgentMessage(
      testPhrase,
      () => setIsPlayingTest(true),
      () => setIsPlayingTest(false)
    );
    if (!started) setIsPlayingTest(false);
  };

  const italianVoices = voices.filter(v => v.lang.startsWith('it') || v.lang.includes('IT'));
  const otherVoices = voices.filter(v => !v.lang.startsWith('it') && !v.lang.includes('IT'));

  const isLight = theme === 'light';

  return (
    <div 
      className="account-tab-root"
      style={{
        position: 'relative',
        padding: 0,
        margin: 0,
        width: '100%',
        height: '100%',
        background: isLight ? '#f7f4ed' : '#080a10',
        color: isLight ? '#111111' : '#e2e4eb',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'Inter, system-ui, sans-serif',
        boxSizing: 'border-box',
        overflowY: 'auto'
      }}
    >
      <TechSpaceCanvas isLight={theme === 'light'} />
      {/* Hero Visual Banner matching Domotica Header Style */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '20px 32px 18px 32px',
        minHeight: '100px',
        borderBottom: '1px solid rgba(234, 88, 12, 0.3)',
        boxShadow: 'none',
        backgroundImage: 'linear-gradient(to right, rgba(28, 12, 4, 0.96) 35%, rgba(120, 45, 10, 0.6) 75%, rgba(234, 88, 12, 0.22) 100%), url("/images/account_voice_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        width: '100%',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <User size={14} /> ACCOUNT & SYNTHESIS CONTROL HUB
            </div>
            <h1 style={{ margin: '0 0 4px 0', fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              👤 Account & Voce Neurale AI
            </h1>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#a0aec0', lineHeight: 1.4 }}>
              Personalizza il tuo avatar, direttive di sistema ed i parametri della voce neurale per gli Agenti dello Swarm.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={handleSave}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 20px',
                borderRadius: '12px',
                fontSize: '0.82rem',
                fontWeight: 800,
                background: savedSuccess ? 'rgba(63, 185, 80, 0.2)' : 'linear-gradient(135deg, #00d2ff, #0072ff)',
                border: savedSuccess ? '1px solid rgba(63, 185, 80, 0.5)' : 'none',
                color: savedSuccess ? '#3fb950' : '#fff',
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(0, 210, 255, 0.25)',
                transition: 'all 0.2s ease'
              }}
            >
              {savedSuccess ? <Check size={16} /> : <Sparkles size={16} />}
              <span>{savedSuccess ? 'Impostazioni Salvate!' : 'Salva Profilo & Voce'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Inner Content Body Padding Container */}
      <div style={{ padding: '0 24px 32px 24px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Griglia a 2 Colonne */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', flex: 1, minHeight: 0, alignItems: 'stretch' }}>
        
        {/* COLONNA SINISTRA — PROFILO UTENTE */}
        <div 
          className="account-card primi-passi-card"
          style={{
            backgroundColor: isLight ? '#fffdf9' : '#0e1017',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
            borderRadius: '14px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
            <User size={18} style={{ color: '#00d2ff' }} />
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f0f2f8' }}>Profilo Utente & Avatar</h3>
          </div>

          {/* Foto Profilo Preview & Upload */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ position: 'relative' }}>
              <img 
                src={profile.avatar || '/images/default.png'} 
                alt="Foto Profilo" 
                style={{
                  width: '68px',
                  height: '68px',
                  borderRadius: '50%',
                  objectFit: 'cover',
                  border: '2px solid #00d2ff',
                  boxShadow: '0 0 16px rgba(0, 210, 255, 0.25)',
                  background: '#1a1d2d'
                }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#e2e4eb' }}>Foto Profilo Chat</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <label 
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '5px 12px',
                    borderRadius: '8px',
                    background: 'rgba(0, 210, 255, 0.1)',
                    border: '1px solid rgba(0, 210, 255, 0.25)',
                    color: '#00d2ff',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  <Upload size={13} />
                  <span>Carica Foto</span>
                  <input type="file" accept="image/*" onChange={handlePhotoUpload} style={{ display: 'none' }} />
                </label>
                <button
                  onClick={() => updateProfile(prev => ({ ...prev, avatar: '/images/default.png' }))}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '8px',
                    background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: '#8b8fa3',
                    fontSize: '0.72rem',
                    cursor: 'pointer'
                  }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>

          {/* Preset Avatars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#8b8fa3', fontWeight: 600 }}>Oppure scegli un avatar preset:</span>
            <div style={{ display: 'flex', gap: '10px' }}>
              {PRESET_AVATARS.map(av => (
                <div
                  key={av.id}
                  onClick={() => updateProfile(prev => ({ ...prev, avatar: av.url }))}
                  style={{
                    cursor: 'pointer',
                    padding: '3px',
                    borderRadius: '50%',
                    border: profile.avatar === av.url ? '2px solid #00d2ff' : '2px solid transparent',
                    transition: 'all 0.15s'
                  }}
                  title={av.name}
                >
                  <img src={av.url} alt={av.name} style={{ width: '38px', height: '38px', borderRadius: '50%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          </div>

          {/* Input Nome Utente */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Nome Utente (mostrato in chat):</label>
            <input
              type="text"
              value={profile.name}
              onChange={e => updateProfile(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Inserisci il tuo nome..."
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '8px',
                background: '#0e1016',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#f0f2f8',
                fontSize: '0.8rem',
                outline: 'none'
              }}
            />
          </div>

          {/* Input Ruolo Utente */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Ruolo / Titolo:</label>
            <input
              type="text"
              value={profile.title}
              onChange={e => updateProfile(prev => ({ ...prev, title: e.target.value }))}
              placeholder="es. AI Architect & Developer..."
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '8px',
                background: '#0e1016',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#f0f2f8',
                fontSize: '0.8rem',
                outline: 'none'
              }}
            />
          </div>
        </div>

        {/* COLONNA DESTRA — VOCE ASSISTENTE AI & HUGGINGFACE TOKEN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
          
          {/* SEZIONE 2 — VOCE ASSISTENTE AI */}
          <div 
            className="account-card primi-passi-card"
            style={{
              backgroundColor: isLight ? '#fffdf9' : '#0e1017',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(188, 140, 255, 0.25)',
              borderRadius: '14px',
              padding: '18px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Volume2 size={18} style={{ color: '#bc8cff' }} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f0f2f8' }}>Voce Assistente AI (TTS)</h3>
              </div>

              {/* Test Voice Button */}
              <button
                onClick={handleTestVoice}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '5px 12px',
                  borderRadius: '7px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  background: isPlayingTest ? 'rgba(255, 85, 85, 0.15)' : 'rgba(188, 140, 255, 0.15)',
                  border: isPlayingTest ? '1px solid rgba(255, 85, 85, 0.4)' : '1px solid rgba(188, 140, 255, 0.3)',
                  color: isPlayingTest ? '#ff5555' : '#bc8cff',
                  cursor: 'pointer',
                  transition: 'all 0.15s'
                }}
              >
                {isPlayingTest ? <Square size={12} /> : <Play size={12} />}
                <span>{isPlayingTest ? 'Ferma Test' : '🔊 Test Voce'}</span>
              </button>
            </div>

            {/* Engine Selector */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Motore Vocale:</label>
              <select
                value={voiceConfig.engine || ''}
                onChange={e => updateVoiceConfig(prev => ({ ...prev, engine: e.target.value, neuralVoice: '' }))}
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: '8px',
                  background: '#0e1016', border: '1px solid rgba(255,255,255,0.08)',
                  color: '#f0f2f8', fontSize: '0.78rem', outline: 'none', cursor: 'pointer'
                }}
              >
                <option value="">
                  Automatico (consigliato: {ttsDefault.engine === 'browser' ? 'voce di sistema' : ttsDefault.engine})
                </option>
                {ttsEngines.map(engine => (
                  <option key={engine.id} value={engine.id} disabled={!engine.installed}>
                    {engine.name}{engine.installed ? '' : ' — non installato'}
                  </option>
                ))}
              </select>
              {activeEngine && activeEngine.id !== 'browser' && (
                <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                  <div>{activeEngine.description}</div>
                  <div style={{ color: activeEngine.installed ? '#8b8fa3' : '#ffb454' }}>
                    Licenza: {activeEngine.license}
                  </div>
                  {!activeEngine.installed && activeEngine.install_hint && (
                    <div style={{ marginTop: '4px', color: '#ffb454' }}>
                      Per attivarlo: <code style={{ color: '#bc8cff' }}>{activeEngine.install_hint}</code>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Neural Voice Dropdown */}
            {activeEngine && activeEngine.id !== 'browser' && activeEngine.voices?.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Voce Neurale:</label>
                <select
                  value={voiceConfig.neuralVoice || activeEngine.default_voice}
                  onChange={e => updateVoiceConfig(prev => ({ ...prev, neuralVoice: e.target.value }))}
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: '8px',
                    background: '#0e1016', border: '1px solid rgba(255,255,255,0.08)',
                    color: '#f0f2f8', fontSize: '0.78rem', outline: 'none', cursor: 'pointer'
                  }}
                >
                  {activeEngine.voices.map(v => (
                    <option key={v.id} value={v.id}>
                      {v.gender === 'male' ? '♂' : '♀'} {v.name} ({v.lang})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Voice Dropdown */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Seleziona Voce Sospesa:</label>
              <select
                value={voiceConfig.voiceURI}
                onChange={e => updateVoiceConfig(prev => ({ ...prev, voiceURI: e.target.value }))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  background: '#0e1016',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: '#f0f2f8',
                  fontSize: '0.78rem',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                {italianVoices.length > 0 && (
                  <optgroup label="🇮🇹 Voci Italiane Raccomandate">
                    {italianVoices.map(v => (
                      <option key={v.voiceURI} value={v.voiceURI}>
                        🇮🇹 {v.name} ({v.lang})
                      </option>
                    ))}
                  </optgroup>
                )}
                {otherVoices.length > 0 && (
                  <optgroup label="🌐 Altre Voci del Sistema">
                    {otherVoices.map(v => (
                      <option key={v.voiceURI} value={v.voiceURI}>
                        🌐 {v.name} ({v.lang})
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>

            {/* Slider Velocità (Rate) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem' }}>
                <span style={{ fontWeight: 600, color: '#8b8fa3' }}>Velocità di Lettura (Speed):</span>
                <span style={{ color: '#bc8cff', fontWeight: 700 }}>{voiceConfig.rate}x</span>
              </div>
              <input
                type="range"
                min="0.7"
                max="1.6"
                step="0.05"
                value={voiceConfig.rate}
                onChange={e => updateVoiceConfig(prev => ({ ...prev, rate: parseFloat(e.target.value) }))}
                style={{ accentColor: '#bc8cff', cursor: 'pointer', height: '4px' }}
              />
            </div>

            {/* Slider Tono (Pitch) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem' }}>
                <span style={{ fontWeight: 600, color: '#8b8fa3' }}>Tono della Voce (Pitch):</span>
                <span style={{ color: '#00d2ff', fontWeight: 700 }}>{voiceConfig.pitch}</span>
              </div>
              <input
                type="range"
                min="0.6"
                max="1.4"
                step="0.05"
                value={voiceConfig.pitch}
                onChange={e => updateVoiceConfig(prev => ({ ...prev, pitch: parseFloat(e.target.value) }))}
                style={{ accentColor: '#00d2ff', cursor: 'pointer', height: '4px' }}
              />
            </div>

            {/* Visual Waveform Effect when testing */}
            {isPlayingTest && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', padding: '6px 0' }}>
                <span style={{ fontSize: '0.72rem', color: '#bc8cff', fontWeight: 600, marginRight: '6px' }}>Riproduzione in corso:</span>
                <div style={{ display: 'flex', gap: '3px', alignItems: 'center', height: '16px' }}>
                  <span className="wave-bar" style={{ width: '3px', height: '100%', background: '#bc8cff', borderRadius: '2px', animation: 'wave 0.8s infinite ease-in-out' }} />
                  <span className="wave-bar" style={{ width: '3px', height: '60%', background: '#00d2ff', borderRadius: '2px', animation: 'wave 0.6s infinite ease-in-out 0.1s' }} />
                  <span className="wave-bar" style={{ width: '3px', height: '80%', background: '#bc8cff', borderRadius: '2px', animation: 'wave 1.0s infinite ease-in-out 0.2s' }} />
                  <span className="wave-bar" style={{ width: '3px', height: '40%', background: '#00d2ff', borderRadius: '2px', animation: 'wave 0.5s infinite ease-in-out 0.3s' }} />
                </div>
                <style>{`
                  @keyframes wave {
                    0%, 100% { transform: scaleY(0.3); }
                    50% { transform: scaleY(1); }
                  }
                `}</style>
              </div>
            )}
          </div>

          {/* SEZIONE 3 — CREDENZIALI ESTERNE */}
          <div
            style={{
              backgroundColor: isLight ? '#fffdf9' : '#0e1017',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(99, 102, 241, 0.2)',
              borderRadius: '14px',
              padding: '18px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
              <ShieldCheck size={18} style={{ color: '#6366f1' }} />
              <div>
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f0f2f8' }}>
                  HuggingFace Token
                </h3>
                <div style={{ fontSize: '0.7rem', color: '#8b8fa3', marginTop: '1px' }}>
                  Download modelli, dataset e training su tutta l'app
                </div>
              </div>
            </div>
            <HFTokenSettings addToast={(message, type) => setTokenNotice({ message, type })} />
            {tokenNotice && (
              <div style={{
                fontSize: '0.72rem', padding: '6px 10px', borderRadius: '6px',
                color: tokenNotice.type === 'error' ? '#ff5555' : '#3fb950',
                background: tokenNotice.type === 'error' ? 'rgba(255,85,85,0.08)' : 'rgba(63,185,80,0.08)',
              }}>
                {tokenNotice.message}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
);
}
