# ==============================================================================
# core/loop_handler.py — Facade Re-export for Loop Sub-package
# Sigma Studio v7 — Modular Architecture
# ==============================================================================
"""Facade module for backward compatibility.

All autonomous task-driven loop orchestration, task execution, verification,
and HTTP endpoint handlers have been decomposed into the modular `core/loop/` package:
- core/loop/verification.py     (Context Builder & JSON Extractor)
- core/loop/autonomous_runner.py (Autonomous 3-Phase Execution Engine & API Handlers)
"""

from core.loop.verification import (
    _build_loop_filesystem_context,
    _get_tasks_context,
    _extract_json_from_response,
)
from core.loop.autonomous_runner import (
    execute_task_driven_loop,
    handle_chat_loop,
)

__all__ = [
    "_build_loop_filesystem_context",
    "_get_tasks_context",
    "_extract_json_from_response",
    "execute_task_driven_loop",
    "handle_chat_loop",
]