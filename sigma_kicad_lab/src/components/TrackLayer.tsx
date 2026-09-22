// =============================================================================
// TrackLayer — renderizza le tracce (tracks) sul layer F.Cu o B.Cu
// =============================================================================
import type { Track } from '../types/pcb';
import { netColorHash } from '../lib/netColorHash';
import { PCB_COLORS } from '../lib/constants';

interface Props {
  tracks: Track[];
  visible: boolean;
}

export default function TrackLayer({ tracks, visible }: Props) {
  const cls = visible ? '' : 'layer-hidden';

  return (
    <g className={`pcb-layer pcb-tracks ${cls}`}>
      {tracks.map((t, i) => {
        const color = t.netName ? netColorHash(t.netName) : PCB_COLORS.trackUnrouted;
        return (
          <line
            key={i}
            x1={t.start.x}
            y1={t.start.y}
            x2={t.end.x}
            y2={t.end.y}
            stroke={color}
            strokeWidth={Math.max(t.width, 0.1)}
            strokeLinecap="round"
          />
        );
      })}
    </g>
  );
}