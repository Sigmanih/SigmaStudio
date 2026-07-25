# ==============================================================================
# core/training/hardware.py — CUDA Hardware & VRAM Telemetry
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""GPU Hardware telemetry, PyTorch CUDA capability detection, multi-GPU
configuration, and driver diagnostic helpers.
"""

import os
import sys
import json
import subprocess
import shutil
from core.logger import get_logger

log = get_logger(__name__)


def _check_torch_cuda() -> dict:
    try:
        import torch
        avail = torch.cuda.is_available()
        count = torch.cuda.device_count() if avail else 0
        gpus = []
        if avail:
            for i in range(count):
                props = torch.cuda.get_device_properties(i)
                tot_mb = round(props.total_memory / (1024**2), 1)
                # Attempt to read allocated memory
                try:
                    used_bytes = torch.cuda.memory_allocated(i)
                    used_mb = round(used_bytes / (1024**2), 1)
                except Exception:
                    used_mb = 0.0
                free_mb = max(0.0, tot_mb - used_mb)
                gpus.append({
                    "index": i,
                    "name": props.name,
                    "vendor": "NVIDIA",
                    "vendor_color": "#76b900" if "NVIDIA" in props.name.upper() else "#00f2fe",
                    "vram_total_mb": tot_mb,
                    "vram_used_mb": used_mb,
                    "vram_free_mb": free_mb,
                    "vram_total_gb": round(tot_mb / 1024, 1),
                    "vram_used_gb": round(used_mb / 1024, 1),
                    "vram_free_gb": round(free_mb / 1024, 1),
                    "vram_pct": round((used_mb / tot_mb) * 100, 1) if tot_mb > 0 else 0,
                    "compute_capability": f"{props.major}.{props.minor}",
                    "compute_cap": f"{props.major}.{props.minor}",
                    "multi_processor_count": getattr(props, "multi_processor_count", 0),
                    "gpu_util_pct": 0.0,
                    "temp_c": 45.0,
                    "power_draw_w": 0.0,
                    "power_limit_w": 0.0,
                })
        return {
            "torch_available": True,
            "cuda_available": avail,
            "cuda_device_count": count,
            "torch_version": torch.__version__,
            "torch_cuda_version": getattr(torch.version, "cuda", None),
            "torch_gpu_list": gpus,
            "cudnn_version": str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else None,
            "cuda_error": None,
        }
    except Exception as e:
        return {
            "torch_available": False,
            "cuda_available": False,
            "cuda_device_count": 0,
            "torch_version": None,
            "torch_cuda_version": None,
            "torch_gpu_list": [],
            "cudnn_version": None,
            "cuda_error": str(e),
        }


def _query_nvidia_smi() -> list[dict]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return []
    try:
        res = subprocess.run(
            [nvidia_smi, "--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version,utilization.gpu,temperature.gpu,power.draw,power.limit,compute_cap", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode != 0:
            return []
        gpus = []
        for line in res.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                tot_mb = float(parts[2])
                used_mb = float(parts[3])
                free_mb = float(parts[4])
                
                util_pct = 0.0
                if len(parts) > 6:
                    try: util_pct = float(parts[6])
                    except ValueError: pass
                
                temp_c = 45.0
                if len(parts) > 7:
                    try: temp_c = float(parts[7])
                    except ValueError: pass
                
                pwr_draw = 0.0
                if len(parts) > 8:
                    try: pwr_draw = float(parts[8])
                    except ValueError: pass
                
                pwr_limit = 0.0
                if len(parts) > 9:
                    try: pwr_limit = float(parts[9])
                    except ValueError: pass

                comp_cap = parts[10] if len(parts) > 10 else "N/A"
                gpu_name = parts[1]
                vendor = "NVIDIA" if "NVIDIA" in gpu_name.upper() else "GPU"
                vendor_color = "#76b900" if "NVIDIA" in gpu_name.upper() else "#00f2fe"

                gpus.append({
                    "index": int(parts[0]),
                    "name": gpu_name,
                    "vendor": vendor,
                    "vendor_color": vendor_color,
                    "vram_total_mb": tot_mb,
                    "vram_used_mb": used_mb,
                    "vram_free_mb": free_mb,
                    "vram_total_gb": round(tot_mb / 1024, 1),
                    "vram_used_gb": round(used_mb / 1024, 1),
                    "vram_free_gb": round(free_mb / 1024, 1),
                    "vram_pct": round((used_mb / tot_mb) * 100, 1) if tot_mb > 0 else 0,
                    "driver_version": parts[5],
                    "compute_cap": comp_cap,
                    "compute_capability": comp_cap,
                    "gpu_util_pct": round(util_pct, 1),
                    "temp_c": round(temp_c, 1),
                    "power_draw_w": round(pwr_draw, 1),
                    "power_limit_w": round(pwr_limit, 1),
                })
        return gpus
    except Exception as exc:
        log.warning("_query_nvidia_smi error: %s", exc)
        return []


def _query_wmi_gpus() -> list[dict]:
    """Query system video controllers (AMD, Intel, NVIDIA) via PowerShell WMI on Windows."""
    if sys.platform != "win32":
        return []
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        if res.returncode != 0 or not res.stdout.strip():
            return []
        
        data = json.loads(res.stdout.strip())
        if isinstance(data, dict):
            data = [data]
            
        gpus = []
        for idx, item in enumerate(data):
            name = item.get("Name") or f"GPU {idx}"
            ram_bytes = item.get("AdapterRAM") or 0
            tot_mb = round(ram_bytes / (1024**2), 1) if ram_bytes > 0 else 2048.0
            driver = item.get("DriverVersion") or "N/A"
            
            vendor = "GPU"
            vendor_color = "#00f2fe"
            name_u = name.upper()
            if "NVIDIA" in name_u:
                vendor = "NVIDIA"
                vendor_color = "#76b900"
            elif "AMD" in name_u or "RADEON" in name_u:
                vendor = "AMD"
                vendor_color = "#ff4444"
            elif "INTEL" in name_u or "ARC" in name_u:
                vendor = "INTEL"
                vendor_color = "#0071c5"

            gpus.append({
                "index": idx,
                "name": name,
                "vendor": vendor,
                "vendor_color": vendor_color,
                "vram_total_mb": tot_mb,
                "vram_used_mb": 0.0,
                "vram_free_mb": tot_mb,
                "vram_total_gb": round(tot_mb / 1024, 1),
                "vram_used_gb": 0.0,
                "vram_free_gb": round(tot_mb / 1024, 1),
                "vram_pct": 0.0,
                "driver_version": driver,
                "compute_cap": "DirectX/WMI",
                "compute_capability": "DirectX/WMI",
                "gpu_util_pct": 0.0,
                "temp_c": 40.0,
                "power_draw_w": 0.0,
                "power_limit_w": 0.0,
            })
        return gpus
    except Exception as exc:
        log.warning("_query_wmi_gpus error: %s", exc)
        return []


def get_hardware_info() -> dict:
    th = sys.modules.get("core.training_handler")
    fn_torch = getattr(th, "_check_torch_cuda", _check_torch_cuda)
    fn_smi = getattr(th, "_query_nvidia_smi", _query_nvidia_smi)
    fn_wmi = getattr(th, "_query_wmi_gpus", _query_wmi_gpus)

    torch_info = fn_torch()
    smi_gpus = fn_smi()
    wmi_gpus = fn_wmi()

    # Merge GPUs: 1) Non-NVIDIA GPUs from WMI (AMD iGPU, Intel, etc.)
    gpus = [g.copy() for g in wmi_gpus if g.get("vendor", "").upper() != "NVIDIA" and "NVIDIA" not in g.get("name", "").upper()]

    # 2) Dedicated NVIDIA GPUs from nvidia-smi (live telemetry)
    if smi_gpus:
        gpus.extend([g.copy() for g in smi_gpus])
    else:
        # Fallback to WMI for NVIDIA if nvidia-smi is not available
        gpus.extend([g.copy() for g in wmi_gpus if g.get("vendor", "").upper() == "NVIDIA" or "NVIDIA" in g.get("name", "").upper()])

    # 3) Fallback to PyTorch list if still empty
    if not gpus and torch_info.get("torch_gpu_list"):
        gpus = [g.copy() for g in torch_info.get("torch_gpu_list")]

    # Re-index GPUs cleanly 0..N-1
    for idx, g in enumerate(gpus):
        g["index"] = idx

    gpu_count = len(gpus)
    total_vram = sum(g.get("vram_total_gb", g.get("vram_gb", 0)) for g in gpus)

    # Detailed System (CPU / RAM / Disk) via psutil
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_total = round(vm.total / (1024**3), 1)
        ram_used = round(vm.used / (1024**3), 1)
        ram_free = round(vm.available / (1024**3), 1)
        ram_pct = round(vm.percent, 1)
        cpu_util = round(psutil.cpu_percent(interval=None), 1)
        cpu_logical = psutil.cpu_count(logical=True) or os.cpu_count() or 4
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical

        disk = psutil.disk_usage("/")
        disk_total = round(disk.total / (1024**3), 1)
        disk_used = round(disk.used / (1024**3), 1)
        disk_pct = round(disk.percent, 1)
    except Exception:
        ram_total, ram_used, ram_free, ram_pct = 16.0, 4.0, 12.0, 25.0
        cpu_util, cpu_logical, cpu_physical = 10.0, os.cpu_count() or 4, 4
        disk_total, disk_used, disk_pct = 500.0, 100.0, 20.0

    return {
        "success": True,
        "hardware": {
            "gpu": gpus,
            "gpu_count": gpu_count,
            "torch_available": torch_info.get("torch_available", False),
            "cuda_available": torch_info.get("cuda_available", False),
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
                "strategy": "device_map auto",
            },
            "cuda_fix": {
                "has_issue": not torch_info.get("cuda_available", False) and gpu_count == 0,
            },
        },
    }


def restart_ollama_service() -> dict:
    """Restart Ollama service or unload models to free VRAM."""
    messages = []
    
    # 1. Clear PyTorch CUDA cache if available
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            messages.append("Cache PyTorch CUDA svuotata")
    except Exception:
        pass

    # 2. Try Ollama CLI stop / model unload
    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        try:
            res = subprocess.run([ollama_bin, "stop"], capture_output=True, text=True, timeout=10)
            messages.append("Servizio/Modelli Ollama arrestati con successo")
        except Exception as exc:
            log.warning("Ollama stop command: %s", exc)

    # 3. HTTP Request to Ollama unload endpoint if Ollama server is running
    try:
        import requests
        requests.post("http://localhost:11434/api/generate", json={"model": "", "keep_alive": 0}, timeout=2)
    except Exception:
        pass

    msg = " • ".join(messages) if messages else "VRAM liberata e cache resettata con successo."
    return {"success": True, "message": msg}


def get_hardware_status() -> dict:
    return get_hardware_info()
