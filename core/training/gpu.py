# ==============================================================================
# core/training/gpu.py — Universal Accelerator Layer (CUDA-first, vendor agnostic)
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Single source of truth about the compute hardware available for training.

Responsibilities:
  * detect every usable backend (CUDA, ROCm/HIP, Intel XPU, Apple MPS, DirectML, CPU)
  * enrich each GPU with architecture capabilities derived from its compute
    capability (bf16 / tf32 / fp8 / FlashAttention / tensor cores / 4-bit)
  * turn "hardware + model + method" into a concrete, CUDA-optimised training
    recipe (dtype, attention kernel, batch size, grad-accum, quantisation,
    multi-GPU strategy)
  * emit the environment variables and in-process torch flags that make CUDA
    training fast and memory-stable

Everything degrades gracefully: no torch, no driver, no GPU -> CPU recipe.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

from core.logger import get_logger

log = get_logger(__name__)

# ------------------------------------------------------------------ constants

VENDOR_COLORS = {
    "NVIDIA": "#76b900",
    "AMD": "#ff4444",
    "INTEL": "#0071c5",
    "APPLE": "#a2aaad",
    "GPU": "#00f2fe",
}

# NVIDIA compute capability -> architecture + tensor-core feature set.
# Only the *major* families are listed; lookup falls back to the closest lower
# entry so future GPUs (sm_130, ...) inherit the newest known feature set.
_NVIDIA_ARCH = [
    # (major, minor), arch name, features
    ((5, 0), "Maxwell", {"tensor_cores": False, "fp16": False, "bf16": False, "tf32": False, "fp8": False, "flash_attn": False}),
    ((6, 0), "Pascal", {"tensor_cores": False, "fp16": True, "bf16": False, "tf32": False, "fp8": False, "flash_attn": False}),
    ((7, 0), "Volta", {"tensor_cores": True, "fp16": True, "bf16": False, "tf32": False, "fp8": False, "flash_attn": False}),
    ((7, 5), "Turing", {"tensor_cores": True, "fp16": True, "bf16": False, "tf32": False, "fp8": False, "flash_attn": False}),
    ((8, 0), "Ampere", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": False, "flash_attn": True}),
    ((8, 6), "Ampere", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": False, "flash_attn": True}),
    ((8, 9), "Ada Lovelace", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": True, "flash_attn": True}),
    ((9, 0), "Hopper", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": True, "flash_attn": True}),
    ((10, 0), "Blackwell", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": True, "flash_attn": True}),
    ((12, 0), "Blackwell (RTX 50)", {"tensor_cores": True, "fp16": True, "bf16": True, "tf32": True, "fp8": True, "flash_attn": True}),
]

# AMD gfx target -> architecture. ROCm exposes bf16 from CDNA/RDNA2 onwards.
_AMD_ARCH = {
    "gfx900": "Vega", "gfx906": "Vega 20", "gfx908": "CDNA", "gfx90a": "CDNA 2",
    "gfx940": "CDNA 3", "gfx941": "CDNA 3", "gfx942": "CDNA 3",
    "gfx1010": "RDNA", "gfx1030": "RDNA 2", "gfx1031": "RDNA 2", "gfx1032": "RDNA 2",
    "gfx1100": "RDNA 3", "gfx1101": "RDNA 3", "gfx1102": "RDNA 3",
    "gfx1200": "RDNA 4", "gfx1201": "RDNA 4",
}

_CACHE: dict = {"report": None, "ts": 0.0}
_CACHE_TTL = 2.0  # seconds — telemetry is polled by the UI, keep it cheap


# ------------------------------------------------------------------ helpers

def _vendor_of(name: str) -> str:
    n = (name or "").upper()
    if "NVIDIA" in n or "GEFORCE" in n or "QUADRO" in n or "TESLA" in n or "RTX" in n:
        return "NVIDIA"
    if "AMD" in n or "RADEON" in n or "GFX" in n or "INSTINCT" in n:
        return "AMD"
    if "INTEL" in n or "ARC" in n or "IRIS" in n or "XE " in n:
        return "INTEL"
    if "APPLE" in n or n.startswith("M1") or n.startswith("M2") or n.startswith("M3"):
        return "APPLE"
    return "GPU"


def nvidia_arch_features(major: int, minor: int) -> dict:
    """Architecture name + capability flags for an NVIDIA compute capability."""
    best = _NVIDIA_ARCH[0]
    for entry in _NVIDIA_ARCH:
        if (major, minor) >= entry[0]:
            best = entry
    (_cc, arch, feats) = best
    out = {"arch": arch}
    out.update(feats)
    return out


def _amd_arch_features(gfx: str) -> dict:
    gfx = (gfx or "").lower().split(":")[0]
    arch = _AMD_ARCH.get(gfx, "AMD GPU")
    modern = any(gfx.startswith(p) for p in ("gfx90a", "gfx94", "gfx110", "gfx111", "gfx12"))
    return {
        "arch": arch,
        "tensor_cores": modern,
        "fp16": True,
        "bf16": modern,
        "tf32": False,
        "fp8": gfx.startswith("gfx94") or gfx.startswith("gfx12"),
        "flash_attn": modern,
    }


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            return None
        return res.stdout
    except Exception:
        return None


def _blank_gpu(index: int, name: str) -> dict:
    vendor = _vendor_of(name)
    return {
        "index": index,
        "name": name,
        "vendor": vendor,
        "vendor_color": VENDOR_COLORS.get(vendor, VENDOR_COLORS["GPU"]),
        "backend": "cpu",
        "vram_total_mb": 0.0,
        "vram_used_mb": 0.0,
        "vram_free_mb": 0.0,
        "vram_total_gb": 0.0,
        "vram_used_gb": 0.0,
        "vram_free_gb": 0.0,
        "vram_pct": 0.0,
        "driver_version": "N/A",
        "compute_cap": "N/A",
        "compute_capability": "N/A",
        "arch": "Unknown",
        "gpu_util_pct": 0.0,
        "temp_c": 0.0,
        "power_draw_w": 0.0,
        "power_limit_w": 0.0,
        "supports_bf16": False,
        "supports_fp16": False,
        "supports_tf32": False,
        "supports_fp8": False,
        "supports_flash_attn": False,
        "tensor_cores": False,
        "trainable": False,
    }


def _fill_vram(gpu: dict, total_mb: float, used_mb: float, free_mb: float | None = None) -> None:
    free_mb = max(0.0, total_mb - used_mb) if free_mb is None else free_mb
    gpu.update({
        "vram_total_mb": round(total_mb, 1),
        "vram_used_mb": round(used_mb, 1),
        "vram_free_mb": round(free_mb, 1),
        "vram_total_gb": round(total_mb / 1024, 1),
        "vram_used_gb": round(used_mb / 1024, 1),
        "vram_free_gb": round(free_mb / 1024, 1),
        "vram_pct": round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0,
    })


# ------------------------------------------------------------------ probes

def probe_nvidia_smi() -> list[dict]:
    """Live NVIDIA telemetry (VRAM, utilisation, temperature, power, cc)."""
    binary = shutil.which("nvidia-smi")
    if not binary:
        return []
    fields = ("index,name,memory.total,memory.used,memory.free,driver_version,"
              "utilization.gpu,temperature.gpu,power.draw,power.limit,compute_cap")
    out = _run([binary, f"--query-gpu={fields}", "--format=csv,noheader,nounits"])
    if not out:
        return []

    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue

        def num(i: int, default: float = 0.0) -> float:
            try:
                return float(parts[i])
            except (IndexError, ValueError):
                return default

        gpu = _blank_gpu(int(num(0)), parts[1])
        gpu["backend"] = "cuda"
        gpu["trainable"] = True
        _fill_vram(gpu, num(2), num(3), num(4))
        gpu["driver_version"] = parts[5]
        gpu["gpu_util_pct"] = round(num(6), 1)
        gpu["temp_c"] = round(num(7), 1)
        gpu["power_draw_w"] = round(num(8), 1)
        gpu["power_limit_w"] = round(num(9), 1)

        cc = parts[10] if len(parts) > 10 else ""
        if re.match(r"^\d+\.\d+$", cc or ""):
            major, minor = (int(x) for x in cc.split("."))
            feats = nvidia_arch_features(major, minor)
            gpu.update({
                "compute_cap": cc,
                "compute_capability": cc,
                "sm": f"sm_{major}{minor}",
                "arch": feats["arch"],
                "supports_bf16": feats["bf16"],
                "supports_fp16": feats["fp16"],
                "supports_tf32": feats["tf32"],
                "supports_fp8": feats["fp8"],
                "supports_flash_attn": feats["flash_attn"],
                "tensor_cores": feats["tensor_cores"],
            })
        gpus.append(gpu)
    return gpus


def probe_gpu_processes() -> list[dict]:
    """Chi sta tenendo memoria sulla GPU, non solo quanta ne e' occupata.

    `probe_nvidia_smi` risponde "5 GB su 16"; questa risponde "il pid 36672".
    La differenza conta quando un processo resta appeso: senza il pid non c'e'
    niente su cui agire, e la VRAM occupata da sola non dice nemmeno se sia il
    training di Sigma o qualcos'altro.

    Due limiti del driver da tenere presenti, perche' cambiano cosa si puo'
    mostrare:

    * `used_gpu_memory` vale `[N/A]` su Windows in modalita' WDDM — li' e' il
      sistema operativo a gestire la memoria video, non il driver, che quindi
      non sa attribuirla ai singoli processi. Quel `None` va portato fino in
      fondo: scriverlo come 0 significherebbe mostrare "0 GB" accanto a un
      training che ne sta usando cinque.
    * `--query-compute-apps` non elenca i soli contesti di calcolo. Le
      applicazioni che ne aprono uno accanto a quello grafico — i browser
      basati su Chromium, i launcher di giochi — compaiono qui esattamente come
      un training. Distinguerle non e' possibile da questa sonda: se ne occupa
      `gpu_process_inventory`, che sa quali pid appartengono a Sigma.
    """
    binary = shutil.which("nvidia-smi")
    if not binary:
        return []

    # nvidia-smi identifica la scheda di un processo per uuid; tutto il resto di
    # Sigma la identifica per indice.
    schede: dict[str, tuple[int, str]] = {}
    mappa = _run([binary, "--query-gpu=index,uuid,name", "--format=csv,noheader"])
    for riga in (mappa or "").strip().splitlines():
        parti = [p.strip() for p in riga.split(",")]
        if len(parti) >= 3:
            try:
                schede[parti[1]] = (int(parti[0]), parti[2])
            except ValueError:
                continue

    out = _run([binary, "--query-compute-apps=pid,used_gpu_memory,gpu_uuid",
                "--format=csv,noheader,nounits"])
    if not out:
        return []

    try:
        import psutil
    except ImportError:
        psutil = None

    processi = []
    for riga in out.strip().splitlines():
        parti = [p.strip() for p in riga.split(",")]
        if len(parti) < 2:
            continue
        try:
            pid = int(parti[0])
        except ValueError:
            continue
        try:
            vram_mb = float(parti[1])
        except ValueError:
            vram_mb = None          # "[N/A]": il driver non la sa, non e' zero
        indice, nome_gpu = schede.get(parti[2] if len(parti) > 2 else "", (-1, ""))

        voce = {
            "pid": pid,
            "gpu_index": indice,
            "gpu_name": nome_gpu,
            "vram_mb": round(vram_mb, 1) if vram_mb is not None else None,
            "vram_gb": round(vram_mb / 1024, 2) if vram_mb is not None else None,
            "name": "",
            "cmdline": "",
            "started_at": "",
            "ram_gb": 0.0,
            "alive": True,
        }
        if psutil is not None:
            try:
                proc = psutil.Process(pid)
                with proc.oneshot():
                    voce["name"] = proc.name()
                    voce["cmdline"] = " ".join(proc.cmdline())
                    voce["started_at"] = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(proc.create_time()))
                    voce["ram_gb"] = round(proc.memory_info().rss / 1024**3, 2)
            except Exception:
                # Il driver lo elenca ma il processo e' gia' sparito, oppure e'
                # di un altro utente e non e' ispezionabile.
                voce["alive"] = False
        processi.append(voce)

    # Il criterio giusto sarebbe la VRAM, ma su WDDM e' quasi sempre `None`: li'
    # decide l'eta', che c'e' sempre, con il piu' recente in testa — e' quello
    # che l'utente ha appena avviato e sta cercando. Due passate invece di una
    # chiave sola perche' l'ordinamento di Python e' stabile: la prima fissa il
    # criterio di scorta, la seconda gli antepone la VRAM dove esiste.
    processi.sort(key=lambda p: p["started_at"] or "", reverse=True)
    processi.sort(key=lambda p: p["vram_mb"] or 0.0, reverse=True)
    return processi


def probe_rocm_smi() -> list[dict]:
    """Live AMD telemetry via rocm-smi (Linux ROCm installs)."""
    binary = shutil.which("rocm-smi")
    if not binary:
        return []
    out = _run([binary, "--showid", "--showproductname", "--showmeminfo", "vram",
                "--showuse", "--showtemp", "--showpower", "--json"], timeout=8)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []

    gpus = []
    for key, card in sorted(data.items()):
        if not isinstance(card, dict) or not key.lower().startswith("card"):
            continue
        idx = int(re.sub(r"\D", "", key) or len(gpus))
        name = (card.get("Card series") or card.get("Card model")
                or card.get("Device Name") or f"AMD GPU {idx}")
        gpu = _blank_gpu(idx, name)
        gpu["vendor"] = "AMD"
        gpu["vendor_color"] = VENDOR_COLORS["AMD"]
        gpu["backend"] = "rocm"
        gpu["trainable"] = True

        def as_float(val, div=1.0, default=0.0):
            try:
                return float(str(val).strip().rstrip("%cCW")) / div
            except Exception:
                return default

        total = as_float(card.get("VRAM Total Memory (B)"), 1024 ** 2)
        used = as_float(card.get("VRAM Total Used Memory (B)"), 1024 ** 2)
        _fill_vram(gpu, total, used)
        gpu["gpu_util_pct"] = as_float(card.get("GPU use (%)"))
        gpu["temp_c"] = as_float(card.get("Temperature (Sensor edge) (C)"))
        gpu["power_draw_w"] = as_float(card.get("Average Graphics Package Power (W)"))

        gfx = str(card.get("GFX Version") or card.get("Target Graphics Version") or "")
        feats = _amd_arch_features(gfx)
        gpu.update({
            "compute_cap": gfx or "ROCm",
            "compute_capability": gfx or "ROCm",
            "arch": feats["arch"],
            "supports_bf16": feats["bf16"],
            "supports_fp16": feats["fp16"],
            "supports_fp8": feats["fp8"],
            "supports_flash_attn": feats["flash_attn"],
            "tensor_cores": feats["tensor_cores"],
        })
        gpus.append(gpu)
    return gpus


def probe_torch() -> dict:
    """Everything torch knows: backend availability, versions, device list."""
    info = {
        "torch_available": False,
        "torch_version": None,
        "cuda_available": False,
        "cuda_device_count": 0,
        "torch_cuda_version": None,
        "hip_version": None,
        "cudnn_version": None,
        "xpu_available": False,
        "mps_available": False,
        "directml_available": False,
        "arch_list": [],
        "torch_gpu_list": [],
        "cuda_error": None,
        "flash_attn_pkg": False,
    }
    # La GPU può supportare FlashAttention-2 e il pacchetto non essere
    # installato: senza questo controllo l'autotune chiede
    # attn_implementation="flash_attention_2" e il caricamento del modello
    # fallisce a run avviato.
    info["flash_attn_pkg"] = importlib.util.find_spec("flash_attn") is not None
    try:
        import torch
    except Exception as exc:
        info["cuda_error"] = f"torch non importabile: {exc}"
        return info

    info["torch_available"] = True
    info["torch_version"] = torch.__version__
    info["torch_cuda_version"] = getattr(torch.version, "cuda", None)
    info["hip_version"] = getattr(torch.version, "hip", None)

    try:
        info["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as exc:
        info["cuda_error"] = str(exc)

    if info["cuda_available"]:
        try:
            info["cuda_device_count"] = torch.cuda.device_count()
            info["arch_list"] = list(torch.cuda.get_arch_list())
            if torch.backends.cudnn.is_available():
                info["cudnn_version"] = str(torch.backends.cudnn.version())
        except Exception as exc:
            info["cuda_error"] = str(exc)

        is_rocm = bool(info["hip_version"])
        for i in range(info["cuda_device_count"]):
            try:
                props = torch.cuda.get_device_properties(i)
            except Exception:
                continue
            gpu = _blank_gpu(i, props.name)
            gpu["backend"] = "rocm" if is_rocm else "cuda"
            gpu["trainable"] = True
            total_mb = props.total_memory / (1024 ** 2)
            try:
                free_b, _total_b = torch.cuda.mem_get_info(i)
                free_mb = free_b / (1024 ** 2)
                _fill_vram(gpu, total_mb, total_mb - free_mb, free_mb)
            except Exception:
                _fill_vram(gpu, total_mb, torch.cuda.memory_allocated(i) / (1024 ** 2))

            if is_rocm:
                feats = _amd_arch_features(getattr(props, "gcnArchName", ""))
                cc = getattr(props, "gcnArchName", "ROCm")
            else:
                feats = nvidia_arch_features(props.major, props.minor)
                cc = f"{props.major}.{props.minor}"
                gpu["sm"] = f"sm_{props.major}{props.minor}"
            gpu.update({
                "compute_cap": cc,
                "compute_capability": cc,
                "arch": feats["arch"],
                "supports_bf16": feats["bf16"],
                "supports_fp16": feats["fp16"],
                "supports_tf32": feats.get("tf32", False),
                "supports_fp8": feats["fp8"],
                "supports_flash_attn": feats["flash_attn"],
                "tensor_cores": feats["tensor_cores"],
                "multi_processor_count": getattr(props, "multi_processor_count", 0),
            })
            info["torch_gpu_list"].append(gpu)

    # Intel XPU (Arc / Data Center GPU Max)
    try:
        xpu = getattr(torch, "xpu", None)
        if xpu is not None and xpu.is_available():
            info["xpu_available"] = True
            for i in range(xpu.device_count()):
                props = xpu.get_device_properties(i)
                gpu = _blank_gpu(i, getattr(props, "name", f"Intel XPU {i}"))
                gpu["vendor"] = "INTEL"
                gpu["vendor_color"] = VENDOR_COLORS["INTEL"]
                gpu["backend"] = "xpu"
                gpu["trainable"] = True
                _fill_vram(gpu, getattr(props, "total_memory", 0) / (1024 ** 2), 0.0)
                gpu.update({
                    "arch": "Intel Xe",
                    "compute_cap": "XPU",
                    "compute_capability": "XPU",
                    "supports_fp16": True,
                    "supports_bf16": True,
                    "tensor_cores": True,
                })
                info["torch_gpu_list"].append(gpu)
    except Exception:
        pass

    # Apple Silicon
    try:
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            info["mps_available"] = True
    except Exception:
        pass

    # DirectML (Windows: AMD / Intel / any DX12 device)
    try:
        import torch_directml
        if torch_directml.is_available():
            info["directml_available"] = True
    except Exception:
        pass

    return info


def probe_wmi() -> list[dict]:
    """Windows fallback: every display adapter, including iGPUs without a CLI."""
    if sys.platform != "win32":
        return []
    out = _run(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"], timeout=6)
    if not out or not out.strip():
        return []
    try:
        data = json.loads(out.strip())
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]

    gpus = []
    for idx, item in enumerate(data):
        name = item.get("Name") or f"GPU {idx}"
        gpu = _blank_gpu(idx, name)
        ram = item.get("AdapterRAM") or 0
        _fill_vram(gpu, round(ram / (1024 ** 2), 1) if ram > 0 else 0.0, 0.0)
        gpu["driver_version"] = item.get("DriverVersion") or "N/A"
        gpu["compute_cap"] = "DirectX"
        gpu["compute_capability"] = "DirectX"
        gpu["backend"] = "directml"
        gpu["arch"] = "DirectX 12"
        gpus.append(gpu)
    return gpus


# ------------------------------------------------------------------ report

def get_accelerator_report(refresh: bool = False) -> dict:
    """Merged view of every accelerator, newest telemetry first.

    Priority per GPU: vendor CLI (live telemetry) > torch > WMI (names only).
    """
    now = time.time()
    if not refresh and _CACHE["report"] and (now - _CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["report"]

    torch_info = probe_torch()
    nv = probe_nvidia_smi()
    amd = probe_rocm_smi()
    wmi = probe_wmi()

    gpus: list[dict] = []
    seen_names: set[str] = set()

    for gpu in nv + amd:
        gpus.append(dict(gpu))
        seen_names.add(gpu["name"].upper())

    # torch devices the vendor CLIs did not report (XPU, MPS-backed, ROCm w/o CLI)
    for gpu in torch_info["torch_gpu_list"]:
        if gpu["name"].upper() in seen_names:
            # merge torch-only fields (compute cap, SM count) into the CLI entry
            for existing in gpus:
                if existing["name"].upper() == gpu["name"].upper() and \
                        existing.get("multi_processor_count", 0) == 0:
                    existing["multi_processor_count"] = gpu.get("multi_processor_count", 0)
                    break
            continue
        gpus.append(dict(gpu))
        seen_names.add(gpu["name"].upper())

    if torch_info["mps_available"] and not any(g["backend"] == "mps" for g in gpus):
        gpu = _blank_gpu(len(gpus), "Apple Silicon GPU")
        gpu.update({"vendor": "APPLE", "vendor_color": VENDOR_COLORS["APPLE"],
                    "backend": "mps", "arch": "Apple Silicon", "trainable": True,
                    "supports_fp16": True, "supports_bf16": True,
                    "compute_cap": "MPS", "compute_capability": "MPS"})
        gpus.append(gpu)

    # WMI adds display adapters nothing else saw (Intel iGPU, AMD APU, ...)
    for gpu in wmi:
        if any(gpu["name"].upper() in s or s in gpu["name"].upper() for s in seen_names):
            continue
        if torch_info["directml_available"]:
            gpu["trainable"] = True  # DirectML can actually train on it
        gpus.append(gpu)
        seen_names.add(gpu["name"].upper())

    for i, gpu in enumerate(gpus):
        gpu["index"] = i
        gpu.setdefault("device_str", _device_str(gpu))

    trainable = [g for g in gpus if g.get("trainable")]
    backend = select_backend(torch_info, trainable)

    report = {
        "backend": backend,
        "gpus": gpus,
        "trainable_gpus": trainable,
        "gpu_count": len(gpus),
        "trainable_count": len(trainable),
        "total_vram_gb": round(sum(g.get("vram_total_gb", 0.0) for g in trainable), 1),
        "torch": torch_info,
        "capabilities": aggregate_capabilities(trainable, torch_info, backend),
    }
    _CACHE["report"] = report
    _CACHE["ts"] = now
    return report


def _device_str(gpu: dict) -> str:
    backend = gpu.get("backend", "cpu")
    if backend in ("cuda", "rocm"):
        return f"cuda:{gpu['index']}"
    if backend == "xpu":
        return f"xpu:{gpu['index']}"
    if backend == "mps":
        return "mps"
    if backend == "directml":
        return f"dml:{gpu['index']}"
    return "cpu"


def select_backend(torch_info: dict, trainable: list[dict]) -> str:
    """CUDA first, then the other accelerators, CPU last."""
    if torch_info.get("cuda_available"):
        return "rocm" if torch_info.get("hip_version") else "cuda"
    if torch_info.get("xpu_available"):
        return "xpu"
    if torch_info.get("mps_available"):
        return "mps"
    if torch_info.get("directml_available") and trainable:
        return "directml"
    return "cpu"


def aggregate_capabilities(trainable: list[dict], torch_info: dict, backend: str) -> dict:
    """What the *whole rig* can do — driven by the weakest trainable GPU.

    Mixed rigs (e.g. RTX 5070 Ti + RTX 5060) must pick a dtype every device
    supports, otherwise a DDP run dies on the slower card.
    """
    if not trainable:
        return {
            "backend": backend,
            "bf16": False, "fp16": False, "tf32": False, "fp8": False,
            "flash_attn": False, "tensor_cores": False, "bnb_4bit": False,
            "arch": "CPU", "min_vram_gb": 0.0, "max_vram_gb": 0.0,
            "homogeneous": True, "device_strs": ["cpu"],
        }

    def every(flag: str) -> bool:
        return all(g.get(flag, False) for g in trainable)

    vrams = [g.get("vram_total_gb", 0.0) for g in trainable]
    archs = {g.get("arch", "?") for g in trainable}
    cuda_like = backend in ("cuda", "rocm")

    return {
        "backend": backend,
        "bf16": every("supports_bf16"),
        "fp16": every("supports_fp16"),
        "tf32": every("supports_tf32") and backend == "cuda",
        "fp8": every("supports_fp8"),
        # Anche l'hardware più recente resta su SDPA se flash_attn non c'è.
        "flash_attn": (every("supports_flash_attn") and cuda_like
                       and bool(torch_info.get("flash_attn_pkg"))),
        "tensor_cores": every("tensor_cores"),
        # bitsandbytes 4-bit needs a real CUDA/ROCm device
        "bnb_4bit": cuda_like,
        "arch": " + ".join(sorted(archs)),
        "min_vram_gb": round(min(vrams), 1),
        "max_vram_gb": round(max(vrams), 1),
        "total_vram_gb": round(sum(vrams), 1),
        "homogeneous": len(archs) == 1 and len(set(vrams)) == 1,
        "device_strs": [g.get("device_str", "cpu") for g in trainable],
        "torch_version": torch_info.get("torch_version"),
        "cuda_version": torch_info.get("torch_cuda_version"),
        "arch_list": torch_info.get("arch_list", []),
    }


# ------------------------------------------------------------------ recipes

def estimate_model_params_b(model_name: str) -> float:
    """Best-effort parameter count (billions) from a model id."""
    name = (model_name or "").lower()
    match = re.search(r"(\d+(?:[\.,]\d+)?)\s*b(?:[-_./]|$)", name)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            pass
    match = re.search(r"(\d+)\s*m(?:[-_./]|$)", name)
    if match:
        return float(match.group(1)) / 1000.0
    for needle, size in (("gpt2-xl", 1.5), ("gpt2-large", 0.77), ("gpt2-medium", 0.35),
                         ("gpt2", 0.124), ("from_scratch", 0.05), ("tiny", 0.1)):
        if needle in name:
            return size
    return 7.0  # unknown id: assume a 7B, the safe/conservative default


def recommend_training_config(method: str = "lora_unsloth",
                              base_model: str = "",
                              seq_len: int = 2048,
                              report: dict | None = None) -> dict:
    """Turn hardware + model into concrete, CUDA-optimised training settings."""
    report = report or get_accelerator_report()
    caps = report["capabilities"]
    trainable = report["trainable_gpus"]
    params_b = estimate_model_params_b(base_model)
    gpu_count = len(trainable)

    # Heterogeneous rigs (e.g. 5070 Ti 16GB + 5060 8GB) cannot do DDP: the run
    # would be capped by the smaller card. Default to the *largest* GPU and only
    # spread across devices when the model genuinely does not fit on it.
    homogeneous = caps.get("homogeneous", True)
    primary = max(trainable, key=lambda g: g.get("vram_total_gb", 0.0)) if trainable else None
    vram = caps.get("min_vram_gb", 0.0) if homogeneous else (primary or {}).get("vram_total_gb", 0.0)

    if not trainable:
        return {
            "device": "cpu", "device_map": None, "gpu_indices": [],
            "dtype": "float32", "bf16": False, "fp16": False, "tf32": False,
            "load_in_4bit": False, "attn_implementation": "eager",
            "batch_size": 1, "gradient_accumulation": 8,
            "gradient_checkpointing": True, "optim": "adamw_torch",
            "max_seq_length": min(seq_len, 1024), "torch_compile": False,
            "params_b": params_b, "strategy": "cpu",
            "notes": ["Nessuna GPU utilizzabile: training su CPU, molto lento."],
        }

    notes: list[str] = []

    # --- precision ---------------------------------------------------------
    if caps["bf16"]:
        dtype, bf16, fp16 = "bfloat16", True, False
        notes.append(f"bf16 attivo ({caps['arch']}): range dinamico pieno, nessun GradScaler.")
    elif caps["fp16"]:
        dtype, bf16, fp16 = "float16", False, True
        notes.append("bf16 non supportato: uso fp16 con loss scaling.")
    else:
        dtype, bf16, fp16 = "float32", False, False
        notes.append("Nessun tensor core: fp32.")

    # --- quantisation ------------------------------------------------------
    # Rough VRAM budget: LoRA on a 4-bit base ~= 0.75 GB/B params + activations.
    weights_gb_16bit = params_b * 2.0
    weights_gb_4bit = params_b * 0.6
    load_in_4bit = False
    if method in ("lora_unsloth", "trl_sft"):
        if caps["bnb_4bit"] and weights_gb_16bit + 3.0 > vram:
            load_in_4bit = True
            notes.append(f"Modello ~{params_b:g}B > VRAM {vram:g}GB: quantizzazione 4-bit (QLoRA).")
    budget = weights_gb_4bit if load_in_4bit else weights_gb_16bit

    # --- attention kernel --------------------------------------------------
    if caps["flash_attn"]:
        attn = "flash_attention_2"
    elif caps["backend"] in ("cuda", "rocm"):
        attn = "sdpa"
    else:
        attn = "eager"

    # --- activations, batch, accumulation ----------------------------------
    gradient_checkpointing = params_b >= 3 or budget > vram * 0.5 or method == "full_pretrain"
    if gradient_checkpointing:
        notes.append("Gradient checkpointing attivo: ~30-50% meno VRAM, ~20% più lento.")

    # Costo delle attivazioni per sequenza, tarato su una misura e non a
    # intuito. La costante precedente (0,55) veniva da run su dati che si
    # erano poi rivelati sbagliati: sequenze di dieci caratteri, che dopo la
    # tokenizzazione non riempivano niente. Con testo vero da 1024 token e un
    # modello da 0,5B la spesa reale e' ~1,8 GB a sequenza — dieci volte la
    # stima — e il batch 8 che ne derivava portava la scheda al 94%, con il
    # passo degradato da 18 a 83 secondi.
    per_seq_gb = 5.5 * (seq_len / 2048.0) * max(0.35, params_b) ** 0.7
    if gradient_checkpointing:
        per_seq_gb *= 0.45
    # Quanto c'e' davvero, non quanto c'e' scritto sulla scatola: browser,
    # editor e il resto del desktop tengono qualche GB, e la scheda che il
    # training trova non e' mai quella nominale. Se la lettura non e'
    # disponibile si resta sul totale, come prima.
    # Chi occupa la scheda adesso spesso non ci sara' fra un minuto: Ollama
    # rilascia il modello dopo il keep-alive, un job che sta finendo libera
    # tutto. Prendere la lettura alla lettera farebbe pianificare a batch 1 un
    # run che poi girera' su una scheda vuota. Il pavimento al 60% e' il
    # compromesso: una scheda davvero occupata abbassa il batch, un occupante
    # di passaggio no.
    libera = (primary or {}).get("vram_free_gb") or 0.0
    disponibile = max(min(vram, libera), vram * 0.6) if libera > 0 else vram
    headroom = max(0.4, disponibile * 0.85 - budget - 1.2)  # margine 15% + contesto CUDA
    batch = int(max(1, min(8, headroom / per_seq_gb)))
    target_batch = 32                                  # effective batch in sequences
    grad_accum = max(1, round(target_batch / max(1, batch)))

    # --- multi-GPU ---------------------------------------------------------
    device_map = None
    strategy = "single_gpu"
    selected = [primary] if primary else []
    if gpu_count > 1 and homogeneous:
        strategy = "ddp"
        selected = list(trainable)
        notes.append(f"{gpu_count} GPU identiche: DDP (data parallel), throughput ~{gpu_count}x.")
    elif gpu_count > 1:
        sizes = ", ".join(f"{g['name']} {g['vram_total_gb']:g}GB" for g in trainable)
        if budget + 2.0 > vram:
            strategy = "model_parallel"
            device_map = "auto"
            selected = list(trainable)
            notes.append(f"Modello troppo grande per una sola scheda: device_map='auto' "
                         f"distribuisce i layer su {gpu_count} GPU ({sizes}).")
        else:
            notes.append(f"GPU eterogenee ({sizes}): DDP non applicabile, uso la più capiente "
                         f"({primary['name']}, {vram:g}GB). L'altra resta libera per inferenza.")
    elif gpu_count == 1:
        notes.append(f"1 GPU: {trainable[0]['name']} ({vram:g}GB, {trainable[0].get('arch')}).")

    # DDP already multiplies the batch by the world size: rebalance accumulation
    # so the *effective* batch stays at the target instead of exploding.
    if strategy == "ddp":
        grad_accum = max(1, round(target_batch / max(1, batch * len(selected))))

    # --- optimiser ---------------------------------------------------------
    if caps["backend"] == "cuda":
        optim = "adamw_8bit" if load_in_4bit or params_b >= 3 else "adamw_torch_fused"
    else:
        optim = "adamw_torch"

    return {
        "device": (selected[0].get("device_str") if selected else caps["device_strs"][0]),
        "device_map": device_map,
        "gpu_indices": [g["index"] for g in selected],
        "gpu_names": [g["name"] for g in selected],
        "dtype": dtype,
        "bf16": bf16,
        "fp16": fp16,
        "tf32": caps["tf32"],
        "load_in_4bit": load_in_4bit,
        "attn_implementation": attn,
        "batch_size": batch,
        "gradient_accumulation": grad_accum,
        "effective_batch": batch * grad_accum * (len(selected) if strategy == "ddp" else 1),
        "gradient_checkpointing": gradient_checkpointing,
        "optim": optim,
        "max_seq_length": seq_len,
        "torch_compile": caps["backend"] == "cuda" and params_b <= 3,
        "strategy": strategy,
        "params_b": params_b,
        "estimated_weights_gb": round(budget, 1),
        "notes": notes,
    }


# ------------------------------------------------------------------ runtime

def cuda_env_vars(gpu_indices: list[int] | None = None, backend: str | None = None) -> dict:
    """Environment for a training subprocess: allocator, visibility, logging."""
    report = get_accelerator_report()
    backend = backend or report["backend"]
    env: dict[str, str] = {}

    if backend in ("cuda", "rocm"):
        # expandable_segments kills the fragmentation OOMs of long LoRA runs, but
        # the Windows CUDA allocator does not implement it (warns and ignores).
        env["PYTORCH_CUDA_ALLOC_CONF"] = ("garbage_collection_threshold:0.8"
                                          if sys.platform == "win32"
                                          else "expandable_segments:True")
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        if gpu_indices:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in gpu_indices)
        if backend == "rocm":
            env["HIP_VISIBLE_DEVICES"] = env.get("CUDA_VISIBLE_DEVICES", "")
            env["HSA_OVERRIDE_GFX_VERSION"] = os.environ.get("HSA_OVERRIDE_GFX_VERSION", "")
            env = {k: v for k, v in env.items() if v != ""}
    elif backend == "directml":
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    env["TOKENIZERS_PARALLELISM"] = "false"   # silences the fork warning spam
    env["PYTHONUNBUFFERED"] = "1"             # live logs in the Monitor tab
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return env


def apply_runtime_optimizations(deterministic: bool = False) -> dict:
    """Enable the in-process torch fast paths. Safe to call when torch is absent."""
    applied: list[str] = []
    try:
        import torch
    except Exception:
        return {"applied": applied, "backend": "cpu"}

    report = get_accelerator_report()
    caps = report["capabilities"]

    if caps.get("tf32"):
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.set_float32_matmul_precision("high")
            applied.append("tf32")
        except Exception:
            pass

    if caps["backend"] in ("cuda", "rocm") and not deterministic:
        try:
            torch.backends.cudnn.benchmark = True
            applied.append("cudnn.benchmark")
        except Exception:
            pass

    if deterministic:
        try:
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
            applied.append("deterministic")
        except Exception:
            pass

    if caps["backend"] == "cuda":
        try:
            torch.backends.cuda.enable_flash_sdp(True)
            torch.backends.cuda.enable_mem_efficient_sdp(True)
            applied.append("sdp_kernels")
        except Exception:
            pass

    return {"applied": applied, "backend": caps["backend"], "arch": caps.get("arch")}


def empty_cache() -> dict:
    """Free cached blocks on whatever accelerator is active."""
    freed = []
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            freed.append("cuda")
        xpu = getattr(torch, "xpu", None)
        if xpu is not None and xpu.is_available():
            xpu.empty_cache()
            freed.append("xpu")
        mps = getattr(torch, "mps", None)
        if mps is not None and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            mps.empty_cache()
            freed.append("mps")
    except Exception as exc:
        log.warning("empty_cache: %s", exc)
    _CACHE["report"] = None
    return {"freed": freed}
