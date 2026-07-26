import React, { useState, useEffect, useCallback } from 'react';
import { Play, Activity, Zap, CheckCircle2, XCircle, Clock, Trash2, Cpu, Award, RefreshCw, BarChart2, Shield, HelpCircle, ChevronDown, ChevronUp, Code, BookOpen, Brain, Compass, AlertTriangle } from 'lucide-react';

const OFFICIAL_SUITES = [
  { id: 'all', name: '🌐 Tutti i Benchmark Ufficiali', desc: 'Esegue una selezione combinata da tutte le suite ufficiali', badge: 'FULL' },
  { id: 'mmlu', name: '🏆 MMLU', desc: 'Massive Multitask Language Understanding (57 materie: medicina, legge, fisica, CS...)', badge: '57 Materie' },
  { id: 'mmlu_pro', name: '🧠 MMLU-Pro', desc: 'Versione avanzata ad alto ragionamento con opzioni multiple e problemi complessi', badge: 'Ragionamento Hard' },
  { id: 'gsm8k', name: '🧮 GSM8K', desc: 'Grade School Math 8K: problemi matematici a parole con passaggi di ragionamento', badge: 'Math 8.5K' },
  { id: 'math', name: '📐 MATH', desc: 'Problemi matematici olimpici e universitari avanzati (algebra, calcolo, dimostrazioni)', badge: 'Olimpico' },
  { id: 'humaneval', name: '💻 HumanEval', desc: 'Completamento ed esecuzione di codice Python con verifica su test unitari', badge: 'Coding Eval' },
  { id: 'mbpp', name: '🐍 MBPP', desc: 'Mostly Basic Python Problems: sfide pratiche di programmazione in Python', badge: 'Python Base' },
  { id: 'arc', name: '🔬 ARC Science', desc: 'AI2 Reasoning Challenge: quesiti scientifici e di ragionamento empirico', badge: 'Scienze' },
  { id: 'hellaswag', name: '💡 HellaSwag', desc: 'Valutazione del buon senso e continuazione naturale degli eventi della vita', badge: 'Buon Senso' },
  { id: 'truthfulqa', name: '🛡️ TruthfulQA', desc: 'Rilevamento allucinazioni e misurazione della veridicità vs falsi miti', badge: 'Anti-Allucinazione' },
  { id: 'gpqa', name: '🎓 GPQA', desc: 'Graduate-Level Google-Proof Q&A (domande di livello specialistico universitario)', badge: 'Expert Level' },
  { id: 'bbh', name: '⚙️ BIG-Bench Hard', desc: '23 task complessi di ragionamento multi-step e logica simbolica', badge: 'BBH Multi-step' },
];

