import { useState, useEffect, useCallback, useRef } from 'react';
import { saveLastModel } from '../chatStorage';
import { registerLocalModels } from './modelSpecsHelper';

export function useChatConfig({ saveSessionsState, sessionRefs }) {
  const [favoriteModels, setFavoriteModels] = useState(() => {
    try {
      const stored = localStorage.getItem('sigma_favorite_models');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
      const single = localStorage.getItem('sigma_favorite_model');
      if (single) return [single];
      return [];
    } catch (e) {
      return [];
    }
  });

  const favoriteModel = favoriteModels[0] || '';
  const [selectedModel, setSelectedModel] = useState(() => {
    try {
      const lastUsed = localStorage.getItem('sigma_last_selected_model') || localStorage.getItem('sigma_selected_model');
      if (lastUsed) return lastUsed;
      const stored = localStorage.getItem('sigma_favorite_models');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed[0];
      }
      return localStorage.getItem('sigma_favorite_model') || '';
    } catch (e) {
      return '';
    }
  });
  const [configModel, setConfigModel] = useState('');
  const [configProvider, setConfigProvider] = useState('ollama');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [providerConfigs, setProviderConfigs] = useState({});
  const [activeManifesto, setActiveManifesto] = useState({ name: 'Sigma Assistant', path: 'manifesti/sigma_assistant.md', exists: true, image: '/images/default.png' });
  const [manifestos, setManifestos] = useState([]);
  const [selectedManifestoPath, setSelectedManifestoPath] = useState('manifesti/sigma_assistant.md');
  const [manifestoManuallySelected, setManifestoManuallySelected] = useState(false);
  const [showManifestoDropdown, setShowManifestoDropdown] = useState(false);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showQuickConfig, setShowQuickConfig] = useState(false);

  // --- Quick config ---
  const [quickConfig, setQuickConfig] = useState({
    temperature: 0.7,
    max_tokens: 16384,
    top_p: 0.95,
    top_k: 40,
    repeat_penalty: 1.1,
    num_ctx: 32768,
    seed: 0,
    timeout: 300
  });

  const refs = {
    manifestoManuallySelected: useRef(manifestoManuallySelected),
  };

  useEffect(() => { refs.manifestoManuallySelected.current = manifestoManuallySelected; }, [manifestoManuallySelected]);

  // The SIGMA list is whatever is actually installed under the models
  // directory, nothing more. It used to be seeded with a fixed roster of
  // placeholder names (sigma-native, llama4:16x17b, deepseek-r1:70b...) that
  // existed nowhere on disk: selecting one produced a load failure, and they
  // buried the real models the user had just downloaded or converted.
  const SIGMA_NATIVE_MODELS = [];

  const fetchOllamaModels = useCallback(async (customConfigs) => {
    setLoadingModels(true);
    try {
      const pConfigs = customConfigs || providerConfigs;
      const isOllamaExplicitlyEnabled = pConfigs?.ollama?.enabled === true;

      let models = [...SIGMA_NATIVE_MODELS];
      const known = new Set(models.map(m => m.name));

      // 1. Fetch Local Models downloaded via Modelli Locali & Storage (SigmaEngine / Local Storage)
      try {
        const localRes = await fetch('/api/models/local/list');
        if (localRes.ok) {
          const localJson = await localRes.json();
          if (localJson.success && Array.isArray(localJson.models)) {
            registerLocalModels(localJson.models);
            localJson.models.forEach(m => {
              const mName = m.display_name || m.filename || m.model_id;
              if (!known.has(mName)) {
                models.unshift({
                  ...m,
                  name: mName,
                  filename: m.filename,
                  model_id: m.model_id,
                  display_name: m.display_name,
                  size: m.size_label || (m.size_gb ? `~${m.size_gb} GB` : 'Locale'),
                  size_gb: m.size_gb,
                  size_label: m.size_label,
                  provider: 'sigma_engine',
                  path: m.path,
                  format: m.format,
                  format_tag: m.format_tag,
                  quantization: m.quantization,
                  est_vram_gb: m.est_vram_gb,
                  benchmark_summary: m.benchmark_summary,
                  family: m.family,
                  publisher: m.publisher,
                  category: m.category,
                  is_local_hub: true
                });
                known.add(mName);
              }
            });

          }
        }
      } catch (locErr) {
        console.warn("Modelli Locali fetching error:", locErr);
      }

      // 2. Fetch external Ollama ONLY IF explicitly configured & enabled by user
      if (isOllamaExplicitlyEnabled) {
        try {
          const res = await fetch('/api/ollama_models');
          const data = await res.json();
          let fetchedModels = data.models?.length ? data.models : [];

          fetchedModels.forEach(m => {
            const mName = m.name || m;
            if (!known.has(mName)) {
              models.push({ name: mName, size: m.size || 'External', provider: 'ollama' });
              known.add(mName);
            }
          });
        } catch (fetchErr) {
          console.warn("Ollama esterno non raggiungibile:", fetchErr);
        }
      }


      
      if (pConfigs) {
        Object.entries(pConfigs).forEach(([pk, pv]) => {
          // Ollama and Sigma models are already included
          if (pk === 'ollama' || pk === 'sigma_engine' || pk === 'sigma') return;

          // For all cloud/external providers, ONLY add models IF configured (has_api_key or api_key present or custom endpoint)
          const isConfigured = pv?.has_api_key === true || (pv?.api_key && pv?.api_key.trim().length > 0) || (pk === 'custom' && (pv?.endpoint || pv?.api_url));
          if (!isConfigured) return;

          if (pv.model && !known.has(pv.model)) {
            models.push({ name: pv.model, size: 'API', provider: pk });
            known.add(pv.model);
          }
          (pv.models || []).forEach(m => {
            if (!known.has(m)) {
              models.push({ name: m, size: 'API', provider: pk });
              known.add(m);
            }
          });
        });
      }
      setAvailableModels(models);
    } catch (e) {
      console.error("Errore recupero modelli:", e);
      setAvailableModels([...SIGMA_NATIVE_MODELS]);
    } finally {
      setLoadingModels(false);
    }
  }, [providerConfigs]);


  const fetchConfigAndModels = useCallback(async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        const provs = d.config?.providers || {};
        setProviderConfigs(provs);
        let favs = [];
        try {
          const stored = localStorage.getItem('sigma_favorite_models');
          if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed) && parsed.length > 0) favs = parsed;
          }
          if (favs.length === 0) {
            const single = localStorage.getItem('sigma_favorite_model');
            if (single) favs = [single];
          }
        } catch (e) {}

        if (favs.length === 0 && d.config?.favorite_models && Array.isArray(d.config.favorite_models) && d.config.favorite_models.length > 0) {
          favs = d.config.favorite_models;
        } else if (favs.length === 0 && d.config?.favorite_model) {
          favs = [d.config.favorite_model];
        }

        const lastUsed = (() => {
          try { return localStorage.getItem('sigma_last_selected_model') || localStorage.getItem('sigma_selected_model') || ''; } catch (e) { return ''; }
        })();
        let initialModel = '';
        if (lastUsed) {
          initialModel = lastUsed;
        } else if (favs.length > 0) {
          initialModel = favs[0];
        } else if (d.config?.model) {
          initialModel = d.config.model;
        }

        if (favs.length > 0) {
          setFavoriteModels(favs);
        }
        if (initialModel) {
          setSelectedModel(prev => prev || initialModel);
          setConfigModel(initialModel);
        }
        if (d.config?.provider) setConfigProvider(d.config.provider);
        if (d.config?.manifesto && !refs.manifestoManuallySelected.current) {
          const m = d.config.manifesto;
          setActiveManifesto({ ...m, image: m.image || '/images/default.png' });
        }
        await fetchOllamaModels(provs);
      } else {
        await fetchOllamaModels();
      }
    } catch (e) {
      const fallback = (() => {
        try { return localStorage.getItem('sigma_last_selected_model') || ''; } catch (e) { return ''; }
      })();
      if (fallback) {
        setSelectedModel(prev => prev || fallback);
        setConfigModel(fallback);
      }
      setConfigProvider('ollama');
      await fetchOllamaModels();
    }
  }, [fetchOllamaModels]);

  const refreshConfig = useCallback(async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        if (d.config?.providers) setProviderConfigs(d.config.providers);
        if (d.config?.favorite_models && Array.isArray(d.config.favorite_models)) {
          setFavoriteModels(d.config.favorite_models);
        } else if (d.config?.favorite_model) {
          setFavoriteModels([d.config.favorite_model]);
        }
        if (d.config?.model) setConfigModel(d.config.model);
        if (d.config?.provider) setConfigProvider(d.config.provider);
        setQuickConfig(prev => ({
          ...prev,
          temperature: d.config?.temperature ?? 0.7,
          max_tokens: d.config?.max_tokens ?? 32768,
          top_p: d.config?.top_p ?? 0.9,
          top_k: d.config?.top_k ?? 40,
          repeat_penalty: d.config?.repeat_penalty ?? 1.1,
          num_ctx: d.config?.num_ctx ?? 32768,
          seed: d.config?.seed ?? 0,
          timeout: d.config?.timeout ?? 300
        }));
        if (d.config?.manifesto && !refs.manifestoManuallySelected.current) {
          const m = d.config.manifesto;
          setActiveManifesto({ ...m, image: m.image || '/images/default.png' });
        }
      }
    } catch (e) {}
  }, []);

  const fetchManifestos = useCallback(async () => {
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      const files = data.manifesti || data.files || [];
      if (data.success && files) {
        const loaded = files.map(f => ({
          path: f.path,
          name: f.name || f.filename?.replace('.md', ''),
          filename: f.filename,
          image: f.image || '/images/default.png',
          role: f.role || '',
          domainColor: f.domainColor || '#00d2ff'
        }));
        setManifestos([
          { path: 'auto', name: 'auto', filename: 'auto.md', image: '/images/default.png', role: 'Centralino Automatico' },
          ...loaded
        ]);
      }
    } catch (e) {}
  }, []);

  const saveQuickConfig = async (key, value) => {
    const updated = { ...quickConfig, [key]: value };
    setQuickConfig(updated);
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
    } catch (e) {}
  };

  const handleToggleFavoriteModel = (modelName) => {
    if (!modelName) return;
    setFavoriteModels(prev => {
      let newFavs = [];
      if (prev.includes(modelName)) {
        newFavs = prev.filter(m => m !== modelName);
      } else {
        newFavs = [...prev, modelName];
      }
      try {
        localStorage.setItem('sigma_favorite_models', JSON.stringify(newFavs));
        if (newFavs.length > 0) {
          localStorage.setItem('sigma_favorite_model', newFavs[0]);
        } else {
          localStorage.removeItem('sigma_favorite_model');
        }
      } catch (e) {}

      (async () => {
        try {
          const r = await fetch('/api/config');
          const d = await r.json();
          if (d.success && d.config) {
            await fetch('/api/config', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                ...d.config,
                favorite_models: newFavs,
                favorite_model: newFavs[0] || '',
                model: selectedModel || newFavs[0] || d.config.model
              })
            });
          }
        } catch (e) {}
      })();

      return newFavs;
    });
  };

  const handleModelSelect = async (name) => {
    setSelectedModel(name);
    setShowModelDropdown(false);
    saveLastModel(name);
    try {
      localStorage.setItem('sigma_last_selected_model', name);
      localStorage.setItem('sigma_selected_model', name);
    } catch (e) {}
    if (sessionRefs && sessionRefs.activeSessionId?.current && saveSessionsState) {
      saveSessionsState(sessionRefs.sessions.current.map(s =>
        s.id === sessionRefs.activeSessionId.current
          ? { ...s, model: name, updatedAt: new Date().toISOString() }
          : s
      ));
    }
    try {
      const cfg = await (await fetch('/api/config')).json();
      if (cfg.success && cfg.config) {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...cfg.config, model: name, active_model: name })
        });
      }
      await fetchOllamaModels();
    } catch (e) {}
  };

  const handleToggleModelDropdown = useCallback((valOrFn) => {
    setShowModelDropdown(prev => {
      const next = typeof valOrFn === 'function' ? valOrFn(prev) : valOrFn;
      if (next && !prev) {
        // Refresh live dei modelli all'apertura del dropdown
        fetchOllamaModels();
      }
      return next;
    });
  }, [fetchOllamaModels]);

  useEffect(() => {
    const handleConfigUpdated = () => {
      fetchConfigAndModels();
    };
    const handleModelsUpdated = () => {
      fetchOllamaModels();
    };
    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === 'visible') {
        fetchOllamaModels();
      }
    };

    window.addEventListener('ai-config-updated', handleConfigUpdated);
    window.addEventListener('models-updated', handleModelsUpdated);
    window.addEventListener('visibilitychange', handleVisibilityOrFocus);
    window.addEventListener('focus', handleVisibilityOrFocus);

    return () => {
      window.removeEventListener('ai-config-updated', handleConfigUpdated);
      window.removeEventListener('models-updated', handleModelsUpdated);
      window.removeEventListener('visibilitychange', handleVisibilityOrFocus);
      window.removeEventListener('focus', handleVisibilityOrFocus);
    };
  }, [fetchConfigAndModels, fetchOllamaModels]);

  return {
    favoriteModel,
    favoriteModels,
    setFavoriteModels,
    handleSetFavoriteModel: handleToggleFavoriteModel,
    handleToggleFavoriteModel,
    selectedModel,
    setSelectedModel,
    configModel,
    setConfigModel,
    configProvider,
    setConfigProvider,
    availableModels,
    setAvailableModels,
    loadingModels,
    setLoadingModels,
    providerConfigs,
    setProviderConfigs,
    activeManifesto,
    setActiveManifesto,
    manifestos,
    setManifestos,
    selectedManifestoPath,
    setSelectedManifestoPath,
    manifestoManuallySelected,
    setManifestoManuallySelected,
    showManifestoDropdown,
    setShowManifestoDropdown,
    showModelDropdown,
    setShowModelDropdown: handleToggleModelDropdown,
    showQuickConfig,
    setShowQuickConfig,
    quickConfig,
    setQuickConfig,
    fetchOllamaModels,
    fetchConfigAndModels,
    refreshConfig,
    fetchManifestos,
    saveQuickConfig,
    handleModelSelect,
    configRefs: refs
  };
}
