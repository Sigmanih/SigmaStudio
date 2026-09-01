import { useState, useCallback, useRef, useEffect } from 'react';
import { STORAGE_KEY, MAX_HISTORY, createSession, loadSessions, saveSessions,
         loadActiveSessionId, saveActiveSessionId } from '../chatStorage';

export function useChatSessions({ selectedModel, setSelectedModel, setActionsLog, saveMessagesImmediately, loadMessagesFromStorage, welcomeMsg }) {
  // Synchronously initialize sessions from localStorage
  const [sessions, setSessions] = useState(() => {
    const saved = loadSessions();
    if (saved && saved.length > 0) {
      const enriched = saved.map(s => {
        if (s.messageCount === undefined || s.lastMessageAt === undefined) {
          const stored = loadMessagesFromStorage(s.id);
          const count = stored ? stored.length : (Array.isArray(s.messages) ? s.messages.length : 0);
          let lastTime = s.updatedAt || s.createdAt || new Date().toISOString();
          if (stored && stored.length > 0) {
            const lastMsg = stored[stored.length - 1];
            if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
              lastTime = lastMsg.timestamp || lastMsg.time;
            }
          }
          return { ...s, messageCount: count, lastMessageAt: lastTime };
        }
        return s;
      });
      return enriched;
    }
    const s = createSession(selectedModel);
    saveSessions([s]);
    return [s];
  });

  // Synchronously determine active session
  const [activeSessionId, setActiveSessionId] = useState(() => {
    const saved = loadSessions();
    const storedId = loadActiveSessionId();
    if (saved && saved.length > 0) {
      const target = (storedId ? saved.find(x => x.id === storedId) : null) || saved[0];
      if (target) {
        saveActiveSessionId(target.id);
        return target.id;
      }
    }
    return null;
  });

  // Synchronously initialize message cache for the active session
  const [sessionMessages, setSessionMessages] = useState(() => {
    const saved = loadSessions();
    const storedId = loadActiveSessionId();
    const target = (saved && saved.length > 0)
      ? ((storedId ? saved.find(x => x.id === storedId) : null) || saved[0])
      : null;

    if (!target) return {};

    let restored = loadMessagesFromStorage(target.id);
    if (!restored || restored.length === 0) {
      if (Array.isArray(target.messages) && target.messages.length > 0) {
        restored = target.messages;
      } else {
        restored = [welcomeMsg];
        saveMessagesImmediately(target.id, [welcomeMsg]);
      }
    }
    return { [target.id]: restored };
  });

  const [editingSessionName, setEditingSessionName] = useState(null);
  const [editNameValue, setEditNameValue] = useState('');

  const refs = {
    sessions: useRef(sessions),
    sessionMessages: useRef(sessionMessages),
    activeSessionId: useRef(activeSessionId),
  };

  useEffect(() => { refs.sessions.current = sessions; }, [sessions]);
  useEffect(() => { refs.sessionMessages.current = sessionMessages; }, [sessionMessages]);
  useEffect(() => { refs.activeSessionId.current = activeSessionId; }, [activeSessionId]);

  // Keep active session saved in localStorage
  useEffect(() => {
    if (activeSessionId) {
      saveActiveSessionId(activeSessionId);
    }
  }, [activeSessionId]);

  // Listen for explicit chat history purge event ONLY when clear_history / clear_chat is true
  useEffect(() => {
    const handleChatCleared = (e) => {
      if (e?.detail && e.detail.clear_history === false && e.detail.clearChat === false) {
        return;
      }
      const s = createSession(selectedModel);
      setSessions([s]);
      refs.sessions.current = [s];
      saveSessions([s]);
      setSessionMessages({ [s.id]: [welcomeMsg] });
      refs.sessionMessages.current = { [s.id]: [welcomeMsg] };
      saveMessagesImmediately(s.id, [welcomeMsg]);
      setActiveSessionId(s.id);
      refs.activeSessionId.current = s.id;
      saveActiveSessionId(s.id);
    };
    window.addEventListener('sigma-chat-cleared', handleChatCleared);
    return () => window.removeEventListener('sigma-chat-cleared', handleChatCleared);
  }, [selectedModel, welcomeMsg, saveMessagesImmediately]);

  const saveSessionsState = useCallback((ns) => {
    setSessions(ns);
    refs.sessions.current = ns;
    saveSessions(ns);
  }, []);

  const setMessagesForSession = useCallback((sessionId, msgsOrUpdater) => {
    setSessionMessages(prev => {
      const existing = prev[sessionId] || loadMessagesFromStorage(sessionId) || [];
      const next = typeof msgsOrUpdater === 'function' ? msgsOrUpdater(existing) : msgsOrUpdater;
      const updated = { ...prev, [sessionId]: next };
      refs.sessionMessages.current = updated;
      saveMessagesImmediately(sessionId, next);

      // Update session metadata in sessions state
      const nowIso = new Date().toISOString();
      let lastMsgTime = nowIso;
      if (next.length > 0) {
        const lastMsg = next[next.length - 1];
        if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
          lastMsgTime = lastMsg.timestamp || lastMsg.time;
        }
      }

      setSessions(prevSessions => {
        const nextSessions = prevSessions.map(s => {
          if (s.id === sessionId) {
            let nextName = s.name;
            if (s.name.startsWith('Chat ') && next.length > 1) {
              const firstUser = next.find(m => m.role === 'user');
              if (firstUser && firstUser.content) {
                const snippet = firstUser.content.trim().slice(0, 40).replace(/\n/g, ' ');
                if (snippet) nextName = `${snippet}...`;
              }
            }
            return {
              ...s,
              name: nextName,
              messageCount: next.length,
              lastMessageAt: lastMsgTime,
              updatedAt: nowIso
            };
          }
          return s;
        });
        refs.sessions.current = nextSessions;
        saveSessions(nextSessions);
        return nextSessions;
      });

      return updated;
    });
  }, [saveMessagesImmediately, loadMessagesFromStorage]);

  const switchToSession = useCallback((sid) => {
    const curId = refs.activeSessionId.current;
    const curMsgs = refs.sessionMessages.current[curId];
    if (curId && curMsgs && curMsgs.length > 0) {
      saveMessagesImmediately(curId, curMsgs);
    }

    const s = refs.sessions.current.find(x => x.id === sid);
    if (s) {
      let msgsForSession = refs.sessionMessages.current[sid];
      if (!msgsForSession || msgsForSession.length === 0) {
        const stored = loadMessagesFromStorage(sid);
        msgsForSession = stored && stored.length > 0 ? stored : [welcomeMsg];
        setSessionMessages(prev => ({ ...prev, [sid]: msgsForSession }));
        refs.sessionMessages.current[sid] = msgsForSession;
      }
      if (setSelectedModel && s.model) {
        setSelectedModel(s.model);
      }
      setActiveSessionId(sid);
      refs.activeSessionId.current = sid;
      saveActiveSessionId(sid);
    }
    if (setActionsLog) setActionsLog([]);
  }, [saveMessagesImmediately, loadMessagesFromStorage, welcomeMsg, setSelectedModel, setActionsLog]);

  const handleNewSession = () => {
    const s = createSession(selectedModel);
    const updated = [s, ...sessions].slice(0, MAX_HISTORY);
    saveSessionsState(updated);
    setSessionMessages(prev => ({ ...prev, [s.id]: [welcomeMsg] }));
    refs.sessionMessages.current[s.id] = [welcomeMsg];
    saveMessagesImmediately(s.id, [welcomeMsg]);
    setActiveSessionId(s.id);
    refs.activeSessionId.current = s.id;
    saveActiveSessionId(s.id);
    if (setActionsLog) setActionsLog([]);
    if (setSelectedModel && s.model) setSelectedModel(s.model);
  };

  const handleDeleteSession = (e, sid) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const ns = sessions.filter(s => s.id !== sid);
    saveSessionsState(ns);
    setSessionMessages(prev => { const next = { ...prev }; delete next[sid]; return next; });
    try {
      localStorage.removeItem(`sigma_chat_msgs_${sid}`);
      localStorage.removeItem(`sigma_chat_session_${sid}`);
    } catch (err) {}

    if (activeSessionId === sid) {
      if (ns.length > 0) {
        switchToSession(ns[0].id);
      } else {
        const s = createSession(selectedModel);
        saveSessionsState([s]);
        setSessionMessages({ [s.id]: [welcomeMsg] });
        refs.sessionMessages.current[s.id] = [welcomeMsg];
        saveMessagesImmediately(s.id, [welcomeMsg]);
        switchToSession(s.id);
      }
    }
  };

  const handleStartRename = (e, sid) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const s = sessions.find(x => x.id === sid);
    setEditingSessionName(sid);
    setEditNameValue(s?.name || '');
  };

  const handleFinishRename = (sid) => {
    const name = editNameValue.trim() || 'Chat';
    saveSessionsState(sessions.map(s => s.id === sid ? { ...s, name } : s));
    setEditingSessionName(null);
  };

  const handleRenameKeyDown = (e, sid) => {
    if (e.key === 'Enter') handleFinishRename(sid);
    if (e.key === 'Escape') setEditingSessionName(null);
  };

  const deleteMessage = (msgIndexOrIndices) => {
    if (!activeSessionId) return;

    const currentMsgs = sessionMessages[activeSessionId] || loadMessagesFromStorage(activeSessionId) || [];
    const indices = Array.isArray(msgIndexOrIndices) ? msgIndexOrIndices : [msgIndexOrIndices];
    
    // Raccoglie PID e Job ID associati ai messaggi che si stanno eliminando
    const pidsToKill = new Set();
    const jobIdsToKill = new Set();

    indices.forEach(idx => {
      const msg = currentMsgs[idx];
      if (msg) {
        if (msg.pid) pidsToKill.add(msg.pid);
        if (msg.process_id) pidsToKill.add(msg.process_id);
        if (msg.processId) pidsToKill.add(msg.processId);
        if (msg.meta?.pid) pidsToKill.add(msg.meta.pid);
        if (msg.meta?.process_id) pidsToKill.add(msg.meta.process_id);

        if (msg.job_id) jobIdsToKill.add(msg.job_id);
        if (msg.jobId) jobIdsToKill.add(msg.jobId);
        if (msg.meta?.job_id) jobIdsToKill.add(msg.meta.job_id);
        if (msg.meta?.jobId) jobIdsToKill.add(msg.meta.jobId);

        const actionsList = [...(msg.actions || []), ...(msg.actionsLog || [])];
        actionsList.forEach(act => {
          if (act && typeof act === 'object') {
            if (act.pid) pidsToKill.add(act.pid);
            if (act.process_id) pidsToKill.add(act.process_id);
            if (act.processId) pidsToKill.add(act.processId);
          }
        });
      }
    });

    const killPid = (pid) => {
      fetch('/api/hardware/gpu/kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid })
      }).catch(err => {
        console.warn(`[deleteMessage] Impossibile terminare il processo ${pid}:`, err);
      });
    };

    pidsToKill.forEach(pid => killPid(pid));

    if (jobIdsToKill.size > 0) {
      fetch('/api/hardware/gpu/processes')
        .then(res => res.json())
        .then(data => {
          if (data.success && Array.isArray(data.processes)) {
            data.processes.forEach(proc => {
              if (proc.job_id && jobIdsToKill.has(proc.job_id) && proc.killable) {
                killPid(proc.pid);
              }
            });
          }
        })
        .catch(() => {});
    }

    const newMsgs = currentMsgs.filter((_, idx) => !indices.includes(idx));
    setSessionMessages(prev => ({ ...prev, [activeSessionId]: newMsgs }));
    refs.sessionMessages.current[activeSessionId] = newMsgs;
    saveMessagesImmediately(activeSessionId, newMsgs);

    const nowIso = new Date().toISOString();
    let lastMsgTime = nowIso;
    if (newMsgs.length > 0) {
      const lastMsg = newMsgs[newMsgs.length - 1];
      if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
        lastMsgTime = lastMsg.timestamp || lastMsg.time;
      }
    }

    setSessions(prevSessions => {
      const nextSessions = prevSessions.map(s => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messageCount: newMsgs.length,
            lastMessageAt: lastMsgTime,
            updatedAt: nowIso
          };
        }
        return s;
      });
      refs.sessions.current = nextSessions;
      saveSessions(nextSessions);
      return nextSessions;
    });
  };

  return {
    sessions,
    setSessions,
    activeSessionId,
    setActiveSessionId,
    sessionMessages,
    setSessionMessages,
    editingSessionName,
    setEditingSessionName,
    editNameValue,
    setEditNameValue,
    saveSessionsState,
    setMessagesForSession,
    switchToSession,
    handleNewSession,
    handleDeleteSession,
    handleStartRename,
    handleFinishRename,
    handleRenameKeyDown,
    deleteMessage,
    sessionRefs: refs
  };
}
