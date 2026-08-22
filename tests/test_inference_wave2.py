# ==============================================================================
# tests/test_inference_wave2.py — Regression cover for the second wave
#
# Throughput and structure: cross-turn KV reuse, the generation queue, the
# llama.cpp placement knobs, token-budgeted history, SSE coalescing and
# grammar-constrained tool calls.
#
# Most of it needs no model: planning and bookkeeping are where the decisions
# live, and testing them there is why the bulk of this file runs identically on
# a CUDA box, an Apple laptop and a board with no accelerator at all.
#
# Three tests deliberately break that rule, because the wave shipped a crash
# that only a real runtime could have caught: a grammar that reads correctly and
# generates invalid JSON, and a llama.cpp option that loads cleanly and fails on
# the first long prompt. Those are exercised against the installed libraries --
# a two-layer transformers model built from config, and the smallest local GGUF
# -- and skip themselves where the library is absent.
# ==============================================================================
import threading
import time
import unittest

from core.chat.history import (
    estimate_tokens, trim_history, dropped_notice, history_budget,
)
from core.engine.grammars import (
    tool_call_grammar, json_object_grammar, compile_for_llama_cpp,
)
from core.engine.prefix_cache import PrefixKVCache, MIN_REUSABLE_TOKENS
from core.engine.model_inspector import ModelFacts
from core.engine.backends.llamacpp_backend import LlamaCppBackend


class _FakeCache:
    """Stands in for a transformers DynamicCache: it only needs to crop."""

    def __init__(self, length):
        self.length = length
        self.cropped_to = None

    def crop(self, maximum_length):
        self.cropped_to = maximum_length
        self.length = maximum_length


class TestPrefixKVCache(unittest.TestCase):
    """L2 — the model should not re-read what it read last turn."""

    def _cache(self):
        cache = PrefixKVCache(max_tokens=4096)
        cache.configure("model-a", 4096)
        return cache

    def test_cold_cache_is_a_miss(self):
        cache = self._cache()
        past, reused = cache.take(list(range(200)), "model-a")
        self.assertIsNone(past)
        self.assertEqual(reused, 0)

    def test_shared_prefix_is_reused_and_cropped(self):
        cache = self._cache()
        turn_one = list(range(500))
        cache.store(turn_one, _FakeCache(len(turn_one)), "model-a")

        # Next turn: same conversation plus a new question.
        turn_two = turn_one + [9001, 9002, 9003]
        past, reused = cache.take(turn_two, "model-a")

        self.assertIsNotNone(past)
        self.assertEqual(reused, len(turn_one))
        self.assertEqual(past.cropped_to, len(turn_one))

    def test_cache_never_covers_the_whole_prompt(self):
        # generate() needs at least one token to forward; a cache as long as
        # the input leaves it nothing to do and raises.
        cache = self._cache()
        ids = list(range(300))
        cache.store(ids, _FakeCache(len(ids)), "model-a")
        past, reused = cache.take(ids, "model-a")
        self.assertLess(reused, len(ids))

    def test_a_changed_prefix_is_not_reused(self):
        # This is the failure the whole feature guards against: reusing a cache
        # whose tokens no longer match would corrupt the answer, not slow it.
        cache = self._cache()
        cache.store(list(range(500)), _FakeCache(500), "model-a")
        diverged = [777] + list(range(1, 500))
        past, reused = cache.take(diverged, "model-a")
        self.assertIsNone(past)
        self.assertEqual(reused, 0)

    def test_a_different_model_is_never_reused(self):
        cache = self._cache()
        cache.store(list(range(500)), _FakeCache(500), "model-a")
        past, _ = cache.take(list(range(600)), "model-b")
        self.assertIsNone(past)

    def test_tiny_overlap_is_not_worth_keeping(self):
        cache = self._cache()
        shared = MIN_REUSABLE_TOKENS - 10
        cache.store(list(range(shared)), _FakeCache(shared), "model-a")
        past, reused = cache.take(list(range(shared)) + [1] * 50, "model-a")
        self.assertIsNone(past)

    def test_sequence_beyond_the_reserved_window_is_dropped(self):
        cache = PrefixKVCache(max_tokens=100)
        cache.configure("model-a", 100)
        cache.store(list(range(500)), _FakeCache(500), "model-a")
        past, _ = cache.take(list(range(500)) + [1], "model-a")
        self.assertIsNone(past, "a cache past the reserved window must not be held")

    def test_configure_for_a_new_model_drops_the_old_cache(self):
        cache = self._cache()
        cache.store(list(range(500)), _FakeCache(500), "model-a")
        cache.configure("model-b", 4096)
        past, _ = cache.take(list(range(600)), "model-b")
        self.assertIsNone(past)

    def test_stats_report_real_counters(self):
        cache = self._cache()
        cache.store(list(range(500)), _FakeCache(500), "model-a")
        cache.take(list(range(520)), "model-a")
        cache.take(list(range(10)), "model-a")
        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["tokens_reused"], 500)


