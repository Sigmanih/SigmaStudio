import React, { useState, useEffect } from 'react';
import { ShieldCheck, CheckCircle2 } from 'lucide-react';

export default function HFTokenSettings({ addToast }) {
  const [hfToken, setHfToken] = useState('');
  const [hfHasToken, setHfHasToken] = useState(false);
  const [savingHfToken, setSavingHfToken] = useState(false);

  useEffect(() => {
    // Check if token is already configured on mount
    fetch('/api/config/hf_token')
      .then(r => r.json())
      .then(data => {
        if (data.success && data.hf_has_token !== undefined) {
          setHfHasToken(data.hf_has_token);
        }
      })
      .catch(() => {});

  }, []);

  const handleSave = async () => {
    if (!hfToken.trim()) {
      if (addToast) addToast('❌ Inserisci un token valido', 'error');
      return;
    }
    setSavingHfToken(true);
    try {
      const res = await fetch('/api/config/hf_token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hf_token: hfToken }),
      });
      const json = await res.json();
      if (json.success) {
        setHfHasToken(json.hf_has_token);
        if (addToast) addToast('🔑 HF_TOKEN salvato con successo!', 'success', 5000);
      } else {
        if (addToast) addToast(`❌ Errore: ${json.error}`, 'error');
      }
    } catch (err) {
      if (addToast) addToast(`❌ Errore di rete: ${err.message}`, 'error');
    } finally {
      setSavingHfToken(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '2px', lineHeight: 1.6 }}>
              Imposta il tuo <strong>HuggingFace Token</strong> per velocizzare i download dei modelli e dei dataset.
              <br />
              Senza token, HuggingFace limita la velocità a ~50KB/s — con token arrivi a 5-50MB/s.
              <br /><br />
              Puoi ottenere il tuo token su{' '}
              <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer"
                style={{ color: 'var(--primary)', textDecoration: 'underline' }}>
                huggingface.co/settings/tokens
              </a>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
              <input
                type="password"
                className="training-input"
                placeholder="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                value={hfToken}
                onChange={(e) => setHfToken(e.target.value)}
                style={{ flex: 1, fontFamily: 'monospace', fontSize: '13px' }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                className="training-start-btn"
                style={{ width: 'auto', padding: '10px 24px' }}
                onClick={handleSave}
                disabled={savingHfToken || !hfToken.trim()}
              >
                {savingHfToken ? (
                  <><div className="training-spinner" style={{ width: '14px', height: '14px', borderColor: 'rgba(0,0,0,0.2)', borderTopColor: '#000' }} /> Salvataggio...</>
                ) : hfHasToken ? (
                  <><CheckCircle2 size={14} /> Aggiorna Token</>
                ) : (
                  <><CheckCircle2 size={14} /> Salva Token</>
                )}
              </button>
              {hfHasToken && (
                <span style={{ color: '#3fb950', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <CheckCircle2 size={14} /> Token configurato
                </span>
              )}
            </div>

      <div style={{
        background: 'rgba(0,210,255,0.03)', border: '1px solid rgba(0,210,255,0.1)',
        borderRadius: '12px', padding: '16px', fontSize: '0.68rem',
        color: 'var(--text-dim)', lineHeight: 1.6,
      }}>
        <strong style={{ color: 'var(--primary)' }}>💡 Perché serve il token?</strong>
        <ul style={{ margin: '8px 0 0 16px', padding: 0 }}>
          <li>Download dei modelli da HuggingFace 10x più veloci</li>
          <li>Accesso a modelli con <em>gated access</em> (es. LLaMA, Mistral, Gemma)</li>
          <li>Necessario per alcuni dataset privati o con restrizioni</li>
          <li>Il token viene salvato in <code style={{ color: 'var(--primary)', fontFamily: 'JetBrains Mono', fontSize: '0.6rem' }}>config.json</code> e applicato automaticamente a ogni riavvio</li>
        </ul>
      </div>
    </div>
  );
}