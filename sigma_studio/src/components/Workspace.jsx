import React, { useState, useEffect } from 'react';
import { X, FileText, Terminal, PieChart, BookOpen, Trash2, ChevronRight, Home, MessageSquare, FlaskConical, Brain, Zap, User, Palette, Blocks, Image, Store, Key, Music } from 'lucide-react';
import WelcomeDashboard from './WelcomeDashboard';
import CreativeStudio from './CreativeStudio/CreativeStudio';
import SkillsHub from './SkillsHub';
import { RoadmapView } from './Dashboard';
import StudioEditor from './Workspace/StudioEditor';
import ImageViewer from './Workspace/ImageViewer';
import ManifestiGallery from './Workspace/ManifestiGallery';
import ModuleView from './Workspace/ModuleView';
import { MarkdownPreview, MappaArgomenti, SigmaLabEditor } from './SigmaLab';
import ChatWorkspace from './Chat/ChatWorkspace';
import ResearchLabTab from './Workspace/ResearchLabTab';
import TrainingLab from './TrainingLab';
import HardwareLab from './HardwareLab';

import AccountTab from './AccountTab';
import McpHubTab from './McpHubTab';
import KnowledgeNodeExplorer from './KnowledgeNodeExplorer';
import DomoticaTab from './Workspace/DomoticaTab';
import MarketplaceTab from './MarketplaceTab';
import AIConfigTab from './AIConfigTab';
import MusicTab from './Music/MusicTab';
import { useModuleState } from '../hooks/useModuleState';

// ==============================================================================
// Workspace — Content area that renders based on active tab type
// ==============================================================================

const FileIcon = ({ type }) => {
  switch (type) {
    case 'manifesti': case 'manifesto':
    case 'scripts': case 'test': return <Terminal size={16} />;
    case 'viz': return <PieChart size={16} />;
    case 'module': return <BookOpen size={16} />;
    case 'chat': return <MessageSquare size={16} />;
    case 'research_lab': return <FlaskConical size={16} />;
    case 'training_lab': return <Brain size={16} />;
    case 'hardware_lab': return <Zap size={16} />;
    case 'account': return <User size={16} />;
    case 'creative_studio': return <Palette size={16} />;
    case 'skills_hub': return <Blocks size={16} />;
    case 'marketplace': return <Store size={16} />;
    case 'image_viewer': return <Image size={16} />;
    case 'music': case 'music_lounge': case 'audio_studio': return <Music size={16} />;
    case 'ai_config': case 'config': return <Key size={16} />;
    default: return <FileText size={16} />;
  }
};

