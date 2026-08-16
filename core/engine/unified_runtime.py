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
        self.model_instance = None
        self.tokenizer_instance = None
        self.model_facts: Optional[ModelFacts] = None
        self.placement_plan: Optional[PlacementPlan] = None
        self.last_load_error: Optional[str] = None
        self.last_device_map_report: Optional[Dict[str, Any]] = None
        self._load_lock = threading.Lock()

    # ------------------------------------------------------------- hardware

    @property
    def hardware_profile(self) -> Dict[str, Any]:
        if self._hardware_profile is None:
            self._hardware_profile = UniversalHardwareProbe.probe_all()
            log.info(
                "[SigmaEngine] Kernel initialized. Active backend: %s",
                self.active_backend,
            )
        return self._hardware_profile

    @hardware_profile.setter
    def hardware_profile(self, value: Dict[str, Any]) -> None:
        self._hardware_profile = value
        self._active_backend = None

    @property
    def active_backend(self) -> str:
        if self._active_backend is None:
            self._active_backend = self._determine_optimal_backend()
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
        accs = (self._hardware_profile or {}).get("accelerators", [])
        system = (self._hardware_profile or {}).get("system", {})
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
        Returns (target_path, display_name) or None.
        """
        models_dir = os.path.join(os.getcwd(), "data", "models")
        if not os.path.exists(models_dir):
            return None

        if model_identifier:
            candidates = [
                model_identifier,
                model_identifier.replace("/", "--"),
                model_identifier.replace(":", "-"),
                model_identifier.split("/")[-1],
                model_identifier.split(":")[0],
            ]
            for cand in candidates:
                p = os.path.join(models_dir, cand)
                if self._folder_has_weights(p):
                    return p, cand

            clean_id = "".join(c for c in model_identifier.lower() if c.isalnum())
            for folder in os.listdir(models_dir):
                p = os.path.join(models_dir, folder)
                if self._folder_has_weights(p):
                    clean_folder = "".join(c for c in folder.lower() if c.isalnum())
                    if clean_id in clean_folder or clean_folder in clean_id:
                        return p, folder

        for folder in sorted(os.listdir(models_dir)):
            p = os.path.join(models_dir, folder)
            if self._folder_has_weights(p):
                return p, folder

        return None

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

        if facts.weight_format == "gguf":
            error = (
                f"'{display_name}' e' in formato GGUF, che richiede llama-cpp-python "
                "(non installato). Usa un checkpoint safetensors oppure installa "
                "llama-cpp-python."
            )
            self.last_load_error = error
            log.error("[SigmaEngine] %s", error)
            return {"success": False, "error": error, "stage": "format"}

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

        # A VRAM-only plan that the runtime rejects is recoverable: replan with a
        # host-RAM budget rather than leaving the user with no model at all.
        if model is None and has_cuda and plan.fits_in_vram:
            log.warning(
                "[SigmaEngine] VRAM-only placement rejected (%s). "
                "Retrying with host RAM spill.", load_error,
            )
            plan = MemoryPlanner.build_plan(
                facts,
                profile,
                context_tokens=context_tokens,
                force_quantization=force_quantization,
                allow_host_spill=True,
            )
            plan.warnings.append(
                "VRAM-only placement was rejected by the runtime; part of the "
                "model now sits in system RAM, which is slower."
            )
            model, load_error = self._attempt_load(
                model_cls, target_path, plan, compute_dtype, has_cuda
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

        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception as exc:
            log.debug("[SigmaEngine] Cache clear skipped: %s", exc)

        freed_gb = round((freed_before - self._vram_used_bytes()) / 2**30, 2)
        log.info("[SigmaEngine] Unloaded '%s', freed %.2f GB VRAM", previous, freed_gb)
        return {"success": True, "unloaded": previous, "freed_vram_gb": freed_gb}

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

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        model_name: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Streams tokens from native PyTorch inference with live throughput metrics."""
        t_start = time.perf_counter()
        token_count = 0

        model_info = self.find_valid_model_directory(model_name or self.loaded_model_name)
        target_model = model_info[1] if model_info else (model_name or self.loaded_model_name)

        if target_model is None:
            yield from self._yield_no_model_message()
            return

        if self.model_instance is None or self.loaded_model_name != target_model:
            yield {
                "token": (
                    f"⏳ *[SigmaEngine]* Caricamento `{target_model}` "
                    "sui tier di memoria disponibili...\n\n"
                ),
                "token_index": 1,
                "done": False,
            }
            result = self.load_native_model(target_model)
            if not result.get("success"):
                yield {
                    "token": self._format_load_failure(target_model, result),
                    "token_index": 2,
                    "done": True,
                }
                return

            plan = result.get("plan", {})
            yield {
                "token": (
                    f"✅ Caricato in {result.get('load_seconds')}s "
                    f"({plan.get('quantization', '?').upper()}, "
                    f"{plan.get('total_required_gb', '?')} GB).\n\n"
                ),
                "token_index": 2,
                "done": False,
            }

        try:
            import torch
            from transformers import TextIteratorStreamer

            streamer = TextIteratorStreamer(
                self.tokenizer_instance,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=300.0,
            )

            inputs = self._build_inputs(prompt, system_prompt)
            do_sample = temperature is not None and temperature > 0

            gen_kwargs: Dict[str, Any] = dict(
                **inputs,
                streamer=streamer,
                max_new_tokens=max(1, min(max_tokens or 4096, 16384)),
                do_sample=do_sample,
                use_cache=True,
            )
            # Sampling knobs are invalid without sampling and emit warnings.
            if do_sample:
                gen_kwargs["temperature"] = temperature
                gen_kwargs["top_p"] = 0.95

            pad_id = getattr(self.tokenizer_instance, "pad_token_id", None)
            eos_id = getattr(self.tokenizer_instance, "eos_token_id", None)
            gen_kwargs["pad_token_id"] = pad_id if pad_id is not None else eos_id

            generation_error: List[BaseException] = []

            def _run_generate():
                try:
                    with torch.inference_mode():
                        self.model_instance.generate(**gen_kwargs)
                except BaseException as exc:  # surfaced to the caller below
                    log.error("[SigmaEngine] Generation thread failed: %s", exc)
                    generation_error.append(exc)
                    streamer.end()

            thread = threading.Thread(target=_run_generate, daemon=True)
            thread.start()

            first_token_sent = False
            for token_text in streamer:
                if not token_text:
                    continue
                token_count += 1
                now = time.perf_counter()

                chunk: Dict[str, Any] = {
                    "token": token_text,
                    "token_index": token_count,
                    "speed_tok_s": round(token_count / max(now - t_start, 0.001), 1),
                    "done": False,
                }
                if not first_token_sent:
                    chunk["ttft_ms"] = round((now - t_start) * 1000, 1)
                    first_token_sent = True
                yield chunk

            thread.join(timeout=5.0)

            if generation_error:
                yield {
                    "token": f"\n\n❌ **Errore GPU durante la generazione**: "
                             f"{type(generation_error[0]).__name__}: {generation_error[0]}",
                    "token_index": token_count + 1,
                    "done": True,
                }
                return

            elapsed = time.perf_counter() - t_start
            yield {
                "token": "",
                "token_index": token_count + 1,
                "speed_tok_s": round(token_count / max(elapsed, 0.001), 1),
                "total_tokens": token_count,
                "done": True,
            }

        except Exception as exc:
            log.error("[SigmaEngine] Generation error: %s", exc, exc_info=True)
            yield {
                "token": f"\n\n❌ **Errore SigmaEngine**: {type(exc).__name__}: {exc}",
                "token_index": token_count + 1,
                "done": True,
            }

    def _build_inputs(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Applies the model's chat template and moves tensors to the input device."""
        import torch

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            formatted = self.tokenizer_instance.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            formatted = f"System: {system_prompt}\nUser: {prompt}\nAssistant:"

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

    def _format_load_failure(self, target_model: str, result: Dict[str, Any]) -> str:
        """Renders the real load failure, with guidance matched to the stage."""
        stage = result.get("stage", "load")
        error = result.get("error", "causa sconosciuta")

        hints = {
            "discovery": (
                "Apri **Model Hub** nella barra laterale per scaricare un modello, "
                "oppure seleziona un provider Cloud in **Impostazioni AI**."
            ),
            "format": "Installa `llama-cpp-python` oppure usa un checkpoint safetensors.",
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
            "tiering_summary": self.hardware_profile.get("recommended_tiering"),
        }

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
