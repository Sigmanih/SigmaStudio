// =============================================================================
// PartAddPanel — pannello laterale per aggiungere una footprint alla board
// Chiamata MCP: kicad_add_part (POST /api/mcp/kicad_add_part)
// Dopo successo, richiama il refresh della board dal genitore.
// =============================================================================
import { useState } from 'react';
import { PlusCircle, X, PackageOpen } from 'lucide-react';

export interface PartAddPanelProps {
  /** Percorso del progetto .kicad_pcb (o nome) da aggiornare. */
  projectPath: string;
  /** Richiama il refresh della board dopo l'aggiunta. */
  onAdded: () => void;
  /** Chiudi pannello. */
  onClose: () => void;
}

interface FormState {
  library: string;
  footprint: string;
  reference: string;
  value: string;
  xMm: number;
  yMm: number;
  rotationDeg: number;
  netPerPad: string; // JSON semplice {"1":"GND"}
}

const DEFAULT_FORM: FormState = {
  library: 'Resistor_SMD',
  footprint: 'R_0805_2012Metric',
  reference: '',
  value: '10kΩ',
  xMm: 10,
  yMm: 10,
  rotationDeg: 0,
  netPerPad: '{"1": "GND"}',
};

export default function PartAddPanel({ projectPath, onAdded, onClose }: PartAddPanelProps) {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleAdd() {
    if (!projectPath) {
      setError('Nessun progetto aperto');
      return;
    }
    let netPerPad: Record<string, string> | null = null;
    try {
      const parsed = JSON.parse(form.netPerPad || '{}');
      if (parsed && typeof parsed === 'object') netPerPad = parsed as Record<string, string>;
    } catch {
      setError('net_per_pad non è un JSON valido');
      return;
    }

    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await fetch('/api/mcp/kicad_add_part', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: projectPath,
          library: form.library.trim(),
          footprint: form.footprint.trim(),
          reference: form.reference.trim(),
          value: form.value.trim(),
          x_mm: Number(form.xMm),
          y_mm: Number(form.yMm),
          rotation: Number(form.rotationDeg),
          net_per_pad: netPerPad,
        }),
      });
      const data = (await res.json()) as { success?: boolean; error?: string };
      if (!res.ok || !data.success) {
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }
      setOk('Componente aggiunto con successo');
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="part-add-panel">
      <header className="part-add-panel__head">
        <div className="part-add-panel__title">
          <PackageOpen size={16} />
          Aggiungi footprint
        </div>
        <button type="button" className="part-add-panel__close" onClick={onClose} aria-label="Chiudi">
          <X size={14} />
        </button>
      </header>

      <form
        className="part-add-panel__body"
        onSubmit={(e) => {
          e.preventDefault();
          void handleAdd();
        }}
      >
        <label className="field">
          <span>Libreria</span>
          <input value={form.library} onChange={(e) => update('library', e.target.value)} placeholder="Resistor_SMD" />
        </label>

        <label className="field">
          <span>Footprint</span>
          <input value={form.footprint} onChange={(e) => update('footprint', e.target.value)} placeholder="R_0805_2012Metric" />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Reference</span>
            <input value={form.reference} onChange={(e) => update('reference', e.target.value)} placeholder="R1" />
          </label>
          <label className="field">
            <span>Valore</span>
            <input value={form.value} onChange={(e) => update('value', e.target.value)} placeholder="10kΩ" />
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span>X (mm)</span>
            <input type="number" step="0.1" value={form.xMm} onChange={(e) => update('xMm', Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Y (mm)</span>
            <input type="number" step="0.1" value={form.yMm} onChange={(e) => update('yMm', Number(e.target.value))} />
          </label>
        </div>

        <label className="field">
          <span>Rotazione (°)</span>
          <input type="number" step="5" value={form.rotationDeg} onChange={(e) => update('rotationDeg', Number(e.target.value))} />
        </label>

        <label className="field">
          <span>Net per pad (JSON)</span>
          <textarea rows={2} value={form.netPerPad} onChange={(e) => update('netPerPad', e.target.value)} placeholder='{"1": "GND"}' />
        </label>

        {error && <div className="part-add-panel__msg part-add-panel__msg--err">{error}</div>}
        {ok && !busy && <div className="part-add-panel__msg part-add-panel__msg--ok">{ok}</div>}

        <button type="submit" className="btn btn--primary" disabled={busy}>
          <PlusCircle size={14} />
          {busy ? 'Aggiunta…' : 'Aggiungi alla board'}
        </button>
      </form>
    </aside>
  );
}
