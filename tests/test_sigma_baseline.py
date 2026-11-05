"""Il profilo Sigma non deve trasformare misure incompatibili in miglioramenti."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

pytest.importorskip("core.modules.sigma_benchmark_lab.sigma_baseline")

from core.modules.sigma_benchmark_lab.sigma_baseline import (
    compare, failure_category, is_target, summarize, placement_matches_target,
)


def job():
    return {"id": "baseline", "model": "sigma:Qwen/Qwen3.8-27B-GGUF-Q4_K_M",
            "status": "completed", "thinking_mode": "no_thinking",
            "reproducibility": {"temperature": 0, "seed": 42, "prompt_protocol": 3,
                                "grader": "v3", "protocols": {
                                    "humaneval": {"mode": "code_execution"},
                                    "mbpp": {"mode": "code_execution"}}}}


def test_sigma_identifica_il_checkpoint_e_non_il_proxy():
    from core.modules.sigma_benchmark_lab.model_resolver import resolve_underlying_model

    assert is_target("sigma:sigma")
    assert not is_target("sigma")
    assert resolve_underlying_model("sigma:sigma") == "sigma:sigma"


def row():
    return {"suite": "humaneval", "id": "he_1", "prompt": "Somma due numeri",
            "verification": {"test_code": "assert add(1, 2) == 3"},
            "execution": {"status": "passed"}, "passed": True,
            "answer_protocol": "generative-parse", "tokens": 20, "latency_ms": 1000}


@pytest.mark.parametrize("name,expected", [
    ("sigma:Qwen/Qwen3.8-27B-GGUF-Q5_K_M", True),
    ("sigma:sigmanih--Qwen-Qwen3.8-27B-GGUF-IQ2_XXS", True),
    ("sigma:Qwen/Qwen3-8B", False), ("sigma", False),
    ("sigma:Qwen/Qwen3.8-127B", False),
])
def test_target_identity(name, expected):
    assert is_target(name) is expected


@pytest.mark.parametrize("change,expected", [
    ({"error": "Connessione interrotta"}, "inference_error"),
    ({"finish_reason": "length", "execution": {"status": "failed"}, "passed": False}, "token_limit"),
    ({"execution": {"status": "timeout"}}, "timeout"),
    ({"execution": {"status": "failed", "detail": "AssertionError"}}, "wrong_result"),
    ({"execution": {"status": "failed", "detail": "SyntaxError: invalid"}}, "syntax_error"),
    ({"execution": None}, "unverified"),
])
def test_failure_requires_execution_evidence(change, expected):
    result = row()
    result.update(change)
    assert failure_category(result) == expected


def test_valid_code_stays_correct_when_only_trailing_text_is_truncated():
    result = row()
    result["finish_reason"] = "length"
    assert failure_category(result) == "passed"


def test_identical_inputs_allow_recorded_comparison():
    first = summarize(job(), [row()])
    failed = row()
    failed.update(passed=False, execution={"status": "failed", "detail": "AssertionError"})
    second = summarize(job(), [failed])
    assert compare(first, second)["delta_points"] == -100
    assert first["tokens_per_second"] == 20
    assert second["failures"] == {"wrong_result": 1}


@pytest.mark.parametrize("field", ["prompt", "verification"])
def test_changed_input_or_tests_cannot_be_compared(field):
    changed = row()
    changed[field] = "diverso" if field == "prompt" else {"test_code": "diverso"}
    result = compare(summarize(job(), [row()]), summarize(job(), [changed]))
    assert result["comparable"] is False
    assert result["delta_points"] is None


def test_missing_protocol_incomplete_or_duplicate_not_comparable():
    original = summarize(job(), [row()])
    missing = deepcopy(job())
    missing["reproducibility"].pop("grader")
    running = job()
    running["status"] = "running"
    for candidate in (summarize(missing, [row()]), summarize(running, [row()]),
                      summarize(job(), [row(), row()]), summarize(job(), [row()], True)):
        assert compare(original, candidate)["comparable"] is False


def test_changed_protocol_not_comparable():
    changed = job()
    changed["reproducibility"]["seed"] = 7
    assert not compare(summarize(job(), [row()]), summarize(changed, [row()]))["comparable"]


def test_single_gpu_requires_context_and_full_offload():
    settings = {"forced_single_gpu": True, "main_gpu": 0, "n_ctx": 8192}
    placement = {"fully_offloaded": True, "layers_on_cpu": 0}
    assert placement_matches_target(settings, placement, 0)
    assert not placement_matches_target(settings, placement, 1)
    assert not placement_matches_target({**settings, "n_ctx": 32768}, placement, 0)
    assert not placement_matches_target(settings, {"fully_offloaded": False, "layers_on_cpu": 10}, 0)
    assert not placement_matches_target(settings, {}, 0)


@pytest.mark.parametrize("cpu_layers,expected", [(0, True), (10, False)])
def test_prepare_reloads_with_explicit_context_and_rejects_cpu(monkeypatch, cpu_layers, expected):
    from core.engine import unified_runtime
    from core.modules.sigma_benchmark_lab import benchmarks, protocol_runner
    from core.modules.sigma_benchmark_lab.sigma_baseline import prepare_baseline

    model = job()["model"]
    engine = MagicMock()
    engine.hardware_profile = {"accelerators": [{"name": "RTX 5070 Ti", "device_id": 0}]}
    engine.load_native_model.return_value = {"success": True}
    engine.active_backend_instance.telemetry.return_value = {
        "forced_single_gpu": True, "main_gpu": 0, "n_ctx": 8192}
    engine.active_backend_instance.describe_placement.return_value = {
        "fully_offloaded": cpu_layers == 0, "layers_on_cpu": cpu_layers}
    monkeypatch.setattr(unified_runtime, "sigma_engine", engine)
    monkeypatch.setattr(benchmarks, "get_available_models_for_benchmark", lambda: [{"id": model}])
    monkeypatch.setattr(benchmarks, "list_benchmark_jobs", lambda: [])
    monkeypatch.setattr(protocol_runner, "list_protocol_history", lambda: [])
    result = prepare_baseline(model)
    assert result["success"] is expected
    engine.unload.assert_called_once()
    engine.load_native_model.assert_called_once_with(
        model.removeprefix("sigma:"), context_tokens=8192, target_hardware="gpu:0",
        require_full_offload=True)


def test_prepare_does_not_interrupt_active_run(monkeypatch):
    from core.modules.sigma_benchmark_lab import benchmarks
    from core.modules.sigma_benchmark_lab.sigma_baseline import prepare_baseline

    monkeypatch.setattr(benchmarks, "list_benchmark_jobs", lambda: [{"status": "loading_model"}])
    assert prepare_baseline(job()["model"])["success"] is False


def test_report_uses_bounded_pages_and_separates_protocol(monkeypatch):
    from core.modules.sigma_benchmark_lab import benchmarks, benchmark_store, protocol_runner
    from core.modules.sigma_benchmark_lab.sigma_baseline import get_baseline_report

    monkeypatch.setattr(benchmarks, "list_benchmark_jobs", lambda: [job()])
    calls = []

    def page(job_id, page, page_size, suite):
        calls.append((page, page_size))
        return {"results": [row()] if suite == "humaneval" else [], "pages": 100, "total": 20000}

    monkeypatch.setattr(benchmark_store, "read_page", page)
    monkeypatch.setattr(protocol_runner, "list_protocol_history", lambda: [])
    report = get_baseline_report()
    assert len(calls) == 8
    assert all(size == 200 for _, size in calls)
    assert report["runs"][0]["truncated"] is True
    assert report["runs"][0]["comparable"] is False
    assert report["protocol_runs"] == []
