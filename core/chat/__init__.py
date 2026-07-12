# core/chat/__init__.py
"""Chat sub-package for Sigma Studio.

Exports only the public surface needed by the rest of the codebase so that
external modules don't need to know the internal structure.
"""
from core.chat.response_parser import (  # noqa: F401
    _TAG_PATTERNS,
    _clean_all_tags,
    _extract_json_from_response,
    _extract_english_thinking,
    _extract_bullet_thinking,
    _extract_done_thinking,
    _format_response,
)
from core.chat.prompt_builder import (  # noqa: F401
    _get_time_context,
    _get_manifesto_content,
    _build_filesystem_context,
    _collect_context_files,
    _resolve_manifesto_for_model,
)
from core.chat.web_search import _perform_web_search  # noqa: F401
