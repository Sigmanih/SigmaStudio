import React, { useEffect } from 'react';

// Sub-components
import Sidebar from './components/Sidebar';
import Workspace from './components/Workspace';
import Dashboard from './components/Dashboard';
import ChatPanel from './components/Chat/ChatPanel';
import AIConfig from './components/AIConfig';
import ToastNotification from './components/ToastNotification';
import { ModuleModal, TaskModal, NewFileModal } from './components/modals';

// Context
import { AppProvider, useApp } from './contexts/AppContext';

// ==============================================================================
// SIGMA STUDIO | State Orchestrator v6.2 — Context & Provider Refactored
// ==============================================================================

function AppContent() {
  const {
    modules,
    loading,
    fetchModules,
    tasks,
    fetchTasks,
    onTaskSave,
    toggleTaskStatus,
    deleteTask,
    clearAllTasks,
    isTaskModalOpen,
    setIsTaskModalOpen,
    editingTask,
    setEditingTask,
    openTabs,
    activeTabId,
    setActiveTabId,
    openTab,
    closeTab,
    closeAllTabs,
    handleDirtyChange,
    handleFileDelete,
    toasts,
    addToast,
    removeToast,
    manifesti,
    fetchManifesti,
    topicsCount,
    aiChatOpen,
    setAiChatOpen,
    aiConfigOpen,
    setAiConfigOpen,
    leftVisible,
    setLeftVisible,
    rightVisible,
    setRightVisible,
    fileOps,
    moduleOps
  } = useApp();

  // --- MESSAGE EVENT LISTENERS ---
  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === 'OPEN_FILE' && e.data?.path) {
        const type = e.data.fileType || 'teoria';
        const filename = e.data.filename || e.data.path.split('/').pop();
        openTab({ path: e.data.path, filename }, type);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [openTab]);

  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.path) {
        const path = e.detail.path;
        const filename = path.split('/').pop();
        const section = path.includes('/teoria/') ? 'teoria'
          : path.includes('/test/') ? 'test'
          : path.includes('/viz/') ? 'viz'
          : path.includes('/docs/') ? 'docs' : 'teoria';
        openTab({ path, filename }, section);
      }
    };
    window.addEventListener('sigma-open-file', handler);
    return () => window.removeEventListener('sigma-open-file', handler);
  }, [openTab]);

  if (loading) return <div className="loading-screen">SIGMA_STUDIO Booting...</div>;

  return (
    <div className={`app-container ${!leftVisible ? 'left-collapsed' : ''} ${!rightVisible ? 'right-collapsed' : ''}`}>
      <Sidebar
        modules={modules}
        manifestiCount={manifesti.length}
        activeTabId={activeTabId}
        leftVisible={leftVisible}
        setLeftVisible={setLeftVisible}
        setActiveTabId={setActiveTabId}
        openTab={openTab}
        goHome={closeAllTabs}
        tasks={tasks}
        topicsCount={topicsCount}
      />

      <Workspace
        openTabs={openTabs}
        activeTabId={activeTabId}
        setActiveTabId={setActiveTabId}
        closeTab={closeTab}
        closeAllTabs={closeAllTabs}
        modules={modules}
        manifesti={manifesti}
        tasks={tasks}
        terminalOutput={fileOps.terminalOutput}
        openTab={openTab}
        handleDirtyChange={handleDirtyChange}
        handleFileDelete={handleFileDelete}
        deleteFileDirectly={fileOps.deleteFileDirectly}
        runTest={fileOps.runTest}
        setFileModalContext={fileOps.setFileModalContext}
        setIsFileModalOpen={fileOps.setIsFileModalOpen}
        setEditingTask={setEditingTask}
        setIsTaskModalOpen={setIsTaskModalOpen}
        fetchData={fetchModules}
        fetchManifesti={fetchManifesti}
        toggleTaskStatus={toggleTaskStatus}
        deleteTask={deleteTask}
        clearAllTasks={clearAllTasks}
      />

      <Dashboard
        tasks={tasks}
        rightVisible={rightVisible}
        setRightVisible={setRightVisible}
        toggleTaskStatus={toggleTaskStatus}
        setEditingTask={setEditingTask}
        setIsTaskModalOpen={setIsTaskModalOpen}
        deleteTask={deleteTask}
        activeTabId={activeTabId}
      />

      <ModuleModal
        isOpen={moduleOps.isModalOpen}
        onClose={() => { moduleOps.setIsModalOpen(false); moduleOps.setEditingModule(null); }}
        onSave={moduleOps.editingModule ? moduleOps.handleUpdateModule : moduleOps.handleCreateModule}
        initialData={moduleOps.editingModule || {}}
      />
      <TaskModal
        isOpen={isTaskModalOpen}
        onClose={() => { setIsTaskModalOpen(false); setEditingTask(null); }}
        onSave={onTaskSave}
        initialData={editingTask}
        onOpenFile={(path) => openTab({ path, filename: path.split('/').pop() }, 'teoria')}
      />
      <NewFileModal
        isOpen={fileOps.isFileModalOpen}
        onClose={() => fileOps.setIsFileModalOpen(false)}
        onSave={fileOps.handleCreateFile}
        folder={fileOps.fileModalContext.folder}
        type={fileOps.fileModalContext.type}
      />

      {/* AI CHAT TOGGLE BUTTON — FIRST in DOM to stay clickable on all browsers */}
      <div className="ai-float-bar">
        <button
          className="ai-float-btn"
          onClick={() => setAiChatOpen(!aiChatOpen)}
          title={aiChatOpen ? 'Chiudi AI Chat' : 'Apri AI Chat'}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </button>
        <button
          className="ai-float-btn config"
          onClick={() => setAiConfigOpen(true)}
          title="Configurazione AI"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </button>
      </div>

      {/* AI CHAT PANEL — AFTER the float bar so it doesn't cover the button */}
      {aiChatOpen && (
        <ChatPanel
          manifesti={manifesti}
          openFiles={openTabs.filter(t => t.type !== 'module').map(t => t.path)}
          onClose={() => setAiChatOpen(false)}
          onOpenConfig={() => setAiConfigOpen(true)}
          onTasksUpdated={fetchTasks}
          addToast={addToast}
        />
      )}

      {/* AI CONFIG MODAL */}
      <AIConfig isOpen={aiConfigOpen} onClose={() => setAiConfigOpen(false)} />
      
      {/* Toast Notifications */}
      <ToastNotification toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}