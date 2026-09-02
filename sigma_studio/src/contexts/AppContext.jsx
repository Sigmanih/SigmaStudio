import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// Hooks
import { useModules } from '../hooks/useModules';
import { useTasks } from '../hooks/useTasks';
import { useTabs } from '../hooks/useTabs';
import { useToast } from '../components/ToastNotification';
import { useFileOps } from '../hooks/useFileOps';
import { useModuleOps } from '../hooks/useModuleOps';

const AppContext = createContext(null);

export const DEFAULT_CUSTOM_THEME = {
  primary: '#00d2ff',
  accent: '#bc8cff',
  bg: '#030305',
  cardBg: '#121622',
  text: '#f0f0f5',
  borderRadius: 14,
  bgEngine: 'pattern', // 'pattern' | 'mesh' | 'solid' | 'custom_image'
  bgCustomImage: '',
  bgOverlayOpacity: 0.85,
};

export const THEME_PRESETS = [
  { id: 'cyber-dark', name: 'Cyber Dark', desc: 'Predefinito futuristico ciano & viola neon', primary: '#00d2ff', accent: '#bc8cff', bg: '#030305', cardBg: '#121622', text: '#f0f0f5' },
  { id: 'light', name: 'Warm Cream', desc: 'Tema chiaro elegante crema & ambra', primary: '#ea580c', accent: '#8b5cf6', bg: '#f7f4ed', cardBg: '#ffffff', text: '#111111' },
  { id: 'oled-midnight', name: 'OLED Midnight', desc: 'Nero profondo & blu elettrico per display OLED', primary: '#38bdf8', accent: '#10b981', bg: '#000000', cardBg: '#0b0b10', text: '#ffffff' },
  { id: 'nord-slate', name: 'Nordic Slate', desc: 'Grigio ardesia nordico & verde smeraldo', primary: '#88c0d0', accent: '#a3be8c', bg: '#1a202c', cardBg: '#222b3d', text: '#eceff4' },
  { id: 'synthwave', name: 'Synthwave Sunset', desc: 'Viola cyberpunk, magenta fucsia & arancio', primary: '#f43f5e', accent: '#f97316', bg: '#120924', cardBg: '#1e103b', text: '#fdf4ff' },
  { id: 'monokai-pro', name: 'Monokai Pro', desc: 'Grigio tecnico, oro solare & corallo', primary: '#ffd866', accent: '#ff6188', bg: '#1c1d1f', cardBg: '#2d3036', text: '#fcfcfa' },
];

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

  // --- Multi-Theme Engine & Customizer State ---
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('sigma_app_theme');
    if (saved === 'dark') return 'cyber-dark';
    return saved || 'cyber-dark';
  });

  const [customThemeConfig, setCustomThemeConfig] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_custom_theme_config');
      return saved ? { ...DEFAULT_CUSTOM_THEME, ...JSON.parse(saved) } : DEFAULT_CUSTOM_THEME;
    } catch {
      return DEFAULT_CUSTOM_THEME;
    }
  });

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' || prev === 'cream' ? 'cyber-dark' : 'light'));
  };

  const applyCustomProperties = useCallback((config, currentTheme) => {
    const root = document.documentElement;
    if (currentTheme === 'custom') {
      root.style.setProperty('--sigma-primary', config.primary);
      root.style.setProperty('--sigma-primary-glow', `${config.primary}22`);
      root.style.setProperty('--sigma-primary-border', `${config.primary}55`);
      root.style.setProperty('--sigma-accent', config.accent);
      root.style.setProperty('--sigma-accent-glow', `${config.accent}22`);
      root.style.setProperty('--sigma-bg', config.bg);
      root.style.setProperty('--sigma-card-bg', config.cardBg);
      root.style.setProperty('--sigma-text', config.text);
      root.style.setProperty('--sigma-radius-md', `${config.borderRadius}px`);
    } else {
      // Clear inline overrides so CSS preset classes take precedence
      root.style.removeProperty('--sigma-primary');
      root.style.removeProperty('--sigma-primary-glow');
      root.style.removeProperty('--sigma-primary-border');
      root.style.removeProperty('--sigma-accent');
      root.style.removeProperty('--sigma-accent-glow');
      root.style.removeProperty('--sigma-bg');
      root.style.removeProperty('--sigma-card-bg');
      root.style.removeProperty('--sigma-text');
      root.style.removeProperty('--sigma-radius-md');
    }

    // Background Engine Handling
    if (config.bgEngine === 'custom_image' && config.bgCustomImage) {
      document.body.classList.add('has-custom-bg');
      root.style.setProperty('--sigma-bg-custom-image', `url("${config.bgCustomImage}")`);
      root.style.setProperty('--sigma-bg-overlay-opacity', config.bgOverlayOpacity ?? 0.85);
    } else if (config.bgEngine === 'solid') {
      document.body.classList.remove('has-custom-bg');
      root.style.setProperty('--sigma-bg-pattern', 'none');
    } else if (config.bgEngine === 'mesh') {
      document.body.classList.remove('has-custom-bg');
      root.style.setProperty('--sigma-bg-pattern', 'radial-gradient(at 10% 20%, var(--sigma-primary-glow) 0, transparent 60%), radial-gradient(at 90% 80%, var(--sigma-accent-glow) 0, transparent 60%)');
    } else {
      document.body.classList.remove('has-custom-bg');
      root.style.removeProperty('--sigma-bg-pattern');
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('sigma_app_theme', theme);
    localStorage.setItem('sigma_custom_theme_config', JSON.stringify(customThemeConfig));
    document.documentElement.setAttribute('data-theme', theme);
    document.body.className = (theme === 'light' || theme === 'cream') ? 'theme-light' : 'theme-dark';
    applyCustomProperties(customThemeConfig, theme);
  }, [theme, customThemeConfig, applyCustomProperties]);

  const updateCustomTheme = (updater) => {
    setCustomThemeConfig(prev => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater };
      return next;
    });
  };

  const resetThemeToDefault = () => {
    setTheme('cyber-dark');
    setCustomThemeConfig(DEFAULT_CUSTOM_THEME);
    addToast('Tema ripristinato alle impostazioni predefinite', 'success');
  };

  // UI layout state & Mobile Drawer
  const [leftVisible, setLeftVisible] = useState(true);
  const [rightVisible, setRightVisible] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const toggleMobileSidebar = () => {
    setMobileSidebarOpen(prev => !prev);
  };

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

  // System Cleanup Modal state
  const [isCleanupModalOpen, setIsCleanupModalOpen] = useState(false);
  const openCleanupModal = () => setIsCleanupModalOpen(true);
  const closeCleanupModal = () => setIsCleanupModalOpen(false);

  const onTaskSave = async (taskData) => {
    if (await handleTaskSave(taskData, editingTask)) {
      setIsTaskModalOpen(false);
      setEditingTask(null);
    }
  };

  const clearSystemMemory = async (options = { clearTasks: true, clearChat: false }) => {
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
        window.dispatchEvent(new CustomEvent('sigma-chat-cleared', { detail: { clear_history: true } }));
      }
      window.dispatchEvent(new CustomEvent('sigma-system-cleanup-done', { detail: options }));
      addToast(data.message || 'Memoria e risorse ripulite con successo.', 'success');
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

    // System Cleanup Modal
    isCleanupModalOpen,
    setIsCleanupModalOpen,
    openCleanupModal,
    closeCleanupModal,
    
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
    
    // Multi-Theme Engine & Customizer
    theme,
    setTheme,
    toggleTheme,
    customThemeConfig,
    updateCustomTheme,
    resetThemeToDefault,

    // UI Layout state & Mobile Drawer
    leftVisible,
    setLeftVisible,
    rightVisible,
    setRightVisible,
    mobileSidebarOpen,
    setMobileSidebarOpen,
    toggleMobileSidebar,
    
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
