# ==============================================================================
# core/capability_manager.py — Sigma Studio Capability Manager
# Bridges hardware detection with module compatibility and dependency selection.
# ==============================================================================

from __future__ import annotations
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from core import paths
from core.logger import get_logger

log = get_logger(__name__)


@dataclass
class SystemCapabilities:
    """Comprehensive snapshot of the current system's capabilities."""
    # Platform
    os: str = ""                    # "Windows" | "Linux" | "Darwin"
    arch: str = ""                  # "x86_64" | "aarch64" | "arm64" | "AMD64"
    python_version: str = ""
    
    # Hardware flags
    is_arm: bool = False
    is_raspberry_pi: bool = False
    is_apple_silicon: bool = False
    is_windows: bool = False
    is_linux: bool = False
    is_darwin: bool = False
    
    # GPU / Accelerator
    gpu_type: Optional[str] = None   # "nvidia" | "amd" | "apple" | "directml" | None
    cuda: bool = False
    cuda_version: Optional[str] = None
    mps: bool = False                # Apple Metal
    rocm: bool = False               # AMD ROCm
    gpu_count: int = 0
    total_vram_gb: float = 0.0
    
    # System resources
    ram_gb: float = 0.0
    cpu_cores: int = 0
    
    # External services
    ollama: bool = False
    docker: bool = False
    npm: bool = False
    git: bool = False
    
    # Integration capabilities
    home_assistant: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)


# ==============================================================================
# REQUISITI DEI MODULI
# ==============================================================================
# Qui c'era un dizionario con i requisiti hardware di ogni modulo, scritto a
# mano nel kernel. Era uno dei posti in cui il kernel conosceva i moduli per
# nome: aggiungerne uno voleva dire modificare il kernel, e un modulo che
# cambiava i propri requisiti non poteva dirlo da solo.
#
# Ora ci sono due fonti, in quest'ordine:
#
#   1. il manifest del modulo installato — e' lui l'autorita' su se stesso;
#   2. core/modules_catalog.json — per i moduli che il marketplace conosce ma
#      che non sono installati, di cui la UI deve comunque poter dire se
#      girerebbero su questa macchina prima di scaricarli.
#
# Il kernel non nomina piu' nessun modulo.

_CATALOGO_MODULI = Path(__file__).resolve().parent / "modules_catalog.json"

_cache_requisiti: Optional[dict] = None


def _requisiti_dal_catalogo() -> dict:
    """I requisiti dei moduli conosciuti ma non installati."""
    try:
        dati = json.loads(_CATALOGO_MODULI.read_text(encoding="utf-8"))
        return dati.get("moduli", {})
    except (OSError, ValueError) as exc:
        log.warning("[Capabilities] Catalogo dei moduli non leggibile: %s", exc)
        return {}


def _requisiti_dai_manifest() -> dict:
    """I requisiti dichiarati dai moduli effettivamente installati."""
    from core import paths

    trovati: dict = {}
    radice = paths.modules_backend_dir()
    if not radice.is_dir():
        return trovati

    from core.module_links import module_manifest_path

    for cartella in sorted(radice.iterdir()):
        if not cartella.is_dir() or cartella.name.startswith((".", "_")):
            continue
        # Per un modulo collegato al repository di sviluppo il manifest sta
        # nella radice del modulo, un livello sopra il codice: chiederlo al
        # risolutore invece di comporlo a mano e' cio' che distingue un modulo
        # in sviluppo da uno senza dichiarazioni.
        manifest = module_manifest_path(cartella.name)
        if manifest is None:
            continue
        try:
            dati = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("[Capabilities] Manifest illeggibile per '%s': %s",
                        cartella.name, exc)
            continue

        requisiti = (dati.get("requires") or {}).get("hardware")
        if requisiti is None:
            # Un manifest senza sezione hardware non dichiara vincoli: il modulo
            # e' installato, quindi gira. Non e' un errore, e' il caso normale.
            continue

        trovati[dati.get("id") or cartella.name] = {
            "description": dati.get("description", ""),
            "requires": requisiti.get("requires", {}),
            "recommended": requisiti.get("recommended", {}),
            "reason_if_unavailable": requisiti.get("reason_if_unavailable"),
        }
    return trovati


def get_module_requirements(refresh: bool = False) -> dict:
    """Requisiti di tutti i moduli noti: catalogo, sovrascritto dai manifest."""
    global _cache_requisiti
    if _cache_requisiti is None or refresh:
        requisiti = dict(_requisiti_dal_catalogo())
        requisiti.update(_requisiti_dai_manifest())
        _cache_requisiti = requisiti
    return _cache_requisiti


