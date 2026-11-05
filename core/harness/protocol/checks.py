"""Verifiche esterne del comportamento, indipendenti dalle stringhe nel codice."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import uuid
from typing import Callable

PROTOCOL_VERSION = "sigma.agent_tasks/2"
MAX_SOURCE_BYTES = 1024 * 1024
CHECK_TIMEOUT_SECONDS = 5


def file_invariato(root: Path, name: str, original: str) -> str:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        return f"{name}: percorso esterno al workspace"
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return f"{name}: supera il limite del verificatore"
        if path.read_text(encoding="utf-8") != original:
            return f"{name}: il test originale e' stato modificato"
    except (OSError, UnicodeError) as exc:
        return f"{name}: test originale non leggibile: {exc}"
    return ""


def python_behavior(program: str, *sources: str) -> Callable[[Path], str]:
    """Esegue casi controllati con tempo limitato e diagnostica troncata."""
    def check(root: Path) -> str:
        try:
            for name in sources:
                path = (root / name).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    return f"{name}: sorgente mancante o esterno al workspace"
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    return f"{name}: supera il limite del verificatore"
            with tempfile.TemporaryDirectory(prefix="sigma_behavior_") as temporary:
                marker = "SIGMA-VERIFIED-" + uuid.uuid4().hex
                # Una cache separata evita di verificare bytecode precedente alla correzione.
                bootstrap = (
                    "import sys\n"
                    f"sys.pycache_prefix = {str(Path(temporary) / 'bytecode')!r}\n"
                    "sys.path.insert(0, '.')\n"
                )
                with (Path(temporary) / "output").open("w+b") as output:
                    result = subprocess.run(
                        [sys.executable, "-I", "-B", "-c", bootstrap + textwrap.dedent(program)
                         + f"\nprint({marker!r})\n"],
                        cwd=root, stdout=output, stderr=subprocess.STDOUT,
                        timeout=CHECK_TIMEOUT_SECONDS, check=False,
                    )
                    if output.tell() > 65536:
                        return "Verificatore: output oltre 64 KiB"
                    output.seek(0)
                    detail = output.read(65536).decode("utf-8", errors="replace")
                    # Un exit(0) nel sorgente non deve saltare i casi di verifica.
                    if result.returncode == 0 and detail.rstrip().endswith(marker):
                        return ""
                    detail = detail[-4096:]
                    return f"Verifica del comportamento fallita ({result.returncode}): {detail}"
        except subprocess.TimeoutExpired:
            return f"Verifica del comportamento oltre {CHECK_TIMEOUT_SECONDS}s"
        except (OSError, UnicodeError) as exc:
            return f"Verifica del comportamento non eseguibile: {exc}"
    return check


discount = python_behavior("""
import math, runpy
fn = runpy.run_path('calc.py')['calcola_sconto']
for price, percentage in [(100, 20), (200, 25), (100, 0), (100, 100), (49.99, 15)]:
    assert math.isclose(fn(price, percentage), price * (1 - percentage / 100), abs_tol=1e-9)
""", "calc.py")

conversion = python_behavior("""
import math, runpy
fn = runpy.run_path('conversione.py')['celsius_a_fahrenheit']
for value in [0, 100, -40, 20, 37]:
    assert math.isclose(fn(value), value * 9 / 5 + 32, abs_tol=1e-9)
""", "conversione.py")

refactor = python_behavior("""
import contextlib, io, runpy
fn = runpy.run_path('service.py')['formatta_messaggio']
for sender, text in [('Sigma', 'Pronto'), ('A', 'B'), ('', '')]:
    assert fn(sender, text) == f'SIGMA- [{sender}]: {text}'
output = io.StringIO()
with contextlib.redirect_stdout(output):
    runpy.run_path('app.py', run_name='__main__')
assert output.getvalue().strip() == 'SIGMA- [Sigma]: Pronto'
""", "service.py", "app.py")

email_domain = python_behavior("""
import contextlib, io, runpy
fn = runpy.run_path('helpers/validazione.py')['valida_email']
for address in ['a@b.it', 'user@sub.example.org']:
    assert fn(address)
for address in ['a@localhost', 'a@dominio', 'plain']:
    assert not fn(address)
output = io.StringIO()
with contextlib.redirect_stdout(output):
    runpy.run_path('app.py', run_name='__main__')
assert output.getvalue().strip() == 'True'
""", "helpers/validazione.py", "app.py")

new_file = python_behavior("""
import json
from pathlib import Path
assert json.loads(Path('locales/it.json').read_text(encoding='utf-8')) == {'titolo': 'Ciao'}
""", "locales/it.json")

package_version = python_behavior("""
import json
from pathlib import Path
assert json.loads(Path('package.json').read_text(encoding='utf-8')) == {
    'name': 'demo-app', 'version': '1.1.0', 'private': True}
""", "package.json")

config_edit = python_behavior("""
import ast
from pathlib import Path
expected = "LINGUA = 'it'\\nDEBUG = False\\nTIMEOUT = 60\\n"
actual = Path('config.py').read_text(encoding='utf-8')
assert ast.dump(ast.parse(actual)) == ast.dump(ast.parse(expected))
""", "config.py")

database_port = python_behavior("""
from pathlib import Path
lines = Path('src/backend/settings/database.conf').read_text(encoding='utf-8').splitlines()
values = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
assert sorted(values) == sorted(['HOST=localhost', 'PORT=5433', 'NAME=sigmadb'])
""", "src/backend/settings/database.conf")

orders_csv = python_behavior("""
import contextlib, io, runpy
from decimal import Decimal
parse = runpy.run_path('orders/parser.py')['parse_orders']
total = runpy.run_path('orders/totals.py')['total_cents']
rows = parse('id,quantity,price\\n"A,1",1,0.105\\nB,2,1.20\\n')
assert rows == [{'id': 'A,1', 'quantity': 1, 'price': Decimal('0.105')},
                {'id': 'B', 'quantity': 2, 'price': Decimal('1.20')}]
assert all(isinstance(row['price'], Decimal) for row in rows)
assert total(rows) == 251
assert total(parse('id,quantity,price\\nA,1,0.005\\nB,1,0.005\\n')) == 2
assert total(parse('id,quantity,price\\nA,3,0.335\\n')) == 101
assert total(parse('id,quantity,price\\nA,1,0\\n')) == 0
assert parse('id,quantity,price\\n') == []
for text in ['id,quantity,price\\nA,0,1\\n', 'id,quantity,price\\nA,-1,1\\n',
             'id,quantity,price\\nA,1.5,1\\n', 'id,quantity,price\\nA,1,-1\\n',
             'id,quantity,price\\nA,1,NaN\\n', 'id,quantity,price\\nA,1,Infinity\\n',
             'id,quantity,price\\nA,1,nope\\n', 'id,quantity\\nA,1\\n']:
    try:
        parse(text)
    except ValueError:
        continue
    raise AssertionError('Riga non valida accettata: ' + repr(text))
output = io.StringIO()
with contextlib.redirect_stdout(output):
    runpy.run_path('app.py', run_name='__main__')
assert output.getvalue().strip() == '251'
""", "orders/parser.py", "orders/totals.py", "app.py", "fixtures/orders.csv")
