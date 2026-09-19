import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Cpu,
  Layers,
  Database,
  Activity,
  Zap,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  HardDrive
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

/**
 * RustTelemetryPanel — Telemetria in tempo reale del Micro-Kernel Nativo Rust & Scheduler Continuous Batching.
 *
 * Interroga ciclicamente GET /api/engine/rust/metrics per visualizzare lo stato dello scheduler,
 * l'efficienza della Radix Tree Paged KV-Cache e l'allocazione Dual-GPU/RAM.
 */
export default function RustTelemetryPanel({ compact = false }) {
  const { theme } = useApp ? useApp() : { theme: 'dark' };
  const isLight = theme === 'light';

  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const isMountedRef = useRef(true);

  const fetchMetrics = useCallback(async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    try {
      const res = await fetch('/api/engine/rust/metrics');
      if (!isMountedRef.current) return;

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (isMountedRef.current) {
        setMetrics(data);
        setErrorMsg(data.status === 'unavailable' ? (data.error || 'Motore Rust in standby') : null);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMsg(err.message || 'Disconnesso');
        setMetrics((prev) => prev ? { ...prev, status: 'unavailable' } : { status: 'unavailable' });
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        if (isManual) setIsRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    fetchMetrics();
    const timer = setInterval(() => {
      fetchMetrics(false);
    }, 2000);

    return () => {
      isMountedRef.current = false;
      clearInterval(timer);
    };
  }, [fetchMetrics]);

  // Design tokens & palette
  const cardBg = isLight ? '#ffffff' : 'rgba(13, 16, 25, 0.75)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#0f172a' : '#f8fafc';
  const textMuted = isLight ? '#64748b' : '#94a3b8';
  const innerCardBg = isLight ? '#f8fafc' : 'rgba(255, 255, 255, 0.03)';
  const innerBorder = isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.05)';

  const isOnline = metrics?.status === 'ok';
  const scheduler = metrics?.scheduler || {};
  const kvCache = metrics?.kv_cache || {};
  const hardware = metrics?.hardware || {};

  // `null` significa «non misurato», e va scritto. Prima ogni campo assente
  // diventava uno zero o un valore di ripiego — 2048 pagine, 96 GB di RAM,
  // due schede NVIDIA per nome — e il pannello sembrava vivo su qualunque
  // macchina, dicendo sempre le stesse cifre.
  const nd = (v) => (v === null || v === undefined ? null : v);
  const testo = (v, formatta) => (nd(v) === null ? 'non disponibile' : formatta(v));

  const pagesAlloc = nd(kvCache.pages_allocated);
  const pagesTotal = nd(kvCache.pages_total);
  const pagesPct =
    pagesAlloc !== null && pagesTotal
      ? Math.min(100, Math.round((pagesAlloc / pagesTotal) * 100))
      : null;
  const hitRatePct =
    nd(kvCache.radix_hit_rate) === null ? null : Math.round(kvCache.radix_hit_rate * 100);

  const gpus = Array.isArray(hardware.gpus) ? hardware.gpus : [];
  const ram = hardware.ram || {};
  const vramTotaleGb = gpus.reduce(
    (somma, g) => (g.mem_total_mb ? somma + g.mem_total_mb / 1024 : somma),
    0
  );

  return (
    <div
      style={{
        background: cardBg,
        border: cardBorder,
        borderRadius: '14px',
        padding: compact ? '16px' : '22px',
        color: textPrimary,
        boxShadow: isLight ? '0 4px 18px rgba(0,0,0,0.04)' : '0 8px 32px rgba(0,0,0,0.35)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px'
      }}
    >
      {/* Header con Badge stato e refresh manuale */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: isOnline ? 'rgba(0, 242, 254, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              color: isOnline ? '#00f2fe' : '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: `1px solid ${isOnline ? 'rgba(0, 242, 254, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
            }}
          >
            <Zap size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.01em' }}>
                Micro-Kernel Rust & Scheduler
              </span>
              <span
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  padding: '2px 8px',
                  borderRadius: '20px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  background: isOnline ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                  color: isOnline ? '#10b981' : '#f59e0b',
                  border: `1px solid ${isOnline ? 'rgba(16, 185, 129, 0.35)' : 'rgba(245, 158, 11, 0.35)'}`,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: isOnline ? '#10b981' : '#f59e0b'
                  }}
                />
                {isOnline ? 'ONLINE • PORTA 8090' : 'STANDBY / DISCONNESSO'}
              </span>
            </div>
            <div style={{ fontSize: '0.76rem', color: textMuted, marginTop: '2px' }}>
              Continuous Batching nativo, zero-copy KV Radix Tree e sharding asimmetrico Dual-GPU
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {lastUpdated && (
            <span style={{ fontSize: '0.72rem', color: textMuted, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} /> {lastUpdated}
            </span>
          )}
          <button
            type="button"
            onClick={() => fetchMetrics(true)}
            disabled={isRefreshing}
            style={{
              background: innerCardBg,
              border: innerBorder,
              color: textPrimary,
              borderRadius: '8px',
              padding: '6px 10px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <RefreshCw size={13} style={{ animation: isRefreshing ? 'spin 1s linear infinite' : 'none' }} />
            Aggiorna
          </button>
        </div>
      </div>

      {/* Banner di avviso se il motore non è raggiungibile */}
      {!isOnline && (
        <div
          style={{
            background: isLight ? '#fef3c7' : 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            borderRadius: '10px',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            fontSize: '0.82rem',
            color: isLight ? '#92400e' : '#fcd34d'
          }}
        >
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>Micro-kernel nativo Rust in standby sulla porta 8090.</strong>
            <div style={{ opacity: 0.85, fontSize: '0.75rem', marginTop: '2px' }}>
              {errorMsg ? `Stato del servizio: ${errorMsg}. ` : ''}
              Il router Python resta pronto e interroga automaticamente il container dev / demone locale ogni 2s.
            </div>
          </div>
        </div>
      )}

      {/* Grid delle tre macro-sezioni: Scheduler, KV-Cache, Dual-GPU */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '14px'
        }}
      >
        {/* Sezione 1: Continuous Batching Scheduler */}
        <div
          style={{
            background: innerCardBg,
            border: innerBorder,
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '0.88rem' }}>
              <Activity size={16} color="#10b981" />
              <span>Continuous Batching Scheduler</span>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                color: '#10b981',
                background: 'rgba(16, 185, 129, 0.1)',
                padding: '2px 6px',
                borderRadius: '6px',
                fontWeight: 700
              }}
            >
              Nativo Lock-Free
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div style={{ padding: '8px 10px', borderRadius: '8px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>Batch Formati</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#10b981', marginTop: '2px' }}>
                {isOnline ? (scheduler.batch_count?.toLocaleString() || '0') : '—'}
              </div>
            </div>

            <div style={{ padding: '8px 10px', borderRadius: '8px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>Latenza Media</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#00f2fe', marginTop: '2px' }}>
                {isOnline ? testo(scheduler.avg_latency_ms, (v) => `${v} ms`) : '—'}
              </div>
            </div>

            <div style={{ padding: '8px 10px', borderRadius: '8px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>Coda Pendente</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f59e0b', marginTop: '2px' }}>
                {isOnline ? testo(scheduler.queue_depth, (v) => String(v)) : '—'}
              </div>
            </div>

            <div style={{ padding: '8px 10px', borderRadius: '8px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.2)' }}>
              <div style={{ fontSize: '0.7rem', color: textMuted }}>Token / Processati</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#bc8cff', marginTop: '2px' }}>
                {isOnline ? (scheduler.total_processed?.toLocaleString() || '0') : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Sezione 2: Radix Tree Paged KV-Cache */}
        <div
          style={{
            background: innerCardBg,
            border: innerBorder,
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '0.88rem' }}>
              <Layers size={16} color="#00f2fe" />
              <span>Radix Tree Paged KV-Cache</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {kvCache.system_prompt_reuse ? (
                <span
                  style={{
                    fontSize: '0.68rem',
                    color: '#10b981',
                    background: 'rgba(16, 185, 129, 0.1)',
                    padding: '2px 6px',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px'
                  }}
                >
                  <CheckCircle2 size={11} /> Prompt Reuse
                </span>
              ) : null}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', marginBottom: '4px' }}>
                <span style={{ color: textMuted }}>Prefix Hit Rate:</span>
                <span style={{ fontWeight: 700, color: hitRatePct >= 90 ? '#10b981' : '#00f2fe' }}>
                  {isOnline ? testo(hitRatePct, (v) => `${v}%`) : '—'}
                </span>
              </div>
              <div
                style={{
                  height: '6px',
                  borderRadius: '3px',
                  background: isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)',
                  overflow: 'hidden'
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${isOnline && hitRatePct !== null ? hitRatePct : 0}%`,
                    background: 'linear-gradient(90deg, #00f2fe, #10b981)',
                    transition: 'width 0.3s ease'
                  }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', marginBottom: '4px' }}>
                <span style={{ color: textMuted }}>Pagine Memoria Paged:</span>
                <span style={{ fontWeight: 600 }}>
                  {isOnline && pagesTotal
                    ? `${pagesAlloc} / ${pagesTotal} (${pagesPct}%)`
                    : 'non disponibile'}
                </span>
              </div>
              <div
                style={{
                  height: '6px',
                  borderRadius: '3px',
                  background: isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)',
                  overflow: 'hidden'
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${isOnline && pagesPct !== null ? pagesPct : 0}%`,
                    background: '#bc8cff',
                    transition: 'width 0.3s ease'
                  }}
                />
              </div>
            </div>

            <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px', lineHeight: 1.4 }}>
              Zero overhead di frammentazione grazie all'allocazione unificata in blocchi da 16 token.
            </div>
          </div>
        </div>

        {/* Sezione 3: Dual-GPU & Hardware */}
        <div
          style={{
            background: innerCardBg,
            border: innerBorder,
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '0.88rem' }}>
              <Cpu size={16} color="#bc8cff" />
              <span>Dual-GPU & Host Memory</span>
            </div>
            <span style={{ fontSize: '0.7rem', color: textMuted }}>
              {vramTotaleGb > 0
                ? `VRAM Totale: ${Math.round(vramTotaleGb)} GB`
                : 'VRAM: non disponibile'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Le schede rilevate. Nessuna e' un esito legittimo: su
                Raspberry Pi 5 non ce ne sono, e il pannello deve dirlo
                invece di disegnarne due che non esistono. */}
            {gpus.length === 0 && (
              <div style={{ padding: '6px 8px', borderRadius: '6px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.15)' }}>
                <span style={{ fontSize: '0.72rem', color: textMuted }}>
                  Nessuna GPU rilevata dal kernel
                </span>
              </div>
            )}
            {gpus.map((g, i) => (
              <div
                key={g.name || i}
                style={{ padding: '6px 8px', borderRadius: '6px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.15)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                  <span style={{ fontWeight: 600 }}>{g.name || `GPU ${i}`}</span>
                  <span style={{ color: i === 0 ? '#00f2fe' : '#bc8cff' }}>
                    {g.mem_used_mb && g.mem_total_mb
                      ? `${Math.round((g.mem_used_mb / 1024) * 10) / 10} / ${Math.round(g.mem_total_mb / 1024)} GB`
                      : 'memoria non misurata'}
                  </span>
                </div>
              </div>
            ))}

            {/* RAM Host */}
            <div style={{ padding: '6px 8px', borderRadius: '6px', background: isLight ? '#f1f5f9' : 'rgba(0,0,0,0.15)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem' }}>
                <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <HardDrive size={12} /> RAM Host:
                </span>
                <span>
                  {ram.total_mb
                    ? `${Math.round(ram.used_mb / 1024)} / ${Math.round(ram.total_mb / 1024)} GB`
                    : 'non disponibile'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
