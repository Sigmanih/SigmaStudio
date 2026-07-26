import React, { useState, useEffect, useCallback } from 'react';
import { Play, Activity, Zap, CheckCircle2, XCircle, Clock, Trash2, Cpu, Award, RefreshCw, BarChart2, Shield } from 'lucide-react';

export default function TrainingBenchmark({ addToast }) {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedSuite, setSelectedSuite] = useState('all');
  const [sampleCount, setSampleCount] = useState(5);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);

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
                if (addToast) addToast('✅ Test di Benchmark completato con successo!', 'success');
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
        if (addToast) addToast(`🚀 Benchmark avviato per ${selectedModel}`, 'info');
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

  return (
    <div style={{ padding: '20px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* ── Header Card ── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(30,34,60,0.8), rgba(15,18,35,0.9))',
        border: '1px solid rgba(0,210,255,0.2)',
        borderRadius: '16px',
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'linear-gradient(135deg, rgba(0,210,255,0.2), rgba(188,140,255,0.2))',
            border: '1px solid rgba(0,210,255,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Award size={24} style={{ color: '#00d2ff' }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)' }}>
              Model Benchmark & Evaluation Lab
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--text-dark)' }}>
              Testa la precisione matematica, velocità di generazione (tok/s), latenza e stabilità del codice per i tuoi modelli.
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

      {/* ── Configurator Panel ── */}
      <div style={{
        background: 'rgba(15,18,35,0.6)',
        border: '1px solid var(--border)',
        borderRadius: '16px',
        padding: '20px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '16px',
        alignItems: 'end',
      }}>
        {/* Model Select */}
        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)', marginBottom: '8px' }}>
            <Cpu size={14} style={{ inlineSize: '14px', marginRight: '6px', verticalAlign: 'middle' }} />
            Modello da Testare
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

        {/* Suite Select */}
        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)', marginBottom: '8px' }}>
            <BarChart2 size={14} style={{ inlineSize: '14px', marginRight: '6px', verticalAlign: 'middle' }} />
            Suite di Test
          </label>
          <select
            value={selectedSuite}
            onChange={(e) => setSelectedSuite(e.target.value)}
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
            <option value="all">🌐 Full Suite (Math + Code + Speed)</option>
            <option value="math">🧠 Math & Reasoning (MMLU/GSM8K)</option>
            <option value="code">💻 Code Generation & AST Syntax</option>
            <option value="speed">⚡ Speed & Throughput (Tok/s)</option>
          </select>
        </div>

        {/* Samples */}
        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dark)', marginBottom: '8px' }}>
            <Activity size={14} style={{ inlineSize: '14px', marginRight: '6px', verticalAlign: 'middle' }} />
            Campioni di Test: {sampleCount}
          </label>
          <input
            type="range"
            min="3"
            max="10"
            step="1"
            value={sampleCount}
            onChange={(e) => setSampleCount(Number(e.target.value))}
            disabled={isEvaluating}
            style={{ width: '100%', accentColor: 'var(--accent)' }}
          />
        </div>

        {/* Run Button */}
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
              transition: 'all 0.2s ease',
            }}
          >
            {isEvaluating ? (
              <>
                <RefreshCw size={16} className="spin-icon" /> Valutazione in corso...
              </>
            ) : (
              <>
                <Play size={16} /> Avvia Test Benchmark
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Active Benchmark Metrics Cards ── */}
      {activeJob && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Progress bar if running */}
          {activeJob.status === 'running' && (
            <div style={{ background: 'rgba(15,18,35,0.8)', border: '1px solid rgba(0,210,255,0.3)', borderRadius: '12px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text)', marginBottom: '8px' }}>
                <span>🚀 Esecuzione benchmark per <strong>{activeJob.model}</strong>...</span>
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
                Accuratezza Globale
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--success)', marginTop: '4px' }}>
                {metrics.overall_score || 0}%
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                {metrics.tests_passed || 0} / {metrics.tests_total || 0} test superati
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
                {metrics.total_tokens || 0} token generati totali
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
                Tempo medio risposta per prompt
              </div>
            </div>

            {/* Model Info */}
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '14px', padding: '16px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <Shield size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Modello In Prova
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)', marginTop: '6px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeJob.model}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--accent)', marginTop: '6px' }}>
                ID Job: {activeJob.id}
              </div>
            </div>
          </div>

          {/* Test Items Table */}
          {activeJob.test_results && activeJob.test_results.length > 0 && (
            <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '16px', padding: '20px' }}>
              <h3 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)' }}>
                📋 Dettaglio Risultati dei Test di Valutazione
              </h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', color: 'var(--text)' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-dark)', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Stato</th>
                      <th style={{ padding: '8px 12px' }}>Categoria</th>
                      <th style={{ padding: '8px 12px' }}>Prompt di Test</th>
                      <th style={{ padding: '8px 12px' }}>Velocità</th>
                      <th style={{ padding: '8px 12px' }}>Latenza</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeJob.test_results.map((tr, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '10px 12px' }}>
                          {tr.passed ? (
                            <span style={{ color: 'var(--success)', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                              <CheckCircle2 size={14} /> PASS
                            </span>
                          ) : (
                            <span style={{ color: '#ff5555', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                              <XCircle size={14} /> FAIL
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--accent)' }}>
                          {tr.category}
                        </td>
                        <td style={{ padding: '10px 12px', maxWidth: '300px' }}>
                          <div style={{ fontWeight: 600, color: 'var(--text)' }}>{tr.prompt}</div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dark)', marginTop: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {tr.response}
                          </div>
                        </td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#00d2ff' }}>
                          {tr.tokens_per_sec} tok/s
                        </td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#ffb86c' }}>
                          {tr.latency_ms} ms
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Benchmark History Table ── */}
      {jobs.length > 0 && (
        <div style={{ background: 'rgba(15,18,35,0.6)', border: '1px solid var(--border)', borderRadius: '16px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)' }}>
            📜 Storico Sessioni di Benchmark
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
                      {j.model}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-dark)' }}>
                      Data: {new Date(j.created_at).toLocaleString()} | Suite: {j.suite}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--success)' }}>
                      {j.metrics?.overall_score || 0}% Score
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#00d2ff' }}>
                      {j.metrics?.tokens_per_sec || 0} tok/s
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
