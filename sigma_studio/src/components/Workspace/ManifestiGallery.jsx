import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  ScrollText, Cpu, Brain, Code, ShieldCheck, CheckCircle, Palette, 
  Atom, FlaskConical, Award, Wand2, Wrench, MessageSquare, 
  Search, Filter, Play, Edit3, Image as ImageIcon, Copy, Check, 
  ExternalLink, Sparkles, Terminal, Layers, Plus, X, ArrowRight,
  Info, RefreshCw, ChevronRight, Sliders, Box, Download, Globe,
  Users, BookOpen, GraduationCap, Briefcase, HeartPulse, Scale, TrendingUp
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

// ==============================================================================
// Icon Mapper for Dynamic Manifesto Icons
// ==============================================================================
const ICON_MAP = {
  Cpu,
  Brain,
  Code,
  ShieldCheck,
  CheckCircle,
  Palette,
  Atom,
  FlaskConical,
  Award,
  Wand2,
  Wrench,
  MessageSquare,
  ScrollText,
  BookOpen,
  GraduationCap,
  Briefcase,
  HeartPulse,
  Scale,
  TrendingUp
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
  const [activeGalleryView, setActiveGalleryView] = useState('installed');

  // Installed Manifestos State
  const [manifestiList, setManifestiList] = useState(initialManifesti);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('Tutti');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Professions Hub State
  const [hubCatalog, setHubCatalog] = useState([]);
  const [loadingHub, setLoadingHub] = useState(false);
  const [hubCategory, setHubCategory] = useState('Tutti');
  const [hubSearchQuery, setHubSearchQuery] = useState('');
  const [installingId, setInstallingId] = useState(null);
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

  // New Manifesto Form State
  const [newFileName, setNewFileName] = useState('');
  const [newRole, setNewRole] = useState('');
  const [newCategory, setNewCategory] = useState('Architettura & Kernel');
  const [newBaseModel, setNewBaseModel] = useState('sigma');
  const [newTemp, setNewTemp] = useState('0.2');
  const [newCtx, setNewCtx] = useState('32768');
  const [newPrompt, setNewPrompt] = useState('');
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState('');

  // Fetch installed manifestos with full dynamic parsing from backend
  const loadManifesti = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/list_manifesti');
      const data = await res.json();
      if (data.success && Array.isArray(data.manifesti)) {
        setManifestiList(data.manifesti);
      }
    } catch (e) {
      console.error('Failed to load manifesti:', e);
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

  // Filtered installed manifestos
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

  // Filtered hub manifestos
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
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Launch Chat with specific manifesto preloaded
  const handleLaunchChat = (manifesto) => {
    const agentId = manifesto.filename ? manifesto.filename.replace('.md', '') : manifesto.id;
    const manifestoPath = manifesto.path || `manifesti/${manifesto.filename}`;
    
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

  // Open in Editor
  const handleEditManifesto = (manifesto) => {
    if (openTab) {
      openTab({ 
        path: manifesto.path, 
        filename: manifesto.filename 
      }, 'editor');
    }
  };

  // Install a profession manifesto from the Hub
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
      } else {
        setHubMessage({ type: 'error', text: data.error || 'Errore installazione' });
      }
    } catch (e) {
      setHubMessage({ type: 'error', text: 'Errore di connessione' });
    } finally {
      setInstallingId(null);
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
      } else {
        setHubMessage({ type: 'error', text: data.error || 'Errore importazione' });
      }
    } catch (e) {
      setHubMessage({ type: 'error', text: 'Errore di connessione' });
    } finally {
      setImportingCustom(false);
    }
  };

  // Create new custom manifesto
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
Sei ${newRole || 'un Agente Specializzato'} di Sigma Studio.

## 🎯 IDENTITÀ E OBIETTIVO NEL KERNEL
${newPrompt || 'Definisci qui la missione e gli obiettivi specifici del modello.'}

