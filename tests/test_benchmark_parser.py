# ==============================================================================
# tests/test_benchmark_parser.py — Test del grader dei benchmark ufficiali
# ==============================================================================
"""Copre il punto delicato del motore di benchmark: decidere se una risposta e'
una scelta, due scelte in conflitto, oppure nessuna scelta.

Il caso che ha motivato questi test: "The correct answer is A. The correct choice
is H." veniva contato come corretto perche' il vecchio estrattore prendeva la
prima lettera trovata e ignorava il resto.
"""

import json
import os
import shutil
import tempfile
import unittest

from core.training.answer_parser import (
    VERDICT_AMBIGUOUS, VERDICT_FAIL, VERDICT_PASS, VERDICT_UNPARSABLE,
    STATUS_AMBIGUOUS, STATUS_RESOLVED, STATUS_UNPARSABLE,
    extract_chosen_letter, extract_python_code, grade_answer, numeric_equal,
    option_letters, parse_free_form, parse_math, parse_multiple_choice,
)

OPTIONS_4 = ["A) Reticolo Endoplasmatico", "B) Mitocondrio", "C) Apparato di Golgi", "D) Lisosoma"]


class TestMultipleChoiceResolution(unittest.TestCase):
    """Risposte che contengono una sola scelta riconoscibile."""

    def _letter(self, text, options=OPTIONS_4):
        result = parse_multiple_choice(text, options)
        self.assertEqual(result.status, STATUS_RESOLVED, f"non risolta: {text!r} ({result.reason})")
        return result.value

    def test_bare_letter(self):
        self.assertEqual(self._letter("B"), "B")

    def test_letter_with_punctuation(self):
        for text in ("B)", "(B)", "B.", "B:", '"B"', "**B**", "  b  "):
            self.assertEqual(self._letter(text), "B", f"forma non riconosciuta: {text!r}")

    def test_declared_answer(self):
        for text in ("The correct answer is C.", "Answer: C", "risposta corretta: C",
                     "La risposta è C", "C is the correct answer", "The final answer is C"):
            self.assertEqual(self._letter(text), "C", f"forma non riconosciuta: {text!r}")

    def test_anchored_option_line(self):
        self.assertEqual(self._letter("D) Lisosoma"), "D")

    def test_option_body_without_letter(self):
        self.assertEqual(self._letter("Mitocondrio"), "B")

    def test_reasoning_block_is_discarded(self):
        # Il blocco di ragionamento valuta tutte le opzioni: contarlo renderebbe
        # ambigua ogni risposta di un modello che ragiona ad alta voce.
        text = "<think>Could be A, or maybe C, let me check D</think>\nAnswer: B"
        self.assertEqual(self._letter(text), "B")

    def test_lowercase_declaration(self):
        self.assertEqual(self._letter("the answer is d."), "D")

    def test_mmlu_pro_extended_range(self):
        options = [f"{chr(65 + i)}) opzione {i}" for i in range(10)]
        self.assertEqual(self._letter("The correct answer is J.", options), "J")
        self.assertEqual(option_letters(options)[-1], "J")


class TestMultipleChoiceAmbiguity(unittest.TestCase):
    """Risposte duplici: nessun verdetto, vanno nella coda di revisione."""

    def _ambiguous(self, text, options=OPTIONS_4):
        result = parse_multiple_choice(text, options)
        self.assertEqual(result.status, STATUS_AMBIGUOUS,
                         f"attesa ambiguita' per {text!r}, ottenuto {result.status}/{result.value}")
        return result

    def test_two_conflicting_declarations(self):
        result = self._ambiguous("The correct answer is A. The correct choice is H.")
        self.assertEqual(result.candidates, ["A", "H"])
        self.assertIn("duplice", result.reason.lower())

    def test_enumerated_answers(self):
        for text in ("Answer: A and also D", "Answer: A, B", "The answer is B or C",
                     'The answer is "a" and the answer is "b".'):
            self._ambiguous(text)

    def test_ambiguous_never_scores_a_pass(self):
        # Il punto centrale: due risposte non diventano una risposta giusta
        # solo perche' una delle due combacia.
        item = {"suite": "mmlu", "options": OPTIONS_4, "correct_choice": "A"}
        graded = grade_answer(item, "The correct answer is A. The correct choice is H.")
        self.assertEqual(graded["verdict"], VERDICT_AMBIGUOUS)
        self.assertFalse(graded["passed"])
        self.assertTrue(graded["needs_review"])

    def test_compat_extractor_refuses_ambiguity(self):
        self.assertIsNone(extract_chosen_letter("The answer is A. The choice is H.", OPTIONS_4))
        self.assertEqual(extract_chosen_letter("The answer is A.", OPTIONS_4), "A")


