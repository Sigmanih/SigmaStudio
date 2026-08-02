# ==============================================================================
# core/training/audit.py — Verifica che i verdetti siano dati per il motivo giusto
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Un benchmark si fida di due cose: che il modello risponda, e che noi
capiamo la sua risposta. La seconda e' codice nostro, quindi va verificata.

Questo modulo non conta i pass: controlla **perche'** ogni verdetto e' stato
dato, e separa i due errori opposti che rendono un punteggio inutile.

  falso NEGATIVO — il modello ha dichiarato la risposta esatta e l'abbiamo
                   segnata sbagliata. Sottostima il modello: e' successo
                   davvero, il parser prendeva la prima risposta invece
                   dell'ultima e costava 30 punti su GSM8K.
  falso POSITIVO — abbiamo segnato giusto senza che il modello abbia mai
                   dichiarato quella risposta: il valore atteso compariva per
                   caso nel ragionamento e l'abbiamo raccolto. Sovrastima il
                   modello, ed e' l'errore piu' insidioso perche' fa festa.

La distinzione operativa e' fra risposta **dichiarata** (dentro `\\boxed{}`,
dopo `####`, o dopo "the answer is") e numero semplicemente **presente** nel
testo. Un pass che non poggia su una dichiarazione e' una congettura, e come
tale va segnalato — non necessariamente sbagliato, ma non certificabile.
"""

from __future__ import annotations

import re
from collections import Counter

from core.logger import get_logger
from core.training.answer_parser import (
    REVIEW_VERDICTS, VERDICT_PASS, _all_boxed, grade_answer, normalize_numeric,
    normalize_text_answer, numeric_equal, option_letters,
)

log = get_logger(__name__)

#: Marcatore `####` di GSM8K. I vincoli sono stretti di proposito: deve aprire
#: la riga e il numero deve esaurirla. Una versione permissiva scambiava per
#: risposta finale un titolo markdown come "#### 5. State the Answer", e l'audit
#: accusava il parser di un errore che aveva commesso l'audit.
_HASH_FINAL = re.compile(
    r"^[ \t]*#{3,}[ \t]*\$?[ \t]*(-?[\d.,]*\d)[ \t]*[^\d\n]{0,15}$", re.M)
_ANY_NUMBER = re.compile(r"-?\d[\d.,]*\d|-?\d")

#: Tier che rappresentano una dichiarazione esplicita. Gli altri sono deduzioni
#: dal contesto e non bastano a certificare un pass.
_DECLARED_TIERS = ("exact", "declared", "anchored")

FINDING_FALSE_NEGATIVE = "falso_negativo"
FINDING_FALSE_POSITIVE = "falso_positivo"
FINDING_UNDECLARED_PASS = "pass_non_dichiarato"
FINDING_REASONED_THEN_LOST = "ragionata_poi_persa"

FINDING_LABELS = {
    FINDING_FALSE_NEGATIVE: "Risposta giusta dichiarata, verdetto negativo",
    FINDING_FALSE_POSITIVE: "Verdetto positivo su una risposta mai dichiarata",
    FINDING_UNDECLARED_PASS: "Verdetto positivo dedotto, non dichiarato",
    FINDING_REASONED_THEN_LOST: "Il modello arriva al risultato e poi ne dichiara un altro",
}

#: Solo i primi due invalidano il punteggio. Gli altri due sono segnalazioni:
#: dicono che il verdetto e' fragile, non che e' sbagliato.
BLOCKING_FINDINGS = (FINDING_FALSE_NEGATIVE, FINDING_FALSE_POSITIVE)


#: Dichiarazione esplicita in prosa, per le risposte che non sono numeri.
_SAID_IS = re.compile(
    r"\b(?:answer|risposta|result|risultato|solution|soluzione)\b"
    r"\s*(?:is|was|:|=|e'|è)\s*[\"'“*\(\[]*([^\n\"'”*\)\]\.]{1,60})", re.I)


#: Residui di fine generazione che i modelli lasciano attaccati alla risposta.
_TURN_MARKER = re.compile(r"<\|[^|>]*\|>|</s>|<\|endoftext\|>")


def final_declaration(text: str, item: dict) -> str | None:
    """L'**ultima** risposta che il modello dichiara, o None se non ne dichiara.

    E' un oracolo indipendente dal parser: se coincidesse con lui, l'audit non
    potrebbe che assolverlo. Applica una sola regola, quella su cui c'e'
    consenso in letteratura — l'ultima dichiarazione e' la risposta finale — e
    la applica al testo grezzo.

    Elencare tutte le opzioni non e' dichiarare: un modello che scrive
    "A) No, B) No, C) No, D) Si" non ha scelto, e il quesito va in revisione,
    non contato come giusto o sbagliato.
    """
    options = item.get("options") or []
    if options:
        letters = [l.upper() for l in option_letters(options)]
        stripped = text.strip().strip('."\'*() ').upper()
        # Il prompt della scelta multipla chiede una lettera e basta: la
        # risposta piu' comune e' proprio quella, senza alcun delimitatore.
        if stripped in letters:
            return stripped
        said = _SAID_IS.search(text)
        if said:
            head = said.group(1).strip().upper()[:1]
            if head in letters:
                return head
        mentioned = [l for l in letters
                     if re.search(rf"(?<![A-Za-z]){re.escape(l)}[\)\].:]", text, re.I)]
        # Se compaiono quasi tutte, il modello sta enumerando, non scegliendo.
        if len(mentioned) > max(1, len(letters) // 2):
            return None
        return mentioned[-1] if mentioned else None

    # I marcatori numerici valgono solo se la risposta attesa e' un numero.
    # Su BBH formal_fallacies l'attesa e' la parola "valid", e un `#### 7`
    # rimasto in coda alla generazione non e' una dichiarazione: e' spazzatura.
    if _is_numeric(item.get("correct_choice") or ""):
        marks = [(m.start(), m.group(1)) for m in _HASH_FINAL.finditer(text)]
        marks += [(text.find(b, 0), b) for b in _all_boxed(text)]
        if marks:
            marks.sort(key=lambda pair: pair[0])
            return normalize_numeric(marks[-1][1]) or None

    said = None
    for said in _SAID_IS.finditer(text):
        pass                                    # vale l'ultima dichiarazione
    if not said:
        return None
    # I marcatori di fine turno restano attaccati alla cattura: "valid<|end|>"
    # non e' la risposta, e' la risposta piu' spazzatura di generazione.
    return _TURN_MARKER.split(said.group(1).strip())[0].strip() or None


def _is_numeric(value: str) -> bool:
    """La risposta attesa e' un numero? Decide quale forma di dichiarazione vale."""
    return bool(re.fullmatch(r"\s*-?[\d.,]*\d\s*(?:/\s*-?\d+)?\s*", value or ""))


