# =======================================================================
# tests/test_backup_restore.py — Developer Studio File Backup & Restore Tests
# =======================================================================
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from core.developer_studio.fs_manager import (
    write_file_content,
    delete_fs_entry,
    backup_file_snapshot,
    list_file_backups,
    restore_file_backup,
)
from core.developer_studio.admin_agent import execute_admin_tool


@pytest.fixture
def temp_workspace():
    tmp = tempfile.mkdtemp(prefix="sigma_backup_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


def test_automatic_backup_on_write(temp_workspace):
    test_file = temp_workspace / "sample.py"
    test_file.write_text("print('version 1')", encoding="utf-8")

    # Overwrite using write_file_content passing root
    res = write_file_content(str(test_file), "print('version 2')", root=str(temp_workspace))
    assert res["success"] is True
    assert "backup_id" in res

    # Verify backup exists
    backups = list_file_backups(file_path=str(test_file), root=str(temp_workspace))
    assert len(backups) == 1
    assert "sample.py" in backups[0]["rel_path"] or backups[0]["original_path"].endswith("sample.py")

    # Check content of the modified file
    assert test_file.read_text(encoding="utf-8") == "print('version 2')"

    # Restore from backup
    restore_res = restore_file_backup(str(test_file), root=str(temp_workspace))
    assert restore_res["success"] is True
    assert test_file.read_text(encoding="utf-8") == "print('version 1')"


def test_restore_file_tool(temp_workspace):
    test_file = temp_workspace / "sigma_test.py"
    test_file.write_text("initial code", encoding="utf-8")

    # Admin agent writes new code
    res = execute_admin_tool(
        "write_file",
        {"path": "sigma_test.py", "content": "broken code"},
        workspace_root=str(temp_workspace)
    )
    assert res["success"] is True
    assert test_file.read_text(encoding="utf-8") == "broken code"

    # Admin agent lists backups
    list_res = execute_admin_tool(
        "list_backups",
        {"path": "sigma_test.py"},
        workspace_root=str(temp_workspace)
    )
    assert list_res["success"] is True
    assert list_res["count"] >= 1

    # Admin agent reverts file using restore_file tool
    restore_res = execute_admin_tool(
        "restore_file",
        {"path": "sigma_test.py"},
        workspace_root=str(temp_workspace)
    )
    assert restore_res["success"] is True
    assert test_file.read_text(encoding="utf-8") == "initial code"


def test_backup_on_delete(temp_workspace):
    test_file = temp_workspace / "to_delete.txt"
    test_file.write_text("important data", encoding="utf-8")

    # Delete
    del_res = delete_fs_entry(str(test_file), root=str(temp_workspace))
    assert del_res["success"] is True
    assert not test_file.exists()

    # Backups index still has it
    backups = list_file_backups(file_path=str(test_file), root=str(temp_workspace))
    assert len(backups) == 1

    # Can restore deleted file
    rest_res = restore_file_backup(str(test_file), root=str(temp_workspace))
    assert rest_res["success"] is True
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "important data"