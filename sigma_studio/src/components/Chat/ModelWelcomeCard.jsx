import React, { useState } from 'react';
import { 
  Cpu, 
  Zap, 
  HardDrive, 
  Layers, 
  Activity, 
  ChevronDown, 
  ChevronUp, 
  Award, 
  Gauge, 
  Sliders, 
  ExternalLink
} from 'lucide-react';
import { getModelSpecs } from './core/modelSpecsHelper';

/**
 * ModelWelcomeCard — Strip orizzontale snella a tutta lunghezza per il modello attivo.
 * Profilo compatto (non ingombrante verticalmente), si sviluppa per lungo
 * dichiarando il motore attivo, le metriche misurate e consentendo
 * l'espansione dei dettagli tecnici al click.
 */
export default function ModelWelcomeCard({
  modelName,
  effectiveModelName,
  roleName = 'Sigma Assistant',
  agentStyle = null,
  activeManifesto = null,
  availableModels = [],
  openTab = null
}) {
  const [showSpecsDetails, setShowSpecsDetails] = useState(false);

  // Risoluzione precisa del modello attivo e delle specifiche
  const activeModelRaw = effectiveModelName || modelName || 'AI Model';
  const cleanModelName = activeModelRaw.includes(':\\') 
    ? activeModelRaw.split(/[/\\]/).pop().replace(/\.gguf$/i, '') 
    : activeModelRaw.replace(/\.gguf$/i, '');

  const specs = getModelSpecs(activeModelRaw, availableModels) || {};
  const family = specs.family || {};
  const chatSpeed = specs.chatSpeed;
  const benchmarkScore = specs.benchmark_score;
  const rawModel = specs.rawModel || {};

  return (
    <div className="model-welcome-strip">
      {/* Barra orizzontale snella principale a tutta lunghezza */}
      <div className="model-welcome-main-bar">
        {/* Sinistra: Stato, Modello, Brand e Ruolo */}
        <div className="model-welcome-left">
          <span className="model-welcome-pulse-dot" title="Motore AI online e pronto" />
          <Cpu size={15} className="model-welcome-chip-icon" />
          <span className="model-welcome-name" title={activeModelRaw}>
            {cleanModelName}
          </span>

          {family.brand && (
            <span 
              className="model-welcome-family-tag"
              style={{ color: family.color || '#00d2ff', borderColor: family.border || 'rgba(0, 210, 255, 0.3)' }}
            >
              {family.brand}
            </span>
          )}

          <span className="model-welcome-divider">|</span>

          <div className="model-welcome-role-inline" title="Ruolo cognitivo assegnato">
            <span className="model-welcome-role-icon">{agentStyle?.icon || activeManifesto?.icon || '🤖'}</span>
            <span className="model-welcome-role-name">{activeManifesto?.name || roleName}</span>
          </div>
        </div>

        {/* Destra: Pillole metriche rapide orizzontali + Toggle dettagli */}
        <div className="model-welcome-right">
          {specs.params && (
            <div className="model-metric-pill params" title="Conteggio parametri">
              <Zap size={11} />
              <span>{specs.params}</span>
            </div>
          )}

          {specs.size && (
            <div className="model-metric-pill size" title="Occupazione VRAM / Memoria">
              <HardDrive size={11} />
              <span>{specs.size}</span>
            </div>
          )}

          {specs.format && (
            <div className="model-metric-pill format" title="Formato e quantizzazione">
              <Layers size={11} />
              <span>{specs.format}</span>
            </div>
          )}

          {benchmarkScore && (
            <div className="model-metric-pill benchmark" title="Punteggio benchmark">
              <Award size={11} />
              <span>{benchmarkScore}%</span>
            </div>
          )}

          {chatSpeed ? (
            <div className="model-metric-pill speed" title="Velocità live misurata">
              <Gauge size={11} />
              <span>{chatSpeed} t/s</span>
            </div>
          ) : (
            <div className="model-metric-pill ready" title="Inferenza pronta">
              <Activity size={11} />
              <span>Live Ready</span>
            </div>
          )}

          <button
            type="button"
            className={`model-welcome-toggle-btn ${showSpecsDetails ? 'active' : ''}`}
            onClick={() => setShowSpecsDetails(!showSpecsDetails)}
            title="Mostra / Nascondi specifiche misurate e dettagli tecnici"
          >
            <Sliders size={11} />
            <span>{showSpecsDetails ? 'Chiudi' : 'Specifiche'}</span>
            {showSpecsDetails ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>
        </div>
      </div>

      {/* Pannello Dettagli Tecnico compatto a comparsa */}
      {showSpecsDetails && (
        <div className="model-welcome-expanded-panel">
          <div className="model-welcome-expanded-grid">
            <div className="model-strip-detail">
              <span className="model-strip-label">File / Percorso</span>
              <span className="model-strip-val mono" title={activeModelRaw}>{rawModel.filename || activeModelRaw}</span>
            </div>
            <div className="model-strip-detail">
              <span className="model-strip-label">Architettura</span>
              <span className="model-strip-val">{family.title || rawModel.architecture || 'Transformer GGUF'}</span>
            </div>
            <div className="model-strip-detail">
              <span className="model-strip-label">Quantizzazione</span>
              <span className="model-strip-val">{specs.quantization || specs.format || 'Standard'}</span>
            </div>
            <div className="model-strip-detail">
              <span className="model-strip-label">Contesto</span>
              <span className="model-strip-val">
                {rawModel.context_length ? `${Number(rawModel.context_length).toLocaleString()} token` : 'Adattivo'}
              </span>
            </div>
            <div className="model-strip-detail">
              <span className="model-strip-label">Velocità Misurata</span>
              <span className="model-strip-val">{chatSpeed ? `${chatSpeed} token/sec` : 'Al primo prompt'}</span>
            </div>
            <div className="model-strip-detail">
              <span className="model-strip-label">Backend</span>
              <span className="model-strip-val">{specs.provider || 'Sigma Engine'}</span>
            </div>
          </div>

          {openTab && (
            <div className="model-welcome-strip-actions">
              <button 
                type="button" 
                className="model-welcome-strip-link"
                onClick={() => openTab('models')}
              >
                <ExternalLink size={11} />
                <span>Apri tab Modelli</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
