import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Terminal, Gauge, X, TrendingUp, Scale } from 'lucide-react';
import AutopilotPanel from './AutopilotPanel';
import TrainingMetrics from './TrainingMetrics';

// ==============================================================================
// AutopilotStudio — la tab del ciclo automatico
// ==============================================================================
// Lo Studio resta il percorso manuale: si sceglie, si configura, si avvia, si
// guarda. Qui invece si sceglie una volta sola e poi si osserva. Sono due modi
// di lavorare diversi e mescolarli rendeva entrambi confusi, per questo il
// ciclo automatico ha una pagina sua.
//
// Un ciclo che gira per ore va guardato mentre gira: a sinistra la scelta, lo
// stato e il diario, a destra il lavoro di questo momento — la curva di loss
// del training in corso, o l'avanzamento della valutazione.

// Il profilo e' la mappa: dove il modello e' debole, quanti quesiti lo dicono,
// e quali competenze il ciclo puo' ancora prendere di mira.
//
// Una riga per competenza, due misure sovrapposte: in **azzurro** il modello
// standard, quello da cui si e' partiti e che non cambia mai, e in **verde**
// quanto ci abbiamo guadagnato sopra. Cosi' il guadagno si legge come uno
// spessore, non come due numeri da sottrarre a mente. Su due colonne perche'
// diciannove suite in fila sono uno schermo intero di spazio sprecato.

function Riga({ s, bersaglio, etichetta }) {
  // Poche decine di quesiti non bastano a dire se un round ha funzionato:
  // la suite si vede, ma non e' un bersaglio.
  const magra = s.total < 8;
  const base = Math.round(s.prima * 100);
  const ora = Math.round((s.dopo === null ? s.prima : s.dopo) * 100);
  const guadagno = Math.max(0, ora - base);
  const perdita = Math.max(0, base - ora);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '7px', padding: '4px 8px',
      borderRadius: '7px',
      background: bersaglio ? 'rgba(0,210,255,0.05)' : 'transparent',
      border: `1px solid ${bersaglio ? 'rgba(0,210,255,0.18)' : 'transparent'}`,
    }}>
      <span style={{
        fontSize: '0.61rem', width: '118px', flexShrink: 0,
        color: magra ? 'var(--text-dark)' : 'var(--text)',
        fontWeight: bersaglio ? 700 : 500,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }} title={`${etichetta} — ${s.total} quesiti`}>
        {etichetta}
      </span>
      <div style={{
        flex: 1, minWidth: '46px', display: 'flex', height: '8px',
        borderRadius: '4px', overflow: 'hidden',
        background: 'rgba(255,255,255,0.05)',
        opacity: magra ? 0.45 : 1,
      }}>
        {/* Azzurro: il modello standard. Non si muove, e' il riferimento. */}
        <div style={{ width: `${base - perdita}%`, background: 'var(--primary)' }} />
        {/* Verde: quello che il ciclo ha aggiunto sopra. */}
        <div style={{ width: `${guadagno}%`, background: 'var(--success)' }} />
        {/* Rosso: quello che ha fatto perdere. */}
        <div style={{ width: `${perdita}%`, background: 'rgba(255,85,85,0.5)' }} />
      </div>
      <span style={{
        fontFamily: 'JetBrains Mono, monospace', fontSize: '0.6rem',
        width: '32px', textAlign: 'right', flexShrink: 0,
        color: magra ? 'var(--text-dark)' : 'var(--text)',
      }}>
        {ora}%
      </span>
      <span style={{
        fontFamily: 'JetBrains Mono, monospace', fontSize: '0.58rem',
        width: '34px', textAlign: 'right', flexShrink: 0, fontWeight: 700,
        color: guadagno ? 'var(--success)' : perdita ? 'var(--error)' : 'var(--text-dark)',
      }}>
        {guadagno ? `+${guadagno}` : perdita ? `-${perdita}` : '·'}
      </span>
      <span style={{
        fontSize: '0.56rem', width: '26px', textAlign: 'right', flexShrink: 0,
        color: 'var(--text-dark)',
      }}>
        {s.total}
      </span>
    </div>
  );
}

