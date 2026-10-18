import React, { useState, useEffect, useCallback } from 'react';
import {
  Link2,
  ShieldCheck,
  ShieldAlert,
  Coins,
  Server,
  Play,
  Square,
  Send,
  RefreshCw,
  Cpu,
  Activity,
  ArrowRightLeft,
  Loader2,
  Database
} from 'lucide-react';

const API = '/api/sigma_network/ailo';

// Le route rispondono { detail } sugli errori FastAPI: lo trasformiamo in testo.
async function call(path, options = {}) {
  const resp = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  let data = null;
  try {
    data = await resp.json();
  } catch {
    data = null;
  }
  if (!resp.ok) {
    throw new Error((data && (data.detail || data.error)) || `HTTP ${resp.status}`);
  }
  return data;
}

const fmt = (n, d = 4) => (typeof n === 'number' ? n.toFixed(d) : '—');

const Notice = ({ kind, children }) => (
  <div
    role={kind === 'error' ? 'alert' : 'status'}
    style={{
      padding: '8px 12px',
      borderRadius: 8,
      fontSize: '0.84rem',
      background: kind === 'error' ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)',
      border: `1px solid ${kind === 'error' ? 'rgba(239,68,68,0.35)' : 'rgba(16,185,129,0.35)'}`,
      color: kind === 'error' ? '#fca5a5' : '#6ee7b7',
      overflowWrap: 'anywhere',
    }}
  >
    {children}
  </div>
);

