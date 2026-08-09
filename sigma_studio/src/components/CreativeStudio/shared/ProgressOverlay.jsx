import React from 'react';

export default function ProgressOverlay({ label, progress, status, onCancel }) {
  const value = typeof progress === 'number' ? Math.max(0, Math.min(100, progress)) : undefined;

  return (
    <div className="cs-overlay cs-fade-in">
      <div className="cs-progress-card">
        <div className="cs-spinner" />
        <div className="cs-progress-title">{label || 'Elaborazione'}</div>
        <div className="cs-progress-text">{status || 'In corso...'}</div>

        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px', color: 'var(--text-dim)' }}>
            <span>Avanzamento</span>
            <span>{value === undefined ? '—' : `${Math.round(value)}%`}</span>
          </div>
          <div className="cs-progress-bar">
            {/* Senza percentuale nota si mostra una barra indeterminata anziché 0% */}
            <div
              className={`cs-progress-fill ${value === undefined ? 'indeterminate' : ''}`}
              style={value === undefined ? undefined : { width: `${value}%` }} />
          </div>
        </div>

        {onCancel && (
          <button className="cs-action-secondary" onClick={onCancel} style={{ marginTop: '16px' }}>
            Annulla
          </button>
        )}
      </div>
    </div>
  );
}
