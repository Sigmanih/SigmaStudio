import React, { useState, useEffect, useCallback } from 'react';
import { Download, Activity, CheckCircle2, XCircle, Trash2, ArrowRight, Zap, RefreshCw, Layers, HardDrive } from 'lucide-react';

export default function DownloadManager({ isLight, addToast, onDeployRequested }) {
  const [downloads, setDownloads] = useState([]);
  const [loading, setLoading] = useState(true);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const fetchDownloads = useCallback(async () => {
    try {
      const res = await fetch('/api/models/hf/downloads');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setDownloads(json.downloads || []);
        }
      }
    } catch (e) {
      console.error('Error fetching downloads:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDownloads();
    const interval = setInterval(fetchDownloads, 1200);
    return () => clearInterval(interval);
  }, [fetchDownloads]);

  const handleCancelDownload = async (taskId) => {
    try {
      const res = await fetch('/api/models/hf/download/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`Download #${taskId} annullato.`, 'info');
        fetchDownloads();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
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
            Coda di Download in Background
          </h2>
          <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
            {downloads.length} Download registrati • Supporto per repository completi e multi-shard
          </div>
        </div>

        <button
          onClick={fetchDownloads}
          style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer', padding: '4px' }}
          title="Aggiorna lista"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: textMuted }}>
          <Activity className="mh-spin" size={20} color="#00d2ff" style={{ margin: '0 auto 8px' }} />
          <span>Caricamento coda download...</span>
        </div>
      ) : downloads.length === 0 ? (
        <div style={{
          padding: '50px 20px', borderRadius: '14px', background: cardBg, border: cardBorder,
          textAlign: 'center', color: textMuted, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px'
        }}>
          <Download size={28} color="#00d2ff" />
          <div style={{ fontSize: '0.86rem', fontWeight: 700, color: textPrimary }}>Nessun download attivo al momento</div>
          <div style={{ fontSize: '0.74rem' }}>Esplora Hugging Face e avvia il download completo di un modello per vederlo qui in tempo reale.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {downloads.map(t => {
            const isDone = t.status === 'completed';
            const isDown = t.status === 'downloading';
            const isFailed = t.status === 'failed';
            const isCancelled = t.status === 'cancelled';

            return (
              <div
                key={t.task_id}
                style={{
                  padding: '16px', borderRadius: '14px',
                  background: cardBg, border: isDone ? '1px solid rgba(16, 185, 129, 0.3)' : cardBorder,
                  display: 'flex', flexDirection: 'column', gap: '10px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '0.64rem', padding: '1px 5px', borderRadius: '3px', background: subBg, color: textMuted, fontFamily: 'monospace' }}>
                        #{t.task_id}
                      </span>
                      <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
                        {t.filename}
                      </span>
                      {t.is_repo_download && (
                        <span style={{
                          fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                          background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', fontWeight: 800
                        }}>
                          MODULO COMPLETO ({t.total_files} file)
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                      Repository: <strong>{t.model_id}</strong>
                      {t.is_repo_download && isDown && t.current_file_name && (
                        <span style={{ color: '#ffb86c', marginLeft: '6px' }}>
                          • Scaricamento File {t.current_file_idx}/{t.total_files}: <code>{t.current_file_name}</code>
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {isDown && (
                      <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff', fontFamily: 'monospace' }}>
                        {t.speed_mbps} MB/s • ETA: {t.eta_seconds > 60 ? `${Math.round(t.eta_seconds / 60)}m` : `${t.eta_seconds}s`}
                      </span>
                    )}

                    {isDone && (
                      <button
                        onClick={() => onDeployRequested && onDeployRequested({ filename: t.filename, path: t.save_path, size_gb: (t.downloaded_mb / 1024).toFixed(1) })}
                        style={{
                          padding: '5px 12px', borderRadius: '6px',
                          border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                          color: '#ffffff', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: '4px', boxShadow: '0 0 10px rgba(0, 210, 255, 0.3)'
                        }}
                      >
                        <Zap size={12} /> ⚡ Avvia in SigmaEngine
                      </button>
                    )}

                    {isDown && (
                      <button
                        onClick={() => handleCancelDownload(t.task_id)}
                        style={{
                          padding: '4px 8px', borderRadius: '4px',
                          border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.1)',
                          color: '#ef4444', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                        }}
                      >
                        Annulla
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress Bar Track */}
                <div className="mh-progress-track">
                  <div
                    className="mh-progress-bar"
                    style={{
                      width: `${t.progress_pct}%`,
                      background: isDone ? '#10b981' : (isFailed ? '#ef4444' : 'linear-gradient(90deg, #00d2ff, #0090ff)')
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem', color: textMuted }}>
                  <span>{t.downloaded_mb} / {t.total_mb || '...'} MB ({t.progress_pct}%)</span>
                  <span style={{
                    fontWeight: 700,
                    color: isDone ? '#10b981' : (isDown ? '#00d2ff' : (isFailed ? '#ef4444' : textMuted))
                  }}>
                    {t.status.toUpperCase()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
