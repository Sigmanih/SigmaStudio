# ==============================================================================
# core/modules/sigma_model_hub/backend/hf_client.py
# Dynamic Real-Time Hugging Face Hub Client & Model Explorer for SigmaEngine
# ==============================================================================
from __future__ import annotations
import os
import re
import json
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from core.logger import get_logger

log = get_logger(__name__)

HF_API_BASE = "https://huggingface.co/api"


# Every place the token is read from or written to, in resolution order. The
# Model Hub is the single UI for the token, so a save has to reach all of them:
# a stale copy left behind in one file is a download that silently falls back
# to anonymous rate limits.
HF_TOKEN_ENV_KEYS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")


def _hf_root_dir() -> str:
    """Installation root, anchored to this file rather than the working directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))


def _hf_config_paths() -> List[str]:
    """Config files that can carry `hf_token`, in the order they are resolved."""
    root_dir = _hf_root_dir()
    return [
        os.path.join(root_dir, "data", "model_hub_config.json"),
        os.path.join(root_dir, "core", "data", "model_hub_config.json"),
        os.path.join(root_dir, "config.json"),
        os.path.join(root_dir, "data", "config.json"),
    ]


def resolve_hf_token(explicit_token: Optional[str] = None) -> Dict[str, Any]:
    """Resolves the token and reports where it came from, so the Model Hub can show its origin."""
    if explicit_token and explicit_token.strip():
        return {"token": explicit_token.strip(), "source": "input", "detail": "Token inserito manualmente"}

    # 1. Environment variables
    for env_key in HF_TOKEN_ENV_KEYS:
        val = os.getenv(env_key)
        if val and val.strip():
            return {"token": val.strip(), "source": "env", "detail": "Variabile d'ambiente " + env_key}

    # 2. Sigma config files
    for path in _hf_config_paths():
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            continue
        if not isinstance(cfg, dict):
            continue
        providers = cfg.get("ai_providers") if isinstance(cfg.get("ai_providers"), dict) else {}
        hf_provider = providers.get("huggingface") if isinstance(providers.get("huggingface"), dict) else {}
        tok = (cfg.get("hf_token") or hf_provider.get("token") or "").strip()
        if tok:
            return {"token": tok, "source": "config", "detail": os.path.relpath(path, _hf_root_dir())}

    # 3. Hugging Face CLI cache (`huggingface-cli login`)
    for cache_path in (
        os.path.expanduser("~/.cache/huggingface/token"),
        os.path.expanduser("~/.huggingface/token"),
    ):
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    tok = f.read().strip()
            except Exception:
                continue
            if tok:
                return {"token": tok, "source": "cli_cache", "detail": "Cache huggingface-cli"}

    return {"token": None, "source": None, "detail": None}


def get_effective_hf_token(explicit_token: Optional[str] = None) -> Optional[str]:
    """Resolves the best available Hugging Face API token from explicit arg, env vars, config, or HF CLI cache."""
    return resolve_hf_token(explicit_token)["token"]


def persist_hf_token(token: Optional[str]) -> Dict[str, Any]:
    """
    Single write path for the Hugging Face token.

    Applies it to the process environment, to every Sigma config file that is
    read back on resolution, and to any download already in flight, so the token
    saved from the Model Hub is the one used everywhere without a restart.
    """
    token = (token or "").strip()
    written: List[str] = []

    if token:
        for env_key in HF_TOKEN_ENV_KEYS:
            os.environ[env_key] = token
    else:
        for env_key in HF_TOKEN_ENV_KEYS:
            os.environ.pop(env_key, None)

    root_dir = _hf_root_dir()
    targets = [
        os.path.join(root_dir, "data", "model_hub_config.json"),
        os.path.join(root_dir, "config.json"),
        os.path.join(root_dir, "data", "config.json"),
    ]
    # The legacy copy is only refreshed when it already exists: creating it
    # would add a file that shadows the primary one on the next resolution.
    legacy = os.path.join(root_dir, "core", "data", "model_hub_config.json")
    if os.path.exists(legacy):
        targets.append(legacy)

    for path in targets:
        cfg = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
            except Exception:
                cfg = {}
        cfg["hf_token"] = token
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            written.append(os.path.relpath(path, root_dir))
        except Exception as exc:
            log.warning("persist_hf_token: impossibile scrivere %s: %s", path, exc)

    # Downloads already queued or paused keep their own copy of the token.
    try:
        from .downloader_engine import downloader_manager
        with downloader_manager.lock:
            for task in downloader_manager.tasks.values():
                task.hf_token = token
    except Exception:
        pass

    return {"hf_has_token": bool(token), "written": written}


# Recognized verified official organizations and AI labs
OFFICIAL_ORGANIZATIONS = {
    'qwen', 'meta-llama', 'deepseek-ai', 'mistralai', 'google', 'microsoft',
    'anthropic', 'cohereforai', 'thudm', '01-ai', 'nvidia', 'facebook', 'baai',
    'stabilityai', 'black-forest-labs', 'allenai', 'apple', 'openai', 'tiiuae',
    'bytedance', 'internlm', 'systran', 'bigcode', 'salesforce', 'openchat'
}

OFFICIAL_AUTHOR_MAP = {
    'qwen': 'Qwen',
    'llama': 'meta-llama',
    'meta': 'meta-llama',
    'deepseek': 'deepseek-ai',
    'mistral': 'mistralai',
    'google': 'google',
    'gemma': 'google',
    'microsoft': 'microsoft',
    'phi': 'microsoft',
    'cohere': 'CohereForAI',
    '01-ai': '01-ai',
    'yi': '01-ai',
    'nvidia': 'nvidia',
    'nemotron': 'nvidia',
    'stability': 'stabilityai',
    'black-forest': 'black-forest-labs',
    'flux': 'black-forest-labs',
    'apple': 'apple',
    'internlm': 'internlm',
    'thudm': 'THUDM',
    'glm': 'THUDM'
}


def is_official_provider(author: str, model_id: str) -> bool:
    """Checks if the model author or repository organization is an official AI lab or provider."""
    auth_low = (author or "").lower().strip()
    id_low = (model_id or "").lower().strip()
    org = id_low.split('/')[0] if '/' in id_low else auth_low
    
    if org in OFFICIAL_ORGANIZATIONS:
        return True
    return any(o in org for o in [
        'qwen', 'meta-llama', 'deepseek-ai', 'mistralai', 'google', 'microsoft',
        'cohereforai', 'nvidia', 'baai', 'stabilityai', 'black-forest-labs',
        'allenai', 'apple', 'tiiuae', 'bytedance', 'internlm', 'systran', '01-ai', 'thudm'
    ])


def _format_date_label(iso_date: Optional[str]) -> str:
    """Converts ISO date string (e.g. 2025-02-14T18:22:00.000Z) to human-readable Italian date label."""
    if not iso_date:
        return "Recente"
    try:
        part = iso_date.split('T')[0]
        y, m, d = part.split('-')
        month_names = {
            "01": "Gen", "02": "Feb", "03": "Mar", "04": "Apr", "05": "Mag", "06": "Giu",
            "07": "Lug", "08": "Ago", "09": "Set", "10": "Ott", "11": "Nov", "12": "Dic"
        }
        return f"{int(d)} {month_names.get(m, m)} {y}"
    except Exception:
        return iso_date[:10] if len(iso_date) >= 10 else iso_date


def parse_model_specs(model_id: str, name: str, tags: List[str] = None) -> Dict[str, Any]:
    """
    Accurately extracts:
    - active_params_b (float) & active_params_label (e.g. '27B', '95B')
    - total_params_b (float) & total_params_label (e.g. '27B', '2.4T Totali', '671B Totali')
    - is_moe (bool)
    - precision_label (e.g. 'FP8', 'FP16', 'GGUF Q4_K_M', 'NVFP4')
    - estimated size_gb: TOTAL DISK STORAGE / DOWNLOAD SIZE (based on total_b * precision)
    - estimated active_vram_gb: ACTIVE INFERENCE VRAM FOOTPRINT (based on active_b * precision)
    - size_label (e.g. '~2.4 TB', '~4.8 TB', '~54.0 GB')
    - active_vram_label (e.g. '~95 GB VRAM', '~190 GB VRAM')
    """
    text = f"{model_id} {name} {' '.join(tags or [])}".lower()

    # 1. Parameter extraction (Active vs Total)
    active_b = 7.0
    total_b = 7.0
    active_label = "7B"
    total_label = "7B"
    is_moe = False

    # Check for DeepSeek-V3 / DeepSeek-R1 full 671B MoE
    if ("deepseek-v3" in text or "deepseek-r1" in text or "deepseek_v3" in text or "deepseek_r1" in text) and "distill" not in text and "tiny" not in text and "zero" not in text:
        is_moe = True
        total_b = 671.0
        active_b = 37.0
        active_label = "37B"
        total_label = "671B Totali"
    else:
        # Check for MoE active token patterns like 2.4T-A95B or 35B-A3B or A95B
        moe_a_match = re.search(r'(?:(\d+(?:\.\d+)?)\s*t\s*[-_])?a(\d+(?:\.\d+)?)\s*b', text)
        if moe_a_match:
            is_moe = True
            t_tokens = moe_a_match.group(1)
            active_val = float(moe_a_match.group(2))
            active_b = active_val
            active_label = f"{active_val:g}B"
            if t_tokens:
                total_b = float(t_tokens) * 1000.0  # e.g. 2.4T -> 2400B
                total_label = f"{t_tokens}T Totali"
            else:
                total_b = active_val * 4.0
                total_label = f"{active_val:g}B (MoE)"
        else:
            # Check standard MoE expert patterns like 8x7b, 16x17b, 8x22b
            moe_match = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*b', text)
            if moe_match:
                is_moe = True
                experts = int(moe_match.group(1))
                expert_size = float(moe_match.group(2))
                active_b = round(expert_size * 2, 1)
                total_b = round(experts * expert_size, 1)
                active_label = f"~{active_b:g}B"
                total_label = f"{total_b:g}B ({experts}x{expert_size:g}B)"
            else:
                # Check standard B pattern like 70b, 32b, 27b, 14b, 8b, 7b, 3b, 1.5b, 0.5b
                param_match = re.search(r'(\d+(?:\.\d+)?)\s*b(?:\b|[^a-z0-9])', text)
                if param_match:
                    val = float(param_match.group(1))
                    if 0.1 <= val <= 1000:
                        active_b = val
                        total_b = val
                        active_label = f"{val:g}B"
                        total_label = f"{val:g}B"
                else:
                    m_match = re.search(r'(\d+)\s*m(?:\b|[^a-z0-9])', text)
                    if m_match:
                        val_m = float(m_match.group(1))
                        active_b = round(val_m / 1000, 2)
                        total_b = active_b
                        active_label = f"{int(val_m)}M"
                        total_label = f"{int(val_m)}M"

    # 2. Precision & Size estimation (FP8, FP16, GGUF, NVFP4)
    is_gguf = "gguf" in text
    if "fp8" in text or "int8" in text or "w8a8" in text or "8bit" in text or "8-bit" in text:
        precision = "FP8 (8-bit)"
        fmt_label = "Safetensors (FP8)"
        bytes_per_param = 1.0
    elif "nvfp4" in text or "mxfp4" in text or "int4" in text or "fp4" in text or "awq" in text or "gptq" in text or "4bit" in text:
        precision = "4-bit (NVFP4/AWQ)"
        fmt_label = "Safetensors (4-bit)"
        bytes_per_param = 0.55
    elif is_gguf:
        if "q8" in text:
            precision = "GGUF Q8_0 (8-bit)"
            bytes_per_param = 1.08
        elif "q5" in text:
            precision = "GGUF Q5_K_M (5-bit)"
            bytes_per_param = 0.75
        elif "q2" in text or "q3" in text:
            precision = "GGUF Q3_K_M (3-bit)"
            bytes_per_param = 0.45
        else:
            precision = "GGUF Q4_K_M (4-bit)"
            bytes_per_param = 0.62
        fmt_label = "GGUF"
    else:
        precision = "FP16 / BF16 (16-bit)"
        fmt_label = "Safetensors"
        bytes_per_param = 2.0

    # Total repository storage / download size is based on total_b
    size_gb = round(total_b * bytes_per_param, 1)
    # Active inference VRAM footprint is based on active_b
    active_vram_gb = round(active_b * bytes_per_param, 1)

    if size_gb >= 1000.0:
        size_label = f"~{size_gb / 1000.0:.1f} TB"
    else:
        size_label = f"~{size_gb:g} GB"

    if active_vram_gb >= 1000.0:
        active_vram_label = f"~{active_vram_gb / 1000.0:.1f} TB"
    else:
        active_vram_label = f"~{active_vram_gb:g} GB"

    return {
        "active_b": active_b,
        "total_b": total_b,
        "active_label": active_label,
        "total_label": total_label,
        "is_moe": is_moe,
        "precision": precision,
        "format": fmt_label,
        "size_gb": size_gb,
        "size_label": size_label,
        "active_vram_gb": active_vram_gb,
        "active_vram_label": active_vram_label,
        "bytes_per_param": bytes_per_param
    }


# Weights alone never fill a device: KV cache, activations and the CUDA context
# also live there. A placement is only called a fit with this much slack on top.
_FIT_HEADROOM = 1.15

# The hardware inventory is stable for the lifetime of a machine, but a search
# page asks for it once per result. Cached so a listing costs one probe.
_hardware_snapshot_cache: Optional[Dict[str, Any]] = None
_hardware_snapshot_at: float = 0.0
_HARDWARE_SNAPSHOT_TTL_S = 60.0


def get_local_hardware_snapshot(force: bool = False) -> Dict[str, Any]:
    """
    Capacity of the machine actually running Sigma, as measured by the probe.

    Returns empty lists when nothing can be detected: callers must degrade to a
    hardware-neutral answer rather than describe a machine that may not exist.
    """
    global _hardware_snapshot_cache, _hardware_snapshot_at

    now = time.time()
    if not force and _hardware_snapshot_cache is not None and \
            (now - _hardware_snapshot_at) < _HARDWARE_SNAPSHOT_TTL_S:
        return _hardware_snapshot_cache

    snapshot: Dict[str, Any] = {"gpus": [], "ram_gb": 0.0, "fast_storage": False}
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe

        for acc in UniversalHardwareProbe.probe_accelerators():
            vram = acc.get("total_vram_gb") or acc.get("unified_memory_gb") or 0.0
            if not vram:
                continue
            snapshot["gpus"].append({
                "name": acc.get("name", "GPU"),
                "vram_gb": float(vram),
                "type": acc.get("type", ""),
            })
        snapshot["gpus"].sort(key=lambda g: g["vram_gb"], reverse=True)

        snapshot["ram_gb"] = float(UniversalHardwareProbe.probe_ram().get("total_gb", 0.0))
        snapshot["fast_storage"] = any(
            d.get("is_fast_storage") for d in UniversalHardwareProbe.probe_storage_drives()
        )
    except Exception as ex:
        log.debug("[HF_Client] Hardware snapshot unavailable: %s", ex)

    _hardware_snapshot_cache = snapshot
    _hardware_snapshot_at = now
    return snapshot


def _short_gpu_name(name: str) -> str:
    """Drops vendor boilerplate so a card fits on a badge, without renaming it."""
    cleaned = re.sub(r"\b(NVIDIA|GeForce|AMD|Radeon|Intel\(R\)|Corporation)\b", "", name)
    return re.sub(r"\s+", " ", cleaned).strip() or name


def _determine_target_gpu(
    size_gb: float,
    is_moe: bool = False,
    active_vram_label: str = "",
    active_vram_gb: Optional[float] = None,
) -> str:
    """
    Where this model would actually run, on the hardware this machine has.

    Nothing here is keyed to a particular card. The requirement is compared with
    the VRAM, RAM and storage the probe reports, and when the probe finds
    nothing the answer states the requirement instead of naming hardware.
    """
    # A MoE only holds its active experts in VRAM; the rest can stream.
    required_gb = active_vram_gb if (is_moe and active_vram_gb) else size_gb
    required_gb = max(float(required_gb or 0.0), 0.1)

    hardware = get_local_hardware_snapshot()
    gpus = hardware["gpus"]
    ram_gb = hardware["ram_gb"]

    def _requirement_label() -> str:
        if required_gb >= 1000.0:
            return f"~{required_gb / 1000.0:.1f} TB"
        return f"~{required_gb:g} GB"

    if not gpus:
        if ram_gb and ram_gb >= required_gb * _FIT_HEADROOM:
            return f"CPU + RAM di sistema ({ram_gb:g} GB)"
        if ram_gb:
            return f"CPU + offload su disco ({_requirement_label()} richiesti)"
        return f"{_requirement_label()} richiesti ({active_vram_label or 'pesi'})"

    needed = required_gb * _FIT_HEADROOM
    largest = gpus[0]
    total_vram = sum(g["vram_gb"] for g in gpus)

    if largest["vram_gb"] >= needed:
        return f"{_short_gpu_name(largest['name'])} ({largest['vram_gb']:g} GB) • VRAM completa"

    if len(gpus) > 1 and total_vram >= needed:
        return f"Multi-GPU {len(gpus)}× ({total_vram:g} GB VRAM totali) • sharded"

    if total_vram + ram_gb >= needed:
        return f"{_short_gpu_name(largest['name'])} + RAM ({ram_gb:g} GB) • offload parziale"

    if hardware["fast_storage"]:
        return f"Offload su disco ({_requirement_label()}) • streaming NVMe/SSD"

    return f"Oltre le risorse locali ({_requirement_label()} richiesti)"



def _matches_size_bracket(size_gb: float, bracket: str) -> bool:
    if not bracket or bracket == "all":
        return True
    if bracket == "under_4gb":
        return size_gb < 4.0
    if bracket == "4_8gb":
        return 4.0 <= size_gb <= 8.0
    if bracket == "8_16gb":
        return 8.0 < size_gb <= 16.0
    if bracket == "16_32gb":
        return 16.0 < size_gb <= 32.0
    if bracket == "32_48gb":
        return 32.0 < size_gb <= 48.0
    if bracket == "48_70gb":
        return 48.0 < size_gb <= 70.0
    if bracket == "70_140gb":
        return 70.0 < size_gb <= 140.0
    if bracket == "over_140gb":
        return size_gb > 140.0
    if bracket == "over_32gb":
        return size_gb > 32.0
    return True


def _matches_param_bracket(params_b: float, bracket: str) -> bool:
    if not bracket or bracket == "all":
        return True
    if bracket == "under_3b":
        return params_b < 4.0
    if bracket == "7b_8b":
        return 6.0 <= params_b <= 9.0
    if bracket == "12b_14b":
        return 10.0 <= params_b <= 16.0
    if bracket == "27b_34b":
        return 20.0 <= params_b <= 40.0
    if bracket == "70b_plus":
        return params_b >= 60.0
    return True


# Curated Popular Official & Featured Models with direct HF links
POPULAR_MODELS = [
    {
        "id": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "name": "Qwen 2.5 Coder 14B Instruct",
        "author": "Qwen",
        "category": "code",
        "params_b": 14.0,
        "params_label": "14B",
        "active_params_label": "14B",
        "total_params_label": "14B",
        "precision": "FP16 (16-bit)",
        "size_gb": 28.0,
        "format": "Safetensors",
        "downloads": 240000,
        "likes": 3800,
        "is_official": True,
        "created_at": "2024-11-12T09:30:00Z",
        "last_modified": "2024-11-14T11:00:00Z",
        "release_date_label": "12 Nov 2024",
        "description": "Modello ufficiale Alibaba Qwen per la generazione, analisi e refactoring di codice.",
        "quantizations": ["Safetensors (FP16 28 GB)", "GGUF Q4_K_M (8.9 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct",
    },
    {
        "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "name": "DeepSeek R1 Distill Qwen 14B",
        "author": "deepseek-ai",
        "category": "reasoning",
        "params_b": 14.0,
        "params_label": "14B",
        "active_params_label": "14B",
        "total_params_label": "14B",
        "precision": "FP16 (16-bit)",
        "size_gb": 28.0,
        "format": "Safetensors",
        "downloads": 410000,
        "likes": 5900,
        "is_official": True,
        "created_at": "2025-01-20T08:00:00Z",
        "last_modified": "2025-01-22T12:00:00Z",
        "release_date_label": "20 Gen 2025",
        "description": "Modello di ragionamento ufficiale rilasciato da DeepSeek AI basato su Qwen 14B.",
        "quantizations": ["Safetensors FP16 (28 GB)", "GGUF Q4_K_M (8.9 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    },
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct",
        "name": "Meta Llama 3.1 8B Instruct",
        "author": "meta-llama",
        "category": "llm",
        "params_b": 8.0,
        "params_label": "8B",
        "active_params_label": "8B",
        "total_params_label": "8B",
        "precision": "FP16 (16-bit)",
        "size_gb": 16.0,
        "format": "Safetensors",
        "downloads": 820000,
        "likes": 8400,
        "is_official": True,
        "created_at": "2024-07-23T12:00:00Z",
        "last_modified": "2024-08-01T10:00:00Z",
        "release_date_label": "23 Lug 2024",
        "description": "Modello ufficiale di Meta con 128k context window e alte capacità conversazionali.",
        "quantizations": ["Safetensors (16 GB)", "GGUF Q4_K_M (4.9 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
    },
    {
        "id": "meta-llama/Llama-3.3-70B-Instruct",
        "name": "Meta Llama 3.3 70B Instruct",
        "author": "meta-llama",
        "category": "moe",
        "params_b": 70.0,
        "params_label": "70B",
        "active_params_label": "70B",
        "total_params_label": "70B",
        "precision": "FP16 (16-bit)",
        "size_gb": 140.0,
        "format": "Safetensors",
        "downloads": 310000,
        "likes": 4700,
        "is_official": True,
        "created_at": "2024-12-06T15:00:00Z",
        "last_modified": "2024-12-08T18:00:00Z",
        "release_date_label": "6 Dic 2024",
        "description": "Modello ammiraglia da 70 miliardi di parametri ufficiale rilasciato da Meta.",
        "quantizations": ["Safetensors (140 GB)", "GGUF Q4_K_M (42 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct",
    },
    {
        "id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
        "name": "DeepSeek R1 Distill Qwen 14B (GGUF)",
        "author": "bartowski",
        "category": "reasoning",
        "params_b": 14.0,
        "params_label": "14B",
        "active_params_label": "14B",
        "total_params_label": "14B",
        "precision": "GGUF Q4_K_M (4-bit)",
        "size_gb": 8.9,
        "format": "GGUF",
        "downloads": 128000,
        "likes": 2400,
        "is_official": False,
        "created_at": "2025-01-22T08:00:00Z",
        "last_modified": "2025-01-24T12:30:00Z",
        "release_date_label": "22 Gen 2025",
        "description": "Quantizzazione GGUF ad alta efficienza per DeepSeek R1 14B.",
        "quantizations": ["Q4_K_M (8.9 GB)", "Q5_K_M (10.5 GB)", "Q8_0 (15.2 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf",
        "hf_url": "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
    },
    {
        "id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "Qwen 2.5 7B Instruct",
        "author": "Qwen",
        "category": "llm",
        "params_b": 7.0,
        "params_label": "7B",
        "active_params_label": "7B",
        "total_params_label": "7B",
        "precision": "FP16 (16-bit)",
        "size_gb": 14.0,
        "format": "Safetensors",
        "downloads": 520000,
        "likes": 6100,
        "is_official": True,
        "created_at": "2024-09-18T10:00:00Z",
        "last_modified": "2024-09-20T12:00:00Z",
        "release_date_label": "18 Set 2024",
        "description": "Modello ufficiale Qwen 2.5 7B ad altissime prestazioni per general LLM e chat.",
        "quantizations": ["Safetensors (14 GB)", "GGUF Q4_K_M (4.6 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
    }
]


def _fetch_from_hf_api(params: Dict[str, Any], hf_token: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Helper to query Hugging Face API and extract items and next_cursor."""
    url = f"{HF_API_BASE}/models?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
    if hf_token:
        req.add_header("Authorization", f"Bearer {hf_token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw = json.loads(response.read().decode("utf-8"))
                link = response.headers.get("Link", "")
                next_cursor = None
                if 'rel="next"' in link:
                    match = re.search(r'[?&]cursor=([^&>]+)', link)
                    if match:
                        next_cursor = urllib.parse.unquote(match.group(1))
                return raw, next_cursor
    except Exception as ex:
        log.debug(f"[HF_Client] HF API fetch error for {params}: {ex}")
    return [], None


def search_hf_models(
    query: str = "",
    category: str = "all",
    size_bracket: str = "all",
    param_bracket: str = "all",
    format_filter: str = "all",
    sort: str = "downloads",
    official_only: bool = False,
    cursor: Optional[str] = None,
    page: int = 1,
    limit: int = 30,
    hf_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Searches models on Hugging Face API dynamically in real time.
    Supports official_only filter, granular size brackets, active/total parameters and precision-aware sizing.
    """
    results = []

    cat_tag_map = {
        "vision": "image-text-to-text",
        "audio": "automatic-speech-recognition",
    }

    # 1. Match from POPULAR_MODELS catalogue first (only on page 1 / initial load without cursor)
    if not cursor and page == 1:
        q_low = query.lower().strip()
        for m in POPULAR_MODELS:
            if official_only and not m.get("is_official", False):
                continue
            if q_low:
                if q_low not in m["id"].lower() and q_low not in m["name"].lower() and q_low not in m["description"].lower():
                    continue
            if category != "all" and category != m.get("category"):
                continue
            if not _matches_size_bracket(m.get("size_gb", 5.0), size_bracket):
                continue
            if not _matches_param_bracket(m.get("params_b", 7.0), param_bracket):
                continue
            if format_filter != "all" and format_filter.lower() not in m.get("format", "").lower():
                continue
            # Computed here rather than stored with the entry: the catalogue is
            # shared, the machine reading it is not.
            results.append({
                **m,
                "recommended_gpu": _determine_target_gpu(
                    m.get("size_gb", 0.0), m.get("is_moe", False),
                    m.get("active_vram_label", ""), m.get("active_vram_gb"),
                ),
            })

    # 2. Dynamic Multi-Pass Live Fetch directly from Hugging Face Hub API
    next_cursor = None
    try:
        search_query = query.strip()
        hf_sort = sort
        if sort in ["size_asc", "size_desc"]:
            hf_sort = "downloads"
        elif sort in ["newest", "lastModified"]:
            hf_sort = "lastModified"

        raw_items: List[Dict[str, Any]] = []

        # A. If searching official models or query matches an official provider keyword, fetch from official author endpoint first!
        detected_author = None
        q_lower = search_query.lower()
        for key_kw, author_name in OFFICIAL_AUTHOR_MAP.items():
            if key_kw in q_lower:
                detected_author = author_name
                break

        if not cursor and (official_only or detected_author):
            target_authors = [detected_author] if detected_author else ["Qwen", "meta-llama", "deepseek-ai", "mistralai"]
            for auth in target_authors:
                if not auth:
                    continue
                auth_clean_q = re.sub(auth, '', search_query, flags=re.IGNORECASE).strip()
                auth_clean_q = re.sub(r'(qwen|llama|deepseek|mistral)', '', auth_clean_q, flags=re.IGNORECASE).strip()
                auth_params = {
                    "author": auth,
                    "limit": 30,
                    "full": "true"
                }
                if auth_clean_q:
                    auth_params["search"] = auth_clean_q
                if hf_sort:
                    auth_params["sort"] = hf_sort
                    auth_params["direction"] = -1

                auth_raw, _ = _fetch_from_hf_api(auth_params, hf_token=hf_token)
                for item in auth_raw:
                    if not any(x.get("id") == item.get("id") for x in raw_items):
                        raw_items.append(item)

        # B. Standard global search query
        effective_search = search_query
        if not effective_search:
            effective_search = "qwen" if official_only else "gguf"

        fetch_limit = min(limit * 3, 90)
        params = {
            "search": effective_search,
            "sort": hf_sort,
            "direction": -1,
            "limit": fetch_limit,
            "full": "true"
        }
        if category in cat_tag_map:
            params["pipeline_tag"] = cat_tag_map[category]
        if cursor:
            params["cursor"] = cursor

        global_raw, next_cursor = _fetch_from_hf_api(params, hf_token=hf_token)
        for item in global_raw:
            if not any(x.get("id") == item.get("id") for x in raw_items):
                raw_items.append(item)

        # C. Transform and filter raw items with precision & active/total specs
        for item in raw_items:
            mid = item.get("id") or item.get("modelId", "")
            if any(r["id"] == mid for r in results):
                continue

            author = mid.split("/")[0] if "/" in mid else "HuggingFace"
            is_official = is_official_provider(author, mid)

            # If official_only is enabled, skip community repackages
            if official_only and not is_official:
                continue

            m_name = mid.split("/")[-1] if "/" in mid else mid
            pipeline = item.get("pipeline_tag", "text-generation")
            tags = item.get("tags", [])

            # Parse release date and last modified
            created_at = item.get("createdAt")
            last_modified = item.get("lastModified")
            release_date = created_at or last_modified
            date_label = _format_date_label(release_date)

            # Parse precision, active/total parameters and realistic size in GB
            specs = parse_model_specs(mid, m_name, tags)
            params_b = specs["active_b"]
            total_b = specs["total_b"]
            params_label = specs["active_label"]
            total_params_label = specs["total_label"]
            precision = specs["precision"]
            fmt_label = specs["format"]
            size_gb = specs["size_gb"]
            size_label = specs["size_label"]
            active_vram_gb = specs["active_vram_gb"]
            active_vram_label = specs["active_vram_label"]
            rec_gpu = _determine_target_gpu(size_gb, specs["is_moe"], active_vram_label, active_vram_gb)

            # Apply filters
            if not _matches_size_bracket(size_gb, size_bracket):
                continue
            if not _matches_param_bracket(params_b, param_bracket):
                continue
            if format_filter != "all" and format_filter.lower() not in fmt_label.lower():
                continue

            inferred_cat = category if category != "all" else (
                "code" if "code" in mid.lower() or "coder" in mid.lower() else (
                    "vision" if "vl" in mid.lower() or "vision" in mid.lower() else (
                        "reasoning" if "r1" in mid.lower() or "reason" in mid.lower() else (
                            "moe" if specs["is_moe"] or "moe" in mid.lower() or "x" in mid.lower() else "llm"
                        )
                    )
                )
            )

            desc_text = (
                f"Modello MoE {m_name} ({precision} • {params_label} attivi per token / {total_params_label}). Storage: {size_label}, VRAM attiva: {active_vram_label}."
                if specs["is_moe"]
                else f"Modello {m_name} ({precision} • {params_label} • {size_label}) di {author}."
            )

            results.append({
                "id": mid,
                "name": m_name,
                "author": author,
                "category": inferred_cat,
                "params_b": params_b,
                "total_b": total_b,
                "params_label": params_label,
                "active_params_label": params_label,
                "total_params_label": total_params_label,
                "is_moe": specs["is_moe"],
                "precision": precision,
                "size_gb": size_gb,
                "size_label": size_label,
                "active_vram_gb": active_vram_gb,
                "active_vram_label": active_vram_label,
                "format": fmt_label,
                "downloads": item.get("downloads", 0),
                "likes": item.get("likes", 0),
                "is_official": is_official,
                "created_at": created_at,
                "last_modified": last_modified,
                "release_date_label": date_label,
                "description": desc_text,
                "quantizations": ["GGUF Q4_K_M", "Q8_0", "FP16"] if "GGUF" in fmt_label else [f"{precision} ({size_label})"],
                "pipeline_tag": pipeline,
                "default_file": f"{m_name}.gguf" if "GGUF" in fmt_label else f"{m_name}.safetensors",
                "hf_url": f"https://huggingface.co/{mid}",
                "recommended_gpu": rec_gpu
            })

    except Exception as ex:
        log.debug(f"[HF_Client] Dynamic online search error: {ex}")

    # 3. Apply custom sorting
    if sort == "likes":
        results.sort(key=lambda x: x.get("likes", 0), reverse=True)
    elif sort == "downloads":
        results.sort(key=lambda x: x.get("downloads", 0), reverse=True)
    elif sort in ["newest", "lastModified"]:
        results.sort(key=lambda x: x.get("created_at") or x.get("last_modified") or "", reverse=True)
    elif sort == "size_asc":
        results.sort(key=lambda x: x.get("size_gb", 0.0))
    elif sort == "size_desc":
        results.sort(key=lambda x: x.get("size_gb", 0.0), reverse=True)

    return {
        "results": results,
        "total": len(results),
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor) or len(results) >= limit
    }


def get_hf_model_details(model_id: str, hf_token: Optional[str] = None) -> Dict[str, Any]:
    """Fetches detailed metadata, file list, dates, and available quantizations for a model."""
    try:
        url = f"{HF_API_BASE}/models/{model_id}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
        if hf_token:
            req.add_header("Authorization", f"Bearer {hf_token}")

        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                siblings = data.get("siblings", [])
                
                files = []
                for s in siblings:
                    rfilename = s.get("rfilename", "")
                    if any(rfilename.endswith(ext) for ext in [".gguf", ".safetensors", ".bin", ".json", ".pt"]):
                        files.append({
                            "filename": rfilename,
                            "is_gguf": rfilename.endswith(".gguf"),
                            "is_safetensors": rfilename.endswith(".safetensors"),
                            "download_url": f"https://huggingface.co/{model_id}/resolve/main/{rfilename}"
                        })

                created_at = data.get("createdAt")
                last_modified = data.get("lastModified")
                release_date_label = _format_date_label(created_at or last_modified)

                specs = parse_model_specs(model_id, data.get("id", ""), data.get("tags", []))
                author = data.get("author", model_id.split("/")[0] if "/" in model_id else "Community")

                return {
                    "success": True,
                    "id": model_id,
                    "author": author,
                    "is_official": is_official_provider(author, model_id),
                    "downloads": data.get("downloads", 0),
                    "likes": data.get("likes", 0),
                    "created_at": created_at,
                    "last_modified": last_modified,
                    "release_date_label": release_date_label,
                    "params_label": specs["active_label"],
                    "active_params_label": specs["active_label"],
                    "total_params_label": specs["total_label"],
                    "precision": specs["precision"],
                    "is_moe": specs["is_moe"],
                    "size_gb": specs["size_gb"],
                    "size_label": specs["size_label"],
                    "active_vram_gb": specs["active_vram_gb"],
                    "active_vram_label": specs["active_vram_label"],
                    "recommended_gpu": _determine_target_gpu(
                        specs["size_gb"], specs["is_moe"],
                        specs["active_vram_label"], specs["active_vram_gb"]),
                    "pipeline_tag": data.get("pipeline_tag", "text-generation"),
                    "tags": data.get("tags", []),
                    "files": files,
                    "card_url": f"https://huggingface.co/{model_id}",
                    "hf_url": f"https://huggingface.co/{model_id}"
                }
    except Exception as ex:
        log.error(f"[HF_Client] get_hf_model_details error for {model_id}: {ex}")

    # Fallback representation
    specs = parse_model_specs(model_id, model_id)
    author = model_id.split("/")[0] if "/" in model_id else "Community"
    return {
        "success": True,
        "id": model_id,
        "author": author,
        "is_official": is_official_provider(author, model_id),
        "downloads": 0,
        "likes": 0,
        "created_at": None,
        "last_modified": None,
        "release_date_label": "N/D",
        "params_label": specs["active_label"],
        "active_params_label": specs["active_label"],
        "total_params_label": specs["total_label"],
        "precision": specs["precision"],
        "is_moe": specs["is_moe"],
        "size_gb": specs["size_gb"],
        "size_label": specs["size_label"],
        "active_vram_gb": specs["active_vram_gb"],
        "active_vram_label": specs["active_vram_label"],
        "recommended_gpu": _determine_target_gpu(
                        specs["size_gb"], specs["is_moe"],
                        specs["active_vram_label"], specs["active_vram_gb"]),
        "pipeline_tag": "text-generation",
        "tags": [],
        "files": [{
            "filename": f"{model_id.split('/')[-1]}.safetensors",
            "is_gguf": False,
            "is_safetensors": True,
            "download_url": f"https://huggingface.co/{model_id}/resolve/main/model.safetensors"
        }],
        "card_url": f"https://huggingface.co/{model_id}",
        "hf_url": f"https://huggingface.co/{model_id}"
    }

