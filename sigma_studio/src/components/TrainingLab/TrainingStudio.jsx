import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Boxes, Database, Cpu, Sliders, Activity, PackageCheck, ChevronDown, ChevronRight } from 'lucide-react';
import TrainingConfigurator from './TrainingConfigurator';
import TrainingMonitor from './TrainingMonitor';
import PipelinePanel from './PipelinePanel';
import InfoHint from './InfoHint';

// ==============================================================================
// TrainingStudio — l'intero processo in una pagina sola
// ==============================================================================
// Le sotto-tab costringevano a tenere a mente in quale scheda stava ogni pezzo:
// il dataset di là, gli iperparametri di qua, le curve altrove. Qui il percorso
// è verticale e sempre visibile, e la barra in alto dice a colpo d'occhio a che
// punto è.
//
// Non è una riscrittura: preparazione ed esecuzione restano i componenti già
// collaudati, innestati senza la loro cornice. Quello che aggiunge lo Studio è
// il filo che li lega e lo stato condiviso fra le due metà.

const STEPS = [
  {
    id: 'sorgente', label: 'Sorgente', icon: Boxes,
    hint: {
      label: 'Da cosa parte il modello',
      what: 'Un modello base pubblico, oppure un fine-tuning che hai già fatto qui '
          + 'e vuoi specializzare ancora.',
      good: 'Continuare conserva quello che il modello ha già imparato.',
      bad: 'I modelli Ollama non sono utilizzabili: sono GGUF quantizzati, che '
         + 'nessun trainer sa caricare.',
    },
  },
  {
    id: 'dati', label: 'Dati', icon: Database,
    hint: {
      label: 'Il dataset di addestramento',
      what: 'Da HuggingFace o importato da file. Il 5% viene tenuto da parte come '
          + 'validation, per accorgersi dell\'overfitting mentre il run è in corso.',
      good: 'Un formato riconosciuto (instruction/output, question/answer, chat) '
          + 'viene convertito da solo nel testo di training.',
      bad: 'Sotto 40 esempi la validation viene disattivata: la sua loss '
         + 'oscillerebbe più del segnale che deve misurare.',
    },
  },
  {
    id: 'tecnica', label: 'Tecnica', icon: Cpu,
    hint: {
      label: 'Come vengono modificati i pesi',
      what: 'LoRA e SFT allenano un piccolo adapter lasciando intatto il modello. '
          + 'Il pre-training riscrive tutti i pesi. FWE genera i pesi invece di '
          + 'memorizzarli.',
      good: 'Per specializzare un modello esistente, LoRA è quasi sempre la scelta.',
      bad: 'Il pre-training completo su una sola GPU consumer è praticabile solo '
         + 'su modelli molto piccoli.',
    },
  },
  {
    id: 'messa-a-punto', label: 'Messa a punto', icon: Sliders,
    hint: {
      label: 'Gli iperparametri',
      what: 'Epoche, learning rate, batch e lunghezza di contesto. I valori '
          + 'arrivano già calibrati sull\'hardware reale di questa macchina.',
      good: 'Partire dai valori autotunati e cambiarne uno alla volta.',
      bad: 'Alzare il batch senza guardare la VRAM: il run muore al primo step.',
    },
  },
  {
    id: 'esecuzione', label: 'Esecuzione', icon: Activity,
    hint: {
      label: 'Il run e le sue metriche',
      what: 'Curve di loss e validation, perplexity, divario train/validation e '
          + 'una diagnosi automatica che dice se sta ancora imparando.',
      good: 'La validation loss che scende insieme alla training loss.',
      bad: 'La validation che risale mentre la training scende: overfitting, '
         + 'il momento di fermarsi.',
    },
  },
  {
    id: 'consegna', label: 'Consegna', icon: PackageCheck,
    hint: {
      label: 'Il modello finito',
      what: 'Export verso Ollama, con quantizzazione facoltativa, e continuazione '
          + 'su un altro dataset per specializzarlo ancora.',
      good: 'Q4_K_M riduce il modello a circa un terzo con una perdita minima.',
      bad: 'Esportare a 16 bit un modello da 9B significa 18 GB su disco.',
    },
  },
];

const PHASE_OF = {
  ready: 'esecuzione', running: 'esecuzione',
  completed: 'consegna', stopped: 'consegna', failed: 'esecuzione',
};

