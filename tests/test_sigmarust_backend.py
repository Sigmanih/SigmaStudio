# tests/test_sigmarust_backend.py — Test per SigmaRustBackend
import unittest
from unittest.mock import patch, MagicMock
import json

from core.engine.backends.sigmarust_backend import SigmaRustBackend, _is_rust_kernel_online
from core.engine.backends.registry import select_backend, all_backends
from core.engine.model_inspector import ModelFacts


class TestSigmaRustBackend(unittest.TestCase):
    def test_backend_in_registry(self):
        backends = all_backends()
        self.assertIn(SigmaRustBackend, backends)

    def test_supports_formats(self):
        facts_gguf = ModelFacts(path="/tmp/fake.gguf", name="test_model", weight_format="gguf")
        facts_safetensors = ModelFacts(path="/tmp/fake.st", name="test_st", weight_format="safetensors")
        facts_other = ModelFacts(path="/tmp/fake.bin", name="test_other", weight_format="pytorch_bin")

        self.assertTrue(SigmaRustBackend.supports(facts_gguf, {}))
        self.assertTrue(SigmaRustBackend.supports(facts_safetensors, {}))
        self.assertFalse(SigmaRustBackend.supports(facts_other, {}))

    def test_score_priority(self):
        facts = ModelFacts(path="/tmp/fake.gguf", name="test_model", weight_format="gguf")
        # Default: 95 per non scavalcare l'inferenza CUDA reale di llama-server
        self.assertEqual(SigmaRustBackend.score(facts, {}), 95)

        # Con SIGMA_RUST_INFERENCE=1: priorità massima (120)
        with patch.dict("os.environ", {"SIGMA_RUST_INFERENCE": "1"}):
            self.assertEqual(SigmaRustBackend.score(facts, {}), 120)

    @patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online")
    def test_availability(self, mock_online):
        mock_online.return_value = True
        avail, reason = SigmaRustBackend.availability()
        self.assertTrue(avail)
        self.assertIn("attivo", reason)

        mock_online.return_value = False
        avail, reason = SigmaRustBackend.availability()
        self.assertFalse(avail)

    def test_select_backend_prefers_rust_when_online(self):
        facts = ModelFacts(path="/tmp/fake.gguf", name="qwen", weight_format="gguf")
        hardware = {"accelerators": []}

        # Con SIGMA_RUST_INFERENCE=1 vince per punteggio (120 vs 110/100)
        with patch.dict("os.environ", {"SIGMA_RUST_INFERENCE": "1"}):
            with patch.object(SigmaRustBackend, "availability", return_value=(True, "Online")):
                chosen = select_backend(facts, hardware)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.name, "sigma_engine_rust")


if __name__ == "__main__":
    unittest.main()
