import { useState, useCallback } from 'react';

// ==============================================================================
// useModules Hook | Fetch, create, update, delete modules
// ==============================================================================

export function useModules() {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchModules = useCallback(async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch('/api/modules', { signal: controller.signal });
      const data = await res.json();
      setModules(data.modules || []);
    } catch (e) {
      console.error("Fetch modules error:", e);
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }, []);

  const createModule = useCallback(async (data) => {
    try {
      const res = await fetch('/api/create_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const result = await res.json();
      if (result.success) {
        await fetchModules();
        return true;
      }
      return false;
    } catch (e) {
      console.error("Create module error:", e);
      return false;
    }
  }, [fetchModules]);

  const updateModule = useCallback(async (data, editingModule) => {
    try {
      const res = await fetch('/api/update_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, old_folder: editingModule.folder })
      });
      const result = await res.json();
      if (result.success) {
        await fetchModules();
        return true;
      }
      return false;
    } catch (e) {
      console.error("Update module error:", e);
      return false;
    }
  }, [fetchModules]);

  const deleteModule = useCallback(async (folder) => {
    try {
      const res = await fetch('/api/delete_module', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder })
      });
      const result = await res.json();
      if (result.success) {
        await fetchModules();
        return true;
      }
      return false;
    } catch (e) {
      console.error("Delete module error:", e);
      return false;
    }
  }, [fetchModules]);

  return { modules, setModules, loading, fetchModules, createModule, updateModule, deleteModule };
}