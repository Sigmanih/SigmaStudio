import { useCallback, useState } from 'react';

/**
 * Client per le API creative.
 *
 * Gli endpoint pesanti rispondono in SSE (`text/event-stream`) e gli altri in
 * JSON: `runTask` gestisce entrambi i casi con lo stesso contratto, così i
 * pannelli non devono sapere quale forma userà il server.
 */
export function useCreativeApi() {
  const [busy, setBusy] = useState(null);   // { label, progress, message }
  const [error, setError] = useState(null);

  const runTask = useCallback(async (url, body, { label = 'Elaborazione', onEvent } = {}) => {
    setBusy({ label, progress: 5, message: 'Avvio...' });
    setError(null);
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok && !response.headers.get('content-type')?.includes('event-stream')) {
        let detail = `HTTP ${response.status}`;
        try { detail = (await response.json()).error || detail; } catch { /* body non JSON */ }
        throw new Error(detail);
      }

      if (response.headers.get('content-type')?.includes('application/json')) {
        const data = await response.json();
        if (data.success === false) throw new Error(data.error || 'Operazione fallita');
        return data;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let last = null;
      let failure = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ') || line === 'data: [DONE]') continue;
          let evt;
          try { evt = JSON.parse(line.slice(6)); } catch { continue; }
          onEvent?.(evt);
          if (evt.error) failure = evt.error;
          if (evt.progress !== undefined || evt.message) {
            setBusy(b => ({ ...(b || { label }), progress: evt.progress ?? b?.progress, message: evt.message || b?.message }));
          }
          if (evt.asset || evt.results) last = evt;
        }
      }

      if (failure) throw new Error(failure);
      return last || {};
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setBusy(null);
    }
  }, []);

  return { runTask, busy, error, clearError: () => setError(null) };
}
