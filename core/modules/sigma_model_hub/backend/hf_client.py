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
from core.net_utils import safe_urlopen
from core.logger import get_logger

log = get_logger(__name__)

HF_API_BASE = "https://huggingface.co/api"


# Every place the token is read from or written to, in resolution order. The
# Model Hub is the single UI for the token, so a save has to reach all of them:
# a stale copy left behind in one file is a download that silently falls back
# to anonymous rate limits.
HF_TOKEN_ENV_KEYS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")


def _hf_root_dir() -> str:
    """Installation root, resolved by the kernel path service."""
    from core.paths import project_root
    return str(project_root())


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


# Recognized verified official organizations, AI labs and premier open-weight providers
OFFICIAL_ORGANIZATIONS = {
    # SigmaStudio Ecosystem & User
    'sigmanih', 'sigma', 'sigmastudio',

    # Frontier Open-Weight Labs & Creators
    'qwen', 'meta-llama', 'deepseek-ai', 'mistralai', 'google', 'microsoft',
    'anthropic', 'cohereforai', 'thudm', 'zhipuai', 'zai-org', 'zai', 'zhipu', '01-ai', 'nvidia', 'facebook', 'baai',
    'stabilityai', 'black-forest-labs', 'allenai', 'apple', 'openai', 'tiiuae',
    'bytedance', 'internlm', 'shanghai-ai-lab', 'systran', 'bigcode', 'salesforce',
    'openchat', 'nousresearch', 'upstage', 'snowflake', 'kyutai', 'liquid-ai',
    'ai21labs', 'minimax', 'kwai', 'kwaivgi', 'deci', 'nexusflow', 'writer',
    'huggingfacetb',

    # Premier GGUF & Quantization Providers
    'bartowski', 'mradermacher', 'thebloke', 'unsloth', 'turboderp',
    'casperhansen', 'mlx-community', 'ggml-org', 'city96', 'undi95',
    'solidrust', 'second-state', 'lone-striker', 'oobabooga'
}

PROVIDER_AUTHOR_MAP = {
    'sigmanih': ['sigmanih'],
    'thudm': ['THUDM', 'ZhipuAI', 'zai-org', 'zai'],
    'zai': ['zai-org', 'zai', 'THUDM', 'ZhipuAI'],
    'glm': ['zai-org', 'THUDM', 'ZhipuAI'],
    'qwen': ['Qwen'],
    'deepseek': ['deepseek-ai'],
    'llama': ['meta-llama'],
    'mistral': ['mistralai'],
    'gemma': ['google'],
    'microsoft': ['microsoft'],
    'bartowski': ['bartowski'],
    'unsloth': ['unsloth'],
    'thebloke': ['TheBloke'],
    'mradermacher': ['mradermacher'],
    'nous': ['NousResearch'],
    'nvidia': ['nvidia'],
    'cohere': ['CohereForAI'],
    '01-ai': ['01-ai'],
    'apple': ['apple'],
    'stability': ['stabilityai'],
    'allenai': ['allenai'],
}

OFFICIAL_AUTHOR_MAP = {
    # Sigma Ecosystem
    'sigmanih': 'sigmanih',
    'sigma': 'sigmanih',

    # GLM & THUDM & ZAI (Zhipu AI)
    'zai-org': 'zai-org',
    'zai': 'zai-org',
    'thudm': 'THUDM',
    'glm': 'zai-org',
    'zhipu': 'zai-org',
    'chatglm': 'THUDM',
    'cogvideo': 'THUDM',
    'cogview': 'THUDM',

    # Major Frontier Labs
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
    'allenai': 'allenai',
    'olmo': 'allenai',
    'baai': 'BAAI',
    'tiiuae': 'tiiuae',
    'falcon': 'tiiuae',
    'nous': 'NousResearch',
    'snowflake': 'Snowflake',
    'smollm': 'HuggingFaceTB',
    'starcoder': 'bigcode',

    # Famous Quantization & GGUF Creators
    'bartowski': 'bartowski',
    'mradermacher': 'mradermacher',
    'unsloth': 'unsloth',
    'thebloke': 'TheBloke',
    'casperhansen': 'casperhansen',
    'city96': 'city96',
    'turboderp': 'turboderp',
    'mlx': 'mlx-community',
}


