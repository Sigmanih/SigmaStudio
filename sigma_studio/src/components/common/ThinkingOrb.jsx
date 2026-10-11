import React, { useEffect, useRef } from 'react';
import { Globe, Sparkles, Zap, Check, Activity } from 'lucide-react';

// ==============================================================================
// THINKING ORB — Visualizzatore di Stato Cognitivo ed Operativo per Agenti
// Supporta gli stati: 'idle', 'thinking', 'browsing', 'executing', 'done'
// Zero dipendenze esterne: Standard React + Canvas 2D + Lucide Icons
// ==============================================================================

const STATE_CONFIG = {
  idle: {
    label: 'Pronto',
    color1: '#00d2ff',
    color2: '#7c5bf0',
    speed: 0.015,
    icon: Activity,
  },
  thinking: {
    label: 'Ragionamento...',
    color1: '#a855f7',
    color2: '#00d2ff',
    speed: 0.045,
    icon: Sparkles,
  },
  browsing: {
    label: 'Scansione Web...',
    color1: '#00e5ff',
    color2: '#3b82f6',
    speed: 0.035,
    icon: Globe,
  },
  executing: {
    label: 'Esecuzione Tools...',
    color1: '#10b981',
    color2: '#00d2ff',
    speed: 0.05,
    icon: Zap,
  },
  done: {
    label: 'Completato',
    color1: '#10b981',
    color2: '#34d399',
    speed: 0.01,
    icon: Check,
  },
};

export default function ThinkingOrb({
  state = 'idle',
  size = 22,
  showLabel = false,
  customLabel = null,
  className = '',
}) {
  const canvasRef = useRef(null);
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.idle;
  const IconComponent = cfg.icon;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId;
    let angle = 0;
    const pixelRatio = window.devicePixelRatio || 1;
    const diameter = size * pixelRatio;
    canvas.width = diameter;
    canvas.height = diameter;

    const centerX = diameter / 2;
    const centerY = diameter / 2;
    const baseRadius = (diameter / 2) * 0.72;

    const render = () => {
      ctx.clearRect(0, 0, diameter, diameter);
      angle += cfg.speed;

      // 1. Nucleo energetico pulsante (Core)
      const pulse = Math.sin(angle * 2) * (baseRadius * 0.12);
      const coreRadius = Math.max(2, baseRadius * 0.55 + pulse);

      const grad = ctx.createRadialGradient(
        centerX, centerY, 1,
        centerX, centerY, coreRadius * 1.4
      );
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.35, cfg.color1);
      grad.addColorStop(0.85, cfg.color2);
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.beginPath();
      ctx.arc(centerX, centerY, coreRadius * 1.3, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // 2. Anello orbitale / Radar
      if (state === 'browsing') {
        // Radar sweep beam per la scansione browser
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(angle * 2.5);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, baseRadius * 1.25, 0, Math.PI * 0.38);
        ctx.closePath();
        const radarGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, baseRadius * 1.25);
        radarGrad.addColorStop(0, 'rgba(0, 240, 255, 0.45)');
        radarGrad.addColorStop(1, 'rgba(0, 240, 255, 0.0)');
        ctx.fillStyle = radarGrad;
        ctx.fill();
        ctx.restore();

        // Anello di bordo tech
        ctx.beginPath();
        ctx.arc(centerX, centerY, baseRadius * 1.15, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(0, 229, 255, 0.35)';
        ctx.lineWidth = 1 * pixelRatio;
        ctx.stroke();
      } else {
        // Orbita con scintille
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(angle);

        ctx.beginPath();
        ctx.ellipse(0, 0, baseRadius * 1.1, baseRadius * 0.65, angle * 0.5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${state === 'thinking' ? '168, 85, 247' : '0, 210, 255'}, 0.28)`;
        ctx.lineWidth = 1 * pixelRatio;
        ctx.stroke();

        // Particelle su orbita
        const sparkCount = state === 'thinking' || state === 'executing' ? 3 : 2;
        for (let i = 0; i < sparkCount; i++) {
          const sparkAngle = angle * (i % 2 === 0 ? 2 : -2) + (i * Math.PI * 2) / sparkCount;
          const px = Math.cos(sparkAngle) * (baseRadius * 1.05);
          const py = Math.sin(sparkAngle) * (baseRadius * 0.7);
          ctx.beginPath();
          ctx.arc(px, py, 1.4 * pixelRatio, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.shadowColor = cfg.color1;
          ctx.shadowBlur = 4 * pixelRatio;
          ctx.fill();
        }
        ctx.restore();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [state, size, cfg]);

  const labelText = customLabel || cfg.label;

  return (
    <div className={`thinking-orb-container state-${state} ${className}`} title={labelText}>
      <div
        className="thinking-orb-wrapper"
        style={{ width: `${size}px`, height: `${size}px` }}
      >
        <div
          className="thinking-orb-glow"
          style={{ width: `${size * 1.5}px`, height: `${size * 1.5}px` }}
        />
        <canvas
          ref={canvasRef}
          className="thinking-orb-canvas"
          style={{ width: `${size}px`, height: `${size}px` }}
        />
      </div>

      {showLabel && (
        <span className={`thinking-orb-badge badge-${state}`}>
          <IconComponent size={11} />
          <span>{labelText}</span>
        </span>
      )}
    </div>
  );
}
