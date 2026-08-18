# ==============================================================================
# core/engine/benchmark.py — On-host inference benchmark
#
# Optimisation decisions (which backend, which precision, how to split layers)
# depend on numbers that differ per machine. This measures them on the host
# actually running the model, rather than assuming figures from another setup.
#
# Two numbers matter and they behave differently:
#   - prefill  is compute bound and scales with batched matmul throughput
#   - decode   is memory-bandwidth bound in theory, but on small models or
#              heavily-dispatched ones it is dominated by per-kernel launch
#              overhead instead. The ratio between measured and bandwidth-implied
#              decode time is what tells the two cases apart.
# ==============================================================================
import time
from typing import Dict, Any, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

# Sequential-read bandwidth by GPU family, GB/s. Used only to compute the
# bandwidth ceiling a placement implies; measured numbers always take priority.
_GPU_BANDWIDTH_GB_S = {
    "5090": 1792.0, "5080": 960.0, "5070 ti": 896.0, "5070": 672.0,
    "5060 ti": 448.0, "5060": 448.0,
    "4090": 1008.0, "4080": 717.0, "4070": 504.0, "4060": 272.0,
    "3090": 936.0, "3080": 760.0, "3070": 448.0, "3060": 360.0,
    "a100": 1935.0, "h100": 3350.0, "l40": 864.0,
}
_DEFAULT_BANDWIDTH_GB_S = 400.0

# Modules worth timing individually. Anything not covered lands in "other",
# which is where launch overhead becomes visible.
_PROFILED_SUFFIXES = (
    "linear_attn", "self_attn", "mlp", "lm_head", "embed_tokens", "visual",
)


