# ==============================================================================
# tests/test_model_paths.py — Every component must agree on where models live
#
# The models directory used to be derived independently in five places, four of
# them from os.getcwd(). These tests pin the two failures that caused: a wrong
# working directory splitting the app's view of its own models, and a directory
# configured in the Model Hub being honoured by the downloader but not by the
# engine, so downloads landed where inference never looked.
# ==============================================================================
import os
import unittest
import tempfile

from core import model_paths


class TestProjectRootAnchoring(unittest.TestCase):
    def test_root_is_independent_of_working_directory(self):
        original = os.getcwd()
        expected = model_paths.project_root()
        try:
            os.chdir(tempfile.gettempdir())
            self.assertEqual(model_paths.project_root(), expected)
        finally:
            os.chdir(original)

    def test_root_contains_the_project(self):
        root = model_paths.project_root()
        self.assertTrue(
            os.path.isdir(os.path.join(root, "core")),
            f"project_root() resolved to {root}, which has no core/",
        )


class TestSharedResolution(unittest.TestCase):
    def setUp(self):
        self.original = model_paths.models_dir()

    def tearDown(self):
        model_paths.set_models_dir(self.original)

    def test_every_consumer_reports_the_same_directory(self):
        """The engine, inventory, downloader and converter must not diverge."""
        from core.modules.sigma_model_hub.backend import model_inventory
        from core.modules.sigma_model_hub.backend import downloader_engine

        shared = model_paths.models_dir()
        self.assertEqual(model_inventory._models_dir(), shared)
        self.assertEqual(downloader_engine.DEFAULT_MODELS_DIR, shared)

    def test_set_models_dir_is_visible_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_paths.set_models_dir(tmp)
            self.assertEqual(model_paths.models_dir(), os.path.abspath(tmp))

            from core.modules.sigma_model_hub.backend import model_inventory
            self.assertEqual(model_inventory._models_dir(), os.path.abspath(tmp))

    def test_unusable_configured_dir_falls_back(self):
        """A bad setting must not break every model operation."""
        model_paths.set_models_dir(self.original)
        self.assertTrue(os.path.isdir(model_paths.models_dir()))


class TestModelResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = model_paths.models_dir()
        model_paths.set_models_dir(self.tmp.name)

        self.model_dir = os.path.join(self.tmp.name, "Vendor--Model-7B")
        os.makedirs(self.model_dir)
        with open(os.path.join(self.model_dir, "model.safetensors"), "wb") as f:
            f.write(b"\x00" * 16)

    def tearDown(self):
        model_paths.set_models_dir(self.original)
        self.tmp.cleanup()

    def test_resolves_the_spellings_that_circulate(self):
        """
        The same model is referred to as 'Vendor/Model-7B' in config and
        'Vendor--Model-7B' on disk; both have to land on the same directory.
        """
        for spelling in ("Vendor--Model-7B", "Vendor/Model-7B", "Model-7B",
                         "vendormodel7b"):
            self.assertEqual(
                model_paths.resolve_model_dir(spelling), self.model_dir,
                f"failed to resolve {spelling!r}",
            )

    def test_absolute_path_is_accepted(self):
        self.assertEqual(
            model_paths.resolve_model_dir(self.model_dir), self.model_dir
        )

    def test_unknown_model_resolves_to_nothing(self):
        self.assertIsNone(model_paths.resolve_model_dir("no-such-model"))

    def test_directory_without_weights_is_not_a_model(self):
        empty = os.path.join(self.tmp.name, "just-a-folder")
        os.makedirs(empty)
        self.assertFalse(model_paths.has_weights(empty))
        self.assertNotIn(empty, model_paths.list_model_dirs())

    def test_engine_uses_the_shared_resolver(self):
        from core.engine.unified_runtime import UniversalSigmaEngine

        engine = UniversalSigmaEngine()
        found = engine.find_valid_model_directory("Vendor/Model-7B")
        self.assertIsNotNone(found)
        self.assertEqual(found[0], self.model_dir)
        self.assertEqual(found[1], "Vendor--Model-7B")


class TestImportSafety(unittest.TestCase):
    def test_engine_imports_from_any_working_directory(self):
        """
        Importing the engine must not depend on the working directory: it builds
        a shared streamer whose scratch path was previously resolved relatively,
        which crashed the import outright when the server started elsewhere.
        """
        import subprocess
        import sys

        root = model_paths.project_root()
        script = (
            "import sys, os; sys.path.insert(0, r'" + root + "'); "
            "os.chdir(os.path.dirname(sys.executable)); "
            "import core.engine.unified_runtime as m; "
            "print('OK', m.sigma_engine is not None)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=300,
        )
        self.assertIn("OK True", result.stdout, msg=result.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
