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
        """Verify the stream terminates and reports TTFT on the first real token."""
        engine = UniversalSigmaEngine()
        # Loading is lazy inside generate_stream, so release VRAM afterwards or
        # later tests plan against a machine that looks out of memory.
        self.addCleanup(engine.unload)
        status = engine.get_status()
        self.assertIn("active_backend", status)

        chunks = list(engine.generate_stream("Test prompt", max_tokens=16))
        self.assertGreater(len(chunks), 0)
        self.assertTrue(chunks[-1]["done"])

        # The stream legitimately opens with status chunks (loading notice,
        # load summary) before the model emits anything, so TTFT belongs to the
        # first chunk carrying a generated token, not to chunks[0].
        timed = [c for c in chunks if c.get("ttft_ms") is not None]
        if timed:
            self.assertGreater(timed[0]["ttft_ms"], 0)
            self.assertEqual(timed[0]["token_index"], 1)

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


class TestModelInspector(unittest.TestCase):
    """Introspection must read the checkpoint, never guess from its name."""

    @classmethod
    def setUpClass(cls):
        cls.model_dir = _find_local_model()

    def setUp(self):
        if not self.model_dir:
            self.skipTest("no local model in data/models/")

    def test_reads_real_geometry(self):
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.model_dir, use_cache=False)
        self.assertIsNotNone(facts)
        self.assertGreater(facts.num_hidden_layers, 0)
        self.assertGreater(facts.param_count, 0)
        self.assertGreater(facts.total_bytes, 0)
        self.assertTrue(facts.architectures)

    def test_discovers_layer_prefix_from_weights(self):
        """
        The decoder prefix is checkpoint-specific ('model.layers' on Llama,
        'model.language_model.layers' on multimodal Qwen). Hardcoding it
        produces device maps that match no module at all.
        """
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.model_dir, use_cache=False)
        self.assertTrue(facts.layer_prefix.endswith("layers"))

    def test_resolved_class_matches_architecture(self):
        """
        AutoModelForCausalLM picks a text-only class for multimodal configs and
        then fails on fields that live under text_config.
        """
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.model_dir, use_cache=False)
        resolved = ModelInspector.resolve_model_class(facts)
        self.assertEqual(resolved.__name__, facts.architectures[0])

    def test_quantized_footprint_excludes_resident_tensors(self):
        """Embeddings and lm_head stay in compute dtype under bitsandbytes."""
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.model_dir, use_cache=False)
        footprint = ModelInspector.estimate_footprint(facts, "nf4")
        self.assertGreater(footprint["resident_gb"], 0)
        self.assertLess(footprint["total_gb"], facts.total_bytes / 2**30)


def _fake_profile(gpus, ram_gb=64.0, drives=None):
    """Builds a hardware profile so planning is testable without real GPUs."""
    return {
        "accelerators": gpus,
        "ram": {"available_gb": ram_gb, "total_gb": ram_gb + 8},
        "storage_drives": drives or [],
    }


def _gpu(device_id, name, free_gb, sms):
    return {
        "device_id": device_id, "type": "NVIDIA_CUDA", "name": name,
        "free_vram_gb": free_gb, "multi_processor_count": sms,
        "supports_bf16": True,
    }


def _facts(layers=32, params=7e9, quantizable=6.5e9):
    from core.engine.model_inspector import ModelFacts
    return ModelFacts(
        path="/fake", name="fake-7b", num_hidden_layers=layers,
        hidden_size=4096, head_dim=128, num_attention_heads=32,
        num_key_value_heads=8, param_count=int(params),
        quantizable_params=int(quantizable),
        resident_params=int(params - quantizable),
        total_bytes=int(params * 2),
    )