def detect_capabilities() -> SystemCapabilities:
    """Detect current system capabilities using hardware_probe if available."""
    caps = SystemCapabilities()
    
    # Basic platform info (always available, no dependencies)
    caps.os = platform.system()
    caps.arch = platform.machine().lower()
    caps.python_version = platform.python_version()
    caps.is_windows = caps.os == "Windows"
    caps.is_linux = caps.os == "Linux"
    caps.is_darwin = caps.os == "Darwin"
    caps.is_arm = "arm" in caps.arch or "aarch64" in caps.arch
    caps.is_apple_silicon = caps.is_darwin and caps.is_arm
    caps.cpu_cores = os.cpu_count() or 1
    
    # Raspberry Pi detection
    if caps.is_linux:
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r", encoding="utf-8", errors="ignore") as f:
                    if "raspberry pi" in f.read().lower():
                        caps.is_raspberry_pi = True
        except Exception:
            pass
    
    # RAM
    try:
        import psutil
        caps.ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        pass
    
    # GPU detection via hardware_probe
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        accs = UniversalHardwareProbe.probe_accelerators()
        for acc in accs:
            acc_type = acc.get("type", "")
            if acc_type == "NVIDIA_CUDA":
                caps.gpu_type = "nvidia"
                caps.cuda = True
                caps.gpu_count += 1
                caps.total_vram_gb += acc.get("total_vram_gb", 0)
                # Try to get CUDA version
                try:
                    import torch
                    caps.cuda_version = torch.version.cuda
                except Exception:
                    pass
            elif acc_type == "APPLE_MPS":
                caps.gpu_type = "apple"
                caps.mps = True
                caps.gpu_count = 1
            elif acc_type == "AMD_ROCM":
                caps.gpu_type = "amd"
                caps.rocm = True
                caps.gpu_count += 1
                caps.total_vram_gb += acc.get("total_vram_gb", 0)
            elif acc_type == "DIRECT_ML_COMPATIBLE":
                caps.gpu_type = "directml"
    except Exception as e:
        log.debug(f"GPU detection via hardware_probe failed: {e}")
    
    # External tools
    caps.ollama = shutil.which("ollama") is not None
    caps.docker = shutil.which("docker") is not None
    caps.npm = shutil.which("npm") is not None
    caps.git = shutil.which("git") is not None
    
    # Home Assistant check (from config.json)
    try:
        import json
        config_path = str(paths.config_file())
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            ha_cfg = cfg.get("mcp", {}).get("integrations", {}).get("home_assistant", {})
            if ha_cfg.get("baseUrl") and ha_cfg.get("token"):
                caps.home_assistant = True
    except Exception:
        pass
    
    return caps


def get_requirements_file(caps: SystemCapabilities) -> str:
    """Return the appropriate requirements file path based on capabilities."""
    if caps.cuda:
        return "requirements/cuda.txt"
    elif caps.mps or caps.is_apple_silicon:
        return "requirements/apple.txt"
    else:
        return "requirements/cpu.txt"


def get_available_modules(caps: Optional[SystemCapabilities] = None) -> dict[str, dict]:
    """Return module compatibility information based on system capabilities.
    
    Returns a dict of module_id -> {
        "compatible": bool,
        "description": str,
        "reason": str | None,  # Only set if incompatible
        "recommended_upgrade": str | None,  # Suggestion to make it compatible
    }
    """
    if caps is None:
        caps = detect_capabilities()
    
    result = {}
    for module_id, req_info in get_module_requirements().items():
        compatible = True
        reason = None
        recommended_upgrade = None
        
        requires = req_info.get("requires", {})
        for key, value in requires.items():
            if value is True and not getattr(caps, key, False):
                compatible = False
                reason = req_info.get("reason_if_unavailable", f"Requires {key}")
                break
            elif isinstance(value, (int, float)) and getattr(caps, key, 0) < value:
                compatible = False
                reason = f"Requires {key} >= {value} (current: {getattr(caps, key, 0)})"
                break
        
        # Check recommended (doesn't affect compatibility, just adds suggestions)
        recommended = req_info.get("recommended", {})
        for key, value in recommended.items():
            if value is True:
                cap_val = getattr(caps, key, None)
                if not cap_val:
                    recommended_upgrade = f"Performance improves with {key}"
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                cap_val = getattr(caps, key, 0)
                if isinstance(cap_val, (int, float)) and cap_val < value:
                    recommended_upgrade = f"Performance improves with {key} >= {value}"
        
        result[module_id] = {
            "compatible": compatible,
            "description": req_info.get("description", ""),
            "reason": reason,
            "recommended_upgrade": recommended_upgrade,
        }
    
    return result
