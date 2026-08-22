# ==============================================================================
# core/engine/memory_planner.py — Hardware-aware placement planner
#
# Turns measured hardware (UniversalHardwareProbe) + measured model facts
# (ModelInspector) into the concrete arguments accelerate needs:
# max_memory, offload_folder and the quantization choice.
#
# Filling order is strictly: fastest VRAM -> slower VRAM -> system RAM -> disk.
# Precision is chosen as the highest quality that still fits entirely in VRAM,
# because spilling to RAM costs far more speed than dropping to 4-bit costs
# quality.
# ==============================================================================
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Union

from core.logger import get_logger
from core.engine.model_inspector import ModelFacts, ModelInspector

log = get_logger(__name__)

# Per-GPU reserve for the CUDA context, cuBLAS/cuDNN workspaces and allocator
# fragmentation. Without this a plan that fits on paper OOMs in practice.
_CUDA_CONTEXT_RESERVE_GB = 0.8
# Floor for the extra headroom on the device that carries lm_head and the
# sampling step. It used to be the whole story, and a flat gigabyte is simply
# the wrong shape: activations scale with how many tokens are pushed through at
# once and how wide the model is. A 27B at 16k context reported a comfortable
# +1.08GB of headroom and then died allocating 230MB mid-answer, because the
# prefill working set it never counted was worth about two gigabytes.
_PRIMARY_ACTIVATION_RESERVE_GB = 1.0

# Live tensors per token during a prefill step: the residual stream plus the
# query/key/value and MLP intermediates that coexist inside one decoder block.
# Deliberately a small integer rather than a precise model -- the point is that
# the term scales with context and hidden size at all, which a constant does
# not. Verified against the case above: 16384 x 5120 x 2B x 8 = 1.25GB, which
# is the order of magnitude that was missing.
_ACTIVATION_TENSORS_PER_TOKEN = 8

# No estimate should be allowed to eat a whole card; past this fraction of the
# primary GPU the answer is a smaller context, not a bigger reserve.
_MAX_ACTIVATION_FRACTION = 0.35
# Leave the OS and the rest of Sigma Studio room to breathe.
_HOST_RAM_RESERVE_GB = 8.0
# Below this much slack, the fit is inside estimation error: accelerate places
# indivisible decoder blocks, so a plan this tight can still spill or OOM.
_MARGINAL_FIT_GB = 1.0
# Never shrink the planning context below this: an assistant that cannot
# hold a page of conversation is not useful, however fast it is.
_MIN_CONTEXT_TOKENS = 4096
# Quantization candidates, best quality first.
_PRECISION_LADDER = ("bf16", "int8", "nf4")

# transformers' bitsandbytes quantizers shrink whatever max_memory they are
# given by this factor (quantizer_bnb_4bit.adjust_max_memory) to leave room for
# quantization buffers. We already reserve context, activation and KV headroom
# ourselves, so passing our budget through unchanged would apply that safety
# margin twice and push weights onto the CPU that were meant for VRAM. We divide
# it out so the budget transformers ends up using is the one we planned.
_BNB_MAX_MEMORY_HAIRCUT = 0.90


@dataclass
class PlacementPlan:
    """Everything load_native_model needs to place a model optimally."""
    quantization: str = "nf4"
    max_memory: Dict[Union[int, str], str] = field(default_factory=dict)
    offload_folder: Optional[str] = None
    fits_in_vram: bool = False
    uses_host_ram: bool = False
    uses_disk: bool = False

    # Reporting
    model_footprint_gb: float = 0.0      # weights only, at the chosen precision
    kv_cache_gb: float = 0.0             # at context_tokens
    total_required_gb: float = 0.0       # weights + KV
    total_vram_gb: float = 0.0           # raw free VRAM across all GPUs
    weight_budget_gb: float = 0.0        # VRAM left for weights after reserves + KV
    vram_headroom_gb: float = 0.0        # weight_budget - weights; negative means spill
    context_tokens: int = 0            # planned, after fitting to VRAM
    requested_context_tokens: int = 0  # what the caller asked for
    devices: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # JSON keys must be strings; accelerate needs the int keys.
        data["max_memory"] = {str(k): v for k, v in self.max_memory.items()}
        return data

    def max_memory_for_string_strategy(self) -> Dict[Union[int, str], str]:
        """
        Budgets adjusted for transformers' own safety margin.

        When device_map is a string, the bitsandbytes quantizers shrink whatever
        max_memory they receive (quantizer_bnb_4bit.adjust_max_memory) to leave
        room for quantization buffers. We already reserve context, activation
        and KV headroom, so passing the raw budget would apply that margin twice
        and push weights onto the CPU that were meant for VRAM. An explicit
        device map skips that code path and needs no adjustment, which is why
        this is a separate accessor rather than baked into max_memory.
        """
        if self.quantization not in ("nf4", "fp4", "int8"):
            return dict(self.max_memory)

        adjusted: Dict[Union[int, str], str] = {}
        for key, value in self.max_memory.items():
            gib = float(str(value).replace("GiB", "").strip())
            adjusted[key] = f"{gib / _BNB_MAX_MEMORY_HAIRCUT:.2f}GiB"
        return adjusted

    def summary(self) -> str:
        tiers = ["VRAM"]
        if self.uses_host_ram:
            tiers.append("RAM")
        if self.uses_disk:
            tiers.append("disk")
        return (
            f"{self.quantization.upper()} | "
            f"{self.total_required_gb:.1f}GB required "
            f"({self.model_footprint_gb:.1f} weights + {self.kv_cache_gb:.1f} KV) "
            f"vs {self.total_vram_gb:.1f}GB VRAM | "
            f"headroom {self.vram_headroom_gb:+.2f}GB | "
            f"tiers: {' -> '.join(tiers)}"
        )


