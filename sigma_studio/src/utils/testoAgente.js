// ==============================================================================
// sigma_studio/src/utils/testoAgente.js — Il testo che l'agente ha scritto
// Sigma Studio v8 — Developer Studio
// ==============================================================================
/**
 * Riporta alla luce la prosa che un agente ha scritto dentro un corpo JSON.
 *
 * **Il difetto, visto dal vivo il 23 settembre 2026.** In chat l'agente
 * rispondeva con `{"summary": "## Task #1 completato: Analisi TTFT\n\n- ..."}`:
 * l'utente leggeva gli a capo come `\n` e nessun titolo, nessun elenco, nessun
 * grassetto. Non era colpa di chi disegna il markdown — che c'era gia' e
 * funzionava — ma del testo: dentro una stringa JSON un `##` non sta a inizio
 * riga e un `\n` non e' un a capo.
 *
 * Due cause, e servono tutte e due le strade:
 *
 * - il corpo e' JSON **valido**: basta leggerne il campo di prosa;
 * - il corpo **non lo e'**, tipicamente per una virgoletta non protetta dentro
 *   la prosa (`sono ancora "DA FARE"`): si prende il testo fra la chiave e
 *   l'ultima virgoletta, senza pretese. E' lo stesso caso che faceva rifiutare
 *   otto volte il riepilogo di `complete_goal`, e che il ciclo ora recupera dal
 *   lato suo — qui si recupera per chi lo legge.
 *
 * Resta una rete per i trascritti vecchi: un testo senza un solo a capo vero ma
 * pieno di sequenze `\n` e' un testo scritto per un JSON e mai sciolto.
 *
 * Sta in un file suo, e non dentro il componente che lo usa, perche' cosi' si
 * puo' provare: `node src/utils/testoAgente.prova.mjs`.
 */

/** Le chiavi con cui un agente mette la prosa dentro un corpo JSON. */
export const CHIAVI_DI_PROSA = [
  'summary', 'riepilogo', 'message', 'messaggio', 'esito',
  'content', 'contenuto', 'text', 'output', 'descrizione',
];

const CHIAVI = CHIAVI_DI_PROSA.join('|');

//: Le chiavi che dicono «questa e' una chiamata a un tool, non un riepilogo».
//:
//: Servono perche' `content` e `output` sono prosa in un riepilogo e sono il
//: file intero in una scrittura: senza questa distinzione il testo da mostrare
//: diventava il contenuto del file. L'ha trovato la prova, non l'occhio -
//: `{"path": "x.py", "content": "1"}` usciva come `1`.
const CHIAVI_DI_CHIAMATA = [
  'path', 'tool', 'action', 'command', 'file', 'query', 'tasks', 'criteria',
  'old_string', 'old', 'new_string', 'new', 'raw_block',
];

const sembraUnaChiamata = (corpo) => {
  try {
    const dati = JSON.parse(corpo);
    if (dati && typeof dati === 'object' && !Array.isArray(dati)) {
      return Object.keys(dati).some((k) => CHIAVI_DI_CHIAMATA.includes(k));
    }
  } catch (e) {
    // Corpo non valido: si guarda il testo, che e' il caso delle virgolette
    // non protette - e li' `path` c'e' comunque.
  }
  return new RegExp(`"(${CHIAVI_DI_CHIAMATA.join('|')})"\\s*:`).test(corpo);
};

/** Scioglie le sequenze di escape di un testo che doveva essere JSON. */
export const sciogliEscape = (testo) => String(testo || '')
  .replace(/\\r\\n/g, '\n')
  .replace(/\\n/g, '\n')
  .replace(/\\r/g, '\n')
  .replace(/\\t/g, '  ')
  .replace(/\\"/g, '"');

/** Il testo di prosa dentro un corpo JSON, valido o no che sia. */
export const prosaDaCorpo = (corpo) => {
  try {
    const dati = JSON.parse(corpo);
    const chiave = CHIAVI_DI_PROSA.find(
      (k) => dati && typeof dati[k] === 'string' && dati[k].trim()
    );
    if (chiave) return dati[chiave];
  } catch (e) {
    // JSON non valido: si prende la prosa fra la chiave e l'ultima virgoletta,
    // perche' una virgoletta dentro la prosa e' il motivo per cui siamo qui.
    const m = corpo.match(new RegExp(`"(${CHIAVI})"\\s*:\\s*"([\\s\\S]*)"\\s*\\}?\\s*$`));
    if (m && m[2] && m[2].trim()) return sciogliEscape(m[2]);
  }
  return '';
};

/**
 * Il testo pronto da dare al markdown.
 *
 * Ordine: prima il recinto (che sparisce insieme al contenuto), poi il corpo
 * nudo, e solo alla fine la rete sugli escape. Un testo normale esce identico.
 */
export const normalizzaTestoAgente = (testo) => {
  if (!testo || typeof testo !== 'string') return testo;
  let fuori = testo;
  const chiave = new RegExp(`"(${CHIAVI})"\\s*:`);

  const recintato = fuori.match(/```(?:json)?\s*(\{[\s\S]{0,20000}?\})\s*```/);
  if (recintato && chiave.test(recintato[1]) && !sembraUnaChiamata(recintato[1])) {
    const prosa = prosaDaCorpo(recintato[1]);
    if (prosa) fuori = fuori.replace(recintato[0], prosa);
  }

  const nudo = fuori.match(/\{[\s\S]{0,20000}?\}/);
  if (nudo && chiave.test(nudo[0]) && !sembraUnaChiamata(nudo[0])) {
    const prosa = prosaDaCorpo(nudo[0]);
    if (prosa) fuori = fuori.replace(nudo[0], prosa);
  }

  if (fuori.indexOf('\\n') !== -1 && fuori.indexOf('\n') === -1) {
    fuori = sciogliEscape(fuori);
  }

  return fuori;
};
