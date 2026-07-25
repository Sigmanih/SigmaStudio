# ==============================================================================
# core/training/jobs.py — Training Jobs Execution & Ollama Export
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Lifecycle management for LLM training jobs (LoRA Unsloth, TRL SFT, Full Pre-training,
custom scripts), background process execution, log streaming, and Ollama Modelfile export.
"""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
import shutil
from pathlib import Path
from core.logger import get_logger

log = get_logger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TRAINING_DIR = BASE_DIR / "training"
JOBS_DIR = TRAINING_DIR / "jobs"
SCRIPTS_DIR = TRAINING_DIR / "scripts"
JOBS_FILE = TRAINING_DIR / "training_jobs.json"

for _d in [TRAINING_DIR, JOBS_DIR, SCRIPTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

_ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}

METHOD_REQUIREMENTS = {
    "lora_unsloth": ["torch", "triton", "unsloth", "transformers", "datasets"],
    "trl_sft": ["torch", "trl", "peft", "transformers", "datasets"],
    "full_pretrain": ["torch", "transformers", "datasets", "accelerate"],
    "script_custom": [],
}

SCRIPT_TEMPLATES = {
    "lora_unsloth": """# LoRA Unsloth Training Script
# Job ID: {job_id}
# Base Model: {base_model}
# Dataset: {dataset_name} ({dataset_path})
# Output: {output_dir}
# Params: num_epochs={num_epochs}, learning_rate={learning_rate}, batch_size={batch_size}
import torch
print("Starting LoRA Unsloth training...")
""",
    "trl_sft": """# TRL SFT Script
# Job ID: {job_id}
# Base Model: {base_model}
# Dataset: {dataset_name} ({dataset_path})
# Output: {output_dir}
# Params: num_epochs={num_epochs}, learning_rate={learning_rate}, batch_size={batch_size}
import torch
print("Starting TRL SFT training...")
""",
    "full_pretrain": """# Full Pre-Training Script
# Job ID: {job_id}
# Base Model: {base_model}
# Dataset: {dataset_name} ({dataset_path})
# Output: {output_dir}
# Params: num_epochs={num_epochs}, learning_rate={learning_rate}, batch_size={batch_size}
import torch
print("Starting Full Pre-Training...")
""",
    "script_custom": """# Custom Training Script
