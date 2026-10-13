import React, { useState, useEffect, useCallback } from 'react';
import {
  Share2,
  GitMerge,
  Layers,
  Database,
  RefreshCw,
  CheckCircle2,
  Clock,
  Cpu,
  ArrowRight
} from 'lucide-react';

const FederatedDashboard = ({ onRefreshWallet }) => {
  const [federatedState, setFederatedState] = useState(null);
  const [weightsMetadata, setWeightsMetadata] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAggregating, setIsAggregating] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const fetchFederatedData = useCallback(async () => {
    setLoading(true);
    try {
      const [resState, resWeights] = await Promise.all([
        fetch('/api/sigma_network/federated/status'),
        fetch('/api/sigma_network/federated/weights'),
      ]);
      if (resState.ok) {
        setFederatedState(await resState.json());
      }
      if (resWeights.ok) {
        setWeightsMetadata(await resWeights.json());
      }
    } catch (e) {
      console.error('Errore fetch stato federated', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFederatedData();
    const interval = setInterval(fetchFederatedData, 6000);
    return () => clearInterval(interval);
  }, [fetchFederatedData]);

  const handleForceAggregate = async () => {
    setIsAggregating(true);
    setStatusMessage(null);
    try {
      const resp = await fetch('/api/sigma_network/federated/aggregate', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        if (data.aggregated) {
          setStatusMessage(`Aggregazione FedAvg completata con successo! Nuova versione: v${data.model_version}`);
        } else {
          setStatusMessage('Nessun nuovo gradiente presente nel buffer per eseguire il merging.');
        }
        await fetchFederatedData();
        if (onRefreshWallet) onRefreshWallet();
      }
    } catch (e) {
      setStatusMessage('Errore durante la richiesta di aggregazione federata.');
    } finally {
      setIsAggregating(false);
    }
  };

  const bufferCount = federatedState?.buffered_gradients || 0;
  const minGradients = federatedState?.min_for_aggregation || 2;
  const progressPercent = Math.min(100, Math.round((bufferCount / minGradients) * 100));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85))',
        border: '1px solid rgba(168, 85, 247, 0.3)',
        borderRadius: 12,
        padding: '20px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.37)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Share2 size={22} color="#c084fc" />
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#f8fafc', fontWeight: 700 }}>
              Federated Learning & Gradient Consensus
            </h2>
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.85rem', maxWidth: 640 }}>
            Algoritmo FedAvg decentralizzato per il modello open-source della rete Ailo. I nodi miner calcolano gradienti neurali utili che vengono aggregati e mediati in una nuova versione globale dei pesi.
          </p>
        </div>

        <button
          onClick={fetchFederatedData}
          disabled={loading}
          style={{
            background: 'rgba(168, 85, 247, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.4)',
            borderRadius: 8,
            padding: '8px 16px',
            color: '#c084fc',
            cursor: 'pointer',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}
        >
          <RefreshCw size={14} className={loading ? 'sn-spin' : ''} />
          <span>Aggiorna Dati</span>
        </button>
      </div>

      {statusMessage && (
        <div style={{
          background: 'rgba(168, 85, 247, 0.15)',
          border: '1px solid #c084fc',
          borderRadius: 8,
          padding: '12px 16px',
          color: '#e9d5ff',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: '0.85rem'
        }}>
          <CheckCircle2 size={16} color="#c084fc" />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Grid delle Statistiche Principali */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc' }}>
            <Cpu size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ color: '#c084fc' }}>
              v{federatedState?.model_version || 1}
            </div>
            <div className="sn-stat-label">Versione Modello Globale</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
            <Database size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ color: '#38bdf8' }}>
              {federatedState?.total_aggregations || 0}
            </div>
            <div className="sn-stat-label">Round FedAvg Completati</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>
            <Layers size={22} />
          </div>
          <div>
            <div className="sn-stat-val" style={{ color: '#34d399' }}>
              {bufferCount} / {minGradients}
            </div>
            <div className="sn-stat-label">Gradienti in Coda Consenso</div>
          </div>
        </div>
      </div>

      {/* Card Stato Avanzamento Buffer */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.7)',
        borderRadius: 12,
        padding: '24px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: 16
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', fontWeight: 600 }}>
              Soglia di Consenso FedAvg (Prossimo Modello v{(federatedState?.model_version || 1) + 1})
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              Raggiunti {minGradients} contributi neurale indipendenti, la rete fonde automaticamente i pesi.
            </p>
          </div>

          <button
            onClick={handleForceAggregate}
            disabled={isAggregating || bufferCount === 0}
            className="sn-btn-primary"
            style={{
              background: 'linear-gradient(135deg, #9333ea, #7e22ce)',
              border: 'none',
              padding: '8px 18px',
              fontSize: '0.82rem',
              opacity: bufferCount === 0 ? 0.5 : 1,
              cursor: bufferCount === 0 ? 'not-allowed' : 'pointer'
            }}
          >
            <GitMerge size={15} />
            <span>{isAggregating ? 'Fusione Pesi...' : 'Esegui Fusione Pesi Ora'}</span>
          </button>
        </div>

        {/* Progress Bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8', marginBottom: 6 }}>
            <span>Buffer Gradienti: {bufferCount} di {minGradients} richiesti</span>
            <span>{progressPercent}% completato</span>
          </div>
          <div style={{
            width: '100%',
            height: 8,
            background: 'rgba(30, 41, 59, 0.8)',
            borderRadius: 4,
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #38bdf8, #c084fc)',
              transition: 'width 0.4s ease'
            }} />
          </div>
        </div>

        {/* Ultimi gradienti inviati */}
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', marginBottom: 8 }}>
            Contributi Recenti in Coda:
          </div>
          {(!federatedState?.buffer_summary || federatedState.buffer_summary.length === 0) ? (
            <div style={{ fontSize: '0.8rem', color: '#64748b', fontStyle: 'italic', padding: '10px 0' }}>
              Nessun gradiente in attesa. Avvia il mining PoUW o esegui un ciclo per inviare un calcolo utile.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {federatedState.buffer_summary.map((g, idx) => (
                <div key={idx} style={{
                  background: 'rgba(30, 41, 59, 0.6)',
                  padding: '8px 12px',
                  borderRadius: 6,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.78rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Cpu size={14} color="#c084fc" />
                    <span style={{ fontFamily: 'monospace', color: '#cbd5e1' }}>Peer: {g.peer_id}...</span>
                  </div>
                  <span style={{ color: '#94a3b8' }}>Step #{g.step}</span>
                  <span style={{ color: '#34d399', fontSize: '0.72rem' }}>
                    <CheckCircle2 size={12} style={{ display: 'inline', marginRight: 4 }} />
                    Verificato
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Specifiche Architettura Rete */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.6)',
        borderRadius: 12,
        padding: '20px',
        border: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
        <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={16} color="#38bdf8" /> Specifiche Modello Rete P2P (AILO-152M)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, fontSize: '0.8rem' }}>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', padding: '10px', borderRadius: 6 }}>
            <span style={{ color: '#64748b' }}>Architettura:</span>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginTop: 4 }}>SwiGLU + RoPE + RMSNorm</div>
          </div>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', padding: '10px', borderRadius: 6 }}>
            <span style={{ color: '#64748b' }}>Layer Transformers:</span>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginTop: 4 }}>12 Blocchi Decodificatore</div>
          </div>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', padding: '10px', borderRadius: 6 }}>
            <span style={{ color: '#64748b' }}>Consenso Aggregazione:</span>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginTop: 4 }}>FedAvg Distribuito (float16)</div>
          </div>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', padding: '10px', borderRadius: 6 }}>
            <span style={{ color: '#64748b' }}>Ultimo Update Pesi:</span>
            <div style={{ color: '#cbd5e1', fontWeight: 600, marginTop: 4 }}>
              {weightsMetadata?.updated_at ? new Date(weightsMetadata.updated_at * 1000).toLocaleTimeString() : 'Iniziale'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FederatedDashboard;
