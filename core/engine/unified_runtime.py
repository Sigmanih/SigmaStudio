# ==============================================================================
# core/engine/unified_runtime.py — Universal Inference Engine & Hardware Dispatcher
#
# Placement is derived, never hardcoded: ModelInspector measures the checkpoint,
# UniversalHardwareProbe measures the machine, MemoryPlanner turns both into the
# max_memory / offload arguments accelerate consumes. Adding a GPU, changing a
# model or moving to another machine changes the plan without a code edit.
# ==============================================================================
import os
import time
import atexit
import threading
from typing import Dict, Any, List, Optional, Generator, Tuple

from core.logger import get_logger
from core.engine.hardware_probe import UniversalHardwareProbe
from core.engine.weight_profiler import WeightSaliencyProfiler
from core.engine.disk_streamer import MultiDriveShardedStreamer
from core.engine.moe_expert_cache import MoEExpertCache
from core.engine.speculative import SpeculativeDecodingEngine
from core.engine.model_inspector import ModelInspector, ModelFacts
from core.engine.memory_planner import MemoryPlanner, PlacementPlan
from core.engine.sampling import SamplingParams
from core.engine.cancellation import is_cancelled, stopping_criteria_for
from core.engine.prefix_cache import PrefixKVCache

log = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "Sei Sigma Assistant, un'architettura AI avanzata, precisa e utile. "
    "Rispondi in italiano in modo esaustivo, dettagliato e strutturato."
)


