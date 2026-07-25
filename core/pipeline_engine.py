# ==============================================================================
# core/pipeline_engine.py — Facade Re-export for Pipeline Sub-package
# Sigma Studio v7 — Modular Architecture
# ==============================================================================
"""Facade module for backward compatibility.

All pipeline DAG execution, topological sorting, feedback loops, and API handlers
have been decomposed into the modular `core/pipeline/` package:
- core/pipeline/self_healing.py   (Self-Correction & Role Instructions)
- core/pipeline/report_builder.py (Checkpoints & Status Persistence)
- core/pipeline/runner.py         (DAG Execution Engine & HTTP Handlers)
"""

from core.pipeline.self_healing import (
    MAX_FEEDBACK_ITERATIONS,
    _evaluate_condition,
    _get_role_instructions,
)
from core.pipeline.report_builder import (
    PIPELINE_STATUS_DIR,
    _get_pipeline,
    _set_pipeline,
    _delete_pipeline,
    _load_checkpoints,
    _get_parallel_levels,
    _topological_sort,
    _get_upstream_nodes,
    _get_node_by_id,
    _build_connection_map,
)
from core.pipeline.runner import (
    _load_pipeline_def,
    _map_role_to_agent_id,
    _call_ai_model,
    run_pipeline,
    get_pipeline_status,
    stop_pipeline,
    handle_pipeline_start,
    handle_pipeline_status,
    handle_pipeline_stop,
)

__all__ = [
    "MAX_FEEDBACK_ITERATIONS",
    "PIPELINE_STATUS_DIR",
    "_get_pipeline",
    "_set_pipeline",
    "_delete_pipeline",
    "_load_checkpoints",
    "_get_parallel_levels",
    "_topological_sort",
    "_get_upstream_nodes",
    "_get_node_by_id",
    "_build_connection_map",
    "_evaluate_condition",
    "_get_role_instructions",
    "_load_pipeline_def",
    "_map_role_to_agent_id",
    "_call_ai_model",
    "run_pipeline",
    "get_pipeline_status",
    "stop_pipeline",
    "handle_pipeline_start",
    "handle_pipeline_status",
    "handle_pipeline_stop",
]
