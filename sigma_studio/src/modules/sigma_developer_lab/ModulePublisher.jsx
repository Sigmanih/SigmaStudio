// =============================================================================
// ModulePublisher.jsx — Il lavoro sui moduli, e dove deve andare
// Sigma Studio v8 — Developer Studio
// =============================================================================
//
// Si sviluppa qui dentro, ma i moduli appartengono al loro repository. Il
// commit avviene da solo — a ogni salvataggio e a fine run dell'agente — e
// resta in locale; la pubblicazione la decide una persona, ed è questo il
// pulsante che gliela fa decidere senza passare dal terminale.
//
// Il pannello non compare a tutti: pubblicare vuol dire spingere su un
// repository che appartiene a qualcuno. Chi non ha quei permessi vedrebbe solo
// un pulsante che fallisce, e un pulsante che fallisce sempre è peggio di un
// pulsante assente. Lo accende `show_publish_ui` in config/module_sync.json.

import React, { useCallback, useEffect, useState } from 'react';
import { UploadCloud, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';

export default function ModulePublisher({ isLight }) {
  const [abilitato, setAbilitato] = useState(null);   // null = non ancora saputo
  const [aperto, setAperto] = useState(false);
  const [stato, setStato] = useState(null);
  const [caricamento, setCaricamento] = useState(false);
  const [esito, setEsito] = useState(null);

  useEffect(() => {
    let annullato = false;
    (async () => {
      try {
        const res = await fetch('/api/modules/sync/config');
        const dati = await res.json();
        if (!annullato) setAbilitato(!!dati.show_publish_ui);
      } catch (e) {
        if (!annullato) setAbilitato(false);
      }
    })();
    return () => { annullato = true; };
  }, []);

  // La prova a vuoto confronta ogni file di ogni modulo: si fa quando si apre
  // il pannello, non a ogni montaggio del Developer Studio.
  const aggiorna = useCallback(async () => {
    setCaricamento(true);
    setEsito(null);
    try {
      const res = await fetch('/api/modules/sync/status');
      setStato(await res.json());
    } catch (e) {
      setStato({ success: false, errors: [e.message], changed: {} });
    } finally {
      setCaricamento(false);
    }
  }, []);

  useEffect(() => {
    if (aperto && !stato && !caricamento) aggiorna();
  }, [aperto, stato, caricamento, aggiorna]);

  const pubblica = async () => {
    setCaricamento(true);
    try {
      const res = await fetch('/api/modules/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ push: true })
      });
      const dati = await res.json();
      setEsito(dati);
      setStato(null);
      if (dati.success) await aggiorna();
    } catch (e) {
      setEsito({ success: false, errors: [e.message] });
    } finally {
      setCaricamento(false);
    }
  };

  if (!abilitato) return null;

  const moduli = Object.entries(stato?.changed || {});
  const totale = moduli.reduce((acc, [, c]) => (
    acc + c.aggiunti.length + c.modificati.length + c.rimossi.length
  ), 0);

  const bordo = isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)';

  return (
    <div style={{
      borderTop: bordo,
      background: isLight ? '#ffffff' : '#0d1117',
      fontSize: '0.7rem',
      flexShrink: 0
    }}>
      <div
        onClick={() => setAperto(!aperto)}
        style={{
          padding: '7px 10px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          fontWeight: 700,
          letterSpacing: '0.4px',
          color: isLight ? '#24292e' : '#c9d1d9'
        }}
      >
        {aperto ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <UploadCloud size={13} color="#a371f7" />
        <span>PUBBLICA MODULI</span>
        {moduli.length > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.62rem',
            fontWeight: 800,
            color: '#a371f7'
          }}>
            {moduli.length}
          </span>
        )}
      </div>

      {aperto && (
        <div style={{ padding: '0 10px 9px' }}>
          <div style={{
            fontSize: '0.62rem',
            color: '#8b949e',
            lineHeight: 1.5,
            marginBottom: '7px'
          }}>
            Le modifiche vengono committate da sole in locale. Qui si decide
            quando mandarle sul repository dei moduli.
          </div>

          {caricamento && (
            <div style={{ color: '#8b949e', fontSize: '0.65rem' }}>Confronto in corso…</div>
          )}

          {!caricamento && stato && moduli.length === 0 && !esito && (
            <div style={{ color: '#3fb950', fontSize: '0.65rem' }}>
              Tutto allineato: niente da pubblicare.
            </div>
          )}

          {!caricamento && moduli.length > 0 && (
            <div style={{ maxHeight: '190px', overflowY: 'auto', marginBottom: '8px' }}>
              {moduli.map(([nome, c]) => (
                <div key={nome} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '2px 0',
                  fontFamily: 'monospace',
                  fontSize: '0.64rem'
                }}>
                  <span style={{
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    color: isLight ? '#24292e' : '#c9d1d9'
                  }}>
                    {nome}
                  </span>
                  {c.aggiunti.length > 0 && <span style={{ color: '#3fb950' }}>+{c.aggiunti.length}</span>}
                  {c.modificati.length > 0 && <span style={{ color: '#d29922' }}>~{c.modificati.length}</span>}
                  {c.rimossi.length > 0 && <span style={{ color: '#f85149' }}>-{c.rimossi.length}</span>}
                </div>
              ))}
            </div>
          )}

          {(stato?.orphans || []).length > 0 && (
            <div style={{
              fontSize: '0.62rem',
              color: '#f85149',
              marginBottom: '7px',
              lineHeight: 1.5
            }}>
              Fuori da ogni repository — il loro codice gira e non sta da
              nessuna parte:{' '}
              {stato.orphans.map(o => `${o.module_id} (${o.reason})`).join('; ')}
            </div>
          )}

          {(stato?.skipped_secrets || []).length > 0 && (
            <div style={{
              fontSize: '0.62rem',
              color: '#d29922',
              marginBottom: '7px',
              lineHeight: 1.5
            }}>
              Non pubblicati perché sembrano credenziali:{' '}
              {stato.skipped_secrets.join(', ')}
            </div>
          )}

          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              onClick={pubblica}
              disabled={caricamento || moduli.length === 0}
              style={{
                flex: 1,
                padding: '5px 10px',
                borderRadius: '5px',
                border: '1px solid rgba(163, 113, 247, 0.55)',
                background: moduli.length > 0 ? 'rgba(163, 113, 247, 0.18)' : 'transparent',
                color: moduli.length > 0 ? '#a371f7' : '#6e7681',
                fontWeight: 800,
                fontSize: '0.64rem',
                cursor: (caricamento || moduli.length === 0) ? 'default' : 'pointer'
              }}
            >
              Pubblica {totale > 0 ? `(${totale} file)` : ''}
            </button>
            <button
              onClick={aggiorna}
              disabled={caricamento}
              title="Ricontrolla cosa è cambiato"
              style={{
                padding: '5px 8px',
                borderRadius: '5px',
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'transparent',
                color: '#8b949e',
                cursor: caricamento ? 'wait' : 'pointer'
              }}
            >
              <RefreshCw size={12} />
            </button>
          </div>

          {esito && (
            <div style={{
              marginTop: '7px',
              fontSize: '0.63rem',
              lineHeight: 1.5,
              color: esito.success ? '#3fb950' : '#f85149'
            }}>
              {esito.success
                ? (esito.pushed ? 'Pubblicato.' : 'Commit creato in locale.')
                : `Non riuscito: ${(esito.errors || []).join(' · ')}`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
