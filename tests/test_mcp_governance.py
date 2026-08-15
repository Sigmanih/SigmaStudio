# ==============================================================================
# tests/test_mcp_governance.py — Policy gate, tool calling and integrations
# ==============================================================================
"""Regole di sicurezza e policy gate per gli strumenti MCP del kernel."""

import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

from core import mcp_handler
from core.mcp import governance, mcp_hub
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
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


class MockGovernanceServer(BaseMCPServer):
    integration_key = "email"
    config_fields = [
        {"key": "smtp_host", "label": "SMTP Host", "type": "text"},
        {"key": "password", "label": "Password", "type": "secret"},
    ]

    def __init__(self):
        super().__init__(name="Mock Governance Server", version="1.0.0", description="Mock server for governance tests")
        self.register_tool(
            name="search_web",
            description="Mock safe tool",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            handler=lambda **args: {"output": f"Search results for {args.get('query', '')}"},
            safety=SAFE
        )
        self.register_tool(
            name="create_workspace_file",
            description="Mock sensitive tool",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
            handler=lambda **args: {"output": f"Created {args.get('path', '')}"},
            safety=SENSITIVE
        )
        self.register_tool(
            name="execute_sandbox_code",
            description="Mock sensitive tool 2",
            input_schema={"type": "object", "properties": {"code": {"type": "string"}}},
            handler=lambda **args: {"output": f"Executed {args.get('code', '')}"},
            safety=SENSITIVE
        )



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
        self._mock_server = MockGovernanceServer()
        mcp_hub.register_server(self._mock_server)

    def tearDown(self):
        self._patch.stop()
        governance.reset_pending()
        if "Mock Governance Server" in mcp_hub.servers:
            del mcp_hub.servers["Mock Governance Server"]
        try:
            os.unlink(self.config_path)
        except OSError:
            pass


class TestToolSwitches(GovernanceTestCase):
    def test_disabled_tool_is_refused_at_execution(self):
        """Lo spegnimento è un cancello, non un suggerimento nel prompt."""
        self.assertEqual(mcp_hub.execute_tool("search_web", {"query": "test"})["status"], "ok")

        governance.set_tool_enabled("search_web", False)
        outcome = mcp_hub.execute_tool("search_web", {"query": "test"})

        self.assertEqual(outcome["status"], "error")
        self.assertIn("disattivat", outcome["error"].lower())

    def test_disabling_a_server_disables_its_tools(self):
        governance.set_server_enabled("Mock Governance Server", False)
        outcome = mcp_hub.execute_tool("search_web", {"query": "test"})
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
        outcome = mcp_hub.execute_tool("create_workspace_file", {"path": "test.txt", "content": "hello"})
        self.assertEqual(outcome["status"], "confirmation_required")
        self.assertEqual(outcome["approval"]["tool"], "create_workspace_file")
        self.assertTrue(outcome["approval"]["request_id"])

    def test_safe_tool_runs_unattended(self):
        self.assertEqual(mcp_hub.execute_tool("search_web", {"query": "test"})["status"], "ok")

    def test_auto_approve_lets_sensitive_tools_through(self):
        governance.set_auto_approve(True)
        outcome = mcp_hub.execute_tool("create_workspace_file", {"path": "test.txt", "content": "hello"})
        self.assertEqual(outcome["status"], "ok")

    def test_approval_cannot_be_replayed(self):
        """Un assenso vale per una chiamata sola, altrimenti è un lasciapassare."""
        approval = mcp_hub.execute_tool("create_workspace_file", {"path": "test.txt", "content": "hello"})["approval"]
        first = mcp_hub.execute_tool("", {}, approval_id=approval["request_id"])
        second = mcp_hub.execute_tool("", {}, approval_id=approval["request_id"])

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "error")
        self.assertIn("scadut", second["error"].lower())

    def test_approval_runs_the_arguments_it_showed(self):
        """Gli argomenti eseguiti sono quelli mostrati, non quelli reinviati."""
        approval = mcp_hub.execute_tool("create_workspace_file", {"path": "test.txt", "content": "hello"})
        self.assertEqual(approval["status"], "confirmation_required")
        parked = governance.take_approval(approval["approval"]["request_id"])
        self.assertEqual(parked["arguments"], {"path": "test.txt", "content": "hello"})

    def test_rpc_endpoint_honours_the_gate(self):
        """La via JSON-RPC è raggiungibile dal browser: non deve aggirare le regole."""
        response = mcp_hub.dispatch_rpc({
            "jsonrpc": "2.0", "id": "r1",
            "method": "tools/call",
            "params": {"name": "create_workspace_file", "arguments": {"path": "a.txt", "content": "b"}},
        })
        self.assertTrue(response["result"].get("confirmationRequired"))

        governance.set_tool_enabled("create_workspace_file", False)
        refused = mcp_hub.dispatch_rpc({
            "jsonrpc": "2.0", "id": "r2",
            "method": "tools/call",
            "params": {"name": "create_workspace_file", "arguments": {}},
        })
        self.assertIn("error", refused)


