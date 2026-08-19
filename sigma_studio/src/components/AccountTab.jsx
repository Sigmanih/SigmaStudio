import React, { useState, useEffect } from 'react';
import { User, Upload, Check, Sparkles, ShieldCheck, HardDrive, Key, CheckCircle2 } from 'lucide-react';
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
  const [savedSuccess, setSavedSuccess] = useState(false);

  // --- Profile State ---
  const [profile, setProfile] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_user_profile');
      if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { name: 'Utente', title: 'AI Developer & Researcher', avatar: '/images/default.png' };
  });

  // Helper to update profile and auto-save + notify app in real-time
  const updateProfile = (updater) => {
    setProfile(prev => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      try {
        const serialized = JSON.stringify(updated);
        localStorage.setItem('sigma_user_profile', serialized);
        window.dispatchEvent(new CustomEvent('sigma_profile_updated', { detail: updated }));
      } catch (e) {
        console.error("Error updating profile:", e);
        window.dispatchEvent(new CustomEvent('sigma_toast', {
          detail: { message: '❌ Errore nel salvataggio del profilo.', type: 'error' }
        }));
      }
      return updated;
    });
  };

  // Save profile preferences to localStorage
  const handleSave = () => {
    try {
      const profileSerialized = JSON.stringify(profile);
      localStorage.setItem('sigma_user_profile', profileSerialized);
      window.dispatchEvent(new CustomEvent('sigma_profile_updated', { detail: profile }));
      
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);

      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: '✅ Profilo salvato con successo!', type: 'success' }
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

        if (width > maxSize || height > maxSize) {
          const ratio = Math.min(maxSize / width, maxSize / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#11131b';
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL('image/jpeg', quality));
      };
      img.onerror = () => reject(new Error('Failed to load image for compression'));
      img.src = dataUrl;
    });
  };

  // Image Upload Handler
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          const dataUrl = event.target?.result;
          if (dataUrl) {
            const compressed = await compressImage(dataUrl, 256, 0.6);
            updateProfile(prev => ({ ...prev, avatar: compressed }));
            window.dispatchEvent(new CustomEvent('sigma_toast', {
              detail: { message: '✅ Avatar aggiornato con successo!', type: 'success' }
            }));
          }
        } catch (compErr) {
          console.error("Compression error:", compErr);
        }
      };
      reader.readAsDataURL(file);
    } catch (err) {
      console.error("Error uploading photo:", err);
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: '❌ Errore durante il caricamento dell\'immagine.', type: 'error' }
      }));
    }
  };

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
      
      {/* Hero Visual Banner */}
      <div style={{
        position: 'relative',
        padding: '24px 32px',
        borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(0, 210, 255, 0.15)',
        background: isLight 
          ? 'linear-gradient(180deg, rgba(234, 88, 12, 0.08) 0%, rgba(247, 244, 237, 0) 100%)' 
          : 'linear-gradient(180deg, rgba(0, 210, 255, 0.08) 0%, rgba(8, 10, 16, 0) 100%)',
        marginBottom: '20px',
        width: '100%',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: isLight ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <User size={14} /> ACCOUNT & PREFERENCE HUB
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: isLight ? '#111111' : '#fff', letterSpacing: '-0.3px' }}>
              👤 Profilo Utente & <span style={{
                color: isLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Credenziali Esterne</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: isLight ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Personalizza il tuo avatar, ruolo di sistema e configura i token di integrazione esterna per il download di modelli e dataset.
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
                background: savedSuccess 
                  ? 'rgba(63, 185, 80, 0.2)' 
                  : (isLight ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : 'linear-gradient(135deg, #00d2ff, #0072ff)'),
                border: savedSuccess ? '1px solid rgba(63, 185, 80, 0.5)' : 'none',
                color: savedSuccess ? '#3fb950' : '#fff',
                cursor: 'pointer',
                boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.25)' : '0 4px 16px rgba(0, 210, 255, 0.25)',
                transition: 'all 0.2s ease'
              }}
            >
              {savedSuccess ? <Check size={16} /> : <Sparkles size={16} />}
              <span>{savedSuccess ? 'Profilo Salvato!' : 'Salva Modifiche'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Content Grid */}
      <div style={{ padding: '0 24px 32px 24px', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', flex: 1, minHeight: 0, alignItems: 'stretch' }}>
        
          {/* COLONNA SINISTRA — PROFILO UTENTE & AVATAR */}
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
              <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: isLight ? '#111' : '#f0f2f8' }}>Profilo Utente & Avatar</h3>
            </div>

            {/* Avatar Preview & Upload Area */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                overflow: 'hidden',
                border: '2px solid #00d2ff',
                flexShrink: 0,
                background: '#080a10'
              }}>
                <img 
                  src={profile.avatar} 
                  alt="Avatar Utente" 
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={(e) => { e.currentTarget.src = '/images/default.png'; }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: isLight ? '#111' : '#f0f2f8' }}>
                  {profile.name || 'Utente'}
                </div>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3' }}>
                  {profile.title || 'AI Developer'}
                </div>
                
                <label style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  background: 'rgba(0, 210, 255, 0.12)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  color: '#00d2ff',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  width: 'fit-content'
                }}>
                  <Upload size={12} />
                  <span>Carica Foto / Avatar</span>
                  <input type="file" accept="image/*" onChange={handlePhotoUpload} style={{ display: 'none' }} />
                </label>
              </div>
            </div>

            {/* Presets Avatar Grid */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Preset Rapidi Avatar:</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {PRESET_AVATARS.map(avatar => {
                  const isSelected = profile.avatar === avatar.url;
                  return (
                    <button
                      key={avatar.id}
                      onClick={() => updateProfile(prev => ({ ...prev, avatar: avatar.url }))}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '8px',
                        borderRadius: '8px',
                        background: isSelected ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255,255,255,0.03)',
                        border: isSelected ? '1px solid #00d2ff' : '1px solid rgba(255,255,255,0.05)',
                        cursor: 'pointer',
                        transition: 'all 0.15s'
                      }}
                    >
                      <img 
                        src={avatar.url} 
                        alt={avatar.name} 
                        style={{ width: '36px', height: '36px', borderRadius: '50%', objectFit: 'cover' }} 
                      />
                      <span style={{ fontSize: '0.68rem', color: isSelected ? '#00d2ff' : '#8b8fa3', fontWeight: isSelected ? 700 : 500 }}>
                        {avatar.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Input Nome */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 600, color: '#8b8fa3' }}>Nome Utente:</label>
              <input
                type="text"
                value={profile.name}
                onChange={e => updateProfile(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Il tuo nome o nickname..."
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

            {/* Input Ruolo */}
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

          {/* COLONNA DESTRA — STATO SESSIONE & STORAGE */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

            {/* SEZIONE STORAGE & STATO SESSIONE */}
            <div
              style={{
                backgroundColor: isLight ? '#fffdf9' : '#0e1017',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(0, 210, 255, 0.15)',
                borderRadius: '14px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
                <HardDrive size={18} style={{ color: '#00d2ff' }} />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: isLight ? '#111' : '#f0f2f8' }}>
                  Stato Sessione & Profilo
                </h3>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem', color: '#8b8fa3' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Dimensione Profilo Salvato:</span>
                  <span style={{ color: '#00d2ff', fontWeight: 600 }}>
                    ~{Math.round((JSON.stringify(profile).length * 2) / 1024)} KB
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Archiviazione Locale:</span>
                  <span style={{ color: '#3fb950', fontWeight: 600 }}>Attiva (LocalStorage)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Sincronizzazione Realtime Swarm:</span>
                  <span style={{ color: '#3fb950', fontWeight: 600 }}>Abilitata</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
