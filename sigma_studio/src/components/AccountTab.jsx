import React, { useState, useEffect } from 'react';
import { User, Volume2, VolumeX, Play, Square, Upload, RefreshCw, Check, Sparkles, Shield, ShieldCheck, Cpu, AlertTriangle } from 'lucide-react';
import { speakAgentMessage, stopSpeech } from './Chat/audioSpeech';
import HFTokenSettings from './HFTokenSettings';

const PRESET_AVATARS = [
  { id: 'user_default', name: 'Utente Cyber', url: '/images/default.png' },
  { id: 'user_dev', name: 'Developer', url: '/images/programmatoreAi.png' },
  { id: 'user_math', name: 'Researcher', url: '/images/matematicoAi.png' },
  { id: 'user_architect', name: 'Architect', url: '/images/agente0.png' },
];

export default function AccountTab() {
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
  const [voiceConfig, setVoiceConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_assistant_voice_config');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { voiceURI: '', rate: 1.05, pitch: 1.0 };
  });

  const [isPlayingTest, setIsPlayingTest] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Load available Voices from SpeechSynthesis
  useEffect(() => {
    const updateVoices = () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        const available = window.speechSynthesis.getVoices();
        setVoices(available);
        if (!voiceConfig.voiceURI && available.length > 0) {
          const defaultIt = available.find(v => v.lang.startsWith('it') || v.lang.includes('IT')) || available[0];
          setVoiceConfig(prev => ({ ...prev, voiceURI: defaultIt.voiceURI }));
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

  return (
    <div 
      className="account-tab-root"
      style={{
        padding: '24px',
        maxWidth: '960px',
        margin: '0 auto',
        color: '#e2e4eb',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        fontFamily: 'Inter, system-ui, sans-serif'
      }}
    >
      {/* Header Banner */}
      <div 
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '20px 24px',
          background: 'linear-gradient(135deg, rgba(17, 19, 27, 0.95), rgba(24, 27, 40, 0.85))',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div 
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.12)',
              border: '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#00d2ff'
            }}
          >
            <User size={28} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#f0f2f8' }}>
              👤 Account & Voce Assistente
            </h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#8b8fa3' }}>
              Gestisci il tuo profilo utente, la foto per la chat e personalizza la voce sintetizzata dell'assistente AI.
            </p>
          </div>
        </div>

        <button
          onClick={handleSave}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            borderRadius: '10px',
            fontSize: '0.82rem',
            fontWeight: 700,
            background: savedSuccess ? 'rgba(63, 185, 80, 0.2)' : 'linear-gradient(135deg, #00d2ff, #0072ff)',
            border: savedSuccess ? '1px solid rgba(63, 185, 80, 0.5)' : 'none',
            color: savedSuccess ? '#3fb950' : '#ffffff',
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(0, 210, 255, 0.25)',
            transition: 'all 0.2s ease'
          }}
        >
          {savedSuccess ? <Check size={16} /> : <Sparkles size={16} />}
          <span>{savedSuccess ? 'Salvato!' : 'Salva Modifiche'}</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '24px' }}>
        
        {/* SEZIONE 1 — PROFILO UTENTE */}
        <div 
          style={{
            background: '#11131b',
            border: '1px solid #1e2030',
            borderRadius: '16px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #1e2030', paddingBottom: '14px' }}>
            <User size={20} style={{ color: '#00d2ff' }} />
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f0f2f8' }}>Profilo Utente</h3>
          </div>

          {/* Foto Profilo Preview & Upload */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <div style={{ position: 'relative' }}>
              <img 
                src={profile.avatar || '/images/default.png'} 
                alt="Foto Profilo" 
                style={{
                  width: '80px',
                  height: '80px',
                  borderRadius: '50%',
                  objectFit: 'cover',
                  border: '2px solid #00d2ff',
                  boxShadow: '0 0 16px rgba(0, 210, 255, 0.25)',
                  background: '#1a1d2d'
                }}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e4eb' }}>Foto Profilo Chat</span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <label 
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    background: 'rgba(0, 210, 255, 0.1)',
                    border: '1px solid rgba(0, 210, 255, 0.25)',
                    color: '#00d2ff',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  <Upload size={14} />
                  <span>Carica Foto</span>
                  <input type="file" accept="image/*" onChange={handlePhotoUpload} style={{ display: 'none' }} />
                </label>
                <button
                  onClick={() => updateProfile(prev => ({ ...prev, avatar: '/images/default.png' }))}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    background: 'transparent',
                    border: '1px solid #1e2030',
                    color: '#8b8fa3',
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>

          {/* Preset Avatars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: '#8b8fa3', fontWeight: 600 }}>Oppure scegli un avatar preset:</span>
            <div style={{ display: 'flex', gap: '10px' }}>
              {PRESET_AVATARS.map(av => (
                <div
                  key={av.id}
                  onClick={() => updateProfile(prev => ({ ...prev, avatar: av.url }))}
                  style={{
                    cursor: 'pointer',
                    padding: '4px',
                    borderRadius: '50%',
                    border: profile.avatar === av.url ? '2px solid #00d2ff' : '2px solid transparent',
                    transition: 'all 0.15s'
                  }}
                  title={av.name}
                >
                  <img src={av.url} alt={av.name} style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          </div>

          {/* Input Nome Utente */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#8b8fa3' }}>Nome Utente (mostrato in chat):</label>
            <input
              type="text"
              value={profile.name}
              onChange={e => updateProfile(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Inserisci il tuo nome..."
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#0e1016',
                border: '1px solid #1e2030',
                color: '#f0f2f8',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          </div>

          {/* Input Ruolo Utente */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#8b8fa3' }}>Ruolo / Titolo:</label>
            <input
              type="text"
              value={profile.title}
              onChange={e => updateProfile(prev => ({ ...prev, title: e.target.value }))}
              placeholder="es. AI Architect & Developer..."
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#0e1016',
                border: '1px solid #1e2030',
                color: '#f0f2f8',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          </div>
        </div>

        {/* SEZIONE 2 — VOCE ASSISTENTE AI */}
        <div 
          style={{
            background: '#11131b',
            border: '1px solid #1e2030',
            borderRadius: '16px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1e2030', paddingBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Volume2 size={20} style={{ color: '#bc8cff' }} />
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f0f2f8' }}>Voce Assistente AI (TTS)</h3>
            </div>

            {/* Test Voice Button */}
            <button
              onClick={handleTestVoice}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '0.75rem',
                fontWeight: 600,
                background: isPlayingTest ? 'rgba(255, 85, 85, 0.15)' : 'rgba(188, 140, 255, 0.15)',
                border: isPlayingTest ? '1px solid rgba(255, 85, 85, 0.4)' : '1px solid rgba(188, 140, 255, 0.3)',
                color: isPlayingTest ? '#ff5555' : '#bc8cff',
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              {isPlayingTest ? <Square size={13} /> : <Play size={13} />}
              <span>{isPlayingTest ? 'Ferma Test' : '🔊 Test Voce'}</span>
            </button>
          </div>

          {/* Voice Dropdown */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#8b8fa3' }}>Seleziona Voce Sospesa:</label>
            <select
              value={voiceConfig.voiceURI}
              onChange={e => updateVoiceConfig(prev => ({ ...prev, voiceURI: e.target.value }))}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '8px',
                background: '#0e1016',
                border: '1px solid #1e2030',
                color: '#f0f2f8',
                fontSize: '0.82rem',
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
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
              style={{ accentColor: '#bc8cff', cursor: 'pointer' }}
            />
          </div>

          {/* Slider Tono (Pitch) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
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
              style={{ accentColor: '#00d2ff', cursor: 'pointer' }}
            />
          </div>

          {/* Visual Waveform Effect when testing */}
          {isPlayingTest && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', padding: '10px 0' }}>
              <span style={{ fontSize: '0.75rem', color: '#bc8cff', fontWeight: 600, marginRight: '8px' }}>Riproduzione in corso:</span>
              <div style={{ display: 'flex', gap: '3px', alignItems: 'center', height: '20px' }}>
                <span className="wave-bar" style={{ width: '4px', height: '100%', background: '#bc8cff', borderRadius: '2px', animation: 'wave 0.8s infinite ease-in-out' }} />
                <span className="wave-bar" style={{ width: '4px', height: '60%', background: '#00d2ff', borderRadius: '2px', animation: 'wave 0.6s infinite ease-in-out 0.1s' }} />
                <span className="wave-bar" style={{ width: '4px', height: '80%', background: '#bc8cff', borderRadius: '2px', animation: 'wave 1.0s infinite ease-in-out 0.2s' }} />
                <span className="wave-bar" style={{ width: '4px', height: '40%', background: '#00d2ff', borderRadius: '2px', animation: 'wave 0.5s infinite ease-in-out 0.3s' }} />
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
            background: '#11131b',
            border: '1px solid #1e2030',
            borderRadius: '16px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #1e2030', paddingBottom: '14px' }}>
            <ShieldCheck size={20} style={{ color: '#6366f1' }} />
            <div>
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f0f2f8' }}>
                HuggingFace Token
              </h3>
              <div style={{ fontSize: '0.72rem', color: '#8b8fa3', marginTop: '2px' }}>
                Vale per tutta l'app: download dei modelli, dataset e training
              </div>
            </div>
          </div>
          <HFTokenSettings addToast={(message, type) => setTokenNotice({ message, type })} />
          {tokenNotice && (
            <div style={{
              fontSize: '0.75rem', padding: '8px 12px', borderRadius: '8px',
              color: tokenNotice.type === 'error' ? '#ff5555' : '#3fb950',
              background: tokenNotice.type === 'error' ? 'rgba(255,85,85,0.08)' : 'rgba(63,185,80,0.08)',
            }}>
              {tokenNotice.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
