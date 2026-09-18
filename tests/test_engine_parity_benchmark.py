# ==============================================================================
# tests/test_engine_parity_benchmark.py — Test e Verifica Parità Benchmark Rust vs Py
# Sigma Studio v8 — Kernel Test Suite
# ==============================================================================
import unittest
from benchmarks.engine_vs_rust_benchmark import (
    bench_prefix_cache_lookup,
    bench_grammar_validation,
    bench_agent_event_bus,
)
from core.engine.backends.sigmarust_backend import SigmaRustBackend, _DEFAULT_RUST_URL, _is_rust_kernel_online


class TestEngineParityBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.online = _is_rust_kernel_online()

    def test_radix_cache_speedup(self):
        res = bench_prefix_cache_lookup(iterations=100)
        self.assertGreater(res["speedup"], 1.0)
        self.assertLess(res["rust_internal_us"], res["python_us"])

    def test_grammar_validation_parity(self):
        if not self.online:
            self.skipTest("Micro-kernel Rust non online su porta 8090")
        res = bench_grammar_validation(iterations=20)
        self.assertGreaterEqual(res["speedup"], 0.8)

    def test_agent_event_bus_throughput(self):
        if not self.online:
            self.skipTest("Micro-kernel Rust non online su porta 8090")
        res = bench_agent_event_bus(iterations=20)
        self.assertGreaterEqual(res["speedup"], 1.0)


if __name__ == "__main__":
    unittest.main()
