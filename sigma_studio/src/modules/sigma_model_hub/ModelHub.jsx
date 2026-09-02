import React, { useState, useEffect, useCallback } from 'react';
import {
  DownloadCloud, Search, HardDrive, Zap, Shield, Key,
  CheckCircle2, RefreshCw, Folder, FolderOpen, Layers, Activity, Sparkles, ExternalLink,
  ArrowRight, XCircle, RotateCcw, Eye, EyeOff, ShieldCheck, AlertTriangle, Check,
  Plus, X, Tag, FolderPlus, Link2, Copy, FileText, Package, Settings
} from 'lucide-react';

import { useApp } from '../../contexts/AppContext';
import HfBrowser from './HfBrowser';
import LocalInventory from './LocalInventory';
import GgufConverter from './GgufConverter';
import DirectoryPicker from './DirectoryPicker';
import SigmaDeployModal from './SigmaDeployModal';
import './styles/model-hub.css';


// Where an active token was resolved from. Only a token stored in Sigma's own
// config is editable here: one coming from the environment or from a
// `huggingface-cli login` wins over whatever is typed in, and saying so is the
// difference between "the field is empty" and "the field is irrelevant".
const HF_TOKEN_SOURCE_LABELS = {
  input: 'Inserito manualmente',
  env: "Variabile d'ambiente",
  config: 'Configurazione Sigma',
  cli_cache: 'Login huggingface-cli',
};

// Le fasi di una conversione, come le chiama il backend.
const CONVERSION_STAGE_LABELS = {
  queued: 'In coda',
  converting: 'Conversione in GGUF',
  quantizing: 'Quantizzazione',
};

const DEFAULT_OFFICIAL_PUBLISHERS = [
  'sigmanih', 'google', 'qwen', 'meta-llama', 'deepseek-ai', 'mistralai',
  'microsoft', 'thudm', 'zai-org', 'zai', '01-ai', 'nvidia', 'stabilityai',
  'black-forest-labs', 'allenai', 'apple', 'openai', 'tiiuae', 'bytedance',
  'internlm'
];


const TAB_METADATA = {
  browse: {
    title: 'Esplora Hugging Face',
    icon: Search,
    badge: 'ESPLORA',
    desc: 'Cerca e scarica modelli GGUF e Safetensors da Hugging Face per SigmaEngine.'
  },
  inventory: {
    title: 'Modelli Locali & Storage',
    icon: HardDrive,
    badge: 'STORAGE',
    desc: 'Gestione pesi locali, storage su disco, benchmark e deploy su SigmaEngine.'
  },
  converter: {
    title: 'Convertitore GGUF & Quantizzazione',
    icon: Zap,
    badge: 'CONVERTITORE',
    desc: 'Converti checkpoint Hugging Face in GGUF e applica la quantizzazione desiderata.'
  },
  settings: {
    title: 'Impostazioni & HF Token',
    icon: Settings,
    badge: 'CONFIG',
    desc: 'Cartelle di salvataggio modelli, token Hugging Face e parametri ufficiali.'
  }
};

