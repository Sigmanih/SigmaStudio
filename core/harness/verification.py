# ==============================================================================
# core/harness/verification.py — Analisi strutturata delle prove di verifica
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Analisi strutturata dell'esito dei comandi di verifica eseguiti dall'agente.

Finora «verificato» significava unicamente «processo uscito con codice zero».
Questo presentava due difetti simmetrici emersi nei run empirici dell'agente:

1. **Falso positivo (prova illusoria):** Un comando come `python -m pytest
   tests/test_inesistente.py` o un run che raccoglie zero test (`collected 0
   items`) puo' uscire con codice 0 o mascherare l'assenza totale di prove.
   L'agente dichiarava completato il task credendosi verificato quando nessun
   test aveva in realta' girato.

2. **Falso negativo (blocco indebito):** Un comando di terminale che non era un
   test (o una scrittura malformata scambiata per verifica) veniva registrato
   come fallito, e il cancello di completamento pretendeva il suo superamento,
   bloccando l'agente per decine di turni in un vicolo cieco.

Questo modulo analizza l'output (stdout/stderr e codice di ritorno) dei runner
piu' comuni (pytest, unittest, vitest/jest, eslint, build, py_compile) ed
estrae un rapporto strutturato con il conteggio dei test realmente passati,
falliti o raccolti. Una verifica e' considerata valida solo se ha effettivamente
dimostrato il funzionamento del codice.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class VerificationReport:
    """Rapporto strutturato sull'esito di un comando di verifica."""

    command: str
    returncode: int
    kind: str  # "pytest", "unittest", "js_test", "linter", "build", "syntax", "generic"
    is_valid: bool  # True se dimostra positivamente che il codice funziona
    passed: int = 0
    failed: int = 0
    errors: int = 0
    collected: int = 0
    skipped: int = 0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Parser specifici per i principali runner
# ---------------------------------------------------------------------------

_PYTEST_SUMMARY_RE = re.compile(
    r"(?:(?P<passed>\d+)\s+passed)?|"
    r"(?:(?P<failed>\d+)\s+failed)?|"
    r"(?:(?P<errors>\d+)\s+error(?:s)?)?|"
    r"(?:(?P<skipped>\d+)\s+skipped)?",
    re.IGNORECASE,
)

_PYTEST_COLLECTED_RE = re.compile(
    r"collected\s+(?P<collected>\d+)\s+item",
    re.IGNORECASE,
)

_UNITTEST_RAN_RE = re.compile(
    r"Ran\s+(?P<count>\d+)\s+test",
    re.IGNORECASE,
)

_JS_TEST_SUMMARY_RE = re.compile(
    r"Tests:\s+(?:(?P<failed>\d+)\s+failed,\s*)?(?:(?P<passed>\d+)\s+passed,\s*)?(?P<total>\d+)\s+total",
    re.IGNORECASE,
)

_ESLINT_PROBLEMS_RE = re.compile(
    r"✖\s+(?P<problems>\d+)\s+problem",
    re.IGNORECASE,
)


def _parse_pytest(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza l'output di pytest."""
    if not text.strip():
        # Output assente (es. mock di test unitari senza cattura stdout):
        is_ok = (rc == 0)
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="pytest",
            is_valid=is_ok,
            passed=1 if is_ok else 0,
            summary="pytest: test superati" if is_ok else "pytest fallito",
        )

    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    collected = 0

    col_match = _PYTEST_COLLECTED_RE.search(text)
    if col_match:
        try:
            collected = int(col_match.group("collected"))
        except (ValueError, TypeError):
            collected = 0

    # Cerca la riga di summary (es. "5 passed, 1 warning in 0.42s")
    # Troviamo tutti i blocchi numerici corrispondenti
    for m in re.finditer(r"(\d+)\s+(passed|failed|error|errors|skipped)", text, re.IGNORECASE):
        val = int(m.group(1))
        label = m.group(2).lower()
        if "pass" in label:
            passed = max(passed, val)
        elif "fail" in label:
            failed = max(failed, val)
        elif "err" in label:
            errors = max(errors, val)
        elif "skip" in label:
            skipped = max(skipped, val)

    if collected == 0 and (passed + failed + errors) > 0:
        collected = passed + failed + errors

    # Pytest puo' uscire con rc 5 se non ha trovato alcun test
    if "no tests ran" in text.lower() or "collected 0 items" in text.lower():
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="pytest",
            is_valid=False,
            passed=0,
            failed=0,
            collected=0,
            summary="Nessun test trovato o raccolto da pytest",
        )

    # Una prova e' valida solo se rc e' 0, c'e' almeno un test passato e zero falliti/errori
    is_valid = (rc == 0 and passed > 0 and failed == 0 and errors == 0)

    parts = []
    if passed:
        parts.append(f"{passed} passati")
    if failed:
        parts.append(f"{failed} falliti")
    if errors:
        parts.append(f"{errors} errori")
    if skipped:
        parts.append(f"{skipped} saltati")
    dettaglio = ", ".join(parts) if parts else ("test superati" if rc == 0 else "test falliti")

    return VerificationReport(
        command=command,
        returncode=rc,
        kind="pytest",
        is_valid=is_valid,
        passed=passed,
        failed=failed,
        errors=errors,
        collected=collected,
        skipped=skipped,
        summary=f"pytest: {dettaglio}" if is_valid else f"pytest fallito: {dettaglio}",
    )


