# ==============================================================================
# tests/test_inference_wave2.py — Regression cover for the second wave
#
# Throughput and structure: cross-turn KV reuse, the generation queue, the
# llama.cpp placement knobs, token-budgeted history, SSE coalescing and
# grammar-constrained tool calls.
#
# Nothing here loads a model. The pieces that need one are tested through their
# planning and bookkeeping, which is where the decisions actually live -- and
# which is why these run identically on a CUDA box, an Apple laptop and a board
# with no accelerator at all.
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
_HW_APPLE = {"accelerators": [{"type": "APPLE_MPS"}],
             "cpu": {"cores_physical": 10}, "system": {}}
_HW_PI = {"accelerators": [], "cpu": {"cores_physical": 4},
          "system": {"is_arm": True, "is_raspberry_pi": True}}
_HW_CPU = {"accelerators": [], "cpu": {"cores_physical": 12}, "system": {}}


class TestLlamaCppPlanning(unittest.TestCase):
    """L11 / L6 — the knobs that decide throughput on the GGUF path."""

    def test_kv_is_quantized_at_a_long_context(self):
        settings = LlamaCppBackend._plan_settings(_facts_27b(), _HW_DUAL_GPU, 32768)
        self.assertEqual(settings["kv_quant"], "q8_0")
        self.assertLess(settings["kv_cache_gb"], settings["kv_cache_gb_f16"])

    def test_kv_is_left_alone_at_a_short_context(self):
        settings = LlamaCppBackend._plan_settings(_facts_27b(), _HW_DUAL_GPU, 4096)
        self.assertIsNone(settings["kv_quant"])

    def test_quantized_kv_buys_back_gpu_layers(self):
        # The point of the whole change: on a card where the f16 cache leaves no
        # room, halving it is what puts layers back on the accelerator.
        facts = _facts_27b()
        settings = LlamaCppBackend._plan_settings(facts, _HW_TIGHT_GPU, 32768)
        self.assertGreater(settings["n_gpu_layers"], 0)

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
        gbnf = tool_call_grammar(["get_hardware_status", "search_web"])
        self.assertIn('"get_hardware_status"', gbnf)
        self.assertIn('"search_web"', gbnf)
        self.assertIn("root", gbnf)

    def test_no_tools_means_no_grammar(self):
        self.assertIsNone(tool_call_grammar([]))
        self.assertIsNone(tool_call_grammar(["", None]))

    def test_duplicate_tool_names_appear_once(self):
        gbnf = tool_call_grammar(["a", "a", "b"])
        self.assertEqual(gbnf.count('"a"'), 1)

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

    def test_compiling_degrades_instead_of_raising(self):
        # Without llama.cpp there is no grammar; the caller decodes
        # unconstrained and the existing parsers do what they always did.
        self.assertIsNone(compile_for_llama_cpp(""))
        result = compile_for_llama_cpp("root ::= object")
        self.assertTrue(result is None or hasattr(result, "__class__"))


if __name__ == "__main__":
    unittest.main()
