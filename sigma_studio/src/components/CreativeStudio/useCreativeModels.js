import { useCallback, useEffect, useState } from 'react';

/**
 * Registro modelli + inventario reale del backend locale.
 *
 * Il registro dice *cosa esiste concettualmente* (FLUX, Qwen-Image, SDXL...),
 * la discovery dice *cosa è davvero installato* su questo ComfyUI. La UI ha
 * bisogno di entrambi: senza il primo non sa cosa proporre, senza il secondo
 * propone modelli che poi non partono.
 */
export function useCreativeModels() {
  const [models, setModels] = useState([]);
  const [inventory, setInventory] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    return Promise.all([
      fetch('/api/creative/models').then(r => r.json()).catch(() => ({})),
      fetch('/api/creative/backends/discover').then(r => r.json()).catch(() => ({})),
    ]).then(([reg, disc]) => {
      if (reg.success) setModels(reg.models || []);
      if (disc.success) setInventory(disc.comfyui || null);
      setLoading(false);
    });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const modelsFor = useCallback(
    (task) => models.filter(m => m.tasks.includes(task)),
    [models],
  );

  return { models, modelsFor, inventory, loading, refresh };
}
