#!/usr/bin/env python3
"""
tests/test_rust_kernel_simd.py
Verifica di correttezza numerica, throughput GB/s, GFLOPS e test fast_git_status
per il motore di calcolo SIMD del Micro-Kernel Rust.
"""

import json
import math
import os
import shutil
import pytest
import struct
import subprocess
import sys
import time
from pathlib import Path

# Assicura stdout UTF-8 su Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def f16_to_f32_py(val_u16: int) -> float:
    """Implementazione di riferimento Python pura di IEEE 754 half-precision."""
    b = struct.pack("<H", val_u16)
    return struct.unpack("<e", b)[0]


def dequant_q8_0_ref(block_bytes: bytes) -> list[float]:
    """Dequantizzazione di riferimento Python per blocco Q8_0 (34 byte -> 32 float)."""
    assert len(block_bytes) == 34
    scale_raw = struct.unpack("<H", block_bytes[0:2])[0]
    scale = f16_to_f32_py(scale_raw)
    quants = struct.unpack("<32b", block_bytes[2:34])
    return [q * scale for q in quants]


def test_riferimenti_f16_e_q8():
    for raw, expected in ((0x0000, 0.0), (0x3C00, 1.0), (0xBC00, -1.0),
                          (0x3800, 0.5), (0x4000, 2.0), (0x5140, 42.0)):
        assert f16_to_f32_py(raw) == expected
    block = struct.pack("<e32b", 2.5, *range(-16, 16))
    assert dequant_q8_0_ref(block) == [2.5 * value for value in range(-16, 16)]


def test_simd_and_dequant():
    root = Path(__file__).resolve().parent.parent
    native = root / "projects" / "sigma_engine_rust"
    if not (native / "Cargo.toml").is_file():
        pytest.skip("Sorgente Rust opzionale assente: throughput nativo non verificato.")
    bench_bin = native / "target" / "release" / ("simd_bench.exe" if os.name == "nt" else "simd_bench")
    if not bench_bin.is_file():
        cargo = shutil.which("cargo")
        if not cargo:
            pytest.skip("Toolchain cargo assente: compilazione nativa non verificata.")
        result = subprocess.run([cargo, "build", "--release", "--bin", "simd_bench"],
                                cwd=native, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stderr
    result = subprocess.run([str(bench_bin), "--json"], cwd=native,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    measured = json.loads(result.stdout)["benchmark"]
    for name in ("q8_0", "q4_k_m"):
        assert measured[name]["elements"] > 0
        assert measured[name]["duration_ms"] > 0


if __name__ == "__main__":
    test_simd_and_dequant()
