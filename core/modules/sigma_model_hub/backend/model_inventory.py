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


def _get_workspace_root() -> str:
    """Finds the root directory containing data/ or sigma_server.py."""
    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, "data")):
        return cwd
    curr = os.path.abspath(os.path.dirname(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(curr, "sigma_server.py")) or os.path.exists(os.path.join(curr, "data")):
            return curr
        curr = os.path.dirname(curr)
    return cwd


ROOT_DIR = _get_workspace_root()
MODELS_DIR = os.path.join(ROOT_DIR, "data", "models")


def scan_local_models(custom_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scans local disk for downloaded model files (.gguf, .safetensors, .bin, multi-shard repos)."""
    base_dir = custom_dir if custom_dir and os.path.exists(custom_dir) else MODELS_DIR
    os.makedirs(base_dir, exist_ok=True)
    results = []

    try:
        entries = os.listdir(base_dir)
    except Exception as e:
        log.warning(f"[ModelInventory] Error reading {base_dir}: {e}")
        return []

    for entry in entries:
        full_entry_path = os.path.join(base_dir, entry)

        # 1. Check if entry is a directory (e.g. Qwen--Qwen3.8-27B or Multi-Shard Model Repository)
        if os.path.isdir(full_entry_path):
            try:
                dir_files = os.listdir(full_entry_path)
                shard_files = [f for f in dir_files if f.endswith((".safetensors", ".bin", ".gguf", ".pt"))]
                if not shard_files:
                    continue

                total_bytes = sum(os.path.getsize(os.path.join(full_entry_path, f)) for f in shard_files)
                size_gb = round(total_bytes / (1024**3), 2)
                size_mb = round(total_bytes / (1024**2), 1)

                raw_name = entry.replace("--", "/")
                is_sharded = len(shard_files) > 1
                primary_file = os.path.join(full_entry_path, "model.safetensors.index.json") if os.path.exists(os.path.join(full_entry_path, "model.safetensors.index.json")) else os.path.join(full_entry_path, shard_files[0])

                if any(f.endswith(".gguf") for f in shard_files):
                    fmt = f"GGUF ({len(shard_files)} Shard)" if is_sharded else "GGUF"
                elif any(f.endswith(".safetensors") for f in shard_files):
                    fmt = f"Safetensors ({len(shard_files)} Shards • Completo)" if is_sharded else "Safetensors"
                else:
                    fmt = "PyTorch Bin"

                quant_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4|AWQ|EXL2)', entry, re.IGNORECASE)
                quantization = quant_match.group(1).upper() if quant_match else ("FP16 / BF16" if "safetensors" in fmt.lower() else "Standard")

                est_vram_gb = round(size_gb * 1.15 + 0.8, 1)
                stat = os.stat(full_entry_path)

                is_active = (
                    sigma_engine.loaded_model_name == raw_name or
                    sigma_engine.loaded_model_name == entry or
                    sigma_engine.loaded_model_name == full_entry_path
                )

                results.append({
                    "filename": raw_name,
                    "model_id": raw_name,
                    "display_name": raw_name,
                    "path": full_entry_path,
                    "primary_file": primary_file,
                    "format": fmt,
                    "quantization": quantization,
                    "is_repo_folder": True,
                    "total_shards": len(shard_files),
                    "size_gb": size_gb,
                    "size_mb": size_mb,
                    "size_label": f"~{size_gb:.1f} GB" if size_gb < 1000 else f"~{size_gb/1000:.1f} TB",
                    "est_vram_gb": est_vram_gb,
                    "is_active_in_engine": is_active,
                    "modified_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                })
            except Exception as ex:
                log.debug(f"[ModelInventory] Error reading directory {full_entry_path}: {ex}")

        # 2. Check if entry is a standalone single model file
        elif os.path.isfile(full_entry_path) and entry.endswith((".gguf", ".safetensors", ".bin", ".pt")):
            try:
                stat = os.stat(full_entry_path)
                size_bytes = stat.st_size
                size_gb = round(size_bytes / (1024**3), 2)
                size_mb = round(size_bytes / (1024**2), 1)

                fmt = "GGUF" if entry.endswith(".gguf") else ("Safetensors" if entry.endswith(".safetensors") else "PyTorch Bin")
                quant_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4|AWQ|EXL2)', entry, re.IGNORECASE)
                quantization = quant_match.group(1).upper() if quant_match else "Standard"
                est_vram_gb = round(size_gb * 1.15 + 0.8, 1)

                is_active = (
                    sigma_engine.loaded_model_name == entry or
                    sigma_engine.loaded_model_name == full_entry_path
                )

                results.append({
                    "filename": entry,
                    "model_id": entry,
                    "display_name": entry,
                    "path": full_entry_path,
                    "primary_file": full_entry_path,
                    "format": fmt,
                    "quantization": quantization,
                    "is_repo_folder": False,
                    "total_shards": 1,
                    "size_gb": size_gb,
                    "size_mb": size_mb,
                    "size_label": f"~{size_gb:.1f} GB" if size_gb < 1000 else f"~{size_gb/1000:.1f} TB",
                    "est_vram_gb": est_vram_gb,
                    "is_active_in_engine": is_active,
                    "modified_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                })
            except Exception as ex:
                log.debug(f"[ModelInventory] Error reading file {full_entry_path}: {ex}")

    results.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
    return results


def deploy_model_to_sigma_engine(
    model_path: str,
    quantization: Optional[str] = None,
    primary_gpu_layers: int = -1,
    enable_moe_cache: bool = True
) -> Dict[str, Any]:
    """Registers and activates a local model inside UniversalSigmaEngine."""
    resolved_path = model_path

    if not os.path.exists(resolved_path):
        # 1. Try relative to MODELS_DIR
        candidate1 = os.path.join(MODELS_DIR, model_path)
        candidate2 = os.path.join(MODELS_DIR, model_path.replace("/", "--"))
        candidate3 = os.path.join(MODELS_DIR, model_path.replace("--", "/"))
        if os.path.exists(candidate1):
            resolved_path = candidate1
        elif os.path.exists(candidate2):
            resolved_path = candidate2
        elif os.path.exists(candidate3):
            resolved_path = candidate3
        else:
            # 2. Search in local models inventory
            for m in scan_local_models():
                if m.get("filename") == model_path or m.get("model_id") == model_path or m.get("display_name") == model_path:
                    resolved_path = m.get("path")
                    break

    if not resolved_path or not os.path.exists(resolved_path):
        return {"success": False, "error": f"File modello non trovato su disco: {model_path}"}

    model_name = os.path.basename(resolved_path).replace("--", "/")
    
    if os.path.isdir(resolved_path):
        dir_files = [os.path.join(resolved_path, f) for f in os.listdir(resolved_path) if f.endswith((".safetensors", ".bin", ".gguf", ".pt"))]
        file_size_gb = round(sum(os.path.getsize(f) for f in dir_files) / (1024**3), 2) if dir_files else 10.0
    else:
        file_size_gb = round(os.path.getsize(resolved_path) / (1024**3), 2)

    # Calculate optimal tiering across available GPUs and RAM
    probe = UniversalHardwareProbe.probe_all()
    accs = probe.get("accelerators", [])
    vram_0 = accs[0].get("free_vram_gb", 16.0) if accs else 16.0
    vram_1 = accs[1].get("free_vram_gb", 8.0) if len(accs) > 1 else 0.0
    ram_gb = probe.get("ram", {}).get("available_gb", 64.0)

    tiering = WeightSaliencyProfiler.partition_model_layers(
        total_layers=32 if "27b" not in model_name.lower() and "70b" not in model_name.lower() else 64,
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
        "path": resolved_path,
        "format": "GGUF" if model_name.endswith(".gguf") else "Safetensors",
        "size_gb": file_size_gb,
        "quantization": quantization or "Auto (Tiered)",
        "backend": sigma_engine.active_backend,
        "tiering": tiering,
        "loaded_at": time.time()
    }

    # Automatically set this model as active for Chat
    try:
        from core.ai_brain import load_ai_config, save_ai_config
        cfg = load_ai_config()
        cfg["active_model"] = model_name
        cfg["active_provider"] = "sigma_engine"
        if "providers" not in cfg:
            cfg["providers"] = {}
        if "sigma_engine" not in cfg["providers"]:
            cfg["providers"]["sigma_engine"] = {
                "label": "SigmaEngine (Nativo & Sharded)",
                "endpoint": "http://localhost:8000/api/engine"
            }
        cfg["providers"]["sigma_engine"]["model"] = model_name
        if "models" not in cfg["providers"]["sigma_engine"]:
            cfg["providers"]["sigma_engine"]["models"] = []
        if model_name not in cfg["providers"]["sigma_engine"]["models"]:
            cfg["providers"]["sigma_engine"]["models"].insert(0, model_name)
        save_ai_config(cfg)
    except Exception as ex:
        log.debug(f"[ModelInventory] Note updating ai_config: {ex}")

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
