import React, { useState, useMemo, useEffect } from 'react';
import {
  Cpu, ChevronDown, Check, Loader, Search, Key, Sparkles, HardDrive, Zap,
  Trophy, Award, Gauge, Brain, Dna, Boxes, ArrowDownUp, RefreshCw
} from 'lucide-react';
import { PROVIDER_COLORS, getProviderForModel } from './modelProviderMap';
import {
  getModelSpecs, detectModelFamily, isSigmanihModel, getModelChatSpeed,
  sortModelsList, FAMILY_CONFIG
} from './core/modelSpecsHelper';

const SORT_OPTIONS = [
  { id: 'default', label: 'Default', icon: Boxes, title: 'Ordinamento predefinito' },
  { id: 'size', label: 'Peso', icon: HardDrive, title: 'Ordina per dimensione file / VRAM (GB)' },
  { id: 'params', label: 'Parametri', icon: Cpu, title: 'Ordina per conteggio parametri (es. 70B > 32B > 7B)' },
  { id: 'speed', label: 't/s', icon: Zap, title: 'Ordina per velocità live di inferenza (tokens/sec)' },
  { id: 'benchmark', label: 'Benchmark', icon: Trophy, title: 'Ordina per punteggio di benchmark (%)' },
  { id: 'name', label: 'Nome', icon: null, title: 'Ordina alfabeticamente per nome modello' }
];