function StepRail({ current, jobStatus }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap',
      padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
      background: 'rgba(255,255,255,0.015)',
    }}>
      {STEPS.map((step, i) => {
        const active = step.id === current;
        const done = STEPS.findIndex(s => s.id === current) > i;
        const Icon = step.icon;
        return (
          <React.Fragment key={step.id}>
            {i > 0 && (
              <span style={{
                width: '14px', height: '1px', flexShrink: 0,
                background: done ? 'rgba(0,210,255,0.35)' : 'rgba(255,255,255,0.08)',
              }} />
            )}
            <span style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '4px 10px', borderRadius: '999px',
              border: '1px solid',
              borderColor: active ? 'rgba(0,210,255,0.3)'
                : done ? 'rgba(0,210,255,0.12)' : 'rgba(255,255,255,0.06)',
              background: active ? 'rgba(0,210,255,0.07)' : 'transparent',
              color: active ? 'var(--primary)' : done ? 'var(--text-dim)' : 'var(--text-dark)',
              fontSize: '0.62rem', fontWeight: active ? 700 : 500, whiteSpace: 'nowrap',
            }}>
              <Icon size={11} />
              {step.label}
              <InfoHint entry={step.hint} side="bottom" />
            </span>
          </React.Fragment>
        );
      })}
      {jobStatus && (
        <span style={{
          marginLeft: 'auto', fontSize: '0.6rem', color: 'var(--text-dark)',
          whiteSpace: 'nowrap',
        }}>
          job {jobStatus}
        </span>
      )}
    </div>
  );
}

// Una pagina lineare che tiene tutto sempre aperto costringe a scorrere fra
// campi già decisi per arrivare a quello che serve adesso. Ogni sezione si
// richiude su una riga di riepilogo, e resta a un clic di distanza.
function Section({ id, title, subtitle, summary, children, open, onToggle, tone = 'normal' }) {
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <section id={`studio-${id}`} style={{ marginBottom: '4px' }}>
      <button
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', gap: '9px', width: '100%',
          padding: '8px 14px', background: 'none', border: 'none', cursor: 'pointer',
          textAlign: 'left', borderRadius: '8px',
        }}
      >
        <Chevron size={13} style={{ color: 'var(--text-dark)', flexShrink: 0 }} />
        <h3 style={{
          margin: 0, fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.04em',
          textTransform: 'uppercase', whiteSpace: 'nowrap',
          color: tone === 'muted' ? 'var(--text-dark)' : 'var(--text)',
        }}>
          {title}
        </h3>
        <span style={{
          fontSize: '0.62rem', color: 'var(--text-dim)', overflow: 'hidden',
          textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {open ? subtitle : (summary || subtitle)}
        </span>
      </button>
      {open && <div style={{ padding: '0 14px 4px' }}>{children}</div>}
    </section>
  );
}

