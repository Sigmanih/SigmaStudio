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


from core.model_paths import (models_dir as _active_models_dir, all_models_dirs,
                              extra_models_dirs, project_root)

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


def _extract_author_and_name(raw_name: str) -> tuple[str, str, bool]:
    """Extracts author/organization, clean model name, and official provider status."""
    try:
        from core.modules.sigma_model_hub.backend.hf_client import is_official_provider
    except Exception:
        def is_official_provider(a, m): return False

    name_clean = raw_name.replace('\\', '/')
    if name_clean.startswith("models--"):
        parts = name_clean.split("--")
        if len(parts) >= 3:
            author = parts[1]
            m_name = "--".join(parts[2:])
            return author, m_name, is_official_provider(author, f"{author}/{m_name}")
    if '/' in name_clean:
        parts = name_clean.split('/')
        author = parts[0]
        m_name = "/".join(parts[1:])
        return author, m_name, is_official_provider(author, name_clean)

    low = name_clean.lower()
    if low.startswith("sigma"):
        return "sigmanih", name_clean, True
    if low.startswith("qwen"):
        return "Qwen", name_clean, True
    if low.startswith("deepseek"):
        return "deepseek-ai", name_clean, True
    if low.startswith("llama") or low.startswith("meta"):
        return "meta-llama", name_clean, True
    if low.startswith("gemma") or low.startswith("google"):
        return "google", name_clean, True
    if low.startswith("glm") or low.startswith("thudm") or low.startswith("chatglm") or low.startswith("zai"):
        return "zai-org", name_clean, True
    if low.startswith("mistral"):
        return "mistralai", name_clean, True
    if low.startswith("phi"):
        return "microsoft", name_clean, True

    return "", name_clean, False


def detect_family_and_category(name: str, architecture: str = "", author: str = "", is_multimodal: bool = False) -> tuple[str, str]:
    """Detects model architecture family (e.g. Gemma, Qwen, Llama) and task category (e.g. reasoning, code, vision, llm)."""
    text = f"{name} {architecture} {author}".lower()
    
    # 1. Family detection
    family = "Altro"
    if "gemma" in text:
        family = "Gemma"
    elif "qwen" in text:
        family = "Qwen"
    elif "llama" in text or "meta" in text:
        family = "Llama"
    elif "deepseek" in text:
        family = "DeepSeek"
    elif "mistral" in text or "mixtral" in text or "codestral" in text or "pixtral" in text:
        family = "Mistral"
    elif "phi" in text:
        family = "Phi"
    elif "glm" in text or "chatglm" in text or "zai" in text:
        family = "GLM"
    elif "stheno" in text:
        family = "Stheno"
    elif "solar" in text:
        family = "Solar"
    elif "yi" in text:
        family = "Yi"
    elif "command" in text or "cohere" in text:
        family = "Command"
    elif "granite" in text or "ibm" in text:
        family = "Granite"
    elif architecture:
        family = architecture.capitalize()

    # 2. Category detection
    category = "llm"
    if author.lower() == "sigmanih" or "sigmanih" in text:
        category = "sigmanih"
    elif "r1" in text or "reason" in text or "think" in text or "qwq" in text or "marco" in text:
        category = "reasoning"
    elif "coder" in text or "code" in text or "dev" in text or "starcoder" in text:
        category = "code"
    elif is_multimodal or "vision" in text or "vl" in text or "clip" in text or "mmproj" in text:
        category = "vision"
    elif "moe" in text or "expert" in text or "8x" in text or "16x" in text:
        category = "moe"

    return family, category


