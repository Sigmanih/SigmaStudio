# ==============================================================================
# core/engine/device_map_builder.py — Explicit, repaired device maps
#
# Builds the module->device assignment ourselves instead of handing transformers
# a string strategy. Two reasons:
#
#  1. device_map="auto" routes through get_balanced_memory, which caps every GPU
#     but the last at roughly total_size/num_devices. On asymmetric cards that
#     throws away the big GPU's capacity.
#  2. Neither "auto" nor "sequential" knows that some modules are far more
#     expensive to exile than others. lm_head runs a hidden_size x vocab_size
#     matmul for every generated token; leaving it on the CPU costs more than
#     leaving a dozen decoder layers there.
# ==============================================================================
from typing import Dict, Any, List, Optional, Tuple

from core.logger import get_logger
from core.engine.model_inspector import ModelFacts
from core.engine.memory_planner import PlacementPlan

log = get_logger(__name__)

# Modules whose cost is paid once per token rather than once per layer. These
# stay on an accelerator while any GPU room remains.
_CRITICAL_SUBSTRINGS = ("lm_head", "embed_tokens", "embed_in", "wte")

# Slack a device must retain after taking a rescued module, covering the gap
# between estimated tensor sizes and real allocation.
_REPAIR_MARGIN_BYTES = int(0.4 * 2**30)


