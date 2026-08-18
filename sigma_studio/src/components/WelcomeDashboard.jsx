import React, { useEffect, useState, useRef, useCallback } from 'react';
import { 
  FolderTree, MessageSquare, Edit3, Share2, Palette, 
  FlaskConical, Cpu, Home as HomeIcon, Scroll, Microscope, ArrowRight,
  Sun, Moon, Store, Sparkles, ShieldCheck, Zap, Layers,
  Activity, Calendar, Brain, FileText, PieChart, Wrench, Compass, CheckCircle2, Key, DownloadCloud
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import TechSpaceCanvas from './common/TechSpaceCanvas';

const PRIMI_PASSI_CARDS = [
  {
    step: '01',
    category: 'setup',
    categoryLabel: 'Token & Providers',
    badgeText: 'FONDAMENTA',
    title: 'Configura Token & Providers AI',
    subtitle: 'Gestisci le API key in modo sicuro (OpenAI, Claude, DeepSeek, Google, Groq) e collega Ollama GPU.',
    tip: 'Concentra tutti i token in un unico hub sicuro e testa le connessioni con un click.',
    icon: Key,
    color: '#00d2ff',
    actionText: 'Configurazione AI ⚙️',
    onClick: (openTab) => openTab({ name: '⚙️ Configurazione AI' }, 'ai_config')
  },
  {
    step: '02',
    category: 'setup',
    categoryLabel: 'Ruoli & Manifesti',
    badgeText: 'IDENTITÀ',
    title: 'Scegli il tuo Ruolo Specialistico',
    subtitle: 'Attiva il manifesto ideale per il tuo studio o lavoro (studente, programmatore, medico, giurista, ecc.).',
    tip: 'Il modello Sigma assumerà subito le competenze del ruolo scelto.',
    icon: Scroll,
    color: '#bc8cff',
    actionText: 'Esplora Manifesti 📜',
    onClick: (openTab) => openTab({ name: 'Manifesti' }, 'whitepapers_lib')
  },
  {
    step: '03',
    category: 'studio',
    categoryLabel: 'Struttura Dati',
    badgeText: 'ORGANIZZAZIONE',
    title: 'Naviga la Mappa degli Argomenti',
    subtitle: 'Esplora il grafo relazionale di cartelle in data/ e consulta teoria LaTeX, test Pytest e grafici D3.js.',
    tip: 'Tutti i documenti e gli script sono organizzati per materia.',
    icon: FolderTree,
    color: '#3fb950',
    actionText: 'Apri Argomenti 🗺️',
    onClick: (openTab) => openTab({ name: 'Argomenti' }, 'knowledge')
  },
  {
    step: '04',
    category: 'studio',
    categoryLabel: 'Conversazione',
    badgeText: 'INTERAZIONE',
    title: 'Collabora in AI Chat Studio',
    subtitle: 'Dialoga in 4 modalità (Ask, Plan, Execute, Complete) con supporto diretto ai file e tool MCP.',
    tip: 'Chiedi spiegazioni, crea nuovi script o pianifica compiti.',
    icon: MessageSquare,
    color: '#7c5bf0',
    actionText: 'Avvia Chat AI 💬',
    onClick: (openTab) => openTab({ name: 'AI Chat Workspace' }, 'chat')
  },
  {
    step: '05',
    category: 'studio',
    categoryLabel: 'Pianificazione',
    badgeText: 'TRACKING',
    title: 'Pianifica Task & Monitora Audit',
    subtitle: 'Definisci la roadmap di studio e verifica lo storico delle attività svolte dagli agenti.',
    tip: 'Tieni traccia dello stato di avanzamento e dei verbali.',
    icon: Activity,
    color: '#faa03c',
    actionText: 'Vedi Pianificazione 📅',
    onClick: (openTab) => openTab({ name: '📅 Pianificazione & Audit' }, 'roadmap')
  },
  {
    step: '06',
    category: 'advanced',
    categoryLabel: 'Swarm Multi-Agente',
    badgeText: 'AUTOMAZIONE',
    title: 'Lancia una Pipeline Swarm DAG',
    subtitle: 'Scomponi un obiettivo complesso in micro-task eseguiti in parallelo con self-healing automatico.',
    tip: 'Un team di agenti coopererà per scrivere teoria, codice e test.',
    icon: FlaskConical,
    color: '#00d2ff',
    actionText: 'Pipelines Lab 🔬',
    onClick: (openTab) => openTab({ name: '🔬 Pipelines Lab' }, 'research_lab')
  },
  {
    step: '07',
    category: 'advanced',
    categoryLabel: 'Addestramento',
    badgeText: 'SPECIALIZZAZIONE',
    title: 'Addestra con Training Lab & SLM',
    subtitle: 'Esegui il fine-tuning Unsloth QLoRA in locale, ottimizza con l\'Autopilota e valuta su 11 benchmark.',
    tip: 'Rendi la tua squadra AI sempre più potente sul tuo settore.',
    icon: Sparkles,
    color: '#d29922',
    actionText: 'Training Lab 🧪',
    onClick: (openTab) => openTab({ name: 'Training Lab' }, 'training_lab')
  },
  {
    step: '08',
    category: 'creative_iot',
    categoryLabel: 'Studio Grafico',
    badgeText: 'CREATIVITÀ',
    title: 'Crea Media in Creative Lab 3D/2D',
    subtitle: 'Genera immagini 8K, texture PBR per materiali, inpainting ed esegui rendering Blender 3D headless.',
    tip: 'Produci illustrazioni ad alta risoluzione e asset 3D.',
    icon: Palette,
    color: '#ff5064',
    actionText: 'Creative Lab 🎨',
    onClick: (openTab) => openTab({ name: '🎨 Creative Lab' }, 'creative_studio')

  },
  {
    step: '09',
    category: 'creative_iot',
    categoryLabel: 'Smart Home',
    badgeText: 'DOMOTICA',
    title: 'Governa la Casa con Domotica IoT',
    subtitle: 'Controlla luci, termostati, sensori ambientali e scene domotiche tramite Home Assistant MCP.',
    tip: 'L\'intelligenza artificiale interagisce con il mondo reale.',
    icon: HomeIcon,
    color: '#10b981',
    actionText: 'Pannello Domotica 🏠',
    onClick: (openTab) => openTab({ name: '🏠 Domotica & Home Assistant' }, 'domotica')
  }
];

/* ----- 9 Showcase Module Definitions (Alternating Showcase Blocks) ----- */
const MODULE_SHOWCASE_LIST = [
  {
    id: 'knowledge',
    step: 'MODULO 01',
    badge: 'STRUTTURA & GRAFO DELLA CONOSCENZA',
    icon: FolderTree,
    color: '#00d2ff',
    title: 'Mappa degli Argomenti & Moduli di Conoscenza',
    objective: 'Organizzare l\'intero corpus scientifico in alberature tematiche e moduli strutturati (data/), integrando teoria rigorosa in LaTeX, script computazionali Python, test automatici Pytest e simulazioni visive interattive.',
    features: [
      { icon: '🌐', label: 'Grafo Relazionale D3.js', desc: 'Navigazione force-directed dei nodi e delle dipendenze concettuali.' },
      { icon: '📐', label: 'Formulario & Teoria LaTeX', desc: 'Rendering in tempo reale delle formule con KaTeX ($ e $$).' },
      { icon: '⚡', label: 'Validazione Pytest', desc: 'Suite di test computazionali confinati e replicabili su disco.' },
      { icon: '📊', label: 'Asset Multimodali', desc: 'Whitepaper, schede PDF, grafici SVG e documentazione accademica.' }
    ],
    actionText: 'Esplora Mappa Argomenti 🗺️',
    tabPayload: [{ name: 'Argomenti' }, 'knowledge'],
    image: '/images/knowledge_graph_banner.jpg',
    imageCaption: '🌐 Grafo Relazionale Force-Directed e Struttura Modulare dei Dati'
  },
  {
    id: 'whitepapers_lib',
    step: 'MODULO 02',
    badge: 'IDENTITY & CONTRATTI OPERATIVI DEI RUOLI',
    icon: Scroll,
    color: '#bc8cff',
    title: 'Galleria dei Manifesti & Ruoli Specialistici',
    objective: 'Fornire al modello unificato Sigma contratti vincolanti ed identità professionali per ogni disciplina: studenti, docenti, programmatori, medici, ingegneri, avvocati e ricercatori, con sincronizzazione dal repository aperto su GitHub.',
    features: [
      { icon: '🧠', label: 'Modello Unico Sigma', desc: 'Competenze verticali caricate a runtime tramite Modelfile standard.' },
      { icon: '🎓', label: 'Studenti & Formazione', desc: 'Ruoli didattici per spiegazioni guidate e risoluzione di problemi.' },
      { icon: '💼', label: 'Discipline Professionali', desc: 'Manifesti per medici, giuristi, data scientist ed ingegneri.' },
      { icon: '🌐', label: 'Hub GitHub Sincronizzato', desc: 'Download e aggiornamento istantaneo dei manifesti della community.' }
    ],
    actionText: 'Apri Galleria Manifesti 📜',
    tabPayload: [{ name: 'Manifesti' }, 'whitepapers_lib'],
    image: '/images/manifesti_gallery_banner.jpg',
    imageCaption: '📜 Catalogo dei Manifesti Modelfile & Competenze Verticali'
  },
  {
    id: 'roadmap',
    step: 'MODULO 03',
    badge: 'ROADMAP, MONITORAGGIO & AUDIT STORICO',
    icon: Activity,
    color: '#faa03c',
    title: 'Pianificazione Strategica & Roadmap dei Task',
    objective: 'Pianificare lo studio e lo sviluppo della conoscenza, monitorare lo stato di avanzamento delle attività degli agenti in tempo reale e conservare un registro storico di audit per la conformità di ogni deliverable.',
    features: [
      { icon: '📌', label: 'Tracking di Stato', desc: 'Gestione visiva delle attività in corso, completate e in attesa.' },
      { icon: '📑', label: 'Audit & Registro Prove', desc: 'Log dettagliato con marcatura oraria di ogni esecuzione autonoma.' },
      { icon: '⏱️', label: 'Timeline & Milestone', desc: 'Cronologia interattiva per seguire l\'evoluzione dei progetti.' },
      { icon: '🎯', label: 'Prioritizzazione Dinamica', desc: 'Assegnazione rapida dei task prioritari ai diversi laboratori.' }
    ],
    actionText: 'Consulta Pianificazione 📅',
    tabPayload: [{ name: '📅 Pianificazione & Audit' }, 'roadmap'],
    image: '/images/roadmap_plan_banner.jpg',
    imageCaption: '📅 Tabellone di Pianificazione, Milestone e Audit dei Task'
  },
  {
    id: 'chat',
    step: 'MODULO 04',
    badge: 'WORKSPACE CONVERSAZIONALE MULTI-MODALE',
    icon: MessageSquare,
    color: '#7c5bf0',
    title: 'AI Chat Studio & Modalità Operative',
    objective: 'Interagire con il modello Sigma e con gli agenti specialistici attraverso 4 modalità native (Ask, Plan, Execute, Complete), con accesso diretto ai file del workspace, rendering inline di formule e codice, e invocazione di tool MCP.',
    features: [
      { icon: '🔄', label: '4 Modalità Native', desc: 'Da pura consultazione (Ask) a piena esecuzione autonoma su file (Execute).' },
      { icon: '⚡', label: 'Routing Intelligente Auto', desc: 'Selezione autonoma del ruolo e degli strumenti più indicati.' },
      { icon: '🛠️', label: 'Esecuzione Tool MCP', desc: 'Lettura/scrittura file, query SQLite, ricerche web e automazioni.' },
      { icon: '🖼️', label: 'Lightbox Multimodale', desc: 'Visualizzazione immediata di codice, immagini generate e formule.' }
    ],
    actionText: 'Entra in AI Chat Studio 💬',
    tabPayload: [{ name: 'Chat AI', path: 'chat-tab' }, 'chat'],
    image: '/images/chat_swarm_banner.jpg',
    imageCaption: '💬 Workspace Conversazionale con Manifesti e Supporto Tool MCP'
  },
  {
    id: 'research_lab',
    step: 'MODULO 05',
    badge: 'SWARM AUTONOMO & GRAFI ACICLICI DIRETTI',
    icon: FlaskConical,
    color: '#00d2ff',
    title: 'Pipelines Lab & Dynamic Swarm',
    objective: 'Scomporre automaticamente un obiettivo scientifico o ingegneristico complesso in una roadmap di micro-task strutturati in un grafo DAG, eseguiti in parallelo da agenti cooperanti con self-healing automatico dei fallimenti.',
    features: [
      { icon: '🤖', label: 'Swarm Multi-Agente', desc: 'Matematico, Programmatore, Revisore e Visualizzatore in cooperazione.' },
      { icon: '📈', label: 'Workflow DAG Paralleli', desc: 'Risoluzione ordinata delle dipendenze tra nodi computazionali.' },
      { icon: '🛡️', label: 'Ciclo di Self-Healing', desc: 'Ispezione dei test ed autoriparazione immediata del codice difettoso.' },
      { icon: '📝', label: 'Deliverable Completi', desc: 'Generazione automatica di moduli con teoria, test e grafici D3.js.' }
    ],
    actionText: 'Apri Pipelines Lab 🔬',
    tabPayload: [{ name: '🔬 Pipelines Lab' }, 'research_lab'],
    image: '/images/pipelines_lab_banner.jpg',
    imageCaption: '🔬 Orchestrazione a Grafo DAG di Agenti Paralleli e Self-Healing'
  },
  {
    id: 'training_lab',
    step: 'MODULO 06',
    badge: 'FINE-TUNING, FORGIA SLM & BENCHMARK',
    icon: Sparkles,
    color: '#d29922',
    title: 'Training Lab & Forgia di Piccoli Modelli (SLM)',
    objective: 'Specializzare ed addestrare modelli linguistici compatti in locale con Unsloth QLoRA, automatizzare la taratura degli iperparametri con l\'Autopilota ed esportare pesi quantizzati GGUF certificati su 11 benchmark ufficiali.',
    features: [
      { icon: '🚀', label: 'Unsloth QLoRA 5x Fast', desc: 'Fine-tuning locale ultra-rapido con consumo minimo di memoria VRAM.' },
      { icon: '🤖', label: 'Ciclo Autopilota AI', desc: 'Ottimizzazione autonoma di learning rate, batch size e rank LoRA.' },
      { icon: '🔨', label: 'Forgia Modelli Italiani', desc: 'Addestramento SLM da zero ed export diretto in formato GGUF Ollama.' },
      { icon: '📊', label: '11 Suite Benchmark', desc: 'Audit dei miglioramenti su MMLU, GSM8K, HumanEval, ARC e BBH.' }
    ],
    actionText: 'Entra nel Training Lab 🧪',
    tabPayload: [{ name: '🧠 Training Lab' }, 'training_lab'],
    image: '/images/training_lab_hero.jpg',
    imageCaption: '🧪 Fine-Tuning QLoRA, Autopilota e Forgia Modelli GGUF'
  },
  {
    id: 'creative_studio',
    step: 'MODULO 07',
    badge: 'CREATIVE SUITE 2D/3D & BLENDER HEADLESS',
    icon: Palette,
    color: '#ff5064',
    title: 'Creative Lab & Studio 3D / 2D',
    objective: 'Generare e modificare asset grafici di livello professionale in 8K, creare mappe PBR complete per materiali fisici, isolare elementi con segmentazione SAM/RemBG ed eseguire rendering 3D via Blender in modalità headless.',
    features: [
      { icon: '🖼️', label: 'Text-to-Image & Img2Img 8K', desc: 'Generazione fotorealistica ad altissima risoluzione con prompt visivi.' },
      { icon: '🧊', label: 'Blender Headless 3D', desc: 'Rendering di mesh, animazioni e scene tridimensionali via codice.' },
      { icon: '🪄', label: 'Inpainting & RemBG', desc: 'Rimozione sfondo trasparente PNG e segmentazione precisa con SAM.' },
      { icon: '🧱', label: 'Mappe PBR & Materiali', desc: 'Creazione di normal, roughness e height map per rendering e videogiochi.' }
    ],
    actionText: 'Apri Creative Lab 🎨',
    tabPayload: [{ name: '🎨 Creative Lab' }, 'creative_studio'],
    image: '/images/creative_lab_banner.jpg',
    imageCaption: '🎨 Generazione Grafica 8K, Texture PBR e Rendering 3D con Blender'
  },
  {
    id: 'hardware_lab',
    step: 'MODULO 08',
    badge: 'TELEMETRIA GPU, VRAM & CONTROLLO RISORSE',
    icon: Zap,
    color: '#0284c7',
    title: 'Hardware Lab & Telemetria del Cluster',
    objective: 'Monitorare in tempo reale le risorse fisiche della macchina (VRAM GPU, RAM di sistema, carico CPU, temperature e latenze), gestire configurazioni multi-GPU parallele e terminare processi orfani con rilascio istantaneo della VRAM.',
    features: [
      { icon: '📊', label: 'Telemetria Real-Time SVG', desc: 'Grafici sparkline interattivi con campionamento continuo dei nodi.' },
      { icon: '🧹', label: 'Svuotamento Rapido VRAM', desc: 'Flush immediato della memoria video GPU con salvaguardia del sistema.' },
      { icon: '🛑', label: 'Process Killer PID', desc: 'Ispezione e terminazione forzata sicura di processi orfani o bloccati.' },
      { icon: '⚙️', label: 'Tuning Multi-GPU Parallelo', desc: 'Allocazione dinamica dei pesi e bilanciamento dei thread di calcolo.' }
    ],
    actionText: 'Apri Hardware Lab ⚡',
    tabPayload: [{ name: '⚡ Hardware' }, 'hardware_lab'],
    image: '/images/hardware_cluster_lab.jpg',
    imageCaption: '⚡ Telemetria Real-Time VRAM GPU, Monitor Processi e Cluster'
  },
  {
    id: 'model_hub',
    step: 'KERNEL 08',
    badge: 'MODELLI LOCALI & STORAGE (KERNEL OPTIMIZER)',
    icon: DownloadCloud,
    color: '#ffb86c',
    title: 'Modelli Locali & Storage (Kernel Optimizer)',
    objective: 'Scaricare, ottimizzare ed eseguire modelli di intelligenza artificiale direttamente da Hugging Face all\'interno di SigmaEngine con partizionamento automatico su GPU e RAM e FlashAttention-2.',
    features: [
      { icon: '🔍', label: 'Esploratore Hugging Face', desc: 'Ricerca istantanea di modelli GGUF, MoE, Reasoning, Vision e Coding.' },
      { icon: '📥', label: 'Download Streaming con Resume', desc: 'Scaricamento in background ad altissima velocità con tracking MB/s.' },
      { icon: '⚡', label: 'Deploy Diretto in SigmaEngine', desc: 'Partizionamento automatico a livelli tra GPU RTX 5070 Ti, RTX 5060 e RAM.' },
      { icon: '🚀', label: 'FlashAttention-2 & KV FP8', desc: 'Compilazione kernel e quantizzazione dinamica per massimizzare i token/s.' }
    ],
    actionText: 'Apri Modelli Locali & Storage 📥',
    tabPayload: [{ name: '⚡ Modelli Locali & Storage' }, 'model_hub'],
    image: '/images/hardware_cluster_lab.jpg',
    imageCaption: '📥 Ricerca, Download e Ottimizzazione Hardware di Modelli Hugging Face'
  },
  {
    id: 'domotica',

    step: 'MODULO 09',
    badge: 'DOMOTICA IOT & HOME ASSISTANT INTEGRATION',
    icon: HomeIcon,
    color: '#10b981',
    title: 'Domotica & Smart Home con Home Assistant',
    objective: 'Interfacciare l\'intelligenza artificiale ai dispositivi smart e sensori della casa attraverso il server MCP di Home Assistant, per monitorare ambienti fisici, gestire clima e luci, ed eseguire automazioni intelligenti con supervisione sicura.',
    features: [
      { icon: '💡', label: 'Controllo Luci & Clima', desc: 'Regolazione istantanea di tonalità, dimmerazione e termostati smart.' },
      { icon: '🌡️', label: 'Sensori Ambientali Real-Time', desc: 'Monitoraggio di temperatura, umidità, consumi elettrici e presenze.' },
      { icon: '🎬', label: 'Scene & Automazioni AI', desc: 'Creazione ed attivazione contestuale di routine domotiche avanzate.' },
      { icon: '🔒', label: 'Sicurezza MCP Governata', desc: 'Protocollo I/O protetto con approvazione esplicita per le azioni fisiche.' }
    ],
    actionText: 'Apri Pannello Domotica 🏠',
    tabPayload: [{ name: '🏠 Domotica' }, 'domotica'],
    image: '/images/domotica_smart_hub.jpg',
    imageCaption: '🏠 Gestione Dispositivi Smart, Clima e Scene via Home Assistant MCP'
  }
];

// ==============================================================================
// WelcomeDashboard — Modern Home with Force-Directed Topic Graph + CRUD
// ==============================================================================

/* ----- 5 Core Domain Color Mapping ----- */
const DOMAIN_COLORS = {
  'Analisi':     { bg: '#00d2ff', label: 'Analisi' },
  'Algebra':     { bg: '#a78bfa', label: 'Algebra' },
  'Fisica':      { bg: '#ff5064', label: 'Fisica' },
  'Informatica': { bg: '#3fb950', label: 'Informatica' },
  'Generale':    { bg: '#faa03c', label: 'Generale' },
};

/* ----- Domain Picker (modern pill UX) ----- */
function DomainPicker({ value, onChange }) {
  return (
    <div className="wg-domain-picker">
      {Object.entries(DOMAIN_COLORS).map(([key, { bg }]) => (
        <button
          key={key}
          type="button"
          className={`wg-domain-pill ${value === key ? 'active' : ''}`}
          style={{
            '--domain-color': bg,
            '--domain-color-15': bg + '26',
            '--domain-color-08': bg + '14',
          }}
          onClick={() => onChange(key)}
        >
          <span className="wg-domain-dot" style={{ background: bg }} />
          {key}
        </button>
      ))}
    </div>
  );
}

/* ----- Parent Selector (styled dropdown) ----- */
function ParentSelector({ value, onChange, allTopics, excludeId }) {
  // Compute available parents (exclude self and descendants to prevent cycles)
  const getDescendantIds = (tid, topics) => {
    const ids = new Set();
    const find = (pid) => {
      for (const t of topics) {
        if (t.id !== pid && t.parent_id === pid) {
          ids.add(t.id);
          find(t.id);
        }
      }
    };
    find(tid);
    return ids;
  };

  const excluded = new Set();
  if (excludeId) {
    excluded.add(excludeId);
    getDescendantIds(excludeId, allTopics || []).forEach(id => excluded.add(id));
  }

  const available = (allTopics || []).filter(t => !excluded.has(t.id));

  return (
    <div className="wg-field">
      <label>Argomento Padre (opzionale)</label>
      <select
        className="wg-parent-select"
        value={value || ''}
        onChange={e => onChange(e.target.value || null)}
      >
        <option value="">— Nessuno —</option>
        {available.map(t => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
      <span className="wg-field-sub">Collega questo argomento come figlio di un altro</span>
    </div>
  );
}

/* ----- Inline Rename / Edit Modal ----- */
function TopicEditModal({ topic, onSave, onCancel, allTopics }) {
  const [name, setName] = useState(topic?.name || '');
  const [description, setDescription] = useState(topic?.description || '');
  const [domain, setDomain] = useState(topic?.domain || 'Generale');
  const [parentId, setParentId] = useState(topic?.parent_id || null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!name.trim()) return setError('Il nome è obbligatorio');
    setSaving(true);
    setError('');
    try {
      const body = {
        topic_id: topic.id,
        name: name.trim(),
        description,
        domain,
        parent_id: parentId
      };
      const r = await fetch('/api/update_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const d = await r.json();
      if (d.success) {
        onSave({ ...topic, name: name.trim(), description, domain, parent_id: parentId });
      } else {
        setError(d.error || 'Errore durante il salvataggio');
      }
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setSaving(false);
    }
  };

  if (!topic) return null;

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Modifica Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <div className="wg-field">
            <label>Nome</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="es. Topologia non archimedea" autoFocus />
          </div>
          <div className="wg-field">
            <label>Descrizione</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Descrizione dell'argomento…" />
          </div>
          <div className="wg-field">
            <label>Dominio</label>
            <DomainPicker value={domain} onChange={setDomain} />
          </div>
          <ParentSelector
            value={parentId}
            onChange={setParentId}
            allTopics={allTopics}
            excludeId={topic.id}
          />
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Salvataggio…' : 'Salva'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Create Topic Modal ----- */
function CreateTopicModal({ onCreated, onCancel, allTopics }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState('Generale');
  const [parentId, setParentId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    if (!name.trim()) return setError('Il nome è obbligatorio');
    const id = name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/(^_|_$)/g, '');
    if (!id) return setError('ID non valido (usa solo lettere, numeri e underscore)');
    setSaving(true);
    setError('');
    try {
      const r = await fetch('/api/create_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name: name.trim(), description, domain, parent_id: parentId })
      });
      const d = await r.json();
      if (d.success) {
        onCreated({
          id,
          name: name.trim(),
          description,
          domain,
          parent_id: parentId,
          manifesto_ref: '',
          modules: []
        });
      } else {
        setError(d.error || 'Errore durante la creazione');
      }
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Nuovo Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <div className="wg-field">
            <label>Nome</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="es. Topologia non archimedea" autoFocus />
          </div>
          <div className="wg-field">
            <label>Descrizione</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Descrizione dell'argomento…" />
          </div>
          <div className="wg-field">
            <label>Dominio</label>
            <DomainPicker value={domain} onChange={setDomain} />
          </div>
          <ParentSelector
            value={parentId}
            onChange={setParentId}
            allTopics={allTopics}
            excludeId={null}
          />
          <div className="wg-field-hint">
            L'ID verrà generato automaticamente dal nome: <code>{name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/(^_|_$)/g, '') || '…'}</code>
          </div>
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-primary" onClick={handleCreate} disabled={saving}>
            {saving ? 'Creazione…' : 'Crea Argomento'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Delete Confirmation ----- */
function DeleteConfirmModal({ topic, onConfirm, onCancel }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async () => {
    setDeleting(true);
    setError('');
    try {
      const r = await fetch('/api/delete_topic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_id: topic.id })
      });
      const d = await r.json();
      if (d.success) onConfirm(topic.id);
      else setError(d.error || 'Errore durante l\'eliminazione');
    } catch (e) {
      setError('Errore di rete');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="wg-modal-overlay" onClick={onCancel}>
      <div className="wg-modal wg-modal-danger" onClick={e => e.stopPropagation()}>
        <div className="wg-modal-head">
          <h3>Elimina Argomento</h3>
          <button className="wg-modal-close" onClick={onCancel}>×</button>
        </div>
        <div className="wg-modal-body">
          {error && <div className="wg-modal-error">{error}</div>}
          <p>Sei sicuro di voler eliminare <strong>"{topic.name}"</strong>?</p>
          <p className="wg-modal-warn">Tutti i moduli e file associati verranno cancellati definitivamente.</p>
        </div>
        <div className="wg-modal-foot">
          <button className="wg-btn wg-btn-secondary" onClick={onCancel}>Annulla</button>
          <button className="wg-btn wg-btn-danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Eliminazione…' : 'Elimina definitivamente'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ----- Force-Directed Graph Component ----- */
function TopicGraph({ topics, selectedTopic, onSelectTopic }) {
  const svgRef = useRef(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const animRef = useRef(null);
  const dims = { w: 540, h: 440 };

  const domainColors = {
    'Analisi': '#00d2ff', 'Algebra': '#a78bfa', 'Fisica': '#ff5064',
    'Informatica': '#3fb950', 'Generale': '#faa03c',
  };
  const getDomainColor = (d) => domainColors[d] || '#9494a5';

  useEffect(() => {
    if (!topics || !topics.length) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Build graph nodes
    const initialNodes = topics.map((t, i) => {
      const angle = (i / topics.length) * 2 * Math.PI;
      const r = 120;
      return {
        id: t.id,
        label: t.name || t.id,
        domain: t.domain || 'Generale',
        description: t.description || '',
        count: t.modules?.length || 1,
        x: dims.w / 2 + Math.cos(angle) * r,
        y: dims.h / 2 + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
        radius: 24 + Math.min(16, (t.children?.length || 0) * 4),
      };
    });

    const initialEdges = [];
    for (const t of topics) {
      if (t.parent_id) {
        const exists = topics.find(p => p.id === t.parent_id);
        if (exists) {
          initialEdges.push({ source: t.parent_id, target: t.id });
        }
      }
    }

    setNodes(initialNodes);
    setEdges(initialEdges);

    let currentNodes = initialNodes.map(n => ({ ...n }));
    let iter = 0;
    const maxIter = 100;

    const tick = () => {
      if (iter >= maxIter) return;
      iter++;

      const centerForce = 0.012;
      const repulsion = 1200;
      const springLength = 100;
      const springStrength = 0.008;

      for (let a of currentNodes) {
        a.vx += (dims.w / 2 - a.x) * centerForce;
        a.vy += (dims.h / 2 - a.y) * centerForce;
      }

      for (let i = 0; i < currentNodes.length; i++) {
        const a = currentNodes[i];
        for (let j = i + 1; j < currentNodes.length; j++) {
          const b = currentNodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 20);
          const force = repulsion / (dist * dist);
          a.vx += (dx / dist) * force;
          b.vx -= (dx / dist) * force;
          a.vy += (dy / dist) * force;
          b.vy -= (dy / dist) * force;
        }
      }

      for (let edge of initialEdges) {
        const src = currentNodes.find(n => n.id === edge.source);
        const tgt = currentNodes.find(n => n.id === edge.target);
        if (src && tgt) {
          const dx = tgt.x - src.x;
          const dy = tgt.y - src.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = (dist - springLength) * springStrength;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          src.vx += fx;
          src.vy += fy;
          tgt.vx -= fx;
          tgt.vy -= fy;
        }
      }

      for (let n of currentNodes) {
        n.vx *= 0.82;
        n.vy *= 0.82;
        n.x += n.vx;
        n.y += n.vy;
        n.x = Math.max(n.radius + 15, Math.min(dims.w - n.radius - 15, n.x));
        n.y = Math.max(n.radius + 15, Math.min(dims.h - n.radius - 15, n.y));
      }

      setNodes([...currentNodes]);
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [topics]);

  if (!topics || !topics.length) {
    return <div className="wg-empty" style={{ padding: '40px', textAlign: 'center', color: '#8b8fa3' }}>Caricamento argomenti…</div>;
  }

  return (
    <div className="wg-graph-wrapper">
      <svg ref={svgRef} viewBox={`0 0 ${dims.w} ${dims.h}`} className="wg-svg">
        {/* Edge lines */}
        {edges.map((edge, i) => {
          const src = nodes.find(n => n.id === edge.source);
          const tgt = nodes.find(n => n.id === edge.target);
          if (!src || !tgt) return null;
          return (
            <line
              key={`edge-${edge.source}-${edge.target}`}
              className="topic-edge"
              x1={src.x} y1={src.y}
              x2={tgt.x} y2={tgt.y}
              stroke="rgba(0, 210, 255, 0.3)"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
          );
        })}

        {/* Node groups */}
        {nodes.map((n) => {
          const isSelected = selectedTopic?.id === n.id;
          const color = getDomainColor(n.domain);
          return (
            <g
              key={n.id}
              className="topic-node-group"
              onClick={() => {
                const topic = topics.find(t => t.id === n.id);
                if (topic) onSelectTopic(topic);
              }}
              style={{ cursor: 'pointer' }}
            >
              <circle
                className="topic-node"
                cx={n.x}
                cy={n.y}
                r={n.radius}
                fill={color}
                fillOpacity={isSelected ? 0.35 : 0.18}
                stroke={color}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeOpacity={isSelected ? 1 : 0.6}
              />
              <text
                className="topic-label"
                x={n.x}
                y={n.y + 4}
                textAnchor="middle"
                dominantBaseline="central"
                fill={isSelected ? '#fff' : '#e2e8f0'}
                fontSize={Math.max(9, Math.min(12, n.radius * 0.42))}
                fontWeight={isSelected ? '700' : '600'}
                pointerEvents="none"
                style={{ userSelect: 'none' }}
              >
                {n.label.length > 14 ? n.label.slice(0, 13) + '…' : n.label}
              </text>
              {isSelected && (
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.radius + 6}
                  fill="none"
                  stroke={color}
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                  opacity="0.6"
                >
                  <animate attributeName="r" values={`${n.radius + 6};${n.radius + 12};${n.radius + 6}`} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
            </g>
          );
        })}
      </svg>

      <div className="wg-legend">
        {Object.entries(domainColors).map(([domain, color]) => (
          <span key={domain} className="wg-legend-item">
            <span className="wg-legend-dot" style={{ background: color }} />
            {domain}
          </span>
        ))}
        <span className="wg-legend-item" style={{ marginLeft: 'auto', opacity: 0.5, fontSize: 11 }}>
          linee = relazioni padre-figlio
        </span>
      </div>
    </div>
  );
}

/* ----- Topic Detail Panel (with Edit/Delete actions) ----- */
function TopicDetail({ topic, topics, openTab, onEdit, onDelete }) {
  if (!topic) {
    return (
      <div className="wg-detail wg-detail-empty">
        <div className="wg-detail-empty-icon">☝️</div>
        <h4>Seleziona un Nodo</h4>
        <p>Clicca su un argomento nel grafo per visualizzarne i dettagli e i moduli correlati.</p>
      </div>
    );
  }

  const domainColors = {
    'Analisi': '#00d2ff', 'Algebra': '#a78bfa', 'Fisica': '#ff5064',
    'Informatica': '#3fb950', 'Generale': '#faa03c',
  };
  const color = domainColors[topic.domain] || '#9494a5';
  const temaModules = topic.modules || [];

  // Find parent topic
  const parentTopic = topic.parent_id ? (topics || []).find(t => t.id === topic.parent_id) : null;

  // Find child topics
  const childTopics = (topics || []).filter(t => t.parent_id === topic.id);

  return (
    <div className="wg-detail">
      <div className="wg-detail-head">
        <span className="wg-detail-domain" style={{ background: `${color}18`, color, border: `1px solid ${color}44` }}>
          {topic.domain || 'Generale'}
        </span>
        <span className="wg-detail-badge">{temaModules.length} moduli</span>
      </div>
      <h3 className="wg-detail-title">{topic.name}</h3>
      <p className="wg-detail-desc">{topic.description}</p>

      {/* Parent-child relationships */}
      {parentTopic && (
        <div className="wg-detail-rel wg-detail-rel-parent">
          <span className="wg-detail-rel-label">Argomento Padre</span>
          <span className="wg-detail-rel-value">{parentTopic.name}</span>
        </div>
      )}
      {childTopics.length > 0 && (
        <div className="wg-detail-rel wg-detail-rel-children">
          <span className="wg-detail-rel-label">Argomenti Figli ({childTopics.length})</span>
          <div className="wg-detail-rel-list">
            {childTopics.map(ct => (
              <span key={ct.id} className="wg-detail-rel-tag">{ct.name}</span>
            ))}
          </div>
        </div>
      )}

      <div className="wg-detail-actions">
        <button className="wg-btn-sm wg-btn-sm-edit" onClick={() => onEdit(topic)} title="Modifica argomento">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Modifica
        </button>
        <button className="wg-btn-sm wg-btn-sm-delete" onClick={() => onDelete(topic)} title="Elimina argomento">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          Elimina
        </button>
      </div>

      {temaModules.length > 0 && (
        <div className="wg-detail-modules">
          <div className="wg-detail-subtitle">Moduli Associati</div>
          {temaModules.map(mod => {
            const totalFiles = (mod.teoria?.length || 0) + (mod.test?.length || 0) + (mod.viz?.length || 0) + (mod.docs?.length || 0) + (mod.whitepapers?.length || 0);
            return (
              <div key={mod.number} className="wg-detail-module" onClick={() => openTab(mod, 'module')}>
                <span className="wg-detail-mod-num" style={{ background: `${color}15`, color, border: `1px solid ${color}33` }}>
                  MOD {mod.number}
                </span>
                <div className="wg-detail-mod-info">
                  <span className="wg-detail-mod-name">{mod.name}</span>
                  <span className="wg-detail-mod-files">{totalFiles} file</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ----- Quick Feature Card ----- */
function QuickFeature({ icon, title, desc, color }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(14,16,22,0.9), rgba(20,22,28,0.9))',
      border: `1px solid ${color}22`,
      borderRadius: '12px',
      padding: '20px',
      transition: 'all 0.2s',
      cursor: 'default'
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = `${color}44`; e.currentTarget.style.transform = 'translateY(-2px)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = `${color}22`; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${color}14`, border: `1px solid ${color}22`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.3rem', flexShrink: 0
        }}>
          {icon}
        </div>
        <div>
          <h4 style={{ margin: '0 0 6px 0', fontSize: '0.82rem', fontWeight: 600, color: color }}>
            {title}
          </h4>
          <p style={{ margin: 0, fontSize: '0.68rem', color: '#5a5e72', lineHeight: 1.6 }}>
            {desc}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ----- Quick Link button style ----- */
const quickLinkStyle = (color) => ({
  padding: '10px 22px',
  borderRadius: '10px',
  fontSize: '0.72rem',
  fontWeight: 600,
  cursor: 'pointer',
  border: `1px solid ${color}33`,
  background: `${color}0d`,
  color: color,
  fontFamily: 'inherit',
  transition: 'all 0.15s',
  display: 'flex',
  alignItems: 'center',
  gap: '8px'
});

/* ----- WelcomeScreen Export ----- */
export default function WelcomeDashboard({ modules, openTab }) {
  const { theme, toggleTheme } = useApp();
  const isLight = theme === 'light';
  const titleColor = isLight ? '#000000' : '#ffffff';
  const subtitleColor = isLight ? '#000000' : '#8b8fa3';
  const cardBg = isLight ? '#ffffff' : '#121622';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 6px 20px rgba(190, 160, 110, 0.15)' : '0 12px 40px rgba(0,0,0,0.5)';
  const innerCardBg = isLight ? '#fbf8f2' : '#181e2b';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.06)';
  const innerCardText = isLight ? '#000000' : '#cbd5e1';

  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);

  // Modal states
  const [showCreate, setShowCreate] = useState(false);
  const [editTopic, setEditTopic] = useState(null);
  const [deleteTopic, setDeleteTopic] = useState(null);
  const [activeStepCategory, setActiveStepCategory] = useState('all');

  const fetchTopics = useCallback(() => {
    fetch('/api/topics')
      .then(r => r.json())
      .then(d => { if (d.topics) setTopics(d.topics); })
      .catch(() => {});
  }, []);

  const [manifestiCount, setManifestiCount] = useState(12);

  useEffect(() => {
    fetchTopics();
    fetch('/api/list_manifesti')
      .then(r => r.json())
      .then(d => {
        if (d.files && Array.isArray(d.files)) {
          setManifestiCount(d.files.length);
        } else if (d.manifesti && Array.isArray(d.manifesti)) {
          setManifestiCount(d.manifesti.length);
        }
      })
      .catch(() => {});
  }, [fetchTopics]);

  const handleCreated = (newTopic) => {
    setTopics(prev => [...prev, newTopic]);
    setShowCreate(false);
  };

  const handleEdited = (updatedTopic) => {
    setTopics(prev => prev.map(t => t.id === updatedTopic.id ? { ...t, ...updatedTopic } : t));
    setSelectedTopic(prev => prev?.id === updatedTopic.id ? { ...prev, ...updatedTopic } : prev);
    setEditTopic(null);
  };

  const handleDeleted = (topicId) => {
    // Also orphan children
    setTopics(prev => prev.map(t => t.parent_id === topicId ? { ...t, parent_id: null } : t).filter(t => t.id !== topicId));
    if (selectedTopic?.id === topicId) setSelectedTopic(null);
    setDeleteTopic(null);
  };

  // Categorize files by extension across modules prop and topics API
  const rootTopics = topics.filter(t => !t.parent_id);
  const countRootTopics = rootTopics.length > 0 ? rootTopics.length : 5;
  const countModules = modules?.length > 0 ? modules.length : (topics.length > 0 ? topics.length : 5);

  const allFilePaths = new Set();

  // Collect files from modules prop
  (modules || []).forEach(m => {
    ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
      if (Array.isArray(m[cat])) {
        m[cat].forEach(f => {
          const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
          if (pathStr) allFilePaths.add(pathStr);
        });
      }
    });
  });

  // Collect files from topics API
  (topics || []).forEach(t => {
    if (Array.isArray(t.files)) {
      t.files.forEach(f => {
        const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
        if (pathStr) allFilePaths.add(pathStr);
      });
    }
    ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media'].forEach(cat => {
      if (Array.isArray(t[cat])) {
        t[cat].forEach(f => {
          const pathStr = typeof f === 'string' ? f : (f.path || f.name || '');
          if (pathStr) allFilePaths.add(pathStr);
        });
      }
    });
  });

  let countDocs = 0;
  let countScripts = 0;
  let countVizMedia = 0;

  allFilePaths.forEach(pathStr => {
    const lower = pathStr.toLowerCase();
    if (lower.endsWith('.md') || lower.endsWith('.txt') || lower.endsWith('.pdf') || lower.endsWith('.doc') || lower.endsWith('.docx')) {
      countDocs++;
    } else if (lower.endsWith('.py') || lower.endsWith('.ipynb') || lower.endsWith('.js') || lower.endsWith('.ts') || lower.endsWith('.sh') || lower.endsWith('.bat')) {
      countScripts++;
    } else {
      countVizMedia++;
    }
  });

  return (
    <div className="wg-container" style={{ position: 'relative' }}>
      {/* Animated Translucent Cyber Space Background Canvas */}
      <TechSpaceCanvas isLight={theme === 'light'} />

      {/* Hero Visual Banner with Standardized Theme System */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        borderRadius: 0,
        overflow: 'hidden',
        padding: '24px 32px',
        minHeight: '110px',
        borderBottom: theme === 'light' ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: theme === 'light' ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: theme === 'light'
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/hero_banner.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/hero_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: 0,
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '720px', display: 'flex', alignItems: 'center', gap: '18px' }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              overflow: 'hidden',
              border: theme === 'light' ? '2px solid #ea580c' : '2px solid #00d2ff',
              boxShadow: theme === 'light' ? '0 0 20px rgba(234, 88, 12, 0.4)' : '0 0 20px rgba(0, 210, 255, 0.5), inset 0 0 10px rgba(0, 210, 255, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#0a0d14',
              flexShrink: 0
            }}>
              <img 
                src="/images/sigma_logo_harmonic_flow.jpg" 
                alt="Sigma Logo" 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={(e) => { e.target.src = '/sigma_logo.jpg'; }}
              />
            </div>
            <div>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 12px',
                borderRadius: '14px',
                background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
                border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
                color: isLight ? '#9a3412' : '#00d2ff',
                fontSize: '0.68rem',
                fontWeight: 800,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                marginBottom: '6px'
              }}>
                <span>🧬</span> Σ SIGMA STUDIO v8.0 — KERNEL COGNITIVO
              </div>

              <h1 style={{
                fontSize: '1.4rem',
                fontWeight: 800,
                color: isLight ? '#000000' : '#ffffff',
                margin: '0 0 6px 0',
                letterSpacing: '-0.3px',
                textShadow: 'none'
              }}>
                Il Sistema Operativo AI-Native per la Conoscenza, la Ricerca e le <span style={{
                  color: isLight ? '#c2410c' : '#00d2ff',
                  fontWeight: 800
                }}>Professioni</span>
              </h1>

              <p style={{
                fontSize: '0.82rem',
                color: isLight ? '#000000' : '#cbd5e0',
                lineHeight: 1.45,
                margin: 0,
                fontWeight: isLight ? 600 : 400
              }}>
                Sigma Studio orchestra il modello unificato Sigma, i Manifesti Modelfile per ogni disciplina, il protocollo MCP come bus I/O di sistema e la validazione computazionale autonoma in un unico ambiente integrato.
              </p>
            </div>
          </div>

          {/* README Action Buttons & Theme Toggle on the Right */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button
              onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
              style={{
                padding: '10px 16px',
                borderRadius: '12px',
                background: isLight ? '#ffffff' : '#181b28',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 210, 255, 0.5)',
                color: isLight ? '#000000' : '#00d2ff',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                opacity: 1,
                boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 16px rgba(0,0,0,0.4)',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🇮🇹 README (IT)
            </button>

            <button
              onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
              style={{
                padding: '10px 16px',
                borderRadius: '12px',
                background: isLight ? '#ffffff' : '#181b28',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(167, 139, 250, 0.5)',
                color: isLight ? '#000000' : '#a78bfa',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                opacity: 1,
                boxShadow: isLight ? '0 4px 14px rgba(190, 160, 110, 0.1)' : '0 4px 16px rgba(0,0,0,0.4)',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🌐 Docs (EN)
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 12px 12px 12px', display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
      {/* Redesigned High-Tech Metrics Bar */}
      <div className="wg-metrics" style={{ marginTop: '18px', marginBottom: '12px' }}>
        <div className="wg-metric" style={{ borderTop: '3px solid #00d2ff', background: cardBg }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>🧠</span>
            <span className="wg-metric-value" style={{ color: isLight ? '#0284c7' : '#00d2ff' }}>{countRootTopics}</span>
          </div>
          <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Argomenti Fondamentali</span>
        </div>
        <div className="wg-metric" style={{ borderTop: '3px solid #a78bfa', background: cardBg }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>📚</span>
            <span className="wg-metric-value" style={{ color: isLight ? '#7c3aed' : '#a78bfa' }}>{countModules}</span>
          </div>
          <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Moduli di Conoscenza</span>
        </div>
        <div className="wg-metric" style={{ borderTop: '3px solid #3fb950', background: cardBg }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>📄</span>
            <span className="wg-metric-value" style={{ color: isLight ? '#16a34a' : '#3fb950' }}>{countDocs}</span>
          </div>
          <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Teoria & Whitepaper</span>
        </div>
        <div className="wg-metric" style={{ borderTop: '3px solid #ff5064', background: cardBg }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>⚡</span>
            <span className="wg-metric-value" style={{ color: isLight ? '#dc2626' : '#ff5064' }}>{countScripts}</span>
          </div>
          <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Script & Test Pytest</span>
        </div>
        <div className="wg-metric" style={{ borderTop: '3px solid #bc8cff', background: cardBg }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
            <span style={{ fontSize: '1.1rem' }}>📜</span>
            <span className="wg-metric-value" style={{ color: isLight ? '#9333ea' : '#bc8cff' }}>{manifestiCount}</span>
          </div>
          <span className="wg-metric-label" style={{ color: isLight ? '#000000' : '#8b8fa3' }}>Manifesti dei Ruoli</span>
        </div>
      </div>

      {/* Visual Kernel Cognitivo Showcase Overview */}
      <div className="wg-showcase-card" style={{
        margin: '4px 0 16px 0',
        padding: '28px',
        borderRadius: '20px',
        background: cardBg,
        border: isLight ? '1px solid rgba(124, 91, 240, 0.35)' : '1px solid rgba(124, 91, 240, 0.3)',
        boxShadow: cardShadow,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '24px',
        alignItems: 'center'
      }}>
        <div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '4px 12px', borderRadius: '12px',
            background: 'rgba(124, 91, 240, 0.15)', color: isLight ? '#6d28d9' : '#7c5bf0',
            fontSize: '0.72rem', fontWeight: 800, marginBottom: '12px'
          }}>
            <span>🧠</span> ARCHITETTURA DI SISTEMA
          </div>
          <h2 style={{ margin: '0 0 12px 0', fontSize: '1.4rem', color: titleColor, fontWeight: 800 }}>
            Sigma Studio come Kernel Cognitivo Eseguibile
          </h2>
          <p style={{ fontSize: '0.86rem', color: subtitleColor, lineHeight: 1.65, margin: '0 0 20px 0', fontWeight: isLight ? 500 : 400 }}>
            Come un sistema operativo orchestra processi, memoria e periferiche hardware, Sigma Studio trasforma i Modelli Linguistici (LLM) 
            in unità di computazione (CPU), regolamentati da contratti vincolanti (Manifesti Modelfile), con bus di I/O (Server MCP) e memoria confinata (Sandbox protetta).
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#0284c7' : '#00d2ff' }}>⚡ Modello Sigma = CPU</div>
              <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Unità di elaborazione unificata in locale su Ollama o via Cloud.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#16a34a' : '#3fb950' }}>📜 Manifesti = Ruoli & Regole</div>
              <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Modelfile vincolanti per ogni professione e materia di studio.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#6d28d9' : '#7c5bf0' }}>🔌 12 Server MCP = Bus I/O</div>
              <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Accesso a filesystem, memoria, Domotica, browser e strumenti.</div>
            </div>
            <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontWeight: 800, fontSize: '0.82rem', color: isLight ? '#d97706' : '#ffb86c' }}>🔒 Sandbox & Test = Bounds</div>
              <div style={{ fontSize: '0.74rem', color: innerCardText, marginTop: '3px', fontWeight: isLight ? 500 : 400 }}>Validazione con Pytest, formule KaTeX e grafici D3.js.</div>
            </div>
          </div>
        </div>

        <div style={{
          position: 'relative',
          borderRadius: '16px',
          overflow: 'hidden',
          border: '1px solid rgba(124, 91, 240, 0.3)',
          boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
          minHeight: '280px',
          maxHeight: '320px'
        }}>
          <img
            src="/images/kernel_graphic.jpg"
            alt="Kernel Cognitivo Architecture"
            style={{ width: '100%', height: '320px', maxHeight: '320px', objectFit: 'cover', display: 'block' }}
          />
          <div style={{
            position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
            padding: '12px 16px',
            background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
            fontSize: '0.75rem', color: '#ffffff', fontWeight: 600
          }}>
            🌐 Schema Architetturale del Kernel di Orchestrazione AI
          </div>
        </div>
      </div>

      {/* Section Header: I Moduli Separati di Sigma Studio */}
      <div style={{ margin: '20px 0 10px 0' }}>
        <h2 style={{ fontSize: '1.35rem', color: titleColor, fontWeight: 800, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🏛️</span> I Laboratori & Moduli Operativi di Sigma Studio
        </h2>
        <p style={{ fontSize: '0.86rem', color: subtitleColor, margin: '0 0 16px 0', fontWeight: isLight ? 500 : 400 }}>
          Ciascuna scheda del workspace costituisce un ambiente dedicato e modulare. Esplora gli obiettivi e le capacità di ogni laboratorio:
        </p>
      </div>

      {/* Alternating Showcase Cards for All 9 Modules */}
      {MODULE_SHOWCASE_LIST.map((mod, index) => {
        const isImageRight = index % 2 === 0;
        const IconComp = mod.icon;

        const textContent = (
          <div key="text" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '4px 12px', borderRadius: '12px',
                background: `${mod.color}18`,
                color: isLight ? '#000000' : mod.color,
                border: `1px solid ${mod.color}45`,
                fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.5px'
              }}>
                <IconComp size={14} style={{ color: mod.color }} />
                <span>{mod.badge}</span>
              </div>
              <span style={{
                fontSize: '0.68rem', fontWeight: 800,
                color: isLight ? '#000000' : '#8b8fa3',
                background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                padding: '4px 10px', borderRadius: '12px',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.08)'
              }}>
                {mod.step}
              </span>
            </div>

            <h2 style={{ margin: '0 0 12px 0', fontSize: '1.35rem', color: titleColor, fontWeight: 800, lineHeight: 1.3 }}>
              {mod.title}
            </h2>

            <div style={{
              padding: '14px 16px',
              borderRadius: '12px',
              background: isLight ? '#fbf8f2' : `${mod.color}12`,
              border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : `1px solid ${mod.color}30`,
              marginBottom: '16px'
            }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 800, color: isLight ? '#c2410c' : mod.color, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>
                🎯 Obiettivo del Modulo
              </div>
              <p style={{ margin: 0, fontSize: '0.84rem', color: isLight ? '#000000' : '#e2e8f0', lineHeight: 1.55, fontWeight: isLight ? 600 : 500 }}>
                {mod.objective}
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '20px' }}>
              {mod.features.map((feat, fIdx) => (
                <div key={fIdx} style={{
                  padding: '10px 12px',
                  borderRadius: '10px',
                  background: innerCardBg,
                  border: innerCardBorder
                }}>
                  <div style={{ fontWeight: 800, fontSize: '0.8rem', color: isLight ? '#9a3412' : mod.color, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{feat.icon}</span>
                    <span>{feat.label}</span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: innerCardText, marginTop: '3px', lineHeight: 1.45, fontWeight: isLight ? 500 : 400 }}>
                    {feat.desc}
                  </div>
                </div>
              ))}
            </div>

            <div>
              <button
                onClick={() => openTab(...mod.tabPayload)}
                style={{
                  padding: '10px 20px',
                  borderRadius: '10px',
                  background: isLight
                    ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)'
                    : `linear-gradient(135deg, ${mod.color}, ${mod.color}cc)`,
                  border: 'none',
                  color: '#fff',
                  fontWeight: 800,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                  boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.25)' : `0 6px 20px ${mod.color}35`,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'all 0.2s ease'
                }}
              >
                {mod.actionText}
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        );

        const imageContent = (
          <div key="image" style={{
            position: 'relative',
            borderRadius: '16px',
            overflow: 'hidden',
            border: isLight ? `1px solid ${mod.color}45` : `1px solid ${mod.color}35`,
            boxShadow: isLight ? `0 12px 30px ${mod.color}18` : '0 14px 36px rgba(0,0,0,0.5)',
            minHeight: '280px',
            maxHeight: '340px',
            background: '#0a0d14'
          }}>
            <img
              src={mod.image}
              alt={mod.title}
              style={{
                width: '100%',
                height: '340px',
                maxHeight: '340px',
                objectFit: 'cover',
                display: 'block'
              }}
              onError={(e) => { e.target.src = '/images/hero_banner.jpg'; }}
            />
            <div style={{
              position: 'absolute', bottom: 0, inset: 'auto 0 0 0',
              padding: '12px 16px',
              background: 'linear-gradient(to top, rgba(14,16,22,0.95), transparent)',
              fontSize: '0.74rem', color: '#ffffff', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '6px'
            }}>
              {mod.imageCaption}
            </div>
          </div>
        );

        return (
          <div
            key={mod.id}
            className="wg-showcase-card"
            style={{
              margin: '8px 0',
              padding: '28px',
              borderRadius: '20px',
              background: cardBg,
              border: isLight ? `1px solid rgba(190, 160, 110, 0.4)` : `1px solid ${mod.color}25`,
              boxShadow: cardShadow,
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '28px',
              alignItems: 'center'
            }}
          >
            {isImageRight ? [textContent, imageContent] : [imageContent, textContent]}
          </div>
        );
      })}

      {/* Primi Passi nella Piattaforma (Modern Friendly Interactive Journey) */}
      <div style={{ margin: '16px 0 8px 0' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '16px'
        }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '4px 12px', borderRadius: '12px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
              color: isLight ? '#c2410c' : '#00d2ff',
              fontSize: '0.72rem', fontWeight: 800, marginBottom: '8px'
            }}>
              <Compass size={14} />
              <span>PERCORSO DI AVVIO GUIDATO</span>
            </div>
            <h2 style={{ fontSize: '1.4rem', color: titleColor, fontWeight: 800, margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🚀</span> Primi Passi nella Piattaforma
            </h2>
            <p style={{ fontSize: '0.86rem', color: subtitleColor, margin: 0, fontWeight: isLight ? 500 : 400 }}>
              Segui questo itinerario in tappe o seleziona una categoria per iniziare subito ad utilizzare Sigma Studio:
            </p>
          </div>

          {/* Interactive Category Filter Pills */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap',
            background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
            padding: '4px',
            borderRadius: '14px',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.06)'
          }}>
            {[
              { id: 'all', label: '✨ Tutti (9)' },
              { id: 'setup', label: '⚙️ 1. Setup & Ruoli' },
              { id: 'studio', label: '📚 2. Studio & Chat' },
              { id: 'advanced', label: '🤖 3. Swarm & SLM' },
              { id: 'creative_iot', label: '🎨 4. Media & IoT' }
            ].map(cat => {
              const active = activeStepCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveStepCategory(cat.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '10px',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    background: active 
                      ? (isLight ? '#ea580c' : '#00d2ff') 
                      : 'transparent',
                    color: active ? '#ffffff' : (isLight ? '#000000' : subtitleColor),
                    boxShadow: active ? (isLight ? '0 3px 10px rgba(234, 88, 12, 0.3)' : '0 4px 12px rgba(0, 210, 255, 0.35)') : 'none'
                  }}
                >
                  {cat.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Dynamic Card Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px'
        }}>
          {PRIMI_PASSI_CARDS
            .filter(card => activeStepCategory === 'all' || card.category === activeStepCategory)
            .map(card => {
              const IconComponent = card.icon;
              return (
                <div
                  key={card.step}
                  onClick={() => card.onClick(openTab)}
                  className="primi-passi-card"
                  style={{
                    padding: '24px',
                    borderRadius: '20px',
                    background: cardBg,
                    border: isLight ? `1px solid rgba(190, 160, 110, 0.4)` : `1px solid ${card.color}35`,
                    boxShadow: cardShadow,
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '16px',
                    transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                >
                  <div>
                    {/* Card Top Row */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '14px',
                        background: `${card.color}18`,
                        border: `1px solid ${card.color}45`,
                        color: isLight ? '#9a3412' : card.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: `0 0 16px ${card.color}25`
                      }}>
                        <IconComponent size={24} style={{ color: card.color }} />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '0.66rem',
                          fontWeight: 800,
                          color: isLight ? '#000000' : '#a0a6bc',
                          background: isLight ? '#f4efe6' : 'rgba(255,255,255,0.06)',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : 'none'
                        }}>
                          {card.categoryLabel}
                        </span>
                        <span style={{
                          fontSize: '0.68rem',
                          fontWeight: 800,
                          color: isLight ? '#9a3412' : card.color,
                          background: `${card.color}18`,
                          border: `1px solid ${card.color}35`,
                          padding: '3px 10px',
                          borderRadius: '20px',
                          letterSpacing: '0.5px'
                        }}>
                          PASSO {card.step}
                        </span>
                      </div>
                    </div>

                    {/* Card Title & Subtitle */}
                    <h3 style={{ margin: '0 0 8px 0', fontSize: '1.05rem', fontWeight: 800, color: titleColor, lineHeight: 1.35 }}>
                      {card.title}
                    </h3>
                    <p style={{ margin: '0 0 14px 0', fontSize: '0.82rem', color: subtitleColor, lineHeight: 1.55, fontWeight: isLight ? 500 : 400 }}>
                      {card.subtitle}
                    </p>

                    {/* Friendly Tip Box */}
                    <div style={{
                      padding: '10px 12px',
                      borderRadius: '10px',
                      background: isLight ? '#fbf8f2' : `${card.color}10`,
                      border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : `1px solid ${card.color}25`,
                      fontSize: '0.74rem',
                      color: isLight ? '#000000' : '#cbd5e1',
                      lineHeight: 1.45,
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '8px',
                      fontWeight: isLight ? 500 : 400
                    }}>
                      <span style={{ fontSize: '0.85rem' }}>💡</span>
                      <span>{card.tip}</span>
                    </div>
                  </div>

                  {/* Card Bottom CTA */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingTop: '14px',
                    borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)'
                  }}>
                    <span style={{
                      fontSize: '0.78rem',
                      fontWeight: 800,
                      color: isLight ? '#c2410c' : card.color,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      {card.actionText}
                    </span>
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      background: isLight ? 'rgba(234, 88, 12, 0.12)' : `${card.color}18`,
                      color: isLight ? '#c2410c' : card.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <ArrowRight size={14} />
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        marginTop: '8px',
        padding: '24px 0 12px 0',
        borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        color: isLight ? '#000000' : '#6b7080',
        fontSize: '0.78rem',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: isLight ? '#c2410c' : '#00d2ff',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🇮🇹 README_IT.md
          </button>
          <span>•</span>
          <button
            onClick={() => openTab({ path: 'README.md', filename: 'README.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: isLight ? '#15803d' : '#3fb950',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🇬🇧 README.md
          </button>
          <span>•</span>
          <button
            onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
            style={{
              background: 'none',
              border: 'none',
              color: isLight ? '#7c3aed' : '#a78bfa',
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: 0
            }}
          >
            🏛️ Specifica Architetturale
          </button>
        </div>

        <div style={{ color: isLight ? '#000000' : '#8b8fa3', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>⚡ Creato da <strong style={{ color: isLight ? '#000000' : '#ffffff' }}>Diego Saitta</strong> — 🧬 <strong style={{ color: isLight ? '#000000' : '#ffffff' }}>Sigma Studio</strong></span>
        </div>
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateTopicModal
          onCreated={handleCreated}
          onCancel={() => setShowCreate(false)}
          allTopics={topics}
        />
      )}
      {editTopic && (
        <TopicEditModal
          topic={editTopic}
          onSave={handleEdited}
          onCancel={() => setEditTopic(null)}
          allTopics={topics}
        />
      )}
      {deleteTopic && (
        <DeleteConfirmModal
          topic={deleteTopic}
          onConfirm={handleDeleted}
          onCancel={() => setDeleteTopic(null)}
        />
      )}
      </div>
    </div>
  );
}