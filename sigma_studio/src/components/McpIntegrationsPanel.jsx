import React, { useState } from 'react';
import {
  Home, Mail, MessageSquare, Calendar, Server, Plug, Check, XCircle,
  RefreshCw, Trash2, Plus, AlertTriangle, Play
} from 'lucide-react';

// Il segnaposto che il backend rimanda al posto dei segreti già salvati: il
// browser non riceve mai un token in chiaro, e rispedirlo così com'è significa
// "lascialo com'era".
const SECRET_MARKER = '••••••••';

const INTEGRATION_ICONS = {
  home_assistant: Home,
  email: Mail,
  messaging: MessageSquare,
  calendar: Calendar,
};

const card = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '12px',
  padding: '18px',
};

const label = { fontSize: '0.72rem', color: '#8b8fa3', marginBottom: '4px', display: 'block' };

const input = {
  width: '100%',
  background: 'rgba(0,0,0,0.35)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '7px',
  color: '#e2e4eb',
  padding: '8px 10px',
  fontSize: '0.82rem',
  fontFamily: 'JetBrains Mono, monospace',
};

const button = (accent) => ({
  background: accent || 'rgba(255,255,255,0.06)',
  border: accent ? 'none' : '1px solid rgba(255,255,255,0.12)',
  color: accent ? '#fff' : '#e2e4eb',
  padding: '7px 14px',
  borderRadius: '7px',
  cursor: 'pointer',
  fontSize: '0.78rem',
  fontWeight: 600,
  display: 'flex',
  alignItems: 'center',
  gap: '6px',
});

function StatusPill({ ok, children }) {
  return (
    <span style={{
      fontSize: '0.68rem', fontWeight: 700, padding: '3px 9px', borderRadius: '20px',
      color: ok ? '#3fb950' : '#d29922',
      background: ok ? 'rgba(63,185,80,0.12)' : 'rgba(210,153,34,0.12)',
      border: `1px solid ${ok ? 'rgba(63,185,80,0.3)' : 'rgba(210,153,34,0.3)'}`,
      display: 'inline-flex', alignItems: 'center', gap: '4px',
    }}>
      {ok ? <Check size={11} /> : <AlertTriangle size={11} />}
      {children}
    </span>
  );
}

