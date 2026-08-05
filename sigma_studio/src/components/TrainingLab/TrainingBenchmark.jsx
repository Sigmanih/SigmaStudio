import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Play, Activity, Zap, CheckCircle2, XCircle, Trash2, Cpu,
  Award, RefreshCw, Shield, Download, Check, StopCircle, Search,
  RotateCcw, Layers, Compass, AlertTriangle, HelpCircle, Database, Terminal,
  Gauge, Server, Plus, Power, ChevronDown,
} from 'lucide-react';

const SUITE_LABELS = {
  all: { name: '🌐 Tutti i Benchmark', badge: 'FULL 100%' },
  mmlu: { name: '🏆 MMLU', badge: '57 Materie' },
  mmlu_pro: { name: '🧠 MMLU-Pro', badge: 'Ragionamento Hard' },
  gsm8k: { name: '🧮 GSM8K', badge: 'Math' },
  math: { name: '📐 MATH', badge: 'Olimpico' },
  humaneval: { name: '💻 HumanEval', badge: 'pass@1' },
  mbpp: { name: '🐍 MBPP', badge: 'pass@1' },
  arc: { name: '🔬 ARC Science', badge: 'Scienze' },
  hellaswag: { name: '💡 HellaSwag', badge: 'Buon Senso' },
  truthfulqa: { name: '🛡️ TruthfulQA', badge: 'Anti-Allucinazione' },
  gpqa: { name: '🎓 GPQA', badge: 'Expert Level' },
  bbh: { name: '⚙️ BIG-Bench Hard', badge: '27 Task' },
};

const SUITE_ORDER = ['all', 'mmlu', 'mmlu_pro', 'gsm8k', 'math', 'humaneval', 'mbpp',
  'arc', 'hellaswag', 'truthfulqa', 'gpqa', 'bbh'];

// Stati che indicano un job ancora vivo: guidano il polling e i pulsanti.
const ACTIVE_STATUSES = ['running', 'preparing', 'paused', 'cancelling', 'executing'];

// Un verdetto per riquadro: `pass`/`fail` sono esiti, gli altri tre vanno rivisti.
const VERDICT_STYLE = {
  pass: { label: 'PASS', color: 'var(--success)', bg: 'rgba(63,185,80,0.12)', border: 'rgba(63,185,80,0.4)', Icon: CheckCircle2 },
  fail: { label: 'FAIL', color: '#ff5555', bg: 'rgba(255,85,85,0.12)', border: 'rgba(255,85,85,0.4)', Icon: XCircle },
  ambiguous: { label: 'RISPOSTA DUPLICE', color: '#ffb86c', bg: 'rgba(255,184,108,0.12)', border: 'rgba(255,184,108,0.45)', Icon: AlertTriangle },
  unparsable: { label: 'NON INTERPRETABILE', color: '#bc8cff', bg: 'rgba(188,140,255,0.12)', border: 'rgba(188,140,255,0.45)', Icon: HelpCircle },
  error: { label: 'ERRORE MODELLO', color: '#8b949e', bg: 'rgba(139,148,158,0.12)', border: 'rgba(139,148,158,0.4)', Icon: StopCircle },
};

const CONFIDENCE_LABEL = { high: 'alta', medium: 'media', low: 'bassa', none: '—' };

const ACCENT = '#00d2ff';
const fmt = (n) => (Number(n) || 0).toLocaleString('it-IT');

const card = {
  background: 'rgba(15,18,35,0.6)',
  border: '1px solid var(--border)',
  borderRadius: '16px',
  padding: '20px',
};

const panel = {
  background: 'rgba(10,12,26,0.6)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  padding: '14px',
};

const btn = (active, accent = ACCENT) => ({
  padding: '4px 10px',
  borderRadius: '6px',
  fontSize: '0.72rem',
  fontWeight: 600,
  cursor: 'pointer',
  background: active ? `${accent}2b` : 'rgba(255,255,255,0.05)',
  color: active ? accent : 'var(--text-dark)',
  border: `1px solid ${active ? accent : 'transparent'}`,
});

const sectionTitle = {
  fontSize: '0.7rem',
  fontWeight: 700,
  color: 'var(--text-dark)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
  marginBottom: '10px',
};

