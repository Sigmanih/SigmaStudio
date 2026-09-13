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
  Sparkles, 
  Gauge, 
  CheckCircle2, 
  Sliders, 
  Info,
  ExternalLink
} from 'lucide-react';
import { getModelSpecs } from './core/modelSpecsHelper';

/**
 * ModelWelcomeCard — Card elegante di presentazione del modello attivo.
 * Sostituisce il vecchio messaggio fittizio con un header moderno che dichiara
 * lo stato del modello attivo e consente l'accesso alle statistiche misurate
 * e informazioni tecniche avanzate.
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

  // Risoluzione precisa del nome e delle specifiche del modello attivo
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
    <div className="model-welcome-card">
      {/* Glow aura di sfondo */}
      <div className="model-welcome-aura" />

      {/* Header card: Status e Famiglia */}
      <div className="model-welcome-header">
        <div className="model-welcome-status">
          <span className="model-welcome-pulse-dot" />
          <span className="model-welcome-status-text">Motore Attivo</span>
          {family.brand && (
            <span 
              className="model-welcome-brand-chip" 
              style={{ color: family.color || '#00d2ff', borderColor: family.border || 'rgba(0, 210, 255, 0.3)' }}
            >
              {family.brand}
            </span>
          )}
        </div>

        <div className="model-welcome-role-badge">
          <span className="model-welcome-role-icon">{agentStyle?.icon || activeManifesto?.icon || '🤖'}</span>
          <span className="model-welcome-role-label">
            Ruolo: <strong>{activeManifesto?.name || roleName}</strong>
          </span>
        </div>
      </div>

      {/* Sezione Centrale: Nome Modello e Titolo */}
      <div className="model-welcome-body">
        <div className="model-welcome-title-row">
          <div className="model-welcome-icon-box">
            <Cpu size={22} className="model-welcome-icon" />
          </div>
          <div className="model-welcome-name-group">
            <h2 className="model-welcome-name" title={activeModelRaw}>
              {cleanModelName}
            </h2>
            <p className="model-welcome-subtitle">
              {specs.format ? `${specs.format}` : 'Modello linguistico pronto all\'esecuzione'}
              {specs.isPublished && ' • Convalidato e Pubblicato'}
            </p>
          </div>
        </div>

        {/* Barra Metriche Rapide (Pillole visive ad alto impatto) */}
        <div className="model-welcome-quick-metrics">
          {specs.params && (
            <div className="model-metric-pill params" title="Conteggio parametri stimato/dichiarato">
              <Zap size={12} />
              <span>Parametri: <strong>{specs.params}</strong></span>
            </div>
          )}

          {specs.size && (
            <div className="model-metric-pill size" title="Occupazione VRAM / Disco">
              <HardDrive size={12} />
              <span>Memoria: <strong>{specs.size}</strong></span>
            </div>
          )}

          {specs.format && (
            <div className="model-metric-pill format" title="Formato file e quantizzazione">
              <Layers size={12} />
              <span>{specs.format}</span>
            </div>
          )}

          {benchmarkScore && (
            <div className="model-metric-pill benchmark" title="Punteggio benchmark registrato">
              <Award size={12} />
              <span>Score: <strong>{benchmarkScore}%</strong></span>
            </div>
          )}

          {chatSpeed ? (
            <div className="model-metric-pill speed" title="Velocità di inferenza live misurata">
              <Gauge size={12} />
              <span>Velocità: <strong>{chatSpeed} t/s</strong></span>
            </div>
          ) : (
            <div className="model-metric-pill ready" title="In attesa del primo token per calcolo t/s">
              <Activity size={12} />
              <span>Inferenza: <strong>Pronta</strong></span>
            </div>
          )}

          {/* Pulsante Toggle Dettagli / Statistiche Misurate */}
          <button
            type="button"
            className={`model-welcome-toggle-btn ${showSpecsDetails ? 'active' : ''}`}
            onClick={() => setShowSpecsDetails(!showSpecsDetails)}
            title="Mostra / Nascondi statistiche misurate e specifiche tecniche complete"
          >
            <Sliders size={12} />
            <span>{showSpecsDetails ? 'Meno dettagli' : 'Specifiche & Metriche'}</span>
            {showSpecsDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        </div>

        {/* Pannello Espandibile con Statistiche Misurate & Specifiche Tecniche */}
        {showSpecsDetails && (
          <div className="model-welcome-details-panel">
            <div className="model-welcome-details-grid">
              <div className="model-detail-item">
                <span className="model-detail-label">Nome Completo</span>
                <span className="model-detail-value mono" title={activeModelRaw}>{activeModelRaw}</span>
              </div>

              <div className="model-detail-item">
                <span className="model-detail-label">Architettura / Famiglia</span>
                <span className="model-detail-value">{family.title || rawModel.architecture || 'Transformer'}</span>
              </div>

              <div className="model-detail-item">
                <span className="model-detail-label">Quantizzazione</span>
                <span className="model-detail-value">{specs.quantization || specs.format || 'Standard'}</span>
              </div>

              <div className="model-detail-item">
                <span className="model-detail-label">Finestra di Contesto</span>
                <span className="model-detail-value">
                  {rawModel.context_length 
                    ? `${Number(rawModel.context_length).toLocaleString()} token`
                    : 'Adattiva (gestita da provider)'}
                </span>
              </div>

              <div className="model-detail-item">
                <span className="model-detail-label">Velocità Misurata</span>
                <span className="model-detail-value">
                  {chatSpeed ? `${chatSpeed} token/sec` : 'Calcolata al primo output'}
                </span>
              </div>

              <div className="model-detail-item">
                <span className="model-detail-label">Backend di Inferenza</span>
                <span className="model-detail-value">{specs.provider || 'Sigma Local Engine'}</span>
              </div>

              {benchmarkScore && (
                <div className="model-detail-item highlight">
                  <span className="model-detail-label">Accuratezza Benchmark</span>
                  <span className="model-detail-value">{benchmarkScore}% (Test completati)</span>
                </div>
              )}

              {rawModel.filename && (
                <div className="model-detail-item full-width">
                  <span className="model-detail-label">File Sorgente</span>
                  <span className="model-detail-value mono">{rawModel.filename}</span>
                </div>
              )}
            </div>

            {openTab && (
              <div className="model-welcome-panel-footer">
                <button 
                  type="button" 
                  className="model-welcome-link-btn"
                  onClick={() => openTab('models')}
                >
                  <ExternalLink size={12} />
                  <span>Gestisci o cambia modello nella tab Modelli</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Footer accogliente con suggerimento operativo */}
        <div className="model-welcome-footer">
          <div className="model-welcome-hint">
            <Sparkles size={14} className="model-welcome-sparkle" />
            <span>Sistema pronto per ragionamento, codice e analisi. Digita una richiesta o formula una domanda per iniziare.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
