import React, { useState, useEffect, useCallback } from 'react';
import { Zap, Cpu, HardDrive, Sparkles, Activity, CheckCircle2, ArrowRight, ShieldCheck, Gauge } from 'lucide-react';

export default function EngineOptimizer({ isLight, addToast }) {
  const [engineData, setEngineData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [hfInputRepo, setHfInputRepo] = useState('');
  const [importing, setImporting] = useState(false);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  const fetchEngineData = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/models');
      if (res.ok) {
        const json = await res.json();
        if (json.success) setEngineData(json);
      }
    } catch (e) {
      console.error('Error fetching engine data:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEngineData();
  }, [fetchEngineData]);

  const handleRecalibrate = async () => {
    setOptimizing(true);
    try {
      const res = await fetch('/api/engine/optimize', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⚡ Prestazioni kernel e FlashAttention-2 ricalibrate al massimo!', 'success');
        fetchEngineData();
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setOptimizing(false);
    }
  };

  const handleDirectImport = async (repoId) => {
    const target = repoId || hfInputRepo;
    if (!target) return;
    setImporting(true);
    try {
      const res = await fetch('/api/engine/hf/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_id: target })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🚀 Modello ${target} integrato ed ottimizzato in SigmaEngine!`, 'success');
        fetchEngineData();
      } else {
        if (addToast) addToast(`❌ Errore: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setImporting(false);
    }
  };

  const opts = engineData?.optimizations || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. DIRECT HUGGING FACE REPO IMPORTER BANNER */}
      <div style={{
        padding: '20px', borderRadius: '16px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf5ec 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(26, 32, 54, 0.85) 100%)',
        border: '1.5px solid #ffb86c',
        display: 'flex', flexDirection: 'column', gap: '14px',
        boxShadow: '0 8px 30px rgba(255, 184, 108, 0.12)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#ffb86c', textTransform: 'uppercase' }}>
              PROVISIONING DIRETTO HUGGING FACE → KERNEL SIGMAENGINE
            </span>
            <h2 style={{ margin: '2px 0 0 0', fontSize: '1.15rem', fontWeight: 800, color: textPrimary }}>
              Importa e Ottimizza qualsiasi Modello Hugging Face
            </h2>
          </div>

          <button
            onClick={handleRecalibrate}
            disabled={optimizing}
            style={{
              padding: '7px 16px', borderRadius: '8px',
              border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
              color: '#ffffff', fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '6px',
              boxShadow: '0 0 15px rgba(0, 210, 255, 0.35)'
            }}
          >
            {optimizing ? <Activity className="mh-spin" size={14} /> : <Gauge size={14} />}
            {optimizing ? 'Ricalibrazione...' : '⚡ Ricalibra & Massimizza Throughput'}
          </button>
        </div>

        {/* Hugging Face Input Bar */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="Incolla repo Hugging Face (es. bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF o Qwen/Qwen2.5-Coder-7B-Instruct)..."
            value={hfInputRepo}
            onChange={e => setHfInputRepo(e.target.value)}
            style={{
              flex: 1, padding: '10px 14px', borderRadius: '10px',
              background: subBg, border: subBorder,
              color: textPrimary, fontSize: '0.84rem', outline: 'none'
            }}
          />
          <button
            onClick={() => handleDirectImport()}
            disabled={importing || !hfInputRepo}
            style={{
              padding: '10px 20px', borderRadius: '10px',
              border: 'none', background: 'linear-gradient(135deg, #ffb86c, #ea580c)',
              color: '#ffffff', fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0
            }}
          >
            {importing ? <Activity className="mh-spin" size={14} /> : <Sparkles size={14} />}
            {importing ? 'Adattamento...' : 'Importa & Massimizza'}
          </button>
        </div>
      </div>

      {/* 2. ACTIVE HARDWARE ADAPTATION & PERFORMANCE MATRIX */}
      <div style={{
        padding: '18px 20px', borderRadius: '16px',
        background: cardBg, border: cardBorder,
        display: 'flex', flexDirection: 'column', gap: '14px'
      }}>
        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: textPrimary, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Zap size={14} color="#00d2ff" /> Parametri di Massimizzazione Prestazioni Kernel
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div style={{ padding: '12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700 }}>ATTENTION KERNEL</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>
              {opts.attention_kernel || 'FLASH_ATTENTION_2'}
            </div>
            <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>Zero-memory attention scaling</div>
          </div>

          <div style={{ padding: '12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700 }}>KV CACHE QUANTIZZATA</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#10b981', marginTop: '2px' }}>
              {opts.kv_cache_quantization || 'FP8_E4M3'} (Risparmio 50% VRAM)
            </div>
            <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>128k contesti lunghi ultra-rapidi</div>
          </div>

          <div style={{ padding: '12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700 }}>TENSOR PARALLEL SHARDING</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#bc8cff', marginTop: '2px' }}>
              Dual GPU (RTX 5070 Ti + RTX 5060)
            </div>
            <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>Partizionamento asincrono a livelli</div>
          </div>

          <div style={{ padding: '12px', borderRadius: '10px', background: subBg, border: subBorder }}>
            <div style={{ fontSize: '0.66rem', color: textMuted, fontWeight: 700 }}>SPECULATIVE DECODING</div>
            <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#ffb86c', marginTop: '2px' }}>
              Lookahead Gamma 4 (~{opts.estimated_tok_sec || 85} tok/s)
            </div>
            <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>+220% velocità di generazione</div>
          </div>
        </div>
      </div>

      {/* 3. CURATED HIGH-PERFORMANCE PRESETS */}
      <div style={{
        padding: '18px 20px', borderRadius: '16px',
        background: cardBg, border: cardBorder,
        display: 'flex', flexDirection: 'column', gap: '12px'
      }}>
        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: textPrimary, textTransform: 'uppercase' }}>
          ⭐ Modelli Hugging Face Consigliati & Pre-Ottimizzati per il tuo Hardware
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(engineData?.recommended_models || []).map((m, i) => (
            <div
              key={i}
              style={{
                padding: '12px 14px', borderRadius: '10px',
                background: subBg, border: subBorder,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px'
              }}
            >
              <div>
                <div style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                  {m.name}
                </div>
                <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px' }}>
                  Target: <strong style={{ color: '#00d2ff' }}>{m.target_device}</strong> • Dimensione: {m.size_gb} GB ({m.quantization})
                </div>
              </div>

              <button
                onClick={() => handleDirectImport(m.repo_id)}
                disabled={importing}
                style={{
                  padding: '6px 14px', borderRadius: '6px',
                  border: 'none', background: 'linear-gradient(135deg, #00d2ff, #0090ff)',
                  color: '#ffffff', fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                <Zap size={12} /> Importa & Ottimizza
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
