import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { 
  Cpu, HardDrive, Zap, ChevronDown, Check, Search, Sparkles, 
  Layers, Database, Shield, Server, Star, Trophy, Wrench, CheckCircle2, ArrowUpDown
} from 'lucide-react';
import { 
  getModelSpecs, 
  detectModelFamily, 
  isSigmanihModel, 
  getModelChatSpeed, 
  FAMILY_CONFIG 
} from '../../components/Chat/core/modelSpecsHelper';

export default function DeveloperModelSelector({
  selectedModel,
  onSelectModel,
  contextTokens = 32768,
  onSelectContextTokens,
  contextMetrics,
  theme,
  isLight
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('all'); // 'favorites' | 'all' | 'local' | 'cloud'
  const [familyFilter, setFamilyFilter] = useState('all');
  const [sortBy, setSortBy] = useState('default'); // 'default' | 'speed' | 'params' | 'size' | 'name'
  const [sortOrder, setSortOrder] = useState('desc');
  const [localModels, setLocalModels] = useState([]);
  const [serverInfo, setServerInfo] = useState(null);
  const [speedVersion, setSpeedVersion] = useState(0);

  // Favorite models state (sync with shared localStorage key)
  const [favoriteModels, setFavoriteModels] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_favorite_models') || localStorage.getItem('sigma_developer_favorite_models');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const dropdownRef = useRef(null);
  const contextMenuRef = useRef(null);

  const CONTEXT_PRESETS = [
    { label: '4K', tokens: 4096, desc: 'Leggero (4,096 tok)' },
    { label: '8K', tokens: 8192, desc: 'Bilanciato (8,192 tok)' },
    { label: '16K', tokens: 16384, desc: 'Esteso (16,384 tok)' },
    { label: '32K', tokens: 32768, desc: 'Consigliato Code (32,768 tok)' },
    { label: '64K', tokens: 65536, desc: 'Lungo Contesto (65,536 tok)' },
    { label: '128K', tokens: 131072, desc: 'Massimo Workspace (131,072 tok)' }
  ];

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target)) {
        setIsContextMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  // Listen to favorite model changes & speed updates across tabs
  useEffect(() => {
    const handleFavoritesUpdated = (e) => {
      if (e.detail && Array.isArray(e.detail)) {
        setFavoriteModels(e.detail);
      }
    };
    const handleSpeedUpdated = () => {
      setSpeedVersion(v => v + 1);
    };
    window.addEventListener('sigma-favorites-updated', handleFavoritesUpdated);
    window.addEventListener('sigma-model-speed-updated', handleSpeedUpdated);
    return () => {
      window.removeEventListener('sigma-favorites-updated', handleFavoritesUpdated);
      window.removeEventListener('sigma-model-speed-updated', handleSpeedUpdated);
    };
  }, []);

  const toggleFavorite = useCallback((modelId, e) => {
    if (e) e.stopPropagation();
    setFavoriteModels(prev => {
      const next = prev.includes(modelId)
        ? prev.filter(id => id !== modelId)
        : [...prev, modelId];
      try {
        localStorage.setItem('sigma_favorite_models', JSON.stringify(next));
        localStorage.setItem('sigma_developer_favorite_models', JSON.stringify(next));
        window.dispatchEvent(new CustomEvent('sigma-favorites-updated', { detail: next }));
      } catch {}
      return next;
    });
  }, []);

  // Fetch local models inventory and server info
  useEffect(() => {
    fetch('/api/models/local/list')
      .then(r => r.json())
      .then(d => {
        if (d.success && Array.isArray(d.models)) {
          setLocalModels(d.models);
        }
      })
      .catch(() => {});

    fetch('/api/engine/server_info')
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setServerInfo(d);
        }
      })
      .catch(() => {});
  }, []);

  // Format and enrich all available models
  const allModels = useMemo(() => {
    const list = [];
    const residentName = serverInfo?.resident_model;

    // 1. Local Models from Disk (GGUF & Safetensors)
    localModels.forEach(m => {
      const id = m.model_id || m.filename || m.name;
      const rawName = m.display_name || m.name || m.filename || id;
      const specs = getModelSpecs(rawName, localModels) || {};
      const fam = detectModelFamily(m);
      const isSig = isSigmanihModel(m);
      
      const isResident = residentName && (
        residentName.toLowerCase() === id.toLowerCase() || 
        residentName.toLowerCase() === rawName.toLowerCase() ||
        residentName.toLowerCase().includes(rawName.toLowerCase())
      );

      // Extract parameter count (e.g. 27B, 3.8B, 7B)
      let paramLabel = specs.params || m.params_label;
      if (!paramLabel) {
        const pMatch = rawName.match(/([0-9.]+[bBmM])/);
        paramLabel = pMatch ? pMatch[1].toUpperCase() : 'LLM';
      }

      // Quantization
      let quantLabel = m.quantization && m.quantization !== 'Standard' 
        ? m.quantization 
        : (specs.quant || (rawName.match(/(Q[0-9]_[A-Z0-9_]+|FP16|BF16|INT8|INT4|FP8)/i)?.[1]?.toUpperCase() || 'FP16'));

      const isComplete = m.is_complete !== false && !m.has_part_files;
      const chatTps = getModelChatSpeed(id, m) || getModelChatSpeed(rawName, m) || specs.chatSpeed || (m.benchmark_summary?.tokens_per_sec || null);
      const bmScore = m.benchmark_summary?.score ?? specs?.benchmark?.score ?? null;
      const toolScore = m.tool_score ?? specs?.toolScore ?? null;
      const isPublished = Boolean(m.publication?.repo_id || specs?.publication?.repo_id || specs?.isPublished);

      list.push({
        id: id,
        name: rawName,
        shortName: rawName.replace(/--/g, '/').split('/').pop().replace(/\.gguf$/i, ''),
        provider: 'local',
        category: 'local',
        family: fam,
        isSigmanih: isSig,
        params: paramLabel,
        size: m.size_formatted || (m.size_bytes ? `${(m.size_bytes / (1024 ** 3)).toFixed(1)} GB` : null),
        sizeBytes: m.size_bytes || 0,
        quant: quantLabel,
        format: m.format || (id.endsWith('.gguf') ? 'GGUF' : 'Safetensors'),
        isResident: isResident,
        isComplete: isComplete,
        chatSpeed: chatTps,
        benchmarkScore: bmScore,
        toolScore: toolScore,
        isPublished: isPublished,
        description: `Modello locale pronto all'uso con caricamento ultra-rapido.`
      });
    });

    // 3. Configured Cloud Providers (if keys exist in localStorage)
    try {
      const pConfigs = JSON.parse(localStorage.getItem('sigma_ai_providers') || '{}');
      const cloudDefs = [
        { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic', family: 'altro', params: '200K ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'gpt-4o', name: 'GPT-4o (Omni)', provider: 'openai', family: 'altro', params: '128K ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'deepseek-chat', name: 'DeepSeek V3 (Chat)', provider: 'deepseek', family: 'deepseek', params: '671B MoE', size: 'Cloud API', quant: 'FP8' },
        { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'google', family: 'gemma', params: '2M ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B (Groq)', provider: 'groq', family: 'llama', params: '70B Versatile', size: 'Cloud Ultra-Fast', quant: 'FP8' }
      ];

      cloudDefs.forEach(c => {
        if (pConfigs[c.provider]?.has_api_key || pConfigs[c.provider]?.api_key) {
          list.push({
            id: c.id,
            name: `${c.name} (${c.provider.toUpperCase()})`,
            shortName: c.name,
            provider: c.provider,
            category: 'cloud',
            family: c.family,
            isSigmanih: false,
            params: c.params,
            size: c.size,
            sizeBytes: 0,
            quant: c.quant,
            format: 'Cloud API',
            isResident: false,
            chatSpeed: getModelChatSpeed(c.id) || null
          });
        }
      });
    } catch {}

    return list;
  }, [localModels, serverInfo, speedVersion, contextMetrics?.tps]);

  // Selected Model Object with full details
  const activeModelObj = useMemo(() => {
    if (!selectedModel || selectedModel === 'sigmaengine') {
      const firstFav = favoriteModels.length > 0 ? allModels.find(m => favoriteModels.includes(m.id) || favoriteModels.includes(m.name)) : null;
      return firstFav || allModels[0] || {
        id: 'default',
        name: 'Nessun modello selezionato',
        shortName: 'Default',
        family: 'qwen',
        params: 'LLM',
        quant: 'FP16',
        isResident: false
      };
    }
    const found = allModels.find(m => m.id === selectedModel || m.name === selectedModel);
    if (found) return found;
    
    const specs = getModelSpecs(selectedModel, localModels) || {};
    return {
      id: selectedModel,
      name: selectedModel,
      shortName: selectedModel.replace(/--/g, '/').split('/').pop(),
      provider: 'custom',
      family: detectModelFamily(selectedModel),
      params: specs.params || 'Custom',
      quant: specs.quant || 'LLM',
      isResident: false,
      chatSpeed: specs.chatSpeed || null
    };
  }, [allModels, selectedModel, localModels]);

  // Seleziona automaticamente il primo tra i preferiti o il primo presente se non impostato o 'sigmaengine'
  useEffect(() => {
    if ((!selectedModel || selectedModel === 'sigmaengine') && allModels.length > 0) {
      const firstFav = favoriteModels.length > 0 
        ? allModels.find(m => favoriteModels.includes(m.id) || favoriteModels.includes(m.name)) 
        : null;
      const target = firstFav || allModels[0];
      if (target?.id && target.id !== selectedModel) {
        onSelectModel?.(target.id);
      }
    }
  }, [selectedModel, allModels, favoriteModels, onSelectModel]);

  // Models in the currently selected top tab (for family counts)
  const modelsInCurrentTab = useMemo(() => {
    return allModels.filter(m => {
      if (activeCategory === 'favorites') {
        return favoriteModels.includes(m.id) || favoriteModels.includes(m.name);
      }
      if (activeCategory === 'local') return m.category === 'local';
      if (activeCategory === 'cloud') return m.category === 'cloud';
      return true;
    });
  }, [allModels, activeCategory, favoriteModels]);

  // Family filter pills
  const familyPills = useMemo(() => {
    const counts = { all: modelsInCurrentTab.length };
    counts.sigmanih = modelsInCurrentTab.filter(m => m.isSigmanih).length;

    modelsInCurrentTab.forEach(m => {
      const fam = m.family || 'altro';
      if (fam !== 'sigmanih') {
        counts[fam] = (counts[fam] || 0) + 1;
      }
    });

    const familyKeys = ['all', 'sigmanih', 'qwen', 'llama', 'deepseek', 'mistral', 'gemma', 'phi', 'glm', 'altro'];

    return familyKeys
      .filter(k => k === 'all' || (counts[k] && counts[k] > 0))
      .map(k => {
        if (k === 'all') {
          return {
            id: 'all',
            title: 'Tutte',
            count: counts.all || 0,
            color: '#00f2fe',
            bg: 'rgba(0, 242, 254, 0.15)',
            border: 'rgba(0, 242, 254, 0.35)'
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

  // Filtered & Sorted models
  const filteredAndSortedModels = useMemo(() => {
    let list = modelsInCurrentTab.filter(m => {
      // Family filter
      let matchesFamily = true;
      if (familyFilter !== 'all') {
        if (familyFilter === 'sigmanih') {
          matchesFamily = Boolean(m.isSigmanih);
        } else {
          matchesFamily = (m.family === familyFilter);
        }
      }

      // Search query
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch = !q || 
        m.name.toLowerCase().includes(q) ||
        (m.shortName && m.shortName.toLowerCase().includes(q)) ||
        (m.params && m.params.toLowerCase().includes(q)) ||
        (m.quant && m.quant.toLowerCase().includes(q)) ||
        (m.family && m.family.toLowerCase().includes(q));

      return matchesFamily && matchesSearch;
    });

    // Sorting
    if (sortBy === 'speed') {
      list = [...list].sort((a, b) => {
        const sa = a.chatSpeed || 0;
        const sb = b.chatSpeed || 0;
        return sortOrder === 'desc' ? sb - sa : sa - sb;
      });
    } else if (sortBy === 'params') {
      const parseP = (p) => {
        const match = String(p || '').match(/([0-9.]+)\s*([BMKbmk]?)/);
        if (!match) return 0;
        const val = parseFloat(match[1]);
        const unit = (match[2] || '').toUpperCase();
        if (unit === 'B') return val * 1000;
        if (unit === 'M') return val;
        return val;
      };
      list = [...list].sort((a, b) => {
        const pa = parseP(a.params);
        const pb = parseP(b.params);
        return sortOrder === 'desc' ? pb - pa : pa - pb;
      });
    } else if (sortBy === 'size') {
      list = [...list].sort((a, b) => {
        const va = a.sizeBytes || 0;
        const vb = b.sizeBytes || 0;
        return sortOrder === 'desc' ? vb - va : va - vb;
      });
    } else if (sortBy === 'name') {
      list = [...list].sort((a, b) => {
        const na = a.shortName || a.name;
        const nb = b.shortName || b.name;
        return sortOrder === 'desc' ? nb.localeCompare(na) : na.localeCompare(nb);
      });
    }

    return list;
  }, [modelsInCurrentTab, familyFilter, searchQuery, sortBy, sortOrder]);

  const activeContextLabel = CONTEXT_PRESETS.find(p => p.tokens === contextTokens)?.label || `${Math.round(contextTokens / 1024)}K`;
  const isSelectedFav = favoriteModels.includes(activeModelObj.id) || favoriteModels.includes(activeModelObj.name);
  const activeFamilyConf = FAMILY_CONFIG[activeModelObj.family] || (activeModelObj.isSigmanih ? FAMILY_CONFIG.sigmanih : null);

  const favCount = allModels.filter(m => favoriteModels.includes(m.id) || favoriteModels.includes(m.name)).length;

  return (
    <div style={{ position: 'relative', width: '100%', display: 'flex', alignItems: 'center', gap: '6px' }} ref={dropdownRef}>
      {/* Main Model Selector Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px',
          borderRadius: '8px',
          background: isLight ? '#ffffff' : '#161b22',
          border: isLight ? '1px solid #d0d7de' : '1px solid rgba(0, 242, 254, 0.25)',
          color: isLight ? '#24292f' : '#f0f6fc',
          cursor: 'pointer',
          transition: 'all 0.15s ease'
        }}
        title={`Modello attivo Developer: ${activeModelObj.name}`}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          <div style={{
            width: '22px',
            height: '22px',
            borderRadius: '6px',
            background: activeModelObj?.isResident ? 'rgba(63, 185, 80, 0.2)' : 'rgba(0, 242, 254, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            {activeModelObj?.isResident ? (
              <Zap size={13} color="#3fb950" />
            ) : (
              <Cpu size={13} color="#00f2fe" />
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', overflow: 'hidden', textAlign: 'left' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', width: '100%' }}>
              {isSelectedFav && (
                <span title="Modello Preferito" style={{ fontSize: '0.72rem', color: '#facc15', lineHeight: 1 }}>⭐</span>
              )}
              <span style={{
                fontSize: '0.74rem',
                fontWeight: 800,
                color: isLight ? '#24292f' : '#f0f6fc',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {activeModelObj?.shortName || activeModelObj?.name}
              </span>
              {activeFamilyConf && (
                <span style={{
                  fontSize: '0.54rem',
                  fontWeight: 800,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: activeFamilyConf.bg,
                  border: `1px solid ${activeFamilyConf.border}`,
                  color: activeFamilyConf.color,
                  flexShrink: 0
                }}>
                  {activeFamilyConf.title}
                </span>
              )}
            </div>

            {/* Badges row: Params, Quant, Size, Live Speed, TTFT */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px', flexWrap: 'wrap' }}>
              {activeModelObj?.params && (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 800,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: 'rgba(0, 242, 254, 0.15)',
                  color: '#00f2fe'
                }}>
                  {activeModelObj.params}
                </span>
              )}
              {activeModelObj?.quant && (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)',
                  color: isLight ? '#57606a' : '#8b949e'
                }}>
                  {activeModelObj.quant}
                </span>
              )}
              {activeModelObj?.size && (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: 'rgba(210, 153, 34, 0.15)',
                  color: '#d29922'
                }}>
                  {activeModelObj.size}
                </span>
              )}
              {(contextMetrics?.tps != null && contextMetrics.tps > 0) ? (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 800,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: contextMetrics.tps >= 30 ? 'rgba(63, 185, 80, 0.18)' : 'rgba(210, 153, 34, 0.15)',
                  color: contextMetrics.tps >= 30 ? '#3fb950' : '#d29922',
                  whiteSpace: 'nowrap'
                }}>
                  ⚡{contextMetrics.tps} t/s
                </span>
              ) : (activeModelObj?.chatSpeed != null && (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 800,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: 'rgba(0, 210, 255, 0.14)',
                  color: '#00d2ff',
                  whiteSpace: 'nowrap'
                }}>
                  ⚡{activeModelObj.chatSpeed} t/s
                </span>
              ))}
              {contextMetrics?.ttftMs != null && contextMetrics.ttftMs > 0 && (
                <span style={{
                  fontSize: '0.58rem',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '4px',
                  background: contextMetrics.ttftMs <= 5000 ? 'rgba(63, 185, 80, 0.12)' : 'rgba(210, 153, 34, 0.12)',
                  color: contextMetrics.ttftMs <= 5000 ? '#3fb950' : '#d29922',
                  whiteSpace: 'nowrap'
                }}>
                  {contextMetrics.ttftMs < 1000
                    ? `${Math.round(contextMetrics.ttftMs)}ms`
                    : `${(contextMetrics.ttftMs / 1000).toFixed(1)}s`
                  } TTFT
                </span>
              )}
            </div>
          </div>
        </div>

        <ChevronDown size={14} color="#8b949e" style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease', flexShrink: 0 }} />
      </button>

      {/* Context Length Quick Control & Meter */}
      <div style={{ position: 'relative' }} ref={contextMenuRef}>
        <button
          type="button"
          onClick={() => setIsContextMenuOpen(!isContextMenuOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 8px',
            borderRadius: '8px',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(163, 113, 247, 0.35)',
            cursor: 'pointer',
            height: '100%',
            transition: 'all 0.15s ease'
          }}
          title={`Lunghezza Finestra di Contesto: ${contextTokens.toLocaleString()} token. Clicca per modificare.`}
        >
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={11} color="#a371f7" />
              <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#a371f7' }}>
                {activeContextLabel} Ctx
              </span>
            </div>
            {contextMetrics?.promptTokens ? (
              <span style={{ fontSize: '0.56rem', color: '#8b949e', whiteSpace: 'nowrap' }}>
                ~{(contextMetrics.promptTokens / 1000).toFixed(1)}K / {activeContextLabel}
              </span>
            ) : (
              <span style={{ fontSize: '0.56rem', color: '#8b949e', whiteSpace: 'nowrap' }}>
                {contextTokens.toLocaleString()} tok
              </span>
            )}
          </div>
          <ChevronDown size={12} color="#8b949e" style={{ transform: isContextMenuOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
        </button>

        {/* Context Presets Menu */}
        {isContextMenuOpen && (
          <div style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            right: 0,
            zIndex: 110,
            width: '210px',
            borderRadius: '8px',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(163, 113, 247, 0.4)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            padding: '6px',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px'
          }}>
            <div style={{ padding: '4px 6px', fontSize: '0.62rem', fontWeight: 800, color: '#a371f7', borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)', marginBottom: '4px' }}>
              🧠 Finestra Contesto (RAM/VRAM)
            </div>
            {CONTEXT_PRESETS.map(p => {
              const isSelected = p.tokens === contextTokens;
              return (
                <div
                  key={p.tokens}
                  onClick={() => {
                    onSelectContextTokens?.(p.tokens);
                    setIsContextMenuOpen(false);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '5px 8px',
                    borderRadius: '5px',
                    background: isSelected ? 'rgba(163, 113, 247, 0.15)' : 'transparent',
                    cursor: 'pointer',
                    fontSize: '0.66rem',
                    color: isSelected ? '#a371f7' : (isLight ? '#24292f' : '#f0f6fc'),
                    transition: 'background 0.1s'
                  }}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = isLight ? '#f6f8fa' : 'rgba(255,255,255,0.05)'; }}
                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: isSelected ? 800 : 600 }}>{p.label} Tokens</span>
                    <span style={{ fontSize: '0.56rem', color: '#8b949e' }}>{p.desc}</span>
                  </div>
                  {isSelected && <Check size={12} color="#a371f7" />}
                </div>
              );
            })}
            <div style={{
              marginTop: '4px',
              padding: '5px 8px',
              borderRadius: '5px',
              background: 'rgba(0, 242, 254, 0.1)',
              border: '1px solid rgba(0, 242, 254, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.62rem',
              color: '#00f2fe',
              fontWeight: 700
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Zap size={11} color="#00f2fe" />
                <span>Flash Attention (FA)</span>
              </span>
              <span style={{
                fontSize: '0.56rem',
                fontWeight: 800,
                padding: '1px 5px',
                borderRadius: '3px',
                background: '#00f2fe',
                color: '#000'
              }}>
                ON (GPU)
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Popover Dropdown */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 100,
          borderRadius: '10px',
          background: isLight ? '#ffffff' : '#161b22',
          border: isLight ? '1px solid #d0d7de' : '1px solid rgba(0, 242, 254, 0.3)',
          boxShadow: isLight ? '0 8px 24px rgba(0,0,0,0.12)' : '0 12px 32px rgba(0,0,0,0.6)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '460px'
        }}>
          {/* Search Box */}
          <div style={{
            padding: '8px',
            borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <Search size={13} color="#8b949e" />
            <input
              type="text"
              placeholder="Cerca per nome, famiglia (Qwen), peso (27B) o quant (Q4_K_S)..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              autoFocus
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                color: isLight ? '#24292f' : '#f0f6fc',
                fontSize: '0.72rem',
                outline: 'none'
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: '0.72rem' }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Top Category Tabs: ⭐ Preferiti, Tutti, Locali, Cloud */}
          <div style={{
            display: 'flex',
            padding: '4px 6px',
            gap: '4px',
            background: isLight ? '#f6f8fa' : '#0d1117',
            borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
          }}>
            {[
              { id: 'favorites', label: '⭐ Preferiti', count: favCount, color: '#facc15' },
              { id: 'all', label: 'Tutti', count: allModels.length, color: '#00f2fe' },
              { id: 'local', label: '⚡ Locali', count: allModels.filter(m => m.category === 'local').length, color: '#3fb950' },
              { id: 'cloud', label: '☁️ Cloud', count: allModels.filter(m => m.category === 'cloud').length, color: '#bc8cff' }
            ].map(cat => {
              const isActive = activeCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => {
                    setActiveCategory(cat.id);
                    setFamilyFilter('all');
                  }}
                  style={{
                    flex: 1,
                    padding: '4px 2px',
                    borderRadius: '5px',
                    fontSize: '0.64rem',
                    fontWeight: isActive ? 800 : 600,
                    background: isActive ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.15)') : 'transparent',
                    border: isActive ? `1px solid ${cat.color || 'rgba(0, 242, 254, 0.3)'}` : 'none',
                    color: isActive ? (cat.color || '#00f2fe') : (isLight ? '#57606a' : '#8b949e'),
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '4px'
                  }}
                >
                  <span>{cat.label}</span>
                  <span style={{
                    fontSize: '0.56rem',
                    padding: '0 4px',
                    borderRadius: '4px',
                    background: isActive ? `${cat.color || '#00f2fe'}25` : (isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)'),
                    color: isActive ? (cat.color || '#00f2fe') : '#8b949e'
                  }}>
                    {cat.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Model Family Filter Pills */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '5px 8px',
            overflowX: 'auto',
            background: isLight ? '#ffffff' : '#111620',
            borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.05)'
          }}>
            <span style={{ fontSize: '0.58rem', fontWeight: 700, color: '#8b949e', whiteSpace: 'nowrap', marginRight: '2px' }}>
              Famiglia:
            </span>
            {familyPills.map(fam => {
              const isFamActive = familyFilter === fam.id;
              return (
                <button
                  key={fam.id}
                  type="button"
                  onClick={() => setFamilyFilter(fam.id)}
                  style={{
                    padding: '2px 7px',
                    borderRadius: '12px',
                    fontSize: '0.60rem',
                    fontWeight: isFamActive ? 800 : 600,
                    background: isFamActive ? fam.bg : (isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.04)'),
                    border: isFamActive ? `1px solid ${fam.color}` : `1px solid ${isLight ? '#e1e4e8' : 'rgba(255,255,255,0.08)'}`,
                    color: isFamActive ? fam.color : (isLight ? '#57606a' : '#8b949e'),
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <span>{fam.title}</span>
                  <span style={{
                    fontSize: '0.52rem',
                    opacity: 0.8
                  }}>
                    {fam.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Sort bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '3px 8px',
            background: isLight ? '#f6f8fa' : '#0a0e14',
            borderBottom: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.04)',
            fontSize: '0.58rem',
            color: '#8b949e'
          }}>
            <span>Ordina per:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {[
                { id: 'default', label: 'Default' },
                { id: 'speed', label: '⚡ t/s' },
                { id: 'params', label: 'Parametri' },
                { id: 'size', label: 'Peso' },
                { id: 'name', label: 'Nome' }
              ].map(opt => {
                const isSortActive = sortBy === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      if (sortBy === opt.id) {
                        setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc');
                      } else {
                        setSortBy(opt.id);
                        setSortOrder(opt.id === 'name' ? 'asc' : 'desc');
                      }
                    }}
                    style={{
                      background: isSortActive ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                      border: isSortActive ? '1px solid rgba(0, 242, 254, 0.35)' : 'none',
                      color: isSortActive ? '#00f2fe' : '#8b949e',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      fontSize: '0.56rem',
                      fontWeight: isSortActive ? 800 : 500,
                      cursor: 'pointer'
                    }}
                  >
                    {opt.label} {isSortActive && opt.id !== 'default' && (sortOrder === 'desc' ? '↓' : '↑')}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model Items List */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
            {filteredAndSortedModels.length === 0 ? (
              <div style={{ padding: '24px 16px', fontSize: '0.72rem', color: '#8b949e', textAlign: 'center' }}>
                {activeCategory === 'favorites' ? (
                  <div>
                    <span style={{ fontSize: '1.4rem', display: 'block', marginBottom: '6px' }}>⭐</span>
                    <p style={{ margin: '0 0 6px 0', fontSize: '0.76rem', fontWeight: 700, color: '#facc15' }}>
                      Nessun modello tra i preferiti
                    </p>
                    <p style={{ margin: '0', fontSize: '0.68rem', opacity: 0.7 }}>
                      Clicca sulla stellina ☆ accanto a qualsiasi modello per aggiungerlo alla selezione rapida.
                    </p>
                  </div>
                ) : (
                  <div>
                    Nessun modello trovato per i filtri selezionati.
                  </div>
                )}
              </div>
            ) : (
              filteredAndSortedModels.map(m => {
                const isSelected = selectedModel === m.id;
                const isFav = favoriteModels.includes(m.id) || favoriteModels.includes(m.name);
                const famConf = FAMILY_CONFIG[m.family] || (m.isSigmanih ? FAMILY_CONFIG.sigmanih : null);

                return (
                  <div
                    key={m.id}
                    onClick={() => {
                      onSelectModel(m.id);
                      setIsOpen(false);
                    }}
                    style={{
                      padding: '7px 9px',
                      borderRadius: '7px',
                      marginBottom: '4px',
                      cursor: 'pointer',
                      background: isSelected 
                        ? (isLight ? 'rgba(0, 242, 254, 0.12)' : 'rgba(0, 242, 254, 0.1)') 
                        : 'transparent',
                      border: isSelected ? '1px solid rgba(0, 242, 254, 0.4)' : '1px solid transparent',
                      transition: 'all 0.1s ease'
                    }}
                    onMouseEnter={e => {
                      if (!isSelected) e.currentTarget.style.background = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)';
                    }}
                    onMouseLeave={e => {
                      if (!isSelected) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                      {/* Left side: Star + Resident dot + Name + Family chip */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                        {/* Star Button */}
                        <button
                          type="button"
                          onClick={(e) => toggleFavorite(m.id, e)}
                          title={isFav ? "Rimuovi dai preferiti" : "Aggiungi ai preferiti"}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '1px 3px',
                            fontSize: '0.80rem',
                            lineHeight: 1,
                            color: isFav ? '#facc15' : 'rgba(255, 255, 255, 0.25)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0
                          }}
                          onMouseEnter={e => { if (!isFav) e.currentTarget.style.color = '#facc15'; }}
                          onMouseLeave={e => { if (!isFav) e.currentTarget.style.color = 'rgba(255, 255, 255, 0.25)'; }}
                        >
                          {isFav ? '⭐' : '☆'}
                        </button>

                        {/* Resident in VRAM green dot */}
                        {m.isResident && (
                          <span
                            title="Modello attualmente residente in VRAM"
                            style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3fb950', flexShrink: 0 }}
                          />
                        )}

                        {/* Family badge chip */}
                        {famConf && (
                          <span
                            title={`Famiglia architetturale: ${famConf.title}`}
                            style={{
                              fontSize: '0.54rem',
                              fontWeight: 800,
                              padding: '1px 5px',
                              borderRadius: '4px',
                              background: famConf.bg,
                              border: `1px solid ${famConf.border}`,
                              color: famConf.color,
                              flexShrink: 0
                            }}
                          >
                            {famConf.title}
                          </span>
                        )}

                        {/* Model Name */}
                        <span style={{
                          fontSize: '0.74rem',
                          fontWeight: isSelected ? 800 : 600,
                          color: isSelected ? '#00f2fe' : (isLight ? '#24292f' : '#f0f6fc'),
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {m.shortName || m.name}
                        </span>
                      </div>

                      {/* Right side: Check if selected */}
                      {isSelected && <Check size={13} color="#00f2fe" style={{ flexShrink: 0 }} />}
                    </div>

                    {/* Meta tags / Model Details */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', flexWrap: 'wrap' }}>
                      {/* Parameters */}
                      {m.params && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px', background: 'rgba(0, 242, 254, 0.15)', color: '#00f2fe' }}>
                          {m.params}
                        </span>
                      )}

                      {/* Quantization */}
                      {m.quant && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', color: isLight ? '#57606a' : '#8b949e' }}>
                          {m.quant}
                        </span>
                      )}

                      {/* Size */}
                      {m.size && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(210, 153, 34, 0.15)', color: '#d29922' }}>
                          {m.size}
                        </span>
                      )}

                      {/* Format */}
                      {m.format && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff' }}>
                          {m.format}
                        </span>
                      )}

                      {/* Live Speed t/s */}
                      {m.chatSpeed != null && (
                        <span
                          title={`Velocità di inferenza: ${m.chatSpeed} t/s`}
                          style={{
                            fontSize: '0.58rem',
                            fontWeight: 800,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(0, 210, 255, 0.16)',
                            color: '#00d2ff',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                        >
                          <Zap size={9} color="#00d2ff" />
                          <span>{m.chatSpeed} t/s</span>
                        </span>
                      )}

                      {/* Benchmark Score */}
                      {m.benchmarkScore != null && (
                        <span
                          title={`Valutazione Benchmark: ${Math.round(m.benchmarkScore)}%`}
                          style={{
                            fontSize: '0.58rem',
                            fontWeight: 800,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(16, 185, 129, 0.15)',
                            color: '#10b981',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                        >
                          <Trophy size={9} color="#10b981" />
                          <span>{Math.round(m.benchmarkScore)}%</span>
                        </span>
                      )}

                      {/* Tool Benchmark */}
                      {m.toolScore != null && (
                        <span
                          title={`Benchmark Tools: ${Math.round(m.toolScore)}%`}
                          style={{
                            fontSize: '0.58rem',
                            fontWeight: 800,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: '#38bdf8',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                        >
                          <Wrench size={9} color="#38bdf8" />
                          <span>{Math.round(m.toolScore)}%</span>
                        </span>
                      )}

                      {/* Published flag */}
                      {m.isPublished && (
                        <span
                          title="Pubblicato su Hugging Face"
                          style={{
                            fontSize: '0.56rem',
                            fontWeight: 800,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(16, 185, 129, 0.15)',
                            color: '#10b981',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                        >
                          <CheckCircle2 size={8} color="#10b981" />
                          <span>Pubblicato</span>
                        </span>
                      )}

                      {/* Incomplete Download Warning */}
                      {m.isComplete === false && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }} title="Download parziale su disco.">
                          ⚠️ Incompleto
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
