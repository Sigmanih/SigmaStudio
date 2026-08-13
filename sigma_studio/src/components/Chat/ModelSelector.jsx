import React, { useState, useMemo } from 'react';
import { Cpu, ChevronDown, Check, Loader, Search, Key, Sparkles } from 'lucide-react';
import { PROVIDER_COLORS, getProviderForModel } from './modelProviderMap';

export default function ModelSelector({
  modelBtnRef, effectiveModelName, showDropdown, models,
  selectedModel, loadingModels, providerConfigs, onToggle, onSelect, onOpenConfig
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Group models by provider and STRICTLY FILTER to only available/configured providers:
  // - Ollama (locale): sempre attivo
  // - Cloud Providers: SOLO se l'utente ha inserito la chiave API (has_api_key o api_key) o endpoint custom
  const modelsWithProvider = useMemo(() => {
    return (models || [])
      .map(m => {
        const provider = m.provider || getProviderForModel(m.name, providerConfigs) || 'ollama';
        return { ...m, provider };
      })
      .filter(m => {
        if (m.provider === 'ollama') return true;
        const pCfg = providerConfigs?.[m.provider];
        return (
          pCfg?.has_api_key === true || 
          (pCfg?.api_key && pCfg?.api_key.trim().length > 0) || 
          (m.provider === 'custom' && (pCfg?.endpoint || pCfg?.api_url))
        );
      });
  }, [models, providerConfigs]);

  // Extract unique providers present in active models
  const providerTabs = useMemo(() => {
    const counts = { all: modelsWithProvider.length };
    modelsWithProvider.forEach(m => {
      counts[m.provider] = (counts[m.provider] || 0) + 1;
    });
    const preferredOrder = ['all', 'ollama', 'openai', 'anthropic', 'deepseek', 'google', 'groq', 'openrouter', 'mistral', 'xai', 'perplexity', 'together', 'qwen', 'glm', 'custom'];
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

  const handleOpenConfig = (e) => {
    e.stopPropagation();
    if (onOpenConfig) {
      onOpenConfig();
    } else {
      window.dispatchEvent(new CustomEvent('open-ai-config'));
    }
  };

  return (
    <div className="model-selector-wrapper" ref={modelBtnRef}>
      <button className={`model-selector-btn ${!effectiveModelName ? 'no-model' : ''}`} onClick={onToggle}>
        <Cpu size={12} />
        <span className="model-selector-name">{effectiveModelName || 'Scegli modello'}</span>
        <ChevronDown size={10} className={`model-selector-chevron ${showDropdown ? 'open' : ''}`} />
      </button>

      {showDropdown && (
        <div className="model-selector-popover tabbed-popover" style={{ minWidth: '280px' }}>
          {/* Search Bar */}
          <div className="model-selector-search-box">
            <Search size={12} className="search-icon" style={{ opacity: 0.6 }} />
            <input
              type="text"
              className="model-selector-search-input"
              placeholder="Cerca modello disponibile..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
            {searchQuery && (
              <button className="search-clear-btn" onClick={() => setSearchQuery('')}>✕</button>
            )}
          </div>

          {/* Provider Tabs Header (Only shows tabs for authenticated/configured providers) */}
          {providerTabs.length > 2 && (
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
          )}

          {/* Models List */}
          <div className="model-selector-list">
            {loadingModels && (
              <div className="model-selector-loading">
                <Loader size={12} className="spin" /> Caricamento modelli disponibili...
              </div>
            )}
            {!loadingModels && filteredModels.length === 0 && (
              <div className="model-selector-empty" style={{ padding: '16px 12px', textAlign: 'center' }}>
                <p style={{ margin: '0 0 8px 0', fontSize: '0.78rem' }}>
                  {searchQuery ? `Nessun modello per "${searchQuery}"` : 'Nessun modello attivo in questa categoria.'}
                </p>
                <button
                  onClick={handleOpenConfig}
                  style={{
                    background: 'rgba(0, 210, 255, 0.1)',
                    border: '1px solid rgba(0, 210, 255, 0.3)',
                    color: '#00d2ff',
                    padding: '4px 10px',
                    borderRadius: '8px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Configura Provider AI ⚙️
                </button>
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

          {/* Quick Footer for AI Configuration */}
          <div style={{
            padding: '8px 12px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(0, 0, 0, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px'
          }}>
            <span style={{ fontSize: '0.68rem', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={11} color="#3fb950" /> Solo modelli attivi
            </span>
            <button
              onClick={handleOpenConfig}
              style={{
                background: 'none',
                border: 'none',
                color: '#00d2ff',
                cursor: 'pointer',
                fontSize: '0.7rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                borderRadius: '6px'
              }}
            >
              <Key size={11} /> Gestisci Token & Accessi ⚙️
            </button>
          </div>
        </div>
      )}
    </div>
  );
}