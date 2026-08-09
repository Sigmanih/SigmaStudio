# ==============================================================================
# tests/test_mcp_governance.py — Policy gate, tool calling and integrations
# ==============================================================================
"""Le regole che contano quando un agente può accendere le luci di casa.

I test scrivono su una config.json temporanea: la politica vive su disco, e
verificarla sulla copia dell'utente vorrebbe dire spegnergli gli strumenti.
"""

import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

from core import mcp_handler
from core.mcp import governance, mcp_hub
from core.mcp.agent_loop import (build_tools_prompt, execute_calls,
                                 extract_tool_calls, format_results_for_model,
                                 strip_tool_blocks)


class FakeHandler:
    """Il minimo che gli handler HTTP si aspettano: un corpo e una risposta."""

    def __init__(self, payload=None):
        self._payload = payload or {}
        self.status = 200
        self.body = None

    def read_json_body(self):
        return self._payload

    def send_json_response(self, data, status=200):
        self.status = status
        self.body = data


class GovernanceTestCase(unittest.TestCase):
    """Base che isola ogni test su un file di configurazione usa e getta."""

    def setUp(self):
        handle, self.config_path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        self._patch = mock.patch.object(governance, "CONFIG_PATH", self.config_path)
        self._patch.start()
        governance.reset_pending()

    def tearDown(self):
        self._patch.stop()
        governance.reset_pending()
        try:
            os.unlink(self.config_path)
        except OSError:
            pass


class TestToolSwitches(GovernanceTestCase):
    def test_disabled_tool_is_refused_at_execution(self):
        """Lo spegnimento è un cancello, non un suggerimento nel prompt."""
        self.assertEqual(mcp_hub.execute_tool("get_hardware_status")["status"], "ok")

        governance.set_tool_enabled("get_hardware_status", False)
        outcome = mcp_hub.execute_tool("get_hardware_status")

        self.assertEqual(outcome["status"], "error")
        self.assertIn("disattivat", outcome["error"].lower())

    def test_disabling_a_server_disables_its_tools(self):
        governance.set_server_enabled("Hardware MCP", False)
        outcome = mcp_hub.execute_tool("get_hardware_status")
        self.assertEqual(outcome["status"], "error")

    def test_unknown_tool_is_named_not_swallowed(self):
        outcome = mcp_hub.execute_tool("strumento_inventato")
        self.assertEqual(outcome["status"], "error")
        self.assertIn("strumento_inventato", outcome["error"])

    def test_agent_catalogue_hides_disabled_tools(self):
        before = {t["name"] for t in mcp_hub.get_agent_tools()}
        self.assertIn("search_web", before)

        governance.set_tool_enabled("search_web", False)
        after = {t["name"] for t in mcp_hub.get_agent_tools()}

        self.assertNotIn("search_web", after)
        self.assertNotIn("search_web", build_tools_prompt(mcp_hub.get_agent_tools()))


class TestApprovalGate(GovernanceTestCase):
    def test_sensitive_tool_waits_for_a_human(self):
        outcome = mcp_hub.execute_tool("clear_vram_cache", {})
        self.assertEqual(outcome["status"], "confirmation_required")
        self.assertEqual(outcome["approval"]["tool"], "clear_vram_cache")
        self.assertTrue(outcome["approval"]["request_id"])

    def test_safe_tool_runs_unattended(self):
        self.assertEqual(mcp_hub.execute_tool("get_hardware_status")["status"], "ok")

    def test_auto_approve_lets_sensitive_tools_through(self):
        governance.set_auto_approve(True)
        self.assertEqual(mcp_hub.execute_tool("clear_vram_cache", {})["status"], "ok")

    def test_approval_cannot_be_replayed(self):
        """Un assenso vale per una chiamata sola, altrimenti è un lasciapassare."""
        approval = mcp_hub.execute_tool("clear_vram_cache", {})["approval"]
        first = mcp_hub.execute_tool("", {}, approval_id=approval["request_id"])
        second = mcp_hub.execute_tool("", {}, approval_id=approval["request_id"])

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "error")
        self.assertIn("scadut", second["error"].lower())

    def test_approval_runs_the_arguments_it_showed(self):
        """Gli argomenti eseguiti sono quelli mostrati, non quelli reinviati."""
        governance.set_integration_config(
            "home_assistant", {"base_url": "http://ha.invalid:8123", "token": "t"})
        approval = mcp_hub.execute_tool("ha_light_set", {"entity_id": "light.studio", "state": "off"})

        self.assertEqual(approval["status"], "confirmation_required")
        parked = governance.take_approval(approval["approval"]["request_id"])
        self.assertEqual(parked["arguments"], {"entity_id": "light.studio", "state": "off"})

    def test_unconfigured_integration_fails_before_asking(self):
        """Non si chiede di approvare una chiamata che non può comunque partire."""
        outcome = mcp_hub.execute_tool("ha_light_set", {"entity_id": "light.x", "state": "on"})
        self.assertEqual(outcome["status"], "error")
        self.assertIn("configurat", outcome["error"].lower())

    def test_rpc_endpoint_honours_the_gate(self):
        """La via JSON-RPC è raggiungibile dal browser: non deve aggirare le regole."""
        response = mcp_hub.dispatch_rpc({
            "jsonrpc": "2.0", "id": "r1",
            "method": "tools/call",
            "params": {"name": "clear_vram_cache", "arguments": {}},
        })
        self.assertTrue(response["result"].get("confirmationRequired"))

        governance.set_tool_enabled("get_hardware_status", False)
        refused = mcp_hub.dispatch_rpc({
            "jsonrpc": "2.0", "id": "r2",
            "method": "tools/call",
            "params": {"name": "get_hardware_status", "arguments": {}},
        })
        self.assertIn("error", refused)


