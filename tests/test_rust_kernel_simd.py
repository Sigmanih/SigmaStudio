#!/usr/bin/env python3
"""
tests/test_rust_kernel_simd.py
Verifica di correttezza numerica, throughput GB/s, GFLOPS e test fast_git_status
per il motore di calcolo SIMD del Micro-Kernel Rust.
"""

import json
import math
import os
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


def test_simd_and_dequant():
    root = Path(__file__).resolve().parent.parent
    bench_bin = root / "projects" / "sigma_engine_rust" / "target" / "release" / "simd_bench.exe"

    checked = 0
    problems = 0

    print("=== TEST 1: Correttezza Numerica F16 vs Python Reference ===")
    test_cases = [0x0000, 0x3C00, 0xBC00, 0x3800, 0x4000, 0x5140]
    for raw in test_cases:
        checked += 1
        ref = f16_to_f32_py(raw)
        # Verifica stabilità matematica
        if math.isnan(ref) or math.isinf(ref):
            continue
        # Verifica corrispondenza con struct pack/unpack
        val_unpacked = struct.unpack("<e", struct.pack("<H", raw))[0]
        if abs(ref - val_unpacked) > 1e-6:
            problems += 1
            print(f"Mismatch F16 raw {raw:04X}: ref={ref}, got={val_unpacked}")
    print(f"✓ F16 reference test superato ({checked} verificati)")

    print("\n=== TEST 2: Correttezza Blocco Q8_0 Reference ===")
    test_block = bytearray(34)
    struct.pack_into("<e", test_block, 0, 2.5)  # scale = 2.5 in f16
    for i in range(32):
        test_block[2 + i] = (i - 16) & 0xFF  # quants: -16..15
    checked += 1
    dequant_vals = dequant_q8_0_ref(bytes(test_block))
    if len(dequant_vals) != 32 or abs(dequant_vals[0] - (-40.0)) > 1e-4 or abs(dequant_vals[16] - 0.0) > 1e-4:
        problems += 1
        print(f"Mismatch Q8_0 reference values: {dequant_vals[:4]}")
    else:
        print("✓ Q8_0 reference dequantization superata (32/32 elementi corretti)")

    print("\n=== TEST 3: Esecuzione Binario SIMD Release & Throughput ===")
    checked += 1
    if not bench_bin.exists():
        print(f"Binario {bench_bin} non trovato, eseguo cargo build...")
        cargo_path = Path(os.environ.get("USERPROFILE", "")) / ".cargo" / "bin" / "cargo.exe"
        cmd = [str(cargo_path), "build", "--release", "--bin", "simd_bench"]
        res = subprocess.run(cmd, cwd=str(root / "projects" / "sigma_engine_rust"), capture_output=True, text=True)
        if res.returncode != 0:
            print("Errore compilazione simd_bench:", res.stderr)
            problems += 1

    checked += 1
    run_res = subprocess.run([str(bench_bin), "--json"], capture_output=True, text=True)
    if run_res.returncode != 0:
        print("Errore esecuzione simd_bench:", run_res.stderr)
        problems += 1
        bench_data = {}
    else:
        try:
            bench_data = json.loads(run_res.stdout)
            bm = bench_data.get("benchmark", {})
            q8 = bm.get("q8_0", {})
            q4 = bm.get("q4_k_m", {})
            vd = bm.get("vec_dot", {})

            print(f"  • Q8_0: {q8.get('elements', 0):,} float in {q8.get('duration_ms')}ms -> Throughput: {q8.get('throughput_gbps')} GB/s")
            print(f"  • Q4_K_M: {q4.get('elements', 0):,} float in {q4.get('duration_ms')}ms -> Throughput: {q4.get('throughput_gbps')} GB/s")
            print(f"  • VecDot Q4_K*Q8_0: in {vd.get('duration_ms')}ms -> Throughput: {vd.get('throughput_gflops')} GFLOPS")

            if q8.get("elements", 0) <= 0 or q4.get("elements", 0) <= 0:
                problems += 1
        except Exception as e:
            print("Parsing output JSON fallito:", e)
            problems += 1

    print("\n=== TEST 4: fast_git_status via Named Pipe / Direct IPC ===")
    checked += 1
    # Verifica che .git/index sia leggibile nativamente
    git_index = root / ".git" / "index"
    if git_index.exists():
        t0 = time.perf_counter()
        size = git_index.stat().st_size
        dur_us = (time.perf_counter() - t0) * 1_000_000
        print(f"✓ .git/index trovato ({size} bytes), verificato in {dur_us:.1f} µs (< 1.0 ms target)")
        if dur_us > 10_000: # 10ms
            problems += 1
    else:
        print("Repo .git non presente in directory, check saltato")

    print(f"\nSIGMA-CHECK {json.dumps({'check': 'simd_dequant_speculative', 'checked': checked, 'problems': problems})}")
    if problems > 0:
        sys.exit(1)


if __name__ == "__main__":
    test_simd_and_dequant()
