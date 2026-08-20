"""Unit tests for core/capability_manager.py."""
import pytest
from core.capability_manager import (
    SystemCapabilities,
    detect_capabilities,
    get_requirements_file,
    get_available_modules,
    MODULE_REQUIREMENTS,
)


def test_detect_capabilities_returns_valid_object():
    caps = detect_capabilities()
    assert isinstance(caps, SystemCapabilities)
    assert caps.os in ("Windows", "Linux", "Darwin")
    assert caps.arch != ""
    assert caps.python_version != ""
    assert isinstance(caps.cpu_cores, int) and caps.cpu_cores > 0
    assert isinstance(caps.ram_gb, float) and caps.ram_gb >= 0.0

    d = caps.to_dict()
    assert isinstance(d, dict)
    assert "cuda" in d
    assert "mps" in d
    assert "is_raspberry_pi" in d


def test_requirements_file_selection():
    # CUDA platform
    cuda_caps = SystemCapabilities(cuda=True, gpu_type="nvidia")
    assert get_requirements_file(cuda_caps) == "requirements/cuda.txt"

    # Apple Silicon platform
    mps_caps = SystemCapabilities(mps=True, is_apple_silicon=True, is_darwin=True)
    assert get_requirements_file(mps_caps) == "requirements/apple.txt"

    # CPU/Raspberry Pi platform
    cpu_caps = SystemCapabilities(cuda=False, mps=False, is_raspberry_pi=True, is_arm=True)
    assert get_requirements_file(cpu_caps) == "requirements/cpu.txt"


def test_available_modules_cuda_vs_cpu():
    # CUDA GPU with high VRAM -> Training Lab compatible
    cuda_caps = SystemCapabilities(cuda=True, total_vram_gb=16.0, gpu_type="nvidia")
    cuda_modules = get_available_modules(cuda_caps)
    assert cuda_modules["sigma_training_lab"]["compatible"] is True
    assert cuda_modules["sigma_creative_lab"]["compatible"] is True

    # CPU-only (Raspberry Pi) -> Training Lab incompatible
    rpi_caps = SystemCapabilities(
        cuda=False,
        mps=False,
        is_raspberry_pi=True,
        is_arm=True,
        is_linux=True,
        total_vram_gb=0.0,
    )
    rpi_modules = get_available_modules(rpi_caps)
    assert rpi_modules["sigma_training_lab"]["compatible"] is False
    assert "Requires NVIDIA GPU" in rpi_modules["sigma_training_lab"]["reason"]
    # CPU-friendly modules remain compatible
    assert rpi_modules["sigma_voice_studio"]["compatible"] is True
    assert rpi_modules["sigma_knowledge"]["compatible"] is True
    assert rpi_modules["sigma_hardware_lab"]["compatible"] is True


def test_available_modules_home_assistant():
    no_ha_caps = SystemCapabilities(home_assistant=False)
    mods = get_available_modules(no_ha_caps)
    assert mods["sigma_domotica"]["compatible"] is False

    ha_caps = SystemCapabilities(home_assistant=True)
    mods_ha = get_available_modules(ha_caps)
    assert mods_ha["sigma_domotica"]["compatible"] is True
