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
    pause_training_job, resume_training_job, update_job_hyperparams,
    continue_training_job, merge_job_adapter, get_job_lineage, CONTINUATION_MODES,
    get_job_status, get_job_logs, get_job_metrics, list_jobs, clear_job_logs, export_to_ollama,
    OLLAMA_QUANT_LEVELS, check_training_dependencies,
    # hardware / accelerators
    get_hardware_info, get_gpu_capabilities, get_autotune, restart_ollama_service,
    gpu_process_inventory, terminate_gpu_process,
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
        body.get("dataset_id", ""), body.get("split", "train"), body.get("config", "")))


def handle_training_dataset_delete(self):
    self.send_json_response(delete_dataset(self.read_json_body().get("dataset_id", "")))


# ---------------------------------------------------------------- jobs

def handle_training_list_jobs(self):
    self.send_json_response(list_jobs())


def handle_training_job_status(self):
    self.send_json_response(get_job_status(_job_id(self)))


def handle_training_job_logs(self):
    self.send_json_response(get_job_logs(_job_id(self), offset=_query_int(self, "offset", 0)))


def handle_training_job_metrics(self):
    self.send_json_response(get_job_metrics(_job_id(self)))


def handle_training_job_create(self):
    self.send_json_response(create_training_job(self.read_json_body()))


def handle_training_job_continue(self):
    body = self.read_json_body()
    self.send_json_response(continue_training_job(_job_id(self), body))


def handle_training_continuation_modes(self):
    """Modi di proseguire un training, per popolare la UI."""
    self.send_json_response({"success": True, "modes": [
        {"id": key, "label": meta["label"], "detail": meta["detail"], "needs": meta["needs"]}
        for key, meta in CONTINUATION_MODES.items()]})


def handle_training_job_merge(self):
    self.send_json_response(merge_job_adapter(_job_id(self), self.read_json_body()))


def handle_training_job_lineage(self):
    self.send_json_response(get_job_lineage(_job_id(self)))


def handle_training_job_start(self):
    body = self.read_json_body()
    total = body.get("total_steps") or body.get("continue_to")
    self.send_json_response(start_training_job(_job_id(self),
                                               int(total) if total else None))


def handle_training_job_stop(self):
    self.send_json_response(stop_training_job(_job_id(self)))


def handle_training_job_pause(self):
    self.send_json_response(pause_training_job(_job_id(self)))


def handle_training_job_resume(self):
    self.send_json_response(resume_training_job(_job_id(self)))


def handle_training_job_update(self):
    body = self.read_json_body()
    self.send_json_response(update_job_hyperparams(
        _job_id(self), body.get("hyperparams") or {}))


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
        body.get("system_prompt"), body.get("quantization", "")))


def handle_training_models_local(self):
    from core.training.model_catalog import local_models
    self.send_json_response(local_models())


def handle_training_models_search(self):
    from core.training.model_catalog import search_hf_models
    query = _query(self, "q") or _query(self, "query") or ""
    self.send_json_response(search_hf_models(query, limit=_query_int(self, "limit", 25)))


def handle_training_models_pull_status(self):
    from core.training.model_catalog import pull_status
    self.send_json_response(pull_status())


def handle_training_models_import(self):
    from core.training.model_catalog import import_hf_model
    body = self.read_json_body()
    self.send_json_response(import_hf_model(
        body.get("model", ""), body.get("name", ""),
        body.get("quantization", "q4_K_M")))


def handle_training_models_pull(self):
    from core.training.model_catalog import pull_to_ollama
    self.send_json_response(pull_to_ollama(self.read_json_body().get("model", "")))


def handle_training_autopilot_status(self):
    from core.training.autopilot import status
    self.send_json_response(status(_query(self, "model") or ""))


def handle_training_autopilot_start(self):
    from core.training.autopilot import DEFAULT_ITEMS, start
    body = self.read_json_body()
    self.send_json_response(start(
        body.get("base_model", ""),
        int(body.get("items") or DEFAULT_ITEMS),
        int(body.get("max_examples") or 30000),
        body.get("train_model", ""),
        bool(body.get("trust_remote_code")),
        int(body.get("max_seq_length") or 1024)))


def handle_training_autopilot_stop(self):
    from core.training.autopilot import request_stop
    self.send_json_response(request_stop(self.read_json_body().get("model", "")))


def handle_training_autopilot_reopen(self):
    from core.training.autopilot import reopen_targets
    self.send_json_response(reopen_targets(self.read_json_body().get("model", "")))


def handle_training_autopilot_drop_rounds(self):
    from core.training.autopilot import drop_rounds
    body = self.read_json_body()
    self.send_json_response(drop_rounds(body.get("model", ""), int(body.get("quanti") or 0)))


