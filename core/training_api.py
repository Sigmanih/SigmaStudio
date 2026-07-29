# ==============================================================================
# core/training_api.py — Training Lab & Hardware HTTP handlers (single source)
# Sigma Studio v7 — Modular Architecture
# ==============================================================================
"""One implementation of every Training Lab / Hardware Lab endpoint, registered
onto whichever handler class is serving requests.

Sigma ships two request pipelines — the legacy `http.server` handler and the
FastAPI adapter — and they used to carry their own copy of these handlers. The
copies drifted: the whole write side of the Training Lab (create/start/stop a
job, import a dataset, export to Ollama, check dependencies) existed only on the
legacy handler, so on the FastAPI server every one of those calls answered
404 "Endpoint non trovato". Defining them once here removes that failure mode.

A handler class only has to provide three things:
  * `self.path`             — request path, query string included
  * `self.read_json_body()` — parsed JSON body (empty dict when absent)
  * `self.send_json_response(data, status=200)`
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse, parse_qs

from core.logger import get_logger
from core.training_handler import (
    # dataset
    search_hf_datasets, import_local_dataset, register_hf_dataset,
    list_datasets, delete_dataset, get_featured_datasets,
    # job lifecycle
    create_training_job, start_training_job, stop_training_job, delete_job,
    get_job_status, get_job_logs, list_jobs, clear_job_logs, export_to_ollama,
    check_training_dependencies,
    # hardware / accelerators
    get_hardware_info, get_gpu_capabilities, get_autotune, restart_ollama_service,
    # Gradus FWE
    fwe_status, list_fwe_runs, run_engine_selftest,
    # SLM Forge
    forge_status, search_italian_datasets, dataset_configs, estimate_run, dataset_exists,
    search_teacher_models, model_accessible,
    list_checkpoints, checkpoint_chat, unload_checkpoint,
)

log = get_logger(__name__)

CONFIG_FILE = "config.json"


# ---------------------------------------------------------------- helpers

def _query(handler, key: str, default: str = "") -> str:
    """Read a GET query parameter from the request path."""
    return parse_qs(urlparse(handler.path).query).get(key, [default])[0]


def _query_int(handler, key: str, default: int) -> int:
    try:
        return int(_query(handler, key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _job_id(handler) -> str:
    """Job id from the query string (GET) or the JSON body (POST)."""
    from_query = _query(handler, "job_id") or _query(handler, "id")
    if from_query:
        return from_query
    body = handler.read_json_body()
    return body.get("job_id") or body.get("id") or ""


def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            log.warning("config.json non leggibile: %s", exc)
    return {}


def _save_config(cfg: dict) -> str:
    """Persist config.json. Returns an error message, empty when successful."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=4)
        return ""
    except Exception as exc:
        return str(exc)


def _mask(token: str) -> str:
    return token[:8] + "..." if len(token) > 8 else ""


# ---------------------------------------------------------------- datasets

def handle_training_list_datasets(self):
    self.send_json_response(list_datasets())


def handle_training_featured_datasets(self):
    self.send_json_response(get_featured_datasets())


def handle_training_dataset_search(self):
    query = _query(self, "q") or _query(self, "query") or self.read_json_body().get("query", "")
    self.send_json_response(search_hf_datasets(query, limit=_query_int(self, "limit", 20)))


def handle_training_dataset_import(self):
    body = self.read_json_body()
    self.send_json_response(import_local_dataset(
        body.get("path", ""), body.get("name"), body.get("format") or "auto"))


def handle_training_dataset_register_hf(self):
    body = self.read_json_body()
    self.send_json_response(register_hf_dataset(
        body.get("dataset_id", ""), body.get("split", "train")))


def handle_training_dataset_delete(self):
    self.send_json_response(delete_dataset(self.read_json_body().get("dataset_id", "")))


# ---------------------------------------------------------------- jobs

def handle_training_list_jobs(self):
    self.send_json_response(list_jobs())


def handle_training_job_status(self):
    self.send_json_response(get_job_status(_job_id(self)))


def handle_training_job_logs(self):
    self.send_json_response(get_job_logs(_job_id(self), offset=_query_int(self, "offset", 0)))


def handle_training_job_create(self):
    self.send_json_response(create_training_job(self.read_json_body()))


