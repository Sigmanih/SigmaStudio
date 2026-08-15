# ==============================================================================
# tests/test_sigma_engine.py — Test Suite for Universal SigmaEngine
# Tests: Hardware Probe, Weight Saliency Profiler, Multi-Drive Sharding, Engine Stream
# ==============================================================================
import unittest
import os
import shutil
import tempfile
from core.engine.hardware_probe import UniversalHardwareProbe
from core.engine.weight_profiler import WeightSaliencyProfiler
from core.engine.disk_streamer import MultiDriveShardedStreamer
from core.engine.unified_runtime import UniversalSigmaEngine


class TestSigmaEngine(unittest.TestCase):
    def test_hardware_probe(self):
        """Verify universal hardware probe returns all expected system metrics."""
        probe = UniversalHardwareProbe.probe_all()
        self.assertIn("system", probe)
        self.assertIn("cpu", probe)
        self.assertIn("ram", probe)
        self.assertIn("accelerators", probe)
        self.assertIn("storage_drives", probe)
        self.assertIn("recommended_tiering", probe)
        self.assertGreater(probe["ram"]["total_gb"], 0)

    def test_weight_saliency_and_partitioning(self):
        """Verify layer saliency calculation and 4-tier memory distribution."""
        partition = WeightSaliencyProfiler.partition_model_layers(
            total_layers=32,
            vram_primary_gb=8.0,
            vram_secondary_gb=0.0,
            system_ram_gb=16.0,
            model_size_gb=8.0,
            is_moe=False
        )
        self.assertEqual(partition["total_layers"], 32)
        total_allocated = (
            partition["tier0_primary_vram"]["count"] +
            partition["tier1_secondary_vram"]["count"] +
            partition["tier2_host_ram"]["count"] +
            partition["tier3_disk_shards"]["count"]
        )
        self.assertEqual(total_allocated, 32)
        self.assertGreater(partition["tier0_primary_vram"]["count"], 0)

    def test_multi_drive_sharded_streaming(self):
        """Verify striping tensor bytes across multiple drives and parallel reconstruction."""
        tmp_dir1 = tempfile.mkdtemp(prefix="sigma_drive1_")
        tmp_dir2 = tempfile.mkdtemp(prefix="sigma_drive2_")
        try:
            streamer = MultiDriveShardedStreamer(target_drives=[tmp_dir1, tmp_dir2], chunk_size_mb=1)
            
            # Generate 2.5 MB dummy layer weights
            dummy_weights = b"A" * (2500 * 1024)
            shards = streamer.register_sharded_layer(layer_index=5, layer_bytes=dummy_weights)
            
            self.assertGreaterEqual(len(shards), 3)
            
            # Read back in parallel
            assembled = streamer.fetch_layer_parallel(layer_index=5)
            self.assertEqual(len(assembled), len(dummy_weights))
            self.assertEqual(assembled, dummy_weights)
        finally:
            shutil.rmtree(tmp_dir1, ignore_errors=True)
            shutil.rmtree(tmp_dir2, ignore_errors=True)

    def test_engine_streaming_generation(self):
        """Verify token generation stream with TTFT and token speed calculation."""
        engine = UniversalSigmaEngine()
        status = engine.get_status()
        self.assertIn("active_backend", status)
        
        tokens = list(engine.generate_stream("Test prompt"))
        self.assertGreater(len(tokens), 0)
        self.assertIsNotNone(tokens[0].get("ttft_ms"))
        self.assertTrue(tokens[-1]["done"])

    def test_moe_expert_cache(self):
        """Verify predictive MoE LRU cache tracking and hit-rate."""
        from core.engine.moe_expert_cache import MoEExpertCache
        cache = MoEExpertCache(max_vram_experts=4)
        
        # Cold miss
        self.assertFalse(cache.record_activation(0, 1))
        # Hot hit
        self.assertTrue(cache.record_activation(0, 1))
        
        stats = cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["vram_hit_rate_percent"], 50.0)

    def test_speculative_decoding(self):
        """Verify candidate acceptance logic and speedup calculation."""
        from core.engine.speculative import SpeculativeDecodingEngine
        spec = SpeculativeDecodingEngine(gamma_lookahead=4)
        accepted, count = spec.speculate_and_verify(
            draft_tokens=["il", "modello", "MoE", "funziona"],
            target_verification_probs=[0.98, 0.95, 0.92, 0.40]
        )
        self.assertEqual(count, 3)
        self.assertEqual(accepted, ["il", "modello", "MoE"])
        stats = spec.get_stats()
        self.assertGreater(stats["total_accepted"], 0)


if __name__ == "__main__":
    unittest.main()

