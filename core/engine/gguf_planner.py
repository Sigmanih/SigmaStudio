# ==============================================================================
# core/engine/gguf_planner.py — Come caricare un modello su questa macchina
#
# Questi conti stavano dentro LlamaCppBackend, ed e' li' che avrebbero smesso
# di funzionare. Sigma Studio sta per avere un secondo runtime GGUF — i binari
# ufficiali di llama.cpp, avviati come server — e un secondo backend che si
# riscrivesse la propria pianificazione sarebbe la sesta duplicazione di questa
# sessione dopo le due pipeline HTTP, le cinque copie di _sse, le tre dei
# manifesti e le cinque sonde hardware. Ognuna era divergente, e ognuna e'
# costata un difetto vero.
#
# Qui la decisione si prende una volta: quanti layer stanno in VRAM, quanto
# contesto entra, se quantizzare la cache KV conviene davvero, quanto batch
# regge la memoria dell'host. I backend non decidono, traducono — uno in
# argomenti di Llama(), l'altro in flag da riga di comando — e un test verifica
# che parlino lo stesso vocabolario.
#
# I numeri qui dentro sono misurati su hardware vero, non stimati: dove un
# commento riporta una cifra, quella cifra viene da una prova. Vanno letti
# prima di cambiarli.
# ==============================================================================
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from core.engine.model_inspector import ModelFacts, ModelInspector
from core.logger import get_logger

log = get_logger(__name__)


# ------------------------------------------------------------------ costanti

# Single-channel LPDDR4X on a small ARM board. This one is measured rather
# than assumed: a 1.88 GB Q4_K_M decoded at 4.38 tok/s on a Raspberry Pi 5
# (4 threads, all layers on the CPU), which is 8.2 GB/s of effective read
# bandwidth. Rounded down, because that run had the board to itself.
_ARM_BANDWIDTH_GB_S = 8.0

# A page fault to NVMe is roughly an order of magnitude worse again.
_DISK_BANDWIDTH_GB_S = 1.5

# Host memory bandwidth actually reached by a streaming read, as opposed to
# the figure on the module label. Dual-channel DDR4/DDR5 desktops land here;
# it is a stated assumption, not a measurement, and is labelled as such
# wherever the forecast is shown.
_HOST_BANDWIDTH_GB_S = 12.0

# Prefill is compute-bound rather than bandwidth-bound, and on the same
# board it ran 5.7x faster than decode. Measured across n_batch 128 and 256,
# which produced 24.8 and 24.5 tok/s -- within noise of each other, so the
# small ARM prefill batch costs nothing and the memory it saves is real.
_PREFILL_TO_DECODE_RATIO = 5.5


# --------------------------------------------- soglie e riserve di memoria

# Without an accelerator, prefill is the wall: every doubling of the window
# doubles the KV cache and lengthens the worst-case prompt the board has to
# chew through before the first token. 32k on a Raspberry Pi is not a longer
# conversation, it is a conversation that never starts. Callers that really
# want more can say so through SIGMA_MAX_CONTEXT.
_CPU_CONTEXT_CEILING = 8192

# Fraction of physical cores used when running on CPU. Leaving one core free
# keeps the host responsive, which matters most on the small boards where the
# CPU path is the only path.
_CPU_THREAD_HEADROOM = 1

# Below this an assistant cannot hold a system prompt plus a question, so a
# plan that needs less says so instead of pretending.
_FLOOR_CONTEXT_TOKENS = 1024

# llama.cpp puts more on the GPU than the layers themselves: the output and
# embedding tensors, per-device compute buffers, and the KV cache for whatever
# it offloaded. Measured on a 27B F16 split across two cards, 23 layers
# estimated at 18.0GB actually occupied 21.5GB and filled both cards to the
# last byte, which collapsed throughput to 0.2 tok/s. Sizing layers by their
# raw bytes alone reliably overcommits, so the estimate carries that margin.
_GGUF_OVERHEAD_FACTOR = 1.20

# Room left on each GPU for the CUDA context and per-device scratch.
# Modern NVIDIA/AMD drivers use ~0.3-0.5 GB per device for runtime context and buffers.
_GPU_RESERVE_GB = 0.6


# Host RAM that must stay free for the OS, the web server and the page cache
# llama.cpp reads mmapped weights through. A flat figure is the wrong shape:
# reserving 8 GB on a board that only has 8 is the same as refusing to run,
# and reserving 0.6 GB on a 128 GB workstation is not a reserve at all.
_HOST_RESERVE_FRACTION = 0.12

_HOST_RESERVE_MAX_GB = 4.0

_HOST_RESERVE_MIN_GB = 0.6

