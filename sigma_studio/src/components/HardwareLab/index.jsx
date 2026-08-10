import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Activity, Zap, HardDrive, Save, ChevronDown, ChevronUp, RotateCcw, Trash2,
  ShieldCheck, Sliders, Play, Pause, TrendingUp, BarChart2,
  Cpu, Thermometer, Flame, Gauge, AlertTriangle, Layers, CheckCircle2, ArrowRight
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import '../../styles/hardware-lab.css';

const MAX_HISTORY = 900; // ~30 minutes at 2s intervals

const INACTIVE_HARDWARE_NODES = [
  {
    id: 'arm64_node',
    title: 'Cluster Nodi ARM64 & Raspberry Pi 5 Edge',
    subtitle: 'Offloading di task leggeri di sensoristica, micro-controller e preprocessing I/O su nodi ARM64.',
    prerequisite: 'Indirizzo IP o Hostname SSH nodo ARM64 (pi@192.168.1.xxx)',
    statusBadge: 'DISPOSITIVO EDGE STANDBY',
    icon: Cpu,
    color: '#3fb950',
    actionText: 'Collega Nodo ARM64',
    details: 'Consente di delegare compiti a basso consumo energetico (es. polling sensori, ascolto di eventi MQTT, piccoli script di monitoraggio) a nodi Raspberry Pi 5 o micro-server ARM64 collegati in rete locale.'
  },
  {
    id: 'intel_npu',
    title: 'NPU Neural Processing Unit (OpenVINO / DirectML)',
    subtitle: 'Accelerazione hardware dedicata su NPU di bordo per la quantizzazione ed il risparmio energetico durante la sintesi TTS.',
    prerequisite: 'Driver Intel OpenVINO / DirectML NPU Active',
    statusBadge: 'DRIVER NPU NON RILEVATO',
    icon: Gauge,
    color: '#00d2ff',
    actionText: 'Abilita Acceleration NPU',
    details: 'Sfrutta l\'acceleratore di calcolo NPU dedicato presente nei processori Intel Core Ultra o Qualcomm Snapdragon per liberare la GPU principale durante i task di sintesi vocale e tokenization.'
  },
  {
    id: 'liquid_cooling',
    title: 'Liquid Cooling & Dynamic Thermal Throttle',
    subtitle: 'Monitoraggio del flusso di liquido refrigerante ed auto-throttling preventivo della frequenza di clock sui picchi > 85°C.',
    prerequisite: 'Controller Pompa PWM / Sensore Flusso Corsair iCUE',
    statusBadge: 'SENSORE LIQUIDO STANDBY',
    icon: Thermometer,
    color: '#ff5064',
    actionText: 'Associa Sensore Liquido',
    details: 'Monitora la telemetria della temperatura del liquido di raffreddamento e regola preventivamente i power limit (TDP) della GPU per evitare il throttling termico improvviso durante le sessioni di fine-tuning prolungate.'
  },
  {
    id: 'nvlink_bridge',
    title: 'NVLink High-Speed Distributed GPU Bridge',
    subtitle: 'Comunicazione P2P a 900 GB/s tra GPU NVIDIA per la ripartizione dei pesi di modelli > 70B senza colli di bottiglia PCIe.',
    prerequisite: '2x GPU NVIDIA RTX/A-Series + Ponte Fisico NVLink',
    statusBadge: 'NVLINK SLI STANDBY',
    icon: Zap,
    color: '#a78bfa',
    actionText: 'Attiva Bridge NVLink',
    details: 'Attiva il bus ad altissima velocità NVLink per unire la VRAM di più schede grafiche NVIDIA in un unico pool di memoria contiguo, permettendo di caricare modelli LLM da 70 miliardi di parametri a piena velocità.'
  },
  {
    id: 'fpga_accelerator',
    title: 'FPGA Logic Accelerator Board',
    subtitle: 'Accelerazione hardware di algoritmi di crittografia custom, matrici veloci e compressione token via chip FPGA.',
    prerequisite: 'Scheda Xilinx Alveo / PCIe FPGA Driver',
    statusBadge: 'SCHEDA FPGA STANDBY',
    icon: HardDrive,
    color: '#ffb86c',
    actionText: 'Inizializza FPGA',
    details: 'Sfrutta le schede FPGA programmabili via PCIe per velocizzare le operazioni di hashing, de-compressione dei dataset e moltiplicazione tra matrici a precisione arbitraria.'
  },
  {
    id: 'ups_power',
    title: 'UPS Power & Line Voltage Monitoring',
    subtitle: 'Monitoraggio della continuità elettrica del cluster, con salvataggio automatico delle memorie agentiche prima di blackout.',
    prerequisite: 'Gruppo di Continuità USB / NUT (Network UPS Tools)',
    statusBadge: 'UPS USB DISCONNESSO',
    icon: ShieldCheck,
    color: '#38bdf8',
    actionText: 'Collega Telemetria UPS',
    details: 'Si interfaccia con il gruppo di continuità via USB o rete local NUT per tracciare il voltaggio di rete, i Watt assorbiti e sincronizzare uno spegnimento di emergenza controllato con salvataggio dello stato del sistema in caso di mancanza di corrente.'
  }
];

