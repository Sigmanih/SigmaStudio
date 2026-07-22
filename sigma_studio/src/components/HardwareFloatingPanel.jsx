import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Zap, Activity, ShieldCheck, Play, Pause, X, GripVertical, Maximize2,
  HardDrive, Cpu, Thermometer, Flame, Gauge, Sliders, BarChart2, ChevronDown, ChevronUp
} from 'lucide-react';
import RealtimeTelemetryChart from './HardwareLab/RealtimeTelemetryChart';
import '../styles/hardware-lab.css';
import '../styles/chat.css';

const MIN_WIDTH = 480;
const MIN_HEIGHT = 380;
const MAX_HISTORY = 900;

export default function HardwareFloatingPanel({ onClose, onOpenTab, addToast }) {
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

  useEffect(() => {
    fetchHardwareStatus();
    if (!autoRefresh) return;
    const interval = setInterval(fetchHardwareStatus, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchHardwareStatus, autoRefresh, refreshInterval]);

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
  const history = historyData;

  const safeX = (panelPos.x !== undefined && !isNaN(panelPos.x)) ? panelPos.x : undefined;
  const safeY = (panelPos.y !== undefined && !isNaN(panelPos.y)) ? panelPos.y : undefined;

  const resizeHandles = [
    { dir: 'n' }, { dir: 's' }, { dir: 'e' }, { dir: 'w' },
    { dir: 'ne' }, { dir: 'nw' }, { dir: 'se' }, { dir: 'sw' }
  ];

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
        background: 'rgba(10, 14, 23, 0.96)',
        border: '1px solid rgba(0, 242, 254, 0.3)',
        borderRadius: '16px',
        boxShadow: '0 32px 64px -16px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 242, 254, 0.15)',
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        animation: 'slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
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
          padding: '10px 14px',
          background: 'rgba(15, 23, 42, 0.75)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none'
        }}
      >
        <div className="task-floating-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GripVertical size={16} color="var(--text-dim)" />
          <Zap size={16} color="#00f2fe" />
          <span style={{ fontWeight: 700, fontSize: '13px', background: 'linear-gradient(135deg, #00f2fe, #bc8cff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Hardware & GPU Monitor
          </span>
          <span className="hw-badge hw-badge-live" style={{ fontSize: '10px', padding: '2px 8px', marginLeft: '4px' }}>
            <span className="hw-badge-dot" />
            {gpus.length} GPU Live
          </span>
        </div>

        <div className="task-floating-actions" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button 
            onClick={() => setShowCharts(!showCharts)} 
            className="chat-header-btn" 
            title={showCharts ? 'Nascondi i grafici per compattare' : 'Mostra grafici storici'}
            style={{ background: showCharts ? 'rgba(0, 242, 254, 0.2)' : 'rgba(255,255,255,0.05)', border: '1px solid rgba(0, 242, 254, 0.3)', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', color: '#fff', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <BarChart2 size={12} color="#00f2fe" />
            {showCharts ? 'Grafici ON' : 'Grafici OFF'}
          </button>
          <button 
            onClick={() => setAutoRefresh(!autoRefresh)} 
            className="chat-header-btn" 
            title={autoRefresh ? 'Pausa refresh' : 'Riprendi refresh'}
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', color: '#fff' }}
          >
            {autoRefresh ? <Pause size={12} color="#00f2fe" /> : <Play size={12} />}
          </button>
          {onOpenTab && (
            <button 
              onClick={onOpenTab} 
              className="chat-header-btn" 
              title="Espandi in Tab Workspace"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', color: '#fff' }}
            >
              <Maximize2 size={12} color="#00f2fe" />
            </button>
          )}
          <button 
            onClick={onClose} 
            className="chat-header-btn" 
            title="Chiudi pannello"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '4px 8px', cursor: 'pointer', color: '#fff' }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Floating Panel Body */}
      <div className="task-floating-body" style={{ padding: '12px 14px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
        
        {/* ==================================================================== */}
        {/* SYSTEM CPU & RAM CARD (LEFT = COMPUTE, RIGHT = MEMORY) */}
        {/* ==================================================================== */}
        <div className="gpu-card" style={{ padding: '12px 14px', borderRadius: '12px', background: 'rgba(15, 23, 42, 0.7)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="gpu-index-pill" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', height: '22px', minWidth: '22px', fontSize: '10px' }}>SYS</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: '13px', color: '#fff' }}>Sistema (CPU & RAM)</div>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                  {hw.cpu?.logical_count || hw.cpu_count || '?'} Threads • {hw.cpu?.freq_mhz ? `${(hw.cpu.freq_mhz / 1000).toFixed(1)} GHz` : 'N/A'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 6px', color: '#00f2fe', borderColor: 'rgba(0,242,254,0.3)' }}>
                CPU: {hw.cpu?.util_pct ?? 0}%
              </span>
              <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 6px', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                RAM: {hw.ram?.used_gb || 0}/{hw.ram?.total_gb || 0} GB
              </span>
            </div>
          </div>

          {/* 2-COLUMN SPLIT: LEFT = CPU COMPUTE, RIGHT = RAM MEMORY */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            
            {/* LEFT: CPU COMPUTE */}
            <div style={{ background: 'rgba(0, 242, 254, 0.04)', border: '1px solid rgba(0, 242, 254, 0.15)', borderRadius: '8px', padding: '8px 10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', fontSize: '11px' }}>
                <span style={{ fontWeight: 700, color: '#00f2fe', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Cpu size={12} /> ⚡ COMPUTE
                </span>
                <span style={{ fontWeight: 800, color: '#00f2fe' }}>{hw.cpu?.util_pct ?? 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '6px' }}>
                <div className="metric-progress-bar bar-cyan" style={{ width: `${Math.min(100, hw.cpu?.util_pct ?? 0)}%` }} />
              </div>
            </div>

            {/* RIGHT: RAM MEMORY */}
            <div style={{ background: 'rgba(16, 185, 129, 0.04)', border: '1px solid rgba(16, 185, 129, 0.15)', borderRadius: '8px', padding: '8px 10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', fontSize: '11px' }}>
                <span style={{ fontWeight: 700, color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <HardDrive size={12} /> 🧠 MEMORIA
                </span>
                <span style={{ fontWeight: 800, color: '#10b981' }}>{hw.ram?.util_pct || 0}%</span>
              </div>
              <div className="metric-progress-track" style={{ height: '6px' }}>
                <div className="metric-progress-bar" style={{ width: `${Math.min(100, hw.ram?.util_pct || 0)}%`, background: 'linear-gradient(90deg, #10b981, #059669)' }} />
              </div>
            </div>

          </div>

          {/* COLLAPSIBLE SYSTEM CHARTS */}
          {showCharts && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
              <RealtimeTelemetryChart 
                data={systemHistory.cpu} 
                label="Carico CPU (%)" 
                icon={Cpu}
                color="#00f2fe" 
                unit="%" 
                maxVal={100} 
                height={70}
              />
              <RealtimeTelemetryChart 
                data={systemHistory.ram} 
                label="RAM (GB)" 
                icon={HardDrive}
                color="#10b981" 
                unit="GB" 
                maxVal={hw.ram?.total_gb || 64} 
                height={70}
                formatVal={(val) => `${typeof val === 'number' ? val.toFixed(1) : val}`}
              />
            </div>
          )}
        </div>

        {/* ==================================================================== */}
        {/* MULTI-VENDOR GPU CARDS (LEFT = COMPUTE, RIGHT = VRAM) */}
        {/* ==================================================================== */}
        {gpus.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 16px', color: '#94a3b8' }}>
            {loading ? (
              <>
                <Activity className="spin" size={28} color="#00f2fe" style={{ margin: '0 auto 10px' }} />
                <div style={{ fontSize: '13px' }}>Rilevamento telemetria hardware in corso...</div>
              </>
            ) : (
              <div style={{ fontSize: '13px' }}>⚠️ Nessuna GPU rilevata nel sistema.</div>
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
              <div key={idx} className="gpu-card" style={{ padding: '12px 14px', borderRadius: '12px', background: 'rgba(15, 23, 42, 0.7)' }}>
                {/* GPU Info Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="gpu-index-pill" style={{ height: '22px', minWidth: '22px', fontSize: '10px' }}>GPU {idx}</span>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ fontWeight: 700, fontSize: '13px', color: '#fff' }}>{gpu.name}</div>
                        <span className="hw-badge" style={{ 
                          background: `${gpu.vendor_color || '#00f2fe'}18`, 
                          color: gpu.vendor_color || '#00f2fe',
                          borderColor: `${gpu.vendor_color || '#00f2fe'}44`,
                          fontSize: '9px',
                          padding: '1px 5px'
                        }}>
                          {gpu.vendor || 'GPU'}
                        </span>
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                        Driver {gpu.driver_version || 'N/A'} • {gpu.temp_c ? `${gpu.temp_c}°C` : 'N/A'} • {pwrDraw}W
                      </div>
                    </div>
                  </div>
                  <span className="hw-badge" style={{ fontSize: '10px', padding: '2px 6px', color: utilPct > 80 ? '#ef4444' : '#00f2fe' }}>
                    {utilPct}% Utilizzo
                  </span>
                </div>

                {/* 2-COLUMN SPLIT: LEFT = GPU COMPUTE, RIGHT = GPU VRAM */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  
                  {/* LEFT: GPU COMPUTE */}
                  <div style={{ background: 'rgba(188, 140, 255, 0.04)', border: '1px solid rgba(188, 140, 255, 0.18)', borderRadius: '8px', padding: '8px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', fontSize: '11px' }}>
                      <span style={{ fontWeight: 700, color: '#bc8cff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Gauge size={12} /> ⚡ COMPUTE
                      </span>
                      <span style={{ fontWeight: 800, color: '#bc8cff' }}>{utilPct}%</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '6px' }}>
                      <div className="metric-progress-bar bar-purple" style={{ width: `${utilPct}%` }} />
                    </div>
                  </div>

                  {/* RIGHT: GPU VRAM */}
                  <div style={{ background: 'rgba(0, 210, 255, 0.04)', border: '1px solid rgba(0, 210, 255, 0.18)', borderRadius: '8px', padding: '8px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', fontSize: '11px' }}>
                      <span style={{ fontWeight: 700, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <HardDrive size={12} /> 🧠 VRAM
                      </span>
                      <span style={{ fontWeight: 800, color: '#00d2ff' }}>{vramUsed} / {vramTotal} MB</span>
                    </div>
                    <div className="metric-progress-track" style={{ height: '6px' }}>
                      <div className="metric-progress-bar bar-cyan" style={{ width: `${vramPct}%` }} />
                    </div>
                  </div>

                </div>

                {/* COLLAPSIBLE GPU CHARTS */}
                {showCharts && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                    <RealtimeTelemetryChart 
                      data={hist.compute} 
                      label="Compute GPU nel tempo" 
                      icon={Cpu}
                      color="#bc8cff" 
                      unit="%" 
                      maxVal={100} 
                      height={75}
                    />
                    <RealtimeTelemetryChart 
                      data={hist.vram} 
                      label="VRAM nel tempo" 
                      icon={HardDrive}
                      color="#00d2ff" 
                      unit="MB" 
                      maxVal={vramTotal} 
                      height={75}
                    />
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
