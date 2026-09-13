import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Cpu, Brain, Code, ShieldCheck, CheckCircle, Palette, 
  Atom, FlaskConical, Award, Wand2, Wrench, MessageSquare, 
  Search, Filter, Play, Edit3, Image as ImageIcon, Copy, Check, 
  ExternalLink, Sparkles, Terminal, Layers, Plus, X, ArrowRight,
  Info, RefreshCw, ChevronRight, Sliders, Box, Download, Globe,
  Users, BookOpen, GraduationCap, Briefcase, HeartPulse, Scale, TrendingUp,
  Trash2, UserCheck, Star, Eye, ScrollText, Boxes, Upload
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import TabHeader from '../common/TabHeader';

// ==============================================================================
// Icon & Category Mapper for Roles & Professions
// ==============================================================================
const ROLE_CATEGORY_META = {
  'Architettura & Kernel': { icon: '🏛️', color: '#00d2ff', desc: 'Kernel, routing, amministrazione e coordinamento' },
  'Scienze, Ingegneria & Tech': { icon: '⚡', color: '#38bdf8', desc: 'Scienze esatte, ingegneria, fisica e calcolo' },
  'Sviluppo & Test': { icon: '💻', color: '#3fb950', desc: 'Sviluppo software, test suite, refactoring' },
  'Sviluppo & Codice': { icon: '💻', color: '#3fb950', desc: 'Programmazione, architettura web e algoritmi' },
  'Scienze & Medicina': { icon: '🧬', color: '#10b981', desc: 'Medicina, biologia, genetica e divulgazione clinica' },
  'Medicina & Salute': { icon: '🩺', color: '#10b981', desc: 'Sanità, protocolli clinici e benessere' },
  'Comunicazione & Creatività': { icon: '🎨', color: '#f43f5e', desc: 'Grafica, design visivo, scrittura e media' },
  'Creatività & Design': { icon: '🎨', color: '#f43f5e', desc: 'Design di interfacce, infografiche e creatività' },
  'Economia & Diritto': { icon: '⚖️', color: '#eab308', desc: 'Diritto, finanza quantitativa e contrattualistica' },
  'Finanza & Business': { icon: '📊', color: '#eab308', desc: 'Analisi mercati, business plan e contabilità' },
  'Studenti & Università': { icon: '🎓', color: '#a855f7', desc: 'Tutoraggio accademico, studio e preparazione esami' },
  'Assistente Generale': { icon: '🤖', color: '#00d2ff', desc: 'Front-desk cognitivo ed assistenza quotidiana' }
};

const getRoleCategoryMeta = (cat) => {
  if (!cat) return { icon: '🧠', color: '#00d2ff', desc: 'Ruolo cognitivo specializzato' };
  return ROLE_CATEGORY_META[cat] || { icon: '🧠', color: '#00d2ff', desc: cat };
};

// ==============================================================================
// Helper di risoluzione immagine avatar per ogni ruolo/profilo
// ==============================================================================
const getRoleImage = (role) => {
  if (!role) return '/images/default.png';
  if (role.image && role.image !== '/images/default.png') return role.image;
  
  const text = `${role.id || ''} ${role.filename || ''} ${role.name || ''} ${role.role || ''} ${role.category || ''}`.toLowerCase();
  
  if (text.includes('medic') || text.includes('clin') || text.includes('salut') || text.includes('biol') || text.includes('genet')) {
    return '/images/medico_ai.jpg';
  }
  if (text.includes('design') || text.includes('grafic') || text.includes('creativ') || text.includes('visual') || text.includes('art') || text.includes('ui/ux')) {
    return '/images/designer_ai.jpg';
  }
  if (text.includes('avvocat') || text.includes('leg') || text.includes('giur') || text.includes('finanz') || text.includes('quant') || text.includes('econom') || text.includes('mercati')) {
    return '/images/quant_law_ai.jpg';
  }
  if (text.includes('matemat') || text.includes('fisic') || text.includes('scienz') || text.includes('statist') || text.includes('quantum')) {
    return '/images/matematicoAi.png';
  }
  if (text.includes('programm') || text.includes('cod') || text.includes('svilupp') || text.includes('web') || text.includes('fullstack') || text.includes('software') || text.includes('dev')) {
    return '/images/programmatoreAi.png';
  }
  if (text.includes('arch') || text.includes('kernel') || text.includes('admin') || text.includes('sistem')) {
    return '/images/agente0.png';
  }
  if (text.includes('sigma') || text.includes('assistan')) {
    return '/images/sigma_logo_harmonic_flow.jpg';
  }
  return '/images/default.png';
};

