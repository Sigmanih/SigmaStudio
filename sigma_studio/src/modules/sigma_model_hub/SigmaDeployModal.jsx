import React, { useState, useEffect } from 'react';
import { Zap, Cpu, HardDrive, CheckCircle2, X, Activity, Layers, ArrowRight, MessageSquare } from 'lucide-react';

export default function SigmaDeployModal({ model, onClose, onDeployed, onSuccess, isLight, addToast, onNavigateToChat }) {
  const [loading, setLoading] = useState(false);
  const [deployedData, setDeployedData] = useState(null);
  const [quant, setQuant] = useState(model.quantization || 'Auto (Tiered)');

  // Tiers come from the machine, not from a fixed list of cards: this modal
  // used to name two specific GPUs and a fixed amount of RAM, and printed layer
  // counts that no planner had produced.
  const [hardware, setHardware] = useState(null);

  useEffect(() => {
    fetch('/api/hardware/status')
      .then(r => r.json())
      .then(data => setHardware(data?.hardware || null))
      .catch(() => setHardware(null));
  }, []);

  const gpus = (hardware?.gpu || []).filter(g => !g.is_integrated);
  const ramTotalGb = hardware?.ram?.total_gb || 0;
  const TIER_COLORS = ['#00d2ff', '#bc8cff', '#f59e0b', '#ef4444'];
  const gb = (value) => (value || value === 0 ? `${Number(value).toFixed(1)} GB` : '—');

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.12)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.04)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.07)';

  const handleDeploy = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/models/engine/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: model.path || model.filename || model.name,
          quantization: quant
        })
      });
      const json = await res.json();
      if (json.success) {
        setDeployedData(json);
        if (addToast) addToast(`⚡ Modello ${model.filename || model.name} attivato in SigmaEngine!`, 'success');
        if (onSuccess) onSuccess(json);
        if (onDeployed) onDeployed(json);
        try {
          window.dispatchEvent(new CustomEvent('sigma_model_deployed', { detail: { model: model.filename || model.name } }));
        } catch (e) {}
      } else {
        if (addToast) addToast(`❌ Errore deploy: ${json.error}`, 'error');
      }
    } catch (err) {
      if (addToast) addToast(`❌ Errore di connessione: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleGoToChat = () => {
    if (onNavigateToChat) {
      onNavigateToChat();
    } else {
      try {
        window.dispatchEvent(new CustomEvent('open_tab', { detail: { type: 'chat' } }));
      } catch (e) {}
    }
    onClose();
  };

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      backdropFilter: 'blur(10px)',
      zIndex: 10050,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
    }}>
      <div style={{
        maxWidth: '540px', width: '100%',
        background: cardBg,
        border: cardBorder,
        borderRadius: '18px',
        boxShadow: '0 30px 60px rgba(0, 0, 0, 0.6)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Modal Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.3)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: deployedData ? 'rgba(16, 185, 129, 0.15)' : 'rgba(0, 210, 255, 0.15)',
              border: deployedData ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              {deployedData ? <CheckCircle2 size={18} color="#10b981" /> : <Zap size={18} color="#00d2ff" />}
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                {deployedData ? 'Modello Pronto in ' : 'Distribuzione in '}
                <span style={{ color: deployedData ? '#10b981' : '#00d2ff' }}>SigmaEngine</span>
              </h2>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>
                {deployedData ? 'Integrazione hardware completata' : 'Universal Inference & VRAM Sharding Tiering'}
              </div>
            </div>
          </div>

          <button onClick={onClose} style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer' }}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Target Model Info */}
          <div style={{ padding: '12px 14px', borderRadius: '12px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', fontWeight: 800, color: '#00d2ff', textTransform: 'uppercase' }}>
              MODELLO SELEZIONATO
            </div>
            <div style={{ fontSize: '0.94rem', fontWeight: 800, color: textPrimary, marginTop: '2px' }}>
              {model.filename || model.name}
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '4px', display: 'flex', gap: '12px' }}>
              <span>Dimensione: <strong>{model.size_label || (model.size_gb ? `${model.size_gb} GB` : 'n/d')}</strong></span>
              <span>Formato: <strong>{model.format || 'Safetensors'}</strong></span>
              <span>VRAM Richiesta: <strong>{model.est_vram_gb ? `~${model.est_vram_gb} GB` : (model.active_vram_label || 'calcolata al deploy')}</strong></span>
            </div>
          </div>

          {/* Success State vs Tiering Preview */}
          {deployedData ? (
            <div style={{
              padding: '16px', borderRadius: '14px',
              background: 'rgba(16, 185, 129, 0.06)', border: '1px solid rgba(16, 185, 129, 0.3)',
              display: 'flex', flexDirection: 'column', gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontWeight: 800, fontSize: '0.86rem' }}>
                <CheckCircle2 size={16} />
                <span>Modello Allocato e Impostato per la Chat</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: textPrimary, lineHeight: '1.5' }}>
                Il modello <strong>{model.filename || model.name}</strong> è ora attivo in memoria e configurato come motore predefinito per la Chat e gli Agenti AI.
              </div>

              {deployedData.tiering_plan?.devices?.length > 0 && (
                <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.70rem' }}>
                  {deployedData.tiering_plan.devices
                    .filter(d => d.estimated_use_gb > 0)
                    .map((d, i) => (
                      <div key={d.tier || i} style={{ display: 'flex', justifyContent: 'space-between', color: TIER_COLORS[i % TIER_COLORS.length], fontWeight: 700 }}>
                        <span>
                          {d.device_id === 'cpu' ? '💾' : d.device_id === 'disk' ? '🗄️' : '⚡'} {d.name}
                          {d.device_id !== 'cpu' && d.device_id !== 'disk' ? ` (${gb(d.free_vram_gb)} liberi)` : ''}:
                        </span>
                        <span>{gb(d.estimated_use_gb)} allocati</span>
                      </div>
                    ))}
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: textMuted, fontWeight: 700, paddingTop: '4px', borderTop: subBorder }}>
                    <span>Precisione: {(deployedData.tiering_plan.quantization || 'auto').toUpperCase()}</span>
                    <span>Totale richiesto: {gb(deployedData.tiering_plan.total_required_gb)}</span>
                  </div>
                </div>
              )}

              {deployedData.tiering_plan?.warnings?.length > 0 && (
                <div style={{ marginTop: '4px', fontSize: '0.68rem', color: '#f59e0b', lineHeight: 1.5 }}>
                  {deployedData.tiering_plan.warnings.map((w, i) => (
                    <div key={i}>⚠️ {w}</div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '8px' }}>
                TIER DISPONIBILI SU QUESTA MACCHINA
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {gpus.map((g, i) => (
                  <div key={g.index ?? i} style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                      <Zap size={15} color={TIER_COLORS[i % TIER_COLORS.length]} />
                      <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        GPU {g.index ?? i}: {g.name}
                      </span>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 800, color: TIER_COLORS[i % TIER_COLORS.length], whiteSpace: 'nowrap' }}>
                      Tier {i} • {g.vram_free_mb ? `${gb(g.vram_free_mb / 1024)} liberi` : ''}
                      {g.vram_total_mb ? ` / ${gb(g.vram_total_mb / 1024)}` : ''}
                    </span>
                  </div>
                ))}

                {ramTotalGb > 0 && (
                  <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <HardDrive size={15} color="#10b981" />
                      <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>RAM di Sistema</span>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#10b981', whiteSpace: 'nowrap' }}>
                      Tier {gpus.length} • {gb(hardware?.ram?.free_gb)} liberi / {gb(ramTotalGb)}
                    </span>
                  </div>
                )}

                {!hardware && (
                  <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, fontSize: '0.74rem', color: textMuted }}>
                    Rilevamento hardware in corso...
                  </div>
                )}
                {hardware && gpus.length === 0 && (
                  <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, fontSize: '0.74rem', color: textMuted }}>
                    Nessuna GPU dedicata rilevata: il modello verrà eseguito su CPU e RAM di sistema.
                  </div>
                )}
              </div>

              <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '8px', lineHeight: 1.5 }}>
                Il piano di partizionamento definitivo viene calcolato da SigmaEngine sul modello scelto e mostrato dopo il deploy.
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '14px 20px',
          borderTop: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.3)'
        }}>
          {deployedData ? (
            <>
              <button
                onClick={onClose}
                style={{
                  padding: '7px 16px', borderRadius: '8px',
                  border: subBorder, background: subBg, color: textPrimary,
                  fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Chiudi
              </button>
              <button
                onClick={handleGoToChat}
                style={{
                  padding: '7px 18px', borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #10b981 0%, #00d2ff 100%)',
                  color: '#ffffff',
                  fontSize: '0.78rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  boxShadow: '0 0 15px rgba(16, 185, 129, 0.4)'
                }}
              >
                <MessageSquare size={14} /> 💬 Vai alla Chat con questo Modello
              </button>
            </>
          ) : (
            <>
              <button
                onClick={onClose}
                disabled={loading}
                style={{
                  padding: '7px 16px', borderRadius: '8px',
                  border: subBorder, background: subBg, color: textPrimary,
                  fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Annulla
              </button>

              <button
                onClick={handleDeploy}
                disabled={loading}
                style={{
                  padding: '7px 18px', borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #00d2ff 0%, #0090ff 100%)',
                  color: '#ffffff',
                  fontSize: '0.78rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px',
                  boxShadow: '0 0 15px rgba(0, 210, 255, 0.4)'
                }}
              >
                {loading ? <Activity className="mh-spin" size={14} /> : <Zap size={14} />}
                {loading ? 'Allocazione in corso...' : '⚡ Avvia in SigmaEngine'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
