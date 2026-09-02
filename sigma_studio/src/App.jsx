import React, { useState, useEffect } from 'react';
import { GripVertical, Sparkles, X, Calendar, Cpu, MessageSquare, Settings, Music, Trash2, RefreshCw } from 'lucide-react';

// Sub-components
import Sidebar from './components/Sidebar';
import Workspace from './components/Workspace';
import ChatPanel from './components/Chat/ChatPanel';
import AIConfig from './components/AIConfig';
import ToastNotification from './components/ToastNotification';
import MusicFloatingWidget from './components/Music/MusicFloatingWidget';
import { ModuleModal, TaskModal, NewFileModal, SystemCleanupModal } from './components/modals';

// Context
import { AppProvider, useApp } from './contexts/AppContext';
import { MusicProvider } from './contexts/MusicContext';

// Hooks
import { useModuleState } from './hooks/useModuleState';
import { getLazyHardwareFloating } from './modules/registry';


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
    clearSystemMemory,
    isTaskModalOpen,
    setIsTaskModalOpen,
    editingTask,
    setEditingTask,
    isCleanupModalOpen,
    openCleanupModal,
    closeCleanupModal,
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
    mobileSidebarOpen,
    setMobileSidebarOpen,
    fileOps,
    moduleOps
  } = useApp();

  const { modulesState, isLoaded: modulesLoaded } = useModuleState();
  const isAudioInstalled = modulesState.audio_studio === true;
  const isHardwareInstalled = modulesState.sigma_hardware_lab === true;
  const isRoadmapInstalled = modulesState.sigma_roadmap === true;


  const [taskPanelOpen, setTaskPanelOpen] = React.useState(false);
  const [hardwarePanelOpen, setHardwarePanelOpen] = React.useState(false);
  const [dockMinimized, setDockMinimized] = React.useState(true);

  const LazyHardwareFloating = React.useMemo(() => {
    if (isHardwareInstalled) {
      return getLazyHardwareFloating();
    }
    return null;
  }, [isHardwareInstalled]);


  // Floating dock bar drag state
  const [dockPos, setDockPos] = React.useState({ x: undefined, y: undefined });
  const [dockDragging, setDockDragging] = React.useState(false);
  const [dockDragStart, setDockDragStart] = React.useState({ x: 0, y: 0 });
  const hasMovedRef = React.useRef(false);

  useEffect(() => {
    if (!dockDragging) return;
    const hMM = (e) => {
      const dx = e.clientX - dockDragStart.x;
      const dy = e.clientY - dockDragStart.y;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        hasMovedRef.current = true;
        setDockPos(prev => ({
          x: (prev.x !== undefined ? prev.x : 20) + dx,
          y: (prev.y !== undefined ? prev.y : window.innerHeight - 70) + dy
        }));
        setDockDragStart({ x: e.clientX, y: e.clientY });
      }
    };
    const hMU = () => setDockDragging(false);
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => {
      document.removeEventListener('mousemove', hMM);
      document.removeEventListener('mouseup', hMU);
    };
  }, [dockDragging, dockDragStart]);

  const handleDockMouseDown = (e) => {
    if (e.button !== 0) return;
    hasMovedRef.current = false;
    const initialX = dockPos.x !== undefined ? dockPos.x : 20;
    const initialY = dockPos.y !== undefined ? dockPos.y : window.innerHeight - 70;
    setDockPos({ x: initialX, y: initialY });
    setDockDragStart({ x: e.clientX, y: e.clientY });
    setDockDragging(true);
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
    const configHandler = () => {
      openTab({ name: 'Providers' }, 'ai_config');
    };
    window.addEventListener('message', handler);
    window.addEventListener('open-ai-config', configHandler);
    return () => {
      window.removeEventListener('message', handler);
      window.removeEventListener('open-ai-config', configHandler);
    };
  }, [openTab]);

  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.path) {
        const path = e.detail.path;
        const filename = path.split('/').pop();
        const section = path.includes('/teoria/') ? 'teoria'
          : (path.includes('/scripts/') || path.includes('/test/')) ? 'scripts'
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
    if (pathLower.includes('/scripts/') || pathLower.includes('/test/')) type = 'scripts';
    else if (pathLower.includes('/viz/')) type = 'viz';
    else if (pathLower.includes('/docs/')) type = 'docs';
    openTab({ path, filename }, type);
  };

  if (loading) return <div className="loading-screen">SIGMA_STUDIO Booting...</div>;

  return (
    <div className={`app-container ${!leftVisible ? 'left-collapsed' : ''}`}>
      {/* Mobile Drawer Backdrop */}
      <div 
        className={`mobile-sidebar-backdrop ${mobileSidebarOpen ? 'active' : ''}`} 
        onClick={() => setMobileSidebarOpen(false)} 
      />

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

      {/* FLOATING ACTION SPEED-DIAL CONTAINER */}
      <div 
        className="ai-float-dock-container"
        style={{
          position: 'fixed',
          zIndex: 9990,
          left: dockPos.x !== undefined ? `${dockPos.x}px` : '20px',
          top: dockPos.y !== undefined ? `${dockPos.y}px` : undefined,
          bottom: dockPos.y !== undefined ? 'auto' : '20px',
          display: 'flex',
          alignItems: 'center'
        }}
      >
        {/* TRIGGER FLOATING ACTION BUTTON (FAB) — STATIONARY ANCHOR */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
          
          {/* EXPANDED SPEED-DIAL MENU CARD POPOVER — ABSOLUTE ABOVE FAB */}
          {!dockMinimized && (
            <div 
              style={{
                position: 'absolute',
                bottom: 'calc(100% + 12px)',
                left: 0,
                background: 'linear-gradient(135deg, rgba(14, 16, 26, 0.96), rgba(20, 24, 38, 0.92))',
                border: '1px solid rgba(0, 242, 254, 0.25)',
                borderRadius: '16px',
                padding: '14px',
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(0, 242, 254, 0.12)',
                backdropFilter: 'blur(20px) saturate(180%)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                minWidth: '270px',
                zIndex: 9995,
                animation: 'fadeInUp 0.22s cubic-bezier(0.16, 1, 0.3, 1)'
              }}
            >
              {/* Header / Drag handle */}
              <div 
                onMouseDown={handleDockMouseDown}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)',
                  cursor: 'grab', userSelect: 'none'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <GripVertical size={14} color="#8b8fa3" />
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#00f2fe', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
                    ⚡ Strumenti Rapidi
                  </span>
                </div>
                <button 
                  onClick={() => setDockMinimized(true)}
                  style={{ background: 'none', border: 'none', color: '#8b8fa3', cursor: 'pointer', padding: '2px', display: 'flex' }}
                  title="Chiudi menu"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Menu Items Stack */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                
                {/* Item 1: Chat AI Assistente (Ora Primo in Lista) */}
                <button
                  onClick={() => setAiChatOpen(!aiChatOpen)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 12px', borderRadius: '10px',
                    background: aiChatOpen ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                    border: aiChatOpen ? '1px solid rgba(188, 140, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                    color: aiChatOpen ? '#bc8cff' : '#e2e4eb',
                    cursor: 'pointer', transition: 'all 0.18s ease', textAlign: 'left'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(188, 140, 255, 0.15)', border: '1px solid rgba(188, 140, 255, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <MessageSquare size={16} color="#bc8cff" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>AI Chat Assistente</div>
                      <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>Finestra di chat agentica</div>
                    </div>
                  </div>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: aiChatOpen ? '#bc8cff' : '#555' }} />
                </button>

                {/* Item 2: Pianificazione & Task */}
                {isRoadmapInstalled && (
                  <button
                    onClick={() => {
                      // openTab takes (item, type); handleOpenTab never existed,
                      // so this button threw a ReferenceError on click.
                      openTab({ name: 'Pianificazione & Task' }, 'roadmap');
                      setDockMinimized(true);
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', borderRadius: '10px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      color: '#e2e4eb',
                      cursor: 'pointer', transition: 'all 0.18s ease', textAlign: 'left'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(0, 242, 254, 0.15)', border: '1px solid rgba(0, 242, 254, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Calendar size={16} color="#00f2fe" />
                      </div>
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>Pianificazione</div>
                        <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>Task board, calendario e log</div>
                      </div>
                    </div>
                    {tasks?.length > 0 && (
                      <span style={{ fontSize: '0.65rem', fontWeight: 700, background: 'rgba(0, 242, 254, 0.2)', color: '#00f2fe', padding: '2px 8px', borderRadius: '10px', border: '1px solid rgba(0, 242, 254, 0.3)' }}>
                        {tasks.length}
                      </span>
                    )}
                  </button>
                )}


                {/* Item 3: Hardware & GPU Mini Floating Panel */}
                {isHardwareInstalled && (
                  <button
                    onClick={() => {
                      setHardwarePanelOpen(!hardwarePanelOpen);
                      setDockMinimized(true);
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', borderRadius: '10px',
                      background: hardwarePanelOpen ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                      border: hardwarePanelOpen ? '1px solid rgba(63, 185, 80, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                      color: hardwarePanelOpen ? '#3fb950' : '#e2e4eb',
                      cursor: 'pointer', transition: 'all 0.18s ease', textAlign: 'left'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Cpu size={16} color="#3fb950" />
                      </div>
                      <div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>Mini Hardware</div>
                        <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>Pannello flottante VRAM & GPU</div>
                      </div>
                    </div>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: hardwarePanelOpen ? '#3fb950' : '#555' }} />
                  </button>
                )}




                {/* Item 4: Providers Hub (Allineato) */}
                <button
                  onClick={() => {
                    openTab({ name: 'Providers' }, 'ai_config');
                    setDockMinimized(true);
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 12px', borderRadius: '10px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    color: '#e2e4eb', cursor: 'pointer', transition: 'all 0.18s ease', textAlign: 'left'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(255, 184, 108, 0.15)', border: '1px solid rgba(255, 184, 108, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Settings size={16} color="#ffb86c" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>Providers</div>
                      <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>Routing modelli & API Keys</div>
                    </div>
                  </div>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ffb86c' }} />
                </button>

                {/* Item 5: Pulisci Memoria & Task */}
                <button
                  onClick={() => {
                    openCleanupModal();
                    setDockMinimized(true);
                  }}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 12px', borderRadius: '10px',
                    background: 'rgba(0, 242, 254, 0.08)',
                    border: '1px solid rgba(0, 242, 254, 0.25)',
                    color: '#00f2fe', cursor: 'pointer', transition: 'all 0.18s ease', textAlign: 'left'
                  }}
                  title="Pulisci memoria, resetta task, snapshot o cronologia senza chiudere Sigma Studio"
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(0, 242, 254, 0.15)', border: '1px solid rgba(0, 242, 254, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Trash2 size={16} color="#00f2fe" />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700 }}>Pulisci & Ottimizza</div>
                      <div style={{ fontSize: '0.62rem', color: '#8b8fa3' }}>RAM, task, chat e backup con pesi</div>
                    </div>
                  </div>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00f2fe' }} />
                </button>

                {/* Item 6: Musica & Focus Lounge Quick Widget */}
                {isAudioInstalled && (
                  <div style={{ marginTop: '2px' }}>
                    <MusicFloatingWidget onOpenTab={(tabObj, tabId) => {
                      openTab(tabObj, tabId);
                      setDockMinimized(true);
                    }} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STATIONARY & DRAGGABLE FAB TRIGGER BUTTON */}
          <button
            onMouseDown={handleDockMouseDown}
            onClick={(e) => {
              if (hasMovedRef.current) {
                e.stopPropagation();
                return;
              }
              setDockMinimized(!dockMinimized);
            }}
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              background: dockMinimized 
                ? 'linear-gradient(135deg, #00f2fe 0%, #0072ff 100%)' 
                : 'linear-gradient(135deg, rgba(255, 85, 85, 0.9), rgba(220, 38, 38, 0.9))',
              border: 'none',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: dockDragging ? 'grabbing' : 'grab',
              boxShadow: dockMinimized 
                ? '0 6px 24px rgba(0, 242, 254, 0.45), 0 0 0 2px rgba(0, 242, 254, 0.3)' 
                : '0 6px 24px rgba(255, 85, 85, 0.45), 0 0 0 2px rgba(255, 85, 85, 0.3)',
              transition: dockDragging ? 'none' : 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
              transform: dockMinimized ? 'scale(1)' : 'scale(1.05)',
              userSelect: 'none'
            }}
            title={dockMinimized ? 'Trascina o premi per aprire il Menu' : 'Chiudi Menu'}
          >
            {dockMinimized ? <Sparkles size={22} /> : <X size={22} />}
          </button>

          {dockMinimized && (
            <div 
              onMouseDown={handleDockMouseDown}
              onClick={(e) => {
                if (hasMovedRef.current) {
                  e.stopPropagation();
                  return;
                }
                setDockMinimized(false);
              }}
              style={{
                background: 'rgba(14, 16, 26, 0.9)',
                border: '1px solid rgba(0, 242, 254, 0.3)',
                padding: '6px 12px',
                borderRadius: '20px',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: '#00f2fe',
                backdropFilter: 'blur(10px)',
                cursor: dockDragging ? 'grabbing' : 'grab',
                boxShadow: '0 4px 14px rgba(0, 0, 0, 0.3)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                userSelect: 'none'
              }}
            >
              <GripVertical size={14} color="#00f2fe" />
              <span>Strumenti AI</span>
              {tasks?.length > 0 && (
                <span style={{ fontSize: '0.62rem', background: '#00f2fe', color: '#000', padding: '1px 6px', borderRadius: '10px', fontWeight: 800 }}>
                  {tasks.length}
                </span>
              )}
            </div>
          )}
        </div>
      </div>





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

      {/* HARDWARE MINI FLOATING PANEL */}
      {hardwarePanelOpen && isHardwareInstalled && LazyHardwareFloating && (
        <React.Suspense fallback={null}>
          <LazyHardwareFloating
            onClose={() => setHardwarePanelOpen(false)}
            onOpenTab={(tabObj, tabId) => {
              openTab(tabObj, tabId);
              setHardwarePanelOpen(false);
            }}
            addToast={addToast}
          />
        </React.Suspense>
      )}


      {/* AI CONFIG MODAL */}
      {aiConfigOpen && (
        <AIConfig
          isOpen={aiConfigOpen}
          onClose={() => setAiConfigOpen(false)}
          addToast={addToast}
        />
      )}

      {/* SYSTEM CLEANUP MODAL */}
      <SystemCleanupModal
        isOpen={isCleanupModalOpen}
        onClose={closeCleanupModal}
      />

      <ToastNotification toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <MusicProvider>
        <AppContent />
      </MusicProvider>
    </AppProvider>
  );
}