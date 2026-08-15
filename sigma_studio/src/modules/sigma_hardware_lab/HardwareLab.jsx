import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Cpu, HardDrive, Zap, Sliders, RotateCcw, AlertTriangle,
  Play, Pause, ChevronRight, BarChart2,
  Trash2, ShieldCheck, Thermometer, Flame, Gauge, Sparkles,
  Layers, CheckCircle2, Activity, Search, Terminal,
  RefreshCw, Info, X, Power, ArrowUpRight, Wifi, ArrowDown, ArrowUp, Database
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
    statusBadge: 'STANDBY',
  },
  {
    id: 'vllm_engine',
    title: 'vLLM PagedAttention Cluster',
    subtitle: 'Motore di inferenza avanzato a memoria paginata per token generation ultra-rapida.',
    icon: Activity,
    color: '#bc8cff',
    statusBadge: 'STANDBY',
  },
  {
    id: 'whisper_npu',
    title: 'Acceleratore Audio NPU & DirectML',
    subtitle: 'Trascrizione e sintesi vocale locale a latenza zero tramite NPU Intel/AMD o DirectML.',
    icon: Cpu,
    color: '#10b981',
    statusBadge: 'STANDBY',
  },
  {
    id: 'comfyui_worker',
    title: 'Nodo di Calcolo ComfyUI Creativo',
    subtitle: 'Cluster dedicato alla generazione di immagini SDXL e modelli 3D in background.',
    icon: Layers,
    color: '#ea580c',
    statusBadge: 'STANDBY',
  }
];

