# ==============================================================================
# core/engine/backends/llamacpp_backend.py — GGUF runtime via llama.cpp
#
# llama.cpp is the portable half of the engine. The same GGUF runs on CUDA,
# Metal, Vulkan or plain NEON, and its kernels are fused and graph-friendly in a
# way the transformers path is not, so it stays fast on hardware that cannot
# host a full-precision checkpoint at all.
#
# The adaptation happens in how many layers go to the accelerator and how they
# are split across several of them; everything else llama.cpp handles itself.
# ==============================================================================
import os
import time
from typing import Dict, Any, Generator, List, Optional, Tuple

from core.logger import get_logger
from core.engine.model_inspector import ModelFacts, ModelInspector
from core.engine.backends.base import InferenceBackend, module_available

log = get_logger(__name__)

# Room left on each GPU for the CUDA context and per-device scratch.
_GPU_RESERVE_GB = 1.5

# llama.cpp puts more on the GPU than the layers themselves: the output and
# embedding tensors, per-device compute buffers, and the KV cache for whatever
# it offloaded. Measured on a 27B F16 split across two cards, 23 layers
# estimated at 18.0GB actually occupied 21.5GB and filled both cards to the
# last byte, which collapsed throughput to 0.2 tok/s. Sizing layers by their
# raw bytes alone reliably overcommits, so the estimate carries that margin.
_GGUF_OVERHEAD_FACTOR = 1.20
# Fraction of physical cores used when running on CPU. Leaving one core free
# keeps the host responsive, which matters most on the small boards where the
# CPU path is the only path.
_CPU_THREAD_HEADROOM = 1


