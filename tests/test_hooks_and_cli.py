# ==============================================================================
# tests/test_hooks_and_cli.py — Test per il sistema di Hook e CLI Headless
# ==============================================================================
import unittest
from unittest.mock import patch

from core.developer_studio.hooks import (
    register_pre_hook,
    register_post_hook,
    run_pre_hooks,
    run_post_hooks,
)


class TestHooksAndCli(unittest.TestCase):
    """Verifica il funzionamento degli hook pre/post tool e la CLI."""

    def test_pre_hook_interception(self):
        def blocking_hook(tool_name, params, ws):
            if tool_name == "delete" and "sensitive" in str(params):
                return {"tool": "delete", "success": False, "error": "Operazione bloccata da security hook"}
            return None

        register_pre_hook(blocking_hook)

        # 1. Non-matching call passes through
        res_pass = run_pre_hooks("read_file", {"path": "safe.py"}, ".")
        self.assertIsNone(res_pass)

        # 2. Matching call is intercepted
        res_blocked = run_pre_hooks("delete", {"path": "sensitive/keys.env"}, ".")
        self.assertIsNotNone(res_blocked)
        self.assertFalse(res_blocked["success"])
        self.assertIn("security hook", res_blocked["error"])

    def test_post_hook_recording(self):
        logged = []
        def log_hook(tool_name, params, result, ws):
            logged.append(tool_name)

        register_post_hook(log_hook)
        run_post_hooks("terminal", {"command": "dir"}, {"success": True}, ".")

        self.assertIn("terminal", logged)


if __name__ == "__main__":
    unittest.main()
