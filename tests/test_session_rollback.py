# ==============================================================================
# tests/test_session_rollback.py — Test per il rollback multi-file di sessione
# ==============================================================================
import unittest
from unittest.mock import MagicMock, patch

from core.developer_studio.session_ledger import DevSessionLedger
from core.developer_studio import session_store


class TestSessionRollback(unittest.TestCase):
    """Verifica il rollback coordinato dei file modificati in una sessione."""

    @patch("core.developer_studio.fs_manager.restore_file_backup")
    @patch("core.developer_studio.session_store.load")
    @patch("core.developer_studio.session_store._path_for")
    def test_rollback_session_files_success(self, mock_path_for, mock_load, mock_restore):
        mock_load.return_value = {
            "session_id": "sess_test_123",
            "workspace_root": "c:/repo",
            "ledger": {
                "files": {
                    "src/app.py": {"reads": 1, "edits": 2, "writes": 0},
                    "src/utils.py": {"reads": 3, "edits": 0, "writes": 0},
                    "src/config.py": {"reads": 1, "edits": 0, "writes": 1},
                }
            }
        }
        mock_restore.return_value = {"success": True, "restored_path": "foo"}
        mock_file = MagicMock()
        mock_path_for.return_value = mock_file

        res = session_store.rollback_session_files("sess_test_123", workspace_root="c:/repo")

        self.assertTrue(res.get("success"))
        self.assertEqual(len(res.get("restored_files", [])), 2)
        self.assertIn("src/app.py", res["restored_files"])
        self.assertIn("src/config.py", res["restored_files"])
        self.assertNotIn("src/utils.py", res["restored_files"])  # Only read, not edited
        self.assertEqual(mock_restore.call_count, 2)


if __name__ == "__main__":
    unittest.main()
