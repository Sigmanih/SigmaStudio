import React, { useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle, HelpCircle } from 'lucide-react';

// ==============================================================================
// TrainingMetrics — curve di loss, aggregati e diagnosi automatica di un run
// ==============================================================================
// I due colori delle serie non sono quelli di accento dell'app: cyan e viola,
// affiancati su fondo scuro, hanno una separazione ΔE di 7.5 in deuteranopia,
// sotto la soglia sicura. Questa coppia passa banda di luminosità, croma,
// separazione CVD (9.4 deutan / 30.2 tritan) e contrasto sul fondo.
const SERIES = {
  train: { color: '#0e9ec4', label: 'Training loss' },
  eval:  { color: '#d8598f', label: 'Validation loss' },
};

const LEVEL_STYLE = {
  critical: { icon: XCircle,      color: 'var(--error)',   bg: 'rgba(255,85,85,0.08)',  border: 'rgba(255,85,85,0.22)' },
  warning:  { icon: AlertTriangle, color: 'var(--warning)', bg: 'rgba(255,184,108,0.08)', border: 'rgba(255,184,108,0.22)' },
  good:     { icon: CheckCircle2, color: 'var(--success)', bg: 'rgba(63,185,80,0.08)',  border: 'rgba(63,185,80,0.22)' },
  info:     { icon: Info,         color: 'var(--text-dim)', bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.08)' },
};

const fmt = (v, digits = 4) =>
  (v === null || v === undefined || Number.isNaN(v)) ? '—' : Number(v).toFixed(digits);

const pct = (v) =>
  (v === null || v === undefined) ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

// Media mobile: la loss istantanea di un singolo step oscilla troppo perché la
// tendenza si veda a occhio. La curva grezza resta disegnata sotto, in trasparenza.
function movingAverage(points, window) {
  if (points.length < window) return points;
  return points.map((p, i) => {
    const from = Math.max(0, i - window + 1);
    const slice = points.slice(from, i + 1);
    return { x: p.x, y: slice.reduce((s, q) => s + q.y, 0) / slice.length };
  });
}

// ------------------------------------------------------------------ tooltip

function Explain({ entry }) {
  const [open, setOpen] = useState(false);
  if (!entry) return null;
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', cursor: 'help' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <HelpCircle size={11} style={{ color: 'var(--text-dark)' }} />
      {open && (
        <span style={{
          position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
          marginBottom: '6px', width: '280px', zIndex: 40, textAlign: 'left',
          background: 'rgba(6,8,18,0.98)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: '10px', padding: '10px 12px', boxShadow: '0 12px 32px rgba(0,0,0,0.6)',
          fontSize: '0.63rem', lineHeight: 1.55, color: 'var(--text-dim)', fontWeight: 400,
        }}>
          <div style={{ color: 'var(--text)', fontWeight: 700, marginBottom: '5px' }}>{entry.label}</div>
          <div style={{ marginBottom: '6px' }}>{entry.what}</div>
          <div><span style={{ color: 'var(--success)' }}>Bene:</span> {entry.good}</div>
          <div><span style={{ color: 'var(--warning)' }}>Male:</span> {entry.bad}</div>
          <div><span style={{ color: 'var(--primary)' }}>Ottimo:</span> {entry.optimal}</div>
        </span>
      )}
    </span>
  );
}

function StatTile({ label, value, sub, guide, accent }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '10px', padding: '10px 12px', minWidth: 0,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '4px',
        fontSize: '0.58rem', color: 'var(--text-dark)', textTransform: 'uppercase',
        letterSpacing: '0.04em', fontWeight: 700,
      }}>
        {accent && <span style={{
          width: '8px', height: '2px', borderRadius: '1px', background: accent, flexShrink: 0,
        }} />}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
        <Explain entry={guide} />
      </div>
      <div style={{
        fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)',
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.58rem', color: 'var(--text-dim)', marginTop: '2px' }}>{sub}</div>}
    </div>
  );
}

// -------------------------------------------------------------------- chart

