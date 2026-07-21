import React, { useEffect } from 'react';

// Sub-components
import Sidebar from './components/Sidebar';
import Workspace from './components/Workspace';
import ChatPanel from './components/Chat/ChatPanel';
import AIConfig from './components/AIConfig';
import ToastNotification from './components/ToastNotification';
import TaskFloatingPanel from './components/TaskFloatingPanel';
import { ModuleModal, TaskModal, NewFileModal } from './components/modals';

// Context
import { AppProvider, useApp } from './contexts/AppContext';

// ==============================================================================
// SIGMA STUDIO | State Orchestrator v7.0 — Floating UI Edition
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
    aiChatOpen,
    setAiChatOpen,
    aiConfigOpen,
    setAiConfigOpen,
    leftVisible,
    setLeftVisible,
    fileOps,
    moduleOps
  } = useApp();

  const [taskPanelOpen, setTaskPanelOpen] = React.useState(false);
  const [dockMinimized, setDockMinimized] = React.useState(false);

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

  const handleDeleteTask = (task) => {
    if (confirm(`Eliminare il task "${task.titolo}"?`)) {
      deleteTask(task.titolo);
    }
  };

  const handleOpenFileFromTask = (path) => {
    if (!path) return;
    const filename = path.split('/').pop() || path;
    const pathLower = path.toLowerCase();
    let type = 'teoria';
    if (pathLower.includes('/test/')) type = 'test';
    else if (pathLower.includes('/viz/')) type = 'viz';
    else if (pathLower.includes('/docs/')) type = 'docs';
    openTab({ path, filename }, type);
  };

  if (loading) return <div className="loading-screen">SIGMA_STUDIO Booting...</div>;

  return (
    <div className={`app-container ${!leftVisible ? 'left-collapsed' : ''}`}>
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
        topicsCount={0}
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

      {/* FLOATING DOCK BAR — BOTTOM LEFT */}
      <div className={`ai-float-dock-bar ${dockMinimized ? 'minimized' : ''}`}>
        <button
          className="dock-toggle-btn"
          onClick={() => setDockMinimized(!dockMinimized)}
          title={dockMinimized ? 'Espandi barra strumenti' : 'Nascondi in basso'}
        >
          {dockMinimized ? '⚡' : '❮'}
        </button>

        {!dockMinimized && (
          <div className="dock-buttons-row">
            {/* Task Roadmap button */}
            <button
              className={`dock-btn ${taskPanelOpen ? 'active' : ''}`}
              onClick={() => setTaskPanelOpen(!taskPanelOpen)}
              title={taskPanelOpen ? 'Riduci Task Roadmap' : 'Apri Task Roadmap'}
            >
              <span className="dock-btn-icon">📋</span>
              <span className="dock-btn-label">Roadmap</span>
              {tasks?.length > 0 && <span className="dock-btn-badge">{tasks.length}</span>}
            </button>

            {/* AI Chat button */}
            <button
              className={`dock-btn chat-btn ${aiChatOpen ? 'active' : ''}`}
              onClick={() => setAiChatOpen(!aiChatOpen)}
              title={aiChatOpen ? 'Riduci AI Chat' : 'Apri AI Chat'}
            >
              <span className="dock-btn-icon">💬</span>
              <span className="dock-btn-label">AI Chat</span>
              <span className="dock-btn-dot" style={{ backgroundColor: aiChatOpen ? '#00f2fe' : '#555' }} />
            </button>

            {/* AI Config button */}
            <button
              className={`dock-btn config-btn ${aiConfigOpen ? 'active' : ''}`}
              onClick={() => setAiConfigOpen(true)}
              title="Configurazione AI"
            >
              <span className="dock-btn-icon">⚙️</span>
              <span className="dock-btn-label">Config AI</span>
            </button>
          </div>
        )}
      </div>

      {/* TASK FLOATING PANEL */}
      {taskPanelOpen && (
        <TaskFloatingPanel
          tasks={tasks}
          onAdd={() => { setEditingTask(null); setIsTaskModalOpen(true); }}
          onEdit={(task) => { setEditingTask(task); setIsTaskModalOpen(true); }}
          onDelete={handleDeleteTask}
          onToggleStatus={toggleTaskStatus}
          onOpenFile={handleOpenFileFromTask}
          onClearAll={clearAllTasks}
          onClose={() => setTaskPanelOpen(false)}
        />
      )}

      {/* AI CHAT PANEL */}
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