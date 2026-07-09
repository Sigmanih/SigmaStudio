import React, { useState, useEffect } from 'react';
import { 
  ArrowRight, BookOpen, FileText, FileSignature, Layers, FileDown, 
  Sparkles, ScrollText, Eye, Plus, Cpu, Play, Terminal, CheckCircle, AlertCircle, Loader,
  Info, Code, GitBranch, Wand2
} from 'lucide-react';

// ==============================================================================
// ManifestiGallery + AI Model Lab
// Crea e gestisce modelli AI su Ollama usando Modelfile
// ==============================================================================

export default function ManifestiGallery({ modules, manifesti, openTab, setFileModalContext, setIsFileModalOpen, fetchManifesti }) {
  const [manifestoText, setManifestoText] = useState('');
  const [manifestoLoading, setManifestoLoading] = useState(true);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [creatingModel, setCreatingModel] = useState(false);
  const [createResult, setCreateResult] = useState(null);
  const [selectedModelfile, setSelectedModelfile] = useState('manifesti/agente0.md');
  const [modelName, setModelName] = useState('sigma-agent');
  const [baseModel, setBaseModel] = useState('llama3.2');

  useEffect(() => {
    fetch('/api/get_file?path=manifesti/agente0.md')
      .then(r => r.json())
      .then(d => { 
        if (d.success) setManifestoText(d.content); 
        setManifestoLoading(false);
      })
      .catch(() => setManifestoLoading(false));
  }, []);

  // Fetch Ollama models via backend (avoids CORS issues)
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

  const allWp = modules.flatMap(m => m.whitepapers || []);

  const handleNewManifesto = () => {
    setFileModalContext({ folder: 'manifesti', type: 'manifesti' });
    setIsFileModalOpen(true);
  };

  const handleCreateModel = async () => {
    if (!modelName.trim()) return;
    setCreatingModel(true);
    setCreateResult(null);
    
    try {
      // Get Modelfile content
      const res = await fetch(`/api/get_file?path=${encodeURIComponent(selectedModelfile)}`);
      const data = await res.json();
      if (!data.success) {
        setCreateResult({ success: false, message: 'Impossibile leggere il Modelfile' });
        return;
      }

      // Replace FROM line in Modelfile with the selected base model
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
        fetchOllamaModels(); // Refresh models list
      }
    } catch (e) {
      setCreateResult({ success: false, message: e.message });
    }
    setCreatingModel(false);
  };

  return (
    <div className="wp-tab">
      <style>{`
        .wp-tab { padding: 24px; height: 100%; overflow-y: auto; }
        .wp-manifesto-hero { background: linear-gradient(135deg, rgba(188,140,255,0.08) 0%, rgba(0,210,255,0.04) 100%); border: 1px solid rgba(188,140,255,0.15); border-radius: 16px; padding: 28px; margin-bottom: 24px; }
        .wp-manifesto-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 0.55rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px; background: rgba(188,140,255,0.15); color: #bc8cff; margin-bottom: 12px; }
        .wp-manifesto-hero-content { display: flex; gap: 24px; align-items: flex-start; }
        .wp-manifesto-hero-left { flex: 1; }
        .wp-manifesto-title { font-size: 1.5rem; font-weight: 700; color: #e2e4eb; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; }
        .wp-manifesto-version { font-size: 0.6rem; background: rgba(0,210,255,0.1); color: #00d2ff; padding: 2px 10px; border-radius: 4px; font-weight: 600; }
        .wp-manifesto-subtitle { font-size: 0.75rem; color: #8b8fa3; margin-bottom: 16px; }
        .wp-manifesto-actions { display: flex; gap: 8px; }
        .wp-btn-primary { display: inline-flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 8px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid rgba(0,210,255,0.3); background: rgba(0,210,255,0.1); color: #00d2ff; font-family: inherit; transition: all 0.15s; }
        .wp-btn-primary:hover { background: rgba(0,210,255,0.2); box-shadow: 0 0 20px rgba(0,210,255,0.15); }
        
        .wp-section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .wp-section-title { font-size: 0.95rem; font-weight: 600; color: #e2e4eb; display: flex; align-items: center; gap: 8px; }
        .wp-section-desc { font-size: 0.65rem; color: #5a5e72; margin-top: 4px; }
        .wp-btn-create { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; font-size: 0.7rem; cursor: pointer; border: 1px solid rgba(188,140,255,0.2); background: rgba(188,140,255,0.08); color: #bc8cff; font-family: inherit; transition: all 0.15s; }
        .wp-btn-create:hover { background: rgba(188,140,255,0.15); }
        .wp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .wp-modern-card { display: flex; align-items: center; gap: 12px; padding: 14px 16px; background: #11131b; border: 1px solid #1e2030; border-radius: 10px; cursor: pointer; transition: all 0.15s; }
        .wp-modern-card:hover { border-color: #2a2d3e; transform: translateY(-1px); }
        .wp-modern-card-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .wp-modern-card-body h4 { font-size: 0.8rem; font-weight: 600; color: #e2e4eb; margin-bottom: 2px; }
        .wp-modern-card-meta { font-size: 0.6rem; color: #5a5e72; display: flex; align-items: center; gap: 4px; }
        .wp-modern-card-action { margin-left: auto; color: #5a5e72; }
        .wp-empty { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 40px; color: #5a5e72; font-size: 0.75rem; text-align: center; }

        /* Model Lab Section */
        .model-lab { background: #11131b; border: 1px solid #1e2030; border-radius: 12px; padding: 20px; margin-top: 24px; }
        .model-lab h3 { font-size: 0.95rem; font-weight: 600; color: #e2e4eb; display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
        .model-lab-row { display: flex; gap: 16px; margin-bottom: 16px; }
        .model-lab-col { flex: 1; }
        .model-lab label { font-size: 0.65rem; color: #8b8fa3; display: block; margin-bottom: 4px; font-weight: 500; }
        .model-lab input, .model-lab select { width: 100%; padding: 8px 12px; border-radius: 6px; font-size: 0.75rem; border: 1px solid #1e2030; background: #0e1016; color: #e2e4eb; font-family: inherit; outline: none; }
        .model-lab input:focus, .model-lab select:focus { border-color: #bc8cff; }
        .model-lab .btn-create-model { display: inline-flex; align-items: center; gap: 8px; padding: 10px 24px; border-radius: 8px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid rgba(63,185,80,0.3); background: rgba(63,185,80,0.1); color: #3fb950; font-family: inherit; transition: all 0.15s; }
        .model-lab .btn-create-model:hover { background: rgba(63,185,80,0.2); }
        .model-lab .btn-create-model:disabled { opacity: 0.5; cursor: not-allowed; }
        .model-result { padding: 10px 14px; border-radius: 8px; font-size: 0.7rem; margin-top: 12px; display: flex; align-items: center; gap: 8px; }
        .model-result.success { background: rgba(63,185,80,0.1); border: 1px solid rgba(63,185,80,0.2); color: #3fb950; }
        .model-result.error { background: rgba(255,85,85,0.1); border: 1px solid rgba(255,85,85,0.2); color: #ff5555; }
        
        .models-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; margin-top: 12px; }
        .model-chip { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #0e1016; border: 1px solid #1e2030; border-radius: 8px; font-size: 0.65rem; color: #8b8fa3; }
        .model-chip .model-status { width: 6px; height: 6px; border-radius: 50%; background: #3fb950; flex-shrink: 0; }
      `}</style>

      {/* === Manifesto Hero Section === */}
      <div className="wp-manifesto-hero" style={{ marginBottom: '20px' }}>
        <div className="wp-manifesto-badge">
          <ScrollText size={14} />
          MODELFILE AI
        </div>
        <div className="wp-manifesto-hero-content">
          <div className="wp-manifesto-hero-left">
            <h2 className="wp-manifesto-title">
              Σ-SIGMA AI Modelfile
              <span className="wp-manifesto-version">v5.0</span>
            </h2>
            <p className="wp-manifesto-subtitle">
              Modelfile per Ollama — istruisce modelli AI a operare in Sigma Studio
            </p>
            <div className="wp-manifesto-actions">
              <button 
                className="wp-btn-primary"
                onClick={() => openTab({ name: 'agente0.md', path: 'manifesti/agente0.md' }, 'manifesti')}
              >
                <Eye size={16} />
                Leggi il Modelfile
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* === Manifesti Guide Section === */}
      <div className="model-lab" style={{ marginBottom: '24px', borderColor: 'rgba(188,140,255,0.15)', background: 'linear-gradient(135deg, rgba(188,140,255,0.02) 0%, rgba(0,210,255,0.01) 100%)' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1rem' }}>
          <Info size={20} style={{ color: '#bc8cff' }} />
          Cosa sono i Modelfile e perché servono
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginTop: '16px' }}>
          {/* Card 1 */}
          <div style={{ background: 'rgba(14,16,22,0.6)', border: '1px solid rgba(188,140,255,0.08)', borderRadius: '10px', padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(188,140,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ScrollText size={16} style={{ color: '#bc8cff' }} />
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.8rem', color: '#e2e4eb' }}>System Prompt Persistente</span>
            </div>
            <p style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6, margin: 0 }}>
              Un Modelfile definisce l'identità e il comportamento di un modello AI in modo <strong style={{ color: '#bc8cff' }}>permanente</strong>. 
              A differenza dei prompt temporanei nella chat, il Modelfile viene incorporato direttamente nel modello quando lo crei con <code style={{ background: '#1e2030', padding: '1px 6px', borderRadius: '3px', fontSize: '0.65rem' }}>ollama create</code>.
            </p>
          </div>
          {/* Card 2 */}
          <div style={{ background: 'rgba(14,16,22,0.6)', border: '1px solid rgba(0,210,255,0.08)', borderRadius: '10px', padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(0,210,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <GitBranch size={16} style={{ color: '#00d2ff' }} />
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.8rem', color: '#e2e4eb' }}>Specializzazione per Dominio</span>
            </div>
            <p style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6, margin: 0 }}>
              Ogni argomento di ricerca può avere il suo modello specializzato. Un Modelfile per la <strong style={{ color: '#00d2ff' }}>matematica</strong> include regole e conoscenze diverse da uno per la <strong style={{ color: '#00d2ff' }}>linguistica</strong>. Questo garantisce risposte più pertinenti e contestualizzate.
            </p>
          </div>
          {/* Card 3 */}
          <div style={{ background: 'rgba(14,16,22,0.6)', border: '1px solid rgba(63,185,80,0.08)', borderRadius: '10px', padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(63,185,80,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Wand2 size={16} style={{ color: '#3fb950' }} />
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.8rem', color: '#e2e4eb' }}>Parametri Ottimizzati</span>
            </div>
            <p style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6, margin: 0 }}>
              Il Modelfile ti permette di configurare parametri come <strong style={{ color: '#3fb950' }}>temperature</strong>, <strong style={{ color: '#3fb950' }}>top_p</strong> e <strong style={{ color: '#3fb950' }}>num_ctx</strong> una volta per tutte, 
              senza doverli reimpostare a ogni conversazione. Il modello "nasce" già configurato per il suo scopo.
            </p>
          </div>
        </div>

        {/* How-to build section */}
        <div style={{ marginTop: '20px', padding: '16px', background: 'rgba(14,16,22,0.8)', border: '1px solid rgba(210,153,34,0.15)', borderRadius: '10px' }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', fontWeight: 600, color: '#d29922', margin: '0 0 12px 0' }}>
            <Code size={18} />
            Come costruire un Modelfile — procedura
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '10px' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(210,153,34,0.15)', color: '#d29922', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>1</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6 }}>
                <strong style={{ color: '#e2e4eb' }}>Scegli un Modelfile base</strong> — Usa agente0.md come template universale o creane uno nuovo con il pulsante <span style={{ color: '#bc8cff' }}>"Nuovo Modelfile"</span>.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(210,153,34,0.15)', color: '#d29922', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>2</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6 }}>
                <strong style={{ color: '#e2e4eb' }}>Personalizza il SYSTEM</strong> — Scrivi istruzioni chiare sul ruolo del modello, il dominio di competenza, lo stile di risposta e le regole da seguire.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(210,153,34,0.15)', color: '#d29922', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>3</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6 }}>
                <strong style={{ color: '#e2e4eb' }}>Seleziona un modello base</strong> — Scegli da Ollama (es. qwen3.6, llama3.1, gemma4). Il modello base fornisce le capacità linguistiche fondamentali.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(210,153,34,0.15)', color: '#d29922', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>4</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6 }}>
                <strong style={{ color: '#e2e4eb' }}>Assegna un nome</strong> — Scegli un nome descrittivo (es. sigma-matematico, sigma-linguista). Il nome verrà usato per richiamare il modello nella chat.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(63,185,80,0.15)', color: '#3fb950', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0 }}>5</div>
              <div style={{ fontSize: '0.68rem', color: '#8b8fa3', lineHeight: 1.6 }}>
                <strong style={{ color: '#3fb950' }}>Crea il modello</strong> — Clicca <span style={{ color: '#3fb950' }}>"Crea Modello su Ollama"</span>. Sigma Studio invia il Modelfile a Ollama che lo compila in un nuovo modello AI pronto all'uso.
              </div>
            </div>
          </div>
          <div style={{ marginTop: '12px', padding: '10px 14px', background: 'rgba(0,210,255,0.05)', border: '1px solid rgba(0,210,255,0.1)', borderRadius: '8px', fontSize: '0.65rem', color: '#8b8fa3', lineHeight: 1.6 }}>
            <strong style={{ color: '#00d2ff' }}>💡 Struttura di un Modelfile:</strong><br/>
            <code style={{ display: 'block', marginTop: '6px', padding: '8px 12px', background: '#0e1016', borderRadius: '6px', fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", color: '#bc8cff' }}>
              FROM qwen3.6:27b<br/>
              <span style={{ color: '#5a5e72' }}># Sistema</span><br/>
              SYSTEM "Sei un assistente specializzato in..."<br/>
              <span style={{ color: '#5a5e72' }}># Parametri</span><br/>
              PARAMETER temperature 0.7<br/>
              PARAMETER num_ctx 32768
            </code>
          </div>
        </div>
      </div>

      {/* === AI Model Lab === */}
      <div className="model-lab">
        <h3><Cpu size={20} /> AI Model Lab — Crea un modello Sigma su Ollama</h3>
        
        <div className="model-lab-row">
          <div className="model-lab-col">
            <label>Modelfile di base</label>
            <select value={selectedModelfile} onChange={e => setSelectedModelfile(e.target.value)}>
              <option value="manifesti/agente0.md">agente0.md (Modelfile principale)</option>
              {manifesti.map((mf, i) => (
                <option key={i} value={mf.path}>{mf.filename}</option>
              ))}
            </select>
          </div>
          <div className="model-lab-col">
            <label>Modello base Ollama</label>
            <select value={baseModel} onChange={e => setBaseModel(e.target.value)}>
              <option value="">— Seleziona un modello —</option>
              {ollamaModels.map((m, i) => (
                <option key={i} value={m.name}>{m.name}</option>
              ))}
            </select>
            {ollamaModels.length === 0 && !modelsLoading && (
              <div style={{ fontSize: '0.6rem', color: '#ff5555', marginTop: '4px' }}>
                ⚠️ Nessun modello trovato. Verifica che Ollama sia in esecuzione.
              </div>
            )}
          </div>
          <div className="model-lab-col">
            <label>Nome del nuovo modello</label>
            <input 
              value={modelName} 
              onChange={e => setModelName(e.target.value)} 
              placeholder="es. sigma-agent, sigma-matematico"
            />
          </div>
        </div>
        
        <button className="btn-create-model" onClick={handleCreateModel} disabled={creatingModel || !modelName.trim()}>
          {creatingModel ? <><Loader size={16} /> Creazione in corso...</> : <><Play size={16} /> Crea Modello su Ollama</>}
        </button>

        {createResult && (
          <div className={`model-result ${createResult.success ? 'success' : 'error'}`}>
            {createResult.success ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {createResult.message}
          </div>
        )}
      </div>

      {/* === Ollama Models === */}
      <div className="model-lab" style={{ marginTop: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h3 style={{ margin: 0 }}><Cpu size={18} /> Modelli Ollama disponibili</h3>
          <button className="wp-btn-create" onClick={fetchOllamaModels} style={{ fontSize: '0.6rem', padding: '4px 10px' }}>
            <ArrowRight size={12} /> Aggiorna
          </button>
        </div>
        {modelsLoading ? (
          <div style={{ fontSize: '0.7rem', color: '#5a5e72', padding: '12px' }}>Caricamento modelli...</div>
        ) : ollamaModels.length === 0 ? (
          <div style={{ fontSize: '0.7rem', color: '#5a5e72', padding: '12px' }}>
            Nessun modello trovato. Assicurati che Ollama sia in esecuzione e crea il tuo primo modello qui sopra.
          </div>
        ) : (
          <div className="models-grid">
            {ollamaModels.map((m, i) => (
              <div key={i} className="model-chip">
                <span className="model-status" />
                <span style={{ fontWeight: 600 }}>{m.name}</span>
                <span style={{ marginLeft: 'auto', opacity: 0.5, fontSize: '0.55rem' }}>
                  {m.size ? `${(m.size / 1e9).toFixed(1)}GB` : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* === Manifesti Collection === */}
      <div className="wp-section" style={{ marginTop: '24px' }}>
        <div className="wp-section-header">
          <div className="wp-section-header-left">
            <h3 className="wp-section-title">
              <Layers size={20} />
              Modelfile Collection
            </h3>
            <p className="wp-section-desc">
              {manifesti.length} Modelfile nella cartella manifesti/ — usa il Modelfile Lab qui sopra per crearne un modello AI
            </p>
          </div>
          <button className="wp-btn-create" onClick={handleNewManifesto}>
            <FileSignature size={16} />
            Nuovo Modelfile
            <Sparkles size={14} />
          </button>
        </div>
        <div className="wp-grid">
          {manifesti.map((mf, i) => (
            <div key={i} className="wp-modern-card" onClick={() => openTab(mf, 'manifesti')}>
              <div className="wp-modern-card-icon" style={{background: 'rgba(124,91,240,0.15)', color: '#a78bfa'}}>
                <FileSignature size={22} />
              </div>
              <div className="wp-modern-card-body">
                <h4>{mf.name}</h4>
                <span className="wp-modern-card-meta">
                  <FileDown size={12} />
                  Modelfile AI
                </span>
              </div>
              <div className="wp-modern-card-action">
                <ArrowRight size={16} />
              </div>
            </div>
          ))}
          {manifesti.length === 0 && (
            <div className="wp-empty">
              <Layers size={48} />
              <p>Nessun Modelfile trovato</p>
              <span>Crea il tuo primo Modelfile per istruire un modello AI.</span>
              <button className="wp-btn-create" onClick={handleNewManifesto} style={{marginTop: 16}}>
                <FileSignature size={16} />
                Crea il primo Modelfile
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}