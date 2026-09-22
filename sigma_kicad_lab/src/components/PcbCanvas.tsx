// =============================================================================
// PcbCanvas — canvas SVG principale con pan/zoom, layer e tooltip hover
// Il canvas è il contenitore assoluto del viewport: riceve board + viewBox
// (in mm) dal genitore, applica i layer in ordine di rendering corretto e
// espone gli eventi mouse per pan/zoom. Il SelectionTooltip viene renderizzato
// qui dentro come overlay assoluto, clampato nel viewport.
// =============================================================================
import { useRef } from 'react';
import type { PcbBoardModel, LayerVisibility, Footprint, Pad, Point } from '../types/pcb';
import BoardOutlineLayer from './BoardOutlineLayer';
import FootprintLayer from './FootprintLayer';
import TrackLayer from './TrackLayer';
import ViaLayer from './ViaLayer';
import GridOverlay from './GridOverlay';
import SelectionTooltip, { type TooltipData } from './SelectionTooltip';

interface Props {
  board: PcbBoardModel;
  viewBox: { x: number; y: number; w: number; h: number };
  layerVisibility: LayerVisibility;
  gridVisible: boolean;
  gridStep: number;
  onPanStart?: (e: React.MouseEvent) => void;
  onPanMove?: (e: React.MouseEvent) => void;
  onPanEnd?: () => void;
  onWheel?: (e: React.WheelEvent) => void;

  // Tooltip (il debounce è interno a SelectionTooltip; qui passiamo solo i dati)
  tooltipData: TooltipData | null;
  /** Posizione mouse in px relative al container canvas. */
  mouseX: number;
  mouseY: number;
  onMouseMoveCanvas?: (e: React.MouseEvent) => void;
  onPadEnter?: (pad: Pad, fp: Footprint) => void;
  onPadLeave?: () => void;

  // Drag-to-move footprint (task #2)
  /** Reference della footprint in drag, o null. */
  draggingRef?: string | null;
  /** Posizione corrente (mm) della footprint in drag per il preview. */
  dragPreviewPosition?: Point | null;
  /** Da chiamare su mousedown sulla footprint selezionata. */
  onFootprintDragStart?: (fp: Footprint, p: Point) => void;
  /** Da chiamare su mousemove durante il drag. */
  onFootprintDragMove?: (p: Point) => void;
  /** Da chiamare su mouseup per inviare la posizione finale. */
  onFootprintDragEnd?: () => void;

  // Tracciatura interattiva (track / via)
  /** Modalità di disegno attiva: 'none' | 'track' | 'via'. */
  drawMode?: 'none' | 'track' | 'via';
  /** Segmento in bozza da renderizzare durante il drag. */
  draftSegment?: { start: Point; current: Point } | null;
  /** Larghezza della traccia in bozza, per lo stroke del preview. */
  draftWidthMm?: number;
  /** Callback: converte un evento mouse in coordinate mm e avvia il drag. */
  onDrawStart?: (p: Point) => void;
  /** Callback: aggiorna la posizione corrente durante il drag. */
  onDrawMove?: (p: Point) => void;
  /** Callback: conclude il drag (invio kicad_add_track). */
  onDrawEnd?: () => void;
  /** Callback: piazzamento via su click singolo. */
  onViaPlace?: (p: Point) => void;
}

