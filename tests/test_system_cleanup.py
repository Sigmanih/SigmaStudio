# ==============================================================================
# tests/test_system_cleanup.py — System Cleanup & Resource Optimization Tests
# ==============================================================================
import pytest
from core.system_cleanup import get_cleanup_stats, execute_selective_cleanup


def test_get_cleanup_stats_structure():
    stats = get_cleanup_stats()
    assert stats["success"] is True
    assert "memory" in stats
    assert "tasks" in stats
    assert "history" in stats
    assert "backups" in stats
    assert "cache" in stats
    assert "total_disk_formatted" in stats
    assert isinstance(stats["tasks"]["bytes"], int)
    assert isinstance(stats["backups"]["bytes"], int)


def test_execute_selective_cleanup_safe():
    # Test safe cache and memory purge without resetting developer tasks
    res = execute_selective_cleanup({
        "free_memory": True,
        "stop_background_tasks": False,
        "clear_tasks": False,
        "clear_history": False,
        "clear_backups": False,
        "clear_cache": True
    })
    assert res["success"] is True
    assert "cleaned" in res
    assert isinstance(res["cleaned"], list)
    assert "freed_disk_formatted" in res
