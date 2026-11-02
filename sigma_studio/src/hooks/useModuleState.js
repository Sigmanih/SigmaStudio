import { useState, useEffect, useCallback } from 'react';
import { loadLocalModules } from '../services/moduleCatalog';

export function useModuleState() {
  const [snapshot, setSnapshot] = useState({ modulesState: {}, moduleCatalog: [], isLoaded: false, error: '' });
  const fetchState = useCallback(async () => {
    try {
      const data = await loadLocalModules();
      setSnapshot({ modulesState: data.modules_state, moduleCatalog: data.modules, isLoaded: true, error: '' });
    } catch (error) {
      setSnapshot(previous => ({ ...previous, isLoaded: true, error: error.message }));
    }
  }, []);

  useEffect(() => {
    fetchState();
    window.addEventListener('sigma_modules_updated', fetchState);
    return () => window.removeEventListener('sigma_modules_updated', fetchState);
  }, [fetchState]);

  return { ...snapshot, refetch: fetchState };
}
