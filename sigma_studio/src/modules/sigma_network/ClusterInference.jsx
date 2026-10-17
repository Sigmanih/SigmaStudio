import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Send,
  Cpu,
  Coins,
  ShieldCheck,
  Zap,
  Activity,
  Layers,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';

const ClusterInference = ({ initialPeer, walletBalance, onReceiptCreated }) => {
  const [clusterModels, setClusterModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [prompt, setPrompt] = useState('Spiega il funzionamento di un cluster P2P decentralizzato per intelligenza artificiale.');
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [telemetry, setTelemetry] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const terminalEndRef = useRef(null);

  const fetchModels = async () => {
    try {
      const resp = await fetch('/api/sigma_network/cluster/models');
      if (resp.ok) {
        const data = await resp.json();
        const modelsList = Array.isArray(data) ? data : (data.models || []);
        setClusterModels(modelsList);
        if (modelsList.length > 0 && !selectedModel) {
          // Seleziona preferibilmente il peer passato da radar o il primo disponibile
          if (initialPeer && Array.isArray(initialPeer.models) && initialPeer.models.length > 0) {
            const match = modelsList.find(m => m.provider_id === initialPeer.peer_id);
            setSelectedModel(match || modelsList[0]);
          } else {
            setSelectedModel(modelsList[0]);
          }
        }
      }
    } catch (e) {
      console.error('Errore caricamento modelli cluster', e);
    }
  };

  useEffect(() => {
    fetchModels();
  }, [initialPeer]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [streamedText]);

  const handleRunInference = async () => {
    if (!prompt.trim() || !selectedModel || isGenerating) return;

    setIsGenerating(true);
    setStreamedText('');
    setTelemetry(null);
    setErrorMsg(null);

    const startTime = performance.now();
    let tokenCount = 0;

    try {
      const response = await fetch('/api/sigma_network/cluster/infer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          model: selectedModel.model_id,
          max_tokens: 1024,
          preferred_peer_id: selectedModel.is_local ? null : selectedModel.provider_id,
        }),
      });

      if (!response.ok) {
        let errDetail = `Errore HTTP ${response.status}`;
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errJson.error || errDetail;
        } catch {
          try {
            const raw = await response.text();
            if (raw) errDetail = raw;
          } catch {}
        }
        throw new Error(errDetail);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (jsonStr === '[DONE]') continue;

          try {
            const event = JSON.parse(jsonStr);
            if (event.token) {
              tokenCount++;
              setStreamedText(prev => prev + event.token);
            } else if (event.error) {
              setErrorMsg(event.error);
            } else if (event.type === 'finish') {
              const elapsedSec = (performance.now() - startTime) / 1000;
              setTelemetry({
                tokens: event.tokens_generated || tokenCount,
                cost: event.cost_ailocoin || 0,
                speed: elapsedSec > 0 ? (tokenCount / elapsedSec).toFixed(1) : '0',
                receiptId: event.receipt_id,
                provider: event.provider_name || selectedModel.provider_name,
              });
              if (onReceiptCreated) onReceiptCreated();
            }
          } catch (pe) {
            // frammento testo grezzo
            tokenCount++;
            setStreamedText(prev => prev + jsonStr);
          }
        }
      }
    } catch (err) {
      setErrorMsg(err.message || 'Errore durante la comunicazione con il cluster P2P');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="sn-cluster-view">
      {/* Catalogo Modelli del Cluster */}
      <div className="sn-models-catalog">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#00d4ff', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Layers size={18} /> Modelli nel Cluster ({clusterModels.length})
          </h3>
          <button
            onClick={fetchModels}
            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.75rem' }}
          >
            Aggiorna
          </button>
        </div>

        <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
          Interroga qualsiasi modello esposto dai peer. Se è remoto, i token vengono pagati in AiloCoin al completamento.
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', maxHeight: '560px' }}>
          {clusterModels.map((m, idx) => {
            const isSelected = selectedModel?.model_id === m.model_id && selectedModel?.provider_id === m.provider_id;
            return (
              <div
                key={`${m.provider_id}-${m.model_id}-${idx}`}
                className={`sn-model-card ${isSelected ? 'selected' : ''}`}
                onClick={() => setSelectedModel(m)}
              >
                <div className="sn-model-card-header">
                  <span className="sn-model-name">{m.name}</span>
                  <span style={{
                    fontSize: '0.7rem',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: m.is_local ? 'rgba(0, 212, 255, 0.15)' : 'rgba(168, 85, 247, 0.15)',
                    color: m.is_local ? '#38bdf8' : '#c084fc',
                    fontWeight: 700,
                  }}>
                    {m.is_local ? 'LOCALE' : 'P2P REMOTO'}
                  </span>
                </div>

                <div className="sn-model-provider">
                  Fornitore: <strong>{m.provider_name}</strong> {m.latency_ms > 0 && `(${Math.round(m.latency_ms)}ms)`}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                  <span className="sn-model-rate">
                    {m.is_local ? 'Gratuito (Tuo PC)' : `1 AiloCoin / ${m.rate_tokens_per_coin} tok`}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: m.status === 'online' || m.is_local ? '#34d399' : '#94a3b8' }}>
                    ● {m.status}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Terminale di Generazione ed Esecuzione */}
      <div className="sn-infer-terminal">
        <div className="sn-terminal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Cpu size={16} color="#00d4ff" />
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f1f5f9' }}>
              {selectedModel ? `${selectedModel.name} via ${selectedModel.provider_name}` : 'Nessun modello selezionato'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: '0.75rem', color: '#94a3b8' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#38bdf8' }}>
              <Coins size={14} /> Saldo: {walletBalance.toFixed(2)} AiloCoin
            </span>
          </div>
        </div>

        {/* Telemetria HUD in tempo reale */}
        {telemetry && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.1)',
            borderBottom: '1px solid rgba(16, 185, 129, 0.2)',
            padding: '8px 18px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 16,
            fontSize: '0.75rem',
            color: '#34d399',
            alignItems: 'center'
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <CheckCircle2 size={13} /> <strong>{telemetry.tokens}</strong> token generati
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Zap size={13} /> {telemetry.speed} tok/sec
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Coins size={13} /> Costo: {telemetry.cost} AiloCoin
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#a855f7' }}>
              <ShieldCheck size={13} /> Ricevuta: {telemetry.receiptId.slice(0, 8)}...
            </span>
          </div>
        )}

        {/* Notifica di errore */}
        {errorMsg && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
            padding: '10px 18px',
            fontSize: '0.8rem',
            color: '#f87171',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <AlertTriangle size={15} /> {errorMsg}
          </div>
        )}

        {/* Corpo Output Streaming */}
        <div className="sn-terminal-body">
          {streamedText ? (
            <div>
              {streamedText}
              {isGenerating && <span className="sn-cursor">▋</span>}
            </div>
          ) : (
            <div style={{ color: '#64748b', fontStyle: 'italic', padding: '40px 0', textAlign: 'center' }}>
              I risultati generati dal cluster P2P appariranno qui in streaming live.
            </div>
          )}
          <div ref={terminalEndRef} />
        </div>

        {/* Input Prompt Footer */}
        <div className="sn-terminal-footer">
          <input
            type="text"
            className="sn-prompt-input"
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleRunInference()}
            placeholder="Scrivi una richiesta per il cluster P2P..."
            disabled={isGenerating}
          />
          <button
            className="sn-send-btn"
            onClick={handleRunInference}
            disabled={isGenerating || !prompt.trim()}
          >
            {isGenerating ? <Activity size={16} className="sn-spin" /> : <Send size={16} />}
            <span>{isGenerating ? 'Generazione...' : 'Invia al Cluster'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClusterInference;
