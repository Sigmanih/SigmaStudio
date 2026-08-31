import { useState, useCallback, useEffect, useRef } from 'react';

// ==============================================================================
// useTabs Hook | Open, close, manage tabs
// ==============================================================================

//: Nomi leggibili per le schede aperte da URL. Chi non compare qui riceve il
//: proprio tipo come titolo: e' brutto ma corretto, e non richiede di
//: aggiornare questa mappa ogni volta che nasce un modulo.
const TITOLI_DA_URL = {
  home: 'Home',
  chat: 'Chat',
  model_hub: 'Modelli',
  ai_config: 'Providers',
  config: 'Providers',
  marketplace: 'Skills',
  whitepapers_lib: 'Ruoli AI',
  whitepaper: 'Ruoli AI',
  mcp_hub: 'MCP Tools',
  account: 'Impostazioni',
  settings: 'Impostazioni',
  creative_studio: 'Creative',
  domotica: 'Domotica',
  music: 'Musica',
  audio_studio: 'Musica',
  training_lab: 'Training',
  research_lab: 'Pipelines',
  knowledge: 'Argomenti',
  developer_studio: 'Developer Sigma',
  developer_lab: 'Developer Sigma',
  hardware_lab: 'Monitor Hardware',
  network_lab: 'AI Web Browser',
  sigma_network: 'Sigma Network',
  roadmap: 'Pianificazione & Task',
  voice_studio: 'Voice Studio',
  email_client: 'Email Hub',
  messaging_hub: 'Messaging Hub',
};

export function useTabs() {
  const [openTabs, setOpenTabs] = useState([]);
  const [activeTabId, setActiveTabId] = useState(null);

  const openTab = useCallback((item, type) => {
    // Singleton types (no path needed — one tab per type)
    const SINGLETON_TYPES = ['chat', 'research_lab', 'training_lab', 'hardware_lab', 'roadmap', 'whitepapers_lib', 'knowledge', 'mappa_argomenti', 'account', 'marketplace'];
    const tabId = SINGLETON_TYPES.includes(type)
      ? `${type}-singleton`
      : `${type}-${item.path || item.folder || item.name || type}`;
    setOpenTabs(prev => {
      if (prev.find(t => t.id === tabId)) return prev;
      return [...prev, {
        id: tabId,
        name: item.filename || item.name || `Mod ${item.number}`,
        type,
        path: item.path,
        folder: item.folder
      }];
    });
    setActiveTabId(tabId);
  }, []);

  // Apertura da URL: ?tab=sigma_network apre quella scheda al primo render.
  // Il ref impedisce che un cambio di dipendenze la riapra dopo che l'utente
  // l'ha chiusa, cosa che renderebbe impossibile chiuderla.
  const deepLinkFatto = useRef(false);
  useEffect(() => {
    if (deepLinkFatto.current) return;
    deepLinkFatto.current = true;
    try {
      const richiesta = new URLSearchParams(window.location.search).get('tab');
      if (!richiesta) return;
      const tipo = richiesta.trim();
      if (!/^[a-z0-9_]+$/i.test(tipo)) return;   // solo tipi plausibili
      openTab({ name: TITOLI_DA_URL[tipo] || tipo }, tipo);
    } catch (e) {
      // Un URL malformato non deve impedire l'avvio dell'applicazione.
    }
  }, [openTab]);


  const removeTab = useCallback((id) => {
    setOpenTabs(prev => {
      const newTabs = prev.filter(t => t.id !== id);
      if (activeTabId === id && newTabs.length > 0) {
        setActiveTabId(newTabs[newTabs.length - 1].id);
      } else if (newTabs.length === 0) {
        setActiveTabId(null);
      }
      return newTabs;
    });
  }, [activeTabId]);

  const closeTab = useCallback((e, id) => {
    e?.stopPropagation();
    removeTab(id);
  }, [removeTab]);

  const closeAllTabs = useCallback(() => {
    setOpenTabs([]);
    setActiveTabId(null);
  }, []);

  const handleDirtyChange = useCallback((id, dirty) => {
    setOpenTabs(prev => prev.map(t =>
      (t.id === id && t.isDirty !== dirty) ? { ...t, isDirty: dirty } : t
    ));
  }, []);

  const handleFileDelete = useCallback((id) => {
    removeTab(id);
  }, [removeTab]);

  return {
    openTabs, setOpenTabs,
    activeTabId, setActiveTabId,
    openTab, closeTab, closeAllTabs, removeTab,
    handleDirtyChange, handleFileDelete
  };
}