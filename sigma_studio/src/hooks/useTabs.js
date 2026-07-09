import { useState, useCallback } from 'react';

// ==============================================================================
// useTabs Hook | Open, close, manage tabs
// ==============================================================================

export function useTabs() {
  const [openTabs, setOpenTabs] = useState([]);
  const [activeTabId, setActiveTabId] = useState(null);

  const openTab = useCallback((item, type) => {
    const tabId = `${type}-${item.path || item.folder}`;
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