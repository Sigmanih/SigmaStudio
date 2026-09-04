"""Due strade per ottenere una chiamata, una sola forma per eseguirla.

Con un modello locale l'harness usa un blocco recintato piu' una grammatica
GBNF: e' l'unico modo di ottenere una chiamata ben formata da un 8B. Con un
provider che il tool-calling ce l'ha nativo quella scelta diventa la peggiore —
si costringe il modello a imitare un formato testuale e si fa passare la sua
risposta per le euristiche di riparazione scritte per chi quel supporto non ce
l'ha.

Il vincolo che tiene insieme le due strade e' che producano la stessa forma
interna. Se divergesse, il tool-calling nativo diventerebbe un secondo agente
con permessi, ledger e cancello di completamento propri — cioe' senza.
"""

import json

import pytest

from core.harness.tool_schema import (
    NATIVE_TOOL_PROVIDERS,
    TOOL_SCHEMAS,
    schemas_for,
    supports_native_tools,
    tool_calls_to_invocations,
)


class TestRilevamentoProvider:
    def test_il_motore_locale_usa_il_percorso_recintato(self):
        for nome in ("sigma_engine", "sigma", "sigmaengine", "local", "native", "ollama"):
            assert supports_native_tools(nome) is False, nome

    def test_i_provider_cloud_usano_quello_nativo(self):
        for nome in ("openai", "deepseek", "anthropic", "groq"):
            assert supports_native_tools(nome) is True, nome

    def test_un_provider_sconosciuto_non_riceve_i_tool(self):
        """Un 400 a meta' del run costa piu' che tenere una lista esplicita."""
        assert supports_native_tools("provider_mai_visto") is False
        assert supports_native_tools("") is False
        assert supports_native_tools(None) is False

    def test_il_nome_e_normalizzato(self):
        assert supports_native_tools("  OpenAI ") is True


class TestCatalogo:
    def test_ogni_schema_e_ben_formato(self):
        for schema in TOOL_SCHEMAS:
            assert schema["type"] == "function"
            fn = schema["function"]
            assert fn["name"] and fn["description"]
            assert fn["parameters"]["type"] == "object"
            for richiesto in fn["parameters"]["required"]:
                assert richiesto in fn["parameters"]["properties"], fn["name"]

    def test_i_nomi_sono_quelli_canonici(self):
        """Una chiamata nativa e una recintata devono finire nello stesso ramo."""
        from core.harness.policy import canonical
        for schema in TOOL_SCHEMAS:
            nome = schema["function"]["name"]
            assert canonical(nome) == nome, nome

    def test_i_tool_essenziali_ci_sono_tutti(self):
        nomi = {s["function"]["name"] for s in TOOL_SCHEMAS}
        assert {"read_file", "edit_file", "write_file", "terminal",
                "spec", "complete_goal"} <= nomi

    def test_il_catalogo_si_restringe_ai_tool_permessi(self):
        """Offrire un tool che verrebbe rifiutato costa un turno per nulla."""
        ristretto = schemas_for(["read_file", "search_code"])
        assert {s["function"]["name"] for s in ristretto} == {"read_file", "search_code"}

    def test_senza_restrizioni_si_offre_tutto(self):
        assert len(schemas_for(None)) == len(TOOL_SCHEMAS)
        assert len(schemas_for([])) == len(TOOL_SCHEMAS)

    def test_lo_schema_e_serializzabile(self):
        """Finisce dentro una richiesta HTTP: se non e' JSON, non parte."""
        assert json.loads(json.dumps(TOOL_SCHEMAS)) == TOOL_SCHEMAS


