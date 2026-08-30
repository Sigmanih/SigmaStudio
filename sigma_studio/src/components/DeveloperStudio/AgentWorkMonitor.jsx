// ==============================================================================
// AgentWorkMonitor.jsx — What the agent has actually done, as it does it
// Sigma Studio v8 — Developer Studio
// ==============================================================================
//
// The chat transcript shows what the agent *said*. This shows what it *did*:
// which files it has read and how much of each, which it has changed, which
// commands passed or failed, and whether the completion gate would currently
// let it declare the job finished.
//
// It renders the same ledger snapshot the model receives in its own prompt, so
// what the user is watching and what the agent is reasoning over cannot drift
// apart. When a run goes wrong, the discrepancy is usually visible here several
// turns before it becomes visible in the answer.

import React, { useState } from 'react';
import {
  Activity, FileCheck2, FilePlus2, Eye, TerminalSquare,
  ChevronDown, ChevronUp, AlertTriangle, ShieldCheck, ShieldAlert,
} from 'lucide-react';

const fmtDuration = (seconds) => {
  if (!Number.isFinite(seconds)) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${String(s).padStart(2, '0')}s`;
};

export default function AgentWorkMonitor({
  ledger,
  isLight = false,
  gateReason = null,
  truncationCount = 0,
}) {
  const [open, setOpen] = useState(true);

  if (!ledger) return null;

  const files = Array.isArray(ledger.files) ? ledger.files : [];
  const commands = Array.isArray(ledger.commands) ? ledger.commands : [];
  const changed = files.filter((f) => f.edits > 0 || f.writes > 0);
  const readOnly = files.filter((f) => f.reads > 0 && !f.edits && !f.writes);
  const failedCommands = commands.filter((c) => !c.ok);
  const lastCommand = commands.length ? commands[commands.length - 1] : null;

  const border = isLight ? '#d0d7de' : '#30363d';
  const surface = isLight ? '#ffffff' : '#0d1117';
  const subtle = isLight ? '#f6f8fa' : '#161b22';
  const text = isLight ? '#24292f' : '#f0f6fc';
  const muted = isLight ? '#57606a' : '#8b949e';
  const ok = '#3fb950';
  const bad = '#f85149';
  const accent = '#00f2fe';

  const canComplete = !gateReason && changed.length > 0 && !!lastCommand?.ok;

  const chip = (label, value, color) => (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 10,
        background: `${color}22`,
        color,
        fontSize: '0.62rem',
        fontWeight: 800,
        whiteSpace: 'nowrap',
      }}
    >
      {value} {label}
    </span>
  );

  return (
    <div
      style={{
        border: `1px solid ${border}`,
        borderRadius: 10,
        background: surface,
        marginBottom: 10,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
          padding: '8px 10px',
          background: subtle,
          border: 'none',
          borderBottom: open ? `1px solid ${border}` : 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <Activity size={13} color={accent} />
        <span style={{ fontSize: '0.68rem', fontWeight: 800, color: text }}>
          Stato del lavoro
        </span>
        <span style={{ fontSize: '0.60rem', color: muted }}>
          {fmtDuration(ledger.elapsed_s)}
        </span>

        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginLeft: 'auto' }}>
          {changed.length > 0 && chip('modificati', changed.length, ok)}
          {readOnly.length > 0 && chip('letti', readOnly.length, accent)}
          {failedCommands.length > 0 && chip('falliti', failedCommands.length, bad)}
          {truncationCount > 0 && chip('troncamenti', truncationCount, '#d29922')}
          {open ? <ChevronUp size={13} color={muted} /> : <ChevronDown size={13} color={muted} />}
        </div>
      </button>

      {open && (
        <div style={{ padding: '8px 10px', display: 'grid', gap: 10 }}>
          {/* Completion readiness — the same rule the backend gate applies. */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 6,
              padding: '6px 8px',
              borderRadius: 8,
              background: canComplete ? `${ok}18` : `${muted}18`,
            }}
          >
            {canComplete
              ? <ShieldCheck size={13} color={ok} style={{ flexShrink: 0, marginTop: 1 }} />
              : <ShieldAlert size={13} color={muted} style={{ flexShrink: 0, marginTop: 1 }} />}
            <span style={{ fontSize: '0.62rem', color: canComplete ? ok : muted, lineHeight: 1.45 }}>
              {canComplete
                ? 'Pronto a completare: ci sono modifiche reali e l’ultima verifica è passata.'
                : (gateReason || 'Non ancora completabile: servono modifiche ai file e una verifica riuscita.')}
            </span>
          </div>

          {changed.length > 0 && (
            <Section title="File modificati" isLight={isLight}>
              {changed.map((f) => (
                <Row key={f.path} isLight={isLight}>
                  {f.created
                    ? <FilePlus2 size={12} color={ok} style={{ flexShrink: 0 }} />
                    : <FileCheck2 size={12} color={accent} style={{ flexShrink: 0 }} />}
                  <code style={{ fontSize: '0.62rem', color: text, wordBreak: 'break-all' }}>{f.path}</code>
                  <span style={{ fontSize: '0.58rem', color: muted, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                    {f.created ? 'creato' : `${f.edits} edit`}
                    {f.total_lines ? ` · ${f.total_lines} righe` : ''}
                  </span>
                  {f.last_error && <AlertTriangle size={12} color={bad} style={{ flexShrink: 0 }} />}
                </Row>
              ))}
            </Section>
          )}

          {readOnly.length > 0 && (
            <Section title="File letti" isLight={isLight}>
              {readOnly.slice(0, 12).map((f) => (
                <Row key={f.path} isLight={isLight}>
                  <Eye size={12} color={muted} style={{ flexShrink: 0 }} />
                  <code style={{ fontSize: '0.62rem', color: muted, wordBreak: 'break-all' }}>{f.path}</code>
                  <span
                    style={{
                      fontSize: '0.58rem',
                      color: f.fully_read ? ok : '#d29922',
                      marginLeft: 'auto',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {f.fully_read ? 'integrale' : 'parziale'}
                  </span>
                </Row>
              ))}
            </Section>
          )}

          {commands.length > 0 && (
            <Section title="Comandi" isLight={isLight}>
              {commands.slice(-8).map((c, i) => (
                <Row key={`${c.command}-${i}`} isLight={isLight}>
                  <TerminalSquare size={12} color={c.ok ? ok : bad} style={{ flexShrink: 0 }} />
                  <code
                    style={{
                      fontSize: '0.62rem',
                      color: c.ok ? text : bad,
                      wordBreak: 'break-all',
                    }}
                  >
                    {c.command}
                  </code>
                  <span style={{ fontSize: '0.58rem', color: muted, marginLeft: 'auto' }}>
                    exit {c.returncode}
                  </span>
                </Row>
              ))}
            </Section>
          )}

          {Array.isArray(ledger.failures) && ledger.failures.length > 0 && (
            <Section title="Errori recenti" isLight={isLight}>
              {ledger.failures.slice(-4).map((f, i) => (
                <Row key={i} isLight={isLight}>
                  <AlertTriangle size={12} color="#d29922" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span style={{ fontSize: '0.60rem', color: muted, lineHeight: 1.45 }}>{f}</span>
                </Row>
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, isLight, children }) {
  return (
    <div>
      <div
        style={{
          fontSize: '0.58rem',
          fontWeight: 800,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: isLight ? '#57606a' : '#8b949e',
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      <div style={{ display: 'grid', gap: 3 }}>{children}</div>
    </div>
  );
}

function Row({ isLight, children }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 6px',
        borderRadius: 6,
        background: isLight ? '#f6f8fa' : '#161b22',
        minWidth: 0,
      }}
    >
      {children}
    </div>
  );
}
