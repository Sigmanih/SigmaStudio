import React, { useState } from 'react';
import { Zap, Cpu, HardDrive, CheckCircle2, X, Activity, Layers, ArrowRight, MessageSquare } from 'lucide-react';

export default function SigmaDeployModal({ model, onClose, onDeployed, onSuccess, isLight, addToast, onNavigateToChat }) {
  const [loading, setLoading] = useState(false);
  const [deployedData, setDeployedData] = useState(null);
  const [quant, setQuant] = useState(model.quantization || 'Auto (Tiered)');

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
              <span>Dimensione: <strong>{model.size_label || (model.size_gb ? `${model.size_gb} GB` : '51.8 GB')}</strong></span>
              <span>Formato: <strong>{model.format || 'Safetensors'}</strong></span>
              <span>VRAM Richiesta: <strong>~{model.est_vram_gb || 60} GB</strong></span>
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

              {deployedData.tiering_plan && (
                <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.70rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#00d2ff', fontWeight: 700 }}>
                    <span>⚡ GPU 0 (RTX 5070 Ti 16GB):</span>
                    <span>{deployedData.tiering_plan.tier0_primary_vram?.count || 16} Layer (~{deployedData.tiering_plan.tier0_primary_vram?.estimated_memory_gb || 12.9} GB VRAM)</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#bc8cff', fontWeight: 700 }}>
                    <span>⚡ GPU 1 (RTX 5060 8GB):</span>
                    <span>{deployedData.tiering_plan.tier1_secondary_vram?.count || 7} Layer (~{deployedData.tiering_plan.tier1_secondary_vram?.estimated_memory_gb || 5.7} GB VRAM)</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#10b981', fontWeight: 700 }}>
                    <span>💾 Host System RAM (94GB):</span>
                    <span>{deployedData.tiering_plan.tier2_host_ram?.count || 41} Layer (~{deployedData.tiering_plan.tier2_host_ram?.estimated_memory_gb || 33.2} GB RAM)</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '8px' }}>
                PIANO DI PARTIZIONAMENTO SALIENCY TIERING (AILOFLOW)
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Zap size={15} color="#00d2ff" />
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>GPU 0: NVIDIA RTX 5070 Ti (16 GB)</span>
                  </div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#00d2ff' }}>Tier 0 • Layer Primari (~13 GB)</span>
                </div>

                <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Zap size={15} color="#bc8cff" />
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>GPU 1: NVIDIA RTX 5060 (8 GB)</span>
                  </div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#bc8cff' }}>Tier 1 • Layer Secondari (~6 GB)</span>
                </div>

                <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <HardDrive size={15} color="#10b981" />
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>RAM di Sistema (94 GB Host)</span>
                  </div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#10b981' }}>Tier 2 • MoE Routing & Layer Restanti (~33 GB)</span>
                </div>
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
