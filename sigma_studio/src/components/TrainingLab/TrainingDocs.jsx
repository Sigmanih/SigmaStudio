import React, { useState, useMemo } from 'react';
import { 
  BookOpen, Cpu, Database, BarChart2, Brain, Check, Copy, 
  Search, Zap, HardDrive, Terminal, HelpCircle, Layers, Sparkles, X, ChevronRight, Scale, Sliders
} from 'lucide-react';

// ==============================================================================
// TrainingDocs — Redesign Smart & Moderno per Sigma Studio
// ==============================================================================

const VRAM_RECOMMENDATIONS = {
  '4gb': {
    title: '💻 GPU Entry (4-6 GB VRAM)',
    method: 'LoRA (Unsloth)',
    model: 'unsloth/llama-3.2-1b-instruct',
    batchSize: 1,
    gradAccum: 4,
    seqLen: 1024,
    loraRank: 8,
    datasetLimit: '< 10.000 esempi',
    note: 'Consigliata quantizzazione 4-bit per evitare Out of Memory (OOM).',
  },
  '8gb': {
    title: '🎮 GPU Consumer (8 GB VRAM)',
    method: 'LoRA (Unsloth / TRL)',
    model: 'unsloth/llama-3.2-3b-instruct',
    batchSize: 2,
    gradAccum: 4,
    seqLen: 2048,
    loraRank: 16,
    datasetLimit: '10.000 ÷ 50.000 esempi',
    note: 'Ottimo bilanciamento per fine-tuning su compiti di conversazione ed estrazione.',
  },
  '12gb': {
    title: '⚡ GPU Mid-Range (12 GB VRAM)',
    method: 'LoRA / SFT (TRL)',
    model: 'unsloth/mistral-7b-instruct-v0.3',
    batchSize: 4,
    gradAccum: 2,
    seqLen: 4096,
    loraRank: 32,
    datasetLimit: '50.000 ÷ 150.000 esempi',
    note: 'Capace di gestire contesti medi e modelli da 7B-8B parametri senza difficoltà.',
  },
  '16gb': {
    title: '🚀 GPU Pro (16 GB VRAM)',
    method: 'LoRA / SFT / Forgia SLM',
    model: 'unsloth/qwen2.5-7b-instruct',
    batchSize: 4,
    gradAccum: 4,
    seqLen: 4096,
    loraRank: 64,
    datasetLimit: '150.000+ esempi',
    note: 'Supporta Rank LoRA alti per massima capacità di apprendimento.',
  },
  '24gb': {
    title: '🔥 GPU High-End (24 GB+ VRAM)',
    method: 'Full Pre-Training / SFT 8B+',
    model: 'unsloth/llama-3.1-8b-instruct+',
    batchSize: 8,
    gradAccum: 2,
    seqLen: 8192,
    loraRank: 128,
    datasetLimit: 'Illimitato',
    note: 'Ideale per addestrare modelli da zero o fine-tuning integrale ad altissima qualità.',
  },
};

const METHOD_CARDS = [
  {
    id: 'lora',
    name: 'LoRA (Unsloth)',
    icon: '⚡',
    color: '#00d2ff',
    bg: 'rgba(0,210,255,0.06)',
    border: 'rgba(0,210,255,0.22)',
    desc: 'Metodo ultra-efficiente che addestra un piccolo adattatore (low-rank adapter) sui pesi esistenti. Fino a 2x più veloce col 60% in meno di VRAM.',
    quando: 'GPU consumer (4-12GB) o fine-tuning veloce di modelli esistenti',
    vram: '4 - 12 GB',
    difficolta: 'Principiante',
    install: 'pip install unsloth trl transformers datasets',
  },
  {
    id: 'sft',
    name: 'SFT (TRL)',
    icon: '🔬',
    color: '#bc8cff',
    bg: 'rgba(188,140,255,0.06)',
    border: 'rgba(188,140,255,0.22)',
    desc: 'Supervised Fine-Tuning classico con PEFT/LoRA tramite la libreria TRL. Offre massimo controllo sulle loss mask e sui formati di conversazione.',
    quando: 'GPU da 12-24GB VRAM dove si ricerca controllo totale sul loop di training',
    vram: '12 - 24 GB',
    difficolta: 'Intermedio',
    install: 'pip install trl peft transformers datasets',
  },
  {
    id: 'pretrain',
    name: 'Full Pre-Training',
    icon: '🌐',
    color: '#ffa600',
    bg: 'rgba(255,184,108,0.06)',
    border: 'rgba(255,184,108,0.22)',
    desc: "Addestramento da zero su testo grezzo non strutturato. Crea un'architettura da zero (es. GPT-2 su TinyStories). Richiede un gran volume di dati.",
    quando: 'Creazione di nuovi modelli per domini specialistici o ricerca',
    vram: '4 - 80 GB',
    difficolta: 'Avanzato',
    install: 'pip install transformers datasets torch accelerate',
  },
  {
    id: 'gradus',
    name: 'Gradus FWE',
    icon: '🧬',
    color: '#3fb950',
    bg: 'rgba(63,185,80,0.06)',
    border: 'rgba(63,185,80,0.22)',
    desc: 'Functional Weight Engine: i pesi vengono generati da un decoder AILO da 152M guidato da un codebook VQ. Riduce il payload a soli ~0.5 MB.',
    quando: 'Compressione spinta di modelli e ricerca su generatori di pesi funzionali',
    vram: '6 - 16 GB',
    difficolta: 'Ricerca',
    install: 'pip install torch transformers datasets',
  },
];

