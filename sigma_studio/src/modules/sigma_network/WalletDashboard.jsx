import React, { useState } from 'react';
import {
  Coins,
  ArrowUpRight,
  ArrowDownLeft,
  Pickaxe,
  Gift,
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
  FileCheck,
  RefreshCw,
  Send,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

const WalletDashboard = ({ walletData, identity, onRefresh }) => {
  const [copied, setCopied] = useState(false);
  const [isFauceting, setIsFauceting] = useState(false);
  const [isVerifyingChain, setIsVerifyingChain] = useState(false);
  const [chainStatus, setChainStatus] = useState(null);

  // Modal / Form Trasferimento
  const [showTransfer, setShowTransfer] = useState(false);
  const [recipientId, setRecipientId] = useState('');
  const [transferAmount, setTransferAmount] = useState('');
  const [transferNote, setTransferNote] = useState('');
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferFeedback, setTransferFeedback] = useState(null);

  const balance = walletData?.balance || 0;
  const earned = walletData?.earned || 0;
  const mined = walletData?.mined || 0;
  const faucet = walletData?.faucet || 0;
  const spent = walletData?.spent || 0;
  const receipts = walletData?.receipts || [];

  const handleCopyPeerId = () => {
    if (identity?.peer_id) {
      navigator.clipboard.writeText(identity.peer_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRequestFaucet = async () => {
    setIsFauceting(true);
    try {
      const resp = await fetch('/api/sigma_network/wallet/faucet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: 100.0 }),
      });
      if (resp.ok && onRefresh) {
        onRefresh();
      }
    } catch (e) {
      console.error('Errore richiesta faucet', e);
    } finally {
      setIsFauceting(false);
    }
  };

  const handleVerifyChain = async () => {
    setIsVerifyingChain(true);
    setChainStatus(null);
    try {
      const resp = await fetch('/api/sigma_network/wallet/verify_chain', { method: 'POST' });
      if (resp.ok) {
        const data = await resp.json();
        setChainStatus(data);
      }
    } catch (e) {
      console.error('Errore verifica blockchain', e);
    } finally {
      setIsVerifyingChain(false);
    }
  };

  const handleTransfer = async (e) => {
    e.preventDefault();
    const amt = parseFloat(transferAmount);
    if (!recipientId.trim() || isNaN(amt) || amt <= 0) {
      setTransferFeedback({ error: true, msg: 'Inserisci un Peer ID valido e un importo positivo.' });
      return;
    }
    if (amt > balance) {
      setTransferFeedback({ error: true, msg: 'Saldo insufficiente per completare il trasferimento.' });
      return;
    }

    setIsTransferring(true);
    setTransferFeedback(null);
    try {
      const resp = await fetch('/api/sigma_network/wallet/transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_id: recipientId.trim(),
          amount: amt,
          note: transferNote.trim(),
        }),
      });

      const resData = await resp.json();
      if (resp.ok && resData.status === 'success') {
        setTransferFeedback({
          error: false,
          msg: `Trasferiti con successo ${amt.toFixed(2)} AILO a ${recipientId.slice(0, 10)}...!`,
        });
        setTransferAmount('');
        setRecipientId('');
        setTransferNote('');
        if (onRefresh) onRefresh();
      } else {
        setTransferFeedback({ error: true, msg: resData.detail || 'Trasferimento rifiutato.' });
      }
    } catch (err) {
      setTransferFeedback({ error: true, msg: 'Errore di connessione durante il trasferimento.' });
    } finally {
      setIsTransferring(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Griglia Superiore: Cyber Card + Ripartizione Metriche */}
      <div className="sn-wallet-grid">
        {/* Cyber Card */}
        <div className="sn-card-cyber">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.08em', fontWeight: 700 }}>
              AiloCoin P2P Micro-Blockchain
            </span>
            <span style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.75rem',
              color: '#34d399',
              background: 'rgba(16, 185, 129, 0.15)',
              padding: '2px 8px',
              borderRadius: '6px'
            }}>
              <ShieldCheck size={13} /> Ed25519 Custody
            </span>
          </div>

          <div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Saldo Spendibile Locale</div>
            <div className="sn-balance-big">
              <Coins size={30} color="#00d4ff" />
              <span>{balance.toFixed(2)}</span>
              <span style={{ fontSize: '1rem', color: '#94a3b8', fontWeight: 500 }}>AILOTOKEN</span>
            </div>
          </div>

          <div style={{
            background: 'rgba(15, 23, 42, 0.7)',
            padding: '10px 12px',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Chiave Pubblica / Peer ID:</span>
              <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#cbd5e1' }}>
                {identity?.peer_id ? `${identity.peer_id.slice(0, 14)}...${identity.peer_id.slice(-6)}` : 'Inizializzazione...'}
              </span>
            </div>
            <button
              onClick={handleCopyPeerId}
              style={{ background: 'transparent', border: 'none', color: '#38bdf8', cursor: 'pointer', padding: 4 }}
              title="Copia Peer ID"
            >
              {copied ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
            </button>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="sn-btn-primary"
              onClick={handleRequestFaucet}
              disabled={isFauceting}
              style={{ flex: 1 }}
            >
              <Gift size={16} />
              <span>{isFauceting ? 'Erogazione...' : 'Genesis Faucet (+100)'}</span>
            </button>

            <button
              onClick={() => setShowTransfer(!showTransfer)}
              style={{
                background: showTransfer ? 'rgba(0, 212, 255, 0.3)' : 'rgba(30, 41, 59, 0.9)',
                border: '1px solid #00d4ff',
                borderRadius: 8,
                color: '#38bdf8',
                padding: '10px 16px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: '0.85rem',
                fontWeight: 600,
                transition: 'all 0.15s ease'
              }}
            >
              <Send size={15} />
              <span>Invia Token</span>
            </button>
          </div>
        </div>

        {/* Metriche Dettagliate */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
          <div className="sn-stat-card">
            <div className="sn-stat-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              <ArrowDownLeft size={22} />
            </div>
            <div>
              <div className="sn-stat-val" style={{ color: '#34d399' }}>+{earned.toFixed(2)}</div>
              <div className="sn-stat-label">Inferenza Servita</div>
            </div>
          </div>

          <div className="sn-stat-card">
            <div className="sn-stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' }}>
              <Pickaxe size={22} />
            </div>
            <div>
              <div className="sn-stat-val" style={{ color: '#c084fc' }}>+{mined.toFixed(2)}</div>
              <div className="sn-stat-label">Mining PoUW</div>
            </div>
          </div>

          <div className="sn-stat-card">
            <div className="sn-stat-icon" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
              <Gift size={22} />
            </div>
            <div>
              <div className="sn-stat-val" style={{ color: '#60a5fa' }}>+{faucet.toFixed(2)}</div>
              <div className="sn-stat-label">Genesis Faucet</div>
            </div>
          </div>

          <div className="sn-stat-card">
            <div className="sn-stat-icon" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
              <ArrowUpRight size={22} />
            </div>
            <div>
              <div className="sn-stat-val" style={{ color: '#f87171' }}>-{spent.toFixed(2)}</div>
              <div className="sn-stat-label">Inferenza Consumata</div>
            </div>
          </div>
        </div>
      </div>

      {/* Drawer Trasferimento AiloCoin */}
      {showTransfer && (
        <form
          onSubmit={handleTransfer}
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(0, 212, 255, 0.3)',
            borderRadius: 12,
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            boxShadow: '0 8px 32px rgba(0, 212, 255, 0.08)'
          }}
        >
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Send size={16} color="#00d4ff" /> Trasferimento Diretto P2P AiloCoin
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 4, display: 'block' }}>
                Peer ID Destinatario (32 caratteri hex):
              </label>
              <input
                type="text"
                value={recipientId}
                onChange={(e) => setRecipientId(e.target.value)}
                placeholder="es. 4f9b2d8e..."
                style={{
                  width: '100%',
                  background: 'rgba(30, 41, 59, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 6,
                  color: '#f8fafc',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                  fontFamily: 'monospace'
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 4, display: 'block' }}>
                Importo (AILO):
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={transferAmount}
                onChange={(e) => setTransferAmount(e.target.value)}
                placeholder="es. 10.0"
                style={{
                  width: '100%',
                  background: 'rgba(30, 41, 59, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 6,
                  color: '#f8fafc',
                  padding: '8px 12px',
                  fontSize: '0.85rem'
                }}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 4, display: 'block' }}>
              Causale / Nota (opzionale):
            </label>
            <input
              type="text"
              value={transferNote}
              onChange={(e) => setTransferNote(e.target.value)}
              placeholder="es. Pagamento per inferenza batch o collaborazione cluster"
              style={{
                width: '100%',
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 6,
                color: '#f8fafc',
                padding: '8px 12px',
                fontSize: '0.85rem'
              }}
            />
          </div>

          {transferFeedback && (
            <div style={{
              background: transferFeedback.error ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
              border: `1px solid ${transferFeedback.error ? '#ef4444' : '#10b981'}`,
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: '0.8rem',
              color: transferFeedback.error ? '#f87171' : '#34d399',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              {transferFeedback.error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}
              <span>{transferFeedback.msg}</span>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button
              type="button"
              onClick={() => setShowTransfer(false)}
              style={{
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 6,
                color: '#94a3b8',
                padding: '6px 14px',
                cursor: 'pointer',
                fontSize: '0.8rem'
              }}
            >
              Annulla
            </button>
            <button
              type="submit"
              disabled={isTransferring}
              className="sn-btn-primary"
              style={{ padding: '6px 20px', fontSize: '0.82rem' }}
            >
              {isTransferring ? 'Firma & Invio...' : 'Firma con Ed25519 & Invia'}
            </button>
          </div>
        </form>
      )}

      {/* Verifica Integrità Catena Crittografica */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.6)',
        borderRadius: 10,
        padding: '16px 20px',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 12
      }}>
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={16} color="#00d4ff" /> Integrità Micro-Blockchain Locale (Hash-Chaining SHA-256)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 2 }}>
            Verifica che ogni blocco e ricevuta siano concatenati deterministamente senza manomissioni.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {chainStatus && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.78rem',
              fontWeight: 600,
              padding: '4px 12px',
              borderRadius: 6,
              background: chainStatus.valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: chainStatus.valid ? '#34d399' : '#f87171',
              border: `1px solid ${chainStatus.valid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
            }}>
              {chainStatus.valid ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
              <span>
                {chainStatus.valid
                  ? `Catena Integra (Lunghezza: ${chainStatus.chain_length} blocchi)`
                  : `Rilevate ${chainStatus.corrupted_count} anomalie!`}
              </span>
            </div>
          )}

          <button
            onClick={handleVerifyChain}
            disabled={isVerifyingChain}
            style={{
              background: 'rgba(0, 212, 255, 0.1)',
              border: '1px solid rgba(0, 212, 255, 0.3)',
              borderRadius: 6,
              color: '#38bdf8',
              padding: '6px 14px',
              cursor: 'pointer',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <RefreshCw size={13} className={isVerifyingChain ? 'sn-spin' : ''} />
            <span>{isVerifyingChain ? 'Verifica...' : 'Verifica Catena'}</span>
          </button>
        </div>
      </div>

      {/* Registro Transazioni & Ricevute Firmate */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileCheck size={18} color="#00d4ff" /> Registro Ricevute Crittografiche ({receipts.length})
          </h3>
          <button
            onClick={onRefresh}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <RefreshCw size={13} /> Aggiorna Storico
          </button>
        </div>

        <div className="sn-table-container">
          <table className="sn-table">
            <thead>
              <tr>
                <th>ID Transazione</th>
                <th>Data</th>
                <th>Tipo / Operazione</th>
                <th>Controparte</th>
                <th>Token</th>
                <th>Importo</th>
                <th>Verifica Crittografica</th>
              </tr>
            </thead>
            <tbody>
              {receipts.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                    Nessuna transazione ancora registrata nel wallet.
                  </td>
                </tr>
              ) : (
                receipts.map((r, i) => {
                  const dateStr = r.created_at ? new Date(r.created_at * 1000).toLocaleString() : 'N/A';
                  const isIncoming = r.provider_id === identity?.peer_id || r.type === 'faucet' || r.type === 'mining_reward';
                  const counterparty = isIncoming
                    ? (r.consumer_id ? `${r.consumer_id.slice(0, 8)}...` : 'Rete')
                    : (r.provider_id ? `${r.provider_id.slice(0, 8)}...` : 'Provider');

                  return (
                    <tr key={r.receipt_id || i}>
                      <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>
                        {r.receipt_id ? r.receipt_id.slice(0, 8) : `tx-${i}`}
                      </td>
                      <td style={{ fontSize: '0.78rem' }}>{dateStr}</td>
                      <td>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          background: r.type === 'mining_reward' ? 'rgba(168, 85, 247, 0.2)' : r.type === 'faucet' ? 'rgba(59, 130, 246, 0.2)' : r.type === 'transfer' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(0, 212, 255, 0.2)',
                          color: r.type === 'mining_reward' ? '#c084fc' : r.type === 'faucet' ? '#60a5fa' : r.type === 'transfer' ? '#34d399' : '#38bdf8'
                        }}>
                          {r.type ? r.type.toUpperCase() : 'INFERENZA'}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'monospace' }}>{counterparty}</td>
                      <td>{r.tokens ? r.tokens.toLocaleString() : '-'}</td>
                      <td style={{
                        fontWeight: 700,
                        color: isIncoming ? '#34d399' : '#f87171'
                      }}>
                        {isIncoming ? '+' : '-'}{Math.abs(r.amount || 0).toFixed(4)} AILO
                      </td>
                      <td>
                        <span className="sn-verified-pill">
                          <ShieldCheck size={11} /> Ed25519 Valid
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default WalletDashboard;
