import React, { useState, useEffect } from 'react';
import {
  Home, FileText, Activity, PieChart, Layers, ChevronRight, ChevronDown, MessageSquare, X,
  FlaskConical, Brain, Zap, User, Server, Wrench, Palette, Blocks, Sun, Clapperboard,
  Moon, Store, Package, Sliders, Key, Sparkles, FolderGit2, Compass,
  Cpu, Box, Radio, Music, Mic, Terminal, Globe, Mail, Send, DownloadCloud, Settings, Trash2,
  Share2, Plus, Search, HardDrive, Copy, UserCheck, Award, CircuitBoard, MonitorPlay
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useModuleState } from '../hooks/useModuleState';
import { useCapabilities } from '../hooks/useCapabilities';
import { workspaceEntries, multimediaEntries, settingsEntries, coreNavigation, navigateStudio } from '../services/studioNavigation';
import { WORK_DOMAINS, workDomainFor } from '../utils/workDomains';
import WorkspaceIcon from './common/WorkspaceIcon';
import '../styles/03-modules/home-navigation.css';

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
  groupOnly = false,
  onToggleExpand = null
}) => {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const computedBadgeColor = isLight ? '#2e2820' : (badgeColor || '#3fb950');
  const computedBadgeSecondaryColor = isLight ? '#2e2820' : (badgeSecondaryColor || '#d29922');

  return (
    <div className={`sidebar-item ${isKernel ? 'kernel-item' : ''} ${active ? 'active' : ''}`} onClick={onClick} title={label}
      role="button" tabIndex={0} aria-label={label} aria-current={active ? 'page' : undefined}
      aria-expanded={expandable ? expanded : undefined} data-sidebar-group-only={groupOnly || undefined}
      onKeyDown={event => { if (event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) { event.preventDefault(); onClick?.(); } }}>
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
          role="button" tabIndex={0} aria-label={`Sezioni ${label}`} aria-expanded={expanded}
          onKeyDown={event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); event.stopPropagation(); onToggleExpand?.(); } }}
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
        >
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </span>
      )}
    </div>
  );
};

