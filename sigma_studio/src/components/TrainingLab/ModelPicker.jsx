import React, { useCallback, useEffect, useRef, useState } from 'react';
import { HardDrive, Search, Download, Check, AlertTriangle, Loader2, Cloud } from 'lucide-react';
import InfoHint from './InfoHint';

// ==============================================================================
// ModelPicker — da dove parte il ciclo
// ==============================================================================
// Un modello ha due identita': il tag Ollama con cui lo si misura e i pesi con
// cui lo si addestra. Quasi tutti gli errori di questo pannello nascevano dal
// doverle scrivere a mano in due caselle di testo. Qui si sceglie una voce e le
// identita' arrivano gia' accoppiate, con scritto sopra cosa manca quando manca.

const SOURCE_BADGE = {
  job:    { label: 'nostro',      color: 'var(--success)' },
  cache:  { label: 'in cache',    color: 'var(--primary)' },
  ollama: { label: 'Ollama',      color: 'var(--text-dim)' },
  hf:     { label: 'HuggingFace', color: 'var(--warning)' },
};

const fmtGB = (v) => (v ? `${Number(v).toFixed(1)} GB` : '');
const fmtNum = (v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v || 0}`);

function Badge({ ok, children }) {
  return (
    <span style={{
      fontSize: '0.54rem', fontWeight: 700, padding: '1px 5px', borderRadius: '5px',
      textTransform: 'uppercase', letterSpacing: '0.03em', whiteSpace: 'nowrap',
      color: ok ? 'var(--success)' : 'var(--text-dark)',
      background: ok ? 'rgba(63,185,80,0.10)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${ok ? 'rgba(63,185,80,0.25)' : 'rgba(255,255,255,0.07)'}`,
    }}>
      {children}
    </span>
  );
}

