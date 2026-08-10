import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ArrowRight, BookOpen, FileText, FileSignature, Layers, FileDown, 
  Sparkles, ScrollText, Eye, Plus, Cpu, Play, CheckCircle, AlertCircle, Loader,
  Info, Code, GitBranch, Wand2, Upload, Brain, Target, Award, Zap, RefreshCw, User,
  ChevronLeft, ChevronRight, Check
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

// Helper to calculate manifesto particularities and domain metadata
const getManifestoDetails = (mf) => {
  const name = ((mf && (mf.filename || mf.name)) || '').toLowerCase();
  if (name.includes('architect')) {
    return {
      role: 'System Architect & Chief Agent',
      badge: '🏗️ SYSTEM ARCHITECT',
      badgeColor: '#bc8cff',
      badgeBg: 'rgba(188, 140, 255, 0.15)',
      badgeBorder: 'rgba(188, 140, 255, 0.35)',
      icon: Cpu,
      desc: 'Orchestratore principale dello Swarm: scompone compiti complessi, assegna ruoli agli agenti specializzati e supervisiona il consenso.',
      features: [
        'System Prompt di Orchestrazione Persistente',
        'Routing Condizionale e Gestione Sub-Task DAG',
        'Temperatura Bassa (0.2) per Massima Rigorosità',
        'Integrazione Completa con Bus MCP Hub'
      ],
      temp: '0.2 (Stabile)',
      context: '16384 Token',
      output: 'Architettura & Task Breakdown'
    };
  } else if (name.includes('matematico') || name.includes('math')) {
    return {
      role: 'Mathematical Reasoning & Formal Proofs',
      badge: '∑ MATH SPECIALIST',
      badgeColor: '#00d2ff',
      badgeBg: 'rgba(0, 210, 255, 0.15)',
      badgeBorder: 'rgba(0, 210, 255, 0.35)',
      icon: Brain,
      desc: 'Specializzato in dimostrazioni formali, sintassi KaTeX, equazioni differenziali e modellazione algebrica avanzata.',
      features: [
        'Formattazione Rigorosa LaTeX / KaTeX',
        'Derivazione Passo-Passo dei Teoremi',
        'Validazione di Script SymPy e NumPy',
        'Temperatura 0.1 per Precisione Numerica'
      ],
      temp: '0.1 (Matematico)',
      context: '8192 Token',
      output: 'Dimostrazioni & Formule'
    };
  } else if (name.includes('programmatore') || name.includes('code') || name.includes('developer')) {
    return {
      role: 'Full-Stack Developer & Python Engineer',
      badge: '⚙️ CODE DEVELOPER',
      badgeColor: '#3fb950',
      badgeBg: 'rgba(63, 185, 80, 0.15)',
      badgeBorder: 'rgba(63, 185, 80, 0.35)',
      icon: Code,
      desc: 'Sviluppa script Python, componenti React e microservizi in ambiente sandbox con verifica automatica dei test.',
      features: [
        'Generazione di Codice Pulito, Documentato e Tipizzato',
        'Esecuzione di Script di Verifica pytest & Node.js',
        'Refactoring e Diagnosi Errori da Stack Trace',
        'Integrazione MCP Git & Local Storage'
      ],
      temp: '0.15 (Codice Piatto)',
      context: '16384 Token',
      output: 'Script Eseguibili & Unit Test'
    };
  } else if (name.includes('ricercatore') || name.includes('research')) {
    return {
      role: 'Multidisciplinary Research & Synthesis',
      badge: '🔬 RESEARCH LEAD',
      badgeColor: '#d29922',
      badgeBg: 'rgba(210, 153, 34, 0.15)',
      badgeBorder: 'rgba(210, 153, 34, 0.35)',
      icon: Wand2,
      desc: 'Esplora letteratura scientifica, sintetizza fonti e costruisce mappe concettuali gerarchiche per il Knowledge Graph.',
      features: [
        'Analisi Critica di Paper Scientifici e PDF',
        'Generazione Mappe Concettuali D3 per Mappa Argomenti',
        'Estrazione Concetti Chiave & Metadati Formattati',
        'Temperatura 0.35 per Sintesi Creativa Rigorosa'
      ],
      temp: '0.35 (Bilanciato)',
      context: '32768 Token',
      output: 'Report & Mappe Concettuali'
    };
  }
  return {
    role: 'Agentic Intelligence Directive',
    badge: '📜 AI MANIFESTO',
    badgeColor: '#a78bfa',
    badgeBg: 'rgba(167, 139, 250, 0.15)',
    badgeBorder: 'rgba(167, 139, 250, 0.35)',
    icon: ScrollText,
    desc: 'Manifesto agentico personalizzato per l\'orchestrazione del modello e l\'istruzione dei prompt di sistema.',
    features: [
      'Identità e Ruolo Personalizzabile',
      'Configurazione Parametri Ollama Modelfile',
      'Assegnazione Avatar Grafico Personalizzato',
      'Compatibilità Multi-Modello LLM/SLM'
    ],
    temp: '0.25 (Standard)',
    context: '8192 Token',
    output: 'Testo Strutturato'
  };
};

