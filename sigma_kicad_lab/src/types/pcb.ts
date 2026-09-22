// =============================================================================
// Tipi TypeScript per il modello di board KiCad (Fase 1 — read-only)
// =============================================================================

/** Punto 2D in millimetri. */
export interface Point {
  x: number;
  y: number;
}

/** Pad di un footprint. */
export interface Pad {
  /** Identificativo numerico del pad (es. "1", "A1"). */
  id: string;
  /** Posizione in mm rispetto all'origine della board. */
  position: Point;
  /** Larghezza in mm. */
  width: number;
  /** Altezza in mm. */
  height: number;
  /** Forma: 'circle' | 'rect' | 'oval'. */
  shape: 'circle' | 'rect' | 'oval';
  /** Tipo di pad: 'thru_hole' | 'smd' | 'np_thru_hole'. */
  type: 'thru_hole' | 'smd' | 'np_thru_hole';
  /** Nome della net collegata, o null se non collegato. */
  netName: string | null;
}

/** Footprint (componente) sulla board. */
export interface Footprint {
  /** Reference designatore (es. "R1", "U3"). */
  reference: string;
  /** Valore del componente (es. "10kΩ", "STM32F4"). */
  value: string;
  /** Nome footprint KiCad (es. "Resistor_SMD:R_0805"). */
  footprintName: string;
  /** Posizione in mm. */
  position: Point;
  /** Rotazione in gradi. */
  rotation: number;
  /** Layer di posizionamento: 'F.Cu' | 'B.Cu'. */
  layer: 'F.Cu' | 'B.Cu';
  /** Pads del footprint. */
  pads: Pad[];
}

/** Traccia (track) tra due punti. */
export interface Track {
  /** Punto di partenza in mm. */
  start: Point;
  /** Punto di arrivo in mm. */
  end: Point;
  /** Nome della net, o null se non assegnata. */
  netName: string | null;
  /** Larghezza in mm. */
  width: number;
  /** Layer: 'F.Cu' | 'B.Cu'. */
  layer: 'F.Cu' | 'B.Cu';
}

/** Via (passante) tra due layer. */
export interface Via {
  /** Posizione in mm. */
  position: Point;
  /** Diametro del foro in mm. */
  drillDiameter: number;
  /** Diametro del pad in mm. */
  padDiameter: number;
  /** Nome della net, o null. */
  netName: string | null;
}

/** Percorso outline (contorno) della board. */
export interface OutlinePath {
  /** Punti del contorno in mm. */
  points: Point[];
}

/** Modello completo della board KiCad. */
export interface PcbBoardModel {
  /** Nome del progetto. */
  projectName: string;
  /** Nome file (basename). */
  filePath: string;
  /** Larghezza board in mm. */
  width: number;
  /** Altezza board in mm. */
  height: number;
  /** Footprint presenti sulla board. */
  footprints: Footprint[];
  /** Tracce (tracks). */
  tracks: Track[];
  /** Vie (vias). */
  vias: Via[];
  /** Contorno della board. */
  outline: OutlinePath | null;
}

/** Stato di un layer nel viewer. */
export type LayerKey = 'Edge.Cuts' | 'F.Cu' | 'B.Cu' | 'F.SilkS' | 'B.SilkS';

/** Mappa visibilità layer. */
export interface LayerVisibility {
  [key: string]: boolean;
}
