import React, { useState, useEffect, useCallback } from 'react';
import { HardDrive, Zap, RefreshCw, CheckCircle2, Trash2, Folder, Power, Activity } from 'lucide-react';

export default function LocalInventory({ isLight, addToast, onDeployRequested,
                                         activeDownloads = [] }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unloading, setUnloading] = useState(false);
  const [deletingPath, setDeletingPath] = useState(null);

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
        if (addToast) addToast(`🧹 ${json.message}`, 'info');
        fetchLocalModels();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setUnloading(false);
    }
  };

  const handleDeleteModel = async (model) => {
    const name = model.filename || model.display_name || model.model_id;
    const sizeInfo = model.size_label || (model.size_gb ? `${model.size_gb} GB` : '');
    const confirmMsg = `Sei sicuro di voler eliminare definitivamente il modello "${name}"${sizeInfo ? ` (${sizeInfo})` : ''} dallo storage locale?`;
    
    if (!window.confirm(confirmMsg)) {
      return;
    }

    setDeletingPath(model.path || model.filename);
    try {
      const res = await fetch('/api/models/local/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path,
          model_id: model.model_id || model.filename,
          filename: model.filename
        })
      });
      const json = await res.json();
      if (res.ok && json.success) {
        if (addToast) addToast(`🗑️ ${json.message || 'Modello eliminato con successo.'}`, 'success');
        fetchLocalModels();
      } else {
        if (addToast) addToast(`❌ ${json.error || 'Errore durante l\'eliminazione del modello.'}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setDeletingPath(null);
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
            title="Scarica il modello attivo e libera la memoria che occupa"
            style={{
              padding: '6px 12px', borderRadius: '6px',
              border: '1px solid rgba(239, 68, 68, 0.35)', background: 'rgba(239, 68, 68, 0.1)',
              color: '#ef4444', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px'
            }}
          >
            <Power size={12} /> {unloading ? 'Rilascio…' : 'Rilascia memoria'}
          </button>

          <button
            onClick={fetchLocalModels}
            style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: '4px' }}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {activeDownloads.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary }}>
            Download in corso
          </div>
          {activeDownloads.map(task => (
            <div key={task.task_id} style={{
              padding: '12px 16px', borderRadius: '12px',
              background: cardBg, border: '1.5px solid rgba(0, 210, 255, 0.35)',
              display: 'flex', flexDirection: 'column', gap: '7px',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', gap: '10px',
                fontSize: '0.82rem', fontWeight: 700, color: textPrimary,
              }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {task.repo_id || task.filename}
                </span>
                <span style={{ color: textMuted, fontWeight: 600, flexShrink: 0 }}>
                  {task.progress_pct}%
                </span>
              </div>
              <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)' }}>
                <div style={{
                  width: `${task.progress_pct}%`, height: '100%', borderRadius: '3px',
                  background: 'linear-gradient(90deg,#00d2ff,#3a7bd5)',
                  transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{ fontSize: '0.68rem', color: textMuted }}>
                {task.downloaded_label || ''} {task.status}
              </div>
            </div>
          ))}
        </div>
      )}

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
                  {m.format_tag && (
                    <span style={{
                      fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
                      fontWeight: 800,
                      background: m.format_tag === 'GGUF'
                        ? 'rgba(34, 197, 94, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                      color: m.format_tag === 'GGUF' ? '#22c55e' : '#00d2ff',
                    }}>
                      {m.format_tag}
                    </span>
                  )}
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
                  {m.format} • {m.size_gb} GB • VRAM stimata ~{m.est_vram_gb} GB
                  {m.added_at && <> • Aggiunto: {m.added_at}</>}
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

                <button
                  onClick={() => handleDeleteModel(m)}
                  disabled={deletingPath === (m.path || m.filename)}
                  title="Elimina definitivamente questo modello dallo storage locale"
                  style={{
                    padding: '6px 10px', borderRadius: '6px',
                    border: isLight ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid rgba(239, 68, 68, 0.3)',
                    background: isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.1)',
                    color: '#ef4444', fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '4px',
                    opacity: deletingPath === (m.path || m.filename) ? 0.6 : 1,
                    transition: 'all 0.18s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                    e.currentTarget.style.borderColor = '#ef4444';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.1)';
                    e.currentTarget.style.borderColor = isLight ? 'rgba(239, 68, 68, 0.35)' : 'rgba(239, 68, 68, 0.3)';
                  }}
                >
                  <Trash2 size={13} />
                  {deletingPath === (m.path || m.filename) ? 'Rimozione...' : 'Elimina'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