/* ----- Animated Cyber-Space Background Canvas Component ----- */
const TechSpaceCanvas = ({ isLight }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    let width = (canvas.width = canvas.parentElement ? canvas.parentElement.offsetWidth : window.innerWidth);
    let height = (canvas.height = canvas.parentElement ? canvas.parentElement.offsetHeight : window.innerHeight);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.offsetWidth;
      height = canvas.height = canvas.parentElement.offsetHeight;
    };

    window.addEventListener('resize', handleResize);

    const particleCount = Math.min(Math.floor((width * height) / 10000), 75);
    const particles = [];
    const colors = isLight 
      ? ['#0078c8', '#7c5bf0', '#2563eb', '#0284c7'] 
      : ['#00d2ff', '#bc8cff', '#3b82f6', '#00f0ff'];

    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2 + 1,
        color: colors[Math.floor(Math.random() * colors.length)],
        pulse: Math.random() * Math.PI * 2
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = isLight ? 'rgba(0, 120, 200, 0.04)' : 'rgba(0, 210, 255, 0.04)';
      ctx.lineWidth = 1;
      const gridSize = 50;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 150) {
            const alpha = (1 - dist / 150) * (isLight ? 0.15 : 0.22);
            ctx.strokeStyle = isLight ? `rgba(0, 120, 200, ${alpha})` : `rgba(0, 210, 255, ${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += 0.03;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        const currentRadius = p.radius + Math.sin(p.pulse) * 0.5;

        ctx.fillStyle = p.color;
        ctx.shadowBlur = isLight ? 4 : 10;
        ctx.shadowColor = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.5, currentRadius), 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isLight]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
        opacity: isLight ? 0.5 : 0.75
      }}
    />
  );
};

export default function ManifestiGallery({ modules, manifesti, openTab, setFileModalContext, setIsFileModalOpen, fetchManifesti }) {
  const { theme } = useApp();
  const [activeSubTab, setActiveSubTab] = useState('standard'); // 'standard' | 'trained'
  const [manifestoText, setManifestoText] = useState('');
  const [manifestoLoading, setManifestoLoading] = useState(true);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [creatingModel, setCreatingModel] = useState(false);
  const [createResult, setCreateResult] = useState(null);
  const [selectedManifesto, setSelectedManifesto] = useState('');
  const [modelName, setModelName] = useState('sigma-agent');
  const [baseModel, setBaseModel] = useState('llama3.2');

  // Trained models state
  const [trainedModels, setTrainedModels] = useState([]);
  const [trainingJobs, setTrainingJobs] = useState([]);
  const [loadingTrained, setLoadingTrained] = useState(false);

  const fileInputRefs = useRef({});

  // Fetch trained models from Training Lab
  const fetchTrainedData = useCallback(async () => {
    setLoadingTrained(true);
    try {
      const [resM, resJ] = await Promise.all([
        fetch('/api/training/models'),
        fetch('/api/training/jobs')
      ]);
      const dataM = await resM.json();
      const dataJ = await resJ.json();
      if (dataM.success) setTrainedModels(dataM.models || []);
      if (dataJ.success) setTrainingJobs(dataJ.jobs || []);
    } catch (e) {
      console.error("Failed to load trained models:", e);
    } finally {
      setLoadingTrained(false);
    }
  }, []);

  useEffect(() => {
    fetchTrainedData();
  }, [fetchTrainedData]);

  // Load the first available manifesto on mount (or the default fallback)
  useEffect(() => {
    const defaultPath = manifesti.length > 0
      ? manifesti[0].path
      : 'manifesti/sigma_architect.md';
    setSelectedManifesto(defaultPath);
    fetch(`/api/get_file?path=${encodeURIComponent(defaultPath)}`)
      .then(r => r.json())
      .then(d => {
        if (d.success) setManifestoText(d.content);
        setManifestoLoading(false);
      })
      .catch(() => setManifestoLoading(false));
  }, [manifesti]);

  const fetchOllamaModels = async () => {
    setModelsLoading(true);
    try {
      const res = await fetch('/api/ollama_models');
      const data = await res.json();
      setOllamaModels(data.models || []);
    } catch (e) {
      console.error('Failed to fetch Ollama models:', e);
    }
    setModelsLoading(false);
  };

  useEffect(() => { fetchOllamaModels(); }, []);

  const handleUpdateImage = async (path, image) => {
    try {
      const res = await fetch('/api/manifesti/update_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, image })
      });
      const data = await res.json();
      if (data.success && fetchManifesti) {
        fetchManifesti();
      }
    } catch (e) {
      console.error("Failed to update manifesto image:", e);
    }
  };

  const handleFileUpload = async (e, path) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', path);

    try {
      const res = await fetch('/api/agents/upload_image', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        if (fetchManifesti) fetchManifesti();
      } else {
        alert(data.error || "Errore nel caricamento dell'immagine");
      }
    } catch (err) {
      console.error("Upload image error:", err);
      alert("Errore di rete durante l'upload dell'immagine");
    }
  };

  const triggerFileInput = (e, path) => {
    e.stopPropagation();
    fileInputRefs.current[path]?.click();
  };

  const handleNewManifesto = () => {
    setFileModalContext({ folder: 'manifesti', type: 'manifesti' });
    setIsFileModalOpen(true);
  };

  const handleSelectAsChatModel = (modelName) => {
    try {
      localStorage.setItem('sigma_selected_model', modelName);
      window.dispatchEvent(new CustomEvent('sigma_model_selected', { detail: { model: modelName } }));
      window.dispatchEvent(new CustomEvent('sigma_toast', {
        detail: { message: `⚡ Modello '${modelName}' impostato come attivo per la Chat AI!`, type: 'success' }
      }));
    } catch (e) {
      console.error("Failed to select chat model:", e);
    }
  };

  const handleCreateModel = async () => {
    if (!modelName.trim()) return;
    setCreatingModel(true);
    setCreateResult(null);
    
    try {
      const res = await fetch(`/api/get_file?path=${encodeURIComponent(selectedManifesto)}`);
      const data = await res.json();
      if (!data.success) {
        setCreateResult({ success: false, message: 'Impossibile leggere il manifesto' });
        return;
      }

      let modelfileContent = data.content;
      modelfileContent = modelfileContent.replace(/^FROM\s+.+$/m, `FROM ${baseModel}`);

      const createRes = await fetch('/api/create_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: modelName, modelfile: modelfileContent })
      });
      const result = await createRes.json();
      setCreateResult({ 
        success: result.success, 
        message: result.message || result.error || 'Errore sconosciuto' 
      });
      if (result.success) {
        fetchOllamaModels();
      }
    } catch (e) {
      setCreateResult({ success: false, message: e.message });
    }
    setCreatingModel(false);
  };

  return (
    <div className="mg-tab" style={{ position: 'relative' }}>
      {/* Animated Cyber Space Background Canvas */}
      <TechSpaceCanvas isLight={theme === 'light'} />
      <style>{`
        .mg-tab { padding: 0; height: 100%; overflow-y: auto; display: flex; flex-direction: column; }
        .mg-section { margin-bottom: 25px; }
        .mg-section-title { font-size: 0.85rem; font-weight: 600; color: #e2e4eb; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
        .mg-section-desc { font-size: 0.62rem; color: #5a5e72; margin-bottom: 10px; }
        .mg-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
        .mg-card { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 16px; background: #11131b; border: 1px solid #1e2030; border-radius: 12px; cursor: pointer; transition: all 0.15s; position: relative; }
        .mg-card:hover { border-color: #2a2d3e; transform: translateY(-1px); }
        .mg-card-header { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 100%; }
        .mg-card-icon { width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 1.5rem; border: 2px solid #1e2030; transition: border-color 0.15s; }
        .mg-card:hover .mg-card-icon { border-color: #bc8cff; }
        .mg-card-name { font-size: 0.72rem; font-weight: 600; color: #e2e4eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
        .mg-card-meta { font-size: 0.55rem; color: #5a5e72; display: flex; align-items: center; justify-content: center; gap: 4px; width: 100%; margin-top: 4px; }
        .mg-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 8px; font-size: 0.65rem; cursor: pointer; border: 1px solid rgba(188,140,255,0.2); background: rgba(188,140,255,0.08); color: #bc8cff; font-family: inherit; transition: all 0.15s; }
        .mg-btn:hover { background: rgba(188,140,255,0.15); }
        .mg-btn-primary { display: inline-flex; align-items: center; gap: 8px; padding: 8px 18px; border-radius: 8px; font-size: 0.7rem; font-weight: 600; cursor: pointer; border: 1px solid rgba(0,210,255,0.3); background: rgba(0,210,255,0.1); color: #00d2ff; font-family: inherit; transition: all 0.15s; }
        .mg-btn-primary:hover { background: rgba(0,210,255,0.2); }
        .mg-btn-create-model { display: inline-flex; align-items: center; gap: 8px; padding: 8px 20px; border-radius: 8px; font-size: 0.7rem; font-weight: 600; cursor: pointer; border: 1px solid rgba(63,185,80,0.3); background: rgba(63,185,80,0.1); color: #3fb950; font-family: inherit; transition: all 0.15s; }
        .mg-btn-create-model:hover { background: rgba(63,185,80,0.2); }
        .mg-btn-create-model:disabled { opacity: 0.5; cursor: not-allowed; }
        .mg-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .mg-hero { background: linear-gradient(135deg, rgba(188,140,255,0.06) 0%, rgba(0,210,255,0.03) 100%); border: 1px solid rgba(188,140,255,0.12); border-radius: 12px; padding: 20px; }
        .mg-hero-badge { display: inline-flex; align-items: center; gap: 5px; font-size: 0.5rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 3px 10px; border-radius: 20px; background: rgba(188,140,255,0.12); color: #bc8cff; margin-bottom: 10px; }
        .mg-hero-title { font-size: 1.2rem; font-weight: 700; color: #e2e4eb; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
        .mg-hero-version { font-size: 0.55rem; background: rgba(0,210,255,0.1); color: #00d2ff; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
        .mg-hero-sub { font-size: 0.68rem; color: #8b8fa3; margin-bottom: 16px; line-height: 1.5; }
        .mg-guide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; margin-bottom: 16px; }
        .mg-guide-card { background: rgba(14,16,22,0.6); border: 1px solid rgba(188,140,255,0.08); border-radius: 8px; padding: 14px; }
        .mg-guide-card-title { display: flex; align-items: center; gap: 6px; font-size: 0.75rem; font-weight: 600; color: #e2e4eb; margin-bottom: 8px; }
        .mg-guide-card p { font-size: 0.62rem; color: #8b8fa3; line-height: 1.5; margin: 0; }
        .mg-lab { background: #11131b; border: 1px solid #1e2030; border-radius: 10px; padding: 16px; }
        .mg-lab-title { font-size: 0.85rem; font-weight: 600; color: #e2e4eb; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
        .mg-lab-row { display: flex; gap: 12px; margin-bottom: 12px; }
        .mg-lab-col { flex: 1; }
        .mg-lab label { font-size: 0.6rem; color: #8b8fa3; display: block; margin-bottom: 3px; font-weight: 500; }
        .mg-lab input, .mg-lab select { width: 100%; padding: 6px 10px; border-radius: 6px; font-size: 0.7rem; border: 1px solid #1e2030; background: #0e1016; color: #e2e4eb; font-family: inherit; outline: none; }
        .mg-lab input:focus, .mg-lab select:focus { border-color: #bc8cff; }
        .mg-result { padding: 8px 12px; border-radius: 6px; font-size: 0.65rem; margin-top: 10px; display: flex; align-items: center; gap: 6px; }
        .mg-result.success { background: rgba(63,185,80,0.1); border: 1px solid rgba(63,185,80,0.2); color: #3fb950; }
        .mg-result.error { background: rgba(255,85,85,0.1); border: 1px solid rgba(255,85,85,0.2); color: #ff5555; }
        .mg-models-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 6px; margin-top: 10px; }
        .mg-model-chip { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #0e1016; border: 1px solid #1e2030; border-radius: 6px; font-size: 0.6rem; color: #8b8fa3; }
        .mg-model-chip .dot { width: 5px; height: 5px; border-radius: 50%; background: #3fb950; flex-shrink: 0; }
        .mg-howto { margin-top: 8px; padding: 14px; background: rgba(14,16,22,0.8); border: 1px solid rgba(210,153,34,0.12); border-radius: 10px; }
        .mg-howto-title { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; font-weight: 600; color: #d29922; margin: 0 0 10px 0; }
        .mg-howto-steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
        .mg-step { display: flex; gap: 8px; align-items: flex-start; }
        .mg-step-num { width: 22px; height: 22px; border-radius: 50%; background: rgba(210,153,34,0.12); color: #d29922; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; font-weight: 700; flex-shrink: 0; }
        .mg-step p { font-size: 0.62rem; color: #8b8fa3; line-height: 1.5; margin: 0; }
        .mg-code-block { margin-top: 10px; padding: 8px 12px; background: #0e1016; border-radius: 6px; font-size: 0.58rem; font-family: 'JetBrains Mono', monospace; color: #bc8cff; line-height: 1.6; }
        .upload-icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 4px; background: rgba(124,91,240,0.1); color: #a78bfa; border: 1px solid rgba(124,91,240,0.2); cursor: pointer; transition: all 0.15s; }
        .upload-icon-btn:hover { background: rgba(124,91,240,0.2); color: #ffffff; }
      `}</style>

      {/* Hero Visual Banner matching Domotica Header Style */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '20px 32px 18px 32px',
        minHeight: '100px',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: 'linear-gradient(to right, rgba(8, 10, 16, 0.98) 45%, rgba(8, 10, 16, 0.5) 100%), url("/images/manifesti_gallery_banner.jpg")',
        backgroundSize: '360px auto',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <ScrollText size={14} /> AI MANIFESTOS & DIRECTIVES CATALOG
            </div>
            <h1 style={{ margin: '0 0 4px 0', fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              📜 Manifesti & Direttive di Sistema
            </h1>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#a0aec0', lineHeight: 1.4 }}>
              Identità agentiche, Modelfile Ollama e Agenti Addestrati con la suite Training Lab.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="mg-btn" onClick={handleNewManifesto} style={{ padding: '10px 18px', borderRadius: '12px', background: 'rgba(0,210,255,0.15)', border: '1px solid rgba(0,210,255,0.35)', color: '#00d2ff', fontWeight: 800, fontSize: '0.82rem' }}>
              <Plus size={15} /> Nuovo Manifesto
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>

      {/* Sub-Tab Switcher */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '10px' }}>
        <button
          onClick={() => setActiveSubTab('standard')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', borderRadius: '8px',
            fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
            background: activeSubTab === 'standard' ? 'rgba(188, 140, 255, 0.15)' : 'rgba(255,255,255,0.03)',
            border: activeSubTab === 'standard' ? '1px solid rgba(188, 140, 255, 0.4)' : '1px solid rgba(255,255,255,0.08)',
            color: activeSubTab === 'standard' ? '#bc8cff' : '#8b8fa3',
            transition: 'all 0.2s ease'
          }}
        >
          <FileText size={15} />
          <span>📄 Manifesti Standard ({manifesti.length})</span>
        </button>
        <button
          onClick={() => setActiveSubTab('trained')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', borderRadius: '8px',
            fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
            background: activeSubTab === 'trained' ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255,255,255,0.03)',
            border: activeSubTab === 'trained' ? '1px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(255,255,255,0.08)',
            color: activeSubTab === 'trained' ? '#00d2ff' : '#8b8fa3',
            transition: 'all 0.2s ease'
          }}
        >
          <Brain size={15} />
          <span>🤖 Agenti Addestrati (Training Lab) ({trainedModels.length})</span>
        </button>
      </div>

      {activeSubTab === 'standard' && (
        <>
          {/* === Hero Section ========================================== */}
          <div className="mg-hero mg-section">
            <div className="mg-hero-badge">
              <Sparkles size={12} />
              Modalità Agentica per Ruoli
            </div>
            <div className="mg-hero-title">
              Σ-SIGMA Manifesti degli Agenti
              <span className="mg-hero-version">v6.2</span>
            </div>
            <p className="mg-hero-sub">
              I manifesti degli agenti permettono di definire l'identità, il dominio, le regole comportamentali 
              e i parametri dedicati per ciascun ruolo AI del team di ricerca Sigma Studio. 
              Questo approccio consente di specializzare i singoli membri e di massimizzarne l'efficacia 
              nella scomposizione, esecuzione e verifica dei complessi compiti scientifici.
            </p>

            <div className="mg-guide-grid">
              <div className="mg-guide-card">
                <div className="mg-guide-card-title">
                  <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(188,140,255,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
                    <ScrollText size={12} style={{color:'#bc8cff'}} />
                  </div>
                  System Prompt Persistente
                </div>
                <p>Il manifesto definisce il comportamento e le regole comportamentali <strong style={{color:'#bc8cff'}}>permanentemente</strong>, offrendo una linea guida stabile per i compiti e l'output dell'agente.</p>
              </div>
              <div className="mg-guide-card">
                <div className="mg-guide-card-title">
                  <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(0,210,255,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
                    <GitBranch size={12} style={{color:'#00d2ff'}} />
                  </div>
                  Specializzazione per Ambiti
                </div>
                <p>Ogni dominio di ricerca dispone di un manifesto dedicato. L'agente matematico segue logiche formali in LaTeX, mentre lo sviluppatore predilige codice documentato.</p>
              </div>
              <div className="mg-guide-card">
                <div className="mg-guide-card-title">
                  <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(63,185,80,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
                    <Wand2 size={12} style={{color:'#3fb950'}} />
                  </div>
                  Parametri Ottimizzati
                </div>
                <p>Configura <strong style={{color:'#3fb950'}}>temperature</strong>, penalità e <strong style={{color:'#3fb950'}}>finestre di contesto</strong> una volta sola. L'agente risponde sempre con il livello ideale di creatività e memoria.</p>
              </div>
            </div>

            <div className="mg-howto">
              <h4 className="mg-howto-title">
                <Code size={16} />
                La creazione di un Manifesto in 5 passi
              </h4>
              <div className="mg-howto-steps">
                <div className="mg-step">
                  <div className="mg-step-num">1</div>
                  <p><strong style={{color:'#e2e4eb'}}>Definisci il Ruolo</strong> — Identifica l'identità dell'agente e la sua area d'azione.</p>
                </div>
                <div className="mg-step">
                  <div className="mg-step-num">2</div>
                  <p><strong style={{color:'#e2e4eb'}}>Scrivi le Istruzioni</strong> — Formula regole ferree, vincoli e il formato di output richiesto.</p>
                </div>
                <div className="mg-step">
                  <div className="mg-step-num">3</div>
                  <p><strong style={{color:'#e2e4eb'}}>Ottimizza i Parametri</strong> — Configura temperature, finestre di contesto e penalità.</p>
                </div>
                <div className="mg-step">
                  <div className="mg-step-num">4</div>
                  <p><strong style={{color:'#e2e4eb'}}>Assegna l'Avatar</strong> — Carica dal tuo PC un'immagine da associare al manifesto dell'agente.</p>
                </div>
                <div className="mg-step">
                  <div className="mg-step-num" style={{background:'rgba(63,185,80,0.12)', color:'#3fb950'}}>5</div>
                  <p><strong style={{color:'#3fb950'}}>Compila il Modello</strong> — Invia il Modelfile a Ollama che lo compila, rendendo l'agente pronto per la chat.</p>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              <button className="mg-btn-primary" onClick={() => {
                const path = manifesti.length > 0 ? manifesti[0].path : 'manifesti/sigma_architect.md';
                const name = manifesti.length > 0 ? manifesti[0].filename : 'sigma_architect.md';
                openTab({ name, path }, 'manifesti');
              }}>
                <Eye size={14} />
                Leggi il Manifesto Principale
              </button>
              <button className="mg-btn" onClick={handleNewManifesto}>
                <FileSignature size={14} />
                Nuovo Manifesto
              </button>
            </div>
          </div>

          {/* === MANIFESTI COLLECTION ================================== */}
          <div className="mg-section">
            <div className="mg-toolbar">
              <div>
                <div className="mg-section-title">
                  <Layers size={16} />
                  Collezione Manifesti Agenti
                </div>
                <div className="mg-section-desc">
                  {manifesti.length} manifesti degli agenti disponibili nella cartella manifesti/
                </div>
              </div>
              <button className="mg-btn" onClick={handleNewManifesto}>
                <Plus size={12} />
                Nuovo
              </button>
            </div>
            <div className="mg-grid">
              {manifesti.map((mf, i) => (
                <div key={i} className="mg-card" onClick={() => openTab(mf, 'manifesti')}>
                  <div className="mg-card-header">
                    <div className="mg-card-icon" style={{overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0e1016'}}>
                      {mf.image ? (
                        <img src={mf.image} alt={mf.name} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
                      ) : (
                        <ScrollText size={22} style={{color: '#bc8cff'}} />
                      )}
                    </div>
                    <span className="mg-card-name" title={mf.name}>{mf.name}</span>
                  </div>
                  <div className="mg-card-meta" onClick={(e) => e.stopPropagation()}>
                    <span style={{marginRight: 'auto', color: '#5a5e72'}}>Avatar:</span>
                    <button 
                      className="upload-icon-btn" 
                      onClick={(e) => triggerFileInput(e, mf.path)}
                      title="Carica immagine da PC"
                      style={{marginRight: '4px'}}
                    >
                      <Upload size={10} />
                    </button>
                    <input 
                      type="file" 
                      ref={el => fileInputRefs.current[mf.path] = el}
                      onChange={(e) => handleFileUpload(e, mf.path)}
                      accept="image/*"
                      style={{display: 'none'}}
                    />
                    <select 
                      value={mf.image || '/images/default.png'} 
                      onChange={(e) => handleUpdateImage(mf.path, e.target.value)}
                      style={{fontSize: '0.55rem', background: '#0e1016', border: '1px solid #1e2030', color: '#e2e4eb', borderRadius: '4px', padding: '2px 4px', cursor: 'pointer', outline: 'none', maxWidth: '85px'}}
                    >
                      <option value="/images/default.png">🤖 Default</option>
                      <option value="/images/agente0.png">🏗️ Architect</option>
                      <option value="/images/matematicoAi.png">∑ Math</option>
                      <option value="/images/programmatoreAi.png">⚙️ Code</option>
                    </select>
                  </div>
                </div>
              ))}
              {manifesti.length === 0 && (
                <div className="mg-empty" style={{gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '30px', color: '#5a5e72', fontSize: '0.7rem'}}>
                  <Layers size={36} />
                  <p>Nessun manifesto trovato</p>
                  <button className="mg-btn" onClick={handleNewManifesto}>
                    <FileSignature size={14} />
                    Crea il primo Manifesto
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* === OLLAMA MODEL LAB ====================================== */}
          <div className="mg-section mg-lab">
            <div className="mg-lab-title"><Cpu size={18} /> Ollama Model Lab — Compila un Modello Locale</div>
            <div className="mg-lab-row">
              <div className="mg-lab-col">
                <label>Manifesto base</label>
                <select value={selectedManifesto} onChange={e => setSelectedManifesto(e.target.value)}>
                  {manifesti.length === 0 && (
                    <option value="manifesti/sigma_architect.md">sigma_architect.md (default)</option>
                  )}
                  {manifesti.map((mf, i) => (
                    <option key={i} value={mf.path}>{mf.filename}</option>
                  ))}
                </select>
              </div>
              <div className="mg-lab-col">
                <label>Modello base Ollama</label>
                <select value={baseModel} onChange={e => setBaseModel(e.target.value)}>
                  <option value="">— Seleziona un modello —</option>
                  {ollamaModels.map((m, i) => (
                    <option key={i} value={m.name}>{m.name}</option>
                  ))}
                </select>
              </div>
              <div className="mg-lab-col">
                <label>Nome del nuovo modello</label>
                <input value={modelName} onChange={e => setModelName(e.target.value)} placeholder="es. sigma-agent" />
              </div>
            </div>
            <button className="mg-btn-create-model" onClick={handleCreateModel} disabled={creatingModel || !modelName.trim()}>
              {creatingModel ? <><Loader size={14} /> Creazione...</> : <><Play size={14} /> Compila Modello su Ollama</>}
            </button>
            {createResult && (
              <div className={`mg-result ${createResult.success ? 'success' : 'error'}`}>
                {createResult.success ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                {createResult.message}
              </div>
            )}
          </div>

          {/* === Ollama Models Installed =============================== */}
          <div className="mg-section mg-lab">
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'8px'}}>
              <div className="mg-lab-title" style={{margin:0}}><Cpu size={14} /> Modelli Ollama installati localmente</div>
              <button className="mg-btn" onClick={fetchOllamaModels} style={{fontSize:'0.55rem',padding:'3px 8px'}}>
                <ArrowRight size={10} /> Aggiorna
              </button>
            </div>
            {modelsLoading ? (
              <div style={{fontSize:'0.65rem',color:'#5a5e72',padding:'8px'}}>Caricamento...</div>
            ) : ollamaModels.length === 0 ? (
              <div style={{fontSize:'0.65rem',color:'#5a5e72',padding:'8px'}}>
                Nessun modello locale trovato.
              </div>
            ) : (
              <div className="mg-models-grid">
                {ollamaModels.map((m, i) => (
                  <div key={i} className="mg-model-chip">
                    <span className="dot" />
                    <span style={{fontWeight:600}}>{m.name}</span>
                    <span style={{marginLeft:'auto',opacity:0.5,fontSize:'0.5rem'}}>
                      {m.size ? `${(m.size / 1e9).toFixed(1)}GB` : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* === SUB TAB: AGENTI ADDESTRATI (TRAINING LAB) ================= */}
      {activeSubTab === 'trained' && (
        <div className="mg-section">
          <div className="mg-toolbar" style={{ marginBottom: '16px' }}>
            <div>
              <div className="mg-section-title" style={{ fontSize: '0.95rem' }}>
                <Brain size={18} style={{ color: '#00d2ff' }} />
                Agenti e Modelli Addestrati nel Training Lab
              </div>
              <div className="mg-section-desc">
                Modelli personalizzati, adapter LoRA, checkpoint Forgia SLM ed Autopilota registrati localmente
              </div>
            </div>
            <button className="mg-btn-primary" onClick={fetchTrainedData}>
              <RefreshCw size={13} className={loadingTrained ? 'spin' : ''} />
              Aggiorna Catalogo
            </button>
          </div>

          {loadingTrained ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#8b8fa3' }}>
              <Loader size={24} className="spin" />
              <p style={{ marginTop: '8px', fontSize: '0.8rem' }}>Caricamento agenti addestrati...</p>
            </div>
          ) : trainedModels.length === 0 ? (
            <div className="mg-hero" style={{ textAlign: 'center', padding: '40px' }}>
              <Brain size={40} style={{ color: '#00d2ff', opacity: 0.6, marginBottom: '12px' }} />
              <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', color: '#fff' }}>Nessun Agente Addestrato trovato</h3>
              <p style={{ fontSize: '0.78rem', color: '#8b8fa3', maxWidth: '500px', margin: '0 auto 16px auto' }}>
                Non sono ancora presenti modelli personalizzati completati nel Training Lab. Avvia un job con Autopilota o Forgia SLM per addestrare il tuo primo agente!
              </p>
              <button 
                className="mg-btn-primary" 
                onClick={() => openTab({ name: '🧠 Training Lab' }, 'training_lab')}
              >
                <Zap size={14} /> Vai al Training Lab
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
              {trainedModels.map((m, idx) => {
                const acc = m.accuracy_pct || m.accuracy;
                const sources = m.sources || ['job'];
                return (
                  <div
                    key={m.id || idx}
                    style={{
                      background: 'linear-gradient(135deg, rgba(17, 19, 27, 0.95), rgba(10, 12, 20, 0.9))',
                      border: '1px solid rgba(0, 210, 255, 0.2)',
                      borderRadius: '14px',
                      padding: '18px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '12px',
                      position: 'relative',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '42px', height: '42px', borderRadius: '12px',
                          background: 'radial-gradient(circle at 30% 30%, rgba(0, 242, 254, 0.2), rgba(0, 210, 255, 0.05))',
                          border: '1px solid rgba(0, 242, 254, 0.3)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#00f2fe'
                        }}>
                          <Brain size={22} />
                        </div>
                        <div>
                          <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#fff', wordBreak: 'break-all' }}>
                            {m.display_name || m.name}
                          </h4>
                          <span style={{ fontSize: '0.65rem', color: '#8b8fa3', fontFamily: 'JetBrains Mono, monospace' }}>
                            {m.base_model || m.name}
                          </span>
                        </div>
                      </div>

                      {acc !== undefined && acc !== null && (
                        <div style={{
                          padding: '3px 8px', borderRadius: '12px',
                          background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.3)',
                          color: '#3fb950', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0
                        }}>
                          🎯 {acc}%
                        </div>
                      )}
                    </div>

                    {/* Sources Tags */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '2px' }}>
                      {sources.map(s => (
                        <span key={s} style={{
                          fontSize: '0.6rem', padding: '2px 7px', borderRadius: '6px',
                          background: s === 'ollama' ? 'rgba(0,210,255,0.12)' : s === 'cache' ? 'rgba(188,140,255,0.12)' : 'rgba(63,185,80,0.12)',
                          color: s === 'ollama' ? '#00d2ff' : s === 'cache' ? '#bc8cff' : '#3fb950',
                          border: `1px solid ${s === 'ollama' ? 'rgba(0,210,255,0.25)' : s === 'cache' ? 'rgba(188,140,255,0.25)' : 'rgba(63,185,80,0.25)'}`
                        }}>
                          [{s.toUpperCase()}]
                        </span>
                      ))}
                      {m.last_run_at && (
                        <span style={{ fontSize: '0.6rem', color: '#8b8fa3', marginLeft: 'auto' }}>
                          🕒 {m.last_run_at}
                        </span>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
                      <button
                        className="mg-btn-primary"
                        onClick={() => handleSelectAsChatModel(m.name)}
                        style={{ flex: 1, padding: '6px 10px', fontSize: '0.68rem', justifyContent: 'center' }}
                      >
                        <Zap size={12} /> Seleziona in Chat
                      </button>
                      <button
                        className="mg-btn"
                        onClick={() => {
                          setModelName(`sigma-${(m.name || 'agent').replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase()}`);
                          setBaseModel(m.name);
                          setActiveSubTab('standard');
                        }}
                        style={{ padding: '6px 10px', fontSize: '0.68rem' }}
                        title="Crea un Modelfile basato su questo modello addestrato"
                      >
                        <FileSignature size={12} /> Manifesto
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  );
}