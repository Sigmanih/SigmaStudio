# ==============================================================================
# core/chat_handler.py — Facade Re-export for Chat Sub-package
# Sigma Studio v8 — Modular Architecture
# ==============================================================================
"""Facade module for backward compatibility.

All chat orchestration, response parsing, prompt building, AST code validation,
file extraction, web search, and chat execution have been decomposed into the modular
`core/chat/` package:
- core/chat/chat_runner.py    (Chat Conversation Engine & Command Handlers)
- core/chat/file_extractor.py (File Extraction, AST Validation, Diff Tracking)
- core/chat/prompt_builder.py (Manifesto & Context Assembly)
- core/chat/response_parser.py(Monologue & Tag Cleaners)
- core/chat/web_search.py     (Web Search Engine)
"""

from core.chat import (
    _TAG_PATTERNS,
    _clean_all_tags,
    _extract_json_from_response,
    _extract_english_thinking,
    _extract_bullet_thinking,
    _extract_done_thinking,
    _format_response,
    _get_time_context,
    _get_manifesto_content,
    _build_filesystem_context,
    _collect_context_files,
    _resolve_manifesto_for_model,
    _determine_agent_by_request,
    _normalize_data_path,
    _ensure_module_subfolders,
    _determine_default_module_path,
    _generate_files_summary,
    _format_conversational_summary,
    _extract_and_create_files_from_text,
    _perform_web_search,
    _sanitize_history_message,
    handle_chat,
    handle_chat_extract_files,
)

__all__ = [
    "_TAG_PATTERNS",
    "_clean_all_tags",
    "_extract_json_from_response",
    "_extract_english_thinking",
    "_extract_bullet_thinking",
    "_extract_done_thinking",
    "_format_response",
    "_get_time_context",
    "_get_manifesto_content",
    "_build_filesystem_context",
    "_collect_context_files",
    "_resolve_manifesto_for_model",
    "_determine_agent_by_request",
    "_normalize_data_path",
    "_ensure_module_subfolders",
    "_determine_default_module_path",
    "_generate_files_summary",
    "_format_conversational_summary",
    "_extract_and_create_files_from_text",
    "_perform_web_search",
    "_sanitize_history_message",
    "handle_chat",
    "handle_chat_extract_files",
]
