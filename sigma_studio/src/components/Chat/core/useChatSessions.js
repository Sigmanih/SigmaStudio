import { useState, useCallback, useRef, useEffect } from 'react';
import { STORAGE_KEY, MAX_HISTORY, createSession, loadSessions } from '../chatStorage';

export function useChatSessions({ selectedModel, setSelectedModel, setActionsLog, saveMessagesImmediately, loadMessagesFromStorage, welcomeMsg }) {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionMessages, setSessionMessages] = useState({});
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

  // Carica le sessioni salvate da localStorage al mount
  useEffect(() => {
    const saved = loadSessions();
    if (saved.length > 0) {
      setSessions(saved);
    }
  }, []);

  const saveSessionsState = useCallback((ns) => {
    setSessions(ns);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ns)); } catch (e) {}
  }, []);

  const setMessagesForSession = useCallback((sessionId, msgsOrUpdater) => {
    setSessionMessages(prev => {
      const existing = prev[sessionId] || [];
      const next = typeof msgsOrUpdater === 'function' ? msgsOrUpdater(existing) : msgsOrUpdater;
      const updated = { ...prev, [sessionId]: next };
      refs.sessionMessages.current = updated;
      return updated;
    });
  }, []);

  const switchToSession = useCallback((sid) => {
    const curId = refs.activeSessionId.current;
    const curMsgs = refs.sessionMessages.current[curId];
    if (curId && curMsgs && curMsgs.length > 0) saveMessagesImmediately(curId, curMsgs);
    const s = refs.sessions.current.find(x => x.id === sid);
    if (s) {
      let msgsForSession = refs.sessionMessages.current[sid];
      if (!msgsForSession || msgsForSession.length === 0) {
        const stored = loadMessagesFromStorage(sid);
        msgsForSession = stored && stored.length > 0 ? stored : [welcomeMsg];
        setSessionMessages(prev => ({ ...prev, [sid]: msgsForSession }));
      }
      if (setSelectedModel && s.model) {
        setSelectedModel(s.model);
      }
      setActiveSessionId(sid);
    }
    if (setActionsLog) setActionsLog([]);
  }, [saveMessagesImmediately, loadMessagesFromStorage, welcomeMsg, setSelectedModel, setActionsLog]);

  const handleNewSession = () => {
    const s = createSession(selectedModel);
    const updated = [s, ...sessions].slice(0, MAX_HISTORY);
    saveSessionsState(updated);
    setSessionMessages(prev => ({ ...prev, [s.id]: [welcomeMsg] }));
    saveMessagesImmediately(s.id, [welcomeMsg]);
    setActiveSessionId(s.id);
    if (setActionsLog) setActionsLog([]);
    if (setSelectedModel) setSelectedModel(s.model);
  };

  const handleDeleteSession = (e, sid) => {
    if (e && e.stopPropagation) e.stopPropagation();
    const ns = sessions.filter(s => s.id !== sid);
    saveSessionsState(ns);
    setSessionMessages(prev => { const next = { ...prev }; delete next[sid]; return next; });
    try { localStorage.removeItem(`sigma_chat_msgs_${sid}`); } catch (e) {}
    if (activeSessionId === sid) {
      if (ns.length > 0) switchToSession(ns[0].id);
      else {
        const s = createSession(selectedModel);
        saveSessionsState([s]);
        setSessionMessages({ [s.id]: [welcomeMsg] });
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

    const currentMsgs = sessionMessages[activeSessionId] || [];
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
      }).then(res => res.json())
        .then(data => {
          if (data.success) {
            console.log(`[deleteMessage] Processo ${pid} terminato.`);
          }
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

    setSessionMessages(prev => {
      const msgs = prev[activeSessionId] || [];
      const newMsgs = msgs.filter((_, idx) => !indices.includes(idx));
      try {
        localStorage.setItem(`sigma_chat_session_${activeSessionId}`, JSON.stringify(newMsgs));
      } catch (e) {}
      return { ...prev, [activeSessionId]: newMsgs };
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
