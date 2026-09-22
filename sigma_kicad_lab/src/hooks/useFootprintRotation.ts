// =============================================================================
// useFootprintRotation — hook per ruotare una footprint selezionata di 90°.
// Chiamando `rotate()` si invia al backend la nuova rotazione (attuale + 90°)
// e si richiama onBoardChanged. Il genitore fornisce: projectPath, footprint
// selezionata, callback refresh.
// =============================================================================
import { useCallback, useState } from 'react';
import type { Footprint } from '../types/pcb';

export interface UseFootprintRotationOptions {
  projectPath: string;
  /** Footprint attualmente selezionata (null = nessuna). */
  selectedFootprint: Footprint | null;
  /** Richiama il refresh della board dopo una modifica riuscita. */
  onBoardChanged: () => void | Promise<void>;
}

export interface UseFootprintRotationResult {
  busy: boolean;
  error: string | null;
  lastOk: string | null;
  /** Ruota la footprint selezionata di `degrees` in senso orario (90/180/270). */
  rotate: (degrees?: 90 | 180 | 270) => Promise<void>;
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

export function useFootprintRotation(
  opts: UseFootprintRotationOptions,
): UseFootprintRotationResult {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<string | null>(null);

  const rotate = useCallback(async (degrees: 90 | 180 | 270 = 90) => {
    const fp = opts.selectedFootprint;
    if (!fp) return;

    // Nuova rotazione: attuale + angolo richiesto, normalizzata in [0, 360)
    const newRot = ((fp.rotation ?? 0) + degrees) % 360;

    setBusy(true);
    setError(null);
    try {
      await postMcp('/api/mcp/kicad_update_footprint_position', {
        project: opts.projectPath,
        reference: fp.reference,
        x_mm: fp.position.x,
        y_mm: fp.position.y,
        rotation: newRot,
      });
      setLastOk(`${fp.reference} ruotata a ${newRot}°`);
      await opts.onBoardChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [opts.selectedFootprint, opts.projectPath, opts.onBoardChanged]);

  return { busy, error, lastOk, rotate };
}
