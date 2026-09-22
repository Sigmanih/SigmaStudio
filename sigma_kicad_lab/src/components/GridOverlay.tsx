// =============================================================================
// GridOverlay — griglia di riferimento SVG (pattern) con step selezionabile
// =============================================================================
import { PCB_COLORS } from '../lib/constants';

interface Props {
  visible: boolean;
  /** Step della griglia in mm. */
  step: number;
  /** Larghezza board in mm. */
  width: number;
  /** Altezza board in mm. */
  height: number;
}

export default function GridOverlay({ visible, step, width, height }: Props) {
  if (!visible || step <= 0) return null;

  const cls = '' ; // la visibilità è gestita dal rendering condizionale + classe

  return (
    <g className={`pcb-layer pcb-grid ${cls}`}>
      <defs>
        <pattern
          id="pcb-grid-pattern"
          width={step}
          height={step}
          patternUnits="userSpaceOnUse"
        >
          <path
            d={`M ${step} 0 L 0 0 0 ${step}`}
            fill="none"
            stroke={PCB_COLORS.gridLine}
            strokeWidth={0.05}
          />
        </pattern>
      </defs>
      <rect
        x={0}
        y={0}
        width={width}
        height={height}
        fill="url(#pcb-grid-pattern)"
        pointerEvents="none"
      />
    </g>
  );
}