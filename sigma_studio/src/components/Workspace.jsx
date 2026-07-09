import React from 'react';
import { X, FileText, Terminal, PieChart, BookOpen, Trash2, ChevronRight, Home, MessageSquare, FlaskConical } from 'lucide-react';
import WelcomeDashboard from './WelcomeDashboard';
import { RoadmapView } from './Dashboard';
import StudioEditor from './Workspace/StudioEditor';
import ManifestiGallery from './Workspace/ManifestiGallery';
import ModuleView from './Workspace/ModuleView';
import { MarkdownPreview, MappaArgomenti, SigmaLabEditor } from './SigmaLab';
import ChatWorkspace from './Chat/ChatWorkspace';
import ResearchLabTab from './Workspace/ResearchLabTab';

// ==============================================================================
// Workspace — Content area that renders based on active tab type
// ==============================================================================

const FileIcon = ({ type }) => {
  switch (type) {
    case 'manifesti': case 'manifesto':
    case 'teoria': case 'docs': case 'whitepaper': return <FileText size={16} />;
    case 'test': return <Terminal size={16} />;
    case 'viz': return <PieChart size={16} />;
    case 'module': return <BookOpen size={16} />;
    case 'chat': return <MessageSquare size={16} />;
    case 'research_lab': return <FlaskConical size={16} />;
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
    let type = 'teoria';
    if (pathLower.includes('/test/')) type = 'test';
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
    
    // All file types (teoria, docs, whitepaper, manifesti, test, viz) use the unified SigmaLabEditor
    if (tab.type === 'teoria' || tab.type === 'docs' || tab.type === 'whitepaper' || tab.type === 'manifesti' || tab.type === 'test' || tab.type === 'viz') {
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