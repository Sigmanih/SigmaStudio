"""Il kernel deve avviarsi senza laboratori e senza ridefinizioni silenziose."""
import ast
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_nessuna_definizione_sovrascrive_un_altra():
    duplicates = []
    for filename in (ROOT / "core").rglob("*.py"):
        if "modules" in filename.relative_to(ROOT / "core").parts:
            continue
        tree = ast.parse(filename.read_text(encoding="utf-8-sig"))
        for parent in [tree, *(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))]:
            seen = set()
            for node in parent.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                setter = any(isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter")
                             for dec in node.decorator_list)
                if node.name in seen and not setter:
                    duplicates.append(f"{filename.relative_to(ROOT)}:{node.lineno}:{node.name}")
                seen.add(node.name)
    assert not duplicates, "\n".join(duplicates)


def test_avvio_del_kernel_con_import_dei_moduli_vietato(tmp_path):
    script = '''
import importlib.abc
import sys
class NoExtensions(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "core.modules" or fullname.startswith("core.modules."):
            raise ImportError("Il kernel ha chiesto un modulo opzionale: " + fullname)
        return None
sys.meta_path.insert(0, NoExtensions())
from core.fastapi_app import app
from core.harness import loop, protocol_bench
assert app is not None
assert protocol_bench.SCENARI
assert not any(name.startswith("core.modules.") for name in sys.modules)
'''
    environment = {**os.environ, "SIGMA_HOME": str(tmp_path), "SIGMA_NO_BROWSER": "1"}
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