def handle_training_job_start(self):
    body = self.read_json_body()
    total = body.get("total_steps") or body.get("continue_to")
    self.send_json_response(start_training_job(_job_id(self),
                                               int(total) if total else None))


def handle_training_job_stop(self):
    self.send_json_response(stop_training_job(_job_id(self)))


def handle_training_job_delete(self):
    self.send_json_response(delete_job(_job_id(self)))


def handle_training_clear_logs(self):
    self.send_json_response(clear_job_logs(_job_id(self)))


def handle_training_dependencies(self):
    method = self.read_json_body().get("method") or _query(self, "method", "lora_unsloth")
    self.send_json_response(check_training_dependencies(method))


def handle_training_export_ollama(self):
    body = self.read_json_body()
    self.send_json_response(export_to_ollama(
        body.get("job_id", ""), body.get("model_name", "") or "custom_model",
        body.get("system_prompt", "")))


# ---------------------------------------------------------------- accelerators

def handle_training_hardware(self):
    self.send_json_response(get_hardware_info())


def handle_training_gpu_capabilities(self):
    self.send_json_response(get_gpu_capabilities())


def handle_training_gpu_autotune(self):
    body = self.read_json_body()
    self.send_json_response(get_autotune(
        _query(self, "method") or body.get("method", "lora_unsloth"),
        _query(self, "base_model") or body.get("base_model", ""),
        _query_int(self, "seq_len", int(body.get("seq_len") or 2048)),
    ))


def handle_hardware_status(self):
    hw_res = get_hardware_info()
    cfg = _load_config()
    hw_config = cfg.get("hardware", {
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "0,1"),
        "ollama_num_parallel": int(os.environ.get("OLLAMA_NUM_PARALLEL", 4)),
        "ollama_max_loaded_models": int(os.environ.get("OLLAMA_MAX_LOADED_MODELS", 2)),
        "num_gpu_layers": -1,
        "preferred_training_gpu": "cuda:0",
        "fp16_enabled": True,
    })
    hf_token = cfg.get("hf_token", "")
    self.send_json_response({
        "success": True,
        "hardware": hw_res.get("hardware", {}),
        "config": hw_config,
        "env": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0,1"),
            "OLLAMA_NUM_PARALLEL": os.environ.get("OLLAMA_NUM_PARALLEL", "4"),
            "OLLAMA_MAX_LOADED_MODELS": os.environ.get("OLLAMA_MAX_LOADED_MODELS", "2"),
            "HF_TOKEN": _mask(hf_token),
            "HF_HAS_TOKEN": bool(hf_token),
        },
        "hf_token": _mask(hf_token),
        "hf_has_token": bool(hf_token),
    })


def handle_hardware_config(self):
    body = self.read_json_body()
    cfg = _load_config()
    hw_cfg = cfg.get("hardware", {})
    hw_cfg.update({
        "cuda_visible_devices": body.get("cuda_visible_devices", "0,1"),
        "ollama_num_parallel": int(body.get("ollama_num_parallel", 4)),
        "ollama_max_loaded_models": int(body.get("ollama_max_loaded_models", 2)),
        "num_gpu_layers": int(body.get("num_gpu_layers", -1)),
        "preferred_training_gpu": body.get("preferred_training_gpu", "cuda:0"),
        "fp16_enabled": bool(body.get("fp16_enabled", True)),
    })
    cfg["hardware"] = hw_cfg
    error = _save_config(cfg)
    if error:
        return self.send_json_response({"success": False, "error": error}, 500)

    os.environ["CUDA_VISIBLE_DEVICES"] = hw_cfg["cuda_visible_devices"]
    os.environ["OLLAMA_NUM_PARALLEL"] = str(hw_cfg["ollama_num_parallel"])
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = str(hw_cfg["ollama_max_loaded_models"])
    self.send_json_response({"success": True, "config": hw_cfg})


def handle_hardware_restart_ollama(self):
    self.send_json_response(restart_ollama_service())


def handle_hf_token_config(self):
    """Save HF_TOKEN in config.json and export it to the environment."""
    token = self.read_json_body().get("hf_token", "")
    cfg = _load_config()
    cfg["hf_token"] = token
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACE_TOKEN"] = token
    error = _save_config(cfg)
    if error:
        return self.send_json_response({"success": False, "error": error}, 500)
    self.send_json_response({"success": True, "hf_token": _mask(token),
                             "hf_has_token": bool(token)})


