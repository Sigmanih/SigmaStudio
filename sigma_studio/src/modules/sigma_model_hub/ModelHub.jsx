import React, { useState, useEffect, useCallback } from 'react';
import {
  DownloadCloud, Search, HardDrive, Zap, Shield, Key,
  CheckCircle2, RefreshCw, Folder, Layers, Activity, Sparkles, ExternalLink,
  ArrowRight, XCircle, RotateCcw, Eye, EyeOff, ShieldCheck, AlertTriangle, Check
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import HfBrowser from './HfBrowser';
import LocalInventory from './LocalInventory';
import GgufConverter from './GgufConverter';
import DirectoryPicker from './DirectoryPicker';
import SigmaDeployModal from './SigmaDeployModal';
import EngineOptimizer from './EngineOptimizer';
import './styles/model-hub.css';


export default function ModelHub({ addToast, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [activeTab, setActiveTab] = useState('browse'); // 'optimizer' | 'browse' | 'downloads' | 'inventory' | 'settings'
  const [deployTargetModel, setDeployTargetModel] = useState(null);


  // Active Downloads Tracking
  const [activeDownloads, setActiveDownloads] = useState([]);

  // Hub Settings state
  const [config, setConfig] = useState({
    models_dir: '',
    hf_token: '',
    auto_deploy_on_download: true,
    preferred_quantization: 'Q4_K_M'
  });
  const [savingConfig, setSavingConfig] = useState(false);
  const [pickingDir, setPickingDir] = useState(false);

  // Token testing and visibility state
  const [showToken, setShowToken] = useState(false);
  const [testingToken, setTestingToken] = useState(false);
  const [tokenTestResult, setTokenTestResult] = useState(null);

  // Engine status
  const [engineStatus, setEngineStatus] = useState(null);

  const fetchDownloads = useCallback(async () => {
    try {
      const res = await fetch('/api/models/hf/downloads');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setActiveDownloads(json.downloads || []);
        }
      }
    } catch (e) {
      // silent background poll
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/models/config');
      if (res.ok) {
        const json = await res.json();
        if (json.success) setConfig(json.config || {});
      }
    } catch (e) {
      console.error('Error fetching Model Hub config:', e);
    }
  }, []);

  const fetchEngineStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/status');
      if (res.ok) {
        const json = await res.json();
        setEngineStatus(json);
      }
    } catch (e) {
      console.error('Error fetching engine status:', e);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchEngineStatus();
    fetchDownloads();
    const interval = setInterval(fetchDownloads, 1500);
    return () => clearInterval(interval);
  }, [fetchConfig, fetchEngineStatus, fetchDownloads]);

  const handleTestToken = async () => {
    const token = (config.hf_token || '').trim();
    if (!token) {
      if (addToast) addToast('⚠️ Inserisci prima il token Hugging Face da verificare.', 'warning');
      return;
    }
    setTestingToken(true);
    setTokenTestResult(null);
    try {
      const res = await fetch('/api/models/hf/token/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hf_token: token })
      });
      const json = await res.json();
      setTokenTestResult(json);
      if (json.valid) {
        if (addToast) addToast(`✅ ${json.message || 'Token valido!'}`, 'success', 5000);
      } else {
        if (addToast) addToast(json.error || 'Token non valido.', 'error', 6000);
      }
    } catch (e) {
      setTokenTestResult({ valid: false, error: e.message });
      if (addToast) addToast(`Errore verifica token: ${e.message}`, 'error');
    } finally {
      setTestingToken(false);
    }
  };

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⚡ Configurazione e Token salvati con successo!', 'success');
        fetchDownloads();
      }
    } catch (e) {
      if (addToast) addToast(`Errore salvataggio: ${e.message}`, 'error');
    } finally {
      setSavingConfig(false);
    }
  };

  const cardBg = isLight ? '#fffdf9' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(0,0,0,0.05)' : '0 12px 36px rgba(0, 0, 0, 0.45)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const handleRetryTask = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🚀 Ripresa del download in corso dai file salvati su disco!`, 'success');
        fetchDownloads();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };

  const formatMb = (mb) => {
    if (!mb || mb <= 0) return '0 MB';
    if (mb >= 1024 * 1024) return `${(mb / (1024 * 1024)).toFixed(2)} TB`;
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  // Find currently downloading task or last interrupted task if any
  const currentRunningTask = activeDownloads.find(d => d.status === 'downloading' || d.status === 'queued');
  const lastFailedTask = activeDownloads.find(d => d.status === 'failed' || d.status === 'cancelled');
  const totalActiveTasksCount = activeDownloads.filter(d => d.status === 'downloading' || d.status === 'queued').length;



  return (
    <div className="model-hub-container" style={{ backgroundColor: isLight ? '#f4efe4' : '#07090e', color: textPrimary }}>
      {/* 1. FUTURISTIC HEADER */}
      <div style={{
        padding: '16px 20px', borderRadius: '16px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf6ec 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(20, 26, 42, 0.85) 100%)',
        border: cardBorder, boxShadow: cardShadow,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '12px',
            background: 'radial-gradient(circle at 30% 30%, rgba(255, 184, 108, 0.25), rgba(255, 184, 108, 0.05))',
            border: '1px solid rgba(255, 184, 108, 0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px rgba(255, 184, 108, 0.2)'
          }}>
            <DownloadCloud size={24} color="#ffb86c" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.3px', color: textPrimary }}>
                Model Hub & <span style={{ color: '#ffb86c' }}>Hugging Face Downloader</span>
              </h1>
              <span style={{
                fontSize: '0.66rem', padding: '2px 8px', borderRadius: '12px',
                background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', border: '1px solid rgba(255, 184, 108, 0.3)',
                fontWeight: 800
              }}>
                Hugging Face API Live
              </span>
            </div>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.75rem', color: textMuted }}>
              Scarica modelli GGUF e Safetensors da Hugging Face e avviali direttamente con <strong>⚡ SigmaEngine</strong>.
            </p>
          </div>
        </div>

        {/* Engine Live Status Pill */}
        <div style={{
          padding: '8px 14px', borderRadius: '10px',
          background: subBg, border: subBorder,
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <Zap size={15} color="#00d2ff" />
          <div style={{ fontSize: '0.72rem' }}>
            <div style={{ color: textMuted, fontWeight: 700 }}>MOTORE ATTIVO</div>
            <div style={{ color: '#00d2ff', fontWeight: 800 }}>
              {engineStatus?.loaded_model || 'Nessun modello caricato (Standby)'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. NAVIGATION TABS */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: subBorder, paddingBottom: '8px', flexWrap: 'wrap' }}>
        {[
          { id: 'optimizer', label: '⚡ SigmaEngine Kernel & Ottimizzatore' },
          { id: 'browse', label: '🔍 Esplora Hugging Face' },
          { id: 'convert', label: '📦 Conversione GGUF' },
          {
            id: 'inventory',
            label: totalActiveTasksCount > 0
              ? `💾 Modelli Locali (${currentRunningTask ? `${currentRunningTask.progress_pct}%` : totalActiveTasksCount} in download)`
              : '💾 Modelli Locali & Storage'
          },
          { id: 'settings', label: '⚙️ Directory & HF Token' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 16px', borderRadius: '10px',
              border: activeTab === tab.id ? '1px solid #ffb86c' : '1px solid transparent',
              background: activeTab === tab.id ? (isLight ? '#ffffff' : 'rgba(255, 184, 108, 0.15)') : subBg,
              color: activeTab === tab.id ? (isLight ? '#ea580c' : '#ffb86c') : textMuted,
              fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer',
              transition: 'all 0.15s ease', display: 'flex', alignItems: 'center', gap: '6px'
            }}
          >
            {tab.label}
            {tab.id === 'downloads' && currentRunningTask && (
              <span className="mh-spin" style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', border: '2px solid #00d2ff', borderTopColor: 'transparent' }} />
            )}
          </button>
        ))}
      </div>

      {/* 3. TAB CONTENT VIEWS */}
      {activeTab === 'optimizer' && (
        <EngineOptimizer
          isLight={isLight}
          addToast={addToast}
        />
      )}

      {activeTab === 'browse' && (
        <HfBrowser
          isLight={isLight}
          addToast={addToast}
          activeDownloads={activeDownloads}
          onDownloadStarted={() => {
            fetchDownloads();
          }}
        />
      )}

      {activeTab === 'convert' && (
        <GgufConverter
          isLight={isLight}
          addToast={addToast}
        />
      )}

      {activeTab === 'inventory' && (
        <LocalInventory
          isLight={isLight}
          addToast={addToast}
          activeDownloads={activeDownloads}
          onDeployRequested={m => setDeployTargetModel(m)}
        />
      )}

      {activeTab === 'settings' && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '720px'
        }}>
          {/* SEZIONE 1: HUGGING FACE TOKEN & AUTENTICAZIONE */}
          <div style={{
            padding: '24px', borderRadius: '16px',
            background: cardBg, border: cardBorder, boxShadow: cardShadow,
            display: 'flex', flexDirection: 'column', gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(0, 210, 255, 0.2))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Key size={20} color="#00d2ff" />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                    Hugging Face Access Token
                  </h2>
                  <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
                    Download ultra-veloci (5-50 MB/s) e accesso ai modelli protetti / Gated (Llama 3, Gemma, DeepSeek)
                  </div>
                </div>
              </div>
              <a
                href="https://huggingface.co/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: '0.72rem', color: '#00d2ff', textDecoration: 'none',
                  display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 700,
                  padding: '6px 12px', borderRadius: '8px', background: subBg, border: subBorder
                }}
              >
                Genera Token <ExternalLink size={12} />
              </a>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary }}>
                Token Personale Hugging Face (hf_...):
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={config.hf_token || ''}
                    onChange={e => {
                      setConfig({ ...config, hf_token: e.target.value });
                      setTokenTestResult(null);
                    }}
                    placeholder="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    style={{
                      width: '100%', padding: '10px 42px 10px 14px', borderRadius: '10px',
                      background: subBg, border: subBorder,
                      color: textPrimary, fontSize: '0.82rem', fontFamily: 'monospace', outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    style={{
                      position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', color: textMuted, cursor: 'pointer',
                      padding: '4px', display: 'flex', alignItems: 'center'
                    }}
                  >
                    {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                <button
                  onClick={handleTestToken}
                  disabled={testingToken || !config.hf_token}
                  style={{
                    padding: '10px 16px', borderRadius: '10px', border: subBorder,
                    background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(0, 210, 255, 0.2))',
                    color: textPrimary, fontSize: '0.78rem', fontWeight: 800, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                  }}
                >
                  {testingToken ? <Activity className="mh-spin" size={14} color="#00d2ff" /> : <ShieldCheck size={14} color="#00d2ff" />}
                  {testingToken ? 'Verifica...' : 'Verifica Token'}
                </button>
              </div>
            </div>

            {/* Test result alert */}
            {tokenTestResult && (
              <div style={{
                padding: '12px 16px', borderRadius: '10px',
                background: tokenTestResult.valid ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                border: tokenTestResult.valid ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex', alignItems: 'flex-start', gap: '10px'
              }}>
                {tokenTestResult.valid ? (
                  <CheckCircle2 size={18} color="#10b981" style={{ flexShrink: 0, marginTop: '2px' }} />
                ) : (
                  <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0, marginTop: '2px' }} />
                )}
                <div style={{ fontSize: '0.76rem', color: tokenTestResult.valid ? '#10b981' : '#ef4444' }}>
                  <div style={{ fontWeight: 800 }}>
                    {tokenTestResult.valid ? 'Autenticazione Riuscita' : 'Autenticazione Fallita'}
                  </div>
                  <div style={{ marginTop: '2px', color: textPrimary, fontSize: '0.72rem' }}>
                    {tokenTestResult.message || tokenTestResult.error}
                  </div>
                  {tokenTestResult.valid && tokenTestResult.orgs && tokenTestResult.orgs.length > 0 && (
                    <div style={{ marginTop: '4px', fontSize: '0.68rem', color: textMuted }}>
                      Organizzazioni associate: {tokenTestResult.orgs.join(', ')}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* SEZIONE 2: DIRECTORY STORAGE MODELLI */}
          <div style={{
            padding: '24px', borderRadius: '16px',
            background: cardBg, border: cardBorder, boxShadow: cardShadow,
            display: 'flex', flexDirection: 'column', gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '12px' }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(255, 184, 108, 0.2), rgba(234, 88, 12, 0.2))',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Folder size={20} color="#ffb86c" />
              </div>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                  Cartella di Salvataggio Modelli
                </h2>
                <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
                  Directory su disco dove vengono archiviati i pesi GGUF e Safetensors scaricati
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary }}>
                Percorso Directory:
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={config.models_dir || ''}
                  onChange={e => setConfig({ ...config, models_dir: e.target.value })}
                  placeholder="es. data/models (Default)"
                  style={{
                    flex: 1, padding: '10px 14px', borderRadius: '10px',
                    background: subBg, border: subBorder,
                    color: textPrimary, fontSize: '0.82rem', fontFamily: 'monospace', outline: 'none'
                  }}
                />
                <button
                  onClick={() => setPickingDir(true)}
                  title="Sfoglia le cartelle del computer"
                  style={{
                    padding: '10px 16px', borderRadius: '10px', border: subBorder,
                    background: subBg, color: textPrimary,
                    fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                >
                  Sfoglia...
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.06)', flexWrap: 'wrap', gap: '10px' }}>
              <button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                style={{
                  padding: '11px 24px', borderRadius: '10px',
                  border: 'none', background: 'linear-gradient(135deg, #10b981, #00d2ff)',
                  color: '#ffffff', fontSize: '0.84rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  boxShadow: '0 4px 20px rgba(16, 185, 129, 0.3)'
                }}
              >
                {savingConfig ? <Activity className="mh-spin" size={16} /> : <CheckCircle2 size={16} />}
                {savingConfig ? 'Salvataggio...' : 'Salva Impostazioni'}
              </button>

              {lastFailedTask && (
                <button
                  onClick={() => {
                    handleSaveConfig().then(() => handleRetryTask(lastFailedTask.task_id));
                  }}
                  style={{
                    padding: '11px 20px', borderRadius: '10px',
                    border: '1px solid rgba(255, 184, 108, 0.4)',
                    background: 'rgba(255, 184, 108, 0.12)',
                    color: '#ffb86c', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <RotateCcw size={14} /> Salva e Riprendi Download Interrotto
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 4. SLEEK LIVE FLOATING DOWNLOAD HUD BANNER (Visible across any tab when downloading or interrupted) */}
      {currentRunningTask && activeTab !== 'inventory' && (
        <div
          onClick={() => setActiveTab('inventory')}
          style={{
            position: 'sticky', bottom: '16px', zIndex: 100,
            padding: '12px 18px', borderRadius: '14px',
            background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
            backdropFilter: 'blur(12px)',
            border: '1.5px solid #00d2ff',
            boxShadow: '0 10px 30px rgba(0, 210, 255, 0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px',
            cursor: 'pointer', transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
            <Activity className="mh-spin" size={20} color="#00d2ff" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Download in corso: {currentRunningTask.model_id}
                </span>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff', fontFamily: 'monospace' }}>
                  {currentRunningTask.progress_pct}%
                </span>
              </div>
              <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                {currentRunningTask.is_repo_download
                  ? `File ${currentRunningTask.current_file_idx}/${currentRunningTask.total_files} (${currentRunningTask.current_file_name}) • ${formatMb(currentRunningTask.downloaded_mb)} / ${currentRunningTask.total_mb ? formatMb(currentRunningTask.total_mb) : '...'}`
                  : `${formatMb(currentRunningTask.downloaded_mb)} / ${currentRunningTask.total_mb ? formatMb(currentRunningTask.total_mb) : '...'}`}
                {' • '}
                <span style={{ color: '#ffb86c', fontWeight: 700 }}>
                  {currentRunningTask.speed_mbps} MB/s
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab('inventory');
              }}
              style={{
                padding: '6px 12px', borderRadius: '8px', border: 'none',
                background: 'linear-gradient(135deg, #00d2ff, #0090ff)', color: '#ffffff',
                fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '4px'
              }}
            >
              Apri Dettagli <ArrowRight size={12} />
            </button>
          </div>
        </div>
      )}

      {!currentRunningTask && lastFailedTask && activeTab !== 'inventory' && (
        <div
          onClick={() => setActiveTab('inventory')}
          style={{
            position: 'sticky', bottom: '16px', zIndex: 100,
            padding: '12px 18px', borderRadius: '14px',
            background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
            backdropFilter: 'blur(12px)',
            border: '1.5px solid rgba(239, 68, 68, 0.4)',
            boxShadow: '0 10px 30px rgba(239, 68, 68, 0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px',
            cursor: 'pointer', transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
            }}>
              <RotateCcw size={16} color="#ef4444" />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {lastFailedTask.error_message && (lastFailedTask.error_message.includes('401') || lastFailedTask.error_message.includes('403') || lastFailedTask.error_message.includes('Autenticazione'))
                    ? `🔒 Token HF Richiesto: ${lastFailedTask.model_id}`
                    : `Download Interrotto: ${lastFailedTask.model_id}`}
                </span>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#ef4444', fontFamily: 'monospace' }}>
                  {lastFailedTask.progress_pct}%
                </span>
              </div>
              <div style={{ fontSize: '0.68rem', color: lastFailedTask.error_message && (lastFailedTask.error_message.includes('401') || lastFailedTask.error_message.includes('403') || lastFailedTask.error_message.includes('Autenticazione')) ? '#f59e0b' : '#10b981', marginTop: '2px', fontWeight: 700 }}>
                {lastFailedTask.error_message && (lastFailedTask.error_message.includes('401') || lastFailedTask.error_message.includes('403') || lastFailedTask.error_message.includes('Autenticazione'))
                  ? '⚠️ Modello protetto / Gated: Inserisci il tuo Access Token HF nelle Impostazioni'
                  : `💾 ${formatMb(lastFailedTask.downloaded_mb)} già salvati su disco (riprende da dove si era fermato)`}
              </div>
            </div>
          </div>


          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            {lastFailedTask.error_message && (lastFailedTask.error_message.includes('401') || lastFailedTask.error_message.includes('403') || lastFailedTask.error_message.includes('Autenticazione')) && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveTab('settings');
                }}
                style={{
                  padding: '6px 14px', borderRadius: '8px', border: 'none',
                  background: 'linear-gradient(135deg, #f59e0b, #ea580c)', color: '#ffffff',
                  fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '4px', boxShadow: '0 0 10px rgba(245, 158, 11, 0.3)'
                }}
              >
                ⚙️ Inserisci Token HF
              </button>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleRetryTask(lastFailedTask.task_id);
              }}
              style={{
                padding: '6px 14px', borderRadius: '8px', border: 'none',
                background: 'linear-gradient(135deg, #10b981, #00d2ff)', color: '#ffffff',
                fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '4px', boxShadow: '0 0 10px rgba(16, 185, 129, 0.3)'
              }}
            >
              <RotateCcw size={12} /> Riprendi Ora
            </button>
          </div>
        </div>
      )}


      {pickingDir && (
        <DirectoryPicker
          initialPath={config.models_dir}
          isLight={isLight}
          onSelect={dir => setConfig(c => ({ ...c, models_dir: dir }))}
          onClose={() => setPickingDir(false)}
        />
      )}

      {/* 5. DEPLOY TO SIGMA ENGINE MODAL */}
      {deployTargetModel && (
        <SigmaDeployModal
          model={deployTargetModel}
          isLight={isLight}
          addToast={addToast}
          onClose={() => setDeployTargetModel(null)}
          onSuccess={() => {
            fetchEngineStatus();
          }}
          onNavigateToChat={() => {
            // The chat panel must be told which model was just deployed, and
            // openTab takes (item, type): passing a single object left the tab
            // with no type at all, which rendered an empty pane.
            try {
              window.dispatchEvent(new CustomEvent('ai-config-updated'));
            } catch (e) { /* the chat refreshes on its own next mount */ }

            if (openTab) {
              openTab({ name: 'Chat' }, 'chat');
            } else {
              try {
                window.dispatchEvent(new CustomEvent('open_tab', { detail: { type: 'chat' } }));
              } catch (e) {}
            }
          }}
        />
      )}
    </div>
  );
}

