"""Unit test for deterministic topic/file deletion logic in Sigma Studio."""
import os
import shutil
import unittest
from core.task_handler import _normalize_action_path

class TestDeletionLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = "data/test_topic_delete"
        os.makedirs(os.path.join(self.test_dir, "01_base", "teoria"), exist_ok=True)
        with open(os.path.join(self.test_dir, "01_base", "teoria", "test.md"), "w", encoding="utf-8") as f:
            f.write("# Test Topic")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_topic_folder_exists(self):
        self.assertTrue(os.path.exists(self.test_dir))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "01_base", "teoria", "test.md")))

    def test_delete_folder_simulation(self):
        shutil.rmtree(self.test_dir)
        self.assertFalse(os.path.exists(self.test_dir))

    def test_path_normalization(self):
        norm = _normalize_action_path("📄 data/frattali/01_base/teoria/test.md")
        self.assertEqual(norm, "data/frattali/01_base/teoria/test.md")

if __name__ == "__main__":
    unittest.main()
