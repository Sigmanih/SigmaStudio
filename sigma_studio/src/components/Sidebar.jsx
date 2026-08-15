import React, { useState, useEffect } from 'react';
import { 
  Home, FileText, Activity, PieChart, Layers, ChevronRight, MessageSquare, 
  FlaskConical, Brain, Zap, User, Server, Wrench, Palette, Blocks, Sun, 
  Moon, Store, Package, Sliders, Key, Sparkles, FolderGit2, Compass,
  Cpu, Box, Radio, Music, Mic, Terminal, Globe, Mail, Send, DownloadCloud
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
  badgeSecondaryColor 
}) => {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const computedBadgeColor = isLight ? '#2e2820' : (badgeColor || '#3fb950');
  const computedBadgeSecondaryColor = isLight ? '#2e2820' : (badgeSecondaryColor || '#d29922');

  return (
    <div className={`sidebar-item ${active ? 'active' : ''}`} onClick={onClick} title={label}>
      <Icon size={15} style={{ flexShrink: 0 }} />
      <span style={{ 
        flex: 1, 
        whiteSpace: 'nowrap', 
        fontSize: '0.76rem',
        fontWeight: 600,
        letterSpacing: '-0.1px',
        lineHeight: 1.2
      }}>
        {label}
      </span>
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
  const { theme, toggleTheme } = useApp();
  const isLight = theme === 'light';

  const [chatCount, setChatCount] = React.useState(0);
  const [hiddenTabs, setHiddenTabs] = React.useState(() => new Set());
  
  React.useEffect(() => {
    fetch('/api/skills')
      .then(r => r.json())
      .then(d => {
        if (!d.success) return;
        setHiddenTabs(new Set(d.skills.filter(s => !s.enabled && s.tab_type).map(s => s.tab_type)));
      })
      .catch(() => {});
  }, []);

  const [researchCount, setResearchCount] = React.useState(0);
  const [trainingCompleted, setTrainingCompleted] = React.useState(0);
  const [localTopicsCount, setLocalTopicsCount] = React.useState(0);
  const [assetCount, setAssetCount] = React.useState(0);

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
  const isEmailInstalled = modulesState.sigma_email_client === true;
  const isMessagingInstalled = modulesState.sigma_messaging_hub === true;

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


  return (
    <aside className="sidebar">
      <button className="collapse-btn left" onClick={() => setLeftVisible(!leftVisible)}>
         {leftVisible ? <ChevronRight size={14} style={{transform: 'rotate(180deg)'}} /> : <ChevronRight size={14} />}
      </button>
      <div className="sidebar-content">
        
        {/* SIDEBAR HEADER & LOGO */}
        <div className="sidebar-header">
          <div 
            className="logo" 
            onClick={goHome}
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

          {/* Theme Switcher Pill */}
          <div 
            onClick={toggleTheme} 
            title="Cambia Tema (Scuro / Crema Chiaro)"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 12px',
              marginBottom: '18px',
              borderRadius: '12px',
              background: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(190, 160, 110, 0.18)',
              border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(190, 160, 110, 0.35)',
              cursor: 'pointer',
              transition: 'all 0.25s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.68rem', fontWeight: 800, color: theme === 'dark' ? '#e2e8f0' : '#111111' }}>
              {theme === 'dark' ? <Moon size={13} style={{ color: '#bc8cff' }} /> : <Sun size={13} style={{ color: '#ea580c' }} />}
              <span>TEMA {theme === 'dark' ? 'SCURO' : 'CREMA'}</span>
            </div>

            <div style={{
              width: '34px',
              height: '18px',
              borderRadius: '9px',
              background: theme === 'dark' ? 'rgba(188, 140, 255, 0.25)' : 'rgba(234, 88, 12, 0.25)',
              border: theme === 'dark' ? '1px solid rgba(188, 140, 255, 0.45)' : '1px solid rgba(234, 88, 12, 0.5)',
              position: 'relative',
              transition: 'all 0.25s ease',
              display: 'flex',
              alignItems: 'center',
              padding: '2px'
            }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: theme === 'dark' ? '#bc8cff' : '#ea580c',
                transform: theme === 'dark' ? 'translateX(0px)' : 'translateX(16px)',
                transition: 'transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                boxShadow: '0 0 6px rgba(0,0,0,0.3)'
              }} />
            </div>
          </div>
        </div>

        {/* ================================================================= */}
        {/* 1. MACROCATEGORIA: SPAZIO DI LAVORO & GOVERNANCE                   */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '14px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>SPAZIO DI LAVORO</span>
          </div>

          <SidebarItem 
            icon={Home} 
            label="Bacheca" 
            active={activeTabId === null}
            onClick={goHome}
          />
          {isRoadmapInstalled && (
            <SidebarItem 
              icon={Activity} 
              label="Pianificazione & Task" 
              badge={taskInCorso > 0 ? taskInCorso : (taskTotal === 0 ? 0 : undefined)}
              badgeColor="rgba(210,153,34,0.15)"
              badgeSecondary={taskDone > 0 ? taskDone : undefined}
              badgeSecondaryColor="rgba(63,185,80,0.15)"
              active={activeTabId != null && activeTabId.startsWith('roadmap')}
              onClick={() => openTab({ name: '📅 Pianificazione & Audit' }, 'roadmap')} 
            />
          )}

          <SidebarItem 
            icon={FileText} 
            label="Manifesti & Direttive" 
            badge={manifestiCount + modules.reduce((acc, m) => acc + (m.whitepapers?.length || 0), 0)}
            badgeColor="rgba(188,140,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('whitepaper') || activeTabId.startsWith('whitepapers_lib'))}
            onClick={() => openTab({ name: 'Manifesti' }, 'whitepapers_lib')} 
          />
          {isKnowledgeInstalled && (
            <SidebarItem 
              icon={PieChart} 
              label="Argomenti & Memoria" 
              badge={localTopicsCount > 0 || topicsCount > 0 ? Math.max(localTopicsCount, topicsCount) : 0}
              badgeColor="rgba(0,210,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('knowledge')}
              onClick={() => openTab({ name: 'Argomenti' }, 'knowledge')} 
            />
          )}

        </nav>

        {/* ================================================================= */}
        {/* 2. MACROCATEGORIA: STUDIO GENERATIVO & AGENTI AI                  */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '14px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>STUDIO & AGENTI AI</span>
          </div>

          <SidebarItem 
            icon={MessageSquare} 
            label="Chat AI & Assistenti" 
            badge={chatCount > 0 ? chatCount : 0}
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && activeTabId === 'chat'}
            onClick={() => openTab({ name: 'Chat AI', path: 'chat-tab' }, 'chat')} 
          />
          
          {isCreativeInstalled && (
            <SidebarItem
              icon={Palette}
              label="Creative Lab"
              badge={assetCount > 0 ? assetCount : 0}
              badgeColor="rgba(255,80,100,0.15)"
              active={activeTabId != null && activeTabId.startsWith('creative_studio')}
              onClick={() => openTab({ name: '🎨 Creative Lab' }, 'creative_studio')}
            />
          )}

          {isVoiceInstalled && (
            <SidebarItem
              icon={Mic}
              label="Voice Studio"
              badge="TTS"
              badgeColor="rgba(255,121,198,0.15)"
              active={activeTabId != null && activeTabId.startsWith('voice_studio')}
              onClick={() => openTab({ name: '🎙️ Voice Studio' }, 'voice_studio')}
            />
          )}

          {isDevInstalled && (
            <SidebarItem
              icon={Terminal}
              label="Developer Lab"
              badge="DOCKER"
              badgeColor="rgba(0,210,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('developer_lab')}
              onClick={() => openTab({ name: '💻 Developer Lab' }, 'developer_lab')}
            />
          )}





          {isResearchInstalled && (
            <SidebarItem 
              icon={FlaskConical} 
              label="Pipelines Lab" 
              badge={researchCount > 0 ? researchCount : 0}
              badgeColor="rgba(188,140,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('research_lab')}
              onClick={() => openTab({ name: '🔬 Pipelines Lab' }, 'research_lab')} 
            />
          )}


          {isTrainingInstalled && (
            <SidebarItem
              icon={Brain}
              label="Training Lab"
              badge={trainingCompleted > 0 ? trainingCompleted : 0}
              badgeColor="rgba(0,210,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('training_lab')}
              onClick={() => openTab({ name: '🧠 Training Lab' }, 'training_lab')}
            />
          )}

        </nav>

        {/* ================================================================= */}
        {/* 3. MACROCATEGORIA: INFRASTRUTTURA & SISTEMA                       */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '14px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>INFRASTRUTTURA & SISTEMA</span>
          </div>

          {isHardwareInstalled && (
            <SidebarItem 
              icon={Zap} 
              label="Hardware & GPU" 
              badge="VRAM"
              badgeColor="rgba(0,242,254,0.15)"
              active={activeTabId != null && activeTabId.startsWith('hardware_lab')}
              onClick={() => openTab({ name: '⚡ Hardware' }, 'hardware_lab')} 
            />
          )}

          <SidebarItem 
            icon={DownloadCloud} 
            label="Model Hub & HF Engine" 
            badge="KERNEL"
            badgeColor="rgba(255,184,108,0.2)"
            active={activeTabId != null && activeTabId.startsWith('model_hub')}
            onClick={() => openTab({ name: '⚡ Model Hub & HF' }, 'model_hub')} 
          />


          {isNetworkInstalled && (
            <SidebarItem 
              icon={Globe} 
              label="Network Lab" 
              badge="NET"
              badgeColor="rgba(63,185,80,0.15)"
              active={activeTabId != null && activeTabId.startsWith('network_lab')}
              onClick={() => openTab({ name: '🌐 Network Lab' }, 'network_lab')} 
            />
          )}




          <SidebarItem 
            icon={Sliders} 
            label="Configurazione AI" 
            badge="API"
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('ai_config') || activeTabId.startsWith('config'))}
            onClick={() => openTab({ name: '⚙️ Configurazione AI' }, 'ai_config')} 
          />

          {!hiddenTabs.has('mcp_hub') && (
            <SidebarItem 
              icon={Wrench} 
              label="MCP Tools Hub" 
              badge={6}
              badgeColor="rgba(63,185,80,0.15)"
              active={activeTabId != null && activeTabId.startsWith('mcp_hub')}
              onClick={() => openTab({ name: '⚡ MCP Tools' }, 'mcp_hub')} 
            />
          )}

          {isDomoticaInstalled && (
            <SidebarItem 
              icon={Home} 
              label="Domotica & IoT" 
              badge="HA"
              badgeColor="rgba(167,139,250,0.2)"
              active={activeTabId != null && (activeTabId.startsWith('domotica') || activeTabId.startsWith('home_assistant'))}
              onClick={() => openTab({ name: '🏠 Domotica' }, 'domotica')} 
            />
          )}

        </nav>

        {/* ================================================================= */}
        {/* 4. MACROCATEGORIA: COMUNICAZIONE & SOCIAL                         */}
        {/* ================================================================= */}
        {(isEmailInstalled || isMessagingInstalled) && (
          <nav className="nav-section" style={{ marginBottom: '14px' }}>
            <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>COMUNICAZIONE & SOCIAL</span>
            </div>

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
          </nav>
        )}


        {/* ================================================================= */}
        {/* 4. MACROCATEGORIA: ESTENSIONI & PROFILO                            */}
        {/* ================================================================= */}
        <nav className="nav-section" style={{ marginBottom: '14px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>ESTENSIONI & PROFILO</span>
          </div>

          <SidebarItem 
            icon={Package} 
            label="Hub Moduli & Estensioni" 
            badge="STORE"
            badgeColor="rgba(0,210,255,0.2)"
            active={activeTabId != null && activeTabId.startsWith('marketplace')}
            onClick={() => openTab({ name: '📦 Hub Moduli & Estensioni' }, 'marketplace')} 
          />

          {isAudioInstalled && (
            <SidebarItem 
              icon={Radio} 
              label="Musica & Radio FM" 
              badge="LOUNGE"
              badgeColor="rgba(0,242,254,0.2)"
              active={activeTabId != null && (activeTabId.startsWith('music') || activeTabId === 'audio_studio' || activeTabId === 'music_lounge')}
              onClick={() => openTab({ name: '📻 Musica & Radio FM' }, 'music')} 
            />
          )}

          <SidebarItem 
            icon={User} 
            label="Account & Voce" 
            active={activeTabId != null && activeTabId.startsWith('account')}
            onClick={() => openTab({ name: '👤 Account & Profilo' }, 'account')} 
          />

          {/* Dynamic Extra Installed Modules from Marketplace */}
          {dynamicInstalledModules.length > 0 && (
            <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: isLight ? '1px dashed rgba(190, 160, 110, 0.3)' : '1px dashed rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.6rem', color: isLight ? '#7a7060' : 'rgba(255,255,255,0.4)', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px', paddingLeft: '8px' }}>
                MODULI INSTALLATI
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
        </nav>

      </div>
    </aside>
  );
}