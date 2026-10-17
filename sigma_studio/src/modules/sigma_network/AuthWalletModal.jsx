import React, { useState, useEffect } from 'react';
import {
  KeyRound,
  ShieldCheck,
  UserPlus,
  LogIn,
  Download,
  Copy,
  Check,
  AlertTriangle,
  X,
  FileKey,
  Lock
} from 'lucide-react';

const AuthWalletModal = ({ isOpen, onClose, onAuthSuccess }) => {
  const [mode, setMode] = useState('login'); // 'login' | 'register' | 'import'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [importKey, setImportKey] = useState('');
  const [errorMsg, setErrorMsg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generatedSeed, setGeneratedSeed] = useState(null);
  const [copiedSeed, setCopiedSeed] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetch('/api/sigma_network/auth/session')
        .then(r => r.json())
        .then(data => {
          if (data && data.has_accounts === false) {
            setMode('register');
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const resetForm = () => {
    setUsername('');
    setPassword('');
    setImportKey('');
    setErrorMsg(null);
    setGeneratedSeed(null);
    setCopiedSeed(false);
  };

  const handleCopySeed = () => {
    if (generatedSeed) {
      navigator.clipboard.writeText(generatedSeed);
      setCopiedSeed(true);
      setTimeout(() => setCopiedSeed(false), 2000);
    }
  };

  const handleLoginWithNode = async () => {
    setErrorMsg(null);
    setLoading(true);
    try {
      const resp = await fetch('/api/sigma_network/auth/login_node', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Impossibile accedere con il wallet del nodo');
      }
      if (onAuthSuccess) onAuthSuccess(data);
      resetForm();
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Errore accesso nodo locale');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);

    try {
      let endpoint = '/api/sigma_network/auth/login';
      let payload = { username, password };

      if (mode === 'register') {
        endpoint = '/api/sigma_network/auth/register';
      } else if (mode === 'import') {
        endpoint = '/api/sigma_network/auth/import';
        payload = { username, password, mnemonic_or_privkey: importKey };
      }

      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || 'Operazione fallita');
      }

      if (mode === 'register' && data.mnemonic_seed) {
        // Mostra la seed phrase da annotare prima di chiudere
        setGeneratedSeed(data.mnemonic_seed);
        if (onAuthSuccess) onAuthSuccess(data);
      } else {
        if (onAuthSuccess) onAuthSuccess(data);
        resetForm();
        onClose();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Errore di comunicazione con il nodo');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(2, 6, 23, 0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: 16
    }}>
      <div style={{
        background: 'linear-gradient(145deg, #0f172a, #1e293b)',
        border: '1px solid rgba(0, 212, 255, 0.3)',
        borderRadius: 14,
        width: '100%',
        maxWidth: 480,
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(0, 212, 255, 0.1)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Header Modal */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(15, 23, 42, 0.6)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <KeyRound size={20} color="#00d4ff" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', fontWeight: 700 }}>
              {mode === 'login' && 'Accedi al Tuo Wallet P2P'}
              {mode === 'register' && 'Crea Nuovo Account & Wallet'}
              {mode === 'import' && 'Ripristina Wallet da Seed Phrase'}
            </h3>
          </div>
          <button
            onClick={() => { resetForm(); onClose(); }}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4 }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Scelta Modalità */}
        {!generatedSeed && (
          <div style={{
            display: 'flex',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'rgba(15, 23, 42, 0.4)'
          }}>
            <button
              onClick={() => { setMode('login'); setErrorMsg(null); }}
              style={{
                flex: 1,
                padding: '12px',
                border: 'none',
                background: mode === 'login' ? 'rgba(0, 212, 255, 0.12)' : 'transparent',
                borderBottom: mode === 'login' ? '2px solid #00d4ff' : '2px solid transparent',
                color: mode === 'login' ? '#38bdf8' : '#94a3b8',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6
              }}
            >
              <LogIn size={15} /> Login
            </button>
            <button
              onClick={() => { setMode('register'); setErrorMsg(null); }}
              style={{
                flex: 1,
                padding: '12px',
                border: 'none',
                background: mode === 'register' ? 'rgba(0, 212, 255, 0.12)' : 'transparent',
                borderBottom: mode === 'register' ? '2px solid #00d4ff' : '2px solid transparent',
                color: mode === 'register' ? '#38bdf8' : '#94a3b8',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6
              }}
            >
              <UserPlus size={15} /> Nuovo Account
            </button>
            <button
              onClick={() => { setMode('import'); setErrorMsg(null); }}
              style={{
                flex: 1,
                padding: '12px',
                border: 'none',
                background: mode === 'import' ? 'rgba(0, 212, 255, 0.12)' : 'transparent',
                borderBottom: mode === 'import' ? '2px solid #00d4ff' : '2px solid transparent',
                color: mode === 'import' ? '#38bdf8' : '#94a3b8',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6
              }}
            >
              <Download size={15} /> Ripristina
            </button>
          </div>
        )}

        {/* Corpo del Form */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {errorMsg && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 8,
              padding: '10px 14px',
              color: '#f87171',
              fontSize: '0.82rem',
              display: 'flex',
              flexDirection: 'column',
              gap: 6
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={16} />
                <span>{errorMsg}</span>
              </div>
              {mode === 'login' && (
                <button
                  type="button"
                  onClick={() => { setMode('register'); setErrorMsg(null); }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#38bdf8',
                    fontSize: '0.78rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    padding: 0,
                    textDecoration: 'underline'
                  }}
                >
                  Non hai ancora un account? Clicca qui per registrarti con Seed Phrase
                </button>
              )}
            </div>
          )}

          {/* Schermata di Backup Seed Phrase (Mostrata solo dopo registrazione) */}
          {generatedSeed ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid #10b981',
                borderRadius: 8,
                padding: '12px',
                color: '#34d399',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}>
                <ShieldCheck size={18} />
                <span>Account e Wallet Ed25519 creati con successo!</span>
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                  Annota la tua Seed Phrase Mnemonica (12 Parole):
                </label>
                <div style={{
                  background: 'rgba(2, 6, 23, 0.8)',
                  border: '1px solid rgba(0, 212, 255, 0.3)',
                  borderRadius: 8,
                  padding: '14px',
                  fontFamily: 'monospace',
                  fontSize: '0.9rem',
                  color: '#38bdf8',
                  lineHeight: '1.8',
                  wordBreak: 'break-word',
                  userSelect: 'all'
                }}>
                  {generatedSeed}
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.5 }}>
                Questa frase è la chiave master del tuo wallet AiloCoin e ti permette di recuperare i fondi su qualsiasi nodo. Non condividerla mai con nessuno.
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={handleCopySeed}
                  className="sn-btn-secondary"
                  style={{ flex: 1, padding: '10px', fontSize: '0.85rem' }}
                >
                  {copiedSeed ? <Check size={16} color="#34d399" /> : <Copy size={16} />}
                  <span>{copiedSeed ? 'Frase Copiata!' : 'Copia 12 Parole'}</span>
                </button>
                <button
                  onClick={() => { resetForm(); onClose(); }}
                  className="sn-btn-primary"
                  style={{ flex: 1, padding: '10px', fontSize: '0.85rem' }}
                >
                  <span>Ho Salvato la Frase</span>
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                  Nome Utente:
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="es. Satoshi_Sigma"
                  style={{
                    width: '100%',
                    background: 'rgba(30, 41, 59, 0.8)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 8,
                    color: '#f8fafc',
                    padding: '10px 14px',
                    fontSize: '0.85rem',
                    outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                  Password di Cifratura Locale (AES-256):
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Almeno 6 caratteri..."
                  style={{
                    width: '100%',
                    background: 'rgba(30, 41, 59, 0.8)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: 8,
                    color: '#f8fafc',
                    padding: '10px 14px',
                    fontSize: '0.85rem',
                    outline: 'none'
                  }}
                />
              </div>

              {mode === 'import' && (
                <div>
                  <label style={{ fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Mnemonic Phrase (12 parole) o Private Key:
                  </label>
                  <textarea
                    rows={3}
                    required
                    value={importKey}
                    onChange={(e) => setImportKey(e.target.value)}
                    placeholder="Incolla le 12 parole separate da spazio..."
                    style={{
                      width: '100%',
                      background: 'rgba(30, 41, 59, 0.8)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: 8,
                      color: '#f8fafc',
                      padding: '10px 14px',
                      fontSize: '0.85rem',
                      fontFamily: 'monospace',
                      outline: 'none',
                      resize: 'vertical'
                    }}
                  />
                </div>
              )}

              <div style={{
                background: 'rgba(15, 23, 42, 0.5)',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid rgba(255, 255, 255, 0.05)',
                fontSize: '0.75rem',
                color: '#94a3b8',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}>
                <Lock size={14} color="#00d4ff" />
                <span>Le chiavi private rimangono cifrate in locale e non viaggiano mai in chiaro sulla rete.</span>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="sn-btn-primary"
                style={{ padding: '12px', marginTop: 4, fontSize: '0.88rem' }}
              >
                {loading ? 'Elaborazione Crittografica...' : (
                  mode === 'login' ? 'Sblocca Wallet & Accedi' :
                  mode === 'register' ? 'Genera Wallet & Accedi' :
                  'Ripristina Wallet & Accedi'
                )}
              </button>

              {mode === 'login' && (
                <button
                  type="button"
                  onClick={handleLoginWithNode}
                  disabled={loading}
                  style={{
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(0, 212, 255, 0.25)',
                    borderRadius: 8,
                    color: '#94a3b8',
                    padding: '10px 14px',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    transition: 'all 0.15s ease'
                  }}
                >
                  <ShieldCheck size={16} color="#00d4ff" />
                  <span>Accedi come Nodo Locale (Senza Password)</span>
                </button>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuthWalletModal;
