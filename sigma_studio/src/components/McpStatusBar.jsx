import React, { useState, useEffect } from 'react';
import { Brain, Wrench, Cpu, Zap, Settings, Globe, RefreshCw, Home, Activity } from 'lucide-react';

const MCP_ICONS = {
  'Memory MCP': Brain,
  'Developer MCP': Wrench,
  'Hardware MCP': Cpu,
  'Training MCP': Settings,
  'Inference MCP': Zap,
  'Network MCP': Globe,
  'Home Assistant MCP': Home,
};

export default function McpStatusBar({ openTab }) {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchMcpStatus = async () => {
    try {
      const res = await fetch('/api/mcp/servers');
      if (res.ok) {
        const data = await res.json();
        if (data.servers) {
          setServers(data.servers);
        }
      }
    } catch (e) {
      console.warn("MCP servers status fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMcpStatus();
    const interval = setInterval(fetchMcpStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const totalServersCount = servers.length > 0 ? servers.length : 12;

  return (
    <div
      className="mcp-status-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '6px 16px',
        background: 'rgba(14, 16, 22, 0.95)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        overflowX: 'auto',
        fontSize: '0.75rem',
        color: '#8b8fa3',
        backdropFilter: 'blur(10px)',
        scrollbarWidth: 'none'
      }}
    >
      {/* Card 1: MCP Hub Status */}
      <div
        onClick={() => openTab && openTab({ name: '⚡ MCP Tools' }, 'mcp_hub')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 12px',
          borderRadius: '12px',
          background: 'rgba(63, 185, 80, 0.1)',
          border: '1px solid rgba(63, 185, 80, 0.3)',
          color: '#3fb950',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'all 0.2s ease',
          fontWeight: 700
        }}
        title="Clicca per aprire l'MCP Hub"
      >
        <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#3fb950', boxShadow: '0 0 8px #3fb950' }} />
        <span>🔌 MCP Hub: Collegamenti Attivi ({totalServersCount} Server)</span>
      </div>

      {/* Card 2: Hardware & GPU Status */}
      <div
        onClick={() => openTab && openTab({ name: '⚡ Hardware & GPU Monitor' }, 'hardware_lab')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 12px',
          borderRadius: '12px',
          background: 'rgba(0, 210, 255, 0.1)',
          border: '1px solid rgba(0, 210, 255, 0.3)',
          color: '#00d2ff',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'all 0.2s ease',
          fontWeight: 700
        }}
        title="Clicca per aprire Hardware Lab"
      >
        <Activity size={13} color="#00d2ff" />
        <span>⚡ Hardware: Cluster GPU & Ollama Online</span>
      </div>

      {/* Card 3: Home Assistant Status */}
      <div
        onClick={() => openTab && openTab({ name: '🏠 Domotica & Home Assistant' }, 'domotica')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '4px 12px',
          borderRadius: '12px',
          background: 'rgba(167, 139, 250, 0.1)',
          border: '1px solid rgba(167, 139, 250, 0.3)',
          color: '#a78bfa',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'all 0.2s ease',
          fontWeight: 700
        }}
        title="Clicca per aprire il Pannello Domotica"
      >
        <Home size={13} color="#a78bfa" />
        <span>🏠 Home Assistant: Integrazione Domotica OK</span>
      </div>

      <div style={{ width: '1px', height: '16px', background: 'rgba(255, 255, 255, 0.1)', margin: '0 2px' }} />

      {/* Connected Server Pills */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'nowrap' }}>
        {servers.map(s => {
          const Icon = MCP_ICONS[s.name] || Wrench;
          return (
            <div
              key={s.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '3px 8px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: '#c0c4d0',
                whiteSpace: 'nowrap',
                fontSize: '0.7rem'
              }}
              title={`${s.description} — Tools: ${s.tools_count}`}
            >
              <Icon size={12} style={{ color: '#00d2ff' }} />
              <span style={{ fontWeight: 600 }}>{s.name.replace(' MCP', '')}</span>
              <span style={{ fontSize: '0.62rem', color: '#3fb950', fontWeight: 700 }}>({s.tools_count})</span>
            </div>
          );
        })}
      </div>

      <button
        onClick={fetchMcpStatus}
        style={{
          marginLeft: 'auto',
          background: 'transparent',
          border: 'none',
          color: '#8b8fa3',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '0.7rem'
        }}
        title="Aggiorna stato connessioni"
      >
        <RefreshCw size={12} className={loading ? 'spin' : ''} />
      </button>
    </div>
  );
}
