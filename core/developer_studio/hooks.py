# ==============================================================================
# core/developer_studio/hooks.py — Pre/Post Tool Execution Hooks
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Provides extensible pre-tool and post-tool lifecycle hooks for custom
project workflows (e.g. running formatting, security gating, linting).
"""

from typing import Any, Callable, Dict, List, Optional
from core.logger import get_logger

log = get_logger("developer_hooks")

_PRE_HOOKS: List[Callable[[str, Dict[str, Any], str], Optional[Dict[str, Any]]]] = []
_POST_HOOKS: List[Callable[[str, Dict[str, Any], Dict[str, Any], str], None]] = []


def register_pre_hook(hook: Callable[[str, Dict[str, Any], str], Optional[Dict[str, Any]]]) -> None:
    """Registers a function called before any tool executes.

    If the hook returns a Dict, it replaces the tool execution (acts as a short-circuit/interceptor).
    """
    _PRE_HOOKS.append(hook)


def register_post_hook(hook: Callable[[str, Dict[str, Any], Dict[str, Any], str], None]) -> None:
    """Registers a function called after a tool has executed."""
    _POST_HOOKS.append(hook)


def run_pre_hooks(tool_name: str, params: Dict[str, Any], workspace_root: str) -> Optional[Dict[str, Any]]:
    """Runs all registered pre-hooks. If any hook returns a dict, returns it immediately."""
    for hook in _PRE_HOOKS:
        try:
            intercepted = hook(tool_name, params, workspace_root)
            if intercepted is not None:
                return intercepted
        except Exception as ex:
            log.warning("Pre-hook error for tool '%s': %s", tool_name, ex)
    return None


def run_post_hooks(tool_name: str, params: Dict[str, Any], result: Dict[str, Any], workspace_root: str) -> None:
    """Runs all registered post-hooks."""
    for hook in _POST_HOOKS:
        try:
            hook(tool_name, params, result, workspace_root)
        except Exception as ex:
            log.warning("Post-hook error for tool '%s': %s", tool_name, ex)
