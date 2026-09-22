import { useCallback, useEffect, useState } from 'react';
import { Save, X } from 'lucide-react';
import type { FootprintData } from '../types/pcb';

interface PropertiesPanelProps {
  footprint: FootprintData | null;
  onSave: (ref: string, value: string) => Promise<void>;
  onClose: () => void;
}

export function PropertiesPanel({ footprint, onSave, onClose }: PropertiesPanelProps) {
  const [reference, setReference] = useState('');
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (footprint) {
      setReference(footprint.reference);
      setValue(footprint.value ?? '');
      setError(null);
    }
  }, [footprint]);

  const handleSave = useCallback(async () => {
    if (!footprint || saving) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(footprint.reference, value);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore di salvataggio');
    } finally {
      setSaving(false);
    }
  }, [footprint, saving, value, onSave]);

  if (!footprint) return null;

  return (
    <div className="properties-panel" role="dialog" aria-label="Proprietà footprint">
      <div className="properties-panel__header">
        <span className="properties-panel__title">Proprietà</span>
        <button type="button" className="properties-panel__close" onClick={onClose} aria-label="Chiudi">
          <X size={14} />
        </button>
      </div>

      <div className="properties-panel__body">
        <label className="properties-panel__field">
          <span className="properties-panel__label">Riferimento</span>
          <input
            type="text"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            disabled
            aria-label="Riferimento footprint"
          />
        </label>

        <label className="properties-panel__field">
          <span className="properties-panel__label">Valore</span>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="es. 10kΩ, 100nF, ATMEGA328P"
            aria-label="Valore footprint"
          />
        </label>

        <div className="properties-panel__meta">
          <span>Layer: {footprint.layer}</span>
          <span>Rotazione: {footprint.rotation}°</span>
        </div>

        {error && <p className="properties-panel__error">{error}</p>}

        <button
          type="button"
          className="properties-panel__save"
          onClick={handleSave}
          disabled={saving || reference === footprint.reference}
        >
          <Save size={14} />
          {saving ? 'Salvataggio…' : 'Salva modifiche'}
        </button>
      </div>
    </div>
  );
}