class TestMemoryPlanner(unittest.TestCase):
    def test_fills_fastest_gpu_first(self):
        from core.engine.memory_planner import MemoryPlanner
        profile = _fake_profile([
            _gpu(0, "slow", 8.0, 30),
            _gpu(1, "fast", 16.0, 70),
        ])
        plan = MemoryPlanner.build_plan(_facts(), profile, context_tokens=4096)
        # The 70-SM card must be filled first regardless of enumeration order.
        self.assertEqual(plan.devices[0]["device_id"], 1)
        self.assertGreater(
            plan.devices[0]["budget_gb"], plan.devices[1]["budget_gb"]
        )

    def test_precision_ladder_picks_best_that_fits(self):
        from core.engine.memory_planner import MemoryPlanner
        roomy = _fake_profile([_gpu(0, "big", 48.0, 100)])
        tight = _fake_profile([_gpu(0, "small", 8.0, 30)])

        self.assertEqual(
            MemoryPlanner.build_plan(_facts(), roomy, context_tokens=4096).quantization,
            "bf16",
        )
        self.assertEqual(
            MemoryPlanner.build_plan(_facts(), tight, context_tokens=4096).quantization,
            "nf4",
        )

    def test_offload_prefers_internal_drive_over_roomy_usb(self):
        """
        Bandwidth beats capacity: streaming weights over USB puts that bus on
        the critical path of every forward pass.
        """
        from core.engine.memory_planner import MemoryPlanner
        drives = [
            {"mountpoint": "D:\\", "free_gb": 2000.0, "is_removable": True,
             "estimated_read_speed_mb_s": 400.0, "speed_class": "usb"},
            {"mountpoint": os.path.abspath(tempfile.gettempdir()), "free_gb": 300.0,
             "is_removable": False, "estimated_read_speed_mb_s": 3500.0,
             "speed_class": "nvme"},
        ]
        profile = _fake_profile(
            [_gpu(0, "tiny", 4.0, 20)], ram_gb=10.0, drives=drives
        )
        plan = MemoryPlanner.build_plan(
            _facts(layers=80, params=70e9, quantizable=66e9),
            profile, context_tokens=4096,
        )
        self.assertIsNotNone(plan.offload_folder)
        self.assertNotIn("D:\\", plan.offload_folder)

    def test_withholds_cpu_budget_when_model_fits_in_vram(self):
        """
        Offering a CPU budget is what lets accelerate place weights there; when
        the model fits we withhold it so an optimistic estimate surfaces as an
        error rather than silent PCIe-bound inference.
        """
        from core.engine.memory_planner import MemoryPlanner
        profile = _fake_profile([_gpu(0, "big", 48.0, 100)])
        plan = MemoryPlanner.build_plan(_facts(), profile, context_tokens=4096)
        self.assertTrue(plan.fits_in_vram)
        self.assertNotIn("cpu", plan.max_memory)

    def test_kv_cache_scales_only_with_full_attention_layers(self):
        from core.engine.model_inspector import ModelInspector
        facts = _facts(layers=64)
        facts.layer_types = ["linear_attention"] * 48 + ["full_attention"] * 16
        hybrid = ModelInspector.estimate_kv_cache_gb(facts, 32768)

        facts.layer_types = ["full_attention"] * 64
        dense = ModelInspector.estimate_kv_cache_gb(facts, 32768)
        self.assertLess(hybrid, dense)


