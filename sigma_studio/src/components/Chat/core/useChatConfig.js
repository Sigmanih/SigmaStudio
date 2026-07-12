import { useState, useEffect, useCallback, useRef } from 'react';
import { saveLastModel } from '../chatStorage';

export function useChatConfig({ saveSessionsState, sessionRefs }) {
  const [selectedModel, setSelectedModel] = useState('');
  const [configModel, setConfigModel] = useState('llama3.2');
  const [configProvider, setConfigProvider] = useState('ollama');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [providerConfigs, setProviderConfigs] = useState({});
  const [activeManifesto, setActiveManifesto] = useState({ name: '', path: '', exists: false });
  const [manifestos, setManifestos] = useState([]);
  const [selectedManifestoPath, setSelectedManifestoPath] = useState('');
  const [manifestoManuallySelected, setManifestoManuallySelected] = useState(false);
  const [showManifestoDropdown, setShowManifestoDropdown] = useState(false);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showQuickConfig, setShowQuickConfig] = useState(false);

  // --- Quick config ---
  const [quickConfig, setQuickConfig] = useState({
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 0.9,
    top_k: 40,
    repeat_penalty: 1.1,
    num_ctx: 8192,
    seed: 0,
    timeout: 300
  });

  const refs = {
    manifestoManuallySelected: useRef(manifestoManuallySelected),
  };

  useEffect(() => { refs.manifestoManuallySelected.current = manifestoManuallySelected; }, [manifestoManuallySelected]);

  const fetchOllamaModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const res = await fetch('/api/ollama_models');
      const data = await res.json();
      let models = data.models?.length ? data.models : [];
      const known = new Set(models.map(m => m.name));
      if (providerConfigs) {
        Object.entries(providerConfigs).forEach(([, pv]) => {
          (pv.models || []).forEach(m => { if (!known.has(m)) { models.push({ name: m, size: 'API' }); known.add(m); } });
          if (pv.model && !known.has(pv.model)) { models.push({ name: pv.model, size: 'API' }); known.add(pv.model); }
        });
      }
      if (models.length > 0) setAvailableModels(models);
    } catch (e) {}
    if (availableModels.length === 0 && selectedModel) {
      setAvailableModels([{ name: selectedModel, size: configProvider !== 'ollama' ? 'API' : '' }]);
    }
    setLoadingModels(false);
  }, [providerConfigs, selectedModel, configProvider, availableModels.length]);

  const fetchConfigAndModels = useCallback(async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        if (d.config?.providers) setProviderConfigs(d.config.providers);
        if (d.config?.model) { setSelectedModel(d.config.model); setConfigModel(d.config.model); }
        if (d.config?.provider) setConfigProvider(d.config.provider);
        if (d.config?.manifesto && !refs.manifestoManuallySelected.current) {
          const m = d.config.manifesto;
          setActiveManifesto({ ...m, image: m.image || '/images/default.png' });
        }
      }
    } catch (e) {} finally { fetchOllamaModels(); }
  }, [fetchOllamaModels]);

  const refreshConfig = useCallback(async () => {
    try {
      const r = await fetch('/api/config');
      const d = await r.json();
      if (d.success) {
        if (d.config?.providers) setProviderConfigs(d.config.providers);
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
      if (data.success && data.files) {
        setManifestos(data.files.map(f => ({
          path: f.path,
          name: f.name.replace('.md', ''),
          filename: f.filename,
          image: f.image || '/images/default.png'
        })));
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

  const handleModelSelect = async (name) => {
    setSelectedModel(name);
    setShowModelDropdown(false);
    saveLastModel(name);
    if (sessionRefs && sessionRefs.activeSessionId?.current && saveSessionsState) {
      saveSessionsState(sessionRefs.sessions.current.map(s =>
        s.id === sessionRefs.activeSessionId.current
          ? { ...s, model: name, updatedAt: new Date().toISOString() }
          : s
      ));
    }
    try {
      const cfg = await (await fetch('/api/config')).json();
      if (cfg.success?.config) {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...cfg.config, model: name })
        });
      }
      await fetchOllamaModels();
    } catch (e) {}
  };

  return {
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
    setShowModelDropdown,
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
