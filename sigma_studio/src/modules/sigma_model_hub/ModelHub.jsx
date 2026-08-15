import React, { useState, useEffect, useCallback } from 'react';
import {
  DownloadCloud, Search, HardDrive, Zap, Shield, Key,
  CheckCircle2, RefreshCw, Folder, Layers, Activity, Sparkles, ExternalLink
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import HfBrowser from './HfBrowser';
import DownloadManager from './DownloadManager';
import LocalInventory from './LocalInventory';
import SigmaDeployModal from './SigmaDeployModal';
import EngineOptimizer from './EngineOptimizer';
import './styles/model-hub.css';


export default function ModelHub({ addToast }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [activeTab, setActiveTab] = useState('browse'); // 'browse' | 'downloads' | 'inventory' | 'settings'
  const [deployTargetModel, setDeployTargetModel] = useState(null);

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
  }, [fetchConfig, fetchEngineStatus]);

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
                Hugging Face API OK
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
      <div style={{ display: 'flex', gap: '8px', borderBottom: subBorder, paddingBottom: '8px' }}>
        {[
          { id: 'optimizer', label: '⚡ SigmaEngine Kernel & Ottimizzatore' },
          { id: 'browse', label: '🔍 Esplora Hugging Face' },
          { id: 'downloads', label: '📥 Download Attivi & Coda' },
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
              transition: 'all 0.15s ease'
            }}
          >
            {tab.label}
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
          onDownloadStarted={() => {
            if (addToast) addToast('Download aggiunto alla coda.', 'info');
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary, display: 'block', marginBottom: '6px' }}>
                Cartella di Salvataggio Modelli (Storage SSD)
              </label>
              <input
                type="text"
                value={config.models_dir}
                onChange={e => setConfig({ ...config, models_dir: e.target.value })}
                placeholder="es. C:\Users\Sigma\Desktop\Sigma_Studio\data\models o D:\AI_Models"
                style={{
                  width: '100%', padding: '9px 12px', borderRadius: '8px',
                  background: subBg, border: subBorder,
                  color: textPrimary, fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary, display: 'block', marginBottom: '6px' }}>
                Hugging Face User Access Token (Opzionale, per modelli gated come Llama 3 o Gemma)
              </label>
              <input
                type="password"
                value={config.hf_token}
                onChange={e => setConfig({ ...config, hf_token: e.target.value })}
                placeholder="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                style={{
                  width: '100%', padding: '9px 12px', borderRadius: '8px',
                  background: subBg, border: subBorder,
                  color: textPrimary, fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                id="autodeploy"
                checked={config.auto_deploy_on_download}
                onChange={e => setConfig({ ...config, auto_deploy_on_download: e.target.checked })}
              />
              <label htmlFor="autodeploy" style={{ fontSize: '0.76rem', color: textPrimary, cursor: 'pointer' }}>
                Suggerisci automaticamente l'avvio in <strong>⚡ SigmaEngine</strong> al termine del download
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px' }}>
              <button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                style={{
                  padding: '8px 18px', borderRadius: '8px',
                  border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)',
                  color: '#ffffff', fontSize: '0.78rem', fontWeight: 800, cursor: 'pointer'
                }}
              >
                {savingConfig ? 'Salvataggio...' : 'Salva Impostazioni'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. SIGMAENGINE INSTANT DEPLOY MODAL */}
      {deployTargetModel && (
        <SigmaDeployModal
          model={deployTargetModel}
          isLight={isLight}
          addToast={addToast}
          onClose={() => setDeployTargetModel(null)}
          onDeployed={() => {
            fetchEngineStatus();
          }}
        />
      )}
    </div>
  );
}
