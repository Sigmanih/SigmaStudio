# ==============================================================================
# tests/test_loop_handler.py — Test Suite for Autonomous Task-Driven Loop
# Sigma Studio v0.8.2 — Test Coverage Expansion
# ==============================================================================
"""Unit tests for task-driven autonomous loop: context extraction, tasks state,
and robust JSON extractor.
"""

import json
import pytest
from core.loop.verification import (
    _build_loop_filesystem_context, _get_tasks_context, _extract_json_from_response
)


class TestLoopVerification:
    """Test filesystem context inspection and JSON parsing for autonomous loop."""

    def test_build_loop_filesystem_context(self):
        """Filesystem context string contains data directory contents."""
        ctx = _build_loop_filesystem_context()
        assert isinstance(ctx, str)

    def test_get_tasks_context(self):
        """Tasks context retrieves valid JSON string."""
        tasks_ctx = _get_tasks_context()
        assert isinstance(tasks_ctx, str)
        # Should be valid JSON
        parsed = json.loads(tasks_ctx)
        assert isinstance(parsed, list)

    def test_extract_json_from_response_clean(self):
        """Robust JSON extraction from clean AI response string."""
        ai_resp = 'Ecco la pianificazione:\n{"response": "Pianificati 2 task", "tasks": [{"titolo": "T1", "descrizione": "D1"}]}'
        match = _extract_json_from_response(ai_resp)
        assert match is not None
        extracted = json.loads(match.group())
        assert extracted["response"] == "Pianificati 2 task"
        assert len(extracted["tasks"]) == 1

    def test_extract_json_from_response_with_thinking(self):
        """JSON extraction when surrounded by markdown and thinking text."""
        ai_resp = """<think>Ho analizzato la richiesta</think>
```json
{
  "response": "Esecuzione completata",
  "actions": [
    {"type": "create_file", "path": "data/test/01_base/teoria/doc.md", "content": "# Test"}
  ]
}
```
"""
        match = _extract_json_from_response(ai_resp)
        assert match is not None
        extracted = json.loads(match.group())
        assert extracted["response"] == "Esecuzione completata"
        assert len(extracted["actions"]) == 1
