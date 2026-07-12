import React, { useState, useEffect } from 'react';
import { 
  ArrowRight, BookOpen, FileText, FileSignature, Layers, FileDown, 
  Sparkles, ScrollText, Eye, Plus, Cpu, Play, CheckCircle, AlertCircle, Loader,
  Info, Code, GitBranch, Wand2
} from 'lucide-react';

// ==============================================================================
// ManifestiGallery — Manifesto Editor & AI Model Lab
// Gestisce i manifesti Modelfile per agenti AI su Ollama
// ==============================================================================

export default function ManifestiGallery({ modules, manifesti, openTab, setFileModalContext, setIsFileModalOpen, fetchManifesti }) {
  const [manifestoText, setManifestoText] = useState('');
  const [manifestoLoading, setManifestoLoading] = useState(true);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [creatingModel, setCreatingModel] = useState(false);
  const [createResult, setCreateResult] = useState(null);
  const [selectedManifesto, setSelectedManifesto] = useState('');
  const [modelName, setModelName] = useState('sigma-agent');
  const [baseModel, setBaseModel] = useState('llama3.2');

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

  const handleNewManifesto = () => {
    setFileModalContext({ folder: 'manifesti', type: 'manifesti' });
    setIsFileModalOpen(true);
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
    <div className="mg-tab">
      <style>{`
        .mg-tab { padding: 20px; height: 100%; overflow-y: auto; }
        .mg-section { margin-bottom: 20px; }
        .mg-section-title { font-size: 0.85rem; font-weight: 600; color: #e2e4eb; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
        .mg-section-desc { font-size: 0.62rem; color: #5a5e72; margin-bottom: 10px; }
        .mg-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
        .mg-card { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; background: #11131b; border: 1px solid #1e2030; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
        .mg-card:hover { border-color: #2a2d3e; transform: translateY(-1px); }
        .mg-card-header { display: flex; align-items: center; gap: 8px; }
        .mg-card-icon { width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 0.85rem; }
        .mg-card-name { font-size: 0.72rem; font-weight: 600; color: #e2e4eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .mg-card-meta { font-size: 0.55rem; color: #5a5e72; display: flex; align-items: center; gap: 4px; }
        .mg-card-action { margin-left: auto; color: #5a5e72; flex-shrink: 0; }
        .mg-empty { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 30px; color: #5a5e72; font-size: 0.7rem; text-align: center; }
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
        .mg-hero-sub { font-size: 0.68rem; color: #8b8fa3; margin-bottom: 12px; }
        .mg-guide-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
        .mg-guide-card { background: rgba(14,16,22,0.6); border: 1px solid rgba(188,140,255,0.06); border-radius: 8px; padding: 12px; }
        .mg-guide-card-title { display: flex; align-items: center; gap: 6px; font-size: 0.7rem; font-weight: 600; color: #e2e4eb; margin-bottom: 6px; }
        .mg-guide-card p { font-size: 0.6rem; color: #8b8fa3; line-height: 1.5; margin: 0; }
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
        .mg-howto { margin-top: 12px; padding: 12px; background: rgba(14,16,22,0.8); border: 1px solid rgba(210,153,34,0.12); border-radius: 8px; }
        .mg-howto-title { display: flex; align-items: center; gap: 6px; font-size: 0.75rem; font-weight: 600; color: #d29922; margin: 0 0 8px 0; }
        .mg-howto-steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 6px; }
        .mg-step { display: flex; gap: 8px; align-items: flex-start; }
        .mg-step-num { width: 20px; height: 20px; border-radius: 50%; background: rgba(210,153,34,0.12); color: #d29922; display: flex; align-items: center; justify-content: center; font-size: 0.6rem; font-weight: 700; flex-shrink: 0; }
        .mg-step p { font-size: 0.6rem; color: #8b8fa3; line-height: 1.5; margin: 0; }
        .mg-code-block { margin-top: 8px; padding: 6px 10px; background: #0e1016; border-radius: 6px; font-size: 0.55rem; font-family: 'JetBrains Mono', monospace; color: #bc8cff; line-height: 1.6; }
      `}</style>

      {/* === Hero Section (compact) === */}
      <div className="mg-hero mg-section">
        <div className="mg-hero-badge">
          <ScrollText size={12} />
          MANIFESTI AI
        </div>
        <div className="mg-hero-title">
          Σ-SIGMA Manifesti
          <span className="mg-hero-version">v5.0</span>
        </div>
        <p className="mg-hero-sub">
          I manifesti (Modelfile Ollama) definiscono identità, regole e parametri di ogni agente AI. 
          Scegli, modifica o crea il tuo manifesto, poi genera un modello AI su Ollama con un click.
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="mg-btn-primary" onClick={() => {
            const path = manifesti.length > 0 ? manifesti[0].path : 'manifesti/sigma_architect.md';
            const name = manifesti.length > 0 ? manifesti[0].filename : 'sigma_architect.md';
            openTab({ name, path }, 'manifesti');
          }}>
            <Eye size={14} />
            Leggi il Manifesto
          </button>
          <button className="mg-btn" onClick={handleNewManifesto}>
            <FileSignature size={14} />
            Nuovo Manifesto
          </button>
        </div>
      </div>

      {/* === MANIFESTI COLLECTION — cards in alto === */}
      <div className="mg-section">
        <div className="mg-toolbar">
          <div>
            <div className="mg-section-title">
              <Layers size={16} />
              Collezione Manifesti
            </div>
            <div className="mg-section-desc">
              {manifesti.length} manifesti disponibili in manifesti/
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
                <div className="mg-card-icon" style={{background: 'rgba(124,91,240,0.12)', color: '#a78bfa'}}>
                  <ScrollText size={14} />
                </div>
                <span className="mg-card-name">{mf.name}</span>
                <div className="mg-card-action">
                  <ArrowRight size={14} />
                </div>
              </div>
              <div className="mg-card-meta">
                <FileSignature size={10} />
                Manifesto AI
              </div>
            </div>
          ))}
          {manifesti.length === 0 && (
            <div className="mg-empty">
              <Layers size={36} />
              <p>Nessun manifesto trovato</p>
              <span>Crea il tuo primo manifesto per istruire un agente AI.</span>
              <button className="mg-btn" onClick={handleNewManifesto} style={{marginTop: 12}}>
                <FileSignature size={14} />
                Crea il primo Manifesto
              </button>
            </div>
          )}
        </div>
      </div>

      {/* === Guida Rapida (compatta) === */}
      <div className="mg-section mg-guide-grid">
        <div className="mg-guide-card">
          <div className="mg-guide-card-title">
            <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(188,140,255,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
              <ScrollText size={12} style={{color:'#bc8cff'}} />
            </div>
            System Prompt Persistente
          </div>
          <p>Il manifesto definisce identità e comportamento <strong style={{color:'#bc8cff'}}>permanentemente</strong> nel modello Ollama, non come prompt temporaneo.</p>
        </div>
        <div className="mg-guide-card">
          <div className="mg-guide-card-title">
            <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(0,210,255,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
              <GitBranch size={12} style={{color:'#00d2ff'}} />
            </div>
            Specializzazione
          </div>
          <p>Ogni dominio di ricerca ha il suo manifesto specializzato. Un agente matematico segue regole diverse da uno linguistico.</p>
        </div>
        <div className="mg-guide-card">
          <div className="mg-guide-card-title">
            <div style={{width:'24px',height:'24px',borderRadius:'6px',background:'rgba(63,185,80,0.1)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
              <Wand2 size={12} style={{color:'#3fb950'}} />
            </div>
            Parametri Ottimizzati
          </div>
          <p>Configura <strong style={{color:'#3fb950'}}>temperature</strong>, <strong style={{color:'#3fb950'}}>num_ctx</strong> e altri parametri una volta sola. Il modello nasce già pronto per il suo scopo.</p>
        </div>
      </div>

      {/* === How-to build (compatto) === */}
      <div className="mg-section mg-howto">
        <h4 className="mg-howto-title">
          <Code size={16} />
          Come creare un Manifesto in 5 passi
        </h4>
        <div className="mg-howto-steps">
          <div className="mg-step">
            <div className="mg-step-num" style={{background:'rgba(210,153,34,0.12)'}}>1</div>
            <p><strong style={{color:'#e2e4eb'}}>Scegli un base</strong> — sigma_architect.md come template universale o creane uno nuovo.</p>
          </div>
          <div className="mg-step">
            <div className="mg-step-num" style={{background:'rgba(210,153,34,0.12)'}}>2</div>
            <p><strong style={{color:'#e2e4eb'}}>Personalizza il SYSTEM</strong> — ruolo, dominio, regole, stile di risposta.</p>
          </div>
          <div className="mg-step">
            <div className="mg-step-num" style={{background:'rgba(210,153,34,0.12)'}}>3</div>
            <p><strong style={{color:'#e2e4eb'}}>Modello base</strong> — Scegli da Ollama (llama3.2, qwen3.6, gemma4...).</p>
          </div>
          <div className="mg-step">
            <div className="mg-step-num" style={{background:'rgba(210,153,34,0.12)'}}>4</div>
            <p><strong style={{color:'#e2e4eb'}}>Nome unico</strong> — es. sigma-matematico, sigma-linguista.</p>
          </div>
          <div className="mg-step">
            <div className="mg-step-num" style={{background:'rgba(63,185,80,0.12)', color:'#3fb950'}}>5</div>
            <p><strong style={{color:'#3fb950'}}>Crea il modello</strong> — Sigma Studio invia il Modelfile a Ollama che lo compila.</p>
          </div>
        </div>
        <div className="mg-code-block">
          FROM qwen3.6:27b<br/>
          <span style={{color:'#5a5e72'}}># Sistema</span><br/>
          SYSTEM "Sei un assistente specializzato in..."<br/>
          <span style={{color:'#5a5e72'}}># Parametri</span><br/>
          PARAMETER temperature 0.7<br/>
          PARAMETER num_ctx 32768
        </div>
      </div>

      {/* === AI Model Lab === */}
      <div className="mg-section mg-lab">
        <div className="mg-lab-title"><Cpu size={18} /> AI Model Lab — Crea un modello su Ollama</div>
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
            {ollamaModels.length === 0 && !modelsLoading && (
              <div style={{fontSize:'0.55rem',color:'#ff5555',marginTop:'3px'}}>
                ⚠️ Verifica che Ollama sia in esecuzione.
              </div>
            )}
          </div>
          <div className="mg-lab-col">
            <label>Nome del nuovo modello</label>
            <input value={modelName} onChange={e => setModelName(e.target.value)} placeholder="es. sigma-agent" />
          </div>
        </div>
        <button className="mg-btn-create-model" onClick={handleCreateModel} disabled={creatingModel || !modelName.trim()}>
          {creatingModel ? <><Loader size={14} /> Creazione...</> : <><Play size={14} /> Crea Modello su Ollama</>}
        </button>
        {createResult && (
          <div className={`mg-result ${createResult.success ? 'success' : 'error'}`}>
            {createResult.success ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            {createResult.message}
          </div>
        )}
      </div>

      {/* === Ollama Models === */}
      <div className="mg-section mg-lab">
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'8px'}}>
          <div className="mg-lab-title" style={{margin:0}}><Cpu size={14} /> Modelli Ollama installati</div>
          <button className="mg-btn" onClick={fetchOllamaModels} style={{fontSize:'0.55rem',padding:'3px 8px'}}>
            <ArrowRight size={10} /> Aggiorna
          </button>
        </div>
        {modelsLoading ? (
          <div style={{fontSize:'0.65rem',color:'#5a5e72',padding:'8px'}}>Caricamento...</div>
        ) : ollamaModels.length === 0 ? (
          <div style={{fontSize:'0.65rem',color:'#5a5e72',padding:'8px'}}>
            Nessun modello. Crea il tuo primo manifesto qui sopra.
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
    </div>
  );
}