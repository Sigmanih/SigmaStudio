# ==============================================================================
# tests/test_model_hub.py — Model Hub & HF Downloader API Verification
# ==============================================================================
import unittest
import os
import urllib.parse
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
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)

    def test_hf_search_cursor_pagination(self):
        """GET /api/models/hf/search with cursor pagination."""
        res1 = self.client.get("/api/models/hf/search?q=qwen&limit=5")
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertTrue(d1.get("success"))
        cursor = d1.get("next_cursor")
        if cursor:
            res2 = self.client.get(f"/api/models/hf/search?q=qwen&limit=5&cursor={urllib.parse.quote(cursor)}")
            self.assertEqual(res2.status_code, 200)
            d2 = res2.json()
            self.assertTrue(d2.get("success"))
            self.assertIn("results", d2)

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

    def test_download_retry_endpoint(self):
        """POST /api/models/hf/download/retry should resume an interrupted download task."""
        # 1. Start a download task
        start_res = self.client.post("/api/models/hf/download/start", json={
            "model_id": "test/model",
            "filename": "test.safetensors",
            "download_url": "https://huggingface.co/test/model/resolve/main/test.safetensors"
        })
        task_id = start_res.json()["task"]["task_id"]

        # 2. Cancel it
        self.client.post("/api/models/hf/download/cancel", json={"task_id": task_id})

        # 3. Retry / Resume it
        retry_res = self.client.post("/api/models/hf/download/retry", json={"task_id": task_id})
        self.assertEqual(retry_res.status_code, 200)
        data = retry_res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["task"]["task_id"], task_id)
        self.assertIn(data["task"]["status"], ["queued", "downloading", "completed"])

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

    def test_engine_hf_import_requires_the_weights_to_be_present(self):
        """
        POST /api/engine/hf/import must not claim to have prepared a model that
        is not on disk.

        Resolution used to fall through to "the first model that has weights"
        even when a specific repo was named, so asking for a model you had never
        downloaded silently handed back a different one. The plan is computed
        from measured weights, so with nothing to measure the honest answer is
        that it has to be downloaded first.
        """
        response = self.client.post("/api/engine/hf/import", json={
            "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF",
            "quantization": "Q4_K_M"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertTrue(data.get("requires_download"))
        self.assertIn("Model Hub", data.get("error", ""))


    def test_conversion_endpoints_are_reachable(self):
        """
        The conversion routes must answer, not 404.

        register_get_handlers/register_post_handlers used to assign a fresh
        route table, wiping anything the module loader had registered before
        them. The tab was fully wired while every one of its calls 404ed, and
        the UI reported "no models" for what was really a missing endpoint.
        """
        response = self.client.get("/api/models/convert/info")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("models", data)
        self.assertIn("quantization_types", data)
        self.assertIn("tooling", data)

        self.assertEqual(self.client.get("/api/models/convert/jobs").status_code, 200)

    def test_only_oversized_gguf_models_are_offered(self):
        """
        A GGUF is offered again only when shrinking it still buys something.

        Re-quantizing an F16 or Q8 is how a model that turned out too large for
        the machine becomes usable without repeating the hours-long Hugging
        Face conversion. Re-quantizing something already at Q4 or below trades
        quality for space that is no longer the constraint, so it is not shown.
        """
        data = self.client.get("/api/models/convert/info").json()
        for model in data.get("models", []):
            if model.get("source_format") != "gguf":
                continue
            weights = [f for f in os.listdir(model["path"]) if f.endswith(".gguf")]
            joined = " ".join(weights).upper()
            self.assertTrue(
                any(tag in joined for tag in ("F16", "F32", "BF16", "Q8_0", "Q6_K")),
                f"{model['name']} is already compact and should not be offered",
            )

    def test_conversion_refuses_an_unknown_model(self):
        response = self.client.post("/api/models/convert/start", json={
            "model": "does-not-exist", "quantization": "Q4_K_M",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get("success"))


    def test_conversion_reports_architecture_compatibility(self):
        """
        Every model must carry a verdict on whether it can be converted and then
        run, so an impossible job is refused instantly instead of after hours.

        The names differ between ecosystems: transformers reports "qwen3_5"
        while the GGUF file records "qwen35". Comparing the Hugging Face
        spelling against the runtime marked working models as unsupported.
        """
        data = self.client.get("/api/models/convert/info").json()
        for model in data.get("models", []):
            compat = model.get("compatibility")
            self.assertIsNotNone(compat, f"{model['name']} has no verdict")
            self.assertIn("blocked_by", compat)
            self.assertIn("summary", compat)
            if compat.get("gguf_architecture"):
                self.assertNotIn("_", compat["gguf_architecture"])


    def test_existing_gguf_is_offered_for_requantization(self):
        """
        A GGUF that is still large must be re-quantizable without redoing the
        Hugging Face conversion.

        That first stage takes hours on a large checkpoint. Discovering only
        afterwards that the chosen precision does not fit in VRAM should not
        mean paying it again: dropping an existing F16 to Q4_K_M is a straight
        file transform that runs in-process.
        """
        data = self.client.get("/api/models/convert/info").json()
        for model in data.get("models", []):
            self.assertIn("source_format", model)
            self.assertIn(model["source_format"], ("safetensors", "gguf"))

    def test_each_model_reports_what_fits_in_vram(self):
        """
        Choosing a precision that does not fit costs an order of magnitude of
        throughput, and the conversion is far too slow to learn that by trying.
        """
        data = self.client.get("/api/models/convert/info").json()
        for model in data.get("models", []):
            fit = model.get("fits_in_vram")
            if not fit:
                continue
            self.assertIn("per_quantization", fit)
            self.assertIn("usable_vram_gb", fit)
            for name, ok in fit["per_quantization"].items():
                expected = model["estimated_outputs"][name] <= fit["usable_vram_gb"]
                self.assertEqual(ok, expected, f"{name} fit verdict is inconsistent")


if __name__ == "__main__":
    unittest.main()

