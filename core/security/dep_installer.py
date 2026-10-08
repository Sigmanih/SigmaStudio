# ==============================================================================
# core/dep_installer.py — Sigma Studio Smart Dependency Installer
# Automatically selects and installs the correct dependencies for the platform.
# ==============================================================================

import os
import sys
import json
import subprocess
from typing import Optional, Dict, Any
from core import paths
from core.logger import get_logger
from core.capability_manager import detect_capabilities, get_requirements_file, SystemCapabilities

log = get_logger(__name__)


def get_pip_executable() -> str:
    """Returns the path to pip in the virtual environment of the installation.

    Il percorso era relativo a ".venv": lanciando il server da un'altra
    cartella non lo trovava e ripiegava silenziosamente sul pip di sistema,
    installando le dipendenze fuori dall'ambiente del progetto.
    """
    pip_path = paths.venv_pip()
    if pip_path.exists():
        return str(pip_path)

    # Fallback to sys.executable -m pip
    return f"{sys.executable} -m pip"


def get_torch_index_url(caps: SystemCapabilities) -> Optional[str]:
    """Returns the appropriate PyTorch index URL based on capabilities."""
    if caps.cuda:
        return "https://download.pytorch.org/whl/cu124"
    elif caps.mps or caps.is_apple_silicon:
        return None  # Standard PyPI has MPS support
    else:
        return "https://download.pytorch.org/whl/cpu"


def install_requirements_file(req_file: str, extra_index_url: Optional[str] = None, verbose: bool = True) -> bool:
    """Runs pip install with the given requirements file."""
    pip_exe = get_pip_executable()
    
    cmd = []
    if pip_exe.endswith("pip") or pip_exe.endswith("pip.exe"):
        cmd = [pip_exe, "install", "-r", req_file]
    else:
        cmd = pip_exe.split() + ["install", "-r", req_file]
        
    if extra_index_url:
        cmd.extend(["--extra-index-url", extra_index_url])
        
    log.info(f"[SIGMA] Installing dependencies from {req_file}...")
    
    try:
        if verbose:
            subprocess.run(cmd, check=True)
        else:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info(f"[SIGMA] Successfully installed {req_file}")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"[SIGMA] Failed to install {req_file}: {e}")
        return False


def install_for_platform(caps: Optional[SystemCapabilities] = None, include_tts: bool = False, verbose: bool = True) -> bool:
    """Detects platform and installs appropriate requirements."""
    if caps is None:
        caps = detect_capabilities()
        
    log.info(f"[SIGMA] Detected platform: {caps.os} {caps.arch}")
    if caps.gpu_type:
        log.info(f"[SIGMA] Detected accelerator: {caps.gpu_type.upper()}")
        
    req_file = get_requirements_file(caps)
    index_url = get_torch_index_url(caps)
    
    success = install_requirements_file(req_file, extra_index_url=index_url, verbose=verbose)
    
    if success and include_tts:
        tts_req = "requirements/tts.txt"
        if os.path.exists(tts_req):
            log.info("[SIGMA] Installing optional TTS dependencies...")
            success = install_requirements_file(tts_req, verbose=verbose)
            
    return success


def check_installed_packages() -> Dict[str, str]:
    """Returns a dictionary of installed packages and versions."""
    pip_exe = get_pip_executable()
    
    cmd = []
    if pip_exe.endswith("pip") or pip_exe.endswith("pip.exe"):
        cmd = [pip_exe, "list", "--format=json"]
    else:
        cmd = pip_exe.split() + ["list", "--format=json"]
        
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        packages = json.loads(result.stdout)
        return {pkg["name"].lower(): pkg["version"] for pkg in packages}
    except Exception as e:
        log.error(f"[SIGMA] Failed to list packages: {e}")
        return {}


def verify_installation(caps: SystemCapabilities) -> Dict[str, Any]:
    """Checks critical imports work and returns success/failure info."""
    results = {
        "success": True,
        "imports": {},
        "errors": []
    }
    
    critical_modules = ["fastapi", "uvicorn", "pydantic", "torch", "transformers"]
    
    for mod in critical_modules:
        try:
            __import__(mod)
            results["imports"][mod] = True
        except ImportError as e:
            results["imports"][mod] = False
            results["success"] = False
            results["errors"].append(str(e))
            
    if results["success"] and caps.cuda:
        try:
            import torch
            if not torch.cuda.is_available():
                results["success"] = False
                results["errors"].append("CUDA detected but torch.cuda.is_available() returned False")
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Failed to check CUDA availability: {e}")
            
    return results
