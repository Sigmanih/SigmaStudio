import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowRight, BookOpen, FileText, FileSignature, Layers, FileDown, 
  Sparkles, ScrollText, Eye, Plus, Cpu, Play, CheckCircle, AlertCircle, Loader,
  Info, Code, GitBranch, Wand2, Upload
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

  const fileInputRefs = useRef({});

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
    </div>
  );
}