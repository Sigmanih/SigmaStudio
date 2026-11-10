# ==============================================================================
# tests/test_engine_parity_benchmark.py — Test e Verifica Parità Benchmark Rust vs Py
# Sigma Studio v8 — Kernel Test Suite
# ==============================================================================
import unittest
from unittest.mock import patch
from tools.benchmarks.engine_vs_rust_benchmark import (
    bench_prefix_cache_lookup,
    bench_grammar_validation,
    bench_agent_event_bus,
)


class TestEngineParityBenchmark(unittest.TestCase):
    def test_radix_cache_speedup(self):
        with patch("tools.benchmarks.engine_vs_rust_benchmark._post", return_value={"matched_tokens": 512}) as post:
            res = bench_prefix_cache_lookup(iterations=100)
        self.assertEqual(post.call_count, 101)
        self.assertGreater(res["python_us"], 0)
        self.assertIsNone(res["rust_internal_us"])
        if res["rust_measured"]:
            self.assertTrue(res["parity"])
            self.assertGreater(res["rust_roundtrip_us"], 0)
        else:
            self.assertIsNone(res["speedup"])

    def test_grammar_validation_parity(self):
        with patch("tools.benchmarks.engine_vs_rust_benchmark._post", return_value={"result": {"valid": True}}) as post:
            res = bench_grammar_validation(iterations=20)
        self.assertEqual(post.call_count, 20)
        self.assertTrue(res["rust_measured"], res["error"])
        self.assertTrue(res["parity"])

    def test_agent_event_bus_throughput(self):
        with patch("tools.benchmarks.engine_vs_rust_benchmark._post", return_value={"success": True}) as post:
            res = bench_agent_event_bus(iterations=20)
        self.assertEqual(post.call_count, 20)
        self.assertTrue(res["rust_measured"], res["error"])
        self.assertTrue(res["parity"])

    def test_offline_non_produce_speedup(self):
        with patch("tools.benchmarks.engine_vs_rust_benchmark._post", side_effect=OSError("offline")):
            for benchmark in (bench_prefix_cache_lookup, bench_grammar_validation, bench_agent_event_bus):
                result = benchmark(iterations=3)
                self.assertFalse(result["rust_measured"])
                self.assertIsNone(result["speedup"])
                self.assertIsNone(result["parity"])


if __name__ == "__main__":
    unittest.main()
