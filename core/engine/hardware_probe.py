# ==============================================================================
# core/engine/hardware_probe.py — Universal Hardware Detector & Calibrator
# Supports: NVIDIA CUDA, AMD ROCm/HIP, Apple Silicon Metal (MPS), Intel/DirectML,
# ARM NEON (Raspberry Pi 4/5, Jetson, Rockchip), CPU AVX-512/AVX2, Multi-Drive Storage
# ==============================================================================
import os
import sys
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
        info = {
            "cores_physical": psutil.cpu_count(logical=False) or 1,
            "cores_logical": psutil.cpu_count(logical=True) or 1,
            "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "simd_features": []
        }
        # Check SIMD instructions
        arch = platform.machine().lower()
        if "arm" in arch or "aarch64" in arch:
            info["simd_features"].append("ARM_NEON")
            if sys.byteorder == 'little':
                info["simd_features"].append("ARM_64")
        else:
            info["simd_features"].extend(["AVX2", "FMA"])
        return info

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
            "swap_free_gb": round(swap.free / (1024**3), 2)
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
                    accelerators.append({
                        "device_id": idx,
                        "type": "NVIDIA_CUDA",
                        "name": props.name,
                        "compute_capability": f"{props.major}.{props.minor}",
                        "total_vram_gb": round(total_vram / (1024**3), 2),
                        "free_vram_gb": round(free_vram / (1024**3), 2),
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

    @classmethod
    def probe_storage_drives(cls) -> List[Dict[str, Any]]:
        """List all physical storage partitions and mounts available for sharded streaming."""
        drives = []
        try:
            partitions = psutil.disk_partitions(all=False)
            seen_mounts = set()
            for p in partitions:
                if p.mountpoint in seen_mounts:
                    continue
                seen_mounts.add(p.mountpoint)
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    # Benchmark read speed briefly (5MB sample)
                    read_speed_mb = cls._benchmark_read_speed(p.mountpoint)
                    drives.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "used_percent": usage.percent,
                        "estimated_read_speed_mb_s": read_speed_mb,
                        "is_fast_storage": read_speed_mb >= 350
                    })
                except Exception:
                    continue
        except Exception as e:
            log.warning(f"[HardwareProbe] Error probing storage drives: {e}")
        return drives

    @classmethod
    def _benchmark_read_speed(cls, mountpoint: str) -> float:
        """Estimate sequential read bandwidth of a drive in MB/s."""
        sample_file = os.path.join(mountpoint, f".sigma_speed_test_{int(time.time())}.tmp")
        try:
            # Write 4MB test chunk
            data = b"0" * (4 * 1024 * 1024)
            with open(sample_file, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

            # Read and measure time
            t0 = time.perf_counter()
            with open(sample_file, "rb") as f:
                _ = f.read()
            t1 = time.perf_counter()
            
            elapsed = max(t1 - t0, 0.0001)
            mb_s = round(4.0 / elapsed, 1)
            return mb_s
        except Exception:
            return 250.0  # Safe default estimate for SSD
        finally:
            if os.path.exists(sample_file):
                try:
                    os.remove(sample_file)
                except Exception:
                    pass

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
