import React from 'react';
import { Server } from 'lucide-react';

export default function BackendStatus({ backends = [] }) {
  if (backends.length === 0) {
    return (
      <div className="cs-backend-status">
        <div className="cs-status-dot unknown"></div>
        <span>No backends</span>
      </div>
    );
  }

  const connected = backends.filter(b => b.available).length;
  const isAllConnected = connected === backends.length;
  
  return (
    <div className="cs-backend-status" title={backends.map(b => `${b.name}: ${b.available ? 'Online' : 'Offline'}`).join('\n')}>
      <div className={`cs-status-dot ${isAllConnected ? 'connected' : connected > 0 ? 'unknown' : 'disconnected'}`}></div>
      <Server size={14} />
      <span>{connected}/{backends.length} Backends</span>
    </div>
  );
}