export default function ModelSelector({
  modelBtnRef, effectiveModelName, showDropdown, models,
  selectedModel, loadingModels, providerConfigs, onToggle, onSelect, onOpenConfig,
  favoriteModel, favoriteModels, onSetFavorite
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [familyFilter, setFamilyFilter] = useState('all');
  const [sortBy, setSortBy] = useState('default');
  const [sortOrder, setSortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [speedVersion, setSpeedVersion] = useState(0);

  const handleSortChange = (newSort) => {
    if (sortBy === newSort) {
      setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(newSort);
      setSortOrder(newSort === 'name' ? 'asc' : 'desc');
    }
  };

  // Listen to live model speed updates after chatting
  useEffect(() => {
    const handleSpeedUpdated = () => {
      setSpeedVersion(v => v + 1);
    };
    window.addEventListener('sigma-model-speed-updated', handleSpeedUpdated);
    return () => window.removeEventListener('sigma-model-speed-updated', handleSpeedUpdated);
  }, []);

  const activeSpecs = useMemo(() => {
    return getModelSpecs(effectiveModelName || selectedModel, models);
  }, [effectiveModelName, selectedModel, models, speedVersion]);

  const favList = useMemo(() => {
    if (Array.isArray(favoriteModels) && favoriteModels.length > 0) return favoriteModels;
    if (favoriteModel) return [favoriteModel];
    return [];
  }, [favoriteModels, favoriteModel]);

  const primaryFav = favList[0] || '';

  // Group models by provider and strictly filter to only configured/available providers
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
        const family = detectModelFamily(m);
        return { ...m, provider, family };
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

  // Compute models matching the active provider tab and search query for family counting
  const modelsInCurrentTab = useMemo(() => {
    return modelsWithProvider.filter(m => {
      let matchesTab = true;
      if (activeTab === 'favorites') {
        matchesTab = favList.includes(m.name);
      } else if (activeTab !== 'all') {
        matchesTab = m.provider === activeTab;
      }
      return matchesTab;
    });
  }, [modelsWithProvider, activeTab, favList]);

  // Compute available families for the family filter bar
  const familyPills = useMemo(() => {
    const counts = { all: modelsInCurrentTab.length };
    counts.sigmanih = modelsInCurrentTab.filter(m => isSigmanihModel(m)).length;

    modelsInCurrentTab.forEach(m => {
      const fam = detectModelFamily(m);
      if (fam !== 'sigmanih') {
        counts[fam] = (counts[fam] || 0) + 1;
      }
    });

    const familyKeys = ['all', 'sigmanih', 'gemma', 'qwen', 'llama', 'deepseek', 'mistral', 'phi', 'glm', 'altro'];
    
    return familyKeys
      .filter(k => k === 'all' || (counts[k] && counts[k] > 0))
      .map(k => {
        if (k === 'all') {
          return {
            id: 'all',
            title: 'Tutte',
            count: counts.all || 0,
            color: '#00d2ff',
            bg: 'rgba(0, 210, 255, 0.15)',
            border: 'rgba(0, 210, 255, 0.35)'
          };
        }
        const conf = FAMILY_CONFIG[k] || FAMILY_CONFIG.altro;
        return {
          id: k,
          title: conf.title,
          count: counts[k] || 0,
          color: conf.color,
          bg: conf.bg,
          border: conf.border
        };
      });
  }, [modelsInCurrentTab]);

  // Filter and sort models based on active provider tab, family filter, search query, and sort criteria
  const filteredAndSortedModels = useMemo(() => {
    const filtered = modelsWithProvider.filter(m => {
      let matchesTab = true;
      if (activeTab === 'favorites') {
        matchesTab = favList.includes(m.name);
      } else if (activeTab !== 'all') {
        matchesTab = m.provider === activeTab;
      }

      let matchesFamily = true;
      if (familyFilter !== 'all') {
        if (familyFilter === 'sigmanih') {
          matchesFamily = isSigmanihModel(m);
        } else {
          matchesFamily = (detectModelFamily(m) === familyFilter);
        }
      }

      const matchesSearch = !searchQuery.trim() || m.name.toLowerCase().includes(searchQuery.toLowerCase().trim());
      
      return matchesTab && matchesFamily && matchesSearch;
    });

    return sortModelsList(filtered, sortBy, sortOrder, models);
  }, [modelsWithProvider, activeTab, familyFilter, searchQuery, favList, sortBy, sortOrder, models]);


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
        
        {activeSpecs?.chatSpeed !== null && activeSpecs?.chatSpeed !== undefined && (
          <span
            className="model-spec-badge"
            title={`Velocità live misurata: ${activeSpecs.chatSpeed} tok/s`}
            style={{
              fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
              background: 'rgba(0, 210, 255, 0.16)', color: '#00d2ff', fontWeight: 800,
              display: 'inline-flex', alignItems: 'center', gap: '2px', whiteSpace: 'nowrap'
            }}
          >
            ⚡ {activeSpecs.chatSpeed} t/s
          </span>
        )}

        {activeSpecs?.params && (
          <span className="model-spec-badge" style={{ fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(0, 210, 255, 0.16)', color: '#00d2ff', fontWeight: 800, whiteSpace: 'nowrap' }}>
            ⚡ {activeSpecs.params}
          </span>
        )}
        {activeSpecs?.size && (
          <span className="model-spec-badge" style={{ fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 800, whiteSpace: 'nowrap' }}>
            💾 {activeSpecs.size}
          </span>
        )}
        <ChevronDown size={10} className={`model-selector-chevron ${showDropdown ? 'open' : ''}`} />
      </button>

      {showDropdown && (
        <div className="model-selector-popover tabbed-popover" style={{ left: 0, right: 'auto', transform: 'none' }}>
          {/* Search Bar */}
          <div className="model-selector-search-box">
            <Search size={12} className="search-icon" style={{ opacity: 0.6 }} />
            <input
              type="text"
              className="model-selector-search-input"
              placeholder="Cerca modello disponibile per nome, tag o architettura..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
            />
            {searchQuery && (
              <button className="search-clear-btn" onClick={() => setSearchQuery('')} title="Cancella ricerca">✕</button>
            )}
            <button
              className="search-clear-btn"
              title="Riscansiona modelli da tutte le cartelle (store/models e cartelle collegate)"
              onClick={(e) => {
                e.stopPropagation();
                try {
                  window.dispatchEvent(new CustomEvent('models-updated'));
                  window.dispatchEvent(new CustomEvent('ai-config-updated'));
                } catch (err) {}
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#00d2ff',
                cursor: 'pointer',
                padding: '2px 5px',
                display: 'flex',
                alignItems: 'center',
                opacity: 0.85
              }}
            >
              <RefreshCw size={11} className={loadingModels ? "spin" : ""} />
            </button>
          </div>

          {/* Provider Tabs Header (Includes ⭐ Preferiti, Tutti, and configured providers) */}
          <div className="model-selector-tabs-header">
            {providerTabs.map(tab => (
              <button
                key={tab.id}
                className={`model-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveTab(tab.id);
                }}
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

          {/* 🧬 Family Filter Pill Bar */}
          {familyPills.length > 1 && (
            <div className="model-selector-family-bar">
              <span style={{ fontSize: '0.60rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginRight: '3px' }}>
                Famiglia:
              </span>
              {familyPills.map(fam => {
                const isActive = familyFilter === fam.id;
                return (
                  <button
                    key={fam.id}
                    type="button"
                    className={`model-family-pill ${isActive ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setFamilyFilter(fam.id);
                    }}
                    style={{
                      '--family-color': fam.color,
                      '--family-bg': fam.bg,
                      '--family-glow': `${fam.color}40`
                    }}
                  >
                    <span>{fam.title}</span>
                    <span className="model-family-pill-count">{fam.count}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* 🔀 Sorting Bar (Peso, Parametri, t/s, Benchmark, Nome) */}
          <div className="model-selector-sort-bar">
            <span style={{ fontSize: '0.60rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginRight: '3px', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <ArrowDownUp size={10} color="#00d2ff" /> Ordina:
            </span>
            {SORT_OPTIONS.map(opt => {
              const isActive = sortBy === opt.id;
              const IconComponent = opt.icon;
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`model-sort-pill ${isActive ? 'active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSortChange(opt.id);
                  }}
                  title={opt.title}
                >
                  {IconComponent && <IconComponent size={10} />}
                  <span>{opt.label}</span>
                  {isActive && opt.id !== 'default' && (
                    <span className="model-sort-pill-indicator">
                      {sortOrder === 'desc' ? '↓' : '↑'}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Models List */}
          <div className="model-selector-list">
            {loadingModels && (
              <div className="model-selector-loading">
                <Loader size={12} className="spin" /> Caricamento modelli disponibili...
              </div>
            )}
            {!loadingModels && filteredAndSortedModels.length === 0 && (
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
                    {searchQuery ? `Nessun modello per "${searchQuery}"` : 'Nessun modello trovato per i filtri selezionati.'}
                  </p>
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                    {familyFilter !== 'all' && (
                      <button
                        onClick={() => setFamilyFilter('all')}
                        style={{
                          background: 'rgba(255, 255, 255, 0.06)',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#fff',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          fontSize: '0.70rem',
                          cursor: 'pointer'
                        }}
                      >
                        Azzera filtro famiglia
                      </button>
                    )}
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
                </div>
              )
            )}
            {!loadingModels && filteredAndSortedModels.map(m => {
              const colors = PROVIDER_COLORS[m.provider] || PROVIDER_COLORS.ollama;
              const isSelected = selectedModel === m.name;
              const isFavorite = favList.includes(m.name);
              const isPrimary = m.name === primaryFav;
              const itemSpecs = getModelSpecs(m.name, models);
              const isSig = isSigmanihModel(m);
              const famKey = detectModelFamily(m);
              const familyConf = FAMILY_CONFIG[famKey] || FAMILY_CONFIG.altro;

              // Benchmark metrics
              const bm = m.benchmark_summary || itemSpecs?.benchmark || null;
              const hasBm = Boolean(bm && (bm.has_benchmarks || bm.score !== undefined || bm.overall_pass_rate !== undefined));
              const bmScore = hasBm ? (bm.score ?? bm.overall_pass_rate ?? bm.best_score ?? 0) : null;
              const bmColor = bmScore !== null ? (bmScore >= 75 ? '#10b981' : (bmScore >= 50 ? '#00d2ff' : '#ffb86c')) : '#8b8fa3';

              // Live Speed (tokens/sec)
              const chatTps = getModelChatSpeed(m.name, m) ?? (m.benchmark_summary?.tokens_per_sec || null);

              return (
                <div
                  key={m.name}
                  className={`model-selector-option ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelect(m.name)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    gap: '8px', cursor: 'pointer', padding: '7px 10px',
                    borderRadius: '8px', transition: 'all 0.15s ease'
                  }}
                >
                  {/* Left part: Star + Provider dot + Family chip + Name */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                    <button
                      type="button"
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
                        justifyContent: 'center',
                        flexShrink: 0
                      }}
                      onMouseEnter={(e) => { if (!isFavorite) e.currentTarget.style.color = '#facc15'; }}
                      onMouseLeave={(e) => { if (!isFavorite) e.currentTarget.style.color = 'rgba(255, 255, 255, 0.25)'; }}
                    >
                      {isFavorite ? '⭐' : '☆'}
                    </button>

                    <span
                      className="model-selector-provider-dot"
                      style={{ backgroundColor: colors.color, flexShrink: 0 }}
                      title={`Provider: ${m.provider}`}
                    />

                    {/* Sigmanih badge if model belongs to Sigmanih */}
                    {isSig && (
                      <span
                        title="Modello Sigmanih Ecosystem"
                        style={{
                          fontSize: '0.56rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px',
                          background: 'rgba(255, 184, 108, 0.15)', border: '1px solid rgba(255, 184, 108, 0.35)',
                          color: '#ffb86c', flexShrink: 0
                        }}
                      >
                        Sigmanih
                      </span>
                    )}

                    {/* Family chip if recognized */}
                    {famKey && famKey !== 'altro' && famKey !== 'sigmanih' && (
                      <span
                        title={`Famiglia architetturale: ${familyConf.title}`}
                        style={{
                          fontSize: '0.56rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px',
                          background: familyConf.bg, border: `1px solid ${familyConf.border}`,
                          color: familyConf.color, flexShrink: 0
                        }}
                      >
                        {familyConf.title}
                      </span>
                    )}


                    <span
                      className="model-selector-opt-name"
                      title={m.display_name || m.clean_name || m.name}
                      style={{
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        fontWeight: isSelected ? 800 : 600, fontSize: '0.78rem',
                        flex: '1 1 auto', minWidth: '160px'
                      }}
                    >
                      {m.display_name || m.clean_name || m.name}
                    </span>
                  </div>


                  {/* Right part: Benchmark Badge + Speed t/s + Specs + Provider */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
                    {/* Default pill */}
                    {isPrimary && (
                      <span style={{ fontSize: '0.60rem', fontWeight: 800, color: '#facc15', background: 'rgba(234, 179, 8, 0.15)', padding: '1px 5px', borderRadius: '4px', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                        Default
                      </span>
                    )}

                    {/* 🏆 Benchmark Characteristics Badge */}
                    <span
                      title={hasBm
                        ? `Valutazione Benchmark: ${Math.round(bmScore)}% ${bm.tests_total ? `(${bm.tests_passed || 0}/${bm.tests_total} quesiti superati)` : ''}`
                        : 'Nessun benchmark registrato per questo modello'
                      }
                      style={{
                        fontSize: '0.58rem', fontWeight: 800, padding: '1px 6px', borderRadius: '4px',
                        background: sortBy === 'benchmark' ? `${bmColor}30` : (hasBm ? `${bmColor}18` : 'rgba(255, 255, 255, 0.04)'),
                        border: sortBy === 'benchmark' ? `1px solid ${bmColor}` : (hasBm ? `1px solid ${bmColor}40` : '1px solid rgba(255, 255, 255, 0.08)'),
                        boxShadow: sortBy === 'benchmark' ? `0 0 8px ${bmColor}40` : 'none',
                        color: bmColor,
                        display: 'inline-flex', alignItems: 'center', gap: '3px'
                      }}
                    >
                      <Trophy size={10} color={bmColor} />
                      <span>{hasBm ? `${Math.round(bmScore)}%` : '-'}</span>
                    </span>

                    {/* ⚡ Live Generation Speed (t/s) Badge */}
                    <span
                      title={chatTps !== null
                        ? `Velocità inferenza registrata: ${chatTps} token/secondo`
                        : 'Nessuna misurazione live. I t/s si calcolano automaticamente non appena chatti con questo modello.'
                      }
                      style={{
                        fontSize: '0.58rem', fontWeight: 800, padding: '1px 6px', borderRadius: '4px',
                        background: sortBy === 'speed' ? 'rgba(0, 210, 255, 0.28)' : (chatTps !== null ? 'rgba(0, 210, 255, 0.14)' : 'rgba(255, 255, 255, 0.04)'),
                        border: sortBy === 'speed' ? '1px solid #00d2ff' : (chatTps !== null ? '1px solid rgba(0, 210, 255, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)'),
                        boxShadow: sortBy === 'speed' ? '0 0 8px rgba(0, 210, 255, 0.4)' : 'none',
                        color: chatTps !== null ? '#00d2ff' : '#8b8fa3',
                        display: 'inline-flex', alignItems: 'center', gap: '2px'
                      }}
                    >
                      <Zap size={9} color={chatTps !== null ? '#00d2ff' : '#8b8fa3'} />
                      <span>{chatTps !== null ? `${chatTps} t/s` : '-'}</span>
                    </span>

                    {/* Parameter size */}
                    {itemSpecs?.params && (
                      <span style={{
                        fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                        background: sortBy === 'params' ? 'rgba(0, 210, 255, 0.28)' : 'rgba(0, 210, 255, 0.12)',
                        border: sortBy === 'params' ? '1px solid #00d2ff' : 'none',
                        boxShadow: sortBy === 'params' ? '0 0 8px rgba(0, 210, 255, 0.4)' : 'none',
                        color: '#00d2ff', fontWeight: 800
                      }}>
                        {itemSpecs.params}
                      </span>
                    )}

                    {/* Disk size */}
                    {itemSpecs?.size && (
                      <span style={{
                        fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px',
                        background: sortBy === 'size' ? 'rgba(255, 184, 108, 0.28)' : 'rgba(255, 184, 108, 0.12)',
                        border: sortBy === 'size' ? '1px solid #ffb86c' : 'none',
                        boxShadow: sortBy === 'size' ? '0 0 8px rgba(255, 184, 108, 0.4)' : 'none',
                        color: '#ffb86c', fontWeight: 800
                      }}>
                        {itemSpecs.size}
                      </span>
                    )}

                    {/* Provider badge */}
                    <span className="model-selector-provider-badge" style={{ backgroundColor: colors.bg, color: colors.color }}>
                      {m.provider === 'sigma_engine' ? 'SIGMA' : m.provider}
                    </span>

                    {isSelected && <Check size={13} color="#00d2ff" className="model-selector-check" />}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Footer for AI Configuration */}
          <div style={{
            padding: '8px 12px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(0, 0, 0, 0.18)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px'
          }}>
            <span style={{ fontSize: '0.68rem', opacity: 0.7, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={11} color="#3fb950" /> Modelli pronti all'uso
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