def is_official_provider(author: str, model_id: str, custom_officials: Optional[List[str]] = None) -> bool:
    """Checks if the model author or repository organization is an official AI lab, verified creator or premier provider."""
    auth_low = (author or "").lower().strip()
    id_low = (model_id or "").lower().strip()
    org = id_low.split('/')[0] if '/' in id_low else auth_low

    if custom_officials:
        custom_set = {str(o).lower().strip() for o in custom_officials if o}
        if org in custom_set or auth_low in custom_set:
            return True

    return org in OFFICIAL_ORGANIZATIONS or auth_low in OFFICIAL_ORGANIZATIONS


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


def parse_model_specs(model_id: str, name: str, tags: List[str] = None, raw_item: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Accurately extracts:
    - active_params_b (float) & active_params_label (e.g. '27B', '95B')
    - total_params_b (float) & total_params_label (e.g. '27B', '2.4T Totali', '671B Totali')
    - is_moe (bool)
    - precision_label (e.g. 'FP8', 'FP16', 'GGUF Q4_K_S', 'GGUF Q4_K_M', 'NVFP4')
    - realistic size_gb: ACTUAL DISK STORAGE / DOWNLOAD SIZE (from usedStorage or accurate precision formula)
    - realistic active_vram_gb: ACTIVE INFERENCE VRAM FOOTPRINT (based on active_b * precision)
    - size_label (e.g. '~2.4 TB', '~4.8 TB', '~14.7 GB', '~54.0 GB')
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
                # Check standard B pattern like 70b, 32b, 27b, 14b, 8b, 7b, 3.8b, 3b, 1.5b, 0.5b
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

    # Check if assistant / draft / speculative model
    is_draft = any(k in text for k in ("-assistant", "_assistant", "/assistant", "-draft", "_draft", "speculative"))
    if is_draft:
        active_b = 0.5
        total_b = 0.5
        active_label = "~0.5B (Draft)"
        total_label = "~0.5B (Draft Assistant)"

    # Refine with exact parameter count from Hugging Face metadata if available
    if raw_item:
        if isinstance(raw_item.get("gguf"), dict) and raw_item["gguf"].get("total"):
            exact_params = round(raw_item["gguf"]["total"] / 1e9, 2)
            if exact_params > 0 and not is_moe:
                active_b = exact_params
                total_b = exact_params
                active_label = f"{exact_params:g}B" if exact_params < 100 else f"{int(exact_params)}B"
                total_label = active_label
        elif isinstance(raw_item.get("safetensors"), dict) and raw_item["safetensors"].get("total"):
            exact_params = round(raw_item["safetensors"]["total"] / 1e9, 2)
            if exact_params > 0 and not is_moe:
                active_b = exact_params
                total_b = exact_params
                active_label = f"{exact_params:g}B" if exact_params < 100 else f"{int(exact_params)}B"
                total_label = active_label

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
        fmt_label = "GGUF"
        if "q8_0" in text or "q8_k" in text or "q8" in text:
            precision = "GGUF Q8_0 (8-bit)"
            bytes_per_param = 1.05
        elif "q6_k" in text or "q6" in text:
            precision = "GGUF Q6_K (6-bit)"
            bytes_per_param = 0.82
        elif "q5_k_m" in text or "q5_m" in text:
            precision = "GGUF Q5_K_M (5-bit)"
            bytes_per_param = 0.70
        elif "q5_k_s" in text or "q5_s" in text or "q5_0" in text or "q5" in text:
            precision = "GGUF Q5_K_S (5-bit)"
            bytes_per_param = 0.66
        elif "q4_k_s" in text or "q4_s" in text:
            precision = "GGUF Q4_K_S (4-bit)"
            bytes_per_param = 0.54
        elif "q4_0" in text:
            precision = "GGUF Q4_0 (4-bit)"
            bytes_per_param = 0.52
        elif "iq4_xs" in text or "iq4_nl" in text or "iq4" in text:
            precision = "GGUF IQ4_XS (4-bit)"
            bytes_per_param = 0.49
        elif "q4_k_m" in text or "q4_m" in text:
            precision = "GGUF Q4_K_M (4-bit)"
            bytes_per_param = 0.58
        elif "q3_k_l" in text or "q3_k_m" in text or "iq3_m" in text:
            precision = "GGUF Q3_K_M (3-bit)"
            bytes_per_param = 0.45
        elif "q3_k_s" in text or "q3_s" in text or "iq3_xs" in text or "iq3_xxs" in text:
            precision = "GGUF Q3_K_S (3-bit)"
            bytes_per_param = 0.40
        elif "q2_k" in text or "iq2_m" in text or "iq2_xs" in text or "iq2_xxs" in text or "q2" in text:
            precision = "GGUF Q2_K (2-bit)"
            bytes_per_param = 0.30
        elif "f16" in text or "fp16" in text or "bf16" in text:
            precision = "GGUF F16 (16-bit)"
            bytes_per_param = 2.0
        else:
            precision = "GGUF Q4_K_M (4-bit)"
            bytes_per_param = 0.58
    else:
        precision = "FP16 / BF16 (16-bit)"
        fmt_label = "Safetensors"
        bytes_per_param = 2.0

    # Total repository storage / download size
    # Check if exact usedStorage is available from Hugging Face
    used_storage_bytes = raw_item.get("usedStorage") if raw_item else None
    if used_storage_bytes and isinstance(used_storage_bytes, (int, float)) and used_storage_bytes > 0:
        if not is_gguf:
            # Safetensors / FP16 / BF16 repos: usedStorage = real download size
            size_gb = round(used_storage_bytes / (1024**3), 1)
        else:
            # GGUF repo: check if it has multiple GGUF variants (usedStorage would be sum of all)
            siblings = raw_item.get("siblings") or []
            gguf_files = [s for s in siblings if s.get("rfilename", "").lower().endswith(".gguf")]
            if len(gguf_files) <= 1:
                size_gb = round(used_storage_bytes / (1024**3), 1)
            else:
                # Multiple GGUF variants: usedStorage is sum of all; use formula for one variant
                size_gb = round(total_b * bytes_per_param, 1)
    else:
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


def _matches_quant_filter(quant_filter: str, text_corpus: str, specs: Optional[Dict[str, Any]] = None) -> bool:
    """Matches a model against the requested quantization filter."""
    if not quant_filter or quant_filter == "all":
        return True
    q = quant_filter.lower().strip()
    extra = ""
    if specs:
        extra = f"{specs.get('precision', '')} {specs.get('format', '')}"
    text = f"{text_corpus} {extra}".lower().replace("-", "_")

    if q == "q4_k_m":
        return "q4_k_m" in text or "q4km" in text or ("q4" in text and "gguf" in text and "q4_k_s" not in text and "q4_0" not in text)
    elif q == "q5_k_m":
        return "q5_k_m" in text or "q5km" in text or "q5_k_s" in text or ("q5" in text and "gguf" in text)
    elif q == "q8_0":
        return "q8_0" in text or "q8_k" in text or "q80" in text or ("q8" in text and "gguf" in text) or ("8bit" in text and "gguf" in text)
    elif q == "q4_k_s":
        return "q4_k_s" in text or "q4ks" in text or "q4_0" in text or "q4_1" in text
    elif q == "q6_k":
        return "q6_k" in text or "q6k" in text or ("q6" in text and "gguf" in text)
    elif q == "q3_k_m":
        return "q3_k_m" in text or "q3km" in text or "q3_k_l" in text or "q3_k_s" in text or ("q3" in text and "gguf" in text)
    elif q == "q2_k":
        return "q2_k" in text or "q2k" in text or ("q2" in text and "gguf" in text)
    elif q == "imatrix":
        return "iq4" in text or "iq3" in text or "iq2" in text or "iq1" in text or "imatrix" in text
    elif q == "fp8":
        return "fp8" in text or "w8a8" in text or ("int8" in text and "safetensors" in text) or ("8bit" in text and "safetensors" in text)
    elif q == "nvfp4":
        return "nvfp4" in text or "mxfp4" in text or "fp4" in text
    elif q == "awq_gptq":
        return "awq" in text or "gptq" in text or "exl2" in text or ("int4" in text and "safetensors" in text)
    elif q == "fp16_bf16":
        return "fp16" in text or "bf16" in text or "bfloat16" in text or "float16" in text or "16bit" in text or ("safetensors" in text and "fp8" not in text and "4bit" not in text and "awq" not in text)
    return q in text


# Curated Popular Official & Featured Models with direct HF links
POPULAR_MODELS = [
    {
        "id": "zai-org/GLM-5.3-Flash",
        "name": "GLM 5.3 Flash",
        "author": "zai-org",
        "category": "llm",
        "params_b": 9.0,
        "params_label": "Flash",
        "active_params_label": "Flash",
        "total_params_label": "Flash",
        "precision": "FP16 / BF16",
        "size_gb": 18.0,
        "format": "Safetensors",
        "downloads": 350000,
        "likes": 4800,
        "is_official": True,
        "created_at": "2025-02-15T10:00:00Z",
        "last_modified": "2025-02-20T12:00:00Z",
        "release_date_label": "15 Feb 2025",
        "description": "Modello ufficiale ad altissima velocità, reasoning avanzato e architettura multimodale di ZAI (Zhipu AI).",
        "quantizations": ["Safetensors (18 GB)", "GGUF Q4_K_M (5.5 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/zai-org/GLM-5.3-Flash",
    },
    {
        "id": "THUDM/glm-4-9b-chat",
        "name": "GLM 4 9B Chat",
        "author": "THUDM",
        "category": "llm",
        "params_b": 9.0,
        "params_label": "9B",
        "active_params_label": "9B",
        "total_params_label": "9B",
        "precision": "FP16 (16-bit)",
        "size_gb": 18.0,
        "format": "Safetensors",
        "downloads": 480000,
        "likes": 5600,
        "is_official": True,
        "created_at": "2024-06-05T10:00:00Z",
        "last_modified": "2024-06-10T12:00:00Z",
        "release_date_label": "5 Giu 2024",
        "description": "Modello conversazionale bilingue ufficiale di Zhipu AI / THUDM con 128k context window.",
        "quantizations": ["Safetensors (18 GB)", "GGUF Q4_K_M (5.5 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "model.safetensors",
        "hf_url": "https://huggingface.co/THUDM/glm-4-9b-chat",
    },
    {
        "id": "bartowski/glm-4-9b-chat-GGUF",
        "name": "GLM 4 9B Chat (GGUF)",
        "author": "bartowski",
        "category": "llm",
        "params_b": 9.0,
        "params_label": "9B",
        "active_params_label": "9B",
        "total_params_label": "9B",
        "precision": "GGUF Q4_K_M (4-bit)",
        "size_gb": 5.5,
        "format": "GGUF",
        "downloads": 95000,
        "likes": 1800,
        "is_official": True,
        "created_at": "2024-06-06T12:00:00Z",
        "last_modified": "2024-06-08T14:00:00Z",
        "release_date_label": "6 Giu 2024",
        "description": "Quantizzazione GGUF ad altissima efficienza per THUDM GLM-4 9B Chat per inferenza locale rapida.",
        "quantizations": ["Q4_K_M (5.5 GB)", "Q5_K_M (6.4 GB)", "Q8_0 (9.5 GB)"],
        "pipeline_tag": "text-generation",
        "default_file": "glm-4-9b-chat-Q4_K_M.gguf",
        "hf_url": "https://huggingface.co/bartowski/glm-4-9b-chat-GGUF",
    },
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
        "is_official": True,
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
    # expand[]=usedStorage asks HF to include the real on-disk repo size in
    # every result — without it parse_model_specs can only guess from the
    # parameter count, which is often wrong for multi-shard safetensors repos.
    base_qs = urllib.parse.urlencode(params)
    url = f"{HF_API_BASE}/models?{base_qs}&expand[]=usedStorage&expand[]=siblings"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
    if hf_token:
        req.add_header("Authorization", f"Bearer {hf_token}")

    try:
        with safe_urlopen(req, timeout=10) as response:
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
    quant_filter: str = "all",
    sort: str = "downloads",
    official_only: bool = False,
    provider: str = "all",
    cursor: Optional[str] = None,
    page: int = 1,
    limit: int = 30,
    hf_token: Optional[str] = None,
    custom_officials: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Searches models on Hugging Face API dynamically in real time.
    Supports provider-specific author scoping, official_only filter, granular size brackets, active/total parameters, precision and quantization-aware filtering.
    """
    results = []

    cat_tag_map = {
        "vision": "image-text-to-text",
        "audio": "automatic-speech-recognition",
    }

    target_provider_authors = [a.lower() for a in PROVIDER_AUTHOR_MAP.get(provider.lower(), [provider])] if (provider and provider != "all") else None

    # 1. Match from POPULAR_MODELS catalogue first (only on page 1 / initial load without cursor)
    if not cursor and page == 1:
        q_low = query.lower().strip()
        for m in POPULAR_MODELS:
            m_author = (m.get("author") or m["id"].split("/")[0]).lower()
            if target_provider_authors and m_author not in target_provider_authors:
                continue
            if official_only and not is_official_provider(m.get("author", ""), m["id"], custom_officials=custom_officials):
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
            if not _matches_quant_filter(quant_filter, f"{m['id']} {m['name']} {m['description']}", {"precision": m.get("precision", ""), "format": m.get("format", "")}):
                continue
            results.append({
                **m,
                "recommended_gpu": _determine_target_gpu(
                    m.get("size_gb", 0.0), m.get("is_moe", False),
                    m.get("active_vram_label", ""), m.get("active_vram_gb"),
                ),
            })

    # 2. Dynamic Live Fetch directly from Hugging Face Hub API
    next_cursor = None
    try:
        search_query = query.strip()
        if search_query.startswith("https://huggingface.co/"):
            search_query = search_query.replace("https://huggingface.co/", "").strip("/")
        elif search_query.startswith("http://huggingface.co/"):
            search_query = search_query.replace("http://huggingface.co/", "").strip("/")
        elif search_query.startswith("huggingface.co/"):
            search_query = search_query.replace("huggingface.co/", "").strip("/")

        hf_sort = sort
        if sort in ["size_asc", "size_desc"]:
            hf_sort = "downloads"
        elif sort in ["newest", "lastModified"]:
            hf_sort = "lastModified"

        raw_items: List[Dict[str, Any]] = []
        fetch_limit = min(limit * 3, 90)

        # A0. If direct repository id is queried (e.g. author/repo), fetch exact model metadata directly
        if "/" in search_query and not cursor:
            try:
                exact_url = f"{_HF_API_BASE}/models/{search_query}"
                exact_res = _hf_session.get(exact_url, headers=_auth_headers(hf_token), timeout=8)
                if exact_res.status_code == 200:
                    exact_item = exact_res.json()
                    if isinstance(exact_item, dict) and exact_item.get("id"):
                        raw_items.append(exact_item)
            except Exception as _ex_direct:
                log.debug("Direct repo fetch error for %s: %s", search_query, _ex_direct)

        # A. If provider filter is active: fetch ONLY models authored by that specific provider account
        if target_provider_authors:
            canonical_authors = PROVIDER_AUTHOR_MAP.get(provider.lower(), [provider])
            for auth in canonical_authors:
                auth_params = {
                    "author": auth,
                    "limit": fetch_limit,
                    "full": "true"
                }
                if search_query:
                    auth_params["search"] = search_query
                if hf_sort:
                    auth_params["sort"] = hf_sort
                    auth_params["direction"] = -1
                if category in cat_tag_map:
                    auth_params["pipeline_tag"] = cat_tag_map[category]

                auth_raw, next_c = _fetch_from_hf_api(auth_params, hf_token=hf_token)
                for item in auth_raw:
                    if not any(x.get("id") == item.get("id") for x in raw_items):
                        raw_items.append(item)
                if next_c:
                    next_cursor = next_c

        # B. If official_only is enabled without a specific provider: query official lab authors
        elif official_only:
            if not search_query:
                official_target_authors = custom_officials if (custom_officials and len(custom_officials) > 0) else [
                    "sigmanih", "zai-org", "Qwen", "deepseek-ai", "meta-llama", "THUDM", "mistralai", "google", "microsoft", "bartowski", "unsloth"
                ]
                for auth in official_target_authors[:15]:
                    auth_params = {
                        "author": auth,
                        "limit": 15,
                        "full": "true"
                    }
                    if hf_sort:
                        auth_params["sort"] = hf_sort
                        auth_params["direction"] = -1
                    if category in cat_tag_map:
                        auth_params["pipeline_tag"] = cat_tag_map[category]

                    auth_raw, _ = _fetch_from_hf_api(auth_params, hf_token=hf_token)
                    for item in auth_raw:
                        if not any(x.get("id") == item.get("id") for x in raw_items):
                            raw_items.append(item)
            else:
                params = {
                    "search": search_query,
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

        # C. Standard global search query
        else:
            effective_search = search_query
            if not effective_search:
                if quant_filter and quant_filter != "all":
                    effective_search = f"gguf {quant_filter}" if "q" in quant_filter or "imatrix" in quant_filter else quant_filter
                else:
                    effective_search = "gguf"
            elif quant_filter and quant_filter != "all" and quant_filter.lower() not in effective_search.lower():
                effective_search = f"{effective_search} {quant_filter}"

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

        # D. Transform and filter raw items with precision & active/total specs
        for item in raw_items:
            mid = item.get("id") or item.get("modelId", "")
            if any(r["id"] == mid for r in results):
                continue

            author = mid.split("/")[0] if "/" in mid else "HuggingFace"
            is_official = is_official_provider(author, mid, custom_officials=custom_officials)

            # Strict author filtering when provider is selected
            if target_provider_authors and author.lower() not in target_provider_authors:
                continue

            # Strict official filtering when official_only is enabled
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
            specs = parse_model_specs(mid, m_name, tags, raw_item=item)
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
            if not _matches_quant_filter(quant_filter, f"{mid} {m_name} {' '.join(tags)}", specs):
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
        url = f"{HF_API_BASE}/models/{model_id}?blobs=true"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
        if hf_token:
            req.add_header("Authorization", f"Bearer {hf_token}")

        with safe_urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                siblings = data.get("siblings", [])
                
                files = []
                for s in siblings:
                    rfilename = s.get("rfilename", "")
                    f_sz = s.get("size") or (s.get("lfs") or {}).get("size") or 0
                    if any(rfilename.endswith(ext) for ext in [".gguf", ".safetensors", ".bin", ".json", ".pt"]):
                        files.append({
                            "filename": rfilename,
                            "size": f_sz,
                            "is_gguf": rfilename.endswith(".gguf"),
                            "is_safetensors": rfilename.endswith(".safetensors"),
                            "download_url": f"https://huggingface.co/{model_id}/resolve/main/{rfilename}"
                        })

                created_at = data.get("createdAt")
                last_modified = data.get("lastModified")
                release_date_label = _format_date_label(created_at or last_modified)

                specs = parse_model_specs(model_id, data.get("id", ""), data.get("tags", []), raw_item=data)
                
                # Check if exact usedStorage is available from HF
                used_storage = data.get("usedStorage")
                if used_storage and used_storage > 0:
                    real_gb = round(used_storage / (1024**3), 2)
                    specs["size_gb"] = real_gb
                    specs["size_label"] = f"~{real_gb:.1f} GB" if real_gb < 1000 else f"~{real_gb/1000:.1f} TB"

                author = data.get("author", model_id.split("/")[0] if "/" in model_id else "Community")

                # Extract eval_results / benchmarks from HF model card metadata
                eval_results = []
                card_data = data.get("cardData") or {}
                raw_evals = card_data.get("eval_results") or card_data.get("model-index") or []
                # model-index is a list of dicts with "results" key
                if isinstance(raw_evals, list):
                    for entry in raw_evals:
                        if isinstance(entry, dict):
                            if "results" in entry:
                                # model-index format
                                for r in entry.get("results", []):
                                    dataset = r.get("dataset", {})
                                    for metric in r.get("metrics", []):
                                        eval_results.append({
                                            "task": r.get("task", {}).get("type", "unknown"),
                                            "dataset": dataset.get("name", dataset.get("type", "unknown")),
                                            "metric": metric.get("name", metric.get("type", "unknown")),
                                            "value": metric.get("value", 0),
                                            "verified": metric.get("verified", False),
                                        })
                            elif "task" in entry or "metric" in entry:
                                # flat eval_results format
                                eval_results.append({
                                    "task": entry.get("task", "unknown"),
                                    "dataset": entry.get("dataset", "unknown"),
                                    "metric": entry.get("metric", "unknown"),
                                    "value": entry.get("value", 0),
                                    "verified": entry.get("verified", False),
                                })

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
                    "eval_results": eval_results,
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