def handle_training_autopilot_reset(self):
    from core.training.autopilot import reset
    self.send_json_response(reset(self.read_json_body().get("model", "")))


def handle_training_autopilot_cleanup(self):
    from core.training.autopilot import cleanup, load_state, save_state
    state = load_state()
    result = cleanup(state, dry_run=bool(self.read_json_body().get("dry_run")))
    save_state(state)
    self.send_json_response(result)


def handle_training_identity(self):
    """Il system prompt con cui esce un modello di Sigma Studio."""
    from core.training.identity import (SIGMA_CREATOR, SIGMA_NAME, SIGMA_PRODUCT,
                                        default_system_prompt)
    self.send_json_response({
        "success": True, "name": SIGMA_NAME, "creator": SIGMA_CREATOR,
        "product": SIGMA_PRODUCT,
        "system_prompt": default_system_prompt(),
        "system_prompt_short": default_system_prompt(compact=True),
    })


def handle_training_quant_levels(self):
    """Livelli di quantizzazione offerti dall'export, per popolare la UI."""
    self.send_json_response({"success": True, "levels": [
        {"id": key, **meta} for key, meta in OLLAMA_QUANT_LEVELS.items()]})


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


def handle_hardware_gpu_processes(self):
    """GET /api/hardware/gpu/processes — chi sta occupando la GPU adesso."""
    self.send_json_response(gpu_process_inventory())


def handle_hardware_gpu_kill(self):
    """POST /api/hardware/gpu/kill — chiude un processo che occupa la GPU."""
    body = self.read_json_body()
    pid = body.get("pid", _query(self, "pid"))
    if pid in (None, ""):
        return self.send_json_response(
            {"success": False, "error": "Manca il pid del processo da chiudere."}, 400)
    result = terminate_gpu_process(pid)
    self.send_json_response(result, 200 if result.get("success") else 409)


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
    """Modelli valutabili più stato del servizio Ollama.

    Risponde con un oggetto (non piu' un array nudo) perche' la UI deve poter
    distinguere "nessun modello installato" da "Ollama non raggiungibile": prima
    entrambi i casi arrivavano come lista vuota.
    """
    from core.training.benchmarks import get_benchmark_models_payload
    self.send_json_response(get_benchmark_models_payload())


def handle_training_benchmark_jobs(self):
    """Elenco job con sole metriche aggregate, senza il dettaglio dei quesiti."""
    from core.training.benchmarks import list_benchmark_jobs
    self.send_json_response(list_benchmark_jobs())


def handle_training_benchmark_results(self):
    """Pagina di esiti di un job, filtrabile per verdetto, suite e testo."""
    from core.training.benchmarks import get_job_detail
    self.send_json_response(get_job_detail(
        job_id=_job_id(self),
        page=_query_int(self, "page", 1),
        page_size=_query_int(self, "page_size", 15),
        verdict=_query(self, "verdict", "all"),
        suite=_query(self, "suite", "all"),
        query=_query(self, "q", ""),
    ))


def handle_training_benchmark_audit(self):
    """Verifica dei verdetti di un run: falsi positivi e falsi negativi."""
    from core.training.benchmarks import audit_benchmark_job
    self.send_json_response(audit_benchmark_job(
        _query(self, "id") or _query(self, "job_id")
        or self.read_json_body().get("id", "")))


def handle_training_benchmark_review(self):
    """Quesiti da valutare a parte: risposta duplice, illeggibile o in errore."""
    from core.training.benchmarks import get_review_queue
    self.send_json_response(get_review_queue(_job_id(self)))


# ---------------------------------------------------------------- capacita' parallela

def handle_training_benchmark_capacity(self):
    """Quante richieste in parallelo regge un modello: stima e ultima misura."""
    from core.training.capacity import estimate_capacity, get_profile
    model = _query(self, "model")
    if not model:
        return self.send_json_response({"success": False, "error": "Parametro 'model' mancante"}, 400)
    self.send_json_response({
        "success": True,
        "model": model,
        "estimate": estimate_capacity(model),
        "profile": get_profile(model),
    })


def handle_training_benchmark_capacity_probe(self):
    """Avvia la misura empirica della concorrenza utile per un modello."""
    from core.training.capacity import DEFAULT_LEVELS, start_capacity_probe
    body = self.read_json_body()
    model = body.get("model", "")
    if not model:
        return self.send_json_response({"success": False, "error": "Parametro 'model' mancante"}, 400)
    levels = body.get("levels") or list(DEFAULT_LEVELS)
    self.send_json_response(start_capacity_probe(model, levels))


