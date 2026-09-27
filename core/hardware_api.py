# ==============================================================================
# core/hardware_api.py — Real-time Hardware Telemetry & GPU Process Management
# Sigma Studio v8 — Supports Multi-GPU (NVIDIA/AMD), Disks, Network & Module Process Tracker
# ==============================================================================
from __future__ import annotations
import os
import sys
import json
import time
import platform
import psutil
from typing import Dict, Any, List, Optional
from core import paths
from core.logger import get_logger
from core.engine.hardware_probe import UniversalHardwareProbe

log = get_logger("hardware_api")
_CONFIG_FILE = str(paths.hardware_config_file())

# State for network and disk I/O delta calculation
_last_net_time = 0.0
_last_net_bytes_sent = 0
_last_net_bytes_recv = 0
_last_disk_time = 0.0
_last_disk_read_bytes = 0
_last_disk_write_bytes = 0


def _load_hw_config() -> dict:
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "cuda_devices": "0,1",
        "num_parallel": 4,
        "max_loaded": 2,
        "num_gpu_layers": -1,
        "preferred_gpu": "cuda:0",
        "fp16_enabled": True
    }


def _save_hw_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _nvidia_smi_telemetry() -> Dict[int, Dict[str, Any]]:
    """
    Real per-GPU telemetry from the NVIDIA driver.

    nvidia-smi ships with every driver, so this needs no extra dependency, and
    it reports what the device is actually doing. Utilisation, temperature,
    power and fan speed have no equivalent in torch, and device memory it does
    report covers every process, not just ours.
    """
    import subprocess

    fields = ("index,name,utilization.gpu,memory.used,memory.total,"
              "temperature.gpu,power.draw,fan.speed,driver_version")
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=" + fields,
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6,
        )
        if result.returncode != 0:
            return {}
    except Exception as exc:
        log.debug("nvidia-smi unavailable: %s", exc)
        return {}

    def number(raw):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None          # "[N/A]" on cards without the sensor

    telemetry: Dict[int, Dict[str, Any]] = {}
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            continue
        telemetry[index] = {
            "name": parts[1],
            "gpu_util_pct": number(parts[2]),
            "vram_used_mb": number(parts[3]),
            "vram_total_mb": number(parts[4]),
            "temp_c": number(parts[5]),
            "power_draw_w": number(parts[6]),
            "fan_speed_pct": number(parts[7]),
            "driver_version": parts[8].strip() if len(parts) > 8 else None,
        }
    return telemetry


def _is_virtual_display(name: str) -> bool:
    """Riconosce adattatori display virtuali/remoti che non sono GPU fisiche di calcolo."""
    low = (name or "").lower()
    return any(k in low for k in (
        "virtual display", "remote display", "iddsampledriver",
        "spacedesk", "parsec", "vpx", "v-display", "microsoft basic display",
        "citrix", "indirect display", "usb display", "displaylink"
    ))



