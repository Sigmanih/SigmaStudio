// =============================================================================
// ActivityBar.jsx — Cosa sta girando adesso, chiunque lo abbia lanciato
// Sigma Studio v8 — Developer Studio
// =============================================================================
//
// Un ventaglio lanciato da riga di comando non compariva da nessuna parte qui
// dentro: la pagina mostrava un sistema fermo mentre due agenti stavano
// riscrivendo il progetto. Lo stream degli eventi è visibile solo a chi è
// attaccato a quello stream, e non è quasi mai chi apre la scheda.
//
// Questa barra legge il registro delle attività, che sta su disco proprio per
// questo: la domanda «cosa sta girando» arriva da una richiesta diversa da
// quella che sta lavorando.

import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Users, Layers, MessageSquare, Clock, ChevronDown, ChevronRight } from 'lucide-react';

// Un secondo e mezzo: abbastanza per sembrare vivo, abbastanza poco da non
// pesare. Il registro è un file piccolo, la lettura costa quanto un ls.
// Il backend riusa la fotografia dell'attivita' per un secondo (vedi
// `core/harness/attivita.stato`), e questo pannello non e' l'unico a chiederla:
// due componenti piu' le schede aperte moltiplicavano le richieste. «Chi sta
// lavorando adesso» non cambia in tre secondi, e chiederlo tre volte meno spesso
// e' l'unica parte di questo costo che si poteva togliere senza perdere niente.
const INTERVALLO_MS = 3000;

const ICONA = {
  ventaglio: Layers,
  obiettivo: Users,
  agente: MessageSquare,
};

const COLORE = {
  ventaglio: '#a371f7',
  obiettivo: '#00f2fe',
  agente: '#3fb950',
};

