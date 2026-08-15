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


if __name__ == "__main__":
    unittest.main()
