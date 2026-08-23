# ==============================================================================
# tests/test_system_cleanup.py — Unit Tests for System Cleanup & Shutdown
# ==============================================================================
import pytest
from core.system_cleanup import shutdown_all_tasks, clear_system_memory
from core.store import tasks_store, agent_tasks_store


def test_shutdown_all_tasks_executes_safely():
    """Verify shutdown_all_tasks runs without raising exceptions even when idle."""
    shutdown_all_tasks()


def test_clear_system_memory_resets_stores():
    """Verify clear_system_memory clears tasks_store and agent_tasks_store."""
    # Seed some dummy tasks
    tasks_store.save([{"id": 1, "titolo": "Test Task", "status": "in_corso"}])
    agent_tasks_store.save({"active_agent_task": "Running inference"})

    assert len(tasks_store.load()) == 1
    assert len(agent_tasks_store.load()) == 1

    # Purge memory
    result = clear_system_memory(clear_tasks=True, clear_history=True)

    assert result["success"] is True
    assert "tasks_roadmap" in result["cleaned"]
    assert "agent_tasks_cache" in result["cleaned"]

    # Verify stores are now empty
    assert tasks_store.load() == []
    assert agent_tasks_store.load() == {}