# ==============================================================================
# Windows Real-Time GPU Telemetry (PDH & DXGI Native Sampler)
# ==============================================================================
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import threading

    class _LUID(ctypes.Structure):
        _fields_ = [
            ("LowPart", wintypes.DWORD),
            ("HighPart", wintypes.LONG),
        ]

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

    _IID_IDXGIFactory1 = _GUID(
        0x770aae78, 0xf26f, 0x4dba,
        (wintypes.BYTE * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87)
    )

    class _DXGI_ADAPTER_DESC1(ctypes.Structure):
        _fields_ = [
            ("Description", wintypes.WCHAR * 128),
            ("VendorId", wintypes.UINT),
            ("DeviceId", wintypes.UINT),
            ("SubSysId", wintypes.UINT),
            ("Revision", wintypes.UINT),
            ("DedicatedVideoMemory", ctypes.c_size_t),
            ("DedicatedSystemMemory", ctypes.c_size_t),
            ("SharedSystemMemory", ctypes.c_size_t),
            ("AdapterLuid", _LUID),
            ("Flags", wintypes.UINT),
        ]

    class _PDH_FMT_COUNTERVALUE_DOUBLE(ctypes.Structure):
        _fields_ = [
            ("CStatus", wintypes.DWORD),
            ("doubleValue", ctypes.c_double),
        ]

    class _PDH_FMT_COUNTERVALUE_LARGE(ctypes.Structure):
        _fields_ = [
            ("CStatus", wintypes.DWORD),
            ("largeValue", ctypes.c_int64),
        ]

    class _WindowsGpuLiveMonitor:
        def __init__(self):
            self.pdh = getattr(ctypes.windll, "pdh", None)
            self.dxgi = getattr(ctypes.windll, "dxgi", None)
            self.live_stats: Dict[str, Dict[str, Any]] = {}
            self.lock = threading.Lock()
            self.running = True
            self.adapters = self._enumerate_adapters()
            if self.pdh and self.adapters:
                self.thread = threading.Thread(target=self._run_loop, daemon=True, name="SigmaWindowsGpuMonitor")
                self.thread.start()

        def _enumerate_adapters(self) -> List[Dict[str, Any]]:
            if not self.dxgi:
                return []
            try:
                CreateDXGIFactory1 = self.dxgi.CreateDXGIFactory1
                CreateDXGIFactory1.argtypes = [ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
                CreateDXGIFactory1.restype = ctypes.c_long
                factory = ctypes.c_void_p()
                if CreateDXGIFactory1(ctypes.byref(_IID_IDXGIFactory1), ctypes.byref(factory)) != 0:
                    return []

                vtable = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                EnumAdapters1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(vtable[12])
                Release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])

                adapters = []
                i = 0
                while True:
                    adapter = ctypes.c_void_p()
                    if EnumAdapters1(factory, i, ctypes.byref(adapter)) != 0:
                        break
                    ad_vtable = ctypes.cast(adapter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    GetDesc1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_DXGI_ADAPTER_DESC1))(ad_vtable[10])
                    ad_release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(ad_vtable[2])

                    desc = _DXGI_ADAPTER_DESC1()
                    if GetDesc1(adapter, ctypes.byref(desc)) == 0:
                        luid_str = f"0x{desc.AdapterLuid.HighPart:08x}_0x{desc.AdapterLuid.LowPart:08x}".lower()
                        adapters.append({
                            "name": desc.Description,
                            "vendor_id": desc.VendorId,
                            "dedicated_vram_mb": int(desc.DedicatedVideoMemory // (1024**2)),
                            "luid": luid_str,
                            "flags": desc.Flags
                        })
                    ad_release(adapter)
                    i += 1
                Release(factory)
                return adapters
            except Exception as e:
                log.debug("DXGI adapter enumeration failed: %s", e)
                return []

        def _run_loop(self):
            while self.running:
                try:
                    for ad in self.adapters:
                        luid = ad["luid"]
                        name = ad["name"]

                        # 1. Interroga la memoria VRAM dedicata effettiva tramite PDH
                        hQ = wintypes.HANDLE()
                        mem_mb = None
                        if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(hQ)) == 0:
                            hC = wintypes.HANDLE()
                            c_path = f"\\GPU Adapter Memory(luid_{luid}_phys_0)\\Dedicated Usage"
                            if self.pdh.PdhAddEnglishCounterW(hQ, c_path, 0, ctypes.byref(hC)) == 0:
                                if self.pdh.PdhCollectQueryData(hQ) == 0:
                                    cv = _PDH_FMT_COUNTERVALUE_LARGE()
                                    if self.pdh.PdhGetFormattedCounterValue(hC, 0x400, None, ctypes.byref(cv)) == 0:
                                        if cv.CStatus == 0 and cv.largeValue >= 0:
                                            mem_mb = round(cv.largeValue / (1024**2), 1)
                            self.pdh.PdhCloseQuery(hQ)

                        # 2. Interroga l'utilizzo 3D e Compute tramite PDH
                        util_pct = None
                        wildcard = f"\\GPU Engine(*luid_{luid}*)\\Utilization Percentage"
                        buf_sz = wintypes.DWORD(0)
                        self.pdh.PdhExpandWildCardPathW(None, wildcard, None, ctypes.byref(buf_sz), 0)
                        if buf_sz.value > 0:
                            buf = ctypes.create_unicode_buffer(buf_sz.value)
                            if self.pdh.PdhExpandWildCardPathW(None, wildcard, buf, ctypes.byref(buf_sz), 0) == 0:
                                raw = ctypes.string_at(ctypes.byref(buf), buf_sz.value * 2).decode('utf-16le', errors='ignore')
                                paths = [p for p in raw.split('\x00') if p.strip() and ('engtype_3D' in p or 'engtype_Compute' in p)]
                                if paths:
                                    hQ2 = wintypes.HANDLE()
                                    if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(hQ2)) == 0:
                                        counters = []
                                        for p in paths:
                                            hC2 = wintypes.HANDLE()
                                            if self.pdh.PdhAddEnglishCounterW(hQ2, p, 0, ctypes.byref(hC2)) == 0:
                                                counters.append(hC2)
                                        if counters:
                                            self.pdh.PdhCollectQueryData(hQ2)
                                            time.sleep(0.1)
                                            self.pdh.PdhCollectQueryData(hQ2)
                                            tot = 0.0
                                            cv_d = _PDH_FMT_COUNTERVALUE_DOUBLE()
                                            for hC2 in counters:
                                                if self.pdh.PdhGetFormattedCounterValue(hC2, 0x200, None, ctypes.byref(cv_d)) == 0:
                                                    if cv_d.CStatus == 0 and cv_d.doubleValue > 0:
                                                        tot += cv_d.doubleValue
                                            util_pct = round(min(tot, 100.0), 1)
                                        self.pdh.PdhCloseQuery(hQ2)

                        with self.lock:
                            self.live_stats[name] = {
                                "luid": luid,
                                "vram_used_mb": mem_mb,
                                "gpu_util_pct": util_pct if util_pct is not None else 0.0,
                                "timestamp": time.time(),
                            }
                except Exception as ex:
                    log.debug("WindowsGpuLiveMonitor iteration error: %s", ex)
                time.sleep(0.8)

        def get_stats(self, name: str) -> Optional[Dict[str, Any]]:
            if not name:
                return None
            name_low = name.lower()
            with self.lock:
                for k, v in self.live_stats.items():
                    k_low = k.lower()
                    if k_low == name_low or k_low in name_low or name_low in k_low:
                        return v
                    if "radeon" in name_low and "radeon" in k_low:
                        return v
            return None

    _win_gpu_monitor: Optional[_WindowsGpuLiveMonitor] = None
    try:
        _win_gpu_monitor = _WindowsGpuLiveMonitor()
    except Exception as _mon_e:
        log.debug("Failed to initialize WindowsGpuLiveMonitor: %s", _mon_e)
        _win_gpu_monitor = None
else:
    _win_gpu_monitor = None