function Profilo({ state, targets, now, championLabel }) {
  const partenza = state?.profile || {};
  const adesso = now || {};
  const suites = Object.entries(partenza)
    .map(([suite, v]) => {
      const a = (v.passed || 0) / Math.max(1, v.total || 0);
      const dopo = adesso[suite];
      const b = dopo ? (dopo.passed || 0) / Math.max(1, dopo.total || 0) : null;
      return { suite, total: v.total || 0, prima: a, dopo: b };
    })
    .sort((a, b) => b.total - a.total || a.prima - b.prima);
  if (suites.length === 0) return null;

  const mirati = new Set((targets || []).map(t => t.suite));
  const etichette = Object.fromEntries((targets || []).map(t => [t.suite, t.label]));
  const cambiato = suites.some(s => s.dopo !== null && Math.abs(s.dopo - s.prima) > 0.0001);

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '4px',
        fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)',
      }}>
        <Gauge size={14} style={{ color: 'var(--primary)' }} />
        Profilo di {state.base_model || 'il modello'}
      </div>
      <div style={{
        fontSize: '0.59rem', color: 'var(--text-dark)', marginBottom: '9px',
        lineHeight: 1.5,
      }}>
        <span style={{ color: 'var(--primary)', fontWeight: 700 }}>■</span> modello standard
        {'  '}
        <span style={{ color: 'var(--success)', fontWeight: 700 }}>■</span>{' '}
        {cambiato ? `guadagno di ${championLabel || 'il campione'}`
                  : 'guadagno — ancora nessuno, il campione è il modello di partenza'}
        {' · numeri a destra: accuratezza, delta, quesiti'}
      </div>
      <div style={{
        display: 'grid', gap: '2px 14px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
      }}>
        {suites.map(s => (
          <Riga key={s.suite} s={s} bersaglio={mirati.has(s.suite)}
                etichetta={etichette[s.suite] || s.suite} />
        ))}
      </div>
    </div>
  );
}


// Un round in elenco dice solo il verdetto. Per capire *perche'* e' stato
// scartato servono le due meta' del lavoro: come e' andato l'addestramento —
// la curva della loss — e come si e' comportato il candidato quesito per
// quesito rispetto al campione.
function Confronto({ round: r }) {
  const misurato = r.wins !== undefined && r.wins !== null;
  if (!misurato) {
    return (
      <div style={{ fontSize: '0.63rem', color: 'var(--text-dim)', lineHeight: 1.6 }}>
        Questo round non e' arrivato a una misura: {r.verdict || 'interrotto'}.
        Non c'e' confronto da mostrare.
      </div>
    );
  }
  const voci = [
    ['Quesiti confrontati', r.items, 'quelli su cui entrambi hanno risposto'],
    ['Vinti dal candidato', r.wins, 'giusti per lui, sbagliati per il campione'],
    ['Persi', r.losses, 'il contrario'],
    ['Differenza', (r.delta > 0 ? '+' : '') + r.delta, 'vinti meno persi'],
    ['p di McNemar', r.p, 'sotto 0,05 la differenza non e’ rumore'],
  ];
  return (
    <div>
      <div style={{
        display: 'grid', gap: '6px', marginBottom: '10px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(104px, 1fr))',
      }}>
        {voci.map(([etichetta, valore, spiega]) => (
          <div key={etichetta} title={spiega} style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '9px', padding: '6px 9px',
          }}>
            <div style={{
              fontSize: '0.53rem', color: 'var(--text-dark)', textTransform: 'uppercase',
              letterSpacing: '0.04em', fontWeight: 700, marginBottom: '2px',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {etichetta}
            </div>
            <div style={{
              fontSize: '0.82rem', fontWeight: 700,
              fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)',
            }}>
              {valore}
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.65 }}>
        Accuratezza del candidato:{' '}
        <strong style={{ color: 'var(--text)' }}>
          {(r.selection_accuracy * 100).toFixed(1)}%
        </strong>{' '}
        sui quesiti di selezione,{' '}
        <strong style={{ color: 'var(--text)' }}>
          {(r.holdout_accuracy * 100).toFixed(1)}%
        </strong>{' '}
        su quelli di verifica, mai guardati per decidere.
        {r.selection_accuracy === 0 && (
          <div style={{ color: 'var(--warning)', marginTop: '5px' }}>
            Zero risposte valide non e’ un modello che ha imparato male: e’ un
            modello che non risponde. Di solito significa che ha perso il
            formato di conversazione nell’export.
          </div>
        )}
      </div>
    </div>
  );
}

