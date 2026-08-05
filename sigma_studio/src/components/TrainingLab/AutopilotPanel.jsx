import React, { useCallback, useEffect, useState } from 'react';
import { Bot, Play, Square, Trash2, RotateCcw, Target, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import InfoHint from './InfoHint';
import ModelPicker from './ModelPicker';

// ==============================================================================
// AutopilotPanel — il ciclo automatico, mentre lavora
// ==============================================================================
// Un ciclo che gira per ore da solo va guardato, non subìto: qui ci sono lo
// stato, i bersagli scelti, l'esito di ogni round con il suo test statistico, e
// il diario in tempo reale. Il pulsante che conta è quello per fermarlo — il
// ciclo si interrompe alla fine del passo corrente e riprende da lì.

const STATUS = {
  idle:        { label: 'fermo',        color: 'var(--text-dark)' },
  running:     { label: 'in corso',     color: 'var(--primary)' },
  stopped:     { label: 'fermato',      color: 'var(--warning)' },
  interrupted: { label: 'interrotto',   color: 'var(--error)' },
  done:        { label: 'concluso',     color: 'var(--success)' },
};

const fmtGB = (v) => `${Number(v || 0).toFixed(1)} GB`;

function Metric({ label, value, hint, tone }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '10px', padding: '7px 10px', minWidth: 0,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px',
        fontSize: '0.56rem', color: 'var(--text-dark)', textTransform: 'uppercase',
        letterSpacing: '0.04em', fontWeight: 700,
      }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
        <InfoHint entry={hint} />
      </div>
      <div style={{
        fontSize: '0.9rem', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace',
        color: tone || 'var(--text)',
      }}>
        {value}
      </div>
    </div>
  );
}

