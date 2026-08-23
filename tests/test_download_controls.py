# ==============================================================================
# tests/test_download_controls.py — Unit Tests for Pause, Resume & Remove Download
# ==============================================================================
import pytest
from core.modules.sigma_model_hub.backend.downloader_engine import downloader_manager, ModelDownloadTask


def test_pause_and_resume_download_task():
    """Verify pausing and resuming downloads transitions states correctly."""
    task_id = "test-task-1"
    task = ModelDownloadTask(
        task_id=task_id,
        model_id="test/sample-model",
        filename="sample-model.gguf",
        download_url="https://example.com/sample.gguf",
        save_path="/tmp/sample.gguf",
        status="downloading",
        total_bytes=1000,
        downloaded_bytes=400,
        progress_pct=40.0
    )
    with downloader_manager.lock:
        downloader_manager.tasks[task_id] = task

    # 1. Pause
    assert downloader_manager.pause_download(task_id) is True
    assert task.status == "paused"
    assert task._cancel_flag is True

    # 2. Cancel
    assert downloader_manager.cancel_download(task_id) is True
    assert task.status == "cancelled"

    # 3. Remove
    assert downloader_manager.remove_task(task_id, delete_from_disk=False) is True
    assert task_id in downloader_manager.dismissed_task_ids
    assert task_id not in downloader_manager.tasks