class DeviceMapBuilder:
    """Computes and repairs an explicit device map for a planned load."""

    @classmethod
    def build(
        cls,
        model_cls,
        config,
        facts: ModelFacts,
        plan: PlacementPlan,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Returns (device_map, report), or None if the map cannot be computed and
        the caller should fall back to a library strategy.
        """
        try:
            import torch
            from accelerate import init_empty_weights
            from accelerate.utils import (
                infer_auto_device_map, compute_module_sizes, CustomDtype,
            )
        except Exception as exc:
            log.warning("[DeviceMapBuilder] accelerate unavailable: %s", exc)
            return None

        try:
            with init_empty_weights():
                skeleton = model_cls._from_config(config)
        except Exception as exc:
            log.warning("[DeviceMapBuilder] Cannot build meta skeleton: %s", exc)
            return None

        no_split = list(skeleton._no_split_modules or [])
        special_dtypes = cls._special_dtypes(skeleton, plan, torch)
        weight_dtype = cls._weight_dtype(plan, torch, CustomDtype)

        try:
            sizes = compute_module_sizes(
                skeleton, dtype=weight_dtype, special_dtypes=special_dtypes
            )
            max_memory = cls._max_memory_bytes(plan)

            device_map = infer_auto_device_map(
                skeleton,
                max_memory=max_memory,
                no_split_module_classes=no_split,
                dtype=weight_dtype,
                special_dtypes=special_dtypes,
            )
        except Exception as exc:
            log.warning("[DeviceMapBuilder] Inference failed: %s", exc)
            return None

        device_map, moves = cls._repair_critical_modules(
            device_map, sizes, max_memory
        )

        report = cls._build_report(device_map, sizes, max_memory, moves)
        log.info(
            "[DeviceMapBuilder] %s | %s",
            report["summary"],
            f"{len(moves)} repair(s)" if moves else "no repairs needed",
        )
        return device_map, report

    # ------------------------------------------------------------- internals

    @staticmethod
    def _special_dtypes(skeleton, plan: PlacementPlan, torch) -> Dict[str, Any]:
        """
        Names the parameters bitsandbytes will NOT quantize, so the size model
        matches what actually lands in memory.

        Embeddings, lm_head, norms and conv kernels stay in compute dtype; on a
        large-vocab model that is several GB, and ignoring it makes every plan
        optimistic.
        """
        if plan.quantization not in ("nf4", "fp4", "int8"):
            return {}

        compute_dtype = torch.bfloat16
        special: Dict[str, Any] = {}
        for name, param in skeleton.named_parameters():
            stays_resident = (
                param.ndim != 2
                or any(hint in name for hint in _CRITICAL_SUBSTRINGS)
            )
            if stays_resident:
                special[name] = compute_dtype
        return special

    @staticmethod
    def _weight_dtype(plan: PlacementPlan, torch, CustomDtype):
        if plan.quantization in ("nf4", "fp4"):
            return CustomDtype.INT4
        if plan.quantization == "int8":
            return torch.int8
        return torch.bfloat16

    @staticmethod
    def _max_memory_bytes(plan: PlacementPlan) -> Dict[Any, int]:
        """
        Converts the plan's budgets into the byte dict accelerate expects.

        These are the raw planned budgets: an explicit device map bypasses
        transformers' quantizer haircut, so no compensation is applied here.
        """
        max_memory: Dict[Any, int] = {}
        for key, value in plan.max_memory.items():
            gib = float(str(value).replace("GiB", "").strip())
            max_memory[key] = int(gib * (1024 ** 3))
        return max_memory

    @classmethod
    def _repair_critical_modules(
        cls,
        device_map: Dict[str, Any],
        sizes: Dict[str, int],
        max_memory: Dict[Any, int],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Pulls per-token modules back onto a GPU, evicting cheaper modules if
        needed. Eviction prefers the largest non-critical module so the fewest
        modules move.
        """
        gpu_devices = [d for d in max_memory if isinstance(d, int)]
        if not gpu_devices:
            return device_map, []

        used = cls._usage_by_device(device_map, sizes)
        moves: List[Dict[str, Any]] = []

        exiled_critical = [
            name for name, device in device_map.items()
            if str(device) in ("cpu", "disk") and cls._is_critical(name)
        ]

        for name in exiled_critical:
            needed = sizes.get(name, 0)
            if not needed:
                continue

            target = cls._device_with_room(gpu_devices, used, max_memory, needed)

            if target is None:
                target = cls._evict_for(
                    name, needed, device_map, sizes, used, max_memory,
                    gpu_devices, moves,
                )
            if target is None:
                log.warning(
                    "[DeviceMapBuilder] Could not rescue '%s' (%.2f GB) onto a GPU",
                    name, needed / 2**30,
                )
                continue

            origin = str(device_map[name])
            device_map[name] = target
            used[target] = used.get(target, 0) + needed
            used[origin] = max(used.get(origin, 0) - needed, 0)
            moves.append({
                "module": name,
                "from": origin,
                "to": target,
                "size_gb": round(needed / 2**30, 2),
                "reason": "per-token module kept off CPU",
            })

        return device_map, moves

    @staticmethod
    def _usage_by_device(
        device_map: Dict[str, Any], sizes: Dict[str, int]
    ) -> Dict[Any, int]:
        used: Dict[Any, int] = {}
        for name, device in device_map.items():
            used[device] = used.get(device, 0) + sizes.get(name, 0)
        return used

    @staticmethod
    def _device_with_room(
        gpu_devices: List[int],
        used: Dict[Any, int],
        max_memory: Dict[Any, int],
        needed: int,
    ) -> Optional[int]:
        """
        Returns the GPU with the most free budget that can take `needed`.

        Requires a margin beyond the module's own size: these budgets come from
        estimated tensor sizes and a VRAM reading taken before the load began.
        Filling a device to exactly its budget leaves nothing for the difference
        and the module OOMs while being materialised.
        """
        candidates = [
            (max_memory[d] - used.get(d, 0), d)
            for d in gpu_devices
            if max_memory[d] - used.get(d, 0) >= needed + _REPAIR_MARGIN_BYTES
        ]
        if not candidates:
            return None
        return max(candidates)[1]

    @classmethod
    def _evict_for(
        cls,
        critical_name: str,
        needed: int,
        device_map: Dict[str, Any],
        sizes: Dict[str, int],
        used: Dict[Any, int],
        max_memory: Dict[Any, int],
        gpu_devices: List[int],
        moves: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Frees room on the roomiest GPU by exiling non-critical modules to CPU.
        Returns the device that now has space, or None if it cannot be freed.
        """
        target = max(gpu_devices, key=lambda d: max_memory[d] - used.get(d, 0))
        shortfall = needed - (max_memory[target] - used.get(target, 0))
        if shortfall <= 0:
            return target

        evictable = sorted(
            (
                (sizes.get(n, 0), n) for n, d in device_map.items()
                if d == target and not cls._is_critical(n) and sizes.get(n, 0) > 0
            ),
            reverse=True,
        )

        for size, name in evictable:
            if shortfall <= 0:
                break
            device_map[name] = "cpu"
            used[target] -= size
            used["cpu"] = used.get("cpu", 0) + size
            shortfall -= size
            moves.append({
                "module": name,
                "from": str(target),
                "to": "cpu",
                "size_gb": round(size / 2**30, 2),
                "reason": f"evicted to make room for {critical_name}",
            })

        return target if shortfall <= 0 else None

    @staticmethod
    def _is_critical(module_name: str) -> bool:
        return any(hint in module_name for hint in _CRITICAL_SUBSTRINGS)

    @staticmethod
    def _build_report(
        device_map: Dict[str, Any],
        sizes: Dict[str, int],
        max_memory: Dict[Any, int],
        moves: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        per_device: Dict[str, Dict[str, Any]] = {}
        for name, device in device_map.items():
            key = str(device)
            entry = per_device.setdefault(
                key, {"modules": 0, "bytes": 0, "budget_gb": None}
            )
            entry["modules"] += 1
            entry["bytes"] += sizes.get(name, 0)

        for key, entry in per_device.items():
            entry["used_gb"] = round(entry.pop("bytes") / 2**30, 2)
            budget = max_memory.get(int(key)) if key.isdigit() else max_memory.get(key)
            entry["budget_gb"] = round(budget / 2**30, 2) if budget else None

        off_gpu = [
            name for name, device in device_map.items()
            if str(device) in ("cpu", "disk")
        ]
        summary = " | ".join(
            f"{dev}: {info['modules']} modules, {info['used_gb']}GB"
            for dev, info in sorted(per_device.items())
        )

        return {
            "summary": summary,
            "per_device": per_device,
            "modules_off_gpu": len(off_gpu),
            "off_gpu_modules": off_gpu[:20],
            "all_on_gpu": not off_gpu,
            "repairs": moves,
        }
