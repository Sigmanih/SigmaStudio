"""Interoperabilita' del provider con i tool dichiarati dai client.

Un harness esterno — opencode, Cline, Continue, Aider — parla a Sigma con il
protocollo OpenAI: dichiara delle funzioni in `tools` e si aspetta di
riconoscere nella risposta quale il modello ha scelto. Prima queste due cose
non succedevano: il campo non lo leggeva nessuno e la risposta portava solo
`content`, quindi il client restava in attesa di una chiamata che non sarebbe
mai arrivata.

Questi test coprono i pezzi che stanno fra le due estremita', quelli dove le
convenzioni delle famiglie di modelli divergono e dove un errore non si vede
finche' non e' un harness a bloccarsi.
"""

import json
import unittest

from core.engine.provider_server import (
    _ToolCallAccumulator,
    _balanced_objects,
    _declared_tool_names,
    _forced_tool_grammar,
    _tool_calls_from_text,
    _tools_from_request,
)

WEATHER = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Meteo di una citta",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}
TIME = {"type": "function", "function": {"name": "get_time", "parameters": {}}}


class TestLetturaTools(unittest.TestCase):
    def test_lista_vuota_equivale_ad_assenza(self):
        """`tools: []` significa "nessuno": inoltrarlo cambierebbe il prompt per nulla."""
        self.assertEqual(_tools_from_request({"tools": []}), (None, None))
        self.assertEqual(_tools_from_request({}), (None, None))
        self.assertEqual(_tools_from_request(None), (None, None))

    def test_tool_choice_viaggia_con_i_tool(self):
        tools, choice = _tools_from_request({"tools": [WEATHER], "tool_choice": "auto"})
        self.assertEqual(len(tools), 1)
        self.assertEqual(choice, "auto")

    def test_i_nomi_si_leggono_da_entrambe_le_forme(self):
        """Alcuni client annidano sotto `function`, altri no."""
        self.assertEqual(_declared_tool_names([WEATHER]), {"get_weather"})
        self.assertEqual(_declared_tool_names([{"name": "diretto"}]), {"diretto"})
        self.assertEqual(_declared_tool_names([]), set())


class TestAccumulatore(unittest.TestCase):
    """Le chiamate arrivano spezzate: il nome in un delta, gli argomenti in venti."""

    def test_i_frammenti_si_ricompongono_per_indice(self):
        acc = _ToolCallAccumulator()
        acc.add([{"index": 0, "id": "call_1",
                  "function": {"name": "get_weather", "arguments": '{"ci'}}])
        acc.add([{"index": 0, "function": {"arguments": 'ty": "Roma"}'}}])

        calls = acc.result()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "get_weather")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"city": "Roma"})

    def test_due_chiamate_non_si_fondono(self):
        """Concatenare in ordine di arrivo produrrebbe un JSON solo e invalido."""
        acc = _ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "get_weather", "arguments": '{"a":1}'}}])
        acc.add([{"index": 1, "function": {"name": "get_time", "arguments": '{"b":2}'}}])

        calls = acc.result()
        self.assertEqual([c["function"]["name"] for c in calls], ["get_weather", "get_time"])
        for call in calls:
            json.loads(call["function"]["arguments"])

    def test_un_id_viene_generato_se_manca(self):
        """Il client correla il risultato alla chiamata per id: senza, non puo'."""
        acc = _ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "get_time", "arguments": "{}"}}])
        self.assertTrue(acc.result()[0]["id"])

    def test_un_frammento_senza_nome_non_e_una_chiamata(self):
        acc = _ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"arguments": "{}"}}])
        self.assertEqual(acc.result(), [])


