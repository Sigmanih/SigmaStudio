import React from 'react';
import { 
  Home, FileText, Activity, PieChart, Layers, ChevronRight, MessageSquare, FlaskConical, Brain, Zap, User, Server, Wrench, Palette, Blocks, Sun, Moon
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';

export const SidebarItem = ({ icon: Icon, label, active, onClick, badge, badgeColor, badgeSecondary, badgeSecondaryColor }) => {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const computedBadgeColor = isLight ? '#2e2820' : (badgeColor || '#3fb950');
  const computedBadgeSecondaryColor = isLight ? '#2e2820' : (badgeSecondaryColor || '#d29922');
  return (
    <div className={`sidebar-item ${active ? 'active' : ''}`} onClick={onClick}>
      <Icon size={18} />
      <span>{label}</span>
      {(badge !== undefined || badgeSecondary !== undefined) && (
        <span className="sidebar-badges">
          {badgeSecondary !== undefined && (
            <span className="badge" style={{ 
              background: badgeSecondaryColor || 'rgba(210,153,34,0.15)', 
              color: computedBadgeSecondaryColor,
              fontSize: '0.6rem',
              padding: '2px 8px',
              borderRadius: '10px',
              fontWeight: 600,
              marginRight: badge !== undefined ? '4px' : '0'
            }}>
              {badgeSecondary}
            </span>
          )}
          {badge !== undefined && (
            <span className="badge" style={{ 
              background: badgeColor || 'rgba(63,185,80,0.15)', 
              color: computedBadgeColor,
              fontSize: '0.6rem',
              padding: '2px 8px',
              borderRadius: '10px',
              fontWeight: 600
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
  modules, 
  manifestiCount,
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
  const [chatCount, setChatCount] = React.useState(0);
  // Le skill disattivate non compaiono nella barra: la scelta vive in config.json
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

  React.useEffect(() => {
    const updateCounts = () => {
      try {
        const data = localStorage.getItem('sigma_chat_sessions');
        if (data) {
          const parsed = JSON.parse(data);
          if (Array.isArray(parsed)) {
            setChatCount(parsed.length);
          }
        } else {
          setChatCount(0);
        }
      } catch (e) {
        setChatCount(0);
      }

      fetch('/api/research/list')
        .then(res => res.json())
        .then(data => {
          if (data.success && Array.isArray(data.sessions)) {
            setResearchCount(data.sessions.length);
          }
        })
        .catch(() => {});

      fetch('/api/training/jobs')
        .then(res => res.json())
        .then(data => {
          if (data.success && Array.isArray(data.jobs)) {
            setTrainingCompleted(data.jobs.filter(j => j.status === 'completed' || j.status === 'running').length);
          }
        })
        .catch(() => {});

      // Argomenti: fetch da /api/topics (endpoint corretto)
      fetch('/api/topics')
        .then(res => res.json())
        .then(data => {
          if (data.topics && Array.isArray(data.topics)) {
            setLocalTopicsCount(data.topics.length);
          }
        })
        .catch(() => {
          // fallback: prova localStorage
          try {
            const k = localStorage.getItem('sigma_knowledge_topics');
            if (k) {
              const parsed = JSON.parse(k);
              if (Array.isArray(parsed)) setLocalTopicsCount(parsed.length);
            }
          } catch (e) {}
        });

      fetch('/api/creative/stats')
        .then(res => res.json())
        .then(data => {
          if (data.assets) {
            setAssetCount(data.assets);
          }
        })
        .catch(() => {});
    };

    updateCounts();
    const interval = setInterval(updateCounts, 5000);
    return () => clearInterval(interval);
  }, []);

  const taskInCorso = tasks.filter(t => t.status === 'in_corso' || !t.status).length;
  const taskDone = tasks.filter(t => t.status === 'done').length;
  const taskTotal = tasks.length;

  return (
    <aside className="sidebar">
      <button className="collapse-btn left" onClick={() => setLeftVisible(!leftVisible)}>
         {leftVisible ? <ChevronRight size={14} style={{transform: 'rotate(180deg)'}} /> : <ChevronRight size={14} />}
      </button>
      <div className="sidebar-content">
        <div className="sidebar-header">
          <div className="logo" style={{ marginBottom: '16px' }}>
            <Layers className="logo-icon" size={24} />
            <h2>Sigma <span>Studio</span></h2>
          </div>

          {/* Modern Theme Switcher directly under Sigma Studio Logo */}
          <div 
            onClick={toggleTheme} 
            title="Cambia Tema (Scuro / Crema Chiaro)"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 12px',
              marginBottom: '20px',
              borderRadius: '12px',
              background: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(190, 160, 110, 0.18)',
              border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(190, 160, 110, 0.35)',
              cursor: 'pointer',
              transition: 'all 0.25s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.7rem', fontWeight: 800, color: theme === 'dark' ? '#e2e8f0' : '#111111' }}>
              {theme === 'dark' ? <Moon size={14} style={{ color: '#bc8cff' }} /> : <Sun size={14} style={{ color: '#ea580c' }} />}
              <span>TEMA {theme === 'dark' ? 'SCURO' : 'CREMA'}</span>
            </div>

            {/* Sliding Pill Switch */}
            <div style={{
              width: '36px',
              height: '20px',
              borderRadius: '10px',
              background: theme === 'dark' ? 'rgba(188, 140, 255, 0.25)' : 'rgba(234, 88, 12, 0.25)',
              border: theme === 'dark' ? '1px solid rgba(188, 140, 255, 0.45)' : '1px solid rgba(234, 88, 12, 0.5)',
              position: 'relative',
              transition: 'all 0.25s ease',
              display: 'flex',
              alignItems: 'center',
              padding: '2px'
            }}>
              <div style={{
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                background: theme === 'dark' ? '#bc8cff' : '#ea580c',
                transform: theme === 'dark' ? 'translateX(0px)' : 'translateX(16px)',
                transition: 'transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                boxShadow: '0 0 6px rgba(0,0,0,0.3)'
              }} />
            </div>
          </div>
        </div>

        <nav className="nav-section">
          <div className="section-title">REPOSITORY</div>
          <SidebarItem 
            icon={Home} 
            label="Bacheca" 
            active={activeTabId === null}
            onClick={goHome}
          />
          <SidebarItem 
            icon={FileText} 
            label="Manifesti" 
            badge={manifestiCount + modules.reduce((acc, m) => acc + (m.whitepapers?.length || 0), 0)}
            badgeColor="rgba(188,140,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('whitepaper') || activeTabId.startsWith('whitepapers_lib'))}
            onClick={() => openTab({ name: 'Manifesti' }, 'whitepapers_lib')} 
          />
          <SidebarItem 
            icon={Activity} 
            label="Pianificazione" 
            badge={taskInCorso > 0 ? taskInCorso : (taskTotal === 0 ? 0 : undefined)}
            badgeColor="rgba(210,153,34,0.15)"
            badgeSecondary={taskDone > 0 ? taskDone : undefined}
            badgeSecondaryColor="rgba(63,185,80,0.15)"
            active={activeTabId != null && activeTabId.startsWith('roadmap')}
            onClick={() => openTab({ name: '📅 Pianificazione & Audit' }, 'roadmap')} 
          />
          <SidebarItem 
            icon={PieChart} 
            label="Argomenti" 
            badge={localTopicsCount > 0 || topicsCount > 0 ? Math.max(localTopicsCount, topicsCount) : 0}
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && activeTabId.startsWith('knowledge')}
            onClick={() => openTab({ name: 'Argomenti' }, 'knowledge')} 
          />
        </nav>

        <nav className="nav-section">
          <div className="section-title">AGENTI</div>
          <SidebarItem 
            icon={MessageSquare} 
            label="Chat" 
            badge={chatCount > 0 ? chatCount : 0}
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && activeTabId === 'chat'}
            onClick={() => openTab({ name: 'Chat AI', path: 'chat-tab' }, 'chat')} 
          />
          {!hiddenTabs.has('creative_studio') && (
            <SidebarItem
              icon={Palette}
              label="Creative Lab"
              badge={assetCount > 0 ? assetCount : 0}
              badgeColor="rgba(188,140,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('creative_studio')}
              onClick={() => openTab({ name: '🎨 Creative Lab' }, 'creative_studio')}
            />
          )}
          <SidebarItem 
            icon={FlaskConical} 
            label="Pipelines Lab" 
            badge={researchCount > 0 ? researchCount : 0}
            badgeColor="rgba(188,140,255,0.15)"
            active={activeTabId != null && activeTabId.startsWith('research_lab')}
            onClick={() => openTab({ name: '🔬 Pipelines Lab' }, 'research_lab')} 
          />
          {!hiddenTabs.has('training_lab') && (
            <SidebarItem
              icon={Brain}
              label="Training Lab"
              badge={trainingCompleted > 0 ? trainingCompleted : 0}
              badgeColor="rgba(0,210,255,0.15)"
              active={activeTabId != null && activeTabId.startsWith('training_lab')}
              onClick={() => openTab({ name: '🧠 Training Lab' }, 'training_lab')}
            />
          )}
          {!hiddenTabs.has('hardware_lab') && (
            <SidebarItem 
              icon={Zap} 
              label="Hardware" 
              badge={2}
              badgeColor="rgba(0,242,254,0.15)"
              active={activeTabId != null && activeTabId.startsWith('hardware_lab')}
              onClick={() => openTab({ name: '⚡ Hardware' }, 'hardware_lab')} 
            />
          )}
          {!hiddenTabs.has('mcp_hub') && (
            <SidebarItem 
              icon={Wrench} 
              label="MCP Tools" 
              badge={6}
              badgeColor="rgba(63,185,80,0.15)"
              active={activeTabId != null && activeTabId.startsWith('mcp_hub')}
              onClick={() => openTab({ name: '⚡ MCP Tools' }, 'mcp_hub')} 
            />
          )}
          <SidebarItem 
            icon={Home} 
            label="Domotica" 
            badge="HA"
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && (activeTabId.startsWith('domotica') || activeTabId.startsWith('home_assistant'))}
            onClick={() => openTab({ name: '🏠 Domotica' }, 'domotica')} 
          />
          <SidebarItem 
            icon={User} 
            label="Account & Voce" 
            active={activeTabId != null && activeTabId.startsWith('account')}
            onClick={() => openTab({ name: '👤 Account & Profilo' }, 'account')} 
          />
        </nav>

      </div>
    </aside>
  );
}