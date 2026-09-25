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
        self.assertFalse(SigmaRustBackend.supports(facts_safetensors, {}))
        self.assertFalse(SigmaRustBackend.supports(facts_other, {}))

    def test_score_priority(self):
        facts = ModelFacts(path="/tmp/fake.gguf", name="test_model", weight_format="gguf")
        # Quando il kernel Rust è online: punteggio prioritario 125 che supera llama-server (110)
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=True):
            self.assertEqual(SigmaRustBackend.score(facts, {}), 125)

        # Quando il kernel Rust è offline: punteggio 0
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=False):
            self.assertEqual(SigmaRustBackend.score(facts, {}), 0)

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

        # Quando è online vince per punteggio (125 vs 110/100)
        with patch("core.engine.backends.sigmarust_backend._is_rust_kernel_online", return_value=True):
            with patch.object(SigmaRustBackend, "availability", return_value=(True, "Online")):
                chosen = select_backend(facts, hardware)
                self.assertIsNotNone(chosen)
                self.assertEqual(chosen.name, "sigma_engine_rust")


class TestSenzaWorkerNonSiDichiaraCaricato(unittest.TestCase):
    """Il kernel e' un orchestratore: senza worker di calcolo non risponde.

    La rotta `/v1/chat/completions` del kernel restituisce 503 quando nessun
    upstream risponde, ed e' una scelta dichiarata (coda_inferenza.json: meglio
    un rifiuto che testo inventato -- il forward pass in Rust e' la voce i2, non
    ancora scritta). Quello che non deve succedere e' che il caricamento risulti
    riuscito lo stesso: la chat elencherebbe fra i modelli attivi uno che non
    produce un token, ed e' esattamente cio' che l'utente chiama "non funziona".
    """

    def _facts(self):
        return ModelFacts(path="/tmp/fake.gguf",
                          name="XHToken--Spark-X2.5-4B-GGUF",
                          weight_format="gguf")

    def _delegato(self, **configurazione):
        return patch("core.engine.backends.llamaserver_backend.LlamaServerBackend",
                     return_value=MagicMock(**configurazione))

    def test_un_worker_che_non_parte_fa_fallire_il_caricamento(self):
        esito = {
            "success": False, "stage": "runtime",
            "error": "La build di llama.cpp installata (b10682) non conosce "
                     "l'architettura 'spark2_5'.",
        }
        with self._delegato(load=MagicMock(return_value=esito)):
            backend = SigmaRustBackend()
            risultato = backend.load(self._facts(), {})

        self.assertFalse(risultato.get("success"))
        self.assertIn("non conosce l'architettura", risultato.get("error"))
        self.assertEqual(risultato.get("stage"), "runtime")
        self.assertFalse(backend.is_loaded)

    def test_un_worker_che_esplode_non_diventa_un_caricamento(self):
        with self._delegato(load=MagicMock(side_effect=RuntimeError("niente da fare"))):
            backend = SigmaRustBackend()
            risultato = backend.load(self._facts(), {})

        self.assertFalse(risultato.get("success"))
        self.assertIn("RuntimeError", risultato.get("error"))
        self.assertFalse(backend.is_loaded)

    def test_il_messaggio_non_consiglia_di_ridurre_il_contesto(self):
        """Un runtime che non conosce l'architettura non e' un problema di memoria."""
        from core.engine.unified_runtime import sigma_engine

        messaggio = sigma_engine._format_load_failure("XHToken--Spark-X2.5-4B-GGUF", {
            "success": False, "stage": "runtime",
            "error": "La build di llama.cpp installata (b10682) non conosce "
                     "l'architettura 'spark2_5'. Il file GGUF e' valido: aggiorna "
                     "il runtime dal pannello del motore e riprova.",
        })
        self.assertIn("non conosce l'architettura", messaggio)
        self.assertNotIn("riduci il contesto", messaggio)

    def test_con_il_worker_pronto_ma_il_kernel_irraggiungibile_si_usa_il_worker(self):
        """Il caso opposto: il calcolo c'e', il kernel e' caduto, e si prosegue."""
        finto = MagicMock()
        finto.load.return_value = {"success": True}
        finto.is_loaded = True

        with self._delegato(load=finto.load):
            with patch("core.engine.backends.sigmarust_backend.urllib.request.urlopen",
                       side_effect=OSError("kernel giu'")):
                risultato = SigmaRustBackend().load(self._facts(), {})

        self.assertTrue(risultato.get("success"))
        self.assertTrue(risultato.get("fallback"))


if __name__ == "__main__":
    unittest.main()