export default function TrainingStudio({ myDatasets, selectedDatasetId, onDatasetSelect,
                                         onJobCreated, addToast }) {
  const [activeJob, setActiveJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [continueFrom, setContinueFrom] = useState(null);
  // Cambia a ogni azione sulla catena: fa ricaricare la lineage.
  const [chainVersion, setChainVersion] = useState(0);
  // Aperta di default solo la sezione che serve adesso: senza un job si
  // prepara, con un job si guarda come sta andando.
  const [open, setOpen] = useState({ preparazione: true, catena: true, esecuzione: true });
  const toggle = (id) => setOpen(o => ({ ...o, [id]: !o[id] }));

  const refreshJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/training/jobs');
      const data = await res.json();
      if (data.success) setJobs(data.jobs || []);
    } catch (e) {}
  }, []);

  useEffect(() => { refreshJobs(); }, [refreshJobs]);

  // Con un run in corso la lista va riletta: senza, la barra delle fasi e il
  // riepilogo restano fermi allo stato del momento in cui la pagina è stata
  // aperta, anche mentre il training avanza.
  const running = jobs.some(j => ['running', 'paused'].includes(j.status));
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(() => {
      refreshJobs();
      setChainVersion(v => v + 1);
    }, 5000);
    return () => clearInterval(timer);
  }, [running, refreshJobs]);

  // All'apertura, se un job c'è già la preparazione parte richiusa: si arriva
  // qui per vedere come sta andando, non per riconfigurare da capo. Succede una
  // volta sola, così una scelta manuale non viene poi ribaltata.
  const collapsedOnce = useRef(false);
  useEffect(() => {
    if (collapsedOnce.current || jobs.length === 0) return;
    collapsedOnce.current = true;
    setOpen(o => ({ ...o, preparazione: false }));
  }, [jobs.length]);

  // Il job più recente è quello di cui lo Studio racconta lo stato: appena ne
  // crei uno la pagina scorre giù da sola, senza cambiare scheda.
  const current = useMemo(
    () => jobs.find(j => j.id === activeJob) || jobs.find(j => j.status === 'running') || jobs[0],
    [jobs, activeJob]);

  const phase = current ? (PHASE_OF[current.status] || 'esecuzione') : 'sorgente';

  const scrollTo = (id) => requestAnimationFrame(() => {
    document.getElementById(`studio-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  const handleChainAction = (action, stage) => {
    if (action === 'continue') {
      setContinueFrom(stage.id);
      setOpen(o => ({ ...o, preparazione: true }));
      scrollTo('preparazione');
      addToast && addToast(
        `Preparazione impostata per proseguire da ${stage.stage_name || stage.id}: `
        + 'scegli dataset e iperparametri.', 'info', 6000);
      return;
    }
    // Export e valutazione vivono nella sezione di esecuzione, sul job scelto.
    setActiveJob(stage.id);
    scrollTo('esecuzione');
    if (action === 'benchmark') {
      addToast && addToast(
        'Il modello va valutato dalla tab Benchmark Test: esportalo in Ollama e '
        + 'lanciarlo lì è per ora il percorso.', 'info', 7000);
    }
  };

  const handleCreated = (job) => {
    setActiveJob(job.id);
    setContinueFrom(null);
    setChainVersion(v => v + 1);
    setOpen(o => ({ ...o, preparazione: false, esecuzione: true }));
    refreshJobs();
    if (onJobCreated) onJobCreated(job);
    scrollTo('esecuzione');
  };

  return (
    <div className="training-panel training-studio">
      <StepRail current={phase} jobStatus={current ? `${current.id} · ${current.status}` : null} />
      {jobs.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
          <span style={{ fontSize: '0.6rem', color: 'var(--text-dark)', whiteSpace: 'nowrap' }}>
            Fase in esame
          </span>
          <div className="training-select-wrapper" style={{ flex: 1, maxWidth: '520px' }}>
            <select
              className="training-select"
              value={current ? current.id : ''}
              onChange={e => { setActiveJob(e.target.value); setChainVersion(v => v + 1); }}
            >
              {jobs.map(j => (
                <option key={j.id} value={j.id}>
                  {j.id} · {j.stage_name || j.name || j.output_name} — {j.status}
                </option>
              ))}
            </select>
          </div>
          <button className="training-btn" onClick={() => { refreshJobs(); setChainVersion(v => v + 1); }}>
            Aggiorna
          </button>
        </div>
      )}
      <div className="training-scroll-area training-studio-grid" style={{ paddingTop: 0 }}>
        {/* Colonna sinistra: dov'è il lavoro. Non si richiude, è la mappa. */}
        <aside className="training-studio-aside">
          {current ? (
            <PipelinePanel
              jobId={current.id}
              refreshKey={chainVersion}
              addToast={addToast}
              onSelect={(id) => { setActiveJob(id); setChainVersion(v => v + 1); refreshJobs(); }}
              onAction={handleChainAction}
            />
          ) : (
            <div style={{
              padding: '18px 14px', fontSize: '0.64rem', color: 'var(--text-dark)',
              border: '1px dashed rgba(255,255,255,0.08)', borderRadius: '12px', lineHeight: 1.6,
            }}>
              La catena delle fasi comparirà qui appena crei il primo job.
              Ogni anello è un training o un merge, e da ognuno si può proseguire.
            </div>
          )}
        </aside>

        {/* Colonna destra: cosa si fa adesso sulla fase scelta. */}
        <div className="training-studio-main">
        <Section
          id="preparazione"
          title="Preparazione"
          subtitle="sorgente · dati · tecnica · messa a punto"
          summary={current
            ? `ultimo job ${current.id} · ${current.base_model || ''} su ${current.dataset_name || current.dataset_id || 'n/d'}`
            : 'nessun job ancora — apri per configurarne uno'}
          open={open.preparazione}
          onToggle={() => toggle('preparazione')}
        >
          <TrainingConfigurator
            embedded
            continueFrom={continueFrom}
            myDatasets={myDatasets}
            selectedDatasetId={selectedDatasetId}
            onDatasetSelect={onDatasetSelect}
            onJobCreated={handleCreated}
            addToast={addToast}
          />
        </Section>

        <Section
          id="esecuzione"
          title="Esecuzione e consegna"
          subtitle="avvio, metriche, diagnosi, export"
          tone={current ? 'normal' : 'muted'}
          open={open.esecuzione}
          onToggle={() => toggle('esecuzione')}
        >
          {current ? (
            <TrainingMonitor embedded jobId={current.id} onAddToast={addToast} />
          ) : (
            <div style={{
              padding: '28px 16px', textAlign: 'center', fontSize: '0.68rem',
              color: 'var(--text-dark)', border: '1px dashed rgba(255,255,255,0.08)',
              borderRadius: '12px',
            }}>
              Qui compariranno curve, metriche e export appena crei il primo job.
            </div>
          )}
        </Section>
        </div>
      </div>
    </div>
  );
}
