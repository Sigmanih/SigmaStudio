// =============================================================================
// SigmaEngineNativeBar.jsx — Telemetria e Controllo Micro-Kernel Rust
// Sigma Studio v8 — Developer Studio
// =============================================================================

import React, { useState, useEffect, useCallback } from 'react';
import { Cpu, Zap, Server, HardDrive, RefreshCw, ChevronDown, ChevronRight, CheckCircle2, AlertCircle, Hammer } from 'lucide-react';

const INTERVALLO_POLL_MS = 3000;

export default function SigmaEngineNativeBar({ isLight = false }) {
  const [engineStatus, setEngineStatus] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Ricompilazione del kernel: un solo stato, perche' il tasto deve dire
  // in che punto e' senza aprire nessun pannello.
  const [rebuild, setRebuild] = useState({ inCorso: false, esito: null, messaggio: '' });

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/developer/engine/status');
      if (res.ok) {
        const payload = await res.json();
        if (payload && payload.success) {
          setEngineStatus(payload.data);
        }
      }
    } catch {
      // Ignora errori di fetch per evitare crash della dashboard
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, INTERVALLO_POLL_MS);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleManualRefresh = (e) => {
    e.stopPropagation();
    setIsRefreshing(true);
    fetchStatus();
  };

  // Ricompila il kernel nativo e lo ricarica a caldo.
  //
  // La rotta esisteva gia' — la usava solo un tasto dentro il modale Docker,
  // dove nessuno lo cercava. Qui sta accanto all'indicatore di stato, che e'
  // il posto in cui si guarda quando ci si chiede se il kernel gira.
  //
  // Compila (30-60 s), inietta il binario nel contenitore e lo riavvia: il
  // tasto resta occupato per tutto il tempo e lo dice, perche' un pulsante
  // che sembra libero mentre lavora viene premuto due volte.
  const handleRebuild = useCallback(async (e) => {
    e.stopPropagation();
    if (rebuild.inCorso) return;
    setRebuild({ inCorso: true, esito: null, messaggio: 'Compilazione in corso...' });
    try {
      const res = await fetch('/api/developer/docker/rust/hot-reload', { method: 'POST' });
      const dati = await res.json().catch(() => null);
      if (res.ok && dati?.success) {
        setRebuild({
          inCorso: false,
          esito: 'ok',
          messaggio: dati.message || 'Kernel ricompilato e riavviato.',
        });
        // Il contenitore si sta riavviando: la telemetria va riletta dopo,
        // non adesso, o mostrerebbe offline un kernel che sta tornando su.
        setTimeout(fetchStatus, 2500);
      } else {
        setRebuild({
          inCorso: false,
          esito: 'errore',
          messaggio: dati?.error || `Ricompilazione fallita (HTTP ${res.status}).`,
        });
      }
    } catch (err) {
      setRebuild({ inCorso: false, esito: 'errore', messaggio: String(err) });
    }
  }, [rebuild.inCorso, fetchStatus]);

  const isOnline = !!engineStatus?.online;
  const latency = engineStatus?.latency_ms;
  const isDualGpu = !!engineStatus?.dual_gpu;
  const gpus = engineStatus?.gpus || [];

  const borderColor = isLight ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.08)';
  const textColor = isLight ? '#1f2328' : '#e6edf3';
  const mutedColor = isLight ? '#656d76' : '#8b949e';
  const bgCard = isLight ? '#f6f8fa' : 'rgba(255,255,255,0.03)';

  return (
    <div
      style={{
        borderBottom: `1px solid ${borderColor}`,
        background: isLight ? '#ffffff' : '#0d1117',
        fontSize: '0.75rem',
        userSelect: 'none',
      }}
    >
      {/* Header compatto cliccabile per espansione */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          cursor: 'pointer',
          background: isOpen ? bgCard : 'transparent',
          transition: 'background 0.15s ease',
        }}
        title="Clicca per espandere i dettagli del micro-kernel nativo Rust"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          {/* Indicatore visivo Online / Offline */}
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isOnline ? '#22c55e' : '#ef4444',
              boxShadow: isOnline ? '0 0 6px rgba(34, 197, 94, 0.6)' : 'none',
              flexShrink: 0,
            }}
          />
          <span style={{ fontWeight: 600, color: textColor, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            SigmaEngine Rust
          </span>
          {isOnline && latency !== null && (
            <span
              style={{
                fontSize: '0.68rem',
                color: '#22c55e',
                background: isLight ? 'rgba(34, 197, 94, 0.1)' : 'rgba(34, 197, 94, 0.15)',
                padding: '1px 5px',
                borderRadius: '4px',
                fontWeight: 600,
              }}
            >
              {latency}ms
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Ricompila: solo a kernel attivo. A kernel spento non c'e'
              niente da ricaricare a caldo, e un tasto che fallisce sempre
              e' peggio di un tasto assente. */}
          {isOnline && (
            <button
              onClick={handleRebuild}
              disabled={rebuild.inCorso}
              style={{
                background: rebuild.esito === 'errore'
                  ? (isLight ? 'rgba(239,68,68,0.10)' : 'rgba(239,68,68,0.15)')
                  : (isLight ? 'rgba(59,130,246,0.10)' : 'rgba(59,130,246,0.15)'),
                border: 'none',
                borderRadius: '4px',
                cursor: rebuild.inCorso ? 'wait' : 'pointer',
                padding: '2px 7px',
                color: rebuild.esito === 'errore' ? '#ef4444' : '#3b82f6',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.68rem',
                fontWeight: 600,
                opacity: rebuild.inCorso ? 0.7 : 1,
              }}
              title={rebuild.messaggio || 'Ricompila il kernel Rust e ricaricalo a caldo nel contenitore'}
            >
              <Hammer size={11} className={rebuild.inCorso ? 'animate-spin' : ''} />
              {rebuild.inCorso ? 'Compilo...' : 'Ricompila'}
            </button>
          )}
          <button
            onClick={handleManualRefresh}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '2px',
              color: mutedColor,
              display: 'flex',
              alignItems: 'center',
            }}
            title="Aggiorna telemetria kernel"
          >
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
          </button>
          {isOpen ? <ChevronDown size={14} color={mutedColor} /> : <ChevronRight size={14} color={mutedColor} />}
        </div>
      </div>

      {/* L'esito dell'ultima ricompilazione, sotto l'intestazione.
          Un errore di compilazione e' lungo e va letto: resta li' finche'
          non si ricompila di nuovo, invece di sparire da solo. */}
      {rebuild.esito && (
        <div
          style={{
            padding: '6px 12px',
            fontSize: '0.68rem',
            lineHeight: 1.45,
            color: rebuild.esito === 'ok' ? '#22c55e' : '#ef4444',
            background: rebuild.esito === 'ok'
              ? (isLight ? 'rgba(34,197,94,0.08)' : 'rgba(34,197,94,0.10)')
              : (isLight ? 'rgba(239,68,68,0.08)' : 'rgba(239,68,68,0.10)'),
            borderTop: `1px solid ${borderColor}`,
            whiteSpace: 'pre-wrap',
            maxHeight: '160px',
            overflowY: 'auto',
            fontFamily: rebuild.esito === 'errore' ? 'ui-monospace, monospace' : 'inherit',
          }}
        >
          {rebuild.esito === 'ok' ? '\u2713 ' : '\u2717 '}
          {rebuild.messaggio}
        </div>
      )}

      {/* Contenuto dettagliato espanso */}
      {isOpen && (
        <div
          style={{
            padding: '10px 12px',
            background: bgCard,
            borderTop: `1px solid ${borderColor}`,
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          {/* Ripartizione Architettura e Canali */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: mutedColor }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Server size={12} />
                <span>Porta REST:</span>
              </span>
              <span style={{ fontFamily: 'monospace', color: textColor }}>:8090 (Axum)</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: mutedColor }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Zap size={12} />
                <span>IPC Pipe:</span>
              </span>
              <span style={{ fontFamily: 'monospace', color: '#c084fc', fontSize: '0.68rem' }} title="Windows Named Pipe ultra-rapida">
                \\.\pipe\sigma_engine_ipc
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: mutedColor }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <HardDrive size={12} />
                <span>KV-Cache:</span>
              </span>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>Radix Tree O(1) CoW</span>
            </div>
          </div>

          {/* Ripartizione Hardware / GPU */}
          <div
            style={{
              paddingTop: '6px',
              borderTop: `1px solid ${borderColor}`,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ color: mutedColor, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Cpu size={12} />
                <span>Accelerazione GPU:</span>
              </span>
              <span
                style={{
                  color: isDualGpu ? '#22c55e' : textColor,
                  fontWeight: 600,
                  fontSize: '0.68rem',
                }}
              >
                {isDualGpu ? 'Dual-GPU Asymmetric' : gpus.length > 0 ? 'Single GPU' : 'CPU Mode'}
              </span>
            </div>

            {gpus.map((gpu, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingLeft: '17px',
                  fontSize: '0.68rem',
                  color: mutedColor,
                }}
              >
                <span>GPU {idx}: {gpu.name || `Device #${idx}`}</span>
                <span style={{ color: textColor, fontFamily: 'monospace' }}>
                  {gpu.memory_total ? `${Math.round(gpu.memory_total / 1024)}GB` : 'CUDA'}
                </span>
              </div>
            ))}
          </div>

          {/* Stato finale diagnostico */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.68rem',
              color: isOnline ? '#22c55e' : '#ef4444',
              paddingTop: '4px',
            }}
          >
            {isOnline ? (
              <>
                <CheckCircle2 size={12} />
                <span>Kernel attivo & integrato con l'IDE</span>
              </>
            ) : (
              <>
                <AlertCircle size={12} />
                <span>Kernel offline (fallback su llama-server)</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
