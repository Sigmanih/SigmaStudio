# ==============================================================================
# core/agent_orchestrator.py — Backward compatibility wrapper
# Sigma Studio v6.2 — Modular Orchestration Engine
# ==============================================================================
"""Wrapper for backward compatibility.

Imports and exposes all orchestration and research sessions logic from the new
refactored `core.orchestration` package.
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

# Backward-compatible alias
_load_agent_config = load_agent_config