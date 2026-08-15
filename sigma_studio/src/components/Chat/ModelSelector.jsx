import React, { useState, useMemo } from 'react';
import { Cpu, ChevronDown, Check, Loader, Search, Key, Sparkles } from 'lucide-react';
import { PROVIDER_COLORS, getProviderForModel } from './modelProviderMap';

export default function ModelSelector({
  modelBtnRef, effectiveModelName, showDropdown, models,
  selectedModel, loadingModels, providerConfigs, onToggle, onSelect, onOpenConfig,
  favoriteModel, favoriteModels, onSetFavorite
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const favList = useMemo(() => {
    if (Array.isArray(favoriteModels) && favoriteModels.length > 0) return favoriteModels;
    if (favoriteModel) return [favoriteModel];
    return [];
  }, [favoriteModels, favoriteModel]);

  const primaryFav = favList[0] || '';

  // Group models by provider and STRICTLY FILTER to only available/configured providers:
  // - Respect user-disabled providers (e.g. Ollama removed/disabled)
  // - SigmaEngine (nativo): sempre attivo
  // - Cloud Providers: SOLO se l'utente ha inserito la chiave API o endpoint custom
  const modelsWithProvider = useMemo(() => {
    const disabledMap = (() => {
      try {
        return JSON.parse(localStorage.getItem('sigma_disabled_providers') || '{}');
      } catch {
        return {};
      }
    })();

    return (models || [])
      .map(m => {
        const provider = m.provider || getProviderForModel(m.name, providerConfigs) || 'sigma_engine';
        return { ...m, provider };
      })
      .filter(m => {
        if (disabledMap[m.provider] === true) return false;
        if (m.provider === 'sigma_engine' || m.provider === 'sigma' || m.provider === 'ailoflow') return true;
        if (m.provider === 'ollama') return disabledMap.ollama !== true;
        const pCfg = providerConfigs?.[m.provider];
        return (
          pCfg?.has_api_key === true || 
          (pCfg?.api_key && pCfg?.api_key.trim().length > 0) || 
          (m.provider === 'custom' && (pCfg?.endpoint || pCfg?.api_url))
        );
      });
  }, [models, providerConfigs]);


  // Extract unique providers present in active models + ⭐ PREFERITI Tab
  const providerTabs = useMemo(() => {
    const counts = { all: modelsWithProvider.length };
    const favCount = modelsWithProvider.filter(m => favList.includes(m.name)).length;
    counts.favorites = favCount;

    modelsWithProvider.forEach(m => {
      counts[m.provider] = (counts[m.provider] || 0) + 1;
    });
    const preferredOrder = ['favorites', 'all', 'sigma_engine', 'ollama', 'ailoflow', 'deepseek', 'openai', 'anthropic', 'google', 'groq', 'openrouter', 'mistral', 'xai', 'perplexity', 'together', 'qwen', 'glm', 'custom'];
    const availableProviders = Object.keys(counts).filter(p => p !== 'all' && p !== 'favorites');
    
    const sorted = preferredOrder.filter(p => p in counts);
    availableProviders.forEach(p => {
      if (!sorted.includes(p)) sorted.push(p);
    });

    const getTabLabel = (p) => {
      if (p === 'favorites') return '⭐ Preferiti';
      if (p === 'all') return 'Tutti';
      if (p === 'sigma_engine' || p === 'sigma') return '⚡ SIGMA';
      if (p === 'ailoflow') return '🌊 AILOFLOW';
      if (p === 'ollama') return '🦙 OLLAMA';
      return p.toUpperCase();
    };

    return sorted.map(p => ({
      id: p,
      label: getTabLabel(p),
      count: counts[p] || 0,
      color: p === 'favorites' ? '#facc15' : (p === 'all' ? '#00d2ff' : (PROVIDER_COLORS[p]?.color || '#8b8fa3'))
    }));
  }, [modelsWithProvider, favList]);


  // Filter models based on active tab and search query
  const filteredModels = useMemo(() => {
    return modelsWithProvider.filter(m => {
      let matchesTab = true;
      if (activeTab === 'favorites') {
        matchesTab = favList.includes(m.name);
      } else if (activeTab !== 'all') {
        matchesTab = m.provider === activeTab;
      }
      const matchesSearch = !searchQuery.trim() || m.name.toLowerCase().includes(searchQuery.toLowerCase().trim());
      return matchesTab && matchesSearch;
    });
  }, [modelsWithProvider, activeTab, searchQuery, favList]);

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
        <div className="model-selector-popover tabbed-popover" style={{ minWidth: '310px' }}>
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

          {/* Quick Favorite Suggestion Bar */}
          {primaryFav && activeTab !== 'favorites' && (
            <div 
              className="model-selector-favorite-suggestion"
              onClick={() => onSelect(primaryFav)}
              style={{
                margin: '6px 8px 4px',
                padding: '6px 10px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, rgba(234, 179, 8, 0.15) 0%, rgba(202, 138, 4, 0.08) 100%)',
                border: '1px solid rgba(234, 179, 8, 0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              title="Clicca per selezionare il modello preferito predefinito"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                <span style={{ fontSize: '0.9rem' }}>⭐</span>
                <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                  <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Suggerito (Predefinito)
                  </span>
                  <span style={{ fontSize: '0.74rem', fontWeight: 600, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {primaryFav}
                  </span>
                </div>
              </div>
              <span style={{
                fontSize: '0.66rem',
                padding: '2px 8px',
                borderRadius: '5px',
                background: selectedModel === primaryFav ? 'rgba(34, 197, 94, 0.2)' : 'rgba(234, 179, 8, 0.25)',
                color: selectedModel === primaryFav ? '#4ade80' : '#facc15',
                border: selectedModel === primaryFav ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid rgba(234, 179, 8, 0.4)',
                fontWeight: 700,
                flexShrink: 0
              }}>
                {selectedModel === primaryFav ? '✓ In Uso' : 'Usa Ora ⚡'}
              </span>
            </div>
          )}

          {/* Provider Tabs Header (Includes ⭐ Preferiti, Tutti, and configured providers) */}
          <div className="model-selector-tabs-header">
            {providerTabs.map(tab => (
              <button
                key={tab.id}
                className={`model-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                onClick={(e) => { e.stopPropagation(); setActiveTab(tab.id); }}
                style={{ '--tab-color': tab.color }}
              >
                {tab.id !== 'all' && tab.id !== 'favorites' && (
                  <span className="model-tab-dot" style={{ backgroundColor: tab.color }} />
                )}
                <span className="model-tab-label">{tab.label}</span>
                <span className="model-tab-count" style={{
                  backgroundColor: tab.id === 'favorites' ? 'rgba(234, 179, 8, 0.2)' : undefined,
                  color: tab.id === 'favorites' ? '#facc15' : undefined
                }}>{tab.count}</span>
              </button>
            ))}
          </div>

          {/* Models List */}
          <div className="model-selector-list">
            {loadingModels && (
              <div className="model-selector-loading">
                <Loader size={12} className="spin" /> Caricamento modelli disponibili...
              </div>
            )}
            {!loadingModels && filteredModels.length === 0 && (
              activeTab === 'favorites' ? (
                <div className="model-selector-empty" style={{ padding: '20px 14px', textAlign: 'center' }}>
                  <span style={{ fontSize: '1.4rem', display: 'block', marginBottom: '6px' }}>⭐</span>
                  <p style={{ margin: '0 0 6px 0', fontSize: '0.78rem', fontWeight: '700', color: '#facc15' }}>
                    {searchQuery ? `Nessun preferito per "${searchQuery}"` : 'Nessun modello tra i preferiti'}
                  </p>
                  <p style={{ margin: '0', fontSize: '0.72rem', opacity: 0.7, lineHeight: 1.4 }}>
                    Clicca sulla stellina <b>☆</b> accanto a qualsiasi modello per aggiungerlo alla tua selezione rapida.
                  </p>
                </div>
              ) : (
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
              )
            )}
            {!loadingModels && filteredModels.map(m => {
              const colors = PROVIDER_COLORS[m.provider] || PROVIDER_COLORS.ollama;
              const isSelected = selectedModel === m.name;
              const isFavorite = favList.includes(m.name);
              const isPrimary = m.name === primaryFav;
              return (
                <div
                  key={m.name}
                  className={`model-selector-option ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelect(m.name)}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                    <button
                      className="model-star-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onSetFavorite) onSetFavorite(m.name);
                      }}
                      title={isFavorite ? (isPrimary ? "Modello preferito predefinito (Clicca per rimuovere dai preferiti)" : "Modello preferito (Clicca per rimuovere)") : "Aggiungi ai modelli preferiti"}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: '2px 4px',
                        fontSize: '0.85rem',
                        lineHeight: 1,
                        color: isFavorite ? '#facc15' : 'rgba(255, 255, 255, 0.25)',
                        transition: 'transform 0.15s ease, color 0.15s ease',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                      onMouseEnter={(e) => { if (!isFavorite) e.currentTarget.style.color = '#facc15'; }}
                      onMouseLeave={(e) => { if (!isFavorite) e.currentTarget.style.color = 'rgba(255, 255, 255, 0.25)'; }}
                    >
                      {isFavorite ? '⭐' : '☆'}
                    </button>
                    <span
                      className="model-selector-provider-dot"
                      style={{ backgroundColor: colors.color }}
                      title={m.provider}
                    />
                    <span className="model-selector-opt-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
                    {isPrimary && (
                      <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#facc15', background: 'rgba(234, 179, 8, 0.15)', padding: '1px 5px', borderRadius: '4px', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                        Default
                      </span>
                    )}
                    {isFavorite && !isPrimary && (
                      <span style={{ fontSize: '0.62rem', fontWeight: 700, color: '#facc15', background: 'rgba(234, 179, 8, 0.1)', padding: '1px 5px', borderRadius: '4px', border: '1px solid rgba(234, 179, 8, 0.2)' }}>
                        ⭐
                      </span>
                    )}
                    <span className="model-selector-provider-badge" style={{ backgroundColor: colors.bg, color: colors.color }}>
                      {m.provider}
                    </span>
                    {m.size && <span className="model-selector-opt-size">{m.size === 'API' ? m.size : m.size + 'GB'}</span>}
                    {isSelected && <Check size={12} className="model-selector-check" />}
                  </div>
                </div>
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