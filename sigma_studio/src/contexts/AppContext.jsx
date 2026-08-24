import React, { createContext, useContext, useState, useEffect } from 'react';

// Hooks
import { useModules } from '../hooks/useModules';
import { useTasks } from '../hooks/useTasks';
import { useTabs } from '../hooks/useTabs';
import { useToast } from '../components/ToastNotification';
import { useFileOps } from '../hooks/useFileOps';
import { useModuleOps } from '../hooks/useModuleOps';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const { modules, loading, fetchModules, createModule, updateModule, deleteModule } = useModules();
  const { tasks, setTasks, fetchTasks, handleTaskSave, toggleTaskStatus, deleteTask, clearAllTasks } = useTasks();
  const { openTabs, activeTabId, setActiveTabId, openTab, closeTab, closeAllTabs, handleDirtyChange, handleFileDelete } = useTabs();
  const { toasts, addToast, removeToast } = useToast();

  const [manifesti, setManifesti] = useState([]);
  const [topicsCount, setTopicsCount] = useState(0);

  // AI chat config open & state
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [aiConfigOpen, setAiConfigOpen] = useState(false);

  // Theme state ('dark' | 'light')
  const [theme, setTheme] = useState(() => localStorage.getItem('sigma_app_theme') || 'dark');

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  useEffect(() => {
    localStorage.setItem('sigma_app_theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
    document.body.className = theme === 'light' ? 'theme-light' : 'theme-dark';
  }, [theme]);

  // UI layout state
  const [leftVisible, setLeftVisible] = useState(true);
  const [rightVisible, setRightVisible] = useState(true);

  // Fetch topics count
  const fetchTopicsCount = async () => {
    try {
      const res = await fetch('/api/topics');
      const data = await res.json();
      if (data.topics) setTopicsCount(data.topics.length);
    } catch (e) {}
  };

  // Fetch manifesti list
  const fetchManifesti = async () => {
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      if (data.success) setManifesti(data.manifesti || data.files || []);

    } catch (e) {
      console.error("Fetch manifesti error:", e);
    }
  };

  // File Operations Hook
  const fileOps = useFileOps({
    fetchManifesti,
    fetchModules,
    openTab,
    openTabs,
    handleFileDelete
  });

  // Module Operations Hook
  const moduleOps = useModuleOps({
    createModule,
    updateModule,
    deleteModule,
    handleFileDelete
  });

  // Task modal UI state
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);

  const onTaskSave = async (taskData) => {
    if (await handleTaskSave(taskData, editingTask)) {
      setIsTaskModalOpen(false);
      setEditingTask(null);
    }
  };

  const clearSystemMemory = async (options = { clearTasks: true, clearChat: true }) => {
    try {
      const res = await fetch('/api/system/clear-memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options)
      });
      const data = await res.json();
      if (options.clearTasks) {
        if (typeof clearAllTasks === 'function') {
          await clearAllTasks();
        } else if (typeof setTasks === 'function') {
          setTasks([]);
        }
      }
      if (options.clearChat) {
        try {
          localStorage.removeItem('sigma_chat_sessions');
          localStorage.removeItem('sigma_active_session');
          Object.keys(localStorage).forEach(k => {
            if (k.startsWith('sigma_chat_msgs_') || k.startsWith('sigma_chat_session_')) {
              localStorage.removeItem(k);
            }
          });
        } catch (e) {}
      }
      window.dispatchEvent(new CustomEvent('sigma-memory-cleared'));
      addToast(data.message || 'Memoria e task ripuliti con successo.', 'success');
      return data;
    } catch (err) {
      console.error('Clear system memory error:', err);
      addToast('Errore durante la pulizia: ' + err.message, 'error');
      return { success: false, error: err.message };
    }
  };

  // Initial load
  useEffect(() => {
    fetchModules();
    fetchTasks();
    fetchManifesti();
    fetchTopicsCount();
  }, []);

  const value = {
    // Modules
    modules,
    loading,
    fetchModules,
    createModule,
    updateModule,
    deleteModule,
    
    // Tasks
    tasks,
    fetchTasks,
    onTaskSave,
    toggleTaskStatus,
    deleteTask,
    clearAllTasks,
    clearSystemMemory,
    isTaskModalOpen,
    setIsTaskModalOpen,
    editingTask,
    setEditingTask,
    
    // Tabs
    openTabs,
    activeTabId,
    setActiveTabId,
    openTab,
    closeTab,
    closeAllTabs,
    handleDirtyChange,
    handleFileDelete,
    
    // Toasts
    toasts,
    addToast,
    removeToast,
    
    // Local / manifesti state
    manifesti,
    setManifesti,
    fetchManifesti,
    topicsCount,
    setTopicsCount,
    fetchTopicsCount,
    
    // Chat state toggles
    aiChatOpen,
    setAiChatOpen,
    aiConfigOpen,
    setAiConfigOpen,
    
    // Theme state
    theme,
    setTheme,
    toggleTheme,

    // UI Layout state
    leftVisible,
    setLeftVisible,
    rightVisible,
    setRightVisible,
    
    // Sub operations
    fileOps,
    moduleOps
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
