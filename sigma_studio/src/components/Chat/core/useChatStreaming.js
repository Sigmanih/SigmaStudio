import { useState, useCallback, useRef, useEffect } from 'react';
import { MAX_ATTACHMENTS, createSession, MAX_HISTORY } from '../chatStorage';
import { getModelRoutingInfo } from '../modelProviderMap';
import { getAgentStyle } from '../AgentMessage';
import {
  speakAgentMessage, stopSpeech,
  startSpeechStream, pushSpeechStream, endSpeechStream,
} from '../audioSpeech';

let globalAbortController = null;

function appendAndSave(sid, msg, setFn) {
  setFn(prev => {
    const updated = [...(prev[sid] || []), msg];
    try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(updated)); } catch (e) {}
    return { ...prev, [sid]: updated };
  });
}

function cleanModelTags(text) {
  if (!text) return text;
  let cleaned = text;

  // 1. Remove XML thinking tags
  cleaned = cleaned.replace(/<(think|thinking|Thought|reasoning|Rationale|scratchpad)>[\s\S]*?<\/\1>/gi, '');
  // Unclosed reasoning block (stream cut short): drop it rather than render it.
  cleaned = cleaned.replace(/<(think|thinking|reasoning|scratchpad)>[\s\S]*$/gi, '');

  // 2. Remove "Here's a thinking process:" English self-analysis blocks
  cleaned = cleaned.replace(/^(?:We\s+need\s+to|We\s+must|Let'?s\s+craft|Here'?s\s+a\s+thinking\s+process|Analyze\s+User\s+Input|Determine\s+Output\s+Structure|Draft\s+Content|Self-Correction|Execution|Plan|Requirements\s+from\s+System\s+Prompt)[\s\S]*?(?=\n#|\nEcco|\n1️⃣|\n[A-ZÀ-Ü]|\n\{|\n\n|\Z)/gi, '');
  cleaned = cleaned.replace(/^(?:-\s*(?:Request|Language|Domain|Requirements|Identity|Rules|Structure):[^\n]*\n)+/gi, '');

  // 3. Extract "response" value if raw JSON object string was outputted by LLM
  if (cleaned.trim().startsWith('{') && cleaned.includes('"response"')) {
    try {
      const parsed = JSON.parse(cleaned.trim());
      if (parsed.response && typeof parsed.response === 'string') {
        cleaned = parsed.response;
      }
    } catch (e) {
      const match = cleaned.match(/"response"\s*:\s*"([\s\S]*?)"\s*,\s*"thinking"/);
      if (match && match[1]) {
        cleaned = match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
      }
    }
  }

  // 4. Remove meta-reasoning headers (e.g. "🧭 **Ragionamento e procedura operativa:**")
  cleaned = cleaned.replace(/^(?:🧭|🧠|🔍)?\s*\*\*Ragionamento\s+e\s+procedura\s+operativa[^*]*\*\*:[^\n]*\n(?:[0-9]+\.[^\n]*\n)*/gi, '');
  cleaned = cleaned.replace(/^(?:🧭|🧠|🔍)?\s*\*\*Ragionamento\s+passo-passo[^*]*\*\*:[^\n]*\n(?:[0-9]+\.[^\n]*\n)*/gi, '');

  // 5. Remove container tags and cleanup
  cleaned = cleaned.replace(/<\/?(response|Response|output|Output|answer|Answer|result|Result|tool_call|ToolCall|function_call|FunctionCall)>/gi, '');
  cleaned = cleaned.replace(/<\/?[a-zA-Z_][a-zA-Z0-9_]*>/g, '');
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  return cleaned.trim();
}

export function useChatStreaming({
  openFiles: externalOpenFiles,
  onTasksUpdated,
  addToast,
  sessions,
  activeSessionId,
  setActiveSessionId,
  speakerEnabled,
  sessionMessages,
  setSessionMessages,
  saveSessionsState,
  setMessagesForSession,
  saveMessagesImmediately,
  loadMessagesFromStorage,
  welcomeMsg,
  sessionRefs,
  selectedModel,
  providerConfigs,
  quickConfig,
  selectedManifestoPath,
  fetchOllamaModels,
  refreshConfig,
  activeManifesto,
}) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeMode, setActiveMode] = useState('chat');
  const [actionsLog, setActionsLog] = useState([]);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [pcFiles, setPcFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState({});
  const [autoScroll, setAutoScroll] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
  const [loopMaxIterations, setLoopMaxIterations] = useState(25);
  const [loopIteration, setLoopIteration] = useState(0);
  const [loopActive, setLoopActive] = useState(false);
  const [actionStrategy, setActionStrategy] = useState('bilanciata');
  const [actionMaxReadIterations, setActionMaxReadIterations] = useState('2');
  const [actionMaxTotalReads, setActionMaxTotalReads] = useState('5');
  const [autoApprove, setAutoApprove] = useState(false);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [planExecuting, setPlanExecuting] = useState(false);
  const [showHistory, setShowHistory] = useState(true);
  const [showFilePicker, setShowFilePicker] = useState(false);

  const abortRef = useRef(null);
  const streamingSessionIdRef = useRef(null);
  const loopActiveRef = useRef(loopActive);
  const loopIterationRef = useRef(loopIteration);
  const loopMaxIterationsRef = useRef(loopMaxIterations);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [sessionMessages, activeSessionId, loading, autoScroll]);

  useEffect(() => { loopActiveRef.current = loopActive; }, [loopActive]);
  useEffect(() => { loopIterationRef.current = loopIteration; }, [loopIteration]);
  useEffect(() => { loopMaxIterationsRef.current = loopMaxIterations; }, [loopMaxIterations]);

  const stopInference = useCallback((e) => {
    if (e && typeof e.preventDefault === 'function') {
      try { e.preventDefault(); } catch (err) {}
    }
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    if (globalAbortController) { globalAbortController.abort(); globalAbortController = null; }
    // Stopping generation stops the reading too, queued sentences included.
    stopSpeech();
    
    const sid = streamingSessionIdRef.current || sessionRefs.activeSessionId.current;
    if (sid) {
      setSessionMessages(prev => {
        const msgs = [...(prev[sid] || [])];
        if (msgs.length > 0) {
          const last = msgs[msgs.length - 1];
          if (last.role === 'assistant') {
            const curContent = typeof last.content === 'string' ? last.content.trim() : '';
            msgs[msgs.length - 1] = {
              ...last,
              streaming: false,
              streamingThinking: false,
              statusMessage: undefined,
              content: curContent ? `${curContent}\n\n*🛑 Generazione interrotta dall'utente.*` : '🛑 *Generazione interrotta dall\'utente.*'
            };
          }
          saveMessagesImmediately(sid, msgs);
          try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (err) {}
        }
        return { ...prev, [sid]: msgs };
      });
    }

    setLoopActive(false);
    setLoading(false);
    streamingSessionIdRef.current = null;
    sessionStorage.removeItem('sigma_pending_chat');
  }, [saveMessagesImmediately, sessionRefs]);

  const handleStreamResponse = async (res, sessionId, continuationCount = 0, userPrompt = '') => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '', fullThinking = '', buffer = '';
    let firstToken = true, hasThinking = false, wasTruncated = false;
    // Server-side formatted version of the answer (code blocks stripped, file
    // summary appended). Replaces the streamed text once the stream is over.
    let finalOverride = null;
    let finalThinkingOverride = null;
    // Identifies this message for the TTS: lets the per-message button know it
    // is the one being read, and lets a single click stop it.
    const assistantTimestamp = new Date().toISOString();
    let speechStarted = false;
    const modelName = selectedModel;
    
    let streamAgentId = activeManifesto?.path?.replace('manifesti/', '')?.replace('.md', '') || '';
    let streamAgentName = activeManifesto?.name || '';
    let streamAgentStyle = getAgentStyle(streamAgentId);

    let streamCreatedFiles = [];
    let streamActionsLog = [];
    // Strumenti MCP eseguiti in questo turno, e le chiamate che si sono fermate
    // ad aspettare l'operatore prima di toccare qualcosa fuori da Sigma Studio.
    let streamToolCalls = [];
    let streamToolApprovals = [];
    let streamRoutingTimeMs = null;
    let streamLoadDurationMs = null;
    let streamHardwareNote = null;
    let streamTps = null;
    let firstTokenTime = null;
    let generatedTokenCount = 0;

    try {
      let streamDone = false, hasError = false, streamErrorMsg = '';
      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (payload === '[DONE]') { streamDone = true; break; }
            if (payload === '[ERROR]') { hasError = true; streamDone = true; break; }
            try {
              const p = JSON.parse(payload);
              if (p.truncated || p.done_reason === 'length') {
                wasTruncated = true;
              }
              if (p.created_files && Array.isArray(p.created_files)) {
                streamCreatedFiles = p.created_files;
              }
              if (p.actions_log && Array.isArray(p.actions_log)) {
                streamActionsLog = p.actions_log;
              }
              if (p.metrics) {
                if (p.metrics.routing_time_ms !== undefined && p.metrics.routing_time_ms !== null) {
                  streamRoutingTimeMs = p.metrics.routing_time_ms;
                }
                if (p.metrics.load_duration_ms !== undefined && p.metrics.load_duration_ms !== null) {
                  streamLoadDurationMs = p.metrics.load_duration_ms;
                }
                if (p.metrics.hardware_note) {
                  streamHardwareNote = p.metrics.hardware_note;
                }
                if (p.metrics.tokens_per_second !== undefined && p.metrics.tokens_per_second !== null) {
                  streamTps = p.metrics.tokens_per_second;
                }
              }
              // L'agente li manda uno per evento mentre ragiona; la corsia
              // veloce risponde con un blocco solo che li porta già in elenco.
              // Entrambe le forme arrivano su questo canale, quindi si leggono
              // entrambe: leggerne una sola faceva sparire la scheda di
              // conferma e il comando restava non eseguito senza spiegazioni.
              if (p.tool_result) {
                streamToolCalls = [...streamToolCalls, p.tool_result];
              }
              if (Array.isArray(p.tool_calls)) {
                streamToolCalls = [...streamToolCalls, ...p.tool_calls];
              }
              if (p.tool_approval) {
                streamToolApprovals = [...streamToolApprovals, p.tool_approval];
              }
              if (Array.isArray(p.tool_approvals)) {
                streamToolApprovals = [...streamToolApprovals, ...p.tool_approvals];
              }
              if (p.final_content && continuationCount === 0) {
                finalOverride = p.final_content;
              }
              if (p.final_thinking !== undefined && continuationCount === 0) {
                finalThinkingOverride = p.final_thinking;
              }
              if (p.model_status) {
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      statusMessage: p.model_status
                    };
                  }
                  return { ...prev, [sessionId]: n };
                });
              }
              if (p.meta) {
                if (p.meta.routing_time_ms !== undefined && p.meta.routing_time_ms !== null) {
                  streamRoutingTimeMs = p.meta.routing_time_ms;
                }
                if (p.meta.load_duration_ms !== undefined && p.meta.load_duration_ms !== null) {
                  streamLoadDurationMs = p.meta.load_duration_ms;
                }
                if (p.meta.hardware_note) {
                  streamHardwareNote = p.meta.hardware_note;
                }
                streamAgentId = p.meta.agent_id || p.meta.manifesto_used || 'sigma_assistant';
                streamAgentStyle = getAgentStyle(streamAgentId);
                const resolvedRole = p.meta.agent_role || streamAgentStyle.name || p.meta.agent_name || (streamAgentId ? streamAgentId.replace('_', ' ') : 'Sigma Assistant');
                const resolvedName = p.meta.agent_name || streamAgentStyle.name || resolvedRole;
                const resolvedImage = p.meta.agent_image || streamAgentStyle.image || '/images/default.png';
                streamAgentName = resolvedName;
                const modelStatus = p.meta.model_status;
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      agent_id: streamAgentId,
                      agentRole: resolvedRole,
                      agentName: `${resolvedRole} (${selectedModel})`,
                      agentImage: resolvedImage,
                      statusMessage: modelStatus || n[n.length - 1].statusMessage,
                      routing_time_ms: streamRoutingTimeMs,
                      load_duration_ms: streamLoadDurationMs,
                      hardware_note: streamHardwareNote,
                      metrics: {
                        routing_time_ms: streamRoutingTimeMs,
                        load_duration_ms: streamLoadDurationMs,
                        tokens_per_second: streamTps,
                        hardware_note: streamHardwareNote
                      }
                    };
                  }
                  return { ...prev, [sessionId]: n };
                });
              }
              if (p.thinking) {
                hasThinking = true;
                fullThinking += p.thinking;
                if (!firstTokenTime) firstTokenTime = performance.now();
                generatedTokenCount += Math.max(1, p.thinking.split(/\s+/).filter(Boolean).length);
              }
              if (p.token) {
                fullText += p.token;
                if (!firstTokenTime) firstTokenTime = performance.now();
                generatedTokenCount += Math.max(1, p.token.split(/\s+/).filter(Boolean).length);
                // Read along as the answer is written — reasoning is on its own
                // channel and never reaches this branch, so it is never spoken.
                if (speakerEnabled) {
                  if (!speechStarted) {
                    speechStarted = startSpeechStream(assistantTimestamp);
                  }
                  pushSpeechStream(p.token);
                }
              }
              else if (p.response) {
                fullText += p.response;
                if (!firstTokenTime) firstTokenTime = performance.now();
                generatedTokenCount += Math.max(1, p.response.split(/\s+/).filter(Boolean).length);
              }

              // Live TPS calculation
              if (firstTokenTime && !streamTps) {
                const elapsedSec = (performance.now() - firstTokenTime) / 1000;
                if (elapsedSec > 0.4) {
                  streamTps = parseFloat((generatedTokenCount / elapsedSec).toFixed(1));
                }
              }

              if (firstToken && continuationCount === 0) {
                firstToken = false;
                const resolvedRole = streamAgentStyle?.name || streamAgentName || (activeManifesto?.name && activeManifesto?.name !== 'auto' ? activeManifesto.name : 'Sigma Assistant');
                const resolvedImage = streamAgentStyle?.image || (activeManifesto?.image && activeManifesto?.image !== '/images/default.png' ? activeManifesto.image : '/images/default.png');
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      content: fullText,
                      agent_id: streamAgentId,
                      agentName: `${resolvedRole} (${selectedModel})`,
                      agentRole: resolvedRole,
                      agentImage: resolvedImage,
                      timestamp: assistantTimestamp,
                      streaming: true,
                      thinking: hasThinking ? fullThinking : undefined,
                      streamingThinking: hasThinking,
                      created_files: streamCreatedFiles,
                      actions_log: streamActionsLog,
                      tool_calls: streamToolCalls,
                      tool_approvals: streamToolApprovals,
                      routing_time_ms: streamRoutingTimeMs,
                      load_duration_ms: streamLoadDurationMs,
                      tokens_per_second: streamTps,
                      hardware_note: streamHardwareNote,
                      metrics: {
                        routing_time_ms: streamRoutingTimeMs,
                        load_duration_ms: streamLoadDurationMs,
                        tokens_per_second: streamTps,
                        hardware_note: streamHardwareNote
                      }
                    };
                  } else {
                    n.push({
                      role: 'assistant',
                      content: fullText,
                      agent_id: streamAgentId,
                      agentName: `${resolvedRole} (${selectedModel})`,
                      agentRole: resolvedRole,
                      agentImage: resolvedImage,
                      timestamp: assistantTimestamp,
                      streaming: true,
                      thinking: hasThinking ? fullThinking : undefined,
                      streamingThinking: hasThinking,
                      created_files: streamCreatedFiles,
                      actions_log: streamActionsLog,
                      tool_calls: streamToolCalls,
                      tool_approvals: streamToolApprovals,
                      routing_time_ms: streamRoutingTimeMs,
                      load_duration_ms: streamLoadDurationMs,
                      tokens_per_second: streamTps,
                      hardware_note: streamHardwareNote,
                      metrics: {
                        routing_time_ms: streamRoutingTimeMs,
                        load_duration_ms: streamLoadDurationMs,
                        tokens_per_second: streamTps,
                        hardware_note: streamHardwareNote
                      }
                    });
                  }
                  return { ...prev, [sessionId]: n };
                });
              } else {
                setSessionMessages(prev => {
                  const n = [...(prev[sessionId] || [])];
                  if (n.length > 0 && n[n.length - 1].role === 'assistant') {
                    const existingContent = continuationCount > 0 ? n[n.length - 1].content : '';
                    const updatedContent = continuationCount > 0 ? existingContent + fullText : fullText;
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      content: updatedContent,
                      thinking: hasThinking ? fullThinking : n[n.length - 1].thinking,
                      streamingThinking: hasThinking,
                      created_files: streamCreatedFiles.length > 0 ? streamCreatedFiles : n[n.length - 1].created_files,
                      actions_log: streamActionsLog.length > 0 ? streamActionsLog : n[n.length - 1].actions_log,
                      tool_calls: streamToolCalls,
                      tool_approvals: streamToolApprovals,
                      routing_time_ms: streamRoutingTimeMs || n[n.length - 1].routing_time_ms,
                      load_duration_ms: streamLoadDurationMs || n[n.length - 1].load_duration_ms,
                      tokens_per_second: streamTps || n[n.length - 1].tokens_per_second,
                      hardware_note: streamHardwareNote || n[n.length - 1].hardware_note,
                      metrics: {
                        routing_time_ms: streamRoutingTimeMs || n[n.length - 1].routing_time_ms,
                        load_duration_ms: streamLoadDurationMs || n[n.length - 1].load_duration_ms,
                        tokens_per_second: streamTps || n[n.length - 1].tokens_per_second,
                        hardware_note: streamHardwareNote || n[n.length - 1].hardware_note
                      }
                    };
                  }
                  return { ...prev, [sessionId]: n };
                });
              }
            } catch (e) {}
          }
          if (streamDone) break;
        }
      }

      if (wasTruncated && continuationCount < 3) {
        setSessionMessages(prev => {
          const n = [...(prev[sessionId] || [])];
          if (n.length > 0 && n[n.length - 1].role === 'assistant') {
            n[n.length - 1] = {
              ...n[n.length - 1],
              statusMessage: '⚡ Token massimi raggiunti: Auto-continuazione in corso...'
            };
          }
          return { ...prev, [sessionId]: n };
        });

        try {
          const contRes = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: "Continua esattamente da dove ti sei fermato nell'ultimo messaggio, senza ripetere il testo già scritto.",
              history: sessionRefs.sessionMessages.current[sessionId] || [],
              stream: true,
              model: selectedModel,
              manifesto: activeManifesto?.path
            })
          });
          if (contRes.ok) {
            await handleStreamResponse(contRes, sessionId, continuationCount + 1, userPrompt);
            return;
          }
        } catch (contErr) {
          console.warn("Auto-continuation fetch failed:", contErr);
        }
      }

      setLoading(false);
      const finalContent = cleanModelTags(finalOverride || fullText) || (fullThinking ? cleanModelTags(fullThinking) : (hasError ? streamErrorMsg || '⚠️ Error' : '⚠️ Nessuna risposta.'));

      if (streamCreatedFiles.length === 0 && finalContent && !hasError) {
        try {
          const extRes = await fetch('/api/chat/extract_files', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: finalContent, prompt_topic: userPrompt || '' })
          });
          if (extRes.ok) {
            const extData = await extRes.json();
            if (extData.created_files?.length > 0) {
              streamCreatedFiles = extData.created_files;
              streamActionsLog = extData.actions_log || [];
              window.dispatchEvent(new Event('sigma_topics_updated'));
            }
          }
        } catch (extErr) {
          console.warn("Post-stream file extraction failed:", extErr);
        }
      }

      if (!streamTps && firstTokenTime) {
        const elapsedSec = (performance.now() - firstTokenTime) / 1000;
        if (elapsedSec > 0.2) {
          streamTps = parseFloat((generatedTokenCount / elapsedSec).toFixed(1));
        }
      }

      setSessionMessages(prev => {
        const n = [...(prev[sessionId] || [])];
        if (n.length > 0 && n[n.length - 1].role === 'assistant') {
          const resolvedThinking = finalThinkingOverride !== null
            ? (finalThinkingOverride || undefined)
            : (hasThinking ? fullThinking : n[n.length - 1].thinking);
          n[n.length - 1] = {
            ...n[n.length - 1],
            content: finalContent,
            thinking: resolvedThinking,
            streaming: false,
            streamingThinking: false,
            statusMessage: undefined,
            created_files: streamCreatedFiles.length > 0 ? streamCreatedFiles : n[n.length - 1].created_files,
            actions_log: streamActionsLog.length > 0 ? streamActionsLog : n[n.length - 1].actions_log,
            tool_calls: streamToolCalls,
            tool_approvals: streamToolApprovals,
            routing_time_ms: streamRoutingTimeMs || n[n.length - 1].routing_time_ms,
            tokens_per_second: streamTps || n[n.length - 1].tokens_per_second,
            metrics: {
              routing_time_ms: streamRoutingTimeMs || n[n.length - 1].routing_time_ms,
              tokens_per_second: streamTps || n[n.length - 1].tokens_per_second
            }
          };
        }
        saveMessagesImmediately(sessionId, n);
        try { localStorage.setItem(`sigma_chat_msgs_${sessionId}`, JSON.stringify(n)); } catch (err) {}
        if (addToast && streamActionsLog.length > 0) {
          streamActionsLog.forEach(act => {
            if (act.type === 'create_file') {
              addToast(`📄 Nuovo file creato: ${act.path}`, 'success', 4000);
            } else if (act.type === 'edit_file') {
              addToast(`✏️ File modificato: ${act.path}`, 'info', 4000);
            } else if (act.type === 'mcp_tool_call') {
              addToast(act.message || '⚡ Strumento MCP eseguito', 'info', 4000);
            }
          });
        }
        if (speechStarted) {
          // Already reading along: just flush the tail of the sentence buffer.
          endSpeechStream();
        } else if (speakerEnabled && finalContent && !hasError) {
          // No progressive reading happened (non-streaming provider): read it now.
          speakAgentMessage(finalContent, null, null, assistantTimestamp);
        }
        return { ...prev, [sessionId]: n };
      });
    } catch (e) {
      setLoading(false);
      stopSpeech();
      setSessionMessages(prev => {
        const msgs = [...(prev[sessionId] || []), { role: 'assistant', content: `⚠️ **Errore:** ${e.message}`, timestamp: new Date().toISOString(), error: true, agentImage: activeManifesto?.image || '/images/default.png', agentRole: activeManifesto?.name || '' }];
        saveMessagesImmediately(sessionId, msgs);
        return { ...prev, [sessionId]: msgs };
      });
    }
  };

  const handleJsonResponse = async (res, sessionId, updatedMessages) => {
    try {
      const data = await res.json();
      const routedAgentId = data.agent_id || data.manifesto_used || 'sigma_assistant';
      const routedStyle = getAgentStyle(routedAgentId);
      const resolvedRole = data.agent_role || routedStyle?.name || data.agent_name || (routedAgentId ? routedAgentId.replace('_', ' ') : 'Sigma Assistant');
      const resolvedImage = data.agent_image || routedStyle?.image || '/images/default.png';
      const routingTimeMs = data.routing_time_ms ?? data.metrics?.routing_time_ms ?? null;
      const tokensPerSecond = data.tokens_per_second ?? data.metrics?.tokens_per_second ?? null;
      const assistant = {
        role: 'assistant',
        content: cleanModelTags(data.response) || '⚠️ Nessuna risposta.',
        thinking: data.thinking || null,
        actions_log: data.actions_log || [],
        // La corsia veloce risponde qui invece che in streaming: gli strumenti
        // eseguiti e le conferme in attesa arrivano per questa strada.
        tool_calls: data.tool_calls || [],
        tool_approvals: data.tool_approvals || [],
        timestamp: new Date().toISOString(),
        error: data.error || null,
        agent_id: routedAgentId,
        agentName: `${resolvedRole} (${selectedModel})`,
        agentRole: resolvedRole,
        agentImage: resolvedImage,
        routing_time_ms: routingTimeMs,
        tokens_per_second: tokensPerSecond,
        metrics: {
          routing_time_ms: routingTimeMs,
          tokens_per_second: tokensPerSecond
        }
      };
      if (sessionRefs.activeSessionId.current === sessionId) {
        const finalMessages = [...updatedMessages, assistant];
        setMessagesForSession(sessionId, finalMessages);
        saveMessagesImmediately(sessionId, finalMessages);
        if (data.actions_log?.length > 0) {
          setActionsLog(data.actions_log);
          if (onTasksUpdated) onTasksUpdated();
          if (addToast) {
            data.actions_log.forEach(act => {
              if (act.type === 'create_file') {
                addToast(`📄 Nuovo file creato: ${act.path}`, 'success', 4000);
              } else if (act.type === 'edit_file') {
                addToast(`✏️ File modificato: ${act.path}`, 'info', 4000);
              } else if (act.type === 'mcp_tool_call') {
                addToast(act.message || '⚡ Strumento MCP eseguito', 'info', 4000);
              }
            });
          }
        }
      } else {
        const prevForSession = sessionRefs.sessionMessages.current[sessionId] || [];
        const finalMessages = [...prevForSession, ...updatedMessages.slice(prevForSession.length), assistant];
        setSessionMessages(prev => ({ ...prev, [sessionId]: finalMessages }));
        saveMessagesImmediately(sessionId, finalMessages);
      }
      if (speakerEnabled && data.response) {
        // Read the answer only — never `data.thinking`.
        speakAgentMessage(assistant.content, null, null, assistant.timestamp);
      }
    } catch (e) {
      if (sessionRefs.activeSessionId.current === sessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore nella risposta del server:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...(sessionRefs.sessionMessages.current[sessionId] || []), errorMsg];
        setMessagesForSession(sessionId, finalMsgs);
        saveMessagesImmediately(sessionId, finalMsgs);
      }
    }
  };

  // --- Send Message (unified: chat + plan) ---
  const sendMessage = useCallback(async (textOverride, extraParams = {}) => {
    if (loading) return;
    const currentSessionId = sessionRefs.activeSessionId.current;
    if (!currentSessionId) return;

    const rawText = (typeof textOverride === 'string' ? textOverride : '') || input || '';
    const messageText = typeof rawText === 'string' ? rawText.trim() : '';
    if (!messageText && attachedFiles.length === 0) return;

    streamingSessionIdRef.current = currentSessionId;
    const openFiles = externalOpenFiles || [];
    const contextFiles = [...(openFiles || []), ...attachedFiles].slice(0, MAX_ATTACHMENTS);
    const userMsg = { role: 'user', content: messageText.trim(), timestamp: new Date().toISOString(), attachments: attachedFiles.length > 0 ? [...attachedFiles] : undefined, agentName: selectedModel };
    const currentMsgs = sessionRefs.sessionMessages.current[currentSessionId] || [];
    const updatedMessages = [...currentMsgs, userMsg];
    const isAuto = !selectedManifestoPath || selectedManifestoPath === 'auto';
    const initialStatus = isAuto 
      ? '🎯 Analisi semantica della richiesta e selezione agente...' 
      : `🧠 Inizializzazione contesto per ${activeManifesto?.name || selectedModel}...`;

    const placeholderRole = isAuto ? 'Sigma Assistant' : (activeManifesto?.name || 'Sigma Assistant');
    const placeholderId = isAuto ? 'sigma_assistant' : (activeManifesto?.path?.replace('manifesti/', '')?.replace('.md', '') || 'sigma_assistant');
    const placeholderImage = isAuto ? '/images/default.png' : (activeManifesto?.image || '/images/default.png');

    const assistantPlaceholder = {
      role: 'assistant',
      content: '',
      agent_id: placeholderId,
      agentName: `${placeholderRole} (${selectedModel})`,
      agentRole: placeholderRole,
      agentImage: placeholderImage,
      timestamp: new Date().toISOString(),
      streaming: true,
      statusMessage: initialStatus
    };
    const updatedMessagesWithPlaceholder = [...updatedMessages, assistantPlaceholder];
    setMessagesForSession(currentSessionId, updatedMessagesWithPlaceholder);
    saveMessagesImmediately(currentSessionId, updatedMessages);
    const sessionName = sessionRefs.sessions.current.find(s => s.id === currentSessionId)?.name;
    if (sessionName && sessionName.startsWith('Chat ')) {
      const firstWords = messageText.trim().slice(0, 50).replace(/\n/g, ' ');
      const newName = `${firstWords}... (${selectedModel.split(':')[0]})`;
      saveSessionsState(sessionRefs.sessions.current.map(s => s.id === currentSessionId ? { ...s, name: newName } : s));
    }
    setInput('');
    setLoading(true);
    setActionsLog([]);
    const controller = new AbortController();
    abortRef.current = controller;
    globalAbortController = controller;

    try {
      const routing = getModelRoutingInfo(selectedModel, providerConfigs);
      const isPlan = activeMode === 'plan';

      const userProfile = (() => {
        try { return JSON.parse(localStorage.getItem('sigma_user_profile') || '{}'); }
        catch(e) { return {}; }
      })();

      const useStream = !isPlan;
      const body = {
        message: messageText.trim(), bot_name: selectedModel, model: selectedModel,
        model_provider: routing.provider, model_endpoint: routing.endpoint, model_api_url: routing.api_url,
        allow_actions: true, planning_mode: isPlan, stream: useStream,
        timeout: quickConfig.timeout || 300, web_search: webSearch,
        user_name: userProfile.name || 'Utente',
        user_title: userProfile.title || '',
        user_profile: userProfile,
        context: { open_files: contextFiles, history: updatedMessages.slice(-10).map(m => ({ role: m.role, content: m.content })) },
        uploaded_files: pcFiles.length > 0 ? pcFiles : undefined
      };
      if (selectedManifestoPath) body.manifesto_path = selectedManifestoPath;
      const res = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal
      });
      const contentType = res.headers.get("content-type") || "";
      if (res.ok && contentType.includes("text/event-stream")) {
        await handleStreamResponse(res, currentSessionId, 0, messageText);
      } else {
        await handleJsonResponse(res, currentSessionId, updatedMessages);
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        sessionStorage.removeItem('sigma_pending_chat');
        const sid = currentSessionId || sessionRefs.activeSessionId.current;
        if (sid) {
          setSessionMessages(prev => {
            const msgs = [...(prev[sid] || [])];
            if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
              const curContent = msgs[msgs.length - 1].content || (msgs[msgs.length - 1].thinking ? cleanModelTags(msgs[msgs.length - 1].thinking) : '');
              msgs[msgs.length - 1] = {
                ...msgs[msgs.length - 1],
                content: curContent ? `${curContent}\n\n*⏹️ Generazione interrotta dall'utente.*` : '⏹️ Generazione interrotta dall\'utente.',
                streaming: false,
                streamingThinking: false,
                statusMessage: undefined
              };
            }
            saveMessagesImmediately(sid, msgs);
            try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (err) {}
            return { ...prev, [sid]: msgs };
          });
        }
        return;
      }
      if (sessionRefs.activeSessionId.current === currentSessionId) {
        const errorMsg = { role: 'assistant', content: `❌ **Errore di connessione:** ${e.message}`, timestamp: new Date().toISOString(), error: true };
        const finalMsgs = [...(sessionRefs.sessionMessages.current[currentSessionId] || []), errorMsg];
        setMessagesForSession(currentSessionId, finalMsgs);
        saveMessagesImmediately(currentSessionId, finalMsgs);
      }
    } finally {
      const sid = sessionRefs.activeSessionId.current;
      if (sid) {
        const msgs = sessionRefs.sessionMessages.current[sid];
        if (msgs && msgs.length > 0) {
          try { localStorage.setItem(`sigma_chat_msgs_${sid}`, JSON.stringify(msgs)); } catch (e) {}
        }
      }
      setLoading(false);
      abortRef.current = null;
      globalAbortController = null;
      streamingSessionIdRef.current = null;
    }
  }, [input, loading, selectedModel, providerConfigs, quickConfig, loopMaxIterations, webSearch, attachedFiles, pcFiles, activeMode, selectedManifestoPath, externalOpenFiles, refreshConfig, saveSessionsState, setMessagesForSession, saveMessagesImmediately, sessionRefs, setActiveSessionId]);

  const removePcFile = useCallback((filename) => { setPcFiles(prev => prev.filter(f => f.filename !== filename)); }, []);
  const handleDragOver = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation(); setDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    Promise.all(files.map(f => new Promise(resolve => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve({ filename: f.name, content: ev.target.result });
      reader.onerror = () => resolve(null);
      reader.readAsText(f);
    }))).then(results => { const valid = results.filter(Boolean); setPcFiles(prev => [...prev, ...valid].slice(0, 20)); });
  }, []);

  return {
    input, setInput, loading, setLoading, activeMode, setActiveMode,
    actionsLog, setActionsLog, attachedFiles, setAttachedFiles,
    pcFiles, setPcFiles, dragOver, expandedThinking, setExpandedThinking,
    autoScroll, setAutoScroll, webSearch, setWebSearch,
    loopMaxIterations, setLoopMaxIterations, loopIteration, setLoopIteration,
    loopActive, setLoopActive, actionStrategy, setActionStrategy,
    actionMaxReadIterations, setActionMaxReadIterations,
    actionMaxTotalReads, setActionMaxTotalReads, autoApprove, setAutoApprove,
    currentPlan, setCurrentPlan, planExecuting, setPlanExecuting,
    showHistory, setShowHistory, showFilePicker, setShowFilePicker,
    sendMessage, stopInference, removePcFile,
    handleDragOver, handleDragLeave, handleDrop,
    streamingRefs: {
      abort: abortRef, streamingSessionId: streamingSessionIdRef,
      loopActive: loopActiveRef, loopIteration: loopIterationRef,
      loopMaxIterations: loopMaxIterationsRef, messagesEnd: messagesEndRef
    }
  };
}