function DettaglioRound({ round: r, onChiudi }) {
  const [metrics, setMetrics] = useState(null);
  const [vista, setVista] = useState('confronto');

  useEffect(() => {
    setMetrics(null);
    if (!r?.job_id) return undefined;
    let vivo = true;
    fetch(`/api/training/job/metrics?job_id=${r.job_id}`)
      .then(x => x.json())
      .then(j => { if (vivo && j.success) setMetrics(j); })
      .catch(() => {});
    return () => { vivo = false; };
  }, [r?.job_id]);

  if (!r) return null;
  const schede = [['confronto', 'Confronto', Scale], ['loss', 'Addestramento', TrendingUp]];

  return (
    <div style={{
      marginBottom: '18px', padding: '12px 14px', borderRadius: '12px',
      border: '1px solid rgba(0,210,255,0.22)', background: 'rgba(0,210,255,0.03)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px',
        fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)', flexWrap: 'wrap',
      }}>
        {r.label || r.suite}
        <span style={{ fontWeight: 400, color: 'var(--text-dim)' }}>· {r.dataset}</span>
        <span style={{
          fontFamily: 'JetBrains Mono, monospace', fontSize: '0.58rem',
          color: 'var(--text-dark)',
        }}>
          job {r.job_id}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
          {schede.map(([id, testo, Icona]) => (
            <button key={id} className="training-log-ctrl-btn" onClick={() => setVista(id)}
                    style={{
                      color: vista === id ? 'var(--primary)' : 'var(--text-dim)',
                      fontWeight: vista === id ? 700 : 500,
                    }}>
              <Icona size={10} style={{ marginRight: '4px' }} /> {testo}
            </button>
          ))}
          <button className="training-log-ctrl-btn" onClick={onChiudi} title="Chiudi">
            <X size={11} />
          </button>
        </div>
      </div>

      {vista === 'confronto' ? <Confronto round={r} /> : (
        metrics ? <TrainingMetrics metrics={metrics} /> : (
          <div style={{ fontSize: '0.63rem', color: 'var(--text-dark)', padding: '10px' }}>
            Nessuna metrica per questo job: gli artefatti potrebbero essere stati
            eliminati con la pulizia degli scarti.
          </div>
        )
      )}
    </div>
  );
}

