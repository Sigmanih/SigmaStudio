# ==============================================================================
# tests/test_sigma_engine.py — Test Suite for Universal SigmaEngine
# Tests: Hardware Probe, Weight Saliency Profiler, Multi-Drive Sharding, Engine Stream
# ==============================================================================
import unittest
import os
import shutil
import tempfile
import time
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

    def test_engine_status_without_loading(self):
        """
        Status must be answerable on a cold engine.

        Weights are never touched here: streaming is covered against the shared
        model in TestNativeLoadIntegration, so this stays cheap and cannot leave
        VRAM behind for whichever test pytest-randomly schedules next.
        """
        engine = UniversalSigmaEngine()
        status = engine.get_status()
        self.assertIn("active_backend", status)
        self.assertEqual(status["status"], "ready")
        self.assertIsNone(engine.model_instance)
        self.assertIn("optimizations", status)

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


class TestBackendSelection(unittest.TestCase):
    """
    The engine must pick a runtime that can actually start on this machine, and
    adapt its settings to the hardware it finds.
    """

    def test_capability_report_names_the_missing_dependency(self):
        from core.engine.backends import capability_report
        report = capability_report(_fake_profile([]))
        self.assertIn("llama_cpp", report)
        entry = report["llama_cpp"]
        self.assertIn("gguf", entry["formats"])
        # An unavailable backend must say what is missing, not just "no".
        self.assertTrue(entry["reason"])

    def test_gguf_routes_to_llamacpp(self):
        from core.engine.backends import select_backend, LlamaCppBackend
        facts = _facts()
        facts.weight_format = "gguf"
        available, _ = LlamaCppBackend.availability()
        chosen = select_backend(facts, _fake_profile([_gpu(0, "x", 16.0, 70)]))
        if available:
            self.assertIs(chosen, LlamaCppBackend)
        else:
            self.assertIsNone(chosen)

    def test_safetensors_is_not_claimed_by_llamacpp(self):
        from core.engine.backends import select_backend
        facts = _facts()
        facts.weight_format = "safetensors"
        self.assertIsNone(
            select_backend(facts, _fake_profile([_gpu(0, "x", 16.0, 70)]))
        )

    def test_arm_board_runs_on_cpu_with_neon(self):
        """
        On a board with no accelerator the model has to run on the CPU, and the
        batch size has to come down to fit the memory such devices have.
        """
        from core.engine.backends import LlamaCppBackend
        facts = _facts(layers=28)
        facts.weight_format = "gguf"
        facts.total_bytes = 2 * 2**30
        facts.max_position_embeddings = 8192

        profile = _fake_profile([], ram_gb=6.0)
        profile["cpu"] = {"cores_physical": 4}
        profile["system"] = {"is_arm": True, "is_raspberry_pi": True}

        settings = LlamaCppBackend._plan_settings(facts, profile, 4096)
        self.assertEqual(settings["n_gpu_layers"], 0)
        self.assertEqual(settings["device"], "arm_neon")
        self.assertEqual(settings["n_batch"], 128)
        self.assertEqual(settings["n_threads"], 3)      # 4 cores, one left free

    def test_apple_silicon_offloads_everything(self):
        from core.engine.backends import LlamaCppBackend
        facts = _facts()
        facts.weight_format = "gguf"
        profile = _fake_profile([{"type": "APPLE_MPS", "device_id": 0}])
        profile["cpu"] = {"cores_physical": 8}
        settings = LlamaCppBackend._plan_settings(facts, profile, 4096)
        self.assertEqual(settings["device"], "metal")
        self.assertEqual(settings["n_gpu_layers"], -1)

    def test_tensor_split_follows_free_vram(self):
        """A 16GB + 8GB pair must not be split evenly."""
        from core.engine.backends import LlamaCppBackend
        facts = _facts(layers=32)
        facts.weight_format = "gguf"
        facts.total_bytes = 4 * 2**30

        profile = _fake_profile([_gpu(0, "big", 15.0, 70), _gpu(1, "small", 7.0, 30)])
        profile["cpu"] = {"cores_physical": 12}

        settings = LlamaCppBackend._plan_settings(facts, profile, 4096)
        split = settings["tensor_split"]
        self.assertIsNotNone(split)
        self.assertAlmostEqual(sum(split), 1.0, places=2)
        self.assertGreater(split[0], split[1])

    def test_oversized_model_offloads_only_what_fits(self):
        from core.engine.backends import LlamaCppBackend
        facts = _facts(layers=80)
        facts.weight_format = "gguf"
        facts.total_bytes = 40 * 2**30          # far larger than the card

        profile = _fake_profile([_gpu(0, "small", 8.0, 40)])
        profile["cpu"] = {"cores_physical": 8}

        settings = LlamaCppBackend._plan_settings(facts, profile, 2048)
        self.assertGreater(settings["n_gpu_layers"], 0)
        self.assertLess(settings["n_gpu_layers"], 80)

    def test_context_is_clamped_to_training_length(self):
        from core.engine.backends import LlamaCppBackend
        facts = _facts()
        facts.max_position_embeddings = 4096
        self.assertEqual(LlamaCppBackend._clamp_context(facts, 32768), 4096)
        self.assertEqual(LlamaCppBackend._clamp_context(facts, 2048), 2048)


