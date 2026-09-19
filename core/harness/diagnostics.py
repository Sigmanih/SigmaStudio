# ==============================================================================
# core/harness/diagnostics.py — Fast Multi-Language Syntax Validator
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Provides fast, zero-external-dependency syntax validation for Python, JSON,
JavaScript, JSX, TypeScript, TSX, and CSS before and after edits.
"""

import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger("developer_diagnostics")


#: Percorso dello script che chiede il verdetto al parser vero, e memoria di
#: quanto scoperto la prima volta: `None` = non ancora provato, `False` = non
#: c'e' (node assente, o @babel/parser non installato), stringa = eseguibile.
_CHECKER_JS = Path(__file__).resolve().parents[2] / "tools" / "check_js_syntax.mjs"
_NODE_DISPONIBILE: Any = None


def _parse_with_babel(content: str, nome_file: str) -> Optional[Dict[str, Any]]:
    """Il verdetto del parser vero, o `None` se non e' consultabile.

    `None` non vuol dire «valido»: vuol dire «non lo so», e chi chiama ripiega
    sull'euristica dichiarandolo. Distinguere le due cose e' il punto: un
    controllo che non ha potuto girare non deve poter passare per un controllo
    superato.
    """
    global _NODE_DISPONIBILE

    if _NODE_DISPONIBILE is False:
        return None
    if not _CHECKER_JS.exists():
        _NODE_DISPONIBILE = False
        return None

    import subprocess

    try:
        esito = subprocess.run(
            ["node", str(_CHECKER_JS), "--stdin", nome_file],
            input=content.encode("utf-8"),
            capture_output=True,
            timeout=20.0,
        )
    except (FileNotFoundError, OSError):
        _NODE_DISPONIBILE = False
        log.info("[Diagnostics] node non disponibile: la sintassi JS/JSX usa l'euristica")
        return None
    except subprocess.TimeoutExpired:
        log.warning("[Diagnostics] il parser ha superato i 20 s su %s", nome_file)
        return None

    try:
        dati = json.loads(esito.stdout.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return None

    if dati.get("valid") is None:
        # Lo script c'e' ma @babel/parser no: inutile riprovare a ogni scrittura.
        _NODE_DISPONIBILE = False
        log.info("[Diagnostics] parser JS non disponibile (%s): si usa l'euristica",
                 dati.get("error"))
        return None

    _NODE_DISPONIBILE = True
    return dati


def _validate_brackets_and_quotes(code: str, language: str) -> Optional[str]:
    """Bilanciatore a caratteri per JS, JSX, TS, TSX, CSS. Solo come ripiego.

    Tre cose lo facevano sbagliare su un file su cinque di questo progetto, e
    sono corrette qui sotto:

    - **l'apostrofo nel testo JSX**. `<p>l'utente</p>` apriva una stringa che
      non si chiudeva piu', e tutto il resto del file spariva dentro di essa.
      Era la causa piu' frequente: 45 file su 206 venivano respinti, e quasi
      tutti per questo. Una stringa con apice singolo o doppio **non puo'
      attraversare una riga**: se arriva a fine riga senza chiudersi, non era
      una stringa, ed e' piu' onesto tornare a leggere codice che dichiarare
      un guasto;
    - **la regex letterale**. `/\\{/g` faceva contare una graffa aperta che nel
      codice non c'era. Una `/` inizia una regex solo se cio' che la precede
      non puo' chiudere un'espressione;
    - **l'interpolazione nel template literal**. Dentro `${...}` si torna a
      leggere codice, e le parentesi contano; il backtick di un template
      annidato pure.

    Resta approssimativo — non e' un parser — quindi il chiamante lo usa solo
    quando il parser vero non e' consultabile, e lo dichiara.
    """
    matching = {")": "(", "}": "{", "]": "["}
    aperte = "({["
    chiuse = ")}]"

    #: Dopo uno di questi, una `/` apre una regex: nessuno puo' chiudere
    #: un'espressione, quindi non ci puo' essere una divisione.
    PRIMA_DI_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {""}
    PAROLE_PRIMA_DI_REGEX = {
        "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
        "throw", "do", "else", "yield", "await", "case",
    }

    n = len(code)
    stack = []          # parentesi aperte: (carattere, riga, colonna)
    modi = ["code"]     # 'code' | 'template', impilati dalle interpolazioni
    i = 0
    riga = 1
    inizio_riga = 0
    prec = ""           # ultimo carattere significativo visto in modo codice
    parola = ""         # ultimo identificatore, per riconoscere `return /re/`

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if c == "\n":
            riga += 1
            i += 1
            inizio_riga = i
            continue

        if modi[-1] == "template":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                modi.pop()
                prec = "`"
                i += 1
                continue
            if c == "$" and nxt == "{":
                # Dentro l'interpolazione si torna a leggere codice: le
                # parentesi da qui in poi contano davvero.
                stack.append(("${", riga, i - inizio_riga + 1))
                modi.append("code")
                prec = "{"
                parola = ""
                i += 2
                continue
            i += 1
            continue

        # --- modo codice ---

        if c == "/" and nxt == "/":
            fine_riga = code.find("\n", i)
            i = n if fine_riga == -1 else fine_riga
            continue

        if c == "/" and nxt == "*":
            fine_commento = code.find("*/", i + 2)
            if fine_commento == -1:
                return "Commento a blocchi /* ... */ non chiuso."
            riga += code.count("\n", i, fine_commento)
            ultimo_a_capo = code.rfind("\n", i, fine_commento)
            if ultimo_a_capo != -1:
                inizio_riga = ultimo_a_capo + 1
            i = fine_commento + 2
            continue

        if c in ("'", '"'):
            # Una stringa con apice non attraversa una riga. Se non si chiude
            # entro fine riga, quell'apice era testo — quasi sempre
            # l'apostrofo di una parola italiana dentro il JSX — e insistere
            # significherebbe perdere tutto il resto del file dentro una
            # stringa che non esiste.
            j = i + 1
            chiusa = False
            while j < n and code[j] != "\n":
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == c:
                    chiusa = True
                    break
                j += 1
            if chiusa:
                i = j + 1
                prec = c
                parola = ""
                continue
            i += 1
            continue

        if c == "`":
            modi.append("template")
            i += 1
            continue

        if c == "/":
            # In JSX la barra compare in due posti dove non e' ne' divisione ne'
            # regex: `<FileText />` e `</div>`. Senza questa guardia la prima
            # veniva letta come inizio di regex — `prec` e' `}` o `>` — e la
            # finta regex si mangiava tutto fino alla barra successiva, spesso
            # dentro una stringa. Era la causa dei falsi allarmi rimasti.
            if nxt == ">" or prec == "<":
                prec = ">"
                parola = ""
                i += 2 if nxt == ">" else 1
                continue
            if parola in PAROLE_PRIMA_DI_REGEX or prec in PRIMA_DI_REGEX:
                j = i + 1
                in_classe = False
                while j < n and code[j] != "\n":
                    if code[j] == "\\":
                        j += 2
                        continue
                    if code[j] == "[":
                        in_classe = True
                    elif code[j] == "]":
                        in_classe = False
                    elif code[j] == "/" and not in_classe:
                        break
                    j += 1
                if j < n and code[j] == "/":
                    i = j + 1
                    while i < n and code[i].isalpha():
                        i += 1
                    prec = "/"
                    parola = ""
                    continue
            prec = "/"
            parola = ""
            i += 1
            continue

        if c in aperte:
            stack.append((c, riga, i - inizio_riga + 1))
            prec = c
            parola = ""
            i += 1
            continue

        if c in chiuse:
            if not stack:
                return (f"Parentesi chiusa non corrispondente '{c}' "
                        f"alla riga {riga}, colonna {i - inizio_riga + 1}")
            top_char, top_riga, top_col = stack.pop()
            if top_char == "${":
                if c != "}":
                    return (f"Interpolazione aperta alla riga {top_riga} "
                            f"e chiusa con '{c}' alla riga {riga}")
                modi.pop()
                prec = "}"
                parola = ""
                i += 1
                continue
            if top_char != matching[c]:
                return (f"Parentesi non corrispondente: aperta '{top_char}' alla riga "
                        f"{top_riga} ma chiusa '{c}' alla riga {riga}")
            prec = c
            parola = ""
            i += 1
            continue

        if c.isalnum() or c in "_$":
            j = i
            while j < n and (code[j].isalnum() or code[j] in "_$"):
                j += 1
            parola = code[i:j]
            prec = code[j - 1]
            i = j
            continue

        if not c.isspace():
            prec = c
            parola = ""
        i += 1

    if len(modi) > 1 or modi[-1] == "template":
        return "Template literal con backtick non chiuso."
    if stack:
        top_char, top_riga, top_col = stack[-1]
        if top_char == "${":
            return f"Interpolazione aperta alla riga {top_riga}, colonna {top_col} non chiusa."
        return f"Parentesi aperta '{top_char}' alla riga {top_riga}, colonna {top_col} non chiusa."

    return None


def _check_jsx_component_imports(content: str) -> Optional[str]:
    """Detects capitalized JSX components (<Component ...>) used without import or definition."""
    raw_tags = re.findall(r"<([A-Z][a-zA-Z0-9_]*)", content)
    if not raw_tags:
        return None

    unique_tags = set(raw_tags)
    builtins = {"Fragment", "React"}

    # Trova identificatori importati: import Foo from ... oppure import { Bar, Baz as B } from ...
    imported = set()
    for m in re.finditer(r"import\s+(?:(?:\*\s+as\s+([A-Za-z0-9_]+))|([A-Za-z0-9_]+)|(?:\{([^}]+)\}))", content):
        if m.group(1):
            imported.add(m.group(1).strip())
        if m.group(2):
            imported.add(m.group(2).strip())
        if m.group(3):
            for part in m.group(3).split(","):
                cleaned = part.strip().split(" as ")[-1].strip()
                if cleaned:
                    imported.add(cleaned)

    # Trova definizioni locali: function Foo, class Foo, const Foo = ...
    defined = set()
    for m in re.finditer(r"(?:function|class|const|let|var)\s+([A-Z][a-zA-Z0-9_]*)", content):
        defined.add(m.group(1).strip())

    missing = unique_tags - imported - defined - builtins
    if missing:
        missing_list = ", ".join(f"<{t}>" for t in sorted(missing))
        return (
            f"Componenti JSX utilizzati ma non importati né definiti: {missing_list}. "
            "Aggiungi l'import in testa al file o definisci il componente."
        )
    return None


def _fast_lint_rust(content: str, language: str) -> Optional[Dict[str, Any]]:
    """Tenta la validazione nativa tramite il tool fast_lint del micro-kernel Rust."""
    try:
        from core.engine.backends.sigmarust_backend import _DEFAULT_RUST_URL, _intestazioni
        import urllib.request
        payload = json.dumps({
            "tool": "fast_lint",
            "params": {"code": content, "language": language}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{_DEFAULT_RUST_URL}/api/engine/tools/execute",
            data=payload,
            headers=_intestazioni({"Content-Type": "application/json"}),
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success"):
                return {
                    "valid": data.get("valid", True),
                    "error": data.get("message") if not data.get("valid") else None,
                    "line": (data.get("errors") or [{}])[0].get("line") if data.get("errors") else None
                }
    except Exception:
        return None
    return None


def validate_code_syntax(file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Validates syntax for Python, JSON, JavaScript/JSX/TypeScript, CSS, and Rust."""
    p = Path(file_path)
    ext = p.suffix.lower()

    if content is None:
        if not p.is_file():
            return {"valid": True, "language": "unknown", "error": None}
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as ex:
            return {"valid": False, "language": "unknown", "error": f"Impossibile leggere file: {ex}"}

    # 1. Python (.py)
    if ext == ".py":
        try:
            ast.parse(content, filename=str(p))
            return {"valid": True, "language": "python", "error": None}
        except SyntaxError as syn:
            return {
                "valid": False,
                "language": "python",
                "error": f"Errore di sintassi Python (riga {syn.lineno}): {syn.msg}",
                "line": syn.lineno,
            }

    # 2. JSON (.json)
    if ext in (".json", ".jsonc") and not ext == ".jsonc":
        # Tentativo veloce tramite fast_lint del kernel Rust se attivo
        rust_lint = _fast_lint_rust(content, "json")
        if rust_lint is not None:
            return {"valid": rust_lint["valid"], "language": "json", "error": rust_lint["error"]}
        try:
            json.loads(content)
            return {"valid": True, "language": "json", "error": None}
        except json.JSONDecodeError as jde:
            return {
                "valid": False,
                "language": "json",
                "error": f"Errore di formattazione JSON (riga {jde.lineno}): {jde.msg}",
                "line": jde.lineno,
            }

    # 2b. Rust (.rs)
    if ext == ".rs":
        rust_lint = _fast_lint_rust(content, "rust")
        if rust_lint is not None and not rust_lint["valid"]:
            return {"valid": False, "language": "rust", "error": rust_lint["error"]}
        err = _validate_brackets_and_quotes(content, "rust")
        if err:
            return {"valid": False, "language": "rust", "error": err}
        return {"valid": True, "language": "rust", "error": None}

    # 3. JavaScript, JSX, TypeScript, TSX (.js, .jsx, .ts, .tsx)
    if ext in (".js", ".jsx", ".ts", ".tsx"):
        lang = "javascript" if ext in (".js", ".jsx") else "typescript"

        # Il giudice e' il parser vero: e' lo stesso che il bundler usa, e su
        # questo progetto (testo italiano dentro il JSX, regex con graffe,
        # template literal annidati) e' l'unico che non sbaglia.
        verdetto = _parse_with_babel(content, p.name)
        if verdetto is not None:
            if verdetto.get("valid"):
                esito = {"valid": True, "language": lang, "error": None}
                # Un componente usato senza import compila e rompe a schermo.
                # Non e' un errore di sintassi e non deve bloccare la scrittura,
                # ma sparire in `log.debug` significa non dirlo a nessuno: qui
                # torna all'agente come avviso, dentro il risultato del tool.
                if ext in (".jsx", ".tsx"):
                    avviso = _check_jsx_component_imports(content)
                    if avviso:
                        esito["warning"] = avviso
                return esito
            riga = verdetto.get("line")
            dove = f" (riga {riga})" if riga else ""
            return {
                "valid": False,
                "language": lang,
                "error": f"Errore di sintassi{dove}: {verdetto.get('error')}",
                "line": riga,
            }

        # Ripiego quando node o @babel/parser non ci sono. Il bilanciatore a
        # caratteri e' approssimativo per costruzione, quindi qui segnala solo
        # cio' di cui puo' essere sicuro: vedi `_validate_brackets_and_quotes`.
        err = _validate_brackets_and_quotes(content, lang)
        if err:
            return {"valid": False, "language": lang, "error": err, "fonte": "euristica"}
        return {"valid": True, "language": lang, "error": None, "fonte": "euristica"}

    # 4. CSS e SCSS: nessun parser esterno, il bilanciamento basta
    if ext in (".css", ".scss"):
        err = _validate_brackets_and_quotes(content, "css")
        if err:
            return {"valid": False, "language": "css", "error": err}
        return {"valid": True, "language": "css", "error": None}

    return {"valid": True, "language": ext.lstrip("."), "error": None}
