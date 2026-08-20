import React, { useState, useEffect } from 'react';
import { X, FileText, Terminal, PieChart, BookOpen, Trash2, ChevronRight, Home, MessageSquare, FlaskConical, Brain, Zap, User, Palette, Blocks, Image, Store, Key, Music, DownloadCloud, Settings, Sliders } from 'lucide-react';
import WelcomeDashboard from './WelcomeDashboard';
import SkillsHub from './SkillsHub';
import StudioEditor from './Workspace/StudioEditor';
import ImageViewer from './Workspace/ImageViewer';
import ManifestiGallery from './Workspace/ManifestiGallery';
import ModuleView from './Workspace/ModuleView';
import { MarkdownPreview, SigmaLabEditor } from './SigmaLab';
import ChatWorkspace from './Chat/ChatWorkspace';

import AccountTab from './AccountTab';
import McpHubTab from './McpHubTab';
import DomoticaTab from './Workspace/DomoticaTab';
import MarketplaceTab from './MarketplaceTab';
import AIConfigTab from './AIConfigTab';
import MusicTab from './Music/MusicTab';
import { useModuleState } from '../hooks/useModuleState';
import { getLazyModule } from '../modules/registry';
import ModuleNotInstalled from '../modules/ModuleNotInstalled';

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
    case 'model_hub': return <DownloadCloud size={16} />;
    case 'account': case 'settings': return <Settings size={16} />;
    case 'creative_studio': return <Palette size={16} />;
    case 'skills_hub': return <Blocks size={16} />;
    case 'marketplace': return <Store size={16} />;
    case 'image_viewer': return <Image size={16} />;
    case 'music': case 'music_lounge': case 'audio_studio': return <Music size={16} />;
    case 'ai_config': case 'config': return <Sliders size={16} />;
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
  const isAudioInstalled = modulesState.audio_studio === true || modulesState.sigma_audio_studio === true;
  const isDomoticaInstalled = modulesState.sigma_domotica === true;

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
      const isKnowledgeInstalled = modulesState.sigma_knowledge === true;
      const LazyKnowledge = getLazyModule('knowledge');
      if (!isKnowledgeInstalled || !LazyKnowledge) {
        return <ModuleNotInstalled tabType="knowledge" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Argomenti & Memoria...</div>}>
          <LazyKnowledge onOpenFile={openTabFromMappa} openTab={openTab} />
        </React.Suspense>
      );
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
      const isRoadmapInstalled = modulesState.sigma_roadmap === true;
      const LazyRoadmap = getLazyModule('roadmap');
      if (!isRoadmapInstalled || !LazyRoadmap) {
        return <ModuleNotInstalled tabType="roadmap" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Pianificazione & Audit...</div>}>
          <LazyRoadmap 
            tasks={tasks} 
            onAdd={() => { setEditingTask(null); setIsTaskModalOpen(true); }} 
            onEdit={(task) => { setEditingTask(task); setIsTaskModalOpen(true); }}
            onDelete={(task) => handleRoadmapDelete(task)}
            onToggleStatus={handleRoadmapToggleStatus}
            onOpenFile={openTabFromMappa}
            onClearAll={clearAllTasks}
            openTab={openTab}
          />
        </React.Suspense>
      );
    }

    if (tab.type === 'chat') {
      return <ChatWorkspace />;
    }
    if (tab.type === 'research_lab') {
      const isResearchInstalled = modulesState.sigma_research_lab === true;
      const LazyResearch = getLazyModule('research_lab');
      if (!isResearchInstalled || !LazyResearch) {
        return <ModuleNotInstalled tabType="research_lab" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Pipelines Lab...</div>}>
          <LazyResearch onTasksUpdated={() => {}} addToast={(msg, type, duration) => {}} openTab={openTab} />
        </React.Suspense>
      );
    }

    if (tab.type === 'training_lab') {
      const isTrainingInstalled = modulesState.sigma_training_lab === true;
      const LazyTraining = getLazyModule('training_lab');
      if (!isTrainingInstalled || !LazyTraining) {
        return <ModuleNotInstalled tabType="training_lab" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Training Lab...</div>}>
          <LazyTraining
            addToast={(msg, type, dur) => {}}
            onTasksUpdated={() => {}}
            openTab={openTab}
          />
        </React.Suspense>
      );
    }

    if (tab.type === 'hardware_lab' || tab.type === 'hardware') {
      const isHardwareInstalled = modulesState.sigma_hardware_lab === true;
      const LazyHardware = getLazyModule('hardware_lab');
      if (!isHardwareInstalled || !LazyHardware) {
        return <ModuleNotInstalled tabType="hardware_lab" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Hardware Lab...</div>}>
          <LazyHardware addToast={(msg, type, dur) => {}} openTab={openTab} />
        </React.Suspense>
      );
    }

    if (tab.type === 'model_hub' || tab.type === 'hf_hub') {
      const isModelHubInstalled = modulesState.sigma_model_hub === true;
      const LazyModelHub = getLazyModule('model_hub');
      if (!isModelHubInstalled || !LazyModelHub) {
        return <ModuleNotInstalled tabType="model_hub" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Modelli Hub...</div>}>
          <LazyModelHub addToast={(msg, type, dur) => {}} openTab={openTab} />
        </React.Suspense>
      );
    }

    if (tab.type === 'mcp_hub') {

      return <McpHubTab />;
    }
    if (tab.type === 'domotica' || tab.type === 'home_assistant') {
      if (!isDomoticaInstalled) {
        return <ModuleNotInstalled tabType="domotica" openTab={openTab} />;
      }
      return <DomoticaTab />;
    }
    if (tab.type === 'account' || tab.type === 'settings') {
      return <AccountTab openTab={openTab} />;
    }
    if (tab.type === 'creative_studio') {
      const isCreativeInstalled = modulesState.sigma_creative_lab === true;
      const LazyCreative = getLazyModule('creative_studio');
      if (!isCreativeInstalled || !LazyCreative) {
        return <ModuleNotInstalled tabType="creative_studio" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Creative Lab...</div>}>
          <LazyCreative openTab={openTab} />
        </React.Suspense>
      );
    }
    if (tab.type === 'voice_studio') {
      const isVoiceInstalled = modulesState.sigma_voice_studio === true;
      const LazyVoice = getLazyModule('voice_studio');
      if (!isVoiceInstalled || !LazyVoice) {
        return <ModuleNotInstalled tabType="voice_studio" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Voice Studio...</div>}>
          <LazyVoice openTab={openTab} />
        </React.Suspense>
      );
    }
    if (tab.type === 'developer_lab') {
      const isDevInstalled = modulesState.sigma_developer_lab === true;
      const LazyDev = getLazyModule('developer_lab');
      if (!isDevInstalled || !LazyDev) {
        return <ModuleNotInstalled tabType="developer_lab" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Developer Lab...</div>}>
          <LazyDev openTab={openTab} />
        </React.Suspense>
      );
    }

    if (tab.type === 'network_lab') {
      const isNetInstalled = modulesState.sigma_network_lab === true;
      const LazyNet = getLazyModule('network_lab');
      if (!isNetInstalled || !LazyNet) {
        return <ModuleNotInstalled tabType="network_lab" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Network Lab...</div>}>
          <LazyNet openTab={openTab} />
        </React.Suspense>
      );
    }
    if (tab.type === 'email_client') {
      const isEmailInstalled = modulesState.sigma_email_client === true;
      const LazyEmail = getLazyModule('email_client');
      if (!isEmailInstalled || !LazyEmail) {
        return <ModuleNotInstalled tabType="email_client" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Email Hub...</div>}>
          <LazyEmail openTab={openTab} />
        </React.Suspense>
      );
    }
    if (tab.type === 'messaging_hub') {
      const isMsgInstalled = modulesState.sigma_messaging_hub === true;
      const LazyMsg = getLazyModule('messaging_hub');
      if (!isMsgInstalled || !LazyMsg) {
        return <ModuleNotInstalled tabType="messaging_hub" openTab={openTab} />;
      }
      return (
        <React.Suspense fallback={<div style={{ padding: '32px', color: '#94a3b8', textAlign: 'center' }}>Caricamento Messaging Hub...</div>}>
          <LazyMsg openTab={openTab} />
        </React.Suspense>
      );
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
        return <ModuleNotInstalled tabType="music" openTab={openTab} />;
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