const HYPERPARAMS = [
  {
    name: 'Learning Rate',
    icon: '📐',
    range: '1e-5 ÷ 1e-3',
    suggested: '2e-4 (LoRA)',
    desc: 'Velocità di aggiornamento dei pesi. Valori troppo alti causano divergenza della loss.',
    consiglio: 'Per LoRA inizia con 2e-4. Per SFT su modelli grandi usa 1e-5 o 2e-5.',
  },
  {
    name: 'Batch Size',
    icon: '📦',
    range: '1 ÷ 32',
    suggested: '1 - 4 per GPU < 12GB',
    desc: 'Numero di esempi processati in parallelo ad ogni passo di gradiente.',
    consiglio: 'Se riscontri errori di VRAM (OOM), riduci il batch size a 1 e aumenta il Gradient Accumulation.',
  },
  {
    name: 'Gradient Accumulation',
    icon: '📊',
    range: '1 ÷ 32',
    suggested: '4',
    desc: 'Simula un batch size più grande senza occupare VRAM aggiuntiva.',
    consiglio: 'Batch Size (1) × Grad Accum (4) = Batch effettivo (4). Essenziale su schede consumer.',
  },
  {
    name: 'Num Epochs',
    icon: '🔄',
    range: '1 ÷ 20',
    suggested: '3 epoche',
    desc: 'Quante volte l\'intero dataset viene mostrato al modello durante il training.',
    consiglio: '3 epoche sono il gold standard. Oltre le 5 epoche aumenta drasticamente il rischio overfitting.',
  },
  {
    name: 'Max Seq Length',
    icon: '📏',
    range: '512 ÷ 8192 tok',
    suggested: '2048 / 4096',
    desc: 'Lunghezza massima in token per singola conversazione. Testi oltre questo limite vengono troncati.',
    consiglio: 'Attenzione: raddoppiare il contesto quadruplica il consumo di VRAM nella memoria attenzione.',
  },
  {
    name: 'LoRA Rank (r)',
    icon: '🔗',
    range: '4 ÷ 128',
    suggested: '16 o 32',
    desc: 'Dimensione della matrice adattatore LoRA. Più alto = maggiore capacità di apprendimento.',
    consiglio: '16 offre l\'equilibrio ideale. Usa 32 o 64 se devi far imparare concetti logici complessi.',
  },
];

