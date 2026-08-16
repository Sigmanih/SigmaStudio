import React, { useState, useEffect, useCallback } from 'react';
import {
  DownloadCloud, Search, HardDrive, Zap, Shield, Key,
  CheckCircle2, RefreshCw, Folder, Layers, Activity, Sparkles, ExternalLink,
  ArrowRight, XCircle
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import HfBrowser from './HfBrowser';
import DownloadManager from './DownloadManager';
import LocalInventory from './LocalInventory';
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
        if (addToast) addToast('⚡ Configurazione Model Hub salvata con successo!', 'success');
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
          {
            id: 'downloads',
            label: totalActiveTasksCount > 0
              ? `📥 Download Attivi (${currentRunningTask ? `${currentRunningTask.progress_pct}%` : totalActiveTasksCount})`
              : '📥 Download Attivi & Coda'
          },
          { id: 'inventory', label: '💾 Modelli Locali & Storage' },
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

      {activeTab === 'downloads' && (
        <DownloadManager
          isLight={isLight}
          addToast={addToast}
          onDeployRequested={m => setDeployTargetModel(m)}
        />
      )}

      {activeTab === 'inventory' && (
        <LocalInventory
          isLight={isLight}
          addToast={addToast}
          onDeployRequested={m => setDeployTargetModel(m)}
        />
      )}

      {activeTab === 'settings' && (
        <div style={{
          padding: '24px', borderRadius: '16px',
          background: cardBg, border: cardBorder, boxShadow: cardShadow,
          display: 'flex', flexDirection: 'column', gap: '18px', maxWidth: '640px'
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
              Configurazione Download & Storage Modelli
            </h2>
            <p style={{ margin: '3px 0 0 0', fontSize: '0.74rem', color: textMuted }}>
              Imposta la cartella locale di salvataggio e il tuo Hugging Face API Token personale.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Folder size={14} color="#ffb86c" /> Cartella Download Modelli:
            </label>
            <input
              type="text"
              value={config.models_dir || ''}
              onChange={e => setConfig({ ...config, models_dir: e.target.value })}
              placeholder="es. data/models (Default)"
              style={{
                padding: '9px 12px', borderRadius: '10px',
                background: subBg, border: subBorder,
                color: textPrimary, fontSize: '0.8rem', outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Key size={14} color="#00d2ff" /> Hugging Face Access Token (Opzionale per modelli gated/Llama):
            </label>
            <input
              type="password"
              value={config.hf_token || ''}
              onChange={e => setConfig({ ...config, hf_token: e.target.value })}
              placeholder="hf_..."
              style={{
                padding: '9px 12px', borderRadius: '10px',
                background: subBg, border: subBorder,
                color: textPrimary, fontSize: '0.8rem', outline: 'none'
              }}
            />
          </div>

          <button
            onClick={handleSaveConfig}
            disabled={savingConfig}
            style={{
              padding: '10px 20px', borderRadius: '10px',
              border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)',
              color: '#ffffff', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
              width: 'fit-content', boxShadow: '0 4px 15px rgba(255, 184, 108, 0.3)'
            }}
          >
            {savingConfig ? <Activity className="mh-spin" size={14} /> : <CheckCircle2 size={14} />}
            {savingConfig ? 'Salvataggio...' : 'Salva Impostazioni'}
          </button>
        </div>
      )}

      {/* 4. SLEEK LIVE FLOATING DOWNLOAD HUD BANNER (Visible across any tab when downloading or interrupted) */}
      {currentRunningTask && activeTab !== 'downloads' && (
        <div
          onClick={() => setActiveTab('downloads')}
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
                setActiveTab('downloads');
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

      {!currentRunningTask && lastFailedTask && activeTab !== 'downloads' && (
        <div
          onClick={() => setActiveTab('downloads')}
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
                  Download Interrotto: {lastFailedTask.model_id}
                </span>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#ef4444', fontFamily: 'monospace' }}>
                  {lastFailedTask.progress_pct}%
                </span>
              </div>
              <div style={{ fontSize: '0.68rem', color: '#10b981', marginTop: '2px', fontWeight: 700 }}>
                💾 {formatMb(lastFailedTask.downloaded_mb)} già salvati su disco (riprende da dove si era fermato)
              </div>
            </div>
          </div>


          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
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
            if (openTab) {
              openTab({ id: 'chat', title: 'Chat', type: 'chat' });
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

