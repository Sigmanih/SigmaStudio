# ==============================================================================
# tests/test_engine_portability.py — Running, or refusing clearly, everywhere
#
# Two failures from the same root cause prompted these: a 27B safetensors that
# loaded on a workstation and then died allocating 230MB mid-answer, and the
# same checkpoint on a Raspberry Pi that did not fail so much as stop
# responding. Both are the transformers path being the only path a safetensors
# model can take, with a memory estimate that counted weights and KV but not
# the working set of a forward pass.
#
# The tests are hardware-independent by construction: every scenario is a
# hardware profile passed in, so the CPU-only board and the dual-GPU desktop are
# both exercised on whatever machine happens to run the suite.
# ==============================================================================
import unittest

from core.engine.memory_planner import MemoryPlanner
from core.engine.model_inspector import ModelFacts


def _facts_27b(total_gb=51.7):
    facts = ModelFacts(
        path="/fake/qwen3-27b", name="Qwen--Qwen3.8-27B", model_type="qwen35",
        architectures=["Qwen35ForCausalLM"], weight_format="safetensors",
        num_hidden_layers=64, hidden_size=5120, head_dim=256,
        num_attention_heads=40, num_key_value_heads=4, vocab_size=248320,
        max_position_embeddings=262144,
    )
    facts.total_bytes = int(total_gb * 2**30)
    facts.param_count = 27_800_000_000
    facts.quantizable_params = 25_233_780_736
    facts.resident_params = 2_547_647_216
    return facts


_PI = {"accelerators": [], "ram": {"available_gb": 6.0},
       "cpu": {"cores_physical": 4}, "system": {"is_raspberry_pi": True, "is_arm": True}}
_LAPTOP_CPU = {"accelerators": [], "ram": {"available_gb": 28.0},
               "cpu": {"cores_physical": 8}, "system": {}}
_DESKTOP = {
    "accelerators": [
        {"type": "NVIDIA_CUDA", "free_vram_gb": 14.68, "total_vram_gb": 15.92,
         "multi_processor_count": 84, "device_id": 0},
        {"type": "NVIDIA_CUDA", "free_vram_gb": 6.87, "total_vram_gb": 7.96,
         "multi_processor_count": 68, "device_id": 1},
    ],
    "ram": {"available_gb": 30.8}, "cpu": {"cores_physical": 12}, "system": {},
}


class TestActivationReserve(unittest.TestCase):
    """
    The term the planner did not have.

    Weights and KV are static and were both counted. The working set of a
    prefill step is neither, and a flat gigabyte does not describe it: it grows
    with the tokens pushed through at once and with the width of the model.
    """

    def test_the_reserve_grows_with_context(self):
        facts = _facts_27b()
        short = MemoryPlanner.activation_reserve_gb(facts, 4096, 14.68)
        long = MemoryPlanner.activation_reserve_gb(facts, 32768, 14.68)
        self.assertGreater(long, short)

    def test_the_reserve_grows_with_model_width(self):
        narrow = _facts_27b()
        narrow.hidden_size = 2048
        wide = _facts_27b()
        wide.hidden_size = 8192
        self.assertGreater(
            MemoryPlanner.activation_reserve_gb(wide, 32768, 14.68),
            MemoryPlanner.activation_reserve_gb(narrow, 32768, 14.68),
        )

    def test_the_reserve_never_eats_the_whole_card(self):
        facts = _facts_27b()
        absurd = MemoryPlanner.activation_reserve_gb(facts, 1_000_000, 14.68)
        self.assertLess(absurd, 14.68 * 0.5)

    def test_missing_facts_fall_back_to_the_floor(self):
        self.assertGreater(MemoryPlanner.activation_reserve_gb(None, 32768, 14.0), 0)

    def test_the_planner_backs_off_the_context_instead_of_overcommitting(self):
        # The reported case: 16384 tokens looked like a +1.08GB fit and OOMed.
        # Counting the prefill working set has to reduce the context it accepts.
        facts = _facts_27b()
        plan = MemoryPlanner.build_plan(facts, _DESKTOP, context_tokens=32768)
        self.assertLess(plan.context_tokens, 32768)
        self.assertGreater(plan.vram_headroom_gb, 1.0)