class TestToolCallParsing(unittest.TestCase):
    def test_extracts_a_call_from_prose(self):
        calls = extract_tool_calls(
            'Controllo la casa.\n'
            '```sigma-tool\n'
            '{"tool": "ha_list_entities", "arguments": {"domain": "light"}}\n'
            '```\n'
            'Ecco fatto.'
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "ha_list_entities")
        self.assertEqual(calls[0]["arguments"], {"domain": "light"})

    def test_tolerates_the_name_and_parameters_spelling(self):
        """I modelli locali sbagliano il nome del campo, non l'intenzione."""
        calls = extract_tool_calls('```sigma-tool\n{"name": "search_web", "parameters": {"query": "x"}}\n```')
        self.assertEqual(calls[0]["tool"], "search_web")
        self.assertEqual(calls[0]["arguments"], {"query": "x"})

    def test_malformed_block_reports_instead_of_vanishing(self):
        calls = extract_tool_calls('```sigma-tool\n{non sono json}\n```')
        self.assertEqual(len(calls), 1)
        self.assertIn("JSON non valido", calls[0]["parse_error"])

    def test_plain_json_block_is_not_a_call(self):
        """Un esempio di JSON mostrato all'utente non deve eseguire niente."""
        self.assertEqual(extract_tool_calls('```json\n{"tool": "clear_vram_cache"}\n```'), [])

    def test_blocks_are_removed_from_the_visible_answer(self):
        visible = strip_tool_blocks(
            'Accendo la luce.\n```sigma-tool\n{"tool": "ha_light_set"}\n```\nFatto.')
        self.assertNotIn("sigma-tool", visible)
        self.assertIn("Accendo la luce.", visible)
        self.assertIn("Fatto.", visible)

    def test_round_is_capped(self):
        block = '```sigma-tool\n{"tool": "search_web", "arguments": {}}\n```\n'
        self.assertLessEqual(len(extract_tool_calls(block * 12)), 4)


class TestAgentLoop(GovernanceTestCase):
    def test_safe_calls_run_and_report(self):
        outcomes, approvals = execute_calls([{"tool": "get_hardware_status", "arguments": {}}])
        self.assertEqual(approvals, [])
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0]["ok"])
        self.assertIn("get_hardware_status", format_results_for_model(outcomes))

    def test_nothing_after_a_pending_call_is_silently_dropped(self):
        """La lettura che segue una chiamata in attesa si rimanda, non svanisce.

        Prima il ciclo si fermava alla prima approvazione e buttava via il resto:
        l'agente chiedeva tre cose, l'operatore ne vedeva una.
        """
        outcomes, approvals = execute_calls([
            {"tool": "get_hardware_status", "arguments": {}},
            {"tool": "clear_vram_cache", "arguments": {}},
            {"tool": "search_web", "arguments": {"query": "dopo"}},
        ])
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["tool"], "clear_vram_cache")

        by_tool = {o["tool"]: o for o in outcomes}
        self.assertTrue(by_tool["get_hardware_status"]["ok"], "la lettura prima parte")
        self.assertTrue(by_tool["search_web"]["deferred"], "quella dopo è dichiarata rimandata")

    def test_several_sensitive_calls_are_all_parked(self):
        outcomes, approvals = execute_calls([
            {"tool": "clear_vram_cache", "arguments": {}},
            {"tool": "benchmark_gpu", "arguments": {}},
        ])
        self.assertEqual([a["tool"] for a in approvals], ["clear_vram_cache", "benchmark_gpu"])
        self.assertEqual(outcomes, [])

    def test_failure_is_handed_back_to_the_model(self):
        outcomes, _ = execute_calls([{"tool": "non_esiste", "arguments": {}}])
        self.assertFalse(outcomes[0]["ok"])
        self.assertIn("non_esiste", outcomes[0]["output"])