// ==============================================================================
// Componente Scheda Dettaglio Ruolo (Modal) - Allineato allo stile delle Skills
// ==============================================================================
function RoleDetailModal({
  role,
  isInstalled,
  isLight,
  onClose,
  onLaunchChat,
  onEdit,
  onInspect,
  onUninstall,
  onInstallFromHub,
  onChangeAvatar,
  isInstalling,
  isUninstalling,
  extractSystemPrompt
}) {
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [showRawModelfile, setShowRawModelfile] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!role) return null;

  const domainColor = role.domainColor || (isLight ? '#ea580c' : '#00d2ff');
  const catMeta = getRoleCategoryMeta(role.category);
  const systemPrompt = extractSystemPrompt(role);

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(systemPrompt || '');
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2000);
  };

  return (
    <div className="marketplace-modal-overlay" onClick={onClose}>
      <div 
        className="marketplace-modal-box"
        style={{ maxWidth: '820px', border: `1px solid ${domainColor}40` }}
        onClick={e => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="marketplace-modal-header">
          <div className="marketplace-modal-title-row">
            {/* Avatar con badge per personalizzazione se installato */}
            <div
              onClick={() => isInstalled && onChangeAvatar && onChangeAvatar(role)}
              title={isInstalled ? "Clicca per cambiare avatar del ruolo" : role.name}
              style={{
                width: '68px',
                height: '68px',
                borderRadius: '16px',
                overflow: 'hidden',
                border: `2px solid ${domainColor}`,
                boxShadow: `0 0 16px ${domainColor}35`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: isLight ? '#f1f5f9' : '#0a0d14',
                flexShrink: 0,
                position: 'relative',
                cursor: isInstalled ? 'pointer' : 'default'
              }}
            >
              <img
                src={getRoleImage(role)}
                alt={role.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onError={e => { e.target.src = '/images/default.png'; }}
              />
              {isInstalled && (
                <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  background: 'rgba(0,0,0,0.68)',
                  textAlign: 'center',
                  fontSize: '0.52rem',
                  color: '#fff',
                  fontWeight: 800,
                  letterSpacing: '0.4px',
                  padding: '2px 0'
                }}>
                  AVATAR
                </div>
              )}
            </div>

            {/* Titoli e Badge */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: `${domainColor}18`,
                  border: `1px solid ${domainColor}40`,
                  color: domainColor,
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  textTransform: 'uppercase'
                }}>
                  <span>{catMeta.icon}</span>
                  <span>{role.category || 'Specializzazione'}</span>
                </span>

                {role.filename && (
                  <code style={{
                    fontSize: '0.68rem',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: isLight ? '#f1f5f9' : 'rgba(255,255,255,0.06)',
                    color: isLight ? '#475569' : '#94a3b8'
                  }}>
                    {role.filename}
                  </code>
                )}

                <span style={{
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: isInstalled ? 'rgba(63, 185, 80, 0.12)' : 'rgba(168, 85, 247, 0.12)',
                  border: `1px solid ${isInstalled ? 'rgba(63, 185, 80, 0.3)' : 'rgba(168, 85, 247, 0.3)'}`,
                  color: isInstalled ? '#3fb950' : '#c084fc',
                  fontSize: '0.65rem',
                  fontWeight: 700
                }}>
                  {isInstalled ? '✓ Attivo nel Kernel' : '🌐 Catalogo Community'}
                </span>
              </div>

              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc' }}>
                {role.name}
              </h3>
              <span style={{ fontSize: '0.80rem', color: domainColor, fontWeight: 700 }}>
                {role.role}
              </span>
            </div>
          </div>

          <button
            type="button"
            className="marketplace-modal-close-btn"
            onClick={onClose}
            title="Chiudi Scheda"
          >
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="marketplace-modal-body">
          {/* Primary Action Banner */}
          <div>
            {isInstalled ? (
              <button
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => { onLaunchChat(role); onClose(); }}
                style={{
                  width: '100%',
                  padding: '12px 20px',
                  fontSize: '0.90rem',
                  borderRadius: '12px',
                  justifyContent: 'center',
                  background: isLight
                    ? 'linear-gradient(135deg, #ea580c 0%, #f97316 100%)'
                    : `linear-gradient(135deg, ${domainColor} 0%, #7c5bf0 100%)`
                }}
              >
                <MessageSquare size={16} />
                <span>Avvia Chat con {role.name}</span>
                <ArrowRight size={14} />
              </button>
            ) : (
              <button
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => onInstallFromHub(role)}
                disabled={isInstalling}
                style={{
                  width: '100%',
                  padding: '12px 20px',
                  fontSize: '0.90rem',
                  borderRadius: '12px',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)'
                }}
              >
                {isInstalling ? <RefreshCw size={16} className="spin" /> : <Download size={16} />}
                <span>{isInstalling ? 'Scaricamento in corso...' : `Scarica & Attiva ${role.name} nel Kernel`}</span>
              </button>
            )}
          </div>

          {/* Parameters Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '10px'
          }}>
            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.06)'
            }}>
              <div style={{ fontSize: '0.64rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Cpu size={12} color="#00d2ff" /> Modello Base
              </div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc', marginTop: '3px' }}>
                {role.baseModel || 'sigma'}
              </div>
            </div>

            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.06)'
            }}>
              <div style={{ fontSize: '0.64rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Sliders size={12} color="#f59e0b" /> Temperatura
              </div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: domainColor, marginTop: '3px' }}>
                {role.temperature ?? 0.2}
              </div>
            </div>

            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.06)'
            }}>
              <div style={{ fontSize: '0.64rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Box size={12} color="#10b981" /> Finestra Contesto
              </div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: '#10b981', marginTop: '3px' }}>
                {role.numCtx ? `${Math.round(role.numCtx / 1024)}k tokens` : '32k tokens'}
              </div>
            </div>

            <div style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.03)',
              border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.06)'
            }}>
              <div style={{ fontSize: '0.64rem', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Sparkles size={12} color="#a855f7" /> Top-P / Penality
              </div>
              <div style={{ fontSize: '0.90rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc', marginTop: '3px' }}>
                {role.topP || 0.85} / 1.1
              </div>
            </div>
          </div>

          {/* Missione & Descrizione */}
          <div>
            <div className="marketplace-modal-section-title">
              <Sparkles size={14} /> Missione & Profilo Cognitivo
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', color: isLight ? '#334155' : '#cbd5e1', lineHeight: 1.6 }}>
              {role.description || 'Nessuna descrizione specificata per questo ruolo.'}
            </p>
            {role.target && (
              <div style={{
                marginTop: '10px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: isLight ? '#f1f5f9' : 'rgba(0, 210, 255, 0.08)',
                border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(0, 210, 255, 0.2)',
                color: isLight ? '#0284c7' : '#38bdf8',
                fontSize: '0.74rem',
                fontWeight: 700
              }}>
                <Users size={12} /> Target: {role.target}
              </div>
            )}
          </div>

          {/* Competenze Chiave */}
          {role.capabilities && role.capabilities.length > 0 && (
            <div>
              <div className="marketplace-modal-section-title">
                <Boxes size={14} /> Competenze & Artifacts Prodotti
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {role.capabilities.map((cap, idx) => (
                  <span
                    key={idx}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: isLight ? '#f1f5f9' : 'rgba(255, 255, 255, 0.04)',
                      border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.08)',
                      color: isLight ? '#0f172a' : '#f1f5f9',
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px'
                    }}
                  >
                    <span style={{ color: domainColor }}>✓</span>
                    <span>{cap}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* MCP Tools */}
          {role.mcpTools && role.mcpTools.length > 0 && (
            <div>
              <div className="marketplace-modal-section-title">
                <Wrench size={14} /> Strumenti MCP Associati
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {role.mcpTools.map((tool, idx) => (
                  <span
                    key={idx}
                    style={{
                      padding: '3px 8px',
                      borderRadius: '6px',
                      background: 'rgba(0, 210, 255, 0.08)',
                      border: '1px solid rgba(0, 210, 255, 0.25)',
                      color: '#00d2ff',
                      fontSize: '0.72rem',
                      fontWeight: 700
                    }}
                  >
                    {typeof tool === 'string' ? tool : tool.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Direttive di Sistema / System Prompt */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div className="marketplace-modal-section-title" style={{ margin: 0 }}>
                <ScrollText size={14} /> Direttive & Prompt di Sistema
              </div>
              <button
                type="button"
                onClick={handleCopyPrompt}
                style={{
                  background: 'none',
                  border: 'none',
                  color: isLight ? '#ea580c' : '#00d2ff',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                {copiedPrompt ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                <span>{copiedPrompt ? 'Copiato!' : 'Copia Prompt'}</span>
              </button>
            </div>

            <div style={{
              padding: '14px',
              borderRadius: '10px',
              background: isLight ? '#f1f5f9' : '#07090e',
              border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.08)',
              maxHeight: '180px',
              overflowY: 'auto',
              fontSize: '0.74rem',
              lineHeight: 1.55,
              color: isLight ? '#334155' : '#94a3b8',
              whiteSpace: 'pre-wrap',
              fontFamily: 'inherit'
            }}>
              {systemPrompt}
            </div>
          </div>

          {/* Toggle Raw Modelfile Box */}
          {(role.rawContent || role.content) && (
            <div>
              <button
                type="button"
                onClick={() => setShowRawModelfile(prev => !prev)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: 0
                }}
              >
                <Terminal size={12} />
                <span>{showRawModelfile ? 'Nascondi Modelfile Raw' : 'Mostra Modelfile Raw Markdown'}</span>
              </button>

              {showRawModelfile && (
                <pre style={{
                  marginTop: '8px',
                  background: isLight ? '#f8fafc' : '#05070a',
                  border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  padding: '12px',
                  fontFamily: 'monospace',
                  fontSize: '0.72rem',
                  color: isLight ? '#0f172a' : '#38bdf8',
                  lineHeight: 1.45,
                  maxHeight: '160px',
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap'
                }}>
                  {role.rawContent || role.content}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="marketplace-modal-footer">
          <button
            type="button"
            className="marketplace-action-btn"
            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#cbd5e1' }}
            onClick={onClose}
          >
            Chiudi Scheda
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {isInstalled && role.filename !== 'sigma_assistant.md' && role.id !== 'sigma_assistant' && onUninstall && (
              <button
                type="button"
                className="marketplace-action-btn danger"
                onClick={() => onUninstall(role)}
                disabled={isUninstalling}
                title="Disinstalla ruolo dal Kernel"
              >
                <Trash2 size={13} />
                <span>{isUninstalling ? 'Rimozione...' : 'Disinstalla'}</span>
              </button>
            )}

            {isInstalled && onEdit && (
              <button
                type="button"
                className="marketplace-action-btn"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#cbd5e1' }}
                onClick={() => { onEdit(role); onClose(); }}
                title="Modifica istruzioni nel SigmaLab Editor"
              >
                <Edit3 size={13} />
                <span>Modifica nel SigmaLab Editor</span>
              </button>
            )}

            <button
              type="button"
              className="marketplace-action-btn"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#cbd5e1' }}
              onClick={() => { onInspect(role); }}
              title="Ispeziona formato Modelfile completo"
            >
              <Terminal size={13} />
              <span>Modelfile</span>
            </button>

            {isInstalled && onLaunchChat && (
              <button
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => { onLaunchChat(role); onClose(); }}
              >
                <MessageSquare size={13} />
                <span>Apri Chat</span>
                <ArrowRight size={13} />
              </button>
            )}

            {!isInstalled && onInstallFromHub && (
              <button
                type="button"
                className="marketplace-action-btn primary"
                onClick={() => onInstallFromHub(role)}
                disabled={isInstalling}
              >
                {isInstalling ? <RefreshCw size={13} className="spin" /> : <Download size={13} />}
                <span>{isInstalling ? 'Installazione...' : 'Installa Ruolo'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Icon Mapper for Dynamic Role Icons
const ICON_MAP = {
  Cpu, Brain, Code, ShieldCheck, CheckCircle, Palette, 
  Atom, FlaskConical, Award, Wand2, Wrench, MessageSquare, 
  BookOpen, GraduationCap, Briefcase, HeartPulse, Scale, TrendingUp,
  Trash2, Users, Star
};

export default function ManifestiGallery({ 
  modules = [], 
  manifesti: initialManifesti = [], 
  openTab, 
  fetchManifesti: externalFetchManifesti 
}) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Main View Tab: 'installed' | 'hub'
  const [activeGalleryView, setActiveGalleryView] = useState(() => {
    try {
      return localStorage.getItem('sigma_manifesti_active_subtab') || 'installed';
    } catch {
      return 'installed';
    }
  });

  useEffect(() => {
    const handleSetTab = (e) => {
      if (e?.detail) setActiveGalleryView(e.detail);
    };
    window.addEventListener('sigma-manifesti-set-tab', handleSetTab);
    return () => window.removeEventListener('sigma-manifesti-set-tab', handleSetTab);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('sigma_manifesti_active_subtab', activeGalleryView);
    } catch {}
    window.dispatchEvent(new CustomEvent('sigma-manifesti-tab-changed', { detail: activeGalleryView }));
  }, [activeGalleryView]);

  // Installed Roles State
  const [manifestiList, setManifestiList] = useState(initialManifesti);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('Tutti');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Selected Role for the Full Detail Modal (Skills Marketplace UX)
  const [selectedRoleModal, setSelectedRoleModal] = useState(null);

  // Professions Hub State
  const [hubCatalog, setHubCatalog] = useState([]);
  const [loadingHub, setLoadingHub] = useState(false);
  const [hubCategory, setHubCategory] = useState('Tutti');
  const [hubSearchQuery, setHubSearchQuery] = useState('');
  const [installingId, setInstallingId] = useState(null);
  const [uninstallingId, setUninstallingId] = useState(null);
  const [hubMessage, setHubMessage] = useState(null);

  // Custom Git / URL Import
  const [customImportUrl, setCustomImportUrl] = useState('');
  const [customImportName, setCustomImportName] = useState('');
  const [importingCustom, setImportingCustom] = useState(false);

  // Modals state
  const [inspectManifesto, setInspectManifesto] = useState(null);
  const [editingAvatarManifesto, setEditingAvatarManifesto] = useState(null);
  const [newManifestoModalOpen, setNewManifestoModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  // New Role Form State
  const [newFileName, setNewFileName] = useState('');
  const [newRole, setNewRole] = useState('');
  const [newCategory, setNewCategory] = useState('Sviluppo & Codice');
  const [newBaseModel, setNewBaseModel] = useState('sigma');
  const [newTemp, setNewTemp] = useState('0.2');
  const [newCtx, setNewCtx] = useState('32768');
  const [newPrompt, setNewPrompt] = useState('');
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState('');

  // Fetch installed roles with full dynamic parsing from backend
  const loadManifesti = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      if (data.success && Array.isArray(data.manifesti)) {
        setManifestiList(data.manifesti);
        if (selectedRoleModal) {
          const matched = data.manifesti.find(m => (m.id && m.id === selectedRoleModal.id) || (m.path && m.path === selectedRoleModal.path));
          if (matched) setSelectedRoleModal(matched);
        }
      }
    } catch (e) {
      console.error('Failed to load roles:', e);
    } finally {
      setLoading(false);
    }
  };

  // Fetch remote Professions Hub catalog
  const loadHubCatalog = async () => {
    setLoadingHub(true);
    try {
      const res = await fetch('/api/manifesti/hub');
      const data = await res.json();
      if (data.success && Array.isArray(data.catalog)) {
        setHubCatalog(data.catalog);
      }
    } catch (e) {
      console.error('Failed to load professions hub:', e);
    } finally {
      setLoadingHub(false);
    }
  };

  useEffect(() => {
    loadManifesti();
    loadHubCatalog();
  }, []);

  // Compute Categories from installed data
  const categories = useMemo(() => {
    const set = new Set();
    manifestiList.forEach(m => {
      if (m.category) set.add(m.category);
    });
    return ['Tutti', ...Array.from(set)];
  }, [manifestiList]);

  // Compute Categories from Hub data
  const hubCategories = useMemo(() => {
    const set = new Set();
    hubCatalog.forEach(m => {
      if (m.category) set.add(m.category);
    });
    return ['Tutti', ...Array.from(set)];
  }, [hubCatalog]);

  // Filtered installed roles
  const filteredManifesti = useMemo(() => {
    return manifestiList.filter(m => {
      const matchesCat = selectedCategory === 'Tutti' || m.category === selectedCategory;
      const q = searchQuery.toLowerCase();
      const matchesSearch = !q || 
        (m.name && m.name.toLowerCase().includes(q)) ||
        (m.role && m.role.toLowerCase().includes(q)) ||
        (m.description && m.description.toLowerCase().includes(q)) ||
        (m.baseModel && m.baseModel.toLowerCase().includes(q)) ||
        (m.capabilities && m.capabilities.some(c => c.toLowerCase().includes(q)));
      return matchesCat && matchesSearch;
    });
  }, [manifestiList, selectedCategory, searchQuery]);

  // Filtered hub roles
  const filteredHubCatalog = useMemo(() => {
    return hubCatalog.filter(m => {
      const matchesCat = hubCategory === 'Tutti' || m.category === hubCategory;
      const q = hubSearchQuery.toLowerCase();
      const matchesSearch = !q || 
        (m.name && m.name.toLowerCase().includes(q)) ||
        (m.role && m.role.toLowerCase().includes(q)) ||
        (m.target && m.target.toLowerCase().includes(q)) ||
        (m.description && m.description.toLowerCase().includes(q)) ||
        (m.capabilities && m.capabilities.some(c => c.toLowerCase().includes(q)));
      return matchesCat && matchesSearch;
    });
  }, [hubCatalog, hubCategory, hubSearchQuery]);

  // Copy Modelfile text helper
  const handleCopyModelfile = (text) => {
    navigator.clipboard.writeText(text || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Copy System Prompt
  const handleCopyPrompt = (promptText) => {
    navigator.clipboard.writeText(promptText || '');
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2000);
  };

  // Launch Chat with specific role preloaded
  const handleLaunchChat = (manifesto) => {
    if (!manifesto) return;
    const agentId = manifesto.filename ? manifesto.filename.replace('.md', '') : manifesto.id;
    const manifestoPath = manifesto.path ? manifesto.path.replace('manifesti/', 'Ruoli/') : `Ruoli/${manifesto.filename}`;
    
    try {
      localStorage.setItem('sigma_preload_agent', agentId);
      localStorage.setItem('sigma_selected_manifesto', JSON.stringify({
        name: manifesto.name,
        path: manifestoPath,
        exists: true,
        image: manifesto.image || '/images/default.png',
        role: manifesto.role,
        temperature: manifesto.temperature
      }));
    } catch (e) {}

    if (openTab) {
      openTab({ 
        name: `Chat: ${manifesto.name}`, 
        agent: agentId,
        manifestoPath: manifestoPath
      }, 'chat');
    }
  };

  // Open in SigmaLab Editor
  const handleEditManifesto = (manifesto) => {
    if (openTab && manifesto) {
      openTab({ 
        path: manifesto.path ? manifesto.path.replace('manifesti/', 'Ruoli/') : `Ruoli/${manifesto.filename}`, 
        filename: manifesto.filename || `${manifesto.id}.md` 
      }, 'editor');
    }
  };

  // Install a profession role from the Hub
  const handleInstallFromHub = async (hubItem) => {
    setInstallingId(hubItem.id);
    setHubMessage(null);
    try {
      const res = await fetch('/api/manifesti/install_from_hub', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manifesto_id: hubItem.id })
      });
      const data = await res.json();
      if (data.success) {
        setHubMessage({ type: 'success', text: data.message });
        await loadManifesti();
        await loadHubCatalog();
        if (externalFetchManifesti) externalFetchManifesti();
      } else {
        setHubMessage({ type: 'error', text: data.error || 'Errore installazione' });
      }
    } catch (e) {
      setHubMessage({ type: 'error', text: 'Errore di connessione' });
    } finally {
      setInstallingId(null);
    }
  };

  // Uninstall/delete an agent role from the Kernel
  const handleUninstallManifesto = async (manifesto) => {
    const filename = manifesto.filename || (manifesto.path ? manifesto.path.split('/').pop() : `${manifesto.id}.md`);
    if (filename === 'sigma_assistant.md' || manifesto.id === 'sigma_assistant') {
      setHubMessage({ type: 'error', text: 'Sigma Assistant è l\'assistente predefinito del sistema e non può essere rimosso.' });
      return;
    }
    if (!window.confirm(`Sei sicuro di voler disinstallare il ruolo '${manifesto.name || filename}' dal Kernel?`)) {
      return;
    }
    setUninstallingId(manifesto.id || filename);
    setHubMessage(null);
    try {
      const res = await fetch('/api/manifesti/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename })
      });
      const data = await res.json();
      if (data.success) {
        setHubMessage({ type: 'success', text: data.message });
        await loadManifesti();
        await loadHubCatalog();
        if (selectedRoleModal && (selectedRoleModal.filename === filename || selectedRoleModal.id === manifesto.id)) {
          setSelectedRoleModal(null);
        }
        if (externalFetchManifesti) externalFetchManifesti();
      } else {
        setHubMessage({ type: 'error', text: data.error || 'Errore durante la disinstallazione' });
      }
    } catch (e) {
      setHubMessage({ type: 'error', text: 'Errore di connessione' });
    } finally {
      setUninstallingId(null);
    }
  };

  // Import from custom URL
  const handleCustomImport = async () => {
    if (!customImportUrl.trim()) return;
    setImportingCustom(true);
    setHubMessage(null);
    try {
      const res = await fetch('/api/manifesti/install_from_hub', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: customImportUrl.trim(),
          name: customImportName.trim()
        })
      });
      const data = await res.json();
      if (data.success) {
        setHubMessage({ type: 'success', text: data.message });
        setCustomImportUrl('');
        setCustomImportName('');
        await loadManifesti();
        await loadHubCatalog();
        if (externalFetchManifesti) externalFetchManifesti();
      } else {
        setHubMessage({ type: 'error', text: data.error || 'Errore importazione' });
      }
    } catch (e) {
      setHubMessage({ type: 'error', text: 'Errore di connessione' });
    } finally {
      setImportingCustom(false);
    }
  };

  // Create new custom role
  const handleCreateManifesto = async () => {
    if (!newFileName.trim()) {
      setFormError('Il nome del file è obbligatorio (es. quantum_physicist.md)');
      return;
    }
    setCreating(true);
    setFormError('');

    let finalFileName = newFileName.trim();
    if (!finalFileName.endsWith('.md')) finalFileName += '.md';

    const modelfileContent = `FROM ${newBaseModel}

# --- METADATA & DOMAIN SPECIFICATION ---
# Role: ${newRole || 'Agente Specializzato'}
# Category: ${newCategory}
# DomainColor: #00d2ff
# Icon: Cpu
# Capabilities: Ricerca, Elaborazione, Documentazione
# OutputArtifacts: Documenti Markdown, Script Python
# McpTools: Memory MCP, Inference MCP

PARAMETER temperature ${newTemp}
PARAMETER top_p 0.85
PARAMETER top_k 30
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx ${newCtx}
PARAMETER num_predict 16384

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"

TEMPLATE """<|im_start|>system
{{ .System }}
<|im_end|>
<|im_start|>user
{{ .Prompt }}
<|im_end|>
<|im_start|>assistant
"""

SYSTEM """
Sei ${newRole || 'un Agente Specializzato'} di Sigma AI Studio.

## 🎯 IDENTITÀ E OBIETTIVO OPERATIVO
${newPrompt || 'Definisci qui la missione e gli obiettivi specifici del modello.'}

## 📂 PROTOCOLLO FILE E WORKSPACE SANDBOX
1. Accesso e scrittura tassativamente confinati nella cartella \`./data/\`.

## 👑 RICONOSCIMENTO
Creato per l'ecosistema sovrano Sigma AI Studio.
"""
`;

    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: `Ruoli/${finalFileName}`,
          content: modelfileContent
        })
      });
      const d = await res.json();
      if (d.success) {
        setNewManifestoModalOpen(false);
        setNewFileName('');
        setNewRole('');
        setNewPrompt('');
        await loadManifesti();
      } else {
        setFormError(d.error || 'Errore durante la creazione');
      }
    } catch (e) {
      setFormError('Errore di rete');
    } finally {
      setCreating(false);
    }
  };

  // Avatar presets
  const AVATAR_PRESETS = [
    { label: 'Architect (Agente 0)', path: '/images/agente0.png' },
    { label: 'Programmatore AI', path: '/images/programmatoreAi.png' },
    { label: 'Matematico AI', path: '/images/matematicoAi.png' },
    { label: 'Scienze Mediche AI', path: '/images/medico_ai.jpg' },
    { label: 'Visual Designer AI', path: '/images/designer_ai.jpg' },
    { label: 'Quant & Legale AI', path: '/images/quant_law_ai.jpg' },
    { label: 'Sigma Harmonic', path: '/images/sigma_logo_harmonic_flow.jpg' },
    { label: 'Default Avatar', path: '/images/default.png' }
  ];

  const fileInputRef = useRef(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  const handleUploadCustomAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !editingAvatarManifesto) return;
    setUploadingAvatar(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('path', editingAvatarManifesto.path || `Ruoli/${editingAvatarManifesto.filename || editingAvatarManifesto.id + '.md'}`);
      const res = await fetch('/api/agents/upload_image', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success && data.image) {
        await handleUpdateAvatar(editingAvatarManifesto, data.image);
      } else {
        alert(data.error || 'Errore durante il caricamento immagine');
      }
    } catch (err) {
      console.error(err);
      alert('Errore durante il caricamento del file');
    } finally {
      setUploadingAvatar(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleUpdateAvatar = async (manifesto, imagePath) => {
    try {
      await fetch('/api/manifesti/update_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: manifesto.path,
          image: imagePath
        })
      });
      setEditingAvatarManifesto(null);
      await loadManifesti();
      if (selectedRoleModal && (selectedRoleModal.path === manifesto.path || selectedRoleModal.id === manifesto.id)) {
        setSelectedRoleModal(prev => prev ? ({ ...prev, image: imagePath }) : null);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const accentColor = isLight ? '#ea580c' : '#00d2ff';
  const cardBg = isLight ? '#ffffff' : '#111522';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 16px rgba(180, 150, 100, 0.12)' : '0 4px 24px rgba(0,0,0,0.35)';
  const textPrimary = isLight ? '#0f172a' : '#ffffff';
  const textSecondary = isLight ? '#475569' : '#94a3b8';
  const textMuted = isLight ? '#64748b' : '#64748b';
  const innerCardBg = isLight ? '#f8fafc' : 'rgba(255, 255, 255, 0.04)';
  const innerCardBorder = isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255, 255, 255, 0.08)';

  // Extract clean system prompt from raw content if available
  const extractSystemPrompt = (manifesto) => {
    if (!manifesto) return '';
    const raw = manifesto.rawContent || manifesto.content || '';
    const systemMatch = raw.match(/SYSTEM\s+"""([\s\S]*?)"""/);
    if (systemMatch && systemMatch[1]) {
      return systemMatch[1].trim();
    }
    return manifesto.description || 'Nessuna direttiva di sistema esplicita.';
  };

  return (
    <div className="manifesti-gallery-root" style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: isLight ? '#f8fafc' : 'var(--bg-main, #090c14)',
      color: textPrimary,
      overflow: 'hidden'
    }}>
      {/* ── UNIFIED KERNEL TAB HEADER — Stile Compatto Bacheca & Chat ──────── */}
      <TabHeader
        icon={activeGalleryView === 'installed' ? Brain : Globe}
        title="Ruoli AI"
        tabs={[
          { id: 'installed', label: `Ruoli Kernel (${manifestiList.length})`, icon: Brain, active: activeGalleryView === 'installed', onClick: () => setActiveGalleryView('installed') },
          { id: 'hub', label: 'Hub Community', icon: Globe, active: activeGalleryView === 'hub', onClick: () => setActiveGalleryView('hub') }
        ]}
        description={
          activeGalleryView === 'installed'
            ? "Profili cognitivi specialistici e direttive applicate a SigmaEngine."
            : "Esplora, importa e sincronizza ruoli AI specializzati dalla community GitHub."
        }
        actions={
          <>
            <button
              onClick={() => setNewManifestoModalOpen(true)}
              className="sigma-tab-btn sigma-tab-btn-primary"
            >
              <Plus size={12} /> <span>Nuovo Ruolo</span>
            </button>

            <button
              onClick={() => { loadManifesti(); loadHubCatalog(); }}
              title="Ricarica Ruoli dal Kernel e da GitHub"
              className="sigma-tab-btn sigma-tab-btn-ghost"
            >
              <RefreshCw size={12} className={(loading || loadingHub) ? 'spin' : ''} />
              <span>Ricarica</span>
            </button>
          </>
        }
      />

      {/* ── CORPO PRINCIPALE IN DUAL-PANE LAYOUT ──────── */}
      <div style={{ padding: '20px 24px', width: '100%', boxSizing: 'border-box', flex: 1, overflowY: 'auto' }}>
        
        {/* Toast / Notification Banner */}
        {hubMessage && (
          <div style={{
            padding: '10px 16px',
            borderRadius: '10px',
            background: hubMessage.type === 'success' ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 80, 100, 0.15)',
            border: `1px solid ${hubMessage.type === 'success' ? '#3fb950' : '#ff5064'}`,
            color: hubMessage.type === 'success' ? (isLight ? '#15803d' : '#4ade80') : (isLight ? '#991b1b' : '#f87171'),
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            fontWeight: 700
          }}>
            <span>{hubMessage.text}</span>
            <button onClick={() => setHubMessage(null)} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}><X size={14} /></button>
          </div>
        )}

        {/* =================================================================== */}
        {/* GRIGLIA RUOLI FULL-WIDTH — STILE CATALOGO SKILLS                   */}
        {/* =================================================================== */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%' }}>
          
          {/* VIEW 1: RUOLI INSTALLATI NEL KERNEL */}
          {activeGalleryView === 'installed' && (
            <>
              {/* Filter & Search Bar */}
              <div className="marketplace-filter-bar">
                <div className="marketplace-search-wrapper">
                  <Search size={14} className="marketplace-search-icon" />
                  <input
                    type="text"
                    className="marketplace-search-input"
                    placeholder="Cerca ruolo per nome, modello base o competenze..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: '#94a3b8',
                        cursor: 'pointer',
                        padding: 0
                      }}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>

                {/* Category Chips with Icons */}
                <div className="marketplace-categories">
                  <button
                    type="button"
                    className={`marketplace-cat-chip ${selectedCategory === 'Tutti' ? 'active' : ''}`}
                    onClick={() => setSelectedCategory('Tutti')}
                  >
                    <span>✨</span>
                    <span>Tutti i Ruoli ({manifestiList.length})</span>
                  </button>
                  {categories.filter(c => c !== 'Tutti').map(cat => {
                    const meta = getRoleCategoryMeta(cat);
                    const active = selectedCategory === cat;
                    return (
                      <button
                        key={cat}
                        type="button"
                        className={`marketplace-cat-chip ${active ? 'active' : ''}`}
                        onClick={() => setSelectedCategory(cat)}
                        title={meta.desc || cat}
                      >
                        <span>{meta.icon}</span>
                        <span>{cat}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Role Cards Grid */}
              {filteredManifesti.length === 0 ? (
                <div style={{
                  padding: '48px 24px',
                  borderRadius: '16px',
                  background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.02)',
                  border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.08)',
                  textAlign: 'center',
                  color: '#94a3b8',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  <Brain size={36} style={{ opacity: 0.5, color: '#00d2ff' }} />
                  <div style={{ fontSize: '1rem', fontWeight: 800, color: textPrimary }}>
                    Nessun ruolo trovato con i criteri di ricerca
                  </div>
                  <div style={{ fontSize: '0.78rem' }}>
                    Prova a modificare il testo di ricerca o seleziona "Tutti i Ruoli".
                  </div>
                </div>
              ) : (
                <div className="marketplace-grid">
                  {filteredManifesti.map(manifesto => {
                    const domainColor = manifesto.domainColor || (isLight ? '#ea580c' : '#00d2ff');
                    const catMeta = getRoleCategoryMeta(manifesto.category);

                    return (
                      <div
                        key={manifesto.path || manifesto.id}
                        className="marketplace-card"
                        onClick={() => setSelectedRoleModal(manifesto)}
                      >
                        <div className="marketplace-card-glow" style={{ background: `linear-gradient(90deg, ${domainColor}, transparent)` }} />

                        {/* Card Header: Avatar (60px) + Titles */}
                        <div className="marketplace-card-header">
                          <div className="marketplace-card-title-area">
                            <div 
                              onClick={(e) => { e.stopPropagation(); setEditingAvatarManifesto(manifesto); }}
                              title="Clicca per cambiare avatar del ruolo"
                              style={{
                                width: '56px',
                                height: '56px',
                                borderRadius: '14px',
                                overflow: 'hidden',
                                border: `2px solid ${domainColor}`,
                                boxShadow: `0 0 14px ${domainColor}35`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: isLight ? '#f1f5f9' : '#0a0d14',
                                flexShrink: 0,
                                cursor: 'pointer',
                                transition: 'transform 0.15s ease'
                              }}
                            >
                              <img 
                                src={getRoleImage(manifesto)} 
                                alt={manifesto.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                onError={e => { e.target.src = '/images/default.png'; }}
                              />
                            </div>

                            <div className="marketplace-card-titles">
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                  padding: '1px 6px',
                                  borderRadius: '5px',
                                  background: `${domainColor}18`,
                                  border: `1px solid ${domainColor}40`,
                                  color: domainColor,
                                  fontSize: '0.62rem',
                                  fontWeight: 800,
                                  textTransform: 'uppercase'
                                }}>
                                  <span>{catMeta.icon}</span>
                                  <span>{manifesto.category}</span>
                                </span>
                              </div>

                              <h4 className="marketplace-card-name" style={{ marginTop: '2px' }}>
                                {manifesto.name}
                              </h4>
                              <span style={{ fontSize: '0.74rem', color: domainColor, fontWeight: 700, lineHeight: 1.3 }}>
                                {manifesto.role}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Description Excerpt */}
                        <p className="marketplace-card-desc" style={{
                          margin: 0,
                          fontSize: '0.75rem',
                          color: textSecondary,
                          lineHeight: 1.45,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden'
                        }}>
                          {manifesto.description || 'Nessuna descrizione disponibile.'}
                        </p>

                        {/* Parameter Badges Row */}
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            padding: '2px 7px', borderRadius: '5px',
                            background: innerCardBg, border: innerCardBorder,
                            color: textPrimary, fontSize: '0.64rem', fontWeight: 700
                          }}>
                            <Cpu size={10} style={{ color: isLight ? '#0284c7' : '#00d2ff' }} /> {manifesto.baseModel || 'sigma'}
                          </span>

                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            padding: '2px 7px', borderRadius: '5px',
                            background: innerCardBg, border: innerCardBorder,
                            color: textPrimary, fontSize: '0.64rem', fontWeight: 700
                          }}>
                            <Sliders size={10} style={{ color: isLight ? '#7c3aed' : '#bc8cff' }} /> {manifesto.temperature ?? 0.2}
                          </span>

                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            padding: '2px 7px', borderRadius: '5px',
                            background: innerCardBg, border: innerCardBorder,
                            color: textPrimary, fontSize: '0.64rem', fontWeight: 700
                          }}>
                            <Box size={10} style={{ color: isLight ? '#16a34a' : '#3fb950' }} /> {manifesto.numCtx ? `${Math.round(manifesto.numCtx / 1024)}k` : '32k'}
                          </span>
                        </div>

                        {/* Card Action Buttons */}
                        <div className="marketplace-card-footer" style={{ marginTop: 'auto', paddingTop: '10px' }}>
                          <button
                            type="button"
                            className="marketplace-action-btn"
                            onClick={(e) => { e.stopPropagation(); setSelectedRoleModal(manifesto); }}
                            style={{
                              padding: '5px 10px',
                              fontSize: '0.72rem',
                              fontWeight: 700
                            }}
                            title="Visualizza scheda tecnica completa del ruolo"
                          >
                            <Eye size={12} color={domainColor} />
                            <span>Dettagli</span>
                          </button>

                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <button
                              type="button"
                              className="marketplace-action-btn"
                              onClick={(e) => { e.stopPropagation(); handleEditManifesto(manifesto); }}
                              style={{ padding: '5px 8px' }}
                              title="Modifica istruzioni nel SigmaLab Editor"
                            >
                              <Edit3 size={11} />
                            </button>

                            <button
                              type="button"
                              className="marketplace-action-btn primary"
                              onClick={(e) => { e.stopPropagation(); handleLaunchChat(manifesto); }}
                              style={{
                                padding: '5px 12px',
                                fontSize: '0.74rem',
                                fontWeight: 800,
                                background: isLight 
                                  ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                                  : `linear-gradient(135deg, ${domainColor} 0%, #7c5bf0 100%)`
                              }}
                            >
                              <MessageSquare size={12} />
                              <span>Chat</span>
                              <ArrowRight size={10} />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* VIEW 2: HUB PROFESSIONI (GITHUB REPOSITORY) */}
          {activeGalleryView === 'hub' && (
            <>
              {/* Custom Git Raw URL Importer */}
              <div style={{
                borderRadius: '14px',
                background: isLight ? '#ffffff' : 'rgba(168, 85, 247, 0.05)',
                border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(168, 85, 247, 0.2)',
                boxShadow: cardShadow,
                padding: '14px 18px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
                  <div>
                    <h2 style={{ fontSize: '0.96rem', fontWeight: 800, margin: '0 0 2px 0', color: textPrimary }}>
                      🌐 Repository GitHub Ruoli Specialistici
                    </h2>
                    <p style={{ fontSize: '0.74rem', color: textSecondary, margin: 0 }}>
                      Pacchetti di ruoli e istruzioni specialistiche per studenti, ricercatori e professionisti.
                    </p>
                  </div>

                  <a
                    href="https://github.com/Sigmanih/SigmaStudio-Manifesti"
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '5px 10px',
                      borderRadius: '6px',
                      background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(255,255,255,0.06)',
                      border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(255,255,255,0.15)',
                      color: isLight ? '#c2410c' : '#bc8cff',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      textDecoration: 'none'
                    }}
                  >
                    <ExternalLink size={12} /> Repository Ufficiale
                  </a>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <input
                    type="text"
                    placeholder="URL Raw GitHub (.md)..."
                    value={customImportUrl}
                    onChange={e => setCustomImportUrl(e.target.value)}
                    style={{
                      flex: 2, minWidth: '180px', padding: '6px 10px', borderRadius: '6px',
                      background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.05)',
                      border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.15)',
                      color: textPrimary, fontSize: '0.76rem'
                    }}
                  />
                  <input
                    type="text"
                    placeholder="Nome file..."
                    value={customImportName}
                    onChange={e => setCustomImportName(e.target.value)}
                    style={{
                      flex: 1, minWidth: '110px', padding: '6px 10px', borderRadius: '6px',
                      background: isLight ? '#f8fafc' : 'rgba(255,255,255,0.05)',
                      border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.15)',
                      color: textPrimary, fontSize: '0.76rem'
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleCustomImport}
                    disabled={importingCustom || !customImportUrl.trim()}
                    style={{
                      padding: '6px 14px', borderRadius: '6px',
                      background: isLight ? '#ea580c' : '#a855f7',
                      border: 'none', color: '#fff', fontWeight: 800, fontSize: '0.76rem',
                      cursor: (importingCustom || !customImportUrl.trim()) ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {importingCustom ? 'Import...' : '📥 Importa'}
                  </button>
                </div>
              </div>

              {/* Hub Filters & Search */}
              <div className="marketplace-filter-bar">
                <div className="marketplace-search-wrapper">
                  <Search size={14} className="marketplace-search-icon" />
                  <input
                    type="text"
                    className="marketplace-search-input"
                    placeholder="Cerca professione, ruolo o target..."
                    value={hubSearchQuery}
                    onChange={e => setHubSearchQuery(e.target.value)}
                  />
                  {hubSearchQuery && (
                    <button
                      type="button"
                      onClick={() => setHubSearchQuery('')}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: '#94a3b8',
                        cursor: 'pointer',
                        padding: 0
                      }}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>

                <div className="marketplace-categories">
                  <button
                    type="button"
                    className={`marketplace-cat-chip ${hubCategory === 'Tutti' ? 'active' : ''}`}
                    onClick={() => setHubCategory('Tutti')}
                  >
                    <span>✨</span>
                    <span>Tutte le Professioni ({hubCatalog.length})</span>
                  </button>
                  {hubCategories.filter(c => c !== 'Tutti').map(cat => {
                    const meta = getRoleCategoryMeta(cat);
                    const active = hubCategory === cat;
                    return (
                      <button
                        key={cat}
                        type="button"
                        className={`marketplace-cat-chip ${active ? 'active' : ''}`}
                        onClick={() => setHubCategory(cat)}
                        title={meta.desc || cat}
                      >
                        <span>{meta.icon}</span>
                        <span>{cat}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Hub Cards Grid */}
              {filteredHubCatalog.length === 0 ? (
                <div style={{
                  padding: '48px 24px',
                  borderRadius: '16px',
                  background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.02)',
                  border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.08)',
                  textAlign: 'center',
                  color: '#94a3b8',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  <Globe size={36} style={{ opacity: 0.5, color: '#a855f7' }} />
                  <div style={{ fontSize: '1rem', fontWeight: 800, color: textPrimary }}>
                    Nessuna professione corrisponde alla ricerca
                  </div>
                  <div style={{ fontSize: '0.78rem' }}>
                    Prova a reimpostare i filtri o visualizza tutte le categorie.
                  </div>
                </div>
              ) : (
                <div className="marketplace-grid">
                  {filteredHubCatalog.map(item => {
                    const domainColor = item.domainColor || (isLight ? '#7c3aed' : '#a855f7');
                    const catMeta = getRoleCategoryMeta(item.category);
                    const isInstalling = installingId === item.id;

                    return (
                      <div
                        key={item.id}
                        className="marketplace-card"
                        onClick={() => setSelectedRoleModal(item)}
                      >
                        <div className="marketplace-card-glow" style={{ background: `linear-gradient(90deg, ${domainColor}, transparent)` }} />

                        <div className="marketplace-card-header">
                          <div className="marketplace-card-title-area">
                            <div 
                              style={{
                                width: '56px',
                                height: '56px',
                                borderRadius: '14px',
                                overflow: 'hidden',
                                border: `2px solid ${domainColor}`,
                                boxShadow: `0 0 14px ${domainColor}35`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: isLight ? '#f1f5f9' : '#0a0d14',
                                flexShrink: 0
                              }}
                            >
                              <img 
                                src={getRoleImage(item)} 
                                alt={item.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                onError={e => { e.target.src = '/images/default.png'; }}
                              />
                            </div>

                            <div className="marketplace-card-titles">
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                                <span style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                  padding: '1px 6px',
                                  borderRadius: '5px',
                                  background: `${domainColor}18`,
                                  border: `1px solid ${domainColor}40`,
                                  color: domainColor,
                                  fontSize: '0.62rem',
                                  fontWeight: 800,
                                  textTransform: 'uppercase'
                                }}>
                                  <span>{catMeta.icon}</span>
                                  <span>{item.category}</span>
                                </span>
                              </div>

                              <h4 className="marketplace-card-name" style={{ marginTop: '3px' }}>
                                {item.name}
                              </h4>
                              <span style={{ fontSize: '0.74rem', color: domainColor, fontWeight: 700 }}>
                                {item.role}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div style={{
                          display: 'inline-flex', alignItems: 'center', gap: '4px',
                          padding: '2px 7px', borderRadius: '5px',
                          background: innerCardBg, border: innerCardBorder,
                          color: textPrimary, fontSize: '0.66rem', fontWeight: 700
                        }}>
                          <Users size={11} style={{ color: domainColor }} /> Target: {item.target}
                        </div>

                        <p className="marketplace-card-desc" style={{
                          margin: 0,
                          fontSize: '0.74rem',
                          color: textSecondary,
                          lineHeight: 1.45,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden'
                        }}>
                          {item.description}
                        </p>

                        <div className="marketplace-card-footer" style={{ marginTop: 'auto', paddingTop: '10px' }}>
                          <button
                            type="button"
                            className="marketplace-action-btn"
                            onClick={(e) => { e.stopPropagation(); setSelectedRoleModal(item); }}
                            style={{ padding: '5px 10px', fontSize: '0.72rem', fontWeight: 700 }}
                            title="Visualizza scheda tecnica completa della professione"
                          >
                            <Eye size={12} />
                            <span>Dettagli</span>
                          </button>

                          {item.installed ? (
                            <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <Check size={12} /> Già Installato
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="marketplace-action-btn primary"
                              onClick={(e) => { e.stopPropagation(); handleInstallFromHub(item); }}
                              disabled={isInstalling}
                              style={{
                                padding: '5px 12px',
                                fontSize: '0.74rem',
                                fontWeight: 800,
                                background: 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)'
                              }}
                            >
                              {isInstalling ? <RefreshCw size={12} className="spin" /> : <Download size={12} />}
                              <span>{isInstalling ? 'Scaricamento...' : 'Scarica & Attiva'}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

        </div>

      </div>

      {/* ===================================================================== */}
      {/* MODALE ISPEZIONE RUOLO & MODELFILE */}
      {/* ===================================================================== */}
      {inspectManifesto && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: isLight ? '#ffffff' : '#0d1117',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '850px',
            width: '100%',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: isLight ? '0 16px 48px rgba(0,0,0,0.25)' : '0 16px 48px rgba(0,0,0,0.7)',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '20px 24px',
              borderBottom: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  border: `2px solid ${inspectManifesto.domainColor || (isLight ? '#ea580c' : '#00d2ff')}`
                }}>
                  <img src={getRoleImage(inspectManifesto)} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: textPrimary }}>
                    {inspectManifesto.name}
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: isLight ? '#ea580c' : (inspectManifesto.domainColor || '#00d2ff'), fontWeight: 700 }}>
                    {inspectManifesto.role} • <code style={{ color: textPrimary }}>{inspectManifesto.filename || `${inspectManifesto.id}.md`}</code>
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  onClick={() => handleCopyModelfile(inspectManifesto.rawContent || inspectManifesto.content)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: copied 
                      ? (isLight ? 'rgba(34, 197, 94, 0.18)' : 'rgba(63, 185, 80, 0.2)') 
                      : (isLight ? '#f1f5f9' : 'rgba(255,255,255,0.08)'),
                    border: copied ? '1px solid #16a34a' : (isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.15)'),
                    color: copied ? '#15803d' : textPrimary,
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  <span>{copied ? 'Copiato!' : 'Copia Modelfile'}</span>
                </button>

                <button
                  onClick={() => setInspectManifesto(null)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: textPrimary,
                    cursor: 'pointer',
                    padding: '6px'
                  }}
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
              
              {/* Parameter Table */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '12px',
                marginBottom: '20px'
              }}>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Modello Base</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: textPrimary, marginTop: '2px' }}>{inspectManifesto.baseModel || 'sigma'}</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Temperatura</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isLight ? '#ea580c' : '#00d2ff', marginTop: '2px' }}>{inspectManifesto.temperature ?? 0.2}</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Finestra Contesto</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', marginTop: '2px' }}>{inspectManifesto.numCtx || 32768} tokens</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Top-P / Repeat Penalty</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#10b981', marginTop: '2px' }}>{inspectManifesto.topP || 0.85} / 1.1</div>
                </div>
              </div>

              {/* Raw Syntax Box */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isLight ? '#ea580c' : '#00d2ff', fontSize: '0.85rem', fontWeight: 700, marginBottom: '8px' }}>
                  <Terminal size={14} /> Contenuto Modelfile Markdown
                </div>
                <pre style={{
                  background: isLight ? '#f8fafc' : '#080a0f',
                  border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  padding: '16px',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  color: isLight ? '#0f172a' : '#38bdf8',
                  lineHeight: 1.5,
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap'
                }}>
                  {inspectManifesto.rawContent || inspectManifesto.content}
                </pre>
              </div>

            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '16px 24px',
              borderTop: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              {!inspectManifesto.installed && inspectManifesto.id !== 'sigma_assistant' && (
                <button
                  onClick={async () => {
                    await handleInstallFromHub(inspectManifesto);
                    setInspectManifesto(null);
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 18px',
                    borderRadius: '8px',
                    background: 'linear-gradient(135deg, #a855f7 0%, #7c5bf0 100%)',
                    border: 'none',
                    color: '#fff',
                    fontSize: '0.85rem',
                    fontWeight: 800,
                    cursor: 'pointer'
                  }}
                >
                  <Download size={14} /> Scarica & Attiva nel Kernel
                </button>
              )}

              {inspectManifesto.path && (
                <button
                  onClick={() => {
                    handleEditManifesto(inspectManifesto);
                    setInspectManifesto(null);
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 18px',
                    borderRadius: '8px',
                    background: isLight ? '#f1f5f9' : 'rgba(255,255,255,0.1)',
                    border: 'none',
                    color: textPrimary,
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  <Edit3 size={14} /> Modifica nel SigmaLab Editor
                </button>
              )}

              <button
                onClick={() => {
                  handleLaunchChat(inspectManifesto);
                  setInspectManifesto(null);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 20px',
                  borderRadius: '8px',
                  background: isLight 
                    ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                    : 'linear-gradient(135deg, #00d2ff 0%, #0077ff 100%)',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                <MessageSquare size={14} /> Apri Chat con questo Ruolo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODALE SELEZIONE AVATAR */}
      {/* ===================================================================== */}
      {editingAvatarManifesto && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: isLight ? '#ffffff' : '#0d1117',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '620px',
            width: '100%',
            boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '10px',
                  overflow: 'hidden',
                  border: '2px solid #00d2ff'
                }}>
                  <img
                    src={getRoleImage(editingAvatarManifesto)}
                    alt="current avatar"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary }}>
                    Personalizza Avatar: {editingAvatarManifesto.name}
                  </h3>
                  <span style={{ fontSize: '0.72rem', color: textSecondary }}>
                    Scegli un preset ufficiale o carica un'immagine personalizzata
                  </span>
                </div>
              </div>
              <button 
                onClick={() => setEditingAvatarManifesto(null)} 
                style={{ background: 'transparent', border: 'none', color: textPrimary, cursor: 'pointer', padding: '4px' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Upload Immagine Personalizzata */}
            <div style={{
              marginBottom: '18px',
              padding: '12px 14px',
              borderRadius: '12px',
              background: innerCardBg,
              border: innerCardBorder,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px'
            }}>
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: textPrimary }}>
                  Carica Avatar Personalizzato
                </div>
                <div style={{ fontSize: '0.68rem', color: textSecondary }}>
                  Formati supportati: PNG, JPG, WEBP, SVG
                </div>
              </div>

              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                onChange={handleUploadCustomAvatar}
                style={{ display: 'none' }}
              />

              <button
                type="button"
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
                disabled={uploadingAvatar}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  background: isLight ? '#f1f5f9' : 'rgba(0, 210, 255, 0.12)',
                  border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(0, 210, 255, 0.3)',
                  color: isLight ? '#0f172a' : '#00d2ff',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                {uploadingAvatar ? <RefreshCw size={13} className="spin" /> : <Upload size={13} />}
                <span>{uploadingAvatar ? 'Caricamento...' : 'Seleziona File...'}</span>
              </button>
            </div>

            {/* Presets Grid */}
            <div style={{ fontSize: '0.75rem', fontWeight: 800, color: textSecondary, textTransform: 'uppercase', marginBottom: '10px' }}>
              Preset di Sistema Disponibili ({AVATAR_PRESETS.length})
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '20px' }}>
              {AVATAR_PRESETS.map(av => {
                const isCurrent = (editingAvatarManifesto.image === av.path) || 
                  (!editingAvatarManifesto.image && av.path === getRoleImage(editingAvatarManifesto));

                return (
                  <div
                    key={av.path}
                    onClick={() => handleUpdateAvatar(editingAvatarManifesto, av.path)}
                    style={{
                      padding: '8px',
                      borderRadius: '12px',
                      background: innerCardBg,
                      border: isCurrent ? '2px solid #00d2ff' : innerCardBorder,
                      boxShadow: isCurrent ? '0 0 10px rgba(0, 210, 255, 0.3)' : 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ width: '52px', height: '52px', borderRadius: '10px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
                      <img src={av.path} alt={av.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                    <span style={{ fontSize: '0.64rem', fontWeight: 700, color: textPrimary, textAlign: 'center', lineHeight: 1.2 }}>
                      {av.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setEditingAvatarManifesto(null)}
                style={{
                  padding: '8px 18px', borderRadius: '8px',
                  background: innerCardBg, border: innerCardBorder,
                  color: textPrimary, fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer'
                }}
              >
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODALE NUOVO RUOLO AI */}
      {/* ===================================================================== */}
      {newManifestoModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: isLight ? '#ffffff' : '#0d1117',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '650px',
            width: '100%',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
            padding: '24px',
            overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Plus size={20} color={isLight ? '#ea580c' : '#00d2ff'} />
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: textPrimary }}>
                  Crea Nuovo Ruolo AI nel Kernel
                </h3>
              </div>
              <button onClick={() => setNewManifestoModalOpen(false)} style={{ background: 'transparent', border: 'none', color: textPrimary, cursor: 'pointer' }}><X size={18} /></button>
            </div>

            {formError && (
              <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#ef4444', fontSize: '0.78rem', marginBottom: '14px', fontWeight: 700 }}>
                {formError}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>NOME FILE (.md)</label>
                  <input
                    type="text"
                    placeholder="es. senior_code_reviewer.md"
                    value={newFileName}
                    onChange={e => setNewFileName(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>TITOLO / RUOLO</label>
                  <input
                    type="text"
                    placeholder="es. Senior Code Reviewer & Architect"
                    value={newRole}
                    onChange={e => setNewRole(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>CATEGORIA</label>
                  <select
                    value={newCategory}
                    onChange={e => setNewCategory(e.target.value)}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.78rem' }}
                  >
                    <option value="Sviluppo & Codice">Sviluppo & Codice</option>
                    <option value="Architettura & Kernel">Architettura & Kernel</option>
                    <option value="Scienza & Ricerca">Scienza & Ricerca</option>
                    <option value="Creatività & Media">Creatività & Media</option>
                    <option value="Ingegneria & Hardware">Ingegneria & Hardware</option>
                    <option value="Medicina & Salute">Medicina & Salute</option>
                    <option value="Finanza & Business">Finanza & Business</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>TEMPERATURA</label>
                  <input
                    type="text"
                    value={newTemp}
                    onChange={e => setNewTemp(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>FINESTRA CONTESTO</label>
                  <input
                    type="text"
                    value={newCtx}
                    onChange={e => setNewCtx(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.72rem', fontWeight: 700, color: textMuted, display: 'block', marginBottom: '4px' }}>DIRETTIVE E PROMPT DI SISTEMA</label>
                <textarea
                  rows={6}
                  placeholder="Definisci qui la missione, le competenze disciplinari e le linee guida comportamentali del modello..."
                  value={newPrompt}
                  onChange={e => setNewPrompt(e.target.value)}
                  style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', fontFamily: 'inherit', boxSizing: 'border-box', lineHeight: 1.5 }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
              <button
                onClick={() => setNewManifestoModalOpen(false)}
                style={{ padding: '8px 16px', borderRadius: '8px', background: 'transparent', border: innerCardBorder, color: textPrimary, fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button
                onClick={handleCreateManifesto}
                disabled={creating}
                style={{
                  padding: '8px 20px', borderRadius: '8px',
                  background: isLight ? '#ea580c' : 'linear-gradient(135deg, #00d2ff, #0077ff)',
                  border: 'none', color: '#fff', fontSize: '0.8rem', fontWeight: 800, cursor: creating ? 'not-allowed' : 'pointer'
                }}
              >
                {creating ? 'Creazione in corso...' : 'Crea Ruolo AI'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODALE DETTAGLIO SCHEDA RUOLO (STILE SKILLS)                          */}
      {/* ===================================================================== */}
      {selectedRoleModal && (
        <RoleDetailModal
          role={selectedRoleModal}
          isInstalled={Boolean(selectedRoleModal.path || selectedRoleModal.installed || manifestiList.some(m => (m.filename && m.filename === selectedRoleModal.filename) || (m.id && m.id === selectedRoleModal.id)))}
          isLight={isLight}
          onClose={() => setSelectedRoleModal(null)}
          onLaunchChat={handleLaunchChat}
          onEdit={handleEditManifesto}
          onInspect={(r) => setInspectManifesto(r)}
          onUninstall={handleUninstallManifesto}
          onInstallFromHub={handleInstallFromHub}
          onChangeAvatar={(r) => setEditingAvatarManifesto(r)}
          isInstalling={installingId === selectedRoleModal.id}
          isUninstalling={uninstallingId === (selectedRoleModal.id || selectedRoleModal.filename)}
          extractSystemPrompt={extractSystemPrompt}
        />
      )}

    </div>
  );
}