# ==============================================================================
# core/engine/engine_router.py — HTTP Route Handlers for SigmaEngine
# ==============================================================================
from typing import Dict, Any
from core.logger import get_logger
from core.engine.unified_runtime import sigma_engine
from core.engine.hardware_probe import UniversalHardwareProbe
from core.engine.weight_profiler import WeightSaliencyProfiler

log = get_logger(__name__)


def handle_engine_status(self):
    """GET /api/engine/status — Returns engine health and active backend."""
    return self.send_json_response(sigma_engine.get_status())


def handle_engine_profile(self):
    """GET /api/engine/profile — Comprehensive hardware benchmark & drive matrix."""
    probe = UniversalHardwareProbe.probe_all()
    return self.send_json_response({"success": True, "profile": probe})


def handle_engine_partition(self):
    """POST /api/engine/partition — Calculate optimal layer tiering for a given model size."""
    try:
        body = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        total_layers = int(body.get("total_layers", 32))
        model_size_gb = float(body.get("model_size_gb", 8.0))
        is_moe = bool(body.get("is_moe", False))
        
        probe = UniversalHardwareProbe.probe_all()
        accs = probe.get("accelerators", [])
        vram_0 = accs[0].get("free_vram_gb", 0.0) if accs else 0.0
        vram_1 = accs[1].get("free_vram_gb", 0.0) if len(accs) > 1 else 0.0
        ram_gb = probe.get("ram", {}).get("available_gb", 16.0)

        plan = WeightSaliencyProfiler.partition_model_layers(
            total_layers=total_layers,
            vram_primary_gb=vram_0,
            vram_secondary_gb=vram_1,
            system_ram_gb=ram_gb,
            model_size_gb=model_size_gb,
            is_moe=is_moe
        )
        return self.send_json_response({"success": True, "tiering_plan": plan})
    except Exception as exc:
        log.error(f"handle_engine_partition error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


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


def handle_engine_models(self):
    """GET /api/engine/models — Returns active model, local catalog, and recommended Hugging Face models."""
    try:
        status = sigma_engine.get_status()
        optimizations = getattr(sigma_engine, 'optimization_telemetry', {})
        return self.send_json_response({
            "success": True,
            "loaded_model": sigma_engine.loaded_model,
            "loaded_model_name": sigma_engine.loaded_model_name,
            "active_backend": sigma_engine.active_backend,
            "optimizations": optimizations,
            "recommended_models": [
                {
                    "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Qwen 14B",
                    "quantization": "Q4_K_M",
                    "size_gb": 8.9,
                    "target_device": "RTX 5070 Ti (16 GB) + FlashAttention-2"
                },
                {
                    "repo_id": "unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF",
                    "filename": "DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
                    "name": "DeepSeek R1 Distill Llama 8B",
                    "quantization": "Q4_K_M",
                    "size_gb": 4.9,
                    "target_device": "RTX 5060 (8 GB) Full VRAM"
                },
                {
                    "repo_id": "bartowski/Qwen2.5-Coder-14B-Instruct-GGUF",
                    "filename": "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf",
                    "name": "Qwen 2.5 Coder 14B Instruct",
                    "quantization": "Q4_K_M",
                    "size_gb": 8.9,
                    "target_device": "RTX 5070 Ti (16 GB)"
                },
                {
                    "repo_id": "bartowski/Llama-3.3-70B-Instruct-GGUF",
                    "filename": "Llama-3.3-70B-Instruct-Q4_K_M.gguf",
                    "name": "Llama 3.3 70B Instruct (MoE Sharded)",
                    "quantization": "Q4_K_M",
                    "size_gb": 42.0,
                    "target_device": "Multi-GPU Dual RTX 5070 Ti + 5060 + RAM"
                }
            ]
        })
    except Exception as exc:
        log.error(f"handle_engine_models error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_engine_optimize(self):
    """POST /api/engine/optimize — Recalibrates and maximizes hardware dispatching."""
    try:
        sigma_engine.hardware_profile = UniversalHardwareProbe.probe_all()
        sigma_engine.optimization_telemetry = sigma_engine._generate_default_optimizations()
        return self.send_json_response({
            "success": True,
            "message": "Parametri di calcolo e FlashAttention-2 ricalibrati con successo.",
            "optimizations": sigma_engine.optimization_telemetry
        })
    except Exception as exc:
        log.error(f"handle_engine_optimize error: {exc}")
        return self.send_json_response({"success": False, "error": str(exc)}, 500)