class TestRecuperoDalTesto(unittest.TestCase):
    """Quando il runtime non riconosce la chiamata, si cerca nel testo.

    Il caso reale: Qwen2.5-Coder ha risposto `<tools>{...}</tools>` mentre
    llama.cpp cercava `<tool_call>`. Una parola di differenza fra due
    convenzioni, e il client riceveva prosa.
    """

    def test_le_convenzioni_note_vengono_riconosciute(self):
        for testo in (
            '<tools>{"name": "get_weather", "arguments": {"city": "Roma"}}</tools>',
            '<tool_call>{"name": "get_weather", "arguments": {"city": "Roma"}}</tool_call>',
            'Ecco:\n```json\n{"name": "get_weather", "arguments": {"city": "Roma"}}\n```',
            '{"name": "get_weather", "arguments": {"city": "Roma"}}',
        ):
            _, calls = _tool_calls_from_text(testo, [WEATHER])
            self.assertEqual(len(calls), 1, testo[:40])
            self.assertEqual(
                json.loads(calls[0]["function"]["arguments"]), {"city": "Roma"}
            )

    def test_una_chiamata_sola_non_diventa_due(self):
        """Il payload si trova sia dentro il tag sia dalla scansione bilanciata."""
        testo = '<tools>{"name": "get_weather", "arguments": {"city": "Bari"}}</tools>'
        _, calls = _tool_calls_from_text(testo, [WEATHER])
        self.assertEqual(len(calls), 1)

    def test_la_prosa_resta_prosa(self):
        """Il rischio da evitare non e' perdere una chiamata: e' inventarne una."""
        testo = "Non ho accesso ai dati meteo. Il codice usa {\"a\": 1} come esempio."
        residuo, calls = _tool_calls_from_text(testo, [WEATHER])
        self.assertEqual(calls, [])
        self.assertEqual(residuo, testo)

    def test_un_tool_non_dichiarato_viene_ignorato(self):
        testo = '<tools>{"name": "rm_rf", "arguments": {}}</tools>'
        _, calls = _tool_calls_from_text(testo, [WEATHER])
        self.assertEqual(calls, [])

    def test_senza_tool_dichiarati_non_si_tocca_nulla(self):
        testo = '{"name": "get_weather", "arguments": {}}'
        residuo, calls = _tool_calls_from_text(testo, None)
        self.assertEqual(calls, [])
        self.assertEqual(residuo, testo)

    def test_le_graffe_nelle_stringhe_non_chiudono_l_oggetto(self):
        """Gli argomenti contengono spesso codice: contarle come struttura tronca."""
        testo = '{"name": "get_weather", "arguments": {"city": "a{b}c"}}'
        _, calls = _tool_calls_from_text(testo, [WEATHER])
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"city": "a{b}c"})

    def test_la_scansione_bilanciata_trova_gli_oggetti_annidati(self):
        trovati = _balanced_objects('prima {"a": {"b": 1}} in mezzo {"c": 2} dopo')
        self.assertEqual(trovati, ['{"a": {"b": 1}}', '{"c": 2}'])


class TestGrammaticaObbligata(unittest.TestCase):
    """`required` deve essere una garanzia, non un auspicio.

    Su un modello grande la differenza fra `auto` e `required` la fa il prompt.
    Su un 7B locale `required` senza vincolo produce prosa, e l'harness aspetta.
    """

    def test_auto_lascia_libero_il_modello(self):
        """La maggior parte delle richieste con tool dichiarati non ne usa nessuno."""
        self.assertIsNone(_forced_tool_grammar([WEATHER], "auto"))
        self.assertIsNone(_forced_tool_grammar([WEATHER], None))

    def test_required_vincola_ai_nomi_dichiarati(self):
        grammatica = _forced_tool_grammar([WEATHER, TIME], "required")
        self.assertIsNotNone(grammatica)
        self.assertIn("get_weather", grammatica)
        self.assertIn("get_time", grammatica)

    def test_una_scelta_esplicita_esclude_le_altre(self):
        grammatica = _forced_tool_grammar(
            [WEATHER, TIME], {"type": "function", "function": {"name": "get_time"}}
        )
        self.assertIn("get_time", grammatica)
        self.assertNotIn("get_weather", grammatica)

    def test_una_scelta_inesistente_non_vincola_nulla(self):
        """Meglio nessun vincolo che una grammatica che non ammette nulla."""
        self.assertIsNone(
            _forced_tool_grammar(
                [WEATHER], {"type": "function", "function": {"name": "assente"}}
            )
        )

    def test_senza_tool_non_c_e_grammatica(self):
        self.assertIsNone(_forced_tool_grammar(None, "required"))
        self.assertIsNone(_forced_tool_grammar([], "required"))

    def test_la_grammatica_e_compilabile(self):
        """Una grammatica che llama.cpp rifiuta bloccherebbe ogni generazione."""
        from core.engine.grammars import compile_for_llama_cpp

        grammatica = _forced_tool_grammar([WEATHER, TIME], "required")
        self.assertIsNotNone(compile_for_llama_cpp(grammatica))


if __name__ == "__main__":
    unittest.main()
