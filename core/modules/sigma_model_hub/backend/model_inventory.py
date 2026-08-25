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

log = get_logger(__name__)


def _get_workspace_root() -> str:
    """The installation root, from the kernel path service.

    Cercava prima os.getcwd(), quindi rispondeva diversamente a seconda di
    dove veniva lanciato il server.
    """
    from core.paths import project_root
    return str(project_root())


from core.model_paths import models_dir as _active_models_dir, project_root

ROOT_DIR = project_root()


def _models_dir() -> str:
    """The active models directory, shared with the engine and downloader."""
    return _active_models_dir()


def _earliest_weight_time(folder: str, weight_files) -> float:
    """
    When this model first appeared on disk.

    The oldest weight file, not the folder's own timestamp: a directory keeps
    being touched as files are added, so it says when the download finished
    rather than when it started, and it says nothing at all about a model that
    was simply pointed at where it already lived.
    """
    times = []
    for name in weight_files:
        try:
            times.append(os.path.getctime(os.path.join(folder, name)))
        except Exception:
            continue
    return min(times) if times else os.path.getctime(folder)


def scan_local_models(custom_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scans local disk for downloaded model files (.gguf, .safetensors, .bin, multi-shard repos)."""
    base_dir = custom_dir if custom_dir and os.path.exists(custom_dir) else _models_dir()
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
                part_files = [f for f in dir_files if f.endswith((".part", ".download", ".tmp"))]
                has_tokenizer = any(f in dir_files for f in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "tokenizer.model")) or any(f.endswith(".gguf") for f in shard_files)
                
                if not shard_files and not part_files:
                    continue

                main_shards = [f for f in shard_files if not (
                    f.lower().startswith("mmproj") or "mmproj" in f.lower() or
                    "-clip-" in f.lower() or "_clip_" in f.lower() or f.lower().startswith("clip-")
                )]
                target_shards = main_shards if main_shards else shard_files
                has_mmproj = any(f not in main_shards for f in shard_files)

                total_bytes = sum(os.path.getsize(os.path.join(full_entry_path, f)) for f in target_shards)
                size_gb = round(total_bytes / (1024**3), 2)
                size_mb = round(total_bytes / (1024**2), 1)

                raw_name = entry.replace("--", "/")
                is_sharded = len(target_shards) > 1
                primary_file = os.path.join(full_entry_path, "model.safetensors.index.json") if os.path.exists(os.path.join(full_entry_path, "model.safetensors.index.json")) else (os.path.join(full_entry_path, target_shards[0]) if target_shards else full_entry_path)

                # Check if all declared shards exist
                is_complete = True
                if part_files:
                    is_complete = False
                elif not has_tokenizer and not any(f.endswith(".gguf") for f in target_shards):
                    is_complete = False

                if any(f.endswith(".gguf") for f in target_shards):
                    fmt = f"GGUF ({len(target_shards)} Shard)" if is_sharded else "GGUF"
                    if has_mmproj:
                        fmt += " + Vision (CLIP)"
                    fmt_tag = "GGUF"
                elif any(f.endswith(".safetensors") for f in target_shards):
                    if is_complete:
                        fmt = f"Safetensors ({len(target_shards)} Shards • Completo)" if is_sharded else "Safetensors"
                    else:
                        fmt = f"Safetensors ({len(target_shards)} Shards • Incompleto)"
                    fmt_tag = "SAFETENSORS"
                else:
                    fmt = "PyTorch Bin"
                    fmt_tag = "BIN"

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
                    "format_tag": fmt_tag,
                    "quantization": quantization,
                    "is_repo_folder": True,
                    "is_complete": is_complete,
                    "is_multimodal": has_mmproj,
                    "has_part_files": len(part_files) > 0,
                    "total_shards": len(target_shards),
                    "size_gb": size_gb,
                    "size_mb": size_mb,
                    "size_label": f"~{size_gb:.1f} GB" if size_gb < 1000 else f"~{size_gb/1000:.1f} TB",
                    "est_vram_gb": est_vram_gb,
                    "is_active_in_engine": is_active,
                    "modified_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    "added_at": time.strftime(
                        '%Y-%m-%d %H:%M:%S',
                        time.localtime(_earliest_weight_time(full_entry_path, target_shards))
                    ),
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
                fmt_tag = ("GGUF" if entry.endswith(".gguf")
                           else "SAFETENSORS" if entry.endswith(".safetensors") else "BIN")
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
                    "format_tag": fmt_tag,
                    "quantization": quantization,
                    "is_repo_folder": False,
                    "total_shards": 1,
                    "size_gb": size_gb,
                    "size_mb": size_mb,
                    "size_label": f"~{size_gb:.1f} GB" if size_gb < 1000 else f"~{size_gb/1000:.1f} TB",
                    "est_vram_gb": est_vram_gb,
                    "is_active_in_engine": is_active,
                    "modified_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    "added_at": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_ctime)),
                })
            except Exception as ex:
                log.debug(f"[ModelInventory] Error reading file {full_entry_path}: {ex}")

    results.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
    return results


def deploy_model_to_sigma_engine(
    model_path: str,
    quantization: Optional[str] = None,
    primary_gpu_layers: int = -1,
) -> Dict[str, Any]:
    """Registers and activates a local model inside UniversalSigmaEngine."""
    resolved_path = model_path

    if not os.path.exists(resolved_path):
        # 1. Try relative to MODELS_DIR
        candidate1 = os.path.join(_models_dir(), model_path)
        candidate2 = os.path.join(_models_dir(), model_path.replace("/", "--"))
        candidate3 = os.path.join(_models_dir(), model_path.replace("--", "/"))
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

    # Ask the engine to plan this model against real hardware. Planning is
    # cheap and does not touch VRAM, so selecting a model stays responsive
    # while still reporting where it would actually land.
    canonical_name = model_name
    resolved = sigma_engine.find_valid_model_directory(model_path) or \
        sigma_engine.find_valid_model_directory(model_name)
    if resolved:
        canonical_name = resolved[1]

    planned = sigma_engine.plan_for_model(canonical_name)
    tiering = planned.get("plan", {}) if planned.get("success") else {}

    # Only claim a model is loaded when one really is. The engine compares
    # loaded_model_name against the directory name it resolves from a request;
    # writing a different spelling here (Qwen/X instead of Qwen--X) makes every
    # later generate believe the wrong model is resident and reload on top of
    # it, briefly holding two copies in VRAM and spilling the second to CPU.
    if sigma_engine.model_instance is None:
        sigma_engine.loaded_model_name = canonical_name
        sigma_engine.loaded_model = {
            "name": canonical_name,
            "path": resolved_path,
            "format": "GGUF" if resolved_path.endswith(".gguf") else "Safetensors",
            "size_gb": file_size_gb,
            "quantization": (
                quantization or tiering.get("quantization", "Auto (Tiered)")
            ),
            "backend": sigma_engine.active_backend,
            "plan": tiering,
            "status": "selected",
            "loaded_at": time.time(),
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

    log.info(
        "[ModelInventory] Modello %s selezionato in SigmaEngine (piano: %s).",
        canonical_name, tiering.get("quantization", "n/d"),
    )

    return {
        "success": True,
        "message": (
            f"Modello {model_name} selezionato. Verra' caricato al primo "
            "messaggio, oppure e' gia' residente se in uso."
        ),
        "model_name": canonical_name,
        "tiering_plan": tiering,
        "active_backend": sigma_engine.active_backend
    }



def unload_sigma_engine_model() -> Dict[str, Any]:
    """
    Releases the active model from SigmaEngine and returns the memory.

    Delegates to the engine rather than clearing metadata here: the weights are
    held by model_instance and by accelerate's dispatch hooks, so dropping the
    name alone frees nothing while convincing the engine that nothing is loaded.
    """
    prev = sigma_engine.loaded_model_name
    result = sigma_engine.unload()
    freed_gb = result.get("freed_vram_gb", 0.0)

    log.info(
        "[ModelInventory] Modello %s scaricato da SigmaEngine (%.2f GB liberati).",
        prev, freed_gb,
    )
    return {
        "success": True,
        "freed_vram_gb": freed_gb,
        "message": (
            f"Modello {prev or 'attivo'} scaricato. "
            f"{freed_gb:.1f} GB di memoria liberati."
            if prev else "Nessun modello era caricato."
        ),
    }


def delete_local_model(model_path_or_id: str, custom_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely deletes a downloaded model file or repository folder from disk.
    Prevents directory traversal and ensures safe sandbox boundaries.
    """
    import shutil
    if not model_path_or_id or not str(model_path_or_id).strip():
        return {"success": False, "error": "Identificativo o percorso del modello non valido"}

    base_dir = os.path.abspath(custom_dir if custom_dir and os.path.exists(custom_dir) else _models_dir())
    raw_target = str(model_path_or_id).strip()

    # 1. Determine target full path
    target_path = None
    if os.path.isabs(raw_target) and os.path.exists(raw_target):
        target_path = os.path.abspath(raw_target)
    else:
        # Check standard model naming variations
        candidates = [
            os.path.join(base_dir, raw_target),
            os.path.join(base_dir, raw_target.replace("/", "--")),
            os.path.join(base_dir, os.path.basename(raw_target)),
        ]
        for c in candidates:
            if os.path.exists(c):
                target_path = os.path.abspath(c)
                break

    if not target_path or not os.path.exists(target_path):
        return {"success": False, "error": f"Modello '{raw_target}' non trovato su disco"}

    # 2. Security sandbox check: target must be inside base_dir
    try:
        common = os.path.commonpath([base_dir, target_path])
        if os.path.abspath(common) != base_dir:
            return {"success": False, "error": "Operazione non consentita al di fuori della cartella modelli"}
    except Exception:
        return {"success": False, "error": "Verifica di sicurezza percorso fallita"}

    if target_path == base_dir:
        return {"success": False, "error": "Non è possibile cancellare l'intera cartella radice dei modelli"}

    # 3. If model is currently loaded in SigmaEngine, unload it first
    try:
        if (sigma_engine.loaded_model_name and 
            (sigma_engine.loaded_model_name in target_path or target_path in sigma_engine.loaded_model_name)):
            sigma_engine.unload()
    except Exception as ex:
        log.warning(f"[ModelInventory] Warning unloading model before deletion: {ex}")

    # 4. Perform deletion
    try:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        # 5. Clean any matching residual .part files
        parent_dir = os.path.dirname(target_path)
        base_name = os.path.basename(target_path)
        part_candidates = [
            os.path.join(parent_dir, base_name + ".part"),
            os.path.join(parent_dir, base_name + ".tmp")
        ]
        for p in part_candidates:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        log.info(f"[ModelInventory] Modello rimosso con successo da disco: {target_path}")
        return {
            "success": True,
            "message": f"Modello '{os.path.basename(target_path)}' rimosso con successo dallo storage.",
            "deleted_path": target_path
        }
    except Exception as e:
        log.error(f"[ModelInventory] Errore cancellazione modello {target_path}: {e}")
        return {"success": False, "error": f"Errore durante l'eliminazione dei file: {str(e)}"}

