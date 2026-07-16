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
      return { ...prev, [sessionId]: next };
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
    setSessionMessages(prev => {
      const msgs = prev[activeSessionId] || [];
      let newMsgs;
      if (Array.isArray(msgIndexOrIndices)) {
        newMsgs = msgs.filter((_, idx) => !msgIndexOrIndices.includes(idx));
      } else {
        newMsgs = msgs.filter((_, idx) => idx !== msgIndexOrIndices);
      }
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
