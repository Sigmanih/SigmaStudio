// =============================================================================
// ReviewProposal.jsx — La modifica proposta, prima che resti
// Sigma Studio v8 — Developer Studio
// =============================================================================
//
// L'agente ha appena toccato un file e il run è fermo qui: finché non arriva
// una decisione non prosegue, e ciò che non viene tenuto torna com'era.
//
// Il pannello mostra il diff vero — la modifica è già passata da backup,
// guardia sul troncamento e controllo di sintassi — perché il senso della
// revisione è vedere cosa cambia davvero, non una previsione di cosa
// cambierebbe.

import React from 'react';

/** Colora una riga di diff secondo il suo segno. */
const rigaColore = (riga, isLight) => {
  if (riga.startsWith('+++') || riga.startsWith('---')) {
    return isLight ? '#6a737d' : '#8b949e';
  }
  if (riga.startsWith('@@')) return '#a371f7';
  if (riga.startsWith('+')) return '#3fb950';
  if (riga.startsWith('-')) return '#f85149';
  return isLight ? '#24292e' : '#c9d1d9';
};

const rigaSfondo = (riga, isLight) => {
  if (riga.startsWith('+++') || riga.startsWith('---') || riga.startsWith('@@')) {
    return 'transparent';
  }
  if (riga.startsWith('+')) {
    return isLight ? 'rgba(63, 185, 80, 0.12)' : 'rgba(63, 185, 80, 0.10)';
  }
  if (riga.startsWith('-')) {
    return isLight ? 'rgba(248, 81, 73, 0.12)' : 'rgba(248, 81, 73, 0.10)';
  }
  return 'transparent';
};

export default function ReviewProposal({ proposal, onDecide, deciding, isLight }) {
  if (!proposal) return null;

  const righe = String(proposal.diff || '').split('\n');
  const aggiunte = righe.filter(r => r.startsWith('+') && !r.startsWith('+++')).length;
  const rimosse = righe.filter(r => r.startsWith('-') && !r.startsWith('---')).length;

  return (
    <div style={{
      margin: '6px 0',
      borderRadius: '8px',
      overflow: 'hidden',
      border: '1px solid rgba(210, 153, 34, 0.55)',
      background: isLight ? '#fffdf5' : '#1a1710',
      boxShadow: isLight ? '0 1px 6px rgba(0,0,0,0.08)' : '0 2px 12px rgba(0,0,0,0.35)'
    }}>
      <div style={{
        padding: '7px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexWrap: 'wrap',
        background: isLight ? 'rgba(210, 153, 34, 0.12)' : 'rgba(210, 153, 34, 0.10)',
        borderBottom: '1px solid rgba(210, 153, 34, 0.35)'
      }}>
        <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#d29922' }}>
          {proposal.isRun ? '⏸ Lavoro del run da rivedere' : '⏸ Modifica da rivedere'}
        </span>
        <code style={{
          fontSize: '0.68rem',
          fontFamily: 'monospace',
          color: isLight ? '#24292e' : '#c9d1d9',
          overflowWrap: 'anywhere'
        }}>
          {proposal.path}
        </code>
        <span style={{ fontSize: '0.62rem', color: '#8b949e' }}>
          {proposal.isRun ? `${proposal.fileCount} file` : proposal.tool}
        </span>
        <span style={{ fontSize: '0.62rem', fontWeight: 700, marginLeft: 'auto' }}>
          <span style={{ color: '#3fb950' }}>+{aggiunte}</span>
          {' '}
          <span style={{ color: '#f85149' }}>-{rimosse}</span>
        </span>
      </div>

      <pre style={{
        margin: 0,
        padding: '6px 0',
        maxHeight: '320px',
        overflow: 'auto',
        fontSize: '0.68rem',
        lineHeight: 1.45,
        fontFamily: 'Consolas, Monaco, monospace',
        background: isLight ? '#ffffff' : '#0d1117'
      }}>
        {righe.map((riga, i) => (
          <div key={i} style={{
            padding: '0 10px',
            whiteSpace: 'pre-wrap',
            overflowWrap: 'anywhere',
            color: rigaColore(riga, isLight),
            background: rigaSfondo(riga, isLight)
          }}>
            {riga || ' '}
          </div>
        ))}
      </pre>

      {proposal.truncated && (
        <div style={{
          padding: '4px 10px',
          fontSize: '0.6rem',
          color: '#8b949e',
          borderTop: '1px solid rgba(210, 153, 34, 0.2)'
        }}>
          Diff troncato. Il testo completo è sul branch{' '}
          <code style={{ color: '#a371f7' }}>{proposal.path}</code>.
        </div>
      )}

      <div style={{
        padding: '7px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        borderTop: '1px solid rgba(210, 153, 34, 0.28)'
      }}>
        <button
          onClick={() => onDecide(proposal.id, 'approved')}
          disabled={deciding}
          style={{
            padding: '5px 14px',
            borderRadius: '6px',
            border: '1px solid rgba(63, 185, 80, 0.55)',
            background: 'rgba(63, 185, 80, 0.18)',
            color: '#3fb950',
            fontWeight: 800,
            fontSize: '0.68rem',
            cursor: deciding ? 'wait' : 'pointer'
          }}
        >
          ✓ Applica
        </button>
        <button
          onClick={() => onDecide(proposal.id, 'rejected')}
          disabled={deciding}
          style={{
            padding: '5px 14px',
            borderRadius: '6px',
            border: '1px solid rgba(248, 81, 73, 0.55)',
            background: 'rgba(248, 81, 73, 0.15)',
            color: '#f85149',
            fontWeight: 800,
            fontSize: '0.68rem',
            cursor: deciding ? 'wait' : 'pointer'
          }}
        >
          ✕ Scarta
        </button>
        {/* Il silenzio non è un sì: se nessuno decide, la modifica viene
            annullata da sola. Dirlo qui evita di scoprirlo dopo. */}
        <span style={{ fontSize: '0.6rem', color: '#8b949e' }}>
          {proposal.isRun
            ? "Applica trasferisce il lavoro all'albero principale. Scarta lo lascia sul branch della sessione: non si perde."
            : "L'agente è in attesa. Senza risposta la modifica viene annullata."}
        </span>
      </div>
    </div>
  );
}
