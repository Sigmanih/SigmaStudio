"""Il corpo di una chiamata si ripara quando la rottura e' meccanica.

Contato sui fallimenti veri (260 in 187 sessioni, al 24 settembre 2026): 46
corpi di `write_file` e 15 di `edit_file` sono rifiutati perche' non sono JSON
valido, e ogni rifiuto costa un turno di ritentativo. Le cause sono due, e sono
entrambe meccaniche: una virgoletta doppia dentro il testo non protetta, e un a
capo vero dentro una stringa. Qui si verifica che si riparano, che il contenuto
arriva intero — virgolette comprese — e che cio' che non e' riparabile resta
malformato invece di diventare un'altra cosa.
"""

from core.harness.loop import normalize_tool_params
from core.harness.tool_schema import ripara_corpo_json, tool_calls_to_invocations

#: Il caso piu' frequente: virgolette dentro il codice scritto.
CORPO_CON_VIRGOLETTE = (
    '{"path": "core/esempio.py", "content": "def ciao():\n'
    '    print("ciao")\n'
    '    return True\n"}'
)

#: Lo stesso, ma con gli a capo VERI invece della sequenza di escape.
CORPO_CON_A_CAPO_VERI = (
    '{"path": "core/esempio.py", "content": "def ciao():\n'
    '    print(\'ciao\')\n'          # <- a capo vero dentro la stringa
    '    return True"}'
)

#: Troncato a meta': nessuna graffa di chiusura, nessuna virgoletta finale.
CORPO_TRONCATO = '{"path": "core/esempio.py", "content": "x = 1\nprint(x)'


class TestLaRiparazione:
    def test_virgolette_non_protette_si_proteggono(self):
        corpo = '{"path": "a.py", "content": "print("ciao")"}'
        riparato = ripara_corpo_json(corpo)
        params = normalize_tool_params(corpo, "write_file")
        assert "__malformed__" not in params, params
        assert params["content"] == 'print("ciao")', params

    def test_i_capo_veri_diventano_sequenze(self):
        riparato = ripara_corpo_json(CORPO_CON_A_CAPO_VERI)
        assert riparato is not None
        params = normalize_tool_params(CORPO_CON_A_CAPO_VERI, "write_file")
        assert "__malformed__" not in params, params
        assert params["path"] == "core/esempio.py"
        assert "\n    print('ciao')\n" in params["content"]
        assert params["content"].count("\n") == 2

    def test_un_corpo_troncato_si_chiude(self):
        params = normalize_tool_params(CORPO_TRONCATO, "write_file")
        assert "__malformed__" not in params, params
        assert params["content"].startswith("x = 1")

    def test_le_virgole_ttrailing_non_rompono(self):
        corpo = '{"path": "a.py", "content": "x = 1", }'
        params = normalize_tool_params(corpo, "write_file")
        assert params["content"] == "x = 1", params

    def test_un_corpo_gia_valido_non_si_tocca(self):
        assert ripara_corpo_json('{"path": "core/x.py", "content": "1"}') is None
        params = normalize_tool_params('{"path": "core/x.py", "content": "1"}',
                                       "write_file")
        assert params == {"path": "core/x.py", "content": "1"}

    def test_la_prosa_non_diventa_una_scrittura(self):
        """Non si inventa un campo: cio' che non e' JSON non diventa un write."""
        assert ripara_corpo_json("scrivi un file con dentro ciao") is None
        params = normalize_tool_params("scrivi un file con dentro ciao", "write_file")
        assert "content" not in params
        assert "path" not in params


class TestLaRiparazioneNeiDuePercorsi:
    """Il testo e le tool-call native passano dalla stessa riparazione."""

    def test_percorso_testuale(self):
        params = normalize_tool_params(CORPO_CON_VIRGOLETTE, "write_file")
        assert params["path"] == "core/esempio.py"
        assert 'print("ciao")' in params["content"]

    def test_percorso_nativo(self):
        chiamate = [{
            "id": "call_1",
            "function": {
                "name": "write_file",
                "arguments": '{"path": "a.py", "content": "print("ciao")"}',
            },
        }]
        invocazioni = tool_calls_to_invocations(chiamate)
        assert len(invocazioni) == 1
        params = invocazioni[0]["params"]
        assert "__malformed__" not in params, params
        assert params["content"] == 'print("ciao")'

    def test_percorso_nativo_illeggibile_resta_malformato(self):
        chiamate = [{
            "id": "call_2",
            "function": {"name": "write_file", "arguments": "non e json"},
        }]
        invocazioni = tool_calls_to_invocations(chiamate)
        assert "__malformed__" in invocazioni[0]["params"]
