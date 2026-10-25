// ==============================================================================
// AgentWorkMonitor.jsx — What the agent has actually done, as it does it
// Sigma Studio v8 — Developer Studio Deep Inspector
// ==============================================================================
//
// The chat transcript shows what the agent *said*. This shows what it *did*:
// which files it has read and how much of each, which it has changed, live diffs,
// which commands passed or failed, and whether the completion gate would currently
// let it declare the job finished.

import React, { useState } from 'react';
import {
  Activity, FileCheck2, FilePlus2, Eye, TerminalSquare,
  ChevronDown, ChevronUp, AlertTriangle, ShieldCheck, ShieldAlert,
  Code2, CheckCircle2, Search, FileDiff, Sparkles, Terminal
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
  resumedFrom = null,
  runMetrics = null,
  diario = [],
  runReport = null,
}) {
  const [open, setOpen] = useState(true);
  const [expandedDiffFile, setExpandedDiffFile] = useState(null);
  const [expandedCommandIdx, setExpandedCommandIdx] = useState(null);

  if (!ledger && !runReport && !diario.length) return null;

  const stato = ledger || {};
  const files = Array.isArray(stato.files) ? stato.files : [];
  const commands = Array.isArray(stato.commands) ? stato.commands : [];
  const diffs = stato.diffs || {};
  const changed = files.filter((f) => f.edits > 0 || f.writes > 0);
  const readOnly = files.filter((f) => f.reads > 0 && !f.edits && !f.writes);
  const failedCommands = commands.filter((c) => !c.ok);
  const lastCommand = commands.length ? commands[commands.length - 1] : null;
  const isExploration = Boolean(stato.is_exploration);
  // I criteri di accettazione: l'unica cosa che dica se il lavoro e finito
  // davvero, invece che soltanto interrotto in un punto verde.
  const criteria = Array.isArray(stato.requirements) ? stato.requirements : [];
  const criteriaMet = criteria.filter((c) => c.met).length;

  const border = isLight ? '#d0d7de' : '#30363d';
  const surface = isLight ? '#ffffff' : '#0d1117';
  const subtle = isLight ? '#f6f8fa' : '#161b22';
  const text = isLight ? '#24292f' : '#f0f6fc';
  const muted = isLight ? '#57606a' : '#8b949e';
  const ok = '#3fb950';
  const bad = '#f85149';
  const accent = '#00f2fe';
  const purple = '#a371f7';

  const canComplete = isExploration
    ? (!gateReason && (readOnly.length > 0 || changed.length > 0))
    : (!gateReason && changed.length > 0 && !!lastCommand?.ok);

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
      {/* Il consuntivo: cosa è stato fatto, come funziona, come lo sappiamo.
          Costruito dai fatti registrati nel ledger, non da ciò che il modello
          dice di aver fatto. Sta in cima perché è la risposta alla domanda
          che uno si fa per prima. */}
      {runReport && (
        <div style={{
          padding: '10px 12px',
          borderBottom: `1px solid ${border}`,
          background: runReport.reached
            ? 'rgba(63, 185, 80, 0.08)'
            : 'rgba(210, 153, 34, 0.08)',
        }}>
          <div style={{
            fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.04em',
            color: runReport.reached ? '#3fb950' : '#d29922', marginBottom: 6,
          }}>
            {runReport.reached ? 'LAVORO CHIUSO' : 'LAVORO NON CHIUSO'}
          </div>
          <pre style={{
            margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            fontSize: '0.66rem', lineHeight: 1.55, color: text,
            fontFamily: 'inherit', maxHeight: 320, overflowY: 'auto',
          }}>{runReport.text}</pre>
        </div>
      )}

      {/* Il diario: lo stesso racconto un pezzo per volta, mentre succede.
          Chi guarda non può aspettare il consuntivo, e non deve leggere
          `tool_result` grezzi per capire a che punto siamo. */}
      {diario.length > 0 && (
        <details style={{ borderBottom: `1px solid ${border}` }}>
          <summary style={{
            padding: '7px 10px', cursor: 'pointer', fontSize: '0.64rem',
            fontWeight: 700, color: text, background: subtle,
          }}>
            Diario · {diario.length} passi
          </summary>
          <div style={{ maxHeight: 220, overflowY: 'auto', padding: '6px 10px' }}>
            {diario.slice().reverse().map((riga, i) => (
              <div key={diario.length - i} style={{
                fontSize: '0.64rem', lineHeight: 1.5, color: text,
                padding: '2px 0', opacity: i === 0 ? 1 : 0.82,
              }}>
                <span style={{ opacity: 0.5, marginRight: 6 }}>
                  {diario.length - i}.
                </span>
                {riga.text}
              </div>
            ))}
          </div>
        </details>
      )}

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
        
        {/* Task Mode Badge */}
        <span
          style={{
            fontSize: '0.58rem',
            fontWeight: 800,
            padding: '1px 6px',
            borderRadius: 4,
            background: isExploration ? `${purple}22` : `${accent}22`,
            color: isExploration ? purple : accent,
            border: `1px solid ${isExploration ? `${purple}44` : `${accent}44`}`,
          }}
        >
          {isExploration ? '🔍 Modalità Analisi / Audit' : '⚡ Modalità Sviluppo / Coding'}
        </span>

        <span style={{ fontSize: '0.60rem', color: muted }}>
          {fmtDuration(stato.elapsed_s)}
        </span>

        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginLeft: 'auto' }}>
          {criteria.length > 0 && chip(
            'criteri',
            `${criteriaMet}/${criteria.length}`,
            criteriaMet === criteria.length ? ok : '#d29922',
          )}
          {changed.length > 0 && chip('modificati', changed.length, ok)}
          {readOnly.length > 0 && chip('letti', readOnly.length, accent)}
          {failedCommands.length > 0 && chip('falliti', failedCommands.length, bad)}
          {truncationCount > 0 && chip('troncamenti', truncationCount, '#d29922')}
          {runMetrics?.toolRefusals > 0 && chip('non permessi', runMetrics.toolRefusals, '#d29922')}
          {resumedFrom && chip('ripresi', resumedFrom.files, purple)}
          {open ? <ChevronUp size={13} color={muted} /> : <ChevronDown size={13} color={muted} />}
        </div>
      </button>

      {open && (
        <div style={{ padding: '8px 10px', display: 'grid', gap: 10 }}>
          {/* Completion readiness */}
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
                ? (isExploration
                    ? 'Pronto a completare: consultazione file e sintesi grounded completate con successo.'
                    : 'Pronto a completare: modifiche applicate e ultima verifica terminata con successo.')
                : (gateReason || (isExploration 
                    ? 'In corso: raccogli informazioni sui file con read_file o search_code.'
                    : 'Non ancora completabile: servono modifiche ai file e una verifica riuscita.'))}
            </span>
          </div>

          {/* I criteri di accettazione, dichiarati prima di cominciare */}
          {criteria.length > 0 && (
            <Section title={`Criteri di accettazione (${criteriaMet}/${criteria.length})`} isLight={isLight}>
              {stato.intake && (
                <Row isLight={isLight}>
                  <span style={{ fontSize: '0.62rem', color: muted, lineHeight: 1.45 }}>
                    {stato.intake}
                  </span>
                </Row>
              )}
              {criteria.map((c) => (
                <Row key={c.id} isLight={isLight}>
                  {c.met
                    ? <ShieldCheck size={12} color={ok} style={{ flexShrink: 0 }} />
                    : <ShieldAlert size={12} color={'#d29922'} style={{ flexShrink: 0 }} />}
                  <span style={{ fontSize: '0.62rem', color: c.met ? text : muted, lineHeight: 1.45 }}>
                    {c.text}
                    {c.met && c.evidence && (
                      <span style={{ display: 'block', color: muted, fontSize: '0.58rem' }}>
                        prova: {c.evidence}
                      </span>
                    )}
                  </span>
                </Row>
              ))}
            </Section>
          )}

          {/* Stato ritrovato all'avvio: spiega perche' l'agente non rilegge */}
          {resumedFrom && (
            <Row isLight={isLight}>
              <span style={{ fontSize: '0.62rem', color: purple }}>
                ↺ Sessione ripresa dal disco: {resumedFrom.files} file gia noti
                {resumedFrom.commands > 0 ? `, ${resumedFrom.commands} comandi` : ''}.
              </span>
            </Row>
          )}

          {/* Consuntivo dell'ultimo run */}
          {runMetrics && (
            <Section title="Consuntivo del run" isLight={isLight}>
              <Row isLight={isLight}>
                <span style={{ fontSize: '0.62rem', color: muted }}>
                  {runMetrics.turns} turni · {runMetrics.generatedTokens} token generati
                  {runMetrics.elapsedS ? ` · ${fmtDuration(runMetrics.elapsedS)}` : ''}
                </span>
              </Row>
              <Row isLight={isLight}>
                <span style={{ fontSize: '0.62rem', color: muted }}>
                  {runMetrics.toolCalls} chiamate a tool
                  {runMetrics.toolFailures > 0 ? ` · ${runMetrics.toolFailures} fallite` : ''}
                  {runMetrics.toolRefusals > 0 ? ` · ${runMetrics.toolRefusals} non permesse` : ''}
                </span>
              </Row>
              {runMetrics.exhaustedTurns && (
                <Row isLight={isLight}>
                  <span style={{ fontSize: '0.62rem', color: '#d29922' }}>
                    Turni esauriti prima del completamento: l'obiettivo era piu
                    grande del budget, non necessariamente sbagliato.
                  </span>
                </Row>
              )}
            </Section>
          )}

          {/* Modified files and live Diff Viewer */}
          {changed.length > 0 && (
            <Section title="File modificati & Live Diffs" isLight={isLight}>
              {changed.map((f) => {
                const diffText = f.diff || diffs[f.path];
                const isExpanded = expandedDiffFile === f.path;
                return (
                  <div key={f.path} style={{ display: 'grid', gap: 4 }}>
                    <Row isLight={isLight}>
                      {f.created
                        ? <FilePlus2 size={12} color={ok} style={{ flexShrink: 0 }} />
                        : <FileCheck2 size={12} color={accent} style={{ flexShrink: 0 }} />}
                      <code style={{ fontSize: '0.62rem', color: text, wordBreak: 'break-all' }}>{f.path}</code>
                      <span style={{ fontSize: '0.58rem', color: muted, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                        {f.created ? 'creato' : `${f.edits} edit`}
                        {f.total_lines ? ` · ${f.total_lines} righe` : ''}
                      </span>
                      {diffText && (
                        <button
                          type="button"
                          onClick={() => setExpandedDiffFile(isExpanded ? null : f.path)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 3,
                            padding: '2px 6px',
                            borderRadius: 4,
                            background: isExpanded ? `${accent}33` : `${subtle}`,
                            border: `1px solid ${accent}55`,
                            color: accent,
                            fontSize: '0.56rem',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          <FileDiff size={11} />
                          {isExpanded ? 'Chiudi Diff' : 'Vedi Diff'}
                        </button>
                      )}
                      {f.last_error && <AlertTriangle size={12} color={bad} style={{ flexShrink: 0 }} />}
                    </Row>

                    {/* Expandable Unified Diff Box */}
                    {isExpanded && diffText && (
                      <div
                        style={{
                          borderRadius: 6,
                          background: isLight ? '#f6f8fa' : '#04070b',
                          border: `1px solid ${accent}44`,
                          padding: '6px 8px',
                          maxHeight: '220px',
                          overflowY: 'auto',
                          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                          fontSize: '0.58rem',
                          lineHeight: '1.4',
                        }}
                      >
                        {diffText.split('\n').map((line, lIdx) => {
                          let lColor = isLight ? '#24292f' : '#f0f6fc';
                          let lBg = 'transparent';
                          if (line.startsWith('+') && !line.startsWith('+++')) {
                            lColor = ok;
                            lBg = `${ok}15`;
                          } else if (line.startsWith('-') && !line.startsWith('---')) {
                            lColor = bad;
                            lBg = `${bad}15`;
                          } else if (line.startsWith('@@')) {
                            lColor = purple;
                          }
                          return (
                            <div key={lIdx} style={{ background: lBg, color: lColor, whiteSpace: 'pre-wrap' }}>
                              {line}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </Section>
          )}

          {/* Files Read & Line Coverage */}
          {readOnly.length > 0 && (
            <Section title="File letti (Grounding & Copertura)" isLight={isLight}>
              {readOnly.slice(0, 15).map((f) => (
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

          {/* Commands executed and stdout inspector */}
          {commands.length > 0 && (
            <Section title="Comandi eseguiti (Terminal Log)" isLight={isLight}>
              {commands.slice(-8).map((c, i) => {
                const isCmdExpanded = expandedCommandIdx === i;
                return (
                  <div key={`${c.command}-${i}`} style={{ display: 'grid', gap: 3 }}>
                    <Row isLight={isLight}>
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
                      <span style={{ fontSize: '0.58rem', color: c.ok ? ok : bad, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                        exit {c.returncode}
                      </span>
                      {c.stdout && (
                        <button
                          type="button"
                          onClick={() => setExpandedCommandIdx(isCmdExpanded ? null : i)}
                          style={{
                            fontSize: '0.54rem',
                            padding: '1px 5px',
                            borderRadius: 3,
                            background: subtle,
                            border: `1px solid ${border}`,
                            color: muted,
                            cursor: 'pointer',
                          }}
                        >
                          {isCmdExpanded ? 'Nascondi' : 'Log'}
                        </button>
                      )}
                    </Row>

                    {isCmdExpanded && (c.stdout || c.error) && (
                      <div
                        style={{
                          borderRadius: 4,
                          background: isLight ? '#24292f' : '#000000',
                          color: '#58a6ff',
                          padding: '6px 8px',
                          fontSize: '0.56rem',
                          fontFamily: 'Consolas, monospace',
                          whiteSpace: 'pre-wrap',
                          maxHeight: '140px',
                          overflowY: 'auto',
                        }}
                      >
                        {c.stdout || c.error}
                      </div>
                    )}
                  </div>
                );
              })}
            </Section>
          )}

          {Array.isArray(stato.failures) && stato.failures.length > 0 && (
            <Section title="Errori recenti intercettati" isLight={isLight}>
              {stato.failures.slice(-4).map((f, i) => (
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
