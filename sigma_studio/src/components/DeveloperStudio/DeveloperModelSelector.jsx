import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Cpu, HardDrive, Zap, ChevronDown, Check, Search, Sparkles, 
  Layers, Database, Shield, Server 
} from 'lucide-react';
import { getModelSpecs } from '../Chat/core/modelSpecsHelper';

export default function DeveloperModelSelector({
  selectedModel,
  onSelectModel,
  theme,
  isLight
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [localModels, setLocalModels] = useState([]);
  const [serverInfo, setServerInfo] = useState(null);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
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

    // 1. Default Auto / SigmaEngine Option
    list.push({
      id: 'sigmaengine',
      name: '⚡ SigmaEngine (Auto-Risoluzione Nativa)',
      shortName: 'SigmaEngine Auto',
      provider: 'sigma_engine',
      category: 'local',
      params: residentName ? (residentName.match(/([0-9.]+[bBmM])/)?.[1]?.toUpperCase() || 'Auto') : 'Auto',
      size: residentName ? 'Residente in VRAM' : 'Auto GPU Sharding',
      quant: 'Auto FlashAttn-2',
      format: 'Nativo',
      isResident: true,
      description: 'Seleziona automaticamente il modello residente in VRAM o il miglior modello locale disponibile.'
    });

    // 2. Local Models from Disk (GGUF & Safetensors)
    localModels.forEach(m => {
      const id = m.model_id || m.filename || m.name;
      const rawName = m.display_name || m.name || m.filename || id;
      const specs = getModelSpecs(rawName, localModels) || {};
      
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

      list.push({
        id: id,
        name: rawName,
        shortName: rawName.replace(/^.*\//, '').replace(/\.gguf$/i, ''),
        provider: 'local',
        category: 'local',
        params: paramLabel,
        size: m.size_label || (m.size_gb ? `~${m.size_gb.toFixed(1)} GB` : 'Locale'),
        quant: quantLabel,
        format: m.format || (rawName.toLowerCase().includes('gguf') ? 'GGUF' : 'Safetensors'),
        isResident: isResident,
        isComplete: isComplete,
        hasPartFiles: !!m.has_part_files,
        estVram: m.est_vram_gb ? `~${m.est_vram_gb} GB VRAM` : null
      });
    });

    // 3. Configured Cloud Providers (if keys exist in localStorage)
    try {
      const pConfigs = JSON.parse(localStorage.getItem('sigma_ai_providers') || '{}');
      const cloudDefs = [
        { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic', params: '200K ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'gpt-4o', name: 'GPT-4o (Omni)', provider: 'openai', params: '128K ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'deepseek-chat', name: 'DeepSeek V3 (Chat)', provider: 'deepseek', params: '671B MoE', size: 'Cloud API', quant: 'FP8' },
        { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'google', params: '2M ctx', size: 'Cloud API', quant: 'FP16' },
        { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B (Groq)', provider: 'groq', params: '70B Versatile', size: 'Cloud Ultra-Fast', quant: 'FP8' }
      ];

      cloudDefs.forEach(c => {
        if (pConfigs[c.provider]?.has_api_key || pConfigs[c.provider]?.api_key) {
          list.push({
            id: c.id,
            name: `${c.name} (${c.provider.toUpperCase()})`,
            shortName: c.name,
            provider: c.provider,
            category: 'cloud',
            params: c.params,
            size: c.size,
            quant: c.quant,
            format: 'Cloud API',
            isResident: false
          });
        }
      });
    } catch {}

    return list;
  }, [localModels, serverInfo]);

  // Active selected model object
  const activeModelObj = useMemo(() => {
    return allModels.find(m => m.id === selectedModel) || allModels[0];
  }, [allModels, selectedModel]);

  // Filtered models by search query and category
  const filteredModels = useMemo(() => {
    return allModels.filter(m => {
      const matchCat = activeCategory === 'all' || 
        (activeCategory === 'local' && m.category === 'local') ||
        (activeCategory === 'cloud' && m.category === 'cloud') ||
        (activeCategory === 'resident' && m.isResident);

      if (!matchCat) return false;
      if (!searchQuery.trim()) return true;

      const q = searchQuery.toLowerCase();
      return (
        m.name.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        (m.params && m.params.toLowerCase().includes(q)) ||
        (m.quant && m.quant.toLowerCase().includes(q)) ||
        (m.size && m.size.toLowerCase().includes(q))
      );
    });
  }, [allModels, activeCategory, searchQuery]);

  return (
    <div ref={dropdownRef} style={{ position: 'relative', width: '100%' }}>
      {/* Active Model Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
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
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          <div style={{
            width: '20px',
            height: '20px',
            borderRadius: '5px',
            background: activeModelObj?.isResident ? 'rgba(63, 185, 80, 0.2)' : 'rgba(0, 242, 254, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            {activeModelObj?.isResident ? (
              <Zap size={12} color="#3fb950" />
            ) : (
              <Cpu size={12} color="#00f2fe" />
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', overflow: 'hidden', textAlign: 'left' }}>
            <div style={{
              fontSize: '0.74rem',
              fontWeight: 800,
              color: isLight ? '#24292f' : '#f0f6fc',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {activeModelObj?.shortName || activeModelObj?.name}
            </div>

            {/* Badges row: Params, Quant, Size */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
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
            </div>
          </div>
        </div>

        <ChevronDown size={14} color="#8b949e" style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }} />
      </button>

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
          maxHeight: '380px'
        }}>
          {/* Search Box */}
          <div style={{
            padding: '8px',
            borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <Search size={12} color="#8b949e" />
            <input
              type="text"
              placeholder="Cerca per nome, peso (27B) o quant (Q4_K_S)..."
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
          </div>

          {/* Category Tabs */}
          <div style={{
            display: 'flex',
            padding: '4px 6px',
            gap: '4px',
            background: isLight ? '#f6f8fa' : '#0d1117',
            borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
          }}>
            {[
              { id: 'all', label: 'Tutti' },
              { id: 'local', label: '⚡ GPU Locali' },
              { id: 'cloud', label: '☁️ Cloud' }
            ].map(cat => (
              <button
                key={cat.id}
                type="button"
                onClick={() => setActiveCategory(cat.id)}
                style={{
                  flex: 1,
                  padding: '3px 0',
                  borderRadius: '5px',
                  fontSize: '0.64rem',
                  fontWeight: activeCategory === cat.id ? 800 : 500,
                  background: activeCategory === cat.id ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.15)') : 'transparent',
                  border: activeCategory === cat.id ? '1px solid rgba(0, 242, 254, 0.3)' : 'none',
                  color: activeCategory === cat.id ? '#00f2fe' : (isLight ? '#57606a' : '#8b949e'),
                  cursor: 'pointer'
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Model Items List */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
            {filteredModels.length === 0 ? (
              <div style={{ padding: '16px', fontSize: '0.72rem', color: '#8b949e', textAlign: 'center' }}>
                Nessun modello trovato per i filtri selezionati.
              </div>
            ) : (
              filteredModels.map(m => {
                const isSelected = selectedModel === m.id;
                return (
                  <div
                    key={m.id}
                    onClick={() => {
                      onSelectModel(m.id);
                      setIsOpen(false);
                    }}
                    style={{
                      padding: '8px 10px',
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
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {m.isResident && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#3fb950' }} />}
                        <span style={{ fontSize: '0.74rem', fontWeight: 800, color: isSelected ? '#00f2fe' : (isLight ? '#24292f' : '#f0f6fc') }}>
                          {m.shortName || m.name}
                        </span>
                      </div>
                      {isSelected && <Check size={12} color="#00f2fe" />}
                    </div>

                    {/* Meta tags */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', flexWrap: 'wrap' }}>
                      {m.params && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px', background: 'rgba(0, 242, 254, 0.15)', color: '#00f2fe' }}>
                          {m.params}
                        </span>
                      )}
                      {m.quant && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', color: isLight ? '#57606a' : '#8b949e' }}>
                          {m.quant}
                        </span>
                      )}
                      {m.size && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(210, 153, 34, 0.15)', color: '#d29922' }}>
                          {m.size}
                        </span>
                      )}
                      {m.format && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff' }}>
                          {m.format}
                        </span>
                      )}
                      {m.estVram && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(63, 185, 80, 0.15)', color: '#3fb950' }}>
                          {m.estVram}
                        </span>
                      )}
                      {(!m.isComplete || m.hasPartFiles) && (
                        <span style={{ fontSize: '0.58rem', fontWeight: 800, padding: '1px 5px', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }} title="Download parziale su disco. Usa Model Hub per completare il download.">
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
