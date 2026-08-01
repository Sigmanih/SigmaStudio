import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';

// ==============================================================================
// InfoHint — la spiegazione di un campo, al passaggio del mouse
// ==============================================================================
// Il Training Lab è pieno di parametri che non si spiegano da soli (rank della
// LoRA, gradient accumulation, perplexity). Metterne la descrizione sotto ogni
// campo riempirebbe la pagina; questo la tiene a portata di mouse e lascia la
// vista compatta.
//
// `entry` accetta le stesse chiavi che il backend espone in METRIC_GUIDE, così
// spiegazioni e soglie restano una cosa sola:
//   { label, what, good, bad, optimal }
// Le voci oltre `what` sono facoltative: un iperparametro ha un "cosa fa" e un
// "come sceglierlo", una metrica ha anche un valore ottimo.

export default function InfoHint({ entry, text, side = 'top', width = 280 }) {
  const [open, setOpen] = useState(false);
  const info = entry || (text ? { what: text } : null);
  if (!info) return null;

  // Un elemento in cima al pannello non può aprire il suo tooltip verso l'alto:
  // finirebbe fuori dal contenitore, che ha overflow nascosto, e verrebbe
  // tagliato a metà. Chi sta sul bordo superiore usa `side="bottom"`.
  const position = {
    right: { left: '100%', top: '50%', transform: 'translateY(-50%)', marginLeft: '8px' },
    bottom: { top: '100%', left: '50%', transform: 'translateX(-50%)', marginTop: '7px' },
    top: { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '6px' },
  }[side] || { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '6px' };

  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', cursor: 'help' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      role="note"
      aria-label={info.label || 'Spiegazione'}
    >
      <HelpCircle size={11} style={{ color: 'var(--text-dark)' }} />
      {open && (
        <span style={{
          position: 'absolute', ...position, width: `${width}px`, zIndex: 60,
          textAlign: 'left', background: 'rgba(6,8,18,0.98)',
          border: '1px solid rgba(255,255,255,0.12)', borderRadius: '10px',
          padding: '10px 12px', boxShadow: '0 12px 32px rgba(0,0,0,0.6)',
          fontSize: '0.63rem', lineHeight: 1.55, color: 'var(--text-dim)',
          fontWeight: 400, whiteSpace: 'normal',
          // I label dei campi sono in maiuscolo spaziato: la spiegazione
          // erediterebbe entrambi e diventerebbe illeggibile.
          textTransform: 'none', letterSpacing: 'normal',
        }}>
          {info.label && (
            <span style={{ display: 'block', color: 'var(--text)', fontWeight: 700, marginBottom: '5px' }}>
              {info.label}
            </span>
          )}
          <span style={{ display: 'block' }}>{info.what}</span>
          {info.good && (
            <span style={{ display: 'block', marginTop: '6px' }}>
              <span style={{ color: 'var(--success)' }}>Bene:</span> {info.good}
            </span>
          )}
          {info.bad && (
            <span style={{ display: 'block' }}>
              <span style={{ color: 'var(--warning)' }}>Male:</span> {info.bad}
            </span>
          )}
          {info.optimal && (
            <span style={{ display: 'block' }}>
              <span style={{ color: 'var(--primary)' }}>Ottimo:</span> {info.optimal}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
