# ==============================================================================
# tests/test_hf_uploader.py
# Unit and Integration Tests for Hugging Face Model Publisher
# ==============================================================================
import os
import io
import time
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from core.modules.sigma_model_hub.backend.uploader_engine import (
    ModelUploaderManager, ModelUploadTask, ProgressReader, _format_bytes
)


class TestModelUploadTask(unittest.TestCase):
    def test_task_init_and_to_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"GGUF_TEST_HEADER_DATA" * 100)
            tmp_path = f.name

        try:
            task = ModelUploadTask(
                task_id="task123",
                local_path=tmp_path,
                repo_id="testuser/my-model-q4",
                private=True,
                commit_message="Test commit"
            )
            self.assertEqual(task.task_id, "task123")
            self.assertEqual(task.repo_id, "testuser/my-model-q4")
            self.assertTrue(task.private)
            self.assertEqual(task.status, "queued")
            self.assertFalse(task.is_dir)
            self.assertEqual(task.hf_url, "https://huggingface.co/testuser/my-model-q4")

            d = task.to_dict()
            self.assertEqual(d["task_id"], "task123")
            self.assertEqual(d["status"], "queued")
            self.assertEqual(d["repo_id"], "testuser/my-model-q4")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_task_cancel(self):
        task = ModelUploadTask("task1", "nonexistent.gguf", "user/repo")
        self.assertFalse(task.is_cancelled())
        task.cancel()
        self.assertTrue(task.is_cancelled())
        self.assertEqual(task.status, "cancelled")

    def test_task_progress_update(self):
        task = ModelUploadTask("task1", "dummy.gguf", "user/repo")
        task.update_progress(500, 1000)
        self.assertEqual(task.progress_pct, 50.0)
        self.assertEqual(task.uploaded_bytes, 500)
        self.assertEqual(task.total_bytes, 1000)


class TestProgressReader(unittest.TestCase):
    def test_progress_reader_tracks_bytes(self):
        data = b"Hello Hugging Face Hub!" * 50
        raw_io = io.BytesIO(data)
        progress_calls = []

        def on_prog(cur, tot):
            progress_calls.append((cur, tot))

        reader = ProgressReader(raw_io, len(data), on_prog, lambda: False)
        chunk1 = reader.read(20)
        self.assertEqual(len(chunk1), 20)
        self.assertEqual(reader.bytes_read, 20)
        self.assertTrue(len(progress_calls) > 0)

        chunk2 = reader.read(-1)
        self.assertEqual(len(chunk2), len(data) - 20)
        self.assertEqual(reader.bytes_read, len(data))


class TestModelUploaderManager(unittest.TestCase):
    def setUp(self):
        self.mgr = ModelUploaderManager()

    def test_whoami_without_token(self):
        with patch("core.modules.sigma_model_hub.backend.uploader_engine.resolve_hf_token", return_value={"token": "", "source": "none"}):
            res = self.mgr.get_whoami(token="")
            self.assertFalse(res["authenticated"])
            self.assertIn("Nessun token", res["error"])

    def test_whoami_with_mock_user(self):
        mock_user_info = {
            "name": "sigmadev",
            "fullname": "Sigma Developer",
            "email": "dev@sigma.ai",
            "avatarUrl": "https://huggingface.co/avatar.png",
            "orgs": [{"name": "sigma-labs", "fullname": "Sigma Labs"}],
            "auth": {"accessToken": {"role": "write"}}
        }
        with patch("core.modules.sigma_model_hub.backend.uploader_engine.resolve_hf_token", return_value={"token": "hf_mock_token", "source": "input"}), \
             patch("huggingface_hub.whoami", return_value=mock_user_info):
            res = self.mgr.get_whoami("hf_mock_token")
            self.assertTrue(res["authenticated"])
            self.assertEqual(res["username"], "sigmadev")
            self.assertEqual(res["fullname"], "Sigma Developer")
            self.assertTrue(res["can_write"])
            self.assertEqual(len(res["orgs"]), 1)
            self.assertEqual(res["orgs"][0]["name"], "sigma-labs")

    def test_generate_default_model_card(self):
        task_gguf = ModelUploadTask("t1", "Llama-3.2-1B-Q4_K_M.gguf", "myuser/llama-gguf")
        card = self.mgr._generate_default_model_card(task_gguf)
        self.assertIn("tags:", card)
        self.assertIn("gguf", card)
        self.assertIn("llama.cpp", card)
        self.assertIn("myuser/llama-gguf", card)

    def test_start_upload_validation(self):
        # Non-existent file
        res = self.mgr.start_upload("/path/that/does/not/exist.gguf", "user/repo")
        self.assertFalse(res["success"])
        self.assertIn("non trovato", res["error"])

        # Invalid repo format
        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"data")
            tmp = f.name
        try:
            res = self.mgr.start_upload(tmp, "invalid-repo-without-slash")
            self.assertFalse(res["success"])
            self.assertIn("username/nome-modello", res["error"])
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @patch("huggingface_hub.HfApi")
    def test_simulated_upload_flow(self, mock_hf_api_cls):
        mock_api = MagicMock()
        mock_hf_api_cls.return_value = mock_api

        with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as f:
            f.write(b"MOCK_MODEL_WEIGHTS" * 100)
            tmp = f.name

        try:
            with patch("core.modules.sigma_model_hub.backend.uploader_engine.resolve_hf_token", return_value={"token": "hf_valid", "source": "input"}):
                res = self.mgr.start_upload(
                    local_path=tmp,
                    repo_id="sigmadev/mock-model-q4",
                    private=False,
                    token="hf_valid"
                )
                self.assertTrue(res["success"])
                task_id = res["task"]["task_id"]

                # Wait shortly for daemon thread to complete
                time.sleep(0.3)

                task = self.mgr.tasks.get(task_id)
                self.assertIsNotNone(task)
                self.assertEqual(task.status, "completed")
                self.assertEqual(task.progress_pct, 100.0)
                self.assertEqual(task.hf_url, "https://huggingface.co/sigmadev/mock-model-q4")

                # Verify api calls
                mock_api.create_repo.assert_called_once()
                self.assertTrue(mock_api.upload_file.call_count >= 1)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
