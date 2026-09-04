import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Cpu, Brain, Code, ShieldCheck, CheckCircle, Palette, 
  Atom, FlaskConical, Award, Wand2, Wrench, MessageSquare, 
  Search, Filter, Play, Edit3, Image as ImageIcon, Copy, Check, 
  ExternalLink, Sparkles, Terminal, Layers, Plus, X, ArrowRight,
  Info, RefreshCw, ChevronRight, Sliders, Box, Download, Globe,
  Users, BookOpen, GraduationCap, Briefcase, HeartPulse, Scale, TrendingUp,
  Trash2, UserCheck, Star, Eye, ScrollText
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import TabHeader from '../common/TabHeader';

// ==============================================================================
// Icon Mapper for Dynamic Role Icons
// ==============================================================================
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
  
  // Selected Role for the Right Detail Pane
  const [selectedRole, setSelectedRole] = useState(null);

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
        // If no selected role or current selected role was deleted, default to the first one
        if (!selectedRole && data.manifesti.length > 0) {
          setSelectedRole(data.manifesti[0]);
        } else if (selectedRole) {
          const matched = data.manifesti.find(m => (m.id && m.id === selectedRole.id) || (m.path && m.path === selectedRole.path));
          if (matched) setSelectedRole(matched);
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

  // Update selected role if active list changes
  useEffect(() => {
    if (!selectedRole && filteredManifesti.length > 0) {
      setSelectedRole(filteredManifesti[0]);
    }
  }, [filteredManifesti, selectedRole]);

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

  // Open in SigmaLab Editor
  const handleEditManifesto = (manifesto) => {
    if (openTab && manifesto) {
      openTab({ 
        path: manifesto.path || `manifesti/${manifesto.filename}`, 
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
        if (selectedRole && (selectedRole.filename === filename || selectedRole.id === manifesto.id)) {
          setSelectedRole(null);
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

  // Avatar presets
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
      overflowY: 'auto'
    }}>
      {/* ── UNIFIED KERNEL TAB HEADER ──────── */}
      <TabHeader
        badge="Σ RUOLI AI & PROFILI COGNITIVI SPECIALISTICI"
        badgeIcon={Brain}
        icon={activeGalleryView === 'installed' ? UserCheck : Globe}
        title="Ruoli AI / "
        highlight={activeGalleryView === 'installed' ? `Ruoli Attivi nel Kernel (${manifestiList.length})` : 'Hub Professioni & Community'}
        description={
          activeGalleryView === 'installed'
            ? "I Ruoli AI applicano direttive deontologiche, competenze e parametri di campionamento al motore sigma, trasformando l'assistente in uno specialista verticale."
            : "Esplora, importa e sincronizza ruoli AI specializzati creati dalla community direttamente da GitHub."
        }
        bannerImage="/images/manifesti_gallery_banner.jpg"
        actions={
          <>
            <button
              onClick={() => setNewManifestoModalOpen(true)}
              className="sigma-tab-btn sigma-tab-btn-primary"
            >
              <Plus size={14} /> <span>Nuovo Ruolo AI</span>
            </button>

            <button
              onClick={() => { loadManifesti(); loadHubCatalog(); }}
              title="Ricarica Ruoli dal Kernel e da GitHub"
              className="sigma-tab-btn sigma-tab-btn-ghost"
            >
              <RefreshCw size={14} className={(loading || loadingHub) ? 'spin' : ''} />
              <span>Ricarica</span>
            </button>
          </>
        }
      />

      {/* ── CORPO PRINCIPALE IN DUAL-PANE LAYOUT ──────── */}
      <div style={{ padding: '20px 24px', width: '100%', boxSizing: 'border-box', flex: 1 }}>
        
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
        {/* DUAL-PANE CONTAINER (SINISTRA: LISTA RUOLI - DESTRA: RUOLO ASSOCIATO) */}
        {/* =================================================================== */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.35fr) minmax(360px, 0.95fr)',
          gap: '20px',
          alignItems: 'start'
        }}>
          
          {/* ── COLONNA SINISTRA: SELETTORE E GRIGLIA RUOLI ──────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', minWidth: 0 }}>
            
            {/* VIEW 1: RUOLI INSTALLATI NEL KERNEL */}
            {activeGalleryView === 'installed' && (
              <>
                {/* Categories Filter Pills & Search */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '10px'
                }}>
                  {/* Category Pills */}
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
                              : (isLight ? '#ffffff' : 'rgba(255,255,255,0.04)'),
                            color: active ? '#ffffff' : textPrimary,
                            border: active 
                              ? `1px solid ${isLight ? '#ea580c' : '#00d2ff'}` 
                              : (isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.1)'),
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
                  <div style={{ position: 'relative', width: '240px' }}>
                    <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: textMuted }} />
                    <input
                      type="text"
                      placeholder="Cerca ruolo o competenza..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '7px 12px 7px 32px',
                        borderRadius: '8px',
                        background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
                        border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.15)',
                        color: textPrimary,
                        fontSize: '0.78rem',
                        outline: 'none',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>

                {/* Role Cards Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                  gap: '12px'
                }}>
                  {filteredManifesti.map(manifesto => {
                    const domainColor = manifesto.domainColor || (isLight ? '#ea580c' : '#00d2ff');
                    const isSelected = selectedRole && ((selectedRole.id && selectedRole.id === manifesto.id) || (selectedRole.path && selectedRole.path === manifesto.path));

                    return (
                      <div
                        key={manifesto.path || manifesto.id}
                        onClick={() => setSelectedRole(manifesto)}
                        className="mg-card"
                        style={{
                          borderRadius: '16px',
                          background: isSelected 
                            ? (isLight ? 'rgba(234, 88, 12, 0.06)' : 'rgba(0, 210, 255, 0.07)')
                            : cardBg,
                          border: isSelected 
                            ? `2px solid ${isLight ? '#ea580c' : '#00d2ff'}` 
                            : cardBorder,
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          position: 'relative',
                          boxShadow: isSelected 
                            ? (isLight ? '0 6px 20px rgba(234, 88, 12, 0.2)' : '0 6px 24px rgba(0, 210, 255, 0.25)')
                            : cardShadow,
                          cursor: 'pointer',
                          transition: 'all 0.18s ease'
                        }}
                      >
                        <div>
                          {/* Card Header: Big Avatar (64px) + Titles */}
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '10px' }}>
                            {/* Avatar Immagine Più Grande */}
                            <div 
                              onClick={(e) => { e.stopPropagation(); setEditingAvatarManifesto(manifesto); }}
                              title="Clicca per cambiare avatar"
                              style={{
                                width: '60px',
                                height: '60px',
                                borderRadius: '14px',
                                overflow: 'hidden',
                                border: `2px solid ${domainColor}`,
                                boxShadow: isLight ? '0 4px 12px rgba(0,0,0,0.1)' : `0 0 14px ${domainColor}45`,
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
                                src={manifesto.image || '/images/default.png'} 
                                alt={manifesto.name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                onError={e => { e.target.src = '/images/default.png'; }}
                              />
                            </div>

                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                                <span style={{
                                  padding: '2px 6px',
                                  borderRadius: '5px',
                                  background: `${domainColor}18`,
                                  border: `1px solid ${domainColor}40`,
                                  color: domainColor,
                                  fontSize: '0.62rem',
                                  fontWeight: 800,
                                  textTransform: 'uppercase'
                                }}>
                                  {manifesto.category}
                                </span>

                                {isSelected && (
                                  <span style={{
                                    fontSize: '0.62rem',
                                    color: isLight ? '#ea580c' : '#00d2ff',
                                    fontWeight: 800,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '3px'
                                  }}>
                                    <Star size={10} fill="currentColor" /> Selezionato
                                  </span>
                                )}
                              </div>

                              <h3 style={{ margin: '4px 0 2px 0', fontSize: '0.94rem', fontWeight: 800, color: textPrimary, lineHeight: 1.3 }}>
                                {manifesto.name}
                              </h3>
                              <span style={{ fontSize: '0.74rem', color: isLight ? '#ea580c' : domainColor, fontWeight: 700, lineHeight: 1.35, display: 'block' }}>
                                {manifesto.role}
                              </span>
                            </div>
                          </div>

                          {/* Description Excerpt */}
                          <p style={{
                            fontSize: '0.74rem',
                            color: textSecondary,
                            lineHeight: 1.4,
                            margin: '0 0 10px 0',
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
                        </div>

                        {/* Card Action Buttons */}
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          borderTop: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.06)',
                          paddingTop: '10px',
                          gap: '6px'
                        }}>
                          <button
                            onClick={(e) => { e.stopPropagation(); setSelectedRole(manifesto); }}
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: '4px',
                              padding: '4px 8px', borderRadius: '6px',
                              background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.05)',
                              border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255, 255, 255, 0.15)',
                              color: textPrimary, fontSize: '0.70rem', fontWeight: 700, cursor: 'pointer'
                            }}
                            title="Visualizza dettagli a destra"
                          >
                            <Eye size={12} color={isLight ? '#ea580c' : '#00d2ff'} /> Dettagli
                          </button>

                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleEditManifesto(manifesto); }}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '4px',
                                padding: '4px 8px', borderRadius: '6px',
                                background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.05)',
                                border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255, 255, 255, 0.15)',
                                color: textPrimary, fontSize: '0.70rem', fontWeight: 700, cursor: 'pointer'
                              }}
                              title="Modifica istruzioni nel SigmaLab Editor"
                            >
                              <Edit3 size={11} />
                            </button>

                            <button
                              onClick={(e) => { e.stopPropagation(); handleLaunchChat(manifesto); }}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: '5px',
                                padding: '5px 12px', borderRadius: '6px',
                                background: isLight 
                                  ? 'linear-gradient(135deg, #ea580c 0%, #d97706 100%)' 
                                  : `linear-gradient(135deg, ${domainColor} 0%, #7c5bf0 100%)`,
                                border: 'none', color: '#fff',
                                fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                                boxShadow: isLight ? '0 2px 8px rgba(234, 88, 12, 0.25)' : `0 2px 8px ${domainColor}35`,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              <MessageSquare size={12} /> Chat <ArrowRight size={10} />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
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
                        display: 'inline-flex', alignItems: 'center', gap: '5px',
                        padding: '5px 10px', borderRadius: '6px',
                        background: isLight ? 'rgba(234, 88, 12, 0.12)' : 'rgba(255,255,255,0.06)',
                        border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(255,255,255,0.15)',
                        color: isLight ? '#c2410c' : '#bc8cff',
                        fontSize: '0.72rem', fontWeight: 700, textDecoration: 'none'
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

                {/* Hub Filters */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {hubCategories.map(cat => (
                      <button
                        key={cat}
                        onClick={() => setHubCategory(cat)}
                        style={{
                          padding: '5px 12px', borderRadius: '8px',
                          background: hubCategory === cat ? (isLight ? '#7c3aed' : '#a855f7') : (isLight ? '#ffffff' : 'rgba(255,255,255,0.04)'),
                          color: hubCategory === cat ? '#ffffff' : textPrimary,
                          border: hubCategory === cat ? '1px solid #7c3aed' : (isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.1)'),
                          fontWeight: 700, fontSize: '0.74rem', cursor: 'pointer'
                        }}
                      >
                        {cat} {cat === 'Tutti' ? `(${hubCatalog.length})` : ''}
                      </button>
                    ))}
                  </div>

                  <div style={{ position: 'relative', width: '240px' }}>
                    <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: textMuted }} />
                    <input
                      type="text"
                      placeholder="Cerca professione..."
                      value={hubSearchQuery}
                      onChange={e => setHubSearchQuery(e.target.value)}
                      style={{
                        width: '100%', padding: '7px 12px 7px 32px', borderRadius: '8px',
                        background: isLight ? '#ffffff' : 'rgba(255,255,255,0.04)',
                        border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.15)',
                        color: textPrimary, fontSize: '0.78rem', outline: 'none', boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>

                {/* Hub Cards Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                  {filteredHubCatalog.map(item => {
                    const domainColor = item.domainColor || (isLight ? '#7c3aed' : '#a855f7');
                    const isInstalling = installingId === item.id;
                    const isSelected = selectedRole && (selectedRole.id === item.id);

                    return (
                      <div
                        key={item.id}
                        onClick={() => setSelectedRole(item)}
                        className="mg-card"
                        style={{
                          borderRadius: '16px',
                          background: isSelected ? (isLight ? 'rgba(124, 58, 237, 0.08)' : 'rgba(168, 85, 247, 0.1)') : cardBg,
                          border: isSelected ? '2px solid #a855f7' : cardBorder,
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          boxShadow: cardShadow,
                          cursor: 'pointer'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <h3 style={{ margin: '0 0 2px 0', fontSize: '0.92rem', fontWeight: 800, color: textPrimary }}>
                                {item.name}
                              </h3>
                              <span style={{ fontSize: '0.74rem', color: domainColor, fontWeight: 700 }}>
                                {item.role}
                              </span>
                            </div>
                            <span style={{
                              padding: '2px 7px', borderRadius: '6px',
                              background: `${domainColor}15`, border: `1px solid ${domainColor}40`,
                              color: domainColor, fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase'
                            }}>
                              {item.category}
                            </span>
                          </div>

                          <div style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '2px 7px', borderRadius: '5px',
                            background: innerCardBg, border: innerCardBorder,
                            color: textPrimary, fontSize: '0.66rem', fontWeight: 700, marginBottom: '8px'
                          }}>
                            <Users size={11} style={{ color: domainColor }} /> Target: {item.target}
                          </div>

                          <p style={{ fontSize: '0.74rem', color: textSecondary, lineHeight: 1.35, margin: '0 0 8px 0', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {item.description}
                          </p>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
                          <button
                            onClick={(e) => { e.stopPropagation(); setSelectedRole(item); }}
                            style={{
                              padding: '4px 8px', borderRadius: '6px',
                              background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.05)',
                              border: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255, 255, 255, 0.15)',
                              color: textPrimary, fontSize: '0.70rem', fontWeight: 700, cursor: 'pointer'
                            }}
                          >
                            <Eye size={12} /> Dettagli
                          </button>

                          {item.installed ? (
                            <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <Check size={12} /> Già Installato
                            </span>
                          ) : (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleInstallFromHub(item); }}
                              disabled={isInstalling}
                              style={{
                                padding: '5px 12px', borderRadius: '6px',
                                background: 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)',
                                border: 'none', color: '#fff', fontSize: '0.74rem', fontWeight: 800, cursor: isInstalling ? 'not-allowed' : 'pointer'
                              }}
                            >
                              <Download size={12} /> {isInstalling ? 'Scaricamento...' : 'Scarica & Attiva'}
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

          {/* ── COLONNA DESTRA: PANNELLO DETTAGLIO RUOLO ASSOCIATO (STICKY) ──────── */}
          <div style={{
            position: 'sticky',
            top: '16px',
            borderRadius: '20px',
            background: isLight ? '#ffffff' : 'linear-gradient(135deg, #111522 0%, #0c0f1a 100%)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.35)' : '1px solid rgba(0, 210, 255, 0.35)',
            boxShadow: isLight ? '0 10px 30px rgba(0,0,0,0.08)' : '0 10px 40px rgba(0,0,0,0.6)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            minHeight: '480px'
          }}>
            {selectedRole ? (
              <>
                {/* Header Dettaglio Ruolo */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                  {/* Large Avatar */}
                  <div 
                    onClick={() => selectedRole.path && setEditingAvatarManifesto(selectedRole)}
                    title="Clicca per cambiare avatar"
                    style={{
                      width: '76px',
                      height: '76px',
                      borderRadius: '18px',
                      overflow: 'hidden',
                      border: `3px solid ${selectedRole.domainColor || (isLight ? '#ea580c' : '#00d2ff')}`,
                      boxShadow: isLight ? '0 6px 16px rgba(0,0,0,0.12)' : `0 0 20px ${(selectedRole.domainColor || '#00d2ff')}50`,
                      background: isLight ? '#f1f5f9' : '#080a10',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      cursor: selectedRole.path ? 'pointer' : 'default'
                    }}
                  >
                    <img 
                      src={selectedRole.image || '/images/default.png'} 
                      alt={selectedRole.name} 
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={e => { e.target.src = '/images/default.png'; }}
                    />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '6px',
                        background: `${selectedRole.domainColor || '#00d2ff'}20`,
                        border: `1px solid ${selectedRole.domainColor || '#00d2ff'}40`,
                        color: selectedRole.domainColor || (isLight ? '#ea580c' : '#00d2ff'),
                        fontSize: '0.66rem',
                        fontWeight: 800,
                        textTransform: 'uppercase'
                      }}>
                        {selectedRole.category || 'Specializzazione'}
                      </span>
                      {selectedRole.filename && (
                        <code style={{ fontSize: '0.68rem', color: textMuted }}>{selectedRole.filename}</code>
                      )}
                    </div>

                    <h2 style={{ margin: '0 0 3px 0', fontSize: '1.25rem', fontWeight: 800, color: textPrimary, letterSpacing: '-0.3px' }}>
                      {selectedRole.name}
                    </h2>
                    <span style={{ fontSize: '0.84rem', color: isLight ? '#ea580c' : (selectedRole.domainColor || '#00d2ff'), fontWeight: 700 }}>
                      {selectedRole.role}
                    </span>
                  </div>
                </div>

                {/* Primary Action Button: Launch Chat */}
                <button
                  onClick={() => handleLaunchChat(selectedRole)}
                  style={{
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: '12px',
                    background: isLight 
                      ? 'linear-gradient(135deg, #ea580c 0%, #f97316 100%)' 
                      : 'linear-gradient(135deg, #00d2ff 0%, #0077ff 100%)',
                    border: 'none',
                    color: '#ffffff',
                    fontWeight: 800,
                    fontSize: '0.90rem',
                    cursor: 'pointer',
                    boxShadow: isLight ? '0 4px 16px rgba(234, 88, 12, 0.35)' : '0 4px 20px rgba(0, 210, 255, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    transition: 'transform 0.15s ease'
                  }}
                >
                  <MessageSquare size={16} />
                  <span>Avvia Chat con {selectedRole.name}</span>
                  <ArrowRight size={14} />
                </button>

                {/* Parameters & Specs Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '8px',
                  background: innerCardBg,
                  border: innerCardBorder,
                  padding: '10px',
                  borderRadius: '12px'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>MODELLO BASE</div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 800, color: textPrimary, marginTop: '2px' }}>
                      {selectedRole.baseModel || 'sigma'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>TEMPERATURA</div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isLight ? '#ea580c' : '#00d2ff', marginTop: '2px' }}>
                      {selectedRole.temperature ?? 0.2}
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.62rem', color: textMuted, fontWeight: 700, textTransform: 'uppercase' }}>CONTESTO</div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#10b981', marginTop: '2px' }}>
                      {selectedRole.numCtx ? `${Math.round(selectedRole.numCtx / 1024)}k` : '32k'}
                    </div>
                  </div>
                </div>

                {/* System Prompt & Directive Preview */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '0.74rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <ScrollText size={13} color={isLight ? '#ea580c' : '#00d2ff'} />
                      <span>DIRETTIVE & PROMPT DI SISTEMA</span>
                    </div>
                    <button
                      onClick={() => handleCopyPrompt(extractSystemPrompt(selectedRole))}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: isLight ? '#ea580c' : '#00d2ff',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px'
                      }}
                    >
                      {copiedPrompt ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                      <span>{copiedPrompt ? 'Copiato!' : 'Copia Prompt'}</span>
                    </button>
                  </div>

                  <div style={{
                    padding: '12px',
                    borderRadius: '10px',
                    background: isLight ? '#f1f5f9' : '#07090e',
                    border: isLight ? '1px solid #e2e8f0' : '1px solid rgba(255,255,255,0.08)',
                    maxHeight: '160px',
                    overflowY: 'auto',
                    fontSize: '0.74rem',
                    lineHeight: 1.5,
                    color: textSecondary,
                    whiteSpace: 'pre-wrap'
                  }}>
                    {extractSystemPrompt(selectedRole)}
                  </div>
                </div>

                {/* Capabilities & Artifacts */}
                {selectedRole.capabilities && selectedRole.capabilities.length > 0 && (
                  <div>
                    <div style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', marginBottom: '6px' }}>
                      COMPETENZE E ARTIFACTS GENERATI
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {selectedRole.capabilities.map(cap => (
                        <span
                          key={cap}
                          style={{
                            padding: '2px 8px',
                            borderRadius: '5px',
                            background: innerCardBg,
                            border: innerCardBorder,
                            color: textPrimary,
                            fontSize: '0.68rem',
                            fontWeight: 700
                          }}
                        >
                          ✓ {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Secondary Actions Row */}
                <div style={{
                  display: 'flex',
                  gap: '8px',
                  alignItems: 'center',
                  borderTop: isLight ? '1px solid rgba(226, 232, 240, 0.9)' : '1px solid rgba(255,255,255,0.08)',
                  paddingTop: '12px',
                  marginTop: 'auto',
                  flexWrap: 'wrap'
                }}>
                  {selectedRole.path && (
                    <button
                      onClick={() => handleEditManifesto(selectedRole)}
                      style={{
                        flex: 1,
                        padding: '7px 12px',
                        borderRadius: '8px',
                        background: innerCardBg,
                        border: innerCardBorder,
                        color: textPrimary,
                        fontSize: '0.74rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '5px'
                      }}
                    >
                      <Edit3 size={13} /> Modifica Istruzioni
                    </button>
                  )}

                  <button
                    onClick={() => setInspectManifesto(selectedRole)}
                    style={{
                      padding: '7px 12px',
                      borderRadius: '8px',
                      background: innerCardBg,
                      border: innerCardBorder,
                      color: textPrimary,
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                    title="Ispeziona formato completo"
                  >
                    <Terminal size={13} /> Modelfile
                  </button>

                  {selectedRole.filename !== 'sigma_assistant.md' && selectedRole.id !== 'sigma_assistant' && selectedRole.path && (
                    <button
                      onClick={() => handleUninstallManifesto(selectedRole)}
                      disabled={uninstallingId === (selectedRole.id || selectedRole.filename)}
                      style={{
                        padding: '7px 10px',
                        borderRadius: '8px',
                        background: 'rgba(239, 68, 68, 0.12)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        color: '#ef4444',
                        fontSize: '0.74rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                      title="Disinstalla ruolo dal Kernel"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px', textAlign: 'center', color: textMuted }}>
                <Brain size={36} style={{ marginBottom: '12px', opacity: 0.5 }} />
                <h3 style={{ margin: '0 0 6px 0', fontSize: '0.98rem', fontWeight: 800, color: textPrimary }}>Nessun Ruolo Selezionato</h3>
                <p style={{ margin: 0, fontSize: '0.78rem' }}>Clicca su un ruolo nella lista a sinistra per visualizzarne i dettagli, il prompt e i parametri.</p>
              </div>
            )}
          </div>

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
                  <img src={inspectManifesto.image || '/images/default.png'} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
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
            maxWidth: '520px',
            width: '100%',
            boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
            padding: '24px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: textPrimary }}>
                🎨 Personalizza Avatar per {editingAvatarManifesto.name}
              </h3>
              <button onClick={() => setEditingAvatarManifesto(null)} style={{ background: 'transparent', border: 'none', color: textPrimary, cursor: 'pointer' }}><X size={18} /></button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '20px' }}>
              {AVATAR_PRESETS.map(av => (
                <div
                  key={av.path}
                  onClick={() => handleUpdateAvatar(editingAvatarManifesto, av.path)}
                  style={{
                    padding: '10px',
                    borderRadius: '12px',
                    background: innerCardBg,
                    border: editingAvatarManifesto.image === av.path ? '2px solid #00d2ff' : innerCardBorder,
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <div style={{ width: '56px', height: '56px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
                    <img src={av.path} alt={av.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: textPrimary, textAlign: 'center' }}>{av.label}</span>
                </div>
              ))}
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

    </div>
  );
}