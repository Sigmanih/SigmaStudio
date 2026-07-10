import React from 'react';
import { Cpu, ChevronDown, Check, Loader } from 'lucide-react';
import { PROVIDER_COLORS, getProviderForModel } from './modelProviderMap';

export default function ModelSelector({
  modelBtnRef, effectiveModelName, showDropdown, models,
  selectedModel, loadingModels, providerConfigs, onToggle, onSelect, onRefresh
}) {
  return (
    <div className="model-selector-wrapper" ref={modelBtnRef}>
      <button className={`model-selector-btn ${!effectiveModelName ? 'no-model' : ''}`} onClick={onToggle}>
        <Cpu size={12} />
        <span className="model-selector-name">{effectiveModelName || 'Scegli modello'}</span>
        <ChevronDown size={10} className={`model-selector-chevron ${showDropdown ? 'open' : ''}`} />
      </button>
      {showDropdown && (
        <div className="model-selector-popover">
          {loadingModels && (
            <div className="model-selector-loading"><Loader size={12} className="spin" /> Caricamento...</div>
          )}
          {!loadingModels && models.length === 0 && (
            <div className="model-selector-empty">Nessun modello disponibile</div>
          )}
          {!loadingModels && models.map(m => {
            const provider = getProviderForModel(m.name, providerConfigs);
            const colors = PROVIDER_COLORS[provider] || PROVIDER_COLORS.ollama;
            return (
              <button
                key={m.name}
                className={`model-selector-option ${selectedModel === m.name ? 'active' : ''}`}
                onClick={() => onSelect(m.name)}
              >
                <span
                  className="model-selector-provider-dot"
                  style={{ backgroundColor: colors.color }}
                  title={provider}
                />
                <span className="model-selector-opt-name">{m.name}</span>
                <span className="model-selector-provider-badge" style={{ backgroundColor: colors.bg, color: colors.color }}>
                  {provider}
                </span>
                {m.size && <span className="model-selector-opt-size">{m.size === 'API' ? m.size : m.size + 'GB'}</span>}
                {selectedModel === m.name && <Check size={12} className="model-selector-check" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}