def _parse_unittest(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza l'output di python -m unittest."""
    if not text.strip():
        is_ok = (rc == 0)
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="unittest",
            is_valid=is_ok,
            passed=1 if is_ok else 0,
            summary="unittest superato" if is_ok else "unittest fallito",
        )

    ran_match = _UNITTEST_RAN_RE.search(text)
    count = int(ran_match.group("count")) if ran_match else 0

    if count == 0 or "ran 0 tests" in text.lower():
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="unittest",
            is_valid=False,
            passed=0,
            summary="Nessun test eseguito da unittest",
        )

    is_ok = (rc == 0 and "OK" in text and "FAILED" not in text)
    failed = 0
    fail_match = re.search(r"failures=(\d+)", text)
    if fail_match:
        failed += int(fail_match.group(1))
    err_match = re.search(r"errors=(\d+)", text)
    if err_match:
        failed += int(err_match.group(1))

    passed = max(0, count - failed) if is_ok else 0

    return VerificationReport(
        command=command,
        returncode=rc,
        kind="unittest",
        is_valid=is_ok,
        passed=passed if is_ok else 0,
        failed=failed,
        collected=count,
        summary=f"unittest: {count} test superati" if is_ok else f"unittest: {failed} test falliti",
    )


def _parse_js_test(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza output di vitest, jest o npm test."""
    m = _JS_TEST_SUMMARY_RE.search(text)
    if m:
        passed = int(m.group("passed") or 0)
        failed = int(m.group("failed") or 0)
        total = int(m.group("total") or 0)
        is_valid = (rc == 0 and passed > 0 and failed == 0)
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="js_test",
            is_valid=is_valid,
            passed=passed,
            failed=failed,
            collected=total,
            summary=f"test js: {passed}/{total} superati" if is_valid else f"test js falliti ({failed} errori)",
        )

    # Fallback su pass/fail generico
    is_valid = (rc == 0 and "pass" in text.lower() and "fail" not in text.lower())
    return VerificationReport(
        command=command,
        returncode=rc,
        kind="js_test",
        is_valid=is_valid,
        passed=1 if is_valid else 0,
        summary="test frontend completati" if is_valid else "test frontend non superati",
    )


def _parse_linter(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza l'esito di linters (eslint, flake8, ruff, mypy)."""
    # Nel caso di eslint: "✖ N problems (N errors, M warnings)"
    m = _ESLINT_PROBLEMS_RE.search(text)
    if m:
        problems = int(m.group("problems"))
        is_valid = (rc == 0 and problems == 0)
        return VerificationReport(
            command=command,
            returncode=rc,
            kind="linter",
            is_valid=is_valid,
            failed=problems,
            summary="linter pulito: nessun errore" if is_valid else f"linter: {problems} problemi rilevati",
        )

    is_valid = (rc == 0)
    return VerificationReport(
        command=command,
        returncode=rc,
        kind="linter",
        is_valid=is_valid,
        summary="linter pulito: nessun errore" if is_valid else "linter ha rilevato errori di sintassi o stile",
    )


def _parse_build(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza comandi di compilazione o build frontend/backend."""
    # Vite/Webpack build: "built in XXXms" o presenza asset dist
    is_valid = (rc == 0)
    if "error" in text.lower() and rc != 0:
        is_valid = False

    return VerificationReport(
        command=command,
        returncode=rc,
        kind="build",
        is_valid=is_valid,
        summary="build completata con successo" if is_valid else "build fallita",
    )


def _parse_syntax(command: str, rc: int, text: str) -> VerificationReport:
    """Analizza controlli di import o py_compile."""
    is_valid = (rc == 0 and not text.strip()) or (rc == 0 and "error" not in text.lower())
    return VerificationReport(
        command=command,
        returncode=rc,
        kind="syntax",
        is_valid=is_valid,
        summary="controllo sintassi/import riuscito" if is_valid else "errore di sintassi o importazione fallita",
    )


# ---------------------------------------------------------------------------
# Punto di ingresso unificato
# ---------------------------------------------------------------------------


def parse_verification(
    command: str,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> VerificationReport:
    """Estrae un rapporto di verifica strutturato a partire dal comando e dal suo output."""
    cmd = (command or "").strip().lower()
    full_output = (stdout or "") + "\n" + (stderr or "")

    if "pytest" in cmd:
        return _parse_pytest(command, returncode, full_output)

    if "unittest" in cmd:
        return _parse_unittest(command, returncode, full_output)

    if any(k in cmd for k in ("vitest", "jest", "npm test", "npm run test", "yarn test")):
        return _parse_js_test(command, returncode, full_output)

    if any(k in cmd for k in ("eslint", "lint:undef", "ruff", "flake8", "mypy", "pylint")):
        return _parse_linter(command, returncode, full_output)

    if any(k in cmd for k in ("build", "vite build", "tsc")):
        return _parse_build(command, returncode, full_output)

    if any(k in cmd for k in ("py_compile", "compileall", "import ")):
        return _parse_syntax(command, returncode, full_output)

    # Verifica generica: richiede codice zero e assenza di parole di errore evidenti
    is_valid = (returncode == 0)
    return VerificationReport(
        command=command,
        returncode=returncode,
        kind="generic",
        is_valid=is_valid,
        summary="comando completato con codice 0" if is_valid else f"comando uscito con codice {returncode}",
    )
