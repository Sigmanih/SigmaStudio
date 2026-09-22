// =============================================================================
// SelectionTooltip — tooltip hover su footprint con debounce 300ms
// Il componente è controllato: riceve data/mouseX/mouseY dal genitore.
// La temporizzazione (showDelayMs=300, hideDelayMs=150) è gestita internamente:
// al primo mouseenter su un pad il tooltip appare dopo 300ms; al mouseleave
// scompare in <200ms. Lo stato visibile è derivato da data + timer interni.
// =============================================================================
import { useEffect, useRef, useState } from 'react';
import type { Footprint, Pad } from '../types/pcb';

export interface TooltipData {
  footprint: Footprint;
  pad?: Pad | null;
}

interface Props {
  data: TooltipData | null;
  mouseX: number;
  mouseY: number;
  viewportWidth: number;
  viewportHeight: number;
  /** Delay in ms prima che il tooltip appaia (default 300). */
  showDelayMs?: number;
  /** Delay in ms prima che il tooltip scompaia (default 150, <200). */
  hideDelayMs?: number;
}

const TOOLTIP_W = 220;
const TOOLTIP_H = 96;

export default function SelectionTooltip({
  data,
  mouseX,
  mouseY,
  viewportWidth,
  viewportHeight,
  showDelayMs = 300,
  hideDelayMs = 150,
}: Props) {
  const [visible, setVisible] = useState(false);
  const showTimer = useRef<number | null>(null);
  const hideTimer = useRef<number | null>(null);

  // Pulizia timer su unmount per evitare leak di memoria.
  useEffect(() => {
    return () => {
      if (showTimer.current !== null) window.clearTimeout(showTimer.current);
      if (hideTimer.current !== null) window.clearTimeout(hideTimer.current);
    };
  }, []);

  // Quando data diventa non-null: programma la comparsa dopo showDelayMs.
  useEffect(() => {
    if (data) {
      if (hideTimer.current !== null) { window.clearTimeout(hideTimer.current); hideTimer.current = null; }
      if (showTimer.current !== null) window.clearTimeout(showTimer.current);
      setVisible(false);
      showTimer.current = window.setTimeout(() => {
        setVisible(true);
        showTimer.current = null;
      }, showDelayMs);
    } else {
      // data null: programma la scomparsa dopo hideDelayMs.
      if (showTimer.current !== null) { window.clearTimeout(showTimer.current); showTimer.current = null; }
      if (hideTimer.current !== null) window.clearTimeout(hideTimer.current);
      setVisible(true); // resta visibile fino allo scadere del timer
      hideTimer.current = window.setTimeout(() => {
        setVisible(false);
        hideTimer.current = null;
      }, hideDelayMs);
    }
  }, [data, showDelayMs, hideDelayMs]);

  if (!visible || !data) return null;

  // Clamp posizione nel viewport canvas.
  let left = mouseX + 14;
  let top = mouseY + 14;
  if (left + TOOLTIP_W > viewportWidth) left = Math.max(8, mouseX - TOOLTIP_W - 14);
  if (top + TOOLTIP_H > viewportHeight) top = Math.max(8, mouseY - TOOLTIP_H - 14);

  const { footprint: fp, pad } = data;

  return (
    <div
      className="pcb-tooltip"
      role="tooltip"
      style={{
        position: 'absolute',
        left,
        top,
        width: TOOLTIP_W,
        background: '#1e293b',
        border: '1px solid var(--pcb-accent, #00d4ff)',
        borderRadius: 6,
        padding: '10px 12px',
        pointerEvents: 'none',
        zIndex: 50,
        boxShadow: '0 8px 24px rgba(0,0,0,.45), 0 0 0 1px rgba(0,212,255,.15)',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ color: 'var(--pcb-accent, #00d4ff)', fontWeight: 700, fontSize: 13 }}>{fp.reference}</span>
        <span style={{ color: '#e2e8f0', fontSize: 12 }}>{fp.value || '—'}</span>
      </div>
      {pad && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8' }}>
          <span>Pin: <strong style={{ color: '#e2e8f0' }}>{pad.id}</strong></span>
          {pad.netName && (
            <span>Net: <strong style={{ color: 'var(--pcb-accent, #00d4ff)' }}>{pad.netName}</strong></span>
          )}
        </div>
      )}
      <div style={{ marginTop: 6, fontSize: 10, color: '#64748b' }}>
        {fp.footprintName} · {fp.layer === 'F.Cu' ? 'Top' : 'Bottom'} · rot {fp.rotation.toFixed(0)}°
      </div>
    </div>
  );
}
