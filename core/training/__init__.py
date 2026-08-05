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
    _query_rocm_smi,
    _query_wmi_gpus,
    get_hardware_status,
    get_hardware_info,
    get_gpu_capabilities,
    get_autotune,
    restart_ollama_service,
)
from core.training.fwe import (  # noqa: F401
    FWE_TARGETS,
    FWE_DATASETS,
    fwe_available,
    fwe_defaults,
    fwe_status,
    list_fwe_runs,
    run_engine_selftest,
)
from core.training.jobs import (  # noqa: F401
    JOBS_DIR,
    SCRIPTS_DIR,
    JOBS_FILE,
    SCRIPT_TEMPLATES,
    METHOD_LABELS,
    resolve_dataset,
    resolve_base_model,
    reconcile_jobs,
    gpu_process_inventory,
    terminate_gpu_process,
    check_training_dependencies,
    _load_jobs,
    _save_jobs,
    list_training_jobs,
    list_jobs,
    get_job_status,
    create_training_job,
    start_training_job,
    continue_training_job,
    merge_job_adapter,
    get_job_lineage,
    CONTINUATION_MODES,
    stop_training_job,
    pause_training_job,
    resume_training_job,
    update_job_hyperparams,
    delete_job,
    get_job_logs,
    get_job_metrics,
    clear_job_logs,
    export_to_ollama,
    OLLAMA_QUANT_LEVELS,
)
