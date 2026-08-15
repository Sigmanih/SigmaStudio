import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Zap, Activity, ShieldCheck, Play, Pause, X, GripVertical, Maximize2, RotateCcw,
  HardDrive, Cpu, Thermometer, Flame, Gauge, Sliders, BarChart2, AlertTriangle
} from 'lucide-react';
import RealtimeTelemetryChart from './RealtimeTelemetryChart';
import { useApp } from '../../contexts/AppContext';
import './styles/hardware-lab.css';
import '../../styles/chat.css';


const MIN_WIDTH = 480;
const MIN_HEIGHT = 380;
const MAX_HISTORY = 900;

export default function HardwareFloatingPanel({ onClose, onOpenTab, addToast }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  const [panelPos, setPanelPos] = useState({ x: undefined, y: undefined });
  const [panelSize, setPanelSize] = useState({ width: 660, height: 520 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [resizing, setResizing] = useState(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0 });
  const resizeSizeStart = useRef({ width: 660, height: 520 });
  const resizePosStart = useRef({ x: 0, y: 0 });
  const panelRef = useRef(null);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(2000);
  const [showCharts, setShowCharts] = useState(false); // Collapsible charts state
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
          const cpuUtil = Number(json.hardware?.cpu?.util_pct) || 0;
          const ramUsed = Number(json.hardware?.ram?.used_gb) || Number(json.hardware?.ram_used_gb) || 0;

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

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x)) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y)) ? panelPos.y : undefined;

  const resizeHandles = [
    { dir: 'n' }, { dir: 's' }, { dir: 'e' }, { dir: 'w' },
    { dir: 'ne' }, { dir: 'nw' }, { dir: 'se' }, { dir: 'sw' }
  ];

  // Theme Design Tokens
  const panelBg = isLight ? '#fffdf9' : 'rgba(10, 14, 23, 0.96)';
  const panelBorder = isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 242, 254, 0.3)';
  const panelShadow = isLight 
    ? '0 24px 60px rgba(0, 0, 0, 0.22), 0 0 20px rgba(234, 88, 12, 0.08)' 
    : '0 32px 64px -16px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 242, 254, 0.15)';
  const headerBg = isLight ? '#f4efe4' : 'rgba(15, 23, 42, 0.75)';
  const headerBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardBg = isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.7)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111111' : '#ffffff';
  const textSecondary = isLight ? '#374151' : '#cbd5e1';
  const textDim = isLight ? '#6b7280' : 'var(--text-dim, #94a3b8)';
  const accentColor = isLight ? '#ea580c' : '#00f2fe';
  const headerBtnBg = isLight ? '#fffdf9' : 'rgba(255,255,255,0.05)';
  const headerBtnBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.1)';

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
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* CONFIRMATION ALERT MODAL */}
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
                <div style={{ fontSize: '11px', color: textDim }}>Svuota modelli in memoria</div>
              </div>
            </div>

            <div style={{ fontSize: '12px', color: textSecondary, lineHeight: '1.5', marginBottom: '16px', background: isLight ? '#f4efe4' : 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid #ef4444' }}>
              ⚠️ Scaricherà tutti i modelli da VRAM/RAM e riavvierà Ollama. Continuare?
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

      {/* Header — Drag Handle */}
      <div 
        className="task-floating-header" 
        onMouseDown={handleMouseDownHeader}
        style={{ 
          cursor: isDragging ? 'grabbing' : 'grab',
          padding: '12px 16px',
          background: headerBg,
          borderBottom: headerBorder,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none'
        }}
      >
        <div className="task-floating-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GripVertical size={16} color={textDim} />
          <Zap size={16} color={accentColor} />
          <span style={{ fontWeight: 800, fontSize: '13px', color: accentColor }}>
            Hardware & GPU Monitor
          </span>
          <span className="hw-badge hw-badge-live" style={{ fontSize: '10px', padding: '2px 8px', marginLeft: '4px' }}>
            <span className="hw-badge-dot" />
            {gpus.length} GPU Live
          </span>
        </div>

        <div className="task-floating-actions" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button 
            onClick={() => setShowRestartAlert(true)} 
            className="chat-header-btn" 
            title="Svuota la memoria VRAM/RAM scaricando tutti i modelli da Ollama"
            style={{ 
              background: isLight ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.15)', 
              border: '1px solid rgba(239, 68, 68, 0.35)', 
              borderRadius: '8px', 
              padding: '5px 10px', 
              cursor: 'pointer', 
              color: isLight ? '#dc2626' : '#fca5a5', 
              fontSize: '11px', 
              fontWeight: 700,
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <RotateCcw size={12} color="#ef4444" />
            <span>Svuota VRAM</span>
          </button>

          <button 
            onClick={() => setShowCharts(!showCharts)} 
            className="chat-header-btn" 
            title={showCharts ? 'Nascondi i grafici per compattare' : 'Mostra grafici storici'}
            style={{ 
              background: showCharts 
                ? (isLight ? '#ea580c' : 'rgba(0, 242, 254, 0.2)') 
                : headerBtnBg, 
              border: showCharts 
                ? (isLight ? '1px solid #ea580c' : '1px solid rgba(0, 242, 254, 0.4)') 
                : headerBtnBorder, 
              borderRadius: '8px', 
              padding: '5px 10px', 
              cursor: 'pointer', 
              color: showCharts ? '#fff' : textPrimary, 
              fontSize: '11px', 
              fontWeight: 700,
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px' 
            }}
          >
            <BarChart2 size={12} color={showCharts ? '#fff' : accentColor} />
            {showCharts ? 'Grafici ON' : 'Grafici OFF'}
          </button>

          <button 
            onClick={() => setAutoRefresh(!autoRefresh)} 
            className="chat-header-btn" 
            title={autoRefresh ? 'Pausa refresh' : 'Riprendi refresh'}
            style={{ 
              background: headerBtnBg, 
              border: headerBtnBorder, 
              borderRadius: '8px', 
              padding: '5px 8px', 
              cursor: 'pointer', 
              color: textPrimary 
            }}
          >
            {autoRefresh ? <Pause size={12} color={accentColor} /> : <Play size={12} />}
          </button>

          {onOpenTab && (
            <button 
              onClick={onOpenTab} 
              className="chat-header-btn" 
              title="Espandi in Tab Workspace"
              style={{ 
                background: headerBtnBg, 
                border: headerBtnBorder, 
                borderRadius: '8px', 
                padding: '5px 8px', 
                cursor: 'pointer', 
                color: textPrimary 
              }}
            >
              <Maximize2 size={12} color={accentColor} />
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
      <div className="task-floating-body" style={{ padding: '14px 16px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* SYSTEM CPU & RAM CARD */}
        <div className="gpu-card" style={{ padding: '14px 16px', borderRadius: '14px', background: cardBg, border: cardBorder }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="gpu-index-pill" style={{ 
                background: isLight ? 'rgba(22, 163, 74, 0.12)' : 'rgba(16, 185, 129, 0.15)', 
                color: isLight ? '#16a34a' : '#10b981', 
                border: isLight ? '1px solid rgba(22, 163, 74, 0.35)' : '1px solid rgba(16, 185, 129, 0.3)', 
                height: '24px', 
                minWidth: '28px', 
                fontSize: '11px',
                fontWeight: 800
              }}>SYS</span>
              <div>
                <div style={{ fontWeight: 800, fontSize: '13px', color: textPrimary }}>Sistema (CPU & RAM)</div>
                <div style={{ fontSize: '10px', color: textDim, fontFamily: 'monospace' }}>
                  {hw.cpu?.logical_count || hw.cpu_count || '?'} Threads • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span className="hw-badge" style={{ 
                fontSize: '10px', 
                padding: '3px 8px', 
                background: isLight ? 'rgba(2, 132, 199, 0.1)' : undefined,
                color: isLight ? '#0284c7' : '#00f2fe', 
                borderColor: isLight ? 'rgba(2, 132, 199, 0.3)' : 'rgba(0,242,254,0.3)',
                fontWeight: 700
              }}>
                CPU: {hw.cpu?.util_pct ?? 0}%
              </span>
              <span className="hw-badge" style={{ 
                fontSize: '10px', 
                padding: '3px 8px', 
                background: isLight ? 'rgba(22, 163, 74, 0.1)' : undefined,
                color: isLight ? '#16a34a' : '#10b981', 
                borderColor: isLight ? 'rgba(22, 163, 74, 0.3)' : 'rgba(16, 185, 129, 0.3)',
                fontWeight: 700
              }}>
                RAM: {hw.ram?.used_gb || 0}/{hw.ram?.total_gb || 0} GB
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div style={{ 
              background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 242, 254, 0.04)', 
              border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 242, 254, 0.15)', 
              borderRadius: '10px', 
              padding: '10px 12px' 
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '11px' }}>
                <span style={{ fontWeight: 800, color: isLight ? '#0284c7' : '#00f2fe', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Cpu size={13} /> ⚡ COMPUTE
                </span>
                <span style={{ fontWeight: 800, color: isLight ? '#0284c7' : '#00f2fe' }}>{hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '7px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                <div className="metric-progress-bar bar-cyan" style={{ width: `${Math.min(100, hw.cpu?.util_pct ?? 0)}%` }} />
              </div>
            </div>

            <div style={{ 
              background: isLight ? 'rgba(22, 163, 74, 0.06)' : 'rgba(16, 185, 129, 0.04)', 
              border: isLight ? '1px solid rgba(22, 163, 74, 0.25)' : '1px solid rgba(16, 185, 129, 0.15)', 
              borderRadius: '10px', 
              padding: '10px 12px' 
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '11px' }}>
                <span style={{ fontWeight: 800, color: isLight ? '#16a34a' : '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <HardDrive size={13} /> 🧠 MEMORIA
                </span>
                <span style={{ fontWeight: 800, color: isLight ? '#16a34a' : '#10b981' }}>{hw.ram?.util_pct || 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '7px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                <div className="metric-progress-bar" style={{ width: `${Math.min(100, hw.ram?.util_pct || 0)}%`, background: 'linear-gradient(90deg, #10b981, #059669)' }} />
              </div>
            </div>
          </div>

          {showCharts && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '12px', paddingTop: '12px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)' }}>
              <RealtimeTelemetryChart 
                data={systemHistory.cpu} 
                label="Carico CPU (%)" 
                icon={Cpu}
                color={isLight ? '#0284c7' : '#00f2fe'} 
                unit="%" 
                maxVal={100} 
                height={70}
                isLight={isLight}
              />
              <RealtimeTelemetryChart 
                data={systemHistory.ram} 
                label="RAM (GB)" 
                icon={HardDrive}
                color={isLight ? '#16a34a' : '#10b981'} 
                unit="GB" 
                maxVal={hw.ram?.total_gb || 64} 
                height={70}
                isLight={isLight}
                formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
              />
            </div>
          )}
        </div>

        {/* MULTI-VENDOR GPU CARDS */}
        {gpus.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 16px', color: textDim }}>
            {loading ? (
              <>
                <Activity className="spin" size={28} color={accentColor} style={{ margin: '0 auto 10px' }} />
                <div style={{ fontSize: '13px', color: textPrimary }}>Rilevamento telemetria hardware in corso...</div>
              </>
            ) : (
              <div style={{ fontSize: '13px', color: textSecondary }}>⚠️ Nessuna GPU rilevata nel sistema.</div>
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
              <div key={idx} className="gpu-card" style={{ padding: '14px 16px', borderRadius: '14px', background: cardBg, border: cardBorder }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="gpu-index-pill" style={{ 
                      height: '24px', 
                      minWidth: '38px', 
                      fontSize: '11px',
                      background: isLight ? 'rgba(234, 88, 12, 0.12)' : undefined,
                      color: isLight ? '#ea580c' : undefined,
                      borderColor: isLight ? 'rgba(234, 88, 12, 0.35)' : undefined
                    }}>GPU {idx}</span>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ fontWeight: 800, fontSize: '13px', color: textPrimary }}>{gpu.name}</div>
                        <span className="hw-badge" style={{ 
                          background: isLight ? 'rgba(2, 132, 199, 0.12)' : `${gpu.vendor_color || '#00f2fe'}18`, 
                          color: isLight ? '#0284c7' : (gpu.vendor_color || '#00f2fe'),
                          borderColor: isLight ? 'rgba(2, 132, 199, 0.3)' : `${gpu.vendor_color || '#00f2fe'}44`,
                          fontSize: '9px',
                          padding: '2px 6px',
                          fontWeight: 700
                        }}>
                          {gpu.vendor || 'GPU'}
                        </span>
                      </div>
                      <div style={{ fontSize: '10px', color: textDim, fontFamily: 'monospace' }}>
                        Driver {gpu.driver_version || 'N/A'} • {gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'} • {pwrDraw}W
                      </div>
                    </div>
                  </div>
                  <span className="hw-badge" style={{ 
                    fontSize: '10px', 
                    padding: '3px 8px', 
                    background: utilPct > 80 ? 'rgba(239, 68, 68, 0.15)' : (isLight ? 'rgba(2, 132, 199, 0.1)' : undefined),
                    color: utilPct > 80 ? '#dc2626' : (isLight ? '#0284c7' : '#00f2fe'),
                    borderColor: utilPct > 80 ? 'rgba(239, 68, 68, 0.4)' : (isLight ? 'rgba(2, 132, 199, 0.3)' : undefined),
                    fontWeight: 700
                  }}>
                    {utilPct}% Utilizzo
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div style={{ 
                    background: isLight ? 'rgba(124, 58, 237, 0.06)' : 'rgba(188, 140, 255, 0.04)', 
                    border: isLight ? '1px solid rgba(124, 58, 237, 0.25)' : '1px solid rgba(188, 140, 255, 0.18)', 
                    borderRadius: '10px', 
                    padding: '10px 12px' 
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '11px' }}>
                      <span style={{ fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Gauge size={13} /> ⚡ COMPUTE
                      </span>
                      <span style={{ fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff' }}>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '7px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                      <div className="metric-progress-bar bar-purple" style={{ width: `${utilPct}%` }} />
                    </div>
                  </div>

                  <div style={{ 
                    background: isLight ? 'rgba(2, 132, 199, 0.06)' : 'rgba(0, 210, 255, 0.04)', 
                    border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 210, 255, 0.18)', 
                    borderRadius: '10px', 
                    padding: '10px 12px' 
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '11px' }}>
                      <span style={{ fontWeight: 800, color: isLight ? '#0284c7' : '#00d2ff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <HardDrive size={13} /> 🧠 VRAM
                      </span>
                      <span style={{ fontWeight: 800, color: isLight ? '#0284c7' : '#00d2ff' }}>{vramUsed} / {vramTotal} MB</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '7px', background: isLight ? 'rgba(0,0,0,0.06)' : undefined }}>
                      <div className="metric-progress-bar bar-cyan" style={{ width: `${vramPct}%` }} />
                    </div>
                  </div>
                </div>

                {showCharts && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '12px', paddingTop: '12px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)' }}>
                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Compute GPU nel tempo" 
                      icon={Cpu}
                      color={isLight ? '#7c3aed' : '#bc8cff'} 
                      unit="%" 
                      maxVal={100} 
                      height={75}
                      isLight={isLight}
                    />
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="VRAM nel tempo" 
                      icon={HardDrive}
                      color={isLight ? '#0284c7' : '#00d2ff'} 
                      unit="MB" 
                      maxVal={vramTotal} 
                      height={75}
                      isLight={isLight}
                    />
                  </div>
                )}
              </div>
            );
          })
        )}

        {/* PROCESSES LIST IN FLOATING PANEL */}

        {gpuProcs.processes.length > 0 && (
          <div style={{
            marginTop: '6px',
            borderRadius: '12px',
            background: cardBg,
            border: cardBorder,
            overflow: 'hidden'
          }}>
            <div style={{
              padding: '8px 12px',
              background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(0,0,0,0.3)',
              borderBottom: cardBorder,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <span style={{ fontSize: '11px', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Zap size={12} color={accentColor} /> Processi & Memoria Attivi ({gpuProcs.processes.length})
              </span>
            </div>

            <div style={{ maxHeight: '180px', overflowY: 'auto' }}>
              {gpuProcs.processes.slice(0, 10).map(proc => (
                <div key={proc.pid} style={{
                  padding: '6px 12px',
                  borderBottom: isLight ? '1px solid rgba(0,0,0,0.04)' : '1px solid rgba(255,255,255,0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  fontSize: '11px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: textDim }}>#{proc.pid}</span>
                    <span style={{ fontWeight: 700, color: textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {proc.name}
                    </span>
                    <span style={{ fontSize: '9px', color: textDim }}>({proc.user || 'Sigma'})</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <span style={{ fontFamily: 'monospace', color: accentColor, fontWeight: 700 }}>
                      {proc.vram_mb || 0} MB VRAM
                    </span>
                    <span style={{ fontFamily: 'monospace', color: textDim, fontSize: '10px' }}>
                      {proc.memory_mb || 0}M RAM
                    </span>
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
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