const AiloNetworkPanel = () => {
  const [status, setStatus] = useState(null);
  const [wallet, setWallet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState(null);

  const [serverUrl, setServerUrl] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [toWallet, setToWallet] = useState('');
  const [amount, setAmount] = useState('');
  const [transferPassword, setTransferPassword] = useState('');
  const [prompt, setPrompt] = useState('');
  const [backend, setBackend] = useState('gpu');
  const [answer, setAnswer] = useState(null);
  const [hub, setHub] = useState(null);
  const [importPath, setImportPath] = useState('');

  const refresh = useCallback(async () => {
    try {
      setHub(await call('/hub/status'));
    } catch (e) {
      setHub({ error: e.message });
    }
    try {
      const st = await call('/status');
      setStatus(st);
      setServerUrl(prev => prev || st.server_url || '');
      if (st.verified && st.wallet) {
        try {
          setWallet(await call('/wallet'));
        } catch (e) {
          setWallet({ error: e.message });
        }
      } else {
        setWallet(null);
      }
    } catch (e) {
      setStatus({ error: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 8000);
    return () => clearInterval(timer);
  }, [refresh]);

  // Esegue un'azione mostrando sempre un esito: nessun pulsante muto.
  const run = async (label, fn, okText) => {
    setBusy(label);
    setMessage(null);
    try {
      const out = await fn();
      if (okText) setMessage({ kind: 'ok', text: typeof okText === 'function' ? okText(out) : okText });
      await refresh();
      return out;
    } catch (e) {
      setMessage({ kind: 'error', text: e.message });
      return null;
    } finally {
      setBusy('');
    }
  };

  const saveServer = () =>
    run('server', () => call('/config', { method: 'POST', body: JSON.stringify({ server_url: serverUrl }) }),
      'Server salvato. Verifica in corso…');

  const auth = (mode) =>
    run(mode, async () => {
      const out = await call(`/${mode}`, { method: 'POST', body: JSON.stringify({ email, password }) });
      setPassword('');
      return out;
    }, out => `Wallet collegato: ${out.wallet}`);

  const toggleHub = () =>
    run('hub', () => call('/hub/enable', { method: 'POST', body: JSON.stringify({ enabled: !hub?.enabled }) }),
      out => (out.enabled ? 'Hub AiLo attivo: questa istanza ospita registro ALC e nodi.' : 'Hub AiLo spento.'));

  const useLocalHub = () =>
    run('uselocal', async () => {
      const out = await call('/hub/use_local', { method: 'POST' });
      setServerUrl(out.server_url);
      return out;
    }, "Collegato all'hub di questa istanza.");

  const importDb = () =>
    run('import', () => call('/hub/import', { method: 'POST', body: JSON.stringify({ path: importPath }) }),
      out => `Importati ${out.users} account e ${out.transactions} transazioni (${out.skipped_users} gia' presenti).`);

  const toggleNode = () =>
    run('node', () => call(status?.node?.running ? '/node/stop' : '/node/start', { method: 'POST' }),
      out => (out.running ? 'Nodo AiLo avviato: questo PC serve inferenza e guadagna ALC.' : 'Nodo AiLo fermato.'));

  const transfer = () =>
    run('transfer', async () => {
      const out = await call('/transfer', {
        method: 'POST',
        body: JSON.stringify({ to_wallet: toWallet, amount: parseFloat(amount), password: transferPassword }),
      });
      setTransferPassword('');
      return out;
    }, out => `Trasferimento eseguito. Nuovo saldo: ${fmt(out.newBalance)} ALC`);

  const infer = () =>
    run('infer', async () => {
      setAnswer(null);
      const out = await call('/infer', { method: 'POST', body: JSON.stringify({ prompt, backend, max_tokens: 200 }) });
      setAnswer(out);
      return out;
    });

  if (loading) {
    return (
      <div className="sn-card-cyber" style={{ alignItems: 'center' }}>
        <Loader2 size={20} className="spin" /> Connessione alla rete AiLo…
      </div>
    );
  }

  const node = status?.node || {};
  const verified = Boolean(status?.verified);
  const linked = Boolean(status?.wallet);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
      {message && <Notice kind={message.kind}>{message.text}</Notice>}

      {/* Stato rete */}
      <div className="sn-stats-row">
        <div className="sn-stat-card">
          <div className="sn-stat-icon">{verified ? <ShieldCheck size={20} /> : <ShieldAlert size={20} />}</div>
          <div>
            <div className="sn-stat-label">Server AiLo</div>
            <div className="sn-stat-val">{verified ? 'Verificato' : status?.configured ? 'Non raggiungibile' : 'Da configurare'}</div>
          </div>
        </div>
        <div className="sn-stat-card">
          <div className="sn-stat-icon"><Activity size={20} /></div>
          <div>
            <div className="sn-stat-label">Nodi in rete</div>
            <div className="sn-stat-val">{status?.network?.totalNodes ?? '—'}</div>
          </div>
        </div>
        <div className="sn-stat-card">
          <div className="sn-stat-icon"><Coins size={20} /></div>
          <div>
            <div className="sn-stat-label">Supply ALC</div>
            <div className="sn-stat-val">{fmt(status?.chain?.totalSupply, 2)}</div>
          </div>
        </div>
        <div className="sn-stat-card">
          <div className="sn-stat-icon"><Server size={20} /></div>
          <div>
            <div className="sn-stat-label">Il mio nodo</div>
            <div className="sn-stat-val">{node.connected ? 'Online' : node.running ? 'Connessione…' : 'Spento'}</div>
          </div>
        </div>
      </div>

      <div className="sn-wallet-grid">
        {/* Colonna sinistra: collegamento e wallet */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
          <div className="sn-card-cyber">
            <h3 className="sn-inspector-title"><Database size={16} /> Hub AiLo su questa istanza</h3>
            <p className="sn-stat-label" style={{ margin: 0 }}>
              Il coordinatore AiLo originale è dismesso: l'hub ospita qui il registro AiloCoin, gli account
              e lo smistamento dell'inferenza ai nodi. Le altre istanze Sigma vi si collegano con l'URL qui sotto.
            </p>
            {hub?.error && <Notice kind="error">{hub.error}</Notice>}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className={hub?.enabled ? 'sn-btn-secondary' : 'sn-btn-primary'} onClick={toggleHub} disabled={!!busy}>
                {busy === 'hub' ? <Loader2 size={14} /> : hub?.enabled ? 'Spegni hub' : 'Attiva hub'}
              </button>
              {hub?.enabled && (
                <button className="sn-btn-secondary" onClick={useLocalHub} disabled={!!busy}>
                  {busy === 'uselocal' ? 'Collegamento…' : 'Usa questo hub'}
                </button>
              )}
            </div>
            {hub?.enabled && (
              <>
                <div className="sn-stat-label" style={{ overflowWrap: 'anywhere' }}>
                  URL hub: <span style={{ fontFamily: 'monospace' }}>{hub.local_url}</span>
                </div>
                <div className="sn-stat-label">
                  Account {hub.ledger?.activeAddresses ?? 0} · Transazioni {hub.ledger?.blockNumber ?? 0} ·
                  Nodi collegati {hub.nodes?.length ?? 0}
                </div>
                <label className="sn-stat-label" htmlFor="ailo-import">Migra da un ailo.db del vecchio server</label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <input id="ailo-import" className="sn-prompt-input" placeholder="percorso/del/vecchio/ailo.db"
                    value={importPath} onChange={e => setImportPath(e.target.value)} />
                  <button className="sn-btn-secondary" onClick={importDb} disabled={!!busy || !importPath.trim()}>
                    {busy === 'import' ? 'Import…' : 'Importa'}
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="sn-card-cyber">
            <h3 className="sn-inspector-title"><Link2 size={16} /> Collegamento</h3>
            <label className="sn-stat-label" htmlFor="ailo-server">URL dell'hub AiLo</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                id="ailo-server"
                className="sn-prompt-input"
                placeholder="http://host:8000/api/sigma_network/ailo_hub"
                value={serverUrl}
                onChange={e => setServerUrl(e.target.value)}
              />
              <button className="sn-btn-secondary" onClick={saveServer} disabled={busy === 'server'}>
                {busy === 'server' ? <Loader2 size={14} /> : 'Salva'}
              </button>
            </div>
            {status?.error && <Notice kind="error">{status.error}</Notice>}

            {verified && !linked && (
              <>
                <input className="sn-prompt-input" type="email" placeholder="Email account AiLo"
                  value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" />
                <input className="sn-prompt-input" type="password" placeholder="Password (non viene salvata)"
                  value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button className="sn-btn-primary" onClick={() => auth('login')} disabled={!!busy || !email || !password}>
                    {busy === 'login' ? 'Accesso…' : 'Collega wallet'}
                  </button>
                  <button className="sn-btn-secondary" onClick={() => auth('register')} disabled={!!busy || !email || !password}>
                    {busy === 'register' ? 'Creazione…' : 'Crea account'}
                  </button>
                </div>
              </>
            )}
            {linked && (
              <div className="sn-stat-label" style={{ overflowWrap: 'anywhere' }}>
                Wallet: <span style={{ fontFamily: 'monospace' }}>{status.wallet}</span>
                {status.email ? ` · ${status.email}` : ''}
              </div>
            )}
          </div>

          {linked && (
            <div className="sn-card-cyber">
              <h3 className="sn-inspector-title"><Coins size={16} /> Wallet AiloCoin</h3>
              {wallet?.error ? (
                <Notice kind="error">{wallet.error}</Notice>
              ) : (
                <>
                  <div className="sn-balance-big">{fmt(wallet?.balance)} ALC</div>
                  <div className="sn-stat-label">
                    Confermati {fmt(wallet?.confirmedBalance)} · In attesa {fmt(wallet?.pendingBalance)}
                  </div>
                </>
              )}
              <h4 className="sn-stat-label"><ArrowRightLeft size={14} /> Invia ALC</h4>
              <input className="sn-prompt-input" placeholder="Wallet destinatario (0x…)"
                value={toWallet} onChange={e => setToWallet(e.target.value)} />
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <input className="sn-prompt-input" type="number" min="0" step="0.01" placeholder="Importo"
                  value={amount} onChange={e => setAmount(e.target.value)} />
                <input className="sn-prompt-input" type="password" placeholder="Password"
                  value={transferPassword} onChange={e => setTransferPassword(e.target.value)} autoComplete="current-password" />
              </div>
              <button className="sn-btn-primary" onClick={transfer}
                disabled={!!busy || !toWallet || !(parseFloat(amount) > 0) || !transferPassword}>
                {busy === 'transfer' ? 'Invio…' : 'Invia'}
              </button>
            </div>
          )}
        </div>

        {/* Colonna destra: nodo provider e inferenza distribuita */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
          <div className="sn-card-cyber">
            <h3 className="sn-inspector-title"><Cpu size={16} /> Nodo di inferenza AiLo</h3>
            <p className="sn-stat-label" style={{ margin: 0 }}>
              Il motore locale di Sigma Studio risponde alle richieste della rete AiLo come un miner GPU.
              Solo generazione di testo, con i limiti del Resource Guard del provider.
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                className={node.running ? 'sn-btn-secondary' : 'sn-btn-primary'}
                onClick={toggleNode}
                disabled={!!busy || !verified || !linked}
                title={!linked ? 'Collega prima un wallet AiLo' : ''}
              >
                {node.running ? <><Square size={14} /> Ferma nodo</> : <><Play size={14} /> Avvia nodo</>}
              </button>
              <button className="sn-btn-secondary" onClick={() => run('refresh', refresh)} disabled={!!busy}>
                <RefreshCw size={14} />
              </button>
            </div>
            <div className="sn-stats-row">
              <div><div className="sn-stat-label">Richieste servite</div><div className="sn-stat-val">{node.inferences ?? 0}</div></div>
              <div><div className="sn-stat-label">Token generati</div><div className="sn-stat-val">{node.tokens_generated ?? 0}</div></div>
              <div><div className="sn-stat-label">Rifiutate</div><div className="sn-stat-val">{node.rejected ?? 0}</div></div>
            </div>
            {node.node_id && <div className="sn-stat-label">ID nodo: <span style={{ fontFamily: 'monospace' }}>{node.node_id}</span></div>}
            {node.last_error && <Notice kind="error">{node.last_error}</Notice>}
          </div>

          <div className="sn-card-cyber">
            <h3 className="sn-inspector-title"><Send size={16} /> Inferenza distribuita AiLo</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select className="sn-prompt-input" style={{ flex: '0 1 auto' }} value={backend}
                onChange={e => setBackend(e.target.value)} aria-label="Backend AiLo">
                <option value="gpu">Nodi GPU della rete</option>
                <option value="fused">Modello AILO Fused</option>
              </select>
            </div>
            <textarea className="sn-prompt-input" rows={3} placeholder="Scrivi un prompt per la rete AiLo…"
              value={prompt} onChange={e => setPrompt(e.target.value)} />
            <button className="sn-send-btn" onClick={infer} disabled={!!busy || !verified || !prompt.trim()}>
              {busy === 'infer' ? 'In attesa di un nodo…' : 'Invia alla rete'}
            </button>
            {answer && (
              answer.success === false
                ? <Notice kind="error">{answer.response || answer.error}</Notice>
                : (
                  <div className="sn-infer-terminal">
                    <div className="sn-terminal-body" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{answer.response}</div>
                    <div className="sn-terminal-footer">
                      {answer.tokens_generated ?? 0} token
                      {answer.processed_by ? ` · nodo ${answer.processed_by}` : ''}
                      {answer.model ? ` · ${answer.model}` : ''}
                    </div>
                  </div>
                )
            )}
          </div>
        </div>
      </div>

      {linked && wallet?.transactions?.length > 0 && (
        <div className="sn-table-container">
          <table className="sn-table">
            <thead>
              <tr><th>Tipo</th><th>Da</th><th>A</th><th>ALC</th><th>Data</th></tr>
            </thead>
            <tbody>
              {[...wallet.transactions].reverse().map((tx, i) => (
                <tr key={tx.hash || i}>
                  <td>{tx.type}</td>
                  <td style={{ fontFamily: 'monospace' }}>{(tx.from || '').slice(0, 12)}</td>
                  <td style={{ fontFamily: 'monospace' }}>{(tx.to || '').slice(0, 12)}</td>
                  <td>{fmt(tx.amount)}</td>
                  <td>{tx.timestamp ? new Date(tx.timestamp).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {linked && wallet && !wallet.error && !wallet.transactions?.length && (
        <div className="sn-stat-label">Nessuna transazione ALC per questo wallet.</div>
      )}
    </div>
  );
};

export default AiloNetworkPanel;
