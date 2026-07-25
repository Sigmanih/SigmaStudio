# core/training/__init__.py
"""Training sub-package for Sigma Studio.

Exports all dataset, hardware, and job management functions for LLM training.
"""

from core.training.datasets import (  # noqa: F401
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
from core.training.hardware import (  # noqa: F401
    _check_torch_cuda,
    _query_nvidia_smi,
    get_hardware_status,
    get_hardware_info,
    restart_ollama_service,
)
from core.training.jobs import (  # noqa: F401
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