class TestMultipleChoiceUnparsable(unittest.TestCase):
    """Risposte senza alcuna scelta: da rivedere, non da bocciare."""

    def _unparsable(self, text, options=OPTIONS_4):
        result = parse_multiple_choice(text, options)
        self.assertEqual(result.status, STATUS_UNPARSABLE,
                         f"attesa risposta illeggibile per {text!r}, ottenuto {result.status}/{result.value}")
        return result

    def test_empty_answer(self):
        self._unparsable("")

    def test_numeric_answer_to_a_letter_question(self):
        self._unparsable("The correct answer is 8.")

    def test_abbreviation_is_not_a_letter(self):
        # "e.g." produceva la lettera E, "i.e." la I.
        self._unparsable("The letter of the correct choice is e.g. something else.")

    def test_plural_keyword_is_not_a_letter(self):
        # "LETTERS ARE H AND K" faceva combaciare "LETTER" e catturava la S.
        result = self._unparsable("The letters in the correct order are H and K.")
        self.assertNotIn("S", result.candidates)

    def test_out_of_range_letter_is_rejected(self):
        result = self._unparsable("The correct answer is T(-3,2).")
        self.assertIn("T", result.rejected)

    def test_algebraic_expression_is_not_a_choice(self):
        for text in ("The correct answer is (a+b+c)/len(z_7)).",
                     "The inverse of the expression is (a+b)/2."):
            self._unparsable(text)

    def test_unparsable_is_not_counted_as_failure(self):
        item = {"suite": "mmlu", "options": OPTIONS_4, "correct_choice": "B"}
        graded = grade_answer(item, "The correct answer is 8.")
        self.assertEqual(graded["verdict"], VERDICT_UNPARSABLE)
        self.assertTrue(graded["needs_review"])


class TestMathGrading(unittest.TestCase):
    def test_boxed_value(self):
        result = parse_math(r"\boxed{42} because of the sum")
        self.assertEqual(result.status, STATUS_RESOLVED)
        self.assertEqual(result.value, "42")

    def test_a_self_correction_resolves_to_the_last_value(self):
        """Un modello che si ricrede ha una risposta finale, non due.

        Trattarle come ambigue mandava in revisione — e in pratica contava come
        fallimento — ogni risposta corretta preceduta da un tentativo.
        """
        result = parse_math(r"\boxed{18} ... on reflection \boxed{20}")
        self.assertEqual(result.status, STATUS_RESOLVED)
        self.assertEqual(result.value, "20")
        self.assertEqual(result.rejected, ["18"])
        # la contraddizione resta visibile a chi rivede
        self.assertEqual(result.confidence, "medium")
        self.assertIn("conflitto", result.reason)

    def test_repeated_identical_boxed_value_is_fine(self):
        result = parse_math(r"\boxed{7} and again \boxed{7}")
        self.assertEqual(result.status, STATUS_RESOLVED)
        self.assertEqual(result.confidence, "high")   # nessuna contraddizione

    def test_alternatives_offered_on_one_line_stay_ambiguous(self):
        """"o X o Y" non ha un ordine che dica quale sia definitiva."""
        result = parse_math(r"The result is either \boxed{3} or \boxed{4}")
        self.assertEqual(result.status, STATUS_AMBIGUOUS)

    def test_gsm8k_hash_marker_is_the_final_answer(self):
        result = parse_math("Reasoning here.\n#### 42")
        self.assertEqual(result.value, "42")

    def test_hash_marker_wins_over_an_earlier_boxed(self):
        """Il caso reale: il modello apre con un boxed e chiude con ####."""
        text = "\\boxed{682}\nMary has 80 plants.\n#### 58"
        self.assertEqual(parse_math(text).value, "58")

    def test_a_later_boxed_wins_over_an_earlier_hash(self):
        """Nessuna delle due forme ha la precedenza per principio: conta la posizione."""
        text = "#### 180\nrivedendo i conti...\n\\boxed{720}"
        self.assertEqual(parse_math(text).value, "720")

    def test_a_markdown_heading_is_not_a_final_answer(self):
        """'## 2 Passaggi' e' un titolo, non la risposta."""
        text = "## 2 Passaggi\nIl prodotto e' 3*4.\n\\boxed{12}"
        self.assertEqual(parse_math(text).value, "12")

    def test_a_wrong_answer_stated_last_still_fails(self):
        """La regola dell'ultimo non deve regalare punti: se il modello finisce
        su un valore sbagliato, e' un fallimento anche se prima aveva ragione."""
        item = {"suite": "gsm8k", "options": [], "correct_choice": "6"}
        text = "\\boxed{6}\nJana has 27/3 = 9 puppies.\nOf those, 9/3 = 3 are girls.\n#### 3"
        self.assertEqual(grade_answer(item, text)["verdict"], VERDICT_FAIL)

    def test_declared_result(self):
        self.assertEqual(parse_math("The answer is 1,200 euros").value, "1,200")

    def test_numeric_equivalence(self):
        self.assertTrue(numeric_equal(r"\frac{1}{2}", "0.5"))
        self.assertTrue(numeric_equal("$1,200", "1200"))
        self.assertTrue(numeric_equal(r"50\%", "50"))
        self.assertTrue(numeric_equal("3.0", "3"))
        self.assertFalse(numeric_equal("3", "4"))

    def test_formatting_does_not_fail_a_correct_answer(self):
        item = {"suite": "gsm8k", "options": [], "correct_choice": "1200"}
        self.assertEqual(grade_answer(item, r"\boxed{1{,}200}")["verdict"], VERDICT_PASS)

    def test_wrong_math_answer_fails(self):
        item = {"suite": "gsm8k", "options": [], "correct_choice": "3"}
        self.assertEqual(grade_answer(item, r"\boxed{5}")["verdict"], VERDICT_FAIL)