class TestGgufInspection(unittest.TestCase):
    """GGUF geometry is parsed from the file itself, without llama.cpp."""

    def setUp(self):
        self.gguf_dir = _find_local_model(suffix=".gguf", smallest=True)
        if not self.gguf_dir:
            self.skipTest("no local GGUF model in data/models/")

    def test_reads_geometry_from_header(self):
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.gguf_dir, use_cache=False)
        self.assertEqual(facts.weight_format, "gguf")
        self.assertGreater(facts.num_hidden_layers, 0)
        self.assertGreater(facts.hidden_size, 0)
        self.assertGreater(facts.head_dim, 0)
        self.assertGreater(facts.total_bytes, 0)

    def test_kv_estimate_available_for_gguf(self):
        from core.engine.model_inspector import ModelInspector
        facts = ModelInspector.inspect(self.gguf_dir, use_cache=False)
        self.assertGreater(ModelInspector.estimate_kv_cache_gb(facts, 4096), 0)


class TestGgufGeneration(unittest.TestCase):
    """End-to-end through the engine, exercising the backend hand-off."""

    def setUp(self):
        from core.engine.backends import LlamaCppBackend
        available, reason = LlamaCppBackend.availability()
        if not available:
            self.skipTest(reason)
        gguf_dir = _find_local_model(suffix=".gguf", smallest=True)
        if not gguf_dir:
            self.skipTest("no local GGUF model in data/models/")
        self.model_name = os.path.basename(gguf_dir)

    def test_loads_and_generates(self):
        engine = UniversalSigmaEngine()
        self.addCleanup(engine.unload)

        result = engine.load_native_model(self.model_name, context_tokens=2048)
        self.assertTrue(result.get("success"), msg=result.get("error"))
        self.assertEqual(result.get("backend"), "llama_cpp")
        self.assertTrue(engine.has_resident_model)

        chunks = list(engine.generate_stream(
            "Di' semplicemente: ciao.", max_tokens=24, model_name=self.model_name
        ))
        text = "".join(c.get("token", "") for c in chunks)
        self.assertTrue(chunks[-1]["done"])
        self.assertGreater(len(text.strip()), 0)
        self.assertNotIn("Errore", text)

    def test_residency_applies_to_backend_models_too(self):
        engine = UniversalSigmaEngine()
        self.addCleanup(engine.unload)
        engine.load_native_model(self.model_name, context_tokens=2048)

        t0 = time.perf_counter()
        again = engine.load_native_model(self.model_name, context_tokens=2048)
        self.assertTrue(again.get("already_loaded"))
        self.assertLess(time.perf_counter() - t0, 0.5)