# Scratch llama.cpp allocates per context beyond the KV cache: compute graph,
# per-thread buffers and the tokenizer's own working set. Small, but it is the
# difference between a plan that just fits and one that pages.
_HOST_SCRATCH_GB = 0.3

# Quantizing the KV cache halves it, which can buy back GPU layers -- but it is
# not free. Measured on this project's own hardware, decoding a 3B with every
# layer on the CPU:
#
#     KV f16   8.59 tok/s          KV q8_0   7.65 tok/s      -10.9%
#
# and with every layer on the GPU the same comparison is within noise (+1.8%).
# The dequantization cost lands on whichever device holds the layer, so on a
# split placement the many CPU-resident layers each pay it.
#
# It is therefore applied only when it earns its place: when the halved cache
# moves enough layers onto the accelerator to more than repay the per-token
# cost. Applying it by context length alone -- as this did at first -- gained a
# single layer out of 65 on a model that did not fit anyway, and slowed the 47
# CPU-resident ones down for nothing.
_KV_QUANT_CONTEXT_THRESHOLD = 8192

# The measured decode penalty of a quantized cache on a host-resident layer:
# 8.59 -> 7.65 tok/s on the CPU-only run above. The placement decision is made
# against this number rather than against a rule of thumb.
_KV_QUANT_DECODE_PENALTY = 0.11

_KV_QUANT_TYPE = "q8_0"

# Contexts to try when the requested one does not fit, largest first. Halving
# rather than searching keeps the choice stable, so small changes in free RAM
# do not silently move the window between two loads of the same model.
_MIN_CONTEXT_TOKENS = 2048

# Measured on a Raspberry Pi 5 with a 3B Q4_K_M, 2048 prompt tokens, 4 threads:
#
#     n_batch 128 -> 24.8 tok/s prefill      n_batch 256 -> 24.5 tok/s
#
# Prefill on this class of board is compute-bound, not batch-bound, so a larger
# batch buys nothing and costs n_batch x n_vocab x float32 of host RAM. Raising
# this looks like an optimisation and is not one.
_N_BATCH_ARM = 128

# Prefill batches. 512 is llama.cpp's conservative default, chosen so it fits
# anywhere; with VRAM to spare a larger batch feeds the GPU properly and cuts
# the wait before the first token on a long prompt.
_N_BATCH_DEFAULT = 512

_N_BATCH_ROOMY = 2048

# Prompt lookup decoding: the draft tokens are taken from the prompt itself, so
# there is no second model to load, no VRAM to find and nothing to configure.
# It pays for itself whenever the answer quotes its input -- refactoring, code
# edits, translation, summarising a pasted document -- and costs close to
# nothing when it does not, because a rejected draft is one batched forward
# pass the model was going to make anyway.
#
# It is not free in memory, though, and the cost is not obvious: passing a
# draft model makes llama-cpp-python turn `logits_all` on, and the logits
# buffer then spans the whole context instead of one batch. At n_ctx x n_vocab
# x float32 that is 15.7 GB for a 32k window on a 128256-token vocabulary --
# more than three times the model itself. It is therefore requested only when
# that buffer has been costed against real free RAM (see _fit_to_host_memory).
_PROMPT_LOOKUP_TOKENS = 10

# n_batch is not free in host RAM. llama-cpp-python allocates a logits buffer of
# n_batch x n_vocab float32 whether or not it ever writes to it, so the cost
# scales with the vocabulary: on a 262144-token vocabulary, n_batch 2048 commits
# 2 GB before a single token is generated. The batch is capped so that buffer
# stays inside this budget -- a faster prefill is not worth two gigabytes the
# machine could have spent on layers.
_SCORES_BUDGET_BYTES = 512 * 2**20

_SPECULATION_BUFFER_CAP_GB = 1.0

# The speculation buffer is an optimisation. It is allowed at most this share
# of what is actually free, and never more than the cap: a speedup that takes
# a gigabyte away from the page cache the weights stream through is a loss.
_SPECULATION_BUFFER_FRACTION = 0.10