export default function AutopilotStudio({ addToast }) {
  const [current, setCurrent] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [logs, setLogs] = useState([]);
  const [stato, setStato] = useState(null);
  const [targets, setTargets] = useState([]);
  const [profiloOra, setProfiloOra] = useState(null);
  const [campione, setCampione] = useState('');
  // Il modello che si sta guardando lo decide il selettore a sinistra: il
  // profilo deve seguirlo, altrimenti si sceglie un modello e si continua a
  // leggere le statistiche di un altro.
  const [modello, setModello] = useState('');
  const [roundScelto, setRoundScelto] = useState(null);

  const jobId = current?.id || '';
  const isTraining = current?.kind === 'training';

  // Il job in corso lo dichiara il ciclo stesso: la UI non deve indovinarlo.
  const loadCurrent = useCallback(async () => {
    try {
      const url = modello
        ? `/api/training/autopilot/status?model=${encodeURIComponent(modello)}`
        : '/api/training/autopilot/status';
      const r = await fetch(url);
      const j = await r.json();
      const cj = j.state?.current_job;
      setCurrent(cj && cj.id ? cj : null);
      setStato(j.state || null);
      setTargets(j.targets || []);
      setProfiloOra(j.profile_now || null);
      setCampione(j.champion_label || '');
    } catch (e) { /* la colonna resta su cio' che aveva */ }
  }, [modello]);

  useEffect(() => {
    loadCurrent();
    const timer = setInterval(loadCurrent, 5000);
    return () => clearInterval(timer);
  }, [loadCurrent]);

  // Metriche e log solo mentre c'e' un training: durante un benchmark non
  // esistono, e chiederle sarebbe traffico per un 404.
  useEffect(() => {
    if (!jobId || !isTraining) { setMetrics(null); setLogs([]); return undefined; }
    let alive = true;
    const tick = async () => {
      try {
        const [m, l] = await Promise.all([
          fetch(`/api/training/job/metrics?job_id=${jobId}`).then(r => r.json()),
          fetch(`/api/training/job/logs?job_id=${jobId}`).then(r => r.json()),
        ]);
        if (!alive) return;
        if (m.success) setMetrics(m);
        if (l.success) setLogs(l.lines || []);
      } catch (e) { /* riproviamo al giro dopo */ }
    };
    tick();
    const timer = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(timer); };
  }, [jobId, isTraining]);

  return (
    <div className="training-scroll-area training-studio-grid autopilot-studio-grid" style={{ paddingTop: '14px' }}>
      <aside className="training-studio-aside">
        <AutopilotPanel addToast={addToast} onModelloScelto={setModello}
                        onRoundScelto={setRoundScelto} />
      </aside>

      <div style={{ minWidth: 0 }}>
        {/* Il profilo sta in cima: e' la mappa del modello, e resta il primo
            dato da leggere anche mentre un training scorre. Metterlo sotto
            significava doverlo cercare ogni volta. */}
        {stato?.profile && Object.keys(stato.profile).length > 0 && (
          <div style={{ marginBottom: '18px' }}>
            <Profilo state={stato} targets={targets}
                     now={profiloOra} championLabel={campione} />
          </div>
        )}

        {roundScelto && (
          <DettaglioRound round={roundScelto} onChiudi={() => setRoundScelto(null)} />
        )}

        {current && (
          <div style={{ marginBottom: '18px' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px',
              fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)',
            }}>
              <Activity size={14} style={{ color: 'var(--primary)' }} />
              {current.label || current.kind}
              <span style={{
                fontFamily: 'JetBrains Mono, monospace', fontWeight: 500,
                fontSize: '0.6rem', color: 'var(--text-dark)',
              }}>
                job {current.id}
              </span>
            </div>

            {isTraining && metrics && <TrainingMetrics metrics={metrics} />}

            {isTraining && !metrics && (
              <div style={{ fontSize: '0.64rem', color: 'var(--text-dark)', padding: '10px' }}>
                Il training è partito: la curva compare al primo logging step.
              </div>
            )}

            {!isTraining && (
              <div style={{
                padding: '18px', fontSize: '0.65rem', color: 'var(--text-dim)',
                border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px',
                lineHeight: 1.6,
              }}>
                Valutazione in corso. Non produce una curva di loss: l'esito
                arriva nel diario e nei round, a sinistra, quando ha finito di
                interrogare il modello su tutti i quesiti.
              </div>
            )}

            {logs.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <div className="training-log-controls">
                  <div className="training-log-label">
                    <Terminal size={12} style={{ display: 'inline', marginRight: '5px' }} />
                    Log del job — {logs.length} righe
                  </div>
                </div>
                <div className="training-log-terminal" style={{ maxHeight: '260px' }}>
                  {logs.slice(-200).map((line, i) => (
                    <div key={i} className="log-line">{line}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!(stato?.profile && Object.keys(stato.profile).length > 0) && !current && (
          <div style={{
            padding: '22px 18px', fontSize: '0.66rem', color: 'var(--text-dark)',
            border: '1px dashed rgba(255,255,255,0.08)', borderRadius: '12px',
            lineHeight: 1.65,
          }}>
            Nessun lavoro in corso. Scegli un modello a sinistra e avvia il ciclo:
            comincerà misurandolo su tutte le suite, e qui comparirà il profilo —
            poi la curva di loss di ogni training, aggiornata mentre lavora.
          </div>
        )}
      </div>
    </div>
  );
}