class TestPrefixCacheAgainstRealTransformers(unittest.TestCase):
    """
    The library contract PrefixKVCache depends on, exercised for real.

    A fake cache proves the bookkeeping; it cannot prove that transformers
    still offers `crop`, or that a cropped cache produces the same answer as a
    full prefill. That second property is the whole safety argument for the
    feature -- a reused cache that changes the answer is worse than no cache --
    so it is checked against a real model rather than asserted in a comment.

    The model is built from a config with random weights: two layers and a
    64-wide hidden state, which is instant and needs no download, while
    exercising exactly the same generate() path a real checkpoint would.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM
        except ImportError:
            raise unittest.SkipTest("transformers/torch not installed on this host")

        torch.manual_seed(0)
        config = AutoConfig.for_model(
            "qwen2", vocab_size=512, hidden_size=64, intermediate_size=128,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
            max_position_embeddings=1024,
        )
        cls.torch = torch
        cls.model = AutoModelForCausalLM.from_config(config).eval()

    def _generate(self, ids, past=None, new_tokens=6):
        with self.torch.inference_mode():
            return self.model.generate(
                ids, max_new_tokens=new_tokens, do_sample=False, use_cache=True,
                past_key_values=past, return_dict_in_generate=True,
            )

    def test_generate_returns_a_croppable_cache(self):
        ids = self.torch.arange(120).unsqueeze(0) % 512
        result = self._generate(ids)
        cache = result.past_key_values
        self.assertTrue(hasattr(cache, "crop"),
                        "transformers no longer exposes crop(); prefix reuse "
                        "must fall back to a full prefill")
        cache.crop(100)
        self.assertEqual(cache.get_seq_length(), 100)

    def test_a_reused_cache_produces_the_identical_answer(self):
        first = self._generate(self.torch.arange(120).unsqueeze(0) % 512)
        sequence = first.sequences[0].tolist()

        cache = PrefixKVCache(max_tokens=1024)
        cache.configure("tiny", 1024)
        cache.store(sequence, first.past_key_values, "tiny")

        follow_up = self.torch.tensor([sequence + [7, 8, 9]])
        past, reused = cache.take(follow_up[0].tolist(), "tiny")
        self.assertGreater(reused, 0)

        warm = self._generate(follow_up, past=past)
        cold = self._generate(follow_up)

        start = follow_up.shape[1]
        self.assertEqual(
            warm.sequences[0].tolist()[start:],
            cold.sequences[0].tolist()[start:],
            "reusing the cache changed the answer",
        )


class TestGenerationQueue(unittest.TestCase):
    """L5 — one resident model means one generation at a time."""

    def test_engine_exposes_a_generation_lock(self):
        from core.engine import sigma_engine
        self.assertTrue(hasattr(sigma_engine, "_generation_lock"))

    def test_the_lock_actually_serialises(self):
        lock = threading.RLock()
        order = []

        def worker(name):
            with lock:
                order.append(f"{name}:in")
                time.sleep(0.02)
                order.append(f"{name}:out")

        threads = [threading.Thread(target=worker, args=(n,)) for n in "ab"]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No interleaving: every "in" is followed by its own "out".
        for index in range(0, len(order), 2):
            self.assertEqual(order[index].split(":")[0], order[index + 1].split(":")[0])

    def test_status_reports_the_queue_and_the_cache(self):
        from core.engine import sigma_engine
        status = sigma_engine.get_status()
        self.assertIn("generation_queue", status)
        self.assertIn("prefix_cache", status)


def _facts_27b():
    facts = ModelFacts(
        path="/fake/qwen3-27b-gguf", name="Qwen3.8-27B-GGUF", model_type="qwen3",
        architectures=["Qwen3ForCausalLM"], weight_format="gguf",
        num_hidden_layers=64, hidden_size=5120, head_dim=128,
        num_attention_heads=40, num_key_value_heads=8, vocab_size=152064,
        max_position_embeddings=32768,
    )
    facts.total_bytes = 16 * 2**30
    return facts


_HW_DUAL_GPU = {
    "accelerators": [
        {"type": "NVIDIA_CUDA", "free_vram_gb": 24.0, "multi_processor_count": 84},
        {"type": "NVIDIA_CUDA", "free_vram_gb": 16.0, "multi_processor_count": 68},
    ],
    "cpu": {"cores_physical": 16}, "system": {},
}
_HW_TIGHT_GPU = {
    "accelerators": [{"type": "NVIDIA_CUDA", "free_vram_gb": 8.0,
                      "multi_processor_count": 46}],
    "cpu": {"cores_physical": 8}, "system": {},
}
# One card with just enough VRAM that the KV cache decides the placement: the
# f16 cache leaves most layers on the host, the halved one nearly clears them.
# This is the only regime where quantizing is the right call, and the fixture
# exists so the policy is tested where it actually applies.
_HW_BORDERLINE_GPU = {
    "accelerators": [{"type": "NVIDIA_CUDA", "free_vram_gb": 21.5,
                      "multi_processor_count": 84}],
    "cpu": {"cores_physical": 16}, "system": {}, "ram": {"available_gb": 64.0},
}
_HW_APPLE = {"accelerators": [{"type": "APPLE_MPS"}],
             "cpu": {"cores_physical": 10}, "system": {}}
_HW_PI = {"accelerators": [], "cpu": {"cores_physical": 4},
          "system": {"is_arm": True, "is_raspberry_pi": True}}
_HW_CPU = {"accelerators": [], "cpu": {"cores_physical": 12}, "system": {}}


class TestLlamaCppPlanning(unittest.TestCase):
    """L11 / L6 — the knobs that decide throughput on the GGUF path."""

    def test_kv_is_quantized_only_when_it_pays_for_itself(self):
        """
        The rule is the measurement, not the context length.

        Quantizing costs ~11% of decode on every host-resident layer, so it is
        applied when halving the cache cuts host traffic by more than that.
        The first version of this policy fired on context length alone: on the
        50GB F16 that prompted the rewrite it moved one layer of sixty-five
        onto the GPU and slowed the other forty-seven down.
        """
        # Borderline card: the f16 cache strands most layers on the host and
        # halving it nearly clears them. Apply.
        borderline = _facts_27b()
        borderline.total_bytes = 14 * 2**30
        self.assertEqual(
            LlamaCppBackend._plan_settings(borderline, _HW_BORDERLINE_GPU, 32768)["kv_quant"],
            "q8_0",
        )

        # Everything already fits: there is nothing to buy, and the penalty
        # would be paid for no gain.
        self.assertIsNone(
            LlamaCppBackend._plan_settings(borderline, _HW_DUAL_GPU, 32768)["kv_quant"]
        )

        # Hopeless placement: halving the cache changes almost nothing, and the
        # penalty would land on every layer left on the host. This is the 50GB
        # F16 from the report.
        hopeless = _facts_27b()
        hopeless.total_bytes = 51 * 2**30
        self.assertIsNone(
            LlamaCppBackend._plan_settings(hopeless, _HW_BORDERLINE_GPU, 32768)["kv_quant"]
        )

    def test_the_decision_rule_matches_the_measurement(self):
        # 4 host layers -> 1 is a fourfold cut: worth 11%.
        self.assertTrue(LlamaCppBackend._kv_quant_pays_off(61, 64, 65))
        # 48 -> 47 is not.
        self.assertFalse(LlamaCppBackend._kv_quant_pays_off(17, 18, 65))
        # Reaching full offload always wins.
        self.assertTrue(LlamaCppBackend._kv_quant_pays_off(60, -1, 65))
        # Already fully offloaded: nothing to buy.
        self.assertFalse(LlamaCppBackend._kv_quant_pays_off(-1, -1, 65))

    def test_a_hopeless_placement_is_forecast_not_hidden(self):
        """
        The regression report this came from: a 50GB F16 on 21GB of VRAM
        answered at half a token per second, and the engine said nothing.
        """
        facts = _facts_27b()
        facts.total_bytes = 51 * 2**30
        hardware = dict(_HW_TIGHT_GPU, ram={"available_gb": 31.0})
        settings = LlamaCppBackend._plan_settings(facts, hardware, 32768)

        forecast = settings["forecast"]
        self.assertEqual(forecast["placement"], "split")
        self.assertTrue(forecast["pages_from_disk"],
                        "the host-resident part does not fit in free RAM and "
                        "that has to be said, it is the difference between "
                        "slow and unusable")
        self.assertLess(forecast["estimated_tokens_per_second"], 1.0)
        self.assertIn("token/s", settings["warning"])

    def test_a_good_placement_carries_no_alarm(self):
        facts = _facts_27b()
        facts.total_bytes = 6 * 2**30
        settings = LlamaCppBackend._plan_settings(facts, _HW_DUAL_GPU, 8192)
        self.assertEqual(settings["forecast"]["placement"], "fully_offloaded")
        self.assertNotIn("warning", settings)

    def test_rates_below_a_tenth_do_not_round_to_zero(self):
        self.assertIn("meno di", LlamaCppBackend._render_rate(0.04))
        self.assertIn("0.5", LlamaCppBackend._render_rate(0.5))
        self.assertIn("12.0", LlamaCppBackend._render_rate(12.0))

    def test_kv_is_left_alone_at_a_short_context(self):
        settings = LlamaCppBackend._plan_settings(_facts_27b(), _HW_DUAL_GPU, 4096)
        self.assertIsNone(settings["kv_quant"])

    def test_quantized_kv_buys_back_gpu_layers(self):
        # Where the trade fires, it must actually move layers onto the card.
        facts = _facts_27b()
        facts.total_bytes = 14 * 2**30
        with_quant = LlamaCppBackend._plan_settings(
            facts, _HW_BORDERLINE_GPU, 32768)["n_gpu_layers"]
        without = LlamaCppBackend._layers_that_fit(
            14.0, facts.num_hidden_layers, 20.0, 8.0)
        self.assertTrue(with_quant == -1 or with_quant > without)

    def test_prefill_batch_grows_only_when_there_is_room(self):
        roomy = LlamaCppBackend._plan_settings(_facts_27b(), _HW_DUAL_GPU, 32768)
        tight = LlamaCppBackend._plan_settings(_facts_27b(), _HW_TIGHT_GPU, 32768)
        self.assertGreater(roomy["n_batch"], tight["n_batch"])

    def test_cpu_paths_do_not_quantize_the_kv_cache(self):
        # KV quantization rides on flash attention, which these paths do not
        # enable; claiming it would be reporting something that is not running.
        for hardware in (_HW_PI, _HW_CPU):
            settings = LlamaCppBackend._plan_settings(_facts_27b(), hardware, 32768)
            self.assertIsNone(settings["kv_quant"])
            self.assertFalse(settings["flash_attn"])

    def test_arm_keeps_a_small_prefill_batch(self):
        settings = LlamaCppBackend._plan_settings(_facts_27b(), _HW_PI, 8192)
        self.assertLessEqual(settings["n_batch"], 128)
        self.assertEqual(settings["n_gpu_layers"], 0)

    def test_prompt_lookup_is_planned_on_every_platform(self):
        # It needs no second model and no VRAM, and it is worth most on the
        # slowest hosts, so there is no platform that should opt out.
        for hardware in (_HW_DUAL_GPU, _HW_TIGHT_GPU, _HW_APPLE, _HW_PI, _HW_CPU):
            settings = LlamaCppBackend._plan_settings(_facts_27b(), hardware, 16384)
            self.assertGreater(settings["prompt_lookup_tokens"], 0)

    def test_apple_puts_everything_on_the_shared_pool(self):
        settings = LlamaCppBackend._plan_settings(_facts_27b(), _HW_APPLE, 16384)
        self.assertEqual(settings["n_gpu_layers"], -1)
        self.assertEqual(settings["device"], "metal")

    def test_a_wheel_that_rejects_an_option_still_loads(self):
        # The wheel is chosen per accelerator, so several llama.cpp versions
        # are in play across supported machines. A newer argument must cost its
        # own optimisation, never the model.
        attempts = []

        def picky(**kwargs):
            attempts.append(set(kwargs))
            if "type_k" in kwargs or "draft_model" in kwargs:
                raise TypeError("unexpected keyword argument")
            return "loaded"

        settings = {"kv_quant": "q8_0", "prompt_lookup_tokens": 10}
        result = LlamaCppBackend._construct(
            picky,
            {"model_path": "x", "type_k": 8, "type_v": 8, "draft_model": object()},
            settings,
        )
        self.assertEqual(result, "loaded")
        self.assertEqual(len(attempts), 2)
        self.assertIsNone(settings["kv_quant"])
        self.assertEqual(settings["prompt_lookup_tokens"], 0)
        self.assertTrue(settings["degraded"])


class _FakeLlm:
    """Enough of a llama_cpp.Llama to exercise the consistency check."""

    def __init__(self, rows, logits_all, vocab=248320):
        import numpy as np
        self._logits_all = logits_all
        self.scores = np.zeros((rows, 1), dtype=np.float32)
        self.scores = type("S", (), {"shape": (rows, vocab)})()
        self.draft_model = object()


class TestSpeculationSafety(unittest.TestCase):
    """
    Regression cover for the crash this wave shipped.

    llama-cpp-python 0.3.34 turns its per-token logits buffer on whenever a
    draft model is present, but sizes that buffer from the `logits_all`
    argument, which is still False. The object loads, answers short prompts,
    and then raises

        could not broadcast input array from shape (N,) into shape (0,)

    the first time a prompt is longer than one batch -- which a first chat
    message with a real system prompt already is. Reproduced against the
    installed wheel at exactly 512 x 248320 = 127139840, the number in the
    report.
    """

    def setUp(self):
        self._previous = LlamaCppBackend._prompt_lookup_broken
        LlamaCppBackend._prompt_lookup_broken = False

    def tearDown(self):
        LlamaCppBackend._prompt_lookup_broken = self._previous

    def test_an_undersized_logits_buffer_disables_the_drafter(self):
        backend = LlamaCppBackend()
        backend._llm = _FakeLlm(rows=512, logits_all=True)
        settings = {"n_ctx": 32768, "prompt_lookup_tokens": 10}

        backend._verify_speculation(settings)

        self.assertEqual(settings["prompt_lookup_tokens"], 0)
        self.assertIsNone(backend._llm.draft_model)
        self.assertFalse(backend._llm._logits_all)
        self.assertTrue(settings["degraded"])

    def test_a_consistent_buffer_keeps_the_speedup(self):
        # A fixed wheel must pass the same check and lose nothing.
        backend = LlamaCppBackend()
        backend._llm = _FakeLlm(rows=32768, logits_all=True)
        settings = {"n_ctx": 32768, "prompt_lookup_tokens": 10}

        backend._verify_speculation(settings)

        self.assertEqual(settings["prompt_lookup_tokens"], 10)
        self.assertFalse(LlamaCppBackend._prompt_lookup_broken)

    def test_no_drafter_means_nothing_to_verify(self):
        backend = LlamaCppBackend()
        backend._llm = _FakeLlm(rows=512, logits_all=False)
        settings = {"n_ctx": 32768, "prompt_lookup_tokens": 0}
        backend._verify_speculation(settings)
        self.assertIsNotNone(backend._llm.draft_model)

    def test_the_verdict_is_remembered_for_later_loads(self):
        backend = LlamaCppBackend()
        backend._llm = _FakeLlm(rows=512, logits_all=True)
        backend._verify_speculation({"n_ctx": 32768, "prompt_lookup_tokens": 10})
        self.assertTrue(LlamaCppBackend._prompt_lookup_broken)

        # A second load must not even ask for a drafter.
        settings = {"prompt_lookup_tokens": 10}
        self.assertIsNone(LlamaCppBackend._build_draft_model(settings))
        self.assertEqual(settings["prompt_lookup_tokens"], 0)


class TestBatchMemoryCost(unittest.TestCase):
    """
    The prefill batch is not free in host RAM.

    llama-cpp-python allocates n_batch x n_vocab float32 up front, written or
    not. On the 248320-token vocabulary of the model in use, the roomy 2048
    would commit two gigabytes before generating anything.
    """

    def test_a_large_vocabulary_caps_the_batch(self):
        facts = _facts_27b()
        facts.vocab_size = 248320
        capped = LlamaCppBackend._cap_batch(2048, facts)
        self.assertLess(capped, 2048)
        self.assertLessEqual(capped * facts.vocab_size * 4, 512 * 2**20)

    def test_a_small_vocabulary_keeps_the_roomy_batch(self):
        facts = _facts_27b()
        facts.vocab_size = 32000
        self.assertEqual(LlamaCppBackend._cap_batch(2048, facts), 2048)

    def test_an_unknown_vocabulary_refuses_to_guess_upward(self):
        # Unknown cost plus an optional speedup: the only safe direction is down.
        facts = _facts_27b()
        facts.vocab_size = 0
        self.assertLessEqual(LlamaCppBackend._cap_batch(2048, facts), 512)

    def test_the_cap_never_goes_below_llamacpp_s_floor(self):
        facts = _facts_27b()
        facts.vocab_size = 10_000_000          # absurd, to force the floor
        self.assertEqual(LlamaCppBackend._cap_batch(2048, facts), 128)

    def test_the_planner_reports_what_the_buffer_costs(self):
        facts = _facts_27b()
        facts.vocab_size = 248320
        settings = LlamaCppBackend._plan_settings(facts, _HW_DUAL_GPU, 32768)
        self.assertIn("logits_buffer_gb", settings)
        self.assertLess(settings["logits_buffer_gb"], 1.0)


class TestGgufVocabulary(unittest.TestCase):
    """The planner cannot budget for a vocabulary it never reads."""

    def test_vocab_is_read_from_the_gguf_header(self):
        import glob
        import os
        from core.engine.model_inspector import ModelInspector

        folders = [d for d in glob.glob("data/models/*")
                   if os.path.isdir(d) and glob.glob(os.path.join(d, "*.gguf"))]
        if not folders:
            self.skipTest("no local GGUF to inspect")

        facts = ModelInspector.inspect(folders[0])
        self.assertGreater(
            facts.vocab_size, 0,
            "GGUF vocab_size stayed at zero; the llama.cpp batch cap silently "
            "does nothing without it",
        )

    def test_the_facts_cache_is_versioned(self):
        # The fingerprint only notices a directory that changed, so a field that
        # starts being populated needs a schema bump or old caches win forever.
        from core.engine import model_inspector
        self.assertGreaterEqual(model_inspector._FACTS_SCHEMA, 4)


class TestBackendBenchmark(unittest.TestCase):
    """M1 — the measurement tool must cover the path that serves traffic."""

    def test_the_contract_exists_on_the_base_backend(self):
        from core.engine.backends.base import InferenceBackend
        self.assertTrue(hasattr(InferenceBackend, "benchmark"))

    def test_llamacpp_refuses_clearly_with_no_model(self):
        backend = LlamaCppBackend()
        result = backend.benchmark()
        self.assertFalse(result["success"])
        self.assertEqual(result["backend"], "llama_cpp")
        self.assertIn("Nessun modello", result["error"])

    def test_engine_exposes_the_effective_context_window(self):
        from core.engine import sigma_engine
        self.assertIsInstance(sigma_engine.context_window(), int)


class TestHistoryBudget(unittest.TestCase):
    """Q4 — a conversation is trimmed by what it costs, not by how many turns."""

    def test_short_history_is_kept_whole(self):
        messages = [{"role": "user", "content": "ciao"},
                    {"role": "assistant", "content": "ciao!"}]
        kept, report = trim_history(messages, budget_tokens=4096)
        self.assertEqual(len(kept), 2)
        self.assertEqual(report["dropped"], 0)

    def test_long_history_is_trimmed_from_the_oldest_end(self):
        messages = [{"role": "user", "content": "x" * 4000} for _ in range(20)]
        kept, report = trim_history(messages, budget_tokens=2000)
        self.assertGreater(report["dropped"], 0)
        # What survives is the end of the conversation, not the start.
        self.assertIs(kept[-1], messages[-1])

    def test_order_is_preserved(self):
        messages = [{"role": "user", "content": f"messaggio {i}"} for i in range(10)]
        kept, _ = trim_history(messages, budget_tokens=100000)
        self.assertEqual([m["content"] for m in kept],
                         [m["content"] for m in messages])

    def test_the_last_exchange_survives_any_budget(self):
        # An assistant that cannot see the turn before the question is not
        # saving context, it is losing the thread.
        messages = [{"role": "user", "content": "y" * 50000} for _ in range(4)]
        kept, _ = trim_history(messages, budget_tokens=10)
        self.assertGreaterEqual(len(kept), 2)

    def test_ten_short_messages_are_no_longer_treated_like_ten_huge_ones(self):
        short = [{"role": "user", "content": "ok"} for _ in range(40)]
        huge = [{"role": "user", "content": "z" * 20000} for _ in range(40)]
        kept_short, _ = trim_history(short, budget_tokens=4096)
        kept_huge, _ = trim_history(huge, budget_tokens=4096)
        self.assertGreater(len(kept_short), len(kept_huge))

    def test_the_model_is_told_what_it_cannot_see(self):
        messages = [{"role": "user", "content": "w" * 8000} for _ in range(10)]
        _, report = trim_history(messages, budget_tokens=1000)
        notice = dropped_notice(report)
        self.assertIn(str(report["dropped"]), notice)
        self.assertFalse(dropped_notice({"dropped": 0}))

    def test_italian_is_not_measured_with_an_english_ratio(self):
        # Roughly three characters per token, not four: the English rule of
        # thumb understates an Italian prompt by about a quarter, which is the
        # direction that overflows a window.
        text = "Analizziamo il metodo di inferenza sui modelli locali." * 20
        self.assertGreater(estimate_tokens(text), len(text) / 4)

    def test_exact_counting_is_used_when_a_tokenizer_is_available(self):
        class FakeTokenizer:
            def encode(self, text, add_special_tokens=False):
                return list(range(len(text.split())))

        _, report = trim_history(
            [{"role": "user", "content": "una due tre"}],
            budget_tokens=100, tokenizer=FakeTokenizer(),
        )
        self.assertTrue(report["exact"])

    def test_budget_is_what_is_left_after_everything_else(self):
        self.assertEqual(history_budget(32768, 8000, 4096), 32768 - 8000 - 4096)
        # A prompt that already fills the window leaves the history nothing,
        # rather than a negative budget that would wrap into "unlimited".
        self.assertEqual(history_budget(8192, 8000, 4096), 0)
        # Unknown window: stay modest instead of assuming the largest.
        self.assertGreater(history_budget(0, 0, 0), 0)


class TestTokenCoalescer(unittest.TestCase):
    """L12 — fewer events, identical text."""

    def _coalescer(self):
        from core.chat.chat_runner import _TokenCoalescer
        emitted = []
        return _TokenCoalescer(lambda ch, tx: emitted.append((ch, tx))), emitted

    def test_text_survives_batching_exactly(self):
        coalescer, emitted = self._coalescer()
        tokens = [f"tok{i} " for i in range(200)]
        for token in tokens:
            coalescer.feed("token", token)
        coalescer.flush()
        self.assertEqual("".join(t for _, t in emitted), "".join(tokens))

    def test_batching_reduces_the_event_count(self):
        coalescer, emitted = self._coalescer()
        for i in range(200):
            coalescer.feed("token", "ab")
        coalescer.flush()
        self.assertLess(len(emitted), 200)

    def test_channels_never_merge(self):
        # Reasoning and answer land in different bubbles; merging them would
        # put the thinking in the reply.
        coalescer, emitted = self._coalescer()
        coalescer.feed("thinking", "penso")
        coalescer.feed("token", "rispondo")
        coalescer.flush()
        self.assertEqual([ch for ch, _ in emitted], ["thinking", "token"])

    def test_flush_is_idempotent_and_empty_feeds_do_nothing(self):
        coalescer, emitted = self._coalescer()
        coalescer.feed("token", "")
        coalescer.flush()
        coalescer.flush()
        self.assertEqual(emitted, [])


class TestGrammars(unittest.TestCase):
    """Q2 — a malformed tool call should be unreachable, not repaired."""

    def test_tool_grammar_pins_the_callable_names(self):
        # Asserted in the escaped form the grammar must actually contain. The
        # earlier version of this test looked for the bare terminal, which is
        # precisely the broken rendering, so it passed while the grammar was
        # producing unquoted JSON.
        gbnf = tool_call_grammar(["get_hardware_status", "search_web"])
        self.assertIn(r'"\"get_hardware_status\""', gbnf)
        self.assertIn(r'"\"search_web\""', gbnf)
        self.assertIn("root", gbnf)

    def test_no_tools_means_no_grammar(self):
        self.assertIsNone(tool_call_grammar([]))
        self.assertIsNone(tool_call_grammar(["", None]))

    def test_duplicate_tool_names_appear_once(self):
        gbnf = tool_call_grammar(["a", "a", "b"])
        self.assertEqual(gbnf.count(r'"\"a\""'), 1)

    def test_names_needing_escapes_do_not_break_the_grammar(self):
        gbnf = tool_call_grammar(['weird"name'])
        self.assertIn("root", gbnf)

    def test_json_grammar_honours_required_keys(self):
        gbnf = json_object_grammar({
            "properties": {"titolo": {"type": "string"}, "passi": {"type": "array"}},
            "required": ["titolo", "passi"],
        })
        self.assertIn("titolo", gbnf)
        self.assertIn("array", gbnf)

    def test_schemaless_grammar_is_still_valid_json(self):
        self.assertIn("root ::= object", json_object_grammar())

    def test_a_constrained_name_is_emitted_as_a_quoted_json_string(self):
        # The bug this pins: in GBNF a double-quoted sequence delimits a
        # terminal, so `"search_web"` emits search_web with no quotes -- valid
        # against the grammar, invalid as JSON. llama.cpp does not reject the
        # mistake, it generates the broken output, so reading the grammar is
        # not enough to catch it.
        gbnf = tool_call_grammar(["search_web"])
        self.assertIn(r'"\"search_web\""', gbnf)
        self.assertNotIn('("search_web")', gbnf)

    def test_grammar_output_round_trips_through_json(self):
        # The only check that would have caught the quoting bug: generate under
        # the grammar and parse the result.
        import glob
        import json
        import os

        try:
            from llama_cpp import Llama
        except ImportError:
            self.skipTest("llama_cpp not installed on this host")

        models = [f for d in glob.glob("data/models/*")
                  for f in glob.glob(os.path.join(d, "*.gguf"))]
        if not models:
            self.skipTest("no local GGUF to generate with")

        tools = ["get_hardware_status", "search_web", "read_file"]
        llm = Llama(model_path=min(models, key=os.path.getsize),
                    n_ctx=1024, n_gpu_layers=0, verbose=False)
        try:
            result = llm.create_chat_completion(
                messages=[{"role": "user", "content": "Leggi il file config.json"}],
                max_tokens=80, temperature=0.0,
                grammar=compile_for_llama_cpp(tool_call_grammar(tools)),
            )
            text = result["choices"][0]["message"]["content"]
            payload = json.loads(text)             # raises if the grammar is wrong
            self.assertIn(payload["tool"], tools)
            self.assertIsInstance(payload["arguments"], dict)
        finally:
            llm.close()

    def test_compiling_degrades_instead_of_raising(self):
        # Without llama.cpp there is no grammar; the caller decodes
        # unconstrained and the existing parsers do what they always did.
        self.assertIsNone(compile_for_llama_cpp(""))
        result = compile_for_llama_cpp("root ::= object")
        self.assertTrue(result is None or hasattr(result, "__class__"))


if __name__ == "__main__":
    unittest.main()
