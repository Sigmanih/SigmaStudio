import React, { useState, useEffect } from 'react';
import { Play, Square, Cpu, Brain, Sliders, Database, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

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
  },
  {
    id: 'trl_sft',
    name: 'SFT',
    fullName: 'SFT (TRL)',
    desc: 'Stabile',
    req: 'Richiede: trl, peft',
    color: '#bc8cff',
    icon: '🔬',
  },
  {
    id: 'script_custom',
    name: 'Custom',
    fullName: 'Script Custom',
    desc: 'Flessibile',
    req: 'Script Python tuo',
    color: '#ffa600',
    icon: '🛠️',
  },
];

const POPULAR_MODELS = [
  'unsloth/llama-3.2-3b-instruct',
  'unsloth/llama-3.2-1b-instruct',
  'unsloth/llama-3.1-8b-instruct',
  'unsloth/mistral-7b-instruct-v0.3',
  'unsloth/Phi-3-mini-4k-instruct',
  'unsloth/gemma-2-2b-it',
  'meta-llama/Llama-3.2-3B-Instruct',
  'microsoft/Phi-3-mini-4k-instruct',
  'mistralai/Mistral-7B-Instruct-v0.3',
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

export default function TrainingConfigurator({ myDatasets, onJobCreated, addToast }) {
  const [method, setMethod] = useState('lora_unsloth');
  const [baseModel, setBaseModel] = useState('unsloth/llama-3.2-3b-instruct');
  const [customModel, setCustomModel] = useState('');
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [outputName, setOutputName] = useState('');
  const [textField, setTextField] = useState('text');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [creating, setCreating] = useState(false);
  const [ollamaModels, setOllamaModels] = useState([]);

  // Hyperparams
  const [numEpochs, setNumEpochs] = useState(3);
  const [lr, setLr] = useState(2e-4);
  const [batchSize, setBatchSize] = useState(2);
  const [maxSeqLen, setMaxSeqLen] = useState(2048);
  const [loraR, setLoraR] = useState(16);
  const [loraAlpha, setLoraAlpha] = useState(16);
  const [gradAccum, setGradAccum] = useState(4);

  const [hardware, setHardware] = useState(null);

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
  }, []);

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

  const handleCreate = async () => {
    if (!finalModel.trim()) {
      addToast && addToast('Seleziona un modello base', 'error');
      return;
    }
    if (!selectedDatasetId) {
      addToast && addToast('Seleziona un dataset prima di avviare il training', 'warning');
      return;
    }
    setCreating(true);
    try {
      const res = await fetch('/api/training/job/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_model: finalModel.trim(),
          dataset_id: selectedDatasetId,
          method,
          output_name: outputName || 'sigma_model',
          hyperparams: {
            num_epochs: numEpochs,
            learning_rate: lr,
            batch_size: batchSize,
            max_seq_length: maxSeqLen,
            lora_r: loraR,
            lora_alpha: loraAlpha,
            gradient_accumulation: gradAccum,
            text_field: textField,
          },
        }),
      });
      const data = await res.json();
      if (data.success) {
        addToast && addToast(`✅ Job "${data.job.id}" creato!`, 'success');
        if (onJobCreated) onJobCreated(data.job);
      } else {
        addToast && addToast(`Errore: ${data.error}`, 'error');
      }
    } catch (e) {
      addToast && addToast('Errore di rete', 'error');
    } finally {
      setCreating(false);
    }
  };

  const allModels = [...new Set([...POPULAR_MODELS, ...ollamaModels])];

  return (
    <div className="training-panel">
      <div className="training-scroll-area">

        {/* ── Method selector ── */}
        <div style={{ marginBottom: '20px' }}>
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
          {method === 'script_custom' && (
            <div style={{
              marginTop: '8px', padding: '8px 12px', background: 'rgba(255,166,0,0.05)',
              border: '1px solid rgba(255,166,0,0.12)', borderRadius: '8px', fontSize: '0.62rem', color: 'var(--text-dim)'
            }}>
              🛠️ <strong style={{ color: '#ffa600' }}>Modalità Custom</strong> — Sigma genera un template Python che puoi modificare prima di avviare.
            </div>
          )}
        </div>

        <div className="training-divider" />

        {/* ── Base Model ── */}
        <div style={{ marginBottom: '20px' }}>
          <div className="training-section-header">
            <Cpu size={14} />
            <h3>Modello Base</h3>
          </div>
          <div className="training-config-grid">
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
                <select
                  className="training-select"
                  value={baseModel}
                  onChange={e => setBaseModel(e.target.value)}
                  style={{ marginTop: '6px' }}
                >
                  <optgroup label="🤗 HuggingFace (Unsloth optimized)">
                    {POPULAR_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                  </optgroup>
                  {ollamaModels.length > 0 && (
                    <optgroup label="🦙 Ollama (locale)">
                      {ollamaModels.map(m => <option key={`ollama:${m}`} value={m}>{m}</option>)}
                    </optgroup>
                  )}
                </select>
              ) : (
                <input
                  className="training-input"
                  placeholder="es: meta-llama/Llama-3.2-3B-Instruct"
                  value={customModel}
                  onChange={e => setCustomModel(e.target.value)}
                  style={{ marginTop: '6px' }}
                />
              )}
            </div>
          </div>
        </div>

        <div className="training-divider" />

        {/* ── Dataset ── */}
        <div style={{ marginBottom: '20px' }}>
          <div className="training-section-header">
            <Database size={14} />
            <h3>Dataset</h3>
            {selectedDs && (
              <span className="training-section-sub">
                ✓ {selectedDs.name}
                {selectedDs.row_count && ` (${selectedDs.row_count.toLocaleString()} esempi)`}
              </span>
            )}
          </div>
          {(!myDatasets || myDatasets.length === 0) ? (
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
                    onClick={() => setSelectedDatasetId(ds.id)}
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

        {/* ── Base Hyperparams ── */}
        <div style={{ marginBottom: '20px' }}>
          <div className="training-section-header">
            <Sliders size={14} />
            <h3>Iperparametri</h3>
          </div>
          <div className="training-config-grid">
            <HyperParam
              label="Epoche"
              desc="Quante volte passare sul dataset"
              value={numEpochs}
              min={1} max={20} step={1}
              onChange={setNumEpochs}
            />
            <HyperParam
              label="Batch Size"
              desc="Esempi per step GPU"
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
            <HyperParam
              label="Contesto Max (token)"
              desc="Lunghezza massima sequenza"
              value={maxSeqLen}
              min={512} max={8192} step={512}
              onChange={setMaxSeqLen}
              display={v => `${v}`}
            />
          </div>

          {/* Advanced toggle */}
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
                desc="Grado del decomposizione LoRA"
                value={loraR}
                min={4} max={128} step={4}
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
        </div>

        <div className="training-divider" />

        {/* ── Output name ── */}
        <div className="training-field" style={{ marginBottom: '20px' }}>
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
        {finalModel && selectedDatasetId && (
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: '12px', padding: '14px', marginBottom: '16px', fontSize: '0.68rem',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: '8px' }}>📋 Riepilogo Job</div>
            {[
              ['Metodo', METHODS.find(m => m.id === method)?.fullName],
              ['Base Model', finalModel],
              ['Dataset', selectedDs?.name || selectedDatasetId],
              ['Hardware Target', hardware?.gpu_count > 1 
                ? `⚡ Multi-GPU (${hardware.gpu_count} Schede: ${hardware.multi_gpu?.total_vram_gb} GB VRAM - device_map='auto')`
                : (hardware?.gpu?.[0]?.name ? `🎮 1 GPU (${hardware.gpu[0].name})` : '💻 CPU Mode')],
              ['Epoche', numEpochs],
              ['Learning Rate', lr.toExponential(1)],
              ['Batch Size', batchSize],
              ['Contesto', `${maxSeqLen} token`],
              ['Output', outputName],
            ].map(([k, v]) => (
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
          disabled={creating || !finalModel.trim() || !selectedDatasetId}
        >
          {creating ? (
            <><div className="training-spinner" style={{ width: '16px', height: '16px', borderColor: 'rgba(0,0,0,0.2)', borderTopColor: '#000' }} /> Creazione Job...</>
          ) : (
            <><Play size={16} fill="currentColor" /> Crea Job di Training</>
          )}
        </button>

        {!selectedDatasetId && (
          <div style={{ textAlign: 'center', fontSize: '0.62rem', color: 'var(--text-dark)', marginTop: '8px' }}>
            Seleziona un dataset per abilitare il training
          </div>
        )}

      </div>
    </div>
  );
}
