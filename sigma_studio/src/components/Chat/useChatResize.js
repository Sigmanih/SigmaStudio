import { useState, useEffect, useRef } from 'react';
import { loadSize, saveSize, savePosition } from './chatStorage';

const MIN_WIDTH = 360;
const MIN_HEIGHT = 300;

export { MIN_WIDTH, MIN_HEIGHT };

/**
 * Custom hook per il resize del pannello chat tramite bordi e angoli.
 * Supporta 8 direzioni: n, s, e, w, ne, nw, se, sw.
 */
export default function useChatResize(panelPos, setPanelPos) {
  const [panelSize, setPanelSize] = useState(() => loadSize(480, 600));
  const [resizing, setResizing] = useState(null);
  const [resizeStart, setResizeStart] = useState({ x: 0, y: 0 });
  const resizeSizeStart = useRef({ width: 480, height: 600 });
  const resizePosStart = useRef({ x: 0, y: 0 });

  // Resize effect
  useEffect(() => {
    if (!resizing) return;
    const hMM = (e) => {
      const dx = e.clientX - resizeStart.x;
      const dy = e.clientY - resizeStart.y;

      setPanelPos(prev => {
        let newX = prev.x;
        let newY = prev.y;
        let newW = resizeSizeStart.current.width;
        let newH = resizeSizeStart.current.height;

        if (resizing.includes('e')) {
          newW = Math.max(MIN_WIDTH, resizeSizeStart.current.width + dx);
        }
        if (resizing.includes('w')) {
          const diff = resizeSizeStart.current.width - dx;
          if (diff >= MIN_WIDTH) {
            newW = diff;
            newX = (resizePosStart.current.x || 0) + dx;
          }
        }
        if (resizing.includes('s')) {
          newH = Math.max(MIN_HEIGHT, resizeSizeStart.current.height + dy);
        }
        if (resizing.includes('n')) {
          const diff = resizeSizeStart.current.height - dy;
          if (diff >= MIN_HEIGHT) {
            newH = diff;
            newY = (resizePosStart.current.y || 0) + dy;
          }
        }

        return { x: newX, y: newY };
      });

      setPanelSize(() => {
        let newW = resizeSizeStart.current.width;
        let newH = resizeSizeStart.current.height;
        if (resizing.includes('e')) newW = Math.max(MIN_WIDTH, resizeSizeStart.current.width + dx);
        if (resizing.includes('w')) newW = Math.max(MIN_WIDTH, resizeSizeStart.current.width - dx);
        if (resizing.includes('s')) newH = Math.max(MIN_HEIGHT, resizeSizeStart.current.height + dy);
        if (resizing.includes('n')) newH = Math.max(MIN_HEIGHT, resizeSizeStart.current.height - dy);
        return { width: newW, height: newH };
      });
    };
    const hMU = () => {
      setResizing(null);
      // Use a synchronous save via callback pattern
      setPanelSize(prev => { saveSize(prev); return prev; });
      setPanelPos(prev => { savePosition(prev); return prev; });
    };
    document.addEventListener('mousemove', hMM);
    document.addEventListener('mouseup', hMU);
    return () => { document.removeEventListener('mousemove', hMM); document.removeEventListener('mouseup', hMU); };
  }, [resizing, resizeStart, panelPos, setPanelPos]);

  const handleResizeStart = (direction, e) => {
    e.preventDefault();
    e.stopPropagation();
    setResizing(direction);
    setResizeStart({ x: e.clientX, y: e.clientY });
    resizeSizeStart.current = { width: panelSize.width, height: panelSize.height };
    resizePosStart.current = { x: panelPos.x, y: panelPos.y };
  };

  // Resize handle definitions
  const resizeHandles = [
    { dir: 'n', className: 'chat-resize-n', cursor: 'n-resize' },
    { dir: 's', className: 'chat-resize-s', cursor: 's-resize' },
    { dir: 'e', className: 'chat-resize-e', cursor: 'e-resize' },
    { dir: 'w', className: 'chat-resize-w', cursor: 'w-resize' },
    { dir: 'ne', className: 'chat-resize-ne', cursor: 'ne-resize' },
    { dir: 'nw', className: 'chat-resize-nw', cursor: 'nw-resize' },
    { dir: 'se', className: 'chat-resize-se', cursor: 'se-resize' },
    { dir: 'sw', className: 'chat-resize-sw', cursor: 'sw-resize' },
  ];

  return { panelSize, resizing, resizeHandles, handleResizeStart };
}