class TestStratifiedSampling(unittest.TestCase):
    """Un campione deve rappresentare ogni suite, non solo le più grandi.

    Il campionamento casuale sull'unione le pesa per dimensione: MMLU ha 14.042
    quesiti e GSM8K 1.319, quindi su 100 estrazioni GSM8K ne prende due — e può
    prenderne zero. È successo: un modello messo a punto proprio su GSM8K è
    stato confrontato con la sua base su un campione senza un solo GSM8K.
    """

    SIZES = {"mmlu": 14042, "mmlu_pro": 12032, "math": 12500, "hellaswag": 10042,
             "bbh": 6511, "gsm8k": 1319, "truthfulqa": 817, "arc": 1172,
             "gpqa": 448, "humaneval": 164, "mbpp": 500}

    def _suites(self):
        return {s: [{"id": f"{s}_{i}", "suite": s} for i in range(n)]
                for s, n in self.SIZES.items()}

    def _sample(self, total):
        from core.training.benchmarks import _stratified_sample
        return _stratified_sample(self._suites(), total)

    def test_every_suite_appears_in_a_hundred_item_sample(self):
        from collections import Counter
        counts = Counter(i["suite"] for i in self._sample(100))
        missing = set(self.SIZES) - set(counts)
        self.assertEqual(missing, set(), f"suite assenti dal campione: {missing}")

    def test_the_small_suites_get_a_usable_share(self):
        from collections import Counter
        counts = Counter(i["suite"] for i in self._sample(100))
        self.assertGreaterEqual(counts["gsm8k"], 5)

    def test_the_sample_has_exactly_the_size_requested(self):
        for total in (30, 100, 250):
            self.assertEqual(len(self._sample(total)), total)

    def test_two_calls_give_the_same_sample(self):
        """Senza questo il confronto fra due modelli non sarebbe appaiato."""
        first = [i["id"] for i in self._sample(100)]
        second = [i["id"] for i in self._sample(100)]
        self.assertEqual(first, second)

    def test_a_suite_smaller_than_the_floor_is_not_over_drawn(self):
        from core.training.benchmarks import _stratified_sample
        tiny = {"a": [{"id": f"a{i}"} for i in range(2)],
                "b": [{"id": f"b{i}"} for i in range(500)]}
        picked = _stratified_sample(tiny, 50)
        self.assertEqual(sum(1 for p in picked if p["id"].startswith("a")), 2)
        self.assertEqual(len(picked), 50)


class TestMathPromptProtocol(unittest.TestCase):
    """Il prompt deve far ragionare il modello PRIMA di chiedergli il risultato.

    La versione precedente pretendeva la risposta sulla prima riga e il
    ragionamento dopo: misurava quanto il modello indovina a freddo, non quanto
    sa ragionare. Su GSM8K costava 50 punti di accuratezza allo stesso modello.
    """

    def _payload(self, suite="gsm8k"):
        from core.training.benchmarks import _prepare_benchmark_payload
        item = {"suite": suite, "prompt": "Two plus two?", "options": [],
                "correct_choice": "4"}
        return _prepare_benchmark_payload(item, "modello-di-prova")

    def test_the_answer_is_asked_for_last(self):
        payload = self._payload()
        text = (payload["prompt"] + " " + payload["system"]).lower()
        self.assertIn("step by step", text)
        self.assertIn("last line", text)
        self.assertNotIn("first line", text)

    def test_only_one_final_answer_is_requested(self):
        payload = self._payload()
        self.assertIn("exactly one final answer",
                      (payload["prompt"] + " " + payload["system"]).lower())

    def test_the_protocol_is_recorded_for_reproducibility(self):
        """Due run con prompt diversi non sono confrontabili: il certificato
        deve dire quale protocollo ha usato."""
        from core.training.benchmarks import PROMPT_PROTOCOL, GRADER_VERSION
        self.assertGreaterEqual(PROMPT_PROTOCOL, 2)
        self.assertTrue(GRADER_VERSION.startswith("sigma.answer_parser/"))


