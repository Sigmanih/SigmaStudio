// ==============================================================================
// sigma_studio/src/modules/ModuleNotInstalled.jsx
// Schermata fallback interattiva con installazione diretta in 1-Click.
// Installa e attiva la skill in tempo reale senza richiedere il refresh della pagina.
// ==============================================================================
import React, { useState } from 'react';
import { Package, ArrowRight, Download, RefreshCw, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
import { useApp } from '../contexts/AppContext';

const MODULE_META = {
  creative_studio: { id: 'sigma_creative_lab',  icon: '🎨', name: 'Creative Lab 3D/2D',            color: '#ff5064', desc: 'Studio generativo 3D/2D: FLUX, SDXL, Blender headless e rimozione sfondo SAM2.' },
  training_lab:    { id: 'sigma_training_lab',   icon: '🧠', name: 'Training Lab & SLM Forge',       color: '#d29922', desc: 'Fine-tuning QLoRA Unsloth, forgia SLM e 11 benchmark ufficiali.' },
  hardware_lab:    { id: 'sigma_hardware_lab',   icon: '⚡', name: 'Hardware Lab & VRAM',            color: '#00d2ff', desc: 'Telemetria in tempo reale di GPU VRAM, RAM, CPU e gestione processi CUDA.' },
  hardware:        { id: 'sigma_hardware_lab',   icon: '⚡', name: 'Hardware Lab & VRAM',            color: '#00d2ff', desc: 'Telemetria in tempo reale di GPU VRAM, RAM, CPU e gestione processi CUDA.' },
  model_hub:       { id: 'sigma_model_hub',      icon: '📥', name: 'Model Hub & HF Downloader',       color: '#ffb86c', desc: 'Esplora e scarica modelli da Hugging Face con deploy diretto in SigmaEngine.' },
  hf_hub:          { id: 'sigma_model_hub',      icon: '📥', name: 'Model Hub & HF Downloader',       color: '#ffb86c', desc: 'Esplora e scarica modelli da Hugging Face con deploy diretto in SigmaEngine.' },
  research_lab:    { id: 'sigma_research_lab',   icon: '🔬', name: 'Pipelines Lab & Dynamic Swarm',  color: '#7c5bf0', desc: 'Pianificatore DAG multi-agente per ricerche scientifiche e codice auto-correggente.' },
  knowledge:       { id: 'sigma_knowledge',      icon: '🗺️', name: 'Knowledge Explorer',             color: '#00d2ff', desc: 'Grafo relazionale D3.js, formulari KaTeX e memoria RAG episodica.' },
  mappa_argomenti: { id: 'sigma_knowledge',      icon: '🗺️', name: 'Knowledge Explorer',             color: '#00d2ff', desc: 'Grafo relazionale D3.js, formulari KaTeX e memoria RAG episodica.' },
  mcp_hub:         { id: 'sigma_mcp_hub',        icon: '🔧', name: 'MCP Tools Hub',                  color: '#00f2fe', desc: 'Gateway centralizzato per 12 server MCP, permessi e governance di sicurezza.' },
  music:           { id: 'audio_studio',         icon: '📻', name: 'Hi-Fi Sound & FM Radio Studio',  color: '#00f2fe', desc: 'Radio FM nazionali in diretta, YouTube Live e generatore binaurale a 432Hz.' },
  music_lounge:    { id: 'audio_studio',         icon: '📻', name: 'Hi-Fi Sound & FM Radio Studio',  color: '#00f2fe', desc: 'Radio FM nazionali in diretta, YouTube Live e generatore binaurale a 432Hz.' },
  audio_studio:    { id: 'audio_studio',         icon: '📻', name: 'Hi-Fi Sound & FM Radio Studio',  color: '#00f2fe', desc: 'Radio FM nazionali in diretta, YouTube Live e generatore binaurale a 432Hz.' },
  voice_studio:    { id: 'sigma_voice_studio',   icon: '🎙️', name: 'Voice Studio & Neural Speech',    color: '#ff79c6', desc: 'Sintesi vocale neurale, trascrizione Whisper e clonazione vocale real-time.' },
  developer_studio:{ id: 'sigma_developer_lab',  icon: '💻', name: 'Developer Studio & Sandbox',     color: '#10b981', desc: 'Editor di codice avanzato, terminale integrato ed esecuzione sandbox.' },
  developer_lab:   { id: 'sigma_developer_lab',  icon: '💻', name: 'Developer Studio & Sandbox',     color: '#10b981', desc: 'Editor di codice avanzato, terminale integrato ed esecuzione sandbox.' },
  network_lab:     { id: 'sigma_network_lab',    icon: '🌐', name: 'Network Explorer & Web Research',color: '#3fb950', desc: 'Ricerche web live, compositore di chiamate HTTP REST e diagnostica DNS.' },
  roadmap:         { id: 'sigma_roadmap',        icon: '📅', name: 'Pianificazione & Task Audit',    color: '#faa03c', desc: 'Tabellone Kanban interattivo, calendario milestone e audit trail.' },
  email_client:    { id: 'sigma_email_client',   icon: '✉️', name: 'Email Hub & Client',             color: '#38bdf8', desc: 'Client di posta elettronica IMAP/SMTP integrato con analisi AI dei messaggi.' },
  messaging_hub:   { id: 'sigma_messaging_hub',  icon: '💬', name: 'Messaging & Notification Hub',   color: '#bc8cff', desc: 'Invio notifiche push broadcast su Telegram, Discord e Slack via MCP.' },
  domotica:        { id: 'sigma_domotica',       icon: '🏠', name: 'Domotica & Home Assistant IoT',  color: '#10b981', desc: 'Controllo completo della smart home: luci, clima, sensori e scene via MCP.' },
  home_assistant:  { id: 'sigma_domotica',       icon: '🏠', name: 'Domotica & Home Assistant IoT',  color: '#10b981', desc: 'Controllo completo della smart home: luci, clima, sensori e scene via MCP.' },
};

export default function ModuleNotInstalled({ tabType, openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';
  const meta = MODULE_META[tabType] || { id: tabType, icon: '📦', name: tabType, color: '#8b8fa3', desc: 'Skill componibile di Sigma Studio.' };

  const [installing, setInstalling] = useState(false);
  const [installStatus, setInstallStatus] = useState('');
  const [errorMsg, setErrorMsg] = useState(null);

  const handleQuickInstall = async () => {
    setInstalling(true);
    setErrorMsg(null);
    setInstallStatus(`Connessione al repository e download modulo '${meta.name}'...`);

    const moduleId = meta.id;
    const repoUrl = `https://github.com/Sigmanih/SigmaStudio-Moduli/tree/main/modules/${moduleId}`;

    try {
      const res = await fetch('/api/marketplace/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module_id: moduleId, repo_url: repoUrl })
      });

      if (res.ok) {
        setInstallStatus('Registrazione backend e attivazione componenti...');

        // Update local storage
        try {
          const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
          existing[moduleId] = true;
          if (moduleId === 'audio_studio') existing['sigma_audio_studio'] = true;
          localStorage.setItem('sigma_modules_state', JSON.stringify(existing));
        } catch (e) {}

        // Dispatch events for real-time reactivity across all components
        window.dispatchEvent(new CustomEvent('sigma_modules_updated', { detail: { moduleId, installed: true } }));
        window.dispatchEvent(new CustomEvent('sigma_skills_updated'));

        setInstallStatus('Skill installata con successo!');
        
        // Auto-refresh state in-place without page reload
        setTimeout(() => {
          if (openTab) {
            openTab({ name: meta.name }, tabType);
          }
        }, 600);
      } else {
        const txt = await res.text();
        setErrorMsg(`Errore installazione (HTTP ${res.status}): ${txt.slice(0, 100)}`);
      }
    } catch (err) {
      setErrorMsg(`Errore di connessione: ${err.message}`);
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      gap: '18px',
      color: isLight ? '#374151' : '#a0aec0',
      textAlign: 'center',
      padding: '40px 24px',
      boxSizing: 'border-box'
    }}>
      {/* Icon Card */}
      <div style={{
        width: '84px',
        height: '84px',
        borderRadius: '22px',
        background: `linear-gradient(135deg, ${meta.color}22, ${meta.color}08)`,
        border: `1.5px solid ${meta.color}45`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '2.4rem',
        boxShadow: `0 0 24px ${meta.color}20`
      }}>
        {meta.icon}
      </div>

      {/* Title & Desc */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center', maxWidth: '440px' }}>
        <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: isLight ? '#111827' : '#f8fafc', letterSpacing: '-0.01em' }}>
          {meta.name}
        </h3>
        <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.5, color: isLight ? '#4b5563' : '#94a3b8' }}>
          {meta.desc}
        </p>
      </div>

      {/* Real-time Status / Error */}
      {installStatus && !errorMsg && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          borderRadius: '10px',
          background: 'rgba(0, 210, 255, 0.12)',
          border: '1px solid rgba(0, 210, 255, 0.35)',
          color: isLight ? '#0284c7' : '#00d2ff',
          fontSize: '0.78rem',
          fontWeight: 700
        }}>
          {installing ? <RefreshCw size={14} className="spin" /> : <CheckCircle2 size={14} color="#3fb950" />}
          <span>{installStatus}</span>
        </div>
      )}

      {errorMsg && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          borderRadius: '10px',
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          color: '#ef4444',
          fontSize: '0.78rem',
          fontWeight: 700,
          maxWidth: '460px'
        }}>
          <AlertCircle size={14} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '6px' }}>
        {/* Primary 1-Click Install Button */}
        <button
          onClick={handleQuickInstall}
          disabled={installing}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 22px',
            borderRadius: '12px',
            background: isLight 
              ? 'linear-gradient(135deg, #ea580c 0%, #c2410c 100%)' 
              : `linear-gradient(135deg, ${meta.color}, ${meta.color}bb)`,
            border: 'none',
            color: '#ffffff',
            fontWeight: 800,
            fontSize: '0.86rem',
            cursor: 'pointer',
            boxShadow: `0 4px 16px ${meta.color}35`,
            transition: 'all 0.2s ease',
            opacity: installing ? 0.75 : 1
          }}
        >
          {installing ? <RefreshCw size={15} className="spin" /> : <Download size={15} />}
          {installing ? 'Download in corso...' : '⚡ Scarica & Abilita Skill Ora'}
        </button>

        {/* Secondary Hub Button */}
        <button
          onClick={() => openTab && openTab({ name: '📦 Hub Skills & Estensioni' }, 'marketplace')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '10px 18px',
            borderRadius: '12px',
            background: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.12)',
            color: isLight ? '#374151' : '#cbd5e0',
            fontWeight: 700,
            fontSize: '0.82rem',
            cursor: 'pointer'
          }}
        >
          <Package size={14} />
          Sfoglia Catalogo Hub
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: isLight ? '#6b7280' : '#64748b', marginTop: '8px' }}>
        <Sparkles size={13} color={meta.color} />
        <span>Download streaming istantaneo da GitHub con registrazione automatica nel Kernel.</span>
      </div>
    </div>
  );
}