class TestTraduzione:
    def test_una_chiamata_nativa_diventa_la_forma_interna(self):
        invocazioni = tool_calls_to_invocations([{
            "id": "call_1",
            "function": {"name": "read_file",
                         "arguments": '{"path": "core/paths.py", "offset": 10}'},
        }])
        assert invocazioni == [{
            "tool": "read_file",
            "params": {"path": "core/paths.py", "offset": 10},
            "id": "call_1",
            "native": True,
        }]

    def test_gli_argomenti_gia_decodificati_passano(self):
        """Alcuni provider consegnano un oggetto invece di una stringa."""
        inv = tool_calls_to_invocations([
            {"function": {"name": "terminal", "arguments": {"command": "pytest"}}}
        ])
        assert inv[0]["params"] == {"command": "pytest"}

    def test_argomenti_troncati_diventano_una_chiamata_malformata(self):
        """Anche un provider nativo tronca: scartarla in silenzio sarebbe peggio."""
        inv = tool_calls_to_invocations([
            {"function": {"name": "write_file", "arguments": '{"path": "x.py", "cont'}}
        ])
        assert inv[0]["params"]["__malformed__"] is True
        assert inv[0]["tool"] == "write_file"

    def test_argomenti_che_non_sono_un_oggetto_sono_malformati(self):
        inv = tool_calls_to_invocations([
            {"function": {"name": "read_file", "arguments": '["core/paths.py"]'}}
        ])
        assert inv[0]["params"]["__malformed__"] is True

    def test_una_chiamata_senza_nome_viene_scartata(self):
        assert tool_calls_to_invocations([{"function": {"arguments": "{}"}}]) == []

    def test_argomenti_assenti_danno_parametri_vuoti(self):
        inv = tool_calls_to_invocations([{"function": {"name": "git_status"}}])
        assert inv[0]["params"] == {}

    def test_voci_non_valide_non_fanno_saltare_le_altre(self):
        inv = tool_calls_to_invocations([
            "non un dizionario",
            {"function": {"name": "read_file", "arguments": '{"path": "a.py"}'}},
        ])
        assert len(inv) == 1

    def test_un_elenco_vuoto_non_produce_nulla(self):
        assert tool_calls_to_invocations([]) == []
        assert tool_calls_to_invocations(None) == []


class TestFormaCondivisa:
    """Il vincolo che impedisce al percorso nativo di diventare un altro agente."""

    def test_le_due_strade_producono_le_stesse_chiavi(self):
        from core.harness.loop import extract_tool_invocations

        testuale = extract_tool_invocations(
            '```tool:read_file\n{"path": "core/paths.py"}\n```'
        )
        nativa = tool_calls_to_invocations([
            {"function": {"name": "read_file", "arguments": '{"path": "core/paths.py"}'}}
        ])
        assert testuale[0]["tool"] == nativa[0]["tool"]
        assert testuale[0]["params"] == nativa[0]["params"]

    def test_la_policy_giudica_allo_stesso_modo_le_due_forme(self):
        from core.harness.policy import ToolPolicy
        policy = ToolPolicy.of(("read_file",))
        nativa = tool_calls_to_invocations([
            {"function": {"name": "terminal", "arguments": '{"command": "rm -rf /"}'}}
        ])
        assert not policy.permits(nativa[0]["tool"])


class TestRicomposizioneDeiDelta:
    """I frammenti in streaming, che nessuno garantisce contigui."""

    def test_nome_e_argomenti_spezzati_si_ricompongono(self):
        from core.engine.tool_calls import ToolCallAccumulator
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "read_file", "arguments": '{"pa'}}])
        acc.add([{"index": 0, "function": {"arguments": 'th": "x.py"}'}}])
        inv = tool_calls_to_invocations(acc.result())
        assert inv[0]["params"] == {"path": "x.py"}

    def test_due_chiamate_non_si_fondono(self):
        """Concatenare in ordine di arrivo ne farebbe una sola, illeggibile."""
        from core.engine.tool_calls import ToolCallAccumulator
        acc = ToolCallAccumulator()
        acc.add([{"index": 0, "function": {"name": "read_file", "arguments": '{"path":"a.py"}'}},
                 {"index": 1, "function": {"name": "read_file", "arguments": '{"path":"b.py"}'}}])
        inv = tool_calls_to_invocations(acc.result())
        assert [i["params"]["path"] for i in inv] == ["a.py", "b.py"]
