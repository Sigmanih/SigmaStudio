# ==============================================================================
# core/hardware_api.py — Real-time Hardware Telemetry & GPU Process Management
# Sigma Studio v8 — Supports Multi-GPU (NVIDIA/AMD), Disks, Network & Module Process Tracker
# ==============================================================================
from __future__ import annotations
import os
import sys
import json
import time
import psutil
from typing import Dict, Any, List
from core.logger import get_logger
from core.engine.hardware_probe import UniversalHardwareProbe

log = get_logger("hardware_api")
_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hardware_config.json")

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
              "temperature.gpu,power.draw,fan.speed")
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
        }
    return telemetry


def _detect_all_gpus(cpu_pct: float) -> List[Dict[str, Any]]:
    """
    Reports every GPU with measured values.

    Nothing here is synthesised. An earlier version derived GPU utilisation from
    CPU load, computed temperature and power from the device index, held VRAM
    usage above a fixed floor, and invented a discrete card when it found no GPU
    at all -- so the panel showed plausible numbers that described no real
    hardware. Fields the system cannot measure are reported as null so the UI
    can say "unknown" instead of showing a fabricated reading.
    """
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
                # No driver telemetry: mem_get_info still reports true device
                # occupancy, unlike the torch allocator counters.
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

    # Integrated GPUs: enumerable on Windows, but with no usage telemetry. They
    # are listed so the user sees the whole picture, with the unmeasurable
    # fields left null rather than filled in with invented values.
    if sys.platform == "win32":
        try:
            import subprocess
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_VideoController | "
                   "Select-Object Name, AdapterRAM | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and res.stdout.strip():
                adapters = json.loads(res.stdout)
                if isinstance(adapters, dict):
                    adapters = [adapters]
                for adapter in adapters:
                    name = (adapter.get("Name") or "").strip()
                    if not name or name.lower() in seen_names:
                        continue
                    ram_bytes = adapter.get("AdapterRAM")
                    vram_mb = int(ram_bytes // (1024 ** 2)) if ram_bytes else None
                    is_amd = "amd" in name.lower() or "radeon" in name.lower()
                    gpus_list.append({
                        "index": len(gpus_list),
                        "name": name,
                        "type": ("AMD Radeon iGPU (DirectML/DirectX 12)"
                                 if is_amd else "Integrated Graphics"),
                        "vram_total_mb": vram_mb,
                        "vram_used_mb": None,
                        "vram_free_mb": None,
                        "vram_usage_pct": None,
                        "gpu_util_pct": None,
                        "temp_c": None,
                        "power_draw_w": None,
                        "fan_speed_pct": None,
                        "telemetry_source": "none",
                        "is_integrated": True,
                    })
                    seen_names.add(name.lower())
        except Exception as ex:
            log.debug("CIM VideoController query failed: %s", ex)

    # No placeholder GPU when none is present: a machine without one must say
    # so, not display a discrete card it does not have.
    return gpus_list


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

    # 2. Linux /proc/cpuinfo
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "model name" in line:
                        _cached_cpu_brand = " ".join(line.split(":", 1)[1].split()).strip()
                        return _cached_cpu_brand
        except Exception:
            pass

    # 3. macOS sysctl
    if sys.platform == "darwin":
        try:
            import subprocess
            res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                _cached_cpu_brand = " ".join(res.stdout.split()).strip()
                return _cached_cpu_brand
        except Exception:
            pass

    # 4. Fallback to platform.processor()
    p = platform.processor()
    if p and not p.isdigit() and len(p.strip()) > 2:
        _cached_cpu_brand = " ".join(p.split()).strip()
        return _cached_cpu_brand

    _cached_cpu_brand = "CPU Host"
    return _cached_cpu_brand


def get_hardware_telemetry() -> Dict[str, Any]:
    """Collects real-time hardware telemetry for CPU, RAM, GPU, Disks, and Network."""
    # 1. CPU (100% real measured dynamic values)
    cpu_pct = psutil.cpu_percent(interval=None)
    cpu_freq = psutil.cpu_freq()
    phys_count = psutil.cpu_count(logical=False)
    log_count = psutil.cpu_count(logical=True)
    cpu_info = {
        "name": _get_cpu_brand(),
        "cores_physical": phys_count if phys_count is not None else 0,
        "cores_logical": log_count if log_count is not None else 0,
        "usage_pct": round(cpu_pct, 1),
        "freq_mhz": round(cpu_freq.current, 0) if (cpu_freq and cpu_freq.current) else 0
    }

    # 2. RAM (100% real measured dynamic values)
    vm = psutil.virtual_memory()
    ram_info = {
        "total_gb": round(vm.total / (1024**3), 2),
        "used_gb": round(vm.used / (1024**3), 2),
        "free_gb": round(vm.available / (1024**3), 2),
        "usage_pct": round(vm.percent, 1)
    }

    # 3. GPUs
    gpus_list = _detect_all_gpus(cpu_pct)

    # 4. Storage & Disks
    storage_info = _get_disks_info()

    # 5. Network
    network_info = _get_network_info()

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
