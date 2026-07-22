import React from 'react';
import { BookOpen, Cpu, Database, BarChart2, Brain, ExternalLink } from 'lucide-react';

// ==============================================================================
// TrainingDocs — Documentazione completa del Training Lab
// Spiega concetti, metodi, iperparametri e flusso di lavoro
// ==============================================================================

const STYLES = {
  container: {
    flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
  },
  scroll: {
    flex: 1, overflowY: 'auto', padding: '18px',
  },
  section: {
    marginBottom: '24px',
  },
  h2: {
    fontSize: '1rem', fontWeight: 700, color: 'var(--text)',
    marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px',
  },
  h3: {
    fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)',
    marginBottom: '6px',
  },
  p: {
    fontSize: '0.72rem', color: 'var(--text-dim)', lineHeight: 1.65,
    marginBottom: '8px',
  },
  card: {
    background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)',
    borderRadius: '12px', padding: '14px 16px', marginBottom: '12px',
  },
  badge: (bg, color) => ({
    display: 'inline-block', padding: '2px 8px', borderRadius: '6px',
    fontSize: '0.6rem', fontWeight: 600, background: bg, color, marginRight: '4px',
  }),
  step: {
    display: 'flex', alignItems: 'flex-start', gap: '10px',
    padding: '10px 14px', marginBottom: '6px',
    background: 'rgba(255,255,255,0.02)', borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.04)', fontSize: '0.72rem', color: 'var(--text-dim)',
  },
  stepNum: {
    width: '22px', height: '22px', borderRadius: '50%',
    background: 'rgba(0,210,255,0.12)', color: 'var(--primary)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '0.65rem', fontWeight: 700, flexShrink: 0,
  },
  inlineCode: {
    background: 'rgba(0,0,0,0.3)', borderRadius: '4px',
    padding: '1px 5px', color: 'var(--primary)', fontSize: '0.65rem',
    fontFamily: 'JetBrains Mono',
  },
  table: {
    width: '100%', borderCollapse: 'collapse', fontSize: '0.65rem',
    marginBottom: '12px',
  },
  th: {
    textAlign: 'left', padding: '7px 10px', color: 'var(--text-dim)',
    borderBottom: '1px solid rgba(255,255,255,0.06)', fontWeight: 600,
    textTransform: 'uppercase', fontSize: '0.6rem', letterSpacing: '0.02em',
  },
  td: {
    padding: '7px 10px', color: 'var(--text)', borderBottom: '1px solid rgba(255,255,255,0.04)',
  },
};

const METHOD_CARDS = [
  {
    name: 'LoRA (Unsloth)',
    icon: '⚡',
    color: '#00d2ff',
    desc: 'Il metodo più efficiente in VRAM. Addestra solo piccoli adattatori (LoRA) invece di tutto il modello. 2x più veloce, 60% meno VRAM rispetto a SFT tradizionale.',
    quando: 'Hai una GPU consumer (4-12GB VRAM) e vuoi specializzare un modello esistente',
    vram: '4-12 GB',
    difficolta: 'Principiante',
    install: 'pip install unsloth trl transformers datasets',
  },
  {
    name: 'SFT (TRL)',
    icon: '🔬',
    color: '#bc8cff',
    desc: 'Supervised Fine-Tuning classico con PEFT/LoRA. Più controllabile, ideale per instruction tuning su modelli di medie dimensioni.',
    quando: 'Hai 12-24GB VRAM e vuoi il massimo controllo sul training',
    vram: '12-24 GB',
    difficolta: 'Intermedio',
    install: 'pip install trl peft transformers datasets',
  },
  {
    name: 'Full Pre-Training',
    icon: '🌐',
    color: '#ffa600',
    desc: 'Addestramento da zero su testo grezzo. Crea un modello nuovo da zero (es. GPT-2 su TinyStories). Richiede molti dati e VRAM.',
    quando: 'Vuoi creare un modello da zero per un dominio specifico o fare esperimenti di ricerca',
    vram: '4-80 GB',
    difficolta: 'Avanzato',
    install: 'pip install transformers datasets torch accelerate',
  },
  {
    name: 'Script Custom',
    icon: '🛠️',
    color: '#ff7043',
    desc: 'Template Python generico da personalizzare. Per utenti esperti che vogliono scrivere il proprio loop di training.',
    quando: 'Hai esigenze specifiche non coperte dagli altri metodi',
    vram: 'Variabile',
    difficolta: 'Esperto',
    install: 'Personalizzato',
  },
];

