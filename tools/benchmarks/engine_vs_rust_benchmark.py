# ==============================================================================
# tools/benchmarks/engine_vs_rust_benchmark.py — Benchmark parità e throughput
# Sigma Studio v8 — Tools & Benchmarks Suite
# ==============================================================================
import time
import json
import statistics
import urllib.request
import uuid
from typing import Dict, Any


def _post(path: str, payload: dict) -> dict:
    from core.engine.backends.sigmarust_backend import _DEFAULT_RUST_URL, _intestazioni
    request = urllib.request.Request(_DEFAULT_RUST_URL + path,
        data=json.dumps(payload).encode(), headers=_intestazioni({"Content-Type": "application/json"}))
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read())


def _measure(python_call, rust_call, iterations: int) -> Dict[str, Any]:
    if not 1 <= iterations <= 10000:
        raise ValueError("iterations deve essere fra 1 e 10000")
    python_samples, rust_samples = [], []
    error = None
    parity = True
    for _ in range(iterations):
        start = time.perf_counter_ns()
        expected = python_call()
        python_samples.append((time.perf_counter_ns() - start) / 1000)
        if error is None:
            try:
                start = time.perf_counter_ns()
                actual = rust_call()
                rust_samples.append((time.perf_counter_ns() - start) / 1000)
                parity = parity and actual == expected
            except (OSError, ValueError, KeyError, TypeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
    python_us = statistics.median(python_samples)
    rust_us = statistics.median(rust_samples) if error is None and rust_samples else None
    return {"python_us": python_us, "rust_internal_us": None, "rust_roundtrip_us": rust_us,
            "speedup": python_us / rust_us if rust_us else None, "iterations": iterations,
            "rust_measured": rust_us is not None, "parity": parity if rust_us is not None else None,
            "scope": "python_in_process_vs_rust_http_roundtrip", "error": error}


def bench_prefix_cache_lookup(iterations: int = 100) -> Dict[str, Any]:
    """
    Misura il tempo di lookup e matching del prefix cache tra implementazione
    Python pura e runtime nativo/ottimizzato.
    """
    prefix = [uuid.uuid4().int & 0x7fffffff] + list(range(511))
    tokens = prefix + [1000, 1001, 1002]

    # Benchmark Python
    def python_lookup():
        common = 0
        limit = min(len(prefix), len(tokens))
        while common < limit and prefix[common] == tokens[common]:
            common += 1
        return common
    seeded = False
    def rust_lookup():
        nonlocal seeded
        if not seeded:
            _post("/api/engine/cache/insert", {"tokens": prefix, "page_id": 0})
            seeded = True
        return _post("/api/engine/cache/lookup", {"tokens": tokens})["matched_tokens"]
    return _measure(python_lookup, rust_lookup, iterations)


def bench_grammar_validation(iterations: int = 20) -> Dict[str, Any]:
    """
    Misura il throughput di validazione grammaticale (JSON/EBNF) per token.
    """
    sample_json = '{"action": "read_file", "path": "core/paths.py", "lines": [1, 50]}'
    def python_validate():
        json.loads(sample_json)
        return True
    def rust_validate():
        return _post("/api/engine/tools/execute", {"tool": "fast_lint",
            "params": {"code": sample_json, "language": "json"}})["result"]["valid"]
    return _measure(python_validate, rust_validate, iterations)


def bench_agent_event_bus(iterations: int = 20) -> Dict[str, Any]:
    """
    Misura la latenza di dispatching eventi dell'Agent Event Bus.
    """
    events = []
    session = uuid.uuid4().hex
    event = {"type": "agent_action", "payload": {"value": 1}}
    def python_publish():
        events.append(event.copy())
        return True
    def rust_publish():
        return _post("/api/agent/bus/publish", {"session_id": session,
            "agent_role": "benchmark", "event_type": "agent_action", "payload": event})["success"]
    return _measure(python_publish, rust_publish, iterations)
