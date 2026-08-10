import React, { useState, useEffect, useCallback, Suspense, lazy } from 'react';
import {
  Wand2, Edit3, Box, Hexagon, Layers, Workflow, Film, Cpu,
  ChevronLeft, ChevronRight, Database, X
} from 'lucide-react';
import AssetPanel from './AssetPanel';
import PropertiesPanel from './PropertiesPanel';
import ToolPanel from './ToolPanel';
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

// three.js pesa ~600 kB: si carica solo quando si apre davvero la vista 3D.
const Viewport3D = lazy(() => import('./Viewport3D/Viewport3D'));

const VIEWS = [
  { id: 'generate', label: 'Generate', icon: Wand2 },
  { id: 'edit', label: 'Edit', icon: Edit3 },
  { id: '3d', label: '3D', icon: Box },
  { id: 'mesh', label: 'Mesh Lab', icon: Hexagon },
  { id: 'materials', label: 'Materials', icon: Layers },
  { id: 'video', label: 'Video', icon: Film },
  { id: 'pipeline', label: 'Pipeline', icon: Workflow },
  { id: 'models', label: 'Modelli', icon: Cpu },
];

export default function CreativeStudio() {
  const [activeView, setActiveView] = useState('generate');
  const [leftVisible, setLeftVisible] = useState(true);
  const [rightVisible, setRightVisible] = useState(true);

  const [assets, setAssets] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState(null);

  const [backends, setBackends] = useState([]);
  const [capabilities, setCapabilities] = useState({});
  const [stats, setStats] = useState({ total: 0 });

  const { runTask, busy, error, clearError } = useCreativeApi();
  const { models, inventory, refresh: refreshModels } = useCreativeModels();

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

  /** Inserisce gli asset appena prodotti in cima al vault senza rileggere tutto. */
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

  // --- operazioni ------------------------------------------------------

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

  /** Vision agent: il risultato non è un asset ma un'analisi da mostrare. */
  const handleVision = useCallback((task_type, params = {}) => (
    runTask('/api/creative/vision',
      { task_type, asset_id: params.asset_id, params },
      { label: `Vision: ${task_type}` })
      .then(data => {
        fetchAssets();
        return data.result;
      })
  ), [runTask, fetchAssets]);

  const handleUpload = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      runTask('/api/creative/upload', { name: file.name, image: reader.result }, { label: 'Upload' })
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

  // --- rendering -------------------------------------------------------

  const is3DAsset = (a) => a && (a.type === 'model_3d' || a.type === 'mesh');

  const renderCanvas = () => {
    switch (activeView) {
      case 'generate':
        return <GeneratePanel
          onGenerate={handleGenerate}
          onUpload={handleUpload}
          isGenerating={!!busy}
          backends={backends}
          models={models}
          inventory={inventory}
          recentAssets={assets.filter(a => a.type === 'image' || a.type === 'render')}
          onSelectAsset={setSelectedAsset} />;
      case 'edit':
        return <EditCanvas
          asset={selectedAsset}
          busy={!!busy}
          capabilities={capabilities}
          onEdit={handleEdit}
          onUpscale={handleUpscale}
          onSegment={handleSegment} />;
      case '3d':
        return (
          <Suspense fallback={<div className="cs-canvas-wrapper"><p>Caricamento viewport 3D...</p></div>}>
            <Viewport3D
              asset={selectedAsset}
              busy={!!busy}
              canGenerate3D={(capabilities.image_to_3d || []).length > 0}
              blenderAvailable={(capabilities.render || []).length > 0}
              onGenerate3D={handle3D}
              onRender={handleRender} />
          </Suspense>
        );
      case 'mesh':
        return <MeshLab
          asset={selectedAsset}
          busy={!!busy}
          blenderAvailable={(capabilities.render || []).length > 0}
          onMeshOp={handleMesh} />;
      case 'materials':
        return <MaterialsPanel
          asset={selectedAsset}
          assets={assets}
          busy={!!busy}
          blenderAvailable={(capabilities.render || []).length > 0}
          onMaterial={handleMaterial} />;
      case 'video':
        return <VideoPanel
          asset={selectedAsset}
          assets={assets}
          busy={!!busy}
          canVideo={((capabilities.text_to_video || []).length + (capabilities.image_to_video || []).length) > 0}
          onVideo={handleVideo} />;
      case 'pipeline':
        return <CreativeNodeEditor assets={assets} onAssetsProduced={registerAssets} />;
      case 'models':
        return <ModelsPanel models={models} inventory={inventory} onRefresh={refreshModels} />;
      default:
        return null;
    }
  };

  return (
    <div className="creative-studio cs-fade-in">
      {/* Hero Visual Banner matching Domotica Header Style */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '20px 32px 18px 32px',
        minHeight: '100px',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: 'linear-gradient(to right, rgba(8, 10, 16, 0.98) 45%, rgba(8, 10, 16, 0.5) 100%), url("/images/creative_lab_banner.jpg")',
        backgroundSize: '360px auto',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right center',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Wand2 size={14} /> CREATIVE LAB & MULTIMEDIA GENERATION BUS
            </div>
            <h1 style={{ margin: '0 0 4px 0', fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              🎨 Creative Lab — Generazione & Design Multimediale
            </h1>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#a0aec0', lineHeight: 1.4 }}>
              Generazione di immagini, modelli 3D, mesh Blender, texture PBR e video con ComfyUI, Automatic1111 e SDXL.
            </p>
          </div>
        </div>
      </div>

      <div className="cs-toolbar" style={{ margin: 0, borderRadius: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button className="collapse-btn" onClick={() => setLeftVisible(!leftVisible)}><ChevronLeft size={16} /></button>
          <div className="cs-view-modes">
            {VIEWS.map(v => (
              <button
                key={v.id}
                className={`cs-mode-btn ${activeView === v.id ? 'active' : ''}`}
                onClick={() => setActiveView(v.id)}
              >
                <v.icon size={16} /> {v.label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="cs-toolbar-status">
            <BackendStatus backends={backends} />
            <div className="cs-toolbar-sep" />
            <Database size={14} color="var(--accent)" />
            <span>{stats.total ?? assets.length} asset</span>
          </div>
          <button className="collapse-btn" onClick={() => setRightVisible(!rightVisible)}><ChevronRight size={16} /></button>
        </div>
      </div>

      {error && (
        <div className="cs-error-bar">
          <span>{error}</span>
          <button onClick={clearError}><X size={14} /></button>
        </div>
      )}

      <div className="cs-workspace">
        {leftVisible && (
          <div className="cs-panel-left">
            <AssetPanel
              assets={assets}
              selectedAsset={selectedAsset}
              onSelectAsset={setSelectedAsset}
              onUpload={handleUpload}
              onDelete={handleDelete}
              onOpenAsset={(a) => {
                setSelectedAsset(a);
                setActiveView(is3DAsset(a) ? '3d' : 'edit');
              }} />
            <ToolPanel activeView={activeView} onViewChange={setActiveView} />
          </div>
        )}

        <div className="cs-canvas">
          {renderCanvas()}
          {busy && <ProgressOverlay label={busy.label} progress={busy.progress} status={busy.message} />}
        </div>

        {rightVisible && (
          <div className="cs-panel-right">
            <PropertiesPanel
              asset={selectedAsset}
              busy={busy}
              capabilities={capabilities}
              onUpscale={handleUpscale}
              onEdit={handleEdit}
              onGenerate3D={handle3D}
              onMaterial={handleMaterial}
              onRender={handleRender}
              onVideo={handleVideo}
              onVision={handleVision}
              onDelete={handleDelete}
              onSelectAsset={(id) => {
                const found = assets.find(a => a.id === id);
                if (found) setSelectedAsset(found);
              }} />
          </div>
        )}
      </div>
    </div>
  );
}
