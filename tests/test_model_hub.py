# ==============================================================================
# tests/test_model_hub.py — Model Hub & HF Downloader API Verification
# ==============================================================================
import unittest
from fastapi.testclient import TestClient
from core.fastapi_app import app


class TestModelHubAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_hf_search_endpoint(self):
        """GET /api/models/hf/search should return 200 with popular/search results."""
        response = self.client.get("/api/models/hf/search?q=deepseek&category=reasoning")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)

    def test_hf_search_multi_dimensional_filters(self):
        """GET /api/models/hf/search with size_bracket, param_bracket, and sort."""
        # Filter by size bracket
        res_size = self.client.get("/api/models/hf/search?size_bracket=8_16gb&sort=likes")
        self.assertEqual(res_size.status_code, 200)
        data_size = res_size.json()
        self.assertTrue(data_size.get("success"))
        for item in data_size.get("results", []):
            self.assertGreater(item.get("size_gb", 0), 8.0)
            self.assertLessEqual(item.get("size_gb", 0), 16.0)

        # Filter by parameter bracket
        res_params = self.client.get("/api/models/hf/search?param_bracket=12b_14b&sort=downloads")
        self.assertEqual(res_params.status_code, 200)
        data_params = res_params.json()
        self.assertTrue(data_params.get("success"))
        for item in data_params.get("results", []):
            self.assertGreaterEqual(item.get("params_b", 0), 10.0)
        # Filter by official only
        res_official = self.client.get("/api/models/hf/search?official_only=true")
        self.assertEqual(res_official.status_code, 200)
        data_off = res_official.json()
        self.assertTrue(data_off.get("success"))
        for item in data_off.get("results", []):
            self.assertTrue(item.get("is_official", False))

        # Filter by large size bracket 32_48gb
        res_large = self.client.get("/api/models/hf/search?size_bracket=32_48gb")
        self.assertEqual(res_large.status_code, 200)
        data_large = res_large.json()
        self.assertTrue(data_large.get("success"))
        for item in data_large.get("results", []):
            self.assertGreater(item.get("size_gb", 0), 32.0)
            self.assertLessEqual(item.get("size_gb", 0), 48.0)

    def test_download_repo_endpoint(self):
        """POST /api/models/hf/download/repo should accept multi-file/repo download tasks."""
        response = self.client.post("/api/models/hf/download/repo", json={
            "model_id": "Qwen/Qwen2.5-7B-Instruct",
            "files": [
                {"filename": "config.json", "download_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/resolve/main/config.json"},
                {"filename": "tokenizer.json", "download_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/resolve/main/tokenizer.json"}
            ]
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("task", data)
        self.assertTrue(data["task"].get("is_repo_download"))
        self.assertEqual(data["task"].get("total_files"), 2)

    def test_local_models_list_endpoint(self):
        """GET /api/models/local/list should return 200 with local models list."""
        response = self.client.get("/api/models/local/list")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data.get("success"))
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)

    def test_models_config_endpoints(self):
        """GET & POST /api/models/config should save and return config correctly."""
        get_res = self.client.get("/api/models/config")
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.json()
        self.assertTrue(get_data.get("success"))
        self.assertIn("config", get_data)

        post_res = self.client.post("/api/models/config", json={
            "preferred_quantization": "Q4_K_M",
            "auto_deploy_on_download": True
        })
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.json()
        self.assertTrue(post_data.get("success"))

    def test_engine_unload_endpoint(self):
        """POST /api/models/engine/unload should return 200 and success."""
        response = self.client.post("/api/models/engine/unload")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))

    def test_engine_models_endpoint(self):
        """GET /api/engine/models should return active model, backend, and recommended presets."""
        response = self.client.get("/api/engine/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("recommended_models", data)
        self.assertIn("optimizations", data)

    def test_engine_hf_import_endpoint(self):
        """POST /api/engine/hf/import should adapt and optimize HF model for SigmaEngine."""
        response = self.client.post("/api/engine/hf/import", json={
            "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
            "quantization": "Q4_K_M"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("model", data)
        self.assertEqual(data["model"]["repo_id"], "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF")


if __name__ == "__main__":
    unittest.main()

