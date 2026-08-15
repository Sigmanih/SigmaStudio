# ==============================================================================
# core/modules/sigma_model_hub/backend/model_inventory.py
# Local Model Storage Inventory & SigmaEngine Deployment Gateway
# ==============================================================================
from __future__ import annotations
import os
import re
import time
from typing import Dict, Any, List, Optional
from core.logger import get_logger
from core.engine.unified_runtime import sigma_engine
from core.engine.hardware_probe import UniversalHardwareProbe
from core.engine.weight_profiler import WeightSaliencyProfiler

log = get_logger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "models")


def scan_local_models(custom_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scans local disk for downloaded model files (.gguf, .safetensors, .bin)."""
    base_dir = custom_dir if custom_dir and os.path.exists(custom_dir) else MODELS_DIR
    os.makedirs(base_dir, exist_ok=True)
    results = []

    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith((".gguf", ".safetensors", ".bin", ".pt")):
                full_path = os.path.join(root, f)
                try:
                    stat = os.stat(full_path)
                    size_bytes = stat.st_size
                    size_gb = round(size_bytes / (1024**3), 2)
                    size_mb = round(size_bytes / (1024**2), 1)

                    # Extract model name and quantization
                    filename = f
                    fmt = "GGUF" if f.endswith(".gguf") else ("Safetensors" if f.endswith(".safetensors") else "PyTorch Bin")
                    
                    quant_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|INT8|INT4|AWQ|EXL2)', f, re.IGNORECASE)
                    quantization = quant_match.group(1).upper() if quant_match else "Standard"

                    # Estimate required VRAM
                    est_vram_gb = round(size_gb * 1.15 + 0.8, 1)
                    
                    is_active = (sigma_engine.loaded_model_name == f or sigma_engine.loaded_model_name == full_path)

                    results.append({
                        "filename": filename,
                        "path": full_path,
                        "format": fmt,
                        "quantization": quantization,
                        "size_gb": size_gb,
                        "size_mb": size_mb,
                        "est_vram_gb": est_vram_gb,
                        "is_active_in_engine": is_active,
                        "modified_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                    })
                except Exception as ex:
                    log.debug(f"[ModelInventory] Error reading {full_path}: {ex}")

    # Sort by modification time descending
    results.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
    return results


def deploy_model_to_sigma_engine(
    model_path: str,
    quantization: Optional[str] = None,
    primary_gpu_layers: int = -1,
    enable_moe_cache: bool = True
) -> Dict[str, Any]:
    """Registers and activates a local model inside UniversalSigmaEngine."""
    if not os.path.exists(model_path):
        return {"success": False, "error": f"File modello non trovato: {model_path}"}

    model_name = os.path.basename(model_path)
    file_size_gb = round(os.path.getsize(model_path) / (1024**3), 2)

    # Calculate optimal tiering across available GPUs and RAM
    probe = UniversalHardwareProbe.probe_all()
    accs = probe.get("accelerators", [])
    vram_0 = accs[0].get("free_vram_gb", 16.0) if accs else 16.0
    vram_1 = accs[1].get("free_vram_gb", 8.0) if len(accs) > 1 else 0.0
    ram_gb = probe.get("ram", {}).get("available_gb", 64.0)

    tiering = WeightSaliencyProfiler.partition_model_layers(
        total_layers=32,
        vram_primary_gb=vram_0,
        vram_secondary_gb=vram_1,
        system_ram_gb=ram_gb,
        model_size_gb=file_size_gb,
        is_moe=("moe" in model_name.lower() or "16x" in model_name.lower() or "8x" in model_name.lower())
    )

    # Set as active model in SigmaEngine
    sigma_engine.loaded_model_name = model_name
    sigma_engine.loaded_model = {
        "name": model_name,
        "path": model_path,
        "format": "GGUF" if model_name.endswith(".gguf") else "Safetensors",
        "size_gb": file_size_gb,
        "quantization": quantization or "Auto",
        "backend": sigma_engine.active_backend,
        "tiering": tiering,
        "loaded_at": time.time()
    }

    log.info(f"[ModelInventory] Modello {model_name} caricato con successo in SigmaEngine!")

    return {
        "success": True,
        "message": f"Modello {model_name} allocato e pronto in SigmaEngine.",
        "model_name": model_name,
        "tiering_plan": tiering,
        "active_backend": sigma_engine.active_backend
    }


def unload_sigma_engine_model() -> Dict[str, Any]:
    """Unloads active model from SigmaEngine and frees GPU/RAM memory."""
    prev = sigma_engine.loaded_model_name
    sigma_engine.loaded_model_name = None
    sigma_engine.loaded_model = None

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass

    log.info(f"[ModelInventory] Modello {prev} scaricato da SigmaEngine. Memoria liberata.")
    return {
        "success": True,
        "message": f"Modello {prev or 'attivo'} scaricato da SigmaEngine. Memoria VRAM/RAM liberata."
    }
