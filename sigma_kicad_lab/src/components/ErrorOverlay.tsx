// =============================================================================
// ErrorOverlay — overlay per errori di caricamento e stato vuoto (Fase 1)
// Mostra un messaggio centrale con icona, titolo e descrizione.
// Stile: bg semi-trasparente #0f172a/95%, border #334155, radius 8px
// =============================================================================
import { AlertTriangle, FolderOpen } from 'lucide-react';

export interface ErrorOverlayProps {
  /** Tipo di stato: errore o vuoto. */
  variant?: 'error' | 'empty';
  /** Messaggio principale (titolo). */
  title: string;
  /** Messaggio secondario (descrizione). */
  description?: string;
  /** Callback opzionale per il pulsante d'azione. */
  onAction?: () => void;
  /** Etichetta del pulsante d'azione. */
  actionLabel?: string;
}

export function ErrorOverlay({
  variant = 'empty',
  title,
  description,
  onAction,
  actionLabel,
}: ErrorOverlayProps) {
  const Icon = variant === 'error' ? AlertTriangle : FolderOpen;
  const iconColor = variant === 'error' ? '#ef4444' : '#00d4ff';

  return (
    <div className="pcb-error-overlay">
      <div className="pcb-error-overlay__card">
        <Icon size={48} style={{ color: iconColor, marginBottom: 16 }} />
        <h3 className="pcb-error-overlay__title">{title}</h3>
        {description && (
          <p className="pcb-error-overlay__desc">{description}</p>
        )}
        {onAction && actionLabel && (
          <button
            type="button"
            className="pcb-error-overlay__btn"
            onClick={onAction}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorOverlay;
