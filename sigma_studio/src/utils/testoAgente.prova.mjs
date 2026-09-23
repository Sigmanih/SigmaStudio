// ==============================================================================
// sigma_studio/src/utils/testoAgente.prova.mjs — La prova del normalizzatore
// ==============================================================================
/**
 * `node src/utils/testoAgente.prova.mjs` (dalla cartella `sigma_studio`).
 *
 * Perche' a mano e non con un framework: il frontend non ha un runner, e
 * aggiungerne uno per quattro casi sarebbe una dipendenza in piu'. Questa prova
 * non ha dipendenze, esce con codice diverso da zero se qualcosa non torna e
 * chiude con la riga SIGMA-CHECK, che e' quella che l'harness legge.
 */

import { normalizzaTestoAgente, sciogliEscape, prosaDaCorpo } from './testoAgente.js';

const CASI = [
  {
    nome: 'corpo JSON valido: la prosa esce e gli a capo sono veri',
    dentro: '{"summary": "## Fatto\\n\\n- riga uno\\n- riga due"}',
    atteso: (t) => t.includes('## Fatto') && t.includes('\n') && !t.includes('\\n'),
  },
  {
    nome: 'corpo JSON rotto da virgolette non protette: la prosa si recupera',
    dentro: '{"summary": "sono ancora "DA FARE" i criteri 1 e 3"}',
    atteso: (t) => t.includes('DA FARE') && !t.includes('{"summary"'),
  },
  {
    nome: 'recinto di codice: sparisce il recinto e resta il testo',
    dentro: '```json\n{"summary": "# Titolo\\n\ntesto"}\n```',
    atteso: (t) => !t.includes('```') && t.includes('# Titolo'),
  },
  {
    nome: 'testo normale: non si tocca',
    dentro: 'Risposta normale\ncon due righe.',
    atteso: (t) => t === 'Risposta normale\ncon due righe.',
  },
  {
    nome: 'rete sugli escape: nessun a capo vero ma sequenze \\n',
    dentro: 'prima riga\\nseconda riga',
    atteso: (t) => t.includes('\n') && !t.includes('\\n'),
  },
  {
    nome: 'sequenze sciolte in una riga sola',
    dentro: 'a\\nb\\tc\\"d',
    atteso: (t) => t === 'a\nb  c"d',
  },
  {
    nome: 'corpo che e una chiamata a un tool: resta com era',
    dentro: '{"path": "x.py", "content": "1"}',
    atteso: (t) => t.includes('{"path"'),
  },
];

let problems = 0;
for (const caso of CASI) {
  let esito;
  try {
    esito = normalizzaTestoAgente(caso.dentro);
  } catch (errore) {
    problems += 1;
    console.log(`  ROSSO  ${caso.nome}: ha sollevato ${errore.message}`);
    continue;
  }
  if (caso.atteso(esito)) {
    console.log(`  ok     ${caso.nome}`);
  } else {
    problems += 1;
    console.log(`  ROSSO  ${caso.nome}: ${JSON.stringify(esito).slice(0, 160)}`);
  }
}

// Due funzioni di servizio, provate a parte perche' il resto ci si appoggia.
const servizio = [
  ['sciogliEscape', sciogliEscape('a\\nb') === 'a\nb'],
  ['prosaDaCorpo valido', prosaDaCorpo('{"message": "ciao"}') === 'ciao'],
  ['prosaDaCorpo rotto', prosaDaCorpo('{"message": "ciao "mondo""}') === 'ciao "mondo"'],
];

for (const [nome, bene] of servizio) {
  console.log(`  ${bene ? 'ok    ' : 'ROSSO '} ${nome}`);
  if (!bene) problems += 1;
}

const checked = CASI.length + servizio.length;
console.log(`SIGMA-CHECK {"check": "testoAgente", "checked": ${checked}, "problems": ${problems}}`);
process.exit(problems ? 1 : 0);
