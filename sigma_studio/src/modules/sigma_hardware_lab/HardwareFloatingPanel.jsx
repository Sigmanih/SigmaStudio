import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Zap, Activity, ShieldCheck, Play, Pause, X, GripVertical, Maximize2, RotateCcw,
  HardDrive, Cpu, Thermometer, Flame, Gauge, Sliders, BarChart2, AlertTriangle, Database,
  Terminal, Search, Trash2, ChevronRight
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import { useApp } from '../../contexts/AppContext';
import './styles/hardware-lab.css';
import '../../styles/chat.css';

const MIN_WIDTH = 500;
const MIN_HEIGHT = 400;
const MAX_HISTORY = 900;

export default function HardwareFloatingPanel({ onClose, onOpenTab, addToast }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [panelPos, setPanelPos] = useState({ x: undefined, y: undefined });
  const [panelSize, setPanelSize] = useState({ width: 700, height: 550 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [resizing, setResizing] = useState(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0 });
  const resizeSizeStart = useRef({ width: 700, height: 550 });
  const resizePosStart = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(3000);
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'processes' | 'charts'
  const [procSearch, setProcSearch] = useState('');
  const [showRestartAlert, setShowRestartAlert] = useState(false);
  const [restartingOllama, setRestartingOllama] = useState(false);

  // History buffers per GPU index & System
  const [historyData, setHistoryData] = useState({});
  const historyRef = useRef({});
  const [systemHistory, setSystemHistory] = useState({ cpu: [], ram: [] });
  const systemHistoryRef = useRef({ cpu: [], ram: [] });

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

          // 2. Accumulate System CPU & RAM History
          const cpuUtil = Number(json.hardware?.cpu?.usage_pct ?? json.hardware?.cpu?.util_pct) || 0;
          const ramUsed = Number(json.hardware?.ram?.used_gb ?? json.hardware?.ram?.ram_used_gb) || 0;

          const currentSysHist = { ...systemHistoryRef.current };
          const newCpu = [...(currentSysHist.cpu || []), cpuUtil];
          const newRam = [...(currentSysHist.ram || []), ramUsed];

          if (newCpu.length > MAX_HISTORY) newCpu.shift();
          if (newRam.length > MAX_HISTORY) newRam.shift();

          systemHistoryRef.current = { cpu: newCpu, ram: newRam };
          setSystemHistory({ cpu: newCpu, ram: newRam });
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

  // Il bottone "Svuota VRAM" del dialogo di conferma lo chiamava senza che
  // esistesse: aprire quel dialogo faceva cadere il pannello con un
  // ReferenceError, perche' in JSX il riferimento viene valutato al render.
  const handleRestartOllama = async () => {
    setRestartingOllama(true);
    try {
      const res = await fetch('/api/hardware/restart-ollama', { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        if (addToast) addToast(json.message || 'VRAM liberata.', 'success');
      } else if (addToast) {
        addToast(json.error || 'Impossibile liberare la VRAM.', 'error');
      }
      // La telemetria va riletta subito: il senso del gesto e' vedere la
      // memoria scendere, e aspettare il tick successivo la fa sembrare inerte.
      fetchHardwareStatus();
      fetchGpuProcesses();
    } catch (e) {
      if (addToast) addToast(`Errore: ${e.message}`, 'error');
    } finally {
      setRestartingOllama(false);
      setShowRestartAlert(false);
    }
  };

  useEffect(() => {
    fetchHardwareStatus();
    fetchGpuProcesses();
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchHardwareStatus();
    }, refreshInterval);
    const procInterval = setInterval(() => {
      fetchGpuProcesses();
    }, refreshInterval * 2);
    return () => {
      clearInterval(interval);
      clearInterval(procInterval);
    };
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
          y: (prev.y !== undefined ? prev.y : 80) + dy
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
    const initialY = panelPos.y !== undefined ? panelPos.y : 80;
    setPanelPos({ x: initialX, y: initialY });
    setDragStart({ x: e.clientX, y: e.clientY });
    setIsDragging(true);
  };

  const handleMouseDownResize = (e, dir) => {
    e.stopPropagation();
    const currX = panelPos.x !== undefined ? panelPos.x : (window.innerWidth - panelSize.width) / 2;
    const currY = panelPos.y !== undefined ? panelPos.y : 80;
    resizePosStart.current = { x: currX, y: currY };
    resizeSizeStart.current = { width: panelSize.width, height: panelSize.height };
    setResizeStart({ x: e.clientX, y: e.clientY });
    setResizing(dir);
  };

  const hw = data?.hardware || {};
  const gpus = hw.gpu || [];
  const cpu = hw.cpu || {};
  const ram = hw.ram || {};
  const storage = hw.storage || {};

  const totalVramMb = gpus.reduce((acc, g) => acc + (Number(g.vram_total_mb) || 0), 0);
  const usedVramMb = gpus.reduce((acc, g) => acc + (Number(g.vram_used_mb) || 0), 0);
  const totalVramPct = totalVramMb > 0 ? Math.min(100, Math.round((usedVramMb / totalVramMb) * 100)) : 0;

  const cpuUsage = Math.min(100, Math.round(Number(cpu.usage_pct ?? cpu.util_pct) || 0));
  const ramUsedGb = Number(ram.used_gb ?? ram.ram_used_gb) || 0;
  const ramTotalGb = Number(ram.total_gb ?? ram.ram_total_gb) || 0;
  const ramPct = ramTotalGb > 0 ? Math.min(100, Math.round((ramUsedGb / ramTotalGb) * 100)) : 0;

  const maxGpuTemp = gpus.reduce((max, g) => Math.max(max, Number(g.temp_c) || 0), 0);
  const totalGpuPower = gpus.reduce((acc, g) => acc + (Number(g.power_draw_w) || 0), 0);

  const formatMbToGb = (mb) => {
    const n = Number(mb) || 0;
    if (n >= 1024) {
      return `${(n / 1024).toFixed(1)} GB`;
    }
    return `${Math.round(n)} MB`;
  };

  const filteredProcs = (gpuProcs.processes || []).filter(p => {
    if (!procSearch) return true;
    const q = procSearch.toLowerCase();
    return (
      String(p.pid).includes(q) ||
      (p.name && p.name.toLowerCase().includes(q)) ||
      (p.module_name && p.module_name.toLowerCase().includes(q))
    );
  });

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x)) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y)) ? panelPos.y : undefined;

  const resizeHandles = [
    { dir: 'n' }, { dir: 's' }, { dir: 'e' }, { dir: 'w' },
    { dir: 'ne' }, { dir: 'nw' }, { dir: 'se' }, { dir: 'sw' }
  ];

  // Theme Design Tokens
  const panelBg = isLight ? '#fffdf9' : 'rgba(9, 13, 22, 0.97)';
  const panelBorder = isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 242, 254, 0.28)';
  const panelShadow = isLight 
    ? '0 24px 60px rgba(0, 0, 0, 0.18), 0 0 20px rgba(234, 88, 12, 0.08)' 
    : '0 32px 64px -16px rgba(0, 0, 0, 0.85), 0 0 30px rgba(0, 242, 254, 0.18)';
  const headerBg = isLight ? '#f4efe4' : 'rgba(13, 20, 34, 0.85)';
  const headerBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardBg = isLight ? '#ffffff' : 'rgba(15, 23, 40, 0.75)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 2px 6px rgba(0,0,0,0.05)' : '0 4px 20px rgba(0,0,0,0.45)';
  const textPrimary = isLight ? '#111111' : '#f8fafc';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textDim = isLight ? '#6b7280' : '#94a3b8';
  const accentColor = isLight ? '#ea580c' : '#00f2fe';
  const headerBtnBg = isLight ? '#fffdf9' : 'rgba(255, 255, 255, 0.05)';
  const headerBtnBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.1)';

  return (
    <div
      ref={panelRef}
      className={`task-floating-panel hw-floating-panel ${resizing ? 'is-resizing' : ''}`}
      style={{
        position: 'fixed',
        zIndex: 10002,
        ...(safeX !== undefined ? { left: safeX, right: 'auto' } : { left: '50%', marginLeft: -panelSize.width / 2 }),
        ...(safeY !== undefined ? { bottom: 'auto', top: safeY } : { top: 80 }),
        width: `${panelSize.width}px`,
        height: `${panelSize.height}px`,
        maxHeight: 'calc(100vh - 90px)',
        background: panelBg,
        border: panelBorder,
        borderRadius: '18px',
        boxShadow: panelShadow,
        backdropFilter: 'blur(24px) saturate(190%)',
        WebkitBackdropFilter: 'blur(24px) saturate(190%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* Top subtle neon glow line */}
      <div style={{
        height: '2px',
        width: '100%',
        background: isLight 
          ? 'linear-gradient(90deg, #ea580c 0%, #d97706 50%, #16a34a 100%)' 
          : 'linear-gradient(90deg, #00f2fe 0%, #a855f7 50%, #10b981 100%)',
        boxShadow: isLight ? 'none' : '0 0 10px rgba(0, 242, 254, 0.5)'
      }} />

      {/* CONFIRMATION ALERT MODAL */}
      {showRestartAlert && (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
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
            border: '1px solid rgba(239, 68, 68, 0.5)',
            borderRadius: '14px',
            padding: '22px',
            boxShadow: '0 25px 50px rgba(0, 0, 0, 0.9), 0 0 25px rgba(239, 68, 68, 0.2)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '8px', borderRadius: '10px', display: 'flex' }}>
                <AlertTriangle size={20} color="#ef4444" />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: textPrimary }}>Riavvio & Pulizia VRAM</h3>
                <div style={{ fontSize: '11px', color: textDim }}>Scarica tutti i modelli residenti</div>
              </div>
            </div>

            <div style={{ fontSize: '12px', color: textSecondary, lineHeight: '1.5', marginBottom: '18px', background: isLight ? '#f4efe4' : 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid #ef4444' }}>
              Questa azione scaricherà immediatamente tutti i modelli residenti nella VRAM/RAM GPU e riallineerà il runtime. Continuare?
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
                style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: '#fff', border: 'none', fontWeight: 800, fontSize: '12px', padding: '6px 14px', display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}
              >
                {restartingOllama ? <Activity className="spin" size={13} /> : <RotateCcw size={13} />}
                {restartingOllama ? 'Svuotamento...' : 'Conferma Svuotamento'}
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

      {/* Header — Drag Handle */}
      <div 
        className="task-floating-header" 
        onMouseDown={handleMouseDownHeader}
        style={{ 
          cursor: isDragging ? 'grabbing' : 'grab',
          padding: '12px 18px',
          background: headerBg,
          borderBottom: headerBorder,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <GripVertical size={16} color={textDim} />
          <div style={{
            width: '26px', height: '26px', borderRadius: '7px',
            background: isLight ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 242, 254, 0.15)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 242, 254, 0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Zap size={15} color={accentColor} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 900, fontSize: '13px', color: textPrimary, letterSpacing: '0.4px' }}>
                HARDWARE TELEMETRY HUD
              </span>
              <span className="hw-badge hw-badge-live" style={{ fontSize: '9px', padding: '2px 7px' }}>
                <span className="hw-badge-dot" />
                LIVE
              </span>
            </div>
            <div style={{ fontSize: '10px', color: textDim, fontFamily: 'monospace' }}>
              {gpus.length} Acceleratori GPU • {cpu.name ? cpu.name.split(' ')[0] : 'Host'} • {ramTotalGb.toFixed(0)} GB RAM
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button 
            onClick={() => setShowRestartAlert(true)} 
            className="chat-header-btn" 
            title="Svuota la memoria VRAM scaricando tutti i modelli residenti"
            style={{ 
              background: isLight ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.15)', 
              border: '1px solid rgba(239, 68, 68, 0.35)', 
              borderRadius: '8px', 
              padding: '5px 10px', 
              cursor: 'pointer', 
              color: isLight ? '#dc2626' : '#fca5a5', 
              fontSize: '11px', 
              fontWeight: 800,
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <RotateCcw size={12} color="#ef4444" />
            <span>Svuota VRAM</span>
          </button>

          {onOpenTab && (
            <button 
              onClick={() => onOpenTab({ name: 'Monitor Hardware' }, 'hardware_lab')} 
              className="chat-header-btn" 
              title="Apri scheda estesa con grafici di approfondimento e telemetria continua"
              style={{ 
                background: isLight ? 'rgba(0, 210, 255, 0.12)' : 'rgba(0, 242, 254, 0.12)', 
                border: isLight ? '1px solid rgba(0, 210, 255, 0.35)' : '1px solid rgba(0, 242, 254, 0.35)', 
                borderRadius: '8px', 
                padding: '5px 10px', 
                cursor: 'pointer', 
                color: isLight ? '#0284c7' : '#00f2fe',
                fontSize: '11px',
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Maximize2 size={12} color={accentColor} />
              <span>Info Avanzate</span>
            </button>
          )}

          <button 
            onClick={onClose} 
            className="chat-header-btn" 
            title="Chiudi pannello"
            style={{ 
              background: headerBtnBg, 
              border: headerBtnBorder, 
              borderRadius: '8px', 
              padding: '5px 8px', 
              cursor: 'pointer', 
              color: textPrimary 
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Floating Panel Body */}
      <div className="task-floating-body" style={{ padding: '14px 18px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* 1. CYBERPUNK HUD RIBBON - KEY METRICS AT FIRST GLANCE */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: '8px'
        }}>
          {/* HUD 1: VRAM POOL */}
          <div style={{
            padding: '10px 12px',
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.05)',
            border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 242, 254, 0.2)',
            boxShadow: isLight ? '0 2px 4px rgba(0,0,0,0.04)' : '0 0 15px rgba(0, 242, 254, 0.06)',
            display: 'flex', flexDirection: 'column', gap: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#0284c7' : '#00f2fe', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Zap size={11} color={isLight ? '#0284c7' : '#00f2fe'} /> VRAM POOL
              </span>
              <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                {totalVramPct}%
              </span>
            </div>
            <div style={{ fontSize: '0.92rem', fontWeight: 900, color: textPrimary, fontFamily: 'JetBrains Mono, monospace' }}>
              {formatMbToGb(usedVramMb)}
              <span style={{ fontSize: '0.68rem', fontWeight: 600, color: textDim, marginLeft: '3px' }}>/ {formatMbToGb(totalVramMb)}</span>
            </div>
            <div style={{ height: '4px', borderRadius: '2px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${totalVramPct}%`, background: 'linear-gradient(90deg, #00f2fe, #38bdf8)', borderRadius: '2px', boxShadow: '0 0 8px #00f2fe', transition: 'width 0.3s ease' }} />
            </div>
          </div>

          {/* HUD 2: CPU COMPUTE */}
          <div style={{
            padding: '10px 12px',
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(188, 140, 255, 0.05)',
            border: isLight ? '1px solid rgba(124, 58, 237, 0.25)' : '1px solid rgba(188, 140, 255, 0.2)',
            boxShadow: isLight ? '0 2px 4px rgba(0,0,0,0.04)' : '0 0 15px rgba(188, 140, 255, 0.06)',
            display: 'flex', flexDirection: 'column', gap: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Cpu size={11} color={isLight ? '#7c3aed' : '#bc8cff'} /> CPU HOST
              </span>
              <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
                {cpu.cores_logical || 24}T
              </span>
            </div>
            <div style={{ fontSize: '0.92rem', fontWeight: 900, color: textPrimary, fontFamily: 'JetBrains Mono, monospace' }}>
              {cpuUsage}%
              <span style={{ fontSize: '0.68rem', fontWeight: 600, color: textDim, marginLeft: '3px' }}>
                {cpu.freq_mhz ? `@ ${(cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'Load'}
              </span>
            </div>
            <div style={{ height: '4px', borderRadius: '2px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${cpuUsage}%`, background: 'linear-gradient(90deg, #bc8cff, #a855f7)', borderRadius: '2px', boxShadow: '0 0 8px #bc8cff', transition: 'width 0.3s ease' }} />
            </div>
          </div>

          {/* HUD 3: RAM HOST */}
          <div style={{
            padding: '10px 12px',
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(16, 185, 129, 0.05)',
            border: isLight ? '1px solid rgba(22, 163, 74, 0.25)' : '1px solid rgba(16, 185, 129, 0.2)',
            boxShadow: isLight ? '0 2px 4px rgba(0,0,0,0.04)' : '0 0 15px rgba(16, 185, 129, 0.06)',
            display: 'flex', flexDirection: 'column', gap: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#16a34a' : '#10b981', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <HardDrive size={11} color={isLight ? '#16a34a' : '#10b981'} /> RAM HOST
              </span>
              <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                {ramPct}%
              </span>
            </div>
            <div style={{ fontSize: '0.92rem', fontWeight: 900, color: textPrimary, fontFamily: 'JetBrains Mono, monospace' }}>
              {ramUsedGb.toFixed(1)}
              <span style={{ fontSize: '0.68rem', fontWeight: 600, color: textDim, marginLeft: '3px' }}>/ {ramTotalGb.toFixed(0)} GB</span>
            </div>
            <div style={{ height: '4px', borderRadius: '2px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${ramPct}%`, background: 'linear-gradient(90deg, #10b981, #059669)', borderRadius: '2px', boxShadow: '0 0 8px #10b981', transition: 'width 0.3s ease' }} />
            </div>
          </div>

          {/* HUD 4: TERMICHE & CONSUMI */}
          <div style={{
            padding: '10px 12px',
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(245, 158, 11, 0.05)',
            border: isLight ? '1px solid rgba(217, 119, 6, 0.25)' : '1px solid rgba(245, 158, 11, 0.2)',
            boxShadow: isLight ? '0 2px 4px rgba(0,0,0,0.04)' : '0 0 15px rgba(245, 158, 11, 0.06)',
            display: 'flex', flexDirection: 'column', gap: '4px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#d97706' : '#f59e0b', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Flame size={11} color={isLight ? '#d97706' : '#f59e0b'} /> TERMICHE
              </span>
              <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#d97706' : '#f59e0b', fontFamily: 'JetBrains Mono, monospace' }}>
                {totalGpuPower > 0 ? `${totalGpuPower.toFixed(0)}W` : 'OK'}
              </span>
            </div>
            <div style={{ fontSize: '0.92rem', fontWeight: 900, color: textPrimary, fontFamily: 'JetBrains Mono, monospace' }}>
              {maxGpuTemp > 0 ? `${maxGpuTemp}°C` : 'N/A'}
              <span style={{ fontSize: '0.68rem', fontWeight: 600, color: textDim, marginLeft: '3px' }}>
                {maxGpuTemp < 60 ? 'Normale' : maxGpuTemp < 75 ? 'Caldo' : 'Elevato'}
              </span>
            </div>
            <div style={{ height: '4px', borderRadius: '2px', background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, (maxGpuTemp / 90) * 100)}%`, background: maxGpuTemp > 75 ? '#ef4444' : maxGpuTemp > 60 ? '#f59e0b' : '#10b981', borderRadius: '2px', transition: 'width 0.3s ease' }} />
            </div>
          </div>
        </div>

        {/* 2. TABS SELECTOR SWITCHER */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          padding: '4px',
          background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(0,0,0,0.35)',
          borderRadius: '10px',
          border: cardBorder
        }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              onClick={() => setActiveTab('overview')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', borderRadius: '7px',
                border: 'none',
                background: activeTab === 'overview' ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.15)') : 'transparent',
                color: activeTab === 'overview' ? (isLight ? '#111827' : '#00f2fe') : textDim,
                boxShadow: activeTab === 'overview' ? (isLight ? '0 1px 3px rgba(0,0,0,0.1)' : '0 0 10px rgba(0, 242, 254, 0.2)') : 'none',
                fontSize: '11px', fontWeight: activeTab === 'overview' ? 800 : 600,
                cursor: 'pointer', transition: 'all 0.15s ease'
              }}
            >
              <Zap size={12} color={activeTab === 'overview' ? (isLight ? '#ea580c' : '#00f2fe') : textDim} />
              <span>Dispositivi ({gpus.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('processes')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', borderRadius: '7px',
                border: 'none',
                background: activeTab === 'processes' ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.15)') : 'transparent',
                color: activeTab === 'processes' ? (isLight ? '#111827' : '#00f2fe') : textDim,
                boxShadow: activeTab === 'processes' ? (isLight ? '0 1px 3px rgba(0,0,0,0.1)' : '0 0 10px rgba(0, 242, 254, 0.2)') : 'none',
                fontSize: '11px', fontWeight: activeTab === 'processes' ? 800 : 600,
                cursor: 'pointer', transition: 'all 0.15s ease'
              }}
            >
              <Terminal size={12} color={activeTab === 'processes' ? (isLight ? '#ea580c' : '#00f2fe') : textDim} />
              <span>Processi ({gpuProcs.processes.length})</span>
              {gpuProcs.orfani > 0 && (
                <span style={{
                  fontSize: '9px', padding: '1px 5px', borderRadius: '4px',
                  background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', fontWeight: 800
                }}>
                  {gpuProcs.orfani} orfani
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('charts')}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', borderRadius: '7px',
                border: 'none',
                background: activeTab === 'charts' ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.15)') : 'transparent',
                color: activeTab === 'charts' ? (isLight ? '#111827' : '#00f2fe') : textDim,
                boxShadow: activeTab === 'charts' ? (isLight ? '0 1px 3px rgba(0,0,0,0.1)' : '0 0 10px rgba(0, 242, 254, 0.2)') : 'none',
                fontSize: '11px', fontWeight: activeTab === 'charts' ? 800 : 600,
                cursor: 'pointer', transition: 'all 0.15s ease'
              }}
            >
              <BarChart2 size={12} color={activeTab === 'charts' ? (isLight ? '#ea580c' : '#00f2fe') : textDim} />
              <span>Grafici Live</span>
            </button>
          </div>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Metti in pausa telemetria' : 'Riprendi telemetria live'}
            style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              padding: '4px 8px', borderRadius: '6px',
              border: cardBorder, background: 'transparent',
              color: textDim, fontSize: '10px', cursor: 'pointer'
            }}
          >
            {autoRefresh ? <Pause size={10} color={accentColor} /> : <Play size={10} />}
            <span style={{ fontFamily: 'monospace' }}>{autoRefresh ? '3s' : 'Pausa'}</span>
          </button>
        </div>

        {/* 3. TAB CONTENT */}

        {/* TAB 1: OVERVIEW (DISPOSITIVI, GPU & SISTEMA) */}
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* MULTI-GPU CARDS */}
            {gpus.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 16px', color: textDim }}>
                {loading ? (
                  <>
                    <Activity className="spin" size={26} color={accentColor} style={{ margin: '0 auto 8px' }} />
                    <div style={{ fontSize: '12px', color: textPrimary }}>Rilevamento telemetria hardware in corso...</div>
                  </>
                ) : (
                  <div style={{ fontSize: '12px', color: textSecondary }}>⚠️ Nessuna GPU rilevata nel sistema.</div>
                )}
              </div>
            ) : (
              gpus.map((gpu) => {
                const vramTotal = Number(gpu.vram_total_mb) || 1;
                const vramUsed = Number(gpu.vram_used_mb) || 0;
                const vramPct = vramTotal > 0 ? Math.min(100, Math.round((vramUsed / vramTotal) * 100)) : 0;
                const utilPct = Math.min(100, Math.round(Number(gpu.gpu_util_pct) || 0));
                const pwrDraw = Number(gpu.power_draw_w) || 0;
                const tempC = Number(gpu.temp_c) || 0;
                const isIntegrated = gpu.is_integrated;
                const idx = gpu.index;

                return (
                  <div
                    key={idx}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '12px',
                      background: cardBg,
                      border: cardBorder,
                      boxShadow: cardShadow,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '9px',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                  >
                    {/* Top subtle neon line */}
                    <div style={{
                      position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
                      background: isIntegrated 
                        ? 'linear-gradient(90deg, #ea580c, transparent)' 
                        : idx === 0 
                          ? 'linear-gradient(90deg, #00f2fe, #a855f7, transparent)'
                          : 'linear-gradient(90deg, #38bdf8, transparent)'
                    }} />

                    {/* GPU Header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                        <div style={{
                          width: '32px', height: '32px', borderRadius: '8px',
                          background: isIntegrated ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 242, 254, 0.15)',
                          border: isIntegrated ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 242, 254, 0.35)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontWeight: 900, fontSize: '0.75rem',
                          color: isIntegrated ? '#ea580c' : '#00f2fe',
                          fontFamily: 'JetBrains Mono, monospace'
                        }}>
                          G{idx}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ fontWeight: 800, fontSize: '0.88rem', color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {gpu.name}
                            </span>
                            <span style={{
                              fontSize: '0.62rem', padding: '1px 6px', borderRadius: '4px',
                              background: isIntegrated ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 242, 254, 0.12)',
                              color: isIntegrated ? '#ea580c' : (isLight ? '#0284c7' : '#00f2fe'),
                              fontWeight: 700
                            }}>
                              {gpu.vendor || (isIntegrated ? 'AMD APU' : 'NVIDIA CUDA')}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.66rem', color: textDim, fontFamily: 'JetBrains Mono, monospace', marginTop: '1px' }}>
                            {gpu.driver_version ? `Driver ${gpu.driver_version}` : 'Dispositivo Attivo'}
                          </div>
                        </div>
                      </div>

                      {/* Telemetry badges */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {tempC > 0 && (
                          <span style={{
                            fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                            background: tempC > 75 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                            border: tempC > 75 ? '1px solid rgba(239, 68, 68, 0.4)' : cardBorder,
                            color: tempC > 75 ? '#ef4444' : tempC > 60 ? '#f59e0b' : '#10b981',
                            fontFamily: 'JetBrains Mono, monospace', fontWeight: 800,
                            display: 'flex', alignItems: 'center', gap: '3px'
                          }}>
                            <Thermometer size={10} /> {tempC}°C
                          </span>
                        )}
                        {pwrDraw > 0 && (
                          <span style={{
                            fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                            background: 'rgba(255, 255, 255, 0.05)', border: cardBorder,
                            color: textDim, fontFamily: 'JetBrains Mono, monospace', fontWeight: 700,
                            display: 'flex', alignItems: 'center', gap: '3px'
                          }}>
                            <Zap size={10} color="#f59e0b" /> {pwrDraw}W
                          </span>
                        )}
                        <span style={{
                          fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                          background: utilPct > 70 ? 'rgba(188, 140, 255, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                          border: utilPct > 70 ? '1px solid rgba(188, 140, 255, 0.4)' : cardBorder,
                          color: utilPct > 70 ? '#bc8cff' : textPrimary,
                          fontFamily: 'JetBrains Mono, monospace', fontWeight: 800
                        }}>
                          {utilPct}% Load
                        </span>
                      </div>
                    </div>

                    {/* Active LLM Model Badge */}
                    {gpu.active_model && (
                      <div style={{
                        padding: '4px 10px', borderRadius: '6px',
                        background: 'rgba(168, 85, 247, 0.12)', border: '1px solid rgba(168, 85, 247, 0.3)',
                        display: 'flex', alignItems: 'center', gap: '6px',
                        fontSize: '0.7rem', color: '#c084fc', fontWeight: 700
                      }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981' }} />
                        Modello LLM Residente: <strong style={{ color: '#fff' }}>{gpu.active_model}</strong>
                      </div>
                    )}

                    {/* Dual Gauges Grid: VRAM & COMPUTE */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {/* VRAM Gauge */}
                      <div style={{
                        padding: '7px 9px', borderRadius: '8px',
                        background: isLight ? 'rgba(0, 210, 255, 0.05)' : 'rgba(0, 0, 0, 0.25)',
                        border: isLight ? '1px solid rgba(0, 210, 255, 0.2)' : '1px solid rgba(0, 242, 254, 0.12)'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#0284c7' : '#00f2fe', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <HardDrive size={10} /> VRAM
                          </span>
                          <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                            {formatMbToGb(vramUsed)} / {formatMbToGb(vramTotal)} ({vramPct}%)
                          </span>
                        </div>
                        <div style={{ height: '5px', borderRadius: '3px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', width: `${vramPct}%`,
                            background: vramPct > 90 ? 'linear-gradient(90deg, #ef4444, #dc2626)' : 'linear-gradient(90deg, #00f2fe, #38bdf8)',
                            borderRadius: '3px',
                            boxShadow: vramPct > 90 ? '0 0 8px #ef4444' : '0 0 8px #00f2fe',
                            transition: 'width 0.3s ease'
                          }} />
                        </div>
                      </div>

                      {/* Compute Gauge */}
                      <div style={{
                        padding: '7px 9px', borderRadius: '8px',
                        background: isLight ? 'rgba(124, 58, 237, 0.05)' : 'rgba(0, 0, 0, 0.25)',
                        border: isLight ? '1px solid rgba(124, 58, 237, 0.2)' : '1px solid rgba(188, 140, 255, 0.12)'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Gauge size={10} /> COMPUTE
                          </span>
                          <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
                            {utilPct}%
                          </span>
                        </div>
                        <div style={{ height: '5px', borderRadius: '3px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', width: `${utilPct}%`,
                            background: 'linear-gradient(90deg, #bc8cff, #a855f7)',
                            borderRadius: '3px',
                            boxShadow: '0 0 8px #bc8cff',
                            transition: 'width 0.3s ease'
                          }} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}

            {/* CPU & RAM HOST CARD */}
            <div style={{
              padding: '12px 14px',
              borderRadius: '12px',
              background: cardBg,
              border: cardBorder,
              boxShadow: cardShadow,
              display: 'flex',
              flexDirection: 'column',
              gap: '9px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '8px',
                    background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 900, fontSize: '0.75rem', color: '#10b981',
                    fontFamily: 'JetBrains Mono, monospace'
                  }}>
                    SYS
                  </div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '0.88rem', color: textPrimary }}>
                      {cpu.name || 'Processore Host & Memoria RAM'}
                    </div>
                    <div style={{ fontSize: '0.66rem', color: textDim, fontFamily: 'JetBrains Mono, monospace', marginTop: '1px' }}>
                      {cpu.cores_physical || 12} Core • {cpu.cores_logical || 24} Thread • {cpu.freq_mhz ? `${(cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'Base'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{
                    fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                    background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)',
                    color: '#10b981', fontFamily: 'JetBrains Mono, monospace', fontWeight: 800
                  }}>
                    RAM {ramUsedGb.toFixed(1)} / {ramTotalGb.toFixed(0)} GB
                  </span>
                  <span style={{
                    fontSize: '0.64rem', padding: '3px 8px', borderRadius: '6px',
                    background: 'rgba(188, 140, 255, 0.12)', border: '1px solid rgba(188, 140, 255, 0.3)',
                    color: '#bc8cff', fontFamily: 'JetBrains Mono, monospace', fontWeight: 800
                  }}>
                    CPU {cpuUsage}%
                  </span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{
                  padding: '7px 9px', borderRadius: '8px',
                  background: isLight ? 'rgba(188, 140, 255, 0.05)' : 'rgba(0, 0, 0, 0.25)',
                  border: isLight ? '1px solid rgba(124, 58, 237, 0.2)' : '1px solid rgba(188, 140, 255, 0.12)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Cpu size={10} /> CARICO CORE
                    </span>
                    <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#7c3aed' : '#bc8cff', fontFamily: 'JetBrains Mono, monospace' }}>
                      {cpuUsage}%
                    </span>
                  </div>
                  <div style={{ height: '5px', borderRadius: '3px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${cpuUsage}%`, background: 'linear-gradient(90deg, #bc8cff, #a855f7)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                  </div>
                </div>

                <div style={{
                  padding: '7px 9px', borderRadius: '8px',
                  background: isLight ? 'rgba(16, 185, 129, 0.05)' : 'rgba(0, 0, 0, 0.25)',
                  border: isLight ? '1px solid rgba(22, 163, 74, 0.2)' : '1px solid rgba(16, 185, 129, 0.12)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.62rem', fontWeight: 800, color: isLight ? '#16a34a' : '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <HardDrive size={10} /> RAM DI SISTEMA
                    </span>
                    <span style={{ fontSize: '0.66rem', fontWeight: 900, color: isLight ? '#16a34a' : '#10b981', fontFamily: 'JetBrains Mono, monospace' }}>
                      {ramUsedGb.toFixed(1)} / {ramTotalGb.toFixed(0)} GB ({ramPct}%)
                    </span>
                  </div>
                  <div style={{ height: '5px', borderRadius: '3px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${ramPct}%`, background: 'linear-gradient(90deg, #10b981, #059669)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                  </div>
                </div>
              </div>
            </div>

            {/* STORAGE & NVMe DISKS */}
            {storage.disks && storage.disks.length > 0 && (
              <div style={{
                padding: '12px 14px',
                borderRadius: '12px',
                background: cardBg,
                border: cardBorder,
                boxShadow: cardShadow,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Database size={13} color="#3b82f6" />
                    <span style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary }}>
                      Unità di Memoria NVMe & SSD ({storage.disks.length})
                    </span>
                  </div>
                  <span style={{ fontSize: '0.66rem', color: textDim, fontFamily: 'JetBrains Mono, monospace' }}>
                    {storage.used_gb} / {storage.total_gb} GB Totali ({storage.usage_pct}%)
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(storage.disks.length, 3)}, 1fr)`, gap: '8px' }}>
                  {storage.disks.map((d, dIdx) => (
                    <div key={dIdx} style={{
                      padding: '7px 9px', borderRadius: '8px',
                      background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255, 255, 255, 0.02)',
                      border: cardBorder
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ fontSize: '0.7rem', fontWeight: 800, color: textPrimary, fontFamily: 'JetBrains Mono, monospace' }}>
                          {d.mountpoint || d.device}
                        </span>
                        <span style={{ fontSize: '0.64rem', fontWeight: 800, color: d.usage_pct > 85 ? '#ef4444' : '#3b82f6', fontFamily: 'JetBrains Mono, monospace' }}>
                          {d.usage_pct}%
                        </span>
                      </div>
                      <div style={{ height: '4px', borderRadius: '2px', background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)', overflow: 'hidden', marginBottom: '3px' }}>
                        <div style={{ height: '100%', width: `${d.usage_pct}%`, background: d.usage_pct > 85 ? '#ef4444' : '#3b82f6', borderRadius: '2px' }} />
                      </div>
                      <div style={{ fontSize: '0.62rem', color: textDim, fontFamily: 'JetBrains Mono, monospace' }}>
                        {d.free_gb} GB liberi
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ORPHANS ALERT IN OVERVIEW */}
            {gpuProcs.orfani > 0 && (
              <div style={{
                padding: '10px 14px', borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.35)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle size={15} color="#ef4444" />
                  <span style={{ fontSize: '0.74rem', color: '#fca5a5', fontWeight: 700 }}>
                    Rilevati <strong>{gpuProcs.orfani} processi orfani</strong> che occupano memoria VRAM.
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={async () => {
                      try {
                        await fetch('/api/hardware/gpu/kill', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ all_orphans: true })
                        });
                        fetchGpuProcesses();
                        fetchHardwareStatus();
                        if (addToast) addToast('Processi orfani terminati.', 'success');
                      } catch {}
                    }}
                    style={{
                      padding: '4px 10px', borderRadius: '6px',
                      background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                      border: 'none', color: '#fff', fontSize: '0.68rem', fontWeight: 800,
                      cursor: 'pointer'
                    }}
                  >
                    Termina Orfani
                  </button>
                  <button
                    onClick={() => setActiveTab('processes')}
                    style={{
                      padding: '4px 10px', borderRadius: '6px',
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: cardBorder, color: textPrimary, fontSize: '0.68rem', fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    Ispeziona
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PROCESSES & MODULES */}
        {activeTab === 'processes' && (
          <div style={{
            borderRadius: '12px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            {/* Toolbar */}
            <div style={{
              padding: '10px 14px',
              background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(0,0,0,0.25)',
              borderBottom: cardBorder,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              flexWrap: 'wrap'
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                background: isLight ? '#ffffff' : 'rgba(255,255,255,0.05)',
                border: cardBorder, borderRadius: '8px',
                padding: '5px 10px', flex: 1, minWidth: '180px', maxWidth: '320px'
              }}>
                <Search size={13} color={textDim} />
                <input
                  type="text"
                  placeholder="Cerca per PID, nome o modulo..."
                  value={procSearch}
                  onChange={(e) => setProcSearch(e.target.value)}
                  style={{
                    background: 'transparent', border: 'none', outline: 'none',
                    fontSize: '0.72rem', color: textPrimary, width: '100%'
                  }}
                />
                {procSearch && (
                  <X size={12} color={textDim} style={{ cursor: 'pointer' }} onClick={() => setProcSearch('')} />
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {gpuProcs.orfani > 0 && (
                  <button
                    onClick={async () => {
                      try {
                        await fetch('/api/hardware/gpu/kill', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ all_orphans: true })
                        });
                        fetchGpuProcesses();
                        fetchHardwareStatus();
                        if (addToast) addToast('Processi orfani terminati.', 'success');
                      } catch {}
                    }}
                    style={{
                      padding: '5px 12px', borderRadius: '6px',
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      color: '#ef4444', fontSize: '0.7rem', fontWeight: 800,
                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
                    }}
                  >
                    <Trash2 size={12} /> Kill {gpuProcs.orfani} Orfani
                  </button>
                )}
                <button
                  onClick={() => { fetchGpuProcesses(); fetchHardwareStatus(); }}
                  style={{
                    padding: '5px 10px', borderRadius: '6px',
                    background: headerBtnBg, border: headerBtnBorder,
                    color: textPrimary, fontSize: '0.7rem', fontWeight: 700,
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px'
                  }}
                >
                  <RotateCcw size={12} /> Ricarica
                </button>
              </div>
            </div>

            {/* Table Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '70px 1fr 110px 90px 80px 70px',
              padding: '8px 14px',
              fontSize: '0.62rem',
              fontWeight: 800,
              color: textDim,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              borderBottom: cardBorder,
              background: isLight ? 'rgba(0,0,0,0.01)' : 'rgba(0,0,0,0.1)'
            }}>
              <span>PID</span>
              <span>Processo</span>
              <span>Modulo</span>
              <span style={{ textAlign: 'right' }}>VRAM</span>
              <span style={{ textAlign: 'right' }}>RAM</span>
              <span style={{ textAlign: 'center' }}>Azione</span>
            </div>

            {/* Process Rows */}
            <div style={{ flex: 1, overflowY: 'auto', minHeight: '180px', maxHeight: '320px' }}>
              {filteredProcs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 16px', color: textDim, fontSize: '0.75rem' }}>
                  {procSearch ? 'Nessun processo corrisponde al filtro di ricerca.' : 'Nessun processo attivo al momento.'}
                </div>
              ) : (
                filteredProcs.map(proc => (
                  <div
                    key={proc.pid}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '70px 1fr 110px 90px 80px 70px',
                      padding: '8px 14px',
                      alignItems: 'center',
                      borderBottom: isLight ? '1px solid rgba(0,0,0,0.04)' : '1px solid rgba(255,255,255,0.04)',
                      fontSize: '0.72rem',
                      transition: 'background 0.15s ease'
                    }}
                  >
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: textDim, fontWeight: 700 }}>
                      #{proc.pid}
                    </span>
                    <div style={{ minWidth: 0, paddingRight: '8px' }}>
                      <div style={{ fontWeight: 800, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {proc.name}
                      </div>
                      {proc.orfano && (
                        <span style={{ fontSize: '0.58rem', color: '#ef4444', fontWeight: 800 }}>⚠️ ORFANO</span>
                      )}
                    </div>
                    <span style={{
                      fontSize: '0.62rem', padding: '2px 6px', borderRadius: '4px',
                      background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)',
                      color: textDim, fontWeight: 700,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: 'fit-content'
                    }}>
                      {proc.module_name || 'Kernel'}
                    </span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#00f2fe', fontWeight: 800, textAlign: 'right' }}>
                      {proc.vram_mb ? `${proc.vram_mb} MB` : '0 MB'}
                    </span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: textDim, textAlign: 'right' }}>
                      {proc.memory_mb ? `${proc.memory_mb} MB` : '0 MB'}
                    </span>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      {proc.killable ? (
                        <button
                          onClick={() => handleKillGpuProcess(proc)}
                          disabled={killingPid === proc.pid}
                          style={{
                            background: 'rgba(239, 68, 68, 0.12)',
                            border: '1px solid rgba(239, 68, 68, 0.35)',
                            color: '#ef4444',
                            borderRadius: '4px',
                            padding: '2px 8px',
                            fontSize: '0.64rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '3px'
                          }}
                        >
                          <Trash2 size={10} /> {killingPid === proc.pid ? '...' : 'Kill'}
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.62rem', color: '#00f2fe', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: 'rgba(0,242,254,0.1)' }}>
                          Protetto
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 3: REALTIME TELEMETRY CHARTS */}
        {activeTab === 'charts' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* System charts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div style={{ padding: '12px 14px', borderRadius: '12px', background: cardBg, border: cardBorder }}>
                <RealtimeTelemetryChart 
                  data={systemHistory.cpu} 
                  label="Carico CPU Host (%)" 
                  icon={Cpu}
                  color={isLight ? '#7c3aed' : '#bc8cff'} 
                  unit="%" 
                  maxVal={100} 
                  height={85}
                  isLight={isLight}
                />
              </div>
              <div style={{ padding: '12px 14px', borderRadius: '12px', background: cardBg, border: cardBorder }}>
                <RealtimeTelemetryChart 
                  data={systemHistory.ram} 
                  label="RAM Allocata (GB)" 
                  icon={HardDrive}
                  color={isLight ? '#16a34a' : '#10b981'} 
                  unit="GB" 
                  maxVal={ramTotalGb || 94} 
                  height={85}
                  isLight={isLight}
                  formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
                />
              </div>
            </div>

            {/* GPU Telemetry charts */}
            {gpus.map(gpu => {
              const idx = gpu.index;
              const hist = historyData[idx] || { vram: [], compute: [], temp: [], power: [] };
              const vramTotal = Number(gpu.vram_total_mb) || 16384;

              return (
                <div key={idx} style={{ padding: '12px 14px', borderRadius: '12px', background: cardBg, border: cardBorder, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary }}>
                    GPU {idx}: {gpu.name}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Compute GPU (%)" 
                      icon={Gauge}
                      color={isLight ? '#7c3aed' : '#bc8cff'} 
                      unit="%" 
                      maxVal={100} 
                      height={80}
                      isLight={isLight}
                    />
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="VRAM Allocata (MB)" 
                      icon={Zap}
                      color={isLight ? '#0284c7' : '#00f2fe'} 
                      unit="MB" 
                      maxVal={vramTotal} 
                      height={80}
                      isLight={isLight}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


