# ==============================================================================
# core/training/code_exec.py — Verifica per esecuzione delle suite di codice
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Esegue i test unitari ufficiali di HumanEval e MBPP sul codice generato.

HumanEval e MBPP si misurano in pass@1: il codice passa se supera le asserzioni
della suite. Non esiste una scorciatoia testuale — confrontare il codice del
modello con la soluzione di riferimento parola per parola boccia qualunque
implementazione corretta ma scritta in modo diverso.

Il codice generato viene eseguito in un sottoprocesso Python isolato (`-I`), con
directory di lavoro temporanea e timeout: l'esito e' un fallimento del test, mai
un blocco del worker di benchmark. Resta comunque esecuzione di codice non
verificato prodotto da un modello: la funzione gira solo su richiesta esplicita
di una suite di codice, in locale.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from core.logger import get_logger
from core.training.answer_parser import extract_python_code

log = get_logger(__name__)

#: Secondi concessi a un singolo item prima di dichiarare il timeout.
DEFAULT_TIMEOUT = 12

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_TIMEOUT = "timeout"
STATUS_NO_CODE = "no_code"
STATUS_NO_TESTS = "no_tests"
STATUS_ERROR = "error"


#: Tracce minime che il testo estratto sia codice e non prosa di rifiuto.
_CODE_MARKERS = ("def ", "import ", "return", "lambda", "=", "class ")


def looks_like_code(code: str) -> bool:
    """Distingue "non so risolverlo" da un tentativo di soluzione.

    Serve al verdetto: codice sintatticamente rotto e' un pass@1 mancato, mentre
    una risposta senza alcun codice non e' misurabile e va rivista a parte.
    """
    return any(marker in code for marker in _CODE_MARKERS)


def _normalize_newlines(text: str) -> str:
    """Uniforma i fine riga: MBPP arriva con CRLF.

    Scritto senza normalizzare su Windows diventava CRLF doppio e il tokenizer
    Python rifiutava anche la soluzione di riferimento.
    """
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def build_test_script(item: dict, code: str) -> str | None:
    """Compone il modulo eseguibile: codice del modello + test ufficiali.

    Restituisce None quando l'item non porta test verificabili (cache scaricata
    con uno schema vecchio), cosi' che il chiamante possa mandarlo in revisione
    invece di contarlo come errore del modello.
    """
    verification = item.get("verification") or {}
    suite = (item.get("suite") or "").lower()
    code = _normalize_newlines(code)

    if suite == "humaneval":
        test_code = _normalize_newlines(verification.get("test") or "")
        entry_point = verification.get("entry_point") or ""
        if not test_code or not entry_point:
            return None
        return f"{code}\n\n{test_code}\n\ncheck({entry_point})\nprint('SIGMA_OK')\n"

    if suite == "mbpp":
        asserts = [_normalize_newlines(a) for a in (verification.get("test_list") or [])]
        if not asserts:
            return None
        setup = _normalize_newlines(verification.get("test_setup_code") or "")
        body = "\n".join(asserts)
        return f"{code}\n\n{setup}\n{body}\nprint('SIGMA_OK')\n"

    return None


def run_code_item(item: dict, output_text: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Verifica un item di codice eseguendo i test ufficiali della suite."""
    code = extract_python_code(output_text, item.get("prompt", ""))
    if not code.strip() or not looks_like_code(code):
        return {"status": STATUS_NO_CODE, "detail": "Nessun codice Python nella risposta"}

    script = build_test_script(item, code)
    if script is None:
        return {
            "status": STATUS_NO_TESTS,
            "detail": "Item senza test ufficiali: riscarica la suite per abilitare pass@1",
        }

    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="sigma_bench_")
        script_path = os.path.join(tmp_dir, "candidate.py")
        # newline="\n": senza questo Windows riscrive ogni \n come \r\n e il
        # codice già normalizzato tornerebbe a righe doppie.
        with open(script_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(script)

        proc = subprocess.run(
            [sys.executable, "-I", script_path],
            cwd=tmp_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0 and "SIGMA_OK" in (proc.stdout or ""):
            return {"status": STATUS_PASSED, "detail": "Tutti i test ufficiali superati"}

        stderr = (proc.stderr or "").strip().splitlines()
        detail = stderr[-1] if stderr else f"Uscita con codice {proc.returncode}"
        return {"status": STATUS_FAILED, "detail": detail[:400]}

    except subprocess.TimeoutExpired:
        return {"status": STATUS_TIMEOUT, "detail": f"Esecuzione oltre {timeout}s (probabile ciclo infinito)"}
    except Exception as err:
        log.warning("Verifica codice non riuscita per %s: %s", item.get("id"), err)
        return {"status": STATUS_ERROR, "detail": str(err)[:400]}
    finally:
        if tmp_dir:
            _cleanup(tmp_dir)


def _cleanup(path: str) -> None:
    """Rimuove la directory temporanea senza far fallire la valutazione."""
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception as err:
        log.debug("Pulizia di %s non riuscita: %s", path, err)
