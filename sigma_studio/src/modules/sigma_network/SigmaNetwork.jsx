import React, { useState, useEffect, useCallback } from 'react';
import {
  Radio,
  Layers,
  Users,
  Share2,
  Coins,
  Pickaxe,
  Sliders,
  Server,
  Globe,
  KeyRound,
  UserCheck,
  LogOut
} from 'lucide-react';
import PeerRadar from './PeerRadar.jsx';
import ClusterInference from './ClusterInference.jsx';
import EnsembleSwarm from './EnsembleSwarm.jsx';
import FederatedDashboard from './FederatedDashboard.jsx';
import WalletDashboard from './WalletDashboard.jsx';
import MiningConsole from './MiningConsole.jsx';
import ProviderSettings from './ProviderSettings.jsx';
import AuthWalletModal from './AuthWalletModal.jsx';
import './styles/sigma-network.css';

const SigmaNetwork = () => {
  const [activeTab, setActiveTab] = useState('radar');
  const [networkMap, setNetworkMap] = useState(null);
  const [walletData, setWalletData] = useState(null);
  const [identity, setIdentity] = useState(null);
  const [settings, setSettings] = useState(null);
  const [authSession, setAuthSession] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [initialPeerForQuery, setInitialPeerForQuery] = useState(null);
  const [, setLoading] = useState(true);

  // Caricamento Dati Rete & Stato Sessione Wallet
  const fetchAllData = useCallback(async () => {
    try {
      const [mapRes, walletRes, idRes, setRes, authRes] = await Promise.all([
        fetch('/api/sigma_network/peers/map'),
        fetch('/api/sigma_network/wallet'),
        fetch('/api/sigma_network/identity'),
        fetch('/api/sigma_network/settings'),
        fetch('/api/sigma_network/auth/session'),
      ]);

      if (mapRes.ok) setNetworkMap(await mapRes.json());
      if (walletRes.ok) setWalletData(await walletRes.json());
      if (idRes.ok) setIdentity(await idRes.json());
      if (setRes.ok) setSettings(await setRes.json());
      if (authRes.ok) setAuthSession(await authRes.json());
    } catch (err) {
      console.error('Errore sincronizzazione Sigma Network', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
    // Avvia la scoperta peer locale UDP in background e sweep immediato
    fetch('/api/sigma_network/discovery/start', { method: 'POST' }).catch(() => {});
    fetch('/api/sigma_network/cluster/sweep', { method: 'POST' })
      .then(() => fetchAllData())
      .catch(() => {});
    const timer = setInterval(fetchAllData, 6000);
    return () => clearInterval(timer);
  }, [fetchAllData]);

  // Gestione toggle veloce Provider Mode dall'header
  const handleToggleProviderQuick = async () => {
    if (!settings) return;
    const newSharing = !settings.sharing_enabled;
    try {
      const resp = await fetch('/api/sigma_network/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sharing_enabled: newSharing }),
      });
      if (resp.ok) {
        setSettings(prev => ({ ...prev, sharing_enabled: newSharing }));
        fetchAllData();
      }
    } catch (e) {
      console.error('Errore toggle provider rapido', e);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/sigma_network/auth/logout', { method: 'POST' });
      fetchAllData();
    } catch (e) {
      console.error('Errore logout', e);
    }
  };

  const handleSelectPeerForQuery = (peer) => {
    setInitialPeerForQuery(peer);
    setActiveTab('cluster');
  };

  const isProviderActive = Boolean(settings?.sharing_enabled);
  const currentBalance = walletData?.balance || 0;
  const isAuthenticated = Boolean(authSession?.authenticated);

  return (
    <div className="sigma-network-container">
      {/* Header Futuristico Sigma Network & Ailo */}
      <header className="sn-header">
        <div className="sn-header-left">
          <div className="sn-title-group">
            <h1 className="sn-title">
              <Globe size={22} color="#00d4ff" />
              Sigma Network P2P
            </h1>
            <div className="sn-subtitle">
              <span>{authSession?.username || identity?.name || 'Sigma Studio'}</span>
              <span>•</span>
              <span style={{ fontFamily: 'monospace' }}>
                {identity?.peer_id ? `${identity.peer_id.slice(0, 8)}...` : 'offline'}
              </span>
            </div>
          </div>
        </div>

        <div className="sn-header-right">
          {/* Badge / Login Utente Wallet */}
          {isAuthenticated ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: 8,
              padding: '6px 12px',
              fontSize: '0.82rem',
              color: '#34d399'
            }}>
              <UserCheck size={15} />
              <span style={{ fontWeight: 600 }}>{authSession.username}</span>
              <button
                onClick={handleLogout}
                title="Disconnetti wallet"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: 2,
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <LogOut size={13} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsAuthModalOpen(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'linear-gradient(135deg, rgba(0, 212, 255, 0.15), rgba(56, 189, 248, 0.25))',
                border: '1px solid #00d4ff',
                borderRadius: 8,
                padding: '6px 14px',
                color: '#38bdf8',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <KeyRound size={15} />
              <span>Login / Collega Wallet</span>
            </button>
          )}

          <div className="sn-badge" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#34d399' }}>
            <span className="sn-badge-pulse" />
            <span>P2P Scan 47777</span>
          </div>

          {/* Toggle Rapido Provider Mode */}
          <button
            className={`sn-toggle-provider ${isProviderActive ? 'active' : ''}`}
            onClick={handleToggleProviderQuick}
            title="Attiva/disattiva la condivisione della tua GPU/CPU come fornitore nel cluster"
          >
            <Server size={14} />
            <span>{isProviderActive ? 'Provider ON' : 'Provider OFF'}</span>
          </button>

          {/* Pill Saldo AiloCoin */}
          <div
            className="sn-wallet-pill"
            onClick={() => setActiveTab('wallet')}
            title="Clicca per aprire il Wallet AiloCoin"
          >
            <Coins size={16} />
            <span>{currentBalance.toFixed(2)} AILO</span>
          </div>
        </div>
      </header>

      {/* Barra di Navigazione Tab */}
      <nav className="sn-nav-tabs">
        <button
          className={`sn-tab-btn ${activeTab === 'radar' ? 'active' : ''}`}
          onClick={() => setActiveTab('radar')}
        >
          <Radio size={16} /> Radar Nodi
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'cluster' ? 'active' : ''}`}
          onClick={() => setActiveTab('cluster')}
        >
          <Layers size={16} /> Inferenza Singola
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'ensemble' ? 'active' : ''}`}
          onClick={() => setActiveTab('ensemble')}
        >
          <Users size={16} /> Ensemble Swarm
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'federated' ? 'active' : ''}`}
          onClick={() => setActiveTab('federated')}
        >
          <Share2 size={16} /> Federated Learning
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'wallet' ? 'active' : ''}`}
          onClick={() => setActiveTab('wallet')}
        >
          <Coins size={16} /> Wallet AiloCoin
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'mining' ? 'active' : ''}`}
          onClick={() => setActiveTab('mining')}
        >
          <Pickaxe size={16} /> PoUW Mining
        </button>

        <button
          className={`sn-tab-btn ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <Sliders size={16} /> Impostazioni Provider
        </button>
      </nav>

      {/* Vista Principale */}
      <main className="sn-main-content">
        {activeTab === 'radar' && (
          <PeerRadar
            networkMap={networkMap}
            onRefresh={fetchAllData}
            onSelectPeerForQuery={handleSelectPeerForQuery}
          />
        )}

        {activeTab === 'cluster' && (
          <ClusterInference
            initialPeer={initialPeerForQuery}
            walletBalance={currentBalance}
            onReceiptCreated={fetchAllData}
          />
        )}

        {activeTab === 'ensemble' && (
          <EnsembleSwarm
            identity={identity}
            onRefreshWallet={fetchAllData}
          />
        )}

        {activeTab === 'federated' && (
          <FederatedDashboard
            onRefreshWallet={fetchAllData}
          />
        )}

        {activeTab === 'wallet' && (
          <WalletDashboard
            walletData={walletData}
            identity={identity}
            onRefresh={fetchAllData}
          />
        )}

        {activeTab === 'mining' && (
          <MiningConsole
            onRewardMined={fetchAllData}
          />
        )}

        {activeTab === 'settings' && (
          <ProviderSettings
            settings={settings}
            onSaveSettings={fetchAllData}
          />
        )}
      </main>

      {/* Modal di Autenticazione & Gestione Wallet */}
      <AuthWalletModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={() => {
          fetchAllData();
        }}
      />
    </div>
  );
};

export default SigmaNetwork;