class UniversalSigmaEngine:
    """
    Universal LLM engine for Sigma Studio.

    Dispatches execution to the best backend available on the device and places
    model weights across VRAM -> RAM -> disk according to measured capacity.
    """

    def __init__(self):
        # Hardware probing is deferred: it spawns subprocesses and touches every
        # volume, which must not happen at import time.
        self._hardware_profile: Optional[Dict[str, Any]] = None
        self._active_backend: Optional[str] = None

        self.streamer = MultiDriveShardedStreamer()
        self.moe_cache = MoEExpertCache(max_vram_experts=8)
        self.speculative_engine = SpeculativeDecodingEngine(gamma_lookahead=4)

        self.loaded_model_name: Optional[str] = None
        self.loaded_model: Optional[Dict[str, Any]] = None
        # Set when a non-safetensors checkpoint is served by a registry backend
        # (llama.cpp today). The transformers path uses model_instance instead.
        self.active_backend_instance = None
        self.model_instance = None
        self.tokenizer_instance = None
        self.model_facts: Optional[ModelFacts] = None
        self.placement_plan: Optional[PlacementPlan] = None
        self.last_load_error: Optional[str] = None
        self.last_device_map_report: Optional[Dict[str, Any]] = None
        self._load_lock = threading.Lock()

        # One model is resident at a time, so one generation runs at a time.
        # The server is threaded and admits concurrent requests: without this,
        # two chats for different models had one thread unload the weights the
        # other was mid-generation on, and two chats for the same GGUF called
        # into llama.cpp concurrently, which is not thread-safe. The queue is
        # not a limitation added here -- it is the truth about the hardware,
        # made explicit instead of discovered as a crash.
        self._generation_lock = threading.RLock()
        self._generation_waiting = 0
        self._waiting_lock = threading.Lock()

        # Cross-turn KV reuse on the transformers path. On by default because
        # the memory it holds is memory the placement plan already reserved for
        # the context window; SIGMA_PREFIX_CACHE=0 turns it off for a machine
        # where that budget is genuinely tight.
        self.prefix_cache = PrefixKVCache()
        self.prefix_cache_enabled = os.environ.get("SIGMA_PREFIX_CACHE", "1") != "0"

    # ------------------------------------------------------------- hardware

    @property
    def has_resident_model(self) -> bool:
        """
        Whether any runtime currently holds weights.

        Residency lives in two places: the transformers path keeps a module in
        model_instance, a registry backend keeps its own handle. Checking only
        one makes the engine reload on top of a model it already has.
        """
        if self.model_instance is not None:
            return True
        backend = self.active_backend_instance
        return backend is not None and backend.is_loaded

    @property
    def hardware_profile(self) -> Dict[str, Any]:
        if self._hardware_profile is None:
            self._hardware_profile = UniversalHardwareProbe.probe_all()
        return self._hardware_profile

    @hardware_profile.setter
    def hardware_profile(self, value: Dict[str, Any]) -> None:
        self._hardware_profile = value
        self._active_backend = None

    @property
    def active_backend(self) -> str:
        if self._active_backend is None:
            self._active_backend = self._determine_optimal_backend()
            log.info("[SigmaEngine] Active backend: %s", self._active_backend)
        return self._active_backend

    def refresh_vram(self) -> Dict[str, Any]:
        """
        Re-reads free VRAM before planning a load.

        Free VRAM is the one input that changes minute to minute (other
        processes, a previously loaded model), so a plan built from a stale
        reading will overcommit.
        """
        profile = self.hardware_profile
        try:
            profile["accelerators"] = UniversalHardwareProbe.probe_accelerators()
            profile["ram"] = UniversalHardwareProbe.probe_ram()
        except Exception as exc:
            log.warning("[SigmaEngine] VRAM refresh failed: %s", exc)
        return profile

    def _determine_optimal_backend(self) -> str:
        """
        Selects the best execution backend that is actually usable here.

        A backend is only reported when its runtime dependency is importable:
        naming a backend whose library is missing produces a plan that cannot
        run.
        """
        # Probe if needed rather than reading the raw field: callers reach this
        # through get_status(), where the accelerator list may not have been
        # populated yet, and an empty list would silently look like a CPU-only
        # machine and select a CPU backend on a box with two GPUs.
        profile = self.hardware_profile
        accs = profile.get("accelerators", [])
        system = profile.get("system", {})
        has_torch = self._module_available("torch")

        if has_torch and any(a.get("type") == "NVIDIA_CUDA" for a in accs):
            return "TORCH_CUDA_SDPA" if not self._module_available("flash_attn") \
                else "TORCH_CUDA_FLASHATTN"
        if has_torch and any(a.get("type") == "AMD_ROCM" for a in accs):
            return "TORCH_ROCM_HIP"
        if has_torch and any(a.get("type") == "APPLE_MPS" for a in accs):
            return "TORCH_APPLE_MPS"
        if self._module_available("llama_cpp"):
            if system.get("is_raspberry_pi") or system.get("is_arm"):
                return "ARM_NEON_LLAMACPP"
            return "CPU_LLAMACPP"
        if self._module_available("onnxruntime"):
            return "ONNX_RUNTIME"
        if has_torch:
            return "TORCH_CPU"
        return "UNAVAILABLE_NO_RUNTIME"

    @staticmethod
    def _module_available(name: str) -> bool:
        import importlib.util
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False

    def _generate_default_optimizations(self) -> Dict[str, Any]:
        """
        Reports the optimizations that are genuinely active on this machine.

        Every flag here is one the loader actually applies; nothing is reported
        as enabled unless its dependency is installed and its argument is passed
        to the runtime.
        """
        accs = self.hardware_profile.get("accelerators", [])
        has_cuda = any(a.get("type") == "NVIDIA_CUDA" for a in accs)
        has_flash = self._module_available("flash_attn")
        has_fla = self._module_available("fla")

        return {
            "backend": self.active_backend,
            "attention_kernel": self._select_attn_implementation(),
            "flash_attention_2_available": has_flash,
            "linear_attention_kernels": "fla_triton" if has_fla else "torch_fallback",
            "causal_conv1d_available": self._module_available("causal_conv1d"),
            "devices_in_use": len([a for a in accs if "free_vram_gb" in a]),
            "quantization": (
                self.placement_plan.quantization if self.placement_plan else "auto"
            ),
            "max_memory": (
                {str(k): v for k, v in self.placement_plan.max_memory.items()}
                if self.placement_plan else {}
            ),
            "offload_folder": (
                self.placement_plan.offload_folder if self.placement_plan else None
            ),
            "bf16_supported": any(a.get("supports_bf16") for a in accs) if has_cuda else False,
            "moe_expert_cache_active": bool(
                self.model_facts and self.model_facts.is_moe
            ),
            "native_mtp_head": bool(self.model_facts and self.model_facts.has_mtp),
        }

    def _select_attn_implementation(self) -> str:
        """Picks the fastest attention kernel whose dependency is installed."""
        if self._module_available("flash_attn"):
            return "flash_attention_2"
        try:
            import torch
            if torch.cuda.is_available() or hasattr(torch.nn.functional, "scaled_dot_product_attention"):
                return "sdpa"
        except Exception:
            pass
        return "eager"

    # -------------------------------------------------------- model discovery

    @staticmethod
    def _folder_has_weights(folder_path: str) -> bool:
        """Checks if a directory actually contains neural model weights."""
        if not os.path.isdir(folder_path):
            return False
        try:
            files = os.listdir(folder_path)
        except Exception:
            return False
        return any(
            f.endswith((".safetensors", ".gguf", ".bin"))
            or f == "model.safetensors.index.json"
            for f in files
        )

    def find_valid_model_directory(
        self, model_identifier: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Finds the directory and canonical name of a local model with weights.

        Resolution lives in core.model_paths so the engine, the downloader,
        the inventory and the converter all agree on where models are, and
        all follow the directory configured in the Model Hub.
        """
        from core.model_paths import resolve_model_dir, list_model_dirs

        path = resolve_model_dir(model_identifier)
        if path is None and not model_identifier:
            candidates = list_model_dirs()
            path = candidates[0] if candidates else None
        if path is None:
            return None
        return path, os.path.basename(path.rstrip(os.sep + '/'))

    # ------------------------------------------------------------- loading

    def load_native_model(
        self,
        model_identifier: Optional[str] = None,
        context_tokens: int = 32768,
        force_quantization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Loads a local model across all available memory tiers.

        Returns a structured result. Failures carry the real exception text so
        the caller can show the actual cause instead of a generic message.
        """
        with self._load_lock:
            return self._load_native_model_locked(
                model_identifier, context_tokens, force_quantization
            )

    def _load_native_model_locked(
        self,
        model_identifier: Optional[str],
        context_tokens: int,
        force_quantization: Optional[str],
    ) -> Dict[str, Any]:
        model_info = self.find_valid_model_directory(model_identifier)
        if not model_info:
            error = (
                f"Nessun modello con pesi validi trovato in data/models/ per "
                f"'{model_identifier}'."
            )
            self.last_load_error = error
            log.warning("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "discovery"}

        target_path, display_name = model_info

        # Already resident: switching chats that share a model costs nothing.
        if self.has_resident_model and self.loaded_model_name == display_name:
            log.debug("[SigmaEngine] '%s' already resident, reusing", display_name)
            return {
                "success": True,
                "model_name": display_name,
                "already_loaded": True,
                "load_seconds": 0.0,
                "plan": self.placement_plan.to_dict() if self.placement_plan else {},
                "placement": (self.loaded_model or {}).get("placement"),
            }

        # A different model: release the current one first. Two checkpoints
        # cannot share the VRAM budget, and loading over a resident model makes
        # the new plan overcommit and fall back to a host-RAM spill.
        if self.has_resident_model:
            log.info(
                "[SigmaEngine] Switching '%s' -> '%s', releasing current weights",
                self.loaded_model_name, display_name,
            )
            self.unload()

        # ------------------------------------------------------ measure
        try:
            facts = ModelInspector.inspect(target_path)
            if facts is None:
                raise RuntimeError("introspezione del checkpoint fallita")
        except Exception as exc:
            error = f"Impossibile analizzare il modello in {target_path}: {exc}"
            self.last_load_error = error
            log.error("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "inspection"}

        # Formats other than safetensors are served by a dedicated backend
        # chosen for this machine, so GGUF runs on llama.cpp CUDA kernels here
        # and on NEON on an ARM board without the caller knowing the difference.
        if facts.weight_format != "safetensors":
            return self._load_via_backend(facts, display_name, context_tokens)

        # -------------------------------------------------------- plan
        profile = self.refresh_vram()
        plan = MemoryPlanner.build_plan(
            facts,
            profile,
            context_tokens=context_tokens,
            force_quantization=force_quantization,
        )

        log.info(
            "[SigmaEngine] Loading '%s' | %s | %s",
            display_name, facts.summary(), plan.summary(),
        )
        for warning in plan.warnings:
            log.warning("[SigmaEngine] %s", warning)

        # -------------------------------------------------------- load
        try:
            import torch
            from transformers import AutoTokenizer, AutoProcessor, BitsAndBytesConfig

            os.environ.setdefault(
                "PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True"
            )

            has_cuda = torch.cuda.is_available()
            compute_dtype = (
                torch.bfloat16
                if has_cuda and torch.cuda.is_bf16_supported()
                else (torch.float16 if has_cuda else torch.float32)
            )

            model_cls = ModelInspector.resolve_model_class(facts)
            log.info("[SigmaEngine] Model class: %s", model_cls.__name__)

            tokenizer = self._load_tokenizer(
                AutoTokenizer, AutoProcessor, target_path, facts
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.last_load_error = error
            log.error("[SigmaEngine] Preparation failed: %s", error, exc_info=True)
            return {
                "success": False,
                "error": error,
                "stage": "preparation",
                "facts": facts.to_dict(),
            }

        t0 = time.perf_counter()
        model, load_error = self._attempt_load(
            model_cls, target_path, plan, compute_dtype, has_cuda, facts
        )

        # Any first-attempt failure is potentially recoverable. Free VRAM can
        # drop between planning and loading -- another process, or another model
        # in this one -- so re-probe instead of trusting the reading the failed
        # plan was built on, and allow a host spill rather than leaving the user
        # with no model at all.
        if model is None and has_cuda:
            log.warning(
                "[SigmaEngine] First placement failed (%s). "
                "Re-probing VRAM and retrying with host RAM spill.", load_error,
            )
            self._free_cuda_cache()
            plan = MemoryPlanner.build_plan(
                facts,
                self.refresh_vram(),
                context_tokens=context_tokens,
                force_quantization=force_quantization,
                allow_host_spill=True,
            )
            plan.warnings.append(
                "First placement failed; replanned against currently free VRAM "
                "with a host-RAM spill, which is slower than a pure-VRAM fit."
            )
            model, load_error = self._attempt_load(
                model_cls, target_path, plan, compute_dtype, has_cuda, facts
            )

        if model is None:
            self.last_load_error = load_error
            log.error(
                "[SigmaEngine] Failed to load '%s': %s", display_name, load_error
            )
            return {
                "success": False,
                "error": load_error,
                "stage": "load",
                "plan": plan.to_dict(),
                "facts": facts.to_dict(),
            }

        model.eval()
        load_seconds = round(time.perf_counter() - t0, 1)

        # ------------------------------------------------------ register
        self.model_instance = model
        self.tokenizer_instance = tokenizer
        self.model_facts = facts
        self.placement_plan = plan
        self.loaded_model_name = display_name
        self.last_load_error = None

        # The cache may grow to the context the plan reserved KV for, and no
        # further: past that it stops being a saving and becomes a second copy
        # of the conversation sitting in VRAM.
        self.prefix_cache.configure(display_name, plan.context_tokens)

        actual_placement = self._describe_placement(model)
        self.loaded_model = {
            "name": display_name,
            "path": target_path,
            "format": facts.weight_format,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "param_count_b": round(facts.param_count / 1e9, 2),
            "quantization": plan.quantization,
            "backend": self.active_backend,
            "placement": actual_placement,
            "plan": plan.to_dict(),
            "load_seconds": load_seconds,
            "loaded_at": time.time(),
            "status": "ready",
        }

        log.info(
            "[SigmaEngine] '%s' loaded in %ss | placement: %s",
            display_name, load_seconds, actual_placement,
        )

        return {
            "success": True,
            "model_name": display_name,
            "load_seconds": load_seconds,
            "plan": plan.to_dict(),
            "facts": facts.to_dict(),
            "placement": actual_placement,
        }

    def _load_via_backend(
        self, facts: ModelFacts, display_name: str, context_tokens: int
    ) -> Dict[str, Any]:
        """Loads a non-safetensors checkpoint through the backend registry."""
        from core.engine.backends import select_backend, explain_unsupported

        backend_cls = select_backend(facts, self.refresh_vram())
        if backend_cls is None:
            error = explain_unsupported(facts)
            self.last_load_error = error
            log.error("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "backend"}

        backend = backend_cls()
        result = backend.load(facts, self.hardware_profile, context_tokens=context_tokens)
        if not result.get("success"):
            self.last_load_error = result.get("error")
            log.error(
                "[SigmaEngine] Backend %s failed: %s",
                backend_cls.name, result.get("error"),
            )
            return result

        self.active_backend_instance = backend
        self.model_facts = facts
        self.loaded_model_name = display_name
        self.placement_plan = None
        self.last_load_error = None
        self.loaded_model = {
            "name": display_name,
            "path": facts.path,
            "format": facts.weight_format,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "backend": backend_cls.name,
            "placement": result.get("placement", {}),
            "settings": result.get("settings", {}),
            "load_seconds": result.get("load_seconds"),
            "loaded_at": time.time(),
            "status": "ready",
        }
        return result

    def _attempt_load(
        self,
        model_cls,
        target_path: str,
        plan: PlacementPlan,
        compute_dtype,
        has_cuda: bool,
        facts: Optional[ModelFacts] = None,
    ):
        """
        Runs one placement attempt. Returns (model, None) or (None, error_text).
        Errors are returned rather than raised so the caller can replan.
        """
        from transformers import BitsAndBytesConfig

        load_kwargs: Dict[str, Any] = {
            "low_cpu_mem_usage": True,
            "trust_remote_code": True,
            "dtype": compute_dtype,
            "attn_implementation": self._select_attn_implementation(),
        }
        device_map: Any = None

        if has_cuda:
            device_map, map_report = self._resolve_device_map(
                model_cls, target_path, facts, plan
            )
            load_kwargs["device_map"] = device_map
            self.last_device_map_report = map_report

            if isinstance(device_map, str):
                # A string strategy passes through the quantizer's own budget
                # shrink, so it needs the compensated numbers.
                load_kwargs["max_memory"] = plan.max_memory_for_string_strategy()

            if plan.offload_folder:
                load_kwargs["offload_folder"] = plan.offload_folder

            quant_config = self._build_quantization_config(
                BitsAndBytesConfig, plan, compute_dtype
            )
            if quant_config is not None:
                load_kwargs["quantization_config"] = quant_config

        log.info(
            "[SigmaEngine] Attempting load: quant=%s device_map=%s offload=%s",
            plan.quantization,
            device_map if isinstance(device_map, str) else "explicit",
            plan.offload_folder,
        )

        try:
            return model_cls.from_pretrained(target_path, **load_kwargs), None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def _resolve_device_map(
        self,
        model_cls,
        target_path: str,
        facts: Optional[ModelFacts],
        plan: PlacementPlan,
    ):
        """
        Prefers an explicit, repaired device map; falls back to "sequential".

        The fallback is "sequential" rather than "auto" because "auto" routes
        through get_balanced_memory, which caps every GPU but the last at
        roughly total_size/num_devices. On asymmetric cards that discards the
        larger GPU's capacity: a 16GB + 8GB pair ends up capped near 6GB each
        and the remainder spills to the CPU.
        """
        if facts is not None:
            try:
                from transformers import AutoConfig
                from core.engine.device_map_builder import DeviceMapBuilder

                config = AutoConfig.from_pretrained(
                    target_path, trust_remote_code=True
                )
                built = DeviceMapBuilder.build(model_cls, config, facts, plan)
                if built is not None:
                    return built[0], built[1]
            except Exception as exc:
                log.warning(
                    "[SigmaEngine] Explicit device map unavailable (%s); "
                    "falling back to sequential.", exc,
                )
        return "sequential", None

    @staticmethod
    def _build_quantization_config(
        BitsAndBytesConfig, plan: PlacementPlan, compute_dtype
    ):
        """Builds the bitsandbytes config matching the planner's precision choice."""
        # bitsandbytes refuses any off-GPU dispatch unless this is set, so it
        # must follow the budget actually offered, not the predicted outcome.
        allows_offload = any(
            str(k) in ("cpu", "disk") for k in plan.max_memory
        ) or bool(plan.offload_folder)

        if plan.quantization == "nf4":
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
                llm_int8_enable_fp32_cpu_offload=allows_offload,
            )
        if plan.quantization == "int8":
            return BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_enable_fp32_cpu_offload=allows_offload,
            )
        return None  # bf16: weights load in compute dtype

    @staticmethod
    def _load_tokenizer(AutoTokenizer, AutoProcessor, target_path: str, facts: ModelFacts):
        """
        Loads the tokenizer, preferring the processor for multimodal checkpoints
        so the chat template and special image tokens stay consistent.
        """
        if facts.is_multimodal:
            try:
                processor = AutoProcessor.from_pretrained(
                    target_path, trust_remote_code=True
                )
                tokenizer = getattr(processor, "tokenizer", None)
                if tokenizer is not None:
                    return tokenizer
            except Exception as exc:
                log.debug("[SigmaEngine] Processor unavailable, using tokenizer: %s", exc)
        return AutoTokenizer.from_pretrained(target_path, trust_remote_code=True)

    @staticmethod
    def _describe_placement(model) -> Dict[str, Any]:
        """
        Reports where accelerate actually put the weights.

        This is the ground truth to compare against the plan; a mismatch means
        the budget estimate was wrong.
        """
        device_map = getattr(model, "hf_device_map", None)
        if not device_map:
            try:
                device = str(next(model.parameters()).device)
            except Exception:
                device = "unknown"
            return {"mode": "single_device", "device": device}

        counts: Dict[str, int] = {}
        for device in device_map.values():
            counts[str(device)] = counts.get(str(device), 0) + 1

        return {
            "mode": "sharded",
            "modules_per_device": counts,
            "devices": sorted(counts.keys()),
        }

    def unload(self) -> Dict[str, Any]:
        """
        Releases the model and returns VRAM to the allocator.

        Dropping the reference is not enough: accelerate attaches dispatch hooks
        that hold the module graph alive, so they are removed first. Freed bytes
        are reported so callers can verify the memory actually came back before
        planning the next load.
        """
        previous = self.loaded_model_name
        freed_before = self._vram_used_bytes()
        allocated_before = self._torch_allocated_bytes()

        # The cache holds tensors on the model's devices. Dropping it before
        # the weights is what makes the freed-bytes figure below honest.
        self.prefix_cache.clear("model unloaded")

        # A registry backend owns its own memory (llama.cpp allocates outside
        # the torch allocator), so it must release through its own path.
        if self.active_backend_instance is not None:
            self.active_backend_instance.unload()
            self.active_backend_instance = None

        model = self.model_instance
        if model is not None:
            try:
                from accelerate.hooks import remove_hook_from_module
                remove_hook_from_module(model, recurse=True)
            except Exception as exc:
                log.debug("[SigmaEngine] Hook removal skipped: %s", exc)

        self.model_instance = None
        self.tokenizer_instance = None
        self.loaded_model = None
        self.loaded_model_name = None
        self.model_facts = None
        self.placement_plan = None
        self.last_device_map_report = None
        del model

        self._free_cuda_cache()

        # Two figures, because they answer different questions. The driver delta
        # is what the machine actually gets back and is what a user sees, but
        # other processes move it. The allocator delta counts only tensors this
        # process released, so it is exact regardless of what else is running.
        freed_gb = round((freed_before - self._vram_used_bytes()) / 2**30, 2)
        freed_allocated_gb = round(
            (allocated_before - self._torch_allocated_bytes()) / 2**30, 2
        )
        log.info(
            "[SigmaEngine] Unloaded '%s', released %.2f GB of tensors "
            "(%.2f GB returned to the driver)",
            previous, freed_allocated_gb, freed_gb,
        )
        return {
            "success": True,
            "unloaded": previous,
            "freed_vram_gb": freed_gb,
            "freed_allocated_gb": freed_allocated_gb,
        }

    @staticmethod
    def _free_cuda_cache() -> None:
        """
        Returns cached blocks on every GPU to the driver.

        empty_cache() only releases the caching allocator's pool for the current
        device, so on a multi-GPU split it leaves the secondary cards holding
        gigabytes that the driver still counts as used. The next plan then reads
        a machine with far less free VRAM than it really has.
        """
        try:
            import gc
            import torch
            gc.collect()
            if not torch.cuda.is_available():
                return
            for index in range(torch.cuda.device_count()):
                with torch.cuda.device(index):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
        except Exception as exc:
            log.debug("[SigmaEngine] Cache release skipped: %s", exc)

    @staticmethod
    def _torch_allocated_bytes() -> int:
        """Bytes of live tensors this process holds, across all CUDA devices."""
        try:
            import torch
            if not torch.cuda.is_available():
                return 0
            return sum(
                torch.cuda.memory_allocated(i)
                for i in range(torch.cuda.device_count())
            )
        except Exception:
            return 0

    @staticmethod
    def _vram_used_bytes() -> int:
        """Total bytes in use across all CUDA devices, or 0 without CUDA."""
        try:
            import torch
            if not torch.cuda.is_available():
                return 0
            total = 0
            for idx in range(torch.cuda.device_count()):
                free, capacity = torch.cuda.mem_get_info(idx)
                total += capacity - free
            return total
        except Exception:
            return 0

    # ---------------------------------------------------------- generation

    #: How long a queued request waits for the engine before giving up. Longer
    #: than any single answer should take, short enough that a wedged
    #: generation surfaces as an error instead of a hung tab.
    GENERATION_QUEUE_TIMEOUT = 600.0

    def generate_stream(
        self,
        prompt: str = "",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        model_name: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Serialises access to the engine, then streams the answer.

        Everything below the lock assumes it owns the resident model: it may
        unload it, replace it, and mutate its KV cache. Two threads doing that
        at once is not slower, it is wrong, so the queue is part of the
        contract rather than a tuning choice.
        """
        with self._waiting_lock:
            self._generation_waiting += 1
            position = self._generation_waiting

        acquired = self._generation_lock.acquire(blocking=False)
        try:
            if not acquired:
                # Say so rather than appearing frozen: on a single-model engine
                # a wait is normal, and a silent one reads as a crash.
                yield {
                    "token": "",
                    "status": True,
                    "model_status": (
                        f"⏳ Motore occupato da un'altra richiesta"
                        f"{f' ({position - 1} in attesa)' if position > 1 else ''}..."
                    ),
                    "queue_position": position,
                    "done": False,
                }
                acquired = self._generation_lock.acquire(
                    timeout=self.GENERATION_QUEUE_TIMEOUT
                )
        finally:
            with self._waiting_lock:
                self._generation_waiting -= 1

        if not acquired:
            yield {
                "token": (
                    "\n\n⏳ **Motore occupato**: la richiesta precedente non si è "
                    f"conclusa entro {int(self.GENERATION_QUEUE_TIMEOUT)}s. "
                    "Riprova, oppure scarica il modello dal Model Hub per "
                    "liberare il motore."
                ),
                "token_index": 1,
                "done": True,
            }
            return

        try:
            yield from self._generate_stream_locked(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
                messages=messages,
                params=params,
                cancel=cancel,
            )
        finally:
            self._generation_lock.release()

    def _generate_stream_locked(
        self,
        prompt: str = "",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        model_name: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams tokens from native inference with live throughput metrics.

        `messages` carries the whole conversation -- system prompt, attached
        file context, prior turns and tool results. Passing only `prompt` and
        `system_prompt` collapses that to a single exchange, so the model loses
        everything the user has already said.

        `params` carries the whole sampler. Callers that predate it still pass
        temperature and max_tokens, which are promoted into the same object, so
        there is exactly one place where sampling is decided either way.

        `cancel` is checked between tokens: when the reader goes away the
        generation stops instead of running to the token budget with nobody
        listening.
        """
        t_start = time.perf_counter()
        token_count = 0

        if params is None:
            params = SamplingParams.resolve(model_name=model_name or "").with_overrides(
                temperature=temperature, max_tokens=max_tokens
            )

        model_info = self.find_valid_model_directory(model_name or self.loaded_model_name)
        target_model = model_info[1] if model_info else (model_name or self.loaded_model_name)

        if target_model is None:
            yield from self._yield_no_model_message()
            return

        def _clean_m_name(name):
            if not name: return ""
            return str(name).strip().lower().replace(".gguf", "").replace("--", "/").split("/")[-1].split("\\")[-1]

        is_already_resident = (
            self.has_resident_model and (
                _clean_m_name(self.loaded_model_name) == _clean_m_name(target_model) or
                _clean_m_name(self.loaded_model_name) == _clean_m_name(model_name) or
                (model_info and self.loaded_model and os.path.abspath(self.loaded_model.get("path", "")) == os.path.abspath(model_info[0]))
            )
        )

        if not is_already_resident:
            result = self.load_native_model(target_model)
            if not result.get("success"):
                yield {
                    "token": self._format_load_failure(target_model, result),
                    "token_index": 1,
                    "done": True,
                }
                return

            load_sec = result.get("load_seconds") or round(time.perf_counter() - t_start, 2)
            load_ms = round(load_sec * 1000, 1)

            yield {
                "token": "",
                "status": True,
                "load_duration_ms": load_ms,
                "load_seconds": load_sec,
                "model_status": f"⚡ Modello caricato in {load_sec}s",
                "done": False,
            }

            # Throughput must measure generation, not the load before it.
            t_start = time.perf_counter()

        # A registry backend runs its own generation loop; it owns the model.
        if self.active_backend_instance is not None:
            yield from self.active_backend_instance.generate_stream(
                prompt,
                system_prompt=system_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                messages=self._as_messages(prompt, system_prompt, messages),
                params=params,
                cancel=cancel,
            )
            return

        try:
            import torch
            from transformers import TextIteratorStreamer

            streamer = TextIteratorStreamer(
                self.tokenizer_instance,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=300.0,
            )

            inputs = self._build_inputs(
                self._as_messages(prompt, system_prompt, messages)
            )

            # One sampler, resolved once, adapted here. The token budget still
            # has the last word: it knows what is left of the context window.
            gen_kwargs: Dict[str, Any] = dict(
                **inputs,
                **params.for_transformers(self.tokenizer_instance),
                streamer=streamer,
                use_cache=True,
            )
            gen_kwargs["max_new_tokens"] = self._token_budget(
                params.max_tokens, inputs
            )

            # Reuse the KV of whatever this prompt shares with the last one.
            # In a conversation that is the entire history: the model then
            # prefills only the newest turn instead of re-reading everything
            # it read a minute ago.
            prompt_ids = inputs["input_ids"][0].tolist()
            reused_tokens = 0
            if self.prefix_cache_enabled:
                past, reused_tokens = self.prefix_cache.take(
                    prompt_ids, self.loaded_model_name or ""
                )
                if past is not None:
                    gen_kwargs["past_key_values"] = past
                    # generate() must return the cache it leaves behind, or the
                    # next turn has nothing to crop.
                    gen_kwargs["return_dict_in_generate"] = True
            self.prefix_cache.tokens_prefilled += max(
                len(prompt_ids) - reused_tokens, 0
            )
            if self.prefix_cache_enabled and "return_dict_in_generate" not in gen_kwargs:
                gen_kwargs["return_dict_in_generate"] = True

            if params.seed is not None:
                from transformers import set_seed
                set_seed(params.seed)

            stopper = stopping_criteria_for(cancel)
            if stopper is not None:
                gen_kwargs["stopping_criteria"] = stopper

            pad_id = getattr(self.tokenizer_instance, "pad_token_id", None)
            eos_id = getattr(self.tokenizer_instance, "eos_token_id", None)
            gen_kwargs["pad_token_id"] = pad_id if pad_id is not None else eos_id

            log.debug("[SigmaEngine] Sampling: %s", params.summary())

            generation_error: List[BaseException] = []
            generation_output: List[Any] = []

            def _run_generate():
                try:
                    with torch.inference_mode():
                        result = self.model_instance.generate(**gen_kwargs)
                    generation_output.append(result)
                except BaseException as exc:  # surfaced to the caller below
                    log.error("[SigmaEngine] Generation thread failed: %s", exc)
                    generation_error.append(exc)
                    # A failed generation leaves a cache of unknown length; the
                    # next turn must not crop something it cannot trust.
                    self.prefix_cache.clear("generation failed")
                    streamer.end()

            thread = threading.Thread(target=_run_generate, daemon=True)
            thread.start()

            first_token_sent = False
            first_token_at = t_start
            for token_text in streamer:
                # The stopping criterion already told generate to wind down;
                # leaving the consumer loop as well means the caller stops
                # paying for tokens nobody will read. The streamer queue is
                # unbounded, so the producer never blocks on our exit.
                if is_cancelled(cancel):
                    break
                if not token_text:
                    continue
                token_count += 1
                now = time.perf_counter()

                # Throughput is reported for the decode phase alone. Prompt
                # processing is a one-off cost that scales with the prompt, and
                # folding it in makes a healthy model look several times slower
                # as soon as the conversation carries real context. It is
                # reported separately, as time-to-first-token.
                if not first_token_sent:
                    first_token_at = now
                    chunk = {
                        "token": token_text,
                        "token_index": token_count,
                        "ttft_ms": round((now - t_start) * 1000, 1),
                        "done": False,
                    }
                    first_token_sent = True
                else:
                    decode_seconds = max(now - first_token_at, 1e-3)
                    chunk = {
                        "token": token_text,
                        "token_index": token_count,
                        "speed_tok_s": round((token_count - 1) / decode_seconds, 1),
                        "done": False,
                    }
                yield chunk

            thread.join(timeout=5.0)

            self._retain_prefix_cache(generation_output, cancel)

            if generation_error:
                yield {
                    "token": f"\n\n❌ **Errore GPU durante la generazione**: "
                             f"{type(generation_error[0]).__name__}: {generation_error[0]}",
                    "token_index": token_count + 1,
                    "done": True,
                }
                return

            now = time.perf_counter()
            decode_seconds = max(now - first_token_at, 1e-3)
            yield {
                "token": "",
                "token_index": token_count + 1,
                "speed_tok_s": round(max(token_count - 1, 1) / decode_seconds, 1),
                "total_tokens": token_count,
                "prefill_ms": round((first_token_at - t_start) * 1000, 1),
                "cancelled": is_cancelled(cancel),
                "sampling": params.to_dict(),
                "prefix_reused_tokens": reused_tokens,
                "prompt_tokens": len(prompt_ids),
                "done": True,
            }

        except Exception as exc:
            self.prefix_cache.clear("generation error")
            log.error("[SigmaEngine] Generation error: %s", exc, exc_info=True)
            yield {
                "token": f"\n\n❌ **Errore SigmaEngine**: {type(exc).__name__}: {exc}",
                "token_index": token_count + 1,
                "done": True,
            }

    def _retain_prefix_cache(self, generation_output: List[Any], cancel: Any) -> None:
        """
        Keeps the KV cache a finished generation left, for the next turn.

        Only a generation that ran to its natural end is kept. A cancelled one
        stopped at an arbitrary token, and the sequence it reports may not be
        the sequence the cache actually covers -- reusing that would not slow
        the next answer down, it would corrupt it.
        """
        if not self.prefix_cache_enabled:
            return
        if is_cancelled(cancel) or not generation_output:
            self.prefix_cache.clear("generation did not finish")
            return

        result = generation_output[0]
        cache = getattr(result, "past_key_values", None)
        sequences = getattr(result, "sequences", None)
        if cache is None or sequences is None:
            # An older transformers, or a model whose generate() returns a bare
            # tensor: nothing to retain, and nothing broken by not retaining it.
            self.prefix_cache.clear("runtime returned no cache")
            return

        try:
            ids = sequences[0].tolist()
        except Exception as exc:
            log.debug("[SigmaEngine] Cannot read generated ids (%s)", exc)
            self.prefix_cache.clear("unreadable sequence")
            return

        self.prefix_cache.store(ids, cache, self.loaded_model_name or "")

    def _token_budget(self, requested: int, inputs: Dict[str, Any]) -> int:
        """
        How many new tokens this request may generate.

        Bounded by what is left of the model's context after the prompt, rather
        than by a fixed ceiling: a long conversation must not be allowed to run
        past the window and corrupt its own KV cache, while a short one should
        not be cut off early just because some constant said so.
        """
        limit = requested if requested and requested > 0 else 4096

        prompt_tokens = 0
        ids = inputs.get("input_ids")
        if ids is not None and hasattr(ids, "shape"):
            prompt_tokens = int(ids.shape[-1])

        window = 0
        if self.model_facts:
            window = self.model_facts.max_position_embeddings or 0
        if self.placement_plan and self.placement_plan.context_tokens:
            # The plan reserved KV for this many tokens; going beyond it is what
            # turns a comfortable placement into an out-of-memory mid-answer.
            window = min(window, self.placement_plan.context_tokens) if window                 else self.placement_plan.context_tokens

        if window:
            room = window - prompt_tokens - 16      # leave the template a margin
            if room > 0:
                limit = min(limit, room)

        return max(1, limit)

    @staticmethod
    def _as_messages(
        prompt: str,
        system_prompt: str,
        messages: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """
        Normalises the two calling styles into one conversation.

        Callers that already assembled a conversation pass it through intact;
        the older prompt/system_prompt pair is promoted into the same shape.
        """
        if messages:
            return [m for m in messages if m.get("content")]

        conversation = []
        if system_prompt:
            conversation.append({"role": "system", "content": system_prompt})
        conversation.append({"role": "user", "content": prompt})
        return conversation

    def _build_inputs(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Applies the model's chat template and moves tensors to the input device."""
        import torch

        try:
            formatted = self.tokenizer_instance.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            # No chat template: render the whole transcript rather than
            # dropping every turn but the last.
            formatted = "\n".join(
                f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
                for m in messages
            ) + "\nAssistant:"

        inputs = self.tokenizer_instance(formatted, return_tensors="pt")

        # With a sharded model, inputs must land on the device holding the
        # embedding layer, which is not necessarily cuda:0.
        target_device = None
        device_map = getattr(self.model_instance, "hf_device_map", None)
        if device_map:
            for module_name, device in device_map.items():
                if "embed" in module_name:
                    target_device = device
                    break
        if target_device is None:
            try:
                target_device = next(self.model_instance.parameters()).device
            except Exception:
                target_device = "cuda" if torch.cuda.is_available() else "cpu"

        if isinstance(target_device, int):
            target_device = f"cuda:{target_device}"

        return {
            k: v.to(target_device) if hasattr(v, "to") else v
            for k, v in inputs.items()
        }

    @staticmethod
    def _describe_load(result: Dict[str, Any]) -> str:
        """One line describing how a model was placed, for either runtime."""
        seconds = result.get("load_seconds")
        plan = result.get("plan") or {}
        if plan:
            return (
                f"Caricato in {seconds}s "
                f"({str(plan.get('quantization', '?')).upper()}, "
                f"{plan.get('total_required_gb', '?')} GB)."
            )

        settings = result.get("settings") or {}
        placement = result.get("placement") or {}
        layers = placement.get("layers_on_gpu")
        total = placement.get("layers_total")
        where = (
            "tutti i layer su GPU" if placement.get("fully_offloaded")
            else f"{layers}/{total} layer su GPU"
        )
        return (
            f"Caricato in {seconds}s "
            f"({result.get('backend', 'backend')}, {where}, "
            f"ctx {settings.get('n_ctx', '?')})."
        )

    def _format_load_failure(self, target_model: str, result: Dict[str, Any]) -> str:
        """Renders the real load failure, with guidance matched to the stage."""
        stage = result.get("stage", "load")
        error = result.get("error", "causa sconosciuta")

        hints = {
            "discovery": (
                "Apri **Model Hub** nella barra laterale per scaricare un modello, "
                "oppure seleziona un provider Cloud in **Impostazioni AI**."
            ),
            "format": (
                "Esegui `python sigma_launcher.py --install` per installare il "
                "runtime GGUF su questo hardware, oppure usa un checkpoint "
                "safetensors."
            ),
            "inspection": "Il checkpoint sembra incompleto: verifica il download.",
            "load": (
                "Se e' un errore di memoria, riduci il contesto o forza una "
                "quantizzazione piu' aggressiva dal Model Hub."
            ),
        }

        message = (
            f"❌ **SigmaEngine non ha potuto caricare `{target_model}`**\n\n"
            f"**Fase**: {stage}\n"
            f"**Causa**: `{error}`\n\n"
            f"{hints.get(stage, '')}"
        )

        plan = result.get("plan")
        if plan:
            message += (
                f"\n\n*Piano calcolato*: {plan.get('quantization', '?').upper()}, "
                f"{plan.get('total_required_gb', '?')} GB richiesti contro "
                f"{plan.get('total_vram_gb', '?')} GB di VRAM utilizzabile."
            )
        return message

    @staticmethod
    def _yield_no_model_message() -> Generator[Dict[str, Any], None, None]:
        message = (
            "⚠️ **Nessun modello AI locale presente in `data/models/`.**\n\n"
            "SigmaEngine esegue l'inferenza nativa sui pesi locali.\n\n"
            "1. Apri **Model Hub** e scarica un modello Hugging Face.\n"
            "2. Oppure configura un provider Cloud in **Impostazioni** (⚙️)."
        )
        yield {"token": message, "token_index": 1, "done": True}

    # -------------------------------------------------------------- status

    def context_window(self) -> int:
        """
        The context the resident model actually has, in tokens.

        Not what the checkpoint was trained for: what this machine could
        allocate for it. The planner shrinks the window to fit the VRAM it
        found, and a caller budgeting a conversation against the trained figure
        would build a prompt the runtime then refuses.
        """
        if self.active_backend_instance is not None:
            settings = self.active_backend_instance.telemetry() or {}
            return int(settings.get("n_ctx", 0) or 0)
        if self.placement_plan and self.placement_plan.context_tokens:
            return int(self.placement_plan.context_tokens)
        if self.model_facts and self.model_facts.max_position_embeddings:
            return int(self.model_facts.max_position_embeddings)
        return 0

    def get_status(self) -> Dict[str, Any]:
        """Returns engine state, hardware allocation and the active plan."""
        return {
            "status": "model_loaded" if self.model_instance is not None else "ready",
            "active_backend": self.active_backend,
            "loaded_model": self.loaded_model_name,
            "last_load_error": self.last_load_error,
            "hardware": self.hardware_profile,
            "model_facts": self.model_facts.to_dict() if self.model_facts else None,
            "placement_plan": (
                self.placement_plan.to_dict() if self.placement_plan else None
            ),
            "optimizations": self._generate_default_optimizations(),
            "backends": self.backend_capabilities(),
            "active_backend_name": (
                self.active_backend_instance.name
                if self.active_backend_instance else "transformers"
            ),
            "tiering_summary": self.hardware_profile.get("recommended_tiering"),
            # Real counters, not a claim: hits, misses and how much prefill the
            # cache actually removed on this machine with this conversation.
            "prefix_cache": (
                self.prefix_cache.stats() if self.prefix_cache_enabled
                else {"enabled": False}
            ),
            "generation_busy": self._generation_waiting > 0,
            "generation_queue": self._generation_waiting,
        }

    def backend_capabilities(self) -> Dict[str, Any]:
        """
        Which runtimes this machine can use, and what is missing for the rest.

        Lets the UI explain why a downloaded checkpoint cannot run here and name
        the install that would fix it, instead of failing at load time.
        """
        from core.engine.backends import capability_report

        report = capability_report(self.hardware_profile)
        report["transformers"] = {
            "available": self._module_available("transformers")
            and self._module_available("torch"),
            "reason": (
                "pronto" if self._module_available("transformers")
                else "transformers non installato"
            ),
            "formats": ["safetensors"],
            "quantization": (
                "bitsandbytes" if self._module_available("bitsandbytes")
                else "non disponibile"
            ),
        }
        return report

    def benchmark(
        self,
        prompt_tokens: int = 128,
        decode_tokens: int = 24,
        profile_modules: bool = False,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Measures real prefill and decode speed for the loaded model.

        Loads the model first if needed, so the endpoint is usable from a cold
        engine.
        """
        from core.engine.benchmark import EngineBenchmark

        if not self.has_resident_model:
            target = model_name or self.loaded_model_name
            result = self.load_native_model(target)
            if not result.get("success"):
                return {"success": False, "error": result.get("error")}

        # A registry backend owns its own model and measures itself. Routing
        # everything through the transformers benchmark is why this endpoint
        # answered "no model loaded" for every GGUF -- that is, for the format
        # most models on this machine are actually in.
        if self.active_backend_instance is not None:
            with self._generation_lock:
                return self.active_backend_instance.benchmark(
                    prompt_tokens=prompt_tokens, decode_tokens=decode_tokens,
                )

        # Measuring mutates the KV cache and competes for the device, so it
        # queues behind chat like any other generation.
        with self._generation_lock:
            self.prefix_cache.clear("benchmark run")
            return EngineBenchmark.run(
                self,
                prompt_tokens=prompt_tokens,
                decode_tokens=decode_tokens,
                profile_modules=profile_modules,
            )

    def plan_for_model(
        self,
        model_identifier: Optional[str] = None,
        context_tokens: int = 32768,
        force_quantization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes the placement plan for a model without loading it.

        Lets the UI show what will happen, and on which tiers, before paying the
        cost of a load.
        """
        model_info = self.find_valid_model_directory(model_identifier)
        if not model_info:
            return {
                "success": False,
                "error": f"Modello non trovato: {model_identifier}",
            }

        target_path, display_name = model_info
        facts = ModelInspector.inspect(target_path)
        if facts is None:
            return {"success": False, "error": f"Introspezione fallita: {target_path}"}

        plan = MemoryPlanner.build_plan(
            facts,
            self.refresh_vram(),
            context_tokens=context_tokens,
            force_quantization=force_quantization,
        )
        return {
            "success": True,
            "model_name": display_name,
            "facts": facts.to_dict(),
            "plan": plan.to_dict(),
        }

    def import_and_optimize_hf_model(
        self,
        repo_id: str,
        filename: Optional[str] = None,
        quantization: Optional[str] = None,
        hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registers a Hugging Face model and plans its hardware placement.

        When the weights are already local the plan is computed from measured
        facts; otherwise the caller is told to download first rather than being
        given invented numbers.
        """
        model_name = filename or repo_id.split("/")[-1]
        model_info = self.find_valid_model_directory(repo_id) or \
            self.find_valid_model_directory(model_name)

        if not model_info:
            return {
                "success": False,
                "error": (
                    f"'{repo_id}' non e' presente in data/models/. Scaricalo dal "
                    "Model Hub: il piano hardware viene calcolato sui pesi reali."
                ),
                "requires_download": True,
            }

        target_path, display_name = model_info
        facts = ModelInspector.inspect(target_path)
        if facts is None:
            return {"success": False, "error": f"Introspezione fallita: {target_path}"}

        plan = MemoryPlanner.build_plan(
            facts, self.refresh_vram(), force_quantization=quantization
        )

        self.loaded_model = {
            "repo_id": repo_id,
            "name": display_name,
            "path": target_path,
            "quantization": plan.quantization,
            "size_gb": round(facts.total_bytes / 2**30, 2),
            "param_count_b": round(facts.param_count / 1e9, 2),
            "backend": self.active_backend,
            "plan": plan.to_dict(),
            "facts": facts.to_dict(),
            "imported_at": time.time(),
            "status": "planned",
        }

        return {
            "success": True,
            "message": (
                f"{display_name} analizzato: {facts.param_count / 1e9:.1f}B parametri, "
                f"piano {plan.summary()}"
            ),
            "model": self.loaded_model,
        }


# Singleton engine instance. Construction is cheap: hardware probing happens on
# first access, not at import time.
sigma_engine = UniversalSigmaEngine()


@atexit.register
def _release_engine_on_exit() -> None:
    """
    Returns model memory when the program closes.

    Completes the residency contract: weights stay put across chats and are
    released on an explicit request, a switch to a different model, or here.
    """
    try:
        if sigma_engine.model_instance is not None:
            sigma_engine.unload()
    except Exception:
        # Interpreter shutdown tears down CUDA and threading in an order we do
        # not control; a failure here must never mask the real exit path.
        pass
