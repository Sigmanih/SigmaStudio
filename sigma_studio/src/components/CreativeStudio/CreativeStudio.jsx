import React, { useState, useEffect, useCallback, useMemo, Suspense, lazy } from 'react';
import {
  Wand2, Edit3, Box, Hexagon, Layers, Workflow, Film, Cpu,
  Database, X, Upload, Search, Download, Trash2, CheckCircle2,
  Sparkles, Sliders, LayoutGrid, List, Play, Scissors, ChevronRight,
  RefreshCw, Eye
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import TechSpaceCanvas from '../common/TechSpaceCanvas';
import GeneratePanel from './Generate/GeneratePanel';
import EditCanvas from './Edit/EditCanvas';
import MeshLab from './MeshLab/MeshLab';
import MaterialsPanel from './Materials/MaterialsPanel';
import VideoPanel from './Video/VideoPanel';
import ModelsPanel from './Models/ModelsPanel';
import CreativeNodeEditor from './NodeEditor/CreativeNodeEditor';
import BackendStatus from './shared/BackendStatus';
import ProgressOverlay from './shared/ProgressOverlay';
import { useCreativeApi } from './useCreativeApi';
import { useCreativeModels } from './useCreativeModels';

// Lazy load 3D viewport
const Viewport3D = lazy(() => import('./Viewport3D/Viewport3D'));

const VIEWS = [
  { id: 'generate', label: '2D Generator', icon: Wand2, badge: 'SDXL' },
  { id: 'edit', label: 'Ritocco & Edit', icon: Edit3, badge: 'INPAINT' },
  { id: '3d', label: '3D Viewport', icon: Box, badge: 'THREE.JS' },
  { id: 'mesh', label: 'Mesh Lab', icon: Hexagon, badge: 'BLENDER' },
  { id: 'materials', label: 'Materiali PBR', icon: Layers, badge: 'TEXTURE' },
  { id: 'video', label: 'Video Studio', icon: Film, badge: 'MOTION' },
  { id: 'pipeline', label: 'Pipeline Nodi', icon: Workflow, badge: 'COMFY' },
  { id: 'models', label: 'Modelli AI', icon: Cpu, badge: 'DIFFUSION' },
];

const ASSET_FILTERS = [
  { id: 'all', label: 'Tutti' },
  { id: 'image', label: 'Immagini' },
  { id: 'model_3d', label: '3D' },
  { id: 'video', label: 'Video' },
  { id: 'material', label: 'Materiali' },
];

export default function CreativeStudio() {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [activeView, setActiveView] = useState('generate');
  const [assets, setAssets] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [assetSearch, setAssetSearch] = useState('');
  const [assetFilter, setAssetFilter] = useState('all');

  const [backends, setBackends] = useState([]);
  const [capabilities, setCapabilities] = useState({});
  const [stats, setStats] = useState({ total: 0 });

  const { runTask, busy, error, clearError } = useCreativeApi();
  const { models, inventory, refresh: refreshModels } = useCreativeModels();
  const uploadInputRef = React.useRef(null);

  // Theme styling tokens
  const bg = isLight ? '#fcfaf6' : '#0b0d13';
  const cardBg = isLight ? '#fffdf9' : '#11141d';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const innerCardBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.035)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#a0a6bc';

  const fetchAssets = useCallback(() => (
    fetch('/api/creative/assets?limit=200')
      .then(r => r.json())
      .then(data => { if (data.success && Array.isArray(data.assets)) setAssets(data.assets); })
      .catch(() => {})
  ), []);

  const fetchCreativeData = useCallback(() => {
    fetchAssets();
    fetch('/api/creative/backends/status').then(r => r.json()).then(data => {
      if (data.success) {
        setBackends(data.backends || []);
        setCapabilities(data.capabilities || {});
      }
    }).catch(() => {});
    fetch('/api/creative/stats').then(r => r.json()).then(data => {
      if (data.success) setStats(data.stats || { total: 0 });
    }).catch(() => {});
  }, [fetchAssets]);

  useEffect(() => { fetchCreativeData(); }, [fetchCreativeData]);

  const registerAssets = useCallback((produced) => {
    const list = (Array.isArray(produced) ? produced : [produced]).filter(Boolean);
    if (!list.length) return;
    setAssets(prev => {
      const ids = new Set(list.map(a => a.id));
      return [...list, ...prev.filter(a => !ids.has(a.id))];
    });
    setSelectedAsset(list[0]);
    fetch('/api/creative/stats').then(r => r.json())
      .then(data => { if (data.success) setStats(data.stats || { total: 0 }); }).catch(() => {});
  }, []);

  // --- Operations ---
  const handleGenerate = useCallback((params, backend) => (
    runTask('/api/creative/generate',
      { task_type: 'text_to_image', params, backend },
      { label: 'Generazione immagine' })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleEdit = useCallback((task_type, asset_id, params = {}) => (
    runTask('/api/creative/edit',
      { task_type, asset_id, params },
      { label: `Edit: ${task_type}` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleMesh = useCallback((task_type, asset_id, params = {}) => (
    runTask('/api/creative/mesh',
      { task_type, asset_id, params },
      { label: `Mesh: ${task_type}` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handle3D = useCallback((task_type, params = {}) => (
    runTask('/api/creative/3d', { task_type, params }, { label: `3D: ${task_type}` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleMaterial = useCallback((task_type, params = {}) => (
    runTask('/api/creative/material', { task_type, params }, { label: `Materiale: ${task_type}` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleRender = useCallback((asset_id, params = {}) => (
    runTask('/api/creative/render', { asset_id, params }, { label: 'Render Blender' })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleUpscale = useCallback((asset_id, scale = 2, restore = false) => (
    runTask('/api/creative/generate',
      { task_type: 'upscale', params: { source_asset_id: asset_id, scale, restore } },
      { label: restore ? `Restauro ${scale}x` : `Upscale ${scale}x` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleVideo = useCallback((task_type, params = {}) => (
    runTask('/api/creative/video', { task_type, params }, { label: `Video: ${task_type}` })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleSegment = useCallback((asset_id, prompt = '') => (
    runTask('/api/creative/segment', { asset_id, params: { prompt } }, { label: 'Segmentazione' })
      .then(data => registerAssets(data.asset))
      .catch(() => {})
  ), [runTask, registerAssets]);

  const handleUpload = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      runTask('/api/creative/upload', { name: file.name, image: reader.result }, { label: 'Upload Asset' })
        .then(data => registerAssets(data.asset))
        .catch(() => {});
    };
    reader.readAsDataURL(file);
  }, [runTask, registerAssets]);

  const handleDelete = useCallback((asset_id) => {
    fetch('/api/creative/assets/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id }),
    }).then(() => {
      setAssets(prev => prev.filter(a => a.id !== asset_id));
      setSelectedAsset(prev => (prev?.id === asset_id ? null : prev));
      fetchCreativeData();
    }).catch(() => {});
  }, [fetchCreativeData]);

  // Filtered assets
  const filteredAssets = useMemo(() => {
    return assets.filter(a => {
      const matchType = assetFilter === 'all' || a.type === assetFilter || (assetFilter === '3d' && (a.type === 'mesh' || a.type === 'model_3d'));
      const matchSearch = !assetSearch.trim() || a.name?.toLowerCase().includes(assetSearch.toLowerCase().trim());
      return matchType && matchSearch;
    });
  }, [assets, assetFilter, assetSearch]);

  // Render main canvas for active view
  const renderCanvas = () => {
    switch (activeView) {
      case 'generate':
        return (
          <GeneratePanel
            onGenerate={handleGenerate}
            onUpload={handleUpload}
            isGenerating={!!busy}
            backends={backends}
            models={models}
            inventory={inventory}
            recentAssets={assets.filter(a => a.type === 'image' || a.type === 'render')}
            onSelectAsset={setSelectedAsset}
          />
        );
      case 'edit':
        return (
          <EditCanvas
            asset={selectedAsset}
            busy={!!busy}
            capabilities={capabilities}
            onEdit={handleEdit}
            onUpscale={handleUpscale}
            onSegment={handleSegment}
          />
        );
      case '3d':
        return (
          <Suspense fallback={<div style={{ padding: '40px', textAlign: 'center' }}><p>Caricamento Viewport 3D...</p></div>}>
            <Viewport3D
              asset={selectedAsset}
              busy={!!busy}
              canGenerate3D={(capabilities.image_to_3d || []).length > 0}
              blenderAvailable={(capabilities.render || []).length > 0}
              onGenerate3D={handle3D}
              onRender={handleRender}
            />
          </Suspense>
        );
      case 'mesh':
        return (
          <MeshLab
            asset={selectedAsset}
            busy={!!busy}
            blenderAvailable={(capabilities.render || []).length > 0}
            onMeshOp={handleMesh}
          />
        );
      case 'materials':
        return (
          <MaterialsPanel
            asset={selectedAsset}
            assets={assets}
            busy={!!busy}
            blenderAvailable={(capabilities.render || []).length > 0}
            onMaterial={handleMaterial}
          />
        );
      case 'video':
        return (
          <VideoPanel
            asset={selectedAsset}
            assets={assets}
            busy={!!busy}
            canVideo={((capabilities.text_to_video || []).length + (capabilities.image_to_video || []).length) > 0}
            onVideo={handleVideo}
          />
        );
      case 'pipeline':
        return <CreativeNodeEditor assets={assets} onAssetsProduced={registerAssets} />;
      case 'models':
        return <ModelsPanel models={models} inventory={inventory} onRefresh={refreshModels} />;
      default:
        return null;
    }
  };

  return (
    <div className="creative-studio cs-fade-in" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      background: bg,
      color: titleColor,
      fontFamily: 'inherit',
      overflow: 'hidden',
      position: 'relative'
    }}>
      <TechSpaceCanvas isLight={isLight} />

      {/* TOP HEADER & STUDIO CONTROLS */}
      <div style={{
        padding: '14px 24px',
        background: cardBg,
        borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        zIndex: 10,
        flexShrink: 0
      }}>
        {/* Title & Engine status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.2rem'
          }}>
            🎨
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: titleColor }}>
              Creative Lab
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.68rem', color: subtitleColor }}>
              <BackendStatus backends={backends} />
              <span>•</span>
              <Database size={11} color="#00d2ff" />
              <span>{stats.total ?? assets.length} asset generati</span>
            </div>
          </div>
        </div>

        {/* View Switcher Chips (Horizontal Pills) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: innerCardBg,
          padding: '4px',
          borderRadius: '12px',
          border: innerCardBorder,
          overflowX: 'auto'
        }}>
          {VIEWS.map(v => {
            const active = activeView === v.id;
            const Icon = v.icon;
            return (
              <button
                key={v.id}
                onClick={() => setActiveView(v.id)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: 'none',
                  background: active ? (isLight ? '#111827' : '#00d2ff') : 'transparent',
                  color: active ? '#ffffff' : subtitleColor,
                  fontSize: '0.74rem',
                  fontWeight: active ? 800 : 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                <Icon size={13} />
                <span>{v.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div style={{
          padding: '8px 16px',
          background: 'rgba(239, 68, 68, 0.15)',
          borderBottom: '1px solid #ef4444',
          color: '#ef4444',
          fontSize: '0.78rem',
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 10
        }}>
          <span>{error}</span>
          <button onClick={clearError} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* TWO-COLUMN STUDIO WORKBENCH */}
      <div style={{
        display: 'flex',
        flex: 1,
        height: 'calc(100% - 65px)',
        overflow: 'hidden',
        position: 'relative'
      }}>
        {/* COLUMN 1: LEFT CONTROL & ASSET HUB */}
        <aside style={{
          width: '330px',
          minWidth: '290px',
          maxWidth: '360px',
          flexShrink: 0,
          background: cardBg,
          borderRight: cardBorder,
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
          zIndex: 5
        }}>
          {/* Asset Hub Header & Upload */}
          <div style={{ padding: '12px 14px', borderBottom: innerCardBorder }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: titleColor }}>
                📦 Libreria Asset ({filteredAssets.length})
              </span>
              <button
                onClick={() => uploadInputRef.current?.click()}
                style={{
                  padding: '4px 10px',
                  borderRadius: '8px',
                  background: 'rgba(0, 210, 255, 0.15)',
                  border: '1px solid rgba(0, 210, 255, 0.3)',
                  color: '#00d2ff',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Upload size={12} /> Carica
              </button>
              <input
                ref={uploadInputRef}
                type="file"
                accept="image/*"
                hidden
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ''; }}
              />
            </div>

            {/* Search Input */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '5px 10px',
              borderRadius: '8px',
              background: innerCardBg,
              border: innerCardBorder,
              marginBottom: '8px'
            }}>
              <Search size={12} color={subtitleColor} />
              <input
                type="text"
                placeholder="Cerca per nome..."
                value={assetSearch}
                onChange={e => setAssetSearch(e.target.value)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: titleColor,
                  fontSize: '0.74rem',
                  outline: 'none',
                  width: '100%'
                }}
              />
            </div>

            {/* Type Filter Pills */}
            <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
              {ASSET_FILTERS.map(f => (
                <button
                  key={f.id}
                  onClick={() => setAssetFilter(f.id)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '0.66rem',
                    fontWeight: 700,
                    border: 'none',
                    background: assetFilter === f.id ? '#00d2ff' : 'transparent',
                    color: assetFilter === f.id ? '#000000' : subtitleColor,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Scrollable Asset List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '10px 12px',
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '8px',
            alignContent: 'flex-start'
          }}>
            {filteredAssets.length === 0 ? (
              <div style={{ gridColumn: '1 / -1', padding: '24px 12px', textAlign: 'center', color: subtitleColor, fontSize: '0.74rem' }}>
                Nessun asset presente. Genera o carica una nuova opera!
              </div>
            ) : (
              filteredAssets.map(a => {
                const isSelected = selectedAsset?.id === a.id;
                return (
                  <div
                    key={a.id}
                    onClick={() => setSelectedAsset(a)}
                    onDoubleClick={() => {
                      setSelectedAsset(a);
                      setActiveView(a.type === 'model_3d' || a.type === 'mesh' ? '3d' : 'edit');
                    }}
                    style={{
                      borderRadius: '10px',
                      overflow: 'hidden',
                      background: innerCardBg,
                      border: isSelected ? '2px solid #00d2ff' : innerCardBorder,
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      position: 'relative',
                      boxShadow: isSelected ? '0 0 12px rgba(0, 210, 255, 0.25)' : 'none',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ width: '100%', height: '80px', background: 'rgba(0,0,0,0.25)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {a.url ? (
                        <img src={a.url} alt={a.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <Box size={22} color={subtitleColor} />
                      )}
                    </div>
                    <div style={{ padding: '6px 8px' }}>
                      <div style={{ fontSize: '0.7rem', fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {a.name || 'Senza titolo'}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: subtitleColor, display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
                        <span style={{ textTransform: 'uppercase' }}>{a.type || 'image'}</span>
                        {a.dimensions && <span>{a.dimensions.width}×{a.dimensions.height}</span>}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Selected Asset Quick Inspector (Bottom Card) */}
          {selectedAsset && (
            <div style={{
              padding: '12px 14px',
              borderTop: cardBorder,
              background: innerCardBg,
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: titleColor }}>
                  🔍 Azioni su Asset
                </span>
                <span style={{ fontSize: '0.65rem', color: '#00d2ff', fontWeight: 700 }}>
                  {selectedAsset.name?.slice(0, 18) || 'Asset selezionato'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}>
                <button
                  onClick={() => handleUpscale(selectedAsset.id, 2)}
                  style={{
                    padding: '5px 8px',
                    borderRadius: '6px',
                    background: cardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Sparkles size={11} color="#00d2ff" /> Upscale 2x
                </button>

                <button
                  onClick={() => {
                    setActiveView('3d');
                    handle3D('image_to_3d', { source_asset_id: selectedAsset.id });
                  }}
                  style={{
                    padding: '5px 8px',
                    borderRadius: '6px',
                    background: cardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Box size={11} color="#bc8cff" /> Genera 3D
                </button>

                <button
                  onClick={() => {
                    setActiveView('video');
                    handleVideo('image_to_video', { source_asset_id: selectedAsset.id });
                  }}
                  style={{
                    padding: '5px 8px',
                    borderRadius: '6px',
                    background: cardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Film size={11} color="#ea580c" /> Anima Video
                </button>

                <button
                  onClick={() => handleDelete(selectedAsset.id)}
                  style={{
                    padding: '5px 8px',
                    borderRadius: '6px',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    color: '#ef4444',
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <Trash2 size={11} /> Elimina
                </button>
              </div>
            </div>
          )}
        </aside>

        {/* COLUMN 2: MAIN INTERACTIVE STUDIO WORKBENCH */}
        <main style={{
          flex: 1,
          height: '100%',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative'
        }}>
          {renderCanvas()}
          {busy && <ProgressOverlay label={busy.label} progress={busy.progress} status={busy.message} />}
        </main>
      </div>
    </div>
  );
}
