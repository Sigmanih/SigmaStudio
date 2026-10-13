import React, { useState, useEffect } from 'react';
import {
  Pickaxe,
  Play,
  Square,
  TrendingDown,
  Layers,
  Coins,
  Cpu,
  Zap,
  Activity,
  CheckCircle2
} from 'lucide-react';

const MiningConsole = ({ onRewardMined }) => {
  const [miningStatus, setMiningStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stepping, setStepping] = useState(false);

  const fetchStatus = async () => {
    try {
      const resp = await fetch('/api/sigma_network/mining/status');
      if (resp.ok) {
        const data = await resp.json();
        setMiningStatus(data);
      }
    } catch (e) {
      console.error('Errore recupero stato mining', e);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/sigma_network/mining/toggle', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        setMiningStatus(data);
      }
    } catch (e) {
      console.error('Errore toggle mining', e);
    } finally {
      setLoading(false);
    }
  };

  const handleStep = async () => {
    setStepping(true);
    try {
      const resp = await fetch('/api/sigma_network/mining/step', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        setMiningStatus(data);
        if (onRewardMined) onRewardMined();
      }
    } catch (e) {
      console.error('Errore step mining', e);
    } finally {
      setStepping(false);
    }
  };

  const handleSetIntensity = async (intensity) => {
    try {
      const resp = await fetch('/api/sigma_network/mining/intensity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intensity }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setMiningStatus(data);
      }
    } catch (e) {
      console.error('Errore intensità mining', e);
    }
  };

  const isRunning = miningStatus?.running || false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Intestazione Sezione */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.6)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '24px',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 20
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            width: 52,
            height: 52,
            borderRadius: '14px',
            background: isRunning ? 'rgba(168, 85, 247, 0.2)' : 'rgba(100, 116, 139, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: isRunning ? '#c084fc' : '#94a3b8',
            border: `1px solid ${isRunning ? '#a855f7' : 'rgba(255, 255, 255, 0.1)'}`
          }}>
            <Pickaxe size={28} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 10 }}>
              Ailo Proof-of-Useful-Compute
              <span style={{
                fontSize: '0.72rem',
                padding: '3px 8px',
                borderRadius: '6px',
                background: isRunning ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                color: isRunning ? '#34d399' : '#94a3b8',
                fontWeight: 700
              }}>
                {isRunning ? 'IN ESECUZIONE' : 'IN PAUSA'}
              </span>
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              Addestra modelli distribuiti in background (discesa del gradiente RoPE/SwiGLU) e guadagna AiloCoin per ogni blocco utile calcolato.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={handleStep}
            disabled={stepping}
            style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#38bdf8',
              borderRadius: '8px',
              padding: '10px 18px',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            <Zap size={16} />
            <span>{stepping ? 'Calcolo in corso...' : 'Calcola Blocco Ora'}</span>
          </button>

          <button
            onClick={handleToggle}
            disabled={loading}
            style={{
              background: isRunning ? 'rgba(239, 68, 68, 0.2)' : 'linear-gradient(135deg, #a855f7, #00d4ff)',
              border: isRunning ? '1px solid #ef4444' : 'none',
              color: isRunning ? '#fca5a5' : '#000',
              borderRadius: '8px',
              padding: '10px 22px',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            {isRunning ? <Square size={16} /> : <Play size={16} />}
            <span>{isRunning ? 'Ferma Miner' : 'Avvia Mining Background'}</span>
          </button>
        </div>
      </div>

      {/* Riquadri Telemetria */}
      <div className="sn-stats-row">
        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc' }}>
            <TrendingDown size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{miningStatus?.loss ? miningStatus.loss.toFixed(4) : '4.2500'}</div>
            <div className="sn-stat-label">Loss Convergente</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(0, 212, 255, 0.15)', color: '#00d4ff' }}>
            <Layers size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{miningStatus?.total_gradients || 0}</div>
            <div className="sn-stat-label">Batch Gradienti Calcolati</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            <Coins size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ color: '#34d399' }}>
              +{miningStatus?.rewards_mined ? miningStatus.rewards_mined.toFixed(2) : '0.00'}
            </div>
            <div className="sn-stat-label">AiloCoin Guadagnati</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
            <Cpu size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ fontSize: '0.95rem' }}>{miningStatus?.architecture || 'AILO-152M'}</div>
            <div className="sn-stat-label">Architettura Modello</div>
          </div>
        </div>
      </div>

      {/* Configurazione Intensità e Log Cronologia */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr',
        gap: 20
      }}>
        {/* Intensità Calcolo */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '14px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 16
        }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#38bdf8' }}>Intensità Risorse Macchina</h3>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#94a3b8' }}>
            Regola quanto processore/GPU allocare per la computazione distribuita dei gradienti:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { level: 1, label: 'Bassa (Silenziosa)', desc: 'Ideale per non pesare su CPU/RAM' },
              { level: 2, label: 'Bilanciata (Standard)', desc: 'Consigliata per PC moderni o Raspberry Pi 5' },
              { level: 3, label: 'Alta (Prestazioni Max)', desc: 'Sfrutta appieno accelerazione vettoriale/CUDA' },
            ].map(item => (
              <div
                key={item.level}
                onClick={() => handleSetIntensity(item.level)}
                style={{
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: `1px solid ${miningStatus?.intensity === item.level ? '#00d4ff' : 'rgba(255, 255, 255, 0.08)'}`,
                  background: miningStatus?.intensity === item.level ? 'rgba(0, 212, 255, 0.1)' : 'rgba(30, 41, 59, 0.4)',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3
                }}
              >
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>{item.label}</div>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Log Cronologia Passi */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '14px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity size={18} color="#a855f7" /> Telemetria Passi di Convergenza
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Ultimi 20 round</span>
          </div>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            maxHeight: '260px',
            overflowY: 'auto'
          }}>
            {(!miningStatus?.history || miningStatus.history.length === 0) ? (
              <div style={{ color: '#64748b', fontSize: '0.8rem', padding: '30px 0', textAlign: 'center' }}>
                Nessun round eseguito. Clicca su "Calcola Blocco Ora" o avvia il mining.
              </div>
            ) : (
              [...miningStatus.history].reverse().map((h, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'rgba(30, 41, 59, 0.5)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '0.78rem'
                  }}
                >
                  <span style={{ fontFamily: 'monospace', color: '#38bdf8' }}>Round #{h.step}</span>
                  <span style={{ color: '#cbd5e1' }}>Loss: <strong>{h.loss}</strong></span>
                  <span style={{ color: '#94a3b8' }}>{h.tokens} tok</span>
                  <span style={{ color: '#34d399', fontWeight: 600 }}>+{h.reward} AILO</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MiningConsole;
