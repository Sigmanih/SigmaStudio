import React, { useState, useEffect } from 'react';
import { Play, Square, Cpu, Brain, Sliders, Database, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import InfoHint from './InfoHint';

// ==============================================================================
// TrainingConfigurator — Base model + method + hyperparams + dataset picker + launch
// ==============================================================================

const METHODS = [
  {
    id: 'lora_unsloth',
    name: 'LoRA',
    fullName: 'LoRA (Unsloth)',
    desc: 'Consigliato',
    req: 'Richiede: unsloth, trl',
    color: '#00d2ff',
    icon: '⚡',
    isFinetune: true,
  },
  {
    id: 'trl_sft',
    name: 'SFT',
    fullName: 'SFT (TRL)',
    desc: 'Stabile',
    req: 'Richiede: trl, peft',
    color: '#bc8cff',
    icon: '🔬',
    isFinetune: true,
  },
  {
    id: 'full_pretrain',
    name: 'Pre-Training',
    fullName: 'Full Pre-Training da Zero',
    desc: 'Da Zero',
    req: '≥8GB VRAM (Tiny) / 24GB+',
    color: '#ffa600',
    icon: '🌐',
    isFinetune: false,
  },
  {
    id: 'fwe_gradus',
    name: 'FWE',
    fullName: 'Gradus — Functional Weight Engine',
    desc: 'Compressione',
    req: 'Genera i pesi, non li salva',
    color: '#3fb950',
    icon: '🧬',
    isFinetune: false,
  },
  {
    id: 'script_custom',
    name: 'Custom',
    fullName: 'Script Custom',
    desc: 'Flessibile',
    req: 'Script Python tuo',
    color: '#ff7043',
    icon: '🛠️',
    isFinetune: true,
  },
];

// Modelli target supportati dal motore FWE (architettura Qwen2 manuale)
const FWE_MODELS = [
  'qwen0.5b-instruct',
  'qwen0.5b',
  'qwen1.5b',
];


const POPULAR_MODELS = [
  // Fine-tuning (Unsloth optimized)
  'unsloth/llama-3.2-3b-instruct',
  'unsloth/llama-3.2-1b-instruct',
  'unsloth/llama-3.1-8b-instruct',
  'unsloth/mistral-7b-instruct-v0.3',
  'unsloth/Phi-3-mini-4k-instruct',
  'unsloth/gemma-2-2b-it',
  'meta-llama/Llama-3.2-3B-Instruct',
  'microsoft/Phi-3-mini-4k-instruct',
  'mistralai/Mistral-7B-Instruct-v0.3',
  // Pre-training base architectures
  'gpt2',
  'gpt2-medium',
  'openai-community/gpt2-xl',
  'EleutherAI/gpt-neo-125m',
  'EleutherAI/pythia-160m',
  'from_scratch',  // GPT-2 style from scratch
];


function HyperParam({ label, desc, value, min, max, step, onChange, display }) {
  return (
    <div className="training-field">
      <label>{label}</label>
      {desc && <div className="training-field-desc">{desc}</div>}
      <div className="training-slider-row">
        <input
          type="range"
          className="training-slider"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
        />
        <div className="training-slider-val">{display ? display(value) : value}</div>
      </div>
    </div>
  );
}

// `embedded`: dentro lo Studio la pagina scorre tutta insieme, quindi il
// pannello non deve portarsi dietro la propria area di scroll.
export default function TrainingConfigurator({ myDatasets, selectedDatasetId: propDatasetId, onDatasetSelect: propOnDatasetSelect, onJobCreated, addToast, embedded = false, continueFrom = null }) {

  const [method, setMethod] = useState('lora_unsloth');
  const [baseModel, setBaseModel] = useState('unsloth/llama-3.2-3b-instruct');
  const [customModel, setCustomModel] = useState('');
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState(propDatasetId || '');
  const [outputName, setOutputName] = useState('');
  const [textField, setTextField] = useState('text');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [creating, setCreating] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);
  // Continuazione: invece di partire da un modello base si riprende un
  // fine-tuning gia' fatto, tipicamente per specializzarlo su un altro dataset.
  const [startFrom, setStartFrom] = useState('base');   // 'base' | 'continue'
  const [continuableJobs, setContinuableJobs] = useState([]);
  const [continueJobId, setContinueJobId] = useState('');
  const [continueMode, setContinueMode] = useState('resume_adapter');
  const [continueModes, setContinueModes] = useState([]);

  // La catena può chiedere di proseguire da una fase precisa: il form ci si
  // posiziona sopra invece di far ricominciare la scelta a mano.
  useEffect(() => {
    if (!continueFrom) return;
    setStartFrom('continue');
    setContinueJobId(continueFrom);
  }, [continueFrom]);

  // Sync selected dataset from parent (when user adds from DatasetBrowser tab)
  useEffect(() => {
    if (propDatasetId && propDatasetId !== selectedDatasetId) {
      setSelectedDatasetId(propDatasetId);
    }
  }, [propDatasetId]);

  const handleDatasetChange = (id) => {
    setSelectedDatasetId(id);
    if (propOnDatasetSelect) propOnDatasetSelect(id);
  };

  // Hyperparams
  const [numEpochs, setNumEpochs] = useState(3);
  const [lr, setLr] = useState(2e-4);
  const [batchSize, setBatchSize] = useState(2);
  const [maxSeqLen, setMaxSeqLen] = useState(2048);
  const [loraR, setLoraR] = useState(16);
  const [loraAlpha, setLoraAlpha] = useState(16);
  const [gradAccum, setGradAccum] = useState(4);
  // 0 = dataset intero. Su un dataset da centinaia di migliaia di esempi
  // un'epoca dura ore, e per specializzare quasi mai serve tutto.
  const [maxExamples, setMaxExamples] = useState(0);

  const [hardware, setHardware] = useState(null);
  const [dependencies, setDependencies] = useState(null);
  const [checkingDeps, setCheckingDeps] = useState(false);

  // Auto-tune calcolato dal backend sull'hardware reale
  const [autotune, setAutotune] = useState(null);
  const [autoApplied, setAutoApplied] = useState(false);

  // Gradus FWE
  const [fweInfo, setFweInfo] = useState(null);
  const [fwe, setFwe] = useState({
    fwe_include: '_proj',
    fwe_block_size: 32,
    fwe_latent_dim: 64,
    fwe_steps: 600,
    fwe_vq: 512,
    fwe_dataset: 'wikitext',
    fwe_max_layers: -1,
    fwe_save_every: 25,
    fwe_devices: '',
  });
  const [selftest, setSelftest] = useState(null);
  const [runningSelftest, setRunningSelftest] = useState(false);

  const isFwe = method === 'fwe_gradus';
  // Nello Studio le sezioni stanno una sotto l'altra nella stessa pagina:
  // i respiri pensati per una tab a sé diventano vuoti da scorrere.
  const blockGap = embedded ? '11px' : '20px';

  // Load Ollama models and Hardware info
  useEffect(() => {
    fetch('/api/ollama_models')
      .then(r => r.json())
      .then(d => {
        if (d.success && d.models) {
          setOllamaModels(d.models.map(m => m.name || m.model || m));
        }
      })
      .catch(() => {});

    fetch('/api/training/hardware')
      .then(r => r.json())
      .then(d => {
        if (d.success) setHardware(d.hardware);
      })
      .catch(() => {});

    fetch('/api/training/job/continuation_modes')
      .then(r => r.json())
      .then(d => { if (d.success) setContinueModes(d.modes || []); })
      .catch(() => {});

    // Solo i job che hanno davvero prodotto un adapter da riprendere.
    fetch('/api/training/jobs')
      .then(r => r.json())
      .then(d => {
        if (!d.success) return;
        const usable = (d.jobs || []).filter(j =>
          ['lora_unsloth', 'trl_sft'].includes(j.method)
          && ['completed', 'stopped'].includes(j.status));
        setContinuableJobs(usable);
        if (usable.length && !continueJobId) setContinueJobId(usable[0].id);
      })
      .catch(() => {});
  }, []);

  // Check dependencies when method changes
  useEffect(() => {
    if (!method) return;
    setCheckingDeps(true);
    setDependencies(null);
    fetch('/api/training/dependencies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.success) setDependencies(d);
        else setDependencies(null);
      })
      .catch(() => setDependencies(null))
      .finally(() => setCheckingDeps(false));
  }, [method]);

  // Auto-tune: chiede al backend la ricetta ottimale per hardware + modello + metodo
  useEffect(() => {
    const model = (useCustomModel ? customModel : baseModel).trim();
    if (!model) return;
    const params = new URLSearchParams({ method, base_model: model, seq_len: String(maxSeqLen) });
    const timer = setTimeout(() => {
      fetch(`/api/training/gpu/autotune?${params}`)
        .then(r => r.json())
        .then(d => { if (d.success) { setAutotune(d.config); setAutoApplied(false); } })
        .catch(() => setAutotune(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [method, baseModel, customModel, useCustomModel, maxSeqLen]);

  // Stato del motore Gradus + default per questa GPU
  useEffect(() => {
    if (!isFwe || fweInfo) return;
    fetch('/api/training/fwe/status')
      .then(r => r.json())
      .then(d => {
        if (!d.success) return;
        setFweInfo(d);
        const def = d.defaults || {};
        setFwe(prev => ({
          ...prev,
          fwe_include: def.fwe_include ?? prev.fwe_include,
          fwe_latent_dim: def.fwe_latent_dim ?? prev.fwe_latent_dim,
          fwe_steps: def.fwe_steps ?? prev.fwe_steps,
          fwe_vq: def.fwe_vq ?? prev.fwe_vq,
          fwe_devices: def.fwe_devices ?? prev.fwe_devices,
        }));
        if (def.batch_size) setBatchSize(def.batch_size);
        if (def.learning_rate) setLr(def.learning_rate);
        if (!FWE_MODELS.includes(baseModel)) setBaseModel(def.base_model || FWE_MODELS[0]);
      })
      .catch(() => {});
  }, [isFwe]);

  const applyAutotune = () => {
    if (!autotune) return;
    setBatchSize(autotune.batch_size);
    setGradAccum(autotune.gradient_accumulation);
    setAutoApplied(true);
    addToast && addToast('Iperparametri allineati alla ricetta hardware', 'success');
  };

  const runSelftest = async (brick) => {
    setRunningSelftest(true);
    setSelftest(null);
    try {
      const res = await fetch('/api/training/fwe/selftest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brick, device: 'auto', steps: 150 }),
      });
      const d = await res.json();
      setSelftest(d);
      addToast && addToast(
        d.passed ? `✅ Gradient-check brick ${brick} superato (${d.elapsed_s}s)`
                 : `❌ Gradient-check brick ${brick} fallito`,
        d.passed ? 'success' : 'error');
    } catch {
      addToast && addToast('Errore durante il self-test del motore', 'error');
    } finally {
      setRunningSelftest(false);
    }
  };

  // Auto-detect text_field from selected dataset
  useEffect(() => {
    if (selectedDatasetId && myDatasets) {
      const ds = myDatasets.find(d => d.id === selectedDatasetId);
      if (ds?.columns?.length) {
        const preferred = ['text', 'instruction', 'output', 'content', 'input'];
        const found = preferred.find(p => ds.columns.includes(p));
        if (found) setTextField(found);
      }
    }
  }, [selectedDatasetId, myDatasets]);

  // Auto-generate output name
  useEffect(() => {
    const ds = myDatasets?.find(d => d.id === selectedDatasetId);
    const dsName = ds?.name || 'dataset';
    const modelShort = (useCustomModel ? customModel : baseModel).split('/').pop()?.split('-')[0] || 'model';
    setOutputName(`sigma_${modelShort}_${dsName}`.slice(0, 40).replace(/[^a-zA-Z0-9_-]/g, '_'));
  }, [selectedDatasetId, baseModel, customModel, useCustomModel, myDatasets]);

  const selectedDs = myDatasets?.find(d => d.id === selectedDatasetId);
  const finalModel = useCustomModel ? customModel : baseModel;

  const isContinuation = startFrom === 'continue' && !isFwe;

  const handleCreate = async () => {
    if (isContinuation && !continueJobId) {
      addToast && addToast('Scegli il training da continuare', 'error');
      return;
    }
    if (!isContinuation && !finalModel.trim()) {
      addToast && addToast('Seleziona un modello base', 'error');
      return;
    }
    // Il motore FWE usa il proprio corpus (wikitext / interno): nessun dataset richiesto
    if (!selectedDatasetId && !isFwe) {
      addToast && addToast('Seleziona un dataset prima di avviare il training', 'warning');
      return;
    }
    setCreating(true);
    const hyperparams = {
      num_epochs: numEpochs,
      learning_rate: lr,
      batch_size: batchSize,
      max_seq_length: maxSeqLen,
      max_examples: maxExamples,
      lora_r: loraR,
      lora_alpha: loraAlpha,
      gradient_accumulation: gradAccum,
      text_field: textField,
      ...(isFwe ? fwe : {}),
    };
    try {
      // La continuazione ha il suo endpoint: e' il backend a risalire
      // all'adapter (o ai pesi fusi) del job padre e a registrare la catena.
      const url = isContinuation
        ? '/api/training/job/continue'
        : '/api/training/job/create';
      const body = isContinuation
        ? {
            job_id: continueJobId,
            mode: continueMode,
            dataset_id: selectedDatasetId || '',
            output_name: outputName || 'sigma_model',
            hyperparams,
          }
        : {
            base_model: finalModel.trim(),
            dataset_id: selectedDatasetId || '',
            method,
            output_name: outputName || 'sigma_model',
            hyperparams,
          };
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (data.success) {
        addToast && addToast(`✅ Job "${data.job.id}" creato!`, 'success');
        if (onJobCreated) onJobCreated(data.job);
      } else {
        addToast && addToast(`Errore: ${data.error}`, 'error');
      }
    } catch {
      addToast && addToast('Errore di rete', 'error');
    } finally {
      setCreating(false);
    }
  };


  return (
    <div className={embedded ? "" : "training-panel"}>
      <div className={embedded ? "" : "training-scroll-area"}>

        {!embedded && (
          <div className="app-page-header" style={{ marginBottom: '18px' }}>
            <div className="app-page-header-title">
              <div className="app-page-header-icon">
                <Cpu size={22} color="#00f2fe" />
              </div>
              <div>
                <h1>Training Studio</h1>
                <div className="app-page-header-subtitle">
                  <span>Configurazione iperparametri e modello</span>
                  <span>•</span>
                  <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                    Metodo attivo: {method}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Method selector ── */}
        <div style={{ marginBottom: blockGap }}>
          <div className="training-section-header">
            <Brain size={14} />
            <h3>Metodo di Training</h3>
          </div>
          <div className="training-method-pills">
            {METHODS.map(m => (
              <button
                key={m.id}
                className={`training-method-pill ${method === m.id ? 'active' : ''}`}
                onClick={() => setMethod(m.id)}
                style={method === m.id ? { borderColor: `${m.color}50`, color: m.color, background: `${m.color}0f` } : {}}
              >
                <span className="training-method-pill-name">{m.icon} {m.name}</span>
                <span className="training-method-pill-desc">{m.desc}</span>
                <span className="training-method-pill-desc" style={{ fontSize: '0.55rem', opacity: 0.5 }}>{m.req}</span>
              </button>
            ))}
          </div>
          {method === 'lora_unsloth' && (
            <div style={{
              marginTop: '8px', padding: '8px 12px', background: 'rgba(0,210,255,0.05)',
              border: '1px solid rgba(0,210,255,0.12)', borderRadius: '8px', fontSize: '0.62rem', color: 'var(--text-dim)'
            }}>
              ⚡ <strong style={{ color: 'var(--primary)' }}>Unsloth LoRA</strong> — 2x più veloce, 60% meno VRAM.
              Installa con: <code style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono' }}>pip install unsloth trl</code>
            </div>
          )}
          {method === 'full_pretrain' && (
            <div style={{
              marginTop: '8px', padding: '10px 14px',
              background: 'rgba(255,166,0,0.06)', border: '1px solid rgba(255,166,0,0.2)',
              borderRadius: '10px', fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.6
            }}>
              <div style={{ color: '#ffa600', fontWeight: 700, marginBottom: '4px' }}>🌐 Full Pre-Training da Zero</div>
              Addestra un modello <strong>da zero</strong> su testo grezzo. Non richiede un modello base istruito.
              <ul style={{ margin: '6px 0 0 14px', padding: 0, fontSize: '0.6rem' }}>
                <li><strong>TinyStories</strong>: 4-8GB VRAM — ottimo per iniziare</li>
                <li><strong>OpenWebText</strong>: 24GB+ VRAM — qualità GPT-2</li>
                <li>Usa <code style={{ color: '#ffa600', fontFamily: 'JetBrains Mono' }}>from_scratch</code> come modello per architettura custom GPT-2 mini</li>
              </ul>
              Installa: <code style={{ color: '#ffa600', fontFamily: 'JetBrains Mono', fontSize: '0.58rem' }}>pip install transformers datasets accelerate</code>
            </div>
          )}
          {method === 'script_custom' && (
            <div style={{
              marginTop: '8px', padding: '8px 12px', background: 'rgba(255,112,67,0.05)',
              border: '1px solid rgba(255,112,67,0.12)', borderRadius: '8px', fontSize: '0.62rem', color: 'var(--text-dim)'
            }}>
              🛠️ <strong style={{ color: '#ff7043' }}>Modalità Custom</strong> — Sigma genera un template Python (con preambolo CUDA già pronto: DEVICE, DTYPE, TUNE) che puoi modificare prima di avviare.
            </div>
          )}
          {/* Stato dipendenze del metodo scelto */}
          {(checkingDeps || dependencies) && (
            <div style={{
              marginTop: '8px', padding: '6px 12px', borderRadius: '8px',
              fontSize: '0.6rem', display: 'flex', alignItems: 'center', gap: '8px',
              background: dependencies?.all_installed ? 'rgba(63,185,80,0.05)' : 'rgba(255,166,0,0.05)',
              border: `1px solid ${dependencies?.all_installed ? 'rgba(63,185,80,0.15)' : 'rgba(255,166,0,0.15)'}`,
              color: 'var(--text-dim)',
            }}>
              {checkingDeps ? (
                <span>Verifica dipendenze…</span>
              ) : dependencies?.all_installed ? (
                <span style={{ color: 'var(--success)' }}>
                  ✓ Dipendenze installate: {dependencies.dependencies.join(', ') || 'nessuna richiesta'}
                </span>
              ) : (
                <>
                  <span style={{ color: 'var(--warning)' }}>
                    ⚠️ Mancano: {dependencies.missing.join(', ')}
                  </span>
                  <code style={{
                    fontFamily: 'JetBrains Mono', color: 'var(--primary)',
                    fontSize: '0.56rem', marginLeft: 'auto',
                  }}>
                    {dependencies.install_command}
                  </code>
                </>
              )}
            </div>
          )}

          {isFwe && (
            <div style={{
              marginTop: '8px', padding: '10px 14px',
              background: 'rgba(63,185,80,0.06)', border: '1px solid rgba(63,185,80,0.2)',
              borderRadius: '10px', fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.6
            }}>
              <div style={{ color: '#3fb950', fontWeight: 700, marginBottom: '4px' }}>
                🧬 Gradus — Functional Weight Engine
              </div>
              I pesi del modello non vengono <strong>memorizzati</strong> ma <strong>generati</strong>:
              un decoder AILO da 152M congelato, guidato da un codebook VQ e dalle coordinate
              semantiche del blocco (tipo di tensore, layer, posizione), produce i blocchi di pesi
              su richiesta. Il payload per-modello scende a ~0.5 MB.
              <ul style={{ margin: '6px 0 0 14px', padding: 0, fontSize: '0.6rem' }}>
                <li>Obiettivo <strong>task-fidelity</strong>: mantenere la perplexity, non copiare i pesi</li>
                <li>Motore con forward e backward <strong>scritti a mano</strong> (nessun autograd), percorsi CUDA ottimizzati</li>
                <li>Checkpoint automatico: i run lunghi riprendono dopo un riavvio</li>
              </ul>
              {fweInfo?.engine && !fweInfo.engine.available && (
                <div style={{ marginTop: '6px', color: 'var(--warning)' }}>
                  ⚠️ Motore non disponibile — mancano: {fweInfo.engine.missing.join(', ')}
                </div>
              )}
              {fweInfo?.engine?.backbone && (
                <div style={{ marginTop: '6px', fontSize: '0.6rem' }}>
                  {fweInfo.engine.backbone.ready ? (
                    <span style={{ color: 'var(--success)' }}>
                      ✓ Decoder AILO pronto ({fweInfo.engine.backbone.size_mb} MB)
                    </span>
                  ) : (
                    <span style={{ color: 'var(--warning)' }}>
                      ⓘ Decoder AILO non ancora scaricato: al primo avvio Sigma preleva
                      ~600 MB da <code style={{ fontFamily: 'JetBrains Mono' }}>{fweInfo.engine.backbone.repo_id}</code>{' '}
                      (una sola volta, riusato da tutti i job).
                    </span>
                  )}
                </div>
              )}
              <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
                {[1, 2, 3].map(b => (
                  <button
                    key={b}
                    onClick={() => runSelftest(b)}
                    disabled={runningSelftest}
                    style={{
                      padding: '3px 9px', borderRadius: '6px', cursor: 'pointer',
                      border: '1px solid rgba(63,185,80,0.25)', background: 'rgba(63,185,80,0.06)',
                      color: '#3fb950', fontSize: '0.58rem',
                    }}
                  >
                    {runningSelftest ? '…' : `Gradient-check ${b}`}
                  </button>
                ))}
                {selftest && (
                  <span style={{ fontSize: '0.58rem', color: selftest.passed ? 'var(--success)' : 'var(--danger)', alignSelf: 'center' }}>
                    {selftest.passed ? '✅' : '❌'} brick {selftest.brick} · {selftest.elapsed_s}s
                  </span>
                )}
              </div>
            </div>
          )}

        </div>

        <div className="training-divider" />

        {/* ── Base Model ── */}
        <div style={{ marginBottom: blockGap }}>
          <div className="training-section-header">
            <Cpu size={14} />
            <h3>Modello Base</h3>
          </div>
          <div className="training-config-grid">
            {!isFwe && (
              <div className="training-field" style={{ gridColumn: '1 / -1' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  Punto di partenza
                  <InfoHint entry={{
                    label: 'Da dove partono i pesi',
                    what: 'Un training può iniziare da un modello pubblico oppure riprendere '
                        + 'un fine-tuning che hai già fatto qui, per specializzarlo ancora.',
                    good: 'Continuare serve quando vuoi aggiungere una competenza senza '
                        + 'ripartire da zero: il modello tiene quello che ha già imparato.',
                    bad: 'Continuare su un dataset molto diverso dal precedente può fargli '
                       + 'dimenticare il primo compito.',
                  }} />
                </label>
                <div style={{ display: 'flex', gap: '8px', marginTop: '6px', flexWrap: 'wrap' }}>
                  {[
                    { id: 'base', label: '🧊 Modello base' },
                    { id: 'continue', label: '🔗 Continua un fine-tuning' },
                  ].map(opt => (
                    <button
                      key={opt.id}
                      onClick={() => setStartFrom(opt.id)}
                      disabled={opt.id === 'continue' && continuableJobs.length === 0}
                      title={opt.id === 'continue' && continuableJobs.length === 0
                        ? 'Nessun job LoRA o SFT completato da cui ripartire'
                        : undefined}
                      style={{
                        padding: '5px 12px', borderRadius: '8px', border: '1px solid',
                        borderColor: startFrom === opt.id ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.06)',
                        background: startFrom === opt.id ? 'rgba(0,210,255,0.06)' : 'transparent',
                        color: startFrom === opt.id ? 'var(--primary)' : 'var(--text-dim)',
                        fontSize: '0.64rem', cursor: 'pointer',
                        opacity: opt.id === 'continue' && continuableJobs.length === 0 ? 0.4 : 1,
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {isContinuation ? (
              <>
                <div className="training-field" style={{ gridColumn: '1 / -1' }}>
                  <label>Training da continuare</label>
                  <div className="training-select-wrapper" style={{ marginTop: '6px' }}>
                    <select
                      className="training-select"
                      value={continueJobId}
                      onChange={e => setContinueJobId(e.target.value)}
                    >
                      {continuableJobs.map(j => (
                        <option key={j.id} value={j.id}>
                          {j.id} · {j.name || j.output_name} — {j.base_model} su {j.dataset_name || j.dataset_id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="training-field-desc">
                    Il metodo e il modello base li eredita dal job scelto. Qui sotto
                    scegli il dataset nuovo e gli iperparametri di questo giro.
                  </div>
                </div>
                <div className="training-field" style={{ gridColumn: '1 / -1' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    Da dove ripartono i pesi
                    <InfoHint entry={{
                      label: 'Adapter ripreso o adapter nuovo',
                      what: 'Un adapter LoRA è il pacchetto di pesi aggiuntivi prodotto dal '
                          + 'fine-tuning. Puoi continuare ad allenare quello, oppure fonderlo '
                          + 'nel modello e ricominciarne uno pulito.',
                      good: 'Riprendere l\'adapter è più veloce e non consuma disco.',
                      bad: 'Fondere costa ~18 GB e diversi minuti, ma tiene le fasi separate '
                         + 'e ispezionabili una per una.',
                    }} />
                  </label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                    {continueModes.map(m => (
                      <button
                        key={m.id}
                        onClick={() => setContinueMode(m.id)}
                        style={{
                          textAlign: 'left', padding: '9px 11px', borderRadius: '9px',
                          border: '1px solid', cursor: 'pointer',
                          borderColor: continueMode === m.id ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.06)',
                          background: continueMode === m.id ? 'rgba(0,210,255,0.06)' : 'transparent',
                        }}
                      >
                        <div style={{
                          fontSize: '0.66rem', fontWeight: 700, marginBottom: '2px',
                          color: continueMode === m.id ? 'var(--primary)' : 'var(--text)',
                        }}>
                          {m.label}
                        </div>
                        <div style={{ fontSize: '0.6rem', color: 'var(--text-dim)', lineHeight: 1.45 }}>
                          {m.detail}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
            <div className="training-field" style={{ gridColumn: '1 / -1' }}>
              <label>Seleziona Modello</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  onClick={() => setUseCustomModel(false)}
                  style={{
                    padding: '4px 10px', borderRadius: '7px', border: '1px solid',
                    borderColor: !useCustomModel ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.06)',
                    background: !useCustomModel ? 'rgba(0,210,255,0.06)' : 'transparent',
                    color: !useCustomModel ? 'var(--primary)' : 'var(--text-dim)',
                    fontSize: '0.62rem', cursor: 'pointer',
                  }}
                >
                  Popolare / Ollama
                </button>
                <button
                  onClick={() => setUseCustomModel(true)}
                  style={{
                    padding: '4px 10px', borderRadius: '7px', border: '1px solid',
                    borderColor: useCustomModel ? 'rgba(188,140,255,0.3)' : 'rgba(255,255,255,0.06)',
                    background: useCustomModel ? 'rgba(188,140,255,0.06)' : 'transparent',
                    color: useCustomModel ? 'var(--accent)' : 'var(--text-dim)',
                    fontSize: '0.62rem', cursor: 'pointer',
                  }}
                >
                  Modello Custom
                </button>
              </div>
              {!useCustomModel ? (
                <div className="training-select-wrapper" style={{ marginTop: '6px' }}>
                  <select
                    className="training-select"
                    value={baseModel}
                    onChange={e => setBaseModel(e.target.value)}
                  >
                    {isFwe ? (
                      <optgroup label="🧬 Target FWE (architettura Qwen2)">
                        {FWE_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                      </optgroup>
                    ) : (
                      <>
                        <optgroup label="🤗 HuggingFace (Unsloth optimized)">
                          {POPULAR_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                        </optgroup>
                        {ollamaModels.length > 0 && (
                          <optgroup label="🦙 Ollama (locale) — GGUF, non addestrabile">
                            {ollamaModels.map(m => (
                              <option key={`ollama:${m}`} value={m} disabled>{m}</option>
                            ))}
                          </optgroup>
                        )}
                      </>
                    )}
                  </select>
                </div>
              ) : (
                <input
                  className="training-input"
                  placeholder="es: meta-llama/Llama-3.2-3B-Instruct"
                  value={customModel}
                  onChange={e => setCustomModel(e.target.value)}
                  style={{ marginTop: '6px' }}
                />
              )}
              {!isFwe && (
                <div className="training-field-desc" style={{ marginTop: '6px' }}>
                  I modelli Ollama sono GGUF quantizzati: nessun trainer li sa caricare.
                  Per addestrarne uno parti dai safetensors originali su HuggingFace
                  («Modello Custom» → <code>owner/Nome-Modello</code>).
                </div>
              )}
            </div>
            )}
          </div>
        </div>

        <div className="training-divider" />

        {/* ── Dataset ── */}
        <div style={{ marginBottom: blockGap }}>
          <div className="training-section-header">
            <Database size={14} />
            <h3>Dataset</h3>
            {selectedDs && !isFwe && (
              <span className="training-section-sub">
                ✓ {selectedDs.name}
                {selectedDs.row_count && ` (${selectedDs.row_count.toLocaleString()} esempi)`}
              </span>
            )}
          </div>
          {isFwe ? (
            <div style={{
              padding: '12px 14px', background: 'rgba(63,185,80,0.05)',
              border: '1px solid rgba(63,185,80,0.15)', borderRadius: '10px',
              fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.6,
            }}>
              Il motore FWE non fa fine-tuning su un dataset di istruzioni: comprime i pesi
              del modello target e misura la <strong>perplexity su testo held-out</strong>.
              Il corpus si sceglie nella sezione <em>Motore FWE</em> qui sotto.
            </div>
          ) : (!myDatasets || myDatasets.length === 0) ? (
            <div style={{
              padding: '14px', background: 'rgba(255,166,0,0.05)', border: '1px solid rgba(255,166,0,0.15)',
              borderRadius: '10px', fontSize: '0.68rem', color: 'var(--warning)', display: 'flex', gap: '8px'
            }}>
              <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>Nessun dataset disponibile. Vai alla tab <strong>Dataset</strong> per importarne uno.</span>
            </div>
          ) : (
            <>
              <div className="training-ds-selector">
                {myDatasets.map(ds => (
                  <div
                    key={ds.id}
                    className={`training-ds-option ${selectedDatasetId === ds.id ? 'selected' : ''}`}
                    onClick={() => handleDatasetChange(ds.id)}
                  >
                    <span style={{ fontSize: '16px' }}>
                      {ds.source === 'huggingface' ? '🤗' : '📁'}
                    </span>
                    <span className="training-ds-option-name">{ds.name}</span>
                    <span className="training-ds-option-meta">
                      {ds.source === 'huggingface' ? ds.hf_id : `${ds.row_count?.toLocaleString() || '?'} righe`}
                    </span>
                  </div>
                ))}
              </div>
              {selectedDs?.columns?.length > 0 && (
                <div style={{ marginTop: '8px' }}>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-dark)', marginBottom: '4px' }}>
                    Colonne rilevate:
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {selectedDs.columns.map(c => (
                      <button
                        key={c}
                        onClick={() => setTextField(c)}
                        style={{
                          padding: '2px 8px', borderRadius: '6px', border: '1px solid',
                          borderColor: textField === c ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.06)',
                          background: textField === c ? 'rgba(0,210,255,0.08)' : 'rgba(255,255,255,0.02)',
                          color: textField === c ? 'var(--primary)' : 'var(--text-dim)',
                          fontSize: '0.6rem', cursor: 'pointer', fontFamily: 'JetBrains Mono',
                        }}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-dark)', marginTop: '4px' }}>
                    Campo di testo selezionato: <code style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono' }}>{textField}</code>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="training-divider" />

        {/* ── Auto-tune hardware ── */}
        {autotune && (
          <div style={{
            marginBottom: blockGap, padding: '12px 14px',
            background: 'rgba(0,210,255,0.04)', border: '1px solid rgba(0,210,255,0.15)',
            borderRadius: '10px', fontSize: '0.64rem', color: 'var(--text-dim)', lineHeight: 1.6,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ color: 'var(--primary)', fontWeight: 700 }}>⚙️ Ricetta hardware</span>
              <span style={{ fontSize: '0.58rem', opacity: 0.7 }}>
                {autotune.gpu_names?.length ? autotune.gpu_names.join(' + ') : 'CPU'}
              </span>
              <button
                onClick={applyAutotune}
                disabled={autoApplied}
                style={{
                  marginLeft: 'auto', padding: '3px 10px', borderRadius: '6px',
                  border: '1px solid rgba(0,210,255,0.3)',
                  background: autoApplied ? 'transparent' : 'rgba(0,210,255,0.08)',
                  color: autoApplied ? 'var(--text-dark)' : 'var(--primary)',
                  fontSize: '0.58rem', cursor: autoApplied ? 'default' : 'pointer',
                }}
              >
                {autoApplied ? '✓ Applicata' : 'Applica ai parametri'}
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '6px' }}>
              {[
                ['dtype', autotune.dtype],
                ['attention', autotune.attn_implementation],
                ['optimizer', autotune.optim],
                ['batch', `${autotune.batch_size} × ${autotune.gradient_accumulation} = ${autotune.effective_batch}`],
                ['strategia', autotune.strategy],
                autotune.load_in_4bit ? ['quantizzazione', '4-bit NF4'] : null,
                autotune.tf32 ? ['TF32', 'on'] : null,
                autotune.gradient_checkpointing ? ['grad checkpoint', 'on'] : null,
              ].filter(Boolean).map(([k, v]) => (
                <span key={k} style={{
                  padding: '2px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)', fontFamily: 'JetBrains Mono',
                  fontSize: '0.56rem', color: 'var(--text)',
                }}>
                  {k}: <span style={{ color: 'var(--primary)' }}>{String(v)}</span>
                </span>
              ))}
            </div>
            {autotune.notes?.map((n, i) => (
              <div key={i} style={{ fontSize: '0.58rem', opacity: 0.8 }}>• {n}</div>
            ))}
          </div>
        )}

        {/* ── Parametri FWE ── */}
        {isFwe && (
          <div style={{ marginBottom: blockGap }}>
            <div className="training-section-header">
              <Sliders size={14} />
              <h3>Motore FWE</h3>
              {fweInfo?.defaults?.note && (
                <span className="training-section-sub">{fweInfo.defaults.note}</span>
              )}
            </div>
            <div className="training-config-grid">
              <div className="training-field" style={{ gridColumn: '1 / -1' }}>
                <label>Tensori da comprimere</label>
                <div className="training-field-desc">Più copertura = più compressione, ma run molto più lunghi</div>
                <div className="training-select-wrapper">
                  <select
                    className="training-select"
                    value={fwe.fwe_include}
                    onChange={e => setFwe({ ...fwe, fwe_include: e.target.value })}
                  >
                    {(fweInfo?.targets || []).map(t => (
                      <option key={t.id} value={t.id}>{t.label} — {t.desc}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="training-field">
                <label>Corpus di valutazione</label>
                <div className="training-field-desc">La perplexity si misura su testo held-out</div>
                <div className="training-select-wrapper">
                  <select
                    className="training-select"
                    value={fwe.fwe_dataset}
                    onChange={e => setFwe({ ...fwe, fwe_dataset: e.target.value })}
                  >
                    {(fweInfo?.datasets || []).map(d => (
                      <option key={d.id} value={d.id}>{d.label} — {d.desc}</option>
                    ))}
                  </select>
                </div>
              </div>
              <HyperParam
                label="Codebook VQ (K atomi)"
                desc="0 = latent liberi (non comprimono). K basso = più compressione"
                value={fwe.fwe_vq}
                min={0} max={2048} step={64}
                onChange={v => setFwe({ ...fwe, fwe_vq: v })}
              />
              <HyperParam
                label="Dimensione blocco"
                desc="Lato del blocco quadrato di pesi generato"
                value={fwe.fwe_block_size}
                min={16} max={64} step={16}
                onChange={v => setFwe({ ...fwe, fwe_block_size: v })}
              />
              <HyperParam
                label="Latent dim"
                desc="Dimensione dell'atomo del codebook"
                value={fwe.fwe_latent_dim}
                min={16} max={256} step={16}
                onChange={v => setFwe({ ...fwe, fwe_latent_dim: v })}
              />
              <HyperParam
                label="Step di training"
                desc="Checkpoint automatico ogni 25 step"
                value={fwe.fwe_steps}
                min={50} max={5000} step={50}
                onChange={v => setFwe({ ...fwe, fwe_steps: v })}
              />
            </div>

            {fweInfo?.defaults?.multi_gpu_available && (
              <div
                onClick={() => setFwe({ ...fwe, fwe_devices: fwe.fwe_devices ? '' : 'all' })}
                style={{
                  marginTop: '10px', padding: '10px 14px', cursor: 'pointer',
                  borderRadius: '10px', fontSize: '0.64rem', lineHeight: 1.6,
                  border: `1px solid ${fwe.fwe_devices ? 'rgba(63,185,80,0.25)' : 'rgba(255,255,255,0.06)'}`,
                  background: fwe.fwe_devices ? 'rgba(63,185,80,0.06)' : 'rgba(255,255,255,0.02)',
                  color: 'var(--text-dim)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.85rem' }}>{fwe.fwe_devices ? '☑' : '☐'}</span>
                  <strong style={{ color: fwe.fwe_devices ? 'var(--success)' : 'var(--text)' }}>
                    Dividi il generatore su tutte le GPU
                  </strong>
                  <span style={{ marginLeft: 'auto', fontSize: '0.58rem', opacity: 0.7 }}>
                    {fweInfo.defaults.gpu_names?.join(' + ')}
                  </span>
                </div>
                <div style={{ marginTop: '4px', fontSize: '0.58rem', opacity: 0.85 }}>
                  Il generatore è il 94% del tempo ed è indipendente blocco per blocco.
                  Le fette sono proporzionali alla throughput <em>misurata</em> di ogni
                  scheda, quindi funziona anche con GPU di potenza diversa (dove DDP
                  non sarebbe applicabile). Misurato su questo rig: <strong>1,45×</strong>.
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Base Hyperparams ── */}
        <div style={{ marginBottom: blockGap }}>
          <div className="training-section-header">
            <Sliders size={14} />
            <h3>Iperparametri</h3>
          </div>
          <div className="training-config-grid">
            {!isFwe && (
              <HyperParam
                label="Epoche"
                desc="Quante volte passare sul dataset"
                value={numEpochs}
                min={1} max={20} step={1}
                onChange={setNumEpochs}
              />
            )}
            <HyperParam
              label={isFwe ? 'Sequenze per step' : 'Batch Size'}
              desc={isFwe ? 'Batch grande = loss più stabile' : 'Esempi per step GPU'}
              value={batchSize}
              min={1} max={32} step={1}
              onChange={setBatchSize}
            />
            <HyperParam
              label="Learning Rate"
              desc="Velocità di apprendimento"
              value={lr}
              min={1e-5} max={1e-3} step={1e-5}
              onChange={setLr}
              display={v => v.toExponential(1)}
            />
            {!isFwe && (
              <HyperParam
                label="Contesto Max (token)"
                desc="Lunghezza massima sequenza"
                value={maxSeqLen}
                min={512} max={8192} step={512}
                onChange={setMaxSeqLen}
                display={v => `${v}`}
              />
            )}
            {!isFwe && (
              <div className="training-field">
                <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  Esempi da usare
                  <InfoHint entry={{
                    label: 'Quanta parte del dataset addestrare',
                    what: 'Il numero di esempi estratti dal dataset. A zero si usa '
                        + 'tutto. Il taglio è mescolato con seed fisso, non i primi N: '
                        + 'molti dataset sono ordinati per categoria, e prendere la '
                        + 'testa significherebbe allenare su una fetta sola del compito.',
                    good: 'Per specializzare un modello bastano di norma 20-50 mila '
                        + 'esempi: il grosso del guadagno arriva lì.',
                    bad: 'Il dataset intero su corpora enormi (MetaMathQA sono 395K, '
                       + 'quasi 100 mila step) significa ore di GPU per un guadagno '
                       + 'che si era già visto molto prima.',
                  }} />
                </label>
                <div className="training-field-desc">
                  {maxExamples > 0
                    ? `${maxExamples.toLocaleString('it-IT')} esempi estratti a caso`
                    : "tutto il dataset"}
                  {selectedDs?.row_count > 0 && ` — disponibili ${selectedDs.row_count.toLocaleString('it-IT')}`}
                </div>
                <div className="training-slider-row">
                  <input
                    type="range" className="training-slider"
                    min={0} max={200000} step={5000}
                    value={maxExamples}
                    onChange={e => setMaxExamples(parseInt(e.target.value, 10))}
                  />
                  <div className="training-slider-val">
                    {maxExamples > 0 ? `${Math.round(maxExamples / 1000)}k` : 'tutto'}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Advanced toggle */}
          {!isFwe && method !== 'full_pretrain' && (
          <>
          <button
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', background: 'none',
              border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: '0.68rem',
              marginTop: '8px', padding: '4px 0',
            }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {showAdvanced ? 'Nascondi' : 'Mostra'} parametri avanzati (LoRA)
          </button>

          {showAdvanced && (
            <div className="training-config-grid" style={{ marginTop: '10px' }}>
              <HyperParam
                label="LoRA Rank (r)"
                desc={loraR === 0
                  ? 'Zero = niente LoRA: si addestrano i pesi veri. Ha senso '
                    + 'sotto il miliardo di parametri, dove un adapter da '
                    + 'rank 16 è una gabbia senza il vantaggio che la giustifica.'
                  : 'Grado della decomposizione LoRA. A zero si addestra il '
                    + 'modello intero invece di un adapter.'}
                value={loraR}
                min={0} max={128} step={4}
                onChange={setLoraR}
              />
              <HyperParam
                label="LoRA Alpha"
                desc="Scaling factor (solitamente = r)"
                value={loraAlpha}
                min={4} max={256} step={4}
                onChange={setLoraAlpha}
              />
              <HyperParam
                label="Gradient Accumulation"
                desc="Step prima di aggiornare pesi"
                value={gradAccum}
                min={1} max={32} step={1}
                onChange={setGradAccum}
              />
            </div>
          )}
          </>
          )}
        </div>

        <div className="training-divider" />

        {/* ── Output name ── */}
        <div className="training-field" style={{ marginBottom: blockGap }}>
          <label>Nome Output Modello</label>
          <div className="training-field-desc">Nome che avrà il modello in Ollama dopo l'export</div>
          <input
            className="training-input"
            value={outputName}
            onChange={e => setOutputName(e.target.value.replace(/\s+/g, '_').toLowerCase())}
            placeholder="sigma_modello_dataset"
          />
        </div>

        {/* ── Summary card ── */}
        {(isContinuation ? continueJobId : finalModel) && (selectedDatasetId || isFwe) && (
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: '12px', padding: '14px', marginBottom: '16px', fontSize: '0.68rem',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: '8px' }}>📋 Riepilogo Job</div>
            {[
              ['Metodo', METHODS.find(m => m.id === method)?.fullName],
              ['Base Model', isContinuation ? `continua ${continueJobId} (${continueMode})` : finalModel],
              ['Dataset', isFwe
                ? (fwe.fwe_dataset || 'corpus interno')
                : (selectedDs?.name || selectedDatasetId)],
              ['Hardware Target', isFwe && fwe.fwe_devices
                ? `🎮 ${(fweInfo?.defaults?.gpu_names || []).join(' + ')} — sharding blocchi`
                : (autotune?.gpu_names?.length
                  ? `🎮 ${autotune.gpu_names.join(' + ')} — ${autotune.strategy}`
                  : (hardware?.gpu?.[0]?.name ? `🎮 ${hardware.gpu[0].name}` : '💻 CPU Mode'))],
              ['Precisione', autotune
                ? `${autotune.dtype}${autotune.load_in_4bit ? ' + 4-bit' : ''}${autotune.tf32 ? ' + TF32' : ''}`
                : '—'],
              isFwe ? ['Tensori', fwe.fwe_include] : ['Epoche', numEpochs],
              isFwe ? ['Step', fwe.fwe_steps] : ['Contesto', `${maxSeqLen} token`],
              isFwe ? ['Codebook VQ', fwe.fwe_vq ? `K=${fwe.fwe_vq}` : 'latent liberi'] : null,
              ['Learning Rate', lr.toExponential(1)],
              ['Batch Size', `${batchSize}${!isFwe ? ` × ${gradAccum} accum` : ''}`],
              ['Output', outputName],
            ].filter(Boolean).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ color: 'var(--text-dim)' }}>{k}</span>
                <span style={{ color: 'var(--text)', fontFamily: 'JetBrains Mono', fontSize: '0.62rem' }}>{v}</span>
              </div>
            ))}
          </div>
        )}

        {/* ── Launch button ── */}
        <button
          className="training-start-btn"
          onClick={handleCreate}
          disabled={creating || (isContinuation ? !continueJobId : !finalModel.trim())
                    || (!selectedDatasetId && !isFwe)}
        >
          {creating ? (
            <><div className="training-spinner" style={{ width: '16px', height: '16px', borderColor: 'rgba(0,0,0,0.2)', borderTopColor: '#000' }} /> Creazione Job...</>
          ) : (
            <><Play size={16} fill="currentColor" /> Crea Job di Training</>
          )}
        </button>

        {!selectedDatasetId && !isFwe && (
          <div style={{ textAlign: 'center', fontSize: '0.62rem', color: 'var(--text-dark)', marginTop: '8px' }}>
            Seleziona un dataset per abilitare il training
          </div>
        )}
        {isFwe && (
          <div style={{ textAlign: 'center', fontSize: '0.62rem', color: 'var(--text-dark)', marginTop: '8px' }}>
            Il motore FWE usa il proprio corpus: nessun dataset richiesto
          </div>
        )}

      </div>
    </div>
  );
}