def handle_training_benchmark_capacity_status(self):
    """Stato di una misura di capacita' in corso."""
    from core.training.capacity import get_probe_status
    self.send_json_response(get_probe_status(_query(self, "probe_id")))


# ---------------------------------------------------------------- pool di endpoint

def handle_training_benchmark_endpoints(self):
    """Servitori Ollama nel pool, GPU disponibili e comandi per aggiungerne."""
    from core.training.capacity import cuda_devices
    from core.training.endpoints import active_endpoints, free_port, instance_command, managed_instances

    endpoints = active_endpoints()
    bound = {e.get("gpu_index") if e.get("gpu_index") is not None else 0
             for e in endpoints if e.get("reachable")}
    devices = cuda_devices()

    port = free_port()
    suggestions = []
    for device in devices:
        if device["index"] in bound:
            continue
        # Una porta diversa per ogni suggerimento: proporle tutte uguali
        # farebbe fallire il secondo avvio.
        suggestions.append({
            "gpu": device,
            **instance_command(device["index"], port + len(suggestions), device.get("backend", "cuda")),
        })

    self.send_json_response({
        "success": True,
        "endpoints": endpoints,
        "gpus": devices,
        "managed": managed_instances(),
        "suggestions": suggestions,
    })


def handle_training_benchmark_endpoint_start(self):
    """Avvia un servitore Ollama legato a una GPU e lo aggiunge al pool."""
    from core.training.capacity import cuda_devices
    from core.training.endpoints import start_instance

    body = self.read_json_body()
    if body.get("gpu_index") is None:
        return self.send_json_response({"success": False, "error": "Parametro 'gpu_index' mancante"}, 400)
    gpu_index = int(body["gpu_index"])
    backend = next((d.get("backend", "cuda") for d in cuda_devices() if d["index"] == gpu_index), "cuda")
    port = body.get("port")
    self.send_json_response(start_instance(
        gpu_index=gpu_index,
        port=int(port) if port else None,
        backend=backend,
    ))


def handle_training_benchmark_endpoint_stop(self):
    from core.training.endpoints import stop_instance
    port = self.read_json_body().get("port")
    if not port:
        return self.send_json_response({"success": False, "error": "Parametro 'port' mancante"}, 400)
    self.send_json_response(stop_instance(int(port)))


def handle_training_benchmark_endpoint_add(self):
    """Registra un endpoint esterno (altra macchina, servizio già avviato)."""
    from core.training.endpoints import add_endpoint
    body = self.read_json_body()
    self.send_json_response(add_endpoint(
        body.get("url", ""), body.get("gpu_index"), body.get("label", "")))


def handle_training_benchmark_endpoint_remove(self):
    from core.training.endpoints import remove_endpoint
    self.send_json_response(remove_endpoint(self.read_json_body().get("url", "")))


def handle_training_benchmark_run(self):
    from core.training.benchmarks import start_benchmark_run
    body = self.read_json_body()
    job = start_benchmark_run(
        model_name=body.get("model", "qwen2.5-coder:14b"),
        suite_id=body.get("suite", "all"),
        num_samples=int(body.get("samples", 0)),
        mode=body.get("mode", "full"),
        # Non convertito a int qui: "auto" e' un valore valido, e la traduzione
        # in un numero spetta a core.training.capacity, che conosce l'hardware.
        concurrency=body.get("concurrency", "auto"),
    )
    self.send_json_response({"success": True, "job": job})


def handle_training_benchmark_delete(self):
    from core.training.benchmarks import delete_benchmark_job
    ok = delete_benchmark_job(self.read_json_body().get("id", ""))
    self.send_json_response({"success": ok})


def handle_training_benchmark_cancel(self):
    from core.training.benchmarks import cancel_benchmark_job
    ok = cancel_benchmark_job(self.read_json_body().get("id", ""))
    self.send_json_response({"success": ok})


def handle_training_benchmark_pause(self):
    from core.training.benchmarks import pause_benchmark_job
    ok = pause_benchmark_job(self.read_json_body().get("id", ""))
    self.send_json_response({"success": ok})


def handle_training_benchmark_resume(self):
    from core.training.benchmarks import resume_benchmark_job
    ok = resume_benchmark_job(self.read_json_body().get("id", ""))
    self.send_json_response({"success": ok})


# ---------------------------------------------------------------- registration

def handle_training_benchmark_suite_info(self):
    from core.training.benchmarks import get_suite_info
    self.send_json_response(get_suite_info(_query(self, "suite", "all") or "all"))


def handle_training_benchmark_download(self):
    from core.training.benchmarks import download_suite
    self.send_json_response(download_suite(self.read_json_body().get("suite", "all")))


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
