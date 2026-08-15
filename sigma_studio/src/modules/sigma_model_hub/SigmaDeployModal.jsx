import React, { useState } from 'react';
import { Zap, Cpu, HardDrive, CheckCircle2, X, Activity, Layers, ArrowRight } from 'lucide-react';

export default function SigmaDeployModal({ model, onClose, onDeployed, isLight, addToast }) {
  const [loading, setLoading] = useState(false);
  const [quant, setQuant] = useState(model.quantization || 'Q4_K_M');

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
          model_path: model.path || model.filename,
          quantization: quant
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`⚡ Modello ${model.filename || model.name} attivato in SigmaEngine!`, 'success');
        if (onDeployed) onDeployed(json);
        onClose();
      } else {
        if (addToast) addToast(`❌ Errore deploy: ${json.error}`, 'error');
      }
    } catch (err) {
      if (addToast) addToast(`❌ Errore di connessione: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
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
        maxWidth: '520px', width: '100%',
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
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Zap size={18} color="#00d2ff" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                Distribuzione in <span style={{ color: '#00d2ff' }}>SigmaEngine</span>
              </h2>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>
                Universal Inference & VRAM Sharding Tiering
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
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: textPrimary, marginTop: '2px' }}>
              {model.filename || model.name}
            </div>
            <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '4px', display: 'flex', gap: '12px' }}>
              <span>Dimensione: <strong>{model.size_gb || 4.5} GB</strong></span>
              <span>Formato: <strong>{model.format || 'GGUF'}</strong></span>
              <span>VRAM Richiesta: <strong>~{model.est_vram_gb || 6.0} GB</strong></span>
            </div>
          </div>

          {/* GPU Hardware Tiering Preview */}
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '8px' }}>
              PARTIZIONAMENTO HARDWARE DINAMICO
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Zap size={15} color="#00d2ff" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>GPU 0: NVIDIA RTX 5070 Ti (16 GB)</span>
                </div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#00d2ff' }}>Tier 0 • Layer Primari (100% VRAM)</span>
              </div>

              <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Zap size={15} color="#bc8cff" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>GPU 1: NVIDIA RTX 5060 (8 GB)</span>
                </div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#bc8cff' }}>Tier 1 • Layer Secondari / KV Cache</span>
              </div>

              <div style={{ padding: '10px 12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <HardDrive size={15} color="#10b981" />
                  <span style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>RAM di Sistema (94 GB Host)</span>
                </div>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#10b981' }}>Tier 2 • MoE Routing & Context Buffer</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '14px 20px',
          borderTop: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.3)'
        }}>
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
        </div>
      </div>
    </div>
  );
}
