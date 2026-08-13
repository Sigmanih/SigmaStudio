import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Activity, Zap, HardDrive, Save, ChevronDown, ChevronUp, RotateCcw, Trash2,
  ShieldCheck, Sliders, Play, Pause, TrendingUp, BarChart2,
  Cpu, Thermometer, Flame, Gauge, AlertTriangle, Layers, CheckCircle2, ArrowRight
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import { useApp } from '../../contexts/AppContext';
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
  const { theme } = useApp();
  const isLight = theme === 'light';
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

  const totalVramGb = hw.multi_gpu?.total_vram_gb || (gpus.reduce((acc, g) => acc + (g.vram_total_gb || 0), 0)).toFixed(1);

  // Theme Design Tokens
  const cardBg = isLight ? '#fffdf9' : 'rgba(15, 23, 42, 0.75)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(0,0,0,0.06)' : '0 12px 40px rgba(0, 0, 0, 0.4)';
  const textPrimary = isLight ? '#111111' : '#ffffff';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subCardBg = isLight ? '#f9f6f0' : 'rgba(8, 10, 16, 0.6)';
  const subCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.04)';

  return (
    <div className="hardware-lab-container" style={{ padding: 0, position: 'relative', overflowY: 'auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
      
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
              Questa azione scaricherà tutti i modelli caricati in memoria video (VRAM) ed eseguità il riavvio del servizio Ollama. 
              Nessun dato andrà perso.
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button 
                className="hw-btn" 
                onClick={() => setShowRestartAlert(false)}
                disabled={restartingOllama}
                style={{ padding: '8px 16px', fontSize: '13px', background: isLight ? '#f2ede2' : undefined, color: textPrimary }}
              >
                Annulla
              </button>
              <button 
                className="hw-btn" 
                onClick={handleRestartOllama} 
                disabled={restartingOllama}
                style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', fontWeight: 800, fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {restartingOllama ? <Activity className="spin" size={15} /> : <RotateCcw size={15} />}
                {restartingOllama ? 'Svuotamento VRAM in corso...' : '⚡ Svuota VRAM & Riavvia Ollama'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hero Visual Banner matching Domotica Header Style */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: isLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/hardware_cluster_lab.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/hardware_cluster_lab.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)', 
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
              color: isLight ? '#ea580c' : '#00d2ff', 
              fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Zap size={14} /> CLUSTER GPU TELEMETRY & HARDWARE LAB
            </div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.4rem', fontWeight: 800, color: textPrimary, letterSpacing: '-0.3px', textShadow: 'none' }}>
              ⚡ Hardware & <span style={{
                color: isLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Cluster Telemetry Lab</span>
            </h1>
            <p style={{ margin: 0, fontSize: '0.82rem', color: isLight ? '#4b5563' : '#cbd5e0', lineHeight: 1.45 }}>
              Monitoraggio VRAM in tempo reale, allocazione dinamica dei pesi su GPU NVIDIA ed esecuzione parallela dei thread.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button 
              className="hw-btn"
              onClick={() => setShowRestartAlert(true)}
              title="Svuota la memoria VRAM/RAM scaricando tutti i modelli caricati da Ollama"
              style={{ fontSize: '0.82rem', padding: '10px 16px', borderRadius: '12px', border: '1px solid rgba(239, 68, 68, 0.45)', background: isLight ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.15)', color: isLight ? '#dc2626' : '#fca5a5', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RotateCcw size={15} color="#ef4444" />
              <span>Svuota VRAM / Riavvia Ollama</span>
            </button>

            <button 
              className={`hw-btn ${showCharts ? 'hw-btn-primary' : ''}`}
              onClick={() => setShowCharts(!showCharts)}
              title={showCharts ? 'Nascondi i grafici per compattare la vista' : 'Mostra i grafici storici in tempo reale'}
              style={{ fontSize: '0.82rem', padding: '10px 16px', borderRadius: '12px', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <BarChart2 size={15} color={showCharts ? '#fff' : (isLight ? '#c2410c' : '#00d2ff')} />
              {showCharts ? 'Nascondi Grafici Storici' : 'Mostra Grafici Storici'}
              {showCharts ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>

            <button 
              className="hw-btn" 
              onClick={() => setAutoRefresh(!autoRefresh)}
              title={autoRefresh ? 'Metti in pausa il refresh' : 'Riprendi refresh automatico'}
              style={{ fontSize: '0.82rem', padding: '10px 16px', borderRadius: '12px', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', background: isLight ? '#fffdf9' : undefined, border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : undefined, color: textPrimary }}
            >
              {autoRefresh ? <Pause size={14} color={isLight ? '#ea580c' : '#00d2ff'} /> : <Play size={14} />}
              {autoRefresh ? 'Pausa (2s)' : 'Riprendi'}
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>

        {/* Bottom Row: Compact Telemetry Stat Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', zIndex: 2 }}>
          
          {/* Card 1: VRAM & GPU */}
          <div style={{
            padding: '12px 16px', borderRadius: '14px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(2, 132, 199, 0.35)' : '1px solid rgba(0, 210, 255, 0.3)', 
            boxShadow: isLight ? '0 4px 18px rgba(2, 132, 199, 0.08)' : '0 4px 18px rgba(0, 210, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.68rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase', marginBottom: '4px' }}>
              GPU & VRAM ALLOCATA
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
              {gpus.length} GPU • {totalVramGb} GB
            </div>
            <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {gpus.map(g => g.name || `GPU ${g.index}`).join(', ') || 'NVIDIA Compute'}
            </div>
          </div>

          {/* Card 2: SYSTEM RAM */}
          <div style={{
            padding: '12px 16px', borderRadius: '14px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(22, 163, 74, 0.35)' : '1px solid rgba(16, 185, 129, 0.3)', 
            boxShadow: isLight ? '0 4px 18px rgba(22, 163, 74, 0.08)' : '0 4px 18px rgba(16, 185, 129, 0.1)'
          }}>
            <div style={{ fontSize: '0.68rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase', marginBottom: '4px' }}>
              SISTEMA RAM & DISCO
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.ram?.used_gb || hw.ram_used_gb || 0} / {hw.ram?.total_gb || hw.ram_gb || 0} GB
            </div>
            <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px' }}>
              RAM Utilizzata {hw.ram?.util_pct || hw.ram_pct || 0}% • Disco {hw.disk?.used_gb || 0} GB
            </div>
          </div>

          {/* Card 3: CPU THREADS */}
          <div style={{
            padding: '12px 16px', borderRadius: '14px',
            backgroundColor: cardBg,
            border: isLight ? '1px solid rgba(124, 58, 237, 0.35)' : '1px solid rgba(188, 140, 255, 0.3)', 
            boxShadow: isLight ? '0 4px 18px rgba(124, 58, 237, 0.08)' : '0 4px 18px rgba(188, 140, 255, 0.1)'
          }}>
            <div style={{ fontSize: '0.68rem', color: textMuted, fontWeight: 800, textTransform: 'uppercase', marginBottom: '4px' }}>
              CPU SYSTEM LOAD
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
              {hw.cpu?.util_pct ?? 0}% LOAD
            </div>
            <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px' }}>
              {hw.cpu?.logical_count || '?'} Thread Logici • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
            </div>
          </div>

        </div>

      {/* Main Cards Container */}
      <div className="gpu-cards-container" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

        {/* ==================================================================== */}
        {/* PROCESSI SULLA GPU — chi la sta occupando, e come chiuderlo          */}
        {/* ==================================================================== */}
        <div className="gpu-card" style={{
          padding: '16px 20px',
          backgroundColor: cardBg,
          border: gpuProcs.orfani > 0 ? '1px solid rgba(239, 68, 68, 0.45)' : cardBorder,
          boxShadow: cardShadow
        }}>
          <div className="gpu-card-header" style={{ marginBottom: gpuProcs.processes.length ? '12px' : 0 }}>
            <div className="gpu-title">
              <div className="gpu-index-pill" style={{ 
                background: isLight ? 'rgba(124, 58, 237, 0.12)' : 'rgba(168, 85, 247, 0.15)', 
                color: isLight ? '#7c3aed' : '#a855f7', 
                border: isLight ? '1px solid rgba(124, 58, 237, 0.35)' : '1px solid rgba(168, 85, 247, 0.3)', 
                padding: '2px 8px', 
                fontSize: '11px',
                fontWeight: 800
              }}>
                PID
              </div>
              <div>
                <div className="gpu-name" style={{ fontSize: '15px', color: textPrimary, fontWeight: 800 }}>Processi sulla GPU</div>
                <div className="gpu-bus-info" style={{ fontSize: '11px', color: textMuted }}>
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
                  <span style={{ fontWeight: 800, color: '#ef4444' }}>
                    {gpuProcs.orfani} orfan{gpuProcs.orfani === 1 ? 'o' : 'i'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {gpuProcs.processes.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {gpuProcs.processes.map(proc => {
                const isTraining = proc.kind === 'training';
                const accent = proc.orphan ? '#ef4444' : (isTraining ? (isLight ? '#0284c7' : '#00d2ff') : textMuted);
                return (
                  <div key={proc.pid} style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '10px 14px', borderRadius: '10px',
                    background: isLight 
                      ? (isTraining ? 'rgba(2, 132, 199, 0.08)' : '#f4efe4') 
                      : (isTraining ? 'rgba(0, 210, 255, 0.05)' : 'rgba(148, 163, 184, 0.04)'),
                    border: `1px solid ${proc.orphan ? 'rgba(239, 68, 68, 0.35)' : (isTraining ? (isLight ? 'rgba(2, 132, 199, 0.3)' : 'rgba(0, 210, 255, 0.2)') : (isLight ? 'rgba(190, 160, 110, 0.3)' : 'rgba(148, 163, 184, 0.12)'))}`
                  }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 800, fontSize: '13px', color: accent }}>
                          {proc.name || `PID ${proc.pid}`}
                        </span>
                        <span style={{ fontSize: '10px', color: textMuted }}>PID {proc.pid}</span>
                        {proc.job_id && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: isLight ? 'rgba(2, 132, 199, 0.15)' : 'rgba(0, 210, 255, 0.15)', color: isLight ? '#0284c7' : '#00d2ff', borderColor: isLight ? 'rgba(2, 132, 199, 0.35)' : 'rgba(0, 210, 255, 0.3)', fontWeight: 700 }}>
                            job {proc.job_id}
                          </span>
                        )}
                        {proc.orphan && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.35)', fontWeight: 700 }}>
                            ORFANO — il job risulta {proc.job_status}
                          </span>
                        )}
                        {proc.kind === 'esterno' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', color: textMuted }}>
                            esterno a Sigma
                          </span>
                        )}
                        {proc.kind === 'sigma' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: isLight ? 'rgba(22, 163, 74, 0.15)' : 'rgba(16, 185, 129, 0.15)', color: isLight ? '#16a34a' : '#10b981', borderColor: isLight ? 'rgba(22, 163, 74, 0.35)' : 'rgba(16, 185, 129, 0.3)', fontWeight: 700 }}>
                            Sigma Studio
                          </span>
                        )}
                        {proc.kind === 'sistema' && (
                          <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 8px', background: 'rgba(245, 158, 11, 0.15)', color: '#d97706', borderColor: 'rgba(245, 158, 11, 0.3)', fontWeight: 700 }}>
                            processo di Windows
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '10px', color: textMuted, marginTop: '3px' }}>
                        {(proc.gpus || []).map(g => g.name || `GPU ${g.index}`).join(' + ') || 'GPU sconosciuta'}
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
                          fontSize: '11px', padding: '6px 12px', flexShrink: 0,
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
                          fontWeight: 700
                        }}
                      >
                        <Trash2 size={12} color="#ef4444" />
                        <span>{killingPid === proc.pid ? 'Chiudo…' : 'Termina'}</span>
                      </button>
                    ) : (
                      <span style={{ fontSize: '10px', color: textMuted, flexShrink: 0 }}
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
        <div className="gpu-card" style={{ padding: '16px 20px', backgroundColor: cardBg, border: cardBorder, boxShadow: cardShadow }}>
          <div className="gpu-card-header" style={{ marginBottom: '14px' }}>
            <div className="gpu-title">
              <div className="gpu-index-pill" style={{ 
                background: isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(16, 185, 129, 0.15)', 
                color: isLight ? '#16a34a' : '#10b981', 
                border: isLight ? '1px solid rgba(22, 163, 74, 0.35)' : '1px solid rgba(16, 185, 129, 0.3)', 
                padding: '2px 8px', 
                fontSize: '11px',
                fontWeight: 800
              }}>
                SYS
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div className="gpu-name" style={{ fontSize: '15px', color: textPrimary, fontWeight: 800 }}>Sistema Principale (CPU & RAM)</div>
                  <span className="hw-badge" style={{ background: isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(16, 185, 129, 0.15)', color: isLight ? '#16a34a' : '#10b981', borderColor: isLight ? 'rgba(22, 163, 74, 0.35)' : 'rgba(16, 185, 129, 0.3)', fontSize: '10px', padding: '2px 8px', fontWeight: 700 }}>
                    SISTEMA
                  </span>
                </div>
                <div className="gpu-bus-info" style={{ fontSize: '11px', color: textMuted }}>
                  {hw.cpu?.logical_count || hw.cpu_count || '?'} Thread Logici ({hw.cpu?.physical_count || '?'} Cores) • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
                </div>
              </div>
            </div>

            <div className="gpu-header-badges">
              <div className="gpu-stat-badge" style={{ padding: '5px 12px', fontSize: '12px', background: isLight ? '#f4efe4' : undefined, border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : undefined }}>
                <Cpu size={14} color={isLight ? '#0284c7' : '#00d2ff'} />
                <span style={{ fontWeight: 800, color: isLight ? '#0284c7' : '#00d2ff' }}>CPU: {hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="gpu-stat-badge" style={{ padding: '5px 12px', fontSize: '12px', background: isLight ? '#f4efe4' : undefined, border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : undefined }}>
                <HardDrive size={14} color={isLight ? '#16a34a' : '#10b981'} />
                <span style={{ fontWeight: 800, color: isLight ? '#16a34a' : '#10b981' }}>RAM: {hw.ram?.used_gb || hw.ram_used_gb || 0} / {hw.ram?.total_gb || hw.ram_gb || 0} GB</span>
              </div>
            </div>
          </div>

          {/* 2-COLUMN SPLIT: LEFT = COMPUTE, RIGHT = MEMORY */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            
            {/* LEFT SIDE: CPU COMPUTE */}
            <div style={{ background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 242, 254, 0.04)', border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 242, 254, 0.15)', borderRadius: '12px', padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, fontSize: '12px', color: isLight ? '#0284c7' : '#00d2ff' }}>
                  <Cpu size={14} /> ⚡ COMPUTE (CPU System Load)
                </div>
                <span style={{ fontSize: '12px', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff' }}>{hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                <div className="metric-progress-bar bar-cyan" style={{ width: `${Math.min(100, hw.cpu?.util_pct ?? 0)}%` }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: textMuted }}>
                <span>Max Core Load: {hw.cpu?.max_core_pct || 0}%</span>
                <span>Frequenza: {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(2)} GHz` : 'N/A'}</span>
              </div>
            </div>

            {/* RIGHT SIDE: MEMORY & STORAGE */}
            <div style={{ background: isLight ? 'rgba(22, 163, 74, 0.06)' : 'rgba(16, 185, 129, 0.04)', border: isLight ? '1px solid rgba(22, 163, 74, 0.25)' : '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '12px', padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, fontSize: '12px', color: isLight ? '#16a34a' : '#10b981' }}>
                  <HardDrive size={14} /> 🧠 MEMORIA (System RAM & Disco)
                </div>
                <span style={{ fontSize: '12px', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981' }}>{hw.ram?.util_pct || hw.ram_pct || 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                <div className="metric-progress-bar" style={{ width: `${Math.min(100, hw.ram?.util_pct || hw.ram_pct || 0)}%`, background: 'linear-gradient(90deg, #10b981, #059669)' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: textMuted }}>
                <span>RAM Libera: {hw.ram?.free_gb || 0} GB</span>
                <span>Disco: {hw.disk?.used_gb || 0} / {hw.disk?.total_gb || 0} GB ({hw.disk?.util_pct || 0}%)</span>
              </div>
            </div>

          </div>

          {/* COLLAPSIBLE SYSTEM CHARTS */}
          {showCharts && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px', paddingTop: '16px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)' }}>
              <RealtimeTelemetryChart 
                data={systemHistory.cpu} 
                label="Storico Carico CPU (%)" 
                icon={Cpu}
                color={isLight ? '#0284c7' : '#00d2ff'} 
                unit="%" 
                maxVal={100} 
                height={80}
                isLight={isLight}
              />
              <RealtimeTelemetryChart 
                data={systemHistory.ram} 
                label="Storico RAM Utilizzata (GB)" 
                icon={HardDrive}
                color={isLight ? '#16a34a' : '#10b981'} 
                unit="GB" 
                maxVal={hw.ram?.total_gb || hw.ram_gb || 64} 
                height={80}
                isLight={isLight}
                formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
              />
            </div>
          )}
        </div>

        {/* ==================================================================== */}
        {/* MULTI-VENDOR GPU CARDS (LEFT = COMPUTE, RIGHT = VRAM) */}
        {/* ==================================================================== */}
        {gpus.length === 0 ? (
          <div className="gpu-card" style={{ textAlign: 'center', padding: '40px 20px', backgroundColor: cardBg, border: cardBorder }}>
            {loading ? (
              <>
                <Activity className="spin" size={32} color={isLight ? '#ea580c' : '#00d2ff'} style={{ margin: '0 auto 12px' }} />
                <div style={{ fontSize: '14px', color: textPrimary, fontWeight: 700 }}>Rilevamento telemetria hardware in corso...</div>
              </>
            ) : (
              <div style={{ color: textMuted, fontSize: '14px', fontWeight: 600 }}>
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
              <div key={idx} className="gpu-card" style={{ padding: '16px 20px', backgroundColor: cardBg, border: cardBorder, boxShadow: cardShadow }}>
                {/* GPU Card Top Title Bar */}
                <div className="gpu-card-header" style={{ marginBottom: '14px' }}>
                  <div className="gpu-title">
                    <div className="gpu-index-pill" style={{ 
                      padding: '2px 8px', 
                      fontSize: '11px',
                      background: isLight ? 'rgba(234, 88, 12, 0.12)' : undefined,
                      color: isLight ? '#ea580c' : undefined,
                      borderColor: isLight ? 'rgba(234, 88, 12, 0.35)' : undefined
                    }}>GPU {idx}</div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div className="gpu-name" style={{ fontSize: '15px', color: textPrimary, fontWeight: 800 }}>{gpu.name}</div>
                        <span className="hw-badge" style={{ 
                          background: isLight ? 'rgba(2, 132, 199, 0.12)' : `${gpu.vendor_color || '#00f2fe'}18`, 
                          color: isLight ? '#0284c7' : (gpu.vendor_color || '#00f2fe'),
                          borderColor: isLight ? 'rgba(2, 132, 199, 0.3)' : `${gpu.vendor_color || '#00f2fe'}44`,
                          fontSize: '10px',
                          padding: '2px 8px',
                          fontWeight: 700
                        }}>
                          {gpu.vendor || 'GPU'}
                        </span>
                      </div>
                      <div className="gpu-bus-info" style={{ fontSize: '11px', color: textMuted }}>
                        Driver v{gpu.driver_version || 'N/A'} • Compute Cap {gpu.compute_cap || 'v9.0+'} • Temp {gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'} • Potenza {pwrDraw}W
                      </div>
                    </div>
                  </div>

                  <div className="gpu-header-badges">
                    <div className="gpu-stat-badge" style={{ padding: '5px 12px', fontSize: '12px', background: isLight ? '#f4efe4' : undefined, border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : undefined }}>
                      <Thermometer size={14} color="#ea580c" />
                      <span style={{ color: textPrimary, fontWeight: 700 }}>{gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'}</span>
                    </div>
                    <div className="gpu-stat-badge" style={{ padding: '5px 12px', fontSize: '12px', background: isLight ? '#f4efe4' : undefined, border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : undefined }}>
                      <Flame size={14} color="#ef4444" />
                      <span style={{ color: textPrimary, fontWeight: 700 }}>{pwrDraw}W</span>
                    </div>
                  </div>
                </div>

                {/* 2-COLUMN SPLIT: LEFT = COMPUTE, RIGHT = VRAM */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  
                  {/* LEFT SIDE: GPU COMPUTE */}
                  <div style={{ background: isLight ? 'rgba(124, 58, 237, 0.06)' : 'rgba(188, 140, 255, 0.04)', border: isLight ? '1px solid rgba(124, 58, 237, 0.25)' : '1px solid rgba(188, 140, 255, 0.18)', borderRadius: '12px', padding: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, fontSize: '12px', color: isLight ? '#7c3aed' : '#bc8cff' }}>
                        <Gauge size={14} /> ⚡ COMPUTE (Utilizzo GPU)
                      </div>
                      <span style={{ fontSize: '12px', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff' }}>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                      <div className="metric-progress-bar bar-purple" style={{ width: `${utilPct}%` }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: textMuted }}>
                      <span>Stato: {utilPct > 80 ? '🔥 Alto Carico' : utilPct > 20 ? '⚡ Attivo' : '💤 Idle'}</span>
                      <span>Potenza: {pwrDraw}W / {pwrLimit > 0 ? `${pwrLimit}W` : 'N/A'}</span>
                    </div>
                  </div>

                  {/* RIGHT SIDE: GPU VRAM MEMORY */}
                  <div style={{ background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 210, 255, 0.04)', border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 210, 255, 0.18)', borderRadius: '12px', padding: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, fontSize: '12px', color: isLight ? '#0284c7' : '#00d2ff' }}>
                        <HardDrive size={14} /> 🧠 MEMORIA VRAM
                      </div>
                      <span style={{ fontSize: '12px', fontWeight: 900, color: isLight ? '#0284c7' : '#00d2ff' }}>{vramUsed} / {vramTotal} MB ({vramPct}%)</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '8px', marginBottom: '8px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                      <div className="metric-progress-bar bar-cyan" style={{ width: `${vramPct}%` }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: textMuted }}>
                      <span>Libera: {gpu.vram_free_mb || Math.max(0, vramTotal - vramUsed)} MB</span>
                      <span>VRAM Totale: {gpu.vram_total_gb || (vramTotal / 1024).toFixed(1)} GB</span>
                    </div>
                  </div>

                </div>

                {showCharts && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px', paddingTop: '16px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)' }}>
                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Storico Compute GPU (%)" 
                      icon={Cpu}
                      color={isLight ? '#7c3aed' : '#bc8cff'} 
                      unit="%" 
                      maxVal={100} 
                      height={80}
                      isLight={isLight}
                    />
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="Storico Occupazione VRAM (MB)" 
                      icon={HardDrive}
                      color={isLight ? '#0284c7' : '#00d2ff'} 
                      unit="MB" 
                      maxVal={vramTotal} 
                      height={80}
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

      {/* Multi-GPU Tuning Controls */}
      <div className="hw-section" style={{ marginTop: '20px', background: cardBg, border: cardBorder, boxShadow: cardShadow }}>
        <div className="hw-section-title">
          <Sliders size={18} color={isLight ? '#ea580c' : '#00f2fe'} />
          <span style={{ fontSize: '15px', color: textPrimary, fontWeight: 800 }}>Configurazione Multi-GPU & Parallelismo Ollama</span>
        </div>

        <div className="hw-form-grid">
          <div className="hw-form-group">
            <label style={{ color: textPrimary, fontWeight: 700 }}>
              <span>CUDA_VISIBLE_DEVICES</span>
              <span style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>Target GPU</span>
            </label>
            <select 
              className="hw-select" 
              value={cudaDevices} 
              onChange={(e) => setCudaDevices(e.target.value)}
              style={{
                background: isLight ? '#ffffff' : undefined,
                color: textPrimary,
                borderColor: isLight ? 'rgba(190, 160, 110, 0.4)' : undefined
              }}
            >
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
            <label style={{ color: textPrimary, fontWeight: 700 }}>
              <span>OLLAMA_NUM_PARALLEL</span>
              <span style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>Slot Paralleli</span>
            </label>
            <select 
              className="hw-select" 
              value={numParallel} 
              onChange={(e) => setNumParallel(Number(e.target.value))}
              style={{
                background: isLight ? '#ffffff' : undefined,
                color: textPrimary,
                borderColor: isLight ? 'rgba(190, 160, 110, 0.4)' : undefined
              }}
            >
              <option value={1}>1 — Singolo stream</option>
              <option value={2}>2 — 2 stream paralleli</option>
              <option value={4}>4 — 4 stream paralleli (Ottimale Multi-Agenti)</option>
              <option value={8}>8 — 8 stream paralleli (Massimo throughput)</option>
            </select>
          </div>

          <div className="hw-form-group">
            <label style={{ color: textPrimary, fontWeight: 700 }}>
              <span>OLLAMA_MAX_LOADED_MODELS</span>
              <span style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>Modelli in VRAM</span>
            </label>
            <select 
              className="hw-select" 
              value={maxLoaded} 
              onChange={(e) => setMaxLoaded(Number(e.target.value))}
              style={{
                background: isLight ? '#ffffff' : undefined,
                color: textPrimary,
                borderColor: isLight ? 'rgba(190, 160, 110, 0.4)' : undefined
              }}
            >
              <option value={1}>1 modello alla volta</option>
              <option value={2}>2 modelli contemporaneamente (Consigliato)</option>
              <option value={3}>3 modelli contemporaneamente</option>
            </select>
          </div>

          <div className="hw-form-group">
            <label style={{ color: textPrimary, fontWeight: 700 }}>
              <span>GPU Preferita Training Lab</span>
              <span style={{ color: isLight ? '#c2410c' : '#00d2ff' }}>Fine-Tuning</span>
            </label>
            <select 
              className="hw-select" 
              value={preferredGpu} 
              onChange={(e) => setPreferredGpu(e.target.value)}
              style={{
                background: isLight ? '#ffffff' : undefined,
                color: textPrimary,
                borderColor: isLight ? 'rgba(190, 160, 110, 0.4)' : undefined
              }}
            >
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

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
          <button 
            className="hw-btn hw-btn-primary" 
            onClick={handleSaveConfig} 
            disabled={saving} 
            style={{ 
              fontSize: '13px', 
              padding: '10px 20px', 
              borderRadius: '10px',
              fontWeight: 800,
              background: isLight ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' : undefined
            }}
          >
            <Save size={15} />
            {saving ? 'Salvataggio in corso...' : 'Applica e Salva Impostazioni Multi-GPU'}
          </button>
        </div>
      </div>

      {/* ── CARD GRIGIE — HARDWARE & NODI IN STANDBY ── */}
      <div style={{ marginTop: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <div style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '6px', 
            padding: '4px 12px', 
            borderRadius: '12px', 
            background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(255, 255, 255, 0.06)', 
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(255, 255, 255, 0.1)', 
            color: isLight ? '#9a3412' : '#8b8fa3', 
            fontSize: '0.72rem', 
            fontWeight: 800, 
            textTransform: 'uppercase', 
            letterSpacing: '1px', 
            marginBottom: '8px' 
          }}>
            <Layers size={13} /> ESPANSIONI CLUSTER & ACCELERATORI HARDWARE IN ATTESA
          </div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: textPrimary }}>
            ⚡ Hardware & Nodi di Calcolo Avanzati in Standby (Da Attivare)
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: textMuted }}>
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
                  backgroundColor: isLight ? '#fffdf9' : (isActivated ? 'rgba(14, 17, 25, 0.85)' : 'rgba(14, 17, 25, 0.4)'),
                  border: isLight 
                    ? (isActivated ? `1px solid ${node.color}` : '1px solid rgba(190, 160, 110, 0.35)') 
                    : ('1px solid ' + (isActivated ? `${node.color}40` : 'rgba(255, 255, 255, 0.08)')),
                  boxShadow: isLight 
                    ? (isActivated ? `0 8px 32px ${node.color}20` : '0 4px 16px rgba(0,0,0,0.04)') 
                    : (isActivated ? `0 8px 32px ${node.color}15` : 'none'),
                  display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                  gap: '16px', opacity: isActivated ? 1 : (isLight ? 0.9 : 0.72),
                  filter: isActivated ? 'none' : (isLight ? 'none' : 'grayscale(35%)'),
                  transition: 'all 0.3s ease'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{
                      width: '44px', height: '44px', borderRadius: '12px',
                      background: isActivated ? `${node.color}25` : (isLight ? '#f4efe4' : 'rgba(255, 255, 255, 0.04)'),
                      border: '1px solid ' + (isActivated ? node.color : (isLight ? 'rgba(190, 160, 110, 0.35)' : 'rgba(255,255,255,0.08)')),
                      color: isActivated ? node.color : (isLight ? '#9a3412' : '#8b8fa3'),
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <IconComp size={22} />
                    </div>

                    <span style={{
                      fontSize: '0.68rem', fontWeight: 800,
                      color: isActivated ? '#16a34a' : textMuted,
                      background: isActivated ? (isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(63, 185, 80, 0.15)') : (isLight ? '#f4efe4' : 'rgba(255, 255, 255, 0.06)'),
                      border: '1px solid ' + (isActivated ? (isLight ? 'rgba(22, 163, 74, 0.35)' : 'rgba(63, 185, 80, 0.3)') : (isLight ? 'rgba(190, 160, 110, 0.35)' : 'rgba(255, 255, 255, 0.1)')),
                      padding: '3px 10px', borderRadius: '20px', letterSpacing: '0.5px'
                    }}>
                      {isActivated ? 'NODO HARDWARE ATTIVO ⚡' : node.statusBadge}
                    </span>
                  </div>

                  <h3 style={{ margin: '0 0 6px 0', fontSize: '1rem', fontWeight: 800, color: textPrimary }}>
                    {node.title}
                  </h3>
                  <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: textSecondary, lineHeight: 1.5, fontWeight: isLight ? 500 : 400 }}>
                    {node.subtitle}
                  </p>
                  <div style={{ fontSize: '0.72rem', color: textPrimary, background: subCardBg, padding: '8px 12px', borderRadius: '8px', border: subCardBorder }}>
                    <strong style={{ color: isLight ? '#9a3412' : '#fff' }}>Requisito:</strong> {node.prerequisite}
                  </div>
                </div>

                <button
                  onClick={() => setActiveHwModal(node)}
                  disabled={isActivated}
                  style={{
                    padding: '10px 16px', borderRadius: '10px',
                    background: isActivated 
                      ? (isLight ? 'rgba(22, 163, 74, 0.15)' : 'rgba(63, 185, 80, 0.15)') 
                      : (isLight ? '#f4efe4' : 'rgba(255, 255, 255, 0.06)'),
                    border: '1px solid ' + (isActivated 
                      ? (isLight ? 'rgba(22, 163, 74, 0.4)' : 'rgba(63, 185, 80, 0.3)') 
                      : (isLight ? 'rgba(190, 160, 110, 0.4)' : 'rgba(255, 255, 255, 0.12)')),
                    color: isActivated ? (isLight ? '#16a34a' : '#3fb950') : textPrimary, 
                    fontSize: '0.8rem', 
                    fontWeight: 800,
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
          background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', 
            background: isLight ? '#fffdf9' : 'rgba(18, 20, 28, 0.95)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : `1px solid ${activeHwModal.color}40`, 
            borderRadius: '20px',
            padding: '28px', 
            boxShadow: isLight ? '0 20px 60px rgba(0,0,0,0.25)' : '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: activeHwModal.color }}>
              <activeHwModal.icon size={26} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.2rem', color: textPrimary, fontWeight: 800 }}>
                  {activeHwModal.title}
                </h2>
                <div style={{ fontSize: '0.74rem', color: textMuted, marginTop: '2px' }}>
                  {activeHwModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.84rem', color: textSecondary, lineHeight: 1.6, marginBottom: '20px', fontWeight: isLight ? 500 : 400 }}>
              {activeHwModal.details}
            </p>

            <div style={{ padding: '12px 16px', borderRadius: '12px', background: isLight ? '#f4efe4' : 'rgba(8, 10, 16, 0.8)', border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.08)', marginBottom: '24px', fontSize: '0.78rem', color: textPrimary }}>
              <div style={{ fontWeight: 800, color: isLight ? '#9a3412' : '#fff', marginBottom: '4px' }}>📋 Requisito di Inizializzazione:</div>
              {activeHwModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveHwModal(null)}
                style={{ padding: '10px 18px', borderRadius: '10px', background: isLight ? '#f4efe4' : 'rgba(255,255,255,0.06)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.1)', color: textPrimary, cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700 }}
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
                  background: isLight 
                    ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                    : `linear-gradient(135deg, ${activeHwModal.color}, #00d2ff)`, 
                  border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '8px',
                  boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.3)' : undefined
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
    </div>
  );
}