export default function TrainingBenchmark({ addToast }) {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedSuite, setSelectedSuite] = useState('all');
  const [sampleCount, setSampleCount] = useState(5);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [expandedItem, setExpandedItem] = useState(null);

  // Load available models and benchmark jobs
  const loadModelsAndJobs = useCallback(async () => {
    try {
      const [modelsRes, jobsRes] = await Promise.all([
        fetch('/api/training/benchmark/models'),
        fetch('/api/training/benchmark/jobs')
      ]);

      if (modelsRes.ok) {
        const mData = await modelsRes.json();
        setModels(mData || []);
        if (mData && mData.length > 0 && !selectedModel) {
          setSelectedModel(mData[0].id);
        }
      }

      if (jobsRes.ok) {
        const jData = await jobsRes.json();
        setJobs(jData || []);
        if (jData && jData.length > 0 && !selectedJob) {
          setSelectedJob(jData[0]);
        }
      }
    } catch (err) {
      console.error("Failed to load benchmark data:", err);
    }
  }, [selectedModel, selectedJob]);

  useEffect(() => {
    loadModelsAndJobs();
  }, []);

  // Poll active benchmark job if running
  useEffect(() => {
    let timer = null;
    const active = jobs.find(j => j.status === 'running');
    if (active) {
      setIsEvaluating(true);
      timer = setInterval(async () => {
        try {
          const res = await fetch('/api/training/benchmark/jobs');
          if (res.ok) {
            const data = await res.json();
            setJobs(data || []);
            const updatedActive = (data || []).find(j => j.id === active.id);
            if (updatedActive) {
              setSelectedJob(updatedActive);
              if (updatedActive.status === 'completed') {
                setIsEvaluating(false);
                if (addToast) addToast('✅ Benchmark Ufficiale completato con successo!', 'success');
              }
            }
          }
        } catch (e) {
          console.error(e);
        }
      }, 1500);
    } else {
      setIsEvaluating(false);
    }
    return () => { if (timer) clearInterval(timer); };
  }, [jobs, addToast]);

  // Start benchmark handler
  const handleStartBenchmark = async () => {
    if (!selectedModel) {
      if (addToast) addToast('⚠️ Seleziona un modello da testare', 'warning');
      return;
    }
    setIsEvaluating(true);
    try {
      const res = await fetch('/api/training/benchmark/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          suite: selectedSuite,
          samples: sampleCount
        })
      });
      const data = await res.json();
      if (data.success) {
        const suiteObj = OFFICIAL_SUITES.find(s => s.id === selectedSuite);
        if (addToast) addToast(`🚀 Benchmark Ufficiale [${suiteObj?.name || selectedSuite}] avviato per ${selectedModel}`, 'info');
        setSelectedJob(data.job);
        loadModelsAndJobs();
      } else {
        setIsEvaluating(false);
        if (addToast) addToast(`❌ Errore avvio benchmark: ${data.error}`, 'error');
      }
    } catch (err) {
      setIsEvaluating(false);
      if (addToast) addToast(`❌ Errore di rete: ${err.message}`, 'error');
    }
  };

  // Delete benchmark handler
  const handleDeleteJob = async (jobId) => {
    try {
      const res = await fetch('/api/training/benchmark/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: jobId })
      });
      if (res.ok) {
        if (addToast) addToast('🗑️ Benchmark eliminato dallo storico', 'info');
        const updated = jobs.filter(j => j.id !== jobId);
        setJobs(updated);
        if (selectedJob?.id === jobId) {
          setSelectedJob(updated[0] || null);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const activeJob = selectedJob || (jobs.length > 0 ? jobs[0] : null);
  const metrics = activeJob?.metrics || {};
  const currentSuiteObj = OFFICIAL_SUITES.find(s => s.id === selectedSuite);

  return (
    <div style={{ padding: '20px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* ── Header Banner ── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(30,34,60,0.85), rgba(15,18,35,0.95))',
        border: '1px solid rgba(0,210,255,0.25)',
        borderRadius: '16px',
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '52px', height: '52px', borderRadius: '14px',
            background: 'linear-gradient(135deg, rgba(0,210,255,0.25), rgba(188,140,255,0.25))',
            border: '1px solid rgba(0,210,255,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Award size={26} style={{ color: '#00d2ff' }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: 'var(--text)' }}>
              Official AI Benchmark & Evaluation Suite
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--text-dark)' }}>
              Esegui i benchmark standard internazionali (MMLU, MMLU-Pro, GSM8K, MATH, HumanEval, MBPP, ARC, HellaSwag, TruthfulQA, GPQA, BBH) con risposte visibili ed opzioni a confronto.
            </p>
          </div>
        </div>

        <button
          onClick={loadModelsAndJobs}
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px',
            padding: '8px 12px',
            color: 'var(--text)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '0.75rem',
          }}
        >
          <RefreshCw size={14} /> Aggiorna
        </button>
      </div>

      {/* ── Official Suite Selector Grid ── */}
      <div style={{
        background: 'rgba(15,18,35,0.6)',
        border: '1px solid var(--border)',
        borderRadius: '16px',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={16} style={{ color: 'var(--accent)' }} /> Selezione Benchmark Ufficiale (11 Test Standard)
          </h3>
          <span style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600 }}>
            {currentSuiteObj?.name}
          </span>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
          maxHeight: '260px',
          overflowY: 'auto',
          paddingRight: '4px',
        }}>
          {OFFICIAL_SUITES.map(s => (
            <div
              key={s.id}
              onClick={() => !isEvaluating && setSelectedSuite(s.id)}
              style={{
                background: selectedSuite === s.id ? 'rgba(0,210,255,0.12)' : 'rgba(10,12,26,0.6)',
                border: `1px solid ${selectedSuite === s.id ? 'rgba(0,210,255,0.4)' : 'var(--border)'}`,
                borderRadius: '12px',
                padding: '12px 14px',
                cursor: isEvaluating ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: selectedSuite === s.id ? '#00d2ff' : 'var(--text)' }}>
                    {s.name}
                  </span>
                  <span style={{
                    fontSize: '0.62rem', fontWeight: 700,
                    padding: '2px 6px', borderRadius: '6px',
                    background: selectedSuite === s.id ? 'rgba(0,210,255,0.2)' : 'rgba(255,255,255,0.06)',
                    color: selectedSuite === s.id ? '#00d2ff' : 'var(--text-dark)',
                  }}>
                    {s.badge}
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dark)', lineHeight: 1.4 }}>
                  {s.desc}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Configuration Toolbar */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginTop: '8px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          alignItems: 'end',
        }}>
          {/* Model */}
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)', marginBottom: '8px' }}>
              <Cpu size={14} style={{ inlineSize: '14px', marginRight: '6px', verticalAlign: 'middle' }} />
              Modello da Valutare
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isEvaluating}
              style={{
                width: '100%',
                background: 'rgba(10,12,26,0.8)',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '10px 14px',
                color: 'var(--text)',
                fontSize: '0.85rem',
                outline: 'none',
              }}
            >
              {models.map(m => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.provider} — {m.size_gb} GB)
                </option>
              ))}
            </select>
          </div>

          {/* Sample count */}
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)', marginBottom: '8px' }}>
              <Activity size={14} style={{ inlineSize: '14px', marginRight: '6px', verticalAlign: 'middle' }} />
              Campioni per Benchmark: {sampleCount}
            </label>
            <input
              type="range"
              min="2"
              max="10"
              step="1"
              value={sampleCount}
              onChange={(e) => setSampleCount(Number(e.target.value))}
              disabled={isEvaluating}
              style={{ width: '100%', accentColor: 'var(--accent)' }}
            />
          </div>

          {/* Run button */}
          <div>
            <button
              onClick={handleStartBenchmark}
              disabled={isEvaluating || !selectedModel}
              style={{
                width: '100%',
                height: '42px',
                background: isEvaluating
                  ? 'rgba(255,255,255,0.1)'
                  : 'linear-gradient(135deg, #00d2ff 0%, #0072ff 100%)',
                border: 'none',
                borderRadius: '10px',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: isEvaluating ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                boxShadow: isEvaluating ? 'none' : '0 4px 20px rgba(0,210,255,0.3)',
              }}
            >
              {isEvaluating ? (
                <>
                  <RefreshCw size={16} className="spin-icon" /> Valutazione Ufficiale in corso...
                </>
              ) : (
                <>
                  <Play size={16} /> Avvia Benchmark Ufficiale
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ── Active Benchmark Overview Cards ── */}
      {activeJob && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Progress bar if running */}
          {activeJob.status === 'running' && (
            <div style={{ background: 'rgba(15,18,35,0.8)', border: '1px solid rgba(0,210,255,0.3)', borderRadius: '12px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text)', marginBottom: '8px' }}>
                <span>🚀 Esecuzione benchmark <strong>{activeJob.suite_name}</strong> per <strong>{activeJob.model}</strong>...</span>
                <span>{activeJob.progress}%</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{
                  width: `${activeJob.progress}%`, height: '100%',
                  background: 'linear-gradient(90deg, #00d2ff, #bc8cff)',
                  transition: 'width 0.4s ease'
                }} />
              </div>
            </div>
          )}

          {/* Cards Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
          }}>
            {/* Score */}
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Punteggio Benchmark
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--success)', marginTop: '4px' }}>
                {activeJob.suite_name} = {metrics.overall_score || 0}%
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                {metrics.tests_passed || 0} / {metrics.tests_total || 0} quesiti superati
              </div>
            </div>

            {/* Speed */}
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Zap size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Throughput Generazione
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#00d2ff', marginTop: '4px' }}>
                {metrics.tokens_per_sec || 0} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>tok/s</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                {metrics.total_tokens || 0} token totali
              </div>
            </div>

            {/* Latency */}
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Clock size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Latenza Media
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#ffb86c', marginTop: '4px' }}>
                {metrics.avg_latency_ms || 0} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>ms</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                Tempo di risposta per quesito
              </div>
            </div>

            {/* Model Info */}
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Shield size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Modello Testato
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)', marginTop: '6px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeJob.model}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent)', marginTop: '6px' }}>
                Suite: {activeJob.suite_name}
              </div>
            </div>
          </div>

          {/* ── Detailed Questions & Responses Table (CON OPZIONI E RISPOSTE VISIBILI) ── */}
          {activeJob.test_results && activeJob.test_results.length > 0 && (
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '16px', padding: '20px' }}>
              <h3 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BookOpen size={16} style={{ color: 'var(--accent)' }} />
                Dettaglio Quesiti, Opzioni Disponibili e Risposte Date dal Modello
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {activeJob.test_results.map((tr, idx) => {
                  const isExpanded = expandedItem === idx;
                  return (
                    <div
                      key={idx}
                      style={{
                        background: tr.passed ? 'rgba(63,185,80,0.04)' : 'rgba(255,85,85,0.04)',
                        border: `1px solid ${tr.passed ? 'rgba(63,185,80,0.2)' : 'rgba(255,85,85,0.2)'}`,
                        borderRadius: '12px',
                        padding: '14px 16px',
                      }}
                    >
                      {/* Summary Row */}
                      <div
                        onClick={() => setExpandedItem(isExpanded ? null : idx)}
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          {tr.passed ? (
                            <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 700, fontSize: '0.85rem' }}>
                              <CheckCircle2 size={16} /> PASS
                            </span>
                          ) : (
                            <span style={{ color: '#ff5555', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 700, fontSize: '0.85rem' }}>
                              <XCircle size={16} /> FAIL
                            </span>
                          )}

                          <span style={{
                            fontSize: '0.7rem', fontWeight: 700,
                            padding: '2px 8px', borderRadius: '6px',
                            background: 'rgba(0,210,255,0.1)', color: '#00d2ff'
                          }}>
                            {tr.suite_name || tr.suite}
                          </span>

                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)' }}>
                            {tr.category}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                          <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#00d2ff' }}>
                            {tr.tokens_per_sec} tok/s
                          </span>
                          <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#ffb86c' }}>
                            {tr.latency_ms} ms
                          </span>
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </div>
                      </div>

                      {/* Prompt Title */}
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)', marginTop: '8px' }}>
                        Quesito #{idx + 1}: {tr.prompt}
                      </div>

                      {/* Expanded Details: Opzioni Disponibili + Risposta Data + Risposta Attesa */}
                      <div style={{
                        marginTop: '12px',
                        paddingTop: '12px',
                        borderTop: '1px dashed rgba(255,255,255,0.08)',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                        gap: '16px',
                      }}>
                        {/* Opzioni Disponibili */}
                        <div style={{ background: 'rgba(10,12,26,0.6)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-dark)', textTransform: 'uppercase', marginBottom: '6px' }}>
                            📋 Opzioni Disponibili nel Test:
                          </div>
                          {tr.options && tr.options.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {tr.options.map((opt, oIdx) => (
                                <div key={oIdx} style={{ fontSize: '0.78rem', color: opt.includes(tr.correct_choice) ? 'var(--success)' : 'var(--text)' }}>
                                  {opt}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-dark)' }}>Formato a risposta aperta / script</div>
                          )}
                        </div>

                        {/* Risposta Data dal Modello */}
                        <div style={{ background: 'rgba(10,12,26,0.6)', padding: '12px', borderRadius: '8px', border: `1px solid ${tr.passed ? 'rgba(63,185,80,0.3)' : 'rgba(255,85,85,0.3)'}` }}>
                          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: tr.passed ? 'var(--success)' : '#ff5555', textTransform: 'uppercase', marginBottom: '6px' }}>
                            🤖 Risposta Data dal Modello ({activeJob.model}):
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text)', whiteSpace: 'pre-wrap', maxHeight: '160px', overflowY: 'auto', fontFamily: 'monospace' }}>
                            {tr.given_answer}
                          </div>
                        </div>

                        {/* Risposta Corretta Attesa */}
                        <div style={{ background: 'rgba(10,12,26,0.6)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(63,185,80,0.3)' }}>
                          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--success)', textTransform: 'uppercase', marginBottom: '6px' }}>
                            ✅ Risposta Attesa / Soluzione Corretta:
                          </div>
                          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--success)' }}>
                            {tr.correct_answer}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Benchmark History Table ── */}
      {jobs.length > 0 && (
        <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '16px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)' }}>
            📜 Storico Valutazioni Benchmark Ufficiali
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {jobs.map(j => (
              <div
                key={j.id}
                onClick={() => setSelectedJob(j)}
                style={{
                  background: selectedJob?.id === j.id ? 'rgba(0,210,255,0.08)' : 'rgba(10,12,26,0.6)',
                  border: `1px solid ${selectedJob?.id === j.id ? 'rgba(0,210,255,0.3)' : 'var(--border)'}`,
                  borderRadius: '10px',
                  padding: '12px 16px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Cpu size={16} style={{ color: 'var(--accent)' }} />
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text)' }}>
                      {j.model} — <span style={{ color: '#00d2ff' }}>{j.suite_name || j.suite}</span>
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)' }}>
                      Data: {new Date(j.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--success)' }}>
                      {j.suite_name || j.suite} = {j.metrics?.overall_score || 0}%
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#00d2ff' }}>
                      {j.metrics?.tokens_per_sec || 0} tok/s | {j.metrics?.tests_passed || 0}/{j.metrics?.tests_total || 0} Pass
                    </div>
                  </div>

                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteJob(j.id); }}
                    style={{
                      background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer',
                      padding: '4px', borderRadius: '4px',
                    }}
                    title="Elimina Benchmark"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