def _scan_single_dir(base_dir: str, is_extra: bool = False) -> List[Dict[str, Any]]:
    """Scansiona una specifica cartella su disco per modelli (.gguf, .safetensors, .bin, multi-shard)."""
    if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
        return []

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
                dir_files = []
                for root, _dirs, f_list in os.walk(full_entry_path):
                    for f in sorted(f_list):
                        dir_files.append(os.path.relpath(os.path.join(root, f), full_entry_path).replace("\\", "/"))

                shard_files = [f for f in dir_files if f.endswith((".safetensors", ".bin", ".gguf", ".pt"))]
                part_files = [f for f in dir_files if f.endswith((".part", ".download", ".tmp"))]
                has_tokenizer = any(os.path.basename(f) in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "tokenizer.model") for f in dir_files) or any(f.endswith(".gguf") for f in shard_files)

                if not shard_files and not part_files:
                    continue

                main_shards = [f for f in shard_files if not (
                    os.path.basename(f).lower().startswith("mmproj") or "mmproj" in os.path.basename(f).lower() or
                    "-clip-" in os.path.basename(f).lower() or "_clip_" in os.path.basename(f).lower() or os.path.basename(f).lower().startswith("clip-")
                )]
                target_shards = main_shards if main_shards else shard_files
                has_mmproj = any(f not in main_shards for f in shard_files)

                total_bytes = sum(os.path.getsize(os.path.join(full_entry_path, f)) for f in target_shards)
                size_gb = round(total_bytes / (1024**3), 2)
                size_mb = round(total_bytes / (1024**2), 1)

                raw_name = entry.replace("--", "/")
                is_sharded = len(target_shards) > 1
                primary_file = os.path.join(full_entry_path, "model.safetensors.index.json") if os.path.exists(os.path.join(full_entry_path, "model.safetensors.index.json")) else (os.path.join(full_entry_path, target_shards[0]) if target_shards else full_entry_path)

                # Check declared shards vs present shards
                total_shards_declared = len(target_shards) if target_shards else 1
                for f in target_shards + part_files:
                    m_match = re.search(r"-of-(\d+)\.(safetensors|gguf)", f)
                    if m_match:
                        try:
                            total_shards_declared = max(total_shards_declared, int(m_match.group(1)))
                        except Exception:
                            pass

                idx_path = os.path.join(full_entry_path, "model.safetensors.index.json")
                if os.path.exists(idx_path):
                    try:
                        with open(idx_path, "r", encoding="utf-8") as f_idx:
                            idx_d = json.load(f_idx)
                        declared_set = set(idx_d.get("weight_map", {}).values())
                        total_shards_declared = max(total_shards_declared, len(declared_set))
                    except Exception:
                        pass

                is_complete = True
                if part_files or len(part_files) > 0:
                    is_complete = False
                elif total_shards_declared > 1 and (len(target_shards) < total_shards_declared or (any(f.endswith(".safetensors") for f in target_shards) and not os.path.exists(idx_path))):
                    is_complete = False
                elif not has_tokenizer and not any(f.endswith(".gguf") for f in target_shards):
                    is_complete = False

                missing_shards_count = max(0, total_shards_declared - len(target_shards))

                if any(f.endswith(".gguf") for f in target_shards):
                    fmt = f"GGUF ({len(target_shards)} Shard)" if is_sharded else "GGUF"
                    if has_mmproj:
                        fmt += " + Vision (CLIP)"
                    fmt_tag = "GGUF"
                elif any(f.endswith(".safetensors") for f in target_shards):
                    if is_complete:
                        fmt = f"Safetensors ({len(target_shards)} Shards • Completo)" if is_sharded else "Safetensors"
                    else:
                        fmt = f"Safetensors ({len(target_shards)}/{total_shards_declared} Shards • Incompleto)"
                    fmt_tag = "SAFETENSORS"
                else:
                    fmt = "PyTorch Bin"
                    fmt_tag = "BIN"

                sample_tag_text = f"{entry} {' '.join(target_shards[:3])}"
                quant_match = re.search(r'(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4|AWQ|EXL2)', sample_tag_text, re.IGNORECASE)
                quantization = quant_match.group(1).upper() if quant_match else ("FP16 / BF16" if "safetensors" in fmt.lower() else "Standard")

                est_vram_gb = round(size_gb * 1.15 + 0.8, 1)
                stat = os.stat(full_entry_path)

                is_active = (
                    sigma_engine.loaded_model_name == raw_name or
                    sigma_engine.loaded_model_name == entry or
                    sigma_engine.loaded_model_name == full_entry_path
                )

                cfg_path = os.path.join(full_entry_path, "config.json")
                param_label = None
                arch_name = None
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f_cfg:
                            cfg_data = json.load(f_cfg)
                        text_cfg = cfg_data.get("text_config") if isinstance(cfg_data.get("text_config"), dict) else cfg_data
                        h_dim = text_cfg.get("hidden_size") or text_cfg.get("d_model")
                        n_lay = text_cfg.get("num_hidden_layers") or text_cfg.get("n_layer")
                        v_sz = text_cfg.get("vocab_size", 32000)
                        inter_sz = text_cfg.get("intermediate_size") or (h_dim * 4 if h_dim else 0)
                        arch_name = cfg_data.get("architectures", [""])[0] if cfg_data.get("architectures") else cfg_data.get("model_type", "")
                        if h_dim and n_lay:
                            tot_p = n_lay * (4 * h_dim**2 + 3 * h_dim * inter_sz) + v_sz * h_dim
                            p_b = round(tot_p / 1e9, 2)
                            param_label = f"{p_b:g}B" if p_b >= 1.0 else f"{int(p_b*1000)}M"
                            if "assistant" in str(arch_name).lower() or "draft" in str(arch_name).lower() or "assistant" in raw_name.lower():
                                param_label += " (Draft Assistant)"
                    except Exception:
                        pass

                if not param_label:
                    try:
                        from core.engine.model_inspector import ModelInspector
                        f_info = ModelInspector.inspect(full_entry_path)
                        if f_info:
                            arch_name = (f_info.architectures or [f_info.model_type or ""])[0]
                            if f_info.param_count:
                                p_b = round(f_info.param_count / 1e9, 2)
                                param_label = f"{p_b:g}B" if p_b >= 1.0 else f"{int(p_b*1000)}M"
                            elif f_info.total_bytes:
                                p_b = round(f_info.total_bytes * 8 / 4.8 / 1e9, 1)
                                param_label = f"~{p_b:g}B"
                            if f_info.is_moe and f_info.num_experts:
                                param_label = f"MoE {f_info.num_experts}x" + (f" ({param_label})" if param_label else "")
                    except Exception:
                        pass

                author, clean_name, is_official = _extract_author_and_name(raw_name)
                family, category = detect_family_and_category(
                    name=clean_name or raw_name,
                    architecture=arch_name or "",
                    author=author or "",
                    is_multimodal=has_mmproj
                )

                results.append({
                    "filename": raw_name,
                    "model_id": raw_name,
                    "display_name": raw_name,
                    "clean_name": clean_name,
                    "author": author,
                    "publisher": author or "Altro",
                    "family": family,
                    "category": category,
                    "is_official": is_official,
                    "path": full_entry_path,
                    "source_dir": base_dir,
                    "is_extra_dir": is_extra,
                    "primary_file": primary_file,
                    "format": fmt,
                    "format_tag": fmt_tag,
                    "quantization": quantization,
                    "params_label": param_label,
                    "architecture": arch_name,
                    "is_repo_folder": True,
                    "is_complete": is_complete,
                    "is_multimodal": has_mmproj,
                    "has_part_files": len(part_files) > 0,
                    "total_shards": len(target_shards),
                    "shards_present": len(target_shards),
                    "total_shards_declared": total_shards_declared,
                    "missing_shards_count": missing_shards_count,
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

                author, clean_name, is_official = _extract_author_and_name(entry)
                family, category = detect_family_and_category(
                    name=clean_name or entry,
                    architecture="",
                    author=author or "",
                    is_multimodal=False
                )

                results.append({
                    "filename": entry,
                    "model_id": entry,
                    "display_name": entry,
                    "clean_name": clean_name,
                    "author": author,
                    "publisher": author or "Altro",
                    "family": family,
                    "category": category,
                    "is_official": is_official,
                    "path": full_entry_path,
                    "source_dir": base_dir,
                    "is_extra_dir": is_extra,
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

    return results


def scan_local_models(custom_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scans local disk for downloaded model files (.gguf, .safetensors, .bin, multi-shard repos).
    
    Aggregates models from the primary models directory (or custom_dir if provided)
    and all configured extra directories (e.g. secondary drives or external paths).
    """
    primary_dir = os.path.abspath(custom_dir) if (custom_dir and os.path.exists(custom_dir)) else os.path.abspath(_models_dir())
    os.makedirs(primary_dir, exist_ok=True)

    results: List[Dict[str, Any]] = []
    seen_paths = set()

    # 1. Scansiona directory primaria
    for m in _scan_single_dir(primary_dir, is_extra=False):
        try:
            canon = os.path.abspath(m["path"])
            if canon not in seen_paths:
                seen_paths.add(canon)
                results.append(m)
        except Exception:
            results.append(m)

    # 2. Scansiona tutte le cartelle secondarie / extra collegate
    for extra_d in extra_models_dirs(refresh=True):
        try:
            extra_abs = os.path.abspath(extra_d)
            if extra_abs != primary_dir and os.path.exists(extra_abs) and os.path.isdir(extra_abs):
                for m in _scan_single_dir(extra_abs, is_extra=True):
                    canon = os.path.abspath(m["path"])
                    if canon not in seen_paths:
                        seen_paths.add(canon)
                        results.append(m)
        except Exception as ex:
            log.debug(f"[ModelInventory] Errore scansione directory modelli extra '{extra_d}': {ex}")

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
        part_files = [f for f in os.listdir(resolved_path) if f.endswith((".part", ".download", ".tmp"))]
        if part_files:
            return {
                "success": False,
                "error": f"Impossibile attivare '{model_name}': il download su disco è incompleto ({len(part_files)} file .part ancora in sospeso). Completa o riprendi il download dal Model Hub."
            }
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
        is_gguf = resolved_path.endswith(".gguf") or (
            os.path.isdir(resolved_path) and any(f.endswith(".gguf") for f in os.listdir(resolved_path))
        )
        sigma_engine.loaded_model = {
            "name": canonical_name,
            "path": resolved_path,
            "format": "GGUF" if is_gguf else "Safetensors",
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


def _percorso_modello(model_path_or_id: str, base_dir: str) -> Optional[str]:
    """Il percorso su disco di un modello, dato il nome o il percorso stesso."""
    raw = str(model_path_or_id or "").strip()
    if not raw:
        return None
    if os.path.isabs(raw) and os.path.exists(raw):
        return os.path.abspath(raw)
    for candidato in (
        os.path.join(base_dir, raw),
        os.path.join(base_dir, raw.replace("/", "--")),
        os.path.join(base_dir, os.path.basename(raw)),
        os.path.join(base_dir, f"{raw}.gguf"),
        os.path.join(base_dir, f"{raw.replace('/', '--')}.gguf"),
        os.path.join(base_dir, f"{os.path.basename(raw)}.gguf"),
    ):
        if os.path.exists(candidato):
            return os.path.abspath(candidato)
    return None


def _dentro_la_cartella(base_dir: str, percorso: str) -> bool:
    """Se un percorso sta davvero dentro la cartella dei modelli."""
    try:
        return os.path.abspath(os.path.commonpath([base_dir, percorso])) == base_dir
    except Exception:
        return False


def _trova_base_e_percorso(model_path_or_id: str, custom_dir: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Identifica la cartella base appropriata e il percorso reale del modello."""
    raw = str(model_path_or_id or "").strip()
    if not raw:
        return os.path.abspath(_models_dir()), None
    if custom_dir and os.path.exists(custom_dir):
        base_dirs = [os.path.abspath(custom_dir)]
    else:
        base_dirs = [os.path.abspath(d) for d in all_models_dirs() if os.path.exists(d)]
        if not base_dirs:
            base_dirs = [os.path.abspath(_models_dir())]

    for base in base_dirs:
        p = _percorso_modello(raw, base)
        if p and os.path.exists(p):
            return base, p
    return base_dirs[0], None



def rename_local_model(model_path_or_id: str, new_name: str,
                       custom_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Rinomina un modello sul disco, con le stesse protezioni della cancellazione.

    Il nuovo nome viene trattato come il nome di una cartella o di un file (.gguf).
    La forma `autore/modello` resta ammessa e diventa `autore--modello` sul disco.
    """
    base_dir, origine = _trova_base_e_percorso(model_path_or_id, custom_dir)
    if not origine or not os.path.exists(origine):
        return {"success": False, "error": f"Modello '{model_path_or_id}' non trovato su disco"}
    if not _dentro_la_cartella(base_dir, origine):
        return {"success": False, "error": "Operazione non consentita al di fuori della cartella modelli"}
    if origine == base_dir:
        return {"success": False, "error": "Non è possibile rinominare la cartella radice dei modelli"}

    grezzo = str(new_name or "").strip()
    if not grezzo:
        return {"success": False, "error": "Il nuovo nome è vuoto"}
    if os.path.isabs(grezzo) or ".." in grezzo or ":" in grezzo:
        return {"success": False, "error": "Il nuovo nome non può essere un percorso"}

    pulito = grezzo.strip("/\\")
    if not pulito:
        return {"success": False, "error": "Il nuovo nome è vuoto"}

    # `autore/modello` -> `autore--modello`: e' la convenzione con cui i modelli
    # scaricati da Hugging Face stanno gia' sul disco.
    cartella = pulito.replace("/", "--").replace("\\", "--")
    if any(c in cartella for c in '<>:"|?*'):
        return {"success": False, "error": "Il nuovo nome contiene caratteri non ammessi"}

    # Se l'origine e' un file singolo (es. .gguf), mantieni l'estensione del file se non specificata
    if os.path.isfile(origine):
        orig_ext = os.path.splitext(origine)[1]
        if orig_ext and not cartella.lower().endswith(orig_ext.lower()):
            cartella = f"{cartella}{orig_ext}"

    destinazione = os.path.abspath(os.path.join(base_dir, cartella))
    if not _dentro_la_cartella(base_dir, destinazione):
        return {"success": False, "error": "Il nuovo nome porterebbe fuori dalla cartella modelli"}
    if destinazione == origine:
        return {"success": True, "renamed": False, "path": origine,
                "message": "Il nome era già questo"}
    if os.path.exists(destinazione):
        return {"success": False,
                "error": f"Esiste già un modello chiamato '{cartella}'"}

    # Un modello residente tiene aperti i suoi file: su Windows la rinomina
    # fallirebbe, su Linux riuscirebbe lasciando il runtime a puntare al nulla.
    try:
        residente = sigma_engine.loaded_model_name or ""
        percorso_residente = (sigma_engine.loaded_model or {}).get("path", "")
        if residente and (os.path.basename(origine).lower() in residente.lower()
                          or (percorso_residente
                              and os.path.abspath(percorso_residente) == origine)):
            log.info("[ModelInventory] Scarico '%s' prima di rinominarlo.", residente)
            sigma_engine.unload()
    except Exception as err:
        log.warning("[ModelInventory] Scaricamento prima della rinomina non riuscito: %s", err)

    try:
        os.rename(origine, destinazione)
    except OSError as err:
        return {"success": False,
                "error": f"Rinomina non riuscita: {err}. "
                         f"Se il modello è in uso, scaricalo dal motore e riprova."}

    # Il repository su Hugging Face segue il modello: senza, una rinomina gli
    # farebbe perdere il collegamento, e la pubblicazione successiva ne creerebbe
    # uno nuovo lasciando due copie senza indicazioni su quale sia quella buona.
    try:
        from core.modules.sigma_model_hub.backend import publications
        publications.rename_local_reference(os.path.basename(origine), cartella)
    except Exception as err:
        log.debug("[ModelInventory] Legame di pubblicazione non aggiornato: %s", err)

    log.info("[ModelInventory] Modello rinominato: %s -> %s",
             os.path.basename(origine), cartella)
    return {
        "success": True,
        "renamed": True,
        "old_name": os.path.basename(origine),
        "new_name": cartella,
        "model_id": pulito if "/" in pulito else cartella.replace("--", "/"),
        "path": destinazione,
    }


def delete_local_model(model_path_or_id: str, custom_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely deletes a downloaded model file or repository folder from disk.
    Prevents directory traversal and ensures safe sandbox boundaries.
    """
    import shutil
    if not model_path_or_id or not str(model_path_or_id).strip():
        return {"success": False, "error": "Identificativo o percorso del modello non valido"}

    base_dir, target_path = _trova_base_e_percorso(model_path_or_id, custom_dir)

    if not target_path or not os.path.exists(target_path):
        return {"success": False, "error": f"Modello '{model_path_or_id}' non trovato su disco"}

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