const HYPERPARAMS = [
  {
    name: 'Learning Rate',
    icon: '📐',
    desc: 'La velocità con cui il modello apprende. Valori tipici: 2e-4 per LoRA, 1e-5 per SFT.',
    consiglio: 'Troppo alto → divergenza. Troppo basso → apprendimento lentissimo. Inizia con 2e-4 per LoRA.',
    range: '1e-5 ÷ 1e-3',
  },
  {
    name: 'Batch Size',
    icon: '📦',
    desc: 'Numero di esempi processati per ogni passo di training. Batch più grande = gradiente più stabile ma più VRAM.',
    consiglio: 'Con 8GB VRAM usa batch_size=1 o 2. Con 24GB puoi arrivare a 8.',
    range: '1 ÷ 32',
  },
  {
    name: 'Num Epochs',
    icon: '🔄',
    desc: 'Quante volte il modello vede TUTTO il dataset. Più epoche = più apprendimento ma rischio overfitting.',
    consiglio: '3-5 per instruction tuning, 1-2 per dataset molto grandi (>100K esempi).',
    range: '1 ÷ 20',
  },
  {
    name: 'Max Seq Length',
    icon: '📏',
    desc: 'Lunghezza massima in token per ogni esempio. Testi più lunghi catturano più contesto ma richiedono più VRAM.',
    consiglio: '2048 per la maggior parte dei casi. 4096 per chat multi-turn. 8192 solo con GPU > 24GB.',
    range: '512 ÷ 8192',
  },
  {
    name: 'LoRA Rank (r)',
    icon: '🔗',
    desc: 'Grado della decomposizione LoRA. Più alto = più parametri addestrabili = più capacità ma più overfitting.',
    consiglio: '16 per bilanciamento ottimale. 8 per risparmiare VRAM. 32+ per massima qualità.',
    range: '4 ÷ 128',
  },
  {
    name: 'LoRA Alpha',
    icon: '⚖️',
    desc: 'Fattore di scala dei pesi LoRA. Solitamente uguale a LoRA Rank. Alfa > Rank amplifica l\'aggiornamento.',
    consiglio: 'Usa alpha = rank per iniziare. Alpha = 2× rank per apprendimento più forte.',
    range: '4 ÷ 256',
  },
  {
    name: 'Gradient Accumulation',
    icon: '📊',
    desc: 'Accumula gradienti per N step prima di aggiornare i pesi. Simula un batch più grande senza consumare più VRAM.',
    consiglio: 'batch_size=1 + grad_accum=4 = batch effettivo=4. Ottimo per GPU limitate.',
    range: '1 ÷ 32',
  },
];

const SCENARIOS = [
  {
    title: '💻 GPU Consumer (4-8GB VRAM)',
    steps: ['Usa metodo LoRA (Unsloth)', 'Modello: unsloth/llama-3.2-1b-instruct', 'Batch size: 1', 'Gradient accumulation: 4', 'Dataset piccolo: < 10K esempi', 'Max seq length: 2048'],
  },
  {
    title: '🎮 GPU Mid-Range (12-24GB VRAM)',
    steps: ['Usa metodo LoRA o SFT', 'Modello: unsloth/llama-3.2-3b-instruct', 'Batch size: 4-8', 'Dataset: 10K-100K esempi', 'Max seq length: 4096', 'LoRA Rank: 16-32'],
  },
  {
    title: '🚀 GPU High-End (24GB+ VRAM)',
    steps: ['Usa SFT o Full Pre-Train', 'Modello: unsloth/llama-3.1-8b-instruct+', 'Batch size: 8-16', 'Dataset: 100K+ esempi', 'Max seq length: 8192', 'LoRA Rank: 32-64'],
  },
  {
    title: '🌱 Da Zero (Pre-Training)',
    steps: ['Usa metodo Full Pre-Training', 'Modello: from_scratch o gpt2', 'Dataset: TinyStories (4GB VRAM) o The Pile (80GB VRAM)', 'Batch size: 2-8', 'Max seq length: 512-1024', 'Richiede giorni di training'],
  },
];

