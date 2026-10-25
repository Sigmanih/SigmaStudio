// =============================================================================
// FanoutPanel.jsx — Il lavoro grande, spezzato e dato a più agenti
// Sigma Studio v8 — Developer Studio
// =============================================================================
//
// Un lavoro da duecento file non si fa con un run: il contesto non ci sta, e a
// metà strada l'agente non ricorda più cosa aveva già sistemato. Si spezza
// prima — una voce per file, per cartella, per modulo — e si fa consumare la
// coda da più run in parallelo, ognuno nel proprio worktree.
//
// Questo pannello è la faccia di quella macchina. Serve a tre cose che senza
// interfaccia non si possono fare: riempire la coda, farla partire, e vedere a
// che punto è mentre gira — perché un lavoro che dura ore senza notizie è
// indistinguibile da uno bloccato.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Layers, Play, Square, RefreshCw, ChevronDown, ChevronRight, Plus } from 'lucide-react';

const COLORE = {
  todo: '#8b949e',
  doing: '#00f2fe',
  done: '#3fb950',
  failed: '#f85149',
  // Bloccata non è ferma: è una voce che aspetta qualcosa che non è stato
  // fatto. Con lo stesso colore di «ferma» si cercherebbe il difetto nella
  // voce sbagliata.
  blocked: '#d29922'
};

