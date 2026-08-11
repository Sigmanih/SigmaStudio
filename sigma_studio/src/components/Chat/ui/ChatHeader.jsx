import React from 'react';
import { GripVertical, Cpu, FileText } from 'lucide-react';
import ModelSelector from '../ModelSelector';

const MANIFESTO_STYLE = { position: 'relative', marginLeft: '6px' };

export default function ChatHeader({
  isDragging, onStartDrag, selectedModel, availableModels, loadingModels,
  showModelDropdown, onToggleDropdown, onSelectModel, providerConfigs, modelBtnRef,
  activeManifesto, manifestos, showManifestoDropdown, setShowManifestoDropdown,
  onSelectManifesto, onDuplicateSession, onOpenQuickConfig, showQuickConfig,
  onOpenConfig, onClose, isPanel = false, contextStats, onCopyAll,
}) {
  const [copiedAll, setCopiedAll] = React.useState(false);

  const handleCopyAll = (e) => {
    e.stopPropagation();
    if (onCopyAll) {
      onCopyAll();
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    }
  };

  return (
    <div 
      className="chat-header"
      onMouseDown={(e) => {
        if (!isPanel || !onStartDrag) return;
        if (e.target.closest('button') || e.target.closest('.model-selector-popover') || e.target.closest('.model-selector-wrapper')) {
          return;
        }
        onStartDrag(e);
      }}
      style={{ 
        cursor: isPanel && onStartDrag ? (isDragging ? 'grabbing' : 'grab') : 'default',
        userSelect: 'none'
      }}
    >
      <div className="chat-header-left">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>
      <div className="chat-header-center">
        <ModelSelector
          modelBtnRef={modelBtnRef}
          effectiveModelName={selectedModel}
          showDropdown={showModelDropdown}
          models={availableModels}
          selectedModel={selectedModel}
          loadingModels={loadingModels}
          providerConfigs={providerConfigs}
          onToggle={onToggleDropdown}
          onSelect={onSelectModel}
        />
        <div className="model-selector-wrapper" style={{ position: 'relative', marginLeft: '6px' }}>
          <button
            className="model-selector-btn"
            onClick={(e) => { e.stopPropagation(); setShowManifestoDropdown(!showManifestoDropdown); }}
            style={{ gap: '4px', padding: '3px 8px', fontSize: '0.65rem' }}
          >
            <span>📋</span>
            <span className={`model-selector-name ${!activeManifesto.name ? 'no-manifesto' : ''}`}>{activeManifesto.name || 'Scegli manifesto'}</span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
          {showManifestoDropdown && (
            <div className="model-selector-popover" style={{ left: '0', transform: 'none', minWidth: '180px' }}>
              {manifestos.length === 0 && <div className="model-selector-option disabled">Nessun manifesto</div>}
              {manifestos.map(m => (
                <div
                  key={m.path}
                  className={`model-selector-option ${activeManifesto.name === m.name ? 'selected' : ''}`}
                  onClick={(e) => { e.stopPropagation(); onSelectManifesto(m); }}
                >
                  📋 {m.name}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="chat-header-right">
        {onCopyAll && (
          <button
            className={`chat-header-btn ${copiedAll ? 'copied' : ''}`}
            onClick={handleCopyAll}
            title="Copia l'intera conversazione negli appunti"
            style={{
              gap: '4px',
              fontSize: '0.72rem',
              padding: '3px 8px',
              background: copiedAll ? 'rgba(74, 222, 128, 0.15)' : 'rgba(255,255,255,0.05)',
              color: copiedAll ? '#4ade80' : 'var(--text-muted, #8b8fa3)',
              border: copiedAll ? '1px solid rgba(74, 222, 128, 0.3)' : '1px solid rgba(255,255,255,0.08)',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              transition: 'all 0.2s ease'
            }}
          >
            {copiedAll ? '✓ Copiato!' : '📋 Copia Tutto'}
          </button>
        )}
        {onOpenConfig && (
          <button className="chat-header-btn" onClick={(e) => { e.stopPropagation(); onOpenConfig(); }} title="Configurazione completa">
            <Cpu size={14} />
          </button>
        )}
        {onClose && (
          <button className="chat-header-btn" onClick={(e) => { e.stopPropagation(); onClose(); }} title="Riduci in basso nel dock">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M5 12h14" />
            </svg>
          </button>
        )}
        {onClose && (
          <button className="chat-close-btn" onClick={(e) => { e.stopPropagation(); onClose(); }} title="Chiudi">✕</button>
        )}
      </div>
    </div>
  );
}