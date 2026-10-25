// =============================================================================
// ActivityTerminalStrip.jsx — Striscia compatta ad una riga sopra il terminale
// Sigma Studio v8 — Developer Studio
// =============================================================================

import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Clock } from 'lucide-react';

// Tre secondi, come `ActivityBar`: il backend riusa la fotografia per un
// secondo, e due componenti che la chiedono ogni 1,5 s si sommano.
const INTERVALLO_MS = 3000;

function formatDurata(secondiDa) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - secondiDa));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${String(s % 60).padStart(2, '0')}s`;
}

export default function ActivityTerminalStrip({ isLight = false }) {
  const [attivi, setAttivi] = useState([]);

  const leggi = useCallback(() => {
    fetch('/api/harness/activity')
      .then((r) => r.json())
      .then((d) => {
        if (d && d.success && Array.isArray(d.running)) {
          setAttivi(d.running);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    leggi();
    const t = setInterval(leggi, INTERVALLO_MS);
    return () => clearInterval(t);
  }, [leggi]);

  if (!attivi || attivi.length === 0) {
    return null;
  }

  const voce = attivi[0];
  const testo = isLight ? '#1f2328' : '#e6edf3';
  const colore = voce.tipo === 'obiettivo' ? '#00f2fe' : voce.tipo === 'agente' ? '#3fb950' : '#a371f7';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '3px 12px',
        background: isLight ? 'rgba(0, 242, 254, 0.05)' : 'rgba(0, 242, 254, 0.07)',
        borderTop: isLight ? '1px solid rgba(0, 242, 254, 0.2)' : '1px solid rgba(0, 242, 254, 0.25)',
        borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)',
        fontSize: '0.67rem',
        userSelect: 'none',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: colore,
            boxShadow: `0 0 6px ${colore}`,
            flexShrink: 0,
          }}
        />
        <Activity size={12} color={colore} style={{ flexShrink: 0 }} />
        <span
          style={{
            fontSize: '0.62rem',
            fontWeight: 800,
            color: colore,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            flexShrink: 0,
          }}
        >
          {voce.tipo || 'attività'}
        </span>
        <span
          style={{
            color: testo,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
          title={voce.titolo || ''}
        >
          {voce.titolo || 'Operazione in corso...'}
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0, marginLeft: '12px' }}>
        <Clock size={10} color="#8b949e" />
        <span style={{ fontSize: '0.62rem', color: '#8b949e', fontFamily: 'monospace', fontWeight: 600 }}>
          {voce.iniziato ? formatDurata(voce.iniziato) : '0s'}
        </span>
        {attivi.length > 1 && (
          <span
            style={{
              marginLeft: '4px',
              padding: '1px 5px',
              borderRadius: '4px',
              background: 'rgba(0, 242, 254, 0.15)',
              color: '#00f2fe',
              fontSize: '0.58rem',
              fontWeight: 700,
            }}
          >
            +{attivi.length - 1} altri
          </span>
        )}
      </div>
    </div>
  );
}
