# core/chat/__init__.py
"""Chat sub-package for Sigma Studio.

Exports response parsing, prompt building, file extraction, web search,
and chat conversation runner.
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
    _determine_agent_by_request,
)
from core.chat.file_extractor import (  # noqa: F401
    _normalize_data_path,
    _ensure_module_subfolders,
    _determine_default_module_path,
    _generate_files_summary,
    _format_conversational_summary,
    _extract_and_create_files_from_text,
)
from core.chat.web_search import (  # noqa: F401
    _perform_web_search,
    _search_youtube,
)
from core.chat.chat_runner import (  # noqa: F401
    _sanitize_history_message,
    handle_chat,
    handle_chat_extract_files,
)
