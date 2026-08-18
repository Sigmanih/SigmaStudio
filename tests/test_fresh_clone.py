# ==============================================================================
# tests/test_fresh_clone.py — A clone must start without local leftovers
#
# Everything gitignored is absent for someone who clones the repository:
# config.json, data/, the built frontend, downloaded models. These tests pin the
# things that have to hold on that machine, so a change that quietly depends on
# a file only this workstation has fails here instead of in someone's issue.
# ==============================================================================
import os
import ast
import subprocess
import sys
import unittest

from core import model_paths


ROOT = model_paths.project_root()


def _tracked_files():
    """Files git actually ships, which is all a cloner receives."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        return None
    return set(result.stdout.split("\n"))


class TestRepositoryContents(unittest.TestCase):
    def setUp(self):
        self.tracked = _tracked_files()
        if self.tracked is None:
            self.skipTest("not a git repository")

    def test_secrets_are_not_committed(self):
        """
        config.json holds the Hugging Face token and provider API keys. It must
        stay untracked; committing it publishes those credentials.
        """
        self.assertNotIn("config.json", self.tracked)
        self.assertIn("config.example.json", self.tracked,
                      "the template a cloner starts from is missing")

    def test_entry_points_are_present(self):
        for required in ("sigma_server.py", "requirements.txt",
                         "sigma_studio/package.json"):
            self.assertIn(required, self.tracked, f"{required} is not shipped")

    def test_no_absolute_local_paths_in_shipped_python(self):
        """
        A path from this workstation baked into a shipped file breaks on every
        other machine, and does so silently.
        """
        offenders = []
        for rel in sorted(self.tracked):
            if not rel.endswith(".py") or rel.startswith(("tests/", "training/")):
                continue
            full = os.path.join(ROOT, rel)
            if not os.path.isfile(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as handle:
                    body = handle.read()
            except Exception:
                continue
            for marker in ("C:/Users/", "C:\\\\Users\\\\", "/home/"):
                if marker in body:
                    offenders.append(f"{rel} contains {marker}")
        self.assertEqual(offenders, [], "\n".join(offenders))


class TestStartupIsLocationIndependent(unittest.TestCase):
    """
    The server must find its own files regardless of the working directory it
    was launched from. Resolving them relatively meant a launcher started from
    elsewhere served an empty UI and read no config.
    """

    def test_app_imports_from_an_unrelated_directory(self):
        script = (
            "import sys, os; sys.path.insert(0, r'" + ROOT + "'); "
            "os.chdir(os.path.dirname(sys.executable)); "
            "import core.fastapi_app as fa; "
            "print('DIST', fa.DIST_DIR); "
            "print('OK', fa.app is not None)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=600,
        )
        self.assertIn("OK True", result.stdout, msg=result.stderr[-1500:])
        # The UI directory must resolve under the installation, not the cwd.
        self.assertIn("sigma_studio", result.stdout)
        self.assertIn(os.path.basename(ROOT), result.stdout)

    def test_models_directory_resolves_without_config(self):
        """A cloner has no model_hub_config.json; the default must still work."""
        resolved = model_paths.models_dir()
        self.assertTrue(os.path.isabs(resolved))
        self.assertTrue(resolved.startswith(ROOT))


class TestFrontendSourceIsSound(unittest.TestCase):
    """
    The bundle is built on the cloner's machine, so a reference error in the
    source reaches them as a blank screen with a stack trace. ESLint's no-undef
    catches exactly that class of fault, and it has already shipped twice.
    """

    def test_no_undefined_variables_in_frontend(self):
        frontend = os.path.join(ROOT, "sigma_studio")
        if not os.path.isdir(os.path.join(frontend, "node_modules")):
            self.skipTest("frontend dependencies not installed")

        result = subprocess.run(
            ["npm", "run", "lint", "--", "--rule",
             '{"no-undef":"error"}', "--format", "compact"],
            cwd=frontend, capture_output=True, text=True, timeout=900, shell=True,
        )
        # Compact format reports problems as "path: line X, col Y, Error - ...".
        # npm also echoes the command it runs, which mentions the rule name
        # too, so match reported problems rather than any mention of it.
        undefined = []
        for line in (result.stdout or "").splitlines():
            if "no-undef" in line and "Error -" in line:
                undefined.append(line.strip())
        self.assertEqual(
            undefined, [],
            "undefined variables would crash the UI at runtime:\n"
            + "\n".join(undefined),
        )


if __name__ == "__main__":
    unittest.main()
