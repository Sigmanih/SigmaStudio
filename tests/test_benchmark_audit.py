# ==============================================================================
# tests/test_benchmark_audit.py — La verifica dei verdetti verifica sé stessa
# ==============================================================================
"""Copre core/training/audit.py.

Un audit che grida al lupo è peggio di nessun audit: fa perdere fiducia in
verdetti corretti. Metà di questi test sono casi in cui l'audit **non** deve
segnalare nulla, e vengono tutti da falsi allarmi trovati sui run reali.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.training.audit import (
    BLOCKING_FINDINGS, FINDING_FALSE_NEGATIVE, FINDING_FALSE_POSITIVE,
    FINDING_REASONED_THEN_LOST, FINDING_UNDECLARED_PASS,
    audit_result, audit_run, final_declaration,
)

BS = chr(92)


def boxed(value):
    return BS + "boxed{" + str(value) + "}"


def _check(item, text, verdict, tier="declared"):
    return audit_result(item, text, verdict, {"tier": tier})


MATH_ITEM = {"suite": "gsm8k", "options": [], "correct_choice": "72"}
MC_ITEM = {"suite": "mmlu", "options": ["A) uno", "B) due", "C) tre", "D) quattro"],
           "correct_choice": "C"}


# ====================================================== l'oracolo indipendente

class TestFinalDeclaration:

    def test_the_last_marker_wins(self):
        text = f"{boxed(10)}\nrivedendo i conti...\n#### 72"
        assert final_declaration(text, MATH_ITEM) == "72"

    def test_a_markdown_heading_is_not_a_declaration(self):
        """'#### 5. State the Answer' è un titolo. Una versione permissiva di
        questo controllo accusava il parser di un errore dell'audit."""
        text = f"70 + 30 = 100 pounds\n\n#### 5. State the Answer\n{boxed(100)}"
        assert final_declaration(text, {**MATH_ITEM, "correct_choice": "100"}) == "100"

    def test_a_bare_letter_is_a_declaration(self):
        """Il prompt della scelta multipla chiede una lettera e basta."""
        assert final_declaration("C", MC_ITEM) == "C"
        assert final_declaration(" c. ", MC_ITEM) == "C"

    def test_listing_every_option_is_not_choosing(self):
        assert final_declaration("A) No, B) No, C) No, D) Si", MC_ITEM) is None

    def test_a_numeric_marker_is_ignored_when_the_answer_is_a_word(self):
        """Su BBH l'attesa è 'valid': un '#### 7' rimasto in coda alla
        generazione è spazzatura, non una dichiarazione."""
        item = {"suite": "bbh", "options": [], "correct_choice": "valid"}
        text = "The argument is valid.\nTherefore the answer is valid<|end|>\n#### 7<"
        assert final_declaration(text, item) == "valid"

    def test_no_declaration_at_all(self):
        assert final_declaration("Il totale viene 72 mele.", MATH_ITEM) is None


# =========================================================== i due errori veri

class TestBlockingFindings:

    def test_a_declared_right_answer_marked_wrong_is_a_false_negative(self):
        finding = _check(MATH_ITEM, f"ragionamento...\n{boxed(72)}", "fail")
        assert finding["finding"] == FINDING_FALSE_NEGATIVE

    def test_a_pass_on_an_answer_never_declared_is_a_false_positive(self):
        finding = _check(MATH_ITEM, f"ragionamento...\n{boxed(65)}", "pass")
        assert finding["finding"] == FINDING_FALSE_POSITIVE
        assert "65" in finding["detail"]

    def test_both_findings_are_blocking(self):
        assert FINDING_FALSE_NEGATIVE in BLOCKING_FINDINGS
        assert FINDING_FALSE_POSITIVE in BLOCKING_FINDINGS


# ============================================ i casi in cui deve stare zitto

