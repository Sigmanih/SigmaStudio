# ==============================================================================
# tests/test_frontend_diagnostics.py — Test validatore sintassi multi-linguaggio
# ==============================================================================
import unittest

from core.developer_studio.diagnostics import validate_code_syntax


class TestFrontendDiagnostics(unittest.TestCase):
    """Verifica il validatore di sintassi per Python, JSON, JS, JSX, TS e CSS."""

    def test_python_valid_and_invalid(self):
        valid_py = "def hello():\n    return 'world'\n"
        invalid_py = "def hello(\n    return 'world'"
        
        self.assertTrue(validate_code_syntax("test.py", valid_py)["valid"])
        res = validate_code_syntax("test.py", invalid_py)
        self.assertFalse(res["valid"])
        self.assertIn("Python", res["error"])

    def test_json_valid_and_invalid(self):
        valid_json = '{"key": "value", "items": [1, 2, 3]}'
        invalid_json = '{"key": "value", "items": [1, 2, 3,]}'  # trailing comma
        
        self.assertTrue(validate_code_syntax("data.json", valid_json)["valid"])
        res = validate_code_syntax("data.json", invalid_json)
        self.assertFalse(res["valid"])
        self.assertIn("JSON", res["error"])

    def test_javascript_and_jsx_brackets(self):
        valid_jsx = "export const Button = ({ text }) => { return (<button>{text}</button>); };"
        invalid_jsx = "export const Button = ({ text }) => { return (<button>{text}</button>; };"  # missing ')'
        
        self.assertTrue(validate_code_syntax("Button.jsx", valid_jsx)["valid"])
        res = validate_code_syntax("Button.jsx", invalid_jsx)
        self.assertFalse(res["valid"])
        self.assertIn("Parentesi", res["error"])

    def test_css_brackets(self):
        valid_css = ".card { padding: 10px; margin: 0; }"
        invalid_css = ".card { padding: 10px; margin: 0;"  # unclosed '{'
        
        self.assertTrue(validate_code_syntax("style.css", valid_css)["valid"])
        res = validate_code_syntax("style.css", invalid_css)
        self.assertFalse(res["valid"])
        self.assertIn("non chiusa", res["error"])


if __name__ == "__main__":
    unittest.main()
