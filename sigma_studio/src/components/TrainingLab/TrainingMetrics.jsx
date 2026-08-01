import React, { useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import InfoHint from './InfoHint';

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

function StatTile({ label, value, sub, guide, accent }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: '10px', padding: '7px 10px', minWidth: 0,
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
        <InfoHint entry={guide} />
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

// Quanta parte del run si vede in una schermata, quando si stringe la finestra.
const ZOOMS = [
  { id: 1, label: 'tutto' },
  { id: 0.5, label: '½' },
  { id: 0.25, label: '¼' },
  { id: 0.1, label: '10%' },
];

function LossChart({ trainPoints, evalPoints, avgPoints, bestEvalStep }) {
  const [hover, setHover] = useState(null);
  // `span` è la frazione di run inquadrata, `end` dove finisce la finestra:
  // su un run da migliaia di step la curva iniziale si schiaccia in due pixel,
  // e senza poterci tornare sopra la parte interessante è illeggibile.
  const [span, setSpan] = useState(1);
  const [end, setEnd] = useState(1);
  const svgRef = useRef(null);

  // Margine destro generoso: è dove vivono le etichette dirette delle serie,
  // che tolgono all'occhio il salto continuo fra curva e legenda.
  const W = 1120, H = 380, padL = 58, padR = 112, padT = 18, padB = 32;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const all = [...trainPoints, ...evalPoints];
  const geometry = useMemo(() => {
    if (!all.length) return null;
    const fullMin = Math.min(...all.map(p => p.x));
    const fullMax = Math.max(...all.map(p => p.x));
    const width = Math.max(1e-9, (fullMax - fullMin) * span);
    const xMax = fullMin + (fullMax - fullMin) * end;
    const xMin = Math.max(fullMin, xMax - width);

    // La scala verticale segue la finestra: guardare la coda di un run non deve
    // significare vedere una riga piatta perché il picco iniziale schiaccia tutto.
    const visible = all.filter(p => p.x >= xMin && p.x <= xMax);
    const scope = visible.length > 1 ? visible : all;
    const yMin = Math.min(...scope.map(p => p.y));
    const yMax = Math.max(...scope.map(p => p.y));
    const yPad = (yMax - yMin) * 0.12 || 0.1;
    const lo = Math.max(0, yMin - yPad), hi = yMax + yPad;
    const sx = (x) => padL + ((x - xMin) / Math.max(1e-9, xMax - xMin)) * chartW;
    const sy = (y) => padT + chartH - ((y - lo) / Math.max(1e-9, hi - lo)) * chartH;
    return { xMin, xMax, fullMin, fullMax, lo, hi, sx, sy };
  }, [all.length, trainPoints, evalPoints, span, end]);

  if (!geometry) {
    return (
      <div className="training-chart-empty">
        📈 Le curve appariranno appena il run emette il primo logging step
      </div>
    );
  }

  const { xMin, xMax, fullMin, fullMax, lo, hi, sx, sy } = geometry;
  // Un punto appena fuori per lato tiene la linea agganciata al bordo invece di
  // farla partire dal vuoto.
  const clip = (pts) => {
    const inside = pts.filter(p => p.x >= xMin && p.x <= xMax);
    if (!inside.length) return [];
    const before = pts.filter(p => p.x < xMin).slice(-1);
    const after = pts.filter(p => p.x > xMax).slice(0, 1);
    return [...before, ...inside, ...after];
  };
  const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(' ');
  const area = (pts) => pts.length
    ? `${path(pts)} L${sx(pts[pts.length - 1].x).toFixed(1)},${(padT + chartH).toFixed(1)} `
      + `L${sx(pts[0].x).toFixed(1)},${(padT + chartH).toFixed(1)} Z`
    : '';
  const yTicks = [0, 0.2, 0.4, 0.6, 0.8, 1].map(t => ({ v: lo + t * (hi - lo), y: padT + chartH - t * chartH }));
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ v: Math.round(xMin + t * (xMax - xMin)), x: padL + t * chartW }));

  // Etichette dirette: si posano sull'ultimo punto di ciascuna serie e, se si
  // sovrappongono, la seconda viene scostata quel tanto che basta a leggerle.
  const endLabels = [];
  const lastVisible = (pts) => { const c = clip(pts); return c.length ? c[c.length - 1] : null; };
  const lastAvg = lastVisible(avgPoints);
  const lastEval = lastVisible(evalPoints);
  if (lastAvg) {
    endLabels.push({ y: sy(lastAvg.y), color: SERIES.train.color,
                     label: SERIES.train.label, value: lastAvg.y });
  }
  if (lastEval) {
    endLabels.push({ y: sy(lastEval.y), color: SERIES.eval.color,
                     label: SERIES.eval.label, value: lastEval.y });
  }
  endLabels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < endLabels.length; i++) {
    const gap = endLabels[i].y - endLabels[i - 1].y;
    if (gap < 26) endLabels[i].y = endLabels[i - 1].y + 26;
  }

  const best = bestEvalStep != null && evalPoints.length
    ? evalPoints.reduce((b, p) => (Math.abs(p.x - bestEvalStep) < Math.abs(b.x - bestEvalStep) ? p : b))
    : null;

  const onWheel = (e) => {
    e.preventDefault();
    setSpan(s => Math.min(1, Math.max(0.02, s * (e.deltaY > 0 ? 1.25 : 0.8))));
  };

  const onDrag = (e) => {
    if (e.buttons !== 1 || span >= 1) return;
    // Trascinare a destra porta indietro nel tempo: la finestra segue la mano.
    const rect = svgRef.current.getBoundingClientRect();
    const frac = (e.movementX / rect.width) * span;
    setEnd(v => Math.min(1, Math.max(span, v - frac)));
  };

  const onMove = (e) => {
    onDrag(e);
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    if (x < padL || x > W - padR) return setHover(null);
    const step = xMin + ((x - padL) / chartW) * (xMax - xMin);
    const near = (pts) => pts.length
      ? pts.reduce((b, p) => (Math.abs(p.x - step) < Math.abs(b.x - step) ? p : b))
      : null;
    setHover({ step: Math.round(step), train: near(trainPoints), avg: near(avgPoints), ev: near(evalPoints) });
  };

  const windowed = span < 1;
  return (
    <div style={{ position: 'relative' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px',
        fontSize: '0.58rem', color: 'var(--text-dark)', flexWrap: 'wrap',
      }}>
        <span>finestra</span>
        {ZOOMS.map(z => (
          <button
            key={z.id}
            onClick={() => { setSpan(z.id); if (z.id === 1) setEnd(1); }}
            style={{
              padding: '2px 8px', borderRadius: '6px', cursor: 'pointer',
              border: '1px solid ' + (span === z.id ? 'rgba(0,210,255,0.3)' : 'rgba(255,255,255,0.07)'),
              background: span === z.id ? 'rgba(0,210,255,0.07)' : 'transparent',
              color: span === z.id ? 'var(--primary)' : 'var(--text-dim)',
              fontSize: '0.58rem', fontWeight: 600,
            }}
          >
            {z.label}
          </button>
        ))}
        <span style={{ marginLeft: '4px' }}>
          step {Math.round(xMin)}–{Math.round(xMax)} su {Math.round(fullMax)}
        </span>
        <span style={{ marginLeft: 'auto' }}>
          rotella per stringere · trascina per scorrere
        </span>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="training-metrics-svg"
        preserveAspectRatio="xMidYMid meet"
        onMouseMove={onMove}
        onWheel={onWheel}
        style={{ cursor: span < 1 ? 'ew-resize' : 'default' }}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Andamento della training loss e della validation loss"
      >
        <defs>
          <linearGradient id="lossArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES.train.color} stopOpacity="0.16" />
            <stop offset="100%" stopColor={SERIES.train.color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={padL} y1={t.y} x2={W - padR} y2={t.y}
                  stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
            <text x={padL - 9} y={t.y + 3} textAnchor="end"
                  fill="var(--text-dark)" fontSize="10" fontFamily="JetBrains Mono, monospace">
              {t.v.toFixed(2)}
            </text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <text key={i} x={t.x} y={H - 11} textAnchor="middle"
                fill="var(--text-dark)" fontSize="10" fontFamily="JetBrains Mono, monospace">
            {t.v}
          </text>
        ))}
        <text x={padL + chartW / 2} y={H - 1} textAnchor="middle"
              fill="var(--text-dark)" fontSize="9">step</text>

        <path d={area(clip(avgPoints))} fill="url(#lossArea)" />
        {/* loss grezza: contesto, non la linea da leggere */}
        <path d={path(clip(trainPoints))} fill="none" stroke={SERIES.train.color}
              strokeWidth="1" opacity="0.2" />
        <path d={path(clip(avgPoints))} fill="none" stroke={SERIES.train.color}
              strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {evalPoints.length > 0 && (
          <>
            <path d={path(clip(evalPoints))} fill="none" stroke={SERIES.eval.color}
                  strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {clip(evalPoints).map((p, i) => (
              <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="4"
                      fill={SERIES.eval.color} stroke="#0a0c1a" strokeWidth="2" />
            ))}
          </>
        )}

        {/* Il minimo della validation è il checkpoint da tenere: è l'unico
            punto del grafico su cui si prende una decisione, quindi è marcato. */}
        {best && best.x >= xMin && best.x <= xMax && (
          <g>
            <line x1={sx(best.x)} y1={padT} x2={sx(best.x)} y2={padT + chartH}
                  stroke={SERIES.eval.color} strokeWidth="1" strokeDasharray="2 4" opacity="0.55" />
            <circle cx={sx(best.x)} cy={sy(best.y)} r="6" fill="none"
                    stroke={SERIES.eval.color} strokeWidth="2" />
            <text x={sx(best.x)} y={padT - 5} textAnchor="middle"
                  fill="var(--text-dim)" fontSize="9.5">
              miglior checkpoint · step {Math.round(best.x)}
            </text>
          </g>
        )}

        {/* Etichette dirette: identità senza dover rimbalzare sulla legenda.
            Il testo resta in inchiostro neutro, il colore lo porta il pallino. */}
        {endLabels.map((l, i) => (
          <g key={i}>
            <circle cx={W - padR + 8} cy={l.y} r="3.5" fill={l.color} />
            <text x={W - padR + 16} y={l.y - 2} fill="var(--text-dim)" fontSize="10">
              {l.label}
            </text>
            <text x={W - padR + 16} y={l.y + 10} fill="var(--text)" fontSize="10.5"
                  fontFamily="JetBrains Mono, monospace" fontWeight="700">
              {fmt(l.value, 3)}
            </text>
          </g>
        ))}

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

      {windowed && (
        <div
          onClick={e => {
            // Clic sulla minimappa: la finestra si centra dove hai indicato.
            const rect = e.currentTarget.getBoundingClientRect();
            const at = (e.clientX - rect.left) / rect.width;
            setEnd(Math.min(1, Math.max(span, at + span / 2)));
          }}
          style={{
            position: 'relative', height: '7px', margin: '3px 0 5px', cursor: 'pointer',
            background: 'rgba(255,255,255,0.04)', borderRadius: '4px',
          }}
        >
          <span style={{
            position: 'absolute', top: 0, bottom: 0, borderRadius: '4px',
            left: `${Math.max(0, (end - span)) * 100}%`, width: `${span * 100}%`,
            background: 'rgba(0,210,255,0.28)', border: '1px solid rgba(0,210,255,0.4)',
          }} />
        </div>
      )}

      <div style={{
        display: 'flex', gap: '14px', justifyContent: 'center', flexWrap: 'wrap',
        fontSize: '0.6rem', color: 'var(--text-dim)',
      }}>
        {[SERIES.train, SERIES.eval].map(s => (
          <span key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '13px', height: '2px', borderRadius: '1px', background: s.color }} />
            {s.label}
          </span>
        ))}
        <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-dark)' }}>
          <span style={{ width: '13px', height: '1px', background: SERIES.train.color, opacity: 0.35 }} />
          loss grezza per step
        </span>
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
            display: 'flex', gap: '9px', padding: '8px 11px', borderRadius: '10px',
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
    <div style={{ marginTop: '10px' }}>
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
        <LossChart trainPoints={trainPoints} evalPoints={evalPoints} avgPoints={avgPoints}
                   bestEvalStep={summary.best_eval_step} />
      </div>

      <div className="training-metrics-split">
      <div style={{
        display: 'grid', gap: '6px', marginTop: '8px', alignContent: 'start',
        gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))',
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
        <div style={{ marginTop: '8px' }}>
          <div className="training-chart-title">🔎 Valutazione automatica</div>
          <Diagnostics verdicts={metrics.diagnostics} />
        </div>
      )}
      </div>

      <RunHistory runs={metrics?.runs} />
    </div>
  );
}
