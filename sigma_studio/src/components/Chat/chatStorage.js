// ==============================================================================
// CHAT STORAGE | Helpers per persistenza sessioni, messaggi e posizione
// ==============================================================================

const STORAGE_KEY = 'sigma_chat_sessions';
const POS_KEY = 'sigma_chat_position';
const SIZE_KEY = 'sigma_chat_size';
const LAST_MODEL_KEY = 'sigma_last_model';
const ACTIVE_SESSION_KEY = 'sigma_active_session';
const MAX_HISTORY = 25;
const MAX_ATTACHMENTS = 10;

export { STORAGE_KEY, POS_KEY, SIZE_KEY, LAST_MODEL_KEY, ACTIVE_SESSION_KEY, MAX_HISTORY, MAX_ATTACHMENTS };

export function loadLastModel(defaultModel = '') {
  try {
    const saved = localStorage.getItem(LAST_MODEL_KEY);
    return saved || defaultModel;
  } catch { return defaultModel; }
}

export function saveLastModel(modelName) {
  try {
    localStorage.setItem(LAST_MODEL_KEY, modelName);
  } catch (e) {}
}

export function loadActiveSessionId() {
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY) || null;
  } catch { return null; }
}

export function saveActiveSessionId(sessionId) {
  try {
    if (sessionId) localStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
    else localStorage.removeItem(ACTIVE_SESSION_KEY);
  } catch (e) {}
}

let pendingTitleGenerations = {};

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

