import React, { useState, useRef, useEffect } from 'react';
import { ZoomIn, ZoomOut, Maximize2, Download, Palette, RotateCcw, Loader, AlertTriangle } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

export default function ImageViewer({ tab }) {
  const appContext = useApp();
  const openTab = appContext ? appContext.openTab : null;
  
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [dimensions, setDimensions] = useState(null);
  
  const containerRef = useRef(null);
  const imgRef = useRef(null);

  // Reset state when tab changes
  useEffect(() => {
    setLoading(true);
    setError(false);
    setScale(1);
    setPosition({ x: 0, y: 0 });
    setDimensions(null);
  }, [tab.path]);

  const handleImageLoad = (e) => {
    setLoading(false);
    setDimensions({
      width: e.target.naturalWidth,
      height: e.target.naturalHeight
    });
    // Auto-fit on load
    fitToScreen(e.target.naturalWidth, e.target.naturalHeight);
  };

  const handleImageError = () => {
    setLoading(false);
    setError(true);
  };

  const fitToScreen = (natWidth = null, natHeight = null) => {
    if (!containerRef.current) return;
    const imgWidth = natWidth || (imgRef.current ? imgRef.current.naturalWidth : 0);
    const imgHeight = natHeight || (imgRef.current ? imgRef.current.naturalHeight : 0);
    if (!imgWidth || !imgHeight) return;

    const container = containerRef.current.getBoundingClientRect();
    const padding = 40;
    const scaleX = (container.width - padding) / imgWidth;
    const scaleY = (container.height - padding) / imgHeight;
    
    const newScale = Math.min(scaleX, scaleY, 1);
    setScale(newScale);
    setPosition({ x: 0, y: 0 });
  };

  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleZoom = (delta) => {
    setScale(prev => {
      const newScale = prev + delta;
      return Math.max(0.1, Math.min(newScale, 5)); // Min 10%, Max 500%
    });
  };

  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      handleZoom(delta);
    }
  };

  const handleMouseDown = (e) => {
    if (scale > 1 || (imgRef.current && imgRef.current.getBoundingClientRect().width > containerRef.current.getBoundingClientRect().width)) {
      setIsDragging(true);
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y
      });
    }
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleDoubleClick = () => {
    if (scale === 1) {
      fitToScreen();
    } else {
      resetZoom();
    }
  };

  const handleDownload = () => {
    const a = document.createElement('a');
    a.href = tab.path;
    a.download = tab.path.split('/').pop().split('\\').pop() || 'image';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleOpenStudio = () => {
    if (openTab) {
      openTab(tab.path);
    } else {
      console.log('Opening in Creative Lab', tab.path);

    }
  };

  const filename = tab.path ? tab.path.split('/').pop().split('\\').pop() : 'Immagine';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#12141c' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 16px',
        backgroundColor: '#0e1016',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            fontSize: '0.9rem',
            color: '#e2e4eb',
            fontWeight: 500,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '300px'
          }}>
            {filename}
          </div>
          {dimensions && (
            <div style={{ fontSize: '0.75rem', color: '#8b8fa3', fontFamily: 'JetBrains Mono, monospace' }}>
              {dimensions.width} × {dimensions.height}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Zoom controls */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            background: 'rgba(255,255,255,0.03)', 
            borderRadius: '6px',
            border: '1px solid rgba(255,255,255,0.08)'
          }}>
            <button onClick={() => handleZoom(-0.2)} className="image-viewer-toolbar-btn" title="Riduci (Ctrl + Scroll giù)">
              <ZoomOut size={16} />
            </button>
            <div style={{ 
              fontSize: '0.75rem', 
              color: '#a0a5b8', 
              width: '45px', 
              textAlign: 'center',
              fontFamily: 'JetBrains Mono, monospace'
            }}>
              {Math.round(scale * 100)}%
            </div>
            <button onClick={() => handleZoom(0.2)} className="image-viewer-toolbar-btn" title="Ingrandisci (Ctrl + Scroll su)">
              <ZoomIn size={16} />
            </button>
            <div style={{ width: '1px', height: '16px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />
            <button onClick={resetZoom} className="image-viewer-toolbar-btn" title="Dimensioni originali (100%)">
              <RotateCcw size={16} />
            </button>
            <button onClick={() => fitToScreen()} className="image-viewer-toolbar-btn" title="Adatta allo schermo">
              <Maximize2 size={16} />
            </button>
          </div>

          <div style={{ width: '1px', height: '20px', backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />

          <button onClick={handleDownload} className="image-viewer-action-btn" style={{ background: 'rgba(255,255,255,0.05)' }}>
            <Download size={16} /> <span style={{ fontSize: '0.8rem' }}>Scarica</span>
          </button>
          
          <button onClick={handleOpenStudio} className="image-viewer-action-btn studio-btn" style={{ background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.15), rgba(124, 91, 240, 0.15))', border: '1px solid rgba(124, 91, 240, 0.3)', color: '#00d2ff' }}>
            <Palette size={16} color="#7c5bf0" /> <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>Apri in Creative Lab</span>

          </button>
        </div>
      </div>

      {/* Main Area */}
      <div 
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: '#0e1016',
          backgroundImage: `
            linear-gradient(45deg, rgba(255,255,255,0.02) 25%, transparent 25%), 
            linear-gradient(-45deg, rgba(255,255,255,0.02) 25%, transparent 25%), 
            linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.02) 75%), 
            linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.02) 75%)
          `,
          backgroundSize: '20px 20px',
          backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          cursor: isDragging ? 'grabbing' : (scale > 1 ? 'grab' : 'default'),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: '#8b8fa3' }}>
            <Loader size={32} className="image-viewer-spin" color="#00d2ff" style={{ animation: 'imageViewerSpin 1s linear infinite' }} />
            <span style={{ fontSize: '0.85rem' }}>Caricamento immagine...</span>
          </div>
        )}

        {error && !loading && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: '#f85149', background: 'rgba(248,81,73,0.1)', padding: '20px', borderRadius: '8px', border: '1px solid rgba(248,81,73,0.2)' }}>
            <AlertTriangle size={32} />
            <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Impossibile caricare l'immagine</span>
            <button 
              onClick={() => { setLoading(true); setError(false); }}
              style={{
                background: 'rgba(255,255,255,0.1)',
                border: 'none',
                color: '#fff',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.8rem',
                marginTop: '8px'
              }}
            >
              Riprova
            </button>
          </div>
        )}

        <img
          ref={imgRef}
          src={tab.path}
          alt={filename}
          onLoad={handleImageLoad}
          onError={handleImageError}
          onDoubleClick={handleDoubleClick}
          style={{
            display: loading || error ? 'none' : 'block',
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.2s cubic-bezier(0.2, 0, 0, 1)',
            maxWidth: 'none',
            maxHeight: 'none',
            boxShadow: '0 10px 30px rgba(0,0,0,0.3)'
          }}
          draggable="false"
        />
        
        <style>{`
          @keyframes imageViewerSpin {
            100% { transform: rotate(360deg); }
          }
          .image-viewer-toolbar-btn {
            background: transparent;
            border: none;
            color: #a0a5b8;
            padding: 6px;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
          }
          .image-viewer-toolbar-btn:hover {
            background: rgba(255,255,255,0.1);
            color: #fff;
          }
          .image-viewer-action-btn {
            border: 1px solid rgba(255,255,255,0.1);
            color: #e2e4eb;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
          }
          .image-viewer-action-btn:hover {
            background: rgba(255,255,255,0.1) !important;
          }
          .image-viewer-action-btn.studio-btn:hover {
            background: linear-gradient(135deg, rgba(0, 210, 255, 0.25), rgba(124, 91, 240, 0.25)) !important;
          }
        `}</style>
      </div>
    </div>
  );
}
