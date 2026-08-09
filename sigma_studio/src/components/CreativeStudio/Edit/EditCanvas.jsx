import React, { useState, useRef, useEffect } from 'react';
import {
  Brush, Eraser, Scissors, Square, Sliders, Image as ImageIcon,
  SplitSquareHorizontal, Sun, Sparkles, RotateCcw, MessageSquare, Layers, Wand2
} from 'lucide-react';

const DIRECTIONS = ['all', 'top', 'bottom', 'left', 'right'];

export default function EditCanvas({ asset, busy, capabilities = {}, onEdit, onUpscale, onSegment }) {
  const [tool, setTool] = useState('brush');
  const [brushSize, setBrushSize] = useState(40);
  const [prompt, setPrompt] = useState('');
  const [direction, setDirection] = useState('all');
  const [pixels, setPixels] = useState(128);
  const [lightDir, setLightDir] = useState('front');
  const canvasRef = useRef(null);
  const maskRef = useRef(null);
  const drawing = useRef(false);

  useEffect(() => {
    if (!asset?.url || !canvasRef.current) return;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = asset.url;
    img.onload = () => {
      const canvas = canvasRef.current;
      const mask = maskRef.current;
      if (!canvas || !mask) return;
      canvas.width = img.width;
      canvas.height = img.height;
      canvas.getContext('2d').drawImage(img, 0, 0);
      mask.width = img.width;
      mask.height = img.height;
      mask.getContext('2d').clearRect(0, 0, img.width, img.height);
    };
  }, [asset]);

  const pointAt = (e) => {
    const rect = maskRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (maskRef.current.width / rect.width),
      y: (e.clientY - rect.top) * (maskRef.current.height / rect.height),
    };
  };

  const startDrawing = (e) => { drawing.current = true; draw(e); };
  const stopDrawing = () => {
    drawing.current = false;
    maskRef.current?.getContext('2d').beginPath();
  };

  const draw = (e) => {
    if (!drawing.current || !maskRef.current) return;
    const ctx = maskRef.current.getContext('2d');
    const { x, y } = pointAt(e);

    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over';
    ctx.strokeStyle = 'rgba(255, 0, 0, 0.55)';
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const clearMask = () => {
    const mask = maskRef.current;
    mask?.getContext('2d').clearRect(0, 0, mask.width, mask.height);
  };

  const hasMask = () => {
    const mask = maskRef.current;
    if (!mask) return false;
    const { data } = mask.getContext('2d').getImageData(0, 0, mask.width, mask.height);
    for (let i = 3; i < data.length; i += 4) if (data[i] > 8) return true;
    return false;
  };

  const maskData = () => maskRef.current?.toDataURL('image/png');

  const runMaskedEdit = (task_type) => {
    if (!hasMask()) return alert('Disegna prima la maschera sull’area da modificare.');
    if (!prompt.trim()) return alert('Scrivi cosa deve comparire nell’area mascherata.');
    onEdit(task_type, asset.id, { mask_data: maskData(), prompt });
  };

  if (!asset) {
    return (
      <div className="cs-canvas-wrapper">
        <ImageIcon size={48} style={{ opacity: 0.2 }} />
        <p>Seleziona un asset immagine per modificarlo</p>
      </div>
    );
  }

  const disabled = busy || !asset.url;
  const canInstruct = (capabilities.instruct_edit || []).length > 0;

  return (
    <div className="cs-edit-canvas-container">
      <div className="cs-edit-toolbar">
        <button className={`cs-tool-btn ${tool === 'brush' ? 'active' : ''}`} onClick={() => setTool('brush')} title="Pennello maschera"><Brush size={16} /> Maschera</button>
        <button className={`cs-tool-btn ${tool === 'eraser' ? 'active' : ''}`} onClick={() => setTool('eraser')} title="Gomma"><Eraser size={16} /> Gomma</button>
        <button className="cs-tool-btn" onClick={clearMask} title="Azzera maschera"><RotateCcw size={16} /></button>

        <div className="cs-toolbar-sep" />
        <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Size</span>
        <input type="range" min="2" max="200" value={brushSize} onChange={e => setBrushSize(Number(e.target.value))} style={{ width: '80px', accentColor: 'var(--primary)' }} />

        <div className="cs-toolbar-sep" />
        <input
          className="cs-inline-input"
          placeholder="Prompt per l'area mascherata / lo stile..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)} />
      </div>

      <div className="cs-edit-actions">
        <button className="cs-tool-btn" disabled={disabled} onClick={() => runMaskedEdit('inpaint')}><Square size={16} /> Inpaint</button>
        <button className="cs-tool-btn" disabled={disabled} onClick={() => runMaskedEdit('replace_object')}><Sparkles size={16} /> Sostituisci</button>

        <div className="cs-action-group">
          <select className="cs-select" value={direction} onChange={e => setDirection(e.target.value)}>
            {DIRECTIONS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <input className="cs-num-input" type="number" min="16" max="1024" step="16" value={pixels} onChange={e => setPixels(Number(e.target.value))} />
          <button className="cs-tool-btn" disabled={disabled}
                  onClick={() => onEdit('outpaint', asset.id, { direction, pixels, prompt })}>
            <SplitSquareHorizontal size={16} /> Outpaint
          </button>
        </div>

        <button className="cs-tool-btn" disabled={disabled} onClick={() => onEdit('remove_background', asset.id)}><Scissors size={16} /> Rimuovi sfondo</button>
        <button className="cs-tool-btn" disabled={disabled || !prompt.trim()}
                title="Scontorna il soggetto e rigenera lo sfondo dal prompt"
                onClick={() => onEdit('replace_background', asset.id, { prompt })}>
          <Layers size={16} /> Sostituisci sfondo
        </button>
        <button className="cs-tool-btn" disabled={disabled} title="Crea una maschera riutilizzabile (SAM 2)"
                onClick={() => onSegment?.(asset.id, prompt)}>
          <Wand2 size={16} /> Segmenta
        </button>
        <button className="cs-tool-btn" disabled={disabled || !prompt.trim() || !canInstruct}
                title={canInstruct
                  ? 'Modifica guidata dal linguaggio (FLUX Kontext / Qwen-Image-Edit)'
                  : 'Richiede ComfyUI con Kontext/Qwen-Image-Edit oppure fal.ai'}
                onClick={() => onEdit('instruct_edit', asset.id, { instruction: prompt })}>
          <MessageSquare size={16} /> Instruct edit
        </button>
        <button className="cs-tool-btn" disabled={disabled || !prompt.trim()}
                onClick={() => onEdit('style_transfer', asset.id, { style_prompt: prompt, strength: 0.7 })}>
          <Sliders size={16} /> Style transfer
        </button>

        <div className="cs-action-group">
          <select className="cs-select" value={lightDir} onChange={e => setLightDir(e.target.value)}>
            {['front', 'left', 'right', 'top', 'bottom'].map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <button className="cs-tool-btn" disabled={disabled}
                  onClick={() => onEdit('relight', asset.id, { light_direction: lightDir, intensity: 1.2 })}>
            <Sun size={16} /> Relight
          </button>
        </div>

        <button className="cs-tool-btn" disabled={disabled} onClick={() => onUpscale(asset.id, 2)}>2x Upscale</button>
      </div>

      <div className="cs-canvas-wrapper">
        <canvas ref={canvasRef} className="cs-main-canvas" />
        <canvas
          ref={maskRef}
          className="cs-mask-canvas"
          onPointerDown={startDrawing}
          onPointerUp={stopDrawing}
          onPointerLeave={stopDrawing}
          onPointerMove={draw}
          style={{ cursor: 'crosshair', touchAction: 'none' }} />
      </div>
    </div>
  );
}