export default function Sidebar({
  modules = [],
  manifestiCount = 0,
  activeTabId,
  setActiveTabId,
  openTab,
  goHome,
  tasks = [],
  topicsCount = 0
}) {
  const {
    theme,
    toggleTheme,
    clearSystemMemory,
    openCleanupModal,
    mobileSidebarOpen,
    setMobileSidebarOpen, sidebarOpen, isMobileLayout, closeSidebar
  } = useApp();
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

  const [chatExpanded, setChatExpanded] = useState(false);
  const [modelsExpanded, setModelsExpanded] = useState(false);
  const [multimediaExpanded, setMultimediaExpanded] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [activeModelTab, setActiveModelTab] = useState(() => {
    try {
      const area = sessionStorage.getItem('sigma_model_workspace_section');
      return ['benchmark', 'training'].includes(area) ? area : 'inventory';
    } catch {
      return 'inventory';
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
      return localStorage.getItem('sigma_marketplace_active_subtab') || 'capabilities';
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
      if (e?.detail) setActiveModelTab('inventory');
    };
    const handleModelAreaChange = event => setActiveModelTab(event.detail === 'models' ? 'inventory' : event.detail);
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
    window.addEventListener('sigma-model-workspace-section', handleModelAreaChange);
    window.addEventListener('sigma-providers-tab-changed', handleProvidersTabChange);
    window.addEventListener('sigma-marketplace-tab-changed', handleSkillsTabChange);
    window.addEventListener('sigma-manifesti-tab-changed', handleManifestiTabChange);
    return () => {
      window.removeEventListener('sigma-chat-sessions-updated', handleSessionsUpdate);
      window.removeEventListener('sigma-model-hub-tab-changed', handleModelTabChange);
      window.removeEventListener('sigma-model-workspace-section', handleModelAreaChange);
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
    navigateStudio({ tabType: 'model_hub', name: 'Modelli' }, openTab, tabId);
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectProvidersTab = (tabId) => {
    setActiveProvidersTab(tabId);
    try {
      localStorage.setItem('sigma_providers_active_subtab', tabId);
    } catch { }
    openTab({ name: 'Providers' }, 'ai_config');
    window.dispatchEvent(new CustomEvent('sigma-providers-set-tab', { detail: tabId }));
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectSkillsTab = (tabId) => {
    setActiveSkillsTab(tabId);
    navigateStudio({ tabType: 'marketplace', name: 'Skills' }, openTab, tabId);
    if (setMobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const handleSelectManifestiTab = (tabId) => {
    setActiveManifestiTab(tabId);
    try {
      localStorage.setItem('sigma_manifesti_active_subtab', tabId);
    } catch { }
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
        .catch(() => { });
    };
    fetchSkills();

    window.addEventListener('sigma_skills_updated', fetchSkills);
    window.addEventListener('sigma_modules_updated', fetchSkills);
    return () => {
      window.removeEventListener('sigma_skills_updated', fetchSkills);
      window.removeEventListener('sigma_modules_updated', fetchSkills);
    };
  }, []);

  // Collapsible sub-sections inside the Skills Catalog (chiuse di default per mantenere la visualizzazione pulita)
  const [collapsedSections, setCollapsedSections] = useState({
    multimodal: true,
    studio: true,
    infra: true,
    comms: true,
  });

  const toggleSubtopic = (key) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !(prev[key] ?? true) }));
  };

  const { moduleCatalog } = useModuleState();
  const { skills: capabilitySkills } = useCapabilities();
  const sidebarWorkspaces = workspaceEntries(moduleCatalog, capabilitySkills)
    .filter(entry => !['model_hub', 'creative_studio', 'video_studio', 'voice_studio', 'music', 'developer_studio'].includes(entry.tabType));
  const mediaEntries = multimediaEntries(moduleCatalog, capabilitySkills);
  const modelSections = coreNavigation(moduleCatalog, capabilitySkills).find(e => e.tabType === 'model_hub')?.children || [];

  useEffect(() => {
    if (!mobileSidebarOpen || !isMobileLayout) return;
    const previous = document.activeElement;
    document.querySelector('[data-sidebar-close]')?.focus();
    return () => previous?.focus();
  }, [mobileSidebarOpen, isMobileLayout]);

  return (
    <aside id="studio-sidebar" className={`sidebar ${mobileSidebarOpen ? 'mobile-open' : ''}`}
      aria-label="Navigazione Sigma Studio" aria-hidden={!sidebarOpen} inert={!sidebarOpen}
      role={isMobileLayout ? 'dialog' : undefined} aria-modal={isMobileLayout && sidebarOpen ? true : undefined}
      onClick={event => { if (event.target.closest('.sidebar-item') && !event.target.closest('.sidebar-expand-arrow, [data-sidebar-group-only]')) setMobileSidebarOpen(false); }}
      onKeyDown={event => {
        if (!isMobileLayout || !mobileSidebarOpen || event.key !== 'Tab') return;
        const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]), [role="button"], input, select, a[href]')].filter(node => node.getClientRects().length);
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
      <button type="button" className="studio-sidebar-close" data-sidebar-close onClick={closeSidebar} aria-label="Chiudi pannello di navigazione"><X size={17} /></button>
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
            icon={DownloadCloud}
            label="Modelli"
            isKernel={true}
            badge="LOCAL"
            badgeColor="rgba(255,184,108,0.2)"
            active={activeTabId != null && activeTabId.startsWith('model_hub')}
            onClick={() => {
              handleSelectModelTab('inventory');
              setModelsExpanded(true);
            }}
            expandable={true}
            expanded={modelsExpanded}
            onToggleExpand={() => setModelsExpanded(prev => !prev)}
          />

          {modelsExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'inventory', label: 'Modelli', icon: HardDrive },
                { id: 'benchmark', label: 'Benchmark', icon: Award },
                { id: 'training', label: 'Training', icon: Brain },
              ].filter(sub => modelSections.some(section => section.id === sub.id)).map(sub => {
                const isSelected = activeTabId != null && activeTabId.startsWith('model_hub') && activeModelTab === sub.id;
                const SubIcon = sub.icon;
                return (
                  <button type="button"
                    key={sub.id}
                    className={`sidebar-subitem ${isSelected ? 'active' : ''}`}
                    onClick={() => handleSelectModelTab(sub.id)}
                  >
                    <SubIcon size={12} style={{ flexShrink: 0 }} />
                    <span className="sidebar-subitem-label">{sub.label}</span>
                  </button>
                );
              })}
            </div>
          )}

          <SidebarItem icon={Clapperboard} label="Multimedia" isKernel={true}
            active={activeTabId?.startsWith('multimedia') || ['creative_studio', 'video_studio', 'voice_studio', 'music'].some(type => activeTabId?.startsWith(type))}
            onClick={() => { handleNavClick(() => openTab({ name: 'Multimedia' }, 'multimedia')); setMultimediaExpanded(true); }}
            expandable expanded={multimediaExpanded} onToggleExpand={() => setMultimediaExpanded(value => !value)} />
          {multimediaExpanded && <div className="sidebar-subnav">{mediaEntries.map(entry =>
            <button type="button" key={entry.id} className="sidebar-subitem studio-sidebar-child"
              onClick={() => handleNavClick(() => navigateStudio(entry, openTab))}><WorkspaceIcon name={entry.icon} size={13} /><span>{entry.name}</span></button>)}</div>}

          <SidebarItem
            icon={Brain}
            label="Agenti"
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
                { id: 'installed', label: 'Agenti disponibili', icon: UserCheck },
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
            onClick={() => { handleSelectSkillsTab('capabilities'); setSkillsExpanded(true); }}
            expandable={true}
            expanded={skillsExpanded}
            onToggleExpand={() => setSkillsExpanded(prev => !prev)}
          />
          {skillsExpanded && (
            <div className="sidebar-subnav sidebar-models-subnav">
              {[
                { id: 'capabilities', label: 'Capacità e agenti', icon: Sparkles },
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
            icon={Terminal}
            label="Developer Sigma"
            isKernel={true}
            badge="ADMIN IDE"
            badgeColor="rgba(0,210,255,0.2)"
            active={activeTabId != null && (activeTabId.startsWith('developer_studio') || activeTabId.startsWith('developer_lab'))}
            onClick={() => handleNavClick(() => openTab({ name: 'Developer Sigma' }, 'developer_studio'))}
          />

          <SidebarItem
            icon={Settings}
            label="Impostazioni"
            groupOnly
            isKernel={true}
            badge="CONFIG"
            badgeColor="rgba(188,140,255,0.15)"
            active={['account', 'settings', 'mcp_hub', 'theme', 'palette'].some(type => activeTabId?.startsWith(type))}
            onClick={() => setSettingsExpanded(value => !value)}
            expandable expanded={settingsExpanded} onToggleExpand={() => setSettingsExpanded(value => !value)}
          />
          {settingsExpanded && <div className="sidebar-subnav">{settingsEntries(capabilitySkills).map(entry =>
            <button type="button" className="sidebar-subitem studio-sidebar-child" key={entry.id}
              onClick={() => handleNavClick(() => navigateStudio(entry, openTab))}><WorkspaceIcon name={entry.icon} size={13} /><span>{entry.name}</span></button>)}</div>}
        </nav>

        {/* ================================================================= */}
        {/* 2. SEZIONE MODULARE: CATALOGO SKILLS (SUDDIVISO PER SOTTOARGOMENTI) */}
        {/* ================================================================= */}
        <nav className="nav-section studio-sidebar-capabilities" aria-label="Laboratori disponibili">
          <div className="section-title">SKILLS E LABORATORI · {sidebarWorkspaces.length}</div>
          {WORK_DOMAINS.map(domain => {
            const entries = sidebarWorkspaces.filter(e => workDomainFor(e).id === domain.id);
            if (!entries.length) return null;
            const expanded = collapsedSections[domain.id] === false;
            return <section key={domain.id}>
              <button type="button" className="sidebar-group-button" aria-expanded={expanded}
                onClick={() => toggleSubtopic(domain.id)}>{domain.name}{expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button>
              {expanded && entries.map(entry => <div key={entry.id}>
                <SidebarItem icon={({ size }) => <WorkspaceIcon name={entry.icon} size={size} />}
                  label={entry.name} active={activeTabId?.startsWith(entry.tabType)}
                  onClick={() => handleNavClick(() => navigateStudio(entry, openTab))} />
                {!!entry.children?.length && <div className="sidebar-subnav">{entry.children.map(child =>
                  <button type="button" className="sidebar-subitem studio-sidebar-child" key={child.id}
                    onClick={() => handleNavClick(() => navigateStudio(entry, openTab, child.id))}>{child.name}</button>)}</div>}
              </div>)}
            </section>;
          })}

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