class LlamaCppBackend(InferenceBackend):
    """Runs GGUF checkpoints through llama-cpp-python."""

    name = "llama_cpp"
    supported_formats = ("gguf",)

    def __init__(self):
        self._llm = None
        self._facts: Optional[ModelFacts] = None
        self._settings: Dict[str, Any] = {}

    # --------------------------------------------------------- capabilities

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        if not module_available("llama_cpp"):
            return False, (
                "llama-cpp-python non installato. Wheel precompilate CUDA: "
                "pip install llama-cpp-python "
                "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125"
            )
        return True, "pronto"

    @classmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """
        GGUF is llama.cpp's native format, so it always wins for it. The margin
        widens without a CUDA GPU, where the alternative would be float32 on the
        CPU rather than quantized kernels.
        """
        has_cuda = any(
            a.get("type") == "NVIDIA_CUDA"
            for a in hardware.get("accelerators", [])
        )
        return 90 if has_cuda else 100

    # -------------------------------------------------------------- runtime

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def load(
        self,
        facts: ModelFacts,
        hardware: Dict[str, Any],
        context_tokens: int = 8192,
        **options,
    ) -> Dict[str, Any]:
        available, reason = self.availability()
        if not available:
            return {"success": False, "error": reason, "stage": "availability"}

        model_file = self._resolve_gguf_file(facts)
        if not model_file:
            return {
                "success": False,
                "error": f"Nessun file .gguf trovato in {facts.path}",
                "stage": "discovery",
            }

        settings = self._plan_settings(facts, hardware, context_tokens)

        try:
            from llama_cpp import Llama

            t0 = time.perf_counter()
            self._llm = Llama(
                model_path=model_file,
                n_gpu_layers=settings["n_gpu_layers"],
                tensor_split=settings["tensor_split"],
                n_ctx=settings["n_ctx"],
                n_threads=settings["n_threads"],
                n_batch=settings["n_batch"],
                flash_attn=settings["flash_attn"],
                verbose=False,
            )
            load_seconds = round(time.perf_counter() - t0, 2)
        except Exception as exc:
            self._llm = None
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "stage": "load",
                "settings": settings,
            }

        self._facts = facts
        self._settings = dict(settings, load_seconds=load_seconds)

        log.info(
            "[LlamaCpp] Loaded '%s' in %.2fs | %s/%s layers on GPU | ctx %d",
            facts.name, load_seconds, settings["n_gpu_layers"],
            facts.num_hidden_layers or "?", settings["n_ctx"],
        )
        return {
            "success": True,
            "backend": self.name,
            "model_name": facts.name,
            "load_seconds": load_seconds,
            "settings": settings,
            "placement": self.describe_placement(),
        }

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        if self._llm is None:
            yield {
                "token": "❌ **LlamaCpp**: nessun modello caricato.",
                "token_index": 1,
                "done": True,
            }
            return

        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

        t_start = time.perf_counter()
        token_count = 0
        first_token_sent = False

        try:
            stream = self._llm.create_chat_completion(
                messages=messages,
                temperature=max(temperature, 0.0),
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content")
                if not text:
                    continue

                token_count += 1
                now = time.perf_counter()
                payload: Dict[str, Any] = {
                    "token": text,
                    "token_index": token_count,
                    "speed_tok_s": round(token_count / max(now - t_start, 1e-3), 1),
                    "done": False,
                }
                if not first_token_sent:
                    payload["ttft_ms"] = round((now - t_start) * 1000, 1)
                    first_token_sent = True
                yield payload

            elapsed = time.perf_counter() - t_start
            yield {
                "token": "",
                "token_index": token_count + 1,
                "speed_tok_s": round(token_count / max(elapsed, 1e-3), 1),
                "total_tokens": token_count,
                "done": True,
            }

        except Exception as exc:
            log.error("[LlamaCpp] Generation failed: %s", exc, exc_info=True)
            yield {
                "token": f"\n\n❌ **Errore LlamaCpp**: {type(exc).__name__}: {exc}",
                "token_index": token_count + 1,
                "done": True,
            }

    def unload(self) -> Dict[str, Any]:
        previous = self._facts.name if self._facts else None
        if self._llm is not None:
            try:
                self._llm.close()
            except Exception as exc:
                log.debug("[LlamaCpp] close() skipped: %s", exc)
        self._llm = None
        self._facts = None
        self._settings = {}
        return {"success": True, "unloaded": previous}

    def describe_placement(self) -> Dict[str, Any]:
        if not self._settings:
            return {}
        total = self._facts.num_hidden_layers if self._facts else 0
        offloaded = self._settings.get("n_gpu_layers", 0)
        return {
            "mode": "llama_cpp",
            "layers_total": total,
            "layers_on_gpu": offloaded,
            "layers_on_cpu": max(total - offloaded, 0) if offloaded >= 0 else 0,
            "tensor_split": self._settings.get("tensor_split"),
            "fully_offloaded": offloaded < 0 or (total and offloaded >= total),
        }

    def telemetry(self) -> Dict[str, Any]:
        return dict(self._settings)

    # ------------------------------------------------------------ planning

    @staticmethod
    def _resolve_gguf_file(facts: ModelFacts) -> Optional[str]:
        """Picks the GGUF to load, preferring the first shard of a split set."""
        if os.path.isfile(facts.path) and facts.path.endswith(".gguf"):
            return facts.path
        if not os.path.isdir(facts.path):
            return None

        candidates = sorted(f for f in os.listdir(facts.path) if f.endswith(".gguf"))
        if not candidates:
            return None
        # llama.cpp opens a split model from its first part and finds the rest.
        first_shard = [c for c in candidates if "00001-of-" in c]
        return os.path.join(facts.path, (first_shard or candidates)[0])

    @classmethod
    def _plan_settings(
        cls, facts: ModelFacts, hardware: Dict[str, Any], context_tokens: int
    ) -> Dict[str, Any]:
        """
        Chooses offload depth, split and threading for this machine.

        The single decision that matters is how many layers reach the
        accelerator: everything left behind is read over the host bus on every
        token.
        """
        accelerators = hardware.get("accelerators", [])
        cpu = hardware.get("cpu", {})
        system = hardware.get("system", {})

        gpus = [
            a for a in accelerators
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM") and "free_vram_gb" in a
        ]
        gpus.sort(
            key=lambda a: (a.get("multi_processor_count", 0), a.get("free_vram_gb", 0)),
            reverse=True,
        )

        n_ctx = cls._clamp_context(facts, context_tokens)
        physical_cores = int(cpu.get("cores_physical", 4) or 4)
        n_threads = max(physical_cores - _CPU_THREAD_HEADROOM, 1)

        # Apple silicon shares one memory pool, so everything goes to the GPU.
        if any(a.get("type") == "APPLE_MPS" for a in accelerators):
            return {
                "n_gpu_layers": -1, "tensor_split": None, "n_ctx": n_ctx,
                "n_threads": n_threads, "n_batch": 512, "flash_attn": True,
                "device": "metal",
            }

        if not gpus:
            # CPU-only, which is the normal case on ARM boards. Smaller batches
            # keep peak memory down where there is little of it to spare.
            is_arm = bool(system.get("is_arm") or system.get("is_raspberry_pi"))
            return {
                "n_gpu_layers": 0, "tensor_split": None, "n_ctx": n_ctx,
                "n_threads": n_threads, "n_batch": 128 if is_arm else 512,
                "flash_attn": False,
                "device": "arm_neon" if is_arm else "cpu",
            }

        usable = [max(g.get("free_vram_gb", 0.0) - _GPU_RESERVE_GB, 0.0) for g in gpus]
        total_usable = sum(usable)
        kv_gb = ModelInspector.estimate_kv_cache_gb(facts, n_ctx)
        weights_gb = facts.total_bytes / 2**30
        layers = facts.num_hidden_layers or 0

        if layers and (weights_gb * _GGUF_OVERHEAD_FACTOR + kv_gb) > total_usable:
            per_layer = (weights_gb / layers) * _GGUF_OVERHEAD_FACTOR
            budget = max(total_usable - kv_gb, 0.0)
            n_gpu_layers = max(int(budget / max(per_layer, 1e-6)), 0)
            n_gpu_layers = min(n_gpu_layers, layers)
        else:
            n_gpu_layers = -1                      # everything fits: offload all

        tensor_split = None
        if len(gpus) > 1 and total_usable > 0:
            tensor_split = [round(u / total_usable, 4) for u in usable]

        settings = {
            "n_gpu_layers": n_gpu_layers,
            "tensor_split": tensor_split,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            "n_batch": 512,
            "flash_attn": True,
            "device": "cuda",
            "usable_vram_gb": round(total_usable, 2),
            "weights_gb": round(weights_gb, 2),
            "kv_cache_gb": kv_gb,
        }
        if 0 <= n_gpu_layers < layers:
            settings["warning"] = (
                f"Solo {n_gpu_layers} dei {layers} layer stanno in VRAM: i "
                "restanti girano dalla RAM di sistema, circa dieci volte piu' "
                "lentamente. Una quantizzazione piu' compatta entrerebbe tutta."
            )
        return settings

    @staticmethod
    def _clamp_context(facts: ModelFacts, requested: int) -> int:
        """Keeps the context within what the checkpoint was trained for."""
        trained = facts.max_position_embeddings or 0
        if trained and requested > trained:
            return trained
        return max(requested, 512)