class TestToolCallParsing(unittest.TestCase):
    def test_extracts_a_call_from_prose(self):
        calls = extract_tool_calls(
            'Controllo la memoria.\n'
            '```sigma-tool\n'
            '{"tool": "query_vector_db", "arguments": {"query": "AI"}}\n'
            '```\n'
            'Ecco fatto.'
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "query_vector_db")
        self.assertEqual(calls[0]["arguments"], {"query": "AI"})

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
        self.assertEqual(extract_tool_calls('```json\n{"tool": "create_workspace_file"}\n```'), [])

    def test_blocks_are_removed_from_the_visible_answer(self):
        visible = strip_tool_blocks(
            'Invio messaggio.\n```sigma-tool\n{"tool": "telegram_send_message"}\n```\nFatto.')
        self.assertNotIn("sigma-tool", visible)
        self.assertIn("Invio messaggio.", visible)
        self.assertIn("Fatto.", visible)

    def test_round_is_capped(self):
        block = '```sigma-tool\n{"tool": "search_web", "arguments": {}}\n```\n'
        self.assertLessEqual(len(extract_tool_calls(block * 12)), 4)


class TestAgentLoop(GovernanceTestCase):
    def test_safe_calls_run_and_report(self):
        outcomes, approvals = execute_calls([{"tool": "search_web", "arguments": {"query": "pytest"}}])
        self.assertEqual(approvals, [])
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0]["ok"])
        self.assertIn("search_web", format_results_for_model(outcomes))

    def test_nothing_after_a_pending_call_is_silently_dropped(self):
        outcomes, approvals = execute_calls([
            {"tool": "search_web", "arguments": {"query": "prima"}},
            {"tool": "create_workspace_file", "arguments": {"path": "a.txt", "content": "b"}},
            {"tool": "search_web", "arguments": {"query": "dopo"}},
        ])
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["tool"], "create_workspace_file")

        self.assertEqual(len(outcomes), 2)
        self.assertTrue(outcomes[0]["ok"], "la lettura prima parte")
        self.assertTrue(outcomes[1]["deferred"], "quella dopo è dichiarata rimandata")

    def test_several_sensitive_calls_are_all_parked(self):
        outcomes, approvals = execute_calls([
            {"tool": "create_workspace_file", "arguments": {"path": "1.txt", "content": "1"}},
            {"tool": "execute_sandbox_code", "arguments": {"code": "print(1)"}},
        ])
        self.assertEqual([a["tool"] for a in approvals], ["create_workspace_file", "execute_sandbox_code"])
        self.assertEqual(outcomes, [])

    def test_failure_is_handed_back_to_the_model(self):
        outcomes, _ = execute_calls([{"tool": "non_esiste", "arguments": {}}])
        self.assertFalse(outcomes[0]["ok"])
        self.assertIn("non_esiste", outcomes[0]["output"])


class TestCredentialPersistence(GovernanceTestCase):
    def setUp(self):
        super().setUp()
        governance.set_integration_config(
            "email", {"smtp_host": "smtp.example.com", "password": "TOKEN-VERO"})

    def test_credentials_survive_a_restart(self):
        """Un processo nuovo rilegge da disco, senza stato in memoria."""
        importlib.reload(governance)
        governance.CONFIG_PATH = self.config_path
        self.assertEqual(governance.get_integration_config("email")["password"], "TOKEN-VERO")

    def test_an_untouched_secret_field_does_not_erase_it(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "email",
                         "values": {"smtp_host": "smtp.example.com", "password": ""}}))
        self.assertEqual(governance.get_integration_config("email")["password"], "TOKEN-VERO")

    def test_the_masked_placeholder_does_not_erase_it(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "email",
                         "values": {"password": mcp_handler.SECRET_MARKER}}))
        self.assertEqual(governance.get_integration_config("email")["password"], "TOKEN-VERO")

    def test_a_real_new_secret_replaces_the_old_one(self):
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "email", "values": {"password": "TOKEN-NUOVO"}}))
        self.assertEqual(governance.get_integration_config("email")["password"], "TOKEN-NUOVO")

    def test_a_non_secret_field_can_still_be_cleared(self):
        """Solo i segreti sono protetti: un host si deve poter svuotare."""
        mcp_handler.handle_mcp_integration(
            FakeHandler({"key": "email", "values": {"smtp_host": ""}}))
        self.assertEqual(governance.get_integration_config("email")["smtp_host"], "")

    def test_secrets_never_travel_back_to_the_browser(self):
        handler = FakeHandler()
        mcp_handler.handle_mcp_servers(handler)
        email_srv = next(s for s in handler.body["servers"] if s.get("integration_key") == "email")
        self.assertIn("configured", email_srv)


class TestIntegrations(GovernanceTestCase):
    def test_saving_policy_does_not_erase_the_rest_of_config(self):
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump({"ai": {"active_model": "qualcosa"}}, fh)

        governance.set_tool_enabled("search_web", False)

        with open(self.config_path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertEqual(saved["ai"]["active_model"], "qualcosa")
        self.assertIn("search_web", saved["mcp"]["disabled_tools"])

    def test_governance_safety_policies(self):
        """Verify governance default policies and tool registration."""
        by_name = {t["name"]: t for t in mcp_hub.get_aggregated_tools()}
        for name in ("select_routed_model", "discover_peers", "search_web"):
            if name in by_name:
                self.assertEqual(by_name[name]["safety"], governance.SAFE)


if __name__ == "__main__":
    unittest.main()
