// =============================================================================
// Hook useSvgViewport — gestione viewBox, pan, zoom e fit-to-board
// Operando in unità millimetriche (mm) per coerenza col modello di board.
// =============================================================================

import { useState, useCallback, useMemo } from 'react';
import type { PcbBoardModel } from '../types/pcb';
import { ZOOM_LIMITS } from '../lib/constants';

/** Rappresenta il viewport SVG in mm. */
export interface ViewBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Stato completo del viewport. */
export interface SvgViewportState {
  viewBox: ViewBox;
  zoom: number; // 1 = fit-to-board, >1 zoom in, <1 zoom out
  /** Zoom in di un fattore (default 1.2). */
  zoomIn: (factor?: number) => void;
  /** Zoom out di un fattore (default 1/1.2). */
  zoomOut: (factor?: number) => void;
  /** Fit-to-board: centra e scala per mostrare tutta la board. */
  fitToBoard: () => void;
  /** Pan relativo in mm (dx, dy positivi = spostamento a destra/basso). */
  pan: (dxMm: number, dyMm: number) => void;
  /** Imposta il centro del viewport su un punto in mm. */
  centerOn: (xMm: number, yMm: number) => void;
  /** Adatta il viewBox alla bounding box di una selezione (in mm). */
  zoomToSelection: (bbox: { x: number; y: number; width: number; height: number }) => void;
}

/** Calcola il viewBox fit-to-board con un margine del 10%. */
function computeFitViewBox(board: PcbBoardModel): ViewBox {
  const margin = Math.max(board.width, board.height) * 0.1;
  return {
    x: -margin,
    y: -margin,
    width: board.width + margin * 2,
    height: board.height + margin * 2,
  };
}

/**
 * Hook per la gestione del viewport SVG di un canvas PCB.
 *
 * @param board - Modello della board (può essere null se non caricata).
 */
export function useSvgViewport(board: PcbBoardModel | null): SvgViewportState {
  const [viewBox, setViewBox] = useState<ViewBox>(() =>
    board ? computeFitViewBox(board) : { x: 0, y: 0, width: 100, height: 80 }
  );

  // Zoom relativo rispetto al fit-to-board (width fit / width corrente)
  const zoom = useMemo(() => {
    if (!board) return 1;
    const fitWidth = board.width * 1.2; // margine 10% su entrambi i lati
    return fitWidth / viewBox.width;
  }, [board, viewBox.width]);

  const clampZoom = useCallback(
    (newZoom: number): number => {
      if (newZoom < ZOOM_LIMITS.min) return ZOOM_LIMITS.min;
      if (newZoom > ZOOM_LIMITS.max) return ZOOM_LIMITS.max;
      return newZoom;
    },
    []
  );

  const zoomIn = useCallback(
    (factor: number = 1.2) => {
      setViewBox((vb) => {
        if (!board) return vb;
        const currentZoom = board.width * 1.2 / vb.width;
        const newZoom = clampZoom(currentZoom * factor);
        // Calcola il nuovo width mantenendo il centro
        const centerX = vb.x + vb.width / 2;
        const centerY = vb.y + vb.height / 2;
        const aspectRatio = vb.height / vb.width;
        const newWidth = (board.width * 1.2) / newZoom;
        const newHeight = newWidth * aspectRatio;
        return {
          x: centerX - newWidth / 2,
          y: centerY - newHeight / 2,
          width: newWidth,
          height: newHeight,
        };
      });
    },
    [board, clampZoom]
  );

  const zoomOut = useCallback(
    (factor: number = 1 / 1.2) => {
      setViewBox((vb) => {
        if (!board) return vb;
        const currentZoom = board.width * 1.2 / vb.width;
        const newZoom = clampZoom(currentZoom * factor);
        const centerX = vb.x + vb.width / 2;
        const centerY = vb.y + vb.height / 2;
        const aspectRatio = vb.height / vb.width;
        const newWidth = (board.width * 1.2) / newZoom;
        const newHeight = newWidth * aspectRatio;
        return {
          x: centerX - newWidth / 2,
          y: centerY - newHeight / 2,
          width: newWidth,
          height: newHeight,
        };
      });
    },
    [board, clampZoom]
  );

  const fitToBoard = useCallback(() => {
    if (board) {
      setViewBox(computeFitViewBox(board));
    }
  }, [board]);

  const pan = useCallback((dxMm: number, dyMm: number) => {
    setViewBox((vb) => ({ ...vb, x: vb.x - dxMm, y: vb.y - dyMm }));
  }, []);

  const centerOn = useCallback(
    (xMm: number, yMm: number) => {
      setViewBox((vb) => ({
        ...vb,
        x: xMm - vb.width / 2,
        y: yMm - vb.height / 2,
      }));
    },
    []
  );

  const zoomToSelection = useCallback(
    (bbox: { x: number; y: number; width: number; height: number }) => {
      if (!board) return;
      // Margine del 20% attorno alla bounding box di selezione
      const margin = Math.max(bbox.width, bbox.height) * 0.2 + 1;
      const x = bbox.x - margin;
      const y = bbox.y - margin;
      const w = bbox.width + margin * 2;
      const h = bbox.height + margin * 2;
      // Mantieni l'aspect ratio del viewBox attuale
      const currentAspect = viewBox.height / viewBox.width;
      let finalW = w;
      let finalH = h;
      if (finalH / finalW < currentAspect) {
        finalW = finalH / currentAspect;
      } else {
        finalH = finalW * currentAspect;
      }
      setViewBox({
        x: bbox.x + bbox.width / 2 - finalW / 2,
        y: bbox.y + bbox.height / 2 - finalH / 2,
        width: finalW,
        height: finalH,
      });
    },
    [board, viewBox]
  );

  return { viewBox, zoom, zoomIn, zoomOut, fitToBoard, pan, centerOn, zoomToSelection };
}
