# ==============================================================================
# tests/test_radix_cache_integration.py — Test Integrazione Radix Prefix Cache
# ==============================================================================
import unittest
from unittest.mock import MagicMock, patch

from core.chat.chat_runner import _lookup_radix_prefix_cache
from core.engine.backends.sigmarust_backend import SigmaRustBackend


class TestRadixCacheIntegration(unittest.TestCase):
    """Verifica l'interazione tra Chat Runner e la Radix Prefix Cache del kernel Rust."""

    def test_lookup_empty_messages(self):
        matched, total, ratio, tokens, backend = _lookup_radix_prefix_cache([])
        self.assertEqual(matched, 0)
        self.assertEqual(total, 0)
        self.assertEqual(ratio, 0.0)
        self.assertEqual(tokens, [])

    def test_lookup_single_non_system_message(self):
        messages = [{"role": "user", "content": "Ciao"}]
        matched, total, ratio, tokens, backend = _lookup_radix_prefix_cache(messages)
        self.assertEqual(matched, 0)
        self.assertEqual(total, 0)
        self.assertEqual(ratio, 0.0)

    @patch("core.engine.backends.sigmarust_backend.SigmaRustBackend.tokenize")
    @patch("core.engine.backends.sigmarust_backend.SigmaRustBackend.lookup_prefix_cache")
    def test_lookup_with_history_match(self, mock_lookup, mock_tok):
        mock_tok.return_value = [101, 102, 103, 104]
        mock_lookup.return_value = {"status": "ok", "matched_tokens": 3}

        messages = [
            {"role": "user", "content": "Come ti chiami?"},
            {"role": "assistant", "content": "Sono Sigma Studio."},
            {"role": "user", "content": "Cosa puoi fare?"}
        ]

        matched, total, ratio, tokens, backend = _lookup_radix_prefix_cache(messages)
        self.assertEqual(matched, 3)
        self.assertEqual(total, 4)
        self.assertEqual(ratio, 75.0)
        self.assertEqual(tokens, [101, 102, 103, 104])

    def test_sigmarust_backend_tokenize_fallback(self):
        backend = SigmaRustBackend()
        # Con URL non raggiungibile o offline, il ripiego deterministico genera token interi validi
        toks = backend.tokenize("Sigma Studio Kernel Rust")
        self.assertIsInstance(toks, list)
        self.assertEqual(len(toks), 4)
        for t in toks:
            self.assertIsInstance(t, int)
            self.assertGreaterEqual(t, 0)

    def test_sigmarust_backend_empty_tokenize(self):
        backend = SigmaRustBackend()
        self.assertEqual(backend.tokenize(""), [])
        self.assertEqual(backend.tokenize(None), [])
