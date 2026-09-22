// =============================================================================
// Parser difensivo della risposta MCP kicad_board_read → PcbBoardModel
// Gestisce campi mancanti, Y-flip (KiCad y cresce verso il basso) e default.
// =============================================================================

import type {
  Point,
  Pad,
  Footprint,
  Track,
  Via,
  OutlinePath,
  PcbBoardModel,
} from '../types/pcb';

/** Punto di default se i campi non sono numeri validi. */
const DEFAULT_POINT: Point = { x: 0, y: 0 };

/** Coerzi a numero finito, altrimenti fallback. */
function toFinite(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : parseFloat(String(value));
  return Number.isFinite(n) ? n : fallback;
}

/** Coerzi un punto da oggetto arbitrario. */
function parsePoint(raw: unknown): Point {
  if (raw && typeof raw === 'object') {
    const obj = raw as Record<string, unknown>;
    return { x: toFinite(obj.x, 0), y: toFinite(obj.y, 0) };
  }
  return { ...DEFAULT_POINT };
}

/** Coerzi un pad da oggetto arbitrario. */
function parsePad(raw: unknown): Pad {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const shapeRaw = String(obj.shape ?? '').toLowerCase();
  const typeRaw = String(obj.type ?? '').toLowerCase();

  return {
    id: String(obj.id ?? obj.number ?? ''),
    position: parsePoint(obj.position),
    width: toFinite(obj.width, 1.0),
    height: toFinite(obj.height, 1.0),
    shape: (['circle', 'rect', 'oval'].includes(shapeRaw) ? shapeRaw : 'circle') as Pad['shape'],
    type: (['thru_hole', 'smd', 'np_thru_hole'].includes(typeRaw)
      ? typeRaw
      : 'smd') as Pad['type'],
    netName: obj.netName != null && String(obj.netName).trim() !== ''
      ? String(obj.netName)
      : null,
  };
}

/** Coerzi un footprint da oggetto arbitrario. */
function parseFootprint(raw: unknown): Footprint {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const layerRaw = String(obj.layer ?? '').toUpperCase();

  // Supporto sia schema classico {position:{x,y}, pads:[...]} sia schema
  // backend sigma_kicad_lab {x_mm, y_mm, side, width_mm, height_mm}.
  let position: Point;
  if (obj.position && typeof obj.position === 'object') {
    position = parsePoint(obj.position);
  } else {
    position = { x: toFinite(obj.x_mm ?? obj.x, 0), y: toFinite(obj.y_mm ?? obj.y, 0) };
  }

  let pads: Pad[] = Array.isArray(obj.pads)
    ? (obj.pads as unknown[]).map((p) => parsePad(p))
    : [];

  // Se il backend non espone pad ma fornisce dimensioni del corpo, sintetizzo
  // un unico pad rettangolare centrato sull'origine locale così che la canvas
  // mostri comunque il componente.
  if (pads.length === 0) {
    const w = toFinite(obj.width_mm ?? obj.width, 2.0);
    const h = toFinite(obj.height_mm ?? obj.height, 1.5);
    pads = [{
      id: '1',
      position: { x: 0, y: 0 },
      width: w,
      height: h,
      shape: 'rect',
      type: 'smd',
      netName: null,
    }];
  }

  return {
    reference: String(obj.reference ?? obj.designator ?? ''),
    value: String(obj.value ?? ''),
    footprintName: String(obj.footprintName ?? obj.name ?? obj.footprint ?? ''),
    position,
    rotation: toFinite(obj.rotation, 0),
    layer: (layerRaw === 'B.CU' || String(obj.side).toUpperCase() === 'B'
      ? 'B.Cu'
      : 'F.Cu') as Footprint['layer'],
    pads,
  };
}

