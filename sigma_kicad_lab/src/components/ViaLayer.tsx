// =============================================================================
// ViaLayer — renderizza le vie (passanti) sulla board
// =============================================================================
import type { Via } from '../types/pcb';
import { netColorHash } from '../lib/netColorHash';
import { PCB_COLORS } from '../lib/constants';

interface Props {
  vias: Via[];
  visible: boolean;
}

export default function ViaLayer({ vias, visible }: Props) {
  const cls = visible ? '' : 'layer-hidden';

  return (
    <g className={`pcb-layer pcb-vias ${cls}`}>
      {vias.map((v, i) => {
        const color = v.netName ? netColorHash(v.netName) : PCB_COLORS.viaUnrouted;
        const rPad = v.padDiameter / 2;
        const rDrill = v.drillDiameter / 2;

        return (
          <g key={i}>
            {/* Pad della via */}
            <circle
              cx={v.position.x}
              cy={v.position.y}
              r={rPad}
              fill={color}
              stroke="var(--pcb-via-ring, #1e293b)"
              strokeWidth={0.15}
            />
            {/* Foro di perforazione */}
            <circle
              cx={v.position.x}
              cy={v.position.y}
              r={rDrill}
              fill="var(--pcb-bg, #0a1628)"
              stroke="#334155"
              strokeWidth={0.08}
            />
          </g>
        );
      })}
    </g>
  );
}