function Row({ model: m, selected, onPick }) {
  const badge = SOURCE_BADGE[m.source] || SOURCE_BADGE.hf;
  return (
    <button
      onClick={() => onPick(m)}
      style={{
        display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
        padding: '7px 10px', marginBottom: '4px', borderRadius: '9px',
        border: `1px solid ${selected ? 'rgba(0,210,255,0.35)' : 'rgba(255,255,255,0.06)'}`,
        background: selected ? 'rgba(0,210,255,0.07)' : 'rgba(255,255,255,0.015)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
        {selected && <Check size={12} style={{ color: 'var(--primary)', flexShrink: 0 }} />}
        <span style={{
          fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
        }}>
          {m.label}
        </span>
        <span style={{ fontSize: '0.54rem', fontWeight: 700, color: badge.color,
                       textTransform: 'uppercase', letterSpacing: '0.03em' }}>
          {badge.label}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px', flexShrink: 0 }}>
          <Badge ok={m.can_eval}>misura</Badge>
          <Badge ok={m.can_train}>addestra</Badge>
        </div>
      </div>
      <div style={{
        fontSize: '0.6rem', color: 'var(--text-dim)', marginTop: '3px',
        display: 'flex', gap: '8px', flexWrap: 'wrap',
      }}>
        {m.size_gb ? <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{fmtGB(m.size_gb)}</span> : null}
        {m.source === 'hf' && <span>↓ {fmtNum(m.downloads)} · ♥ {fmtNum(m.likes)}</span>}
        <span>{m.detail}</span>
      </div>
      {!m.ready && (
        <div style={{
          fontSize: '0.58rem', color: 'var(--warning)', marginTop: '3px',
          display: 'flex', gap: '4px', alignItems: 'flex-start', lineHeight: 1.45,
        }}>
          <AlertTriangle size={10} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>{m.missing}</span>
        </div>
      )}
    </button>
  );
}

export default function ModelPicker({ value, onChange, addToast, disabled }) {
  const [source, setSource] = useState('local');
  const [local, setLocal] = useState([]);
  const [found, setFound] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [pull, setPull] = useState(null);
  const searchRef = useRef(0);

  const loadLocal = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/training/models/local');
      const j = await r.json();
      setLocal(j.models || []);
    } catch (e) { /* la lista resta vuota, il messaggio sotto lo dice */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadLocal(); }, [loadLocal]);

  // La ricerca parte da sola dopo mezzo secondo di quiete: digitando "qwen3"
  // sarebbero sei richieste, e HuggingFace le conta.
  useEffect(() => {
    if (source !== 'hf') return undefined;
    const q = query.trim();
    if (q.length < 2) { setFound([]); return undefined; }
    const ticket = ++searchRef.current;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const r = await fetch(`/api/training/models/search?q=${encodeURIComponent(q)}&limit=25`);
        const j = await r.json();
        if (ticket === searchRef.current) setFound(j.models || []);
      } catch (e) { /* idem */ }
      if (ticket === searchRef.current) setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [query, source]);

  // Un download di modello dura minuti: senza polling il pannello sembrerebbe
  // bloccato proprio mentre sta funzionando.
  useEffect(() => {
    if (!pull?.running) return undefined;
    const timer = setInterval(async () => {
      try {
        const r = await fetch('/api/training/models/pull_status');
        const j = await r.json();
        setPull(j.pull);
        if (j.pull?.done) { addToast && addToast('✅ Modello scaricato in Ollama.', 'success'); loadLocal(); }
        if (j.pull?.error) addToast && addToast(`❌ ${j.pull.error}`, 'error', 8000);
      } catch (e) { /* riproviamo al giro dopo */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [pull?.running, addToast, loadLocal]);

  // I repo con GGUF si scaricano diretti da Ollama, gli altri passano dal
  // convertitore: la differenza la sceglie il backend, non l'utente.
  const startPull = async (m) => {
    const r = await fetch('/api/training/models/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: m.train_model || m.label }),
    });
    const j = await r.json();
    if (j.success) setPull({ running: true, model: j.model, percent: 0, status: 'avvio' });
    else addToast && addToast(`❌ ${j.error}`, 'error', 8000);
  };

  const list = source === 'local' ? local : found;
  const picked = value?.key;

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px',
        fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)',
      }}>
        Modello di partenza
        <InfoHint entry={{
          label: 'Le due identità di un modello',
          what: 'Per misurarlo serve un tag Ollama, per addestrarlo servono i '
              + 'pesi: repo HuggingFace o cartella locale.',
          good: 'Le voci con entrambe le etichette verdi sono pronte: il ciclo '
              + 'può profilarle e specializzarle senza altri passaggi.',
          bad: 'Un modello pubblicato solo su Ollama si misura ma non si '
             + 'specializza; uno solo su HuggingFace va prima portato in Ollama.',
        }} />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
          {[['local', 'In locale', HardDrive], ['hf', 'HuggingFace', Cloud]].map(([id, label, Icon]) => (
            <button
              key={id} className="training-log-ctrl-btn" onClick={() => setSource(id)}
              style={{
                color: source === id ? 'var(--primary)' : 'var(--text-dim)',
                borderColor: source === id ? 'rgba(0,210,255,0.3)' : undefined,
                background: source === id ? 'rgba(0,210,255,0.06)' : undefined,
                fontWeight: source === id ? 700 : 500,
              }}
            >
              <Icon size={10} style={{ marginRight: '4px' }} /> {label}
            </button>
          ))}
        </div>
      </div>

      {source === 'hf' && (
        <div style={{ position: 'relative', marginBottom: '7px' }}>
          <Search size={12} style={{
            position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-dark)', pointerEvents: 'none',
          }} />
          <input
            className="training-input" value={query} autoFocus
            onChange={e => setQuery(e.target.value)}
            placeholder="cerca su HuggingFace (es. qwen3, llama, minerva)"
            style={{ fontSize: '0.66rem', paddingLeft: '26px' }}
          />
        </div>
      )}

      {pull?.running && (
        <div style={{
          marginBottom: '7px', padding: '7px 10px', borderRadius: '9px',
          border: '1px solid rgba(0,210,255,0.22)', background: 'rgba(0,210,255,0.05)',
          fontSize: '0.62rem', color: 'var(--text-dim)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Loader2 size={11} className="spin" style={{ color: 'var(--primary)' }} />
            <span style={{ color: 'var(--text)', fontWeight: 600 }}>{pull.model}</span>
            <span style={{ marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
              {pull.status} {pull.percent ? `${pull.percent}%` : ''}
            </span>
          </div>
          <div style={{
            height: '3px', borderRadius: '2px', marginTop: '5px',
            background: 'rgba(255,255,255,0.07)', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', width: `${pull.percent || 0}%`,
              background: 'var(--primary)', transition: 'width 0.4s',
            }} />
          </div>
        </div>
      )}

      <div style={{ maxHeight: '300px', overflowY: 'auto', paddingRight: '2px' }}>
        {loading && list.length === 0 && (
          <div style={{ fontSize: '0.63rem', color: 'var(--text-dark)', padding: '10px' }}>
            Cerco…
          </div>
        )}
        {!loading && list.length === 0 && (
          <div style={{ fontSize: '0.63rem', color: 'var(--text-dark)', padding: '10px', lineHeight: 1.5 }}>
            {source === 'hf'
              ? 'Scrivi almeno due lettere per cercare tra i modelli generativi di HuggingFace.'
              : 'Nessun modello in locale: installane uno in Ollama o scaricane uno dalla scheda HuggingFace.'}
          </div>
        )}
        {list.map(m => (
          <Row key={m.key} model={m} selected={picked === m.key}
               onPick={disabled ? () => {} : onChange} />
        ))}
      </div>

      {value && !value.can_eval && value.can_train && (
        <div style={{ marginTop: '7px' }}>
          <button
            className="training-btn" disabled={pull?.running}
            onClick={() => startPull(value)}
          >
            <Download size={11} /> Porta {value.label} in Ollama
          </button>
          <div className="training-field-desc" style={{ marginTop: '4px' }}>
            Non è obbligatorio: avviando il ciclo l'import parte da solo. Serve
            se vuoi misurare il modello prima di decidere.
          </div>
        </div>
      )}
    </div>
  );
}
