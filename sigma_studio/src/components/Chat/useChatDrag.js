import { useState, useEffect } from 'react';
import { loadPosition, savePosition } from './chatStorage';

/**
 * Custom hook per il drag del pannello chat.
 * Trascinando l'header si sposta il pannello.
 */
export default function useChatDrag(panelSize) {
  const [panelPos, setPanelPos] = useState(() => loadPosition());
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Drag effect
  useEffect(() => {
    if (!isDragging) return;
    const hMM = (e) => {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2 || panelPos.x !== undefined) {
        setPanelPos(prev => ({
          x: (prev.x !== undefined ? prev.x : window.innerWidth - (panelSize.width || 480)) + dx,
          y: (prev.y !== undefined ? prev.y : 80) + dy
        }));
        setDragStart({ x: e.clientX, y: e.clientY });
      }
    };
    const hMU = () => {
      setIsDragging(false);
      // Save position via ref to avoid stale closure
      setPanelPos(prev => { savePosition(prev); return prev; });
    };
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [isDragging, dragStart, panelPos, panelSize]);

  const startDrag = (e) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  return { panelPos, setPanelPos, isDragging, startDrag };
}