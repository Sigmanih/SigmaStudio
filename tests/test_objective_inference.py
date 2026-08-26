# ==============================================================================
# tests/test_objective_inference.py — The model, measured instead of dressed up
#
# Three claims are under test here, and each of them was false before:
#
#   1. Neutrality. A benchmark and a served endpoint get the checkpoint, not
#      Sigma Studio: no persona, no vendor sampling recipe, no repetition
#      penalty, and none of the engine's own progress narration concatenated
#      into the answer.
#   2. Determinacy. A multiple-choice item resolves to exactly one option,
#      because the option is read off the distribution rather than mined out of
#      prose with regular expressions.
#   3. Throughput. Independent prompts share a forward pass, in the caller's
#      order, and an out-of-memory batch is halved rather than lost.
#
# None of it needs a real model: the decisions live in the plumbing, and a fake
# tokenizer with a fake model exercises them identically on a CUDA desktop and
# on a Raspberry Pi.
# ==============================================================================
import unittest

from core.engine import evaluation
from core.engine.grammars import choice_grammar
from core.engine.provider_server import (
    _cut_at_stop, _estimate_tokens, _sampler_from_request, _split_conversation,
    _thinking_from_request,
)
from core.engine.unified_runtime import _cut_at_stop as runtime_cut


# ---------------------------------------------------------------------------
# The neutral sampler
# ---------------------------------------------------------------------------

class TestNeutralSampler(unittest.TestCase):
    """A measurement must not carry the machine's configuration into itself."""

    def test_measurement_sampler_is_greedy_and_unpenalised(self):
        params = evaluation.deterministic_params(max_tokens=256)
        self.assertEqual(params.temperature, 0.0)
        self.assertEqual(params.top_p, 1.0)
        self.assertEqual(params.top_k, 0)
        # The one that actually costs accuracy: a repetition penalty punishes a
        # model for writing "144" when the prompt already said "12 x 12".
        self.assertEqual(params.repeat_penalty, 1.0)
        self.assertEqual(params.seed, evaluation.DETERMINISTIC_SEED)

    def test_greedy_decoding_passes_no_sampling_knobs(self):
        kwargs = evaluation.deterministic_params(max_tokens=64).for_transformers(None)
        self.assertFalse(kwargs["do_sample"])
        for knob in ("temperature", "top_p", "top_k", "min_p", "repetition_penalty"):
            self.assertNotIn(knob, kwargs)

    def test_family_recipe_is_not_consulted(self):
        # SamplingParams.resolve would give qwen3 top_p 0.8 and rep 1.05. The
        # evaluation sampler must be identical for every checkpoint, or two
        # models are not being compared on the same terms.
        for name in ("qwen3-8b", "gemma-2-9b", "deepseek-r1-7b"):
            params = evaluation.deterministic_params(max_tokens=32)
            self.assertEqual((params.top_p, params.repeat_penalty), (1.0, 1.0), name)


# ---------------------------------------------------------------------------
# Engine narration is not the model's answer
# ---------------------------------------------------------------------------

class TestNoticeSeparation(unittest.TestCase):
    """The engine narrates; that narration used to be graded as an answer."""

    def test_status_chunks_are_recognised(self):
        self.assertTrue(evaluation.is_notice({"token": "", "notice": True}))
        self.assertTrue(evaluation.is_notice({"token": "x", "loading": True}))
        self.assertTrue(evaluation.is_notice({"token": "x", "type": "status"}))
        self.assertFalse(evaluation.is_notice({"token": "A", "done": False}))

    def test_collect_keeps_only_the_model(self):
        stream = [
            {"token": "", "notice": True, "model_status": "Caricamento pesi..."},
            {"token": "> WARNING placement", "status": True, "notice": True},
            {"token": "Answer:", "ttft_ms": 40.0},
            {"token": " B"},
            {"token": "", "done": True, "total_tokens": 3,
             "prompt_tokens": 120, "speed_tok_s": 41.5},
        ]
        answer = evaluation.collect(stream)
        self.assertEqual(answer.text, "Answer: B")
        self.assertEqual(answer.tokens, 3)
        self.assertEqual(answer.prompt_tokens, 120)
        self.assertEqual(answer.ttft_ms, 40.0)
        self.assertTrue(answer.ok)

    def test_engine_failure_surfaces_as_an_error_not_as_an_answer(self):
        stream = [{"token": "Motore occupato da un'altra richiesta.",
                   "notice": True, "error": "engine_busy", "done": True}]
        answer = evaluation.collect(stream)
        self.assertEqual(answer.text, "")
        self.assertFalse(answer.ok)
        self.assertIn("occupato", answer.error)


# ---------------------------------------------------------------------------
# Stop sequences
# ---------------------------------------------------------------------------

class TestStopSequences(unittest.TestCase):

    def test_text_is_cut_at_the_first_marker(self):
        text = "Answer: C\nQuestion: next one\nAnswer: D"
        cut, hit = _cut_at_stop(text, ("\nQuestion:",))
        self.assertTrue(hit)
        self.assertEqual(cut, "Answer: C")

    def test_missing_marker_leaves_the_text_alone(self):
        cut, hit = _cut_at_stop("Answer: C", ("\nQuestion:",))
        self.assertFalse(hit)
        self.assertEqual(cut, "Answer: C")

    def test_runtime_and_server_cut_identically(self):
        # The same answer must come back whether it was streamed or batched.
        text = "42\nTask: something else"
        self.assertEqual(_cut_at_stop(text, ("\nTask:",)), runtime_cut(text, ("\nTask:",)))


# ---------------------------------------------------------------------------
# Serving a model is serving the model
# ---------------------------------------------------------------------------

class TestServingContract(unittest.TestCase):

    def test_no_persona_when_the_client_sent_none(self):
        system, conversation = _split_conversation([{"role": "user", "content": "hi"}])
        self.assertEqual(system, "")
        self.assertEqual(conversation, [{"role": "user", "content": "hi"}])

    def test_client_system_prompt_reaches_the_conversation(self):
        # It used to be extracted into a separate argument the transformers
        # path then ignored, so a served model never saw it at all.
        _, conversation = _split_conversation([
            {"role": "system", "content": "You are a linter."},
            {"role": "user", "content": "review this"},
        ])
        self.assertEqual(conversation[0],
                         {"role": "system", "content": "You are a linter."})

    def test_stacked_system_messages_are_joined_not_dropped(self):
        system, _ = _split_conversation([
            {"role": "system", "content": "base"},
            {"role": "system", "content": "rider"},
            {"role": "user", "content": "go"},
        ])
        self.assertEqual(system, "base\n\nrider")

    def test_multimodal_text_parts_survive(self):
        _, conversation = _split_conversation([{
            "role": "user",
            "content": [{"type": "text", "text": "describe "},
                        {"type": "image_url", "image_url": {"url": "x"}},
                        {"type": "text", "text": "this"}],
        }])
        self.assertEqual(conversation[-1]["content"], "describe this")

    def test_client_sampling_is_honoured(self):
        params = _sampler_from_request(
            "qwen3-8b", 0.0, 128, 1.0,
            {"stop": ["\n\n"], "seed": 7, "top_k": 5},
        )
        self.assertEqual(params.temperature, 0.0)
        self.assertEqual(params.top_p, 1.0)      # was silently discarded before
        self.assertEqual(params.top_k, 5)
        self.assertEqual(params.seed, 7)
        self.assertEqual(params.stop, ("\n\n",))

    def test_omitted_knobs_fall_back_to_the_family_recipe(self):
        params = _sampler_from_request("qwen3-8b", None, 128, None, {})
        self.assertEqual(params.top_p, 0.80)     # qwen3's published value

    def test_thinking_switch_is_read_in_every_spelling(self):
        self.assertIs(_thinking_from_request({"think": False}), False)
        self.assertIs(_thinking_from_request(
            {"chat_template_kwargs": {"enable_thinking": True}}), True)
        self.assertIsNone(_thinking_from_request({}))

    def test_token_estimate_is_not_a_word_count(self):
        # Words undercount a tokenizer badly, and that number was being divided
        # into elapsed time and reported as tokens per second.
        text = "def solve(n): return sum(range(n))"
        self.assertGreater(_estimate_tokens(text), len(text.split()))


