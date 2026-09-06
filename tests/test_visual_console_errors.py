# ==============================================================================
# tests/test_visual_console_errors.py — Test cattura errori console JS visivi
# ==============================================================================
import unittest
from unittest.mock import patch, MagicMock

from core.harness.visual import extract_console_errors, describe, capture
from core.harness.ledger import DevSessionLedger


class TestVisualConsoleErrors(unittest.TestCase):
    def test_extract_console_errors_blink_format(self):
        stderr = (
            "[14220:12888:0906/142000.123:INFO:CONSOLE(15)] \"App starting...\", source: http://localhost:8000/src/App.jsx (15)\n"
            "[14220:12888:0906/142000.150:ERROR:CONSOLE(42)] \"Uncaught ReferenceError: PipelineView is not defined\", source: http://localhost:8000/src/App.jsx (42)\n"
        )
        errors = extract_console_errors(stderr)
        self.assertEqual(len(errors), 1)
        self.assertIn("ReferenceError", errors[0]["message"])
        self.assertEqual(errors[0]["line"], "42")
        self.assertIn("App.jsx", errors[0]["source"])

    def test_extract_console_errors_type_error_and_unhandled(self):
        stderr = (
            "[8912:4400:0906/142200.500:CONSOLE:88] \"Uncaught TypeError: Cannot read properties of undefined (reading 'map')\", source: http://localhost:8000/bundle.js (88)\n"
            "Uncaught (in promise) Error: Network failed\n"
        )
        errors = extract_console_errors(stderr)
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("TypeError", errors[0]["message"])

    def test_extract_console_errors_clean_output(self):
        stderr = (
            "[14220:12888:0906/142000.123:INFO:CONSOLE(15)] \"App mounted successfully\", source: http://localhost:8000/src/App.jsx (15)\n"
            "DevTools listening on ws://127.0.0.1:9222/devtools/browser/abc\n"
        )
        errors = extract_console_errors(stderr)
        self.assertEqual(len(errors), 0)

    def test_describe_alerts_on_console_errors(self):
        result = {
            "success": False,
            "error": "Errori di console JavaScript rilevati durante la cattura: Uncaught ReferenceError: x is not defined",
            "path": "C:/temp/shot.png",
            "bytes": 50000,
            "width": 1440,
            "height": 900,
            "browser": "chrome.exe",
            "likely_blank": False,
            "has_console_errors": True,
            "console_errors": [
                {"message": "Uncaught ReferenceError: x is not defined", "source": "main.js", "line": "10"}
            ],
        }
        desc = describe(result)
        self.assertIn("Verifica visiva non riuscita", desc)
        self.assertIn("ReferenceError", desc)

    @patch("core.harness.visual.subprocess.run")
    @patch("core.harness.visual.os.path.isfile", return_value=True)
    @patch("core.harness.visual.os.path.getsize", return_value=45000)
    @patch("core.harness.visual.find_browser", return_value="C:/Program Files/Google/Chrome/Application/chrome.exe")
    def test_capture_fails_when_console_errors_present(self, mock_find, mock_size, mock_isfile, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = (
            '[1234:5678:0906/142000.123:ERROR:CONSOLE(20)] "Uncaught ReferenceError: BadComp is not defined", source: http://localhost:8000/App.js (20)\n'
        )
        mock_run.return_value = mock_proc

        res = capture("http://localhost:8000", output_path="C:/temp/sigma_shot_test.png")
        self.assertFalse(res["success"])
        self.assertTrue(res["has_console_errors"])
        self.assertIn("BadComp is not defined", res["error"])

    def test_ledger_rejects_screenshot_with_console_errors(self):
        ledger = DevSessionLedger(goal="Aggiungi vista pipeline")
        tool_result = {
            "success": False,
            "error": "Errori di console JavaScript rilevati",
            "path": "shot.png",
            "likely_blank": False,
            "has_console_errors": True,
            "console_errors": [{"message": "Uncaught ReferenceError", "source": "app.js", "line": "1"}],
        }
        ledger.record_tool("screenshot", {"url": "http://localhost:8000"}, tool_result)

        self.assertFalse(ledger.has_visual_proof())
        self.assertEqual(len(ledger._screenshots), 0)
        self.assertTrue(any("Errori di console" in f for f in ledger._failures))


if __name__ == "__main__":
    unittest.main()
