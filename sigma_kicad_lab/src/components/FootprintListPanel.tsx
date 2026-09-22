// =============================================================================
// FootprintListPanel — pannello laterale con lista footprint, ricerca e
// click-to-select. Ogni voce mostra riferimento, valore, layer e posizione.
// Il click su una voce seleziona la footprint (evidenziata sulla canvas) e
// centra il viewport su di essa tramite il callback onSelect.
// =============================================================================
import { useMemo, useState } from 'react';
import { Search, X, Cpu } from 'lucide-react';
import type { Footprint } from '../types/pcb';

interface Props {
  /** Tutte le footprint della board. */
  footprints: Footprint[];
  /** Reference della footprint attualmente selezionata, o null. */
  selectedRef: string | null;
  /** Callback: l'utente ha cliccato una voce — seleziona e centra. */
  onSelect: (fp: Footprint) => void;
  /** Chiude il pannello. */
  onClose: () => void;
}

export default function FootprintListPanel({
  footprints,
  selectedRef,
  onSelect,
  onClose,
}: Props) {
  const [query, setQuery] = useState('');

  // Filtra in base a riferimento, valore o nome footprint (case-insensitive).
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return footprints;
    return footprints.filter(
      (fp) =>
        fp.reference.toLowerCase().includes(q) ||
        fp.value.toLowerCase().includes(q) ||
        fp.footprintName.toLowerCase().includes(q)
    );
  }, [footprints, query]);

  // Ordina per riferimento (R1, R2, … U1, …) in modo deterministico.
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => a.reference.localeCompare(b.reference, undefined, { numeric: true }));
  }, [filtered]);

  return (
    <aside className="fp-panel">
      {/* Header */}
      <div className="fp-panel__header">
        <div className="fp-panel__title">
          <Cpu size={16} />
          <span>Footprint</span>
          <span className="fp-panel__count">{sorted.length}</span>
        </div>
        <button
          type="button"
          className="fp-panel__close"
          onClick={onClose}
          title="Chiudi pannello"
        >
          <X size={16} />
        </button>
      </div>

      {/* Ricerca */}
      <div className="fp-panel__search">
        <Search size={14} className="fp-panel__search-icon" />
        <input
          type="text"
          className="fp-panel__input"
          placeholder="Cerca ref, valore…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        {query && (
          <button
            type="button"
            className="fp-panel__clear"
            onClick={() => setQuery('')}
            title="Pulisci ricerca"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Lista */}
      <ul className="fp-panel__list">
        {sorted.length === 0 ? (
          <li className="fp-panel__empty">Nessuna footprint trovata</li>
        ) : (
          sorted.map((fp) => {
            const isSel = selectedRef === fp.reference;
            return (
              <li
                key={fp.reference}
                className={`fp-item ${isSel ? 'fp-item--selected' : ''}`}
                onClick={() => onSelect(fp)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(fp);
                  }
                }}
              >
                <div className="fp-item__main">
                  <span className="fp-item__ref">{fp.reference}</span>
                  <span className="fp-item__value">{fp.value || '—'}</span>
                </div>
                <div className="fp-item__meta">
                  <span className={`fp-item__layer fp-item__layer--${fp.layer === 'F.Cu' ? 'top' : 'bot'}`}>
                    {fp.layer === 'F.Cu' ? 'TOP' : 'BOT'}
                  </span>
                  <span className="fp-item__pos">
                    {fp.position.x.toFixed(1)}, {fp.position.y.toFixed(1)} mm
                  </span>
                </div>
              </li>
            );
          })
        )}
      </ul>
    </aside>
  );
}
