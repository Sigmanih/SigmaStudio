import React, { useState, useEffect, useCallback } from 'react';
import { HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power, Activity } from 'lucide-react';

export default function LocalInventory({ isLight, addToast, onDeployRequested }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unloading, setUnloading] = useState(false);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const fetchLocalModels = useCallback(async () => {
    try {
      const res = await fetch('/api/models/local/list');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setModels(json.models || []);
        }
      }
    } catch (e) {
      console.error('Error fetching local models:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLocalModels();
  }, [fetchLocalModels]);

  const handleUnloadModel = async () => {
    setUnloading(true);
    try {
      const res = await fetch('/api/models/engine/unload', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('🧹 Modello scaricato e memoria VRAM liberata.', 'info');
        fetchLocalModels();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setUnloading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{
        padding: '14px 18px', borderRadius: '14px',
        background: cardBg, border: cardBorder,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: textPrimary }}>
            Inventario Modelli Locali & Storage
          </h2>
          <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
            {models.length} Modelli rilevati • Disponibili per il caricamento istantaneo su GPU e SigmaEngine
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={handleUnloadModel}
            disabled={unloading}
            title="Scarica qualsiasi modello attivo in memoria"
            style={{
              padding: '6px 12px', borderRadius: '6px',
              border: '1px solid rgba(239, 68, 68, 0.35)', background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px'
            }}
          >
            <Power size={12} /> Scarica da VRAM
          </button>

          <button
            onClick={fetchLocalModels}
            style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: '4px' }}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: textMuted }}>
          <Activity className="mh-spin" size={20} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
          <span>Scansione storage modelli...</span>
        </div>
      ) : models.length === 0 ? (
        <div style={{
          padding: '50px 20px', borderRadius: '14px', background: cardBg, border: cardBorder,
          textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px'
        }}>
          <HardDrive size={28} color="#bc8cff" />
          <div style={{ fontSize: '0.86rem', fontWeight: 700, color: textPrimary }}>Nessun modello trovato nella directory locale</div>
          <div style={{ fontSize: '0.74rem' }}>Scarica il tuo primo modello da Hugging Face per renderlo disponibile all'istante in SigmaEngine.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {models.map((m, idx) => (
            <div
              key={idx}
              style={{
                padding: '14px 18px', borderRadius: '12px',
                background: m.is_active_in_engine ? (isLight ? 'rgba(0, 210, 255, 0.08)' : 'rgba(0, 210, 255, 0.06)') : cardBg,
                border: m.is_active_in_engine ? '1.5px solid #00d2ff' : cardBorder,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px'
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {m.filename}
                  </span>
                  <span style={{
                    fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
                    background: 'rgba(188, 140, 255, 0.15)', color: '#bc8cff', fontWeight: 800
                  }}>
                    {m.quantization}
                  </span>
                  {m.is_active_in_engine && (
                    <span style={{
                      fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
                      background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 800
                    }}>
                      ATTIVO IN SIGMAENGINE
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '3px' }}>
                  Dimensione: {m.size_gb} GB • VRAM Stimata: ~{m.est_vram_gb} GB • Modificato: {m.modified_at}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                <button
                  onClick={() => onDeployRequested && onDeployRequested(m)}
                  style={{
                    padding: '6px 14px', borderRadius: '6px',
                    border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                    color: '#ffffff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px',
                    boxShadow: '0 0 12px rgba(0, 210, 255, 0.25)'
                  }}
                >
                  <Zap size={13} /> {m.is_active_in_engine ? 'Rialloca' : '⚡ Avvia in SigmaEngine'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
