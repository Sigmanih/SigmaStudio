// tools/check_js_syntax.mjs — Verdetto di sintassi vero per JS/JSX/TS/TSX.
//
// Il bilanciatore a caratteri in core/harness/diagnostics.py non sa distinguere
// una regex da una divisione, ne' un apostrofo dentro il testo JSX da una
// stringa aperta. Sui file di questo progetto — testo italiano dentro il JSX,
// regex con graffe, template literal annidati — sbagliava abbastanza spesso da
// far venire la tentazione di spegnerlo, che e' esattamente cio' che e'
// successo. Qui il verdetto lo da' il parser vero, lo stesso che Vite usa.
//
// Uso:  node tools/check_js_syntax.mjs <percorso>
//       node tools/check_js_syntax.mjs --stdin <nome-per-le-estensioni>
//
// Esce sempre con codice 0 e scrive su stdout un JSON:
//   {"valid": true}
//   {"valid": false, "error": "...", "line": N, "column": M}
//   {"valid": null,  "error": "parser non disponibile"}   → chi chiama ripiega

import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const qui = dirname(fileURLToPath(import.meta.url));

function esito(o) {
  process.stdout.write(JSON.stringify(o));
  process.exit(0);
}

// @babel/parser vive sotto sigma_studio/node_modules: il require va ancorato
// li', non alla cartella di questo script.
let parse;
try {
  const require = createRequire(join(qui, '..', 'sigma_studio', 'package.json'));
  ({ parse } = require('@babel/parser'));
} catch {
  try {
    const require = createRequire(import.meta.url);
    ({ parse } = require('@babel/parser'));
  } catch (e) {
    esito({ valid: null, error: `parser non disponibile: ${e.message}` });
  }
}

const argomenti = process.argv.slice(2);
if (argomenti.length === 0) {
  esito({ valid: null, error: 'nessun percorso indicato' });
}

let codice;
let nome;
if (argomenti[0] === '--stdin') {
  nome = argomenti[1] || 'anonimo.jsx';
  codice = readFileSync(0, 'utf8');
} else {
  nome = argomenti[0];
  try {
    codice = readFileSync(nome, 'utf8');
  } catch (e) {
    esito({ valid: null, error: `impossibile leggere il file: ${e.message}` });
  }
}

const ext = extname(nome).toLowerCase();
const plugins = ['jsx'];
if (ext === '.ts' || ext === '.tsx') plugins.push('typescript');
// I file .js di questo progetto usano la sintassi moderna di React: le
// estensioni sperimentali piu' comuni vanno accese o un file valido verrebbe
// respinto per una funzionalita' che il bundler accetta.
plugins.push('decorators-legacy', 'classProperties', 'classPrivateProperties',
             'classPrivateMethods', 'importMeta', 'topLevelAwait',
             'dynamicImport', 'optionalChaining', 'nullishCoalescingOperator');

try {
  parse(codice, {
    sourceType: 'module',
    allowReturnOutsideFunction: true,
    allowAwaitOutsideFunction: true,
    errorRecovery: false,
    plugins,
  });
  esito({ valid: true });
} catch (e) {
  const pos = e.loc || {};
  esito({
    valid: false,
    error: String(e.message || e).replace(/\s*\(\d+:\d+\)\s*$/, ''),
    line: pos.line ?? null,
    column: pos.column != null ? pos.column + 1 : null,
  });
}
