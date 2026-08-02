import React, { useCallback, useEffect, useState } from 'react';
import { Play, Pause, Square, GitMerge, ArrowDownToLine, Package, Award, Trash2, Layers, Sliders } from 'lucide-react';
import InfoHint from './InfoHint';

// ==============================================================================
// PipelinePanel — la catena di specializzazioni e le azioni su ogni fase
// ==============================================================================
// Specializzare un modello per fasi (LoRA → merge → nuova base → LoRA) ha senso
// solo se la catena si vede tutta insieme: è così che si capisce se una fase ha
// davvero migliorato quella prima, e da quale ripartire se non ha funzionato.
//
// Ogni nodo espone soltanto le azioni che i suoi artefatti su disco rendono
// possibili: il backend le calcola guardando le cartelle, non lo stato dichiarato.

const ACTIONS = {
  start: {
    label: 'Avvia', icon: Play, tone: 'primary',
    hint: { label: 'Avvia il run', what: 'Lancia lo script di questa fase. Se era già partito e si è fermato, riparte da capo.' },
  },
  pause: {
    label: 'Pausa', icon: Pause, tone: 'normal',
    hint: {
      label: 'Sospendi senza perdere nulla',
      what: 'Il processo si ferma esattamente dove si trova e riprende identico: '
          + 'non riparte da un checkpoint e non perde gli step fatti.',
      bad: 'La VRAM resta occupata. Per liberare la GPU — per esempio per un '
         + 'benchmark — il run va fermato, non messo in pausa.',
    },
  },
  resume: {
    label: 'Riprendi', icon: Play, tone: 'primary',
    hint: { label: 'Riprendi da dove era', what: 'Il processo torna a girare dallo stesso punto.' },
  },
  stop: {
    label: 'Ferma', icon: Square, tone: 'danger',
    hint: { label: 'Ferma il run', what: 'Interrompe il processo. I checkpoint già salvati restano.' },
  },
  tune: {
    label: 'Regola', icon: Sliders, tone: 'normal',
    hint: {
      label: 'Cambia batch e accumulation prima di ripartire',
      what: 'Serve quando un run non entra in VRAM: lo si ferma, si alleggerisce '
          + 'il batch e si riparte dal checkpoint invece che da zero.',
      good: 'Tenendo costante il batch effettivo (batch x accumulation) il numero '
          + 'di step non cambia, quindi il checkpoint indica ancora lo stesso '
          + 'punto e la ripresa è esatta.',
      bad: 'Cambiando il batch effettivo cambiano gli step totali, e i checkpoint '
         + 'esistenti non corrispondono più allo stesso punto del training.',
    },
  },
  merge: {
    label: 'Merge', icon: GitMerge, tone: 'accent',
    hint: {
      label: 'Fondi l\'adapter nel modello',
      what: 'Produce un modello autonomo che incorpora quello che questa fase ha imparato. '
          + 'È il punto di partenza della fase successiva.',
      good: 'Da fare quando la fase ha dato i risultati che volevi: da lì in poi è reversibile, '
          + 'perché la fase precedente resta intatta.',
      bad: 'Costa ~18 GB su disco per un modello da 9B, e diversi minuti.',
    },
  },
  continue: {
    label: 'Continua', icon: ArrowDownToLine, tone: 'primary',
    hint: {
      label: 'Aggiungi una fase',
      what: 'Crea il job successivo della catena, di norma su un dataset diverso, '
          + 'per aggiungere una competenza.',
    },
  },
  export: {
    label: 'Export', icon: Package, tone: 'normal',
    hint: { label: 'Porta il modello in Ollama', what: 'Con quantizzazione facoltativa, per provarlo subito in chat.' },
  },
  benchmark: {
    label: 'Valuta', icon: Award, tone: 'normal',
    hint: {
      label: 'Misura questa fase',
      what: 'Manda il modello ai benchmark ufficiali per confrontarlo con la fase precedente.',
      good: 'Valutare ogni anello è ciò che rende la catena confrontabile invece che una scommessa.',
    },
  },
  delete: {
    label: 'Elimina', icon: Trash2, tone: 'danger',
    hint: { label: 'Cancella la fase', what: 'Rimuove job, log e artefatti. Le fasi successive restano ma perdono la loro base.' },
  },
};