class TestNativeLoadIntegration(unittest.TestCase):
    """
    End-to-end load and generate. This is the only test that exercises the path
    where model-class selection, device-map construction and quantization all
    have to agree; every unit above passed while that path was broken.
    """

    engine = None
    load_result = None

    @classmethod
    def setUpClass(cls):
        """
        Loads the model once for the whole class.

        Each load costs ~23s and ~17GB of VRAM. Loading per-test also makes the
        suite order-dependent: pytest-randomly can interleave these with other
        tests, and any VRAM not returned by a previous instance shows up here as
        an unrelated OOM.
        """
        cls.model_dir = _find_local_model(suffix=".safetensors")
        cls.skip_reason = None

        if not cls.model_dir:
            cls.skip_reason = "no local safetensors model in data/models/"
            return
        try:
            import torch
            if not torch.cuda.is_available():
                cls.skip_reason = "CUDA not available"
                return
        except ImportError:
            cls.skip_reason = "torch not installed"
            return

        cls.model_name = os.path.basename(cls.model_dir)
        cls.engine = UniversalSigmaEngine()

        # Record whether a pure-VRAM placement is even possible right now. On a
        # smaller machine, or with VRAM already in use, spilling to host RAM is
        # the correct outcome rather than a defect, and assertions about ideal
        # placement have to stand down.
        planned = cls.engine.plan_for_model(cls.model_name, context_tokens=4096)
        cls.fits_in_vram = bool(
            planned.get("success") and planned["plan"]["fits_in_vram"]
        )

        cls.load_result = cls.engine.load_native_model(
            cls.model_name, context_tokens=4096
        )

    @classmethod
    def tearDownClass(cls):
        if cls.engine is not None:
            cls.engine.unload()
            cls.engine = None

    def setUp(self):
        if self.skip_reason:
            self.skipTest(self.skip_reason)
        if not self.load_result.get("success"):
            self.fail(f"model load failed: {self.load_result.get('error')}")

    def test_loads_and_generates(self):
        self.assertEqual(self.load_result["placement"]["mode"], "sharded")

        chunks = list(self.engine.generate_stream(
            "Rispondi con una sola parola: ciao.",
            max_tokens=24, model_name=self.model_name,
        ))
        text = "".join(c.get("token", "") for c in chunks)
        self.assertTrue(chunks[-1]["done"])
        self.assertGreater(len(text.strip()), 0)
        self.assertNotIn("Errore", text)

        # The stream opens with status chunks before the model emits anything,
        # so TTFT belongs to the first chunk carrying a generated token.
        timed = [c for c in chunks if c.get("ttft_ms") is not None]
        self.assertTrue(timed, "no chunk reported time-to-first-token")
        self.assertGreater(timed[0]["ttft_ms"], 0)
        self.assertEqual(timed[0]["token_index"], 1)

    def test_critical_modules_stay_on_gpu(self):
        if not self.fits_in_vram:
            self.skipTest(
                "model does not fit in this machine's free VRAM; spilling "
                "per-token modules is the correct behaviour here"
            )
        device_map = getattr(self.engine.model_instance, "hf_device_map", {}) or {}
        exiled = [
            name for name, device in device_map.items()
            if str(device) in ("cpu", "disk")
            and any(h in name for h in ("lm_head", "embed_tokens"))
        ]
        self.assertEqual(exiled, [], f"per-token modules left off GPU: {exiled}")

    def test_benchmark_reports_a_verdict(self):
        """
        The benchmark must name what the model is bound by, since that is what
        decides whether tuning should target placement, precision or kernels.
        """
        result = self.engine.benchmark(prompt_tokens=64, decode_tokens=8)
        self.assertTrue(result.get("success"), msg=result.get("error"))

        self.assertGreater(result["prefill"]["tokens_per_second"], 0)
        self.assertGreater(result["decode"]["tokens_per_second"], 0)
        self.assertIn(
            result["verdict"]["bound_by"],
            ("memory_bandwidth", "kernel_launch_overhead", "host_memory", "unknown"),
        )
        # Prefill batches many tokens through the same weights, so it is always
        # far faster per token than decode; an inversion means a broken measure.
        self.assertGreater(
            result["prefill"]["tokens_per_second"],
            result["decode"]["tokens_per_second"],
        )

    def test_resident_model_is_reused_not_reloaded(self):
        """
        A model stays resident across chats: re-requesting the one already
        loaded must cost nothing, since a reload is tens of seconds and would
        also briefly need VRAM for two copies.
        """
        t0 = time.perf_counter()
        result = self.engine.load_native_model(self.model_name, context_tokens=4096)
        elapsed = time.perf_counter() - t0

        self.assertTrue(result.get("success"))
        self.assertTrue(result.get("already_loaded"))
        self.assertLess(elapsed, 0.5)

        # Generation must not announce a load either.
        chunks = list(self.engine.generate_stream(
            "Ciao", max_tokens=8, model_name=self.model_name
        ))
        self.assertFalse(
            any("Caricamento" in c.get("token", "") for c in chunks),
            "generation reloaded a model that was already resident",
        )

    def test_unload_returns_vram(self):
        """Switching models must actually give the memory back."""
        released = self.engine.unload()
        # Assert on the allocator delta, not the driver delta: the latter also
        # moves with whatever else is using the GPU, which makes it flaky.
        self.assertGreater(released["freed_allocated_gb"], 1.0)
        self.assertIsNone(self.engine.model_instance)

        # Restore state for whatever test runs next in this class.
        type(self).load_result = self.engine.load_native_model(
            self.model_name, context_tokens=4096
        )
        self.assertTrue(
            self.load_result.get("success"), msg=self.load_result.get("error")
        )



