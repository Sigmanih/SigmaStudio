import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Activity, Zap, HardDrive, Save, 
  ShieldCheck, Sliders, Play, Pause, TrendingUp,
  Cpu, Thermometer, Flame, Gauge
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import '../../styles/hardware-lab.css';

const MAX_HISTORY = 900; // ~30 minutes at 2s intervals

export default function HardwareLab({ addToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  
  // History buffers per GPU index
  const [historyData, setHistoryData] = useState({});
  const historyRef = useRef({});
  const initialConfigLoadedRef = useRef(false);

  const [cudaDevices, setCudaDevices] = useState('0,1');
  const [numParallel, setNumParallel] = useState(4);
  const [maxLoaded, setMaxLoaded] = useState(2);
  const [numGpuLayers, setNumGpuLayers] = useState(-1);
  const [preferredGpu, setPreferredGpu] = useState('cuda:0');
  const [fp16Enabled, setFp16Enabled] = useState(true);

  const fetchHardwareStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/hardware/status');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setData(json);
          // Accumulate history safely for each GPU
          const gpus = json.hardware?.gpu || [];
          const currentHist = { ...historyRef.current };

          gpus.forEach(gpu => {
            const idx = gpu.index;
            const existing = currentHist[idx] || { vram: [], compute: [], temp: [], power: [] };

            const vramVal = Number(gpu.vram_used_mb) || 0;
            const computeVal = Number(gpu.gpu_util_pct) || 0;
            const tempVal = Number(gpu.temp_c) || 0;
            const powerVal = Number(gpu.power_draw_w) || 0;

            const newVram = [...existing.vram, vramVal];
            const newCompute = [...existing.compute, computeVal];
            const newTemp = [...existing.temp, tempVal];
            const newPower = [...existing.power, powerVal];

            if (newVram.length > MAX_HISTORY) newVram.shift();
            if (newCompute.length > MAX_HISTORY) newCompute.shift();
            if (newTemp.length > MAX_HISTORY) newTemp.shift();
            if (newPower.length > MAX_HISTORY) newPower.shift();

            currentHist[idx] = {
              vram: newVram,
              compute: newCompute,
              temp: newTemp,
              power: newPower
            };
          });

          historyRef.current = currentHist;
          setHistoryData(currentHist);

          // Populate initial configuration fields once
          if (!initialConfigLoadedRef.current) {
            initialConfigLoadedRef.current = true;
            const cfg = json.config || {};
            if (cfg.cuda_visible_devices !== undefined) setCudaDevices(cfg.cuda_visible_devices);
            if (cfg.ollama_num_parallel !== undefined) setNumParallel(cfg.ollama_num_parallel);
            if (cfg.ollama_max_loaded_models !== undefined) setMaxLoaded(cfg.ollama_max_loaded_models);
            if (cfg.num_gpu_layers !== undefined) setNumGpuLayers(cfg.num_gpu_layers);
            if (cfg.preferred_training_gpu !== undefined) setPreferredGpu(cfg.preferred_training_gpu);
            if (cfg.fp16_enabled !== undefined) setFp16Enabled(cfg.fp16_enabled);
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch hardware status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHardwareStatus();
    if (!autoRefresh) return;
    const interval = setInterval(fetchHardwareStatus, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchHardwareStatus, autoRefresh, refreshInterval]);

  const handleSaveConfig = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/hardware/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cuda_visible_devices: cudaDevices,
          ollama_num_parallel: Number(numParallel),
          ollama_max_loaded_models: Number(maxLoaded),
          num_gpu_layers: Number(numGpuLayers),
          preferred_training_gpu: preferredGpu,
          fp16_enabled: fp16Enabled
        })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⚡ Impostazioni Multi-GPU salvate ed applicate con successo!', 'success', 4000);
        fetchHardwareStatus();
      } else {
        if (addToast) addToast(`❌ Errore salvataggio: ${json.error}`, 'error', 5000);
      }
    } catch (err) {
      if (addToast) addToast(`❌ Errore di rete: ${err.message}`, 'error', 5000);
    } finally {
      setSaving(false);
    }
  };

  const hw = data?.hardware || {};
  const gpus = hw.gpu || [];
  const history = historyData;

  const totalVramGb = hw.multi_gpu?.total_vram_gb || (gpus.reduce((acc, g) => acc + (g.vram_total_gb || 0), 0)).toFixed(1);

  return (
    <div className="hardware-lab-container">
      {/* Top Header */}
      <div className="hardware-header">
        <div className="hardware-header-title">
          <div className="hardware-header-icon">
            <Zap size={24} color="#00f2fe" />
          </div>
          <div>
            <h1>Hardware & Multi-GPU Lab</h1>
            <div className="hardware-header-subtitle">
              <span>Monitoraggio real-time con grafici ad alta definizione</span>
              <span>•</span>
              <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>{gpus.length} GPU Attive ({totalVramGb} GB VRAM Totali)</span>
            </div>
          </div>
        </div>

        <div className="hardware-header-actions">
          <span className={`hw-badge ${autoRefresh ? 'hw-badge-live' : ''}`}>
            <span className="hw-badge-dot" />
            {autoRefresh ? 'FEED LIVE ON (2s)' : 'PAUSA'}
          </span>
          <button 
            className="hw-btn" 
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Metti in pausa il refresh' : 'Riprendi refresh automatico'}
          >
            {autoRefresh ? <Pause size={14} color="#00f2fe" /> : <Play size={14} />}
            {autoRefresh ? 'Pausa' : 'Riprendi'}
          </button>
        </div>
      </div>

      {/* Main GPU Cards Grid */}
      <div className="gpu-cards-container">
        {gpus.length === 0 ? (
          <div className="gpu-card" style={{ textAlign: 'center', padding: '60px 20px' }}>
            {loading ? (
              <>
                <Activity className="spin" size={36} color="#00f2fe" style={{ margin: '0 auto 16px' }} />
                <div style={{ fontSize: '15px', fontWeight: 600 }}>Inizializzazione telemetria GPU da nvidia-smi / PyTorch...</div>
              </>
            ) : (
              <div style={{ color: '#94a3b8', fontSize: '14px' }}>
                ⚠️ Nessuna GPU NVIDIA rilevata o runtime CUDA non disponibile.
              </div>
            )}
          </div>
        ) : (
          gpus.map((gpu) => {
            const vramTotal = Number(gpu.vram_total_mb) || 1;
            const vramUsed = Number(gpu.vram_used_mb) || 0;
            const vramPct = vramTotal > 0 ? Math.min(100, Math.round((vramUsed / vramTotal) * 100)) : 0;
            const utilPct = Math.min(100, Math.round(Number(gpu.gpu_util_pct) || 0));
            const pwrLimit = Number(gpu.power_limit_w) || 0;
            const pwrDraw = Number(gpu.power_draw_w) || 0;
            const pwrPct = pwrLimit > 0 ? Math.min(100, Math.round((pwrDraw / pwrLimit) * 100)) : 0;

            const idx = gpu.index;
            const hist = history[idx] || { vram: [], compute: [], temp: [], power: [] };

            return (
              <div key={idx} className="gpu-card">
                {/* GPU Card Top Title Bar */}
                <div className="gpu-card-header">
                  <div className="gpu-title">
                    <div className="gpu-index-pill">GPU {idx}</div>
                    <div>
                      <div className="gpu-name">{gpu.name}</div>
                      <div className="gpu-bus-info">
                        Driver v{gpu.driver_version || 'N/A'} • PCIe Gen{gpu.pcie_gen || '?'} x{gpu.pcie_width || '?'} • Compute Cap {gpu.compute_cap || 'v9.0+'}
                      </div>
                    </div>
                  </div>

                  <div className="gpu-header-badges">
                    <div className="gpu-stat-badge">
                      <Thermometer size={14} color="#ffb86c" />
                      <span>{gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'}</span>
                    </div>
                    <div className="gpu-stat-badge">
                      <Flame size={14} color="#ff5555" />
                      <span>{pwrDraw}W / {pwrLimit > 0 ? `${pwrLimit}W` : 'N/A'}</span>
                    </div>
                    <span className="hw-badge" style={{ 
                      background: utilPct > 80 ? 'rgba(239,68,68,0.15)' : 'rgba(0,242,254,0.15)', 
                      color: utilPct > 80 ? '#ef4444' : '#00f2fe',
                      borderColor: utilPct > 80 ? 'rgba(239,68,68,0.3)' : 'rgba(0,242,254,0.3)'
                    }}>
                      <Gauge size={14} />
                      {utilPct}% Utilizzo Compute
                    </span>
                  </div>
                </div>

                {/* Instant Metrics Progress Gauges */}
                <div className="gpu-metrics-grid">
                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span className="metric-label-title"><HardDrive size={12} color="#00d2ff" /> Memoria VRAM</span>
                      <span className="metric-label-value" style={{ color: '#00d2ff' }}>{vramUsed} MB / {vramTotal} MB ({gpu.vram_total_gb || (vramTotal / 1024).toFixed(1)} GB)</span>
                    </div>
                    <div className="metric-progress-track">
                      <div className="metric-progress-bar bar-cyan" style={{ width: `${vramPct}%` }} />
                    </div>
                  </div>

                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span className="metric-label-title"><Cpu size={12} color="#bc8cff" /> Carico Compute</span>
                      <span className="metric-label-value" style={{ color: '#bc8cff' }}>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track">
                      <div className="metric-progress-bar bar-purple" style={{ width: `${utilPct}%` }} />
                    </div>
                  </div>

                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span className="metric-label-title"><Zap size={12} color="#ffb86c" /> Potenza assorbita</span>
                      <span className="metric-label-value" style={{ color: '#ffb86c' }}>{pwrDraw}W ({pwrPct}%)</span>
                    </div>
                    <div className="metric-progress-track">
                      <div className="metric-progress-bar bar-amber" style={{ width: `${pwrPct}%` }} />
                    </div>
                  </div>
                </div>

                {/* Dedicated Realtime Telemetry Charts Section */}
                <div style={{ marginTop: '8px' }}>
                  <div className="charts-section-header">
                    <div className="charts-section-title">
                      <TrendingUp size={14} color="#00f2fe" />
                      <span>Grafici Storici in Tempo Reale (Avvio ~30 min)</span>
                    </div>
                  </div>

                  {/* Primary 2-Column Hero Charts: VRAM & Compute */}
                  <div className="charts-grid-main">
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="Occupazione VRAM nel tempo" 
                      icon={HardDrive}
                      color="#00d2ff" 
                      unit="MB" 
                      maxVal={vramTotal} 
                      formatVal={(val) => `${typeof val === 'number' ? Math.round(val) : val}`}
                    />

                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Utilizzo Compute GPU nel tempo" 
                      icon={Cpu}
                      color="#bc8cff" 
                      unit="%" 
                      maxVal={100} 
                    />
                  </div>

                  {/* Secondary 2-Column Sparklines: Temperature & Power */}
                  <div className="charts-grid-secondary">
                    <RealtimeTelemetryChart 
                      data={hist.temp} 
                      label="Temperatura GPU nel tempo" 
                      icon={Thermometer}
                      color="#ffb86c" 
                      unit="°C" 
                      maxVal={100} 
                    />

                    <RealtimeTelemetryChart 
                      data={hist.power} 
                      label="Potenza Assorbita nel tempo" 
                      icon={Zap}
                      color="#ff5555" 
                      unit="W" 
                      maxVal={pwrLimit || 300} 
                    />
                  </div>
                </div>

              </div>
            );
          })
        )}
      </div>

      {/* Multi-GPU Tuning & Ollama Configuration */}
      <div className="hw-section">
        <div className="hw-section-title">
          <Sliders size={20} color="#00f2fe" />
          <span>Configurazione Multi-GPU & Parallelismo Ollama</span>
        </div>

        <div className="hw-form-grid">
          <div className="hw-form-group">
            <label>
              <span>CUDA_VISIBLE_DEVICES</span>
              <span style={{ color: '#00f2fe' }}>Ollama / PyTorch Target</span>
            </label>
            <select className="hw-select" value={cudaDevices} onChange={(e) => setCudaDevices(e.target.value)}>
              <option value="0,1">0,1 — Parallelismo su entrambe le GPU (RTX 5070 Ti + RTX 5060)</option>
              <option value="0">0 — Solo GPU 0 (RTX 5070 Ti - 16GB VRAM)</option>
              <option value="1">1 — Solo GPU 1 (RTX 5060 - 8GB VRAM)</option>
            </select>
            <div className="hw-help-text">
              Definisce quali GPU sono visibili ai modelli AI per l'inferenza e il training.
            </div>
          </div>

          <div className="hw-form-group">
            <label>
              <span>OLLAMA_NUM_PARALLEL</span>
              <span style={{ color: '#00f2fe' }}>Slot Richieste Simultanee</span>
            </label>
            <select className="hw-select" value={numParallel} onChange={(e) => setNumParallel(Number(e.target.value))}>
              <option value={1}>1 — Singolo stream</option>
              <option value={2}>2 — 2 stream paralleli</option>
              <option value={4}>4 — 4 stream paralleli (Ottimale per Multi-Agenti)</option>
              <option value={8}>8 — 8 stream paralleli (Massimo throughput)</option>
            </select>
            <div className="hw-help-text">
              Richieste di inferenza simultanee che Ollama può elaborare in parallelo.
            </div>
          </div>

          <div className="hw-form-group">
            <label>
              <span>OLLAMA_MAX_LOADED_MODELS</span>
              <span style={{ color: '#00f2fe' }}>Modelli in VRAM</span>
            </label>
            <select className="hw-select" value={maxLoaded} onChange={(e) => setMaxLoaded(Number(e.target.value))}>
              <option value={1}>1 modello alla volta</option>
              <option value={2}>2 modelli contemporaneamente (Consigliato)</option>
              <option value={3}>3 modelli contemporaneamente</option>
              <option value={4}>4 modelli contemporaneamente</option>
            </select>
            <div className="hw-help-text">
              Modelli mantenuti contemporaneamente in VRAM senza swap su disco.
            </div>
          </div>

          <div className="hw-form-group">
            <label>
              <span>GPU Preferita Training Lab</span>
              <span style={{ color: '#00f2fe' }}>Fine-Tuning Target</span>
            </label>
            <select className="hw-select" value={preferredGpu} onChange={(e) => setPreferredGpu(e.target.value)}>
              <option value="cuda:0">cuda:0 (RTX 5070 Ti — 16GB VRAM)</option>
              <option value="cuda:1">cuda:1 (RTX 5060 — 8GB VRAM)</option>
              <option value="cuda:0,1">cuda:0,1 (DataParallel Dual-GPU)</option>
            </select>
            <div className="hw-help-text">
              Scheda target predefinita per job di fine-tuning PyTorch / Unsloth.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button className="hw-btn hw-btn-primary" onClick={handleSaveConfig} disabled={saving}>
            <Save size={16} />
            {saving ? 'Salvataggio in corso...' : 'Applica e Salva Impostazioni Multi-GPU'}
          </button>
        </div>
      </div>

    </div>
  );
}