/** Coerzi una track da oggetto arbitrario. */
function parseTrack(raw: unknown): Track {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const layerRaw = String(obj.layer ?? '').toUpperCase();

  return {
    start: parsePoint(obj.start),
    end: parsePoint(obj.end),
    netName: obj.netName != null && String(obj.netName).trim() !== ''
      ? String(obj.netName)
      : null,
    width: toFinite(obj.width, 0.25),
    layer: (layerRaw === 'B.CU' ? 'B.Cu' : 'F.Cu') as Track['layer'],
  };
}

/** Coerzi una via da oggetto arbitrario. */
function parseVia(raw: unknown): Via {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;

  return {
    position: parsePoint(obj.position),
    drillDiameter: toFinite(obj.drillDiameter ?? obj.diameter, 0.3),
    padDiameter: toFinite(obj.padDiameter, 0.8),
    netName: obj.netName != null && String(obj.netName).trim() !== ''
      ? String(obj.netName)
      : null,
  };
}

/** Coerzi l'outline da oggetto arbitrario. */
function parseOutline(raw: unknown): OutlinePath | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  if (Array.isArray(obj.points) && obj.points.length >= 2) {
    return { points: obj.points.map((p) => parsePoint(p)) };
  }
  return null;
}

/**
 * Applica il Y-flip a un punto: KiCad ha l'asse y crescente verso il basso,
 * mentre lo schermo SVG ha y crescente verso il basso ma l'origine in alto a
 * sinistra. Per mantenere la board orientata correttamente rispetto all'utente
 * si inverte y rispetto al centro della board.
 */
function flipY(point: Point, boardHeightMm: number): Point {
  return { x: point.x, y: boardHeightMm - point.y };
}

/**
 * Converte la risposta JSON del tool MCP `kicad_board_read` in un modello
 * PcbBoardModel coerente e pronto per il rendering SVG.
 *
 * @param raw - Risposta grezza (oggetto arbitrario, potenzialmente incompleta).
 * @returns Modello di board con default sensati e Y-flip applicato.
 */
export function parseKicadBoardResponse(raw: unknown): PcbBoardModel {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;

  const boardObj = (obj.board && typeof obj.board === 'object'
    ? obj.board
    : {}) as Record<string, unknown>;
  const width = toFinite(obj.width ?? obj.boardWidth ?? boardObj.width_mm, 100);
  const height = toFinite(obj.height ?? obj.boardHeight ?? boardObj.height_mm, 80);

  // Il backend sigma_kicad_lab espone i componenti in `components` (con x_mm,
  // y_mm, side) invece che in `footprints`; supporto entrambi gli schemi.
  const rawFootprints: unknown[] = Array.isArray(obj.footprints)
    ? obj.footprints
    : Array.isArray(obj.components)
      ? obj.components
      : [];

  const footprints: Footprint[] = rawFootprints.map((f) => {
    const fp = parseFootprint(f);
    // Y-flip su posizione e pad
    fp.position = flipY(fp.position, height);
    fp.pads = fp.pads.map((p) => ({ ...p, position: flipY(p.position, height) }));
    return fp;
  });

  const tracks: Track[] = Array.isArray(obj.tracks)
    ? obj.tracks.map((t) => {
        const tr = parseTrack(t);
        tr.start = flipY(tr.start, height);
        tr.end = flipY(tr.end, height);
        return tr;
      })
    : [];

  const vias: Via[] = Array.isArray(obj.vias)
    ? obj.vias.map((v) => {
        const via = parseVia(v);
        via.position = flipY(via.position, height);
        return via;
      })
    : [];

  let outline = parseOutline(obj.outline ?? obj.edgeCuts);
  if (outline) {
    outline.points = outline.points.map((p) => flipY(p, height));
  }

  return {
    projectName: String(obj.projectName ?? obj.name ?? 'Progetto sconosciuto'),
    filePath: String(obj.filePath ?? obj.file ?? ''),
    width,
    height,
    footprints,
    tracks,
    vias,
    outline,
  };
}
