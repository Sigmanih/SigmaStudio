# ==============================================================================
# tests/test_terminal_runner_async.py — Test per il terminal runner potenziato
# ==============================================================================
import time
import sys
import unittest

from core.developer_studio.terminal_runner import (
    execute_shell_command_sync,
    start_background_process,
    get_background_process_status,
    kill_background_process,
    list_background_processes,
)


class TestTerminalRunnerAsync(unittest.TestCase):
    """Verifica l'esecuzione sincrona, streaming e background del terminal runner."""

    def test_execute_shell_command_sync_success(self):
        cmd = "echo hello_sigma"
        res = execute_shell_command_sync(cmd, timeout_seconds=10)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("returncode"), 0)
        self.assertIn("hello_sigma", res.get("stdout", ""))

    def test_execute_shell_command_sync_timeout(self):
        # Command that sleeps longer than timeout
        if sys.platform == "win32":
            cmd = "Start-Sleep -Seconds 5"
        else:
            cmd = "sleep 5"
        res = execute_shell_command_sync(cmd, timeout_seconds=1)
        self.assertFalse(res.get("success"))
        self.assertIn("timeout", res.get("stderr", "").lower())

    def test_background_process_lifecycle(self):
        if sys.platform == "win32":
            cmd = "Start-Sleep -Seconds 10"
        else:
            cmd = "sleep 10"

        # 1. Start background process
        start_res = start_background_process(cmd, process_id="test_bg_proc_1")
        self.assertTrue(start_res.get("success"))
        self.assertEqual(start_res.get("process_id"), "test_bg_proc_1")

        # 2. Get status
        status_res = get_background_process_status("test_bg_proc_1")
        self.assertTrue(status_res.get("success"))
        self.assertTrue(status_res.get("running"))

        # 3. List
        procs = list_background_processes()
        found = any(p["process_id"] == "test_bg_proc_1" for p in procs)
        self.assertTrue(found)

        # 4. Kill
        kill_res = kill_background_process("test_bg_proc_1")
        self.assertTrue(kill_res.get("success"))

        time.sleep(0.3)
        status_after = get_background_process_status("test_bg_proc_1")
        self.assertFalse(status_after.get("running"))


if __name__ == "__main__":
    unittest.main()
