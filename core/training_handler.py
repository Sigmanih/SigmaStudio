# ==============================================================================
# core/training_handler.py — Facade Re-export for Training Sub-package
# Sigma Studio v7 — Modular Architecture
# ==============================================================================
"""Facade module for backward compatibility.

All training logic has been decomposed into the modular `core/training/` package:
- core/training/datasets.py  (Dataset Management & HF Search)
- core/training/hardware.py  (CUDA Hardware & VRAM Telemetry)
- core/training/jobs.py      (Training Job Lifecycle & Ollama Export)
"""

import sys
import time
import uuid
import shutil
import subprocess
from urllib.request import urlopen, Request
from urllib.parse import quote, urlencode
from urllib.error import URLError

from core.training.datasets import (
    BASE_DIR,
    TRAINING_DIR,
    DATASETS_DIR,
    FEATURED_DATASETS,
    get_featured_datasets,
    search_hf_datasets,
    get_hf_dataset_info,
    import_local_dataset,
    register_hf_dataset,
    list_imported_datasets,
    list_datasets,
    delete_dataset,
)
from core.training.hardware import (
    _check_torch_cuda,
    _query_nvidia_smi,
    _query_wmi_gpus,
    get_hardware_status,
    get_hardware_info,
    restart_ollama_service,
)
from core.training.jobs import (
    JOBS_DIR,
    SCRIPTS_DIR,
    JOBS_FILE,
    SCRIPT_TEMPLATES,
    check_training_dependencies,
    _load_jobs,
    _save_jobs,
    list_training_jobs,
    list_jobs,
    get_job_status,
    create_training_job,
    start_training_job,
    stop_training_job,
    delete_job,
    get_job_logs,
    clear_job_logs,
    export_to_ollama,
)

__all__ = [
    "sys",
    "time",
    "uuid",
    "shutil",
    "subprocess",
    "urlopen",
    "Request",
    "quote",
    "urlencode",
    "URLError",
    "BASE_DIR",
    "TRAINING_DIR",
    "DATASETS_DIR",
    "JOBS_DIR",
    "SCRIPTS_DIR",
    "JOBS_FILE",
    "FEATURED_DATASETS",
    "SCRIPT_TEMPLATES",
    "check_training_dependencies",
    "_load_jobs",
    "_save_jobs",
    "_check_torch_cuda",
    "_query_nvidia_smi",
    "get_featured_datasets",
    "search_hf_datasets",
    "get_hf_dataset_info",
    "import_local_dataset",
    "register_hf_dataset",
    "list_imported_datasets",
    "list_datasets",
    "delete_dataset",
    "get_hardware_status",
    "get_hardware_info",
    "restart_ollama_service",
    "list_training_jobs",
    "list_jobs",
    "get_job_status",
    "create_training_job",
    "start_training_job",
    "stop_training_job",
    "delete_job",
    "get_job_logs",
    "clear_job_logs",
    "export_to_ollama",
]