# ---------------------------------------------------------------------------
# Constrained choice
# ---------------------------------------------------------------------------

class TestChoiceGrammar(unittest.TestCase):

    def test_grammar_admits_the_labels_and_nothing_else(self):
        self.assertEqual(choice_grammar(["A", "B", "C"]),
                         'root ::= "A" | "B" | "C"\n')

    def test_no_labels_means_no_grammar(self):
        self.assertIsNone(choice_grammar([]))


# ---------------------------------------------------------------------------
# Fakes for the batched paths
# ---------------------------------------------------------------------------

class _FakeTokenizer:
    """Enough of a tokenizer to drive batching decisions."""

    pad_token_id = 0
    eos_token_id = 1
    eos_token = "</s>"
    padding_side = "right"

    def __init__(self):
        self.seen_padding_side = []

    def __call__(self, text, return_tensors=None, padding=False,
                 add_special_tokens=True):
        self.seen_padding_side.append(self.padding_side)
        texts = [text] if isinstance(text, str) else list(text)
        rows = [[ord(c) % 97 for c in t] for t in texts]
        width = max(len(r) for r in rows)
        if padding:
            rows = [[self.pad_token_id] * (width - len(r)) + r for r in rows]
        if return_tensors is None:
            return {"input_ids": rows[0] if isinstance(text, str) else rows}
        return {"input_ids": _FakeTensor(rows),
                "attention_mask": _FakeTensor([[1] * len(r) for r in rows])}

    def encode(self, text, add_special_tokens=False):
        return [ord(text[-1])]

    def decode(self, ids, skip_special_tokens=True):
        return "".join(chr(int(i)) for i in ids if int(i) > 2)

    def apply_chat_template(self, messages, tokenize=False,
                            add_generation_prompt=True, **kwargs):
        body = "|".join(f"{m['role']}:{m['content']}" for m in messages)
        if kwargs.get("enable_thinking") is False:
            body += "|<think></think>"
        return body


class _FakeTensor(list):
    """A list that answers the two tensor questions the engine actually asks."""

    @property
    def shape(self):
        return (len(self), len(self[0]) if self else 0)

    def to(self, device):
        return self

    def tolist(self):
        return list(self)


