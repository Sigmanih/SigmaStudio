"""Lo stesso file scritto in due modi e' lo stesso file.

Difetto trovato su un run vero dell'utente. L'agente ha letto
`backend/index.js` dieci volte, poi ha chiamato `edit_file` su
`./backend/index.js`, e la guardia gli ha risposto «non hai ancora letto
questo file in questa sessione» — otto volte di fila. Dal suo punto di vista
il sistema mentiva, e infatti il ledger aveva due voci distinte per lo stesso
file: indicizzava per stringa grezza, non per percorso.

Otto dei dieci fallimenti di quel run vengono da qui. E' il terzo schema di
questo progetto — il sistema che si contraddice — e il piu' costoso, perche'
l'agente non ha modo di capire cosa stia sbagliando: sta guardando il file
giusto.
"""

import pytest

from core.harness.ledger import DevSessionLedger


@pytest.fixture
def led(tmp_path):
    return DevSessionLedger(goal="x", workspace_root=str(tmp_path).replace("\\", "/"))


class TestLaStessaChiavePerLoStessoFile:
    @pytest.mark.parametrize("a,b", [
        ("backend/index.js", "./backend/index.js"),
        ("backend/index.js", "backend\index.js"),
        ("src/app.py", "src/../src/app.py"),
        ("a/b.py", "a//b.py"),
        ("./x.py", "x.py"),
    ])
    def test_forme_diverse_stesso_file(self, led, a, b):
        assert led._rel(a) == led._rel(b), f"'{a}' e '{b}' finiscono in voci diverse"

    def test_il_percorso_assoluto_coincide_con_quello_relativo(self, led, tmp_path):
        radice = str(tmp_path).replace("\\", "/")
        assert led._rel(f"{radice}/backend/index.js") == led._rel("./backend/index.js")

    def test_file_diversi_restano_diversi(self, led):
        """La normalizzazione non deve far collassare file distinti."""
        assert led._rel("a/b.py") != led._rel("a/c.py")
        assert led._rel("uno/x.py") != led._rel("due/x.py")

    def test_un_percorso_fuori_dal_workspace_resta_riconoscibile(self, led):
        assert led._rel("D:/altrove/x.py") == "D:/altrove/x.py"


class TestLaGuardiaSullaLettura:
    """Il caso vero, riprodotto end to end."""

    def test_leggere_in_un_modo_e_modificare_nell_altro(self, led, tmp_path):
        f = tmp_path / "backend" / "index.js"
        f.parent.mkdir(parents=True)
        f.write_text("const express = require('express');\n", encoding="utf-8")

        led.record_tool("read_file", {"path": "backend/index.js"},
                        {"success": True, "path": str(f), "content": "x",
                         "total_lines": 1})

        assert led.was_read_before_change("./backend/index.js") is True, (
            "l'agente aveva letto il file: la guardia non deve rifiutarlo"
        )

    def test_un_file_mai_letto_resta_rifiutato(self, led):
        """La guardia serve e deve restare: senza aver letto un file non si
        conosce il testo esatto da sostituire, e l'ancora viene inventata."""
        assert led.was_read_before_change("./mai/visto.js") is False

    def test_leggere_col_percorso_assoluto_vale_per_quello_relativo(self, led, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("X = 1\n", encoding="utf-8")
        led.record_tool("read_file", {"path": str(f)},
                        {"success": True, "path": str(f), "content": "X = 1",
                         "total_lines": 1})
        assert led.was_read_before_change("app.py") is True


class TestUnSoloRecordPerFile:
    def test_scritture_e_letture_finiscono_sulla_stessa_voce(self, led, tmp_path):
        f = tmp_path / "backend" / "index.js"
        f.parent.mkdir(parents=True)
        f.write_text("x\n", encoding="utf-8")

        led.record_tool("write_file", {"path": "backend/index.js"},
                        {"success": True, "path": str(f)})
        led.record_tool("read_file", {"path": "./backend/index.js"},
                        {"success": True, "path": str(f), "content": "x",
                         "total_lines": 1})

        voci = [v for v in led.snapshot()["files"] if "index.js" in v["path"]]
        assert len(voci) == 1, f"lo stesso file compare in {len(voci)} voci"
        assert voci[0]["reads"] >= 1 and voci[0]["writes"] >= 1
