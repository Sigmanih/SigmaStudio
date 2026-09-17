# ==============================================================================
# tools/benchmark_engine_comparison.py — Benchmark comparativo SigmaEngine
#
# Misura le metriche prestazionali del kernel nativo in Rust rispetto
# all'orchestrazione Python:
# - TTFT (Time To First Token)
# - Throughput di generazione (Decode t/s ed E2E t/s)
# - Latenza esecuzione tool (50 tool calls consecutive)
# - Memory Tiering & Zero-Copy Mmap
# ==============================================================================
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict


def test_rust_kernel_metrics(url: str = "http://localhost:8090") -> Dict[str, Any]:
    """Interroga gli endpoint di stato e benchmark di SigmaEngine Rust."""
    results = {}
    
    # 1. Health check
    t0 = time.perf_counter()
    req = urllib.request.Request(f"{url}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        results["health_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        results["health_data"] = json.loads(resp.read().decode("utf-8"))

    # 2. Engine status & hardware
    req = urllib.request.Request(f"{url}/api/engine/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        results["status_data"] = json.loads(resp.read().decode("utf-8"))

    # 3. Models list
    t0 = time.perf_counter()
    req = urllib.request.Request(f"{url}/v1/models")
    with urllib.request.urlopen(req, timeout=5) as resp:
        results["models_latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        results["models_count"] = json.loads(resp.read().decode("utf-8")).get("total_models", 0)

    # 4. Partitioning / Memory Tiering su modello reale
    t0 = time.perf_counter()
    payload = json.dumps({
        "model": "google--gemma-4-12B-it.Q4_K_M.gguf",
        "total_layers": 40
    }).encode("utf-8")
    req = urllib.request.Request(f"{url}/api/engine/partition", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        results["partition_latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        results["partition_plan"] = json.loads(resp.read().decode("utf-8"))

    # 5. Benchmark suite & Tool calls
    payload = json.dumps({"model": "Qwen3.8-27B"}).encode("utf-8")
    req = urllib.request.Request(f"{url}/api/bench/run", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        results["bench_data"] = json.loads(resp.read().decode("utf-8"))

    # 6. Agent pipeline deterministica (Read -> Taskify -> Execute -> Verify)
    t0 = time.perf_counter()
    payload = json.dumps({
        "session_id": "bench_test_session",
        "prompt": "Esegui analisi del workspace e diagnostica hardware"
    }).encode("utf-8")
    req = urllib.request.Request(f"{url}/api/agent/run", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        results["agent_latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        results["agent_result"] = json.loads(resp.read().decode("utf-8"))

    return results


if __name__ == "__main__":
    print("Avvio rilevamento metriche SigmaEngine Rust...")
    try:
        metrics = test_rust_kernel_metrics()
        print(json.dumps(metrics, indent=2))
    except Exception as e:
        print(f"Errore durante l'esecuzione del benchmark: {e}")