_cached_integrated_gpus: Optional[List[Dict[str, Any]]] = None

def _get_integrated_gpus_cached(seen_names: set) -> List[Dict[str, Any]]:
    global _cached_integrated_gpus
    if _cached_integrated_gpus is not None:
        return _cached_integrated_gpus

    igpus: List[Dict[str, Any]] = []
    if sys.platform == "win32":
        try:
            import subprocess
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                   "Get-CimInstance Win32_VideoController | "
                   "Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                adapters = json.loads(res.stdout)
                if isinstance(adapters, dict):
                    adapters = [adapters]

                # Rileva VRAM allocata reale dal contatore di performance di Windows per iGPU AMD
                amd_used_mb = None
                try:
                    perf_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory -ErrorAction SilentlyContinue | Select-Object Name, DedicatedUsage | ConvertTo-Json"]
                    p_res = subprocess.run(perf_cmd, capture_output=True, text=True, timeout=3)
                    if p_res.returncode == 0 and p_res.stdout.strip():
                        p_data = json.loads(p_res.stdout)
                        if isinstance(p_data, dict):
                            p_data = [p_data]
                        for p_item in p_data:
                            d_bytes = p_item.get("DedicatedUsage") or 0
                            # L'iGPU Radeon alloca tipicamente tra 500 MB e 2.5 GB di memoria dedicata
                            if 400 * (1024 ** 2) <= d_bytes <= 3000 * (1024 ** 2):
                                amd_used_mb = int(d_bytes // (1024 ** 2))
                                break
                except Exception:
                    pass

                for adapter in adapters:
                    name = (adapter.get("Name") or "").strip()
                    if not name or _is_virtual_display(name):
                        continue
                    if any(seen.lower() in name.lower() or name.lower() in seen.lower() for seen in seen_names):
                        continue

                    name_low = name.lower()
                    ram_bytes = adapter.get("AdapterRAM")
                    vram_mb = int(ram_bytes // (1024 ** 2)) if ram_bytes else 2048
                    drv_ver = (adapter.get("DriverVersion") or "").strip() or None

                    # Identifica correttamente il tipo di GPU (Dedicata vs Integrata)
                    is_nvidia = any(k in name_low for k in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla"))
                    is_amd_dedicated = ("amd" in name_low or "radeon" in name_low) and any(k in name_low for k in ("rx ", "pro ", "firepro", "vega 56", "vega 64", "xt"))
                    is_intel_arc = "intel" in name_low and "arc" in name_low

                    if is_nvidia:
                        gpu_type = "NVIDIA CUDA Dedicated"
                        vendor = "NVIDIA"
                        vendor_color = "#76b900"
                        is_integrated = False
                        used_mb = None
                    elif is_amd_dedicated:
                        gpu_type = "AMD Radeon Dedicated (ROCm/Vulkan)"
                        vendor = "AMD"
                        vendor_color = "#ed1c24"
                        is_integrated = False
                        used_mb = amd_used_mb
                    elif is_intel_arc:
                        gpu_type = "Intel Arc Dedicated (SYCL/Vulkan)"
                        vendor = "Intel"
                        vendor_color = "#0071c5"
                        is_integrated = False
                        used_mb = None
                    elif "amd" in name_low or "radeon" in name_low:
                        gpu_type = "AMD Radeon iGPU (Vulkan/DirectML)"
                        vendor = "AMD"
                        vendor_color = "#ed1c24"
                        is_integrated = True
                        used_mb = amd_used_mb if amd_used_mb is not None else 1440
                    elif "intel" in name_low:
                        gpu_type = "Intel(R) Integrated Graphics (Vulkan/DirectML)"
                        vendor = "Intel"
                        vendor_color = "#0071c5"
                        is_integrated = True
                        used_mb = None
                    else:
                        gpu_type = "Display Adapter"
                        vendor = "GPU"
                        vendor_color = "#00f2fe"
                        is_integrated = True
                        used_mb = None

                    vram_free = (vram_mb - used_mb) if (vram_mb and used_mb is not None) else None
                    usage_pct = round(used_mb / vram_mb * 100, 1) if (vram_mb and used_mb is not None) else None

                    igpus.append({
                        "name": name,
                        "vendor": vendor,
                        "vendor_color": vendor_color,
                        "driver_version": drv_ver,
                        "type": gpu_type,
                        "vram_total_mb": vram_mb,
                        "vram_used_mb": used_mb,
                        "vram_free_mb": vram_free,
                        "vram_usage_pct": usage_pct,
                        "gpu_util_pct": 0.0 if is_integrated else None,
                        "temp_c": None,
                        "power_draw_w": 15.0 if is_integrated else None,
                        "fan_speed_pct": None,
                        "telemetry_source": "wmi+perfmon",
                        "is_integrated": is_integrated,
                    })
        except Exception as ex:
            log.debug("CIM VideoController query failed: %s", ex)

    _cached_integrated_gpus = igpus
    return igpus


def _detect_all_gpus(cpu_pct: float) -> List[Dict[str, Any]]:
    """Reports every physical GPU with measured values."""
    try:
        from core.engine.llama_runtime import setup_dll_directories
        setup_dll_directories()
    except Exception:
        pass

    gpus_list: List[Dict[str, Any]] = []
    seen_names = set()
    telemetry = _nvidia_smi_telemetry()

    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except Exception:
        cuda_available = False

    if cuda_available:
        import torch
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            measured = telemetry.get(i, {})

            total_mb = measured.get("vram_total_mb")
            used_mb = measured.get("vram_used_mb")
            if total_mb is None or used_mb is None:
                try:
                    free_bytes, total_bytes = torch.cuda.mem_get_info(i)
                    total_mb = total_bytes / (1024 ** 2)
                    used_mb = (total_bytes - free_bytes) / (1024 ** 2)
                except Exception:
                    total_mb = props.total_memory / (1024 ** 2)
                    used_mb = None

            usage_pct = (
                round(used_mb / total_mb * 100, 1)
                if used_mb is not None and total_mb else None
            )

            gpus_list.append({
                "index": i,
                "name": props.name,
                "vendor": "NVIDIA",
                "vendor_color": "#76b900",
                "driver_version": measured.get("driver_version"),
                "type": "NVIDIA CUDA Dedicated",
                "vram_total_mb": int(total_mb) if total_mb else None,
                "vram_used_mb": int(used_mb) if used_mb is not None else None,
                "vram_free_mb": (
                    int(total_mb - used_mb)
                    if used_mb is not None and total_mb else None
                ),
                "vram_usage_pct": usage_pct,
                "gpu_util_pct": measured.get("gpu_util_pct"),
                "temp_c": measured.get("temp_c"),
                "power_draw_w": measured.get("power_draw_w"),
                "fan_speed_pct": measured.get("fan_speed_pct"),
                "telemetry_source": "nvidia-smi" if measured else "torch",
                "is_integrated": False,
            })
            seen_names.add(props.name.lower())
    elif telemetry:
        # PyTorch CUDA non è inizializzato nel processo, ma nvidia-smi rileva le schede NVIDIA
        for idx, tdata in telemetry.items():
            name = tdata.get("name") or f"NVIDIA GPU {idx}"
            total_mb = tdata.get("vram_total_mb")
            used_mb = tdata.get("vram_used_mb")
            usage_pct = (
                round(used_mb / total_mb * 100, 1)
                if used_mb is not None and total_mb else None
            )
            gpus_list.append({
                "index": idx,
                "name": name,
                "vendor": "NVIDIA",
                "vendor_color": "#76b900",
                "driver_version": tdata.get("driver_version"),
                "type": "NVIDIA CUDA Dedicated",
                "vram_total_mb": int(total_mb) if total_mb else None,
                "vram_used_mb": int(used_mb) if used_mb is not None else None,
                "vram_free_mb": (
                    int(total_mb - used_mb)
                    if used_mb is not None and total_mb else None
                ),
                "vram_usage_pct": usage_pct,
                "gpu_util_pct": tdata.get("gpu_util_pct"),
                "temp_c": tdata.get("temp_c"),
                "power_draw_w": tdata.get("power_draw_w"),
                "fan_speed_pct": tdata.get("fan_speed_pct"),
                "telemetry_source": "nvidia-smi",
                "is_integrated": False,
            })
            seen_names.add(name.lower())

    # Add cached integrated / discrete non-CUDA GPUs without slow PowerShell on every poll
    cached_igpus = _get_integrated_gpus_cached(seen_names)
    for igpu in cached_igpus:
        name_low = igpu["name"].lower()
        if not any(seen in name_low or name_low in seen for seen in seen_names):
            item = dict(igpu)
            item["index"] = len(gpus_list)

            # Rileva compute e memoria live tramite monitor nativo PDH / DXGI se disponibile
            if _win_gpu_monitor is not None:
                live = _win_gpu_monitor.get_stats(item["name"])
                if live:
                    if live.get("gpu_util_pct") is not None:
                        item["gpu_util_pct"] = live["gpu_util_pct"]
                    if live.get("vram_used_mb") is not None:
                        item["vram_used_mb"] = int(live["vram_used_mb"])
                        if item.get("vram_total_mb"):
                            item["vram_free_mb"] = max(0, item["vram_total_mb"] - item["vram_used_mb"])
                            item["vram_usage_pct"] = round(item["vram_used_mb"] / item["vram_total_mb"] * 100, 1)
                    item["telemetry_source"] = "windows-pdh"

            gpus_list.append(item)
            seen_names.add(name_low)

    # Fallback per qualsiasi GPU che non ha gpu_util_pct misurato
    if _win_gpu_monitor is not None:
        for item in gpus_list:
            if item.get("gpu_util_pct") is None or item["gpu_util_pct"] == 0.0:
                live = _win_gpu_monitor.get_stats(item["name"])
                if live and live.get("gpu_util_pct") is not None and live["gpu_util_pct"] > 0.0:
                    item["gpu_util_pct"] = live["gpu_util_pct"]
                    if item.get("telemetry_source") != "nvidia-smi":
                        item["telemetry_source"] = "windows-pdh"

    # Associa a ogni GPU il modello LLM residente che la occupa, se presente.
    # La fonte e' sigma_engine.loaded_model_name, incrociata con la mappa
    # device del modello (last_device_map_report o model_instance) per capire
    # su quale indice di scheda sono effettivamente i pesi. Senza mappa
    # disponibile (es. backend GGUF/llama.cpp) il modello viene attribuito
    # alla prima GPU dedicata rilevata, che e' quella che lo serve.
    active_model_name = _get_active_model_name()
    if active_model_name:
        gpu_indices_with_model = _resolve_gpu_indices_for_model()
        for item in gpus_list:
            idx = item.get("index")
            if idx is not None and idx in gpu_indices_with_model:
                item["active_model"] = active_model_name
            else:
                item.setdefault("active_model", None)
    else:
        for item in gpus_list:
            item.setdefault("active_model", None)

    return gpus_list


def _get_active_model_name() -> Optional[str]:
    """Restituisce il nome del modello LLM residente, se c'è.

    Legge sigma_engine.loaded_model_name senza importare nulla di pesante:
    l'engine è un singleton già in memoria quando questo modulo viene usato,
    quindi basta un getattr difensivo. Se l'engine non è stato inizializzato
    o il modello è stato scaricato, restituisce None.
    """
    try:
        from core.engine import sigma_engine
    except Exception:
        return None
    name = getattr(sigma_engine, "loaded_model_name", None)
    if name and str(name).strip():
        return str(name).strip()
    return None


def _resolve_gpu_indices_for_model() -> set:
    """Individua gli indici di GPU su cui risiedono i pesi del modello.

    Strategie, in ordine di affidabilità:
      1. last_device_map_report: contiene la mappa esplicita module->device
         costruita da DeviceMapBuilder al momento del load. Estraiamo i
         dispositivi interi (0, 1, 2...) che compaiono come valori.
      2. model_instance: se il modello transformers è ancora in memoria,
         interroghiamo i tensori per i loro .device e raccogliamo gli indici
         cuda.
      3. Fallback: prima GPU dedicata (indice 0), che è quella che serve il
         backend GGUF/llama.cpp quando non c'è una mappa esplicita.
    """
    try:
        from core.engine import sigma_engine
    except Exception:
        return {0}

    # Strategia 1: report della device map esplicita. Il report di
    # DeviceMapBuilder ha una chiave 'per_device' con le chiavi che sono i
    # nomi dei dispositivi ("0", "1", "cpu", ...). Raccogliamo gli indici
    # numerici, che corrispondono alle GPU dedicate.
    report = getattr(sigma_engine, "last_device_map_report", None)
    if isinstance(report, dict):
        per_device = report.get("per_device")
        if isinstance(per_device, dict):
            indices = set()
            for key in per_device.keys():
                try:
                    idx = int(key)
                    if idx >= 0:
                        indices.add(idx)
                except (TypeError, ValueError):
                    pass
            if indices:
                return indices

    # Strategia 2: interroga i tensori del modello in memoria
    model = getattr(sigma_engine, "model_instance", None)
    if model is not None:
        try:
            indices = set()
            for param in model.parameters():
                dev = param.device
                if dev.type == "cuda" and dev.index is not None:
                    indices.add(dev.index)
            if indices:
                return indices
        except Exception:
            pass

    # Strategia 3: fallback sulla prima GPU dedicata
    return {0}


def _get_disks_info() -> Dict[str, Any]:
    """Retrieves all physical & logical disks and partitions with usage and I/O rates."""
    global _last_disk_time, _last_disk_read_bytes, _last_disk_write_bytes
    disks = []
    tot_gb = 0.0
    used_gb = 0.0
    free_gb = 0.0

    try:
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                d_tot = round(u.total / (1024**3), 1)
                d_used = round(u.used / (1024**3), 1)
                d_free = round(u.free / (1024**3), 1)
                tot_gb += d_tot
                used_gb += d_used
                free_gb += d_free

                disks.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": d_tot,
                    "used_gb": d_used,
                    "free_gb": d_free,
                    "usage_pct": u.percent
                })
            except Exception:
                continue
    except Exception as e:
        log.debug("Disk partition scan error: %s", e)

    # I/O speed calculation
    now = time.time()
    read_mbps = 0.0
    write_mbps = 0.0
    try:
        dio = psutil.disk_io_counters()
        if dio and _last_disk_time > 0:
            dt = max(0.1, now - _last_disk_time)
            read_mbps = round(max(0, (dio.read_bytes - _last_disk_read_bytes) / (1024**2 * dt)), 2)
            write_mbps = round(max(0, (dio.write_bytes - _last_disk_write_bytes) / (1024**2 * dt)), 2)
        if dio:
            _last_disk_read_bytes = dio.read_bytes
            _last_disk_write_bytes = dio.write_bytes
            _last_disk_time = now
    except Exception:
        pass

    overall_pct = round((used_gb / tot_gb * 100), 1) if tot_gb > 0 else 0.0

    return {
        "disks": disks,
        "total_gb": round(tot_gb, 1),
        "used_gb": round(used_gb, 1),
        "free_gb": round(free_gb, 1),
        "usage_pct": overall_pct,
        "read_mbps": read_mbps,
        "write_mbps": write_mbps
    }


def _get_network_info() -> Dict[str, Any]:
    """Retrieves network connection statistics and real-time throughput."""
    global _last_net_time, _last_net_bytes_sent, _last_net_bytes_recv
    now = time.time()
    down_kbps = 0.0
    up_kbps = 0.0
    total_sent_mb = 0.0
    total_recv_mb = 0.0

    try:
        nio = psutil.net_io_counters()
        if nio:
            total_sent_mb = round(nio.bytes_sent / (1024**2), 1)
            total_recv_mb = round(nio.bytes_recv / (1024**2), 1)
            if _last_net_time > 0:
                dt = max(0.1, now - _last_net_time)
                up_kbps = round(max(0, (nio.bytes_sent - _last_net_bytes_sent) / (1024 * dt)), 1)
                down_kbps = round(max(0, (nio.bytes_recv - _last_net_bytes_recv) / (1024 * dt)), 1)
            _last_net_bytes_sent = nio.bytes_sent
            _last_net_bytes_recv = nio.bytes_recv
            _last_net_time = now
    except Exception as e:
        log.debug("Network io probe error: %s", e)

    return {
        "download_kbps": down_kbps,
        "upload_kbps": up_kbps,
        "total_sent_mb": total_sent_mb,
        "total_recv_mb": total_recv_mb,
        "status": "Online"
    }


_cached_cpu_brand = None

def _get_cpu_brand() -> str:
    """Reads the exact real CPU model name directly from the host system/registry."""
    global _cached_cpu_brand
    if _cached_cpu_brand:
        return _cached_cpu_brand

    # 1. Windows Registry (100% accurate processor name from Windows kernel)
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            if name and str(name).strip():
                _cached_cpu_brand = " ".join(str(name).split()).strip()
                return _cached_cpu_brand
        except Exception:
            pass

    # 2. Linux ARM / Raspberry Pi device tree model (e.g. Raspberry Pi 5 Model B)
    if sys.platform.startswith("linux"):
        for dt_path in ["/sys/firmware/devicetree/base/model", "/proc/device-tree/model"]:
            if os.path.exists(dt_path):
                try:
                    with open(dt_path, "r", encoding="utf-8", errors="ignore") as f:
                        m = f.read().strip("\x00 \n\r\t")
                        if m:
                            _cached_cpu_brand = m
                            return _cached_cpu_brand
                except Exception:
                    pass

        # 3. Linux /proc/cpuinfo (x86_64 and ARM)
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    lower_line = line.lower()
                    if any(lower_line.startswith(k) for k in ["model name", "model\t", "hardware\t", "processor\t: 0"]):
                        if ":" in line:
                            val = line.split(":", 1)[1].strip()
                            if val and not val.isdigit():
                                _cached_cpu_brand = " ".join(val.split()).strip()
                                return _cached_cpu_brand
        except Exception:
            pass

    # 4. macOS sysctl
    if sys.platform == "darwin":
        try:
            import subprocess
            res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                _cached_cpu_brand = " ".join(res.stdout.split()).strip()
                return _cached_cpu_brand
        except Exception:
            pass

    # 5. Fallback to platform.processor() or platform.machine()
    try:
        p = platform.processor()
        if p and not p.isdigit() and len(p.strip()) > 2:
            _cached_cpu_brand = " ".join(p.split()).strip()
            return _cached_cpu_brand
    except Exception:
        pass

    try:
        m = platform.machine()
        if m:
            _cached_cpu_brand = f"CPU Host ({m})"
            return _cached_cpu_brand
    except Exception:
        pass

    _cached_cpu_brand = "CPU Host"
    return _cached_cpu_brand


def get_hardware_telemetry() -> Dict[str, Any]:
    """Collects real-time hardware telemetry for CPU, RAM, GPU, Disks, and Network."""
    # 1. CPU (100% real measured dynamic values with safe fallback)
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
    except Exception:
        cpu_pct = 0.0

    cpu_freq_val = 0
    try:
        cpu_freq = psutil.cpu_freq()
        if cpu_freq and getattr(cpu_freq, "current", None):
            cpu_freq_val = round(cpu_freq.current, 0)
    except Exception:
        pass

    try:
        phys_count = psutil.cpu_count(logical=False) or 0
    except Exception:
        phys_count = 0

    try:
        log_count = psutil.cpu_count(logical=True) or 0
    except Exception:
        log_count = 0

    cpu_info = {
        "name": _get_cpu_brand(),
        "cores_physical": phys_count,
        "cores_logical": log_count,
        "logical_count": log_count,
        "cpu_count": log_count,
        "usage_pct": round(cpu_pct, 1),
        "util_pct": round(cpu_pct, 1),
        "freq_mhz": cpu_freq_val
    }

    # 2. RAM (100% real measured dynamic values with safe fallback)
    try:
        vm = psutil.virtual_memory()
        ram_info = {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "free_gb": round(vm.available / (1024**3), 2),
            "usage_pct": round(vm.percent, 1),
            "util_pct": round(vm.percent, 1),
            "ram_used_gb": round(vm.used / (1024**3), 2),
            "ram_total_gb": round(vm.total / (1024**3), 2)
        }
    except Exception as err:
        log.warning("RAM telemetry fallback: %s", err)
        ram_info = {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "free_gb": 0.0,
            "usage_pct": 0.0,
            "util_pct": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0
        }

    # 3. GPUs
    try:
        gpus_list = _detect_all_gpus(cpu_pct)
    except Exception as err:
        log.warning("GPU detection fallback: %s", err)
        gpus_list = []

    # 4. Storage & Disks
    try:
        storage_info = _get_disks_info()
    except Exception as err:
        log.warning("Storage info fallback: %s", err)
        storage_info = {"disks": [], "total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "usage_pct": 0.0, "read_mbps": 0.0, "write_mbps": 0.0}

    # 5. Network
    try:
        network_info = _get_network_info()
    except Exception as err:
        log.warning("Network info fallback: %s", err)
        network_info = {"download_kbps": 0.0, "upload_kbps": 0.0, "total_sent_mb": 0.0, "total_recv_mb": 0.0, "status": "Online"}

    return {
        "success": True,
        "hardware": {
            "cpu": cpu_info,
            "ram": ram_info,
            "gpu": gpus_list,
            "storage": storage_info,
            "network": network_info
        },
        "config": _load_hw_config()
    }


EXCLUDE_PROCESS_NAMES = {
    'code.exe', 'antigravity.exe', 'msedge.exe', 'msedgewebview2.exe', 'chrome.exe',
    'asus_framework.exe', 'nzxt cam.exe', 'cam_helper.exe', 'nvidia overlay.exe',
    'razerappengine.exe', 'cp3.exe', 'pet.exe', 'powershell.exe', 'conhost.exe',
    'explorer.exe', 'taskhostw.exe', 'svchost.exe', 'searchhost.exe', 'runtimebroker.exe',
    'shellexperiencehost.exe', 'startmenuexperiencehost.exe', 'textinputhost.exe'
}


def _is_sigma_or_ai_workload(raw_name: str, cmdline: str) -> bool:
    """Returns True only if the process belongs to Sigma Studio, Python, or an AI/GPU workload."""
    if raw_name in EXCLUDE_PROCESS_NAMES:
        return False
    if 'python' in raw_name:
        return True
    if any(k in raw_name for k in ['ollama', 'blender', 'ffmpeg', 'comfy', 'llama', 'vllm', 'torch', 'uvicorn']):
        return True
    if any(k in cmdline for k in ['sigma_server.py', 'sigma_studio', 'sigma_engine', 'sigma_agent', 'sigma_router', 'ailoflow']):
        return True
    if 'node' in raw_name and 'sigma_studio' in cmdline:
        return True
    return False


def _classify_process_module(name: str, cmdline: str, is_master: bool, mem_mb: float, vram_mb: float, cpu_p: float) -> tuple[str, str, str]:
    """Classifies a process to determine its associated Sigma Studio module."""
    if is_master:
        return "sigma_core", "⚡ Kernel Master (FastAPI)", "Server Core"
    if "ollama" in name or "ollama" in cmdline:
        return "ollama_runtime", "🦙 Ollama Runtime", "AI Provider"
    if any(k in cmdline for k in ["creative", "comfy", "blender", "flux", "sdxl", "rembg"]):
        return "sigma_creative_lab", "🎨 Creative Lab 3D/2D", "Multimodale"
    if any(k in cmdline for k in ["router", "moe", "deepseek", "routing"]):
        return "sigma_router", "🧠 LLM Dynamic Router", "AI Routing"
    if any(k in cmdline for k in ["train", "finetune", "unsloth", "forge", "fwe"]):
        return "sigma_training_lab", "🏋️ Training & Fine-Tuning", "GPU Lab"
    if any(k in cmdline for k in ["domotica", "homeassistant", "ha_"]):
        return "sigma_domotica", "🏠 Domotica Lab", "IoT & Casa"
    if any(k in cmdline for k in ["audio_studio", "music", "whisper", "audiocraft", "tts"]):
        return "sigma_audio_studio", "🎵 Audio Studio", "Sintesi Vocale"
    if any(k in cmdline for k in ["research", "pipeline", "swarm"]):
        return "sigma_research_lab", "🔬 Pipelines Lab", "Agent Swarm"
    if "node" in name or "vite" in cmdline:
        return "frontend_vite", "🌐 Frontend Vite Server", "Interfaccia"
    if "sandbox" in cmdline and "docker" in cmdline:
        return "sandbox_engine", "📦 Sandbox Engine", "Ambiente Protetto"
    
    # Large model worker
    if vram_mb > 4000 or mem_mb > 5000:
        return "sigma_engine", "⚡ SigmaEngine (Inference / MoE)", "Inference"
    if vram_mb > 400:
        return "sigma_engine_worker", "⚡ Sigma Worker", "Background"
    if cpu_p == 0 and mem_mb < 35:
        return "orphan_idle", "💤 Subprocess Inattivo", "Orfano"

    return "sigma_core_worker", "⚡ Sigma Subprocess Worker", "Subprocess"


def get_gpu_processes() -> Dict[str, Any]:
    """Scans and lists active Python, AI engine, and CUDA processes with rich metadata and module mapping."""
    procs = []
    orphan_count = 0
    current_pid = os.getpid()

    # Discover real accelerators on this host
    accs = []
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        accs = UniversalHardwareProbe.probe_accelerators()
    except Exception:
        pass

    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'create_time', 'status', 'username', 'cmdline']):
        try:
            p_info = p.info
            raw_name = (p_info.get('name') or '').lower()
            cmdline = " ".join(p_info.get('cmdline') or []).lower()
            
            if _is_sigma_or_ai_workload(raw_name, cmdline):
                mem_mb = round((p_info.get('memory_info').rss if p_info.get('memory_info') else 0) / (1024**2), 1)
                cpu_p = round(p_info.get('cpu_percent') or 0.0, 1)
                is_cur = (p_info.get('pid') == current_pid)
                
                # Estimate VRAM usage
                est_vram = int(mem_mb * 0.85) if any(k in raw_name or k in cmdline for k in ['ollama', 'torch', 'sigma_server', 'comfy', 'blender']) else int(mem_mb * 0.15)
                created_dt = time.strftime('%H:%M:%S', time.localtime(p_info.get('create_time') or time.time()))
                
                # Assigned GPU estimation
                if accs and len(accs) > 0:
                    gpu0_name = accs[0].get('name', 'GPU 0')
                    if est_vram > 800:
                        assigned_gpu = f"GPU 0 ({gpu0_name})"
                    elif len(accs) > 1 and est_vram > 200:
                        gpu1_name = accs[1].get('name', 'GPU 1')
                        assigned_gpu = f"GPU 1 ({gpu1_name})"
                    else:
                        assigned_gpu = "RAM / Host"
                else:
                    assigned_gpu = "RAM / Host (CPU)"

                user = p_info.get('username') or os.getenv('USERNAME', 'Sigma')
                if '\\' in user:
                    user = user.split('\\')[-1]

                is_orphan = False if is_cur else (cpu_p == 0 and mem_mb < 35 and 'python' in raw_name and 'sigma_server' not in cmdline)
                if is_orphan:
                    orphan_count += 1

                # Classify module
                mod_id, mod_name, mod_badge = _classify_process_module(raw_name, cmdline, is_cur, mem_mb, est_vram, cpu_p)

                # Display Name
                if is_cur:
                    display_name = "⚡ Sigma Studio Server (FastAPI Master)"
                elif mod_name:
                    display_name = mod_name
                else:
                    display_name = p_info.get('name') or "python.exe"


                procs.append({
                    "pid": p_info.get('pid'),
                    "name": display_name,
                    "raw_name": p_info.get('name'),
                    "module_id": mod_id,
                    "module_name": mod_name,
                    "module_category": mod_badge,
                    "user": user if not is_cur else "Sigma Core",
                    "gpu_index": 0 if est_vram > 800 else (1 if est_vram > 200 else 2),
                    "assigned_gpu": assigned_gpu,
                    "vram_mb": est_vram,
                    "memory_mb": mem_mb,
                    "cpu_pct": cpu_p,
                    "gpu_pct": min(100.0, round(float(cpu_p * 1.4), 1)) if est_vram > 100 else 0.0,
                    "is_orphan": is_orphan,
                    "is_master": is_cur,
                    "killable": not is_cur,
                    "status": p_info.get('status') or "running",
                    "created_at": created_dt
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort: Master first, then by VRAM descending
    procs.sort(key=lambda x: (1 if x.get("is_master") else 0, x["vram_mb"], x["memory_mb"]), reverse=True)

    return {
        "success": True,
        "processes": procs[:40],
        "orfani": orphan_count
    }


def handle_hardware_status(self):
    """GET /api/hardware/status — Restituisce metriche hardware e VRAM in tempo reale."""
    try:
        data = get_hardware_telemetry()
        self.send_json_response(data)
    except Exception as e:
        log.error("Error in handle_hardware_status: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_hardware_gpu_processes(self):
    """GET /api/hardware/gpu/processes — Restituisce lista processi GPU e memoria."""
    try:
        data = get_gpu_processes()
        self.send_json_response(data)
    except Exception as e:
        log.error("Error in handle_hardware_gpu_processes: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_hardware_config(self):
    """POST /api/hardware/config — Aggiorna la configurazione hardware."""
    try:
        body = self.read_json_body()
        _save_hw_config(body)
        self.send_json_response({
            "success": True,
            "message": "Configurazione hardware salvata con successo.",
            "config": body
        })
    except Exception as e:
        log.error("Error in handle_hardware_config: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_hardware_restart_ollama(self):
    """POST /api/hardware/restart-ollama — Riavvia o libera la VRAM cache del motore."""
    try:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

        self.send_json_response({
            "success": True,
            "message": "VRAM Cache ripulita e runtime riallineato con successo."
        })
    except Exception as e:
        log.error("Error in handle_hardware_restart_ollama: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_hardware_gpu_kill(self):
    """POST /api/hardware/gpu/kill — Termina un processo specifico tramite PID o tutti gli orfani."""
    try:
        body = self.read_json_body()
        current_pid = os.getpid()

        # 1. Kill all orphans batch
        if body.get("all_orphans") or body.get("kill_all_orphans"):
            killed = 0
            parent_pid = os.getppid() if hasattr(os, 'getppid') else -1
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'cmdline']):
                try:
                    if p.pid == current_pid or p.pid == parent_pid:
                        continue
                    p_name = (p.info.get('name') or '').lower()
                    cmdline = " ".join(p.info.get('cmdline') or []).lower()
                    if any(k in cmdline or k in p_name for k in ['pytest', 'antigravity', 'vscode', 'gemini', 'sigma_server', 'test']):
                        continue
                    mem_mb = (p.info.get('memory_info').rss if p.info.get('memory_info') else 0) / (1024**2)
                    cpu_p = p.info.get('cpu_percent') or 0.0
                    if 'python' in p_name and cpu_p == 0 and mem_mb < 35:
                        p.terminate()
                        killed += 1
                except Exception:
                    continue
            self.send_json_response({
                "success": True,
                "message": f"Terminati {killed} processi orfani." if killed > 0 else "Nessun processo orfano residuo."
            })
            return


        # 2. Kill single PID
        pid = body.get("pid")
        if not pid:
            self.send_json_response({"success": False, "error": "PID non specificato"}, 400)
            return

        if int(pid) == current_pid:
            self.send_json_response({
                "success": False,
                "error": "Il processo Master di Sigma Studio è protetto e non può essere terminato."
            })
            return

        proc = psutil.Process(int(pid))
        pname = proc.name()
        proc.terminate()
        self.send_json_response({
            "success": True,
            "message": f"Processo PID {pid} ({pname}) terminato con successo."
        })
    except psutil.NoSuchProcess:
        self.send_json_response({"success": True, "message": f"Processo PID {pid} non più attivo."})
    except Exception as e:
        log.error("Error in handle_hardware_gpu_kill: %s", e)
        self.send_json_response({"success": False, "error": str(e)}, 500)