// Il modello non si sceglie qui: lo risolve il ciclo dal ruolo configurato,
// che è l'unico posto in cui quella scelta vive. Un secondo selettore qui
// sarebbe una seconda verità, e le due divergerebbero.
// inline=true: dentro le mini-tab della chat, senza header toggle collapsible
export default function FanoutPanel({ workspaceRoot, isLight, inline = false }) {
  const [aperto, setAperto] = useState(inline);
  const [code, setCode] = useState([]);
  const [codaAttiva, setCodaAttiva] = useState('');
  const [progresso, setProgresso] = useState(null);
  const [inCorso, setInCorso] = useState(false);
  const [lavoratori, setLavoratori] = useState(2);
  const [voci, setVoci] = useState('');
  const [obiettivo, setObiettivo] = useState('');
  const [eventi, setEventi] = useState([]);
  const [errore, setErrore] = useState('');
  const [mostraForm, setMostraForm] = useState(false);
  const abortRef = useRef(null);

  const caricaCode = useCallback(async () => {
    try {
      const res = await fetch('/api/harness/queues');
      const dati = await res.json();
      setCode(dati.queues || []);
      if (!codaAttiva && (dati.queues || []).length > 0) {
        setCodaAttiva(dati.queues[0].queue_id);
        setProgresso(dati.queues[0]);
      }
    } catch (e) {
      setErrore(e.message);
    }
  }, [codaAttiva]);

  useEffect(() => {
    // In inline carica sempre; in standalone solo quando aperto
    if (inline || aperto) caricaCode();
  }, [inline, aperto, caricaCode]);

  useEffect(() => () => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (e) { /* già chiuso */ }
    }
  }, []);

  const creaCoda = async () => {
    const titoli = voci.split('\n').map(r => r.trim()).filter(Boolean);
    if (titoli.length === 0) {
      setErrore('Servono delle voci: una per riga.');
      return;
    }
    const id = codaAttiva || `q_${Date.now().toString(36)}`;
    setErrore('');
    try {
      const res = await fetch('/api/harness/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queue_id: id, goal: obiettivo, items: titoli })
      });
      const dati = await res.json();
      if (!dati.success) {
        setErrore(dati.error || 'Coda non creata.');
        return;
      }
      setCodaAttiva(id);
      setProgresso(dati);
      setVoci('');
      setMostraForm(false);
      caricaCode();
    } catch (e) {
      setErrore(e.message);
    }
  };

  const avvia = async () => {
    if (!codaAttiva) {
      setErrore('Scegli o crea una coda.');
      return;
    }
    setErrore('');
    setEventi([]);
    setInCorso(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch('/api/harness/fanout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          queue_id: codaAttiva,
          workspace_root: workspaceRoot,
          workers: lavoratori
        })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const righe = buffer.split('\n\n');
        buffer = righe.pop() || '';

        for (const riga of righe) {
          if (!riga.startsWith('data: ')) continue;
          let evento;
          try {
            evento = JSON.parse(riga.slice(6).trim());
          } catch (e) {
            continue;
          }

          if (evento.type === 'fanout_progress' || evento.type === 'fanout_started'
              || evento.type === 'fanout_finished') {
            setProgresso(evento);
          }
          if (evento.type === 'item_started' || evento.type === 'item_finished') {
            setEventi(prec => [...prec.slice(-40), evento]);
          }
          if (evento.type === 'error') setErrore(evento.error || 'errore');
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setErrore(e.message);
    } finally {
      setInCorso(false);
      abortRef.current = null;
      caricaCode();
    }
  };

  const ferma = () => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch (e) { /* già chiuso */ }
    }
  };

  const bordo = isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)';
  const totale = progresso?.total || 0;
  const fatte = progresso?.done || 0;
  const percentuale = totale > 0 ? Math.round((fatte / totale) * 100) : 0;
  const testo = isLight ? '#24292e' : '#c9d1d9';

  // ── Il contenuto operativo, usato sia in inline che standalone ────────
  const renderContenuto = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {/* Selettore coda esistente */}
      {code.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <select
            value={codaAttiva}
            onChange={e => {
              setCodaAttiva(e.target.value);
              setProgresso(code.find(c => c.queue_id === e.target.value) || null);
            }}
            disabled={inCorso}
            style={{
              flex: 1, padding: '4px 6px',
              fontSize: '0.64rem', borderRadius: '5px',
              background: isLight ? '#ffffff' : '#161b22',
              color: testo, border: bordo
            }}
          >
            {code.map(c => (
              <option key={c.queue_id} value={c.queue_id}>
                {c.queue_id} — {c.done}/{c.total}
              </option>
            ))}
          </select>
          <button
            onClick={caricaCode}
            disabled={inCorso}
            title="Ricarica lo stato delle code"
            style={{
              padding: '4px 6px', borderRadius: '5px', border: bordo,
              background: 'transparent', color: '#8b949e',
              cursor: inCorso ? 'default' : 'pointer', flexShrink: 0
            }}
          >
            <RefreshCw size={11} />
          </button>
        </div>
      )}

      {/* Barra di progresso visuale */}
      {totale > 0 && (
        <div>
          <div style={{
            height: 5, borderRadius: 3, overflow: 'hidden',
            background: isLight ? '#e1e4e8' : '#21262d', display: 'flex'
          }}>
            <div style={{ width: `${percentuale}%`, background: COLORE.done, transition: 'width 0.3s' }} />
            <div style={{
              width: `${totale ? Math.round(((progresso?.doing || 0) / totale) * 100) : 0}%`,
              background: COLORE.doing
            }} />
            <div style={{
              width: `${totale ? Math.round(((progresso?.failed || 0) / totale) * 100) : 0}%`,
              background: COLORE.failed
            }} />
          </div>
          <div style={{
            display: 'flex', gap: 6, marginTop: 4,
            fontSize: '0.58rem', fontWeight: 700, flexWrap: 'wrap'
          }}>
            <span style={{ color: COLORE.done }}>✓ {progresso?.done || 0} fatte</span>
            <span style={{ color: COLORE.doing }}>⚡ {progresso?.doing || 0} in corso</span>
            <span style={{ color: COLORE.todo }}>
              ⏳ {progresso?.todo || 0} da fare
              {typeof progresso?.ready === 'number' && progresso.ready < (progresso?.todo || 0)
                && ` (${progresso.ready} pronte)`}
            </span>
            {(progresso?.blocked || 0) > 0 && (
              <span style={{ color: COLORE.blocked }} title="Dipendono da voci non riuscite">
                ⊘ {progresso.blocked} bloccate
              </span>
            )}
            {(progresso?.failed || 0) > 0 && (
              <span style={{ color: COLORE.failed }}>✕ {progresso.failed} ferme</span>
            )}
          </div>
        </div>
      )}

      {/* Pulsanti azione */}
      <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
        {!inCorso ? (
          <>
            <button
              onClick={avvia}
              disabled={!codaAttiva || totale === 0}
              style={{
                flex: 1, padding: '5px', borderRadius: '5px',
                border: '1px solid rgba(0, 242, 254, 0.5)',
                background: totale > 0 ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                color: totale > 0 ? '#00f2fe' : '#6e7681',
                fontWeight: 800, fontSize: '0.64rem',
                cursor: totale > 0 ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center',
                justifyContent: 'center', gap: '4px'
              }}
            >
              <Play size={11} /> Avvia
            </button>
            <select
              value={lavoratori}
              onChange={e => setLavoratori(Number(e.target.value))}
              title="Quanti agenti in parallelo"
              style={{
                padding: '5px', fontSize: '0.63rem', borderRadius: '5px',
                background: isLight ? '#ffffff' : '#161b22',
                color: testo, border: bordo
              }}
            >
              {[1, 2, 3, 4, 6, 8].map(n => (
                <option key={n} value={n}>{n}×</option>
              ))}
            </select>
          </>
        ) : (
          <button
            onClick={ferma}
            style={{
              flex: 1, padding: '5px', borderRadius: '5px',
              border: '1px solid rgba(248, 81, 73, 0.5)',
              background: 'rgba(248, 81, 73, 0.15)', color: '#f85149',
              fontWeight: 800, fontSize: '0.64rem', cursor: 'pointer',
              display: 'flex', alignItems: 'center',
              justifyContent: 'center', gap: '4px'
            }}
          >
            <Square size={11} /> Ferma
          </button>
        )}
        {!inCorso && (
          <button
            onClick={() => setMostraForm(!mostraForm)}
            title="Nuova coda di lavoro"
            style={{
              padding: '5px 7px', borderRadius: '5px', border: bordo,
              background: mostraForm ? 'rgba(0, 242, 254, 0.10)' : 'transparent',
              color: mostraForm ? '#00f2fe' : '#8b949e',
              cursor: 'pointer', flexShrink: 0
            }}
          >
            <Plus size={11} />
          </button>
        )}
      </div>

      {/* Form creazione coda — collassato dietro il + */}
      {mostraForm && !inCorso && (
        <div style={{
          padding: '6px 8px', borderRadius: '6px',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.03)',
          border: bordo, display: 'flex', flexDirection: 'column', gap: '4px'
        }}>
          <input
            value={obiettivo}
            onChange={e => setObiettivo(e.target.value)}
            placeholder="Obiettivo (a cosa serve)"
            style={{
              width: '100%', padding: '3px 6px',
              fontSize: '0.62rem', borderRadius: '4px',
              background: isLight ? '#ffffff' : '#161b22',
              color: testo, border: bordo, outline: 'none'
            }}
          />
          <textarea
            value={voci}
            onChange={e => setVoci(e.target.value)}
            placeholder={'Una voce per riga, es:\ntraduci sigma_network/index.jsx\ntraduci sigma_roadmap/index.jsx'}
            rows={3}
            style={{
              width: '100%', padding: '3px 6px',
              fontSize: '0.60rem', fontFamily: 'monospace',
              borderRadius: '4px', resize: 'vertical',
              background: isLight ? '#ffffff' : '#161b22',
              color: testo, border: bordo, outline: 'none'
            }}
          />
          <div style={{ display: 'flex', gap: '5px', justifyContent: 'flex-end' }}>
            <button
              onClick={() => setMostraForm(false)}
              style={{ background: 'none', border: 'none', color: '#8b949e',
                cursor: 'pointer', fontSize: '0.58rem' }}>
              Annulla
            </button>
            <button
              onClick={creaCoda}
              style={{
                padding: '3px 8px', borderRadius: '4px',
                background: '#00f2fe', border: 'none', color: '#000',
                fontSize: '0.60rem', fontWeight: 700, cursor: 'pointer'
              }}>
              Crea coda
            </button>
          </div>
        </div>
      )}

      {/* Log eventi in tempo reale */}
      {eventi.length > 0 && (
        <div style={{
          maxHeight: '120px', overflowY: 'auto',
          fontSize: '0.58rem', fontFamily: 'monospace', lineHeight: 1.5,
          padding: '4px 6px', borderRadius: '5px',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)',
          border: bordo
        }}>
          {[...eventi].reverse().map((e, i) => (
            <div key={i} style={{
              display: 'flex', gap: 4,
              color: e.type === 'item_started'
                ? COLORE.doing
                : (e.ok ? COLORE.done : COLORE.failed)
            }}>
              <span>{e.type === 'item_started' ? '▸' : (e.ok ? '✓' : '✕')}</span>
              <span style={{
                flex: 1, overflow: 'hidden',
                textOverflow: 'ellipsis', whiteSpace: 'nowrap'
              }}>
                {e.title}
              </span>
              <span style={{ color: '#6e7681', flexShrink: 0 }}>{e.worker}</span>
            </div>
          ))}
        </div>
      )}

      {errore && (
        <div style={{ fontSize: '0.60rem', color: '#f85149', padding: '2px 0' }}>
          {errore}
        </div>
      )}

      {(progresso?.failed || 0) > 0 && !inCorso && (
        <div style={{ fontSize: '0.58rem', color: '#8b949e', lineHeight: 1.4 }}>
          Le voci ferme hanno esaurito i tentativi. Guarda i branch delle
          sessioni, o rimettile in coda cambiando ciò che le faceva fallire.
        </div>
      )}
    </div>
  );

  // ── Vista inline per le mini-tab ──────────────────────────────────────
  if (inline) {
    return (
      <div style={{ padding: '8px 10px' }}>
        {totale === 0 && code.length === 0 ? (
          <div style={{
            padding: '14px 10px', textAlign: 'center',
            fontSize: '0.66rem', color: '#8b949e'
          }}>
            <Layers size={18} color="#8b949e" style={{ marginBottom: 6, opacity: 0.5 }} />
            <div style={{ marginBottom: 6 }}>Nessuna coda di lavoro attiva</div>
            <button
              onClick={() => setMostraForm(true)}
              style={{
                padding: '4px 10px', borderRadius: '5px',
                border: '1px solid rgba(0, 242, 254, 0.4)',
                background: 'rgba(0, 242, 254, 0.10)',
                color: '#00f2fe', fontSize: '0.62rem',
                fontWeight: 700, cursor: 'pointer'
              }}>
              <Plus size={10} style={{ verticalAlign: '-1px' }} /> Crea una coda
            </button>

            {mostraForm && (
              <div style={{
                marginTop: 8, padding: '6px 8px', borderRadius: '6px',
                background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.03)',
                border: bordo, display: 'flex', flexDirection: 'column', gap: '4px',
                textAlign: 'left'
              }}>
                <input
                  value={obiettivo}
                  onChange={e => setObiettivo(e.target.value)}
                  placeholder="Obiettivo (a cosa serve)"
                  style={{
                    width: '100%', padding: '3px 6px',
                    fontSize: '0.62rem', borderRadius: '4px',
                    background: isLight ? '#ffffff' : '#161b22',
                    color: testo, border: bordo, outline: 'none'
                  }}
                />
                <textarea
                  value={voci}
                  onChange={e => setVoci(e.target.value)}
                  placeholder={'Una voce per riga, es:\ntraduci sigma_network/index.jsx'}
                  rows={3}
                  style={{
                    width: '100%', padding: '3px 6px',
                    fontSize: '0.60rem', fontFamily: 'monospace',
                    borderRadius: '4px', resize: 'vertical',
                    background: isLight ? '#ffffff' : '#161b22',
                    color: testo, border: bordo, outline: 'none'
                  }}
                />
                <div style={{ display: 'flex', gap: '5px', justifyContent: 'flex-end' }}>
                  <button onClick={() => setMostraForm(false)}
                    style={{ background: 'none', border: 'none', color: '#8b949e',
                      cursor: 'pointer', fontSize: '0.58rem' }}>
                    Annulla
                  </button>
                  <button onClick={creaCoda}
                    style={{ padding: '3px 8px', borderRadius: '4px',
                      background: '#00f2fe', border: 'none', color: '#000',
                      fontSize: '0.60rem', fontWeight: 700, cursor: 'pointer' }}>
                    Crea coda
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          renderContenuto()
        )}
      </div>
    );
  }

  // ── Vista standalone per la sidebar sinistra ──────────────────────────
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
          color: testo
        }}
      >
        {aperto ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <Layers size={13} color="#00f2fe" />
        <span>LAVORO IN PARALLELO</span>
        {totale > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.62rem',
            fontWeight: 800,
            color: inCorso ? '#00f2fe' : COLORE.done
          }}>
            {fatte}/{totale}
          </span>
        )}
      </div>

      {aperto && (
        <div style={{ padding: '0 10px 9px' }}>
          {renderContenuto()}
        </div>
      )}
    </div>
  );
}
