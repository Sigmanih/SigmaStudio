# ==============================================================================
# tests/test_hardware_api.py — Hardware Lab API & Telemetry Verification
# ==============================================================================
import unittest
from fastapi.testclient import TestClient
from core.fastapi_app import app


class TestHardwareAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_hardware_status_endpoint(self):
        """GET /api/hardware/status should return 200 with cpu, ram, gpu telemetry."""
        response = self.client.get("/api/hardware/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("hardware", data)
        self.assertIn("cpu", data["hardware"])
        self.assertIn("ram", data["hardware"])
        self.assertIn("gpu", data["hardware"])

    def test_hardware_gpu_processes_endpoint(self):
        """GET /api/hardware/gpu/processes should return 200 with process list."""
        response = self.client.get("/api/hardware/gpu/processes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("processes", data)
        self.assertIsInstance(data["processes"], list)

    def test_hardware_config_endpoint(self):
        """POST /api/hardware/config should save and return updated configuration."""
        response = self.client.post("/api/hardware/config", json={
            "cuda_devices": "0",
            "num_parallel": 4,
            "max_loaded": 2,
            "preferred_gpu": "cuda:0"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))


    def test_hardware_gpu_kill_all_orphans(self):
        """POST /api/hardware/gpu/kill with all_orphans should return 200 and success."""
        response = self.client.post("/api/hardware/gpu/kill", json={"all_orphans": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))

    def test_hardware_protect_master_process(self):
        """POST /api/hardware/gpu/kill on master process should be safely rejected without 400."""
        import os
        response = self.client.post("/api/hardware/gpu/kill", json={"pid": os.getpid()})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("success"))
        self.assertIn("protetto", data.get("error", "").lower())


if __name__ == "__main__":
    unittest.main()

