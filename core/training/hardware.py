# ==============================================================================
# core/training/hardware.py — GPU Telemetry & Training Capability Report
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Hardware telemetry for the Training Lab.

Thin presentation layer on top of `core.training.gpu`, which owns the actual
multi-vendor detection (CUDA, ROCm, XPU, MPS, DirectML, CPU). This module keeps
the historical payload shape the UI and the test-suite rely on, and enriches it
with the capability/auto-tune data the Training Lab now shows.
"""

import os
import sys
import shutil
import subprocess

from core.logger import get_logger
from core.training import gpu as gpu_layer

log = get_logger(__name__)


# ---------------------------------------------------------------- probes
# NOTE: these three keep their historical names and payload shape — the test
# suite patches them on `core.training_handler` and `get_hardware_info` resolves
# them dynamically through that module.

def _check_torch_cuda() -> dict:
    """Torch/CUDA capability probe (also reports ROCm, XPU, MPS, DirectML)."""
    info = gpu_layer.probe_torch()
    return {
        "torch_available": info["torch_available"],
        "cuda_available": info["cuda_available"],
        "cuda_device_count": info["cuda_device_count"],
        "torch_version": info["torch_version"],
        "torch_cuda_version": info["torch_cuda_version"],
        "torch_gpu_list": info["torch_gpu_list"],
        "cudnn_version": info["cudnn_version"],
        "cuda_error": info["cuda_error"],
        "hip_version": info["hip_version"],
        "xpu_available": info["xpu_available"],
        "mps_available": info["mps_available"],
        "directml_available": info["directml_available"],
        "arch_list": info["arch_list"],
    }


def _query_nvidia_smi() -> list[dict]:
    """Live NVIDIA telemetry via nvidia-smi."""
    return gpu_layer.probe_nvidia_smi()


def _query_rocm_smi() -> list[dict]:
    """Live AMD telemetry via rocm-smi."""
    return gpu_layer.probe_rocm_smi()


def _query_wmi_gpus() -> list[dict]:
    """Windows display adapters (iGPU included) via WMI."""
    return gpu_layer.probe_wmi()


# ---------------------------------------------------------------- report

def _resolve(name: str, default):
    """Resolve a probe through core.training_handler so patches apply."""
    th = sys.modules.get("core.training_handler")
    return getattr(th, name, default) if th else default


def _multi_gpu_strategy(gpus: list[dict]) -> str:
    if len(gpus) < 2:
        return "device_map single"
    names = {g.get("name") for g in gpus}
    vrams = {round(g.get("vram_total_gb", g.get("vram_gb", 0)), 1) for g in gpus}
    if len(names) == 1 and len(vrams) == 1:
        return "DDP data parallel (device_map auto per modelli grandi)"
    return "device_map auto — model parallel (GPU eterogenee: DDP non applicabile)"


def get_hardware_info() -> dict:
    """Full hardware snapshot: GPUs, CPU, RAM, disk, capabilities, auto-tune."""
    fn_torch = _resolve("_check_torch_cuda", _check_torch_cuda)
    fn_smi = _resolve("_query_nvidia_smi", _query_nvidia_smi)
    fn_rocm = _resolve("_query_rocm_smi", _query_rocm_smi)
    fn_wmi = _resolve("_query_wmi_gpus", _query_wmi_gpus)

    torch_info = fn_torch()
    smi_gpus = fn_smi()
    rocm_gpus = fn_rocm()
    wmi_gpus = fn_wmi()

    def is_nvidia(g: dict) -> bool:
        return g.get("vendor", "").upper() == "NVIDIA" or "NVIDIA" in g.get("name", "").upper()

    # 1) non-NVIDIA adapters seen only by WMI (Intel/AMD iGPU) …
    gpus = [g.copy() for g in wmi_gpus
            if not is_nvidia(g) and not any(
                g.get("name", "").upper() == r.get("name", "").upper() for r in rocm_gpus)]
    # 2) … AMD cards with live ROCm telemetry …
    gpus.extend(g.copy() for g in rocm_gpus)
    # 3) … NVIDIA cards with live nvidia-smi telemetry (fallback: WMI) …
    if smi_gpus:
        gpus.extend(g.copy() for g in smi_gpus)
    else:
        gpus.extend(g.copy() for g in wmi_gpus if is_nvidia(g))
    # 4) … last resort: whatever torch enumerated.
    if not gpus and torch_info.get("torch_gpu_list"):
        gpus = [g.copy() for g in torch_info["torch_gpu_list"]]

    for idx, g in enumerate(gpus):
        g["index"] = idx
        g.setdefault("vram_total_gb", round(g.get("vram_total_mb", 0) / 1024, 1))

    gpu_count = len(gpus)
    total_vram = sum(g.get("vram_total_gb", g.get("vram_gb", 0)) for g in gpus)
    trainable = [g for g in gpus if g.get("trainable")]

    # Capabilities + auto-tune come from the live accelerator layer.
    try:
        report = gpu_layer.get_accelerator_report()
        capabilities = report["capabilities"]
        backend = report["backend"]
        autotune = gpu_layer.recommend_training_config(report=report)
    except Exception as exc:                                    # pragma: no cover
        log.warning("capability report: %s", exc)
        capabilities, backend, autotune = {}, "cpu", {}

    # System (CPU / RAM / disk)
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_total, ram_used = round(vm.total / (1024 ** 3), 1), round(vm.used / (1024 ** 3), 1)
        ram_free, ram_pct = round(vm.available / (1024 ** 3), 1), round(vm.percent, 1)
        cpu_util = round(psutil.cpu_percent(interval=None), 1)
        cpu_logical = psutil.cpu_count(logical=True) or os.cpu_count() or 4
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_total, disk_used, disk_pct = (round(disk.total / (1024 ** 3), 1),
                                          round(disk.used / (1024 ** 3), 1),
                                          round(disk.percent, 1))
    except Exception:
        ram_total, ram_used, ram_free, ram_pct = 16.0, 4.0, 12.0, 25.0
        cpu_util, cpu_logical, cpu_physical = 10.0, os.cpu_count() or 4, 4
        disk_total, disk_used, disk_pct = 500.0, 100.0, 20.0

    return {
        "success": True,
        "hardware": {
            "gpu": gpus,
            "gpu_count": gpu_count,
            "backend": backend,
            "capabilities": capabilities,
            "autotune": autotune,
            "trainable_gpu_count": len(trainable),
            "torch_available": torch_info.get("torch_available", False),
            "cuda_available": torch_info.get("cuda_available", False),
            "torch_version": torch_info.get("torch_version"),
            "cuda_version": torch_info.get("torch_cuda_version"),
            "hip_version": torch_info.get("hip_version"),
            "cudnn_version": torch_info.get("cudnn_version"),
            "arch_list": torch_info.get("arch_list", []),
            "cpu_count": cpu_logical,
            "ram_gb": ram_total,
            "ram_used_gb": ram_used,
            "cpu": {
                "logical_count": cpu_logical,
                "physical_count": cpu_physical,
                "util_pct": cpu_util,
            },
            "ram": {
                "total_gb": ram_total,
                "used_gb": ram_used,
                "free_gb": ram_free,
                "util_pct": ram_pct,
            },
            "disk": {
                "total_gb": disk_total,
                "used_gb": disk_used,
                "util_pct": disk_pct,
            },
            "multi_gpu": {
                "available": gpu_count > 1,
                "gpu_count": gpu_count,
                "total_vram_gb": total_vram,
                "strategy": _multi_gpu_strategy(gpus),
            },
            "cuda_fix": {
                "has_issue": not torch_info.get("cuda_available", False) and gpu_count == 0,
                "torch_error": torch_info.get("cuda_error"),
                "hint": _cuda_hint(torch_info, gpus),
            },
        },
    }


def _cuda_hint(torch_info: dict, gpus: list[dict]) -> str:
    """Actionable diagnosis when torch cannot use the GPUs that are present."""
    if torch_info.get("cuda_available"):
        arch_list = torch_info.get("arch_list") or []
        missing = [g for g in gpus
                   if g.get("sm") and arch_list and g["sm"] not in arch_list]
        if missing:
            names = ", ".join(f"{g['name']} ({g['sm']})" for g in missing)
            return (f"PyTorch non è compilato per {names}. Installa una build che includa "
                    f"quell'architettura (build attuali: {', '.join(arch_list)}).")
        return ""
    if not torch_info.get("torch_available"):
        return "PyTorch non installato: pip install torch --index-url https://download.pytorch.org/whl/cu128"
    if gpus and any(g.get("vendor") == "NVIDIA" for g in gpus):
        return ("GPU NVIDIA rilevata ma CUDA non disponibile in PyTorch: probabilmente è "
                "installata la build CPU. Reinstalla torch con l'indice cu128.")
    if torch_info.get("directml_available"):
        return "Nessuna CUDA: verrà usato DirectML (GPU AMD/Intel su Windows)."
    return "Nessun acceleratore disponibile: il training userà la CPU."


def get_hardware_status() -> dict:
    return get_hardware_info()


def get_gpu_capabilities() -> dict:
    """Capabilities + per-GPU detail + auto-tune recipe (API endpoint payload)."""
    report = gpu_layer.get_accelerator_report(refresh=True)
    return {
        "success": True,
        "backend": report["backend"],
        "capabilities": report["capabilities"],
        "gpus": report["gpus"],
        "trainable_gpus": report["trainable_gpus"],
        "total_vram_gb": report["total_vram_gb"],
        "torch": report["torch"],
    }


def get_autotune(method: str = "lora_unsloth", base_model: str = "",
                 seq_len: int = 2048) -> dict:
    """Recommended training settings for a given model/method on this rig."""
    return {
        "success": True,
        "method": method,
        "base_model": base_model,
        "config": gpu_layer.recommend_training_config(method, base_model, seq_len),
    }


def restart_ollama_service() -> dict:
    """Free VRAM: empty torch/CUDA caches and unload all active Ollama models."""
    import gc
    messages = []

    # 1. Force Python garbage collection & Torch CUDA cache empty
    gc.collect()
    res = gpu_layer.empty_cache()
    if res.get("freed"):
        messages.append(f"Cache {'/'.join(res['freed'])} svuotata")

    # 2. Discover loaded Ollama models via API and unload them
    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    if not ollama_url.startswith(("http://", "https://")):
        ollama_url = f"http://{ollama_url}"

    unloaded_models = []
    ollama_bin = shutil.which("ollama")

    try:
        import requests
        # Get list of currently running/loaded models from Ollama /api/ps
        ps_resp = requests.get(f"{ollama_url}/api/ps", timeout=4)
        if ps_resp.status_code == 200:
            ps_data = ps_resp.json()
            models = ps_data.get("models", [])
            for m in models:
                model_name = m.get("name") or m.get("model")
                if model_name:
                    # Unload model by setting keep_alive to 0 on /api/generate and /api/chat
                    try:
                        requests.post(f"{ollama_url}/api/generate",
                                      json={"model": model_name, "keep_alive": 0},
                                      timeout=4)
                    except Exception:
                        pass
                    try:
                        requests.post(f"{ollama_url}/api/chat",
                                      json={"model": model_name, "keep_alive": 0},
                                      timeout=4)
                    except Exception:
                        pass

                    # Stop via CLI if binary exists
                    if ollama_bin:
                        try:
                            subprocess.run([ollama_bin, "stop", model_name],
                                           capture_output=True, text=True, timeout=5)
                        except Exception as exc:
                            log.warning("Ollama stop command for %s failed: %s", model_name, exc)

                    unloaded_models.append(model_name)
    except Exception as exc:
        log.warning("Failed to reach Ollama API at %s/api/ps: %s", ollama_url, exc)

    # 3. Fallback: if /api/ps returned nothing or failed, but CLI is available, try listing models via CLI or stopping
    if not unloaded_models and ollama_bin:
        try:
            ps_cli = subprocess.run([ollama_bin, "ps"], capture_output=True, text=True, timeout=5)
            if ps_cli.returncode == 0:
                lines = [line.strip() for line in ps_cli.stdout.splitlines() if line.strip()]
                # Skip header line if present
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        try:
                            subprocess.run([ollama_bin, "stop", model_name],
                                           capture_output=True, text=True, timeout=5)
                            unloaded_models.append(model_name)
                        except Exception:
                            pass
        except Exception as exc:
            log.warning("Ollama CLI ps/stop fallback failed: %s", exc)

    # 4. Final CUDA cache cleanup after unloading models
    gpu_layer.empty_cache()

    if unloaded_models:
        unique_models = list(dict.fromkeys(unloaded_models))
        messages.append(f"Modelli Ollama scaricati dalla VRAM: {', '.join(unique_models)}")
    else:
        messages.append("Nessun modello Ollama attivo in VRAM da scaricare")

    msg = " • ".join(messages) if messages else "VRAM liberata e cache resettata con successo."
    return {"success": True, "message": msg, "unloaded_models": unloaded_models}