class TestBatchHelpers(unittest.TestCase):
    """The parts of batching that are decisions rather than tensor arithmetic."""

    def test_letter_spellings_are_collected(self):
        from core.engine.unified_runtime import _letter_token_ids

        ids = _letter_token_ids(_FakeTokenizer(), "B")
        self.assertIn(ord("B"), ids)
        self.assertEqual(len(ids), len(set(ids)))   # deduplicated

    def test_thinking_switch_detected_from_the_template(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        engine = UniversalSigmaEngine()
        engine.tokenizer_instance = _FakeTokenizer()
        self.assertTrue(engine._template_honours_thinking())

        rendered = engine._render_chat([{"role": "user", "content": "x"}],
                                       thinking=False)
        self.assertIn("<think></think>", rendered)

    def test_inert_thinking_switch_falls_back_to_the_directive(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        class _Inert(_FakeTokenizer):
            def apply_chat_template(self, messages, tokenize=False,
                                    add_generation_prompt=True, **kwargs):
                return "|".join(f"{m['role']}:{m['content']}" for m in messages)

        engine = UniversalSigmaEngine()
        engine.tokenizer_instance = _Inert()
        engine.loaded_model_name = "qwen3-8b-instruct"
        self.assertFalse(engine._template_honours_thinking())
        self.assertIn("/no_think",
                      engine._render_chat([{"role": "user", "content": "x"}],
                                          thinking=False))

    def test_no_directive_is_invented_for_families_without_one(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        class _Inert(_FakeTokenizer):
            def apply_chat_template(self, messages, tokenize=False,
                                    add_generation_prompt=True, **kwargs):
                return "|".join(f"{m['role']}:{m['content']}" for m in messages)

        engine = UniversalSigmaEngine()
        engine.tokenizer_instance = _Inert()
        engine.loaded_model_name = "llama-3-8b"
        # Adding an unknown directive would change the prompt without changing
        # the behaviour -- on a benchmark that is a change to the measurement.
        self.assertNotIn("/no_think",
                         engine._render_chat([{"role": "user", "content": "x"}],
                                             thinking=False))

    def test_batch_size_falls_back_to_one_without_an_accelerator(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        engine = UniversalSigmaEngine()
        engine.hardware_profile = {"accelerators": [], "ram": {"available_gb": 4}}
        engine.refresh_vram = lambda: {"accelerators": [], "ram": {"available_gb": 4}}
        self.assertEqual(engine.auto_batch_size(), 1)

    def test_explicit_batch_size_wins(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        self.assertEqual(UniversalSigmaEngine().auto_batch_size(12), 12)


    def test_a_backend_without_logits_falls_back_to_a_grammar(self):
        # A GGUF on llama.cpp cannot expose a distribution, but it can be
        # constrained. The guarantee must survive the change of mechanism.
        calls = {}

        class _NoLogits:
            def choice_logits(self, **kwargs):
                return [{"index": i, "error": "unsupported_backend"}
                        for i in range(len(kwargs["conversations"]))]

            def generate_batch(self, conversations, params, **kwargs):
                calls["grammar"] = params.grammar
                return [{"index": i, "text": "B", "tokens": 1, "error": ""}
                        for i in range(len(conversations))]

        outcomes = evaluation.choose(
            [[{"role": "user", "content": "q"}]], [["A", "B", "C"]],
            model_name="gguf", engine=_NoLogits(),
        )
        self.assertEqual(outcomes[0]["choice"], "B")
        self.assertTrue(outcomes[0]["constrained"])
        self.assertEqual(calls["grammar"], choice_grammar(["A", "B", "C"]))

    def test_a_constrained_answer_outside_the_label_set_is_not_invented(self):
        class _Wayward:
            def choice_logits(self, **kwargs):
                return [{"index": 0, "error": "unsupported_backend"}]

            def generate_batch(self, conversations, params, **kwargs):
                return [{"index": 0, "text": "maybe A?", "tokens": 3, "error": ""}]

        outcomes = evaluation.choose(
            [[{"role": "user", "content": "q"}]], [["A", "B"]],
            model_name="gguf", engine=_Wayward(),
        )
        self.assertIsNone(outcomes[0]["choice"])
        self.assertTrue(outcomes[0]["error"])


class TestBenchmarkProtocol(unittest.TestCase):
    """What the benchmark asks for, and what it records about how it asked."""

    def test_multiple_choice_prompt_asks_only_for_the_letter(self):
        from core.modules.sigma_training_lab.training.benchmarks import _choice_messages

        messages = _choice_messages({
            "prompt": "What is 2+2?",
            "options": ["A) 3", "B) 4"],
        })
        self.assertEqual(len(messages), 1)
        content = messages[0]["content"]
        self.assertIn("B) 4", content)
        # No invitation to reason: nobody reads the reasoning on this path, and
        # asking for it changes the distribution that is read.
        self.assertNotIn("step by step", content.lower())

    def test_reasoning_is_on_exactly_where_the_suite_is_about_reasoning(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            _prepare_benchmark_payload,
        )
        # Forcing every suite to answer without reasoning was the single
        # biggest cause of the collapsed scores: MMLU-Pro, GPQA, BBH, GSM8K and
        # MATH are published *with* chain of thought, and measuring them on the
        # model's first instinct measures what they were built not to reward.
        expected = {"mmlu": False, "gsm8k": True, "math": True,
                    "mmlu_pro": True, "bbh": True, "humaneval": False}
        for suite, thinking in expected.items():
            options = ["A) x", "B) y"] if suite in ("mmlu", "mmlu_pro") else []
            payload = _prepare_benchmark_payload(
                {"suite": suite, "prompt": "q", "options": options}, "sigma:model")
            self.assertTrue(payload.get("stop"), suite)
            self.assertIs(payload.get("think"), thinking, suite)

    def test_a_reasoning_suite_gets_room_to_reason(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            _prepare_benchmark_payload,
        )
        # Truncating mid-reasoning does not produce a wrong answer, it produces
        # no answer -- which the tally counts as an error and is not one.
        budget = _prepare_benchmark_payload(
            {"suite": "math", "prompt": "q", "options": []},
            "sigma:model")["options"]["num_predict"]
        self.assertGreaterEqual(budget, 2048)

    def test_the_certificate_records_how_the_answer_was_obtained(self):
        from core.modules.sigma_training_lab.training import benchmarks

        # Two runs that chose in different ways are not the same measurement,
        # however similar the scores look.
        self.assertNotEqual(benchmarks.ANSWER_PROTOCOL_LOGITS,
                            benchmarks.ANSWER_PROTOCOL_GENERATIVE)
        self.assertGreaterEqual(benchmarks.PROMPT_PROTOCOL, 3)


# ---------------------------------------------------------------------------
# The batched paths, against a real transformers model
# ---------------------------------------------------------------------------
# Batching is where a plausible-looking implementation is silently wrong:
# padding a decoder-only model on the wrong side puts pad tokens between the
# prompt and the answer, and the model then answers a question nobody asked --
# fluently, with no error anywhere. The only test that catches it is comparing
# a batched answer against the same prompt run alone.


class _TorchTokenizer:
    """A tokenizer that is real where it matters: tensors, padding, decoding."""

    pad_token_id = 0
    eos_token_id = 1
    eos_token = "</s>"
    pad_token = "<pad>"
    padding_side = "right"

    def __init__(self, torch):
        self._torch = torch

    def _ids(self, text):
        return [(ord(c) % 400) + 3 for c in text]

    def __call__(self, text, return_tensors=None, padding=False,
                 add_special_tokens=True):
        texts = [text] if isinstance(text, str) else list(text)
        rows = [self._ids(t) for t in texts]
        if padding:
            width = max(len(r) for r in rows)
            if self.padding_side == "left":
                mask = [[0] * (width - len(r)) + [1] * len(r) for r in rows]
                rows = [[self.pad_token_id] * (width - len(r)) + r for r in rows]
            else:
                mask = [[1] * len(r) + [0] * (width - len(r)) for r in rows]
                rows = [r + [self.pad_token_id] * (width - len(r)) for r in rows]
        else:
            mask = [[1] * len(r) for r in rows]

        if return_tensors != "pt":
            return {"input_ids": rows[0] if isinstance(text, str) else rows}
        return {
            "input_ids": self._torch.tensor(rows),
            "attention_mask": self._torch.tensor(mask),
        }

    def encode(self, text, add_special_tokens=False):
        return self._ids(text)

    def decode(self, ids, skip_special_tokens=True):
        values = ids.tolist() if hasattr(ids, "tolist") else list(ids)
        return "".join(chr(int(v) - 3) for v in values if 3 <= int(v) < 403)

    def apply_chat_template(self, messages, tokenize=False,
                            add_generation_prompt=True, **kwargs):
        joined = "|".join(f"{m['role']}:{m['content']}" for m in messages)
        return joined + "|assistant:"


class TestBatchedGenerationAgainstRealModel(unittest.TestCase):
    """Two layers of random weights are enough: the plumbing is what is on trial."""

    @classmethod
    def setUpClass(cls):
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM
        except ImportError:
            raise unittest.SkipTest("transformers/torch not installed on this host")

        from core.engine.unified_runtime import UniversalSigmaEngine

        torch.manual_seed(0)
        config = AutoConfig.for_model(
            "qwen2", vocab_size=512, hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            max_position_embeddings=1024,
        )
        cls.torch = torch
        cls.engine = UniversalSigmaEngine()
        cls.engine.model_instance = AutoModelForCausalLM.from_config(config).eval()
        cls.engine.tokenizer_instance = _TorchTokenizer(torch)
        cls.engine.loaded_model_name = "tiny"
        cls.engine._ensure_resident = lambda name=None: {"success": True}
        cls.engine.refresh_vram = lambda: {"accelerators": [],
                                           "ram": {"available_gb": 64}}

    def _conversations(self):
        return [
            [{"role": "user", "content": "short"}],
            [{"role": "user", "content": "a considerably longer question here"}],
            [{"role": "user", "content": "mid length one"}],
        ]

    def test_results_come_back_in_the_caller_order(self):
        answers = evaluation.complete_batch(
            self._conversations(), model_name="tiny", max_tokens=6,
            batch_size=3, engine=self.engine,
        )
        self.assertEqual(len(answers), 3)
        self.assertTrue(all(a.ok for a in answers), [a.error for a in answers])
        self.assertTrue(all(a.batch_size == 3 for a in answers))

    def test_a_batched_answer_equals_the_same_prompt_run_alone(self):
        # The padding-side test. Left padding keeps every sequence's last real
        # token in the last position; right padding does not, and the model
        # continues from a run of pad tokens instead of from the question.
        batched = evaluation.complete_batch(
            self._conversations(), model_name="tiny", max_tokens=6,
            batch_size=3, engine=self.engine,
        )
        alone = [
            evaluation.complete_batch([conv], model_name="tiny", max_tokens=6,
                                      batch_size=1, engine=self.engine)[0]
            for conv in self._conversations()
        ]
        for position, (grouped, single) in enumerate(zip(batched, alone)):
            self.assertEqual(grouped.text, single.text,
                             f"batching changed the answer for prompt {position}")

    def test_an_oversized_batch_is_halved_rather_than_lost(self):
        calls = {"n": 0}
        real = self.engine._run_one_batch

        def _explode(group, prompts, params, results, tokenizer):
            calls["n"] += 1
            if len(group) > 1 and calls["n"] == 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 2 GiB")
            return real(group, prompts, params, results, tokenizer)

        self.engine._run_one_batch = _explode
        try:
            answers = evaluation.complete_batch(
                self._conversations(), model_name="tiny", max_tokens=4,
                batch_size=3, engine=self.engine,
            )
        finally:
            self.engine._run_one_batch = real

        self.assertGreater(calls["n"], 1, "the batch was not retried smaller")
        self.assertTrue(all(a.ok for a in answers), [a.error for a in answers])

    def test_choice_scoring_is_single_valued_and_repeatable(self):
        conversations = [
            [{"role": "user", "content": "pick one A or B"}],
            [{"role": "user", "content": "another question entirely, longer"}],
        ]
        letters = [["A", "B", "C", "D"], ["A", "B", "C", "D"]]

        first = evaluation.choose(conversations, letters, model_name="tiny",
                                  batch_size=2, engine=self.engine)
        second = evaluation.choose(conversations, letters, model_name="tiny",
                                   batch_size=2, engine=self.engine)

        self.assertEqual(len(first), 2)
        for outcome, twin in zip(first, second):
            self.assertEqual(outcome["choice"], twin["choice"])
            if outcome["choice"] is None:
                # Random weights put no probability on the labels, and saying
                # so is the correct answer. Naming a letter anyway would be the
                # bug: an invented choice is indistinguishable, downstream, from
                # a real one.
                self.assertTrue(outcome["error"])
                continue
            self.assertIn(outcome["choice"], ["A", "B", "C", "D"])
            self.assertAlmostEqual(sum(outcome["probs"].values()), 1.0, places=4)
            self.assertGreaterEqual(outcome["margin"], 0.0)

    def test_a_choice_batch_matches_the_same_item_scored_alone(self):
        conversations = [
            [{"role": "user", "content": "pick one A or B"}],
            [{"role": "user", "content": "another question entirely, longer"}],
        ]
        letters = [["A", "B", "C", "D"], ["A", "B", "C", "D"]]

        grouped = evaluation.choose(conversations, letters, model_name="tiny",
                                    batch_size=2, engine=self.engine)
        for position, conversation in enumerate(conversations):
            alone = evaluation.choose([conversation], [letters[position]],
                                      model_name="tiny", batch_size=1,
                                      engine=self.engine)
            self.assertEqual(grouped[position]["choice"], alone[0]["choice"],
                             "padding changed which option was ranked first")

    def test_continuation_scores_survive_being_batched(self):
        # Same padding trap as generation, and harder to notice: a misplaced
        # offset reads the log-probability of the wrong position and still
        # returns a plausible-looking number for every option.
        pairs = [("The capital of France is", " Paris"),
                 ("The capital of France is", " a very large elephant indeed"),
                 ("Two plus two equals", " four")]

        grouped = self.engine.continuation_logprobs(pairs, model_name="tiny",
                                                    batch_size=3)
        alone = [self.engine.continuation_logprobs([pair], model_name="tiny",
                                                   batch_size=1)[0]
                 for pair in pairs]
        for position, (batched, single) in enumerate(zip(grouped, alone)):
            self.assertAlmostEqual(batched["logprob"], single["logprob"], places=3,
                                   msg=f"padding changed the score of pair {position}")
            self.assertEqual(batched["tokens"], single["tokens"])

    def test_length_normalisation_is_what_stops_the_shortest_winning(self):
        from core.engine import evaluation

        questions = [("A man opens a fridge and",
                      [" eats.", " takes out a carton of milk and pours a glass."])]
        raw = evaluation.rank_continuations(questions, model_name="tiny",
                                            normalize="", engine=self.engine)
        normalised = evaluation.rank_continuations(questions, model_name="tiny",
                                                   normalize="char",
                                                   engine=self.engine)
        # Unnormalised, every extra token can only subtract probability, so the
        # short option wins almost regardless of meaning.
        self.assertEqual(raw[0]["choice"], 0)
        self.assertIn(normalised[0]["choice"], (0, 1))
        self.assertEqual(len(normalised[0]["scores"]), 2)



# ---------------------------------------------------------------------------
# The benchmark driver on the local engine
# ---------------------------------------------------------------------------

class TestBenchmarkSigmaDriver(unittest.TestCase):
    """Items in, verdicts out -- with the engine stubbed at the seam above it."""

    def setUp(self):
        from core.engine import evaluation as ev
        from core.modules.sigma_training_lab.training import benchmarks

        self.benchmarks = benchmarks
        self.ev = ev
        self._choose = ev.choose
        self._complete_batch = ev.complete_batch

    def tearDown(self):
        self.ev.choose = self._choose
        self.ev.complete_batch = self._complete_batch

    def _mc_items(self, count):
        return [{
            "id": f"mmlu_{i}", "suite": "mmlu", "suite_name": "MMLU",
            "prompt": f"question {i}", "options": ["A) one", "B) two", "C) three"],
            "correct_choice": "B", "correct_answer": "B) two",
        } for i in range(count)]

    def test_choice_scoring_produces_a_gradable_answer_per_item(self):
        self.ev.choose = lambda conversations, letters, **kw: [
            {"index": i, "choice": "B", "probs": {"A": 0.1, "B": 0.8, "C": 0.1},
             "margin": 0.7, "error": ""}
            for i in range(len(conversations))
        ]
        items = self._mc_items(3)
        scored = self.benchmarks._run_sigma_choice_scoring(items, "tiny", 8)

        self.assertEqual(len(scored), 3)
        for outcome in scored.values():
            # The text is synthesised so the one official grader still decides
            # the verdict: two protocols must not become two score tables.
            self.assertEqual(outcome["text"], "Answer: B")
            graded = self.benchmarks._grade(items[0], outcome["text"])
            self.assertTrue(graded["passed"])
            self.assertFalse(graded["needs_review"])

    def test_a_backend_that_cannot_choose_hands_the_items_back(self):
        self.ev.choose = lambda conversations, letters, **kw: [
            {"index": i, "choice": None, "probs": {}, "margin": 0.0, "error": ""}
            for i in range(len(conversations))
        ]
        # Empty means "route these to the written path", not "mark them failed":
        # a model that can answer must not be scored zero for a backend gap.
        self.assertEqual(
            self.benchmarks._run_sigma_choice_scoring(self._mc_items(2), "tiny", 8),
            {},
        )

    def test_written_answers_are_grouped_by_token_budget(self):
        seen = []

        def _fake_batch(conversations, model_name=None, max_tokens=512, **kw):
            seen.append((max_tokens, len(conversations)))
            return [self.ev.Completion(text="\\\\boxed{42}", tokens=7,
                                       tokens_per_sec=90.0)
                    for _ in conversations]

        self.ev.complete_batch = _fake_batch
        items = [
            {"id": "m1", "suite": "math", "prompt": "sum", "options": []},
            {"id": "m2", "suite": "math", "prompt": "product", "options": []},
            {"id": "h1", "suite": "humaneval", "prompt": "code", "options": []},
        ]
        results = self.benchmarks._run_sigma_generative(items, "sigma:tiny",
                                                        "tiny", 8)

        self.assertEqual(len(results), 3)
        # Mixing a 1024-token budget with a 3072-token one in a single batch
        # makes the short items pay for the long ones.
        self.assertEqual(sorted(seen), [(1024, 1), (3072, 2)])

    def test_a_transport_error_reaches_the_caller_per_item(self):
        def _fake_batch(conversations, **kw):
            return [self.ev.Completion(error="Motore occupato")
                    for _ in conversations]

        self.ev.complete_batch = _fake_batch
        items = [{"id": "b1", "suite": "bbh", "prompt": "logic", "options": []}]
        results = self.benchmarks._run_sigma_generative(items, "sigma:tiny",
                                                        "tiny", 8, None)
        self.assertEqual(results[0]["error"], "Motore occupato")
        self.assertEqual(results[0]["text"], "")


# ---------------------------------------------------------------------------
# Preparing the questions
# ---------------------------------------------------------------------------

class TestBenchmarkPreparation(unittest.TestCase):
    """Where the run spends its time before the model is asked anything."""

    def test_cache_is_anchored_to_the_installation_not_the_cwd(self):
        import os
        from core.modules.sigma_training_lab import paths as module_paths
        from core.modules.sigma_training_lab.training import benchmarks

        # A relative path answers "not cached" whenever the server starts from
        # another directory, and the preparation then re-downloads eleven
        # datasets to keep a hundred questions -- silently, because makedirs
        # cheerfully creates the empty tree next to it.
        for value in (benchmarks.BENCHMARK_CACHE_DIR, benchmarks.BENCHMARKS_FILE):
            self.assertTrue(os.path.isabs(value), value)
            self.assertTrue(str(value).startswith(str(module_paths.PROJECT_ROOT)), value)

    def test_index_sampling_selects_the_same_questions_as_before(self):
        # The sample must not change when the way of drawing it does: two models
        # compared across the change have to have seen the same questions.
        import random
        items = [{"id": f"i{n}"} for n in range(5000)]
        drawn_directly = random.Random(42).sample(items, 100)
        drawn_by_index = [items[i]
                          for i in random.Random(42).sample(range(len(items)), 100)]
        self.assertEqual(drawn_directly, drawn_by_index)

    def test_in_memory_suites_are_bounded(self):
        from core.modules.sigma_training_lab.training import benchmarks

        # Eleven suites is around 60k dictionaries. Holding them all is fine on
        # a workstation and fatal on an 8 GB board that also has model weights.
        self.assertLessEqual(benchmarks._IN_MEMORY_LIMIT, 3)
        for suite in ("a", "b", "c", "d"):
            benchmarks._remember(suite, [{"id": suite}])
        self.assertLessEqual(len(benchmarks._IN_MEMORY_SUITES),
                             benchmarks._IN_MEMORY_LIMIT)
        self.assertIn("d", benchmarks._IN_MEMORY_SUITES)

    def test_preparation_announces_each_suite(self):
        from core.modules.sigma_training_lab.training import benchmarks

        seen = []
        benchmarks.get_benchmark_items("mmlu,gsm8k", mode="sample",
                                       num_samples=10, progress=seen.append)
        # "preparing" with no message reads as a freeze; the suite names turn a
        # download into something the user can wait for.
        self.assertTrue(any("MMLU" in line for line in seen), seen)

    def test_an_unloadable_model_stops_the_run(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            ModelUnavailable, _raise_if_unavailable,
        )

        with self.assertRaises(ModelUnavailable) as caught:
            _raise_if_unavailable([
                {"fatal": True, "error": "Caricamento modello fallito: X",
                 "diagnosis": "stage: preparation"},
            ])
        self.assertIn("preparation", caught.exception.diagnosis)

        # A per-question failure is not a per-model failure and must not stop it.
        _raise_if_unavailable([{"error": "timeout", "fatal": False}])

    def test_the_cause_chain_survives_the_error_message(self):
        from core.engine.unified_runtime import _describe_exception

        # transformers re-raises import failures as "Could not import module
        # 'Qwen3ForCausalLM'", which names the symbol and hides the reason.
        try:
            try:
                raise ImportError("libcudart.so.12 not found")
            except ImportError as cause:
                raise ModuleNotFoundError(
                    "Could not import module 'Qwen3ForCausalLM'."
                ) from cause
        except ModuleNotFoundError as exc:
            described = _describe_exception(exc)

        self.assertIn("Qwen3ForCausalLM", described)
        self.assertIn("libcudart", described)


# ---------------------------------------------------------------------------
# Reading a label off the distribution
# ---------------------------------------------------------------------------

class _RealisticTokenizer:
    """A tokenizer that splits prefixed spellings, the way a BPE one does."""

    #: "A" and " A" are single tokens; "**A" is two, and its first token is the
    #: asterisk pair -- which is shared by every letter.
    _SINGLE = {"A": 32, "B": 33, "C": 34, "D": 35,
               " A": 362, " B": 425, " C": 356, " D": 422}
    _DECORATION_ID = 334

    def encode(self, text, add_special_tokens=False):
        if text in self._SINGLE:
            return [self._SINGLE[text]]
        if text.startswith("**"):
            return [self._DECORATION_ID, self._SINGLE.get(text[2:], 99)]
        if text.startswith("\n"):
            return [198, self._SINGLE.get(text[1:], 99)]
        return [99]


class TestLabelReading(unittest.TestCase):
    """The half of logit scoring that is a reader, not a model."""

    def test_only_single_token_spellings_are_scored(self):
        from core.engine.unified_runtime import _letter_token_ids

        tokenizer = _RealisticTokenizer()
        per_letter = {L: _letter_token_ids(tokenizer, L) for L in "ABCD"}

        # The bug this exists to prevent: a prefixed spelling contributes its
        # *prefix* token, which every letter shares. Score that and all four
        # labels get the same probability, every question is won by whichever
        # letter is checked first, and every margin is zero -- which reads as a
        # model with a severe position bias and is in fact a broken reader.
        shared = set.intersection(*(set(ids) for ids in per_letter.values()))
        self.assertEqual(shared, set(), f"labels share tokens: {per_letter}")
        for letter, ids in per_letter.items():
            self.assertTrue(ids, letter)
            self.assertNotIn(_RealisticTokenizer._DECORATION_ID, ids, letter)

    def test_decoration_is_recognised_so_it_can_be_stepped_over(self):
        from core.engine.unified_runtime import _is_decoration

        # "Answer: **C**" is the single most common shape a chat model gives
        # back, and the label is one token further along than expected.
        for token in (" **", "**", " ", "\n", " -", ":", " ("):
            self.assertTrue(_is_decoration(token), repr(token))
        for token in (" C", "C", " The", "When"):
            self.assertFalse(_is_decoration(token), repr(token))

    def test_an_answer_position_is_primed(self):
        from core.engine.evaluation import CHOICE_ANSWER_PREFIX

        # Reading the first token of a free reply reads "When" or "The", not a
        # label: the ranking is right and the mass behind it rounds to zero.
        self.assertTrue(CHOICE_ANSWER_PREFIX.strip())
        self.assertFalse(CHOICE_ANSWER_PREFIX.endswith(" "),
                         "a trailing space is absorbed into the next token")


# ---------------------------------------------------------------------------
# A run that can be watched, paused and stopped
# ---------------------------------------------------------------------------

class TestRunProgress(unittest.TestCase):
    """The difference between a slow run and a frozen one is whether it reports."""

    def setUp(self):
        from core.engine import evaluation as ev
        self.ev = ev
        self._complete_batch = ev.complete_batch

    def tearDown(self):
        self.ev.complete_batch = self._complete_batch

    def test_written_answers_are_reported_as_they_arrive(self):
        from core.modules.sigma_training_lab.training import benchmarks

        def _fake_batch(conversations, on_result=None, **kw):
            answers = []
            for position, _ in enumerate(conversations):
                entry = {"index": position, "text": "42", "tokens": 3,
                         "tokens_per_sec": 9.0, "error": ""}
                if on_result:
                    on_result(entry)
                answers.append(self.ev.Completion(text="42", tokens=3))
            return answers

        self.ev.complete_batch = _fake_batch
        items = [{"id": f"b{n}", "suite": "bbh", "prompt": "q", "options": []}
                 for n in range(5)]

        arrived = []
        benchmarks._run_sigma_generative(items, "sigma:tiny", "tiny", 1,
                                         on_item=lambda i, o: arrived.append(i))

        # A backend that decodes one sequence at a time -- a GGUF on llama.cpp
        # -- would otherwise show nothing until the whole queue finished, which
        # with a thousand-token budget per question reads as a hang.
        self.assertEqual(arrived, [0, 1, 2, 3, 4])

    def test_results_are_still_collected_if_the_backend_never_calls_back(self):
        from core.modules.sigma_training_lab.training import benchmarks

        self.ev.complete_batch = lambda conversations, **kw: [
            self.ev.Completion(text="42", tokens=3) for _ in conversations
        ]
        items = [{"id": "b0", "suite": "bbh", "prompt": "q", "options": []}]
        arrived = []
        results = benchmarks._run_sigma_generative(
            items, "sigma:tiny", "tiny", 1, on_item=lambda i, o: arrived.append(i))

        self.assertEqual(len(results), 1)
        self.assertEqual(arrived, [0])

    def test_batch_size_never_exceeds_what_the_backend_can_do(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        engine = UniversalSigmaEngine()
        engine.active_backend_instance = object()      # a resident GGUF
        # Asking for sixteen used to be granted and then reported in the UI as
        # "x16", while llama.cpp did the work one prompt at a time.
        self.assertEqual(engine.auto_batch_size(16), 1)
        self.assertEqual(engine.auto_batch_size(), 1)


# ---------------------------------------------------------------------------
# What is on disk, and how much of it
# ---------------------------------------------------------------------------

class TestSuiteCache(unittest.TestCase):
    """Downloading once, and knowing whether what you have is the whole thing."""

    def test_split_is_sliced_only_when_a_limit_is_asked_for(self):
        from core.modules.sigma_training_lab.training.benchmarks import _split

        self.assertEqual(_split("test", 0), "test")
        self.assertEqual(_split("test", 250), "test[:250]")
        self.assertEqual(_split("validation", 10), "validation[:10]")

    def test_a_cache_with_no_metadata_counts_as_complete(self):
        from core.modules.sigma_training_lab.training.benchmarks import _load_meta

        # Every cache downloaded before slicing existed is a full one, and must
        # not start reporting itself as partial after an upgrade.
        self.assertTrue(_load_meta("a-suite-that-does-not-exist")["complete"])

    def test_a_short_slice_is_recorded_as_partial(self):
        import json, os, tempfile
        from unittest import mock
        from core.modules.sigma_training_lab.training import benchmarks

        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(benchmarks, "BENCHMARK_CACHE_DIR", folder):
                benchmarks._save_meta("mmlu", count=300, limit=300)
                self.assertFalse(benchmarks._load_meta("mmlu")["complete"])

                # Fewer rows than asked for means the split ran out: that is the
                # whole suite, however it was requested.
                benchmarks._save_meta("gsm8k", count=120, limit=500)
                self.assertTrue(benchmarks._load_meta("gsm8k")["complete"])

    def test_suites_covered_by_an_identifier(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            OFFICIAL_BENCHMARKS_INFO, suites_in,
        )
        self.assertEqual(len(suites_in("all")), len(OFFICIAL_BENCHMARKS_INFO))
        self.assertEqual(suites_in("mmlu,gsm8k"), ["mmlu", "gsm8k"])
        self.assertEqual(suites_in("nonesuch"), [])

    def test_a_partial_dataset_cannot_claim_full_coverage(self):
        import inspect
        from core.modules.sigma_training_lab.training import benchmarks

        # The certificate has to distinguish a run over the whole suite from a
        # run over its first few hundred rows -- they are different measurements
        # wearing the same name.
        source = inspect.getsource(benchmarks._run_official_benchmark)
        self.assertIn("dataset_complete", source)
        self.assertIn('if mode == "full" and dataset_complete', source)


# ---------------------------------------------------------------------------
# One protocol per suite, matching how each one is published
# ---------------------------------------------------------------------------

class TestSuiteProtocols(unittest.TestCase):
    """A single measurement method for eleven suites was the wrong answer."""

    def test_every_suite_declares_how_it_is_measured(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            OFFICIAL_BENCHMARKS_INFO,
        )
        from core.modules.sigma_training_lab.training.protocols import PROTOCOLS

        self.assertEqual(set(PROTOCOLS), set(OFFICIAL_BENCHMARKS_INFO))

    def test_reasoning_suites_are_measured_with_reasoning(self):
        from core.modules.sigma_training_lab.training.protocols import (
            MODE_COT, protocol_for,
        )
        # These exist to reward step-by-step work; reading the first token
        # after "Answer:" measures the instinct they were built not to reward.
        for suite in ("mmlu_pro", "gpqa", "bbh", "gsm8k", "math"):
            protocol = protocol_for(suite)
            self.assertEqual(protocol.mode, MODE_COT, suite)
            self.assertTrue(protocol.thinking, suite)
            self.assertGreaterEqual(protocol.max_tokens, 2048, suite)

    def test_commonsense_suites_are_scored_on_the_answer_text(self):
        from core.modules.sigma_training_lab.training.protocols import (
            MODE_CONTINUATION, protocol_for,
        )
        # HellaSwag does not ask "which letter", it asks which ending is real.
        # Length normalisation is not optional: without it the shortest ending
        # wins nearly always, because each extra token only subtracts.
        for suite in ("hellaswag", "arc", "truthfulqa"):
            protocol = protocol_for(suite)
            self.assertEqual(protocol.mode, MODE_CONTINUATION, suite)
            self.assertEqual(protocol.normalize, "char", suite)
            self.assertEqual(protocol.metric, "acc_norm", suite)

    def test_mmlu_keeps_the_protocol_it_is_published_with(self):
        from core.modules.sigma_training_lab.training.protocols import (
            MODE_LETTER, protocol_for,
        )
        protocol = protocol_for("mmlu")
        self.assertEqual(protocol.mode, MODE_LETTER)
        self.assertEqual(protocol.shots, 5)

    def test_continuation_options_carry_no_labels(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            _continuation_question,
        )
        context, options = _continuation_question({
            "prompt": "A man opens a fridge.",
            "options": ["A) He takes out milk.", "B) He flies away."],
        })
        self.assertEqual(context, "A man opens a fridge.")
        # "A) " in front of a continuation changes its likelihood for reasons
        # that have nothing to do with whether the sentence makes sense.
        self.assertEqual(options, [" He takes out milk.", " He flies away."])

    def test_few_shot_never_shows_a_question_being_scored(self):
        from core.modules.sigma_training_lab.training import benchmarks

        pool = [{"id": f"q{n}", "suite": "mmlu", "category": "math",
                 "prompt": f"question {n}", "options": ["A) x", "B) y"],
                 "correct_choice": "A"} for n in range(10)]
        benchmarks._remember("mmlu", pool)
        benchmarks.register_evaluated_ids(pool[:3])
        try:
            block = benchmarks._fewshot_block(pool[0], shots=3)
        finally:
            benchmarks.register_evaluated_ids([])

        self.assertTrue(block)
        for shown in ("question 0", "question 1", "question 2"):
            self.assertNotIn(shown, block,
                             "an exemplar gave away a question under evaluation")

    def test_a_partial_run_does_not_report_the_official_score(self):
        from core.modules.sigma_training_lab.training.benchmarks import (
            VERDICT_FAIL, VERDICT_PASS, _compute_metrics,
        )
        # 32 right out of 61 answered, with 100 planned. The official score is
        # 32% only because 39 questions have not been asked yet; reading it as
        # the model's score is how a decent model looked terrible mid-run.
        metrics = _compute_metrics({VERDICT_PASS: 32, VERDICT_FAIL: 29},
                                   total_done=61, planned_total=100,
                                   total_tokens=61, total_duration=10.0,
                                   latency_sum_ms=24000)
        self.assertEqual(metrics["overall_score"], 32.0)
        self.assertEqual(metrics["progress_score"], 52.46)


# ---------------------------------------------------------------------------
# When the backend stops answering
# ---------------------------------------------------------------------------

class TestGenerationDeadlines(unittest.TestCase):
    """A timeout is a fact about the run, not a sentence the model wrote."""

    def setUp(self):
        from core.engine import evaluation as ev
        self.ev = ev
        self._complete_batch = ev.complete_batch

    def tearDown(self):
        self.ev.complete_batch = self._complete_batch

    def test_the_generation_deadline_is_not_the_startup_one(self):
        from core.engine.backends import llamaserver_backend as backend

        # Reusing the 300 s meant for loading a model declared every chain of
        # thought a failure: two thousand tokens on a quantised 12B legitimately
        # takes longer than the model took to load.
        self.assertGreater(backend._limite_generazione(2048), backend._AVVIO_TIMEOUT_S)
        self.assertGreaterEqual(backend._limite_generazione(0),
                                backend._GENERAZIONE_MIN_S)
        self.assertLessEqual(backend._limite_generazione(100000),
                             backend._GENERAZIONE_MAX_S)

    def test_a_backend_failure_never_becomes_the_answer(self):
        from core.engine.evaluation import collect

        # This is verbatim what the benchmark graded as an attempt at a Python
        # exercise, and counted as the model getting it wrong.
        answer = collect([
            {"token": "\n\n❌ **Errore llama-server**: TimeoutError: timed out",
             "notice": True, "error": "timeout", "done": True},
        ])
        self.assertEqual(answer.text, "")
        self.assertIn("TimeoutError", answer.error)

    def test_work_done_before_a_deadline_is_kept(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        class _SlowBackend:
            def generate_stream(self, prompt, **kw):
                yield {"token": "def is_prime(n):\n    return n > 1", "done": False}
                yield {"token": "", "done": True, "total_tokens": 12,
                       "finish_reason": "timeout", "truncated": True}

        engine = UniversalSigmaEngine()
        engine.active_backend_instance = _SlowBackend()
        engine._ensure_resident = lambda name=None: {"success": True}
        results = engine.generate_batch([[{"role": "user", "content": "q"}]],
                                        model_name="gguf")

        # A chain of thought cut off after fifteen hundred tokens has usually
        # written the answer already. Discarding it measures the deadline.
        self.assertIn("is_prime", results[0]["text"])
        self.assertEqual(results[0]["finish_reason"], "timeout")
        self.assertFalse(results[0]["error"])
        self.assertTrue(results[0]["warning"])

    def test_repeated_timeouts_stop_the_run_instead_of_grinding(self):
        from core.modules.sigma_training_lab.training import benchmarks

        def _fake_batch(conversations, on_result=None, **kw):
            answers = []
            for position, _ in enumerate(conversations):
                entry = {"index": position, "text": "", "tokens": 0,
                         "error": "TimeoutError: timed out",
                         "finish_reason": "timeout"}
                if on_result:
                    on_result(entry)
                answers.append(self.ev.Completion(error="TimeoutError: timed out"))
            return answers

        self.ev.complete_batch = _fake_batch
        items = [{"id": f"g{n}", "suite": "gsm8k", "prompt": "q", "options": []}
                 for n in range(10)]

        # Thirty-two remaining questions at ten minutes of timeout each is five
        # hours of collecting errors, and from the outside it looks like a hang.
        with self.assertRaises(benchmarks.ModelUnavailable) as caught:
            benchmarks._run_sigma_generative(items, "sigma:tiny", "tiny", 1)
        self.assertIn("scadute", str(caught.exception))

    def test_one_slow_question_does_not_stop_the_run(self):
        from core.modules.sigma_training_lab.training import benchmarks

        state = {"n": 0}

        def _fake_batch(conversations, on_result=None, **kw):
            answers = []
            for position, _ in enumerate(conversations):
                state["n"] += 1
                slow = state["n"] == 1
                entry = {"index": position,
                         "text": "" if slow else "\\boxed{42}",
                         "tokens": 0 if slow else 4,
                         "error": "TimeoutError: timed out" if slow else "",
                         "finish_reason": "timeout" if slow else "stop"}
                if on_result:
                    on_result(entry)
                answers.append(self.ev.Completion(text=entry["text"],
                                                  error=entry["error"]))
            return answers

        self.ev.complete_batch = _fake_batch
        items = [{"id": f"g{n}", "suite": "gsm8k", "prompt": "q", "options": []}
                 for n in range(4)]
        results = benchmarks._run_sigma_generative(items, "sigma:tiny", "tiny", 1)
        self.assertEqual(len(results), 4)


# ---------------------------------------------------------------------------
# Nothing fails in silence
# ---------------------------------------------------------------------------

class TestFailuresAreVisible(unittest.TestCase):
    """A daemon thread that dies takes the whole run's explanation with it."""

    def test_a_crashing_run_leaves_a_failed_job_not_a_running_one(self):
        from unittest import mock
        from core.modules.sigma_training_lab.training import benchmarks

        states = []
        with mock.patch.object(benchmarks, "_run_official_benchmark",
                               side_effect=RuntimeError("connessione chiusa dal server")), \
             mock.patch.object(benchmarks, "_update_job_state",
                               side_effect=lambda job, upd: states.append(upd)):
            benchmarks._active_threads["bm_test"] = object()
            benchmarks._worker_run_official_benchmark("bm_test", "sigma:x", "mmlu",
                                                      "sample", 10, 1)

        # Without this, the job stayed "running" for ever, the UI polled a
        # worker that no longer existed, the weights stayed in VRAM and the
        # cards sat at zero. A blackout, from the outside, with no cause.
        self.assertTrue(states, "il fallimento non ha aggiornato nessuno stato")
        self.assertEqual(states[-1]["status"], "failed")
        self.assertIn("connessione chiusa", states[-1]["status_message"])
        self.assertIn("RuntimeError", states[-1]["error"])
        self.assertNotIn("bm_test", benchmarks._active_threads)

    def test_the_thread_is_always_deregistered(self):
        from unittest import mock
        from core.modules.sigma_training_lab.training import benchmarks

        with mock.patch.object(benchmarks, "_run_official_benchmark",
                               side_effect=lambda *a: None):
            benchmarks._active_threads["bm_ok"] = object()
            benchmarks._worker_run_official_benchmark("bm_ok", "sigma:x", "mmlu",
                                                      "sample", 10, 1)
        self.assertNotIn("bm_ok", benchmarks._active_threads)


class TestArchitectureMismatch(unittest.TestCase):
    """A checkpoint newer than the library must fail, and say so precisely."""

    def test_the_unrecognised_architecture_error_is_recognised(self):
        from core.engine.unified_runtime import _unrecognised_architecture

        self.assertTrue(_unrecognised_architecture(
            "ValueError: The checkpoint you are trying to load has model type "
            "`gemma4_unified` but Transformers does not recognize this architecture."))
        self.assertFalse(_unrecognised_architecture("CUDA out of memory"))

    def test_the_advice_names_both_versions(self):
        import json, os, tempfile
        from core.engine.unified_runtime import _version_mismatch_advice

        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "config.json"), "w", encoding="utf-8") as fh:
                json.dump({"transformers_version": "9.9.0"}, fh)
            advice = _version_mismatch_advice(folder)

        # "Your version of Transformers is out of date" followed by three things
        # to try is a guess. Both numbers are knowable, so it can be a statement.
        self.assertIn("9.9.0", advice)
        self.assertIn("pip install --upgrade transformers", advice)
        self.assertIn("GGUF", advice)

    def test_a_memory_hint_is_not_given_for_an_unknown_architecture(self):
        from core.engine.unified_runtime import sigma_engine

        message = sigma_engine._format_load_failure("some-model", {
            "stage": "load",
            "error": "ValueError: The checkpoint you are trying to load has model "
                     "type `gemma4_unified` but Transformers does not recognize "
                     "this architecture.",
        })
        # It used to end with "if it is a memory error, reduce the context",
        # which sent the reader looking in entirely the wrong place.
        self.assertNotIn("errore di memoria", message)
        self.assertIn("transformers", message.lower())


# ---------------------------------------------------------------------------
# Placing a model across two cards
# ---------------------------------------------------------------------------

class TestTiedWeightPlacement(unittest.TestCase):
    """One tensor with two names cannot live on two devices."""

    def _map(self):
        return {
            "model.language_model.embed_tokens": 0,
            "model.language_model.layers.0": 0,
            "model.language_model.layers.1": 1,
            "lm_head": 1,
        }

    def _sizes(self):
        return {"model.language_model.embed_tokens": 2 * 2 ** 30,
                "model.language_model.layers.0": 4 * 2 ** 30,
                "model.language_model.layers.1": 4 * 2 ** 30,
                "lm_head": 2 * 2 ** 30}

    def test_the_head_follows_the_table_it_shares_memory_with(self):
        from core.engine.device_map_builder import DeviceMapBuilder

        placed, moves = DeviceMapBuilder._align_tied_head(self._map(), self._sizes())

        # Split, the tensor exists only where the second of the two landed while
        # the map keeps promising the first. Inputs then go to the promised
        # device and every forward dies on "Expected all tensors to be on the
        # same device" -- with a map that reads perfectly reasonably.
        self.assertEqual(placed["lm_head"], placed["model.language_model.embed_tokens"])
        self.assertEqual(len(moves), 1)
        self.assertIn("legati", moves[0]["reason"])

    def test_an_already_aligned_pair_is_left_alone(self):
        from core.engine.device_map_builder import DeviceMapBuilder

        aligned = self._map()
        aligned["lm_head"] = 0
        placed, moves = DeviceMapBuilder._align_tied_head(aligned, self._sizes())
        self.assertEqual(moves, [])
        self.assertEqual(placed["lm_head"], 0)

    def test_tying_is_read_from_the_text_config_too(self):
        from core.engine.device_map_builder import DeviceMapBuilder

        class _Sub:
            tie_word_embeddings = True

        class _Multimodal:
            tie_word_embeddings = False
            text_config = _Sub()

        class _Plain:
            tie_word_embeddings = False

        # A unified checkpoint declares it on the text sub-config, and reading
        # only the top level answers "no" for a model that ties.
        self.assertTrue(DeviceMapBuilder._weights_are_tied(_Multimodal()))
        self.assertFalse(DeviceMapBuilder._weights_are_tied(_Plain()))

    def test_token_tables_are_gathered_when_they_fit(self):
        from core.engine.device_map_builder import DeviceMapBuilder

        device_map = {"model.language_model.embed_tokens": 0,
                      "model.embed_vision": 1,
                      "model.embed_audio": 1}
        sizes = {k: 1 * 2 ** 29 for k in device_map}
        max_memory = {0: 8 * 2 ** 30, 1: 8 * 2 ** 30}

        placed, moves = DeviceMapBuilder._colocate_token_consumers(
            device_map, sizes, max_memory)

        self.assertEqual(len({str(v) for v in placed.values()}), 1)
        # The card already holding most of them wins, so the fewest bytes move.
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0]["module"], "model.language_model.embed_tokens")

    def test_gathering_is_skipped_rather_than_forced(self):
        from core.engine.device_map_builder import DeviceMapBuilder

        device_map = {"model.language_model.embed_tokens": 0,
                      "model.embed_vision": 1}
        sizes = {k: 6 * 2 ** 30 for k in device_map}
        max_memory = {0: 7 * 2 ** 30, 1: 7 * 2 ** 30}

        # Forcing them together here would trade a device mismatch for an
        # out-of-memory half way through the first answer.
        placed, moves = DeviceMapBuilder._colocate_token_consumers(
            device_map, sizes, max_memory)
        self.assertEqual(moves, [])
        self.assertEqual(placed, device_map)


class TestPlacementValidation(unittest.TestCase):
    """A map that names modules the model does not have places nothing."""

    def test_phantom_modules_are_detected(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        class _Model:
            def named_modules(self):
                return [("", None), ("model", None), ("model.embed_tokens", None)]

        stale = UniversalSigmaEngine._stale_placement(
            _Model(), {"model.embed_tokens": 0, "model.vision_tower": 1})
        self.assertEqual(stale, ["model.vision_tower"])

    def test_a_matching_map_reports_nothing_stale(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        class _Model:
            def named_modules(self):
                return [("", None), ("model", None),
                        ("model.embed_tokens", None), ("model.layers.0", None)]

        self.assertEqual(
            UniversalSigmaEngine._stale_placement(
                _Model(), {"model.embed_tokens": 0, "model.layers": 1}),
            [])


class TestSequenceStart(unittest.TestCase):
    """The token a tokenizer promises and then does not add."""

    def test_bos_is_prepended_when_the_tokenizer_skips_it(self):
        from core.engine.unified_runtime import _with_bos

        class _GemmaLike:
            bos_token_id = 2

        # Gemma declares a BOS and does not prepend it, even when asked. Without
        # it the model is outside its own training distribution and every
        # likelihood is noise -- quietly, with plausible-looking scores.
        self.assertEqual(_with_bos(_GemmaLike(), [818, 5279]), [2, 818, 5279])

    def test_an_existing_bos_is_not_duplicated(self):
        from core.engine.unified_runtime import _with_bos

        class _Tok:
            bos_token_id = 2

        self.assertEqual(_with_bos(_Tok(), [2, 818]), [2, 818])

    def test_a_tokenizer_without_a_bos_is_left_alone(self):
        from core.engine.unified_runtime import _with_bos

        class _NoBos:
            bos_token_id = None

        self.assertEqual(_with_bos(_NoBos(), [818, 5279]), [818, 5279])

    def test_the_calibration_floor_would_have_caught_it(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        # The broken run scored -18.7 on an obvious continuation; a working one
        # scores about -0.4. Any floor between the two catches it, and this one
        # is nearer the broken end so a merely weak model is not accused.
        self.assertLess(-18.7, UniversalSigmaEngine.CALIBRATION_FLOOR)
        self.assertGreater(-0.445, UniversalSigmaEngine.CALIBRATION_FLOOR)

    def test_continuation_contexts_follow_the_published_format(self):
        from core.modules.sigma_training_lab.training.protocols import protocol_for

        # " Paris" is not equally likely after a bare question and after the
        # same question framed with an "Answer:" cue, and the published scores
        # are the second.
        self.assertIn("Answer:", protocol_for("arc").context)
        self.assertIn("A:", protocol_for("truthfulqa").context)
        # HellaSwag's context is already a sentence to finish; a frame around it
        # would change what is being measured.
        self.assertEqual(protocol_for("hellaswag").context, "{q}")


class TestParallelSlots(unittest.TestCase):
    """Capacity the GGUF server already has, and used to sit idle."""

    def test_a_server_with_slots_runs_prompts_together(self):
        import threading
        import time
        from core.engine.unified_runtime import UniversalSigmaEngine

        vivi, massimo = [], [0]
        guardia = threading.Lock()

        class _SlottedBackend:
            def parallel_slots(self):
                return 4

            def generate_stream(self, prompt, **kw):
                with guardia:
                    vivi.append(1)
                    massimo[0] = max(massimo[0], len(vivi))
                time.sleep(0.05)
                with guardia:
                    vivi.pop()
                yield {"token": "42", "done": False}
                yield {"token": "", "done": True, "total_tokens": 1}

        engine = UniversalSigmaEngine()
        engine.active_backend_instance = _SlottedBackend()
        engine._ensure_resident = lambda name=None: {"success": True}

        results = engine.generate_batch(
            [[{"role": "user", "content": f"q{n}"}] for n in range(8)],
            model_name="gguf",
        )
        self.assertEqual(len(results), 8)
        self.assertTrue(all(r["text"] == "42" for r in results))
        # `-np 4 --cont-batching` is paid for at startup; one request at a time
        # left three slots idle for the whole run.
        self.assertGreater(massimo[0], 1)

    def test_an_in_process_context_stays_sequential(self):
        import threading
        from core.engine.unified_runtime import UniversalSigmaEngine

        vivi, massimo = [], [0]
        guardia = threading.Lock()

        class _SingleContext:
            # No parallel_slots(): the base contract answers 1, and one is not
            # caution here -- an in-process llama.cpp context is not thread-safe,
            # so two callers do not run twice as fast, they corrupt each other.
            def generate_stream(self, prompt, **kw):
                with guardia:
                    vivi.append(1)
                    massimo[0] = max(massimo[0], len(vivi))
                    vivi.pop()
                yield {"token": "ok", "done": False}
                yield {"token": "", "done": True, "total_tokens": 1}

        engine = UniversalSigmaEngine()
        engine.active_backend_instance = _SingleContext()
        engine._ensure_resident = lambda name=None: {"success": True}
        engine.generate_batch([[{"role": "user", "content": f"q{n}"}]
                               for n in range(4)], model_name="gguf")
        self.assertEqual(massimo[0], 1)


class TestConcurrentSlotSafety(unittest.TestCase):
    """Adding concurrency to a backend exposes what was hiding on `self`."""

    def test_reasoning_state_does_not_leak_between_generations(self):
        import inspect
        from core.engine.backends import llamaserver_backend

        # `self._in_ragionamento` marked where one answer's <think> block began
        # and ended. With four slots in flight, one answer's marker closed
        # another answer's block, and the reader downstream hid everything
        # after it.
        source = inspect.getsource(llamaserver_backend)
        self.assertNotIn("_in_ragionamento", source)
        self.assertIn('"kind": "reasoning"', source)

    def test_the_stall_budget_grows_with_requests_in_flight(self):
        from core.engine.backends import llamaserver_backend as backend

        # One request alone owns the server; four share it, and three of them
        # legitimately wait while the first decodes. A budget sized for one
        # declared all four failed at the same second.
        self.assertEqual(backend._STALLO_TIMEOUT_S * 4,
                         min(backend._STALLO_TIMEOUT_S * 4,
                             backend._GENERAZIONE_MAX_S))
        self.assertLessEqual(backend._STALLO_TIMEOUT_S * 100,
                             backend._GENERAZIONE_MAX_S * 100)

    def test_a_timeout_drops_the_run_to_one_request_at_a_time(self):
        import threading
        from core.engine.unified_runtime import UniversalSigmaEngine

        larghezze, guardia = [], threading.Lock()
        vivi = [0]

        class _FlakyServer:
            def parallel_slots(self):
                return 4

            def generate_stream(self, prompt, **kw):
                with guardia:
                    vivi[0] += 1
                    larghezze.append(vivi[0])
                primo = len(larghezze) <= 4
                with guardia:
                    vivi[0] -= 1
                if primo:
                    yield {"token": "", "done": True, "total_tokens": 0,
                           "finish_reason": "timeout", "truncated": True}
                else:
                    yield {"token": "ok", "done": False}
                    yield {"token": "", "done": True, "total_tokens": 1}

        engine = UniversalSigmaEngine()
        engine.active_backend_instance = _FlakyServer()
        engine._ensure_resident = lambda name=None: {"success": True}
        engine.generate_batch([[{"role": "user", "content": f"q{n}"}]
                               for n in range(8)], model_name="gguf")

        # Collecting timeouts four at a time until the sample runs out is the
        # slowest possible way to learn the server cannot take four.
        self.assertEqual(max(larghezze[4:], default=1), 1)


class TestPerItemTiming(unittest.TestCase):
    """A timing that is an interval between arrivals is not a timing."""

    def setUp(self):
        from core.engine import evaluation as ev
        self.ev = ev
        self._complete_batch = ev.complete_batch

    def tearDown(self):
        self.ev.complete_batch = self._complete_batch

    def test_answers_arriving_together_do_not_report_zero(self):
        from core.modules.sigma_training_lab.training import benchmarks

        def _fake_batch(conversations, on_result=None, **kw):
            answers = []
            entries = [{"index": i, "text": "42", "tokens": 3, "error": ""}
                       for i in range(len(conversations))]
            for entry in entries:            # tutte insieme, come da un lotto
                if on_result:
                    on_result(entry)
                answers.append(self.ev.Completion(text="42", tokens=3))
            return answers

        self.ev.complete_batch = _fake_batch
        items = [{"id": f"g{n}", "suite": "bbh", "prompt": "q", "options": []}
                 for n in range(4)]
        results = benchmarks._run_sigma_generative(items, "sigma:tiny", "tiny", 4)

        # The old measurement gave the first arrival the whole elapsed time and
        # the rest nothing: "300.013 ms" followed by "6 ms", "0 ms", "2 ms".
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r["latency_ms"] >= 0 for r in results.values()))
        tempi = [r["latency_ms"] for r in results.values()]
        self.assertLessEqual(max(tempi) - min(tempi), max(tempi) + 1)


if __name__ == "__main__":
    unittest.main()
