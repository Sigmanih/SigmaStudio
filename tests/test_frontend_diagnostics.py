# ==============================================================================
# tests/test_frontend_diagnostics.py — Test validatore sintassi multi-linguaggio
# ==============================================================================
"""Il controllo di sintassi del frontend, e i casi che lo avevano fatto spegnere.

Il bilanciatore a caratteri respingeva 45 file validi su 206 — l'apostrofo di
una parola italiana dentro il JSX, una regex con una graffa, `<Icon />` dopo
un'interpolazione. La risposta era stata declassare l'errore a `log.debug` per
qualunque file contenente un backtick o una regex: il 77% del frontend, cioe'
il controllo spento proprio dove serviva.

Qui il verdetto lo da' il parser vero. Questa suite lo prova da due lati, e il
secondo e' quello che mancava: **cosa NON deve essere respinto**. Senza i casi
positivi, il primo falso allarme fa spegnere di nuovo il controllo; senza i
negativi, spegnerlo non fa fallire niente.
"""
import unittest

from core.harness.diagnostics import (
    _validate_brackets_and_quotes,
    validate_code_syntax,
)


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
        invalid_jsx = "export const Button = ({ text }) => { return (<button>{text}</button>; };"

        self.assertTrue(validate_code_syntax("Button.jsx", valid_jsx)["valid"])
        self.assertFalse(validate_code_syntax("Button.jsx", invalid_jsx)["valid"])

    def test_css_brackets(self):
        valid_css = ".card { padding: 10px; margin: 0; }"
        invalid_css = ".card { padding: 10px; margin: 0;"  # unclosed '{'

        self.assertTrue(validate_code_syntax("style.css", valid_css)["valid"])
        res = validate_code_syntax("style.css", invalid_css)
        self.assertFalse(res["valid"])

    def test_rust_valid_and_invalid(self):
        valid_rs = "fn compute(x: i32) -> i32 { x * 2 }"
        invalid_rs = "fn compute(x: i32) -> i32 { x * 2"  # unclosed '{'

        self.assertTrue(validate_code_syntax("main.rs", valid_rs)["valid"])
        res = validate_code_syntax("main.rs", invalid_rs)
        self.assertFalse(res["valid"])
        self.assertEqual(res["language"], "rust")


#: I costrutti che facevano sbagliare il bilanciatore. Ognuno compare due
#: volte: una versione valida, che **non** deve essere respinta, e la stessa
#: con una graffa in meno, che deve esserlo. Se il controllo venisse spento
#: per uno di questi costrutti, la seconda meta' fallirebbe.
CASI = {
    "template literal con interpolazione": (
        "export default function X({ n }) {\n"
        "  const s = `ciao ${n}`;\n"
        "  return <div className={s}>{n}</div>;\n"
        "}\n"
    ),
    "template literal annidato": (
        "export default function X({ a, b }) {\n"
        "  const s = `fuori ${`dentro ${a} ancora`} ${b}`;\n"
        "  return <p>{s}</p>;\n"
        "}\n"
    ),
    "regex con graffe": (
        "export function pulisci(t) {\n"
        "  return t.replace(/\\{[^}]*\\}/g, '').replace(/\\s{2,}/g, ' ');\n"
        "}\n"
    ),
    "commento JSX con parentesi dentro": (
        "export default function X() {\n"
        "  return (\n"
        "    <div>\n"
        "      {/* nota: qui (una parentesi) e una } graffa */}\n"
        "      <span>ok</span>\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    ),
    "apostrofo nel testo JSX": (
        "export default function X() {\n"
        "  return (\n"
        "    <p>L'utente ha chiuso l'attivita' e l'agente l'ha registrata.</p>\n"
        "  );\n"
        "}\n"
    ),
    "tag JSX autochiuso dopo interpolazione": (
        "export default function X({ p }) {\n"
        "  return (\n"
        "    <span>\n"
        "      <FileText size={10} /> {p.split('/').pop()}\n"
        "    </span>\n"
        "  );\n"
        "}\n"
    ),
    "stringa che contiene graffe": (
        "export const modello = {\n"
        "  schema: 'prendi { questo } e { quello }',\n"
        "  chiudi: \"} non e' una graffa vera\",\n"
        "};\n"
    ),
}


def _rompi(sorgente: str) -> str:
    """Lo stesso file con l'ultima graffa di chiusura tolta."""
    taglio = sorgente.rstrip().rfind("}")
    assert taglio != -1, "il caso di prova deve contenere una graffa di chiusura"
    return sorgente[:taglio] + sorgente[taglio + 1:]


class TestCostruttiCheFacevanoSbagliare(unittest.TestCase):
    """Il parser vero: nessun falso allarme, e nessun guasto lasciato passare."""

    def test_i_costrutti_validi_non_vengono_respinti(self):
        for nome, sorgente in CASI.items():
            with self.subTest(costrutto=nome):
                esito = validate_code_syntax("Comp.jsx", sorgente)
                self.assertTrue(
                    esito["valid"],
                    f"{nome}: file valido respinto — {esito.get('error')}",
                )

    def test_lo_stesso_file_rotto_viene_respinto(self):
        """E' il test che il declassamento a `log.debug` faceva passare.

        Prima della correzione bastava un backtick o una regex perche' un file
        con una graffa in meno risultasse valido.
        """
        for nome, sorgente in CASI.items():
            with self.subTest(costrutto=nome):
                esito = validate_code_syntax("Comp.jsx", _rompi(sorgente))
                self.assertFalse(
                    esito["valid"],
                    f"{nome}: file rotto dichiarato valido",
                )

    def test_il_verdetto_dice_dove(self):
        esito = validate_code_syntax("Comp.jsx", _rompi(CASI["template literal con interpolazione"]))
        self.assertFalse(esito["valid"])
        self.assertIsNotNone(esito.get("line"), "un errore di sintassi deve dire a quale riga")


class TestRipiegoSenzaParser(unittest.TestCase):
    """Il bilanciatore a caratteri, quando node non c'e'.

    Resta un'approssimazione: su 206 file del progetto ne respinge 6 a torto,
    contro i 45 di prima. Non e' zero, ed e' per questo che non e' il giudice.
    Ma i tre costrutti che lo rompevano piu' spesso ora li regge.
    """

    def test_non_inciampa_piu_sui_costrutti_frequenti(self):
        for nome in ("apostrofo nel testo JSX", "regex con graffe",
                     "tag JSX autochiuso dopo interpolazione",
                     "template literal annidato"):
            with self.subTest(costrutto=nome):
                self.assertIsNone(
                    _validate_brackets_and_quotes(CASI[nome], "javascript"),
                    f"{nome}: il ripiego segnala un guasto che non c'e'",
                )

    def test_vede_comunque_la_graffa_mancante(self):
        rotto = _rompi(CASI["apostrofo nel testo JSX"])
        self.assertIsNotNone(_validate_brackets_and_quotes(rotto, "javascript"))

    def test_quando_ripiega_lo_dichiara(self):
        """Un controllo che non ha potuto girare non deve sembrare superato."""
        import core.harness.diagnostics as diagnostics

        precedente = diagnostics._NODE_DISPONIBILE
        diagnostics._NODE_DISPONIBILE = False
        try:
            esito = validate_code_syntax("Comp.jsx", CASI["regex con graffe"])
            self.assertEqual(esito.get("fonte"), "euristica")
        finally:
            diagnostics._NODE_DISPONIBILE = precedente


if __name__ == "__main__":
    unittest.main()
