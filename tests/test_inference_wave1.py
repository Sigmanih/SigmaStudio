# ==============================================================================
# tests/test_inference_wave1.py — Regression cover for the first optimisation wave
#
# Each test here pins a property that was previously violated on every single
# chat message. They are cheap and hardware-independent on purpose: no model is
# loaded, no GPU is required, and they pass identically on CUDA, Apple silicon
# and a CPU-only board -- which is the point, since the changes they cover exist
# to make the engine behave the same everywhere.
# ==============================================================================
import hashlib
import unittest

from core.engine.sampling import SamplingParams, FAMILY_RECIPES
from core.engine.cancellation import CancellationToken, is_cancelled, stopping_criteria_for
from core.ai_providers import EXECUTION_PROFILES, detect_execution_profile


class TestSamplingParams(unittest.TestCase):
    """Q1 — one sampler, resolved once, honoured by every backend."""

    def test_family_recipe_applies_when_config_is_untouched(self):
        params = SamplingParams.resolve(model_name="Qwen/Qwen3-8B-Instruct")
        recipe = FAMILY_RECIPES["qwen3"]["direct"]
        self.assertEqual(params.top_p, recipe["top_p"])
        self.assertEqual(params.top_k, recipe["top_k"])
        self.assertIn("family:qwen3", params.source)

    def test_reasoning_and_direct_modes_differ(self):
        direct = SamplingParams.resolve(model_name="qwen3-27b", reasoning=False)
        thinking = SamplingParams.resolve(model_name="qwen3-27b", reasoning=True)
        self.assertNotEqual(direct.top_p, thinking.top_p)

    def test_unknown_family_falls_back_to_generic(self):
        params = SamplingParams.resolve(model_name="entirely-made-up-model")
        self.assertIn("family:generic", params.source)

    def test_shipped_default_is_not_treated_as_user_intent(self):
        # 0.9 is what Sigma Studio ships for top_p, so it carries no opinion and
        # must not overwrite the family recipe.
        params = SamplingParams.resolve(
            model_name="Qwen/Qwen3-8B",
            provider_key="sigma_engine",
            provider_cfg={"top_p": 0.9},
        )
        self.assertEqual(params.top_p, FAMILY_RECIPES["qwen3"]["direct"]["top_p"])

    def test_changed_config_value_does_override_the_recipe(self):
        params = SamplingParams.resolve(
            model_name="Qwen/Qwen3-8B",
            provider_key="sigma_engine",
            provider_cfg={"top_k": 7},
        )
        self.assertEqual(params.top_k, 7)

    def test_profile_owns_temperature_and_budget(self):
        cfg = {"temperature": 0.1, "max_tokens": 65536}
        fast = SamplingParams.resolve(
            provider_key="sigma_engine", provider_cfg=cfg,
            profile=EXECUTION_PROFILES["fast_chat"],
        )
        deep = SamplingParams.resolve(
            provider_key="sigma_engine", provider_cfg=cfg,
            profile=EXECUTION_PROFILES["code"],
        )
        # A greeting and a refactor must not be planned with the same budget,
        # which is exactly what a single global config value produced.
        self.assertEqual(fast.max_tokens, EXECUTION_PROFILES["fast_chat"]["max_tokens"])
        self.assertEqual(deep.temperature, EXECUTION_PROFILES["code"]["temperature"])
        self.assertNotEqual(fast.max_tokens, deep.max_tokens)

    def test_sampling_locked_returns_control_to_the_user(self):
        cfg = {"temperature": 0.1, "max_tokens": 65536, "sampling_locked": True}
        params = SamplingParams.resolve(
            provider_key="sigma_engine", provider_cfg=cfg,
            profile=EXECUTION_PROFILES["fast_chat"],
        )
        self.assertEqual(params.temperature, 0.1)
        self.assertEqual(params.max_tokens, 65536)
        self.assertIn("locked", params.source)

    def test_seed_zero_means_no_seed(self):
        # The shipped config carries seed 0; forwarding it literally would pin
        # every answer in the product to one sample.
        self.assertIsNone(SamplingParams.resolve(provider_cfg={"seed": 0}).seed)
        self.assertEqual(SamplingParams.resolve(provider_cfg={"seed": 42}).seed, 42)

    def test_greedy_decoding_drops_sampling_knobs(self):
        kwargs = SamplingParams.resolve().with_overrides(temperature=0).for_transformers()
        self.assertFalse(kwargs["do_sample"])
        for knob in ("temperature", "top_p", "top_k", "min_p"):
            self.assertNotIn(knob, kwargs)

    def test_every_backend_adapter_produces_valid_keys(self):
        params = SamplingParams.resolve(model_name="qwen3-8b")
        self.assertIn("max_new_tokens", params.for_transformers())
        self.assertIn("repeat_penalty", params.for_llama_cpp())
        self.assertIn("num_predict", params.for_ollama_options())
        # top_k has no place in the OpenAI schema and must not be sent.
        self.assertNotIn("top_k", params.for_openai())

    def test_unknown_override_keys_are_ignored(self):
        params = SamplingParams.resolve().with_overrides(nonsense=1, temperature=0.3)
        self.assertEqual(params.temperature, 0.3)
        self.assertFalse(hasattr(params, "nonsense"))


