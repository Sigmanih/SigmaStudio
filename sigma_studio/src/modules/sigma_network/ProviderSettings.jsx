import React, { useState, useEffect, useCallback } from 'react';
import {
  Server,
  Cpu,
  Save,
  CheckCircle,
  AlertCircle,
  Check,
  Zap,
  Activity,
  HardDrive,
  Clock,
  TrendingUp,
  Award,
  RefreshCw,
  Coins
} from 'lucide-react';

const ProviderSettings = ({ settings, onSaveSettings }) => {
  const [form, setForm] = useState({
    sharing_enabled: false,
    shared_models: [],
    rate_tokens_per_coin: 1000,
    max_tokens_per_request: 4096,
    max_concurrent: 3,
    max_requests_per_hour: 60,
    display_name: 'Sigma Peer',
  });

  const [localModels, setLocalModels] = useState([]);
  const [telemetry, setTelemetry] = useState(null);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [saving, setSaving] = useState(false);
  const [benchmarkingModel, setBenchmarkingModel] = useState(null);
  const [guardState, setGuardState] = useState({
    max_memory_percent: 88,
    local_user_priority: true,
  });

  // Carica modelli locali disponibili
  useEffect(() => {
    fetch('/api/sigma_network/local_models')
      .then(res => res.json())
      .then(data => setLocalModels(Array.isArray(data) ? data : []))
      .catch(err => console.error('Errore caricamento modelli locali', err));
  }, []);

  // Sincronizza settings in ingresso
  useEffect(() => {
    if (settings) {
      setForm(prev => ({
        ...prev,
        ...settings,
        shared_models: settings.shared_models || [],
      }));
    }
  }, [settings]);

  // Carica e aggiorna la telemetria live del provider
  const fetchTelemetry = useCallback(async () => {
    try {
      const res = await fetch('/api/sigma_network/provider/telemetry');
      if (res.ok) {
        const data = await res.json();
        setTelemetry(data);
        if (data.guard) {
          setGuardState({
            max_memory_percent: data.guard.max_memory_percent ?? 88,
            local_user_priority: data.guard.local_user_priority ?? true,
          });
        }
      }
    } catch (err) {
      console.warn('Impossibile recuperare la telemetria provider', err);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3500);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  const handleToggleModel = (modelId) => {
    setForm(prev => {
      const current = prev.shared_models || [];
      if (current.includes(modelId)) {
        return { ...prev, shared_models: current.filter(m => m !== modelId) };
      } else {
        return { ...prev, shared_models: [...current, modelId] };
      }
    });
  };

  const handleRunBenchmark = async (modelId) => {
    setBenchmarkingModel(modelId);
    try {
      const res = await fetch('/api/sigma_network/provider/benchmark', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId, test_tokens: 64 }),
      });
      if (res.ok) {
        await fetchTelemetry();
      }
    } catch (err) {
      console.error('Errore durante il benchmark hardware', err);
    } finally {
      setBenchmarkingModel(null);
    }
  };

  const handleUpdateGuard = async (newGuard) => {
    setGuardState(newGuard);
    try {
      await fetch('/api/sigma_network/provider/guard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newGuard),
      });
    } catch (err) {
      console.error('Errore aggiornamento Resource Guard', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);
    try {
      const res = await fetch('/api/sigma_network/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setSavedSuccess(true);
        if (onSaveSettings) onSaveSettings(form);
        setTimeout(() => setSavedSuccess(false), 3000);
        await fetchTelemetry();
      }
    } catch (err) {
      console.error('Errore salvataggio impostazioni', err);
    } finally {
      setSaving(false);
    }
  };

  const metrics = telemetry?.metrics || {
    total_requests_served: 0,
    total_tokens_served: 0,
    total_coins_earned: 0.0,
    average_tok_per_sec: 0.0,
    active_requests: 0,
    max_concurrent: form.max_concurrent || 3,
  };

  const sysMem = telemetry?.system_memory || { percent: 0, available_mb: 0, total_mb: 0 };
  const history = telemetry?.history || [];
  const benchmarks = telemetry?.benchmarks || {};

  const getMemoryColor = (percent) => {
    if (percent > 85) return '#ef4444';
    if (percent > 70) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="sn-provider-hub" style={{ maxWidth: '960px' }}>
      {/* 1. Header & Live Toggle Modalità Provider */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.7))',
        border: '1px solid rgba(0, 212, 255, 0.25)',
        borderRadius: '16px',
        padding: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
      }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{
            width: 50,
            height: 50,
            borderRadius: '12px',
            background: form.sharing_enabled ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: form.sharing_enabled ? '#34d399' : '#94a3b8',
            border: `1px solid ${form.sharing_enabled ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.08)'}`,
          }}>
            <Server size={26} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#f8fafc', fontWeight: 700 }}>
                P2P Inference Provider Hub
              </h2>
              {form.sharing_enabled ? (
                <span className="sn-badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <span className="sn-badge-pulse" /> ONLINE & CONDIVISO
                </span>
              ) : (
                <span className="sn-badge" style={{ background: 'rgba(100, 116, 139, 0.2)', color: '#94a3b8' }}>
                  STANDBY
                </span>
              )}
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
              Metti a disposizione i tuoi modelli locali per il cluster decentralizzato. Guadagni AiloCoin per ogni richiesta completata.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            const next = !form.sharing_enabled;
            setForm({ ...form, sharing_enabled: next });
          }}
          className={`sn-toggle-provider ${form.sharing_enabled ? 'active' : ''}`}
          style={{ padding: '10px 20px', fontSize: '0.9rem', fontWeight: 700 }}
        >
          <Server size={18} />
          <span>{form.sharing_enabled ? 'Disattiva Provider' : 'Attiva Provider'}</span>
        </button>
      </div>

      {/* 2. Live Operations Metrics Dashboard */}
      <div className="sn-stats-row">
        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <Zap size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{metrics.total_tokens_served.toLocaleString()}</div>
            <div className="sn-stat-label">Token Generati per la Rete</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc' }}>
            <Coins size={22} />
          </div>
          <div>
            <div className="sn-stat-val">+{Number(metrics.total_coins_earned).toFixed(3)} AILO</div>
            <div className="sn-stat-label">Ricavi Totali Guadagnati</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' }}>
            <Activity size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{metrics.average_tok_per_sec.toFixed(1)} <span style={{ fontSize: '0.8rem', fontWeight: 400 }}>tok/s</span></div>
            <div className="sn-stat-label">Throughput Medio</div>
          </div>
        </div>

        <div className="sn-stat-card">
          <div className="sn-stat-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' }}>
            <TrendingUp size={22} />
          </div>
          <div>
            <div className="sn-stat-val">{metrics.active_requests} / {metrics.max_concurrent}</div>
            <div className="sn-stat-label">Carico Richieste Concorrenti</div>
          </div>
        </div>
      </div>

      {/* 3. Smart Resource Guard & Health Panel */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <HardDrive size={18} color="#00d4ff" /> Smart Resource Guard (Protezione Hardware)
          </h3>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Previene il degrado delle prestazioni del tuo PC durante l'inferenza remota
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: 6 }}>
              <span style={{ color: '#cbd5e1' }}>Utilizzo RAM di Sistema:</span>
              <span style={{ fontWeight: 700, color: getMemoryColor(sysMem.percent) }}>
                {sysMem.percent}% ({Math.round(sysMem.total_mb - sysMem.available_mb)} MB / {Math.round(sysMem.total_mb)} MB)
              </span>
            </div>
            <div className="sn-meter-track">
              <div
                className="sn-meter-fill"
                style={{
                  width: `${Math.min(100, sysMem.percent)}%`,
                  backgroundColor: getMemoryColor(sysMem.percent)
                }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: '#cbd5e1' }}>Soglia Limite RAM Remote Call:</span>
              <span style={{ fontWeight: 700, color: '#00d4ff' }}>{guardState.max_memory_percent}%</span>
            </div>
            <input
              type="range"
              min="50"
              max="95"
              step="1"
              value={guardState.max_memory_percent}
              onChange={e => handleUpdateGuard({ ...guardState, max_memory_percent: parseInt(e.target.value) })}
              style={{ cursor: 'pointer', accentColor: '#00d4ff' }}
            />
          </div>
        </div>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: 8,
          borderTop: '1px solid rgba(255, 255, 255, 0.05)'
        }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={guardState.local_user_priority}
              onChange={e => handleUpdateGuard({ ...guardState, local_user_priority: e.target.checked })}
              style={{ width: 17, height: 17, cursor: 'pointer', accentColor: '#00d4ff' }}
            />
            <span style={{ fontSize: '0.84rem', color: '#f1f5f9', fontWeight: 500 }}>
              Priorità Utente Locale Assoluta (rifiuta richieste peer se l'IDE o la chat locale stanno generando)
            </span>
          </label>
        </div>
      </div>

      {/* 4. Modelli Condivisi & Profiling Hardware (QoS Tiering) */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Cpu size={18} /> Modelli Locali & Certificazione Prestazioni (QoS Tiering)
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
              Abilita i modelli che desideri offrire al cluster P2P ed esegui il benchmark per certificare velocità e tariffa consigliata.
            </p>
          </div>
          <button
            type="button"
            className="sn-btn-secondary"
            onClick={fetchTelemetry}
            title="Aggiorna telemetria"
          >
            <RefreshCw size={14} /> Aggiorna
          </button>
        </div>

        {localModels.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
            Nessun modello trovato nella cartella locale o nel motore. Installa o posiziona un modello GGUF/Gemma in Sigma Studio per iniziare.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {localModels.map(m => {
              const isShared = (form.shared_models || []).includes(m.id);
              const bench = benchmarks[m.id];
              const isBenchmarking = benchmarkingModel === m.id;

              const renderTierBadge = () => {
                if (!bench) return null;
                const tier = bench.qos_tier || 'Silver';
                let icon = '🥈';
                let cls = 'sn-tier-silver';
                if (tier === 'Diamond') {
                  icon = '💎';
                  cls = 'sn-tier-diamond';
                } else if (tier === 'Gold') {
                  icon = '🥇';
                  cls = 'sn-tier-gold';
                }
                return (
                  <span className={`sn-tier-badge ${cls}`}>
                    {icon} {tier} ({bench.tok_per_sec.toFixed(1)} tok/s)
                  </span>
                );
              };

              return (
                <div
                  key={m.id}
                  style={{
                    background: isShared ? 'rgba(0, 212, 255, 0.05)' : 'rgba(30, 41, 59, 0.4)',
                    border: `1px solid ${isShared ? 'rgba(0, 212, 255, 0.3)' : 'rgba(255, 255, 255, 0.08)'}`,
                    borderRadius: '12px',
                    padding: '14px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 16,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <input
                      type="checkbox"
                      checked={isShared}
                      onChange={() => handleToggleModel(m.id)}
                      style={{ width: 18, height: 18, cursor: 'pointer', accentColor: '#00d4ff' }}
                    />
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc' }}>
                          {m.name || m.id}
                        </span>
                        {renderTierBadge()}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
                        ID: <code style={{ color: '#cbd5e1' }}>{m.id}</code>
                        {m.size && ` • Dimensione: ${m.size}`}
                        {bench && (
                          <span style={{ color: '#34d399', marginLeft: 8 }}>
                            • Tariffa suggerita: {bench.suggested_rate} tok / AiloCoin
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {bench && bench.suggested_rate && (
                      <button
                        type="button"
                        className="sn-btn-secondary"
                        style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                        onClick={() => setForm({ ...form, rate_tokens_per_coin: bench.suggested_rate })}
                        title="Imposta questa tariffa come predefinita del nodo"
                      >
                        Applica Tariffa
                      </button>
                    )}
                    <button
                      type="button"
                      className="sn-btn-secondary"
                      disabled={isBenchmarking}
                      onClick={() => handleRunBenchmark(m.id)}
                    >
                      {isBenchmarking ? (
                        <>
                          <RefreshCw size={14} className="sn-spin" />
                          <span>Testing...</span>
                        </>
                      ) : (
                        <>
                          <Award size={14} color="#38bdf8" />
                          <span>Esegui Benchmark</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. Live Request Feed (Stream delle richieste servite) */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={18} color="#a855f7" /> Live Request Stream (Ultime Chiamate Servite)
          </h3>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            {history.length} transazioni di inferenza completate in questa sessione
          </span>
        </div>

        {history.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '0.82rem' }}>
            Nessuna richiesta remota servita finora. Quando altri peer sulla rete interrogheranno i tuoi modelli, vedrai qui i log in tempo reale con token e guadagno.
          </div>
        ) : (
          <div className="sn-table-container">
            <table className="sn-table">
              <thead>
                <tr>
                  <th>Orario</th>
                  <th>Modello</th>
                  <th>Token</th>
                  <th>Velocità</th>
                  <th>Latenza</th>
                  <th>Guadagno</th>
                  <th>Peer Chiamante</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 10).map((req, idx) => {
                  const dateStr = new Date(req.timestamp * 1000).toLocaleTimeString();
                  return (
                    <tr key={idx}>
                      <td style={{ color: '#94a3b8' }}>{dateStr}</td>
                      <td style={{ fontWeight: 600, color: '#f8fafc' }}>{req.model}</td>
                      <td>{req.tokens} tok</td>
                      <td>
                        <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                          {req.tok_per_sec.toFixed(1)} tok/s
                        </span>
                      </td>
                      <td>{req.duration_sec.toFixed(2)}s</td>
                      <td>
                        <span style={{ color: '#34d399', fontWeight: 700 }}>
                          +{req.earned_ailo.toFixed(4)} AILO
                        </span>
                      </td>
                      <td style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: '0.78rem' }}>
                        {req.caller_ip}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 6. Parametri Economici e Form di Salvataggio */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{
          background: 'rgba(15, 23, 42, 0.65)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '22px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 20
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 600 }}>Nome Visualizzato sulla Rete:</label>
            <input
              type="text"
              value={form.display_name}
              onChange={e => setForm({ ...form, display_name: e.target.value })}
              style={{
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f8fafc',
                fontSize: '0.85rem'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 600 }}>Tariffa (Token per 1 AiloCoin):</label>
            <input
              type="number"
              min="100"
              max="50000"
              value={form.rate_tokens_per_coin}
              onChange={e => setForm({ ...form, rate_tokens_per_coin: parseInt(e.target.value) || 1000 })}
              style={{
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f8fafc',
                fontSize: '0.85rem'
              }}
            />
            <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
              Esempio: a 1000 tok/Ailo, servire 500 token frutta 0.5 AiloCoin.
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 600 }}>Max Token per Richiesta:</label>
            <input
              type="number"
              min="256"
              max="16384"
              value={form.max_tokens_per_request}
              onChange={e => setForm({ ...form, max_tokens_per_request: parseInt(e.target.value) || 4096 })}
              style={{
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f8fafc',
                fontSize: '0.85rem'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 600 }}>Richieste Concorrenti Massime:</label>
            <input
              type="number"
              min="1"
              max="10"
              value={form.max_concurrent}
              onChange={e => setForm({ ...form, max_concurrent: parseInt(e.target.value) || 3 })}
              style={{
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f8fafc',
                fontSize: '0.85rem'
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 14 }}>
          {savedSuccess && (
            <span style={{ color: '#34d399', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <CheckCircle size={16} /> Impostazioni salvate e propagate istantaneamente via P2P!
            </span>
          )}
          <button
            type="submit"
            className="sn-btn-primary"
            disabled={saving}
            style={{ padding: '12px 28px', fontSize: '0.9rem' }}
          >
            <Save size={18} />
            <span>{saving ? 'Salvataggio...' : 'Salva Impostazioni Provider'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default ProviderSettings;
