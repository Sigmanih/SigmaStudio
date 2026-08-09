import React, { useState } from 'react';
import { Wrench, Check, XCircle, ShieldAlert, RefreshCw, ChevronDown, ChevronRight, Clock } from 'lucide-react';

/**
 * Quello che l'agente ha fatto fuori dal testo della risposta.
 *
 * Due cose distinte: gli strumenti già eseguiti, che sono un resoconto, e le
 * chiamate che si sono fermate ad aspettare. Le seconde stanno in evidenza
 * perché finché nessuno decide, l'agente è fermo lì.
 */
export default function McpToolStrip({ calls = [], approvals = [] }) {
  const [openCall, setOpenCall] = useState(null);
  const [decisions, setDecisions] = useState({});
  const [busy, setBusy] = useState('');

  const decide = async (approval, approve) => {
    setBusy(approval.request_id);
    try {
      const res = await fetch('/api/mcp/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: approval.request_id, approve }),
      });
      const data = await res.json();
      setDecisions(prev => ({
        ...prev,
        [approval.request_id]: data.success
          ? { ok: approve, text: approve ? (data.output || 'Eseguito.') : 'Rifiutata.' }
          : { ok: false, text: data.error || 'Esecuzione fallita.' },
      }));
    } catch (err) {
      setDecisions(prev => ({ ...prev, [approval.request_id]: { ok: false, text: err.message } }));
    } finally {
      setBusy('');
    }
  };

  // Le chiamate in attesa arrivano in blocco quando l'agente ne chiede più di
  // una. Decidere una per una tre lampade è una tassa senza contropartita:
  // sono sotto gli occhi tutte insieme, e si approvano nell'ordine chiesto.
  const pending = approvals.filter(a => !decisions[a.request_id]);
  const decideAll = async (approve) => {
    for (const approval of pending) {
      await decide(approval, approve);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
      {calls.map((call, idx) => {
        // Try to extract image URL from tool output (for generate_image, edit_image, etc.)
        let imageUrl = null;
        if (call.ok && call.output && /generate_image|edit_image|upscale_image|render_scene/.test(call.tool || '')) {
          try {
            const parsed = typeof call.output === 'string' ? JSON.parse(call.output) : call.output;
            if (parsed && parsed.url) {
              imageUrl = parsed.url;
            }
          } catch (e) {
            // Try regex fallback for URL in raw text
            const urlMatch = (call.output || '').match(/["']?url["']?\s*:\s*["']([^"']+\.(?:png|jpg|jpeg|webp|gif))["']/i);
            if (urlMatch) imageUrl = urlMatch[1];
          }
        }
        return (
        <div key={`tc-${idx}`} style={{
          // Una chiamata rimandata non è un errore: aspetta il suo turno.
          border: `1px solid ${call.deferred ? 'rgba(255,255,255,0.12)'
            : call.ok ? 'rgba(63,185,80,0.22)' : 'rgba(248,81,73,0.22)'}`,
          background: call.deferred ? 'rgba(255,255,255,0.03)'
            : call.ok ? 'rgba(63,185,80,0.06)' : 'rgba(248,81,73,0.06)',
          borderRadius: '8px', padding: '7px 10px', fontSize: '0.78rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
               onClick={() => setOpenCall(openCall === idx ? null : idx)}>
            {call.deferred ? <Clock size={13} color="#8b8fa3" />
              : call.ok ? <Check size={13} color="#3fb950" /> : <XCircle size={13} color="#f85149" />}
            <Wrench size={12} style={{ opacity: 0.6 }} />
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{call.tool}</span>
            {call.server && <span style={{ opacity: 0.5, fontSize: '0.72rem' }}>· {call.server}</span>}
            <span style={{ marginLeft: 'auto', opacity: 0.6 }}>
              {openCall === idx ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </span>
          </div>
          {openCall === idx && (
            <pre style={{
              margin: '8px 0 0', padding: '8px', borderRadius: '6px', maxHeight: '260px',
              overflow: 'auto', background: 'rgba(0,0,0,0.3)', fontSize: '0.72rem',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>{call.output}</pre>
          )}
          {/* Inline image preview for creative tools */}
          {imageUrl && (
            <div className="agent-image-preview" style={{ marginTop: '8px', maxWidth: '320px' }}>
              <img
                src={imageUrl}
                alt={call.tool || 'Generated image'}
                loading="lazy"
                style={{ maxHeight: '240px' }}
                onError={(e) => { e.target.parentElement.style.display = 'none'; }}
              />
              <div className="image-overlay">
                <span>🎨 Immagine generata</span>
              </div>
            </div>
          )}
        </div>
        );
      })}

      {pending.length > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '9px', padding: '8px 11px',
          border: '1px solid rgba(210,153,34,0.3)', background: 'rgba(210,153,34,0.06)',
          borderRadius: '9px', fontSize: '0.79rem',
        }}>
          <ShieldAlert size={14} color="#d29922" />
          <span><b>{pending.length}</b> azioni in attesa della tua decisione</span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '7px' }}>
            <button onClick={() => decideAll(true)} disabled={!!busy}
                    style={{
                      background: 'linear-gradient(135deg,#3fb950,#2ea043)', border: 'none',
                      color: '#fff', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer',
                      fontWeight: 700, fontSize: '0.75rem',
                    }}>
              Approva tutte
            </button>
            <button onClick={() => decideAll(false)} disabled={!!busy}
                    style={{
                      background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
                      color: '#e2e4eb', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer',
                      fontWeight: 600, fontSize: '0.75rem',
                    }}>
              Rifiuta tutte
            </button>
          </div>
        </div>
      )}

      {approvals.map(approval => {
        const decided = decisions[approval.request_id];
        return (
          <div key={approval.request_id} style={{
            border: '1px solid rgba(210,153,34,0.35)',
            background: 'rgba(210,153,34,0.08)',
            borderRadius: '10px', padding: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '7px' }}>
              <ShieldAlert size={15} color="#d29922" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#d29922' }}>
                L'agente chiede di eseguire uno strumento
              </span>
            </div>
            <div style={{ fontSize: '0.79rem', marginBottom: '4px' }}>
              <b style={{ fontFamily: 'JetBrains Mono, monospace' }}>{approval.tool}</b>
              {approval.server && <span style={{ opacity: 0.65 }}> · {approval.server}</span>}
            </div>
            {approval.summary && (
              <div style={{ fontSize: '0.75rem', opacity: 0.75, marginBottom: '7px' }}>{approval.summary}</div>
            )}
            <pre style={{
              margin: '0 0 10px', padding: '8px', borderRadius: '6px', maxHeight: '180px',
              overflow: 'auto', background: 'rgba(0,0,0,0.28)', fontSize: '0.72rem',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>{JSON.stringify(approval.arguments, null, 2)}</pre>

            {decided ? (
              <div style={{ fontSize: '0.78rem', color: decided.ok ? '#3fb950' : '#f85149' }}>
                {decided.ok ? '✓' : '✗'} {decided.text}
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => decide(approval, true)} disabled={busy === approval.request_id}
                        style={{
                          background: 'linear-gradient(135deg,#3fb950,#2ea043)', border: 'none',
                          color: '#fff', padding: '6px 14px', borderRadius: '7px', cursor: 'pointer',
                          fontWeight: 700, fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '6px',
                        }}>
                  {busy === approval.request_id ? <RefreshCw size={12} className="spin" /> : <Check size={12} />}
                  Approva ed esegui
                </button>
                <button onClick={() => decide(approval, false)} disabled={busy === approval.request_id}
                        style={{
                          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.14)',
                          color: '#e2e4eb', padding: '6px 14px', borderRadius: '7px', cursor: 'pointer',
                          fontWeight: 600, fontSize: '0.78rem',
                        }}>
                  Rifiuta
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
