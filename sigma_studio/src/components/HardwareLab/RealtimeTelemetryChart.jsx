import React, { useState } from 'react';
import { Activity } from 'lucide-react';

/**
 * Modern High-Definition Realtime Telemetry Chart
 */
export default function RealtimeTelemetryChart({ 
  data = [], 
  label, 
  icon: Icon, 
  color = '#00f2fe', 
  unit = '', 
  maxVal,
  formatVal,
  height = 100 
}) {
  const [hoverIdx, setHoverIdx] = useState(null);
  const N = 30; // 30 points = 60 seconds history window

  // Sanitize numeric array
  const recent = Array.isArray(data) && data.length > 0
    ? data.slice(-N).map(v => (typeof v === 'number' && !isNaN(v) ? v : 0))
    : [];

  const rawLastVal = recent.length > 0 ? recent[recent.length - 1] : 0;
  
  const displayVal = formatVal 
    ? formatVal(rawLastVal)
    : (typeof rawLastVal === 'number' 
        ? (Number.isInteger(rawLastVal) ? rawLastVal : rawLastVal.toFixed(1)) 
        : rawLastVal);

  const peakMax = recent.length > 0 ? Math.max(...recent) : 0;
  const avgVal = recent.length > 0 ? (recent.reduce((a, b) => a + b, 0) / recent.length) : 0;
  const mx = Math.max(1, maxVal || peakMax || 1);

  if (recent.length === 0) {
    return (
      <div className="hw-chart-card">
        <div className="hw-chart-header">
          <div className="hw-chart-title-box">
            <div className="hw-chart-icon-wrap" style={{ background: `${color}18`, color }}>
              {Icon ? <Icon size={14} color={color} /> : <Activity size={14} color={color} />}
            </div>
            <span className="hw-chart-label">{label}</span>
          </div>
        </div>
        <div className="hw-chart-placeholder">
          <Activity className="spin" size={16} color={color} />
          <span>Raccolta dati telemetria...</span>
        </div>
      </div>
    );
  }

  // SVG Geometry Calculation
  const svgWidth = 400;
  const svgHeight = height;
  const topPadding = 10;
  const bottomPadding = 10;
  const usableHeight = svgHeight - topPadding - bottomPadding;

  const points = recent.map((val, i) => {
    const x = (i / Math.max(1, recent.length - 1)) * svgWidth;
    const pct = Math.min(100, Math.max(0, (val / mx) * 100));
    const y = svgHeight - bottomPadding - (pct / 100) * usableHeight;
    return { x, y, val };
  });

  // Construct Cubic Bezier Smooth Path
  let pathD = '';
  if (points.length === 1) {
    pathD = `M 0,${points[0].y} L ${svgWidth},${points[0].y}`;
  } else if (points.length > 1) {
    pathD = `M ${points[0].x},${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i];
      const p1 = points[i + 1];
      const cpX = (p0.x + p1.x) / 2;
      pathD += ` C ${cpX},${p0.y} ${cpX},${p1.y} ${p1.x},${p1.y}`;
    }
  }

  const areaD = pathD
    ? `${pathD} L ${svgWidth},${svgHeight} L 0,${svgHeight} Z`
    : '';

  const hoveredPoint = hoverIdx !== null && points[hoverIdx] ? points[hoverIdx] : null;
  const gradId = `spark-grad-${label.replace(/[^a-zA-Z0-9]/g, '')}-${color.replace('#', '')}`;
  const glowFilterId = `glow-${label.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div className="hw-chart-card" style={{ borderColor: hoverIdx !== null ? `${color}44` : 'rgba(255,255,255,0.07)' }}>
      {/* Chart Header */}
      <div className="hw-chart-header">
        <div className="hw-chart-title-box">
          <div className="hw-chart-icon-wrap" style={{ background: `${color}18`, color }}>
            {Icon ? <Icon size={14} color={color} /> : <Activity size={14} color={color} />}
          </div>
          <span className="hw-chart-label">{label}</span>
        </div>
        <div className="hw-chart-val-box">
          <span className="hw-chart-val" style={{ color }}>{displayVal}</span>
          <span className="hw-chart-unit">{unit}</span>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div 
        className="hw-chart-body"
        style={{ height: `${svgHeight}px` }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <svg 
          viewBox={`0 0 ${svgWidth} ${svgHeight}`} 
          className="hw-chart-svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={color} stopOpacity="0.0" />
            </linearGradient>

            <filter id={glowFilterId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Reference Dashed Lines */}
          <line x1="0" y1={topPadding} x2={svgWidth} y2={topPadding} stroke="rgba(255,255,255,0.03)" strokeDasharray="4 4" />
          <line x1="0" y1={svgHeight / 2} x2={svgWidth} y2={svgHeight / 2} stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
          <line x1="0" y1={svgHeight - bottomPadding} x2={svgWidth} y2={svgHeight - bottomPadding} stroke="rgba(255,255,255,0.03)" strokeDasharray="4 4" />

          {/* Area Fill */}
          {areaD && <path d={areaD} fill={`url(#${gradId})`} />}

          {/* Glowing Line Stroke */}
          {pathD && (
            <path 
              d={pathD} 
              fill="none" 
              stroke={color} 
              strokeWidth="2.2" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              filter={`url(#${glowFilterId})`}
            />
          )}

          {/* Hover Crosshair Vertical Line */}
          {hoveredPoint && (
            <line
              x1={hoveredPoint.x}
              y1={topPadding}
              x2={hoveredPoint.x}
              y2={svgHeight - bottomPadding}
              stroke={color}
              strokeWidth="1"
              strokeDasharray="2 2"
              opacity="0.75"
            />
          )}

          {/* Live Endpoint Glow Circle */}
          {points.length > 0 && hoverIdx === null && (
            <circle 
              cx={points[points.length - 1].x} 
              cy={points[points.length - 1].y} 
              r="3.5" 
              fill={color}
              stroke="#0a0c12"
              strokeWidth="1.8"
            />
          )}

          {/* Hover Target Overlay Zones */}
          {points.map((p, i) => (
            <rect
              key={i}
              x={i === 0 ? 0 : (points[i - 1].x + p.x) / 2}
              y="0"
              width={i === points.length - 1 ? svgWidth - p.x + 10 : Math.max(1, points[i + 1].x - p.x)}
              height={svgHeight}
              fill="transparent"
              onMouseEnter={() => setHoverIdx(i)}
            />
          ))}

          {/* Hover Circle Marker */}
          {hoveredPoint && (
            <circle
              cx={hoveredPoint.x}
              cy={hoveredPoint.y}
              r="4.5"
              fill="#ffffff"
              stroke={color}
              strokeWidth="2"
            />
          )}
        </svg>

        {/* Floating Tooltip */}
        {hoveredPoint && (
          <div 
            className="hw-chart-tooltip"
            style={{ 
              left: `${Math.min(85, Math.max(15, (hoveredPoint.x / svgWidth) * 100))}%`,
              borderColor: color
            }}
          >
            {formatVal ? formatVal(hoveredPoint.val) : (typeof hoveredPoint.val === 'number' ? (Number.isInteger(hoveredPoint.val) ? hoveredPoint.val : hoveredPoint.val.toFixed(1)) : hoveredPoint.val)} {unit}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="hw-chart-footer">
        <span>-{recent.length * 2}s</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <span className="hw-chart-stat-pill">Avg: {formatVal ? formatVal(avgVal) : avgVal.toFixed(1)} {unit}</span>
          <span className="hw-chart-stat-pill">Peak: {formatVal ? formatVal(peakMax) : (Number.isInteger(peakMax) ? peakMax : peakMax.toFixed(1))} {unit}</span>
        </div>
        <span style={{ color, opacity: 0.9, fontWeight: 700 }}>Live ●</span>
      </div>
    </div>
  );
}