class TestFreeFormGrading(unittest.TestCase):
    def test_boolean_target(self):
        item = {"suite": "bbh", "options": [], "correct_choice": "False"}
        self.assertEqual(grade_answer(item, "False")["verdict"], VERDICT_PASS)
        self.assertEqual(grade_answer(item, "True")["verdict"], VERDICT_FAIL)

    def test_both_booleans_is_ambiguous(self):
        result = parse_free_form("It is True. Actually, False.", "False")
        self.assertEqual(result.status, STATUS_AMBIGUOUS)

    def test_word_answer(self):
        item = {"suite": "bbh", "options": [], "correct_choice": "valid"}
        self.assertEqual(grade_answer(item, "valid")["verdict"], VERDICT_PASS)


class TestCodeExtraction(unittest.TestCase):
    def test_fenced_block_is_isolated(self):
        text = "Here you go:\n```python\ndef f(x):\n    return x + 1\n```\nHope it helps."
        self.assertIn("return x + 1", extract_python_code(text))
        self.assertNotIn("Hope it helps", extract_python_code(text))

    def test_indented_continuation_reattaches_signature(self):
        prompt = "def add(a, b):\n"
        code = extract_python_code("    return a + b", prompt)
        self.assertIn("def add(a, b):", code)
        self.assertIn("return a + b", code)
        compile(code, "<test>", "exec")

    def test_prose_prompt_is_not_prepended(self):
        # I prompt MBPP sono descrizioni in linguaggio naturale: incollarli
        # davanti al codice produceva un modulo non compilabile.
        prompt = "Write a python function to remove the first occurrence."
        code = extract_python_code("```python\ndef remove(s):\n    return s\n```", prompt)
        self.assertNotIn("Write a python function", code)
        compile(code, "<test>", "exec")


class TestCodeExecution(unittest.TestCase):
    """Verifica per esecuzione: le suite di codice si misurano in pass@1."""

    HUMANEVAL_ITEM = {
        "suite": "humaneval",
        "prompt": "def add_one(n):\n",
        "verification": {
            "test": "def check(candidate):\n    assert candidate(1) == 2\n    assert candidate(5) == 6\n",
            "entry_point": "add_one",
        },
    }

    def _run(self, output, item=None, **kwargs):
        from core.training.code_exec import run_code_item
        return run_code_item(item or self.HUMANEVAL_ITEM, output, **kwargs)

    def test_correct_solution_passes(self):
        result = self._run("```python\ndef add_one(n):\n    return n + 1\n```")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(grade_code_verdict(result), VERDICT_PASS)

    def test_wrong_solution_fails(self):
        result = self._run("```python\ndef add_one(n):\n    return n\n```")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(grade_code_verdict(result), VERDICT_FAIL)

    def test_no_code_goes_to_review(self):
        result = self._run("I am not able to solve this task.")
        self.assertEqual(result["status"], "no_code")
        self.assertEqual(grade_code_verdict(result), VERDICT_UNPARSABLE)

    def test_infinite_loop_times_out(self):
        result = self._run("```python\ndef add_one(n):\n    while True:\n        pass\n```", timeout=3)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(grade_code_verdict(result), VERDICT_UNPARSABLE)

    def test_missing_tests_goes_to_review_not_failure(self):
        # Cache scaricata prima che salvassimo i test ufficiali: non e' colpa
        # del modello, quindi non deve pesare come pass@1 mancato.
        item = {"suite": "humaneval", "prompt": "def f(): pass", "verification": {}}
        result = self._run("```python\ndef f():\n    return 1\n```", item=item)
        self.assertEqual(result["status"], "no_tests")
        self.assertEqual(grade_code_verdict(result), VERDICT_UNPARSABLE)

    def test_crlf_solution_is_normalized(self):
        # MBPP arriva con CRLF: senza normalizzare, su Windows il file scritto
        # aveva righe doppie e nemmeno la soluzione di riferimento compilava.
        item = {
            "suite": "mbpp",
            "prompt": "Write a function that doubles a number.",
            "verification": {"test_list": ["assert double(2) == 4"], "test_setup_code": ""},
        }
        result = self._run("def double(n): \r\n    return n * 2\r\n", item=item)
        self.assertEqual(result["status"], "passed")