export function createSession(model, name) {
  const nowIso = new Date().toISOString();
  return {
    id: generateId(),
    name: name || `Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
    model: model || '',
    manifestoPath: 'auto',
    messages: [],
    messageCount: 0,
    lastMessageAt: nowIso,
    createdAt: nowIso,
    updatedAt: nowIso
  };
}

export function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

export function saveSessions(sessions) {
  try {
    if (Array.isArray(sessions)) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_HISTORY)));
    }
  } catch (e) {}
}

export function loadMessagesFromStorage(sessionId) {
  if (!sessionId) return null;
  try {
    // 1. Primary key
    const saved = localStorage.getItem(`sigma_chat_msgs_${sessionId}`);
    if (saved) {
      const p = JSON.parse(saved);
      if (Array.isArray(p) && p.length > 0) return p;
    }
    // 2. Legacy fallback key
    const legacy = localStorage.getItem(`sigma_chat_session_${sessionId}`);
    if (legacy) {
      const p = JSON.parse(legacy);
      if (Array.isArray(p) && p.length > 0) return p;
    }
    // 3. Fallback: check session object itself
    const sessions = loadSessions();
    const match = sessions.find(s => s.id === sessionId);
    if (match && Array.isArray(match.messages) && match.messages.length > 0) {
      return match.messages;
    }
  } catch (e) {}
  return null;
}

export function saveMessagesToStorage(sessionId, messages) {
  if (!sessionId || !Array.isArray(messages)) return;
  try {
    localStorage.setItem(`sigma_chat_msgs_${sessionId}`, JSON.stringify(messages));
    
    // Also touch the session in session list with new updatedAt, messageCount and lastMessageAt
    const sessions = loadSessions();
    let updated = false;
    const nowIso = new Date().toISOString();

    let lastMsgTime = nowIso;
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
        lastMsgTime = lastMsg.timestamp || lastMsg.time;
      }
    }

    const nextSessions = sessions.map(s => {
      if (s.id === sessionId) {
        updated = true;
        let nextName = s.name;
        // Auto-generate title if still default
        if (s.name.startsWith('Chat ') && messages.length > 1) {
          const firstUser = messages.find(m => m.role === 'user');
          if (firstUser && firstUser.content) {
            const snippet = firstUser.content.trim().slice(0, 40).replace(/\n/g, ' ');
            if (snippet) nextName = `${snippet}...`;
          }
        }
        return {
          ...s,
          name: nextName,
          messageCount: messages.length,
          lastMessageAt: lastMsgTime,
          updatedAt: nowIso
        };
      }
      return s;
    });

    if (updated) {
      saveSessions(nextSessions);
    }
  } catch (e) {}
}

export function getSessionStats(session, sessionMessages) {
  if (!session) return { count: 0, lastTime: '' };

  let count = 0;
  let lastTime = session.lastMessageAt || session.updatedAt || session.createdAt || '';

  if (sessionMessages && sessionMessages[session.id] && Array.isArray(sessionMessages[session.id])) {
    const msgs = sessionMessages[session.id];
    count = msgs.length;
    if (msgs.length > 0) {
      const lastMsg = msgs[msgs.length - 1];
      if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
        lastTime = lastMsg.timestamp || lastMsg.time;
      }
    }
  } else if (session.messageCount !== undefined && session.messageCount !== null) {
    count = session.messageCount;
  } else if (Array.isArray(session.messages) && session.messages.length > 0) {
    count = session.messages.length;
  } else {
    const stored = loadMessagesFromStorage(session.id);
    if (stored && Array.isArray(stored)) {
      count = stored.length;
      if (stored.length > 0) {
        const lastMsg = stored[stored.length - 1];
        if (lastMsg && (lastMsg.timestamp || lastMsg.time)) {
          lastTime = lastMsg.timestamp || lastMsg.time;
        }
      }
    }
  }

  return { count, lastTime };
}

export function formatSessionTime(val) {
  if (!val) return '';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();

    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = d.toDateString() === yesterday.toDateString();

    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (isToday) {
      return timeStr;
    }
    if (isYesterday) {
      return `Ieri ${timeStr}`;
    }

    const monthNames = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];
    const day = d.getDate();
    const month = monthNames[d.getMonth()];

    if (d.getFullYear() === now.getFullYear()) {
      return `${day} ${month} ${timeStr}`;
    }
    return `${day}/${d.getMonth() + 1}/${d.getFullYear().toString().slice(-2)} ${timeStr}`;
  } catch {
    return '';
  }
}

export function loadPosition(defaultWidth = 480, defaultHeight = 600) {
  try {
    const s = localStorage.getItem(POS_KEY);
    if (s) {
      const pos = JSON.parse(s);
      const ww = window.innerWidth || 1920;
      const wh = window.innerHeight || 1080;
      const valid = (
        pos.x === undefined || (
          typeof pos.x === 'number' && !isNaN(pos.x) &&
          pos.x > -defaultWidth && pos.x < ww - 100
        )
      ) && (
        pos.y === undefined || (
          typeof pos.y === 'number' && !isNaN(pos.y) &&
          pos.y > 0 && pos.y < wh - 100
        )
      );
      if (valid) return pos;
    }
  } catch {}
  return { x: undefined, y: undefined };
}

export function savePosition(pos) {
  try {
    if (pos && typeof pos === 'object') {
      const ww = window.innerWidth || 1920;
      const wh = window.innerHeight || 1080;
      const saved = { ...pos };
      if (saved.x !== undefined) {
        saved.x = Math.max(-480, Math.min(ww - 200, saved.x));
      }
      if (saved.y !== undefined) {
        saved.y = Math.max(10, Math.min(wh - 200, saved.y));
      }
      localStorage.setItem(POS_KEY, JSON.stringify(saved));
    }
  } catch (e) {}
}

export function loadSize(defaultWidth = 480, defaultHeight = 600) {
  try {
    const s = localStorage.getItem(SIZE_KEY);
    return s ? JSON.parse(s) : { width: defaultWidth, height: defaultHeight };
  } catch { return { width: defaultWidth, height: defaultHeight }; }
}

export function saveSize(size) {
  try {
    localStorage.setItem(SIZE_KEY, JSON.stringify(size));
  } catch (e) {}
}

export function formatSessionDate(dateStr) {
  const diff = new Date() - new Date(dateStr);
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Oggi';
  if (days === 1) return 'Ieri';
  if (days < 7) return `${days} giorni fa`;
  return new Date(dateStr).toLocaleDateString();
}

export function groupSessions(sessions) {
  return sessions.reduce((acc, s) => {
    const l = formatSessionDate(s.updatedAt);
    if (!acc[l]) acc[l] = [];
    acc[l].push(s);
    return acc;
  }, {});
}

export function getPendingTitleGeneration(sessionId) {
  return pendingTitleGenerations[sessionId];
}

export function setPendingTitleGeneration(sessionId, value) {
  if (value === undefined) {
    delete pendingTitleGenerations[sessionId];
  } else {
    pendingTitleGenerations[sessionId] = value;
  }
}