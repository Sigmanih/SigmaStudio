// =============================================================================
// useMcpTool — wrapper generico per chiamate MCP con stati loading/error/success
// Timeout gestito, cancellazione su unmount.
// =============================================================================
import { useCallback, useEffect, useRef, useState } from 'react';

export type McpToolStatus = 'idle' | 'loading' | 'success' | 'error';

export interface UseMcpToolState<T> {
  status: McpToolStatus;
  data: T | null;
  error: string | null;
}

export interface UseMcpToolOptions {
  /** Timeout in millisecondi (default 15000). */
  timeoutMs?: number;
  /** Esegue automaticamente al mount. Default false. */
  autoRun?: boolean;
}

/**
 * Hook generico per eseguire una funzione MCP con gestione di stati e timeout.
 * @param fn - funzione asincrona che restituisce il dato (es. chiamata fetch MCP).
 * @param options - configurazione opzionale.
 */
export function useMcpTool<T>(
  fn: () => Promise<T>,
  options?: UseMcpToolOptions,
) {
  const timeoutMs = options?.timeoutMs ?? 15000;
  const autoRun = options?.autoRun ?? false;

  const [state, setState] = useState<UseMcpToolState<T>>({
    status: 'idle',
    data: null,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  // Pulizia su unmount: annulla timeout pendenti.
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, []);

  const execute = useCallback(async (...args: unknown[]) => {
    // Annulla eventuale esecuzione precedente.
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ status: 'loading', data: null, error: null });

    try {
      // Timeout wrapper.
      const timeoutPromise = new Promise<never>((_, reject) => {
        const timer = setTimeout(
          () => reject(new Error(`Timeout dopo ${timeoutMs}ms`)),
          timeoutMs,
        );
        controller.signal.addEventListener('abort', () => clearTimeout(timer));
      });

      const result = await Promise.race([fn(), timeoutPromise]);
      setState({ status: 'success', data: result, error: null });
      return result;
    } catch (err) {
      if (controller.signal.aborted) {
        // Annullato volontariamente: torna a idle.
        setState({ status: 'idle', data: null, error: null });
        return undefined as unknown as T;
      }
      const message = err instanceof Error ? err.message : String(err);
      setState({ status: 'error', data: null, error: message });
      throw err;
    }
  }, [fn, timeoutMs]);

  // Auto-run al mount se richiesto.
  useEffect(() => {
    if (autoRun) {
      execute();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setState({ status: 'idle', data: null, error: null });
  }, []);

  return { ...state, execute, reset };
}