export default function HardwareLab({ addToast }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  const [showRestartAlert, setShowRestartAlert] = useState(false);
  const [restartingOllama, setRestartingOllama] = useState(false);

  // Selected device for inspector
  const [selectedDeviceId, setSelectedDeviceId] = useState('gpu_0');

  // Selected chart tab in UX inspector
  const [activeChartType, setActiveChartType] = useState('compute'); // 'compute' | 'vram' | 'temp' | 'power' | 'net_down' | 'disk_io'

  // GPU processes & Console filters
  const [gpuProcs, setGpuProcs] = useState({ processes: [], orfani: 0 });
  const [killingPid, setKillingPid] = useState(null);
  const [procSearch, setProcSearch] = useState('');
  const [procModuleFilter, setProcModuleFilter] = useState('all');

  // History buffers
  const [historyData, setHistoryData] = useState({});
  const historyRef = useRef({});
  const [systemHistory, setSystemHistory] = useState({ cpu: [], ram: [], net_down: [], net_up: [], disk_read: [], disk_write: [] });
  const systemHistoryRef = useRef({ cpu: [], ram: [], net_down: [], net_up: [], disk_read: [], disk_write: [] });

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

            if (newVram.length > 30) newVram.shift();
            if (newCompute.length > 30) newCompute.shift();
            if (newTemp.length > 30) newTemp.shift();
            if (newPower.length > 30) newPower.shift();

            currentHist[idx] = { vram: newVram, compute: newCompute, temp: newTemp, power: newPower };
          });

          historyRef.current = currentHist;
          setHistoryData(currentHist);

          // 2. Accumulate System, Network & Disk History
          const cpuVal = Number(json.hardware?.cpu?.usage_pct) || 0;
          const ramVal = Number(json.hardware?.ram?.used_gb) || 0;
          const netDown = Number(json.hardware?.network?.download_kbps) || 0;
          const netUp = Number(json.hardware?.network?.upload_kbps) || 0;
          const diskRead = Number(json.hardware?.storage?.read_mbps) || 0;
          const diskWrite = Number(json.hardware?.storage?.write_mbps) || 0;

          const newSysCpu = [...systemHistoryRef.current.cpu, cpuVal];
          const newSysRam = [...systemHistoryRef.current.ram, ramVal];
          const newNetDown = [...systemHistoryRef.current.net_down, netDown];
          const newNetUp = [...systemHistoryRef.current.net_up, netUp];
          const newDiskR = [...systemHistoryRef.current.disk_read, diskRead];
          const newDiskW = [...systemHistoryRef.current.disk_write, diskWrite];

          if (newSysCpu.length > 30) newSysCpu.shift();
          if (newSysRam.length > 30) newSysRam.shift();
          if (newNetDown.length > 30) newNetDown.shift();
          if (newNetUp.length > 30) newNetUp.shift();
          if (newDiskR.length > 30) newDiskR.shift();
          if (newDiskW.length > 30) newDiskW.shift();

          const updatedSysHist = {
            cpu: newSysCpu,
            ram: newSysRam,
            net_down: newNetDown,
            net_up: newNetUp,
            disk_read: newDiskR,
            disk_write: newDiskW
          };
          systemHistoryRef.current = updatedSysHist;
          setSystemHistory(updatedSysHist);
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
        body: JSON.stringify({ pid: proc.pid })
      });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(json.message || `Processo #${proc.pid} terminato.`, 'success');
      } else if (addToast) {
        addToast(json.error || `Impossibile chiudere il processo #${proc.pid}.`, 'error');
      }
      fetchGpuProcesses();
      fetchHardwareStatus();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
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

  const handleRestartOllama = async () => {
    setRestartingOllama(true);
    try {
      const res = await fetch('/api/hardware/restart-ollama', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(`🧹 ${json.message}`, 'success');
        fetchHardwareStatus();
        fetchGpuProcesses();
      } else if (addToast) {
        addToast(`❌ Errore: ${json.error}`, 'error');
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
      const res = await fetch('/api/hardware/restart-ollama', { method: 'POST' });
      if (res.ok) {
        if (addToast) addToast('⚡ VRAM Cache liberata con successo.', 'success');
        fetchHardwareStatus();
        fetchGpuProcesses();
      }
    } catch (e) {
      console.error("VRAM clear error:", e);
    }
  };

  const hw = data?.hardware || {};
  const gpus = hw.gpu || [];
  const cpu = hw.cpu || {};
  const ram = hw.ram || {};
  const storage = hw.storage || {};
  const network = hw.network || {};
  const disks = storage.disks || [];

  // Module filter options for Process Table
  const moduleCategories = useMemo(() => {
    const set = new Set();
    gpuProcs.processes.forEach(p => {
      if (p.module_name) set.add(p.module_name);
    });
    return Array.from(set);
  }, [gpuProcs.processes]);

  // Filtered processes in Console
  const filteredProcesses = useMemo(() => {
    return gpuProcs.processes.filter(p => {
      const q = procSearch.toLowerCase().trim();
      const matchSearch = !q ||
        String(p.pid).includes(q) ||
        p.name?.toLowerCase().includes(q) ||
        p.module_name?.toLowerCase().includes(q) ||
        p.user?.toLowerCase().includes(q) ||
        p.assigned_gpu?.toLowerCase().includes(q);

      if (!matchSearch) return false;
      if (procModuleFilter === 'all') return true;
      if (procModuleFilter === 'orphans') return p.is_orphan || p.orphan;
      if (procModuleFilter === 'gpu_only') return (p.vram_mb || 0) > 50;
      return p.module_name === procModuleFilter;
    });
  }, [gpuProcs.processes, procSearch, procModuleFilter]);

  // Selected device resolution for right pane inspector
  const selectedDevice = useMemo(() => {
    if (selectedDeviceId === 'cpu_sys') {
      return {
        id: 'cpu_sys',
        type: 'CPU & Host RAM',
        name: cpu.name || 'AMD Ryzen Multi-Core Processor',
        subtitle: `${cpu.cores_physical || 8} Core Fisici • ${cpu.cores_logical || 16} Thread • ${cpu.freq_mhz || 3800} MHz`,
        availableCharts: [
          { id: 'compute', label: 'Carico CPU', icon: Cpu, color: '#00d2ff', unit: '%', max: 100, data: systemHistory.cpu },
          { id: 'vram', label: 'RAM Host', icon: HardDrive, color: '#10b981', unit: 'GB', max: ram.total_gb || 96, data: systemHistory.ram, format: v => `${typeof v === 'number' ? v.toFixed(1) : v} GB` },
        ],
        metrics: [
          { label: 'Carico CPU', val: `${cpu.usage_pct ?? 0}%`, color: '#00d2ff', progress: cpu.usage_pct ?? 0 },
          { label: 'RAM Occupata', val: `${ram.used_gb || 0} / ${ram.total_gb || 0} GB`, color: '#10b981', progress: ram.usage_pct ?? 0 },
          { label: 'RAM Libera', val: `${ram.free_gb || 0} GB`, color: '#bc8cff' },
          { label: 'Frequenza', val: `${cpu.freq_mhz || 3800} MHz`, color: '#ffb86c' }
        ]
      };
    }

    if (selectedDeviceId === 'storage_sys') {
      return {
        id: 'storage_sys',
        type: 'Storage & Drive Fisici',
        name: `Storage di Sistema (${disks.length} Partizioni)`,
        subtitle: `Capacità Totale: ${storage.total_gb || 3800} GB • Libero: ${storage.free_gb || 1900} GB`,
        availableCharts: [
          { id: 'disk_read', label: 'Lettura Disco', icon: HardDrive, color: '#00d2ff', unit: 'MB/s', max: 500, data: systemHistory.disk_read },
          { id: 'disk_write', label: 'Scrittura Disco', icon: HardDrive, color: '#ffb86c', unit: 'MB/s', max: 500, data: systemHistory.disk_write },
        ],
        metrics: [
          { label: 'Spazio Totale', val: `${storage.total_gb || 0} GB`, color: '#00d2ff' },
          { label: 'Spazio Libero', val: `${storage.free_gb || 0} GB`, color: '#10b981' },
          { label: 'Lettura I/O', val: `${storage.read_mbps || 0} MB/s`, color: '#bc8cff' },
          { label: 'Scrittura I/O', val: `${storage.write_mbps || 0} MB/s`, color: '#ffb86c' }
        ]
      };
    }

    if (selectedDeviceId === 'network_sys') {
      return {
        id: 'network_sys',
        type: 'Telemetria di Rete',
        name: 'Interfaccia di Rete & Connettività',
        subtitle: `${network.status || 'Gigabit Ethernet / Wi-Fi'} • Inviati: ${network.total_sent_mb || 0} MB • Ricevuti: ${network.total_recv_mb || 0} MB`,
        availableCharts: [
          { id: 'net_down', label: 'Download Rate', icon: ArrowDown, color: '#10b981', unit: 'KB/s', max: 10000, data: systemHistory.net_down },
          { id: 'net_up', label: 'Upload Rate', icon: ArrowUp, color: '#00d2ff', unit: 'KB/s', max: 5000, data: systemHistory.net_up },
        ],
        metrics: [
          { label: 'Download Live', val: `${network.download_kbps || 0} KB/s`, color: '#10b981' },
          { label: 'Upload Live', val: `${network.upload_kbps || 0} KB/s`, color: '#00d2ff' },
          { label: 'Dati Ricevuti', val: `${network.total_recv_mb || 0} MB`, color: '#bc8cff' },
          { label: 'Dati Inviati', val: `${network.total_sent_mb || 0} MB`, color: '#ffb86c' }
        ]
      };
    }

    const gpuIdx = parseInt(selectedDeviceId.replace('gpu_', ''), 10);
    const targetGpu = gpus.find(g => g.index === gpuIdx) || gpus[0];
    if (targetGpu) {
      const hist = historyData[targetGpu.index] || { vram: [], compute: [], temp: [], power: [] };
      return {
        id: `gpu_${targetGpu.index}`,
        type: targetGpu.type || 'NVIDIA Dedicated GPU',
        name: targetGpu.name,
        subtitle: `Dispositivo #${targetGpu.index} • ${targetGpu.is_integrated ? 'APU Integrata su Ryzen' : 'GPU Dedicata CUDA'}`,
        availableCharts: [
          { id: 'compute', label: 'Compute GPU', icon: Gauge, color: '#bc8cff', unit: '%', max: 100, data: hist.compute },
          { id: 'vram', label: 'VRAM Allocata', icon: HardDrive, color: '#00d2ff', unit: 'MB', max: targetGpu.vram_total_mb || 16384, data: hist.vram, format: v => `${typeof v === 'number' ? Math.round(v) : v} MB` },
          { id: 'temp', label: 'Temperatura', icon: Thermometer, color: targetGpu.temp_c > 75 ? '#ef4444' : '#10b981', unit: '°C', max: 100, data: hist.temp, format: v => `${typeof v === 'number' ? v.toFixed(1) : v}°C` },
          { id: 'power', label: 'Potenza Elettrica', icon: Zap, color: '#ffb86c', unit: 'Watt', max: 300, data: hist.power, format: v => `${typeof v === 'number' ? v.toFixed(1) : v} W` },
        ],
        metrics: [
          { label: 'Memoria VRAM', val: `${targetGpu.vram_used_mb} / ${targetGpu.vram_total_mb} MB`, color: '#00d2ff', progress: targetGpu.vram_usage_pct },
          { label: 'GPU Compute', val: `${targetGpu.gpu_util_pct}%`, color: '#bc8cff', progress: targetGpu.gpu_util_pct },
          { label: 'Temperatura', val: `${targetGpu.temp_c}°C`, color: targetGpu.temp_c > 75 ? '#ef4444' : '#10b981' },
          { label: 'Consumo Elettrico', val: `${targetGpu.power_draw_w} W`, color: '#ffb86c' }
        ]
      };
    }

    return null;
  }, [selectedDeviceId, cpu, ram, storage, network, disks, gpus, historyData, systemHistory]);

  // Adjust active chart tab if not available for currently selected device
  useEffect(() => {
    if (selectedDevice?.availableCharts && !selectedDevice.availableCharts.some(c => c.id === activeChartType)) {
      setActiveChartType(selectedDevice.availableCharts[0].id);
    }
  }, [selectedDevice, activeChartType]);

  // Design Tokens
  const cardBg = isLight ? '#fffdf9' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(0,0,0,0.05)' : '0 12px 36px rgba(0, 0, 0, 0.45)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subCardBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';

  // Active chart object
  const currentChart = selectedDevice?.availableCharts?.find(c => c.id === activeChartType) || selectedDevice?.availableCharts?.[0];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100%',
      backgroundColor: isLight ? '#f4efe4' : '#07090e',
      color: textPrimary,
      padding: '20px 24px',
      gap: '20px',
      boxSizing: 'border-box'
    }}>
      {/* 1. HEADER & GLOBAL ACTIONS */}
      <div style={{
        padding: '16px 20px',
        borderRadius: '16px',
        background: isLight
          ? 'linear-gradient(135deg, #ffffff 0%, #faf6ec 100%)'
          : 'linear-gradient(135deg, rgba(13, 16, 25, 0.95) 0%, rgba(20, 26, 42, 0.85) 100%)',
        border: cardBorder,
        boxShadow: cardShadow,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '46px', height: '46px', borderRadius: '12px',
            background: 'radial-gradient(circle at 30% 30%, rgba(0, 242, 254, 0.25), rgba(0, 210, 255, 0.05))',
            border: '1px solid rgba(0, 242, 254, 0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 20px rgba(0, 242, 254, 0.2)'
          }}>
            <Zap size={22} color="#00d2ff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.3px', color: textPrimary }}>
                Hardware Lab & <span style={{ color: '#00d2ff' }}>Cluster Telemetry</span>
              </h1>
              <span style={{
                fontSize: '0.66rem', padding: '2px 8px', borderRadius: '12px',
                background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)',
                fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px'
              }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
                {gpus.length} GPU • {ram.total_gb || 94} GB RAM • {disks.length} Dischi
              </span>
            </div>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.75rem', color: textMuted }}>
              Telemetria in tempo reale: GPU, CPU, RAM, Hard Disk, Rete e tracciamento processi per modulo.
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={handleClearVramMcp}
            title="Svuota la cache VRAM GPU"
            style={{
              fontSize: '0.74rem', padding: '7px 12px', borderRadius: '8px',
              border: '1px solid rgba(0, 210, 255, 0.4)',
              background: 'rgba(0, 210, 255, 0.12)', color: isLight ? '#0284c7' : '#00d2ff',
              fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
            }}
          >
            <Zap size={13} /> Scarica VRAM
          </button>

          <button
            onClick={() => setShowRestartAlert(true)}
            title="Riavvia e ripulisci il runtime VRAM"
            style={{
              fontSize: '0.74rem', padding: '7px 12px', borderRadius: '8px',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
              fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
            }}
          >
            <RotateCcw size={13} /> Svuota Memoria
          </button>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            style={{
              fontSize: '0.74rem', padding: '7px 12px', borderRadius: '8px',
              border: subCardBorder,
              background: autoRefresh ? (isLight ? '#111827' : '#00d2ff') : subCardBg,
              color: autoRefresh ? '#ffffff' : textPrimary,
              fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
            }}
          >
            {autoRefresh ? <Pause size={13} /> : <Play size={13} />}
            {autoRefresh ? 'Live (2s)' : 'In Pausa'}
          </button>
        </div>
      </div>

      {/* 2. ROW-BASED HARDWARE MASTER LIST (LEFT) + UX CHART INSPECTOR (RIGHT) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.15fr) minmax(0, 0.85fr)',
        gap: '18px'
      }}>
        {/* LEFT COLUMN: INTERACTIVE HARDWARE DEVICES (ROW-BY-ROW) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', letterSpacing: '0.8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} color="#00d2ff" /> DISPOSITIVI & RISORSE DISPONIBILI ({gpus.length + 3})
          </div>

          {/* ROW 1: CPU & RAM HOST */}
          <div
            onClick={() => setSelectedDeviceId('cpu_sys')}
            style={{
              padding: '13px 16px', borderRadius: '12px',
              background: selectedDeviceId === 'cpu_sys' ? (isLight ? '#ffffff' : 'rgba(0, 210, 255, 0.08)') : cardBg,
              border: selectedDeviceId === 'cpu_sys' ? '1.5px solid #00d2ff' : cardBorder,
              boxShadow: selectedDeviceId === 'cpu_sys' ? '0 0 20px rgba(0, 210, 255, 0.15)' : cardShadow,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
              transition: 'all 0.2s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
              <div style={{
                width: '38px', height: '38px', borderRadius: '10px',
                background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Cpu size={18} color="#10b981" />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                    {cpu.name || 'AMD Ryzen Host Processor'}
                  </span>
                  <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 700 }}>
                    CPU & RAM
                  </span>
                </div>
                <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                  {cpu.cores_physical || 8} Core • {cpu.cores_logical || 16} Thread • {cpu.freq_mhz || 3800} MHz
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>CARICO CPU</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
                  {cpu.usage_pct ?? 0}%
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>RAM HOST</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                  {ram.used_gb || 0} / {ram.total_gb || 0} GB
                </div>
              </div>
              <ChevronRight size={18} color={selectedDeviceId === 'cpu_sys' ? '#00d2ff' : textMuted} />
            </div>
          </div>

          {/* ROWS FOR GPUS */}
          {gpus.map(gpu => {
            const isSelected = selectedDeviceId === `gpu_${gpu.index}`;
            const isIntegrated = gpu.is_integrated;

            return (
              <div
                key={gpu.index}
                onClick={() => setSelectedDeviceId(`gpu_${gpu.index}`)}
                style={{
                  padding: '13px 16px', borderRadius: '12px',
                  background: isSelected ? (isLight ? '#ffffff' : 'rgba(0, 210, 255, 0.08)') : cardBg,
                  border: isSelected ? '1.5px solid #00d2ff' : cardBorder,
                  boxShadow: isSelected ? '0 0 20px rgba(0, 210, 255, 0.15)' : cardShadow,
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                  <div style={{
                    width: '38px', height: '38px', borderRadius: '10px',
                    background: isIntegrated ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                    border: isIntegrated ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Zap size={18} color={isIntegrated ? '#ea580c' : '#00d2ff'} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {gpu.name}
                      </span>
                      <span style={{
                        fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
                        background: isIntegrated ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 210, 255, 0.15)',
                        color: isIntegrated ? '#ea580c' : '#00d2ff', fontWeight: 700
                      }}>
                        GPU {gpu.index}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                      {gpu.type || (isIntegrated ? 'AMD APU' : 'NVIDIA CUDA')} • {gpu.temp_c}°C • {gpu.power_draw_w}W
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>VRAM ALLOCATA</div>
                    <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
                      {gpu.vram_used_mb} / {gpu.vram_total_mb} MB
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>UTILIZZO GPU</div>
                    <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
                      {gpu.gpu_util_pct}%
                    </div>
                  </div>
                  <ChevronRight size={18} color={isSelected ? '#00d2ff' : textMuted} />
                </div>
              </div>
            );
          })}

          {/* ROW 3: HARD DISK & STORAGE PARTITIONS */}
          <div
            onClick={() => setSelectedDeviceId('storage_sys')}
            style={{
              padding: '13px 16px', borderRadius: '12px',
              background: selectedDeviceId === 'storage_sys' ? (isLight ? '#ffffff' : 'rgba(0, 210, 255, 0.08)') : cardBg,
              border: selectedDeviceId === 'storage_sys' ? '1.5px solid #00d2ff' : cardBorder,
              boxShadow: selectedDeviceId === 'storage_sys' ? '0 0 20px rgba(0, 210, 255, 0.15)' : cardShadow,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
              transition: 'all 0.2s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
              <div style={{
                width: '38px', height: '38px', borderRadius: '10px',
                background: 'rgba(255, 184, 108, 0.15)', border: '1px solid rgba(255, 184, 108, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Database size={18} color="#ffb86c" />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                    Hard Disk & Partizioni SSD
                  </span>
                  <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(255, 184, 108, 0.15)', color: '#ffb86c', fontWeight: 700 }}>
                    {disks.length} Volumi
                  </span>
                </div>
                <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                  {disks.map(d => `${d.device} (${d.used_gb}/${d.total_gb} GB)`).join(' • ')}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>SPAZIO USATO</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#ffb86c', fontFamily: 'JetBrains Mono, monospace' }}>
                  {storage.used_gb || 0} / {storage.total_gb || 0} GB
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>DISCO I/O</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
                  {storage.read_mbps || 0}M / {storage.write_mbps || 0}M
                </div>
              </div>
              <ChevronRight size={18} color={selectedDeviceId === 'storage_sys' ? '#00d2ff' : textMuted} />
            </div>
          </div>

          {/* ROW 4: NETWORK & BANDWIDTH */}
          <div
            onClick={() => setSelectedDeviceId('network_sys')}
            style={{
              padding: '13px 16px', borderRadius: '12px',
              background: selectedDeviceId === 'network_sys' ? (isLight ? '#ffffff' : 'rgba(0, 210, 255, 0.08)') : cardBg,
              border: selectedDeviceId === 'network_sys' ? '1.5px solid #00d2ff' : cardBorder,
              boxShadow: selectedDeviceId === 'network_sys' ? '0 0 20px rgba(0, 210, 255, 0.15)' : cardShadow,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
              transition: 'all 0.2s ease'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
              <div style={{
                width: '38px', height: '38px', borderRadius: '10px',
                background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Wifi size={18} color="#00d2ff" />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary }}>
                    Connessione di Rete & Bandwidth
                  </span>
                  <span style={{ fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', fontWeight: 700 }}>
                    Online
                  </span>
                </div>
                <div style={{ fontSize: '0.68rem', color: textMuted, marginTop: '2px' }}>
                  {network.status || 'Gigabit Ethernet / Wi-Fi'} • Inviati: {network.total_sent_mb || 0} MB • Ricevuti: {network.total_recv_mb || 0} MB
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0 }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>DOWNLOAD</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                  {network.download_kbps || 0} KB/s
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700 }}>UPLOAD</div>
                <div style={{ fontSize: '0.86rem', fontWeight: 900, color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace' }}>
                  {network.upload_kbps || 0} KB/s
                </div>
              </div>
              <ChevronRight size={18} color={selectedDeviceId === 'network_sys' ? '#00d2ff' : textMuted} />
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: HIGH-END UX INSPECTOR WITH DEDICATED GRAPH SELECTOR */}
        <div style={{
          padding: '18px 20px',
          borderRadius: '16px',
          background: cardBg,
          border: cardBorder,
          boxShadow: cardShadow,
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          {selectedDevice ? (
            <>
              {/* Selected Device Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: subCardBorder, paddingBottom: '10px' }}>
                <div>
                  <div style={{ fontSize: '0.64rem', color: '#00d2ff', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.8px' }}>
                    {selectedDevice.type} • ISPETTORE REALTIME
                  </div>
                  <h2 style={{ margin: '2px 0 0 0', fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                    {selectedDevice.name}
                  </h2>
                  <div style={{ fontSize: '0.7rem', color: textMuted, marginTop: '2px' }}>
                    {selectedDevice.subtitle}
                  </div>
                </div>
              </div>

              {/* Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {selectedDevice.metrics.map((m, idx) => (
                  <div key={idx} style={{
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: subCardBg,
                    border: subCardBorder
                  }}>
                    <div style={{ fontSize: '0.64rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>
                      {m.label}
                    </div>
                    <div style={{ fontSize: '0.98rem', fontWeight: 900, color: m.color, fontFamily: 'JetBrains Mono, monospace', margin: '3px 0' }}>
                      {m.val}
                    </div>
                    {m.progress !== undefined && (
                      <div style={{ height: '4px', borderRadius: '2px', background: 'rgba(0,0,0,0.15)', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${Math.min(100, m.progress)}%`, background: m.color, borderRadius: '2px', transition: 'width 0.3s ease' }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* UX DESIGN GRAPH SELECTOR (SELECT ONE CHART AT A TIME) */}
              <div style={{ marginTop: '4px' }}>
                <div style={{ fontSize: '0.66rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>SELEZIONA TELEMETRIA GRAFICA</span>
                  <span style={{ color: currentChart?.color, fontWeight: 900 }}>{currentChart?.label}</span>
                </div>

                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {selectedDevice.availableCharts.map(c => {
                    const ChartIcon = c.icon;
                    const isActive = activeChartType === c.id;
                    return (
                      <button
                        key={c.id}
                        onClick={() => setActiveChartType(c.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '5px',
                          padding: '6px 12px', borderRadius: '8px',
                          border: isActive ? `1.5px solid ${c.color}` : subCardBorder,
                          background: isActive ? (isLight ? '#ffffff' : `${c.color}20`) : subCardBg,
                          color: isActive ? (isLight ? '#111827' : '#ffffff') : textMuted,
                          fontSize: '0.72rem', fontWeight: isActive ? 800 : 600,
                          cursor: 'pointer', transition: 'all 0.15s ease'
                        }}
                      >
                        <ChartIcon size={13} color={c.color} />
                        <span>{c.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* EXPANDED HD LIVE CHART */}
              {currentChart && (
                <div style={{ marginTop: '6px' }}>
                  <RealtimeTelemetryChart
                    data={currentChart.data}
                    label={`${currentChart.label} nel tempo`}
                    icon={currentChart.icon}
                    color={currentChart.color}
                    unit={currentChart.unit}
                    maxVal={currentChart.max}
                    height={120}
                    isLight={isLight}
                    formatVal={currentChart.format}
                  />
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: textMuted }}>
              Seleziona un dispositivo per visualizzarne i grafici in tempo reale.
            </div>
          )}
        </div>
      </div>

      {/* 3. FULL-WIDTH TASK MANAGER & PROCESSES CONSOLE WITH MODULE MAPPING */}
      <div style={{
        borderRadius: '16px',
        backgroundColor: cardBg,
        border: gpuProcs.orfani > 0 ? '1px solid rgba(239, 68, 68, 0.45)' : cardBorder,
        boxShadow: cardShadow,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Table Header Controls */}
        <div style={{
          padding: '14px 18px',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.3)',
          borderBottom: cardBorder,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Terminal size={18} color="#00d2ff" />
            <div>
              <span style={{ fontSize: '0.92rem', fontWeight: 800, color: textPrimary }}>
                Task Manager Processi & Moduli Sigma
              </span>
              <span style={{
                fontSize: '0.66rem', padding: '2px 8px', borderRadius: '8px',
                background: 'rgba(0, 210, 255, 0.12)', color: '#00d2ff', fontWeight: 800, marginLeft: '8px'
              }}>
                {gpuProcs.processes.length} Processi Attivi
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Search Bar */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '5px 10px', borderRadius: '8px',
              background: subCardBg, border: subCardBorder, minWidth: '180px'
            }}>
              <Search size={12} color={textMuted} />
              <input
                type="text"
                placeholder="Cerca PID, modulo, utente..."
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

            {/* Filter by Module Pill Tabs */}
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              <button
                onClick={() => setProcModuleFilter('all')}
                style={{
                  fontSize: '0.66rem', padding: '4px 10px', borderRadius: '6px', border: 'none',
                  background: procModuleFilter === 'all' ? (isLight ? '#111827' : '#00d2ff') : subCardBg,
                  color: procModuleFilter === 'all' ? '#ffffff' : textMuted,
                  fontWeight: procModuleFilter === 'all' ? 800 : 600, cursor: 'pointer'
                }}
              >
                Tutti
              </button>

              <button
                onClick={() => setProcModuleFilter('gpu_only')}
                style={{
                  fontSize: '0.66rem', padding: '4px 10px', borderRadius: '6px', border: 'none',
                  background: procModuleFilter === 'gpu_only' ? (isLight ? '#111827' : '#00d2ff') : subCardBg,
                  color: procModuleFilter === 'gpu_only' ? '#ffffff' : textMuted,
                  fontWeight: procModuleFilter === 'gpu_only' ? 800 : 600, cursor: 'pointer'
                }}
              >
                Solo GPU
              </button>

              {moduleCategories.slice(0, 4).map(mod => (
                <button
                  key={mod}
                  onClick={() => setProcModuleFilter(mod)}
                  style={{
                    fontSize: '0.66rem', padding: '4px 10px', borderRadius: '6px', border: 'none',
                    background: procModuleFilter === mod ? (isLight ? '#111827' : '#00d2ff') : subCardBg,
                    color: procModuleFilter === mod ? '#ffffff' : textMuted,
                    fontWeight: procModuleFilter === mod ? 800 : 600, cursor: 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {mod}
                </button>
              ))}

              <button
                onClick={() => setProcModuleFilter('orphans')}
                style={{
                  fontSize: '0.66rem', padding: '4px 10px', borderRadius: '6px', border: 'none',
                  background: procModuleFilter === 'orphans' ? '#ef4444' : subCardBg,
                  color: procModuleFilter === 'orphans' ? '#ffffff' : (gpuProcs.orfani > 0 ? '#ef4444' : textMuted),
                  fontWeight: procModuleFilter === 'orphans' ? 800 : 600, cursor: 'pointer'
                }}
              >
                Orfani ({gpuProcs.orfani})
              </button>
            </div>

            {gpuProcs.orfani > 0 && (
              <button
                onClick={handleKillAllOrphans}
                style={{
                  fontSize: '0.68rem', padding: '5px 10px', borderRadius: '6px',
                  background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#ef4444', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                <AlertTriangle size={12} /> Termina {gpuProcs.orfani} Orfani
              </button>
            )}

            <button
              onClick={fetchGpuProcesses}
              style={{ background: 'transparent', border: 'none', color: textMuted, cursor: 'pointer', padding: '4px' }}
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </div>

        {/* Table Column Headers */}
        <div style={{
          padding: '8px 18px',
          display: 'grid',
          gridTemplateColumns: 'minmax(180px, 1.8fr) minmax(130px, 1.3fr) minmax(100px, 1fr) minmax(120px, 1.2fr) minmax(110px, 1fr) minmax(100px, 1fr) 80px',
          gap: '8px',
          fontSize: '0.64rem',
          fontWeight: 800,
          color: textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.6px',
          borderBottom: subCardBorder,
          background: isLight ? 'rgba(0,0,0,0.01)' : 'rgba(0,0,0,0.15)'
        }}>
          <div>Processo & PID</div>
          <div>Modulo / Contesto</div>
          <div>Proprietario</div>
          <div>Dispositivo / GPU</div>
          <div>VRAM / RAM Host</div>
          <div>CPU & GPU %</div>
          <div style={{ textAlign: 'right' }}>Azione</div>
        </div>

        {/* Process List Entries */}
        <div style={{ maxHeight: '380px', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {filteredProcesses.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', fontSize: '0.76rem', color: textMuted }}>
              Nessun processo trovato per il filtro selezionato.
            </div>
          ) : (
            filteredProcesses.map(proc => {
              const isOrphan = proc.is_orphan || proc.orphan;
              const isMaster = proc.is_master;

              return (
                <div
                  key={proc.pid}
                  style={{
                    padding: '9px 18px',
                    borderBottom: subCardBorder,
                    display: 'grid',
                    gridTemplateColumns: 'minmax(180px, 1.8fr) minmax(130px, 1.3fr) minmax(100px, 1fr) minmax(120px, 1.2fr) minmax(110px, 1fr) minmax(100px, 1fr) 80px',
                    alignItems: 'center',
                    gap: '8px',
                    background: isMaster
                      ? (isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 210, 255, 0.05)')
                      : (isOrphan ? (isLight ? 'rgba(239, 68, 68, 0.06)' : 'rgba(239, 68, 68, 0.08)') : 'transparent'),
                    transition: 'background 0.15s ease'
                  }}
                >
                  {/* 1. Process Name & PID */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <span style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: '0.66rem', fontWeight: 800,
                      padding: '2px 6px', borderRadius: '4px',
                      background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)',
                      color: textPrimary
                    }}>
                      #{proc.pid}
                    </span>
                    <span style={{
                      fontSize: '0.78rem', fontWeight: 800,
                      color: isMaster ? '#00d2ff' : (isOrphan ? '#ef4444' : textPrimary),
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                    }} title={proc.name}>
                      {proc.name || `PID ${proc.pid}`}
                    </span>
                  </div>

                  {/* 2. Module / Context */}
                  <div>
                    <span style={{
                      fontSize: '0.64rem', fontWeight: 700, padding: '2px 7px', borderRadius: '5px',
                      background: isMaster
                        ? 'rgba(0, 210, 255, 0.15)'
                        : (proc.module_id === 'sigma_creative_lab' ? 'rgba(234, 88, 12, 0.15)' : (proc.module_id === 'sigma_engine' ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255, 255, 255, 0.05)')),
                      color: isMaster
                        ? '#00d2ff'
                        : (proc.module_id === 'sigma_creative_lab' ? '#ea580c' : (proc.module_id === 'sigma_engine' ? '#bc8cff' : textSecondary)),
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block', maxWidth: '100%'
                    }}>
                      {proc.module_name || 'Sigma Core'}
                    </span>
                  </div>

                  {/* 3. User */}
                  <div style={{ fontSize: '0.72rem', color: textSecondary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {proc.user || 'Sigma'}
                  </div>

                  {/* 4. Assigned GPU */}
                  <div>
                    <span style={{
                      fontSize: '0.64rem', fontWeight: 700, padding: '2px 7px', borderRadius: '5px',
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

                  {/* 5. VRAM / RAM */}
                  <div style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono, monospace', color: textPrimary }}>
                    <span style={{ color: '#00d2ff', fontWeight: 700 }}>{proc.vram_mb || 0} MB</span>
                    <span style={{ color: textMuted, fontSize: '0.64rem' }}> / {proc.memory_mb || 0}M</span>
                  </div>

                  {/* 6. CPU / GPU Load */}
                  <div style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono, monospace', color: textMuted }}>
                    <span>{proc.cpu_pct ?? 0}% CPU</span>
                    {proc.gpu_pct > 0 && <span style={{ color: '#bc8cff', marginLeft: '6px' }}>{proc.gpu_pct}% GPU</span>}
                  </div>

                  {/* 7. Kill Action */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    {proc.killable ? (
                      <button
                        onClick={() => handleKillGpuProcess(proc)}
                        disabled={killingPid === proc.pid}
                        style={{
                          fontSize: '0.64rem', padding: '3px 8px', borderRadius: '4px',
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
                          fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px'
                        }}
                        title="Termina processo"
                      >
                        <Trash2 size={11} /> {killingPid === proc.pid ? '...' : 'Kill'}
                      </button>
                    ) : (
                      <span style={{ fontSize: '0.62rem', color: '#00d2ff', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: 'rgba(0,210,255,0.1)' }}>
                        Protetto
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 4. STANDBY ACCELERATOR NODES */}
      <div style={{
        padding: '16px 20px',
        borderRadius: '16px',
        backgroundColor: cardBg,
        border: cardBorder,
        boxShadow: cardShadow,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={16} color="#bc8cff" />
            <span style={{ fontSize: '0.88rem', fontWeight: 800, color: textPrimary }}>
              Acceleratori Hardware Standby & Cluster Distribuito
            </span>
          </div>
          <span style={{ fontSize: '0.66rem', color: textMuted }}>
            {INACTIVE_HARDWARE_NODES.length} Moduli di Espansione
          </span>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '12px'
        }}>
          {INACTIVE_HARDWARE_NODES.map(node => {
            const NodeIcon = node.icon;
            return (
              <div key={node.id} style={{
                padding: '12px 14px',
                borderRadius: '12px',
                background: subCardBg,
                border: subCardBorder,
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <NodeIcon size={16} color={node.color} />
                    <span style={{ fontSize: '0.8rem', fontWeight: 800, color: textPrimary }}>
                      {node.title}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.58rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', color: textMuted, fontWeight: 700 }}>
                    {node.statusBadge}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.68rem', color: textMuted, lineHeight: '1.4' }}>
                  {node.subtitle}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* CONFIRMATION ALERT MODAL */}
      {showRestartAlert && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 10020,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px'
        }}>
          <div style={{
            maxWidth: '420px', width: '100%',
            background: isLight ? '#fffdf9' : 'rgba(15, 23, 42, 0.98)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '14px', padding: '20px',
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.8)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <AlertTriangle size={22} color="#ef4444" />
              <div>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: textPrimary }}>Riavvio & Svuotamento Memoria</h3>
                <div style={{ fontSize: '11px', color: textMuted }}>Scarica tutti i modelli da VRAM</div>
              </div>
            </div>
            <p style={{ fontSize: '12px', color: textSecondary, lineHeight: '1.5', marginBottom: '16px' }}>
              Questa azione scaricherà immediatamente tutti i modelli residenti nella VRAM/RAM GPU e riallineerà il runtime. Continuare?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                onClick={() => setShowRestartAlert(false)}
                disabled={restartingOllama}
                style={{ fontSize: '12px', padding: '6px 14px', borderRadius: '6px', border: subCardBorder, background: subCardBg, color: textPrimary, cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button
                onClick={handleRestartOllama}
                disabled={restartingOllama}
                style={{ fontSize: '12px', padding: '6px 14px', borderRadius: '6px', border: 'none', background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', fontWeight: 800, cursor: 'pointer' }}
              >
                {restartingOllama ? 'Svuotamento...' : 'Conferma Svuotamento'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}