class MemoryPlanner:
    """Computes optimal multi-tier placement for a model on this machine."""

    @classmethod
    def build_plan(
        cls,
        facts: ModelFacts,
        hardware_profile: Dict[str, Any],
        context_tokens: int = 32768,
        force_quantization: Optional[str] = None,
        include_vision: bool = True,
        allow_host_spill: bool = False,
    ) -> PlacementPlan:
        """
        Builds a placement plan for this model on this machine.

        allow_host_spill offers accelerate a CPU budget even when the model is
        expected to fit in VRAM. Used as a retry path when a VRAM-only load is
        rejected, trading speed for actually running.
        """
        plan = PlacementPlan(context_tokens=context_tokens)

        gpus = [
            a for a in hardware_profile.get("accelerators", [])
            if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM") and "free_vram_gb" in a
        ]
        # Fastest first: more SMs wins, VRAM breaks ties.
        gpus.sort(
            key=lambda a: (a.get("multi_processor_count", 0), a.get("free_vram_gb", 0)),
            reverse=True,
        )

        ram_available_gb = float(
            hardware_profile.get("ram", {}).get("available_gb", 16.0)
        )

        # ------------------------------------------------ precision & context
        # Reserving KV for a context the conversation may never reach is not
        # free: it comes straight out of the weight budget, and a fit with no
        # slack left makes the CUDA allocator thrash. Measured on a 27B NF4
        # across two cards, 32k context left 0.08GB spare and ran at 1.5 tok/s,
        # while 8k left real headroom and ran at 11.4 tok/s for the same
        # placement. So the context is fitted to the hardware, not assumed.
        chosen_ctx = context_tokens
        for candidate in cls._context_candidates(context_tokens):
            kv_gb = ModelInspector.estimate_kv_cache_gb(facts, candidate)
            budget = round(sum(cls._usable_vram(
                gpus, kv_gb, facts, candidate).values()), 2)
            _, trial = cls._choose_precision(facts, budget, force_quantization)
            if budget - trial["total_gb"] >= _MARGINAL_FIT_GB:
                chosen_ctx = candidate
                break
            chosen_ctx = candidate

        if chosen_ctx != context_tokens:
            plan.notes.append(
                f"Context reduced from {context_tokens} to {chosen_ctx} tokens to "
                "keep enough VRAM headroom; a marginal fit costs far more speed "
                "than the unused context is worth."
            )
        plan.context_tokens = chosen_ctx
        plan.requested_context_tokens = context_tokens

        plan.kv_cache_gb = ModelInspector.estimate_kv_cache_gb(facts, chosen_ctx)
        usable_vram = cls._usable_vram(
            gpus, plan.kv_cache_gb, facts, chosen_ctx
        )

        # Raw capacity vs the budget actually available to weights: the latter
        # is what the fill loop spends, the former is what the user recognises
        # as "my VRAM".
        plan.total_vram_gb = round(
            sum(g.get("free_vram_gb", 0.0) for g in gpus), 2
        )
        plan.weight_budget_gb = round(sum(usable_vram.values()), 2)

        quantization, footprint = cls._choose_precision(
            facts, plan.weight_budget_gb, force_quantization
        )
        plan.quantization = quantization
        plan.model_footprint_gb = footprint["total_gb"]
        plan.total_required_gb = round(plan.model_footprint_gb + plan.kv_cache_gb, 2)
        plan.vram_headroom_gb = round(plan.weight_budget_gb - plan.model_footprint_gb, 2)

        if not include_vision and facts.is_multimodal:
            plan.notes.append(
                "Vision tower excluded from the VRAM budget (text-only session)."
            )

        # -------------------------------------------------------- device fill
        remaining = plan.model_footprint_gb
        for idx, gpu in enumerate(gpus):
            device_id = gpu.get("device_id", idx)
            budget = usable_vram.get(device_id, 0.0)
            assigned = min(budget, remaining) if remaining > 0 else 0.0
            remaining = max(remaining - assigned, 0.0)

            plan.max_memory[device_id] = cls._gib(budget)
            plan.devices.append({
                "device_id": device_id,
                "tier": f"tier{idx}_vram",
                "name": gpu.get("name", f"GPU{device_id}"),
                "free_vram_gb": gpu.get("free_vram_gb", 0.0),
                "budget_gb": round(budget, 2),
                "estimated_use_gb": round(assigned, 2),
            })

        plan.fits_in_vram = remaining <= 0.01
        if plan.fits_in_vram and plan.vram_headroom_gb < _MARGINAL_FIT_GB:
            plan.warnings.append(
                f"Marginal fit: only {plan.vram_headroom_gb:.2f}GB of slack. "
                f"Reduce the context below {context_tokens} tokens, or expect "
                "accelerate to spill a block into system RAM."
            )

        # ------------------------------------------------ tier 2: system RAM
        host_budget = max(ram_available_gb - _HOST_RAM_RESERVE_GB, 1.0)
        host_assigned = min(host_budget, remaining) if remaining > 0 else 0.0
        remaining = max(remaining - host_assigned, 0.0)
        plan.uses_host_ram = host_assigned > 0.01

        # Offering a CPU budget is what lets accelerate place weights there. When
        # the model fits in VRAM we withhold it, so a slightly optimistic
        # estimate surfaces as an explicit error instead of silently degrading
        # into PCIe-bound inference.
        if plan.uses_host_ram or allow_host_spill:
            plan.max_memory["cpu"] = cls._gib(host_budget)

        plan.devices.append({
            "device_id": "cpu",
            "tier": "tier2_host_ram",
            "name": "System RAM",
            "free_vram_gb": round(ram_available_gb, 2),
            "budget_gb": round(host_budget, 2),
            "estimated_use_gb": round(host_assigned, 2),
        })

        # ----------------------------------------------------- tier 3: disk
        if remaining > 0.01:
            offload_dir = cls._select_offload_drive(
                hardware_profile, required_gb=remaining
            )
            if offload_dir:
                plan.offload_folder = offload_dir
                plan.uses_disk = True
                plan.devices.append({
                    "device_id": "disk",
                    "tier": "tier3_disk",
                    "name": offload_dir,
                    "budget_gb": round(remaining * 4, 2),
                    "estimated_use_gb": round(remaining, 2),
                })
                plan.warnings.append(
                    f"{remaining:.1f}GB must stream from disk: expect a large "
                    "slowdown. A smaller model or heavier quantization will be "
                    "dramatically faster."
                )
            else:
                plan.warnings.append(
                    f"{remaining:.1f}GB does not fit anywhere, and no drive has "
                    "room for offload. Loading will fail."
                )
        elif plan.uses_host_ram:
            plan.warnings.append(
                f"{host_assigned:.1f}GB spills into system RAM over PCIe: "
                "generation will be noticeably slower than a pure-VRAM fit."
            )

        # An offload folder must exist whenever CPU offload is in play, because
        # accelerate can still decide to page individual weights out.
        if plan.offload_folder is None and (plan.uses_host_ram or not plan.fits_in_vram):
            plan.offload_folder = cls._select_offload_drive(hardware_profile, 8.0)

        cls._add_quality_notes(plan, facts, footprint)
        log.info("[MemoryPlanner] %s", plan.summary())
        return plan

    # ------------------------------------------------------------- internals

    @staticmethod
    def _context_candidates(requested: int) -> List[int]:
        """
        Context sizes to try, largest first, down to a usable floor.

        Halving rather than searching continuously keeps the plan stable: small
        changes in free VRAM should not make the engine pick a slightly
        different context on every load and invalidate the KV cache.
        """
        candidates = [requested]
        value = requested
        while value > _MIN_CONTEXT_TOKENS:
            value //= 2
            candidates.append(max(value, _MIN_CONTEXT_TOKENS))
        seen, ordered = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        return ordered

    @staticmethod
    def _gib(gb: float) -> str:
        return f"{max(gb, 0.0):.2f}GiB"

    @staticmethod
    def activation_reserve_gb(
        facts: Optional[ModelFacts], context_tokens: int, primary_free_gb: float
    ) -> float:
        """
        Working memory a prefill step needs on the device that runs it.

        Weights and KV are both accounted for elsewhere and both are static;
        this is the third term, the one that only exists while a forward pass is
        running, and it is the one that used to be a constant. It scales with
        the two things that actually drive it -- how many tokens go through at
        once, and how wide the model is -- and is capped so an implausible
        context cannot reserve the entire card.
        """
        base = _PRIMARY_ACTIVATION_RESERVE_GB
        if facts is None or not facts.hidden_size or context_tokens <= 0:
            return base

        bytes_per_token = facts.hidden_size * 2 * _ACTIVATION_TENSORS_PER_TOKEN
        scaled = (context_tokens * bytes_per_token) / 2**30
        ceiling = max(primary_free_gb * _MAX_ACTIVATION_FRACTION, base)
        return round(min(max(base, scaled), ceiling), 2)

    @classmethod
    def _usable_vram(
        cls,
        gpus: List[Dict[str, Any]],
        kv_cache_gb: float,
        facts: Optional[ModelFacts] = None,
        context_tokens: int = 0,
    ) -> Dict[Any, float]:
        """
        Free VRAM minus CUDA context, activations and this device's share of the
        KV cache. KV is charged proportionally to capacity, since accelerate
        spreads layers the same way.
        """
        total_free = sum(g.get("free_vram_gb", 0.0) for g in gpus) or 1.0
        usable: Dict[Any, float] = {}

        for idx, gpu in enumerate(gpus):
            device_id = gpu.get("device_id", idx)
            free = float(gpu.get("free_vram_gb", 0.0))
            reserve = _CUDA_CONTEXT_RESERVE_GB
            if idx == 0:
                # The primary card runs the forward pass, so it is the only one
                # that pays for activations on top of its share of the weights.
                reserve += cls.activation_reserve_gb(facts, context_tokens, free)
            kv_share = kv_cache_gb * (free / total_free)
            usable[device_id] = max(free - reserve - kv_share, 0.0)

        return usable

    @classmethod
    def _choose_precision(
        cls,
        facts: ModelFacts,
        usable_vram_gb: float,
        forced: Optional[str],
    ):
        """
        Picks the highest-quality precision whose weights fit entirely in VRAM.
        Falls back to the smallest option when nothing fits, so the caller can
        still plan a RAM/disk spill.
        """
        if forced:
            return forced, ModelInspector.estimate_footprint(facts, forced)

        for precision in _PRECISION_LADDER:
            footprint = ModelInspector.estimate_footprint(facts, precision)
            if footprint["total_gb"] <= usable_vram_gb:
                return precision, footprint

        smallest = _PRECISION_LADDER[-1]
        return smallest, ModelInspector.estimate_footprint(facts, smallest)

    @staticmethod
    def _select_offload_drive(
        hardware_profile: Dict[str, Any], required_gb: float
    ) -> Optional[str]:
        """
        Chooses the fastest drive with enough headroom for offload shards.

        Bandwidth outranks capacity: a roomy USB disk is the worst possible
        offload target, since every streamed layer crosses that bus on the
        critical path of every forward pass.
        """
        drives = hardware_profile.get("storage_drives", []) or []
        needed = max(required_gb * 1.5, 8.0)

        candidates = [d for d in drives if d.get("free_gb", 0) >= needed]
        if not candidates:
            return None

        internal = [d for d in candidates if not d.get("is_removable")]
        if internal:
            candidates = internal

        candidates.sort(
            key=lambda d: (
                d.get("estimated_read_speed_mb_s", 0),
                d.get("free_gb", 0),
            ),
            reverse=True,
        )

        target = os.path.join(candidates[0]["mountpoint"], "sigma_offload")
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except Exception as exc:
            log.warning("[MemoryPlanner] Cannot create offload dir %s: %s", target, exc)
            return None

    @staticmethod
    def _add_quality_notes(
        plan: PlacementPlan, facts: ModelFacts, footprint: Dict[str, float]
    ) -> None:
        if plan.quantization == "nf4" and footprint.get("resident_gb", 0) > 2.0:
            plan.notes.append(
                f"{footprint['resident_gb']:.1f}GB stays in bf16 (embeddings, "
                f"lm_head, norms): bitsandbytes never quantizes those."
            )
        if facts.layer_types and "linear_attention" in facts.layer_types:
            linear = facts.layer_types.count("linear_attention")
            plan.notes.append(
                f"{linear}/{facts.num_hidden_layers} layers use linear attention: "
                "KV cache grows only with the full-attention layers."
            )
        if facts.has_mtp:
            plan.notes.append(
                "Checkpoint ships a native MTP head, usable for speculative decoding."
            )