export default function HardwareLab({ addToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  const [showCharts, setShowCharts] = useState(true); // Collapsible charts enabled by default
  const [showRestartAlert, setShowRestartAlert] = useState(false); // Alert modal
  const [restartingOllama, setRestartingOllama] = useState(false);

  // Standby hardware activation modal state
  const [activeHwModal, setActiveHwModal] = useState(null);
  const [activatingHw, setActivatingHw] = useState(null);
  const [activatedHw, setActivatedHw] = useState({});

  // Chi sta occupando la GPU, e con quale job di Sigma.
  const [gpuProcs, setGpuProcs] = useState({ processes: [], orfani: 0 });
  const [killingPid, setKillingPid] = useState(null);

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

  const fetchGpuProcesses = useCallback(async () => {
    try {
      const res = await fetch('/api/hardware/gpu/processes');
      if (!res.ok) return;
      const json = await res.json();
      if (json.success) setGpuProcs({ processes: json.processes || [], orfani: json.orfani || 0 });
    } catch (err) {
      console.error('Failed to fetch GPU processes:', err);
    }
  }, []);

  // Cadenza propria, piu' lenta della telemetria: ogni giro costa due
  // invocazioni di nvidia-smi, e la lista dei processi cambia di rado.
  useEffect(() => {
    fetchGpuProcesses();
    if (!autoRefresh) return;
    const interval = setInterval(fetchGpuProcesses, 5000);
    return () => clearInterval(interval);
  }, [fetchGpuProcesses, autoRefresh]);

  const handleKillGpuProcess = async (proc) => {
    // Chiudere un training di Sigma e' l'operazione per cui questa lista
    // esiste; chiudere un processo estraneo e' una cosa diversa, e la domanda
    // deve dirlo — dall'altra parte puo' esserci il browser dell'utente.
    const domanda = proc.job_id
      ? `Fermare il training del job ${proc.job_id} (PID ${proc.pid})?\n` +
        `Gli step non ancora salvati in un checkpoint andranno persi.`
      : `Chiudere ${proc.name || `il processo ${proc.pid}`} (PID ${proc.pid})?\n\n` +
        `ATTENZIONE: non è un job di Sigma Studio. È un'applicazione esterna ` +
        `che sta usando la GPU, e chiuderla può farti perdere il lavoro non salvato.`;
    if (!confirm(domanda)) return;

    setKillingPid(proc.pid);
    try {
      const res = await fetch('/api/hardware/gpu/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: proc.pid })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(json.message || `Processo ${proc.pid} terminato.`, 'success');
      } else if (addToast) {
        addToast(json.error || `Non sono riuscito a chiudere il processo ${proc.pid}.`, 'error');
      }
      fetchGpuProcesses();
      fetchHardwareStatus();
    } catch (e) {
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    } finally {
      setKillingPid(null);
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

  // Nome storico: `clear_vram_cache` riavvia il servizio Ollama, e libera la
  // VRAM solo dei modelli che Ollama teneva caricati. Non ha nessun effetto sui
  // processi di training, che sono processi a se' — l'etichetta «Pulisci VRAM»
  // lo faceva sembrare il pulsante da premere su un run appeso, e non lo e'.
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

      {/* Premium Cyber-Glassmorphic Hardware Hero Panel */}
      <div style={{
        position: 'relative',
        borderRadius: '28px',
        overflow: 'hidden',
        padding: '50px 52px 36px 52px',
        minHeight: '340px',
        border: '1px solid rgba(0, 210, 255, 0.4)',
        boxShadow: '0 24px 80px rgba(0, 0, 0, 0.75), 0 0 40px rgba(0, 210, 255, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.15)',
        backgroundImage: 'linear-gradient(to right, rgba(8, 10, 16, 0.88) 32%, rgba(8, 10, 16, 0.25) 100%), url("/images/hardware_cluster_lab.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center right',
        marginBottom: '28px',
        display: 'flex',
        flexDirection: 'column',
        justify: 'space-between',
        gap: '36px'
      }}>
        {/* Top Header Row: Title & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '24px', zIndex: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '20px',
              background: 'radial-gradient(circle at 30% 30%, rgba(0, 242, 254, 0.35), rgba(0, 210, 255, 0.12))',
              border: '1px solid rgba(0, 242, 254, 0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 35px rgba(0, 242, 254, 0.35)'
            }}>
              <Zap size={32} color="#00f2fe" />
            </div>
            <div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: '8px',
                padding: '4px 14px', borderRadius: '14px',
                background: 'rgba(0, 210, 255, 0.18)', border: '1px solid rgba(0, 210, 255, 0.4)',
                color: '#00d2ff', fontSize: '0.74rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: '6px'
              }}>
                <Activity size={14} /> HARDWARE TELEMETRY & CLUSTER COMPUTING
              </div>
              <h1 style={{ margin: 0, fontSize: '2.2rem', fontWeight: 900, color: '#fff', letterSpacing: '-0.8px' }}>
                ⚡ Hardware & Cluster Telemetry Lab
              </h1>
            </div>
          </div>

          {/* Action Buttons Row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button 
              className="hw-btn"
              onClick={() => setShowRestartAlert(true)}
              title="Svuota la memoria VRAM/RAM scaricando tutti i modelli caricati da Ollama"
              style={{ fontSize: '12px', padding: '8px 16px', borderRadius: '12px', border: '1px solid rgba(239, 68, 68, 0.45)', background: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', fontWeight: 800 }}
            >
              <RotateCcw size={14} color="#ef4444" />
              <span>Svuota VRAM / Riavvia Ollama</span>
            </button>

            <button 
              className={`hw-btn ${showCharts ? 'hw-btn-primary' : ''}`}
              onClick={() => setShowCharts(!showCharts)}
              title={showCharts ? 'Nascondi i grafici per compattare la vista' : 'Mostra i grafici storici in tempo reale'}
              style={{ fontSize: '12px', padding: '8px 16px', borderRadius: '12px', fontWeight: 800 }}
            >
              <BarChart2 size={14} color={showCharts ? '#fff' : '#00f2fe'} />
              {showCharts ? 'Nascondi Grafici Storici' : 'Mostra Grafici Storici'}
              {showCharts ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            <button 
              className="hw-btn" 
              onClick={() => setAutoRefresh(!autoRefresh)}
              title={autoRefresh ? 'Metti in pausa il refresh' : 'Riprendi refresh automatico'}
              style={{ fontSize: '12px', padding: '8px 16px', borderRadius: '12px', fontWeight: 800 }}
            >
              {autoRefresh ? <Pause size={13} color="#00f2fe" /> : <Play size={13} />}
              {autoRefresh ? 'Pausa (2s)' : 'Riprendi'}
            </button>
          </div>
        </div>

        {/* Bottom Row: Compact Telemetry Stat Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', zIndex: 2 }}>
          
          {/* Card 1: VRAM & GPU */}
          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: 'rgba(10, 14, 24, 0.85)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(0, 210, 255, 0.3)', boxShadow: '0 4px 18px rgba(0, 210, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              GPU & VRAM ALLOCATA
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
              {gpus.length} GPU • {totalVramGb} GB
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {gpus.map(g => g.name || `GPU ${g.index}`).join(', ') || 'NVIDIA Compute'}
            </div>
          </div>

          {/* Card 2: SYSTEM RAM */}
          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: 'rgba(10, 14, 24, 0.85)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(16, 185, 129, 0.3)', boxShadow: '0 4px 18px rgba(16, 185, 129, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              SISTEMA RAM & DISCO
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.ram?.used_gb || hw.ram_used_gb || 0} / {hw.ram?.total_gb || hw.ram_gb || 0} GB
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px' }}>
              RAM Utilizzata {hw.ram?.util_pct || hw.ram_pct || 0}% • Disco {hw.disk?.used_gb || 0} GB
            </div>
          </div>

          {/* Card 3: CPU THREADS */}
          <div style={{
            padding: '10px 14px', borderRadius: '12px',
            background: 'rgba(10, 14, 24, 0.85)', backdropFilter: 'blur(12px)',
            border: '1px solid rgba(188, 140, 255, 0.3)', boxShadow: '0 4px 18px rgba(188, 140, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontWeight: 800, textTransform: 'uppercase', marginBottom: '2px' }}>
              CPU SYSTEM LOAD
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.cpu?.util_pct ?? 0}% LOAD
            </div>
            <div style={{ fontSize: '0.65rem', color: '#6b7080', marginTop: '1px' }}>
              {hw.cpu?.logical_count || '?'} Thread Logici • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
            </div>
          </div>

        </div>
      </div>

      {/* Main Cards Container */}
      <div className="gpu-cards-container" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

        {/* ==================================================================== */}
        {/* PROCESSI SULLA GPU — chi la sta occupando, e come chiuderlo          */}
        {/* ==================================================================== */}
        <div className="gpu-card" style={{
          padding: '14px 18px',
          background: 'rgba(15, 23, 42, 0.75)',
          border: gpuProcs.orfani > 0 ? '1px solid rgba(239, 68, 68, 0.45)' : undefined
        }}>
          <div className="gpu-card-header" style={{ marginBottom: gpuProcs.processes.length ? '12px' : 0 }}>
            <div className="gpu-title">
              <div className="gpu-index-pill" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7', border: '1px solid rgba(168, 85, 247, 0.3)', padding: '2px 8px', fontSize: '11px' }}>
                PID
              </div>
              <div>
                <div className="gpu-name" style={{ fontSize: '15px' }}>Processi sulla GPU</div>
                <div className="gpu-bus-info" style={{ fontSize: '11px' }}>
                  {gpuProcs.processes.length === 0
                    ? 'Nessun processo sta usando la GPU per il calcolo'
                    : `${gpuProcs.processes.length} processi • i job di Sigma si fermano da qui`}
                </div>
              </div>
            </div>
            {gpuProcs.orfani > 0 && (
              <div className="gpu-header-badges">
                <div className="gpu-stat-badge" style={{ padding: '4px 10px', fontSize: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.35)' }}>
                  <AlertTriangle size={14} color="#ef4444" />
                  <span style={{ fontWeight: 700, color: '#ef4444' }}>
                    {gpuProcs.orfani} orfan{gpuProcs.orfani === 1 ? 'o' : 'i'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {gpuProcs.processes.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {gpuProcs.processes.map(proc => {
                const isTraining = proc.kind === 'training';
                const accent = proc.orphan ? '#ef4444' : (isTraining ? '#00d2ff' : 'var(--text-dim)');
                return (
                  <div key={proc.pid} style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '8px 12px', borderRadius: '8px',
                    background: isTraining ? 'rgba(0, 210, 255, 0.05)' : 'rgba(148, 163, 184, 0.04)',
                    border: `1px solid ${proc.orphan ? 'rgba(239, 68, 68, 0.35)' : (isTraining ? 'rgba(0, 210, 255, 0.2)' : 'rgba(148, 163, 184, 0.12)')}`
                  }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: accent }}>
                          {proc.name || `PID ${proc.pid}`}
                        </span>
                        <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>PID {proc.pid}</span>
                        {proc.job_id && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', borderColor: 'rgba(0, 210, 255, 0.3)' }}>
                            job {proc.job_id}
                          </span>
                        )}
                        {proc.orphan && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.35)' }}>
                            ORFANO — il job risulta {proc.job_status}
                          </span>
                        )}
                        {proc.kind === 'esterno' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', color: 'var(--text-dim)' }}>
                            esterno a Sigma
                          </span>
                        )}
                        {proc.kind === 'sigma' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                            Sigma Studio
                          </span>
                        )}
                        {proc.kind === 'sistema' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                            processo di Windows
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '3px' }}>
                        {/* Il nome della scheda, non il suo numero: la numerazione
                            di nvidia-smi conta solo le GPU NVIDIA, mentre le card
                            qui sotto contano anche la iGPU, e i due numeri non
                            coincidono. Meglio nessun indice di uno che contraddice
                            il resto della pagina. */}
                        {(proc.gpus || []).map(g => g.name || `GPU ${g.index}`).join(' + ') || 'GPU sconosciuta'}
                        {/* Su Windows in modalita' WDDM il driver non attribuisce la
                            VRAM ai singoli processi: meglio "n/d" di uno zero falso. */}
                        {' • VRAM '}{proc.vram_gb != null ? `${proc.vram_gb} GB` : 'n/d'}
                        {proc.started_at ? ` • dalle ${proc.started_at.slice(11)}` : ''}
                        {proc.base_model ? ` • ${proc.base_model}` : ''}
                      </div>
                    </div>
                    {proc.killable ? (
                      <button
                        className="hw-btn"
                        onClick={() => handleKillGpuProcess(proc)}
                        disabled={killingPid === proc.pid}
                        title={isTraining ? 'Ferma il job e libera la GPU' : 'Chiudi questo processo esterno'}
                        style={{
                          fontSize: '11px', padding: '5px 10px', flexShrink: 0,
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444'
                        }}
                      >
                        <Trash2 size={12} color="#ef4444" />
                        <span>{killingPid === proc.pid ? 'Chiudo…' : 'Termina'}</span>
                      </button>
                    ) : (
                      <span style={{ fontSize: '10px', color: 'var(--text-dim)', flexShrink: 0 }}
                            title={proc.kind === 'sistema'
                              ? 'Processo di sistema: chiuderlo comprometterebbe la sessione di Windows'
                              : 'È Sigma Studio: chiuderlo spegnerebbe questa interfaccia'}>
                        non chiudibile
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>


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
            const hist = historyData[idx] || { vram: [], compute: [], temp: [], power: [] };

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
              {gpus.length > 1 && (
                <option value={gpus.map(g => g.index).join(',')}>
                  {gpus.map(g => g.index).join(',')} — Parallelismo Multi-GPU ({gpus.map(g => g.name || `GPU ${g.index}`).join(' + ')})
                </option>
              )}
              {gpus.map(g => (
                <option key={g.index} value={String(g.index)}>
                  {g.index} — Solo GPU {g.index} ({g.name || `GPU ${g.index}`} {g.vram_total_gb ? `- ${g.vram_total_gb}GB VRAM` : ''})
                </option>
              ))}
              {gpus.length === 0 && <option value="0">0 — GPU predefinita del sistema</option>}
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
              {gpus.map(g => (
                <option key={g.index} value={`cuda:${g.index}`}>
                  cuda:{g.index} ({g.name || `GPU ${g.index}`} {g.vram_total_gb ? `— ${g.vram_total_gb}GB VRAM` : ''})
                </option>
              ))}
              {gpus.length > 1 && (
                <option value={`cuda:${gpus.map(g => g.index).join(',')}`}>
                  cuda:{gpus.map(g => g.index).join(',')} (DataParallel Multi-GPU)
                </option>
              )}
              {gpus.length === 0 && <option value="cuda:0">cuda:0 (GPU predefinita del sistema)</option>}
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

      {/* ── CARD GRIGIE — HARDWARE & NODI IN STANDBY ── */}
      <div style={{ marginTop: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#8b8fa3', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
            <Layers size={13} /> ESPANSIONI CLUSTER & ACCELERATORI HARDWARE IN ATTESA
          </div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: '#fff' }}>
            ⚡ Hardware & Nodi di Calcolo Avanzati in Standby (Da Attivare)
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#8b8fa3' }}>
            Moduli hardware, acceleratori e nodi di calcolo distribuito in attesa di pairing o collegamento fisico:
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
          {INACTIVE_HARDWARE_NODES.map(node => {
            const IconComp = node.icon;
            const isActivated = activatedHw[node.id];

            return (
              <div
                key={node.id}
                style={{
                  padding: '24px', borderRadius: '18px',
                  background: isActivated ? 'rgba(14, 17, 25, 0.85)' : 'rgba(14, 17, 25, 0.4)',
                  border: '1px solid ' + (isActivated ? `${node.color}40` : 'rgba(255, 255, 255, 0.08)'),
                  boxShadow: isActivated ? `0 8px 32px ${node.color}15` : 'none',
                  display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                  gap: '16px', opacity: isActivated ? 1 : 0.72,
                  filter: isActivated ? 'none' : 'grayscale(35%)',
                  transition: 'all 0.3s ease'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{
                      width: '44px', height: '44px', borderRadius: '12px',
                      background: isActivated ? `${node.color}25` : 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid ' + (isActivated ? node.color : 'rgba(255,255,255,0.08)'),
                      color: isActivated ? node.color : '#8b8fa3',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <IconComp size={22} />
                    </div>

                    <span style={{
                      fontSize: '0.68rem', fontWeight: 800,
                      color: isActivated ? '#3fb950' : '#8b8fa3',
                      background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.1)'),
                      padding: '3px 10px', borderRadius: '20px', letterSpacing: '0.5px'
                    }}>
                      {isActivated ? 'NODO HARDWARE ATTIVO ⚡' : node.statusBadge}
                    </span>
                  </div>

                  <h3 style={{ margin: '0 0 6px 0', fontSize: '1rem', fontWeight: 800, color: '#fff' }}>
                    {node.title}
                  </h3>
                  <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                    {node.subtitle}
                  </p>
                  <div style={{ fontSize: '0.72rem', color: '#6b7080', background: 'rgba(8, 10, 16, 0.6)', padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                    <strong>Requisito:</strong> {node.prerequisite}
                  </div>
                </div>

                <button
                  onClick={() => setActiveHwModal(node)}
                  disabled={isActivated}
                  style={{
                    padding: '10px 16px', borderRadius: '10px',
                    background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.12)'),
                    color: isActivated ? '#3fb950' : '#e2e8f0', fontSize: '0.8rem', fontWeight: 700,
                    cursor: isActivated ? 'default' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {isActivated ? <CheckCircle2 size={15} /> : <ArrowRight size={15} />}
                  {isActivated ? 'Modulo Hardware Inizializzato' : node.actionText}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Standby Hardware Activation Modal Popup */}
      {activeHwModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', background: 'rgba(18, 20, 28, 0.95)',
            border: `1px solid ${activeHwModal.color}40`, borderRadius: '20px',
            padding: '28px', boxShadow: '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: activeHwModal.color }}>
              <activeHwModal.icon size={26} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                  {activeHwModal.title}
                </h2>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginTop: '2px' }}>
                  {activeHwModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#c0c4d0', lineHeight: 1.6, marginBottom: '20px' }}>
              {activeHwModal.details}
            </p>

            <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '24px', fontSize: '0.78rem', color: '#8b8fa3' }}>
              <div style={{ fontWeight: 700, color: '#fff', marginBottom: '4px' }}>📋 Requisito di Inizializzazione:</div>
              {activeHwModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveHwModal(null)}
                style={{ padding: '10px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
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
                  }, 1200);
                }}
                disabled={activatingHw === activeHwModal.id}
                style={{
                  padding: '10px 22px', borderRadius: '10px',
                  background: `linear-gradient(135deg, ${activeHwModal.color}, #00d2ff)`, border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}
              >
                {activatingHw === activeHwModal.id ? <Activity className="spin" size={15} /> : <Zap size={15} />}
                {activatingHw === activeHwModal.id ? 'Inizializzazione...' : 'Connetti & Attiva Nodo Hardware ⚡'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}