class TestCancellation(unittest.TestCase):
    """L4 — an abandoned request must stop costing compute."""

    def test_token_reports_and_keeps_the_first_reason(self):
        token = CancellationToken()
        self.assertFalse(is_cancelled(token))
        token.cancel("client_disconnected")
        token.cancel("something_later")
        self.assertTrue(is_cancelled(token))
        self.assertEqual(token.reason, "client_disconnected")

    def test_absent_token_is_never_cancelled(self):
        # Every call site may legitimately have no token: chat has to work on a
        # host with no local engine installed.
        self.assertFalse(is_cancelled(None))
        self.assertIsNone(stopping_criteria_for(None))

    def test_stopping_criteria_fires_once_cancelled(self):
        token = CancellationToken()
        criteria = stopping_criteria_for(token)
        if criteria is None:
            self.skipTest("transformers not installed on this host")
        self.assertFalse(criteria[0](None, None))
        token.cancel()
        self.assertTrue(criteria[0](None, None))


class TestExecutionProfiles(unittest.TestCase):
    """L8 / L9 — the profile decides the budget and whether to think."""

    def test_every_profile_declares_whether_it_reasons(self):
        for key, profile in EXECUTION_PROFILES.items():
            self.assertIn("reasoning", profile, f"profile '{key}' has no reasoning flag")

    def test_greetings_take_the_fast_lane_even_with_punctuation(self):
        for greeting in ("ciao", "Ciao!", "buongiorno,", "grazie!!", "Ciao, come stai?"):
            self.assertEqual(
                detect_execution_profile(greeting), "fast_chat",
                f"'{greeting}' should not be planned like a proof",
            )

    def test_greetings_do_not_ask_the_model_to_think(self):
        profile = EXECUTION_PROFILES[detect_execution_profile("ciao")]
        self.assertFalse(profile["reasoning"])

    def test_code_and_maths_do_ask_the_model_to_think(self):
        for message in ("scrivi una funzione python di quicksort",
                        "dimostra il teorema di Pitagora"):
            profile = EXECUTION_PROFILES[detect_execution_profile(message)]
            self.assertTrue(profile["reasoning"], message)


class TestPromptPrefixStability(unittest.TestCase):
    """L1 — the system message must be reusable from the KV cache."""

    def _assemble(self, message, history):
        import core.chat.chat_runner as cr

        captured = {}

        def fake_stream(handler, messages, *args, **kwargs):
            captured["messages"] = messages
            captured["sampling"] = kwargs.get("sampling")
            captured["wants_reasoning"] = kwargs.get("wants_reasoning")
            return None

        class FakeHandler:
            def read_json_body(self):
                return {"message": message, "history": history, "stream": True,
                        "manifesto_path": "manifesti/sigma_assistant.md"}

            def send_json_response(self, payload, code=200):
                return payload

        original = cr._stream_chat_response
        cr._stream_chat_response = fake_stream
        try:
            cr.handle_chat(FakeHandler())
        finally:
            cr._stream_chat_response = original
        return captured

    def test_system_message_is_byte_identical_across_turns(self):
        history = []
        digests = set()
        for message in ("Ciao", "scrivi una funzione python",
                        "e ora dimostra che termina"):
            captured = self._assemble(message, list(history))
            system = captured["messages"][0]["content"]
            digests.add(hashlib.sha1(system.encode("utf-8")).hexdigest())
            history += [{"role": "user", "content": message},
                        {"role": "assistant", "content": "ok"}]
        self.assertEqual(len(digests), 1,
                         "the system prefix changed between turns, so no KV cache can hit")

    def test_volatile_context_is_not_in_the_system_message(self):
        captured = self._assemble("Ciao", [])
        system = captured["messages"][0]["content"]
        self.assertNotIn("ORA CORRENTE", system)
        self.assertNotIn("STRUTTURA PROGETTO", system)

    def test_volatile_context_rides_with_the_final_user_turn(self):
        captured = self._assemble("Ciao", [])
        last = captured["messages"][-1]
        self.assertEqual(last["role"], "user")
        self.assertIn("ORA CORRENTE", last["content"])

    def test_the_question_stays_last_in_its_turn(self):
        # Burying the question under a directory listing is how an assistant
        # ends up describing the listing.
        message = "scrivi una funzione python"
        captured = self._assemble(message, [])
        self.assertTrue(captured["messages"][-1]["content"].rstrip().endswith(message))

    def test_reasoning_follows_the_message_not_the_provider(self):
        self.assertFalse(self._assemble("Ciao", [])["wants_reasoning"])
        self.assertTrue(self._assemble("dimostra il teorema", [])["wants_reasoning"])


