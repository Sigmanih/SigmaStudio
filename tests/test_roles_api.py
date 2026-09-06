# ==============================================================================
# tests/test_roles_api.py — Test per gli endpoint REST dei Ruoli
# ==============================================================================
import unittest
from fastapi.testclient import TestClient

from core.fastapi_app import app
from core.harness import role_registry
from core.harness.roles import DEV_ROLES


class TestRolesAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        role_registry.invalidate()

    def tearDown(self):
        role_registry.invalidate()

    def test_get_roles_endpoint(self):
        res = self.client.get("/api/roles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        roles = data.get("roles", [])
        self.assertGreaterEqual(len(roles), 5)
        role_ids = [r["id"] for r in roles]
        self.assertIn("coder", role_ids)
        self.assertIn("architect", role_ids)

    def test_get_developer_roles_endpoint(self):
        res = self.client.get("/api/developer/roles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("roles", [])), 5)

    def test_save_and_reset_role_endpoint(self):
        # 1. Modifica Coder (aumenta turn budget)
        res_post = self.client.post("/api/roles", json={
            "id": "coder",
            "patch": {"max_turns": 35}
        })
        self.assertEqual(res_post.status_code, 200)
        post_data = res_post.json()
        self.assertTrue(post_data.get("success"))
        self.assertEqual(post_data["role"]["max_turns"], 35)

        # Verifica lettura aggiornata
        res_get = self.client.get("/api/roles")
        coder = next(r for r in res_get.json()["roles"] if r["id"] == "coder")
        self.assertEqual(coder["max_turns"], 35)

        # 2. Reset Coder
        res_reset = self.client.post("/api/roles/reset", json={"id": "coder"})
        self.assertEqual(res_reset.status_code, 200)
        reset_data = res_reset.json()
        self.assertTrue(reset_data.get("success"))

        # Verifica ritorno al predefinito
        res_get_after = self.client.get("/api/roles")
        coder_after = next(r for r in res_get_after.json()["roles"] if r["id"] == "coder")
        self.assertEqual(coder_after["max_turns"], DEV_ROLES["coder"].max_turns)


if __name__ == "__main__":
    unittest.main()