class TestFactsCacheInvalidation(unittest.TestCase):
    """
    Introspection caches its findings next to the weights. That cache has to
    notice when the directory changes: a conversion creates its output folder
    before the weights land in it, and an inspection during that window cached
    "no weights here", which the engine then reported as an unknown format long
    after the model was complete.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_cache_is_refreshed_when_weights_appear(self):
        from core.engine.model_inspector import ModelInspector

        # Inspected while still empty, exactly as a conversion leaves it.
        first = ModelInspector.inspect(self.dir)
        self.assertIsNotNone(first)
        self.assertNotEqual(first.weight_format, "gguf")

        # A GGUF header is enough for the format to be recognised.
        with open(os.path.join(self.dir, "model.gguf"), "wb") as handle:
            handle.write(b"GGUF" + bytes(64))

        second = ModelInspector.inspect(self.dir)
        self.assertEqual(
            second.weight_format, "gguf",
            "the cache was served after the directory changed",
        )

    def test_cache_is_reused_when_nothing_changed(self):
        from core.engine.model_inspector import ModelInspector

        with open(os.path.join(self.dir, "model.gguf"), "wb") as handle:
            handle.write(b"GGUF" + bytes(64))

        first = ModelInspector.inspect(self.dir)
        cache = os.path.join(self.dir, ".sigma_facts.json")
        self.assertTrue(os.path.exists(cache))
        before = os.stat(cache).st_mtime_ns

        second = ModelInspector.inspect(self.dir)
        self.assertEqual(second.weight_format, first.weight_format)
        self.assertEqual(os.stat(cache).st_mtime_ns, before,
                         "cache was rewritten despite an unchanged directory")


def _find_local_model(suffix=None, smallest=False):
    """
    Returns a data/models/ subdirectory holding real weights.

    `suffix` narrows the search to one weight format, so the GGUF and
    safetensors paths can each be exercised against whatever is installed.

    `smallest` picks the least bulky match. Tests that actually load and
    generate should not be handed a 50GB checkpoint just because it sorts
    first: the run becomes minutes long and fails on machines that cannot hold
    it, for reasons unrelated to what is being asserted.
    """
    from core.model_paths import models_dir as _models_dir

    base = _models_dir()
    if not os.path.isdir(base):
        return None

    wanted = (suffix,) if suffix else (".safetensors", ".gguf", ".bin")
    matches = []
    for entry in sorted(os.listdir(base)):
        path = os.path.join(base, entry)
        if not os.path.isdir(path):
            continue
        weights = [f for f in os.listdir(path) if f.endswith(wanted)]
        if not weights:
            continue
        if not smallest:
            return path
        size = sum(os.path.getsize(os.path.join(path, f)) for f in weights)
        matches.append((size, path))

    if not matches:
        return None
    return min(matches)[1]


if __name__ == "__main__":
    unittest.main()

