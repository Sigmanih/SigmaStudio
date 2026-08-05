import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { HardDrive, Search, Download, Check, AlertTriangle, Loader2, Cloud, Clock, Target, X } from 'lucide-react';
import InfoHint from './InfoHint';

// ==============================================================================
// ModelPicker — da dove parte il ciclo (Riorganizzato & Arricchito)
// ==============================================================================

const SOURCE_BADGE = {
  job:    { label: 'nostro',      color: 'var(--success)', bg: 'rgba(63,185,80,0.12)' },
  cache:  { label: 'in cache',    color: 'var(--primary)', bg: 'rgba(0,210,255,0.12)' },
  ollama: { label: 'Ollama',      color: '#bc8cff', bg: 'rgba(188,140,255,0.12)' },
  hf:     { label: 'HuggingFace', color: 'var(--warning)', bg: 'rgba(255,184,108,0.12)' },
};

const fmtGB = (v) => (v ? `${Number(v).toFixed(1)} GB` : '');
const fmtNum = (v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : `${v || 0}`);

function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 60) return 'ora';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m fa`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h fa`;
    const days = Math.floor(diffSec / 86400);
    if (days === 1) return 'ieri';
    if (days < 30) return `${days}gg fa`;
    return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
  } catch (e) {
    return dateStr;
  }
}

function Badge({ ok, children, color, bg }) {
  return (
    <span style={{
      fontSize: '0.55rem', fontWeight: 700, padding: '2px 6px', borderRadius: '5px',
      textTransform: 'uppercase', letterSpacing: '0.03em', whiteSpace: 'nowrap',
      color: color || (ok ? 'var(--success)' : 'var(--text-dark)'),
      background: bg || (ok ? 'rgba(63,185,80,0.10)' : 'rgba(255,255,255,0.04)'),
      border: `1px solid ${color ? 'rgba(255,255,255,0.08)' : ok ? 'rgba(63,185,80,0.25)' : 'rgba(255,255,255,0.07)'}`,
    }}>
      {children}
    </span>
  );
}

function Row({ model: m, selected, onPick }) {
  const sources = m.sources && m.sources.length > 0 ? m.sources : [m.source || 'hf'];
  const acc = m.accuracy_pct !== undefined && m.accuracy_pct !== null ? m.accuracy_pct : null;
  const relTime = formatRelativeTime(m.last_run_at);

  return (
    <div
      onClick={() => onPick(m)}
      style={{
        display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
        padding: '10px 12px', marginBottom: '6px', borderRadius: '10px',
        border: `1px solid ${selected ? 'rgba(0,210,255,0.45)' : 'rgba(255,255,255,0.07)'}`,
        background: selected ? 'rgba(0,210,255,0.09)' : 'rgba(255,255,255,0.02)',
        boxShadow: selected ? '0 0 12px rgba(0,210,255,0.12)' : 'none',
        transition: 'all 0.15s ease-in-out',
      }}
    >
      {/* Prima riga: Nome Modello ben visibile */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '5px' }}>
        {selected && <Check size={14} style={{ color: 'var(--primary)', flexShrink: 0, marginTop: '2px' }} />}
        
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '0.81rem', fontWeight: 700, color: 'var(--text)',
            lineHeight: 1.35, wordBreak: 'break-word', letterSpacing: '-0.01em',
          }}>
            {m.label}
          </div>
        </div>

        {/* Accuracy badge if available */}
        {acc !== null && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '3px',
            padding: '2px 7px', borderRadius: '6px',
            background: 'rgba(0,210,255,0.12)', border: '1px solid rgba(0,210,255,0.3)',
            color: 'var(--primary)', fontSize: '0.62rem', fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace', flexShrink: 0,
          }} title="Accuratezza globale (risposte corrette)">
            <Target size={10} />
            <span>{acc}%</span>
          </div>
        )}
      </div>

      {/* Seconda riga: Fonti, Badges & Dettagli */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap',
        fontSize: '0.61rem', color: 'var(--text-dim)', marginTop: '4px',
      }}>
        {sources.map(src => {
          const b = SOURCE_BADGE[src] || SOURCE_BADGE.hf;
          return (
            <Badge key={src} color={b.color} bg={b.bg}>
              {b.label}
            </Badge>
          );
        })}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px', flexShrink: 0 }}>
          <Badge ok={m.can_eval}>misura</Badge>
          <Badge ok={m.can_train}>addestra</Badge>
        </div>
      </div>

      {/* Terza riga: Dettagli tecnici e Tempo Avvio */}
      <div style={{
        fontSize: '0.6rem', color: 'var(--text-dark)', marginTop: '4px',
        display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap',
      }}>
        {m.size_gb ? <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-dim)' }}>{fmtGB(m.size_gb)}</span> : null}
        {m.source === 'hf' && <span>↓ {fmtNum(m.downloads)} · ♥ {fmtNum(m.likes)}</span>}
        {m.detail && <span>{m.detail}</span>}

        {relTime && (
          <span style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '3px',
            color: 'var(--primary)', fontSize: '0.58rem', fontWeight: 600,
          }}>
            <Clock size={9} /> Avviato {relTime}
          </span>
        )}
      </div>

      {!m.ready && (
        <div style={{
          fontSize: '0.58rem', color: 'var(--warning)', marginTop: '5px',
          display: 'flex', gap: '4px', alignItems: 'flex-start', lineHeight: 1.45,
          background: 'rgba(255,184,108,0.06)', padding: '4px 7px', borderRadius: '6px',
        }}>
          <AlertTriangle size={10} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>{m.missing}</span>
        </div>
      )}
    </div>
  );
}