/** Pannello di configurazione di un singolo server che parla con l'esterno. */
function IntegrationCard({ server, onSaved }) {
  const [values, setValues] = useState(server.config || {});
  const [saving, setSaving] = useState(false);
  const [probe, setProbe] = useState(null);
  const [probing, setProbing] = useState(false);

  const Icon = INTEGRATION_ICONS[server.integration_key] || Plug;

  const save = async () => {
    setSaving(true);
    setProbe(null);
    try {
      const res = await fetch('/api/mcp/integration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: server.integration_key, values }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      onSaved?.();
    } catch (err) {
      setProbe({ ok: false, message: `Salvataggio fallito: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  // La prova usa uno strumento di sola lettura: verificare le credenziali non
  // deve accendere una luce né spedire un messaggio a nessuno.
  const test = async () => {
    setProbing(true);
    setProbe(null);
    try {
      const res = await fetch('/api/mcp/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: server.integration_key }),
      });
      const data = await res.json();
      setProbe(data.success
        ? { ok: true, message: 'Connessione riuscita.' }
        : { ok: false, message: data.error || 'Prova fallita.' });
    } catch (err) {
      setProbe({ ok: false, message: err.message });
    } finally {
      setProbing(false);
    }
  };

  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
        <div style={{
          width: '38px', height: '38px', borderRadius: '10px', display: 'flex',
          alignItems: 'center', justifyContent: 'center', background: 'rgba(0,210,255,0.1)',
        }}>
          <Icon size={19} color="#00d2ff" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{server.name}</div>
          <div style={{ fontSize: '0.76rem', color: '#8b8fa3' }}>{server.description}</div>
        </div>
        <StatusPill ok={server.configured}>
          {server.configured ? 'configurato' : 'da configurare'}
        </StatusPill>
      </div>

      {server.missing_dependency && (
        <div style={{
          background: 'rgba(210,153,34,0.1)', border: '1px solid rgba(210,153,34,0.25)',
          borderRadius: '8px', padding: '9px 12px', marginBottom: '14px', fontSize: '0.78rem',
        }}>
          Libreria mancante. Installala con{' '}
          <code style={{ color: '#d29922', fontWeight: 700 }}>{server.missing_dependency}</code>
        </div>
      )}

      <div style={{ display: 'grid', gap: '11px', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))' }}>
        {(server.config_fields || []).map(field => (
          <div key={field.key}>
            <label style={label}>{field.label}</label>
            <input
              style={input}
              type={field.type === 'secret' ? 'password' : (field.type === 'number' ? 'number' : 'text')}
              placeholder={field.placeholder || ''}
              value={values[field.key] ?? ''}
              onChange={e => setValues(v => ({ ...v, [field.key]: e.target.value }))}
              // Selezionare invece di svuotare: chi scrive sostituisce il
              // segnaposto, chi si limita a cliccarci sopra non lo perde. Con lo
              // svuotamento, un clic distratto seguito da Salva cancellava il
              // segreto salvato.
              onFocus={e => { if (e.target.value === SECRET_MARKER) e.target.select(); }}
            />
            {field.help && (
              <div style={{ fontSize: '0.68rem', color: '#6b7080', marginTop: '4px' }}>{field.help}</div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '9px', marginTop: '15px', alignItems: 'center' }}>
        <button style={button('linear-gradient(135deg,#00d2ff,#0072ff)')} onClick={save} disabled={saving}>
          {saving ? <RefreshCw size={13} className="spin" /> : <Check size={13} />}
          Salva
        </button>
        <button style={button()} onClick={test} disabled={probing || !server.configured}>
          {probing ? <RefreshCw size={13} className="spin" /> : <Play size={13} />}
          Prova connessione
        </button>
        {probe && (
          <span style={{ fontSize: '0.76rem', color: probe.ok ? '#3fb950' : '#f85149' }}>
            {probe.ok ? '✓' : '✗'} {probe.message}
          </span>
        )}
      </div>
    </div>
  );
}

/** Aggiunta, collegamento e rimozione dei server MCP di terze parti. */
function ExternalServers({ servers, onChanged }) {
  const blank = { name: '', transport: 'stdio', command: 'npx', args: '', url: '', read_only: false };
  const [draft, setDraft] = useState(blank);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const add = async () => {
    setBusy('add');
    setError('');
    try {
      const res = await fetch('/api/mcp/external/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: draft.name,
          transport: draft.transport,
          command: draft.command,
          // "-y @modelcontextprotocol/server-filesystem ." → lista di argomenti
          args: draft.args.trim() ? draft.args.trim().split(/\s+/) : [],
          url: draft.url,
          read_only: draft.read_only,
        }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (data.connection && data.connection.connected === false) {
        setError(data.connection.error || 'Server aggiunto ma non collegato.');
      }
      setDraft(blank);
      onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const act = async (path, id) => {
    setBusy(id);
    try {
      await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      onChanged?.();
    } finally {
      setBusy('');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={card}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '9px', marginBottom: '6px' }}>
          <Plus size={17} color="#00d2ff" />
          <span style={{ fontWeight: 700 }}>Collega un server MCP di terze parti</span>
        </div>
        <div style={{ fontSize: '0.78rem', color: '#8b8fa3', marginBottom: '15px' }}>
          Qualunque server che parli il Model Context Protocol. Con il trasporto <b>stdio</b> il server
          viene avviato come processo figlio (serve Node.js per quelli lanciati con <code>npx</code>);
          con <b>http</b> ci si collega a un server già in ascolto.
        </div>

        <div style={{ display: 'grid', gap: '11px', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
          <div>
            <label style={label}>Nome</label>
            <input style={input} placeholder="Filesystem MCP" value={draft.name}
                   onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} />
          </div>
          <div>
            <label style={label}>Trasporto</label>
            <select style={input} value={draft.transport}
                    onChange={e => setDraft(d => ({ ...d, transport: e.target.value }))}>
              <option value="stdio">stdio (processo locale)</option>
              <option value="http">http (server remoto)</option>
            </select>
          </div>
          {draft.transport === 'stdio' ? (
            <>
              <div>
                <label style={label}>Comando</label>
                <input style={input} placeholder="npx" value={draft.command}
                       onChange={e => setDraft(d => ({ ...d, command: e.target.value }))} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={label}>Argomenti</label>
                <input style={input} placeholder="-y @modelcontextprotocol/server-filesystem C:\\Users\\Sigma\\Desktop"
                       value={draft.args}
                       onChange={e => setDraft(d => ({ ...d, args: e.target.value }))} />
              </div>
            </>
          ) : (
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={label}>URL</label>
              <input style={input} placeholder="https://esempio.it/mcp" value={draft.url}
                     onChange={e => setDraft(d => ({ ...d, url: e.target.value }))} />
            </div>
          )}
        </div>

        <label style={{
          display: 'flex', alignItems: 'center', gap: '8px', marginTop: '13px',
          fontSize: '0.78rem', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={draft.read_only}
                 onChange={e => setDraft(d => ({ ...d, read_only: e.target.checked }))} />
          <span>
            Server di sola lettura
            <span style={{ color: '#6b7080' }}>
              {' '}— senza questa spunta i suoi strumenti chiedono conferma prima di partire,
              perché è codice che non abbiamo scritto noi.
            </span>
          </span>
        </label>

        {error && (
          <div style={{ marginTop: '12px', fontSize: '0.78rem', color: '#f85149' }}>{error}</div>
        )}

        <button style={{ ...button('linear-gradient(135deg,#00d2ff,#0072ff)'), marginTop: '14px' }}
                onClick={add} disabled={busy === 'add' || (!draft.command && !draft.url)}>
          {busy === 'add' ? <RefreshCw size={13} className="spin" /> : <Plus size={13} />}
          Aggiungi e collega
        </button>
      </div>

      {servers.length === 0 ? (
        <div style={{ ...card, textAlign: 'center', color: '#6b7080', fontSize: '0.82rem' }}>
          Nessun server esterno collegato.
        </div>
      ) : servers.map(server => {
        const conn = server.connection || {};
        return (
          <div key={conn.id || server.name} style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Server size={18} color={conn.connected ? '#3fb950' : '#8b8fa3'} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700 }}>{server.name}</div>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3', fontFamily: 'JetBrains Mono, monospace' }}>
                  {conn.transport} · {server.tools_count} strumenti
                  {conn.read_only ? ' · sola lettura' : ' · richiede conferma'}
                </div>
              </div>
              <StatusPill ok={conn.connected}>{conn.connected ? 'collegato' : 'non collegato'}</StatusPill>
              <button style={button()} onClick={() => act('/api/mcp/external/connect', conn.id)}
                      disabled={busy === conn.id}>
                <RefreshCw size={13} className={busy === conn.id ? 'spin' : ''} />
                Ricollega
              </button>
              <button style={{ ...button(), color: '#f85149' }}
                      onClick={() => act('/api/mcp/external/remove', conn.id)} disabled={busy === conn.id}>
                <Trash2 size={13} />
              </button>
            </div>
            {conn.error && (
              <div style={{
                marginTop: '11px', padding: '9px 12px', borderRadius: '8px', fontSize: '0.76rem',
                background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.2)', color: '#f85149',
              }}>
                <XCircle size={12} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
                {conn.error}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Le due schede che prima non esistevano: dove si dicono a Sigma Studio le
 * credenziali dei sistemi esterni, e dove si collegano server MCP altrui.
 */
export default function McpIntegrationsPanel({ servers, onChanged }) {
  const integrations = servers.filter(s => s.integration_key);
  const external = servers.filter(s => s.external);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '26px' }}>
      <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Integrazioni native</h3>
          <div style={{ fontSize: '0.79rem', color: '#8b8fa3', marginTop: '4px' }}>
            Le credenziali restano nel tuo <code>config.json</code> e non lasciano mai la macchina.
            Un'integrazione non configurata resta visibile ma i suoi strumenti si rifiutano di partire,
            spiegando cosa manca.
          </div>
        </div>
        {integrations.map(server => (
          <IntegrationCard key={server.integration_key} server={server} onSaved={onChanged} />
        ))}
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>Server MCP esterni</h3>
          <div style={{ fontSize: '0.79rem', color: '#8b8fa3', marginTop: '4px' }}>
            Ogni server che parla il protocollo si collega qui, e i suoi strumenti compaiono
            nel catalogo insieme agli altri.
          </div>
        </div>
        <ExternalServers servers={external} onChanged={onChanged} />
      </section>
    </div>
  );
}
