// ==============================================================================
// Attivita' dell'agente condivisa tra chat, Home e plancia 3D
// La chat e' l'unica fonte: chi mostra l'agente (ritratto, plancia, HUD) legge
// da qui invece di ricalcolare lo stato, cosi' tutto racconta la stessa cosa.
// ==============================================================================
import { useEffect, useState } from 'react';

const EVENT = 'sigma-agent-activity';
export const IDLE_ACTIVITY = { state: 'idle', tool: '', detail: '', roleId: '', roleName: '', image: '', color: '' };

export const ACTIVITY_LABEL = {
  idle: 'Pronto',
  thinking: 'Sta ragionando',
  tool: 'Sta usando uno strumento',
  browsing: 'Sta cercando sul web',
  writing: 'Sta scrivendo',
  done: 'Ha finito',
  error: 'Qualcosa e\' andato storto'
};

// Frase breve per spazi stretti (barra della Home, intestazione della chat):
// il nome del tool dice piu' di "sta usando uno strumento".
export function activityText(activity = IDLE_ACTIVITY) {
  if (activity.state === 'tool' && activity.tool) return `Usa ${activity.tool}`;
  return ACTIVITY_LABEL[activity.state] || ACTIVITY_LABEL.idle;
}

// Piu' istanze della chat (scheda e pannello flottante) possono essere montate
// insieme: si tiene lo stato di ognuna e vince l'ultima che sta lavorando.
const sources = new Map();
let current = IDLE_ACTIVITY;

const aggregate = () => {
  let best = null;
  for (const entry of sources.values()) {
    if (entry.activity.state === 'idle') continue;
    if (!best || entry.at > best.at) best = entry;
  }
  return best ? best.activity : (sources.size ? [...sources.values()].pop().activity : IDLE_ACTIVITY);
};

const sameActivity = (a, b) => a.state === b.state && a.tool === b.tool && a.detail === b.detail && a.roleId === b.roleId;

export function publishAgentActivity(sourceId, activity) {
  const prev = sources.get(sourceId);
  if (prev && sameActivity(prev.activity, activity)) return;
  sources.set(sourceId, { activity, at: Date.now() });
  const next = aggregate();
  if (sameActivity(current, next)) return;
  current = next;
  window.dispatchEvent(new CustomEvent(EVENT, { detail: current }));
}

export function releaseAgentActivity(sourceId) {
  if (!sources.delete(sourceId)) return;
  current = aggregate();
  window.dispatchEvent(new CustomEvent(EVENT, { detail: current }));
}

export function getAgentActivity() {
  return current;
}

export function useAgentActivity() {
  const [activity, setActivity] = useState(current);
  useEffect(() => {
    const onActivity = (e) => setActivity(e.detail || IDLE_ACTIVITY);
    window.addEventListener(EVENT, onActivity);
    setActivity(current);
    return () => window.removeEventListener(EVENT, onActivity);
  }, []);
  return activity;
}

const TOOL_WEB = /web|browse|search_web|fetch_url|http/i;

// Lo stato nasce dall'ultimo messaggio dell'assistente, aggiornato dallo streaming:
// le azioni hanno status 'running' finche' il tool non risponde.
export function deriveAgentActivity({ loading, messages }) {
  const last = Array.isArray(messages) && messages.length ? messages[messages.length - 1] : null;
  const assistant = last && last.role === 'assistant' ? last : null;

  if (!loading) {
    if (assistant && assistant.error) return { state: 'error', tool: '', detail: '' };
    return { state: 'idle', tool: '', detail: '' };
  }

  const actions = assistant && Array.isArray(assistant.actions_log) ? assistant.actions_log : [];
  const running = [...actions].reverse().find(a => a && a.status === 'running');
  if (running) {
    const tool = running.tool || running.type || 'tool';
    return {
      state: TOOL_WEB.test(tool) ? 'browsing' : 'tool',
      tool,
      detail: running.message || running.path || running.command || running.query || ''
    };
  }

  if (assistant && assistant.streamingThinking) return { state: 'thinking', tool: '', detail: '' };
  if (assistant && assistant.streaming && assistant.content && assistant.content.trim()) {
    return { state: 'writing', tool: '', detail: '' };
  }
  return { state: 'thinking', tool: '', detail: assistant?.statusMessage || '' };
}
