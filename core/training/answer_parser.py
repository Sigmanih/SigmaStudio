# ==============================================================================
# core/training/answer_parser.py — Grading answer extraction for benchmarks
# Sigma Studio v7 — Training Lab Sub-package
# ==============================================================================
"""Estrae la risposta finale del modello e la confronta con la verità di base.

Il punto centrale di questo modulo: una risposta che non e' *una sola* risposta
non e' un errore del modello, e' un esito **non deciso**. Un modello che scrive
"The correct answer is A. The correct choice is H." non ha scelto A: ha scritto
due risposte in conflitto, e contarla come corretta gonfia il punteggio.

Ogni funzione di parsing restituisce un `ParseResult` con uno stato fra:

* ``resolved``   — una sola risposta finale, estratta con una certa confidenza
* ``ambiguous``  — piu' risposte in conflitto (il caso "risposta duplice")
* ``unparsable`` — nessuna risposta riconoscibile (o solo lettere fuori range)

`ambiguous` e `unparsable` non diventano ne' pass ne' fail: finiscono nella coda
di revisione (`VERDICT_AMBIGUOUS` / `VERDICT_UNPARSABLE`) e sono esclusi
dall'accuratezza corretta, restando visibili come copertura del giudizio.

Tecnologia: regex deterministiche a tier di priorita', senza dipendenze nuove.
Serve girare su ~200k item per run e restare bit-per-bit riproducibile sotto il
certificato SHA-256 (temp 0.0 / seed 42); un giudice LLM o un parser statistico
introdurrebbe non determinismo proprio nel punto che il certificato attesta.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction

# ---------------------------------------------------------------- verdetti

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_AMBIGUOUS = "ambiguous"
VERDICT_UNPARSABLE = "unparsable"
VERDICT_ERROR = "error"

#: Verdetti che richiedono un giudizio umano invece di contare come esito.
REVIEW_VERDICTS = (VERDICT_AMBIGUOUS, VERDICT_UNPARSABLE, VERDICT_ERROR)

STATUS_RESOLVED = "resolved"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNPARSABLE = "unparsable"

# Tier di estrazione, dal piu' affidabile al piu' debole.
TIER_EXACT = "exact"            # la risposta e' solo la lettera
TIER_DECLARED = "declared"      # "the answer is B"
TIER_ANCHORED = "anchored"      # la risposta apre con "B)"
TIER_OPTION_TEXT = "option_text"  # la risposta ricalca il testo di un'opzione
TIER_MENTION = "mention"        # lettera isolata citata nella prosa

_TIER_ORDER = (TIER_EXACT, TIER_DECLARED, TIER_ANCHORED, TIER_OPTION_TEXT, TIER_MENTION)

#: Confidenza per tier, esposta alla UI per ordinare la coda di revisione.
TIER_CONFIDENCE = {
    TIER_EXACT: "high",
    TIER_DECLARED: "high",
    TIER_ANCHORED: "medium",
    TIER_OPTION_TEXT: "medium",
    TIER_MENTION: "low",
}


@dataclass
class ParseResult:
    """Esito dell'estrazione, prima del confronto con la risposta corretta."""

    status: str
    value: str | None = None
    tier: str = ""
    candidates: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def confidence(self) -> str:
        """Quanto fidarsi del valore estratto.

        Un valore ricavato scartandone altri resta valido — vince l'ultimo —
        ma non e' pulito come una risposta dichiarata una volta sola: si scende
        di un gradino, cosi' la coda di revisione mostra per primi i casi in
        cui il modello si e' contraddetto.
        """
        level = TIER_CONFIDENCE.get(self.tier, "none")
        if self.rejected and level == "high":
            return "medium"
        if self.rejected and level == "medium":
            return "low"
        return level

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "value": self.value,
            "tier": self.tier,
            "confidence": self.confidence,
            "candidates": self.candidates,
            "rejected": self.rejected,
            "reason": self.reason,
        }


# ---------------------------------------------------------------- pre-pulizia

