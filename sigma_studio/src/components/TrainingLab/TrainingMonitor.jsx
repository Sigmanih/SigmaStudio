import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Play, Square, Trash2, RefreshCw, Download, Copy, ScrollText, Cpu, Package, BarChart2 } from 'lucide-react';
import TrainingMetrics from './TrainingMetrics';

// ==============================================================================
// TrainingMonitor — Live log stream, loss chart, hardware info, export panel
// ==============================================================================

const STATUS_LABELS = {
  ready: { label: 'Pronto', color: 'var(--text-dim)' },
  running: { label: 'In esecuzione', color: 'var(--primary)' },
  completed: { label: 'Completato', color: 'var(--success)' },
  failed: { label: 'Fallito', color: 'var(--error)' },
  stopped: { label: 'Fermato', color: 'var(--warning)' },
};

// Parse loss from log line patterns
function parseLoss(line) {
  const patterns = [
    /loss[:\s=]+([0-9.]+)/i,
    /'loss':\s*([0-9.]+)/,
    /train_loss[:\s=]+([0-9.]+)/i,
    /\[SIGMA\].*loss:\s*([0-9.]+)/i,
  ];
  for (const p of patterns) {
    const m = line.match(p);
    if (m) return parseFloat(m[1]);
  }
  return null;
}

// Parse epoch / step from log line
function parseProgress(line) {
  const epMatch = line.match(/[Ee]poch\s+(\d+)\s*\/\s*(\d+)/);
  const stepMatch = line.match(/[Ss]tep\s+(\d+)\s*\/\s*(\d+)/);
  return {
    epoch: epMatch ? { current: parseInt(epMatch[1]), total: parseInt(epMatch[2]) } : null,
    step: stepMatch ? { current: parseInt(stepMatch[1]), total: parseInt(stepMatch[2]) } : null,
  };
}

// SVG loss chart
function LossChart({ dataPoints }) {
  if (!dataPoints || dataPoints.length < 2) {
    return (
      <div className="training-chart-empty">
        📈 Il grafico della loss apparirà qui durante il training
      </div>
    );
  }
  const W = 500, H = 110;
  const padL = 35, padR = 10, padT = 10, padB = 25;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const minL = Math.min(...dataPoints.map(d => d.loss));
  const maxL = Math.max(...dataPoints.map(d => d.loss));
  const range = maxL - minL || 1;

  const xs = dataPoints.map((_, i) => padL + (i / (dataPoints.length - 1)) * chartW);
  const ys = dataPoints.map(d => padT + chartH - ((d.loss - minL) / range) * chartH);

  const pathD = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const areaD = `${pathD} L${xs[xs.length-1].toFixed(1)},${(padT + chartH).toFixed(1)} L${padL},${(padT + chartH).toFixed(1)} Z`;

  // Y-axis ticks
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({
    y: padT + chartH - t * chartH,
    val: (minL + t * range).toFixed(3),
  }));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="training-chart-svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="lossGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00d2ff" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#00d2ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={t.y} x2={W - padR} y2={t.y} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
          <text x={padL - 4} y={t.y + 4} fill="rgba(148,148,165,0.7)" fontSize="8" textAnchor="end">{t.val}</text>
        </g>
      ))}
      {/* Area fill */}
      <path d={areaD} fill="url(#lossGrad)" />
      {/* Loss line */}
      <path d={pathD} fill="none" stroke="#00d2ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {/* Last point dot */}
      <circle
        cx={xs[xs.length - 1]}
        cy={ys[ys.length - 1]}
        r="3"
        fill="#00d2ff"
        style={{ filter: 'drop-shadow(0 0 4px #00d2ff)' }}
      />
      {/* X label */}
      <text x={W / 2} y={H - 4} fill="rgba(148,148,165,0.5)" fontSize="8" textAnchor="middle">Steps</text>
    </svg>
  );
}

