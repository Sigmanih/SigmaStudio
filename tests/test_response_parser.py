# ==============================================================================
# tests/test_response_parser.py — Unit tests for core/chat/response_parser.py
# ==============================================================================
"""Test JSON extraction, tag cleaning, and thinking extraction."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.chat.response_parser import (
    _clean_all_tags,
    _extract_json_from_response,
    _extract_done_thinking,
    _format_response,
)


class TestExtractJsonFromResponse:
    def test_valid_actions_json(self):
        content = '{"response": "ok", "actions": []}'
        match = _extract_json_from_response(content)
        assert match is not None
        assert '"response"' in match.group()

    def test_valid_tasks_json(self):
        content = '{"response": "planned", "tasks": [{"titolo": "t"}]}'
        match = _extract_json_from_response(content)
        assert match is not None

    def test_valid_done_json(self):
        content = '{"response": "done!", "done": true}'
        match = _extract_json_from_response(content)
        assert match is not None

    def test_no_response_key_returns_none(self):
        content = '{"actions": ["create_file"]}'
        match = _extract_json_from_response(content)
        assert match is None

    def test_invalid_json_returns_none(self):
        # Strings without braces should always return None
        content = "This is plain text with no JSON at all."
        match = _extract_json_from_response(content)
        assert match is None

    def test_json_missing_valid_pair_key_returns_none(self):
        # Has 'response' but no valid paired key
        content = '{"response": "hello", "other": "stuff"}'
        match = _extract_json_from_response(content)
        assert match is None

    def test_json_with_preamble_text(self):
        content = "Sure! Here's the response:\n{\"response\": \"ok\", \"actions\": []}\nDone."
        match = _extract_json_from_response(content)
        assert match is not None

    def test_empty_string_returns_none(self):
        assert _extract_json_from_response("") is None

    def test_none_returns_none(self):
        assert _extract_json_from_response(None) is None


class TestCleanAllTags:
    def test_removes_thinking_tag(self):
        content = "<thinking>I should do X</thinking>The real answer."
        cleaned, thinking = _clean_all_tags(content)
        assert "thinking>" not in cleaned
        assert thinking is not None
        assert "I should do X" in thinking

    def test_removes_response_container_tag(self):
        content = "<response>Hello!</response>"
        cleaned, _ = _clean_all_tags(content)
        assert "<response>" not in cleaned
        assert "Hello!" in cleaned

    def test_done_thinking_marker(self):
        # The exact marker is '...done thinking.' — shorter prefix won't match
        content = "I need to think...done thinking. Here is the answer."
        cleaned, thinking = _clean_all_tags(content)
        assert "Here is the answer" in cleaned

    def test_cleans_excessive_blank_lines(self):
        content = "Line 1\n\n\n\n\nLine 2"
        cleaned, _ = _clean_all_tags(content)
        assert "\n\n\n" not in cleaned

    def test_plain_text_unchanged(self):
        content = "Questa è una risposta normale senza tag."
        cleaned, thinking = _clean_all_tags(content)
        assert cleaned == content
        assert thinking is None


class TestExtractDoneThinking:
    def test_splits_on_marker(self):
        content = "I reasoned about this...done thinking. The actual answer is here."
        response, thinking = _extract_done_thinking(content)
        assert thinking is not None and "I reasoned" in thinking
        assert "actual answer" in response

    def test_no_marker_returns_unchanged(self):
        content = "No marker here at all."
        response, thinking = _extract_done_thinking(content)
        assert response == content
        assert thinking is None


class TestFormatResponse:
    def test_trims_whitespace(self):
        assert _format_response("  hello  ") == "hello"

    def test_cleans_excessive_newlines(self):
        result = _format_response("a\n\n\n\nb")
        assert "\n\n\n" not in result

    def test_none_returns_none(self):
        assert _format_response(None) is None
