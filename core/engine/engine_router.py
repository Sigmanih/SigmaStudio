# ==============================================================================
# core/engine/engine_router.py — HTTP Route Handlers for SigmaEngine
# ==============================================================================
from typing import Dict, Any
from core.logger import get_logger
from core.engine.unified_runtime import sigma_engine
from core.engine.hardware_probe import UniversalHardwareProbe

log = get_logger(__name__)


def handle_engine_status(self):
    """GET /api/engine/status — Returns engine health and active backend."""
    return self.send_json_response(sigma_engine.get_status())


def handle_engine_profile(self):
    """GET /api/engine/profile — Comprehensive hardware benchmark & drive matrix."""
    probe = UniversalHardwareProbe.probe_all()
    return self.send_json_response({"success": True, "profile": probe})


def handle_engine_partition(self):
    """
    POST /api/engine/partition — Where this model's layers would actually go.

    This used to answer with a saliency heuristic: a hardcoded U-curve over a
    hypothetical model, with 450MB assumed per layer, computed from whatever
    numbers the caller passed. The panel that displays it always passed 32
    layers and 8GB, so the tiering shown in the UI described a model that did
    not exist and had never been loaded.

    It now answers from MemoryPlanner -- the same code that decides the real
    placement -- for a real model, so the panel and the loader can no longer
    disagree.
    """
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        model = body.get("model") or sigma_engine.loaded_model_name
        if not model:
            default_dir = sigma_engine.find_valid_model_directory()
            if default_dir:
                model = default_dir[1]
        
        if not model:
            return self.send_json_response({
                "success": False,
                "error": "Nessun modello indicato e nessuno caricato: il "
                         "partizionamento dipende dal modello, non e' una "
                         "proprieta' della sola macchina.",
            }, 400)

        result = sigma_engine.plan_for_model(
            model_identifier=model,
            context_tokens=int(body.get("context_tokens", 32768)),
            force_quantization=body.get("quantization"),
        )
        if not result.get("success"):
            return self.send_json_response(result, 404)

        return self.send_json_response({
            "success": True,
            "model": model,
            "tiering_plan": _tiering_view(result),
            "plan": result.get("plan"),
        })
    except Exception as exc:
        log.error(f"handle_engine_partition error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def _tiering_view(result: dict) -> dict:
    """
    The plan rendered as the tier counts the settings panel reads.

    Derived from the same budgets the loader spends, so a layer counted here in
    VRAM is a layer accelerate will be told to put there. Layers per tier come
    from each device's share of the weight budget: that is exactly how the
    filling loop assigns them.
    """
    plan = result.get("plan") or {}
    facts = result.get("facts") or {}
    layers = int(facts.get("num_hidden_layers") or 0)
    weights_gb = float(plan.get("model_footprint_gb") or 0.0)

    def budget_gb(value) -> float:
        try:
            return float(str(value).replace("GiB", "").strip())
        except (TypeError, ValueError):
            return 0.0

    per_layer = (weights_gb / layers) if layers else 0.0
    budgets = plan.get("max_memory") or {}
    gpu_keys = sorted(k for k in budgets if str(k).isdigit())

    def tier(count: int) -> dict:
        return {
            "count": count,
            "estimated_memory_gb": round(count * per_layer, 2),
        }

    placed = 0
    tiers = []
    for key in gpu_keys:
        if per_layer <= 0:
            break
        fits = min(int(budget_gb(budgets[key]) / per_layer), layers - placed)
        tiers.append(max(fits, 0))
        placed += max(fits, 0)

    host = min(layers - placed, layers) if plan.get("uses_host_ram") else 0
    placed += host
    disk = max(layers - placed, 0) if plan.get("uses_disk") else 0

    return {
        "total_layers": layers,
        "quantization": plan.get("quantization"),
        "context_tokens": plan.get("context_tokens"),
        "tier0_primary_vram": tier(tiers[0] if tiers else 0),
        "tier1_secondary_vram": tier(sum(tiers[1:]) if len(tiers) > 1 else 0),
        "tier2_host_ram": tier(host),
        "tier3_disk_shards": dict(
            tier(disk),
            streaming_mode="accelerate_offload_folder" if disk else "disabled",
        ),
        "warnings": plan.get("warnings") or [],
    }


def handle_engine_hf_import(self):
    """POST /api/engine/hf/import — Direct Hugging Face Model Import & Hardware Maximizer."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        repo_id = body.get("repo_id")
        filename = body.get("filename")
        quantization = body.get("quantization")
        token = body.get("hf_token")

        if not repo_id:
            return self.send_json_response({"success": False, "error": "repo_id obbligatorio"}, 400)

        res = sigma_engine.import_and_optimize_hf_model(
            repo_id=repo_id,
            filename=filename,
            quantization=quantization,
            hf_token=token
        )
        return self.send_json_response(res)
    except Exception as exc:
        log.error(f"handle_engine_hf_import error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_plan(self):
    """
    POST /api/engine/plan — Placement plan for a model without loading it.

    Lets the UI show which tiers a model will occupy, and any warnings, before
    paying the cost of a load.
    """
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        res = sigma_engine.plan_for_model(
            model_identifier=body.get("model"),
            context_tokens=int(body.get("context_tokens", 32768)),
            force_quantization=body.get("quantization"),
        )
        return self.send_json_response(res, 200 if res.get("success") else 404)
    except Exception as exc:
        log.error(f"handle_engine_plan error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_benchmark(self):
    """
    POST /api/engine/benchmark — Measures prefill and decode speed on this host.

    Returns a verdict naming what the model is bound by, so tuning targets the
    actual limit rather than an assumed one.
    """
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        res = sigma_engine.benchmark(
            prompt_tokens=int(body.get("prompt_tokens", 128)),
            decode_tokens=int(body.get("decode_tokens", 24)),
            profile_modules=bool(body.get("profile_modules", False)),
            model_name=body.get("model"),
        )
        return self.send_json_response(res, 200 if res.get("success") else 400)
    except Exception as exc:
        log.error(f"handle_engine_benchmark error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_unload(self):
    """POST /api/engine/unload — Releases the active model and frees VRAM."""
    try:
        return self.send_json_response(sigma_engine.unload())
    except Exception as exc:
        log.error(f"handle_engine_unload error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_models(self):
    """GET /api/engine/models — Returns active model, local catalog, and recommended Hugging Face models dynamically tailored to current hardware."""
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        status = sigma_engine.get_status()
        optimizations = sigma_engine._generate_default_optimizations()

        # Probe current machine hardware
        hw = UniversalHardwareProbe.probe_all()
        accs = hw.get("accelerators", [])
        sys_info = hw.get("system", {})
        ram_gb = sys_info.get("ram_gb", 8.0)
        cpu_cores = sys_info.get("cpu_cores", 4)
        is_rpi = sys_info.get("is_raspberry_pi", False)
        is_apple = sys_info.get("is_apple_silicon", False)

        total_vram = sum(a.get("total_vram_gb", 0) for a in accs)
        gpu_names = [a.get("name", "GPU") for a in accs if a.get("name")]

        # Determine primary device name & architecture description
        if len(gpu_names) > 1:
            sharding_desc = f"Multi-GPU ({' + '.join(gpu_names)})"
            primary_device = gpu_names[0]
        elif len(gpu_names) == 1:
            sharding_desc = f"GPU ({gpu_names[0]} • {total_vram:.1f} GB VRAM)"
            primary_device = gpu_names[0]
        elif is_apple:
            sharding_desc = f"Apple Silicon Metal (MPS Unified RAM • {ram_gb:.0f} GB)"
            primary_device = "Apple Silicon (MPS)"
        elif is_rpi:
            sharding_desc = f"Raspberry Pi ARM64 (CPU • {ram_gb:.0f} GB RAM)"
            primary_device = "Raspberry Pi CPU"
        else:
            sharding_desc = f"CPU Host ({cpu_cores} Cores • {ram_gb:.0f} GB RAM)"
            primary_device = "CPU Host"

        # Enrich optimizations with hardware description
        optimizations["sharding_desc"] = sharding_desc
        optimizations["primary_device"] = primary_device
        optimizations["total_vram_gb"] = total_vram
        optimizations["ram_gb"] = ram_gb

        # Generate dynamic recommendations based on available memory
        if total_vram >= 24 or (is_apple and ram_gb >= 64):
            # Heavyweight 32B-70B tier
            recommended_models = [
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 32B",
                    "quantization": "Q4_K_M",
                    "size_gb": 19.8,
                    "target_device": f"{primary_device} Full VRAM"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-Coder-32B-Instruct-GGUF",
                    "filename": "Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 Coder 32B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 19.8,
                    "target_device": f"{primary_device} (Coding 32B)"
                },
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 14B",
                    "quantization": "Q4_K_M",
                    "size_gb": 8.9,
                    "target_device": f"{primary_device} (Ultra Veloce)"
                },
                {
                    "repo_id": "bartowski/Llama-3.3-70B-Instruct-GGUF",
                    "filename": "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
                    "name": "Llama 3.3 70B Instruct (MoE Sharded)",
                    "quantization": "Q4_K_M",
                    "size_gb": 42.0,
                    "target_device": f"{sharding_desc} + RAM"
                }
            ]
        elif total_vram >= 12 or (is_apple and ram_gb >= 24):
            # 14B tier
            recommended_models = [
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 14B",
                    "quantization": "Q4_K_M",
                    "size_gb": 8.9,
                    "target_device": f"{primary_device} Full VRAM"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-Coder-14B-Instruct-GGUF",
                    "filename": "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 Coder 14B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 8.9,
                    "target_device": f"{primary_device} (Coding 14B)"
                },
                {
                    "repo_id": "unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Llama 8B",
                    "quantization": "Q4_K_M",
                    "size_gb": 4.9,
                    "target_device": f"{primary_device} (Ultra Veloce)"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-7B-Instruct-GGUF",
                    "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 7B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 4.7,
                    "target_device": f"{primary_device} (All-Rounder)"
                }
            ]
        elif total_vram >= 6 or (is_apple and ram_gb >= 16):
            # 7B-8B tier
            recommended_models = [
                {
                    "repo_id": "unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Llama 8B",
                    "quantization": "Q4_K_M",
                    "size_gb": 4.9,
                    "target_device": f"{primary_device} Full VRAM"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-Coder-7B-Instruct-GGUF",
                    "filename": "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 Coder 7B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 4.7,
                    "target_device": f"{primary_device} (Coding 7B)"
                },
                {
                    "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
                    "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
                    "name": "Llama 3.2 3B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 2.0,
                    "target_device": f"{primary_device} (Ultra Veloce)"
                },
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 1.5B",
                    "quantization": "Q4_K_M",
                    "size_gb": 1.1,
                    "target_device": f"{primary_device} (Reasoning Leggero)"
                }
            ]
        else:
            # Low VRAM / CPU / Raspberry Pi tier (0.5B - 3B, up to 7B lightweight)
            recommended_models = [
                {
                    "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
                    "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
                    "name": "Llama 3.2 3B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 2.0,
                    "target_device": f"{primary_device} (~35 tok/s)"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-Coder-1.5B-Instruct-GGUF",
                    "filename": "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 Coder 1.5B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 1.1,
                    "target_device": f"{primary_device} (Coding Leggero)"
                },
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 1.5B",
                    "quantization": "Q4_K_M",
                    "size_gb": 1.1,
                    "target_device": f"{primary_device} (Reasoning Leggero)"
                },
                {
                    "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                    "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
                    "name": "Qwen 2.5 0.5B Instruct (Ultra-Light)",
                    "quantization": "Q4_K_M",
                    "size_gb": 0.4,
                    "target_device": f"{primary_device} (Massima Velocità)"
                }
            ]

        return self.send_json_response({
            "success": True,
            "loaded_model": sigma_engine.loaded_model,
            "loaded_model_name": sigma_engine.loaded_model_name,
            "active_backend": sigma_engine.active_backend,
            "optimizations": optimizations,
            "recommended_models": recommended_models
        })
    except Exception as exc:
        log.error(f"handle_engine_models error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_optimize(self):
    """POST /api/engine/optimize — Recalibrates and maximizes hardware dispatching."""
    try:
        sigma_engine.hardware_profile = UniversalHardwareProbe.probe_all()
        optimizations = sigma_engine._generate_default_optimizations()
        return self.send_json_response({
            "success": True,
            "message": (
                f"Hardware riesaminato: backend {optimizations['backend']}, "
                f"attenzione {optimizations['attention_kernel']}."
            ),
            "optimizations": optimizations
        })
    except Exception as exc:
        log.error(f"handle_engine_optimize error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)