export default function TrainingMonitor({ onAddToast, embedded = false, jobId = null }) {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logOffset, setLogOffset] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [lossPoints, setLossPoints] = useState([]);
  const [hardware, setHardware] = useState(null);
  const [exportModal, setExportModal] = useState(false);
  const [exportName, setExportName] = useState('');
  const [exportSystemPrompt, setExportSystemPrompt] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);
  const [exportQuant, setExportQuant] = useState('');
  const [quantLevels, setQuantLevels] = useState([]);
  const [metrics, setMetrics] = useState(null);
  // 'output' = il log grezzo, 'riepilogo' = ciò che serve per capire
  // com'è andata, in una forma incollabile.
  const [consoleTab, setConsoleTab] = useState('output');
  const [continueModal, setContinueModal] = useState(false);
  const [continueMode, setContinueMode] = useState('resume_adapter');
  const [continueDataset, setContinueDataset] = useState('');
  const [continueModes, setContinueModes] = useState([]);
  const [continuing, setContinuing] = useState(false);
  const [continueResult, setContinueResult] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const logEndRef = useRef();
  const pollRef = useRef();

  const selectedJob = jobs.find(j => j.id === selectedJobId);

  // Dentro lo Studio la fase la sceglie la catena: il monitor la segue, invece
  // di tenere una selezione propria che direbbe un'altra cosa nella stessa pagina.
  useEffect(() => {
    if (jobId && jobId !== selectedJobId) setSelectedJobId(jobId);
  }, [jobId]);

  // Load jobs list
  const loadJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/training/jobs');
      const data = await res.json();
      if (data.success) {
        setJobs(data.jobs || []);
        // Auto-select first running job or first job
        if (!selectedJobId && data.jobs?.length > 0) {
          const running = data.jobs.find(j => j.status === 'running');
          setSelectedJobId((running || data.jobs[0]).id);
        }
      }
    } catch (e) {}
  }, [selectedJobId]);

  // Livelli di quantizzazione, modi di continuazione e dataset disponibili
  useEffect(() => {
    fetch('/api/training/export/quant_levels')
      .then(r => r.json())
      .then(d => { if (d.success) setQuantLevels(d.levels || []); })
      .catch(() => {});
    fetch('/api/training/job/continuation_modes')
      .then(r => r.json())
      .then(d => { if (d.success) setContinueModes(d.modes || []); })
      .catch(() => {});
    fetch('/api/training/datasets')
      .then(r => r.json())
      .then(d => { if (d.success) setDatasets(d.datasets || []); })
      .catch(() => {});
  }, []);

  const handleContinueTraining = async () => {
    if (!selectedJobId) return;
    setContinuing(true);
    setContinueResult(null);
    try {
      const res = await fetch('/api/training/job/continue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: selectedJobId,
          mode: continueMode,
          dataset_id: continueDataset || undefined,
        }),
      });
      const data = await res.json();
      setContinueResult(data);
      if (data.success) {
        await loadJobs();
        setSelectedJobId(data.job_id);
        onAddToast && onAddToast(data.message, 'success', 6000);
      }
    } catch (e) {
      setContinueResult({ success: false, error: e.message });
    } finally {
      setContinuing(false);
    }
  };

  // Load hardware info
  const loadHardware = useCallback(async () => {
    try {
      const res = await fetch('/api/training/hardware');
      const data = await res.json();
      if (data.success) setHardware(data.hardware);
    } catch (e) {}
  }, []);

  useEffect(() => {
    loadJobs();
    loadHardware();
  }, []);

  // Poll logs for selected running job
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!selectedJobId) return;

    const fetchLogs = async () => {
      try {
        const res = await fetch(`/api/training/job/logs?job_id=${selectedJobId}&offset=0`);
        const data = await res.json();
        if (data.success && data.lines) {
          setLogs(data.lines);
          // Fallback per i run vecchi, generati prima delle righe [SIGMA-METRIC]:
          // per loro la loss si può solo ripescare dal testo del log.
          const pts = [];
          data.lines.forEach((line, i) => {
            const loss = parseLoss(line);
            if (loss !== null && loss > 0 && loss < 100) {
              pts.push({ step: i, loss });
            }
          });
          if (pts.length > 0) setLossPoints(pts);
        }
      } catch (e) {}
      try {
        const res = await fetch(`/api/training/job/metrics?job_id=${selectedJobId}`);
        const data = await res.json();
        if (data.success) setMetrics(data);
      } catch (e) {}
      // Also refresh job status
      loadJobs();
    };

    fetchLogs();

    // Poll ONLY if job is running, stop polling for completed/failed/ready/stopped
    if (['running', 'ready', 'paused'].includes(selectedJob?.status)) {
      pollRef.current = setInterval(() => {
        // Check current status before polling logs
        loadJobs().then(() => {});
        fetchLogs();
      }, 2000);
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // `selectedJob.status` deve stare fra le dipendenze: al primo giro la lista
    // dei job è ancora vuota (arriva da una fetch), quindi lo stato è
    // `undefined`, l'intervallo non parte e — non cambiando più
    // `selectedJobId` — non sarebbe mai partito. La pagina restava ferma
    // sull'ultimo dato letto mentre il training andava avanti.
  }, [selectedJobId, selectedJob?.status]);

  // Auto-scroll log terminal
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleStart = async (jobId, totalSteps = null) => {
    try {
      const res = await fetch('/api/training/job/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, ...(totalSteps ? { total_steps: totalSteps } : {}) }),
      });
      const data = await res.json();
      if (data.success) {
        onAddToast && onAddToast(
          totalSteps ? `▶ Ripreso dal checkpoint fino a ${totalSteps} step` : '🚀 Training avviato!',
          'success');
        loadJobs();
      } else {
        onAddToast && onAddToast(`Errore: ${data.error}`, 'error');
      }
    } catch (e) {}
  };

  // Un run FWE riparte dal proprio checkpoint: per proseguire basta alzare il
  // totale degli step (col totale attuale il ciclo sarebbe vuoto).
  const handleContinue = (job) => {
    const current = Number(job.hyperparams?.fwe_steps || job.total_steps || 0);
    const answer = prompt(
      `Il job è a ${current} step. Fino a quanti step vuoi continuare?\n` +
      `(riprende dal checkpoint, non ricomincia)`,
      String(current + 600));
    if (!answer) return;
    const target = parseInt(answer, 10);
    if (!Number.isFinite(target) || target <= current) {
      onAddToast && onAddToast(`Indica un totale maggiore di ${current}`, 'warning');
      return;
    }
    handleStart(job.id, target);
  };

  const handleStop = async (jobId) => {
    try {
      await fetch('/api/training/job/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId }),
      });
      loadJobs();
    } catch (e) {}
  };

  const handleDelete = async (jobId) => {
    if (!confirm('Eliminare questo job e tutti i file?')) return;
    try {
      await fetch('/api/training/job/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId }),
      });
      setJobs(prev => prev.filter(j => j.id !== jobId));
      if (selectedJobId === jobId) setSelectedJobId(jobs[0]?.id || null);
    } catch (e) {}
  };

  const handleExport = async () => {
    if (!selectedJobId || !exportName.trim()) return;
    setExporting(true);
    setExportResult(null);
    try {
      const res = await fetch('/api/training/export/ollama', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: selectedJobId,
          model_name: exportName.trim(),
          system_prompt: exportSystemPrompt,
          quantization: exportQuant,
        }),
      });
      const data = await res.json();
      setExportResult(data);
    } catch (e) {
      setExportResult({ success: false, error: e.message });
    } finally {
      setExporting(false);
    }
  };

  // Le righe del log utili a una diagnosi, senza le barre di avanzamento e i
  // duplicati di transformers che occupano il 90% dell'output.
  const meaningfulLines = () => logs.filter(l =>
    /\[SIGMA\]|error|errore|traceback|warning|exception|failed/i.test(l)
    && !/\[SIGMA-METRIC\]/.test(l));

  const summary = () => {
    const j = selectedJob || {};
    const s = metrics?.summary || {};
    const plan = j.gpu_plan || {};
    const hyper = j.hyperparams || {};
    // 0.6723926663398743 non si legge e non si confronta a occhio: 4 decimali
    // bastano per distinguere due run.
    const n = (v, dec = 4) => (typeof v === 'number' ? v.toFixed(dec) : (v ?? '—'));
    const lines = [
      `# Riepilogo job ${j.id || '—'}`,
      `modello    ${j.base_model || '—'}`,
      `dataset    ${j.dataset_name || j.dataset_id || '—'}`,
      `metodo     ${j.method_label || j.method || '—'}`,
      `stato      ${j.status || '—'}${j.exit_code != null ? ` (exit ${j.exit_code})` : ''}`,
      // I job di merge/export non hanno step: la riga direbbe solo "0/0".
      ...(j.total_steps ? [`progresso  step ${j.current_step ?? '—'}/${j.total_steps}`
        + `  epoca ${j.current_epoch ?? '—'}/${j.total_epochs ?? '—'}`] : []),
      '',
      '## Iperparametri',
      Object.entries(hyper)
        .filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object')
        .map(([k, v]) => `${k.padEnd(24)} ${v}`).join('\n') || '(nessuno)',
      '',
      '## Hardware',
      `strategia  ${plan.strategy || '—'}  ${(plan.devices || []).join(', ')}`,
      `precisione ${plan.dtype || '—'}  attn ${plan.attn || '—'}  4bit ${plan.load_in_4bit ?? '—'}`,
      ...(plan.notes || []).map(n => `  · ${n}`),
      '',
      '## Metriche',
      `run nel log    ${metrics?.run_count ?? '—'}`
        + (metrics?.previous_points ? ` (${metrics.previous_points} punti da avvii precedenti, esclusi)` : ''),
      `punti          ${s.points ?? '—'}   valutazioni ${s.eval_points ?? '—'}`,
      `loss           ultima ${n(s.last_loss)}  minima ${n(s.min_loss)}  media ${n(s.avg_loss)}`,
      `validation     ultima ${n(s.last_eval_loss)}  migliore ${n(s.best_eval_loss)}`
        + `${s.best_eval_step != null ? ` allo step ${Math.round(s.best_eval_step)}` : ''}`,
      `perplexity     ${n(s.perplexity, 3)}   divario ${n(s.gap)}`,
      `tendenza       ${s.trend != null ? (s.trend * 100).toFixed(2) + '%' : '—'}`,
      '',
      '## Valutazione automatica',
      (metrics?.diagnostics || []).map(v =>
        `[${v.level}] ${v.title}
  ${v.detail}${v.action ? `
  -> ${v.action}` : ''}`
      ).join('\n') || '(nessun verdetto)',
      '',
      '## Righe di log rilevanti (ultime 25)',
      meaningfulLines().slice(-25).join('\n') || '(nessuna)',
    ];
    return lines.join('\n');
  };

  const copySummary = () => navigator.clipboard?.writeText(summary());

  const copyLogs = () => {
    navigator.clipboard?.writeText(logs.join('\n'));
  };

  const getLogClass = (line) => {
    if (line.includes('[SIGMA]')) return 'log-sigma';
    if (/error|errore|failed|exception/i.test(line)) return 'log-error';
    if (/warning|warn/i.test(line)) return 'log-warning';
    if (/completat|success|done/i.test(line)) return 'log-success';
    return '';
  };

  // Progress from last log lines
  const lastProgress = logs.slice(-20).reduce((acc, line) => {
    const prog = parseProgress(line);
    if (prog.epoch) acc.epoch = prog.epoch;
    if (prog.step) acc.step = prog.step;
    return acc;
  }, {});
  const lastLoss = lossPoints.length > 0 ? lossPoints[lossPoints.length - 1].loss : null;

  return (
    <div className={embedded ? "" : "training-panel"}>
      <div className="training-monitor">

        {!embedded && (
          <div className="app-page-header" style={{ marginBottom: '16px' }}>
            <div className="app-page-header-title">
              <div className="app-page-header-icon">
                <BarChart2 size={22} color="#00f2fe" />
              </div>
              <div>
                <h1>Monitor Training</h1>
                <div className="app-page-header-subtitle">
                  <span>Telemetria in tempo reale, curve di loss e log live</span>
                  <span>•</span>
                  <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                    {selectedJob ? `Job ${selectedJob.id} (${selectedJob.status || 'pronto'})` : `${jobs.length} Job registrati`}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Hardware info strip ── */}
        {hardware && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div className="training-hw-strip">
              <div className="training-hw-item">
                <div className={`training-hw-dot ${hardware.cuda_available ? 'ok' : 'warn'}`} />
                <span>CUDA: <strong>{hardware.cuda_available ? 'Disponibile' : 'Non disponibile (Runtime PyTorch)'}</strong></span>
              </div>

              {hardware.gpu?.map((g, i) => (
                <div key={i} className="training-hw-item" style={{ background: 'rgba(0,210,255,0.04)', padding: '3px 8px', borderRadius: '6px', border: '1px solid rgba(0,210,255,0.1)' }}>
                  <span>🎮 <strong>GPU {g.index ?? i}: {g.name}</strong></span>
                  <span style={{ color: 'var(--primary)' }}>{g.vram_total_gb || g.vram_gb} GB VRAM</span>
                  {g.temp_c > 0 && <span style={{ fontSize: '0.58rem', color: 'var(--text-dark)' }}>{g.temp_c}°C</span>}
                </div>
              ))}

              {hardware.multi_gpu?.available && (
                <div className="training-hw-item" style={{ background: 'rgba(188,140,255,0.12)', border: '1px solid rgba(188,140,255,0.25)', padding: '3px 8px', borderRadius: '6px', color: 'var(--accent)' }}>
                  <span>⚡ <strong>Multi-GPU Attivo: {hardware.gpu_count} Schede ({hardware.multi_gpu.total_vram_gb} GB VRAM)</strong></span>
                </div>
              )}

              <div className="training-hw-item" style={{ marginLeft: 'auto' }}>
                <span>RAM: <strong>{hardware.ram_gb} GB ({hardware.ram_free_gb || '?'} GB Liberi)</strong></span>
              </div>
              {hardware.torch_available && (
                <div className="training-hw-item">
                  <span>🔥 PyTorch: <strong>{hardware.torch_version}</strong></span>
                </div>
              )}
            </div>

            {/* CUDA Fix / Diagnostic Card if issues detected */}
            {hardware.cuda_fix?.has_issue && (
              <div style={{
                background: 'rgba(255,166,0,0.06)',
                border: '1px solid rgba(255,166,0,0.2)',
                borderRadius: '10px',
                padding: '12px 14px',
                fontSize: '0.7rem',
                color: 'var(--text-dim)',
              }}>
                <div style={{ fontWeight: 700, color: 'var(--warning)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>⚠️</span> {hardware.cuda_fix.title}
                </div>
                <div style={{ marginBottom: '8px', lineHeight: '1.4' }}>
                  {hardware.cuda_fix.description}
                </div>
                {hardware.cuda_fix.commands?.length > 0 && (
                  <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '8px 10px' }}>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text-dark)', marginBottom: '4px', textTransform: 'uppercase' }}>Comandi consigliati da eseguire nel terminale:</div>
                    {hardware.cuda_fix.commands.map((cmd, idx) => (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <code style={{ fontFamily: 'JetBrains Mono', color: 'var(--primary)', fontSize: '0.64rem' }}>{cmd}</code>
                        <button
                          className="training-log-ctrl-btn"
                          onClick={() => navigator.clipboard?.writeText(cmd)}
                          style={{ fontSize: '0.58rem', padding: '2px 6px' }}
                        >
                          Copia
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Job selector ── */}
        {/* Nello Studio la fase la sceglie la catena: una seconda lista qui
            terrebbe una selezione propria e direbbe un'altra cosa nella stessa
            pagina. */}
        {!embedded && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Job di Training
            </div>
            <button className="training-btn" onClick={loadJobs} style={{ marginLeft: 'auto' }}>
              <RefreshCw size={11} /> Aggiorna
            </button>
          </div>
          {jobs.length === 0 ? (
            <div className="training-empty" style={{ padding: '20px' }}>
              <div className="training-empty-icon">📭</div>
              <div className="training-empty-title">Nessun job ancora</div>
              <div className="training-empty-sub">Configura e avvia un training dalla tab "Training"</div>
            </div>
          ) : (
            <div className="training-job-selector">
              {jobs.map(job => {
                const st = STATUS_LABELS[job.status] || STATUS_LABELS.ready;
                return (
                  <button
                    key={job.id}
                    className={`training-job-chip ${selectedJobId === job.id ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedJobId(job.id);
                      setLogs([]);
                      setLossPoints([]);
                    }}
                  >
                    <div className={`training-job-status-dot ${job.status}`} />
                    <span title={`${job.base_model} → ${job.dataset_name}`}>
                      {job.id} · {job.output_name || job.id}
                    </span>
                    <span className={`training-status-chip ${job.status}`}>{st.label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        )}

        {/* ── Selected job controls ── */}
        {selectedJob && (
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
            borderRadius: '12px', padding: '14px',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
                  Job {selectedJob.id}
                  <span className={`training-status-chip ${selectedJob.status}`} style={{ marginLeft: '8px' }}>
                    {STATUS_LABELS[selectedJob.status]?.label}
                  </span>
                </div>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.6 }}>
                  <div>Modello: <code style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono' }}>{selectedJob.base_model}</code></div>
                  <div>Dataset: <strong>{selectedJob.dataset_name || selectedJob.dataset_id}</strong></div>
                  <div>Metodo: {selectedJob.method}</div>
                  {selectedJob.started_at && <div>Avviato: {new Date(selectedJob.started_at).toLocaleTimeString()}</div>}
                  {selectedJob.finished_at && <div>Terminato: {new Date(selectedJob.finished_at).toLocaleTimeString()}</div>}
                </div>
              </div>
              {/* Progress summary */}
              {(lastProgress.epoch || lastLoss !== null) && (
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  {lastProgress.epoch && (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--primary)', fontFamily: 'JetBrains Mono' }}>
                        {lastProgress.epoch.current}/{lastProgress.epoch.total}
                      </div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)' }}>epoche</div>
                    </div>
                  )}
                  {lastLoss !== null && (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent)', fontFamily: 'JetBrains Mono' }}>
                        {lastLoss.toFixed(4)}
                      </div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)' }}>loss</div>
                    </div>
                  )}
                </div>
              )}
              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
                {(selectedJob.status === 'ready' || selectedJob.status === 'stopped' || selectedJob.status === 'failed') && (
                  <button className="training-btn primary" onClick={() => handleStart(selectedJob.id)}>
                    <Play size={12} fill="currentColor" /> Avvia
                  </button>
                )}
                {selectedJob.status === 'running' && (
                  <button className="training-btn danger" onClick={() => handleStop(selectedJob.id)}>
                    <Square size={12} /> Stop
                  </button>
                )}
                {selectedJob.method === 'fwe_gradus'
                  && ['completed', 'stopped', 'failed'].includes(selectedJob.status) && (
                  <button
                    className="training-btn"
                    title="Riprende dal checkpoint del generatore e prosegue fino a un totale maggiore"
                    onClick={() => handleContinue(selectedJob)}
                  >
                    <Play size={12} /> Continua
                  </button>
                )}
                {['lora_unsloth', 'trl_sft'].includes(selectedJob.method)
                  && ['completed', 'stopped'].includes(selectedJob.status) && (
                  <button
                    className="training-btn"
                    title="Prosegue il fine-tuning in un nuovo job, tenendo quello che questo ha imparato"
                    onClick={() => {
                      setContinueDataset(selectedJob.dataset_id || '');
                      setContinueResult(null);
                      setContinueModal(true);
                    }}
                  >
                    <Play size={12} /> Continua training
                  </button>
                )}
                {selectedJob.status === 'completed' && (
                  <button className="training-btn primary" onClick={() => {
                    setExportName(selectedJob.output_name || `sigma_${selectedJob.id}`);
                    setExportModal(true);
                  }}>
                    <Package size={12} /> Export → Ollama
                  </button>
                )}
                <button className="training-btn danger" onClick={() => handleDelete(selectedJob.id)}>
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Metriche, curve e valutazione automatica ── */}
        {selectedJob && (
          metrics?.history?.length > 0 ? (
            <TrainingMetrics metrics={metrics} />
          ) : (
            /* Run generati prima delle righe [SIGMA-METRIC]: resta il grafico
               semplice ricostruito dal testo del log. */
            <div className="training-chart-container">
              <div className="training-chart-title">📈 Loss nel tempo ({lossPoints.length} datapoint)</div>
              <LossChart dataPoints={lossPoints} />
            </div>
          )
        )}

        {/* ── Log terminal ── */}
        {selectedJob && (
          <div>
            <div className="training-log-controls">
              {/* Il log grezzo è migliaia di righe di barre di avanzamento: per
                  capire com'è andato un run, o per farlo leggere a qualcun
                  altro, serve un riepilogo, non l'output. */}
              {[['output', `Output — ${logs.length} righe`],
                ['riepilogo', 'Riepilogo']].map(([id, label]) => (
                <button
                  key={id}
                  className="training-log-ctrl-btn"
                  onClick={() => setConsoleTab(id)}
                  style={{
                    color: consoleTab === id ? 'var(--primary)' : 'var(--text-dim)',
                    borderColor: consoleTab === id ? 'rgba(0,210,255,0.3)' : undefined,
                    background: consoleTab === id ? 'rgba(0,210,255,0.06)' : undefined,
                    fontWeight: consoleTab === id ? 700 : 500,
                  }}
                >
                  {id === 'output' && <ScrollText size={10} style={{ marginRight: '4px' }} />}
                  {label}
                </button>
              ))}
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '5px' }}>
                {consoleTab === 'output' ? (
                  <>
                    <button
                      className="training-log-ctrl-btn"
                      onClick={() => setAutoScroll(!autoScroll)}
                      style={{ color: autoScroll ? 'var(--primary)' : 'var(--text-dim)' }}
                    >
                      {autoScroll ? '⬇ Auto-scroll' : '⬇ Auto-scroll OFF'}
                    </button>
                    <button className="training-log-ctrl-btn" onClick={copyLogs}>
                      <Copy size={10} /> Copia
                    </button>
                    <button className="training-log-ctrl-btn" onClick={() => setLogs([])}>
                      Pulisci
                    </button>
                  </>
                ) : (
                  <button className="training-log-ctrl-btn" onClick={copySummary}
                          style={{ color: 'var(--primary)' }}>
                    <Copy size={10} /> Copia riepilogo
                  </button>
                )}
              </div>
            </div>
            {consoleTab === 'riepilogo' ? (
              <pre className="training-log-terminal" style={{
                whiteSpace: 'pre-wrap', margin: 0, fontSize: '0.68rem', lineHeight: 1.5,
              }}>
                {summary()}
              </pre>
            ) : (
            <div className="training-log-terminal">
              {logs.length === 0 ? (
                <span className="log-empty">
                  {selectedJob.status === 'running'
                    ? 'In attesa di output...'
                    : selectedJob.status === 'ready'
                    ? '💡 Premi "Avvia" per iniziare il training'
                    : 'Nessun log disponibile'}
                </span>
              ) : (
                logs.map((line, i) => (
                  <span key={i} className={`log-line ${getLogClass(line)}`}>
                    {line || '\u00A0'}
                  </span>
                ))
              )}
              <div ref={logEndRef} />
            </div>
            )}
          </div>
        )}

        {/* ── No job selected ── */}
        {!selectedJob && jobs.length > 0 && (
          <div className="training-empty">
            <div className="training-empty-icon">👆</div>
            <div className="training-empty-title">Seleziona un job</div>
          </div>
        )}

      </div>

      {/* ── Export Modal ── */}
      {continueModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex',
            alignItems: 'center', justifyContent: 'center', padding: '20px',
          }}
          onClick={() => setContinueModal(false)}
        >
          <div
            style={{
              background: 'rgba(15,17,32,0.98)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '18px', padding: '24px', width: '100%', maxWidth: '520px',
              maxHeight: '86vh', overflowY: 'auto',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
              ▶️ Continua il training
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', marginBottom: '16px', lineHeight: 1.55 }}>
              Nasce un job nuovo agganciato a <code style={{ color: 'var(--primary)' }}>{selectedJobId}</code>.
              Log, metriche e checkpoint di questo restano intatti.
            </div>

            <div className="training-field" style={{ marginBottom: '14px' }}>
              <label>Da dove ripartono i pesi</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                {continueModes.map(m => (
                  <button
                    key={m.id}
                    onClick={() => setContinueMode(m.id)}
                    style={{
                      textAlign: 'left', padding: '10px 12px', borderRadius: '10px',
                      border: '1px solid', cursor: 'pointer',
                      borderColor: continueMode === m.id ? 'rgba(0,210,255,0.35)' : 'rgba(255,255,255,0.07)',
                      background: continueMode === m.id ? 'rgba(0,210,255,0.06)' : 'transparent',
                    }}
                  >
                    <div style={{
                      fontSize: '0.7rem', fontWeight: 700, marginBottom: '3px',
                      color: continueMode === m.id ? 'var(--primary)' : 'var(--text)',
                    }}>
                      {m.label}
                    </div>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>
                      {m.detail}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="training-field" style={{ marginBottom: '16px' }}>
              <label>Dataset</label>
              <div className="training-select-wrapper">
                <select
                  className="training-select"
                  value={continueDataset}
                  onChange={e => setContinueDataset(e.target.value)}
                >
                  <option value={selectedJob?.dataset_id || ''}>
                    Lo stesso di prima — {selectedJob?.dataset_name || selectedJob?.dataset_id || 'n/d'}
                  </option>
                  {datasets
                    .filter(d => d.id !== selectedJob?.dataset_id)
                    .map(d => <option key={d.id} value={d.id}>{d.name || d.id}</option>)}
                </select>
              </div>
              <div className="training-field-desc">
                Cambiare dataset insegna un compito nuovo, ma su un adapter ripreso il
                modello può dimenticare il precedente se i due sono molto diversi.
              </div>
            </div>

            {continueResult && (
              <div style={{
                padding: '10px 14px', borderRadius: '10px', marginBottom: '14px',
                background: continueResult.success ? 'rgba(63,185,80,0.08)' : 'rgba(255,85,85,0.08)',
                border: `1px solid ${continueResult.success ? 'rgba(63,185,80,0.2)' : 'rgba(255,85,85,0.2)'}`,
                color: continueResult.success ? 'var(--success)' : 'var(--error)',
                fontSize: '0.68rem', lineHeight: 1.55,
              }}>
                {continueResult.success
                  ? `✅ ${continueResult.message} Premi «Avvia» per farlo partire.`
                  : `❌ ${continueResult.error}`}
              </div>
            )}

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button className="training-btn" onClick={() => setContinueModal(false)}>Chiudi</button>
              <button
                className="training-btn primary"
                onClick={handleContinueTraining}
                disabled={continuing || continueResult?.success}
              >
                {continuing ? 'Creazione...' : 'Crea il job di continuazione'}
              </button>
            </div>
          </div>
        </div>
      )}

      {exportModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex',
            alignItems: 'center', justifyContent: 'center', padding: '20px',
          }}
          onClick={() => setExportModal(false)}
        >
          <div
            style={{
              background: 'rgba(15,17,32,0.98)', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '18px', padding: '24px', width: '100%', maxWidth: '480px',
              boxShadow: '0 32px 64px rgba(0,0,0,0.5)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', marginBottom: '16px' }}>
              🦙 Export verso Ollama
            </div>
            <div className="training-field" style={{ marginBottom: '12px' }}>
              <label>Nome Modello Ollama</label>
              <input
                className="training-input"
                value={exportName}
                onChange={e => setExportName(e.target.value)}
                placeholder="sigma_mio_modello"
              />
              <div className="training-field-desc">
                Sarà accessibile come: <code style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono' }}>ollama run {exportName || 'nome'}</code>
              </div>
            </div>
            <div className="training-field" style={{ marginBottom: '12px' }}>
              <label>Quantizzazione</label>
              <div className="training-select-wrapper">
                <select
                  className="training-select"
                  value={exportQuant}
                  onChange={e => setExportQuant(e.target.value)}
                >
                  <option value="">Nessuna — 16 bit, qualità piena</option>
                  {quantLevels.map(q => (
                    <option key={q.id} value={q.id}>{q.label}</option>
                  ))}
                </select>
              </div>
              <div className="training-field-desc">
                {exportQuant
                  ? `Ollama quantizza durante l'export: il modello occuperà circa il ${
                      Math.round((quantLevels.find(q => q.id === exportQuant)?.ratio || 1) * 100)
                    }% dei pesi a 16 bit, e gira su meno VRAM al prezzo di un po' di qualità.`
                  : 'Pesi a 16 bit: nessuna perdita, ma è il file più grande e il più lento da caricare.'}
              </div>
            </div>
            <div className="training-field" style={{ marginBottom: '16px' }}>
              <label>System Prompt (opzionale)</label>
              <textarea
                className="training-input"
                rows={3}
                value={exportSystemPrompt}
                onChange={e => setExportSystemPrompt(e.target.value)}
                placeholder="Sei un assistente AI specializzato in..."
                style={{ resize: 'vertical', fontFamily: 'inherit' }}
              />
            </div>
            {exportResult && (
              <div style={{
                padding: '10px 14px', borderRadius: '10px', marginBottom: '14px',
                background: exportResult.success ? 'rgba(63,185,80,0.08)' : 'rgba(255,85,85,0.08)',
                border: `1px solid ${exportResult.success ? 'rgba(63,185,80,0.2)' : 'rgba(255,85,85,0.2)'}`,
                color: exportResult.success ? 'var(--success)' : 'var(--error)',
                fontSize: '0.7rem', lineHeight: 1.5,
              }}>
                {exportResult.success ? (
                  <>
                    ✅ Modelfile generato in: <code style={{ fontFamily: 'JetBrains Mono', display: 'block', marginTop: '4px', color: 'var(--primary)', fontSize: '0.62rem' }}>{exportResult.modelfile_path}</code>
                    {exportResult.note && <div style={{ marginTop: '6px', color: 'var(--warning)' }}>{exportResult.note}</div>}
                  </>
                ) : (
                  `❌ ${exportResult.error}`
                )}
              </div>
            )}
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                className="training-btn"
                onClick={() => setExportModal(false)}
              >
                Chiudi
              </button>
              <button
                className="training-start-btn"
                style={{ width: 'auto', padding: '10px 20px', marginTop: 0 }}
                onClick={handleExport}
                disabled={exporting || !exportName.trim()}
              >
                {exporting ? <><div className="training-spinner" style={{ width: '14px', height: '14px', borderColor: 'rgba(0,0,0,0.2)', borderTopColor: '#000' }} /> Export...</> : '🦙 Esporta'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
