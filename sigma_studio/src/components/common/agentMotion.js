// ==============================================================================
// Come si muove l'agente nella plancia, deciso da quello che sta facendo
// L'attivita' arriva da agentActivity (la chat e' l'unica fonte). La scelta del
// movimento la fa Laya, il modello decisionale del modulo sigma_laya_router, in
// ~40 ms; se il modulo non e' installato o il modello non e' caricato si usa la
// tabella qui sotto, cosi' la plancia funziona uguale anche sul Pi senza Laya.
// ==============================================================================

// Modalita' che il personaggio sa eseguire (vedi CyberSpace3DCanvas, sezione 7c)
export const MOTION_MODES = ['posa', 'console', 'olotavolo', 'presenta'];

// Ripiego deterministico: lo stesso significato dei criteri dati a Laya
const FALLBACK = {
  idle: 'posa',
  thinking: 'console',
  tool: 'console',
  writing: 'console',
  browsing: 'olotavolo',
  done: 'presenta',
  error: 'presenta'
};

// La domanda a Laya: una scelta tra le modalita', descritte nel linguaggio con
// cui il modello e' stato addestrato (inglese)
const MOTION_QUESTION = {
  movimento: {
    type: 'choice',
    instructions: 'An AI agent is shown as a 3D avatar on the bridge of a starship. '
      + 'Given what the agent is doing right now, choose where its avatar should be and what it should do.',
    criteria: {
      console: 'The agent is reasoning, writing text or code, or running a tool: it works seated at its own console',
      olotavolo: 'The agent is searching the web, reading sources or exploring data: it studies the central holographic table',
      presenta: 'The agent has finished or hit a problem and reports to the user: it stands and faces the user',
      posa: 'The agent is idle and waiting for a request: it stands still in front of its station'
    }
  }
};

// Senza attesa di Laya: la plancia 2D lo usa per l'etichetta della scheda
export const motionFallback = (state) => FALLBACK[state] || 'posa';

let layaAvailable = true;

const describe = (a) => [
  `Agent ${a.roleName || a.roleId || 'unknown'} is ${a.state || 'idle'}.`,
  a.tool ? `Tool in use: ${a.tool}.` : '',
  a.detail ? `Detail: ${String(a.detail).slice(0, 160)}.` : ''
].filter(Boolean).join(' ');

export async function decideAgentMotion(activity) {
  const fallback = FALLBACK[activity && activity.state] || 'posa';
  // Senza attivita' non c'e' niente da decidere: evita una chiamata per l'idle
  if (!activity || activity.state === 'idle' || !layaAvailable) return fallback;
  try {
    const res = await fetch('/api/laya/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: describe(activity), questions: MOTION_QUESTION })
    });
    if (res.status === 404) {
      // Modulo non installato: non lo si richiede a ogni cambio di stato
      layaAvailable = false;
      return fallback;
    }
    const data = await res.json();
    const choice = data && data.success && data.result && data.result.movimento && data.result.movimento.choice;
    if (!data.success && /non disponibile|not available/i.test(String(data.error || ''))) layaAvailable = false;
    return MOTION_MODES.includes(choice) ? choice : fallback;
  } catch {
    return fallback;
  }
}
