import React, { useState } from 'react';
import {
  Radio,
  Shield,
  ShieldAlert,
  Cpu,
  RefreshCw,
  Activity,
  Zap,
  Globe,
  CheckCircle,
  ExternalLink,
  Plus,
  Trash2,
  X,
  Server
} from 'lucide-react';

const PeerRadar = ({ networkMap, onRefresh, onSelectPeerForQuery }) => {
  const [selectedPeerId, setSelectedPeerId] = useState(null);
  const [isPinging, setIsPinging] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [addHost, setAddHost] = useState('');
  const [addPort, setAddPort] = useState('8000');
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState(null);

  const localNode = networkMap?.local_node || {};
  const peers = networkMap?.peers || [];
  const summary = networkMap?.summary || {};

  const selectedPeer = peers.find(p => p.peer_id === selectedPeerId) || peers[0] || null;

  const [isSweeping, setIsSweeping] = useState(false);

  const handleClusterSweep = async () => {
    setIsSweeping(true);
    try {
      await fetch('/api/sigma_network/cluster/sweep', { method: 'POST' });
      await fetch('/api/sigma_network/peers/ping', { method: 'POST' });
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Auto-cluster sweep fallito', e);
    } finally {
      setIsSweeping(false);
    }
  };

  const handlePing = async () => {
    setIsPinging(true);
    try {
      await fetch('/api/sigma_network/peers/ping', { method: 'POST' });
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Ping fallito', e);
    } finally {
      setIsPinging(false);
    }
  };

  const handleAddPeer = async (e) => {
    e.preventDefault();
    if (!addHost.trim()) return;
    setAddLoading(true);
    setAddError(null);
    try {
      const resp = await fetch('/api/sigma_network/peers/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: addHost.trim(),
          port: parseInt(addPort, 10) || 8000,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Impossibile connettere il peer');
      }
      setIsAddModalOpen(false);
      setAddHost('');
      setAddPort('8000');
      // Subito un ping per aggiornare latenza e stato
      await handlePing();
      if (onRefresh) onRefresh();
    } catch (err) {
      setAddError(err.message || 'Errore di connessione al nodo remoto');
    } finally {
      setAddLoading(false);
    }
  };

  const handleRemovePeer = async (peerId) => {
    if (!peerId) return;
    try {
      await fetch(`/api/sigma_network/peers/${peerId}`, { method: 'DELETE' });
      setSelectedPeerId(null);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Errore rimozione peer', err);
    }
  };

  const handleTrustToggle = async (peerId, currentTrust) => {
    try {
      await fetch('/api/sigma_network/peers/trust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ peer_id: peerId, trusted: !currentTrust }),
      });
      if (onRefresh) onRefresh();
    } catch (e) {
      console.error('Errore modifica trust', e);
    }
  };

  // Dimensioni Radar
  const centerX = 220;
  const centerY = 220;
  const maxRadius = 180;

  return (
    <div className="sn-radar-view">
      {/* Telemetria Superiore */}
      <div className="sn-stats-row">
        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(0, 212, 255, 0.15)', color: '#00d4ff' }}>
            <Globe size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{summary.online_count || 1}</div>
            <div className="sn-stat-label">Nodi Online Ora</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' }}>
            <Cpu size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{summary.cluster_models_count || 0}</div>
            <div className="sn-stat-label">Modelli nel Cluster</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            <Shield size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{summary.trusted_count || 0}</div>
            <div className="sn-stat-label">Peer Verificati</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
            <Activity size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ fontSize: '1rem', textTransform: 'uppercase' }}>
              {summary.cluster_status === 'active' ? 'Cooperativo' : 'Standalone'}
            </div>
            <div className="sn-stat-label">Stato Topologia</div>
          </div>
        </div>
      </div>

      {/* Pannello Radar Interattivo */}
      <div className="sn-radar-panel">
        <div className="sn-radar-display">
          <div style={{ position: 'absolute', top: 12, left: 16, display: 'flex', gap: 8, alignItems: 'center', zIndex: 10 }}>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Radio size={14} color="#00d4ff" /> UDP 47777 Scan
            </span>
            <button
              onClick={handleClusterSweep}
              disabled={isSweeping}
              title="Scansiona automaticamente la subnet locale per trovare ed eseguire l'handshake con altri Sigma Studio"
              style={{
                background: 'rgba(168, 85, 247, 0.15)',
                border: '1px solid rgba(168, 85, 247, 0.4)',
                color: '#c084fc',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <Zap size={12} className={isSweeping ? 'sn-spin' : ''} /> {isSweeping ? 'Scansione...' : 'Auto-Cluster LAN'}
            </button>
            <button
              onClick={handlePing}
              disabled={isPinging}
              style={{
                background: 'rgba(0, 212, 255, 0.12)',
                border: '1px solid rgba(0, 212, 255, 0.3)',
                color: '#38bdf8',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <RefreshCw size={12} className={isPinging ? 'sn-spin' : ''} /> Ping Cluster
            </button>
            <button
              onClick={() => { setIsAddModalOpen(true); setAddError(null); }}
              style={{
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.35)',
                color: '#34d399',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 5
              }}
            >
              <Plus size={12} /> Aggiungi Peer
            </button>
          </div>

          <svg className="sn-radar-svg" viewBox="0 0 440 440">
            <defs>
              <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.15" />
                <stop offset="70%" stopColor="#00d4ff" stopOpacity="0.03" />
                <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
              </radialGradient>
              <linearGradient id="sweepGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Sfondo a cerchi concentrici (scale latenza) */}
            <circle cx={centerX} cy={centerY} r={maxRadius} fill="url(#radarGlow)" stroke="rgba(0, 212, 255, 0.2)" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx={centerX} cy={centerY} r={maxRadius * 0.66} fill="none" stroke="rgba(0, 212, 255, 0.25)" strokeWidth="1" />
            <circle cx={centerX} cy={centerY} r={maxRadius * 0.33} fill="none" stroke="rgba(0, 212, 255, 0.3)" strokeWidth="1" strokeDasharray="2 2" />

            {/* Assi ortogonali */}
            <line x1={centerX} y1="30" x2={centerX} y2="410" stroke="rgba(0, 212, 255, 0.15)" strokeWidth="1" />
            <line x1="30" y1={centerY} x2="410" y2={centerY} stroke="rgba(0, 212, 255, 0.15)" strokeWidth="1" />

            {/* Linea rotante di scansione */}
            <g className="sn-radar-sweep">
              <path
                d={`M ${centerX} ${centerY} L ${centerX + maxRadius} ${centerY} A ${maxRadius} ${maxRadius} 0 0 0 ${centerX + maxRadius * 0.86} ${centerY - maxRadius * 0.5} Z`}
                fill="url(#sweepGrad)"
              />
              <line x1={centerX} y1={centerY} x2={centerX + maxRadius} y2={centerY} stroke="#00d4ff" strokeWidth="1.5" />
            </g>

            {/* Nodo Locale (Centro del Radar) */}
            <circle cx={centerX} cy={centerY} r="18" fill="rgba(0, 212, 255, 0.2)" stroke="#00d4ff" strokeWidth="2" />
            <circle cx={centerX} cy={centerY} r="7" fill="#00d4ff" />
            <text x={centerX} y={centerY + 32} fill="#38bdf8" fontSize="10" fontWeight="bold" textAnchor="middle">
              TU (Locale)
            </text>

            {/* Peer posizionati nello spazio polare */}
            {peers.map((peer, idx) => {
              const angleRad = ((peer.radar_angle || (idx * 60)) * Math.PI) / 180;
              const dist = (peer.radar_distance || 0.6) * maxRadius;
              const px = centerX + Math.cos(angleRad) * dist;
              const py = centerY + Math.sin(angleRad) * dist;

              const isOnline = peer.is_online;
              const isTrusted = peer.state === 'trusted';
              const isSelected = selectedPeer?.peer_id === peer.peer_id;

              const nodeColor = isTrusted ? '#10b981' : isOnline ? '#00d4ff' : '#64748b';

              return (
                <g
                  key={peer.peer_id || idx}
                  className="sn-peer-node"
                  onClick={() => setSelectedPeerId(peer.peer_id)}
                >
                  {/* Linea di connessione sottile */}
                  <line x1={centerX} y1={centerY} x2={px} y2={py} stroke={nodeColor} strokeOpacity={isSelected ? 0.4 : 0.12} strokeWidth="1" strokeDasharray="3 3" />

                  {/* Halo di selezione */}
                  {isSelected && (
                    <circle cx={px} cy={py} r="16" fill="none" stroke="#00d4ff" strokeWidth="1.5" strokeDasharray="2 2" />
                  )}

                  {/* Punto Peer */}
                  <circle cx={px} cy={py} r={isSelected ? 9 : 7} fill={nodeColor} stroke="#0f172a" strokeWidth="2" />

                  {/* Nome e Latenza etichetta */}
                  <text x={px} y={py - 12} fill="#e2e8f0" fontSize="9" fontWeight="600" textAnchor="middle">
                    {peer.name || `Peer-${idx}`}
                  </text>
                  <text x={px} y={py + 18} fill={isOnline ? '#34d399' : '#94a3b8'} fontSize="8" textAnchor="middle">
                    {peer.latency_ms ? `${Math.round(peer.latency_ms)}ms` : 'offline'}
                  </text>
                </g>
              );
            })}
          </svg>

          <div style={{ display: 'flex', gap: 16, fontSize: '0.75rem', color: '#94a3b8', marginTop: 10 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} /> Verificato & Trusted
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#00d4ff' }} /> Scoperto Online
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#64748b' }} /> Disconnesso
            </span>
          </div>
        </div>

        {/* Inspector Dettagli Peer Selezionato */}
        <div className="sn-peer-inspector">
          <div className="sn-inspector-title">
            <Cpu size={16} /> Ispezione Nodo
          </div>

          {selectedPeer ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>{selectedPeer.name}</div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', wordBreak: 'break-all' }}>
                  ID: {selectedPeer.peer_id}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <span className={`sn-badge`} style={{
                  background: selectedPeer.state === 'trusted' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                  color: selectedPeer.state === 'trusted' ? '#34d399' : '#fbbf24',
                }}>
                  {selectedPeer.state === 'trusted' ? <CheckCircle size={12} /> : <ShieldAlert size={12} />}
                  {selectedPeer.state.toUpperCase()}
                </span>
                <span className="sn-badge" style={{ background: 'rgba(0, 212, 255, 0.15)', color: '#38bdf8' }}>
                  {selectedPeer.latency_ms ? `${Math.round(selectedPeer.latency_ms)} ms` : 'Inattivo'}
                </span>
              </div>

              <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
                <strong>Endpoint:</strong> {selectedPeer.host}:{selectedPeer.port}
              </div>

              <div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: 4 }}>Modelli Offerti nel Cluster:</div>
                {selectedPeer.models && selectedPeer.models.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {selectedPeer.models.map((m, i) => (
                      <span key={i} style={{
                        background: 'rgba(168, 85, 247, 0.15)',
                        color: '#c084fc',
                        fontSize: '0.72rem',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(168, 85, 247, 0.3)'
                      }}>
                        {m.split('/').pop()}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>Nessun modello condiviso</span>
                )}
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  className={`sn-btn-xs ${selectedPeer.state === 'trusted' ? 'sn-btn-untrust' : 'sn-btn-trust'}`}
                  style={{ flex: 1, padding: '7px 10px' }}
                  onClick={() => handleTrustToggle(selectedPeer.peer_id, selectedPeer.state === 'trusted')}
                >
                  {selectedPeer.state === 'trusted' ? 'Revoca Fiducia' : 'Fidati di questo Peer'}
                </button>
                {onSelectPeerForQuery && selectedPeer.models && selectedPeer.models.length > 0 && (
                  <button
                    className="sn-btn-xs sn-btn-query"
                    style={{ flex: 1, padding: '7px 10px' }}
                    onClick={() => onSelectPeerForQuery(selectedPeer)}
                  >
                    Usa nel Cluster
                  </button>
                )}
                <button
                  className="sn-btn-xs"
                  style={{
                    padding: '7px 10px',
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171'
                  }}
                  title="Dimentica questo peer"
                  onClick={() => handleRemovePeer(selectedPeer.peer_id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ) : (
            <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', padding: '30px 0' }}>
              Nessun peer rilevato. Avvia la scoperta o aggiungi l'IP di un amico.
            </div>
          )}

          {/* Lista Rapida Tutti i Peer */}
          <div style={{ marginTop: 12, borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: 10 }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 8 }}>Elenco Peer Rilevati ({peers.length}):</div>
            <div className="sn-peer-list-mini">
              {peers.map(p => (
                <div
                  key={p.peer_id}
                  className={`sn-peer-item-mini ${selectedPeer?.peer_id === p.peer_id ? 'selected' : ''}`}
                  onClick={() => setSelectedPeerId(p.peer_id)}
                >
                  <div className="sn-peer-item-header">
                    <span className="sn-peer-name">{p.name}</span>
                    <span className="sn-peer-latency">
                      {p.latency_ms ? `${Math.round(p.latency_ms)}ms` : 'offline'}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{p.host}:{p.port}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Modale Aggiungi Peer */}
      {isAddModalOpen && (
        <div className="modal-overlay" onClick={() => setIsAddModalOpen(false)}>
          <div
            className="modal-content small"
            onClick={e => e.stopPropagation()}
            style={{
              background: '#0d1117',
              border: '1px solid rgba(0, 212, 255, 0.3)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '420px',
              width: '90%',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, color: '#00d4ff', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Server size={18} /> Aggiungi Peer Remoto
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: 16, lineHeight: 1.4 }}>
              Inserisci l'indirizzo IP locale (es. <code>192.168.1.15</code>) o hostname dell'altro PC su cui è attivo Sigma Studio.
            </p>

            {addError && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#f87171',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.78rem',
                marginBottom: 14
              }}>
                {addError}
              </div>
            )}

            <form onSubmit={handleAddPeer}>
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#cbd5e1', marginBottom: 6, fontWeight: 600 }}>
                  Host / Indirizzo IP
                </label>
                <input
                  type="text"
                  placeholder="es. 192.168.1.25"
                  value={addHost}
                  onChange={e => setAddHost(e.target.value)}
                  autoFocus
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#161b22',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '6px',
                    color: '#fff',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              <div style={{ marginBottom: 18 }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: '#cbd5e1', marginBottom: 6, fontWeight: 600 }}>
                  Porta TCP FastAPI
                </label>
                <input
                  type="number"
                  placeholder="8000"
                  value={addPort}
                  onChange={e => setAddPort(e.target.value)}
                  min="1"
                  max="65535"
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: '#161b22',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    borderRadius: '6px',
                    color: '#fff',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  style={{
                    padding: '8px 14px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#cbd5e1',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    cursor: 'pointer'
                  }}
                >
                  Annulla
                </button>
                <button
                  type="submit"
                  disabled={addLoading}
                  style={{
                    padding: '8px 16px',
                    background: '#00d4ff',
                    border: 'none',
                    color: '#0d1117',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: addLoading ? 'wait' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6
                  }}
                >
                  {addLoading ? 'Verifica in corso...' : 'Connetti Nodo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PeerRadar;
