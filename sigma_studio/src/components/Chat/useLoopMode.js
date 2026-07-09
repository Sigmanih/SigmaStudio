// ==============================================================================
// useLoopMode.js — Custom hook for autonomous loop mode (SSE streaming)
// Sigma Studio v7.1 — Progressive iteration display via Server-Sent Events
// ==============================================================================
import { useState, useCallback, useRef, useEffect } from 'react';
import { getModelRoutingInfo } from './modelProviderMap';

export default function useLoopMode({
  selectedModel,
  providerConfigs,
  quickConfig,
  activeMode,
  sessionId,
  sessionMessages,
  setMessagesForSession,
  saveMessagesImmediately,
  refreshConfig,
  setLoading,
}) {
  const [loopActive, setLoopActive] = useState(false);
  const [loopIteration, setLoopIteration] = useState(0);
  const [loopMaxIterations, setLoopMaxIterations] = useState(5);
  const [loopError, setLoopError] = useState(null);

  const abortRef = useRef(null);

  // Refs for fresh closure access
  const loopActiveRef = useRef(false);
  const loopIterationRef = useRef(0);
  const loopMaxIterationsRef = useRef(5);

  useEffect(() => { loopActiveRef.current = loopActive; }, [loopActive]);
  useEffect(() => { loopIterationRef.current = loopIteration; }, [loopIteration]);
  useEffect(() => { loopMaxIterationsRef.current = loopMaxIterations; }, [loopMaxIterations]);

  // Build context from session messages
  const buildHistoryContext = useCallback((msgs) => {
    return msgs.slice(-15).map(m => ({
      role: m.role,
      content: m.content,
    }));
  }, []);

  // Start the server-side loop with SSE streaming
  const startLoop = useCallback(async (message) => {
    if (!message || !message.trim()) return;
    if (loopActiveRef.current) return;

    await refreshConfig();

    // Own the loading state completely
    if (setLoading) setLoading(true);

    setLoopActive(true);
    setLoopIteration(0);
    setLoopError(null);

    loopActiveRef.current = true;
    loopIterationRef.current = 0;

    const controller = new AbortController();
    abortRef.current = controller;

    // Add user message + loop start indicator in a single atomic state update
    const userMsg = {
      role: 'user',
      content: message.trim(),
      timestamp: new Date().toISOString(),
      agentName: selectedModel,
    };
    const startMsg = {
      role: 'system',
      content: `🔄 **Loop autonomo avviato** (max ${loopMaxIterationsRef.current} iterazioni)\n➡️ In esecuzione...`,
      timestamp: new Date().toISOString(),
      isAction: true,
    };
    // Atomic: get current messages, append user + start, set in one shot
    const sid = sessionId;
    const currentMsgs = sessionMessages || [];
    const initialMsgs = [...currentMsgs, userMsg, startMsg];
    setMessagesForSession(sid, initialMsgs);
    saveMessagesImmediately(sid, initialMsgs);

    // Reference to track cumulative messages for the session during this loop
    let cumulativeMsgs = [...initialMsgs];

    try {
      const routing = getModelRoutingInfo(selectedModel, providerConfigs);
      const history = buildHistoryContext(currentMsgs);

      const res = await fetch('/api/chat/loop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message.trim(),
          session_id: sid,
          bot_name: selectedModel,
          model: selectedModel,
          model_provider: routing.provider,
          model_endpoint: routing.endpoint,
          model_api_url: routing.api_url,
          mode: activeMode,
          loop_max_iterations: loopMaxIterationsRef.current,
          stream: true,  // SSE streaming
          timeout: quickConfig?.timeout || 300,
          context: {
            open_files: [],
            history: history,
          },
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `Server error ${res.status}`);
      }

      // --- SSE streaming reader ---
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamDone = false;
      let firstEventReceived = false;

      // Safety timeout: only active after first event received (60s after last event)
      let lastEventTime = Date.now();
      const safetyTimer = setInterval(() => {
        if (firstEventReceived && Date.now() - lastEventTime > 60000) {
          reader.cancel('timeout').catch(() => {});
          streamDone = true;
        }
      }, 5000);

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) { streamDone = true; break; }
        lastEventTime = Date.now();
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') { streamDone = true; break; }
            try {
              const event = JSON.parse(payload);

              if (event.type === 'error') {
                setLoopError(event.error);
                cumulativeMsgs.push({
                  role: 'system',
                  content: `⚠️ **Errore:** ${event.error}`,
                  timestamp: new Date().toISOString(),
                  isAction: true,
                  error: true,
                });
                setMessagesForSession(sid, cumulativeMsgs);
                saveMessagesImmediately(sid, cumulativeMsgs);
                break;
              }

              if (event.type === 'iteration_complete') {
                firstEventReceived = true;
                // Update iteration counter
                setLoopIteration(event.iteration);
                loopIterationRef.current = event.iteration;

                // Add iteration label
                const iterLabel = {
                  role: 'system',
                  content: `🔄 **Iterazione ${event.iteration + 1}/${event.max_iterations}**` +
                    (event.quality_score ? ` — Quality: ${event.quality_score}/10` : ''),
                  timestamp: new Date().toISOString(),
                  isAction: true,
                };
                cumulativeMsgs.push(iterLabel);

                // The iteration response is sent as a separate SSE event (see below)
                // We'll process it when we receive the "response" field
                if (event.response) {
                  cumulativeMsgs.push({
                    role: 'assistant',
                    content: event.response,
                    thinking: event.thinking || null,
                    timestamp: new Date().toISOString(),
                    agentName: selectedModel,
                  });
                }

                // Add actions log if present
                if (event.actions_log && event.actions_log.length > 0) {
                  const logStr = event.actions_log
                    .map(a => `  ${a.success ? '✅' : '❌'} ${a.type}: ${a.message || a.error}`)
                    .join('\n');
                  cumulativeMsgs.push({
                    role: 'system',
                    content: `📋 **Azioni eseguite:**\n\`\`\`\n${logStr}\n\`\`\``,
                    timestamp: new Date().toISOString(),
                    isAction: true,
                  });
                }

                // Add test results if present
                if (event.test_results && event.test_results.length > 0) {
                  const passed = event.test_results.filter(t => t.passed).length;
                  const total = event.test_results.length;
                  cumulativeMsgs.push({
                    role: 'system',
                    content: `🧪 **Test:** ${passed}/${total} passati`,
                    timestamp: new Date().toISOString(),
                    isAction: true,
                  });
                }

                // Push updated cumulative messages to UI
                setMessagesForSession(sid, [...cumulativeMsgs]);
                saveMessagesImmediately(sid, cumulativeMsgs);
              }

              if (event.type === 'done') {
                // Loop completed — add final summary
                const s = event.summary || {};
                const summary = [
                  '',
                  `## ✅ Loop completato`,
                  '',
                  `- **Iterazioni completate:** ${s.iterations_completed || '?'}/${s.max_iterations || '?'}`,
                  `- **Quality Score finale:** ${s.final_quality_score || 'N/D'}/10`,
                  `- **Motivo terminazione:** ${s.termination_reason || 'Completato'}`,
                  `- **Fase finale:** ${s.current_phase || 'N/D'}`,
                  `- **Errori:** ${s.error_count || 0}`,
                  '',
                ].join('\n');
                const fullSummary = summary + (
                  s.files_created ? `\n**📄 File creati:** ${s.files_created}` : ''
                ) + (
                  s.test_results_summary ?
                    `\n**🧪 Test:** ${s.test_results_summary.passed || 0}/${s.test_results_summary.total || 0} passati` :
                    ''
                );

                cumulativeMsgs.push({
                  role: 'assistant',
                  content: fullSummary,
                  timestamp: new Date().toISOString(),
                  agentName: selectedModel,
                  isLoopSummary: true,
                });
                setMessagesForSession(sid, [...cumulativeMsgs]);
                saveMessagesImmediately(sid, cumulativeMsgs);
                setLoopIteration(s.max_iterations || loopMaxIterationsRef.current);
                break;
              }
            } catch (e) {
              // Skip malformed SSE lines
            }
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        cumulativeMsgs.push({
          role: 'system',
          content: `⏹️ **Loop fermato** (interrotto dall'utente)`,
          timestamp: new Date().toISOString(),
          isAction: true,
        });
        setMessagesForSession(sid, cumulativeMsgs);
        return;
      }
      setLoopError(e.message);
      cumulativeMsgs.push({
        role: 'assistant',
        content: `❌ **Errore nel loop:** ${e.message}`,
        timestamp: new Date().toISOString(),
        error: true,
      });
      setMessagesForSession(sid, cumulativeMsgs);
    } finally {
      setLoopActive(false);
      loopActiveRef.current = false;
      abortRef.current = null;
      if (setLoading) setLoading(false);
    }
  }, [
    selectedModel, providerConfigs, quickConfig, activeMode, sessionId,
    sessionMessages, setMessagesForSession, saveMessagesImmediately,
    refreshConfig, setLoading, buildHistoryContext,
  ]);

  // Stop the loop
  const stopLoop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoopActive(false);
    loopActiveRef.current = false;
    if (setLoading) setLoading(false);
  }, [setLoading]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      setLoopActive(false);
      loopActiveRef.current = false;
      if (abortRef.current) abortRef.current.abort();
      if (setLoading) setLoading(false);
    };
  }, [setLoading]);

  // Set max iterations
  const setMaxIterations = useCallback((n) => {
    setLoopMaxIterations(n);
    loopMaxIterationsRef.current = n;
  }, []);

  return {
    loopActive,
    loopIteration,
    loopMaxIterations,
    setLoopMaxIterations,
    loopError,
    startLoop,
    stopLoop,
  };
}