// =============================================================================
// useFootprintDrag — hook per trascinare una footprint sulla canvas
// Modalità 'move': mousedown su una footprint → drag → mouseup invia
// kicad_update_footprint_position e richiama onBoardChanged.
// Il genitore fornisce: projectPath, footprint selezionata, callback refresh.
// =============================================================================
import { useCallback, useRef, useState } from 'react';
import type { Point, Footprint } from '../types/pcb';

export interface UseFootprintDragOptions {
  projectPath: string;
  /** Footprint attualmente selezionata (null = nessuna). */
  selectedFootprint: Footprint | null;
  /** Richiama il refresh della board dopo una modifica riuscita. */
  onBoardChanged: () => void | Promise<void>;
  /** Callback opzionale per aggiornare lo stato di selezione esterno. */
  onSelect?: (ref: string | null) => void;
}

export interface UseFootprintDragResult {
  /** Se true, il drag è attivo e la canvas deve mostrare la footprint spostata. */
  dragging: boolean;
  /** Offset in mm tra il punto di presa e l'origine della footprint. */
  grabOffset: Point | null;
  /** Posizione corrente (preview) durante il drag, o null. */
  previewPosition: Point | null;
  busy: boolean;
  error: string | null;
  lastOk: string | null;
  /** Da chiamare su mousedown sulla footprint: avvia il drag se è selezionata. */
  startDrag: (fp: Footprint, p: Point) => void;
  /** Da chiamare su mousemove durante il drag. */
  moveDrag: (p: Point) => void;
  /** Da chiamare su mouseup: invia la posizione finale al backend. */
  endDrag: () => Promise<void>;
  /** Annulla il drag corrente senza inviare modifiche. */
  cancel: () => void;
}

async function postMcp(endpoint: string, body: Record<string, unknown>) {
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let data: { success?: boolean; error?: string } | null = null;
  try {
    data = (await res.json()) as { success?: boolean; error?: string };
  } catch {
    // corpo non-JSON
  }
  if (!res.ok || !data?.success) {
    throw new Error(data?.error ?? `HTTP ${res.status}`);
  }
  return data;
}

export function useFootprintDrag(opts: UseFootprintDragOptions): UseFootprintDragResult {
  const [dragging, setDragging] = useState(false);
  const [grabOffset, setGrabOffset] = useState<Point | null>(null);
  const [previewPosition, setPreviewPosition] = useState<Point | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<string | null>(null);

  // Riferimento alla footprint che si sta trascinando (evita stale closure).
  const dragFpRef = useRef<Footprint | null>(null);

  const startDrag = useCallback((fp: Footprint, p: Point) => {
    if (!opts.selectedFootprint || opts.selectedFootprint.reference !== fp.reference) {
      return;
    }
    dragFpRef.current = fp;
    setGrabOffset({ x: p.x - fp.position.x, y: p.y - fp.position.y });
    setPreviewPosition(fp.position);
    setDragging(true);
    setError(null);
    setLastOk(null);
  }, [opts.selectedFootprint]);

  const moveDrag = useCallback((p: Point) => {
    if (!dragging || !grabOffset) return;
    setPreviewPosition({ x: p.x - grabOffset.x, y: p.y - grabOffset.y });
  }, [dragging, grabOffset]);

  const endDrag = useCallback(async () => {
    const fp = dragFpRef.current;
    const pos = previewPosition;
    setDragging(false);
    setGrabOffset(null);
    setPreviewPosition(null);
    dragFpRef.current = null;

    if (!fp || !pos) return;

    // Evita invii degeneri: se la posizione non cambia, non serve chiamare l'API.
    const dx = pos.x - fp.position.x;
    const dy = pos.y - fp.position.y;
    if (Math.hypot(dx, dy) < 0.01) {
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await postMcp('/api/mcp/kicad_update_footprint_position', {
        project: opts.projectPath,
        reference: fp.reference,
        x_mm: pos.x,
        y_mm: pos.y,
      });
      setLastOk(`${fp.reference} spostata a (${pos.x.toFixed(2)}, ${pos.y.toFixed(2)})`);
      await opts.onBoardChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [previewPosition, opts]);

  const cancel = useCallback(() => {
    setDragging(false);
    setGrabOffset(null);
    setPreviewPosition(null);
    dragFpRef.current = null;
    setError(null);
  }, []);

  return {
    dragging,
    grabOffset,
    previewPosition,
    busy,
    error,
    lastOk,
    startDrag,
    moveDrag,
    endDrag,
    cancel,
  };
}
