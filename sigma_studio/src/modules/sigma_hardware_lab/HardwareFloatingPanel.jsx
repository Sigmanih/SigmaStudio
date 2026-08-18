import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { 
  Zap, Activity, ShieldCheck, Play, Pause, X, GripVertical, Maximize2, RotateCcw,
  HardDrive, Cpu, Thermometer, Flame, Gauge, Sliders, BarChart2, AlertTriangle,
  Database, Wifi, ArrowDown, ArrowUp, Layers, Sparkles, RefreshCw, Search, ChevronDown, ChevronUp
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import { useApp } from '../../contexts/AppContext';
import './styles/hardware-lab.css';
import '../../styles/chat.css';

const MIN_WIDTH = 460;
const MIN_HEIGHT = 340;
const MAX_HISTORY = 900;

/**
 * Compact Hi-Tech Square Metric Tile Component
 * Fluid, responsive, interactive (click to expand full details and realtime charts).
 */
function CompactSquareMetricTile({
  icon: Icon,
  category,
  title,
  fullName,
  badge,
  badgeColor,
  percentage,
  usedLabel,
  usedVal,
  maxVal,
  unit = '',
  subText,
  color = '#00f2fe',
  isSelected = false,
  isLight = false,
  onClick = null
}) {
  const size = 46;
  const strokeWidth = 4.5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const hasPct = percentage !== null && percentage !== undefined && !isNaN(percentage);
  const safePct = hasPct ? Math.min(100, Math.max(0, Number(percentage))) : 0;
  const strokeDashoffset = circumference - (safePct / 100) * circumference;

  let activeColor = color;
  if (safePct >= 90) activeColor = '#ef4444';
  else if (safePct >= 75 && color !== '#ea580c' && color !== '#f59e0b') activeColor = '#f59e0b';

  return (
    <div
      onClick={onClick}
      title={`${fullName || title} (Clicca per espandere dettagli e grafici)`}
      className={`hw-square-card ${isSelected ? 'is-selected' : ''}`}
      style={{
        background: isSelected 
          ? (isLight ? 'linear-gradient(135deg, #ffffff 0%, #f4efe4 100%)' : `linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, ${activeColor}15 100%)`)
          : (isLight ? 'linear-gradient(135deg, #ffffff 0%, #faf8f5 100%)' : 'linear-gradient(135deg, rgba(17, 24, 39, 0.90) 0%, rgba(10, 14, 26, 0.96) 100%)'),
        border: isSelected 
          ? `1.5px solid ${activeColor}` 
          : (isLight ? '1px solid rgba(190, 160, 110, 0.35)' : `1px solid ${activeColor}33`),
        borderRadius: '12px',
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: isSelected 
          ? (isLight ? `0 8px 24px rgba(0, 0, 0, 0.08), 0 0 16px ${activeColor}20` : `0 8px 24px rgba(0, 0, 0, 0.5), 0 0 20px ${activeColor}25`)
          : (isLight ? '0 3px 12px rgba(0, 0, 0, 0.04)' : `0 6px 18px rgba(0, 0, 0, 0.4), 0 0 14px ${activeColor}10`),
        transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
        cursor: 'pointer',
        minHeight: '142px',
      }}
    >
      {/* Top accent glow line */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: isSelected ? '3.5px' : '2.5px',
        background: `linear-gradient(90deg, ${activeColor}, ${activeColor}70, transparent)`
      }} />

      {/* Header Block: Icon + Title + Badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginBottom: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
          <div style={{
            width: '24px',
            height: '24px',
            borderRadius: '6px',
            background: isLight ? `${activeColor}15` : `${activeColor}20`,
            border: `1px solid ${activeColor}40`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: `0 0 8px ${activeColor}25`
          }}>
            <Icon size={13} color={activeColor} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            {category && (
              <div style={{
                fontSize: '8px',
                fontWeight: 800,
                color: activeColor,
                textTransform: 'uppercase',
                letterSpacing: '0.6px',
                lineHeight: 1
              }}>
                {category}
              </div>
            )}
            <div style={{
              fontSize: '11px',
              fontWeight: 800,
              color: isLight ? '#111827' : '#f8fafc',
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {title}
            </div>
          </div>
        </div>

        {badge && (
          <span style={{
            fontSize: '8.5px',
            fontWeight: 800,
            fontFamily: 'monospace',
            padding: '2px 5px',
            borderRadius: '5px',
            background: isLight ? 'rgba(0,0,0,0.06)' : `${badgeColor || activeColor}20`,
            color: badgeColor || activeColor,
            border: `1px solid ${badgeColor || activeColor}35`,
            flexShrink: 0
          }}>
            {badge}
          </span>
        )}
      </div>

      {/* Middle Block: Bold Percentage Typography & Radial SVG Gauge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', margin: '2px 0 6px' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '2px' }}>
            <span style={{
              fontSize: '24px',
              fontWeight: 900,
              fontFamily: 'system-ui, -apple-system, sans-serif',
              letterSpacing: '-0.8px',
              color: isLight ? '#111827' : '#ffffff',
              lineHeight: 1
            }}>
              {hasPct ? percentage : '--'}
            </span>
            {hasPct && (
              <span style={{
                fontSize: '12px',
                fontWeight: 800,
                color: activeColor
              }}>%</span>
            )}
          </div>
          <span style={{
            fontSize: '8.5px',
            fontWeight: 700,
            color: isLight ? '#6b7280' : 'rgba(255, 255, 255, 0.45)',
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
            marginTop: '2px'
          }}>
            {isSelected ? 'Dettagli ON ▾' : 'Live Misurato'}
          </span>
        </div>

        {/* High-Tech SVG Circular Gauge */}
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
          <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}
              strokeWidth={strokeWidth}
            />
            {hasPct && (
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={activeColor}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{
                  transition: 'stroke-dashoffset 0.4s ease, stroke 0.3s ease',
                  filter: `drop-shadow(0 0 4px ${activeColor}80)`
                }}
              />
            )}
          </svg>
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '9px',
            fontWeight: 900,
            color: activeColor,
            fontFamily: 'monospace'
          }}>
            <Icon size={13} color={activeColor} />
          </div>
        </div>
      </div>

      {/* Progress Track Bar */}
      {hasPct && (
        <div style={{
          height: '3.5px',
          borderRadius: '2px',
          background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)',
          overflow: 'hidden',
          marginBottom: '5px'
        }}>
          <div style={{
            height: '100%',
            width: `${safePct}%`,
            background: activeColor,
            borderRadius: '2px',
            transition: 'width 0.35s ease',
            boxShadow: `0 0 6px ${activeColor}80`
          }} />
        </div>
      )}

      {/* Bottom Block: Usato / Max info in bella vista */}
      <div style={{
        marginTop: 'auto',
        paddingTop: '5px',
        borderTop: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.07)',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '9.5px' }}>
          <span style={{ color: isLight ? '#4b5563' : '#94a3b8', fontWeight: 600 }}>
            {usedLabel || 'Usato'}:
          </span>
          <span style={{
            fontFamily: 'monospace',
            fontWeight: 800,
            color: isLight ? '#111827' : '#f8fafc',
            display: 'flex',
            alignItems: 'center',
            gap: '2px'
          }}>
            <span style={{ color: activeColor }}>{usedVal}</span>
            {maxVal !== undefined && maxVal !== null && <span style={{ color: isLight ? '#6b7280' : '#64748b' }}>/{maxVal}</span>}
            {unit && <span style={{ fontSize: '8.5px', color: isLight ? '#6b7280' : '#94a3b8' }}>{unit}</span>}
          </span>
        </div>

        {subText && (
          <div style={{
            fontSize: '8.5px',
            color: isLight ? '#6b7280' : '#94a3b8',
            fontFamily: 'monospace',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: 'flex',
            alignItems: 'center',
            gap: '3px'
          }}>
            <span style={{ width: '3px', height: '3px', borderRadius: '50%', background: activeColor, flexShrink: 0 }} />
            {subText}
          </div>
        )}
      </div>
    </div>
  );
}

