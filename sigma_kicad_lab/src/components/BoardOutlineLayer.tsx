// =============================================================================
// BoardOutlineLayer — renderizza il contorno della board (Edge.Cuts)
// =============================================================================
import type { OutlinePath } from '../types/pcb';

interface Props {
  outline: OutlinePath | null;
  visible: boolean;
}

export default function BoardOutlineLayer({ outline, visible }: Props) {
  if (!outline || outline.points.length < 2) return null;

  const pointsAttr = outline.points.map((p) => `${p.x},${p.y}`).join(' ');
  const cls = visible ? '' : 'layer-hidden';

  return (
    <g className={`pcb-layer pcb-outline ${cls}`}>
      <polygon
        points={pointsAttr}
        fill="none"
        stroke="var(--pcb-courtyard, #475569)"
        strokeWidth={0.3}
        strokeLinejoin="round"
      />
    </g>
  );
}