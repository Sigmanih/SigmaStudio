import React, { useState, useEffect, useCallback } from 'react';
import { 
  Home, MessageSquare, Scroll, ExternalLink,
  DownloadCloud, Layers, Cpu, ShieldCheck, Terminal, 
  ArrowRight, Sparkles, Zap, Wrench, Globe, CheckCircle2,
  RefreshCw, AlertCircle, Download, GitBranch, Check,
  Users, Bell, Info
} from 'lucide-react';

import { useApp } from '../contexts/AppContext';
import SkillsShowcaseSlider from './SkillsShowcaseSlider';

export default function WelcomeDashboard({ modules, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#94a3b8';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 20px rgba(190, 160, 110, 0.12)' : '0 10px 30px rgba(0, 0, 0, 0.4)';

  // GitHub & Roles Update Check State
  const [updateState, setUpdateState] = useState({
    loading: true,
    checking: false,
    updateAvailable: false,
    latestVersion: '0.9.0',
    currentVersion: '0.9.0',
    phase: 'Beta Open Release',
    releaseTitle: 'Sigma AI Studio v0.9.0 (Beta)',
    releaseNotes: '',
    publishedAt: '',
    htmlUrl: 'https://github.com/Sigmanih/SigmaStudio/releases',
    downloadUrl: 'https://github.com/Sigmanih/SigmaStudio/archive/refs/heads/main.zip',
    activeRolesCount: 20,
    hasRoleUpdates: false,
    // Stato commit locale / remoto
    gitAvailable: false,
    commitsBehind: 0,
    newCommits: [],
    localCommit: '',
    localBranch: '',
    remoteCommit: '',
    remoteBranch: 'main',
    diverged: false,
    lastChecked: null,
    error: null,
    applying: false,
    applyResult: null
  });
  const [showCommits, setShowCommits] = useState(false);

  // Check for updates
  const checkForUpdates = useCallback(async (isManual = false) => {
    if (isManual) {
      setUpdateState(p => ({ ...p, checking: true, error: null, applyResult: null }));
    }
    try {
      const res = await fetch(`/api/system/updates/check${isManual ? '?force=1' : ''}`);
      const data = await res.json();
      if (data && data.success) {
        setUpdateState(p => ({
          ...p,
          loading: false,
          checking: false,
          updateAvailable: !!data.update_available,
          latestVersion: data.latest_version || '0.9.0',
          currentVersion: data.current_version || '0.9.0',
          phase: data.phase || 'Beta Open Release',
          releaseTitle: data.release_title || `Sigma AI Studio v${data.current_version || '0.9.0'}`,
          releaseNotes: data.release_notes || '',
          publishedAt: data.published_at || '',
          htmlUrl: data.html_url || 'https://github.com/Sigmanih/SigmaStudio/releases',
          downloadUrl: data.download_url || 'https://github.com/Sigmanih/SigmaStudio/archive/refs/heads/main.zip',
          activeRolesCount: data.active_roles_count || 20,
          hasRoleUpdates: !!data.has_role_updates,
          gitAvailable: !!data.git_available,
          commitsBehind: data.commits_behind || 0,
          newCommits: Array.isArray(data.new_commits) ? data.new_commits : [],
          localCommit: data.local_commit || '',
          localBranch: data.local_branch || '',
          remoteCommit: data.remote_commit || '',
          remoteBranch: data.remote_branch || 'main',
          diverged: !!data.diverged,
          lastChecked: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          error: null
        }));
      } else {
        setUpdateState(p => ({ ...p, loading: false, checking: false }));
      }
    } catch (e) {
      console.debug("Update check fallback:", e);
      setUpdateState(p => ({
        ...p,
        loading: false,
        checking: false,
        lastChecked: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }));
    }
  }, []);

  // Apply update (trigger git pull & catalog sync)
  const applyUpdate = async () => {
    setUpdateState(p => ({ ...p, applying: true, applyResult: null }));
    try {
      const res = await fetch('/api/system/updates/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      setUpdateState(p => ({
        ...p,
        applying: false,
        applyResult: {
          success: data.success,
          message: data.message || (data.success ? 'Aggiornamento applicato con successo!' : 'Verifica manuale richiesta.'),
          log: data.log || '',
          restartRequired: !!data.restart_required
        },
        updateAvailable: data.success ? false : p.updateAvailable
      }));
      // Re-check after 2 seconds
      setTimeout(() => checkForUpdates(false), 2000);
    } catch (err) {
      setUpdateState(p => ({
        ...p,
        applying: false,
        applyResult: {
          success: false,
          message: `Errore durante l'aggiornamento: ${err.message}`
        }
      }));
    }
  };

  useEffect(() => {
    checkForUpdates(false);
  }, [checkForUpdates]);

  return (
    <div className="wg-container" style={{ position: 'relative' }}>
      {/* Minimal Header in Stile Chat AI — Compatto e Senza Bottoni */}
      <div style={{
        position: 'relative',
        zIndex: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 14px',
        borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.08)',
        background: isLight ? 'rgba(255, 255, 255, 0.85)' : 'rgba(10, 14, 26, 0.75)',
        backdropFilter: 'blur(10px)',
        minHeight: '38px',
        boxSizing: 'border-box',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{
            width: '22px', height: '22px', borderRadius: '6px',
            background: isLight ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 210, 255, 0.15)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: isLight ? '#ea580c' : '#00d2ff'
          }}>
            <Home size={12} />
          </div>
          <span style={{ fontSize: '0.80rem', fontWeight: 800, color: titleColor, letterSpacing: '0.2px' }}>
            Sigma Studio Home
          </span>
          <span style={{ fontSize: '0.65rem', color: subtitleColor, paddingLeft: '2px' }}>
            • v{updateState.currentVersion} • {updateState.activeRolesCount} Ruoli Attivi
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '0.62rem',
            padding: '2px 7px',
            borderRadius: '4px',
            background: updateState.updateAvailable ? 'rgba(250, 160, 60, 0.2)' : 'rgba(63, 185, 80, 0.15)',
            color: updateState.updateAvailable ? '#faa03c' : '#3fb950',
            border: `1px solid ${updateState.updateAvailable ? '#faa03c' : '#3fb950'}40`,
            fontWeight: 700
          }}>
            {updateState.updateAvailable ? '⚡ Aggiornamento Disponibile' : '🟢 Sistema Online'}
          </span>
        </div>
      </div>

      {/* Corpo Principale */}
      <div className="welcome-content-body" style={{ padding: '20px 24px 28px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
        
        {/* ── ALERT DIRETTO GITHUB: AGGIORNAMENTI RELEASE & RUOLI ATTIVI ──────── */}
        <div className="welcome-update-card">
          {/* Left: Icon & Update Summary */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: '280px', flex: 1 }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: updateState.updateAvailable ? 'rgba(250, 160, 60, 0.2)' : 'rgba(0, 210, 255, 0.12)',
              border: updateState.updateAvailable ? '1px solid #faa03c' : '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              {updateState.checking ? (
                <RefreshCw size={20} className="spin" color="#00d2ff" />
              ) : updateState.updateAvailable ? (
                <Bell size={20} color="#faa03c" />
              ) : (
                <CheckCircle2 size={20} color="#3fb950" />
              )}
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.88rem', fontWeight: 800, color: titleColor }}>
                  {updateState.updateAvailable
                    ? (updateState.commitsBehind > 0
                        ? `⚡ ${updateState.commitsBehind} ${updateState.commitsBehind === 1 ? 'nuovo commit disponibile' : 'nuovi commit disponibili'} su GitHub`
                        : `⚡ Nuova Versione Rilasciata su GitHub: v${updateState.latestVersion}`)
                    : `🟢 Sigma AI Studio v${updateState.currentVersion} • Sistema & Ruoli Aggiornati`}
                </span>
                <span style={{
                  fontSize: '0.62rem',
                  padding: '2px 7px',
                  borderRadius: '4px',
                  background: updateState.updateAvailable ? 'rgba(250, 160, 60, 0.2)' : 'rgba(63, 185, 80, 0.15)',
                  color: updateState.updateAvailable ? '#faa03c' : '#3fb950',
                  border: `1px solid ${updateState.updateAvailable ? '#faa03c' : '#3fb950'}40`,
                  fontWeight: 700
                }}>
                  {updateState.updateAvailable ? 'Aggiornamento Disponibile' : 'Ultima Release Beta'}
                </span>
              </div>

              <div style={{ fontSize: '0.74rem', color: subtitleColor, marginTop: '3px' }}>
                {updateState.updateAvailable ? (
                  <span>{updateState.releaseNotes || updateState.releaseTitle || 'Disponibile nuova versione con miglioramenti kernel e nuovi manifesti.'}</span>
                ) : updateState.gitAvailable && updateState.localCommit ? (
                  <span>
                    Allineato al commit <code style={{ fontFamily: 'monospace', opacity: 0.95 }}>{updateState.localCommit}</code>
                    {updateState.localBranch ? ` · ramo ${updateState.localBranch}` : ''}
                  </span>
                ) : (
                  <span>Versione open per la community. Repository GitHub sincronizzato con il catalogo dei ruoli attivi.</span>
                )}
                {updateState.lastChecked && (
                  <span style={{ marginLeft: '6px', opacity: 0.8 }}>• Verificato alle {updateState.lastChecked}</span>
                )}
              </div>

              {/* Riepilogo commit locale → remoto */}
              {updateState.updateAvailable && updateState.commitsBehind > 0 && (
                <div style={{ fontSize: '0.7rem', color: subtitleColor, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <span style={{ fontFamily: 'monospace' }}>
                    {updateState.localCommit} → {updateState.remoteCommit}
                  </span>
                  <span style={{ opacity: 0.75 }}>· ramo {updateState.remoteBranch}</span>
                  {updateState.newCommits.length > 0 && (
                    <button
                      onClick={() => setShowCommits(v => !v)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#faa03c',
                        cursor: 'pointer',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: 0
                      }}
                    >
                      {showCommits ? 'Nascondi novità' : 'Vedi cosa cambia'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right: Actions (Check, Download / Apply, GitHub Release) */}
          <div className="welcome-update-actions" style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            {/* Manual Refresh Button */}
            <button
              onClick={() => checkForUpdates(true)}
              disabled={updateState.checking || updateState.applying}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.15)',
                color: titleColor,
                fontSize: '0.74rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
              title="Controlla se ci sono nuove release o manifesti su GitHub"
            >
              <RefreshCw size={12} className={updateState.checking ? "spin" : ""} />
              <span>{updateState.checking ? 'Controllo...' : 'Verifica Aggiornamenti'}</span>
            </button>

            {/* Direct Download & Update Button */}
            {updateState.updateAvailable ? (
              <button
                onClick={applyUpdate}
                disabled={updateState.applying}
                style={{
                  padding: '7px 16px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #faa03c, #ff5064)',
                  border: 'none',
                  color: '#ffffff',
                  fontSize: '0.76rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  boxShadow: '0 4px 14px rgba(250, 160, 60, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {updateState.applying ? <RefreshCw size={13} className="spin" /> : <Download size={13} />}
                <span>{updateState.applying ? 'Download & Aggiornamento...' : 'Scarica & Aggiorna Ora'}</span>
              </button>
            ) : (
              <button
                onClick={applyUpdate}
                disabled={updateState.applying}
                style={{
                  padding: '6px 13px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, rgba(0, 210, 255, 0.15), rgba(79, 172, 254, 0.15))',
                  border: '1px solid rgba(0, 210, 255, 0.4)',
                  color: '#00d2ff',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}
                title="Sincronizza i manifesti e ruoli dal repository ufficiale"
              >
                {updateState.applying ? <RefreshCw size={12} className="spin" /> : <GitBranch size={12} />}
                <span>{updateState.applying ? 'Sincronizzazione...' : 'Sincronizza Ruoli'}</span>
              </button>
            )}

            {/* External GitHub Releases Link */}
            <a
              href={updateState.htmlUrl || "https://github.com/Sigmanih/SigmaStudio/releases"}
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                color: subtitleColor,
                fontSize: '0.74rem',
                fontWeight: 600,
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <ExternalLink size={12} />
              <span>{updateState.commitsBehind > 0 ? 'Vedi su GitHub' : 'Release GitHub'}</span>
            </a>
          </div>

          {/* Elenco dei nuovi commit disponibili */}
          {showCommits && updateState.newCommits.length > 0 && (
            <div style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: '10px',
              background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(0,0,0,0.35)',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255,255,255,0.1)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              maxHeight: '190px',
              overflowY: 'auto'
            }}>
              {updateState.newCommits.map(c => (
                <div key={c.sha} style={{ display: 'flex', alignItems: 'baseline', gap: '8px', fontSize: '0.72rem' }}>
                  <code style={{ fontFamily: 'monospace', color: '#faa03c', flexShrink: 0 }}>{c.sha}</code>
                  <span style={{ color: titleColor, flex: 1, minWidth: 0, wordBreak: 'break-word' }}>{c.message}</span>
                  <span style={{ color: subtitleColor, flexShrink: 0, opacity: 0.8 }}>{c.date}</span>
                </div>
              ))}
            </div>
          )}

          {/* Toast / Feedback Aggiornamento Applicato */}
          {updateState.applyResult && (
            <div style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '8px',
              background: updateState.applyResult.success ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 85, 85, 0.15)',
              border: `1px solid ${updateState.applyResult.success ? 'rgba(63, 185, 80, 0.4)' : 'rgba(255, 85, 85, 0.4)'}`,
              color: updateState.applyResult.success ? '#3fb950' : '#ff5555',
              fontSize: '0.74rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {updateState.applyResult.success ? <Check size={14} /> : <AlertCircle size={14} />}
                <span>{updateState.applyResult.message}</span>
              </div>
              {updateState.applyResult.log && (
                <span style={{ fontWeight: 500, opacity: 0.85, fontSize: '0.68rem', flex: 1, textAlign: 'right' }}>
                  {updateState.applyResult.log.split('\n')[0]}
                </span>
              )}
              <button
                onClick={() => setUpdateState(p => ({ ...p, applyResult: null }))}
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.8rem', padding: '0 4px' }}
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* ── BACHECA DI BENVENUTO ALLA VERSIONE 0.9.0 & COMMUNITY RELEASE ──────── */}
        <div className="welcome-main-card">
          {/* Header del Benvenuto */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <span style={{
                fontSize: '0.68rem',
                fontWeight: 800,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                padding: '3px 10px',
                borderRadius: '6px',
                background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.14)',
                color: isLight ? '#c2410c' : '#00d2ff',
                border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)'
              }}>
                ⚡ Versione 0.9.0 (Beta) • Open Community
              </span>
              <span style={{ fontSize: '0.76rem', color: subtitleColor, fontWeight: 600 }}>
                • Autonomia Sovrana, Zero Costi API & Privacy Assoluta
              </span>
            </div>

            <h2 style={{
              margin: '0 0 10px 0',
              fontSize: '1.4rem',
              fontWeight: 800,
              color: titleColor,
              letterSpacing: '-0.3px'
            }}>
              Benvenuto nella Versione 0.9.0 di Sigma AI Studio
            </h2>

            <p style={{
              margin: '0 0 12px 0',
              fontSize: '0.88rem',
              color: subtitleColor,
              lineHeight: 1.65,
              maxWidth: '1050px'
            }}>
              <strong>Sigma AI Studio</strong> è attualmente in <strong>fase Beta di rilascio aperto</strong>: l'intera community di sviluppatori, ricercatori e appassionati è <strong>completamente libera di utilizzarlo</strong>, sperimentare con i modelli linguistici locali, creare nuovi ruoli e condividere estensioni modulari.
            </p>

            <p style={{
              margin: 0,
              fontSize: '0.86rem',
              color: subtitleColor,
              lineHeight: 1.6,
              maxWidth: '1050px'
            }}>
              Grazie al motore <strong>SigmaEngine</strong> integrato, puoi scaricare modelli open-source (GGUF, Safetensors), quantizzarli e <strong>ottimizzarli su misura per il tuo hardware</strong> — da potenti workstation con GPU dedicate a dispositivi a basso consumo come il Raspberry Pi 5. Tutto gira in locale: <strong>nessun abbonamento, zero latenza cloud e privacy garantita</strong>.
            </p>
          </div>

          {/* I 4 Pilastri del Sistema Sintetizzati ed Enfatici */}
          <div className="welcome-pillars-grid">
            {/* Pilastro 1: SigmaEngine & Download Modelli */}
            <div className="welcome-pillar-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Cpu size={18} color="#00d2ff" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  1. SigmaEngine & Download Modelli
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Scarica qualsiasi modello open-source (GGUF, Safetensors) da Hugging Face ed eseguilo in locale con <strong>gestione dinamica VRAM/RAM</strong> per massime prestazioni sul tuo hardware.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#00d2ff', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Modelli' }, 'model_hub')}
              >
                <span>Gestisci modelli in Modelli</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 2: Manifesti & Ruoli Specialistici */}
            <div className="welcome-pillar-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(188, 140, 255, 0.15)', border: '1px solid rgba(188, 140, 255, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Scroll size={18} color="#bc8cff" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  2. Ruoli AI & Professioni Specialistiche
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Trasforma all'istante l'assistente in un esperto di codice, ingegneria, medicina o ricerca: i manifesti e ruoli applicano <strong>regole etiche e direttive disciplinari</strong> pronte all'uso.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#bc8cff', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Ruoli AI' }, 'whitepapers_lib')}
              >
                <span>Esplora {updateState.activeRolesCount} Ruoli Attivi</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 3: Protocollo MCP & Automazione */}
            <div className="welcome-pillar-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(255, 80, 100, 0.15)', border: '1px solid rgba(255, 80, 100, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Terminal size={18} color="#ff5064" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  3. Protocollo MCP & Azione sul Sistema
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Fornisci all'AI strumenti pratici tramite <strong>Model Context Protocol</strong>: esecuzione di script, gestione file, diagnostica hardware in tempo reale e controllo domotico IoT.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#ff5064', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'MCP Tools' }, 'mcp_hub')}
              >
                <span>Accedi al Gateway MCP</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Pilastro 4: Hub Skills & Estensioni da GitHub */}
            <div className="welcome-pillar-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Layers size={18} color="#3fb950" />
                </div>
                <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  4. Skills ed Estensioni Modulari
                </h3>
              </div>
              <p style={{ margin: 0, fontSize: '0.78rem', color: subtitleColor, lineHeight: 1.5 }}>
                Scarica e attiva con un click nuovi moduli ed estensioni (Creative Lab 3D, Audio Studio, Training Lab, Hardware Monitor) mantenendo il <strong>kernel sempre pulito e leggero</strong>.
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#3fb950', fontWeight: 700, marginTop: 'auto', cursor: 'pointer' }}
                onClick={() => openTab({ name: 'Skills' }, 'marketplace')}
              >
                <span>Apri Skills & Moduli</span> <ArrowRight size={12} />
              </div>
            </div>
          </div>

          {/* Quick Guide: Come iniziare */}
          <div className="welcome-guide-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Sparkles size={20} color={isLight ? '#c2410c' : '#00d2ff'} />
              <div>
                <div style={{ fontSize: '0.84rem', fontWeight: 700, color: titleColor }}>
                  Pronto per iniziare?
                </div>
                <div style={{ fontSize: '0.75rem', color: subtitleColor }}>
                  Apri la Chat per dialogare con l'assistente oppure visita la scheda Modelli per scaricare il tuo primo LLM locale.
                </div>
              </div>
            </div>

            <div className="welcome-guide-buttons" style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={() => openTab({ name: 'Chat' }, 'chat')}
                style={{
                  padding: '7px 14px', borderRadius: '8px',
                  background: isLight ? '#ea580c' : '#00d2ff',
                  border: 'none', color: '#ffffff',
                  fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                💬 Chat
              </button>
              <button
                onClick={() => openTab({ name: 'Modelli' }, 'model_hub')}
                style={{
                  padding: '7px 14px', borderRadius: '8px',
                  background: isLight ? '#ffffff' : 'rgba(255,255,255,0.08)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255, 255, 255, 0.15)',
                  color: isLight ? '#111827' : '#ffffff',
                  fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '6px'
                }}
              >
                ⚡ Modelli
              </button>
            </div>
          </div>

        </div>

        {/* ── CATALOGO SKILLS SHOWCASE SLIDER ──────── */}
        <SkillsShowcaseSlider openTab={openTab} />

        {/* ── FOOTER ESSENZIALE & PULITO ──────── */}
        <div style={{
          marginTop: 'auto',
          padding: '16px 0 6px 0',
          borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: subtitleColor,
          fontSize: '0.76rem',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={() => openTab({ path: 'README_IT.md', filename: 'README_IT.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#c2410c' : '#00d2ff',
                cursor: 'pointer',
                fontSize: '0.76rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: 0
              }}
            >
              🇮🇹 Documentazione IT
            </button>
            <span>•</span>
            <button
              onClick={() => openTab({ path: 'architettura.md', filename: 'architettura.md' }, 'editor')}
              style={{
                background: 'none',
                border: 'none',
                color: isLight ? '#7c3aed' : '#a78bfa',
                cursor: 'pointer',
                fontSize: '0.76rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: 0
              }}
            >
              🏛️ Architettura
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ color: '#3fb950' }}>●</span>
            <span>Sigma AI Studio v0.9.0 (Beta) • Community Open Release • Pronto e operativo</span>
          </div>
        </div>

      </div>
    </div>
  );
}