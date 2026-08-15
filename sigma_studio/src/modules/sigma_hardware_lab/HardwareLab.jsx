import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Cpu, HardDrive, Zap, Sliders, RotateCcw, AlertTriangle,
  Play, Pause, ChevronDown, ChevronUp, Save, BarChart2,
  Trash2, ShieldCheck, Thermometer, Flame, Gauge, Sparkles,
  Layers, CheckCircle2, ArrowRight, Activity, Search, Terminal,
  RefreshCw, Info, X, Power, ShieldAlert
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';

const INACTIVE_HARDWARE_NODES = [
  {
    id: 'egpu_node',
    title: 'Cluster eGPU Thunderbolt / PCIe',
    subtitle: 'Espansione multi-scheda esterna per inferenza parallela e fine-tuning ad alto throughput.',
    icon: Zap,
    color: '#00d2ff',
    statusBadge: 'NON DISPONIBILE',
    prerequisite: 'Nessun modulo eGPU esterno rilevato sulla porta Thunderbolt / PCIe.',
    details: 'Permette di distribuire carichi pesanti (es. modelli 70B quantizzati o batch di embedding) su schede grafiche ausiliarie senza sovraccaricare la GPU primaria.',
    actionText: 'Non ancora disponibile'
  },
  {
    id: 'vllm_engine',
    title: 'vLLM PagedAttention Cluster',
    subtitle: 'Motore di inferenza avanzato a memoria paginata per token generation ultra-rapida.',
    icon: Activity,
    color: '#bc8cff',
    statusBadge: 'NON DISPONIBILE',
    prerequisite: 'Nessun server vLLM attivo rilevato sulla porta locale 8001.',
    details: 'Sostituisce il runtime standard con il protocollo vLLM, ottimizzando la frammentazione VRAM e triplicando la velocità di generazione sui prompt lunghi.',
    actionText: 'Non ancora disponibile'
  },
  {
    id: 'whisper_npu',
    title: 'Acceleratore Audio Whisper & NPU',
    subtitle: 'Trascrizione e sintesi vocale locale a latenza zero tramite NPU Intel/AMD o DirectML.',
    icon: Cpu,
    color: '#10b981',
    statusBadge: 'NON DISPONIBILE',
    prerequisite: 'Nessun chip NPU o acceleratore DirectML dedicato attivo nel sistema.',
    details: 'Sposta l\'elaborazione del parlato dall\'Ollama primario alla NPU a basso consumo, liberando il 100% della VRAM dedicata ai modelli di testo.',
    actionText: 'Non ancora disponibile'
  },
  {
    id: 'comfyui_worker',
    title: 'Nodo di Calcolo ComfyUI Creativo',
    subtitle: 'Cluster dedicato alla generazione di immagini SDXL e modelli 3D in background.',
    icon: Layers,
    color: '#ea580c',
    statusBadge: 'NON DISPONIBILE',
    prerequisite: 'Nessun worker ComfyUI in ascolto sulla porta 8188.',
    details: 'Permette di accodare render pesanti e pipeline di inpainting senza bloccare le sessioni di chat degli assistenti AI.',
    actionText: 'Non ancora disponibile'
  }
];