export default function Workspace({ 
  openTabs, 
  activeTabId, 
  setActiveTabId, 
  closeTab, 
  closeAllTabs, 
  modules, 
  manifesti,
  tasks,
  handleDirtyChange,
  handleFileDelete,
  deleteFileDirectly,
  runTest,
  openTab,
  setFileModalContext,
  setIsFileModalOpen,
  setEditingTask,
  setIsTaskModalOpen,
  terminalOutput,
  fetchData,
  fetchManifesti,
  toggleTaskStatus,
  deleteTask,
  clearAllTasks
}) {
  const { modulesState } = useModuleState();
  const isAudioInstalled = modulesState.audio_studio === true;

  const handleRoadmapDelete = (task) => {
    if (confirm(`Eliminare il task "${task.titolo}"?`)) {
      deleteTask(task.titolo);
    }
  };

  const handleRoadmapToggleStatus = (task) => {
    toggleTaskStatus(task);
  };
  
  // Handler for opening files from the mappa component
  const openTabFromMappa = (path) => {
    if (!path) return;
    const filename = path.split('/').pop() || path;
    const pathLower = path.toLowerCase();
    // Image files go to the dedicated image viewer
    if (/\.(?:png|jpg|jpeg|webp|svg|gif|bmp|tiff)$/i.test(pathLower)) {
      openTab({ path, filename }, 'image_viewer');
      return;
    }
    let type = 'teoria';
    if (pathLower.includes('/scripts/') || pathLower.includes('/test/')) type = 'scripts';
    else if (pathLower.includes('/viz/')) type = 'viz';
    else if (pathLower.includes('/docs/')) {
      type = path.split('/').pop()?.toUpperCase().startsWith('WHITEPAPER_') ? 'whitepaper' : 'docs';
    }
    else if (pathLower.includes('/teoria/')) type = 'teoria';
    openTab({ path, filename }, type);
  };
  
  const getActiveContent = () => {
    const tab = openTabs.find(t => t.id === activeTabId);
    if (!tab) return <WelcomeDashboard modules={modules} openTab={openTab} />;

    if (tab.type === 'module') {
      const folderName = tab.id.replace('module-', '');
      const mod = modules.find(m => m.folder === folderName);
      if (!mod) return <div className="placeholder-content">Modulo [{folderName}] non trovato</div>;
      
      const openAddFile = (type) => {
        setFileModalContext({ folder: mod.folder, type });
        setIsFileModalOpen(true);
      };

      return (
        <ModuleView
          mod={mod}
          openTab={openTab}
          deleteFileDirectly={deleteFileDirectly}
          openAddFile={openAddFile}
          onRefresh={fetchData}
        />
      );
    }
    
    // All file types (teoria, docs, whitepaper, manifesti, scripts, test, viz, editor) use the unified SigmaLabEditor
    if (tab.type === 'teoria' || tab.type === 'docs' || tab.type === 'whitepaper' || tab.type === 'manifesti' || tab.type === 'scripts' || tab.type === 'test' || tab.type === 'viz' || tab.type === 'editor') {
      return (
        <SigmaLabEditor
          tab={tab}
          onDirtyChange={handleDirtyChange}
          onDelete={(id, path) => {
            deleteFileDirectly({ stopPropagation: () => {} }, path);
            handleFileDelete(id);
          }}
          onRun={runTest}
          terminalOutput={terminalOutput}
          onOpenFile={openTabFromMappa}
        />
      );
    }
    if (tab.type === 'mappa_argomenti' || tab.type === 'knowledge') {
      return <MappaArgomenti onOpenFile={openTabFromMappa} />;
    }
    if (tab.type === 'whitepapers_lib') {
      return (
        <ManifestiGallery 
          modules={modules} 
          manifesti={manifesti} 
          openTab={openTab} 
          setFileModalContext={setFileModalContext}
          setIsFileModalOpen={setIsFileModalOpen}
          fetchManifesti={fetchManifesti}
        />
      );
    }
    if (tab.type === 'roadmap') {
      return (
        <RoadmapView 
          tasks={tasks} 
          onAdd={() => { setEditingTask(null); setIsTaskModalOpen(true); }} 
          onEdit={(task) => { setEditingTask(task); setIsTaskModalOpen(true); }}
          onDelete={(task) => handleRoadmapDelete(task)}
          onToggleStatus={handleRoadmapToggleStatus}
          onOpenFile={openTabFromMappa}
          onClearAll={clearAllTasks}
        />
      );
    }
    if (tab.type === 'chat') {
      return <ChatWorkspace />;
    }
    if (tab.type === 'research_lab') {
      return <ResearchLabTab onTasksUpdated={() => {}} addToast={(msg, type, duration) => {}} />;
    }
    if (tab.type === 'training_lab') {
      return (
        <TrainingLab
          addToast={(msg, type, dur) => {}}
          onTasksUpdated={() => {}}
        />
      );
    }
    if (tab.type === 'hardware_lab') {
      return <HardwareLab addToast={(msg, type, dur) => {}} />;
    }
    if (tab.type === 'mcp_hub') {
      return <McpHubTab />;
    }
    if (tab.type === 'domotica' || tab.type === 'home_assistant') {
      return <DomoticaTab />;
    }
    if (tab.type === 'account') {
      return <AccountTab />;
    }
    if (tab.type === 'creative_studio') {
      return <CreativeStudio />;
    }
    if (tab.type === 'skills_hub') {
      return <SkillsHub />;
    }
    if (tab.type === 'marketplace') {
      return <MarketplaceTab openTab={openTab} />;
    }
    if (tab.type === 'image_viewer') {
      return <ImageViewer tab={tab} />;
    }
    if (tab.type === 'music' || tab.type === 'music_lounge' || tab.type === 'audio_studio') {
      if (!isAudioInstalled) {
        return (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            padding: '40px',
            textAlign: 'center',
            color: '#8b8fa3',
            gap: '16px'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.05)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '2rem'
            }}>
              📻
            </div>
            <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.2rem', fontWeight: 700 }}>
              Modulo Audio Studio Disinstallato
            </h3>
            <p style={{ margin: 0, maxWidth: '440px', fontSize: '0.85rem', lineHeight: '1.5' }}>
              Il modulo <strong>Hi-Fi Sound & FM Radio Studio</strong> è attualmente disinstallato o disattivato. Puoi installarlo in qualsiasi momento con un click dall'Hub Moduli.
            </p>
            <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
              <button
                onClick={() => openTab({ name: '📦 Hub Moduli & Estensioni' }, 'marketplace')}
                style={{
                  background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                  border: 'none',
                  color: '#000',
                  fontWeight: 800,
                  borderRadius: '8px',
                  padding: '10px 18px',
                  cursor: 'pointer',
                  fontSize: '0.82rem'
                }}
              >
                Apri Hub Moduli
              </button>
              <button
                onClick={() => closeTab(tab.id)}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  borderRadius: '8px',
                  padding: '10px 18px',
                  cursor: 'pointer',
                  fontSize: '0.82rem'
                }}
              >
                Chiudi Scheda
              </button>
            </div>
          </div>
        );
      }
      return <MusicTab />;
    }
    if (tab.type === 'ai_config' || tab.type === 'config') {
      return <AIConfigTab openTab={openTab} />;
    }
    return <div className="placeholder-content">Content type {tab.type} not implemented in preview.</div>;
  };

  return (
    <main className="workspace">
      <div className="tab-bar">
        {/* Bacheca tab — always visible */}
        <div
          className={`tab ${activeTabId === null ? 'active' : ''}`}
          onClick={() => setActiveTabId(null)}
          style={{ cursor: 'pointer' }}
        >
          <Home size={16} />
          <span>Bacheca</span>
        </div>
        {openTabs.map(tab => (
          <div key={tab.id} className={`tab ${activeTabId === tab.id ? 'active' : ''}`} onClick={() => setActiveTabId(tab.id)}>
            <FileIcon type={tab.type} />
            <span>{tab.name}{tab.isDirty && " *"}</span>
            <button className="tab-close" onClick={(e) => closeTab(e, tab.id)}><X size={14} /></button>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center' }}>
          {openTabs.length > 0 && (
            <button onClick={closeAllTabs} title="Chiudi tutte le schede" className="btn-close-all">
              <X size={16} />
            </button>
          )}
        </div>
      </div>
      <div className="content-area">
        {getActiveContent()}
      </div>
    </main>
  );
}