_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)\b[^>]*>.*?</\1>", re.S | re.I)
_THINK_OPEN = re.compile(r"</?(?:think|thinking|reasoning)\b[^>]*>", re.I)
_CODE_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n?|```", re.S)
# "e.g." e "i.e." producevano una falsa lettera 'E'/'G' subito dopo una frase
# come "the letter of the correct option is e.g. A, b, c".
_ABBREV = re.compile(r"\b(?:e\.\s*g|i\.\s*e|eg|ie|cfr|es)\.", re.I)


def normalize_output(text: str) -> str:
    """Ripulisce l'output grezzo del modello prima di cercare la risposta.

    Toglie i blocchi di ragionamento (che spesso valutano *tutte* le opzioni e
    quindi renderebbero ambigua ogni risposta), le recinzioni di codice e le
    abbreviazioni che imitano una lettera di opzione.
    """
    if not text:
        return ""
    cleaned = _THINK_BLOCK.sub(" ", text)
    cleaned = _THINK_OPEN.sub(" ", cleaned)
    cleaned = _CODE_FENCE.sub(" ", cleaned)
    cleaned = _ABBREV.sub(";", cleaned)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    return cleaned.strip()


def _dedupe(seq) -> list[str]:
    """Elimina i duplicati mantenendo l'ordine di apparizione."""
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------------------------------------------------- scelta multipla

_OPTION_LETTER = re.compile(r"^\s*[\(\[\*]*([A-Za-z])[\)\].:\-]")

# "Answer: B" / "the correct answer is B" / "risposta corretta: B" / "opzione D".
# Il `\b` dopo ogni parola chiave e' necessario: senza, "LETTERS ARE H AND K"
# faceva combaciare "LETTER" e catturava la 'S' del plurale.
_DECLARATION = re.compile(
    r"\b(?:answer|risposta|option|opzione|choice|scelta|letter|lettera|selection)\b"
    r"\s*(?:of\s+the\s+correct\s+\w+\s*)?"
    # Aggettivo posposto: in italiano la qualifica segue il nome
    # ("risposta corretta: C"), non lo precede come in inglese.
    r"(?:\s+(?:correct|corretta|corretto|giusta|giusto|esatta|esatto|right|final|finale))?"
    r"(?:\s*(?:is|was|are|è|e'|=|:|->|—|–|-)\s*|\s+)"
    r"(?:the\s+|la\s+|il\s+)?(?:letter\s+|lettera\s+|option\s+|opzione\s+)?"
    r"[\(\[\"'“*]*([A-Za-z])(?![A-Za-z0-9'’])",
    re.I,
)

# Forma inversa: "B is the correct answer", "D è la risposta corretta".
_DECLARATION_REVERSED = re.compile(
    r"[\(\[\"'“*]*\b([A-Za-z])\b[\)\]\"'”*]*\s*"
    r"(?:is|was|è|e')\s+(?:the\s+|la\s+|il\s+)?"
    r"(?:correct|right|final|giusta|corretta)?\s*"
    r"(?:answer|risposta|option|opzione|choice|scelta)\b",
    re.I,
)

_BOLD_LETTER = re.compile(r"\*\*\s*\(?([A-Za-z])\)?\s*\*\*")
_ANCHORED = re.compile(r"^[\s\(\[\*\"']*([A-Za-z])(?:[\)\].:\-]|\s*$)")
_BARE_LETTER = re.compile(r"^[\s\(\[\*\"'“]*([A-Za-z])[\s\)\]\*\"'”.,:;]*$")

# Menzione debole: solo una lettera *delimitata* come etichetta di opzione —
# "(B)", "[B]", "\"B\"" o "B)". Una lettera nuda nella prosa non conta: modelli
# piccoli scrivono algebra ("is (a+b+c)/len(z_7)", "where a, b, c are...") e
# leggerla come scelta trasformava ogni formula in una risposta multipla.
_MENTION = re.compile(
    r"[\(\[]\s*([A-Za-z])\s*[\)\]]"        # (B) oppure [B]
    r"|[\"'“]\s*([A-Za-z])\s*[\"'”]"       # "B"
    r"|(?<![A-Za-z0-9])([A-Za-z])\)\s"     # B) seguito da spazio
)

# Una lettera seguita da un operatore fa parte di un'espressione, non e' una
# scelta: "the answer is (a+b+c)" dichiara algebra, non l'opzione A.
_EXPRESSION_TAIL = re.compile(r"^\s*(?:[+*/^_=]|-\s*[\dA-Za-z(])")
# Delimitatore incollato a un simbolo: "Z_3[x]" e "(x)/2" sono notazione.
_EXPRESSION_HEAD = re.compile(r"[A-Za-z0-9_]$")


def option_letters(options: list[str] | None) -> list[str]:
    """Lettere ammesse per un item, lette dalle opzioni ("B) testo" -> "B").

    Le suite non usano tutte A-D: MMLU-Pro arriva a J e ARC etichetta con 1-4,
    quindi il range valido va dedotto dall'item e non assunto.
    """
    if not options:
        return []
    letters: list[str] = []
    for idx, opt in enumerate(options):
        match = _OPTION_LETTER.match(opt or "")
        letters.append(match.group(1).upper() if match else chr(65 + idx))
    return _dedupe(letters)


def _option_body(opt: str) -> str:
    return re.sub(r"^\s*[\(\[\*]*[A-Za-z][\)\].:\-]\s*", "", opt or "").strip()


# Elenco che prosegue una dichiarazione: "Answer: A and D", "risposta: B, C".
# Va letto come risposta multipla, non come la prima lettera piu' del rumore.
_DECL_CONTINUATION = re.compile(
    r"(?:\s*(?:,|;|/|&|\band\b|\bor\b|\be\b|\bo\b|\boppure\b|\balso\b|\banche\b|\bthen\b))+"
    r"\s*[\(\[\"'“*]*([A-Za-z])(?![A-Za-z0-9'’])",
    re.I,
)


def _continuation_letters(text: str, pos: int) -> list[str]:
    """Legge le lettere elencate subito dopo una risposta dichiarata."""
    letters: list[str] = []
    while True:
        match = _DECL_CONTINUATION.match(text, pos)
        if not match or _EXPRESSION_TAIL.match(text[match.end(1):match.end(1) + 3]):
            return letters
        letters.append(match.group(1).upper())
        pos = match.end(1)


def _declared_letters(text: str) -> list[str]:
    """Lettere annunciate esplicitamente, scartando quelle dentro espressioni."""
    letters: list[str] = []
    for pattern in (_DECLARATION, _DECLARATION_REVERSED, _BOLD_LETTER):
        for match in pattern.finditer(text):
            if _EXPRESSION_TAIL.match(text[match.end(1):match.end(1) + 3]):
                continue
            letters.append(match.group(1).upper())
            letters.extend(_continuation_letters(text, match.end(1)))
    return _dedupe(letters)


def _collect_mc_candidates(text: str, options: list[str] | None) -> dict[str, list[str]]:
    """Raccoglie per ogni tier le lettere candidate trovate nel testo."""
    found: dict[str, list[str]] = {tier: [] for tier in _TIER_ORDER}

    bare = _BARE_LETTER.match(text)
    if bare:
        found[TIER_EXACT].append(bare.group(1).upper())

    found[TIER_DECLARED] = _declared_letters(text)

    anchored = _ANCHORED.match(text)
    if anchored:
        found[TIER_ANCHORED].append(anchored.group(1).upper())

    if options:
        upper = text.upper()
        for idx, opt in enumerate(options):
            body = _option_body(opt).upper()
            if len(body) < 4:
                continue
            letters = option_letters(options)
            letter = letters[idx] if idx < len(letters) else chr(65 + idx)
            if upper.startswith(body) or upper == body:
                found[TIER_OPTION_TEXT].append(letter)

    found[TIER_MENTION] = _dedupe(
        (m.group(1) or m.group(2) or m.group(3)).upper()
        for m in _MENTION.finditer(text)
        if not _EXPRESSION_HEAD.search(text[max(0, m.start() - 1):m.start()])
        and not _EXPRESSION_TAIL.match(text[m.end():m.end() + 3])
    )

    return found


def parse_multiple_choice(raw_text: str, options: list[str] | None = None) -> ParseResult:
    """Estrae l'unica lettera scelta, o segnala conflitto/assenza di risposta.

    Scende per tier: vince il primo tier che contiene almeno una lettera valida.
    Dentro quel tier, due lettere distinte significano risposta duplice e quindi
    `ambiguous` — anche quando una delle due e' fuori dal range delle opzioni,
    perche' resta una contraddizione dichiarata dal modello.
    """
    text = normalize_output(raw_text)
    if not text:
        return ParseResult(STATUS_UNPARSABLE, reason="Risposta vuota")

    valid = set(option_letters(options))
    found = _collect_mc_candidates(text, options)
    rejected: list[str] = []

    for tier in _TIER_ORDER:
        letters = found.get(tier) or []
        if not letters:
            continue
        in_range = [x for x in letters if not valid or x in valid]
        out_range = [x for x in letters if valid and x not in valid]

        if not in_range:
            # Solo lettere inesistenti (la classica 'E' da "e.g." o la 'T' di
            # "T(-3,2)"): non e' una scelta, va rivista a mano.
            rejected.extend(out_range)
            continue

        distinct = _dedupe(in_range + out_range)
        if len(distinct) > 1:
            return ParseResult(
                STATUS_AMBIGUOUS,
                tier=tier,
                candidates=distinct,
                rejected=_dedupe(rejected),
                reason=f"Risposta duplice: {len(distinct)} lettere in conflitto "
                       f"({', '.join(distinct)}) allo stesso livello '{tier}'",
            )

        return ParseResult(
            STATUS_RESOLVED,
            value=in_range[0],
            tier=tier,
            candidates=distinct,
            rejected=_dedupe(rejected),
        )

    if rejected:
        return ParseResult(
            STATUS_UNPARSABLE,
            candidates=[],
            rejected=_dedupe(rejected),
            reason=f"Solo lettere fuori dalle opzioni disponibili: {', '.join(_dedupe(rejected))}",
        )
    return ParseResult(STATUS_UNPARSABLE, reason="Nessuna lettera di opzione riconoscibile")


# ---------------------------------------------------------------- matematica

_BOXED = re.compile(r"\\+(?:boxed|fbox)\s*\{", re.I)
_NUMBER = re.compile(r"-?\d[\d.,]*(?:\s*/\s*-?\d+)?|-?\.\d+")
_MATH_DECLARATION = re.compile(
    r"\b(?:answer|risposta|result|risultato|solution|soluzione|total|totale|equals?)\b"
    r"\s*(?:is|was|=|:|->|—|–)?\s*"
    r"(?:\$|\\\(|\\\[)?\s*(-?[\d.,]*\d(?:\s*/\s*-?\d+)?|-?\.\d+)",
    re.I,
)


def _extract_braced(text: str, start: int) -> tuple[str, int] | None:
    """Legge il contenuto di una graffa bilanciata, per \\boxed{\\frac{1}{2}}."""
    depth = 0
    for pos in range(start, len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:pos], pos + 1
    return None


def _boxed_spans(text: str) -> list[tuple[int, str]]:
    """(posizione, contenuto) di ogni \\boxed / \\fbox, in ordine di apparizione."""
    out: list[tuple[int, str]] = []
    pos = 0
    while True:
        match = _BOXED.search(text, pos)
        if not match:
            return out
        braced = _extract_braced(text, match.end() - 1)
        if not braced:
            return out
        body, pos = braced
        body = body.strip()
        if body:
            out.append((match.start(), body))


def _all_boxed(text: str) -> list[str]:
    return [body for _pos, body in _boxed_spans(text)]


_LATEX_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
_LATEX_NOISE = re.compile(
    r"\\(?:left|right|text|mathrm|displaystyle|cdot|times)\b"  # comandi con nome
    r"|\\[!,;:\s]"                                             # spaziature \! \, \;
    r"|[\$\\]"                                                 # dollari e backslash residui
)


def normalize_numeric(value: str) -> str:
    """Riduce una risposta matematica a una forma confrontabile.

    Le suite scrivono lo stesso numero in molti modi (``\\frac{1}{2}``, ``1/2``,
    ``$1{,}200``, ``50\\%``): senza normalizzare, risposte giuste risultano
    sbagliate solo per la formattazione.
    """
    if value is None:
        return ""
    text = str(value).strip()
    text = _LATEX_FRAC.sub(r"(\1)/(\2)", text)
    text = _LATEX_NOISE.sub("", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("^\\circ", "").replace("°", "")
    text = re.sub(r"\s+", "", text)
    text = text.rstrip(".")
    # Separatore delle migliaia: 1,200 -> 1200, ma 1,5 (decimale it) resta.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = text.replace("%", "").replace("€", "").replace("$", "")
    return text.lower()


def _to_number(value: str):
    """Converte in numero se possibile, gestendo frazioni e parentesi."""
    text = normalize_numeric(value)
    if not text:
        return None
    text = text.replace("(", "").replace(")", "")
    try:
        if "/" in text:
            num, _, den = text.partition("/")
            return Fraction(Fraction(num), Fraction(den))
        return Fraction(text)
    except (ValueError, ZeroDivisionError, ArithmeticError):
        return None


def numeric_equal(left: str, right: str, tolerance: float = 1e-6) -> bool:
    """Confronta due risposte matematiche per valore, non per stringa."""
    left_num, right_num = _to_number(left), _to_number(right)
    if left_num is not None and right_num is not None:
        return abs(float(left_num) - float(right_num)) <= tolerance
    return normalize_numeric(left) == normalize_numeric(right) != ""


#: Marcatore canonico della risposta finale in GSM8K: il dataset chiude ogni
#: soluzione con "#### 42", e un modello addestrato su GSM8K lo riproduce.
#: Vincoli stretti per non confondersi con un titolo markdown ("## 3. Passaggi"):
#: deve aprire la riga, avere almeno tre cancelletti, e dopo il numero puo'
#: restare solo una coda breve senza altre cifre (un'unita' come "dollars").
_HASH_FINAL = re.compile(
    r"^[ \t]*#{3,}[ \t]*\$?[ \t]*"
    r"(-?[\d.,]*\d(?:[ \t]*/[ \t]*-?\d+)?|-?\.\d+)"
    r"[ \t]*[^\d\n]{0,15}$",
    re.M,
)

# Due risposte sulla stessa riga ("either \boxed{3} or \boxed{4}") non hanno un
# ordine che dica quale sia definitiva: quelle restano davvero ambigue.
_SAME_LINE_ALTERNATIVE = re.compile(
    r"\b(?:or|oppure|either|o\b)\s*[^\n]{0,20}?\\+(?:boxed|fbox)\s*\{", re.I)


def _last_conflicting(values: list[str]) -> tuple[str, list[str]]:
    """The final answer among several, plus the ones it actually contradicts.

    Un modello che ragiona ad alta voce scrive spesso un valore provvisorio e
    poi si corregge; alcuni, addestrati sul formato di GSM8K, aprono
    addirittura con la risposta e la ripetono in fondo. In entrambi i casi la
    risposta buona e' l'**ultima** dichiarata — e' la convenzione dei
    valutatori standard (lm-evaluation-harness, MATH), non una concessione.

    Ripetere lo stesso numero non e' contraddirsi: negli scartati finiscono
    solo i valori davvero diversi, perche' e' quello che fa scendere la
    confidenza e manda l'item in cima alla coda di revisione.
    """
    winner = values[-1]
    chosen = normalize_numeric(winner)
    return winner, [v for v in values[:-1] if normalize_numeric(v) != chosen]


def parse_math(raw_text: str) -> ParseResult:
    """Estrae il risultato finale di un problema matematico.

    Ordine: ``####`` (marcatore di GSM8K), poi ``\\boxed{}``, poi una
    dichiarazione tipo "the answer is 42", infine l'ultimo numero del testo.
    Quando la stessa forma compare piu' volte con valori diversi vince
    l'ultima: e' quella la risposta finale del modello.
    """
    text = normalize_output(raw_text)
    if not text:
        return ParseResult(STATUS_UNPARSABLE, reason="Risposta vuota")

    # `####` e `\boxed{}` sono entrambi marcatori espliciti di risposta finale:
    # si mettono nello stesso insieme e vince quello scritto piu' avanti nel
    # testo, senza dare per principio la precedenza a una delle due forme — un
    # modello che apre con \boxed e poi chiude con #### (o viceversa) non deve
    # dipendere da quale forma abbiamo deciso di preferire.
    markers = ([(m.start(), m.group(1)) for m in _HASH_FINAL.finditer(text)]
               + _boxed_spans(text))
    if markers:
        markers.sort(key=lambda pair: pair[0])
        values = [value for _pos, value in markers]
        distinct = _dedupe(normalize_numeric(v) for v in values)
        if len(distinct) > 1 and _SAME_LINE_ALTERNATIVE.search(text):
            return ParseResult(
                STATUS_AMBIGUOUS,
                tier=TIER_DECLARED,
                candidates=_dedupe(values),
                reason=f"Risposta duplice: {len(distinct)} valori offerti come "
                       f"alternative ({', '.join(_dedupe(values)[:4])})",
            )
        value, superseded = _last_conflicting(values)
        return ParseResult(
            STATUS_RESOLVED, value=value, tier=TIER_DECLARED,
            candidates=_dedupe(values), rejected=_dedupe(superseded),
            reason=(f"{len(distinct)} risposte finali in conflitto: vale l'ultima"
                    if len(distinct) > 1 else ""),
        )

    declared = [m.group(1) for m in _MATH_DECLARATION.finditer(text)]
    if declared:
        value, superseded = _last_conflicting(declared)
        distinct = _dedupe(normalize_numeric(d) for d in declared)
        return ParseResult(
            STATUS_RESOLVED, value=value, tier=TIER_DECLARED,
            candidates=_dedupe(declared), rejected=_dedupe(superseded),
            reason=(f"{len(distinct)} risultati dichiarati in conflitto: vale l'ultimo"
                    if len(distinct) > 1 else ""),
        )

    numbers = [m.group(0) for m in _NUMBER.finditer(text)]
    if numbers:
        # Nessuna forma dichiarata: l'ultimo numero e' una congettura, quindi
        # tier debole — la UI lo mostra come confidenza bassa.
        return ParseResult(
            STATUS_RESOLVED, value=numbers[-1], tier=TIER_MENTION, candidates=_dedupe(numbers[-3:])
        )

    return ParseResult(STATUS_UNPARSABLE, reason="Nessun valore numerico nella risposta")


