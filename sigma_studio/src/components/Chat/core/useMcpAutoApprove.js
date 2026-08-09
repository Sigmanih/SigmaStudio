import { useState, useEffect, useCallback } from 'react';

/**
 * L'interruttore "Auto Approve" della chat.
 *
 * Lo stato vive sul server, non qui: è la stessa impostazione che governa gli
 * strumenti quando li chiama un agente, quando li chiama la corsia veloce e
 * quando li lancia l'orchestratore. Tenerne una copia nel browser vorrebbe dire
 * avere due verità, e quella che conta sarebbe comunque l'altra.
 *
 * Per lo stesso motivo la casella in chat e quella nella tab MCP Tools mostrano
 * sempre lo stesso valore: sono due finestre sulla stessa impostazione.
 */
export function useMcpAutoApprove() {
  const [autoApprove, setAutoApprove] = useState(false);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/mcp/tools');
      if (!res.ok) return;
      const data = await res.json();
      setAutoApprove(!!data.auto_approve);
    } catch (err) {
      // L'hub MCP può non essere raggiungibile: la chat resta usabile e la
      // casella resta sul valore prudente.
      console.debug('Stato Auto Approve non leggibile:', err);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Riallineamento quando si torna sulla scheda: l'impostazione può essere
  // stata cambiata dalla tab MCP Tools nel frattempo.
  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refresh]);

  const update = useCallback(async (next) => {
    const previous = autoApprove;
    setAutoApprove(next);                    // risposta immediata al clic
    try {
      const res = await fetch('/api/mcp/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: next }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAutoApprove(!!data.auto_approve);   // l'ultima parola è del server
    } catch (err) {
      console.error('Cambio Auto Approve fallito:', err);
      setAutoApprove(previous);
    }
  }, [autoApprove]);

  return { mcpAutoApprove: autoApprove, setMcpAutoApprove: update, mcpAutoApproveReady: ready };
}
