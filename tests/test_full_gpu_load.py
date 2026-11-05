"""Un esperimento interamente su GPU deve fallire se richiede offload CPU."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.engine.backends import llamaserver_backend as native
from core.engine import llama_runtime, load_overrides, gpu_lease


@pytest.mark.parametrize("richiesta,ricarica", [(None, False), ("gpu:0", False), ("auto", True)])
def test_generazione_conserva_gpu_esplicita_se_non_richiesto_altrimenti(richiesta, ricarica):
    from core.engine.unified_runtime import UniversalSigmaEngine

    backend = MagicMock()
    backend.generate_stream.return_value = iter([{"token": "ok"}])
    motore = SimpleNamespace(
        loaded_model_name="candidate", has_resident_model=True,
        loaded_model={"path": "candidate", "target_hardware": "gpu:0"},
        find_valid_model_directory=lambda name: ("candidate", "candidate"),
        unload=MagicMock(), load_native_model=MagicMock(),
        active_backend_instance=backend, _as_messages=lambda *args: [],
    )
    flusso = UniversalSigmaEngine._generate_stream_locked(
        motore, model_name="candidate", target_hardware=richiesta,
        params=SimpleNamespace(temperature=0, max_tokens=8))
    try:
        evento = next(flusso)
        assert bool(evento.get("loading")) is ricarica
        assert motore.unload.called is ricarica
        if not ricarica:
            assert evento["token"] == "ok"
            motore.load_native_model.assert_not_called()
    finally:
        flusso.close()


@pytest.fixture
def isolated_loader(tmp_path, monkeypatch):
    backend = native.LlamaServerBackend()
    facts = SimpleNamespace(name="candidate", path=str(tmp_path), num_hidden_layers=64)
    settings = {"n_gpu_layers": 32, "n_ctx": 6144, "main_gpu": 0,
                "forced_single_gpu": True, "split_mode": "none", "n_batch": 128}
    process = MagicMock()
    process.poll.return_value = 1
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(llama_runtime, "installed_server", lambda: Path(tmp_path) / "llama-server")
    monkeypatch.setattr(llama_runtime, "runtime_env", lambda: {})
    monkeypatch.setattr(native.gguf_planner, "placement_is_impossible", lambda *args: None)
    monkeypatch.setattr(native.gguf_planner, "_plan_settings", lambda *args, **kw: dict(settings))
    monkeypatch.setattr(load_overrides, "apply_to", lambda values, name: values)
    monkeypatch.setattr(gpu_lease, "apply_to_llama_command", lambda *args: None)
    monkeypatch.setattr(native, "_assign_kill_on_close", lambda process: None)
    monkeypatch.setattr(native.atexit, "register", lambda *args: None)
    monkeypatch.setattr(native.subprocess, "Popen", popen)
    monkeypatch.setattr(backend, "_file_gguf", lambda facts: str(tmp_path / "candidate.gguf"))
    monkeypatch.setattr(backend, "_find_mmproj_file", lambda facts: None)
    monkeypatch.setattr(backend, "_find_lora_file", lambda facts: None)
    monkeypatch.setattr(backend, "_avvia_lettore_uscita", lambda: None)
    monkeypatch.setattr(backend, "_attendi_pronto", lambda *args, **kw: (True, ""))
    yield backend, facts, settings, popen
    backend.unload()


def test_full_gpu_load_preserves_requested_context(isolated_loader):
    backend, facts, settings, popen = isolated_loader
    result = backend.load(facts, {}, context_tokens=8192, require_full_offload=True)
    assert result["success"]
    command = popen.call_args.args[0]
    assert command[command.index("-ngl") + 1] == "-1"
    assert command[command.index("-c") + 1] == "8192"
    assert result["settings"]["n_ctx"] == 8192
    assert settings["n_gpu_layers"] == 32


def test_default_load_keeps_planner_decisions(isolated_loader):
    backend, facts, _, popen = isolated_loader
    result = backend.load(facts, {}, context_tokens=8192)
    assert result["success"]
    command = popen.call_args.args[0]
    assert command[command.index("-ngl") + 1] == "32"
    assert command[command.index("-c") + 1] == "6144"


def test_full_gpu_rejects_implicit_device(isolated_loader):
    backend, facts, settings, popen = isolated_loader
    settings["forced_single_gpu"] = False
    assert not backend.load(facts, {}, require_full_offload=True)["success"]
    popen.assert_not_called()


def test_cuda_failure_does_not_silently_retry_on_cpu(isolated_loader, monkeypatch):
    backend, facts, _, popen = isolated_loader
    monkeypatch.setattr(backend, "_attendi_pronto", lambda *args, **kw: (False, "CUDA error: out of memory"))
    monkeypatch.setattr(backend, "_raccogli_uscita", lambda: "CUDA error: out of memory")
    fallback = MagicMock()
    monkeypatch.setattr(native, "_scalini_cuda", fallback)
    assert not backend.load(facts, {}, require_full_offload=True)["success"]
    assert popen.call_count == 1
    fallback.assert_not_called()