class EngineBenchmark:
    """Measures real prefill and decode performance for a loaded model."""

    @classmethod
    def run(
        cls,
        engine,
        prompt_tokens: int = 128,
        decode_tokens: int = 24,
        profile_modules: bool = False,
    ) -> Dict[str, Any]:
        """
        Benchmarks the currently loaded model.

        profile_modules attaches per-module CUDA events. Those events serialise
        the pipeline and inflate wall time by roughly 15-20%, so the breakdown
        is reported as proportions and the headline tok/s always comes from the
        uninstrumented pass.
        """
        if engine.model_instance is None or engine.tokenizer_instance is None:
            return {"success": False, "error": "Nessun modello caricato."}

        try:
            import torch
        except ImportError:
            return {"success": False, "error": "torch non disponibile."}

        model = engine.model_instance
        tokenizer = engine.tokenizer_instance

        try:
            device = next(model.parameters()).device
            input_ids = cls._make_input(tokenizer, prompt_tokens, device, torch)

            prefill = cls._measure_prefill(model, input_ids, torch)
            decode = cls._measure_decode(model, input_ids, decode_tokens, torch)

            result: Dict[str, Any] = {
                "success": True,
                "model": engine.loaded_model_name,
                "quantization": (
                    engine.placement_plan.quantization if engine.placement_plan else None
                ),
                "prompt_tokens": int(input_ids.shape[1]),
                "prefill": prefill,
                "decode": decode,
                "placement": cls._placement_bytes(model, torch),
            }

            result["bandwidth_ceiling"] = cls._bandwidth_ceiling(
                engine, result["placement"], decode
            )

            if profile_modules:
                result["module_breakdown"] = cls._profile_modules(
                    model, input_ids, torch
                )

            result["verdict"] = cls._verdict(result)
            log.info(
                "[Benchmark] %s: prefill %.0f tok/s, decode %.1f tok/s (%s)",
                engine.loaded_model_name,
                prefill["tokens_per_second"],
                decode["tokens_per_second"],
                result["verdict"]["bound_by"],
            )
            return result

        except Exception as exc:
            log.error("[Benchmark] Failed: %s", exc, exc_info=True)
            return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    # --------------------------------------------------------------- phases

    @staticmethod
    def _make_input(tokenizer, prompt_tokens: int, device, torch):
        """Builds a prompt of approximately the requested token count."""
        seed = "Il sistema analizza i dati e produce un risultato accurato. "
        text = seed * max(1, prompt_tokens // 12)
        ids = tokenizer(text, return_tensors="pt").input_ids[:, :prompt_tokens]
        return ids.to(device)

    @staticmethod
    def _measure_prefill(model, input_ids, torch) -> Dict[str, Any]:
        with torch.inference_mode():
            for _ in range(2):                       # warm up caches and kernels
                model(input_ids, use_cache=True)
            torch.cuda.synchronize()

            t0 = time.perf_counter()
            model(input_ids, use_cache=True)
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0

        n = int(input_ids.shape[1])
        return {
            "tokens": n,
            "seconds": round(elapsed, 4),
            "tokens_per_second": round(n / max(elapsed, 1e-6), 1),
            "ms_per_token": round(elapsed * 1000 / n, 3),
        }

    @staticmethod
    def _measure_decode(model, input_ids, steps: int, torch) -> Dict[str, Any]:
        with torch.inference_mode():
            out = model(input_ids, use_cache=True)
            past = out.past_key_values
            nxt = out.logits[:, -1:].argmax(-1)

            for _ in range(3):                       # warm up the decode path
                out = model(nxt, past_key_values=past, use_cache=True)
                past = out.past_key_values
                nxt = out.logits[:, -1:].argmax(-1)
            torch.cuda.synchronize()

            t0 = time.perf_counter()
            for _ in range(steps):
                out = model(nxt, past_key_values=past, use_cache=True)
                past = out.past_key_values
                nxt = out.logits[:, -1:].argmax(-1)
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - t0

        per_token = elapsed / max(steps, 1)
        return {
            "steps": steps,
            "ms_per_token": round(per_token * 1000, 2),
            "tokens_per_second": round(1.0 / max(per_token, 1e-6), 1),
        }

    # -------------------------------------------------------------- context

    @staticmethod
    def _placement_bytes(model, torch) -> Dict[str, float]:
        """Weight bytes actually resident on each device."""
        per_device: Dict[str, int] = {}
        for _, tensor in list(model.named_parameters()) + list(model.named_buffers()):
            key = str(tensor.device)
            per_device[key] = per_device.get(key, 0) + tensor.numel() * tensor.element_size()
        return {k: round(v / 2**30, 2) for k, v in sorted(per_device.items())}

    @classmethod
    def _bandwidth_ceiling(
        cls, engine, placement: Dict[str, float], decode: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fastest possible decode for this placement, if every byte of weights were
        read at the device's peak bandwidth.

        Devices are summed rather than maxed: a layer-split model runs its
        devices in sequence within a token, not in parallel.
        """
        accelerators = engine.hardware_profile.get("accelerators", [])
        by_index = {
            str(a.get("device_id")): a.get("name", "") for a in accelerators
        }

        total_seconds = 0.0
        detail: List[Dict[str, Any]] = []
        for device, gb in placement.items():
            if not device.startswith("cuda"):
                # Host or disk residency is far slower; treat it as unbounded
                # here and let the verdict flag it instead of guessing a number.
                detail.append({"device": device, "weights_gb": gb, "bandwidth_gb_s": None})
                continue
            index = device.split(":")[-1]
            bandwidth = cls._bandwidth_for(by_index.get(index, ""))
            total_seconds += gb / bandwidth
            detail.append({
                "device": device, "weights_gb": gb, "bandwidth_gb_s": bandwidth,
            })

        ms = total_seconds * 1000
        measured = decode["ms_per_token"]
        return {
            "ms_per_token": round(ms, 2),
            "tokens_per_second": round(1000 / ms, 1) if ms > 0 else None,
            "efficiency_percent": round(100 * ms / measured, 1) if measured else None,
            "devices": detail,
        }

    @staticmethod
    def _bandwidth_for(gpu_name: str) -> float:
        name = gpu_name.lower()
        for key, value in _GPU_BANDWIDTH_GB_S.items():
            if key in name:
                return value
        return _DEFAULT_BANDWIDTH_GB_S

    @classmethod
    def _profile_modules(cls, model, input_ids, torch) -> Dict[str, Any]:
        """
        Times each major submodule with CUDA events over a few decode steps.

        Whatever is left over after summing these ("other") is layernorms,
        residual adds, device-dispatch hooks and Python overhead. A large
        "other" means the model is launch bound, not bandwidth bound.
        """
        import collections

        totals: collections.defaultdict = collections.defaultdict(float)
        counts: collections.defaultdict = collections.defaultdict(int)
        pending: Dict[str, Any] = {}
        handles = []

        def classify(name: str) -> Optional[str]:
            for suffix in _PROFILED_SUFFIXES:
                if name.endswith(suffix):
                    return suffix
            return None

        def make_pre(name):
            def hook(_module, _inputs):
                event = torch.cuda.Event(enable_timing=True)
                event.record()
                pending[name] = event
            return hook

        def make_post(name, kind):
            def hook(_module, _inputs, _output):
                start = pending.pop(name, None)
                if start is None:
                    return
                event = torch.cuda.Event(enable_timing=True)
                event.record()
                event.synchronize()
                totals[kind] += start.elapsed_time(event)
                counts[kind] += 1
            return hook

        for name, module in model.named_modules():
            kind = classify(name)
            if kind:
                handles.append(module.register_forward_pre_hook(make_pre(name)))
                handles.append(module.register_forward_hook(make_post(name, kind)))

        steps = 8
        try:
            with torch.inference_mode():
                out = model(input_ids, use_cache=True)
                past = out.past_key_values
                nxt = out.logits[:, -1:].argmax(-1)

                totals.clear()
                counts.clear()
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                for _ in range(steps):
                    out = model(nxt, past_key_values=past, use_cache=True)
                    past = out.past_key_values
                    nxt = out.logits[:, -1:].argmax(-1)
                torch.cuda.synchronize()
                instrumented_ms = (time.perf_counter() - t0) / steps * 1000
        finally:
            for handle in handles:
                handle.remove()

        modules = {
            kind: {
                "ms_per_token": round(value / steps, 2),
                "calls_per_token": round(counts[kind] / steps),
                "percent": round(100 * (value / steps) / instrumented_ms, 1),
            }
            for kind, value in sorted(totals.items(), key=lambda kv: -kv[1])
        }
        accounted = sum(m["ms_per_token"] for m in modules.values())

        return {
            "instrumented_ms_per_token": round(instrumented_ms, 2),
            "note": (
                "CUDA events serialise execution; this pass runs ~15-20% slower "
                "than the headline decode figure. Use the proportions, not the "
                "absolute milliseconds."
            ),
            "modules": modules,
            "other": {
                "ms_per_token": round(instrumented_ms - accounted, 2),
                "percent": round(
                    100 * (instrumented_ms - accounted) / instrumented_ms, 1
                ),
                "contains": "layernorms, residual adds, dispatch hooks, Python overhead",
            },
        }

    @staticmethod
    def _verdict(result: Dict[str, Any]) -> Dict[str, Any]:
        """Turns the numbers into the one conclusion that guides tuning."""
        placement = result["placement"]
        ceiling = result["bandwidth_ceiling"]
        efficiency = ceiling.get("efficiency_percent")

        off_gpu = [d for d in placement if not d.startswith("cuda")]
        if off_gpu and any(placement[d] > 0.5 for d in off_gpu):
            return {
                "bound_by": "host_memory",
                "detail": (
                    f"{sum(placement[d] for d in off_gpu):.1f}GB of weights sit "
                    f"outside VRAM ({', '.join(off_gpu)}). Every token crosses "
                    "PCIe; nothing else matters until this is fixed."
                ),
            }

        if efficiency is None:
            return {"bound_by": "unknown", "detail": "No bandwidth ceiling available."}

        if efficiency >= 60:
            return {
                "bound_by": "memory_bandwidth",
                "detail": (
                    f"Running at {efficiency}% of the bandwidth ceiling. Close to "
                    "the hardware limit; further gains need a smaller model or "
                    "fewer bytes per weight."
                ),
            }

        return {
            "bound_by": "kernel_launch_overhead",
            "detail": (
                f"Only {efficiency}% of the bandwidth ceiling. Time is going to "
                "many small kernels rather than reading weights, so a backend "
                "with fused kernels or CUDA graphs would help more than any "
                "change to placement or quantization."
            ),
        }