class TestCredentialPersistence(GovernanceTestCase):
    """Le credenziali si scrivono una volta e restano.

    Il guasto che ha motivato questa classe: bastava sfiorare il campo password
    e premere Salva perché il token sparisse, e ce ne si accorgeva solo alla
    chiamata successiva.
    """

    def setUp(self):
        super().setUp()
        governance.set_integration_config(
            "home_assistant", {"base_url": "http://ha.local:8123", "token": "TOKEN-VERO"})

    def test_credentials_survive_a_restart(self):
        """Un processo nuovo rilegge da disco, senza stato in memoria."""
        importlib.reload(governance)
        governance.CONFIG_PATH = self.config_path
        self.assertEqual(governance.get_integration_config("home_assistant")["token"], "TOKEN-VERO")

    def test_an_untouched_secret_field_does_not_erase_it(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "home_assistant",
                         "values": {"base_url": "http://ha.local:8123", "token": ""}}))
        self.assertEqual(governance.get_integration_config("home_assistant")["token"], "TOKEN-VERO")

    def test_the_masked_placeholder_does_not_erase_it(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "home_assistant",
                         "values": {"token": mcp_handler.SECRET_MARKER}}))
        self.assertEqual(governance.get_integration_config("home_assistant")["token"], "TOKEN-VERO")

    def test_a_real_new_secret_replaces_the_old_one(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "home_assistant", "values": {"token": "TOKEN-NUOVO"}}))
        self.assertEqual(governance.get_integration_config("home_assistant")["token"], "TOKEN-NUOVO")

    def test_a_non_secret_field_can_still_be_cleared(self):
        """Solo i segreti sono protetti: un URL si deve poter svuotare."""
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "home_assistant", "values": {"base_url": ""}}))
        self.assertEqual(governance.get_integration_config("home_assistant")["base_url"], "")

    def test_the_config_path_does_not_follow_the_working_directory(self):
        """Avviare il server da un'altra cartella non deve spostare le credenziali."""
        default = governance.DEFAULT_CONFIG_PATH
        self.assertTrue(os.path.isabs(default), "un percorso relativo segue la cartella di lavoro")
        self.assertEqual(os.path.basename(default), "config.json")
        # Il file sta accanto al server, cioè nella radice del progetto.
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(default), "sigma_server.py")))

    def test_secrets_never_travel_back_to_the_browser(self):
        handler = FakeHandler()
        mcp_handler.handle_mcp_servers(handler)
        ha = next(s for s in handler.body["servers"] if s.get("integration_key") == "home_assistant")
        self.assertEqual(ha["config"]["token"], mcp_handler.SECRET_MARKER)
        self.assertEqual(ha["config"]["base_url"], "http://ha.local:8123")

    def test_the_config_file_is_never_left_half_written(self):
        governance.set_integration_config("home_assistant", {"token": "X"})
        self.assertFalse(os.path.exists(self.config_path + ".tmp"))
        with open(self.config_path, "r", encoding="utf-8") as fh:
            json.load(fh)          # deve restare JSON valido


class TestIntegrations(GovernanceTestCase):
    def test_unconfigured_integration_explains_itself(self):
        """L'agente deve leggere cosa manca, non uno stack trace."""
        outcome = mcp_hub.execute_tool("ha_list_entities", {})
        self.assertEqual(outcome["status"], "error")
        self.assertIn("configurat", outcome["error"].lower())

    def test_integration_settings_survive_a_round_trip(self):
        governance.set_integration_config(
            "home_assistant", {"base_url": "http://ha.local:8123", "token": "segreto"})
        server = mcp_hub.get_server("HomeAssistant MCP")
        self.assertTrue(server.is_configured())
        self.assertEqual(governance.get_integration_config("home_assistant")["base_url"],
                         "http://ha.local:8123")

    def test_saving_policy_does_not_erase_the_rest_of_config(self):
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump({"ai": {"active_model": "qualcosa"}}, fh)

        governance.set_tool_enabled("search_web", False)

        with open(self.config_path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["ai"]["active_model"], "qualcosa")
        self.assertIn("search_web", saved["mcp"]["disabled_tools"])

    def test_every_outward_tool_is_marked_sensitive(self):
        """Se un tool tocca il mondo reale e nasce 'safe', il cancello non scatta."""
        outward = {
            "ha_light_set", "ha_switch_set", "ha_climate_set", "ha_call_service",
            "send_email", "telegram_send_message", "slack_post_message",
            "calendar_create_event",
        }
        by_name = {t["name"]: t for t in mcp_hub.get_aggregated_tools()}
        for name in outward:
            self.assertIn(name, by_name, f"strumento '{name}' assente dall'hub")
            self.assertEqual(by_name[name]["safety"], governance.SENSITIVE,
                             f"'{name}' agisce all'esterno ma non richiede conferma")

    def test_read_only_tools_stay_safe(self):
        by_name = {t["name"]: t for t in mcp_hub.get_aggregated_tools()}
        for name in ("ha_list_entities", "read_inbox", "calendar_list_events", "search_web"):
            self.assertEqual(by_name[name]["safety"], governance.SAFE)


if __name__ == "__main__":
    unittest.main()
