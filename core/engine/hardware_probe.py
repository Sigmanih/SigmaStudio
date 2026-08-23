# ==============================================================================
# core/engine/hardware_probe.py — Universal Hardware Detector & Calibrator
# Supports: NVIDIA CUDA, AMD ROCm/HIP, Apple Silicon Metal (MPS), Intel/DirectML,
# ARM NEON (Raspberry Pi 4/5, Jetson, Rockchip), CPU AVX-512/AVX2, Multi-Drive Storage
# ==============================================================================
import os
import time
import platform
import psutil
from typing import Dict, Any, List, Optional
from core.logger import get_logger

log = get_logger(__name__)


class UniversalHardwareProbe:
    """Detects, benchmarks, and profiles any hardware configuration for SigmaEngine."""

    @classmethod
    def probe_all(cls) -> Dict[str, Any]:
        """Perform comprehensive hardware probing across all compute and storage devices."""
        return {
            "system": cls.probe_system(),
            "cpu": cls.probe_cpu(),
            "ram": cls.probe_ram(),
            "accelerators": cls.probe_accelerators(),
            "storage_drives": cls.probe_storage_drives(),
            "recommended_tiering": cls.get_recommended_tiering(),
            "timestamp": time.time()
        }

    @classmethod
    def probe_system(cls) -> Dict[str, Any]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "arch": platform.machine().lower(),
            "python_version": platform.python_version(),
            "is_arm": "arm" in platform.machine().lower() or "aarch64" in platform.machine().lower(),
            "is_raspberry_pi": cls._is_raspberry_pi(),
            "is_apple_silicon": platform.system() == "Darwin" and ("arm" in platform.machine().lower() or "aarch64" in platform.machine().lower()),
            "is_windows": platform.system() == "Windows",
            "is_linux": platform.system() == "Linux"
        }

    @classmethod
    def _is_raspberry_pi(cls) -> bool:
        if platform.system() != "Linux":
            return False
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r", encoding="utf-8", errors="ignore") as f:
                    return "raspberry pi" in f.read().lower()
        except Exception:
            pass
        return False

    @classmethod
    def probe_cpu(cls) -> Dict[str, Any]:
        """
        Cores, clock and the SIMD this CPU actually has.

        The features used to be asserted rather than read -- every non-ARM host
        was reported as AVX2+FMA, including the ones that predate AVX2 and the
        ones running under emulation. A capability report that is right by
        assumption is worse than none: it is the input to choosing which
        llama.cpp wheel to install.
        """
        freq = None
        try:
            freq = psutil.cpu_freq()
        except Exception:
            freq = None

        return {
            "cores_physical": psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1,
            "cores_logical": psutil.cpu_count(logical=True) or 1,
            "frequency_mhz": round(freq.current) if freq else 0,
            "frequency_max_mhz": round(freq.max) if freq and freq.max else 0,
            "model": cls._cpu_model_name(),
            "simd_features": cls._probe_simd_features(),
        }

    @staticmethod
    def _cpu_model_name() -> str:
        """The CPU's own name, where the platform will say."""
        system = platform.system()
        try:
            if system == "Linux":
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        key, _, value = line.partition(":")
                        if key.strip().lower() in ("model name", "hardware", "cpu model"):
                            return value.strip()
            elif system == "Darwin":
                import subprocess
                out = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5,
                )
                if out.returncode == 0:
                    return out.stdout.strip()
        except Exception as exc:
            log.debug("[HardwareProbe] CPU model unavailable: %s", exc)
        return platform.processor() or platform.machine()

    @classmethod
    def _probe_simd_features(cls) -> List[str]:
        """
        The vector extensions this CPU reports, in llama.cpp's vocabulary.

        Reported from the OS rather than inferred from the architecture, so a
        pre-AVX2 x86 host and a Raspberry Pi both get an answer that matches
        what a kernel would actually be able to run.
        """
        system = platform.system()
        arch = platform.machine().lower()
        found: List[str] = []

        if system == "Linux":
            flags = cls._linux_cpu_flags()
            # /proc/cpuinfo spells ARM features in its own way: `asimd` is
            # NEON on aarch64, and dotprod/i8mm are what llama.cpp's quantized
            # ARM kernels look for.
            mapping = {
                "avx512f": "AVX512", "avx2": "AVX2", "avx": "AVX",
                "fma": "FMA", "f16c": "F16C", "sse4_2": "SSE4.2",
                "asimd": "ARM_NEON", "neon": "ARM_NEON",
                "asimddp": "ARM_DOTPROD", "i8mm": "ARM_I8MM",
                "sve": "ARM_SVE", "asimdhp": "ARM_FP16",
            }
            for flag, label in mapping.items():
                if flag in flags and label not in found:
                    found.append(label)

        elif system == "Darwin":
            found.extend(cls._darwin_simd_features(arch))

        elif system == "Windows":
            found.extend(cls._windows_simd_features())

        if not found:
            # Nothing could be read. Say what the architecture guarantees and
            # nothing more: NEON is mandatory on aarch64, SSE2 on x86-64.
            if "aarch64" in arch or "arm64" in arch:
                found.append("ARM_NEON")
            elif arch in ("x86_64", "amd64"):
                found.append("SSE2")

        if ("aarch64" in arch or "arm64" in arch) and "ARM_NEON" not in found:
            found.append("ARM_NEON")
        return found

    @staticmethod
    def _linux_cpu_flags() -> set:
        flags = set()
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    key, _, value = line.partition(":")
                    if key.strip().lower() in ("flags", "features"):
                        flags.update(value.split())
        except Exception as exc:
            log.debug("[HardwareProbe] /proc/cpuinfo unreadable: %s", exc)
        return flags

    @staticmethod
    def _darwin_simd_features(arch: str) -> List[str]:
        import subprocess
        found: List[str] = []
        probes = {
            "hw.optional.arm.FEAT_DotProd": "ARM_DOTPROD",
            "hw.optional.arm.FEAT_I8MM": "ARM_I8MM",
            "hw.optional.arm.FEAT_FP16": "ARM_FP16",
            "hw.optional.avx2_0": "AVX2",
            "hw.optional.avx512f": "AVX512",
            "hw.optional.fma": "FMA",
        }
        for key, label in probes.items():
            try:
                out = subprocess.run(["sysctl", "-n", key],
                                     capture_output=True, text=True, timeout=5)
                if out.returncode == 0 and out.stdout.strip() == "1":
                    found.append(label)
            except Exception:
                continue
        if ("arm" in arch or "aarch64" in arch) and "ARM_NEON" not in found:
            found.append("ARM_NEON")
        return found

    @staticmethod
    def _windows_simd_features() -> List[str]:
        """Asks Windows itself, via IsProcessorFeaturePresent."""
        found: List[str] = []
        try:
            import ctypes
            is_present = ctypes.windll.kernel32.IsProcessorFeaturePresent
            # Values from winnt.h.
            for code, label in ((40, "AVX2"), (39, "AVX"), (41, "AVX512"),
                                (38, "SSE4.2"), (10, "SSE2")):
                if is_present(code):
                    found.append(label)
            if "AVX2" in found:
                # FMA3 shipped with AVX2 on every part that has AVX2, and
                # Windows exposes no separate flag for it.
                found.append("FMA")
        except Exception as exc:
            log.debug("[HardwareProbe] IsProcessorFeaturePresent failed: %s", exc)
        return found

    # A machine with this little RAM cannot absorb a mis-sized plan: there is
    # no swap worth the name on a Raspberry Pi (512 MB on an SD card), so an
    # over-allocation does not slow the board down, it takes it off the
    # network until somebody power-cycles it.
    _LOW_MEMORY_GB = 10.0

    @classmethod
    def probe_ram(cls) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_bytes": mem.total,
            "total_gb": round(mem.total / (1024**3), 2),
            "available_bytes": mem.available,
            "available_gb": round(mem.available / (1024**3), 2),
            "used_percent": mem.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_free_gb": round(swap.free / (1024**3), 2),
            # Read by the GGUF planner, which spends a fraction of what is free
            # rather than a fixed number of gigabytes.
            "is_low_memory": (mem.total / (1024**3)) < cls._LOW_MEMORY_GB,
        }

    @classmethod
    def probe_accelerators(cls) -> List[Dict[str, Any]]:
        accelerators = []
        
        # 1. Check NVIDIA CUDA via PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                for idx in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(idx)
                    total_vram = props.total_memory
                    free_vram, _ = torch.cuda.mem_get_info(idx) if hasattr(torch.cuda, 'mem_get_info') else (total_vram, total_vram)

                    # Blocks this process has reserved but is no longer using
                    # read as "used" at the driver level, yet the allocator will
                    # hand them straight back to the next allocation. After
                    # unloading a model that pool can be gigabytes, and treating
                    # it as unavailable makes every later plan needlessly
                    # conservative.
                    reclaimable = 0
                    try:
                        reclaimable = max(
                            torch.cuda.memory_reserved(idx)
                            - torch.cuda.memory_allocated(idx),
                            0,
                        )
                    except Exception:
                        reclaimable = 0
                    free_vram = min(free_vram + reclaimable, total_vram)

                    accelerators.append({
                        "device_id": idx,
                        "type": "NVIDIA_CUDA",
                        "name": props.name,
                        "compute_capability": f"{props.major}.{props.minor}",
                        "total_vram_gb": round(total_vram / (1024**3), 2),
                        "free_vram_gb": round(free_vram / (1024**3), 2),
                        "reclaimable_cache_gb": round(reclaimable / (1024**3), 2),
                        "multi_processor_count": props.multi_processor_count,
                        "supports_flash_attention": props.major >= 8,
                        "supports_fp8": props.major >= 8.9 or props.major >= 9,
                        "supports_bf16": torch.cuda.is_bf16_supported()
                    })
        except Exception as e:
            log.debug(f"[HardwareProbe] CUDA check error: {e}")

        # 2. Check Apple Silicon Metal Performance Shaders (MPS)
        try:
            import torch
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                mem = psutil.virtual_memory()
                accelerators.append({
                    "device_id": 0,
                    "type": "APPLE_MPS",
                    "name": "Apple Silicon Unified GPU",
                    "unified_memory_gb": round(mem.total / (1024**3), 2),
                    "supports_mps": True,
                    "supports_fp16": True
                })
        except Exception as e:
            log.debug(f"[HardwareProbe] MPS check error: {e}")

        # 3. Check ROCm / HIP (AMD GPUs)
        try:
            import torch
            if hasattr(torch.version, 'hip') and torch.version.hip and torch.cuda.is_available():
                # Already captured by CUDA wrapper above, but mark as ROCm
                for acc in accelerators:
                    acc["type"] = "AMD_ROCM"
        except Exception:
            pass

        # 4. Check DirectML / ONNX Runtime (Windows / Cross-Vendor)
        if not accelerators and platform.system() == "Windows":
            accelerators.append({
                "device_id": 0,
                "type": "DIRECT_ML_COMPATIBLE",
                "name": "DirectX 12 / DirectML Compute Device",
                "status": "Available via DirectML/ONNX"
            })

        # 5. Pure CPU fallback if no GPU
        if not accelerators:
            accelerators.append({
                "device_id": 0,
                "type": "HOST_CPU",
                "name": f"CPU Compute ({platform.machine()})",
                "threads": psutil.cpu_count(logical=True) or 1
            })

        return accelerators

    # Sequential-read bandwidth by storage class, in MB/s. These are class
    # estimates used for ranking offload targets, not measurements: reliably
    # timing a real read means defeating the OS page cache, which is not
    # portable. Bus type is a far stronger signal than a cached micro-read.
    _SPEED_CLASS_MB_S = {
        "nvme": 3500.0,
        "ssd": 520.0,
        "usb": 400.0,
        "hdd": 150.0,
        "unknown": 250.0,
    }

    _media_map_cache: Optional[Dict[str, Dict[str, str]]] = None

    @classmethod
    def probe_storage_drives(cls) -> List[Dict[str, Any]]:
        """
        Lists mounted volumes with their storage class, for choosing offload
        targets. Performs no disk writes, so it is safe to call on startup.
        """
        drives = []
        media_map = cls._get_media_map()
        try:
            partitions = psutil.disk_partitions(all=False)
            seen_mounts = set()
            for p in partitions:
                if p.mountpoint in seen_mounts:
                    continue
                seen_mounts.add(p.mountpoint)
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                except Exception:
                    continue

                media = media_map.get(cls._mount_key(p.mountpoint), {})
                speed_class = cls._classify_storage(media)
                bandwidth = cls._SPEED_CLASS_MB_S[speed_class]

                drives.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "used_percent": usage.percent,
                    "speed_class": speed_class,
                    "media_type": media.get("MediaType", "Unknown"),
                    "bus_type": media.get("BusType", "Unknown"),
                    "model": media.get("Model", ""),
                    "estimated_read_speed_mb_s": bandwidth,
                    "is_removable": speed_class == "usb",
                    "is_fast_storage": speed_class in ("nvme", "ssd"),
                })
        except Exception as e:
            log.warning(f"[HardwareProbe] Error probing storage drives: {e}")
        return drives

    @staticmethod
    def _mount_key(mountpoint: str) -> str:
        """Normalizes a mountpoint to the key used by the media map."""
        if platform.system() == "Windows":
            return mountpoint.rstrip("\\/").rstrip(":").upper()[:1]
        return mountpoint

    @staticmethod
    def _classify_storage(media: Dict[str, str]) -> str:
        """Maps a drive's reported media/bus type onto a speed class."""
        bus = (media.get("BusType") or "").lower()
        media_type = (media.get("MediaType") or "").lower()

        if bus in ("usb", "1394", "sd", "mmc"):
            return "usb"
        if "nvme" in bus:
            return "nvme"
        if "ssd" in media_type or media_type == "4":
            return "ssd"
        if "hdd" in media_type or "rotational" in media_type or media_type == "3":
            return "hdd"
        return "unknown"

    @classmethod
    def _get_media_map(cls) -> Dict[str, Dict[str, str]]:
        """
        Maps each volume to its physical device characteristics.
        Cached: the answer only changes when hardware is plugged or unplugged.
        """
        if cls._media_map_cache is not None:
            return cls._media_map_cache

        system = platform.system()
        try:
            if system == "Windows":
                cls._media_map_cache = cls._get_media_map_windows()
            elif system == "Linux":
                cls._media_map_cache = cls._get_media_map_linux()
            else:
                cls._media_map_cache = {}
        except Exception as e:
            log.debug(f"[HardwareProbe] Media type detection failed: {e}")
            cls._media_map_cache = {}

        return cls._media_map_cache

    @staticmethod
    def _get_media_map_windows() -> Dict[str, Dict[str, str]]:
        """Joins drive letters to physical disks via Windows Storage cmdlets."""
        import subprocess
        import json as _json

        script = (
            "$p=@{};"
            "Get-Partition -ErrorAction SilentlyContinue | "
            "Where-Object {$_.DriveLetter} | "
            "ForEach-Object { $p[[string]$_.DriveLetter]=[string]$_.DiskNumber };"
            "$d=@{};"
            "Get-PhysicalDisk -ErrorAction SilentlyContinue | "
            "ForEach-Object { $d[[string]$_.DeviceId]=@{"
            "MediaType=[string]$_.MediaType;"
            "BusType=[string]$_.BusType;"
            "Model=[string]$_.FriendlyName} };"
            "$o=@{};"
            "foreach($k in $p.Keys){$n=[string]$p[$k];"
            "if($d.ContainsKey($n)){$o[$k]=$d[$n]}};"
            "$o | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        return _json.loads(result.stdout.strip()) or {}

    @staticmethod
    def _get_media_map_linux() -> Dict[str, Dict[str, str]]:
        """Reads rotational/bus hints from sysfs for each mounted block device."""
        media: Dict[str, Dict[str, str]] = {}
        for part in psutil.disk_partitions(all=False):
            dev = os.path.basename(part.device)
            base = dev.rstrip("0123456789")
            if base.startswith("nvme"):
                base = dev.split("p")[0]
                media[part.mountpoint] = {"BusType": "NVMe", "MediaType": "SSD"}
                continue
            rotational_path = f"/sys/block/{base}/queue/rotational"
            try:
                with open(rotational_path, "r", encoding="utf-8") as f:
                    rotational = f.read().strip()
                media[part.mountpoint] = {
                    "BusType": "SATA",
                    "MediaType": "HDD" if rotational == "1" else "SSD",
                }
            except Exception:
                continue
        return media

    @classmethod
    def get_recommended_tiering(cls) -> Dict[str, Any]:
        """Calculates optimal tiering distribution for the local machine."""
        accs = cls.probe_accelerators()
        ram = cls.probe_ram()
        drives = cls.probe_storage_drives()
        
        has_cuda = any(a.get("type") == "NVIDIA_CUDA" for a in accs)
        has_mps = any(a.get("type") == "APPLE_MPS" for a in accs)
        total_vram = sum(a.get("free_vram_gb", 0) for a in accs if "free_vram_gb" in a)
        
        tier0 = "CUDA_GPU_0" if has_cuda else ("APPLE_MPS" if has_mps else "SYSTEM_RAM")
        tier1 = f"CUDA_GPU_1" if len([a for a in accs if a.get("type") == "NVIDIA_CUDA"]) > 1 else None
        tier2 = "SYSTEM_RAM" if (has_cuda or has_mps) else "HOST_CPU"
        tier3_drives = [d["mountpoint"] for d in drives if d.get("free_gb", 0) > 10]
        
        return {
            "tier0_primary": tier0,
            "tier1_secondary": tier1,
            "tier2_host_ram": tier2,
            "tier3_disk_shards_available": len(tier3_drives) > 1,
            "tier3_drives": tier3_drives,
            "recommended_quantization": "NF4" if (has_cuda and total_vram >= 6) else ("GGUF_Q4_K_M" if ram["available_gb"] >= 4 else "GGUF_Q8_0"),
            "max_supported_params": "70B" if (total_vram + ram["available_gb"] >= 40) else ("32B" if (total_vram + ram["available_gb"] >= 20) else ("8B" if (total_vram + ram["available_gb"] >= 6) else "1.5B"))
        }
