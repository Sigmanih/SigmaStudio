# core/orchestration/__init__.py
"""Orchestration sub-package for Sigma Studio.

Re-exports the public surface used by the rest of the codebase.
"""
from core.orchestration.agent_config import (  # noqa: F401
    AGENT_COLORS,
    get_agent_color,
    load_agent_config,
)
