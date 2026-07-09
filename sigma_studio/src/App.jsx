import React, { useState, useEffect } from 'react';

// Sub-components
import Sidebar from './components/Sidebar';
import Workspace from './components/Workspace';
import Dashboard from './components/Dashboard';
import ChatPanel from './components/Chat/ChatPanel';
import AIConfig from './components/AIConfig';
import ToastNotification, { useToast } from './components/ToastNotification';
import { ModuleModal, TaskModal, NewFileModal } from './components/modals';

// Hooks
import { useModules } from './hooks/useModules';
import { useTasks } from './hooks/useTasks';
import { useTabs } from './hooks/useTabs';

// ==============================================================================
// SIGMA STUDIO | State Orchestrator v6.2 — refactored with hooks
// ==============================================================================

export default function App() {
  // --- HOOKS ---
  const { modules, loading, fetchModules, createModule, updateModule, deleteModule } = useModules();
  const { tasks, fetchTasks, handleTaskSave, toggleTaskStatus, deleteTask, clearAllTasks } = useTasks();
  const { openTabs, activeTabId, setActiveTabId, openTab, closeTab, closeAllTabs, handleDirtyChange, handleFileDelete } = useTabs();
  const { toasts, addToast, removeToast } = useToast();

  // --- LOCAL STATE ---
  const [manifesti, setManifesti] = useState([]);
  const [topicsCount, setTopicsCount] = useState(0);
  const [terminalOutput, setTerminalOutput] = useState("Sigma Studio Initialized. Ready for research.\n");
  
  // --- UI STATE ---
  const [leftVisible, setLeftVisible] = useState(true);
  const [rightVisible, setRightVisible] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingModule, setEditingModule] = useState(null);
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [fileModalContext, setFileModalContext] = useState({ folder: "", type: "" });
  
  // --- AI CHAT STATE ---
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [aiConfigOpen, setAiConfigOpen] = useState(false);

  // --- INIT ---
  useEffect(() => {
    fetchModules();
    fetchTasks();
    fetchManifesti();
    fetchTopicsCount();
  }, []);

  const fetchTopicsCount = async () => {
    try {
      const res = await fetch('/api/topics');
      const data = await res.json();
      if (data.topics) setTopicsCount(data.topics.length);
    } catch (e) {}
  };

  const fetchManifesti = async () => {
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      if (data.success) setManifesti(data.files || []);
    } catch (e) {
      console.error("Fetch manifesti error:", e);
    }
  };

  // --- FILE ACTIONS ---
  const handleCreateFile = async (filename) => {
    let { folder, type } = fileModalContext;
    let finalPath = `${folder}/${type}/${filename}`;
    
    if (type === 'whitepaper') {
      finalPath = `${folder}/docs/WHITEPAPER_${filename}`;
    }
    if (type === 'manifesti') {
      finalPath = `manifesti/${filename}`;
    }

    const initialContent = type === 'test' 
      ? "# Sigma Validation Script\nimport os\n\ndef run():\n    print('Validating...')\n\nif __name__ == '__main__':\n    run()" 
      : "# Nuovo Manifesto Sigma\n= = = = = = = = = = = =\n\n**Sezione**: \n\nContenuto del manifesto...";
    
    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: finalPath, content: initialContent })
      });
      if ((await res.json()).success) {
        setIsFileModalOpen(false);
        if (type === 'manifesti') {
          fetchManifesti();
        } else {
          fetchModules();
        }
        openTab({ path: finalPath, filename: filename.replace('.md', '') }, type);
      }
    } catch (e) { alert(e.message); }
  };

  const deleteFileDirectly = async (e, path) => {
    e.stopPropagation();
    if (!confirm(`Sei sicuro di voler eliminare dal progetto il file: ${path}?`)) return;
    try {
      const res = await fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      if ((await res.json()).success) {
        const tabMatch = openTabs.find(t => t.path === path);
        if (tabMatch) handleFileDelete(tabMatch.id);
        fetchModules();
      }
    } catch(e) { alert(e.message); }
  };

  const runTest = async (path) => {
    setTerminalOutput(`[RUNNING] ${path}...\n`);
    try {
      const res = await fetch('/api/run_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_path: path })
      });
      const data = await res.json();
      setTerminalOutput(prev => prev + (data.stdout || "") + (data.stderr || "") + `\n[EXIT] Code ${data.exit_code}`);
    } catch (e) { setTerminalOutput(prev => prev + `[ERROR] ${e.message}`); }
  };

  // --- MODULE CRUD ---
  const handleCreateModule = async (data) => {
    const ok = await createModule(data);
    if (ok) setIsModalOpen(false);
  };

  const handleUpdateModule = async (data) => {
    const ok = await updateModule(data, editingModule);
    if (ok) {
      setIsModalOpen(false);
      setEditingModule(null);
    }
  };

  const handleDeleteModule = async (folder) => {
    if (!confirm(`Sei sicuro di voler eliminare il modulo ${folder}?`)) return;
    const ok = await deleteModule(folder);
    if (ok) {
      handleFileDelete(`module-${folder}`);
    }
  };

  // --- TASK CRUD ---
  const onTaskSave = async (taskData) => {
    if (await handleTaskSave(taskData, editingTask)) {
      setIsTaskModalOpen(false);
      setEditingTask(null);
    }
  };

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
  }, []);

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
  }, []);

  // --- RENDER ---
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
        terminalOutput={terminalOutput}
        openTab={openTab}
        handleDirtyChange={handleDirtyChange}
        handleFileDelete={handleFileDelete}
        deleteFileDirectly={deleteFileDirectly}
        runTest={runTest}
        setFileModalContext={setFileModalContext}
        setIsFileModalOpen={setIsFileModalOpen}
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
      />

      <ModuleModal
        isOpen={isModalOpen}
        onClose={() => { setIsModalOpen(false); setEditingModule(null); }}
        onSave={editingModule ? handleUpdateModule : handleCreateModule}
        initialData={editingModule || {}}
      />
      <TaskModal
        isOpen={isTaskModalOpen}
        onClose={() => { setIsTaskModalOpen(false); setEditingTask(null); }}
        onSave={onTaskSave}
        initialData={editingTask}
        onOpenFile={(path) => openTab({ path, filename: path.split('/').pop() }, 'teoria')}
      />
      <NewFileModal
        isOpen={isFileModalOpen}
        onClose={() => setIsFileModalOpen(false)}
        onSave={handleCreateFile}
        folder={fileModalContext.folder}
        type={fileModalContext.type}
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