const TONE = {
  primary: { color: 'var(--primary)', border: 'rgba(0,210,255,0.3)', bg: 'rgba(0,210,255,0.07)' },
  accent:  { color: 'var(--accent)', border: 'rgba(188,140,255,0.3)', bg: 'rgba(188,140,255,0.07)' },
  danger:  { color: 'var(--error)', border: 'rgba(255,85,85,0.25)', bg: 'rgba(255,85,85,0.06)' },
  normal:  { color: 'var(--text-dim)', border: 'rgba(255,255,255,0.08)', bg: 'transparent' },
};

const STATUS_TONE = {
  running: 'var(--primary)', paused: 'var(--warning)', completed: 'var(--success)',
  failed: 'var(--error)', stopped: 'var(--warning)', ready: 'var(--text-dark)',
};

function StageNode({ stage, busy, onAction, onSelect }) {
  const isMerge = stage.kind === 'merge';
  const title = stage.stage_name || stage.name;
  return (
    <div style={{ display: 'flex', gap: '10px' }}>
      {/* binario verticale */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '22px', flexShrink: 0 }}>
        <span style={{
          width: '11px', height: '11px', borderRadius: isMerge ? '3px' : '50%',
          marginTop: '13px', flexShrink: 0,
          background: stage.is_current ? 'var(--primary)' : 'transparent',
          border: `2px solid ${stage.is_current ? 'var(--primary)' : 'rgba(255,255,255,0.18)'}`,
        }} />
        <span style={{ flex: 1, width: '2px', background: 'rgba(255,255,255,0.08)', minHeight: '12px' }} />
      </div>

      <div
        onClick={() => onSelect(stage.id)}
        style={{
          flex: 1, marginBottom: '5px', padding: '8px 11px', borderRadius: '11px',
          cursor: 'pointer', border: '1px solid',
          borderColor: stage.is_current ? 'rgba(0,210,255,0.28)' : 'rgba(255,255,255,0.06)',
          background: stage.is_current ? 'rgba(0,210,255,0.04)' : 'rgba(255,255,255,0.015)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)' }}>{title}</span>
          <span style={{
            fontSize: '0.55rem', padding: '1px 7px', borderRadius: '999px',
            border: '1px solid rgba(255,255,255,0.08)', color: 'var(--text-dark)',
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}>
            {isMerge ? 'merge' : 'training'}
          </span>
          <span style={{ fontSize: '0.6rem', color: STATUS_TONE[stage.status] || 'var(--text-dark)' }}>
            ● {stage.status}
          </span>
          <span style={{ marginLeft: 'auto', fontSize: '0.58rem', color: 'var(--text-dark)', fontFamily: 'JetBrains Mono, monospace' }}>
            {stage.id}
          </span>
        </div>

        <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', marginTop: '3px' }}>
          {isMerge
            ? `fonde l'adapter in ${stage.base_model}`
            : `${stage.dataset_name || 'nessun dataset'} · ${stage.method_label || stage.method}`}
          {stage.last_loss != null && ` · loss ${Number(stage.last_loss).toFixed(4)}`}
        </div>

        <div style={{ display: 'flex', gap: '5px', marginTop: '8px', flexWrap: 'wrap' }}>
          {['adapter', 'merged', 'gguf'].filter(k => stage.artifacts[k]).map(k => (
            <span key={k} style={{
              fontSize: '0.53rem', padding: '1px 6px', borderRadius: '5px',
              background: 'rgba(63,185,80,0.09)', color: 'var(--success)',
              border: '1px solid rgba(63,185,80,0.18)',
            }}>
              {k}
            </span>
          ))}
          {!Object.values(stage.artifacts).some(Boolean) && (
            <span style={{ fontSize: '0.53rem', color: 'var(--text-dark)' }}>nessun artefatto</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '5px', marginTop: '9px', flexWrap: 'wrap' }}>
          {stage.actions.map(id => {
            const meta = ACTIONS[id];
            if (!meta) return null;
            const tone = TONE[meta.tone];
            const Icon = meta.icon;
            return (
              <span key={id} style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <button
                  onClick={e => { e.stopPropagation(); onAction(id, stage); }}
                  disabled={busy}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '4px',
                    padding: '3px 9px', borderRadius: '7px', cursor: busy ? 'wait' : 'pointer',
                    border: `1px solid ${tone.border}`, background: tone.bg, color: tone.color,
                    fontSize: '0.6rem', fontWeight: 600, opacity: busy ? 0.5 : 1,
                  }}
                >
                  <Icon size={10} /> {meta.label}
                </button>
                <InfoHint entry={meta.hint} />
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function PipelinePanel({ jobId, onSelect, onAction, addToast, refreshKey }) {
  const [chain, setChain] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!jobId) return setChain(null);
    try {
      const res = await fetch(`/api/training/job/lineage?job_id=${jobId}`);
      const data = await res.json();
      setChain(data.success ? data : null);
    } catch (e) {
      setChain(null);
    }
  }, [jobId]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const tune = async (stage) => {
    const hyper = stage.hyperparams || {};
    const batch = window.prompt(
      `Batch size per fase ${stage.stage_name || stage.id}`
      + ` (attuale ${hyper.batch_size ?? '?'}):`, String(hyper.batch_size ?? 2));
    if (batch === null) return;
    const accum = window.prompt(
      'Gradient accumulation — moltiplicato per il batch dà il batch effettivo.'
      + ` Per non cambiare il numero di step totali, tieni il prodotto uguale a`
      + ` ${(hyper.batch_size || 1) * (hyper.gradient_accumulation || 1)}.`,
      String(hyper.gradient_accumulation ?? 4));
    if (accum === null) return;
    setBusy(true);
    try {
      const res = await fetch('/api/training/job/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: stage.id,
          hyperparams: {
            batch_size: parseInt(batch, 10),
            gradient_accumulation: parseInt(accum, 10),
          },
        }),
      });
      const data = await res.json();
      addToast && addToast(data.success ? data.message : `❌ ${data.error}`,
                           data.success ? 'success' : 'error', 8000);
      await load();
    } catch (e) {
      addToast && addToast(`❌ ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  const run = async (action, stage) => {
    // Le azioni che aprono un modale le gestisce lo Studio: qui restano solo
    // quelle che si risolvono con una chiamata sola.
    if (['continue', 'export', 'benchmark'].includes(action)) {
      onAction && onAction(action, stage);
      return;
    }
    if (action === 'tune') return tune(stage);
    const endpoints = {
      start: '/api/training/job/start',
      pause: '/api/training/job/pause',
      resume: '/api/training/job/resume',
      stop: '/api/training/job/stop',
      merge: '/api/training/job/merge',
      delete: '/api/training/job/delete',
    };
    if (action === 'delete'
        && !window.confirm(`Eliminare la fase ${stage.stage_name || stage.id}? `
                         + 'Job, log e artefatti verranno rimossi.')) return;
    setBusy(true);
    try {
      const body = { job_id: stage.id };
      if (action === 'merge') {
        const name = window.prompt(
          'Nome della fase che nascerà dal merge (es. "Qwythos Reasoning v1"):',
          stage.stage_name || '');
        if (name === null) { setBusy(false); return; }
        body.stage_name = name.trim();
      }
      const res = await fetch(endpoints[action], {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      addToast && addToast(
        data.success ? (data.message || 'Fatto.') : `❌ ${data.error}`,
        data.success ? 'success' : 'error', 6000);
      if (data.success && data.job_id) onSelect && onSelect(data.job_id);
      await load();
    } catch (e) {
      addToast && addToast(`❌ ${e.message}`, 'error');
    } finally {
      setBusy(false);
    }
  };

  if (!chain || !chain.stages?.length) return null;

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '10px',
        fontSize: '0.66rem', fontWeight: 700, color: 'var(--text)',
      }}>
        <Layers size={13} style={{ color: 'var(--primary)' }} />
        Catena di specializzazione
        <span style={{ color: 'var(--text-dark)', fontWeight: 400 }}>
          {chain.stages.length} {chain.stages.length === 1 ? 'fase' : 'fasi'}
        </span>
        <InfoHint entry={{
          label: 'Come si legge',
          what: 'Ogni cerchio è un training, ogni quadrato un merge. Il merge produce '
              + 'un modello autonomo che diventa la base della fase dopo.',
          good: 'Valutare ogni anello prima di aggiungere il successivo: così sai '
              + 'quale fase ha portato il miglioramento.',
          bad: 'Concatenare fasi senza misurarle: se il risultato peggiora non sai dove.',
        }} />
      </div>
      {chain.stages.map(stage => (
        <StageNode
          key={stage.id}
          stage={stage}
          busy={busy}
          onAction={run}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
