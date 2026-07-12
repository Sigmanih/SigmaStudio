# core/orchestration/__init__.py
"""Orchestration sub-package for Sigma Studio.

Re-exports the public surface used by the rest of the codebase.
"""
from core.orchestration.agent_config import (  # noqa: F401
    AGENT_COLORS,
    get_agent_color,
    load_agent_config,
)
from core.orchestration.orchestrator import (  # noqa: F401
    orchestrate,
    handle_chat_orchestrate,
)
from core.orchestration.research import (  # noqa: F401
    decompose_goal_to_micro_objectives,
    generate_next_steps,
    handle_research_decompose,
    handle_research_next_steps,
    handle_research_start,
)
