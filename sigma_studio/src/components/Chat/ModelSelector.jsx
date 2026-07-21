import React, { useState, useMemo } from 'react';
import { Cpu, ChevronDown, Check, Loader, Search } from 'lucide-react';
import { PROVIDER_COLORS, getProviderForModel } from './modelProviderMap';

export default function ModelSelector({
  modelBtnRef, effectiveModelName, showDropdown, models,
  selectedModel, loadingModels, providerConfigs, onToggle, onSelect
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Group models by provider
  const modelsWithProvider = useMemo(() => {
    return (models || []).map(m => {
      const provider = getProviderForModel(m.name, providerConfigs) || 'ollama';
      return { ...m, provider };
    });
  }, [models, providerConfigs]);

  // Extract unique providers present in models
  const providerTabs = useMemo(() => {
    const counts = { all: modelsWithProvider.length };
    modelsWithProvider.forEach(m => {
      counts[m.provider] = (counts[m.provider] || 0) + 1;
    });
    const preferredOrder = ['all', 'ollama', 'deepseek', 'google', 'mistral', 'xai', 'perplexity', 'together', 'qwen', 'glm', 'moonshot', 'yi'];
    const availableProviders = Object.keys(counts).filter(p => p !== 'all');
    
    const sorted = preferredOrder.filter(p => p in counts);
    availableProviders.forEach(p => {
      if (!sorted.includes(p)) sorted.push(p);
    });

    return sorted.map(p => ({
      id: p,
      label: p === 'all' ? 'Tutti' : p.toUpperCase(),
      count: counts[p] || 0,
      color: p === 'all' ? '#00d2ff' : (PROVIDER_COLORS[p]?.color || '#8b8fa3')
    }));
  }, [modelsWithProvider]);

  // Filter models based on active tab and search query
  const filteredModels = useMemo(() => {
    return modelsWithProvider.filter(m => {
      const matchesTab = activeTab === 'all' || m.provider === activeTab;
      const matchesSearch = !searchQuery.trim() || m.name.toLowerCase().includes(searchQuery.toLowerCase().trim());
      return matchesTab && matchesSearch;
    });
  }, [modelsWithProvider, activeTab, searchQuery]);

  return (
    <div className="model-selector-wrapper" ref={modelBtnRef}>
      <button className={`model-selector-btn ${!effectiveModelName ? 'no-model' : ''}`} onClick={onToggle}>
        <Cpu size={12} />
        <span className="model-selector-name">{effectiveModelName || 'Scegli modello'}</span>
        <ChevronDown size={10} className={`model-selector-chevron ${showDropdown ? 'open' : ''}`} />
      </button>

      {showDropdown && (
        <div className="model-selector-popover tabbed-popover">
          {/* Search Bar */}
          <div className="model-selector-search-box">
            <Search size={12} className="search-icon" style={{ opacity: 0.6 }} />
            <input
              type="text"
              className="model-selector-search-input"
              placeholder="Cerca modello..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
            {searchQuery && (
              <button className="search-clear-btn" onClick={() => setSearchQuery('')}>✕</button>
            )}
          </div>

          {/* Provider Tabs Header */}
          <div className="model-selector-tabs-header">
            {providerTabs.map(tab => (
              <button
                key={tab.id}
                className={`model-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                onClick={(e) => { e.stopPropagation(); setActiveTab(tab.id); }}
                style={{ '--tab-color': tab.color }}
              >
                {tab.id !== 'all' && (
                  <span className="model-tab-dot" style={{ backgroundColor: tab.color }} />
                )}
                <span className="model-tab-label">{tab.label}</span>
                <span className="model-tab-count">{tab.count}</span>
              </button>
            ))}
          </div>

          {/* Models List */}
          <div className="model-selector-list">
            {loadingModels && (
              <div className="model-selector-loading">
                <Loader size={12} className="spin" /> Caricamento modelli...
              </div>
            )}
            {!loadingModels && filteredModels.length === 0 && (
              <div className="model-selector-empty">
                {searchQuery ? `Nessun modello per "${searchQuery}"` : 'Nessun modello in questa categoria'}
              </div>
            )}
            {!loadingModels && filteredModels.map(m => {
              const colors = PROVIDER_COLORS[m.provider] || PROVIDER_COLORS.ollama;
              const isSelected = selectedModel === m.name;
              return (
                <button
                  key={m.name}
                  className={`model-selector-option ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelect(m.name)}
                >
                  <span
                    className="model-selector-provider-dot"
                    style={{ backgroundColor: colors.color }}
                    title={m.provider}
                  />
                  <span className="model-selector-opt-name">{m.name}</span>
                  <span className="model-selector-provider-badge" style={{ backgroundColor: colors.bg, color: colors.color }}>
                    {m.provider}
                  </span>
                  {m.size && <span className="model-selector-opt-size">{m.size === 'API' ? m.size : m.size + 'GB'}</span>}
                  {isSelected && <Check size={12} className="model-selector-check" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}