class TestPlatformRefusal(unittest.TestCase):
    """
    A safetensors checkpoint never reaches the backend registry, so on a machine
    where transformers cannot run it there is nothing to fall back to. Saying so
    is the difference between "unsupported platform" and "it hangs".
    """

    def _verdict(self, facts, hardware):
        from core.engine import sigma_engine
        plan = MemoryPlanner.build_plan(facts, hardware, context_tokens=8192)
        return sigma_engine._transformers_infeasibility(facts, plan, hardware)

    def test_a_pi_is_refused_with_a_reason(self):
        verdict = self._verdict(_facts_27b(), _PI)
        self.assertIsNotNone(verdict, "a 27B must not be attempted on 6GB of RAM")
        self.assertIn("GGUF", verdict, "the refusal has to name the format that works")

    def test_a_cpu_laptop_too_small_is_refused(self):
        self.assertIsNotNone(self._verdict(_facts_27b(), _LAPTOP_CPU))

    def test_a_small_model_on_a_pi_is_allowed(self):
        # The check must not become a blanket ban on CPU inference.
        small = _facts_27b(total_gb=1.2)
        small.param_count = 600_000_000
        small.quantizable_params = 500_000_000
        small.resident_params = 100_000_000
        self.assertIsNone(self._verdict(small, _PI))

    def test_the_workstation_is_allowed(self):
        self.assertIsNone(self._verdict(_facts_27b(), _DESKTOP))


class TestOutOfMemoryHandling(unittest.TestCase):
    """An OOM is a placement one allocation too optimistic, not a stack trace."""

    def test_oom_is_recognised_across_backends(self):
        from core.engine import sigma_engine

        class CudaOOM(Exception):
            pass
        CudaOOM.__name__ = "OutOfMemoryError"

        self.assertTrue(sigma_engine._is_out_of_memory(CudaOOM("CUDA out of memory")))
        # ROCm and MPS raise a plain RuntimeError with the same meaning.
        self.assertTrue(sigma_engine._is_out_of_memory(
            RuntimeError("HIP out of memory. Tried to allocate 230.00 MiB")))
        self.assertFalse(sigma_engine._is_out_of_memory(ValueError("shape mismatch")))

    def test_the_message_names_remedies_not_just_the_error(self):
        from core.engine import sigma_engine

        class CudaOOM(Exception):
            pass
        CudaOOM.__name__ = "OutOfMemoryError"

        text = sigma_engine._explain_generation_failure(CudaOOM("CUDA out of memory"))
        self.assertIn("VRAM esaurita", text)
        self.assertIn("GGUF", text)
        self.assertIn("Rimedi", text)

    def test_an_unrelated_failure_is_reported_plainly(self):
        from core.engine import sigma_engine
        text = sigma_engine._explain_generation_failure(ValueError("boom"))
        self.assertIn("ValueError", text)
        self.assertNotIn("Rimedi", text)


class TestTieringView(unittest.TestCase):
    """
    The settings panel used to show a saliency heuristic over a hypothetical
    32-layer, 8GB model -- the numbers were hardcoded in the frontend call and
    described nothing that had ever been loaded.
    """

    def test_tiers_are_derived_from_the_real_plan(self):
        from core.engine.engine_router import _tiering_view

        facts = _facts_27b()
        plan = MemoryPlanner.build_plan(facts, _DESKTOP, context_tokens=8192)
        view = _tiering_view({"plan": plan.to_dict(), "facts": facts.to_dict()})

        self.assertEqual(view["total_layers"], facts.num_hidden_layers)
        self.assertEqual(view["quantization"], plan.quantization)
        placed = sum(
            view[t]["count"] for t in
            ("tier0_primary_vram", "tier1_secondary_vram",
             "tier2_host_ram", "tier3_disk_shards")
        )
        self.assertLessEqual(placed, facts.num_hidden_layers)
        self.assertGreater(view["tier0_primary_vram"]["count"], 0)

    def test_an_empty_plan_does_not_explode(self):
        from core.engine.engine_router import _tiering_view
        view = _tiering_view({})
        self.assertEqual(view["total_layers"], 0)


class TestRemovedSubsystems(unittest.TestCase):
    """
    Three accelerations were constructed at start-up, reported as active in the
    status panel, and never called from any code path. A fourth, the saliency
    profiler, decided a tiering that no loader ever read.
    """

    def test_they_are_gone(self):
        import importlib
        for name in ("core.engine.speculative", "core.engine.moe_expert_cache",
                     "core.engine.disk_streamer", "core.engine.weight_profiler"):
            with self.assertRaises(ImportError, msg=f"{name} still importable"):
                importlib.import_module(name)

    def test_status_reports_only_what_runs(self):
        from core.engine import sigma_engine
        optimizations = sigma_engine.get_status()["optimizations"]
        self.assertNotIn("moe_expert_cache_active", optimizations)
        # What replaced it is read from the live backend, not from a constructor.
        self.assertIn("speculative", optimizations)
        self.assertIn("prefix_kv_reuse", optimizations)


if __name__ == "__main__":
    unittest.main()