export default function TrainingBenchmark({ addToast }) {
  const [models, setModels] = useState([]);
  const [ollamaUp, setOllamaUp] = useState(true);
  const [modelSearch, setModelSearch] = useState('');
  const [modelOpen, setModelOpen] = useState(false);
  // Un modello per volta: un run confronta un modello con un dataset, e la
  // selezione multipla rendeva ambiguo a chi si riferissero capacita' e stime.
  const [selectedModel, setSelectedModel] = useState(null);

  const [selectedSuite, setSelectedSuite] = useState('all');
  const [suiteInfo, setSuiteInfo] = useState({});
  const [suiteTotals, setSuiteTotals] = useState({ count: 0, cached_suites: 0, total_suites: 0 });
  const [downloading, setDownloading] = useState([]);

  const [evalMode, setEvalMode] = useState('full');
  const [sampleCount, setSampleCount] = useState(25);
  // Due sole scelte: una richiesta per volta, oppure quante ne regge la macchina.
  const [execMode, setExecMode] = useState('auto');
  const [launching, setLaunching] = useState(false);

  const [capacity, setCapacity] = useState(null);
  const [probing, setProbing] = useState(false);
  const [probeLevel, setProbeLevel] = useState(null);
  const [engine, setEngine] = useState(null);
  const [engineBusy, setEngineBusy] = useState(false);

  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState('all');
  const [suiteFilter, setSuiteFilter] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);

  const toast = useCallback((msg, kind) => { if (addToast) addToast(msg, kind); }, [addToast]);

  const post = useCallback((path, body) => fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((r) => r.json()), []);

  // ── Caricamenti ────────────────────────────────────────────────────────────

  const loadModels = useCallback(async () => {
    try {
      const res = await fetch('/api/training/benchmark/models');
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.models || []);
      setModels(list);
      setOllamaUp(Array.isArray(data) ? true : data.ollama_available !== false);
      setSelectedModel((prev) => (
        prev && list.some((m) => m.id === prev) ? prev : (list[0]?.id ?? null)
      ));
    } catch (err) {
      console.error('Modelli benchmark non caricati:', err);
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/training/benchmark/jobs');
      if (!res.ok) return [];
      const list = (await res.json()) || [];
      setJobs(list);
      setSelectedJobId((prev) => (prev && list.some((j) => j.id === prev) ? prev : (list[0]?.id ?? null)));
      return list;
    } catch (err) {
      console.error('Job benchmark non caricati:', err);
      return [];
    }
  }, []);

  const loadSuiteInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/training/benchmark/suite_info?suite=all');
      if (!res.ok) return;
      const data = await res.json();
      setSuiteInfo(data?.suites || {});
      setSuiteTotals({
        count: data?.count || 0,
        cached_suites: data?.cached_suites || 0,
        total_suites: data?.total_suites || 0,
      });
    } catch (err) {
      console.error('Stato dataset non caricato:', err);
    }
  }, []);

  const loadEngine = useCallback(async () => {
    try {
      const res = await fetch('/api/training/benchmark/endpoints');
      const data = await res.json();
      setEngine(data?.success ? data : null);
    } catch (err) {
      console.error('Stato motore parallelo non caricato:', err);
    }
  }, []);

  const loadCapacity = useCallback(async () => {
    if (!selectedModel) { setCapacity(null); return; }
    try {
      const res = await fetch(`/api/training/benchmark/capacity?model=${encodeURIComponent(selectedModel)}`);
      const data = await res.json();
      setCapacity(data?.success ? data : null);
    } catch (err) {
      console.error('Capacita\' non caricata:', err);
      setCapacity(null);
    }
  }, [selectedModel]);

  useEffect(() => { loadModels(); loadJobs(); loadSuiteInfo(); loadEngine(); },
    [loadModels, loadJobs, loadSuiteInfo, loadEngine]);
  useEffect(() => { loadCapacity(); }, [loadCapacity]);

  // Un booleano stabile come dipendenza: `jobs` cambia a ogni polling, e usarlo
  // faceva distruggere e ricreare l'intervallo prima che scattasse.
  const hasActiveJobs = useMemo(() => jobs.some((j) => ACTIVE_STATUSES.includes(j.status)), [jobs]);
  const wasActive = useRef(false);

  useEffect(() => {
    if (!hasActiveJobs) {
      if (wasActive.current) {
        wasActive.current = false;
        toast('✅ Valutazione completata.', 'success');
      }
      return undefined;
    }
    wasActive.current = true;
    const timer = setInterval(loadJobs, 2000);
    return () => clearInterval(timer);
  }, [hasActiveJobs, loadJobs, toast]);

  useEffect(() => {
    const timer = setTimeout(() => { setSearchQuery(searchInput); setPage(1); }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => { setPage(1); }, [selectedJobId, verdictFilter, suiteFilter, pageSize]);

  const activeJob = useMemo(
    () => jobs.find((j) => j.id === selectedJobId) || null,
    [jobs, selectedJobId],
  );
  const activeStatus = activeJob?.status;

  const loadDetail = useCallback(async () => {
    if (!selectedJobId) { setDetail(null); return; }
    setDetailLoading(true);
    try {
      const params = new URLSearchParams({
        job_id: selectedJobId,
        page: String(page),
        page_size: String(pageSize),
        verdict: verdictFilter,
        suite: suiteFilter,
        q: searchQuery,
      });
      const res = await fetch(`/api/training/benchmark/results?${params}`);
      const data = await res.json();
      setDetail(data?.success === false ? null : data);
    } catch (err) {
      console.error('Dettaglio job non caricato:', err);
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
    // `activeStatus` fra le dipendenze: al passaggio a "completed" gli esiti si
    // ricaricano da soli, senza aspettare un cambio di pagina o filtro.
  }, [selectedJobId, page, pageSize, verdictFilter, suiteFilter, searchQuery, activeStatus]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  useEffect(() => {
    if (!activeStatus || !ACTIVE_STATUSES.includes(activeStatus)) return undefined;
    const timer = setInterval(loadDetail, 3000);
    return () => clearInterval(timer);
  }, [activeStatus, loadDetail]);

  // ── Azioni ─────────────────────────────────────────────────────────────────

  const handleDownload = async (suiteId) => {
    setDownloading((prev) => [...prev, suiteId]);
    toast(`📥 Download dataset ${suiteId}...`, 'info');
    try {
      const data = await post('/api/training/benchmark/download', { suite: suiteId });
      toast(data.success
        ? `✅ ${suiteId}: ${fmt(data.count)} quesiti in cache`
        : `❌ Download ${suiteId}: ${data.error || 'errore sconosciuto'}`,
      data.success ? 'success' : 'error');
      loadSuiteInfo();
    } catch (err) {
      toast(`❌ Errore di rete: ${err.message}`, 'error');
    } finally {
      setDownloading((prev) => prev.filter((s) => s !== suiteId));
    }
  };

  const handleStart = async (overrideModel = null, overrideSuite = null) => {
    const model = overrideModel || selectedModel;
    const suite = overrideSuite || selectedSuite;
    if (!model) { toast('⚠️ Seleziona un modello', 'warning'); return; }

    setLaunching(true);
    try {
      const data = await post('/api/training/benchmark/run', {
        model,
        suite,
        mode: evalMode,
        samples: evalMode === 'full' ? 0 : sampleCount,
        // "auto" viene risolto dal backend sull'hardware del momento: la UI non
        // deve indovinare un numero che potrebbe non essere piu' valido.
        concurrency: execMode === 'single' ? 1 : 'auto',
      });
      if (!data.success) { toast('❌ Avvio non riuscito', 'error'); return; }
      setSelectedJobId(data.job.id);
      toast(`🚀 [${SUITE_LABELS[suite]?.name || suite}] avviato su ${model} — `
        + `${data.job.concurrency} in parallelo`, 'info');
      loadJobs();
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    } finally {
      setLaunching(false);
    }
  };

  const jobAction = async (path, jobId, message, event) => {
    if (event) event.stopPropagation();
    try {
      const data = await post(path, { id: jobId });
      if (data.success) { toast(message, 'info'); loadJobs(); }
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    }
  };

  const handleCancelAll = async () => {
    const active = jobs.filter((j) => ACTIVE_STATUSES.includes(j.status));
    for (const job of active) await post('/api/training/benchmark/cancel', { id: job.id });
    if (active.length) { toast('🛑 Valutazioni annullate.', 'warning'); loadJobs(); }
  };

  const handleProbeCapacity = async () => {
    if (!selectedModel || probing) return;
    setProbing(true);
    setProbeLevel(null);
    toast(`📈 Misura della capacità di ${selectedModel}...`, 'info');
    try {
      const start = await post('/api/training/benchmark/capacity/probe', { model: selectedModel });
      if (!start.success) { toast(`❌ ${start.error}`, 'error'); return; }
      for (let i = 0; i < 400; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const status = await (await fetch(
          `/api/training/benchmark/capacity/status?probe_id=${start.probe_id}`)).json();
        setProbeLevel(status.current_level);
        if (status.status === 'completed') {
          toast(`✅ ${status.result?.recommended_parallel}x in parallelo `
            + `(picco ${status.result?.peak_tokens_per_sec} tok/s)`, 'success');
          await loadCapacity();
          break;
        }
        if (status.status === 'failed') {
          toast(`❌ ${status.result?.error || 'misura non riuscita'}`, 'error');
          break;
        }
      }
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    } finally {
      setProbing(false);
      setProbeLevel(null);
    }
  };

  const handleStartEndpoint = async (gpuIndex) => {
    setEngineBusy(true);
    toast(`⚙️ Avvio istanza Ollama su GPU ${gpuIndex}...`, 'info');
    try {
      const data = await post('/api/training/benchmark/endpoints/start', { gpu_index: gpuIndex });
      if (data.success) {
        toast(`✅ Istanza attiva su GPU ${gpuIndex} (${data.url})`, 'success');
        await Promise.all([loadEngine(), loadCapacity()]);
      } else {
        toast(`❌ ${data.error}`, 'error');
      }
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    } finally {
      setEngineBusy(false);
    }
  };

  const handleStopEndpoint = async (port) => {
    setEngineBusy(true);
    try {
      const data = await post('/api/training/benchmark/endpoints/stop', { port });
      toast(data.success ? `🔌 Istanza sulla porta ${port} fermata` : `❌ ${data.error}`,
        data.success ? 'info' : 'error');
      await Promise.all([loadEngine(), loadCapacity()]);
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    } finally {
      setEngineBusy(false);
    }
  };

  const download = (payload, filename, message) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
    toast(message, 'success');
  };

  const handleExportReport = async () => {
    if (!activeJob) return;
    const params = new URLSearchParams({ job_id: activeJob.id, page: '1', page_size: '200', verdict: 'all' });
    let all = [];
    try {
      const first = await (await fetch(`/api/training/benchmark/results?${params}`)).json();
      all = first.results || [];
      for (let p = 2; p <= (first.pages || 1); p += 1) {
        params.set('page', String(p));
        const next = await (await fetch(`/api/training/benchmark/results?${params}`)).json();
        all = all.concat(next.results || []);
      }
    } catch (err) {
      toast(`❌ Export non riuscito: ${err.message}`, 'error');
      return;
    }
    download({
      title: `Rapporto Benchmark Ufficiale: ${activeJob.model}`,
      timestamp: activeJob.created_at,
      model: activeJob.model,
      suite: activeJob.suite_name,
      concurrency: activeJob.concurrency,
      endpoints: activeJob.endpoints,
      reproducibility: activeJob.reproducibility,
      metrics: activeJob.metrics,
      verdict_counts: detail?.verdict_counts || {},
      suite_breakdown: detail?.suite_breakdown || {},
      test_results: all,
    }, `benchmark_${activeJob.model.replace(/[^a-zA-Z0-9]/g, '_')}_${activeJob.id}.json`,
    `📥 Report esportato (${fmt(all.length)} quesiti)`);
  };

  const handleExportReview = async () => {
    if (!activeJob) return;
    try {
      const data = await (await fetch(`/api/training/benchmark/review?job_id=${activeJob.id}`)).json();
      if (!data.success) { toast(`❌ ${data.error}`, 'error'); return; }
      download(data, `revisione_${activeJob.id}.json`,
        `⚠️ Coda di revisione esportata (${fmt(data.count)} quesiti)`);
    } catch (err) {
      toast(`❌ ${err.message}`, 'error');
    }
  };

  // ── Derivati ───────────────────────────────────────────────────────────────

  const currentModel = useMemo(
    () => models.find((m) => m.id === selectedModel) || null,
    [models, selectedModel],
  );

  const filteredModels = useMemo(() => {
    const needle = modelSearch.trim().toLowerCase();
    if (!needle) return models;
    return models.filter((m) => `${m.name} ${m.family} ${m.parameter_size} ${m.quantization}`
      .toLowerCase().includes(needle));
  }, [models, modelSearch]);

  const plannedItems = useMemo(() => {
    const info = selectedSuite === 'all'
      ? { count: suiteTotals.count }
      : (suiteInfo[selectedSuite] || { count: 0 });
    const total = info.count || 0;
    return evalMode === 'sample' ? Math.min(sampleCount, total || sampleCount) : total;
  }, [selectedSuite, suiteInfo, suiteTotals, evalMode, sampleCount]);

  // Quante richieste partiranno davvero. Con "auto" il numero definitivo lo
  // decide il backend al lancio; qui si mostra la stessa regola per non
  // sorprendere l'utente dopo che ha premuto Avvia.
  const effectiveConcurrency = useMemo(() => {
    if (execMode === 'single') return 1;
    const measured = capacity?.profile?.recommended_parallel;
    if (measured) return measured;
    const est = capacity?.estimate;
    const ceiling = 4 * Math.max(1, est?.endpoint_count || 1);
    return Math.max(1, Math.min(est?.max_parallel_now || 1, ceiling));
  }, [execMode, capacity]);

  const estimate = useMemo(() => {
    const reference = jobs.find((j) => j.metrics?.avg_latency_ms > 0);
    const perItemMs = reference?.metrics?.avg_latency_ms || 1500;
    const seconds = (plannedItems * perItemMs) / 1000 / Math.max(1, effectiveConcurrency);
    if (!plannedItems) return null;
    if (seconds < 90) return `~${Math.round(seconds)} s`;
    if (seconds < 5400) return `~${Math.round(seconds / 60)} min`;
    return `~${(seconds / 3600).toFixed(1)} h`;
  }, [plannedItems, effectiveConcurrency, jobs]);

  const metrics = activeJob?.metrics || {};
  const repro = activeJob?.reproducibility || {};
  const counts = detail?.verdict_counts || {};
  const reviewTotal = (counts.ambiguous || 0) + (counts.unparsable || 0) + (counts.error || 0);
  const decidedTotal = (counts.pass || 0) + (counts.fail || 0);
  const jobSuites = Object.keys(detail?.suite_breakdown || {});
  const canLaunch = Boolean(selectedModel) && plannedItems > 0 && !launching;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: '20px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Intestazione coordinata Stile Hardware & GPU */}
      <div className="app-page-header">
        <div className="app-page-header-title">
          <div className="app-page-header-icon">
            <Award size={22} color="#00f2fe" />
          </div>
          <div>
            <h1>Valutazione Ufficiale Benchmark LLM</h1>
            <div className="app-page-header-subtitle">
              <span>11 suite ufficiali, temp 0.0 & seed 42</span>
              <span>•</span>
              <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                {fmt(suiteTotals.count)} QUESITI IN CACHE
              </span>
            </div>
          </div>
        </div>
        <div className="app-page-header-actions">
          <button onClick={() => { loadModels(); loadJobs(); loadSuiteInfo(); loadEngine(); loadCapacity(); }} style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px', padding: '6px 12px', color: 'var(--text)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', fontWeight: 600,
          }}>
            <RefreshCw size={13} /> Aggiorna
          </button>
        </div>
      </div>

      {/* Dataset */}
      <div style={{ ...card, display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={16} style={{ color: 'var(--accent)' }} />
            Dataset — {suiteTotals.cached_suites}/{suiteTotals.total_suites} suite in cache
          </h3>
          <button
            onClick={() => handleDownload('all')}
            disabled={downloading.length > 0}
            style={{
              ...btn(false), border: '1px solid rgba(0,210,255,0.3)', color: ACCENT,
              background: 'rgba(0,210,255,0.1)', fontWeight: 700,
              cursor: downloading.length > 0 ? 'wait' : 'pointer',
            }}
          >
            {downloading.includes('all') ? '⏳ Download...' : '📥 Scarica tutte'}
          </button>
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
          gap: '10px', maxHeight: '260px', overflowY: 'auto', paddingRight: '4px',
        }}>
          {SUITE_ORDER.map((id) => {
            const label = SUITE_LABELS[id];
            const info = id === 'all'
              ? { cached: suiteTotals.cached_suites === suiteTotals.total_suites, count: suiteTotals.count }
              : (suiteInfo[id] || {});
            const isSelected = selectedSuite === id;
            const busy = downloading.includes(id) || downloading.includes('all');
            return (
              <div
                key={id}
                onClick={() => setSelectedSuite(id)}
                style={{
                  background: isSelected ? 'rgba(0,210,255,0.12)' : 'rgba(10,12,26,0.6)',
                  border: `1px solid ${isSelected ? 'rgba(0,210,255,0.45)' : 'var(--border)'}`,
                  borderRadius: '10px', padding: '9px 11px', cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', gap: '5px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: isSelected ? ACCENT : 'var(--text)' }}>
                    {label.name}
                  </span>
                  <span style={{
                    fontSize: '0.55rem', fontWeight: 700, padding: '2px 5px', borderRadius: '5px',
                    background: isSelected ? 'rgba(0,210,255,0.2)' : 'rgba(255,255,255,0.06)',
                    color: isSelected ? ACCENT : 'var(--text-dark)', whiteSpace: 'nowrap',
                  }}>{label.badge}</span>
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-dark)' }}>
                  {info.cached ? (
                    <>
                      <span style={{ color: 'var(--success)', fontWeight: 700 }}>{fmt(info.count)} quesiti</span>
                      {info.size_mb ? <span> · {info.size_mb} MB</span> : null}
                      {info.categories?.length ? <span> · {info.categories.length} cat.</span> : null}
                    </>
                  ) : <span style={{ color: '#8b949e' }}>Non scaricato</span>}
                </div>
                {id !== 'all' && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '6px' }}>
                    {info.needs_refresh ? (
                      <span style={{ fontSize: '0.6rem', color: '#ffb86c', display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <AlertTriangle size={9} /> incompleta
                      </span>
                    ) : <span />}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDownload(id); }}
                      disabled={busy}
                      style={{
                        background: info.needs_refresh ? 'rgba(255,184,108,0.12)' : 'rgba(0,210,255,0.1)',
                        border: `1px solid ${info.needs_refresh ? 'rgba(255,184,108,0.4)' : 'rgba(0,210,255,0.3)'}`,
                        borderRadius: '5px', padding: '1px 7px',
                        color: info.needs_refresh ? '#ffb86c' : ACCENT,
                        fontSize: '0.58rem', fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
                      }}
                    >
                      {busy ? '⏳' : info.cached ? (info.needs_refresh ? 'Aggiorna' : 'Riscarica') : 'Scarica'}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ═══ Configura & Avvia ═══ */}
      <div style={{ ...card, display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Compass size={16} style={{ color: 'var(--accent)' }} /> Configura & Avvia
        </h3>

        {/* Riga 1: modello e copertura, larghezze fisse invece di auto-fit —
            l'auto-fit faceva saltare le colonne a ogni cambio di contenuto. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 1.1fr) minmax(240px, 1fr)', gap: '14px', alignItems: 'stretch' }}>
          <ModelPicker
            models={filteredModels}
            total={models.length}
            current={currentModel}
            ollamaUp={ollamaUp}
            search={modelSearch}
            open={modelOpen}
            onSearch={setModelSearch}
            onToggle={() => setModelOpen((v) => !v)}
            onPick={(id) => { setSelectedModel(id); setModelOpen(false); setModelSearch(''); }}
          />
          <CoveragePicker
            evalMode={evalMode}
            sampleCount={sampleCount}
            plannedItems={plannedItems}
            onMode={setEvalMode}
            onCount={setSampleCount}
          />
        </div>

        {/* Riga 2: come eseguire */}
        <ExecutionPicker
          mode={execMode}
          onMode={setExecMode}
          concurrency={effectiveConcurrency}
          measured={Boolean(capacity?.profile)}
          agents={capacity?.profile?.recommended_agents}
        />

        {/* Riga 3: motore parallelo */}
        <ParallelEngine
          model={selectedModel}
          capacity={capacity}
          engine={engine}
          probing={probing}
          probeLevel={probeLevel}
          busy={engineBusy}
          onProbe={handleProbeCapacity}
          onStartEndpoint={handleStartEndpoint}
          onStopEndpoint={handleStopEndpoint}
        />

        {/* Riga 4: riepilogo e lancio */}
        <div style={{
          ...panel, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: '16px', flexWrap: 'wrap', borderColor: canLaunch ? 'rgba(0,210,255,0.3)' : 'var(--border)',
        }}>
          <div style={{ display: 'flex', gap: '22px', flexWrap: 'wrap', fontSize: '0.72rem' }}>
            <Summary label="Modello" value={currentModel?.name || '—'} />
            <Summary label="Quesiti" value={fmt(plannedItems)} />
            <Summary label="In parallelo" value={`${effectiveConcurrency}x`}
              hint={execMode === 'single' ? 'singola' : (capacity?.profile ? 'misurato' : 'stimato')} />
            <Summary label="Durata stimata" value={estimate || '—'} />
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {hasActiveJobs && (
              <button onClick={handleCancelAll} style={{
                height: '40px', padding: '0 16px', border: 'none', borderRadius: '10px',
                background: 'linear-gradient(135deg, #ff5555 0%, #cc3333 100%)', color: '#fff',
                fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px',
              }}>
                <StopCircle size={15} /> Annulla
              </button>
            )}
            <button
              onClick={() => handleStart()}
              disabled={!canLaunch}
              style={{
                height: '40px', padding: '0 26px', border: 'none', borderRadius: '10px', color: '#fff',
                fontWeight: 700, fontSize: '0.82rem',
                background: canLaunch ? 'linear-gradient(135deg, #00d2ff 0%, #0072ff 100%)' : 'rgba(255,255,255,0.1)',
                cursor: canLaunch ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
              }}
            >
              {launching
                ? <><RefreshCw size={15} className="spin-icon" /> Avvio...</>
                : <><Play size={15} /> Avvia valutazione</>}
            </button>
          </div>
        </div>

        {plannedItems === 0 && (
          <div style={{ fontSize: '0.72rem', color: '#ffb86c', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={12} /> Scarica prima il dataset della suite selezionata.
          </div>
        )}
      </div>

      {/* Monitor job + ispezione */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(270px, 310px) 1fr', gap: '20px', alignItems: 'start' }}>
        <div style={{ ...card, padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '820px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={15} style={{ color: ACCENT }} /> Job ({jobs.length})
            </h3>
          </div>

          {jobs.length === 0 ? (
            <div style={{ padding: '30px 10px', textAlign: 'center', color: 'var(--text-dark)', fontSize: '0.78rem' }}>
              Nessun job eseguito.
            </div>
          ) : jobs.map((j) => {
            const isSelected = selectedJobId === j.id;
            const jm = j.metrics || {};
            const isActive = ACTIVE_STATUSES.includes(j.status);
            return (
              <div key={j.id} onClick={() => setSelectedJobId(j.id)} style={{
                background: isSelected ? 'rgba(0,210,255,0.12)' : 'rgba(10,12,26,0.6)',
                border: `1px solid ${isSelected ? ACCENT : 'var(--border)'}`,
                borderRadius: '10px', padding: '10px 12px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: '7px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {j.model}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: ACCENT, fontWeight: 600 }}>{j.suite_name || j.suite}</div>
                  </div>
                  <StatusPill job={j} />
                </div>

                {isActive && (
                  <div style={{ width: '100%', height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${j.progress || 0}%`, height: '100%',
                      background: j.status === 'paused' ? '#ffb86c' : ACCENT, transition: 'width 0.3s ease',
                    }} />
                  </div>
                )}

                <div style={{ fontSize: '0.66rem', color: 'var(--text-dark)' }}>
                  <span style={{ color: (jm.overall_score || 0) >= 50 ? 'var(--success)' : '#ff5555', fontWeight: 700 }}>
                    {jm.overall_score || 0}%
                  </span>
                  {' · '}{fmt(jm.tests_passed)}/{fmt(jm.tests_total)} pass
                  {jm.tests_review > 0 && <span style={{ color: '#ffb86c' }}> · {fmt(jm.tests_review)} rev.</span>}
                  {j.concurrency > 1 && <span> · {j.concurrency}x</span>}
                </div>

                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {j.status === 'running' && (
                    <button onClick={(e) => jobAction('/api/training/benchmark/pause', j.id, '⏸️ In pausa', e)}
                      style={{ ...btn(true, '#ffb86c'), fontSize: '0.58rem' }}>⏸️ Pausa</button>
                  )}
                  {j.status === 'paused' && (
                    <button onClick={(e) => jobAction('/api/training/benchmark/resume', j.id, '▶️ Ripresa', e)}
                      style={{ ...btn(true, '#3fb950'), fontSize: '0.58rem' }}>▶️ Riprendi</button>
                  )}
                  {isActive && (
                    <button onClick={(e) => jobAction('/api/training/benchmark/cancel', j.id, '🛑 Annullato', e)}
                      style={{ ...btn(true, '#ff5555'), fontSize: '0.58rem' }}>🛑 Ferma</button>
                  )}
                  {!isActive && (
                    <button onClick={(e) => { e.stopPropagation(); handleStart(j.model, j.suite); }}
                      disabled={launching} style={{ ...btn(true), fontSize: '0.58rem', display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <RotateCcw size={9} /> Riesegui
                    </button>
                  )}
                  <button onClick={(e) => jobAction('/api/training/benchmark/delete', j.id, '🗑️ Eliminato', e)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer', padding: '2px', marginLeft: 'auto' }}
                    title="Elimina job">
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Pannello di ispezione */}
        <div style={{ ...card, display: 'flex', flexDirection: 'column', gap: '14px', minHeight: '600px' }}>
          {!activeJob ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', color: 'var(--text-dark)', gap: '12px' }}>
              <Compass size={46} style={{ opacity: 0.3 }} />
              <div style={{ fontSize: '0.92rem', fontWeight: 600 }}>Nessuna valutazione selezionata</div>
            </div>
          ) : (
            <>
              <div style={{
                background: 'rgba(10,12,26,0.8)', border: '1px solid rgba(0,210,255,0.3)',
                borderRadius: '12px', padding: '13px 16px', display: 'flex',
                alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px',
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '9px', flexWrap: 'wrap' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text)' }}>{activeJob.model}</h3>
                    <span style={{ fontSize: '0.66rem', padding: '2px 8px', borderRadius: '6px', background: 'rgba(0,210,255,0.15)', color: ACCENT, fontWeight: 700 }}>
                      {activeJob.suite_name || activeJob.suite}
                    </span>
                    {repro.reproducible_hash && (
                      <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: '6px', background: 'rgba(63,185,80,0.15)', color: 'var(--success)', fontWeight: 600, fontFamily: 'monospace' }}>
                        {repro.reproducible_hash}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.69rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                    {new Date(activeJob.created_at).toLocaleString('it-IT')} · temp 0.0 · seed 42 ·
                    {' '}{repro.mode || '—'} · copertura {repro.dataset_coverage || '—'}
                    {activeJob.concurrency ? ` · ${activeJob.concurrency}x parallelo` : ''}
                    {activeJob.concurrency_source ? ` (${activeJob.concurrency_source})` : ''}
                    {activeJob.endpoints?.length > 1 ? ` · ${activeJob.endpoints.length} endpoint` : ''}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <button onClick={handleExportReport} style={{ ...btn(false), border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Download size={13} /> Report JSON
                  </button>
                  {reviewTotal > 0 && (
                    <button onClick={handleExportReview} style={{ ...btn(true, '#ffb86c'), display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <AlertTriangle size={13} /> Revisione ({fmt(reviewTotal)})
                    </button>
                  )}
                </div>
              </div>

              {activeJob.error && (
                <div style={{ background: 'rgba(255,85,85,0.1)', border: '1px solid rgba(255,85,85,0.35)', borderRadius: '10px', padding: '10px 14px', fontSize: '0.74rem', color: '#ff5555' }}>
                  {activeJob.error}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))', gap: '10px' }}>
                <Metric label="Score ufficiale" value={`${metrics.overall_score || 0}%`} color="var(--success)"
                  hint={`${fmt(metrics.tests_passed)}/${fmt(metrics.tests_total)} superati`} />
                <Metric label="Accuratezza sui decisi" value={`${metrics.decided_accuracy_pct || 0}%`} color={ACCENT}
                  hint={`su ${fmt(decidedTotal || (metrics.tests_passed || 0) + (metrics.tests_failed || 0))} decisi`} />
                <Metric label="Da rivedere" value={fmt(metrics.tests_review)} color="#ffb86c"
                  hint={`${metrics.review_pct || 0}% del totale`} />
                <Metric label="Throughput" value={`${metrics.tokens_per_sec || 0} tok/s`} color="#bc8cff"
                  hint={`${fmt(metrics.total_tokens)} token · ${fmt(metrics.avg_latency_ms)} ms medi`} />
              </div>

              {Object.keys(counts).length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {['pass', 'fail', 'ambiguous', 'unparsable', 'error'].filter((v) => counts[v]).map((v) => {
                    const s = VERDICT_STYLE[v];
                    return (
                      <div key={v} style={{
                        background: s.bg, border: `1px solid ${s.border}`, borderRadius: '6px',
                        padding: '3px 9px', fontSize: '0.67rem', fontWeight: 700, color: s.color,
                        display: 'flex', alignItems: 'center', gap: '5px',
                      }}>
                        <s.Icon size={11} /> {s.label}: {fmt(counts[v])}
                      </div>
                    );
                  })}
                </div>
              )}

              {jobSuites.length > 1 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {Object.entries(detail.suite_breakdown).map(([name, stats]) => {
                    const pct = stats.total ? Math.round((stats.passed / stats.total) * 100) : 0;
                    return (
                      <div key={name} style={{
                        background: 'rgba(10,12,26,0.7)', border: '1px solid var(--border)',
                        borderRadius: '6px', padding: '3px 9px', fontSize: '0.66rem', color: 'var(--text-dark)',
                      }}>
                        <b style={{ color: 'var(--text)' }}>{name}</b>: {stats.passed}/{stats.total} ({pct}%)
                        {stats.review > 0 && <span style={{ color: '#ffb86c' }}> · {stats.review} rev.</span>}
                      </div>
                    );
                  })}
                </div>
              )}

              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px',
                background: 'rgba(10,12,26,0.4)', border: '1px solid var(--border)',
                borderRadius: '10px', padding: '8px 12px', flexWrap: 'wrap',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '180px' }}>
                  <Search size={14} style={{ color: 'var(--text-dark)' }} />
                  <input type="text" value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
                    placeholder="Cerca quesito, categoria o risposta..."
                    style={{ width: '100%', background: 'none', border: 'none', color: 'var(--text)', fontSize: '0.76rem', outline: 'none' }} />
                  {searchInput && (
                    <button onClick={() => setSearchInput('')} style={{ background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer' }}>✕</button>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
                  <button onClick={() => setVerdictFilter('all')} style={btn(verdictFilter === 'all')}>
                    Tutti ({fmt(Object.values(counts).reduce((a, b) => a + b, 0))})
                  </button>
                  <button onClick={() => setVerdictFilter('pass')} style={btn(verdictFilter === 'pass', '#3fb950')}>
                    ✓ {fmt(counts.pass)}
                  </button>
                  <button onClick={() => setVerdictFilter('fail')} style={btn(verdictFilter === 'fail', '#ff5555')}>
                    ✕ {fmt(counts.fail)}
                  </button>
                  <button onClick={() => setVerdictFilter('review')} style={btn(verdictFilter === 'review', '#ffb86c')}>
                    ⚠ Da rivedere ({fmt(reviewTotal)})
                  </button>
                  {jobSuites.length > 1 && (
                    <select value={suiteFilter} onChange={(e) => setSuiteFilter(e.target.value)} style={{
                      background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border)',
                      color: 'var(--text)', borderRadius: '6px', fontSize: '0.7rem', padding: '3px 6px', cursor: 'pointer',
                    }}>
                      <option value="all">Tutte le suite</option>
                      {jobSuites.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', minHeight: '200px' }}>
                {detailLoading && !detail ? (
                  <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-dark)', fontSize: '0.78rem' }}>
                    <RefreshCw size={20} className="spin-icon" /> Caricamento...
                  </div>
                ) : !detail || detail.total === 0 ? (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dark)', fontSize: '0.78rem' }}>
                    {activeJob.status === 'preparing'
                      ? 'Preparazione del dataset in corso...'
                      : 'Nessun quesito corrisponde ai filtri selezionati.'}
                  </div>
                ) : (
                  <>
                    {detail.results.map((tr, idx) => (
                      <QuestionCard
                        key={`${tr.id}_${idx}`}
                        result={tr}
                        model={activeJob.model}
                        number={(detail.page - 1) * detail.page_size + idx + 1}
                      />
                    ))}

                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      background: 'rgba(10,12,26,0.85)', border: '1px solid rgba(0,210,255,0.3)',
                      borderRadius: '10px', padding: '8px 14px', flexWrap: 'wrap', gap: '10px',
                    }}>
                      <div style={{ fontSize: '0.71rem', color: 'var(--text-dark)' }}>
                        Quesiti <b style={{ color: 'var(--text)' }}>
                          {fmt((detail.page - 1) * detail.page_size + 1)}–{fmt(Math.min(detail.page * detail.page_size, detail.total))}
                        </b> di <b style={{ color: 'var(--text)' }}>{fmt(detail.total)}</b>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} style={{
                          background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border)',
                          color: 'var(--text)', borderRadius: '6px', fontSize: '0.7rem', padding: '2px 6px', cursor: 'pointer',
                        }}>
                          {[10, 15, 25, 50, 100].map((n) => <option key={n} value={n}>{n} / pagina</option>)}
                        </select>
                        <button disabled={detail.page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}
                          style={{ ...btn(true), opacity: detail.page <= 1 ? 0.4 : 1, cursor: detail.page <= 1 ? 'not-allowed' : 'pointer' }}>
                          ◄ Prec.
                        </button>
                        <span style={{ fontSize: '0.73rem', fontWeight: 800, color: 'var(--text)' }}>
                          {detail.page} / {detail.pages}
                        </span>
                        <button disabled={detail.page >= detail.pages} onClick={() => setPage((p) => p + 1)}
                          style={{ ...btn(true), opacity: detail.page >= detail.pages ? 0.4 : 1, cursor: detail.page >= detail.pages ? 'not-allowed' : 'pointer' }}>
                          Succ. ►
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Configurazione ───────────────────────────────────────────────────────────

function ModelPicker({ models, total, current, ollamaUp, search, open, onSearch, onToggle, onPick }) {
  return (
    <div style={{ ...panel, display: 'flex', flexDirection: 'column' }}>
      <div style={sectionTitle}><Cpu size={13} /> Modello da valutare</div>

      {!ollamaUp ? (
        <div style={{ fontSize: '0.74rem', color: '#ff5555', display: 'flex', gap: '6px', alignItems: 'center' }}>
          <AlertTriangle size={14} /> Ollama non raggiungibile.
        </div>
      ) : (
        <>
          {/* Un solo modello selezionato, mostrato come riga chiusa: l'elenco a
              pillole occupava mezza schermata e non diceva quale fosse attivo. */}
          <button
            type="button"
            onClick={onToggle}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px',
              background: 'rgba(0,210,255,0.1)', border: `1px solid ${ACCENT}`,
              borderRadius: '8px', padding: '9px 12px', cursor: 'pointer', width: '100%',
            }}
          >
            <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 700, color: ACCENT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
                {current?.name || 'Nessun modello'}
              </span>
              <span style={{ fontSize: '0.64rem', color: 'var(--text-dark)', fontFamily: 'monospace' }}>
                {current
                  ? [current.parameter_size, current.quantization, current.size_gb ? `${current.size_gb} GB` : '']
                    .filter(Boolean).join(' · ')
                  : 'installa un modello su Ollama'}
              </span>
            </span>
            <ChevronDown size={15} style={{ color: ACCENT, flexShrink: 0, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
          </button>

          {open && (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px',
                background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
                borderRadius: '7px', padding: '5px 9px',
              }}>
                <Search size={12} style={{ color: 'var(--text-dark)', flexShrink: 0 }} />
                <input
                  autoFocus type="text" value={search} onChange={(e) => onSearch(e.target.value)}
                  placeholder="Filtra fra i modelli installati..."
                  style={{ width: '100%', background: 'none', border: 'none', color: 'var(--text)', fontSize: '0.73rem', outline: 'none' }}
                />
              </div>
              <div style={{
                display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '6px',
                maxHeight: '190px', overflowY: 'auto',
              }}>
                {models.length === 0 ? (
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dark)', padding: '8px' }}>
                    Nessun modello corrisponde al filtro.
                  </div>
                ) : models.map((m) => (
                  <button
                    type="button" key={m.id} onClick={() => onPick(m.id)}
                    style={{
                      background: current?.id === m.id ? 'rgba(0,210,255,0.15)' : 'transparent',
                      border: 'none', borderRadius: '6px', padding: '5px 8px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '8px', textAlign: 'left',
                    }}
                  >
                    <span style={{
                      fontSize: '0.73rem', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      fontWeight: current?.id === m.id ? 700 : 500,
                      color: current?.id === m.id ? ACCENT : 'var(--text)',
                    }}>{m.name}</span>
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-dark)', fontFamily: 'monospace', flexShrink: 0 }}>
                      {[m.parameter_size, `${m.size_gb}GB`].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          <div style={{ marginTop: 'auto', paddingTop: '8px', fontSize: '0.64rem', color: 'var(--text-dark)' }}>
            {total} modelli generativi installati.
          </div>
        </>
      )}
    </div>
  );
}

function CoveragePicker({ evalMode, sampleCount, plannedItems, onMode, onCount }) {
  return (
    <div style={{ ...panel, display: 'flex', flexDirection: 'column' }}>
      <div style={sectionTitle}><Shield size={13} /> Copertura del dataset</div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button type="button" onClick={() => onMode('full')} style={{
          flex: 1, padding: '9px 10px', borderRadius: '8px', cursor: 'pointer',
          border: `1px solid ${evalMode === 'full' ? ACCENT : 'var(--border)'}`,
          background: evalMode === 'full' ? 'rgba(0,210,255,0.15)' : 'rgba(0,0,0,0.25)',
          color: evalMode === 'full' ? ACCENT : 'var(--text-dark)',
          fontSize: '0.74rem', fontWeight: 700,
        }}>🏆 Integrale 100%</button>
        <button type="button" onClick={() => onMode('sample')} style={{
          flex: 1, padding: '9px 10px', borderRadius: '8px', cursor: 'pointer',
          border: `1px solid ${evalMode === 'sample' ? 'var(--accent)' : 'var(--border)'}`,
          background: evalMode === 'sample' ? 'rgba(188,140,255,0.15)' : 'rgba(0,0,0,0.25)',
          color: evalMode === 'sample' ? 'var(--accent)' : 'var(--text-dark)',
          fontSize: '0.74rem', fontWeight: 700,
        }}>⚡ Campione</button>
      </div>

      {evalMode === 'sample' && (
        <div style={{ marginTop: '12px' }}>
          <label style={{ display: 'block', fontSize: '0.69rem', color: 'var(--text-dark)', marginBottom: '5px' }}>
            Quesiti campionati: <b style={{ color: 'var(--accent)' }}>{sampleCount}</b>
          </label>
          <input type="range" min="5" max="500" step="5" value={sampleCount}
            onChange={(e) => onCount(Number(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent)' }} />
        </div>
      )}

      <div style={{ marginTop: 'auto', paddingTop: '10px', fontSize: '0.68rem', color: 'var(--text-dark)' }}>
        {evalMode === 'full'
          ? <>Ogni quesito della suite: <b style={{ color: 'var(--text)' }}>{fmt(plannedItems)}</b>, con certificato SHA-256.</>
          : <>Campione deterministico (seed 42): <b style={{ color: 'var(--text)' }}>{fmt(plannedItems)}</b> quesiti.</>}
      </div>
    </div>
  );
}

function ExecutionPicker({ mode, onMode, concurrency, measured, agents }) {
  const options = [
    {
      id: 'single', icon: '🎯', title: 'Singola',
      desc: 'Una richiesta per volta. Massima riproducibilità, nessuna contesa sull\'hardware.',
      accent: '#8b949e',
    },
    {
      id: 'auto', icon: '⚡', title: 'Auto',
      desc: `Sfrutta l'hardware al massimo: ${concurrency} richieste insieme`
        + `${measured ? ', da capacità misurata' : ', da stima sulla VRAM'}.`,
      accent: ACCENT,
    },
  ];
  return (
    <div style={{ ...panel }}>
      <div style={sectionTitle}><Zap size={13} /> Modalità di esecuzione</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '10px' }}>
        {options.map((opt) => {
          const active = mode === opt.id;
          return (
            <button key={opt.id} type="button" onClick={() => onMode(opt.id)} style={{
              textAlign: 'left', cursor: 'pointer', borderRadius: '10px', padding: '11px 13px',
              border: `1px solid ${active ? opt.accent : 'var(--border)'}`,
              background: active ? `${opt.accent}1f` : 'rgba(0,0,0,0.25)',
              display: 'flex', flexDirection: 'column', gap: '4px',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <span style={{ fontSize: '1rem' }}>{opt.icon}</span>
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: active ? opt.accent : 'var(--text)' }}>
                  {opt.title}
                </span>
                {active && opt.id === 'auto' && (
                  <span style={{
                    marginLeft: 'auto', fontSize: '0.68rem', fontWeight: 800, color: opt.accent,
                    background: `${opt.accent}2b`, borderRadius: '5px', padding: '1px 7px',
                  }}>{concurrency}x</span>
                )}
              </span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dark)', lineHeight: 1.45 }}>{opt.desc}</span>
            </button>
          );
        })}
      </div>
      {mode === 'auto' && measured && agents ? (
        <div style={{ fontSize: '0.66rem', color: 'var(--text-dark)', marginTop: '8px' }}>
          {/* Due ottimi diversi: il benchmark vuole throughput, un agente vuole
              latenza bassa. Confonderli porta a dimensionare male entrambi. */}
          {concurrency}x massimizza il throughput del lotto. Per agenti interattivi,
          questa macchina ne serve bene <b style={{ color: 'var(--text)' }}>{agents}</b> insieme.
        </div>
      ) : null}
    </div>
  );
}

function ParallelEngine({ model, capacity, engine, probing, probeLevel, busy,
  onProbe, onStartEndpoint, onStopEndpoint }) {
  const [showTable, setShowTable] = useState(false);
  const est = capacity?.estimate || {};
  const profile = capacity?.profile || null;
  const gpus = est.gpus || engine?.gpus || [];
  const endpoints = engine?.endpoints || [];
  const managed = engine?.managed || [];
  const idle = est.idle_gpus || [];
  const levels = profile?.measurements || [];
  const staleProfile = profile && endpoints.filter((e) => e.reachable).length !== profile.endpoint_count;

  return (
    <div style={{ ...panel, display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ ...sectionTitle, marginBottom: 0 }}>
          <Gauge size={13} /> Motore parallelo
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          {levels.length > 0 && (
            <button onClick={() => setShowTable((v) => !v)} style={btn(showTable)}>
              {showTable ? 'Nascondi misure' : 'Misure'}
            </button>
          )}
          <button onClick={onProbe} disabled={probing || !model} style={{
            ...btn(true), fontWeight: 700, cursor: probing ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', gap: '5px',
          }}>
            {probing
              ? <><RefreshCw size={11} className="spin-icon" /> Misura{probeLevel ? ` ${probeLevel}x` : ''}...</>
              : <><Activity size={11} /> {profile ? 'Rimisura' : 'Misura capacità'}</>}
          </button>
        </div>
      </div>

      {/* Una scheda per GPU rilevata: l'elenco viene dall'hardware, quindi vale
          per una macchina con una scheda come per una con otto. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(215px, 1fr))', gap: '9px' }}>
        {gpus.length === 0 && (
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)' }}>
            Nessun acceleratore rilevato: i modelli girano su CPU.
          </div>
        )}
        {gpus.map((g) => {
          const active = g.has_endpoint;
          const usable = g.fits !== false;
          return (
            <div key={g.index} style={{
              background: active ? 'rgba(63,185,80,0.08)' : 'rgba(0,0,0,0.25)',
              border: `1px solid ${active ? 'rgba(63,185,80,0.4)' : 'var(--border)'}`,
              borderRadius: '9px', padding: '9px 11px',
              display: 'flex', flexDirection: 'column', gap: '5px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Server size={12} style={{ color: active ? 'var(--success)' : 'var(--text-dark)', flexShrink: 0 }} />
                <span style={{ fontSize: '0.73rem', fontWeight: 700, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  GPU {g.index} · {String(g.name).replace(/NVIDIA GeForce /, '')}
                </span>
              </div>
              <div style={{ fontSize: '0.64rem', color: 'var(--text-dark)', fontFamily: 'monospace' }}>
                {g.vram_free_gb} / {g.vram_total_gb} GB liberi
                {g.max_parallel ? ` · ${g.max_parallel} slot` : ''}
              </div>
              {active ? (
                <span style={{ fontSize: '0.62rem', color: 'var(--success)', fontWeight: 700 }}>● in uso</span>
              ) : usable ? (
                <button onClick={() => onStartEndpoint(g.index)} disabled={busy} style={{
                  ...btn(true, '#ffb86c'), fontSize: '0.62rem', fontWeight: 700,
                  display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center',
                  cursor: busy ? 'wait' : 'pointer',
                }}>
                  <Plus size={10} /> Attiva questa GPU
                </button>
              ) : (
                <span style={{ fontSize: '0.62rem', color: 'var(--text-dark)' }}>
                  modello troppo grande per questa scheda
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Perche' una GPU inattiva non basta accenderla dal nulla: un servitore
          Ollama ne indirizza una sola, quindi ne serve uno per scheda. */}
      {idle.length > 0 && (
        <div style={{
          background: 'rgba(255,184,108,0.1)', borderLeft: '3px solid #ffb86c',
          borderRadius: '4px', padding: '7px 10px', fontSize: '0.69rem', color: '#ffb86c', lineHeight: 1.5,
        }}>
          <AlertTriangle size={11} style={{ verticalAlign: '-1px', marginRight: '5px' }} />
          Un servitore Ollama carica il modello su una sola scheda. Attivando
          {idle.length > 1 ? ' le GPU ' : ' la GPU '}
          {idle.map((g) => g.index).join(', ')} il tetto passa da <b>{est.max_parallel_now}</b> a
          {' '}<b>{est.max_parallel_potential}</b> richieste in parallelo.
        </div>
      )}

      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '0.68rem', color: 'var(--text-dark)' }}>
        <span>Endpoint attivi: <b style={{ color: 'var(--text)' }}>{endpoints.filter((e) => e.reachable).length}</b></span>
        <span>Stima VRAM: <b style={{ color: 'var(--text)' }}>{est.max_parallel_now ?? '—'}x</b></span>
        <span>Misurato: <b style={{ color: profile ? 'var(--success)' : 'var(--text-dark)' }}>
          {profile ? `${profile.recommended_parallel}x` : 'mai'}
        </b>{profile ? ` · picco ${profile.peak_tokens_per_sec} tok/s` : ''}</span>
        {managed.length > 0 && managed.map((m) => (
          <button key={m.port} onClick={() => onStopEndpoint(m.port)} disabled={busy}
            style={{ ...btn(false, '#ff5555'), fontSize: '0.62rem', display: 'flex', alignItems: 'center', gap: '4px' }}
            title={`Ferma l'istanza su ${m.url}`}>
            <Power size={10} /> Ferma GPU {m.gpu_index}
          </button>
        ))}
      </div>

      {/* Una misura fatta con un numero diverso di endpoint non descrive piu'
          questa macchina: va segnalata, non riusata in silenzio. */}
      {staleProfile && (
        <div style={{ fontSize: '0.66rem', color: '#ffb86c' }}>
          {profile.endpoint_count
            ? `La misura risale a quando gli endpoint attivi erano ${profile.endpoint_count}, ora sono `
              + `${endpoints.filter((e) => e.reachable).length}: rimisura per aggiornarla.`
            : 'La misura risale a una configurazione diversa del motore: rimisura per aggiornarla.'}
        </div>
      )}

      {profile?.advice && (
        <div style={{ fontSize: '0.68rem', color: 'var(--text-dark)', lineHeight: 1.5 }}>
          {profile.advice}
        </div>
      )}

      {showTable && levels.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.68rem', minWidth: '470px' }}>
            <thead>
              <tr style={{ color: 'var(--text-dark)', textAlign: 'right' }}>
                <th style={{ textAlign: 'left', padding: '3px 6px', fontWeight: 600 }}>Parallele</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>tok/s</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>Accel.</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>Guadagno</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>Efficienza</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>Latenza</th>
                <th style={{ padding: '3px 6px', fontWeight: 600 }}>Err</th>
              </tr>
            </thead>
            <tbody>
              {levels.map((m) => {
                const best = m.concurrency === profile.recommended_parallel;
                return (
                  <tr key={m.concurrency} style={{
                    textAlign: 'right',
                    background: best ? 'rgba(63,185,80,0.1)' : 'transparent',
                    color: m.faster ? 'var(--text)' : 'var(--text-dark)',
                  }}>
                    <td style={{ textAlign: 'left', padding: '3px 6px', fontWeight: 700 }}>
                      {m.concurrency}x {best && <span style={{ color: 'var(--success)' }}>◀</span>}
                    </td>
                    <td style={{ padding: '3px 6px', fontFamily: 'monospace' }}>{m.aggregate_tokens_per_sec}</td>
                    <td style={{ padding: '3px 6px', fontFamily: 'monospace' }}>{m.speedup ? `${m.speedup}x` : '—'}</td>
                    <td style={{
                      padding: '3px 6px', fontFamily: 'monospace',
                      color: m.gain >= 0.10 ? 'var(--success)' : '#ff5555',
                    }}>{m.gain != null ? `${Math.round(m.gain * 100)}%` : '—'}</td>
                    <td style={{ padding: '3px 6px', fontFamily: 'monospace' }}>
                      {m.efficiency != null ? `${Math.round(m.efficiency * 100)}%` : '—'}
                    </td>
                    <td style={{ padding: '3px 6px', fontFamily: 'monospace' }}>{fmt(m.avg_latency_ms)} ms</td>
                    <td style={{ padding: '3px 6px', color: m.failed ? '#ff5555' : 'inherit' }}>{m.failed}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div style={{ fontSize: '0.63rem', color: 'var(--text-dark)', marginTop: '5px' }}>
            Guadagno = throughput in piu' rispetto al livello precedente; sotto il 10% salire
            non fa finire prima. Efficienza = accelerazione / richieste: sotto il 60% ogni
            richiesta aspetta le altre, quindi conta per gli agenti ma non per un lotto.
            {endpoints.filter((e) => e.reachable).length > 1
              && ` Misurato su ${endpoints.filter((e) => e.reachable).length} endpoint.`}
          </div>
        </div>
      )}
    </div>
  );
}

function Summary({ label, value, hint }) {
  return (
    <div>
      <div style={{ fontSize: '0.6rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '0.88rem', fontWeight: 800, color: 'var(--text)', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value}
      </div>
      {hint && <div style={{ fontSize: '0.6rem', color: 'var(--text-dark)' }}>{hint}</div>}
    </div>
  );
}

// ── Ispezione ────────────────────────────────────────────────────────────────

function StatusPill({ job }) {
  const map = {
    running: { text: `${job.progress || 0}%`, color: ACCENT, bg: 'rgba(0,210,255,0.2)', spin: true },
    preparing: { text: 'PREPARO', color: ACCENT, bg: 'rgba(0,210,255,0.2)', spin: true },
    cancelling: { text: 'FERMO...', color: '#ffb86c', bg: 'rgba(255,184,108,0.2)', spin: true },
    paused: { text: `⏸️ ${job.progress || 0}%`, color: '#ffb86c', bg: 'rgba(255,184,108,0.2)' },
    completed: { text: '✓ FATTO', color: 'var(--success)', bg: 'rgba(63,185,80,0.2)' },
    cancelled: { text: '🟡 ANNULLATO', color: '#ffb86c', bg: 'rgba(255,184,108,0.2)' },
    interrupted: { text: '⚠ INTERROTTO', color: '#ffb86c', bg: 'rgba(255,184,108,0.2)' },
    failed: { text: '🔴 FALLITO', color: '#ff5555', bg: 'rgba(255,85,85,0.2)' },
  };
  const s = map[job.status] || { text: job.status, color: 'var(--text-dark)', bg: 'rgba(255,255,255,0.06)' };
  return (
    <span style={{
      fontSize: '0.56rem', fontWeight: 700, padding: '2px 6px', borderRadius: '6px',
      background: s.bg, color: s.color, display: 'flex', alignItems: 'center', gap: '4px',
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      {s.spin && <RefreshCw size={9} className="spin-icon" />}{s.text}
    </span>
  );
}

function Metric({ label, value, color, hint }) {
  return (
    <div style={{ background: 'rgba(10,12,26,0.6)', border: '1px solid var(--border)', borderRadius: '10px', padding: '10px 12px' }}>
      <div style={{ fontSize: '0.6rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontSize: '1.25rem', fontWeight: 800, color, marginTop: '2px' }}>{value}</div>
      <div style={{ fontSize: '0.64rem', color: 'var(--text-dark)' }}>{hint}</div>
    </div>
  );
}

function QuestionCard({ result, model, number }) {
  const style = VERDICT_STYLE[result.verdict] || VERDICT_STYLE.fail;
  const parsed = result.parsed || {};
  const correct = (result.correct_choice || '').trim().toUpperCase();
  // La lettera scelta arriva già decisa dal parser del backend: rifarne
  // l'estrazione qui rischiava di mostrare un'opzione diversa dal verdetto.
  const chosen = parsed.status === 'resolved' ? (parsed.value || '').toUpperCase() : null;
  const candidates = (parsed.candidates || []).map((c) => String(c).toUpperCase());
  const compact = result.verdict === 'pass';

  return (
    <div style={{
      background: style.bg, border: `1px solid ${style.border}`, borderRadius: '10px',
      padding: compact ? '8px 12px' : '12px 14px', display: 'flex', flexDirection: 'column',
      gap: compact ? '5px' : '9px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', flexWrap: 'wrap' }}>
          <span style={{ color: style.color, display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 800, fontSize: '0.7rem' }}>
            <style.Icon size={13} /> {style.label}
          </span>
          <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(0,210,255,0.1)', color: ACCENT }}>
            #{number}
          </span>
          {result.suite_name && (
            <span style={{ fontSize: '0.63rem', color: 'var(--text-dark)', fontWeight: 600 }}>{result.suite_name}</span>
          )}
          {result.category && (
            <span style={{ fontSize: '0.63rem', color: 'var(--text-dark)' }}>· {result.category}</span>
          )}
          {parsed.confidence && parsed.confidence !== 'none' && (
            <span style={{ fontSize: '0.59rem', color: 'var(--text-dark)', opacity: 0.8 }}>
              · confidenza {CONFIDENCE_LABEL[parsed.confidence] || parsed.confidence}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'monospace', fontSize: '0.62rem' }}>
          <span style={{ color: ACCENT }}>⚡ {result.tokens_per_sec} tok/s</span>
          <span style={{ color: '#ffb86c' }}>⏱️ {fmt(result.latency_ms)} ms</span>
        </div>
      </div>

      {parsed.reason && result.verdict !== 'pass' && result.verdict !== 'fail' && (
        <div style={{
          background: 'rgba(0,0,0,0.25)', borderLeft: `3px solid ${style.color}`,
          borderRadius: '4px', padding: '6px 10px', fontSize: '0.69rem', color: style.color,
        }}>
          {parsed.reason}
          {candidates.length > 1 && (
            <span style={{ opacity: 0.85 }}> — candidati: {candidates.join(', ')}</span>
          )}
          {parsed.rejected?.length > 0 && (
            <span style={{ opacity: 0.7 }}> · scartati: {parsed.rejected.join(', ')}</span>
          )}
        </div>
      )}

      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text)', lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
        {result.prompt}
      </div>

      {result.options?.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '5px' }}>
          {result.options.map((opt, i) => {
            const match = opt.match(/^\s*\(?([A-Za-z0-9])[)\].:]/);
            const letter = (match ? match[1] : String.fromCharCode(65 + i)).toUpperCase();
            const isCorrect = letter === correct;
            const isChosen = chosen === letter;
            const isCandidate = !isChosen && candidates.includes(letter);

            let bg = 'rgba(10,12,26,0.6)';
            let border = 'rgba(255,255,255,0.08)';
            let color = 'var(--text-dark)';
            let badge = null;

            if (isCorrect) {
              bg = 'rgba(63,185,80,0.14)'; border = 'rgba(63,185,80,0.5)'; color = 'var(--success)';
              badge = <Badge color="var(--success)"><Check size={8} /> CORRETTA</Badge>;
            }
            if (isCandidate) {
              bg = 'rgba(255,184,108,0.12)'; border = 'rgba(255,184,108,0.45)'; color = '#ffb86c';
              badge = <Badge color="#ffb86c">🤖 CANDIDATA</Badge>;
            }
            if (isChosen) {
              const ok = result.verdict === 'pass';
              bg = ok ? 'rgba(63,185,80,0.22)' : 'rgba(255,85,85,0.15)';
              border = ok ? '#3fb950' : 'rgba(255,85,85,0.6)';
              color = ok ? '#3fb950' : '#ff5555';
              badge = <Badge color={color}>🤖 SCELTA {ok ? '(GIUSTA)' : '(ERRATA)'}</Badge>;
            }

            return (
              <div key={i} style={{
                background: bg, border: `1px solid ${border}`, borderRadius: '5px',
                padding: '5px 9px', fontSize: '0.72rem', color,
                fontWeight: (isCorrect || isChosen || isCandidate) ? 700 : 500,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px',
              }}>
                <span>{opt}</span>
                {badge}
              </div>
            );
          })}
        </div>
      )}

      {result.execution && (
        <div style={{
          background: 'rgba(10,12,26,0.8)', border: '1px solid var(--border)', borderRadius: '6px',
          padding: '6px 10px', fontSize: '0.69rem', color: 'var(--text-dark)',
          display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'monospace',
        }}>
          <Terminal size={11} style={{ color: style.color, flexShrink: 0 }} />
          <b style={{ color: style.color }}>{result.execution.status}</b>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {result.execution.detail}
          </span>
        </div>
      )}

      <div style={{
        background: 'rgba(10,12,26,0.7)', padding: compact ? '5px 9px' : '8px 12px',
        borderRadius: '6px', border: `1px solid ${style.border}`,
        maxHeight: compact ? '90px' : '320px', overflowY: 'auto',
      }}>
        <div style={{ fontSize: '0.58rem', fontWeight: 800, color: style.color, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '3px', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Cpu size={10} /> Risposta di {model}
        </div>
        <div style={{ fontSize: '0.73rem', color: 'var(--text)', fontFamily: 'monospace', whiteSpace: 'pre-wrap', lineHeight: 1.35 }}>
          {result.given_answer || result.error || '(nessuna risposta generata)'}
        </div>

        {/* La risposta attesa sta sotto quella del modello, non in alto a
            destra: lì veniva tagliata a 60 caratteri proprio sulle soluzioni
            lunghe, che sono quelle in cui serve leggerla per intero. */}
        {!result.options?.length && result.correct_answer && (
          <div style={{
            marginTop: '7px', paddingTop: '6px',
            borderTop: '1px dashed rgba(255,255,255,0.12)',
          }}>
            <div style={{
              fontSize: '0.58rem', fontWeight: 800, color: 'var(--success)',
              textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '3px',
              display: 'flex', alignItems: 'center', gap: '4px',
            }}>
              <Check size={10} /> Risposta attesa
              {result.correct_choice && (
                <span style={{ textTransform: 'none', color: 'var(--text-dim)', fontWeight: 600 }}>
                  — valore da estrarre: <b style={{ color: 'var(--success)' }}>{result.correct_choice}</b>
                </span>
              )}
            </div>
            <div style={{
              fontSize: '0.73rem', color: 'var(--text-dim)', fontFamily: 'monospace',
              whiteSpace: 'pre-wrap', lineHeight: 1.35,
            }}>
              {String(result.correct_answer)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Badge({ color, children }) {
  return (
    <span style={{
      fontSize: '0.55rem', fontWeight: 800, background: `${color}33`, color,
      padding: '1px 5px', borderRadius: '4px', border: `1px solid ${color}`,
      display: 'flex', alignItems: 'center', gap: '3px', whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      {children}
    </span>
  );
}
