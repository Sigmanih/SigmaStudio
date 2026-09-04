# ==============================================================================
# tests/test_multi_tool_execution.py — Test per l'estrazione e uso multi-tool
# ==============================================================================
import unittest

from core.developer_studio.admin_agent import extract_tool_invocations, execute_admin_tool


class TestMultiToolExecution(unittest.TestCase):
    """Verifica l'estrazione di chiamate multiple di tool da un singolo messaggio."""

    def test_extract_multiple_fenced_tools(self):
        text = """
Analizzo i file richiesti:

```tool:read_file
{"path": "core/paths.py"}
```

E verifico anche la lista directory:

```tool:list_dir
{"path": "core"}
```
"""
        calls = extract_tool_invocations(text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["tool"], "read_file")
        self.assertEqual(calls[0]["params"].get("path"), "core/paths.py")
        self.assertEqual(calls[1]["tool"], "list_dir")

    def test_execute_find_symbol_tool(self):
        res = execute_admin_tool("find_symbol", {"query": "get_logger"}, workspace_root=".")
        self.assertTrue(res.get("success"))
        self.assertIn("symbols", res)


if __name__ == "__main__":
    unittest.main()
