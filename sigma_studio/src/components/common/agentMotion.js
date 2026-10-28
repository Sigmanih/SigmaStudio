// ==============================================================================
// Come si muove l'agente nella plancia, deciso da quello che sta facendo
// L'attivita' arriva da agentActivity (la chat e' l'unica fonte). Decidono le
// regole di agentMotionRules.json: misurate con tools/agenti_3d/banco_decisori.py
// battono i modelli zero-shot provati (Laya, Laya multilingue, GLiClass), che
// sbagliavano proprio i casi ovvi, e costano 0 ms anche sul Pi senza modello.
// ==============================================================================
import REGOLE from './agentMotionRules.json';

// Modalita' che il personaggio sa eseguire (vedi CyberSpace3DCanvas, sezione 7c)
export const MOTION_MODES = ['posa', 'console', 'olotavolo', 'presenta', 'collega'];

const compila = (lista) => lista.map(r => ({ modo: r.modo, re: new RegExp(r.schema, 'i') }));
const DETTAGLIO = compila(REGOLE.dettaglio);
const STRUMENTO = compila(REGOLE.strumento);

// Stessa logica di applica_regole() nel banco di prova: stati certi, indizi nel
// dettaglio, nome dello strumento, stato
export function motionFor(activity) {
  const a = activity || {};
  const state = a.state || 'idle';
  if (REGOLE.stati_certi[state]) return REGOLE.stati_certi[state];
  const detail = String(a.detail || '');
  if (detail) {
    const hit = DETTAGLIO.find(r => r.re.test(detail));
    if (hit) return hit.modo;
  }
  const tool = String(a.tool || '').toLowerCase();
  if (tool) {
    const hit = STRUMENTO.find(r => r.re.test(tool));
    if (hit) return hit.modo;
  }
  return REGOLE.stato[state] || REGOLE.predefinito;
}