export default function HardwareLab({ addToast }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  const [showCharts, setShowCharts] = useState(true);
  const [showRestartAlert, setShowRestartAlert] = useState(false);
  const [restartingOllama, setRestartingOllama] = useState(false);

  // Standby hardware activation modal state
  const [activeHwModal, setActiveHwModal] = useState(null);
  const [activatingHw, setActivatingHw] = useState(null);
  const [activatedHw, setActivatedHw] = useState({});
  const [expandedHwNode, setExpandedHwNode] = useState(null);

  // GPU processes & Console filters
  const [gpuProcs, setGpuProcs] = useState({ processes: [], orfani: 0 });
  const [killingPid, setKillingPid] = useState(null);
  const [procSearch, setProcSearch] = useState('');
  const [procFilter, setProcFilter] = useState('all');
  const [expandedPid, setExpandedPid] = useState(null);

  // History buffers per GPU index & System
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

          // Accumulate GPU history
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

            if (newVram.length > 30) newVram.shift();
            if (newCompute.length > 30) newCompute.shift();
            if (newTemp.length > 30) newTemp.shift();
            if (newPower.length > 30) newPower.shift();

            currentHist[idx] = { vram: newVram, compute: newCompute, temp: newTemp, power: newPower };
          });

          historyRef.current = currentHist;
          setHistoryData(currentHist);

          // Accumulate System CPU/RAM history
          const cpuVal = Number(json.hardware?.cpu?.util_pct) || 0;
          const ramVal = Number(json.hardware?.ram?.util_pct || json.hardware?.ram_pct) || 0;

          const newSysCpu = [...systemHistoryRef.current.cpu, cpuVal];
          const newSysRam = [...systemHistoryRef.current.ram, ramVal];
          if (newSysCpu.length > 30) newSysCpu.shift();
          if (newSysRam.length > 30) newSysRam.shift();

          systemHistoryRef.current = { cpu: newSysCpu, ram: newSysRam };
          setSystemHistory({ cpu: newSysCpu, ram: newSysRam });

          // Load Multi-GPU config from backend on first load
          if (!initialConfigLoadedRef.current && json.hardware?.multi_gpu) {
            const mg = json.hardware.multi_gpu;
            if (mg.cuda_visible_devices !== undefined) setCudaDevices(String(mg.cuda_visible_devices));
            if (mg.ollama_num_parallel !== undefined) setNumParallel(mg.ollama_num_parallel);
            if (mg.ollama_max_loaded_models !== undefined) setMaxLoaded(mg.ollama_max_loaded_models);
            if (mg.num_gpu_layers !== undefined) setNumGpuLayers(mg.num_gpu_layers);
            if (mg.preferred_training_gpu !== undefined) setPreferredGpu(mg.preferred_training_gpu);
            if (mg.fp16_enabled !== undefined) setFp16Enabled(mg.fp16_enabled);
            initialConfigLoadedRef.current = true;
          }
        }
      }
    } catch (err) {
      console.error("Hardware status polling error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGpuProcesses = useCallback(async () => {
    try {
      const res = await fetch('/api/hardware/gpu/processes');
      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          setGpuProcs({
            processes: json.processes || [],
            orfani: json.orfani || 0,
          });
        }
      }
    } catch (e) {
      console.error("GPU processes fetch error:", e);
    }
  }, []);

  useEffect(() => {
    fetchHardwareStatus();
    fetchGpuProcesses();
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchHardwareStatus();
      fetchGpuProcesses();
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchHardwareStatus, fetchGpuProcesses, autoRefresh, refreshInterval]);

  const handleKillGpuProcess = async (proc) => {
    if (!proc || !proc.pid) return;
    setKillingPid(proc.pid);
    try {
      const res = await fetch('/api/hardware/gpu/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: proc.pid, job_id: proc.job_id || null })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(json.message || `Processo PID ${proc.pid} (${proc.name || 'GPU'}) terminato.`, 'success');
      } else if (addToast) {
        addToast(json.error || `Impossibile chiudere il processo ${proc.pid}.`, 'error');
      }
      fetchGpuProcesses();
      fetchHardwareStatus();
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setKillingPid(null);
    }
  };

  const handleKillAllOrphans = async () => {
    try {
      const res = await fetch('/api/hardware/gpu/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all_orphans: true })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(json.message || 'Processi orfani terminati con successo.', 'success');
      } else if (addToast) {
        addToast(json.error || 'Errore nella terminazione dei processi orfani.', 'error');
      }
      fetchGpuProcesses();
      fetchHardwareStatus();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    }
  };


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
        if (addToast) addToast('⚡ VRAM svuotata e Ollama riavviato con successo!', 'success');
        fetchHardwareStatus();
      } else {
        if (addToast) addToast(`Errore riavvio: ${json.error}`, 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setRestartingOllama(false);
      setShowRestartAlert(false);
    }
  };

  const handleClearVramMcp = async () => {
    try {
      const res = await fetch('/api/mcp/rpc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: 'clear-vram-mcp',
          method: 'tools/call',
          params: { name: 'clear_vram_cache', arguments: {} }
        })
      });
      if (res.ok) {
        if (addToast) addToast('Modelli Ollama scaricati dalla VRAM.', 'success');
        fetchHardwareStatus();
        fetchGpuProcesses();
      }
    } catch (e) {
      console.error("VRAM clear error via Hardware MCP:", e);
    }
  };

  const hw = data?.hardware || {};
  const gpus = hw.gpu || [];
  const totalVramGb = hw.multi_gpu?.total_vram_gb || (gpus.reduce((acc, g) => acc + (g.vram_total_gb || 0), 0)).toFixed(1);

  // Filtered processes in Console
  const filteredProcesses = useMemo(() => {
    return gpuProcs.processes.filter(p => {
      const matchSearch = !procSearch.trim() ||
        String(p.pid).includes(procSearch.trim()) ||
        p.name?.toLowerCase().includes(procSearch.toLowerCase().trim()) ||
        p.job_id?.toLowerCase().includes(procSearch.toLowerCase().trim());

      if (!matchSearch) return false;
      if (procFilter === 'all') return true;
      if (procFilter === 'training') return p.kind === 'training';
      if (procFilter === 'orphans') return p.orphan;
      if (procFilter === 'external') return p.kind === 'esterno';
      if (procFilter === 'system') return p.kind === 'sistema' || p.kind === 'sigma';
      return true;
    });
  }, [gpuProcs.processes, procSearch, procFilter]);

  // Theme Design Tokens
  const cardBg = isLight ? '#fffdf9' : '#11141d';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 18px rgba(0,0,0,0.05)' : '0 10px 30px rgba(0, 0, 0, 0.4)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subCardBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.035)';
  const subCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  return (
    <div className="hardware-lab-container" style={{
      padding: 0,
      position: 'relative',
      overflowY: 'auto',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: isLight ? '#fcfaf6' : '#0b0d13'
    }}>
      {/* CONFIRMATION ALERT MODAL FOR RESTART OLLAMA */}
      {showRestartAlert && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(10px)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: isLight ? '#fffdf9' : 'rgba(18, 20, 28, 0.95)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '18px',
            padding: '24px',
            maxWidth: '460px',
            boxShadow: isLight ? '0 20px 50px rgba(0, 0, 0, 0.2)' : '0 20px 50px rgba(0, 0, 0, 0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#ef4444', marginBottom: '12px' }}>
              <AlertTriangle size={24} />
              <h3 style={{ margin: 0, fontSize: '1.15rem', color: textPrimary, fontWeight: 800 }}>Svuota VRAM & Riavvia Ollama?</h3>
            </div>
            <p style={{ fontSize: '0.84rem', color: textSecondary, lineHeight: 1.5, marginBottom: '20px' }}>
              Questa azione scaricherà tutti i modelli caricati in memoria video (VRAM) ed eseguirà il riavvio del servizio Ollama. 
              Nessun dato andrà perso.
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button 
                onClick={() => setShowRestartAlert(false)}
                disabled={restartingOllama}
                style={{ padding: '8px 16px', fontSize: '13px', borderRadius: '10px', background: isLight ? '#f2ede2' : 'rgba(255,255,255,0.06)', border: 'none', color: textPrimary, cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button 
                onClick={handleRestartOllama} 
                disabled={restartingOllama}
                style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', fontWeight: 800, fontSize: '13px', padding: '8px 16px', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}
              >
                {restartingOllama ? <Activity className="spin" size={15} /> : <RotateCcw size={15} />}
                {restartingOllama ? 'Svuotamento VRAM in corso...' : '⚡ Svuota VRAM & Riavvia Ollama'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOP HEADER & HERO BANNER */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        padding: '16px 24px',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: isLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.85) 0%, rgba(248, 242, 232, 0.80) 100%), url("/images/hardware_cluster_lab.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.88) 0%, rgba(14, 22, 42, 0.85) 100%), url("/images/hardware_cluster_lab.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center center',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '2px 10px', borderRadius: '12px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: isLight ? '#ea580c' : '#00d2ff', 
              fontSize: '0.66rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '4px'
            }}>
              <Zap size={13} /> CLUSTER GPU TELEMETRY & HARDWARE LAB
            </div>
            <h1 style={{ margin: '0 0 2px 0', fontSize: '1.25rem', fontWeight: 800, color: textPrimary, letterSpacing: '-0.3px' }}>
              ⚡ Hardware & <span style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>Cluster Telemetry Lab</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.76rem', color: textMuted }}>
              Monitoraggio VRAM in tempo reale, gestione processi e orchestrazione multi-scheda.
            </p>
          </div>

          {/* Quick Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button 
              onClick={handleClearVramMcp}
              title="Scarica i modelli dalla VRAM"
              style={{
                fontSize: '0.74rem', padding: '6px 12px', borderRadius: '8px',
                border: '1px solid rgba(0, 210, 255, 0.4)',
                background: isLight ? 'rgba(2, 132, 199, 0.1)' : 'rgba(0, 210, 255, 0.12)',
                color: isLight ? '#0284c7' : '#00d2ff',
                fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              <Zap size={12} /> Scarica VRAM
            </button>

            <button 
              onClick={() => setShowRestartAlert(true)}
              title="Svuota la memoria VRAM scaricando tutti i modelli e riavviando Ollama"
              style={{
                fontSize: '0.74rem', padding: '6px 12px', borderRadius: '8px',
                border: '1px solid rgba(239, 68, 68, 0.45)',
                background: isLight ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.15)',
                color: isLight ? '#dc2626' : '#fca5a5',
                fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              <RotateCcw size={12} color="#ef4444" /> Riavvia Ollama
            </button>

            <button 
              onClick={() => setShowCharts(!showCharts)}
              style={{
                fontSize: '0.74rem', padding: '6px 12px', borderRadius: '8px',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.12)',
                background: showCharts ? (isLight ? '#111827' : '#00d2ff') : (isLight ? '#fffdf9' : 'rgba(255, 255, 255, 0.05)'),
                color: showCharts ? '#ffffff' : textPrimary,
                fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              <BarChart2 size={12} /> {showCharts ? 'Grafici On' : 'Grafici Off'}
            </button>

            <button 
              onClick={() => setAutoRefresh(!autoRefresh)}
              style={{
                fontSize: '0.74rem', padding: '6px 12px', borderRadius: '8px',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.12)',
                background: isLight ? '#fffdf9' : 'rgba(255, 255, 255, 0.05)',
                color: textPrimary,
                fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
              }}
            >
              {autoRefresh ? <Pause size={12} color="#ea580c" /> : <Play size={12} />}
              {autoRefresh ? 'Live (2s)' : 'Pausa'}
            </button>
          </div>
        </div>

        {/* Top Summary Metric Strips */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '10px',
          marginTop: '12px'
        }}>
          {/* Card 1: VRAM */}
          <div style={{
            padding: '8px 12px', borderRadius: '10px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(2, 132, 199, 0.35)' : '1px solid rgba(0, 210, 255, 0.3)',
            boxShadow: isLight ? '0 2px 10px rgba(2, 132, 199, 0.08)' : '0 2px 10px rgba(0, 210, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase' }}>
              GPU & VRAM ALLOCATA
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
              {gpus.length} GPU • {totalVramGb} GB VRAM
            </div>
          </div>

          {/* Card 2: SYSTEM RAM */}
          <div style={{
            padding: '8px 12px', borderRadius: '10px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(22, 163, 74, 0.35)' : '1px solid rgba(16, 185, 129, 0.3)',
            boxShadow: isLight ? '0 2px 10px rgba(22, 163, 74, 0.08)' : '0 2px 10px rgba(16, 185, 129, 0.1)'
          }}>
            <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase' }}>
              SISTEMA RAM & DISCO
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.ram?.used_gb || hw.ram_used_gb || 0} / {hw.ram?.total_gb || hw.ram_gb || 0} GB
            </div>
          </div>

          {/* Card 3: CPU LOAD */}
          <div style={{
            padding: '8px 12px', borderRadius: '10px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(124, 58, 237, 0.35)' : '1px solid rgba(188, 140, 255, 0.3)',
            boxShadow: isLight ? '0 2px 10px rgba(124, 58, 237, 0.08)' : '0 2px 10px rgba(188, 140, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase' }}>
              CPU SYSTEM LOAD
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.cpu?.util_pct ?? 0}% • {hw.cpu?.logical_count || '?'} Thread
            </div>
          </div>
        </div>
      </div>

      {/* 2-COLUMN HARDWARE LAB WORKBENCH */}
      <div style={{
        padding: '16px 20px',
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)',
        gap: '16px',
        flex: 1
      }}>
        {/* ==================================================================== */}
        {/* COLUMN 1 (LEFT): CPU / SISTEMA IN ALTO + SCHEDE GPU FISICHE          */}
        {/* ==================================================================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          {/* 1. CPU & RAM SISTEMA IN ALTO */}
          <div style={{
            padding: '14px 16px',
            borderRadius: '14px',
            backgroundColor: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  padding: '2px 7px', borderRadius: '6px',
                  background: isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(16, 185, 129, 0.15)',
                  color: isLight ? '#16a34a' : '#10b981',
                  fontSize: '0.64rem', fontWeight: 800
                }}>
                  SYS
                </span>
                <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                  Sistema Host (CPU & RAM)
                </span>
              </div>
              <div style={{ fontSize: '0.66rem', color: textMuted }}>
                {hw.cpu?.logical_count || '?'} Cores • {hw.ram?.total_gb || 0} GB RAM
              </div>
            </div>

            {/* Gauges CPU & RAM */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {/* CPU Gauge */}
              <div style={{
                background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 210, 255, 0.04)',
                border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 210, 255, 0.18)',
                borderRadius: '10px', padding: '10px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 800, fontSize: '0.72rem', color: isLight ? '#0284c7' : '#00d2ff' }}>
                    <Cpu size={12} /> Carico CPU
                  </div>
                  <span style={{ fontSize: '0.74rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff' }}>{hw.cpu?.util_pct ?? 0}%</span>
                </div>
                <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(0,0,0,0.15)', overflow: 'hidden', marginBottom: '4px' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, hw.cpu?.util_pct ?? 0)}%`, background: 'linear-gradient(90deg, #0284c7, #00d2ff)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                  <span>{hw.cpu?.physical_count || '?'} Fisici / {hw.cpu?.logical_count || '?'} Thread</span>
                  <span>{hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : ''}</span>
                </div>
              </div>

              {/* RAM Gauge */}
              <div style={{
                background: isLight ? 'rgba(22, 163, 74, 0.06)' : 'rgba(16, 185, 129, 0.04)',
                border: isLight ? '1px solid rgba(22, 163, 74, 0.25)' : '1px solid rgba(16, 185, 129, 0.18)',
                borderRadius: '10px', padding: '10px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 800, fontSize: '0.72rem', color: isLight ? '#16a34a' : '#10b981' }}>
                    <HardDrive size={12} /> Memoria RAM
                  </div>
                  <span style={{ fontSize: '0.74rem', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981' }}>{hw.ram?.util_pct || hw.ram_pct || 0}%</span>
                </div>
                <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(0,0,0,0.15)', overflow: 'hidden', marginBottom: '4px' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, hw.ram?.util_pct || hw.ram_pct || 0)}%`, background: 'linear-gradient(90deg, #16a34a, #10b981)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                  <span>{hw.ram?.used_gb || hw.ram_used_gb || 0} GB usati</span>
                  <span>{hw.ram?.total_gb || hw.ram_gb || 0} GB Totali</span>
                </div>
              </div>
            </div>

            {/* Live CPU & RAM Sparklines */}
            {showCharts && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', paddingTop: '6px', borderTop: subCardBorder }}>
                <RealtimeTelemetryChart 
                  data={systemHistory.cpu} 
                  label="CPU Load (%)" 
                  icon={Cpu}
                  color={isLight ? '#0284c7' : '#00d2ff'} 
                  unit="%" 
                  maxVal={100} 
                  height={55}
                  isLight={isLight}
                />
                <RealtimeTelemetryChart 
                  data={systemHistory.ram} 
                  label="RAM (%)" 
                  icon={HardDrive}
                  color={isLight ? '#16a34a' : '#10b981'} 
                  unit="%" 
                  maxVal={100} 
                  height={55}
                  isLight={isLight}
                />
              </div>
            )}
          </div>

          {/* 2. SCHEDE GPU FISICHE */}
          {gpus.length === 0 ? (
            <div style={{ padding: '20px', borderRadius: '14px', background: cardBg, border: cardBorder, textAlign: 'center' }}>
              <Zap size={28} color="#00d2ff" style={{ margin: '0 auto 6px auto' }} />
              <h3 style={{ margin: 0, fontSize: '0.92rem', color: textPrimary }}>Nessuna GPU Dedicata Rilevata</h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.74rem', color: textMuted }}>Il sistema sta operando in modalità CPU fallback.</p>
            </div>
          ) : (
            gpus.map((gpu) => {
              const idx = gpu.index;
              const vramUsed = Number(gpu.vram_used_mb) || 0;
              const vramTotal = Number(gpu.vram_total_mb) || 1;
              const vramPct = Number(gpu.vram_util_pct) || Math.round((vramUsed / vramTotal) * 100);
              const utilPct = Number(gpu.gpu_util_pct) || 0;
              const pwrDraw = Number(gpu.power_draw_w) || 0;
              const pwrLimit = Number(gpu.power_limit_w) || 0;
              const hist = historyData[idx] || { vram: [], compute: [], temp: [], power: [] };

              return (
                <div key={idx} style={{
                  padding: '14px 16px',
                  borderRadius: '14px',
                  backgroundColor: cardBg,
                  border: cardBorder,
                  boxShadow: cardShadow,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  {/* GPU Card Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{
                        padding: '2px 7px', borderRadius: '6px',
                        fontSize: '0.66rem', fontWeight: 800,
                        background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                        color: isLight ? '#ea580c' : '#00d2ff',
                        border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)'
                      }}>
                        GPU {idx}
                      </div>
                      <div>
                        <div style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
                          {gpu.name}
                        </div>
                        <div style={{ fontSize: '0.64rem', color: textMuted }}>
                          Driver v{gpu.driver_version || 'N/A'} • Compute {gpu.compute_cap || 'v9.0+'}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '4px',
                        padding: '3px 8px', borderRadius: '6px',
                        background: subCardBg, border: subCardBorder,
                        fontSize: '0.68rem', fontWeight: 700, color: textPrimary
                      }}>
                        <Thermometer size={12} color="#ea580c" />
                        <span>{gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'}</span>
                      </div>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '4px',
                        padding: '3px 8px', borderRadius: '6px',
                        background: subCardBg, border: subCardBorder,
                        fontSize: '0.68rem', fontWeight: 700, color: textPrimary
                      }}>
                        <Flame size={12} color="#ef4444" />
                        <span>{pwrDraw}W</span>
                      </div>
                    </div>
                  </div>

                  {/* 2 Sub-gauges: Compute vs VRAM */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    {/* Compute */}
                    <div style={{
                      background: isLight ? 'rgba(124, 58, 237, 0.06)' : 'rgba(188, 140, 255, 0.04)',
                      border: isLight ? '1px solid rgba(124, 58, 237, 0.25)' : '1px solid rgba(188, 140, 255, 0.18)',
                      borderRadius: '10px', padding: '10px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 800, fontSize: '0.72rem', color: isLight ? '#7c3aed' : '#bc8cff' }}>
                          <Gauge size={12} /> Compute
                        </div>
                        <span style={{ fontSize: '0.74rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff' }}>{utilPct}%</span>
                      </div>
                      <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(0,0,0,0.15)', overflow: 'hidden', marginBottom: '4px' }}>
                        <div style={{ height: '100%', width: `${utilPct}%`, background: 'linear-gradient(90deg, #7c3aed, #bc8cff)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                        <span>{utilPct > 80 ? '🔥 Alto' : utilPct > 20 ? '⚡ Attivo' : '💤 Idle'}</span>
                        <span>{pwrDraw}W / {pwrLimit > 0 ? `${pwrLimit}W` : 'N/A'}</span>
                      </div>
                    </div>

                    {/* VRAM */}
                    <div style={{
                      background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 210, 255, 0.04)',
                      border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 210, 255, 0.18)',
                      borderRadius: '10px', padding: '10px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 800, fontSize: '0.72rem', color: isLight ? '#0284c7' : '#00d2ff' }}>
                          <HardDrive size={12} /> Memoria VRAM
                        </div>
                        <span style={{ fontSize: '0.74rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff' }}>{vramPct}%</span>
                      </div>
                      <div style={{ height: '5px', borderRadius: '3px', background: 'rgba(0,0,0,0.15)', overflow: 'hidden', marginBottom: '4px' }}>
                        <div style={{ height: '100%', width: `${vramPct}%`, background: 'linear-gradient(90deg, #0284c7, #00d2ff)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: textMuted }}>
                        <span>{vramUsed} / {vramTotal} MB</span>
                        <span>{(vramTotal / 1024).toFixed(1)} GB</span>
                      </div>
                    </div>
                  </div>

                  {/* Sparkline Charts */}
                  {showCharts && (
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '10px',
                      paddingTop: '8px',
                      borderTop: subCardBorder
                    }}>
                      <RealtimeTelemetryChart 
                        data={hist.compute} 
                        label="Compute (%)" 
                        icon={Cpu}
                        color={isLight ? '#7c3aed' : '#bc8cff'} 
                        unit="%" 
                        maxVal={100} 
                        height={60}
                        isLight={isLight}
                      />
                      <RealtimeTelemetryChart 
                        data={hist.vram} 
                        label="VRAM (MB)" 
                        icon={HardDrive}
                        color={isLight ? '#0284c7' : '#00d2ff'} 
                        unit="MB" 
                        maxVal={vramTotal} 
                        height={60}
                        isLight={isLight}
                        formatVal={(val) => `${typeof val === 'number' ? Math.round(val) : val}`}
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* ==================================================================== */}
        {/* COLUMN 2 (RIGHT): 1. CONSOLE DEI PROCESSI & GESTIONE VRAM/RAM        */}
        {/*                   2. NODI HARDWARE STANDBY                           */}
        {/* ==================================================================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          {/* 1. CONSOLE DEI PROCESSI & TASK MANAGER HARDWARE */}
          <div style={{
            borderRadius: '14px',
            backgroundColor: cardBg,
            border: gpuProcs.orfani > 0 ? '1px solid rgba(239, 68, 68, 0.45)' : cardBorder,
            boxShadow: cardShadow,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flex: 1
          }}>
            {/* Console Header Bar */}
            <div style={{
              padding: '12px 16px',
              background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(0,0,0,0.35)',
              borderBottom: cardBorder,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={16} color={isLight ? '#c2410c' : '#00d2ff'} />
                <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
                  Monitor Processi & Allocazione Memoria
                </span>
                <span style={{
                  fontSize: '0.66rem', padding: '2px 8px', borderRadius: '8px',
                  background: isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)',
                  color: textPrimary, fontWeight: 700
                }}>
                  {gpuProcs.processes.length} processi attivi
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {gpuProcs.orfani > 0 && (
                  <button
                    onClick={handleKillAllOrphans}
                    title="Termina tutti i processi orfani"
                    style={{
                      fontSize: '0.66rem', padding: '4px 10px', borderRadius: '6px',
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      color: '#ef4444', fontWeight: 800, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '4px'
                    }}
                  >
                    <AlertTriangle size={12} /> Termina {gpuProcs.orfani} Orfani
                  </button>
                )}
                <button
                  onClick={fetchGpuProcesses}
                  title="Aggiorna lista processi"
                  style={{
                    background: 'transparent', border: 'none', color: textMuted, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', padding: '4px'
                  }}
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>

            {/* Console Toolbar (Search + Category Filter Chips) */}
            <div style={{
              padding: '8px 12px',
              borderBottom: subCardBorder,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
              background: subCardBg
            }}>
              {/* Search Bar */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '4px 8px', borderRadius: '6px',
                background: isLight ? '#ffffff' : 'rgba(0,0,0,0.25)',
                border: subCardBorder, flex: 1, minWidth: '150px'
              }}>
                <Search size={12} color={textMuted} />
                <input
                  type="text"
                  placeholder="Filtra per PID, nome, utente o GPU..."
                  value={procSearch}
                  onChange={e => setProcSearch(e.target.value)}
                  style={{
                    background: 'transparent', border: 'none',
                    color: textPrimary, fontSize: '0.74rem', outline: 'none', width: '100%'
                  }}
                />
                {procSearch && (
                  <button onClick={() => setProcSearch('')} style={{ background: 'none', border: 'none', color: textMuted, cursor: 'pointer' }}>
                    <X size={12} />
                  </button>
                )}
              </div>

              {/* Filter Pills */}
              <div style={{ display: 'flex', gap: '4px', overflowX: 'auto' }}>
                {[
                  { id: 'all', label: 'Tutti' },
                  { id: 'gpu', label: 'GPU Dedicated' },
                  { id: 'orphans', label: 'Orfani' },
                  { id: 'python', label: 'Python / AI' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setProcFilter(tab.id)}
                    style={{
                      fontSize: '0.66rem', padding: '3px 8px', borderRadius: '6px',
                      border: 'none',
                      background: procFilter === tab.id ? (isLight ? '#111827' : '#00d2ff') : 'transparent',
                      color: procFilter === tab.id ? '#ffffff' : textMuted,
                      fontWeight: procFilter === tab.id ? 800 : 600,
                      cursor: 'pointer'
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Table Header Row */}
            <div style={{
              padding: '6px 14px',
              display: 'grid',
              gridTemplateColumns: 'minmax(140px, 1.4fr) minmax(70px, 0.7fr) minmax(110px, 1fr) minmax(90px, 0.9fr) minmax(80px, 0.8fr) 70px',
              gap: '6px',
              fontSize: '0.62rem',
              fontWeight: 800,
              color: textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              borderBottom: subCardBorder,
              background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.2)'
            }}>
              <div>Processo & PID</div>
              <div>Utente</div>
              <div>GPU Assegnata</div>
              <div>VRAM / RAM</div>
              <div>Carico CPU/GPU</div>
              <div style={{ textAlign: 'right' }}>Azione</div>
            </div>

            {/* Process List Container (Expanded) */}
            <div style={{
              maxHeight: '440px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {filteredProcesses.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', fontSize: '0.76rem', color: textMuted }}>
                  Nessun processo trovato con i filtri selezionati.
                </div>
              ) : (
                filteredProcesses.map(proc => {
                  const isOrphan = proc.is_orphan || proc.orphan;
                  const isExpanded = expandedPid === proc.pid;

                  return (
                    <div
                      key={proc.pid}
                      style={{
                        padding: '8px 14px',
                        borderBottom: subCardBorder,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        background: isOrphan 
                          ? (isLight ? 'rgba(239, 68, 68, 0.06)' : 'rgba(239, 68, 68, 0.08)')
                          : 'transparent',
                        transition: 'background 0.15s ease'
                      }}
                    >
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'minmax(140px, 1.4fr) minmax(70px, 0.7fr) minmax(110px, 1fr) minmax(90px, 0.9fr) minmax(80px, 0.8fr) 70px',
                        alignItems: 'center',
                        gap: '6px'
                      }}>
                        {/* 1. Process & PID */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                          <span style={{
                            fontFamily: 'JetBrains Mono, monospace',
                            fontSize: '0.66rem', fontWeight: 800,
                            padding: '2px 5px', borderRadius: '4px',
                            background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)',
                            color: textPrimary
                          }}>
                            #{proc.pid}
                          </span>
                          <span style={{
                            fontSize: '0.76rem', fontWeight: 800,
                            color: isOrphan ? '#ef4444' : (isLight ? '#0284c7' : '#00d2ff'),
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                          }} title={proc.name}>
                            {proc.name || `PID ${proc.pid}`}
                          </span>
                        </div>

                        {/* 2. User */}
                        <div style={{ fontSize: '0.7rem', color: textSecondary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {proc.user || 'Sigma'}
                        </div>

                        {/* 3. Assigned GPU */}
                        <div>
                          <span style={{
                            fontSize: '0.62rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px',
                            background: proc.vram_mb > 500 
                              ? 'rgba(0, 210, 255, 0.15)' 
                              : (proc.vram_mb > 100 ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255, 255, 255, 0.05)'),
                            color: proc.vram_mb > 500 
                              ? (isLight ? '#0284c7' : '#00d2ff') 
                              : (proc.vram_mb > 100 ? '#bc8cff' : textMuted),
                            border: proc.vram_mb > 500 ? '1px solid rgba(0, 210, 255, 0.3)' : '1px solid transparent',
                            whiteSpace: 'nowrap'
                          }}>
                            {proc.assigned_gpu || `GPU ${proc.gpu_index ?? 0}`}
                          </span>
                        </div>

                        {/* 4. VRAM / RAM */}
                        <div style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono, monospace', color: textPrimary }}>
                          <span style={{ color: isLight ? '#0284c7' : '#00d2ff', fontWeight: 700 }}>{proc.vram_mb || 0} MB</span>
                          <span style={{ color: textMuted, fontSize: '0.62rem' }}> / {proc.memory_mb || 0}M RAM</span>
                        </div>

                        {/* 5. CPU / GPU Load */}
                        <div style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono, monospace', color: textMuted }}>
                          <span>{proc.cpu_pct ?? 0}% CPU</span>
                          {proc.gpu_pct > 0 && <span style={{ color: '#bc8cff', marginLeft: '4px' }}>{proc.gpu_pct}% G</span>}
                        </div>

                        {/* 6. Action */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
                          <button
                            onClick={() => handleKillGpuProcess(proc)}
                            disabled={killingPid === proc.pid}
                            style={{
                              fontSize: '0.62rem', padding: '3px 8px', borderRadius: '4px',
                              border: '1px solid rgba(239, 68, 68, 0.4)',
                              background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
                              fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px'
                            }}
                            title="Termina processo e libera memoria"
                          >
                            <Trash2 size={10} /> {killingPid === proc.pid ? '...' : 'Kill'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>


          {/* 3. ACCELERATORI HARDWARE IN STANDBY */}
          <div style={{
            padding: '16px 18px',
            borderRadius: '14px',
            backgroundColor: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Layers size={15} color="#bc8cff" />
                <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
                  Acceleratori Hardware & Nodi Standby
                </span>
              </div>
              <span style={{ fontSize: '0.64rem', color: textMuted }}>
                {INACTIVE_HARDWARE_NODES.length} Moduli
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {INACTIVE_HARDWARE_NODES.map(node => {
                const IconComp = node.icon;
                const isActivated = activatedHw[node.id];
                const isExpanded = expandedHwNode === node.id;

                return (
                  <div
                    key={node.id}
                    style={{
                      padding: '10px 14px', borderRadius: '10px',
                      background: subCardBg,
                      border: isActivated 
                        ? '1px solid rgba(22, 163, 74, 0.4)' 
                        : subCardBorder,
                      display: 'flex', flexDirection: 'column', gap: '6px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {/* Header Row */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          width: '26px', height: '26px', borderRadius: '6px',
                          background: isActivated ? 'rgba(22, 163, 74, 0.15)' : `${node.color}15`,
                          color: isActivated ? '#16a34a' : node.color,
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          <IconComp size={14} />
                        </div>
                        <div>
                          <div style={{ fontSize: '0.8rem', fontWeight: 800, color: textPrimary }}>
                            {node.title}
                          </div>
                          <div style={{ fontSize: '0.64rem', color: textMuted }}>
                            {node.subtitle}
                          </div>
                        </div>
                      </div>

                      <span style={{
                        fontSize: '0.58rem', fontWeight: 800,
                        color: isActivated ? '#16a34a' : textMuted,
                        background: isActivated ? 'rgba(22, 163, 74, 0.12)' : (isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)'),
                        border: subCardBorder,
                        padding: '2px 6px', borderRadius: '5px'
                      }}>
                        {isActivated ? 'ATTIVO ⚡' : 'NON DISPONIBILE'}
                      </span>
                    </div>

                    {/* Detailed Description & Technical Spec */}
                    <div style={{
                      padding: '6px 10px',
                      borderRadius: '6px',
                      background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(0,0,0,0.25)',
                      border: subCardBorder,
                      fontSize: '0.66rem',
                      lineHeight: 1.45,
                      color: textSecondary,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px'
                    }}>
                      <div>
                        <strong style={{ color: textPrimary }}>Funzione: </strong>
                        {node.details}
                      </div>
                      <div style={{ color: isLight ? '#9a3412' : '#ea580c' }}>
                        <strong>Requisito di attivazione: </strong>
                        {node.prerequisite}
                      </div>
                    </div>

                    {/* Actions Row */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '4px' }}>
                      <button
                        onClick={() => setActiveHwModal(node)}
                        style={{
                          background: 'none', border: 'none',
                          color: isLight ? '#0284c7' : '#00d2ff',
                          fontSize: '0.64rem', fontWeight: 700,
                          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', padding: 0
                        }}
                      >
                        <Info size={11} /> Scheda Tecnica & Info
                      </button>

                      <button
                        onClick={() => {
                          if (isActivated) return;
                          if (addToast) addToast(`⚠️ Il modulo ${node.title} non è ancora disponibile o non collegato al sistema.`, 'info');
                        }}
                        style={{
                          padding: '3px 8px', borderRadius: '5px',
                          background: isActivated ? 'rgba(22, 163, 74, 0.1)' : (isLight ? 'rgba(0, 0, 0, 0.04)' : 'rgba(255, 255, 255, 0.04)'),
                          border: isActivated ? '1px solid rgba(22, 163, 74, 0.3)' : (isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)'),
                          color: isActivated ? '#16a34a' : textMuted,
                          fontSize: '0.64rem', fontWeight: 700,
                          cursor: isActivated ? 'default' : 'not-allowed',
                          display: 'flex', alignItems: 'center', gap: '4px',
                          opacity: isActivated ? 1 : 0.85
                        }}
                        title={isActivated ? 'Modulo inizializzato' : 'Modulo hardware non collegato o non ancora disponibile'}
                      >
                        {isActivated ? <CheckCircle2 size={10} /> : <Info size={10} />}
                        {isActivated ? 'Inizializzato' : 'Non ancora disponibile'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Standby Hardware Activation Modal Popup */}
      {activeHwModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '480px', 
            background: isLight ? '#fffdf9' : 'rgba(18, 20, 28, 0.95)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : `1px solid ${activeHwModal.color}40`, 
            borderRadius: '18px',
            padding: '22px', 
            boxShadow: isLight ? '0 20px 60px rgba(0,0,0,0.25)' : '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', color: activeHwModal.color }}>
              <activeHwModal.icon size={22} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.1rem', color: textPrimary, fontWeight: 800 }}>
                  {activeHwModal.title}
                </h2>
                <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                  {activeHwModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.8rem', color: textSecondary, lineHeight: 1.5, marginBottom: '14px' }}>
              {activeHwModal.details}
            </p>

            <div style={{ padding: '10px 12px', borderRadius: '8px', background: subCardBg, border: subCardBorder, marginBottom: '18px', fontSize: '0.74rem', color: textPrimary }}>
              <div style={{ fontWeight: 800, color: isLight ? '#9a3412' : '#fff', marginBottom: '3px' }}>📋 Requisito di Inizializzazione:</div>
              {activeHwModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveHwModal(null)}
                style={{ padding: '7px 14px', borderRadius: '7px', background: isLight ? '#f4efe4' : 'rgba(255,255,255,0.06)', border: 'none', color: textPrimary, cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700 }}
              >
                Annulla
              </button>
              <button
                onClick={() => {
                  setActivatingHw(activeHwModal.id);
                  setTimeout(() => {
                    setActivatedHw(prev => ({ ...prev, [activeHwModal.id]: true }));
                    setActivatingHw(null);
                    setActiveHwModal(null);
                    if (addToast) addToast(`⚡ Modulo ${activeHwModal.title} collegato con successo!`, 'success');
                  }, 1000);
                }}
                disabled={activatingHw === activeHwModal.id}
                style={{
                  padding: '7px 16px', borderRadius: '7px',
                  background: isLight 
                    ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                    : `linear-gradient(135deg, ${activeHwModal.color}, #00d2ff)`, 
                  border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '5px'
                }}
              >
                {activatingHw === activeHwModal.id ? <Activity className="spin" size={13} /> : <Zap size={13} />}
                {activatingHw === activeHwModal.id ? 'Inizializzazione...' : 'Connetti Modulo ⚡'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}