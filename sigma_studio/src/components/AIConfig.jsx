import React, { useState, useEffect } from 'react';
import { X, Cpu, Database, Save, RefreshCw, Globe, Server, Key, Sliders } from 'lucide-react';

// ==============================================================================
// AI CONFIG | Configurazione provider AI con preset
// ==============================================================================

const PROVIDER_PRESETS = {
  ollama: {
    label: 'Ollama (Locale)',
    endpoint: 'http://localhost:11434',
    api_url: '',
    model: 'llama3.2',
    api_key_required: false,
    hint: 'Modelli installati localmente con Ollama',
    models: []
  },
  openai: {
    label: 'OpenAI (ChatGPT)',
    endpoint: '',
    api_url: 'https://api.openai.com/v1/chat/completions',
    model: 'gpt-4o-mini',
    api_key_required: true,
    hint: 'api.openai.com/v1/chat/completions',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4o-2024-08-06', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'o1', 'o3-mini']
  },
  anthropic: {
    label: 'Anthropic (Claude)',
    endpoint: '',
    api_url: 'https://api.anthropic.com/v1/messages',
    model: 'claude-sonnet-4-20250514',
    api_key_required: true,
    hint: 'api.anthropic.com/v1/messages',
    models: ['claude-sonnet-4-20250514', 'claude-sonnet-4', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307']
  },
  deepseek: {
    label: 'DeepSeek',
    endpoint: '',
    api_url: 'https://api.deepseek.com/v1/chat/completions',
    model: 'deepseek-chat',
    api_key_required: true,
    hint: 'api.deepseek.com/v1/chat/completions',
    models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder', 'deepseek-v4-flash', 'deepseek-v4-pro']
  },
  groq: {
    label: 'Groq',
    endpoint: '',
    api_url: 'https://api.groq.com/openai/v1/chat/completions',
    model: 'llama-3.3-70b-versatile',
    api_key_required: true,
    hint: 'api.groq.com/openai/v1/chat/completions',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it', 'deepseek-r1-distill-llama-70b']
  },
  openrouter: {
    label: 'OpenRouter',
    endpoint: '',
    api_url: 'https://openrouter.ai/api/v1/chat/completions',
    model: 'openai/gpt-4o-mini',
    api_key_required: true,
    hint: 'openrouter.ai/api/v1/chat/completions',
    models: ['openai/gpt-4o-mini', 'openai/gpt-4o', 'anthropic/claude-sonnet-4', 'google/gemini-pro-1.5', 'mistral/mixtral-8x22b', 'deepseek/deepseek-r1']
  },
  google: {
    label: 'Google (Gemini)',
    endpoint: '',
    api_url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
    model: 'gemini-2.0-flash',
    api_key_required: true,
    hint: 'generativelanguage.googleapis.com (usare API key Google AI Studio)',
    models: ['gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-flash-8b']
  },
  mistral: {
    label: 'Mistral AI',
    endpoint: '',
    api_url: 'https://api.mistral.ai/v1/chat/completions',
    model: 'mistral-large-latest',
    api_key_required: true,
    hint: 'api.mistral.ai/v1/chat/completions',
    models: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest', 'mistral-medium-latest', 'open-mistral-nemo']
  },
  xai: {
    label: 'xAI (Grok)',
    endpoint: '',
    api_url: 'https://api.x.ai/v1/chat/completions',
    model: 'grok-2',
    api_key_required: true,
    hint: 'api.x.ai/v1/chat/completions',
    models: ['grok-2', 'grok-2-mini', 'grok-beta', 'grok-2-vision']
  },
  perplexity: {
    label: 'Perplexity',
    endpoint: '',
    api_url: 'https://api.perplexity.ai/chat/completions',
    model: 'sonar-pro',
    api_key_required: true,
    hint: 'api.perplexity.ai/chat/completions',
    models: ['sonar-pro', 'sonar', 'llama-3.1-sonar-small', 'llama-3.1-sonar-large', 'llama-3.1-sonar-huge']
  },
  together: {
    label: 'Together AI',
    endpoint: '',
    api_url: 'https://api.together.xyz/v1/chat/completions',
    model: 'mistralai/Mixtral-8x22B-Instruct-v0.1',
    api_key_required: true,
    hint: 'api.together.xyz/v1/chat/completions',
    models: ['mistralai/Mixtral-8x22B-Instruct-v0.1', 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'deepseek-ai/deepseek-coder-v2-instruct', 'Qwen/Qwen2.5-72B-Instruct-Turbo', 'meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo']
  },
  qwen: {
    label: 'Qwen (Alibaba Cloud)',
    endpoint: '',
    api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    model: 'qwen-max',
    api_key_required: true,
    hint: 'dashscope.aliyuncs.com (API key da Alibaba Cloud)',
    models: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen2.5-72b-instruct', 'qwen2.5-32b-instruct', 'qwen2.5-14b-instruct', 'qwen2.5-7b-instruct', 'qwen2.5-coder-32b-instruct', 'qwen2.5-math-72b-instruct']
  },
  glm: {
    label: 'GLM (Zhipu AI)',
    endpoint: '',
    api_url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    model: 'glm-4-plus',
    api_key_required: true,
    hint: 'open.bigmodel.cn (API key da Zhipu AI)',
    models: ['glm-4-plus', 'glm-4-0520', 'glm-4-air', 'glm-4-flash', 'glm-4-long', 'glm-4v-plus', 'glm-4v']
  },
  moonshot: {
    label: 'Moonshot (Kimi)',
    endpoint: '',
    api_url: 'https://api.moonshot.cn/v1/chat/completions',
    model: 'moonshot-v1-8k',
    api_key_required: true,
    hint: 'api.moonshot.cn (API key da Moonshot AI)',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k', 'moonshot-v1-auto']
  },
  yi: {
    label: 'Yi (01.AI)',
    endpoint: '',
    api_url: 'https://api.01.ai/v1/chat/completions',
    model: 'yi-large',
    api_key_required: true,
    hint: 'api.01.ai (API key da 01.AI)',
    models: ['yi-large', 'yi-medium', 'yi-vision', 'yi-large-rag', 'yi-large-turbo', 'yi-lightning', 'yi-large-preview']
  },
  custom: {
    label: 'API Personalizzata',
    endpoint: '',
    api_url: '',
    model: '',
    api_key_required: false,
    hint: 'Inserisci URL API completo e modello manualmente',
    models: []
  }
};

export default function AIConfig({ isOpen, onClose }) {
  const [config, setConfig] = useState({
    provider: 'ollama',
    endpoint: 'http://localhost:11434',
    model: 'llama3.2',
    api_url: '',
    api_key: '',
    has_api_key: false,
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 0.9,
    num_ctx: 8192,
  });
  const [ollamaModels, setOllamaModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [testStatus, setTestStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) fetchConfig();
  }, [isOpen]);

  /** Convert stored endpoint back to base URL (remove /api/chat suffix) */
  const toBaseEndpoint = (ep) => {
    if (ep.endsWith('/api/chat')) return ep.replace('/api/chat', '');
    if (ep.endsWith('/api/chat/')) return ep.replace('/api/chat/', '');
    return ep;
  };

  const fetchConfig = async () => {
    setTestStatus(null);
    try {
      const res = await fetch('/api/config');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.success) {
        const cfg = data.config;
        setConfig(prev => ({
          ...prev,
          ...cfg,
          endpoint: toBaseEndpoint(cfg.endpoint || prev.endpoint),
          temperature: cfg.temperature ?? 0.7,
          max_tokens: cfg.max_tokens ?? 4096,
          top_p: cfg.top_p ?? 0.9,
          num_ctx: cfg.num_ctx ?? 8192,
        }));
      }
    } catch (e) {
      setTestStatus({ ok: false, msg: `❌ Backend non raggiungibile. Avvia sigma_server.py su porta 8000.` });
    }
  };

  const fetchOllamaModels = async () => {
    const ep = config.endpoint || 'http://localhost:11434';
    setLoadingModels(true);
    try {
      const res = await fetch(`${ep}/api/tags`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const models = (data.models || []).map(m => m.name);
      setOllamaModels(models);
      if (models.length > 0) {
        setTestStatus({ ok: true, msg: `✅ ${models.length} modelli trovati: ${models.slice(0, 5).join(', ')}${models.length > 5 ? '...' : ''}` });
        if (!models.includes(config.model) && models.length > 0) {
          setConfig(prev => ({ ...prev, model: models[0] }));
        }
      } else {
        setTestStatus({ ok: false, msg: '⚠️ Nessun modello trovato su Ollama.' });
      }
    } catch (e) {
      setTestStatus({ ok: false, msg: `❌ Ollama non raggiungibile su ${ep}: ${e.message}` });
      setOllamaModels([]);
    }
    setLoadingModels(false);
  };

  const selectProvider = (providerKey) => {
    const preset = PROVIDER_PRESETS[providerKey];
    if (!preset) return;
    setConfig(prev => ({
      ...prev,
      provider: providerKey,
      endpoint: preset.endpoint || prev.endpoint,
      api_url: preset.api_url || prev.api_url,
      model: preset.model || prev.model,
      api_key: preset.api_key_required ? prev.api_key : ''
    }));
    setTestStatus(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setTestStatus(null);
    try {
      const body = {
        provider: config.provider,
        endpoint: config.provider === 'ollama'
          ? `${config.endpoint}/api/chat`
          : config.endpoint,
        model: config.model,
        api_url: config.api_url,
        api_key: config.api_key,
        temperature: config.temperature,
        max_tokens: config.max_tokens,
        top_p: config.top_p,
        num_ctx: config.num_ctx,
      };
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (data.success) {
        setTestStatus({ ok: true, msg: '✅ Configurazione salvata!' });
        setTimeout(onClose, 1200);
      } else {
        setTestStatus({ ok: false, msg: `❌ ${data.error || 'Errore salvataggio'}` });
      }
    } catch (e) {
      setTestStatus({ ok: false, msg: `❌ ${e.message}` });
    }
    setSaving(false);
  };

  const testConnection = async () => {
    setTestStatus({ ok: null, msg: '⏳ Test in corso...' });
    try {
      // First save current config
      const saveBody = {
        provider: config.provider,
        endpoint: config.provider === 'ollama'
          ? `${config.endpoint}/api/chat`
          : config.endpoint,
        model: config.model,
        api_url: config.api_url,
        api_key: config.api_key,
        temperature: config.temperature,
        max_tokens: config.max_tokens,
        top_p: config.top_p,
        num_ctx: config.num_ctx,
      };
      const saveRes = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(saveBody)
      });
      if (!(await saveRes.json()).success) {
        setTestStatus({ ok: false, msg: '❌ Errore nel salvataggio configurazione' });
        return;
      }
      // Test: send a simple chat
      const chatRes = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: "Rispondi solo con 'OK' se funzioni correttamente.",
          allow_actions: false,
          model: config.model
        })
      });
      const chatData = await chatRes.json();
      if (chatData.error) {
        setTestStatus({ ok: false, msg: `❌ ${chatData.error}` });
      } else {
        const resp = (chatData.response || '').slice(0, 80);
        setTestStatus({ ok: true, msg: `✅ Connessione OK! Risposta: "${resp}..."` });
      }
    } catch (e) {
      setTestStatus({ ok: false, msg: `❌ ${e.message}` });
    }
  };

  if (!isOpen) return null;

  const currentPreset = PROVIDER_PRESETS[config.provider] || PROVIDER_PRESETS.custom;
  const showApiKey = currentPreset.api_key_required || config.provider === 'custom';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content config-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <Cpu size={18} /> Configurazione AI
          </div>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>

        {/* Test status */}
        {testStatus && testStatus.msg && (
          <div className={`test-status ${testStatus.ok === true ? 'ok' : testStatus.ok === false ? 'err' : ''}`}
               style={{ margin: '0 20px 12px' }}>
            {testStatus.msg}
          </div>
        )}

        {/* Provider selector */}
        <div className="config-provider-grid">
          {Object.entries(PROVIDER_PRESETS).map(([key, preset]) => (
            <button
              key={key}
              className={`provider-chip ${config.provider === key ? 'active' : ''}`}
              onClick={() => selectProvider(key)}
              title={preset.hint}
            >
              <span className="provider-chip-icon">
                {key === 'ollama' ? <Server size={14} /> : <Globe size={14} />}
              </span>
              <span className="provider-chip-label">{preset.label}</span>
            </button>
          ))}
        </div>

        <div className="config-grid">
          {/* Endpoint / API URL */}
          {config.provider === 'ollama' && (
            <label className="config-field">
              <span>Endpoint Ollama</span>
              <div className="config-field-row">
                <input
                  type="url"
                  value={config.endpoint}
                  onChange={e => setConfig(p => ({ ...p, endpoint: e.target.value }))}
                  placeholder="http://localhost:11434"
                />
                <button
                  className="btn-small"
                  onClick={fetchOllamaModels}
                  disabled={loadingModels}
                  title="Aggiorna lista modelli"
                >
                  <RefreshCw size={14} className={loadingModels ? 'spin' : ''} />
                </button>
              </div>
            </label>
          )}

          {config.provider !== 'ollama' && (
            <label className="config-field">
              <span>API URL</span>
              <input
                type="url"
                value={config.api_url}
                onChange={e => setConfig(p => ({ ...p, api_url: e.target.value }))}
                placeholder="https://api.openai.com/v1/chat/completions"
              />
              <span className="config-hint">{currentPreset.hint}</span>
            </label>
          )}

          {/* API Key */}
          {showApiKey && (
            <label className="config-field">
              <span><Key size={12} /> API Key</span>
              <input
                type="password"
                value={config.api_key}
                onChange={e => setConfig(p => ({ ...p, api_key: e.target.value }))}
                placeholder={config.has_api_key ? '•••••••• (key salvata)' : 'sk-...'}
              />
            </label>
          )}

          {/* Model - always a select dropdown */}
          <label className="config-field">
            <span>Modello</span>
            {config.provider === 'ollama' ? (
              ollamaModels.length > 0 ? (
                <select
                  value={config.model}
                  onChange={e => setConfig(p => ({ ...p, model: e.target.value }))}
                >
                  {ollamaModels.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <div className="config-field-row">
                  <select
                    value={config.model}
                    onChange={e => setConfig(p => ({ ...p, model: e.target.value }))}
                    style={{ flex: 1 }}
                  >
                    <option value={config.model}>{config.model || 'llama3.2'}</option>
                  </select>
                  <button className="btn-small" onClick={fetchOllamaModels} title="Carica modelli">
                    <RefreshCw size={14} className={loadingModels ? 'spin' : ''} />
                  </button>
                </div>
              )
            ) : (
              <select
                value={config.model}
                onChange={e => setConfig(p => ({ ...p, model: e.target.value }))}
                style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem' }}
              >
                {PROVIDER_PRESETS[config.provider]?.models?.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
                {config.model && !PROVIDER_PRESETS[config.provider]?.models?.includes(config.model) && (
                  <option value={config.model}>{config.model}</option>
                )}
              </select>
            )}
          </label>

          {/* Advanced params */}
          <div className="config-section-divider">
            <Sliders size={12} /> Parametri Avanzati
          </div>

          <div className="config-params-row">
            <label className="config-field config-field-compact" title="Controlla la creatività del modello. 0.1-0.3 = preciso e coerente (ideale per codice e analisi). 0.7 = bilanciato. 0.9-1.5 = creativo e divergente (brainstorming).">
              <span>Temperature</span>
              <div className="config-field-with-range">
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  value={config.temperature}
                  onChange={e => setConfig(p => ({ ...p, temperature: parseFloat(e.target.value) }))}
                  title="0.1-0.3 preciso | 0.7 bilanciato | 0.9+ creativo"
                />
                <span className="config-range-value">{(config.temperature ?? 0.7).toFixed(2)}</span>
              </div>
            </label>

            <label className="config-field config-field-compact" title="Nucleus sampling: filtra i token meno probabili. 0.1 = molto focalizzato, 0.9 = ampia varietà. Alza temperatura O top_p, non entrambi.">
              <span>Top P</span>
              <div className="config-field-with-range">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={config.top_p}
                  onChange={e => setConfig(p => ({ ...p, top_p: parseFloat(e.target.value) }))}
                  title="0.1 focalizzato | 0.5 medio | 0.9 vario"
                />
                <span className="config-range-value">{config.top_p.toFixed(2)}</span>
              </div>
            </label>

            <label className="config-field config-field-compact" title="Massimo token generati in risposta. 1-4K per chat veloci, 8-16K per analisi, 32K per documenti completi. Valori più alti = risposte più lunghe ma più lente.">
              <span>Max Tokens</span>
              <select
                value={config.max_tokens}
                onChange={e => setConfig(p => ({ ...p, max_tokens: parseInt(e.target.value) }))}
              >
                <option value={1024}>1K</option>
                <option value={2048}>2K</option>
                <option value={4096}>4K</option>
                <option value={8192}>8K</option>
                <option value={16384}>16K</option>
                <option value={32768}>32K</option>
              </select>
            </label>
          </div>

          <label className="config-field" title="Finestra di contesto: quanti token di conversazione il modello tiene in memoria. 2K per chat brevi, 8K per analisi, 16K+ per documenti estesi. Richiede RAM/VRAM proporzionale. Solo per Ollama (locale).">
            <span>Context (num_ctx)</span>
            <select
              value={config.num_ctx}
              onChange={e => setConfig(p => ({ ...p, num_ctx: parseInt(e.target.value) }))}
            >
              <option value={2048}>2K — Chat base</option>
              <option value={4096}>4K — Standard</option>
              <option value={8192}>8K — Analisi</option>
              <option value={16384}>16K — Documenti lunghi</option>
              <option value={32768}>32K — Ricerca approfondita</option>
            </select>
          </label>
        </div>

        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-primary" onClick={testConnection} disabled={saving || loadingModels}>
            <Database size={14} style={{ marginRight: 8 }} /> Test Connessione
          </button>
          <button className="btn-save" onClick={handleSave} disabled={saving || loadingModels}>
            <Save size={14} style={{ marginRight: 8 }} /> {saving ? 'Salvataggio...' : 'Salva'}
          </button>
        </div>
      </div>
    </div>
  );
}