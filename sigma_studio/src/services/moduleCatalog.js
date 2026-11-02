let pendingRequest = null;

export function loadLocalModules() {
  if (!pendingRequest) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    pendingRequest = fetch('/api/modules/local', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Catalogo locale non disponibile (${response.status})`);
      const data = await response.json();
      if (!Array.isArray(data.modules) || !data.modules_state || typeof data.modules_state !== 'object' || Array.isArray(data.modules_state)) {
        throw new Error('Catalogo locale non valido');
      }
      return data;
    }).finally(() => { clearTimeout(timer); pendingRequest = null; });
  }
  return pendingRequest;
}