export default function TrainingDocs() {
  return (
    <div className="training-panel">
      <div style={STYLES.scroll}>

        {/* ── Introduzione ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <Brain size={18} style={{ color: 'var(--accent)' }} />
            Benvenuto nel Training Lab
          </div>
          <div style={STYLES.card}>
            <div style={STYLES.p}>
              Il <strong>Training Lab</strong> di Sigma Studio ti permette di <strong>specializzare, ottimizzare e migliorare</strong> modelli 
              LLM direttamente dal tuo computer. Puoi fare <strong>fine-tuning</strong> di modelli esistenti o addestrarne di nuovi 
              <strong>da zero</strong>.
            </div>
            <div style={STYLES.p}>
              <strong>Fine-tuning</strong> = prendere un modello già addestrato (es. Llama 3.2, Mistral) e <strong>specializzarlo</strong> 
              su un dominio specifico usando i tuoi dati. È come prendere un medico generico e specializzarlo in cardiologia.
            </div>
            <div style={STYLES.p}>
              Tutto il training è <strong>sandboxed</strong> nella cartella <code style={STYLES.inlineCode}>data/training/</code>.
              I modelli finiti possono essere esportati in <strong>Ollama</strong> per usarli in chat.
            </div>
          </div>
        </div>

        {/* ── Guida Passo-Passo ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <BarChart2 size={16} style={{ color: 'var(--primary)' }} />
            Guida Passo-Passo
          </div>
          <div style={STYLES.card}>
            {[
              ['Scegli il Metodo', 'Decidi quale tecnica di training usare (LoRA, SFT, Pre-Train, Custom) in base alla tua GPU e obiettivo. Vedi tabella comparativa sotto.'],
              ['Seleziona il Modello Base', 'Scegli il modello di partenza. Per fine-tuning usa modelli Unsloth (ottimizzati per VRAM). Per pre-training usa from_scratch o gpt2.'],
              ['Importa il Dataset', 'Vai alla tab Dataset per aggiungere dati. Puoi usare dataset consigliati (Alpaca, Dolly, GSM8K), cercare su HuggingFace, o importare file JSONL/CSV/TXT locali.'],
              ['Configura gli Iperparametri', 'Imposta learning rate, batch size, epoche e parametri LoRA. La configurazione influenza direttamente qualità e velocità del training.'],
              ['Avvia il Training', 'Crea il job e avvialo. Puoi monitorare loss, epoche e log in tempo reale nella tab Monitor.'],
              ['Esporta in Ollama', 'A training completato, esporta il modello in Ollama con un nome personalizzato. Usalo in chat con: ollama run nome_modello'],
            ].map(([title, desc], i) => (
              <div key={i} style={STYLES.step}>
                <div style={STYLES.stepNum}>{i + 1}</div>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text)', marginBottom: '3px' }}>{title}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Metodi di Training ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <Cpu size={16} style={{ color: '#00d2ff' }} />
            Metodi di Training
          </div>
          {METHOD_CARDS.map((m, i) => (
            <div key={i} style={{
              ...STYLES.card,
              borderLeft: `2px solid ${m.color}40`,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '6px' }}>
                <span style={{ fontSize: '20px' }}>{m.icon}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: m.color }}>{m.name}</div>
                  <div style={STYLES.p}>{m.desc}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                <span style={STYLES.badge('rgba(0,210,255,0.1)', '#00d2ff')}>🖥️ {m.vram} VRAM</span>
                <span style={STYLES.badge('rgba(188,140,255,0.1)', '#bc8cff')}>📊 {m.difficolta}</span>
              </div>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', lineHeight: 1.5 }}>
                <strong>Quando usarlo:</strong> {m.quando}<br />
                <strong>Installa:</strong> <code style={STYLES.inlineCode}>{m.install}</code>
              </div>
            </div>
          ))}
        </div>

        {/* ── Tabella Comparativa ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <BookOpen size={16} style={{ color: 'var(--warning)' }} />
            Tabella Comparativa
          </div>
          <div style={STYLES.card} style={{ overflowX: 'auto' }}>
            <table style={STYLES.table}>
              <thead>
                <tr>
                  <th style={STYLES.th}>Metodo</th>
                  <th style={STYLES.th}>VRAM Min</th>
                  <th style={STYLES.th}>Velocità</th>
                  <th style={STYLES.th}>Qualità</th>
                  <th style={STYLES.th}>Difficoltà</th>
                  <th style={STYLES.th}>Ideale per</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['LoRA (Unsloth)', '4GB', '⚡⚡⚡⚡⚡', '✅ Buona', 'Principiante', 'Fine-tuning veloce'],
                  ['SFT (TRL)', '12GB', '⚡⚡⚡', '✅✅ Ottima', 'Intermedio', 'Instruction tuning'],
                  ['Full Pre-Train', '4GB+', '⚡', '✅✅✅ Massima', 'Avanzato', 'Modelli da zero'],
                  ['Script Custom', '—', '—', '—', 'Esperto', 'Ricerca avanzata'],
                ].map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j} style={STYLES.td}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Iperparametri ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <BarChart2 size={16} style={{ color: 'var(--accent)' }} />
            Iperparametri Spiegati
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            {HYPERPARAMS.map((h, i) => (
              <div key={i} style={STYLES.card}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
                  {h.icon} {h.name} <span style={{ fontSize: '0.6rem', color: 'var(--text-dark)', fontWeight: 400 }}>({h.range})</span>
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.55, marginBottom: '4px' }}>{h.desc}</div>
                <div style={{ fontSize: '0.6rem', color: 'var(--primary)', lineHeight: 1.4, background: 'rgba(0,210,255,0.04)', borderRadius: '6px', padding: '4px 8px' }}>
                  💡 {h.consiglio}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Scenari Tipici ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            <Cpu size={16} style={{ color: 'var(--success)' }} />
            Scenari Tipici
          </div>
          {SCENARIOS.map((s, i) => (
            <div key={i} style={STYLES.card}>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text)', marginBottom: '8px' }}>{s.title}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {s.steps.map((step, j) => (
                  <span key={j} style={{
                    padding: '4px 10px', borderRadius: '8px',
                    background: 'rgba(0,210,255,0.05)', border: '1px solid rgba(0,210,255,0.1)',
                    color: 'var(--text-dim)', fontSize: '0.6rem', lineHeight: 1.4,
                  }}>
                    {step}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* ── Export ── */}
        <div style={STYLES.section}>
          <div style={STYLES.h2}>
            🦙 Export in Ollama
          </div>
          <div style={STYLES.card}>
            <div style={STYLES.p}>
              Dopo il training, puoi esportare il modello in <strong>Ollama</strong> per usarlo come qualsiasi altro modello.
              Sigma Studio genera automaticamente un <strong>Modelfile</strong> con il system prompt personalizzato.
            </div>
            <div style={STYLES.p}>
              Una volta esportato, usa il modello in chat:
            </div>
            <div style={{
              background: 'rgba(0,0,0,0.4)', borderRadius: '8px', padding: '10px 14px',
              fontFamily: 'JetBrains Mono', fontSize: '0.65rem', color: 'var(--primary)', lineHeight: 1.6,
            }}>
              {`# Usa il modello in chat\nollama run sigma_mio_modello\n\n# Oppure dalla chat Sigma\n(Seleziona il modello dal menu a tendina dei modelli)`}
            </div>
          </div>
        </div>

        {/* ── Note finali ── */}
        <div style={{
          ...STYLES.card,
          background: 'rgba(188,140,255,0.04)', border: '1px solid rgba(188,140,255,0.12)',
        }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>🧬</span>
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent)', marginBottom: '4px' }}>
                Principi Sigma per il Training
              </div>
              <ul style={{ fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.7, margin: 0, paddingLeft: '16px' }}>
                <li><strong>Inizia piccolo</strong> — usa TinyStories + from_scratch per testare il flusso</li>
                <li><strong>Monitora la loss</strong> — se non scende, qualcosa non va (LR troppo alto/basso, dati sporchi)</li>
                <li><strong>Backup prima del training</strong> — i job sono salvati su disco, ma conserva i tuoi dataset originali</li>
                <li><strong>Un teorema non è dimostrato finché non è stato testato</strong> — valida sempre il modello dopo il training</li>
              </ul>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}