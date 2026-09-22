// =============================================================================
// PcbStatusBar — barra di stato fissa in basso (Fase 1)
// Altezza 32px, bg #0f172a, testo #94a3b8, font-size 12px
// Campi: Progetto | File | Stato | Zoom | Cursore | DRC
// Layout flex space-between gap 24px; responsive <768px in due righe
// =============================================================================
export interface StatusBarProps {
  project: string;
  file: string;
  statusText?: string;
  zoomPercent: number;
  cursorMm: { x: number; y: number } | null;
}

interface FieldProps {
  label: string;
  value: string;
}

function StatusField({ label, value }: FieldProps) {
  return (
    <div className="pcb-statusbar__field">
      <span className="pcb-statusbar__label">{label}</span>
      <span className="pcb-statusbar__value">{value}</span>
    </div>
  );
}

export function PcbStatusBar({ project, file, zoomPercent, cursorMm, statusText }: StatusBarProps) {
  return (
    <div className="pcb-statusbar">
      <StatusField label="Progetto" value={project || '—'} />
      <StatusField label="File" value={file || '—'} />
      <StatusField label="Stato" value={statusText ?? 'In attesa'} />
      <StatusField label="Zoom" value={`${Math.round(zoomPercent * 100)}%`} />
      <StatusField
        label="Cursore"
        value={cursorMm ? `${cursorMm.x.toFixed(2)}, ${cursorMm.y.toFixed(2)} mm` : '—'}
      />
      <StatusField label="DRC" value="Fase 2" />
    </div>
  );
}

export default PcbStatusBar;
