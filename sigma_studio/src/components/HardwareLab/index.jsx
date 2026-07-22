import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Activity, Zap, HardDrive, Save, ChevronDown, ChevronUp, RotateCcw, Trash2,
  ShieldCheck, Sliders, Play, Pause, TrendingUp, BarChart2,
  Cpu, Thermometer, Flame, Gauge, AlertTriangle
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
  const [showCharts, setShowCharts] = useState(false); // Collapsible charts
  const [showRestartAlert, setShowRestartAlert] = useState(false); // Alert modal
  const [restartingOllama, setRestartingOllama] = useState(false);

  // History buffers per GPU index & System (CPU/RAM)
  const [historyData, setHistoryData] = useState({});
  const historyRef = useRef({});
  const [systemHistory, setSystemHistory] = useState({ cpu: [], ram: [] });
  const systemHistoryRef = useRef({ cpu: [], ram: [] });

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

          // 1. Accumulate GPU history
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

          // 2. Accumulate System CPU & RAM History
          const cpuUtil = Number(json.hardware?.cpu?.util_pct) || 0;
          const ramUsed = Number(json.hardware?.ram?.used_gb) || Number(json.hardware?.ram_used_gb) || 0;

          const currentSysHist = { ...systemHistoryRef.current };
          const newCpu = [...(currentSysHist.cpu || []), cpuUtil];
          const newRam = [...(currentSysHist.ram || []), ramUsed];

          if (newCpu.length > MAX_HISTORY) newCpu.shift();
          if (newRam.length > MAX_HISTORY) newRam.shift();

          systemHistoryRef.current = { cpu: newCpu, ram: newRam };
          setSystemHistory({ cpu: newCpu, ram: newRam });

          // 3. Populate initial configuration fields once
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

  const handleRestartOllama = async () => {
    setRestartingOllama(true);
    try {
      const res = await fetch('/api/hardware/restart-ollama', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🧹 ${json.message}`, 'success', 5000);
        fetchHardwareStatus();
      } else {
        if (addToast) addToast(`❌ Errore riavvio: ${json.error}`, 'error', 5000);
      }
    } catch (err) {
      if (addToast) addToast(`❌ Errore di connessione: ${err.message}`, 'error', 5000);
    } finally {
      setRestartingOllama(false);
      setShowRestartAlert(false);
    }
  };

  const hw = data?.hardware || {};
  const gpus = hw.gpu || [];
  const history = historyData;

  const totalVramGb = hw.multi_gpu?.total_vram_gb || (gpus.reduce((acc, g) => acc + (g.vram_total_gb || 0), 0)).toFixed(1);

  return (
    <div className="hardware-lab-container" style={{ padding: '16px 20px', position: 'relative' }}>
      
      {/* CONFIRMATION ALERT MODAL FOR RESTART OLLAMA */}
      {showRestartAlert && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          zIndex: 10020,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px'
        }}>
          <div style={{
            maxWidth: '460px',
            width: '100%',
            background: 'rgba(15, 23, 42, 0.98)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '16px',
            padding: '22px',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 25px rgba(239, 68, 68, 0.2)',
            animation: 'slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '10px', borderRadius: '12px', display: 'flex' }}>
                <AlertTriangle size={24} color="#ef4444" />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: '#fff' }}>Riavvio & Pulizia VRAM Ollama</h3>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Svuotamento modelli caricati in memoria</div>
              </div>
            </div>

            <div style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '20px', background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '10px', borderLeft: '4px solid #ef4444' }}>
              ⚠️ <b>Confermi la pulizia della memoria?</b><br />
              Questa operazione scaricherà immediatamente tutti i modelli caricati da Ollama in VRAM/RAM e riavvierà il servizio di inferenza. Eventuali chat o task in corso verranno interrotti.
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button 
                className="hw-btn" 
                onClick={() => setShowRestartAlert(false)} 
                disabled={restartingOllama}
                style={{ fontSize: '13px', padding: '8px 16px' }}
              >
                Annulla
              </button>
              <button 
                className="hw-btn" 
                onClick={handleRestartOllama} 
                disabled={restartingOllama}
                style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', fontWeight: 700, fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {restartingOllama ? <Activity className="spin" size={15} /> : <RotateCcw size={15} />}
                {restartingOllama ? 'Svuotamento VRAM in corso...' : '⚡ Svuota VRAM & Riavvia Ollama'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Top Header */}
      <div className="hardware-header" style={{ marginBottom: '16px' }}>
        <div className="hardware-header-title">
          <div className="hardware-header-icon">
            <Zap size={22} color="#00f2fe" />
          </div>
          <div>
            <h1 style={{ fontSize: '20px' }}>Hardware & Multi-GPU Lab</h1>
            <div className="hardware-header-subtitle" style={{ fontSize: '12px' }}>
              <span>Telemetria in tempo reale</span>
              <span>•</span>
              <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                {gpus.length} GPU ({totalVramGb} GB VRAM) • RAM {hw.ram?.used_gb || 0}/{hw.ram?.total_gb || 0} GB
              </span>
            </div>
          </div>
        </div>

        <div className="hardware-header-actions" style={{ gap: '8px' }}>
          {/* RESTART OLLAMA BUTTON */}
          <button 
            className="hw-btn"
            onClick={() => setShowRestartAlert(true)}
            title="Svuota la memoria VRAM/RAM scaricando tutti i modelli caricati da Ollama"
            style={{ fontSize: '12px', padding: '6px 12px', border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.12)', color: '#fca5a5' }}
          >
            <RotateCcw size={14} color="#ef4444" />
            <span>Svuota VRAM / Riavvia Ollama</span>
          </button>

          <button 
            className={`hw-btn ${showCharts ? 'hw-btn-primary' : ''}`}
            onClick={() => setShowCharts(!showCharts)}
            title={showCharts ? 'Nascondi i grafici per compattare la vista' : 'Mostra i grafici storici in tempo reale'}
            style={{ fontSize: '12px', padding: '6px 12px' }}
          >
            <BarChart2 size={14} color={showCharts ? '#fff' : '#00f2fe'} />
            {showCharts ? 'Nascondi Grafici' : 'Mostra Grafici Storici'}
            {showCharts ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          <button 
            className="hw-btn" 
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Metti in pausa il refresh' : 'Riprendi refresh automatico'}
            style={{ fontSize: '12px', padding: '6px 12px' }}
          >
            {autoRefresh ? <Pause size={13} color="#00f2fe" /> : <Play size={13} />}
            {autoRefresh ? 'Pausa (2s)' : 'Riprendi'}
          </button>
        </div>
      </div>

      {/* Main Cards Container */}
      <div className="gpu-cards-container" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* ==================================================================== */}
        {/* SYSTEM OVERVIEW CARD (LEFT = COMPUTE, RIGHT = MEMORY) */}
        {/* ==================================================================== */}
        <div className="gpu-card" style={{ padding: '14px 18px', background: 'rgba(15, 23, 42, 0.75)' }}>
          <div className="gpu-card-header" style={{ marginBottom: '12px' }}>
            <div className="gpu-title">
              <div className="gpu-index-pill" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '2px 8px', fontSize: '11px' }}>
                SYS
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div className="gpu-name" style={{ fontSize: '15px' }}>Sistema Principale (CPU & RAM)</div>
                  <span className="hw-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)', fontSize: '10px', padding: '2px 8px' }}>
                    SISTEMA
                  </span>
                </div>
                <div className="gpu-bus-info" style={{ fontSize: '11px' }}>
                  {hw.cpu?.logical_count || hw.cpu_count || '?'} Thread Logici ({hw.cpu?.physical_count || '?'} Cores) • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
                </div>
              </div>
            </div>

            <div className="gpu-header-badges">
              <div className="gpu-stat-badge" style={{ padding: '4px 10px', fontSize: '12px' }}>
                <Cpu size={14} color="#00f2fe" />
                <span style={{ fontWeight: 700, color: '#00f2fe' }}>CPU: {hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="gpu-stat-badge" style={{ padding: '4px 10px', fontSize: '12px' }}>
                <HardDrive size={14} color="#10b981" />
                <span style={{ fontWeight: 700, color: '#10b981' }}>RAM: {hw.ram?.used_gb || hw.ram_used_gb || 0} / {hw.ram?.total_gb || hw.ram_gb || 0} GB</span>
              </div>
            </div>
          </div>

          {/* 2-COLUMN SPLIT: LEFT = COMPUTE, RIGHT = MEMORY */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            
            {/* LEFT SIDE: CPU COMPUTE */}
            <div style={{ background: 'rgba(0, 242, 254, 0.04)', border: '1px solid rgba(0, 242, 254, 0.15)', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '12px', color: '#00f2fe' }}>
                  <Cpu size={14} /> ⚡ COMPUTE (CPU System Load)
                </div>
                <span style={{ fontSize: '12px', fontWeight: 800, color: '#00f2fe' }}>{hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px' }}>
                <div className="metric-progress-bar bar-cyan" style={{ width: `${Math.min(100, hw.cpu?.util_pct ?? 0)}%` }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)' }}>
                <span>Max Core Load: {hw.cpu?.max_core_pct || 0}%</span>
                <span>Frequenza: {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(2)} GHz` : 'N/A'}</span>
              </div>
            </div>

            {/* RIGHT SIDE: MEMORY & STORAGE */}
            <div style={{ background: 'rgba(16, 185, 129, 0.04)', border: '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '10px', padding: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '12px', color: '#10b981' }}>
                  <HardDrive size={14} /> 🧠 MEMORIA (System RAM & Disco)
                </div>
                <span style={{ fontSize: '12px', fontWeight: 800, color: '#10b981' }}>{hw.ram?.util_pct || hw.ram_pct || 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px' }}>
                <div className="metric-progress-bar" style={{ width: `${Math.min(100, hw.ram?.util_pct || hw.ram_pct || 0)}%`, background: 'linear-gradient(90deg, #10b981, #059669)' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)' }}>
                <span>RAM Libera: {hw.ram?.free_gb || 0} GB</span>
                <span>Disco: {hw.disk?.used_gb || 0} / {hw.disk?.total_gb || 0} GB ({hw.disk?.util_pct || 0}%)</span>
              </div>
            </div>

          </div>

          {/* COLLAPSIBLE SYSTEM CHARTS */}
          {showCharts && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '14px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
              <RealtimeTelemetryChart 
                data={systemHistory.cpu} 
                label="Storico Carico CPU (%)" 
                icon={Cpu}
                color="#00f2fe" 
                unit="%" 
                maxVal={100} 
                height={80}
              />
              <RealtimeTelemetryChart 
                data={systemHistory.ram} 
                label="Storico RAM Utilizzata (GB)" 
                icon={HardDrive}
                color="#10b981" 
                unit="GB" 
                maxVal={hw.ram?.total_gb || hw.ram_gb || 64} 
                height={80}
                formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
              />
            </div>
          )}
        </div>

        {/* ==================================================================== */}
        {/* MULTI-VENDOR GPU CARDS (LEFT = COMPUTE, RIGHT = VRAM) */}
        {/* ==================================================================== */}
        {gpus.length === 0 ? (
          <div className="gpu-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
            {loading ? (
              <>
                <Activity className="spin" size={32} color="#00f2fe" style={{ margin: '0 auto 12px' }} />
                <div style={{ fontSize: '14px' }}>Rilevamento telemetria hardware in corso...</div>
              </>
            ) : (
              <div style={{ color: '#94a3b8', fontSize: '14px' }}>
                ⚠️ Nessuna GPU rilevata nel sistema.
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

            const idx = gpu.index;
            const hist = history[idx] || { vram: [], compute: [], temp: [], power: [] };

            return (
              <div key={idx} className="gpu-card" style={{ padding: '14px 18px', background: 'rgba(15, 23, 42, 0.75)' }}>
                {/* GPU Card Top Title Bar */}
                <div className="gpu-card-header" style={{ marginBottom: '12px' }}>
                  <div className="gpu-title">
                    <div className="gpu-index-pill" style={{ padding: '2px 8px', fontSize: '11px' }}>GPU {idx}</div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div className="gpu-name" style={{ fontSize: '15px' }}>{gpu.name}</div>
                        <span className="hw-badge" style={{ 
                          background: `${gpu.vendor_color || '#00f2fe'}18`, 
                          color: gpu.vendor_color || '#00f2fe',
                          borderColor: `${gpu.vendor_color || '#00f2fe'}44`,
                          fontSize: '10px',
                          padding: '2px 8px'
                        }}>
                          {gpu.vendor || 'GPU'}
                        </span>
                      </div>
                      <div className="gpu-bus-info" style={{ fontSize: '11px' }}>
                        Driver v{gpu.driver_version || 'N/A'} • Compute Cap {gpu.compute_cap || 'v9.0+'} • Temp {gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'} • Potenza {pwrDraw}W
                      </div>
                    </div>
                  </div>

                  <div className="gpu-header-badges">
                    <div className="gpu-stat-badge" style={{ padding: '4px 10px', fontSize: '12px' }}>
                      <Thermometer size={14} color="#ffb86c" />
                      <span>{gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'}</span>
                    </div>
                    <div className="gpu-stat-badge" style={{ padding: '4px 10px', fontSize: '12px' }}>
                      <Flame size={14} color="#ff5555" />
                      <span>{pwrDraw}W</span>
                    </div>
                  </div>
                </div>

                {/* 2-COLUMN SPLIT: LEFT = COMPUTE, RIGHT = VRAM */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  
                  {/* LEFT SIDE: GPU COMPUTE */}
                  <div style={{ background: 'rgba(188, 140, 255, 0.04)', border: '1px solid rgba(188, 140, 255, 0.18)', borderRadius: '10px', padding: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '12px', color: '#bc8cff' }}>
                        <Gauge size={14} /> ⚡ COMPUTE (Utilizzo GPU)
                      </div>
                      <span style={{ fontSize: '12px', fontWeight: 800, color: '#bc8cff' }}>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px' }}>
                      <div className="metric-progress-bar bar-purple" style={{ width: `${utilPct}%` }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)' }}>
                      <span>Stato: {utilPct > 80 ? '🔥 Alto Carico' : utilPct > 20 ? '⚡ Attivo' : '💤 Idle'}</span>
                      <span>Potenza: {pwrDraw}W / {pwrLimit > 0 ? `${pwrLimit}W` : 'N/A'}</span>
                    </div>
                  </div>

                  {/* RIGHT SIDE: GPU VRAM MEMORY */}
                  <div style={{ background: 'rgba(0, 210, 255, 0.04)', border: '1px solid rgba(0, 210, 255, 0.18)', borderRadius: '10px', padding: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '12px', color: '#00d2ff' }}>
                        <HardDrive size={14} /> 🧠 MEMORIA VRAM
                      </div>
                      <span style={{ fontSize: '12px', fontWeight: 800, color: '#00d2ff' }}>{vramUsed} / {vramTotal} MB ({vramPct}%)</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px' }}>
                      <div className="metric-progress-bar bar-cyan" style={{ width: `${vramPct}%` }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)' }}>
                      <span>Libera: {gpu.vram_free_mb || Math.max(0, vramTotal - vramUsed)} MB</span>
                      <span>VRAM Totale: {gpu.vram_total_gb || (vramTotal / 1024).toFixed(1)} GB</span>
                    </div>
                  </div>

                </div>

                {/* COLLAPSIBLE GPU CHARTS */}
                {showCharts && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '14px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Storico Compute GPU (%)" 
                      icon={Cpu}
                      color="#bc8cff" 
                      unit="%" 
                      maxVal={100} 
                      height={80}
                    />
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="Storico Occupazione VRAM (MB)" 
                      icon={HardDrive}
                      color="#00d2ff" 
                      unit="MB" 
                      maxVal={vramTotal} 
                      height={80}
                      formatVal={(val) => `${typeof val === 'number' ? Math.round(val) : val}`}
                    />
                  </div>
                )}

              </div>
            );
          })
        )}
      </div>

      {/* Multi-GPU Tuning Controls */}
      <div className="hw-section" style={{ marginTop: '16px' }}>
        <div className="hw-section-title">
          <Sliders size={18} color="#00f2fe" />
          <span style={{ fontSize: '15px' }}>Configurazione Multi-GPU & Parallelismo Ollama</span>
        </div>

        <div className="hw-form-grid">
          <div className="hw-form-group">
            <label>
              <span>CUDA_VISIBLE_DEVICES</span>
              <span style={{ color: '#00f2fe' }}>Target GPU</span>
            </label>
            <select className="hw-select" value={cudaDevices} onChange={(e) => setCudaDevices(e.target.value)}>
              <option value="0,1">0,1 — Parallelismo su entrambe le GPU (RTX 5070 Ti + RTX 5060)</option>
              <option value="0">0 — Solo GPU 0 (RTX 5070 Ti - 16GB VRAM)</option>
              <option value="1">1 — Solo GPU 1 (RTX 5060 - 8GB VRAM)</option>
            </select>
          </div>

          <div className="hw-form-group">
            <label>
              <span>OLLAMA_NUM_PARALLEL</span>
              <span style={{ color: '#00f2fe' }}>Slot Paralleli</span>
            </label>
            <select className="hw-select" value={numParallel} onChange={(e) => setNumParallel(Number(e.target.value))}>
              <option value={1}>1 — Singolo stream</option>
              <option value={2}>2 — 2 stream paralleli</option>
              <option value={4}>4 — 4 stream paralleli (Ottimale Multi-Agenti)</option>
              <option value={8}>8 — 8 stream paralleli (Massimo throughput)</option>
            </select>
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
            </select>
          </div>

          <div className="hw-form-group">
            <label>
              <span>GPU Preferita Training Lab</span>
              <span style={{ color: '#00f2fe' }}>Fine-Tuning</span>
            </label>
            <select className="hw-select" value={preferredGpu} onChange={(e) => setPreferredGpu(e.target.value)}>
              <option value="cuda:0">cuda:0 (RTX 5070 Ti — 16GB VRAM)</option>
              <option value="cuda:1">cuda:1 (RTX 5060 — 8GB VRAM)</option>
              <option value="cuda:0,1">cuda:0,1 (DataParallel Dual-GPU)</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
          <button className="hw-btn hw-btn-primary" onClick={handleSaveConfig} disabled={saving} style={{ fontSize: '13px', padding: '8px 16px' }}>
            <Save size={15} />
            {saving ? 'Salvataggio in corso...' : 'Applica e Salva Impostazioni Multi-GPU'}
          </button>
        </div>
      </div>

    </div>
  );
}