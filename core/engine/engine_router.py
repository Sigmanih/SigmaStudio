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
