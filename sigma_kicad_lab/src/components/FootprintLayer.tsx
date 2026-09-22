// =============================================================================
// FootprintLayer — renderizza footprint (corpo + pad) sul layer F.Cu o B.Cu
// =============================================================================
import type { JSX } from 'react';
import type { Footprint, Pad } from '../types/pcb';
import { PCB_COLORS } from '../lib/constants';

import type { Point } from '../types/pcb';

interface Props {
  footprints: Footprint[];
  visible: boolean;
  onPadEnter?: (pad: Pad, fp: Footprint) => void;
  onPadLeave?: () => void;
  /** Reference della footprint selezionata (evidenziata). */
  selectedRef?: string | null;
  /** Click su una footprint per selezionarla. */
  onSelectFootprint?: (ref: string) => void;

  // Drag-to-move (task #2)
  /** Se true, la footprint selezionata è in drag e va renderizzata in previewPosition. */
  draggingRef?: string | null;
  /** Posizione corrente della footprint in drag (mm). */
  dragPreviewPosition?: Point | null;
  /** Da chiamare su mousedown sulla footprint selezionata per avviare il drag. */
  onFootprintDragStart?: (fp: Footprint, p: Point) => void;
}

function padShape(pad: Pad): JSX.Element | null {
  const { x, y } = pad.position;
  if (pad.shape === 'circle') {
    return (
      <circle
        cx={x}
        cy={y}
        r={Math.max(pad.width, pad.height) / 2}
        fill={PCB_COLORS.padTop}
        stroke="#0f172a"
        strokeWidth={0.15}
      />
    );
  }
  if (pad.shape === 'oval') {
    return (
      <ellipse
        cx={x}
        cy={y}
        rx={pad.width / 2}
        ry={pad.height / 2}
        fill={PCB_COLORS.padTop}
        stroke="#0f172a"
        strokeWidth={0.15}
      />
    );
  }
  // rect (default)
  return (
    <rect
      x={x - pad.width / 2}
      y={y - pad.height / 2}
      width={pad.width}
      height={pad.height}
      fill={PCB_COLORS.padTop}
      stroke="#0f172a"
      strokeWidth={0.15}
    />
  );
}

export default function FootprintLayer({
  footprints,
  visible,
  onPadEnter,
  onPadLeave,
  selectedRef = null,
  onSelectFootprint,
  draggingRef = null,
  dragPreviewPosition = null,
  onFootprintDragStart,
}: Props) {
  const cls = visible ? '' : 'layer-hidden';

  return (
    <g className={`pcb-layer pcb-footprints ${cls}`}>
      {footprints.map((fp) => {
        const isSel = selectedRef === fp.reference;
        const isDragging = draggingRef === fp.reference;
        // Durante il drag la footprint viene renderizzata nella posizione preview.
        const pos = isDragging && dragPreviewPosition ? dragPreviewPosition : fp.position;
        return (
          <g
            key={fp.reference}
            transform={`translate(${pos.x},${pos.y}) rotate(${fp.rotation})`}
            onClick={(e) => {
              if (onSelectFootprint) {
                e.stopPropagation();
                onSelectFootprint(fp.reference);
              }
            }}
            onMouseDown={(e) => {
              // Avvia il drag solo se la footprint è già selezionata.
              if (isSel && onFootprintDragStart) {
                e.preventDefault();
                e.stopPropagation();
                // Costruisce il punto in mm usando il clientX/Y e la CTM della svg padre.
                const svg = (e.currentTarget as SVGGElement).ownerSVGElement;
                if (!svg) return;
                const pt = svg.createSVGPoint();
                pt.x = e.clientX;
                pt.y = e.clientY;
                const ctm = svg.getScreenCTM();
                if (!ctm) return;
                const p = pt.matrixTransform(ctm.inverse());
                onFootprintDragStart(fp, { x: p.x, y: p.y });
              }
            }}
            style={{ cursor: isSel ? 'move' : onSelectFootprint ? 'pointer' : undefined }}
          >
          {/* Corpo footprint: rettangolo generico 2x1.5mm centrato sull'origine locale */}
          <rect
            x={-1.0}
            y={-0.75}
            width={2.0}
            height={1.5}
            fill={isSel ? 'rgba(79,195,247,0.25)' : 'none'}
            stroke={isSel ? '#4fc3f7' : PCB_COLORS.silkscreen}
            strokeWidth={isSel ? 0.3 : 0.15}
          />
          {/* Reference label */}
          <text
            x={0}
            y={-1.2}
            textAnchor="middle"
            fontSize={0.8}
            fill={PCB_COLORS.silkscreen}
            fontFamily="Inter, sans-serif"
          >
            {fp.reference}
          </text>
          {/* Pad */}
          {fp.pads.map((pad) => (
            <g
              key={pad.id}
              onMouseEnter={() => onPadEnter?.(pad, fp)}
              onMouseLeave={() => onPadLeave?.()}
              style={{ cursor: 'pointer' }}
            >
              {padShape(pad)}
              {/* Numero pad */}
              <text
                x={pad.position.x}
                y={pad.position.y + 0.25}
                textAnchor="middle"
                fontSize={0.45}
                fill="#0f172a"
                fontFamily="Inter, sans-serif"
                pointerEvents="none"
              >
                {pad.id}
              </text>
            </g>
          ))}
          </g>
        );
      })}
    </g>
  );
}