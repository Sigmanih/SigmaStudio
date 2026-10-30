import React, { useState, useEffect } from 'react';
import { Send, Paperclip, RefreshCw, StopCircle, Mic, MicOff, AudioLines, Volume2, VolumeX, Sliders, Square, ChevronDown, Cpu, X, FileText, Image } from 'lucide-react';
import { setVoiceConfig as saveVoiceConfigToSpeechEngine, getVoiceConfig, getVoiceSilenceTimeout, setVoiceSilenceTimeout } from '../audioSpeech';
import ModelSelector from '../ModelSelector';

export default function ChatInput({
  input, setInput, loading, refs, providerColors, currentRouting,
  autoScroll, setAutoScroll,
  mcpAutoApprove, setMcpAutoApprove,
  devModeAvailable, devModeEnabled, setDevModeEnabled,
  devRoles = [], devRole = 'auto', setDevRole,
  speakerEnabled, setSpeakerEnabled,
  isRecording, onToggleRecording,
  smartMicState = 'off', onToggleSmartMic,
  loopMaxIterations, setLoopMaxIterations, loopActive,
  onSend, onStop, onOpenFilePicker, attachedFiles, onRemoveAttachment,
  // Model Selector props
  selectedModel, availableModels, loadingModels,
  showModelDropdown, onToggleModelDropdown, onSelectModel,
  providerConfigs, modelBtnRef,
  favoriteModel, favoriteModels, onSetFavoriteModel, onOpenConfig,
  // Manifesto / Role Selector props
  activeManifesto, manifestos,
  showManifestoDropdown, setShowManifestoDropdown, onSelectManifesto,
  // Hardware Selector props
  selectedHardware, onSelectHardware, availableHardware,
  // Quick Config Parameters
  quickConfig, setQuickConfig,
  compactControls = false,
  children,
}) {
  const [showVoicePopover, setShowVoicePopover] = useState(false);
  const [showAdvancedParams, setShowAdvancedParams] = useState(false);
  // Nel pannello flottante modello, ruolo e interruttori occupavano meta' altezza:
  // restano a un clic di distanza e lasciano spazio alla conversazione.
  const [showControls, setShowControls] = useState(!compactControls);

  // In Dev Mode il selettore sceglie il ruolo dell'harness, non il manifesto
  // della chat: e' il ruolo che decide procedura e tool dell'agente.
  const inDev = !!devModeEnabled;
  const ruoliDev = [
    { id: 'auto', name: 'auto', icon: '🎭', role: 'Agente generico: consulta lo specialista quando serve' },
    ...devRoles.map(r => ({ id: r.id, name: r.name, icon: r.icon, role: r.focus })),
  ];
  const ruoloDevAttivo = ruoliDev.find(r => r.id === devRole) || ruoliDev[0];
  const vociRuolo = inDev ? ruoliDev : (manifestos || []);
  const ruoloAttivo = inDev ? ruoloDevAttivo : activeManifesto;
  const eAttivo = (m) => (inDev ? m.id === ruoloDevAttivo.id : activeManifesto?.name === m.name);
  const scegliRuolo = (m) => {
    if (inDev) {
      if (setDevRole) setDevRole(m.id);
      if (setShowManifestoDropdown) setShowManifestoDropdown(false);
    } else if (onSelectManifesto) {
      onSelectManifesto(m);
    }
  };
  const [voiceConfig, setVoiceConfigState] = useState(() => getVoiceConfig());
  const [voiceSilenceTimeout, setVoiceSilenceTimeoutState] = useState(() => getVoiceSilenceTimeout());

  useEffect(() => {
    const onVoiceTimeoutUpdated = (e) => {
      if (typeof e.detail === 'number') {
        setVoiceSilenceTimeoutState(e.detail);
      }
    };
    window.addEventListener('sigma-voice-timeout-updated', onVoiceTimeoutUpdated);
    return () => window.removeEventListener('sigma-voice-timeout-updated', onVoiceTimeoutUpdated);
  }, []);

  const handleSetVoiceSilenceTimeout = (sec) => {
    setVoiceSilenceTimeoutState(sec);
    setVoiceSilenceTimeout(sec);
  };

  const updateVoiceConfig = (updater) => {
    setVoiceConfigState(prev => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      saveVoiceConfigToSpeechEngine(updated);
      return updated;
    });
  };

  // Ridimensionamento dinamico della textarea quando si scrive codice o testo multilinea
  // e reset automatico all'altezza iniziale compatta quando il messaggio viene inviato
  const adjustHeight = (el) => {
    if (!el) return;
    el.style.height = 'auto';
    const scrollH = el.scrollHeight;
    const newHeight = Math.min(Math.max(scrollH, 44), 380);
    el.style.height = `${newHeight}px`;
  };

  useEffect(() => {
    const el = refs?.input?.current;
    if (!el) return;
    if (!input) {
      el.style.height = '44px';
      return;
    }
    adjustHeight(el);
  }, [input, refs?.input]);

  const handleInputChange = (e) => {
    setInput(e.target.value);
    adjustHeight(e.target);
  };

  const effectiveFavs = Array.isArray(favoriteModels) && favoriteModels.length > 0 
    ? favoriteModels 
    : (favoriteModel ? [favoriteModel] : []);

  return (
    <div className="chat-input-area">
      {/* Modern Extended Model & Role Selection Strip */}
      {showControls && (
      <div className="chat-input-controls-strip">
        <div className="chat-settings-primary">
          {/* 1. Extended Model Selector with explicit Label */}
          <div className="chat-control-field">
            <span className="chat-control-label">Modello:</span>
            <ModelSelector
              modelBtnRef={modelBtnRef}
              effectiveModelName={selectedModel}
              showDropdown={showModelDropdown}
              models={availableModels}
              selectedModel={selectedModel}
              loadingModels={loadingModels}
              providerConfigs={providerConfigs}
              onToggle={onToggleModelDropdown}
              onSelect={onSelectModel}
              onOpenConfig={onOpenConfig}
              favoriteModel={favoriteModel}
              favoriteModels={effectiveFavs}
              onSetFavorite={onSetFavoriteModel}
            />
          </div>

          {/* 2. Extended Role / Manifesto Selector with explicit Label */}
          <div className="chat-control-field">
            <span className="chat-control-label">Ruolo:</span>
            <div className="manifesto-selector-wrapper" style={{ position: 'relative' }}>
              <button
                type="button"
                className={`manifesto-selector-btn ${!ruoloAttivo?.name ? 'no-manifesto' : ''}`}
                onClick={(e) => { e.stopPropagation(); setShowManifestoDropdown && setShowManifestoDropdown(!showManifestoDropdown); }}
                title={inDev ? "Ruolo dell'agente in Dev Mode: decide procedura e tool" : (ruoloAttivo?.role ? `${ruoloAttivo.name}: ${ruoloAttivo.role}` : "Seleziona il Ruolo Specialistico dell'Agente")}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: '1 1 auto', overflow: 'hidden' }}>
                  <span className="manifesto-icon">{ruoloAttivo?.icon || '🎭'}</span>
                  <span className="manifesto-name">{ruoloAttivo?.name || 'Sigma Assistant'}</span>
                </div>
                <ChevronDown size={11} className={`manifesto-chevron ${showManifestoDropdown ? 'open' : ''}`} />
              </button>

              {showManifestoDropdown && (
                <div className="model-selector-popover manifesto-popover" style={{ left: 0, transform: 'none', minWidth: '280px', maxHeight: '340px', overflowY: 'auto', zIndex: 2100 }}>
                  {vociRuolo.length === 0 && (
                    <div className="model-selector-option disabled" style={{ padding: '8px 12px', fontSize: '0.74rem', color: '#8b8fa3' }}>
                      Nessun ruolo installato
                    </div>
                  )}
                  {vociRuolo.map(m => (
                    <div
                      key={m.id || m.path || m.name}
                      className={`model-selector-option ${eAttivo(m) ? 'selected' : ''}`}
                      onClick={(e) => { e.stopPropagation(); scegliRuolo(m); }}
                      style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '8px 12px', gap: '2px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 800, fontSize: '0.76rem', color: eAttivo(m) ? '#00d2ff' : '#f1f5f9' }}>
                          {m.icon || '📋'} {m.name}
                        </span>
                        {eAttivo(m) && <span style={{ fontSize: '0.74rem', color: '#10b981', fontWeight: 800 }}>✓</span>}
                      </div>
                      {m.role && (
                        <span style={{ fontSize: '0.64rem', color: 'var(--text-muted, #8b8fa3)', paddingLeft: '18px', lineHeight: 1.3 }}>
                          {m.role}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 3. Extended Hardware / Accelerator Selector */}
          <div className="chat-control-field">
            <span className="chat-control-label">Hardware:</span>
            <div className="manifesto-selector-wrapper" style={{ position: 'relative' }}>
              <select
                className="manifesto-selector-btn chat-hardware-select"
                value={selectedHardware || 'auto'}
                onChange={(e) => onSelectHardware && onSelectHardware(e.target.value)}
                title="Seleziona la GPU o l'acceleratore dedicato per l'inferenza"
              >
                {(availableHardware && availableHardware.length > 0 ? availableHardware : [
                  { id: 'auto', name: '⚡ Auto (Tutto)' },
                  { id: 'gpu:0', name: '🟢 GPU 0 (Principale)' },
                  { id: 'gpu:1', name: '🔵 GPU 1 (Secondaria)' },
                  { id: 'cpu', name: '💻 Solo CPU' }
                ]).map(hw => (
                  <option key={hw.id} value={hw.id} style={{ background: '#0f1420', color: '#fff' }}>
                    {hw.name}
                  </option>
                ))}
              </select>
              <Cpu size={12} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: '#10b981' }} />
            </div>
          </div>
        </div>

        {/* Middle Group: Utility Toggles & Speaker Controls */}
        <div className="chat-settings-toggles">
          <label className="chat-scroll-toggle" title="Auto-scroll verso l'ultimo messaggio inviato o generato">
            <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            <span>📜 Auto Scroll</span>
          </label>
          <label
            className="chat-scroll-toggle"
            title={mcpAutoApprove
              ? 'Gli agenti eseguono subito anche gli strumenti che agiscono su casa, email e messaggi'
              : 'Gli strumenti che agiscono verso l\'esterno aspettano la tua conferma in chat'}
            style={{ color: mcpAutoApprove ? '#d29922' : undefined }}
          >
            <input
              type="checkbox"
              checked={!!mcpAutoApprove}
              onChange={e => setMcpAutoApprove?.(e.target.checked)}
            />
            <span>{mcpAutoApprove ? '⚡' : '🛡️'} Auto Approve</span>
          </label>
          {devModeAvailable && (
            <label
              className="chat-scroll-toggle"
              title={devModeEnabled
                ? 'Modalità Sviluppo ATTIVA: l\'agente ha accesso all\'harness con lettura/scrittura file, esecuzione test e terminale'
                : 'Modalità Sviluppo SPENTA: clicca per abilitare l\'Harness di Sviluppo con loop autonomo e tool MCP'}
              style={{
                color: devModeEnabled ? '#00d2ff' : undefined,
                borderColor: devModeEnabled ? 'rgba(0, 210, 255, 0.4)' : undefined,
                background: devModeEnabled ? 'rgba(0, 210, 255, 0.12)' : undefined,
                fontWeight: devModeEnabled ? 700 : 500
              }}
            >
              <input
                type="checkbox"
                checked={!!devModeEnabled}
                onChange={e => setDevModeEnabled?.(e.target.checked)}
              />
              <span>{devModeEnabled ? '🛠️' : '🔧'} Dev Mode</span>
            </label>
          )}
          {setSpeakerEnabled !== undefined && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', position: 'relative' }}>
              <label 
                className={`chat-speaker-toggle ${speakerEnabled ? 'active' : ''}`} 
                title={speakerEnabled ? 'Speaker Agente: ON (Voce attiva - Clicca per disattivare)' : 'Speaker Agente: OFF (Clicca per attivare la lettura vocale TTS)'}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '28px',
                  height: '24px',
                  color: speakerEnabled ? '#00d2ff' : '#8b8fa3',
                  background: speakerEnabled ? 'rgba(0, 210, 255, 0.16)' : 'rgba(255, 255, 255, 0.04)',
                  border: speakerEnabled ? '1px solid rgba(0, 210, 255, 0.45)' : '1px solid rgba(255, 255, 255, 0.08)',
                  boxShadow: speakerEnabled ? '0 0 10px rgba(0, 210, 255, 0.35)' : 'none',
                  borderRadius: '7px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <input 
                  type="checkbox" 
                  checked={speakerEnabled} 
                  onChange={e => setSpeakerEnabled(e.target.checked)} 
                  style={{ display: 'none' }}
                />
                {speakerEnabled ? <Volume2 size={13} style={{ color: '#00d2ff' }} /> : <VolumeX size={13} style={{ color: '#64748b' }} />}
              </label>

            {/* Volume Slider accanto al pulsante Speaker Agente */}
            {speakerEnabled && (
              <div 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'rgba(0, 210, 255, 0.08)',
                  border: '1px solid rgba(0, 210, 255, 0.25)',
                  borderRadius: '12px',
                  padding: '2px 7px',
                  transition: 'all 0.2s ease',
                }}
                title={`Volume voce agente: ${Math.round((voiceConfig.volume ?? 1.0) * 100)}%`}
              >
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={voiceConfig.volume ?? 1.0}
                  onChange={e => updateVoiceConfig(prev => ({ ...prev, volume: parseFloat(e.target.value) }))}
                  style={{
                    width: '55px',
                    height: '3px',
                    accentColor: '#00d2ff',
                    cursor: 'pointer',
                  }}
                />
                <span style={{ fontSize: '0.64rem', fontWeight: 700, color: '#00d2ff', minWidth: '24px' }}>
                  {Math.round((voiceConfig.volume ?? 1.0) * 100)}%
                </span>
              </div>
            )}

            {/* Voice Tuning Button */}
            <button
              type="button"
              className={`chat-voice-tune-btn ${showVoicePopover ? 'active' : ''}`}
              onClick={(e) => { e.stopPropagation(); setShowVoicePopover(!showVoicePopover); }}
              title="Regola Velocità (Speed), Tono (Pitch) e Volume della voce dell'agente"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 7px',
                fontSize: '0.66rem',
                fontWeight: 600,
                color: showVoicePopover ? '#bc8cff' : '#8b8fa3',
                background: showVoicePopover ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                border: showVoicePopover ? '1px solid rgba(188, 140, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <Sliders size={12} color={showVoicePopover ? '#bc8cff' : '#00d2ff'} />
              <span>{voiceConfig.rate || 1.05}x</span>
            </button>

            {/* Popover Regolazione Voce */}
            {showVoicePopover && (
              <div 
                style={{
                  position: 'absolute',
                  bottom: '100%',
                  right: 0,
                  marginBottom: '8px',
                  width: '240px',
                  padding: '14px',
                  background: 'rgba(15, 17, 26, 0.95)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  zIndex: 2000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f0f2f8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Sliders size={13} color="#00f2fe" /> Regolazione Voce TTS
                  </span>
                  <button 
                    onClick={() => setShowVoicePopover(false)} 
                    style={{ background: 'none', border: 'none', color: '#8b8fa3', cursor: 'pointer', fontSize: '0.8rem' }}
                  >
                    ✕
                  </button>
                </div>

                {/* Slider Volume */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Volume Voce:</span>
                    <span style={{ color: '#00d2ff', fontWeight: 700 }}>{Math.round((voiceConfig.volume ?? 1.0) * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={voiceConfig.volume ?? 1.0}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, volume: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#00d2ff', cursor: 'pointer', height: '4px' }}
                  />
                </div>

                {/* Slider Velocità */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Velocità Lettura:</span>
                    <span style={{ color: '#bc8cff', fontWeight: 700 }}>{voiceConfig.rate || 1.05}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.7"
                    max="1.6"
                    step="0.05"
                    value={voiceConfig.rate || 1.05}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, rate: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#bc8cff', cursor: 'pointer', height: '4px' }}
                  />
                </div>

                {/* Slider Tono */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Tono Voce (Pitch):</span>
                    <span style={{ color: '#00d2ff', fontWeight: 700 }}>{voiceConfig.pitch || 1.0}</span>
                  </div>
                  <input
                    type="range"
                    min="0.6"
                    max="1.4"
                    step="0.05"
                    value={voiceConfig.pitch || 1.0}
                    onChange={e => updateVoiceConfig(prev => ({ ...prev, pitch: parseFloat(e.target.value) }))}
                    style={{ accentColor: '#00d2ff', cursor: 'pointer', height: '4px' }}
                  />
                </div>

                {/* Timeout Auto-invio Microfono (Silenzio) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                    <span style={{ color: '#8b8fa3', fontWeight: 600 }}>Invio vocale dopo silenzio:</span>
                    <span style={{ color: voiceSilenceTimeout > 0 ? '#10b981' : '#f59e0b', fontWeight: 700 }}>
                      {voiceSilenceTimeout > 0 ? `${voiceSilenceTimeout.toFixed(1)}s` : 'Off (Manuale)'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {[
                      { sec: 1.0, label: '1.0s' },
                      { sec: 1.5, label: '1.5s' },
                      { sec: 2.0, label: '2.0s' },
                      { sec: 3.0, label: '3.0s' },
                      { sec: 5.0, label: '5.0s' },
                      { sec: 0, label: 'Off' },
                    ].map(opt => (
                      <button
                        key={opt.sec}
                        type="button"
                        onClick={() => handleSetVoiceSilenceTimeout(opt.sec)}
                        style={{
                          flex: '1 1 auto',
                          padding: '3px 6px',
                          fontSize: '0.64rem',
                          fontWeight: 700,
                          borderRadius: '6px',
                          cursor: 'pointer',
                          border: voiceSilenceTimeout === opt.sec ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.1)',
                          background: voiceSilenceTimeout === opt.sec ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255,255,255,0.03)',
                          color: voiceSilenceTimeout === opt.sec ? '#10b981' : '#94a3b8',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

          {/* Quick Mic Auto-send Timeout Selector */}
          <div 
            className="chat-voice-timeout-pill"
            title={`Timeout invio vocale automatico dopo che smetti di parlare: ${voiceSilenceTimeout > 0 ? voiceSilenceTimeout + 's' : 'Disattivato (invio con Invio)'}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: '7px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              fontSize: '0.64rem',
              color: '#94a3b8'
            }}
          >
            <Mic size={11} color={voiceSilenceTimeout > 0 ? '#10b981' : '#f59e0b'} />
            <span>Mic invio:</span>
            <select
              value={voiceSilenceTimeout}
              onChange={e => handleSetVoiceSilenceTimeout(parseFloat(e.target.value))}
              style={{
                background: 'transparent',
                border: 'none',
                color: voiceSilenceTimeout > 0 ? '#10b981' : '#f59e0b',
                fontWeight: 700,
                fontSize: '0.64rem',
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value={1.0} style={{ background: '#0f1420', color: '#fff' }}>1.0s</option>
              <option value={1.5} style={{ background: '#0f1420', color: '#fff' }}>1.5s</option>
              <option value={2.0} style={{ background: '#0f1420', color: '#fff' }}>2.0s (Consigliato)</option>
              <option value={3.0} style={{ background: '#0f1420', color: '#fff' }}>3.0s</option>
              <option value={5.0} style={{ background: '#0f1420', color: '#fff' }}>5.0s</option>
              <option value={0} style={{ background: '#0f1420', color: '#fff' }}>Off (Manuale)</option>
            </select>
          </div>
        </div>

        {/* Unified Model Parameters & Presets Section */}
        {quickConfig && setQuickConfig && (
          <div className="chat-settings-params">
            {/* Presets Row & Details Toggle */}
            <div className="chat-presets-header">
              <div className="chat-presets-list">
                <span className="chat-presets-label">
                  <Sliders size={11} color="#00d2ff" /> Preset:
                </span>
                <button
                  type="button"
                  className={`chat-preset-btn ${quickConfig.temperature === 0.7 ? 'active' : ''}`}
                  onClick={() => setQuickConfig(prev => ({ ...prev, temperature: 0.7, top_p: 0.95, top_k: 40, repeat_penalty: 1.1, max_tokens: 16384, num_ctx: 32768 }))}
                >
                  🎯 Bilanciato
                </button>
                <button
                  type="button"
                  className={`chat-preset-btn ${quickConfig.temperature === 0.2 ? 'active' : ''}`}
                  onClick={() => setQuickConfig(prev => ({ ...prev, temperature: 0.2, top_p: 0.9, top_k: 40, repeat_penalty: 1.05, max_tokens: 32768, num_ctx: 65536 }))}
                >
                  🔬 Codice & Logica
                </button>
                <button
                  type="button"
                  className={`chat-preset-btn ${quickConfig.temperature === 0.85 ? 'active' : ''}`}
                  onClick={() => setQuickConfig(prev => ({ ...prev, temperature: 0.85, top_p: 0.95, top_k: 50, repeat_penalty: 1.05, max_tokens: 16384, num_ctx: 65536 }))}
                >
                  🎨 Creativo
                </button>
                <button
                  type="button"
                  className={`chat-preset-btn ${quickConfig.temperature === 1.2 ? 'active' : ''}`}
                  onClick={() => setQuickConfig(prev => ({ ...prev, temperature: 1.2, top_p: 1.0, top_k: 80, repeat_penalty: 1.0, max_tokens: 32768, num_ctx: 65536 }))}
                >
                  🔓 Libero
                </button>
              </div>

              <button
                type="button"
                className={`chat-params-toggle-btn ${showAdvancedParams ? 'active' : ''}`}
                onClick={() => setShowAdvancedParams(!showAdvancedParams)}
              >
                <span>Parametri Modello (Temp: {quickConfig.temperature})</span>
                <ChevronDown size={11} className={`chat-params-chevron ${showAdvancedParams ? 'open' : ''}`} />
              </button>
            </div>

            {/* Collapsible Sliders & Detailed Parameters */}
            {showAdvancedParams && (
              <div className="chat-params-grid">
                {/* Temp */}
                <div className="chat-param-card">
                  <div className="chat-param-header">
                    <span className="chat-param-title">🌡️ Temperatura:</span>
                    <span className="chat-param-val" style={{ color: '#00d2ff' }}>{quickConfig.temperature?.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min="0" max="2" step="0.05"
                    value={quickConfig.temperature ?? 0.7}
                    onChange={e => setQuickConfig(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                    className="chat-param-slider"
                    style={{ accentColor: '#00d2ff' }}
                  />
                </div>

                {/* Top P */}
                <div className="chat-param-card">
                  <div className="chat-param-header">
                    <span className="chat-param-title">🎯 Top P:</span>
                    <span className="chat-param-val" style={{ color: '#00d2ff' }}>{quickConfig.top_p?.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min="0" max="1" step="0.05"
                    value={quickConfig.top_p ?? 0.95}
                    onChange={e => setQuickConfig(prev => ({ ...prev, top_p: parseFloat(e.target.value) }))}
                    className="chat-param-slider"
                    style={{ accentColor: '#00d2ff' }}
                  />
                </div>

                {/* Top K */}
                <div className="chat-param-card">
                  <div className="chat-param-header">
                    <span className="chat-param-title">🔝 Top K:</span>
                    <span className="chat-param-val" style={{ color: '#bc8cff' }}>{quickConfig.top_k}</span>
                  </div>
                  <input
                    type="range" min="1" max="100" step="1"
                    value={quickConfig.top_k ?? 40}
                    onChange={e => setQuickConfig(prev => ({ ...prev, top_k: parseInt(e.target.value) }))}
                    className="chat-param-slider"
                    style={{ accentColor: '#bc8cff' }}
                  />
                </div>

                {/* Repeat Penalty */}
                <div className="chat-param-card">
                  <div className="chat-param-header">
                    <span className="chat-param-title">🔁 Penalità Ripetizione:</span>
                    <span className="chat-param-val" style={{ color: '#10b981' }}>{quickConfig.repeat_penalty?.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min="0" max="2" step="0.05"
                    value={quickConfig.repeat_penalty ?? 1.1}
                    onChange={e => setQuickConfig(prev => ({ ...prev, repeat_penalty: parseFloat(e.target.value) }))}
                    className="chat-param-slider"
                    style={{ accentColor: '#10b981' }}
                  />
                </div>

                {/* Max Tokens Select */}
                <div className="chat-param-card">
                  <span className="chat-param-title">📝 Max Tokens:</span>
                  <select
                    value={quickConfig.max_tokens ?? 16384}
                    onChange={e => setQuickConfig(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
                    className="chat-param-select"
                  >
                    {[2048, 4096, 8192, 16384, 32768, 65536].map(v => (
                      <option key={v} value={v} style={{ background: '#0f1420', color: '#fff' }}>
                        {v >= 1024 ? `${v/1024}K token` : `${v} token`}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Context Window Select */}
                <div className="chat-param-card">
                  <span className="chat-param-title">🧠 Contesto (num_ctx):</span>
                  <select
                    value={quickConfig.num_ctx ?? 32768}
                    onChange={e => setQuickConfig(prev => ({ ...prev, num_ctx: parseInt(e.target.value) }))}
                    className="chat-param-select"
                  >
                    {[4096, 8192, 16384, 32768, 65536, 131072].map(v => (
                      <option key={v} value={v} style={{ background: '#0f1420', color: '#fff' }}>
                        {v >= 1024 ? `${v/1024}K finestra` : `${v} token`}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Timeout Select */}
                <div className="chat-param-card">
                  <span className="chat-param-title">⏱️ Timeout Risposta:</span>
                  <select
                    value={quickConfig.timeout ?? 300}
                    onChange={e => setQuickConfig(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
                    className="chat-param-select"
                  >
                    {[60, 120, 300, 600, 900].map(v => (
                      <option key={v} value={v} style={{ background: '#0f1420', color: '#fff' }}>
                        {v >= 60 ? `${v/60}m` : `${v}s`} {v === 300 ? '(Consigliato)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      )}

      {/* Barra Chip Allegati Correnti */}
      {attachedFiles && attachedFiles.length > 0 && (
        <div className="chat-attachments-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.68rem', color: '#8b8fa3', marginRight: '4px', fontWeight: 600 }}>
            <Paperclip size={12} style={{ color: '#00d2ff' }} />
            <span>Allegati ({attachedFiles.length}):</span>
          </div>
          {attachedFiles.map((f, idx) => {
            const name = typeof f === 'string' ? f.replace('__pc__', '').split('/').pop() : (f.name || f.filename || `allegato-${idx + 1}`);
            const sizeStr = f && f.size ? (f.size > 1024 * 1024 ? `${(f.size / (1024 * 1024)).toFixed(1)} MB` : `${Math.round(f.size / 1024)} KB`) : '';
            const isPdf = name.toLowerCase().endsWith('.pdf') || (f && f.isPdf);
            const isImg = /\.(png|jpe?g|gif|webp|svg)$/i.test(name) || (f && f.isImage);
            return (
              <span
                key={typeof f === 'string' ? f : (f.filename || idx)}
                className="chat-attachment-chip attached"
                title={typeof f === 'string' ? f : `${name} ${sizeStr ? `(${sizeStr})` : ''}`}
              >
                {isPdf ? (
                  <FileText size={11} style={{ color: '#ef4444' }} />
                ) : isImg ? (
                  <Image size={11} style={{ color: '#ec4899' }} />
                ) : (
                  <FileText size={11} style={{ color: '#00d2ff' }} />
                )}
                <span style={{ maxWidth: '170px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {name}
                </span>
                {sizeStr && <span style={{ opacity: 0.65, fontSize: '0.6rem' }}>({sizeStr})</span>}
                {onRemoveAttachment && (
                  <button
                    type="button"
                    className="chat-attachment-remove"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveAttachment(f);
                    }}
                    title={`Rimuovi ${name}`}
                  >
                    <X size={11} />
                  </button>
                )}
              </span>
            );
          })}
        </div>
      )}

      <div className="chat-input-row">
        <textarea
          ref={refs.input}
          className="chat-input"
          placeholder={
            isRecording ? "🔴 Registrazione in corso... Parla adesso..."
            : smartMicState === 'listening' ? "🎤 Ti sto ascoltando... Parla adesso (invio automatico dopo 2s di silenzio)"
            : smartMicState === 'waiting' ? '✨ Pronuncia "Sigma" ed inizia a fare la tua domanda...'
            : `Chiedi qualcosa a ${selectedModel}...`
          }
          value={input}
          onChange={handleInputChange}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (!loading) onSend();
            }
          }}
          rows={1}
          style={
            isRecording ? { borderColor: '#ff5555', background: 'rgba(255, 85, 85, 0.06)' }
            : smartMicState === 'listening' ? { borderColor: '#4ade80', background: 'rgba(74, 222, 128, 0.06)' }
            : smartMicState === 'waiting' ? { borderColor: 'rgba(0, 210, 255, 0.4)' }
            : {}
          }
        />
        {(onToggleSmartMic || onToggleRecording) && (
          <button
            className={`chat-attach-inline-btn ${smartMicState !== 'off' || isRecording ? 'recording' : ''}`}
            onClick={onToggleSmartMic || onToggleRecording}
            title={
              smartMicState === 'listening'
                ? '🎤 Ti sto ascoltando... Parla adesso (invio automatico al termine)'
                : smartMicState === 'waiting'
                ? '✨ Microfono in ascolto: pronuncia "Sigma" ed inizia a fare la tua domanda'
                : 'Attiva microfono vocale (risponde ed ascolta pronunciando "Sigma")'
            }
            style={{
              color: smartMicState === 'listening' ? '#22c55e'
                : smartMicState === 'waiting' ? '#00d2ff'
                : 'var(--text-muted, #8b8fa3)',
              background: smartMicState === 'listening' ? 'rgba(34, 197, 94, 0.18)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.15)'
                : 'transparent',
              borderColor: smartMicState === 'listening' ? 'rgba(34, 197, 94, 0.5)'
                : smartMicState === 'waiting' ? 'rgba(0, 210, 255, 0.4)'
                : 'transparent',
              boxShadow: smartMicState === 'listening' ? '0 0 12px rgba(34, 197, 94, 0.4)'
                : smartMicState === 'waiting' ? '0 0 12px rgba(0, 210, 255, 0.35)'
                : 'none',
              animation: smartMicState === 'listening' ? 'pulseMic 1.2s infinite' : 'none'
            }}
          >
            {smartMicState === 'listening' || smartMicState === 'waiting' || isRecording ? (
              <Mic size={15} />
            ) : (
              <MicOff size={15} />
            )}
          </button>
        )}
        {compactControls && (
          <button
            type="button"
            className={`chat-attach-inline-btn chat-options-toggle ${showControls ? 'active' : ''}`}
            onClick={() => setShowControls(v => !v)}
            title={showControls ? 'Nascondi modello, ruolo e opzioni' : 'Mostra modello, ruolo e opzioni'}
            aria-expanded={showControls}
          >
            <Sliders size={14} />
          </button>
        )}
        <button className="chat-attach-inline-btn" onClick={onOpenFilePicker} title="Allega file">
          <Paperclip size={14} />
          {attachedFiles.length > 0 && <span className="chat-attach-count">{attachedFiles.length}</span>}
        </button>
        {loading ? (
          <button 
            className="chat-send-btn stop" 
            onClick={(e) => { e.preventDefault(); onStop && onStop(e); }} 
            title="Ferma task (puoi sempre riprenderlo)"
            style={{
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              borderColor: '#b91c1c',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(239, 68, 68, 0.4)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Square size={14} fill="#ffffff" />
          </button>
        ) : (
          <div className="chat-input-controls-group" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <div className="chat-loop-wrapper" style={{ display: 'flex', alignItems: 'center' }}>
              <select
                className="chat-loop-max-select"
                value={loopMaxIterations}
                onChange={e => setLoopMaxIterations(parseInt(e.target.value))}
                disabled={loopActive}
                style={{
                  background: '#0e1016',
                  border: '1px solid #1e2030',
                  borderRadius: '4px',
                  color: '#8b8fa3',
                  fontSize: '0.62rem',
                  padding: '4px',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                <option value={1}>1x (Risposta Singola)</option>
                <option value={3}>3x Loop</option>
                <option value={5}>5x Loop</option>
                <option value={10}>10x Loop</option>
                <option value={50}>50x Loop</option>
                <option value={100}>100x Loop</option>
                <option value={999}>∞ Continuo (fino a completamento)</option>
              </select>
            </div>
            
            <button 
              className="chat-send-btn" 
              onClick={onSend} 
              disabled={!input.trim()} 
              title={loopMaxIterations > 1 ? `Invia in Loop (max ${loopMaxIterations === 999 ? '∞' : loopMaxIterations} iterazioni)` : 'Invia richiesta'}
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Send size={16} />
              {loopMaxIterations > 1 && (
                <span className="chat-loop-badge" style={{
                  position: 'absolute',
                  top: '-4px',
                  right: '-4px',
                  background: '#00d2ff',
                  color: '#000',
                  fontSize: '0.5rem',
                  fontWeight: '700',
                  padding: '1px 3px',
                  borderRadius: '3px',
                  lineHeight: 1
                }}>
                  {loopMaxIterations === 999 ? '∞' : loopMaxIterations}
                </span>
              )}
            </button>
          </div>
        )}
      </div>
      {children}
    </div>
  );
}