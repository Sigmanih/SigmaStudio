# ==============================================================================
# tests/test_symbol_index.py — Test per l'indicizzatore AST dei simboli
# ==============================================================================
import unittest
from pathlib import Path

from core.developer_studio.symbol_index import (
    _extract_py_symbols,
    _extract_js_symbols,
    find_symbol_definitions,
)


class TestSymbolIndex(unittest.TestCase):
    """Verifica l'estrazione e ricerca di simboli Python e JS/TS."""

    def test_extract_py_symbols(self):
        code = """
class MyService:
    def __init__(self):
        pass

    async def fetch_data(self, url):
        pass

def standalone_helper():
    pass
"""
        symbols = _extract_py_symbols(code, "services/my_service.py")
        names = [s["name"] for s in symbols]
        
        self.assertIn("MyService", names)
        self.assertIn("fetch_data", names)
        self.assertIn("standalone_helper", names)

    def test_extract_js_symbols(self):
        code = """
export const AppHeader = () => {
    return <div>Header</div>;
};

export function calculateTotal(items) {
    return items.length;
}

class SessionManager {
    constructor() {}
}
"""
        symbols = _extract_js_symbols(code, "src/AppHeader.jsx")
        names = [s["name"] for s in symbols]

        self.assertIn("AppHeader", names)
        self.assertIn("calculateTotal", names)
        self.assertIn("SessionManager", names)


if __name__ == "__main__":
    unittest.main()