function durata(secondiDa) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - secondiDa));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${String(s % 60).padStart(2, '0')}s`;
}

// inline=true: dentro le mini-tab della chat, senza cornice né header toggle
export default function ActivityBar({ isLight = false, inline = false }) {
  const [stato, setStato] = useState({ busy: false, running: [], recent: [] });
  const [aperto, setAperto] = useState(false);

  const leggi = useCallback(() => {
    fetch('/api/harness/activity')
      .then((r) => r.json())
      .then((d) => { if (d && d.success) setStato(d); })
      .catch(() => { /* il registro non deve poter rompere la pagina */ });
  }, []);

  useEffect(() => {
    leggi();
    const t = setInterval(leggi, INTERVALLO_MS);
    return () => clearInterval(t);
  }, [leggi]);

  const bordo = isLight ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.08)';
  const testo = isLight ? '#1f2328' : '#e6edf3';
  const attivi = stato.running || [];
  const recenti = stato.recent || [];

  // ── Vista inline per le mini-tab ──────────────────────────────────────
  if (inline) {
    return (
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {attivi.length === 0 && recenti.length === 0 && (
          <div style={{
            padding: '14px 10px',
            textAlign: 'center',
            fontSize: '0.66rem',
            color: '#8b949e'
          }}>
            <Activity size={18} color="#8b949e" style={{ marginBottom: 6, opacity: 0.5 }} />
            <div>Nessun agente in esecuzione</div>
          </div>
        )}

        {attivi.map((voce) => {
          const Icona = ICONA[voce.tipo] || Activity;
          const colore = COLORE[voce.tipo] || '#8b949e';
          const coda = voce.queue || null;
          const piano = voce.pipeline || null;
          return (
            <div key={voce.id} style={{
              padding: '8px 10px',
              borderRadius: '8px',
              background: isLight ? 'rgba(0, 242, 254, 0.06)' : 'rgba(0, 242, 254, 0.08)',
              border: '1px solid rgba(0, 242, 254, 0.25)',
            }}>
              {/* Intestazione: tipo + durata */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: colore, boxShadow: `0 0 6px ${colore}`,
                    display: 'inline-block', flexShrink: 0
                  }} />
                  <Icona size={12} color={colore} />
                  <span style={{
                    fontSize: '0.64rem', fontWeight: 800, color: colore,
                    textTransform: 'uppercase', letterSpacing: '0.04em'
                  }}>
                    {voce.tipo}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Clock size={10} color="#8b949e" />
                  <span style={{ fontSize: '0.60rem', color: '#8b949e', fontFamily: 'monospace', fontWeight: 700 }}>
                    {durata(voce.iniziato)}
                  </span>
                </div>
              </div>

              {/* Titolo del lavoro */}
              <div style={{
                fontSize: '0.66rem', fontWeight: 600, color: testo,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                marginBottom: 3
              }} title={voce.titolo}>
                {voce.titolo || '(senza titolo)'}
              </div>

              {/* Progresso testuale */}
              {voce.progress && (
                <div style={{ fontSize: '0.60rem', color: '#8b949e', marginBottom: 3 }}>
                  {voce.progress}
                </div>
              )}

              {/* Stato coda (ventaglio) — barra + numeri */}
              {coda && (() => {
                const tot = (coda.done || 0) + (coda.doing || 0) + (coda.todo || 0) + (coda.blocked || 0) + (coda.failed || 0);
                const pct = tot > 0 ? Math.round(((coda.done || 0) / tot) * 100) : 0;
                return (
                  <div style={{ marginTop: 4 }}>
                    <div style={{
                      height: 4, borderRadius: 2, overflow: 'hidden',
                      background: isLight ? '#e1e4e8' : '#21262d',
                      display: 'flex', marginBottom: 4
                    }}>
                      <div style={{ width: `${pct}%`, background: '#3fb950', transition: 'width 0.3s' }} />
                      <div style={{ width: `${tot > 0 ? Math.round(((coda.doing || 0) / tot) * 100) : 0}%`, background: '#00f2fe' }} />
                      <div style={{ width: `${tot > 0 ? Math.round(((coda.failed || 0) / tot) * 100) : 0}%`, background: '#f85149' }} />
                    </div>
                    <div style={{ display: 'flex', gap: 6, fontSize: '0.58rem', fontWeight: 700, flexWrap: 'wrap' }}>
                      <span style={{ color: '#3fb950' }}>✓ {coda.done} fatte</span>
                      <span style={{ color: '#00f2fe' }}>⚡ {coda.doing} in corso</span>
                      <span style={{ color: '#8b949e' }}>⏳ {coda.todo} da fare</span>
                      {coda.blocked > 0 && <span style={{ color: '#d29922' }}>⊘ {coda.blocked} bloccate</span>}
                      {coda.failed > 0 && <span style={{ color: '#f85149' }}>✕ {coda.failed} ferme</span>}
                    </div>
                  </div>
                );
              })()}

              {/* Piano della squadra */}
              {piano && (
                <div style={{
                  marginTop: 4, display: 'flex', alignItems: 'center', gap: 6,
                  fontSize: '0.58rem', color: '#8b949e'
                }}>
                  <span>Piano: {piano.done ?? 0}/{piano.total ?? 0} task</span>
                  {typeof piano.progress_percent === 'number' && (
                    <span style={{
                      padding: '0 4px', borderRadius: 4,
                      background: 'rgba(0, 242, 254, 0.15)',
                      color: '#00f2fe', fontWeight: 800, fontSize: '0.54rem'
                    }}>
                      {Math.round(piano.progress_percent)}%
                    </span>
                  )}
                </div>
              )}

              {/* Workspace */}
              {voce.workspace_root && (
                <div style={{
                  fontSize: '0.54rem', color: '#6e7681', marginTop: 3,
                  fontFamily: 'monospace', overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                }} title={voce.workspace_root}>
                  📁 {voce.workspace_root.replace(/\\/g, '/').split('/').filter(Boolean).pop()}
                </div>
              )}
            </div>
          );
        })}

        {/* Recenti — sempre visibili in inline */}
        {recenti.length > 0 && (
          <div style={{ marginTop: attivi.length > 0 ? 4 : 0 }}>
            <div style={{
              fontSize: '0.58rem', fontWeight: 800, color: '#8b949e',
              marginBottom: 4, letterSpacing: '0.04em',
              textTransform: 'uppercase'
            }}>
              Completati di recente
            </div>
            {recenti.slice(0, 6).map((voce, i) => (
              <div key={`${voce.id}-${i}`} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '3px 6px', borderRadius: 5, marginBottom: 2,
                background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)',
                fontSize: '0.60rem'
              }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: voce.esito === 'obiettivo raggiunto' ? '#3fb950' : '#8b949e',
                  flexShrink: 0
                }} />
                <span style={{
                  flex: 1, overflow: 'hidden', color: testo,
                  display: '-webkit-box', WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical', lineHeight: 1.3,
                  wordBreak: 'break-word'
                }} title={voce.titolo || voce.tipo}>
                  {voce.titolo || voce.tipo}
                </span>
                <span style={{
                  fontSize: '0.54rem', fontWeight: 700, flexShrink: 0,
                  color: voce.esito === 'obiettivo raggiunto' ? '#3fb950' : '#8b949e'
                }}>
                  {voce.esito}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Vista standalone per la sidebar sinistra ──────────────────────────
  const sfondo = isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.03)';

  return (
    <div style={{
      border: `1px solid ${attivi.length ? 'rgba(0, 242, 254, 0.45)' : bordo}`,
      borderRadius: 10,
      background: sfondo,
      marginBottom: 10,
      overflow: 'hidden',
    }}>
      <button
        type="button"
        onClick={() => setAperto((v) => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 10px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left', color: testo,
        }}
      >
        <Activity size={13} color={attivi.length ? '#00f2fe' : '#8b949e'} />
        <span style={{ fontSize: '0.66rem', fontWeight: 800 }}>
          {attivi.length
            ? `${attivi.length} in esecuzione`
            : 'Nessun agente in esecuzione'}
        </span>
        {attivi.length > 0 && (
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: '#00f2fe',
            boxShadow: '0 0 6px #00f2fe',
          }} />
        )}
      </button>

      {attivi.map((voce) => {
        const Icona = ICONA[voce.tipo] || Activity;
        const colore = COLORE[voce.tipo] || '#8b949e';
        const coda = voce.queue || null;
        const piano = voce.pipeline || null;
        return (
          <div key={voce.id} style={{
            padding: '6px 10px 8px', borderTop: `1px solid ${bordo}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icona size={12} color={colore} />
              <span style={{
                fontSize: '0.63rem', fontWeight: 700, color: colore,
                textTransform: 'uppercase', letterSpacing: '0.04em',
              }}>
                {voce.tipo}
              </span>
              <Clock size={10} color="#8b949e" />
              <span style={{ fontSize: '0.6rem', color: '#8b949e' }}>
                {durata(voce.iniziato)}
              </span>
            </div>

            <div style={{
              fontSize: '0.64rem', color: testo, marginTop: 3,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={voce.titolo}>
              {voce.titolo || '(senza titolo)'}
            </div>

            {voce.progress && (
              <div style={{ fontSize: '0.6rem', color: '#8b949e', marginTop: 2 }}>
                {voce.progress}
              </div>
            )}

            {coda && (
              <div style={{
                display: 'flex', gap: 8, marginTop: 4,
                fontSize: '0.58rem', fontWeight: 700,
              }}>
                <span style={{ color: '#3fb950' }}>{coda.done} fatte</span>
                <span style={{ color: '#00f2fe' }}>{coda.doing} in corso</span>
                <span style={{ color: '#8b949e' }}>
                  {coda.todo} da fare
                  {typeof coda.ready === 'number' && coda.ready < coda.todo
                    && ` (${coda.ready} pronte)`}
                </span>
                {coda.blocked > 0 && (
                  <span style={{ color: '#d29922' }} title="Dipendono da voci non riuscite">
                    {coda.blocked} bloccate
                  </span>
                )}
                {coda.failed > 0 && (
                  <span style={{ color: '#f85149' }}>{coda.failed} ferme</span>
                )}
              </div>
            )}

            {piano && (
              <div style={{ fontSize: '0.58rem', color: '#8b949e', marginTop: 4 }}>
                piano: {piano.done ?? 0}/{piano.total ?? 0} task
                {typeof piano.progress_percent === 'number' &&
                  ` (${Math.round(piano.progress_percent)}%)`}
              </div>
            )}

            {voce.workspace_root && (
              <div style={{
                fontSize: '0.56rem', color: '#6e7681', marginTop: 3,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }} title={voce.workspace_root}>
                {voce.workspace_root}
              </div>
            )}
          </div>
        );
      })}

      {aperto && recenti.length > 0 && (
        <div style={{ borderTop: `1px solid ${bordo}`, padding: '6px 10px' }}>
          <div style={{
            fontSize: '0.58rem', fontWeight: 800, color: '#8b949e',
            marginBottom: 4, letterSpacing: '0.04em',
          }}>
            APPENA FINITI
          </div>
          {recenti.slice(0, 6).map((voce, i) => (
            <div key={`${voce.id}-${i}`} style={{
              fontSize: '0.6rem', color: '#8b949e', padding: '1px 0',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              <span style={{
                color: voce.esito === 'obiettivo raggiunto' ? '#3fb950' : '#8b949e',
              }}>
                ●
              </span>{' '}
              {voce.titolo || voce.tipo} — {voce.esito}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