export default function HardwareFloatingPanel({ onClose, onOpenTab, addToast }) {
  const { theme } = useApp ? useApp() : { theme: 'dark' };
  const isLight = theme === 'light';

  const [panelPos, setPanelPos] = useState({ x: undefined, y: undefined });
  const [panelSize, setPanelSize] = useState({ width: 720, height: 500 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [resizing, setResizing] = useState(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0 });
  const resizeSizeStart = useRef({ width: 720, height: 500 });
  const resizePosStart = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  const [showCharts, setShowCharts] = useState(false);
  const [showRestartAlert, setShowRestartAlert] = useState(false);
  const [restartingOllama, setRestartingOllama] = useState(false);
  const [activeCategory, setActiveCategory] = useState('all'); // 'all' | 'system' | 'gpu' | 'processes'

  // Selected card for expanded deep inspector details & charts
  const [selectedCardId, setSelectedCardId] = useState(null);

  // History buffers per GPU index & System
  const [historyData, setHistoryData] = useState({});
  const historyRef = useRef({});
  const [systemHistory, setSystemHistory] = useState({ 
    cpu: [], 
    ram: [], 
    net_down: [], 
    net_up: [], 
    disk_read: [], 
    disk_write: [] 
  });
  const systemHistoryRef = useRef({ 
    cpu: [], 
    ram: [], 
    net_down: [], 
    net_up: [], 
    disk_read: [], 
    disk_write: [] 
  });

  // Fetch telemetry status
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

          // 2. Accumulate System History (CPU, RAM, Storage I/O, Network Throughput)
          const cpuUtil = Number(json.hardware?.cpu?.usage_pct ?? json.hardware?.cpu?.util_pct ?? 0);
          const ramUsed = Number(json.hardware?.ram?.used_gb ?? json.hardware?.ram_used_gb ?? 0);
          const netDown = Number(json.hardware?.network?.download_kbps) || 0;
          const netUp = Number(json.hardware?.network?.upload_kbps) || 0;
          const diskRead = Number(json.hardware?.storage?.read_mbps) || 0;
          const diskWrite = Number(json.hardware?.storage?.write_mbps) || 0;

          const currentSysHist = { ...systemHistoryRef.current };
          const newCpu = [...(currentSysHist.cpu || []), cpuUtil];
          const newRam = [...(currentSysHist.ram || []), ramUsed];
          const newNetDown = [...(currentSysHist.net_down || []), netDown];
          const newNetUp = [...(currentSysHist.net_up || []), netUp];
          const newDiskRead = [...(currentSysHist.disk_read || []), diskRead];
          const newDiskWrite = [...(currentSysHist.disk_write || []), diskWrite];

          if (newCpu.length > MAX_HISTORY) newCpu.shift();
          if (newRam.length > MAX_HISTORY) newRam.shift();
          if (newNetDown.length > MAX_HISTORY) newNetDown.shift();
          if (newNetUp.length > MAX_HISTORY) newNetUp.shift();
          if (newDiskRead.length > MAX_HISTORY) newDiskRead.shift();
          if (newDiskWrite.length > MAX_HISTORY) newDiskWrite.shift();

          const updatedHist = {
            cpu: newCpu,
            ram: newRam,
            net_down: newNetDown,
            net_up: newNetUp,
            disk_read: newDiskRead,
            disk_write: newDiskWrite
          };

          systemHistoryRef.current = updatedHist;
          setSystemHistory(updatedHist);
        }
      }
    } catch (err) {
      console.error('Failed to fetch hardware status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const [gpuProcs, setGpuProcs] = useState({ processes: [], orfani: 0 });
  const [killingPid, setKillingPid] = useState(null);
  const [procSearch, setProcSearch] = useState('');

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
      console.error('Failed to fetch GPU processes:', e);
    }
  }, []);

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
        if (addToast) addToast(json.message || `Processo PID ${proc.pid} terminato.`, 'success');
      } else if (addToast) {
        addToast(json.error || `Impossibile chiudere il processo ${proc.pid}.`, 'error');
      }
      fetchGpuProcesses();
      fetchHardwareStatus();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setKillingPid(null);
    }
  };

  const handleRestartOllama = async () => {
    setRestartingOllama(true);
    try {
      const res = await fetch('/api/hardware/restart-ollama', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast('⚡ VRAM Cache liberata con successo.', 'success');
        setShowRestartAlert(false);
        fetchHardwareStatus();
        fetchGpuProcesses();
      } else {
        if (addToast) addToast(json.error || 'Errore durante la pulizia VRAM.', 'error');
      }
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setRestartingOllama(false);
    }
  };

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

  // Drag logic
  useEffect(() => {
    if (!isDragging) return;
    const hMM = (e) => {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        setPanelPos(prev => ({
          x: (prev.x !== undefined ? prev.x : (window.innerWidth - panelSize.width) / 2) + dx,
          y: (prev.y !== undefined ? prev.y : 75) + dy
        }));
        setDragStart({ x: e.clientX, y: e.clientY });
      }
    };
    const hMU = () => setIsDragging(false);
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [isDragging, dragStart, panelSize]);

  // Resize logic
  useEffect(() => {
    if (!resizing) return;
    const hMM = (e) => {
      const dx = e.clientX - resizeStart.x;
      const dy = e.clientY - resizeStart.y;
      
      setPanelPos(prev => {
        let newX = prev.x;
        let newY = prev.y;
        if (resizing.includes('w')) {
          const diff = resizeSizeStart.current.width - dx;
          if (diff >= MIN_WIDTH) newX = resizePosStart.current.x + dx;
        }
        if (resizing.includes('n')) {
          const diff = resizeSizeStart.current.height - dy;
          if (diff >= MIN_HEIGHT) newY = resizePosStart.current.y + dy;
        }
        return { x: newX, y: newY };
      });

      setPanelSize(() => {
        let newW = resizeSizeStart.current.width;
        let newH = resizeSizeStart.current.height;
        if (resizing.includes('e')) newW = Math.max(MIN_WIDTH, resizeSizeStart.current.width + dx);
        if (resizing.includes('w')) newW = Math.max(MIN_WIDTH, resizeSizeStart.current.width - dx);
        if (resizing.includes('s')) newH = Math.max(MIN_HEIGHT, resizeSizeStart.current.height + dy);
        if (resizing.includes('n')) newH = Math.max(MIN_HEIGHT, resizeSizeStart.current.height - dy);
        return { width: newW, height: newH };
      });
    };
    const hMU = () => setResizing(null);
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [resizing, resizeStart]);

  const handleMouseDownHeader = (e) => {
    if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select')) return;
    const initialX = panelPos.x !== undefined ? panelPos.x : (window.innerWidth - panelSize.width) / 2;
    const initialY = panelPos.y !== undefined ? panelPos.y : 75;
    setPanelPos({ x: initialX, y: initialY });
    setDragStart({ x: e.clientX, y: e.clientY });
    setIsDragging(true);
  };

  const handleMouseDownResize = (e, dir) => {
    e.stopPropagation();
    const currX = panelPos.x !== undefined ? panelPos.x : (window.innerWidth - panelSize.width) / 2;
    const currY = panelPos.y !== undefined ? panelPos.y : 75;
    resizePosStart.current = { x: currX, y: currY };
    resizeSizeStart.current = { width: panelSize.width, height: panelSize.height };
    setResizeStart({ x: e.clientX, y: e.clientY });
    setResizing(dir);
  };

  // Safe data destructuring — 100% dynamic without fake hardcoded numbers
  const hw = data?.hardware || {};
  const gpus = Array.isArray(hw.gpu) ? hw.gpu : [];
  const cpu = hw.cpu || {};
  const ram = hw.ram || {};
  const storage = hw.storage || {};
  const network = hw.network || {};
  const disks = Array.isArray(storage.disks) ? storage.disks : [];

  // Dynamic CPU Telemetry
  const cpuFullName = cpu.name || 'CPU Host';
  const cpuShortName = cpuFullName
    .replace(/\(R\)/gi, '')
    .replace(/\(TM\)/gi, '')
    .replace(/Processor/gi, '')
    .replace(/\d+-Core/gi, '')
    .replace(/CPU/gi, '')
    .trim() || cpuFullName;
  const cpuUsagePct = cpu.usage_pct !== undefined ? Math.round(Number(cpu.usage_pct)) : (cpu.util_pct !== undefined ? Math.round(Number(cpu.util_pct)) : null);
  const cpuCoresPhysical = Number(cpu.cores_physical) || 0;
  const cpuCoresLogical = Number(cpu.cores_logical ?? cpu.logical_count) || 0;
  const cpuFreqMhz = Number(cpu.freq_mhz) || 0;
  const cpuFreqGhz = cpuFreqMhz > 0 ? (cpuFreqMhz / 1000).toFixed(1) : null;

  // Dynamic RAM Telemetry
  const ramTotalGb = Number(ram.total_gb) || 0;
  const ramUsedGb = Number(ram.used_gb ?? hw.ram_used_gb) || 0;
  const ramFreeGb = Number(ram.free_gb) || (ramTotalGb > 0 ? Math.max(0, Number((ramTotalGb - ramUsedGb).toFixed(1))) : 0);
  const ramUsagePct = ram.usage_pct !== undefined ? Math.round(Number(ram.usage_pct)) : (ramTotalGb > 0 ? Math.round((ramUsedGb / ramTotalGb) * 100) : null);

  // Dynamic Storage Telemetry
  const storageTotalGb = Number(storage.total_gb) || 0;
  const storageUsedGb = Number(storage.used_gb) || 0;
  const storageFreeGb = Number(storage.free_gb) || (storageTotalGb > 0 ? Math.max(0, Number((storageTotalGb - storageUsedGb).toFixed(0))) : 0);
  const storageUsagePct = storage.usage_pct !== undefined ? Math.round(Number(storage.usage_pct)) : (storageTotalGb > 0 ? Math.round((storageUsedGb / storageTotalGb) * 100) : null);
  const storageReadMbps = Number(storage.read_mbps) || 0;
  const storageWriteMbps = Number(storage.write_mbps) || 0;

  // Format Storage in TB if >= 1000 GB
  const isStorageTb = storageTotalGb >= 1000;
  const storageUsedDisp = isStorageTb ? (storageUsedGb / 1024).toFixed(1) + ' TB' : storageUsedGb.toFixed(0) + ' GB';
  const storageTotalDisp = isStorageTb ? (storageTotalGb / 1024).toFixed(1) + ' TB' : storageTotalGb.toFixed(0) + ' GB';

  // Dynamic Network Telemetry
  const netDownKbps = Number(network.download_kbps) || 0;
  const netUpKbps = Number(network.upload_kbps) || 0;
  const netRecvMb = Number(network.total_recv_mb) || 0;
  const netSentMb = Number(network.total_sent_mb) || 0;
  const netStatus = network.status || 'Attiva';

  // Filtered Processes
  const filteredProcesses = useMemo(() => {
    if (!procSearch.trim()) return gpuProcs.processes;
    const q = procSearch.toLowerCase().trim();
    return gpuProcs.processes.filter(p => 
      String(p.pid).includes(q) ||
      p.name?.toLowerCase().includes(q) ||
      p.module_name?.toLowerCase().includes(q)
    );
  }, [gpuProcs.processes, procSearch]);

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x)) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y)) ? panelPos.y : undefined;

  const resizeHandles = [
    { dir: 'n' }, { dir: 's' }, { dir: 'e' }, { dir: 'w' },
    { dir: 'ne' }, { dir: 'nw' }, { dir: 'se' }, { dir: 'sw' }
  ];

  // Theme Design Tokens
  const panelBg = isLight ? '#fffdf9' : 'rgba(10, 14, 23, 0.98)';
  const panelBorder = isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 242, 254, 0.35)';
  const panelShadow = isLight 
    ? '0 20px 50px rgba(0, 0, 0, 0.2), 0 0 16px rgba(234, 88, 12, 0.08)' 
    : '0 28px 56px -12px rgba(0, 0, 0, 0.7), 0 0 26px rgba(0, 242, 254, 0.16)';
  const headerBg = isLight ? '#f4efe4' : 'rgba(15, 23, 42, 0.85)';
  const headerBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111111' : '#ffffff';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textDim = isLight ? '#6b7280' : '#94a3b8';
  const accentColor = isLight ? '#ea580c' : '#00f2fe';
  const headerBtnBg = isLight ? '#fffdf9' : 'rgba(255,255,255,0.05)';
  const headerBtnBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.1)';

  // Handler to toggle card inspection
  const handleCardClick = (cardId) => {
    setSelectedCardId(prev => (prev === cardId ? null : cardId));
  };

  return (
    <div
      ref={panelRef}
      className={`task-floating-panel hw-floating-panel ${resizing ? 'is-resizing' : ''}`}
      style={{
        position: 'fixed',
        zIndex: 10002,
        ...(safeX !== undefined ? { left: safeX, right: 'auto' } : { left: '50%', marginLeft: -panelSize.width / 2 }),
        ...(safeY !== undefined ? { bottom: 'auto', top: safeY } : { top: 75 }),
        width: `${panelSize.width}px`,
        height: `${panelSize.height}px`,
        maxHeight: 'calc(100vh - 80px)',
        background: panelBg,
        border: panelBorder,
        borderRadius: '16px',
        boxShadow: panelShadow,
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideUp 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* CONFIRMATION MODAL FOR VRAM FLUSH */}
      {showRestartAlert && (
        <div style={{
          position: 'absolute',
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
            maxWidth: '420px',
            width: '100%',
            background: isLight ? '#fffdf9' : 'rgba(15, 23, 42, 0.98)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '14px',
            padding: '20px',
            boxShadow: isLight ? '0 20px 45px rgba(0, 0, 0, 0.2)' : '0 25px 50px -12px rgba(0, 0, 0, 0.9)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '8px', borderRadius: '10px', display: 'flex' }}>
                <AlertTriangle size={20} color="#ef4444" />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: textPrimary }}>Riavvio & Pulizia VRAM</h3>
                <div style={{ fontSize: '11px', color: textDim }}>Svuota memoria cache modelli AI</div>
              </div>
            </div>

            <div style={{ fontSize: '12px', color: textSecondary, lineHeight: '1.5', marginBottom: '16px', background: isLight ? '#f4efe4' : 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid #ef4444' }}>
              ⚠️ Scaricherà tutti i modelli pesanti da VRAM/RAM e riallineerà il motore runtime locale. Continuare?
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button 
                className="hw-btn" 
                onClick={() => setShowRestartAlert(false)} 
                disabled={restartingOllama} 
                style={{ fontSize: '12px', padding: '6px 14px', background: isLight ? '#fff' : undefined, color: textPrimary }}
              >
                Annulla
              </button>
              <button 
                className="hw-btn" 
                onClick={handleRestartOllama} 
                disabled={restartingOllama}
                style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', fontWeight: 800, fontSize: '12px', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                {restartingOllama ? <Activity className="spin" size={13} /> : <RotateCcw size={13} />}
                {restartingOllama ? 'Svuotamento...' : 'Svuota VRAM'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resize handles */}
      {resizeHandles.map(rh => (
        <div key={rh.dir} style={{
          position: 'absolute',
          zIndex: 100,
          ...(rh.dir === 'n' ? { top: -2, left: 0, right: 0, height: 6, cursor: 'n-resize' } : {}),
          ...(rh.dir === 's' ? { bottom: -2, left: 0, right: 0, height: 6, cursor: 's-resize' } : {}),
          ...(rh.dir === 'e' ? { right: -2, top: 0, bottom: 0, width: 6, cursor: 'e-resize' } : {}),
          ...(rh.dir === 'w' ? { left: -2, top: 0, bottom: 0, width: 6, cursor: 'w-resize' } : {}),
          ...(rh.dir === 'ne' ? { top: -2, right: -2, width: 10, height: 10, cursor: 'ne-resize' } : {}),
          ...(rh.dir === 'nw' ? { top: -2, left: -2, width: 10, height: 10, cursor: 'nw-resize' } : {}),
          ...(rh.dir === 'se' ? { bottom: -2, right: -2, width: 10, height: 10, cursor: 'se-resize' } : {}),
          ...(rh.dir === 'sw' ? { bottom: -2, left: -2, width: 10, height: 10, cursor: 'sw-resize' } : {}),
        }}
          onMouseDown={(e) => handleMouseDownResize(e, rh.dir)}
        />
      ))}

      {/* Header — Drag Handle & Quick Actions */}
      <div 
        className="task-floating-header" 
        onMouseDown={handleMouseDownHeader}
        style={{ 
          cursor: isDragging ? 'grabbing' : 'grab',
          padding: '10px 14px',
          background: headerBg,
          borderBottom: headerBorder,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none'
        }}
      >
        <div className="task-floating-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GripVertical size={14} color={textDim} />
          <div style={{
            width: '22px',
            height: '22px',
            borderRadius: '6px',
            background: `${accentColor}20`,
            border: `1px solid ${accentColor}40`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Zap size={13} color={accentColor} />
          </div>
          <span style={{ fontWeight: 800, fontSize: '13px', color: accentColor, letterSpacing: '0.2px' }}>
            Hardware & GPU Monitor
          </span>
          <span className="hw-badge hw-badge-live" style={{ fontSize: '9.5px', padding: '1px 7px', marginLeft: '2px' }}>
            <span className="hw-badge-dot" />
            {gpus.length > 0 ? `${gpus.length} GPU Live` : 'CPU Mode'}
          </span>
        </div>

        <div className="task-floating-actions" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <button 
            onClick={() => setShowRestartAlert(true)} 
            className="chat-header-btn" 
            title="Svuota la memoria VRAM scaricando tutti i modelli"
            style={{ 
              background: isLight ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.15)', 
              border: '1px solid rgba(239, 68, 68, 0.35)', 
              borderRadius: '6px', 
              padding: '4px 8px', 
              cursor: 'pointer', 
              color: isLight ? '#dc2626' : '#fca5a5', 
              fontSize: '10.5px', 
              fontWeight: 700,
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <RotateCcw size={11} color="#ef4444" />
            <span>Svuota VRAM</span>
          </button>

          <button 
            onClick={() => setShowCharts(!showCharts)} 
            className="chat-header-btn" 
            title={showCharts ? 'Nascondi i grafici per compattare' : 'Mostra tutti i grafici storici'}
            style={{ 
              background: showCharts 
                ? (isLight ? '#ea580c' : 'rgba(0, 242, 254, 0.2)') 
                : headerBtnBg, 
              border: showCharts 
                ? (isLight ? '1px solid #ea580c' : '1px solid rgba(0, 242, 254, 0.4)') 
                : headerBtnBorder, 
              borderRadius: '6px', 
              padding: '4px 8px', 
              cursor: 'pointer', 
              color: showCharts ? '#fff' : textPrimary, 
              fontSize: '10.5px', 
              fontWeight: 700,
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <BarChart2 size={11} color={showCharts ? '#fff' : accentColor} />
            <span>{showCharts ? 'Grafici ON' : 'Grafici OFF'}</span>
          </button>

          <button 
            onClick={() => setAutoRefresh(!autoRefresh)} 
            className="chat-header-btn" 
            title={autoRefresh ? 'Pausa refresh automatico' : 'Riprendi refresh automatico'}
            style={{ 
              background: headerBtnBg, 
              border: headerBtnBorder, 
              borderRadius: '6px', 
              padding: '4px 7px', 
              cursor: 'pointer', 
              color: textPrimary 
            }}
          >
            {autoRefresh ? <Pause size={11} color={accentColor} /> : <Play size={11} />}
          </button>

          {onOpenTab && (
            <button 
              onClick={onOpenTab} 
              className="chat-header-btn" 
              title="Espandi in Tab Workspace Completa"
              style={{ 
                background: headerBtnBg, 
                border: headerBtnBorder, 
                borderRadius: '6px', 
                padding: '4px 7px', 
                cursor: 'pointer', 
                color: textPrimary 
              }}
            >
              <Maximize2 size={11} color={accentColor} />
            </button>
          )}

          <button 
            onClick={onClose} 
            className="chat-header-btn" 
            title="Chiudi monitor"
            style={{ 
              background: headerBtnBg, 
              border: headerBtnBorder, 
              borderRadius: '6px', 
              padding: '4px 7px', 
              cursor: 'pointer', 
              color: textPrimary 
            }}
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Navigation Filter Pills Bar */}
      <div style={{
        padding: '7px 14px',
        borderBottom: headerBorder,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.2)',
        gap: '8px',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button 
            className={`hw-tab-pill ${activeCategory === 'all' ? 'active' : ''}`}
            onClick={() => setActiveCategory('all')}
          >
            <Sparkles size={11} />
            <span>Tutto ({4 + gpus.length * 2})</span>
          </button>
          <button 
            className={`hw-tab-pill ${activeCategory === 'system' ? 'active' : ''}`}
            onClick={() => setActiveCategory('system')}
          >
            <Cpu size={11} />
            <span>Sistema</span>
          </button>
          <button 
            className={`hw-tab-pill ${activeCategory === 'gpu' ? 'active' : ''}`}
            onClick={() => setActiveCategory('gpu')}
          >
            <Gauge size={11} />
            <span>GPU & VRAM ({gpus.length})</span>
          </button>
          <button 
            className={`hw-tab-pill ${activeCategory === 'processes' ? 'active' : ''}`}
            onClick={() => setActiveCategory('processes')}
          >
            <Zap size={11} />
            <span>Processi ({gpuProcs.processes.length})</span>
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: textDim, fontFamily: 'monospace' }}>
          <span>💡 Clicca su una card per espanderla</span>
          {gpuProcs.orfani > 0 && (
            <span style={{ color: '#ef4444', fontWeight: 800, background: 'rgba(239, 68, 68, 0.15)', padding: '1px 6px', borderRadius: '4px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
              {gpuProcs.orfani} Orfani
            </span>
          )}
        </div>
      </div>

      {/* Floating Panel Body */}
      <div className="task-floating-body" style={{ padding: '12px 14px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* =========================================================================
            FLUID COMPACT SQUARE METRIC CARDS GRID
           ========================================================================= */}
        {(activeCategory === 'all' || activeCategory === 'system' || activeCategory === 'gpu') && (
          <div className="hw-square-grid">
            
            {/* 1. CPU HOST TILE */}
            {(activeCategory === 'all' || activeCategory === 'system') && (
              <CompactSquareMetricTile
                icon={Cpu}
                category="CPU HOST"
                title={cpuShortName}
                fullName={cpuFullName}
                badge={cpuCoresPhysical > 0 ? `${cpuCoresPhysical}C/${cpuCoresLogical}T` : 'CPU'}
                badgeColor="#00f2fe"
                percentage={cpuUsagePct}
                usedLabel="Carico"
                usedVal={cpuUsagePct !== null ? `${cpuUsagePct}%` : 'N/D'}
                maxVal="100%"
                subText={cpuFreqGhz ? `${cpuFreqGhz} GHz • ${cpuCoresPhysical} Cores` : `${cpuCoresPhysical}C / ${cpuCoresLogical}T`}
                color="#00f2fe"
                isSelected={selectedCardId === 'cpu'}
                onClick={() => handleCardClick('cpu')}
                isLight={isLight}
              />
            )}

            {/* 2. RAM HOST TILE */}
            {(activeCategory === 'all' || activeCategory === 'system') && (
              <CompactSquareMetricTile
                icon={HardDrive}
                category="RAM HOST"
                title="RAM Sistema"
                fullName={`Memoria RAM Totale: ${ramTotalGb.toFixed(1)} GB (Allocata: ${ramUsedGb.toFixed(1)} GB, Libera: ${ramFreeGb.toFixed(1)} GB)`}
                badge={ramTotalGb > 0 ? `${ramTotalGb.toFixed(0)} GB` : 'RAM'}
                badgeColor="#10b981"
                percentage={ramUsagePct}
                usedLabel="Allocata"
                usedVal={`${ramUsedGb.toFixed(1)}`}
                maxVal={ramTotalGb > 0 ? `${ramTotalGb.toFixed(0)} GB` : undefined}
                subText={ramFreeGb > 0 ? `${ramFreeGb.toFixed(1)} GB Liberi` : `Allocati ${ramUsedGb.toFixed(1)} GB`}
                color="#10b981"
                isSelected={selectedCardId === 'ram'}
                onClick={() => handleCardClick('ram')}
                isLight={isLight}
              />
            )}

            {/* 3. STORAGE DISKS TILE */}
            {(activeCategory === 'all' || activeCategory === 'system') && storageTotalGb > 0 && (
              <CompactSquareMetricTile
                icon={Database}
                category="STORAGE"
                title="Storage Dischi"
                fullName={`Storage Totale: ${storageTotalDisp} (Occupato: ${storageUsedDisp}, Libero: ${storageFreeGb} GB) - Partizioni: ${disks.map(d => `${d.device || d.mountpoint} (${d.usage_pct}%)`).join(', ')}`}
                badge={disks.length > 0 ? `${disks.length} Unità` : 'DISCO'}
                badgeColor="#f59e0b"
                percentage={storageUsagePct}
                usedLabel="Occupato"
                usedVal={storageUsedDisp}
                maxVal={storageTotalDisp}
                subText={disks.length > 0 ? disks.map(d => `${d.device || d.mountpoint} ${d.usage_pct}%`).join(' • ') : `${storageFreeGb} GB Liberi`}
                color="#f59e0b"
                isSelected={selectedCardId === 'storage'}
                onClick={() => handleCardClick('storage')}
                isLight={isLight}
              />
            )}

            {/* 4. NETWORK TILE */}
            {(activeCategory === 'all' || activeCategory === 'system') && (
              <CompactSquareMetricTile
                icon={Wifi}
                category="RETE"
                title="Connessione"
                fullName={`Interfaccia Rete: ${netStatus} - Ricevuti: ${netRecvMb.toFixed(1)} MB, Inviati: ${netSentMb.toFixed(1)} MB`}
                badge="LIVE"
                badgeColor="#38bdf8"
                percentage={null}
                usedLabel="Down / Up"
                usedVal={`↓ ${netDownKbps > 1000 ? (netDownKbps / 1024).toFixed(1) + 'M' : netDownKbps.toFixed(0) + 'K'}`}
                maxVal={`↑ ${netUpKbps > 1000 ? (netUpKbps / 1024).toFixed(1) + 'M' : netUpKbps.toFixed(0) + 'K'}`}
                subText={`Tot: ↓ ${netRecvMb.toFixed(0)}M • ↑ ${netSentMb.toFixed(0)}M`}
                color="#38bdf8"
                isSelected={selectedCardId === 'network'}
                onClick={() => handleCardClick('network')}
                isLight={isLight}
              />
            )}

            {/* 5. MULTI-GPU TILES (GPU COMPUTE & VRAM) */}
            {(activeCategory === 'all' || activeCategory === 'gpu') && (
              gpus.length === 0 ? (
                <div style={{
                  gridColumn: '1 / -1',
                  textAlign: 'center',
                  padding: '20px 14px',
                  background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.02)',
                  borderRadius: '10px',
                  border: isLight ? '1px dashed rgba(0,0,0,0.1)' : '1px dashed rgba(255,255,255,0.1)'
                }}>
                  <Cpu size={22} color={textDim} style={{ margin: '0 auto 6px' }} />
                  <div style={{ fontSize: '11.5px', color: textSecondary, fontWeight: 700 }}>Nessuna GPU Dedicata Rilevata</div>
                  <div style={{ fontSize: '10px', color: textDim }}>Elaborazione AI su CPU Host / DirectML.</div>
                </div>
              ) : (
                gpus.map(gpu => {
                  const idx = gpu.index;
                  const vramTotalMb = Number(gpu.vram_total_mb) || 0;
                  const vramUsedMb = Number(gpu.vram_used_mb) || 0;
                  const vramUsagePct = vramTotalMb > 0 ? Math.min(100, Math.round((vramUsedMb / vramTotalMb) * 100)) : null;
                  const gpuUtilPct = gpu.gpu_util_pct !== null && gpu.gpu_util_pct !== undefined ? Math.min(100, Math.round(Number(gpu.gpu_util_pct))) : null;
                  
                  const isGb = vramTotalMb >= 2048;
                  const vramUsedDisp = isGb ? (vramUsedMb / 1024).toFixed(1) : `${vramUsedMb}`;
                  const vramTotalDisp = isGb ? `${(vramTotalMb / 1024).toFixed(0)} GB` : `${vramTotalMb} MB`;
                  const vramFreeMb = Math.max(0, vramTotalMb - vramUsedMb);
                  const vramFreeDisp = isGb ? `${(vramFreeMb / 1024).toFixed(1)} GB` : `${vramFreeMb} MB`;

                  const gpuCleanName = (gpu.name || `GPU ${idx}`)
                    .replace(/NVIDIA GeForce/gi, 'GeForce')
                    .replace(/Graphics/gi, '')
                    .replace(/\(TM\)/gi, '')
                    .trim();

                  return (
                    <React.Fragment key={idx}>
                      {/* GPU Compute Core Tile */}
                      <CompactSquareMetricTile
                        icon={Gauge}
                        category={`GPU ${idx} CORE`}
                        title={gpuCleanName}
                        fullName={`${gpu.name || 'GPU ' + idx} (${gpu.type || 'DirectML/CUDA'})`}
                        badge={gpu.vendor || 'CUDA'}
                        badgeColor="#bc8cff"
                        percentage={gpuUtilPct}
                        usedLabel="Carico Core"
                        usedVal={gpuUtilPct !== null ? `${gpuUtilPct}%` : 'N/D'}
                        maxVal="100%"
                        subText={[
                          gpu.temp_c !== null && gpu.temp_c !== undefined ? `${gpu.temp_c}°C` : null,
                          gpu.power_draw_w !== null && gpu.power_draw_w !== undefined ? `${gpu.power_draw_w}W` : null
                        ].filter(Boolean).join(' • ') || (gpu.is_integrated ? 'iGPU Integrata' : 'GPU Dedicata')}
                        color="#bc8cff"
                        isSelected={selectedCardId === `gpu_${idx}`}
                        onClick={() => handleCardClick(`gpu_${idx}`)}
                        isLight={isLight}
                      />

                      {/* GPU Dedicated VRAM Tile */}
                      <CompactSquareMetricTile
                        icon={Layers}
                        category={`VRAM GPU ${idx}`}
                        title={`VRAM ${gpuCleanName}`}
                        fullName={`VRAM ${gpu.name}: ${vramUsedMb} / ${vramTotalMb} MB (${vramFreeMb} MB liberi)`}
                        badge={`VRAM ${idx}`}
                        badgeColor="#ec4899"
                        percentage={vramUsagePct}
                        usedLabel="Allocata"
                        usedVal={vramUsedMb > 0 ? vramUsedDisp : '0 MB'}
                        maxVal={vramTotalMb > 0 ? vramTotalDisp : undefined}
                        subText={vramFreeMb > 0 ? `${vramFreeDisp} Liberi` : (gpu.is_integrated ? 'RAM Condivisa' : 'VRAM GDDR')}
                        color="#ec4899"
                        isSelected={selectedCardId === `vram_${idx}`}
                        onClick={() => handleCardClick(`vram_${idx}`)}
                        isLight={isLight}
                      />
                    </React.Fragment>
                  );
                })
              )
            )}

          </div>
        )}

        {/* =========================================================================
            EXPANDED HARDWARE INSPECTOR DRAWER (Quando si clicca su una card)
           ========================================================================= */}
        {selectedCardId && (
          <div style={{
            borderRadius: '14px',
            background: isLight ? 'linear-gradient(135deg, #ffffff 0%, #f7f4ed 100%)' : 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(10, 14, 26, 0.98) 100%)',
            border: isLight ? '1.5px solid rgba(190, 160, 110, 0.45)' : '1.5px solid rgba(0, 242, 254, 0.45)',
            boxShadow: isLight ? '0 10px 30px rgba(0, 0, 0, 0.08)' : '0 12px 36px rgba(0, 0, 0, 0.6), 0 0 24px rgba(0, 242, 254, 0.12)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            animation: 'fadeIn 0.2s ease-out'
          }}>
            {/* Inspector Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: `${accentColor}20`,
                  border: `1px solid ${accentColor}40`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {selectedCardId === 'cpu' && <Cpu size={16} color={accentColor} />}
                  {selectedCardId === 'ram' && <HardDrive size={16} color="#10b981" />}
                  {selectedCardId === 'storage' && <Database size={16} color="#f59e0b" />}
                  {selectedCardId === 'network' && <Wifi size={16} color="#38bdf8" />}
                  {selectedCardId.startsWith('gpu_') && <Gauge size={16} color="#bc8cff" />}
                  {selectedCardId.startsWith('vram_') && <Layers size={16} color="#ec4899" />}
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: textPrimary }}>
                    {selectedCardId === 'cpu' && cpuFullName}
                    {selectedCardId === 'ram' && `Memoria RAM Host (${ramTotalGb.toFixed(1)} GB Totali)`}
                    {selectedCardId === 'storage' && `Storage & Drive Fisici (${storageTotalDisp} Totali)`}
                    {selectedCardId === 'network' && `Interfaccia di Rete (${netStatus})`}
                    {selectedCardId.startsWith('gpu_') && (gpus[Number(selectedCardId.split('_')[1])]?.name || 'GPU')}
                    {selectedCardId.startsWith('vram_') && `Memoria Video Dedicata ${gpus[Number(selectedCardId.split('_')[1])]?.name || 'GPU'}`}
                  </div>
                  <div style={{ fontSize: '10.5px', color: textDim, fontFamily: 'monospace' }}>
                    {selectedCardId === 'cpu' && `${cpuCoresPhysical} Core Fisici • ${cpuCoresLogical} Thread Logici • Clock ${cpuFreqGhz || 'N/D'} GHz`}
                    {selectedCardId === 'ram' && `Allocati: ${ramUsedGb.toFixed(2)} GB • Liberi: ${ramFreeGb.toFixed(2)} GB • Utilizzo: ${ramUsagePct}%`}
                    {selectedCardId === 'storage' && `Occupati: ${storageUsedDisp} • Liberi: ${storageFreeGb} GB • ${disks.length} Unità Rilevate`}
                    {selectedCardId === 'network' && `Ricevuti: ${(netRecvMb / 1024).toFixed(2)} GB • Inviati: ${(netSentMb / 1024).toFixed(2)} GB`}
                    {selectedCardId.startsWith('gpu_') && `${gpus[Number(selectedCardId.split('_')[1])]?.type || 'CUDA'} • Driver ${gpus[Number(selectedCardId.split('_')[1])]?.telemetry_source || 'N/A'}`}
                    {selectedCardId.startsWith('vram_') && `Capacità: ${(Number(gpus[Number(selectedCardId.split('_')[1])]?.vram_total_mb || 0) / 1024).toFixed(1)} GB • GDDR Dedicata`}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedCardId(null)}
                style={{
                  background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)',
                  border: isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  color: textPrimary,
                  fontSize: '10.5px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <X size={12} /> Chiudi Dettaglio
              </button>
            </div>

            {/* Component Specific Detailed Metrics & Charts */}
            {selectedCardId === 'cpu' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>UTILIZZO LIVE</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#00f2fe' }}>{cpuUsagePct ?? '0'}%</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>CORE FISICI</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{cpuCoresPhysical}</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>THREAD LOGICI</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{cpuCoresLogical}</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>CLOCK FREQUENZA</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#ffb86c' }}>{cpuFreqGhz ? `${cpuFreqGhz} GHz` : 'N/D'}</div>
                  </div>
                </div>
                <RealtimeTelemetryChart 
                  data={systemHistory.cpu} 
                  label={`Carico ${cpuShortName} nel tempo (%)`} 
                  icon={Cpu}
                  color={isLight ? '#0284c7' : '#00f2fe'} 
                  unit="%" 
                  maxVal={100} 
                  height={85}
                  isLight={isLight}
                />
              </div>
            )}

            {selectedCardId === 'ram' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>RAM ALLOCATA</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#10b981' }}>{ramUsedGb.toFixed(2)} GB</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>RAM LIBERA</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{ramFreeGb.toFixed(2)} GB</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>CAPACITÀ TOTALE</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{ramTotalGb.toFixed(2)} GB</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>PERCENTUALE OCCUPATA</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#10b981' }}>{ramUsagePct}%</div>
                  </div>
                </div>
                <RealtimeTelemetryChart 
                  data={systemHistory.ram} 
                  label="Allocazione Memoria RAM Host nel tempo (GB)" 
                  icon={HardDrive}
                  color={isLight ? '#16a34a' : '#10b981'} 
                  unit="GB" 
                  maxVal={ramTotalGb > 0 ? ramTotalGb : 96} 
                  height={85}
                  isLight={isLight}
                  formatVal={(val) => `${typeof val === 'number' ? val.toFixed(2) : val}`}
                />
              </div>
            )}

            {selectedCardId === 'storage' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>SPAZIO OCCUPATO</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#f59e0b' }}>{storageUsedDisp}</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>SPAZIO LIBERO</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{storageFreeGb} GB</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>LETTURA I/O</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#00f2fe' }}>{storageReadMbps} MB/s</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>SCRITTURA I/O</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#ffb86c' }}>{storageWriteMbps} MB/s</div>
                  </div>
                </div>

                {/* Individual Partitions List */}
                {disks.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: isLight ? '#fff' : 'rgba(0,0,0,0.2)', padding: '10px 12px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 800, color: textPrimary }}>Partizioni Fisiche Rilevate</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {disks.map((d, i) => (
                        <div key={i} style={{ fontSize: '11px', fontFamily: 'monospace' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                            <span style={{ fontWeight: 800, color: textPrimary }}>Unità {d.device || d.mountpoint}</span>
                            <span style={{ color: '#f59e0b' }}>{d.used_gb} / {d.total_gb} GB ({d.usage_pct}%)</span>
                          </div>
                          <div style={{ height: '4px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${Math.min(100, d.usage_pct)}%`, background: '#f59e0b' }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {selectedCardId === 'network' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>DOWNLOAD LIVE</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#38bdf8' }}>{netDownKbps.toFixed(1)} KB/s</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>UPLOAD LIVE</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: '#00f2fe' }}>{netUpKbps.toFixed(1)} KB/s</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>TOTALE RICEVUTI</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{netRecvMb > 1024 ? `${(netRecvMb / 1024).toFixed(2)} GB` : `${netRecvMb.toFixed(1)} MB`}</div>
                  </div>
                  <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>TOTALE INVIATI</div>
                    <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{netSentMb > 1024 ? `${(netSentMb / 1024).toFixed(2)} GB` : `${netSentMb.toFixed(1)} MB`}</div>
                  </div>
                </div>
                <RealtimeTelemetryChart 
                  data={systemHistory.net_down} 
                  label="Throughput Download Live (KB/s)" 
                  icon={ArrowDown}
                  color={isLight ? '#0284c7' : '#38bdf8'} 
                  unit="KB/s" 
                  maxVal={5000} 
                  height={85}
                  isLight={isLight}
                />
              </div>
            )}

            {selectedCardId.startsWith('gpu_') && (() => {
              const idx = Number(selectedCardId.split('_')[1]);
              const gpu = gpus[idx];
              if (!gpu) return null;
              const hist = historyData[idx] || { compute: [], vram: [] };
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>UTILIZZO COMPUTE</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#bc8cff' }}>{gpu.gpu_util_pct ?? '0'}%</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>TEMPERATURA</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#ef4444' }}>{gpu.temp_c ? `${gpu.temp_c}°C` : 'N/D'}</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>ASSORBIMENTO WATT</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#ffb86c' }}>{gpu.power_draw_w ? `${gpu.power_draw_w} W` : 'N/D'}</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>VENTOLE SPEED</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{gpu.fan_speed_pct ? `${gpu.fan_speed_pct}%` : 'Auto'}</div>
                    </div>
                  </div>
                  <RealtimeTelemetryChart 
                    data={hist.compute} 
                    label={`Compute ${gpu.name} nel tempo (%)`} 
                    icon={Gauge}
                    color={isLight ? '#7c3aed' : '#bc8cff'} 
                    unit="%" 
                    maxVal={100} 
                    height={85}
                    isLight={isLight}
                  />
                </div>
              );
            })()}

            {selectedCardId.startsWith('vram_') && (() => {
              const idx = Number(selectedCardId.split('_')[1]);
              const gpu = gpus[idx];
              if (!gpu) return null;
              const hist = historyData[idx] || { compute: [], vram: [] };
              const vramTotalMb = Number(gpu.vram_total_mb) || 0;
              const vramUsedMb = Number(gpu.vram_used_mb) || 0;
              const vramFreeMb = Math.max(0, vramTotalMb - vramUsedMb);
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>VRAM ALLOCATA</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#ec4899' }}>{(vramUsedMb / 1024).toFixed(2)} GB</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>VRAM LIBERA</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{(vramFreeMb / 1024).toFixed(2)} GB</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>VRAM TOTALE</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: textPrimary }}>{(vramTotalMb / 1024).toFixed(2)} GB</div>
                    </div>
                    <div style={{ background: isLight ? '#fff' : 'rgba(255,255,255,0.04)', padding: '8px 10px', borderRadius: '8px', border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '9px', color: textDim, fontWeight: 700 }}>PERCENTUALE ALLOCAZIONE</div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#ec4899' }}>{vramTotalMb > 0 ? Math.round((vramUsedMb / vramTotalMb) * 100) : 0}%</div>
                    </div>
                  </div>
                  <RealtimeTelemetryChart 
                    data={hist.vram} 
                    label={`Allocazione VRAM ${gpu.name} (MB)`} 
                    icon={Layers}
                    color={isLight ? '#db2777' : '#ec4899'} 
                    unit="MB" 
                    maxVal={vramTotalMb > 0 ? vramTotalMb : 16384} 
                    height={85}
                    isLight={isLight}
                  />
                </div>
              );
            })()}

          </div>
        )}

        {/* =========================================================================
            REALTIME HISTORICAL CHARTS DRAWER (Global toggle)
           ========================================================================= */}
        {showCharts && !selectedCardId && (
          <div style={{
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.75)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ fontSize: '11px', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <BarChart2 size={13} color={accentColor} /> Grafici Telemetria Storica in Tempo Reale
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <RealtimeTelemetryChart 
                data={systemHistory.cpu} 
                label={`Carico CPU (%)`} 
                icon={Cpu}
                color={isLight ? '#0284c7' : '#00f2fe'} 
                unit="%" 
                maxVal={100} 
                height={70}
                isLight={isLight}
              />
              <RealtimeTelemetryChart 
                data={systemHistory.ram} 
                label="RAM Host (GB)" 
                icon={HardDrive}
                color={isLight ? '#16a34a' : '#10b981'} 
                unit="GB" 
                maxVal={ramTotalGb > 0 ? ramTotalGb : 96} 
                height={70}
                isLight={isLight}
                formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
              />
            </div>

            {gpus.length > 0 && gpus.map(gpu => {
              const hist = historyData[gpu.index] || { vram: [], compute: [] };
              return (
                <div key={`chart-gpu-${gpu.index}`} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <RealtimeTelemetryChart 
                    data={hist.compute} 
                    label={`GPU ${gpu.index} Compute (%)`} 
                    icon={Gauge}
                    color={isLight ? '#7c3aed' : '#bc8cff'} 
                    unit="%" 
                    maxVal={100} 
                    height={70}
                    isLight={isLight}
                  />
                  <RealtimeTelemetryChart 
                    data={hist.vram} 
                    label={`GPU ${gpu.index} VRAM (MB)`} 
                    icon={Layers}
                    color={isLight ? '#db2777' : '#ec4899'} 
                    unit="MB" 
                    maxVal={Number(gpu.vram_total_mb) || 16384} 
                    height={70}
                    isLight={isLight}
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* =========================================================================
            PROCESSES & MODULES MEMORY TABLE
           ========================================================================= */}
        {(activeCategory === 'all' || activeCategory === 'processes') && (
          <div style={{
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.75)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)',
            overflow: 'hidden'
          }}>
            {/* Processes Header */}
            <div style={{
              padding: '8px 12px',
              background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(0,0,0,0.3)',
              borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Zap size={13} color={accentColor} />
                <span style={{ fontSize: '11px', fontWeight: 800, color: textPrimary }}>
                  Processi & Moduli Sigma ({gpuProcs.processes.length})
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {/* Process Search */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: isLight ? '#fff' : 'rgba(255, 255, 255, 0.05)',
                  border: isLight ? '1px solid rgba(0,0,0,0.1)' : '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '5px',
                  padding: '2px 6px'
                }}>
                  <Search size={10} color={textDim} />
                  <input
                    type="text"
                    placeholder="Cerca PID / modulo..."
                    value={procSearch}
                    onChange={(e) => setProcSearch(e.target.value)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: textPrimary,
                      fontSize: '10px',
                      outline: 'none',
                      width: '110px'
                    }}
                  />
                </div>

                {/* Kill All Orphans Batch */}
                {gpuProcs.orfani > 0 && (
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch('/api/hardware/gpu/kill', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ all_orphans: true })
                        });
                        const json = await res.json();
                        if (addToast) addToast(json.message || 'Processi orfani terminati.', 'success');
                        fetchGpuProcesses();
                        fetchHardwareStatus();
                      } catch (e) {}
                    }}
                    style={{
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      color: '#ef4444',
                      borderRadius: '5px',
                      padding: '2px 7px',
                      fontSize: '9.5px',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}
                  >
                    Kill {gpuProcs.orfani} Orfani
                  </button>
                )}
              </div>
            </div>

            {/* Processes List Body */}
            <div style={{ maxHeight: '160px', overflowY: 'auto' }}>
              {filteredProcesses.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '14px', fontSize: '10.5px', color: textDim }}>
                  {gpuProcs.processes.length === 0 ? 'Nessun processo AI attivo al momento.' : 'Nessun processo corrispondente al criterio di ricerca.'}
                </div>
              ) : (
                filteredProcesses.slice(0, 20).map(proc => (
                  <div key={proc.pid} style={{
                    padding: '6px 12px',
                    borderBottom: isLight ? '1px solid rgba(0,0,0,0.04)' : '1px solid rgba(255,255,255,0.04)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '8px',
                    fontSize: '10.5px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: 800, color: textDim, fontSize: '9.5px' }}>#{proc.pid}</span>
                      <span style={{ fontWeight: 700, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {proc.name}
                      </span>
                      <span style={{ fontSize: '9px', padding: '1px 5px', borderRadius: '3px', background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)', color: textDim, fontWeight: 700 }}>
                        {proc.module_name || proc.user || 'Sigma'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                      {proc.vram_mb > 0 && (
                        <span style={{ fontFamily: 'monospace', color: accentColor, fontWeight: 800, fontSize: '10px' }}>
                          {proc.vram_mb} MB VRAM
                        </span>
                      )}
                      <span style={{ fontFamily: 'monospace', color: textDim, fontSize: '10px' }}>
                        {proc.memory_mb || 0} MB RAM
                      </span>
                      {proc.killable ? (
                        <button
                          onClick={() => handleKillGpuProcess(proc)}
                          disabled={killingPid === proc.pid}
                          style={{
                            background: 'rgba(239, 68, 68, 0.12)',
                            border: '1px solid rgba(239, 68, 68, 0.35)',
                            color: '#ef4444',
                            borderRadius: '4px',
                            padding: '2px 6px',
                            fontSize: '9px',
                            fontWeight: 800,
                            cursor: 'pointer'
                          }}
                        >
                          {killingPid === proc.pid ? '...' : 'Kill'}
                        </button>
                      ) : (
                        <span style={{ fontSize: '9px', color: '#00d2ff', fontWeight: 800 }}>Protetto</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