def _env_context_ceiling() -> Optional[int]:
    """An explicit context ceiling from the environment, when one is set."""
    raw = os.environ.get("SIGMA_MAX_CONTEXT", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        log.warning("[LlamaCpp] SIGMA_MAX_CONTEXT='%s' non e' un intero: ignorato.", raw)
        return None
    return value if value > 0 else None


# ------------------------------------------------------------------ pianificazione

def _plan_settings(facts: ModelFacts, hardware: Dict[str, Any], context_tokens: int
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

    weights_gb = facts.total_bytes / 2**30
    n_ctx = _clamp_context(facts, context_tokens)
    physical_cores = int(cpu.get("cores_physical", 4) or 4)
    # Never below two: a single thread makes a board that could answer
    # slowly answer not at all, and the headroom exists to keep the web UI
    # responsive, not to halve the engine.
    n_threads = max(physical_cores - _CPU_THREAD_HEADROOM, min(physical_cores, 2))
    # Prefill is a burst, not a steady load: it runs once per turn and the
    # user is watching a spinner while it does. Giving it every core costs
    # the web UI a moment of latency and buys back seconds of waiting,
    # which on a board without an accelerator is the whole experience.
    n_threads_batch = physical_cores

    env_ceiling = _env_context_ceiling()
    if env_ceiling:
        n_ctx = min(n_ctx, _clamp_context(facts, env_ceiling))

    # Apple silicon shares one memory pool, so everything goes to the GPU --
    # and that pool is the same RAM the logits buffer comes out of, so the
    # host fit applies here exactly as it does on a CPU-only board.
    if any(a.get("type") == "APPLE_MPS" for a in accelerators):
        n_batch = _cap_batch(_N_BATCH_ROOMY, facts)
        fit = _fit_to_host_memory(
            facts, hardware, requested_ctx=n_ctx,
            host_weights_gb=weights_gb, n_batch=n_batch,
            want_speculation=True,
        )
        settings = {
            "n_gpu_layers": -1, "tensor_split": None, "n_ctx": fit["n_ctx"],
            "n_threads": n_threads,
            "n_threads_batch": n_threads_batch,
            "n_batch": n_batch,
            "flash_attn": True,
            "kv_quant": (
                _KV_QUANT_TYPE if fit["n_ctx"] > _KV_QUANT_CONTEXT_THRESHOLD else None
            ),
            "prompt_lookup_tokens": fit["prompt_lookup_tokens"],
            "device": "metal",
        }
        return _merge_host_fit(settings, fit)

    if not gpus:
        # CPU-only, which is the normal case on ARM boards. Smaller batches
        # keep peak memory down where there is little of it to spare.
        #
        # No KV quantization here: it rides on flash attention, which this
        # path does not enable, and dequantizing the cache on every step
        # would cost the CPU exactly what it cannot spare.
        #
        # Prompt lookup is worth most precisely here -- a board that decodes
        # at two tokens a second gains the most from the tokens it can skip
        # -- but it is also here that its logits buffer is least affordable,
        # so the fit below decides rather than the platform.
        is_arm = bool(system.get("is_arm") or system.get("is_raspberry_pi"))
        n_batch = _cap_batch(
            _N_BATCH_ARM if is_arm else _N_BATCH_DEFAULT, facts)
        requested_ctx = min(n_ctx, env_ceiling or _CPU_CONTEXT_CEILING)
        fit = _fit_to_host_memory(
            facts, hardware, requested_ctx=requested_ctx,
            host_weights_gb=weights_gb, n_batch=n_batch,
            want_speculation=True,
        )
        settings = {
            "n_gpu_layers": 0, "tensor_split": None, "n_ctx": fit["n_ctx"],
            "n_threads": n_threads,
            "n_threads_batch": n_threads_batch,
            "n_batch": n_batch,
            "flash_attn": False,
            "kv_quant": None,
            "prompt_lookup_tokens": fit["prompt_lookup_tokens"],
            "device": "arm_neon" if is_arm else "cpu",
            "weights_gb": round(weights_gb, 2),
        }
        if n_ctx > requested_ctx and not env_ceiling:
            settings.setdefault("notes", []).append(
                f"Contesto limitato a {requested_ctx} token su CPU: senza "
                f"acceleratore il prefill di una finestra piu' larga costa "
                f"minuti prima del primo token. Imposta SIGMA_MAX_CONTEXT "
                f"per alzarlo."
            )
        settings.update(_cpu_forecast(facts, settings, hardware))
        return _merge_host_fit(settings, fit)

    usable = [max(g.get("free_vram_gb", 0.0) - _GPU_RESERVE_GB, 0.0) for g in gpus]
    total_usable = sum(usable)
    layers = facts.num_hidden_layers or 0

    tensor_split = None
    if len(gpus) > 1 and total_usable > 0:
        tensor_split = [round(u / total_usable, 4) for u in usable]

    # The split and the host fit depend on each other: the KV cache that
    # stays in host RAM is set by how many layers missed the accelerator,
    # and shrinking the context to fit host RAM changes how many fit. Two
    # passes settle it -- the second only runs when the first shrank the
    # window, and it cannot shrink it again because the ladder is monotonic.
    for _ in range(2):
        # Quantizing the KV cache is decided against the placement it
        # produces, not against the context length: the question is not "is
        # the cache big?" but "does halving it move enough layers onto the
        # accelerator to repay what it costs on the ones that stay behind?"
        kv_gb_f16 = ModelInspector.estimate_kv_cache_gb(facts, n_ctx)

        plain = _layers_that_fit(weights_gb, layers, total_usable, kv_gb_f16)
        halved = _layers_that_fit(weights_gb, layers, total_usable, kv_gb_f16 / 2)

        kv_quant = None
        if n_ctx > _KV_QUANT_CONTEXT_THRESHOLD and layers:
            if _kv_quant_pays_off(plain, halved, layers):
                kv_quant = _KV_QUANT_TYPE

        # Se siamo a pochissimi layer dal full offload (es. 1-3 layer su CPU),
        # vale sempre la pena ridurre leggermente la finestra di contesto
        # (es. da 32k a 24k o 16k) per ottenere l'offload completo (-1):
        # la differenza di velocita' e' di oltre 10x (35 tok/s invece di 2-3 tok/s).
        if plain != -1 and halved != -1 and layers > 0 and not env_ceiling:
            for candidate_ctx in (24576, 16384, 12288, 8192):
                if candidate_ctx >= n_ctx:
                    continue
                cand_kv_f16 = ModelInspector.estimate_kv_cache_gb(facts, candidate_ctx)
                if _layers_that_fit(weights_gb, layers, total_usable, cand_kv_f16) == -1:
                    n_ctx = candidate_ctx
                    kv_gb_f16 = cand_kv_f16
                    plain = -1
                    kv_quant = None
                    break
                if _layers_that_fit(weights_gb, layers, total_usable, cand_kv_f16 / 2) == -1:
                    n_ctx = candidate_ctx
                    kv_gb_f16 = cand_kv_f16
                    halved = -1
                    kv_quant = _KV_QUANT_TYPE
                    break

        kv_gb = round(kv_gb_f16 / 2, 3) if kv_quant else kv_gb_f16
        n_gpu_layers = halved if kv_quant else plain


        # A larger prefill batch only helps where there is memory to hold
        # it. On a card that is already full, it competes with the weights.
        headroom_gb = total_usable - (weights_gb * _GGUF_OVERHEAD_FACTOR + kv_gb)
        n_batch = _cap_batch(
            _N_BATCH_ROOMY if headroom_gb > 1.0 else _N_BATCH_DEFAULT, facts
        )

        # Whatever llama.cpp did not offload is read from host RAM, and the
        # logits buffer lives there regardless of placement -- which is why
        # a workstation with two cards can still be taken down by a 32k
        # context on a large vocabulary if nobody counts it.
        host_layer_fraction = (
            0.0 if (n_gpu_layers < 0 or (layers and n_gpu_layers >= layers))
            else (max(layers - n_gpu_layers, 0) / layers if layers else 1.0)
        )
        fit = _fit_to_host_memory(
            facts, hardware, requested_ctx=n_ctx,
            host_weights_gb=weights_gb * host_layer_fraction,
            n_batch=n_batch, want_speculation=True,
            kv_host_fraction=host_layer_fraction,
            kv_bytes_per_element=1 if kv_quant else 2,
        )
        if fit["n_ctx"] == n_ctx:
            break
        n_ctx = fit["n_ctx"]

    settings = {
        "n_gpu_layers": n_gpu_layers,
        "tensor_split": tensor_split,
        "n_ctx": n_ctx,
        "n_threads": n_threads,
        "n_threads_batch": n_threads_batch,
        "n_batch": n_batch,
        "flash_attn": True,
        "kv_quant": kv_quant,
        "prompt_lookup_tokens": fit["prompt_lookup_tokens"],
        "device": "cuda",
        "usable_vram_gb": round(total_usable, 2),
        "weights_gb": round(weights_gb, 2),
        "kv_cache_gb": kv_gb,
        "kv_cache_gb_f16": kv_gb_f16,
    }
    if kv_quant:
        settings["kv_saving_gb"] = round(kv_gb_f16 - kv_gb, 2)
    # The forecast writes its own `warning`, so it runs before the fit is
    # folded in: _merge_host_fit appends to whatever is already there
    # rather than replacing it, and both warnings matter.
    settings.update(_throughput_forecast(facts, settings, hardware))
    return _merge_host_fit(settings, fit)


def _fit_to_host_memory(facts: ModelFacts,
    hardware: Dict[str, Any],
    requested_ctx: int,
    host_weights_gb: float,
    n_batch: int,
    want_speculation: bool,
    kv_host_fraction: float = 1.0,
    kv_bytes_per_element: int = 2,
) -> Dict[str, Any]:
    """
    Fits the context and the speculation buffer into real free host RAM.

    This is the check the engine did not make, and its absence is what took
    a whole Raspberry Pi 5 down rather than merely running slowly: a 3B at
    the default 32k window asked for 1.9 GB of weights, 3.5 GB of KV cache
    and -- because prompt lookup was on -- a 15.7 GB logits buffer, on a
    board with 8 GB and half a gigabyte of swap. llama.cpp allocates that
    buffer lazily, so the load reported success in thirteen seconds and the
    machine died on the first forward pass instead.

    Concessions are made cheapest-first, because they are not equivalent:
    losing speculative decoding costs some tokens per second, losing
    context costs the conversation. So speculation is dropped before the
    window is halved, and the window is halved before anything is declared
    impossible.
    """
    budget = _host_budget_gb(hardware)
    available = float((hardware.get("ram") or {}).get("available_gb") or 0.0)
    batch_logits_gb = _logits_buffer_gb(facts, n_batch)

    spec_budget = min(
        available * _SPECULATION_BUFFER_FRACTION, _SPECULATION_BUFFER_CAP_GB
    ) if available > 0 else _SPECULATION_BUFFER_CAP_GB

    notes: List[str] = []
    warning: Optional[str] = None

    for ctx in _context_ladder(requested_ctx):
        kv_gb = ModelInspector.estimate_kv_cache_gb(
            facts, ctx, bytes_per_element=kv_bytes_per_element
        ) * max(min(kv_host_fraction, 1.0), 0.0)
        base_gb = host_weights_gb + kv_gb + batch_logits_gb + _HOST_SCRATCH_GB
        spec_gb = _logits_buffer_gb(facts, ctx)

        speculation_affordable = (
            want_speculation
            and spec_gb <= spec_budget
            and (budget <= 0 or base_gb + spec_gb <= budget)
        )
        if speculation_affordable:
            return _host_fit_result(
                ctx, requested_ctx, True, base_gb + spec_gb, budget,
                kv_gb, batch_logits_gb, spec_gb, notes, warning,
            )

        if want_speculation and ctx == requested_ctx:
            notes.append(
                f"Speculative decoding (prompt lookup) disattivato: il suo "
                f"buffer dei logits occuperebbe {spec_gb:.1f} GB di RAM "
                f"({facts.vocab_size} token di vocabolario x {ctx} di "
                f"contesto), oltre il budget di {spec_budget:.1f} GB."
            )

        if budget <= 0 or base_gb <= budget:
            return _host_fit_result(
                ctx, requested_ctx, False, base_gb, budget,
                kv_gb, batch_logits_gb, 0.0, notes, warning,
            )

    # Nothing on the ladder fits. The load is still attempted at the floor:
    # llama.cpp streams mmapped weights from disk and may survive, and an
    # explicit warning beats refusing a model the user can see on disk.
    ctx = _FLOOR_CONTEXT_TOKENS
    kv_gb = ModelInspector.estimate_kv_cache_gb(
        facts, ctx, bytes_per_element=kv_bytes_per_element
    ) * max(min(kv_host_fraction, 1.0), 0.0)
    base_gb = host_weights_gb + kv_gb + batch_logits_gb + _HOST_SCRATCH_GB
    warning = (
        f"Il modello richiede circa {base_gb:.1f} GB di RAM anche con un "
        f"contesto minimo di {ctx} token, ma ne sono liberi solo "
        f"{budget:.1f} GB. Il caricamento verra' tentato leggendo i pesi dal "
        f"disco: sara' molto lento e puo' esaurire la memoria. Usa una "
        f"quantizzazione piu' compatta (Q4_K_S / Q3) o un modello piu' piccolo."
    )
    return _host_fit_result(
        ctx, requested_ctx, False, base_gb, budget,
        kv_gb, batch_logits_gb, 0.0, notes, warning,
    )


def _host_fit_result(
    ctx: int, requested_ctx: int, speculation: bool, required_gb: float,
    budget_gb: float, kv_gb: float, batch_logits_gb: float,
    spec_logits_gb: float, notes: List[str], warning: Optional[str],
) -> Dict[str, Any]:
    if ctx < requested_ctx:
        notes.append(
            f"Contesto ridotto da {requested_ctx} a {ctx} token per stare "
            f"nella RAM disponibile ({budget_gb:.1f} GB utilizzabili)."
        )
    return {
        "n_ctx": ctx,
        "prompt_lookup_tokens": _PROMPT_LOOKUP_TOKENS if speculation else 0,
        "host_required_gb": round(required_gb, 2),
        "host_budget_gb": round(budget_gb, 2),
        "host_kv_gb": round(kv_gb, 2),
        "logits_buffer_gb": round(batch_logits_gb + spec_logits_gb, 3),
        "notes": notes,
        "warning": warning,
    }


def _merge_host_fit(settings: Dict[str, Any], fit: Dict[str, Any]) -> Dict[str, Any]:
    """Folds a host-memory fit into a settings dict, keeping its reporting."""
    settings["n_ctx"] = fit["n_ctx"]
    settings["prompt_lookup_tokens"] = fit["prompt_lookup_tokens"]
    settings["logits_buffer_gb"] = fit["logits_buffer_gb"]
    settings["host_required_gb"] = fit["host_required_gb"]
    settings["host_budget_gb"] = fit["host_budget_gb"]
    settings["host_kv_gb"] = fit["host_kv_gb"]
    if fit["notes"]:
        settings.setdefault("notes", []).extend(fit["notes"])
    if fit["warning"]:
        existing = settings.get("warning")
        settings["warning"] = (
            f"{existing} {fit['warning']}" if existing else fit["warning"]
        )
    return settings


def _cpu_forecast(facts: ModelFacts, settings: Dict[str, Any], hardware: Dict[str, Any]
) -> Dict[str, Any]:
    """
    What a host with no accelerator will actually feel like.

    The CPU path used to report nothing at all, which left the slowest
    configuration the product supports as the only one with no expectation
    attached: a Raspberry Pi 5 answers a 2000-token first message about two
    minutes after it is sent, and every part of the UI implied that was a
    fault rather than the hardware.

    Two numbers, because they behave differently. Decode reads every weight
    once per token, so it is bounded by memory bandwidth and no amount of
    tuning moves it. Prefill is compute-bound and only happens in full once:
    llama.cpp keeps the evaluated tokens and reuses the longest common
    prefix on the next turn, so the system prompt is paid for on the first
    message of a conversation and not again.
    """
    weights_gb = facts.total_bytes / 2**30
    if weights_gb <= 0:
        return {}

    is_arm = settings.get("device") == "arm_neon"
    bandwidth = _ARM_BANDWIDTH_GB_S if is_arm else _HOST_BANDWIDTH_GB_S
    free_ram = float((hardware.get("ram") or {}).get("available_gb", 0.0) or 0.0)
    paging = 0 < free_ram < weights_gb
    if paging:
        bandwidth = _DISK_BANDWIDTH_GB_S

    decode_tps = round(bandwidth / weights_gb, 2)
    prefill_tps = round(decode_tps * _PREFILL_TO_DECODE_RATIO, 1)

    forecast = {
        "placement": "cpu_only",
        "weights_gb": round(weights_gb, 2),
        "assumed_bandwidth_gb_s": bandwidth,
        "estimated_tokens_per_second": decode_tps,
        "estimated_prefill_tokens_per_second": prefill_tps,
        "pages_from_disk": paging,
        "first_turn_only": (
            "llama.cpp riusa il prefisso gia' valutato: il prompt di sistema "
            "si paga al primo messaggio della conversazione, non ai successivi."
        ),
    }

    if paging:
        settings["warning"] = (
            f"I {weights_gb:.1f} GB del modello non stanno nella RAM libera "
            f"({free_ram:.1f} GB): verranno letti dal disco a ogni token. "
            f"Attesa realistica: {_render_rate(decode_tps)}. Serve una "
            f"quantizzazione piu' compatta o un modello piu' piccolo."
        )
    else:
        settings["note_speed"] = (
            f"Esecuzione su CPU: attesa {_render_rate(decode_tps)} in "
            f"generazione e circa {prefill_tps:.0f} token/s nella lettura del "
            f"prompt. Un prompt di sistema da 2000 token costa quindi "
            f"~{2000 / max(prefill_tps, 0.1):.0f}s al primo messaggio, poi "
            f"viene riutilizzato."
        )
    return {"forecast": forecast}


def _throughput_forecast(facts: ModelFacts, settings: Dict[str, Any], hardware: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Says what this placement will feel like, before the user finds out.

    Decoding reads every weight once per token, so the layers left off the
    accelerator set a hard ceiling that no amount of tuning moves: bytes on
    the host bus divided by the bandwidth of that bus. The engine used to
    produce this placement in silence and let the user discover it as "the
    model is slow now" -- a 50GB F16 on 21GB of VRAM answers at a third of
    a token per second, and nothing said so.

    Worse is when the host-resident part does not fit in free RAM either.
    Then it is paged from the model file on every token, an order of
    magnitude slower again, and that case is worth its own warning because
    it is the difference between slow and unusable.
    """
    layers = facts.num_hidden_layers or 0
    on_gpu = settings.get("n_gpu_layers", 0)
    weights_gb = facts.total_bytes / 2**30

    if not layers or on_gpu < 0 or on_gpu >= layers:
        return {"forecast": {"placement": "fully_offloaded"}}

    off_gpu = layers - on_gpu
    host_gb = weights_gb * off_gpu / layers
    free_ram = float((hardware.get("ram") or {}).get("available_gb", 0.0) or 0.0)
    paging = free_ram > 0 and host_gb > free_ram

    bandwidth = _DISK_BANDWIDTH_GB_S if paging else _HOST_BANDWIDTH_GB_S
    ceiling = round(bandwidth / max(host_gb, 1e-6), 2)

    forecast = {
        "placement": "split",
        "layers_on_gpu": on_gpu,
        "layers_on_host": off_gpu,
        "host_gb_per_token": round(host_gb, 1),
        "free_ram_gb": round(free_ram, 1),
        "pages_from_disk": paging,
        "estimated_tokens_per_second": ceiling,
        "assumed_bandwidth_gb_s": bandwidth,
    }

    if paging:
        settings["warning"] = (
            f"{off_gpu} dei {layers} layer non stanno in VRAM e i {host_gb:.0f} GB "
            f"che restano non entrano nemmeno nella RAM libera ({free_ram:.0f} GB): "
            f"verranno letti dal disco a ogni token. Attesa realistica: "
            f"{_render_rate(ceiling)}. Serve una quantizzazione piu' compatta."
        )
    else:
        rimasti = (
            "l'ultimo layer viene letto" if off_gpu == 1
            else f"gli altri {off_gpu} vengono letti"
        )
        quanti = f"{host_gb:.1f} GB" if host_gb < 10 else f"{host_gb:.0f} GB"
        settings["warning"] = (
            f"{on_gpu} dei {layers} layer stanno in VRAM: {rimasti} dalla RAM "
            f"di sistema, {quanti} a ogni token. Tetto stimato "
            f"{_render_rate(ceiling)}, indipendente da ogni altra "
            f"ottimizzazione."
        )

    alternative = suggest_smaller_variant(facts, hardware)
    if alternative:
        forecast["better_variant"] = alternative
        settings["warning"] += (
            f" Su questo disco c'e' gia' '{alternative['name']}' "
            f"({alternative['size_gb']} GB): entrerebbe "
            f"{'quasi tutto' if alternative['partial'] else 'interamente'} in VRAM."
        )
    return {"forecast": forecast}


def suggest_smaller_variant(
    facts: ModelFacts, hardware: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Another local copy of this model that would actually fit.

    Naming the remedy matters more than naming the problem: the user who
    hit this had the Q4_K_S of the very same checkpoint sitting in the next
    folder, and no part of the product mentioned it.

    Matching is on the model name with the quantization suffix removed, so
    'Qwen--Qwen3.8-27B-GGUF-Q4_K_S' is recognised as a variant of
    'Qwen--Qwen3.8-27B-GGUF' without a registry to keep in step.
    """
    try:
        from core.model_paths import models_dir
        root = models_dir()
        if not os.path.isdir(root):
            return None
    except Exception:
        return None

    usable = sum(
        max(a.get("free_vram_gb", 0.0) - _GPU_RESERVE_GB, 0.0)
        for a in hardware.get("accelerators", [])
        if a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM")
    )
    if usable <= 0:
        return None

    def stem(name: str) -> str:
        lowered = name.lower()
        for marker in ("-gguf", "_gguf", ".gguf"):
            index = lowered.find(marker)
            if index > 0:
                return lowered[:index]
        return lowered

    target = stem(facts.name)
    current_gb = facts.total_bytes / 2**30
    best = None

    for entry in sorted(os.listdir(root)):
        folder = os.path.join(root, entry)
        if not os.path.isdir(folder) or entry == facts.name:
            continue
        if stem(entry) != target:
            continue
        files = [f for f in os.listdir(folder) if f.endswith(".gguf")]
        if not files:
            continue
        size_gb = min(
            os.path.getsize(os.path.join(folder, f)) for f in files
        ) / 2**30
        if size_gb >= current_gb:
            continue
        candidate = {
            "name": entry,
            "size_gb": round(size_gb, 1),
            "partial": size_gb * _GGUF_OVERHEAD_FACTOR > usable,
        }
        # Prefer the largest variant that still fits: quality first among
        # the options that solve the speed problem.
        if best is None or (candidate["size_gb"] > best["size_gb"]
                            and not candidate["partial"]):
            best = candidate
    return best


def _layers_that_fit(
    weights_gb: float, layers: int, usable_gb: float, kv_gb: float
) -> int:
    """
    How many layers the accelerator can hold, or -1 when all of them can.

    -1 is llama.cpp's own way of saying "offload everything", and it is not
    the same as the layer count: it also lets the runtime place the output
    and embedding tensors, which a numeric limit does not.
    """
    if not layers:
        return -1
    if (weights_gb * _GGUF_OVERHEAD_FACTOR + kv_gb) <= usable_gb:
        return -1
    per_layer = (weights_gb / layers) * _GGUF_OVERHEAD_FACTOR
    budget = max(usable_gb - kv_gb, 0.0)
    return min(max(int(budget / max(per_layer, 1e-6)), 0), layers)


def _kv_quant_pays_off(plain: int, halved: int, layers: int) -> bool:
    """
    Whether halving the cache saves more than dequantizing it costs.

    Decode on a split placement is dominated by the weights read over the
    host bus, which is proportional to the layers left behind. Quantizing
    the cache multiplies per-token work by the measured penalty but reduces
    that count, so the trade is simply

        host_layers(halved) x penalty  <  host_layers(plain)

    Counting layers moved, as the first version did, gets this backwards at
    both ends: it rejected a case that cut host traffic fourfold because
    only three layers moved, and accepted one that moved a single layer of
    sixty-five while slowing the other forty-seven down.
    """
    if plain == -1:
        return False                  # already fully offloaded; nothing to buy
    if halved == -1:
        return True                   # buys full offload: always worth it

    host_plain = max(layers - plain, 0)
    host_halved = max(layers - halved, 0)
    if host_plain == 0:
        return False
    return host_halved * (1.0 + _KV_QUANT_DECODE_PENALTY) < host_plain


def _cap_batch(desired: int, facts: ModelFacts) -> int:
    """
    The largest prefill batch whose logits buffer stays inside the budget.

    llama-cpp-python allocates n_batch x n_vocab float32 up front, so the
    cost of a bigger batch is set by the vocabulary rather than by the
    model's size. Modern vocabularies are large enough that this dominates:
    at 262144 tokens each batch slot costs a megabyte, so the roomy 2048
    would commit two gigabytes of host RAM before generating anything.
    """
    vocab = int(getattr(facts, "vocab_size", 0) or 0)
    if vocab <= 0:
        # Unknown vocabulary means unknown cost, and the roomy batch is an
        # optimisation while two gigabytes of committed RAM is a real loss.
        # Refusing to guess upward is the only safe direction here.
        return min(desired, _N_BATCH_DEFAULT)
    affordable = _SCORES_BUDGET_BYTES // (vocab * 4)
    # Never below llama.cpp's own floor: a batch smaller than 128 makes
    # prefill slower than the memory it saves is worth.
    return max(min(desired, int(affordable)), 128)


def _clamp_context(facts: ModelFacts, requested: int) -> int:
    """Keeps the context within what the checkpoint was trained for."""
    trained = facts.max_position_embeddings or 0
    if trained and requested > trained:
        return trained
    return max(requested, 512)


def _context_ladder(requested: int) -> List[int]:
    """Context sizes to try, largest first, down to a usable floor."""
    ladder, value = [requested], requested
    while value > _MIN_CONTEXT_TOKENS:
        value //= 2
        ladder.append(max(value, _MIN_CONTEXT_TOKENS))
    ladder.append(_FLOOR_CONTEXT_TOKENS)
    seen, ordered = set(), []
    for candidate in ladder:
        if candidate not in seen and candidate > 0:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _logits_buffer_gb(facts: ModelFacts, rows: int) -> float:
    """
    Host RAM llama-cpp-python commits for its logits buffer.

    The buffer is `rows x n_vocab` float32 and it is host memory even when
    every layer is on the accelerator, because it is a numpy array on the
    Python side. `rows` is n_batch normally and the whole context when a
    draft model is attached -- which is why speculation has to be costed
    here rather than assumed free.
    """
    vocab = int(getattr(facts, "vocab_size", 0) or 0)
    if vocab <= 0 or rows <= 0:
        return 0.0
    return round(rows * vocab * 4 / 2**30, 3)


def _host_budget_gb(hardware: Dict[str, Any]) -> float:
    """
    Host RAM this load may spend, or 0.0 when the probe could not say.

    The reserve scales with the machine so the same rule works on a 8 GB
    board and on a 128 GB workstation.
    """
    ram = hardware.get("ram") or {}
    available = float(ram.get("available_gb") or 0.0)
    total = float(ram.get("total_gb") or available)
    if available <= 0:
        return 0.0
    reserve = min(
        max(total * _HOST_RESERVE_FRACTION, _HOST_RESERVE_MIN_GB),
        _HOST_RESERVE_MAX_GB,
    )
    return max(available - reserve, 0.0)


def _render_rate(tokens_per_second: float) -> str:
    """A rate a person can read, including the ones that round to zero."""
    if tokens_per_second >= 1:
        return f"~{tokens_per_second:.1f} token/s"
    if tokens_per_second >= 0.1:
        return f"~{tokens_per_second:.2f} token/s"
    seconds = 1.0 / max(tokens_per_second, 1e-9)
    return f"meno di 0,1 token/s (circa {seconds:.0f}s per token)"