# ---------------------------------------------------------------- testo libero / booleano

# Solo sinonimi veri di vero/falso. "valid"/"invalid" stavano qui per errore:
# sono i target letterali del task BBH formal_fallacies, e mapparli su un
# booleano rendeva illeggibile una risposta esatta come "valid".
_BOOL_WORDS = {
    "true": "true", "false": "false", "vero": "true", "falso": "false",
    "yes": "true", "no": "false", "si": "true", "sì": "true",
}

_FREE_DECLARATION = re.compile(
    r"\b(?:answer|risposta|result|risultato|output|solution|soluzione)\b"
    r"\s*(?:is|was|=|:|->|—|–)?\s*"
    r"[\"'“*\(\[]*([^\n\"'”*\)\]]{1,80})",
    re.I,
)


def normalize_text_answer(value: str) -> str:
    """Forma canonica per confronti su testo libero."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = _LATEX_NOISE.sub("", text)
    text = re.sub(r"[\s]+", " ", text)
    text = text.strip(" .,:;!?\"'()[]{}*-")
    return _BOOL_WORDS.get(text, text)


def parse_free_form(raw_text: str, expected: str = "") -> ParseResult:
    """Estrae una risposta breve non a scelta multipla (BBH, booleani, parole).

    Quando la verita' di base e' un booleano si cercano solo i due valori
    possibili: se il testo contiene sia "true" sia "false" come affermazioni, il
    modello non ha deciso e l'item va in revisione.
    """
    text = normalize_output(raw_text)
    if not text:
        return ParseResult(STATUS_UNPARSABLE, reason="Risposta vuota")

    target = normalize_text_answer(expected)
    if target in ("true", "false"):
        hits = _dedupe(
            _BOOL_WORDS[m.group(0).lower()]
            for m in re.finditer(r"\b(?:true|false|vero|falso|yes|no|si|sì)\b", text, re.I)
        )
        if len(hits) > 1:
            return ParseResult(
                STATUS_AMBIGUOUS,
                tier=TIER_MENTION,
                candidates=hits,
                reason=f"Risposta duplice: sia {hits[0]} sia {hits[1]} nella stessa risposta",
            )
        if hits:
            return ParseResult(STATUS_RESOLVED, value=hits[0], tier=TIER_DECLARED, candidates=hits)
        return ParseResult(STATUS_UNPARSABLE, reason="Nessun valore booleano riconoscibile")

    exact = normalize_text_answer(text)
    if target and exact == target:
        return ParseResult(STATUS_RESOLVED, value=text.strip(), tier=TIER_EXACT)

    declared = _dedupe(normalize_text_answer(m.group(1)) for m in _FREE_DECLARATION.finditer(text))
    declared = [d for d in declared if d]
    if declared:
        if len(declared) > 1 and target and target in declared:
            return ParseResult(
                STATUS_AMBIGUOUS,
                tier=TIER_DECLARED,
                candidates=declared,
                reason=f"Risposta duplice: {len(declared)} affermazioni finali diverse",
            )
        return ParseResult(STATUS_RESOLVED, value=declared[0], tier=TIER_DECLARED, candidates=declared)

    if target and target in exact:
        return ParseResult(STATUS_RESOLVED, value=target, tier=TIER_MENTION, candidates=[target])

    first_line = text.splitlines()[0].strip()
    if first_line:
        return ParseResult(
            STATUS_RESOLVED, value=first_line, tier=TIER_MENTION, candidates=[normalize_text_answer(first_line)]
        )
    return ParseResult(STATUS_UNPARSABLE, reason="Nessuna risposta finale riconoscibile")


# ---------------------------------------------------------------- estrazione codice

_PY_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)(?:```|\Z)", re.S | re.I)


def extract_python_code(raw_text: str, prompt: str = "") -> str:
    """Isola il codice Python da una risposta, recinzioni o prosa incluse.

    HumanEval consegna un prompt-firma che il modello a volte ripete e a volte
    solo continua: entrambe le forme devono ricomporsi in un modulo eseguibile.
    """
    if not raw_text:
        return ""
    text = _THINK_BLOCK.sub(" ", raw_text)
    text = _THINK_OPEN.sub(" ", text)

    blocks = [b.strip("\n") for b in _PY_FENCE.findall(text) if b.strip()]
    if blocks:
        # Il blocco piu' lungo e' quasi sempre la soluzione, non un esempio d'uso.
        code = max(blocks, key=len)
    else:
        code = text

    signature = (prompt or "").strip()
    # Solo HumanEval passa un prompt che *e'* codice (firma + docstring). MBPP
    # descrive il compito a parole: incollarlo davanti al codice produceva un
    # modulo non compilabile e bocciava anche la soluzione di riferimento.
    prompt_is_code = bool(re.search(r"^\s*(?:def|from|import|class)\s", signature, re.M))
    if prompt_is_code:
        head = signature.splitlines()[-1] if signature.splitlines() else ""
        indented = code.startswith((" ", "\t"))
        defines = re.search(r"^\s*def\s+\w+", code, re.M) is not None
        if indented and not defines:
            # Continuazione pura del corpo: va riattaccata alla firma originale.
            return signature.rstrip("\n") + "\n" + code
        if head and defines and head.strip() not in code:
            return signature.rstrip("\n") + "\n\n" + code
    return code


# ---------------------------------------------------------------- giudizio unificato

_MC_SUITES = {"mmlu", "mmlu_pro", "arc", "hellaswag", "truthfulqa", "gpqa"}
_MATH_SUITES = {"gsm8k", "math"}
_CODE_SUITES = {"humaneval", "mbpp"}


def grade_answer(item: dict, output_text: str) -> dict:
    """Assegna un verdetto a una singola risposta del modello.

    Restituisce sempre un dizionario con `verdict`, `passed`, `parsed` e
    `needs_review`, cosi' che il chiamante non debba piu' distinguere fra suite:
    la logica per tipo di benchmark vive solo qui.
    """
    suite = (item.get("suite") or "").lower()
    options = item.get("options") or []
    correct_choice = (item.get("correct_choice") or "").strip()

    if suite in _CODE_SUITES:
        # La verifica del codice richiede l'esecuzione dei test: la fa
        # core.training.code_exec, che chiama grade_code_result con l'esito.
        return {
            "verdict": VERDICT_UNPARSABLE,
            "passed": False,
            "needs_review": True,
            "parsed": ParseResult(STATUS_UNPARSABLE, reason="Suite di codice: usare run_code_item").as_dict(),
        }

    if suite in _MATH_SUITES or (not options and re.search(r"\d", correct_choice or "")):
        parsed = parse_math(output_text)
        return _verdict_from(parsed, lambda v: numeric_equal(v, correct_choice))

    if options or suite in _MC_SUITES:
        parsed = parse_multiple_choice(output_text, options)
        expected = correct_choice.upper()
        return _verdict_from(parsed, lambda v: v.upper() == expected)

    parsed = parse_free_form(output_text, correct_choice)
    expected_norm = normalize_text_answer(correct_choice)
    return _verdict_from(parsed, lambda v: normalize_text_answer(v) == expected_norm)


def _verdict_from(parsed: ParseResult, matches) -> dict:
    """Traduce un ParseResult in verdetto, applicando il confronto fornito."""
    if parsed.status == STATUS_AMBIGUOUS:
        return {"verdict": VERDICT_AMBIGUOUS, "passed": False, "needs_review": True,
                "parsed": parsed.as_dict()}
    if parsed.status == STATUS_UNPARSABLE or parsed.value is None:
        return {"verdict": VERDICT_UNPARSABLE, "passed": False, "needs_review": True,
                "parsed": parsed.as_dict()}
    try:
        ok = bool(matches(parsed.value))
    except Exception:  # confronto impossibile: meglio rivedere che dare per errato
        return {"verdict": VERDICT_UNPARSABLE, "passed": False, "needs_review": True,
                "parsed": parsed.as_dict()}
    return {
        "verdict": VERDICT_PASS if ok else VERDICT_FAIL,
        "passed": ok,
        "needs_review": False,
        "parsed": parsed.as_dict(),
    }


def grade_code_result(execution: dict) -> dict:
    """Verdetto per un item di codice, dato l'esito dell'esecuzione dei test."""
    status = (execution or {}).get("status", "error")
    if status == "passed":
        verdict, passed, review = VERDICT_PASS, True, False
    elif status == "failed":
        verdict, passed, review = VERDICT_FAIL, False, False
    elif status == "no_tests":
        # Cache scaricata prima che salvassimo i test ufficiali: non e' un
        # fallimento del modello, e dichiararlo tale falserebbe il punteggio.
        verdict, passed, review = VERDICT_UNPARSABLE, False, True
    else:  # timeout, no_code, error
        verdict, passed, review = VERDICT_UNPARSABLE, False, True
    return {
        "verdict": verdict,
        "passed": passed,
        "needs_review": review,
        "parsed": {
            "status": STATUS_RESOLVED if status in ("passed", "failed") else STATUS_UNPARSABLE,
            "value": status,
            "tier": TIER_EXACT if status in ("passed", "failed") else "",
            "confidence": "high" if status in ("passed", "failed") else "none",
            "candidates": [],
            "rejected": [],
            "reason": (execution or {}).get("detail", ""),
        },
        "execution": execution,
    }


# ---------------------------------------------------------------- compatibilita'

def extract_chosen_letter(output_text: str, options: list | None = None) -> str | None:
    """Compat: la lettera scelta, o None se assente **o ambigua**.

    Firma conservata per i chiamanti esistenti. A differenza della versione
    precedente, una risposta duplice restituisce None invece di premiare la
    prima lettera incontrata.
    """
    parsed = parse_multiple_choice(output_text, options)
    return parsed.value if parsed.status == STATUS_RESOLVED else None