def _matches(candidate: str, expected: str, numeric: bool) -> bool:
    if numeric:
        return numeric_equal(candidate, expected)
    return normalize_text_answer(candidate) == normalize_text_answer(expected)


def audit_result(item: dict, output_text: str, verdict: str, parsed: dict) -> dict | None:
    """Il verdetto di un quesito regge? Se no, dice quale dei due errori e'.

    Restituisce ``None`` quando non c'e' niente da segnalare.
    """
    expected = (item.get("correct_choice") or "").strip()
    if not expected or verdict in REVIEW_VERDICTS:
        # Senza risposta attesa non c'e' niente da verificare, e un item gia'
        # mandato in revisione e' gia' stato dichiarato incerto.
        return None

    text = output_text or ""
    numeric = _is_numeric(expected)
    final = final_declaration(text, item)
    tier = (parsed or {}).get("tier") or ""

    if final is None:
        # Nessuna dichiarazione: qualunque verdetto poggia su una deduzione.
        if verdict == VERDICT_PASS:
            return {"finding": FINDING_UNDECLARED_PASS,
                    "detail": ("Il modello non ha dichiarato una risposta finale: "
                               "il verdetto poggia su un valore dedotto dal testo.")}
        return None

    correct = _matches(final, expected, numeric)

    if verdict == VERDICT_PASS and not correct:
        return {"finding": FINDING_FALSE_POSITIVE,
                "detail": (f"Segnato corretto, ma l'ultima risposta dichiarata dal "
                           f"modello e' '{final}', non '{expected}'.")}
    if verdict != VERDICT_PASS and correct:
        return {"finding": FINDING_FALSE_NEGATIVE,
                "detail": (f"L'ultima risposta dichiarata e' '{final}', che coincide "
                           f"con l'attesa, ma il verdetto e' negativo.")}
    if verdict == VERDICT_PASS and tier not in _DECLARED_TIERS:
        return {"finding": FINDING_UNDECLARED_PASS,
                "detail": f"Verdetto corretto ma estratto al livello debole '{tier}'."}

    if not correct and numeric and any(
            _matches(normalize_numeric(n), expected, True) for n in _ANY_NUMBER.findall(text)):
        return {"finding": FINDING_REASONED_THEN_LOST,
                "detail": (f"'{expected}' compare nel ragionamento ma il modello ha "
                           f"poi dichiarato '{final}'.")}
    return None


def audit_run(rows) -> dict:
    """Verifica un run intero, riesaminando ogni quesito dalla sua risposta grezza.

    Non si fida dei verdetti salvati: rigiudica ogni risposta con il parser
    corrente e poi verifica quel giudizio. Cosi' l'audit vede anche i verdetti
    prodotti da una versione precedente del parser.
    """
    counts = Counter()
    findings: list[dict] = []
    regraded = 0
    total = 0

    for row in rows:
        total += 1
        text = row.get("given_answer") or ""
        item = {k: row.get(k) for k in
                ("suite", "options", "correct_choice", "correct_answer",
                 "expected_keywords", "prompt")}
        # Le suite di codice si giudicano eseguendo i test: il parser non c'entra.
        if row.get("execution"):
            counts["saltati_codice"] += 1
            continue

        graded = grade_answer(item, text)
        if graded["verdict"] != row.get("verdict"):
            regraded += 1
        counts[graded["verdict"]] += 1

        finding = audit_result(item, text, graded["verdict"], graded.get("parsed"))
        if finding:
            counts[finding["finding"]] += 1
            findings.append({
                "id": row.get("id"),
                "suite": row.get("suite"),
                "expected": row.get("correct_choice"),
                "extracted": (graded.get("parsed") or {}).get("value"),
                "verdict": graded["verdict"],
                "answer": text[-400:],
                **finding,
            })

    blocking = sum(counts[f] for f in BLOCKING_FINDINGS)
    graded_total = max(1, total - counts["saltati_codice"])
    return {
        "success": True,
        "items": total,
        "regraded": regraded,
        "counts": dict(counts),
        "findings": findings,
        "blocking": blocking,
        # Quota di verdetti che reggono all'esame. E' il numero da guardare
        # prima del punteggio: un punteggio con il 5% di verdetti fragili non
        # e' confrontabile con uno pulito.
        "trust": round(1.0 - (blocking + counts[FINDING_UNDECLARED_PASS]) / graded_total, 4),
        "labels": FINDING_LABELS,
    }
