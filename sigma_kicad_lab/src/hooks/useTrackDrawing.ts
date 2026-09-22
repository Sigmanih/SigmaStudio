// =============================================================================
// useTrackDrawing — hook per la tracciatura interattiva di tracce sulla canvas
// Modalità 'track': click-drag per tracciare un segmento (kicad_add_track)
// Modalità 'via':   click singolo per piazzare una via     (kicad_add_via)
// Il genitore fornisce: projectPath, layer attivo, net corrente, larghezza,
// e il callback onBoardChanged per il refresh.
// =============================================================================
import { useCallback, useRef, useState } from 'react';
import type { Point } from '../types/pcb';

export type DrawMode = 'none' | 'track' | 'via';

export interface TrackDraft {
  start: Point;
  current: Point;
}

export interface UseTrackDrawingOptions {
  projectPath: string;
  /** Layer di rame attivo ('F.Cu' | 'B.Cu'). */
  layer: 'F.Cu' | 'B.Cu';
  /** Net corrente (stringa vuota = non assegnata). */
  netName: string;
  /** Larghezza traccia in mm. */
  trackWidthMm: number;
  /** Diametro pad via in mm. */
  viaSizeMm?: number;
  /** Foro via in mm. */
  viaDrillMm?: number;
  /** Richiama il refresh della board dopo una modifica riuscita. */
  onBoardChanged: () => void | Promise<void>;
}

export interface UseTrackDrawingResult {
  mode: DrawMode;
  setMode: (m: DrawMode) => void;
  draft: TrackDraft | null;
  /** Punto di inizio del drag in mm, o null. */
  anchor: Point | null;
  busy: boolean;
  error: string | null;
  lastOk: string | null;
  startDrag: (p: Point) => void;
  moveDrag: (p: Point) => void;
  endDrag: () => Promise<void>;
  placeVia: (p: Point) => Promise<void>;
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

export function useTrackDrawing(opts: UseTrackDrawingOptions): UseTrackDrawingResult {
  const [mode, setMode] = useState<DrawMode>('none');
  const [anchor, setAnchor] = useState<Point | null>(null);
  const [current, setCurrent] = useState<Point | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<string | null>(null);

  // Evita di inviare tracce degenerate (stesso punto).
  const MIN_LEN_MM = useRef(0.05);

  const startDrag = useCallback((p: Point) => {
    if (mode !== 'track') return;
    setAnchor(p);
    setCurrent(p);
    setError(null);
    setLastOk(null);
  }, [mode]);

  const moveDrag = useCallback((p: Point) => {
    if (mode !== 'track' || !anchor) return;
    setCurrent(p);
  }, [mode, anchor]);

  const endDrag = useCallback(async () => {
    if (mode !== 'track') return;
    const a = anchor;
    const c = current ?? anchor;
    setAnchor(null);
    setCurrent(null);
    if (!a || !c) return;

    const dx = c.x - a.x;
    const dy = c.y - a.y;
    if (Math.hypot(dx, dy) < MIN_LEN_MM.current) {
      // Click senza drag: ignora.
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await postMcp('/api/mcp/kicad_add_track', {
        path: opts.projectPath,
        start: [a.x, a.y],
        end: [c.x, c.y],
        width_mm: opts.trackWidthMm,
        layer: opts.layer,
        net: opts.netName || '',
      });
      setLastOk(`Traccia ${opts.layer} aggiunta (${a.x.toFixed(2)},${a.y.toFixed(2)}) → (${c.x.toFixed(2)},${c.y.toFixed(2)})`);
      await opts.onBoardChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [mode, anchor, current, opts]);

  const placeVia = useCallback(async (p: Point) => {
    if (mode !== 'via') return;
    setBusy(true);
    setError(null);
    try {
      await postMcp('/api/mcp/kicad_add_via', {
        path: opts.projectPath,
        at: [p.x, p.y],
        size_mm: opts.viaSizeMm ?? 0.8,
        drill_mm: opts.viaDrillMm ?? 0.4,
        net: opts.netName || '',
      });
      setLastOk(`Via piazzata a (${p.x.toFixed(2)}, ${p.y.toFixed(2)})`);
      await opts.onBoardChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [mode, opts]);

  const cancel = useCallback(() => {
    setAnchor(null);
    setCurrent(null);
    setError(null);
  }, []);

  const draft: TrackDraft | null = anchor && current ? { start: anchor, current } : null;

  return {
    mode,
    setMode,
    draft,
    anchor,
    busy,
    error,
    lastOk,
    startDrag,
    moveDrag,
    endDrag,
    placeVia,
    cancel,
  };
}