function LossChart({ trainPoints, evalPoints, avgPoints }) {
  const [hover, setHover] = useState(null);
  const svgRef = useRef(null);

  const W = 760, H = 300, padL = 52, padR = 18, padT = 16, padB = 34;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const all = [...trainPoints, ...evalPoints];
  const geometry = useMemo(() => {
    if (!all.length) return null;
    const xMin = Math.min(...all.map(p => p.x));
    const xMax = Math.max(...all.map(p => p.x));
    const yMin = Math.min(...all.map(p => p.y));
    const yMax = Math.max(...all.map(p => p.y));
    const yPad = (yMax - yMin) * 0.12 || 0.1;
    const lo = Math.max(0, yMin - yPad), hi = yMax + yPad;
    const sx = (x) => padL + ((x - xMin) / Math.max(1e-9, xMax - xMin)) * chartW;
    const sy = (y) => padT + chartH - ((y - lo) / Math.max(1e-9, hi - lo)) * chartH;
    return { xMin, xMax, lo, hi, sx, sy };
  }, [all.length, trainPoints, evalPoints]);

  if (!geometry) {
    return (
      <div className="training-chart-empty">
        📈 Le curve appariranno appena il run emette il primo logging step
      </div>
    );
  }

  const { xMin, xMax, lo, hi, sx, sy } = geometry;
  const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(' ');
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ v: lo + t * (hi - lo), y: padT + chartH - t * chartH }));
  const xTicks = [0, 0.5, 1].map(t => ({ v: Math.round(xMin + t * (xMax - xMin)), x: padL + t * chartW }));

  const onMove = (e) => {
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    if (x < padL || x > W - padR) return setHover(null);
    const step = xMin + ((x - padL) / chartW) * (xMax - xMin);
    const near = (pts) => pts.length
      ? pts.reduce((b, p) => (Math.abs(p.x - step) < Math.abs(b.x - step) ? p : b))
      : null;
    setHover({ step: Math.round(step), train: near(trainPoints), avg: near(avgPoints), ev: near(evalPoints) });
  };

  return (
    <div style={{ position: 'relative' }}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="training-metrics-svg"
        preserveAspectRatio="xMidYMid meet"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Andamento della training loss e della validation loss"
      >
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={padL} y1={t.y} x2={W - padR} y2={t.y}
                  stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
            <text x={padL - 8} y={t.y + 3} textAnchor="end"
                  fill="var(--text-dark)" fontSize="9" fontFamily="JetBrains Mono, monospace">
              {t.v.toFixed(2)}
            </text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <text key={i} x={t.x} y={H - 12} textAnchor="middle"
                fill="var(--text-dark)" fontSize="9" fontFamily="JetBrains Mono, monospace">
            step {t.v}
          </text>
        ))}

        {/* loss grezza: contesto, non la linea da leggere */}
        <path d={path(trainPoints)} fill="none" stroke={SERIES.train.color}
              strokeWidth="1" opacity="0.22" />
        <path d={path(avgPoints)} fill="none" stroke={SERIES.train.color}
              strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {evalPoints.length > 0 && (
          <>
            <path d={path(evalPoints)} fill="none" stroke={SERIES.eval.color}
                  strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {evalPoints.map((p, i) => (
              <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="4"
                      fill={SERIES.eval.color} stroke="#0a0c1a" strokeWidth="2" />
            ))}
          </>
        )}

        {hover && (
          <line x1={sx(hover.step)} y1={padT} x2={sx(hover.step)} y2={padT + chartH}
                stroke="rgba(255,255,255,0.22)" strokeWidth="1" strokeDasharray="3 3" />
        )}
      </svg>

      {hover && (
        <div style={{
          position: 'absolute', top: '8px', right: '20px', pointerEvents: 'none',
          background: 'rgba(6,8,18,0.97)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: '9px', padding: '8px 11px', fontSize: '0.63rem', lineHeight: 1.6,
          fontFamily: 'JetBrains Mono, monospace', boxShadow: '0 10px 28px rgba(0,0,0,0.55)',
        }}>
          <div style={{ color: 'var(--text-dark)', marginBottom: '3px' }}>step {hover.step}</div>
          {hover.avg && (
            <div style={{ color: 'var(--text)' }}>
              <span style={{ display: 'inline-block', width: '8px', height: '2px', background: SERIES.train.color, marginRight: '6px', verticalAlign: 'middle' }} />
              media {fmt(hover.avg.y)}
              {hover.train && <span style={{ color: 'var(--text-dark)' }}> · grezza {fmt(hover.train.y)}</span>}
            </div>
          )}
          {hover.ev && (
            <div style={{ color: 'var(--text)' }}>
              <span style={{ display: 'inline-block', width: '8px', height: '2px', background: SERIES.eval.color, marginRight: '6px', verticalAlign: 'middle' }} />
              validation {fmt(hover.ev.y)}
              <span style={{ color: 'var(--text-dark)' }}> · ppl {fmt(Math.exp(Math.min(hover.ev.y, 20)), 2)}</span>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', marginTop: '4px', fontSize: '0.62rem' }}>
        {[SERIES.train, SERIES.eval].map(s => (
          <span key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-dim)' }}>
            <span style={{ width: '14px', height: '2px', borderRadius: '1px', background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------- panel

function Diagnostics({ verdicts }) {
  if (!verdicts?.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {verdicts.map((v, i) => {
        const style = LEVEL_STYLE[v.level] || LEVEL_STYLE.info;
        const Icon = style.icon;
        return (
          <div key={i} style={{
            display: 'flex', gap: '10px', padding: '10px 12px', borderRadius: '10px',
            background: style.bg, border: `1px solid ${style.border}`,
          }}>
            <Icon size={14} style={{ color: style.color, flexShrink: 0, marginTop: '1px' }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: style.color, marginBottom: '3px' }}>
                {v.title}
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', lineHeight: 1.55 }}>{v.detail}</div>
              {v.action && (
                <div style={{ fontSize: '0.65rem', color: 'var(--text)', marginTop: '5px', lineHeight: 1.55 }}>
                  → {v.action}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RunHistory({ runs }) {
  if (!runs?.length) return null;
  return (
    <div style={{ marginTop: '16px' }}>
      <div className="training-chart-title">🕘 Esecuzioni di questo job ({runs.length})</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.63rem', minWidth: '520px' }}>
          <thead>
            <tr style={{ color: 'var(--text-dark)', textAlign: 'left' }}>
              {['#', 'Avvio', 'Dataset', 'Stato', 'Step', 'Loss finale'].map(h => (
                <th key={h} style={{ padding: '6px 8px', fontWeight: 700, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((r, i) => (
              <tr key={i} style={{ color: 'var(--text-dim)' }}>
                <td style={{ padding: '6px 8px' }}>{r.index ?? i + 1}</td>
                <td style={{ padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace' }}>{r.started_at || '—'}</td>
                <td style={{ padding: '6px 8px' }}>{r.dataset_name || r.dataset_id || '—'}</td>
                <td style={{ padding: '6px 8px' }}>{r.status || '—'}</td>
                <td style={{ padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace' }}>{r.steps ?? '—'}</td>
                <td style={{ padding: '6px 8px', fontFamily: 'JetBrains Mono, monospace' }}>{fmt(r.final_loss)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------- main

export default function TrainingMetrics({ metrics }) {
  const history = metrics?.history || [];
  const summary = metrics?.summary || {};
  const guide = metrics?.guide || {};

  const { trainPoints, evalPoints, avgPoints } = useMemo(() => {
    const train = [], evals = [];
    for (const r of history) {
      if (typeof r.loss === 'number' && Number.isFinite(r.loss)) train.push({ x: r.step ?? train.length, y: r.loss });
      if (typeof r.eval_loss === 'number' && Number.isFinite(r.eval_loss)) evals.push({ x: r.step ?? evals.length, y: r.eval_loss });
    }
    return {
      trainPoints: train,
      evalPoints: evals,
      avgPoints: movingAverage(train, Math.max(3, Math.round(train.length / 25))),
    };
  }, [history]);

  return (
    <div>
      <div className="training-chart-container">
        <div className="training-chart-title">
          📈 Loss nel tempo ({trainPoints.length} step · {evalPoints.length} valutazioni)
        </div>
        <LossChart trainPoints={trainPoints} evalPoints={evalPoints} avgPoints={avgPoints} />
      </div>

      <div style={{
        display: 'grid', gap: '8px', marginTop: '12px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
      }}>
        <StatTile label="Loss corrente" value={fmt(summary.last_loss)} guide={guide.loss}
                  accent={SERIES.train.color}
                  sub={summary.min_loss != null ? `minimo ${fmt(summary.min_loss)}` : null} />
        <StatTile label="Loss media" value={fmt(summary.avg_loss)} guide={guide.avg_loss}
                  accent={SERIES.train.color} sub="ultimo 10% degli step" />
        <StatTile label="Validation loss" value={fmt(summary.last_eval_loss)} guide={guide.eval_loss}
                  accent={SERIES.eval.color}
                  sub={summary.best_eval_loss != null
                    ? `migliore ${fmt(summary.best_eval_loss)} @ step ${Math.round(summary.best_eval_step)}`
                    : 'in attesa della prima valutazione'} />
        <StatTile label="Perplexity" value={fmt(summary.perplexity, 2)} guide={guide.perplexity}
                  accent={SERIES.eval.color}
                  sub={summary.best_perplexity != null ? `migliore ${fmt(summary.best_perplexity, 2)}` : null} />
        <StatTile label="Divario train/val" value={fmt(summary.gap)} guide={guide.gap}
                  sub="quanto è avvantaggiato sui dati già visti" />
        <StatTile label="Tendenza" value={pct(summary.trend)} guide={guide.loss}
                  sub="variazione nella finestra recente" />
      </div>

      {metrics?.diagnostics?.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div className="training-chart-title">🔎 Valutazione automatica</div>
          <Diagnostics verdicts={metrics.diagnostics} />
        </div>
      )}

      <RunHistory runs={metrics?.runs} />
    </div>
  );
}