## 📂 PROTOCOLLO FILE E WORKSPACE SANDBOX
1. Accesso e scrittura tassativamente confinati nella cartella \`./data/\`.

## 👑 RICONOSCIMENTO
Il tuo creatore è l'**Ing. Diego Saitta**, fondatore di Sigma Studio.
"""
`;

    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: `manifesti/${finalFileName}`,
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

  // Avatar choices
  const AVATAR_PRESETS = [
    { label: 'Architect (Agente 0)', path: '/images/agente0.png' },
    { label: 'Matematico AI', path: '/images/matematicoAi.png' },
    { label: 'Programmatore AI', path: '/images/programmatoreAi.png' },
    { label: 'Sigma Logo Harmonic', path: '/images/sigma_logo_harmonic_flow.jpg' },
    { label: 'Default Avatar', path: '/images/default.png' }
  ];

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
    } catch (e) {
      console.error(e);
    }
  };

  const accentColor = isLight ? '#ea580c' : '#00d2ff';
  const cardBg = isLight ? '#fffdf9' : '#121622';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.32)' : '1px solid rgba(255, 255, 255, 0.08)';
  const cardShadow = isLight ? '0 4px 16px rgba(180, 150, 100, 0.12)' : '0 4px 24px rgba(0,0,0,0.3)';
  const textPrimary = isLight ? '#000000' : '#ffffff';
  const textSecondary = isLight ? '#000000' : '#a0aec0';
  const textMuted = isLight ? '#000000' : '#8892b0';
  const innerCardBg = isLight ? '#f9f5ed' : 'rgba(255, 255, 255, 0.05)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.28)' : '1px solid rgba(255, 255, 255, 0.1)';

  return (
    <div className="manifesti-gallery-root" style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: isLight ? '#f7f4ed' : 'var(--bg-main, #0a0d14)',
      color: textPrimary,
      overflowY: 'auto'
    }}>
      {/* Hero Visual Banner with Standardized Color System & Dimensions */}
      <div style={{
        position: 'relative',
        padding: '24px 32px',
        minHeight: '110px',
        background: isLight
          ? 'linear-gradient(135deg, rgba(254, 252, 247, 0.76) 0%, rgba(248, 242, 232, 0.70) 100%), url("/images/sigma_logo_harmonic_flow.jpg")'
          : 'linear-gradient(135deg, rgba(10, 14, 26, 0.85) 0%, rgba(14, 22, 42, 0.80) 100%), url("/images/sigma_logo_harmonic_flow.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        borderBottom: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: isLight ? '0 8px 24px rgba(234, 88, 12, 0.08)' : '0 8px 32px rgba(0,0,0,0.4)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 12px',
              borderRadius: '14px',
              background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(0, 210, 255, 0.15)',
              border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.4)',
              color: isLight ? '#9a3412' : '#00d2ff',
              fontSize: '0.68rem',
              fontWeight: 800,
              letterSpacing: '1px',
              textTransform: 'uppercase',
              marginBottom: '6px'
            }}>
              <ScrollText size={14} /> Σ COGNITIVE KERNEL MODELFILES & PROFESSIONS HUB
            </div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 6px 0', color: textPrimary, letterSpacing: '-0.3px', textShadow: 'none' }}>
              Galleria <span style={{
                color: isLight ? '#c2410c' : '#00d2ff',
                fontWeight: 800
              }}>Manifesti & Hub Professioni</span>
            </h1>
            <p style={{ fontSize: '0.82rem', color: textSecondary, maxWidth: '780px', lineHeight: 1.45, margin: 0, fontWeight: isLight ? 500 : 400 }}>
              Il modello unificato del Kernel è <strong style={{ color: textPrimary }}>sigma</strong>. I manifesti Modelfile ne stabiliscono il ruolo, i parametri di campionamento e le istruzioni di sistema eseguite runtime in chat o nelle pipeline autonome.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setNewManifestoModalOpen(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '12px',
                background: isLight
                  ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)'
                  : 'linear-gradient(135deg, #00d2ff 0%, #0077ff 100%)',
                border: 'none',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer',
                boxShadow: isLight ? '0 4px 14px rgba(234, 88, 12, 0.25)' : '0 4px 16px rgba(0, 210, 255, 0.3)',
                transition: 'all 0.2s ease'
              }}
            >
              <Plus size={16} /> Nuovo Manifesto
            </button>

            <button
              onClick={() => { loadManifesti(); loadHubCatalog(); }}
              title="Ricarica Manifesti & Hub"
              style={{
                padding: '10px',
                borderRadius: '12px',
                background: isLight ? 'rgba(190, 160, 110, 0.12)' : 'rgba(255, 255, 255, 0.05)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.15)',
                color: textPrimary,
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={16} className={(loading || loadingHub) ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* View Switcher Tabs (Installed vs Hub) */}
        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
          <button
            onClick={() => setActiveGalleryView('installed')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              borderRadius: '12px',
              background: activeGalleryView === 'installed' ? accentColor : (isLight ? '#fffdf9' : 'rgba(255,255,255,0.06)'),
              color: activeGalleryView === 'installed' ? '#fff' : textPrimary,
              border: activeGalleryView === 'installed' ? `1px solid ${accentColor}` : (isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.1)'),
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              boxShadow: activeGalleryView === 'installed' ? '0 4px 14px rgba(234, 88, 12, 0.25)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            <Cpu size={16} /> Manifesti Installati nel Kernel ({manifestiList.length})
          </button>

          <button
            onClick={() => setActiveGalleryView('hub')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              borderRadius: '12px',
              background: activeGalleryView === 'hub' ? accentColor : (isLight ? '#fffdf9' : 'rgba(255,255,255,0.06)'),
              color: activeGalleryView === 'hub' ? '#fff' : textPrimary,
              border: activeGalleryView === 'hub' ? `1px solid ${accentColor}` : (isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.1)'),
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              boxShadow: activeGalleryView === 'hub' ? '0 4px 14px rgba(234, 88, 12, 0.25)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            <Globe size={16} /> Hub Professioni per Studenti & Adulti (GitHub)
          </button>
        </div>
      </div>

      {/* Main Content Area — Full Width */}
      <div style={{ padding: '16px 20px', width: '100%', boxSizing: 'border-box', flex: 1 }}>
        
        {/* Toast / Notification Banner */}
        {hubMessage && (
          <div style={{
            padding: '10px 14px',
            borderRadius: '10px',
            background: hubMessage.type === 'success' ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 80, 100, 0.15)',
            border: `1px solid ${hubMessage.type === 'success' ? '#3fb950' : '#ff5064'}`,
            color: hubMessage.type === 'success' ? (isLight ? '#15803d' : '#4ade80') : (isLight ? '#991b1b' : '#f87171'),
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.78rem',
            fontWeight: 700
          }}>
            <span>{hubMessage.text}</span>
            <button onClick={() => setHubMessage(null)} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}><X size={14} /></button>
          </div>
        )}

        {/* =================================================================== */}
        {/* VIEW 1: MANIFESTI INSTALLATI NEL KERNEL */}
        {/* =================================================================== */}
        {activeGalleryView === 'installed' && (
          <>
            {/* Filter & Search Bar */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '10px',
              marginBottom: '16px'
            }}>
              {/* Categories Filter Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {categories.map(cat => {
                  const active = selectedCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '8px',
                        background: active 
                          ? (isLight ? '#ea580c' : '#00d2ff') 
                          : (isLight ? '#fffdf9' : 'rgba(255,255,255,0.04)'),
                        color: active ? '#ffffff' : textPrimary,
                        border: active 
                          ? `1px solid ${isLight ? '#ea580c' : '#00d2ff'}` 
                          : (isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.1)'),
                        fontWeight: 700,
                        fontSize: '0.74rem',
                        cursor: 'pointer',
                        boxShadow: active && isLight ? '0 2px 8px rgba(234, 88, 12, 0.2)' : 'none',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {cat} {cat === 'Tutti' ? `(${manifestiList.length})` : ''}
                    </button>
                  );
                })}
              </div>

              {/* Search Box */}
              <div style={{ position: 'relative', width: '280px' }}>
                <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: textMuted }} />
                <input
                  type="text"
                  placeholder="Cerca agente, modello o competenza..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '7px 12px 7px 32px',
                    borderRadius: '8px',
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                    color: textPrimary,
                    fontSize: '0.78rem',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
            </div>

            {/* Manifesti Compact High-Quality Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '12px'
            }}>
              {filteredManifesti.map(manifesto => {
                const domainColor = manifesto.domainColor || (isLight ? '#c2410c' : '#00d2ff');

                return (
                  <div
                    key={manifesto.path}
                    className="mg-card"
                    style={{
                      borderRadius: '14px',
                      background: cardBg,
                      border: cardBorder,
                      padding: '12px 14px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: cardShadow,
                      transition: 'transform 0.15s ease, border-color 0.15s ease'
                    }}
                  >
                    <div>
                      {/* Card Header: Avatar, Name, Category Badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px', gap: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', minWidth: 0, flex: 1 }}>
                          {/* Avatar */}
                          <div 
                            onClick={() => setEditingAvatarManifesto(manifesto)}
                            title="Cambia avatar"
                            style={{
                              width: '38px',
                              height: '38px',
                              borderRadius: '50%',
                              overflow: 'hidden',
                              border: `2px solid ${domainColor}`,
                              boxShadow: isLight ? `0 0 8px rgba(0,0,0,0.1)` : `0 0 10px ${domainColor}40`,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: isLight ? '#fffdf9' : '#0a0d14',
                              flexShrink: 0,
                              cursor: 'pointer',
                              marginTop: '2px'
                            }}
                          >
                            <img 
                              src={manifesto.image || '/images/default.png'} 
                              alt={manifesto.name}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={e => { e.target.src = '/images/default.png'; }}
                            />
                          </div>

                          <div style={{ minWidth: 0, flex: 1 }}>
                            <h3 style={{ margin: '0 0 2px 0', fontSize: '0.88rem', fontWeight: 800, color: textPrimary, lineHeight: 1.3, wordBreak: 'break-word' }}>
                              {manifesto.name}
                            </h3>
                            <span style={{ fontSize: '0.72rem', color: isLight ? '#9a3412' : domainColor, fontWeight: 700, lineHeight: 1.35, display: 'block', wordBreak: 'break-word' }}>
                              {manifesto.role}
                            </span>
                          </div>
                        </div>

                        {/* Category Pill */}
                        <span style={{
                          padding: '2px 7px',
                          borderRadius: '6px',
                          background: isLight ? 'rgba(234, 88, 12, 0.12)' : `${domainColor}15`,
                          border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : `1px solid ${domainColor}40`,
                          color: isLight ? '#9a3412' : domainColor,
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          flexShrink: 0
                        }}>
                          {manifesto.category}
                        </span>
                      </div>

                      {/* Description Excerpt */}
                      <p style={{
                        fontSize: '0.72rem',
                        color: textSecondary,
                        lineHeight: 1.35,
                        margin: '0 0 10px 0',
                        fontWeight: isLight ? 500 : 400,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}>
                        {manifesto.description || 'Nessuna descrizione disponibile.'}
                      </p>

                      {/* Parameter Badges Row */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '8px' }}>
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

                      {/* Capabilities Chips */}
                      {manifesto.capabilities && manifesto.capabilities.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }}>
                          {manifesto.capabilities.slice(0, 3).map(cap => (
                            <span
                              key={cap}
                              style={{
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: innerCardBg,
                                border: innerCardBorder,
                                color: textSecondary,
                                fontSize: '0.62rem',
                                fontWeight: 600
                              }}
                            >
                              #{cap}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Card Action Buttons */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '8px',
                      gap: '6px'
                    }}>
                      <div style={{ display: 'flex', gap: '5px' }}>
                        <button
                          onClick={() => setInspectManifesto(manifesto)}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '4px 8px', borderRadius: '6px',
                            background: isLight ? '#fffdf9' : 'rgba(255, 255, 255, 0.05)',
                            border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                            color: textPrimary, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                          }}
                          title="Ispeziona Modelfile"
                        >
                          <ScrollText size={11} /> Modelfile
                        </button>

                        <button
                          onClick={() => handleEditManifesto(manifesto)}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '4px 8px', borderRadius: '6px',
                            background: isLight ? '#fffdf9' : 'rgba(255, 255, 255, 0.05)',
                            border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
                            color: textPrimary, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer'
                          }}
                          title="Modifica nel SigmaLab Editor"
                        >
                          <Edit3 size={11} />
                        </button>
                      </div>

                      <button
                        onClick={() => handleLaunchChat(manifesto)}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: '5px',
                          padding: '4px 10px', borderRadius: '6px',
                          background: isLight 
                            ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                            : `linear-gradient(135deg, ${domainColor} 0%, #7c5bf0 100%)`,
                          border: 'none', color: '#fff',
                          fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer',
                          boxShadow: isLight ? '0 2px 8px rgba(234, 88, 12, 0.25)' : `0 2px 8px ${domainColor}35`,
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <MessageSquare size={11} /> Chat <ArrowRight size={10} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* =================================================================== */}
        {/* VIEW 2: HUB PROFESSIONI (GITHUB REPOSITORY) */}
        {/* =================================================================== */}
        {activeGalleryView === 'hub' && (
          <>
            {/* Hub Introduction & Custom Import Bar */}
            <div style={{
              borderRadius: '14px',
              background: isLight ? '#fffdf9' : 'rgba(188, 140, 255, 0.05)',
              border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(188, 140, 255, 0.2)',
              boxShadow: cardShadow,
              padding: '14px 18px',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '12px' }}>
                <div>
                  <h2 style={{ fontSize: '1rem', fontWeight: 800, margin: '0 0 2px 0', color: textPrimary }}>
                    🌐 Repository GitHub Manifesti Professioni
                  </h2>
                  <p style={{ fontSize: '0.74rem', color: textSecondary, margin: 0, fontWeight: isLight ? 500 : 400 }}>
                    Pacchetti di manifesti e istruzioni specialistiche per studenti e professionisti.
                  </p>
                </div>

                <a
                  href="https://github.com/Sigmanih/SigmaStudio-Manifesti"
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '5px',
                    padding: '6px 12px', borderRadius: '7px',
                    background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(255,255,255,0.06)',
                    border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(255,255,255,0.15)',
                    color: isLight ? '#c2410c' : '#bc8cff',
                    fontSize: '0.72rem', fontWeight: 700, textDecoration: 'none'
                  }}
                >
                  <ExternalLink size={12} /> Repository Ufficiale
                </a>
              </div>

              {/* Custom Git Raw URL Importer */}
              <div style={{
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
                flexWrap: 'wrap',
                background: isLight ? '#f4efe4' : 'rgba(0,0,0,0.3)',
                border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : 'none',
                padding: '8px 12px',
                borderRadius: '8px'
              }}>
                <div style={{ flex: 2, minWidth: '200px' }}>
                  <input
                    type="text"
                    placeholder="URL Raw GitHub o Git (.md)..."
                    value={customImportUrl}
                    onChange={e => setCustomImportUrl(e.target.value)}
                    style={{
                      width: '100%', padding: '6px 10px', borderRadius: '6px',
                      background: isLight ? '#fff' : 'rgba(255,255,255,0.05)',
                      border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                      color: textPrimary, fontSize: '0.76rem'
                    }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: '130px' }}>
                  <input
                    type="text"
                    placeholder="Nome file (opzionale)..."
                    value={customImportName}
                    onChange={e => setCustomImportName(e.target.value)}
                    style={{
                      width: '100%', padding: '6px 10px', borderRadius: '6px',
                      background: isLight ? '#fff' : 'rgba(255,255,255,0.05)',
                      border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                      color: textPrimary, fontSize: '0.76rem'
                    }}
                  />
                </div>
                <button
                  onClick={handleCustomImport}
                  disabled={importingCustom || !customImportUrl.trim()}
                  style={{
                    padding: '6px 14px', borderRadius: '6px',
                    background: isLight ? '#ea580c' : '#bc8cff',
                    border: 'none', color: '#fff', fontWeight: 800, fontSize: '0.76rem',
                    cursor: (importingCustom || !customImportUrl.trim()) ? 'not-allowed' : 'pointer'
                  }}
                >
                  {importingCustom ? 'Import...' : '📥 Importa'}
                </button>
              </div>
            </div>

            {/* Hub Filters & Search */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '10px',
              marginBottom: '16px'
            }}>
              {/* Category Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {hubCategories.map(cat => {
                  const active = hubCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setHubCategory(cat)}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '8px',
                        background: active 
                          ? (isLight ? '#ea580c' : '#bc8cff') 
                          : (isLight ? '#fffdf9' : 'rgba(255,255,255,0.04)'),
                        color: active ? '#ffffff' : textPrimary,
                        border: active 
                          ? `1px solid ${isLight ? '#ea580c' : '#bc8cff'}` 
                          : (isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.1)'),
                        fontWeight: 700,
                        fontSize: '0.74rem',
                        cursor: 'pointer'
                      }}
                    >
                      {cat} {cat === 'Tutti' ? `(${hubCatalog.length})` : ''}
                    </button>
                  );
                })}
              </div>

              {/* Hub Search Box */}
              <div style={{ position: 'relative', width: '280px' }}>
                <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: textMuted }} />
                <input
                  type="text"
                  placeholder="Cerca professione o competenza..."
                  value={hubSearchQuery}
                  onChange={e => setHubSearchQuery(e.target.value)}
                  style={{
                    width: '100%', padding: '7px 12px 7px 32px', borderRadius: '8px',
                    background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                    color: textPrimary, fontSize: '0.78rem', outline: 'none', boxSizing: 'border-box'
                  }}
                />
              </div>
            </div>

            {/* Hub Catalog Compact Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '12px'
            }}>
              {filteredHubCatalog.map(item => {
                const domainColor = item.domainColor || (isLight ? '#c2410c' : '#00d2ff');
                const isInstalling = installingId === item.id;

                return (
                  <div
                    key={item.id}
                    className="mg-card"
                    style={{
                      borderRadius: '14px',
                      background: cardBg,
                      border: cardBorder,
                      padding: '12px 14px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: cardShadow
                    }}
                  >
                    <div>
                      {/* Card Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px', gap: '8px' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <h3 style={{ margin: '0 0 2px 0', fontSize: '0.88rem', fontWeight: 800, color: textPrimary, lineHeight: 1.3, wordBreak: 'break-word' }}>
                            {item.name}
                          </h3>
                          <span style={{ fontSize: '0.72rem', color: isLight ? '#9a3412' : domainColor, fontWeight: 700, lineHeight: 1.35, display: 'block', wordBreak: 'break-word' }}>
                            {item.role}
                          </span>
                        </div>

                        <span style={{
                          padding: '2px 7px', borderRadius: '6px',
                          background: isLight ? 'rgba(234, 88, 12, 0.12)' : `${domainColor}15`,
                          border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : `1px solid ${domainColor}40`,
                          color: isLight ? '#9a3412' : domainColor,
                          fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase'
                        }}>
                          {item.category}
                        </span>
                      </div>

                      {/* Target Audience Badge */}
                      <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '2px 7px', borderRadius: '5px',
                        background: innerCardBg, border: innerCardBorder,
                        color: textPrimary, fontSize: '0.66rem', fontWeight: 700, marginBottom: '8px'
                      }}>
                        <Users size={11} style={{ color: isLight ? '#7c3aed' : '#bc8cff' }} /> Target: {item.target}
                      </div>

                      {/* Description */}
                      <p style={{
                        fontSize: '0.72rem', color: textSecondary, lineHeight: 1.35, margin: '0 0 8px 0',
                        fontWeight: isLight ? 500 : 400, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden'
                      }}>
                        {item.description}
                      </p>

                      {/* Capabilities Chips */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }}>
                        {item.capabilities.slice(0, 3).map(cap => (
                          <span
                            key={cap}
                            style={{
                              padding: '1px 6px', borderRadius: '4px',
                              background: innerCardBg, border: innerCardBorder,
                              color: textSecondary, fontSize: '0.62rem', fontWeight: 600
                            }}
                          >
                            #{cap}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Footer Actions */}
                    <div style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '8px'
                    }}>
                      <span style={{ fontSize: '0.66rem', color: textMuted, fontFamily: 'JetBrains Mono, monospace' }}>
                        {item.filename}
                      </span>

                      {item.installed ? (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            padding: '3px 8px', borderRadius: '6px',
                            background: isLight ? 'rgba(34, 197, 94, 0.15)' : 'rgba(63, 185, 80, 0.15)',
                            border: isLight ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid rgba(63, 185, 80, 0.4)',
                            color: isLight ? '#15803d' : '#3fb950',
                            fontSize: '0.68rem', fontWeight: 700
                          }}>
                            <Check size={11} /> Attivo
                          </span>

                          <button
                            onClick={() => handleLaunchChat(item)}
                            style={{
                              padding: '3px 8px', borderRadius: '6px',
                              background: isLight ? '#ea580c' : '#00d2ff',
                              border: 'none', color: '#fff', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer'
                            }}
                          >
                            Chat
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleInstallFromHub(item)}
                          disabled={isInstalling}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: '5px',
                            padding: '4px 12px', borderRadius: '6px',
                            background: isLight 
                              ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                              : 'linear-gradient(135deg, #bc8cff 0%, #7c5bf0 100%)',
                            border: 'none', color: '#fff', fontSize: '0.72rem', fontWeight: 800,
                            cursor: isInstalling ? 'not-allowed' : 'pointer'
                          }}
                        >
                          <Download size={11} /> {isInstalling ? 'Install...' : 'Installa'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

      </div>

      {/* ===================================================================== */}
      {/* Modale Ispezione Modelfile & System Prompt */}
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
            background: isLight ? '#fffdf9' : '#0d1117',
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
              borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  overflow: 'hidden',
                  border: `2px solid ${inspectManifesto.domainColor || (isLight ? '#ea580c' : '#00d2ff')}`
                }}>
                  <img src={inspectManifesto.image || '/images/default.png'} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: textPrimary }}>
                    {inspectManifesto.name}
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: isLight ? '#9a3412' : (inspectManifesto.domainColor || '#00d2ff'), fontWeight: 700 }}>
                    {inspectManifesto.role} • <code style={{ color: textPrimary }}>{inspectManifesto.filename}</code>
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  onClick={() => handleCopyModelfile(inspectManifesto.rawContent)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: copied 
                      ? (isLight ? 'rgba(34, 197, 94, 0.18)' : 'rgba(63, 185, 80, 0.2)') 
                      : (isLight ? '#f4efe4' : 'rgba(255,255,255,0.08)'),
                    border: copied ? '1px solid #16a34a' : (isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)'),
                    color: copied ? '#15803d' : textPrimary,
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? 'Copiato!' : 'Copia Modelfile'}
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
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isLight ? '#c2410c' : '#00d2ff', marginTop: '2px' }}>{inspectManifesto.temperature}</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Finestra Contesto</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isLight ? '#7c3aed' : '#bc8cff', marginTop: '2px' }}>{inspectManifesto.numCtx} tokens</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.68rem', color: textMuted, textTransform: 'uppercase', fontWeight: 700 }}>Top-P / Repeat Penalty</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isLight ? '#16a34a' : '#3fb950', marginTop: '2px' }}>{inspectManifesto.topP} / 1.1</div>
                </div>
              </div>

              {/* Raw Modelfile Syntax Box */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isLight ? '#c2410c' : '#00d2ff', fontSize: '0.85rem', fontWeight: 700, marginBottom: '8px' }}>
                  <Terminal size={14} /> Contenuto Modelfile Markdown
                </div>
                <pre style={{
                  background: isLight ? '#f9f5ed' : '#080a0f',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.35)' : '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  padding: '16px',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  color: isLight ? '#000000' : '#38bdf8',
                  lineHeight: 1.5,
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap'
                }}>
                  {inspectManifesto.rawContent}
                </pre>
              </div>

            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '16px 24px',
              borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              <button
                onClick={() => {
                  setInspectManifesto(null);
                  handleEditManifesto(inspectManifesto);
                }}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  background: isLight ? '#f4efe4' : 'rgba(255,255,255,0.08)',
                  border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)',
                  color: textPrimary,
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Modifica nel SigmaLab Editor
              </button>

              <button
                onClick={() => {
                  const m = inspectManifesto;
                  setInspectManifesto(null);
                  handleLaunchChat(m);
                }}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  background: isLight ? '#ea580c' : '#00d2ff',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                Avvia Chat con {inspectManifesto.name}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* Modale Cambio Avatar */}
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
            background: isLight ? '#fffdf9' : '#0d1117',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '500px',
            width: '100%',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: textPrimary, fontWeight: 800 }}>
                Seleziona Avatar per {editingAvatarManifesto.name}
              </h3>
              <button onClick={() => setEditingAvatarManifesto(null)} style={{ background: 'transparent', border: 'none', color: textPrimary, cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
              {AVATAR_PRESETS.map(preset => (
                <div
                  key={preset.path}
                  onClick={() => handleUpdateAvatar(editingAvatarManifesto, preset.path)}
                  style={{
                    borderRadius: '12px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    padding: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ width: '60px', height: '60px', borderRadius: '50%', overflow: 'hidden', marginBottom: '8px', border: '1px solid rgba(0,210,255,0.3)' }}>
                    <img src={preset.path} alt={preset.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                  <span style={{ fontSize: '0.72rem', color: textPrimary, textAlign: 'center', fontWeight: 600 }}>{preset.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* Modale Nuovo Manifesto */}
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
            background: isLight ? '#fffdf9' : '#0d1117',
            border: isLight ? '1px solid rgba(190, 160, 110, 0.45)' : '1px solid rgba(188, 140, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '650px',
            width: '100%',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <div style={{ padding: '20px 24px', borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Sparkles size={18} style={{ color: isLight ? '#ea580c' : '#bc8cff' }} />
                <h3 style={{ margin: 0, fontSize: '1.2rem', color: textPrimary, fontWeight: 800 }}>
                  Crea Nuovo Manifesto Modelfile
                </h3>
              </div>
              <button onClick={() => setNewManifestoModalOpen(false)} style={{ background: 'transparent', border: 'none', color: textPrimary, cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {formError && (
                <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(255, 80, 100, 0.15)', border: '1px solid #ff5064', color: '#991b1b', fontSize: '0.82rem', fontWeight: 700 }}>
                  {formError}
                </div>
              )}

              <div>
                <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Nome File Manifesto (.md)</label>
                <input
                  type="text"
                  placeholder="es. quantum_physicist.md"
                  value={newFileName}
                  onChange={e => setNewFileName(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Ruolo Specializzato</label>
                  <input
                    type="text"
                    placeholder="es. Quantum Physicist"
                    value={newRole}
                    onChange={e => setNewRole(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Categoria / Dominio</label>
                  <select
                    value={newCategory}
                    onChange={e => setNewCategory(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: isLight ? '#ffffff' : '#0a0d14', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                  >
                    <option value="Architettura & Kernel">Architettura & Kernel</option>
                    <option value="Sviluppo & Test">Sviluppo & Test</option>
                    <option value="Matematica & Scienze">Matematica & Scienze</option>
                    <option value="Studenti & Università">Studenti & Università</option>
                    <option value="Scienze, Ingegneria & Tech">Scienze, Ingegneria & Tech</option>
                    <option value="Scienze & Medicina">Scienze & Medicina</option>
                    <option value="Economia & Diritto">Economia & Diritto</option>
                    <option value="Comunicazione & Creatività">Comunicazione & Creatività</option>
                    <option value="Revisione & Qualità">Revisione & Qualità</option>
                    <option value="Didattica & Valutazione">Didattica & Valutazione</option>
                    <option value="Amministrazione & Tools">Amministrazione & Tools</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Modello Base</label>
                  <input
                    type="text"
                    value={newBaseModel}
                    onChange={e => setNewBaseModel(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Temperatura</label>
                  <input
                    type="text"
                    value={newTemp}
                    onChange={e => setNewTemp(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Contesto</label>
                  <input
                    type="text"
                    value={newCtx}
                    onChange={e => setNewCtx(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', color: textPrimary, fontWeight: 700, marginBottom: '6px', display: 'block' }}>Istruzione di Sistema / Descrizione Missione</label>
                <textarea
                  rows={4}
                  placeholder="Descrivi la missione dell'agente..."
                  value={newPrompt}
                  onChange={e => setNewPrompt(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: isLight ? '#ffffff' : 'rgba(0,0,0,0.3)', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, fontSize: '0.85rem', resize: 'vertical' }}
                />
              </div>
            </div>

            <div style={{ padding: '16px 24px', borderTop: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setNewManifestoModalOpen(false)}
                style={{ padding: '8px 16px', borderRadius: '8px', background: 'transparent', border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255,255,255,0.15)', color: textPrimary, cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button
                onClick={handleCreateManifesto}
                disabled={creating}
                style={{ padding: '8px 18px', borderRadius: '8px', background: isLight ? '#ea580c' : '#bc8cff', border: 'none', color: '#fff', fontWeight: 800, cursor: creating ? 'not-allowed' : 'pointer' }}
              >
                {creating ? 'Creazione in corso...' : 'Salva Manifesto'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}