function Round({ round: r, selezionato, onApri }) {
  const ok = r.accepted;
  // Un round guasto non è arrivato a un confronto: mostrare "vince · perde ·
  // p =" con i valori vuoti faceva sembrare un pareggio quello che era un
  // errore da leggere.
  const rotto = r.broken || r.wins === undefined;
  const Icona = ok ? CheckCircle2 : rotto ? AlertTriangle : XCircle;
  const colore = ok ? 'var(--success)' : rotto ? 'var(--warning)' : 'var(--text-dark)';
  return (
    <div
      onClick={() => onApri && onApri(r)}
      title="Apri il dettaglio: curva della loss e confronto quesito per quesito"
      style={{
        display: 'flex', gap: '9px', padding: '7px 10px', borderRadius: '9px',
        marginBottom: '4px', border: '1px solid', cursor: onApri ? 'pointer' : 'default',
        borderColor: selezionato ? 'rgba(0,210,255,0.45)'
                   : ok ? 'rgba(63,185,80,0.22)'
                   : rotto ? 'rgba(255,184,108,0.22)' : 'rgba(255,255,255,0.06)',
        background: selezionato ? 'rgba(0,210,255,0.08)'
                  : ok ? 'rgba(63,185,80,0.05)'
                  : rotto ? 'rgba(255,184,108,0.04)' : 'rgba(255,255,255,0.015)',
      }}>
      <Icona size={13} style={{ color: colore, flexShrink: 0, marginTop: '2px' }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)' }}>
          {r.label || r.suite}
          <span style={{ fontWeight: 400, color: 'var(--text-dim)' }}> · {r.dataset || 'n/d'}</span>
        </div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', marginTop: '2px',
                      lineHeight: 1.5 }}>
          {!rotto && <>vince {r.wins} · perde {r.losses} · p = {r.p} </>}
          <span style={{ color: colore }}>{r.verdict}</span>
          {rotto && r.job_id && (
            <span style={{ marginLeft: '6px', color: 'var(--text-dark)',
                           fontFamily: 'JetBrains Mono, monospace' }}>
              job {r.job_id}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Campo({ etichetta, valore, onChange, hint, min, max, passo, suffisso }) {
  return (
    <label style={{ display: 'block', minWidth: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '3px',
        fontSize: '0.55rem', color: 'var(--text-dark)', textTransform: 'uppercase',
        letterSpacing: '0.04em', fontWeight: 700,
      }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {etichetta}
        </span>
        <InfoHint entry={hint} />
      </div>
      <div style={{ position: 'relative' }}>
        <input
          className="training-input" type="number" value={valore}
          min={min} max={max} step={passo || 1}
          onChange={e => onChange(e.target.value)}
          style={{ fontSize: '0.66rem', paddingRight: suffisso ? '38px' : undefined }}
        />
        {suffisso && (
          <span style={{
            position: 'absolute', right: '9px', top: '50%', transform: 'translateY(-50%)',
            fontSize: '0.55rem', color: 'var(--text-dark)', pointerEvents: 'none',
          }}>
            {suffisso}
          </span>
        )}
      </div>
    </label>
  );
}

export default function AutopilotPanel({ addToast, onModelloScelto, onRoundScelto }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  // I benchmark passano da Ollama, l'addestramento dai pesi: sono due
  // identita' diverse dello stesso modello, e per molti non coincidono. La
  // scelta le accoppia da sola; questa casella resta per i casi in cui
  // l'accoppiamento automatico sbaglia.
  const [picked, setPicked] = useState(null);
  const [weights, setWeights] = useState('');
  // Caricare un modello con architettura propria significa eseguire il
  // codice Python del suo repo. Va acceso a mano, ogni volta.
  const [fidarsi, setFidarsi] = useState(false);
  const [mostraScarti, setMostraScarti] = useState(false);
  const [roundAperto, setRoundAperto] = useState(null);
  const [confermaCancella, setConfermaCancella] = useState(false);
  // Quanto lavoro fare a ogni giro. Sono le tre manopole che decidono se un
  // ciclo dura venti minuti o venti ore, e finora erano sepolte nel codice.
  const [quesiti, setQuesiti] = useState(300);
  const [esempi, setEsempi] = useState(30000);
  const [contesto, setContesto] = useState(1024);
  // Riprendere vuol dire riprendere quello di prima: dopo un ricaricamento la
  // scelta e' vuota, ma il ciclo il suo modello ce l'ha nello stato salvato, e
  // obbligare a riselezionarlo era solo un passaggio in piu' per sbagliare.
  const salvato = data?.state?.base_model || '';
  const chosen = picked?.eval_model || (picked ? '' : salvato);
  const pesi = weights.trim() || (picked ? '' : (data?.state?.train_model || ''));
  // Un modello con i soli pesi si puo' comunque avviare: l'identita' di
  // valutazione la costruisce il ciclo come primo passo.
  const avviabile = Boolean(chosen || pesi);

  // Scegliere un modello deve mostrarne subito la storia — profilo, round,
  // campione — senza doverlo riavviare per scoprire che era gia' stato
  // misurato. Lo stato e' per modello, quindi basta chiederlo per nome.
  const guardato = picked?.eval_model || picked?.label || '';
  const load = useCallback(async () => {
    try {
      const url = guardato
        ? `/api/training/autopilot/status?model=${encodeURIComponent(guardato)}`
        : '/api/training/autopilot/status';
      const res = await fetch(url);
      const json = await res.json();
      if (json.success) setData(json);
    } catch (e) {}
  }, [guardato]);

  useEffect(() => { load(); }, [load]);

  const pick = useCallback((m) => {
    setPicked(m);
    setWeights(m.train_model || '');
    setFidarsi(false);
    onModelloScelto && onModelloScelto(m?.eval_model || m?.label || '');
  }, [onModelloScelto]);

  // Riprendendo un ciclo, le manopole devono mostrare quelle con cui stava
  // girando, non i valori di fabbrica.
  const salvate = data?.state;
  useEffect(() => {
    if (!salvate) return;
    if (salvate.items) setQuesiti(salvate.items);
    if (salvate.max_examples) setEsempi(salvate.max_examples);
    if (salvate.max_seq_length) setContesto(salvate.max_seq_length);
  }, [salvate?.base_model, salvate?.items, salvate?.max_examples, salvate?.max_seq_length]);

  // Mentre il ciclo lavora la pagina deve raccontarlo: senza polling il diario
  // resterebbe fermo all'ultimo stato letto all'apertura.
  const running = data?.running;
  useEffect(() => {
    const timer = setInterval(load, running ? 3000 : 15000);
    return () => clearInterval(timer);
  }, [running, load]);

  const call = async (path, body) => {
    setBusy(true);
    try {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      const json = await res.json();
      addToast && addToast(json.success ? (json.message || 'Fatto.') : `❌ ${json.error}`,
                           json.success ? 'success' : 'error', 6000);
      await load();
      return json;
    } catch (e) {
      addToast && addToast(`❌ ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  if (!data) return null;
  const state = data.state || {};
  const rounds = state.rounds || [];
  const accepted = rounds.filter(r => r.accepted).length;
  const style = STATUS[state.status] || STATUS.idle;
  const discardableGB = (data.discardable || []).reduce((s, d) => s + (d.gb || 0), 0);
  // Il ciclo ha gia' un profilo ma non ha piu' niente da provare: e' la
  // condizione in cui "Riprendi" sembra rotto.
  const senzaBersagli = (data.targets || []).length === 0
    && Object.keys(state.profile || {}).length > 0;

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '9px',
        fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)', flexWrap: 'wrap',
      }}>
        <Bot size={14} style={{ color: 'var(--primary)' }} />
        Ciclo automatico
        <span style={{ color: style.color, fontWeight: 600 }}>● {style.label}</span>
        <InfoHint entry={{
          label: 'Come decide',
          what: 'Profila il modello, sceglie la competenza più debole ancora '
              + 'migliorabile, addestra un adapter dalla base e lo misura.',
          good: 'Un round viene tenuto solo se batte il candidato corrente con '
              + 'un test appaiato: vincere qualche quesito in più non basta.',
          bad: 'Le decisioni si prendono su metà dei quesiti; l\'altra metà non '
             + 'viene mai guardata durante il ciclo, altrimenti il punteggio '
             + 'finale misurerebbe solo quanto il ciclo ha imparato i quesiti.',
        }} />

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
          {running ? (
            <button
              className="training-btn danger" disabled={busy}
              onClick={() => call('/api/training/autopilot/stop')}
            >
              <Square size={11} /> Ferma
            </button>
          ) : (
            <button
              className="training-btn primary" disabled={busy || !avviabile}
              title={!avviabile ? 'Scegli prima un modello'
                : picked && !picked.eval_model ? `${picked.label} non è in Ollama: il ciclo lo importa da solo prima di profilarlo`
                : !picked ? `Riprende su ${salvato}, il modello dello stato salvato`
                : state.rounds?.length ? 'Riprende dallo stato salvato'
                : 'Profila il modello e comincia'}
              onClick={() => call('/api/training/autopilot/start',
                { base_model: chosen, train_model: pesi,
                  trust_remote_code: fidarsi,
                  items: Number(quesiti) || 300,
                  max_examples: Number(esempi) || 30000,
                  max_seq_length: Number(contesto) || 1024 })}
            >
              <Play size={11} /> {state.rounds?.length ? 'Riprendi' : 'Avvia'}
            </button>
          )}
          {(data.discardable || []).length > 0 && (
            <button
              className="training-btn" disabled={busy}
              title="Mostra cosa verrebbe eliminato"
              onClick={() => setMostraScarti(v => !v)}
              style={{ color: mostraScarti ? 'var(--warning)' : undefined }}
            >
              <Trash2 size={11} /> Scarti: {fmtGB(discardableGB)}
            </button>
          )}
          {!running && rounds.length > 0 && (
            <button
              className="training-btn" disabled={busy}
              onClick={() => call('/api/training/autopilot/reset')}
            >
              <RotateCcw size={11} /> Azzera
            </button>
          )}
        </div>
      </div>

      {/* Un ciclo senza bersagli riparte e conclude nello stesso secondo: da
          fuori sembra che il pulsante non funzioni. Va detto, e va offerta la
          via d'uscita — riaprire i bersagli gia' provati. */}
      {!running && senzaBersagli && (
        <div style={{
          marginBottom: '10px', padding: '10px 12px', borderRadius: '10px',
          border: '1px solid rgba(255,184,108,0.25)', background: 'rgba(255,184,108,0.05)',
        }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--warning)' }}>
            Nessun bersaglio disponibile
          </div>
          <div style={{
            fontSize: '0.61rem', color: 'var(--text-dim)', lineHeight: 1.55, marginTop: '4px',
          }}>
            Le competenze misurabili sono già state provate e scartate, e le altre
            hanno troppi pochi quesiti perché un miglioramento si veda. Premendo
            Riprendi il ciclo riparte e conclude nello stesso istante.
          </div>
          <button
            className="training-btn" disabled={busy}
            style={{ marginTop: '8px' }}
            onClick={() => call('/api/training/autopilot/reopen',
                                { model: state.base_model })}
          >
            <RotateCcw size={11} /> Riapri i bersagli provati
          </button>
          <div className="training-field-desc" style={{ marginTop: '4px' }}>
            Serve quando i verdetti precedenti erano viziati: i round restano in
            elenco ma non contano più come misure. Quelli accettati non si toccano.
          </div>
        </div>
      )}

      {!running && (
        <div style={{ marginBottom: '11px' }}>
          <ModelPicker value={picked} onChange={pick} addToast={addToast} cycles={data?.cycles} />
          <input
            className="training-input" value={weights}
            onChange={e => setWeights(e.target.value)}
            placeholder="pesi da addestrare (repo HuggingFace o cartella locale)"
            style={{ fontSize: '0.66rem', marginTop: '7px' }}
          />
          <div className="training-field-desc" style={{ marginTop: '3px' }}>
            Compilata dalla scelta qui sopra. Cambiala solo se i pesi accoppiati
            non sono quelli giusti: se resta vuota, il ciclo prova a dedurli dal
            nome Ollama e si ferma subito se non li trova.
          </div>

          {/* Le tre manopole che decidono se un ciclo dura venti minuti o venti
              ore. Restano scritte nello stato del modello: riprendendo si
              ritrovano quelle con cui stava girando. */}
          <div style={{
            display: 'grid', gap: '8px', marginTop: '10px',
            gridTemplateColumns: 'repeat(auto-fit, minmax(112px, 1fr))',
          }}>
            <Campo
              etichetta="Quesiti per misura" valore={quesiti} onChange={setQuesiti}
              min={40} max={3000} passo={20}
              hint={{
                label: 'Quanti quesiti per ogni valutazione',
                what: 'Il numero di domande su cui si misura il modello, sia '
                    + 'all’inizio sia dopo ogni round.',
                good: 'Metà guida le decisioni e metà resta da parte: con 300 '
                    + 'restano 150 per decidere, abbastanza perché il test '
                    + 'appaiato distingua un miglioramento dal rumore.',
                bad: 'Sotto i 100 le suite finiscono con pochi quesiti ciascuna '
                   + 'e nessun round riesce più a risultare significativo. '
                   + 'Sopra i 600 ogni misura costa minuti, e se ne fanno due '
                   + 'per round.',
              }} />
            <Campo
              etichetta="Esempi per epoca" valore={esempi} onChange={setEsempi}
              min={200} max={200000} passo={1000}
              hint={{
                label: 'Quanti esempi di training per round',
                what: 'Il taglio del dataset su cui si addestra ogni adapter. '
                    + 'Il campione è mescolato con seme fisso, non i primi N.',
                good: 'Con 30.000 esempi e batch efficace 30 fanno ~1000 passi: '
                    + 'un round di qualche decina di minuti.',
                bad: 'MetaMathQA ha 395.000 esempi: un’epoca intera sono ore '
                   + 'per un guadagno che si vede molto prima.',
              }} />
            <Campo
              etichetta="Contesto" valore={contesto} onChange={setContesto}
              min={128} max={8192} passo={128} suffisso="tok"
              hint={{
                label: 'Lunghezza massima delle sequenze',
                what: 'Quanti token al massimo per esempio: oltre, il testo '
                    + 'viene troncato.',
                good: '1024 copre la gran parte delle conversazioni dei dataset '
                    + 'usati dal ciclo.',
                bad: 'La memoria cresce con il **quadrato** del contesto: '
                   + 'raddoppiarlo la quadruplica, ed è la via più rapida per '
                   + 'saturare la scheda.',
              }} />
          </div>
          {picked?.custom_code && (
            <label style={{
              display: 'flex', gap: '7px', alignItems: 'flex-start', marginTop: '8px',
              padding: '8px 10px', borderRadius: '9px', cursor: 'pointer',
              border: `1px solid ${fidarsi ? 'rgba(255,184,108,0.35)' : 'rgba(255,255,255,0.08)'}`,
              background: fidarsi ? 'rgba(255,184,108,0.06)' : 'rgba(255,255,255,0.015)',
            }}>
              <input type="checkbox" checked={fidarsi}
                     onChange={e => setFidarsi(e.target.checked)}
                     style={{ marginTop: '2px', accentColor: 'var(--warning)' }} />
              <span style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>
                <strong style={{ color: 'var(--warning)' }}>
                  {picked.label} ha un'architettura propria.
                </strong>{' '}
                Per caricarlo Sigma deve scaricare ed <strong>eseguire il codice
                Python contenuto nel repo</strong>. Senza questa spunta il job
                fallisce al caricamento. Accendila solo se ti fidi di chi
                pubblica quel repo.
              </span>
            </label>
          )}
        </div>
      )}

      <div style={{
        display: 'grid', gap: '6px', marginBottom: '10px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))',
      }}>
        <Metric label="Round" value={`${accepted}/${rounds.length}`}
                hint={{ label: 'Round accettati sul totale',
                        what: 'Quanti tentativi hanno davvero migliorato il modello.' }} />
        <Metric label="Bersagli rimasti" value={(data.targets || []).length}
                hint={{ label: 'Competenze ancora migliorabili',
                        what: 'Suite sotto il soffitto di accuratezza e misurate su '
                            + 'abbastanza quesiti perché un miglioramento si veda.' }} />
        <Metric label="Da liberare" value={fmtGB(discardableGB)}
                tone={discardableGB > 20 ? 'var(--warning)' : undefined}
                hint={{ label: 'Spazio dei round scartati',
                        what: 'Artefatti di round che non hanno battuto il campione: '
                            + 'si possono cancellare senza perdere nulla.' }} />
        <Metric label="Campione"
                value={state.champion?.holdout_accuracy != null
                  ? `${(state.champion.holdout_accuracy * 100).toFixed(1)}%`
                  : '—'}
                tone={state.champion?.published ? 'var(--success)' : undefined}
                hint={{ label: 'Il migliore finora, sul set di verifica',
                        what: 'Accuratezza sui quesiti che il ciclo non ha mai guardato '
                            + 'per decidere. È il solo numero onesto da comunicare.',
                        good: 'Quando è pubblicato lo trovi come `ollama run sigma-champion`.' }} />
      </div>

      {/* Cancellare artefatti e' irreversibile: prima si mostra la lista di
          cosa sparisce — cartelle e modelli Ollama — poi si conferma. Un
          pulsante che elimina al primo clic, in un pannello che gira per ore
          da solo, e' un incidente che aspetta di succedere. */}
      {mostraScarti && (data.discardable || []).length > 0 && (
        <div style={{
          marginBottom: '10px', padding: '9px 11px', borderRadius: '10px',
          border: '1px solid rgba(255,184,108,0.25)', background: 'rgba(255,184,108,0.05)',
        }}>
          <div style={{
            fontSize: '0.63rem', fontWeight: 700, color: 'var(--warning)',
            marginBottom: '6px',
          }}>
            {data.discardable.length} round scartati — {fmtGB(discardableGB)} da liberare
          </div>
          {data.discardable.map(d => (
            <div key={d.job_id} style={{
              fontSize: '0.6rem', color: 'var(--text-dim)', lineHeight: 1.6,
              display: 'flex', gap: '8px', flexWrap: 'wrap',
            }}>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text)' }}>
                {d.job_id}
              </span>
              <span>{d.suite}</span>
              <span style={{ color: 'var(--text-dark)' }}>{d.reason}</span>
              {d.merge_job_id && <span>+ merge {d.merge_job_id}</span>}
              {d.ollama_model && (
                <span style={{ color: 'var(--warning)' }}>+ Ollama {d.ollama_model}</span>
              )}
              <span style={{ marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
                {fmtGB(d.gb)}
              </span>
            </div>
          ))}
          <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
            <button
              className="training-btn danger" disabled={busy}
              onClick={async () => {
                await call('/api/training/autopilot/cleanup', { dry_run: false });
                setMostraScarti(false);
              }}
            >
              <Trash2 size={11} /> Elimina definitivamente
            </button>
            <button className="training-btn" onClick={() => setMostraScarti(false)}>
              Annulla
            </button>
          </div>
          <div className="training-field-desc" style={{ marginTop: '5px' }}>
            Spariscono cartelle dei job, modelli fusi e le copie in Ollama. I
            round accettati e il campione non vengono toccati.
          </div>
        </div>
      )}

      {(data.targets || []).length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '5px',
            fontSize: '0.6rem', color: 'var(--text-dark)', textTransform: 'uppercase',
            letterSpacing: '0.04em', fontWeight: 700,
          }}>
            <Target size={11} /> Prossimi bersagli
          </div>
          {data.targets.slice(0, 4).map(t => (
            <div key={t.suite} style={{
              display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 9px',
              fontSize: '0.63rem', color: 'var(--text-dim)',
            }}>
              <span style={{ color: 'var(--text)', fontWeight: 600, minWidth: '150px' }}>
                {t.label}
              </span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                {(t.accuracy * 100).toFixed(0)}% su {t.items} quesiti
              </span>
              <span style={{ marginLeft: 'auto', color: 'var(--text-dark)' }}>
                {t.datasets[0]}
              </span>
            </div>
          ))}
        </div>
      )}

      {rounds.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="training-chart-title" style={{ flex: 1 }}>Round eseguiti</div>
            {/* Riaprire lascia il round in elenco; cancellare lo butta con i
                suoi artefatti. Serve quando la misura era viziata da un
                difetto poi corretto, e tenerne traccia confonde e basta. */}
            <button
              className="training-log-ctrl-btn" disabled={busy || running}
              title="Cancella tutti i round e torna allo stato precedente"
              onClick={() => setConfermaCancella(true)}
              style={{ color: 'var(--text-dim)' }}
            >
              <Trash2 size={10} /> Cancella
            </button>
          </div>
          {confermaCancella && (
            <div style={{
              padding: '9px 11px', borderRadius: '9px', marginBottom: '6px',
              border: '1px solid rgba(255,85,85,0.25)', background: 'rgba(255,85,85,0.05)',
            }}>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.55 }}>
                Spariscono i {rounds.length} round con le loro cartelle e i modelli
                in Ollama. Profilo e campione restano; se il campione veniva da un
                round cancellato torna il modello di partenza.
              </div>
              <div style={{ display: 'flex', gap: '6px', marginTop: '7px' }}>
                <button
                  className="training-btn danger" disabled={busy}
                  onClick={async () => {
                    await call('/api/training/autopilot/drop_rounds',
                               { model: state.base_model, quanti: 0 });
                    setConfermaCancella(false);
                    setRoundAperto(null);
                    onRoundScelto && onRoundScelto(null);
                  }}
                >
                  <Trash2 size={11} /> Cancella tutti
                </button>
                <button className="training-btn" onClick={() => setConfermaCancella(false)}>
                  Annulla
                </button>
              </div>
            </div>
          )}
          {rounds.slice().reverse().map((r, i) => (
            <Round key={r.job_id || i} round={r}
                   selezionato={roundAperto === (r.job_id || i)}
                   onApri={(scelto) => {
                     const chiave = scelto.job_id || i;
                     const stesso = roundAperto === chiave;
                     setRoundAperto(stesso ? null : chiave);
                     onRoundScelto && onRoundScelto(stesso ? null : scelto);
                   }} />
          ))}
        </div>
      )}

      {(state.log || []).length > 0 && (
        <div>
          <div className="training-chart-title">Diario</div>
          <div style={{
            maxHeight: '190px', overflowY: 'auto', borderRadius: '9px',
            border: '1px solid rgba(255,255,255,0.06)', padding: '7px 10px',
            background: 'rgba(0,0,0,0.25)', fontSize: '0.62rem',
            fontFamily: 'JetBrains Mono, monospace', lineHeight: 1.55,
          }}>
            {state.log.slice(-60).reverse().map((entry, i) => (
              <div key={i} style={{
                color: entry.level === 'error' ? 'var(--error)'
                     : entry.level === 'warning' ? 'var(--warning)' : 'var(--text-dim)',
              }}>
                <span style={{ color: 'var(--text-dark)' }}>{(entry.at || '').slice(11, 19)} </span>
                {entry.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
