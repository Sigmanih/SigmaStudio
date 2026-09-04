import React, { useState, useEffect, useMemo } from 'react';
import { 
  Home, FileText, Activity, PieChart, Layers, ChevronRight, ChevronDown, MessageSquare, 
  FlaskConical, Brain, Zap, User, Server, Wrench, Palette, Blocks, Sun, 
  Moon, Store, Package, Sliders, Key, Sparkles, FolderGit2, Compass,
  Cpu, Box, Radio, Music, Mic, Terminal, Globe, Mail, Send, DownloadCloud, Settings, Trash2,
  Share2, Plus, Search, HardDrive, Copy, UserCheck
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';

export const SidebarItem = ({ 
  icon: Icon, 
  label, 
  active, 
  onClick, 
  badge, 
  badgeColor, 
  badgeSecondary, 
  badgeSecondaryColor,
  isKernel = false,
  expandable = false,
  expanded = false,
  onToggleExpand = null
}) => {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const computedBadgeColor = isLight ? '#2e2820' : (badgeColor || '#3fb950');
  const computedBadgeSecondaryColor = isLight ? '#2e2820' : (badgeSecondaryColor || '#d29922');

  return (
    <div className={`sidebar-item ${isKernel ? 'kernel-item' : ''} ${active ? 'active' : ''}`} onClick={onClick} title={label}>
      <Icon size={15} style={{ flexShrink: 0 }} />
      <span style={{ 
        flex: 1, 
        whiteSpace: 'nowrap', 
        fontSize: '0.76rem',
        fontWeight: isKernel ? 700 : 600,
        letterSpacing: '-0.1px',
        lineHeight: 1.2
      }}>
        {label}
      </span>
      {isKernel && (
        <span 
          style={{ 
            width: '5px', 
            height: '5px', 
            borderRadius: '50%', 
            background: isLight ? '#d97706' : '#eab308',
            boxShadow: isLight ? '0 0 6px rgba(217, 119, 6, 0.6)' : '0 0 6px rgba(234, 179, 8, 0.8)',
            flexShrink: 0,
            marginRight: (badge !== undefined || badgeSecondary !== undefined) ? '4px' : '0px'
          }}
          title="Funzione Kernel Nativa"
        />
      )}
      {(badge !== undefined || badgeSecondary !== undefined) && (
        <span className="sidebar-badges" style={{ display: 'flex', alignItems: 'center', gap: '3px', flexShrink: 0 }}>
          {badgeSecondary !== undefined && (
            <span className="badge" style={{ 
              background: badgeSecondaryColor || 'rgba(210,153,34,0.15)', 
              color: computedBadgeSecondaryColor,
              fontSize: '0.56rem',
              padding: '1px 5px',
              borderRadius: '6px',
              fontWeight: 700,
              lineHeight: 1.2
            }}>
              {badgeSecondary}
            </span>
          )}
          {badge !== undefined && (
            <span className="badge" style={{ 
              background: badgeColor || 'rgba(63,185,80,0.15)', 
              color: computedBadgeColor,
              fontSize: '0.56rem',
              padding: '1px 5px',
              borderRadius: '6px',
              fontWeight: 700,
              lineHeight: 1.2
            }}>
              {badge}
            </span>
          )}
        </span>
      )}
      {expandable && (
        <span
          onClick={(e) => {
            e.stopPropagation();
            if (onToggleExpand) onToggleExpand();
          }}
          className="sidebar-expand-arrow"
          style={{
            marginLeft: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '18px',
            height: '18px',
            borderRadius: '4px',
            cursor: 'pointer',
            opacity: 0.7
          }}
          title={expanded ? 'Comprimi sotto-voci' : 'Espandi sotto-voci'}
        >
          <ChevronDown size={12} style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s ease' }} />
        </span>
      )}
    </div>
  );
};

export default function Sidebar({ 
  modules = [], 
  manifestiCount = 0,
  activeTabId, 
  leftVisible, 
  setLeftVisible, 
  setActiveTabId, 
  openTab,
  goHome,
  tasks = [],
  topicsCount = 0
}) {
  const { theme, toggleTheme, clearSystemMemory, openCleanupModal, mobileSidebarOpen, setMobileSidebarOpen } = useApp();
  const isLight = theme === 'light' || theme === 'cream';

  const handleNavClick = (fn) => {
    if (typeof fn === 'function') fn();
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const [chatCount, setChatCount] = useState(0);
  const [chatSessions, setChatSessions] = useState(() => {
    try {
      const raw = localStorage.getItem('sigma_chat_sessions');
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [activeSessionId, setActiveSessionId] = useState(() => {
    try {
      return localStorage.getItem('sigma_active_chat_session_id') || null;
    } catch {
      return null;
    }
  });

  const [chatExpanded, setChatExpanded] = useState(true);
  const [modelsExpanded, setModelsExpanded] = useState(true);
  const [activeModelTab, setActiveModelTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_model_hub_active_subtab') || 'browse';
    } catch {
      return 'browse';
    }
  });

  const [providersExpanded, setProvidersExpanded] = useState(false);
  const [activeProvidersTab, setActiveProvidersTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_providers_active_subtab') || 'engine_server';
    } catch {
      return 'engine_server';
    }
  });

  const [skillsExpanded, setSkillsExpanded] = useState(false);
  const [activeSkillsTab, setActiveSkillsTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_marketplace_active_subtab') || 'installed';
    } catch {
      return 'installed';
    }
  });

  const [manifestiExpanded, setManifestiExpanded] = useState(false);
  const [activeManifestiTab, setActiveManifestiTab] = useState(() => {
    try {
      return localStorage.getItem('sigma_manifesti_active_subtab') || 'installed';
    } catch {
      return 'installed';
    }
  });

  useEffect(() => {
    const handleSessionsUpdate = (e) => {
      if (e?.detail) {
        if (Array.isArray(e.detail.sessions)) {
          setChatSessions(e.detail.sessions);
          setChatCount(e.detail.sessions.length);
        }
        if (e.detail.activeSessionId) setActiveSessionId(e.detail.activeSessionId);
      }
    };
    const handleModelTabChange = (e) => {
      if (e?.detail) setActiveModelTab(e.detail);
    };
    const handleProvidersTabChange = (e) => {
      if (e?.detail) setActiveProvidersTab(e.detail);
    };
    const handleSkillsTabChange = (e) => {
      if (e?.detail) setActiveSkillsTab(e.detail);
    };
    const handleManifestiTabChange = (e) => {
      if (e?.detail) setActiveManifestiTab(e.detail);
    };

    window.addEventListener('sigma-chat-sessions-updated', handleSessionsUpdate);
    window.addEventListener('sigma-model-hub-tab-changed', handleModelTabChange);
    window.addEventListener('sigma-providers-tab-changed', handleProvidersTabChange);
    window.addEventListener('sigma-marketplace-tab-changed', handleSkillsTabChange);
    window.addEventListener('sigma-manifesti-tab-changed', handleManifestiTabChange);
    return () => {
      window.removeEventListener('sigma-chat-sessions-updated', handleSessionsUpdate);
      window.removeEventListener('sigma-model-hub-tab-changed', handleModelTabChange);
      window.removeEventListener('sigma-providers-tab-changed', handleProvidersTabChange);
      window.removeEventListener('sigma-marketplace-tab-changed', handleSkillsTabChange);
      window.removeEventListener('sigma-manifesti-tab-changed', handleManifestiTabChange);
    };
  }, []);

  useEffect(() => {
    if (activeTabId != null) {
      if (activeTabId.startsWith('chat')) {
        setChatExpanded(true);
      } else if (activeTabId.startsWith('model_hub')) {
        setModelsExpanded(true);
      } else if (activeTabId.startsWith('ai_config') || activeTabId.startsWith('config')) {
        setProvidersExpanded(true);
      } else if (activeTabId.startsWith('marketplace')) {
        setSkillsExpanded(true);
      } else if (activeTabId.startsWith('whitepaper') || activeTabId.startsWith('whitepapers_lib')) {
        setManifestiExpanded(true);
      }
    }
  }, [activeTabId]);

  const handleSelectChatSession = (sessionId) => {
    setActiveSessionId(sessionId);
    openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
    window.dispatchEvent(new CustomEvent('sigma-chat-switch-session', { detail: sessionId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleNewChatSession = (e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
    window.dispatchEvent(new CustomEvent('sigma-chat-new-session'));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleDeleteChatSession = (e, sessionId) => {
    if (e && e.stopPropagation) e.stopPropagation();
    window.dispatchEvent(new CustomEvent('sigma-chat-delete-session', { detail: sessionId }));
    setChatSessions(prev => prev.filter(s => s.id !== sessionId));
  };

  const handleDuplicateChatSession = (e, sessionId) => {
    if (e && e.stopPropagation) e.stopPropagation();
    window.dispatchEvent(new CustomEvent('sigma-chat-duplicate-session', { detail: sessionId }));
  };

  const handleSelectModelTab = (tabId) => {
    setActiveModelTab(tabId);
    try {
      localStorage.setItem('sigma_model_hub_active_subtab', tabId);
    } catch {}
    openTab({ name: 'Modelli' }, 'model_hub');
    window.dispatchEvent(new CustomEvent('sigma-model-hub-set-tab', { detail: tabId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectProvidersTab = (tabId) => {
    setActiveProvidersTab(tabId);
    try {
      localStorage.setItem('sigma_providers_active_subtab', tabId);
    } catch {}
    openTab({ name: 'Providers' }, 'ai_config');
    window.dispatchEvent(new CustomEvent('sigma-providers-set-tab', { detail: tabId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectSkillsTab = (tabId) => {
    setActiveSkillsTab(tabId);
    try {
      localStorage.setItem('sigma_marketplace_active_subtab', tabId);
    } catch {}
    openTab({ name: 'Skills' }, 'marketplace');
    window.dispatchEvent(new CustomEvent('sigma-marketplace-set-tab', { detail: tabId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectManifestiTab = (tabId) => {
    setActiveManifestiTab(tabId);
    try {
      localStorage.setItem('sigma_manifesti_active_subtab', tabId);
    } catch {}
    openTab({ name: 'Ruoli AI' }, 'whitepapers_lib');
    window.dispatchEvent(new CustomEvent('sigma-manifesti-set-tab', { detail: tabId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };
  const [hiddenTabs, setHiddenTabs] = useState(() => new Set());
  
  useEffect(() => {
    const fetchSkills = () => {
      fetch('/api/skills')
        .then(r => r.json())
        .then(d => {
          if (!d.success) return;
          setHiddenTabs(new Set(d.skills.filter(s => !s.enabled && s.tab_type).map(s => s.tab_type)));
        })
        .catch(() => {});
    };
    fetchSkills();

    window.addEventListener('sigma_skills_updated', fetchSkills);
    window.addEventListener('sigma_modules_updated', fetchSkills);
    return () => {
      window.removeEventListener('sigma_skills_updated', fetchSkills);
      window.removeEventListener('sigma_modules_updated', fetchSkills);
    };
  }, []);

  const [researchCount, setResearchCount] = useState(0);
  const [trainingCompleted, setTrainingCompleted] = useState(0);
  const [localTopicsCount, setLocalTopicsCount] = useState(0);
  const [assetCount, setAssetCount] = useState(0);

  // Collapsible sub-sections inside the Skills Catalog
  const [collapsedSections, setCollapsedSections] = useState({
    multimodal: false,
    studio: false,
    infra: false,
    comms: false,
  });

  const toggleSubtopic = (key) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const { modulesState } = useModuleState();
  const isAudioInstalled = modulesState.audio_studio === true;
  const isDomoticaInstalled = modulesState.sigma_domotica === true;
  const isCreativeInstalled = modulesState.sigma_creative_lab === true;
  const isHardwareInstalled = modulesState.sigma_hardware_lab === true;
  const isModelHubInstalled = modulesState.sigma_model_hub === true;
  const isResearchInstalled = modulesState.sigma_research_lab === true;
  const isTrainingInstalled = modulesState.sigma_training_lab === true;
  const isRoadmapInstalled = modulesState.sigma_roadmap === true;
  const isKnowledgeInstalled = modulesState.sigma_knowledge === true;
  const isVoiceInstalled = modulesState.sigma_voice_studio === true;
  const isDevInstalled = modulesState.sigma_developer_lab === true;
  const isNetworkInstalled = modulesState.sigma_network_lab === true;
  // NOTA: queste bandiere sono scritte a mano una per modulo. Il backend
  // scopre i moduli dai manifest e useModuleState ne riporta lo stato, ma
  // la sidebar li elenca ancora qui: un modulo installato senza la sua riga
  // resta invisibile pur funzionando in tutto il resto.
  const isSigmaNetworkInstalled = modulesState.sigma_network === true;
  const isEmailInstalled = modulesState.sigma_email_client === true;
  const isMessagingInstalled = modulesState.sigma_messaging_hub === true;

  // Verifica se ci sono skill installate per ciascun sottoargomento
  const hasMultimodal = isCreativeInstalled || isVoiceInstalled || isDomoticaInstalled || isAudioInstalled;
  const hasStudio = isTrainingInstalled || isResearchInstalled || isRoadmapInstalled || isKnowledgeInstalled;
  const hasInfra = isDevInstalled || isHardwareInstalled || isNetworkInstalled || isSigmaNetworkInstalled;
  const hasComms = isEmailInstalled || isMessagingInstalled;

  // Poll for counts (chat sessions, manifesti, topics, etc.)
  useEffect(() => {
    const updateCounts = () => {
      try {
        const chatSessions = localStorage.getItem('sigma_chat_sessions');
        if (chatSessions) {
          const parsed = JSON.parse(chatSessions);
          if (Array.isArray(parsed)) setChatCount(parsed.length);
        } else {
          setChatCount(0);
        }
      } catch (e) {
        setChatCount(0);
      }

      if (isResearchInstalled) {
        fetch('/api/research/list')
          .then(res => res.json())
          .then(data => {
            if (data.success && Array.isArray(data.sessions)) {
              setResearchCount(data.sessions.length);
            }
          })
          .catch(() => {});
      }

      if (isTrainingInstalled) {
        fetch('/api/training/jobs')
          .then(res => res.json())
          .then(data => {
            if (data.success && Array.isArray(data.jobs)) {
              setTrainingCompleted(data.jobs.filter(j => j.status === 'completed' || j.status === 'running').length);
            }
          })
          .catch(() => {});
      }

      if (isKnowledgeInstalled) {
        fetch('/api/topics')
          .then(res => res.json())
          .then(data => {
            if (data.topics && Array.isArray(data.topics)) {
              setLocalTopicsCount(data.topics.length);
            }
          })
          .catch(() => {
            try {
              const k = localStorage.getItem('sigma_knowledge_topics');
              if (k) {
                const parsed = JSON.parse(k);
                if (Array.isArray(parsed)) setLocalTopicsCount(parsed.length);
              }
            } catch (e) {}
          });
      }

      if (isCreativeInstalled) {
        fetch('/api/creative/stats')
          .then(res => res.json())
          .then(data => {
            if (data.assets) {
              setAssetCount(data.assets);
            }
          })
          .catch(() => {});
      }
    };

    updateCounts();
    const interval = setInterval(updateCounts, 5000);
    return () => clearInterval(interval);
  }, [isResearchInstalled, isTrainingInstalled, isCreativeInstalled, isKnowledgeInstalled]);

  const taskInCorso = tasks.filter(t => t.status === 'in_corso' || !t.status).length;
  const taskDone = tasks.filter(t => t.status === 'done').length;
  const taskTotal = tasks.length;

  // Custom installed marketplace modules (excluding base standard modules)
  const builtinModuleIds = new Set(['creative_studio', 'research_lab', 'training_lab', 'hardware_lab', 'mcp_hub', 'config', 'account', 'marketplace']);
  const dynamicInstalledModules = modules.filter(m => m.installed && !builtinModuleIds.has(m.id));

  // Count total active modular skills
  const totalActiveSkills = [
    isCreativeInstalled, isVoiceInstalled, isDomoticaInstalled, isAudioInstalled,
    isTrainingInstalled, isResearchInstalled, isRoadmapInstalled, isKnowledgeInstalled,
    isDevInstalled, isHardwareInstalled, isNetworkInstalled, isSigmaNetworkInstalled,
    isEmailInstalled, isMessagingInstalled,
    ...dynamicInstalledModules.map(() => true)
  ].filter(Boolean).length;

  return (
    <aside className={`sidebar ${mobileSidebarOpen ? 'mobile-open' : ''}`}>
      <button className="collapse-btn left" onClick={() => setLeftVisible(!leftVisible)}>
         {leftVisible ? <ChevronRight size={14} style={{transform: 'rotate(180deg)'}} /> : <ChevronRight size={14} />}
      </button>
      <div className="sidebar-content">
        
        {/* SIDEBAR HEADER & LOGO */}
        <div className="sidebar-header">
          <div 
            className="logo" 
            onClick={() => handleNavClick(goHome)}
            title="Torna alla Bacheca"
            style={{ 
              marginBottom: '16px', 
              cursor: 'pointer', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '12px',
              userSelect: 'none'
            }}
          >
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              overflow: 'hidden',
              border: isLight ? '2px solid #ea580c' : '2px solid #00d2ff',
              boxShadow: isLight ? '0 0 12px rgba(234, 88, 12, 0.3)' : '0 0 14px rgba(0, 210, 255, 0.45)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#0a0d14',
              flexShrink: 0,
              transition: 'transform 0.2s ease, box-shadow 0.2s ease'
            }}>
              <img 
                src="/images/sigma_logo_harmonic_flow.jpg" 
                alt="Sigma Logo" 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={(e) => { e.target.src = '/sigma_logo.jpg'; }}
              />
            </div>
            <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800 }}>
              Sigma <span style={{ color: isLight ? '#ea580c' : '#00d2ff' }}>Studio</span>
            </h2>
          </div>
        </div>

        {/* ================================================================= */}
        {/* 1. SEZIONE FONDAMENTALE: FUNZIONI KERNEL                          */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '18px' }}>
          <SidebarItem 
            icon={Home} 
            label="Home" 
            isKernel={true}
            active={activeTabId === null}
            onClick={goHome}
          />

          <SidebarItem 
            icon={MessageSquare} 
            label="Chat" 
            isKernel={true}
            badge={chatCount > 0 ? chatCount : 0}
            badgeColor="rgba(234,179,8,0.18)"
            active={activeTabId != null && activeTabId.startsWith('chat')}
            onClick={() => {
              openTab({ name: 'Chat', path: 'chat-tab' }, 'chat');
              setChatExpanded(true);
            }} 
            expandable={true}
            expanded={chatExpanded}
            onToggleExpand={() => setChatExpanded(prev => !prev)}
          />

          {chatExpanded && (
            <div className="sidebar-subnav sidebar-chat-subnav">
              <button
                type="button"
                className="sidebar-new-chat-btn"
                onClick={handleNewChatSession}
                title="Avvia una nuova conversazione"
              >
                <Plus size={12} />
                <span>Nuova Conversazione</span>
              </button>

              <div className="sidebar-sessions-list">
                {chatSessions.length === 0 ? (
                  <div className="sidebar-subitem-empty">Nessuna sessione</div>
                ) : (
                  chatSessions.slice(0, 15).map(s => {
                    const isSelected = activeTabId != null && activeTabId.startsWith('chat') && activeSessionId === s.id;
                    return (
                      <div
                        key={s.id}
                        className={`sidebar-session-item ${isSelected ? 'active' : ''}`}
                        onClick={() => handleSelectChatSession(s.id)}
                        title={s.name}
                      >
                        <span className="sidebar-session-dot" />
                        <span className="sidebar-session-name">{s.name || 'Chat'}</span>
                        <div className="sidebar-session-actions" style={{ display: 'flex', alignItems: 'center', gap: '2px', flexShrink: 0 }}>
                          <button
                            type="button"
                            className="sidebar-session-duplicate-btn"
                            onClick={(e) => handleDuplicateChatSession(e, s.id)}
                            title="Duplica conversazione"
                          >
                            <Copy size={11} />
                          </button>
                          <button
                            type="button"
                            className="sidebar-session-delete-btn"
                            onClick={(e) => handleDeleteChatSession(e, s.id)}
                            title="Elimina conversazione"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          <SidebarItem 
            icon={DownloadCloud} 
            label="Modelli" 
            isKernel={true}
            badge="LOCAL"
            badgeColor="rgba(255,184,108,0.2)"
            active={activeTabId != null && activeTabId.startsWith('model_hub')}
            onClick={() => {
              openTab({ name: 'Modelli' }, 'model_hub');
              setModelsExpanded(true);
            }} 
            expandable={true}
            expanded={modelsExpanded}
            onToggleExpand={() => setModelsExpanded(prev => !prev)}
          />

          {modelsExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'browse', label: 'Esplora HF', icon: Search },
                { id: 'inventory', label: 'Modelli Locali', icon: HardDrive },
                { id: 'converter', label: 'Convertitore GGUF', icon: Zap },
                { id: 'settings', label: 'Impostazioni & Token', icon: Settings },
              ].map(sub => {
                const isSelected = activeTabId != null && activeTabId.startsWith('model_hub') && activeModelTab === sub.id;
                const SubIcon = sub.icon;
                return (
                  <div
                    key={sub.id}
                    className={`sidebar-subitem ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectModelTab(sub.id)}
                  >
                    <SubIcon size={12} style={{ flexShrink: 0 }} />
                    <span className="sidebar-subitem-label">{sub.label}</span>
                  </div>
                );
              })}
            </div>
          )}

          <SidebarItem 
            icon={Sliders} 
            label="Providers" 
            isKernel={true}
            badge="ROUTING"
            badgeColor="rgba(234,179,8,0.18)"
            active={activeTabId != null && (activeTabId.startsWith('ai_config') || activeTabId.startsWith('config'))}
            onClick={() => {
              openTab({ name: 'Providers' }, 'ai_config');
              setProvidersExpanded(true);
            }} 
            expandable={true}
            expanded={providersExpanded}
            onToggleExpand={() => setProvidersExpanded(prev => !prev)}
          />
          {providersExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'engine_server', label: 'Server Locale & Proxy', icon: Server },
                { id: 'external_providers', label: 'Provider Esterni', icon: Globe },
              ].map(sub => {
                const isSelected = activeTabId != null && (activeTabId.startsWith('ai_config') || activeTabId.startsWith('config')) && activeProvidersTab === sub.id;
                const SubIcon = sub.icon;
                return (
                  <div
                    key={sub.id}
                    className={`sidebar-subitem ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectProvidersTab(sub.id)}
                  >
                    <SubIcon size={12} style={{ flexShrink: 0 }} />
                    <span className="sidebar-subitem-label">{sub.label}</span>
                  </div>
                );
              })}
            </div>
          )}

          <SidebarItem 
            icon={Package} 
            label="Skills" 
            isKernel={true}
            badge="STORE"
            badgeColor="rgba(234,179,8,0.2)"
            active={activeTabId != null && activeTabId.startsWith('marketplace')}
            onClick={() => {
              openTab({ name: 'Skills' }, 'marketplace');
              setSkillsExpanded(true);
            }} 
            expandable={true}
            expanded={skillsExpanded}
            onToggleExpand={() => setSkillsExpanded(prev => !prev)}
          />
          {skillsExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'installed', label: 'Moduli Installati', icon: Cpu },
                { id: 'remote', label: 'Catalogo Moduli', icon: Sparkles },
              ].map(sub => {
                const isSelected = activeTabId != null && activeTabId.startsWith('marketplace') && activeSkillsTab === sub.id;
                const SubIcon = sub.icon;
                return (
                  <div
                    key={sub.id}
                    className={`sidebar-subitem ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectSkillsTab(sub.id)}
                  >
                    <SubIcon size={12} style={{ flexShrink: 0 }} />
                    <span className="sidebar-subitem-label">{sub.label}</span>
                  </div>
                );
              })}
            </div>
          )}

          <SidebarItem 
            icon={Brain} 
            label="Ruoli AI" 
            isKernel={true}
            badge={manifestiCount + modules.reduce((acc, m) => acc + (m.whitepapers?.length || 0), 0)}
            badgeColor="rgba(188,140,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('whitepaper') || activeTabId.startsWith('whitepapers_lib'))}
            onClick={() => {
              openTab({ name: 'Ruoli AI' }, 'whitepapers_lib');
              setManifestiExpanded(true);
            }} 
            expandable={true}
            expanded={manifestiExpanded}
            onToggleExpand={() => setManifestiExpanded(prev => !prev)}
          />
          {manifestiExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'installed', label: 'Ruoli Kernel', icon: UserCheck },
                { id: 'hub', label: 'Hub Community', icon: Globe },
              ].map(sub => {
                const isSelected = activeTabId != null && (activeTabId.startsWith('whitepaper') || activeTabId.startsWith('whitepapers_lib')) && activeManifestiTab === sub.id;
                const SubIcon = sub.icon;
                return (
                  <div
                    key={sub.id}
                    className={`sidebar-subitem ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectManifestiTab(sub.id)}
                  >
                    <SubIcon size={12} style={{ flexShrink: 0 }} />
                    <span className="sidebar-subitem-label">{sub.label}</span>
                  </div>
                );
              })}
            </div>
          )}

          {!hiddenTabs.has('mcp_hub') && (
            <SidebarItem 
              icon={Wrench} 
              label="MCP Tools" 
              isKernel={true}
              badge={6}
              badgeColor="rgba(63,185,80,0.15)"
              active={activeTabId != null && activeTabId.startsWith('mcp_hub')}
              onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')} 
            />
          )}

          <SidebarItem 
            icon={Settings} 
            label="Impostazioni" 
            isKernel={true}
            badge="CONFIG"
            badgeColor="rgba(188,140,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('account') || activeTabId.startsWith('settings'))}
            onClick={() => handleNavClick(() => openTab({ name: 'Impostazioni' }, 'account'))} 
          />

          <SidebarItem 
            icon={Palette} 
            label="Tema" 
            isKernel={true}
            badge="COLORI"
            badgeColor="rgba(0,210,255,0.18)"
            active={activeTabId != null && (activeTabId.startsWith('theme') || activeTabId.startsWith('palette'))}
            onClick={() => handleNavClick(() => openTab({ name: 'Tema' }, 'theme'))} 
          />
        </nav>

        {/* ================================================================= */}
        {/* 2. SEZIONE MODULARE: CATALOGO SKILLS (SUDDIVISO PER SOTTOARGOMENTI) */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '14px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🧩</span> CATALOGO SKILLS
            </span>
            <span style={{ 
              fontSize: '0.58rem', 
              fontWeight: 800, 
              padding: '1px 6px', 
              borderRadius: '6px', 
              background: isLight ? 'rgba(124, 91, 240, 0.12)' : 'rgba(188, 140, 255, 0.15)', 
              color: isLight ? '#6d28d9' : '#bc8cff' 
            }}>
              {totalActiveSkills} ATTIVE
            </span>
          </div>

          {/* SOTTOARGOMENTO 1: MULTIMODALE & CREATIVITÀ (Mostra solo se ha skill) */}
          {hasMultimodal && (
            <div style={{ marginBottom: '6px' }}>
              <div 
                onClick={() => toggleSubtopic('multimodal')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  fontSize: '0.64rem',
                  fontWeight: 800,
                  color: isLight ? '#6b5e4c' : 'rgba(255, 255, 255, 0.45)',
                  letterSpacing: '0.6px',
                  cursor: 'pointer',
                  borderRadius: '6px',
                  textTransform: 'uppercase',
                  userSelect: 'none',
                  transition: 'color 0.2s ease'
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span>🎨</span> MULTIMODALE & CREATIVITÀ
                </span>
                <ChevronDown size={11} style={{ transform: collapsedSections.multimodal ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
              </div>

              {!collapsedSections.multimodal && (
                <div style={{ paddingLeft: '4px', marginTop: '2px' }}>
                  {isCreativeInstalled && (
                    <SidebarItem
                      icon={Palette}
                      label="Creative"
                      badge={assetCount > 0 ? assetCount : 0}
                      badgeColor="rgba(255,80,100,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('creative_studio')}
                      onClick={() => openTab({ name: 'Creative' }, 'creative_studio')}
                    />
                  )}

                  {isVoiceInstalled && (
                    <SidebarItem
                      icon={Mic}
                      label="Voice Studio"
                      badge="TTS"
                      badgeColor="rgba(255,121,198,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('voice_studio')}
                      onClick={() => openTab({ name: 'Voice Studio' }, 'voice_studio')}
                    />
                  )}

                  {isDomoticaInstalled && (
                    <SidebarItem 
                      icon={Home} 
                      label="Domotica" 
                      badge="HA"
                      badgeColor="rgba(167,139,250,0.2)"
                      active={activeTabId != null && (activeTabId.startsWith('domotica') || activeTabId.startsWith('home_assistant'))}
                      onClick={() => openTab({ name: 'Domotica' }, 'domotica')} 
                    />
                  )}

                  {isAudioInstalled && (
                    <SidebarItem 
                      icon={Radio} 
                      label="Musica" 
                      badge="LOUNGE"
                      badgeColor="rgba(0,242,254,0.2)"
                      active={activeTabId != null && (activeTabId.startsWith('music') || activeTabId === 'audio_studio' || activeTabId === 'music_lounge')}
                      onClick={() => openTab({ name: 'Musica' }, 'music')} 
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* SOTTOARGOMENTO 2: STUDIO & INTELLIGENZA ARTIFICIALE (Mostra solo se ha skill) */}
          {hasStudio && (
            <div style={{ marginBottom: '6px' }}>
              <div 
                onClick={() => toggleSubtopic('studio')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  fontSize: '0.64rem',
                  fontWeight: 800,
                  color: isLight ? '#6b5e4c' : 'rgba(255, 255, 255, 0.45)',
                  letterSpacing: '0.6px',
                  cursor: 'pointer',
                  borderRadius: '6px',
                  textTransform: 'uppercase',
                  userSelect: 'none',
                  transition: 'color 0.2s ease'
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span>🧠</span> STUDIO, RICERCA & AI
                </span>
                <ChevronDown size={11} style={{ transform: collapsedSections.studio ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
              </div>

              {!collapsedSections.studio && (
                <div style={{ paddingLeft: '4px', marginTop: '2px' }}>
                  {isTrainingInstalled && (
                    <SidebarItem
                      icon={Brain}
                      label="Training"
                      badge={trainingCompleted > 0 ? trainingCompleted : 0}
                      badgeColor="rgba(0,210,255,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('training_lab')}
                      onClick={() => openTab({ name: 'Training' }, 'training_lab')}
                    />
                  )}

                  {isResearchInstalled && (
                    <SidebarItem 
                      icon={FlaskConical} 
                      label="Pipelines" 
                      badge={researchCount > 0 ? researchCount : 0}
                      badgeColor="rgba(188,140,255,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('research_lab')}
                      onClick={() => openTab({ name: 'Pipelines' }, 'research_lab')} 
                    />
                  )}

                  {isRoadmapInstalled && (
                    <SidebarItem 
                      icon={Activity} 
                      label="Pianificazione & Task" 
                      badge={taskInCorso > 0 ? taskInCorso : (taskTotal === 0 ? 0 : undefined)}
                      badgeColor="rgba(210,153,34,0.15)"
                      badgeSecondary={taskDone > 0 ? taskDone : undefined}
                      badgeSecondaryColor="rgba(63,185,80,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('roadmap')}
                      onClick={() => openTab({ name: 'Pianificazione & Task' }, 'roadmap')} 
                    />
                  )}

                  {isKnowledgeInstalled && (
                    <SidebarItem 
                      icon={PieChart} 
                      label="Argomenti" 
                      badge={localTopicsCount > 0 || topicsCount > 0 ? Math.max(localTopicsCount, topicsCount) : 0}
                      badgeColor="rgba(0,210,255,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('knowledge')}
                      onClick={() => openTab({ name: 'Argomenti' }, 'knowledge')} 
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* SOTTOARGOMENTO 3: INFRASTRUTTURA & RETE (Mostra solo se ha skill) */}
          {hasInfra && (
            <div style={{ marginBottom: '6px' }}>
              <div 
                onClick={() => toggleSubtopic('infra')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  fontSize: '0.64rem',
                  fontWeight: 800,
                  color: isLight ? '#6b5e4c' : 'rgba(255, 255, 255, 0.45)',
                  letterSpacing: '0.6px',
                  cursor: 'pointer',
                  borderRadius: '6px',
                  textTransform: 'uppercase',
                  userSelect: 'none',
                  transition: 'color 0.2s ease'
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span>⚡</span> INFRASTRUTTURA & RETE
                </span>
                <ChevronDown size={11} style={{ transform: collapsedSections.infra ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
              </div>

              {!collapsedSections.infra && (
                <div style={{ paddingLeft: '4px', marginTop: '2px' }}>
                  {isDevInstalled && (
                    <SidebarItem
                      icon={Terminal}
                      label="Developer Sigma"
                      badge="ADMIN IDE"
                      badgeColor="rgba(0,242,254,0.18)"
                      active={activeTabId != null && (activeTabId.startsWith('developer_studio') || activeTabId.startsWith('developer_lab'))}
                      onClick={() => openTab({ name: 'Developer Sigma' }, 'developer_studio')}
                    />
                  )}

                  {isHardwareInstalled && (
                    <SidebarItem 
                      icon={Zap} 
                      label="Monitor Hardware" 
                      badge="VRAM"
                      badgeColor="rgba(0,242,254,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('hardware_lab')}
                      onClick={() => openTab({ name: 'Monitor Hardware' }, 'hardware_lab')} 
                    />
                  )}

                  {isNetworkInstalled && (
                    <SidebarItem 
                      icon={Globe} 
                      label="AI Web Browser" 
                      badge="NET"
                      badgeColor="rgba(63,185,80,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('network_lab')}
                      onClick={() => openTab({ name: 'AI Web Browser' }, 'network_lab')} 
                    />
                  )}

                  {isSigmaNetworkInstalled && (
                    <SidebarItem
                      icon={Share2}
                      label="Sigma Network"
                      badge="P2P"
                      badgeColor="rgba(88,101,242,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('sigma_network')}
                      onClick={() => openTab({ name: 'Sigma Network' }, 'sigma_network')}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* SOTTOARGOMENTO 4: COMUNICAZIONE & SOCIAL (Mostra solo se ha skill) */}
          {hasComms && (
            <div style={{ marginBottom: '6px' }}>
              <div 
                onClick={() => toggleSubtopic('comms')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  fontSize: '0.64rem',
                  fontWeight: 800,
                  color: isLight ? '#6b5e4c' : 'rgba(255, 255, 255, 0.45)',
                  letterSpacing: '0.6px',
                  cursor: 'pointer',
                  borderRadius: '6px',
                  textTransform: 'uppercase',
                  userSelect: 'none',
                  transition: 'color 0.2s ease'
                }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span>📬</span> COMUNICAZIONE & SOCIAL
                </span>
                <ChevronDown size={11} style={{ transform: collapsedSections.comms ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
              </div>

              {!collapsedSections.comms && (
                <div style={{ paddingLeft: '4px', marginTop: '2px' }}>
                  {isEmailInstalled && (
                    <SidebarItem 
                      icon={Mail} 
                      label="Email Hub" 
                      badge="MAIL"
                      badgeColor="rgba(255,180,84,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('email_client')}
                      onClick={() => openTab({ name: '✉️ Email Hub' }, 'email_client')} 
                    />
                  )}

                  {isMessagingInstalled && (
                    <SidebarItem 
                      icon={Send} 
                      label="Messaging Hub" 
                      badge="BOT"
                      badgeColor="rgba(188,140,255,0.15)"
                      active={activeTabId != null && activeTabId.startsWith('messaging_hub')}
                      onClick={() => openTab({ name: '💬 Messaging Hub' }, 'messaging_hub')} 
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Dynamic Extra Installed Modules from Marketplace */}
          {dynamicInstalledModules.length > 0 && (
            <div style={{ marginTop: '6px', paddingLeft: '4px' }}>
              <div style={{ fontSize: '0.6rem', color: isLight ? '#7a7060' : 'rgba(255,255,255,0.4)', fontWeight: 800, letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: '4px', paddingLeft: '8px' }}>
                PLUGINS EXTRA
              </div>
              {dynamicInstalledModules.map(mod => (
                <SidebarItem
                  key={mod.id}
                  icon={Box}
                  label={mod.name || mod.id}
                  badge="PLUGIN"
                  badgeColor="rgba(188,140,255,0.15)"
                  active={activeTabId === mod.tabType || activeTabId === mod.id}
                  onClick={() => openTab({ name: mod.name || mod.id }, mod.tabType || mod.id)}
                />
              ))}
            </div>
          )}

          {/* Quick System Cleanup Action */}
          <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: isLight ? '1px solid #e0d8cc' : '1px solid rgba(255,255,255,0.06)' }}>
            <SidebarItem
              icon={Trash2}
              label="Pulisci & Ottimizza"
              badge="CLEAN"
              badgeColor="rgba(0, 242, 254, 0.2)"
              active={false}
              onClick={openCleanupModal}
            />
          </div>
        </nav>

      </div>
    </aside>
  );
}