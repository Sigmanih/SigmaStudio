# tests/test_extra_models_dirs.py — Test percorsi aggiuntivi e importazione locale
import os
import shutil
import tempfile
import unittest
import json
from pathlib import Path
from unittest import mock

from core.paths import extra_models_dirs, all_models_dirs, set_extra_models_dirs
from core.model_paths import list_model_dirs, resolve_model_dir


class TestExtraModelsDirs(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sigma_test_extra_models_")
        self.main_models_dir = os.path.join(self.test_dir, "main_models")
        self.extra_models_dir1 = os.path.join(self.test_dir, "extra_models1")
        self.extra_models_dir2 = os.path.join(self.test_dir, "extra_models2")
        self.config_file = os.path.join(self.test_dir, "model_hub_config.json")
        os.makedirs(self.main_models_dir, exist_ok=True)
        os.makedirs(self.extra_models_dir1, exist_ok=True)
        os.makedirs(self.extra_models_dir2, exist_ok=True)

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({
                "models_dir": self.main_models_dir,
                "extra_models_dirs": [self.extra_models_dir1, self.extra_models_dir2]
            }, f)

        self._patcher = mock.patch("core.paths.model_hub_config_file", return_value=Path(self.config_file))
        self._patcher.start()

        from core.paths import models_dir, extra_models_dirs
        models_dir(refresh=True)
        extra_models_dirs(refresh=True)

    def tearDown(self):
        self._patcher.stop()
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_all_models_dirs_includes_extras(self):
        all_dirs = [str(p) for p in all_models_dirs(refresh=True)]
        self.assertIn(os.path.abspath(self.main_models_dir), all_dirs)
        self.assertIn(os.path.abspath(self.extra_models_dir1), all_dirs)
        self.assertIn(os.path.abspath(self.extra_models_dir2), all_dirs)


    def test_list_and_resolve_model_dir_finds_in_extra_dirs(self):
        m_dir = os.path.join(self.extra_models_dir1, "custom-model-gguf")
        os.makedirs(m_dir, exist_ok=True)
        with open(os.path.join(m_dir, "model.gguf"), "wb") as f:
            f.write(b"GGUF_TEST_HEADER")

        dirs = list_model_dirs()
        self.assertIn(os.path.abspath(m_dir), [os.path.abspath(d) for d in dirs])

        resolved = resolve_model_dir("custom-model-gguf")
        self.assertIsNotNone(resolved)
        self.assertEqual(os.path.abspath(resolved), os.path.abspath(m_dir))

    def test_delete_and_rename_in_extra_dirs(self):
        from core.modules.sigma_model_hub.backend.model_inventory import delete_local_model, rename_local_model

        m_dir = os.path.join(self.extra_models_dir1, "temp--model-to-rename")
        os.makedirs(m_dir, exist_ok=True)
        with open(os.path.join(m_dir, "model.safetensors"), "wb") as f:
            f.write(b"TEST")

        # Rename
        renamed = rename_local_model("temp--model-to-rename", "renamed--model")
        self.assertTrue(renamed.get("success"), renamed.get("error"))
        self.assertTrue(os.path.exists(os.path.join(self.extra_models_dir1, "renamed--model")))

        # Delete
        deleted = delete_local_model("renamed--model")
        self.assertTrue(deleted.get("success"), deleted.get("error"))
        self.assertFalse(os.path.exists(os.path.join(self.extra_models_dir1, "renamed--model")))

    def test_scan_local_models_multi_dir(self):
        from core.modules.sigma_model_hub.backend.model_inventory import scan_local_models
        m1 = os.path.join(self.main_models_dir, "main--model")
        os.makedirs(m1, exist_ok=True)
        with open(os.path.join(m1, "model.safetensors"), "wb") as f:
            f.write(b"MAIN")

        m2 = os.path.join(self.extra_models_dir1, "extra--model")
        os.makedirs(m2, exist_ok=True)
        with open(os.path.join(m2, "model.safetensors"), "wb") as f:
            f.write(b"EXTRA")

        models = scan_local_models()
        self.assertEqual(len(models), 2)
        names = [m["filename"] for m in models]
        self.assertIn("main/model", names)
        self.assertIn("extra/model", names)
        for m in models:
            if m["filename"] == "main/model":
                self.assertFalse(m["is_extra_dir"])
            else:
                self.assertTrue(m["is_extra_dir"])


if __name__ == "__main__":
    unittest.main()