def grade_code_verdict(execution):
    from core.training.answer_parser import grade_code_result
    return grade_code_result(execution)["verdict"]


class TestBenchmarkStore(unittest.TestCase):
    """Lo store per job: append, indice laterale, filtri e impaginazione."""

    def setUp(self):
        from core.training import benchmark_store
        self.store = benchmark_store
        self._original_dir = benchmark_store.RUNS_DIR
        self.tmp = tempfile.mkdtemp(prefix="test_temp_bench_")
        benchmark_store.RUNS_DIR = self.tmp
        self.job_id = "test_temp_job"

    def tearDown(self):
        self.store.RUNS_DIR = self._original_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, count=40):
        verdicts = ["pass", "fail", "ambiguous", "unparsable"]
        results = [{
            "id": f"item_{i}", "index": i, "suite": "mmlu" if i % 2 else "arc",
            "verdict": verdicts[i % len(verdicts)],
            "prompt": f"Domanda numero {i}", "given_answer": "risposta",
            "category": "Algebra" if i % 3 else "Fisica",
        } for i in range(count)]
        self.store.append_results(self.job_id, results)
        return results

    def test_append_and_count(self):
        self._seed(40)
        self.assertEqual(self.store.count_results(self.job_id), 40)

    def test_offsets_survive_multiple_appends(self):
        # Il bug che questo copre: con la traduzione dei fine riga di Windows gli
        # offset in byte scivolavano e dalla seconda riga la lettura falliva.
        for _ in range(4):
            self._seed(10)
        page = self.store.read_page(self.job_id, page=1, page_size=40)
        self.assertEqual(page["total"], 40)
        self.assertEqual(len(page["results"]), 40)
        self.assertTrue(all(r.get("id") for r in page["results"]))

    def test_verdict_counts(self):
        self._seed(40)
        counts = self.store.verdict_counts(self.job_id)
        self.assertEqual(counts, {"pass": 10, "fail": 10, "ambiguous": 10, "unparsable": 10})

    def test_review_filter_groups_suspended_verdicts(self):
        self._seed(40)
        page = self.store.read_page(self.job_id, page=1, page_size=100, verdict="review")
        self.assertEqual(page["total"], 20)
        self.assertTrue(all(r["verdict"] in ("ambiguous", "unparsable", "error")
                            for r in page["results"]))

    def test_suite_filter_and_breakdown(self):
        self._seed(40)
        page = self.store.read_page(self.job_id, page=1, page_size=100, suite="arc")
        self.assertEqual(page["total"], 20)
        breakdown = self.store.suite_breakdown(self.job_id)
        self.assertEqual(breakdown["arc"]["total"], 20)
        self.assertEqual(breakdown["mmlu"]["total"], 20)

    def test_text_search(self):
        self._seed(40)
        page = self.store.read_page(self.job_id, page=1, page_size=10, query="Domanda numero 7")
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["results"][0]["id"], "item_7")

    def test_pagination_bounds(self):
        self._seed(40)
        page = self.store.read_page(self.job_id, page=99, page_size=15)
        self.assertEqual(page["pages"], 3)
        self.assertEqual(page["page"], 3, "una pagina oltre il limite deve tornare all'ultima")

    def test_review_queue_export(self):
        self._seed(40)
        self.assertEqual(len(self.store.read_review_queue(self.job_id)), 20)

    def test_rebuild_index_recovers_a_corrupt_sidecar(self):
        self._seed(20)
        _, idx_path = self.store._paths(self.job_id)
        with open(idx_path, "w", encoding="utf-8") as fh:
            json.dump({"entries": [[999999, "pass", "mmlu"]] * 20}, fh)
        page = self.store.read_page(self.job_id, page=1, page_size=20)
        self.assertEqual(len(page["results"]), 20, "l'indice incoerente doveva essere ricostruito")

    def test_delete_removes_files(self):
        self._seed(10)
        self.store.delete_results(self.job_id)
        self.assertEqual(self.store.count_results(self.job_id), 0)
        self.assertFalse(any(os.path.exists(p) for p in self.store._paths(self.job_id)))


