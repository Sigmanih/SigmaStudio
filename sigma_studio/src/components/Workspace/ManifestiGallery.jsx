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

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-main, #0a0d14)',
      color: 'var(--text-main, #e2e8f0)',
      overflowY: 'auto'
    }}>
      {/* Hero Visual Banner */}
      <div style={{
        position: 'relative',
        padding: '28px 36px',
        background: 'linear-gradient(135deg, rgba(14, 16, 22, 0.96) 0%, rgba(20, 26, 42, 0.92) 100%), url("/images/sigma_logo_harmonic_flow.jpg")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 14px',
              borderRadius: '20px',
              background: 'rgba(188, 140, 255, 0.15)',
              border: '1px solid rgba(188, 140, 255, 0.4)',
              color: '#bc8cff',
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '1.2px',
              textTransform: 'uppercase',
              marginBottom: '10px'
            }}>
              <ScrollText size={14} /> Σ COGNITIVE KERNEL MODELFILES & PROFESSIONS HUB
            </div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, margin: '0 0 8px 0', color: '#fff', letterSpacing: '-0.5px' }}>
              Galleria <span style={{
                background: 'linear-gradient(135deg, #bc8cff 0%, #00d2ff 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>Manifesti & Hub Professioni</span>
            </h1>
            <p style={{ fontSize: '0.88rem', color: '#a0aec0', maxWidth: '780px', lineHeight: 1.5, margin: 0 }}>
              Il modello unificato del Kernel è <strong>sigma</strong>. I manifesti Modelfile ne stabiliscono il ruolo, i parametri di campionamento e le istruzioni di sistema eseguite runtime in chat o nelle pipeline autonome.
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
                background: 'linear-gradient(135deg, #bc8cff 0%, #7c5bf0 100%)',
                border: 'none',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(188, 140, 255, 0.3)',
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
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#e2e8f0',
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
              background: activeGalleryView === 'installed' ? '#00d2ff' : 'rgba(255,255,255,0.06)',
              color: activeGalleryView === 'installed' ? '#0a0d14' : '#e2e8f0',
              border: activeGalleryView === 'installed' ? '1px solid #00d2ff' : '1px solid rgba(255,255,255,0.1)',
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
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
              background: activeGalleryView === 'hub' ? '#bc8cff' : 'rgba(255,255,255,0.06)',
              color: activeGalleryView === 'hub' ? '#0a0d14' : '#e2e8f0',
              border: activeGalleryView === 'hub' ? '1px solid #bc8cff' : '1px solid rgba(255,255,255,0.1)',
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            <Globe size={16} /> Hub Professioni per Studenti & Adulti (GitHub)
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ padding: '32px 36px', maxWidth: '1440px', width: '100%', boxSizing: 'border-box' }}>
        
        {/* Toast / Notification Banner */}
        {hubMessage && (
          <div style={{
            padding: '12px 18px',
            borderRadius: '12px',
            background: hubMessage.type === 'success' ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 80, 100, 0.15)',
            border: `1px solid ${hubMessage.type === 'success' ? '#3fb950' : '#ff5064'}`,
            color: hubMessage.type === 'success' ? '#3fb950' : '#ff5064',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <span>{hubMessage.text}</span>
            <button onClick={() => setHubMessage(null)} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}><X size={16} /></button>
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
              gap: '16px',
              marginBottom: '28px'
            }}>
              {/* Categories Filter Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {categories.map(cat => {
                  const active = selectedCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '10px',
                        background: active ? '#bc8cff' : 'rgba(255,255,255,0.04)',
                        color: active ? '#0a0d14' : '#e2e8f0',
                        border: active ? '1px solid #bc8cff' : '1px solid rgba(255,255,255,0.1)',
                        fontWeight: 700,
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      {cat} {cat === 'Tutti' ? `(${manifestiList.length})` : ''}
                    </button>
                  );
                })}
              </div>

              {/* Search Box */}
              <div style={{ position: 'relative', width: '320px' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#8892b0' }} />
                <input
                  type="text"
                  placeholder="Cerca agente, modello o competenza..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 16px 10px 38px',
                    borderRadius: '10px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: '0.85rem',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
            </div>

            {/* Manifesti Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
              gap: '24px'
            }}>
              {filteredManifesti.map(manifesto => {
                const domainColor = manifesto.domainColor || '#00d2ff';

                return (
                  <div
                    key={manifesto.path}
                    style={{
                      borderRadius: '18px',
                      background: 'rgba(255, 255, 255, 0.025)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      padding: '24px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
                      transition: 'transform 0.2s ease, border-color 0.2s ease'
                    }}
                  >
                    <div>
                      {/* Card Header: Avatar, Name, Category Badge */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                          {/* Avatar with Halo */}
                          <div 
                            onClick={() => setEditingAvatarManifesto(manifesto)}
                            title="Clicca per cambiare avatar"
                            style={{
                              width: '52px',
                              height: '52px',
                              borderRadius: '50%',
                              overflow: 'hidden',
                              border: `2px solid ${domainColor}`,
                              boxShadow: `0 0 16px ${domainColor}50`,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              background: '#0a0d14',
                              flexShrink: 0,
                              cursor: 'pointer',
                              position: 'relative'
                            }}
                          >
                            <img 
                              src={manifesto.image || '/images/default.png'} 
                              alt={manifesto.name}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={e => { e.target.src = '/images/default.png'; }}
                            />
                          </div>

                          <div>
                            <h3 style={{ margin: '0 0 2px 0', fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
                              {manifesto.name}
                            </h3>
                            <span style={{ fontSize: '0.75rem', color: domainColor, fontWeight: 700 }}>
                              {manifesto.role}
                            </span>
                          </div>
                        </div>

                        {/* Category Pill */}
                        <span style={{
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: `${domainColor}15`,
                          border: `1px solid ${domainColor}40`,
                          color: domainColor,
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          textTransform: 'uppercase'
                        }}>
                          {manifesto.category}
                        </span>
                      </div>

                      {/* Description Excerpt */}
                      <p style={{ fontSize: '0.84rem', color: '#a0aec0', lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {manifesto.description || 'Nessuna descrizione disponibile.'}
                      </p>

                      {/* Parameter Badges Row */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          color: '#e2e8f0',
                          fontSize: '0.72rem',
                          fontWeight: 700
                        }}>
                          <Cpu size={12} style={{ color: '#00d2ff' }} /> Modello: <strong>{manifesto.baseModel || 'sigma'}</strong>
                        </span>

                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          color: '#e2e8f0',
                          fontSize: '0.72rem',
                          fontWeight: 700
                        }}>
                          <Sliders size={12} style={{ color: '#bc8cff' }} /> Temp: <strong>{manifesto.temperature ?? 0.2}</strong>
                        </span>

                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 10px',
                          borderRadius: '8px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          color: '#e2e8f0',
                          fontSize: '0.72rem',
                          fontWeight: 700
                        }}>
                          <Box size={12} style={{ color: '#3fb950' }} /> Ctx: <strong>{manifesto.numCtx ? `${Math.round(manifesto.numCtx / 1024)}k` : '32k'}</strong>
                        </span>
                      </div>

                      {/* Capabilities Chips */}
                      {manifesto.capabilities && manifesto.capabilities.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
                          {manifesto.capabilities.map(cap => (
                            <span
                              key={cap}
                              style={{
                                padding: '2px 8px',
                                borderRadius: '6px',
                                background: 'rgba(255, 255, 255, 0.04)',
                                border: '1px solid rgba(255, 255, 255, 0.06)',
                                color: '#cbd5e0',
                                fontSize: '0.68rem',
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
                      borderTop: '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '14px',
                      gap: '8px',
                      flexWrap: 'wrap'
                    }}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => setInspectManifesto(manifesto)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 255, 255, 0.15)',
                            color: '#e2e8f0',
                            fontSize: '0.76rem',
                            fontWeight: 700,
                            cursor: 'pointer'
                          }}
                        >
                          <ScrollText size={13} /> Modelfile
                        </button>

                        <button
                          onClick={() => handleEditManifesto(manifesto)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 255, 255, 0.15)',
                            color: '#e2e8f0',
                            fontSize: '0.76rem',
                            fontWeight: 700,
                            cursor: 'pointer'
                          }}
                        >
                          <Edit3 size={13} /> Modifica
                        </button>
                      </div>

                      <button
                        onClick={() => handleLaunchChat(manifesto)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '8px',
                          background: `linear-gradient(135deg, ${domainColor} 0%, #7c5bf0 100%)`,
                          border: 'none',
                          color: '#fff',
                          fontSize: '0.78rem',
                          fontWeight: 800,
                          cursor: 'pointer',
                          boxShadow: `0 2px 10px ${domainColor}40`,
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <MessageSquare size={13} /> Avvia Chat <ArrowRight size={12} />
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
              borderRadius: '16px',
              background: 'rgba(188, 140, 255, 0.05)',
              border: '1px solid rgba(188, 140, 255, 0.2)',
              padding: '24px',
              marginBottom: '28px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '18px' }}>
                <div>
                  <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 6px 0', color: '#fff' }}>
                    🌐 Repository GitHub Manifesti Professioni
                  </h2>
                  <p style={{ fontSize: '0.82rem', color: '#a0aec0', margin: 0 }}>
                    Pacchetti di manifesti e istruzioni specialistiche per studenti (universitari e liceali) e professionisti adulti.
                  </p>
                </div>

                <a
                  href="https://github.com/Sigmanih/SigmaStudio-Manifesti"
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#bc8cff',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    textDecoration: 'none'
                  }}
                >
                  <ExternalLink size={14} /> Repository GitHub Ufficiale
                </a>
              </div>

              {/* Custom Git Raw URL Importer */}
              <div style={{
                display: 'flex',
                gap: '12px',
                alignItems: 'center',
                flexWrap: 'wrap',
                background: 'rgba(0,0,0,0.3)',
                padding: '12px 16px',
                borderRadius: '10px'
              }}>
                <div style={{ flex: 2, minWidth: '240px' }}>
                  <input
                    type="text"
                    placeholder="URL Raw GitHub o Git (.md)..."
                    value={customImportUrl}
                    onChange={e => setCustomImportUrl(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.82rem' }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: '160px' }}>
                  <input
                    type="text"
                    placeholder="Nome file (opzionale)..."
                    value={customImportName}
                    onChange={e => setCustomImportName(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.82rem' }}
                  />
                </div>
                <button
                  onClick={handleCustomImport}
                  disabled={importingCustom || !customImportUrl.trim()}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '6px',
                    background: '#bc8cff',
                    border: 'none',
                    color: '#0a0d14',
                    fontWeight: 800,
                    fontSize: '0.82rem',
                    cursor: (importingCustom || !customImportUrl.trim()) ? 'not-allowed' : 'pointer'
                  }}
                >
                  {importingCustom ? 'Importazione...' : '📥 Importa da URL'}
                </button>
              </div>
            </div>

            {/* Hub Filters & Search */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
              marginBottom: '28px'
            }}>
              {/* Category Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {hubCategories.map(cat => {
                  const active = hubCategory === cat;
                  return (
                    <button
                      key={cat}
                      onClick={() => setHubCategory(cat)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '10px',
                        background: active ? '#bc8cff' : 'rgba(255,255,255,0.04)',
                        color: active ? '#0a0d14' : '#e2e8f0',
                        border: active ? '1px solid #bc8cff' : '1px solid rgba(255,255,255,0.1)',
                        fontWeight: 700,
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      {cat} {cat === 'Tutti' ? `(${hubCatalog.length})` : ''}
                    </button>
                  );
                })}
              </div>

              {/* Hub Search Box */}
              <div style={{ position: 'relative', width: '320px' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#8892b0' }} />
                <input
                  type="text"
                  placeholder="Cerca professione o competenza..."
                  value={hubSearchQuery}
                  onChange={e => setHubSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 16px 10px 38px',
                    borderRadius: '10px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: '0.85rem',
                    outline: 'none',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
            </div>

            {/* Hub Catalog Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
              gap: '24px'
            }}>
              {filteredHubCatalog.map(item => {
                const domainColor = item.domainColor || '#00d2ff';
                const isInstalling = installingId === item.id;

                return (
                  <div
                    key={item.id}
                    style={{
                      borderRadius: '18px',
                      background: 'rgba(255, 255, 255, 0.025)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      padding: '24px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      position: 'relative',
                      boxShadow: '0 4px 24px rgba(0,0,0,0.3)'
                    }}
                  >
                    <div>
                      {/* Card Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                        <div>
                          <h3 style={{ margin: '0 0 2px 0', fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
                            {item.name}
                          </h3>
                          <span style={{ fontSize: '0.78rem', color: domainColor, fontWeight: 700 }}>
                            {item.role}
                          </span>
                        </div>

                        <span style={{
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: `${domainColor}15`,
                          border: `1px solid ${domainColor}40`,
                          color: domainColor,
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          textTransform: 'uppercase'
                        }}>
                          {item.category}
                        </span>
                      </div>

                      {/* Target Audience Badge */}
                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        color: '#cbd5e0',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        marginBottom: '14px'
                      }}>
                        <Users size={13} style={{ color: '#bc8cff' }} /> Target: {item.target}
                      </div>

                      {/* Description */}
                      <p style={{ fontSize: '0.84rem', color: '#a0aec0', lineHeight: 1.5, margin: '0 0 16px 0' }}>
                        {item.description}
                      </p>

                      {/* Capabilities Chips */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
                        {item.capabilities.map(cap => (
                          <span
                            key={cap}
                            style={{
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'rgba(255, 255, 255, 0.04)',
                              border: '1px solid rgba(255, 255, 255, 0.06)',
                              color: '#cbd5e0',
                              fontSize: '0.68rem',
                              fontWeight: 600
                            }}
                          >
                            #{cap}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Footer Actions */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderTop: '1px solid rgba(255,255,255,0.06)',
                      paddingTop: '14px'
                    }}>
                      <span style={{ fontSize: '0.72rem', color: '#8892b0' }}>
                        Modelfile: <code>{item.filename}</code>
                      </span>

                      {item.installed ? (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            background: 'rgba(63, 185, 80, 0.15)',
                            border: '1px solid rgba(63, 185, 80, 0.4)',
                            color: '#3fb950',
                            fontSize: '0.75rem',
                            fontWeight: 700
                          }}>
                            <Check size={13} /> Installato
                          </span>

                          <button
                            onClick={() => handleLaunchChat(item)}
                            style={{
                              padding: '6px 12px',
                              borderRadius: '8px',
                              background: '#00d2ff',
                              border: 'none',
                              color: '#0a0d14',
                              fontSize: '0.76rem',
                              fontWeight: 800,
                              cursor: 'pointer'
                            }}
                          >
                            Avvia Chat
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleInstallFromHub(item)}
                          disabled={isInstalling}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '6px 16px',
                            borderRadius: '8px',
                            background: 'linear-gradient(135deg, #bc8cff 0%, #7c5bf0 100%)',
                            border: 'none',
                            color: '#fff',
                            fontSize: '0.78rem',
                            fontWeight: 800,
                            cursor: isInstalling ? 'not-allowed' : 'pointer',
                            boxShadow: '0 2px 12px rgba(188, 140, 255, 0.3)'
                          }}
                        >
                          <Download size={13} /> {isInstalling ? 'Installazione...' : 'Installa nel Kernel'}
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
          background: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: '#0d1117',
            border: '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '850px',
            width: '100%',
            maxHeight: '85vh',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
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
                  border: `2px solid ${inspectManifesto.domainColor || '#00d2ff'}`
                }}>
                  <img src={inspectManifesto.image || '/images/default.png'} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
                    {inspectManifesto.name}
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: inspectManifesto.domainColor || '#00d2ff', fontWeight: 700 }}>
                    {inspectManifesto.role} • <code>{inspectManifesto.filename}</code>
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
                    background: copied ? 'rgba(63, 185, 80, 0.2)' : 'rgba(255,255,255,0.08)',
                    border: copied ? '1px solid #3fb950' : '1px solid rgba(255,255,255,0.15)',
                    color: copied ? '#3fb950' : '#fff',
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
                    color: '#a0aec0',
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
                <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '0.68rem', color: '#8892b0', textTransform: 'uppercase' }}>Modello Base</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>{inspectManifesto.baseModel || 'sigma'}</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '0.68rem', color: '#8892b0', textTransform: 'uppercase' }}>Temperatura</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>{inspectManifesto.temperature}</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '0.68rem', color: '#8892b0', textTransform: 'uppercase' }}>Finestra Contesto</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#bc8cff', marginTop: '2px' }}>{inspectManifesto.numCtx} tokens</div>
                </div>
                <div style={{ padding: '12px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '0.68rem', color: '#8892b0', textTransform: 'uppercase' }}>Top-P / Repeat Penalty</div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#3fb950', marginTop: '2px' }}>{inspectManifesto.topP} / 1.1</div>
                </div>
              </div>

              {/* Raw Modelfile Syntax Box */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#00d2ff', fontSize: '0.85rem', fontWeight: 700, marginBottom: '8px' }}>
                  <Terminal size={14} /> Contenuto Modelfile Markdown
                </div>
                <pre style={{
                  background: '#080a0f',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  padding: '16px',
                  fontFamily: 'monospace',
                  fontSize: '0.8rem',
                  color: '#38bdf8',
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
              borderTop: '1px solid rgba(255,255,255,0.08)',
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
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: '#fff',
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
                  background: '#00d2ff',
                  border: 'none',
                  color: '#0a0d14',
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
          background: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: '#0d1117',
            border: '1px solid rgba(0, 210, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '500px',
            width: '100%',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                Seleziona Avatar per {editingAvatarManifesto.name}
              </h3>
              <button onClick={() => setEditingAvatarManifesto(null)} style={{ background: 'transparent', border: 'none', color: '#8892b0', cursor: 'pointer' }}>
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
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
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
                  <span style={{ fontSize: '0.72rem', color: '#cbd5e0', textAlign: 'center', fontWeight: 600 }}>{preset.label}</span>
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
          background: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px'
        }}>
          <div style={{
            background: '#0d1117',
            border: '1px solid rgba(188, 140, 255, 0.3)',
            borderRadius: '20px',
            maxWidth: '650px',
            width: '100%',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Sparkles size={18} style={{ color: '#bc8cff' }} />
                <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                  Crea Nuovo Manifesto Modelfile
                </h3>
              </div>
              <button onClick={() => setNewManifestoModalOpen(false)} style={{ background: 'transparent', border: 'none', color: '#8892b0', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {formError && (
                <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(255, 80, 100, 0.15)', border: '1px solid #ff5064', color: '#ff5064', fontSize: '0.82rem', fontWeight: 700 }}>
                  {formError}
                </div>
              )}

              <div>
                <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Nome File Manifesto (.md)</label>
                <input
                  type="text"
                  placeholder="es. quantum_physicist.md"
                  value={newFileName}
                  onChange={e => setNewFileName(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                <div>
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Ruolo Specializzato</label>
                  <input
                    type="text"
                    placeholder="es. Quantum Physicist"
                    value={newRole}
                    onChange={e => setNewRole(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Categoria / Dominio</label>
                  <select
                    value={newCategory}
                    onChange={e => setNewCategory(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: '#0a0d14', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
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
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Modello Base</label>
                  <input
                    type="text"
                    value={newBaseModel}
                    onChange={e => setNewBaseModel(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Temperatura</label>
                  <input
                    type="text"
                    value={newTemp}
                    onChange={e => setNewTemp(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Contesto</label>
                  <input
                    type="text"
                    value={newCtx}
                    onChange={e => setNewCtx(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.78rem', color: '#cbd5e0', fontWeight: 700, marginBottom: '6px', display: 'block' }}>Istruzione di Sistema / Descrizione Missione</label>
                <textarea
                  rows={4}
                  placeholder="Descrivi la missione dell'agente..."
                  value={newPrompt}
                  onChange={e => setNewPrompt(e.target.value)}
                  style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', fontSize: '0.85rem', resize: 'vertical' }}
                />
              </div>
            </div>

            <div style={{ padding: '16px 24px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setNewManifestoModalOpen(false)}
                style={{ padding: '8px 16px', borderRadius: '8px', background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#a0aec0', cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button
                onClick={handleCreateManifesto}
                disabled={creating}
                style={{ padding: '8px 18px', borderRadius: '8px', background: 'linear-gradient(135deg, #bc8cff 0%, #7c5bf0 100%)', border: 'none', color: '#fff', fontWeight: 800, cursor: creating ? 'not-allowed' : 'pointer' }}
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