class TestFilesystemContextCache(unittest.TestCase):
    """L10 — the knowledge-base tree is not rebuilt from disk on every message."""

    def test_repeated_calls_return_the_same_text(self):
        from core.chat.prompt_builder import (
            _build_filesystem_context, invalidate_filesystem_context,
        )
        invalidate_filesystem_context()
        first = _build_filesystem_context()
        self.assertEqual(first, _build_filesystem_context())

    def test_invalidation_rebuilds_without_changing_the_answer(self):
        from core.chat.prompt_builder import (
            _build_filesystem_context, invalidate_filesystem_context,
        )
        before = _build_filesystem_context()
        invalidate_filesystem_context()
        self.assertEqual(before, _build_filesystem_context())


class _FakeWfile:
    """A socket that breaks after N writes, like a client that closed the tab."""

    def __init__(self, break_after=None):
        self.events = []
        self.writes = 0
        self.break_after = break_after

    def write(self, blob):
        self.writes += 1
        if self.break_after is not None and self.writes > self.break_after:
            raise BrokenPipeError("client gone")
        line = blob.decode("utf-8").strip()
        if line.startswith("data: "):
            self.events.append(line[6:])

    def flush(self):
        pass


class _FakeHandler:
    def __init__(self, break_after=None):
        self.wfile = _FakeWfile(break_after)

    def send_response(self, code):
        pass

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


class TestStreamCancellation(unittest.TestCase):
    """L4 end to end — a broken pipe must reach the generator, not be swallowed."""

    TOTAL = 200

    def _run(self, break_after, wants_reasoning=True):
        import core.ai_providers as providers
        import core.chat.chat_runner as cr

        state = {"produced": 0, "saw_cancel": False, "messages": None}

        def fake_stream(messages, *args, params=None, cancel=None, **kwargs):
            state["messages"] = messages
            for index in range(self.TOTAL):
                if cancel is not None and cancel.cancelled:
                    state["saw_cancel"] = True
                    return
                state["produced"] += 1
                yield {"token": f"tok{index} "}
            yield {"done": True, "speed_tok_s": 42.0, "total_tokens": self.TOTAL}

        original = providers.call_ai_model_stream
        providers.call_ai_model_stream = fake_stream
        handler = _FakeHandler(break_after)
        try:
            cr._stream_chat_response(
                handler,
                [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                {"providers": {}}, "qwen3-8b", "sigma_engine", "", "", "",
                0.7, 4096, 0.9, 30,
                message="u", bot_name="Bot", manifesto_path="", allow_actions=False,
                sampling=SamplingParams.resolve(model_name="qwen3-8b"),
                wants_reasoning=wants_reasoning,
            )
        finally:
            providers.call_ai_model_stream = original
        return handler, state

    def test_full_stream_reaches_the_client(self):
        handler, state = self._run(break_after=None)
        self.assertEqual(state["produced"], self.TOTAL)
        self.assertTrue(handler.wfile.events)

    def test_broken_pipe_stops_the_generator(self):
        handler, state = self._run(break_after=5)
        self.assertTrue(state["saw_cancel"],
                        "the cancellation never reached the generator")
        self.assertLess(state["produced"], self.TOTAL,
                        "generation ran to the full budget with nobody reading")

    def test_reported_speed_comes_from_the_runtime(self):
        # Not from a word count: in Italian that is off by the tokenizer ratio.
        handler, _ = self._run(break_after=None)
        metrics = {}
        for raw in handler.wfile.events:
            if raw == "[DONE]":
                continue
            payload = __import__("json").loads(raw)
            if payload.get("metrics", {}).get("tokens_per_second") is not None:
                metrics = payload["metrics"]
        self.assertEqual(metrics.get("tokens_per_second"), 42.0)
        self.assertEqual(metrics.get("token_count"), self.TOTAL)

    def test_think_prefill_follows_the_profile(self):
        _, thinking = self._run(break_after=None, wants_reasoning=True)
        _, direct = self._run(break_after=None, wants_reasoning=False)
        self.assertTrue(thinking["messages"][-1]["content"].startswith("<think>"))
        self.assertFalse(direct["messages"][-1]["content"].startswith("<think>"))


class TestEmbeddingRouter(unittest.TestCase):
    """L3 — routing without a model pass, on any host."""

    def test_router_answers_without_sentence_transformers(self):
        # The pure-standard-library fallback is the configuration on a fresh
        # CPU-only install and on ARM boards, so it has to actually route.
        from core.embedding_router import _fallback_similarity_classify

        verdict = _fallback_similarity_classify("scrivi i test pytest per il parser")
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict["agent"], "test_engineer")

    def test_router_tolerates_empty_input(self):
        from core.embedding_router import classify_intent_multilingual
        self.assertIsNone(classify_intent_multilingual("   "))

    def test_routing_never_returns_a_manifesto_that_is_not_installed(self):
        import os
        from core.chat.prompt_builder import _resolve_agent_by_request
        from core.ai_providers import load_ai_config

        cfg = load_ai_config()
        for message in ("traduci in inglese", "fammi un grafico d3",
                        "calcola il ph della soluzione", "ciao"):
            path = _resolve_agent_by_request(message, cfg, "")
            self.assertTrue(os.path.exists(path), f"'{message}' routed to missing {path}")


if __name__ == "__main__":
    unittest.main()