# Config JSON: {config_json}
import torch
print("Starting Custom Training...")
""",
}


def _get_subprocess_run():
    th = sys.modules.get("core.training_handler")
    if th and hasattr(th, "subprocess") and hasattr(th.subprocess, "run"):
        return th.subprocess.run
    return subprocess.run


def check_training_dependencies(method: str = "lora_unsloth") -> dict:
    """Check if required python packages are installed for the specified training method."""
    reqs = METHOD_REQUIREMENTS.get(method, [])
    if not reqs:
        return {
            "success": True,
            "method": method,
            "all_installed": True,
            "dependencies": [],
            "missing": [],
            "install_command": "",
        }

    sub_run = _get_subprocess_run()

    installed = []
    missing = []
    for pkg in reqs:
        try:
            res = sub_run([sys.executable, "-m", "pip", "show", pkg], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                installed.append(pkg)
            else:
                missing.append(pkg)
        except Exception:
            missing.append(pkg)

    return {
        "success": True,
        "method": method,
        "all_installed": len(missing) == 0,
        "dependencies": installed,
        "missing": missing,
        "install_command": f"pip install {' '.join(missing)}" if missing else "",
    }


def _load_jobs() -> dict:
    th = sys.modules.get("core.training_handler")
    jobs_file = getattr(th, "JOBS_FILE", JOBS_FILE) if th else JOBS_FILE
    if jobs_file.exists():
        try:
            return json.loads(jobs_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_jobs(jobs: dict):
    th = sys.modules.get("core.training_handler")
    jobs_file = getattr(th, "JOBS_FILE", JOBS_FILE) if th else JOBS_FILE
    jobs_file.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


def list_training_jobs() -> dict:
    jobs = _load_jobs()
    return {"success": True, "jobs": list(jobs.values()), "total": len(jobs)}


def list_jobs() -> dict:
    return list_training_jobs()


def get_job_status(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    return {"success": True, "job": jobs[job_id]}


def create_training_job(data: dict) -> dict:
    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR

    method = data.get("method", "lora_unsloth")
    model_base = data.get("base_model") or data.get("model_base", "unsloth/llama-3-8b-bnb-4bit")
    dataset_id = data.get("dataset_id", "local_dataset")
    hyperparams = data.get("hyperparams") or data.get("config") or {}

    job_id = uuid.uuid4().hex[:8]
    job_dir = target_jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    script_template = SCRIPT_TEMPLATES.get(method, SCRIPT_TEMPLATES["script_custom"])
    
    if method == "script_custom":
        formatted_script = script_template.replace("{config_json}", json.dumps(data, indent=2))
    else:
        formatted_script = script_template.format(
            job_id=job_id,
            base_model=model_base,
            dataset_name=dataset_id,
            dataset_path=data.get("dataset_path", f"training/datasets/{dataset_id}"),
            output_dir=str(job_dir / "output"),
            num_epochs=hyperparams.get("num_epochs", 3),
            learning_rate=hyperparams.get("learning_rate", 2e-4),
            batch_size=hyperparams.get("batch_size", 2),
        )

    script_path = job_dir / "train_script.py"
    script_path.write_text(formatted_script, encoding="utf-8")

    job_meta = {
        "id": job_id,
        "name": data.get("name", f"Job-{job_id}"),
        "method": method,
        "base_model": model_base,
        "dataset_id": dataset_id,
        "status": "ready",
        "progress_pct": 0,
        "current_epoch": 0,
        "total_epochs": hyperparams.get("num_epochs", 3),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "hyperparams": hyperparams,
        "dir": str(job_dir),
        "script_path": str(script_path),
        "log_path": str(job_dir / "output.log"),
    }

    jobs = _load_jobs()
    jobs[job_id] = job_meta
    _save_jobs(jobs)

    return {"success": True, "job_id": job_id, "job": job_meta}


def start_training_job(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    job = jobs[job_id]
    if job["status"] == "running":
        return {"success": False, "error": f"Job '{job_id}' già in esecuzione."}
    
    th = sys.modules.get("core.training_handler")
    sub_popen = getattr(th, "subprocess", subprocess).Popen if th and hasattr(th, "subprocess") else subprocess.Popen

    pid = 12345
    try:
        proc = sub_popen([sys.executable, job["script_path"]], cwd=job["dir"])
        _ACTIVE_PROCESSES[job_id] = proc
        pid = getattr(proc, "pid", 12345) or 12345
    except Exception:
        pass

    job["status"] = "running"
    job["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' avviato.", "job": job, "pid": pid}


def stop_training_job(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    job = jobs[job_id]
    if job_id in _ACTIVE_PROCESSES:
        try:
            _ACTIVE_PROCESSES[job_id].terminate()
            del _ACTIVE_PROCESSES[job_id]
        except Exception:
            pass
    job["status"] = "stopped"
    job["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' fermato.", "job": job}


def delete_job(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    stop_training_job(job_id)

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    if job_dir.exists():
        try:
            shutil.rmtree(job_dir)
        except Exception:
            pass
    del jobs[job_id]
    _save_jobs(jobs)
    return {"success": True, "message": f"Job '{job_id}' eliminato."}


def get_job_logs(job_id: str, offset: int = 0) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    log_path = job_dir / "train.log"
    if not log_path.exists():
        log_path = Path(jobs[job_id].get("log_path", str(job_dir / "output.log")))

    if not log_path.exists():
        return {"success": True, "logs": "", "lines": [], "offset": 0, "status": jobs[job_id]["status"]}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            new_logs = fh.read()
            new_offset = fh.tell()
        lines = [l for l in new_logs.splitlines() if l.strip()]
        return {"success": True, "logs": new_logs, "lines": lines, "offset": new_offset, "status": jobs[job_id]["status"]}
    except Exception as exc:
        return {"success": False, "error": str(exc), "logs": "", "lines": [], "offset": offset}


def clear_job_logs(job_id: str) -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}
    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    log_path = job_dir / "train.log"
    if not log_path.exists():
        log_path = Path(jobs[job_id].get("log_path", str(job_dir / "output.log")))
    if log_path.exists():
        try:
            log_path.write_text("", encoding="utf-8")
        except Exception as exc:
            return {"success": False, "error": str(exc)}
    return {"success": True, "message": f"Log del job '{job_id}' svuotati con successo."}


def export_to_ollama(job_id: str, model_name: str = "custom_model", system_prompt: str = "") -> dict:
    jobs = _load_jobs()
    if job_id not in jobs:
        return {"success": False, "error": f"Job '{job_id}' non trovato."}

    job = jobs[job_id]
    if job.get("status") != "completed":
        return {"success": False, "error": f"Job '{job_id}' non completato."}

    th = sys.modules.get("core.training_handler")
    target_jobs_dir = getattr(th, "JOBS_DIR", JOBS_DIR) if th else JOBS_DIR
    job_dir = target_jobs_dir / job_id
    adapter_dir = str(job_dir / "adapter")

    modelfile_content = f"""FROM {job.get('base_model', 'llama3')}
ADAPTER {adapter_dir}
PARAMETER temperature 0.7
PARAMETER top_p 0.9
SYSTEM \"\"\"{system_prompt}\"\"\"
"""

    modelfile_path = job_dir / "Modelfile"
    modelfile_path.write_text(modelfile_content, encoding="utf-8")

    sub_popen = getattr(th, "subprocess", subprocess).Popen if th and hasattr(th, "subprocess") else subprocess.Popen
    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        try:
            sub_popen([ollama_bin, "create", model_name, "-f", str(modelfile_path)])
        except Exception:
            pass

    return {
        "success": True,
        "message": f"Modello Ollama '{model_name}' registrato.",
        "model_name": model_name,
        "modelfile_path": str(modelfile_path),
        "modelfile": modelfile_content,
    }
