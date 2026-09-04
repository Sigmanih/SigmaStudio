import React, { useState, useRef } from 'react';
import { 
  Palette, Sun, Moon, Sparkles, RefreshCw, Download, Upload, Check, 
  Layers, Image as ImageIcon, Sliders, CheckCircle2, Eye, Layout, Shield
} from 'lucide-react';
import { useApp, THEME_PRESETS, DEFAULT_CUSTOM_THEME } from '../contexts/AppContext';
import TabHeader from './common/TabHeader';

export default function ThemeTab({ openTab }) {
  const { 
    theme, 
    setTheme, 
    customThemeConfig, 
    updateCustomTheme, 
    resetThemeToDefault,
    addToast 
  } = useApp();

  const fileInputRef = useRef(null);
  const jsonImportRef = useRef(null);

  const [imageUrlInput, setImageUrlInput] = useState('');

  // Handle Preset Select
  const handleSelectPreset = (presetId) => {
    setTheme(presetId);
    addToast(`Tema "${THEME_PRESETS.find(p => p.id === presetId)?.name || presetId}" attivato`, 'info');
  };

  // Handle Custom Image Upload
  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 8 * 1024 * 1024) {
      addToast('L\'immagine è troppo grande (max 8MB)', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result;
      if (base64) {
        updateCustomTheme({
          bgEngine: 'custom_image',
          bgCustomImage: base64
        });
        addToast('Immagine di sfondo caricata con successo', 'success');
      }
    };
    reader.readAsDataURL(file);
  };

  const handleApplyImageUrl = () => {
    if (!imageUrlInput.trim()) return;
    updateCustomTheme({
      bgEngine: 'custom_image',
      bgCustomImage: imageUrlInput.trim()
    });
    addToast('URL immagine di sfondo applicato', 'success');
  };

  // Export theme as JSON
  const handleExportTheme = () => {
    const data = {
      theme,
      customConfig: customThemeConfig,
      exportedAt: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sigma_theme_${theme}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    addToast('Configurazione tema esportata', 'success');
  };

  // Import theme from JSON
  const handleImportTheme = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result);
        if (parsed.customConfig) {
          updateCustomTheme(parsed.customConfig);
        }
        if (parsed.theme) {
          setTheme(parsed.theme);
        }
        addToast('Tema importato con successo', 'success');
      } catch {
        addToast('File JSON tema non valido', 'error');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="theme-tab-container">
      {/* Unified Kernel Tab Header */}
      <TabHeader
        badge="SISTEMA TEMI & PALETTE CROMATICHE"
        badgeIcon={Palette}
        icon={Palette}
        title="Personalizzazione "
        highlight="Tema & Colori"
        description="Gestisci la palette cromatica, i preset di visualizzazione per monitor o dispositivi mobili, e personalizza lo sfondo globale con card ad alta leggibilità 100% opache."
        actions={
          <>
            <button className="sigma-tab-btn sigma-tab-btn-ghost" onClick={handleExportTheme} title="Esporta Tema in JSON">
              <Download size={14} /> <span>Esporta</span>
            </button>
            <button className="sigma-tab-btn sigma-tab-btn-ghost" onClick={() => jsonImportRef.current?.click()} title="Importa Tema da JSON">
              <Upload size={14} /> <span>Importa</span>
            </button>
            <input 
              type="file" 
              ref={jsonImportRef} 
              accept=".json" 
              style={{ display: 'none' }} 
              onChange={handleImportTheme} 
            />
            <button className="sigma-tab-btn sigma-tab-btn-ghost" style={{ color: '#ff5555', borderColor: 'rgba(255,85,85,0.3)' }} onClick={resetThemeToDefault} title="Ripristina Predefiniti">
              <RefreshCw size={14} /> <span>Ripristina</span>
            </button>
          </>
        }
      />

      {/* 1. Preset Ufficiali */}
      <section className="theme-section">
        <div className="theme-section-title">
          <Sparkles size={18} style={{ color: 'var(--sigma-primary)' }} />
          Preset Temi Ufficiali
          <span>(Clicca su un tema per applicarlo istantaneamente)</span>
        </div>
        <div className="presets-grid">
          {THEME_PRESETS.map((preset) => {
            const isActive = theme === preset.id;
            return (
              <div 
                key={preset.id} 
                className={`preset-card sigma-card ${isActive ? 'active' : ''}`}
                onClick={() => handleSelectPreset(preset.id)}
              >
                <div className="preset-card-header">
                  <div className="preset-name">
                    {preset.id === 'light' ? <Sun size={16} style={{ color: preset.primary }} /> : <Moon size={16} style={{ color: preset.primary }} />}
                    {preset.name}
                  </div>
                  {isActive && <CheckCircle2 size={18} style={{ color: 'var(--sigma-primary)' }} />}
                </div>
                <div className="card-desc" style={{ fontSize: '0.74rem' }}>
                  {preset.desc}
                </div>
                <div className="preset-palette-preview">
                  <div className="palette-swatch" style={{ background: preset.primary }} title="Primario" />
                  <div className="palette-swatch" style={{ background: preset.accent }} title="Accento" />
                  <div className="palette-swatch" style={{ background: preset.cardBg }} title="Superficie Card" />
                  <div className="palette-swatch" style={{ background: preset.bg }} title="Sfondo Base" />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 2. Personalizzazione Avanzata Palette (Custom Theme) */}
      <section className="theme-section">
        <div className="theme-section-title">
          <Sliders size={18} style={{ color: 'var(--sigma-accent)' }} />
          Palette Personalizzata & Geometria
          <button 
            className="sigma-btn sigma-btn-sm sigma-btn-primary" 
            style={{ marginLeft: 'auto' }}
            onClick={() => setTheme('custom')}
          >
            {theme === 'custom' ? '✓ Modalità Custom Attiva' : 'Attiva Modalità Custom'}
          </button>
        </div>

        <div className="customizer-grid">
          {/* Colore Primario */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Colore Primario</span>
              <span className="custom-color-desc">Tasti principali, focus, bordi attivi</span>
            </div>
            <div className="custom-color-input-wrapper">
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--sigma-text-dim)' }}>{customThemeConfig.primary}</span>
              <input 
                type="color" 
                className="custom-color-picker" 
                value={customThemeConfig.primary}
                onChange={(e) => {
                  updateCustomTheme({ primary: e.target.value });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>

          {/* Colore Accento */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Colore Accento</span>
              <span className="custom-color-desc">Badge secondari, grafici, glow</span>
            </div>
            <div className="custom-color-input-wrapper">
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--sigma-text-dim)' }}>{customThemeConfig.accent}</span>
              <input 
                type="color" 
                className="custom-color-picker" 
                value={customThemeConfig.accent}
                onChange={(e) => {
                  updateCustomTheme({ accent: e.target.value });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>

          {/* Colore Sfondo Base */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Colore Sfondo Base</span>
              <span className="custom-color-desc">Tonalità del fondale globale</span>
            </div>
            <div className="custom-color-input-wrapper">
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--sigma-text-dim)' }}>{customThemeConfig.bg}</span>
              <input 
                type="color" 
                className="custom-color-picker" 
                value={customThemeConfig.bg}
                onChange={(e) => {
                  updateCustomTheme({ bg: e.target.value });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>

          {/* Colore Superficie Card Opaca */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Superficie Card Opaca</span>
              <span className="custom-color-desc">100% solida contro trasparenze</span>
            </div>
            <div className="custom-color-input-wrapper">
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--sigma-text-dim)' }}>{customThemeConfig.cardBg}</span>
              <input 
                type="color" 
                className="custom-color-picker" 
                value={customThemeConfig.cardBg}
                onChange={(e) => {
                  updateCustomTheme({ cardBg: e.target.value });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>

          {/* Colore Testo Principale */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Colore Testo</span>
              <span className="custom-color-desc">Massimo contrasto e leggibilità</span>
            </div>
            <div className="custom-color-input-wrapper">
              <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--sigma-text-dim)' }}>{customThemeConfig.text}</span>
              <input 
                type="color" 
                className="custom-color-picker" 
                value={customThemeConfig.text}
                onChange={(e) => {
                  updateCustomTheme({ text: e.target.value });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>

          {/* Raggio Angoli */}
          <div className="custom-color-row">
            <div className="custom-color-label">
              <span className="custom-color-name">Raggio Angoli Card: {customThemeConfig.borderRadius}px</span>
              <span className="custom-color-desc">Stile squadrato o arrotondato</span>
            </div>
            <div className="custom-color-input-wrapper" style={{ width: '130px' }}>
              <input 
                type="range" 
                min="0" 
                max="26" 
                value={customThemeConfig.borderRadius}
                onChange={(e) => {
                  updateCustomTheme({ borderRadius: Number(e.target.value) });
                  if (theme !== 'custom') setTheme('custom');
                }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* 3. Gestione Sfondo Globale (Background Engine) */}
      <section className="theme-section">
        <div className="theme-section-title">
          <ImageIcon size={18} style={{ color: 'var(--sigma-primary)' }} />
          Engine Sfondo Globale
          <span>(Lo sfondo è visibile dietro, le card rimangono 100% opache)</span>
        </div>

        <div className="bg-engine-options">
          {/* Pattern Predefinito */}
          <div 
            className={`bg-option-card sigma-card ${customThemeConfig.bgEngine === 'pattern' ? 'active' : ''}`}
            onClick={() => updateCustomTheme({ bgEngine: 'pattern' })}
          >
            <div className="bg-option-title">
              <Layout size={16} /> Griglia Tecnica + Glow
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--sigma-text-dim)' }}>
              Trama geometrica con aloni d'ambiente cibernetici.
            </span>
          </div>

          {/* Mesh Gradient */}
          <div 
            className={`bg-option-card sigma-card ${customThemeConfig.bgEngine === 'mesh' ? 'active' : ''}`}
            onClick={() => updateCustomTheme({ bgEngine: 'mesh' })}
          >
            <div className="bg-option-title">
              <Sparkles size={16} /> Mesh Gradient
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--sigma-text-dim)' }}>
              Sfumatura soffusa basata su Primario & Accento.
            </span>
          </div>

          {/* Sfondo Minimale */}
          <div 
            className={`bg-option-card sigma-card ${customThemeConfig.bgEngine === 'solid' ? 'active' : ''}`}
            onClick={() => updateCustomTheme({ bgEngine: 'solid' })}
          >
            <div className="bg-option-title">
              <Layers size={16} /> Minimale Piatto
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--sigma-text-dim)' }}>
              Colore solido pulito senza trame o gradienti.
            </span>
          </div>

          {/* Immagine Custom */}
          <div 
            className={`bg-option-card sigma-card ${customThemeConfig.bgEngine === 'custom_image' ? 'active' : ''}`}
            onClick={() => updateCustomTheme({ bgEngine: 'custom_image' })}
          >
            <div className="bg-option-title">
              <ImageIcon size={16} /> Immagine di Sfondo
            </div>
            <span style={{ fontSize: '0.74rem', color: 'var(--sigma-text-dim)' }}>
              Foto o grafica personalizzata caricata dall'utente.
            </span>
          </div>
        </div>

        {/* Custom Image Controls */}
        {customThemeConfig.bgEngine === 'custom_image' && (
          <div className="sigma-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button 
                className="sigma-btn sigma-btn-primary" 
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={14} /> Carica Immagine Locale
              </button>
              <input 
                type="file" 
                ref={fileInputRef} 
                accept="image/*" 
                style={{ display: 'none' }} 
                onChange={handleImageUpload} 
              />

              <div style={{ display: 'flex', gap: '8px', flex: 1, minWidth: '240px' }}>
                <input 
                  type="text" 
                  className="sigma-input" 
                  placeholder="Oppure incolla URL immagine (https://...)" 
                  value={imageUrlInput}
                  onChange={(e) => setImageUrlInput(e.target.value)}
                />
                <button className="sigma-btn sigma-btn-ghost" onClick={handleApplyImageUrl}>
                  Applica
                </button>
              </div>
            </div>

            {/* Overlay Opacity Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--sigma-text-dim)', whiteSpace: 'nowrap' }}>
                Oscuramento Sfondo ({Math.round((customThemeConfig.bgOverlayOpacity ?? 0.85) * 100)}%):
              </span>
              <input 
                type="range" 
                min="0.3" 
                max="0.95" 
                step="0.05"
                value={customThemeConfig.bgOverlayOpacity ?? 0.85}
                onChange={(e) => updateCustomTheme({ bgOverlayOpacity: Number(e.target.value) })}
              />
            </div>
          </div>
        )}
      </section>

      {/* 4. Live Preview Interattiva Card & Controlli */}
      <section className="theme-section">
        <div className="theme-section-title">
          <Eye size={18} style={{ color: 'var(--sigma-primary)' }} />
          Anteprima in Tempo Reale (Card Opaca & Contrasto)
        </div>

        <div className="theme-live-preview sigma-card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield size={16} style={{ color: 'var(--sigma-primary)' }} />
              <span className="card-title">Card di Test Isolamento & Leggibilità</span>
            </div>
            <span className="sigma-badge badge-primary">100% Opaca</span>
          </div>

          <div className="card-body">
            <p className="card-desc">
              Questa card dimostra come il contenuto rimane nitido e leggibile anche quando è presente un'immagine o 
              un gradiente di sfondo complesso sotto la schermata. Nessun elemento di disturbo visivo traspare.
            </p>

            <div className="preview-elements-row">
              <button className="sigma-btn sigma-btn-primary">Pulsante Primario</button>
              <button className="sigma-btn sigma-btn-ghost">Pulsante Ghost</button>
              <span className="sigma-badge badge-accent">Badge Accento</span>
              <span className="sigma-badge badge-success">Badge Success</span>
              <span className="mod-num">v7.0</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