export default function ModelHub({ addToast: addToastProp, openTab }) {
  // Workspace monta l'hub passando uno stub vuoto come addToast, quindi ogni
  // notifica finiva nel nulla: errori di conversione compresi. Quella vera sta
  // nel contesto, ed e' la stessa che App rende a schermo.
  const { theme, addToast: appAddToast } = useApp();
  const addToast = appAddToast || addToastProp;
  const isLight = theme === 'light';

  const [activeTab, setActiveTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_model_hub_active_subtab') || 'browse';
    } catch {
      return 'browse';
    }
  }); // 'browse' | 'inventory' | 'converter' | 'settings'
  const currentTabMeta = TAB_METADATA[activeTab] || TAB_METADATA.browse;
  const TabIcon = currentTabMeta.icon;
  const [deployTargetModel, setDeployTargetModel] = useState(null);
  const [preselectedConvertModel, setPreselectedConvertModel] = useState('');

  // Support external sub-tab switching (e.g. from the main application sidebar)
  useEffect(() => {
    const handleSetTab = (e) => {
      if (e?.detail && ['browse', 'inventory', 'converter', 'settings'].includes(e.detail)) {
        setActiveTab(e.detail);
      }
    };
    window.addEventListener('sigma-model-hub-set-tab', handleSetTab);
    return () => window.removeEventListener('sigma-model-hub-set-tab', handleSetTab);
  }, []);

  // Notify sidebar and persist to localStorage when activeTab changes
  useEffect(() => {
    try {
      localStorage.setItem('sigma_model_hub_active_subtab', activeTab);
      window.dispatchEvent(new CustomEvent('sigma-model-hub-tab-changed', { detail: activeTab }));
    } catch (e) {}
  }, [activeTab]);


  // Active Downloads Tracking
  const [activeDownloads, setActiveDownloads] = useState([]);

  // Active Conversions Tracking. Una quantizzazione gira per minuti sul server
  // e non si ferma cambiando scheda: il polling sta qui, non nel convertitore,
  // cosi' l'avanzamento resta visibile da qualunque scheda dell'hub.
  const [conversionJobs, setConversionJobs] = useState([]);

  // Hub Settings state
  const [config, setConfig] = useState({
    models_dir: '',
    extra_models_dirs: [],
    hf_token: '',
    auto_deploy_on_download: true,
    preferred_quantization: 'Q4_K_M',
    official_publishers: DEFAULT_OFFICIAL_PUBLISHERS
  });
  const [newPublisherInput, setNewPublisherInput] = useState('');
  const [newExtraDirInput, setNewExtraDirInput] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);
  const [pickingDir, setPickingDir] = useState(false);
  const [pickingExtraDir, setPickingExtraDir] = useState(false);

  // Local Model Import state
  const [importSourcePath, setImportSourcePath] = useState('');
  const [importMode, setImportMode] = useState('add_path'); // 'add_path' | 'copy' | 'symlink'
  const [importingModel, setImportingModel] = useState(false);
  const [pickingImportItem, setPickingImportItem] = useState(false);


  // Token and connection testing state
  const [showToken, setShowToken] = useState(false);
  const [testingToken, setTestingToken] = useState(false);
  const [tokenTestResult, setTokenTestResult] = useState(null);
  const [testingConn, setTestingConn] = useState(false);
  const [connResult, setConnResult] = useState(null);
  const [savingToken, setSavingToken] = useState(false);
  const [hfTokenStatus, setHfTokenStatus] = useState({ has_token: false, source: null, detail: null });

  // Engine status
  const [engineStatus, setEngineStatus] = useState(null);
  const [localModels, setLocalModels] = useState([]);

  const fetchLocalModels = useCallback(async () => {
    try {
      const res = await fetch('/api/models/local/list');
      if (res.ok) {
        const json = await res.json();
        if (json.success && Array.isArray(json.models)) {
          setLocalModels(json.models);
        }
      }
    } catch (e) {
      console.debug('Error fetching local models:', e);
    }
  }, []);

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

  const fetchConversionJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/models/convert/jobs');
      if (res.ok) {
        const json = await res.json();
        if (json.success) setConversionJobs(json.jobs || []);
      }
    } catch {
      // silent background poll: il tick successivo riprova
    }
  }, []);

  const activeConversion = conversionJobs.find(
    j => ['queued', 'converting', 'quantizing'].includes(j.status)
  );
  const conversionRunning = !!activeConversion;

  // Due cadenze: fitta mentre converte, rada altrimenti, che serve solo ad
  // accorgersi di un job avviato altrove o gia' in corso al mount.
  useEffect(() => {
    fetchConversionJobs();
    const interval = setInterval(fetchConversionJobs, conversionRunning ? 2000 : 15000);
    return () => clearInterval(interval);
  }, [fetchConversionJobs, conversionRunning]);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/models/config');
      if (res.ok) {
        const json = await res.json();
        if (json.success && json.config) {
          setConfig(prev => ({
            ...prev,
            ...json.config,
            hf_token: json.config.hf_token || prev.hf_token || ''
          }));
          setHfTokenStatus({
            has_token: !!json.hf_has_token,
            source: json.hf_token_source || null,
            detail: json.hf_token_source_detail || null,
          });
          return json;
        }
      }
    } catch (e) {
      console.error('Error fetching Model Hub config:', e);
    }
    return null;
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
    fetchLocalModels();
    const interval = setInterval(fetchDownloads, 1500);
    return () => clearInterval(interval);
  }, [fetchConfig, fetchEngineStatus, fetchDownloads, fetchLocalModels]);

  // Anything that used to send the user to Impostazioni for the token now sends
  // them here instead. The flag covers the tab being opened by that request;
  // the event covers the hub already being mounted on another tab.
  useEffect(() => {
    if (typeof window !== 'undefined' && window.__sigmaOpenHfTokenSettings) {
      window.__sigmaOpenHfTokenSettings = false;
      setActiveTab('settings');
    }
    const onRequest = () => setActiveTab('settings');
    window.addEventListener('sigma_open_hf_token_settings', onRequest);
    return () => window.removeEventListener('sigma_open_hf_token_settings', onRequest);
  }, []);

  const handleTestConnection = async () => {
    setTestingConn(true);
    setConnResult(null);
    try {
      const res = await fetch('/api/models/hf/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hf_token: (config.hf_token || '').trim() })
      });
      const json = await res.json();
      setConnResult(json);
      if (json.connected) {
        if (json.token_valid) {
          if (addToast) addToast(`⚡ ${json.message}`, 'success', 6000);
        } else {
          if (addToast) addToast(`🌐 Hugging Face raggiungibile (${json.latency_ms}ms), ma: ${json.error || 'Nessun token valido'}`, 'warning', 6000);
        }
      } else {
        if (addToast) addToast(`❌ ${json.error || 'Hugging Face non raggiungibile'}`, 'error', 6000);
      }
    } catch (e) {
      setConnResult({ connected: false, error: e.message });
      if (addToast) addToast(`Errore test connessione: ${e.message}`, 'error');
    } finally {
      setTestingConn(false);
    }
  };

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

  // The token is saved on its own, without touching the models directory, so
  // fixing a rejected download never depends on the directory field being valid.
  const persistToken = async (token, { successMessage }) => {
    setSavingToken(true);
    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hf_token: token })
      });
      const json = await res.json();
      if (!json.success) {
        if (addToast) addToast(`❌ Errore salvataggio token: ${json.error || 'Errore'}`, 'error');
        return false;
      }
      setHfTokenStatus({
        has_token: !!json.hf_has_token,
        source: json.hf_token_source || null,
        detail: json.hf_token_source_detail || null,
      });
      if (addToast) addToast(successMessage, 'success', 5000);
      fetchConfig();
      fetchDownloads();
      return true;
    } catch (e) {
      if (addToast) addToast(`Errore salvataggio token: ${e.message}`, 'error');
      return false;
    } finally {
      setSavingToken(false);
    }
  };

  const handleSaveToken = async () => {
    const token = (config.hf_token || '').trim();
    if (!token) {
      if (addToast) addToast('⚠️ Inserisci un token Hugging Face valido (hf_...).', 'warning');
      return;
    }
    const ok = await persistToken(token, { successMessage: '🔑 Token Hugging Face salvato e attivo su tutta la piattaforma!' });
    // Saving without knowing whether the token works is the failure mode this
    // tab existed to remove: verify it right away.
    if (ok) handleTestToken();
  };

  const handleRemoveToken = async () => {
    setTokenTestResult(null);
    const ok = await persistToken('', { successMessage: '🗑️ Token Hugging Face rimosso. I download proseguiranno in modalità anonima.' });
    if (ok) setConfig(prev => ({ ...prev, hf_token: '' }));
  };

  const handleAddPublisher = async () => {
    const clean = newPublisherInput.trim().toLowerCase();
    if (!clean) return;
    const current = config.official_publishers || [];
    if (current.map(p => p.toLowerCase()).includes(clean)) {
      if (addToast) addToast(`L'autore "${clean}" è già presente nella lista`, 'info');
      return;
    }
    const updated = [...current, clean];
    setConfig(prev => ({
      ...prev,
      official_publishers: updated
    }));
    setNewPublisherInput('');

    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          official_publishers: updated
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`✅ Autore "${clean}" aggiunto e sincronizzato con Esplora Hugging Face!`, 'success');
        fetchConfig();
      }
    } catch {
      if (addToast) addToast(`Autore aggiunto: ${clean}`, 'info');
    }
  };

  const handleRemovePublisher = async (pubToRemove) => {
    const updated = (config.official_publishers || []).filter(p => p.toLowerCase() !== pubToRemove.toLowerCase());
    setConfig(prev => ({
      ...prev,
      official_publishers: updated
    }));

    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          official_publishers: updated
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`Autore "${pubToRemove}" rimosso e sincronizzato.`, 'info');
        fetchConfig();
      }
    } catch {
      if (addToast) addToast(`Autore "${pubToRemove}" rimosso.`, 'info');
    }
  };

  const handleResetPublishers = async () => {
    const updated = [...DEFAULT_OFFICIAL_PUBLISHERS];
    setConfig(prev => ({
      ...prev,
      official_publishers: updated
    }));

    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          official_publishers: updated
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('✅ Lista autori ufficiali ripristinata e sincronizzata con Esplora HF', 'success');
        fetchConfig();
      }
    } catch {
      if (addToast) addToast('Lista autori ufficiali ripristinata ai valori predefiniti', 'success');
    }
  };


  const handleAddExtraDir = async (dirCandidate) => {
    const raw = (dirCandidate || newExtraDirInput || '').trim();
    if (!raw) return;
    const clean = raw.replace(/[\\/]+$/, '');
    const currentList = config.extra_models_dirs || [];
    if (currentList.some(d => d.toLowerCase() === clean.toLowerCase())) {
      if (addToast) addToast('Questo percorso è già presente nell\'elenco.', 'info');
      setNewExtraDirInput('');
      return;
    }
    const updatedList = [...currentList, clean];
    setConfig(prev => ({
      ...prev,
      extra_models_dirs: updatedList
    }));
    setNewExtraDirInput('');

    // Salva immediatamente sul backend per sincronizzare la scansione
    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          extra_models_dirs: updatedList
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`✅ Cartella "${clean}" collegata con successo! Modelli scansionati automaticamente.`, 'success');
        fetchConfig();
        fetchLocalModels();
        try {
          window.dispatchEvent(new CustomEvent('ai-config-updated'));
          window.dispatchEvent(new CustomEvent('models-updated'));
        } catch (e) {}
      } else {
        if (addToast) addToast(`Cartella aggiunta: ${clean}.`, 'info');
      }
    } catch {
      if (addToast) addToast(`Cartella aggiunta: ${clean}.`, 'info');
    }
  };

  const handleRemoveExtraDir = async (dirToRemove) => {
    const updatedList = (config.extra_models_dirs || []).filter(d => d.toLowerCase() !== dirToRemove.toLowerCase());
    setConfig(prev => ({
      ...prev,
      extra_models_dirs: updatedList
    }));

    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          extra_models_dirs: updatedList
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`Percorso "${dirToRemove}" rimosso.`, 'info');
        fetchConfig();
        fetchLocalModels();
        try {
          window.dispatchEvent(new CustomEvent('ai-config-updated'));
          window.dispatchEvent(new CustomEvent('models-updated'));
        } catch (e) {}
      }
    } catch {
      if (addToast) addToast(`Percorso "${dirToRemove}" rimosso.`, 'info');
    }
  };


  const handleExecuteLocalImport = async () => {
    const target = (importSourcePath || '').trim();
    if (!target) {
      if (addToast) addToast('Seleziona prima un file o una cartella da importare.', 'error');
      return;
    }
    setImportingModel(true);
    try {
      const res = await fetch('/api/models/local/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: target,
          mode: importMode
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`✅ ${json.message}`, 'success');
        setImportSourcePath('');
        fetchConfig();
        fetchLocalModels();
        try {
          window.dispatchEvent(new CustomEvent('ai-config-updated'));
          window.dispatchEvent(new CustomEvent('models-updated'));
        } catch (e) {}
      } else {
        if (addToast) addToast(`❌ Errore importazione: ${json.error || 'Errore'}`, 'error');
      }
    } catch (err) {
      if (addToast) addToast(`Errore durante l'importazione: ${err.message}`, 'error');
    } finally {
      setImportingModel(false);
    }
  };

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      const res = await fetch('/api/models/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          models_dir: config.models_dir || 'store/models',
          extra_models_dirs: config.extra_models_dirs || [],
          hf_token: (config.hf_token || '').trim(),
          auto_deploy_on_download: config.auto_deploy_on_download ?? true,
          preferred_quantization: config.preferred_quantization || 'Q4_K_M',
          official_publishers: config.official_publishers || DEFAULT_OFFICIAL_PUBLISHERS
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⚡ Impostazioni salvate con successo!', 'success');
        fetchDownloads();
        fetchConfig();
        fetchLocalModels();
        try {
          window.dispatchEvent(new CustomEvent('ai-config-updated'));
          window.dispatchEvent(new CustomEvent('models-updated'));
        } catch (e) {}
      } else {
        if (addToast) addToast(`❌ Errore salvataggio: ${json.error || 'Errore'}`, 'error');
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
      {/* 1. FUTURISTIC RESPONSIVE HEADER */}
      <div className="mh-header" style={{
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf6ec 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(20, 26, 42, 0.85) 100%)',
        border: cardBorder, boxShadow: cardShadow,
      }}>
        <div className="mh-header-main">
          <div className="mh-header-icon-box">
            <TabIcon size={22} color={isLight ? '#ea580c' : '#ffb86c'} />
          </div>
          <div className="mh-header-titles">
            <div className="mh-header-title-row">
              <h1 className="mh-header-title" style={{ color: textPrimary }}>
                Model Hub <span style={{ opacity: 0.35 }}>/</span> <span style={{ color: isLight ? '#ea580c' : '#ffb86c' }}>{currentTabMeta.title}</span>
              </h1>
              <span className="mh-view-badge">
                {currentTabMeta.badge}
              </span>
              {totalActiveTasksCount > 0 && (
                <span
                  className="mh-active-task-pill"
                  onClick={() => setActiveTab('inventory')}
                  title="Clicca per visualizzare i download attivi"
                >
                  <Activity size={10} className="mh-spin" />
                  <span>{currentRunningTask ? `${currentRunningTask.progress_pct}%` : `${totalActiveTasksCount} download`}</span>
                </span>
              )}
              {activeConversion && (
                <span
                  className="mh-active-task-pill"
                  onClick={() => setActiveTab('converter')}
                  title="Clicca per visualizzare la conversione in corso"
                  style={{ background: 'rgba(255, 184, 108, 0.18)', color: '#ffb86c', borderColor: 'rgba(255, 184, 108, 0.35)' }}
                >
                  <Zap size={10} className="mh-spin" />
                  <span>{activeConversion.progress || 0}% conv</span>
                </span>
              )}
            </div>
            <p className="mh-header-sub" style={{ color: textMuted }}>
              {currentTabMeta.desc}
            </p>
          </div>
        </div>

        {/* Right Tools & Engine Status */}
        <div className="mh-header-tools">
          <button
            onClick={handleTestConnection}
            disabled={testingConn}
            title="Esegui test connettività verso Hugging Face e verifica token"
            className="mh-conn-btn"
            style={{
              background: connResult?.connected ? 'rgba(16, 185, 129, 0.15)' : (isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(255, 184, 108, 0.15)'),
              color: connResult?.connected ? '#10b981' : (isLight ? '#ea580c' : '#ffb86c'),
              border: connResult?.connected ? '1px solid rgba(16, 185, 129, 0.4)' : (isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(255, 184, 108, 0.3)'),
            }}
          >
            {testingConn ? <Activity className="mh-spin" size={11} /> : <RefreshCw size={11} />}
            <span>{testingConn ? 'Verifica...' : connResult?.latency_ms ? `HF (${connResult.latency_ms}ms)` : 'Test HF'}</span>
          </button>

          {/* Engine Live Status Pill */}
          <div className="mh-engine-pill" style={{ background: subBg, border: subBorder }}>
            <Zap size={13} color="#00d2ff" style={{ flexShrink: 0 }} />
            <div>
              <div className="mh-engine-pill-title" style={{ color: textMuted }}>MOTORE ATTIVO</div>
              <div className="mh-engine-pill-val" style={{ color: '#00d2ff' }}>
                {engineStatus?.loaded_model || 'Standby'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modern Cyber-Segmented Pill Switcher */}
      <div className="mh-segmented-nav">
        {[
          { id: 'browse', label: 'Esplora HF', icon: Search },
          { id: 'inventory', label: totalActiveTasksCount > 0 ? `Modelli Locali (${currentRunningTask ? `${currentRunningTask.progress_pct}%` : totalActiveTasksCount})` : 'Modelli Locali', icon: HardDrive },
          { id: 'converter', label: activeConversion ? `Convertitore (${activeConversion.progress || 0}%)` : 'Convertitore GGUF', icon: Zap },
          { id: 'settings', label: 'Impostazioni & Token', icon: Settings },
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`mh-segmented-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={13} style={{ flexShrink: 0 }} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 2. TAB CONTENT VIEWS */}
      <div className="mh-view-container">

      {/* 3. TAB CONTENT VIEWS */}
      {activeTab === 'browse' && (
        <HfBrowser
          isLight={isLight}
          addToast={addToast}
          activeDownloads={activeDownloads}
          officialPublishers={config.official_publishers || DEFAULT_OFFICIAL_PUBLISHERS}
          localModels={localModels}
          onDownloadStarted={() => {
            fetchDownloads();
            fetchLocalModels();
          }}
        />
      )}


      {activeTab === 'inventory' && (
        <LocalInventory
          isLight={isLight}
          addToast={addToast}
          activeDownloads={activeDownloads}
          onDownloadsChanged={fetchDownloads}
          engineStatus={engineStatus}
          onDeployRequested={m => setDeployTargetModel(m)}
          onNavigateToConverter={modelName => {
            setPreselectedConvertModel(modelName);
            setActiveTab('converter');
          }}
        />
      )}

      {activeTab === 'converter' && (
        <GgufConverter
          isLight={isLight}
          addToast={addToast}
          initialModel={preselectedConvertModel}
          jobs={conversionJobs}
          onJobsChanged={fetchConversionJobs}
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary }}>
                  Token Personale Hugging Face (hf_...):
                </label>
                <span style={{
                  display: 'flex', alignItems: 'center', gap: '5px',
                  fontSize: '0.68rem', fontWeight: 800, padding: '3px 10px', borderRadius: '12px',
                  background: hfTokenStatus.has_token ? 'rgba(16, 185, 129, 0.14)' : 'rgba(245, 158, 11, 0.14)',
                  border: hfTokenStatus.has_token ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(245, 158, 11, 0.35)',
                  color: hfTokenStatus.has_token ? '#10b981' : '#f59e0b'
                }}>
                  {hfTokenStatus.has_token ? <Check size={11} /> : <AlertTriangle size={11} />}
                  {hfTokenStatus.has_token
                    ? `Token attivo • ${HF_TOKEN_SOURCE_LABELS[hfTokenStatus.source] || 'Configurazione Sigma'}`
                    : 'Nessun token configurato'}
                </span>
              </div>

              {hfTokenStatus.has_token && (hfTokenStatus.source === 'env' || hfTokenStatus.source === 'cli_cache') && (
                <div style={{ fontSize: '0.68rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <AlertTriangle size={12} />
                  Token ereditato da {hfTokenStatus.detail || 'una fonte esterna'}: ha la precedenza finché non ne salvi uno qui.
                </div>
              )}

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <div style={{ position: 'relative', flex: '1 1 260px', minWidth: '220px' }}>
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={config.hf_token || ''}
                    onChange={e => {
                      setConfig({ ...config, hf_token: e.target.value });
                      setTokenTestResult(null);
                    }}
                    onKeyDown={e => { if (e.key === 'Enter') handleSaveToken(); }}
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
                  onClick={handleSaveToken}
                  disabled={savingToken || !(config.hf_token || '').trim()}
                  style={{
                    padding: '10px 20px', borderRadius: '10px', border: 'none',
                    background: 'linear-gradient(135deg, #10b981, #00d2ff)',
                    color: '#ffffff', fontSize: '0.8rem', fontWeight: 800,
                    cursor: savingToken || !(config.hf_token || '').trim() ? 'not-allowed' : 'pointer',
                    opacity: savingToken || !(config.hf_token || '').trim() ? 0.6 : 1,
                    display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap',
                    boxShadow: '0 4px 18px rgba(16, 185, 129, 0.25)'
                  }}
                >
                  {savingToken ? <Activity className="mh-spin" size={14} /> : <CheckCircle2 size={14} />}
                  {savingToken ? 'Salvataggio...' : hfTokenStatus.has_token ? 'Aggiorna Token' : 'Salva Token'}
                </button>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '2px' }}>
                <button
                  onClick={handleTestConnection}
                  disabled={testingConn}
                  title="Verifica raggiungibilità di Hugging Face e validità del token attivo"
                  style={{
                    padding: '9px 14px', borderRadius: '10px', border: subBorder,
                    background: 'linear-gradient(135deg, rgba(255, 184, 108, 0.2), rgba(234, 88, 12, 0.2))',
                    color: textPrimary, fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                  }}
                >
                  {testingConn ? <Activity className="mh-spin" size={14} color="#ffb86c" /> : <RefreshCw size={14} color="#ffb86c" />}
                  {testingConn ? 'Test in corso...' : '🧪 Test Connessione'}
                </button>

                <button
                  onClick={handleTestToken}
                  disabled={testingToken || !(config.hf_token || '').trim()}
                  title="Interroga huggingface.co/api/whoami-v2 con il token inserito"
                  style={{
                    padding: '9px 14px', borderRadius: '10px', border: subBorder,
                    background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(0, 210, 255, 0.2))',
                    color: textPrimary, fontSize: '0.76rem', fontWeight: 800,
                    cursor: testingToken || !(config.hf_token || '').trim() ? 'not-allowed' : 'pointer',
                    opacity: testingToken || !(config.hf_token || '').trim() ? 0.6 : 1,
                    display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                  }}
                >
                  {testingToken ? <Activity className="mh-spin" size={14} color="#00d2ff" /> : <ShieldCheck size={14} color="#00d2ff" />}
                  {testingToken ? 'Verifica...' : '🔍 Verifica Token'}
                </button>

                {hfTokenStatus.has_token && (
                  <button
                    onClick={handleRemoveToken}
                    disabled={savingToken}
                    title="Cancella il token da ambiente e configurazione"
                    style={{
                      padding: '9px 14px', borderRadius: '10px',
                      border: '1px solid rgba(239, 68, 68, 0.35)',
                      background: 'rgba(239, 68, 68, 0.1)',
                      color: '#ef4444', fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                    }}
                  >
                    <XCircle size={14} /> Rimuovi Token
                  </button>
                )}

                {lastFailedTask && hfTokenStatus.has_token && (
                  <button
                    onClick={() => handleRetryTask(lastFailedTask.task_id)}
                    title={`Riprende ${lastFailedTask.model_id} con il token attivo`}
                    style={{
                      padding: '9px 14px', borderRadius: '10px',
                      border: '1px solid rgba(255, 184, 108, 0.4)',
                      background: 'rgba(255, 184, 108, 0.12)',
                      color: '#ffb86c', fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                    }}
                  >
                    <RotateCcw size={14} /> Riprendi Download Interrotto
                  </button>
                )}
              </div>
            </div>

            {/* Connection test result alert */}
            {connResult && (
              <div style={{
                padding: '12px 16px', borderRadius: '10px',
                background: connResult.connected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                border: connResult.connected ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex', alignItems: 'flex-start', gap: '10px'
              }}>
                {connResult.connected ? (
                  <CheckCircle2 size={18} color="#10b981" style={{ flexShrink: 0, marginTop: '2px' }} />
                ) : (
                  <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0, marginTop: '2px' }} />
                )}
                <div style={{ fontSize: '0.76rem', color: connResult.connected ? '#10b981' : '#ef4444' }}>
                  <div style={{ fontWeight: 800 }}>
                    {connResult.connected ? `Hugging Face Raggiungibile (Latenza: ${connResult.latency_ms}ms)` : 'Connessione a Hugging Face Fallita'}
                  </div>
                  <div style={{ marginTop: '2px', color: textPrimary, fontSize: '0.72rem' }}>
                    {connResult.message || connResult.error}
                  </div>
                </div>
              </div>
            )}

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

            {/* A che serve il token */}
            <div style={{
              background: 'rgba(0, 210, 255, 0.04)', border: '1px solid rgba(0, 210, 255, 0.12)',
              borderRadius: '12px', padding: '14px 16px',
              fontSize: '0.7rem', color: textMuted, lineHeight: 1.65
            }}>
              <strong style={{ color: '#00d2ff' }}>💡 Perché serve il token?</strong>
              <ul style={{ margin: '8px 0 0 16px', padding: 0 }}>
                <li>Download da Hugging Face fino a 10x più veloci (da ~50 KB/s anonimi a 5-50 MB/s)</li>
                <li>Accesso ai modelli <em>gated</em> (Llama 3, Gemma, Mistral, DeepSeek)</li>
                <li>Necessario per dataset privati o soggetti a restrizioni</li>
                <li>Vale per tutta la piattaforma — Model Hub, Training Lab e conversioni GGUF — e resta attivo dopo il riavvio</li>
              </ul>
            </div>
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
          </div>

          {/* SEZIONE 2-BIS: PERCORSI MODELLI AGGIUNTIVI & IMPORTAZIONE LOCALE */}
          <div style={{
            padding: '24px', borderRadius: '16px',
            background: cardBg, border: cardBorder, boxShadow: cardShadow,
            display: 'flex', flexDirection: 'column', gap: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(168, 85, 247, 0.2))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <HardDrive size={20} color="#00d2ff" />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                    Percorsi Modelli Aggiuntivi & Importazione Locale
                  </h2>
                  <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
                    Collega altre cartelle del tuo computer o importa modelli (GGUF, Safetensors) da qualsiasi percorso su disco
                  </div>
                </div>
              </div>
            </div>

            {/* Aggiunta nuova cartella */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.74rem', fontWeight: 700, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FolderPlus size={14} color="#00d2ff" /> Aggiungi Cartella da Scansionare:
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  value={newExtraDirInput}
                  onChange={e => setNewExtraDirInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleAddExtraDir(); }}
                  placeholder="es. D:\Modelli_AI, C:\Ollama\models, E:\LLM_Archive..."
                  style={{
                    flex: '1 1 280px', padding: '10px 14px', borderRadius: '10px',
                    background: subBg, border: subBorder,
                    color: textPrimary, fontSize: '0.82rem', fontFamily: 'monospace', outline: 'none'
                  }}
                />
                <button
                  type="button"
                  onClick={() => setPickingExtraDir(true)}
                  title="Sfoglia cartelle su disco"
                  style={{
                    padding: '10px 16px', borderRadius: '10px', border: subBorder,
                    background: subBg, color: textPrimary,
                    fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer',
                    whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <Folder size={14} color="#ffb86c" /> Sfoglia...
                </button>
                <button
                  type="button"
                  onClick={() => handleAddExtraDir()}
                  disabled={!newExtraDirInput.trim()}
                  style={{
                    padding: '10px 18px', borderRadius: '10px', border: 'none',
                    background: 'linear-gradient(135deg, #00d2ff, #0088ff)',
                    color: '#ffffff', fontSize: '0.80rem', fontWeight: 800,
                    cursor: !newExtraDirInput.trim() ? 'not-allowed' : 'pointer',
                    opacity: !newExtraDirInput.trim() ? 0.6 : 1,
                    display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                  }}
                >
                  <Plus size={14} /> Aggiungi Percorso
                </button>
              </div>
            </div>

            {/* Lista directory aggiuntive attive */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Cartelle Secondarie Monitorate ({(config.extra_models_dirs || []).length}):
              </div>

              {(config.extra_models_dirs || []).length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                  {(config.extra_models_dirs || []).map((dirPath, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 14px', borderRadius: '10px',
                        background: subBg, border: subBorder, gap: '10px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, overflow: 'hidden' }}>
                        <div style={{
                          width: '28px', height: '28px', borderRadius: '6px',
                          background: 'rgba(0, 210, 255, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                        }}>
                          <HardDrive size={15} color="#00d2ff" />
                        </div>
                        <code style={{ fontSize: '0.78rem', color: textPrimary, wordBreak: 'break-all', fontFamily: 'monospace' }}>
                          {dirPath}
                        </code>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveExtraDir(dirPath)}
                        title="Rimuovi questo percorso"
                        style={{
                          padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.3)',
                          background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                          fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0
                        }}
                      >
                        <X size={12} /> Rimuovi
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{
                  padding: '14px', borderRadius: '10px', background: 'rgba(0, 210, 255, 0.03)',
                  border: '1px dashed rgba(0, 210, 255, 0.2)', fontSize: '0.74rem', color: textMuted,
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}>
                  <Sparkles size={16} color="#00d2ff" style={{ flexShrink: 0 }} />
                  <span>
                    Nessun percorso aggiuntivo impostato. Aggiungi directory esterne (es. da altri dischi o app terze) per scansionare automaticamente tutti i modelli senza doverli copiare né occupare spazio sul disco principale.
                  </span>
                </div>
              )}
            </div>

            {/* Pannello Importazione Rapida File/Modello */}
            <div style={{
              padding: '16px', borderRadius: '12px',
              background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)',
              border: isLight ? '1px solid rgba(190,160,110,0.22)' : '1px solid rgba(255,255,255,0.06)',
              display: 'flex', flexDirection: 'column', gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Package size={17} color="#ffb86c" />
                <strong style={{ fontSize: '0.84rem', color: textPrimary }}>
                  Importazione Rapida (File Singolo o Cartella Esterna)
                </strong>
              </div>
              <div style={{ fontSize: '0.72rem', color: textMuted }}>
                Seleziona un singolo file di pesi (.gguf, .safetensors) o una cartella di un modello scaricato da un'altra sorgente per importarlo immediatamente.
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  value={importSourcePath}
                  onChange={e => setImportSourcePath(e.target.value)}
                  placeholder="Seleziona file o cartella del modello (es. D:\Download\Qwen-7B-Q4.gguf)..."
                  style={{
                    flex: '1 1 280px', padding: '10px 14px', borderRadius: '10px',
                    background: subBg, border: subBorder,
                    color: textPrimary, fontSize: '0.82rem', fontFamily: 'monospace', outline: 'none'
                  }}
                />
                <button
                  type="button"
                  onClick={() => setPickingImportItem(true)}
                  title="Sfoglia file o cartella su disco"
                  style={{
                    padding: '10px 16px', borderRadius: '10px', border: subBorder,
                    background: subBg, color: textPrimary,
                    fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer',
                    whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <FolderOpen size={14} color="#00d2ff" /> Sfoglia File/Cartella...
                </button>
              </div>

              {/* Modalità importazione */}
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted }}>Modalità:</span>
                
                <button
                  type="button"
                  onClick={() => setImportMode('add_path')}
                  style={{
                    padding: '6px 12px', borderRadius: '8px',
                    border: importMode === 'add_path' ? '1px solid #00d2ff' : subBorder,
                    background: importMode === 'add_path' ? 'rgba(0, 210, 255, 0.15)' : subBg,
                    color: importMode === 'add_path' ? '#00d2ff' : textMuted,
                    fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <Zap size={13} color={importMode === 'add_path' ? '#00d2ff' : textMuted} />
                  ⚡ Collega Cartella (Zero-Copy)
                </button>

                <button
                  type="button"
                  onClick={() => setImportMode('copy')}
                  style={{
                    padding: '6px 12px', borderRadius: '8px',
                    border: importMode === 'copy' ? '1px solid #ffb86c' : subBorder,
                    background: importMode === 'copy' ? 'rgba(255, 184, 108, 0.15)' : subBg,
                    color: importMode === 'copy' ? '#ffb86c' : textMuted,
                    fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <Copy size={13} color={importMode === 'copy' ? '#ffb86c' : textMuted} />
                  📁 Copia Fisica in store/models
                </button>

                <button
                  type="button"
                  onClick={() => setImportMode('symlink')}
                  style={{
                    padding: '6px 12px', borderRadius: '8px',
                    border: importMode === 'symlink' ? '1px solid #a855f7' : subBorder,
                    background: importMode === 'symlink' ? 'rgba(168, 85, 247, 0.15)' : subBg,
                    color: importMode === 'symlink' ? '#a855f7' : textMuted,
                    fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                  }}
                >
                  <Link2 size={13} color={importMode === 'symlink' ? '#a855f7' : textMuted} />
                  🔗 Collegamento Simbolico (Symlink)
                </button>

                <div style={{ marginLeft: 'auto' }}>
                  <button
                    type="button"
                    onClick={handleExecuteLocalImport}
                    disabled={importingModel || !importSourcePath.trim()}
                    style={{
                      padding: '8px 18px', borderRadius: '8px', border: 'none',
                      background: 'linear-gradient(135deg, #00d2ff, #0088ff)',
                      color: '#ffffff', fontSize: '0.78rem', fontWeight: 800,
                      cursor: importingModel || !importSourcePath.trim() ? 'not-allowed' : 'pointer',
                      opacity: importingModel || !importSourcePath.trim() ? 0.6 : 1,
                      display: 'flex', alignItems: 'center', gap: '6px'
                    }}
                  >
                    {importingModel ? <Activity className="mh-spin" size={14} /> : <Check size={14} />}
                    {importingModel ? 'Importazione in corso...' : 'Importa Modello'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* SEZIONE 3: PROVIDER & AUTORI UFFICIALI (HUGGING FACE) */}
          <div style={{
            padding: '24px', borderRadius: '16px',
            background: cardBg, border: cardBorder, boxShadow: cardShadow,
            display: 'flex', flexDirection: 'column', gap: '16px'
          }}>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.2), rgba(188, 140, 255, 0.2))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <ShieldCheck size={20} color="#00d2ff" />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                    Provider & Autori Ufficiali
                  </h2>
                  <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
                    Personalizza l'elenco dei creator e laboratori AI riconosciuti dal filtro "Solo Ufficiali"
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleResetPublishers}
                style={{
                  fontSize: '0.72rem', color: '#ffb86c', background: 'rgba(255, 184, 108, 0.1)',
                  border: '1px solid rgba(255, 184, 108, 0.3)', borderRadius: '8px', padding: '6px 12px',
                  fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                <RotateCcw size={12} /> Ripristina Predefiniti
              </button>
            </div>

            {/* Input per aggiungere nuovo autore */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={newPublisherInput}
                onChange={e => setNewPublisherInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleAddPublisher(); }}
                placeholder="es. google, meta-llama, qwen, sigmanih, mistralai..."
                style={{
                  flex: '1 1 240px', padding: '10px 14px', borderRadius: '10px',
                  background: subBg, border: subBorder,
                  color: textPrimary, fontSize: '0.82rem', fontFamily: 'monospace', outline: 'none'
                }}
              />
              <button
                type="button"
                onClick={handleAddPublisher}
                disabled={!newPublisherInput.trim()}
                style={{
                  padding: '10px 18px', borderRadius: '10px', border: 'none',
                  background: 'linear-gradient(135deg, #00d2ff, #0088ff)',
                  color: '#ffffff', fontSize: '0.80rem', fontWeight: 800,
                  cursor: !newPublisherInput.trim() ? 'not-allowed' : 'pointer',
                  opacity: !newPublisherInput.trim() ? 0.6 : 1,
                  display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap'
                }}
              >
                <Plus size={14} /> Aggiungi Autore
              </button>
            </div>

            {/* Tags elenco autori attivi */}
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: '7px', maxHeight: '180px',
              overflowY: 'auto', padding: '10px', background: subBg, borderRadius: '10px', border: subBorder
            }}>
              {(config.official_publishers || DEFAULT_OFFICIAL_PUBLISHERS).map(pub => {
                const isSig = pub.toLowerCase() === 'sigmanih';
                return (
                  <span
                    key={pub}
                    style={{
                      fontSize: '0.72rem', fontWeight: 700, padding: '4px 9px', borderRadius: '6px',
                      background: isSig ? 'rgba(255, 184, 108, 0.20)' : (isLight ? '#ffffff' : 'rgba(255,255,255,0.08)'),
                      border: isSig ? '1px solid rgba(255, 184, 108, 0.45)' : subBorder,
                      color: isSig ? '#ffb86c' : textPrimary,
                      display: 'inline-flex', alignItems: 'center', gap: '6px'
                    }}
                  >
                    <span>{pub}</span>
                    <button
                      type="button"
                      onClick={() => handleRemovePublisher(pub)}
                      title={`Rimuovi ${pub}`}
                      style={{
                        background: 'none', border: 'none', color: textMuted,
                        cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center'
                      }}
                    >
                      <X size={12} />
                    </button>
                  </span>
                );
              })}
            </div>
          </div>

          {/* PULSANTI SALVATAGGIO CONFIGURAZIONE COMPLESSIVA */}
          <div style={{
            padding: '16px 24px', borderRadius: '16px',
            background: cardBg, border: cardBorder,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px'
          }}>
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
              {savingConfig ? 'Salvataggio...' : 'Salva Tutte le Impostazioni'}
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
      )}

      {/* 4. LIVE FLOATING CONVERSION HUD BANNER (visibile da ogni scheda) */}
      {activeConversion && activeTab !== 'converter' && (
        <div
          onClick={() => setActiveTab('converter')}
          style={{
            position: 'sticky', bottom: '16px', zIndex: 100,
            padding: '12px 18px', borderRadius: '14px',
            background: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(13, 16, 25, 0.95)',
            backdropFilter: 'blur(12px)',
            border: '1.5px solid #10b981',
            boxShadow: '0 10px 30px rgba(16, 185, 129, 0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px',
            cursor: 'pointer', transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}>
            <Activity className="mh-spin" size={20} color="#10b981" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {CONVERSION_STAGE_LABELS[activeConversion.status] || 'Conversione'} in corso: {activeConversion.source_model} ➔ {activeConversion.quantization}
                </span>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#10b981', fontFamily: 'monospace' }}>
                  {activeConversion.progress || 0}%
                </span>
              </div>
              <div style={{
                height: '4px', borderRadius: '3px', marginTop: '6px',
                background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)', overflow: 'hidden'
              }}>
                <div style={{
                  width: `${activeConversion.progress || 0}%`, height: '100%', borderRadius: '3px',
                  background: 'linear-gradient(90deg, #00d2ff, #10b981)',
                  transition: 'width 0.4s ease'
                }} />
              </div>
              <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeConversion.message || 'Elaborazione dei pesi in corso…'}
                {' • '}
                <span style={{ color: '#ffb86c', fontWeight: 700 }}>
                  {Math.round(activeConversion.elapsed_seconds || 0)}s
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab('converter');
              }}
              style={{
                padding: '6px 12px', borderRadius: '8px', border: 'none',
                background: 'linear-gradient(135deg, #10b981, #059669)', color: '#ffffff',
                fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '4px'
              }}
            >
              Apri Dettagli <ArrowRight size={12} />
            </button>
          </div>
        </div>
      )}

      {/* 5. SLEEK LIVE FLOATING DOWNLOAD HUD BANNER (Visible across any tab when downloading or interrupted) */}
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
      </div>


      {pickingDir && (
        <DirectoryPicker
          initialPath={config.models_dir}
          isLight={isLight}
          title="Scegli Cartella di Salvataggio Principale"
          confirmLabel="Usa come cartella principale"
          onSelect={dir => setConfig(c => ({ ...c, models_dir: dir }))}
          onClose={() => setPickingDir(false)}
        />
      )}

      {pickingExtraDir && (
        <DirectoryPicker
          initialPath={config.models_dir}
          isLight={isLight}
          title="Scegli Cartella Modelli da Aggiungere"
          confirmLabel="Aggiungi questa cartella"
          onSelect={dir => handleAddExtraDir(dir)}
          onClose={() => setPickingExtraDir(false)}
        />
      )}

      {pickingImportItem && (
        <DirectoryPicker
          initialPath={config.models_dir}
          isLight={isLight}
          title="Seleziona Modello o Cartella da Importare"
          confirmLabel="Importa questo elemento"
          includeFiles={true}
          onSelect={path => setImportSourcePath(path)}
          onClose={() => setPickingImportItem(false)}
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