export default function PcbCanvas({
  board,
  viewBox,
  layerVisibility,
  gridVisible,
  gridStep,
  onPanStart,
  onPanMove,
  onPanEnd,
  onWheel,
  tooltipData,
  mouseX,
  mouseY,
  onMouseMoveCanvas,
  onPadEnter,
  onPadLeave,
  draggingRef = null,
  dragPreviewPosition = null,
  onFootprintDragStart,
  onFootprintDragMove,
  onFootprintDragEnd,
  drawMode = 'none',
  draftSegment = null,
  draftWidthMm = 0.25,
  onDrawStart,
  onDrawMove,
  onDrawEnd,
  onViaPlace,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  // Converte un evento mouse in coordinate mm usando il viewBox corrente.
  const toMm = (e: React.MouseEvent): Point => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const inv = ctm.inverse();
    const p = pt.matrixTransform(inv);
    return { x: p.x, y: p.y };
  };

  // Dimensione viewport in px per il clamp del tooltip.
  const viewportWidth = svgRef.current?.getBoundingClientRect().width ?? 800;
  const viewportHeight = svgRef.current?.getBoundingClientRect().height ?? 600;

  return (
    <div className="pcb-canvas-wrapper" style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg
        ref={svgRef}
        className="pcb-canvas"
        viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
        style={{
          width: '100%',
          height: '100%',
          cursor: 'grab',
          background: 'var(--pcb-bg, #0a1628)',
          touchAction: 'none',
          display: 'block',
        }}
        onMouseDown={(e) => {
          if (drawMode === 'track') {
            e.preventDefault();
            onDrawStart?.(toMm(e));
            return;
          }
          if (drawMode === 'via') {
            // La via si piazza al mouseup per non confliggere con il pan.
            return;
          }
          onPanStart?.(e);
        }}
        onMouseMove={(e) => {
          if (draggingRef && onFootprintDragMove) {
            e.preventDefault();
            onFootprintDragMove(toMm(e));
            return;
          }
          if (drawMode === 'track' && draftSegment) {
            e.preventDefault();
            onDrawMove?.(toMm(e));
            return;
          }
          onPanMove?.(e);
          onMouseMoveCanvas?.(e);
        }}
        onMouseUp={(e) => {
          if (draggingRef && onFootprintDragEnd) {
            e.preventDefault();
            void onFootprintDragEnd();
            return;
          }
          if (drawMode === 'track' && draftSegment) {
            e.preventDefault();
            void onDrawEnd?.();
            return;
          }
          if (drawMode === 'via') {
            // Piazza la via solo se il click non è stato un drag di pan.
            const p = toMm(e);
            void onViaPlace?.(p);
            return;
          }
          onPanEnd?.();
        }}
        onMouseLeave={() => { onPanEnd?.(); onPadLeave?.(); }}
        onWheel={onWheel}
      >
        {/* Griglia di riferimento */}
        <GridOverlay
          visible={gridVisible}
          step={gridStep}
          width={board.width}
          height={board.height}
        />

        {/* Contorno board (Edge.Cuts) */}
        <BoardOutlineLayer
          outline={board.outline}
          visible={layerVisibility['Edge.Cuts'] !== false}
        />

        {/* Tracce */}
        <TrackLayer
          tracks={board.tracks}
          visible={layerVisibility['F.Cu'] !== false || layerVisibility['B.Cu'] !== false}
        />

        {/* Vie */}
        <ViaLayer vias={board.vias} visible={true} />

        {/* Segmento in bozza durante la tracciatura di una traccia */}
        {drawMode === 'track' && draftSegment && (
          <line
            x1={draftSegment.start.x}
            y1={draftSegment.start.y}
            x2={draftSegment.current.x}
            y2={draftSegment.current.y}
            stroke="#4fc3f7"
            strokeWidth={Math.max(draftWidthMm, 0.05)}
            strokeLinecap="round"
            opacity={0.85}
            pointerEvents="none"
          />
        )}

        {/* Footprint (top + bottom) con eventi pad per il tooltip e drag-to-move */}
        <FootprintLayer
          footprints={board.footprints.filter((fp) => fp.layer === 'F.Cu')}
          visible={layerVisibility['F.Cu'] !== false}
          onPadEnter={onPadEnter}
          onPadLeave={onPadLeave}
          selectedRef={draggingRef}
          draggingRef={draggingRef}
          dragPreviewPosition={dragPreviewPosition}
          onFootprintDragStart={onFootprintDragStart}
        />
        <FootprintLayer
          footprints={board.footprints.filter((fp) => fp.layer === 'B.Cu')}
          visible={layerVisibility['B.Cu'] !== false}
          onPadEnter={onPadEnter}
          onPadLeave={onPadLeave}
          selectedRef={draggingRef}
          draggingRef={draggingRef}
          dragPreviewPosition={dragPreviewPosition}
          onFootprintDragStart={onFootprintDragStart}
        />
      </svg>

      {/* Tooltip overlay assoluto, clampato nel viewport.
          Il debounce (300ms show / 150ms hide) è interno a SelectionTooltip: qui
          passiamo solo i dati e la posizione mouse; il componente decide da solo
          quando apparire/scomparire in base alla presenza di `data`. */}
      <SelectionTooltip
        data={tooltipData}
        mouseX={mouseX}
        mouseY={mouseY}
        viewportWidth={viewportWidth}
        viewportHeight={viewportHeight}
      />
    </div>
  );
}