export default function ModelPicker({ value, onChange, addToast, disabled, cycles }) {
  const [source, setSource] = useState('recent'); // 'recent' | 'local' | 'hf'
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
    } catch (e) {}
    setLoading(false);
  }, []);

  useEffect(() => { loadLocal(); }, [loadLocal]);

  // HuggingFace async search
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
      } catch (e) {}
      if (ticket === searchRef.current) setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [query, source]);

  // Status pull polling
  useEffect(() => {
    if (!pull?.running) return undefined;
    const timer = setInterval(async () => {
      try {
        const r = await fetch('/api/training/models/pull_status');
        const j = await r.json();
        setPull(j.pull);
        if (j.pull?.done) { addToast && addToast('✅ Modello scaricato in Ollama.', 'success'); loadLocal(); }
        if (j.pull?.error) addToast && addToast(`❌ ${j.pull.error}`, 'error', 8000);
      } catch (e) {}
    }, 2000);
    return () => clearInterval(timer);
  }, [pull?.running, addToast, loadLocal]);

  const startPull = async (m) => {
    const r = await fetch('/api/training/models/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: m.train_model || m.label }),
    });
    const j = await r.json();
    if (j.success) setPull({ running: true, model: j.model, percent: 0, status: 'avvio' });
    else addToast && addToast(`❌ ${j.error}`, 'error', 8000);
  };

  // Costruzione lista Recenti (ordinati per ultimo avvio decrescente)
  const recentModels = useMemo(() => {
    if (!local || local.length === 0) return [];
    const recents = local.filter(m => Boolean(m.last_run_at));
    return recents.sort((a, b) => new Date(b.last_run_at) - new Date(a.last_run_at));
  }, [local]);

  // Se non ci sono recenti, passa automaticamente a 'local'
  useEffect(() => {
    if (source === 'recent' && recentModels.length === 0 && local.length > 0) {
      setSource('local');
    }
  }, [recentModels.length, local.length, source]);

  // Filtraggio lista locale/recenti basato su query di ricerca
  const displayedList = useMemo(() => {
    let rawList = [];
    if (source === 'recent') rawList = recentModels;
    else if (source === 'local') rawList = local;
    else if (source === 'hf') rawList = found;

    if (source !== 'hf' && query.trim()) {
      const q = query.toLowerCase().trim();
      return rawList.filter(m => 
        (m.label || '').toLowerCase().includes(q) ||
        (m.eval_model || '').toLowerCase().includes(q) ||
        (m.train_model || '').toLowerCase().includes(q)
      );
    }
    return rawList;
  }, [source, recentModels, local, found, query]);

  const picked = value?.key;

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '9px',
        fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)', flexWrap: 'wrap',
      }}>
        <span>Modello di partenza</span>
        <InfoHint entry={{
          label: 'Le due identità di un modello',
          what: 'Per misurarlo serve un tag Ollama, per addestrarlo servono i pesi HuggingFace o locali.',
          good: 'Le voci con le etichette "misura" e "addestra" attive sono pronte all\'uso immediato.',
          bad: 'Se manca una delle due identità, il ciclo la prepara automaticamente prima di partire.',
        }} />

        {/* Tab switcher: Recenti | Locali | HuggingFace */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {[
            ['recent', `Recenti (${recentModels.length})`, Clock],
            ['local', `Locali (${local.length})`, HardDrive],
            ['hf', 'HuggingFace', Cloud],
          ].map(([id, label, Icon]) => (
            <button
              key={id}
              className="training-log-ctrl-btn"
              onClick={() => setSource(id)}
              style={{
                color: source === id ? 'var(--primary)' : 'var(--text-dim)',
                borderColor: source === id ? 'rgba(0,210,255,0.35)' : 'rgba(255,255,255,0.06)',
                background: source === id ? 'rgba(0,210,255,0.08)' : 'rgba(255,255,255,0.02)',
                fontWeight: source === id ? 700 : 500,
                padding: '3px 8px', borderRadius: '7px',
              }}
            >
              <Icon size={11} style={{ marginRight: '4px' }} /> {label}
            </button>
          ))}
        </div>
      </div>

      {/* Barra di ricerca grafica unificata */}
      <div style={{ position: 'relative', marginBottom: '8px' }}>
        <Search size={13} style={{
          position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)',
          color: 'var(--text-dark)', pointerEvents: 'none',
        }} />
        <input
          className="training-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={
            source === 'hf'
              ? "Cerca su HuggingFace (es. qwen2.5, llama3, minerva)..."
              : "Filtra modelli..."
          }
          style={{
            fontSize: '0.68rem', paddingLeft: '28px', paddingRight: query ? '28px' : '10px',
            background: 'rgba(255,255,255,0.03)', borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            style={{
              position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)',
              background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer',
              padding: '2px', borderRadius: '4px', display: 'flex', alignItems: 'center',
            }}
            title="Cancella ricerca"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {pull?.running && (
        <div style={{
          marginBottom: '8px', padding: '8px 11px', borderRadius: '9px',
          border: '1px solid rgba(0,210,255,0.22)', background: 'rgba(0,210,255,0.05)',
          fontSize: '0.62rem', color: 'var(--text-dim)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Loader2 size={12} className="spin" style={{ color: 'var(--primary)' }} />
            <span style={{ color: 'var(--text)', fontWeight: 600 }}>{pull.model}</span>
            <span style={{ marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace' }}>
              {pull.status} {pull.percent ? `${pull.percent}%` : ''}
            </span>
          </div>
          <div style={{
            height: '4px', borderRadius: '2px', marginTop: '6px',
            background: 'rgba(255,255,255,0.07)', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', width: `${pull.percent || 0}%`,
              background: 'var(--primary)', transition: 'width 0.4s',
            }} />
          </div>
        </div>
      )}

      {/* Lista Modelli con max height scrollabile */}
      <div style={{ maxHeight: '340px', overflowY: 'auto', paddingRight: '3px' }}>
        {loading && displayedList.length === 0 && (
          <div style={{ fontSize: '0.64rem', color: 'var(--text-dark)', padding: '12px', textAlign: 'center' }}>
            Caricamento modelli in corso...
          </div>
        )}

        {!loading && displayedList.length === 0 && (
          <div style={{ fontSize: '0.64rem', color: 'var(--text-dark)', padding: '14px', lineHeight: 1.5, textAlign: 'center' }}>
            {source === 'recent'
              ? 'Nessun modello avviato di recente.'
              : source === 'hf'
              ? 'Digita almeno due caratteri per cercare su HuggingFace.'
              : 'Nessun modello trovato in locale.'}
          </div>
        )}

        {displayedList.map(m => (
          <Row
            key={m.key || m.label}
            model={m}
            selected={picked === m.key || (value?.label === m.label)}
            onPick={disabled ? () => {} : onChange}
          />
        ))}
      </div>

      {value && !value.can_eval && value.can_train && (
        <div style={{ marginTop: '8px' }}>
          <button
            className="training-btn" disabled={pull?.running}
            onClick={() => startPull(value)}
          >
            <Download size={11} /> Importa {value.label} in Ollama
          </button>
          <div className="training-field-desc" style={{ marginTop: '4px' }}>
            L'importazione partirà automaticamente all'avvio del ciclo se non effettuata prima.
          </div>
        </div>
      )}
    </div>
  );
}
