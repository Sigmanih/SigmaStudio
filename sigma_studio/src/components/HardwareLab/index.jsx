import React, { useState, useEffect, useCallback } from 'react';
import { 
  Cpu, Activity, Zap, HardDrive, RefreshCw, Save, CheckCircle2, 
  AlertCircle, Server, Layers, ShieldCheck, Sliders, Play, Pause
} from 'lucide-react';

export default function HardwareLab({ addToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);

  // Editable Form Config
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
          if (loading) {
            // Populate initial config values from backend
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
  }, [loading]);

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
  const processes = hw.processes || [];
  const multiGpu = hw.multi_gpu || {};

  return (
    <div className="hardware-lab-container">
      {/* Header */}
      <div className="hardware-header">
        <div className="hardware-header-title">
          <Zap size={26} color="#00f2fe" />
          <div>
            <h1>⚡ Hardware & Multi-GPU Monitor</h1>
            <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
              Ottimizzazione parallelismo per NVIDIA RTX 5070 Ti + RTX 5060 (24GB VRAM)
            </div>
          </div>
        </div>

        <div className="hardware-header-actions">
          <span className="hw-badge">
            <ShieldCheck size={14} />
            {gpus.length > 0 ? `${gpus.length} GPU Attive` : 'Rilevamento...'}
          </span>
          <button 
            className="hw-btn" 
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Pausa aggiornamento automatico' : 'Riprendi aggiornamento automatico'}
          >
            {autoRefresh ? <Pause size={14} color="#00f2fe" /> : <Play size={14} />}
            {autoRefresh ? 'Live ON' : 'Pausa'}
          </button>
          <button className="hw-btn" onClick={fetchHardwareStatus} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            Aggiorna
          </button>
        </div>
      </div>

      {/* GPU Cards Grid */}
      <div className="gpu-cards-grid">
        {gpus.length === 0 ? (
          <div className="gpu-card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px' }}>
            <Activity className="spin" size={32} color="#00f2fe" style={{ margin: '0 auto 12px' }} />
            <div>Lettura telemetria GPU da nvidia-smi...</div>
          </div>
        ) : (
          gpus.map((gpu) => {
            const vramPct = gpu.vram_total_mb > 0 
              ? Math.min(100, Math.round((gpu.vram_used_mb / gpu.vram_total_mb) * 100))
              : 0;
            const utilPct = Math.min(100, Math.round(gpu.gpu_util_pct || 0));
            const pwrPct = gpu.power_limit_w > 0 
              ? Math.min(100, Math.round((gpu.power_draw_w / gpu.power_limit_w) * 100))
              : 0;

            return (
              <div key={gpu.index} className="gpu-card">
                <div className="gpu-card-header">
                  <div className="gpu-title">
                    <div className="gpu-index-pill">GPU {gpu.index}</div>
                    <div>
                      <div className="gpu-name">{gpu.name}</div>
                      <div className="gpu-bus-info">Driver v{gpu.driver_version} • PCIe Gen{gpu.pcie_gen} x{gpu.pcie_width}</div>
                    </div>
                  </div>
                  <span className="hw-badge" style={{ background: utilPct > 80 ? 'rgba(239,68,68,0.15)' : 'rgba(0,242,254,0.15)', color: utilPct > 80 ? '#ef4444' : '#00f2fe' }}>
                    {utilPct}% Utilizzo
                  </span>
                </div>

                {/* Progress Gauges */}
                <div className="gpu-metrics">
                  {/* VRAM Bar */}
                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span>VRAM Occupata</span>
                      <span>{gpu.vram_used_mb} MB / {gpu.vram_total_mb} MB ({gpu.vram_total_gb} GB)</span>
                    </div>
                    <div className="metric-progress-track">
                      <div 
                        className="metric-progress-bar bar-cyan" 
                        style={{ width: `${vramPct}%` }} 
                      />
                    </div>
                  </div>

                  {/* GPU Util Bar */}
                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span>Carico GPU (Compute)</span>
                      <span>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track">
                      <div 
                        className="metric-progress-bar bar-purple" 
                        style={{ width: `${utilPct}%` }} 
                      />
                    </div>
                  </div>

                  {/* Power Draw Bar */}
                  <div className="metric-row">
                    <div className="metric-label-row">
                      <span>Consumo Elettrico</span>
                      <span>{gpu.power_draw_w}W / {gpu.power_limit_w}W</span>
                    </div>
                    <div className="metric-progress-track">
                      <div 
                        className="metric-progress-bar bar-amber" 
                        style={{ width: `${pwrPct}%` }} 
                      />
                    </div>
                  </div>
                </div>

                {/* Mini Stats Grid */}
                <div className="gpu-stats-mini">
                  <div className="stat-item">
                    <span className="stat-label">Temperatura</span>
                    <span className="stat-value">{gpu.temp_c}°C</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">VRAM Libera</span>
                    <span className="stat-value">{gpu.vram_free_gb} GB</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Compute Cap</span>
                    <span className="stat-value">{gpu.compute_cap || 'v9.0+'}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Multi-GPU Tuning Controls */}
      <div className="hw-section">
        <div className="hw-section-title">
          <Sliders size={20} color="#00f2fe" />
          <span>Configurazione Multi-GPU & Parallelismo Ollama</span>
        </div>

        <div className="hw-form-grid">
          {/* CUDA Visible Devices */}
          <div className="hw-form-group">
            <label>
              <span>CUDA_VISIBLE_DEVICES</span>
              <span style={{ color: '#00f2fe' }}>Ollama / PyTorch Target</span>
            </label>
            <select 
              className="hw-select"
              value={cudaDevices}
              onChange={(e) => setCudaDevices(e.target.value)}
            >
              <option value="0,1">0,1 — Parallelismo su entrambe le GPU (RTX 5070 Ti + RTX 5060)</option>
              <option value="0">0 — Solo GPU 0 (RTX 5070 Ti - 16GB VRAM)</option>
              <option value="1">1 — Solo GPU 1 (RTX 5060 - 8GB VRAM)</option>
            </select>
            <div className="hw-help-text">
              Definisce quali GPU sono visibili ai modelli. L'opzione "0,1" distribuisce automaticamente i layer dei modelli su 24.5 GB di VRAM combinata.
            </div>
          </div>

          {/* OLLAMA_NUM_PARALLEL */}
          <div className="hw-form-group">
            <label>
              <span>OLLAMA_NUM_PARALLEL</span>
              <span style={{ color: '#00f2fe' }}>Slot Richieste Simultanee</span>
            </label>
            <select 
              className="hw-select"
              value={numParallel}
              onChange={(e) => setNumParallel(Number(e.target.value))}
            >
              <option value={1}>1 — Singolo stream (massima velocità per 1 utente)</option>
              <option value={2}>2 — 2 stream paralleli</option>
              <option value={4}>4 — 4 stream paralleli (Ottimale per Multi-Agenti)</option>
              <option value={8}>8 — 8 stream paralleli (Massimo throughput)</option>
            </select>
            <div className="hw-help-text">
              Numero di agenti/richieste che Ollama può elaborare in parallelo contemporaneamente sfruttando la VRAM delle 2 GPU.
            </div>
          </div>

          {/* OLLAMA_MAX_LOADED_MODELS */}
          <div className="hw-form-group">
            <label>
              <span>OLLAMA_MAX_LOADED_MODELS</span>
              <span style={{ color: '#00f2fe' }}>Modelli in VRAM</span>
            </label>
            <select 
              className="hw-select"
              value={maxLoaded}
              onChange={(e) => setMaxLoaded(Number(e.target.value))}
            >
              <option value={1}>1 modello alla volta in VRAM</option>
              <option value={2}>2 modelli contemporaneamente in VRAM (Consigliato)</option>
              <option value={3}>3 modelli contemporaneamente in VRAM</option>
              <option value={4}>4 modelli contemporaneamente in VRAM</option>
            </select>
            <div className="hw-help-text">
              Mantiene più modelli caricati contemporaneamente in VRAM senza ricaricarli ad ogni cambio di agente.
            </div>
          </div>

          {/* Training Lab GPU target */}
          <div className="hw-form-group">
            <label>
              <span>GPU Preferita Training Lab</span>
              <span style={{ color: '#00f2fe' }}>Fine-Tuning Target</span>
            </label>
            <select 
              className="hw-select"
              value={preferredGpu}
              onChange={(e) => setPreferredGpu(e.target.value)}
            >
              <option value="cuda:0">cuda:0 (RTX 5070 Ti — 16GB VRAM)</option>
              <option value="cuda:1">cuda:1 (RTX 5060 — 8GB VRAM)</option>
              <option value="cuda:0,1">cuda:0,1 (DataParallel Dual-GPU)</option>
            </select>
            <div className="hw-help-text">
              Seleziona quale scheda utilizzare per i job di training/fine-tuning in PyTorch.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
          <button 
            className="hw-btn hw-btn-primary" 
            onClick={handleSaveConfig}
            disabled={saving}
          >
            <Save size={16} />
            {saving ? 'Salvataggio...' : 'Applica e Salva Impostazioni Multi-GPU'}
          </button>
        </div>
      </div>

      {/* Active GPU Processes */}
      <div className="hw-section">
        <div className="hw-section-title">
          <Activity size={20} color="#00f2fe" />
          <span>Processi Attivi in Memoria GPU (Ollama & Sistema)</span>
        </div>

        {processes.length === 0 ? (
          <div style={{ color: '#94a3b8', fontSize: '13px', fontStyle: 'italic', padding: '10px 0' }}>
            Nessun processo compute aggiuntivo o nessun processo registrato da nvidia-smi.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="proc-table">
              <thead>
                <tr>
                  <th>Bus ID / GPU</th>
                  <th>PID</th>
                  <th>Nome Processo</th>
                  <th>Percorso Eseguibile</th>
                  <th>VRAM Usata</th>
                </tr>
              </thead>
              <tbody>
                {processes.map((proc, idx) => (
                  <tr key={idx}>
                    <td>{proc.bus_id}</td>
                    <td className="proc-pid">{proc.pid}</td>
                    <td className="proc-name">{proc.process_name}</td>
                    <td style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace' }}>{proc.full_path}</td>
                    <td>{proc.used_memory_mb !== 'N/A' ? `${proc.used_memory_mb} MB` : 'In uso'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
