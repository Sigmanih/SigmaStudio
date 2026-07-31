import React, { useState, useEffect } from 'react';
import { Brain, Wrench, Cpu, Zap, Settings, Globe, RefreshCw, CheckCircle2 } from 'lucide-react';

const MCP_ICONS = {
  'Memory MCP': Brain,
  'Developer MCP': Wrench,
  'Hardware MCP': Cpu,
  'Training MCP': Settings,
  'Inference MCP': Zap,
  'Network MCP': Globe,
};

export default function McpStatusBar() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchMcpStatus = async () => {
    try {
      const res = await fetch('/api/mcp/servers');
      if (res.ok) {
        const data = await res.json();
        if (data.servers) {
          setServers(data.servers);
          setLastUpdated(new Date().toLocaleTimeString());
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

  return (
    <div
      className="mcp-status-bar"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '8px 16px',
        background: 'rgba(15, 17, 26, 0.95)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        overflowX: 'auto',
        fontSize: '0.75rem',
        color: '#8b8fa3',
        backdropFilter: 'blur(8px)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#f0f2f8', whiteSpace: 'nowrap' }}>
        <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#3fb950', boxShadow: '0 0 8px #3fb950' }} />
        {/* Contati, non scritti a mano: l'hub ne elenca 7 da quando c'e' il
            server Benchmark, e un numero fisso resta indietro al prossimo. */}
        <span>MCP Hub ({servers.length} Server)</span>
      </div>

      <div style={{ width: '1px', height: '16px', background: 'rgba(255, 255, 255, 0.1)', margin: '0 4px' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'nowrap' }}>
        {servers.map(s => {
          const Icon = MCP_ICONS[s.name] || Wrench;
          return (
            <div
              key={s.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '3px 9px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: '#e2e4eb',
                whiteSpace: 'nowrap',
                fontSize: '0.72rem'
              }}
              title={`${s.description} — Tools: ${s.tools_count}, Risorse: ${s.resources_count}`}
            >
              <Icon size={12} style={{ color: '#00d2ff' }} />
              <span style={{ fontWeight: 600 }}>{s.name.replace(' MCP', '')}</span>
              <span style={{ fontSize: '0.65rem', color: '#3fb950', fontWeight: 700 }}>• Active ({s.tools_count})</span>
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
        title="Aggiorna stato MCP Server"
      >
        <RefreshCw size={12} className={loading ? 'spin' : ''} />
      </button>
    </div>
  );
}