export default function TrainingDocs() {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');
  const [vramTier, setVramTier] = useState('8gb');
  const [copiedText, setCopiedText] = useState(null);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedText(key);
    setTimeout(() => setCopiedText(null), 2500);
  };

  const selectedVram = VRAM_RECOMMENDATIONS[vramTier];

  // Search filter
  const filteredParams = useMemo(() => {
    if (!search.trim()) return HYPERPARAMS;
    const q = search.toLowerCase().trim();
    return HYPERPARAMS.filter(h => 
      h.name.toLowerCase().includes(q) || 
      h.desc.toLowerCase().includes(q) || 
      h.consiglio.toLowerCase().includes(q)
    );
  }, [search]);

  const filteredMethods = useMemo(() => {
    if (!search.trim()) return METHOD_CARDS;
    const q = search.toLowerCase().trim();
    return METHOD_CARDS.filter(m => 
      m.name.toLowerCase().includes(q) || 
      m.desc.toLowerCase().includes(q) || 
      m.quando.toLowerCase().includes(q)
    );
  }, [search]);

  return (
    <div className="training-panel">
      <div className="training-scroll-area" style={{ padding: '20px 24px' }}>
        
        {/* Top Header — Stile Hardware & GPU Lab */}
        <div className="app-page-header" style={{ marginBottom: '20px' }}>
          <div className="app-page-header-title">
            <div className="app-page-header-icon">
              <BookOpen size={22} color="#00f2fe" />
            </div>
            <div>
              <h1>Documentazione Training Lab</h1>
              <div className="app-page-header-subtitle">
                <span>Manuale interattivo al Fine-Tuning</span>
                <span>•</span>
                <span style={{ color: '#00f2fe', fontFamily: 'JetBrains Mono, monospace' }}>
                  Metodi • Iperparametri • Scenari VRAM • Ollama
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Search & Filters Container ── */}
        <div style={{
          position: 'relative', overflow: 'hidden', borderRadius: '16px',
          background: 'linear-gradient(135deg, rgba(0,210,255,0.06) 0%, rgba(188,140,255,0.04) 50%, rgba(10,12,26,0.9) 100%)',
          border: '1px solid rgba(0,210,255,0.18)', padding: '16px 20px', marginBottom: '22px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
        }}>
          {/* Barra di ricerca smart interna */}
          <div style={{ position: 'relative', marginTop: '16px', maxWidth: '640px' }}>
            <Search size={15} style={{
              position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)',
              color: 'var(--text-dark)', pointerEvents: 'none',
            }} />
            <input
              className="training-input"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Cerca nella guida (es. LoRA, VRAM, learning rate, Unsloth, batch size, Ollama)..."
              style={{
                fontSize: '0.74rem', paddingLeft: '34px', paddingRight: search ? '32px' : '14px',
                background: 'rgba(0,0,0,0.4)', borderRadius: '10px', height: '38px',
                border: '1px solid rgba(0,210,255,0.25)', boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
              }}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{
                  position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer',
                  padding: '2px', display: 'flex', alignItems: 'center',
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Chips di navigazione rapida */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '14px' }}>
            {[
              ['all', 'Tutti i Contenuti', Sparkles],
              ['quick', '🚀 Inizio Rapido', Zap],
              ['methods', '⚡ Metodi', Cpu],
              ['params', '📐 Iperparametri', Sliders],
              ['vram', '💻 Advisor VRAM', HardDrive],
              ['ollama', '🦙 Export Ollama', Terminal],
            ].map(([id, label, Icon]) => (
              <button
                key={id}
                onClick={() => setActiveCategory(id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 11px',
                  borderRadius: '8px', fontSize: '0.65rem', fontWeight: activeCategory === id ? 700 : 500,
                  cursor: 'pointer', border: '1px solid',
                  borderColor: activeCategory === id ? 'rgba(0,210,255,0.4)' : 'rgba(255,255,255,0.06)',
                  background: activeCategory === id ? 'rgba(0,210,255,0.12)' : 'rgba(255,255,255,0.03)',
                  color: activeCategory === id ? 'var(--primary)' : 'var(--text-dim)',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>
        </div>

        {/* ── SEZIONE 1: Inizio Rapido & Flusso Guidato ── */}
        {(activeCategory === 'all' || activeCategory === 'quick') && (
          <div style={{ marginBottom: '26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Zap size={16} style={{ color: 'var(--primary)' }} />
              <h2 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Inizio Rapido — I 6 Passaggi del Training
              </h2>
            </div>
            
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px',
            }}>
              {[
                ['1. Scegli il Metodo', 'Seleziona la tecnica (LoRA Unsloth per GPU consumer, SFT per controllo avanzato o Pre-train per modelli da zero).'],
                ['2. Scegli il Modello', 'Seleziona un modello di partenza da Ollama o HuggingFace (es. Llama 3.2 1B / Mistral 7B).'],
                ['3. Collega il Dataset', 'Importa file JSONL/CSV/TXT locali o scarica dataset pronti da HuggingFace nella scheda Dataset.'],
                ['4. Regola gli Iperparametri', 'Imposta Learning Rate (2e-4), Batch Size (1-4) ed Epoche (3). Usa l\'advisor VRAM qui sotto.'],
                ['5. Avvia & Monitora', 'Lancia il job e osserva il grafico della Loss che decresce in tempo reale nella scheda Monitor.'],
                ['6. Esporta in Ollama', 'A fine training il modello viene pacchettizzato in Ollama pronto per le tue chat locali.'],
              ].map(([stepTitle, stepDesc], i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '12px', padding: '12px 14px', display: 'flex', gap: '12px', alignItems: 'flex-start',
                }}>
                  <div style={{
                    width: '26px', height: '26px', borderRadius: '8px',
                    background: 'rgba(0,210,255,0.12)', color: 'var(--primary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.72rem', fontWeight: 800, flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <div>
                    <div style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text)', marginBottom: '3px' }}>{stepTitle}</div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>{stepDesc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── SEZIONE 2: Hardware & VRAM Advisor Interattivo ── */}
        {(activeCategory === 'all' || activeCategory === 'vram') && (
          <div style={{ marginBottom: '26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <HardDrive size={16} style={{ color: 'var(--success)' }} />
              <h2 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Calcolatore & Advisor VRAM Interattivo
              </h2>
            </div>

            <div style={{
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: '14px', padding: '16px',
            }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', marginBottom: '12px' }}>
                Seleziona la quantità di VRAM disponibile sulla tua scheda grafica per ottenere la configurazione raccomandata:
              </div>

              {/* Tasti Taglio VRAM */}
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
                {[
                  ['4gb', '4-6 GB VRAM'],
                  ['8gb', '8 GB VRAM'],
                  ['12gb', '12 GB VRAM'],
                  ['16gb', '16 GB VRAM'],
                  ['24gb', '24 GB+ VRAM'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setVramTier(key)}
                    style={{
                      padding: '6px 14px', borderRadius: '8px', fontSize: '0.68rem', fontWeight: vramTier === key ? 700 : 500,
                      cursor: 'pointer', border: '1px solid',
                      borderColor: vramTier === key ? 'rgba(63,185,80,0.4)' : 'rgba(255,255,255,0.08)',
                      background: vramTier === key ? 'rgba(63,185,80,0.12)' : 'rgba(255,255,255,0.03)',
                      color: vramTier === key ? 'var(--success)' : 'var(--text-dim)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Card Raccomandazione */}
              <div style={{
                background: 'rgba(63,185,80,0.04)', border: '1px solid rgba(63,185,80,0.2)',
                borderRadius: '12px', padding: '14px 16px',
              }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {selectedVram.title}
                </div>

                <div style={{
                  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', marginBottom: '10px',
                }}>
                  {[
                    ['Metodo ideale', selectedVram.method],
                    ['Modello consigliato', selectedVram.model],
                    ['Batch Size / Grad Accum', `${selectedVram.batchSize} / ${selectedVram.gradAccum}`],
                    ['Max Seq Length', `${selectedVram.seqLen} token`],
                    ['LoRA Rank (r)', selectedVram.loraRank],
                    ['Dimensione Dataset', selectedVram.datasetLimit],
                  ].map(([label, val]) => (
                    <div key={label} style={{
                      background: 'rgba(0,0,0,0.25)', padding: '6px 10px', borderRadius: '8px',
                      border: '1px solid rgba(255,255,255,0.05)',
                    }}>
                      <div style={{ fontSize: '0.55rem', color: 'var(--text-dark)', textTransform: 'uppercase', fontWeight: 700, marginBottom: '2px' }}>{label}</div>
                      <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace' }}>{val}</div>
                    </div>
                  ))}
                </div>

                <div style={{ fontSize: '0.64rem', color: 'var(--success)', lineHeight: 1.5 }}>
                  💡 <strong>Consiglio pratico:</strong> {selectedVram.note}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── SEZIONE 3: Metodi di Training ── */}
        {(activeCategory === 'all' || activeCategory === 'methods') && (
          <div style={{ marginBottom: '26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Cpu size={16} style={{ color: '#00d2ff' }} />
              <h2 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Metodi di Training Disponibili
              </h2>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px' }}>
              {filteredMethods.map((m) => (
                <div key={m.id} style={{
                  background: m.bg, border: `1px solid ${m.border}`,
                  borderRadius: '14px', padding: '16px', display: 'flex', flexDirection: 'column',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '1.4rem' }}>{m.icon}</span>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: m.color }}>{m.name}</div>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-dark)', fontWeight: 600 }}>
                        VRAM: {m.vram} · Difficoltà: {m.difficolta}
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', lineHeight: 1.55, marginBottom: '10px', flex: 1 }}>
                    {m.desc}
                  </div>

                  <div style={{ fontSize: '0.63rem', color: 'var(--text-dim)', marginBottom: '8px', lineHeight: 1.45 }}>
                    <strong>Quando sceglierlo:</strong> {m.quando}
                  </div>

                  <div style={{
                    background: 'rgba(0,0,0,0.3)', borderRadius: '8px', padding: '6px 10px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <code style={{ fontSize: '0.6rem', color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}>
                      {m.install}
                    </code>
                    <button
                      onClick={() => copyToClipboard(m.install, m.id)}
                      style={{
                        background: 'none', border: 'none', color: 'var(--text-dark)', cursor: 'pointer',
                        padding: '2px', display: 'flex', alignItems: 'center',
                      }}
                      title="Copia comando"
                    >
                      {copiedText === m.id ? <Check size={12} style={{ color: 'var(--success)' }} /> : <Copy size={12} />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── SEZIONE 4: Iperparametri Spiegati ── */}
        {(activeCategory === 'all' || activeCategory === 'params') && (
          <div style={{ marginBottom: '26px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Sliders size={16} style={{ color: 'var(--accent)' }} />
              <h2 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Iperparametri & Regolazioni
              </h2>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
              {filteredParams.map((h, i) => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: '12px', padding: '14px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text)' }}>
                      {h.icon} {h.name}
                    </div>
                    <span style={{
                      fontSize: '0.58rem', fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)',
                      background: 'rgba(188,140,255,0.1)', padding: '1px 6px', borderRadius: '5px',
                    }}>
                      {h.range}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.66rem', color: 'var(--text-dim)', lineHeight: 1.5, marginBottom: '8px' }}>
                    {h.desc}
                  </div>

                  <div style={{
                    background: 'rgba(0,210,255,0.04)', border: '1px solid rgba(0,210,255,0.12)',
                    borderRadius: '8px', padding: '6px 9px', fontSize: '0.62rem', color: 'var(--primary)', lineHeight: 1.45,
                  }}>
                    💡 <strong>Valore consigliato:</strong> {h.suggested}. {h.consiglio}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── SEZIONE 5: Export in Ollama ── */}
        {(activeCategory === 'all' || activeCategory === 'ollama') && (
          <div style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Terminal size={16} style={{ color: '#bc8cff' }} />
              <h2 style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
                Esportazione e Utilizzo in Ollama
              </h2>
            </div>

            <div style={{
              background: 'rgba(188,140,255,0.04)', border: '1px solid rgba(188,140,255,0.18)',
              borderRadius: '14px', padding: '16px',
            }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', lineHeight: 1.6, marginBottom: '12px' }}>
                Una volta completato il training, il modello pacchettizzato viene registrato in <strong>Ollama</strong>.
                Puoi testarlo direttamente dal terminale o selezionarlo dal menu a tendina della chat di Sigma Studio.
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.5)', borderRadius: '10px', padding: '12px 14px',
                border: '1px solid rgba(255,255,255,0.08)', position: 'relative',
              }}>
                <pre style={{
                  margin: 0, fontFamily: 'JetBrains Mono, monospace', fontSize: '0.66rem',
                  color: 'var(--primary)', lineHeight: 1.65,
                }}>
                  {`# Avvia il tuo modello specializzato nel terminale\nollama run sigma_mio_modello\n\n# Oppure seleziona "sigma_mio_modello" dal menu a tendina della Chat`}
                </pre>
                <button
                  onClick={() => copyToClipboard('ollama run sigma_mio_modello', 'ollama_cmd')}
                  style={{
                    position: 'absolute', right: '10px', top: '10px',
                    background: 'rgba(255,255,255,0.06)', border: 'none', color: 'var(--text-dim)',
                    cursor: 'pointer', padding: '4px 8px', borderRadius: '6px', fontSize: '0.6rem',
                    display: 'flex', alignItems: 'center', gap: '4px',
                  }}
                >
                  {copiedText === 'ollama_cmd' ? <Check size={12} style={{ color: 'var(--success)' }} /> : <Copy size={12} />}
                  <span>{copiedText === 'ollama_cmd' ? 'Copiato!' : 'Copia'}</span>
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}