class TestNoFalseAlarms:

    def test_a_correct_verdict_raises_nothing(self):
        assert _check(MATH_ITEM, f"...\n{boxed(72)}", "pass") is None

    def test_a_genuine_model_error_raises_nothing(self):
        assert _check(MATH_ITEM, f"...\n{boxed(65)}", "fail") is None

    def test_an_earlier_mention_of_the_right_answer_is_not_a_false_negative(self):
        """Il modello nomina 72 strada facendo e poi dichiara 65: il verdetto
        negativo è corretto, va solo annotato che c'era arrivato."""
        finding = _check(MATH_ITEM, f"prima 72, poi rivedo\n{boxed(65)}", "fail")
        assert finding["finding"] == FINDING_REASONED_THEN_LOST
        assert finding["finding"] not in BLOCKING_FINDINGS

    def test_an_item_already_in_review_is_left_alone(self):
        assert _check(MATH_ITEM, "boh", "ambiguous") is None

    def test_an_item_without_an_expected_answer_is_left_alone(self):
        assert _check({"suite": "x", "options": [], "correct_choice": ""}, "qualcosa", "fail") is None

    def test_a_multiple_choice_pass_on_a_bare_letter_is_clean(self):
        assert _check(MC_ITEM, "C", "pass", tier="exact") is None


# ====================================================== il pass non dichiarato

class TestUndeclaredPass:

    def test_a_pass_without_any_declaration_is_flagged_but_not_blocking(self):
        finding = _check(MATH_ITEM, "Il totale viene 72 mele.", "pass", tier="mention")
        assert finding["finding"] == FINDING_UNDECLARED_PASS
        assert finding["finding"] not in BLOCKING_FINDINGS

    def test_a_weak_tier_is_flagged_even_when_the_answer_was_declared(self):
        finding = _check(MATH_ITEM, f"{boxed(72)}", "pass", tier="mention")
        assert finding["finding"] == FINDING_UNDECLARED_PASS


# ============================================================ il run completo

class TestAuditRun:

    def _row(self, **kw):
        base = {"id": "x", "suite": "gsm8k", "options": [], "correct_choice": "72",
                "given_answer": f"{boxed(72)}", "verdict": "pass"}
        return {**base, **kw}

    def test_a_clean_run_has_full_trust(self):
        report = audit_run([self._row(id=str(i)) for i in range(10)])
        assert report["blocking"] == 0
        assert report["trust"] == 1.0
        assert report["findings"] == []

    def test_the_trust_drops_on_undeclared_passes(self):
        rows = [self._row(id=str(i)) for i in range(8)]
        # Nessuna dichiarazione: il pass poggia sull'ultimo numero del testo.
        rows.append(self._row(id="und", given_answer="il totale viene 72"))
        report = audit_run(rows)
        assert report["counts"][FINDING_UNDECLARED_PASS] == 1
        assert report["trust"] < 1.0

    def test_the_current_parser_cannot_produce_a_false_positive_here(self):
        """`audit_run` rigiudica prima di verificare, quindi un falso positivo
        salvato da una versione precedente sparisce — ed è giusto così: il
        conteggio `regraded` è ciò che segnala il run vecchio. Il falso
        positivo si verifica sul singolo verdetto, non sul run rigiudicato."""
        rows = [self._row(id="fp", given_answer=boxed(65), verdict="pass")]
        report = audit_run(rows)
        assert report["regraded"] == 1
        assert report["blocking"] == 0

    def test_code_items_are_not_judged_by_the_parser(self):
        """La correttezza del codice si stabilisce eseguendo i test."""
        rows = [self._row(id="c", suite="humaneval", execution={"status": "passed"})]
        report = audit_run(rows)
        assert report["counts"]["saltati_codice"] == 1
        assert report["findings"] == []

    def test_the_run_is_regraded_from_the_raw_answers(self):
        """Un verdetto salvato da una versione precedente del parser non deve
        essere preso per buono: l'audit rigiudica e conta le differenze."""
        rows = [self._row(id="vecchio", verdict="fail")]
        report = audit_run(rows)
        assert report["regraded"] == 1