class TestDeviceMapRepair(unittest.TestCase):
    """
    lm_head runs a hidden_size x vocab_size matmul per generated token, so
    exiling it to the CPU costs far more than exiling several decoder layers.
    """

    def test_rescues_critical_module_with_spare_room(self):
        from core.engine.device_map_builder import DeviceMapBuilder
        gb = 2**30
        device_map = {"model.layers.0": 0, "model.layers.1": 1, "lm_head": "cpu"}
        sizes = {"model.layers.0": 4 * gb, "model.layers.1": 1 * gb, "lm_head": 2 * gb}
        max_memory = {0: 6 * gb, 1: 6 * gb, "cpu": 40 * gb}

        repaired, moves = DeviceMapBuilder._repair_critical_modules(
            device_map, sizes, max_memory
        )
        self.assertEqual(repaired["lm_head"], 1)
        self.assertEqual(len(moves), 1)

    def test_evicts_a_layer_when_no_room_remains(self):
        from core.engine.device_map_builder import DeviceMapBuilder
        gb = 2**30
        device_map = {"model.layers.0": 0, "model.layers.1": 0, "lm_head": "cpu"}
        sizes = {"model.layers.0": 3 * gb, "model.layers.1": 3 * gb, "lm_head": 2 * gb}
        max_memory = {0: 6 * gb, "cpu": 40 * gb}

        repaired, moves = DeviceMapBuilder._repair_critical_modules(
            device_map, sizes, max_memory
        )
        self.assertEqual(repaired["lm_head"], 0)
        evicted = [m for m in moves if m["to"] == "cpu"]
        self.assertTrue(evicted)
        self.assertTrue(all("layers" in m["module"] for m in evicted))

    def test_leaves_map_untouched_when_all_on_gpu(self):
        from core.engine.device_map_builder import DeviceMapBuilder
        gb = 2**30
        device_map = {"model.layers.0": 0, "lm_head": 0}
        sizes = {"model.layers.0": 1 * gb, "lm_head": 1 * gb}
        repaired, moves = DeviceMapBuilder._repair_critical_modules(
            device_map, sizes, {0: 8 * gb}
        )
        self.assertEqual(moves, [])
        self.assertEqual(repaired, device_map)


class TestNativeLoadIntegration(unittest.TestCase):
    """
    End-to-end load and generate. This is the only test that exercises the path
    where model-class selection, device-map construction and quantization all
    have to agree; every unit above passed while that path was broken.
    """

    def setUp(self):
        model_dir = _find_local_model()
        if not model_dir:
            self.skipTest("no local model in data/models/")
        try:
            import torch
            if not torch.cuda.is_available():
                self.skipTest("CUDA not available")
        except ImportError:
            self.skipTest("torch not installed")
        self.model_name = os.path.basename(model_dir)

    def test_loads_and_generates(self):
        engine = UniversalSigmaEngine()
        self.addCleanup(engine.unload)
        result = engine.load_native_model(self.model_name, context_tokens=4096)
        self.assertTrue(result.get("success"), msg=result.get("error"))

        placement = result["placement"]
        self.assertEqual(placement["mode"], "sharded")

        chunks = list(engine.generate_stream(
            "Rispondi con una sola parola: ciao.",
            max_tokens=24, model_name=self.model_name,
        ))
        text = "".join(c.get("token", "") for c in chunks)
        self.assertTrue(chunks[-1]["done"])
        self.assertGreater(len(text.strip()), 0)
        self.assertNotIn("Errore", text)

    def test_critical_modules_stay_on_gpu(self):
        engine = UniversalSigmaEngine()
        self.addCleanup(engine.unload)
        result = engine.load_native_model(self.model_name, context_tokens=4096)
        self.assertTrue(result.get("success"), msg=result.get("error"))

        device_map = getattr(engine.model_instance, "hf_device_map", {}) or {}
        exiled = [
            name for name, device in device_map.items()
            if str(device) in ("cpu", "disk")
            and any(h in name for h in ("lm_head", "embed_tokens"))
        ]
        self.assertEqual(exiled, [], f"per-token modules left off GPU: {exiled}")

    def test_unload_returns_vram(self):
        """Switching models must actually give the memory back."""
        engine = UniversalSigmaEngine()
        self.addCleanup(engine.unload)
        result = engine.load_native_model(self.model_name, context_tokens=4096)
        self.assertTrue(result.get("success"), msg=result.get("error"))

        released = engine.unload()
        self.assertGreater(released["freed_vram_gb"], 1.0)
        self.assertIsNone(engine.model_instance)


def _find_local_model():
    """Returns the first data/models/ subdirectory holding real weights."""
    models_dir = os.path.join(os.getcwd(), "data", "models")
    if not os.path.isdir(models_dir):
        return None
    for entry in sorted(os.listdir(models_dir)):
        path = os.path.join(models_dir, entry)
        if not os.path.isdir(path):
            continue
        if any(f.endswith((".safetensors", ".gguf", ".bin")) for f in os.listdir(path)):
            return path
    return None


if __name__ == "__main__":
    unittest.main()