class TestMetricsAccounting(unittest.TestCase):
    """Le due accuratezze e la coda di revisione devono quadrare."""

    def test_review_items_excluded_from_decided_accuracy(self):
        from core.training.benchmarks import _compute_metrics
        counts = {"pass": 20, "fail": 30, "ambiguous": 10, "unparsable": 40}
        metrics = _compute_metrics(counts, total_done=100, planned_total=100,
                                   total_tokens=1000, total_duration=10.0, latency_sum_ms=50000)
        self.assertEqual(metrics["overall_score"], 20.0)          # 20 su 100 totali
        self.assertEqual(metrics["decided_accuracy_pct"], 40.0)   # 20 su 50 decisi
        self.assertEqual(metrics["tests_review"], 50)
        self.assertEqual(metrics["review_pct"], 50.0)
        self.assertEqual(metrics["avg_latency_ms"], 500)

    def test_no_division_by_zero_on_an_empty_run(self):
        from core.training.benchmarks import _compute_metrics
        metrics = _compute_metrics({}, 0, 0, 0, 0.0, 0)
        self.assertEqual(metrics["overall_score"], 0)
        self.assertEqual(metrics["decided_accuracy_pct"], 0)


class TestParallelCapacity(unittest.TestCase):
    """Quante richieste in parallelo regge un modello: stima, misura, consiglio."""

    def setUp(self):
        from core.training import capacity
        self.capacity = capacity
        self._original_file = capacity.PROFILES_FILE
        self.tmp = tempfile.mkdtemp(prefix="test_temp_cap_")
        capacity.PROFILES_FILE = os.path.join(self.tmp, "profiles.json")

    def tearDown(self):
        self.capacity.PROFILES_FILE = self._original_file
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- stima

    def _estimate_with(self, size_gb, gpus, endpoints=None):
        """Stima su un hardware simulato: `gpus` e' la lista di VRAM libera.

        Endpoint e GPU sono finti di proposito — la stima deve essere verificabile
        senza un Ollama vivo e senza dipendere dalle schede della macchina.
        """
        from unittest.mock import patch
        devices = [{"index": i, "name": f"GPU{i}", "backend": "cuda",
                    "vram_total_gb": free, "vram_free_gb": free}
                   for i, free in enumerate(gpus)]
        snapshot = {
            "gpus": devices,
            "usable_vram_gb": max(gpus) if gpus else 0.0,
            "total_vram_gb": sum(gpus),
            "ram_free_gb": 32.0, "spread_enabled": False,
        }
        pool = endpoints if endpoints is not None else [
            {"url": "http://127.0.0.1:11434", "gpu_index": 0, "reachable": True}
        ]
        with patch.object(self.capacity, "_gpu_snapshot", return_value=snapshot), \
             patch.object(self.capacity, "_model_size_gb", return_value=size_gb), \
             patch("core.training.endpoints.active_endpoints", return_value=pool):
            return self.capacity.estimate_capacity("modello-di-prova")

    def test_small_model_on_large_gpu_allows_many_slots(self):
        result = self._estimate_with(size_gb=1.0, gpus=[16.0])
        self.assertTrue(result["fits_in_vram"])
        self.assertEqual(result["placement"], "GPU")
        self.assertGreater(result["max_parallel_now"], 8)

    def test_slots_shrink_as_the_model_fills_the_card(self):
        roomy = self._estimate_with(size_gb=8.0, gpus=[16.0])
        tight = self._estimate_with(size_gb=14.0, gpus=[16.0])
        self.assertGreater(roomy["max_parallel_now"], tight["max_parallel_now"])

    def test_model_larger_than_vram_falls_back_to_cpu(self):
        result = self._estimate_with(size_gb=24.0, gpus=[16.0])
        self.assertFalse(result["fits_in_vram"])
        self.assertEqual(result["placement"], "CPU / RAM")
        self.assertGreaterEqual(result["max_parallel_now"], 1)

    def test_unknown_model_does_not_claim_capacity(self):
        result = self._estimate_with(size_gb=0.0, gpus=[16.0])
        self.assertEqual(result["max_parallel_now"], 1)
        self.assertFalse(result["fits_in_vram"])

    # ------------------------------------------------- piu' schede, un endpoint

    def test_second_gpu_is_reported_idle_when_it_has_no_endpoint(self):
        # Il caso concreto: due schede, un solo servitore Ollama. La seconda
        # resta ferma perche' un servitore indirizza una GPU sola.
        result = self._estimate_with(size_gb=2.0, gpus=[16.0, 8.0])
        self.assertEqual(len(result["idle_gpus"]), 1)
        self.assertEqual(result["idle_gpus"][0]["index"], 1)
        self.assertLess(result["max_parallel_now"], result["max_parallel_potential"])
        self.assertIn("una sola scheda", result["note"])

    def test_capacity_doubles_once_every_gpu_has_an_endpoint(self):
        pool = [{"url": "http://127.0.0.1:11434", "gpu_index": 0, "reachable": True},
                {"url": "http://127.0.0.1:11435", "gpu_index": 1, "reachable": True}]
        result = self._estimate_with(size_gb=2.0, gpus=[16.0, 16.0], endpoints=pool)
        self.assertEqual(result["idle_gpus"], [])
        self.assertEqual(result["max_parallel_now"], result["max_parallel_potential"])
        self.assertEqual(result["endpoint_count"], 2)

    def test_gpu_too_small_for_the_model_is_not_offered(self):
        # Una scheda che non regge il modello non e' capacita' inutilizzata:
        # proporre di attivarla porterebbe solo a un caricamento fallito.
        result = self._estimate_with(size_gb=12.0, gpus=[16.0, 8.0])
        self.assertEqual(result["idle_gpus"], [])
        self.assertFalse(result["gpus"][1]["fits"])

    def test_unreachable_endpoint_does_not_count_as_capacity(self):
        pool = [{"url": "http://127.0.0.1:11434", "gpu_index": 0, "reachable": True},
                {"url": "http://127.0.0.1:11435", "gpu_index": 1, "reachable": False}]
        result = self._estimate_with(size_gb=2.0, gpus=[16.0, 16.0], endpoints=pool)
        self.assertEqual(result["endpoint_count"], 1)
        self.assertEqual(len(result["idle_gpus"]), 1)

    # ------------------------------------------------- scala adattiva

    def test_levels_adapt_to_the_hardware_ceiling(self):
        small = self.capacity.adaptive_levels({"max_parallel_potential": 4})
        large = self.capacity.adaptive_levels({"max_parallel_potential": 64})
        self.assertEqual(small, [1, 2, 4])
        self.assertEqual(large[0], 1)
        self.assertLessEqual(large[-1], 32, "la scala non deve superare il tetto assoluto")
        self.assertGreater(len(large), len(small))

    def test_levels_never_empty(self):
        self.assertEqual(self.capacity.adaptive_levels({"max_parallel_potential": 1}), [1])
        self.assertEqual(self.capacity.adaptive_levels({}), [1])

    # ---------------------------------------------------------------- lettura delle misure

    def _measurements(self, pairs):
        """pairs: [(concorrenza, tok/s)] con speedup ed efficienza calcolati."""
        base = pairs[0][1]
        return [{
            "concurrency": c, "aggregate_tokens_per_sec": tps, "failed": 0,
            "succeeded": c, "avg_latency_ms": 100 * c,
            "speedup": round(tps / base, 2), "efficiency": round((tps / base) / c, 2),
            "useful": (tps / base) / c >= self.capacity.EFFICIENCY_THRESHOLD,
        } for c, tps in pairs]

    def test_flat_throughput_is_reported_as_a_configuration_limit(self):
        # La firma della serializzazione: la concorrenza sale, il throughput no.
        measurements = self._measurements([(1, 100.0), (2, 101.0), (4, 99.0)])
        verdict = self.capacity._interpret(measurements, 1, {"max_parallel": 12}, 1, 1)
        self.assertEqual(verdict["bottleneck"], "OLLAMA_NUM_PARALLEL")
        self.assertEqual(verdict["recommended_parallel"], 1)
        self.assertIn("12", verdict["advice"])

    def test_flat_throughput_without_the_env_var_is_a_compute_limit(self):
        measurements = self._measurements([(1, 100.0), (2, 102.0), (4, 101.0)])
        verdict = self.capacity._interpret(measurements, 8, {"max_parallel": 12}, 1, 1)
        self.assertEqual(verdict["bottleneck"], "calcolo")

    def test_throughput_optimum_can_exceed_the_interactive_one(self):
        # Il punto della distinzione: a 8 richieste il lotto finisce prima anche
        # se ogni singola risposta arriva piu' tardi. Un benchmark vuole il
        # primo numero, un agente il secondo.
        measurements = self._measurements([(1, 100.0), (2, 190.0), (4, 260.0), (8, 300.0)])
        verdict = self.capacity._interpret(measurements, 8, {"max_parallel_potential": 12}, 8, 2)
        self.assertEqual(verdict["recommended_parallel"], 8)
        self.assertIn("2", verdict["advice"])

    def test_failures_at_high_concurrency_are_a_memory_limit(self):
        measurements = self._measurements([(1, 100.0), (2, 190.0)])
        measurements.append({"concurrency": 4, "aggregate_tokens_per_sec": 50.0, "failed": 2,
                             "succeeded": 2, "avg_latency_ms": 900, "speedup": 0.5,
                             "efficiency": 0.12, "useful": False})
        verdict = self.capacity._interpret(measurements, 8, {"max_parallel": 12}, 2, 2)
        self.assertEqual(verdict["bottleneck"], "memoria")
        self.assertEqual(verdict["recommended_parallel"], 2)

    def test_idle_gpus_are_surfaced_in_the_advice(self):
        measurements = self._measurements([(1, 100.0), (2, 190.0)])
        estimate = {"max_parallel_potential": 24,
                    "idle_gpus": [{"index": 1, "name": "GPU1", "max_parallel": 12}]}
        verdict = self.capacity._interpret(measurements, 8, estimate, 2, 2)
        self.assertIn("GPU 1", verdict["advice"])

    # ---------------------------------------------------------------- risoluzione

    def test_explicit_concurrency_is_respected(self):
        self.assertEqual(self.capacity.resolve_concurrency("m", 8)[0], 8)
        self.assertEqual(self.capacity.resolve_concurrency("m", "4")[0], 4)

    def test_concurrency_is_clamped_to_a_sane_range(self):
        self.assertEqual(self.capacity.resolve_concurrency("m", 999)[0], 32)
        self.assertEqual(self.capacity.resolve_concurrency("m", -5)[0], 1)

    def test_auto_prefers_a_saved_measurement(self):
        self.capacity._save_profile("m", {"recommended_parallel": 6, "measured_at": "2026-07-30T00:00:00"})
        value, source = self.capacity.resolve_concurrency("m", "auto")
        self.assertEqual(value, 6)
        self.assertIn("misurato", source)

    def test_auto_without_a_measurement_uses_the_measured_ceiling(self):
        from unittest.mock import patch
        # Il tetto non e' un numero di comodo: e' quanto rende questa macchina.
        # Misurato su 24 richieste a qwen2.5:0.5b-instruct, fermarsi a 4 worker
        # invece di 8 costava il 42% del throughput (26.5 contro 37.6 req/s).
        estimate = {"max_parallel_now": 32, "endpoint_count": 1}
        with patch.object(self.capacity, "estimate_capacity", return_value=estimate):
            value, source = self.capacity.resolve_concurrency("mai-misurato", "auto")
        self.assertEqual(value, 8)
        self.assertIn("stima", source)

    def test_a_big_model_is_still_limited_by_its_vram(self):
        from unittest.mock import patch
        # Il tetto alzato non deve travolgere il limite vero: su un modello che
        # occupa la scheda, le slot in piu' non esistono e chiederle rallenta.
        estimate = {"max_parallel_now": 2, "endpoint_count": 1}
        with patch.object(self.capacity, "estimate_capacity", return_value=estimate):
            value, _ = self.capacity.resolve_concurrency("un-9b", "auto")
        self.assertEqual(value, 2)

    def test_auto_ceiling_grows_with_the_endpoint_pool(self):
        from unittest.mock import patch
        # Ogni endpoint ha la sua coda: con due servitori il tetto prudenziale
        # raddoppia, altrimenti il secondo resterebbe inutilizzato.
        estimate = {"max_parallel_now": 32, "endpoint_count": 2}
        with patch.object(self.capacity, "estimate_capacity", return_value=estimate):
            value, _ = self.capacity.resolve_concurrency("mai-misurato", "auto")
        self.assertEqual(value, 16)

    def test_missing_value_means_auto_not_one(self):
        self.capacity._save_profile("m", {"recommended_parallel": 5, "measured_at": "2026-07-30T00:00:00"})
        self.assertEqual(self.capacity.resolve_concurrency("m", None)[0], 5)

    def test_profiles_round_trip(self):
        self.capacity._save_profile("m", {"recommended_parallel": 3})
        self.assertEqual(self.capacity.get_profile("m")["recommended_parallel"], 3)
        self.assertIsNone(self.capacity.get_profile("altro"))


class TestBenchmarkMCPServer(unittest.TestCase):
    def test_tools_are_registered_on_the_hub(self):
        from core.mcp.mcp_hub import mcp_hub
        names = {t["name"] for t in mcp_hub.get_aggregated_tools()}
        for tool in ("list_benchmark_suites", "download_benchmark_suite", "run_benchmark",
                     "get_benchmark_status", "get_benchmark_review_queue", "grade_model_answer",
                     "measure_parallel_capacity", "get_parallel_capacity"):
            self.assertIn(tool, names)

    def test_grade_tool_reports_ambiguity_over_rpc(self):
        from core.mcp.mcp_hub import mcp_hub
        response = mcp_hub.dispatch_rpc({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "grade_model_answer", "arguments": {
                "model_output": "The correct answer is A. The correct choice is H.",
                "correct_choice": "A", "suite": "mmlu", "options": OPTIONS_4,
            }},
        })
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertTrue(payload["success"])
        self.assertEqual(payload["verdict"], VERDICT_AMBIGUOUS)
        self.assertEqual(payload["parsed"]["candidates"], ["A", "H"])


if __name__ == "__main__":
    unittest.main()
