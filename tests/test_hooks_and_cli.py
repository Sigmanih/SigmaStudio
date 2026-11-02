# ==============================================================================
# tests/test_hooks_and_cli.py — Test per il sistema di Hook e CLI Headless
# ==============================================================================
import unittest
import json
from unittest.mock import patch
import pytest

from core.harness.hooks import (
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


@pytest.mark.parametrize("reached,expected", [(True, 0), (False, 2)])
def test_cli_json_rispecchia_esito_reale(monkeypatch, capsys, tmp_path, reached, expected):
    from core.harness import cli
    monkeypatch.setattr("sys.argv", ["sigma", "--goal", "verifica", "--workspace", str(tmp_path), "--json"])
    monkeypatch.setattr(cli, "stream_admin_agent_turn", lambda **kw: iter([
        {"type": "run_metrics", "goal_reached": reached}, {"type": "done", "full_text": "fine"}]))
    assert cli.main() == expected
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["type"] for event in events] == ["run_metrics", "done"]


def test_cli_non_dichiara_successo_se_consegna_fallisce(monkeypatch, capsys, tmp_path):
    from core.harness import cli
    monkeypatch.setattr("sys.argv", ["sigma", "--goal", "verifica", "--workspace", str(tmp_path)])
    monkeypatch.setattr(cli, "stream_admin_agent_turn", lambda **kw: iter([
        {"type": "run_metrics", "goal_reached": True}, {"type": "worktree_preserved", "apply_failed": True}]))
    assert cli.main() == 2
    assert "SUCCESSO" not in capsys.readouterr().out


if __name__ == "__main__":
    unittest.main()