# ---------------------------------------------------------------- Gradus FWE

def handle_training_fwe_status(self):
    self.send_json_response(fwe_status())


def handle_training_fwe_runs(self):
    self.send_json_response(list_fwe_runs())


def handle_training_fwe_selftest(self):
    body = self.read_json_body()
    self.send_json_response(run_engine_selftest(
        int(body.get("brick", 1)), body.get("device", "auto"), int(body.get("steps", 200))))


# ---------------------------------------------------------------- SLM Forge

def handle_training_forge_status(self):
    self.send_json_response(forge_status())


def handle_training_forge_datasets(self):
    """Ricerca dinamica dei dataset italiani sull'hub HuggingFace."""
    self.send_json_response(search_italian_datasets(
        _query(self, "q") or _query(self, "query"),
        limit=_query_int(self, "limit", 30),
        instruct=_query(self, "instruct", "") in ("1", "true", "yes"),
    ))


def handle_training_forge_configs(self):
    self.send_json_response(dataset_configs(_query(self, "dataset_id")))


def handle_training_forge_estimate(self):
    self.send_json_response({"success": True, "estimate": estimate_run(
        _query(self, "architecture", "micro"),
        _query_int(self, "seq_len", 512),
        _query_int(self, "batch_size", 8),
        _query_int(self, "max_steps", 2000),
        _query(self, "mode", "both"),
    )})


def handle_training_forge_verify(self):
    """Il dataset esiste davvero? Meglio saperlo prima di ore di pre-training."""
    self.send_json_response({"success": True,
                             "result": dataset_exists(_query(self, "dataset_id"))})


def handle_training_forge_teachers(self):
    """Insegnanti trovati sull'hub, con lo stato di accesso."""
    self.send_json_response(search_teacher_models(
        _query(self, "q") or _query(self, "query"),
        limit=_query_int(self, "limit", 30),
        italian_only=_query(self, "italian", "1") in ("1", "true", "yes"),
    ))


def handle_training_forge_verify_model(self):
    self.send_json_response({"success": True,
                             "result": model_accessible(_query(self, "model_id"))})


def handle_training_forge_checkpoints(self):
    self.send_json_response(list_checkpoints(_job_id(self)))


def handle_training_forge_chat(self):
    body = self.read_json_body()
    self.send_json_response(checkpoint_chat(
        job_id=body.get("job_id", ""),
        checkpoint=body.get("checkpoint", ""),
        prompt=body.get("prompt", ""),
        max_new_tokens=int(body.get("max_new_tokens", 120)),
        temperature=float(body.get("temperature", 0.8)),
        top_p=float(body.get("top_p", 0.9)),
        training_gpus=body.get("training_gpus"),
        device_preference=body.get("device") or "cpu",
    ))


def handle_training_forge_unload(self):
    self.send_json_response(unload_checkpoint())


# ---------------------------------------------------------------- benchmarks

def handle_training_benchmark_models(self):
    from core.training.benchmarks import get_available_models_for_benchmark
    self.send_json_response(get_available_models_for_benchmark())


def handle_training_benchmark_jobs(self):
    from core.training.benchmarks import list_benchmark_jobs
    self.send_json_response(list_benchmark_jobs())


def handle_training_benchmark_run(self):
    from core.training.benchmarks import start_benchmark_run
    body = self.read_json_body()
    job = start_benchmark_run(
        body.get("model", "qwen2.5-coder:14b"),
        body.get("suite", "all"),
        int(body.get("samples", 0)),
        mode=body.get("mode", "full"),
    )
    self.send_json_response({"success": True, "job": job})


def handle_training_benchmark_delete(self):
    from core.training.benchmarks import delete_benchmark_job
    ok = delete_benchmark_job(self.read_json_body().get("id", ""))
    self.send_json_response({"success": ok})


# ---------------------------------------------------------------- registration

HANDLERS = {
    name: fn for name, fn in list(globals().items())
    if name.startswith("handle_") and callable(fn)
}


def register_training_handlers(handler_class) -> list[str]:
    """Attach every Training Lab / Hardware handler to `handler_class`.

    Call from each request pipeline (legacy http.server and FastAPI adapter) so
    both expose exactly the same endpoints.
    """
    for name, fn in HANDLERS.items():
        setattr(handler_class, name, fn)
    return sorted(HANDLERS)
