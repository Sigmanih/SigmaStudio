# ==============================================================================
# tests/test_dev_provider_routing.py — Test per il routing multi-provider del dev agent
# ==============================================================================
import unittest
from unittest.mock import MagicMock, patch

from core.developer_studio.provider_bridge import stream_dev_generation


class TestDevProviderRouting(unittest.TestCase):
    """Verifica che stream_dev_generation instradi correttamente a SigmaEngine o ai provider esterni."""

    @patch("core.developer_studio.provider_bridge.sigma_engine")
    @patch("core.developer_studio.provider_bridge.load_ai_config")
    def test_routes_to_sigma_engine_by_default(self, mock_load_cfg, mock_engine):
        mock_load_cfg.return_value = {"active_provider": "sigma_engine", "active_model": "sigma-test"}
        mock_engine.generate_stream.return_value = iter([{"token": "Hello"}, {"token": " World"}])

        chunks = list(stream_dev_generation(
            messages=[{"role": "user", "content": "test"}],
            provider="sigma_engine",
        ))

        self.assertEqual(len(chunks), 2)
        self.assertEqual("".join(c["token"] for c in chunks), "Hello World")
        mock_engine.generate_stream.assert_called_once()

    @patch("core.developer_studio.provider_bridge.call_ai_model_stream")
    @patch("core.developer_studio.provider_bridge.load_ai_config")
    def test_routes_to_external_provider(self, mock_load_cfg, mock_call_ai):
        mock_load_cfg.return_value = {
            "active_provider": "sigma_engine",
            "providers": {
                "deepseek": {
                    "api_url": "https://api.deepseek.com/v1/chat/completions",
                    "api_key": "sk-test",
                    "model": "deepseek-coder",
                    "top_p": 0.9,
                    "timeout": 60,
                }
            }
        }
        mock_call_ai.return_value = iter([{"token": "def "}, {"token": "foo(): pass"}])

        chunks = list(stream_dev_generation(
            messages=[{"role": "user", "content": "write code"}],
            provider="deepseek",
            model_name="deepseek-coder",
        ))

        self.assertEqual(len(chunks), 2)
        self.assertEqual("".join(c["token"] for c in chunks), "def foo(): pass")
        mock_call_ai.assert_called_once()
        args, kwargs = mock_call_ai.call_args
        self.assertEqual(kwargs.get("provider"), "deepseek")
        self.assertEqual(kwargs.get("model"), "deepseek-coder")


if __name__ == "__main__":
    unittest.main()
