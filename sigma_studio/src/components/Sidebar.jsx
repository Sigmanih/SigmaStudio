import React from 'react';
import { 
  Home, FileText, Activity, PieChart, Layers, ChevronRight, MessageSquare, FlaskConical
} from 'lucide-react';

export const SidebarItem = ({ icon: Icon, label, active, onClick, badge, badgeColor, badgeSecondary, badgeSecondaryColor }) => (
  <div className={`sidebar-item ${active ? 'active' : ''}`} onClick={onClick}>
    <Icon size={18} />
    <span>{label}</span>
    {(badge !== undefined || badgeSecondary !== undefined) && (
      <span className="sidebar-badges">
        {badgeSecondary !== undefined && (
          <span className="badge" style={{ 
            background: badgeSecondaryColor || 'rgba(210,153,34,0.15)', 
            color: badgeSecondaryColor || '#d29922',
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
            color: badgeColor || '#3fb950',
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
          <div className="logo">
            <Layers className="logo-icon" size={24} />
            <h2>Sigma <span>Studio</span></h2>
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
            label="Roadmap" 
            badge={taskInCorso > 0 ? taskInCorso : (taskTotal === 0 ? 0 : undefined)}
            badgeColor="rgba(210,153,34,0.15)"
            badgeSecondary={taskDone > 0 ? taskDone : undefined}
            badgeSecondaryColor="rgba(63,185,80,0.15)"
            active={activeTabId != null && activeTabId.startsWith('roadmap')}
            onClick={() => openTab({ name: 'Research Roadmap' }, 'roadmap')} 
          />
          <SidebarItem 
            icon={PieChart} 
            label="Argomenti" 
            badge={topicsCount > 0 ? topicsCount : 0}
            badgeColor="rgba(0,210,255,0.15)"
            active={activeTabId != null && activeTabId.startsWith('knowledge')}
            onClick={() => openTab({ name: 'Argomenti' }, 'knowledge')} 
          />
          <SidebarItem 
            icon={MessageSquare} 
            label="Chat" 
            badgeColor="rgba(0,210,255,0.2)"
            active={activeTabId != null && activeTabId === 'chat'}
            onClick={() => openTab({ name: 'Chat AI', path: 'chat-tab' }, 'chat')} 
          />
        </nav>

        <nav className="nav-section">
          <div className="section-title">AGENTI</div>
          <SidebarItem 
            icon={FlaskConical} 
            label="Research Lab" 
            active={activeTabId != null && activeTabId.startsWith('research_lab')}
            onClick={() => openTab({ name: '🔬 Sigma Research Lab' }, 'research_lab')} 
          />
        </nav>
      </div>
    </aside>
  );
}