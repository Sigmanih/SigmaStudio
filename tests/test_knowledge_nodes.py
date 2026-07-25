# ==============================================================================
# tests/test_knowledge_nodes.py — Test Suite for Universal Knowledge Nodes
# ==============================================================================
import os
import shutil
import unittest
from core.data_handler import rebuild_modules_meta


class TestKnowledgeNodes(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join("data", "test_domain", "app_demo")
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write("<h1>App Demo Test</h1>")
        with open(os.path.join(self.test_dir, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('Demo App Running')")

    def tearDown(self):
        if os.path.exists(os.path.join("data", "test_domain")):
            shutil.rmtree(os.path.join("data", "test_domain"))

    def test_node_tree_rebuild(self):
        """Verify that rebuild_modules_meta constructs recursive node graph with apps."""
        meta = rebuild_modules_meta()
        nodes = meta.get("nodes", {})
        self.assertIn("test_domain/app_demo", nodes)

        app_node = nodes["test_domain/app_demo"]
        self.assertEqual(app_node["id"], "test_domain/app_demo")
        self.assertEqual(app_node["parent_id"], "test_domain")
        self.assertTrue(app_node.get("has_app"))
        self.assertGreaterEqual(len(app_node.get("files", [])), 2)


if __name__ == "__main__":
    unittest.main()
