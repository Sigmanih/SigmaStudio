# ==============================================================================
# tests/test_cloud_native_tool_calling.py — Test Tool-Calling Nativo Provider Cloud
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Verifica end-to-end del tool-calling strutturato nativo contro provider cloud.

Copre il percorso nativo per OpenAI, DeepSeek, Anthropic e altri provider cloud:
invio dello schema `tools=[...]`, ricezione dei delta di streaming SSE,
accumulo frammentato in `ToolCallAccumulator`, traduzione in invocazioni interne
ed esecuzione da parte dell'harness senza passare da fence testuali o euristiche.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.harness.tool_schema import (
    supports_native_tools,
    schemas_for,
    tool_calls_to_invocations,
)
from core.harness.providers import stream_dev_generation
from core.harness.loop import stream_admin_agent_turn
from core.harness.ledger import DevSessionLedger


class TestCloudNativeToolCalling(unittest.TestCase):
    """Verifica il flusso completo del tool-calling nativo per provider cloud."""

    def test_provider_supports_native_tools_detection(self):
        """Verifica che i provider cloud siano riconosciuti per il tool calling nativo."""
        self.assertTrue(supports_native_tools("openai"))
        self.assertTrue(supports_native_tools("deepseek"))
        self.assertTrue(supports_native_tools("anthropic"))
        self.assertTrue(supports_native_tools("openrouter"))
        self.assertTrue(supports_native_tools("groq"))
        # Provider locali non devono usare tool calling nativo
        self.assertFalse(supports_native_tools("sigma_engine"))
        self.assertFalse(supports_native_tools("ollama"))

    @patch("core.ai_providers.requests.post")
    def test_openai_compatible_stream_delivers_accumulated_tool_calls(self, mock_post):
        """Simula la risposta in streaming SSE da OpenAI/DeepSeek con frammenti di tool_calls."""
        from core.ai_providers import call_openai_compatible_stream

        # Simulazione di uno stream SSE dove la chiamata a `read_file` arriva spezzata in 3 chunk
        sse_lines = [
            'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_abc123", "type": "function", "function": {"name": "read_file", "arguments": ""}}]}}]}',
            'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\\"path\\": \\"core/paths.py\\""}}]}}]}',
            'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ", \\"offset\\": 1}"}}]}}]}',
            'data: {"choices": [{"finish_reason": "tool_calls", "delta": {}}]}',
            'data: [DONE]',
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = sse_lines
        mock_post.return_value = mock_resp

        tools = schemas_for(["read_file", "terminal"])
        events = list(call_openai_compatible_stream(
            messages=[{"role": "user", "content": "leggi core/paths.py"}],
            model="deepseek-coder",
            api_url="https://api.deepseek.com/chat/completions",
            api_key="sk-testkey-12345",
            temperature=0.2,
            max_tokens=2048,
            top_p=0.9,
            timeout=60,
            tools=tools,
        ))

        # Verifica che la richiesta POST contenga il payload corretto con 'tools'
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs.get("json", {})
        self.assertEqual(payload.get("model"), "deepseek-coder")
        self.assertIn("tools", payload)
        self.assertEqual(len(payload["tools"]), 2)

        # Verifica che gli eventi emessi contengano i tool_calls ricomposti
        tool_call_events = [e for e in events if "tool_calls" in e]
        self.assertEqual(len(tool_call_events), 1)
        complete_call = tool_call_events[0]["tool_calls"][0]
        self.assertEqual(complete_call["id"], "call_abc123")
        self.assertEqual(complete_call["function"]["name"], "read_file")
        args = json.loads(complete_call["function"]["arguments"])
        self.assertEqual(args, {"path": "core/paths.py", "offset": 1})

    @patch("core.harness.providers.call_ai_model_stream")
    @patch("core.harness.providers.load_ai_config")
    def test_stream_dev_generation_emits_native_tools_status(self, mock_load_cfg, mock_call_ai):
        """Verifica che stream_dev_generation segnali l'abilitazione del tool-calling nativo."""
        mock_load_cfg.return_value = {
            "active_provider": "openai",
            "providers": {
                "openai": {
                    "api_url": "https://api.openai.com/v1/chat/completions",
                    "api_key": "sk-test-openai",
                    "model": "gpt-4o",
                }
            }
        }
        mock_call_ai.return_value = iter([
            {"tool_calls": [{"id": "call_1", "function": {"name": "list_dir", "arguments": '{"path": "."}'}}]},
            {"done": True},
        ])

        tools = schemas_for(["list_dir"])
        chunks = list(stream_dev_generation(
            messages=[{"role": "user", "content": "elenca i file"}],
            provider="openai",
            model_name="gpt-4o",
            tools=tools,
        ))

        # Primo evento deve essere la dichiarazione dei native tools
        self.assertTrue(chunks[0].get("native_tools"))
        self.assertEqual(chunks[0].get("provider"), "openai")

        # Poi arrivano i tool calls
        tool_chunks = [c for c in chunks if "tool_calls" in c]
        self.assertEqual(len(tool_chunks), 1)
        self.assertEqual(tool_chunks[0]["tool_calls"][0]["function"]["name"], "list_dir")

    @patch("core.harness.loop.stream_dev_generation")
    def test_admin_agent_turn_executes_native_tool_call(self, mock_stream_dev):
        """Verifica che l'agente elabori ed esegua una tool call nativa da provider cloud."""
        # Creiamo uno scenario in cui l'agente riceve una chiamata nativa per eseguire un comando terminale
        mock_stream_dev.return_value = iter([
            {"native_tools": True, "provider": "deepseek"},
            {"thinking": "Eseguo un test di verifica rapido tramite comando terminale."},
            {
                "tool_calls": [
                    {
                        "id": "call_exec_001",
                        "function": {
                            "name": "terminal",
                            "arguments": '{"command": "python -c \\"print(\'NATIVE_TOOL_OK\')\\""}',
                        },
                    }
                ]
            },
            {"done": True},
        ])

        ledger = DevSessionLedger(goal="Verificare tool-calling nativo")
        events = list(stream_admin_agent_turn(
            session_id="test-cloud-native",
            messages=[{"role": "user", "content": "esegui la verifica"}],
            provider="deepseek",
            model_name="deepseek-chat",
            ledger=ledger,
            max_turns=1,
        ))

        # Deve annunciare l'attivazione del tool-calling nativo
        status_events = [e for e in events if e.get("type") == "status"]
        self.assertTrue(any("Tool-calling nativo attivo" in s.get("text", "") for s in status_events))

        # Deve aver registrato ed eseguito il comando
        self.assertEqual(len(ledger._commands), 1)
        self.assertIn("NATIVE_TOOL_OK", ledger._commands[0]["command"])
        self.assertTrue(ledger._commands[0]["ok"])

        # Deve emettere l'evento di tool_result per il comando eseguito
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        self.assertTrue(len(tool_results) >= 1)
        self.assertEqual(tool_results[0].get("tool"), "terminal")


if __name__ == "__main__":
    unittest.main()
