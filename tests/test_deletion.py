"""Unit test for deterministic topic/file deletion logic in Sigma Studio."""
import os
import shutil
import tempfile
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


class TestModelDeletion(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_delete_single_file_model(self):
        from core.modules.sigma_model_hub.backend.model_inventory import delete_local_model, scan_local_models
        model_file = os.path.join(self.test_dir, "test-q4.gguf")
        with open(model_file, "wb") as f:
            f.write(b"GGUF_TEST")

        models = scan_local_models(custom_dir=self.test_dir)
        self.assertEqual(len(models), 1)

        res = delete_local_model("test-q4.gguf", custom_dir=self.test_dir)
        self.assertTrue(res.get("success"))
        self.assertFalse(os.path.exists(model_file))

    def test_delete_repo_folder_model(self):
        from core.modules.sigma_model_hub.backend.model_inventory import delete_local_model
        repo_dir = os.path.join(self.test_dir, "Qwen--Qwen2.5-Coder-1.5B")
        os.makedirs(repo_dir, exist_ok=True)
        with open(os.path.join(repo_dir, "model-00001.safetensors"), "wb") as f:
            f.write(b"WEIGHTS")

        res = delete_local_model("Qwen/Qwen2.5-Coder-1.5B", custom_dir=self.test_dir)
        self.assertTrue(res.get("success"))
        self.assertFalse(os.path.exists(repo_dir))

    def test_sandbox_prevent_outside_deletion(self):
        from core.modules.sigma_model_hub.backend.model_inventory import delete_local_model
        res = delete_local_model(self.test_dir, custom_dir=self.test_dir)
        self.assertFalse(res.get("success"))


if __name__ == "__main__":
    unittest.main()
