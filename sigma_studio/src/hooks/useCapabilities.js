import { useState, useEffect, useCallback } from 'react';

let pending;
function requestSkills() {
  if (!pending) pending = fetch('/api/skills', { signal: AbortSignal.timeout(10000) }).then(async response => {
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || 'Capacità non disponibili');
    return data.skills || [];
  }).finally(() => { pending = null; });
  return pending;
}

export function useCapabilities() {
  const [state, setState] = useState({ skills: [], loading: true, error: '' });
  const reload = useCallback(async () => {
    try { setState({ skills: await requestSkills(), loading: false, error: '' }); }
    catch (error) { setState(prev => ({ ...prev, loading: false, error: error.message })); }
  }, []);
  useEffect(() => {
    reload();
    window.addEventListener('sigma_skills_updated', reload);
    window.addEventListener('sigma_modules_updated', reload);
    return () => {
      window.removeEventListener('sigma_skills_updated', reload);
      window.removeEventListener('sigma_modules_updated', reload);
    };
  }, [reload]);
  return { ...state, reload };
}
