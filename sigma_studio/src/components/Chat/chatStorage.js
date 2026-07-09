// ==============================================================================
// CHAT STORAGE | Helpers per persistenza sessioni, messaggi e posizione
// ==============================================================================

const STORAGE_KEY = 'sigma_chat_sessions';
const POS_KEY = 'sigma_chat_position';
const SIZE_KEY = 'sigma_chat_size';
const LAST_MODEL_KEY = 'sigma_last_model';
const MAX_HISTORY = 20;
const MAX_ATTACHMENTS = 10;

export { STORAGE_KEY, POS_KEY, SIZE_KEY, LAST_MODEL_KEY, MAX_HISTORY, MAX_ATTACHMENTS };

export function loadLastModel(defaultModel = 'llama3.2') {
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

let pendingTitleGenerations = {};

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

export function createSession(model, name) {
  return {
    id: generateId(),
    name: name || `Chat ${new Date().toLocaleTimeString()}`,
    model: model || 'llama3.2',
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
}

export function loadSessions() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch { return []; }
}

export function saveSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch (e) {}
}

export function loadMessagesFromStorage(sessionId) {
  if (!sessionId) return null;
  try {
    const saved = localStorage.getItem(`sigma_chat_msgs_${sessionId}`);
    if (saved) {
      const p = JSON.parse(saved);
      if (Array.isArray(p) && p.length > 0) return p;
    }
  } catch (e) {}
  return null;
}

export function saveMessagesToStorage(sessionId, messages) {
  if (!sessionId) return;
  try {
    localStorage.setItem(`sigma_chat_msgs_${sessionId}`, JSON.stringify(messages));
  } catch (e) {}
}

export function loadPosition(defaultWidth = 480, defaultHeight = 600) {
  try {
    const s = localStorage.getItem(POS_KEY);
    if (s) {
      const pos = JSON.parse(s);
      // Validate: position must be within reasonable bounds
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
  // Default: bottom-right corner
  return { x: undefined, y: undefined };
}

export function savePosition(pos) {
  try {
    // Clamp position to valid viewport bounds before saving
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